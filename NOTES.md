# Project Notes (plain language)

Read this top to bottom once. Then keep it open next to the code.
Everything here covers what is built so far: Stage 1 (baseline) and Stage 2 (LP).

---

## 1. The big picture

A company has **warehouses** and **customer regions**. Every region wants some
number of units. Every warehouse can only ship so many units. Shipping one unit
from a warehouse to a region costs money, and farther means more expensive.

**The question:** who should ship how much to whom, so the total shipping bill
is as small as possible?

Two ways to answer it:

1. **Simple rule (baseline):** each region uses its nearest warehouse.
2. **Optimizer (LP):** a solver searches all possible plans and returns the
   cheapest one that follows every rule.

The project compares the two, and later tests what happens when things go wrong.

---

## 2. The words you need

| Word | Meaning | In the code |
| --- | --- | --- |
| Warehouse | Where units ship from | `instance.warehouses` |
| Region | Where units are delivered | `instance.regions` |
| Demand | Units a region wants | `instance.demand["R1"]` |
| Capacity | Most units a warehouse can ship | `instance.capacity["W1"]` |
| Cost per unit | Dollars to ship one unit from a warehouse to a region. Equals the rate times the distance | `instance.cost[("W1", "R1")]` |
| Shipment | Units sent on one warehouse-to-region route. Written `x_ij` in math | `shipments[("W1", "R1")]` |
| Plan | The full set of shipments | the `shipments` dictionary |
| Valid plan | Every region gets its demand and no warehouse goes over capacity | |

---

## 3. Stage 1: the baseline

### How cost is calculated

For every shipment: **cost per unit x units shipped**. Then add them all up.

In math: total cost = sum of `cost_ij * x_ij`. The sigma sign just means
"add up one of these for every pair."

### Worked example (the small one from `learning/`)

Two warehouses, three regions, rate = $0.50 per unit per km, all on a line:

| Region | Nearest warehouse | Distance | Units | Cost |
| --- | --- | --- | --- | --- |
| R1 | W1 | 2 km | 100 | 0.5 x 2 x 100 = $100 |
| R2 | W2 | 4 km | 50 | 0.5 x 4 x 50 = $100 |
| R3 | W2 | 1 km | 80 | 0.5 x 1 x 80 = $40 |

Total = **$240**. W1 ships 100 units and W2 ships 130.

### The baseline's weakness

It never checks capacity. If W2 could only ship 100 units, the baseline would
still send it 130. That plan is **not valid**, so the baseline can look cheap
while being impossible to carry out.

`capacity_violations()` exists to catch exactly this.

---

## 4. Stage 2: the linear program (LP)

### What "linear program" means

You want the **best** answer (smallest cost) while following **rules**
(constraints). Everything is a straight-line (linear) formula: no squares, no
"if" statements. That is what makes it fast and exactly solvable.

An LP has three parts:

1. **Decision variables:** the numbers the solver chooses.
2. **Objective:** the thing to make as small (or large) as possible.
3. **Constraints:** the rules every answer must follow.

### Our three parts

**Decision variables.** `x[i][j]` is how many units warehouse `i` ships to
region `j`. There is one for every pair. The main network has 5 x 20 = 100.
They can't be negative (`lowBound=0`).

**Objective.** Make this smallest:

    cost[1][1] * x[1][1]  +  cost[1][2] * x[1][2]  +  ...  (every pair)

**Constraints.**

- *Demand rule* (one per region): units arriving at region `j`, added up from
  all warehouses, **equal** its demand.
- *Capacity rule* (one per warehouse): units leaving warehouse `i`, added up
  across all regions, are **at most** its capacity.

The main network has 20 demand rules and 5 capacity rules: 25 constraints.

### Why the LP is better than the baseline

The baseline picks one plan with a simple rule. The LP considers **every valid
plan** and returns the cheapest. It can split a region's order across several
warehouses, and it respects capacity.

### The small example, solved by the LP

Make W2's capacity only 100. Cost per unit on each route:

| | W1 | W2 |
| --- | --- | --- |
| R1 | $1.00 | $4.00 |
| R2 | $3.00 | $2.00 |
| R3 | $4.50 | $0.50 |

W2 would be 30 units over, so 30 units must move to W1. Which ones?

- Move R2 units: costs $3.00 - $2.00 = **$1.00 more** per unit.
- Move R3 units: costs $4.50 - $0.50 = **$4.00 more** per unit.

Move the cheap ones: 30 x $1 = $30 extra. Total = 240 + 30 = **$270**.
The solver does exactly this reasoning, just for hundreds of routes at once.
The tests check that the LP really returns $270 here.

### Shadow price (the finance idea)

A **shadow price** answers: "if this warehouse could ship one more unit, how
much money would we save?"

- Above 0: that warehouse is a **bottleneck**. Extra capacity there pays off.
- Exactly 0: it has spare room. More capacity would not help.

In the small example, W2's shadow price is $1.00, the cost of the cheapest
move we just worked out. It is like asking what one more dollar of a limit is
worth in a constrained portfolio problem.

In the code we find it by solving twice: once normally, once with one extra
unit of capacity. The drop in cost is the price.

---

## 5. What happened on the main network (seed 42)

These numbers come from running the code. Run it yourself and confirm.

| Plan | Cost | Valid plan? |
| --- | --- | --- |
| 1. Naive (nearest warehouse) | $2,941.33 | **No.** W1 is 27 units over, W5 is 128 over |
| 2. Fair (nearest warehouse with room) | $3,239.74 | Yes |
| 3. LP (optimal) | $2,995.22 | Yes |

**Plan 1 is not a fair comparison.** It only looks cheapest because it breaks
the capacity rule. The LP costs $53.90 more than plan 1, and that is correct:
the LP is the cheapest *valid* plan.

**Plan 2 is the fair comparison.** Both plans are valid, so the gap means
something. The LP saves **$244.52, which is 7.55%** of plan 2's cost.

### Why the fair baseline costs more than the LP

The fair baseline is **greedy**: it handles one region at a time, takes the
nearest warehouse with room, and never changes its mind. Early big regions can
fill up a nearby warehouse and push later regions to far-away ones. The LP
looks at all regions together, so it avoids that.

### One network is not the whole story

Same comparison on four different random networks (computed, not estimated):

| Seed | Fair baseline | LP | LP saving |
| --- | --- | --- | --- |
| 1 | $2,413.69 | $2,221.14 | 7.98% |
| 7 | $3,190.83 | $3,176.54 | 0.45% |
| 42 | $3,239.74 | $2,995.22 | 7.55% |
| 99 | $3,551.60 | $3,406.46 | 4.09% |

The saving ranges from under 1% to nearly 8%, depending on the network. So
never quote one seed as "the" saving. Later we run many networks and report the
range.

### Shadow prices in the LP

W1 saves $0.4660 per extra unit of capacity and W5 saves $0.3228. Both are at
100% utilization. The other three warehouses have spare room, so their price
is 0.

---

## 6. Stage 3: choosing which warehouses to open

### What changes

So far every warehouse was open and free to keep. Now each warehouse has an
**opening cost**: money you pay just for keeping it open, whether it ships 1
unit or 1,000. Two kinds of cost:

- **Variable cost:** grows with what you ship (our shipping cost).
- **Fixed cost:** paid once per open warehouse (our opening cost).

The question becomes: which warehouses should be open, and who ships what?
Closing a warehouse saves its opening cost, but shipping gets more expensive,
because regions must be served from farther away.

### The new variable: a yes/no switch

`open[i]` is 1 if warehouse `i` is open and 0 if it is closed. A variable that
can only be 0 or 1 is a **binary variable**. A model with some whole-number
variables and some continuous ones is a **mixed-integer linear program**
(MILP). The `x` (units shipped) can be any amount. The `open` switches cannot.

### The new objective

Make this smallest:

    (opening cost of every open warehouse)  +  (shipping cost of every shipment)

### The key rule

The capacity rule gets one change:

    units shipped out of warehouse i  <=  capacity[i] * open[i]

| `open[i]` | The right side is | So the warehouse can |
| --- | --- | --- |
| 0 (closed) | capacity x 0 = 0 | ship nothing |
| 1 (open) | capacity x 1 = capacity | ship up to capacity |

One line of math ties the yes/no switch to the shipping. Textbooks call this
a "big-M" constraint. Here the capacity plays the role of the big number.

### Why it is harder than the LP

With 5 warehouses there are 2 x 2 x 2 x 2 x 2 = 32 open/closed combinations.
Every extra warehouse doubles that. Solvers do not try them all. They use
**branch and bound**:

1. Solve an easier version where `open[i]` may be a fraction like 0.4.
2. If some come out fractional, split into two cases ("closed" and "open") and
   solve each.
3. Throw away any case that already costs more than a complete plan you have.

With only 5 warehouses we can also try every combination, which is how the
tests double-check the solver.

### The small example, by hand

Each warehouse can cover all 230 units (capacity 250). Cost per unit is in the
table from section 4. Shipping cost for each choice:

| Open | Shipping | Plus opening costs |
| --- | --- | --- |
| W1 only | 100x1 + 50x3 + 80x4.5 = $610 | W1's cost |
| W2 only | 100x4 + 50x2 + 80x0.5 = $540 | W2's cost |
| Both | 100x1 + 50x2 + 80x0.5 = $240 | both costs |

Say W1 costs $100 to open. Opening W2 as well saves 610 - 240 = **$370** of
shipping. So W2 is worth opening only if its opening cost is **below $370**.
The tests check this: at $369 both open, at $371 only W1 stays open.

### Results on the main network (seed 42)

The opening costs are **made-up assumptions** (more below). Computed by the code:

| Plan | Opening cost | Shipping | Total |
| --- | --- | --- | --- |
| A. Open all five | $1,442.14 | $2,995.22 | $4,437.36 |
| B. MILP choice (closes W2) | $1,062.53 | $3,084.51 | $4,147.04 |

Closing W2 adds $89.29 of shipping and saves $379.60 of opening cost. The MILP
saves **$290.32 (6.54%)** versus opening everything.

### Important: the opening costs are assumptions

Nobody gave us real opening costs. We made them up, so the saving above says
how the *method* behaves, not what a real company would save. Two honest
points:

- The first range we tried ($500 to $1,500) made closing a no-brainer, because
  closing one warehouse adds only about $90 to $1,200 of shipping. We switched
  to $100 to $600, the same size as those shipping increases, so closing is a
  real decision. That is a choice about the data, and we say so.
- Do not put "6.54%" in a headline. The useful result is the method and how it
  reacts when the assumptions change (next).

### How the answer changes

**Four networks** (opening costs made up the same way):

| Seed | Open everything | MILP | Closes | Saving |
| --- | --- | --- | --- | --- |
| 1 | $4,173.71 | $4,083.53 | W5 | 2.16% |
| 7 | $4,637.33 | $4,221.91 | W4 | 8.96% |
| 42 | $4,437.36 | $4,147.04 | W2 | 6.54% |
| 99 | $4,918.38 | $4,801.78 | W4 | 2.37% |

**Opening costs multiplied** (seed 42): W2 stays open at x0.1 and x0.2 and
closes from x0.25 upward. The flip point is about x0.235, which is the
shipping added by closing ($89.29) divided by the opening cost saved
($379.60). That is the break-even idea from the small example.

**Capacity decides how many can close** (seed 42, same opening costs):

| Total capacity / demand | Warehouses open | Closed |
| --- | --- | --- |
| 1.2 | 5 | none |
| 1.4 | 4 | W2 |
| 2.0 | 3 | W2, W3 |
| 3.0 | 3 | W2, W3 |

The open warehouses must still cover all demand. At 1.4, only one warehouse
can close at all, however expensive opening is. At higher ratios more *can*
close, but with these costs a third closing is not worth it, so 3.0 matches 2.0.

### "GapLimit" status

The solver sometimes reports `GapLimit` instead of `Optimal`. It means it
stopped because the proven distance to the best possible plan fell below a tiny
tolerance. We checked that the plan was identical to the exact answer: on all
four networks, the answer matches trying every open/closed combination. The
code accepts `Optimal` and `GapLimit`, and raises an error on anything else.

---

## 7. Stage 4: what if the world is not what we planned for?

### The new question

Stages 1 to 3 assumed we know demand exactly and every warehouse works.
Real life has neither. Stage 4 asks: **how well does our plan hold up when
demand is random or a warehouse goes down?**

Optimizing finds the cheapest plan for *expected* conditions. It says nothing
about what happens when conditions differ. That is what simulation tests.

### New piece 1: shortage variables

If demand is too high, or a warehouse is down, there may be no way to fill every
order. The Stage 2 LP would simply fail. So each region gets a **shortage
variable** `short[j]` (units we could not deliver), and each unmet unit costs a
**penalty**:

    for every region j:   units arriving + short[j] = demand[j]
    objective:            shipping cost + penalty * (all unmet units)

The penalty is **$100 per unit, an assumption**. It only needs to be bigger than
any shipping cost per unit, so the model leaves demand unmet only when it has
no choice. Hand check from the tests: capacity 100 + 100 for demand 230 leaves
30 units unmet, and the solver leaves exactly 30 units of R2 unmet, because
those are the most expensive units to serve.

### New piece 2: Monte Carlo simulation

**Monte Carlo** = try many random "what if" worlds and look at the averages and
the bad cases. One world is a **scenario**. We use 1,000.

In each scenario, every region's demand = its normal demand x a random
multiplier. The multiplier averages 1 and spreads according to the
**coefficient of variation (cv)**: cv = 0.2 means a typical swing of about 20%.
It is lognormal, so demand can never go negative. The seed makes the scenarios
repeatable.

**cv = 0.2 is an assumption, not something we measured.**

### New piece 3: two ways to respond

Both are tested on the **same scenarios**, so the comparison is fair:

- **Fixed plan:** keep the planned routes. Scale each region's shipments to its
  new demand. If that pushes a warehouse over capacity, cut all its shipments
  by the same share. Whatever is not delivered is unmet.
- **Re-plan:** solve the shortage LP again for this scenario.

The gap between them is the **value of being able to re-plan**.

### The metrics

| Metric | Meaning |
| --- | --- |
| Fill rate | Units delivered / units demanded, averaged over scenarios |
| Full-service share | Share of scenarios where nothing goes unmet |
| 95th percentile cost | 19 out of 20 scenarios cost less than this |
| Average of worst 5% | The average of the most expensive 1 in 20 scenarios. Finance people know the idea as CVaR |

### Results on the Stage 3 plan (seed 42, computed)

The plan: W1, W3, W4, W5 open, W2 closed. Planned loads:

| Warehouse | Capacity | Planned load | Utilization |
| --- | --- | --- | --- |
| W1 | 718 | 718 | 100% |
| W3 | 655 | 330 | 50% |
| W4 | 778 | 714 | 92% |
| W5 | 698 | 698 | 100% |

1,000 scenarios, cv = 0.2:

| Metric | Fixed plan | Re-plan |
| --- | --- | --- |
| Average shipping cost | $3,019.10 | $3,098.04 |
| Average unmet units | 52.7 | 0.0 |
| Fill rate | 97.93% | 100.00% |
| Scenarios with nothing unmet | 21.8% | 100.0% |
| Average total cost incl. penalty | $8,289.42 | $3,098.04 |
| 95th percentile total cost | $19,273.17 | $3,444.81 |
| Average of worst 5% | $22,957.26 | $3,539.50 |

**How to read it**

- The fixed plan delivers about 98% of demand on average, but it fully serves
  only about **one scenario in five**. Re-planning serves everything.
- **Be careful with the dollar totals.** About $5,270 of the fixed plan's
  $8,289 is just 52.7 unmet units x the assumed $100 penalty. Change the
  penalty and those totals change. The **fill rate and full-service share do
  not depend on the penalty**, so lead with those.
- The re-plan's average shipping ($3,098.04) is a little above the planned
  $3,084.51. That is expected, not an error: the cost curve bends upward as
  demand moves away from normal, so the average over many scenarios sits above
  the cost at the average.

### Why the plan is fragile

The cheapest plan fills W1 and W5 **to 100%** and W4 to 92%. That leaves no
room. If the regions that W1 serve happen to want a little more, W1 is
overloaded; the same for W5. Each has roughly a 50% chance of being overloaded
in a scenario, however small the swings are. Both avoiding it is about
50% x 50% = 25%, which is close to the 21.8% we see. (That is my explanation,
and the numbers fit it.)

The check, fixed plan only, different volatility:

| cv | Scenarios with nothing unmet | Fill rate |
| --- | --- | --- |
| 0.02 | 24.1% | 99.81% |
| 0.05 | 24.2% | 99.53% |
| 0.10 | 24.2% | 99.05% |
| 0.20 | 21.8% | 97.93% |
| 0.30 | 20.4% | 96.70% |

Bigger swings do not change *how often* it fails much, because it already
fails about 3 times in 4. They change *how badly*. The fill rate falls.

**Lesson: optimizing for the average leaves no slack, and a plan with no slack
is fragile.**

### Is the result stable?

Four different random seeds for the simulation (cv = 0.2):

| Simulation seed | Fixed: nothing unmet | Fixed: fill rate | Re-plan: nothing unmet |
| --- | --- | --- | --- |
| 2026 | 21.8% | 97.93% | 100.0% |
| 1 | 22.7% | 98.00% | 99.9% |
| 2 | 21.4% | 97.81% | 100.0% |
| 3 | 22.6% | 97.91% | 99.9% |

The conclusion does not depend on which random numbers we drew.

### Warehouse outages

Take each open warehouse down, one at a time, with the other three working.

| Down | Usual load | No response: unmet | No response: fill | Re-plan shipping | Re-plan unmet | Re-plan fill |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | 718 | 718 | 70.8% | $3,167.22 | 329 | 86.6% |
| W3 | 330 | 330 | 86.6% | $2,544.92 | 266 | 89.2% |
| W4 | 714 | 714 | 71.0% | $2,895.13 | 389 | 84.2% |
| W5 | 698 | 698 | 71.6% | $3,099.75 | 309 | 87.4% |

- **No response** means the units that warehouse normally ships are simply lost.
- **Re-plan** reroutes. It recovers a lot, but not everything.
- Re-plan shipping can look *lower* than the planned $3,084.51. That is only
  because fewer units are delivered. Compare the unmet units.
- **Re-planning cannot create capacity.** The re-plan's unmet units equal
  demand minus the capacity left. Example: W1 down leaves 2,849 - 718 = 2,131
  units of capacity against 2,460 demand, so 329 units must go unmet. No
  smarter routing can do better. A test checks this for every warehouse.

### The trade-off Stage 3 created

Stage 3 closed W2 to save $379.60 of opening cost. That also removed spare
capacity. With all five open, total capacity is 3,446, and losing even the
largest warehouse (W4, 778) still leaves 2,668, above the 2,460 demand. (Plain
arithmetic from the capacities, assuming we re-plan.) With W2 closed, every
single outage causes a shortage. **The cheapest network is not the most
resilient one.** The cost of resilience is the opening cost we saved.

---

## 8. Python tools used in the code

Each of these appears in the project. Try the small example in a Python shell.

**Dictionary.** Look something up by name.

    demand = {"R1": 100, "R2": 50}
    demand["R1"]            # 100

**Tuple as a dictionary key.** A pair works as a single key, which is how we
store one shipment per warehouse-region pair.

    shipments = {("W1", "R1"): 100}
    shipments[("W1", "R1")] # 100

**Loop over a dictionary's keys and values.**

    for (warehouse, region), units in shipments.items():
        ...                 # the pair splits into two names, units gets the value

**Comprehension.** Build a list or dictionary in one line.

    {name: 0 for name in ["W1", "W2"]}     # {"W1": 0, "W2": 0}

**`min` with a key.** Pick the item whose key value is smallest.

    min(["aaa", "b", "cc"], key=len)       # "b"

**`sorted` with a key.** Like `min`, but returns the whole list in order.
`reverse=True` puts the biggest first. `capacity_aware_plan` uses it twice.

    sorted(["aaa", "b", "cc"], key=len)    # ["b", "cc", "aaa"]

**`break`.** Leave a loop early, as soon as there is nothing left to do.

**`itertools.combinations`.** Every way to pick k items from a list. The tests
use it to try every set of open warehouses.

    list(combinations(["W1", "W2", "W3"], 2))   # [("W1","W2"), ("W1","W3"), ("W2","W3")]

**`dataclasses.replace`.** Copy an Instance with one field changed. The sweeps
use it to change the opening costs or capacities without rebuilding anything.

**numpy arrays.** Do math on a whole list of numbers at once. The simulation
stores one number per scenario in an array.

    import numpy as np
    costs = np.array([100.0, 120.0, 90.0])
    costs.mean()                     # 103.33...
    np.percentile(costs, 95)         # the 95th percentile
    np.sort(costs)[-2:]              # the two biggest values

**Random numbers with numpy.** `np.random.default_rng(seed)` makes the
generator. `rng.standard_normal(size)` gives bell-curve numbers, and
`np.exp(...)` turns them into positive multipliers.

**`lambda`.** A tiny nameless function, used for the key above.

    lambda i: instance.dist[(i, j)]        # "given i, return this distance"

**Dataclass.** A labelled bundle of values. `Instance` holds all the network data.

**Seeded random numbers.** `np.random.default_rng(42)` gives the same "random"
numbers every time. That makes results repeatable and tests possible.

**`+=`.** Add to what is already there: `loads[i] += units`.

**`pytest` and `assert`.** `assert x == y` fails the test if the two differ.
`pytest.approx(240.0)` allows tiny decimal rounding.

---

## 9. How the files fit together

    data.py        builds the network (Instance)
        |
    baseline.py    nearest-warehouse plan, cost, loads, violations
        |
    lp_model.py    the optimizer and shadow prices
        |
    milp_model.py  chooses which warehouses to open, plus the cost sweep
        |
    shortage_model.py   LP where demand may go unmet (penalty per unit)
        |
    simulation.py  random demand scenarios, outages, summary numbers
        |
    run_stage1.py ... run_stage4.py     print the reports
    tests/                            check everything against hand-worked answers

Read the code in that order.

---

## 10. PuLP 4 quirks (they cost us time)

- Install CBC with `pip install "pulp[cbc]"`. It is no longer built in.
- Create the **problem first**, then variables with `prob.add_variable_dicts`.
- With two index lists you get nested dictionaries: `x[i][j]`, not `x[i, j]`.
- `prob.solve(...)` returns a stats object. Read `stats.status_str`.
- Read a variable's answer with `x[i][j].value()`.
- A yes/no variable: `prob.add_variable_dicts("open", W, cat=pulp.LpBinary)`.
  With one index list the result is a plain dictionary, used as `is_open[i]`.
- Binary answers can come back as 0.9999999, so test `value > 0.5`, not `== 1`.
- A mixed-integer solve can return the status `GapLimit` (see section 6).
- `COIN_CMD(gapRel=0, gapAbs=0)` asks CBC to be as exact as it can.
- Most online examples are for PuLP 3. If an example breaks, this is why.

---

## 11. Your 30-second answer (the interview version)

> I built a model that decides how to ship products from warehouses to customer
> regions at the lowest cost. Each shipment between a warehouse and a region
> is a decision variable. The objective is total transportation cost. The
> constraints say every region's demand must be met and no warehouse can exceed
> its capacity. I solved it as a linear program with PuLP and checked it
> against hand-worked examples. A plain nearest-warehouse rule overloaded two
> warehouses, so I compared against a fairer version that respects capacity.
> On my synthetic test network the LP was 7.55% cheaper than that fair
> baseline, and across four test networks the saving ranged from 0.45% to
> 7.98%. I then added a yes/no variable per warehouse to choose which ones to
> open when each has an opening cost. On opening costs I assumed, it closed one
> warehouse and cut total cost by 2% to 9% across four networks, but that
> depends entirely on the assumed costs. Finally I stress-tested the plan with
> 1,000 random demand scenarios (volatility assumed) and with each warehouse
> taken down in turn. The cheapest plan ran two warehouses at 100% utilization,
> so it delivered about 98% of demand on average but fully served only about a
> fifth of scenarios. Re-solving the model per scenario restored full service.
> That showed me that optimizing for the average leaves no slack. All data is
> synthetic.

Say it out loud until it feels natural. Do not add numbers you have not
computed yourself.

---

## 12. Check yourself

1. What are the decision variables, the objective and the constraints?
2. Why must `sum of x[i][j] for i` equal demand, but only be at most capacity?
3. Why can the LP cost more than the baseline here, and why is that fine?
4. What does a shadow price of 0.4660 at W1 mean to a manager?
5. In `nearest_warehouse_plan`, what does `min(..., key=lambda ...)` do?
6. Why use a seed, and what would break in the tests without one?
7. Why is plan 2, not plan 1, the fair thing to compare the LP with?
8. In `capacity_aware_plan`, what changes if you process the smallest regions
   first instead of the biggest? Predict the effect, then try it.
9. Why does the LP saving change so much between seeds?
10. What does `capacity[i] * open[i]` do when `open[i]` is 0, and when it is 1?
11. Why is opening cost "fixed" and shipping cost "variable"?
12. Why can only one warehouse close when capacity is 1.4 times demand?
13. If every opening cost doubled on seed 42, would the MILP's choice change?
    Predict first, then check Sweep 1 in `run_stage3.py`.
14. Why can't we call "6.54%" a real-world saving?
15. Why do we need a shortage variable, and what happens to the LP without it?
16. Why is the $100 penalty an assumption? Which metrics do not depend on it?
17. The fixed plan fills 98% of demand on average but fully serves only about
    22% of scenarios. How can both be true?
18. Why can re-planning not fully fix an outage?
19. Why do we compare both responses on the same scenarios?
20. What do you predict if W1 and W5 each had 10% spare capacity? Try it by
    raising their capacity and re-running `run_stage4.py`.

---

## 13. Coming next

- **Sensitivity analysis:** change one input at a time (shipping rate, demand
  level, total capacity, opening cost) and see how much the cost moves.
- **Second solver:** re-solve the LP with OR-Tools (it installed on Python 3.14)
  and check both give the same cost.
- **Many networks:** repeat the comparisons over many seeds and report ranges.
- **Figures, `run_all.py`, README results, final write-up.**
