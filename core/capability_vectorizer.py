"""Taxonomia inicial de capacidades; embeddings/classificação ainda não implementados."""

from __future__ import annotations

import dataclasses


CAPABILITY_DIMENSIONS: tuple[str, ...] = (
    "general_conversation",
    "programming",
    "math_logic",
    "science_knowledge",
    "rag_external_memory",
    "vision_multimodal",
    "writing_creativity",
    "external_research",
    "tool_use",
    "planning",
    "verification",
    "interdisciplinary",
)


@dataclasses.dataclass(slots=True)
class CapabilityVector:
    """Pontuações entre 0 e 1 para dimensões conhecidas."""

    scores: dict[str, float] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.scores) - set(CAPABILITY_DIMENSIONS)
        if unknown:
            raise ValueError(f"Dimensões desconhecidas: {', '.join(sorted(unknown))}")
        if any(not 0.0 <= value <= 1.0 for value in self.scores.values()):
            raise ValueError("Pontuações devem estar entre 0.0 e 1.0.")

    def to_dict(self) -> dict[str, float]:
        return {name: self.scores.get(name, 0.0) for name in CAPABILITY_DIMENSIONS}
