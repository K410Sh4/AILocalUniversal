"""Orquestrador sequencial mínimo para etapas assíncronas."""

from __future__ import annotations

from typing import Protocol

from core.cognitive_task import CognitiveTask, TaskStatus
from core.execution_trace import ExecutionTrace


class TaskStage(Protocol):
    """Contrato de uma etapa do pipeline."""

    name: str

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        ...


class Orchestrator:
    """Executa estágios registrados e anexa um trace à tarefa.

    Planejamento, paralelismo, roteamento adaptativo e retry ainda não fazem
    parte desta fundação.
    """

    def __init__(self, stages: list[TaskStage] | None = None) -> None:
        self._stages: list[TaskStage] = list(stages or [])

    def add_stage(self, stage: TaskStage) -> None:
        self._stages.append(stage)

    async def run(self, task: CognitiveTask) -> CognitiveTask:
        trace = ExecutionTrace()
        task.status = TaskStatus.RUNNING
        trace.add("orchestrator", "started", {"stage_count": len(self._stages)})

        for stage in self._stages:
            trace.add(stage.name, "started")
            try:
                updated = await stage.process(task)
                if updated.task_id != task.task_id:
                    raise ValueError("Uma etapa não pode trocar o task_id.")
                task = updated
                trace.add(stage.name, "completed")
            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = {"error": str(exc), "failed_stage": stage.name}
                trace.add(
                    stage.name,
                    "failed",
                    {"error_type": type(exc).__name__, "error": str(exc)},
                )
                task.execution_trace.extend(trace.to_list())
                return task

        task.status = TaskStatus.COMPLETED
        trace.add("orchestrator", "completed")
        task.execution_trace.extend(trace.to_list())
        return task
