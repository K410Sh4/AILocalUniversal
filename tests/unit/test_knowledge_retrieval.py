from __future__ import annotations

import pytest

from knowledge.errors import KnowledgeIndexError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentChunk, DocumentPage, LoadedDocument, SearchHit
from knowledge.retrieval import HybridRetriever


def build_document() -> tuple[LoadedDocument, list[DocumentChunk]]:
    text_one = "O gato dorme perto da janela."
    text_two = "O gato brinca no jardim."
    document = LoadedDocument(
        source_uri="file:///tmp/gatos.txt",
        title="gatos.txt",
        sha256="c" * 64,
        media_type="text/plain",
        size_bytes=100,
        pages=(DocumentPage(text_one + "\n\n" + text_two),),
    )
    chunks = [
        DocumentChunk(
            chunk_id=f"chunk-{index}",
            document_id=document.document_id,
            source_uri=document.source_uri,
            title=document.title,
            source_sha256=document.sha256,
            media_type=document.media_type,
            content=content,
            start_offset=index * 40,
            end_offset=index * 40 + len(content),
        )
        for index, content in enumerate((text_one, text_two), start=1)
    ]
    return document, chunks


class FakeVectorBackend:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def search(self, query: str, limit: int, document_ids: set[str] | None = None):
        hits = self.hits
        if document_ids is not None:
            hits = [hit for hit in hits if hit.chunk.document_id in document_ids]
        return hits[:limit]


class ReverseReranker:
    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        return list(reversed(hits))


class InvalidReranker:
    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        return hits + hits[:1]


def test_lexical_and_vector_rankings_are_fused() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = build_document()
    index.add_document(document, chunks)
    vector = FakeVectorBackend(
        [
            SearchHit(chunks[1], 0.95, 1, ("vector",)),
            SearchHit(chunks[0], 0.80, 2, ("vector",)),
        ]
    )

    hits = HybridRetriever(index, vector_backend=vector).search("gato", limit=2)

    assert {hit.chunk.chunk_id for hit in hits} == {"chunk-1", "chunk-2"}
    merged = next(hit for hit in hits if hit.chunk.chunk_id == "chunk-1")
    assert set(merged.retrieval_sources) == {"lexical", "vector"}
    index.close()


def test_reranker_can_reorder_candidates_without_changing_membership() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = build_document()
    index.add_document(document, chunks)

    hits = HybridRetriever(
        index,
        vector_backend=FakeVectorBackend(
            [SearchHit(chunks[1], 0.9), SearchHit(chunks[0], 0.8)]
        ),
        reranker=ReverseReranker(),
    ).search("gato", limit=2)

    assert hits[0].chunk.chunk_id == "chunk-2"
    assert [hit.rank for hit in hits] == [1, 2]
    index.close()


def test_reranker_cannot_inject_or_duplicate_chunks() -> None:
    index = SQLiteKnowledgeIndex()
    document, chunks = build_document()
    index.add_document(document, chunks)

    with pytest.raises(KnowledgeIndexError, match="adicionar ou duplicar"):
        HybridRetriever(
            index,
            reranker=InvalidReranker(),
        ).search("gato", limit=2)
    index.close()
