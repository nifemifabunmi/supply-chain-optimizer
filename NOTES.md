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

## 6. Python tools used in the code

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

**`lambda`.** A tiny nameless function, used for the key above.

    lambda i: instance.dist[(i, j)]        # "given i, return this distance"

**Dataclass.** A labelled bundle of values. `Instance` holds all the network data.

**Seeded random numbers.** `np.random.default_rng(42)` gives the same "random"
numbers every time. That makes results repeatable and tests possible.

**`+=`.** Add to what is already there: `loads[i] += units`.

**`pytest` and `assert`.** `assert x == y` fails the test if the two differ.
`pytest.approx(240.0)` allows tiny decimal rounding.

---

## 7. How the files fit together

    data.py        builds the network (Instance)
        |
    baseline.py    nearest-warehouse plan, cost, loads, violations
        |
    lp_model.py    the optimizer and shadow prices
        |
    run_stage1.py / run_stage2.py     print the reports
    tests/                            check everything against hand-worked answers

Read the code in that order.

---

## 8. PuLP 4 quirks (they cost us time)

- Install CBC with `pip install "pulp[cbc]"`. It is no longer built in.
- Create the **problem first**, then variables with `prob.add_variable_dicts`.
- With two index lists you get nested dictionaries: `x[i][j]`, not `x[i, j]`.
- `prob.solve(...)` returns a stats object. Read `stats.status_str`.
- Read a variable's answer with `x[i][j].value()`.
- Most online examples are for PuLP 3. If an example breaks, this is why.

---

## 9. Your 30-second answer (the interview version)

> I built a model that decides how to ship products from warehouses to customer
> regions at the lowest cost. Each shipment between a warehouse and a region
> is a decision variable. The objective is total transportation cost. The
> constraints say every region's demand must be met and no warehouse can exceed
> its capacity. I solved it as a linear program with PuLP and checked it
> against hand-worked examples. A plain nearest-warehouse rule overloaded two
> warehouses, so I compared against a fairer version that respects capacity.
> On my synthetic test network the LP was 7.55% cheaper than that fair
> baseline, and across four test networks the saving ranged from 0.45% to
> 7.98%. All data is synthetic.

Say it out loud until it feels natural. Do not add numbers you have not
computed yourself.

---

## 10. Check yourself

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

---

## 11. Coming next

- **Stage 3, MILP:** warehouses get a fixed cost to stay open. Add a yes/no
  variable per warehouse, and the model decides which ones to open.
- **Many networks:** repeat the comparison over many seeds and report the range
  of savings, not one number.
- **Stage 4, simulation:** random demand and warehouse outages, to see how
  often the plan fails and what it costs.
- **Stage 5:** charts, README and GitHub.
