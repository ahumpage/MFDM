# What does a spill hour price at?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
- **Blocked by**: [Spill: system-wide or per-plant](03-spill-mechanism.md), [What the clearing price represents](04-clearing-price-meaning.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

A spill hour is the mirror of a scarcity hour, and the existing price machinery has no
answer for it.

In a scarcity hour the marginal MWh is *shed*, so lost load is the marginal unit and
the price is VOLL — `MFDM.py:423` sets this explicitly, and the dual agrees. In a spill
hour the marginal MWh is being **destroyed at a cost of VOLL**, so one more MWh of
demand would *save* VOLL. The dual should be `-VOLL`. Merit order has no answer at all:
every running plant is inframarginal, and nothing in the stack is setting anything.

This would be the model's first negative price. [Map: Model
semantics](../model_plan.md) ruled negative prices out of scope on the grounds that
they needed "model features that do not exist yet" — ramping is that feature arriving.

Settle:

- The reported price in a spill hour: `-VOLL`, zero, the most expensive running plant,
  or something else.
- Whether `SPILL_COST` stays pinned to VOLL. Setting them equal makes shedding and
  dumping exactly equally bad at the margin, and lets one stuck hour dominate the
  objective at roughly $8,300/MWh. A separate, smaller constant would keep spill firmly
  last in the merit order while leaving the run's total cost readable.
- What an hour with **both** unserved energy and spill prices at. Possible across a
  fleet with mixed ramp constraints, and the dual there has no unique value.
- What `Market Cost ($)` means when the price is negative — the model would be
  reporting that consumers were paid to take power.
- How `name_last_in_stack` names the setter when nothing is setting
  it.

## Decision

**A spill hour prices at `-SPILL_COST`,** and this falls out of the dual with no
special case at all. Because [04](04-clearing-price-meaning.md) made the dual
canonical, no code is needed: one more MWh of demand in a spill hour absorbs a MWh
that is currently being destroyed, so the dual is negative by construction. The
model''s first negative price, and it is arrived at rather than asserted.

**`SPILL_COST` does NOT stay pinned to VOLL. It is $1,000/MWh.** This ticket
anticipated the question as a matter of readability; it turned out to be a
correctness problem, and the map''s recorded caveat understated it.

Spill and unserved energy are not symmetric at the margin:

- Shedding a MWh **removes** a MWh of generation, saving `VOLL - marginal_cost`.
- Dumping a MWh **requires** a MWh of extra generation, costing `SPILL_COST + marginal_cost`.

With the two constants equal, shedding is cheaper by twice the marginal cost
wherever they are substitutable — and they are, because spill in one hour is
caused by generation in the hour before, which unserved energy in that earlier
hour relieves. So spill would be **strictly dominated** and would never occur: the
variable introduced to keep the model feasible under ramp-down floors would never
leave zero.

Measured on the Scenario 2 fixture (demand 60/100/0, a plant that cannot shed fast
enough):

| Spill price | What the model does | Objective |
|---|---|---:|
| VOLL ($8,300) | sheds 50 MWh of peak demand, spills nothing | $418,800 |
| VOLL, spill forced | dumps 50 MWh | $420,600 |
| $1,000 | serves all demand, dumps 50 MWh | $55,600 |

At VOLL the model blacks out half of peak demand rather than dump a surplus later.

$1,000/MWh is chosen for two properties: far above the most expensive plant''s
marginal cost ($76/MWh) so spill stays last in the stack, and far below VOLL so
dumping is always preferred to shedding real load. It is a modelling constant, not
a physical quantity, and the spec flags it for revisiting.

**An hour with both unserved energy and spill** is not specially handled. The dual
has no unique value there and the LP picks one; since both are priced and both
appear in their own columns, the quantities are reported honestly whatever the
price does. Not observed in any run to date.

**`Market Cost ($)` goes negative** in a spill hour with non-zero demand, meaning
consumers were paid to take power. `report()` prints an explicit note whenever any
hour has a negative price, so the figure is never met without warning.

**`name_last_in_stack` gains a `-SPILL_COST` case** naming "spilled energy". It
is only used for the *diagnostic* column now, never for the clearing price, so its
ordinary behaviour is unaffected.
