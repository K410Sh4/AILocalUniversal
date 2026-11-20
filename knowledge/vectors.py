"""Embeddings locais Ollama e armazenamento vetorial SQLite."""

from __future__ import annotations

import math
import os
import sqlite3
import struct
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from knowledge.errors import EmbeddingError, KnowledgeIndexError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentChunk, SearchHit


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """Correspondência vetorial antes de recuperar o chunk com proveniência."""

    chunk_id: str
    document_id: str
    source_sha256: str
    score: float


class OllamaEmbeddingProvider:
    """Gera embeddings em um modelo explicitamente configurado no Ollama."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 60.0,
        batch_size: int = 16,
        dimensions: int | None = None,
        truncate: bool = False,
        max_input_chars: int = 100_000,
        keep_alive: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name não pode estar vazio.")
        if timeout <= 0 or batch_size < 1 or max_input_chars < 1:
            raise ValueError("Timeout, batch_size e max_input_chars devem ser positivos.")
        if dimensions is not None and dimensions < 1:
            raise ValueError("dimensions deve ser positivo.")
        self.model_name = model_name.strip()
        self.batch_size = batch_size
        self.dimensions = dimensions
        self.truncate = truncate
        self.max_input_chars = max_input_chars
        self.keep_alive = keep_alive
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
        )

    @staticmethod
    def _validate_vector(value: object) -> list[float]:
        if not isinstance(value, (list, tuple)) or not value:
            raise EmbeddingError("Ollama retornou um vetor vazio ou inválido.")
        vector: list[float] = []
        for component in value:
            if isinstance(component, bool) or not isinstance(component, (int, float)):
                raise EmbeddingError("Ollama retornou componentes não numéricos.")
            try:
                number = float(component)
            except (ValueError, OverflowError) as exc:
                raise EmbeddingError("Ollama retornou um componente inválido.") from exc
            if not math.isfinite(number):
                raise EmbeddingError("Ollama retornou um componente não finito.")
            vector.append(number)
        try:
            norm_squared = math.fsum(item * item for item in vector)
        except OverflowError as exc:
            raise EmbeddingError("Ollama retornou um vetor fora do intervalo numérico.") from exc
        if not math.isfinite(norm_squared) or norm_squared <= 0:
            raise EmbeddingError("Ollama retornou um vetor de norma zero ou não finita.")
        return vector

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError("Todos os textos para embedding devem ser strings não vazias.")
        if any(len(item) > self.max_input_chars for item in items):
            raise EmbeddingError("Uma entrada excede max_input_chars.")

        results: list[list[float]] = []
        expected_dimensions = self.dimensions
        for start in range(0, len(items), self.batch_size):
            batch = items[start : start + self.batch_size]
            payload: dict[str, object] = {
                "model": self.model_name,
                "input": batch,
                "truncate": self.truncate,
            }
            if self.dimensions is not None:
                payload["dimensions"] = self.dimensions
            if self.keep_alive is not None:
                payload["keep_alive"] = self.keep_alive

            try:
                response = self._client.post("/api/embed", json=payload)
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise EmbeddingError(
                    "Não foi possível obter embeddings do endpoint Ollama /api/embed."
                ) from exc

            vectors = data.get("embeddings") if isinstance(data, dict) else None
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise EmbeddingError(
                    "A quantidade de embeddings retornada não corresponde às entradas."
                )
            for raw_vector in vectors:
                vector = self._validate_vector(raw_vector)
                if expected_dimensions is None:
                    expected_dimensions = len(vector)
                if len(vector) != expected_dimensions:
                    raise EmbeddingError(
                        "Ollama retornou dimensões inconsistentes entre embeddings."
                    )
                results.append(vector)

        return results

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OllamaEmbeddingProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SQLiteVectorStore:
    """Armazena vetores float32 normalizados e busca por similaridade cosseno."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        if str(database_path) == ":memory:":
            self.database_path = ":memory:"
        else:
            resolved = Path(database_path).expanduser()
            resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.database_path = str(resolved)
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_embeddings (
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    vector_blob BLOB NOT NULL,
                    PRIMARY KEY (chunk_id, model_name)
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_document_model
                ON vector_embeddings(document_id, model_name)
                """
            )
            self._connection.commit()
            if self.database_path != ":memory:":
                os.chmod(self.database_path, 0o600)
        except (sqlite3.Error, OSError) as exc:
            raise KnowledgeIndexError(
                "Não foi possível inicializar o armazenamento vetorial SQLite local."
            ) from exc

    @staticmethod
    def _normalize(vector: Sequence[float]) -> tuple[float, ...]:
        if not vector:
            raise EmbeddingError("Vetor vazio.")
        try:
            values = tuple(float(value) for value in vector)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EmbeddingError("Vetor contém componentes inválidos.") from exc
        if not all(math.isfinite(value) for value in values):
            raise EmbeddingError("Vetor contém valores não finitos.")
        try:
            norm = math.sqrt(math.fsum(value * value for value in values))
        except OverflowError as exc:
            raise EmbeddingError("Vetor excede o intervalo numérico suportado.") from exc
        if not math.isfinite(norm) or norm <= 0:
            raise EmbeddingError("Vetor possui norma zero ou não finita.")
        normalized = tuple(value / norm for value in values)
        try:
            packed = SQLiteVectorStore._encode(normalized)
        except (OverflowError, struct.error) as exc:
            raise EmbeddingError("Vetor excede o intervalo suportado por float32.") from exc
        if len(packed) != len(normalized) * 4:
            raise EmbeddingError("Não foi possível codificar o vetor.")
        return normalized

    @staticmethod
    def _encode(vector: Sequence[float]) -> bytes:
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _decode(blob: bytes, dimensions: int) -> tuple[float, ...]:
        expected_bytes = dimensions * 4
        if len(blob) != expected_bytes:
            raise EmbeddingError("Registro vetorial corrompido: tamanho incompatível.")
        try:
            values = struct.unpack(f"<{dimensions}f", blob)
        except struct.error as exc:
            raise EmbeddingError("Registro vetorial corrompido.") from exc
        if not all(math.isfinite(value) for value in values):
            raise EmbeddingError("Registro vetorial contém valores não finitos.")
        return values

    def upsert_many(
        self,
        chunks: Sequence[DocumentChunk],
        vectors: Sequence[Sequence[float]],
        model_name: str,
    ) -> int:
        """Insere/substitui somente os chunks informados; útil para indexação em lotes."""
        if not model_name.strip():
            raise ValueError("model_name não pode estar vazio.")
        if len(chunks) != len(vectors):
            raise ValueError("Cada chunk deve possuir exatamente um vetor.")
        if not chunks:
            return 0

        normalized = [self._normalize(vector) for vector in vectors]
        dimensions = len(normalized[0])
        if any(len(vector) != dimensions for vector in normalized):
            raise EmbeddingError("Todos os vetores de um lote devem ter a mesma dimensão.")
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("O lote contém chunk_id duplicado.")

        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for chunk, vector in zip(chunks, normalized, strict=True):
                    self._connection.execute(
                        """
                        INSERT INTO vector_embeddings (
                            chunk_id, document_id, source_sha256,
                            model_name, dimensions, vector_blob
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(chunk_id, model_name) DO UPDATE SET
                            document_id = excluded.document_id,
                            source_sha256 = excluded.source_sha256,
                            dimensions = excluded.dimensions,
                            vector_blob = excluded.vector_blob
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source_sha256,
                            model_name,
                            dimensions,
                            self._encode(vector),
                        ),
                    )
                self._connection.commit()
            except (sqlite3.Error, struct.error) as exc:
                self._connection.rollback()
                raise KnowledgeIndexError(
                    "Não foi possível gravar embeddings atomicamente."
                ) from exc
        return len(chunks)

    def replace_documents(
        self,
        chunks: Sequence[DocumentChunk],
        vectors: Sequence[Sequence[float]],
        model_name: str,
    ) -> int:
        """Substitui todos os vetores dos documentos incluídos, removendo chunks antigos."""
        if not model_name.strip():
            raise ValueError("model_name não pode estar vazio.")
        if len(chunks) != len(vectors):
            raise ValueError("Cada chunk deve possuir exatamente um vetor.")
        if not chunks:
            return 0
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("O lote contém chunk_id duplicado.")
        document_ids = sorted({chunk.document_id for chunk in chunks})
        normalized = [self._normalize(vector) for vector in vectors]
        dimensions = len(normalized[0])
        if any(len(vector) != dimensions for vector in normalized):
            raise EmbeddingError("Todos os vetores de um lote devem ter a mesma dimensão.")
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("O lote contém chunk_id duplicado.")

        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for document_id in document_ids:
                    self._connection.execute(
                        """
                        DELETE FROM vector_embeddings
                        WHERE document_id = ? AND model_name = ?
                        """,
                        (document_id, model_name),
                    )
                for chunk, vector in zip(chunks, normalized, strict=True):
                    self._connection.execute(
                        """
                        INSERT INTO vector_embeddings (
                            chunk_id, document_id, source_sha256,
                            model_name, dimensions, vector_blob
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source_sha256,
                            model_name,
                            dimensions,
                            self._encode(vector),
                        ),
                    )
                self._connection.commit()
            except (sqlite3.Error, struct.error) as exc:
                self._connection.rollback()
                raise KnowledgeIndexError(
                    "Não foi possível substituir embeddings atomicamente."
                ) from exc
        return len(chunks)

    def delete_document(self, document_id: str, model_name: str | None = None) -> int:
        with self._lock:
            try:
                if model_name is None:
                    cursor = self._connection.execute(
                        "DELETE FROM vector_embeddings WHERE document_id = ?",
                        (document_id,),
                    )
                else:
                    cursor = self._connection.execute(
                        """
                        DELETE FROM vector_embeddings
                        WHERE document_id = ? AND model_name = ?
                        """,
                        (document_id, model_name),
                    )
                self._connection.commit()
                return max(0, cursor.rowcount)
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise KnowledgeIndexError(
                    "Não foi possível remover embeddings do documento."
                ) from exc

    def search(
        self,
        query_vector: Sequence[float],
        model_name: str,
        limit: int = 10,
        document_ids: set[str] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            raise ValueError("limit deve ser positivo.")
        query = self._normalize(query_vector)
        if document_ids is not None and not document_ids:
            return []

        sql = """
            SELECT chunk_id, document_id, source_sha256, dimensions, vector_blob
            FROM vector_embeddings
            WHERE model_name = ?
        """
        parameters: list[object] = [model_name]
        if document_ids is not None:
            ordered_ids = sorted(document_ids)
            placeholders = ",".join("?" for _ in ordered_ids)
            sql += f" AND document_id IN ({placeholders})"
            parameters.extend(ordered_ids)

        with self._lock:
            try:
                rows = self._connection.execute(sql, parameters).fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeIndexError("A busca vetorial falhou.") from exc

        matches: list[VectorMatch] = []
        for row in rows:
            dimensions = int(row[3])
            if dimensions != len(query):
                continue
            vector = self._decode(row[4], dimensions)
            score = math.fsum(
                left * right for left, right in zip(query, vector, strict=True)
            )
            matches.append(
                VectorMatch(
                    chunk_id=str(row[0]),
                    document_id=str(row[1]),
                    source_sha256=str(row[2]),
                    score=score,
                )
            )
        matches.sort(key=lambda item: (-item.score, item.chunk_id))
        return matches[:limit]

    def count(self, model_name: str | None = None) -> int:
        with self._lock:
            if model_name is None:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM vector_embeddings"
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM vector_embeddings WHERE model_name = ?",
                    (model_name,),
                ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteVectorStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class LocalVectorIndexer:
    """Gera e grava embeddings para chunks já extraídos."""

    def __init__(self, provider: OllamaEmbeddingProvider, store: SQLiteVectorStore) -> None:
        self.provider = provider
        self.store = store

    def index_chunks(self, chunks: Sequence[DocumentChunk]) -> int:
        if not chunks:
            return 0
        vectors = self.provider.embed([chunk.content for chunk in chunks])
        return self.store.replace_documents(chunks, vectors, self.provider.model_name)


class SQLiteVectorSearchBackend:
    """Adapta o armazenamento vetorial ao contrato SearchHit do HybridRetriever."""

    def __init__(
        self,
        provider: OllamaEmbeddingProvider,
        store: SQLiteVectorStore,
        lexical_index: SQLiteKnowledgeIndex,
    ) -> None:
        self.provider = provider
        self.store = store
        self.lexical_index = lexical_index

    def search(
        self,
        query: str,
        limit: int,
        document_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        if not query.strip():
            return []
        vectors = self.provider.embed([query])
        if len(vectors) != 1:
            raise EmbeddingError("O backend de consulta esperava exatamente um vetor.")
        matches = self.store.search(
            vectors[0],
            model_name=self.provider.model_name,
            limit=limit,
            document_ids=document_ids,
        )
        hits: list[SearchHit] = []
        for rank, match in enumerate(matches, start=1):
            chunk = self.lexical_index.get_chunk(match.chunk_id)
            if (
                chunk is None
                or chunk.document_id != match.document_id
                or chunk.source_sha256 != match.source_sha256
            ):
                continue
            hits.append(
                SearchHit(
                    chunk=chunk,
                    score=match.score,
                    rank=rank,
                    retrieval_sources=("vector",),
                )
            )
        return hits
