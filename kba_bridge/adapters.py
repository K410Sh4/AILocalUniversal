"""Conversores explícitos entre NAPA/NeuralModel Hub e contratos Rust K.BA."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any

from model_hub.contracts import ModelRecord
from model_hub.hardware import HardwareProfile
from napa.contracts import NapaClassification
from napa.registry import CognitiveAreaRegistry

DEFAULT_MODEL_AREA_MAP: dict[str, tuple[str, ...]] = {
    "chat": ("generation",),
    "coding": ("programming",),
    "reasoning": ("reasoning",),
    "general": ("generation",),
    "embeddings": ("retrieval",),
    "vision": ("perception",),
}


def _component_id(record_id: str, runtime: str, reference: str) -> str:
    material = f"{record_id}\0{runtime}\0{reference}".encode()
    return "model-" + hashlib.sha256(material).hexdigest()[:24]


def _resource_vector(value: Mapping[str, Any] | None) -> dict[str, int]:
    keys = ("cpu_millis", "ram_bytes", "gpu_millis", "vram_bytes", "npu_units")
    if value is None:
        return dict.fromkeys(keys, 0)
    result: dict[str, int] = {}
    for key in keys:
        item = value.get(key, 0)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ValueError(f"{key} precisa ser inteiro não negativo.")
        result[key] = item
    return result


def capabilities_from_napa(registry: CognitiveAreaRegistry) -> list[dict[str, Any]]:
    """Exporta todas as áreas do registry NAPA como nós de capacidade.

    Afinidades não são copiadas para o grafo; as âncoras/intents são tags
    declarativas e o CognitiveRequest traz as áreas ativadas para cada tarefa.
    """
    capabilities = []
    for area in registry.areas:
        capabilities.append(
            {
                "id": area.area_id,
                "name": area.name,
                "domain": area.kind.value,
                "intent_tags": sorted(set(area.intents).union(area.anchors)),
                "context_tags": [],
                "enabled": True,
            }
        )
    return capabilities


def components_from_model_records(
    records: Sequence[ModelRecord],
    *,
    capability_ids: set[str],
    resource_estimates: Mapping[str, Mapping[str, Any]] | None = None,
    execution_targets: Mapping[str, str] | None = None,
    baseline_quality: Mapping[str, float] | None = None,
    capability_area_map: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    """Converte apenas artefatos instalados em componentes cognitivos.

    Tamanho do artefato em disco nunca é convertido em RAM/VRAM. Para ser elegível
    no planner, o chamador precisa fornecer custo medido/estimado e alvo explícito.
    resource_estimates aceita component_id ou record_id como chave;
    execution_targets aceita component_id, record_id ou nome do runtime.
    """
    estimates = resource_estimates or {}
    targets = execution_targets or {}
    quality_scores = baseline_quality or {}
    area_map = capability_area_map or DEFAULT_MODEL_AREA_MAP
    components: list[dict[str, Any]] = []
    seen_component_ids: set[str] = set()

    for record in records:
        mapped: set[str] = set()
        for advertised in record.capabilities:
            mapped.update(area_map.get(advertised, ()))
        mapped.update(area_map.get(record.category, ()))
        supported = sorted(mapped.intersection(capability_ids))
        if not supported:
            continue

        for artifact in record.artifacts:
            if not artifact.installed:
                continue
            component_id = _component_id(
                record.record_id, artifact.runtime, artifact.reference
            )
            if component_id in seen_component_ids:
                raise ValueError(f"Artefato duplicado no registro de modelos: {component_id}")
            seen_component_ids.add(component_id)
            raw_estimate = estimates.get(component_id, estimates.get(record.record_id))
            target_value = targets.get(
                component_id,
                targets.get(record.record_id, targets.get(artifact.runtime)),
            )
            cost = _resource_vector(raw_estimate)
            estimate_available = raw_estimate is not None and target_value is not None
            target = str(target_value).casefold() if target_value is not None else "cpu"
            if target not in {"cpu", "gpu", "npu", "remote"}:
                raise ValueError(f"Alvo de execução inválido: {target_value!r}.")

            quality = quality_scores.get(record.record_id, 0.5)
            if (
                isinstance(quality, bool)
                or not isinstance(quality, (int, float))
                or not math.isfinite(quality)
                or not 0.0 <= quality <= 1.0
            ):
                raise ValueError(
                    f"baseline_quality de {record.record_id} precisa estar entre 0 e 1."
                )

            metadata = {
                "record_id": record.record_id,
                "family": record.family,
                "category": record.category,
                "runtime": artifact.runtime,
                "reference": artifact.reference,
                "installed": "true",
            }
            if artifact.digest:
                metadata["digest"] = artifact.digest
            if artifact.quantization:
                metadata["quantization"] = artifact.quantization
            components.append(
                {
                    "id": component_id,
                    "name": record.display_name,
                    "kind": "language_model",
                    "supported_capabilities": supported,
                    "context_tags": [],
                    "execution_target": target,
                    "estimated_cost": cost,
                    "resource_estimate_available": estimate_available,
                    "baseline_quality": float(quality),
                    "enabled": True,
                    "metadata": metadata,
                }
            )
    return components


def build_network_payload(
    registry: CognitiveAreaRegistry,
    records: Sequence[ModelRecord],
    *,
    resource_estimates: Mapping[str, Mapping[str, Any]] | None = None,
    execution_targets: Mapping[str, str] | None = None,
    baseline_quality: Mapping[str, float] | None = None,
    available_executor_ids: Sequence[str] = (),
    capability_area_map: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Monta HostState serializável, com conexões supports iniciais neutras."""
    capabilities = capabilities_from_napa(registry)
    capability_ids = {item["id"] for item in capabilities}
    components = components_from_model_records(
        records,
        capability_ids=capability_ids,
        resource_estimates=resource_estimates,
        execution_targets=execution_targets,
        baseline_quality=baseline_quality,
        capability_area_map=capability_area_map,
    )
    capability_map = {item["id"]: item for item in capabilities}
    component_map = {item["id"]: item for item in components}
    connections = []
    for component in components:
        for capability_id in component["supported_capabilities"]:
            connections.append(
                {
                    "from": {"node_type": "capability", "id": capability_id},
                    "to": {"node_type": "component", "id": component["id"]},
                    "kind": "supports",
                    "weight": 0.5,
                    "observations": 0,
                    "successes": 0,
                }
            )

    executor_ids = sorted(set(available_executor_ids))
    unknown_executors = set(executor_ids) - set(component_map)
    if unknown_executors:
        raise ValueError(
            "Executores referenciam modelos não registrados: "
            + ", ".join(sorted(unknown_executors))
        )

    return {
        "network": {
            "capabilities": capability_map,
            "components": component_map,
            "connections": connections,
            "feedback_history": [],
            "version": 0,
        },
        "available_executors": executor_ids,
    }


def resource_snapshot_from_hardware(
    hardware: HardwareProfile,
    *,
    available_targets: Sequence[str] = ("cpu",),
    gpu_compute_millis: int = 0,
    npu_units: int = 0,
) -> dict[str, Any]:
    """Converte medições conhecidas; acelerador só é elegível se declarado pelo backend.

    CPU disponível representa a capacidade lógica total observada, não uma medição
    instantânea de CPU ociosa. GPU/NPU requerem capacidade fornecida explicitamente
    por um provider de backend; a presença física do dispositivo não prova suporte
    do motor de inferência.
    """
    cores = hardware.cpu_logical_cores
    ram_total = hardware.ram_total_bytes
    ram_available = hardware.ram_available_bytes
    if cores is None or cores <= 0:
        raise ValueError("Quantidade de CPUs lógicas não foi medida.")
    if ram_total is None or ram_available is None or ram_total <= 0 or ram_available < 0:
        raise ValueError("RAM total e disponível precisam ser medidas.")
    if ram_available > ram_total:
        raise ValueError("RAM disponível não pode exceder a RAM total.")
    if (
        isinstance(gpu_compute_millis, bool)
        or not isinstance(gpu_compute_millis, int)
        or gpu_compute_millis < 0
    ):
        raise ValueError("gpu_compute_millis precisa ser inteiro não negativo.")
    if isinstance(npu_units, bool) or not isinstance(npu_units, int) or npu_units < 0:
        raise ValueError("npu_units precisa ser inteiro não negativo.")

    targets = sorted({str(item).casefold() for item in available_targets})
    if not targets or set(targets) - {"cpu", "gpu", "npu", "remote"}:
        raise ValueError("available_targets contém alvo inválido.")
    if "gpu" in targets and gpu_compute_millis <= 0:
        raise ValueError("GPU requer capacidade computacional explicitamente medida.")
    if "npu" in targets and npu_units <= 0:
        raise ValueError("NPU requer unidades disponíveis explicitamente medidas.")

    gpu_devices = [
        item for item in hardware.accelerators
        if item.vram_total_bytes is not None and item.vram_available_bytes is not None
    ]
    vram_total = max((item.vram_total_bytes or 0 for item in gpu_devices), default=0)
    vram_available = max(
        (item.vram_available_bytes or 0 for item in gpu_devices), default=0
    )
    if "gpu" in targets and vram_available <= 0:
        raise ValueError("GPU selecionável requer VRAM disponível medida.")

    cpu_millis = cores * 1000
    gpu_millis = gpu_compute_millis if "gpu" in targets else 0
    npu_capacity = npu_units if "npu" in targets else 0
    return {
        "total": {
            "cpu_millis": cpu_millis,
            "ram_bytes": ram_total,
            "gpu_millis": gpu_millis,
            "vram_bytes": vram_total if "gpu" in targets else 0,
            "npu_units": npu_capacity,
        },
        "available": {
            "cpu_millis": cpu_millis,
            "ram_bytes": ram_available,
            "gpu_millis": gpu_millis,
            "vram_bytes": vram_available if "gpu" in targets else 0,
            "npu_units": npu_capacity,
        },
        "available_targets": targets,
    }


def resource_budget_from_profile(
    snapshot: Mapping[str, Any],
    profile: str = "medium",
) -> dict[str, Any]:
    """Produz o budget lógico correspondente aos perfis 33/66/95."""
    percentages = {"light": 33, "medium": 66, "ultra": 95}
    key = profile.casefold()
    if key not in percentages:
        raise ValueError("Perfil precisa ser light, medium ou ultra.")
    total = _resource_vector(snapshot["total"])
    available = _resource_vector(snapshot["available"])
    if any(available[name] > total[name] for name in total):
        raise ValueError("Recursos disponíveis excedem a capacidade total.")
    cpu_limit = total["cpu_millis"] * percentages[key] // 100
    max_budget = dict(available)
    max_budget["cpu_millis"] = min(cpu_limit, available["cpu_millis"])
    return {"max": max_budget}


def cognitive_request_from_napa(
    request_id: str,
    intent: str,
    classification: NapaClassification,
    *,
    input_payload: Any,
    context_tags: Sequence[str] = (),
    max_components: int = 4,
) -> dict[str, Any]:
    """Converte as áreas ativadas pela NAPA em uma solicitação Rust 1.0."""
    if not request_id.strip():
        raise ValueError("request_id não pode ficar vazio.")
    if not intent.strip():
        raise ValueError("intent não pode ficar vazia.")
    active = list(dict.fromkeys(classification.active_area_ids))
    if not active:
        raise ValueError("NAPA não ativou nenhuma área cognitiva para esta solicitação.")
    if max_components < 1:
        raise ValueError("max_components precisa ser positivo.")
    return {
        "schema_version": 1,
        "request_id": request_id,
        "intent": intent,
        "context_tags": sorted(set(context_tags)),
        "required_capabilities": active,
        "input": input_payload,
        "max_components": max_components,
    }


def host_state_payload(
    network_payload: Mapping[str, Any],
    resource_snapshot: Mapping[str, Any],
    *,
    processing_profile: str = "medium",
) -> dict[str, Any]:
    """Combina catálogo cognitivo, disponibilidade e perfil em HostState."""
    return {
        "network": network_payload["network"],
        "resources": dict(resource_snapshot),
        "budget": resource_budget_from_profile(resource_snapshot, processing_profile),
        "available_executors": list(network_payload["available_executors"]),
    }


def executor_ids_for_registered_engines(
    network_payload: Mapping[str, Any],
    engine_names: Sequence[str],
) -> list[str]:
    """Retorna componentes-modelo cujos runtimes têm EngineAdapter registrado.

    Isso confirma a presença de um adapter por runtime, não saúde do servidor nem
    disponibilidade atual do modelo. O inventário de artefatos instalados continua
    sendo a segunda condição para um componente aparecer na rede.
    """
    known_engines = {name.casefold() for name in engine_names if name.strip()}
    components = network_payload.get("network", {}).get("components", {})
    if not isinstance(components, Mapping):
        raise ValueError("network.components precisa ser um mapa.")
    return sorted(
        component_id
        for component_id, component in components.items()
        if isinstance(component, Mapping)
        and str(component.get("metadata", {}).get("runtime", "")).casefold()
        in known_engines
    )
