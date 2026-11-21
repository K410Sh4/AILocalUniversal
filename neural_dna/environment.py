"""Environmental cue assessment and reaction norms for NeuralDNA.

This is an isolated research primitive, not a complete evolutionary engine.
Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class CueEvidence:
    predicted_state: str
    realized_state: str

    def __post_init__(self) -> None:
        if not self.predicted_state or not self.realized_state:
            raise ValueError("cue states must be non-empty")


@dataclass(frozen=True, slots=True)
class CueCalibration:
    """Forgetting Beta-Bernoulli evidence for one environmental cue."""

    successes: float = 0.0
    failures: float = 0.0
    prior_success: float = 1.0
    prior_failure: float = 1.0
    retention: float = 0.98

    def __post_init__(self) -> None:
        values = (
            self.successes, self.failures, self.prior_success,
            self.prior_failure, self.retention,
        )
        if any(isinstance(value, bool) or not math.isfinite(value) for value in values):
            raise ValueError("calibration values must be finite numbers")
        if self.successes < 0 or self.failures < 0:
            raise ValueError("evidence counts must be non-negative")
        if self.prior_success <= 0 or self.prior_failure <= 0:
            raise ValueError("Beta prior parameters must be positive")
        if not 0.0 <= self.retention <= 1.0:
            raise ValueError("retention must be in [0, 1]")

    def observe(self, evidence: CueEvidence) -> CueCalibration:
        """Decay old evidence, then incorporate one observed prediction outcome."""
        correct = evidence.predicted_state == evidence.realized_state
        return CueCalibration(
            successes=self.successes * self.retention + float(correct),
            failures=self.failures * self.retention + float(not correct),
            prior_success=self.prior_success,
            prior_failure=self.prior_failure,
            retention=self.retention,
        )

    @property
    def reliability(self) -> float:
        return (self.prior_success + self.successes) / (
            self.prior_success + self.prior_failure + self.successes + self.failures
        )

    @property
    def confidence(self) -> float:
        evidence = self.successes + self.failures
        prior_strength = self.prior_success + self.prior_failure
        return evidence / (evidence + prior_strength)


@dataclass(frozen=True, slots=True)
class ReactionExpression:
    plasticity: float
    diversity_reserve: float
    signed_evidence: float


@dataclass(frozen=True, slots=True)
class ReactionNorm:
    """Genetically encoded mapping from assessed cues to developmental strategy."""

    base_plasticity: float = 0.1
    max_plasticity: float = 1.0
    base_diversity_reserve: float = 0.05
    max_diversity_reserve: float = 0.8

    def __post_init__(self) -> None:
        values = (
            self.base_plasticity, self.max_plasticity,
            self.base_diversity_reserve, self.max_diversity_reserve,
        )
        if any(isinstance(value, bool) or not math.isfinite(value)
               or not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("reaction norm values must be finite and in [0, 1]")
        if self.base_plasticity > self.max_plasticity:
            raise ValueError("base_plasticity cannot exceed max_plasticity")
        if self.base_diversity_reserve > self.max_diversity_reserve:
            raise ValueError("base_diversity_reserve cannot exceed its maximum")

    def express(
        self, calibration: CueCalibration, environmental_volatility: float
    ) -> ReactionExpression:
        """Trust reliable cues; preserve alternatives when cues are weak or volatility is high."""
        if (isinstance(environmental_volatility, bool)
                or not math.isfinite(environmental_volatility)
                or not 0.0 <= environmental_volatility <= 1.0):
            raise ValueError("environmental_volatility must be finite and in [0, 1]")

        signed_evidence = calibration.confidence * (2.0 * calibration.reliability - 1.0)
        positive_evidence = max(0.0, signed_evidence)
        plasticity = self.base_plasticity + (
            self.max_plasticity - self.base_plasticity
        ) * positive_evidence
        diversity = self.base_diversity_reserve + (
            self.max_diversity_reserve - self.base_diversity_reserve
        ) * environmental_volatility * (1.0 - positive_evidence)

        return ReactionExpression(
            plasticity=min(1.0, max(0.0, plasticity)),
            diversity_reserve=min(1.0, max(0.0, diversity)),
            signed_evidence=signed_evidence,
        )
