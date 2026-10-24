import pytest

from src.baseline import (
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import build_instance, generate_instance


def tiny_instance(cap_w2=150):
    # The two-warehouse, three-region example from the technical document.
    #
    # Computed by hand first: baseline cost is $240, W1 load 100, W2 load 130.
    
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": 150, "W2": cap_w2},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


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
    inst = tiny_instance(cap_w2=100)  # total capacity 250 still covers demand 230
    _, shipments = baseline(inst)
    assert capacity_violations(inst, shipments) == {"W2": 30}


def test_generator_is_reproducible():
    a = generate_instance(seed=42)
    b = generate_instance(seed=42)
    assert a.demand == b.demand
    assert a.capacity == b.capacity
    assert a.cost == b.cost


def test_different_seeds_differ():
    assert generate_instance(seed=1).demand != generate_instance(seed=2).demand


def test_generated_instance_is_feasible_and_positive():
    inst = generate_instance(seed=42)
    assert len(inst.warehouses) == 5 and len(inst.regions) == 20
    assert sum(inst.capacity.values()) >= sum(inst.demand.values())
    assert all(v > 0 for v in inst.demand.values())
    assert all(v > 0 for v in inst.capacity.values())


def test_infeasible_input_raises():
    with pytest.raises(ValueError):
        build_instance(
            wh_pos={"W1": (0, 0)},
            reg_pos={"R1": (1, 0)},
            demand={"R1": 100},
            capacity={"W1": 50},
            fixed_cost={"W1": 0},
            rate=1.0,
        )


def test_cost_matches_manual_recomputation_on_random_instance():
    inst = generate_instance(seed=7)
    _, shipments = baseline(inst)
    manual = sum(
        inst.rate * inst.dist[(i, j)] * units for (i, j), units in shipments.items()
    )
    assert transport_cost(inst, shipments) == pytest.approx(manual)
    # every region's demand is shipped exactly once
    assert sum(shipments.values()) == sum(inst.demand.values())
