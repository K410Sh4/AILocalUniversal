from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.cognitive_pipeline import analyze_request
from core.deterministic_tools import DeterministicToolRegistry
from core.validation_layer import ValidationLayer
from kia_bridge.flow import (
    KiaExecutionCoordinator,
    append_kia_plan_to_task,
    execute_deterministic_selection,
    record_validated_deterministic_feedback,
)
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.hardware import HardwareProfile
from model_hub.registry import ModelRegistry
from napa import create_default_registry
from resources.contracts import ResourcePlacement


class FakeRuntimeClient:
    """Simula somente o protocolo: a política de candidato vem dos contratos da rede."""

    def __init__(self) -> None:
        self.state = None
        self.request = None
        self.feedback = []

    def replace_state(self, state):
        self.state = state
        return {"network_version": 0}

    def plan(self, request):
        self.request = request
        network = self.state["network"]
        executor_ids = set(self.state["available_executors"])
        selections = []

        for capability_id in request["required_capabilities"]:
            candidates = [
                item
                for item in network["components"].values()
                if item["enabled"]
                and item["resource_estimate_available"]
                and capability_id in item["supported_capabilities"]
                and item["id"] in executor_ids
            ]
            if not candidates:
                return {
                    "request_id": request["request_id"],
                    "network_version": 0,
                    "selections": [],
                    "reserved_resources": {},
                }
            selected = max(
                candidates,
                key=lambda item: (item["baseline_quality"], item["id"]),
            )
            existing = next(
                (
                    item for item in selections
                    if item["component_id"] == selected["id"]
                ),
                None,
            )
            if existing is None:
                selections.append(
                    {
                        "component_id": selected["id"],
                        "capabilities": [capability_id],
                        "estimated_cost": selected["estimated_cost"],
                        "routing_score": selected["baseline_quality"],
                    }
                )
            else:
                existing["capabilities"].append(capability_id)

        return {
            "request_id": request["request_id"],
            "network_version": 0,
            "selections": selections,
            "reserved_resources": {},
        }

    def record_feedback(self, feedback, *, learning_rate=0.05):
        self.feedback.append((feedback, learning_rate))
        return {"updated_weight": 0.9, "observations": 1}


class FakeResourceManager:
    def __init__(self, placement=ResourcePlacement.CPU):
        self.placement = placement

    def cpu_thread_limit(self, *, resource_profile, hardware):
        return 4

    def estimate_model(self, model_id, registry, *, context_tokens, hardware):
        return SimpleNamespace(
            placement=self.placement,
            total_required_bytes=512 * 1024 * 1024
            if self.placement is ResourcePlacement.CPU else None,
        )


def hardware_profile():
    return HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=8,
        ram_total_bytes=16 * 1024**3,
        ram_available_bytes=12 * 1024**3,
        disk_free_bytes=100 * 1024**3,
        accelerators=(),
    )


def model_registry(tmp_path):
    registry = ModelRegistry(tmp_path / "model-registry.json")
    registry.upsert(
        ModelRecord(
            record_id="ollama:qwen3:4b",
            display_name="Qwen3 4B",
            family="qwen3",
            category="general",
            capabilities=("chat",),
            artifacts=(
                ModelArtifact(
                    runtime="ollama",
                    reference="qwen3:4b",
                    installed=True,
                ),
            ),
        )
    )
    return registry


@pytest.mark.asyncio
async def test_rust_plan_selects_python_calculator_then_validation_allows_feedback(
    tmp_path,
) -> None:
    task = await analyze_request(
        "Quanto é 12 * (3 + 2)?",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    tools = DeterministicToolRegistry()
    coordinator = KiaExecutionCoordinator(
        client,
        tools=tools,
        napa_registry=create_default_registry(),
    )

    decision = coordinator.plan_task(
        task,
        model_registry=ModelRegistry(tmp_path / "empty-registry.json"),
        resource_manager=FakeResourceManager(),
        hardware=hardware_profile(),
        engine_names=("ollama",),
        resource_profile="medium",
        model_references=(),
    )

    assert len(decision.deterministic_selections()) == 1
    selected = decision.deterministic_selections()[0]["component"]
    assert selected["metadata"]["tool_name"] == "calculator"

    result = execute_deterministic_selection(task, decision, tools)
    assert result.value == 60.0
    report = ValidationLayer(tools).validate_deterministic_response(task)
    task.validation_report = report
    assert report["status"] == "passed"
    assert report["factual_status"] == "verified_deterministic"

    append_kia_plan_to_task(task, decision)
    updates = record_validated_deterministic_feedback(client, task)

    assert updates
    expected_updates = len(
        decision.deterministic_selections()[0]["selection"]["capabilities"]
    )
    assert len(client.feedback) == expected_updates


@pytest.mark.asyncio
async def test_rust_plan_selects_registered_chat_model_with_explicit_cpu_estimate(
    tmp_path,
) -> None:
    task = await analyze_request(
        "Explique como funcionam as integrais definidas.",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    coordinator = KiaExecutionCoordinator(client)

    decision = coordinator.plan_task(
        task,
        model_registry=model_registry(tmp_path),
        resource_manager=FakeResourceManager(),
        hardware=hardware_profile(),
        engine_names=("ollama",),
        resource_profile="medium",
        preferred_model="qwen3:4b",
        model_references=("qwen3:4b",),
    )

    assert len(decision.model_selections()) == 1
    component = decision.model_selections()[0]["component"]
    assert component["metadata"]["reference"] == "qwen3:4b"
    assert component["execution_target"] == "remote"
    assert component["estimated_cost"]["ram_bytes"] == 512 * 1024 * 1024
    assert component["estimated_cost"]["cpu_millis"] == 4000
    assert "tool-calculator" not in client.state["network"]["components"]
    assert client.request["input"] == {"task_id": task.task_id}
    assert "Explique como funcionam" not in str(client.request["input"])


@pytest.mark.asyncio
async def test_unknown_model_memory_estimate_is_never_plannable(tmp_path) -> None:
    task = await analyze_request(
        "Explique como funcionam as integrais definidas.",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    coordinator = KiaExecutionCoordinator(client)

    decision = coordinator.plan_task(
        task,
        model_registry=model_registry(tmp_path),
        resource_manager=FakeResourceManager(ResourcePlacement.UNKNOWN),
        hardware=hardware_profile(),
        engine_names=("ollama",),
        resource_profile="medium",
        model_references=("qwen3:4b",),
    )

    assert decision.model_selections() == []
    assert not any(
        item["kind"] == "language_model"
        for item in client.state["network"]["components"].values()
    )


@pytest.mark.asyncio
async def test_high_risk_task_does_not_advertise_deterministic_executors(tmp_path) -> None:
    task = await analyze_request(
        "Calcule a dosagem: 2 / 3",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    coordinator = KiaExecutionCoordinator(client)

    decision = coordinator.plan_task(
        task,
        model_registry=ModelRegistry(tmp_path / "empty-registry.json"),
        resource_manager=FakeResourceManager(),
        hardware=hardware_profile(),
        engine_names=(),
        resource_profile="medium",
        model_references=(),
    )

    calculator_id = "tool-calculator"
    assert client.state["network"]["components"][calculator_id]["enabled"] is False
    assert calculator_id not in client.state["available_executors"]
    assert decision.deterministic_selections() == []


@pytest.mark.asyncio
async def test_kia_planner_selects_knowledge_memory_provider_only_when_enabled(tmp_path) -> None:
    task = await analyze_request(
        "Explique como funcionam as integrais definidas.",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    coordinator = KiaExecutionCoordinator(client)

    decision = coordinator.plan_task(
        task,
        model_registry=model_registry(tmp_path),
        resource_manager=FakeResourceManager(),
        hardware=hardware_profile(),
        engine_names=("ollama",),
        resource_profile="medium",
        preferred_model="qwen3:4b",
        model_references=("qwen3:4b",),
        knowledge_enabled=True,
    )

    assert len(decision.model_selections()) == 1
    assert len(decision.memory_selections()) == 1
    memory = decision.memory_selections()[0]["component"]
    assert memory["id"] == "memory-knowledge-library"
    assert memory["metadata"]["provider"] == "knowledge_library"
    assert "retrieval" in client.request["required_capabilities"]
    assert client.request["input"] == {"task_id": task.task_id}


@pytest.mark.asyncio
async def test_kia_planner_does_not_publish_knowledge_provider_when_disabled(tmp_path) -> None:
    task = await analyze_request(
        "Explique como funcionam as integrais definidas.",
        execute_deterministic=False,
    )
    client = FakeRuntimeClient()
    coordinator = KiaExecutionCoordinator(client)

    decision = coordinator.plan_task(
        task,
        model_registry=model_registry(tmp_path),
        resource_manager=FakeResourceManager(),
        hardware=hardware_profile(),
        engine_names=("ollama",),
        resource_profile="medium",
        model_references=("qwen3:4b",),
        knowledge_enabled=False,
    )

    assert decision.memory_selections() == []
    assert "retrieval" not in client.request["required_capabilities"]
