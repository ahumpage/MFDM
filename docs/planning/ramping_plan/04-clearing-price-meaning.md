# What does the reported clearing price represent under ramping?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
- **Blocked by**: [Research: ramp cost and prices](00-research-ramp-cost-and-prices.md), [How ramping efficiency becomes a cost](02-ramp-cost-form.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

The load-bearing ticket of this map. Ramping makes the objective **intertemporal**, and
that breaks a premise [Map: Model semantics](../model_plan.md) explicitly settled:

> **Merit-order price stays canonical.** The dual is a cross-check, reported alongside.

Today the model reports two prices per hour and expects them to agree:

- **Merit order**: the marginal cost of the most expensive plant
  running, or VOLL in a scarce hour.
- **The dual**: the shadow price of the energy balance.

They agree because, with every hour independent, the cost of one more MWh in hour *t*
is exactly some plant's marginal cost. Ramping destroys that. Once moving a plant costs
money, an extra MWh in hour *t* also changes what it costs to serve *t−1* and *t+1*, so
the dual picks up ramp shadow costs from neighbouring hours and stops equalling any
plant's marginal cost.

The consequence is already written into the code as a comment that will become false.
`MFDM.py:435` counts the disagreements, and `MFDM.py:463` reports them as "expected in
degenerate hours where a plant sits exactly on its cap". Under ramping they would fire
in most hours, for an entirely different reason.

Settle:

- What price the model **claims** to report, and what it means. If the dual is the
  honest marginal cost of serving load, is it now canonical?
- Whether the merit-order column survives at all, and if so, what it is *for* — it
  would no longer be a price, but it might still be a useful "who was last in the
  stack" diagnostic under a different name.
- What replaces the mismatch counter. A cross-check between two things that are no
  longer supposed to be equal is not a check.
- Whether the price is still a *market* price the model can defend. `Market Cost ($)`
  and every downstream figure — load-weighted price, producer surplus
  — are computed from whichever column wins here.
- Explicitly: does this overturn the Model-semantics premise, or is that premise
  scoped to the ramp-free model and simply superseded?

## Decision

**The dual becomes canonical.** `Clearing Price ($/MWh)` is now the dual of the
energy balance: what one more MWh of demand in that hour would cost the system.
This is the honest marginal cost of serving load once the hours are coupled, and
it is what a price is for.

**The merit-order column survives, renamed and demoted.** It becomes
`Highest Running Cost ($/MWh)` — the name of what it actually measures, the
marginal cost of the most expensive plant generating. It is a "who was last in the
stack" diagnostic and is documented as not a price. It is still used by
`warn_merit_order_departures` and by `plant_summary.csv`, neither of which wants a price.

**The `Shadow Price` column is removed**, because it has become the clearing
price. Nothing is reported twice.

**The mismatch counter is deleted**, along with its "degenerate hours where a plant
sits exactly on its cap" explanation. A cross-check between two things that are no
longer supposed to be equal is not a check. Nothing replaces it as a *price* check;
what replaces it in the QA banner is a set of accounting identities that are still
true (energy balance closes, nobody exceeds availability or ramp rate, market cost
equals price times demand).

**The price is still defensible as a market price.** `Market Cost ($)`, the
load-weighted average price and producer surplus are all computed from the dual.
In the 744-hour run the price takes 17 distinct values with a maximum of
$160.40/MWh, which is Plant 4''s $41.60 marginal cost plus twice its $59.40
premium — the cost of moving it up and back down. No plant offers $160.40; the
system does. That is a real property of a co-optimised-across-time market, not an
artefact.

**Yes, this overturns the Model-semantics premise.** *"Merit-order price stays
canonical. The dual is a cross-check, reported alongside"* was correct for a model
where hours are independent. It was not scoped to survive intertemporal cost and
it does not. Recorded as superseded rather than wrong.

**Consequences settled here, not left to graduate:** `plant_summary.csv`''s
`Hours Setting Price` is renamed `Hours Last in Stack` and matched against
`Highest Running Cost` rather than the price. Under a dual it would otherwise have
read zero for every plant in almost every hour.
