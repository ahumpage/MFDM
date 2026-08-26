# Map: Ramping

`wayfinder:map` — the map for this effort. Tickets are the files in `ramping_plan/`.

## Destination

A written spec, `docs/ramping_semantics.md`, stating what ramping *means* in MFDM:
how ramping efficiency becomes a cost in the objective, what limits a plant's
hour-to-hour movement, what happens when a plant cannot ramp down fast enough, what
the reported prices represent once cost is intertemporal, which output columns exist
and what each one claims, and one fully worked 3-hour example. Alice implements
afterwards, fitting the code to the spec; this map produces no code.

## Notes

- **Domain**: least-cost economic dispatch LP (PuLP), `model/MFDM.py`. Onboarding
  training repo, so readability beats cleverness in anything the spec prescribes.
- **Tracker**: local markdown, as here. `docs/agents/issue-tracker.md` claims GitHub
  and is wrong (`gh` is not installed and no map has ever used it);
  [Correct the tracker doc](ramping_plan/09-fix-tracker-doc.md) fixes it.
- **Plan only.** Every ticket resolves a decision. No prototypes, no implementation,
  not even throwaway code. The pull to start writing the model means the map is done.
- **Audience**: Alice reads and implements. The spec is decisions + rationale +
  worked numbers, not agent-ready acceptance criteria.
- **Skills every session should call**: `grilling` and `domain-modeling`. Write terms
  into `CONTEXT.md` as they resolve — the repo has none yet, so the first session to
  resolve a term creates it. Ramping introduces real new vocabulary (ramp rate, ramp
  cost, ramping efficiency, spill) and one collision, spill vs curtailment, handled in
  [Spill: system-wide or per-plant](ramping_plan/03-spill-mechanism.md). ADRs only
  where a decision is hard to reverse.
- **This map redraws a boundary.** [Map: Model semantics](model_plan.md) ruled
  *"explicit or penalised curtailment"* and *"negative prices"* out of scope. Priced
  spill is the former, and a spill hour's price may be the latter. That is deliberate:
  out-of-scope work returns only as a fresh effort, and this is it.
- **Alice owns `inputs/plants.csv`.** No ticket edits it. The `Ramp_efficiency($/hr)`
  header is a unit lie — the values are efficiencies in MWh/MWhTh (Coal 0.4→0.3, Gas
  0.5→0.2, Gas 0.3→0.1) — and should become `Ramp_efficiency (MWh/MWhTh)`. Alice's
  edit, recorded here so it is not lost.
- **On close**: assemble `docs/ramping_semantics.md`, add a one-line pointer to it in
  `AGENTS.md`, and update `README.md` per the Origin outline's final line.

### Settled while charting

Premises, not steps on the route. Recorded so no ticket reopens them by accident.

- **Linear horizon; no ramp constraint in hour 1.** Hour 1 has no predecessor, so
  every plant starts wherever it likes, free of charge. The horizon does not wrap.
  `HOURS` must be ascending and contiguous — true of `demand.csv` today (744 rows,
  hours 1–744, sorted, no gaps, no duplicates) but unvalidated, since `HOURS` is taken
  straight from row order (`MFDM.py:161`). `build_parameters` gains that check at
  implementation time.
- **Ramp-down infeasibility is solved with a priced spill variable.** A ramp-down
  limit puts a *floor* under a plant, which can force total generation above demand
  and make the equality energy balance infeasible; `unserved` only covers the opposite
  direction. The balance becomes `sum(gen) + unserved - spill == demand`, with
  `spill[t] >= 0` priced at VOLL, mirroring `unserved`. The model stays
  always-feasible. Caveat on record: spill at VOLL makes shedding and dumping equally
  bad at the margin, and lets one stuck hour dominate the run's objective.
- **Ramping is symmetric.** One `Ramp_efficiency` column and one `Ramp_time` column,
  so up and down cost the same per MWh and share one rate limit. Splitting them is a
  later effort.
- **Ramping efficiency never exceeds normal efficiency**, so ramp cost is never
  negative. Validated on load, mirroring the existing efficiency guard (`MFDM.py:193`).

## Decisions so far

<!-- one line per closed ticket -->

_None yet._

## Not yet specified

In scope, not yet sharp enough to ticket.

- How `plant_summary.csv`'s "Hours Setting Price" survives. It matches a plant by
  `|clearing_price - marginal_cost| < 1e-6` (`MFDM.py:496`), which assumes the price is
  always some plant's marginal cost. Graduates once
  [What the clearing price represents](ramping_plan/04-clearing-price-meaning.md) lands.
- Whether renewables should ever pay a ramp cost. Today they would pay zero, but only
  because their fuel price is zero, not because anyone decided it. A solar farm being
  curtailed and un-curtailed is a large hour-to-hour swing at no charge. Lucky, not
  chosen.
- Whether ramp cost should reorder the merit-order stack itself, or sit outside it as a
  separate charge. Hangs on [How ramping efficiency becomes a
  cost](ramping_plan/02-ramp-cost-form.md).
- Whether VOLL remains the right spill price once the objective inflation is visible in
  a real run.

## Out of scope

Past the destination. Returns only as a fresh effort.

- **`dashboard/dashboard.py`.** Includes two now-false claims to users that ramp rates
  are not modelled (lines 580 and 751) and any surfacing of new columns. A follow-on
  chore, not a decision.
- **`run_archive/` KPIs.** Adding ramp and spill KPIs drags in the unresolved
  KPI-versioning decision already parked in [extra_plan.md](extra_plan.md).
- **Writing tests.** [The worked example](ramping_plan/08-worked-example.md) specifies
  the example the spec must contain; turning it into a test file is implementation.
- **Unit commitment, minimum generation, must-run, start-up costs.** Ramping's natural
  neighbours, all absent from the model. New work, not ambiguity to resolve.
- **Editing `inputs/plants.csv`.** Alice's file; see Notes.
- **Implementing the spec.** Fitted to the spec after this map closes.

## Origin

The loose outline this map was charted from, verbatim.

> # plan outline for ramping
>
> to add ramping I want the following:
> ramping cost should be added to the objective function
> four additional constraints to be added:
> $ V_{up} \geq g(p,t)-g(p,t-1)\leq R_{up}(p)$
> $ V_{dwn} \geq g(p,t-1)-g(p,t)\leq R_{dwn}(p)$
> $V_{up} \geq 0$
> $V_{dwn} \geq 0$
>
> $V_{up} and V_{dwn}$ are the ramp up and down speed respectively
> g is generation
>
> to be added to objective function:
> $\sum_{t,p} R_{upcost} \times V_{up}(t,p) = \sum_{t,p} R_{dwncost} \times V_{dwn}(t,p)$
> where the ramp up and down cost $R_{upcost}$ and $R_{dwncost}$ is based on the ramping
> efficiency for that plant and fuel, used instead of the efficiency at non ramping
> times. These should be calculateable from the plants.csv and fuel.csv files
>
> These equations should be added to the readme file along with the other constraints
> and the rest of the objective function

Two readings of this outline are carried into tickets rather than assumed. The `=` on
the objective line is read as *both sums are added*, not as an equality constraint. And
*"used instead of the efficiency at non ramping times"* is genuinely ambiguous, which is
[How ramping efficiency becomes a cost](ramping_plan/02-ramp-cost-form.md).
