from resources.contracts import EstimateConfidence, ResourcePlacement
from resources.estimator import ResourceEstimator
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.hardware import AcceleratorInfo, HardwareProfile


def hardware_profile(
    *,
    ram_available: int = 11 * 1024**3,
    vram_available: int = 7 * 1024**3,
) -> HardwareProfile:
    return HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=12,
        ram_total_bytes=16 * 1024**3,
        ram_available_bytes=ram_available,
        disk_free_bytes=100 * 1024**3,
        accelerators=(
            AcceleratorInfo(
                vendor="AMD",
                name="Radeon Test GPU",
                vram_total_bytes=8 * 1024**3,
                vram_available_bytes=vram_available,
            ),
        ),
    )


def qwen3_record(
    *,
    parameter_count: int = 4_000_000_000,
    kv_bytes_per_token: int | None = 147_456,
    quantization: str | None = "Q4_K_M",
    context_window: int = 32_768,
    artifact_size: int = 2_600_000_000,
) -> ModelRecord:
    return ModelRecord(
        record_id="ollama:qwen3:4b",
        display_name="Qwen3 4B",
        family="qwen3",
        category="general",
        architecture="qwen3",
        parameter_count=parameter_count,
        context_window=context_window,
        kv_cache_bytes_per_token=kv_bytes_per_token,
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3:4b",
                installed=True,
                size_bytes=artifact_size,
                quantization=quantization,
            ),
        ),
    )


def test_estimator_accounts_for_weights_kv_cache_and_runtime_reserve() -> None:
    result = ResourceEstimator().estimate(
        qwen3_record(),
        hardware_profile(),
        context_tokens=8192,
    )

    assert result.weight_bytes is not None
    assert result.kv_cache_bytes == 147_456 * 8192
    assert result.runtime_overhead_bytes == 768 * 1024**2
    assert result.total_required_bytes == (
        result.weight_bytes + result.kv_cache_bytes + result.runtime_overhead_bytes
    )
    assert result.placement is ResourcePlacement.GPU
    assert result.confidence is EstimateConfidence.MEDIUM
    assert any("artefato em disco" not in reason for reason in result.reasons)


def test_estimator_suggests_hybrid_when_gpu_alone_is_too_small() -> None:
    result = ResourceEstimator().estimate(
        qwen3_record(),
        hardware_profile(),
        context_tokens=32_768,
    )

    assert result.kv_cache_bytes == 147_456 * 32_768
    assert result.placement is ResourcePlacement.HYBRID
    assert any("offload" in reason for reason in result.reasons)


def test_estimator_rejects_context_above_declared_model_window() -> None:
    result = ResourceEstimator().estimate(
        qwen3_record(),
        hardware_profile(),
        context_tokens=65_536,
    )

    assert result.placement is ResourcePlacement.DOES_NOT_FIT
    assert result.total_required_bytes is None
    assert "excede" in result.reasons[0]


def test_estimator_does_not_convert_disk_size_into_memory_requirement() -> None:
    result = ResourceEstimator().estimate(
        qwen3_record(
            parameter_count=0 if False else 4_000_000_000,
            kv_bytes_per_token=None,
            quantization=None,
            artifact_size=52 * 1024**3,
        ),
        hardware_profile(),
        context_tokens=4096,
    )

    assert result.weight_bytes is None
    assert result.total_required_bytes is None
    assert result.placement is ResourcePlacement.UNKNOWN
    assert result.confidence is EstimateConfidence.UNKNOWN
    assert any("tamanho do artefato" in reason for reason in result.reasons)


def test_estimator_marks_missing_kv_metadata_as_partial_not_compatible() -> None:
    result = ResourceEstimator().estimate(
        qwen3_record(kv_bytes_per_token=None),
        hardware_profile(),
        context_tokens=4096,
    )

    assert result.weight_bytes is not None
    assert result.kv_cache_bytes is None
    assert result.total_required_bytes is None
    assert result.placement is ResourcePlacement.UNKNOWN
    assert result.confidence is EstimateConfidence.PARTIAL


def test_estimator_uses_total_parameters_for_moe_weight_memory() -> None:
    record = ModelRecord(
        record_id="ollama:qwen3-coder-next:q4_k_m",
        display_name="Qwen3-Coder-Next 80B",
        family="Qwen3-Coder-Next",
        category="coding",
        parameter_count=80_000_000_000,
        active_parameter_count=3_000_000_000,
        context_window=262_144,
        kv_cache_bytes_per_token=147_456,
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference="qwen3-coder-next:q4_K_M",
                installed=True,
                quantization="Q4_K_M",
            ),
        ),
    )

    result = ResourceEstimator().estimate(
        record,
        hardware_profile(),
        context_tokens=4096,
    )

    assert result.weight_bytes is not None
    assert result.weight_bytes > 40 * 1024**3
    assert result.placement is ResourcePlacement.DOES_NOT_FIT
