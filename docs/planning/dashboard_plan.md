# Map: Dashboard next iteration

`wayfinder:map` — the map for this effort. Tickets are the files in `dashboard_plan/`.

## Destination

A written spec, `docs/dashboard_spec.md`, for how the dashboard presents a model run
to someone judging it: the explanatory layer, the run comparison, and the rerun
workflow. Alice implements from it afterwards; this map produces no dashboard code.

## Notes

- **Domain**: `dashboard/dashboard.py`, a 1643-line Dash app reading `results/` and
  `run_archive/` via `runstore`. Three tabs: dispatch and price, duration curves and
  mix, compare runs. Onboarding training repo — readable beats clever.
- **Plan only.** Tickets resolve decisions. Prototype tickets may produce a throwaway
  mock to react to, but no change lands in `dashboard.py` from this map.
- **Audience**: Alice reads and implements. Decisions + rationale, not agent-ready
  acceptance criteria.
- **Skills every session should call**: `grilling` and `domain-modeling`. Write terms
  into `CONTEXT.md` as they resolve.
- **Sibling map**: [Map: Model semantics](model_plan.md) is deciding what QA means.
  This map must not redesign the QA tab underneath it.
- **On close**: assemble `docs/dashboard_spec.md` and add a one-line pointer in
  `AGENTS.md` under `### Dashboard`.

### Settled while charting

Premises, not steps on the route.

- **Rerun workflow is a wrapper script.** A separate entry point runs the model then
  the dashboard. `MFDM.py` does not import or launch Dash; the model stays free of
  the web framework. Details in [The rerun workflow](dashboard_plan/03-rerun-workflow.md).
- **Comparison defaults to the previous run** rather than starting empty.
- **Comparison charts show the difference, not the overlay.** Two absolute series on
  one chart is the readability problem; B-minus-A is the fix, possibly with a toggle.
  _Superseded by [The comparison view](dashboard_plan/02-comparison-view.md): the
  premise held for the price chart, where three series on two axes was indeed the
  problem, but not for generation. Absolutes and difference are now both always shown,
  the absolutes as two side-by-side stacks on a shared axis rather than overlaid on
  one chart, which was the unreadability the premise was really reacting to._

## Decisions so far

<!-- one line per closed ticket -->

- **[The comparison view](dashboard_plan/02-comparison-view.md)** — show absolutes
  *and* difference, always, and delete the toggle: two dispatch stacks side by side on
  a shared y-axis, per-plant delta bars beneath, and the clearing price overlaid with
  B-minus-A under it. Plants toggle once, through the shared checklist.
- **[The rerun workflow](dashboard_plan/03-rerun-workflow.md)** (partial, still open) —
  "previous" means the second-newest archived run, not the working folder, which is a
  copy of the newest; the default is expressed in the layout at import time, not in
  `refresh_run_lists`.

## Not yet specified

In scope, not yet sharp enough to ticket.

- Whether three tabs survive an explanatory layer. Adding explanation to every chart
  may want a different navigation shape entirely, but that only becomes answerable
  once [The explanatory layer](dashboard_plan/01-explanatory-layer.md) has decided how
  much explanation there is.
- Whether the resolution buckets and the area-chart fallback above `BAR_THRESHOLD`
  (dashboard.py:347) need explaining to a viewer, or are an implementation detail they
  should never have to think about.
- Whether the explanatory layer must describe scarcity pricing and unserved energy —
  concepts that do not exist in the model yet and are being decided by the sibling map.

## Out of scope

Past the destination. Returns only as a fresh effort.

- **The QA tab.** `run_qa` (dashboard.py:585) already checks price-equals-dual and LP
  optimality. [Map: Model semantics](model_plan.md) is deciding those invariants from
  scratch. Revisiting the tab is sequenced *after* that map closes, so the dashboard's
  checks match the agreed ones.
- **Renaming archive runs.** Written up with cause and options in
  [extra_plan.md](extra_plan.md). It is a `run_archive/` problem, not a dashboard one.
- **Understanding the objective function.** Covered by the sibling map.
- **The price line alignment.** Fixed directly, not charted: `"hv"` → `"hvh"` in
  `fig_dispatch`, `fig_price` and `fig_compare_price`, so each flat run is centred on
  its hour instead of starting half a bar to the right of it.
