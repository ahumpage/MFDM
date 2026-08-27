# One KPI implementation or four?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [What does "energy served" mean, and what divides the load-weighted price?](03-kpi-semantics.md)
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The same arithmetic is written out four times, in four files, and three of the copies are
wrong. Fixing the three copies leaves the structure that produced them intact. Decide
whether this repo keeps one definition of a KPI or four.

### What the audit found

The four sites: `MFDM.print_report`, `runstore.compute_kpis`, `dashboard.window_kpis`,
`dashboard.build_kpis`. They are genuinely independent code paths — **the dashboard does
not read `manifest["kpis"]` for any displayed number.** It loads manifests only for
`label` and `git` provenance, and recomputes every KPI from the CSVs. It even calls
`runstore.diff()` and then discards the `kpi_delta` that `diff()` computed.

Consequence: **a fix to `compute_kpis` alone corrects the CLI and leaves both dashboard
surfaces wrong, and vice versa.** That is the structural problem, and it is the reason
this defect survived the scarcity-pricing work.

The good news is that the plumbing already exists. `runstore` is the de facto shared
module: `MFDM.py` and `dashboard.py` both insert `run_archive/` onto `sys.path` and
import it, and `runs.py` imports it directly. A shared helper placed there would be
reachable from all four sites with **no new plumbing**. The duplication is incidental,
not structural.

One asymmetry worth noting: the three that recompute do so over different inputs.
`compute_kpis` takes `(results, summary)` at archive time; `window_kpis` takes an hour
*slice* so the comparison tab can rescope; `build_kpis` takes a slice and returns Dash
components, not numbers. Any shared function has to serve a windowed call, and has to
separate computing a KPI from rendering it.

### What has to be decided

- **Extract or not.** A shared `compute_kpis(results, summary)` in `runstore`, called by
  all four, versus fixing the three copies and accepting the duplication with a comment.
  Extraction is the obvious answer, which is reason to check what it costs: it makes
  `MFDM.py` — the file `AGENTS.md` says to start reading — depend on `runstore` for its
  printed report as well as for archiving.
- **Does `MFDM.print_report` participate?** It currently computes its own totals inline,
  which is readable in a file whose whole purpose is being readable. Routing it through
  a shared helper trades locality for consistency, and this repo's stated priority is
  that the model reads as a learning tool.
- **What the seam looks like.** A function returning a dict of scalars, with rendering
  left to each caller, is the shape all four sites could accept. Confirm it handles the
  windowed case and the summary-optional case (`window_kpis` has no `summary`).
- **Does `dashboard` start reading `manifest["kpis"]`** instead of recomputing? That
  would be a larger change and would tie displayed numbers to archive time rather than
  view time — which breaks the hour-window rescoping the comparison tab depends on.
  Probably no, but it should be ruled out deliberately rather than by omission.
- **What stops the fifth copy.** Whatever is decided, say where the rule is written down
  so the next feature does not add another.

## Decision
