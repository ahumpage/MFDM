# Spill: system-wide or per-plant, and is it "spill" or "curtailment"?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
- **Blocked by**: —
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

That spill exists and is priced at VOLL is settled on the map. Two questions about its
shape are not, and they are entangled enough to answer together.

**1. One variable per hour, or one per plant?**

A single system-wide `spill[t]` says only that the fleet over-generated. A per-plant
`spill[p][t]` attributes the surplus, so the results can say *which* plant was stuck
above demand — but the attribution is arbitrary whenever more than one plant is
pinned by its ramp-down floor, because the LP can split the surplus between them any
way it likes at equal cost. Reporting an arbitrary split as if it were a finding is
worse than reporting no split at all.

**2. The vocabulary collision.**

`MFDM.py` already reports a **Curtailment** column, defined as profiled renewable
energy that was available but not taken (`MFDM.py:441`, `MFDM.py:491`). It is free,
implicit, and applies only to wind and solar. [Map: Model semantics](../model_plan.md)
also settled the premise "curtailment stays free and implicit" and used the phrase
"free spill" for the same idea.

Ramping now introduces a second concept — energy that was *generated* and had to be
thrown away because a plant could not ramp down — which is priced, explicit, and
applies to thermal plants. Two different things, overlapping names, one of which the
codebase already uses for the other meaning.

Settle:

- Whether spill is system-wide or per-plant.
- The canonical term for each concept, and whether the existing Curtailment column
  keeps its name. Write both into `CONTEXT.md`, which does not exist yet, so this
  ticket likely creates it.
- Whether the two are really distinct, or whether unused renewable resource and dumped
  thermal energy should be unified under one concept with different prices.
- What the sign convention is in the energy balance. The map has
  `sum(gen) + unserved - spill == demand`, so spill enters negatively; confirm that
  reads more clearly than moving it to the other side.

## Decision

**1. Spill is system-wide: one `spill[t]` per hour, not per plant.** The
attribution a per-plant variable would offer is arbitrary whenever more than one
plant is pinned by its ramp-down floor, and the ticket''s own argument stands —
reporting an arbitrary split as if it were a finding is worse than reporting no
split at all.

**2. Both terms are kept, and they mean different things.** Written into
[CONTEXT.md](../../../CONTEXT.md), which this ticket created.

| | Curtailment | Spill |
|---|---|---|
| What it is | Renewable resource available but not taken | Energy generated and then destroyed |
| Which plants | Wind and solar only | Any plant, in practice thermal |
| Price | Free | `SPILL_COST` |
| In the LP | Implicit, just `avail - gen` | An explicit decision variable |

**The existing Curtailment column keeps its name.** It is correct for what it
measures, it is already in archived runs, and renaming it would break the
comparison view for no gain.

**They are not unified.** Energy never produced and energy produced-then-destroyed
are different physical events with different costs, and collapsing them would make
the Curtailment column mean "sometimes free, sometimes $1,000/MWh" depending on
which plant it came from.

**"Free spill", used in [Map: Model semantics](../model_plan.md) for what is here
called curtailment, is retired.** CONTEXT.md records this explicitly so the older
document does not mislead.

**3. Sign convention confirmed:** `sum(gen) + unserved - spill == demand`. Spill
enters negatively because it is generation that did not serve demand, which reads
as the direct mirror of `unserved` on the same side of the equation.
