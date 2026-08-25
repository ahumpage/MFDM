# What is the price in an hour where nothing is dispatched?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

The QA list asks that a zero-demand test returns a zero shadow price in every hour.
That holds for the *merit-order* price, which falls back to `0.0` when nothing is
running (MFDM.py:389). It does not hold for the *dual*: the shadow price of the energy
balance at zero demand is the cost of serving one more MWh, which is the cheapest
available plant's marginal cost, not zero.

As written the check asserts something false about the `Shadow Price ($/MWh)` column.
Decide what a no-dispatch hour should report:

- Is zero a *price* here, or an absence of one? A blank is honest; a zero is a number
  the dashboard will happily average into a misleading mean.
- If the two columns legitimately disagree at zero demand, does that hour get exempted
  from the check in [When may the shadow price differ?](02-degenerate-price-tolerance.md),
  or is it a separate rule?
- `check_demand` (MFDM.py:280) already warns that zero demand is usually a data-entry
  slip. Is a zero-demand hour a *scenario the model supports*, or an input error the
  QA pass should reject outright? Those lead to different checks.
