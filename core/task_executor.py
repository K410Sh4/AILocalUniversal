"""Execução sequencial de subtarefas com dependências e síntese final."""

# ruff: noqa: I001

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.cognitive_task import CognitiveTask, TaskStatus
from core.deterministic_tools import DeterministicToolRegistry
from core.validation_layer import ValidationLayer
from engines.base import EngineAdapter, EngineRequest


TaskUpdateCallback = Callable[[dict[str, Any]], None]
TokenCallback = Callable[[str], None]
_NOT_INDEPENDENTLY_VERIFIED = "not_independently_verified"
_DETERMINISTIC_RISK_LIMIT = 0.55


class CognitiveTaskExecutor:
    """Executa subtarefas em série e sintetiza os resultados com um único modelo.

    Saídas de modelo não são consideradas verificadas independentemente. O
    paralelismo e o roteamento para múltiplos modelos não fazem parte desta etapa.
    """

    def __init__(
        self,
        engine: EngineAdapter,
        tools: DeterministicToolRegistry | None = None,
    ) -> None:
        self.engine = engine
        self.tools = tools or DeterministicToolRegistry()
        self.validator = ValidationLayer(self.tools)

    @staticmethod
    def _trace(
        task: CognitiveTask,
        stage: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        task.execution_trace.append(
            {
                "stage": stage,
                "status": status,
                "timestamp": datetime.now(UTC).isoformat(),
                "details": details or {},
            }
        )

    @staticmethod
    def _notify(task: CognitiveTask, callback: TaskUpdateCallback | None) -> None:
        if callback is not None:
            callback(copy.deepcopy(task.to_dict()))

    @staticmethod
    def _ordered_subtasks(task: CognitiveTask) -> list[dict[str, Any]]:
        """Valida IDs/dependências e devolve uma ordem topológica estável."""
        plan = task.subtask_plan
        by_id: dict[str, dict[str, Any]] = {}
        for item in plan:
            subtask_id = str(item.get("id", "")).strip()
            if not subtask_id:
                raise ValueError("Toda subtarefa precisa de um ID.")
            if subtask_id in by_id:
                raise ValueError(f"ID de subtarefa duplicado: {subtask_id}")
            by_id[subtask_id] = item

        for item in plan:
            dependencies = item.get("depends_on", [])
            if not isinstance(dependencies, list):
                raise ValueError("A lista de dependências da subtarefa é inválida.")
            for dependency in dependencies:
                if dependency not in by_id:
                    raise ValueError(
                        f"Dependência inexistente '{dependency}' na subtarefa "
                        f"{item['id']}."
                    )
                if dependency == item["id"]:
                    raise ValueError("Uma subtarefa não pode depender de si mesma.")

        ordered: list[dict[str, Any]] = []
        completed: set[str] = set()
        pending = list(plan)
        while pending:
            ready = [
                item
                for item in pending
                if set(item.get("depends_on", [])).issubset(completed)
            ]
            if not ready:
                raise ValueError("O plano de subtarefas contém uma dependência cíclica.")
            for item in ready:
                ordered.append(item)
                completed.add(str(item["id"]))
                pending.remove(item)
        return ordered

    async def _generate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        *,
        on_token: TokenCallback | None = None,
    ) -> tuple[str, dict[str, Any]]:
        chunks: list[str] = []
        metadata: dict[str, Any] = {}
        received_done = False
        request = EngineRequest(
            model=model,
            messages=messages,
            options=copy.deepcopy(options),
        )
        async for event in self.engine.stream_chat(request):
            if event.content:
                chunks.append(event.content)
                if on_token is not None:
                    on_token(event.content)
            if event.done:
                received_done = True
                metadata = dict(event.metadata)
        if not received_done:
            raise RuntimeError("A geração terminou sem o evento final da engine.")
        content = "".join(chunks).strip()
        if not content:
            raise RuntimeError("A engine concluiu a geração sem produzir conteúdo.")
        return content, metadata

    @staticmethod
    def _subtask_prompt(
        item: dict[str, Any],
        total: int,
        dependencies: list[dict[str, Any]],
    ) -> str:
        parts = [
            f"Execute somente a subtarefa {item.get('order', '?')} de {total}.",
            f"Subtarefa: {item.get('text', '')}",
            "Não responda às outras partes ainda. Produza um resultado claro e autocontido.",
        ]
        if dependencies:
            parts.append(
                "Resultados das dependências anteriores (saídas intermediárias, "
                "ainda não verificadas independentemente):"
            )
            for dependency in dependencies:
                result = dependency.get("result", {})
                content = str(result.get("content", ""))[:6000]
                parts.append(
                    f"- {dependency.get('order', '?')}. "
                    f"{dependency.get('text', '')}: {content}"
                )
        return "\n\n".join(parts)

    @staticmethod
    def _synthesis_prompt(ordered: list[dict[str, Any]]) -> str:
        parts = [
            "SÍNTESE FINAL",
            "Integre os resultados das subtarefas em uma única resposta para o pedido original.",
            "Mantenha a ordem e cubra todas as partes. Remova repetições, preserve ressalvas "
            "e indique incertezas ou divergências em vez de inventar uma reconciliação.",
            "Os resultados abaixo são saídas intermediárias e não foram verificados "
            "independentemente. Não os apresente como fatos validados por uma fonte externa.",
        ]
        for item in ordered:
            result = item.get("result", {})
            parts.append(
                f"Subtarefa {item.get('order', '?')}: {item.get('text', '')}\n"
                f"Execução: {item.get('execution_kind', 'llm')}\n"
                f"Resultado: {result.get('content', '')}"
            )
        return "\n\n".join(parts)

    async def execute(
        self,
        task: CognitiveTask,
        *,
        model: str,
        context_messages: list[dict[str, Any]],
        request_options: dict[str, Any] | None = None,
        on_update: TaskUpdateCallback | None = None,
        on_token: TokenCallback | None = None,
    ) -> dict[str, Any]:
        """Executa as subtarefas em sequência e faz uma geração final de síntese."""
        if not model.strip():
            raise ValueError("Um modelo deve ser selecionado para executar as subtarefas.")
        if len(task.subtask_plan) < 2:
            raise ValueError("O Cognitive Task Executor exige pelo menos duas subtarefas.")

        request_options = request_options or {}
        ordered: list[dict[str, Any]] = []
        current_item: dict[str, Any] | None = None
        results_by_id: dict[str, dict[str, Any]] = {}
        try:
            ordered = self._ordered_subtasks(task)
            items_by_id = {str(item["id"]): item for item in task.subtask_plan}
            for item in task.subtask_plan:
                item["status"] = "pending"
                item["verification_status"] = _NOT_INDEPENDENTLY_VERIFIED
                item.pop("result", None)
                item.pop("execution_kind", None)
                item.pop("error", None)

            next_step = max(
                (int(step.get("step", -1)) for step in task.execution_plan),
                default=-1,
            ) + 1
            task.execution_plan.append(
                {
                    "step": next_step,
                    "component": "cognitive_task_executor",
                    "strategy": "sequential",
                    "subtask_count": len(ordered),
                    "synthesis": "single_model",
                    "parallelism": 1,
                    "model": model,
                }
            )
            task.status = TaskStatus.RUNNING
            task.result = None
            self._trace(
                task,
                "task_executor",
                "started",
                {
                    "subtask_count": len(ordered),
                    "strategy": "sequential",
                    "model": model,
                },
            )
            self._notify(task, on_update)

            for index, item in enumerate(ordered, start=1):
                subtask_id = str(item["id"])
                current_item = item
                dependencies = [
                    items_by_id[str(dependency)]
                    for dependency in item.get("depends_on", [])
                ]
                unresolved = [
                    str(dependency)
                    for dependency in item.get("depends_on", [])
                    if str(dependency) not in results_by_id
                ]
                if unresolved:
                    raise RuntimeError(
                        f"Dependências não concluídas para a subtarefa {subtask_id}: "
                        + ", ".join(unresolved)
                    )

                item["status"] = "running"
                self._trace(
                    task,
                    "task_executor",
                    "subtask_started",
                    {
                        "subtask_id": subtask_id,
                        "order": index,
                        "total": len(ordered),
                        "intent": item.get("intent"),
                    },
                )
                self._notify(task, on_update)

                text = str(item.get("text", "")).strip()
                risk = task.risk if task.risk is not None else 0.0
                tool_result = None
                if risk < _DETERMINISTIC_RISK_LIMIT and item.get("intent") in {
                    "calculation",
                    "unit_conversion",
                }:
                    tool_result = self.tools.execute(text)

                if tool_result is not None and tool_result.matched:
                    if not tool_result.success:
                        raise RuntimeError(
                            f"A ferramenta {tool_result.name} falhou: {tool_result.content}"
                        )
                    execution_kind = "deterministic_tool"
                    item["result"] = {
                        "content": tool_result.content,
                        "tool": tool_result.name,
                        "success": tool_result.success,
                        "value": tool_result.value,
                    }
                    task.deterministic_results.append(tool_result.to_dict())
                else:
                    messages = copy.deepcopy(context_messages)
                    messages.append(
                        {
                            "role": "user",
                            "content": self._subtask_prompt(
                                item,
                                len(ordered),
                                dependencies,
                            ),
                        }
                    )
                    content, metadata = await self._generate(
                        model,
                        messages,
                        request_options,
                    )
                    execution_kind = "llm"
                    item["result"] = {
                        "content": content,
                        "model": model,
                        "metadata": {
                            key: metadata[key]
                            for key in (
                                "eval_count",
                                "eval_duration",
                                "prompt_eval_count",
                                "prompt_eval_duration",
                            )
                            if key in metadata
                        },
                    }

                item["execution_kind"] = execution_kind
                item["status"] = "validating"
                validation_report = self.validator.validate_subtask(task, item)
                item["validation_report"] = validation_report
                item["validation_status"] = validation_report["status"]
                task.validation_report = self.validator.progress_report(task)
                item["verification_status"] = validation_report["factual_status"]
                self._trace(
                    task,
                    "validation_layer",
                    validation_report["status"],
                    {
                        "subtask_id": subtask_id,
                        "check_count": len(validation_report["checks"]),
                        "issue_count": len(validation_report["issues"]),
                    },
                )
                if validation_report["status"] == "failed":
                    item["status"] = "failed"
                    task.validation_report = dict(validation_report)
                    self._notify(task, on_update)
                    raise RuntimeError(
                        f"Validação da subtarefa {subtask_id} falhou: "
                        + "; ".join(
                            issue["message"] for issue in validation_report["issues"]
                        )
                    )
                item["status"] = "completed"
                results_by_id[subtask_id] = item
                self._trace(
                    task,
                    "task_executor",
                    "subtask_completed",
                    {
                        "subtask_id": subtask_id,
                        "order": index,
                        "execution_kind": execution_kind,
                        "verification_status": item["verification_status"],
                    },
                )
                self._notify(task, on_update)
                current_item = None

            self._trace(
                task,
                "task_executor",
                "synthesis_started",
                {"subtask_count": len(ordered), "model": model},
            )
            self._notify(task, on_update)
            synthesis_messages = copy.deepcopy(context_messages)
            synthesis_messages.append(
                {
                    "role": "user",
                    "content": self._synthesis_prompt(ordered),
                }
            )
            final_content, synthesis_metadata = await self._generate(
                model,
                synthesis_messages,
                request_options,
                on_token=on_token,
            )
            validation_report = self.validator.validate_execution(task, final_content)
            task.validation_report = validation_report
            self._trace(
                task,
                "validation_layer",
                validation_report["status"],
                {
                    "scope": "final_execution",
                    "check_count": len(validation_report["checks"]),
                    "issue_count": len(validation_report["issues"]),
                },
            )
            if validation_report["status"] == "failed":
                raise RuntimeError(
                    "A Validation Layer bloqueou a síntese: "
                    + "; ".join(issue["message"] for issue in validation_report["issues"])
                )
            task.result = {
                "route": "llm_assisted",
                "status": "completed",
                "model": model,
                "content": final_content,
                "subtask_count": len(ordered),
                "execution_strategy": "sequential",
                "verification_status": validation_report["factual_status"],
                "validation_status": validation_report["status"],
                "synthesis_metadata": {
                    key: synthesis_metadata[key]
                    for key in (
                        "eval_count",
                        "eval_duration",
                        "prompt_eval_count",
                        "prompt_eval_duration",
                        "total_duration",
                        "load_duration",
                    )
                    if key in synthesis_metadata
                },
            }
            task.status = TaskStatus.COMPLETED
            self._trace(
                task,
                "task_executor",
                "completed",
                {
                    "subtask_count": len(ordered),
                    "synthesis_model": model,
                    "verification_status": _NOT_INDEPENDENTLY_VERIFIED,
                },
            )
            self._notify(task, on_update)
            return synthesis_metadata
        except asyncio.CancelledError:
            if current_item is not None and current_item.get("status") == "running":
                current_item["status"] = "cancelled"
            for item in task.subtask_plan:
                if item.get("status") == "pending":
                    item["status"] = "skipped"
            task.status = TaskStatus.CANCELLED
            task.validation_report = self.validator.interrupted_report(
                "cancelled",
                "A validação não foi concluída porque a execução foi cancelada.",
                str(current_item["id"]) if current_item is not None else None,
            )
            task.result = {
                "route": "llm_assisted",
                "status": "cancelled",
                "completed_subtasks": len(results_by_id),
                "subtask_count": len(task.subtask_plan),
            }
            self._trace(
                task,
                "task_executor",
                "cancelled",
                {
                    "completed_subtasks": len(results_by_id),
                    "subtask_count": len(task.subtask_plan),
                },
            )
            self._notify(task, on_update)
            raise
        except Exception as exc:
            if current_item is not None and current_item.get("status") in {"running", "validating"}:
                current_item["status"] = "failed"
                current_item["error"] = str(exc)
            if (
                not isinstance(task.validation_report, dict)
                or task.validation_report.get("status") != "failed"
            ):
                task.validation_report = self.validator.interrupted_report(
                    "failed",
                    str(exc),
                    str(current_item["id"]) if current_item is not None else None,
                )
            for item in task.subtask_plan:
                if item.get("status") == "pending":
                    item["status"] = "blocked"
            task.status = TaskStatus.FAILED
            task.result = {
                "route": "llm_assisted",
                "status": "failed",
                "error": str(exc),
                "failed_subtask_id": (
                    str(current_item["id"]) if current_item is not None else None
                ),
                "completed_subtasks": len(results_by_id),
                "subtask_count": len(task.subtask_plan),
            }
            self._trace(
                task,
                "task_executor",
                "failed",
                {
                    "error_type": type(exc).__name__,
                    "failed_subtask_id": (
                        str(current_item["id"]) if current_item is not None else None
                    ),
                },
            )
            self._notify(task, on_update)
            raise
