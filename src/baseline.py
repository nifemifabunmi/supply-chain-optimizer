"""Stage 1: the nearest-warehouse baseline.

Every region (n) ships its full demand (d) from the warehouse closest to it.
The baseline ignores capacity on purpose, so it can overload a warehouse.
There is a `capacity_violations()` function that reports overloads instead of hiding them.

A plan is stored as shipments[(i, j)] = units, which mirrors x_ij in the math.
"""


#returns in this format: {region: nearest warehouse name}
def nearest_warehouse_plan(instance):
    return {
        j: min(instance.warehouses, key=lambda i: instance.dist[(i, j)])
        for j in instance.regions
    }

#returns {region: warehouse} into shipments[(warehouse, region)] = demand.
def shipments_from_plan(instance, plan):
    return {(i, j): instance.demand[j] for j, i in plan.items()}

#total cost = sum of c_ij * x_ij over every shipment
def transport_cost(instance, shipments):
    return sum(instance.cost[(i, j)] * units for (i, j), units in shipments.items())

#returns total units shipped out of each warehouse (zero if it ships nothing)
def warehouse_loads(instance, shipments):
    loads = {i: 0 for i in instance.warehouses}
    for (i, _j), units in shipments.items():
        loads[i] += units
    return loads

#returns {warehouse: units over capacity} for every overloaded warehouse
def capacity_violations(instance, shipments):
    loads = warehouse_loads(instance, shipments)
    return {
        i: loads[i] - instance.capacity[i]
        for i in instance.warehouses
        if loads[i] > instance.capacity[i]
    }
