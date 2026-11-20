import pytest

from core.cognitive_inspector import build_inspector_snapshot
from core.cognitive_pipeline import analyze_request


@pytest.mark.asyncio
async def test_inspector_snapshot_exposes_real_cognitive_pipeline_data() -> None:
    task = await analyze_request(
        "Explique integrais e aborde:\n- definição\n- exemplo\n- aplicações"
    )
    snapshot = build_inspector_snapshot(task)

    assert snapshot["task_id"] == task.task_id
    assert snapshot["intent"] == task.intent
    assert snapshot["route"] == "llm_assisted"
    assert len(snapshot["capabilities"]) == 12
    assert len(snapshot["subtasks"]) == 3
    assert snapshot["trace"] == task.execution_trace
    assert snapshot["status"] == "completed"


def test_inspector_snapshot_shows_unset_metrics_as_none() -> None:
    from core.cognitive_task import CognitiveTask

    snapshot = build_inspector_snapshot(CognitiveTask(original_text="Olá"))

    assert snapshot["metrics"]["risk"] is None
    assert snapshot["selected_model"] is None
    assert snapshot["subtasks"] == []


def test_inspector_snapshot_includes_selected_model_and_runtime_trace() -> None:
    from core.cognitive_task import CognitiveTask

    task = CognitiveTask(original_text="Explique integrais")
    task.execution_plan = [
        {"step": 0, "component": "cognitive_analysis", "route": "llm_assisted"},
        {"step": 1, "component": "model_selection", "model": "qwen3:4b", "mode": "auto"},
    ]
    task.execution_trace.append(
        {
            "stage": "ollama_chat",
            "status": "started",
            "timestamp": "2026-11-20T12:00:00+00:00",
            "details": {"model": "qwen3:4b"},
        }
    )

    snapshot = build_inspector_snapshot(task)

    assert snapshot["selected_model"] == "qwen3:4b"
    assert snapshot["trace"][-1]["stage"] == "ollama_chat"


def test_inspector_snapshot_includes_validation_report() -> None:
    from core.cognitive_task import CognitiveTask

    task = CognitiveTask(
        original_text="Calcule 2 + 2",
        validation_report={
            "status": "passed",
            "structural_status": "passed",
            "factual_status": "verified_deterministic",
            "checks": [],
            "issues": [],
        },
    )

    snapshot = build_inspector_snapshot(task)

    assert snapshot["validation_report"]["status"] == "passed"
