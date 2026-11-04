# detailed explanation
# this file tests stage 2: the transportation linear program (LP) and shadow prices.
# the LP picks how many units each warehouse ships to each region at the lowest
# total shipping cost, with every demand met and no warehouse over capacity.
#
# checks in this file:
#   1. the tiny hand-worked example (2 warehouses, 3 regions).
#      with room to spare the LP matches the baseline: $240.
#      when W2 is tight (capacity 100) 30 units of R2 must come from W1.
#      that costs $1 more per unit, so the answer is 240 + 30 = $270.
#   2. shadow prices on that same example. one extra unit of room at W2 saves $1,
#      and W1 has spare room so its price is 0.
#   3. random networks: every region gets its demand, no warehouse is over
#      capacity, no shipment is negative, and the reported cost matches a second
#      calculation done inside the test.
#   4. the LP never costs more than a valid baseline. if the plain baseline is
#      overloaded it is not valid, so it may be cheaper. then the LP only has to
#      be a valid plan itself.
import pytest

from src.baseline import (
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import build_instance, generate_instance
from src.lp_model import TINY, shadow_prices, solve_transportation


# the same small example as in test_baseline.py (worked out by hand)
def tiny_instance(cap_w1=150, cap_w2=150):
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


def test_lp_matches_baseline_when_capacity_is_not_a_problem():
    sol = solve_transportation(tiny_instance(150, 150))
    assert sol.status == "Optimal"
    assert sol.cost == pytest.approx(240.0)


def test_lp_moves_units_when_w2_is_tight():
    # by hand: W2 (capacity 100) serves R3 (80) and 20 units of R2.
    # the other 30 units of R2 go to W1, which costs $1 more per unit.
    # (moving R3 instead would cost $4 more per unit.) so 240 + 30 = 270.
    sol = solve_transportation(tiny_instance(150, 100))
    assert sol.status == "Optimal"
    assert sol.cost == pytest.approx(270.0)
    assert sol.shipments[("W1", "R2")] == pytest.approx(30.0)
    assert sol.shipments[("W2", "R2")] == pytest.approx(20.0)
    assert sol.shipments[("W2", "R3")] == pytest.approx(80.0)


def test_shadow_prices_on_the_tight_example():
    # one more unit at W2 saves one $1 move. W1 has spare room, so its price is 0.
    prices = shadow_prices(tiny_instance(150, 100))
    assert prices["W2"] == pytest.approx(1.0)
    assert prices["W1"] == pytest.approx(0.0)


# a plan is valid if every region gets its demand and no warehouse is over capacity
def check_plan_is_valid(inst, sol):
    received = {j: 0.0 for j in inst.regions}
    for (_i, j), units in sol.shipments.items():
        received[j] += units
    for j in inst.regions:
        assert received[j] == pytest.approx(inst.demand[j], abs=1e-4)

    loads = warehouse_loads(inst, sol.shipments)
    for i in inst.warehouses:
        assert loads[i] <= inst.capacity[i] + 1e-4

    assert all(units >= -TINY for units in sol.shipments.values())


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_plan_is_valid_on_random_networks(seed):
    inst = generate_instance(seed=seed)
    sol = solve_transportation(inst)
    assert sol.status == "Optimal"
    check_plan_is_valid(inst, sol)
    # the reported cost matches a separate calculation
    manual = sum(inst.cost[pair] * units for pair, units in sol.shipments.items())
    assert sol.cost == pytest.approx(manual)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_lp_is_never_worse_than_a_valid_baseline(seed):
    inst = generate_instance(seed=seed)
    plan = nearest_warehouse_plan(inst)
    shipments = shipments_from_plan(inst, plan)
    sol = solve_transportation(inst)
    if not capacity_violations(inst, shipments):
        # the baseline is a valid plan, so the LP can only match or beat it
        assert sol.cost <= transport_cost(inst, shipments) + 1e-6
    else:
        # an overloaded baseline is not a valid plan, so it can be cheaper
        # the LP only has to be valid
        check_plan_is_valid(inst, sol)
