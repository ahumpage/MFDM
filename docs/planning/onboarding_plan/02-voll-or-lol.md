# VOLL or LoL?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

There is an **uncommitted rename in the working tree**: the constant `VOLL` has become
`LoL` throughout `model/MFDM.py`, and a matching comment change sits in
`dashboard/dashboard.py`. The rename reaches **user-facing output** — the strings printed
when a price is set by scarcity read `(LoL)`.

`CONTEXT.md` defines only **VOLL**, at `$8,300/MWh`, and it is one of the most-cited
entries in the glossary. The moment this rename is committed, the repo uses two names for
one constant and the glossary is stale on it.

Pick one name, and say what happens to the other.

### Why this is small and urgent

Small: it is one term. Urgent: it is uncommitted, so every session working on this map
risks either committing it silently or reverting it by accident, and every document
ticket downstream has to write *some* name. Resolving it early stops the ambiguity
propagating into the new documents that [Which document owns which
fact?](01-doc-set-ownership.md) will commission.

### What has to be decided

- **Which name.** `VOLL` (value of lost load) is the standard term in power-system
  literature and is what `docs/research/scarcity_pricing.md` and the European Commission
  JRC source use. `LoL` normally abbreviates *loss of load*, which is a different
  quantity — a probability or an expectation, not a price. If the rename was motivated by
  something specific, that reason needs stating; on its face it looks like it trades a
  standard term for one that collides with another concept.
- **Whether the code identifier and the documented term must match.** They could
  legitimately differ if there is a reason, but `CONTEXT.md`'s whole purpose is
  collision-resolution, so a split would need an explicit entry.
- **Scope of the change.** Code identifier, printed strings, `CONTEXT.md`, `README.md`
  (where the symbol appears in the objective but is never defined), and
  `docs/ramping_semantics.md` — which discusses `SPILL_COST != VOLL` as the single most
  load-bearing modelling decision in the ramping work.
- **What to do with the working-tree diff right now**: commit it, revert it, or amend it.

## Decision
