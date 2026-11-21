"""Smoke test do endpoint local Ollama /api/embed e da busca vetorial."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from knowledge.chunking import DocumentChunker
from knowledge.errors import EmbeddingError, KnowledgeIndexError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentPage, LoadedDocument
from knowledge.retrieval import HybridRetriever
from knowledge.vectors import (
    LocalVectorIndexer,
    OllamaEmbeddingProvider,
    SQLiteVectorSearchBackend,
    SQLiteVectorStore,
)


def _documents() -> tuple[list[LoadedDocument], str]:
    """Cria documentos sintéticos em memória; nenhum arquivo do usuário é lido."""
    texts = [
        "Teste AILocal Universal: água ferve quando atinge sua temperatura de ebulição.",
        "Teste AILocal Universal: Python é uma linguagem usada para desenvolver software.",
    ]
    documents: list[LoadedDocument] = []
    for index, text in enumerate(texts, start=1):
        documents.append(
            LoadedDocument(
                source_uri=f"memory://ailocal-rag-smoke/document-{index}",
                title=f"smoke-document-{index}",
                sha256=f"{index:064x}",
                media_type="text/plain",
                size_bytes=len(text.encode("utf-8")),
                pages=(DocumentPage(text=text, page_number=1),),
                metadata={"synthetic": True},
            )
        )
    return documents, texts[0]


def run_smoke_test(
    model_name: str,
    *,
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 60.0,
    dimensions: int | None = None,
) -> dict[str, object]:
    """Confere endpoint, dimensão, persistência temporária e busca vetorial."""
    documents, query = _documents()
    chunker = DocumentChunker(max_chars=1200, overlap_chars=0)
    chunks = [
        chunk
        for document in documents
        for chunk in chunker.chunk(document)
    ]
    if len(chunks) != len(documents):
        raise RuntimeError("O smoke test esperava exatamente um chunk por documento.")

    index = SQLiteKnowledgeIndex()
    provider = OllamaEmbeddingProvider(
        model_name=model_name,
        base_url=base_url,
        timeout=timeout,
        batch_size=8,
        dimensions=dimensions,
        truncate=False,
    )

    try:
        for document in documents:
            document_chunks = [
                chunk for chunk in chunks if chunk.document_id == document.document_id
            ]
            index.add_document(document, document_chunks)

        with tempfile.TemporaryDirectory(prefix="ailocal-rag-smoke-") as temporary:
            vector_database = Path(temporary) / "vectors.sqlite"
            with SQLiteVectorStore(vector_database) as store:
                indexed_count = LocalVectorIndexer(provider, store).index_chunks(chunks)
                vector_backend = SQLiteVectorSearchBackend(provider, store, index)
                vector_hits = vector_backend.search(query, limit=2)
                hybrid_hits = HybridRetriever(
                    index,
                    vector_backend=vector_backend,
                ).search(query, limit=2)

                expected_chunk_id = next(
                    chunk.chunk_id
                    for chunk in chunks
                    if chunk.content == query
                )
                if not vector_hits:
                    raise RuntimeError("A busca vetorial não retornou resultados.")
                if vector_hits[0].chunk.chunk_id != expected_chunk_id:
                    raise RuntimeError(
                        "A consulta idêntica não recuperou o documento esperado no topo."
                    )
                if not hybrid_hits:
                    raise RuntimeError("A busca híbrida não retornou resultados.")

                return {
                    "status": "passed",
                    "embedding_model": model_name,
                    "embedding_dimensions": len(provider.embed([query])[0]),
                    "indexed_chunks": indexed_count,
                    "vector_results": len(vector_hits),
                    "hybrid_results": len(hybrid_hits),
                    "top_cosine_similarity": round(vector_hits[0].score, 6),
                    "storage": "temporary_and_removed",
                    "documents": "synthetic_only",
                }
    finally:
        provider.close()
        index.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Testa embeddings Ollama reais e a recuperação vetorial SQLite "
            "usando somente documentos sintéticos temporários."
        )
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Nome do modelo de embeddings instalado no Ollama.",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:11434",
        help="URL do serviço Ollama (padrão: http://127.0.0.1:11434).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout HTTP em segundos (padrão: 60).",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Dimensões desejadas, quando suportadas pelo modelo.",
    )
    args = parser.parse_args()

    try:
        result = run_smoke_test(
            args.model,
            base_url=args.url,
            timeout=args.timeout,
            dimensions=args.dimensions,
        )
    except (EmbeddingError, KnowledgeIndexError, OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
