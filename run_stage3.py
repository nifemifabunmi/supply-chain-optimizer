# detailed explanation
# stage 3 report. it asks which warehouses should be open on the main network
# (seed 42), and compares two choices:
#   a. open everything (the status quo) and ship with the stage 2 lp
#   b. let the milp choose which warehouses to open
#
# total cost here means opening costs plus shipping costs.
#
# the opening costs are made-up assumptions (see generate_instance), and the
# answer depends on them. that is why there are two sweeps at the end:
#   sweep 1 makes opening cheaper or dearer, to see when closing starts to pay
#   sweep 2 grows total capacity, to see how many warehouses can close
#
# run it with: python run_stage3.py
from src.data import generate_instance
from src.lp_model import solve_transportation
from src.milp_model import fixed_cost_sweep, solve_facility_location

SEED = 42

inst = generate_instance(seed=SEED)
D = sum(inst.demand.values())

print(f"Network: seed={SEED}, {len(inst.warehouses)} warehouses, {len(inst.regions)} regions")
print(f"Total demand: {D} units | total capacity: {sum(inst.capacity.values())} units\n")

print(f"{'Warehouse':<10}{'Capacity':>10}{'Opening cost':>14}")
for i in inst.warehouses:
    print(f"{i:<10}{inst.capacity[i]:>10}{inst.fixed_cost[i]:>14,.2f}")

# option a: keep every warehouse open and ship with the lp
lp = solve_transportation(inst)
all_fixed = sum(inst.fixed_cost.values())
all_open_total = lp.cost + all_fixed

# option b: let the milp choose
sol = solve_facility_location(inst)
closed = [i for i in inst.warehouses if i not in sol.open_warehouses]

print(f"\n{'Plan':<26}{'Opening':>12}{'Shipping':>12}{'Total':>12}")
print(f"{'A. Open all warehouses':<26}{all_fixed:>12,.2f}{lp.cost:>12,.2f}{all_open_total:>12,.2f}")
print(f"{'B. MILP choice':<26}{sol.fixed_total:>12,.2f}{sol.transport_total:>12,.2f}{sol.total_cost:>12,.2f}")
print(f"\nMILP opens: {sol.open_warehouses}   closes: {closed if closed else 'none'}")
print(f"MILP saves ${all_open_total - sol.total_cost:,.2f} versus opening everything "
      f"({(all_open_total - sol.total_cost) / all_open_total:.2%})")
print(f"Solver status: {sol.status}")

# why the milp's choice pays off: shipping goes up a little, opening costs go down more
print(f"Closing costs ${sol.transport_total - lp.cost:,.2f} more in shipping "
      f"and saves ${all_fixed - sol.fixed_total:,.2f} in opening costs.")

# sweep 1: make opening cheaper or more expensive
print("\nSweep 1: multiply every opening cost by a number")
print(f"{'Multiplier':>11}{'Open':>6}  {'Closed':<14}{'Opening':>10}{'Shipping':>10}{'Total':>11}")
for m, s in fixed_cost_sweep(inst, [0, 0.1, 0.2, 0.25, 0.5, 1, 2, 4]):
    shut = [i for i in inst.warehouses if i not in s.open_warehouses]
    print(f"{m:>11}{len(s.open_warehouses):>6}  {str(shut) if shut else '-':<14}"
          f"{s.fixed_total:>10,.0f}{s.transport_total:>10,.0f}{s.total_cost:>11,.0f}")

# sweep 2: what limits closing? total capacity compared with demand
print("\nSweep 2: how many warehouses can close as total capacity grows?")
print(f"{'Capacity ratio':>15}{'Open':>6}  {'Closed':<22}{'Total cost':>12}")
for ratio in [1.2, 1.4, 2.0, 3.0]:
    net = generate_instance(seed=SEED, capacity_ratio=ratio)
    s = solve_facility_location(net)
    shut = [i for i in net.warehouses if i not in s.open_warehouses]
    print(f"{ratio:>15}{len(s.open_warehouses):>6}  {str(shut) if shut else '-':<22}{s.total_cost:>12,.0f}")
