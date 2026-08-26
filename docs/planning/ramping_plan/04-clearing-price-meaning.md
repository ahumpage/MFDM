# What does the reported clearing price represent under ramping?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [Research: ramp cost and prices](00-research-ramp-cost-and-prices.md), [How ramping efficiency becomes a cost](02-ramp-cost-form.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

The load-bearing ticket of this map. Ramping makes the objective **intertemporal**, and
that breaks a premise [Map: Model semantics](../model_plan.md) explicitly settled:

> **Merit-order price stays canonical.** The dual is a cross-check, reported alongside.

Today the model reports two prices per hour and expects them to agree:

- **Merit order** (`MFDM.py:415`): the marginal cost of the most expensive plant
  running, or VOLL in a scarce hour.
- **The dual** (`MFDM.py:429`): the shadow price of the energy balance.

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
  (`MFDM.py:457`) and every downstream figure — load-weighted price, producer surplus
  — are computed from whichever column wins here.
- Explicitly: does this overturn the Model-semantics premise, or is that premise
  scoped to the ramp-free model and simply superseded?
