# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import math

import pytest

from experiments.neuraldna_morphogen_signal_field import (
    SignalEdge,
    SignalField,
    SignalFieldConfig,
)


def line_edges(region_count, permeability=1.0):
    return tuple(
        SignalEdge(index, index + 1, 1.0, permeability)
        for index in range(region_count - 1)
    )


def source(region_count, amount=1.0):
    return ((amount,),) + ((0.0,),) * (region_count - 1)


def make_field(region_count=5, **overrides):
    parameters = {
        "time_step": 1.0,
        "diffusion": 0.2,
        "degradation": 0.0,
        "uptake_vmax": 0.0,
        "uptake_km": 1.0,
        "sensitivity_kd": 1.0,
        "hill_coefficient": 2.0,
        "exposure_clearance": 0.1,
    }
    parameters.update(overrides)
    return SignalField(
        region_count,
        1,
        line_edges(region_count),
        SignalFieldConfig(**parameters),
    )


def test_zero_diffusion_keeps_signal_at_its_source():
    field = make_field(4, diffusion=0.0)
    result = field.step(source(4))
    assert result.concentrations == ((1.0,), (0.0,), (0.0,), (0.0,))


def test_symmetric_diffusion_conserves_mass_without_sources_or_sinks():
    field = make_field(5, diffusion=0.8)
    field.step(source(5))
    before = field.snapshot().total_mass
    result = field.step(((0.0,),) * 5)
    assert result.total_mass == pytest.approx(before, abs=1e-12)
    assert result.diffusion_substeps > 1


def test_localized_source_forms_a_decreasing_concentration_gradient():
    field = make_field(6, diffusion=0.25, degradation=0.08)
    for _ in range(120):
        result = field.step(source(6))
    profile = tuple(row[0] for row in result.concentrations)
    assert all(left > right for left, right in zip(profile[:-1], profile[1:], strict=True))


def test_higher_transport_increases_far_field_reach():
    low = make_field(8, diffusion=0.03, degradation=0.02)
    high = make_field(8, diffusion=0.50, degradation=0.02)
    for _ in range(24):
        low_result = low.step(source(8))
        high_result = high.step(source(8))
    assert high_result.concentrations[-1][0] > low_result.concentrations[-1][0]


def test_degradation_reduces_total_field_mass():
    slow_decay = make_field(5, degradation=0.02)
    fast_decay = make_field(5, degradation=0.40)
    for _ in range(40):
        slow_result = slow_decay.step(source(5))
        fast_result = fast_decay.step(source(5))
    assert fast_result.total_mass < slow_result.total_mass


def test_saturable_uptake_reduces_field_mass():
    no_uptake = make_field(5, uptake_vmax=0.0)
    strong_uptake = make_field(5, uptake_vmax=0.8, uptake_km=0.2)
    for _ in range(30):
        no_uptake_result = no_uptake.step(source(5))
        uptake_result = strong_uptake.step(source(5))
    assert uptake_result.total_mass < no_uptake_result.total_mass


def test_zero_permeability_blocks_cross_niche_transport():
    edges = (
        SignalEdge(0, 1, 1.0, 1.0),
        SignalEdge(1, 2, 1.0, 0.0),
        SignalEdge(2, 3, 1.0, 1.0),
    )
    field = SignalField(
        4,
        1,
        edges,
        SignalFieldConfig(diffusion=0.5, degradation=0.0),
    )
    for _ in range(20):
        result = field.step(source(4))
    assert result.concentrations[2] == (0.0,)
    assert result.concentrations[3] == (0.0,)
    assert result.concentrations[1][0] > 0.0


def test_receiver_sensitivity_changes_response_without_changing_concentration():
    field = SignalField(
        2,
        1,
        (),
        SignalFieldConfig(
            diffusion=0.0,
            degradation=0.0,
            uptake_vmax=0.0,
            sensitivity_kd=(0.1, 10.0),
            hill_coefficient=(2.0, 2.0),
        ),
    )
    result = field.step(((1.0,), (1.0,)))
    assert result.concentrations[0] == result.concentrations[1]
    assert result.responses[0][0] > result.responses[1][0] + 0.90


def test_exposure_tracks_duration_not_only_peak_concentration():
    pulse = make_field(1, diffusion=0.0, sensitivity_kd=0.5, exposure_clearance=0.2)
    sustained = make_field(
        1, diffusion=0.0, sensitivity_kd=0.5, exposure_clearance=0.2
    )
    pulse.step(((2.0,),))
    for _ in range(4):
        pulse.step(((0.0,),))
        sustained.step(((0.4,),))
    pulse_exposure = pulse.snapshot().exposures[0][0]
    sustained_exposure = sustained.snapshot().exposures[0][0]
    assert pulse_exposure != pytest.approx(sustained_exposure, abs=1e-3)


def test_time_step_refinement_converges_for_diffusion_decay_and_source():
    coarse = make_field(
        3, time_step=0.25, diffusion=0.12, degradation=0.08
    )
    fine = make_field(
        3, time_step=0.125, diffusion=0.12, degradation=0.08
    )
    for _ in range(16):
        coarse_result = coarse.step(((1.0,), (0.0,), (0.0,)))
    for _ in range(32):
        fine_result = fine.step(((1.0,), (0.0,), (0.0,)))
    for coarse_row, fine_row in zip(
        coarse_result.concentrations, fine_result.concentrations, strict=True
    ):
        assert coarse_row[0] == pytest.approx(fine_row[0], abs=0.02)


def test_signal_classes_do_not_mix():
    field = SignalField(
        3,
        2,
        line_edges(3),
        SignalFieldConfig(diffusion=0.3, degradation=0.0, uptake_vmax=0.0),
    )
    for _ in range(12):
        result = field.step(((1.0, 0.0), (0.0, 0.0), (0.0, 0.0)))
    assert result.total_mass > 0.0
    assert all(row[1] == 0.0 for row in result.concentrations)


def test_field_values_remain_finite_and_non_negative_under_high_transport():
    field = make_field(
        8,
        diffusion=100.0,
        degradation=0.0,
        uptake_vmax=10.0,
        uptake_km=0.001,
    )
    for _ in range(12):
        result = field.step(source(8, amount=100.0))
    assert result.diffusion_substeps > 1
    assert all(
        math.isfinite(value) and value >= 0.0
        for row in result.concentrations
        for value in row
    )
    assert all(
        0.0 <= value <= 1.0
        for row in result.responses
        for value in row
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"time_step": 0.0},
        {"diffusion": -0.1},
        {"degradation": -0.1},
        {"uptake_vmax": -0.1},
        {"uptake_km": 0.0},
        {"sensitivity_kd": 0.0},
        {"hill_coefficient": 0.0},
        {"exposure_clearance": -0.1},
        {"max_substeps": 0},
        {"degradation": (0.1, 0.2)},
    ],
)
def test_invalid_field_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_field(3, **overrides)


@pytest.mark.parametrize(
    "edge",
    [
        SignalEdge(0, 0, 1.0),
        SignalEdge(0, 3, 1.0),
        SignalEdge(0, 1, 0.0),
        SignalEdge(0, 1, 1.0, 1.1),
        SignalEdge(0, 1, float("nan")),
    ],
)
def test_invalid_edges_are_rejected(edge):
    with pytest.raises(ValueError):
        SignalField(3, 1, (edge,), SignalFieldConfig())


def test_duplicate_undirected_edges_are_rejected():
    with pytest.raises(ValueError):
        SignalField(
            2,
            1,
            (SignalEdge(0, 1, 1.0), SignalEdge(1, 0, 1.0)),
            SignalFieldConfig(),
        )


@pytest.mark.parametrize(
    "production",
    [
        ((1.0,),),
        ((-1.0,), (0.0,)),
        ((float("nan"),), (0.0,)),
        ((float("inf"),), (0.0,)),
        ((1.0, 2.0), (0.0, 0.0)),
    ],
)
def test_invalid_production_is_rejected(production):
    field = SignalField(2, 1, line_edges(2), SignalFieldConfig())
    with pytest.raises(ValueError):
        field.step(production)


def test_unstable_transport_is_rejected_when_substep_budget_is_exceeded():
    field = make_field(8, diffusion=100.0, max_substeps=1)
    with pytest.raises(ValueError, match="max_substeps"):
        field.step(source(8))
