"""Chunking determinístico com limites, offsets, páginas e seções preservados."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from knowledge.models import DocumentChunk, LoadedDocument


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    section_path: tuple[str, ...]


class DocumentChunker:
    """Divide documentos em trechos sem atravessar páginas ou seções Markdown."""

    def __init__(self, max_chars: int = 1200, overlap_chars: int = 160) -> None:
        if max_chars < 32:
            raise ValueError("max_chars deve ser pelo menos 32.")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars deve estar entre 0 e max_chars.")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    @staticmethod
    def _blocks(text: str, markdown: bool) -> list[_Block]:
        blocks: list[_Block] = []
        section_stack: list[str] = []
        current_start: int | None = None
        current_end = 0
        offset = 0
        fence_marker: str | None = None

        def flush() -> None:
            nonlocal current_start, current_end
            if current_start is not None and current_end > current_start:
                blocks.append(
                    _Block(current_start, current_end, tuple(section_stack))
                )
            current_start = None
            current_end = 0

        for line in text.splitlines(keepends=True):
            line_start = offset
            line_end = line_start + len(line)
            stripped = line.strip()

            heading = None
            if markdown and fence_marker is None:
                heading = re.match(r"^(#{1,6})[ \t]+(.+?)\s*#*\s*$", stripped)
            if heading:
                flush()
                level = len(heading.group(1))
                title = heading.group(2).strip()
                section_stack = section_stack[: level - 1]
                section_stack.append(title)
                blocks.append(_Block(line_start, line_end, tuple(section_stack)))
                offset = line_end
                continue

            fence = None
            if markdown:
                fence = re.match(r"^(\x60{3,}|~{3,})", stripped)
            if fence_marker is None and fence:
                fence_marker = fence.group(1)[0]
            elif fence_marker is not None and fence and fence.group(1)[0] == fence_marker:
                fence_marker = None

            if not stripped and fence_marker is None:
                flush()
                offset = line_end
                continue

            if current_start is None:
                current_start = line_start
            current_end = line_end
            offset = line_end

        flush()
        return blocks

    def _split_block(self, text: str, block: _Block) -> list[_Block]:
        if block.end - block.start <= self.max_chars:
            return [block]

        pieces: list[_Block] = []
        cursor = block.start
        while cursor < block.end:
            limit = min(cursor + self.max_chars, block.end)
            if limit < block.end:
                search_floor = cursor + max(16, self.max_chars // 2)
                newline = text.rfind("\n", search_floor, limit)
                whitespace = text.rfind(" ", search_floor, limit)
                tab = text.rfind("\t", search_floor, limit)
                boundary = max(newline, whitespace, tab)
                if boundary > cursor:
                    limit = boundary + 1

            if limit <= cursor:
                limit = min(cursor + self.max_chars, block.end)
            pieces.append(_Block(cursor, limit, block.section_path))
            if limit >= block.end:
                break
            next_cursor = max(cursor + 1, limit - self.overlap_chars)
            cursor = next_cursor
        return pieces

    def chunk(self, document: LoadedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        markdown = document.media_type == "text/markdown"
        chunk_index = 0

        for page in document.pages:
            text = page.text
            if not text.strip():
                continue

            raw_blocks = self._blocks(text, markdown=markdown)
            blocks = [
                piece
                for block in raw_blocks
                for piece in self._split_block(text, block)
            ]
            current: list[_Block] = []

            def emit(group: list[_Block]) -> None:
                nonlocal chunk_index
                if not group:
                    return
                start = group[0].start
                end = group[-1].end
                raw = text[start:end]
                left_trim = len(raw) - len(raw.lstrip())
                right_trimmed = raw.rstrip()
                actual_start = start + left_trim
                actual_end = start + len(right_trimmed)
                content = text[actual_start:actual_end]
                if not content.strip():
                    return

                page_label = page.page_number if page.page_number is not None else 0
                identity = (
                    f"{document.document_id}:{document.sha256}:{page_label}:"
                    f"{actual_start}:{actual_end}:{content}"
                )
                chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        source_uri=document.source_uri,
                        title=document.title,
                        source_sha256=document.sha256,
                        media_type=document.media_type,
                        content=content,
                        start_offset=actual_start,
                        end_offset=actual_end,
                        page_number=page.page_number,
                        section_path=group[0].section_path,
                        metadata={
                            "chunk_index": chunk_index,
                            "page_offset_unit": "unicode_codepoints",
                        },
                    )
                )
                chunk_index += 1

            for block in blocks:
                must_flush = False
                if current:
                    section_changed = current[-1].section_path != block.section_path
                    exceeds_limit = block.end - current[0].start > self.max_chars
                    must_flush = section_changed or exceeds_limit

                if must_flush:
                    previous = current
                    emit(previous)
                    carry: list[_Block] = []
                    carried_chars = 0
                    for old in reversed(previous):
                        block_size = old.end - old.start
                        if carried_chars + block_size > self.overlap_chars:
                            break
                        carry.insert(0, old)
                        carried_chars += block_size
                    current = carry
                    while current and (
                        current[0].section_path != block.section_path
                        or block.end - current[0].start > self.max_chars
                    ):
                        current.pop(0)

                current.append(block)

            emit(current)

        return chunks
