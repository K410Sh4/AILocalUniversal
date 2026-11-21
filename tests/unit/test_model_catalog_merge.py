from __future__ import annotations

from types import SimpleNamespace

from app.main_window import MainWindow
from model_hub.catalog import CatalogDocument, CatalogEntry, CatalogVariant
from model_hub.contracts import ModelArtifact, ModelRecord
from model_hub.registry import ModelRegistry


def test_catalog_merge_preserves_runtime_discovered_model_metadata(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry.json")
    registry.upsert(
        ModelRecord(
            record_id="ollama:qwen3:4b",
            display_name="Qwen3 4B",
            family="qwen3",
            category="general",
            capabilities=("chat",),
            architecture="qwen3",
            parameter_count=4_000_000_000,
            context_window=32_768,
            kv_cache_bytes_per_token=147_456,
            artifacts=(
                ModelArtifact(
                    runtime="ollama",
                    reference="qwen3:4b",
                    installed=True,
                    size_bytes=2_600_000_000,
                    digest="sha256:runtime-digest",
                    quantization="Q4_K_M",
                ),
            ),
        )
    )
    entry = CatalogEntry(
        record_id="qwen3",
        display_name="Qwen3",
        family="qwen3",
        summary="Modelo de linguagem.",
        publisher="Alibaba",
        categories=("general",),
        capabilities=("chat",),
        modalities=("text",),
        source_url="https://ollama.com/library/qwen3",
        variants=(
            CatalogVariant(
                reference="qwen3:4b",
                size_bytes=2_500_000_000,
            ),
        ),
    )
    document = CatalogDocument(
        catalog_version="test",
        updated_at="2026-11-21",
        entries=(entry,),
        source="test",
    )

    MainWindow._merge_catalog_metadata(
        SimpleNamespace(model_hub_registry=registry),
        document,
        {"qwen3:4b"},
    )

    merged = registry.get("ollama:qwen3:4b")
    assert merged is not None
    assert merged.architecture == "qwen3"
    assert merged.parameter_count == 4_000_000_000
    assert merged.context_window == 32_768
    assert merged.kv_cache_bytes_per_token == 147_456
    artifact = merged.artifacts[0]
    assert artifact.installed is True
    assert artifact.size_bytes == 2_600_000_000
    assert artifact.digest == "sha256:runtime-digest"
    assert artifact.quantization == "Q4_K_M"
