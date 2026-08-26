# What does a spill hour price at?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
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
- How `describe_price_setter` (`MFDM.py:654`) names the setter when nothing is setting
  it.
