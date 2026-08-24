"""
Dispatch Model Dashboard
========================

An interactive Dash app for exploring the output of MFDM.py.

Run MFDM.py first to produce dispatch_results.csv and plant_summary.csv, then:

    python dashboard.py

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


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent
RESULTS_FILE = DATA_DIR / "dispatch_results.csv"
SUMMARY_FILE = DATA_DIR / "plant_summary.csv"

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


def load_outputs():
    """Read the two CSVs written by MFDM.py."""
    missing = [f.name for f in (RESULTS_FILE, SUMMARY_FILE) if not f.exists()]
    if missing:
        raise SystemExit(
            "ERROR: missing {}.\n"
            "Run MFDM.py first to generate dispatch_results.csv and "
            "plant_summary.csv.".format(" and ".join(missing))
        )

    results = pd.read_csv(RESULTS_FILE)
    summary = pd.read_csv(SUMMARY_FILE, keep_default_na=False)

    # Plant order, colours and reference values all come from the summary
    # file, so adding a plant to plants.csv flows through with no edits here.
    summary = summary.sort_values("Marginal Cost ($/MWh)").reset_index(drop=True)

    meta = {}
    seen_tech = {}
    for i, row in summary.iterrows():
        tech = row["Technology"]

        # A fleet can hold several plants of the same technology, for example
        # a mid-merit gas plant and a gas peaker. They must not share a colour
        # or they are indistinguishable in the stack, so repeats are shaded
        # progressively lighter while staying recognisably that technology.
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
            "profiled": bool(row["Profiled"]) if "Profiled" in summary.columns else False,
            "colour": colour,
            "column": "{} (MWh)".format(row["Plant"]),
            # Hourly limit. Falls back to nameplate for older results files
            # that predate the availability columns.
            "avail_column": avail_col if avail_col in results.columns else None,
        }

    # Merit order, cheapest first.
    plant_order = list(summary["Plant"])

    return results, summary, meta, plant_order


RESULTS, SUMMARY, META, PLANT_ORDER = load_outputs()
HOUR_MIN = int(RESULTS["Hour"].min())
HOUR_MAX = int(RESULTS["Hour"].max())
HAS_SHADOW = SHADOW_COL in RESULTS.columns


# --------------------------------------------------------------------------
# Filtering and aggregation
# --------------------------------------------------------------------------

def slice_hours(lo, hi):
    """Rows within the selected hour window, always at hourly resolution."""
    mask = (RESULTS["Hour"] >= lo) & (RESULTS["Hour"] <= hi)
    return RESULTS.loc[mask].copy()


def aggregate(df, resolution):
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

    sum_cols = [META[p]["column"] for p in PLANT_ORDER]
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
    if HAS_SHADOW:
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

def fig_dispatch(agg, plants, overlays, resolution):
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
    for p in PLANT_ORDER:
        if p not in plants:
            continue
        m = META[p]
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
        shape = "hv" if resolution == "hourly" else "linear"
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


def fig_price(agg, overlays, resolution):
    if agg.empty:
        return empty_figure("No hours in the selected range")

    fig = go.Figure()
    # Price is piecewise constant at hourly resolution, so draw it as a step.
    # Once averaged it is no longer a step function, so use a plain line.
    shape = "hv" if resolution == "hourly" else "linear"

    fig.add_trace(go.Scatter(
        x=agg["x"], y=agg[PRICE_COL],
        name="Clearing price", mode="lines",
        line=dict(color=C_PRICE, width=1.8, shape=shape),
        hovertemplate="$%{y:,.2f}/MWh<extra>Clearing price</extra>",
    ))

    if "shadow" in overlays and HAS_SHADOW:
        fig.add_trace(go.Scatter(
            x=agg["x"], y=agg[SHADOW_COL],
            name="Shadow price (dual)", mode="lines",
            line=dict(color=C_SHADOW, width=1.2, dash="dot", shape=shape),
            hovertemplate="$%{y:,.2f}/MWh<extra>Shadow price</extra>",
        ))

    if "mclines" in overlays:
        for p in PLANT_ORDER:
            m = META[p]
            fig.add_hline(
                y=m["marginal_cost"], line=dict(color=m["colour"], width=1, dash="dot"),
                annotation_text="{} ${:.2f}".format(p, m["marginal_cost"]),
                annotation_position="right",
                annotation_font=dict(size=10, color=m["colour"]),
            )

    ylab = ("Clearing price ($/MWh)" if resolution == "hourly"
            else "Load-weighted avg price ($/MWh)")
    return base_layout(fig, "Market clearing price", axis_label(resolution), ylab)


def fig_costs(agg, resolution):
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


def fig_price_duration(hourly):
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


def fig_load_duration(hourly, plants):
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
    for p in PLANT_ORDER:
        if p not in plants:
            continue
        cumulative += META[p]["capacity"]
        fig.add_hline(
            y=cumulative, line=dict(color=META[p]["colour"], width=1.4, dash="dash"),
            annotation_text="through {} = {:,.0f} MW".format(p, cumulative),
            annotation_position="right",
            annotation_font=dict(size=10, color=META[p]["colour"]),
        )

    fig.update_layout(showlegend=False)
    return base_layout(fig, "Load duration curve vs cumulative capacity (hourly)",
                       "Percent of hours (%)", "Demand (MWh)")


def fig_energy_mix(hourly, plants):
    if hourly.empty or not plants:
        return empty_figure("No plants selected")

    n_hours = len(hourly)
    total_demand = hourly[DEMAND_COL].sum()

    names, values, colours, labels = [], [], [], []
    for p in PLANT_ORDER:
        if p not in plants:
            continue
        m = META[p]
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

QA_TOL = 1e-4          # $/MWh and MWh tolerance for declaring a violation
MAX_VIOLATION_ROWS = 100

STATE_PART = "Part loaded"
STATE_FULL = "At capacity"
STATE_IDLE = "Idle"
STATE_UNAVAIL = "No resource"
STATE_COLOURS = {STATE_PART: C_PRICE, STATE_FULL: C_SHADOW,
                 STATE_IDLE: "#BDC3C7", STATE_UNAVAIL: "#EAECEE"}


def run_qa(hourly):
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
    if HAS_SHADOW:
        diff = (price - hourly[SHADOW_COL]).abs()
        out["max_price_diff"] = float(diff.max())
        out["price_mismatch"] = int((diff > QA_TOL).sum())

    # --- check 3: does every price correspond to some plant? ---
    mcs = [round(META[p]["marginal_cost"], 6) for p in PLANT_ORDER]
    out["unexplained_price"] = int((~price.round(6).isin(mcs)).sum())

    # --- check 2: per plant-hour optimality conditions ---
    for p in PLANT_ORDER:
        m = META[p]
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


def fig_qa_price(hourly):
    """Clearing price against the LP dual, with their difference on the right
    axis. On a correct model the difference line sits flat on zero."""
    if hourly.empty:
        return empty_figure("No hours in the selected range")
    if not HAS_SHADOW:
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


def fig_qa_states(qa):
    """Hours each plant spends part loaded, at capacity and idle.

    The part-loaded count should equal the plant's price-setting hours,
    because the marginal plant is by definition the part-loaded one.
    """
    if not qa["states"]:
        return empty_figure("No hours in the selected range")

    plants = [p for p in PLANT_ORDER if p in qa["states"]]
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
                META[p]["marginal_cost"], qa["rents"][p]),
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


def build_kpis(hourly):
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

slider_marks = {h: str(h) for h in range(HOUR_MIN - 1, HOUR_MAX + 1, 72) if h >= HOUR_MIN}
slider_marks[HOUR_MIN] = str(HOUR_MIN)
slider_marks[HOUR_MAX] = str(HOUR_MAX)

app.layout = html.Div([
    html.Div([
        html.H2("Dispatch Model Dashboard",
                style={"margin": "0 0 2px 0", "fontSize": "23px"}),
        html.Div("Least-cost economic dispatch - results from MFDM.py",
                 style={"color": "#666", "fontSize": "13px"}),
    ], style={"marginBottom": "14px"}),

    html.Div(id="kpi-row", style={"display": "flex", "gap": "10px",
                                  "flexWrap": "wrap", "marginBottom": "14px"}),

    # ---- controls ----
    html.Div([
        html.Div([
            html.Div([
                html.Label("Hour range", style={"fontWeight": "600", "fontSize": "13px"}),
                dcc.RangeSlider(
                    id="hour-range", min=HOUR_MIN, max=HOUR_MAX, step=1,
                    value=[HOUR_MIN, HOUR_MAX], marks=slider_marks,
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
                    options=[{"label": " {} ({}) ${:.2f}/MWh".format(
                        p, META[p]["technology"], META[p]["marginal_cost"]), "value": p}
                        for p in PLANT_ORDER],
                    value=list(PLANT_ORDER),
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
    ]),

    dcc.Store(id="store-range"),
], style={"fontFamily": "Segoe UI, Helvetica, Arial, sans-serif",
          "backgroundColor": "#F4F5F7", "padding": "18px", "minHeight": "100vh"})


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------

@app.callback(
    Output("hour-range", "value"),
    Input("preset-day", "n_clicks"),
    Input("preset-week", "n_clicks"),
    Input("preset-all", "n_clicks"),
    prevent_initial_call=True,
)
def apply_preset(_day, _week, _all):
    """Preset buttons write into the range slider."""
    triggered = callback_context.triggered
    if not triggered:
        return [HOUR_MIN, HOUR_MAX]
    which = triggered[0]["prop_id"].split(".")[0]
    if which == "preset-day":
        return [HOUR_MIN, min(HOUR_MIN + HOURS_PER_DAY - 1, HOUR_MAX)]
    if which == "preset-week":
        return [HOUR_MIN, min(HOUR_MIN + HOURS_PER_WEEK - 1, HOUR_MAX)]
    return [HOUR_MIN, HOUR_MAX]


@app.callback(
    Output("store-range", "data"),
    Input("hour-range", "value"),
)
def store_range(hour_range):
    """Single source of truth for the selected window."""
    lo, hi = int(hour_range[0]), int(hour_range[1])
    return {"lo": lo, "hi": hi}


@app.callback(
    Output("kpi-row", "children"),
    Input("store-range", "data"),
)
def update_kpis(rng):
    return build_kpis(slice_hours(rng["lo"], rng["hi"]))


@app.callback(
    Output("graph-dispatch", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
    Input("plant-toggle", "value"),
    Input("overlay-toggle", "value"),
)
def update_dispatch(rng, resolution, plants, overlays):
    hourly = slice_hours(rng["lo"], rng["hi"])
    return fig_dispatch(aggregate(hourly, resolution), plants or [],
                        overlays or [], resolution)


@app.callback(
    Output("graph-price", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
    Input("overlay-toggle", "value"),
)
def update_price(rng, resolution, overlays):
    hourly = slice_hours(rng["lo"], rng["hi"])
    return fig_price(aggregate(hourly, resolution), overlays or [], resolution)


@app.callback(
    Output("graph-costs", "figure"),
    Input("store-range", "data"),
    Input("resolution", "value"),
)
def update_costs(rng, resolution):
    hourly = slice_hours(rng["lo"], rng["hi"])
    return fig_costs(aggregate(hourly, resolution), resolution)


@app.callback(
    Output("graph-price-duration", "figure"),
    Input("store-range", "data"),
)
def update_price_duration(rng):
    return fig_price_duration(slice_hours(rng["lo"], rng["hi"]))


@app.callback(
    Output("graph-load-duration", "figure"),
    Input("store-range", "data"),
    Input("plant-toggle", "value"),
)
def update_load_duration(rng, plants):
    return fig_load_duration(slice_hours(rng["lo"], rng["hi"]), plants or [])


@app.callback(
    Output("graph-energy-mix", "figure"),
    Input("store-range", "data"),
    Input("plant-toggle", "value"),
)
def update_energy_mix(rng, plants):
    return fig_energy_mix(slice_hours(rng["lo"], rng["hi"]), plants or [])


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
    hourly = slice_hours(rng["lo"], rng["hi"])
    qa = run_qa(hourly)
    return (qa_banner(qa), fig_qa_price(hourly), fig_qa_states(qa),
            qa_violations_table(qa))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nDispatch Model Dashboard")
    print("  {} plants, hours {} to {}".format(len(PLANT_ORDER), HOUR_MIN, HOUR_MAX))
    print("  Open http://127.0.0.1:8050 in your browser")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=False, port=8050)
