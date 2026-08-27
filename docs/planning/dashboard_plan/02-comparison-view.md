# The comparison view: what a delta looks like

- **Type**: `wayfinder:prototype` (HITL)
- **Status**: resolved
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Dashboard next iteration](../dashboard_plan.md)

## Question

Charting settled the direction: show the difference, not two overlaid absolutes. This
ticket makes it concrete enough to react to — a rough mock, not a change to
`dashboard.py`.

Where the comparison stands today, so the session does not rediscover it:

- **KPI cards are already deltas** — after value, "was" value, coloured percentage
  change, direction-aware (dashboard.py:1163-1197). These are probably fine.
- **`fig_compare_total` is the problem**: two absolute lines plus demand
  (dashboard.py:1294-1299), justified by a docstring saying stacks cannot be overlaid
  legibly (dashboard.py:1288). Three-plus series on one axis is the unreadability.
- **`fig_compare_price` already has a "B minus A" trace**, but on a secondary axis
  *alongside* both absolutes, and only when the two runs have equal length
  (dashboard.py:1323-1327).
- **`compare_plants_table` has a signed Change column** (dashboard.py:1342-1354).

Decide, by mocking:

- Is the difference the *only* thing shown, or is there a toggle back to absolutes?
  A toggle is more flexible and one more control on an already busy page.
- **Generation difference by plant or in total?** A stacked bar of per-plant deltas,
  positive above and negative below zero, says *why* the total moved — coal down,
  solar up — where a single total line only says *that* it moved. It is also the
  chart the docstring claims cannot be drawn legibly.
- What happens when the runs have different lengths, which currently just suppresses
  the difference trace.
- How zero reads. A delta chart is mostly a flat line at zero for two similar runs, and
  needs to make "nothing changed" obvious rather than looking broken.

Link the mock from this ticket as an asset.

## Decision

Settled directly in `dashboard.py` rather than through a mock, because the difference
view had already been built and the thing left to judge was legibility, which only the
real data shows.

**Absolutes and difference are both shown, always, and the toggle is gone.** The
`compare-mode` radio offered "difference" or "absolute" and so answered the ticket's
first question with "a toggle". That was wrong in practice: the two views answer
different questions — *how much* did each run generate, and *which plant* moved — and a
reader needs both at once to interpret either. A control that hides half the answer is
not flexibility. The radio, and the `_fig_generation_absolute` function behind it, were
deleted.

The comparison tab now reads top to bottom as increasing detail:

1. **Two dispatch stacks side by side**, `fig_compare_dispatch_pair`, as two panels of
   one figure sharing one y-axis. This replaces the old absolute view, which collapsed
   each run to a single total line and so threw away the merit order the stack exists
   to show. The shared axis is load-bearing: scaled independently, a run generating 10%
   more draws a stack the same height as the run it is compared against, and the
   difference the reader came for is scaled away. Each panel is titled with its run
   name, `A - <name>` and `B - <name>`; the bars-or-area mode moves to the figure title
   above both, so the switch is still never silent.
2. **Per-plant delta bars**, the existing `fig_compare_generation`, unchanged. Still
   the answer to "generation difference by plant or in total": by plant, because coal
   down and solar up is the finding, where a total line only says the total moved.
3. **Clearing price overlaid, with B minus A beneath it.** The old
   `fig_compare_price` put the difference on a secondary axis alongside both
   absolutes — three series and two scales on one chart. Split into
   `fig_compare_price_overlay` and `fig_compare_price_diff`, sharing an x-axis in one
   card, at 470px and 300px. Each overlay trace carries its own load-weighted average
   in its legend name, so the headline number is on the chart.

**Plant toggling is the existing shared checklist**, which `plant_options` already
builds as the union of both fleets with a `(B only)` marker. One tick controls both
panels, so they cannot drift out of step.

**One legend over both panels.** This took three attempts. The first dropped panel B's
legend when the fleets matched, on the grounds that one legend served both and the
second was just ink; that was wrong, because the legend is the only way to hide a plant
from the chart itself, so removing it from B made the ability to choose appear to apply
to A alone. The second drew both legends and used `legend_click_to_checklist` to turn a
click into an untick of the shared checklist, so the plant left both panels at once.
That was worse: the figures are rebuilt from the checklist, so the clicked plant lost
its trace, and a legend entry only exists for a trace that exists. The plant vanished
from the legend and could never be clicked back on.

The fix is to stop fighting the constraint that produced both attempts. A Plotly legend
belongs to a figure, so the pair is now **one** figure of two subplots. Each plant's
traces in both panels share a `legendgroup` and only the first carries a legend entry,
so one click hides the plant in A and B together and a second click restores it, with
no callback in the loop. `legend_click_to_checklist` and `visible_plants` are deleted.
The legend swatch shows A's colour for a plant, which can differ from B's, since colour
is keyed on technology and merit position within it — the reason these charts label
rather than rely on colour.

The Plants checklist stays as it was, and is now plainly separate: it decides which
plants reach the charts at all, the legend decides which of those are drawn.

**Overlays apply to both panels too**, from the same shared Overlays checklist, and the
price axis is shared across the pair exactly as the generation axis is. Only `demand`
and `price` mean anything on a generation stack, so `DISPATCH_OVERLAYS` filters
`mclines` and `stack` out rather than drawing price-chart furniture on an MWh axis.

**Different lengths** are unchanged: `align_runs` restricts to the overlapping periods
and `dropped_note` says how many were dropped in the chart title. The side-by-side
panels do not align, deliberately — each shows its own run whole, and the hour slider
is already clamped to the overlap by `switch_run`.

**Zero** is unchanged: `annotate_no_change` still writes "No change" across a delta
chart that is flat, so two similar runs look deliberate rather than broken.
