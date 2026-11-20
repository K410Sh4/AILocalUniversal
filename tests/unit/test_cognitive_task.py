from core.cognitive_task import CognitiveTask, Evidence, TaskStatus


def test_task_round_trip_preserves_fields() -> None:
    task = CognitiveTask(
        original_text="Compare dois valores",
        normalized_text="compare dois valores",
        capabilities={"math_logic": 0.8},
        evidence=[Evidence(source="manual.pdf", content="Trecho", locator="p. 3")],
        subtask_plan=[
            {
                "id": "task-1:subtask:01",
                "order": 1,
                "text": "Compare valores",
                "intent": "comparison",
                "capabilities": {"math_logic": 0.0},
                "depends_on": [],
                "strategy": "independent",
                "status": "pending",
            }
        ],
        status=TaskStatus.RUNNING,
    )
    restored = CognitiveTask.from_dict(task.to_dict())

    assert restored.task_id == task.task_id
    assert restored.original_text == task.original_text
    assert restored.capabilities == task.capabilities
    assert restored.evidence[0].locator == "p. 3"
    assert restored.subtask_plan[0]["intent"] == "comparison"
    assert restored.status is TaskStatus.RUNNING



def test_legacy_task_data_without_subtask_plan_is_compatible() -> None:
    restored = CognitiveTask.from_dict(
        {
            "task_id": "legacy-task",
            "original_text": "Olá",
            "status": "completed",
        }
    )

    assert restored.subtask_plan == []
