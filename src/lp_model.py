"""The optimizer: a transportation linear program (LP), using PuLP 4.

In plain words:
    Choose how many units each warehouse ships to each region so that
    the total shipping cost is as small as possible, while
      - every region gets exactly the demand it asked for, and
      - no warehouse ships more than its capacity.

The math:
    minimize    sum of  cost[i][j] * x[i][j]
    subject to  for every region j:     sum over i of x[i][j] = demand[j]
                for every warehouse i:  sum over j of x[i][j] <= capacity[i]
                x[i][j] >= 0

x[i][j] is the number of units shipped from warehouse i to region j.
"""
from dataclasses import dataclass, replace

import pulp

from src.baseline import transport_cost

TINY = 1e-6  # anything smaller than this counts as zero


@dataclass
class LPSolution:
    status: str       # "Optimal" means the solver found the best plan
    cost: float       # total cost of the plan
    shipments: dict   # (warehouse, region) -> units (zero shipments left out)


def solve_transportation(instance):
    """Build the LP, solve it, and return the best plan."""
    W, R = instance.warehouses, instance.regions

    # PuLP 4: create the problem first, then its variables.
    prob = pulp.LpProblem("transportation", pulp.LpMinimize)

    # One variable per warehouse-region pair. Use it as x[warehouse][region].
    x = prob.add_variable_dicts("x", (W, R), lowBound=0)

    # Goal: make total shipping cost as small as possible.
    prob += pulp.lpSum(instance.cost[(i, j)] * x[i][j] for i in W for j in R)

    # Rule 1: each region gets exactly its demand.
    for j in R:
        prob += pulp.lpSum(x[i][j] for i in W) == instance.demand[j]

    # Rule 2: no warehouse ships more than its capacity.
    for i in W:
        prob += pulp.lpSum(x[i][j] for j in R) <= instance.capacity[i]

    # Solve with CBC. msg=False keeps the solver quiet.
    stats = prob.solve(pulp.COIN_CMD(msg=False))

    # Read the answer back into a plain dictionary.
    shipments = {}
    for i in W:
        for j in R:
            units = x[i][j].value()
            if units is not None and units > TINY:
                shipments[(i, j)] = units

    # Work out the cost ourselves instead of trusting the solver's number.
    cost = transport_cost(instance, shipments)
    return LPSolution(status=stats.status_str, cost=cost, shipments=shipments)


def shadow_prices(instance, step=1):
    """How much money one extra unit of capacity saves at each warehouse.

    Method: add `step` units to one warehouse, solve again, and see how much
    the cost drops.
      - A price above 0 means that warehouse is a bottleneck.
      - A price of 0 means it already has spare room.
    Keep `step` small, because the price only holds for small changes.
    """
    base_cost = solve_transportation(instance).cost
    prices = {}
    for i in instance.warehouses:
        bigger = dict(instance.capacity)
        bigger[i] += step
        new_cost = solve_transportation(replace(instance, capacity=bigger)).cost
        prices[i] = (base_cost - new_cost) / step
    return prices
