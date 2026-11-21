"""Anticipatory plasticity benchmark with explicit cue horizon and development latency.

Synthetic research benchmark, not a biological model or BA runtime.
Run from repository root: python experiments/neuraldna_anticipatory_benchmark.py

Copyright © 2026 K410Sh4. All rights reserved.
SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

STATE_COUNT = 3
GENERALIST_FITNESS = 0.35
SPECIALIST_MISMATCH_FITNESS = 0.05
CUE_RETENTION = 0.98
TRANSITION_RETENTION = 0.995
TRANSITION_PRIOR = 0.25

STRATEGIES = (
    "generalist", "plastic", "hedge", "history",
    "adaptive", "adaptive_plasticity", "adaptive_reserve",
)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    strategy: str
    geometric_mean_fitness: float
    cue_accuracy_at_response: float
    history_forecast_accuracy: float
    mean_plasticity: float
    mean_diversity_reserve: float
    mean_forecast_uncertainty: float
    environmental_change_rate: float
    transition_entropy: float


class TransitionModel:
    """Online Markov estimate; acquired environmental state, never inherited."""

    def __init__(
        self, *, retention: float = TRANSITION_RETENTION,
        prior: float = TRANSITION_PRIOR,
    ) -> None:
        if not math.isfinite(retention) or not 0.0 < retention <= 1.0:
            raise ValueError("retention must be finite and in (0, 1]")
        if not math.isfinite(prior) or prior <= 0.0:
            raise ValueError("prior must be finite and positive")
        self.retention = retention
        self.prior = prior
        self.evidence = [[0.0] * STATE_COUNT for _ in range(STATE_COUNT)]

    def observe(self, previous: int, current: int) -> None:
        if previous not in range(STATE_COUNT) or current not in range(STATE_COUNT):
            raise ValueError("environment states must be 0, 1, or 2")
        for row in self.evidence:
            for index in range(STATE_COUNT):
                row[index] *= self.retention
        self.evidence[previous][current] += 1.0

    def transition_matrix(self) -> tuple[tuple[float, ...], ...]:
        rows = []
        for row in self.evidence:
            denominator = STATE_COUNT * self.prior + sum(row)
            rows.append(tuple((self.prior + value) / denominator for value in row))
        return tuple(rows)

    def forecast(self, current: int, horizon: int) -> tuple[float, ...]:
        if current not in range(STATE_COUNT) or horizon < 0:
            raise ValueError("invalid forecast state or horizon")
        distribution = [float(index == current) for index in range(STATE_COUNT)]
        matrix = self.transition_matrix()
        for _ in range(horizon):
            distribution = [
                sum(distribution[source] * matrix[source][target]
                    for source in range(STATE_COUNT))
                for target in range(STATE_COUNT)
            ]
        return tuple(distribution)

    @staticmethod
    def normalized_entropy(distribution: tuple[float, ...]) -> float:
        entropy = -sum(
            probability * math.log2(probability)
            for probability in distribution if probability > 0.0
        )
        return min(1.0, max(0.0, entropy / math.log2(STATE_COUNT)))


def generate_environment(seed: int, length: int, process: str) -> tuple[int, ...]:
    """Generate stable, cyclic, stochastic, abrupt, or gradual deterministic regimes."""
    if length < 1:
        raise ValueError("length must be positive")
    rng = random.Random(seed)
    if process == "stable":
        return (rng.randrange(STATE_COUNT),) * length
    if process == "cycle":
        phase = rng.randrange(STATE_COUNT)
        return tuple((phase + step) % STATE_COUNT for step in range(length))
    if process == "stochastic":
        state = rng.randrange(STATE_COUNT)
        states = [state]
        for _ in range(1, length):
            if rng.random() < 0.35:
                state = rng.choice(
                    [candidate for candidate in range(STATE_COUNT) if candidate != state]
                )
            states.append(state)
        return tuple(states)
    if process == "abrupt":
        state = rng.randrange(STATE_COUNT)
        changed = rng.choice(
            [candidate for candidate in range(STATE_COUNT) if candidate != state]
        )
        return tuple(state if step < length // 2 else changed for step in range(length))
    if process == "drift":
        phase = rng.randrange(STATE_COUNT)
        return tuple((phase + step // 5) % STATE_COUNT for step in range(length))
    raise ValueError(f"unknown environmental process: {process}")


def generate_cues(
    seed: int, environment: tuple[int, ...], steps: int,
    cue_horizon: int, cue_accuracy: float,
) -> tuple[int, ...]:
    """Generate a cue about t+horizon, independently corrupting it at a set rate."""
    if steps < 1 or cue_horizon < 0 or steps + cue_horizon > len(environment):
        raise ValueError("invalid cue horizon or sequence length")
    if not math.isfinite(cue_accuracy) or not 0.0 <= cue_accuracy <= 1.0:
        raise ValueError("cue_accuracy must be finite and in [0, 1]")
    rng = random.Random(seed ^ 0x9E3779B9)
    cues = []
    for step in range(steps):
        target = environment[step + cue_horizon]
        if rng.random() < cue_accuracy:
            cues.append(target)
        else:
            cues.append(rng.choice(
                [candidate for candidate in range(STATE_COUNT) if candidate != target]
            ))
    return tuple(cues)


def environment_metrics(
    environment: tuple[int, ...], steps: int
) -> tuple[float, float]:
    """Return transition rate and normalized conditional transition entropy."""
    states = environment[:steps]
    if len(states) < 2:
        return 0.0, 0.0
    changes = sum(
        previous != current
        for previous, current in zip(states, states[1:], strict=False)
    )
    counts = [[0] * STATE_COUNT for _ in range(STATE_COUNT)]
    for previous, current in zip(states, states[1:], strict=False):
        counts[previous][current] += 1
    conditional_entropy = 0.0
    for row in counts:
        row_total = sum(row)
        if not row_total:
            continue
        row_entropy = -sum(
            (count / row_total) * math.log2(count / row_total)
            for count in row if count
        )
        conditional_entropy += row_total * row_entropy
    total = len(states) - 1
    return changes / total, conditional_entropy / total / math.log2(STATE_COUNT)


class PredictorCalibration:
    """Online accuracy estimate against the three-class chance baseline."""

    def __init__(self) -> None:
        self.successes = 0.0
        self.failures = 0.0

    def observe(self, correct: bool) -> None:
        self.successes = self.successes * CUE_RETENTION + float(correct)
        self.failures = self.failures * CUE_RETENTION + float(not correct)

    @property
    def skill(self) -> float:
        evidence = self.successes + self.failures
        confidence = evidence / (evidence + 2.0)
        reliability = (1.0 + self.successes) / (2.0 + evidence)
        chance_adjusted = max(
            0.0,
            (reliability - 1.0 / STATE_COUNT) / (1.0 - 1.0 / STATE_COUNT),
        )
        return min(1.0, confidence * chance_adjusted)


def simulate_trial(
    seed: int, *, steps: int, process: str, cue_accuracy: float,
    cue_horizon: int, development_latency: int, strategy: str,
    generalist_fitness: float = GENERALIST_FITNESS,
    mismatch_fitness: float = SPECIALIST_MISMATCH_FITNESS,
) -> BenchmarkResult:
    """Compare strategies with paired seeds and an explicit developmental delay."""
    if steps < 1 or cue_horizon < 0 or development_latency < 0:
        raise ValueError("steps must be positive and horizons/latency non-negative")
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    for name, value in (
        ("generalist_fitness", generalist_fitness),
        ("mismatch_fitness", mismatch_fitness),
    ):
        if not math.isfinite(value) or not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be finite and in (0, 1]")

    length = steps + max(cue_horizon, development_latency) + 1
    environment = generate_environment(seed, length, process)
    cues = generate_cues(seed, environment, steps, cue_horizon, cue_accuracy)
    transition = TransitionModel()
    cue_calibration = PredictorCalibration()
    history_calibration = PredictorCalibration()
    history_predictions: list[int] = []
    log_fitness = 0.0
    cue_hits = history_hits = 0
    plasticity_total = reserve_total = forecast_uncertainty_total = 0.0
    diversified_fitness = (
        1.0 + (STATE_COUNT - 1) * mismatch_fitness
    ) / STATE_COUNT

    for step in range(steps):
        if step > 0:
            transition.observe(environment[step - 1], environment[step])
        if development_latency > 0 and step >= development_latency:
            prior_decision = step - development_latency
            cue_calibration.observe(
                cues[prior_decision] == environment[step]
            )
            history_calibration.observe(
                history_predictions[prior_decision] == environment[step]
            )

        forecast = transition.forecast(environment[step], development_latency)
        history_state = max(
            range(STATE_COUNT), key=lambda state: (forecast[state], -state)
        )
        if development_latency == 0:
            cue_calibration.observe(cues[step] == environment[step])
            history_calibration.observe(history_state == environment[step])
        forecast_uncertainty = transition.normalized_entropy(forecast)
        history_predictions.append(history_state)
        cue_skill = cue_calibration.skill
        history_skill = history_calibration.skill
        best_predictor_skill = max(cue_skill, history_skill)
        residual_uncertainty = 1.0 - best_predictor_skill
        cue_advantage = max(0.0, cue_skill - history_skill)
        cue_advantage /= max(1e-9, 1.0 - history_skill)
        cue_advantage = min(1.0, cue_advantage)

        if strategy == "generalist":
            plasticity, reserve, mode = 0.0, 0.0, "generalist"
        elif strategy == "plastic":
            plasticity, reserve, mode = 1.0, 0.0, "cue"
        elif strategy == "hedge":
            plasticity, reserve, mode = 1.0, 0.5, "cue"
        elif strategy == "history":
            plasticity, reserve, mode = 0.0, 0.0, "history"
        elif strategy == "adaptive":
            plasticity = 0.95 * cue_advantage
            reserve = 0.02 + 0.75 * residual_uncertainty**2
            mode = "combined"
        elif strategy == "adaptive_plasticity":
            plasticity = 0.95 * cue_advantage
            reserve, mode = 0.0, "combined"
        else:
            plasticity = 0.0
            reserve = 0.02 + 0.75 * (1.0 - history_skill) ** 2
            mode = "history"

        target = environment[step + development_latency]
        cue = cues[step]
        cue_hits += int(cue == target)
        history_hits += int(history_state == target)
        cue_fitness = 1.0 if cue == target else mismatch_fitness
        history_fitness = 1.0 if history_state == target else mismatch_fitness

        if mode == "generalist":
            portfolio_fitness = generalist_fitness
        elif mode == "cue":
            portfolio_fitness = (
                (1.0 - reserve) * cue_fitness + reserve * diversified_fitness
            )
        elif mode == "history":
            portfolio_fitness = (
                (1.0 - reserve) * history_fitness + reserve * diversified_fitness
            )
        else:
            directed = plasticity * cue_fitness + (1.0 - plasticity) * history_fitness
            portfolio_fitness = (
                (1.0 - reserve) * directed + reserve * diversified_fitness
            )

        cost = 1.0 - 0.02 * plasticity - 0.01 * reserve
        log_fitness += math.log(max(1e-12, portfolio_fitness * cost))
        plasticity_total += plasticity
        reserve_total += reserve
        forecast_uncertainty_total += forecast_uncertainty

    change_rate, entropy = environment_metrics(
        environment, steps + development_latency
    )
    return BenchmarkResult(
        strategy=strategy,
        geometric_mean_fitness=math.exp(log_fitness / steps),
        cue_accuracy_at_response=cue_hits / steps,
        history_forecast_accuracy=history_hits / steps,
        mean_plasticity=plasticity_total / steps,
        mean_diversity_reserve=reserve_total / steps,
        mean_forecast_uncertainty=forecast_uncertainty_total / steps,
        environmental_change_rate=change_rate,
        transition_entropy=entropy,
    )


def run() -> None:
    scenarios = (
        ("stable_reliable", "stable", 0.95, 0, 2),
        ("stable_noisy", "stable", 0.55, 0, 2),
        ("cycle_anticipatory", "cycle", 0.95, 2, 2),
        ("cycle_current_only", "cycle", 0.95, 0, 2),
        ("stochastic_weak_cue", "stochastic", 0.40, 2, 2),
        ("abrupt_current_only", "abrupt", 0.95, 0, 3),
        ("gradual_drift", "drift", 0.90, 3, 3),
    )
    for name, process, accuracy, cue_horizon, latency in scenarios:
        print(f"\n{name}: process={process}, cue_horizon={cue_horizon}, latency={latency}")
        for strategy in STRATEGIES:
            results = [
                simulate_trial(
                    seed, steps=500, process=process, cue_accuracy=accuracy,
                    cue_horizon=cue_horizon, development_latency=latency,
                    strategy=strategy,
                )
                for seed in range(30)
            ]
            fitness_mean = statistics.fmean(
                result.geometric_mean_fitness for result in results
            )
            cue_mean = statistics.fmean(
                result.cue_accuracy_at_response for result in results
            )
            history_mean = statistics.fmean(
                result.history_forecast_accuracy for result in results
            )
            plasticity_mean = statistics.fmean(
                result.mean_plasticity for result in results
            )
            reserve_mean = statistics.fmean(
                result.mean_diversity_reserve for result in results
            )
            forecast_uncertainty_mean = statistics.fmean(
                result.mean_forecast_uncertainty for result in results
            )
            volatility_mean = statistics.fmean(
                result.environmental_change_rate for result in results
            )
            entropy_mean = statistics.fmean(
                result.transition_entropy for result in results
            )
            print(
                f"  {strategy:22s} fitness={fitness_mean:.4f} "
                f"cue={cue_mean:.3f} history={history_mean:.3f} "
                f"plasticity={plasticity_mean:.3f} reserve={reserve_mean:.3f} "
                f"forecast_uncertainty={forecast_uncertainty_mean:.3f} "
                f"volatility={volatility_mean:.3f} entropy={entropy_mean:.3f}"
            )


if __name__ == "__main__":
    run()
