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
