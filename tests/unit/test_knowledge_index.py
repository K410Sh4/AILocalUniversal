from __future__ import annotations

from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentChunk, DocumentPage, LoadedDocument


def make_pair(
    source_uri: str = "file:///tmp/a.txt",
    content: str = "A informação útil está neste documento.",
    digest: str = "a" * 64,
) -> tuple[LoadedDocument, list[DocumentChunk]]:
    document = LoadedDocument(
        source_uri=source_uri,
        title="a.txt",
        sha256=digest,
        media_type="text/plain",
        size_bytes=len(content),
        pages=(DocumentPage(content),),
    )
    chunk = DocumentChunk(
        chunk_id=f"{digest[:8]}-chunk",
        document_id=document.document_id,
        source_uri=source_uri,
        title=document.title,
        source_sha256=digest,
        media_type=document.media_type,
        content=content,
        start_offset=0,
        end_offset=len(content),
    )
    return document, [chunk]


def test_fts_search_returns_local_evidence_and_metadata() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = make_pair()
    index.add_document(document, chunks)

    hits = index.search("informacao util")

    assert len(hits) == 1
    assert hits[0].chunk.chunk_id == chunks[0].chunk_id
    assert hits[0].chunk.source_sha256 == document.sha256
    assert hits[0].retrieval_sources == ("lexical",)
    assert index.get_chunk(chunks[0].chunk_id) == chunks[0]
    index.close()


def test_search_can_filter_by_document_id() -> None:
    index = SQLiteKnowledgeIndex()
    first, first_chunks = make_pair("file:///tmp/first.txt")
    second, second_chunks = make_pair(
        "file:///tmp/second.txt",
        "Informação útil de outro local.",
        "b" * 64,
    )
    index.add_document(first, first_chunks)
    index.add_document(second, second_chunks)

    hits = index.search("informacao", document_ids={second.document_id})

    assert len(hits) == 1
    assert hits[0].chunk.document_id == second.document_id
    assert index.search("informacao", document_ids=set()) == []
    index.close()


def test_reingesting_same_source_replaces_old_version_atomically() -> None:
    index = SQLiteKnowledgeIndex()
    first, first_chunks = make_pair()
    index.add_document(first, first_chunks)

    second, second_chunks = make_pair(
        content="Conteúdo revisado e atualizado.",
        digest="b" * 64,
    )
    index.add_document(second, second_chunks)

    assert index.search("informacao") == []
    assert len(index.search("atualizado")) == 1
    assert len(index.list_documents()) == 1
    assert index.get_chunk(first_chunks[0].chunk_id) is None
    assert index.get_chunk(second_chunks[0].chunk_id) is not None
    index.close()


def test_delete_document_removes_lexical_entries_too() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = make_pair()
    index.add_document(document, chunks)

    assert index.delete_document(document.document_id) is True
    assert index.search("informacao") == []
    assert index.delete_document(document.document_id) is False
    index.close()

def test_search_removes_portuguese_question_stopwords() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = make_pair(
        content="O guia do projeto define quatro fases iniciais de validação."
    )
    index.add_document(document, chunks)

    hits = index.search("Quais são as fases iniciais de validação?")

    assert len(hits) == 1
    assert hits[0].chunk.chunk_id == chunks[0].chunk_id
    index.close()


def test_search_returns_empty_when_query_contains_only_stopwords() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = make_pair()
    index.add_document(document, chunks)

    assert index.search("o que é de e para") == []
    index.close()


def test_query_normalization_preserves_negation_terms() -> None:
    assert SQLiteKnowledgeIndex._fts_query("não usar") == '"não" AND "usar"'
