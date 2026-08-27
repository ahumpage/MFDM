# The worked 3-hour, 2-plant example

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
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

## Decision

**Two scenarios, not one.** One fixture could not carry a binding rate limit, a
paid ramp *and* a spill hour without becoming unreadable, which the ticket
explicitly allowed for. Both are real input folders under
`docs/examples/ramping/` and both can be run:

```
python model/MFDM.py --inputs docs/examples/ramping/scenario_1_holding_back --results /tmp/s1
python model/MFDM.py --inputs docs/examples/ramping/scenario_2_spill        --results /tmp/s2
```

This required adding `--inputs` / `--results` to the model. Runs over custom
folders are never archived, so a fixture cannot disturb the real results.

**The fixture.** Two 100 MW plants, three hours, everything divides cleanly:

| Plant | Fuel price | Efficiency | Marginal cost | Ramp efficiency | Ramp premium |
|---|---:|---:|---:|---:|---:|
| Cheap | $12/MWhTh | 0.6 | $20/MWh | 0.3 | $20/MWh |
| Dear | $20/MWhTh | 0.5 | $40/MWh | 0.5 | $0/MWh |

**Scenario 1 — holding back.** `Dear` rate 50 MW/hr, demand 60/120/60.
Dispatch `Cheap` 60/70/60, `Dear` 0/50/0. Production $5,800, ramp $400,
objective $6,200. Prices $0 / $60 / $0.

**Scenario 2 — spill and a negative price.** `Dear` rate 20 MW/hr, demand
60/100/0. Dispatch `Cheap` 60/80/50, `Dear` 0/20/0, spill 50 MWh in hour 3.
Production $4,600, ramp $1,000, spill $50,000, objective $55,600.
Prices $0 / $1,060 / **-$1,000**.

All arithmetic in the spec was verified by running the fixtures, not asserted.

**Yes, the legitimate merit-order violation is shown, in both scenarios and for
both reasons.** Scenario 1 hour 2: `Cheap` generates 70 against a ceiling of 90
while `Dear` runs, because each extra MWh saves $20 of fuel but costs $20 to ramp
up and $20 to ramp back down. Scenario 2 hour 2: `Cheap` generates 80 against the
same ceiling of 90, this time to keep its hour-3 floor at 50 rather than 60 and so
spill 10 MWh less. The model prints its merit-order note in both, and continues.

**Yes, hour 1''s freedom is visible and is called out.** In Scenario 1 `Cheap`
moves 60 MWh in hour 1 for nothing, then pays $200 to move 10 MWh in hour 2. The
boundary condition is a number in a table rather than a sentence.

**An unplanned bonus worth keeping:** hours 1 and 3 of Scenario 1 both price at
**$0 while a plant is generating**. Under the old merit-order rule they would have
priced at $20/MWh. Zero is correct — an extra MWh there costs $20 of fuel but
shrinks the adjacent ramp by 1 MWh, saving $20 of premium, and the two cancel
exactly. It is the clearest available demonstration of why the dual had to become
canonical, and it is hand-checkable in one line.

Turning these into a test file remains out of scope, as the ticket states.
