# What happens to the 22 manifests already written?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [What does "energy served" mean, and what divides the load-weighted price?](03-kpi-semantics.md)
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

`extra_plan.md` poses this as a three-way choice — backfill, version the field, or leave
them with a compatibility note — and treats it as the hard part of the scarcity fix.

**The audit makes it much cheaper than that.** Decide it on the real numbers.

### What the audit found

There are **22 manifests** under `run_archive/`. **None of them records non-zero unserved
energy.** The 12 newer runs carry an `Unserved Energy (MWh)` column that sums to exactly
`0`; the 10 older runs predate the column entirely. `energy_served_mwh` is identical
(`461279.447689`) across all 22, because `demand.csv` never changed.

So: **correcting `compute_kpis` would change no existing archived value.** Backfilling is
numerically a no-op. The only real work is a missing-column fallback for the 10 older
runs, and `compute_kpis` already establishes that pattern — it has defensive checks for
both `Hours Last in Stack` and `Curtailment (MWh)`.

Two further facts shape the choice:

- **No manifest carries any version field.** Top-level keys are exactly `id, created,
  label, notes, git, code, inputs, outputs, solver, kpis`. There is no `kpi_version` or
  `schema_version` anywhere.
- **The repo already has a convention for this**, stated in a comment at
  `runstore.compute_kpis`: the `hours_setting_price` key was deliberately *not* renamed
  when the column behind it was, so that old and new manifests still diff. The
  established practice is **frozen key names with reader-side fallbacks, and no version
  stamp**.

That convention is precisely what makes changing the *meaning* of `energy_served_mwh` in
place a live risk: with no version field, nothing can detect that two manifests using the
same key mean different things. It happens to be harmless here because every archived run
is fully served — but the map should say so rather than discover it later.

### What has to be decided

- **Which of the three options**, given that backfill is a no-op and the argument
  against it ("it edits history, and nothing else in `run_archive/` rewrites a manifest
  after creation") is now the only argument that carries weight.
- **Does a version field get introduced at all?** Adding `kpi_version` for a change that
  alters no value is machinery bought for a future change. Not adding it means the next
  KPI redefinition faces this question with no tooling and possibly with real data at
  stake. This is the actual decision; the rest follows from it.
- **Does the existing frozen-key convention survive**, or is this the moment it stops
  scaling?
- **Does `unserved_mwh` join the KPI set?** If so it also needs a `KPI_DISPLAY` entry in
  `runs.py` — `runstore.diff()` picks up new scalar keys automatically, but `runs.py`
  only *displays* what is listed. And older manifests will not have it, so the diff has
  to tolerate a key present on one side only.
- **Where the compatibility note lives**, if that option wins. `extra_plan.md` warns it
  will otherwise "be rediscovered as a bug" — which is exactly what happened once
  already.

## Decision
