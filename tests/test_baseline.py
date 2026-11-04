# detailed explanation
# this file tests stage 1: the data generator and the nearest-warehouse baseline.
# the baseline sends every region to its closest warehouse and ignores capacity.
#
# the checks come in two groups.
# group 1 uses a tiny network small enough to solve on paper:
#   2 warehouses (W1, W2) and 3 regions (R1, R2, R3), shipping rate $0.5 per unit per km.
#   R1 is closest to W1, while R2 and R3 are closest to W2.
#   so W1 ships 100 units and W2 ships 130 units, and the cost is $240.
#   we also shrink W2's capacity to 100 to prove that an overload gets flagged.
# group 2 checks the random generator:
#   the same seed must give the same network, and different seeds must differ.
#   a generated network must be valid (enough capacity, positive numbers).
#   too little capacity must raise an error instead of giving odd answers later.
#   the cost function must match a separate calculation done by hand in the test.
#
# why this matters: every later stage builds on this data and this cost function.
# if they were wrong, every saving we report would be wrong too.
import pytest

from src.baseline import (
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import build_instance, generate_instance


# the small hand-worked example. by hand: cost is $240, W1 ships 100, W2 ships 130.
def tiny_instance(cap_w2=150):
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": 150, "W2": cap_w2},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


# build the baseline plan and the shipments that come from it
def baseline(instance):
    plan = nearest_warehouse_plan(instance)
    return plan, shipments_from_plan(instance, plan)


def test_nearest_assignment():
    plan, _ = baseline(tiny_instance())
    assert plan == {"R1": "W1", "R2": "W2", "R3": "W2"}


def test_baseline_cost_is_240():
    inst = tiny_instance()
    _, shipments = baseline(inst)
    assert transport_cost(inst, shipments) == pytest.approx(240.0)


def test_baseline_loads_and_no_violation():
    inst = tiny_instance()
    _, shipments = baseline(inst)
    assert warehouse_loads(inst, shipments) == {"W1": 100, "W2": 130}
    assert capacity_violations(inst, shipments) == {}


def test_baseline_overload_is_flagged():
    # W2 can only take 100 but the baseline sends it 130, so it is 30 over
    inst = tiny_instance(cap_w2=100)
    _, shipments = baseline(inst)
    assert capacity_violations(inst, shipments) == {"W2": 30}


def test_same_seed_gives_same_network():
    a = generate_instance(seed=42)
    b = generate_instance(seed=42)
    assert a.demand == b.demand
    assert a.capacity == b.capacity
    assert a.cost == b.cost


def test_different_seeds_give_different_networks():
    assert generate_instance(seed=1).demand != generate_instance(seed=2).demand


def test_generated_network_is_valid():
    inst = generate_instance(seed=42)
    assert len(inst.warehouses) == 5 and len(inst.regions) == 20
    assert sum(inst.capacity.values()) >= sum(inst.demand.values())
    assert all(v > 0 for v in inst.demand.values())
    assert all(v > 0 for v in inst.capacity.values())


def test_too_little_capacity_raises_an_error():
    with pytest.raises(ValueError):
        build_instance(
            wh_pos={"W1": (0, 0)},
            reg_pos={"R1": (1, 0)},
            demand={"R1": 100},
            capacity={"W1": 50},
            fixed_cost={"W1": 0},
            rate=1.0,
        )


def test_cost_matches_a_manual_calculation():
    inst = generate_instance(seed=7)
    _, shipments = baseline(inst)
    manual = sum(
        inst.rate * inst.dist[(i, j)] * units for (i, j), units in shipments.items()
    )
    assert transport_cost(inst, shipments) == pytest.approx(manual)
    # every unit of demand is shipped exactly once
    assert sum(shipments.values()) == sum(inst.demand.values())
