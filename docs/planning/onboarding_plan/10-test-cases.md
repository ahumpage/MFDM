# Which cases must the test suite prove?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [How does a test drive this model?](04-test-seam.md)
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The Origin lists six cases: normal merit-order dispatch, a plant at its capacity limit,
equal-cost plants, resource-limited solar or wind, scarcity and VOLL, and zero demand.
That list was written believing ramping and spill were unimplemented. **They are.** So
the list is incomplete, and the shape of a "hand-solvable case" has changed — hours are
no longer independent, so a case is a horizon, not an hour.

Decide the **case set**: what each case proves, and what makes the set sufficient to
trust a change.

### What the audit found

The Origin's six cases are all still valid, and each maps onto behaviour that exists:

| Case | What it would pin down |
|---|---|
| Merit-order dispatch | `marginal_cost = fuel/efficiency + vom`, cheapest first |
| Plant at capacity | the `cap_{plant}_{t}` constraint binds; price steps to the next plant |
| Equal-cost plants | degeneracy — the LP may split arbitrarily, so what is even assertable? |
| Resource-limited wind/solar | `build_profile_factors`, availability as a ceiling |
| Scarcity and VOLL | `unserved[t] > 0`, price pinned to VOLL, `name_last_in_stack` |
| Zero demand | price with nothing running; `Highest Running Cost` falls back to `0.0` |

**What the Origin could not know to ask for**, because it thought ramping was future work:

- **A ramp-rate limit binding** — a plant that cannot rise fast enough, forcing a more
  expensive plant on.
- **A ramp premium changing the dispatch order** — a cheap plant holding back because
  moving costs more than the saving. `docs/ramping_semantics.md` already contains this as
  a worked 3-hour example: `docs/examples/ramping/scenario_1_holding_back/`.
- **A spill hour** — `spill[t] > 0` at `SPILL_COST`, and the **negative price** that
  falls out of the dual. Also already a worked example:
  `docs/examples/ramping/scenario_2_spill/`.
- **The `forced_down` allowance** — a wind or solar profile falling faster than the ramp
  rate. The code comment records a measured consequence of removing it: the objective
  goes from `$4,400` to `$2,415,010` with 58% of demand unserved. That is a
  catastrophic, silent failure mode and arguably the single most valuable regression test
  in the repo.
- **The invariants that already run on every solve** — the objective reconciliation
  (four cost columns summing to `pulp.value(prob.objective)`) and the energy-balance
  check (`gen + unserved - spill == demand`). These are checks the model already
  performs and prints; making them assertions is nearly free.

### What has to be decided

- **The case list**, including how many of the above join the six.
- **What "hand-solvable" means now.** With ramping, the smallest interesting case is
  2 plants x 3 hours, which is what `model_plan.md` already settled on and what the two
  worked examples are. Confirm that shape.
- **Do the two existing worked examples become tests?** They have hand-verified expected
  numbers written out in `ramping_semantics.md`. Reusing them means the document and the
  suite cannot drift; duplicating them means they will.
- **What is asserted for equal-cost plants.** The LP may split output arbitrarily between
  them, so total generation and total cost are assertable but per-plant output is not.
  Decide the assertion, or drop the case.
- **Are the QA checks tested, or are they the tests?** `warn_merit_order_departures` explicitly
  gave up its authority under ramping — its own docstring says it *"no longer proves a
  bug"*. So it is a warning that a test cannot assert on as a correctness gate. Decide
  what, if anything, replaces it.
- **What the suite is for.** "Confirm a safe change" is the Origin's phrase. Whether that
  means regression protection, executable documentation of the model's reasoning, or
  both, changes what a good case looks like.

## Decision
