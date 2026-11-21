"""Multi-region environmental niche benchmark for NeuralDNA 0.6.

The model tests local microenvironments, shared signals, communication delay,
and regional diversity. It is a synthetic hypothesis test, not a BA runtime.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from experiments.neuraldna_anticipatory_benchmark import (
    GENERALIST_FITNESS,
    SPECIALIST_MISMATCH_FITNESS,
    PredictorCalibration,
    TransitionModel,
    generate_cues,
    generate_environment,
)

REGIONAL_STRATEGIES = (
    "local_cue",
    "global_signal",
    "local_history",
    "adaptive_local",
    "adaptive_network",
)
STATE_COUNT = 3


@dataclass(frozen=True, slots=True)
class RegionalBenchmarkResult:
    strategy: str
    geometric_mean_fitness: float
    local_cue_accuracy: float
    global_signal_accuracy: float
    local_history_accuracy: float
    mean_selected_accuracy: float
    mean_global_signal_usage: float
    mean_plasticity: float
    mean_diversity_reserve: float
    regional_divergence: float


def _mode(values: tuple[int, ...]) -> int:
    return max(range(STATE_COUNT), key=lambda state: (values.count(state), -state))


def _generate_regions(
    seed: int, steps: int, processes: tuple[str, ...],
    development_latency: int, communication_latency: int,
    signal_anticipation: int,
) -> tuple[tuple[int, ...], ...]:
    length = steps + development_latency + communication_latency + signal_anticipation + 1
    homogeneous = len(set(processes)) == 1
    return tuple(
        generate_environment(
            seed if homogeneous else seed + region * 104729,
            length,
            process,
        )
        for region, process in enumerate(processes)
    )


def simulate_regional_trial(
    seed: int,
    *,
    steps: int,
    region_processes: tuple[str, ...],
    cue_accuracy: float,
    development_latency: int,
    communication_latency: int,
    signal_anticipation: int,
    strategy: str,
    communication_cost: float = 0.01,
) -> RegionalBenchmarkResult:
    """Compare region-local and shared-signal adaptation under niche divergence."""
    if steps < 2 or not region_processes:
        raise ValueError("steps must be >= 2 and at least one region is required")
    if min(development_latency, communication_latency, signal_anticipation) < 0:
        raise ValueError("latencies and anticipation must be non-negative")
    if strategy not in REGIONAL_STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if not math.isfinite(cue_accuracy) or not 0.0 <= cue_accuracy <= 1.0:
        raise ValueError("cue_accuracy must be finite and in [0, 1]")
    if not math.isfinite(communication_cost) or not 0.0 <= communication_cost < 1.0:
        raise ValueError("communication_cost must be finite and in [0, 1)")

    environments = _generate_regions(
        seed, steps, region_processes, development_latency,
        communication_latency, signal_anticipation,
    )
    region_count = len(environments)
    local_cues = tuple(
        generate_cues(
            seed ^ (0x9E3779B9 + region * 7919),
            environment,
            steps,
            development_latency,
            cue_accuracy,
        )
        for region, environment in enumerate(environments)
    )
    # Signals are emitted by each region and broadcast after communication_latency.
    # signal_anticipation explicitly compensates for transport delay; the evaluator
    # never supplies the future target to the decision policy.
    regional_forecasts = tuple(
        generate_cues(
            seed ^ (0x85EBCA6B + region * 104729),
            environment,
            steps,
            development_latency + signal_anticipation,
            cue_accuracy,
        )
        for region, environment in enumerate(environments)
    )
    global_signals = tuple(
        _mode(tuple(regional_forecasts[region][step] for region in range(region_count)))
        for step in range(steps)
    )

    models = [TransitionModel() for _ in environments]
    local_calibrations = [PredictorCalibration() for _ in environments]
    history_calibrations = [PredictorCalibration() for _ in environments]
    global_calibrations = [PredictorCalibration() for _ in environments]
    history_predictions: list[list[int]] = [[] for _ in environments]

    log_fitness = 0.0
    selected_hits = local_hits = global_hits = history_hits = 0
    selected_count = global_uses = 0
    plasticity_total = reserve_total = 0.0
    global_signal_count = 0
    divergence_total = 0.0
    diversified_fitness = (
        1.0 + (STATE_COUNT - 1) * SPECIALIST_MISMATCH_FITNESS
    ) / STATE_COUNT

    for step in range(steps):
        for region, environment in enumerate(environments):
            if step > 0:
                models[region].observe(environment[step - 1], environment[step])

            forecast = models[region].forecast(environment[step], development_latency)
            history_state = max(
                range(STATE_COUNT), key=lambda state: (forecast[state], -state)
            )
            history_predictions[region].append(history_state)

            # Calibrate only after the forecast exists and its target is observed.
            if step >= development_latency:
                decision_step = step - development_latency
                local_calibrations[region].observe(
                    local_cues[region][decision_step] == environment[step]
                )
                history_calibrations[region].observe(
                    history_predictions[region][decision_step] == environment[step]
                )
            if step >= development_latency + communication_latency:
                emitted_step = step - development_latency - communication_latency
                global_calibrations[region].observe(
                    global_signals[emitted_step] == environment[step]
                )

        target_states = tuple(
            environment[step + development_latency] for environment in environments
        )
        divergence_total += sum(
            left != right
            for index, left in enumerate(target_states)
            for right in target_states[index + 1 :]
        ) / max(1, region_count * (region_count - 1) / 2)

        received_global = (
            global_signals[step - communication_latency]
            if step >= communication_latency
            else None
        )
        if received_global is not None:
            global_signal_count += region_count

        for region in range(region_count):
            target = target_states[region]
            local_cue = local_cues[region][step]
            history = history_predictions[region][step]
            local_hits += int(local_cue == target)
            history_hits += int(history == target)
            if received_global is not None:
                global_hits += int(received_global == target)

            local_skill = local_calibrations[region].skill
            history_skill = history_calibrations[region].skill
            global_skill = (
                global_calibrations[region].skill
                if received_global is not None
                else 0.0
            )
            if strategy == "local_cue":
                prediction, source, skill = local_cue, "local", 1.0
            elif strategy == "global_signal":
                prediction, source, skill = (
                    (received_global, "global", 1.0)
                    if received_global is not None
                    else (history, "history", 1.0)
                )
            elif strategy == "local_history":
                prediction, source, skill = history, "history", 1.0
            else:
                candidates = [
                    (local_skill, local_cue, "local"),
                    (history_skill, history, "history"),
                ]
                if strategy == "adaptive_network" and received_global is not None:
                    candidates.append((global_skill, received_global, "global"))
                skill, prediction, source = max(
                    candidates, key=lambda item: (item[0], item[2] == "local")
                )

            correct = prediction == target
            selected_hits += int(correct)
            selected_count += 1
            adaptive = strategy in ("adaptive_local", "adaptive_network")
            if adaptive:
                reserve = 0.02 + 0.75 * (1.0 - skill) ** 2
                plasticity = 0.95 * skill
                specialist_fitness = (
                    1.0 if correct else SPECIALIST_MISMATCH_FITNESS
                )
                directed = (
                    skill * specialist_fitness + (1.0 - skill) * GENERALIST_FITNESS
                )
                portfolio_fitness = (
                    (1.0 - reserve) * directed + reserve * diversified_fitness
                )
            else:
                reserve = 0.0
                plasticity = 1.0 if source in ("local", "global") else 0.0
                portfolio_fitness = (
                    1.0 if correct else SPECIALIST_MISMATCH_FITNESS
                )

            communication_penalty = (
                1.0 - communication_cost if source == "global" else 1.0
            )
            cost = (
                1.0 - 0.02 * plasticity - 0.01 * reserve
            ) * communication_penalty
            log_fitness += math.log(max(1e-12, portfolio_fitness * cost))
            plasticity_total += plasticity
            reserve_total += reserve
            global_uses += int(source == "global")

    decisions = steps * region_count
    return RegionalBenchmarkResult(
        strategy=strategy,
        geometric_mean_fitness=math.exp(log_fitness / decisions),
        local_cue_accuracy=local_hits / decisions,
        global_signal_accuracy=global_hits / max(1, global_signal_count),
        local_history_accuracy=history_hits / decisions,
        mean_selected_accuracy=selected_hits / decisions,
        mean_global_signal_usage=global_uses / decisions,
        mean_plasticity=plasticity_total / decisions,
        mean_diversity_reserve=reserve_total / decisions,
        regional_divergence=divergence_total / steps,
    )


def run() -> None:
    scenarios = {
        "shared_stable_niche": ("stable", "stable", "stable", "stable"),
        "divergent_local_niches": ("cycle", "stable", "stochastic", "drift"),
    }
    for name, processes in scenarios.items():
        print(f"\n{name}: regions={len(processes)}, processes={processes}")
        for strategy in REGIONAL_STRATEGIES:
            results = [
                simulate_regional_trial(
                    seed,
                    steps=400,
                    region_processes=processes,
                    cue_accuracy=0.95,
                    development_latency=2,
                    communication_latency=2,
                    signal_anticipation=2,
                    strategy=strategy,
                )
                for seed in range(20)
            ]
            print(
                f"  {strategy:18s} "
                f"fitness={statistics.fmean(r.geometric_mean_fitness for r in results):.4f} "
                f"selected={statistics.fmean(r.mean_selected_accuracy for r in results):.3f} "
                f"local={statistics.fmean(r.local_cue_accuracy for r in results):.3f} "
                f"shared={statistics.fmean(r.global_signal_accuracy for r in results):.3f} "
                f"global_use={statistics.fmean(r.mean_global_signal_usage for r in results):.3f} "
                f"reserve={statistics.fmean(r.mean_diversity_reserve for r in results):.3f} "
                f"divergence={statistics.fmean(r.regional_divergence for r in results):.3f}"
            )


if __name__ == "__main__":
    run()
