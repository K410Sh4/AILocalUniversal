import asyncio

import pytest

from core.cognitive_pipeline import analyze_request
from core.cognitive_task import CognitiveTask, TaskStatus
from core.task_executor import CognitiveTaskExecutor
from engines.base import EngineAdapter, EngineEvent, EngineRequest


class RecordingEngine(EngineAdapter):
    name = "recording"

    def __init__(self, *, fail_on: str | None = None, cancel: bool = False) -> None:
        self.requests: list[EngineRequest] = []
        self.fail_on = fail_on
        self.cancel = cancel
        self.active = 0
        self.max_active = 0

    async def health(self) -> bool:
        return True

    async def list_models(self):
        return []

    async def stream_chat(self, request: EngineRequest):
        self.requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0)
            if self.cancel:
                raise asyncio.CancelledError()
            prompt = str(request.messages[-1].get("content", ""))
            if self.fail_on and self.fail_on in prompt:
                raise RuntimeError("falha simulada")
            if "SÍNTESE FINAL" in prompt:
                answer = "Resposta sintetizada."
            else:
                answer = f"Resultado intermediário para {prompt[:45]}"
            yield EngineEvent(event_type="token", content=answer)
            yield EngineEvent(
                event_type="done",
                done=True,
                metadata={"model": request.model, "eval_count": 7, "eval_duration": 1000},
            )
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_executor_runs_independent_subtasks_sequentially_then_synthesizes() -> None:
    task = await analyze_request("Explique o tema:\n- definição\n- aplicações")
    engine = RecordingEngine()
    updates: list[dict] = []
    tokens: list[str] = []

    metadata = await CognitiveTaskExecutor(engine).execute(
        task,
        model="fake:1b",
        context_messages=[{"role": "user", "content": task.original_text}],
        on_update=updates.append,
        on_token=tokens.append,
    )

    assert len(engine.requests) == 3
    assert engine.max_active == 1
    assert all(item["status"] == "completed" for item in task.subtask_plan)
    assert all(
        item["verification_status"] == "not_independently_verified"
        for item in task.subtask_plan
    )
    assert task.status is TaskStatus.COMPLETED
    assert task.result is not None
    assert task.result["content"] == "Resposta sintetizada."
    assert task.result["subtask_count"] == 2
    assert "".join(tokens) == "Resposta sintetizada."
    assert metadata["model"] == "fake:1b"
    assert any(event["status"] == "synthesis_started" for event in task.execution_trace)
    assert updates[-1]["status"] == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_executor_uses_local_calculation_for_dependency_then_model_and_synthesis() -> None:
    task = await analyze_request("Calcule 2 + 2 e depois explique o resultado.")
    engine = RecordingEngine()

    await CognitiveTaskExecutor(engine).execute(
        task,
        model="fake:1b",
        context_messages=[{"role": "user", "content": task.original_text}],
    )

    assert len(engine.requests) == 2
    first, second = task.subtask_plan
    assert first["execution_kind"] == "deterministic_tool"
    assert first["result"]["content"] == "Resultado: 4"
    assert second["execution_kind"] == "llm"
    assert second["depends_on"] == [first["id"]]
    assert "Resultado: 4" in engine.requests[0].messages[-1]["content"]
    assert task.result is not None
    assert task.result["subtask_count"] == 2


@pytest.mark.asyncio
async def test_executor_marks_remaining_subtasks_blocked_after_failure() -> None:
    task = await analyze_request("Explique o tema:\n- primeira parte\n- segunda parte")
    engine = RecordingEngine(fail_on="Execute somente a subtarefa 1 de 2")

    with pytest.raises(RuntimeError, match="falha simulada"):
        await CognitiveTaskExecutor(engine).execute(
            task,
            model="fake:1b",
            context_messages=[{"role": "user", "content": task.original_text}],
        )

    assert task.status is TaskStatus.FAILED
    assert task.subtask_plan[0]["status"] == "failed"
    assert task.subtask_plan[1]["status"] == "blocked"
    assert task.result is not None
    assert task.result["failed_subtask_id"] == task.subtask_plan[0]["id"]


@pytest.mark.asyncio
async def test_executor_rejects_cyclic_dependencies_before_generation() -> None:
    task = CognitiveTask(
        original_text="Pedido composto",
        subtask_plan=[
            {"id": "a", "order": 1, "text": "A", "depends_on": ["b"], "status": "pending"},
            {"id": "b", "order": 2, "text": "B", "depends_on": ["a"], "status": "pending"},
        ],
    )
    engine = RecordingEngine()

    with pytest.raises(ValueError, match="cíclica"):
        await CognitiveTaskExecutor(engine).execute(
            task,
            model="fake:1b",
            context_messages=[{"role": "user", "content": task.original_text}],
        )

    assert not engine.requests
    assert task.status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_executor_rejects_missing_dependency() -> None:
    task = CognitiveTask(
        original_text="Pedido composto",
        subtask_plan=[
            {
                "id": "a",
                "order": 1,
                "text": "A",
                "depends_on": ["inexistente"],
                "status": "pending",
            },
            {"id": "b", "order": 2, "text": "B", "depends_on": [], "status": "pending"},
        ],
    )

    with pytest.raises(ValueError, match="Dependência inexistente"):
        await CognitiveTaskExecutor(RecordingEngine()).execute(
            task,
            model="fake:1b",
            context_messages=[{"role": "user", "content": task.original_text}],
        )
    assert task.status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_executor_marks_active_subtask_cancelled_and_skips_remaining() -> None:
    task = await analyze_request("Explique o tema:\n- primeira parte\n- segunda parte")

    with pytest.raises(asyncio.CancelledError):
        await CognitiveTaskExecutor(RecordingEngine(cancel=True)).execute(
            task,
            model="fake:1b",
            context_messages=[{"role": "user", "content": task.original_text}],
        )

    assert task.status is TaskStatus.CANCELLED
    assert task.subtask_plan[0]["status"] == "cancelled"
    assert task.subtask_plan[1]["status"] == "skipped"
