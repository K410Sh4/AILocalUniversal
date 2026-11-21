from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from knowledge.library import KnowledgeLibrary


class FakeEmbeddingProvider:
    def __init__(self, model_name: str, **_: object) -> None:
        self.model_name = model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [1.0, 0.0]
            if "gatos" in text.casefold() or "felinos" in text.casefold()
            else [0.0, 1.0]
            for text in texts
        ]

    def close(self) -> None:
        pass


def test_library_ingests_searches_and_removes_markdown(tmp_path: Path) -> None:
    source = tmp_path / "guia.md"
    source.write_text(
        "# Animais\n\nGatos dormem perto da janela durante a tarde.\n",
        encoding="utf-8",
    )
    data_directory = tmp_path / "private-data"

    with KnowledgeLibrary(data_directory) as library:
        result = library.ingest_files([source])
        documents = library.list_documents()
        bundle = library.search("Quais gatos dormem perto da janela?")

        assert result["indexed"] == 1
        assert documents[0]["title"] == "guia.md"
        assert documents[0]["chunk_count"] >= 1
        assert "Gatos dormem" in bundle.text
        document_id = documents[0]["document_id"]
        assert library.delete_documents([document_id])["deleted"] == 1
        assert library.list_documents() == []

    assert (data_directory / "knowledge.sqlite3").stat().st_mode & 0o777 == 0o600
    assert (data_directory / "vectors.sqlite3").stat().st_mode & 0o777 == 0o600
    assert data_directory.stat().st_mode & 0o777 == 0o700


def test_library_keeps_lexical_index_when_embedding_provider_fails(tmp_path: Path) -> None:
    source = tmp_path / "notas.txt"
    source.write_text("O projeto possui um núcleo cognitivo local.", encoding="utf-8")

    class FailingProvider:
        def __init__(self, model_name: str, **_: object) -> None:
            pass

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            raise RuntimeError("Ollama offline")

        def close(self) -> None:
            pass

    with KnowledgeLibrary(
        tmp_path / "data",
        embedding_model="embedding-model",
        embedding_provider_factory=FailingProvider,
    ) as library:
        result = library.ingest_files([source])
        bundle = library.search("núcleo cognitivo")

    assert result["indexed"] == 1
    assert result["items"][0]["status"] == "partial"
    assert result["items"][0]["vector_warning"] == "Ollama offline"
    assert "núcleo cognitivo" in bundle.text


def test_library_reindexes_existing_chunks_with_a_new_embedding_model(
    tmp_path: Path,
) -> None:
    source = tmp_path / "manual.txt"
    source.write_text("Gatos dormem e cachorros brincam.", encoding="utf-8")
    data_directory = tmp_path / "data"

    with KnowledgeLibrary(data_directory) as lexical_library:
        assert lexical_library.ingest_files([source])["indexed"] == 1

    with KnowledgeLibrary(
        data_directory,
        embedding_model="fake-embedding",
        embedding_provider_factory=FakeEmbeddingProvider,
    ) as vector_library:
        result = vector_library.reindex_vectors()
        bundle = vector_library.search("felinos")

    assert result["indexed_documents"] == 1
    assert result["vector_count"] >= 1
    assert result["failed_documents"] == 0
    assert "Gatos dormem" in bundle.text


def test_library_reports_unsupported_files_without_aborting_batch(tmp_path: Path) -> None:
    supported = tmp_path / "valid.txt"
    supported.write_text("Conteúdo de teste válido.", encoding="utf-8")
    unsupported = tmp_path / "invalid.bin"
    unsupported.write_bytes(b"\x00\x01")

    with KnowledgeLibrary(tmp_path / "data") as library:
        result = library.ingest_files([unsupported, supported])

    assert result["processed"] == 2
    assert result["indexed"] == 1
    assert result["failed"] == 1
    assert result["items"][0]["status"] == "failed"
    assert result["items"][1]["status"] == "indexed"

def test_library_falls_back_to_lexical_search_when_embedding_service_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "manual.txt"
    source.write_text("O projeto possui um núcleo cognitivo local.", encoding="utf-8")

    class FailingQueryProvider:
        model_name = "fake-embedding"

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            raise RuntimeError("Ollama indisponível durante a consulta")

        def close(self) -> None:
            pass

    with KnowledgeLibrary(tmp_path / "data") as library:
        library.ingest_files([source])
        document = library.list_documents()[0]
        chunks = library.index.list_chunks(document["document_id"])
        library.vector_store.upsert_many(chunks, [[1.0, 0.0]], "fake-embedding")
        library.embedding_model = "fake-embedding"
        library._provider = FailingQueryProvider()

        bundle = library.search("núcleo cognitivo")

    assert "núcleo cognitivo" in bundle.text
    assert "Busca vetorial indisponível" in library.last_search_warning


def test_library_uses_nesa_page_candidates_to_scope_progressive_chunk_search(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "architecture.md"
    secondary = tmp_path / "notes.txt"
    primary.write_text(
        "# Cognitive Runtime\n\nA cognitive runtime coordinates capabilities and resources.\n",
        encoding="utf-8",
    )
    secondary.write_text(
        "The local project tracks unrelated artwork and colors.\n",
        encoding="utf-8",
    )

    with KnowledgeLibrary(tmp_path / "data") as library:
        result = library.ingest_files([primary, secondary])
        assert result["indexed"] == 2

        bundle = library.search("cognitive runtime capabilities", limit=8)

        assert bundle.evidence
        assert any("cognitive runtime" in item.content.casefold() for item in bundle.evidence)
        assert library.last_semantic_page_hits
        candidate_documents = {
            hit.page.document_id for hit in library.last_semantic_page_hits
        }
        primary_document = next(
            item for item in library.list_documents()
            if item["title"] == "architecture.md"
        )
        assert primary_document["document_id"] in candidate_documents
        assert library.index.list_chunks(primary_document["document_id"])


def test_library_clears_nesa_candidates_for_empty_queries(tmp_path: Path) -> None:
    source = tmp_path / "architecture.md"
    source.write_text(
        "# Runtime\n\nA cognitive runtime coordinates local capabilities.\n",
        encoding="utf-8",
    )
    with KnowledgeLibrary(tmp_path / "data") as library:
        library.ingest_files([source])
        library.search("cognitive runtime")
        assert library.last_semantic_page_hits
        empty = library.search(" ")
        assert empty.text == ""
        assert library.last_semantic_page_hits == ()
        assert library.last_search_warning is None
