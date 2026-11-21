"""Deterministic, bounded NeuralStem differentiation simulator (research prototype).
This is a computational abstraction, not a biological cell model or a BA runtime.
Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Fate(str, Enum):  # noqa: UP042 - preserve str/Enum compatibility on supported runtimes.
    MEMORY = "memory"
    ASSOCIATION = "association"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class DevelopmentGenome:
    fate_affinity: tuple[tuple[float, float, float], ...]
    differentiation_threshold: float = 0.35
    self_renewal_bias: float = 0.25
    activity_sensitivity: float = 0.2
    resource_cost: float = 1.0
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported NeuralDNA schema version")
        if len(self.fate_affinity) != len(Fate):
            raise ValueError("fate_affinity must define exactly three fates")
        if any(len(row) != 3 for row in self.fate_affinity):
            raise ValueError("each fate must define three niche affinities")
        values = [v for row in self.fate_affinity for v in row]
        values += [
            self.differentiation_threshold,
            self.self_renewal_bias,
            self.activity_sensitivity,
        ]
        if any(not math.isfinite(v) or not 0.0 <= v <= 1.0 for v in values):
            raise ValueError("genome loci must be finite values in [0, 1]")
        if not math.isfinite(self.resource_cost) or self.resource_cost <= 0:
            raise ValueError("resource_cost must be finite and positive")


@dataclass(frozen=True, slots=True)
class NicheState:
    demand: tuple[float, float, float]
    activity: float = 0.5
    available_resource: float = 100.0

    def __post_init__(self) -> None:
        if len(self.demand) != 3:
            raise ValueError("demand must contain one signal per fate")
        values = (*self.demand, self.activity)
        if any(not math.isfinite(v) or not 0.0 <= v <= 1.0 for v in values):
            raise ValueError("niche signals must be finite values in [0, 1]")
        if not math.isfinite(self.available_resource) or self.available_resource < 0:
            raise ValueError("available_resource must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class NeuralStemCell:
    potency: float = 1.0
    lineage_depth: int = 0

    def __post_init__(self) -> None:
        if not math.isfinite(self.potency) or not 0.0 <= self.potency <= 1.0:
            raise ValueError("potency must be finite and in [0, 1]")
        if self.lineage_depth < 0:
            raise ValueError("lineage_depth cannot be negative")


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    differentiated: tuple[int, int, int]
    self_renewed: int
    resource_used: float
    resource_remaining: float

    @property
    def total(self) -> int:
        return sum(self.differentiated) + self.self_renewed


def _score(genome: DevelopmentGenome, niche: NicheState, fate_index: int) -> float:
    affinity = genome.fate_affinity[fate_index]
    match = sum(
        a * signal
        for a, signal in zip(affinity, niche.demand, strict=True)
    ) / 3.0
    return min(1.0, match + genome.activity_sensitivity * niche.activity)


def develop_population(
    genome: DevelopmentGenome,
    niche: NicheState,
    progenitors: Iterable[NeuralStemCell],
) -> DevelopmentResult:
    """Differentiate under niche/resource constraints; no hidden stochastic behavior."""
    cells = tuple(progenitors)
    counts = [0, 0, 0]
    renewed = 0
    spent = 0.0
    scores = [_score(genome, niche, index) for index in range(len(Fate))]
    preferred = max(range(len(Fate)), key=lambda index: (scores[index], -index))
    for cell in cells:
        below_threshold = scores[preferred] < genome.differentiation_threshold
        if cell.potency <= genome.self_renewal_bias or below_threshold:
            renewed += 1
            continue
        if spent + genome.resource_cost > niche.available_resource:
            renewed += 1
            continue
        counts[preferred] += 1
        spent += genome.resource_cost
    return DevelopmentResult(
        tuple(counts),
        renewed,
        spent,
        niche.available_resource - spent,
    )
