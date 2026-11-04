# detailed explanation
# one random network can be lucky or unlucky. so this file repeats the key
# comparisons on many random networks, one per seed, and reports the typical
# size of each saving and how much it varies.
#
# for each network it works out:
#   - whether the nearest-warehouse baseline overloads a warehouse
#   - the lp saving versus the fair (capacity-aware) baseline
#   - the milp saving versus keeping every warehouse open
#   - how many warehouses the milp keeps open
#
# all the networks come from the same random generator, so the answers describe
# this kind of synthetic network and not real companies.
import numpy as np

from src.baseline import (
    capacity_aware_plan,
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
)
from src.data import generate_instance
from src.lp_model import solve_transportation
from src.milp_model import solve_facility_location


# runs the comparisons on one network per seed and returns a list of rows
def compare_networks(seeds, **generator_args):
    rows = []
    for seed in seeds:
        inst = generate_instance(seed=seed, **generator_args)

        # stage 1 and 2: the two baselines and the lp
        naive = shipments_from_plan(inst, nearest_warehouse_plan(inst))
        overload = capacity_violations(inst, naive)
        fair_cost = transport_cost(inst, capacity_aware_plan(inst))
        lp_cost = solve_transportation(inst).cost

        # stage 3: open everything versus let the milp choose
        all_open_total = lp_cost + sum(inst.fixed_cost.values())
        milp = solve_facility_location(inst)

        rows.append({
            "seed": seed,
            "naive_overloads": bool(overload),
            "naive_units_over": sum(overload.values()),
            "fair_cost": fair_cost,
            "lp_cost": lp_cost,
            "lp_saving_pct": 100 * (fair_cost - lp_cost) / fair_cost,
            "all_open_total": all_open_total,
            "milp_total": milp.total_cost,
            "milp_saving_pct": 100 * (all_open_total - milp.total_cost) / all_open_total,
            "n_open": len(milp.open_warehouses),
        })
    return rows


def _spread(values):
    values = np.array(values, dtype=float)
    return {
        "min": float(values.min()),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "max": float(values.max()),
    }


# boils the rows down to a few numbers
def summarize_networks(rows):
    return {
        "n_networks": len(rows),
        "naive_overload_share": float(np.mean([r["naive_overloads"] for r in rows])),
        "lp_saving_pct": _spread([r["lp_saving_pct"] for r in rows]),
        "milp_saving_pct": _spread([r["milp_saving_pct"] for r in rows]),
        "n_open": _spread([r["n_open"] for r in rows]),
    }
