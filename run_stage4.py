"""Stage 4 report: how does the Stage 3 plan hold up when things go wrong?

Network: the plan the MILP chose on the main network (seed 42).

ASSUMPTIONS (made up, not measured):
  - demand swings with a coefficient of variation of 0.2
  - an unmet unit costs $100 (the penalty), far more than any shipping cost
"""
import time

from src.baseline import transport_cost, warehouse_loads
from src.data import generate_instance
from src.milp_model import solve_facility_location
from src.shortage_model import PENALTY
from src.simulation import run_demand_simulation, run_disruptions, summarize

SEED = 42
N_SCENARIOS = 1000
CV = 0.2
SIM_SEED = 2026

inst = generate_instance(seed=SEED)
plan = solve_facility_location(inst)
open_list = plan.open_warehouses
loads = warehouse_loads(inst, plan.shipments)

print(f"Network: seed={SEED}. Plan from the MILP: open {open_list}, "
      f"closed {[i for i in inst.warehouses if i not in open_list]}")
print(f"Planned shipping cost: ${transport_cost(inst, plan.shipments):,.2f}")
print(f"Total demand: {sum(inst.demand.values())} units | "
      f"capacity of open warehouses: {sum(inst.capacity[i] for i in open_list)} units\n")

print(f"{'Warehouse':<10}{'Capacity':>10}{'Planned load':>14}{'Utilization':>13}")
for i in open_list:
    print(f"{i:<10}{inst.capacity[i]:>10}{loads[i]:>14.0f}{loads[i] / inst.capacity[i]:>12.0%}")

# ---- Demand uncertainty ----
print(f"\nDemand simulation: {N_SCENARIOS} scenarios, cv={CV}, penalty=${PENALTY:.0f} per unmet unit")
start = time.time()
result = run_demand_simulation(inst, plan.shipments, open_list,
                               n_scenarios=N_SCENARIOS, seed=SIM_SEED, cv=CV)
print(f"(took {time.time() - start:.1f} seconds)\n")

summary = summarize(result)
labels = [
    ("mean_shipping", "Average shipping cost ($)", "{:,.2f}"),
    ("mean_unmet_units", "Average unmet units", "{:,.1f}"),
    ("fill_rate", "Fill rate (delivered / demanded)", "{:.2%}"),
    ("full_service_share", "Scenarios with nothing unmet", "{:.1%}"),
    ("mean_total_cost", "Average total cost incl. penalty ($)", "{:,.2f}"),
    ("p95_total_cost", "95th percentile total cost ($)", "{:,.2f}"),
    ("worst_5pct_avg_cost", "Average of worst 5% total cost ($)", "{:,.2f}"),
]
print(f"{'Metric':<40}{'Fixed plan':>14}{'Re-plan':>14}")
for key, name, fmt in labels:
    print(f"{name:<40}{fmt.format(summary['fixed'][key]):>14}{fmt.format(summary['reopt'][key]):>14}")

# ---- Warehouse outages ----
print("\nWarehouse outages (one open warehouse down at a time)")
print(f"{'Down':<6}{'Usual load':>11}{'No-response':>13}{'No-resp.':>10}{'Re-plan':>13}{'Re-plan':>9}{'Re-plan':>9}")
print(f"{'':<6}{'(units)':>11}{'unmet':>13}{'fill':>10}{'shipping ($)':>13}{'unmet':>9}{'fill':>9}")
for r in run_disruptions(inst, plan.shipments, open_list):
    print(f"{r['warehouse']:<6}{r['usual_load']:>11.0f}{r['no_response_unmet']:>13.0f}"
          f"{r['no_response_fill']:>10.1%}{r['replan_shipping']:>13,.2f}"
          f"{r['replan_unmet']:>9.0f}{r['replan_fill']:>9.1%}")

print("\nNote: re-plan shipping can be LOWER than the planned $%s because fewer units are delivered."
      % f"{transport_cost(inst, plan.shipments):,.2f}")
print("Compare the unmet units. The re-plan's unmet units equal demand minus the capacity left,")
print("which is the smallest shortage possible with one warehouse down.")
