from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor
from knowledge.library import KnowledgeLibrary
from knowledge.models import DocumentPage, LoadedDocument
from knowledge.semantic_pages import SemanticPageIndexer


def test_semantic_page_indexer_builds_compact_extractive_pages_and_provenance() -> None:
    document = LoadedDocument(
        source_uri="file:///tmp/thermal.md",
        title="Adaptações ao frio",
        sha256="a" * 64,
        media_type="text/markdown",
        size_bytes=400,
        pages=(
            DocumentPage(
                "# Animais polares\n\n"
                "Animais polares apresentam adaptações ao frio. A gordura atua como "
                "isolamento térmico e reduz a perda de calor. A pelagem também protege "
                "o corpo em ambientes de baixa temperatura.",
                page_number=1,
            ),
            DocumentPage(
                "A hibernação reduz o gasto energético em determinadas espécies.",
                page_number=2,
            ),
        ),
    )
    indexer = SemanticPageIndexer()
    records = indexer.build(document, [])

    assert len(records) == 2
    first = records[0]
    assert 1 <= len(first.summary.split()) <= 50
    assert first.summary_method == "extractive_frequency_v1"
    assert first.page_number == 1
    assert first.source_uri == document.source_uri
    assert first.source_sha256 == document.sha256
    assert first.content_sha256 != document.sha256
    assert first.keywords
    assert first.concepts
    assert first.entities == ()
    assert first.entity_method == "not_configured"
    assert first.metadata["page_offset_unit"] == "unicode_codepoints"


def test_semantic_page_indexer_preserves_markdown_sections_from_chunks(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text(
        "# Instalação\n\nConfigure o serviço local com segurança e valide o estado.\n"
        "## Diagnóstico\n\nConsulte os registros do serviço para identificar falhas.\n",
        encoding="utf-8",
    )
    index = SQLiteKnowledgeIndex()
    ingestor = DocumentIngestor(index)
    result = ingestor.ingest(source)

    pages = index.list_semantic_pages(result.document_id)

    assert len(pages) == 1
    assert ("Instalação",) in pages[0].section_paths
    assert ("Instalação", "Diagnóstico") in pages[0].section_paths
    assert all(start >= 0 and end <= pages[0].content_char_count
               for start, end in pages[0].summary_spans)
    index.close()


def test_entity_extractor_is_pluggable_and_method_is_recorded() -> None:
    class FakeEntityExtractor:
        method_id = "test_entities_v1"

        def extract_entities(self, text: str) -> list[str]:
            return ["Python", "SQLite", "Python"]

    document = LoadedDocument(
        source_uri="file:///tmp/entities.txt",
        title="Entidades",
        sha256="b" * 64,
        media_type="text/plain",
        size_bytes=42,
        pages=(DocumentPage("Python usa SQLite para armazenar dados locais."),),
    )
    pages = SemanticPageIndexer(entity_extractor=FakeEntityExtractor()).build(
        document, []
    )

    assert pages[0].entities == ("Python", "SQLite")
    assert pages[0].entity_method == "test_entities_v1"


def test_blank_pages_are_not_added_to_semantic_catalog() -> None:
    document = LoadedDocument(
        source_uri="file:///tmp/blank.txt",
        title="Vazio",
        sha256="c" * 64,
        media_type="text/plain",
        size_bytes=1,
        pages=(DocumentPage("   "), DocumentPage("Conteúdo da página.")),
    )

    pages = SemanticPageIndexer().build(document, [])

    assert len(pages) == 1
    assert pages[0].page_index == 1


def test_index_persists_and_searches_semantic_pages(tmp_path: Path) -> None:
    source = tmp_path / "animals.md"
    source.write_text(
        "# Animais\n\nUrsos polares vivem em ambientes árticos. "
        "A pelagem e a gordura ajudam no isolamento térmico.\n",
        encoding="utf-8",
    )
    database = tmp_path / "knowledge.sqlite3"
    with SQLiteKnowledgeIndex(database) as index:
        result = DocumentIngestor(index).ingest(source)
        hits = index.search_semantic_pages("isolamento térmico urso polar")

        assert hits
        assert hits[0].page.document_id == result.document_id
        assert hits[0].page.source_sha256 == result.source_sha256
        assert hits[0].page.title == "animals.md"
        assert index.get_semantic_page(hits[0].page.page_id) == hits[0].page

    with SQLiteKnowledgeIndex(database) as reopened:
        pages = reopened.list_semantic_pages(result.document_id)
        assert len(pages) == 1
        assert pages[0].page_id == hits[0].page.page_id


def test_semantic_page_search_can_filter_documents_and_reject_bad_limits() -> None:
    index = SQLiteKnowledgeIndex()
    first = LoadedDocument(
        source_uri="file:///tmp/first.txt",
        title="Primeiro",
        sha256="d" * 64,
        media_type="text/plain",
        size_bytes=40,
        pages=(DocumentPage("Programação Python e estruturas de dados."),),
    )
    second = LoadedDocument(
        source_uri="file:///tmp/second.txt",
        title="Segundo",
        sha256="e" * 64,
        media_type="text/plain",
        size_bytes=40,
        pages=(DocumentPage("Biologia animal e ambientes polares."),),
    )
    for document in (first, second):
        from knowledge.chunking import DocumentChunker

        chunks = DocumentChunker().chunk(document)
        records = SemanticPageIndexer().build(document, chunks)
        index.add_document(document, chunks, page_records=records)

    assert all(
        hit.page.document_id == second.document_id
        for hit in index.search_semantic_pages("biologia", document_ids={second.document_id})
    )
    assert index.search_semantic_pages("biologia", document_ids=set()) == []
    with pytest.raises(ValueError, match="limit"):
        index.search_semantic_pages("biologia", limit=0)
    index.close()


def test_reingestion_replaces_semantic_page_version_without_stale_fts() -> None:
    from knowledge.chunking import DocumentChunker

    index = SQLiteKnowledgeIndex()
    indexer = SemanticPageIndexer()
    chunker = DocumentChunker()
    first = LoadedDocument(
        source_uri="file:///tmp/revision.txt",
        title="Revisão",
        sha256="f" * 64,
        media_type="text/plain",
        size_bytes=42,
        pages=(DocumentPage("A versão antiga descreve astronomia e planetas."),),
    )
    first_chunks = chunker.chunk(first)
    index.add_document(first, first_chunks, page_records=indexer.build(first, first_chunks))

    second = LoadedDocument(
        source_uri=first.source_uri,
        title=first.title,
        sha256="0" * 64,
        media_type=first.media_type,
        size_bytes=40,
        pages=(DocumentPage("A versão nova descreve botânica e plantas."),),
    )
    second_chunks = chunker.chunk(second)
    index.add_document(second, second_chunks, page_records=indexer.build(second, second_chunks))

    assert index.search_semantic_pages("astronomia planetas") == []
    assert index.search_semantic_pages("botânica plantas")
    assert len(index.list_semantic_pages(second.document_id)) == 1
    index.close()


def test_delete_document_removes_semantic_pages_and_fts_candidates() -> None:
    from knowledge.chunking import DocumentChunker

    index = SQLiteKnowledgeIndex()
    document = LoadedDocument(
        source_uri="file:///tmp/delete.txt",
        title="Excluir",
        sha256="1" * 64,
        media_type="text/plain",
        size_bytes=40,
        pages=(DocumentPage("Memória semântica e recuperação hierárquica."),),
    )
    chunks = DocumentChunker().chunk(document)
    pages = SemanticPageIndexer().build(document, chunks)
    index.add_document(document, chunks, page_records=pages)

    assert index.delete_document(document.document_id)
    assert index.list_semantic_pages(document.document_id) == []
    assert index.search_semantic_pages("memória recuperação") == []
    index.close()


def test_library_ingestion_creates_searchable_semantic_catalog(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text(
        "# Python\n\nPython organiza módulos e bibliotecas para projetos locais. "
        "Ambientes virtuais isolam dependências e versões.\n",
        encoding="utf-8",
    )
    with KnowledgeLibrary(tmp_path / "library") as library:
        result = library.ingest_files([source])
        pages = library.list_semantic_pages()
        hits = library.search_semantic_pages("ambientes virtuais dependências")

        assert result["indexed"] == 1
        assert result["items"][0]["semantic_page_count"] == 1
        assert len(pages) == 1
        assert hits
        assert hits[0].page.page_id == pages[0].page_id
        document_id = pages[0].document_id
        assert library.delete_documents([document_id])["deleted"] == 1
        assert library.list_semantic_pages() == []


def test_semantic_catalog_survives_embedding_provider_failure(tmp_path: Path) -> None:
    source = tmp_path / "local.txt"
    source.write_text(
        "O índice semântico organiza conceitos e páginas para recuperação local.",
        encoding="utf-8",
    )

    class FailingProvider:
        def __init__(self, model_name: str, **_: object) -> None:
            pass

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("Ollama offline")

        def close(self) -> None:
            pass

    with KnowledgeLibrary(
        tmp_path / "data",
        embedding_model="embedding-fake",
        embedding_provider_factory=FailingProvider,
    ) as library:
        result = library.ingest_files([source])
        pages = library.list_semantic_pages()

    assert result["indexed"] == 1
    assert result["items"][0]["status"] == "partial"
    assert len(pages) == 1
