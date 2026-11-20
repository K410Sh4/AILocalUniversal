import json
from pathlib import Path

import pytest

from core.neuralinjector.resources import (
    CANONICAL_PROFILES,
    AdaptiveResourceManager,
    BenchmarkMode,
    GPUDevice,
    HardwareSnapshot,
    ProtectionMode,
    ResourceMonitor,
    ResourcePressure,
    ResourceRequirements,
    build_compatibility_report,
    detect_hardware,
    select_profile,
    serialize_hardware_profile,
)


def hw(total=8192, available=6144, vram=None, backends=("cpu",), features=(), disk=None):
    return HardwareSnapshot(
        total,
        available,
        vram,
        vram,
        4,
        frozenset(features),
        frozenset(backends),
        disk_free_mb=disk,
    )


def test_low_memory_selects_minimal():
    assert select_profile(hw(4096, 2500)).profile_id == "minimal"


def test_constrained_host_selects_ultra_light():
    assert select_profile(hw(2048, 1800)).profile_id == "ultra_light"


def test_powerful_machine_selects_max_quality():
    assert select_profile(hw(65536, 50000, 24000, ("cpu", "gpu"))).profile_id == "max_quality"


def test_unknown_gpu_is_not_assumed():
    report = build_compatibility_report(hw())
    assert any("VRAM desconhecida" in item for item in report.fallbacks)
    assert report.budget.selected_backend == "cpu"


def test_required_features_are_enforced():
    report = build_compatibility_report(
        hw(), ResourceRequirements(required_features=("flash_attention",))
    )
    assert not report.compatible
    assert not report.activation_allowed
    assert any("flash_attention" in item for item in report.reasons)


def test_minimum_ram_is_not_silently_degraded():
    report = build_compatibility_report(
        hw(4096, 3000), ResourceRequirements(min_ram_mb=8192)
    )
    assert not report.compatible
    assert not report.activation_allowed


def test_minimum_vram_requires_known_available_memory():
    report = build_compatibility_report(
        hw(), ResourceRequirements(min_vram_mb=2048)
    )
    assert not report.compatible
    assert any("VRAM" in item for item in report.reasons)


def test_minimum_disk_requires_a_measured_target_path():
    report = build_compatibility_report(
        hw(), ResourceRequirements(min_disk_mb=1024)
    )
    assert not report.compatible
    assert any("disco desconhecido" in item for item in report.reasons)


def test_minimum_disk_is_checked_when_measured():
    report = build_compatibility_report(
        hw(disk=512), ResourceRequirements(min_disk_mb=1024)
    )
    assert not report.compatible
    assert any("disco abaixo" in item for item in report.reasons)


def test_permissive_mode_cannot_override_absolute_memory_floor():
    report = build_compatibility_report(
        hw(1024, 700),
        protection_mode=ProtectionMode.PERMISSIVE,
    )
    assert not report.compatible
    assert not report.activation_allowed
    assert report.protection_mode == "permissive"
    assert "1,5 GiB" in report.user_message
    assert report.recommendations


def test_protected_mode_rejects_unavailable_requested_profile():
    report = build_compatibility_report(
        hw(8192, 5000),
        preferred_profile="performance",
        protection_mode=ProtectionMode.PROTECTED,
    )
    assert report.selected_profile == "balanced"
    assert not report.compatible
    assert not report.activation_allowed
    assert any("modo protegido" in item for item in report.reasons)


def test_adaptive_mode_falls_back_to_eligible_profile():
    report = build_compatibility_report(
        hw(8192, 5000),
        preferred_profile="performance",
        protection_mode=ProtectionMode.ADAPTIVE,
    )
    assert report.selected_profile == "balanced"
    assert report.compatible
    assert report.activation_allowed
    assert any("perfil performance indisponível" in item for item in report.fallbacks)


def test_quantization_candidate_requires_backend_capability_confirmation():
    report = build_compatibility_report(
        hw(4096, 2000),
        supported_quantizations=("Q4_0", "Q5_K_M"),
    )
    assert report.quantization_candidate == "Q4_0"


def test_quantization_is_not_selected_when_backend_has_not_reported_support():
    report = build_compatibility_report(hw(4096, 2000))
    assert report.quantization_candidate is None
    assert any("quantização não selecionada" in item for item in report.fallbacks)


def test_quantization_is_not_guessed_when_no_candidate_is_supported():
    report = build_compatibility_report(
        hw(4096, 2000),
        supported_quantizations=("FP16",),
    )
    assert report.quantization_candidate is None
    assert any("nenhum candidato" in item for item in report.fallbacks)


def test_none_benchmark_does_not_run():
    calls = []
    report = build_compatibility_report(
        hw(), benchmark=lambda mode: calls.append(mode) or {}
    )
    assert calls == []
    assert report.benchmark_result is None


@pytest.mark.parametrize("mode", [BenchmarkMode.QUICK, BenchmarkMode.FULL])
def test_benchmark_requires_explicit_mode(mode):
    calls = []
    report = build_compatibility_report(
        hw(),
        benchmark_mode=mode,
        benchmark=lambda value: calls.append(value) or {"tokens_per_second": 12.5},
    )
    assert calls == [mode.value]
    assert report.benchmark_result["tokens_per_second"] == 12.5


def test_detection_reports_cpu_and_memory_without_gpu_probe():
    detected = detect_hardware()
    assert detected.ram_total_mb > 0
    assert detected.cpu_cores > 0
    assert "cpu" in detected.execution_backends
    assert detected.gpu_devices == ()


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        select_profile(hw(), "turbo")


def test_host_below_ultra_light_floor_is_incompatible():
    report = build_compatibility_report(hw(1024, 700))
    assert not report.compatible
    assert not report.activation_allowed
    assert any("ultra_light" in reason for reason in report.reasons)


def test_dynamic_manager_enters_critical_and_emergency_states():
    manager = AdaptiveResourceManager()
    critical = manager.evaluate(hw(10000, 1000), active_parallelism=3)
    assert critical.pressure is ResourcePressure.CRITICAL
    assert critical.pause_new_loads
    assert critical.parallelism_limit == 1

    emergency = manager.evaluate(hw(10000, 500), active_parallelism=2)
    assert emergency.pressure is ResourcePressure.EMERGENCY
    assert emergency.reject_new_loads
    assert emergency.suspend_optional_work


def test_dynamic_manager_uses_hysteresis_before_recovering():
    manager = AdaptiveResourceManager()
    manager.evaluate(hw(10000, 500))
    still_emergency = manager.evaluate(hw(10000, 2000))
    assert still_emergency.pressure is ResourcePressure.EMERGENCY

    recovered = manager.evaluate(hw(10000, 3500))
    assert recovered.pressure is ResourcePressure.NORMAL


def test_dynamic_manager_does_not_kill_active_generation():
    manager = AdaptiveResourceManager()
    decision = manager.evaluate(
        hw(10000, 500),
        active_parallelism=1,
        active_context_tokens=4096,
    )
    assert decision.reject_new_loads
    assert any("suspender tarefas opcionais" in action for action in decision.actions)
    assert not any("cancelar geração" in action for action in decision.actions)


def test_dynamic_manager_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        AdaptiveResourceManager(
            emergency_threshold=0.2,
            critical_threshold=0.1,
        )


def test_detected_gpu_does_not_automatically_register_execution_backend(monkeypatch):
    import core.neuralinjector.resources as resources

    monkeypatch.setattr(
        resources,
        "_detect_ram",
        lambda: type("Ram", (), {"total_mb": 16384, "available_mb": 12000})(),
    )
    monkeypatch.setattr(
        resources,
        "detect_gpu_devices",
        lambda **_kwargs: (
            GPUDevice("GPU", "amd", 8192, 6000, "dedicated", "test"),
        ),
    )

    detected = detect_hardware(include_gpu=True)

    assert detected.gpu_devices[0].vendor == "amd"
    assert detected.vram_total_mb == 8192
    assert detected.vram_available_mb == 6000
    assert detected.execution_backends == frozenset({"cpu"})


def test_multiple_gpus_are_not_counted_as_unified_vram(monkeypatch):
    import core.neuralinjector.resources as resources

    monkeypatch.setattr(
        resources,
        "_detect_ram",
        lambda: type("Ram", (), {"total_mb": 32768, "available_mb": 24000})(),
    )
    monkeypatch.setattr(
        resources,
        "detect_gpu_devices",
        lambda **_kwargs: (
            GPUDevice("GPU A", "amd", 8192, 4096, "dedicated", "test"),
            GPUDevice("GPU B", "nvidia", 4096, 3072, "dedicated", "test"),
        ),
    )

    detected = detect_hardware(
        include_gpu=True,
        execution_backends=("cpu", "gpu"),
    )

    assert detected.vram_total_mb == 8192
    assert detected.vram_available_mb == 4096
    assert detected.vram_total_mb != 8192 + 4096


def test_integrated_gpu_does_not_receive_invented_dedicated_vram(monkeypatch):
    import core.neuralinjector.resources as resources

    monkeypatch.setattr(
        resources,
        "_detect_ram",
        lambda: type("Ram", (), {"total_mb": 8192, "available_mb": 6000})(),
    )
    monkeypatch.setattr(
        resources,
        "detect_gpu_devices",
        lambda **_kwargs: (
            GPUDevice("Integrated GPU", "intel", None, None, "shared", "test"),
        ),
    )

    detected = detect_hardware(include_gpu=True)

    assert len(detected.gpu_devices) == 1
    assert detected.gpu_devices[0].memory_kind == "shared"
    assert detected.vram_total_mb is None
    assert detected.vram_available_mb is None


def test_resource_monitor_is_inert_until_explicitly_started():
    monitor = ResourceMonitor(snapshot_provider=lambda: hw(10000, 1000))

    assert not monitor.is_running
    assert monitor.last_snapshot is None
    assert monitor.last_decision is None


def test_resource_monitor_poll_once_publishes_snapshot_and_decision():
    observed = []
    monitor = ResourceMonitor(
        snapshot_provider=lambda: hw(10000, 1000),
        on_decision=observed.append,
        active_parallelism=2,
    )

    decision = monitor.poll_once()

    assert decision.pressure is ResourcePressure.CRITICAL
    assert monitor.last_snapshot.ram_available_mb == 1000
    assert monitor.last_decision == decision
    assert observed == [decision]


def test_resource_monitor_rejects_high_frequency_polling():
    with pytest.raises(ValueError, match="at least 1 second"):
        ResourceMonitor(interval_seconds=0.5)


@pytest.mark.parametrize("profile", CANONICAL_PROFILES, ids=lambda item: item.profile_id)
def test_json_profile_matches_python_canonical_definition(profile):
    root = Path(__file__).resolve().parents[2]
    path = (
        root
        / "examples"
        / "neuralinjector"
        / "hardware"
        / "profiles"
        / f"{profile.profile_id}.json"
    )
    actual = json.loads(path.read_text(encoding="utf-8"))

    assert actual == serialize_hardware_profile(profile)


def test_profile_budget_separates_cpu_threads_from_request_parallelism():
    profile = next(item for item in CANONICAL_PROFILES if item.profile_id == "ultra_light")
    assert profile.parallelism == 1
    assert profile.max_cpu_threads == 2


def test_protected_report_explains_profile_refusal_and_alternative():
    report = build_compatibility_report(
        hw(8192, 5000),
        preferred_profile="performance",
        protection_mode=ProtectionMode.PROTECTED,
    )

    assert not report.activation_allowed
    assert "bloqueada" in report.user_message
    assert report.recommendations
    assert any("balanced" in item or "perfil" in item for item in report.recommendations)


def test_host_below_absolute_floor_cannot_be_permitted():
    report = build_compatibility_report(
        hw(1024, 700),
        protection_mode=ProtectionMode.PERMISSIVE,
    )

    assert not report.activation_allowed
    assert "piso absoluto" in " ".join(report.reasons)
    assert len(report.recommendations) >= 3


def test_permissive_mode_reports_risk_when_it_allows_a_non_floor_override():
    report = build_compatibility_report(
        hw(8192, 5000),
        ResourceRequirements(min_ram_mb=8192),
        protection_mode=ProtectionMode.PERMISSIVE,
    )

    assert not report.compatible
    assert report.activation_allowed
    assert "modo permissivo autorizou" in report.user_message
    assert report.recommendations
