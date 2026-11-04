# detailed explanation
# this file tests stage 5: sensitivity analysis, break-even, and the many-network
# comparison (src/sensitivity.py and src/experiments.py).
#
# sensitivity analysis changes ONE input (shipping rate, demand, total capacity or
# opening cost) up and down by a percentage, solves the MILP again each time, and
# records how much the total cost moves. break-even finds, by bisection, the
# opening-cost level at which the plan first closes a warehouse.
#
# the tiny example (2 warehouses, 3 regions) is solved by hand. cost per unit:
#              W1     W2
#       R1    $1.00  $4.00     demand: R1 = 100, R2 = 50, R3 = 80 (total 230)
#       R2    $3.00  $2.00
#       R3    $4.50  $0.50
# shipping with both open is $240, and with only W1 it is $610.
# so opening W2 saves 610 - 240 = 370, and with opening cost 300 times a
# multiplier m, W2 closes once 300 * m passes 370 (m = 370 / 300 = 1.2333).
#
# checks in this file:
#   1. scaling changes only the named input, and an unknown name is rejected.
#   2. with huge capacity and free opening, cost is exactly proportional to
#      shipping rate and to demand ($240 becomes $120 and $360 at -50% and +50%).
#   3. opening cost +-20% on the example, worked out by hand.
#   4. rows are sorted with the biggest swing first, and a 0% change gives the base cost.
#   5. the break-even matches the hand answer, and is None if nothing ever closes.
#   6. many networks: known seeds reproduce numbers computed earlier in the project,
#      the optimizer never loses to what it can imitate, and the summary is sensible.
import pytest

from src.data import build_instance, generate_instance
from src.experiments import compare_networks, summarize_networks
from src.sensitivity import INPUTS, breakeven_multiplier, scale_input, sensitivity_table


# the small hand-worked example (see the top of this file for the numbers)
def tiny_instance(cap_w1, cap_w2, fixed_w1=0, fixed_w2=0):
    return build_instance(
        wh_pos={"W1": (0, 0), "W2": (10, 0)},
        reg_pos={"R1": (2, 0), "R2": (6, 0), "R3": (9, 0)},
        demand={"R1": 100, "R2": 50, "R3": 80},
        capacity={"W1": cap_w1, "W2": cap_w2},
        fixed_cost={"W1": fixed_w1, "W2": fixed_w2},
        rate=0.5,
    )


# ---------- scaling one input ----------

def test_scaling_changes_only_the_named_input():
    inst = tiny_instance(250, 250, 100, 300)
    assert scale_input(inst, "demand", 2).demand["R1"] == 200
    assert scale_input(inst, "total capacity", 2).capacity["W1"] == 500
    assert scale_input(inst, "opening cost", 2).fixed_cost["W2"] == 600
    faster = scale_input(inst, "shipping rate", 2)
    assert faster.cost[("W1", "R1")] == pytest.approx(2 * inst.cost[("W1", "R1")])
    # everything else is untouched
    assert scale_input(inst, "demand", 2).capacity == inst.capacity


def test_unknown_input_is_rejected():
    with pytest.raises(ValueError):
        scale_input(tiny_instance(250, 250), "weather", 2)


# ---------- the sensitivity table, by hand ----------

def test_sensitivity_on_the_small_example_with_nothing_binding():
    # capacities are huge and opening is free, so cost is exactly proportional
    # to shipping rate and to demand: base $240 -> $120 at -50%, $360 at +50%
    inst = tiny_instance(1000, 1000)
    table = sensitivity_table(inst, pct=0.5)
    by_name = {r["input"]: r for r in table["rows"]}

    assert by_name["shipping rate"]["low_total"] == pytest.approx(120.0)
    assert by_name["shipping rate"]["high_total"] == pytest.approx(360.0)
    assert by_name["demand"]["low_total"] == pytest.approx(120.0)
    assert by_name["demand"]["high_total"] == pytest.approx(360.0)

    # capacity is not binding and opening is free: no effect at all
    assert by_name["total capacity"]["swing"] == pytest.approx(0.0)
    assert by_name["opening cost"]["swing"] == pytest.approx(0.0)


def test_sensitivity_to_opening_cost_by_hand():
    # capacity 250 each, opening costs 100 and 300. both open costs 240 + 400 = 640.
    #   -20%: opening 80 and 240  -> both open: 240 + 320 = 560
    #   +20%: opening 120 and 360 -> both open: 240 + 480 = 720
    #         (W1 only would cost 610 + 120 = 730, so both stay open)
    table = sensitivity_table(tiny_instance(250, 250, 100, 300), pct=0.2)
    row = {r["input"]: r for r in table["rows"]}["opening cost"]
    assert table["base_total"] == pytest.approx(640.0)
    assert row["low_total"] == pytest.approx(560.0)
    assert row["high_total"] == pytest.approx(720.0)
    assert row["swing"] == pytest.approx(160.0)
    assert row["open_set_changes"] is False


def test_rows_are_sorted_with_the_biggest_swing_first():
    rows = sensitivity_table(generate_instance(seed=42), pct=0.2)["rows"]
    assert [r["input"] for r in rows] != []
    swings = [r["swing"] for r in rows]
    assert swings == sorted(swings, reverse=True)
    assert sorted(r["input"] for r in rows) == sorted(INPUTS)


def test_zero_change_gives_the_base_cost():
    inst = generate_instance(seed=42)
    table = sensitivity_table(inst, pct=0.0)
    for row in table["rows"]:
        assert row["low_total"] == pytest.approx(table["base_total"])
        assert row["high_total"] == pytest.approx(table["base_total"])


# ---------- break-even ----------

def test_breakeven_on_the_small_example_by_hand():
    # opening costs 100 and 300 (times a multiplier m), capacity 250 each.
    # opening W2 as well as W1 saves 610 - 240 = 370 of shipping, so W2 closes
    # once 300 * m exceeds 370, that is m = 370 / 300 = 1.2333...
    m = breakeven_multiplier(tiny_instance(250, 250, 100, 300), hi=5.0)
    assert m == pytest.approx(370 / 300, abs=1e-3)


def test_breakeven_is_none_when_nothing_ever_closes():
    # opening costs of 1 and 1, even times 4, are far below the $370 of shipping saved
    assert breakeven_multiplier(tiny_instance(250, 250, 1, 1), hi=4.0) is None


# ---------- many networks ----------

def test_known_networks_reproduce_earlier_results():
    # numbers computed earlier in the project for these seeds (to the cent)
    rows = {r["seed"]: r for r in compare_networks([1, 42])}
    assert rows[1]["fair_cost"] == pytest.approx(2413.69, abs=0.01)
    assert rows[1]["lp_cost"] == pytest.approx(2221.14, abs=0.01)
    assert rows[1]["all_open_total"] == pytest.approx(4173.71, abs=0.01)
    assert rows[1]["milp_total"] == pytest.approx(4083.53, abs=0.01)
    assert rows[42]["fair_cost"] == pytest.approx(3239.74, abs=0.01)
    assert rows[42]["lp_cost"] == pytest.approx(2995.22, abs=0.01)
    assert rows[42]["milp_total"] == pytest.approx(4147.04, abs=0.01)


def test_the_optimizer_never_loses_to_what_it_can_imitate():
    for r in compare_networks([3, 4, 5]):
        assert r["lp_cost"] <= r["fair_cost"] + 1e-6          # the LP beats a valid baseline
        assert r["milp_total"] <= r["all_open_total"] + 1e-6  # opening all is one option
        assert r["lp_saving_pct"] >= -1e-9
        assert r["milp_saving_pct"] >= -1e-9


def test_summary_has_sensible_numbers():
    s = summarize_networks(compare_networks([1, 2, 3, 4]))
    assert s["n_networks"] == 4
    assert 0.0 <= s["naive_overload_share"] <= 1.0
    spread = s["lp_saving_pct"]
    assert spread["min"] <= spread["median"] <= spread["max"]
    assert spread["min"] <= spread["mean"] <= spread["max"]
