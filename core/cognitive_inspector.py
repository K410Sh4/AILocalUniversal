"""Projeção de leitura do CognitiveTask para inspeção, sem alterar o contrato."""

from __future__ import annotations

from typing import Any

from core.cognitive_task import CognitiveTask


def build_inspector_snapshot(task: CognitiveTask) -> dict[str, Any]:
    """Retorna uma cópia simples e somente de leitura dos dados observáveis da tarefa."""
    route = "não definida"
    for step in task.execution_plan:
        if step.get("component") == "cognitive_analysis":
            route = str(step.get("route", route))
            break

    selected_model = None
    for step in task.execution_plan:
        if step.get("component") == "model_selection":
            selected_model = step.get("model")
            break

    return {
        "task_id": task.task_id,
        "schema_version": task.schema_version,
        "status": task.status.value,
        "original_text": task.original_text,
        "normalized_text": task.normalized_text or "",
        "intent": task.intent or "não identificada",
        "route": route,
        "selected_model": selected_model,
        "metrics": {
            "difficulty": task.difficulty,
            "uncertainty": task.uncertainty,
            "risk": task.risk,
            "urgency": task.urgency,
        },
        "capabilities": [
            {"dimension": name, "score": float(score)}
            for name, score in sorted(task.capabilities.items())
        ],
        "execution_plan": [dict(step) for step in task.execution_plan],
        "subtasks": [dict(item) for item in task.subtask_plan],
        "trace": [dict(event) for event in task.execution_trace],
        "evidence": [
            {
                "citation_id": item.metadata.get("citation_id", "—"),
                "title": item.metadata.get("title", item.source),
                "source": item.source,
                "locator": item.locator or "—",
                "retrieval_sources": list(item.metadata.get("retrieval_sources", [])),
            }
            for item in task.evidence
        ],
        "deterministic_results": [
            dict(result) for result in task.deterministic_results
        ],
        "result": dict(task.result) if isinstance(task.result, dict) else None,
        "validation_report": (
            dict(task.validation_report)
            if isinstance(task.validation_report, dict)
            else None
        ),
    }
