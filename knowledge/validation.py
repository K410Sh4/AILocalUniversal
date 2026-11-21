"""Validação estrutural de referências a evidências recuperadas."""

from __future__ import annotations

import re
from typing import Any

from knowledge.context import ContextBundle
from knowledge.index import SQLiteKnowledgeIndex


class EvidenceValidator:
    """Confere vínculo, hash e trecho; não certifica a verdade de alegações livres."""

    _CITATION_PATTERN = re.compile(r"\[(E[1-9][0-9]*)\]")

    def __init__(self, index: SQLiteKnowledgeIndex) -> None:
        self.index = index

    def validate(self, bundle: ContextBundle, answer: str) -> dict[str, Any]:
        known = {item.citation_id for item in bundle.citations}
        referenced = set(self._CITATION_PATTERN.findall(answer or ""))
        unknown = sorted(referenced - known)
        unused = sorted(known - referenced)
        link_checks: list[dict[str, Any]] = []

        citations_by_id = {item.citation_id: item for item in bundle.citations}
        evidence_by_id = {
            str(item.metadata.get("citation_id")): item
            for item in bundle.evidence
        }

        for citation_id, citation in citations_by_id.items():
            evidence = evidence_by_id.get(citation_id)
            chunk = self.index.get_chunk(citation.chunk_id)
            valid = (
                evidence is not None
                and chunk is not None
                and chunk.document_id == citation.document_id
                and chunk.source_uri == citation.source_uri
                and chunk.source_sha256 == citation.source_sha256
                and evidence.source == chunk.source_uri
                and evidence.content == chunk.content
                and evidence.metadata.get("chunk_id") == chunk.chunk_id
                and evidence.metadata.get("source_sha256") == chunk.source_sha256
                and evidence.metadata.get("start_offset") == chunk.start_offset
                and evidence.metadata.get("end_offset") == chunk.end_offset
            )
            link_checks.append(
                {
                    "citation_id": citation_id,
                    "chunk_id": citation.chunk_id,
                    "status": "passed" if valid else "failed",
                    "message": (
                        "A citação aponta para o trecho indexado e hash de origem."
                        if valid
                        else "A citação não corresponde ao trecho ou à versão indexada."
                    ),
                }
            )

        failed_links = [
            item for item in link_checks if item["status"] == "failed"
        ]
        if failed_links or unknown:
            status = "failed"
        elif not referenced:
            status = "needs_review"
        else:
            status = "passed"

        warnings: list[str] = []
        if not referenced:
            warnings.append("A resposta não contém citações reconhecidas.")
        if unused:
            warnings.append("Há evidências fornecidas ao modelo que não foram citadas.")
        if unknown:
            warnings.append("A resposta contém identificadores de citação desconhecidos.")

        return {
            "status": status,
            "structural_status": "failed" if status == "failed" else "passed",
            "factual_status": "not_independently_verified",
            "summary": {
                "citations_available": len(known),
                "citations_referenced": len(referenced & known),
                "unknown_citations": len(unknown),
                "links_passed": len(link_checks) - len(failed_links),
                "links_failed": len(failed_links),
                "warnings": len(warnings),
            },
            "checks": link_checks,
            "referenced_citations": sorted(referenced & known),
            "unused_citations": unused,
            "unknown_citations": unknown,
            "warnings": warnings,
            "limitations": [
                "A validação confirma integridade e proveniência das citações.",
                "Ela não prova que uma alegação textual é consequência lógica da fonte.",
                "Conteúdo gerado por LLM continua sem verificação factual independente.",
            ],
        }
