# detailed explanation
# stage 1 report. it prints how the simple nearest-warehouse rule does on the
# main network (seed 42).
#
# the rule: every region ships from the warehouse closest to it, and capacity
# is ignored. the report shows, for each warehouse, its capacity, the load the
# rule gives it and how full that is, then the total shipping cost and any
# warehouse pushed over its capacity.
#
# a plan that overloads a warehouse is not valid. so this cost is only a
# starting point, and it is not used to claim savings later.
#
# run it with: python run_stage1.py
from src.baseline import (
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import generate_instance

SEED = 42

# build the network, then the baseline plan and its numbers
inst = generate_instance(seed=SEED)
plan = nearest_warehouse_plan(inst)
shipments = shipments_from_plan(inst, plan)
loads = warehouse_loads(inst, shipments)
violations = capacity_violations(inst, shipments)

print(f"Network: seed={SEED}, {len(inst.warehouses)} warehouses, {len(inst.regions)} regions")
print(f"Total demand: {sum(inst.demand.values())} units | "
      f"total capacity: {sum(inst.capacity.values())} units")
print(f"Rate: ${inst.rate} per unit per km\n")

# one row per warehouse: how full does it get?
print(f"{'Warehouse':<10}{'Capacity':>10}{'Load':>8}{'Utilization':>13}")
for i in inst.warehouses:
    print(f"{i:<10}{inst.capacity[i]:>10}{loads[i]:>8}{loads[i] / inst.capacity[i]:>12.0%}")

print(f"\nBaseline transportation cost: ${transport_cost(inst, shipments):,.2f}")
if violations:
    print("Capacity violations:", violations)
else:
    print("Capacity violations: none")
