# detailed explanation
# checks for the real-map illustration (src/realistic.py).
#
# a. haversine distance: new york to los angeles is about 3,936 km (a number
#    you can look up), and the distance from a point to itself is 0.
# b. the real data is sane: 25 metros, positive populations, demand is
#    population / 100,000, and every pair of points has a distance.
# c. the same models work on it: the lp plan is valid, and the milp is never
#    worse than opening every hub (opening everything is one of its options).
# d. build_instance still uses straight-line distances when no dist is passed,
#    and uses the passed distances when one is.
import pytest

from src.data import build_instance
from src.lp_model import solve_transportation
from src.milp_model import solve_facility_location
from src.realistic import METROS, build_realistic_instance, haversine_km


def test_haversine_new_york_to_los_angeles():
    assert haversine_km(40.71, -74.01, 34.05, -118.24) == pytest.approx(3936, abs=15)


def test_haversine_same_point_is_zero():
    assert haversine_km(33.75, -84.39, 33.75, -84.39) == pytest.approx(0.0)


def test_real_data_is_sane():
    inst = build_realistic_instance()
    assert len(inst.regions) == len(METROS) == 25
    assert all(p > 0 for _, _, _, p in METROS)
    assert inst.demand["New York"] == pytest.approx(20_140_470 / 100_000)
    assert len(inst.dist) == len(inst.warehouses) * len(inst.regions)
    assert sum(inst.capacity.values()) >= sum(inst.demand.values())


def test_lp_plan_is_valid_on_the_real_map():
    inst = build_realistic_instance()
    sol = solve_transportation(inst)
    for j in inst.regions:
        delivered = sum(u for (_i, jj), u in sol.shipments.items() if jj == j)
        assert delivered == pytest.approx(inst.demand[j], abs=1e-4)
    for i in inst.warehouses:
        shipped = sum(u for (ii, _j), u in sol.shipments.items() if ii == i)
        assert shipped <= inst.capacity[i] + 1e-4


def test_milp_is_never_worse_than_opening_everything():
    inst = build_realistic_instance()
    all_open = solve_transportation(inst).cost + sum(inst.fixed_cost.values())
    assert solve_facility_location(inst).total_cost <= all_open + 1e-6


def test_build_instance_dist_option():
    args = dict(
        wh_pos={"W": (0, 0)}, reg_pos={"R": (3, 4)}, demand={"R": 10},
        capacity={"W": 10}, fixed_cost={"W": 0}, rate=2.0,
    )
    # default: straight line, 5 km, cost 2 * 5
    assert build_instance(**args).cost[("W", "R")] == pytest.approx(10.0)
    # passed distance wins: 100 km, cost 2 * 100
    assert build_instance(**args, dist={("W", "R"): 100.0}).cost[("W", "R")] == pytest.approx(200.0)
