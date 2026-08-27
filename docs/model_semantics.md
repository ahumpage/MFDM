# Model semantics in MFDM

What this model *means*, as opposed to what it computes. The maths itself — sets,
parameters, objective, constraints — is in [README.md](../README.md), and so is
everything about running it. This document owns the reasoning underneath.

Most of it is downstream of one change: **ramping couples the hours**. That is why
the price is a dual, why the merit-order check lost its authority, and why spill
exists at all, so ramping is introduced first and the general consequences follow.

| Section | What it owns |
|---|---|
| [1. The problem ramping introduces](#1-the-problem-ramping-introduces) | Why hours stopped being independent |
| [2. Ramp rate](#2-ramp-rate-what-limits-movement) | What limits movement |
| [3. Ramp cost](#3-ramp-cost-how-movement-becomes-money) | How movement becomes money |
| [4. Spill](#4-spill-when-a-plant-cannot-slow-down) | Spill vs curtailment, and why `SPILL_COST` is what it is |
| [5. What the reported price means](#5-what-the-reported-price-means) | **The clearing price.** Applies model-wide |
| [6. The merit-order check](#6-the-merit-order-check-gives-up-its-authority) | Its status. Applies model-wide |
| [7. The CSV contract](#7-the-csv-contract) | **Every input and output column.** Applies model-wide |
| [8. Worked example](#8-worked-example) | Two runnable three-hour fixtures |
| [9. What changed in the full run](#9-what-changed-in-the-full-run) | Before and after, over 744 hours |
| [10. Known gaps](#10-known-gaps) | Not decisions |

Charted in [docs/planning/ramping_plan.md](planning/ramping_plan.md) and
[docs/planning/onboarding_plan.md](planning/onboarding_plan.md). Implemented in
`model/MFDM.py`.

---

## 1. The problem ramping introduces

Before ramping, every hour in MFDM stood alone. The model solved 744 independent
little problems that happened to share a plant list. Nothing a plant did at 3am
constrained what it did at 4am.

Ramping couples the hours. That single change is the source of everything else in
this document — the new prices, the new costs, the abandoned correctness check —
because once hours are coupled, the cheapest thing to do *now* depends on what
happens *next*.

---

## 2. Ramp rate: what limits movement

Each plant carries a `Ramp_rate (MW/hr)` in the plants file: the most it may
move, in either direction, between two adjacent hours.

| Plant | Technology | Capacity | Ramp rate | Reaches full output in |
|---|---|---:|---:|---:|
| Plant 1 | Solar | 500 MW | 500 MW/hr | 1 hour |
| Plant 2 | Wind | 300 MW | 300 MW/hr | 1 hour |
| Plant 3 | Coal | 100 MW | 50 MW/hr | 2 hours |
| Plant 4 | Gas | 600 MW | 200 MW/hr | 3 hours |
| Plant 5 | Gas | 1000 MW | 400 MW/hr | 2.5 hours |

These bind. Coal is the slowest relative to its size, which is physically right,
and the full-run results show it losing 9,300 MWh of generation to the faster gas
plant precisely because it cannot chase demand.

Wind and solar have a ramp rate equal to their nameplate capacity, so they are
effectively unconstrained. That is a placeholder, not a finding — see
[§10 Known gaps](#10-known-gaps).

**Ramping is symmetric.** One rate governs both directions. Splitting up and down
into separate limits is a later piece of work.

### Hour 1 is free

The first hour has no predecessor, so no ramp constraint applies to it and every
plant starts at whatever output it likes at no charge. The horizon does not wrap
around: hour 744 is not followed by hour 1.

This is visible in the worked example below, where a plant moves 60 MWh in hour 1
for nothing and then pays $200 to move 10 MWh in hour 2.

Because the constraints link each hour to *the previous row of `demand.csv`*, the
hours must be ascending, contiguous and free of duplicates. `check_horizon` enforces
this. Before ramping it did not matter; now a stray sort order would quietly
constrain the wrong pairs of hours and still solve.

---

## 3. Ramp cost: how movement becomes money

A plant burns fuel less efficiently while it is changing output than while it is
holding steady. The plants file therefore carries a second, worse efficiency
for the ramping case, and the **ramp premium** is the difference between the two
fuel costs:

```
ramp_cost(p) = fuel_price(p) / ramp_efficiency(p)
             - fuel_price(p) / efficiency(p)
```

charged on every MWh moved, up or down.

| Plant | Fuel price | Efficiency | Ramp efficiency | Marginal cost | Ramp premium |
|---|---:|---:|---:|---:|---:|
| Plant 1 (Solar) | $0 | 1.0 | 1.0 | $1.00/MWh | $0.00/MWh |
| Plant 2 (Wind) | $0 | 1.0 | 1.0 | $2.00/MWh | $0.00/MWh |
| Plant 3 (Coal) | $7.80 | 0.4 | 0.3 | $21.50/MWh | $6.50/MWh |
| Plant 4 (Gas) | $19.80 | 0.5 | 0.2 | $41.60/MWh | $59.40/MWh |
| Plant 5 (Gas) | $19.80 | 0.3 | 0.1 | $76.00/MWh | $132.00/MWh |

### Three things this deliberately is not

**It is not a re-pricing of the whole hour.** The most literal reading of "use the
ramping efficiency instead of the normal efficiency" would price *all* of a moving
plant's output at the worse heat rate. That is conditional on *whether* the plant
moved, which needs a binary indicator, and the model would stop being a linear
program. The premium formulation keeps it an LP, and
[docs/research/ramping.md](research/ramping.md) records the decision to take a
linear penalty for exactly that reason.

**It is not a charge per hour spent ramping.** It is per MWh moved. A plant that
inches up by 1 MW pays for 1 MWh of movement, not for an hour of ramping.

**It does not replace the ordinary marginal cost.** A ramped MWh is charged
**twice**: once at the plant's ordinary marginal cost through the
`marginal_cost × gen` term, and again for the premium. That is what "the extra
cost of a moved MWh over a steady one" means, and it is worth stating because it
is easy to read the formula as a substitution rather than an addition.

**VOM is not in the premium.** VOM is charged on every MWh either way, through
the marginal cost. Only the fuel burn differs while ramping.

### Ramping is never cheaper than steady running

`build_parameters` validates that `ramp_efficiency(p) <= efficiency(p)` for every
plant. If a plant were more efficient while moving, its premium would come out
negative and the solver would be paid to jiggle it up and down for profit. This
mirrors the existing guard on ordinary efficiency.

---

## 4. Spill: when a plant cannot slow down

A ramp *down* limit is different in kind from a ramp *up* limit. An up limit puts
a ceiling over a plant. A down limit puts a **floor** under it: having been at
80 MW last hour, a plant with a 30 MW/hr rate cannot be below 50 MW this hour,
whatever demand does.

Floors can force the fleet to generate more than the demand. The `unserved`
variable only covers the opposite direction — too little generation — so without
somewhere for the surplus to go, the model would have no way to represent it.

`spill[t]` is that somewhere: **energy that was generated and had to be thrown
away.** The energy balance becomes

```
sum over p of gen[p][t]  +  unserved[t]  -  spill[t]  ==  demand[t]
```

Spill enters negatively because it is generation that did not serve demand.

### Spill is not curtailment

MFDM already reports a **Curtailment** column, and it means something different.
Both names are kept; see [CONTEXT.md](../CONTEXT.md).

| | Curtailment | Spill |
|---|---|---|
| What it is | Renewable resource available but not taken | Energy generated and then destroyed |
| Which plants | Wind and solar only | Any plant, in practice thermal |
| Price | Free | `SPILL_COST` |
| In the LP | Implicit — it is just `avail - gen` | An explicit decision variable |

### Why spill is priced at $1,000/MWh and not at LoL

The obvious choice is to price spill at LoL, mirroring unserved energy exactly.
It was the choice this effort started with, and it is wrong. **At LoL, spill is
strictly dominated by shedding load and never happens at all.**

The two are not symmetric in cost:

- Shedding a MWh **removes** a MWh of generation, so it saves `LoL - marginal_cost`.
- Dumping a MWh **requires** a MWh of extra generation, so it costs `SPILL_COST + marginal_cost`.

Set the two constants equal and shedding is always cheaper, by twice the marginal
cost, wherever the two are substitutable — and they are substitutable, because
spill in one hour is caused by generation in the hour before, which unserved
energy in that earlier hour relieves.

Measured on the Scenario 2 fixture below:

| Spill price | What the model does | Objective |
|---|---|---:|
| LoL ($8,300) | **Sheds 50 MWh of peak demand**, spills nothing | $418,800 |
| LoL, spill forced instead | Dumps 50 MWh | $420,600 |
| $1,000 | Serves all demand, dumps 50 MWh | **$55,600** |

The LoL model blacks out half of peak demand rather than dump a surplus later,
and the `spill` variable — introduced precisely to keep the model feasible under
ramp-down floors — never leaves zero.

`SPILL_COST = 1000` is chosen for two properties. It sits far above the most
expensive plant's marginal cost ($76/MWh), so spill stays firmly last in the
stack and is never a cheap way to avoid generating. And it sits far below LoL,
so dumping surplus is always preferred to shedding real load. It is a modelling
constant, not a physical quantity, and is worth revisiting.

### The floor can also trap a plant in its own good hours

There is a second, quieter failure mode. The ramp-down floor says
`gen[t] >= gen[t-1] - ramp_rate`. The capacity constraint says
`gen[t] <= avail[t]`. When a wind or solar profile collapses faster than the
plant's ramp rate, those two cannot both hold at any positive output — so the
only way for the plant to obey them is to have been generating far below its
resource in the earlier hour.

**This is not infeasibility, and that is what makes it dangerous.** The
all-zeros dispatch satisfies every ramp constraint, so the LP can always retreat
towards it and price the demand at LoL instead. The model does not fail; it
returns an absurdly expensive answer and says nothing.

Measured on a deliberately hostile fixture — a 500 MW solar farm limited to
10 MW/hr whose resource falls to zero after one hour:

| | Objective | Demand served | Solar used |
|---|---:|---:|---:|
| Solar left unconstrained | **$4,400** | 100% | 400 MWh |
| Solar limited to 10 MW/hr | **$2,415,010** | 42% | 10 MWh |

Constrained, the solar farm may use 10 MWh of a 500 MWh peak, because anything
more would strand it above its hour-2 ceiling, and 58% of demand goes unserved
at LoL.

The model does not correct for this. An earlier version carried a cost-free
ramp-down allowance bounded by the drop in the plant's own availability, so that
a plant was never charged for a ramp down the weather forced on it. That was
removed when ramping was simplified, and ramp up and ramp down are now
symmetric.

What avoids the trap instead is the input convention: **profiled plants are
left unconstrained.** A blank `Ramp_rate` means no limit. Every plant in
`plants_basic.csv` is blank, and the one plant given a ramp rate in
`plants_ramping.csv` is a coal plant, so no profiled plant is ramp limited in
either. Giving a wind or solar plant a finite ramp rate re-arms the trap, and
nothing in the model will say so.

---

## 5. What the reported price means

This is the decision with the widest blast radius.

Before ramping, MFDM reported two prices per hour and expected them to agree: the
marginal cost of the most expensive plant running, and the dual of the energy
balance. They agreed because, with hours independent, the cost of one more MWh in
hour *t* really was some plant's marginal cost.

Ramping destroys that. An extra MWh in hour *t* also changes what it costs to
serve *t-1* and *t+1*, so the dual absorbs ramp shadow costs from the neighbouring
hours and stops equalling any plant's marginal cost.

### The dual is now the clearing price

`Clearing Price ($/MWh)` is the dual of the energy balance. It is the honest
answer to "what would one more MWh in this hour cost the system", which is what a
price is for. Every downstream figure — `Market Cost`, the load-weighted average
price, producer surplus — is computed from it.

This **supersedes** the premise in [Map: Model semantics](planning/model_plan.md)
that "merit-order price stays canonical, the dual is a cross-check". That premise
was correct for a model where hours are independent. It is not scoped to survive
intertemporal cost, and it does not.

In the full 744-hour run the price takes 17 distinct values, up from a handful of
plant marginal costs, and its maximum is $160.40/MWh — which is Plant 4's
$41.60/MWh marginal cost plus twice its $59.40/MWh premium, the cost of moving it
up and then back down again. No plant offers $160.40. The system does.

### The old calculation survives as a diagnostic

`Highest Running Cost ($/MWh)` is the old merit-order calculation under the name
of what it actually measures: the marginal cost of the most expensive plant
generating. It is a "who was last in the stack" diagnostic and **it is not a
price**. It is used by `warn_merit_order_departures` and by `plant_summary.csv`, and must
not be used for revenue or surplus.

### The mismatch counter is gone

The model used to count hours where the two prices disagreed and explain them as
"degenerate hours where a plant sits exactly on its cap". Under ramping the two
are not supposed to be equal, so a cross-check between them is not a check. Both
the counter and its now-false explanation are deleted.

### A spill hour prices negative

In a scarcity hour the marginal MWh is shed, so lost load is the marginal unit and
the price is LoL. In a spill hour the marginal MWh is being *destroyed*, so one
more MWh of demand would **save** a MWh from destruction. The price is negative.

This falls out of the dual with no special case, and it is the model's first
negative price. [Map: Model semantics](planning/model_plan.md) ruled negative
prices out of scope on the grounds that they needed model features that did not
exist yet; ramping is that feature arriving.

When the price is negative, `Market Cost ($)` for that hour is negative too: the
model is reporting that consumers were paid to take power. `report()` prints a
note whenever this happens so the figure is never encountered without warning.

### `name_last_in_stack` under a dual

`name_last_in_stack` is only used for the *diagnostic* column, never for the
clearing price, so it still resolves to a plant name in the ordinary case. It
gains a `-SPILL_COST` case naming "spilled energy", and otherwise falls back to
"something at $X/MWh" — which is now the honest answer far more often.

---

## 6. The merit-order check gives up its authority

`warn_merit_order_departures` used to **raise**, and `main` treated it as fatal. Its
invariant: no plant may generate strictly below its dispatch ceiling while
something strictly more expensive is generating.

It is now a **printed warning**. The run continues and still archives. Since
giving up a correctness gate is the kind of thing a future reader will question,
here is why.

Ramping breaks the invariant in two separate ways, and both are optimal:

1. **A ramp cost** means a cheap plant may deliberately hold back beneath a
   dearer one, because moving up this hour and back down next hour costs more in
   premium than the fuel it saves.
2. **A ramp-down floor** means a cheap plant may run *low* now so that it can
   reach a low demand later without being stranded above it and spilling.

Neither can be told apart from a genuine modelling bug without re-solving the LP,
which is not something a cheap post-hoc check can do. So the check keeps its
arithmetic and drops its authority: it is a prompt to go and look.

The ceiling and floor it measures against are now:

```
ceiling[p][t] = min( avail[p][t],  gen[p][t-1] + ramp_rate(p) )
floor[p][t]   = max( 0,  gen[p][t-1] - ramp_rate(p) )
```

with hour 1 falling back to availability and zero. A plant sitting on its floor
is excluded from the report, because a plant pinned above demand by its own
ramp-down limit is not "leaving headroom unused" in any meaningful sense, and
including it would be both wrong and extremely noisy.

The "cost of the violation" figure is retained but relabelled: it is now
*"cheap headroom left unused is worth at most $X"*, an upper bound on any waste
rather than a bill, because some of that headroom is legitimately forgone.

---

## 7. The CSV contract

Every file the model reads and every file it writes. A column is a claim about
meaning, so each one is listed with what it claims.

### Inputs

The model reads four inputs, one per **role**: plants, fuel, demand and
profiles. A role is a fixed idea; the file filling it is not. Each role has a
flag naming its file — `--plants`, `--fuel`, `--demand`, `--profiles` — so
`inputs/` can hold several files for a role and a run says which it wants. A
bare name is looked for in `inputs/`, or in the folder given to `--inputs`; a
value containing a directory is used as a path in its own right.

| Role | Default file | Alternatives supplied |
|---|---|---|
| plants | `plants_basic.csv` | `plants_ramping.csv` |
| fuel | `fuel.csv` | — |
| demand | `demand.csv` | — |
| profiles | `profiles_basic.csv` | `profiles_renewables.csv` |

The defaults are the simple case: `plants_basic.csv` leaves `Ramp_rate` blank so
nothing is ramp limited, and `profiles_basic.csv` holds every factor at 1.0 so
nothing is resource limited. The alternatives switch those on independently.

Every role must be filled; a missing file is a `FileNotFoundError` naming the
path. What follows is the contract for each role — **columns, not file names**.
Any file with the right columns can fill a role. The `--inputs` folder is the
one exception: it is read by the plain names `plants.csv`, `fuel.csv`,
`demand.csv` and `profiles.csv`, which is what the worked examples use.

The run archive is keyed by role too, so a run using `plants_ramping.csv` is
filed under `plants.csv` and records `plants_ramping.csv` as its `source`. That
is what makes a basic run and a ramping run directly diffable, and it is what
`runs.py restore` uses to put each file back where it came from.

#### plants — one row per plant

| Column | Meaning |
|---|---|
| `Plant` | The plant's name, and its identity throughout the outputs. Must be unique. |
| `Technology` | `Coal`, `Gas`, `Wind` or `Solar`. Decides whether the plant is profiled. |
| `Fuel` | Looked up in `fuel.csv`. Wind and solar carry the literal string `None`, which is read as text and not as a missing value. |
| `Capacity (MW)` | Nameplate. The plant's ceiling in any hour, before profiles and ramping. |
| `Efficiency (MWh/MWhTh)` | Steady-state efficiency. Electrical MWh out per thermal MWh in. |
| `VOM ($/MWh)` | Variable operating and maintenance cost, charged on every MWh whether the plant is moving or not. |
| `Ramp_rate (MW/hr)` | The most the plant may move between adjacent hours, in either direction. |
| `Ramp_efficiency(MWh/MWhTh)` | Efficiency while moving. Validated never to exceed `Efficiency`; see [§3](#ramping-is-never-cheaper-than-steady-running). Located by column-name prefix, so the exact spacing does not matter. |

#### fuel — one row per fuel

| Column | Meaning |
|---|---|
| `Technology` | Misleadingly named: it holds **fuel** names, matched against `plants.csv`'s `Fuel` column. |
| `Fuel Price ($/MWhTh)` | Price per **thermal** MWh. Divided by efficiency to reach an electrical cost. |

#### demand — one row per hour

| Column | Meaning |
|---|---|
| `Hour` | The hour number. Must be ascending, contiguous and free of duplicates — `check_horizon` enforces this, because the ramp constraints link each row to the one above it. |
| `Demand in region 1 (MWh)` | Demand to be served in that hour. |

The horizon is however many rows this file has, currently 744. It does not wrap:
the last hour is not followed by the first.

#### profiles — hourly availability factors

This is the one input whose shape cannot be guessed, because it may have **one
header row or two**:

```
,FRA,FRA          <- optional region row
hours,Wind,Solar
1,0.6,0
2,0.5,0
```

`load_data` decides which it is by looking at the first cell of the first line.
A region row is blank there, because the column it heads is the hour column,
whose name lives on the row below — so a file starting `,FRA,FRA` has a region
row and one starting `hours,Wind,Solar` does not. With a region row the two
rows are read with `header=[0, 1]` and flattened into names of the form
`FRA Wind`; without one the series names are used as they stand. Column
matching then looks for the technology token (`wind`, `solar`) anywhere in the
name, so the region never affects which column a plant is matched to, and both
shapes behave identically from there on.

Values are **availability factors**: a share of nameplate between 0 and 1, one per
profiled technology per hour. A technology with no matching column is not
profiled, and the model prints a note rather than failing. The file must cover
every hour in `demand.csv`.

> The region row is a hook for multi-region support that never arrived, and
> nothing consumes it. Whether it is removed altogether is
> [an open question](planning/onboarding_plan/11-profiles-region-header.md).
> Accepting both shapes is what keeps archived runs restorable: every archived
> `profiles.csv` has two rows, and the parser still understands them.

### Outputs

#### `results/dispatch_results.csv`

| Column | Claim |
|---|---|
| `Clearing Price ($/MWh)` | The dual of the energy balance. What one more MWh in this hour would cost the system. Can be negative. |
| `Highest Running Cost ($/MWh)` | Diagnostic. Marginal cost of the most expensive plant generating. **Not a price.** |
| `Production Cost ($)` | Fuel and VOM only. Deliberately **excludes** ramp cost, so the objective's components stay separable. |
| `Ramp Up (MWh)` | System total moved upward into this hour. Zero in hour 1. |
| `Ramp Down (MWh)` | System total moved downward into this hour. Zero in hour 1. |
| `Ramp Cost ($)` | **The premium alone**, not the total cost of the ramped energy. The fuel underneath a ramped MWh is already in `Production Cost`; including it here would double count. |
| `Market Cost ($)` | `Clearing Price × Demand`. Negative in a spill hour. |
| `Unserved Energy (MWh)` / `Unserved Cost ($)` | Demand not met, and it at LoL. |
| `Spill (MWh)` / `Spill Cost ($)` | Energy generated and thrown away, and it at `SPILL_COST`. |
| `Curtailment (MWh)` | Renewable resource available and not taken. Free and implicit. Not spill. |

Ramp quantities are **system totals, one pair of columns**, not per plant. The
file already carries two columns per plant; adding two more each would make it
unreadable. Per-plant ramp lives in the summary.

#### `results/plant_summary.csv`

New columns: `Ramp Rate (MW/hr)`, `Ramping Efficiency (MWh/MWhTh)`,
`Ramp Premium ($/MWh)`, `Total Ramp Up (MWh)`, `Total Ramp Down (MWh)`,
`Ramp Cost ($)`.

`Production Cost ($)` stays fuel and VOM only, matching the results file, so the
two still tie out.

`Hours Setting Price` is renamed **`Hours Last in Stack`** and is matched against
`Highest Running Cost`, not against the price. Under a dual, no plant's marginal
cost equals the clearing price, so the old column would have read zero for every
plant in almost every hour. Counting who was last in the merit order is still
useful; it is simply not the same thing as setting the price.

#### Ramp quantities come from the dispatch, not from the LP variables

`ramp_up` and `ramp_down` are defined by *inequalities*
(`gen[t] - gen[t-1] <= ramp_up[t]`), so the objective only pushes them down to the
true movement when the plant has a non-zero premium. A plant with a zero premium —
both renewables, today — can leave them anywhere up to its rate limit without
changing the objective by a cent.

Every reported ramp quantity is therefore **recomputed from the generation profile
after solving**, never read from the variables. The variables exist only to carry
cost into the objective.

#### The objective reconciliation

`report()` prints all four components and their sum:

```
LP objective = Production cost + Ramp cost + Unserved cost + Spill cost
```

and then **checks that sum against what the solver actually minimised**, printing
a warning if they drift. The reconciliation used to be a claim to the user; now it
is a test that runs on every solve. If a cost is ever double counted or dropped
from a column, this is where it surfaces.

---

## 8. Worked example

Two three-hour, two-plant fixtures. Both are real input folders and both can be
run:

```
python model/MFDM.py --inputs docs/examples/ramping/scenario_1_holding_back --results /tmp/s1
python model/MFDM.py --inputs docs/examples/ramping/scenario_2_spill        --results /tmp/s2
```

Runs over custom folders are never archived, so they cannot disturb the real
results.

Both scenarios use the same two plants, with clean arithmetic:

| Plant | Fuel price | Efficiency | Marginal cost | Ramp efficiency | Ramp premium |
|---|---:|---:|---:|---:|---:|
| Cheap | $12/MWhTh | 0.6 | **$20/MWh** | 0.3 | **$20/MWh** |
| Dear | $20/MWhTh | 0.5 | **$40/MWh** | 0.5 | **$0/MWh** |

Both are 100 MW. `Cheap` has a ramp rate of 30 MW/hr throughout. `Dear`'s rate
differs between the scenarios and is given below.

---

### Scenario 1 — a cheap plant holds back to dodge a ramp charge

`Dear` ramp rate: **50 MW/hr**. Demand: **60, 120, 60 MWh**.

**Dispatch:**

| | Hour 1 | Hour 2 | Hour 3 |
|---|---:|---:|---:|
| Demand | 60 | 120 | 60 |
| Cheap | 60 | 70 | 60 |
| Dear | 0 | 50 | 0 |
| Cheap's ceiling | 100 | **90** | 100 |

**Hour 1 is free.** `Cheap` goes from nothing to 60 MWh and pays no premium,
because hour 1 has no predecessor. Compare that with hour 2, where moving just
10 MWh costs $200.

**`Dear`'s ramp rate binds.** Starting from 0, it can reach at most 50 MWh in
hour 2. Demand is 120, so `Cheap` is forced up to 70 whether it likes it or not.

**`Cheap` violates merit order, and is right to.** In hour 2 its ceiling is
`min(100, 60 + 30) = 90`, but it generates only 70, leaving 20 MWh of $20/MWh
headroom unused while $40/MWh `Dear` runs. The old check would have called this a
fatal bug. It is optimal: each extra MWh from `Cheap` saves $20 of `Dear`'s fuel
but costs $20 to ramp up and $20 to ramp back down in hour 3 — a net loss of $20.

The model prints exactly this as a merit order note, valuing the unused headroom
at $400 and continuing.

**Costs:**

| | MWh | Rate | Cost |
|---|---:|---:|---:|
| Hour 1 — Cheap | 60 | $20 | $1,200 |
| Hour 2 — Cheap | 70 | $20 | $1,400 |
| Hour 2 — Dear | 50 | $40 | $2,000 |
| Hour 3 — Cheap | 60 | $20 | $1,200 |
| **Production cost** | | | **$5,800** |
| Ramp up, hour 2 (Cheap, 60→70) | 10 | $20 | $200 |
| Ramp down, hour 3 (Cheap, 70→60) | 10 | $20 | $200 |
| **Ramp cost** | | | **$400** |
| **LP objective** | | | **$6,200** |

`Dear` moves 100 MWh in total and pays nothing, because its ramp premium is zero.

**Prices:**

| Hour | Clearing price | Why |
|---|---:|---|
| 1 | **$0.00** | One more MWh of demand means `Cheap` runs at 61 instead of 60. That costs $20 of fuel — but it also shrinks hour 2's ramp from 10 MWh to 9 MWh, saving $20 of premium. The two cancel exactly. |
| 2 | **$60.00** | `Dear` is stuck at its rate limit, so an extra MWh must come from `Cheap`: $20 of fuel, $20 to ramp up into hour 2, $20 to ramp back down into hour 3. |
| 3 | **$0.00** | Mirror of hour 1. An extra MWh means a smaller ramp down, and the saving cancels the fuel. |

Hour 2's $60/MWh is the headline. **No plant offers $60.** `Cheap` is $20 and
`Dear` is $40. The price is a property of the system across three hours, not of
anyone's offer, and this is what it means for the dual to become canonical.

Hours 1 and 3 pricing at **zero while a plant is generating** is the same point
from the other side. Under the old merit-order rule they would have priced at
$20/MWh, `Cheap`'s marginal cost. That would have been wrong: serving one more
MWh in those hours genuinely costs the system nothing.

---

### Scenario 2 — a plant that cannot slow down, and a negative price

`Dear` ramp rate: **20 MW/hr**. Demand: **60, 100, 0 MWh**.

Demand collapses to zero in hour 3 and neither plant can get down in time.

**Dispatch:**

| | Hour 1 | Hour 2 | Hour 3 |
|---|---:|---:|---:|
| Demand | 60 | 100 | 0 |
| Cheap | 60 | 80 | **50** |
| Dear | 0 | 20 | 0 |
| Total generated | 60 | 100 | **50** |
| **Spill** | 0 | 0 | **50** |

In hour 3 `Cheap` is at 80 from hour 2 and can shed only 30 MW/hr, so it cannot
go below 50 MWh. Demand is zero. Those 50 MWh are generated, cannot be used, and
are thrown away.

The model pre-positions to make the spill as small as it can: `Cheap` runs at 80
rather than its ceiling of 90 in hour 2 specifically so that its hour-3 floor is
50 rather than 60. This is the second kind of legitimate merit-order departure —
holding back to stay reachable — and it too is reported as a note, not an error.

**Costs:**

| | MWh | Rate | Cost |
|---|---:|---:|---:|
| Hour 1 — Cheap | 60 | $20 | $1,200 |
| Hour 2 — Cheap | 80 | $20 | $1,600 |
| Hour 2 — Dear | 20 | $40 | $800 |
| Hour 3 — Cheap | 50 | $20 | $1,000 |
| **Production cost** | | | **$4,600** |
| Ramp up, hour 2 (Cheap, 60→80) | 20 | $20 | $400 |
| Ramp down, hour 3 (Cheap, 80→50) | 30 | $20 | $600 |
| **Ramp cost** | | | **$1,000** |
| **Spill cost** | 50 | $1,000 | **$50,000** |
| **LP objective** | | | **$55,600** |

Note how far spill dominates: $50,000 of a $55,600 objective. That is the price
of `SPILL_COST` being large enough to matter, and it is the reason the constant is
flagged for revisiting.

**Prices:**

| Hour | Clearing price | Why |
|---|---:|---|
| 1 | **$0.00** | As in Scenario 1: extra fuel cancels against a smaller ramp. |
| 2 | **$1,060.00** | An extra MWh here costs $20 of fuel, $20 to ramp up, and then pushes `Cheap`'s hour-3 floor up by 1 MWh — $20 more fuel it cannot avoid burning, plus $1,000 to spill it. |
| 3 | **−$1,000.00** | The model's first negative price. An extra MWh of demand in hour 3 would absorb a MWh that is currently being destroyed, saving the full spill cost. |

The hour-3 price is the mirror image of a scarcity hour. Where scarcity prices at
LoL because the marginal unit is shed load, spill prices at `−SPILL_COST`
because the marginal unit is destroyed energy.

`Market Cost ($)` in hour 3 is `−$1,000 × 0 = $0`, but with any non-zero demand it
would be negative, and the totals block prints a note saying so.

---

## 9. What changed in the full run

Diffing the ramping run against the last ramp-free run over the same 744 hours:

| | Before | After | Change |
|---|---:|---:|---:|
| Production cost (fuel + VOM) | $10,708,480 | $10,976,211 | +2.50% |
| Ramp cost | — | $1,492,843 | new |
| **LP objective** | $10,708,480 | **$12,469,054** | **+16.4%** |
| Load-weighted price | $41.18 | $42.09 | +2.23% |
| Renewable curtailed | 65 MWh | 2,107 MWh | +3,143% |
| Plant 3 (Coal) generation | 73,617 MWh | 64,320 MWh | −12.6% |
| Plant 4 (Gas) generation | 213,197 MWh | 224,536 MWh | +5.3% |

Coal loses 9,300 MWh to gas. At 50 MW/hr on a 100 MW unit it is the slowest plant
in the fleet relative to its size and simply cannot follow demand, so the faster
600 MW gas plant picks up the difference despite costing nearly twice as much.

Renewable curtailment rises thirty-fold, from a rounding error to 1.2% of
available resource. Thermal plants that cannot ramp down fast enough hold their
output up, and wind is pushed out of the stack to make room. This is the
real-world effect ramping is meant to capture, and before this change the model
could not show it at all.

---

## 10. Known gaps

Recorded so they are not mistaken for decisions.

- **Renewables ramp for free.** Wind and solar have a ramp premium of zero, but
  only because their fuel price is zero, not because anyone decided renewables
  ramp for free. A solar farm being curtailed and un-curtailed is a large
  hour-to-hour swing at no charge. Their ramp *rates* are equally a placeholder,
  set to nameplate so that nothing binds.
- **`SPILL_COST` is a guess.** $1,000/MWh has the two properties it needs, but no
  more justification than that, and it dominates the objective whenever it fires.
- **The archive's KPIs do not know about ramping.** `run_archive` reports
  `production_cost`, which now excludes ramp cost, so a diff understates the true
  change in system cost (+2.5% rather than +16.4%). Adding ramp and spill KPIs
  needs the KPI-versioning question parked in
  [extra_plan.md](planning/extra_plan.md) to be settled first.
- **Ramping is symmetric.** One rate and one premium serve both directions.
- **No unit commitment.** Minimum generation, must-run, and start-up costs are
  ramping's natural neighbours and none of them exist. Start-up cost in
  particular is the more common way to express the cost of moving a plant.
- **plants file header.** `Ramp_efficiency($/hr)` holds efficiencies in
  MWh/MWhTh, not dollars per hour. The model locates the column by prefix, so
  renaming it to `Ramp_efficiency (MWh/MWhTh)` is safe and would be an improvement.
