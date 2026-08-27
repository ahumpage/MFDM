# The rerun workflow: wrapper script and what "previous" means

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Dashboard next iteration](../dashboard_plan.md)

## Question

Charting settled the shape: a wrapper script runs the model and then the dashboard, so
`MFDM.py` never imports Dash. Today nothing joins them — the model writes CSVs and
archives (MFDM.py:607-633), the dashboard is launched separately and prints a URL that
nobody clicks (dashboard.py:1634-1643).

Decide:

- **The script's surface.** Does it forward `--label`, `--notes` and `--no-archive`
  through to the model (MFDM.py:569-578), or take its own arguments? What happens when
  the model raises — no dashboard, or the dashboard on the previous results?
- **How the browser opens.** Python's `webbrowser` on a timer before `app.run` is the
  usual trick, since `app.run` blocks. Does it open every time, or only on request?
  Opening a second tab on every rerun gets old fast.
- **What "previous" means for the compare default.** This is subtler than it looks.
  After a rerun, `results/` holds the new run *and* it has been archived, so the newest
  archived run and the working folder are the same numbers. "Previous" therefore means
  the second-newest archived run. Confirm that, and decide what happens on the very
  first run when there is no previous.
- **Where the default is expressed.** `refresh_run_lists` (dashboard.py:1400-1405)
  populates the compare dropdown and excludes the selected run; a default value could
  go there, or in the layout at import time (dashboard.py:939-963).
- **Whether the dashboard should restart at all.** `load_current()` deliberately
  re-reads from disk rather than caching (dashboard.py:202-204) and there is already a
  `run-refresh` button, so a long-running dashboard plus a refresh may beat relaunching
  it. That would make the wrapper only start one if none is running — more moving
  parts, but no lost browser state.

## Settled early: the compare default

Two of the bullets above were answered ahead of the rest, while making the comparison
readable. **Status stays `open`** — the wrapper script, the browser-opening and the
restart question are all still undecided, and this ticket is still the place they get
decided. Recorded here so that work does not reopen them.

**What "previous" means.** Confirmed as stated: the second-newest *archived* run. The
dashboard opened on the working folder against the newest archive, which after any
rerun are the same numbers, so every delta chart read "no change" and the comparison
was worthless by default. The working folder is now not part of the default pair at
all; it stays selectable for the case where results have been written but not archived.

**The first run, with no previous.** With exactly one archived run, A is that run and B
is empty; the compare tab shows its "Pick a run" message. Deliberately *not* paired
with the working folder, for the reason above — it would be the same run twice, which
is the bug being fixed. With no archived runs at all, A falls back to the working
folder.

**Where the default is expressed.** In the layout at import time, via a new
`default_run_ids()`, not in `refresh_run_lists`. Expressing it in the callback meant it
was reapplied on every refresh, so deliberately clearing "Compare with" and pressing
Refresh silently undid the clearing. The callback now only enforces that A and B are
different runs; choosing the opening pair is a startup concern and happens once.
