Start reading in model/MFDM.py, this is the main model which the repo is based around.
The purpose of the repo is to build a power dispatch model from the ground up, adding in
complications and adjusting, as part of onboarding training.
The model should be built using PuLP.
The code should be readable and easy to follow, so that it can be used as a learning tool.

Layout and run order
    inputs/                 plants.csv, fuel.csv, demand.csv, profiles.csv
    model/MFDM.py           the dispatch model, reads inputs/ and writes results/
    results/                dispatch_results.csv, plant_summary.csv
    dashboard/dashboard.py  Dash app for presenting and QA-ing results

Run model/MFDM.py first, then dashboard/dashboard.py, which reads the CSVs in results/.

Runs that are not the most up to date are archived by run_archive/runstore.py into a
timestamped folder under run_archive/, each with a manifest.json recording the git commit
and input hashes. The archive is kept in the repo so past runs stay usable on this machine.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `ahumpage/MFDM`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
