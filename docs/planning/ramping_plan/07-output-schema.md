# Which output columns exist, and what does each one claim?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
- **Blocked by**: [How ramping efficiency becomes a cost](02-ramp-cost-form.md), [Spill: system-wide or per-plant](03-spill-mechanism.md), [What the clearing price represents](04-clearing-price-meaning.md), [What a spill hour prices at](05-spill-hour-price.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

The output schema is in scope for this spec because a column is a claim about meaning,
not a formatting choice. Deciding that a `Ramp Cost ($)` column exists forces the
question of what number it holds.

The sharp one: does **`Ramp Cost ($)`** mean the ramp premium alone, or the total cost
of the ramped energy including the fuel underneath it? Two different numbers. Under the
adder formulation the premium is the marginal quantity, but a reader seeing "ramp cost"
will likely assume the total. Whichever is chosen, the totals block in `report()`
must still reconcile to the LP objective, and that reconciliation is
currently printed as a claim to the user.

Settle, for `dispatch_results.csv`:

- Ramp quantities. One `Ramp Up (MWh)` / `Ramp Down (MWh)` pair for the system, or per
  plant? Per plant is 2 × 5 new columns on a file that already has one generation and
  one availability column per plant.
- `Ramp Cost ($)` — premium or total, per the above.
- Spill quantity and cost columns, whose shape follows
  [Spill: system-wide or per-plant](03-spill-mechanism.md).
- Whether the existing `Production Cost ($)` column now includes ramp cost, or excludes
  it so the two are separable.

For `plant_summary.csv`:

- Which ramp totals a per-plant summary should carry, and whether `Ramping Efficiency`
  is worth surfacing alongside the existing `Marginal Cost ($/MWh)`.
- Whether a plant's `Production Cost ($)`, currently
  `total * marginal_cost`, now needs its ramp cost added — and whether that number
  still ties out against the results file.

And for the totals block in `report()`:

- Where ramp cost and spill appear, and how the LP-objective reconciliation is stated
  now that it has four components (production, unserved, ramp, spill) rather than two.

## Decision

### `dispatch_results.csv`

**Ramp quantities are system totals**, one `Ramp Up (MWh)` / `Ramp Down (MWh)`
pair, not per plant. The file already carries two columns per plant; adding two
more each would make it unreadable. Per-plant ramp lives in the summary, which is
five rows and can afford the width.

**`Ramp Cost ($)` is the premium alone**, not the total cost of the ramped energy.
The fuel and VOM underneath a ramped MWh are already in `Production Cost`, so
including them here would double count against the objective. The spec and the
column''s docstring both state this explicitly, because a reader will assume the
opposite.

**`Production Cost ($)` keeps its current meaning** — fuel and VOM only,
*excluding* ramp cost — so the four components of the objective stay separable and
the reconciliation is legible.

**Spill columns are `Spill (MWh)` and `Spill Cost ($)`**, one pair for the system,
following [03](03-spill-mechanism.md).

**Price columns:** `Clearing Price ($/MWh)` is the dual; `Shadow Price ($/MWh)` is
removed; `Highest Running Cost ($/MWh)` is added as the merit-order diagnostic.

**Ramp quantities are recomputed from the generation profile after solving**, not
read from the LP variables. `ramp_up` and `ramp_down` are defined by inequalities,
so a plant with a zero premium — both renewables today — can leave them anywhere
up to its rate limit without changing the objective. The variables exist only to
carry cost; the dispatch is the only honest source of quantities. This was found
during implementation and is a genuine trap.

### `plant_summary.csv`

New: `Ramp Rate (MW/hr)`, `Ramping Efficiency (MWh/MWhTh)`,
`Ramp Premium ($/MWh)`, `Total Ramp Up (MWh)`, `Total Ramp Down (MWh)`,
`Ramp Cost ($)`. Ramping efficiency **is** worth surfacing beside marginal cost:
it is the input that explains the premium, and the premium is otherwise a bare
number with no provenance.

**A plant''s `Production Cost ($)` stays `total * marginal_cost`**, without ramp
cost, matching the results file so the two still tie out. Ramp cost is its own
column for the same reason.

`Hours Setting Price` is renamed `Hours Last in Stack`, per
[04](04-clearing-price-meaning.md).

### The totals block in `report()`

All four components are printed and then summed:

```
LP objective = Production cost + Ramp cost + Unserved cost + Spill cost
```

**And the sum is checked against the value the solver actually minimised**, with a
warning printed on drift. The ticket noted that the reconciliation "is currently
printed as a claim to the user"; it is now a test that runs on every solve, which
is the only way it stays true as columns change.

### Knock-on breakage found and fixed

`run_archive/runstore.py` read `Hours Setting Price` directly and threw a
`KeyError` on the first ramping run, silently skipping the archive. It now reads
either column name and keeps the `hours_setting_price` KPI key unchanged, so runs
archived before and after the rename still diff against each other. Adding *new*
ramp and spill KPIs remains out of scope per the map, and is noted in the spec as
a known gap: the archive''s `production_cost` now understates the change in system
cost (+2.5% rather than +16.4%).
