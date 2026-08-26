# What does `Ramp_time (hrs)` mean?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
- **Blocked by**: —
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

`inputs/plants.csv` carries `Ramp_time (hrs)`, and the ramp rate limit `R(p)` in MW/hr
has to be derived from it. The obvious reading — hours to go from zero to nameplate,
so `R = Capacity / Ramp_time` — produces limits that bind on nobody:

| Plant | Tech | Cap (MW) | `Ramp_time` | `Cap / Ramp_time` | Binds? |
|-------|------|---------:|------------:|------------------:|--------|
| Plant 1 | Solar | 500 | 0 | — | no |
| Plant 2 | Wind | 300 | 0 | — | no |
| Plant 3 | Coal | 100 | 0.5 | 200 | no |
| Plant 4 | Gas | 600 | 1 | 600 | no |
| Plant 5 | Gas | 1000 | 0.2 | 5000 | no |

Any `Ramp_time <= 1` gives a rate at or above nameplate, and a plant cannot move more
than nameplate in an hour regardless. Every plant in the file is at or below 1, so
under this reading the constraint is dead code by construction — it can never bind on
any input a person would plausibly write.

The physics agrees that something is off. A 1000 MW gas unit reaching full output in
12 minutes is not a real number, and coal — the slowest technology in the fleet —
comes out with the second-fastest ramp time.

The alternative reading is *fraction of nameplate per hour*, `R = Capacity *
Ramp_time`, giving Coal 50, Gas 600, Gas 200 MW/hr. That orders correctly by
technology, and it binds.

Settle:

- What the column means, and therefore the formula for `R(p)`.
- What `Ramp_time = 0` denotes — no limit, or instantaneous ramping. Both wind and
  solar carry it, and the two readings disagree about which end of the scale zero
  sits at.
- Whether the spec states `R(p)` symbolically and leaves the column's meaning as an
  input-data concern, or pins it down here.
- Whether the hard rate limit is worth having at all if no plausible input makes it
  bind. If the answer is that only the ramp *cost* ever shapes dispatch, the spec
  should say so plainly rather than describing a constraint that never fires.

## Decision

**Dissolved by the input data changing.** This ticket asked how to derive a MW/hr
ramp rate from a `Ramp_time (hrs)` column whose only plausible readings either
never bind or order the technologies wrongly.

`inputs/plants.csv` no longer has that column. It now carries `Ramp_rate (MW/hr)`
directly:

| Plant | Technology | Capacity | Ramp rate |
|-------|-----------|---------:|----------:|
| Plant 1 | Solar | 500 | 500 |
| Plant 2 | Wind | 300 | 300 |
| Plant 3 | Coal | 100 | 50 |
| Plant 4 | Gas | 600 | 200 |
| Plant 5 | Gas | 1000 | 400 |

There is nothing left to derive: `R(p)` is read straight from the column. The
values order correctly by technology, with coal the slowest relative to its size,
and they bind — coal loses 9,300 MWh of generation to the faster gas plant over
the 744-hour run precisely because it cannot follow demand.

The ticket's closing question — *"is the hard rate limit worth having at all if no
plausible input makes it bind?"* — is answered yes, on these numbers.

Wind and solar carry a ramp rate equal to their nameplate capacity, so they are
effectively unconstrained. That is a placeholder rather than a decision, and is
recorded as a known gap in the spec.
