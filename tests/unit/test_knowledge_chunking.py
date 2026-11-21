from __future__ import annotations

from knowledge.chunking import DocumentChunker
from knowledge.models import DocumentPage, LoadedDocument


def make_document(
    text: str,
    media_type: str = "text/plain",
    pages: tuple[DocumentPage, ...] | None = None,
) -> LoadedDocument:
    return LoadedDocument(
        source_uri="file:///tmp/manual.md",
        title="manual.md",
        sha256="a" * 64,
        media_type=media_type,
        size_bytes=len(text.encode("utf-8")),
        pages=pages or (DocumentPage(text=text),),
    )


def test_chunker_preserves_offsets_and_page_numbers() -> None:
    text = "Palavra " * 50
    document = make_document(
        text,
        pages=(DocumentPage(text=text, page_number=3),),
    )

    chunks = DocumentChunker(max_chars=80, overlap_chars=12).chunk(document)

    assert len(chunks) > 1
    assert all(chunk.page_number == 3 for chunk in chunks)
    assert all(chunk.content == text[chunk.start_offset:chunk.end_offset] for chunk in chunks)
    assert all(len(chunk.content) <= 80 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_markdown_chunker_tracks_heading_hierarchy() -> None:
    text = (
        "# Manual\n\n"
        "Contexto inicial com detalhes suficientes.\n\n"
        "## Instalação\n\n"
        "Passos de instalação e configuração.\n\n"
        "### Linux\n\n"
        "Comandos para Linux.\n"
    )
    document = make_document(text, media_type="text/markdown")

    chunks = DocumentChunker(max_chars=180, overlap_chars=20).chunk(document)

    paths = {chunk.section_path for chunk in chunks}
    assert ("Manual",) in paths
    assert ("Manual", "Instalação") in paths
    assert ("Manual", "Instalação", "Linux") in paths


def test_chunker_never_combines_different_pdf_pages() -> None:
    document = make_document(
        "Texto da página um.\n\nTexto da página dois.",
        pages=(
            DocumentPage("Texto da página um.", page_number=1),
            DocumentPage("Texto da página dois.", page_number=2),
        ),
    )

    chunks = DocumentChunker().chunk(document)

    assert [chunk.page_number for chunk in chunks] == [1, 2]


def test_markdown_code_fence_stays_together_when_it_fits() -> None:
    text = (
        "# Exemplo\n\n"
        "~~~python\n"
        "print('não executar')\n"
        "valor = 42\n"
        "~~~\n\n"
        "Texto final.\n"
    )
    document = make_document(text, media_type="text/markdown")

    chunks = DocumentChunker(max_chars=160, overlap_chars=10).chunk(document)

    code_chunks = [chunk for chunk in chunks if "print(" in chunk.content]
    assert len(code_chunks) == 1
    assert "~~~python" in code_chunks[0].content
    assert "~~~" in code_chunks[0].content
