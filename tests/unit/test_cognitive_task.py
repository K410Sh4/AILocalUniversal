from core.cognitive_task import CognitiveTask, Evidence, TaskStatus


def test_task_round_trip_preserves_fields() -> None:
    task = CognitiveTask(
        original_text="Compare dois valores",
        normalized_text="compare dois valores",
        capabilities={"math_logic": 0.8},
        evidence=[Evidence(source="manual.pdf", content="Trecho", locator="p. 3")],
        status=TaskStatus.RUNNING,
    )
    restored = CognitiveTask.from_dict(task.to_dict())

    assert restored.task_id == task.task_id
    assert restored.original_text == task.original_text
    assert restored.capabilities == task.capabilities
    assert restored.evidence[0].locator == "p. 3"
    assert restored.status is TaskStatus.RUNNING
