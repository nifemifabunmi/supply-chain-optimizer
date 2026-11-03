"""Builds the network: warehouses, regions, demand, capacity and shipping costs.

Everything is stored in dictionaries. The names match the math in the notes:

    demand[j]       units region j wants
    capacity[i]     most units warehouse i can ship
    fixed_cost[i]   cost of keeping warehouse i open (used from Stage 3)
    dist[(i, j)]    distance from warehouse i to region j
    cost[(i, j)]    dollars to ship ONE unit from i to j  (rate * distance)
"""
import math
from dataclasses import dataclass

import numpy as np


# An Instance is just a labelled bundle of all the data for one network.
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


def euclidean(p, q):
    """Straight-line distance between two (x, y) points."""
    return math.hypot(p[0] - q[0], p[1] - q[1])


def build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate):
    """Turn raw inputs into an Instance, and stop early if the data is bad."""
    # Bad data should fail loudly here, not give strange answers later.
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

    # One distance and one per-unit cost for every warehouse-region pair.
    dist = {(i, j): euclidean(wh_pos[i], reg_pos[j]) for i in warehouses for j in regions}
    cost = {pair: rate * d for pair, d in dist.items()}

    return Instance(warehouses, regions, dict(wh_pos), dict(reg_pos), dict(demand),
                    dict(capacity), dict(fixed_cost), rate, dist, cost)


def generate_instance(seed=42, n_warehouses=5, n_regions=20, grid=100.0,
                      capacity_ratio=1.4, rate=0.05,
                      demand_range=(50, 200), fixed_cost_range=(500, 1500)):
    """Make a random network. The same seed always gives the same network.

    capacity_ratio:   total capacity = this number * total demand (at least 1)
    fixed_cost_range: placeholder for now; we tune it in Stage 3
    """
    rng = np.random.default_rng(seed)  # the seeded random number generator

    wh_names = [f"W{k + 1}" for k in range(n_warehouses)]
    reg_names = [f"R{k + 1}" for k in range(n_regions)]

    # Random spots on a grid x grid square.
    wh_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in wh_names}
    reg_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in reg_names}

    # Random whole-number demand for each region.
    low, high = demand_range
    demand = {n: int(rng.integers(low, high + 1)) for n in reg_names}

    # Give each warehouse a random share, then scale the shares so total
    # capacity equals capacity_ratio * total demand.
    shares = rng.uniform(0.5, 1.5, size=n_warehouses)
    total_capacity = capacity_ratio * sum(demand.values())
    capacity = {n: int(math.ceil(s / shares.sum() * total_capacity))
                for n, s in zip(wh_names, shares)}

    fixed_cost = {n: float(rng.uniform(*fixed_cost_range)) for n in wh_names}

    return build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate)
