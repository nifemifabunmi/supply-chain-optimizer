"""Stage 1: the data model and the synthetic instance generator.

An Instance holds everything the models need. All lookups are dictionaries,
keyed the same way as the math in the technical document:

    demand[j]           d_j      units demanded by region j
    capacity[i]         cap_i    units warehouse i can ship per period
    fixed_cost[i]       f_i      cost of operating warehouse i (used from Stage 3)
    dist[(i, j)]        dist_ij  straight-line distance in km
    cost[(i, j)]        c_ij     = rate * dist_ij, dollars per unit shipped
"""
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Instance:
    warehouses: list      # warehouse names, e.g. ["W1", "W2", ...]
    regions: list         # region names, e.g. ["R1", "R2", ...]
    wh_pos: dict          # warehouse name -> (x, y)
    reg_pos: dict         # region name -> (x, y)
    demand: dict          # region name -> units
    capacity: dict        # warehouse name -> units
    fixed_cost: dict      # warehouse name -> dollars per period
    rate: float           # dollars per unit per km
    dist: dict            # (warehouse, region) -> km
    cost: dict            # (warehouse, region) -> dollars per unit


def euclidean(p, q):
    # Straight-line distance between two (x, y) points.
    return math.hypot(p[0] - q[0], p[1] - q[1])


def build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate):
    # Assemble an Instance from raw inputs and validate it.
    #
    # Used by generate_instance() and directly by the hand-checkable tests.
    #

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
    dist = {(i, j): euclidean(wh_pos[i], reg_pos[j]) for i in warehouses for j in regions}
    cost = {key: rate * d for key, d in dist.items()}
    return Instance(warehouses, regions, dict(wh_pos), dict(reg_pos), dict(demand),
                    dict(capacity), dict(fixed_cost), rate, dist, cost)


def generate_instance(seed=42, n_warehouses=5, n_regions=20, grid=100.0,
                      capacity_ratio=1.4, rate=0.05,
                      demand_range=(50, 200), fixed_cost_range=(500, 1500)):
    # Generate a reproducible synthetic network.
    #
    # Parameters:
    # capacity_ratio : total capacity as a multiple of total demand (must be >= 1).
    # fixed_cost_range : placeholder range. It is calibrated in Stage 3 so that
    #                       opening vs closing a warehouse is a real trade-off.
    
    rng = np.random.default_rng(seed)

    wh_names = [f"W{k + 1}" for k in range(n_warehouses)]
    reg_names = [f"R{k + 1}" for k in range(n_regions)]

    wh_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in wh_names}
    reg_pos = {n: tuple(rng.uniform(0, grid, size=2)) for n in reg_names}

    low, high = demand_range
    demand = {n: int(rng.integers(low, high + 1)) for n in reg_names}

    # Random capacity shares, scaled so total capacity = capacity_ratio * total demand.
    shares = rng.uniform(0.5, 1.5, size=n_warehouses)
    total_capacity = capacity_ratio * sum(demand.values())
    capacity = {n: int(math.ceil(s / shares.sum() * total_capacity))
                for n, s in zip(wh_names, shares)}

    fixed_cost = {n: float(rng.uniform(*fixed_cost_range)) for n in wh_names}

    return build_instance(wh_pos, reg_pos, demand, capacity, fixed_cost, rate)
