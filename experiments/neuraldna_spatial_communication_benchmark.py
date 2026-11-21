"""Spatial communication and local niche topology benchmark for NeuralDNA 0.7.

This is an isolated synthetic experiment, not the BA runtime or a biological
simulation. It tests when neighborhood communication helps or harms regions.

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
import random
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

STATE_COUNT = 3
TOPOLOGIES = ("line", "ring", "complete", "clustered")
SPATIAL_STRATEGIES = (
    "local_cue",
    "global_signal",
    "neighbor_signal",
    "local_history",
    "adaptive_network",
)


@dataclass(frozen=True, slots=True)
class SpatialBenchmarkResult:
    strategy: str
    topology: str
    geometric_mean_fitness: float
    local_cue_accuracy: float
    global_signal_accuracy: float
    neighbor_signal_accuracy: float
    history_accuracy: float
    selected_accuracy: float
    global_signal_usage: float
    neighbor_signal_usage: float
    packet_delivery_rate: float
    regional_divergence: float
    mean_degree: float


def _mode(values: tuple[int, ...]) -> int:
    return max(range(STATE_COUNT), key=lambda state: (values.count(state), -state))


def build_topology(
    region_count: int,
    topology: str,
    region_clusters: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    """Build deterministic undirected neighborhood adjacency."""
    if region_count < 1:
        raise ValueError("region_count must be positive")
    if topology not in TOPOLOGIES:
        raise ValueError(f"unknown topology: {topology}")
    if len(region_clusters) != region_count:
        raise ValueError("region_clusters must match region_count")

    neighbors = [set() for _ in range(region_count)]
    if topology == "line":
        edges = ((index, index + 1) for index in range(region_count - 1))
    elif topology == "ring":
        if region_count < 2:
            edges = ()
        elif region_count == 2:
            edges = ((0, 1),)
        else:
            edges = (
                (index, (index + 1) % region_count)
                for index in range(region_count)
            )
    elif topology == "complete":
        edges = (
            (left, right)
            for left in range(region_count)
            for right in range(left + 1, region_count)
        )
    else:
        edges = (
            (left, right)
            for left in range(region_count)
            for right in range(left + 1, region_count)
            if region_clusters[left] == region_clusters[right]
        )

    for left, right in edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    return tuple(tuple(sorted(items)) for items in neighbors)


def _generate_regions(
    seed: int,
    length: int,
    processes: tuple[str, ...],
    clusters: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    """Regions in one niche share a forcing sequence; clusters have state offsets."""
    base_sequences: dict[str, tuple[int, ...]] = {}
    for process in set(processes):
        base_sequences[process] = generate_environment(seed, length, process)
    return tuple(
        tuple(
            (state + cluster % STATE_COUNT) % STATE_COUNT
            for state in base_sequences[process]
        )
        for process, cluster in zip(processes, clusters, strict=True)
    )


def simulate_spatial_trial(
    seed: int,
    *,
    steps: int,
    region_processes: tuple[str, ...],
    region_clusters: tuple[int, ...],
    topology: str,
    cue_accuracy: float,
    development_latency: int,
    communication_latency: int,
    signal_anticipation: int,
    strategy: str,
    message_loss: float = 0.0,
    communication_cost: float = 0.01,
) -> SpatialBenchmarkResult:
    """Compare local, global, and neighbor information under spatial heterogeneity.

    Future environmental states are used only to generate noisy forecasts and
    score outcomes. The decision policy receives cues, acquired history, and
    delayed messages; it never receives the target state directly.
    """
    region_count = len(region_processes)
    if steps < 2 or region_count < 1:
        raise ValueError("steps must be >= 2 and at least one region is required")
    if len(region_clusters) != region_count:
        raise ValueError("region_clusters must match region_processes")
    if any(not isinstance(cluster, int) or cluster < 0 for cluster in region_clusters):
        raise ValueError("cluster identifiers must be non-negative integers")
    if min(development_latency, communication_latency, signal_anticipation) < 0:
        raise ValueError("latencies and anticipation must be non-negative")
    if strategy not in SPATIAL_STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if not math.isfinite(cue_accuracy) or not 0.0 <= cue_accuracy <= 1.0:
        raise ValueError("cue_accuracy must be finite and in [0, 1]")
    if not math.isfinite(message_loss) or not 0.0 <= message_loss <= 1.0:
        raise ValueError("message_loss must be finite and in [0, 1]")
    if not math.isfinite(communication_cost) or not 0.0 <= communication_cost < 1.0:
        raise ValueError("communication_cost must be finite and in [0, 1)")

    adjacency = build_topology(region_count, topology, region_clusters)
    length = steps + development_latency + communication_latency + signal_anticipation + 1
    environments = _generate_regions(seed, length, region_processes, region_clusters)

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
    forecast_horizon = development_latency + signal_anticipation
    regional_forecasts = tuple(
        generate_cues(
            seed ^ (0x85EBCA6B + region * 104729),
            environment,
            steps,
            forecast_horizon,
            cue_accuracy,
        )
        for region, environment in enumerate(environments)
    )

    global_signals = tuple(
        _mode(tuple(regional_forecasts[region][step] for region in range(region_count)))
        for step in range(steps)
    )

    loss_rng = random.Random(seed ^ 0xC2B2AE35)
    neighbor_signals: list[list[int | None]] = [
        [None] * steps for _ in range(region_count)
    ]
    delivered = attempted = 0
    for decision_step in range(communication_latency, steps):
        send_step = decision_step - communication_latency
        for receiver, senders in enumerate(adjacency):
            received = []
            for sender in senders:
                attempted += 1
                if loss_rng.random() >= message_loss:
                    received.append(regional_forecasts[sender][send_step])
                    delivered += 1
            if received:
                neighbor_signals[receiver][decision_step] = _mode(tuple(received))

    transitions = [TransitionModel() for _ in environments]
    local_calibrations = [PredictorCalibration() for _ in environments]
    history_calibrations = [PredictorCalibration() for _ in environments]
    global_calibrations = [PredictorCalibration() for _ in environments]
    neighbor_calibrations = [PredictorCalibration() for _ in environments]
    history_predictions: list[list[int]] = [[] for _ in environments]

    log_fitness = 0.0
    local_hits = global_hits = neighbor_hits = history_hits = selected_hits = 0
    global_count = neighbor_count = decisions = 0
    global_uses = neighbor_uses = 0
    divergence_total = 0.0

    for step in range(steps):
        # Update calibrations only after the corresponding target is observed.
        for region, environment in enumerate(environments):
            if step > 0:
                transitions[region].observe(environment[step - 1], environment[step])
            if step >= development_latency:
                prior_decision = step - development_latency
                local_calibrations[region].observe(
                    local_cues[region][prior_decision] == environment[step]
                )
                history_calibrations[region].observe(
                    history_predictions[region][prior_decision] == environment[step]
                )
                if prior_decision >= communication_latency:
                    global_calibrations[region].observe(
                        global_signals[prior_decision - communication_latency]
                        == environment[step]
                    )
                    neighbor_message = neighbor_signals[region][prior_decision]
                    if neighbor_message is not None:
                        neighbor_calibrations[region].observe(
                            neighbor_message == environment[step]
                        )

            forecast = transitions[region].forecast(
                environment[step], development_latency
            )
            history_predictions[region].append(
                max(range(STATE_COUNT), key=lambda state: (forecast[state], -state))
            )

        target_states = tuple(
            environment[step + development_latency] for environment in environments
        )
        if region_count > 1:
            pair_count = region_count * (region_count - 1) / 2
            divergence_total += sum(
                left != right
                for index, left in enumerate(target_states)
                for right in target_states[index + 1 :]
            ) / pair_count

        global_message = (
            global_signals[step - communication_latency]
            if step >= communication_latency
            else None
        )

        for region, target in enumerate(target_states):
            local = local_cues[region][step]
            history = history_predictions[region][step]
            neighbor_message = neighbor_signals[region][step]
            local_hits += int(local == target)
            history_hits += int(history == target)
            if global_message is not None:
                global_hits += int(global_message == target)
                global_count += 1
            if neighbor_message is not None:
                neighbor_hits += int(neighbor_message == target)
                neighbor_count += 1

            local_skill = local_calibrations[region].skill
            history_skill = history_calibrations[region].skill
            global_skill = (
                global_calibrations[region].skill if global_message is not None else 0.0
            )
            neighbor_skill = (
                neighbor_calibrations[region].skill
                if neighbor_message is not None
                else 0.0
            )

            if strategy == "local_cue":
                prediction, source, skill = local, "local", 1.0
            elif strategy == "global_signal":
                prediction, source, skill = (
                    (global_message, "global", 1.0)
                    if global_message is not None
                    else (local, "local", 1.0)
                )
            elif strategy == "neighbor_signal":
                prediction, source, skill = (
                    (neighbor_message, "neighbor", 1.0)
                    if neighbor_message is not None
                    else (local, "local", 1.0)
                )
            elif strategy == "local_history":
                prediction, source, skill = history, "history", 1.0
            else:
                candidates = [
                    (local_skill, local, "local"),
                    (history_skill, history, "history"),
                ]
                if global_message is not None:
                    candidates.append((global_skill, global_message, "global"))
                if neighbor_message is not None:
                    candidates.append((neighbor_skill, neighbor_message, "neighbor"))
                skill, prediction, source = max(
                    candidates,
                    key=lambda item: (item[0], item[2] == "local"),
                )

            selected_hits += int(prediction == target)
            decisions += 1
            if source == "global":
                global_uses += 1
            if source == "neighbor":
                neighbor_uses += 1

            if strategy == "adaptive_network":
                reserve = 0.02 + 0.75 * (1.0 - skill) ** 2
                plasticity = 0.95 * skill
                directed_fitness = (
                    1.0 if prediction == target else SPECIALIST_MISMATCH_FITNESS
                )
                diversified_fitness = (
                    1.0 + (STATE_COUNT - 1) * SPECIALIST_MISMATCH_FITNESS
                ) / STATE_COUNT
                portfolio_fitness = (
                    (1.0 - reserve)
                    * (
                        skill * directed_fitness
                        + (1.0 - skill) * GENERALIST_FITNESS
                    )
                    + reserve * diversified_fitness
                )
            else:
                reserve = 0.0
                plasticity = 1.0 if source in ("global", "neighbor") else 0.0
                portfolio_fitness = (
                    1.0 if prediction == target else SPECIALIST_MISMATCH_FITNESS
                )

            communication_penalty = (
                1.0 - communication_cost
                if source in ("global", "neighbor")
                else 1.0
            )
            cost = (
                1.0 - 0.02 * plasticity - 0.01 * reserve
            ) * communication_penalty
            log_fitness += math.log(max(1e-12, portfolio_fitness * cost))

    mean_degree = statistics.fmean(len(items) for items in adjacency)
    return SpatialBenchmarkResult(
        strategy=strategy,
        topology=topology,
        geometric_mean_fitness=math.exp(log_fitness / decisions),
        local_cue_accuracy=local_hits / decisions,
        global_signal_accuracy=global_hits / max(1, global_count),
        neighbor_signal_accuracy=neighbor_hits / max(1, neighbor_count),
        history_accuracy=history_hits / decisions,
        selected_accuracy=selected_hits / decisions,
        global_signal_usage=global_uses / decisions,
        neighbor_signal_usage=neighbor_uses / decisions,
        packet_delivery_rate=delivered / max(1, attempted),
        regional_divergence=divergence_total / steps,
        mean_degree=mean_degree,
    )


def run() -> None:
    scenarios = (
        (
            "shared_stochastic_niche",
            ("stochastic",) * 8,
            (0,) * 8,
            "ring",
            0.80,
            0.0,
        ),
        (
            "two_spatially_clustered_niches",
            ("cycle",) * 8,
            (0, 0, 0, 0, 1, 1, 1, 1),
            "clustered",
            0.95,
            0.0,
        ),
        (
            "clustered_niches_with_global_topology",
            ("cycle",) * 8,
            (0, 0, 0, 0, 1, 1, 1, 1),
            "complete",
            0.95,
            0.0,
        ),
        (
            "communication_loss",
            ("stochastic",) * 8,
            (0,) * 8,
            "ring",
            0.80,
            0.50,
        ),
    )
    for name, processes, clusters, topology, accuracy, loss in scenarios:
        print(
            f"\n{name}: regions={len(processes)}, topology={topology}, "
            f"cue_accuracy={accuracy:.2f}, message_loss={loss:.2f}"
        )
        for strategy in SPATIAL_STRATEGIES:
            results = [
                simulate_spatial_trial(
                    seed,
                    steps=300,
                    region_processes=processes,
                    region_clusters=clusters,
                    topology=topology,
                    cue_accuracy=accuracy,
                    development_latency=2,
                    communication_latency=2,
                    signal_anticipation=2,
                    strategy=strategy,
                    message_loss=loss,
                )
                for seed in range(20)
            ]
            print(
                f"  {strategy:18s} "
                f"fitness={statistics.fmean(r.geometric_mean_fitness for r in results):.4f} "
                f"selected={statistics.fmean(r.selected_accuracy for r in results):.3f} "
                f"local={statistics.fmean(r.local_cue_accuracy for r in results):.3f} "
                f"global={statistics.fmean(r.global_signal_accuracy for r in results):.3f} "
                f"neighbor={statistics.fmean(r.neighbor_signal_accuracy for r in results):.3f} "
                f"neighbor_use={statistics.fmean(r.neighbor_signal_usage for r in results):.3f} "
                f"delivery={statistics.fmean(r.packet_delivery_rate for r in results):.3f} "
                f"divergence={statistics.fmean(r.regional_divergence for r in results):.3f}"
            )


if __name__ == "__main__":
    run()
