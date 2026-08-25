# The comparison view: what a delta looks like

- **Type**: `wayfinder:prototype` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Dashboard next iteration](../dashboard_plan.md)

## Question

Charting settled the direction: show the difference, not two overlaid absolutes. This
ticket makes it concrete enough to react to — a rough mock, not a change to
`dashboard.py`.

Where the comparison stands today, so the session does not rediscover it:

- **KPI cards are already deltas** — after value, "was" value, coloured percentage
  change, direction-aware (dashboard.py:1163-1197). These are probably fine.
- **`fig_compare_total` is the problem**: two absolute lines plus demand
  (dashboard.py:1294-1299), justified by a docstring saying stacks cannot be overlaid
  legibly (dashboard.py:1288). Three-plus series on one axis is the unreadability.
- **`fig_compare_price` already has a "B minus A" trace**, but on a secondary axis
  *alongside* both absolutes, and only when the two runs have equal length
  (dashboard.py:1323-1327).
- **`compare_plants_table` has a signed Change column** (dashboard.py:1342-1354).

Decide, by mocking:

- Is the difference the *only* thing shown, or is there a toggle back to absolutes?
  A toggle is more flexible and one more control on an already busy page.
- **Generation difference by plant or in total?** A stacked bar of per-plant deltas,
  positive above and negative below zero, says *why* the total moved — coal down,
  solar up — where a single total line only says *that* it moved. It is also the
  chart the docstring claims cannot be drawn legibly.
- What happens when the runs have different lengths, which currently just suppresses
  the difference trace.
- How zero reads. A delta chart is mostly a flat line at zero for two similar runs, and
  needs to make "nothing changed" obvious rather than looking broken.

Link the mock from this ticket as an asset.
