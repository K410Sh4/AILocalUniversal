"""Contratos versionados da Neural Adaptive Plasticity Architecture (NAPA)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from core.capability_vectorizer import CAPABILITY_DIMENSIONS


class CognitiveAreaKind(StrEnum):
    """Tipo de mecanismo ativável por uma área cognitiva."""

    DETERMINISTIC_TOOL = "deterministic_tool"
    COGNITIVE_CAPABILITY = "cognitive_capability"
    NEURAL_SPECIALIST = "neural_specialist"


@dataclass(frozen=True, slots=True)
class CognitiveArea:
    """Definição declarativa de uma área cognitiva, sem acoplar um modelo."""

    area_id: str
    name: str
    kind: CognitiveAreaKind
    description: str
    capability_dimensions: tuple[str, ...] = ()
    intents: tuple[str, ...] = ()
    anchors: tuple[str, ...] = ()
    minimum_affinity: float = 0.20

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.area_id):
            raise ValueError("area_id precisa ser um identificador snake_case.")
        if not self.name.strip() or not self.description.strip():
            raise ValueError("name e description não podem ser vazios.")
        if not isinstance(self.kind, CognitiveAreaKind):
            raise TypeError("kind precisa ser CognitiveAreaKind.")
        unknown = set(self.capability_dimensions) - set(CAPABILITY_DIMENSIONS)
        if unknown:
            raise ValueError(
                f"Dimensões desconhecidas: {', '.join(sorted(unknown))}"
            )
        if len(set(self.capability_dimensions)) != len(self.capability_dimensions):
            raise ValueError("capability_dimensions não pode conter duplicatas.")
        if len(set(self.intents)) != len(self.intents):
            raise ValueError("intents não pode conter duplicatas.")
        if len(set(self.anchors)) != len(self.anchors):
            raise ValueError("anchors não pode conter duplicatas.")
        if (
            isinstance(self.minimum_affinity, bool)
            or not isinstance(self.minimum_affinity, (int, float))
            or not isfinite(self.minimum_affinity)
            or not 0.0 <= self.minimum_affinity <= 1.0
        ):
            raise ValueError("minimum_affinity precisa estar entre 0 e 1.")

    def to_dict(self) -> dict[str, object]:
        return {
            "area_id": self.area_id,
            "name": self.name,
            "kind": self.kind.value,
            "description": self.description,
            "capability_dimensions": list(self.capability_dimensions),
            "intents": list(self.intents),
            "anchors": list(self.anchors),
            "minimum_affinity": float(self.minimum_affinity),
        }


@dataclass(frozen=True, slots=True)
class AreaActivation:
    """Ativação heurística explicável; affinity não é probabilidade."""

    area_id: str
    kind: CognitiveAreaKind
    affinity: float
    signals: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.area_id:
            raise ValueError("area_id não pode ser vazio.")
        if not isinstance(self.kind, CognitiveAreaKind):
            raise TypeError("kind precisa ser CognitiveAreaKind.")
        if (
            isinstance(self.affinity, bool)
            or not isinstance(self.affinity, (int, float))
            or not isfinite(self.affinity)
            or not 0.0 <= self.affinity <= 1.0
        ):
            raise ValueError("affinity precisa estar entre 0 e 1.")
        if not self.signals or any(not signal for signal in self.signals):
            raise ValueError("Uma ativação precisa conter sinais explicáveis.")

    def to_dict(self) -> dict[str, object]:
        return {
            "area_id": self.area_id,
            "kind": self.kind.value,
            "affinity": round(float(self.affinity), 3),
            "signals": list(self.signals),
        }


@dataclass(frozen=True, slots=True)
class NapaClassification:
    """Resultado multilabel de classificação da NAPA 1.0."""

    activations: tuple[AreaActivation, ...]
    classifier_version: str = "napa-1.0"
    method: str = "lexical_capability_intent_heuristics"

    @property
    def active_area_ids(self) -> tuple[str, ...]:
        return tuple(item.area_id for item in self.activations)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "classifier_version": self.classifier_version,
            "method": self.method,
            "score_semantics": "heuristic_affinity_not_probability",
            "active_areas": list(self.active_area_ids),
            "activations": [item.to_dict() for item in self.activations],
        }
