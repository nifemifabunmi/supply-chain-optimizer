"""Stage 2 report: three plans compared on the main network.

  1. Naive baseline : every region uses its nearest warehouse (ignores capacity)
  2. Fair baseline  : nearest warehouse that still has room
  3. LP             : the cheapest valid plan
"""
from src.baseline import (
    capacity_aware_plan,
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
    warehouse_loads,
)
from src.data import generate_instance
from src.lp_model import shadow_prices, solve_transportation

SEED = 42

inst = generate_instance(seed=SEED)

# Plan 1: naive baseline.
naive_ship = shipments_from_plan(inst, nearest_warehouse_plan(inst))
naive_cost = transport_cost(inst, naive_ship)
naive_viol = capacity_violations(inst, naive_ship)

# Plan 2: fair baseline.
fair_ship = capacity_aware_plan(inst)
fair_cost = transport_cost(inst, fair_ship)

# Plan 3: LP.
sol = solve_transportation(inst)
lp_loads = warehouse_loads(inst, sol.shipments)
prices = shadow_prices(inst)

print(f"Network: seed={SEED}, {len(inst.warehouses)} warehouses, {len(inst.regions)} regions")
print(f"LP status: {sol.status}\n")

# One row per warehouse. A shadow price above 0 means it is a bottleneck.
print(f"{'Warehouse':<10}{'Capacity':>10}{'LP load':>9}{'LP util':>9}{'Shadow $/unit':>15}")
for i in inst.warehouses:
    print(f"{i:<10}{inst.capacity[i]:>10}{lp_loads[i]:>9.0f}"
          f"{lp_loads[i] / inst.capacity[i]:>9.0%}{prices[i]:>15.4f}")

print()
print(f"{'Plan':<28}{'Cost':>12}{'Valid?':>9}")
print(f"{'1. Naive nearest-warehouse':<28}{naive_cost:>12,.2f}{'no' if naive_viol else 'yes':>9}")
print(f"{'2. Fair (capacity-aware)':<28}{fair_cost:>12,.2f}{'yes':>9}")
print(f"{'3. LP (optimal)':<28}{sol.cost:>12,.2f}{'yes':>9}")

if naive_viol:
    print(f"\nPlan 1 overloads: {naive_viol}. It is not a valid plan, so it is not a fair comparison.")

# The honest comparison: both of these are valid plans.
saving = fair_cost - sol.cost
print(f"\nLP vs fair baseline: saves ${saving:,.2f} ({saving / fair_cost:.2%} of the fair baseline cost)")

# How many regions get their units from more than one warehouse?
split = sum(1 for j in inst.regions
            if sum(1 for i in inst.warehouses if (i, j) in sol.shipments) > 1)
print(f"Regions served by more than one warehouse in the LP: {split}")
