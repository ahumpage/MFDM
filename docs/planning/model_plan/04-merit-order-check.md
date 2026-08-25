# What does "plants dispatch in merit order" actually assert?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

"Plants should dispatch in merit order" is intuitive but not directly checkable,
because a cheap plant can legitimately sit idle while an expensive one runs. Two
reasons in this model:

- A profiled wind or solar plant is capped by its hourly resource, far below
  nameplate (MFDM.py:197). It is not "skipped"; it is exhausted.
- Ties. Two plants on identical marginal cost can split output arbitrarily and the
  solver's choice between them is not meaningful.

Decide the precise invariant. The usual formulation is: *no plant generating strictly
below its availability while a strictly more expensive plant generates anything* —
i.e. no cheap headroom left unused above a running expensive plant. Confirm that, or
choose another, and settle:

- The tie tolerance: how close in marginal cost before two plants count as equal?
- Does the check operate per hour, or on totals? Per hour is stricter and correct;
  totals would pass a dispatch that is wrong in every individual hour.
- Once shortfall exists ([Scarcity pricing](01-scarcity-pricing.md)), unserved energy
  is the most expensive thing in the stack. Does it participate in this check?
