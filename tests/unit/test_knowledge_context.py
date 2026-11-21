from __future__ import annotations

from dataclasses import replace

from knowledge.context import ContextComposer
from knowledge.index import SQLiteKnowledgeIndex
from knowledge.models import DocumentChunk, DocumentPage, LoadedDocument
from knowledge.retrieval import HybridRetriever
from knowledge.validation import EvidenceValidator


def make_index() -> tuple[SQLiteKnowledgeIndex, list[DocumentChunk]]:
    content = "A documentação informa que o ciclo inicial tem sete etapas."
    document = LoadedDocument(
        source_uri="file:///tmp/roadmap.md",
        title="roadmap.md",
        sha256="d" * 64,
        media_type="text/markdown",
        size_bytes=len(content),
        pages=(DocumentPage(content),),
    )
    chunk = DocumentChunk(
        chunk_id="roadmap-chunk",
        document_id=document.document_id,
        source_uri=document.source_uri,
        title=document.title,
        source_sha256=document.sha256,
        media_type=document.media_type,
        content=content,
        start_offset=0,
        end_offset=len(content),
        section_path=("Roadmap", "Fase inicial"),
    )
    index = SQLiteKnowledgeIndex()
    index.add_document(document, [chunk])
    return index, [chunk]


def test_context_composer_emits_citations_and_exact_evidence() -> None:
    index, _ = make_index()
    hits = HybridRetriever(index).search("sete etapas")
    bundle = ContextComposer().compose(hits, max_chars=1000)

    assert "[E1]" in bundle.text
    assert bundle.char_count == len(bundle.text)
    assert bundle.evidence[0].content == hits[0].chunk.content
    assert bundle.evidence[0].metadata["chunk_id"] == hits[0].chunk.chunk_id
    assert bundle.evidence[0].locator.startswith("seção")
    index.close()


def test_context_budget_skips_a_chunk_instead_of_truncating_evidence() -> None:
    index, _ = make_index()
    hits = HybridRetriever(index).search("documentação")
    bundle = ContextComposer().compose(hits, max_chars=20)

    assert bundle.text == ""
    assert bundle.evidence == ()
    assert bundle.skipped_chunk_ids == ("roadmap-chunk",)
    index.close()


def test_evidence_validator_checks_provenance_but_not_factual_truth() -> None:
    index, _ = make_index()
    hits = HybridRetriever(index).search("sete etapas")
    bundle = ContextComposer().compose(hits, max_chars=1000)

    report = EvidenceValidator(index).validate(
        bundle,
        "A fonte descreve sete etapas [E1].",
    )

    assert report["status"] == "passed"
    assert report["factual_status"] == "not_independently_verified"
    assert report["summary"]["links_passed"] == 1
    index.close()


def test_evidence_validator_rejects_unknown_citation_ids() -> None:
    index, _ = make_index()
    hits = HybridRetriever(index).search("sete etapas")
    bundle = ContextComposer().compose(hits, max_chars=1000)

    report = EvidenceValidator(index).validate(bundle, "Alegação sem fonte [E9].")

    assert report["status"] == "failed"
    assert report["unknown_citations"] == ["E9"]
    index.close()


def test_evidence_validator_detects_stale_or_modified_evidence() -> None:
    index, _ = make_index()
    hits = HybridRetriever(index).search("sete etapas")
    bundle = ContextComposer().compose(hits, max_chars=1000)
    original = bundle.evidence[0]
    tampered = replace(original, content="Trecho alterado")
    changed_bundle = replace(bundle, evidence=(tampered,))

    report = EvidenceValidator(index).validate(changed_bundle, "Texto [E1].")

    assert report["status"] == "failed"
    assert report["summary"]["links_failed"] == 1
    index.close()
