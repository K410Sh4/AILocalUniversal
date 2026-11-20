from model_hub.compatibility import CompatibilityEngine, CompatibilityStatus
from model_hub.contracts import ModelArtifact, ModelRecord, ResourceRequirements
from model_hub.hardware import AcceleratorInfo, HardwareProfile


def _hardware(ram: int, vram: int | None = None) -> HardwareProfile:
    accelerators = ()
    if vram is not None:
        accelerators = (
            AcceleratorInfo(
                vendor="AMD",
                name="Test GPU",
                vram_total_bytes=vram,
                vram_used_bytes=0,
                vram_available_bytes=vram,
            ),
        )
    return HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=8,
        ram_total_bytes=ram,
        ram_available_bytes=ram,
        disk_free_bytes=None,
        accelerators=accelerators,
    )


def _model(requirements: ResourceRequirements | None) -> ModelRecord:
    return ModelRecord(
        record_id="ollama:test:latest",
        display_name="Test",
        family="Test",
        artifacts=(
            ModelArtifact("ollama", "test:latest", installed=True, size_bytes=100),
        ),
        resource_requirements=requirements,
    )


def test_unknown_when_execution_requirements_are_missing() -> None:
    result = CompatibilityEngine().assess(
        _model(None),
        _hardware(16 * 1024**3, 8 * 1024**3),
        available_runtimes={"ollama"},
    )
    assert result.status is CompatibilityStatus.UNKNOWN
    assert "não estima" in result.reasons[-1]


def test_verified_requirements_can_be_compatible() -> None:
    requirements = ResourceRequirements(
        minimum_ram_bytes=8,
        evidence_url="https://example.org/ram",
        verified=True,
    )
    result = CompatibilityEngine().assess(
        _model(requirements),
        _hardware(16, None),
        available_runtimes={"ollama"},
    )
    assert result.status is CompatibilityStatus.COMPATIBLE


def test_insufficient_ram_is_incompatible() -> None:
    requirements = ResourceRequirements(
        minimum_ram_bytes=20,
        evidence_url="https://example.org/ram",
        verified=True,
    )
    result = CompatibilityEngine().assess(
        _model(requirements),
        _hardware(16),
        available_runtimes={"ollama"},
    )
    assert result.status is CompatibilityStatus.INCOMPATIBLE


def test_required_vram_without_detected_gpu_is_incompatible() -> None:
    requirements = ResourceRequirements(
        minimum_vram_bytes=8,
        evidence_url="https://example.org/vram",
        verified=True,
    )
    result = CompatibilityEngine().assess(
        _model(requirements),
        _hardware(16),
        available_runtimes={"ollama"},
    )
    assert result.status is CompatibilityStatus.INCOMPATIBLE


def test_unavailable_runtime_is_incompatible() -> None:
    requirements = ResourceRequirements(
        minimum_ram_bytes=8,
        evidence_url="https://example.org/ram",
        verified=True,
    )
    result = CompatibilityEngine().assess(
        _model(requirements),
        _hardware(16),
        available_runtimes={"llama_cpp"},
    )
    assert result.status is CompatibilityStatus.INCOMPATIBLE
