# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import statistics

import pytest

from experiments.neuraldna_field_coupled_adaptation import (
    FIELD_STRATEGIES,
    simulate_field_adaptation_trial,
)


def trial(seed, **overrides):
    parameters = {
        "steps": 180,
        "region_processes": ("stable",) * 8,
        "region_clusters": (0,) * 8,
        "cue_accuracy": 0.80,
        "development_latency": 2,
        "strategy": "adaptive_field",
        "diffusion": 0.25,
        "degradation": 0.10,
        "uptake_vmax": 0.0,
        "uptake_km": 0.5,
        "sensitivity_kd": 0.2,
        "hill_coefficient": 2.0,
        "exposure_clearance": 0.4,
    }
    parameters.update(overrides)
    return simulate_field_adaptation_trial(seed, **parameters)


def test_field_adaptation_is_reproducible():
    assert trial(13) == trial(13)


def test_all_strategies_return_bounded_metrics():
    for strategy in FIELD_STRATEGIES:
        result = trial(7, strategy=strategy)
        assert 0.0 < result.geometric_mean_fitness <= 1.0
        for metric in (
            result.local_cue_accuracy,
            result.history_accuracy,
            result.global_accuracy,
            result.neighbor_accuracy,
            result.field_accuracy,
            result.selected_accuracy,
            result.field_usage,
            result.regional_divergence,
        ):
            assert 0.0 <= metric <= 1.0
        assert result.mean_field_mass >= 0.0
        assert result.field_recovery_lag >= 0.0


def test_field_pooling_improves_noisy_cues_in_a_shared_stable_niche():
    results = [
        trial(
            seed,
            strategy="field_only",
            cue_accuracy=0.70,
            diffusion=0.25,
            degradation=0.10,
            exposure_clearance=0.4,
        )
        for seed in range(16)
    ]
    local = statistics.fmean(item.local_cue_accuracy for item in results)
    field = statistics.fmean(item.field_accuracy for item in results)
    assert field > local + 0.10


def test_closed_niche_boundary_preserves_local_field_signals():
    common = {
        "region_processes": ("stable",) * 8,
        "region_clusters": (0, 1, 0, 1, 0, 1, 0, 1),
        "cue_accuracy": 0.95,
        "strategy": "field_only",
        "diffusion": 4.0,
        "degradation": 0.005,
        "exposure_clearance": 0.4,
    }
    closed = [
        trial(seed, **common, boundary_permeability=0.0)
        for seed in range(12)
    ]
    open_boundary = [
        trial(seed, **common, boundary_permeability=1.0)
        for seed in range(12)
    ]
    closed_accuracy = statistics.fmean(item.field_accuracy for item in closed)
    open_accuracy = statistics.fmean(
        item.field_accuracy for item in open_boundary
    )
    assert closed_accuracy > open_accuracy + 0.20


def test_field_controller_reduces_use_when_field_is_uninformative():
    results = [
        trial(
            seed,
            strategy="adaptive_field",
            region_clusters=(0, 1, 0, 1, 0, 1, 0, 1),
            cue_accuracy=0.95,
            diffusion=4.0,
            degradation=0.005,
            boundary_permeability=1.0,
        )
        for seed in range(12)
    ]
    usage = statistics.fmean(item.field_usage for item in results)
    assert usage < 0.25


def test_fast_removal_recovers_from_abrupt_shift_faster_than_slow_removal():
    common = {
        "region_processes": ("abrupt",) * 8,
        "cue_accuracy": 0.95,
        "strategy": "field_only",
        "diffusion": 0.25,
        "uptake_km": 0.5,
        "sensitivity_kd": 0.2,
        "hill_coefficient": 2.0,
    }
    slow = [
        trial(
            seed,
            **common,
            degradation=0.02,
            uptake_vmax=0.0,
            exposure_clearance=0.02,
        )
        for seed in range(10)
    ]
    fast = [
        trial(
            seed,
            **common,
            degradation=0.80,
            uptake_vmax=0.5,
            exposure_clearance=0.80,
        )
        for seed in range(10)
    ]
    slow_lag = statistics.fmean(item.field_recovery_lag for item in slow)
    fast_lag = statistics.fmean(item.field_recovery_lag for item in fast)
    assert fast_lag < slow_lag


def test_zero_source_strength_disables_field_use():
    result = trial(
        5,
        strategy="field_only",
        source_strength=0.0,
    )
    assert result.field_usage == 0.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"steps": 1},
        {"region_processes": ()},
        {"region_clusters": (0,)},
        {"region_clusters": (-1, 0, 0, 0, 0, 0, 0, 0)},
        {"cue_accuracy": 1.1},
        {"development_latency": -1},
        {"strategy": "unknown"},
        {"diffusion": -0.1},
        {"degradation": -0.1},
        {"uptake_vmax": -0.1},
        {"uptake_km": 0.0},
        {"sensitivity_kd": 0.0},
        {"hill_coefficient": 0.0},
        {"exposure_clearance": -0.1},
        {"boundary_permeability": 1.1},
        {"source_strength": -0.1},
        {"exposure_threshold": -0.1},
        {"field_cost": 1.0},
        {"discrete_cost": 1.0},
    ],
)
def test_invalid_field_adaptation_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        trial(1, **overrides)
