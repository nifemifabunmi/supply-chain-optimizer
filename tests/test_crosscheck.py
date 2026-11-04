# detailed explanation
# this file tests the second-solver cross-check (src/crosscheck.py).
# the main models use PuLP with the CBC solver. crosscheck.py solves the same two
# problems again with a different library, OR-Tools (GLOP for the LP, SCIP for the
# MILP). if both libraries give the same cost and the same open warehouses, a
# numerical or solver mistake is very unlikely.
# a second solver does NOT prove the model matches the real world, only that the
# solving was done right.
#
# checks in this file:
#   1. the tiny 2-warehouse, 3-region example, solved by hand:
#      LP with room to spare costs $240, and with W2 at capacity 100 it costs $270.
#      MILP: if W2 is very expensive, W1 alone costs 610 + 100 = $710.
#      if W2 costs 300, opening both costs 240 + 100 + 300 = $640.
#   2. on random networks (seeds 1, 7, 42, 99) both libraries agree on the LP cost,
#      the MILP cost, and the set of open warehouses.
#   3. the OR-Tools plan is valid: demand met and capacity respected.
#   4. a sanity check on the check itself: change one capacity and the answer changes.
#
# the whole file is skipped (not failed) if OR-Tools is not installed.
import pytest

# skip these tests (instead of failing) if OR-Tools is not installed
pytest.importorskip("ortools")

from dataclasses import replace

from src.crosscheck import (
    compare_solvers,
    solve_facility_location_ortools,
    solve_transportation_ortools,
)
from src.data import build_instance, generate_instance


# the small hand-worked example. cost per unit:
#              W1     W2
#       R1    $1.00  $4.00     demand: R1 = 100, R2 = 50, R3 = 80 (total 230)
#       R2    $3.00  $2.00
#       R3    $4.50  $0.50
def tiny_instance(cap_w1, cap_w2, fixed_w1=0, fixed_w2=0):
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": fixed_w1, "W2": fixed_w2},
        rate=0.5,
    )


def test_ortools_lp_matches_the_hand_calculation():
    assert solve_transportation_ortools(tiny_instance(150, 150))["cost"] == pytest.approx(240.0)
    assert solve_transportation_ortools(tiny_instance(150, 100))["cost"] == pytest.approx(270.0)


def test_ortools_milp_matches_the_hand_calculation():
    # W2 very expensive to open: W1 alone costs 610 + 100 = 710
    sol = solve_facility_location_ortools(tiny_instance(250, 150, 100, 10_000))
    assert sol["open_warehouses"] == ["W1"]
    assert sol["total_cost"] == pytest.approx(710.0)

    # both open when the second pays for itself: 240 + 100 + 300 = 640
    sol = solve_facility_location_ortools(tiny_instance(250, 250, 100, 300))
    assert sorted(sol["open_warehouses"]) == ["W1", "W2"]
    assert sol["total_cost"] == pytest.approx(640.0)


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
def test_both_libraries_agree_on_random_networks(seed):
    result = compare_solvers(generate_instance(seed=seed))
    assert result["lp_pulp"] == pytest.approx(result["lp_ortools"], rel=1e-6)
    assert result["milp_pulp"] == pytest.approx(result["milp_ortools"], rel=1e-6)
    assert result["same_open_set"]


def test_ortools_plan_is_valid():
    inst = generate_instance(seed=42)
    sol = solve_transportation_ortools(inst)
    for j in inst.regions:
        delivered = sum(u for (_i, jj), u in sol["shipments"].items() if jj == j)
        assert delivered == pytest.approx(inst.demand[j], abs=1e-4)
    for i in inst.warehouses:
        shipped = sum(u for (ii, _j), u in sol["shipments"].items() if ii == i)
        assert shipped <= inst.capacity[i] + 1e-4


def test_a_wrong_model_would_be_caught():
    # sanity check on the check itself: change one capacity and the answers change
    inst = tiny_instance(150, 150)
    tighter = replace(inst, capacity={"W1": 150, "W2": 100})
    assert solve_transportation_ortools(inst)["cost"] != pytest.approx(
        solve_transportation_ortools(tighter)["cost"]
    )
