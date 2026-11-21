# Copyright © 2026 K410Sh4. All rights reserved.
# SPDX-License-Identifier: LicenseRef-AILocal-Universal-Proprietary
import itertools
import pytest
from neural_dna import DevelopmentGenome, NeuralStemCell
from neural_dna.lineage import LineagePolicy, RegionalNiche, advance_region

def genome(cost=1.0):
    return DevelopmentGenome(((1,0,0),(0,1,0),(0,0,1)), resource_cost=cost)
def cells(n=10):
    return [NeuralStemCell() for _ in range(n)]
def niche(demand=(1,0,0), resource=100, capacity=100, activity=1):
    return RegionalNiche("region-a", demand, activity, resource, capacity)

def test_seeded_run_is_reproducible():
    args=(genome(),niche(),cells())
    assert advance_region(*args,seed=42)==advance_region(*args,seed=42)
def test_regions_can_commit_to_different_fates():
    a=advance_region(genome(),niche((1,0,0)),cells(),seed=3)
    b=advance_region(genome(),RegionalNiche("region-b",(0,1,0),1,100,100),cells(),seed=3)
    assert a.differentiated[0]>0 and b.differentiated[1]>0
def test_zero_demand_prevents_activation():
    result=advance_region(genome(),niche((0,0,0)),cells())
    assert result.divisions==0 and result.progenitors==tuple(cells())
def test_resource_caps_division_count():
    result=advance_region(genome(2),niche(resource=5),cells(),seed=1)
    assert result.divisions<=2 and result.resource_used<=5
def test_capacity_is_never_exceeded():
    result=advance_region(genome(),niche(capacity=10),cells(10),seed=9)
    assert len(result.progenitors)<=10
def test_initial_population_over_capacity_rejected():
    with pytest.raises(ValueError):
        advance_region(genome(),niche(capacity=2),cells(3))
def test_division_limit_is_enforced():
    policy=LineagePolicy(activation_rate=1,activation_half_saturation=.01,crowding_feedback=0,max_divisions_per_step=3)
    result=advance_region(genome(),niche(),cells(10),policy,seed=1)
    assert result.divisions<=3
def test_max_lineage_depth_stops_activation():
    result=advance_region(genome(),niche(),cells(),LineagePolicy(max_lineage_depth=0),seed=1)
    assert result.divisions==0
def test_crowding_reduces_activation():
    policy=LineagePolicy(crowding_feedback=1)
    sparse=advance_region(genome(),niche(capacity=100),cells(10),policy)
    full=advance_region(genome(),niche(capacity=10),cells(10),policy)
    assert full.activation_probability<=sparse.activation_probability
def test_demand_pressure_reduces_self_renewal():
    policy=LineagePolicy(differentiation_pressure=.5)
    low=advance_region(genome(),niche((.1,0,0)),cells(),policy)
    high=advance_region(genome(),niche((1,0,0)),cells(),policy)
    assert high.self_renewal_probability<=low.self_renewal_probability
def test_population_and_resource_accounting():
    initial=cells(25)
    result=advance_region(genome(),niche(resource=7,capacity=40),initial,seed=11)
    assert result.divisions<=7 and result.resource_used<=7
    assert len(result.progenitors)+result.differentiated_total==len(initial)+result.divisions
@pytest.mark.parametrize("bad",[-.1,1.1,float("nan"),float("inf")])
def test_policy_rejects_invalid_probabilities(bad):
    with pytest.raises(ValueError):
        LineagePolicy(activation_rate=bad)
def test_parameter_sweep_preserves_invariants():
    combinations=itertools.product([0,1,5,10],[0,.1,.5,1],[0,.5,1],[0,1,5,20],
        [10,20],[0,.2,.7,1],[0,.5,1],[0,.5,1],[0,.25,.5],[0,.25,.5],[.1,1,3])
    checked=0
    for n,demand,activity,resource,capacity,activation,crowding,base,homeostasis,pressure,cost in combinations:
        if n>capacity: continue
        policy=LineagePolicy(activation_rate=activation,crowding_feedback=crowding,
            base_self_renewal=base,homeostatic_self_renewal=homeostasis,
            differentiation_pressure=pressure)
        result=advance_region(genome(cost),RegionalNiche("sweep",(demand,0,0),activity,resource,capacity),
            cells(n),policy,seed=13)
        assert len(result.progenitors)<=capacity
        assert result.divisions<=n and result.resource_used<=resource+1e-9
        assert len(result.progenitors)+result.differentiated_total==n+result.divisions
        checked+=1
    assert checked>1000


def test_capacity_pressure_preserves_unselected_resident_progenitors():
    policy = LineagePolicy(
        activation_rate=1.0,
        activation_half_saturation=0.01,
        crowding_feedback=0.0,
        base_self_renewal=1.0,
        homeostatic_self_renewal=0.0,
        differentiation_pressure=0.0,
        max_lineage_depth=1,
    )
    resident = NeuralStemCell(potency=0.7, lineage_depth=1)
    dividing = NeuralStemCell(potency=1.0, lineage_depth=0)
    result = advance_region(
        genome(), niche(capacity=2), [dividing, resident], policy, seed=7
    )
    assert resident in result.progenitors
    assert len(result.progenitors) == 2
    assert result.differentiated_total == 1
    assert len(result.progenitors) + result.differentiated_total == 3
