# My first Dispatch Model

This repo provides the power market model and dashboard for the my first dispatch model onboarding.
Its purpose is to create a python PuLP linear optimisation model which determines the cheapest way to dispatch a set of power plants to meet electricity demand over a set of time periods.
It currently takes into account renewable intermittency and plant ramping constraints. 

## Quickstart

Needs **python 3.8**. Install the dependencies, which are pinned in
[requirements.txt](requirements.txt):

```
pip install -r requirements.txt
```

Then run it:

```
python run.py
```

Run the test suite from the repository root with:

```
python -m pytest
```

`run.py` is a short, editable script. The six constants at the top of it pick
the five input files and name the run:

```python
PLANTS = "plants_basic.csv"
FUEL = "fuel.csv"
DEMAND = "demand.csv"
PROFILES = "profiles_basic.csv"
BATTERY = "battery.csv"
OUTPUT_NAME = "output_basic"
```

It passes those five files to the model, solves, and then opens the dashboard on
the result. Change a constant and run it again to try another case:
`plants_ramping.csv` adds a ramp limit and `profiles_renewables.csv` adds hourly
wind and solar shapes, and the two are independent, so any of the four
combinations is a valid run. Give each case its own `OUTPUT_NAME` and you can
compare them in the dashboard or with `runs.py diff`.

A bare file name is looked for in `inputs/`. A value with a directory in it is
used as a path, so a file kept anywhere else works too.

The model writes CSVs into `results/`; the dashboard reads them. Ctrl-click the
http://127.0.0.1:8050 link the dashboard prints, and Ctrl-C to stop.

The two halves are still ordinary scripts, if you want one without the other:

```
python model/MFDM.py
python dashboard/dashboard.py
```

## What is in the repo

```
requirements.txt        pinned dependencies, python 3.8
run.py                  edit the constants, run it: solves, then opens the dashboard
inputs/                 the input CSVs, including alternatives to choose between
model/MFDM.py           the dispatch model, reads inputs/ and writes results/
results/                dispatch_results.csv, plant_summary.csv
dashboard/dashboard.py  Dash app for presenting and QA-ing results
run_archive/            past runs, one folder each
docs/                   the documents listed under Further reading
```

Every run archives itself under `run_archive/` unless you pass `--no-archive`.
A run given a name is filed under that name, so re-running with the same
`OUTPUT_NAME` replaces it and the name always points at the latest version of
that case. A run with no name is filed under a timestamp instead, and those
accumulate. `run_archive/runs.py` is the tool for working with the archive —
`list`, `show`, `diff`, `restore`, `prune`.

The archive files each input under its **role** — plants, fuel, demand,
profiles — rather than under its file name, so a run using `plants_ramping.csv`
is stored as `plants.csv` with `plants_ramping.csv` recorded as its source.
That is what lets `runs.py diff` compare a basic run against a ramping one cell
by cell. `runs.py show` prints the file each input came from, and `runs.py
restore` writes each one back to that same file.

## Running with options

```
python model/MFDM.py --plants plants_ramping.csv --label ramping
python model/MFDM.py --inputs <folder> --results <folder>
```

The four file flags choose which file fills each input role. `--inputs` and
`--results` move the folders instead: `--inputs` expects `plants.csv`,
`fuel.csv`, `demand.csv` and `profiles.csv` under exactly those names, which is
how the worked examples in the semantics document are run. The two compose, so a
file flag can override one role inside a custom folder.

A run over custom files or folders is archived like any other, because the paths
it used are recorded with it. Add `--no-archive` for a throwaway run you do not
want kept.

| Option | Effect |
|---|---|
| `--plants <file>` | File filling the plants role: a name inside the input folder, or a path |
| `--fuel <file>` | File filling the fuel role |
| `--demand <file>` | File filling the demand role |
| `--profiles <file>` | File filling the profiles role |
| `--battery <file>` | Optional file filling the battery role |
| `--no-battery` | Solve without battery storage, even if `battery.csv` exists |
| `--inputs <folder>` | Read the four input CSVs from `<folder>` instead of `inputs/` |
| `--results <folder>` | Write result CSVs to `<folder>` instead of `results/` |
| `--no-archive` | Solve and write results without archiving the run |
| `--label <name>` | Name for this run. Becomes the archive id, replacing any run of that name |
| `--notes <text>` | Longer description stored with the run |

## Two constants you will meet in the output

| Constant | Value | What it is |
|---|---:|---|
| `LoL` | $8,300/MWh | The cost of lost load — what unserved energy is priced at. Appears as $\text{LoL}$ in the objective below. |
| `SPILL_COST` | $1,000/MWh | What energy that is generated and thrown away is charged. Appears as $\text{SPILL}$ below. |

Both are set at the top of `model/MFDM.py`. Neither is a physical quantity.

`LoL` must stay well above the marginal cost of the most expensive plant. If it
drops below, the solver sheds load rather than running that plant, and nothing
errors — the dispatch just quietly goes dark in expensive hours. The $8,300/MWh
figure is the low end of the European Commission JRC estimate for Greece; see
`docs/research/scarcity_pricing.md`.

`docs/model_semantics.md` explains why `SPILL_COST` is $1,000/MWh and not `LoL`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Could not find input file: ...` | Running from the wrong directory, or an `--inputs` folder missing one of the four CSVs. Run from the repo root. |
| `WARNING: could not read git state` | `git` is not on PATH. The run still solves; pass `--no-archive` to skip archiving entirely. |
| Dashboard shows stale numbers | The model was rerun while the dashboard was open. Close it with Ctrl-C and restart it. |
| `Address already in use` on port 8050 | A previous dashboard is still running. Close it with Ctrl-C. |
| A negative clearing price | Not a bug. It means energy was spilled in that hour; see the semantics document. |

## Further reading

- Vocabulary, one entry per term: [CONTEXT.md](CONTEXT.md)
- What the model means — prices, the CSV contract, ramping, worked examples:
  [docs/model_semantics.md](docs/model_semantics.md)

## The model as maths

### Sets
- $P$ — power plants
- $T$ — hours, ascending and contiguous. The horizon does not wrap.
- $B$ — batteries
- Fuels

### Parameters
- $A(p,t)$ — availability, how much plant $p$ can supply in hour $t$ (MWh). Nameplate for thermal plants; nameplate scaled by an hourly capacity factor for wind and solar.
- $C(p)$ — marginal cost of 1 MWh from plant $p$ ($/MWh)
- $\eta(p)$ — efficiency (MWh/MWhTh)
- $\eta_r(p)$ — ramping efficiency, the efficiency while the plant is moving (MWh/MWhTh). Never better than $\eta(p)$.
- $R(p)$ — ramp rate, the most the plant may move between adjacent hours (MW/hr). Left blank in `plants.csv` the plant is unconstrained, moving freely and paying no premium, which is how every plant in `inputs/plants.csv` is currently set.
- $K(p)$ — ramp premium, the extra cost of a moved MWh over a steady one ($/MWh)
- $D(t)$ — demand in hour $t$ (MWh)
- $P(b)$ — battery charge and discharge power (MW)
- $E(b)$ — battery energy capacity (MWh)
- $n(b)$ — battery one-way efficiency

$$C(p) = \frac{\text{fuel price}(p)}{\eta(p)} + \text{VOM}(p)$$

$$K(p) = \frac{\text{fuel price}(p)}{\eta_r(p)} - \frac{\text{fuel price}(p)}{\eta(p)}$$

### Decision variables
- $g(p,t) \geq 0$ — MWh generated by plant $p$ in hour $t$
- $u(t) \geq 0$ — MWh of demand left unserved in hour $t$
- $s(t) \geq 0$ — MWh generated in hour $t$ and thrown away
- $V_{up}(p,t) \geq 0$ — upward movement by plant $p$ into hour $t$
- $V_{dwn}(p,t) \geq 0$ — downward movement by plant $p$ into hour $t$
- $C_c(b,t) \geq 0$ / $C_d(b,t) \geq 0$ — battery charge and discharge (MWh)
- $SoC(b,t) \geq 0$ — battery state of charge after hour $t$ (MWh)

### Objective function
Minimise the total cost of serving demand — production, ramping, lost load and spill.

$$\min \sum_{p,t} C(p)\, g(p,t) \;+\; \sum_{t} \text{LoL}\, u(t) \;+\; \sum_{t} \text{SPILL}\, s(t) \;+\; \sum_{p,t} K(p) \left( V_{up}(p,t) + V_{dwn}(p,t) \right)$$

Note this minimises **production cost**, not market cost. Minimising the clearing
price times demand would be a different problem, and a wrong one: it would ignore
the cost of ramping, lost load and spill.

### Constraints

Energy balance, one per hour. Spill enters negatively because it is generation
that did not serve demand:

$$\sum_{p} g(p,t) + \sum_b C_d(b,t) + u(t) - s(t) = D(t) + \sum_b C_c(b,t) \qquad \forall t$$

Capacity, one per plant per hour:

$$g(p,t) \leq A(p,t) \qquad \forall p, t$$

Ramping, one pair per plant per hour after the first. Hour 1 has no predecessor,
so no ramp constraint applies to it and plants start wherever they like free of
charge. Up and down are symmetric — neither direction gets an allowance:

$$g(p,t) - g(p,t-1) \leq V_{up}(p,t) \qquad \forall p,\ t > 1$$

$$g(p,t-1) - g(p,t) \leq V_{dwn}(p,t) \qquad \forall p,\ t > 1$$

Ramp rate limits, applied as upper bounds on the movement variables:

$$0 \leq V_{up}(p,t) \leq R(p), \qquad 0 \leq V_{dwn}(p,t) \leq R(p)$$

Battery storage, with the predecessor of the first hour defined as the last hour:

$$SoC(b,t) - SoC(b,(t-1)) = n(b)C_c(b,t) - \frac{C_d(b,t)}{n(b)} \qquad \forall b,t$$

$$0 \leq SoC(b,t) \leq E(b), \qquad C_c(b,t) + C_d(b,t) \leq P(b) \qquad \forall b,t$$

### Prices

The hourly clearing price is the **dual of the energy balance** — what one more
MWh of demand in that hour would cost the system.

Before ramping, every hour stood alone and this equalled the marginal cost of the
most expensive plant running, so the model reported the merit-order price and used
the dual as a cross-check. Ramping couples the hours, so an extra MWh in hour $t$
also changes what it costs to serve $t-1$ and $t+1$. The dual absorbs those ramp
shadow costs and stops equalling any plant's marginal cost. It can exceed every
offer in the stack, and in a spill hour it goes negative.

The old merit-order calculation is still reported, as `Highest Running Cost`. It
is a "who was last in the stack" diagnostic and not a price.

See [docs/model_semantics.md](docs/model_semantics.md) for the full reasoning
and two worked three-hour examples.
