# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import statistics

import pytest

from experiments.neuraldna_spatial_communication_benchmark import (
    SPATIAL_STRATEGIES,
    build_topology,
    simulate_spatial_trial,
)


def trial(seed, **overrides):
    parameters = {
        "steps": 240,
        "region_processes": ("stochastic",) * 4,
        "region_clusters": (0,) * 4,
        "topology": "clustered",
        "cue_accuracy": 0.80,
        "development_latency": 2,
        "communication_latency": 2,
        "signal_anticipation": 2,
        "strategy": "adaptive_network",
    }
    parameters.update(overrides)
    return simulate_spatial_trial(seed, **parameters)


def test_topologies_have_expected_undirected_connectivity():
    assert build_topology(4, "line", (0, 0, 0, 0)) == (
        (1,), (0, 2), (1, 3), (2,)
    )
    assert build_topology(4, "ring", (0, 0, 0, 0)) == (
        (1, 3), (0, 2), (1, 3), (0, 2)
    )
    assert build_topology(4, "complete", (0, 0, 0, 0)) == (
        (1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)
    )


def test_clustered_topology_does_not_cross_niche_boundaries():
    adjacency = build_topology(6, "clustered", (0, 0, 0, 1, 1, 1))
    assert adjacency == ((1, 2), (0, 2), (0, 1), (4, 5), (3, 5), (3, 4))
    assert all(
        (index < 3) == (neighbor < 3)
        for index, neighbors in enumerate(adjacency)
        for neighbor in neighbors
    )


def test_spatial_trial_is_reproducible():
    assert trial(19) == trial(19)


def test_all_strategies_return_bounded_metrics():
    for strategy in SPATIAL_STRATEGIES:
        result = trial(7, strategy=strategy)
        assert 0.0 < result.geometric_mean_fitness <= 1.0
        for metric in (
            result.local_cue_accuracy,
            result.global_signal_accuracy,
            result.neighbor_signal_accuracy,
            result.history_accuracy,
            result.selected_accuracy,
            result.global_signal_usage,
            result.neighbor_signal_usage,
            result.packet_delivery_rate,
            result.regional_divergence,
        ):
            assert 0.0 <= metric <= 1.0
        assert result.mean_degree >= 0.0


def test_neighbor_aggregation_improves_signal_quality_in_shared_niche():
    results = [
        trial(
            seed,
            cue_accuracy=0.80,
            strategy="neighbor_signal",
        )
        for seed in range(16)
    ]
    local = statistics.fmean(item.local_cue_accuracy for item in results)
    neighbor = statistics.fmean(item.neighbor_signal_accuracy for item in results)
    assert neighbor > local + 0.08


def test_local_neighborhood_preserves_cluster_specific_signals():
    common = {
        "region_processes": ("cycle",) * 8,
        "region_clusters": (0, 0, 0, 0, 1, 1, 1, 1),
        "cue_accuracy": 0.98,
        "steps": 240,
    }
    local_results = [
        trial(seed, **common, topology="clustered", strategy="neighbor_signal")
        for seed in range(12)
    ]
    global_results = [
        trial(seed, **common, topology="complete", strategy="global_signal")
        for seed in range(12)
    ]
    local_accuracy = statistics.fmean(
        item.neighbor_signal_accuracy for item in local_results
    )
    global_accuracy = statistics.fmean(
        item.global_signal_accuracy for item in global_results
    )
    assert local_accuracy > global_accuracy + 0.20


def test_complete_network_mixes_distinct_niches():
    result = trial(
        4,
        region_processes=("cycle",) * 8,
        region_clusters=(0, 0, 0, 0, 1, 1, 1, 1),
        topology="complete",
        strategy="global_signal",
        cue_accuracy=0.98,
        steps=180,
    )
    assert result.regional_divergence > 0.55
    assert result.global_signal_accuracy < 0.75


def test_full_message_loss_disables_neighbor_usage():
    result = trial(
        11,
        strategy="neighbor_signal",
        message_loss=1.0,
    )
    assert result.neighbor_signal_usage == 0.0
    assert result.packet_delivery_rate == 0.0


def test_adaptive_policy_can_use_neighbors_when_they_are_predictive():
    results = [
        trial(
            seed,
            strategy="adaptive_network",
            cue_accuracy=0.70,
        )
        for seed in range(16)
    ]
    usage = statistics.fmean(item.neighbor_signal_usage for item in results)
    assert usage > 0.10


def test_signal_anticipation_compensates_for_transport_delay():
    stale = [
        trial(
            seed,
            strategy="neighbor_signal",
            region_processes=("cycle",) * 4,
            cue_accuracy=0.99,
            signal_anticipation=0,
            steps=180,
        )
        for seed in range(8)
    ]
    compensated = [
        trial(
            seed,
            strategy="neighbor_signal",
            region_processes=("cycle",) * 4,
            cue_accuracy=0.99,
            signal_anticipation=2,
            steps=180,
        )
        for seed in range(8)
    ]
    stale_accuracy = statistics.fmean(item.neighbor_signal_accuracy for item in stale)
    compensated_accuracy = statistics.fmean(
        item.neighbor_signal_accuracy for item in compensated
    )
    assert compensated_accuracy > stale_accuracy + 0.40


def test_single_region_has_no_self_communication():
    result = trial(
        3,
        region_processes=("stable",),
        region_clusters=(0,),
        topology="ring",
        strategy="neighbor_signal",
    )
    assert result.mean_degree == 0.0
    assert result.neighbor_signal_usage == 0.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"steps": 1},
        {"region_processes": ()},
        {"region_clusters": (0,)},
        {"region_clusters": (-1, 0, 0, 0)},
        {"topology": "unknown"},
        {"development_latency": -1},
        {"communication_latency": -1},
        {"signal_anticipation": -1},
        {"cue_accuracy": 1.1},
        {"message_loss": -0.1},
        {"message_loss": 1.1},
        {"communication_cost": 1.0},
        {"strategy": "unknown"},
    ],
)
def test_invalid_spatial_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        trial(1, **overrides)
