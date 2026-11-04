# detailed explanation
# this file is a second opinion. it writes the same two models again with a
# different library (google or-tools) and compares the answers with the ones
# from pulp.
#
# the two models are:
#   lp    the cheapest valid shipping plan (stage 2), solved with or-tools' glop
#   milp  which warehouses to open (stage 3), solved with or-tools' scip
#         (pulp uses a solver called cbc)
#
# why bother: if two different libraries, written by different people, give the
# same answer, then the solver probably did not make a numerical mistake.
# what this does not prove: that the model matches the real world. both
# libraries are solving the same idea, so a wrong idea would fool both.
#
# tiny means a number so small that we treat it as zero.
from ortools.linear_solver import pywraplp

from src.baseline import transport_cost
from src.lp_model import solve_transportation
from src.milp_model import solve_facility_location

TINY = 1e-6  # anything smaller than this counts as zero


def _make_solver(name):
    solver = pywraplp.Solver.CreateSolver(name)
    if solver is None:
        raise RuntimeError(f"OR-Tools solver {name} is not available.")
    return solver


# solves the stage 2 lp (cheapest valid shipping plan) with or-tools
# returns {"cost": ..., "shipments": {(warehouse, region): units}}
def solve_transportation_ortools(instance):
    W, R = instance.warehouses, instance.regions
    solver = _make_solver("GLOP")

    # x[i, j] = units shipped from warehouse i to region j (zero or more)
    x = {(i, j): solver.NumVar(0, solver.infinity(), f"x_{i}_{j}") for i in W for j in R}

    for j in R:  # each region gets exactly its demand
        solver.Add(solver.Sum([x[i, j] for i in W]) == instance.demand[j])
    for i in W:  # no warehouse ships more than its capacity
        solver.Add(solver.Sum([x[i, j] for j in R]) <= instance.capacity[i])

    solver.Minimize(solver.Sum([instance.cost[i, j] * x[i, j] for i in W for j in R]))

    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("OR-Tools did not find an optimal LP plan.")

    shipments = {pair: v.solution_value() for pair, v in x.items() if v.solution_value() > TINY}
    return {"cost": transport_cost(instance, shipments), "shipments": shipments}


# solves the stage 3 milp (which warehouses to open) with or-tools
# returns {"total_cost", "open_warehouses", "shipments"}
def solve_facility_location_ortools(instance):
    W, R = instance.warehouses, instance.regions
    solver = _make_solver("SCIP")

    x = {(i, j): solver.NumVar(0, solver.infinity(), f"x_{i}_{j}") for i in W for j in R}
    is_open = {i: solver.BoolVar(f"open_{i}") for i in W}  # a yes/no variable

    for j in R:
        solver.Add(solver.Sum([x[i, j] for i in W]) == instance.demand[j])
    for i in W:  # capacity only counts if the warehouse is open
        solver.Add(solver.Sum([x[i, j] for j in R]) <= instance.capacity[i] * is_open[i])

    solver.Minimize(
        solver.Sum([instance.fixed_cost[i] * is_open[i] for i in W])
        + solver.Sum([instance.cost[i, j] * x[i, j] for i in W for j in R])
    )

    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("OR-Tools did not find an optimal MILP plan.")

    open_list = [i for i in W if is_open[i].solution_value() > 0.5]
    shipments = {pair: v.solution_value() for pair, v in x.items() if v.solution_value() > TINY}
    total = sum(instance.fixed_cost[i] for i in open_list) + transport_cost(instance, shipments)
    return {"total_cost": total, "open_warehouses": open_list, "shipments": shipments}


# solves the lp and the milp with both libraries and returns the numbers side by side
def compare_solvers(instance):
    lp_pulp = solve_transportation(instance).cost
    lp_ortools = solve_transportation_ortools(instance)["cost"]

    milp_pulp = solve_facility_location(instance)
    milp_ortools = solve_facility_location_ortools(instance)

    return {
        "lp_pulp": lp_pulp,
        "lp_ortools": lp_ortools,
        "lp_difference": abs(lp_pulp - lp_ortools),
        "milp_pulp": milp_pulp.total_cost,
        "milp_ortools": milp_ortools["total_cost"],
        "milp_difference": abs(milp_pulp.total_cost - milp_ortools["total_cost"]),
        "same_open_set": sorted(milp_pulp.open_warehouses) == sorted(milp_ortools["open_warehouses"]),
    }
