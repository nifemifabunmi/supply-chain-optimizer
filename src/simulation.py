"""Stage 4: what happens when demand is random or a warehouse goes down?

Monte Carlo simulation = try many random "what if" worlds (scenarios) and look
at the averages and the bad cases.

Two ways to respond to a scenario are compared on the SAME scenarios:
  fixed    keep the plan made for expected demand, scale it to the new demand,
           and cut back any warehouse that goes over capacity
  reopt    solve the shortage LP again for this scenario (needs a new solve)

The gap between them is the value of being able to re-plan.
"""
import math
from dataclasses import dataclass

import numpy as np

from src.baseline import transport_cost
from src.shortage_model import PENALTY, solve_with_shortage

FULL_SERVICE_TOL = 1e-4  # unmet demand below this many units counts as none


def make_demand_scenarios(instance, n_scenarios, seed, cv):
    """Random demand scenarios. Returns a list of {region: demand} dictionaries.

    Each region's demand = its normal demand * a random multiplier.
    The multiplier has an average of 1 and a spread set by cv (coefficient of
    variation: 0.2 means a typical swing of about 20%). It is lognormal, so
    demand can never go negative. The same seed always gives the same scenarios.
    """
    rng = np.random.default_rng(seed)
    sigma = math.sqrt(math.log(1 + cv ** 2))
    mu = -sigma ** 2 / 2  # keeps the average multiplier at exactly 1
    z = rng.standard_normal((n_scenarios, len(instance.regions)))
    multipliers = np.exp(mu + sigma * z)
    return [
        {j: instance.demand[j] * multipliers[s, k] for k, j in enumerate(instance.regions)}
        for s in range(n_scenarios)
    ]


def fixed_plan_outcome(instance, plan, demand, down=()):
    """Outcome of sticking with the planned routes. Returns (shipping_cost, unmet_units).

    Step 1: each region's shipments are scaled by (new demand / planned demand),
            keeping the same split between warehouses.
    Step 2: a warehouse that would ship more than its capacity (or one that is
            in `down`, with capacity 0) cuts all its shipments by the same share.
    Anything not delivered is unmet.
    """
    # Step 1: scale to the new demand.
    scaled = {
        (i, j): units * demand[j] / instance.demand[j]
        for (i, j), units in plan.items()
    }

    # Step 2: cut back warehouses that are over capacity or down.
    loads = {}
    for (i, _j), units in scaled.items():
        loads[i] = loads.get(i, 0.0) + units
    keep = {}
    for i, load in loads.items():
        capacity = 0.0 if i in down else instance.capacity[i]
        keep[i] = min(1.0, capacity / load) if load > 0 else 1.0

    final = {(i, j): units * keep[i] for (i, j), units in scaled.items()}
    delivered = sum(final.values())
    return transport_cost(instance, final), sum(demand.values()) - delivered


@dataclass
class SimulationResult:
    penalty: float
    total_demand: np.ndarray  # total demand in each scenario
    shipping: dict            # policy name -> array of shipping cost per scenario
    unmet: dict               # policy name -> array of unmet units per scenario


def run_demand_simulation(instance, plan, open_warehouses, n_scenarios=1000,
                          seed=0, cv=0.2, penalty=PENALTY):
    """Run both policies on the same random demand scenarios."""
    scenarios = make_demand_scenarios(instance, n_scenarios, seed, cv)

    out = {
        "total_demand": np.zeros(n_scenarios),
        "fixed_ship": np.zeros(n_scenarios), "fixed_unmet": np.zeros(n_scenarios),
        "reopt_ship": np.zeros(n_scenarios), "reopt_unmet": np.zeros(n_scenarios),
    }
    for s, demand in enumerate(scenarios):
        out["total_demand"][s] = sum(demand.values())

        ship, unmet = fixed_plan_outcome(instance, plan, demand)
        out["fixed_ship"][s], out["fixed_unmet"][s] = ship, max(unmet, 0.0)

        best = solve_with_shortage(instance, open_warehouses, demand, penalty)
        out["reopt_ship"][s], out["reopt_unmet"][s] = best.shipping_cost, best.unmet_units

    return SimulationResult(
        penalty=penalty,
        total_demand=out["total_demand"],
        shipping={"fixed": out["fixed_ship"], "reopt": out["reopt_ship"]},
        unmet={"fixed": out["fixed_unmet"], "reopt": out["reopt_unmet"]},
    )


def summarize(result):
    """Turn a SimulationResult into a few numbers per policy."""
    summary = {}
    for policy in result.shipping:
        shipping = result.shipping[policy]
        unmet = result.unmet[policy]
        total = shipping + result.penalty * unmet  # shipping plus the unmet penalty

        # Worst 5% of scenarios: the average of the most expensive ones (like CVaR).
        worst = max(1, int(round(0.05 * len(total))))
        summary[policy] = {
            "mean_shipping": float(shipping.mean()),
            "mean_unmet_units": float(unmet.mean()),
            "fill_rate": float((1 - unmet / result.total_demand).mean()),
            "full_service_share": float((unmet < FULL_SERVICE_TOL).mean()),
            "mean_total_cost": float(total.mean()),
            "p95_total_cost": float(np.percentile(total, 95)),
            "worst_5pct_avg_cost": float(np.sort(total)[-worst:].mean()),
        }
    return summary


def run_disruptions(instance, plan, open_warehouses, penalty=PENALTY):
    """Take each open warehouse down, one at a time, and measure the damage.

    Two responses are shown:
      no response   keep the plan; whatever the lost warehouse shipped goes unmet
      re-plan       solve the shortage LP again without that warehouse

    Note: the re-plan's shipping cost can be LOWER than the original plan's,
    because it delivers fewer units. Compare the unmet units, not just the cost.
    """
    total_demand = sum(instance.demand.values())
    rows = []
    for k in open_warehouses:
        usual_load = sum(u for (i, _j), u in plan.items() if i == k)

        ship, unmet = fixed_plan_outcome(instance, plan, instance.demand, down={k})
        remaining = [i for i in open_warehouses if i != k]
        best = solve_with_shortage(instance, remaining, penalty=penalty)

        rows.append({
            "warehouse": k,
            "usual_load": usual_load,
            "no_response_unmet": max(unmet, 0.0),
            "no_response_fill": 1 - max(unmet, 0.0) / total_demand,
            "replan_shipping": best.shipping_cost,
            "replan_unmet": best.unmet_units,
            "replan_fill": 1 - best.unmet_units / total_demand,
        })
    return rows
