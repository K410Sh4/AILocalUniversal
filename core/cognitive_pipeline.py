"""Composição do pipeline cognitivo inicial."""

from __future__ import annotations

from core.capability_vectorizer import CapabilityVectorizer
from core.cognitive_planner import CognitivePlanningStage
from core.cognitive_task import CognitiveTask
from core.deterministic_tools import DeterministicToolRegistry
from core.input_processing import InputProcessingStage
from core.orchestrator import Orchestrator
from core.semantic_analysis import SemanticAnalysisStage
from core.task_decomposer import TaskDecompositionStage


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
    """Pipeline local com execução determinística opcional para roteamento externo."""

    def __init__(
        self,
        *,
        execute_deterministic: bool = True,
        tools: DeterministicToolRegistry | None = None,
    ) -> None:
        stages = [
            InputProcessingStage(),
            SemanticAnalysisStage(CapabilityVectorizer()),
            TaskDecompositionStage(),
        ]
        if execute_deterministic:
            stages.append(DeterministicProcessingStage(tools))
        stages.append(CognitivePlanningStage())
        self.orchestrator = Orchestrator(stages)

    async def run(self, text: str) -> CognitiveTask:
        return await self.orchestrator.run(CognitiveTask(original_text=text))


async def analyze_request(
    text: str,
    *,
    execute_deterministic: bool = True,
) -> CognitiveTask:
    """Analisa uma solicitação; execução local pode ser delegada ao roteador K.IA."""
    return await CognitivePipeline(
        execute_deterministic=execute_deterministic
    ).run(text)
