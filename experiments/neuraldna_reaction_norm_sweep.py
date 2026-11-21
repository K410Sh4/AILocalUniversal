"""Synthetic multi-environment benchmark for NeuralDNA reaction norms.

Run from repository root: python experiments/neuraldna_reaction_norm_sweep.py
Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
import random
import statistics

from neural_dna.environment import CueCalibration, CueEvidence, ReactionNorm


def simulate(
    seed: int,
    *,
    steps: int,
    switch_probability: float,
    cue_accuracy: float,
    mode: str,
) -> float:
    rng = random.Random(seed)
    environment = rng.randrange(3)
    calibration = CueCalibration()
    reaction_norm = ReactionNorm()
    log_fitness = 0.0

    for _ in range(steps):
        if rng.random() < switch_probability:
            environment = rng.randrange(3)
        if rng.random() < cue_accuracy:
            cue = environment
        else:
            cue = rng.choice([state for state in range(3) if state != environment])

        if mode == "adaptive":
            expression = reaction_norm.express(
                calibration, min(1.0, switch_probability * 2.0)
            )
            plasticity = expression.plasticity
            reserve = expression.diversity_reserve
        elif mode == "fixed_plastic":
            plasticity, reserve = 1.0, 0.0
        elif mode == "fixed_hedge":
            plasticity, reserve = 1.0, 0.5
        elif mode == "fixed_generalist":
            plasticity, reserve = 0.0, 1.0
        elif mode == "fixed":
            plasticity, reserve = 0.0, 0.0
        else:
            raise ValueError(f"unknown benchmark mode: {mode}")

        uses_cue = rng.random() < plasticity
        if uses_cue:
            adaptive_fitness = 1.0 if cue == environment else 0.15
        else:
            adaptive_fitness = 0.62
        fitness = (1.0 - reserve) * adaptive_fitness + reserve * 0.62
        fitness *= 1.0 - 0.025 * plasticity - 0.015 * reserve
        log_fitness += math.log(max(fitness, 1e-12))

        calibration = calibration.observe(
            CueEvidence(str(cue), str(environment))
        )

    return math.exp(log_fitness / steps)


def run() -> None:
    scenarios = (
        ("stable_reliable", 0.01, 1.0),
        ("fast_reliable", 0.40, 1.0),
        ("fast_noisy", 0.40, 0.40),
        ("stable_noisy", 0.01, 0.40),
        ("fast_adversarial", 0.40, 0.20),
    )
    modes = ("fixed", "fixed_plastic", "fixed_hedge", "adaptive")
    for name, switch_probability, cue_accuracy in scenarios:
        print(name)
        for mode in modes:
            scores = [
                simulate(
                    seed,
                    steps=1000,
                    switch_probability=switch_probability,
                    cue_accuracy=cue_accuracy,
                    mode=mode,
                )
                for seed in range(100)
            ]
            print(
                f"  {mode}: mean={statistics.fmean(scores):.4f}, "
                f"sd={statistics.pstdev(scores):.4f}"
            )


if __name__ == "__main__":
    run()
