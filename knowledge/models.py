"""Contratos versionáveis da ingestão e recuperação de conhecimento."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from core.cognitive_task import Evidence


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """Unidade textual de origem; page_number é 1-based para PDFs."""

    text: str
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    """Documento extraído, com hash do arquivo original e páginas preservadas."""

    source_uri: str
    title: str
    sha256: str
    media_type: str
    size_bytes: int
    pages: tuple[DocumentPage, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def document_id(self) -> str:
        """ID estável por origem; reingestão substitui a versão anterior da mesma origem."""
        import hashlib

        return hashlib.sha256(self.source_uri.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """Trecho recuperável com proveniência exata no texto extraído."""

    chunk_id: str
    document_id: str
    source_uri: str
    title: str
    source_sha256: str
    media_type: str
    content: str
    start_offset: int
    end_offset: int
    page_number: int | None = None
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Resultado de recuperação; score não é probabilidade de relevância."""

    chunk: DocumentChunk
    score: float
    rank: int = 0
    retrieval_sources: tuple[str, ...] = ("lexical",)


@dataclass(frozen=True, slots=True)
class CitationRecord:
    citation_id: str
    chunk_id: str
    document_id: str
    source_uri: str
    title: str
    locator: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ContextBundle:
    """Contexto limitado em caracteres, com evidências ligadas às fontes."""

    text: str
    evidence: tuple[Evidence, ...]
    citations: tuple[CitationRecord, ...]
    skipped_chunk_ids: tuple[str, ...]
    char_count: int


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: str
    source_uri: str
    source_sha256: str
    chunk_count: int
    page_count: int
    media_type: str


class VectorSearchBackend(Protocol):
    """Contrato substituível para futuro índice vetorial local."""

    def search(
        self,
        query: str,
        limit: int,
        document_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        ...


class Reranker(Protocol):
    """Contrato para reordenar candidatos sem criar novas evidências."""

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        ...
