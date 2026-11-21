"""Field-coupled regional environmental adaptation benchmark for NeuralDNA 0.9.

The benchmark combines local anticipatory cues, acquired regional history, and
morphogen-like signal fields. It is not the BA runtime or a biological model.

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
from experiments.neuraldna_morphogen_signal_field import (
    SignalEdge,
    SignalField,
    SignalFieldConfig,
)

STATE_COUNT = 3
FIELD_STRATEGIES = (
    "local_cue",
    "local_history",
    "global_mode",
    "discrete_neighbor",
    "field_only",
    "adaptive_field",
)


@dataclass(frozen=True, slots=True)
class FieldAdaptationResult:
    strategy: str
    geometric_mean_fitness: float
    local_cue_accuracy: float
    history_accuracy: float
    global_accuracy: float
    neighbor_accuracy: float
    field_accuracy: float
    selected_accuracy: float
    field_usage: float
    mean_field_mass: float
    regional_divergence: float
    field_recovery_lag: float


def _mode(values: tuple[int, ...]) -> int:
    return max(range(STATE_COUNT), key=lambda state: (values.count(state), -state))


def _generate_regions(
    seed: int,
    length: int,
    processes: tuple[str, ...],
    clusters: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    base = {
        process: generate_environment(seed, length, process)
        for process in set(processes)
    }
    return tuple(
        tuple((state + cluster % STATE_COUNT) % STATE_COUNT for state in base[process])
        for process, cluster in zip(processes, clusters, strict=True)
    )


def _field_prediction(
    exposure: tuple[float, ...],
    threshold: float,
) -> int | None:
    if not exposure or max(exposure) < threshold:
        return None
    return max(range(STATE_COUNT), key=lambda state: (exposure[state], -state))


def _recovery_lag(
    predictions: tuple[int | None, ...],
    change_index: int,
    new_state: int,
    maximum_lag: int,
) -> float:
    for index in range(max(0, change_index), len(predictions) - 2):
        if predictions[index : index + 3] == (new_state, new_state, new_state):
            return float(index - change_index)
    return float(maximum_lag)


def simulate_field_adaptation_trial(
    seed: int,
    *,
    steps: int,
    region_processes: tuple[str, ...],
    region_clusters: tuple[int, ...],
    cue_accuracy: float,
    development_latency: int,
    strategy: str,
    diffusion: float,
    degradation: float,
    uptake_vmax: float,
    uptake_km: float,
    sensitivity_kd: float,
    hill_coefficient: float,
    exposure_clearance: float,
    boundary_permeability: float = 0.0,
    source_strength: float = 1.0,
    exposure_threshold: float = 0.02,
    field_cost: float = 0.01,
    discrete_cost: float = 0.005,
) -> FieldAdaptationResult:
    """Compare field and non-field strategies using only available observations."""
    region_count = len(region_processes)
    if steps < 2 or region_count < 1:
        raise ValueError("steps must be >= 2 and at least one region is required")
    if len(region_clusters) != region_count:
        raise ValueError("region_clusters must match region_processes")
    if any(not isinstance(value, int) or value < 0 for value in region_clusters):
        raise ValueError("cluster identifiers must be non-negative integers")
    if development_latency < 0:
        raise ValueError("development_latency must be non-negative")
    if strategy not in FIELD_STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if not math.isfinite(cue_accuracy) or not 0.0 <= cue_accuracy <= 1.0:
        raise ValueError("cue_accuracy must be finite and in [0, 1]")
    for name, value in (
        ("diffusion", diffusion),
        ("degradation", degradation),
        ("uptake_vmax", uptake_vmax),
        ("exposure_clearance", exposure_clearance),
        ("source_strength", source_strength),
        ("exposure_threshold", exposure_threshold),
        ("field_cost", field_cost),
        ("discrete_cost", discrete_cost),
    ):
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
    if not math.isfinite(boundary_permeability) or not 0.0 <= boundary_permeability <= 1.0:
        raise ValueError("boundary_permeability must be finite and in [0, 1]")
    if not math.isfinite(uptake_km) or uptake_km <= 0.0:
        raise ValueError("uptake_km must be finite and positive")
    if not math.isfinite(sensitivity_kd) or sensitivity_kd <= 0.0:
        raise ValueError("sensitivity_kd must be finite and positive")
    if not math.isfinite(hill_coefficient) or hill_coefficient <= 0.0:
        raise ValueError("hill_coefficient must be finite and positive")
    if field_cost >= 1.0 or discrete_cost >= 1.0:
        raise ValueError("strategy costs must be less than 1")

    environments = _generate_regions(
        seed,
        steps + development_latency + 1,
        region_processes,
        region_clusters,
    )
    cues = tuple(
        generate_cues(
            seed ^ (0x9E3779B9 + region * 7919),
            environment,
            steps,
            development_latency,
            cue_accuracy,
        )
        for region, environment in enumerate(environments)
    )

    edges = tuple(
        SignalEdge(
            index,
            index + 1,
            distance=1.0,
            permeability=(
                1.0
                if region_clusters[index] == region_clusters[index + 1]
                else boundary_permeability
            ),
        )
        for index in range(region_count - 1)
    )
    field = SignalField(
        region_count,
        STATE_COUNT,
        edges,
        SignalFieldConfig(
            time_step=1.0,
            diffusion=diffusion,
            degradation=degradation,
            uptake_vmax=uptake_vmax,
            uptake_km=uptake_km,
            sensitivity_kd=sensitivity_kd,
            hill_coefficient=hill_coefficient,
            exposure_clearance=exposure_clearance,
        ),
    )

    transitions = [TransitionModel() for _ in environments]
    local_calibrations = [PredictorCalibration() for _ in environments]
    history_calibrations = [PredictorCalibration() for _ in environments]
    field_calibrations = [PredictorCalibration() for _ in environments]
    history_predictions: list[list[int]] = [[] for _ in environments]
    field_predictions: list[list[int | None]] = [[] for _ in environments]

    log_fitness = 0.0
    local_hits = history_hits = global_hits = neighbor_hits = 0
    field_hits = selected_hits = 0
    field_count = decisions = field_uses = 0
    neighbor_count = field_mass_total = divergence_total = 0.0

    for step in range(steps):
        for region, environment in enumerate(environments):
            if step > 0:
                transitions[region].observe(environment[step - 1], environment[step])
            if step >= development_latency:
                previous_decision = step - development_latency
                local_calibrations[region].observe(
                    cues[region][previous_decision] == environment[step]
                )
                history_calibrations[region].observe(
                    history_predictions[region][previous_decision] == environment[step]
                )
                previous_field = field_predictions[region][previous_decision]
                if previous_field is not None:
                    field_calibrations[region].observe(
                        previous_field == environment[step]
                    )

            forecast = transitions[region].forecast(
                environment[step], development_latency
            )
            history_predictions[region].append(
                max(range(STATE_COUNT), key=lambda state: (forecast[state], -state))
            )

        # Each region emits only its local forecast cue; no target state is passed in.
        production = tuple(
            tuple(source_strength if cues[region][step] == signal else 0.0
                  for signal in range(STATE_COUNT))
            for region in range(region_count)
        )
        field_snapshot = field.step(production)
        field_mass_total += field_snapshot.total_mass

        field_states = tuple(
            _field_prediction(field_snapshot.exposures[region], exposure_threshold)
            for region in range(region_count)
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

        global_prediction = _mode(tuple(cues[region][step] for region in range(region_count)))

        for region, target in enumerate(target_states):
            local = cues[region][step]
            history = history_predictions[region][step]
            field_state = field_states[region]
            neighbor_ids = []
            if region > 0:
                neighbor_ids.append(region - 1)
            if region + 1 < region_count:
                neighbor_ids.append(region + 1)
            neighbor_ids = [
                other for other in neighbor_ids
                if region_clusters[other] == region_clusters[region]
                or boundary_permeability > 0.0
            ]
            neighbor_prediction = (
                _mode(tuple(cues[other][step] for other in neighbor_ids))
                if neighbor_ids
                else local
            )

            local_hits += int(local == target)
            history_hits += int(history == target)
            global_hits += int(global_prediction == target)
            if neighbor_ids:
                neighbor_hits += int(neighbor_prediction == target)
                neighbor_count += 1
            if field_state is not None:
                field_hits += int(field_state == target)
                field_count += 1

            local_skill = local_calibrations[region].skill
            history_skill = history_calibrations[region].skill
            field_skill = field_calibrations[region].skill

            if strategy == "local_cue":
                prediction, source, skill = local, "local", 1.0
            elif strategy == "local_history":
                prediction, source, skill = history, "history", 1.0
            elif strategy == "global_mode":
                prediction, source, skill = global_prediction, "global", 1.0
            elif strategy == "discrete_neighbor":
                prediction, source, skill = neighbor_prediction, "neighbor", 1.0
            elif strategy == "field_only":
                prediction, source, skill = (
                    (field_state, "field", 1.0)
                    if field_state is not None
                    else (local, "local", 1.0)
                )
            else:
                candidates = [
                    (local_skill, local, "local"),
                    (history_skill, history, "history"),
                ]
                if field_state is not None:
                    candidates.append((field_skill, field_state, "field"))
                skill, prediction, source = max(
                    candidates,
                    key=lambda item: (item[0], item[2] == "local"),
                )

            selected_hits += int(prediction == target)
            decisions += 1
            field_uses += int(source == "field")

            if strategy == "adaptive_field":
                reserve = 0.02 + 0.75 * (1.0 - skill) ** 2
                plasticity = 0.95 * skill
                specialist = (
                    1.0 if prediction == target else SPECIALIST_MISMATCH_FITNESS
                )
                diversified = (
                    1.0 + (STATE_COUNT - 1) * SPECIALIST_MISMATCH_FITNESS
                ) / STATE_COUNT
                portfolio = (
                    (1.0 - reserve)
                    * (skill * specialist + (1.0 - skill) * GENERALIST_FITNESS)
                    + reserve * diversified
                )
            else:
                reserve = 0.0
                plasticity = 1.0 if source in ("field", "neighbor", "global") else 0.0
                portfolio = (
                    1.0 if prediction == target else SPECIALIST_MISMATCH_FITNESS
                )

            cost = 1.0 - 0.02 * plasticity - 0.01 * reserve
            if strategy in ("field_only", "adaptive_field"):
                cost *= 1.0 - field_cost
            elif source in ("global", "neighbor"):
                cost *= 1.0 - discrete_cost
            log_fitness += math.log(max(1e-12, portfolio * cost))

            field_predictions[region].append(field_state)

    recovery_lags = []
    for region, environment in enumerate(environments):
        if region_processes[region] == "abrupt":
            shift_index = len(environment) // 2 - development_latency
            new_state = environment[len(environment) // 2]
            recovery_lags.append(
                _recovery_lag(
                    tuple(field_predictions[region]),
                    shift_index,
                    new_state,
                    steps,
                )
            )

    return FieldAdaptationResult(
        strategy=strategy,
        geometric_mean_fitness=math.exp(log_fitness / decisions),
        local_cue_accuracy=local_hits / decisions,
        history_accuracy=history_hits / decisions,
        global_accuracy=global_hits / decisions,
        neighbor_accuracy=neighbor_hits / max(1.0, neighbor_count),
        field_accuracy=field_hits / max(1, field_count),
        selected_accuracy=selected_hits / decisions,
        field_usage=field_uses / decisions,
        mean_field_mass=field_mass_total / steps,
        regional_divergence=divergence_total / steps,
        field_recovery_lag=statistics.fmean(recovery_lags) if recovery_lags else 0.0,
    )


def run() -> None:
    scenarios = (
        (
            "shared_stable_noisy",
            ("stable",) * 8,
            (0,) * 8,
            0.80,
            0.25,
            0.10,
            0.0,
            1.0,
        ),
        (
            "clustered_stable_closed_boundary",
            ("stable",) * 8,
            (0, 0, 0, 0, 1, 1, 1, 1),
            0.95,
            0.25,
            0.10,
            0.0,
            0.0,
        ),
        (
            "clustered_stable_open_boundary",
            ("stable",) * 8,
            (0, 0, 0, 0, 1, 1, 1, 1),
            0.95,
            0.80,
            0.05,
            0.0,
            1.0,
        ),
        (
            "abrupt_shift_fast_removal",
            ("abrupt",) * 8,
            (0,) * 8,
            0.95,
            0.25,
            0.80,
            0.50,
            1.0,
        ),
    )
    for name, processes, clusters, accuracy, diffusion, degradation, uptake, boundary in scenarios:
        print(
            f"\n{name}: regions={len(processes)}, cue={accuracy:.2f}, "
            f"D={diffusion:.2f}, decay={degradation:.2f}, "
            f"uptake={uptake:.2f}, boundary={boundary:.2f}"
        )
        for strategy in FIELD_STRATEGIES:
            results = [
                simulate_field_adaptation_trial(
                    seed,
                    steps=240,
                    region_processes=processes,
                    region_clusters=clusters,
                    cue_accuracy=accuracy,
                    development_latency=2,
                    strategy=strategy,
                    diffusion=diffusion,
                    degradation=degradation,
                    uptake_vmax=uptake,
                    uptake_km=0.5,
                    sensitivity_kd=0.2,
                    hill_coefficient=2.0,
                    exposure_clearance=0.4,
                    boundary_permeability=boundary,
                )
                for seed in range(12)
            ]
            print(
                f"  {strategy:18s} "
                f"fitness={statistics.fmean(r.geometric_mean_fitness for r in results):.4f} "
                f"selected={statistics.fmean(r.selected_accuracy for r in results):.3f} "
                f"field={statistics.fmean(r.field_accuracy for r in results):.3f} "
                f"field_use={statistics.fmean(r.field_usage for r in results):.3f} "
                f"mass={statistics.fmean(r.mean_field_mass for r in results):.3f} "
                f"recovery={statistics.fmean(r.field_recovery_lag for r in results):.1f}"
            )


if __name__ == "__main__":
    run()
