## Other
What is an MCP and figure it out / apply it
Make a checklist for future builds?

## Run archive: renaming a run folder breaks it

Deferred from the dashboard map. Not a dashboard problem — it lives in `run_archive/`.

**Symptom**: renaming an archive folder makes that run unusable.

**Cause**: the run id is stored twice — as the folder name, and as `"id"` inside
`manifest.json` (runstore.py:258). `resolve()` reads candidate ids out of the
manifests (runstore.py:319), then `get_manifest()` path-joins that string back onto
`run_archive/` (runstore.py:302). Rename the folder and the two disagree, so the run
still appears in `runs.py list` but every read of it raises `FileNotFoundError`.

**Already broken**: `run_archive/doublesolar` and `run_archive/standard` carry the
manifest ids `20260824T154357` and `20260824T154258`. They list, but `show`, `diff`,
`restore`, `prune` and the dashboard's run dropdown all fail on them.

**The decision to make**: which is canonical?

- *Folder name canonical* — `list_runs` derives the id from the directory name and
  ignores `manifest["id"]`. Renaming becomes free, and the two broken folders heal
  themselves. Costs: the manifest is no longer self-describing if copied elsewhere.
- *Manifest canonical* — add a `runs.py rename` command that moves the folder and
  rewrites the manifest together. Renaming by hand stays broken, but the manifest
  remains the single source of truth.

Plus a one-off chore either way: repair the two folders already desynchronised.

**Resolved.** Folder name is canonical: `list_runs` now stamps the id from the
directory it read the manifest from (runstore.py:281), so every id handed out can be
found again on disk. `doublesolar` and `standard` have been repaired and work.

## KPIs count unserved energy as served

Deferred while building the comparison view. Not urgent: no run in the archive has any
unserved energy, so nothing on disk is wrong *yet*. It becomes wrong the first time a
scarce run is archived.

**Symptom**: a run with unserved energy reports more energy served than it served, and
a load-weighted price divided by the wrong denominator.

**Cause**: `energy_served_mwh` is set to total demand, ignoring the shortfall. Since
scarcity pricing landed, demand and energy served are no longer the same number —
`model/MFDM.py` was fixed to `demand - unserved`, but two other places were not:

- `runstore.compute_kpis` (runstore.py:161,176), baked into every manifest at archive
  time, and read by `runs.py list`, `runs.py diff` and the dashboard's attribution.
- `dashboard.window_kpis` (dashboard.py:1180), recomputed per visible window, and the
  source for the comparison tab's delta cards.

`load_weighted_price` (`market / demand`) inherits the same denominator in both.

**The decision to make**: what happens to manifests already written. They record the
old definition, so a corrected dashboard would disagree with an archived manifest
describing the same run.

- *Backfill* — rewrite `kpis` in existing manifests. Makes everything agree, but edits
  history, and nothing else in `run_archive/` ever rewrites a manifest after creation.
- *Leave them, version the field* — add `kpi_version` and have readers interpret old
  manifests by the old rule. Honest, more machinery.
- *Leave them, accept the seam* — cheapest, on the grounds that no archived run is
  actually affected. Needs a note somewhere, or it will be rediscovered as a bug.

Worth adding `unserved_mwh` to the KPI set at the same time, and a delta card for it,
so a scarce run is visible in a comparison rather than silent.
