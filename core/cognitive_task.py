"""Contrato de tarefa cognitiva compartilhado pelas camadas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Evidence:
    """Trecho de evidência com proveniência preservada."""

    source: str
    content: str
    locator: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "locator": self.locator,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            source=str(data["source"]),
            content=str(data["content"]),
            locator=data.get("locator"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class CognitiveTask:
    """Envelope versionado para entrada, análise, execução e resultado.

    difficulty, uncertainty, risk e urgency são indicadores, não probabilidades
    calibradas.
    """

    original_text: str
    task_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0"
    normalized_text: str | None = None
    intent: str | None = None
    capabilities: dict[str, float] = field(default_factory=dict)
    difficulty: float | None = None
    uncertainty: float | None = None
    risk: float | None = None
    urgency: float | None = None
    deterministic_results: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    execution_plan: list[dict[str, Any]] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    subtask_plan: list[dict[str, Any]] = field(default_factory=list)
    token_budget: int | None = None
    ram_budget_mb: int | None = None
    deadline_ms: int | None = None
    execution_trace: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Retorna uma estrutura compatível com JSON."""
        return {
            "task_id": self.task_id,
            "schema_version": self.schema_version,
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "intent": self.intent,
            "capabilities": dict(self.capabilities),
            "difficulty": self.difficulty,
            "uncertainty": self.uncertainty,
            "risk": self.risk,
            "urgency": self.urgency,
            "deterministic_results": list(self.deterministic_results),
            "evidence": [item.to_dict() for item in self.evidence],
            "execution_plan": list(self.execution_plan),
            "subtasks": list(self.subtasks),
            "subtask_plan": list(self.subtask_plan),
            "token_budget": self.token_budget,
            "ram_budget_mb": self.ram_budget_mb,
            "deadline_ms": self.deadline_ms,
            "execution_trace": list(self.execution_trace),
            "result": self.result,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveTask:
        """Reconstrói uma tarefa serializada."""
        return cls(
            task_id=str(data["task_id"]),
            schema_version=str(data.get("schema_version", "1.0")),
            original_text=str(data.get("original_text", "")),
            normalized_text=data.get("normalized_text"),
            intent=data.get("intent"),
            capabilities={str(k): float(v) for k, v in data.get("capabilities", {}).items()},
            difficulty=data.get("difficulty"),
            uncertainty=data.get("uncertainty"),
            risk=data.get("risk"),
            urgency=data.get("urgency"),
            deterministic_results=list(data.get("deterministic_results", [])),
            evidence=[Evidence.from_dict(item) for item in data.get("evidence", [])],
            execution_plan=list(data.get("execution_plan", [])),
            subtasks=list(data.get("subtasks", [])),
            subtask_plan=list(data.get("subtask_plan", [])),
            token_budget=data.get("token_budget"),
            ram_budget_mb=data.get("ram_budget_mb"),
            deadline_ms=data.get("deadline_ms"),
            execution_trace=list(data.get("execution_trace", [])),
            result=data.get("result"),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
        )
