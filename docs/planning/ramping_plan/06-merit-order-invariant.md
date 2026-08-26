# What replaces the merit-order invariant?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
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

## Decision

**Demoted from error to warning, as agreed.** `check_merit_order` prints a note and
returns; the run continues, reports, and archives normally.

**The ceiling gains a ramp term and the check gains a matching floor:**

```
ceiling[p][t] = min( avail[p][t],  gen[p][t-1] + ramp_rate(p) )
floor[p][t]   = max( 0,  gen[p][t-1] - ramp_rate(p) - forced_down[p][t] )
```

Hour 1 falls back to availability and zero. A plant sitting on its floor is
excluded from the report entirely — a plant pinned above demand by its own
ramp-down limit is not leaving headroom unused in any meaningful sense, and
including it would be both wrong and extremely noisy.

**No invariant survives that is worth raising on.** This is the honest answer the
ticket asked for. Ramping breaks the old one in two ways, both optimal:

1. A ramp *cost* means a cheap plant may hold back beneath a dearer one, because
   moving up and back down costs more premium than the fuel it saves.
2. A ramp *down* floor means a cheap plant may run low now to stay able to reach a
   low demand later without spilling.

Neither can be distinguished from a genuine bug without re-solving the LP, which a
post-hoc check cannot do. Both occur in the worked examples and 197 plant-hours of
the 744-hour run are flagged. So the check keeps its arithmetic and drops its
authority.

**The "cost of the violation" figure is retained but relabelled** to *"cheap
headroom left unused is worth at most $X"*. It is an upper bound on any waste
rather than a bill, because some of that headroom is legitimately forgone.

**The run still archives on a warning.** The old behaviour — write the CSVs, then
block archiving — existed so a known-bad run never entered the archive. A warning
is not a known-bad run, and refusing to archive 195 hours of correct results would
make the archive useless exactly when ramping is being studied.

**Why a correctness gate was given up.** Recorded at length in the
`check_merit_order` docstring as well as here, because it is the question a future
reader will ask. In short: the invariant was never about merit order as such, it
was a proxy for "the LP found the cheapest dispatch". That proxy was exact while
hours were independent and is simply false once they are coupled. Keeping it would
mean a fatal error on every correct run, which trains the reader to ignore it —
strictly worse than a note that says "worth a look".

**What replaces it as a gate:** the objective reconciliation in `report()`, which
now checks the four reported cost components against the value the solver actually
minimised and warns on drift. That is a real invariant, it is cheap, and it catches
the class of bug (a cost double counted or dropped from a column) that this effort
was most likely to introduce.
