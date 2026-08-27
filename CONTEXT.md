# CONTEXT

The vocabulary of this repository. One entry per term that means something
specific here, or that collides with a term meaning something else elsewhere.

MFDM is a least-cost economic dispatch model built with PuLP, written as
onboarding training. Readability beats cleverness throughout.

---

## Core

**Dispatch** — deciding how much each plant generates in each hour. The model
chooses the cheapest dispatch that meets demand.

**Plant** — a single generating unit, one row of `inputs/plants.csv`. Not a site
and not a technology; two rows with `Technology` of `Gas` are two separate plants.

**Technology** — what a plant is (`Coal`, `Gas`, `Wind`, `Solar`). Determines
whether the plant is *profiled*.

**Fuel** — what a plant burns, priced per MWh **thermal** in `inputs/fuel.csv`.
Confusingly, the fuel price table's first column is headed `Technology` but holds
fuel names. Wind and solar carry the literal string `None` and are free.

**Marginal cost** — `fuel_price / efficiency + VOM`, in $/MWh electrical. What one
more MWh from a plant costs when it is already running steadily.

**Merit order** — plants sorted by marginal cost. The cheapest way to serve a load
in a single isolated hour. Ramping means the dispatch no longer follows it, and
that is not a bug; see `docs/ramping_semantics.md`.

**Horizon** — the hours in `inputs/demand.csv`, currently 744. It must be
ascending, contiguous and free of gaps, and it does **not** wrap: hour 744 is not
followed by hour 1.

---

## Availability

**Nameplate capacity** — a plant's maximum output, `Capacity (MW)`.

**Profiled** — a plant whose output is limited by an hourly resource rather than
being available at nameplate around the clock. Wind and solar are profiled;
thermal plants are not.

**Availability** — what a plant *could* generate in a given hour. For a thermal
plant this is nameplate. For a profiled plant it is nameplate scaled by that
hour's capacity factor from `inputs/profiles.csv`.

**Capacity factor** — two different things, always labelled. *Availability
factor* is what the resource offered as a share of nameplate. *Capacity factor*
is what was actually generated, so it is net of curtailment.

---

## Prices

**Clearing price** — the dual of the energy balance constraint: what one more MWh
of demand in that hour would cost the system. This is **the** price. It became
canonical when ramping made the objective intertemporal, and it is no longer
equal to any plant's marginal cost. It can be negative.

**Highest running cost** — a *diagnostic*, not a price: the marginal cost of the
most expensive plant generating in an hour. This is the old merit-order clearing
price under the name of what it actually measures. Never use it for revenue.

**Last in stack** — the plant whose marginal cost equals the highest running cost.
Replaces the old phrase "setting the price", which is now false: under a dual, no
plant sets the price.

**VOLL** — Value of Lost Load, $8,300/MWh. What an hour of unmet demand is worth
to the people who go without.

**Shadow price** — retired as a column name. It meant the dual, which is now
simply the clearing price.

---

## Scarcity and surplus

Four distinct concepts that are easy to conflate. Two are about too little energy,
two about too much.

**Unserved energy** — demand the fleet could not meet. Priced at VOLL. Too little.

**Scarcity hour** — an hour with unserved energy. Prices at VOLL, because the
marginal unit is shed load.

**Curtailment** — renewable resource that was *available and not taken*, because
demand was already met more cheaply. **Free and implicit**: it is not a decision
variable, just `availability - generation` for a profiled plant. Applies only to
wind and solar. Too much, and costless.

**Spill** — energy that was *generated and then thrown away*, because a plant
could not ramp down fast enough to follow demand. **Priced and explicit**: a real
decision variable, `spill[t]`, costing `SPILL_COST`. Applies to any plant, in
practice thermal. Too much, and expensive.

> Curtailment and spill are **not** the same thing and the words are not
> interchangeable. Curtailment is energy never produced; spill is energy produced
> and destroyed. An earlier planning document used "free spill" for what is here
> called curtailment — that usage is retired.

**Spill hour** — an hour with spill. Prices at `-SPILL_COST`, the mirror of a
scarcity hour, because the marginal unit is destroyed energy.

**SPILL_COST** — $1,000/MWh. Deliberately *not* VOLL: setting them equal makes
shedding load strictly cheaper than dumping surplus, so the model would black out
demand rather than spill and the mechanism would never fire. See
`docs/ramping_semantics.md` §4.

---

## Ramping

**Ramp** — a change in a plant's output between two adjacent hours.

**Ramp rate** — the most a plant may move per hour, in either direction, in MW.
A hard limit, from `Ramp_rate (MW/hr)` in `inputs/plants.csv`. Symmetric: one
number governs both up and down.

**Ramping efficiency** — a plant's efficiency *while it is moving*, which is worse
than its steady-state efficiency because changing output burns fuel less
efficiently. Validated never to exceed the ordinary efficiency.

**Ramp premium** — the extra cost of a moved MWh over a steady one:
`fuel_price/ramp_efficiency - fuel_price/efficiency`, in $/MWh. Charged **on top
of** the ordinary marginal cost, so a ramped MWh is charged twice. Sometimes
written `ramp_cost` in the code; the two are the same number.

**Ramp cost** — the premium multiplied by the energy moved. In the output columns
this always means **the premium alone**, never the total cost of ramped energy.

**Ceiling** — the most a plant could generate in an hour:
`min(availability, previous output + ramp rate)`.

**Floor** — the least it could generate: `max(0, previous output - ramp rate)`.
Floors are what make spill possible and what make a genuinely optimal dispatch
look like a merit-order violation.

**Forced ramp down** — a cost-free allowance to ramp down faster than the rate
limit, bounded by the collapse in the plant's own availability. Without it, a
profiled plant whose resource falls faster than its ramp rate is trapped by its
own good hours: it must generate far below its peak, or be stranded above its
ceiling next hour. Note this is not an infeasibility — the model can always
retreat to generating nothing and price the demand at VOLL, which is why the
failure is silent and expensive rather than loud.

---

## Runs

**Run** — one solve, archived under `run_archive/` with a manifest recording the
git commit, input hashes and headline KPIs.

**KPI** — a headline number stored in a run's manifest so that listing and diffing
never has to reopen the result CSVs. Note that the `production_cost` KPI is fuel
and VOM only and excludes ramp cost.
