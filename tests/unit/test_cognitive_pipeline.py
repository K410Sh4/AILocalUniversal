import pytest

from core.cognitive_pipeline import analyze_request
from core.cognitive_task import TaskStatus


@pytest.mark.asyncio
async def test_pipeline_routes_simple_calculation_to_local_tool() -> None:
    task = await analyze_request("Quanto é 12 * (3 + 2)?")

    assert task.status is TaskStatus.COMPLETED
    assert task.intent == "calculation"
    assert task.result is not None
    assert task.result["route"] == "deterministic_only"
    assert task.result["tool"] == "calculator"
    assert task.result["content"] == "Resultado: 60"
    assert any(event["stage"] == "deterministic_processing" for event in task.execution_trace)


@pytest.mark.asyncio
async def test_pipeline_routes_unit_conversion_to_local_tool() -> None:
    task = await analyze_request("Converta 5 km para m")

    assert task.result is not None
    assert task.result["route"] == "deterministic_only"
    assert task.result["tool"] == "unit_converter"
    assert task.result["content"] == "5 km = 5000 m"


@pytest.mark.asyncio
async def test_pipeline_routes_explanation_to_model() -> None:
    task = await analyze_request("Explique como funcionam as integrais definidas.")

    assert task.status is TaskStatus.COMPLETED
    assert task.result is None
    assert task.execution_plan[0]["route"] == "llm_assisted"


@pytest.mark.asyncio
async def test_high_risk_marker_prevents_deterministic_shortcut() -> None:
    task = await analyze_request("Calcule a dosagem: 2 / 3")

    assert task.risk is not None and task.risk > 0.5
    assert task.result is None
    assert task.execution_plan[0]["route"] == "llm_assisted"
    assert task.execution_plan[1]["reason"] == "risk_marker_requires_model_review"


@pytest.mark.asyncio
async def test_pipeline_decomposes_explicit_bullet_list() -> None:
    task = await analyze_request(
        "Explique integrais e aborde:\n- definição\n- exemplo\n- aplicações"
    )

    assert len(task.subtask_plan) == 3
    assert task.subtasks == [item["id"] for item in task.subtask_plan]
    assert all(item["intent"] for item in task.subtask_plan)
    assert task.execution_plan[1]["component"] == "subtask_plan"
    assert task.execution_plan[1]["execution"] == "single_model_structured_response"


@pytest.mark.asyncio
async def test_pipeline_decomposes_explicit_sequence_with_dependencies() -> None:
    task = await analyze_request("Calcule 2 + 2 e depois explique o resultado.")

    assert len(task.subtask_plan) == 2
    assert task.subtask_plan[1]["depends_on"] == [task.subtask_plan[0]["id"]]
    assert task.subtask_plan[0]["intent"] == "calculation"
    assert task.execution_plan[0]["route"] == "llm_assisted"


@pytest.mark.asyncio
async def test_pipeline_ignores_bullets_inside_fenced_code() -> None:
    task = await analyze_request(
        "Explique este exemplo:\n```text\n- item de código\n- outro item\n```"
    )

    assert task.subtask_plan == []


@pytest.mark.asyncio
async def test_pipeline_can_defer_deterministic_execution_to_kia_runtime() -> None:
    task = await analyze_request(
        "Calcule 2 + 2.",
        execute_deterministic=False,
    )

    assert task.intent == "calculation"
    assert task.deterministic_results == []
    assert task.result is None
    assert task.execution_plan[0]["route"] == "llm_assisted"
