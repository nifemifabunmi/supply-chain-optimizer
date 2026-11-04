# detailed explanation
# this file tests the shortage model: a transportation LP where demand is allowed
# to go unmet, at a penalty per unmet unit (PENALTY, an assumed number).
# we need it because in the simulation a plan can face more demand than the open
# warehouses can ship, and a normal LP would just say "infeasible".
#
# the tiny example (2 warehouses, 3 regions) is solved by hand. cost per unit:
#              W1     W2
#       R1    $1.00  $4.00     demand: R1 = 100, R2 = 50, R3 = 80 (total 230)
#       R2    $3.00  $2.00
#       R3    $4.50  $0.50
# because the penalty is far bigger than any shipping cost, the model delivers as
# much as capacity allows and leaves unmet the units that are most expensive to serve.
#
# checks in this file:
#   1. enough capacity: nothing unmet, same $270 as stage 2.
#   2. capacity 100 + 100 vs demand 230: exactly 30 units unmet, all from R2.
#   3. only W1 open: 80 units unmet, all from R3 (the costliest to serve from W1).
#   4. no warehouses open: all 230 units unmet and no shipping cost.
#   5. a custom demand overrides the instance's demand.
#   6. on random networks with enough capacity it matches the plain LP, and it
#      matches the MILP's shipping on the MILP's own open set.
#   7. under a big demand jump the plan still respects capacity, and shipped
#      plus unmet units add up to demand in every region.
from dataclasses import replace

import pytest

from src.baseline import warehouse_loads
from src.data import build_instance, generate_instance
from src.lp_model import solve_transportation
from src.milp_model import solve_facility_location
from src.shortage_model import PENALTY, TINY, solve_with_shortage


# the small hand-worked example, with capacities we can change
def tiny_instance(cap_w1, cap_w2):
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


# same example, but total capacity may be below demand
# build_instance refuses that on purpose, so build a valid one and shrink it after
def short_on_capacity_instance(cap_w1, cap_w2):
    return replace(tiny_instance(250, 250), capacity={"W1": cap_w1, "W2": cap_w2})


def test_no_shortage_when_capacity_is_enough():
    # same as the stage 2 answer: $270, nothing unmet
    sol = solve_with_shortage(tiny_instance(150, 100))
    assert sol.unmet_units == pytest.approx(0.0, abs=1e-6)
    assert sol.shipping_cost == pytest.approx(270.0)


def test_shortage_when_capacity_is_too_small():
    # capacity is 100 + 100 = 200 but demand is 230, so 30 units must go unmet.
    # which 30? the ones that cost most to serve. R2 units cost $2 to $3 each,
    # R1 units $1 and R3 units $0.50. so 30 units of R2 go unmet:
    #   W1 ships R1 (100 units, $100). W2 ships R3 (80, $40) and 20 of R2 ($40).
    #   shipping = 100 + 40 + 40 = $180.
    sol = solve_with_shortage(short_on_capacity_instance(100, 100))
    assert sol.unmet_units == pytest.approx(30.0)
    assert sol.unmet["R2"] == pytest.approx(30.0)
    assert sol.shipping_cost == pytest.approx(180.0)
    assert sol.total_cost == pytest.approx(180.0 + 30 * PENALTY)


def test_removing_a_warehouse_by_leaving_it_out():
    # only W1 can ship, capacity 150 for demand 230, so 80 units go unmet.
    # the unserved units are R3's, which cost the most per unit from W1 ($4.50).
    #   W1 ships R1 (100 units, $100) and R2 (50 units, $150). shipping = $250.
    sol = solve_with_shortage(tiny_instance(150, 150), open_warehouses=["W1"])
    assert sol.unmet["R3"] == pytest.approx(80.0)
    assert sol.shipping_cost == pytest.approx(250.0)


def test_no_warehouses_means_nothing_delivered():
    inst = tiny_instance(150, 150)
    sol = solve_with_shortage(inst, open_warehouses=[])
    assert sol.unmet_units == pytest.approx(230.0)
    assert sol.shipping_cost == 0.0


def test_demand_override_is_used():
    inst = tiny_instance(150, 150)
    sol = solve_with_shortage(inst, demand={"R1": 10, "R2": 10, "R3": 10})
    assert sol.unmet_units == pytest.approx(0.0, abs=1e-6)
    assert sum(sol.shipments.values()) == pytest.approx(30.0)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_matches_the_lp_when_nothing_is_short(seed):
    # with every warehouse available and enough capacity, shortages never help
    inst = generate_instance(seed=seed)
    sol = solve_with_shortage(inst)
    assert sol.unmet_units == pytest.approx(0.0, abs=1e-4)
    assert sol.shipping_cost == pytest.approx(solve_transportation(inst).cost, rel=1e-6)


def test_matches_the_milp_shipping_on_its_own_open_set():
    # the MILP picked its warehouses AND its shipments. re-solving with the same
    # open warehouses must find the same shipping cost.
    inst = generate_instance(seed=42)
    milp = solve_facility_location(inst)
    sol = solve_with_shortage(inst, open_warehouses=milp.open_warehouses)
    assert sol.unmet_units == pytest.approx(0.0, abs=1e-4)
    assert sol.shipping_cost == pytest.approx(milp.transport_total, rel=1e-6)


def test_plan_respects_capacity_and_demand():
    inst = generate_instance(seed=42)
    demand = {j: v * 1.3 for j, v in inst.demand.items()}  # a big demand jump
    sol = solve_with_shortage(inst, demand=demand)

    loads = warehouse_loads(inst, sol.shipments)
    for i in inst.warehouses:
        assert loads[i] <= inst.capacity[i] + 1e-4

    for j in inst.regions:
        delivered = sum(u for (_i, jj), u in sol.shipments.items() if jj == j)
        assert delivered + sol.unmet[j] == pytest.approx(demand[j], abs=1e-4)
        assert sol.unmet[j] >= -TINY
