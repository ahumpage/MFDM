# What replaces the merit-order invariant?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [What `Ramp_time (hrs)` means](01-ramp-time-meaning.md), [How ramping efficiency becomes a cost](02-ramp-cost-form.md), [What the clearing price represents](04-clearing-price-meaning.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

`check_merit_order` (`MFDM.py:555`) currently **raises** on violation, and `main`
treats that as fatal (`MFDM.py:826`). Its invariant: no plant may generate strictly
below its dispatch ceiling while something strictly more expensive is generating.

`dispatch_ceiling` (`MFDM.py:527`) was written in advance for this moment. Its
docstring names the replacement — `np.minimum(par["avail"], previous_output +
ramp_up_rate)` — and already warns that a ramp-*down* limit is different in kind,
because it puts a floor under a plant rather than a ceiling over it, and a floor can
make a genuinely optimal dispatch look like a violation.

A ramp *cost* breaks it wider than the docstring anticipated. A cheap plant may now sit
below its ceiling under a dearer plant purely to avoid a ramp charge it would pay back
next hour, and that is optimal. Under the current check, every such hour is a fatal
error.

It has been agreed the check demotes from **error to warning**. This ticket settles
what the warning actually asserts.

Settle:

- The ceiling formula, and whether the check gains a matching **floor** term
  (`max(0, previous_output - ramp_rate)`) so a plant pinned above demand is not
  reported as underused.
- Whether any invariant survives that is strong enough to still be worth raising on.
  A warning nobody can act on is noise; if the honest answer is that no cheap check
  can distinguish a bug from a paid ramp, the spec should say so.
- Whether the diagnostic's "cost of the violation" figure (`MFDM.py:613`) still means
  anything, since some of that cost is now legitimately spent avoiding ramp charges.
- What the run does on warning. Today a failure still writes the CSVs first
  (`MFDM.py:822`) so the dispatch can be inspected, and blocks archiving so a known-bad
  run never enters the archive. If it is only a warning, does the run still archive?
- Record **why** a correctness gate was given up. This is the question a future reader
  will ask, and it is the reason this is a ticket rather than a premise.
