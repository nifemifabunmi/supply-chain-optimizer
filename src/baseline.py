# detailed explanation
# this file holds the simple "rule of thumb" plans we compare the optimizer against.
#
# plan 1, nearest_warehouse_plan: every region ships from its closest
# warehouse. it ignores capacity on purpose, so it can overload a warehouse.
# capacity_violations() shows when that happens. because it breaks the
# capacity rule, it is NOT a valid plan and we never claim savings against it.
#
# plan 2, capacity_aware_plan: a fairer baseline. biggest regions go first,
# each one uses its nearest warehouse until that one is full, then moves on
# to the next nearest. this plan respects capacity, so it is the fair
# thing to compare the optimizer with.
#
# a plan is a dictionary: shipments[(warehouse, region)] = units.
# that is the x_ij from the math.
#
# helper functions here also work out the cost of a plan and how many
# units each warehouse ships (its load).


# for each region, find its closest warehouse. returns {region: warehouse}.
def nearest_warehouse_plan(instance):
    return {
        # min() picks the warehouse with the smallest distance to region j.
        j: min(instance.warehouses, key=lambda i: instance.dist[(i, j)])
        for j in instance.regions
    }


# each region ships its full demand from the warehouse chosen for it.
def shipments_from_plan(instance, plan):
    return {(i, j): instance.demand[j] for j, i in plan.items()}


# total cost: add up (cost per unit * units shipped) for every shipment.
def transport_cost(instance, shipments):
    return sum(instance.cost[(i, j)] * units for (i, j), units in shipments.items())


# total units leaving each warehouse (0 if it ships nothing).
def warehouse_loads(instance, shipments):
    loads = {i: 0 for i in instance.warehouses}
    for (i, _j), units in shipments.items():
        loads[i] += units
    return loads


# warehouses that ship more than their capacity, and by how many units.
def capacity_violations(instance, shipments):
    loads = warehouse_loads(instance, shipments)
    return {
        i: loads[i] - instance.capacity[i]
        for i in instance.warehouses
        if loads[i] > instance.capacity[i]
    }


# a fairer baseline: use the nearest warehouse that still has room.
# biggest regions go first. each region ships from its nearest warehouse
# until that one is full, then moves on to the next nearest.
# returns shipments[(warehouse, region)] = units, like the other plans.
def capacity_aware_plan(instance):
    room = dict(instance.capacity)  # units each warehouse can still ship
    shipments = {}

    # biggest orders first, so they get the closest warehouses.
    by_demand = sorted(instance.regions, key=lambda r: instance.demand[r], reverse=True)

    for j in by_demand:
        still_needed = instance.demand[j]

        # try this region's warehouses from nearest to farthest.
        for i in sorted(instance.warehouses, key=lambda w: instance.dist[(w, j)]):
            if still_needed == 0:
                break
            units = min(still_needed, room[i])  # ship what fits
            if units > 0:
                shipments[(i, j)] = units
                room[i] -= units
                still_needed -= units

    return shipments
