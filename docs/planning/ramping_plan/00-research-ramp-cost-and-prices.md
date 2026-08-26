# How do production models price ramping, and what does a dual mean under ramp constraints?

- **Type**: `wayfinder:research` (AFK)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

Two facts that downstream decisions wait on. Neither is answerable from this
repository, so this is reading, not deliberation.

**1. How do established dispatch and unit-commitment formulations express the cost of
ramping?** The outline for this effort proposes a heat-rate penalty: a worse efficiency
applied when a plant moves. That is one option among several used in practice, and the
others carry different implications for whether the problem stays linear:

- A linear penalty on the ramp delta itself (`cost * |g(t) - g(t-1)|`, linearised via
  two non-negative variables), which is what the outline's `V_up` / `V_dwn` structure
  describes.
- Re-pricing a ramping unit's output at a degraded heat rate, which is conditional on
  *whether* the unit ramped and so is not linear without a binary.
- Start-up and shut-down costs as the more common proxy, with ramp *rate* limits kept
  as pure constraints and no ramp cost at all.

Report which are standard, where each is used (economic dispatch vs unit commitment),
and specifically whether "degraded efficiency while ramping" is a recognised
formulation or a conflation of ramping with part-load efficiency, which is a different
phenomenon.

**2. What does the energy-balance dual mean once intertemporal constraints link the
hours?** In the current model, the balance dual equals the marginal cost of the
marginal plant, and `MFDM.py` reports the two side by side as a cross-check. Ramping
couples adjacent hours, so the dual should absorb the ramp shadow cost of moving
neighbouring hours and stop matching any plant's marginal cost. Confirm that, and find
how the literature and real market operators describe the resulting price: whether it
is still called a marginal or clearing price, whether the divergence has a standard
name, and how markets that co-optimise across time report a price that no single
generator's offer explains.

## Findings

Capture to `docs/research/ramping.md`, matching the shape of the existing
`docs/research/scarcity_pricing.md`. Link it back here when done.
