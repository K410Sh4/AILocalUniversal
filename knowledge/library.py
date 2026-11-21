"""Biblioteca documental local persistente do AILocal Universal."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from knowledge.chunking import DocumentChunker
from knowledge.context import ContextComposer
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor
from knowledge.loaders import LoaderRegistry
from knowledge.models import ContextBundle, SemanticPageHit, SemanticPageRecord
from knowledge.retrieval import HybridRetriever
from knowledge.semantic_pages import SemanticPageIndexer
from knowledge.vectors import (
    OllamaEmbeddingProvider,
    SQLiteVectorSearchBackend,
    SQLiteVectorStore,
)


def default_knowledge_directory() -> Path:
    """Retorna o diretório XDG privado usado pelos índices de conhecimento."""
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ailocal-universal" / "knowledge"


class KnowledgeLibrary:
    """Gerencia ingestão, indexação, busca e remoção sem copiar arquivos originais."""

    def __init__(
        self,
        data_directory: str | Path | None = None,
        *,
        ollama_url: str = "http://127.0.0.1:11434",
        embedding_model: str | None = None,
        embedding_provider_factory: Callable[..., Any] = OllamaEmbeddingProvider,
    ) -> None:
        self.data_directory = (
            Path(data_directory).expanduser()
            if data_directory is not None
            else default_knowledge_directory()
        )
        if (
            self.data_directory.name == "knowledge"
            and self.data_directory.parent.name == "ailocal-universal"
        ):
            self.data_directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.data_directory.parent, 0o700)
        self.data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data_directory, 0o700)

        self.index_path = self.data_directory / "knowledge.sqlite3"
        self.vector_path = self.data_directory / "vectors.sqlite3"
        self.embedding_model = embedding_model.strip() if embedding_model else None
        self.ollama_url = ollama_url.rstrip("/")
        self._provider: Any | None = None
        self._embedding_provider_factory = embedding_provider_factory
        self._closed = False

        self.index = SQLiteKnowledgeIndex(self.index_path)
        try:
            self.vector_store = SQLiteVectorStore(self.vector_path)
        except Exception:
            self.index.close()
            raise

        self.loaders = LoaderRegistry()
        self.chunker = DocumentChunker()
        self.page_indexer = SemanticPageIndexer()
        self.ingestor = DocumentIngestor(
            self.index,
            loaders=self.loaders,
            chunker=self.chunker,
            page_indexer=self.page_indexer,
        )
        self.composer = ContextComposer()
        self.last_search_warning: str | None = None

    def _embedding_provider(self) -> OllamaEmbeddingProvider:
        if not self.embedding_model:
            raise ValueError("Selecione um modelo de embeddings antes de indexar vetores.")
        if self._provider is None:
            self._provider = self._embedding_provider_factory(
                self.embedding_model,
                base_url=self.ollama_url,
                truncate=False,
            )
        return self._provider

    def list_documents(self) -> list[dict[str, Any]]:
        return self.index.list_documents()

    def ingest_files(self, file_paths: Sequence[str | Path]) -> dict[str, Any]:
        """Indexa arquivos escolhidos pelo usuário; falha vetorial mantém busca lexical."""
        results: list[dict[str, Any]] = []
        for file_path in file_paths:
            path = Path(file_path).expanduser()
            try:
                document = self.loaders.load(path)
                chunks = self.chunker.chunk(document)
                if not chunks:
                    raise ValueError("O documento não produziu trechos indexáveis.")

                # Fichas semânticas e chunks são gravados na mesma transação SQLite.
                page_records = self.page_indexer.build(document, chunks)
                # Primeiro confirma a nova versão lexical; somente então descarta vetores
                # antigos do mesmo documento.
                self.index.add_document(document, chunks, page_records=page_records)
                self.vector_store.delete_document(document.document_id)

                vector_count = 0
                vector_warning = None
                if self.embedding_model:
                    try:
                        vectors = self._embedding_provider().embed(
                            [chunk.content for chunk in chunks]
                        )
                        vector_count = self.vector_store.replace_documents(
                            chunks,
                            vectors,
                            self.embedding_model,
                        )
                    except Exception as exc:
                        # O índice lexical continua disponível e o resultado informa
                        # explicitamente que a indexação semântica não foi concluída.
                        vector_warning = str(exc)

                results.append(
                    {
                        "source": document.source_uri,
                        "title": document.title,
                        "document_id": document.document_id,
                        "sha256": document.sha256,
                        "chunk_count": len(chunks),
                        "semantic_page_count": len(page_records),
                        "vector_count": vector_count,
                        "vector_warning": vector_warning,
                        "status": "partial" if vector_warning else "indexed",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "source": str(path),
                        "title": path.name,
                        "chunk_count": 0,
                        "vector_count": 0,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

        return {
            "processed": len(results),
            "indexed": sum(item["status"] in {"indexed", "partial"} for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "vector_indexed": sum(item["vector_count"] for item in results),
            "items": results,
        }

    def list_semantic_pages(
        self,
        document_id: str | None = None,
    ) -> list[SemanticPageRecord]:
        """Lista fichas compactas com hash, página e referência à origem."""
        return self.index.list_semantic_pages(document_id)

    def search_semantic_pages(
        self,
        query: str,
        *,
        limit: int = 10,
        document_ids: set[str] | None = None,
    ) -> list[SemanticPageHit]:
        """Localiza páginas pelo catálogo FTS sem substituir a busca híbrida de chunks."""
        return self.index.search_semantic_pages(
            query,
            limit=limit,
            document_ids=document_ids,
        )

    def reindex_vectors(self) -> dict[str, Any]:
        """Gera novamente embeddings para todos os documentos já extraídos."""
        if not self.embedding_model:
            raise ValueError("Selecione um modelo de embeddings antes de reindexar.")
        provider = self._embedding_provider()
        indexed_documents = 0
        vector_count = 0
        failures: list[dict[str, str]] = []

        for document in self.index.list_documents():
            document_id = str(document["document_id"])
            chunks = self.index.list_chunks(document_id)
            if not chunks:
                continue
            try:
                vectors = provider.embed([chunk.content for chunk in chunks])
                count = self.vector_store.replace_documents(
                    chunks,
                    vectors,
                    self.embedding_model,
                )
                indexed_documents += 1
                vector_count += count
            except Exception as exc:
                failures.append(
                    {
                        "document_id": document_id,
                        "title": str(document["title"]),
                        "error": str(exc),
                    }
                )

        return {
            "indexed_documents": indexed_documents,
            "vector_count": vector_count,
            "failed_documents": len(failures),
            "failures": failures,
            "embedding_model": self.embedding_model,
        }

    def delete_documents(self, document_ids: Sequence[str]) -> dict[str, int]:
        deleted = 0
        missing = 0
        for document_id in dict.fromkeys(document_ids):
            # Vetores são removidos primeiro para que nenhuma entrada órfã sobreviva
            # à exclusão lexical. As operações usam bancos separados e não são uma
            # transação distribuída.
            self.vector_store.delete_document(document_id)
            if self.index.delete_document(document_id):
                deleted += 1
            else:
                missing += 1
        return {"deleted": deleted, "missing": missing}

    def search(
        self,
        query: str,
        *,
        max_chars: int = 6000,
        limit: int = 8,
    ) -> ContextBundle:
        if not query.strip():
            return self.composer.compose([], max_chars=max_chars)

        vector_backend = None
        if (
            self.embedding_model
            and self.vector_store.count(self.embedding_model) > 0
        ):
            vector_backend = SQLiteVectorSearchBackend(
                self._embedding_provider(),
                self.vector_store,
                self.index,
            )
        self.last_search_warning = None
        retriever = HybridRetriever(
            self.index,
            vector_backend=vector_backend,
        )
        try:
            hits = retriever.search(query, limit=limit)
        except Exception as exc:
            if vector_backend is None:
                raise
            # Mantém a biblioteca consultável mesmo quando o serviço de embeddings
            # está indisponível; a interface recebe um aviso explícito.
            self.last_search_warning = (
                "Busca vetorial indisponível; exibindo apenas resultados lexicais: "
                + str(exc)
            )
            hits = HybridRetriever(self.index).search(query, limit=limit)
        return self.composer.compose(hits, max_chars=max_chars)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._provider is not None:
            self._provider.close()
            self._provider = None
        self.vector_store.close()
        self.index.close()

    def __enter__(self) -> KnowledgeLibrary:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
