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
