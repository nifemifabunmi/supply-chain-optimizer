rate = 0.5  # dollars per unit per km

warehouses = {
    "W1": {"pos": (0, 0), "cap": 150},
    "W2": {"pos": (10, 0), "cap": 150},
}
regions = {
    "R1": {"pos": (2, 0), "demand": 100},
    "R2": {"pos": (6, 0), "demand": 50},
    "R3": {"pos": (9, 0), "demand": 80},
}


def distance(p, q):
    """Straight-line distance between two (x, y) points."""
    dx = p[0] - q[0]
    dy = p[1] - q[1]
    return (dx ** 2 + dy ** 2) ** 0.5


def nearest_warehouse(region):
    """Name of the warehouse closest to the given region."""
    region_pos = regions[region]["pos"]
    nearest = None
    nearest_distance = float("inf")
    for warehouse in warehouses:
        d = distance(warehouses[warehouse]["pos"], region_pos)
        if d < nearest_distance:
            nearest_distance = d
            nearest = warehouse
    return nearest


def total_cost(shipments):
    """Sum of distance * units * rate over every (warehouse, region) shipment."""
    total = 0
    for (warehouse, region), amount in shipments.items():
        d = distance(warehouses[warehouse]["pos"], regions[region]["pos"])
        total += d * amount * rate
    return total


def warehouse_loads(shipments):
    """Total units shipped out of each warehouse."""
    loads = {name: 0 for name in warehouses}
    for (warehouse, region), amount in shipments.items():
        loads[warehouse] += amount
    return loads


# Build the baseline plan: every region ships its full demand from its nearest warehouse.
shipments = {}
for region in regions:
    warehouse = nearest_warehouse(region)
    demand = regions[region]["demand"]
    shipments[(warehouse, region)] = demand
    print(f"{region} -> {warehouse}: {demand} units")

loads = warehouse_loads(shipments)
print("Total cost:", total_cost(shipments))
print("Loads:", loads)

for name, load in loads.items():
    if load > warehouses[name]["cap"]:
        print(f"OVERLOAD at {name}: load {load} > capacity {warehouses[name]['cap']}")

# Quick self-check of distance(): a 3-4-5 triangle.
print("distance((0, 0), (3, 4)) =", distance((0, 0), (3, 4)))
