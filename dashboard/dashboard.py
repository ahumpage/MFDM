from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output, State, callback_context, dash_table

# runstore lives in run_archive/, a sibling folder rather than a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "run_archive"))
import runstore


# Configuration

BASE_DIR = Path(__file__).resolve().parent          # dashboard/
REPO_ROOT = BASE_DIR.parent

RESULTS_DIR = REPO_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "dispatch_results.csv"
SUMMARY_FILE = RESULTS_DIR / "plant_summary.csv"

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

RGBA_PRICE_FILL = "rgba(213, 94, 0, 0.15)"
RGBA_PRICE_AREA = "rgba(213, 94, 0, 0.20)"

DEMAND_COL = "Demand (MWh)"
PRICE_COL = "Clearing Price ($/MWh)"

STACK_COL = "Highest Running Cost ($/MWh)"
PROD_COST_COL = "Production Cost ($)"
MARKET_COST_COL = "Market Cost ($)"
UNSERVED_COL = "Unserved Energy (MWh)"
SPILL_COL = "Spill (MWh)"
RAMP_UP_COL = "Ramp Up (MWh)"
RAMP_DOWN_COL = "Ramp Down (MWh)"
RAMP_COST_COL = "Ramp Cost ($)"

HOURS_PER_DAY = 24
HOURS_PER_WEEK = 168


BAR_THRESHOLD = 200

PLOT_BG = "#FFFFFF"
GRID = "#E6E6E6"
PAIR_MARGIN_TOP = 118

# Standard chart heights. CHART_H is the default for a full chart; CHART_H_THIN
# is for a chart that only needs to show a line or two and can afford to be
# short; PAIR_H is the side-by-side A|B dispatch figure, which carries two
# panels and so needs a little more room.
CHART_H = 400
CHART_H_THIN = 230
PAIR_H = 430


# Data loading

def lighten(hex_colour, amount):
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    blended = [int(round(c + (255 - c) * amount)) for c in rgb]
    return "#{:02X}{:02X}{:02X}".format(*blended)


class Run(object):

    def __init__(self, run_id, label, results, summary, manifest=None):
        self.id = run_id
        self.label = label
        self.manifest = manifest
        self.results = results


        self.summary = summary.sort_values(
            "Marginal Cost ($/MWh)").reset_index(drop=True)
        self.plant_order = list(self.summary["Plant"])
        self.meta = self._build_meta()

        self.hour_min = int(results["Hour"].min())
        self.hour_max = int(results["Hour"].max())

        self.has_stack = STACK_COL in results.columns
        self.has_ramp = RAMP_COST_COL in results.columns
        self.has_spill = SPILL_COL in results.columns
        self.batteries = self._find_batteries()
        self.has_storage = bool(self.batteries)

    def _find_batteries(self):
        suffix = " Charge (MWh)"
        return [c[:-len(suffix)] for c in self.results.columns if c.endswith(suffix)
                and "{} Discharge (MWh)".format(c[:-len(suffix)]) in self.results.columns
                and "{} State of Charge (MWh)".format(c[:-len(suffix)]) in self.results.columns]

    def _build_meta(self):
        meta = {}
        seen_tech = {}
        for i, row in self.summary.iterrows():
            tech = row["Technology"]

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
   
                "ramp_rate": (float(row["Ramp Rate (MW/hr)"])
                              if "Ramp Rate (MW/hr)" in self.summary.columns else None),
                "ramp_premium": (float(row["Ramp Premium ($/MWh)"])
                                 if "Ramp Premium ($/MWh)" in self.summary.columns
                                 else None),
                "profiled": (bool(row["Profiled"])
                             if "Profiled" in self.summary.columns else False),
                "colour": colour,
                "column": "{} (MWh)".format(row["Plant"]),

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
    """Load a run by id, caching archived ones; 'current' is always re-read."""
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


def default_run_ids():
    #open on the newest two archived runs.

    runs = runstore.list_runs()
    if len(runs) >= 2:
        return runs[0]["id"], runs[1]["id"]
    if len(runs) == 1:
        return runs[0]["id"], None
    return CURRENT_ID, None



# Filtering and aggregation

def slice_hours(run, lo, hi):
    """Rows within the selected hour window, always at hourly resolution."""
    mask = (run.results["Hour"] >= lo) & (run.results["Hour"] <= hi)
    return run.results.loc[mask].copy()


def aggregate(run, df, resolution):
    #Aggregate to daily or weekly buckets; energy summed, price load-weighted
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
    for b in run.batteries:
        sum_cols += ["{} Charge (MWh)".format(b), "{} Discharge (MWh)".format(b)]
    sum_cols += [DEMAND_COL, PROD_COST_COL, MARKET_COST_COL,
                 RAMP_UP_COL, RAMP_DOWN_COL, RAMP_COST_COL,
                 UNSERVED_COL, SPILL_COL]
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
    if run.has_stack:
        out[STACK_COL] = grouped.apply(
            lambda g: (g[STACK_COL] * g[DEMAND_COL]).sum() / g[DEMAND_COL].sum()
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


def base_layout(fig, title, xlabel, ylabel, y2label=None, height=CHART_H):

    # A thin chart cannot afford a full-size title block and axis gutter, or
    # the chrome would leave almost no room for the line itself.
    thin = height <= CHART_H_THIN
    top, bottom = (58, 36) if thin else (92, 45)
    fig.update_layout(
        title=dict(text=title, x=0.01, y=0.97, yanchor="top", yref="container",
                   font=dict(size=13 if thin else 15)),
        xaxis_title=xlabel,
        yaxis_title=ylabel,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PLOT_BG,
        margin=dict(l=60, r=30, t=top, b=bottom),
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02 if thin else 1.06,
                    xanchor="left", x=0, font=dict(size=11) if thin else None),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)

    if y2label is not None:

        fig.update_layout(
            yaxis2=dict(title=y2label, overlaying="y", side="right",
                        showgrid=False, zeroline=False, rangemode="tozero"),
            margin=dict(l=60, r=65, t=top, b=bottom),
        )
    return fig


def empty_figure(message, height=CHART_H):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False,
                       xref="paper", yref="paper", x=0.5, y=0.5,
                       font=dict(size=14, color="#888"))
    # Same height as the chart it stands in for, so cards do not jump when a
    # range is empty. Callers drawing a thin chart must pass its height.
    fig.update_layout(plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG, height=height,
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


# Figures

GROUP_DEMAND = "__demand"
GROUP_PRICE = "__price"


def dispatch_mode(agg):
    #bars or area
    return len(agg) <= BAR_THRESHOLD


def dispatch_traces(run, agg, plants, overlays, resolution, stackgroup="one"):

    use_bars = dispatch_mode(agg)
    traces = []

    # Stack cheapest first so the chart reads as a merit order.
    for p in run.plant_order:
        if p not in plants:
            continue
        m = run.meta[p]
        name = "{} ({}) ${:.2f}/MWh".format(p, m["technology"], m["marginal_cost"])
        hover = "%{y:,.1f} MWh<extra>" + p + "</extra>"

        if use_bars:
            traces.append((go.Bar(
                x=agg["x"], y=agg[m["column"]],
                name=name, legendgroup=p, marker_color=m["colour"],
                marker_line_width=0,
                hovertemplate=hover,
            ), False))

        else:
            traces.append((go.Scatter(
                x=agg["x"], y=agg[m["column"]],
                name=name, legendgroup=p, mode="lines",
                line=dict(width=0.5, color=m["colour"]),
                fillcolor=m["colour"], stackgroup=stackgroup,
                hovertemplate=hover,
            ), False))

    supply_columns = [run.meta[p]["column"] for p in run.plant_order if p in plants]
    for b in run.batteries:
        discharge_col = "{} Discharge (MWh)".format(b)
        charge_col = "{} Charge (MWh)".format(b)
        if use_bars:
            traces.append((go.Bar(
                x=agg["x"], y=agg[discharge_col], name="{} discharge".format(b),
                legendgroup="storage-{}".format(b), marker_color="#6A3D9A",
                marker_line_width=0,
                hovertemplate="%{{y:,.1f}} MWh<extra>{} discharge</extra>".format(b),
            ), False))
            base = agg[supply_columns].sum(axis=1) if supply_columns else 0.0
            base = base + agg[["{} Discharge (MWh)".format(x) for x in run.batteries]].sum(axis=1)
            traces.append((go.Bar(
                x=agg["x"], y=agg[charge_col], base=base, name="{} charge (load)".format(b),
                legendgroup="storage-{}".format(b), marker_color="#B7A0CF",
                marker_pattern_shape="/", marker_line_width=0,
                hovertemplate="%{{y:,.1f}} MWh<extra>{} charge</extra>".format(b),
            ), False))
        else:
            traces.append((go.Scatter(
                x=agg["x"], y=agg[discharge_col], name="{} discharge".format(b),
                legendgroup="storage-{}".format(b), mode="lines",
                line=dict(width=0.5, color="#6A3D9A"), fillcolor="#6A3D9A",
                stackgroup=stackgroup,
                hovertemplate="%{{y:,.1f}} MWh<extra>{} discharge</extra>".format(b),
            ), False))
    if "demand" in overlays:
        traces.append((go.Scatter(
            x=agg["x"], y=agg[DEMAND_COL],
            name="Demand", legendgroup=GROUP_DEMAND, mode="lines",
            line=dict(color=C_DEMAND, width=1.6, dash="dash"),
            hovertemplate="%{y:,.1f} MWh<extra>Demand</extra>",
        ), False))

    if "price" in overlays:

        shape = "hvh" if resolution == "hourly" else "linear"
        price_name = ("Clearing price" if resolution == "hourly"
                      else "Load-weighted avg price")
        traces.append((go.Scatter(
            x=agg["x"], y=agg[PRICE_COL],
            name=price_name, legendgroup=GROUP_PRICE, mode="lines",
            line=dict(color=C_PRICE, width=1.8, shape=shape),
            hovertemplate="$%{y:,.2f}/MWh<extra>" + price_name + "</extra>",
        ), True))

    return traces


def dispatch_title(agg):
    return "Dispatch by plant ({})".format(
        "stacked bars" if dispatch_mode(agg)
        else "area, {:,} periods".format(len(agg)))


def fig_dispatch(run, agg, plants, overlays, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    for trace, on_price_axis in dispatch_traces(run, agg, plants, overlays,
                                                resolution):
        if on_price_axis:
            trace.update(yaxis="y2")
        fig.add_trace(trace)

    if dispatch_mode(agg):
        fig.update_layout(barmode="stack", bargap=0)

    y2label = "Price ($/MWh)" if "price" in overlays else None
    return base_layout(fig, dispatch_title(agg), axis_label(resolution),
                       energy_label(resolution), y2label=y2label)


def fig_price(run, agg, overlays, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    shape = "hvh" if resolution == "hourly" else "linear"

    fig.add_trace(go.Scatter(
        x=agg["x"], y=agg[PRICE_COL],
        name="Clearing price", mode="lines",
        line=dict(color=C_PRICE, width=1.8, shape=shape),
        hovertemplate="$%{y:,.2f}/MWh<extra>Clearing price</extra>",
    ))

    if "stack" in overlays and run.has_stack:
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[STACK_COL],
            name="Highest running cost (merit order)", mode="lines",
            line=dict(color=C_SHADOW, width=1.2, dash="dot", shape=shape),
            hovertemplate="$%{y:,.2f}/MWh<extra>Highest running cost</extra>",
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


def fig_storage(run, hourly, resolution):
    if not run.has_storage:
        return empty_figure("No storage results in this run")
    agg = aggregate(run, hourly, resolution)
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Charge and discharge", "State of charge"))
    for b in run.batteries:
        fig.add_trace(go.Bar(x=agg["x"], y=agg["{} Charge (MWh)".format(b)],
                             name="{} charge".format(b), marker_color="#B7A0CF",
                             marker_pattern_shape="/"), row=1, col=1)
        fig.add_trace(go.Bar(x=agg["x"], y=agg["{} Discharge (MWh)".format(b)],
                             name="{} discharge".format(b), marker_color="#6A3D9A"), row=1, col=1)
        if resolution == "hourly":
            soc = hourly["{} State of Charge (MWh)".format(b)]
        else:
            step = HOURS_PER_DAY if resolution == "daily" else HOURS_PER_WEEK
            grouped = hourly.assign(bucket=(hourly["Hour"] - 1) // step).groupby("bucket")
            soc = grouped["{} State of Charge (MWh)".format(b)].last().to_numpy()
        fig.add_trace(go.Scatter(x=agg["x"], y=soc, name="{} SoC".format(b),
                                 mode="lines", line=dict(width=2)), row=2, col=1)
    fig.update_layout(barmode="group")
    base_layout(fig, "Battery storage", axis_label(resolution), "Energy (MWh)")
    fig.update_yaxes(title_text=energy_label(resolution), row=1, col=1)
    fig.update_yaxes(title_text="State of charge (MWh)", row=2, col=1)
    return fig


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
        name="Production cost (fuel and VOM)", mode="lines",
        line=dict(color=C_PROD, width=1.6, dash="dash"),
        fill="tonexty", fillcolor=RGBA_PRICE_FILL,
        hovertemplate="$%{y:,.0f}<extra>Production cost</extra>",
    ))

    if run.has_ramp:
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[RAMP_COST_COL],
            name="Ramp cost (premium on energy moved)", mode="lines",
            line=dict(color=C_SHADOW, width=1.2, dash="dot"),
            hovertemplate="$%{y:,.0f}<extra>Ramp cost</extra>",
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

"""
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
"""

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


# QA - consistency checks

QA_TOL = 1e-4          # $/MWh and MWh tolerance for declaring a violation
MAX_VIOLATION_ROWS = 100

STATE_PART = "Part loaded"
STATE_FULL = "At capacity"
STATE_IDLE = "Idle"
STATE_UNAVAIL = "No resource"
STATE_COLOURS = {STATE_PART: C_PRICE, STATE_FULL: C_SHADOW,
                 STATE_IDLE: "#BDC3C7", STATE_UNAVAIL: "#EAECEE"}


def run_qa(run, hourly):
    """Run the consistency checks over the selected hours, always hourly."""
    out = {
        "n_hours": len(hourly),
        "balance_errors": 0,
        "max_balance_error": 0.0,
        "market_cost_errors": 0,
        "violations": [],
        "n_violations": 0,
        "states": {},
        "rents": {},
        "total_rent": 0.0,
        "held_back": 0,
        "ok": True,
    }
    if hourly.empty:
        return out

    price = hourly[PRICE_COL]
    gen_cols = [run.meta[p]["column"] for p in run.plant_order]
    total_gen = hourly[gen_cols].sum(axis=1)

    # --- check 1: the energy balance closes ---
    balance = total_gen.copy()
    if UNSERVED_COL in hourly.columns:
        balance = balance + hourly[UNSERVED_COL]
    if SPILL_COL in hourly.columns:
        balance = balance - hourly[SPILL_COL]
    for b in run.batteries:
        balance = balance + hourly["{} Discharge (MWh)".format(b)]
        balance = balance - hourly["{} Charge (MWh)".format(b)]
    balance_error = (balance - hourly[DEMAND_COL]).abs()
    out["max_balance_error"] = float(balance_error.max())

    out["balance_errors"] = int(
        (balance_error > QA_TOL * hourly[DEMAND_COL].clip(lower=1.0)).sum())

    # --- check 2: market cost is price times demand ---
    if MARKET_COST_COL in hourly.columns:
        expected = price * hourly[DEMAND_COL]
        drift = (hourly[MARKET_COST_COL] - expected).abs()
        out["market_cost_errors"] = int(
            (drift > QA_TOL * expected.abs().clip(lower=1.0)).sum())

    # --- check 3: per plant-hour capacity and ramp limits ---
    for p in run.plant_order:
        m = run.meta[p]
        gen = hourly[m["column"]]
        mc = m["marginal_cost"]

        if m["avail_column"]:
            cap = hourly[m["avail_column"]]
        else:
            cap = pd.Series(m["capacity"], index=hourly.index)

        part = (gen > QA_TOL) & (gen < cap - QA_TOL)
        full = gen >= cap - QA_TOL
        idle = gen <= QA_TOL

        unavailable = cap <= QA_TOL
        idle = idle & ~unavailable
        full = full & ~unavailable

        out["states"][p] = {
            STATE_PART: int(part.sum()),
            STATE_FULL: int(full.sum()),
            STATE_IDLE: int(idle.sum()),
            STATE_UNAVAIL: int(unavailable.sum()),
        }
        out["rents"][p] = float(((price - mc) * gen).sum())

        over_cap = gen > cap + QA_TOL
        for idx, row in hourly.loc[over_cap].iterrows():
            out["violations"].append({
                "Hour": int(row["Hour"]),
                "Plant": p,
                "Check": "Capacity",
                "Generation (MWh)": round(float(row[m["column"]]), 3),
                "Limit": round(float(cap.loc[idx]), 3),
                "Detail": "generated above its hourly availability",
            })

        rate = m["ramp_rate"]
        if rate is not None and len(hourly) > 1:
            delta = gen.diff()
            allowance = pd.Series(0.0, index=hourly.index)
            if m["avail_column"]:
                allowance = (-cap.diff()).clip(lower=0.0).fillna(0.0)

            excess = delta.abs() - rate - allowance
            excess.iloc[0] = float("nan")
            for idx, row in hourly.loc[excess > QA_TOL].iterrows():
                out["violations"].append({
                    "Hour": int(row["Hour"]),
                    "Plant": p,
                    "Check": "Ramp rate",
                    "Generation (MWh)": round(float(row[m["column"]]), 3),
                    "Limit": round(float(rate + allowance.loc[idx]), 3),
                    "Detail": "moved {:,.2f} MWh from the previous hour".format(
                        abs(float(delta.loc[idx]))),
                })

        if run.has_stack:
            out["held_back"] += int(
                (part & (hourly[STACK_COL] > mc + QA_TOL)).sum())

    out["total_rent"] = float(sum(out["rents"].values()))
    out["n_violations"] = len(out["violations"])
    out["violations"].sort(key=lambda r: (r["Hour"], r["Plant"]))
    out["ok"] = (out["n_violations"] == 0
                 and out["balance_errors"] == 0
                 and out["market_cost_errors"] == 0)
    return out


def qa_banner(qa):
    if qa["n_hours"] == 0:
        return html.Div("No hours in the selected range.",
                        style={"padding": "10px 12px", "backgroundColor": "#F4F5F7",
                               "border": "1px solid #E0E0E0", "borderRadius": "5px",
                               "fontSize": "13px", "color": "#666"})

    checks = [
        ("Energy balance closes in every hour",
         qa["balance_errors"], "{} of {} hours off (max {:.2e} MWh)".format(
             qa["balance_errors"], qa["n_hours"], qa["max_balance_error"])),
        ("No plant exceeds its availability or its ramp rate",
         qa["n_violations"], "{} violating plant-hours".format(qa["n_violations"])),
        ("Market cost equals clearing price x demand",
         qa["market_cost_errors"], "{} hours disagree".format(qa["market_cost_errors"])),
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

    note = (
        "These are accounting identities, not optimality conditions, so an "
        "all-pass result is expected and a failure means a bug in the model. "
        "The old merit-order checks were retired when ramping made them false "
        "on correct results: a cheap plant may now sit part loaded beneath a "
        "dearer one rather than pay to move."
    )
    if qa["held_back"]:
        note += (" In this window {:,} plant-hours look like that; see the "
                 "merit order chart below.".format(qa["held_back"]))

    return html.Div([
        html.Div(header, style={"fontWeight": "700", "fontSize": "14px",
                                "marginBottom": "8px",
                                "color": C_PASS if ok else C_FAIL}),
        html.Div(rows),
        html.Div(note,
                 style={"fontSize": "11px", "color": "#888", "fontStyle": "italic",
                        "marginTop": "8px"}),
    ], style={
        "padding": "12px 14px", "borderRadius": "5px",
        "backgroundColor": C_PASS_BG if ok else C_FAIL_BG,
        "border": "1px solid {}".format(C_PASS if ok else C_FAIL),
    })


def fig_qa_price(run, hourly):
    if hourly.empty:
        return empty_figure("No hours in the selected range")
    if not run.has_stack:
        return empty_figure(
            "No 'Highest Running Cost' column in dispatch_results.csv. "
            "This run predates the merit-order diagnostic.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=hourly[PRICE_COL],
        name="Clearing price (energy-balance dual)", mode="lines",
        line=dict(color=C_PRICE, width=2.4, shape="hv"),
        hovertemplate="$%{y:,.2f}/MWh<extra>Clearing price</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=hourly[STACK_COL],
        name="Highest running cost (merit order)", mode="lines",
        line=dict(color=C_SHADOW, width=1.2, dash="dot", shape="hv"),
        hovertemplate="$%{y:,.2f}/MWh<extra>Highest running cost</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=(hourly[PRICE_COL] - hourly[STACK_COL]),
        name="Gap (what ramping adds)", mode="lines", yaxis="y2",
        line=dict(color=C_NEUTRAL, width=1.2),
        hovertemplate="$%{y:,.2f}/MWh<extra>Gap</extra>",
    ))

    return base_layout(fig, "QA: clearing price vs the merit order stack",
                       "Hour", "Price ($/MWh)", y2label="Gap ($/MWh)")


def fig_qa_states(run, qa):
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
    fig = base_layout(fig, "QA: plant state by hour", "", "Hours")
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
        html.Div("Capacity and ramp violations" + note,
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


# KPI cards

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
    unserved = hourly[UNSERVED_COL].sum() if UNSERVED_COL in hourly.columns else 0.0
    generated = sum(hourly[run.meta[p]["column"]].sum() for p in run.plant_order)

    # Production cost is fuel and VOM only, so the ramp and spill components
    # are shown beside it rather than left missing from the reader's sum.
    def total(col):
        return hourly[col].sum() if col in hourly.columns else 0.0

    ramp = total(RAMP_COST_COL)
    unserved_cost = total("Unserved Cost ($)")
    spill_cost = total("Spill Cost ($)")

    cards = [
        kpi_card("Hours", "{:,}".format(len(hourly)),
                 "hour {:,} to {:,}".format(int(hourly["Hour"].min()),
                                            int(hourly["Hour"].max()))),
        kpi_card("Energy served", "{:,.0f} MWh".format(demand - unserved)),
        kpi_card("Unserved energy", "{:,.0f} MWh".format(unserved)),
        kpi_card("Production cost", "${:,.0f}".format(prod), "fuel and VOM"),
    ]
    if run.has_ramp:
        cards.append(kpi_card("Ramp cost", "${:,.0f}".format(ramp),
                              "premium on energy moved"))
        cards.append(kpi_card(
            "Total system cost",
            "${:,.0f}".format(prod + ramp + unserved_cost + spill_cost),
            "the LP objective"))
    cards += [
        kpi_card("Market cost", "${:,.0f}".format(market), "price x demand"),
        kpi_card("Avg production cost", "${:,.2f}/MWh".format(prod / generated if generated else 0)),
        kpi_card("Load-weighted price", "${:,.2f}/MWh".format(market / demand if demand else 0)),
        kpi_card("Market surplus", "${:,.0f}".format(market - prod), "market - production"),
    ]
    if run.has_spill and total(SPILL_COL) > QA_TOL:
        cards.append(kpi_card("Spilled", "{:,.0f} MWh".format(total(SPILL_COL)),
                              "generated and thrown away"))
    return cards


# Layout

app = Dash(__name__)
app.title = "Dispatch Model Dashboard"

CARD = {"backgroundColor": "#FFFFFF", "border": "1px solid #E0E0E0",
        "borderRadius": "6px", "padding": "10px", "marginBottom": "10px"}

# The small italic caption under a chart, explaining how to read it.
NOTE = {"fontSize": "11.5px", "color": "#888", "fontStyle": "italic",
        "padding": "0 10px 6px 10px"}


def hour_marks(lo, hi):
    """Slider ticks that stay readable whatever the run's hour range."""
    span = max(hi - lo, 1)
    step = max(int(round(span / 10.0)), 1)
    marks = {h: str(h) for h in range(lo, hi + 1, step)}
    marks[lo] = str(lo)
    marks[hi] = str(hi)
    return marks


def plant_options(run, extra_run=None):
    """Checklist entries for a run's fleet, or the union of both when comparing."""
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


DEFAULT_A, DEFAULT_B = default_run_ids()
INITIAL_RUN = get_run(DEFAULT_A)

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
                             value=DEFAULT_A, clearable=False,
                             style={"marginTop": "6px"}),
            ], style={"flex": "2", "minWidth": "300px"}),
            html.Div([
                html.Label("Compare with",
                           style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.Dropdown(id="run-compare", options=[], value=DEFAULT_B,
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
                        {"label": " Highest running cost", "value": "stack"},
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
                    style=NOTE),
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
        dcc.Tab(label="Storage", value="tab-storage", children=[
            html.Div([dcc.Graph(id="graph-storage")], style=CARD),
        ]),
        dcc.Tab(label="Duration curves and mix", value="tab-duration", children=[
            html.Div([
                dcc.Graph(id="graph-price-duration"),
                dcc.Graph(id="graph-load-duration"),
                html.Div(
                    "Duration curves always use hourly data. Averaging over days or "
                    "weeks would flatten the peaks these curves exist to show, so the "
                    "resolution setting does not apply here.",
                    style=NOTE),
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

            # The two stacks side by side in one figure, on one shared y-axis
            # and behind one shared legend.
            html.Div([
                dcc.Graph(id="graph-compare-dispatch-pair"),
                html.Div(
                    "Both panels share a y-axis (and price axis), and one "
                    "legend that toggles a plant in A and B together.",
                    style=NOTE),
            ], style=CARD),

            # Price sits directly under the stacks: the stack shows who ran,
            # the price shows what that cost, on the same x-axis.
            html.Div([
                dcc.Graph(id="graph-compare-price"),
                dcc.Graph(id="graph-compare-price-diff"),
            ], style=CARD),

            html.Div([
                dcc.Graph(id="graph-compare-dispatch"),
                html.Div(
                    "The bars break the difference down by plant: above zero the "
                    "plant generated more in B, below zero more in A.",
                    style=NOTE),
            ], style=CARD),

            html.Div([html.Div(id="compare-plants")], style=CARD),
        ]),
    ]),

    dcc.Store(id="store-range"),
], style={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
          "backgroundColor": "#F4F5F7", "padding": "12px", "minHeight": "100vh"})


# Comparison

# Colours identifying which run a trace belongs to, deliberately separate
# from the technology palette so A and B never get confused with fuels.
C_RUN_A = "#0072B2"
C_RUN_B = "#D55E00"

COMPARE_KPIS = [
    ("production_cost", "Production cost", "$", "lower"),
    ("market_cost", "Market cost", "$", "lower"),
    ("market_surplus", "Market surplus", "$", None),
    ("load_weighted_price", "Load-weighted price", "$/MWh", "lower"),
    ("renewable_share_pct", "Renewable share", "%", "higher"),
    ("curtailed_mwh", "Curtailed", "MWh", "lower"),
    ("energy_served_mwh", "Energy served", "MWh", None),
    ("unserved_mwh", "Unserved energy", "MWh", "lower"),
]


def window_kpis(run, lo, hi):
    h = slice_hours(run, lo, hi)
    if h.empty:
        return {}
    demand = float(h[DEMAND_COL].sum())
    prod = float(h[PROD_COST_COL].sum())
    market = float(h[MARKET_COST_COL].sum())
    unserved = float(h[UNSERVED_COL].sum()) if UNSERVED_COL in h.columns else 0.0
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
        "market_surplus": market - prod,
        "load_weighted_price": market / demand if demand else 0.0,
        "renewable_share_pct": 100.0 * ren_used / demand if demand else 0.0,
        "curtailed_mwh": curtailed,
        "energy_served_mwh": demand - unserved,
        "unserved_mwh": unserved,
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
        elif info["kind"] == "presence":
            blocks.append(html.Div("A: {}. B: {}.".format(
                info["before"], info["after"]),
                style={"fontSize": "13px", "color": "#666"}))
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


# Comparison charts

DELTA_TOL = 1e-6        # below this a delta counts as no change at all


def align_runs(agg_a, agg_b):
    """Restrict two aggregated runs to the periods they have in common."""
    common = pd.Index(sorted(set(agg_a["x"]) & set(agg_b["x"])), name="x")
    dropped = (len(agg_a) - len(common)) + (len(agg_b) - len(common))
    aligned_a = agg_a.set_index("x").reindex(common).reset_index()
    aligned_b = agg_b.set_index("x").reindex(common).reset_index()
    return aligned_a, aligned_b, dropped


def dropped_note(dropped):
    if not dropped:
        return ""
    return "  -  {} period(s) outside the overlap not shown".format(dropped)


def plant_delta(a, b, agg_a, agg_b, plant):
    def series(run, agg):
        if plant not in run.meta:
            return pd.Series(0.0, index=agg.index)
        col = run.meta[plant]["column"]
        if col not in agg.columns:
            return pd.Series(0.0, index=agg.index)
        return agg[col].fillna(0.0)
    return series(b, agg_b).values - series(a, agg_a).values


def annotate_no_change(fig, message):
    fig.add_annotation(text=message, showarrow=False, xref="paper", yref="paper",
                       x=0.5, y=0.5, font=dict(size=13, color="#666666"))
    fig.update_yaxes(range=[-1, 1])
    return fig


def fig_compare_generation(a, b, lo, hi, resolution, plants):

    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty or agg_b.empty:
        return empty_figure("No overlapping hours to compare")

    agg_a, agg_b, dropped = align_runs(agg_a, agg_b)
    if agg_a.empty:
        return empty_figure("The two runs share no periods in this window")

    order = list(a.plant_order) + [p for p in b.plant_order
                                   if p not in a.meta]
    shown = [p for p in order if p in plants]
    if not shown:
        return empty_figure("No plants selected")

    deltas = {p: plant_delta(a, b, agg_a, agg_b, p) for p in shown}
    net = np.sum(list(deltas.values()), axis=0)
    biggest = max((np.abs(v).max() for v in deltas.values()), default=0.0)

    use_bars = len(agg_a) <= BAR_THRESHOLD

    fig = go.Figure()
    if use_bars:
        for p in shown:
            meta = a.meta.get(p) or b.meta[p]
            fig.add_trace(go.Bar(x=agg_a["x"], y=deltas[p], name=p,
                                 marker_color=meta["colour"]))
        fig.update_layout(barmode="relative", bargap=0.05)

    net_name = "Net change" if len(shown) == len(order) else "Net change (shown plants)"
    fig.add_trace(go.Scatter(
        x=agg_a["x"], y=net, name=net_name, mode="lines",
        line=dict(color=C_NEUTRAL, width=1.8,
                  shape="hvh" if resolution == "hourly" else "linear")))

    fig.add_hline(y=0, line=dict(color="#333333", width=1))

    if use_bars:
        detail = "per plant"
    else:
        detail = "net only above {} periods, choose daily or weekly for the " \
                 "per-plant breakdown".format(BAR_THRESHOLD)
    title = "Change in generation, B minus A ({}){}".format(
        detail, dropped_note(dropped))
    fig = base_layout(fig, title, axis_label(resolution),
                      "Change in {}".format(energy_label(resolution).lower()))

    if biggest < DELTA_TOL and np.abs(net).max() < DELTA_TOL:
        annotate_no_change(fig, "No change: both runs generate identically here")
    return fig


def stack_ceiling(run, agg, plants):
    """Tallest the selected stack, or demand, gets in one aggregated run."""
    if agg.empty:
        return 0.0
    cols = [run.meta[p]["column"] for p in run.plant_order
            if p in plants and run.meta[p]["column"] in agg.columns]
    tallest = float(agg[cols].sum(axis=1).max()) if cols else 0.0
    if DEMAND_COL in agg.columns:
        tallest = max(tallest, float(agg[DEMAND_COL].max()))
    return tallest


def price_ceiling(agg):
    """Highest price in one aggregated run, for the right-hand axis."""
    if agg.empty or PRICE_COL not in agg.columns:
        return 0.0
    return float(agg[PRICE_COL].max())


# Overlays that mean anything on a dispatch stack. "mclines" and "stack" are
# price-chart overlays, and the comparison has its own price section, so they
# are dropped rather than drawn on a generation axis where they have no units.
DISPATCH_OVERLAYS = ("demand", "price")


def fig_compare_dispatch_pair(a, b, lo, hi, resolution, plants, overlays):
    "The two dispatch stacks as one figure of two panels, sharing a legend"
    
    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty and agg_b.empty:
        return empty_figure("No hours in the selected range", PAIR_H)

    overlays = [o for o in (overlays or []) if o in DISPATCH_OVERLAYS]
    show_price = "price" in overlays

    fig = make_subplots(
        rows=1, cols=2,
        shared_yaxes=True, horizontal_spacing=0.06,
        specs=[[{"secondary_y": True}, {"secondary_y": True}]],
        subplot_titles=("A - {}".format(a.name), "B - {}".format(b.name)),
    )

    seen_groups = set()
    for col, (run, agg) in enumerate(((a, agg_a), (b, agg_b)), start=1):
        if agg.empty:
            continue

        for trace, on_price_axis in dispatch_traces(
                run, agg, plants, overlays, resolution,
                stackgroup="stack-{}".format(col)):
            trace.update(showlegend=trace.legendgroup not in seen_groups)
            seen_groups.add(trace.legendgroup)
            fig.add_trace(trace, row=1, col=col, secondary_y=on_price_axis)

    if dispatch_mode(agg_a) and dispatch_mode(agg_b):
        fig.update_layout(barmode="stack", bargap=0)

    fig.update_xaxes(title_text=axis_label(resolution), row=1, col=1)
    fig.update_xaxes(title_text=axis_label(resolution), row=1, col=2)
    fig.update_yaxes(title_text=energy_label(resolution),
                     row=1, col=1, secondary_y=False)

    ceiling = max(stack_ceiling(a, agg_a, plants),
                  stack_ceiling(b, agg_b, plants))
    for col in (1, 2):
        fig.update_yaxes(gridcolor=GRID, zeroline=False, row=1, col=col,
                         secondary_y=False,
                         range=[0, ceiling * 1.05] if ceiling > 0 else None)
        fig.update_xaxes(gridcolor=GRID, zeroline=False, row=1, col=col)
        # Grid off on the price axis so it does not cross-hatch the stack.
        fig.update_yaxes(showgrid=False, zeroline=False, visible=show_price,
                         rangemode="tozero", row=1, col=col, secondary_y=True)

    if show_price:
        fig.update_yaxes(title_text="Price ($/MWh)", row=1, col=2,
                         secondary_y=True)
        top = max(price_ceiling(agg_a), price_ceiling(agg_b))
        if top > 0:
            for col in (1, 2):
                fig.update_yaxes(range=[0, top * 1.05], row=1, col=col,
                                 secondary_y=True)

    fig.update_layout(
        title=dict(text=dispatch_title(agg_a if not agg_a.empty else agg_b),
                   x=0.01, y=0.98, yanchor="top", yref="container",
                   font=dict(size=15)),
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PLOT_BG,
        margin=dict(l=60, r=65, t=PAIR_MARGIN_TOP, b=45),
        height=PAIR_H,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.10,
                    xanchor="left", x=0,

                    groupclick="togglegroup"),
    )

    for note in fig.layout.annotations:
        note.update(font=dict(size=13), yshift=6)
    return fig


def load_weighted_price(agg):
    if agg.empty or DEMAND_COL not in agg.columns:
        return 0.0
    demand = float(agg[DEMAND_COL].sum())
    if not demand:
        return 0.0
    return float((agg[PRICE_COL] * agg[DEMAND_COL]).sum()) / demand


def fig_compare_price_overlay(a, b, lo, hi, resolution):
    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty or agg_b.empty:
        return empty_figure("No overlapping hours to compare", CHART_H_THIN)


    shape = "hvh" if resolution == "hourly" else "linear"

    fig = go.Figure()
    for run_agg, tag, colour, dash in ((agg_a, "A", C_RUN_A, None),
                                       (agg_b, "B", C_RUN_B, "dash")):

        name = "{} price (avg ${:,.2f}/MWh)".format(
            tag, load_weighted_price(run_agg))
        fig.add_trace(go.Scatter(
            x=run_agg["x"], y=run_agg[PRICE_COL], name=name, mode="lines",

            line=dict(color=colour, width=1.8, shape=shape, dash=dash),
            hovertemplate="$%{y:,.2f}/MWh<extra>" + tag + "</extra>"))

    ylab = ("Clearing price ($/MWh)" if resolution == "hourly"
            else "Load-weighted avg price ($/MWh)")
    return base_layout(fig, "Market clearing price: A and B",
                       axis_label(resolution), ylab, height=CHART_H_THIN)


def fig_compare_price_diff(a, b, lo, hi, resolution):
    agg_a = aggregate(a, slice_hours(a, lo, hi), resolution)
    agg_b = aggregate(b, slice_hours(b, lo, hi), resolution)
    if agg_a.empty or agg_b.empty:
        return empty_figure("No overlapping hours to compare", CHART_H_THIN)

    shape = "hvh" if resolution == "hourly" else "linear"

    agg_a, agg_b, dropped = align_runs(agg_a, agg_b)
    if agg_a.empty:
        return empty_figure("The two runs share no periods in this window",
                            CHART_H_THIN)

    diff = agg_b[PRICE_COL].values - agg_a[PRICE_COL].values

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agg_a["x"], y=diff, name="B minus A", mode="lines",
        fill="tozeroy", fillcolor="rgba(102, 102, 102, 0.18)",
        line=dict(color=C_NEUTRAL, width=1.6, shape=shape),
        hovertemplate="$%{y:,.2f}/MWh<extra>B minus A</extra>"))
    fig.add_hline(y=0, line=dict(color="#333333", width=1))
    fig.update_layout(showlegend=False)

    fig = base_layout(fig, "Change in clearing price, B minus A{}".format(
                          dropped_note(dropped)),
                      axis_label(resolution), "Change ($/MWh)",
                      height=CHART_H_THIN)


    reach = float(np.abs(diff).max()) if len(diff) else 0.0
    if reach < DELTA_TOL:
        annotate_no_change(fig, "No change: the two runs price identically here")
    else:
        fig.update_yaxes(range=[-reach * 1.15, reach * 1.15])
    return fig


def compare_plants_table(a, b, lo, hi, plants):
    ha, hb = slice_hours(a, lo, hi), slice_hours(b, lo, hi)

    order = list(a.plant_order) + [p for p in b.plant_order if p not in a.meta]
    rows = []
    for p in order:
        if p not in plants:
            continue
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

            "_direction": ("up" if delta is not None and delta > DELTA_TOL else
                           "down" if delta is not None and delta < -DELTA_TOL else
                           "flat"),
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

            style_data_conditional=[
                {"if": {"column_id": "Change",
                        "filter_query": "{_direction} = up"},
                 "color": C_RUN_B, "fontWeight": "600"},
                {"if": {"column_id": "Change",
                        "filter_query": "{_direction} = down"},
                 "color": C_RUN_A, "fontWeight": "600"},
            ],
        ),
    ])


def build_comparison(a, b, lo, hi, resolution, plants, overlays):
    ka, kb = window_kpis(a, lo, hi), window_kpis(b, lo, hi)

    cards = []
    if ka and kb:
        for key, label, unit, better in COMPARE_KPIS:
            if key in ka and key in kb:
                cards.append(delta_card(label, ka[key], kb[key], unit, better))

    return (compare_attribution(a, b),
            cards,
            compare_inputs_table(a, b),
            fig_compare_dispatch_pair(a, b, lo, hi, resolution,
                                      plants, overlays),
            fig_compare_generation(a, b, lo, hi, resolution, plants),
            fig_compare_price_overlay(a, b, lo, hi, resolution),
            fig_compare_price_diff(a, b, lo, hi, resolution),
            compare_plants_table(a, b, lo, hi, plants))


# Callbacks

@app.callback(
    Output("run-select", "options"),
    Output("run-compare", "options"),
    Output("run-compare", "value"),
    Input("run-refresh", "n_clicks"),
    Input("run-select", "value"),
    State("run-compare", "value"),
)
def refresh_run_lists(_clicks, selected, current_compare):
    """Keep both dropdowns in step with what is on disk."""
    options = run_options()
    compare = [o for o in options if o["value"] != selected]


    value = current_compare
    if value == selected:
        value = previous_run_id(options, selected)
    return options, compare, value


def previous_run_id(options, selected):
    values = [o["value"] for o in options]
    if selected not in values:
        return None
    for candidate in values[values.index(selected) + 1:]:
        if candidate != CURRENT_ID:
            return candidate
    return None



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
    Output("graph-storage", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
)
def update_storage(rng, resolution):
    run = get_run(rng.get("run"))
    return fig_storage(run, slice_hours(run, rng["lo"], rng["hi"]), resolution)


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

#def update_load_duration(rng, plants):
 #   run = get_run(rng.get("run"))
   # return fig_load_duration(run, slice_hours(run, rng["lo"], rng["hi"]),
   #                         plants or [])


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
    """QA respects the hour range but ignores the resolution dropdown."""
    run = get_run(rng.get("run"))
    hourly = slice_hours(run, rng["lo"], rng["hi"])
    qa = run_qa(run, hourly)
    return (qa_banner(qa), fig_qa_price(run, hourly), fig_qa_states(run, qa),
            qa_violations_table(qa))


@app.callback(
    Output("compare-attribution", "children"),
    Output("compare-kpis", "children"),
    Output("compare-inputs", "children"),
    Output("graph-compare-dispatch-pair", "figure"),
    Output("graph-compare-dispatch", "figure"),
    Output("graph-compare-price", "figure"),
    Output("graph-compare-price-diff", "figure"),
    Output("compare-plants", "children"),
    Input("store-range", "data"),
    Input("resolution", "value"),
    Input("plant-toggle", "value"),
    Input("overlay-toggle", "value"),
)
def update_compare(rng, resolution, plants, overlays):
    run_id, compare_id = rng.get("run"), rng.get("compare")
    if not compare_id:
        msg = html.Div("Pick a run in 'Compare with' above to see a comparison.",
                       style={"color": "#666"})
        blank = empty_figure("No comparison run selected")
        return (msg, [], html.Div(),
                blank, blank, blank, blank,
                html.Div())

    a = get_run(run_id)
    b = get_run(compare_id)
    return build_comparison(a, b, rng["lo"], rng["hi"], resolution,
                            plants or [], overlays or [])



# Main

if __name__ == "__main__":
    print("\nDispatch Model Dashboard")
    print("  opening on: {} plants, hours {} to {}".format(
        len(INITIAL_RUN.plant_order), INITIAL_RUN.hour_min, INITIAL_RUN.hour_max))
    print("  A: {}".format(INITIAL_RUN.name))
    print("  B: {}".format(get_run(DEFAULT_B).name if DEFAULT_B
                           else "none (fewer than two archived runs)"))
    print("  {} archived run(s) available".format(len(runstore.list_runs())))
    print("  Open http://127.0.0.1:8050 in your browser")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=False, port=8050)
