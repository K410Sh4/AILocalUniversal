"""Version-1 access-trace contracts for MoE expert-cache simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable


class TraceFormatError(ValueError):
    """Raised when an expert access trace is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ExpertAccess:
    """One expert-weight access in the order observed by the runtime.

    Multiple records may share one token_index to represent top-k routing.
    expert_id should be globally unique within a model, preferably namespaced
    by layer (for example: "layers.12.experts.7").
    """

    token_index: int
    expert_id: str
    size_bytes: int

    def __post_init__(self) -> None:
        if isinstance(self.token_index, bool) or not isinstance(self.token_index, int):
            raise ValueError("token_index precisa ser um inteiro não negativo.")
        if self.token_index < 0:
            raise ValueError("token_index precisa ser um inteiro não negativo.")
        if not isinstance(self.expert_id, str) or not self.expert_id.strip():
            raise ValueError("expert_id precisa ser uma string não vazia.")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise ValueError("size_bytes precisa ser um inteiro positivo.")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes precisa ser um inteiro positivo.")


@dataclass(frozen=True, slots=True)
class AccessTrace:
    """Ordered sequence of expert accesses from a single model execution."""

    events: tuple[ExpertAccess, ...]

    def __post_init__(self) -> None:
        normalized = tuple(self.events)
        if any(not isinstance(event, ExpertAccess) for event in normalized):
            raise TypeError("events deve conter somente ExpertAccess.")
        previous_token = -1
        sizes: dict[str, int] = {}
        for event in normalized:
            if event.token_index < previous_token:
                raise ValueError("Os eventos precisam estar ordenados por token_index.")
            previous_token = event.token_index
            previous_size = sizes.setdefault(event.expert_id, event.size_bytes)
            if previous_size != event.size_bytes:
                raise ValueError(
                    f"O tamanho do especialista {event.expert_id!r} mudou no mesmo trace."
                )
        object.__setattr__(self, "events", normalized)

    @property
    def token_count(self) -> int:
        """Number of distinct token indices represented in this trace."""
        return len({event.token_index for event in self.events})

    @property
    def expert_sizes(self) -> dict[str, int]:
        """Stable expert size mapping for this trace."""
        return {event.expert_id: event.size_bytes for event in self.events}

    @property
    def has_uniform_expert_sizes(self) -> bool:
        """Whether Belady MIN's equal-sized-object assumption is satisfied."""
        return len(set(self.expert_sizes.values())) <= 1

    @classmethod
    def from_jsonl(cls, text: str) -> AccessTrace:
        """Parse one JSON object per expert access.

        Required keys: token_index (integer), expert_id (string), size_bytes
        (positive integer). Blank lines are ignored; comments are not accepted.
        """
        events: list[ExpertAccess] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TraceFormatError(
                    f"Linha {line_number}: JSON inválido: {exc.msg}."
                ) from exc
            if not isinstance(payload, dict):
                raise TraceFormatError(
                    f"Linha {line_number}: cada registro precisa ser um objeto JSON."
                )
            try:
                events.append(
                    ExpertAccess(
                        token_index=payload["token_index"],
                        expert_id=payload["expert_id"],
                        size_bytes=payload["size_bytes"],
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise TraceFormatError(
                    f"Linha {line_number}: registro de acesso inválido: {exc}"
                ) from exc
        try:
            return cls(tuple(events))
        except (TypeError, ValueError) as exc:
            raise TraceFormatError(f"Trace inconsistente: {exc}") from exc

    @classmethod
    def from_records(cls, records: Iterable[ExpertAccess]) -> AccessTrace:
        """Build a trace from already validated access records."""
        return cls(tuple(records))
