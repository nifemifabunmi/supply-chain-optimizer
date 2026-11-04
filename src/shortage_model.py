"""Stage 4 building block: the transportation LP, but demand is allowed to go unmet.

Why: when demand is higher than expected, or a warehouse is down, there may be
no way to fill every order. The Stage 2 LP would simply fail. Here each region
gets a "shortage" variable, and every unmet unit costs a penalty.

The math:
    minimize    sum of cost[i][j] * x[i][j]  +  penalty * sum of short[j]
    subject to  for every region j:     sum over i of x[i][j] + short[j] = demand[j]
                for every warehouse i:  sum over j of x[i][j] <= capacity[i]
                x[i][j] >= 0,   short[j] >= 0

The penalty is an ASSUMPTION. It only has to be bigger than any shipping cost
per unit, so the model leaves demand unmet only when it truly has no choice.
"""
from dataclasses import dataclass

import pulp

from src.baseline import transport_cost

TINY = 1e-6      # anything smaller than this counts as zero
PENALTY = 100.0  # dollars per unmet unit (an assumption)


@dataclass
class ShortageSolution:
    shipments: dict      # (warehouse, region) -> units (zero shipments left out)
    unmet: dict          # region -> units that could not be delivered
    shipping_cost: float
    unmet_units: float   # total unmet units over all regions
    total_cost: float    # shipping_cost + penalty * unmet_units


def solve_with_shortage(instance, open_warehouses=None, demand=None, penalty=PENALTY):
    """Best plan when some demand may go unmet.

    open_warehouses: which warehouses can ship (default: all of them)
    demand:          a different demand to use instead of instance.demand
    """
    W = list(instance.warehouses if open_warehouses is None else open_warehouses)
    R = instance.regions
    d = instance.demand if demand is None else demand

    # No warehouse can ship at all: nothing is delivered.
    if not W:
        return ShortageSolution({}, dict(d), 0.0, sum(d.values()), penalty * sum(d.values()))

    prob = pulp.LpProblem("transportation_with_shortage", pulp.LpMinimize)
    x = prob.add_variable_dicts("x", (W, R), lowBound=0)
    short = prob.add_variable_dicts("short", R, lowBound=0)

    # Goal: shipping cost plus the penalty for every unmet unit.
    prob += (
        pulp.lpSum(instance.cost[(i, j)] * x[i][j] for i in W for j in R)
        + penalty * pulp.lpSum(short[j] for j in R)
    )

    # Rule 1: what arrives plus what is left unmet equals the demand.
    for j in R:
        prob += pulp.lpSum(x[i][j] for i in W) + short[j] == d[j]

    # Rule 2: no warehouse ships more than its capacity.
    for i in W:
        prob += pulp.lpSum(x[i][j] for j in R) <= instance.capacity[i]

    stats = prob.solve(pulp.COIN_CMD(msg=False))
    if stats.status_str != "Optimal":
        raise RuntimeError(f"Solver did not find a plan: {stats.status_str}")

    shipments = {}
    for i in W:
        for j in R:
            units = x[i][j].value()
            if units is not None and units > TINY:
                shipments[(i, j)] = units

    unmet = {}
    for j in R:
        units = short[j].value()
        unmet[j] = units if (units is not None and units > TINY) else 0.0

    # Work out the costs ourselves instead of trusting the solver's number.
    shipping_cost = transport_cost(instance, shipments)
    unmet_units = sum(unmet.values())
    return ShortageSolution(shipments, unmet, shipping_cost, unmet_units,
                            shipping_cost + penalty * unmet_units)
