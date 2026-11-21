import pytest

from core.cognitive_task import CognitiveTask, TaskStatus
from core.orchestrator import Orchestrator


class NormalizeStage:
    name = "normalize"

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        task.normalized_text = task.original_text.strip().lower()
        return task


class FailingStage:
    name = "failing"

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        raise RuntimeError("falha simulada")


@pytest.mark.asyncio
async def test_orchestrator_runs_stage_and_records_trace() -> None:
    result = await Orchestrator([NormalizeStage()]).run(
        CognitiveTask(original_text="  Olá  ")
    )

    assert result.status is TaskStatus.COMPLETED
    assert result.normalized_text == "olá"
    assert any(event["stage"] == "normalize" for event in result.execution_trace)


@pytest.mark.asyncio
async def test_orchestrator_records_stage_failure() -> None:
    result = await Orchestrator([FailingStage()]).run(CognitiveTask(original_text="teste"))

    assert result.status is TaskStatus.FAILED
    assert result.result["failed_stage"] == "failing"
