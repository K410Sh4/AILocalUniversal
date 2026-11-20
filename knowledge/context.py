"""Composição de contexto com citações e orçamento explícito em caracteres."""

from __future__ import annotations

from knowledge.models import CitationRecord, ContextBundle, SearchHit
from core.cognitive_task import Evidence


class ContextComposer:
    """Transforma hits em contexto rastreável sem fingir estimar tokens."""

    @staticmethod
    def _locator(hit: SearchHit) -> str:
        chunk = hit.chunk
        parts: list[str] = []
        if chunk.page_number is not None:
            parts.append(f"página {chunk.page_number}")
        if chunk.section_path:
            parts.append("seção " + " > ".join(chunk.section_path))
        if not parts:
            parts.append(
                f"caracteres {chunk.start_offset}–{chunk.end_offset}"
            )
        return " · ".join(parts)

    def compose(
        self,
        hits: list[SearchHit],
        max_chars: int,
    ) -> ContextBundle:
        if max_chars < 1:
            raise ValueError("max_chars deve ser positivo.")

        blocks: list[str] = []
        evidence_items: list[Evidence] = []
        citations: list[CitationRecord] = []
        skipped: list[str] = []
        seen: set[str] = set()
        used_chars = 0

        for hit in hits:
            chunk = hit.chunk
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)

            citation_id = f"E{len(citations) + 1}"
            locator = self._locator(hit)
            block = (
                f"[{citation_id}] {chunk.title}\n"
                f"Fonte: {chunk.source_uri} · {locator}\n"
                f"{chunk.content}"
            )
            separator = "\n\n" if blocks else ""
            required = len(separator) + len(block)
            if used_chars + required > max_chars:
                skipped.append(chunk.chunk_id)
                continue

            blocks.append(block)
            used_chars += required
            citations.append(
                CitationRecord(
                    citation_id=citation_id,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_uri=chunk.source_uri,
                    title=chunk.title,
                    locator=locator,
                    source_sha256=chunk.source_sha256,
                )
            )
            evidence_items.append(
                Evidence(
                    source=chunk.source_uri,
                    content=chunk.content,
                    locator=locator,
                    metadata={
                        "citation_id": citation_id,
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "source_sha256": chunk.source_sha256,
                        "start_offset": chunk.start_offset,
                        "end_offset": chunk.end_offset,
                        "page_number": chunk.page_number,
                        "section_path": list(chunk.section_path),
                        "title": chunk.title,
                        "retrieval_sources": list(hit.retrieval_sources),
                        "retrieval_score": hit.score,
                    },
                )
            )

        context_text = "\n\n".join(blocks)
        return ContextBundle(
            text=context_text,
            evidence=tuple(evidence_items),
            citations=tuple(citations),
            skipped_chunk_ids=tuple(skipped),
            char_count=len(context_text),
        )
