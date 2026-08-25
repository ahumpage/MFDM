# Scarcity pricing: the shortfall price and the fate of check_feasibility

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [How do real markets price scarcity?](00-research-scarcity-pricing.md)
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

Charting settled that shortfall is priced rather than fatal. This ticket decides the
mechanics:

- What is the shortfall priced at, and where does the number come from — a real
  market cap, or an arbitrary round figure chosen to sit clearly above every plant?
- Is it a constant, or an input in `inputs/`? An input is honest but adds a file;
  a constant beside `TOL` (MFDM.py:83) is simpler to read.
- Does `check_feasibility` (MFDM.py:294) get deleted, or demoted to a warning? It
  currently gives a much clearer diagnostic than a solved-but-scarce result would.
  Deleting it trades an explicit error for a number you have to notice.
- Is unserved energy one variable per hour, or does it need to distinguish
  "no capacity exists" from "capacity exists but is unavailable"?

Note the knock-on: with a priced shortfall the model can no longer be infeasible on
the energy balance, so "Infeasible" from the solver would become a genuine bug rather
than a data problem.
