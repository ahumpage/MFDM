# Map: Model semantics

`wayfinder:map` — the map for this effort. Tickets are the files in `model_plan/`.

## Destination

A written spec, `docs/model_semantics.md`, stating what MFDM is supposed to *mean*:
what happens when demand cannot be met, what the objective and the reported prices
represent, and what invariants a QA pass asserts on every run. Alice implements the
model changes afterwards, fitting the code to the spec; this map produces no code.

## Notes

- **Domain**: least-cost economic dispatch LP (PuLP), `model/MFDM.py`. Onboarding
  training repo, so readability beats cleverness in anything the spec prescribes.
- **Plan only.** Every ticket resolves a decision. No prototypes, no implementation,
  not even throwaway code. The pull to start writing tests means the map is done.
- **Audience**: Alice reads and implements. The spec is decisions + rationale +
  worked numbers for the awkward hours, not agent-ready acceptance criteria.
- **Skills every session should call**: `grilling` and `domain-modeling`. Write terms
  into `CONTEXT.md` as they resolve. ADRs only where a decision is hard to reverse.
- **On close**: assemble `docs/model_semantics.md` and add a one-line pointer to it
  in `AGENTS.md` under `### Model semantics`.

### Settled while charting

Premises, not steps on the route. Recorded so no ticket reopens them by accident.

- **Scarcity does not abort the solve.** Shortfall becomes priced energy at a value
  far above any plant's marginal cost, so the model always solves and scarcity
  surfaces as a price. The value itself is [Scarcity pricing](model_plan/01-scarcity-pricing.md).
- **Offer price = short-run marginal cost.** `fuel/efficiency + VOM`, as built. This
  is a stated modelling assumption, not a placeholder to be revisited here.
- **Merit-order price stays canonical.** The dual is a cross-check, reported
  alongside. Keep the current behaviour (MFDM.py:387-403).
- **Curtailment stays free and implicit.** `gen <= avail` as today.
- **Test shape: hand-solvable 2-plant / 3-hour LPs** with arithmetic you can do on
  paper, not golden-file regression against `run_archive/`.

## Decisions so far

<!-- one line per closed ticket -->

_None yet._

## Not yet specified

In scope, not yet sharp enough to ticket.

- How a scarcity hour renders in the two price columns and in `plant_summary.csv`'s
  "Hours Setting Price" — unserved energy is not a plant, so the existing
  price-setter attribution has nothing to point at. Graduates once
  [Scarcity pricing](model_plan/01-scarcity-pricing.md) lands.
- Whether the QA output needs a machine-readable form for `dashboard/dashboard.py`
  to surface, or whether human-readable text is enough.
- Whether `run_archive/` snapshots have any role in QA (e.g. flagging that results
  moved versus the last run) or stay purely an archive.

## Out of scope

Past the destination. Returns only as a fresh effort.

- **Explicit or penalised curtailment.** A later addition; free spill is the premise
  for this spec.
- **Negative prices, min-gen and must-run.** The mirror case of scarcity. Needs model
  features that do not exist yet, so there is no ambiguity here to resolve — it is
  new work, not a decision.
- **Deep structural read of `model/MFDM.py`.** Alice's own review, done personally to
  understand AI-written code. Not agent work. Structural findings that *block* a
  semantics decision come back as tickets.
- **Implementing the spec.** Fitted to the spec after this map closes.
