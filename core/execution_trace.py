"""Registro estruturado de eventos de execução."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class TraceEvent:
    stage: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionTrace:
    events: list[TraceEvent] = field(default_factory=list)

    def add(
        self,
        stage: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(stage=stage, status=status, details=details or {})
        self.events.append(event)
        return event

    def to_list(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
