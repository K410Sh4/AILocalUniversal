import json

import httpx
import pytest

from model_hub.catalog import (
    CatalogError,
    ModelCatalogClient,
    current_platform,
    parse_catalog,
    validate_model_reference,
)


def test_bundled_catalog_has_valid_categorized_entries() -> None:
    from importlib import resources

    payload = json.loads(
        resources.files("model_hub").joinpath("catalog_default.json").read_text(
            encoding="utf-8"
        )
    )
    document = parse_catalog(payload, source="test")

    assert len(document.entries) >= 8
    assert any("coding" in entry.categories for entry in document.entries)
    assert any("embeddings" in entry.categories for entry in document.entries)
    assert any("ocr" in entry.categories for entry in document.entries)
    assert any("image_generation" in entry.categories for entry in document.entries)


def test_catalog_rejects_duplicate_model_references() -> None:
    payload = {
        "schema_version": 1,
        "catalog_version": "test",
        "updated_at": "2026-11-20",
        "models": [
            {
                "record_id": "one",
                "display_name": "One",
                "family": "One",
                "summary": "Model one",
                "publisher": "Publisher",
                "categories": ["general"],
                "capabilities": ["chat"],
                "modalities": ["text"],
                "source_url": "https://ollama.com/library/one",
                "variants": [{"reference": "one:latest", "installable": True}],
            },
            {
                "record_id": "two",
                "display_name": "Two",
                "family": "Two",
                "summary": "Model two",
                "publisher": "Publisher",
                "categories": ["coding"],
                "capabilities": ["coding"],
                "modalities": ["text"],
                "source_url": "https://ollama.com/library/two",
                "variants": [{"reference": "one:latest", "installable": True}],
            },
        ],
    }

    with pytest.raises(CatalogError, match="referências"):
        parse_catalog(payload, source="test")


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "../private/file",
        "model name",
        "https://example.com/model",
        "model:tag:extra",
        "model//tag",
    ],
)
def test_model_reference_rejects_arbitrary_paths_and_urls(reference: str) -> None:
    with pytest.raises(CatalogError):
        validate_model_reference(reference)


def test_model_reference_accepts_official_ollama_namespaced_refs() -> None:
    assert validate_model_reference("qwen3.5:4b-q4_K_M") == "qwen3.5:4b-q4_K_M"
    assert validate_model_reference("x/z-image-turbo") == "x/z-image-turbo"


@pytest.mark.asyncio
async def test_remote_catalog_uses_remote_document() -> None:
    body = {
        "schema_version": 1,
        "catalog_version": "test.1",
        "updated_at": "2026-11-20",
        "models": [],
    }

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = ModelCatalogClient(
        remote_url="https://catalog.example/catalog.json",
        transport=httpx.MockTransport(handler),
    )
    document = await client.fetch()

    assert document.source == "online"
    assert document.catalog_version == "test.1"


@pytest.mark.asyncio
async def test_remote_failure_falls_back_to_bundled_catalog() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    client = ModelCatalogClient(
        remote_url="https://catalog.example/catalog.json",
        transport=httpx.MockTransport(handler),
    )
    document = await client.fetch()

    assert document.source == "bundled"
    assert document.entries
    assert document.warning is not None


def test_unsupported_platform_variant_is_not_installable_on_linux() -> None:
    payload = {
        "schema_version": 1,
        "catalog_version": "test",
        "updated_at": "2026-11-20",
        "models": [
            {
                "record_id": "phonon",
                "display_name": "Phonon",
                "family": "Phonon",
                "summary": "Speech model.",
                "publisher": "Gradium",
                "categories": ["speech"],
                "capabilities": ["text_to_speech"],
                "modalities": ["text", "audio"],
                "source_url": "https://ollama.com/library/phonon",
                "variants": [
                    {"reference": "phonon:40m-multilingual", "supported_platforms": ["macos"]}
                ],
            }
        ],
    }
    document = parse_catalog(payload, source="test")
    variant = document.entries[0].variants[0]

    assert current_platform() == "linux"
    assert variant.available_on("macos") is True
    assert variant.available_on("linux") is False
