# How does ramping efficiency become a cost in the objective?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
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

## Decision

**Formulation (a), the per-MWh-of-ramp adder.** The objective term is

```
sum over p, t of ramp_cost(p) * ( ramp_up[p][t] + ramp_down[p][t] )

ramp_cost(p) = fuel_price(p)/ramp_efficiency(p) - fuel_price(p)/efficiency(p)
```

Chosen because it is the only one of the three that stays a linear program, which
[the research ticket](00-research-ramp-cost-and-prices.md) settled as the
requirement. (b) needs a binary indicator; (c) prices the wrong thing.

**The ramped MWh is charged twice, and this is intended.** Once at the plant''s
ordinary marginal cost through the existing `marginal_cost * gen` term, then again
for the premium. The premium is defined as the *difference* between the two fuel
costs, so charging it alone would under-recover; charging the full ramped heat
rate instead of the ordinary one would require knowing which MWh were "the ramped
ones", which is formulation (b). Stated explicitly in the spec.

**VOM is excluded from the premium.** It is charged on every MWh either way,
through the marginal cost. Only the fuel burn differs while ramping.

**Renewables ramping for free is luck, not a decision.** Wind and solar get
`ramp_cost = 0` because their fuel price is zero, and the zero is doing work
nobody chose. Recorded as a known gap in the spec rather than fixed here: giving
renewables a real ramp cost needs a view on what it represents, which is new work.

**A guard was added.** `ramp_efficiency(p) <= efficiency(p)` is validated on load,
mirroring the existing efficiency guard. Without it a plant more efficient while
moving would have a negative premium and the solver would be paid to jiggle it.

**The premium sits outside the merit order, not inside the offer price.** It is a
separate charge on movement, not a modification to `marginal_cost`, because it is
charged per MWh *moved* rather than per MWh *generated* — a plant holding steady
at 90% output pays nothing. This is what makes the merit order stop predicting the
dispatch, and it feeds directly into
[04](04-clearing-price-meaning.md) and [06](06-merit-order-invariant.md).
