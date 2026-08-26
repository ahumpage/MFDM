# Map: Ramping

`wayfinder:map` — the map for this effort. Tickets are the files in `ramping_plan/`.

**Status: closed.** Every ticket is resolved. The spec is
[docs/model_semantics.md](../model_semantics.md), and — unlike the plan below
anticipated — the implementation landed in the same effort. See
[What actually happened](#what-actually-happened).

> Renamed since. This map was written when the spec was called
> `docs/ramping_semantics.md`; references to that filename below are historical.
> It became `docs/model_semantics.md` because roughly 70% of it was always
> model-wide rather than ramping-specific — see
> [Which document owns which fact?](onboarding_plan/01-doc-set-ownership.md).

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
  _Overtaken: Alice asked for planning and implementation together. See
  [What actually happened](#what-actually-happened)._
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
  _Done, plus `CONTEXT.md`, the dashboard and the tracker doc._

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
  _**Overturned in part.** The spill variable and the balance are as described, but
  pricing it at VOLL is wrong, and the caveat understated it: shedding and dumping are
  not equally bad, dumping is strictly worse, so spill never happens at all.
  `SPILL_COST` is $1,000. See [05](ramping_plan/05-spill-hour-price.md).
  The "always feasible" claim does hold, though not for the reason given here — the
  all-zeros dispatch satisfies every constraint, so feasibility was never in doubt.
  A related trap that is **not** about feasibility is described in
  [What actually happened](#what-actually-happened)._
- **Ramping is symmetric.** One `Ramp_efficiency` column and one `Ramp_time` column,
  so up and down cost the same per MWh and share one rate limit. Splitting them is a
  later effort.
- **Ramping efficiency never exceeds normal efficiency**, so ramp cost is never
  negative. Validated on load, mirroring the existing efficiency guard (`MFDM.py:193`).

## Decisions so far

<!-- one line per closed ticket -->

- **[00 Research](ramping_plan/00-research-ramp-cost-and-prices.md)** — use a linear
  penalty on the ramp delta to keep it an LP; minimise production cost, not any one
  marginal cost, which is why the dual becomes the honest price.
- **[01 Ramp time](ramping_plan/01-ramp-time-meaning.md)** — *dissolved.*
  `plants.csv` now carries `Ramp_rate (MW/hr)` directly, so there is nothing to
  derive, and the rates bind.
- **[02 Ramp cost form](ramping_plan/02-ramp-cost-form.md)** — per-MWh-of-ramp
  adder, `fuel/ramp_eff - fuel/eff`, charged on `V_up + V_dwn`. Ramped MWh charged
  twice, deliberately. Premium sits outside the merit order.
- **[03 Spill mechanism](ramping_plan/03-spill-mechanism.md)** — system-wide
  `spill[t]`, not per plant. Spill and curtailment stay distinct terms, both kept;
  `CONTEXT.md` created.
- **[04 Clearing price](ramping_plan/04-clearing-price-meaning.md)** — the dual
  becomes canonical. Merit order survives as the `Highest Running Cost` diagnostic.
  Mismatch counter deleted. Supersedes the Model-semantics premise.
- **[05 Spill hour price](ramping_plan/05-spill-hour-price.md)** — `-SPILL_COST`,
  falling out of the dual with no special case. **`SPILL_COST` is $1,000, not VOLL**:
  at VOLL spill is strictly dominated by shedding load and never occurs.
- **[06 Merit order invariant](ramping_plan/06-merit-order-invariant.md)** — demoted
  to a warning, with a ramp ceiling and floor. No invariant survives worth raising
  on; the objective reconciliation becomes the real gate instead.
- **[07 Output schema](ramping_plan/07-output-schema.md)** — system-total ramp
  columns; `Ramp Cost` is the premium alone; `Production Cost` unchanged so the four
  objective components stay separable, and the reconciliation is now checked.
- **[08 Worked example](ramping_plan/08-worked-example.md)** — two runnable
  3-hour fixtures under `docs/examples/ramping/`, all arithmetic verified by running
  them.
- **[09 Tracker doc](ramping_plan/09-fix-tracker-doc.md)** — rewritten for local
  markdown, whole document rather than just the Wayfinding section.

## What actually happened

Recorded because it departs from the plan in three ways a future reader should not
have to reconstruct.

**The map said "plan only, no code". The effort produced the code as well.** Alice
asked for planning *and* implementation in one pass, so the tickets were resolved
as decisions in a single session rather than one session each, and the model was
fitted to the spec immediately. The spec is still the artefact; it is just no
longer ahead of the code.

**Two decisions were overturned by measurement, not by argument.**

- *Spill priced at VOLL* was a settled premise on this map. It is wrong: it makes
  spill strictly dominated by shedding load, so the mechanism never fires and the
  model blacks out demand rather than dump surplus. Found by building the fixture
  and comparing objectives. `SPILL_COST` is now $1,000.
- *`Ramp_time (hrs)`* — the entire subject of ticket 01 — no longer exists in
  `plants.csv`. The input file changed after the map was charted.

**One failure mode nobody had ticketed.** A ramp-down floor and an availability
ceiling can be jointly unsatisfiable at any positive output, when a wind or solar
profile collapses faster than the plant's ramp rate. The plant is then trapped by
its own good hours: it must generate far below its peak or be stranded above its
ceiling. Handled with a cost-free ramp-down allowance bounded by the drop in the
plant's own availability.

Worth recording precisely, because the first attempt at this got it wrong and
called it *infeasibility*. It is not: the all-zeros dispatch satisfies every ramp
constraint, so the LP can always retreat to it and price the demand at VOLL. The
failure is silent and expensive rather than loud. On a hostile fixture — a 500 MW
solar farm limited to 10 MW/hr, resource falling to zero after one hour —
removing the allowance takes the objective from $4,400 to $2,415,010 and leaves
58% of demand unserved. Caught by testing the claim rather than asserting it.

It never binds on current inputs; it exists so that editing one number in
`plants.csv` cannot silently wreck the dispatch.

**One knock-on break.** `run_archive/runstore.py` read `Hours Setting Price` by
name and threw `KeyError` on the first ramping run, silently skipping the archive.
Fixed, with the KPI key left unchanged so old and new runs still diff.

## Still open after this effort

Was "Not yet specified". These are now genuinely out of the effort's scope rather
than merely unsharp, and each is recorded in the spec's Known gaps section.

- **Whether renewables should pay a ramp cost.** They pay zero today only because
  their fuel price is zero. Their ramp *rates* are equally a placeholder, set to
  nameplate so nothing binds. Lucky, still not chosen.
- **Whether `SPILL_COST` should be $1,000.** It has the two properties it needs —
  above every marginal cost, below VOLL — and no more justification than that. It
  dominates the objective whenever it fires ($50,000 of a $55,600 fixture).
- **Ramp and spill KPIs in `run_archive`.** Still blocked on the KPI-versioning
  question parked in [extra_plan.md](extra_plan.md). The consequence is now
  concrete: a run diff reports +2.5% on `production_cost` where true system cost
  rose +16.4%.
- **`inputs/plants.csv` header.** `Ramp_efficiency($/hr)` holds MWh/MWhTh. The
  model locates the column by prefix, so Alice can rename it to
  `Ramp_efficiency (MWh/MWhTh)` safely and without touching code.

## Out of scope

Past the destination. Returns only as a fresh effort.

- **Writing tests.** [The worked example](ramping_plan/08-worked-example.md)
  specifies the example the spec must contain and it is now two runnable input
  folders, but turning them into assertions is still not done.
- **Unit commitment, minimum generation, must-run, start-up costs.** Ramping's
  natural neighbours, all absent from the model. New work, not ambiguity to resolve.
- **Splitting ramping into separate up and down rates and premiums.** One
  `Ramp_rate` and one `Ramp_efficiency` serve both directions.
- **Editing `inputs/plants.csv`.** Alice's file; see Notes.

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
