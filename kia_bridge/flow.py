"""Fluxo vertical ACCA v0.3: NAPA -> plano Rust -> executor Python -> validação."""

# ruff: noqa: I001  # Absolute project imports plus relative package imports are intentional.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.cognitive_task import CognitiveTask
from core.deterministic_tools import DeterministicToolRegistry, ToolResult
from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile
from model_hub.registry import ModelRegistry
from napa.contracts import AreaActivation, CognitiveAreaKind, NapaClassification
from napa.registry import CognitiveAreaRegistry, create_default_registry
from resources.contracts import ResourcePlacement

from .adapters import (
    build_network_payload,
    cognitive_request_from_napa,
    executor_ids_for_registered_engines,
    host_state_payload,
    resource_budget_from_profile,
    resource_snapshot_from_hardware,
)
from .client import KiaRuntimeClient


MIB = 1024 * 1024
DETERMINISTIC_TOOL_RESERVATION = {
    "cpu_millis": 100,
    "ram_bytes": 2 * MIB,
    "gpu_millis": 0,
    "vram_bytes": 0,
    "npu_units": 0,
}
_TOOL_AREAS: dict[str, tuple[str, ...]] = {
    "calculator": ("mathematics", "tool_use"),
    "unit_converter": ("conversion", "tool_use"),
}


class KiaFlowError(RuntimeError):
    """O plano K.IA não pode ser executado com segurança nesta versão."""


@dataclass(frozen=True, slots=True)
class KiaPlanDecision:
    """Plano Rust e catálogo exato que permite resolver IDs para executores."""

    request: dict[str, Any]
    network_payload: dict[str, Any]
    plan: dict[str, Any]

    @property
    def selections(self) -> list[dict[str, Any]]:
        return list(self.plan.get("selections", []))

    def selected_components(self) -> list[dict[str, Any]]:
        components = self.network_payload["network"]["components"]
        selected: list[dict[str, Any]] = []
        for selection in self.selections:
            component_id = str(selection.get("component_id", ""))
            component = components.get(component_id)
            if not isinstance(component, dict):
                raise KiaFlowError(
                    f"O plano Rust referencia um componente inexistente: {component_id}"
                )
            selected.append(
                {
                    "selection": selection,
                    "component": component,
                }
            )
        return selected

    def deterministic_selections(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.selected_components()
            if item["component"].get("kind") == "deterministic_tool"
        ]

    def model_selections(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.selected_components()
            if item["component"].get("kind") == "language_model"
        ]

    def memory_selections(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.selected_components()
            if item["component"].get("kind") == "memory"
            and item["component"].get("metadata", {}).get("provider")
            == "knowledge_library"
        ]


def _classification_from_task(
    task: CognitiveTask,
    registry: CognitiveAreaRegistry,
) -> NapaClassification:
    payload = task.cognitive_areas
    if not isinstance(payload, dict):
        raise KiaFlowError("A classificação NAPA da tarefa precisa ser um objeto.")

    active_ids = payload.get("active_areas", [])
    activations = payload.get("activations", [])
    if (
        not isinstance(active_ids, list)
        or not isinstance(activations, list)
        or any(not isinstance(area_id, str) or not area_id for area_id in active_ids)
        or len(active_ids) != len(set(active_ids))
    ):
        raise KiaFlowError("A classificação NAPA da tarefa está malformada.")

    by_id: dict[str, dict[str, Any]] = {}
    for item in activations:
        if not isinstance(item, dict):
            raise KiaFlowError("A classificação NAPA contém uma ativação inválida.")
        area_id = item.get("area_id")
        if not isinstance(area_id, str) or not area_id or area_id in by_id:
            raise KiaFlowError("A classificação NAPA contém IDs de ativação inválidos ou duplicados.")
        by_id[area_id] = item

    if set(by_id) != set(active_ids):
        raise KiaFlowError("Áreas ativas e ativações NAPA não correspondem.")

    resolved: list[AreaActivation] = []
    for area_id in active_ids:
        area = registry.find(area_id)
        activation = by_id[area_id]
        if area is None:
            raise KiaFlowError(f"A área NAPA '{area_id}' não possui contrato válido.")

        affinity = activation.get("affinity")
        signals = activation.get("signals")
        if (
            isinstance(affinity, bool)
            or not isinstance(affinity, (int, float))
            or not isinstance(signals, list)
            or not signals
            or any(not isinstance(signal, str) or not signal for signal in signals)
        ):
            raise KiaFlowError(f"A ativação NAPA '{area_id}' possui campos inválidos.")
        try:
            resolved.append(
                AreaActivation(
                    area_id=area_id,
                    kind=area.kind,
                    affinity=affinity,
                    signals=tuple(signals),
                )
            )
        except (TypeError, ValueError) as exc:
            raise KiaFlowError(
                f"A ativação NAPA '{area_id}' não respeita o contrato."
            ) from exc

    classifier_version = payload.get("classifier_version", "napa-1.0")
    method = payload.get("method", "lexical_capability_intent_heuristics")
    if (
        not isinstance(classifier_version, str)
        or not classifier_version.strip()
        or not isinstance(method, str)
        or not method.strip()
    ):
        raise KiaFlowError("Metadados da versão NAPA estão malformados.")

    return NapaClassification(
        activations=tuple(resolved),
        classifier_version=classifier_version,
        method=method,
    )


def _model_capability_map(
    registry: CognitiveAreaRegistry,
) -> dict[str, tuple[str, ...]]:
    """Converte metadados declarados do modelo em áreas que ele pode atender.

    Um modelo de chat genérico recebe somente áreas cognitivas gerais. Especialistas
    como programação/visão/embeddings exigem a categoria ou modalidade correspondente.
    """
    general = tuple(
        area.area_id
        for area in registry.areas
        if area.kind is CognitiveAreaKind.COGNITIVE_CAPABILITY
    )
    explanatory_areas = tuple(
        area_id for area_id in ("mathematics", "conversion") if area_id in registry.area_ids
    )
    general_and_explanatory = tuple(dict.fromkeys((*general, *explanatory_areas)))
    mapping: dict[str, tuple[str, ...]] = {
        "chat": general_and_explanatory,
        "general": general_and_explanatory,
    }
    known = set(registry.area_ids)
    for key, area_id in (
        ("coding", "programming"),
        ("reasoning", "reasoning"),
        ("vision", "perception"),
        ("embeddings", "retrieval"),
    ):
        if area_id in known:
            mapping[key] = (area_id,)
    return mapping


def _add_tool_components(
    network_payload: dict[str, Any],
    *,
    tool_names: tuple[str, ...],
    intent: str,
    risk: float | None,
) -> None:
    network = network_payload["network"]
    capabilities = network["capabilities"]
    components = network["components"]
    connections = network["connections"]
    executor_ids = set(network_payload["available_executors"])
    safe_to_run = risk is None or risk < 0.55

    for tool_name, supported_areas in _TOOL_AREAS.items():
        if tool_name not in tool_names:
            continue
        if tool_name == "calculator" and intent != "calculation":
            continue
        if tool_name == "unit_converter" and intent != "unit_conversion":
            continue
        supported = sorted(area for area in supported_areas if area in capabilities)
        if not supported:
            continue
        component_id = f"tool-{tool_name.replace('_', '-')}"
        components[component_id] = {
            "id": component_id,
            "name": tool_name,
            "kind": "deterministic_tool",
            "supported_capabilities": supported,
            "context_tags": [],
            "execution_target": "cpu",
            "estimated_cost": dict(DETERMINISTIC_TOOL_RESERVATION),
            "resource_estimate_available": True,
            "baseline_quality": 1.0,
            "enabled": safe_to_run,
            "metadata": {
                "tool_name": tool_name,
                "adapter": "python_deterministic_registry",
                "resource_estimate_source": "static_reservation_v1",
            },
        }
        for capability_id in supported:
            connections.append(
                {
                    "from": {"node_type": "capability", "id": capability_id},
                    "to": {"node_type": "component", "id": component_id},
                    "kind": "supports",
                    "weight": 0.9,
                    "observations": 0,
                    "successes": 0,
                }
            )
        if safe_to_run:
            executor_ids.add(component_id)

    network_payload["available_executors"] = sorted(executor_ids)


def execute_deterministic_selection(
    task: CognitiveTask,
    decision: KiaPlanDecision,
    tools: DeterministicToolRegistry,
) -> ToolResult:
    """Executa somente a ferramenta Python que o plano Rust efetivamente selecionou."""
    selections = decision.deterministic_selections()
    models = decision.model_selections()
    if len(selections) != 1 or models or len(decision.selections) != 1:
        raise KiaFlowError(
            "A execução local direta exige exatamente uma ferramenta e nenhum modelo."
        )

    component = selections[0]["component"]
    expected_tool = component.get("metadata", {}).get("tool_name")
    if not isinstance(expected_tool, str) or not expected_tool:
        raise KiaFlowError("O componente selecionado não declarou tool_name.")
    result = tools.execute(task.normalized_text or task.original_text)
    if result is None or not result.matched or result.name != expected_tool:
        raise KiaFlowError(
            "A ferramenta Python não corresponde ao componente selecionado pelo Rust."
        )
    task.deterministic_results.append(result.to_dict())
    task.result = {
        "route": "deterministic_only",
        "tool": result.name,
        "content": result.content,
        "success": bool(result.success),
        "value": result.value,
    }
    return result


def _add_knowledge_component(network_payload: dict[str, Any]) -> None:
    """Publica Knowledge/NeSA como provedor somente quando a aplicação habilitou RAG."""
    network = network_payload["network"]
    capabilities = network["capabilities"]
    if "retrieval" not in capabilities:
        raise KiaFlowError("A NAPA não declarou a capacidade retrieval.")
    component_id = "memory-knowledge-library"
    component = {
        "id": component_id,
        "name": "Knowledge Library + NeSA",
        "kind": "memory",
        "supported_capabilities": ["retrieval"],
        "context_tags": ["local_documents", "semantic_page_index"],
        "execution_target": "cpu",
        "estimated_cost": {
            "cpu_millis": 100,
            "ram_bytes": 4 * MIB,
            "gpu_millis": 0,
            "vram_bytes": 0,
            "npu_units": 0,
        },
        "resource_estimate_available": True,
        "baseline_quality": 0.75,
        "enabled": True,
        "metadata": {
            "provider": "knowledge_library",
            "retrieval": "hybrid_chunks_with_nesa_page_candidates",
            "adapter": "python_knowledge_retrieval_worker",
            "resource_estimate_source": "static_logical_reservation_v1",
        },
    }
    network["components"][component_id] = component
    network["connections"].append(
        {
            "from": {"node_type": "capability", "id": "retrieval"},
            "to": {"node_type": "component", "id": component_id},
            "kind": "supports",
            "weight": 0.85,
            "observations": 0,
            "successes": 0,
        }
    )
    executor_ids = set(network_payload["available_executors"])
    executor_ids.add(component_id)
    network_payload["available_executors"] = sorted(executor_ids)


def append_kia_plan_to_task(
    task: CognitiveTask,
    decision: KiaPlanDecision,
    *,
    selected_model: str | None = None,
) -> None:
    """Anexa plano, IDs e reserva ao trace compartilhado da tarefa."""
    task.execution_plan.append(
        {
            "step": len(task.execution_plan),
            "component": "kia_runtime",
            "protocol_version": 1,
            "network_version": decision.plan.get("network_version"),
            "request_id": decision.plan.get("request_id"),
            "selections": decision.selections,
            "reserved_resources": decision.plan.get("reserved_resources", {}),
            "selected_model": selected_model,
        }
    )
    task.execution_trace.append(
        {
            "stage": "kia_runtime",
            "status": "planned",
            "details": {
                "network_version": decision.plan.get("network_version"),
                "selected_component_ids": [
                    item.get("component_id") for item in decision.selections
                ],
                "reserved_resources": decision.plan.get("reserved_resources", {}),
            },
        }
    )


def record_validated_deterministic_feedback(
    client: KiaRuntimeClient,
    task: CognitiveTask,
    *,
    learning_rate: float = 0.05,
) -> list[dict[str, Any]]:
    """Fortalece apenas rotas cujo resultado foi reproduzido pela ValidationLayer."""
    report = task.validation_report or {}
    if (
        report.get("status") != "passed"
        or report.get("factual_status") != "verified_deterministic"
    ):
        return []

    route_step = next(
        (
            step for step in reversed(task.execution_plan)
            if step.get("component") == "kia_runtime"
        ),
        None,
    )
    if route_step is None:
        return []
    validation_ref = (
        f"validation:{task.task_id}:{report.get('checked_at', 'unknown')}"
    )
    updates = []
    for selection in route_step.get("selections", []):
        component_id = str(selection.get("component_id", ""))
        if not component_id.startswith("tool-"):
            continue
        for capability_id in selection.get("capabilities", []):
            updates.append(
                client.record_feedback(
                    {
                        "capability_id": str(capability_id),
                        "component_id": component_id,
                        "outcome": "success",
                        "validation_ref": validation_ref,
                        "notes": "Resultado reproduzido pela ValidationLayer.",
                    },
                    learning_rate=learning_rate,
                )
            )
    return updates


class KiaExecutionCoordinator:
    """Monta a rede adaptativa, solicita o plano ao Rust e preserva IDs executáveis."""

    def __init__(
        self,
        client: KiaRuntimeClient,
        *,
        tools: DeterministicToolRegistry | None = None,
        napa_registry: CognitiveAreaRegistry | None = None,
    ) -> None:
        self.client = client
        self.tools = tools or DeterministicToolRegistry()
        self.napa_registry = napa_registry or create_default_registry()

    def plan_task(
        self,
        task: CognitiveTask,
        *,
        model_registry: ModelRegistry,
        resource_manager: Any,
        hardware: HardwareProfile,
        engine_names: tuple[str, ...],
        resource_profile: str,
        preferred_model: str | None = None,
        manual_model: str | None = None,
        model_references: tuple[str, ...] | None = None,
        context_tokens: int | None = None,
        local_engine_endpoint: bool = True,
        knowledge_enabled: bool = False,
        max_components: int = 8,
    ) -> KiaPlanDecision:
        if not task.intent:
            raise KiaFlowError("A tarefa precisa ter uma intenção NAPA/semântica.")
        classification = _classification_from_task(task, self.napa_registry)
        if not classification.active_area_ids:
            raise KiaFlowError("NAPA não ativou nenhuma área cognitiva.")

        records = model_registry.list_records(installed_only=True)
        records = [
            record
            for record in records
            if "chat" in record.capabilities
            and any(
                artifact.installed and artifact.runtime in engine_names
                for artifact in record.artifacts
            )
            and (
                model_references is None
                or any(
                    artifact.installed and artifact.reference in model_references
                    for artifact in record.artifacts
                )
            )
            and (
                manual_model is None
                or any(
                    artifact.installed and artifact.reference == manual_model
                    for artifact in record.artifacts
                )
            )
        ]

        resource_estimates: dict[str, dict[str, int]] = {}
        execution_targets: dict[str, str] = {}
        quality: dict[str, float] = {}
        estimable_records: list[ModelRecord] = []
        token_context = context_tokens or task.token_budget or 4096
        base_snapshot = resource_snapshot_from_hardware(
            hardware,
            available_targets=("cpu", "remote") if local_engine_endpoint else ("cpu",),
        )
        base_budget = resource_budget_from_profile(base_snapshot, resource_profile)
        thread_limit = resource_manager.cpu_thread_limit(
            resource_profile=resource_profile,
            hardware=hardware,
        )
        cpu_reservation = (
            min(thread_limit * 1000, base_budget["max"]["cpu_millis"])
            if thread_limit is not None else 0
        )

        if local_engine_endpoint and cpu_reservation > 0:
            for record in records:
                try:
                    estimate = resource_manager.estimate_model(
                        record.record_id,
                        model_registry,
                        context_tokens=token_context,
                        hardware=hardware,
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                # 0.3 aceita somente colocação integral em RAM. GPU/híbrido ficam
                # no roteamento legado até termos prova do alvo de execução do backend.
                if (
                    estimate.placement is not ResourcePlacement.CPU
                    or estimate.total_required_bytes is None
                ):
                    continue
                resource_estimates[record.record_id] = {
                    # Reserva lógica alinhada ao teto de threads do ResourceManager;
                    # não representa FLOPs nem ocupação física medida.
                    "cpu_millis": cpu_reservation,
                    "ram_bytes": estimate.total_required_bytes,
                }
                execution_targets[record.record_id] = "remote"
                quality[record.record_id] = (
                    0.65 if preferred_model and any(
                        artifact.reference == preferred_model
                        for artifact in record.artifacts
                    ) else 0.50
                )
                estimable_records.append(record)

        network_payload = build_network_payload(
            self.napa_registry,
            estimable_records,
            resource_estimates=resource_estimates,
            execution_targets=execution_targets,
            baseline_quality=quality,
            capability_area_map=_model_capability_map(self.napa_registry),
        )
        registered_model_executors = executor_ids_for_registered_engines(
            network_payload,
            engine_names,
        )
        network_payload["available_executors"] = registered_model_executors
        _add_tool_components(
            network_payload,
            tool_names=self.tools.tool_names(),
            intent=task.intent,
            risk=task.risk,
        )
        if knowledge_enabled:
            _add_knowledge_component(network_payload)

        model_available = bool(registered_model_executors)
        targets = ("cpu", "remote") if model_available else ("cpu",)
        resource_snapshot = resource_snapshot_from_hardware(
            hardware,
            available_targets=targets,
        )
        state = host_state_payload(
            network_payload,
            resource_snapshot,
            processing_profile=resource_profile,
        )
        context_tags = []
        if len(task.subtask_plan) > 1:
            context_tags.append("multi_step")
        if task.risk is not None:
            context_tags.append("risk_high" if task.risk >= 0.55 else "risk_low")
        if task.difficulty is not None:
            context_tags.append(
                "difficulty_high" if task.difficulty >= 0.65 else "difficulty_low"
            )
        request = cognitive_request_from_napa(
            task.task_id,
            task.intent,
            classification,
            input_payload={"task_id": task.task_id},
            context_tags=context_tags,
            max_components=max(1, min(max_components, len(classification.active_area_ids))),
        )
        if knowledge_enabled:
            required = set(request["required_capabilities"])
            required.add("retrieval")
            # Knowledge retrieval é um estágio de entrada; o modelo continua
            # necessário para sintetizar a resposta a partir das evidências.
            if "generation" in self.napa_registry.area_ids:
                required.add("generation")
            request["required_capabilities"] = sorted(required)
            request["max_components"] = min(
                8,
                max(int(request["max_components"]), len(required)),
            )
        self.client.replace_state(state)
        plan = self.client.plan(request)
        decision = KiaPlanDecision(
            request=request,
            network_payload=network_payload,
            plan=plan,
        )
        # Resolve IDs immediately so invalid or stale plans cannot reach execution.
        decision.selected_components()
        return decision
