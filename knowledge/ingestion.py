"""Orquestração explícita de ingestão local."""

from __future__ import annotations

from pathlib import Path

from knowledge.chunking import DocumentChunker
from knowledge.errors import EmptyDocumentError
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.loaders import LoaderRegistry
from knowledge.models import IngestionResult


class DocumentIngestor:
    """Carrega, extrai, divide e indexa somente o arquivo solicitado pelo usuário."""

    def __init__(
        self,
        index: SQLiteKnowledgeIndex,
        loaders: LoaderRegistry | None = None,
        chunker: DocumentChunker | None = None,
    ) -> None:
        self.index = index
        self.loaders = loaders or LoaderRegistry()
        self.chunker = chunker or DocumentChunker()

    def ingest(self, path: str | Path) -> IngestionResult:
        document = self.loaders.load(path)
        chunks = self.chunker.chunk(document)
        if not chunks:
            raise EmptyDocumentError("O documento não produziu trechos indexáveis.")
        self.index.add_document(document, chunks)
        return IngestionResult(
            document_id=document.document_id,
            source_uri=document.source_uri,
            source_sha256=document.sha256,
            chunk_count=len(chunks),
            page_count=len(document.pages),
            media_type=document.media_type,
        )
