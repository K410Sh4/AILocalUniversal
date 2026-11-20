"""Composição do pipeline cognitivo inicial."""

from __future__ import annotations

from core.capability_vectorizer import CapabilityVectorizer
from core.cognitive_planner import CognitivePlanningStage
from core.cognitive_task import CognitiveTask
from core.deterministic_tools import DeterministicToolRegistry
from core.input_processing import InputProcessingStage
from core.orchestrator import Orchestrator
from core.semantic_analysis import SemanticAnalysisStage


class DeterministicProcessingStage:
    """Executa ferramenta local apenas para intenções elegíveis e de baixo risco."""

    name = "deterministic_processing"

    def __init__(self, registry: DeterministicToolRegistry | None = None) -> None:
        self.registry = registry or DeterministicToolRegistry()

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        if task.risk is not None and task.risk >= 0.55:
            return task
        if task.intent not in {"calculation", "unit_conversion"}:
            return task

        text = task.normalized_text or task.original_text
        result = self.registry.execute(text)
        if result is not None:
            task.deterministic_results.append(result.to_dict())
        return task


class CognitivePipeline:
    """Pipeline local: entrada, análise, ferramentas e planejamento."""

    def __init__(self) -> None:
        self.orchestrator = Orchestrator(
            [
                InputProcessingStage(),
                SemanticAnalysisStage(CapabilityVectorizer()),
                DeterministicProcessingStage(),
                CognitivePlanningStage(),
            ]
        )

    async def run(self, text: str) -> CognitiveTask:
        return await self.orchestrator.run(CognitiveTask(original_text=text))


async def analyze_request(text: str) -> CognitiveTask:
    """Executa a análise cognitiva completa sem acesso à rede."""
    return await CognitivePipeline().run(text)
