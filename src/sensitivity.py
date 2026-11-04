# detailed explanation
# this file answers two questions about the best plan (the stage 3 milp).
#
# question 1: which inputs does the total cost depend on most?
#   method: change one input at a time, down and up by the same percentage,
#   solve the milp again each time, and see how far the total cost moves.
#   total cost here means opening costs plus shipping costs.
#   the four inputs are: shipping rate, demand, total capacity, opening cost.
#   changing one input at a time keeps each effect easy to read, but it hides
#   what happens when two inputs change together.
#
# question 2: at what opening-cost level does the best plan start closing a
# warehouse? this is called the break-even. it is found by bisection: try a
# cheap level and an expensive level, test the middle, keep the half that still
# holds the switch, and repeat. this assumes that the dearer opening gets, the
# fewer warehouses stay open.
from dataclasses import replace

from src.milp_model import solve_facility_location

INPUTS = ["shipping rate", "demand", "total capacity", "opening cost"]


# returns a copy of the instance with one input multiplied by factor
def scale_input(instance, name, factor):
    if name == "shipping rate":
        return replace(
            instance,
            rate=instance.rate * factor,
            cost={pair: c * factor for pair, c in instance.cost.items()},
        )
    if name == "demand":
        return replace(instance, demand={j: v * factor for j, v in instance.demand.items()})
    if name == "total capacity":
        return replace(instance, capacity={i: v * factor for i, v in instance.capacity.items()})
    if name == "opening cost":
        return replace(instance, fixed_cost={i: v * factor for i, v in instance.fixed_cost.items()})
    raise ValueError(f"Unknown input: {name}")


# changes each input by -pct and +pct, one at a time, and solves again
# returns {"base_total", "base_open", "pct", "rows"}
# each row holds the low and high total, the swing, and whether the open set changed
# rows are sorted with the biggest swing first
def sensitivity_table(instance, pct=0.2):
    base = solve_facility_location(instance)
    rows = []
    for name in INPUTS:
        low = solve_facility_location(scale_input(instance, name, 1 - pct))
        high = solve_facility_location(scale_input(instance, name, 1 + pct))
        rows.append({
            "input": name,
            "low_total": low.total_cost,
            "high_total": high.total_cost,
            "swing": abs(high.total_cost - low.total_cost),
            "low_open": sorted(low.open_warehouses),
            "high_open": sorted(high.open_warehouses),
            "open_set_changes": (sorted(low.open_warehouses) != sorted(base.open_warehouses)
                                 or sorted(high.open_warehouses) != sorted(base.open_warehouses)),
        })
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return {"base_total": base.total_cost, "base_open": sorted(base.open_warehouses),
            "pct": pct, "rows": rows}


# finds the smallest opening-cost multiplier at which at least one warehouse closes
# method: bisection between a cheap multiplier (all open) and hi (something closed)
# assumes dearer opening never means more warehouses open
# returns None if nothing closes even at hi
def breakeven_multiplier(instance, hi=4.0, steps=20):
    n_all = len(instance.warehouses)

    def n_open(m):
        scaled = scale_input(instance, "opening cost", m)
        return len(solve_facility_location(scaled).open_warehouses)

    low, high = 1e-6, hi
    if n_open(high) == n_all:
        return None
    if n_open(low) < n_all:
        return low
    for _ in range(steps):
        middle = (low + high) / 2
        if n_open(middle) == n_all:
            low = middle
        else:
            high = middle
    return (low + high) / 2
