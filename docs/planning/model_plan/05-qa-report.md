# The QA pass: what it checks, where it goes, and whether it can fail a run

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [Scarcity pricing](01-scarcity-pricing.md), [Shadow price divergence](02-degenerate-price-tolerance.md), [Zero-demand price](03-zero-demand-price.md), [Merit order check](04-merit-order-check.md)
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

The invariants are decided by the blocking tickets. This one decides the QA pass as an
artifact. Today the checking is scattered and ephemeral: `warn_nonpositive_demand`
and `check_feasibility` run before the solve, the price-mismatch note
sits inside `build_hourly_results`, and the energy balance check is a print
statement at the end of `report`. All of it goes to stdout and is lost
the moment the terminal scrolls.

Decide:

- **Where the result lands.** Stdout only, a `results/qa_report.txt`, or into the run
  manifest so `run_archive/runs.py diff` can compare QA between runs.
- **Severity.** Is a failed check fatal, or a warning on an otherwise-written result?
  The current code splits both ways — zero demand warns, infeasibility raises — with
  no stated principle. State one.
- **Structure.** One check function per invariant returning a pass/fail, or the
  current scattered prints tidied in place? This is a learning repo; the readable
  answer wins over the clever one.
- **What the report says about a run that is fine.** Silence, or a positive
  confirmation that all checks passed? The original brief wanted QA output that shows
  "what has already been implemented", which argues for the latter.

The stress-test checks ("high demand gives a very high shadow price", "zero demand
gives no price") are *scenarios*, not invariants of a normal run — they belong to
[Test fixtures](06-test-fixtures.md). Keep the boundary explicit: which checks run on
every real run, and which only under test.
