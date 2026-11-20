"""Análise semântica heurística e explicitamente não calibrada."""

from __future__ import annotations

import re
import unicodedata

from core.capability_vectorizer import CapabilityVectorizer
from core.cognitive_task import CognitiveTask


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


_CALCULATION_PREFIXES = (
    "calcule", "calcular", "quanto e", "quanto da", "resolva",
    "resultado de", "compute", "evaluate", "what is",
)
_CONVERSION_PATTERN = re.compile(
    r"(?i)(?:converta|converter|transforme|transformar)?\s*"
    r"[-+]?\d+(?:[.,]\d+)?\s*[a-z°]+\s+(?:para|em|to)\s+[a-z°]+"
)
_RISK_CUES = (
    "diagnostico", "dose", "dosagem", "prescricao", "medicamento",
    "sintoma grave", "suicidio", "autoagressao", "explosivo", "veneno",
    "arma de fogo", "hackear conta", "invadir sistema", "processo judicial",
    "investimento", "alavancagem financeira",
)
_URGENCY_CUES = (
    "urgente", "urgencia", "imediatamente", "agora", "emergencia",
    "asap", "o quanto antes",
)
_AMBIGUOUS_CUES = (
    "isso", "aquilo", "ele", "ela", "dessa forma", "do mesmo jeito",
    "como antes", "aquele negocio",
)


def _looks_like_expression(text: str) -> bool:
    candidate = text.strip().rstrip("?.! ")
    return bool(
        re.fullmatch(r"[0-9\s()+\-*/%^.,]+", candidate)
        and re.search(r"[+\-*/%^]", candidate)
    )


def classify_intent(text: str) -> str:
    normalized = _fold(text).strip()

    if _CONVERSION_PATTERN.fullmatch(normalized):
        return "unit_conversion"
    if _contains_any(normalized, _CALCULATION_PREFIXES) or _looks_like_expression(normalized):
        return "calculation"
    if _contains_any(
        normalized,
        ("python", "codigo", "programacao", "bug", "debug", "script", "funcao", "sql"),
    ):
        return "programming"
    if _contains_any(normalized, ("resuma", "resumo", "sintetize", "em poucas palavras")):
        return "summarization"
    if _contains_any(normalized, ("traduza", "traduzir", "translate", "em ingles", "em portugues")):
        return "translation"
    if _contains_any(normalized, ("planeje", "planejar", "cronograma", "passo a passo", "etapas")):
        return "planning"
    if _contains_any(normalized, ("compare", "diferenca entre", "semelhancas entre")):
        return "comparison"
    if _contains_any(normalized, ("verifique", "confirme", "audite", "valide", "revise")):
        return "verification"
    if _contains_any(normalized, ("escreva", "redija", "crie um texto", "elabore")):
        return "writing"
    if _contains_any(normalized, ("explique", "o que e", "como funciona", "por que")):
        return "explanation"
    if "?" in text:
        return "question"
    if len(normalized.split()) <= 2:
        return "general_chat"
    return "general_question"


class SemanticAnalysisStage:
    """Estima intenção, afinidades e indicadores separados de risco/complexidade."""

    name = "semantic_analysis"

    def __init__(self, vectorizer: CapabilityVectorizer | None = None) -> None:
        self.vectorizer = vectorizer or CapabilityVectorizer()

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        text = task.normalized_text or task.original_text
        folded = _fold(text)
        words = re.findall(r"\w+", folded)

        task.intent = classify_intent(text)
        task.capabilities = self.vectorizer.classify(text).to_dict()

        length_factor = min(len(words) / 80.0, 1.0) * 0.35
        structure_factor = min(text.count("\n") / 5.0, 1.0) * 0.15
        complexity_terms = (
            "prove", "demonstre", "otimize", "arquitetura", "interdependencia",
            "diferencial", "tensor", "distribuido", "multiplas etapas",
        )
        complexity_factor = sum(term in folded for term in complexity_terms) * 0.08
        task.difficulty = round(
            min(1.0, 0.12 + length_factor + structure_factor + complexity_factor),
            3,
        )

        uncertainty = 0.18
        if len(words) <= 2:
            uncertainty += 0.42
        elif len(words) <= 4:
            uncertainty += 0.22
        if _contains_any(folded, _AMBIGUOUS_CUES):
            uncertainty += 0.28
        if task.intent in {"calculation", "unit_conversion", "programming"}:
            uncertainty -= 0.08
        task.uncertainty = round(min(1.0, max(0.0, uncertainty)), 3)

        task.risk = 0.82 if _contains_any(folded, _RISK_CUES) else 0.05
        task.urgency = 0.85 if _contains_any(folded, _URGENCY_CUES) else 0.05
        return task
