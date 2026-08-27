"""
Command line tool for the dispatch model run archive.

    python runs.py list                     recent runs with headline numbers
    python runs.py show <run>               full detail for one run
    python runs.py diff <run a> <run b>     what changed, and what it did
    python runs.py restore <run>            put a run's inputs back in place
    python runs.py prune --keep 20          tidy up old unlabelled runs

A run can be named by its full id, a unique prefix, its label, or "latest".
"""

from __future__ import print_function

import argparse
import sys

import runstore


BAR = "-" * 78

# KPIs worth showing in a diff, in a sensible reading order, with the units
# and the direction that counts as an improvement.
KPI_DISPLAY = [
    ("production_cost", "Production cost", "$", "lower"),
    ("market_cost", "Market cost", "$", "lower"),
    ("avg_production_cost", "Avg production cost", "$/MWh", "lower"),
    ("load_weighted_price", "Load-weighted price", "$/MWh", "lower"),
    ("time_weighted_price", "Time-weighted price", "$/MWh", "lower"),
    ("producer_surplus", "Producer surplus", "$", None),
    ("energy_served_mwh", "Energy served", "MWh", None),
    ("renewable_used_mwh", "Renewable used", "MWh", "higher"),
    ("renewable_share_pct", "Renewable share", "%", "higher"),
    ("curtailed_mwh", "Curtailed", "MWh", "lower"),
    ("curtailment_pct", "Curtailment", "%", "lower"),
    ("hours", "Hours", "", None),
]


def fmt(value, unit=""):
    if value is None:
        return "-"
    if isinstance(value, float):
        if unit == "%":
            return "{:,.2f}%".format(value)
        if abs(value) >= 1000:
            return "{:,.0f}".format(value)
        return "{:,.2f}".format(value)
    return str(value)


def describe_git(manifest):
    git = manifest.get("git") or {}
    if not git.get("short"):
        return "no git"
    return "{}{}".format(git["short"], "*" if git.get("dirty") else "")


# --------------------------------------------------------------------------
# list
# --------------------------------------------------------------------------

def cmd_list(args):
    runs = runstore.list_runs()
    if not runs:
        print("No runs archived yet. Run 'python model/MFDM.py' to create one.")
        return 0

    runs = runs[:args.limit] if args.limit else runs

    header = "{:<34} {:<18} {:>7} {:>13} {:>10} {:>8}".format(
        "RUN ID", "LABEL", "GIT", "PROD COST $", "PRICE", "REN %")
    print(header)
    print(BAR)
    for m in runs:
        k = m["kpis"]
        print("{:<34} {:<18} {:>7} {:>13} {:>10} {:>8}".format(
            m["id"][:34],
            (m.get("label") or "")[:18],
            describe_git(m),
            "{:,.0f}".format(k["production_cost"]),
            "{:,.2f}".format(k["load_weighted_price"]),
            "{:,.1f}".format(k["renewable_share_pct"]),
        ))
    print(BAR)
    print("{} run(s). A trailing * means the working tree was dirty.".format(len(runs)))
    return 0


# --------------------------------------------------------------------------
# show
# --------------------------------------------------------------------------

def cmd_show(args):
    run_id = runstore.resolve(args.run)
    m = runstore.get_manifest(run_id)
    k = m["kpis"]

    print(BAR)
    print("RUN  {}".format(m["id"]))
    print(BAR)
    print("  created   : {}".format(m["created"]))
    print("  label     : {}".format(m.get("label") or "-"))
    if m.get("notes"):
        print("  notes     : {}".format(m["notes"]))
    git = m.get("git") or {}
    print("  git       : {} on {}{}".format(
        git.get("short") or "-", git.get("branch") or "-",
        "  (uncommitted changes present)" if git.get("dirty") else ""))
    solver = m.get("solver") or {}
    print("  solver    : {} in {}s".format(
        solver.get("status") or "-", solver.get("seconds")))

    print("\n  inputs")
    for name, entry in m["inputs"].items():
        print("    {:<16} {}  {:>9,} bytes".format(name, entry["hash"], entry["size"]))

    print("\n  source files")
    for name, digest in sorted(m.get("code", {}).items()):
        print("    {:<16} {}".format(name, digest))

    print("\n  results")
    for key, label, unit, _ in KPI_DISPLAY:
        if key in k:
            print("    {:<22} {:>16}".format(label, fmt(k[key], unit)))

    print("\n  plants")
    print("    {:<10} {:<8} {:>9} {:>9} {:>14} {:>8} {:>10}".format(
        "PLANT", "TECH", "CAP MW", "MC $/MWh", "GEN MWh", "CF %", "STACK h"))
    for p in k["plants"]:
        print("    {:<10} {:<8} {:>9,.0f} {:>9,.2f} {:>14,.1f} {:>8,.1f} {:>10}".format(
            p["plant"], p["technology"], p["capacity_mw"], p["marginal_cost"],
            p["generation_mwh"], p["capacity_factor_pct"], p["hours_setting_price"]))
    print(BAR)
    return 0


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

def cmd_diff(args):
    d = runstore.diff(args.run_a, args.run_b)
    a, b = d["a"], d["b"]

    print(BAR)
    print("DIFF   A: {}   ({})".format(a["id"], a.get("label") or "no label"))
    print("       B: {}   ({})".format(b["id"], b.get("label") or "no label"))
    print(BAR)
    print(runstore.attribution(d))

    # --- code ---
    print("\nCODE")
    ga, gb = a.get("git") or {}, b.get("git") or {}
    print("  git: {} -> {}".format(describe_git(a), describe_git(b)))
    if d["same_code"]:
        print("  source files identical")
    else:
        for c in d["code_changed"]:
            print("  changed: {:<16} {} -> {}".format(
                c["file"], c["before"] or "absent", c["after"] or "absent"))
        if ga.get("dirty") or gb.get("dirty"):
            print("  note: a dirty tree means the commit alone does not identify "
                  "the code; the hashes above do.")

    # --- inputs ---
    print("\nINPUTS")
    if d["same_inputs"]:
        print("  all inputs identical")
    else:
        for name, info in sorted(d["inputs_changed"].items()):
            print("  {}".format(name))
            if info["kind"] == "cells":
                for c in info["changes"]:
                    print("    {:<12} {:<26} {} -> {}".format(
                        c["row"], c["field"], c["before"], c["after"]))
            else:
                before, after = info["before"], info["after"]
                print("    rows: {:,} -> {:,}".format(before["rows"], after["rows"]))
                for col in before["series"]:
                    if col not in after["series"]:
                        continue
                    sa, sb = before["series"][col], after["series"][col]
                    if abs(sa["sum"] - sb["sum"]) < 1e-9:
                        continue
                    print("    {:<24} mean {:,.4f} -> {:,.4f}   sum {:,.1f} -> {:,.1f}"
                          .format(col, sa["mean"], sb["mean"], sa["sum"], sb["sum"]))

    # --- results ---
    print("\nRESULTS")
    print("  {:<22} {:>15} {:>15} {:>15} {:>9}".format(
        "KPI", "A", "B", "DELTA", "CHANGE"))
    order = {key: i for i, (key, _, _, _) in enumerate(KPI_DISPLAY)}
    rows = sorted([r for r in d["kpi_delta"] if r["kpi"] in order],
                  key=lambda r: order[r["kpi"]])
    labels = {key: (label, unit) for key, label, unit, _ in KPI_DISPLAY}
    for r in rows:
        label, unit = labels[r["kpi"]]
        pct = "-" if r["pct"] is None else "{:+.2f}%".format(r["pct"])
        if abs(r["delta"]) < 1e-9:
            pct = "same"
        print("  {:<22} {:>15} {:>15} {:>15} {:>9}".format(
            label, fmt(r["before"], unit), fmt(r["after"], unit),
            fmt(r["delta"], unit), pct))

    # --- plants ---
    print("\nPLANTS")
    print("  {:<10} {:>19} {:>25} {:>19}".format(
        "PLANT", "CAPACITY MW", "GENERATION MWh", "LAST IN STACK h"))
    for p in d["plant_delta"]:
        if not p["in_a"]:
            note = "  (only in B)"
        elif not p["in_b"]:
            note = "  (only in A)"
        else:
            note = ""

        def cap(v):
            return "-" if v is None else "{:,.0f}".format(v)

        print("  {:<10} {:>8} -> {:>8} {:>11,.0f} -> {:>11,.0f} {:>8} -> {:>8}{}".format(
            p["plant"],
            cap(p["capacity_before"]), cap(p["capacity_after"]),
            p["generation_before"] or 0.0, p["generation_after"] or 0.0,
            p["price_hours_before"] if p["price_hours_before"] is not None else "-",
            p["price_hours_after"] if p["price_hours_after"] is not None else "-",
            note))
    print(BAR)
    return 0


# --------------------------------------------------------------------------
# restore
# --------------------------------------------------------------------------

def cmd_restore(args):
    run_id = runstore.resolve(args.run)
    m = runstore.get_manifest(run_id)

    blocked = runstore.check_writable()
    if blocked:
        print("Cannot restore: the following are locked by another program")
        for name in blocked:
            print("  {}".format(name))
        print("\nExcel locks CSV files while they are open. Close them and "
              "try again. Nothing has been changed.")
        return 1

    print("About to restore inputs from run {} ({}).".format(
        run_id, m.get("label") or "no label"))
    print("This overwrites the following in the working folder:")
    for name in runstore.INPUT_FILES:
        print("  {}".format(name))

    if not args.yes:
        answer = input("Continue? Current inputs are snapshotted first. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled. Nothing was changed.")
            return 1

    outcome = runstore.restore(run_id, snapshot_first=not args.no_snapshot)

    print("\nRestored {} file(s) from {}.".format(
        len(outcome["files"]), outcome["restored_run"]))
    if outcome["safety_run"]:
        print("Previous state saved as: {}".format(outcome["safety_run"]))
        print("  undo with:  python runs.py restore {} --yes".format(
            outcome["safety_run"]))
    else:
        print("No safety snapshot was taken.")
    print("\nRe-run the model to reproduce that run:  python model/MFDM.py")
    return 0


# --------------------------------------------------------------------------
# prune
# --------------------------------------------------------------------------

def cmd_prune(args):
    removed, orphans = runstore.prune(keep=args.keep,
                                      unlabelled_only=not args.include_labelled)
    if not removed:
        print("Nothing to prune.")
    else:
        print("Removed {} run(s):".format(len(removed)))
        for r in removed:
            print("  {}".format(r))
    if orphans:
        print("Reclaimed {} unreferenced blob(s) from the store.".format(len(orphans)))
    return 0


# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Inspect, compare and restore archived dispatch model runs.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="list archived runs")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="show one run in full")
    p.add_argument("run", nargs="?", default="latest")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("diff", help="compare two runs")
    p.add_argument("run_a")
    p.add_argument("run_b", nargs="?", default="latest")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("restore", help="restore a run's inputs")
    p.add_argument("run")
    p.add_argument("--yes", action="store_true", help="skip the confirmation")
    p.add_argument("--no-snapshot", action="store_true",
                   help="do not snapshot current inputs first")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("prune", help="delete old runs")
    p.add_argument("--keep", type=int, default=20)
    p.add_argument("--include-labelled", action="store_true")
    p.set_defaults(func=cmd_prune)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print("ERROR: {}".format(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
