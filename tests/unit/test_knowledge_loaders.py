from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from knowledge.errors import (
    DocumentLoadError,
    EmptyDocumentError,
    MissingOptionalDependencyError,
    UnsupportedDocumentError,
)
from knowledge.loaders import LoaderRegistry, MarkdownLoader, PdfLoader, TextLoader


def test_text_loader_preserves_utf8_content_and_hash(tmp_path: Path) -> None:
    source = tmp_path / "notas.txt"
    source.write_text("Informação local e verificável.\n", encoding="utf-8")

    loaded = TextLoader().load(source)

    assert loaded.title == "notas.txt"
    assert loaded.media_type == "text/plain"
    assert loaded.pages[0].text == "Informação local e verificável.\n"
    assert len(loaded.sha256) == 64
    assert loaded.source_uri.startswith("file://")


def test_markdown_loader_preserves_markdown_structure(tmp_path: Path) -> None:
    source = tmp_path / "guia.md"
    content = "# Introdução\n\nTexto com **destaque**.\n"
    source.write_text(content, encoding="utf-8")

    loaded = MarkdownLoader().load(source)

    assert loaded.media_type == "text/markdown"
    assert loaded.pages[0].text == content


def test_loader_registry_rejects_unknown_extensions(tmp_path: Path) -> None:
    source = tmp_path / "arquivo.bin"
    source.write_bytes(b"data")

    with pytest.raises(UnsupportedDocumentError):
        LoaderRegistry().load(source)


def test_loader_enforces_file_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "grande.txt"
    source.write_text("x" * 40, encoding="utf-8")

    with pytest.raises(DocumentLoadError, match="limite"):
        TextLoader(max_bytes=20).load(source)


def test_loader_rejects_empty_text(tmp_path: Path) -> None:
    source = tmp_path / "vazio.txt"
    source.write_text(" \n\t", encoding="utf-8")

    with pytest.raises(EmptyDocumentError):
        TextLoader().load(source)


def test_pdf_loader_extracts_each_page_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "relatorio.pdf"
    source.write_bytes(b"%PDF-fake")

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        is_encrypted = False
        pages = [FakePage("Página um"), FakePage("Página dois")]
        metadata = SimpleNamespace(title="Relatório de teste")

        def __init__(self, stream: object, strict: bool) -> None:
            assert strict is False
            assert stream is not None

    module = types.ModuleType("pypdf")
    module.PdfReader = FakeReader
    monkeypatch.setitem(sys.modules, "pypdf", module)

    loaded = PdfLoader().load(source)

    assert loaded.title == "Relatório de teste"
    assert loaded.media_type == "application/pdf"
    assert [page.page_number for page in loaded.pages] == [1, 2]
    assert [page.text for page in loaded.pages] == ["Página um", "Página dois"]


def test_pdf_loader_reports_missing_optional_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "sem-dependencia.pdf"
    source.write_bytes(b"%PDF-fake")
    monkeypatch.setitem(sys.modules, "pypdf", None)

    with pytest.raises(MissingOptionalDependencyError, match="pypdf"):
        PdfLoader().load(source)


def test_pdf_loader_rejects_encrypted_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "protegido.pdf"
    source.write_bytes(b"%PDF-fake")

    class FakeReader:
        is_encrypted = True
        pages: list[object] = []
        metadata = None

        def __init__(self, stream: object, strict: bool) -> None:
            pass

    module = types.ModuleType("pypdf")
    module.PdfReader = FakeReader
    monkeypatch.setitem(sys.modules, "pypdf", module)

    with pytest.raises(DocumentLoadError, match="criptografado"):
        PdfLoader().load(source)
