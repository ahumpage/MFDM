# How do production models price ramping, and what does a dual mean under ramp constraints?

- **Type**: `wayfinder:research` (AFK)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
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

## Decision

Captured in [docs/research/ramping.md](../../research/ramping.md). Three findings
carried into the tickets that waited on this:

1. **Use a linear penalty on the ramp delta**, to keep the problem an LP. The
   `V_up` / `V_dwn` structure in the Origin outline is the standard linearisation.
   Re-pricing a ramping unit's whole output at a degraded heat rate is conditional
   on *whether* it ramped and needs a binary, so it is not available here.
2. **Degraded efficiency while ramping is an approximation**, and the price effect
   comes through the extra fuel burnt. It is charged as a premium per MWh moved,
   on top of the ordinary marginal cost.
3. **It is production cost that should be minimised**, not any one marginal cost.
   That is what lets the objective trade ramping against lost load and spill, and
   it is why the energy-balance dual becomes the honest price once the hours are
   coupled: the dual absorbs ramp shadow costs from neighbouring hours and stops
   equalling any plant's marginal cost.
