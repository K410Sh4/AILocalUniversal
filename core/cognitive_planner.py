"""Planejamento inicial de execução adaptativa."""

from __future__ import annotations

from core.cognitive_task import CognitiveTask


class CognitivePlanner:
    """Escolhe entre ferramenta local determinística e inferência por LLM.

    As heurísticas são políticas iniciais explícitas, não um planejador treinado.
    """

    def create_plan(self, task: CognitiveTask) -> CognitiveTask:
        deterministic = next(
            (
                result
                for result in reversed(task.deterministic_results)
                if result.get("matched")
            ),
            None,
        )
        risk = task.risk if task.risk is not None else 0.0

        if deterministic is not None and risk < 0.55:
            route = "deterministic_only"
            task.result = {
                "route": route,
                "tool": deterministic["name"],
                "content": deterministic["content"],
                "success": bool(deterministic["success"]),
                "value": deterministic.get("value"),
            }
            task.execution_plan = [
                {
                    "step": 1,
                    "component": "deterministic_tool",
                    "tool": deterministic["name"],
                    "required": True,
                },
                {
                    "step": 2,
                    "component": "local_response",
                    "required": True,
                },
            ]
        else:
            route = "llm_assisted"
            task.result = None
            reason = (
                "risk_marker_requires_model_review"
                if risk >= 0.55
                else "heuristic_analysis"
            )
            task.execution_plan = []
            next_step = 1
            if len(task.subtask_plan) > 1:
                task.execution_plan.append(
                    {
                        "step": next_step,
                        "component": "subtask_plan",
                        "strategy": task.subtask_plan[0].get("strategy", "independent"),
                        "execution": "single_model_structured_response",
                        "subtask_ids": [item["id"] for item in task.subtask_plan],
                        "required": True,
                    }
                )
                next_step += 1
            task.execution_plan.append(
                {
                    "step": next_step,
                    "component": "ollama_chat",
                    "required": True,
                    "reason": reason,
                }
            )

        difficulty = task.difficulty if task.difficulty is not None else 0.5
        task.token_budget = (
            1024 if difficulty < 0.3 else 2048 if difficulty < 0.65 else 4096
        )
        task.execution_plan.insert(
            0,
            {
                "step": 0,
                "component": "cognitive_analysis",
                "intent": task.intent,
                "route": route,
                "risk": task.risk,
                "uncertainty": task.uncertainty,
            },
        )
        return task


class CognitivePlanningStage:
    """Etapa do planejador para o Orchestrator."""

    name = "cognitive_planning"

    def __init__(self, planner: CognitivePlanner | None = None) -> None:
        self.planner = planner or CognitivePlanner()

    async def process(self, task: CognitiveTask) -> CognitiveTask:
        return self.planner.create_plan(task)
