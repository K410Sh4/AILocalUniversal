"""Registro extensível de áreas cognitivas e taxonomia NAPA inicial."""

# ruff: noqa: I001

from __future__ import annotations

from collections.abc import Iterable

from napa.contracts import CognitiveArea, CognitiveAreaKind


DEFAULT_COGNITIVE_AREAS: tuple[CognitiveArea, ...] = (
    CognitiveArea(
        area_id="mathematics",
        name="Mathematics",
        kind=CognitiveAreaKind.DETERMINISTIC_TOOL,
        description="Cálculos, matemática, álgebra e operações numéricas suportadas.",
        capability_dimensions=("math_logic",),
        intents=("calculation",),
        anchors=("matematica", "equacao", "integral", "derivada", "calcule", "calcular",
                 "percentual", "juros"),
    ),
    CognitiveArea(
        area_id="conversion",
        name="Conversion",
        kind=CognitiveAreaKind.DETERMINISTIC_TOOL,
        description="Conversões explícitas de unidades e formatos suportados.",
        intents=("unit_conversion",),
        anchors=("conversao", "converta", "converter", "transforme", "transformar"),
    ),
    CognitiveArea(
        area_id="communication",
        name="Communication",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Compreensão e produção linguística para interação e explicação.",
        capability_dimensions=("general_conversation", "writing_creativity"),
        intents=("summarization", "translation", "writing", "explanation", "question",
                 "general_chat", "general_question"),
        anchors=("explique", "explicar", "comunique", "comunicar", "responda", "responder",
                 "traduza", "traduzir", "resuma", "resumir", "converse", "mensagem"),
    ),
    CognitiveArea(
        area_id="social_cordiality",
        name="Social / Cordiality",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Ajustes de tom, cordialidade, formalidade e apresentação da resposta.",
        anchors=("educado", "educada", "cordial", "gentil", "respeitoso", "respeitosa",
                 "tom amigavel", "amigavel", "empatico", "empatia", "formal", "informal"),
    ),
    CognitiveArea(
        area_id="reasoning",
        name="Reasoning",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Análise, planejamento, comparação, justificativa e decomposição.",
        capability_dimensions=("planning", "verification", "interdisciplinary"),
        intents=("planning", "comparison", "verification"),
        anchors=("analise", "analisar", "raciocine", "raciocinar", "demonstre", "prove",
                 "justifique", "avalie", "otimize", "estrategia", "passo a passo",
                 "interdependencia"),
    ),
    CognitiveArea(
        area_id="opinion",
        name="Opinion",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Avaliação de alternativas e apresentação de perspectivas justificadas.",
        intents=("comparison",),
        anchors=("opiniao", "o que voce acha", "qual sua opiniao", "recomende",
                 "recomendacao", "vale a pena", "vantagens", "desvantagens", "pros", "contras"),
    ),
    CognitiveArea(
        area_id="creativity",
        name="Creativity",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Ideação, associação e produção de alternativas originais.",
        capability_dimensions=("writing_creativity",),
        anchors=("criatividade", "criativo", "criativa", "ideia", "ideias", "brainstorm",
                 "invente", "inventar", "imagine", "imaginar", "historia", "poema", "roteiro"),
    ),
    CognitiveArea(
        area_id="generation",
        name="Generation",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Geração de artefatos textuais, planos, código ou outros conteúdos.",
        intents=("writing",),
        anchors=("crie", "criar", "gere", "gerar", "escreva", "redija", "produza",
                 "implemente", "construa", "desenvolva"),
    ),
    CognitiveArea(
        area_id="programming",
        name="Programming",
        kind=CognitiveAreaKind.NEURAL_SPECIALIST,
        description="Engenharia de software, programação, depuração e código.",
        capability_dimensions=("programming",),
        intents=("programming",),
        anchors=("python", "codigo", "programacao", "debug", "bug", "script", "sql",
                 "funcao", "api", "bash", "terminal"),
    ),
    CognitiveArea(
        area_id="knowledge",
        name="Knowledge",
        kind=CognitiveAreaKind.COGNITIVE_CAPABILITY,
        description="Conhecimento conceitual, científico e análise de informações.",
        capability_dimensions=("science_knowledge",),
        intents=("explanation",),
        anchors=("conhecimento", "conceito", "teoria", "explicacao", "evidencia",
                 "fontes", "documentacao", "pesquise", "pesquisa", "artigo"),
    ),
    CognitiveArea(
        area_id="retrieval",
        name="Knowledge Retrieval",
        kind=CognitiveAreaKind.DETERMINISTIC_TOOL,
        description="Consulta a memória local, documentos e fontes indexadas.",
        capability_dimensions=("rag_external_memory", "external_research"),
        anchors=("documento", "pdf", "arquivo", "meus arquivos", "base de conhecimento",
                 "historico", "busque", "recupere", "consulte", "pesquise"),
    ),
    CognitiveArea(
        area_id="perception",
        name="Perception",
        kind=CognitiveAreaKind.NEURAL_SPECIALIST,
        description="Percepção e interpretação de imagens, áudio e vídeo.",
        capability_dimensions=("vision_multimodal",),
        anchors=("imagem", "foto", "figura", "video", "audio", "captura de tela",
                 "screenshot"),
    ),
    CognitiveArea(
        area_id="tool_use",
        name="Tool Use",
        kind=CognitiveAreaKind.DETERMINISTIC_TOOL,
        description="Acionamento de ferramentas, comandos e operações locais controladas.",
        capability_dimensions=("tool_use",),
        anchors=("execute", "rode", "comando", "terminal", "script", "abra arquivo",
                 "calcule", "converta"),
    ),
)


class CognitiveAreaRegistry:
    """Registro em memória; extensões precisam fornecer contratos declarativos."""

    def __init__(self, areas: Iterable[CognitiveArea] = ()) -> None:
        self._areas: dict[str, CognitiveArea] = {}
        for area in areas:
            self.register(area)

    def register(self, area: CognitiveArea) -> None:
        if not isinstance(area, CognitiveArea):
            raise TypeError("area precisa ser CognitiveArea.")
        if area.area_id in self._areas:
            raise ValueError(f"Área já registrada: {area.area_id}")
        self._areas[area.area_id] = area

    def get(self, area_id: str) -> CognitiveArea:
        try:
            return self._areas[area_id]
        except KeyError as exc:
            raise KeyError(f"Área cognitiva desconhecida: {area_id}") from exc

    def find(self, area_id: str) -> CognitiveArea | None:
        return self._areas.get(area_id)

    @property
    def areas(self) -> tuple[CognitiveArea, ...]:
        return tuple(self._areas[key] for key in sorted(self._areas))

    @property
    def area_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._areas))

    def __len__(self) -> int:
        return len(self._areas)


def create_default_registry() -> CognitiveAreaRegistry:
    """Cria uma instância isolada do registro padrão da NAPA 1.0."""
    return CognitiveAreaRegistry(DEFAULT_COGNITIVE_AREAS)
