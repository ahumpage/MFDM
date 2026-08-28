# What does "energy served" mean, and what divides the load-weighted price?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The Origin frames this as a bug: the archive and dashboard use total demand as energy
served, while the model uses `demand - unserved`. That is true, and worse than stated.
But before deciding where the arithmetic lives or what happens to old manifests, the
repo has to agree on **what the numbers mean**.

### What the audit found

Four implementations, and the Origin named two of them:

| Quantity | `MFDM.print_report` | `runstore.compute_kpis` | `dashboard.window_kpis` | `dashboard.build_kpis` |
|---|---|---|---|---|
| energy served | `total_demand - total_unserved` | `demand` | `demand` | `demand` |
| unserved | summed and printed | **not computed** | **not computed** | cost only, never MWh |
| load-weighted price | `market_cost / total_demand` | `market / demand` | `market / demand` | `market / demand` |

`dashboard.build_kpis` — the single-run KPI card strip, labelled "Energy served" — is a
third defective copy the Origin did not mention.

**The subtler finding is the bottom row.** `load_weighted_price` is `market / demand` in
*all four* places, including the one the Origin calls correct. So it is currently
**consistent**, and consistent with a defensible definition: `Market Cost ($)` is
constructed in `build_hourly_results` as `price x demand`, so `market / demand` is
arithmetically self-consistent. Changing the denominator to served energy without also
redefining the numerator would produce a number that is neither.

Which means `MFDM.print_report` is **internally inconsistent**: it prints energy served
as `demand - unserved`, and three lines later prints a load-weighted price and an average
production cost both divided by `demand`.

### What has to be decided

- **Energy served.** Presumably `demand - unserved`, since that is what the system
  physically delivered. Confirm it, and confirm the label "Energy served" is the right
  name for it.
- **Is `Market Cost = price x demand` right?** In a scarcity hour the price is VOLL and
  demand exceeds generation, so this charges the full demand at VOLL. That may be exactly
  right (it is the cost of the shortage to consumers) or it may be conflating consumer
  cost with generator revenue — which differ by exactly the unserved quantity.
- **What divides the load-weighted price** — and it must follow from the answer above,
  not be chosen independently. If the numerator stays `price x demand`, the denominator
  is demand. If the intent is a revenue-weighted price paid to generators, both change.
- **The same question for `avg_production_cost`**, which shares the denominator.
- **Does `unserved_mwh` become a reported quantity?** The Origin suggests it. It is
  currently absent from every KPI surface in the repo, so a scarce run is silent rather
  than visible.

Once these are settled, [One KPI implementation or four?](06-kpi-single-source.md) can
decide where they live and [What happens to the 22 manifests already
written?](07-manifest-compatibility.md) can decide what it costs.

## Decision

**Energy served is delivered energy:** `demand - unserved energy`. The label is
kept, and `unserved_mwh` becomes a headline KPI in manifests, single-run dashboard
cards and comparison cards. Results written before the unserved-energy column read
as zero unserved energy.

**Market Cost remains `clearing price x demand`.** In a scarcity hour it includes
the LoL cost of unmet demand. Therefore `load_weighted_price = market_cost / demand`;
changing only its denominator would produce a number with no defined numerator.

**Average production cost is production-weighted:**
`production_cost / total_generation`. Generated energy includes spill because it
incurred production cost. It is zero where no energy was generated.

**`Producer surplus` is retired in favour of `Market surplus`:**
`market_cost - production_cost`. The former name falsely implies generator earnings
when market cost includes the cost assigned to unserved demand. The new name is a
system-level market-minus-production measure.

New manifests write `market_surplus`. Readers accept the old `producer_surplus`
key as its predecessor so existing manifests keep displaying and diffing. Whether
to rewrite or version existing manifests remains the compatibility decision in
[What happens to the 22 manifests already written?](07-manifest-compatibility.md).
