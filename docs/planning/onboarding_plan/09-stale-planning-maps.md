# Stale planning maps: supersede, annotate, or close?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [Which document owns which fact?](01-doc-set-ownership.md)
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The Origin asks to *"replace fragile planning-document line-number references with stable
references to functions or named sections"*. That is real — **43 of 49 line references
under `docs/planning/` are wrong**, most by hundreds of lines, several pointing at code
that no longer exists.

But the audit found a worse problem underneath it, and this ticket is mostly about that
one: **two planning maps assert settled premises that are now known to be false, with no
forward pointer to what overturned them.**

### What the audit found

**Stale claims, which mislead more than a stale line number does:**

- `model_plan.md` settles *"Merit-order price stays canonical. The dual is a
  cross-check."* **Reversed.** `docs/ramping_semantics.md` makes the dual canonical and
  says so explicitly, naming `model_plan.md`. `model_plan.md` carries no correction, so a
  reader arriving there gets the opposite of the truth.
- `model_plan.md` settles *"Negative prices... Out of scope."* **Now false**, and again
  ramping_semantics says so directly.
- `model_plan.md` uses *"free spill"* to mean curtailment — the exact usage `CONTEXT.md`
  names and **retires**.
- `model_plan.md` refers to `Hours Setting Price`, renamed to `Hours Last in Stack`.
- `dashboard_plan.md` describes *"a 1643-line Dash app"*; it is now 1992 lines. It also
  says scarcity pricing and unserved energy *"do not exist in the model yet"*. They do.
- Both maps promise to add `### Dashboard` and `### Model semantics` headings to
  `AGENTS.md`. Neither heading exists; neither promised spec exists.
- `ramping_plan.md`'s Notes still describe `docs/agents/issue-tracker.md` as claiming
  GitHub — the ticket that fixed it is closed and the doc is correct now.

**The counter-example worth copying:** `ramping_plan.md` has an overturned premise of its
own (`spill[t]` priced at VOLL) and marks it inline, prominently, *"Overturned in part."*
That is the pattern the other two maps lack.

**Line references**, for completeness: 0 of 24 `MFDM.py` references are accurate; 0 of 19
`dashboard.py`; 4 of 6 `runstore.py` are accurate and 2 are near-misses. Several point at
deleted code — `check_feasibility` no longer exists at all, and the price-mismatch
counter was removed.

**Status of the efforts**: `ramping_plan` is closed and shipped. `model_plan` and
`dashboard_plan` both read *"Decisions so far: None yet."* — zero resolved tickets, and
their Destinations (`docs/model_semantics.md`, `docs/dashboard_spec.md`) do not exist.
`extra_plan` is neither a map nor a ticket folder; it is a flat file with two write-ups
and none of the mandated map sections, yet `issue-tracker.md` lists it as an effort.

### What has to be decided

- **What happens to `model_plan` and `dashboard_plan`.** Three options, and they are not
  the same as the line-number question: **close** them as superseded (their open tickets
  either died or belong to this map); **annotate** them with `Overturned` markers and
  forward pointers, keeping them as history; or **revive** them, which means someone
  intends to finish them. Closing is a scoping act — anything closed this way needs a
  line in the map's *Out of scope*, or graduating into a ticket here.
- **What the stable-reference convention is.** `file.py:function_name` is the obvious
  candidate and is what this map's own tickets use. Decide it, and decide whether it
  applies retroactively to all 49 references or only going forward.
- **Is fixing 43 stale references worth it at all**, if the documents containing them
  are about to be closed as superseded? The cheapest correct answer may be "close the
  maps, fix references only in what survives".
- **Does `extra_plan.md` become a map, a ticket, or absorbed?** Its two write-ups are the
  archive-rename issue (already resolved inline) and the KPI issue (now
  [03](03-kpi-semantics.md)/[06](06-kpi-single-source.md)/[07](07-manifest-compatibility.md)
  in this map). It may have nothing left in it.
- **Does `issue-tracker.md` need updating** to describe how a superseded effort is
  marked? It documents `open/claimed/resolved/dropped` for tickets but nothing for maps.

## Decision
