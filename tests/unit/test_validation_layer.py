from core.cognitive_task import CognitiveTask
from core.deterministic_tools import DeterministicToolRegistry
from core.validation_layer import ValidationLayer


def _calculation_result():
    tool_result = DeterministicToolRegistry().execute("Calcule 2 + 2")
    assert tool_result is not None
    return tool_result


def test_deterministic_response_is_replayed_before_acceptance() -> None:
    tool_result = _calculation_result()
    task = CognitiveTask(
        original_text="Calcule 2 + 2",
        normalized_text="Calcule 2 + 2",
        deterministic_results=[tool_result.to_dict()],
        result={
            "route": "deterministic_only",
            "tool": tool_result.name,
            "content": tool_result.content,
            "success": tool_result.success,
            "value": tool_result.value,
        },
    )

    report = ValidationLayer().validate_deterministic_response(task)

    assert report["status"] == "passed"
    assert report["structural_status"] == "passed"
    assert report["factual_status"] == "verified_deterministic"
    assert report["summary"]["checks_failed"] == 0


def test_deterministic_response_with_tampered_value_is_blocked() -> None:
    tool_result = _calculation_result()
    task = CognitiveTask(
        original_text="Calcule 2 + 2",
        normalized_text="Calcule 2 + 2",
        deterministic_results=[tool_result.to_dict()],
        result={
            "route": "deterministic_only",
            "tool": tool_result.name,
            "content": tool_result.content,
            "success": True,
            "value": 5,
        },
    )

    report = ValidationLayer().validate_deterministic_response(task)

    assert report["status"] == "failed"
    assert any(issue["code"] == "deterministic_response_mismatch" for issue in report["issues"])


def test_deterministic_subtask_is_reproduced_and_verified() -> None:
    tool_result = _calculation_result()
    task = CognitiveTask(
        original_text="Calcule 2 + 2",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Calcule 2 + 2",
                "depends_on": [],
                "status": "validating",
                "execution_kind": "deterministic_tool",
                "result": {
                    "tool": tool_result.name,
                    "content": tool_result.content,
                    "success": tool_result.success,
                    "value": tool_result.value,
                },
            }
        ],
    )

    report = ValidationLayer().validate_subtask(task, task.subtask_plan[0])

    assert report["status"] == "passed"
    assert report["factual_status"] == "verified_deterministic"


def test_llm_subtask_requires_factual_review_even_when_structure_is_valid() -> None:
    task = CognitiveTask(
        original_text="Explique integrais",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Defina integral",
                "depends_on": [],
                "status": "validating",
            }
        ],
    )
    item = task.subtask_plan[0]
    item.update(
        {
            "execution_kind": "llm",
            "result": {"content": "Uma integral mede acumulação.", "model": "qwen3:4b"},
        }
    )

    report = ValidationLayer().validate_subtask(task, item)

    assert report["status"] == "needs_review"
    assert report["structural_status"] == "passed"
    assert report["factual_status"] == "not_independently_verified"
    assert any(
        issue["code"] == "llm_output_not_independently_verified"
        for issue in report["issues"]
    )


def test_final_validation_checks_subtask_coverage_and_marks_llm_synthesis_unverified() -> None:
    task = CognitiveTask(
        original_text="Explique um tema",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Definição",
                "depends_on": [],
                "status": "completed",
                "execution_kind": "llm",
                "result": {"content": "Definição", "model": "qwen3:4b"},
                "validation_report": {
                    "status": "needs_review",
                    "issues": [
                        {
                            "code": "llm_output_not_independently_verified",
                            "severity": "warning",
                            "message": "Não verificada.",
                        }
                    ],
                },
            }
        ],
    )

    report = ValidationLayer().validate_execution(task, "Síntese final.")

    assert report["status"] == "needs_review"
    assert report["structural_status"] == "passed"
    assert report["factual_status"] == "not_independently_verified"
    assert report["summary"]["checked_subtasks"] == 1


def test_final_validation_fails_when_subtask_result_is_missing() -> None:
    task = CognitiveTask(
        original_text="Explique um tema",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Definição",
                "depends_on": [],
                "status": "pending",
            }
        ],
    )

    report = ValidationLayer().validate_execution(task, "Síntese sem resultado.")

    assert report["status"] == "failed"
    assert report["structural_status"] == "failed"
    assert any(issue["code"] == "subtask_coverage_incomplete" for issue in report["issues"])


def test_reproduced_deterministic_error_is_a_validated_response() -> None:
    tool_result = DeterministicToolRegistry().execute("Calcule 1 / 0")
    assert tool_result is not None
    task = CognitiveTask(
        original_text="Calcule 1 / 0",
        normalized_text="Calcule 1 / 0",
        deterministic_results=[tool_result.to_dict()],
        result={
            "route": "deterministic_only",
            "tool": tool_result.name,
            "content": tool_result.content,
            "success": tool_result.success,
            "value": tool_result.value,
        },
    )

    report = ValidationLayer().validate_deterministic_response(task)

    assert report["status"] == "passed"
    assert report["factual_status"] == "verified_deterministic"


def test_missing_subtask_validation_report_fails_final_gate() -> None:
    task = CognitiveTask(
        original_text="Explique um tema",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Definição",
                "depends_on": [],
                "status": "completed",
                "execution_kind": "llm",
                "result": {"content": "Definição", "model": "qwen3:4b"},
            }
        ],
    )

    report = ValidationLayer().validate_execution(task, "Síntese final.")

    assert report["status"] == "failed"
    assert any(
        check["name"] == "subtask_validation" and check["status"] == "failed"
        for check in report["checks"]
    )


def test_chat_response_reports_completeness_without_claiming_factual_verification() -> None:
    task = CognitiveTask(
        original_text="Explique um tema",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Definição",
                "required": True,
                "weight": 1.0,
                "status": "completed",
                "result": {"content": "Definição"},
            },
            {
                "id": "s2",
                "order": 2,
                "text": "Aplicações",
                "required": True,
                "weight": 3.0,
                "status": "completed",
                "result": {"content": "Aplicações"},
            },
        ],
    )

    report = ValidationLayer().validate_chat_response(task, "Resposta completa.")

    assert report["status"] == "needs_review"
    assert report["completeness"]["status"] == "passed"
    assert report["completeness"]["weighted_score"] == 1.0
    assert report["factual_status"] == "not_independently_verified"


def test_chat_response_fails_when_a_mandatory_requirement_is_missing() -> None:
    task = CognitiveTask(
        original_text="Explique um tema",
        subtask_plan=[
            {
                "id": "s1",
                "order": 1,
                "text": "Definição",
                "required": True,
                "weight": 1.0,
                "status": "completed",
                "result": {"content": "Definição"},
            },
            {
                "id": "s2",
                "order": 2,
                "text": "Aplicações",
                "required": True,
                "weight": 3.0,
                "status": "pending",
            },
        ],
    )

    report = ValidationLayer().validate_chat_response(task, "Resposta parcial.")

    assert report["status"] == "failed"
    assert report["completeness"]["status"] == "incomplete"
    assert report["completeness"]["weighted_score"] == 0.25
    assert report["summary"]["checks_failed"] == 1


def test_chat_response_without_declared_requirements_does_not_invent_completeness() -> None:
    task = CognitiveTask(original_text="Olá")

    report = ValidationLayer().validate_chat_response(task, "Olá! Como posso ajudar?")

    assert report["completeness"]["status"] == "not_assessed"
    assert report["completeness"]["weighted_score"] is None
    assert report["factual_status"] == "not_independently_verified"


def test_chat_response_rejects_invalid_completeness_threshold() -> None:
    task = CognitiveTask(original_text="Olá")

    import pytest

    with pytest.raises(ValueError, match="completeness_threshold"):
        ValidationLayer().validate_chat_response(
            task,
            "Resposta.",
            completeness_threshold=1.1,
        )
