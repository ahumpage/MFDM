from pathlib import Path
import argparse
import sys
import time

import numpy as np
import pandas as pd
import pulp

# runstore lives in run_archive/, a sibling folder rather than a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "run_archive"))
import runstore


# Configuration

BASE_DIR = Path(__file__).resolve().parent          # model/
REPO_ROOT = BASE_DIR.parent

INPUTS_DIR = REPO_ROOT / "inputs"
RESULTS_DIR = REPO_ROOT / "results"

# The five inputs the model reads. Each is a *role* - plants, fuel, demand,
# profiles, batteries - and the file filling it is chosen per run with the matching
# command line flag, so inputs/ can hold alternatives side by side. The
# defaults are the simple case: no ramp limits and no renewable profiles.
DEFAULT_INPUT_NAMES = {
    "plants": "plants_basic.csv",
    "fuel": "fuel.csv",
    "demand": "demand.csv",
    "profiles": "profiles_basic.csv",
    "battery": "battery.csv",
}

PLANTS_FILE = INPUTS_DIR / DEFAULT_INPUT_NAMES["plants"]
FUEL_FILE = INPUTS_DIR / DEFAULT_INPUT_NAMES["fuel"]
DEMAND_FILE = INPUTS_DIR / DEFAULT_INPUT_NAMES["demand"]
PROFILE_FILE = INPUTS_DIR / DEFAULT_INPUT_NAMES["profiles"]
BATTERY_FILE = INPUTS_DIR / DEFAULT_INPUT_NAMES["battery"]

# Generation below this counts as "not running", so solver round-off cannot
# set the price.
TOL = 1e-6

# Value of Lost Load, $/MWh. Must stay well above every plant's marginal cost,
# or the solver sheds load rather than running that plant.
LoL = 8300.0

# What a spilled MWh costs. Deliberately not LoL; see
# docs/model_semantics.md#why-spill-is-priced-at-1000mwh-and-not-at-lol.
SPILL_COST = 1000.0

# A blank ramp rate in plants.csv means "no limit". Represented as a large
# multiple of nameplate rather than as infinity, so it survives the round trip
# through plant_summary.csv and into the dashboard.
UNLIMITED_RAMP_FACTOR = 1e6

# Technologies limited by an hourly resource profile. The value is the token
# looked for in the profiles.csv column headers.
PROFILE_TECHNOLOGIES = {
    "Wind": "wind",
    "Solar": "solar",
}


# Load data

def has_region_row(path):
    """Whether a profiles file leads with a region row.

    A region row has nothing in its first cell, because the column it heads is
    the hour column, whose name lives on the row below. A file that starts
    "hours,Wind,Solar" has no region row; one that starts ",FRA,FRA" does.
    """
    with open(str(path)) as fh:
        first = fh.readline()
    return first.lstrip("\ufeff").startswith(",")


def load_data():
    for path in (PLANTS_FILE, FUEL_FILE, DEMAND_FILE, PROFILE_FILE):
        if not path.exists():
            raise FileNotFoundError("Could not find input file: {}".format(path))

    # keep_default_na=False so Solar's fuel of "None" stays the literal string.
    plants = pd.read_csv(PLANTS_FILE, keep_default_na=False)
    fuel = pd.read_csv(FUEL_FILE)
    demand = pd.read_csv(DEMAND_FILE)

    # The profiles file may carry one header row or two. Two rows are a region
    # row above a series row, flattened to "FRA wind (won)" so a multi-region
    # file stays unambiguous. One row is just the series names, which is the
    # single-region case; there is no region to prefix, so the names are used
    # as they stand. The region row is the one that starts with an empty cell,
    # because its first column heading sits on the row below.
    profile = pd.read_csv(PROFILE_FILE, header=[0, 1] if has_region_row(PROFILE_FILE)
                                        else 0)
    if isinstance(profile.columns, pd.MultiIndex):
        flat = []
        for region, series in profile.columns:
            region = "" if str(region).startswith("Unnamed") else str(region).strip()
            series = str(series).strip()
            flat.append("{} {}".format(region, series).strip())
        profile.columns = flat

    for df in (plants, fuel, demand, profile):
        df.columns = [c.strip() for c in df.columns]
    for col in ("Plant", "Technology", "Fuel"):
        plants[col] = plants[col].astype(str).str.strip()
    fuel["Technology"] = fuel["Technology"].astype(str).str.strip()

    battery = (pd.read_csv(BATTERY_FILE, keep_default_na=False)
               if BATTERY_FILE is not None and BATTERY_FILE.exists() else pd.DataFrame(
                   columns=["Battery", "Power (MW)", "Capacity (MWh)",
                            "Efficiency (MWh/MWhEl)"]))
    for df in (plants, fuel, demand, profile, battery):
        df.columns = [c.strip() for c in df.columns]
    if not battery.empty:
        battery["Battery"] = battery["Battery"].astype(str).str.strip()

    return plants, fuel, demand, profile, battery


# Parameters

def build_parameters(plants, fuel, demand, profile, battery):

    # --- sets ---
    PLANTS = list(plants["Plant"])
    BATTERIES = list(battery["Battery"])
    HOURS = [int(h) for h in demand["Hour"]]
    check_horizon(HOURS)
    if len(set(BATTERIES)) != len(BATTERIES) or any(not b for b in BATTERIES):
        raise ValueError("battery.csv battery names must be non-blank and unique")
    if set(BATTERIES) & set(PLANTS):
        raise ValueError("battery.csv names must not match plant names")

    battery_power = {}
    battery_capacity = {}
    battery_efficiency = {}
    for _, row in battery.iterrows():
        b = row["Battery"]
        battery_power[b] = float(row[find_column(battery, "Power", "battery.csv")])
        battery_capacity[b] = float(row[find_column(battery, "Capacity", "battery.csv")])
        battery_efficiency[b] = float(row[find_column(battery, "efficiency", "battery.csv")])
        if battery_power[b] <= 0 or battery_capacity[b] <= 0:
            raise ValueError("Battery {} has non-positive power or capacity".format(b))
        if not 0 < battery_efficiency[b] <= 1:
            raise ValueError("Battery {} has efficiency outside 0 to 1".format(b))

    # --- fuel prices, anything unlisted is free ---
    fuel_price = dict(zip(fuel["Technology"], fuel["Fuel Price ($/MWhTh)"].astype(float)))

    def price_of(fuel_name):
        if fuel_name is None:
            return 0.0
        if str(fuel_name).strip().lower() in ("none", "nan", ""):
            return 0.0
        if fuel_name not in fuel_price:
            print("  note: no fuel price listed for '{}', treating as $0/MWhTh".format(fuel_name))
            return 0.0
        return fuel_price[fuel_name]

    # --- per plant parameters ---
    capacity = {}
    efficiency = {}
    vom = {}
    technology = {}
    plant_fuel = {}
    marginal_cost = {}
    ramp_rate = {}
    ramp_efficiency = {}
    ramp_cost = {}

    rate_col = find_column(plants, "Ramp_rate", "plants.csv")
    ramp_eff_col = find_column(plants, "Ramp_efficiency", "plants.csv")

    for _, row in plants.iterrows():
        p = row["Plant"]
        capacity[p] = float(row["Capacity (MW)"])
        efficiency[p] = float(row["Efficiency (MWh/MWhTh)"])
        vom[p] = float(row["VOM ($/MWh)"])
        technology[p] = row["Technology"]
        plant_fuel[p] = row["Fuel"]

        # A blank ramp rate means the plant is unconstrained and never pays a
        # premium, so its ramping efficiency is its ordinary efficiency.
        if row[rate_col] is None or row[rate_col] == '':
            ramp_rate[p] = capacity[p] * UNLIMITED_RAMP_FACTOR
            ramp_efficiency[p] = efficiency[p]

        else:
            ramp_rate[p] = float(row[rate_col])
            ramp_efficiency[p] = float(row[ramp_eff_col])

        # The premium alone. VOM is excluded: it is charged on every MWh
        # either way, through marginal_cost.
        ramp_cost[p] = (price_of(row["Fuel"]) / ramp_efficiency[p] - price_of(row["Fuel"]) / efficiency[p])

        if efficiency[p] <= 0:
            raise ValueError("Plant {} has a non-positive efficiency".format(p))
        if ramp_efficiency[p] <= 0:
            raise ValueError(
                "Plant {} has a non-positive ramping efficiency".format(p))

        # Ramping is less efficient than steady running, never more. A better
        # ramping efficiency would make the premium negative and pay the
        # solver to jiggle the plant up and down.
        if ramp_efficiency[p] > efficiency[p] + TOL:
            raise ValueError(
                "Plant {} has a ramping efficiency ({:.4f}) better than its "
                "ordinary efficiency ({:.4f}). Ramping is less efficient than "
                "steady running, not more, so this would make the ramp premium "
                "negative and pay the solver to move the plant about."
                .format(p, ramp_efficiency[p], efficiency[p]))
        if ramp_rate[p] < 0:
            raise ValueError("Plant {} has a negative ramp rate".format(p))

        marginal_cost[p] = price_of(row["Fuel"]) / efficiency[p] + vom[p]

    # --- availability ---
    # One (n_plants, n_hours) array. Unprofiled plants keep a factor of 1.0.
    profile_factors = build_profile_factors(profile, technology, HOURS)

    cap_vec = np.array([capacity[p] for p in PLANTS], dtype=float)
    mc_vec = np.array([marginal_cost[p] for p in PLANTS], dtype=float)
    profiled_mask = np.array([p in profile_factors for p in PLANTS], dtype=bool)

    factors_matrix = np.ones((len(PLANTS), len(HOURS)), dtype=float)
    for i, p in enumerate(PLANTS):
        factors = profile_factors.get(p)
        if factors is not None:
            factors_matrix[i] = [factors[t] for t in HOURS]

    avail = cap_vec[:, None] * factors_matrix

    ramp_rate_vec = np.array([ramp_rate[p] for p in PLANTS], dtype=float)
    ramp_cost_vec = np.array([ramp_cost[p] for p in PLANTS], dtype=float)

    # Dict view, derived from `avail` so the two agree by construction.
    availability = {p: dict(zip(HOURS, avail[i]))
                    for i, p in enumerate(PLANTS)}

    # --- demand ---
    demand_col = [c for c in demand.columns if c.lower().startswith("demand")][0]
    demand_vec = demand[demand_col].astype(float).to_numpy()
    demand_by_hour = dict(zip(HOURS, demand_vec))

    return {
        "PLANTS": PLANTS,
        "BATTERIES": BATTERIES,
        "HOURS": HOURS,
        "capacity": capacity,
        "efficiency": efficiency,
        "vom": vom,
        "technology": technology,
        "plant_fuel": plant_fuel,
        "marginal_cost": marginal_cost,
        "ramp_rate": ramp_rate,
        "ramp_efficiency": ramp_efficiency,
        "ramp_cost": ramp_cost,
        "availability": availability,
        "profiled": set(profile_factors),
        "demand": demand_by_hour,
        "battery_power": battery_power,
        "battery_capacity": battery_capacity,
        "battery_efficiency": battery_efficiency,
        "avail": avail,
        "cap_vec": cap_vec,
        "mc_vec": mc_vec,
        "ramp_rate_vec": ramp_rate_vec,
        "ramp_cost_vec": ramp_cost_vec,
        "demand_vec": demand_vec,
        "profiled_mask": profiled_mask,
    }


def find_column(df, prefix, filename):
    """Locate the one column of `df` whose name starts with `prefix`."""
    matches = [c for c in df.columns if c.strip().lower().startswith(prefix.lower())]
    if not matches:
        raise ValueError(
            "{} has no column starting with '{}'. Columns present: {}"
            .format(filename, prefix, ", ".join(df.columns)))
    if len(matches) > 1:
        raise ValueError(
            "{} has more than one column starting with '{}': {}. "
            "Column names must be unambiguous.".format(filename, prefix, matches))
    return matches[0]


def check_horizon(HOURS):
    """Assert that HOURS is ascending, contiguous and free of duplicates."""
    if len(HOURS) < 1:
        raise ValueError("demand.csv contains no hours.")

    duplicates = sorted(set(h for h in HOURS if HOURS.count(h) > 1))
    if duplicates:
        raise ValueError(
            "demand.csv repeats {} hour(s), first {}. Each hour must appear "
            "once.".format(len(duplicates), duplicates[0]))

    breaks = [(HOURS[i - 1], HOURS[i]) for i in range(1, len(HOURS))
              if HOURS[i] != HOURS[i - 1] + 1]
    if breaks:
        a, b = breaks[0]
        raise ValueError(
            "demand.csv hours must be ascending and contiguous, but hour {} is "
            "followed by hour {} ({} such break(s) in total). Ramping links "
            "each hour to the previous row, so the horizon cannot have gaps or "
            "be out of order.".format(a, b, len(breaks)))


def build_profile_factors(profile, technology, HOURS):
    """Map each profiled plant to its hourly capacity factor; others run at nameplate."""
    hour_col = profile.columns[0]
    available_hours = set(int(h) for h in profile[hour_col])

    missing = [t for t in HOURS if t not in available_hours]
    if missing:
        raise ValueError(
            "profiles.csv is missing {} of the {} hours in demand.csv "
            "(first missing: hour {}).".format(len(missing), len(HOURS), missing[0]))

    idx = profile[hour_col].astype(int)
    sub = profile.set_index(idx).loc[HOURS]

    factors = {}
    for plant, tech in technology.items():
        token = PROFILE_TECHNOLOGIES.get(tech)
        if token is None:
            continue

        matches = [c for c in profile.columns
                   if c is not hour_col and token in c.lower()]
        if not matches:
            print("  note: technology '{}' has no profile column in profiles.csv, "
                  "treating {} as always available".format(tech, plant))
            continue
        if len(matches) > 1:
            raise ValueError(
                "Technology '{}' matches more than one profile column: {}. "
                "Column names must be unambiguous.".format(tech, matches))

        series = sub[matches[0]].astype(float)
        lo, hi = float(series.min()), float(series.max())
        if lo < -TOL or hi > 1.0 + TOL:
            raise ValueError(
                "Profile column '{}' has values outside 0 to 1 (min {:.4f}, "
                "max {:.4f}). Expected capacity factors.".format(matches[0], lo, hi))

        factors[plant] = {t: float(v) for t, v in zip(HOURS, series.values)}

    return factors


def warn_nonpositive_demand(params):
    zeros = [t for t in params["HOURS"] if params["demand"][t] <= 0.0]
    if zeros:
        shown = ", ".join(str(t) for t in zeros[:10])
        more = " and {} more".format(len(zeros) - 10) if len(zeros) > 10 else ""
        print("  WARNING: demand is zero or negative in {} hour(s): {}{}."
              .format(len(zeros), shown, more))
        print("           Check demand.csv. The model will dispatch nothing "
              "in those hours.\n")


def warn_capacity_shortfall(params):
    short = []
    for t in params["HOURS"]:
        total = sum(params["availability"][p][t] for p in params["PLANTS"])
        if total < params["demand"][t] - TOL:
            short.append((t, params["demand"][t], total))

    if short:
        t, d, a = short[0]
        worst = max(short, key=lambda r: r[1] - r[2])
        print("  WARNING: demand exceeds available capacity in {} of {} hour(s)."
              .format(len(short), len(params["HOURS"])))
        print("           First is hour {}: demand {:,.2f} MWh vs {:,.2f} MW available."
              .format(t, d, a))
        print("           Worst is hour {}, short by {:,.2f} MW."
              .format(worst[0], worst[1] - worst[2]))
        print("           The shortfall will be priced at ${:,.2f}/MWh (LoL). "
              "Check plants.csv and demand.csv.\n".format(LoL))


# Build and solve

def build_and_solve(params):

    PLANTS, BATTERIES, HOURS = params["PLANTS"], params["BATTERIES"], params["HOURS"]

    # Hour 1 has no predecessor, so it carries no ramp constraint and the
    # fleet starts wherever it likes free of charge.
    RAMP_HOURS = HOURS[1:]
    previous = {t: HOURS[i] for i, t in enumerate(HOURS[1:])}

    prob = pulp.LpProblem("Economic_Dispatch", pulp.LpMinimize)

    gen = pulp.LpVariable.dicts("gen", (PLANTS, HOURS), lowBound=0, cat="Continuous")
    unserved = pulp.LpVariable.dicts("unserved", HOURS, lowBound=0, cat="Continuous")
    spill = pulp.LpVariable.dicts("spill", HOURS, lowBound=0, cat="Continuous")
    charge = pulp.LpVariable.dicts("charge", (BATTERIES, HOURS), lowBound=0, cat="Continuous")
    discharge = pulp.LpVariable.dicts("discharge", (BATTERIES, HOURS), lowBound=0, cat="Continuous")
    soc = {b: {t: pulp.LpVariable("soc_{}_{}".format(b.replace(" ", "_"), t),
                                lowBound=0, upBound=params["battery_capacity"][b])
               for t in HOURS} for b in BATTERIES}

    # Movement split into two non-negative variables so its absolute size can
    # be priced linearly. The upper bound is the hard rate limit, which is why
    # no separate rate constraint is needed.
    ramp_up = {p: {t: pulp.LpVariable(
        "rampup_{}_{}".format(p.replace(" ", "_"), t),
        lowBound=0, upBound=params["ramp_rate"][p]) for t in RAMP_HOURS} for p in PLANTS}
    ramp_down = {p: {t: pulp.LpVariable(
        "rampdown_{}_{}".format(p.replace(" ", "_"), t),
        lowBound=0, upBound=params["ramp_rate"][p]) for t in RAMP_HOURS} for p in PLANTS}

    prob += (
        pulp.lpSum(params["marginal_cost"][p] * gen[p][t] for p in PLANTS for t in HOURS)
        + pulp.lpSum(LoL * unserved[t] for t in HOURS)
        + pulp.lpSum(SPILL_COST * spill[t] for t in HOURS)
        + pulp.lpSum(params["ramp_cost"][p] * (ramp_up[p][t] + ramp_down[p][t])
                     for p in PLANTS for t in RAMP_HOURS),
        "Total_Production_Cost",
    )

    # Energy balance, named so the dual can be pulled out after solving. Spill
    # enters negatively: it is generation that did not serve demand.
    for t in HOURS:
        prob += (
            (pulp.lpSum(gen[p][t] for p in PLANTS)
             + pulp.lpSum(discharge[b][t] for b in BATTERIES)
             + unserved[t] - spill[t]
             == params["demand"][t] + pulp.lpSum(charge[b][t] for b in BATTERIES)),
            "balance_{}".format(t),
        )

    for p in PLANTS:
        for t in HOURS:
            prob += (
                gen[p][t] <= params["availability"][p][t],
                "cap_{}_{}".format(p.replace(" ", "_"), t),
            )

    for b in BATTERIES:
        for i, t in enumerate(HOURS):
            prev = HOURS[i - 1]
            prob += (soc[b][t] - soc[b][prev]
                     == params["battery_efficiency"][b] * charge[b][t]
                     - discharge[b][t] * (1.0 / params["battery_efficiency"][b]),
                     "soc_{}_{}".format(b.replace(" ", "_"), t))
            prob += (charge[b][t] + discharge[b][t] <= params["battery_power"][b],
                     "battery_power_{}_{}".format(b.replace(" ", "_"), t))

    # Inequalities, so ramp_up and ramp_down are only pushed down to the true
    # movement by their cost. A plant with a zero premium leaves them free
    # anywhere up to the rate limit, which is why reported ramp quantities are
    # recomputed from the generation profile instead.
    for p in PLANTS:
        for t in RAMP_HOURS:
            prev = previous[t]
            prob += (
                gen[p][t] - gen[p][prev] <= ramp_up[p][t],
                "rampup_{}_{}".format(p.replace(" ", "_"), t),
            )
            prob += (
                gen[p][prev] - gen[p][t] <= ramp_down[p][t],
                "rampdown_{}_{}".format(p.replace(" ", "_"), t),
            )

    n_vars = (len(PLANTS) * len(HOURS)          # gen
               + 2 * len(HOURS)                   # unserved, spill
               + 3 * len(BATTERIES) * len(HOURS)  # charge, discharge, SoC
              + 2 * len(PLANTS) * len(RAMP_HOURS))  # ramp up and down
    print("Solving: {} variables, {} constraints ...".format(
        n_vars, len(prob.constraints)))
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        raise RuntimeError(
            "Solver did not reach an optimal solution (status: {}). "
            "The all-zeros dispatch always satisfies every constraint in this "
            "model - unserved demand is priced at LoL rather than forbidden, "
            "surplus can be spilled, and no plant has a lower bound above zero "
            "- so a feasible point always exists and this is a bug in how the "
            "LP is built rather than a problem with the input data."
            .format(status)
        )
    print("Solver status: {}\n".format(status))

    return prob, gen, unserved, spill, charge, discharge, soc


# Results

def build_hourly_results(params, prob, gen, unserved, spill, charge, discharge, soc):

    PLANTS, HOURS = params["PLANTS"], params["HOURS"]
    avail, mc_vec, demand_vec = params["avail"], params["mc_vec"], params["demand_vec"]

    # `or 0.0` guards against a None from an unused variable.
    output = np.array(
        [[gen[p][t].value() or 0.0 for t in HOURS] for p in PLANTS],
        dtype=float)

    unserved_vec = np.array([unserved[t].value() or 0.0 for t in HOURS], dtype=float)
    spill_vec = np.array([spill[t].value() or 0.0 for t in HOURS], dtype=float)

    # Recomputed from the generation profile, not read from the LP's ramp
    # variables. See docs/model_semantics.md. Column 0 is zero: hour 1 has no
    # predecessor, so nothing moved into it.
    delta = np.zeros_like(output)
    delta[:, 1:] = output[:, 1:] - output[:, :-1]
    ramp_up_arr = np.maximum(0.0, delta)
    ramp_down_arr = np.maximum(0.0, -delta)

    # The premium alone. The fuel and VOM under a ramped MWh are already in
    # Production Cost, so counting them here would double count.
    ramp_cost_vec = params["ramp_cost_vec"]
    ramp_cost_hourly = ramp_cost_vec @ (ramp_up_arr + ramp_down_arr)

    # Clearing price: the dual of the energy balance.
    price = []
    for t in HOURS:
        constraint = prob.constraints.get("balance_{}".format(t))
        pi = constraint.pi if constraint is not None else None
        price.append(float(pi) if pi is not None else np.nan)
    price = np.array(price, dtype=float)

    # Diagnostic, not a price. Non-running plants are masked to -inf rather
    # than 0 so a negative marginal cost could still be the highest; hours
    # with nothing running fall back to 0.0.
    running = output > TOL
    masked_mc = np.where(running, mc_vec[:, None], -np.inf)
    highest_running = np.where(running.any(axis=0), masked_mc.max(axis=0), 0.0)

    curtailed = np.maximum(0.0, avail - output)[params["profiled_mask"]].sum(axis=0)

    # This is the CSV column order. Availability is written out as well as
    # generation, because a profiled plant at its resource limit is at
    # capacity even though it is far below nameplate.
    columns = {"Hour": HOURS, "Demand (MWh)": demand_vec}
    for i, p in enumerate(PLANTS):
        columns["{} (MWh)".format(p)] = output[i]
    for i, p in enumerate(PLANTS):
        columns["{} Available (MWh)".format(p)] = avail[i]
    for b in params["BATTERIES"]:
        columns["{} Charge (MWh)".format(b)] = [charge[b][t].value() or 0.0 for t in HOURS]
        columns["{} Discharge (MWh)".format(b)] = [discharge[b][t].value() or 0.0 for t in HOURS]
        columns["{} State of Charge (MWh)".format(b)] = [soc[b][t].value() or 0.0 for t in HOURS]
    columns["Clearing Price ($/MWh)"] = price
    columns["Highest Running Cost ($/MWh)"] = highest_running
    columns["Production Cost ($)"] = mc_vec @ output
    columns["Ramp Up (MWh)"] = ramp_up_arr.sum(axis=0)
    columns["Ramp Down (MWh)"] = ramp_down_arr.sum(axis=0)
    columns["Ramp Cost ($)"] = ramp_cost_hourly
    columns["Market Cost ($)"] = price * demand_vec
    columns["Unserved Energy (MWh)"] = unserved_vec
    columns["Unserved Cost ($)"] = LoL * unserved_vec
    columns["Spill (MWh)"] = spill_vec
    columns["Spill Cost ($)"] = SPILL_COST * spill_vec
    columns["Curtailment (MWh)"] = curtailed

    if np.isnan(price).any():
        print("  WARNING: the solver returned no dual for {} of {} hours, so "
              "the clearing price is missing there.\n"
              .format(int(np.isnan(price).sum()), len(HOURS)))

    return pd.DataFrame(columns)


def build_plant_summary(params, results):

    n_hours = len(params["HOURS"])
    rows = []

    for p in params["PLANTS"]:
        series = results["{} (MWh)".format(p)]
        total = series.sum()
        max_possible = params["capacity"][p] * n_hours

        is_profiled = p in params["profiled"]
        available = sum(params["availability"][p][t] for t in params["HOURS"])

        # Idle thermal capacity is not curtailment, it is simply not being
        # called on, so only profiled plants can curtail.
        curtailed = max(0.0, available - total) if is_profiled else 0.0

        # Hour 1 has no predecessor, so the first difference is dropped.
        delta = series.to_numpy(dtype=float)[1:] - series.to_numpy(dtype=float)[:-1]
        ramp_up = float(np.maximum(0.0, delta).sum())
        ramp_down = float(np.maximum(0.0, -delta).sum())

        # Matched against the Highest Running Cost diagnostic, not the
        # clearing price, which is the dual and equals no plant's marginal
        # cost. Counts who was last in the merit order.
        is_running = series > TOL
        is_last = (results["Highest Running Cost ($/MWh)"]
                   - params["marginal_cost"][p]).abs() < 1e-6
        hours_last_in_stack = int((is_running & is_last).sum())

        rows.append({
            "Plant": p,
            "Technology": params["technology"][p],
            "Fuel": params["plant_fuel"][p],
            "Capacity (MW)": params["capacity"][p],
            "Profiled": is_profiled,
            "Marginal Cost ($/MWh)": params["marginal_cost"][p],
            "Ramp Rate (MW/hr)": params["ramp_rate"][p],
            "Ramping Efficiency (MWh/MWhTh)": params["ramp_efficiency"][p],
            "Ramp Premium ($/MWh)": params["ramp_cost"][p],
            "Total Generation (MWh)": total,
            "Available Energy (MWh)": available,
            "Curtailed (MWh)": curtailed,
            "Curtailment (%)": (100.0 * curtailed / available
                                if is_profiled and available > 0 else 0.0),
            "Share of Demand (%)": 100.0 * total / results["Demand (MWh)"].sum(),
            "Capacity Factor (%)": 100.0 * total / max_possible if max_possible else 0.0,
            "Availability Factor (%)": (100.0 * available / max_possible
                                        if max_possible else 0.0),
            "Hours Running": int(is_running.sum()),
            "Hours Last in Stack": hours_last_in_stack,
            "Total Ramp Up (MWh)": ramp_up,
            "Total Ramp Down (MWh)": ramp_down,
            # The premium only, so summing this column reproduces the
            # objective's ramp term exactly.
            "Ramp Cost ($)": params["ramp_cost"][p] * (ramp_up + ramp_down),
            # Fuel and VOM only, excluding ramp cost, so the four components
            # of the objective stay separable.
            "Production Cost ($)": total * params["marginal_cost"][p],
        })

    return pd.DataFrame(rows).sort_values("Marginal Cost ($/MWh)").reset_index(drop=True)


# Merit order

def dispatch_ceiling(params, output):
    """The most each plant could have generated in each hour."""
    ceiling = np.array(params["avail"], dtype=float, copy=True)
    reachable = output[:, :-1] + params["ramp_rate_vec"][:, None]
    ceiling[:, 1:] = np.minimum(ceiling[:, 1:], reachable)
    return ceiling


def dispatch_floor(params, output):
    """The least each plant could have generated in each hour."""
    floor = np.zeros_like(params["avail"])
    floor[:, 1:] = output[:, :-1] - params["ramp_rate_vec"][:, None]
    return np.maximum(0.0, floor)


def warn_merit_order_departures(params, results):
    """Print where the dispatch departs from merit order; a note, not a gate."""
    PLANTS, HOURS = params["PLANTS"], params["HOURS"]
    mc_vec = params["mc_vec"]

    # Rebuilt from the results table, so the check runs against the numbers
    # that were actually written out.
    output = np.array(
        [results["{} (MWh)".format(p)].to_numpy(dtype=float) for p in PLANTS])
    unserved_vec = results["Unserved Energy (MWh)"].to_numpy(dtype=float)

    ceiling = dispatch_ceiling(params, output)
    floor = dispatch_floor(params, output)

    # Recomputed rather than read from Clearing Price, which is the dual and
    # is not any plant's marginal cost. -inf when nothing is running makes the
    # comparison vacuously true, which is what it should be.
    running = output > TOL
    masked_mc = np.where(running, mc_vec[:, None], -np.inf)
    most_expensive = np.where(running.any(axis=0), masked_mc.max(axis=0), -np.inf)
    comparator = np.where(unserved_vec > TOL, LoL, most_expensive)

    undercut = mc_vec[:, None] < comparator - TOL     # something dearer is on
    underused = output < ceiling - TOL                # and this plant has room
    pinned = output <= floor + TOL                    # but cannot go lower
    flagged = undercut & underused & ~pinned

    if not flagged.any():
        return

    headroom = ceiling - output
    # An upper bound on any waste, not a bill: some headroom is legitimately
    # forgone to avoid a ramp premium.
    value = float((headroom * (comparator - mc_vec[:, None]))[flagged].sum())

    rows = []
    for i, t_index in zip(*np.nonzero(flagged)):
        rows.append({
            "hour": HOURS[t_index],
            "plant": PLANTS[i],
            "mc": mc_vec[i],
            "gen": output[i, t_index],
            "ceiling": ceiling[i, t_index],
            "headroom": headroom[i, t_index],
            "above": name_last_in_stack(params, comparator[t_index]),
        })
    rows.sort(key=lambda r: (r["hour"], r["plant"]))
    worst = max(rows, key=lambda r: r["headroom"])
    n_hours_affected = len(set(r["hour"] for r in rows))

    print("-" * 68)
    print("MERIT ORDER NOTE  ({} plant-hour(s) across {} hour(s))"
          .format(len(rows), n_hours_affected))
    print("-" * 68)
    print("  A plant generated below its ramp-adjusted ceiling while something")
    print("  more expensive was running. Under ramping this is often correct:")
    print("  holding back can be cheaper than paying to move, and a plant may")
    print("  stay low so that it can reach a low demand later. Worth a look,")
    print("  not proof of a bug.")
    print("  Cheap headroom left unused is worth at most ${:,.2f}.".format(value))
    print("")
    for r in rows[:10]:
        print("  hour {:>5}   {:<10} ${:>8.2f}/MWh   generated {:>9,.2f} of "
              "{:>9,.2f} MWh   ({:,.2f} MWh spare)   while {} was running"
              .format(r["hour"], r["plant"], r["mc"], r["gen"], r["ceiling"],
                      r["headroom"], r["above"]))
    if len(rows) > 10:
        print("  ... and {} more.".format(len(rows) - 10))
    print("")
    print("  Largest is hour {}: {} left {:,.2f} MWh unused.\n"
          .format(worst["hour"], worst["plant"], worst["headroom"]))


def name_last_in_stack(params, price):
    if abs(price - LoL) < TOL:
        return "unserved energy (LoL)"
    if abs(price + SPILL_COST) < TOL:
        return "spilled energy"
    for p in params["PLANTS"]:
        if abs(params["marginal_cost"][p] - price) < TOL:
            return p
    return "something at ${:,.2f}/MWh".format(price)


# Report

def report(params, results, summary, objective_value=None):
    print("-" * 68)
    print("MARGINAL COSTS  (fuel price / efficiency + VOM)")
    print("-" * 68)
    for _, r in summary.iterrows():
        print("  {:<10} {:<10} {:>7.1f} MW   ${:>7.2f}/MWh{}"
              .format(r["Plant"], str(r["Technology"]), r["Capacity (MW)"],
                      r["Marginal Cost ($/MWh)"],
                      "   (profiled)" if r["Profiled"] else ""))

    print("\n" + "-" * 68)
    print("RAMPING  (premium is the extra cost of a moved MWh over a steady one)")
    print("-" * 68)
    for _, r in summary.iterrows():
        print("  {:<10} rate {:>7.1f} MW/hr   ramp eff {:>5.3f}   "
              "premium ${:>7.2f}/MWh   moved {:>12,.1f} MWh   cost {:>14,.2f} $"
              .format(r["Plant"], r["Ramp Rate (MW/hr)"],
                      r["Ramping Efficiency (MWh/MWhTh)"], r["Ramp Premium ($/MWh)"],
                      r["Total Ramp Up (MWh)"] + r["Total Ramp Down (MWh)"],
                      r["Ramp Cost ($)"]))

    print("\n" + "-" * 68)
    print("DISPATCH SUMMARY")
    print("-" * 68)
    for _, r in summary.iterrows():
        print("  {:<10} {:>12,.1f} MWh   CF {:>5.1f}%   running {:>4} h   last in stack {:>4} h"
              .format(r["Plant"], r["Total Generation (MWh)"], r["Capacity Factor (%)"],
                      r["Hours Running"], r["Hours Last in Stack"]))

    profiled = summary[summary["Profiled"]]
    if not profiled.empty:
        print("\n" + "-" * 68)
        print("RENEWABLE RESOURCE  (capacity factor is after curtailment)")
        print("-" * 68)
        for _, r in profiled.iterrows():
            print("  {:<10} resource {:>5.1f}%   used {:>5.1f}%   "
                  "available {:>10,.1f} MWh   curtailed {:>8,.1f} MWh ({:.1f}%)"
                  .format(r["Plant"], r["Availability Factor (%)"],
                          r["Capacity Factor (%)"], r["Available Energy (MWh)"],
                          r["Curtailed (MWh)"], r["Curtailment (%)"]))

    total_demand = results["Demand (MWh)"].sum()
    total_gen = summary["Total Generation (MWh)"].sum()
    prod_cost = results["Production Cost ($)"].sum()
    ramp_cost = results["Ramp Cost ($)"].sum()
    market_cost = results["Market Cost ($)"].sum()
    total_unserved = results["Unserved Energy (MWh)"].sum()
    unserved_cost = results["Unserved Cost ($)"].sum()
    total_spill = results["Spill (MWh)"].sum()
    spill_cost = results["Spill Cost ($)"].sum()
    objective = prod_cost + unserved_cost + ramp_cost + spill_cost

    print("\n" + "-" * 68)
    print("TOTALS OVER {} HOURS".format(len(results)))
    print("-" * 68)
    print("  Energy served              {:>16,.1f} MWh".format(total_demand - total_unserved))
    print("  Energy generated           {:>16,.1f} MWh".format(total_gen))
    if total_unserved > TOL:
        print("  Energy unserved            {:>16,.1f} MWh   ({:.2f}% of demand)"
              .format(total_unserved,
                      100.0 * total_unserved / total_demand if total_demand else 0.0))
    if total_spill > TOL:
        print("  Energy spilled             {:>16,.1f} MWh   ({:.2f}% of generation)"
              .format(total_spill,
                      100.0 * total_spill / total_gen if total_gen else 0.0))
    print("  Energy moved (ramping)     {:>16,.1f} MWh"
          .format(results["Ramp Up (MWh)"].sum() + results["Ramp Down (MWh)"].sum()))

    # Print all four components and then the sum, so the reconciliation is a
    # shown calculation rather than a claim.
    print("")
    print("  Production cost            {:>16,.2f} $      (fuel and VOM)".format(prod_cost))
    print("  Ramp cost                  {:>16,.2f} $      (premium on energy moved)"
          .format(ramp_cost))
    print("  Cost of unserved energy    {:>16,.2f} $      (LoL x unserved)"
          .format(unserved_cost))
    print("  Cost of spilled energy     {:>16,.2f} $      (spill price x spilled)"
          .format(spill_cost))
    print("  LP objective               {:>16,.2f} $      (the four above)"
          .format(objective))

    # Check that claim rather than assert it: if a cost is ever double counted
    # or dropped from a column, this is where it shows up.
    if objective_value is not None:
        drift = abs(objective - objective_value)
        if drift > max(1e-3, 1e-9 * abs(objective_value)):
            print("  WARNING: those four components sum to ${:,.2f} but the solver "
                  "minimised\n           ${:,.2f}, a difference of ${:,.2f}. One of "
                  "the cost columns is\n           wrong."
                  .format(objective, objective_value, drift))
        else:
            print("  {:<26} {:>16} {:<6} (reconciles with the solver)"
                  .format("", "", ""))
    print("")
    print("  Average production cost    {:>16,.2f} $/MWh".format(
        prod_cost / total_gen if total_gen else 0.0))
    print("  Total market cost          {:>16,.2f} $      (clearing price x demand)"
          .format(market_cost))
    print("  Time-weighted avg price    {:>16,.2f} $/MWh"
          .format(results["Clearing Price ($/MWh)"].mean()))
    print("  Load-weighted avg price    {:>16,.2f} $/MWh".format(market_cost / total_demand))
    print("  Market surplus             {:>16,.2f} $      (market - production)"
           .format(market_cost - prod_cost))
    if (results["Clearing Price ($/MWh)"] < -TOL).any():
        print("  note: the clearing price is negative in {} hour(s), so market cost "
              "there is\n        money paid to consumers to take power. See SPILL below."
              .format(int((results["Clearing Price ($/MWh)"] < -TOL).sum())))

    total_curtailed = results["Curtailment (MWh)"].sum()
    if params["profiled"]:
        avail = summary.loc[summary["Profiled"], "Available Energy (MWh)"].sum()
        used = summary.loc[summary["Profiled"], "Total Generation (MWh)"].sum()
        print("  Renewable energy used      {:>16,.1f} MWh   ({:.1f}% of demand)"
              .format(used, 100.0 * used / total_demand if total_demand else 0.0))
        print("  Renewable curtailed        {:>16,.1f} MWh   ({:.1f}% of available)"
              .format(total_curtailed,
                      100.0 * total_curtailed / avail if avail else 0.0))

    # Unserved energy and spill are both part of the balance, so they are
    # counted here too.
    total_charge = sum(results["{} Charge (MWh)".format(b)].sum()
                       for b in params["BATTERIES"])
    total_discharge = sum(results["{} Discharge (MWh)".format(b)].sum()
                          for b in params["BATTERIES"])
    gap = abs(total_gen + total_discharge + total_unserved - total_spill
              - total_demand - total_charge)
    print("\n  Energy balance check: |generation + discharge + unserved - spill - demand - charge| = "
          "{:.6f} MWh {}".format(gap, "OK" if gap < 1e-3 else "<-- PROBLEM"))

    if total_unserved > TOL:
        short = results[results["Unserved Energy (MWh)"] > TOL]
        print("\n" + "-" * 68)
        print("SCARCITY  ({} hour(s) with unserved energy, priced at ${:,.2f}/MWh)"
              .format(len(short), LoL))
        print("-" * 68)
        for _, r in short.head(10).iterrows():
            unmet = r["Unserved Energy (MWh)"]
            print("  hour {:>5}   demand {:>10,.1f} MWh   served {:>10,.1f} MWh   "
                  "short {:>9,.1f} MWh".format(
                      int(r["Hour"]), r["Demand (MWh)"], r["Demand (MWh)"] - unmet, unmet))
        if len(short) > 10:
            print("  ... and {} more hour(s). See the Unserved Energy column in "
                  "dispatch_results.csv.".format(len(short) - 10))

    if total_spill > TOL:
        dumped = results[results["Spill (MWh)"] > TOL]
        print("\n" + "-" * 68)
        print("SPILL  ({} hour(s) with energy thrown away, priced at ${:,.2f}/MWh)"
              .format(len(dumped), SPILL_COST))
        print("-" * 68)
        print("  Generation that could not be shed fast enough to follow demand down.")
        for _, r in dumped.head(10).iterrows():
            over = r["Spill (MWh)"]
            print("  hour {:>5}   demand {:>10,.1f} MWh   generated {:>10,.1f} MWh   "
                  "spilled {:>9,.1f} MWh   price ${:>10,.2f}/MWh".format(
                      int(r["Hour"]), r["Demand (MWh)"], r["Demand (MWh)"] + over,
                      over, r["Clearing Price ($/MWh)"]))
        if len(dumped) > 10:
            print("  ... and {} more hour(s). See the Spill column in "
                  "dispatch_results.csv.".format(len(dumped) - 10))

    # The dual takes many distinct values, so summarise its distribution
    # rather than enumerating it.
    price = results["Clearing Price ($/MWh)"]
    print("\n  Clearing price (the dual of the energy balance):")
    print("    min {:>10,.2f}   median {:>10,.2f}   max {:>10,.2f}   "
          "{} distinct value(s)"
          .format(price.min(), price.median(), price.max(),
                  price.round(6).nunique()))

    print("\n  Hours each plant was last in the stack:")
    for _, r in summary.iterrows():
        if r["Hours Last in Stack"]:
            print("    {:<10} {:>5} h  ({:>5.1f}%)   at ${:>7.2f}/MWh"
                  .format(r["Plant"], r["Hours Last in Stack"],
                          100.0 * r["Hours Last in Stack"] / len(results),
                          r["Marginal Cost ($/MWh)"]))
    print("")


# Main

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Least-cost economic dispatch model.")
    parser.add_argument("--label", default=None,
                        help="short name for this run, used in the archive id")
    parser.add_argument("--notes", default=None,
                        help="longer description stored with the run")
    parser.add_argument("--no-archive", action="store_true",
                        help="solve and write results without archiving the run")
    parser.add_argument("--no-battery", action="store_true",
                        help="solve without battery storage")
    parser.add_argument("--inputs", default=None,
                        help="read the four input CSVs from here instead of inputs/. "
                             "Useful for running the worked examples in "
                             "docs/examples/ramping/.")
    parser.add_argument("--results", default=None,
                        help="write the result CSVs here instead of results/")
    for role, default in sorted(DEFAULT_INPUT_NAMES.items()):
        parser.add_argument("--" + role, default=None,
                            help="{} file to read: a name inside the input "
                                 "folder, or a path (default: {})"
                                 .format(role, default))
    return parser.parse_args(argv)


def use_directories(inputs=None, results=None):
    """Point the model at a different pair of input and output folders."""
    global INPUTS_DIR, RESULTS_DIR, PLANTS_FILE, FUEL_FILE, DEMAND_FILE, PROFILE_FILE, BATTERY_FILE
    if inputs is not None:
        INPUTS_DIR = Path(inputs).resolve()
        # A whole folder of inputs is expected to use the plain role names,
        # which is what the worked examples in docs/examples/ do. Individual
        # files can still be overridden on top by use_files.
        PLANTS_FILE = INPUTS_DIR / "plants.csv"
        FUEL_FILE = INPUTS_DIR / "fuel.csv"
        DEMAND_FILE = INPUTS_DIR / "demand.csv"
        PROFILE_FILE = INPUTS_DIR / "profiles.csv"
        BATTERY_FILE = INPUTS_DIR / "battery.csv"
    if results is not None:
        RESULTS_DIR = Path(results).resolve()


def resolve_input(name):
    """Turn one --plants/--fuel/--demand/--profiles value into a path.

    A bare file name is looked for in the input folder, so the usual case is
    just `--plants plants_ramping.csv`. A value with a directory part is taken
    as a path in its own right, which is what lets a file from outside inputs/
    be used without moving it there first.
    """
    path = Path(name)
    if path.parent == Path("."):
        path = INPUTS_DIR / path
    return path.resolve()


def use_files(plants=None, fuel=None, demand=None, profiles=None, battery=None):
    """Choose the file filling each input role, leaving the others alone."""
    global PLANTS_FILE, FUEL_FILE, DEMAND_FILE, PROFILE_FILE, BATTERY_FILE
    if plants is not None:
        PLANTS_FILE = resolve_input(plants)
    if fuel is not None:
        FUEL_FILE = resolve_input(fuel)
    if demand is not None:
        DEMAND_FILE = resolve_input(demand)
    if profiles is not None:
        PROFILE_FILE = resolve_input(profiles)
    if battery is not None:
        BATTERY_FILE = resolve_input(battery)


def input_paths():
    """The file filling each input role, keyed by the role's plain name.

    The run archive files inputs by role rather than by file name, so that a
    run using plants_ramping.csv stays directly comparable with one using
    plants_basic.csv. The real name travels alongside as the entry's "source".
    """
    paths = {
        "plants.csv": PLANTS_FILE,
        "fuel.csv": FUEL_FILE,
        "demand.csv": DEMAND_FILE,
        "profiles.csv": PROFILE_FILE,
    }
    if BATTERY_FILE is not None and BATTERY_FILE.exists():
        paths["battery.csv"] = BATTERY_FILE
    return paths


def main(argv=None):
    args = parse_args(argv)
    use_directories(args.inputs, args.results)
    use_files(args.plants, args.fuel, args.demand, args.profiles, args.battery)
    if args.no_battery:
        global BATTERY_FILE
        BATTERY_FILE = None

    print("\n" + "=" * 68)
    print("MY FIRST DISPATCH MODEL")
    print("=" * 68 + "\n")

    # The choice of files is made by the caller, so say which ones were used.
    for role, path in sorted(input_paths().items()):
        print("  {:<10} {}".format(role[:-len(".csv")], path.name))
    print("")

    plants, fuel, demand, profile, battery = load_data()
    print("Loaded {} plants, {} batteries, {} fuels, {} hours, {} profile rows.\n"
          .format(len(plants), len(battery), len(fuel), len(demand), len(profile)))

    params = build_parameters(plants, fuel, demand, profile, battery)
    if params["profiled"]:
        print("  profiled technologies: {}\n".format(
            ", ".join("{} ({})".format(p, params["technology"][p])
                      for p in sorted(params["profiled"]))))
    warn_nonpositive_demand(params)
    warn_capacity_shortfall(params)

    started = time.time()
    prob, gen, unserved, spill, charge, discharge, soc = build_and_solve(params)
    solve_seconds = round(time.time() - started, 3)

    results = build_hourly_results(params, prob, gen, unserved, spill, charge, discharge, soc)
    summary = build_plant_summary(params, results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / "dispatch_results.csv"
    summary_path = RESULTS_DIR / "plant_summary.csv"
    results.round(6).to_csv(results_path, index=False)
    summary.round(6).to_csv(summary_path, index=False)
    print("Results written:\n  {}\n  {}\n".format(results_path, summary_path))

    # A note rather than a gate, so it neither stops the run nor blocks
    # archiving.
    warn_merit_order_departures(params, results)

    # A failure here must not lose the results, which are already on disk.
    # A run over custom files or folders is archived like any other, because
    # the paths it actually used are handed to the archive rather than assumed.
    if not args.no_archive:
        try:
            manifest = runstore.archive_run(
                label=args.label, notes=args.notes,
                solver_status=pulp.LpStatus[prob.status], seconds=solve_seconds,
                input_paths=input_paths(), results_dir=RESULTS_DIR,
                # A labelled run is named after its label alone, so rerunning
                # the same case replaces it instead of piling up near-copies.
                run_id=runstore.slugify(args.label) or None)
            git = manifest["git"]
            print("Archived as run: {}".format(manifest["id"]))
            if git.get("short"):
                print("  git {}{}   compare with:  python run_archive/runs.py diff {} latest\n"
                      .format(git["short"],
                              " (dirty)" if git.get("dirty") else "",
                              manifest["id"]))
            else:
                print("")
        except Exception as exc:                             # noqa: BLE001
            print("WARNING: could not archive this run ({}: {}). "
                  "Results were still written.\n"
                  .format(type(exc).__name__, exc))

    report(params, results, summary, objective_value=pulp.value(prob.objective))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:                              # noqa: BLE001
        print("\nERROR: {}: {}".format(type(exc).__name__, exc))
        sys.exit(1)
