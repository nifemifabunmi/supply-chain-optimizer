# detailed explanation
# this file draws the five figures used in the readme. it does no maths of its
# own. every function takes numbers that were already computed by the models
# (see run_all.py) and turns them into one png picture.
#
# the five figures are:
#   1. network map      the warehouses, the regions and the plan the milp chose
#   2. plan costs       bars comparing the three shipping plans
#   3. cost sweep       total cost as opening costs get cheaper or dearer
#   4. unmet histogram  how much demand the fixed plan misses in the simulation
#   5. tornado          how far the cost moves when each input changes by 20%
#
# style rules used in every figure, so they all look like one set:
#   - one color per kind of thing:
#       blue   = the optimizer (lp, milp, re-plan)
#       orange = a baseline or the fixed plan
#       gray   = something that is not a valid plan, or just neutral
#   - thin marks, a light grid, and never two y-axes on one chart
#   - text stays dark gray and never takes the color of a series
#
# matplotlib is told to draw straight to files, so no window ever opens.
import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"
ORANGE = "#eb6834"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK2,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


# makes the axes quiet: no top or right border, light grid, thin axis lines
def _style_axes(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=9.5)


def _title(fig, title, subtitle):
    fig.text(0.06, 0.965, title, ha="left", va="top", fontsize=13.5, weight="bold", color=INK)
    fig.text(0.06, 0.915, subtitle, ha="left", va="top", fontsize=9.5, color=INK2)


def _money(value, sign=False):
    text = f"${abs(value):,.0f}"
    if sign:
        return ("+" if value >= 0 else "-") + text
    return text if value >= 0 else "-" + text


# ---------------------------------------------------------------------------
# 1. network map
# ---------------------------------------------------------------------------
# draws the warehouses, the regions and the shipments the milp chose
def plot_network_map(instance, milp, path):
    fig, ax = plt.subplots(figsize=(7.4, 7.0))
    fig.subplots_adjust(top=0.84, bottom=0.12, left=0.09, right=0.97)
    _title(fig, "The plan the MILP chose",
           "Line width = units shipped. Region size = demand. Synthetic network, seed 42.")

    max_units = max(milp.shipments.values())
    for (i, j), units in milp.shipments.items():
        x0, y0 = instance.wh_pos[i]
        x1, y1 = instance.reg_pos[j]
        ax.plot([x0, x1], [y0, y1], color=BLUE, alpha=0.45, solid_capstyle="round",
                linewidth=0.6 + 3.2 * units / max_units, zorder=1)

    for j in instance.regions:
        x, y = instance.reg_pos[j]
        ax.scatter(x, y, s=instance.demand[j] * 1.1, color=MUTED, edgecolor=SURFACE,
                   linewidth=1.5, zorder=2)

    for i in instance.warehouses:
        x, y = instance.wh_pos[i]
        if i in milp.open_warehouses:
            ax.scatter(x, y, marker="s", s=190, color=BLUE, edgecolor=SURFACE, linewidth=1.8, zorder=3)
            label = i
        else:
            ax.scatter(x, y, marker="s", s=190, facecolor=SURFACE, edgecolor=INK2, linewidth=1.6, zorder=3)
            label = f"{i} (closed)"
        ax.annotate(label, (x, y), xytext=(9, 9), textcoords="offset points",
                    fontsize=10.5, weight="bold", color=INK, zorder=4)

    ax.set_xlim(-3, 103)
    ax.set_ylim(-3, 103)
    ax.set_aspect("equal")
    ax.set_xlabel("km (east-west)", fontsize=9.5)
    ax.set_ylabel("km (north-south)", fontsize=9.5)
    _style_axes(ax, grid_axis="both")

    handles = [
        Line2D([], [], marker="s", linestyle="", markersize=9, color=BLUE, label="Open warehouse"),
        Line2D([], [], marker="s", linestyle="", markersize=9, markerfacecolor=SURFACE,
               markeredgecolor=INK2, label="Closed warehouse"),
        Line2D([], [], marker="o", linestyle="", markersize=7, color=MUTED, label="Customer region"),
        Line2D([], [], color=BLUE, alpha=0.6, linewidth=2, label="Shipment"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4,
              frameon=False, fontsize=9.5, labelcolor=INK2, handletextpad=0.4, columnspacing=1.6)
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 2. cost of each plan
# ---------------------------------------------------------------------------
# bars for the shipping cost of the three plans, all five warehouses open
# costs: {"naive": ..., "fair": ..., "lp": ...}
# overloads: {warehouse: units over capacity} for the naive plan
def plot_plan_costs(costs, overloads, path):
    fig, ax = plt.subplots(figsize=(8, 5.4))
    fig.subplots_adjust(top=0.78, bottom=0.17, left=0.11, right=0.97)
    saving = costs["fair"] - costs["lp"]
    _title(fig, "Shipping cost by plan",
           f"All five warehouses open, seed 42. Only the last two are valid plans.\n"
           f"The LP is ${saving:,.2f} ({100 * saving / costs['fair']:.2f}%) cheaper than the fair baseline.")

    labels = ["Nearest warehouse\n(ignores capacity)", "Nearest warehouse\nwith room left", "Optimized\n(LP)"]
    values = [costs["naive"], costs["fair"], costs["lp"]]
    colors = [MUTED, ORANGE, BLUE]
    bars = ax.bar(labels, values, color=colors, width=0.52, edgecolor=SURFACE, linewidth=2, zorder=2)

    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(values) * 0.015, _money(value),
                ha="center", va="bottom", fontsize=11, weight="bold", color=INK)

    over = "\n".join(f"{w} +{u:,.0f} units" for w, u in overloads.items())
    ax.text(bars[0].get_x() + bars[0].get_width() / 2, values[0] / 2,
            f"Not valid:\nover capacity\n{over}", ha="center", va="center",
            fontsize=9.5, color=SURFACE, weight="bold")

    ax.set_ylim(0, max(values) * 1.15)
    ax.set_ylabel("Shipping cost ($)", fontsize=10)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    _style_axes(ax, grid_axis="y")
    ax.tick_params(axis="x", labelsize=10, colors=INK2)
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. opening-cost sweep
# ---------------------------------------------------------------------------
# lines for the total cost of the best plan versus keeping every warehouse open
def plot_fixed_cost_sweep(multipliers, milp_totals, all_open_totals, n_open, breakeven, path):
    fig, ax = plt.subplots(figsize=(8, 5.4))
    fig.subplots_adjust(top=0.80, bottom=0.15, left=0.11, right=0.97)
    _title(fig, "When does closing a warehouse pay off?",
           "Every opening cost is multiplied by the number on the x-axis (1 = the assumed costs).")

    multipliers = np.array(multipliers)
    ax.plot(multipliers, all_open_totals, color=ORANGE, linewidth=2, label="Keep all five open", zorder=2)
    ax.plot(multipliers, milp_totals, color=BLUE, linewidth=2, label="Best plan (MILP chooses)", zorder=3)

    if breakeven is not None:
        ax.axvline(breakeven, color=MUTED, linewidth=1, zorder=1)
        ax.text(breakeven + 0.03, ax.get_ylim()[1] * 0.0 + min(milp_totals) + 120,
                f"break-even at x{breakeven:.2f}\nclosing starts to pay", fontsize=9, color=INK2, va="bottom")

    # show how many warehouses stay open in the best plan, along the bottom
    n_open = np.array(n_open)
    for value in sorted(set(n_open.tolist())):
        xs = multipliers[n_open == value]
        ax.text(xs.mean(), ax.get_ylim()[0] + 55, f"{value} open", ha="center", fontsize=9.5,
                color=INK2, weight="bold")

    ax.set_xlabel("Opening-cost multiplier", fontsize=10)
    ax.set_ylabel("Total cost: opening + shipping ($)", fontsize=10)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.set_xlim(multipliers.min(), multipliers.max())
    _style_axes(ax, grid_axis="y")
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=INK2)
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. unmet demand in the simulation
# ---------------------------------------------------------------------------
# histogram of unmet units per scenario for the fixed plan (re-plan is stated in text)
# we chart units, not dollars, because dollars depend on the assumed penalty
def plot_unmet_histogram(unmet_fixed, unmet_replan, path):
    unmet_fixed = np.asarray(unmet_fixed)
    unmet_replan = np.asarray(unmet_replan)
    n = len(unmet_fixed)
    none_fixed = float(np.mean(unmet_fixed < 1e-4))
    none_replan = int(np.sum(unmet_replan < 1e-4))
    p95 = float(np.percentile(unmet_fixed, 95))

    fig, ax = plt.subplots(figsize=(8, 5.4))
    fig.subplots_adjust(top=0.80, bottom=0.15, left=0.11, right=0.97)
    _title(fig, "How much demand does the fixed plan miss?",
           f"{n:,} random demand scenarios on the plan the MILP chose. Each bar = share of scenarios.")

    width = 20
    positive = unmet_fixed[unmet_fixed >= 1e-4]
    edges = np.arange(0, unmet_fixed.max() + width, width)
    counts, _ = np.histogram(positive, bins=edges)
    ax.bar(edges[:-1] + width / 2, 100 * counts / n, width=width * 0.88, color=ORANGE,
           edgecolor=SURFACE, linewidth=1.5, zorder=2)
    # exactly zero unmet gets its own bar, to the left of the others
    zero_x = -width
    ax.bar(zero_x + width / 2, 100 * none_fixed, width=width * 0.88, color=ORANGE,
           edgecolor=SURFACE, linewidth=1.5, zorder=2)
    ax.text(zero_x + width / 2, 100 * none_fixed + 0.6, f"{100 * none_fixed:.1f}%\nnothing unmet",
            ha="center", va="bottom", fontsize=9.5, color=INK2)

    ax.axvline(p95, color=INK2, linewidth=1, zorder=3)
    ax.text(p95 + 6, ax.get_ylim()[1] * 0.80, f"95th percentile:\n{p95:,.0f} units unmet",
            fontsize=9.5, color=INK2, va="top")
    ax.text(0.98, 0.97, f"Re-planning each scenario:\nnothing unmet in {none_replan:,} of {n:,}",
            transform=ax.transAxes, ha="right", va="top", fontsize=10, weight="bold", color=INK,
            bbox={"boxstyle": "round,pad=0.5", "facecolor": SURFACE, "edgecolor": AXIS, "linewidth": 0.8})

    ax.set_xlabel("Unmet demand in a scenario (units, bars are 20 units wide)", fontsize=10)
    ax.set_ylabel("Share of scenarios (%)", fontsize=10)
    ax.set_ylim(0, 100 * max(none_fixed, counts.max() / n) * 1.25)
    _style_axes(ax, grid_axis="y")
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 5. tornado chart
# ---------------------------------------------------------------------------
# bars for how far total cost moves when each input changes by -pct and +pct
def plot_tornado(table, path):
    pct = int(round(100 * table["pct"]))
    base = table["base_total"]
    rows = list(reversed(table["rows"]))  # biggest swing goes on top

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    fig.subplots_adjust(top=0.80, bottom=0.20, left=0.19, right=0.95)
    _title(fig, "Which inputs move the cost most?",
           f"Total cost (opening + shipping) when one input changes by -{pct}% or +{pct}%. Base: {_money(base)}.")

    height = 0.34
    for k, row in enumerate(rows):
        for offset, key, color in ((height / 2, "high_total", BLUE), (-height / 2, "low_total", ORANGE)):
            delta = row[key] - base
            ax.barh(k + offset, delta, height=height * 0.92, color=color, edgecolor=SURFACE,
                    linewidth=1.2, zorder=2)
            ax.text(delta + (14 if delta >= 0 else -14), k + offset, _money(delta, sign=True),
                    ha="left" if delta >= 0 else "right", va="center", fontsize=9, color=INK2)

    names = [r["input"].capitalize() + (" †" if r["open_set_changes"] else "") for r in rows]
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(names, fontsize=10.5, color=INK)
    ax.axvline(0, color=AXIS, linewidth=1, zorder=1)
    limit = max(abs(r[k] - base) for r in rows for k in ("low_total", "high_total")) * 1.28
    ax.set_xlim(-limit, limit)
    ax.xaxis.set_major_formatter(lambda v, _: _money(v, sign=True) if v else "$0")
    ax.set_xlabel("Change in total cost vs. base ($)", fontsize=10)
    _style_axes(ax, grid_axis="x")

    ax.legend(handles=[Patch(color=BLUE, label=f"Input +{pct}%"), Patch(color=ORANGE, label=f"Input -{pct}%")],
              loc="lower right", frameon=False, fontsize=9.5, labelcolor=INK2)
    fig.text(0.06, 0.04, "† The set of open warehouses changes in at least one of the two cases.",
             fontsize=9, color=INK2, ha="left")
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 6. real-map illustration
# ---------------------------------------------------------------------------
# hubs and metro areas on a lon/lat plot, with the shipments the milp chose.
# there is no coastline, only the points, so labels do the work.
def plot_realistic_map(instance, milp, path):
    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    fig.subplots_adjust(top=0.82, bottom=0.08, left=0.06, right=0.98)
    _title(fig, "Illustration: the same model on a real map",
           "25 largest US metro areas (size = 2020 population). Candidate hubs are our own picks. "
           "Not company data.")

    # offsets (dx, dy, align) in points, for labels that would otherwise collide
    region_offsets = {"Los Angeles": (-8, -3, "right"), "Riverside": (7, 3, "left"),
                      "San Diego": (7, -9, "left"), "Washington": (-7, -11, "right"),
                      "Baltimore": (-9, -2, "right"), "Philadelphia": (6, -11, "left"),
                      "New York": (9, -4, "left"), "Detroit": (7, 3, "left"),
                      "Charlotte": (7, 2, "left"), "Houston": (7, -10, "left"),
                      "San Antonio": (-7, -10, "right")}
    hub_offsets = {"Harrisburg": (-9, 8, "right"), "Columbus": (-10, -3, "right"),
                   "Chicago hub": (-8, 9, "right"), "Atlanta hub": (-9, -14, "right")}

    max_units = max(milp.shipments.values())
    for (i, j), units in milp.shipments.items():
        x0, y0 = instance.wh_pos[i]
        x1, y1 = instance.reg_pos[j]
        ax.plot([x0, x1], [y0, y1], color=BLUE, alpha=0.4, solid_capstyle="round",
                linewidth=0.5 + 3.0 * units / max_units, zorder=1)

    for j in instance.regions:
        x, y = instance.reg_pos[j]
        ax.scatter(x, y, s=instance.demand[j] * 1.6, color=MUTED, edgecolor=SURFACE,
                   linewidth=1.2, zorder=2)
        dx, dy, ha = region_offsets.get(j, (5, -9, "left"))
        ax.annotate(j, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7.5,
                    color=INK2, ha=ha, zorder=4)

    for i in instance.warehouses:
        x, y = instance.wh_pos[i]
        if i in milp.open_warehouses:
            ax.scatter(x, y, marker="s", s=150, color=BLUE, edgecolor=SURFACE, linewidth=1.6, zorder=3)
            dx, dy, ha = hub_offsets.get(i, (7, 7, "left"))
            ax.annotate(i, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=9.5,
                        weight="bold", color=INK, ha=ha, zorder=5)
        else:
            ax.scatter(x, y, marker="s", s=150, facecolor=SURFACE, edgecolor=INK2, linewidth=1.5, zorder=3)
            dx, dy, ha = hub_offsets.get(i, (7, 7, "left"))
            ax.annotate(f"{i} (closed)", (x, y), xytext=(dx, dy), textcoords="offset points",
                        fontsize=9, color=INK2, ha=ha, zorder=5)

    ax.set_aspect(1 / np.cos(np.radians(38)))  # keep east-west and north-south roughly to scale
    ax.set_xlabel("longitude", fontsize=9.5)
    ax.set_ylabel("latitude", fontsize=9.5)
    _style_axes(ax, grid_axis="both")

    handles = [
        Line2D([], [], marker="s", linestyle="", markersize=9, color=BLUE, label="Open hub"),
        Line2D([], [], marker="s", linestyle="", markersize=9, markerfacecolor=SURFACE,
               markeredgecolor=INK2, label="Closed hub"),
        Line2D([], [], marker="o", linestyle="", markersize=7, color=MUTED, label="Metro area"),
        Line2D([], [], color=BLUE, alpha=0.6, linewidth=2, label="Shipment"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=True, facecolor=SURFACE, edgecolor=GRID,
              fontsize=9, labelcolor=INK2)
    fig.savefig(path, dpi=170)
    plt.close(fig)
