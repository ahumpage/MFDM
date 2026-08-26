Start reading in model/MFDM.py, this is the main model which the repo is based around.
The purpose of the repo is to build a power dispatch model from the ground up, adding in
complications and adjusting, as part of onboarding training.
The model should be built using PuLP.
The code should be readable and easy to follow, so that it can be used as a learning tool.

Layout and run order
    requirements.txt        pinned dependencies, python 3.8; pip install -r requirements.txt
    inputs/                 plants.csv, fuel.csv, demand.csv, profiles.csv
    model/MFDM.py           the dispatch model, reads inputs/ and writes results/
    results/                dispatch_results.csv, plant_summary.csv
    dashboard/dashboard.py  Dash app for presenting and QA-ing results

Run model/MFDM.py first, then dashboard/dashboard.py, which reads the CSVs in results/.

Runs that are not the most up to date are archived by run_archive/runstore.py into a
timestamped folder under run_archive/, each with a manifest.json recording the git commit
and input hashes. The archive is kept in the repo so past runs stay usable on this machine.

## Key documents

    CONTEXT.md                  the vocabulary. Read this before using a term that
                                sounds domain-specific; several are collisions
                                (spill vs curtailment, price vs highest running cost)
    README.md                   the model stated as maths: sets, parameters,
                                objective, constraints
    docs/ramping_semantics.md   what ramping means, why the clearing price is now
                                the energy-balance dual, and two worked 3-hour
                                examples that can be run
    docs/examples/ramping/      input folders for those worked examples. Run with
                                model/MFDM.py --inputs <folder> --results <folder>

## Agent skills

### Issue tracker

Local markdown under `docs/planning/`. There is no live issue tracker and `gh` is not
installed. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
