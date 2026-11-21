# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import pytest
from neural_dna import DevelopmentGenome, Fate, NeuralStemCell, NicheState, develop_population

def make_genome():
    return DevelopmentGenome(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        differentiation_threshold=0.2, self_renewal_bias=0.1,
        activity_sensitivity=0.0, resource_cost=1.0)

def make_cells(count=5):
    return [NeuralStemCell() for _ in range(count)]

def test_niche_signal_selects_matching_fate():
    result = develop_population(make_genome(), NicheState((1, 0, 0)), make_cells())
    assert result.differentiated == (5, 0, 0)
    assert result.self_renewed == 0

def test_resource_budget_bounds_differentiation():
    result = develop_population(make_genome(), NicheState((0, 1, 0), available_resource=2), make_cells())
    assert result.differentiated == (0, 2, 0)
    assert result.self_renewed == 3
    assert result.resource_used == 2
    assert result.resource_remaining == 0

def test_low_activity_and_demand_preserve_progenitors():
    genome = DevelopmentGenome(((0, 0, 0),) * len(Fate),
        differentiation_threshold=0.4, self_renewal_bias=0.1, activity_sensitivity=0)
    result = develop_population(genome, NicheState((0, 0, 0)), make_cells())
    assert result.differentiated == (0, 0, 0)
    assert result.self_renewed == 5

def test_deterministic_for_identical_inputs():
    args = (make_genome(), NicheState((0, 0, 1)), make_cells())
    assert develop_population(*args) == develop_population(*args)

def test_genome_rejects_invalid_loci():
    with pytest.raises(ValueError):
        DevelopmentGenome(((1.2, 0, 0), (0, 1, 0), (0, 0, 1)))

def test_niche_rejects_invalid_resource():
    with pytest.raises(ValueError):
        NicheState((1, 0, 0), available_resource=-1)

def test_population_accounting_is_conserved():
    source = make_cells(17)
    result = develop_population(make_genome(), NicheState((0, 0, 1), available_resource=8), source)
    assert result.total == len(source)
    assert result.resource_used <= 8
