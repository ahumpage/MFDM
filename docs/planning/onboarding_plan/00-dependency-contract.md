# What are this project's dependencies, and what declares them?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

There is no dependency file of any kind in this repo. Not `requirements.txt`, not
`pyproject.toml`, not `environment.yml`, not a lockfile. The only statement of what to
install is one line of prose in `README.md`, and there is no install command anywhere.
A new user cannot get from a clone to a working model without guessing.

Decide the **dependency contract**: what is declared, in what file, at what precision.

### What the audit found

The complete third-party set is exactly five packages, and they do not divide evenly
across the repo:

| File | Third-party imports |
|---|---|
| `model/MFDM.py` | numpy, pandas, pulp |
| `run_archive/runstore.py` | pandas |
| `run_archive/runs.py` | none directly |
| `dashboard/dashboard.py` | numpy, pandas, plotly, dash |

So **dash and plotly are needed by the dashboard alone**. `AGENTS.md` opens by telling a
reader to start with `model/MFDM.py`, and that file needs no web framework — yet the
README's flat list tells them to install one.

Three further facts a decision has to absorb:

- **PuLP bundles CBC.** No external solver install is required on Windows. The Origin
  asks what to do "if the solver is unavailable", which may be a non-problem — or may
  not be, on a locked-down machine where the bundled binary will not execute.
- **`git` is an undeclared runtime dependency.** `runstore.git_state()` shells out to
  `git` via `subprocess`, and archiving happens on every default run. A user without
  `git` on PATH hits the `try/except` in `MFDM.main` and gets a warning.
- **The only evidence of a target Python version** anywhere in the repo is an untracked
  root `__pycache__` holding CPython **3.8** artefacts from when the modules lived at
  the repo root.

### What has to be decided

- **Which file.** `requirements.txt` is the lowest-ceremony option and matches a repo
  with no package, no `src/`, and scripts invoked by path. `pyproject.toml` would be the
  first step toward making this installable, which may be more than the destination needs.
- **Split or flat.** A base set plus a dashboard extra reflects the real import graph
  and lets a learner run the model without dash. A flat list is simpler to explain. If
  split, what is the mechanism — two files, or extras in a `pyproject.toml`?
- **Pinning.** Exact pins are reproducible and go stale; floors (`pandas>=2.0`) are
  kinder and admit drift; nothing at all is what exists today. Note this is a
  single-machine onboarding repo whose run archive is committed *precisely* so past runs
  stay reproducible — that argues one way.
- **Python version.** Which is supported, and where is it stated so that both a human
  and an agent find it?
- **Whether `git` and the CBC bundling get documented**, and where. See the map's *Not
  yet specified* for the open question of what happens when `git` is absent.

The decision is the contract, not the file. Writing the file is downstream work.

## Decision
