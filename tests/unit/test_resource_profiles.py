import pytest

from model_hub.hardware import HardwareProfile
from resources.manager import AdaptiveResourceManager
from resources.profiles import (
    ResourceProfile,
    cpu_thread_budget,
    normalize_resource_profile,
)


@pytest.mark.parametrize(
    ("profile", "percent"),
    [("light", 33), ("medium", 66), ("ultra", 95)],
)
def test_profiles_use_the_requested_percentages(profile, percent) -> None:
    assert ResourceProfile(profile).usage_percent == percent


@pytest.mark.parametrize(
    ("profile", "expected_threads"),
    [("light", 4), ("medium", 8), ("ultra", 11)],
)
def test_cpu_thread_budget_approximates_percent(profile, expected_threads) -> None:
    assert cpu_thread_budget(12, profile) == expected_threads


def test_cpu_thread_budget_returns_none_when_core_count_is_unknown() -> None:
    assert cpu_thread_budget(None, "light") is None


def test_invalid_resource_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Perfil de processamento inválido"):
        normalize_resource_profile("extreme")


def test_resource_manager_maps_profiles_to_detected_logical_cores() -> None:
    hardware = HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=16,
        ram_total_bytes=32 * 1024**3,
        ram_available_bytes=20 * 1024**3,
        disk_free_bytes=100 * 1024**3,
    )
    manager = AdaptiveResourceManager()

    assert manager.cpu_thread_limit("light", hardware=hardware) == 5
    assert manager.cpu_thread_limit("medium", hardware=hardware) == 11
    assert manager.cpu_thread_limit("ultra", hardware=hardware) == 15
