from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import httpx
import pytest

from knowledge.errors import EmbeddingError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentChunk, DocumentPage, LoadedDocument
from knowledge.retrieval import HybridRetriever
from knowledge.vectors import (
    LocalVectorIndexer,
    OllamaEmbeddingProvider,
    SQLiteVectorSearchBackend,
    SQLiteVectorStore,
)


def make_document(
    source_uri: str,
    title: str,
    digest: str,
    contents: Sequence[str],
) -> tuple[LoadedDocument, list[DocumentChunk]]:
    joined = "\n\n".join(contents)
    document = LoadedDocument(
        source_uri=source_uri,
        title=title,
        sha256=digest,
        media_type="text/plain",
        size_bytes=len(joined.encode("utf-8")),
        pages=(DocumentPage(joined, page_number=1),),
    )
    chunks: list[DocumentChunk] = []
    offset = 0
    for index, content in enumerate(contents, start=1):
        chunks.append(
            DocumentChunk(
                chunk_id=f"{digest[:8]}-{index}",
                document_id=document.document_id,
                source_uri=document.source_uri,
                title=document.title,
                source_sha256=document.sha256,
                media_type=document.media_type,
                content=content,
                start_offset=offset,
                end_offset=offset + len(content),
                page_number=1,
            )
        )
        offset += len(content) + 2
    return document, chunks


def test_ollama_provider_rejects_dimension_mismatch_between_batches() -> None:
    responses = iter(
        [
            {"embeddings": [[1.0, 0.0]]},
            {"embeddings": [[1.0, 0.0, 0.0]]},
        ]
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=next(responses))
        ),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider(
        "embedding-model",
        batch_size=1,
        client=client,
    )

    with pytest.raises(EmbeddingError, match="dimensões inconsistentes"):
        provider.embed(["primeiro", "segundo"])
    client.close()


def test_ollama_provider_wraps_http_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, json={"error": "model unavailable"})
        ),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider("embedding-model", client=client)

    with pytest.raises(EmbeddingError, match="/api/embed"):
        provider.embed(["consulta"])
    client.close()


class StubProvider:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.model_name = "embedding-test"
        self.mapping = mapping

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.mapping[text] for text in texts]


def test_ollama_provider_batches_requests_and_disables_silent_truncation() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(
            200,
            json={"embeddings": [[1.0, 0.0] for _ in payload["input"]]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider(
        model_name="embedding-model",
        batch_size=2,
        client=client,
    )

    vectors = provider.embed(["um", "dois", "três"])

    assert len(vectors) == 3
    assert [len(request["input"]) for request in requests] == [2, 1]
    assert all(request["model"] == "embedding-model" for request in requests)
    assert all(request["truncate"] is False for request in requests)
    client.close()


def test_ollama_provider_sends_optional_dimensions_and_keep_alive() -> None:
    received: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": [[0.2, 0.8]]})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider(
        "embedding-model",
        dimensions=2,
        keep_alive="5m",
        client=client,
    )

    assert provider.embed(["consulta"]) == [[0.2, 0.8]]
    assert received[0]["dimensions"] == 2
    assert received[0]["keep_alive"] == "5m"
    client.close()


@pytest.mark.parametrize(
    "response",
    [
        {"embeddings": []},
        {"embeddings": [[1.0], [1.0]]},
        {"embeddings": [[float("nan"), 1.0]]},
        {"embeddings": [[0.0, 0.0]]},
        {"embeddings": [["not-a-number"]]},
    ],
)
def test_ollama_provider_rejects_invalid_embedding_responses(
    response: dict[str, object],
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=response)
        ),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider("embedding-model", client=client)

    with pytest.raises(EmbeddingError):
        provider.embed(["texto"])
    client.close()


def test_ollama_provider_rejects_oversized_input_without_truncating() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"embeddings": [[1.0]]})
        ),
        base_url="http://ollama.test/",
    )
    provider = OllamaEmbeddingProvider(
        "embedding-model",
        max_input_chars=5,
        client=client,
    )

    with pytest.raises(EmbeddingError, match="max_input_chars"):
        provider.embed(["texto muito longo"])
    client.close()


def test_vector_store_ranks_by_cosine_similarity_and_filters_documents() -> None:
    store = SQLiteVectorStore()
    _doc_a, chunks_a = make_document(
        "file:///tmp/a.txt", "a.txt", "a" * 64, ["gatos e animais"]
    )
    doc_b, chunks_b = make_document(
        "file:///tmp/b.txt", "b.txt", "b" * 64, ["motores e máquinas"]
    )
    store.upsert_many(chunks_a, [[1.0, 0.0]], "embed-v1")
    store.upsert_many(chunks_b, [[0.0, 1.0]], "embed-v1")

    hits = store.search([2.0, 0.0], "embed-v1", limit=2)
    filtered = store.search(
        [1.0, 0.0],
        "embed-v1",
        document_ids={doc_b.document_id},
    )

    assert hits[0].chunk_id == chunks_a[0].chunk_id
    assert hits[0].score == pytest.approx(1.0)
    assert filtered[0].chunk_id == chunks_b[0].chunk_id
    assert store.count("embed-v1") == 2
    store.close()


def test_vector_store_replaces_stale_document_chunks_atomically() -> None:
    store = SQLiteVectorStore()
    _old_doc, old_chunks = make_document(
        "file:///tmp/source.txt",
        "source.txt",
        "a" * 64,
        ["versão antiga", "trecho removido"],
    )
    store.upsert_many(old_chunks, [[1.0, 0.0], [0.8, 0.2]], "embed-v1")

    new_doc, new_chunks = make_document(
        "file:///tmp/source.txt", "source.txt", "b" * 64, ["versão nova"]
    )
    store.replace_documents(new_chunks, [[0.0, 1.0]], "embed-v1")

    remaining = store.search([0.0, 1.0], "embed-v1", limit=10)
    assert len(remaining) == 1
    assert remaining[0].chunk_id == new_chunks[0].chunk_id
    assert remaining[0].source_sha256 == new_doc.sha256
    assert all(
        hit.chunk_id not in {item.chunk_id for item in old_chunks}
        for hit in remaining
    )
    assert store.count("embed-v1") == 1
    store.close()


def test_vector_store_persists_and_enforces_permissions(tmp_path: Path) -> None:
    database = tmp_path / "vectors.sqlite"
    _document, chunks = make_document(
        "file:///tmp/persist.txt",
        "persist.txt",
        "c" * 64,
        ["persistência vetorial"],
    )

    store = SQLiteVectorStore(database)
    store.upsert_many(chunks, [[1.0, 2.0, 3.0]], "embed-v1")
    store.close()

    assert database.exists()
    assert database.stat().st_mode & 0o777 == 0o600

    reopened = SQLiteVectorStore(database)
    assert reopened.count("embed-v1") == 1
    assert (
        reopened.search([1.0, 2.0, 3.0], "embed-v1")[0].chunk_id
        == chunks[0].chunk_id
    )
    reopened.close()


def test_local_vector_indexer_and_hybrid_retrieval_end_to_end() -> None:
    document, chunks = make_document(
        "file:///tmp/local.txt",
        "local.txt",
        "d" * 64,
        ["gatos dormem perto da janela", "motores aquecem durante o uso"],
    )
    lexical_index = SQLiteKnowledgeIndex()
    lexical_index.add_document(document, chunks)
    store = SQLiteVectorStore()
    provider = StubProvider(
        {
            chunks[0].content: [1.0, 0.0],
            chunks[1].content: [0.0, 1.0],
            "felinos descansando": [0.9, 0.1],
        }
    )

    indexed = LocalVectorIndexer(provider, store).index_chunks(chunks)
    vector_backend = SQLiteVectorSearchBackend(provider, store, lexical_index)
    hits = vector_backend.search("felinos descansando", limit=2)
    hybrid = HybridRetriever(lexical_index, vector_backend=vector_backend).search(
        "felinos descansando",
        limit=2,
    )

    assert indexed == 2
    assert hits[0].chunk.chunk_id == chunks[0].chunk_id
    assert hits[0].retrieval_sources == ("vector",)
    assert hybrid[0].chunk.chunk_id == chunks[0].chunk_id
    assert "vector" in hybrid[0].retrieval_sources
    store.close()
    lexical_index.close()


def test_vector_backend_discards_missing_or_stale_lexical_chunks() -> None:
    store = SQLiteVectorStore()
    index = SQLiteKnowledgeIndex()
    _document, chunks = make_document(
        "file:///tmp/stale.txt", "stale.txt", "e" * 64, ["um trecho indexado"]
    )
    store.upsert_many(chunks, [[1.0, 0.0]], "embed-v1")

    class QueryProvider:
        model_name = "embed-v1"

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    backend = SQLiteVectorSearchBackend(QueryProvider(), store, index)

    assert backend.search("consulta", 5) == []
    store.close()
    index.close()
