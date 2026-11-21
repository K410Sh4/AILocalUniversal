import os

from engines.base import EngineCapabilities, ModelInfo
from model_hub.contracts import ModelRecord
from model_hub.registry import ModelRegistry


def test_runtime_inventory_is_persisted_without_inventing_metadata(tmp_path) -> None:
    path = tmp_path / "model-hub" / "registry.json"
    registry = ModelRegistry(path)
    records = registry.sync_runtime_inventory(
        "ollama",
        [
            ModelInfo(
                "qwen3:4b",
                size_bytes=2048,
                digest="sha256:one",
                capabilities=EngineCapabilities(chat=True, verified=True),
            ),
            ModelInfo(
                "qwen3-embedding:0.6b",
                size_bytes=1024,
                capabilities=EngineCapabilities(chat=False, embeddings=True),
            ),
        ],
    )

    assert len(records) == 2
    chat = registry.get("ollama:qwen3:4b")
    assert chat is not None
    assert chat.category == "general"
    assert chat.license_name is None
    assert chat.license_verified is False
    assert chat.parameter_count is None
    assert chat.artifacts[0].installed is True

    reloaded = ModelRegistry(path)
    assert len(reloaded.list_records(installed_only=True)) == 2
    if os.name == "posix":
        assert path.stat().st_mode & 0o077 == 0


def test_sync_marks_previous_runtime_models_not_installed(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry.json")
    registry.sync_runtime_inventory(
        "ollama",
        [ModelInfo("first:latest"), ModelInfo("second:latest")],
    )
    registry.sync_runtime_inventory("ollama", [ModelInfo("second:latest")])

    assert registry.get("ollama:first:latest").artifacts[0].installed is False
    assert registry.get("ollama:second:latest").artifacts[0].installed is True
    assert [item.record_id for item in registry.list_records(installed_only=True)] == [
        "ollama:second:latest"
    ]


def test_sync_preserves_user_curated_license_metadata(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry.json")
    curated = ModelRecord(
        record_id="ollama:curated:latest",
        display_name="Curated",
        family="Curated",
        category="coding",
        license_name="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        license_verified=True,
        metadata_source="user_curated",
    )
    registry.upsert(curated)
    registry.sync_runtime_inventory("ollama", [ModelInfo("curated:latest")])

    stored = registry.get("ollama:curated:latest")
    assert stored is not None
    assert stored.license_name == "Apache-2.0"
    assert stored.license_verified is True
    assert stored.category == "coding"
    assert stored.artifacts[0].installed is True


def test_corrupted_registry_is_preserved_and_not_overwritten(tmp_path) -> None:
    path = tmp_path / "registry.json"
    path.write_text("{broken", encoding="utf-8")
    registry = ModelRegistry(path)

    assert registry.load_warning
    registry.sync_runtime_inventory("ollama", [ModelInfo("new:latest")])
    assert path.read_text(encoding="utf-8") == "{broken"
    assert len(registry.list_records(installed_only=True)) == 1

def test_runtime_inventory_persists_architecture_and_quantization_metadata(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry.json")
    registry.sync_runtime_inventory(
        "ollama",
        [
            ModelInfo(
                "qwen3:4b",
                size_bytes=2_600_000_000,
                capabilities=EngineCapabilities(chat=True, verified=True),
                parameter_count=4_000_000_000,
                architecture="qwen3",
                quantization="Q4_K_M",
                context_window=32_768,
                kv_cache_bytes_per_token=147_456,
            )
        ],
    )

    stored = registry.get("ollama:qwen3:4b")
    assert stored is not None
    assert stored.parameter_count == 4_000_000_000
    assert stored.architecture == "qwen3"
    assert stored.context_window == 32_768
    assert stored.kv_cache_bytes_per_token == 147_456
    assert stored.artifacts[0].quantization == "Q4_K_M"

    restored = ModelRegistry(tmp_path / "registry.json").get("ollama:qwen3:4b")
    assert restored is not None
    assert restored.kv_cache_bytes_per_token == 147_456
    assert restored.artifacts[0].quantization == "Q4_K_M"

