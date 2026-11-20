import pytest
from core.neuralinjector.resources import BenchmarkMode, HardwareSnapshot, ResourceRequirements, build_compatibility_report, detect_hardware, select_profile

def hw(total=8192, available=6144, vram=None, backends=("cpu",), features=()):
    return HardwareSnapshot(total, available, vram, vram, 4, frozenset(features), frozenset(backends))

def test_low_memory_selects_minimal():
    assert select_profile(hw(4096, 2500)).profile_id == "minimal"

def test_powerful_machine_selects_max_quality():
    assert select_profile(hw(65536, 50000, 24000, ("cpu", "gpu"))).profile_id == "max_quality"

def test_unknown_gpu_is_not_assumed():
    assert any("não presumir GPU" in x for x in build_compatibility_report(hw()).fallbacks)

def test_required_features_are_enforced():
    report = build_compatibility_report(hw(), ResourceRequirements(required_features=("flash_attention",)))
    assert not report.compatible and any("flash_attention" in x for x in report.reasons)

def test_minimum_ram_is_not_silently_degraded():
    assert not build_compatibility_report(hw(4096, 3000), ResourceRequirements(min_ram_mb=8192)).compatible

def test_none_benchmark_does_not_run():
    calls=[]
    report=build_compatibility_report(hw(), benchmark=lambda mode: calls.append(mode) or {})
    assert calls == [] and report.benchmark_result is None

@pytest.mark.parametrize("mode", [BenchmarkMode.QUICK, BenchmarkMode.FULL])
def test_benchmark_requires_explicit_mode(mode):
    calls=[]
    report=build_compatibility_report(hw(), benchmark_mode=mode, benchmark=lambda m: calls.append(m) or {"tokens_per_second": 12.5})
    assert calls == [mode.value] and report.benchmark_result["tokens_per_second"] == 12.5

def test_detection_reports_cpu_and_memory():
    detected=detect_hardware()
    assert detected.ram_total_mb > 0 and detected.cpu_cores > 0 and "cpu" in detected.execution_backends

def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        select_profile(hw(), "turbo")
