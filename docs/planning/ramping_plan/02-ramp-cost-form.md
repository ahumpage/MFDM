# How does ramping efficiency become a cost in the objective?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [Research: ramp cost and prices](00-research-ramp-cost-and-prices.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

The originating outline says the ramp cost is "based on the ramping efficiency for that
plant and fuel, **used instead of the efficiency at non ramping times**". That sentence
admits at least three formulations, and they are not equivalent — one of them is not
even a linear program.

**(a) Per-MWh-of-ramp adder.** The extra cost of a ramped MWh over a normal one:

```
ramp_cost(p) = fuel_price(p)/ramp_eff(p) - fuel_price(p)/eff(p)
```

charged on the ramp delta `V_up + V_dwn`. Linear, LP-safe, and it composes with the
existing objective, which already charges `marginal_cost * gen` on every MWh. Values on
current inputs: Coal $6.50/MWh, Gas (600 MW) $59.40/MWh, Gas (1000 MW) $132.00/MWh,
renewables $0.

**(b) Re-price the whole hour.** In an hour where a plant moves, *all* its output is
priced at `fuel_price/ramp_eff` rather than `fuel_price/eff`. This is the most literal
reading of "used instead of", but it is conditional on whether the plant ramped, which
needs a binary indicator. The model stops being an LP.

**(c) Per-ramp-hour charge.** A cost per hour spent ramping rather than per MWh moved,
which is what the discarded `Rampcost($/hr)` column would have expressed.

Settle:

- Which formulation the spec prescribes, and the exact objective term.
- Under (a), confirm the ramped MWh is charged **twice** — once at normal marginal
  cost through the existing `marginal_cost * gen` term, then again for the ramp
  premium. That is the intended reading of "extra cost over a normal MWh", but it
  should be stated rather than inferred.
- What happens for a plant with no fuel cost. Wind and solar get `ramp_cost = 0` under
  (a) automatically, because their fuel price is zero — not because anyone decided
  renewables ramp for free. Confirm that is the intent, or that the zero is doing work
  it should not.
- Whether the ramp premium belongs *inside* the plant's offer price, reordering the
  merit order, or *outside* it as a separate charge. This determines what the merit
  order even means and feeds
  [What the clearing price represents](04-clearing-price-meaning.md).
