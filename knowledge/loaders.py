"""Loaders locais com limites explícitos e extração sem execução de conteúdo."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Protocol

from knowledge.errors import (
    DocumentLoadError,
    EmptyDocumentError,
    MissingOptionalDependencyError,
    UnsupportedDocumentError,
)
from knowledge.models import DocumentPage, LoadedDocument


class DocumentLoader(Protocol):
    def supports(self, path: Path) -> bool:
        ...

    def load(self, path: Path) -> LoadedDocument:
        ...


class _LocalFileLoader:
    def __init__(
        self,
        max_bytes: int = 20 * 1024 * 1024,
        max_characters: int = 2_000_000,
    ) -> None:
        if max_bytes < 1 or max_characters < 1:
            raise ValueError("Os limites do loader devem ser positivos.")
        self.max_bytes = max_bytes
        self.max_characters = max_characters

    def _read(self, path: Path) -> tuple[Path, bytes, str]:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise DocumentLoadError(f"Arquivo não encontrado ou inválido: {resolved}")
        try:
            size = resolved.stat().st_size
            if size > self.max_bytes:
                raise DocumentLoadError(
                    f"Arquivo excede o limite de {self.max_bytes} bytes."
                )
            content = resolved.read_bytes()
        except OSError as exc:
            raise DocumentLoadError(f"Não foi possível ler o arquivo: {resolved}") from exc
        if len(content) > self.max_bytes:
            raise DocumentLoadError(f"Arquivo excede o limite de {self.max_bytes} bytes.")
        digest = hashlib.sha256(content).hexdigest()
        return resolved, content, digest

    @staticmethod
    def _decode(content: bytes, path: Path) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentLoadError(
                f"O arquivo {path.name} não está codificado em UTF-8."
            ) from exc

    def _check_text_size(self, text: str) -> None:
        if len(text) > self.max_characters:
            raise DocumentLoadError(
                f"Texto extraído excede o limite de {self.max_characters} caracteres."
            )


class TextLoader(_LocalFileLoader):
    """Loader UTF-8 para texto e formatos técnicos sem parser executável."""

    extensions = {
        ".txt", ".text", ".log", ".csv", ".json", ".yaml", ".yml",
        ".toml", ".py", ".sh", ".ini", ".cfg", ".xml", ".sql",
    }

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> LoadedDocument:
        resolved, raw, digest = self._read(path)
        text = self._decode(raw, resolved)
        self._check_text_size(text)
        if not text.strip():
            raise EmptyDocumentError(f"O arquivo {resolved.name} não contém texto.")
        return LoadedDocument(
            source_uri=resolved.as_uri(),
            title=resolved.name,
            sha256=digest,
            media_type="text/plain",
            size_bytes=len(raw),
            pages=(DocumentPage(text=text),),
            metadata={"file_name": resolved.name},
        )


class MarkdownLoader(_LocalFileLoader):
    """Loader Markdown UTF-8; não executa HTML, scripts ou links."""

    extensions = {".md", ".markdown"}

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> LoadedDocument:
        resolved, raw, digest = self._read(path)
        text = self._decode(raw, resolved)
        self._check_text_size(text)
        if not text.strip():
            raise EmptyDocumentError(f"O arquivo {resolved.name} não contém texto.")
        return LoadedDocument(
            source_uri=resolved.as_uri(),
            title=resolved.name,
            sha256=digest,
            media_type="text/markdown",
            size_bytes=len(raw),
            pages=(DocumentPage(text=text),),
            metadata={"file_name": resolved.name},
        )


class PdfLoader(_LocalFileLoader):
    """Extrai texto selecionável de PDFs; não executa JavaScript nem aplica OCR."""

    def __init__(
        self,
        max_bytes: int = 20 * 1024 * 1024,
        max_characters: int = 2_000_000,
        max_pages: int = 500,
    ) -> None:
        super().__init__(max_bytes=max_bytes, max_characters=max_characters)
        if max_pages < 1:
            raise ValueError("max_pages deve ser positivo.")
        self.max_pages = max_pages

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def load(self, path: Path) -> LoadedDocument:
        resolved, raw, digest = self._read(path)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise MissingOptionalDependencyError(
                "A leitura de PDF requer a dependência opcional pypdf. "
                'Instale com: pip install -e ".[documents]".'
            ) from exc

        try:
            reader = PdfReader(BytesIO(raw), strict=False)
            if reader.is_encrypted:
                raise DocumentLoadError(
                    f"O PDF {resolved.name} está criptografado; descriptografia não é automática."
                )
            if len(reader.pages) > self.max_pages:
                raise DocumentLoadError(
                    f"PDF excede o limite de {self.max_pages} páginas."
                )
            pages: list[DocumentPage] = []
            total_characters = 0
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                total_characters += len(page_text)
                if total_characters > self.max_characters:
                    raise DocumentLoadError(
                        "Texto extraído do PDF excede o limite configurado."
                    )
                pages.append(DocumentPage(text=page_text, page_number=page_number))
        except DocumentLoadError:
            raise
        except Exception as exc:
            raise DocumentLoadError(
                f"Não foi possível extrair texto do PDF {resolved.name}."
            ) from exc

        if not any(page.text.strip() for page in pages):
            raise EmptyDocumentError(
                f"O PDF {resolved.name} não contém texto selecionável. OCR não está habilitado."
            )

        metadata = reader.metadata
        title = str(getattr(metadata, "title", "") or "").strip() or resolved.name
        return LoadedDocument(
            source_uri=resolved.as_uri(),
            title=title,
            sha256=digest,
            media_type="application/pdf",
            size_bytes=len(raw),
            pages=tuple(pages),
            metadata={"file_name": resolved.name, "page_count": len(pages)},
        )


class LoaderRegistry:
    """Seleciona loaders por extensão, sem baixar ou procurar arquivos automaticamente."""

    def __init__(self, loaders: tuple[DocumentLoader, ...] | None = None) -> None:
        self.loaders = loaders or (MarkdownLoader(), PdfLoader(), TextLoader())

    def load(self, path: str | Path) -> LoadedDocument:
        candidate = Path(path)
        for loader in self.loaders:
            if loader.supports(candidate):
                return loader.load(candidate)
        raise UnsupportedDocumentError(
            f"Formato não suportado: {candidate.suffix or '(sem extensão)'}."
        )
