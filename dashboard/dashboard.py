"""
Dispatch Model Dashboard
========================

An interactive Dash app for exploring the output of model/MFDM.py.

Run model/MFDM.py first to produce dispatch_results.csv and plant_summary.csv
in results/, then:

    python dashboard/dashboard.py

and open http://127.0.0.1:8050 in a browser.

Controls
    hour range slider   zoom to any window of hours
    preset buttons      first day, first week, full period
    resolution          hourly, daily mean or weekly mean
    plant toggles       show or hide each plant
    overlay toggles     demand line, marginal cost lines, shadow price

Note on the duration curves: they always use hourly data, because averaging
over days or weeks flattens the peaks that a duration curve exists to show.
"""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, callback_context, dash_table

# runstore lives in run_archive/, which is a sibling folder rather than a
# package, so it has to be put on the import path before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "run_archive"))
import runstore


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent          # dashboard/
REPO_ROOT = BASE_DIR.parent

# The live results the model most recently wrote.
RESULTS_DIR = REPO_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "dispatch_results.csv"
SUMMARY_FILE = RESULTS_DIR / "plant_summary.csv"

# Consistent colour per technology across every chart. Moved here from
# MFDM.py, which is now purely a solver.
TECH_COLOURS = {
    "Solar": "#E69F00",        # orange
    "Wind": "#56B4E9",         # sky blue
    "Coal": "#333333",         # near black
    "Gas": "#0072B2",          # blue
    "Diesel": "#D55E00",       # vermillion
    "Nuclear": "#CC79A7",      # reddish purple
    "Hydrogen": "#009E73",     # bluish green
}
FALLBACK_COLOURS = ["#F0E442", "#56B4E9", "#CC79A7", "#009E73", "#999999"]

# Semantic colours, also Okabe-Ito. Red and green are deliberately never used
# as a contrasting pair, since that is the hardest combination to tell apart
# under deuteranopia and protanopia.
C_PRICE = "#D55E00"            # vermillion
C_SHADOW = "#0072B2"           # blue
C_MARKET = "#D55E00"           # vermillion
C_PROD = "#009E73"             # bluish green
C_NEUTRAL = "#666666"          # difference line, deliberately unsaturated
C_DEMAND = "#000000"
C_PASS = "#009E73"
C_FAIL = "#D55E00"
C_PASS_BG = "#E8F6F1"
C_FAIL_BG = "#FDF0E7"

# Translucent fills derived from C_PRICE (#D55E00 = rgb(213, 94, 0)).
RGBA_PRICE_FILL = "rgba(213, 94, 0, 0.15)"
RGBA_PRICE_AREA = "rgba(213, 94, 0, 0.20)"

DEMAND_COL = "Demand (MWh)"
PRICE_COL = "Clearing Price ($/MWh)"
SHADOW_COL = "Shadow Price ($/MWh)"
PROD_COST_COL = "Production Cost ($)"
MARKET_COST_COL = "Market Cost ($)"
UNSERVED_COL = "Unserved Energy (MWh)"

HOURS_PER_DAY = 24
HOURS_PER_WEEK = 168

# Above this many periods the stacked bars become too thin to read, so the
# dispatch chart falls back to a filled area. The active mode is named in the
# chart title so the switch is never silent.
BAR_THRESHOLD = 200

PLOT_BG = "#FFFFFF"
GRID = "#E6E6E6"


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def lighten(hex_colour, amount):
    """Blend a hex colour towards white. amount 0 returns it unchanged, 1
    returns white. Used to separate several plants of the same technology
    while keeping them recognisably related."""
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    blended = [int(round(c + (255 - c) * amount)) for c in rgb]
    return "#{:02X}{:02X}{:02X}".format(*blended)


class Run(object):
    """One set of model results, either the live working folder or an
    archived run. Everything the figures need travels on this object rather
    than in module globals, so the dashboard can switch between runs."""

    def __init__(self, run_id, label, results, summary, manifest=None):
        self.id = run_id
        self.label = label
        self.manifest = manifest
        self.results = results

        # Plant order, colours and reference values all come from the summary
        # file, so adding a plant to plants.csv flows through with no edits.
        self.summary = summary.sort_values(
            "Marginal Cost ($/MWh)").reset_index(drop=True)
        self.plant_order = list(self.summary["Plant"])
        self.meta = self._build_meta()

        self.hour_min = int(results["Hour"].min())
        self.hour_max = int(results["Hour"].max())
        self.has_shadow = SHADOW_COL in results.columns

    def _build_meta(self):
        meta = {}
        seen_tech = {}
        for i, row in self.summary.iterrows():
            tech = row["Technology"]

            # A fleet can hold several plants of the same technology, for
            # example a mid-merit gas plant and a gas peaker. They must not
            # share a colour or they are indistinguishable in the stack, so
            # repeats are shaded progressively lighter while staying
            # recognisably that technology.
            #
            # Colour is keyed on technology and merit position within that
            # technology, so it is stable for a given fleet. Comparing runs
            # with different fleets can still shift a colour, which is why
            # the comparison charts label rather than rely on colour.
            n_seen = seen_tech.get(tech, 0)
            seen_tech[tech] = n_seen + 1
            base = TECH_COLOURS.get(tech, FALLBACK_COLOURS[i % len(FALLBACK_COLOURS)])
            colour = base if n_seen == 0 else lighten(base, min(0.30 * n_seen, 0.75))

            avail_col = "{} Available (MWh)".format(row["Plant"])
            meta[row["Plant"]] = {
                "technology": tech,
                "fuel": row["Fuel"],
                "capacity": float(row["Capacity (MW)"]),
                "marginal_cost": float(row["Marginal Cost ($/MWh)"]),
                "profiled": (bool(row["Profiled"])
                             if "Profiled" in self.summary.columns else False),
                "colour": colour,
                "column": "{} (MWh)".format(row["Plant"]),
                # Hourly limit. Falls back to nameplate for older results
                # files that predate the availability columns.
                "avail_column": (avail_col if avail_col in self.results.columns
                                 else None),
            }
        return meta

    @property
    def name(self):
        if self.id == CURRENT_ID:
            return "current (working folder)"
        return "{}{}".format(self.id, "  -  " + self.label if self.label else "")


CURRENT_ID = "__current__"


def load_current():
    """The live CSVs sitting in the working folder."""
    missing = [f.name for f in (RESULTS_FILE, SUMMARY_FILE) if not f.exists()]
    if missing:
        raise SystemExit(
            "ERROR: missing {}.\n"
            "Run model/MFDM.py first to generate dispatch_results.csv and "
            "plant_summary.csv.".format(" and ".join(missing))
        )
    return Run(CURRENT_ID, None,
               pd.read_csv(RESULTS_FILE),
               pd.read_csv(SUMMARY_FILE, keep_default_na=False))


_RUN_CACHE = {}


def get_run(run_id):
    """Load a run by id, caching it. Archived runs never change once written,
    but the working folder does, so 'current' is always re-read."""
    if run_id in (None, "", CURRENT_ID):
        return load_current()
    if run_id not in _RUN_CACHE:
        manifest = runstore.get_manifest(run_id)
        results, summary = runstore.load_results(run_id)
        _RUN_CACHE[run_id] = Run(run_id, manifest.get("label"),
                                 results, summary, manifest)
    return _RUN_CACHE[run_id]


def run_options():
    """Dropdown entries: the working folder first, then archived runs."""
    options = [{"label": "current (working folder)", "value": CURRENT_ID}]
    for m in runstore.list_runs():
        label = m["id"]
        if m.get("label"):
            label = "{}  -  {}".format(m["id"], m["label"])
        options.append({"label": label, "value": m["id"]})
    return options



# --------------------------------------------------------------------------
# Filtering and aggregation
# --------------------------------------------------------------------------

def slice_hours(run, lo, hi):
    """Rows within the selected hour window, always at hourly resolution."""
    mask = (run.results["Hour"] >= lo) & (run.results["Hour"] <= hi)
    return run.results.loc[mask].copy()


def aggregate(run, df, resolution):
    """Aggregate to daily or weekly buckets.

    Generation, demand and costs are summed, because they are energy and
    money and must add up. Price is averaged load-weighted, since that is
    what is actually paid; a plain time-weighted mean would understate the
    cost of expensive peak hours.
    """
    if resolution == "hourly" or df.empty:
        out = df.copy()
        out["x"] = out["Hour"]
        out["Periods"] = 1
        return out

    step = HOURS_PER_DAY if resolution == "daily" else HOURS_PER_WEEK
    df = df.copy()
    # Bucket by absolute hour so buckets stay aligned as the window moves.
    df["bucket"] = (df["Hour"] - 1) // step

    sum_cols = [run.meta[p]["column"] for p in run.plant_order]
    sum_cols += [DEMAND_COL, PROD_COST_COL, MARKET_COST_COL]
    sum_cols = [c for c in sum_cols if c in df.columns]

    grouped = df.groupby("bucket")
    out = grouped[sum_cols].sum()
    out["Hour"] = grouped["Hour"].min()
    out["Periods"] = grouped.size()

    # Load-weighted average price over the bucket.
    out[PRICE_COL] = grouped.apply(
        lambda g: (g[PRICE_COL] * g[DEMAND_COL]).sum() / g[DEMAND_COL].sum()
        if g[DEMAND_COL].sum() > 0 else 0.0
    )
    if run.has_shadow:
        out[SHADOW_COL] = grouped.apply(
            lambda g: (g[SHADOW_COL] * g[DEMAND_COL]).sum() / g[DEMAND_COL].sum()
            if g[DEMAND_COL].sum() > 0 else 0.0
        )

    out = out.reset_index()
    # Label buckets by their day or week number rather than raw hour.
    out["x"] = out["bucket"] + 1
    return out


def axis_label(resolution):
    return {"hourly": "Hour", "daily": "Day", "weekly": "Week"}[resolution]


def energy_label(resolution):
    return "Generation (MWh)" if resolution == "hourly" else "Energy (MWh per {})".format(
        {"daily": "day", "weekly": "week"}[resolution])


def base_layout(fig, title, xlabel, ylabel, y2label=None, height=470):
    # The top margin has to hold the title and the horizontal legend in
    # separate bands. At t=50 they collided and the legend covered the title.
    top = 95
    fig.update_layout(
        title=dict(text=title, x=0.01, y=0.97, yanchor="top", yref="container",
                   font=dict(size=15)),
        xaxis_title=xlabel,
        yaxis_title=ylabel,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PLOT_BG,
        margin=dict(l=60, r=30, t=top, b=45),
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)

    if y2label is not None:
        # Grid off on the right axis so it does not cross-hatch the stack.
        # rangemode="tozero" keeps the line's height honestly comparable
        # between windows. Note this re-specifies margin, so it must carry
        # the same top value or the title would be covered again.
        fig.update_layout(
            yaxis2=dict(title=y2label, overlaying="y", side="right",
                        showgrid=False, zeroline=False, rangemode="tozero"),
            margin=dict(l=60, r=65, t=top, b=45),
        )
    return fig


def empty_figure(message):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False,
                       xref="paper", yref="paper", x=0.5, y=0.5,
                       font=dict(size=14, color="#888"))
    # Same height as base_layout so cards do not jump when a range is empty.
    fig.update_layout(plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG, height=470,
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def fig_dispatch(run, agg, plants, overlays, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    xlab = axis_label(resolution)

    # Stacked bars are honest about the data being discrete periods, but below
    # about 2px wide they stop being readable, so wide windows fall back to a
    # filled area. The mode is named in the title so the switch is not silent.
    n_periods = len(agg)
    use_bars = n_periods <= BAR_THRESHOLD

    # Stack cheapest first so the chart reads as a merit order.
    for p in run.plant_order:
        if p not in plants:
            continue
        m = run.meta[p]
        name = "{} ({}) ${:.2f}/MWh".format(p, m["technology"], m["marginal_cost"])
        hover = "%{y:,.1f} MWh<extra>" + p + "</extra>"

        if use_bars:
            fig.add_trace(go.Bar(
                x=agg["x"], y=agg[m["column"]],
                name=name, marker_color=m["colour"],
                marker_line_width=0,
                hovertemplate=hover,
            ))
        else:
            fig.add_trace(go.Scatter(
                x=agg["x"], y=agg[m["column"]],
                name=name, mode="lines",
                line=dict(width=0.5, color=m["colour"]),
                fillcolor=m["colour"],
                stackgroup="one",
                hovertemplate=hover,
            ))

    if use_bars:
        # bargap=0 so the periods butt up against each other with no stripes.
        fig.update_layout(barmode="stack", bargap=0)

    if "demand" in overlays:
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[DEMAND_COL],
            name="Demand", mode="lines",
            line=dict(color=C_DEMAND, width=1.6, dash="dash"),
            hovertemplate="%{y:,.1f} MWh<extra>Demand</extra>",
        ))

    # Clearing price on a right-hand axis. Generation runs to ~764 MWh and
    # price only to $41.60, so they cannot share an axis meaningfully.
    y2label = None
    if "price" in overlays:
        # "hvh" rather than "hv": the step must be centred on the hour so it
        # lines up with the bar for that hour. A bar at x spans x-0.5 to x+0.5
        # (bargap=0), so the price riser has to sit on the bar edge at x+0.5,
        # which is where "hvh" puts it. "hv" starts the run at x instead, so
        # every price segment sat half a bar to the right of the hour it
        # describes.
        shape = "hvh" if resolution == "hourly" else "linear"
        price_name = ("Clearing price" if resolution == "hourly"
                      else "Load-weighted avg price")
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[PRICE_COL],
            name=price_name, mode="lines", yaxis="y2",
            line=dict(color=C_PRICE, width=1.8, shape=shape),
            hovertemplate="$%{y:,.2f}/MWh<extra>" + price_name + "</extra>",
        ))
        y2label = "Price ($/MWh)"

    title = "Dispatch by plant ({})".format(
        "stacked bars" if use_bars else "area, {:,} periods".format(n_periods))
    return base_layout(fig, title, xlab,
                       energy_label(resolution), y2label=y2label)


def fig_price(run, agg, overlays, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    # Price is piecewise constant at hourly resolution, so draw it as a step.
    # "hvh" centres each flat run on its hour, matching the dispatch bars.
    # Once averaged it is no longer a step function, so use a plain line.
    shape = "hvh" if resolution == "hourly" else "linear"

    fig.add_trace(go.Scatter(
        x=agg["x"], y=agg[PRICE_COL],
        name="Clearing price", mode="lines",
        line=dict(color=C_PRICE, width=1.8, shape=shape),
        hovertemplate="$%{y:,.2f}/MWh<extra>Clearing price</extra>",
    ))

    if "shadow" in overlays and run.has_shadow:
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[SHADOW_COL],
            name="Shadow price (dual)", mode="lines",
            line=dict(color=C_SHADOW, width=1.2, dash="dot", shape=shape),
            hovertemplate="$%{y:,.2f}/MWh<extra>Shadow price</extra>",
        ))

    if "mclines" in overlays:
        for p in run.plant_order:
            m = run.meta[p]
            fig.add_hline(
                y=m["marginal_cost"], line=dict(color=m["colour"], width=1, dash="dot"),
                annotation_text="{} ${:.2f}".format(p, m["marginal_cost"]),
                annotation_position="right",
                annotation_font=dict(size=10, color=m["colour"]),
            )

    ylab = ("Clearing price ($/MWh)" if resolution == "hourly"
            else "Load-weighted avg price ($/MWh)")
    return base_layout(fig, "Market clearing price", axis_label(resolution), ylab)


def fig_costs(run, agg, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agg["x"], y=agg[MARKET_COST_COL],
        name="Market cost (price x demand)", mode="lines",
        line=dict(color=C_MARKET, width=1.6),
        hovertemplate="$%{y:,.0f}<extra>Market cost</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=agg["x"], y=agg[PROD_COST_COL],
        name="Production cost (LP objective)", mode="lines",
        # Dashed as well as differently coloured, so the two lines stay
        # distinguishable without relying on colour at all.
        line=dict(color=C_PROD, width=1.6, dash="dash"),
        fill="tonexty", fillcolor=RGBA_PRICE_FILL,
        hovertemplate="$%{y:,.0f}<extra>Production cost</extra>",
    ))
    return base_layout(fig, "Cost per period - shaded area is producer surplus",
                       axis_label(resolution), "Cost ($)")


def fig_price_duration(run, hourly):
    if hourly.empty:
        return empty_figure("No hours in the selected range")

    prices = hourly[PRICE_COL].sort_values(ascending=False).values
    pct = [100.0 * (i + 1) / len(prices) for i in range(len(prices))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pct, y=prices, mode="lines", name="Price",
        line=dict(color=C_PRICE, width=2, shape="hv"),
        fill="tozeroy", fillcolor=RGBA_PRICE_AREA,
        hovertemplate="$%{y:,.2f}/MWh at %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(showlegend=False)
    return base_layout(fig, "Price duration curve (hourly)",
                       "Percent of hours (%)", "Clearing price ($/MWh)")


def fig_load_duration(run, hourly, plants):
    if hourly.empty:
        return empty_figure("No hours in the selected range")

    loads = hourly[DEMAND_COL].sort_values(ascending=False).values
    pct = [100.0 * (i + 1) / len(loads) for i in range(len(loads))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pct, y=loads, mode="lines", name="Demand",
        line=dict(color="black", width=2),
        hovertemplate="%{y:,.1f} MWh at %{x:.1f}%<extra></extra>",
    ))

    # Cumulative capacity of the selected plants, in merit order. Where the
    # demand curve crosses a line is where the marginal plant changes, so this
    # should agree with the price duration curve.
    cumulative = 0.0
    for p in run.plant_order:
        if p not in plants:
            continue
        cumulative += run.meta[p]["capacity"]
        fig.add_hline(
            y=cumulative, line=dict(color=run.meta[p]["colour"], width=1.4, dash="dash"),
            annotation_text="through {} = {:,.0f} MW".format(p, cumulative),
            annotation_position="right",
            annotation_font=dict(size=10, color=run.meta[p]["colour"]),
        )

    fig.update_layout(showlegend=False)
    return base_layout(fig, "Load duration curve vs cumulative capacity (hourly)",
                       "Percent of hours (%)", "Demand (MWh)")


def fig_energy_mix(run, hourly, plants):
    if hourly.empty or not plants:
        return empty_figure("No plants selected")

    n_hours = len(hourly)
    total_demand = hourly[DEMAND_COL].sum()

    names, values, colours, labels = [], [], [], []
    for p in run.plant_order:
        if p not in plants:
            continue
        m = run.meta[p]
        total = hourly[m["column"]].sum()
        cf = 100.0 * total / (m["capacity"] * n_hours) if n_hours else 0.0
        share = 100.0 * total / total_demand if total_demand else 0.0
        names.append(p)
        values.append(total)
        colours.append(m["colour"])
        labels.append("CF {:.1f}%<br>{:.1f}% of demand".format(cf, share))

    fig = go.Figure(go.Bar(
        x=names, y=values, marker_color=colours,
        text=labels, textposition="outside",
        hovertemplate="%{y:,.1f} MWh<extra>%{x}</extra>",
    ))
    fig.update_layout(showlegend=False)
    fig.update_yaxes(rangemode="tozero")
    fig = base_layout(fig, "Energy mix over the selected window",
                      "", "Total generation (MWh)")
    if values:
        fig.update_yaxes(range=[0, max(values) * 1.25])
    return fig


# --------------------------------------------------------------------------
# QA - LP optimality checks
# --------------------------------------------------------------------------
#
# For a least-cost LP with only an energy balance and capacity limits, the
# optimal solution must satisfy these conditions in every hour, where P is the
# clearing price and MC is a plant's marginal cost:
#
#   part loaded (0 < gen < capacity)   MC == P    the plant is marginal
#   at capacity (gen >= capacity)      MC <= P    inframarginal, earns rent
#   idle        (gen <= 0)             MC >= P    too expensive to run
#
# A violation means the dispatch is not least cost, which points at a bug in
# the model rather than at the data. These identities hold exactly for the
# current model; they start to bind once minimum generation levels, ramp
# rates, unit commitment or storage are added.
#
# One thing generating in an hour is not a plant: unserved energy, priced at
# VoLL. In an hour with a shortfall it is the marginal unit and sets the
# price, so every plant should be at capacity and the price will match no
# plant's marginal cost. That is correct, not unexplained.

QA_TOL = 1e-4          # $/MWh and MWh tolerance for declaring a violation
MAX_VIOLATION_ROWS = 100

STATE_PART = "Part loaded"
STATE_FULL = "At capacity"
STATE_IDLE = "Idle"
STATE_UNAVAIL = "No resource"
STATE_COLOURS = {STATE_PART: C_PRICE, STATE_FULL: C_SHADOW,
                 STATE_IDLE: "#BDC3C7", STATE_UNAVAIL: "#EAECEE"}


def run_qa(run, hourly):
    """Run the LP optimality checks over the selected hours.

    Always uses hourly data: violations are per-hour events and averaging
    would hide them. Returns a dict of counts, per-plant states and the
    offending rows.
    """
    out = {
        "n_hours": len(hourly),
        "price_mismatch": 0,
        "max_price_diff": 0.0,
        "unexplained_price": 0,
        "violations": [],
        "n_violations": 0,
        "states": {},
        "rents": {},
        "total_rent": 0.0,
        "ok": True,
    }
    if hourly.empty:
        return out

    price = hourly[PRICE_COL]

    # --- check 1: clearing price vs shadow price (the LP dual) ---
    if run.has_shadow:
        diff = (price - hourly[SHADOW_COL]).abs()
        out["max_price_diff"] = float(diff.max())
        out["price_mismatch"] = int((diff > QA_TOL).sum())

    # --- check 3: does every price correspond to some plant? ---
    # Except in an hour with unserved energy, where the marginal MWh is not
    # supplied by any plant but shed, and lost load sets the price at VoLL.
    # Those hours are detected from the data rather than by comparing against
    # a hardcoded VoLL, so the figure cannot drift from the model's constant.
    mcs = [round(run.meta[p]["marginal_cost"], 6) for p in run.plant_order]
    if UNSERVED_COL in hourly.columns:
        scarce = hourly[UNSERVED_COL] > QA_TOL
    else:
        scarce = pd.Series(False, index=hourly.index)
    out["unexplained_price"] = int((~price.round(6).isin(mcs) & ~scarce).sum())

    # --- check 2: per plant-hour optimality conditions ---
    for p in run.plant_order:
        m = run.meta[p]
        gen = hourly[m["column"]]
        mc = m["marginal_cost"]

        # The binding limit is the hourly availability, not nameplate. A wind
        # farm running at its resource limit is at capacity and earns rent,
        # even though it may be at 20% of nameplate. Judging it against
        # nameplate would wrongly call it part loaded and demand that it set
        # the price.
        if m["avail_column"]:
            cap = hourly[m["avail_column"]]
        else:
            cap = pd.Series(m["capacity"], index=hourly.index)

        part = (gen > QA_TOL) & (gen < cap - QA_TOL)
        full = gen >= cap - QA_TOL
        idle = gen <= QA_TOL

        # An hour with no resource at all (night-time solar) is neither idle
        # by choice nor at capacity in any meaningful sense; it is unavailable.
        unavailable = cap <= QA_TOL
        idle = idle & ~unavailable
        full = full & ~unavailable

        out["states"][p] = {
            STATE_PART: int(part.sum()),
            STATE_FULL: int(full.sum()),
            STATE_IDLE: int(idle.sum()),
            STATE_UNAVAIL: int(unavailable.sum()),
        }
        # Inframarginal rent: what the plant earns above its own running cost.
        out["rents"][p] = float(((price - mc) * gen).sum())

        bad_part = part & ((mc - price).abs() > QA_TOL)
        bad_full = full & (mc > price + QA_TOL)
        bad_idle = idle & (mc < price - QA_TOL)

        for mask, state, rule in (
            (bad_part, STATE_PART, "part loaded so MC should equal price"),
            (bad_full, STATE_FULL, "at capacity so MC should be <= price"),
            (bad_idle, STATE_IDLE, "idle so MC should be >= price"),
        ):
            if not mask.any():
                continue
            for idx, row in hourly.loc[mask].iterrows():
                out["violations"].append({
                    "Hour": int(row["Hour"]),
                    "Plant": p,
                    "State": state,
                    "Generation (MWh)": round(float(row[m["column"]]), 3),
                    "Available (MW)": round(float(cap.loc[idx]), 3),
                    "Nameplate (MW)": m["capacity"],
                    "Marginal Cost ($/MWh)": mc,
                    "Clearing Price ($/MWh)": round(float(row[PRICE_COL]), 4),
                    "Failed rule": rule,
                })

    out["total_rent"] = float(sum(out["rents"].values()))
    out["n_violations"] = len(out["violations"])
    out["violations"].sort(key=lambda r: (r["Hour"], r["Plant"]))
    out["ok"] = (out["n_violations"] == 0
                 and out["price_mismatch"] == 0
                 and out["unexplained_price"] == 0)
    return out


def qa_banner(qa):
    """Green pass banner, or a red banner listing each failing check."""
    if qa["n_hours"] == 0:
        return html.Div("No hours in the selected range.",
                        style={"padding": "10px 12px", "backgroundColor": "#F4F5F7",
                               "border": "1px solid #E0E0E0", "borderRadius": "5px",
                               "fontSize": "13px", "color": "#666"})

    checks = [
        ("Clearing price equals shadow price (LP dual)",
         qa["price_mismatch"], "{} of {} hours differ (max ${:.2e}/MWh)".format(
             qa["price_mismatch"], qa["n_hours"], qa["max_price_diff"])),
        ("Every plant-hour satisfies LP optimality",
         qa["n_violations"], "{} violating plant-hours".format(qa["n_violations"])),
        ("Every price equals some plant's marginal cost",
         qa["unexplained_price"], "{} unexplained hours".format(qa["unexplained_price"])),
    ]

    rows = []
    for label, count, detail in checks:
        passed = count == 0
        rows.append(html.Div([
            html.Span("PASS" if passed else "FAIL", style={
                "fontWeight": "700", "fontSize": "11px", "marginRight": "8px",
                "color": "#FFFFFF", "padding": "1px 6px", "borderRadius": "3px",
                "backgroundColor": C_PASS if passed else C_FAIL}),
            html.Span(label, style={"fontSize": "13px"}),
            html.Span(" - " + detail, style={"fontSize": "12px", "color": "#777"}),
        ], style={"marginBottom": "5px"}))

    ok = qa["ok"]
    header = ("All QA checks passed over {:,} hours".format(qa["n_hours"]) if ok
              else "QA found problems over {:,} hours".format(qa["n_hours"]))

    return html.Div([
        html.Div(header, style={"fontWeight": "700", "fontSize": "14px",
                                "marginBottom": "8px",
                                "color": C_PASS if ok else C_FAIL}),
        html.Div(rows),
        html.Div(
            "Note: with only balance and capacity constraints these identities hold "
            "exactly, so an all-pass result is expected. The checks start to earn "
            "their keep once minimum generation, ramp rates, unit commitment or "
            "storage are added.",
            style={"fontSize": "11px", "color": "#888", "fontStyle": "italic",
                   "marginTop": "8px"}),
    ], style={
        "padding": "12px 14px", "borderRadius": "5px",
        "backgroundColor": C_PASS_BG if ok else C_FAIL_BG,
        "border": "1px solid {}".format(C_PASS if ok else C_FAIL),
    })


def fig_qa_price(run, hourly):
    """Clearing price against the LP dual, with their difference on the right
    axis. On a correct model the difference line sits flat on zero."""
    if hourly.empty:
        return empty_figure("No hours in the selected range")
    if not run.has_shadow:
        return empty_figure("No shadow price column in dispatch_results.csv")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=hourly[PRICE_COL],
        name="Clearing price (merit order)", mode="lines",
        line=dict(color=C_PRICE, width=2.4, shape="hv"),
        hovertemplate="$%{y:,.2f}/MWh<extra>Clearing</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=hourly[SHADOW_COL],
        name="Shadow price (LP dual)", mode="lines",
        line=dict(color=C_SHADOW, width=1.2, dash="dot", shape="hv"),
        hovertemplate="$%{y:,.2f}/MWh<extra>Shadow</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=(hourly[PRICE_COL] - hourly[SHADOW_COL]),
        name="Difference", mode="lines", yaxis="y2",
        line=dict(color=C_NEUTRAL, width=1.2),
        hovertemplate="$%{y:.2e}/MWh<extra>Difference</extra>",
    ))

    return base_layout(fig, "QA: clearing price vs shadow price",
                       "Hour", "Price ($/MWh)", y2label="Difference ($/MWh)")


def fig_qa_states(run, qa):
    """Hours each plant spends part loaded, at capacity and idle.

    The part-loaded count should equal the plant's price-setting hours,
    because the marginal plant is by definition the part-loaded one.
    """
    if not qa["states"]:
        return empty_figure("No hours in the selected range")

    plants = [p for p in run.plant_order if p in qa["states"]]
    fig = go.Figure()
    for state in (STATE_PART, STATE_FULL, STATE_IDLE, STATE_UNAVAIL):
        values = [qa["states"][p].get(state, 0) for p in plants]
        if not any(values):
            continue
        fig.add_trace(go.Bar(
            name=state, x=plants, y=values,
            marker_color=STATE_COLOURS[state],
            hovertemplate="%{y} h " + state + "<extra>%{x}</extra>",
        ))

    # Annotate each plant with its marginal cost and inframarginal rent.
    for p in plants:
        total = sum(qa["states"][p].values())
        fig.add_annotation(
            x=p, y=total, yshift=8, showarrow=False,
            text="MC ${:.2f}<br>rent ${:,.0f}".format(
                run.meta[p]["marginal_cost"], qa["rents"][p]),
            font=dict(size=10, color="#555"),
        )

    fig.update_layout(barmode="stack")
    fig = base_layout(fig, "QA: plant state by hour (part loaded = price setting)",
                      "", "Hours")
    # Headroom so the per-plant annotations sitting on top of each bar do not
    # clip against the legend.
    tallest = max((sum(qa["states"][p].values()) for p in plants), default=0)
    fig.update_yaxes(rangemode="tozero",
                     range=[0, tallest * 1.12] if tallest else None)
    return fig


def qa_violations_table(qa):
    """Table of offending plant-hours. Hidden entirely when there are none."""
    if qa["n_violations"] == 0:
        return html.Div()

    rows = qa["violations"][:MAX_VIOLATION_ROWS]
    note = ""
    if qa["n_violations"] > MAX_VIOLATION_ROWS:
        note = " Showing the first {} of {}.".format(MAX_VIOLATION_ROWS,
                                                     qa["n_violations"])

    return html.Div([
        html.Div("Optimality violations" + note,
                 style={"fontWeight": "600", "fontSize": "13px",
                        "margin": "14px 0 6px 0", "color": C_FAIL}),
        dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in rows[0].keys()],
            page_size=15,
            style_table={"overflowX": "auto"},
            style_cell={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
                        "fontSize": "12px", "padding": "6px",
                        "textAlign": "left"},
            style_header={"backgroundColor": "#F4F5F7", "fontWeight": "600"},
        ),
    ])


# --------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------

def kpi_card(label, value, sub=""):
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#666",
                               "textTransform": "uppercase", "letterSpacing": "0.5px"}),
        html.Div(value, style={"fontSize": "21px", "fontWeight": "600",
                               "color": "#1a1a1a", "marginTop": "3px"}),
        html.Div(sub, style={"fontSize": "11px", "color": "#888", "marginTop": "2px"}),
    ], style={
        "flex": "1", "minWidth": "150px", "padding": "12px 14px",
        "backgroundColor": "#FFFFFF", "border": "1px solid #E0E0E0",
        "borderRadius": "6px",
    })


def build_kpis(run, hourly):
    if hourly.empty:
        return [kpi_card("No data", "-")]

    demand = hourly[DEMAND_COL].sum()
    prod = hourly[PROD_COST_COL].sum()
    market = hourly[MARKET_COST_COL].sum()

    return [
        kpi_card("Hours", "{:,}".format(len(hourly)),
                 "hour {:,} to {:,}".format(int(hourly["Hour"].min()),
                                            int(hourly["Hour"].max()))),
        kpi_card("Energy served", "{:,.0f} MWh".format(demand)),
        kpi_card("Production cost", "${:,.0f}".format(prod), "the LP objective"),
        kpi_card("Market cost", "${:,.0f}".format(market), "price x demand"),
        kpi_card("Avg production cost", "${:,.2f}/MWh".format(prod / demand if demand else 0)),
        kpi_card("Load-weighted price", "${:,.2f}/MWh".format(market / demand if demand else 0)),
        kpi_card("Producer surplus", "${:,.0f}".format(market - prod), "market - production"),
    ]


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

app = Dash(__name__)
app.title = "Dispatch Model Dashboard"

CARD = {"backgroundColor": "#FFFFFF", "border": "1px solid #E0E0E0",
        "borderRadius": "6px", "padding": "14px", "marginBottom": "14px"}


def hour_marks(lo, hi):
    """Slider ticks that stay readable whatever the run's hour range."""
    span = max(hi - lo, 1)
    step = max(int(round(span / 10.0)), 1)
    marks = {h: str(h) for h in range(lo, hi + 1, step)}
    marks[lo] = str(lo)
    marks[hi] = str(hi)
    return marks


def plant_options(run, extra_run=None):
    """Checklist entries for a run's fleet.

    When comparing, the union of both fleets is offered so a plant present in
    only one run can still be shown; it simply contributes nothing to the run
    that lacks it.
    """
    entries = []
    seen = set()
    for source in (run, extra_run):
        if source is None:
            continue
        for p in source.plant_order:
            if p in seen:
                continue
            seen.add(p)
            m = source.meta[p]
            only = "" if (extra_run is None or p in run.meta) else "  (B only)"
            entries.append({
                "label": " {} ({}) ${:.2f}/MWh{}".format(
                    p, m["technology"], m["marginal_cost"], only),
                "value": p,
            })
    return entries


INITIAL_RUN = load_current()

app.layout = html.Div([
    html.Div([
        html.H2("Dispatch Model Dashboard",
                style={"margin": "0 0 2px 0", "fontSize": "23px"}),
        html.Div("Least-cost economic dispatch - results from MFDM.py",
                 style={"color": "#666", "fontSize": "13px"}),
    ], style={"marginBottom": "14px"}),

    # ---- run selection ----
    html.Div([
        html.Div([
            html.Div([
                html.Label("Run", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Dropdown(id="run-select", options=run_options(),
                             value=CURRENT_ID, clearable=False,
                             style={"marginTop": "6px"}),
            ], style={"flex": "2", "minWidth": "300px"}),
            html.Div([
                html.Label("Compare with",
                           style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Dropdown(id="run-compare", options=[], value=None,
                             placeholder="none", clearable=True,
                             style={"marginTop": "6px"}),
            ], style={"flex": "2", "minWidth": "300px"}),
            html.Div([
                html.Label("\u00a0", style={"fontSize": "13px"}),
                html.Button("Refresh run list", id="run-refresh", n_clicks=0,
                            style={"marginTop": "6px", "display": "block"}),
            ], style={"flex": "1", "minWidth": "150px"}),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap",
                  "alignItems": "flex-start"}),
        html.Div(id="run-info", style={"fontSize": "12px", "color": "#666",
                                       "marginTop": "10px"}),
    ], style=CARD),

    html.Div(id="kpi-row", style={"display": "flex", "gap": "10px",
                                  "flexWrap": "wrap", "marginBottom": "14px"}),

    # ---- controls ----
    html.Div([
        html.Div([
            html.Div([
                html.Label("Hour range", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.RangeSlider(
                    id="hour-range",
                    min=INITIAL_RUN.hour_min, max=INITIAL_RUN.hour_max, step=1,
                    value=[INITIAL_RUN.hour_min, INITIAL_RUN.hour_max],
                    marks=hour_marks(INITIAL_RUN.hour_min, INITIAL_RUN.hour_max),
                    tooltip={"placement": "bottom", "always_visible": False},
                    allowCross=False,
                ),
            ], style={"flex": "3", "minWidth": "320px"}),

            html.Div([
                html.Label("Presets", style={"fontWeight": "600", "fontSize": "13px"}),
                html.Div([
                    html.Button("First day", id="preset-day", n_clicks=0),
                    html.Button("First week", id="preset-week", n_clicks=0),
                    html.Button("Full period", id="preset-all", n_clicks=0),
                ], style={"display": "flex", "gap": "6px", "marginTop": "6px"}),
            ], style={"flex": "1", "minWidth": "230px"}),

            html.Div([
                html.Label("Resolution", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Dropdown(
                    id="resolution",
                    options=[
                        {"label": "Hourly", "value": "hourly"},
                        {"label": "Daily mean", "value": "daily"},
                        {"label": "Weekly mean", "value": "weekly"},
                    ],
                    value="hourly", clearable=False,
                    style={"marginTop": "6px"},
                ),
            ], style={"flex": "1", "minWidth": "170px"}),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap",
                  "alignItems": "flex-start"}),

        html.Hr(style={"border": "none", "borderTop": "1px solid #EEE",
                       "margin": "14px 0 10px 0"}),

        html.Div([
            html.Div([
                html.Label("Plants", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Checklist(
                    id="plant-toggle",
                    options=plant_options(INITIAL_RUN),
                    value=list(INITIAL_RUN.plant_order),
                    labelStyle={"display": "inline-block", "marginRight": "16px",
                                "fontSize": "13px"},
                    style={"marginTop": "6px"},
                ),
            ], style={"flex": "2", "minWidth": "320px"}),

            html.Div([
                html.Label("Overlays", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Checklist(
                    id="overlay-toggle",
                    options=[
                        {"label": " Demand line", "value": "demand"},
                        {"label": " Clearing price", "value": "price"},
                        {"label": " Marginal cost lines", "value": "mclines"},
                        {"label": " Shadow price", "value": "shadow"},
                    ],
                    value=["demand", "mclines"],
                    labelStyle={"display": "inline-block", "marginRight": "16px",
                                "fontSize": "13px"},
                    style={"marginTop": "6px"},
                ),
            ], style={"flex": "2", "minWidth": "320px"}),
        ], style={"display": "flex", "gap": "20px", "flexWrap": "wrap"}),
    ], style=CARD),

    # ---- tabs ----
    dcc.Tabs(id="tabs", value="tab-dispatch", children=[
        dcc.Tab(label="Dispatch and price", value="tab-dispatch", children=[
            html.Div([
                dcc.Graph(id="graph-dispatch"),
                html.Div(
                    "Note: hiding a plant only removes it from the chart, it does not "
                    "re-solve the model. The stack will drop below the demand line; "
                    "that gap is a display filter, not unserved energy.",
                    style={"fontSize": "12px", "color": "#888", "fontStyle": "italic",
                           "padding": "0 14px 10px 14px"}),
            ], style=CARD),
            html.Div([dcc.Graph(id="graph-price")], style=CARD),
            html.Div([dcc.Graph(id="graph-costs")], style=CARD),
            html.Div([
                html.Details([
                    html.Summary(
                        "QA - LP optimality checks",
                        style={"fontWeight": "600", "fontSize": "14px",
                               "cursor": "pointer", "padding": "2px 0"}),
                    html.Div([
                        html.Div(
                            "Checks that the dispatch really is least cost. In an "
                            "optimal LP a part-loaded plant must have marginal cost "
                            "equal to the price, a plant at full capacity must be at "
                            "or below it, and an idle plant at or above it. Uses "
                            "hourly data over the selected hour range; the resolution "
                            "setting does not apply, because violations are per-hour "
                            "events that averaging would hide.",
                            style={"fontSize": "12px", "color": "#666",
                                   "margin": "10px 0 12px 0"}),
                        html.Div(id="qa-banner"),
                        dcc.Graph(id="graph-qa-price"),
                        dcc.Graph(id="graph-qa-states"),
                        html.Div(id="qa-violations"),
                    ], style={"marginTop": "6px"}),
                ], open=False),
            ], style=CARD),
        ]),
        dcc.Tab(label="Duration curves and mix", value="tab-duration", children=[
            html.Div([
                dcc.Graph(id="graph-price-duration"),
                dcc.Graph(id="graph-load-duration"),
                html.Div(
                    "Duration curves always use hourly data. Averaging over days or "
                    "weeks would flatten the peaks these curves exist to show, so the "
                    "resolution setting does not apply here.",
                    style={"fontSize": "12px", "color": "#888", "fontStyle": "italic",
                           "padding": "0 14px 10px 14px"}),
            ], style=CARD),
            html.Div([dcc.Graph(id="graph-energy-mix")], style=CARD),
        ]),
        dcc.Tab(label="Compare runs", value="tab-compare", children=[
            html.Div([
                html.Div(id="compare-attribution",
                         style={"fontSize": "14px", "marginBottom": "10px"}),
                html.Div(id="compare-kpis",
                         style={"display": "flex", "gap": "10px",
                                "flexWrap": "wrap"}),
            ], style=CARD),
            html.Div([html.Div(id="compare-inputs")], style=CARD),
            html.Div([dcc.Graph(id="graph-compare-dispatch")], style=CARD),
            html.Div([dcc.Graph(id="graph-compare-price")], style=CARD),
            html.Div([html.Div(id="compare-plants")], style=CARD),
        ]),
    ]),

    dcc.Store(id="store-range"),
], style={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
          "backgroundColor": "#F4F5F7", "padding": "18px", "minHeight": "100vh"})


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

# Colours identifying which run a trace belongs to, deliberately separate
# from the technology palette so A and B never get confused with fuels.
C_RUN_A = "#0072B2"
C_RUN_B = "#D55E00"

COMPARE_KPIS = [
    ("production_cost", "Production cost", "$", "lower"),
    ("market_cost", "Market cost", "$", "lower"),
    ("load_weighted_price", "Load-weighted price", "$/MWh", "lower"),
    ("renewable_share_pct", "Renewable share", "%", "higher"),
    ("curtailed_mwh", "Curtailed", "MWh", "lower"),
    ("energy_served_mwh", "Energy served", "MWh", None),
]


def window_kpis(run, lo, hi):
    """KPIs recomputed over the visible window, so the comparison always
    matches what the charts are showing rather than the whole archived run."""
    h = slice_hours(run, lo, hi)
    if h.empty:
        return {}
    demand = float(h[DEMAND_COL].sum())
    prod = float(h[PROD_COST_COL].sum())
    market = float(h[MARKET_COST_COL].sum())
    ren_used = sum(float(h[run.meta[p]["column"]].sum())
                   for p in run.plant_order if run.meta[p]["profiled"])
    curtailed = float(h["Curtailment (MWh)"].sum()) \
        if "Curtailment (MWh)" in h.columns else 0.0
    ren_avail = 0.0
    for p in run.plant_order:
        col = run.meta[p]["avail_column"]
        if run.meta[p]["profiled"] and col:
            ren_avail += float(h[col].sum())
    return {
        "production_cost": prod,
        "market_cost": market,
        "load_weighted_price": market / demand if demand else 0.0,
        "renewable_share_pct": 100.0 * ren_used / demand if demand else 0.0,
        "curtailed_mwh": curtailed,
        "energy_served_mwh": demand,
        "renewable_available_mwh": ren_avail,
    }


def delta_card(label, before, after, unit, better):
    delta = after - before
    pct = (100.0 * delta / before) if before else None

    if abs(delta) < 1e-9 or better is None:
        colour = "#555555"
    elif (better == "lower") == (delta < 0):
        colour = C_PASS
    else:
        colour = C_FAIL

    def fmt(v):
        if unit == "%":
            return "{:,.2f}%".format(v)
        if abs(v) >= 1000:
            return "{:,.0f}".format(v)
        return "{:,.2f}".format(v)

    arrow = "" if abs(delta) < 1e-9 else ("v " if delta < 0 else "^ ")
    pct_txt = "no change" if abs(delta) < 1e-9 else (
        "{}{:.2f}%".format(arrow, abs(pct)) if pct is not None else arrow)

    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#666",
                               "textTransform": "uppercase",
                               "letterSpacing": "0.5px"}),
        html.Div(fmt(after), style={"fontSize": "20px", "fontWeight": "600",
                                    "marginTop": "3px"}),
        html.Div("was {}".format(fmt(before)),
                 style={"fontSize": "11px", "color": "#888"}),
        html.Div(pct_txt, style={"fontSize": "12px", "color": colour,
                                 "fontWeight": "600", "marginTop": "2px"}),
    ], style={"flex": "1", "minWidth": "150px", "padding": "12px 14px",
              "backgroundColor": "#FFFFFF", "border": "1px solid #E0E0E0",
              "borderRadius": "6px"})


def compare_attribution(a, b):
    """State plainly whether code or inputs moved, which is the whole point
    of keeping the archive."""
    if a.manifest is None or b.manifest is None:
        return html.Div(
            "One of these is the live working folder, which has no manifest, "
            "so code and inputs cannot be attributed. Compare two archived "
            "runs for that.",
            style={"color": "#8A6D3B"})
    try:
        d = runstore.diff(a.id, b.id)
    except Exception as exc:                                  # noqa: BLE001
        return html.Div("Could not diff: {}".format(exc), style={"color": C_FAIL})

    text = runstore.attribution(d)
    ok = d["same_code"] and d["same_inputs"]
    return html.Div(text, style={
        "padding": "10px 12px", "borderRadius": "5px", "fontWeight": "600",
        "backgroundColor": C_PASS_BG if ok else "#EEF3F8",
        "border": "1px solid {}".format(C_PASS if ok else C_RUN_A)})


def compare_inputs_table(a, b):
    """What actually changed in the input CSVs."""
    if a.manifest is None or b.manifest is None:
        return html.Div()
    try:
        d = runstore.diff(a.id, b.id)
    except Exception:                                         # noqa: BLE001
        return html.Div()

    if d["same_inputs"]:
        return html.Div("Inputs are identical in both runs.",
                        style={"fontSize": "13px", "color": "#666"})

    blocks = [html.Div("Input differences", style={
        "fontWeight": "600", "fontSize": "14px", "marginBottom": "8px"})]

    for name, info in sorted(d["inputs_changed"].items()):
        blocks.append(html.Div(name, style={"fontWeight": "600",
                                            "fontSize": "13px",
                                            "margin": "8px 0 4px 0"}))
        if info["kind"] == "cells":
            rows = [{"Row": c["row"], "Field": c["field"],
                     "A": str(c["before"]), "B": str(c["after"])}
                    for c in info["changes"]]
            blocks.append(dash_table.DataTable(
                data=rows,
                columns=[{"name": c, "id": c} for c in ("Row", "Field", "A", "B")],
                page_size=12,
                style_cell={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
                            "fontSize": "12px", "padding": "6px",
                            "textAlign": "left"},
                style_header={"backgroundColor": "#F4F5F7", "fontWeight": "600"},
            ))
        else:
            before, after = info["before"], info["after"]
            rows = [{"Series": "(rows)", "A": "{:,}".format(before["rows"]),
                     "B": "{:,}".format(after["rows"])}]
            for col in before["series"]:
                if col not in after["series"]:
                    continue
                sa, sb = before["series"][col], after["series"][col]
                if abs(sa["sum"] - sb["sum"]) < 1e-9:
                    continue
                rows.append({"Series": col,
                             "A": "mean {:,.4f}".format(sa["mean"]),
                             "B": "mean {:,.4f}".format(sb["mean"])})
            blocks.append(dash_table.DataTable(
                data=rows,
                columns=[{"name": c, "id": c} for c in ("Series", "A", "B")],
                page_size=8,
                style_cell={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
                            "fontSize": "12px", "padding": "6px",
                            "textAlign": "left"},
                style_header={"backgroundColor": "#F4F5F7", "fontWeight": "600"},
            ))
    return html.Div(blocks)


def fig_compare_total(a, b, lo, hi, resolution):
    """Total generation of each run over time. Stacks cannot be overlaid
    legibly, so the comparison shows each run's total against demand."""
    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty or agg_b.empty:
        return empty_figure("No overlapping hours to compare")

    def total(run, agg):
        cols = [run.meta[p]["column"] for p in run.plant_order
                if run.meta[p]["column"] in agg.columns]
        return agg[cols].sum(axis=1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg_a["x"], y=total(a, agg_a), name="A generation",
                             mode="lines", line=dict(color=C_RUN_A, width=1.8)))
    fig.add_trace(go.Scatter(x=agg_b["x"], y=total(b, agg_b), name="B generation",
                             mode="lines", line=dict(color=C_RUN_B, width=1.8,
                                                     dash="dash")))
    fig.add_trace(go.Scatter(x=agg_a["x"], y=agg_a[DEMAND_COL], name="Demand (A)",
                             mode="lines",
                             line=dict(color="#000000", width=1.1, dash="dot")))
    return base_layout(fig, "Total generation: A vs B",
                       axis_label(resolution), energy_label(resolution))


def fig_compare_price(a, b, lo, hi, resolution):
    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty or agg_b.empty:
        return empty_figure("No overlapping hours to compare")

    # "hvh" to match the step convention used elsewhere: each flat run is
    # centred on its hour.
    shape = "hvh" if resolution == "hourly" else "linear"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg_a["x"], y=agg_a[PRICE_COL], name="A price",
                             mode="lines",
                             line=dict(color=C_RUN_A, width=1.8, shape=shape)))
    fig.add_trace(go.Scatter(x=agg_b["x"], y=agg_b[PRICE_COL], name="B price",
                             mode="lines",
                             line=dict(color=C_RUN_B, width=1.8, shape=shape,
                                       dash="dash")))

    # Difference only makes sense where the two share an x axis.
    if len(agg_a) == len(agg_b):
        fig.add_trace(go.Scatter(
            x=agg_a["x"], y=(agg_b[PRICE_COL].values - agg_a[PRICE_COL].values),
            name="B minus A", mode="lines", yaxis="y2",
            line=dict(color=C_NEUTRAL, width=1.1)))
        return base_layout(fig, "Clearing price: A vs B",
                           axis_label(resolution), "Price ($/MWh)",
                           y2label="Difference ($/MWh)")
    return base_layout(fig, "Clearing price: A vs B",
                       axis_label(resolution), "Price ($/MWh)")


def compare_plants_table(a, b, lo, hi):
    """Per-plant generation in each run over the visible window, including
    plants that exist in only one of the two fleets."""
    ha, hb = slice_hours(a, lo, hi), slice_hours(b, lo, hi)
    rows = []
    for p in sorted(set(a.plant_order) | set(b.plant_order)):
        in_a, in_b = p in a.meta, p in b.meta
        gen_a = float(ha[a.meta[p]["column"]].sum()) if in_a and not ha.empty else None
        gen_b = float(hb[b.meta[p]["column"]].sum()) if in_b and not hb.empty else None
        delta = (gen_b - gen_a) if (gen_a is not None and gen_b is not None) else None
        rows.append({
            "Plant": p,
            "Technology": (a.meta[p]["technology"] if in_a
                           else b.meta[p]["technology"]),
            "Capacity A": "{:,.0f}".format(a.meta[p]["capacity"]) if in_a else "-",
            "Capacity B": "{:,.0f}".format(b.meta[p]["capacity"]) if in_b else "-",
            "Generation A": "{:,.0f}".format(gen_a) if gen_a is not None else "-",
            "Generation B": "{:,.0f}".format(gen_b) if gen_b is not None else "-",
            "Change": "{:+,.0f}".format(delta) if delta is not None else
                      ("only in B" if not in_a else "only in A"),
        })

    cols = ["Plant", "Technology", "Capacity A", "Capacity B",
            "Generation A", "Generation B", "Change"]
    return html.Div([
        html.Div("Per-plant generation over the selected window",
                 style={"fontWeight": "600", "fontSize": "14px",
                        "marginBottom": "8px"}),
        dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in cols],
            style_cell={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
                        "fontSize": "12px", "padding": "6px", "textAlign": "left"},
            style_header={"backgroundColor": "#F4F5F7", "fontWeight": "600"},
        ),
    ])


def build_comparison(a, b, lo, hi, resolution):
    ka, kb = window_kpis(a, lo, hi), window_kpis(b, lo, hi)

    cards = []
    if ka and kb:
        for key, label, unit, better in COMPARE_KPIS:
            if key in ka and key in kb:
                cards.append(delta_card(label, ka[key], kb[key], unit, better))

    return (compare_attribution(a, b),
            cards,
            compare_inputs_table(a, b),
            fig_compare_total(a, b, lo, hi, resolution),
            fig_compare_price(a, b, lo, hi, resolution),
            compare_plants_table(a, b, lo, hi))


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------

@app.callback(
    Output("run-select", "options"),
    Output("run-compare", "options"),
    Input("run-refresh", "n_clicks"),
    Input("run-select", "value"),
)
def refresh_run_lists(_clicks, selected):
    """Keep both dropdowns in step with what is on disk. A run archived while
    the dashboard is open shows up after a refresh."""
    options = run_options()
    compare = [o for o in options if o["value"] != selected]
    return options, compare


@app.callback(
    Output("hour-range", "min"),
    Output("hour-range", "max"),
    Output("hour-range", "marks"),
    Output("hour-range", "value"),
    Output("plant-toggle", "options"),
    Output("plant-toggle", "value"),
    Output("run-info", "children"),
    Input("run-select", "value"),
    Input("run-compare", "value"),
)
def switch_run(run_id, compare_id):
    """Runs differ in fleet and in hour range, so the controls are rebuilt
    whenever the selection changes."""
    run = get_run(run_id)
    other = get_run(compare_id) if compare_id else None

    options = plant_options(run, other)
    values = [o["value"] for o in options]

    lo, hi = run.hour_min, run.hour_max
    if other is not None:
        # Only the overlapping hours can be compared meaningfully.
        lo, hi = max(lo, other.hour_min), min(hi, other.hour_max)
        if lo > hi:
            lo, hi = run.hour_min, run.hour_max

    return (lo, hi, hour_marks(lo, hi), [lo, hi], options, values,
            run_info_text(run, other))


def run_info_text(run, other):
    bits = [describe_run(run, "A" if other is not None else None)]
    if other is not None:
        bits.append(describe_run(other, "B"))
        if run.hour_min != other.hour_min or run.hour_max != other.hour_max:
            bits.append("Hour ranges differ; the slider is limited to the overlap.")
        fleet_a, fleet_b = set(run.plant_order), set(other.plant_order)
        if fleet_a != fleet_b:
            only_a = ", ".join(sorted(fleet_a - fleet_b)) or "none"
            only_b = ", ".join(sorted(fleet_b - fleet_a)) or "none"
            bits.append("Fleets differ. Only in A: {}. Only in B: {}. "
                        "A colour may not mean the same plant in both runs, "
                        "so read the labels rather than the colours."
                        .format(only_a, only_b))
    return html.Div([html.Div(b, style={"marginBottom": "3px"}) for b in bits])


def describe_run(run, tag=None):
    prefix = "{}: ".format(tag) if tag else ""
    if run.id == CURRENT_ID:
        return ("{}current working folder - {} plants, hours {} to {}"
                .format(prefix, len(run.plant_order), run.hour_min, run.hour_max))
    m = run.manifest or {}
    git = m.get("git") or {}
    return ("{}{}{} - {} plants, hours {} to {}, git {}{}"
            .format(prefix, run.id,
                    "  ({})".format(run.label) if run.label else "",
                    len(run.plant_order), run.hour_min, run.hour_max,
                    git.get("short") or "n/a",
                    " dirty" if git.get("dirty") else ""))


@app.callback(
    Output("store-range", "data"),
    Input("hour-range", "value"),
    Input("run-select", "value"),
    Input("run-compare", "value"),
)
def store_range(hour_range, run_id, compare_id):
    """Single source of truth for the selected window and runs."""
    lo, hi = int(hour_range[0]), int(hour_range[1])
    return {"lo": lo, "hi": hi, "run": run_id, "compare": compare_id}


@app.callback(
    Output("hour-range", "value", allow_duplicate=True),
    Input("preset-day", "n_clicks"),
    Input("preset-week", "n_clicks"),
    Input("preset-all", "n_clicks"),
    State("run-select", "value"),
    prevent_initial_call=True,
)
def apply_preset(_day, _week, _all, run_id):
    """Preset buttons write into the range slider, relative to the run."""
    run = get_run(run_id)
    lo, hi = run.hour_min, run.hour_max
    triggered = callback_context.triggered
    if not triggered:
        return [lo, hi]
    which = triggered[0]["prop_id"].split(".")[0]
    if which == "preset-day":
        return [lo, min(lo + HOURS_PER_DAY - 1, hi)]
    if which == "preset-week":
        return [lo, min(lo + HOURS_PER_WEEK - 1, hi)]
    return [lo, hi]


@app.callback(
    Output("kpi-row", "children"),
    Input("store-range", "data"),
)
def update_kpis(rng):
    run = get_run(rng.get("run"))
    return build_kpis(run, slice_hours(run, rng["lo"], rng["hi"]))


@app.callback(
    Output("graph-dispatch", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
    Input("plant-toggle", "value"),
    Input("overlay-toggle", "value"),
)
def update_dispatch(rng, resolution, plants, overlays):
    run = get_run(rng.get("run"))
    hourly = slice_hours(run, rng["lo"], rng["hi"])
    return fig_dispatch(run, aggregate(run, hourly, resolution), plants or [],
                        overlays or [], resolution)


@app.callback(
    Output("graph-price", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
    Input("overlay-toggle", "value"),
)
def update_price(rng, resolution, overlays):
    run = get_run(rng.get("run"))
    hourly = slice_hours(run, rng["lo"], rng["hi"])
    return fig_price(run, aggregate(run, hourly, resolution),
                     overlays or [], resolution)


@app.callback(
    Output("graph-costs", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
)
def update_costs(rng, resolution):
    run = get_run(rng.get("run"))
    hourly = slice_hours(run, rng["lo"], rng["hi"])
    return fig_costs(run, aggregate(run, hourly, resolution), resolution)


@app.callback(
    Output("graph-price-duration", "figure"),
    Input("store-range", "data"),
)
def update_price_duration(rng):
    run = get_run(rng.get("run"))
    return fig_price_duration(run, slice_hours(run, rng["lo"], rng["hi"]))


@app.callback(
    Output("graph-load-duration", "figure"),
    Input("store-range", "data"),
    Input("plant-toggle", "value"),
)
def update_load_duration(rng, plants):
    run = get_run(rng.get("run"))
    return fig_load_duration(run, slice_hours(run, rng["lo"], rng["hi"]),
                             plants or [])


@app.callback(
    Output("graph-energy-mix", "figure"),
    Input("store-range", "data"),
    Input("plant-toggle", "value"),
)
def update_energy_mix(rng, plants):
    run = get_run(rng.get("run"))
    return fig_energy_mix(run, slice_hours(run, rng["lo"], rng["hi"]),
                          plants or [])


@app.callback(
    Output("qa-banner", "children"),
    Output("graph-qa-price", "figure"),
    Output("graph-qa-states", "figure"),
    Output("qa-violations", "children"),
    Input("store-range", "data"),
)
def update_qa(rng):
    """QA respects the hour range so a suspicious window can be isolated,
    but deliberately ignores the resolution dropdown."""
    run = get_run(rng.get("run"))
    hourly = slice_hours(run, rng["lo"], rng["hi"])
    qa = run_qa(run, hourly)
    return (qa_banner(qa), fig_qa_price(run, hourly), fig_qa_states(run, qa),
            qa_violations_table(qa))


@app.callback(
    Output("compare-attribution", "children"),
    Output("compare-kpis", "children"),
    Output("compare-inputs", "children"),
    Output("graph-compare-dispatch", "figure"),
    Output("graph-compare-price", "figure"),
    Output("compare-plants", "children"),
    Input("store-range", "data"),
    Input("resolution", "value"),
)
def update_compare(rng, resolution):
    run_id, compare_id = rng.get("run"), rng.get("compare")
    if not compare_id:
        msg = html.Div("Pick a run in 'Compare with' above to see a comparison.",
                       style={"color": "#666"})
        blank = empty_figure("No comparison run selected")
        return msg, [], html.Div(), blank, blank, html.Div()

    a = get_run(run_id)
    b = get_run(compare_id)
    return build_comparison(a, b, rng["lo"], rng["hi"], resolution)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    run = load_current()
    print("\nDispatch Model Dashboard")
    print("  current results: {} plants, hours {} to {}".format(
        len(run.plant_order), run.hour_min, run.hour_max))
    print("  {} archived run(s) available".format(len(runstore.list_runs())))
    print("  Open http://127.0.0.1:8050 in your browser")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=False, port=8050)
