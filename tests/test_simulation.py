import numpy as np
import pytest

from src.baseline import transport_cost
from src.data import build_instance, generate_instance
from src.lp_model import solve_transportation
from src.milp_model import solve_facility_location
from src.shortage_model import PENALTY
from src.simulation import (
    fixed_plan_outcome,
    make_demand_scenarios,
    run_demand_simulation,
    run_disruptions,
    summarize,
)


def tiny_instance():
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
        capacity={"W1": 150, "W2": 150},
        fixed_cost={"W1": 0, "W2": 0},
        rate=0.5,
    )


# The plan from Stage 2 for this example: R1 from W1, R2 and R3 from W2. Cost $240.
TINY_PLAN = {("W1", "R1"): 100, ("W2", "R2"): 50, ("W2", "R3"): 80}


def milp_network(seed=42):
    inst = generate_instance(seed=seed)
    milp = solve_facility_location(inst)
    return inst, milp.shipments, milp.open_warehouses


# ---------- scenarios ----------

def test_same_seed_gives_the_same_scenarios():
    inst = generate_instance(seed=42)
    a = make_demand_scenarios(inst, 10, seed=5, cv=0.2)
    b = make_demand_scenarios(inst, 10, seed=5, cv=0.2)
    assert a == b


def test_zero_volatility_gives_exactly_the_normal_demand():
    inst = generate_instance(seed=42)
    for demand in make_demand_scenarios(inst, 5, seed=1, cv=0.0):
        assert demand == pytest.approx(inst.demand)


def test_scenario_demand_is_positive_and_averages_to_normal():
    inst = generate_instance(seed=42)
    scenarios = make_demand_scenarios(inst, 2000, seed=3, cv=0.2)
    totals = np.array([sum(s.values()) for s in scenarios])
    assert all(v > 0 for s in scenarios for v in s.values())
    assert totals.mean() == pytest.approx(sum(inst.demand.values()), rel=0.01)


# ---------- the fixed plan ----------

def test_fixed_plan_at_normal_demand_reproduces_the_plan():
    inst = tiny_instance()
    ship, unmet = fixed_plan_outcome(inst, TINY_PLAN, inst.demand)
    assert ship == pytest.approx(240.0)
    assert unmet == pytest.approx(0.0, abs=1e-9)


def test_fixed_plan_scales_with_demand():
    # Every region needs half as much, so half the units ship at half the cost.
    inst = tiny_instance()
    half = {j: v / 2 for j, v in inst.demand.items()}
    ship, unmet = fixed_plan_outcome(inst, TINY_PLAN, half)
    assert ship == pytest.approx(120.0)
    assert unmet == pytest.approx(0.0, abs=1e-9)


def test_fixed_plan_cuts_back_an_overloaded_warehouse():
    # Demand is 20% higher everywhere. W2 would ship 130 * 1.2 = 156 but can only
    # ship 150, so it cuts every shipment by 150/156. W1 ships 120 (under 150).
    inst = tiny_instance()
    up = {j: v * 1.2 for j, v in inst.demand.items()}
    ship, unmet = fixed_plan_outcome(inst, TINY_PLAN, up)
    assert unmet == pytest.approx(156 - 150)  # the 6 units W2 could not ship
    assert ship == pytest.approx(120 * 1.0 + (60 * 2.0 + 96 * 0.5) * 150 / 156)


def test_fixed_plan_with_a_warehouse_down():
    # Without a response, everything W2 normally ships (R2 50 and R3 80) is lost.
    inst = tiny_instance()
    ship, unmet = fixed_plan_outcome(inst, TINY_PLAN, inst.demand, down={"W2"})
    assert unmet == pytest.approx(130.0)
    assert ship == pytest.approx(100.0)  # only R1 from W1 ($1 x 100)


# ---------- the simulation ----------

def test_zero_volatility_reproduces_the_deterministic_plan():
    inst, plan, open_list = milp_network()
    expected = transport_cost(inst, plan)
    result = run_demand_simulation(inst, plan, open_list, n_scenarios=3, seed=0, cv=0.0)
    for policy in ("fixed", "reopt"):
        assert result.shipping[policy] == pytest.approx(expected, rel=1e-6)
        assert result.unmet[policy] == pytest.approx(0.0, abs=1e-4)


def test_same_seed_gives_the_same_summary():
    inst, plan, open_list = milp_network()
    a = summarize(run_demand_simulation(inst, plan, open_list, n_scenarios=15, seed=9))
    b = summarize(run_demand_simulation(inst, plan, open_list, n_scenarios=15, seed=9))
    assert a == b


def test_replanning_is_never_worse_than_the_fixed_plan():
    # The fixed plan is one valid way to respond, so the best re-plan can only
    # match it or beat it in every single scenario.
    inst, plan, open_list = milp_network()
    r = run_demand_simulation(inst, plan, open_list, n_scenarios=25, seed=2, cv=0.3)
    fixed_total = r.shipping["fixed"] + r.penalty * r.unmet["fixed"]
    reopt_total = r.shipping["reopt"] + r.penalty * r.unmet["reopt"]
    assert np.all(reopt_total <= fixed_total + 1e-4)


def test_summary_numbers_make_sense():
    inst, plan, open_list = milp_network()
    r = run_demand_simulation(inst, plan, open_list, n_scenarios=25, seed=4, cv=0.3)
    for stats in summarize(r).values():
        assert 0.0 <= stats["fill_rate"] <= 1.0
        assert 0.0 <= stats["full_service_share"] <= 1.0
        assert stats["mean_unmet_units"] >= 0.0
        # The average of the worst 5% can never be below the 95th percentile.
        assert stats["worst_5pct_avg_cost"] >= stats["p95_total_cost"] - 1e-6


# ---------- warehouse outages ----------

def test_outages_on_the_small_example_by_hand():
    inst = tiny_instance()
    rows = {r["warehouse"]: r for r in run_disruptions(inst, TINY_PLAN, ["W1", "W2"])}

    # W2 down. No response: R2 and R3 (130 units) are lost.
    assert rows["W2"]["no_response_unmet"] == pytest.approx(130.0)
    # Re-plan: W1 (capacity 150) serves R1 (100) and R2 (50) for $250, and R3's 80 go unmet.
    assert rows["W2"]["replan_unmet"] == pytest.approx(80.0)
    assert rows["W2"]["replan_shipping"] == pytest.approx(250.0)

    # W1 down. No response: R1's 100 units are lost.
    assert rows["W1"]["no_response_unmet"] == pytest.approx(100.0)
    # Re-plan: W2 (capacity 150) serves R3 (80, $40), R2 (50, $100) and 20 of R1 ($80)
    # for $220, and 80 units of R1 go unmet.
    assert rows["W1"]["replan_unmet"] == pytest.approx(80.0)
    assert rows["W1"]["replan_shipping"] == pytest.approx(220.0)


def test_replanning_never_loses_more_demand_than_doing_nothing():
    inst, plan, open_list = milp_network()
    for row in run_disruptions(inst, plan, open_list):
        assert row["replan_unmet"] <= row["no_response_unmet"] + 1e-4
        assert 0.0 <= row["replan_fill"] <= 1.0
        assert 0.0 <= row["no_response_fill"] <= 1.0


def test_replan_loses_only_what_capacity_forces():
    # Any warehouse can serve any region, and an unmet unit costs far more than
    # shipping it, so the re-plan leaves unmet exactly
    #   (total demand - capacity of the warehouses still open), the minimum possible.
    inst, plan, open_list = milp_network()
    total_demand = sum(inst.demand.values())
    for row in run_disruptions(inst, plan, open_list):
        remaining = sum(inst.capacity[i] for i in open_list if i != row["warehouse"])
        assert row["replan_unmet"] == pytest.approx(max(0.0, total_demand - remaining), abs=1e-3)
