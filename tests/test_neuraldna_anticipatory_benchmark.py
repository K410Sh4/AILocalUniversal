# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import statistics

import pytest

from experiments.neuraldna_anticipatory_benchmark import (
    STRATEGIES,
    environment_metrics,
    generate_environment,
    simulate_trial,
)


def trial(seed, **overrides):
    parameters = {
        "steps": 300,
        "process": "cycle",
        "cue_accuracy": 0.95,
        "cue_horizon": 1,
        "development_latency": 1,
        "strategy": "adaptive",
    }
    parameters.update(overrides)
    return simulate_trial(seed, **parameters)


def test_trial_is_reproducible():
    assert trial(17) == trial(17)


def test_all_strategies_return_bounded_metrics():
    for strategy in STRATEGIES:
        result = trial(5, strategy=strategy)
        assert 0.0 < result.geometric_mean_fitness <= 1.0
        assert 0.0 <= result.cue_accuracy_at_response <= 1.0
        assert 0.0 <= result.history_forecast_accuracy <= 1.0
        assert 0.0 <= result.mean_plasticity <= 1.0
        assert 0.0 <= result.mean_diversity_reserve <= 1.0
        assert 0.0 <= result.mean_forecast_uncertainty <= 1.0


def test_predictive_horizon_matches_development_latency():
    matched = [
        trial(seed, cue_horizon=1, development_latency=1)
        for seed in range(10)
    ]
    mismatched = [
        trial(seed, cue_horizon=0, development_latency=1)
        for seed in range(10)
    ]
    matched_accuracy = statistics.fmean(
        result.cue_accuracy_at_response for result in matched
    )
    mismatched_accuracy = statistics.fmean(
        result.cue_accuracy_at_response for result in mismatched
    )
    assert matched_accuracy > 0.85
    assert mismatched_accuracy < 0.15


def test_deterministic_cycle_is_volatile_but_predictable():
    cycle = generate_environment(2, 300, "cycle")
    stochastic = generate_environment(2, 300, "stochastic")
    cycle_change, cycle_entropy = environment_metrics(cycle, len(cycle))
    stochastic_change, stochastic_entropy = environment_metrics(
        stochastic, len(stochastic)
    )
    assert cycle_change > 0.95
    assert cycle_entropy < 0.01
    assert stochastic_change > 0.2
    assert stochastic_entropy > cycle_entropy + 0.3


def test_reserve_tracks_residual_forecast_uncertainty_not_change_rate():
    predictable = [
        trial(seed, process="cycle", cue_accuracy=0.95)
        for seed in range(10)
    ]
    unpredictable = [
        trial(
            seed,
            process="stochastic",
            cue_accuracy=0.40,
            cue_horizon=1,
            development_latency=1,
        )
        for seed in range(10)
    ]
    predictable_reserve = statistics.fmean(
        result.mean_diversity_reserve for result in predictable
    )
    unpredictable_reserve = statistics.fmean(
        result.mean_diversity_reserve for result in unpredictable
    )
    assert unpredictable_reserve > predictable_reserve


@pytest.mark.parametrize(
    "overrides",
    [
        {"steps": 0},
        {"cue_horizon": -1},
        {"development_latency": -1},
        {"cue_accuracy": 1.1},
        {"strategy": "unknown"},
    ],
)
def test_invalid_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        trial(1, **overrides)



def test_adaptive_prefers_the_predictor_with_higher_measured_skill():
    cue_leads = [
        trial(
            seed,
            process="drift",
            cue_accuracy=0.90,
            cue_horizon=3,
            development_latency=3,
        )
        for seed in range(10)
    ]
    history_leads = [
        trial(
            seed,
            process="cycle",
            cue_accuracy=0.95,
            cue_horizon=2,
            development_latency=2,
        )
        for seed in range(10)
    ]
    cue_led_plasticity = statistics.fmean(
        result.mean_plasticity for result in cue_leads
    )
    history_led_plasticity = statistics.fmean(
        result.mean_plasticity for result in history_leads
    )
    assert cue_led_plasticity > history_led_plasticity + 0.4
