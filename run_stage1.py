# Stage 1 report: generate the main instance and evaluate the nearest-warehouse baseline.
from src.baseline import (
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import generate_instance

SEED = 42

inst = generate_instance(seed=SEED)
plan = nearest_warehouse_plan(inst)
shipments = shipments_from_plan(inst, plan)
loads = warehouse_loads(inst, shipments)
violations = capacity_violations(inst, shipments)

print(f"Instance: seed={SEED}, {len(inst.warehouses)} warehouses, {len(inst.regions)} regions")
print(f"Total demand: {sum(inst.demand.values())} units | "
      f"total capacity: {sum(inst.capacity.values())} units")
print(f"Rate: ${inst.rate} per unit per km\n")

print(f"{'Warehouse':<10}{'Capacity':>10}{'Load':>8}{'Utilization':>13}")
for i in inst.warehouses:
    print(f"{i:<10}{inst.capacity[i]:>10}{loads[i]:>8}{loads[i] / inst.capacity[i]:>12.0%}")

print(f"\nBaseline transportation cost: ${transport_cost(inst, shipments):,.2f}")
if violations:
    print("Capacity violations:", violations)
else:
    print("Capacity violations: none")
