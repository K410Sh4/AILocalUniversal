"""Regional feedback-regulated NeuralStem lineage simulator.
Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
from typing import Iterable
from .development import DevelopmentGenome, Fate, NeuralStemCell

@dataclass(frozen=True, slots=True)
class RegionalNiche:
    region_id: str
    demand: tuple[float, float, float]
    activity: float
    available_resource: float
    capacity: int
    def __post_init__(self) -> None:
        if not self.region_id:
            raise ValueError("region_id cannot be empty")
        if len(self.demand) != len(Fate):
            raise ValueError("demand must define exactly three fate signals")
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in (*self.demand, self.activity)):
            raise ValueError("niche signals must be finite values in [0, 1]")
        if not math.isfinite(self.available_resource) or self.available_resource < 0:
            raise ValueError("available_resource must be finite and non-negative")
        if self.capacity < 0:
            raise ValueError("capacity must be non-negative")

@dataclass(frozen=True, slots=True)
class LineagePolicy:
    activation_rate: float = 0.7
    activation_half_saturation: float = 0.25
    crowding_feedback: float = 0.8
    base_self_renewal: float = 0.55
    homeostatic_self_renewal: float = 0.25
    differentiation_pressure: float = 0.25
    potency_decay: float = 0.98
    max_divisions_per_step: int | None = None
    max_lineage_depth: int = 32
    def __post_init__(self) -> None:
        values = (self.activation_rate, self.activation_half_saturation, self.crowding_feedback,
                  self.base_self_renewal, self.homeostatic_self_renewal,
                  self.differentiation_pressure, self.potency_decay)
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError("lineage policy values must be finite and in [0, 1]")
        if self.activation_half_saturation <= 0:
            raise ValueError("activation_half_saturation must be positive")
        if self.max_divisions_per_step is not None and self.max_divisions_per_step < 0:
            raise ValueError("max_divisions_per_step must be non-negative")
        if self.max_lineage_depth < 0:
            raise ValueError("max_lineage_depth must be non-negative")

@dataclass(frozen=True, slots=True)
class RegionalStepResult:
    region_id: str
    progenitors: tuple[NeuralStemCell, ...]
    differentiated: tuple[int, int, int]
    activated: int
    divisions: int
    resource_used: float
    resource_remaining: float
    activation_probability: float
    self_renewal_probability: float
    @property
    def differentiated_total(self) -> int:
        return sum(self.differentiated)

def _fate_index(genome: DevelopmentGenome, demand: tuple[float, float, float]) -> int:
    scores = tuple(sum(a*s for a, s in zip(row, demand, strict=True))/3 for row in genome.fate_affinity)
    return max(range(len(Fate)), key=lambda i: (scores[i], -i))

def advance_region(genome: DevelopmentGenome, niche: RegionalNiche,
                   progenitors: Iterable[NeuralStemCell],
                   policy: LineagePolicy = LineagePolicy(), *, seed: int = 0) -> RegionalStepResult:
    """Advance one bounded lineage step using seeded stochastic cell decisions."""
    cells = tuple(progenitors)
    if len(cells) > niche.capacity:
        raise ValueError("initial progenitor population exceeds regional capacity")
    rng = random.Random(seed)
    occupancy = len(cells)/niche.capacity if niche.capacity else 0.0
    demand_level = max(niche.demand)
    hill = demand_level/(policy.activation_half_saturation+demand_level)
    activation = policy.activation_rate*hill*(1-policy.crowding_feedback*occupancy)*(0.5+0.5*niche.activity)
    activation = min(1.0, max(0.0, activation))
    self_renewal = min(1.0, max(0.0, policy.base_self_renewal
        + policy.homeostatic_self_renewal*(1-occupancy)
        - policy.differentiation_pressure*demand_level))
    candidates = [i for i, cell in enumerate(cells)
        if cell.lineage_depth < policy.max_lineage_depth and rng.random() < activation*cell.potency]
    rng.shuffle(candidates)
    resource_limit = math.floor(niche.available_resource/genome.resource_cost)
    divisions = min(len(candidates), resource_limit)
    if policy.max_divisions_per_step is not None:
        divisions = min(divisions, policy.max_divisions_per_step)
    selected = set(candidates[:divisions])
    fate = _fate_index(genome, niche.demand)
    differentiated = [0, 0, 0]
    next_cells: list[NeuralStemCell] = []
    for i, cell in enumerate(cells):
        if i not in selected:
            next_cells.append(cell)
            continue
        for _ in range(2):
            if cell.lineage_depth+1 <= policy.max_lineage_depth and rng.random() < self_renewal:
                next_cells.append(NeuralStemCell(
                    potency=max(0.0, min(1.0, cell.potency*policy.potency_decay)),
                    lineage_depth=cell.lineage_depth+1))
            else:
                differentiated[fate] += 1
    overflow = max(0, len(next_cells)-niche.capacity)
    if overflow:
        del next_cells[-overflow:]
        differentiated[fate] += overflow
    used = divisions*genome.resource_cost
    return RegionalStepResult(niche.region_id, tuple(next_cells), tuple(differentiated),
        len(candidates), divisions, used, max(0.0, niche.available_resource-used),
        activation, self_renewal)
