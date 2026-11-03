"""The simple baseline: every region ships from its nearest warehouse.

It ignores capacity on purpose, so it can overload a warehouse.
capacity_violations() shows when that happens.

A plan is a dictionary: shipments[(warehouse, region)] = units.
That is the x_ij from the math.
"""


def nearest_warehouse_plan(instance):
    """For each region, find its closest warehouse. Returns {region: warehouse}."""
    return {
        # min() picks the warehouse with the smallest distance to region j.
        j: min(instance.warehouses, key=lambda i: instance.dist[(i, j)])
        for j in instance.regions
    }


def shipments_from_plan(instance, plan):
    """Each region ships its full demand from the warehouse chosen for it."""
    return {(i, j): instance.demand[j] for j, i in plan.items()}


def transport_cost(instance, shipments):
    """Total cost: add up (cost per unit * units shipped) for every shipment."""
    return sum(instance.cost[(i, j)] * units for (i, j), units in shipments.items())


def warehouse_loads(instance, shipments):
    """Total units leaving each warehouse (0 if it ships nothing)."""
    loads = {i: 0 for i in instance.warehouses}
    for (i, _j), units in shipments.items():
        loads[i] += units
    return loads


def capacity_violations(instance, shipments):
    """Warehouses that ship more than their capacity, and by how many units."""
    loads = warehouse_loads(instance, shipments)
    return {
        i: loads[i] - instance.capacity[i]
        for i in instance.warehouses
        if loads[i] > instance.capacity[i]
    }


def capacity_aware_plan(instance):
    """A fairer baseline: use the nearest warehouse that still has room.

    Biggest regions go first. Each region ships from its nearest warehouse
    until that one is full, then moves on to the next nearest.
    Returns shipments[(warehouse, region)] = units, like the other plans.
    """
    room = dict(instance.capacity)  # units each warehouse can still ship
    shipments = {}

    # Biggest orders first, so they get the closest warehouses.
    by_demand = sorted(instance.regions, key=lambda r: instance.demand[r], reverse=True)

    for j in by_demand:
        still_needed = instance.demand[j]

        # Try this region's warehouses from nearest to farthest.
        for i in sorted(instance.warehouses, key=lambda w: instance.dist[(w, j)]):
            if still_needed == 0:
                break
            units = min(still_needed, room[i])  # ship what fits
            if units > 0:
                shipments[(i, j)] = units
                room[i] -= units
                still_needed -= units

    return shipments
