# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import statistics

import pytest

from experiments.neuraldna_regional_niche_benchmark import (
    REGIONAL_STRATEGIES,
    simulate_regional_trial,
)


def trial(seed, **overrides):
    parameters = {
        "steps": 240,
        "region_processes": ("cycle", "stable", "stochastic", "drift"),
        "cue_accuracy": 0.95,
        "development_latency": 2,
        "communication_latency": 2,
        "signal_anticipation": 2,
        "strategy": "adaptive_network",
    }
    parameters.update(overrides)
    return simulate_regional_trial(seed, **parameters)


def test_regional_trial_is_reproducible():
    assert trial(17) == trial(17)


def test_all_regional_strategies_return_bounded_metrics():
    for strategy in REGIONAL_STRATEGIES:
        result = trial(5, strategy=strategy)
        assert 0.0 < result.geometric_mean_fitness <= 1.0
        for metric in (
            result.local_cue_accuracy,
            result.global_signal_accuracy,
            result.local_history_accuracy,
            result.mean_selected_accuracy,
            result.mean_global_signal_usage,
            result.mean_plasticity,
            result.mean_diversity_reserve,
            result.regional_divergence,
        ):
            assert 0.0 <= metric <= 1.0


def test_local_cues_outperform_shared_signal_in_divergent_niches():
    results = [
        trial(seed, strategy="local_cue")
        for seed in range(12)
    ]
    local_accuracy = statistics.fmean(
        result.local_cue_accuracy for result in results
    )
    shared_accuracy = statistics.fmean(
        result.global_signal_accuracy for result in results
    )
    assert local_accuracy > shared_accuracy + 0.15


def test_shared_signal_aggregates_noise_in_a_common_niche():
    results = [
        trial(
            seed,
            region_processes=("stochastic", "stochastic", "stochastic", "stochastic"),
            strategy="global_signal",
            cue_accuracy=0.80,
        )
        for seed in range(12)
    ]
    local_accuracy = statistics.fmean(
        result.local_cue_accuracy for result in results
    )
    shared_accuracy = statistics.fmean(
        result.global_signal_accuracy for result in results
    )
    assert shared_accuracy > local_accuracy + 0.05


def test_adaptive_network_uses_shared_signal_only_when_it_adds_value():
    shared = [
        trial(
            seed,
            region_processes=("stochastic", "stochastic", "stochastic", "stochastic"),
        )
        for seed in range(12)
    ]
    divergent = [trial(seed) for seed in range(12)]
    shared_usage = statistics.fmean(
        result.mean_global_signal_usage for result in shared
    )
    divergent_usage = statistics.fmean(
        result.mean_global_signal_usage for result in divergent
    )
    assert shared_usage > divergent_usage + 0.25


def test_communication_delay_requires_matching_signal_anticipation():
    stale = [
        trial(
            seed,
            region_processes=("cycle", "cycle", "cycle", "cycle"),
            strategy="global_signal",
            signal_anticipation=0,
            cue_accuracy=0.99,
        )
        for seed in range(8)
    ]
    compensated = [
        trial(
            seed,
            region_processes=("cycle", "cycle", "cycle", "cycle"),
            strategy="global_signal",
            signal_anticipation=2,
            cue_accuracy=0.99,
        )
        for seed in range(8)
    ]
    stale_accuracy = statistics.fmean(
        result.global_signal_accuracy for result in stale
    )
    compensated_accuracy = statistics.fmean(
        result.global_signal_accuracy for result in compensated
    )
    assert compensated_accuracy > stale_accuracy + 0.5


@pytest.mark.parametrize(
    "overrides",
    [
        {"steps": 1},
        {"region_processes": ()},
        {"development_latency": -1},
        {"communication_latency": -1},
        {"signal_anticipation": -1},
        {"cue_accuracy": 1.1},
        {"communication_cost": 1.0},
        {"strategy": "unknown"},
    ],
)
def test_invalid_regional_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        trial(1, **overrides)
