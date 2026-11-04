# detailed explanation
# this file decides which warehouses to open, and how to ship from them.
#
# it is the stage 2 lp with two additions:
#   - a yes/no variable per warehouse: is_open[i] is 1 if warehouse i is open, 0 if closed
#   - an opening cost: fixed_cost[i] is paid only if warehouse i is open
#
# the math:
#   minimize    sum of fixed_cost[i] * is_open[i]  +  sum of cost[i][j] * x[i][j]
#   subject to  for every region j:     sum over i of x[i][j] = demand[j]
#               for every warehouse i:  sum over j of x[i][j] <= capacity[i] * is_open[i]
#               x[i][j] >= 0,   is_open[i] is 0 or 1
#
# the key line is  capacity[i] * is_open[i]:
#   - closed (0): the limit is 0, so the warehouse can ship nothing
#   - open (1):   the limit is its normal capacity
#
# because is_open[i] must be exactly 0 or 1, this is a milp
# (mixed-integer linear program): x is continuous, is_open is whole-number.
# the solver tries open/closed combinations smartly (branch and bound).
#
# fixed_cost_sweep() solves again with all opening costs scaled up or down,
# to see when closing a warehouse starts to pay off.
# the opening costs themselves are an assumption, not real data.
from dataclasses import dataclass, replace

import pulp

from src.baseline import transport_cost

TINY = 1e-6  # anything smaller than this counts as zero

# "Optimal": the solver proved this is the best plan.
# "GapLimit": it stopped because the proven gap to the best possible plan hit
# its tiny tolerance. in our checks the plan is identical, but the tests also
# compare against trying every open/closed combination.
OK_STATUSES = ("Optimal", "GapLimit")


@dataclass
class MILPSolution:
    status: str             # "Optimal" (proven best) or "GapLimit" (see OK_STATUSES)
    open_warehouses: list   # names of the warehouses chosen to be open
    shipments: dict         # (warehouse, region) -> units (zero shipments left out)
    fixed_total: float      # opening cost of the open warehouses
    transport_total: float  # shipping cost
    total_cost: float       # fixed_total + transport_total


# choose which warehouses to open and how to ship. returns the best plan.
def solve_facility_location(instance):
    W, R = instance.warehouses, instance.regions

    prob = pulp.LpProblem("facility_location", pulp.LpMinimize)

    # x[i][j]: units shipped from warehouse i to region j (any amount >= 0).
    x = prob.add_variable_dicts("x", (W, R), lowBound=0)

    # is_open[i]: 1 if warehouse i is open, 0 if closed (a yes/no variable).
    is_open = prob.add_variable_dicts("open", W, cat=pulp.LpBinary)

    # goal: opening costs plus shipping costs, as small as possible.
    prob += (
        pulp.lpSum(instance.fixed_cost[i] * is_open[i] for i in W)
        + pulp.lpSum(instance.cost[(i, j)] * x[i][j] for i in W for j in R)
    )

    # rule 1: each region gets exactly its demand.
    for j in R:
        prob += pulp.lpSum(x[i][j] for i in W) == instance.demand[j]

    # rule 2: a warehouse can only ship up to its capacity, and only if it is open.
    for i in W:
        prob += pulp.lpSum(x[i][j] for j in R) <= instance.capacity[i] * is_open[i]

    # gapRel=0 and gapAbs=0 ask the solver to keep going until it is as exact as it can be.
    stats = prob.solve(pulp.COIN_CMD(msg=False, gapRel=0, gapAbs=0))
    if stats.status_str not in OK_STATUSES:
        raise RuntimeError(f"Solver did not find a usable plan: {stats.status_str}")

    # read the answer back into plain python values.
    # a yes/no variable can come back as 0.9999999, so compare with 0.5.
    open_list = [i for i in W if is_open[i].value() > 0.5]

    shipments = {}
    for i in W:
        for j in R:
            units = x[i][j].value()
            if units is not None and units > TINY:
                shipments[(i, j)] = units

    # work out the costs ourselves instead of trusting the solver's number.
    fixed_total = sum(instance.fixed_cost[i] for i in open_list)
    transport_total = transport_cost(instance, shipments)
    return MILPSolution(
        status=stats.status_str,
        open_warehouses=open_list,
        shipments=shipments,
        fixed_total=fixed_total,
        transport_total=transport_total,
        total_cost=fixed_total + transport_total,
    )


# solve again with all opening costs multiplied by each number in `multipliers`.
# shows how the best set of open warehouses changes as opening gets
# cheaper or more expensive. returns a list of (multiplier, MILPSolution).
def fixed_cost_sweep(instance, multipliers):
    rows = []
    for m in multipliers:
        scaled = {i: f * m for i, f in instance.fixed_cost.items()}
        rows.append((m, solve_facility_location(replace(instance, fixed_cost=scaled))))
    return rows
