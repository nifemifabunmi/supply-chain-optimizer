from dataclasses import replace
from itertools import combinations

import pytest

from src.baseline import warehouse_loads
from src.data import build_instance, generate_instance
from src.lp_model import solve_transportation
from src.milp_model import OK_STATUSES, TINY, fixed_cost_sweep, solve_facility_location


def tiny_instance(cap_w1, cap_w2, fixed_w1, fixed_w2):
    """The small 2-warehouse, 3-region example worked out by hand.

    Cost per unit:      W1     W2
                R1    $1.00  $4.00      Demand: R1 = 100, R2 = 50, R3 = 80
                R2    $3.00  $2.00      (total 230)
                R3    $4.50  $0.50
    """
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": fixed_w1, "W2": fixed_w2},
        rate=0.5,
    )


# Worked out by hand, with both capacities at 250 (each can cover all 230 units):
#   W1 only : shipping 100*1 + 50*3 + 80*4.5 = 610, plus W1's opening cost
#   W2 only : shipping 100*4 + 50*2 + 80*0.5 = 540, plus W2's opening cost
#   both    : shipping 100*1 + 50*2 + 80*0.5 = 240, plus both opening costs


def test_very_expensive_w2_is_closed():
    # W1 only: 610 + 100 = 710.
    sol = solve_facility_location(tiny_instance(250, 150, 100, 10_000))
    assert sol.status in OK_STATUSES
    assert sol.open_warehouses == ["W1"]
    assert sol.transport_total == pytest.approx(610.0)
    assert sol.total_cost == pytest.approx(710.0)
    assert all(i == "W1" for (i, _j) in sol.shipments)


def test_very_expensive_w1_is_closed():
    # W2 only: 540 + 100 = 640.
    sol = solve_facility_location(tiny_instance(150, 250, 10_000, 100))
    assert sol.open_warehouses == ["W2"]
    assert sol.transport_total == pytest.approx(540.0)
    assert sol.total_cost == pytest.approx(640.0)


def test_opens_both_when_the_second_pays_for_itself():
    # With W1 at 100 and W2 at 300: both = 240 + 400 = 640, W1 only = 710. Both wins.
    sol = solve_facility_location(tiny_instance(250, 250, 100, 300))
    assert sorted(sol.open_warehouses) == ["W1", "W2"]
    assert sol.total_cost == pytest.approx(640.0)


def test_break_even_flips_the_decision():
    # Opening W2 saves 610 - 240 = 370 in shipping. So W2 is worth opening only
    # if its opening cost is below 370.
    below = solve_facility_location(tiny_instance(250, 250, 100, 369))
    above = solve_facility_location(tiny_instance(250, 250, 100, 371))
    assert sorted(below.open_warehouses) == ["W1", "W2"]
    assert above.open_warehouses == ["W1"]


def test_free_opening_matches_the_lp():
    # If opening costs nothing, the best plan is just the Stage 2 LP plan.
    inst = tiny_instance(150, 150, 0, 0)
    assert solve_facility_location(inst).total_cost == pytest.approx(
        solve_transportation(inst).cost
    )


def check_plan_is_valid(inst, sol):
    """Demand met, capacity respected, and closed warehouses ship nothing."""
    received = {j: 0.0 for j in inst.regions}
    for (_i, j), units in sol.shipments.items():
        received[j] += units
    for j in inst.regions:
        assert received[j] == pytest.approx(inst.demand[j], abs=1e-4)

    loads = warehouse_loads(inst, sol.shipments)
    for i in inst.warehouses:
        if i in sol.open_warehouses:
            assert loads[i] <= inst.capacity[i] + 1e-4
        else:
            assert loads[i] == pytest.approx(0.0, abs=1e-4)

    assert all(units >= -TINY for units in sol.shipments.values())


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_plan_is_valid_on_random_networks(seed):
    inst = generate_instance(seed=seed)
    sol = solve_facility_location(inst)
    assert sol.status in OK_STATUSES
    check_plan_is_valid(inst, sol)

    # The total matches a separate calculation.
    fixed = sum(inst.fixed_cost[i] for i in sol.open_warehouses)
    shipping = sum(inst.cost[pair] * units for pair, units in sol.shipments.items())
    assert sol.total_cost == pytest.approx(fixed + shipping)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_milp_is_never_worse_than_opening_everything(seed):
    # Opening every warehouse is one valid option, so the best plan can't cost more.
    inst = generate_instance(seed=seed)
    all_open_total = solve_transportation(inst).cost + sum(inst.fixed_cost.values())
    sol = solve_facility_location(inst)
    assert sol.total_cost <= all_open_total + 1e-6


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_closing_warehouses_never_makes_shipping_cheaper(seed):
    # The LP can use every warehouse, so its shipping cost is a lower bound.
    inst = generate_instance(seed=seed)
    sol = solve_facility_location(inst)
    assert sol.transport_total >= solve_transportation(inst).cost - 1e-6


def test_sweep_with_zero_multiplier_matches_the_lp():
    inst = generate_instance(seed=42)
    (m, sol), = fixed_cost_sweep(inst, [0])
    assert m == 0
    assert sol.total_cost == pytest.approx(solve_transportation(inst).cost)


def best_by_trying_every_combination(inst):
    """Slow but simple check: solve the LP for every set of open warehouses.

    Returns (lowest total cost, names of the warehouses open in that plan).
    """
    best = None
    total_demand = sum(inst.demand.values())
    for k in range(1, len(inst.warehouses) + 1):
        for chosen in combinations(inst.warehouses, k):
            if sum(inst.capacity[i] for i in chosen) < total_demand:
                continue  # these warehouses cannot cover demand
            # Closed warehouses get capacity 0, so the LP cannot use them.
            capacity = {i: (inst.capacity[i] if i in chosen else 0) for i in inst.warehouses}
            plan = solve_transportation(replace(inst, capacity=capacity))
            total = plan.cost + sum(inst.fixed_cost[i] for i in chosen)
            if best is None or total < best[0]:
                best = (total, sorted(chosen))
    return best


@pytest.mark.parametrize("seed", [3, 5])
def test_matches_trying_every_combination(seed):
    # A smaller network (4 warehouses = 15 combinations) keeps this check quick.
    inst = generate_instance(seed=seed, n_warehouses=4, n_regions=8)
    best_total, best_open = best_by_trying_every_combination(inst)
    sol = solve_facility_location(inst)
    assert sol.total_cost == pytest.approx(best_total, abs=1e-4)
    assert sorted(sol.open_warehouses) == best_open
