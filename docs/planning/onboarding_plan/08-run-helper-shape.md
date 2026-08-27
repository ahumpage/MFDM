# First-run helper: shape and option passthrough

- **Type**: `wayfinder:prototype` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [What are this project's dependencies, and what declares them?](00-dependency-contract.md)
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The normal workflow is: run the model, stop if it failed, then start the dashboard.
Today a user does that by hand, and nothing in the repo automates it. There is no `.ps1`,
`.bat`, `.cmd` or `Makefile` anywhere.

This is a **prototype** ticket because the question is "what should it feel like to
run", and that is answered faster by making a rough one and reacting to it than by
arguing about it in prose.

### What the audit found

- **The premise is already settled elsewhere.** `dashboard_plan.md` records as a settled
  premise that *"A separate entry point runs the model then the dashboard"*, and
  `docs/planning/dashboard_plan/03-rerun-workflow.md` is the open ticket for it. That
  effort never closed. This ticket should read that one before starting, and may
  supersede it — see [Stale planning maps](09-stale-planning-maps.md).
- **`model/MFDM.py` imports no dash and no plotly.** That separation is a constraint to
  preserve: the helper coordinates two entry points, it does not merge them.
- **`MFDM.parse_args` exposes five flags**: `--label`, `--notes`, `--no-archive`,
  `--inputs`, `--results`. Only the first three are named in the Origin.
- **The flags interact.** `MFDM.main` skips archiving when `--no-archive` **or**
  `--inputs` **or** `--results` is given. So `--label` and `--notes` have **no effect**
  when combined with `--inputs` or `--results` — they name a run in an archive that will
  not be written. A passthrough that accepts all five without explaining this hands the
  user a silent no-op.
- **The dashboard URL** is `http://127.0.0.1:8050`. `README.md`'s only troubleshooting
  line today is "To rerun, first close dashboard with ctrl c" — which suggests the
  stop-and-rerun cycle is the friction the helper exists to remove.

### What to prototype, then decide

- **The artefact.** PowerShell `.ps1` is native to the stated platform and can test the
  exit code cleanly. A Python `run.py` is cross-platform and can reuse `MFDM.parse_args`
  rather than re-declaring flags. A `.bat` is the lowest common denominator. Make one,
  see how it reads.
- **Failure behaviour.** The acceptance criterion is that a failed model run must not
  open the dashboard. `MFDM.py` exits `1` on any exception, so this is available — but
  decide what the user *sees* when it happens, given the model already prints a
  reasonably detailed error.
- **Which options pass through**, and what happens to the `--label`/`--inputs`
  interaction above: reject the combination, warn, or stay silent and let the model
  decide.
- **Does the helper do anything other than run two things?** Checking that dependencies
  are installed, or that `git` is on PATH, would turn it into a doctor script. That may
  be exactly what a first run needs, or scope creep — the prototype will show which.
- **Stopping the dashboard**, and whether the helper says how.

Link the prototype from this ticket rather than pasting it in.

## Decision
