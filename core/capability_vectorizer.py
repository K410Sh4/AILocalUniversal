"""Vetor heurístico inicial de capacidades, baseado em âncoras lexicais.

Os scores representam afinidade lexical entre 0 e 1. Não são probabilidades,
embeddings, nem uma avaliação calibrada da capacidade real necessária.
"""

# ruff: noqa: I001

from __future__ import annotations

import dataclasses
import unicodedata


CAPABILITY_DIMENSIONS: tuple[str, ...] = (
    "general_conversation",
    "programming",
    "math_logic",
    "science_knowledge",
    "rag_external_memory",
    "vision_multimodal",
    "writing_creativity",
    "external_research",
    "tool_use",
    "planning",
    "verification",
    "interdisciplinary",
)


CAPABILITY_ANCHORS: dict[str, tuple[str, ...]] = {
    "general_conversation": (
        "converse", "olá", "oi", "pergunta", "explique", "me ajuda",
        "o que", "como funciona", "por que",
    ),
    "programming": (
        "python", "codigo", "programacao", "debug", "bug", "funcao",
        "classe", "api", "sql", "script", "terminal", "bash", "git",
        "compilar", "stack trace",
    ),
    "math_logic": (
        "calcule", "calcular", "matematica", "equacao", "integral",
        "derivada", "soma", "multiplicacao", "divisao", "raiz",
        "logica", "prova", "teorema", "percentual", "converta",
    ),
    "science_knowledge": (
        "fisica", "quimica", "biologia", "relatividade", "energia",
        "molecula", "gravidade", "einstein", "schwarzschild", "celula",
        "termodinamica", "astronomia",
    ),
    "rag_external_memory": (
        "documento", "pdf", "arquivo", "fonte", "base de conhecimento",
        "meus arquivos", "historico", "anexo", "conteudo enviado",
    ),
    "vision_multimodal": (
        "imagem", "foto", "figura", "visual", "video", "audio",
        "captura de tela", "screenshot",
    ),
    "writing_creativity": (
        "escreva", "redija", "resuma", "historia", "email", "artigo",
        "roteiro", "poema", "texto", "reformule", "traduza",
    ),
    "external_research": (
        "pesquise", "pesquisa", "atualidade", "noticias", "internet",
        "web", "referencias", "fontes atuais", "fontes externas",
    ),
    "tool_use": (
        "calcule", "converta", "execute", "abra", "busque", "pesquise",
        "arquivo", "terminal", "script",
    ),
    "planning": (
        "planeje", "passo a passo", "etapas", "cronograma", "estrategia",
        "organize", "implemente", "construa", "projeto", "roteiro",
    ),
    "verification": (
        "verifique", "confirme", "audite", "compare", "valide",
        "revise", "prove", "cheque", "teste", "corrija",
    ),
    "interdisciplinary": (
        "interdisciplinar", "relacione", "interacao entre",
        "impacto conjunto", "combine", "multidisciplinar",
    ),
}


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


@dataclasses.dataclass(slots=True)
class CapabilityVector:
    """Pontuações heurísticas entre 0 e 1 para dimensões conhecidas."""

    scores: dict[str, float] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.scores) - set(CAPABILITY_DIMENSIONS)
        if unknown:
            raise ValueError(f"Dimensões desconhecidas: {', '.join(sorted(unknown))}")
        if any(not 0.0 <= value <= 1.0 for value in self.scores.values()):
            raise ValueError("Pontuações devem estar entre 0.0 e 1.0.")

    def to_dict(self) -> dict[str, float]:
        return {name: self.scores.get(name, 0.0) for name in CAPABILITY_DIMENSIONS}


class CapabilityVectorizer:
    """Classificador lexical explicável; não usa rede nem modelo externo."""

    def classify(self, text: str) -> CapabilityVector:
        normalized = _fold(text)
        scores: dict[str, float] = {}

        for dimension in CAPABILITY_DIMENSIONS:
            if dimension == "interdisciplinary":
                continue
            anchors = CAPABILITY_ANCHORS[dimension]
            matches = sum(1 for anchor in anchors if _fold(anchor) in normalized)
            scores[dimension] = round(min(1.0, matches * 0.28), 3)

        active_dimensions = sum(
            score > 0.0
            for name, score in scores.items()
            if name != "general_conversation"
        )
        scores["interdisciplinary"] = round(
            min(1.0, max(0, active_dimensions - 1) * 0.22),
            3,
        )
        return CapabilityVector(scores=scores)
