# How do real markets price scarcity?

- **Type**: `wayfinder:research` (AFK)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

What value do real electricity markets place on unserved energy, and how is it
expressed? Gather the primary-source facts that [Scarcity pricing](01-scarcity-pricing.md)
needs before it can pick a number:

- The market price cap / VOLL used in the NEM (AEMO), and how the administered
  price cap and cumulative price threshold interact with it.
- Whether the cap is expressed as a price ceiling on offers, an explicit VOLL on
  unserved energy in the dispatch objective, or both.
- One or two comparators (GB, ERCOT) for how differently it can be framed.
- Whether such models typically keep a pre-solve feasibility check alongside a
  priced-shortfall formulation, or drop it.

Findings go in `docs/research/scarcity-pricing.md`; link it from this ticket.
