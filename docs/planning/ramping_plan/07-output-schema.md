# Which output columns exist, and what does each one claim?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
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
(`MFDM.py:704`) must still reconcile to the LP objective, and that reconciliation is
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
- Whether a plant's `Production Cost ($)` (`MFDM.py:517`), currently
  `total * marginal_cost`, now needs its ramp cost added — and whether that number
  still ties out against the results file.

And for the totals block in `report()`:

- Where ramp cost and spill appear, and how the LP-objective reconciliation is stated
  now that it has four components (production, unserved, ramp, spill) rather than two.
