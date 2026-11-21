import pytest

from engines.base import EngineCapabilities, ModelInfo
from engines.model_selector import ModelSelectionError
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.hardware import AcceleratorInfo, HardwareProfile
from resources.selector import AdaptiveModelSelector


def _hardware() -> HardwareProfile:
    return HardwareProfile(
        operating_system="Linux",
        architecture="x86_64",
        cpu_model="Test CPU",
        cpu_logical_cores=12,
        ram_total_bytes=16 * 1024**3,
        ram_available_bytes=11 * 1024**3,
        disk_free_bytes=100 * 1024**3,
        accelerators=(
            AcceleratorInfo(
                vendor="AMD",
                name="Radeon Test GPU",
                vram_total_bytes=8 * 1024**3,
                vram_available_bytes=7 * 1024**3,
            ),
        ),
    )


def _record(
    name: str,
    *,
    parameters: int,
    quantization: str,
    kv_bytes_per_token: int,
    category: str = "general",
) -> ModelRecord:
    return ModelRecord(
        record_id=f"ollama:{name.casefold()}",
        display_name=name,
        family=name.split(":", 1)[0],
        category=category,
        parameter_count=parameters,
        context_window=32_768,
        kv_cache_bytes_per_token=kv_bytes_per_token,
        artifacts=(
            ModelArtifact(
                runtime="ollama",
                reference=name,
                installed=True,
                quantization=quantization,
            ),
        ),
    )


def test_selector_avoids_preferred_model_when_estimated_not_to_fit() -> None:
    small = ModelInfo("qwen3:4b")
    large = ModelInfo("qwen3-coder-next:q4_K_M")
    records = {
        "ollama:qwen3:4b": _record(
            "qwen3:4b",
            parameters=4_000_000_000,
            quantization="Q4_K_M",
            kv_bytes_per_token=147_456,
        ),
        "ollama:qwen3-coder-next:q4_k_m": _record(
            "qwen3-coder-next:q4_K_M",
            parameters=80_000_000_000,
            quantization="Q4_K_M",
            kv_bytes_per_token=147_456,
            category="coding",
        ),
    }

    result = AdaptiveModelSelector().select(
        [large, small],
        records,
        _hardware(),
        preferred_model=large.name,
        context_tokens=4096,
    )

    assert result.model.name == small.name
    assert result.strategy == "adaptive"
    assert "cabe" in result.explanation
    assert result.estimate.placement.value == "gpu"


def test_selector_preserves_preference_when_estimate_is_viable() -> None:
    first = ModelInfo("a-model")
    preferred = ModelInfo("z-model")
    records = {
        f"ollama:{name}": _record(
            name,
            parameters=2_000_000_000,
            quantization="Q4_K_M",
            kv_bytes_per_token=32_768,
        )
        for name in ("a-model", "z-model")
    }

    result = AdaptiveModelSelector().select(
        [first, preferred],
        records,
        _hardware(),
        preferred_model=preferred.name,
        context_tokens=4096,
    )

    assert result.model.name == preferred.name
    assert result.strategy == "adaptive"


def test_selector_uses_explicit_fallback_when_metadata_is_missing() -> None:
    models = [ModelInfo("z-model"), ModelInfo("a-model")]

    result = AdaptiveModelSelector().select(
        models,
        {},
        _hardware(),
        preferred_model="z-model",
    )

    assert result.model.name == "z-model"
    assert result.strategy == "metadata_fallback"
    assert "não há metadados suficientes" in result.explanation


def test_selector_fails_when_all_fully_estimated_models_exceed_memory() -> None:
    model = ModelInfo(
        "large-model",
        capabilities=EngineCapabilities(chat=True, verified=True),
    )
    record = _record(
        "large-model",
        parameters=80_000_000_000,
        quantization="Q4_K_M",
        kv_bytes_per_token=147_456,
    )

    with pytest.raises(ModelSelectionError, match="Nenhum modelo de chat cabe"):
        AdaptiveModelSelector().select(
            [model],
            {record.record_id: record},
            _hardware(),
            context_tokens=4096,
        )


def test_selector_ignores_unverified_and_embedding_only_models() -> None:
    models = [
        ModelInfo(
            "embedding-only",
            capabilities=EngineCapabilities(chat=False, embeddings=True),
        ),
        ModelInfo(
            "unknown-chat",
            capabilities=EngineCapabilities(chat=True, verified=False),
        ),
    ]

    with pytest.raises(ModelSelectionError, match="Nenhum modelo de chat verificado"):
        AdaptiveModelSelector().select(models, {}, _hardware())
