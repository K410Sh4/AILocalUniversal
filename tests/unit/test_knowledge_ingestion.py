from __future__ import annotations

from pathlib import Path

from knowledge.index import SQLiteKnowledgeIndex
from knowledge.ingestion import DocumentIngestor


def test_markdown_ingestion_is_searchable_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "manual.md"
    source.write_text(
        "# Instalação\n\nConfigure o serviço local com segurança.\n",
        encoding="utf-8",
    )
    index = SQLiteKnowledgeIndex()
    result = DocumentIngestor(index).ingest(source)

    hits = index.search("servico seguranca")

    assert result.chunk_count >= 1
    assert result.media_type == "text/markdown"
    assert hits
    assert hits[0].chunk.section_path == ("Instalação",)
    assert hits[0].chunk.source_sha256 == result.source_sha256
    index.close()


def test_reingestion_updates_the_same_source_without_stale_results(
    tmp_path: Path,
) -> None:
    source = tmp_path / "manual.txt"
    source.write_text("A versão antiga descreve o legado.", encoding="utf-8")
    index = SQLiteKnowledgeIndex()
    ingestor = DocumentIngestor(index)
    first = ingestor.ingest(source)

    source.write_text("A versão nova descreve o sistema atual.", encoding="utf-8")
    second = ingestor.ingest(source)

    assert first.document_id == second.document_id
    assert first.source_sha256 != second.source_sha256
    assert index.search("legado") == []
    assert index.search("atual")
    assert len(index.list_documents()) == 1
    index.close()
