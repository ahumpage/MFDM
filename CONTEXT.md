# CONTEXT

The vocabulary of this repository. One entry per term that means something
specific here, or that collides with a term meaning something else elsewhere.

An entry says what a term **denotes**. It does not justify why the model is built
that way — that is `docs/model_semantics.md`. If an entry needs a worked example
to make sense, it belongs there instead, with a pointer from here.

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
that is not a bug; see `docs/model_semantics.md`.

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

**LoL** — the cost of lost load, $8,300/MWh. What an hour of unmet demand is
worth to the people who go without, and the price unserved energy is charged at.
A price in $/MWh, not a quantity of energy and not a probability.

**Shadow price** — retired as a column name. It meant the dual, which is now
simply the clearing price.

**Market cost** — `clearing price × demand` for an hour: what the demand of that
hour cost at the price, as opposed to what it cost to produce. Negative in a spill
hour, because the price is. Not the objective, which minimises production cost.

**Production cost** — fuel and VOM only. Deliberately excludes ramp cost, so that
the four components of the objective stay separable and can be checked against it.

**Load-weighted price** — the average price each MWh actually paid,
`total market cost / total demand`. The default average, because it is what is
paid.

**Time-weighted price** — the plain mean of the hourly prices, each hour counting
once regardless of how much energy flowed. Always reported beside the
load-weighted figure and never instead of it: cheap hours are usually quiet hours,
so it understates what demand cost.

**Producer surplus** — `market cost - production cost`, across the fleet. What
generators collectively earn above what it cost them to generate.

**Inframarginal rent** — the same idea for one plant: what it earns at the
clearing price above its own marginal cost. A plant earns rent in every hour the
price sits above its running cost.

---

## Scarcity and surplus

Four distinct concepts that are easy to conflate. Two are about too little energy,
two about too much.

**Unserved energy** — demand the fleet could not meet. Priced at LoL. Too little.

**Scarcity hour** — an hour with unserved energy. Prices at LoL, because the
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

**SPILL_COST** — $1,000/MWh. Deliberately *not* LoL: setting them equal makes
shedding load strictly cheaper than dumping surplus, so the model would black out
demand rather than spill and the mechanism would never fire. See
[Why spill is priced at $1,000/MWh and not at LoL](docs/model_semantics.md#why-spill-is-priced-at-1000mwh-and-not-at-lol).

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

---

## Runs

**Run** — one solve, archived under `run_archive/` with a manifest recording the
git commit, input hashes and headline KPIs.

**Run name** — what a run is filed under. A run given a name is filed under that
name alone, and re-running with the same name replaces it, so the name denotes a
*case* rather than an occasion. An unnamed run is filed under a timestamp
instead, and those accumulate.

**Input role** — what an input *is to the model* — plants, fuel, demand or
profiles — as distinct from the file that fills it. `inputs/` holds more than one
file for some roles, and a run picks one per role with `--plants`, `--fuel`,
`--demand` and `--profiles`. The archive is keyed by role, so runs using
different files stay comparable.

**Source** — in a manifest, the file that filled a role, recorded next to the
hash when it is not the role's plain name. Provenance, and the address a restore
writes back to.

**KPI** — a headline number stored in a run's manifest so that listing and diffing
never has to reopen the result CSVs. Note that the `production_cost` KPI is fuel
and VOM only and excludes ramp cost.

**Attribution** — the one-line verdict on *why* two runs differ, from comparing
their manifests: code identical and inputs changed, inputs identical and code
changed, both, or neither — in which case any difference is solver noise. It is
what makes a diff interpretable rather than just two columns of numbers.

**Objective reconciliation** — the check, run on every solve, that the four
reported cost components sum to what the solver actually minimised:

```
LP objective = production cost + ramp cost + unserved cost + spill cost
```

It is a test rather than a claim. If a cost is ever double counted or dropped from
a column, this is where it surfaces.
