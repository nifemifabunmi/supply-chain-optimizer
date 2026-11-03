import pytest

from src.baseline import (
    capacity_aware_plan,
    capacity_violations,
    transport_cost,
    warehouse_loads,
)
from src.data import build_instance, generate_instance
from src.lp_model import solve_transportation


def tiny_instance(cap_w1=150, cap_w2=100):
    """The small 2-warehouse, 3-region example worked out by hand."""
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


def test_tiny_example_by_hand():
    # Biggest first: R1 (100) -> W1. R3 (80) -> W2, leaving W2 with 20 room.
    # R2 (50): 20 units from W2, then the other 30 from W1.
    # Cost: 100*1 + 80*0.5 + 20*2 + 30*3 = 100 + 40 + 40 + 90 = 270.
    inst = tiny_instance()
    ship = capacity_aware_plan(inst)
    assert ship == {("W1", "R1"): 100, ("W2", "R3"): 80, ("W2", "R2"): 20, ("W1", "R2"): 30}
    assert transport_cost(inst, ship) == pytest.approx(270.0)


def test_matches_naive_baseline_when_nothing_is_tight():
    # With room everywhere, it behaves like plain nearest-warehouse: $240.
    inst = tiny_instance(cap_w1=150, cap_w2=150)
    assert transport_cost(inst, capacity_aware_plan(inst)) == pytest.approx(240.0)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_plan_is_valid_on_random_networks(seed):
    inst = generate_instance(seed=seed)
    ship = capacity_aware_plan(inst)

    received = {j: 0 for j in inst.regions}
    for (_i, j), units in ship.items():
        received[j] += units
    assert received == inst.demand                 # every order filled exactly
    assert capacity_violations(inst, ship) == {}   # nobody over capacity


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_lp_is_never_worse_than_the_fair_baseline(seed):
    # Both plans are valid, so the LP (the true best) can only match or beat it.
    inst = generate_instance(seed=seed)
    fair = transport_cost(inst, capacity_aware_plan(inst))
    assert solve_transportation(inst).cost <= fair + 1e-6
