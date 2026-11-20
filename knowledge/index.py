"""Índice lexical local baseado em SQLite FTS5."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from knowledge.errors import KnowledgeIndexError
from knowledge.models import DocumentChunk, LoadedDocument, SearchHit

_QUERY_STOPWORDS = {
    "a", "as", "ao", "aos", "aquela", "aquele", "aquilo", "até", "com",
    "como", "da", "das", "de", "dela", "dele", "do", "dos", "e", "é",
    "ela", "ele", "em", "entre", "essa", "esse", "esta", "este", "eu",
    "foi", "há", "isso", "isto", "já", "lhe", "mais", "mas", "me", "mesmo",
    "meu", "minha", "muito", "na", "nas", "no", "nos", "nós", "o", "os",
    "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quais",
    "quando", "quanto", "quantos", "quantas", "que", "quem", "se", "ser",
    "seu", "sua", "são", "sao", "sob", "sobre", "também", "tem", "têm",
    "um", "uma", "umas", "uns", "você", "vocês",
    "the", "an", "and", "are", "at", "be", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "this", "to", "was",
    "what", "when", "where", "which", "who", "why", "with",
}


class SQLiteKnowledgeIndex:
    """Índice persistente local; não envia documentos ou consultas à rede."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().parent.mkdir(
                parents=True, exist_ok=True, mode=0o700
            )
        self._lock = threading.RLock()
        try:
            self._connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize()
        except sqlite3.Error as exc:
            raise KnowledgeIndexError(
                "Não foi possível inicializar o índice SQLite local."
            ) from exc

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                source_uri TEXT NOT NULL,
                title TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(document_id)
                    ON DELETE CASCADE,
                source_uri TEXT NOT NULL,
                title TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                media_type TEXT NOT NULL,
                content TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                page_number INTEGER,
                section_path_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON chunks(document_id);
            """
        )
        try:
            self._connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    content,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
        except sqlite3.OperationalError as exc:
            raise KnowledgeIndexError(
                "SQLite foi compilado sem FTS5; instale uma distribuição SQLite "
                "com suporte a FTS5."
            ) from exc

    def add_document(
        self,
        document: LoadedDocument,
        chunks: list[DocumentChunk],
    ) -> None:
        if not chunks:
            raise ValueError("Não é possível indexar um documento sem chunks.")
        for chunk in chunks:
            if (
                chunk.document_id != document.document_id
                or chunk.source_uri != document.source_uri
                or chunk.source_sha256 != document.sha256
            ):
                raise ValueError("Os chunks não pertencem ao documento informado.")

        metadata = json.dumps(
            document.metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    "DELETE FROM chunk_fts WHERE document_id = ?",
                    (document.document_id,),
                )
                self._connection.execute(
                    "DELETE FROM documents WHERE document_id = ?",
                    (document.document_id,),
                )
                self._connection.execute(
                    """
                    INSERT INTO documents (
                        document_id, source_uri, title, source_sha256,
                        media_type, size_bytes, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document.document_id,
                        document.source_uri,
                        document.title,
                        document.sha256,
                        document.media_type,
                        document.size_bytes,
                        metadata,
                    ),
                )
                for chunk in chunks:
                    self._connection.execute(
                        """
                        INSERT INTO chunks (
                            chunk_id, document_id, source_uri, title, source_sha256,
                            media_type, content, start_offset, end_offset,
                            page_number, section_path_json, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source_uri,
                            chunk.title,
                            chunk.source_sha256,
                            chunk.media_type,
                            chunk.content,
                            chunk.start_offset,
                            chunk.end_offset,
                            chunk.page_number,
                            json.dumps(chunk.section_path, ensure_ascii=False),
                            json.dumps(chunk.metadata, ensure_ascii=False, sort_keys=True),
                        ),
                    )
                    self._connection.execute(
                        """
                        INSERT INTO chunk_fts (chunk_id, document_id, content)
                        VALUES (?, ?, ?)
                        """,
                        (chunk.chunk_id, chunk.document_id, chunk.content),
                    )
                self._connection.commit()
            except (sqlite3.Error, TypeError, ValueError) as exc:
                self._connection.rollback()
                if isinstance(exc, ValueError):
                    raise
                raise KnowledgeIndexError(
                    "A ingestão não pôde ser gravada atomicamente no índice."
                ) from exc

    def delete_document(self, document_id: str) -> bool:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    "DELETE FROM chunk_fts WHERE document_id = ?",
                    (document_id,),
                )
                cursor = self._connection.execute(
                    "DELETE FROM documents WHERE document_id = ?",
                    (document_id,),
                )
                self._connection.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise KnowledgeIndexError(
                    "Não foi possível remover o documento do índice."
                ) from exc

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = [
            term
            for term in re.findall(r"[\w]+", query, flags=re.UNICODE)
            if term.casefold() not in _QUERY_STOPWORDS
        ]
        return " AND ".join(f'"{term}"' for term in terms)

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            source_uri=str(row["source_uri"]),
            title=str(row["title"]),
            source_sha256=str(row["source_sha256"]),
            media_type=str(row["media_type"]),
            content=str(row["content"]),
            start_offset=int(row["start_offset"]),
            end_offset=int(row["end_offset"]),
            page_number=(
                int(row["page_number"]) if row["page_number"] is not None else None
            ),
            section_path=tuple(json.loads(row["section_path_json"])),
            metadata=dict(json.loads(row["metadata_json"])),
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        document_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        if limit < 1:
            raise ValueError("limit deve ser positivo.")
        match_query = self._fts_query(query)
        if not match_query:
            return []
        if document_ids is not None and not document_ids:
            return []

        sql = """
            SELECT chunks.*, bm25(chunk_fts) AS relevance_rank
            FROM chunk_fts
            JOIN chunks ON chunks.chunk_id = chunk_fts.chunk_id
            WHERE chunk_fts MATCH ?
        """
        parameters: list[Any] = [match_query]
        if document_ids is not None:
            ordered_ids = sorted(document_ids)
            placeholders = ",".join("?" for _ in ordered_ids)
            sql += f" AND chunks.document_id IN ({placeholders})"
            parameters.extend(ordered_ids)
        sql += " ORDER BY relevance_rank ASC LIMIT ?"
        parameters.append(limit)

        with self._lock:
            try:
                rows = self._connection.execute(sql, parameters).fetchall()
            except sqlite3.Error as exc:
                raise KnowledgeIndexError("A pesquisa lexical falhou.") from exc

        results: list[SearchHit] = []
        for rank, row in enumerate(rows, start=1):
            relevance = max(0.0, -float(row["relevance_rank"]))
            results.append(
                SearchHit(
                    chunk=self._row_to_chunk(row),
                    score=relevance,
                    rank=rank,
                    retrieval_sources=("lexical",),
                )
            )
        return results

    def get_chunk(self, chunk_id: str) -> DocumentChunk | None:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT * FROM chunks WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise KnowledgeIndexError("Não foi possível consultar o chunk.") from exc
        return self._row_to_chunk(row) if row is not None else None

    def list_documents(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT document_id, source_uri, title, source_sha256,
                       media_type, size_bytes
                FROM documents ORDER BY title COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteKnowledgeIndex:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
