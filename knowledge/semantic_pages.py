"""Neural Semantic Atlas: fichas locais e rastreáveis por página documental.

A versão 0.1 usa sumarização extrativa e candidatos lexicais determinísticos.
Não chama LLM, não inventa entidades e não altera o índice de chunks existente.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from knowledge.models import DocumentChunk, LoadedDocument, SemanticPageRecord

_STOPWORDS = {
    "a", "as", "ao", "aos", "aquela", "aquele", "aquilo", "ate", "com",
    "como", "da", "das", "de", "dela", "dele", "do", "dos", "e", "ela",
    "ele", "em", "entre", "essa", "esse", "esta", "este", "eu", "foi",
    "ha", "isso", "isto", "ja", "lhe", "mais", "mas", "me", "mesmo",
    "meu", "minha", "muito", "na", "nas", "no", "nos", "o", "os", "ou",
    "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quais",
    "quando", "quanto", "quantos", "quantas", "que", "quem", "se", "ser",
    "seu", "sua", "sao", "sob", "sobre", "tambem", "tem", "um", "uma",
    "umas", "uns", "voce", "voces", "the", "an", "and", "are", "at",
    "be", "by", "for", "from", "how", "in", "is", "it", "of", "on",
    "or", "that", "this", "to", "was", "what", "when", "where", "which",
    "who", "why", "with",
}


class EntityExtractor(Protocol):
    """Contrato opcional para extrator explícito de entidades."""

    method_id: str

    def extract_entities(self, text: str) -> Sequence[str]:
        ...


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _words(text: str) -> list[str]:
    return [
        _fold(token)
        for token in re.findall(r"[^\W_][\w'-]{2,}", text, flags=re.UNICODE)
        if _fold(token) not in _STOPWORDS
    ]


class SemanticPageIndexer:
    """Constrói fichas por página com resumo extrativo e proveniência explícita."""

    VERSION = "nesa-0.1"

    def __init__(
        self,
        *,
        summary_words: int = 35,
        max_keywords: int = 12,
        max_concepts: int = 8,
        entity_extractor: EntityExtractor | None = None,
    ) -> None:
        if not 20 <= summary_words <= 50:
            raise ValueError("summary_words deve ficar entre 20 e 50.")
        if max_keywords < 1 or max_concepts < 1:
            raise ValueError("Limites de palavras-chave e conceitos devem ser positivos.")
        self.summary_words = summary_words
        self.max_keywords = max_keywords
        self.max_concepts = max_concepts
        self.entity_extractor = entity_extractor

    @staticmethod
    def _sentences(text: str) -> list[tuple[str, int, int]]:
        result: list[tuple[str, int, int]] = []
        cursor = 0
        for part in re.split(r"(?<=[.!?])\s+|\n+", text):
            stripped = part.strip()
            if not stripped:
                continue
            start = text.find(stripped, cursor)
            if start < 0:
                continue
            end = start + len(stripped)
            result.append((stripped, start, end))
            cursor = end
        return result

    def _summary(self, text: str) -> tuple[str, tuple[tuple[int, int], ...]]:
        sentences = self._sentences(text)
        if not sentences:
            return "", ()

        sentence_tokens = [_words(sentence) for sentence, _, _ in sentences]
        frequencies = Counter(token for tokens in sentence_tokens for token in tokens)
        ranked: list[tuple[float, int, int, str]] = []
        for index, ((sentence, start, end), tokens) in enumerate(
            zip(sentences, sentence_tokens, strict=True)
        ):
            if not tokens:
                continue
            score = sum(frequencies[token] for token in tokens) / (len(tokens) ** 0.5)
            if index == 0:
                score += 0.15
            ranked.append((score, start, end, sentence))

        if not ranked:
            sentence, start, end = sentences[0]
            words = sentence.split()
            clipped = " ".join(words[: self.summary_words])
            return clipped, ((start, end),)

        selected: list[tuple[int, int, str]] = []
        used_words = 0
        for _, start, end, sentence in sorted(ranked, key=lambda item: (-item[0], item[1])):
            sentence_words = sentence.split()
            remaining = self.summary_words - used_words
            if remaining <= 0:
                break
            if len(sentence_words) > remaining:
                if not selected:
                    sentence_words = sentence_words[: self.summary_words]
                else:
                    continue
            clipped = " ".join(sentence_words)
            selected.append((start, end, clipped))
            used_words += len(sentence_words)

        selected.sort(key=lambda item: item[0])
        return (
            " ".join(item[2] for item in selected),
            tuple((item[0], item[1]) for item in selected),
        )

    def _keywords_and_concepts(
        self,
        title: str,
        text: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        source_tokens = re.findall(r"[^\W_][\w'-]{2,}", f"{title} {text}", flags=re.UNICODE)
        normalized = [_fold(token) for token in source_tokens]
        counts: Counter[str] = Counter()
        display: dict[str, str] = {}
        first_seen: dict[str, int] = {}
        for position, (raw, token) in enumerate(zip(source_tokens, normalized, strict=True)):
            if token in _STOPWORDS:
                continue
            counts[token] += 1
            display.setdefault(token, raw)
            first_seen.setdefault(token, position)
        keywords = tuple(
            display[token]
            for token in sorted(counts, key=lambda item: (-counts[item], first_seen[item], item))
            [: self.max_keywords]
        )

        bigram_counts: Counter[str] = Counter()
        bigram_display: dict[str, str] = {}
        for index in range(len(source_tokens) - 1):
            left, right = normalized[index : index + 2]
            if left in _STOPWORDS or right in _STOPWORDS:
                continue
            phrase = f"{left} {right}"
            bigram_counts[phrase] += 1
            bigram_display.setdefault(
                phrase, f"{source_tokens[index]} {source_tokens[index + 1]}"
            )
        concepts = tuple(
            bigram_display[phrase]
            for phrase in sorted(
                bigram_counts,
                key=lambda item: (-bigram_counts[item], item),
            )[: self.max_concepts]
        )
        return keywords, concepts

    def build(
        self,
        document: LoadedDocument,
        chunks: Sequence[DocumentChunk],
    ) -> list[SemanticPageRecord]:
        """Gera uma ficha por página não vazia, com os caminhos de seção dos chunks."""
        records: list[SemanticPageRecord] = []
        for page_index, page in enumerate(document.pages):
            text = page.text.strip()
            if not text:
                continue
            summary, spans = self._summary(page.text)
            keywords, concepts = self._keywords_and_concepts(document.title, text)
            if self.entity_extractor is None:
                entities: tuple[str, ...] = ()
                entity_method = "not_configured"
            else:
                entities = tuple(dict.fromkeys(
                    entity.strip()
                    for entity in self.entity_extractor.extract_entities(text)
                    if isinstance(entity, str) and entity.strip()
                ))
                entity_method = getattr(
                    self.entity_extractor, "method_id", "custom_entity_extractor"
                )

            page_chunks = [
                chunk for chunk in chunks
                if chunk.page_number == page.page_number
            ]
            section_paths = tuple(dict.fromkeys(
                chunk.section_path for chunk in page_chunks if chunk.section_path
            ))
            page_sha256 = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
            identity = (
                f"{document.document_id}:{document.sha256}:{page_index}:"
                f"{page.page_number}:{page_sha256}"
            )
            page_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            records.append(
                SemanticPageRecord(
                    page_id=page_id,
                    document_id=document.document_id,
                    source_uri=document.source_uri,
                    source_sha256=document.sha256,
                    page_index=page_index,
                    page_number=page.page_number,
                    title=document.title,
                    content_sha256=page_sha256,
                    content_char_count=len(page.text),
                    summary=summary,
                    summary_spans=spans,
                    concepts=concepts,
                    entities=entities,
                    keywords=keywords,
                    section_paths=section_paths,
                    summary_method="extractive_frequency_v1",
                    concept_method="lexical_ngrams_v1",
                    entity_method=entity_method,
                    metadata={
                        "media_type": document.media_type,
                        "page_offset_unit": "unicode_codepoints",
                        "summary_word_count": len(summary.split()),
                        "source_page_index": page_index,
                    },
                )
            )
        return records
