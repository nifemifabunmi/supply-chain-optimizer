#oluwanifemi - lessons

rate = 0.5

warehouses = {
    "W1": {"pos": (0, 0), "cap": 150},
    "W2": {"pos": (10, 0), "cap": 150},
}

regions = {
    "R1": {"pos": (2, 0), "demand": 100},
    "R2": {"pos": (6, 0), "demand": 50},
    "R3": {"pos": (9, 0), "demand": 80},
}

#straight line distance between two points
def distance(p, q):
    dx = (p[0] - q[0]) ** 2
    dy = (p[1] - q[1]) ** 2
    return (dx + dy) ** 0.5

#nearest warehouse to a given region
def nearest_warehouse(region):
    nearest = None
    nearest_distance = float("inf")
    
    for warehouse in warehouses:
        d = distance(warehouses[warehouse]["pos"], regions[region]["pos"])
        if d < nearest_distance:
            nearest_distance = d
            nearest = warehouse
            
    return nearest 

#total cost of shipments
def total_cost(shipments):
    total = 0
    for (warehouse, region), amount in shipments.items():
        total += distance(warehouses[warehouse]["pos"], regions[region]["pos"]) * amount * rate
    return total

#total units shipped out of each warehouse
def warehouse_loads(shipments):
    loads = {w: 0 for w in warehouses}
    for (warehouse, region), amount in shipments.items():
        loads[warehouse] += amount
    return loads

#baseline plan: every region n ships its full demand from its nearest warehouse
shipments = {}
for region in regions:
    nearest = nearest_warehouse(region)
    shipments[(nearest, region)] = regions[region]["demand"]
    print(f"{region} - {nearest} ships {regions[region]['demand']} units")

loads = warehouse_loads(shipments)
for warehouse, load in loads.items():
    print(f"{warehouse} ships {load} units") 

print("Total cost of shipments:", total_cost(shipments))   

for name, warehouse in warehouses.items():
    if loads[name] > warehouse["cap"]:
        print(f"Warning - OVERLOAD: {name} exceeds capacity by {loads[name] - warehouse['cap']} units")


# Quick self-check of distance(): a 3-4-5 triangle.
print("distance((0, 0), (3, 4)) =", distance((0, 0), (3, 4)))
 