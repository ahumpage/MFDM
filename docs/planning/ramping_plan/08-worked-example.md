# The worked 3-hour, 2-plant example

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [What `Ramp_time (hrs)` means](01-ramp-time-meaning.md), [How ramping efficiency becomes a cost](02-ramp-cost-form.md), [What the clearing price represents](04-clearing-price-meaning.md), [What a spill hour prices at](05-spill-hour-price.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

[Map: Model semantics](../model_plan.md) settled the shape — "hand-solvable 2-plant /
3-hour LPs with arithmetic you can do on paper" — and promised the spec would carry
"worked numbers for the awkward hours". It never delivered them, and the repo has no
tests at all.

Ramping is the first intertemporal feature in this model, which makes a worked example
more valuable here than anywhere it has been proposed before. Hour-by-hour reasoning is
exactly what stops being obvious once hours are coupled, and for an onboarding repo the
worked example is likely the most useful page in the spec.

This ticket specifies the example. It does **not** write tests; turning it into a test
file is implementation and is out of scope for this map.

Settle:

- The fixture: 2 plants, 3 hours, numbers that divide cleanly. It must exercise a
  binding ramp rate limit, a paid ramp, and a spill hour — ideally in one scenario, or
  in two if one cannot carry all three without becoming unreadable.
- The full arithmetic: dispatch per plant per hour, ramp deltas, ramp cost, spill,
  objective value, and the clearing price in each hour under whichever definition
  [What the clearing price represents](04-clearing-price-meaning.md) settles.
- Whether the example also shows a case where the merit order is *legitimately*
  violated — a cheap plant holding back to dodge a ramp charge — since that is the
  single most counter-intuitive consequence of this feature and the justification for
  [What replaces the merit-order invariant](06-merit-order-invariant.md).
- Whether hour 1's freedom from ramp constraints is visible in the example, so the
  boundary condition is concrete rather than a sentence.
