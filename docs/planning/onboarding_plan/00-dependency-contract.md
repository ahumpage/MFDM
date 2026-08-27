# What are this project's dependencies, and what declares them?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
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

**A single `requirements.txt` at the repo root, flat, exactly pinned.** Five packages,
no split, no extras, no lockfile.

```
numpy==1.24.4
pandas==2.0.3
pulp==3.1.1
plotly==6.9.0
dash==4.3.0
```

**`requirements.txt` rather than `pyproject.toml`**, because this repo is not installed
and is not heading toward being installed. There is no package, no `src/` layout, and
both entry points are invoked by path. `pyproject.toml` buys a build backend and extras,
which is machinery for a distribution artefact this project does not produce.

**Flat rather than split, though the import graph does divide.** `dash` and `plotly` are
imported only by `dashboard/dashboard.py`; `model/MFDM.py` needs numpy, pandas and pulp
alone. A base-plus-dashboard split would mirror that honestly. It was rejected because
the dashboard is step two of the documented workflow rather than an optional extra, so
every user installs all five anyway - and a second requirements file is a second thing to
explain and a second thing to drift. The division is a fact about the code, recorded here
and in the table above, not a fact the file layout needs to express.

**Exact pins, not floors.** Three reasons. The run archive exists precisely so past runs
stay reproducible, and a manifest that fixes the git commit and input hashes while
leaving the solver version floating is only reproducible in part. Pins make CBC's
behaviour deterministic, which matters when the point of the repo is teaching what the
model does. And the usual objection - that pins go stale - has little force here, because
Python 3.8 already caps these libraries (see below), so the versions are frozen whether
or not the file says so.

**Python 3.8 stays, and is stated in the Quickstart and in the file.** 3.8 has been end
of life since October 2024, and numpy 1.24.4 and pandas 2.0.3 are the last releases
supporting it - the pins above are ceilings imposed by the interpreter, not free choices.
Moving off 3.8 is real churn with its own consequences and belongs in its own ticket;
this one does not smuggle it in. The version is declared as a comment at the top of
`requirements.txt` and moves up into the README Quickstart, out of "Additional info",
because it is a prerequisite rather than trivia. Note the Origin's claim that a stale
root `__pycache__` is the only evidence of a target version is wrong: `README.md` has
said "Uses python 3.8" all along, just in the wrong section.

**`git` is declared as a comment in `requirements.txt`, and nowhere else.**
`runstore.git_state()` shells out to `git` on every default run, so a user without it on
PATH hits the `try/except` in `MFDM.main` and gets an unexplained warning. It is not a
pip dependency, so a comment is the only honest place for it. It stays out of the README
because run archiving is not expected to remain a committed, every-run concern -
`run_archive/` is already gitignored - and the Quickstart should not carry a caveat with
a short shelf life. The comment names `--no-archive` so a reader who
hits the warning is told the remedy in the same line. **This closes the map's *Not yet
specified* entry on `git` as far as declaration goes; what *should* happen when `git` is
absent, beyond the current warning, remains open.**

**CBC is not documented anywhere, and the Origin's concern about it was a non-problem.**
PuLP bundles CBC, so no separate solver install is needed on Windows. More to the point,
the solver is invoked as `pulp.PULP_CBC_CMD(msg=0)` at `MFDM.py:618` - `msg=0` suppresses
all solver output, and the only thing printed is `Solver status: Optimal`, which names no
solver. The string "CBC" never reaches a user, so there is nothing to explain and no
phantom install step for anyone to go hunting for.

**The README stops listing packages and links to the file instead.** Two statements of
the dependency set is exactly how they drift apart, so `requirements.txt` becomes the
single source of truth and the Quickstart points at it, alongside the install command
`pip install -r requirements.txt` - which is the thing the repo most conspicuously lacked.

**No virtual environment is recommended.** The stated failure is that a new user cannot
get from a clone to a working model without guessing; one install command fixes that. A
venv solves isolation, which is not the problem on a single-machine onboarding repo where
the packages are already installed globally. Revisit if this repo ever shares a machine
with a conflicting project.

**`AGENTS.md` gets a pointer too.** Its "Layout and run order" block lists the
directories but never mentions installing anything, and an agent that never opens
`README.md` would not find the contract at all. One line naming `requirements.txt`,
because agent discoverability is the point of the surrounding map.

### Downstream work

Writing the file and the doc edits. Not done here.

### Noted in passing, not decided here

`AGENTS.md` states "The archive is kept in the repo so past runs stay usable on this
machine", but `.gitignore:9` excludes `run_archive/`. One of the two is wrong. Belongs
with [Which document owns which fact?](01-doc-set-ownership.md) or the map's *What is
committed to git* entry.
