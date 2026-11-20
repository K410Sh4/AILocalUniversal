import pytest

from engines.base import EngineCapabilities, ModelInfo
from engines.model_selector import ModelSelectionError, choose_model


def test_preferred_model_wins_when_available() -> None:
    models = [ModelInfo("z-model"), ModelInfo("a-model")]
    assert choose_model(models, "z-model").name == "z-model"


def test_automatic_selection_has_stable_fallback() -> None:
    models = [ModelInfo("z-model"), ModelInfo("B-model"), ModelInfo("a-model")]
    assert choose_model(models).name == "a-model"


def test_selector_rejects_no_chat_models() -> None:
    models = [
        ModelInfo(
            "embedding",
            capabilities=EngineCapabilities(chat=False),
        )
    ]
    with pytest.raises(ModelSelectionError):
        choose_model(models)



def test_selector_ignores_embedding_and_unverified_models() -> None:
    models = [
        ModelInfo(
            "qwen3-embedding:0.6b",
            capabilities=EngineCapabilities(chat=False, embeddings=True),
        ),
        ModelInfo(
            "legacy-unknown",
            capabilities=EngineCapabilities(chat=False, verified=False),
        ),
        ModelInfo("qwen3:4b"),
    ]

    assert choose_model(models, "qwen3-embedding:0.6b").name == "qwen3:4b"
