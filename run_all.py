# detailed explanation
# this file regenerates every number and every figure in the project with one
# command. nothing in the results is typed in by hand. if you change the model
# or an assumption, run this again and the readme follows.
#
#   python run_all.py            full run (about 1-3 minutes)
#   python run_all.py --quick    smaller run for a fast check (numbers will differ)
#
# what it does, in order:
#   1. builds the main network (seed 42) and solves the baselines, lp and milp
#   2. checks the lp and milp with a second solver (or-tools)
#   3. finds the break-even and sweeps the opening costs
#   4. runs the demand simulation and the one-warehouse-down tests
#   5. runs the sensitivity analysis
#   6. repeats the key comparisons on many random networks
#   7. draws the five figures
#
# what it writes:
#   figures/*.png          the five figures
#   results/results.json   every number, for computers to read
#   results/RESULTS.md     every number, for people to read
#   README.md              only the block between the RESULTS markers changes
#
# the made-up assumptions (opening costs, demand variability, the penalty per
# unmet unit) are read from the code, so they are listed with the results.
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np

from src import plots
from src.baseline import (
    capacity_aware_plan,
    capacity_violations,
    nearest_warehouse_plan,
    shipments_from_plan,
    transport_cost,
)
from src.data import generate_instance
from src.experiments import compare_networks, summarize_networks
from src.lp_model import shadow_prices, solve_transportation
from src.milp_model import fixed_cost_sweep, solve_facility_location
from src.sensitivity import breakeven_multiplier, sensitivity_table
from src.shortage_model import PENALTY
from src.simulation import run_demand_simulation, run_disruptions, summarize

QUICK = "--quick" in sys.argv
SEED = 42              # the main network
N_SCENARIOS = 200 if QUICK else 1000
N_NETWORKS = 10 if QUICK else 50
CV = 0.2               # assumed demand variability
SIM_SEED = 2026
SWEEP_POINTS = 21 if QUICK else 41
SENS_PCT = 0.2

ROOT = Path(__file__).parent
FIG_DIR = ROOT / "figures"
RES_DIR = ROOT / "results"
FIG_DIR.mkdir(exist_ok=True)
RES_DIR.mkdir(exist_ok=True)

START_MARK = "<!-- RESULTS:START -->"
END_MARK = "<!-- RESULTS:END -->"


def step(text):
    print(f"[{time.time() - T0:6.1f}s] {text}", flush=True)


T0 = time.time()
R = {"settings": {"quick": QUICK, "seed": SEED, "n_scenarios": N_SCENARIOS, "n_networks": N_NETWORKS,
                  "cv": CV, "penalty": PENALTY, "sim_seed": SIM_SEED, "sensitivity_pct": SENS_PCT}}

# ---------------------------------------------------------------- main network
step("Main network: baselines, LP, MILP")
inst = generate_instance(seed=SEED)
total_demand = sum(inst.demand.values())
total_capacity = sum(inst.capacity.values())

naive_ship = shipments_from_plan(inst, nearest_warehouse_plan(inst))
overloads = capacity_violations(inst, naive_ship)
naive_cost = transport_cost(inst, naive_ship)
fair_cost = transport_cost(inst, capacity_aware_plan(inst))
lp = solve_transportation(inst)
prices = shadow_prices(inst)

milp = solve_facility_location(inst)
fixed_total_all = sum(inst.fixed_cost.values())
all_open_total = lp.cost + fixed_total_all

R["main"] = {
    "total_demand": total_demand,
    "total_capacity": total_capacity,
    "naive_cost": naive_cost,
    "naive_overloads": overloads,
    "fair_cost": fair_cost,
    "lp_cost": lp.cost,
    "lp_saving": fair_cost - lp.cost,
    "lp_saving_pct": 100 * (fair_cost - lp.cost) / fair_cost,
    "shadow_prices": {i: p for i, p in prices.items() if p > 1e-6},
    "fixed_costs": dict(inst.fixed_cost),
    "all_open_total": all_open_total,
    "milp_total": milp.total_cost,
    "milp_open": sorted(milp.open_warehouses),
    "milp_closed": [i for i in inst.warehouses if i not in milp.open_warehouses],
    "milp_fixed": milp.fixed_total,
    "milp_shipping": milp.transport_total,
    "milp_saving": all_open_total - milp.total_cost,
    "milp_saving_pct": 100 * (all_open_total - milp.total_cost) / all_open_total,
}

# ---------------------------------------------------------------- second solver
step("Cross-check with OR-Tools")
try:
    from src.crosscheck import compare_solvers
    R["crosscheck"] = compare_solvers(inst)
except ImportError:
    R["crosscheck"] = None

# ---------------------------------------------------------------- break-even and sweep
step("Opening-cost sweep and break-even")
breakeven = breakeven_multiplier(inst)
mults = np.round(np.linspace(0, 2, SWEEP_POINTS), 4)
sweep = fixed_cost_sweep(inst, mults)
R["breakeven_multiplier"] = breakeven

# ---------------------------------------------------------------- simulation
step(f"Demand simulation: {N_SCENARIOS} scenarios (re-solves an LP each time)")
sim = run_demand_simulation(inst, milp.shipments, milp.open_warehouses,
                            n_scenarios=N_SCENARIOS, seed=SIM_SEED, cv=CV)
R["simulation"] = summarize(sim)
R["outages"] = run_disruptions(inst, milp.shipments, milp.open_warehouses)

# ---------------------------------------------------------------- sensitivity
step("Sensitivity analysis")
sens = sensitivity_table(inst, pct=SENS_PCT)
R["sensitivity"] = sens

# ---------------------------------------------------------------- many networks
step(f"{N_NETWORKS} random networks")
net_rows = compare_networks(range(1, N_NETWORKS + 1))
R["networks"] = {"summary": summarize_networks(net_rows), "rows": net_rows}
R["networks"]["low_lp_saving_seeds"] = [r["seed"] for r in net_rows if r["lp_saving_pct"] < 1.0]

# ---------------------------------------------------------------- figures
step("Figures")
plots.plot_network_map(inst, milp, FIG_DIR / "network_map.png")
plots.plot_plan_costs({"naive": naive_cost, "fair": fair_cost, "lp": lp.cost}, overloads,
                      FIG_DIR / "plan_costs.png")
plots.plot_fixed_cost_sweep(
    mults,
    [s.total_cost for _, s in sweep],
    [lp.cost + m * fixed_total_all for m in mults],
    [len(s.open_warehouses) for _, s in sweep],
    breakeven,
    FIG_DIR / "fixed_cost_sweep.png",
)
plots.plot_unmet_histogram(sim.unmet["fixed"], sim.unmet["reopt"], FIG_DIR / "unmet_units.png")
plots.plot_tornado(sens, FIG_DIR / "sensitivity_tornado.png")

# ---------------------------------------------------------------- write results
step("Writing results")
gen = inspect.signature(generate_instance).parameters
assumptions = {k: gen[k].default for k in
               ("n_warehouses", "n_regions", "grid", "capacity_ratio", "rate", "demand_range", "fixed_cost_range")}
R["assumptions"] = {k: list(v) if isinstance(v, tuple) else v for k, v in assumptions.items()}
(RES_DIR / "results.json").write_text(json.dumps(R, indent=2, default=float))


def usd(x):
    return f"${x:,.2f}"


m = R["main"]
fx, ro = R["simulation"]["fixed"], R["simulation"]["reopt"]
nets = R["networks"]["summary"]
cc = R["crosscheck"]
lp_s, milp_s, open_s = nets["lp_saving_pct"], nets["milp_saving_pct"], nets["n_open"]
quick_note = "\n> QUICK RUN: smaller sample sizes, numbers differ from the full run.\n" if QUICK else ""

lines = []
add = lines.append
add(quick_note)
add("### Main network (seed 42)")
add("")
add(f"{assumptions['n_warehouses']} warehouses, {assumptions['n_regions']} regions, "
    f"{m['total_demand']:,} units of demand, {m['total_capacity']:,} units of capacity.")
add("")
add("| Plan | Cost | Valid? |")
add("|---|---:|---|")
over = ", ".join(f"{w} +{u:,.0f}" for w, u in m["naive_overloads"].items())
add(f"| Nearest warehouse, ignores capacity | {usd(m['naive_cost'])} shipping | No: over capacity ({over}) |")
add(f"| Nearest warehouse with room left (fair baseline) | {usd(m['fair_cost'])} shipping | Yes |")
add(f"| Transportation LP | {usd(m['lp_cost'])} shipping | Yes |")
add(f"| All five open, LP shipping | {usd(m['all_open_total'])} total | Yes |")
add(f"| MILP picks the open set ({', '.join(m['milp_open'])}) | {usd(m['milp_total'])} total | Yes |")
add("")
add(f"- LP versus the fair baseline: saves {usd(m['lp_saving'])} ({m['lp_saving_pct']:.2f}%). "
    f"The invalid baseline is not used for any saving claim.")
add(f"- MILP versus opening all five: saves {usd(m['milp_saving'])} ({m['milp_saving_pct']:.2f}%) "
    f"by closing {', '.join(m['milp_closed']) or 'nothing'}.")
sp = ", ".join(f"{w} ${p:.4f} per extra unit" for w, p in m["shadow_prices"].items())
add(f"- Shadow prices (capacity worth paying for): {sp or 'none, no capacity binds'}.")
if breakeven is not None:
    add(f"- Break-even: the best plan starts closing a warehouse once opening costs reach "
        f"{breakeven:.2f} times the assumed ones.")
if cc:
    add(f"- Second solver (OR-Tools GLOP and SCIP): LP differs by ${cc['lp_difference']:.6f}, "
        f"MILP differs by ${cc['milp_difference']:.6f}, same open set: {cc['same_open_set']}.")
add("")
add(f"### Demand uncertainty ({N_SCENARIOS:,} scenarios, cv = {CV}, penalty ${PENALTY:.0f} per unmet unit)")
add("")
add("Plan = the MILP's choice. \"Fixed\" keeps its routes and scales them; "
    "\"re-plan\" re-solves for every scenario. Both see the same scenarios.")
add("")
add("| Metric | Fixed plan | Re-plan |")
add("|---|---:|---:|")
add(f"| Fill rate | {fx['fill_rate']:.2%} | {ro['fill_rate']:.2%} |")
add(f"| Scenarios with nothing unmet | {fx['full_service_share']:.1%} | {ro['full_service_share']:.1%} |")
add(f"| Average unmet units | {fx['mean_unmet_units']:,.1f} | {ro['mean_unmet_units']:,.1f} |")
add(f"| Average shipping cost | {usd(fx['mean_shipping'])} | {usd(ro['mean_shipping'])} |")
add(f"| Average total cost incl. penalty | {usd(fx['mean_total_cost'])} | {usd(ro['mean_total_cost'])} |")
add(f"| 95th percentile total cost | {usd(fx['p95_total_cost'])} | {usd(ro['p95_total_cost'])} |")
add("")
add("Dollar totals include the assumed penalty, so lead with fill rate and the share of "
    "fully served scenarios when quoting this.")
add("")
add("### One warehouse down")
add("")
add("| Down | Usual load | Fixed plan: unmet / fill | Re-plan: unmet / fill |")
add("|---|---:|---:|---:|")
for r in R["outages"]:
    add(f"| {r['warehouse']} | {r['usual_load']:.0f} | {r['no_response_unmet']:.0f} / {r['no_response_fill']:.1%} "
        f"| {r['replan_unmet']:.0f} / {r['replan_fill']:.1%} |")
add("")
add("### Sensitivity (one input at a time, -20% and +20%)")
add("")
add(f"Base total cost {usd(sens['base_total'])}.")
add("")
add("| Input | Total at -20% | Total at +20% | Swing | Open set changes? |")
add("|---|---:|---:|---:|---|")
for r in sens["rows"]:
    add(f"| {r['input']} | {usd(r['low_total'])} | {usd(r['high_total'])} | {usd(r['swing'])} "
        f"| {'yes' if r['open_set_changes'] else 'no'} |")
add("")
add(f"### {nets['n_networks']} random networks (seeds 1 to {nets['n_networks']})")
add("")
add("| Quantity | Min | Median | Mean | Max |")
add("|---|---:|---:|---:|---:|")
add(f"| LP saving vs fair baseline (%) | {lp_s['min']:.2f} | {lp_s['median']:.2f} | {lp_s['mean']:.2f} | {lp_s['max']:.2f} |")
add(f"| MILP saving vs all open (%) | {milp_s['min']:.2f} | {milp_s['median']:.2f} | {milp_s['mean']:.2f} | {milp_s['max']:.2f} |")
add(f"| Warehouses open | {open_s['min']:.0f} | {open_s['median']:.0f} | {open_s['mean']:.1f} | {open_s['max']:.0f} |")
add("")
n_over = round(nets["naive_overload_share"] * nets["n_networks"])
add(f"The nearest-warehouse baseline overloaded a warehouse in {n_over} of {nets['n_networks']} networks.")
low = R["networks"]["low_lp_saving_seeds"]
if low:
    add(f"The LP saved under 1% on seeds {', '.join(map(str, low))}: the saving depends on the network.")
add("")
add("### Assumptions (made up, not measured)")
add("")
add(f"- Network: {assumptions['n_warehouses']} warehouses and {assumptions['n_regions']} regions placed at random "
    f"on a {assumptions['grid']:.0f} x {assumptions['grid']:.0f} grid; shipping ${assumptions['rate']} per unit per km.")
add(f"- Demand per region: uniform integer in {tuple(assumptions['demand_range'])}.")
add(f"- Total capacity is {assumptions['capacity_ratio']}x total demand.")
add(f"- Opening cost per warehouse: uniform in {tuple(assumptions['fixed_cost_range'])}. "
    f"Closing decisions depend heavily on this (see the break-even and sweep figure).")
add(f"- Demand uncertainty: lognormal multiplier, mean 1, cv {CV}. Unmet-unit penalty: ${PENALTY:.0f}.")
add("")
add("### Resume bullet (draft, fill in only what you can explain)")
add("")
add(f"> Built a supply chain optimization engine in Python (PuLP/CBC, cross-checked with OR-Tools): a transportation LP "
    f"cut shipping cost {lp_s['median']:.1f}% (median over {nets['n_networks']} synthetic networks) versus a "
    f"capacity-aware nearest-warehouse baseline, and a facility-location MILP cut total cost (opening + shipping) "
    f"{milp_s['median']:.1f}% (median) versus keeping every warehouse open. A {N_SCENARIOS:,}-scenario Monte Carlo "
    f"showed the cheapest fixed plan fully served only {fx['full_service_share']:.0%} of scenarios (fill rate "
    f"{fx['fill_rate']:.1%}), while re-planning per scenario served {ro['full_service_share']:.0%}.")
add("")
add("Say \"synthetic data\" and \"assumed opening costs\" out loud when you present this.")
add("")

body = "\n".join(lines).strip() + "\n"
(RES_DIR / "RESULTS.md").write_text("# Results\n\nGenerated by `run_all.py`. Do not edit by hand.\n\n" + body)

readme = ROOT / "README.md"
text = readme.read_text()
block = f"{START_MARK}\n{body}{END_MARK}"
if START_MARK in text and END_MARK in text:
    head = text[:text.index(START_MARK)]
    tail = text[text.index(END_MARK) + len(END_MARK):]
    readme.write_text(head + block + tail)
    step("README results block updated")
else:
    step("README has no RESULTS markers; left unchanged")

step("Done")
