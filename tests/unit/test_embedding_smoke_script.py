from __future__ import annotations

from collections.abc import Sequence

import scripts.smoke_test_embeddings as smoke


class FakeEmbeddingProvider:
    def __init__(self, model_name: str, **_: object) -> None:
        self.model_name = model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "água" in text else [0.0, 1.0]
            for text in texts
        ]

    def close(self) -> None:
        pass


def test_smoke_script_uses_synthetic_documents_and_vector_retrieval(
    monkeypatch,
) -> None:
    monkeypatch.setattr(smoke, "OllamaEmbeddingProvider", FakeEmbeddingProvider)

    result = smoke.run_smoke_test("fake-embedding-model")

    assert result["status"] == "passed"
    assert result["embedding_model"] == "fake-embedding-model"
    assert result["indexed_chunks"] == 2
    assert result["vector_results"] == 2
    assert result["hybrid_results"] >= 1
    assert result["storage"] == "temporary_and_removed"
    assert result["documents"] == "synthetic_only"
