from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kia_bridge import (
    KiaRuntimeClient,
    KiaRuntimeError,
    KiaRuntimeUnavailable,
    build_network_payload,
    cognitive_request_from_napa,
    host_state_payload,
    resource_budget_from_profile,
    resource_snapshot_from_hardware,
)
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.hardware import AcceleratorInfo, HardwareProfile
from napa import CognitiveAreaClassifier, create_default_registry


def _fake_host(path: Path) -> list[str]:
    path.write_text(
        """#!/usr/bin/env python3
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    kind = request["command"]["type"]
    if kind == "health":
        result = {"service": "kia-cognitive-runtime", "version": "0.4.0"}
    elif kind == "shutdown":
        result = {"shutdown": True}
    elif kind == "inspect":
        result = {"network_version": 1}
    elif kind == "echo":
        result = request["command"].get("payload", {})
    else:
        result = None
    print(json.dumps({
        "protocol_version": 2,
        "request_id": request["request_id"],
        "ok": True,
        "result": result
    }), flush=True)
    if kind == "shutdown":
        break
""",
        encoding="utf-8",
    )
    path.chmod(0o700)
    return [sys.executable, str(path)]


def test_client_starts_persistent_process_correlates_requests_and_shuts_down(
    tmp_path: Path,
) -> None:
    command = _fake_host(tmp_path / "fake-host.py")

    with KiaRuntimeClient(command, timeout_seconds=2.0) as client:
        assert client.health()["service"] == "kia-cognitive-runtime"
        assert client._request("echo", {"value": "á"}).get("value") == "á"
        assert client.inspect()["network_version"] == 1

    assert client._closed is True
    assert client._process.poll() == 0


def test_client_rejects_oversized_utf8_request_without_desynchronizing_host(
    tmp_path: Path,
) -> None:
    command = _fake_host(tmp_path / "bounded-host.py")
    with KiaRuntimeClient(command, timeout_seconds=2.0) as client:
        with pytest.raises(KiaRuntimeError) as error:
            client._request("echo", {"value": "é" * (2 * 1024 * 1024 + 1)})
        assert error.value.code == "request_too_large"
        assert client._request("echo", {"value": "still-aligned"}) == {
            "value": "still-aligned"
        }


def test_client_rejects_non_json_request_payload(tmp_path: Path) -> None:
    command = _fake_host(tmp_path / "json-host.py")
    with KiaRuntimeClient(command, timeout_seconds=2.0) as client:
        with pytest.raises(KiaRuntimeError) as error:
            client._request("echo", {"value": object()})
        assert error.value.code == "invalid_request_payload"
        assert client.health()["service"] == "kia-cognitive-runtime"


def test_client_rejects_missing_executable() -> None:
    with pytest.raises(KiaRuntimeUnavailable):
        KiaRuntimeClient("/definitely/not/a/kia-runtime-host")


def test_client_rejects_incompatible_or_malformed_host_response(
    tmp_path: Path,
) -> None:
    script = tmp_path / "bad-host.py"
    script.write_text(
        """#!/usr/bin/env python3
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    print(json.dumps({
        "protocol_version": 99,
        "request_id": request["request_id"],
        "ok": True,
        "result": {}
    }), flush=True)
""",
        encoding="utf-8",
    )
    script.chmod(0o700)

    with pytest.raises(KiaRuntimeError, match="Versão do protocolo"):
        KiaRuntimeClient([sys.executable, str(script)], timeout_seconds=2.0)


def test_napa_registry_exports_all_declared_areas_and_active_request() -> None:
    registry = create_default_registry()
    classification = CognitiveAreaClassifier(registry=registry).classify(
        "Crie uma função Python para calcular juros compostos.",
        intent="programming",
    )

    state_network = build_network_payload(registry, [])
    capabilities = state_network["network"]["capabilities"]
    request = cognitive_request_from_napa(
        "task-001",
        "Crie uma função Python para calcular juros compostos.",
        classification,
        input_payload={"task": "calcular juros"},
        context_tags=["software_project"],
    )

    assert set(capabilities) == set(registry.area_ids)
    assert {"programming", "mathematics", "generation"} <= set(
        request["required_capabilities"]
    )
    assert request["schema_version"] == 1
    assert request["context_tags"] == ["software_project"]


def test_model_artifact_size_never_becomes_resource_estimate() -> None:
    record = ModelRecord(
        record_id="ollama:qwen3-coder:4b",
        display_name="Qwen3 Coder 4B",
        family="qwen3-coder",
        category="coding",
        capabilities=("chat", "tool_calling"),
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3-coder:4b",
                installed=True,
                size_bytes=8_000_000_000,
            ),
        ),
    )
    network = build_network_payload(registry=create_default_registry(), records=[record])
    components = network["network"]["components"]
    assert len(components) == 1
    component = next(iter(components.values()))
    assert component["resource_estimate_available"] is False
    assert component["estimated_cost"] == {
        "cpu_millis": 0,
        "ram_bytes": 0,
        "gpu_millis": 0,
        "vram_bytes": 0,
        "npu_units": 0,
    }


def test_measured_model_cost_and_explicit_target_make_component_eligible() -> None:
    registry = create_default_registry()
    record = ModelRecord(
        record_id="ollama:qwen3-coder:4b",
        display_name="Qwen3 Coder 4B",
        family="qwen3-coder",
        category="coding",
        capabilities=("chat", "tool_calling"),
        artifacts=(
            ModelArtifact("ollama", "qwen3-coder:4b", installed=True, size_bytes=9_000),
        ),
    )
    network = build_network_payload(
        registry,
        [record],
        resource_estimates={
            "ollama:qwen3-coder:4b": {
                "cpu_millis": 1200,
                "ram_bytes": 5_000_000_000,
            }
        },
        execution_targets={"ollama": "cpu"},
    )

    component = next(iter(network["network"]["components"].values()))
    assert component["resource_estimate_available"] is True
    assert component["estimated_cost"]["ram_bytes"] == 5_000_000_000
    assert component["execution_target"] == "cpu"
    assert len(network["network"]["connections"]) == 2


def test_model_bridge_ignores_uninstalled_artifacts_and_unknown_capabilities() -> None:
    record = ModelRecord(
        record_id="ollama:embedding:latest",
        display_name="Embedding",
        family="embedding",
        capabilities=("embeddings", "unverified"),
        artifacts=(
            ModelArtifact("ollama", "embedding:latest", installed=False),
        ),
    )
    network = build_network_payload(create_default_registry(), [record])
    assert network["network"]["components"] == {}


def test_hardware_snapshot_uses_measured_values_and_explicit_gpu_backend() -> None:
    hardware = HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=8,
        ram_total_bytes=16_000_000_000,
        ram_available_bytes=10_000_000_000,
        disk_free_bytes=100_000_000_000,
        accelerators=(
            AcceleratorInfo(
                vendor="AMD",
                name="Test GPU",
                vram_total_bytes=8_000_000_000,
                vram_used_bytes=2_000_000_000,
                vram_available_bytes=6_000_000_000,
            ),
        ),
    )

    cpu_only = resource_snapshot_from_hardware(hardware)
    assert cpu_only["available_targets"] == ["cpu"]
    assert cpu_only["available"]["gpu_millis"] == 0
    assert cpu_only["available"]["vram_bytes"] == 0

    cpu_gpu = resource_snapshot_from_hardware(
        hardware,
        available_targets=("cpu", "gpu"),
        gpu_compute_millis=2000,
    )
    assert cpu_gpu["available"]["gpu_millis"] == 2000
    assert cpu_gpu["available"]["vram_bytes"] == 6_000_000_000


def test_hardware_bridge_does_not_infer_gpu_compute_support_from_device_presence() -> None:
    hardware = HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test",
        cpu_logical_cores=8,
        ram_total_bytes=8_000,
        ram_available_bytes=4_000,
        disk_free_bytes=1_000,
        accelerators=(
            AcceleratorInfo(
                vendor="AMD",
                name="GPU",
                vram_total_bytes=4_000,
                vram_available_bytes=2_000,
            ),
        ),
    )
    with pytest.raises(ValueError, match="capacidade computacional"):
        resource_snapshot_from_hardware(
            hardware,
            available_targets=("cpu", "gpu"),
        )


@pytest.mark.parametrize(
    ("profile", "expected"),
    [("light", 2640), ("medium", 5280), ("ultra", 7600)],
)
def test_resource_profiles_translate_to_logical_cpu_budget(
    profile: str,
    expected: int,
) -> None:
    snapshot = {
        "total": {
            "cpu_millis": 8000,
            "ram_bytes": 16_000,
            "gpu_millis": 0,
            "vram_bytes": 0,
            "npu_units": 0,
        },
        "available": {
            "cpu_millis": 8000,
            "ram_bytes": 12_000,
            "gpu_millis": 0,
            "vram_bytes": 0,
            "npu_units": 0,
        },
        "available_targets": ["cpu"],
    }

    assert resource_budget_from_profile(snapshot, profile)["max"]["cpu_millis"] == expected
    state = host_state_payload(
        {
            "network": {"capabilities": {}, "components": {}, "connections": [],
                        "feedback_history": [], "version": 0},
            "available_executors": [],
        },
        snapshot,
        processing_profile=profile,
    )
    assert state["budget"]["max"]["ram_bytes"] == 12_000


def test_resource_budget_rejects_free_memory_larger_than_total() -> None:
    snapshot = {
        "total": {"cpu_millis": 1000, "ram_bytes": 10, "gpu_millis": 0,
                  "vram_bytes": 0, "npu_units": 0},
        "available": {"cpu_millis": 1000, "ram_bytes": 11, "gpu_millis": 0,
                      "vram_bytes": 0, "npu_units": 0},
    }
    with pytest.raises(ValueError, match="excedem"):
        resource_budget_from_profile(snapshot)



def test_engine_registry_names_select_only_matching_installed_model_artifacts() -> None:
    from kia_bridge import executor_ids_for_registered_engines

    record = ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="Qwen3 4B",
        family="qwen3",
        capabilities=("chat",),
        artifacts=(
            ModelArtifact("ollama", "qwen3:4b", installed=True),
            ModelArtifact("remote-api", "qwen3:4b", installed=True),
        ),
    )
    network = build_network_payload(create_default_registry(), [record])

    selected = executor_ids_for_registered_engines(network, ("ollama",))

    components = network["network"]["components"]
    assert selected == [
        component_id
        for component_id, component in components.items()
        if component["metadata"]["runtime"] == "ollama"
    ]
    assert len(selected) == 1
