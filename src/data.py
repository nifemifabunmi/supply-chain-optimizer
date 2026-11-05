# detailed explanation
# this file builds the "network" the rest of the project works on.
# a network is a set of warehouses, a set of customer regions, and the
# numbers that connect them: how far apart they are, how much each region
# wants, how much each warehouse can ship, and what it costs to ship.
#
# everything is stored in plain python dictionaries. the names match the
# math in NOTES.md, so you can read the code and the math side by side:
#
#     demand[j]       units region j wants
#     capacity[i]     most units warehouse i can ship
#     fixed_cost[i]   cost of keeping warehouse i open (used from stage 3)
#     dist[(i, j)]    distance from warehouse i to region j
#     cost[(i, j)]    dollars to ship ONE unit from i to j  (rate * distance)
#
# two ways to get a network:
#   build_instance     you give it all the numbers (good for small tests)
#   generate_instance  it makes a random network from a seed
#
# the data is synthetic (made up). the same seed always gives the same
# network, so every result in the project can be reproduced.
# the opening costs are an assumption, not real data.
import math
from dataclasses import dataclass

import numpy as np


# an instance is just a labelled bundle of all the data for one network.
@dataclass
class Instance:
    warehouses: list    # names, like ["W1", "W2"]
    regions: list       # names, like ["R1", "R2"]
    wh_pos: dict        # warehouse name -> (x, y)
    reg_pos: dict       # region name -> (x, y)
    demand: dict        # region name -> units wanted
    capacity: dict      # warehouse name -> units it can ship
    fixed_cost: dict    # warehouse name -> cost to keep it open
    rate: float         # dollars per unit per km
    dist: dict          # (warehouse, region) -> km
    cost: dict          # (warehouse, region) -> dollars per unit


# straight-line distance between two (x, y) points.
def euclidean(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


# turn raw inputs into an instance, and stop early if the data is bad.
# dist is optional. leave it out and distances are straight lines between the
# positions. pass your own {(warehouse, region): km} to use other distances,
# for example real great-circle distances between cities.
def build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate, dist=None):
    # bad data should fail loudly here, not give strange answers later.
    if any(v <= 0 for v in demand.values()):
        raise ValueError("All demands must be positive.")
    if any(v <= 0 for v in capacity.values()):
        raise ValueError("All capacities must be positive.")
    if sum(capacity.values()) < sum(demand.values()):
        raise ValueError(
            f"Infeasible instance: total capacity {sum(capacity.values())} "
            f"is below total demand {sum(demand.values())}."
        )

    warehouses = list(wh_pos)
    regions = list(reg_pos)

    # one distance and one per-unit cost for every warehouse-region pair.
    if dist is None:
        dist = {(i, j): euclidean(wh_pos[i], reg_pos[j]) for i in warehouses for j in regions}
    else:
        dist = dict(dist)
    cost = {pair: rate * d for pair, d in dist.items()}

    return Instance(warehouses, regions, dict(wh_pos), dict(reg_pos), dict(demand),
                    dict(capacity), dict(fixed_cost), rate, dist, cost)


# make a random network. the same seed always gives the same network.
# capacity_ratio: total capacity = this number * total demand (at least 1).
# fixed_cost_range: an assumption, not real data. closing one warehouse adds
# roughly $90 to $1,200 of shipping on our test networks, so we use $100 to
# $600 to make opening vs closing a real choice.
def generate_instance(seed=42, n_warehouses=5, n_regions=20, grid=100.0,
                      capacity_ratio=1.4, rate=0.05,
                      demand_range=(50, 200), fixed_cost_range=(100, 600)):
    rng = np.random.default_rng(seed)  # the seeded random number generator

    wh_names = [f"W{k + 1}" for k in range(n_warehouses)]
    reg_names = [f"R{k + 1}" for k in range(n_regions)]

    # random spots on a grid x grid square.
    wh_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in wh_names}
    reg_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in reg_names}

    # random whole-number demand for each region.
    low, high = demand_range
    demand = {n: int(rng.integers(low, high + 1)) for n in reg_names}

    # give each warehouse a random share, then scale the shares so total
    # capacity equals capacity_ratio * total demand.
    shares = rng.uniform(0.5, 1.5, size=n_warehouses)
    total_capacity = capacity_ratio * sum(demand.values())
    capacity = {n: int(math.ceil(s / shares.sum() * total_capacity))
                for n, s in zip(wh_names, shares)}

    fixed_cost = {n: float(rng.uniform(*fixed_cost_range)) for n in wh_names}

    return build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate)
