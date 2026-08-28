"""
Run archive for the dispatch model
==================================

Every solve is snapshotted so that a past result can be inspected, compared
or restored. The archive answers a question git cannot: given that today's
numbers differ from last week's, was that the code or the inputs?

Layout
------
    run_archive/
        _store/<sha256-16>.csv          deduped input blobs
        <run id>/
            manifest.json
            dispatch_results.csv
            plant_summary.csv

Live files are read from and written back to inputs/ and results/ at the repo
root; the archive itself only ever writes inside run_archive/.

Inputs are content addressed, so an unchanged profiles.csv is stored once no
matter how many runs reference it. Outputs are kept as plain files in the run
folder because they differ on every run anyway and being able to open one
directly in a spreadsheet is worth more than the few kilobytes saved.

The manifest records the git commit, whether the working tree was dirty, and
a hash of each source file. The hashes matter because most runs happen with
uncommitted edits, where the commit alone would be misleading.
"""

from datetime import datetime
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

# Where the live files live. The model reads inputs/ and writes results/.
INPUTS_DIR = REPO_ROOT / "inputs"
RESULTS_DIR = REPO_ROOT / "results"

# Archived runs sit directly in run_archive/, alongside this module.
RUNS_DIR = BASE_DIR
STORE_DIR = RUNS_DIR / "_store"

INPUT_FILES = ["plants.csv", "fuel.csv", "demand.csv", "profiles.csv", "battery.csv"]
OUTPUT_FILES = ["dispatch_results.csv", "plant_summary.csv"]

# Paths relative to the repo root. The manifest keys off the bare file name so
# that runs archived before the code moved into subfolders stay comparable.
CODE_FILES = [
    "model/MFDM.py",
    "dashboard/dashboard.py",
    "run_archive/runstore.py",
    "run_archive/runs.py",
]

# Inputs small enough that a cell by cell diff is readable and useful.
SMALL_INPUTS = {"plants.csv", "fuel.csv", "battery.csv"}

MANIFEST_NAME = "manifest.json"
HASH_LEN = 16

# Label used for the automatic snapshot taken before a restore overwrites
# anything, so that an accidental restore is always recoverable.
SAFETY_LABEL = "autosave-before-restore"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def sha256_file(path):
    """Content hash of a file, truncated to keep manifests readable."""
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:HASH_LEN]


def slugify(text, max_len=40):
    """Filesystem safe fragment for a run id.

    Underscores survive, so a run named output_basic is filed under exactly
    that rather than under output-basic.
    """
    if not text:
        return ""
    slug = re.sub(r"[^A-Za-z0-9_]+", "-", str(text).strip().lower())
    return slug.strip("-")[:max_len]


def _git(args):
    """Run a git command, returning stripped stdout or None on any failure."""
    try:
        out = subprocess.check_output(
            ["git"] + args, cwd=str(BASE_DIR), stderr=subprocess.STDOUT)
        return out.decode("utf-8", "replace").strip()
    except Exception:                                        # noqa: BLE001
        return None


def git_state():
    """Current commit, branch and whether the tree has uncommitted changes.

    A dirty tree is the normal case while iterating, so the flag matters:
    two runs can share a commit and still have been produced by different
    code, which is what the source hashes are for.
    """
    commit = _git(["rev-parse", "HEAD"])
    if commit is None:
        return {"commit": None, "short": None, "branch": None, "dirty": None}
    status = _git(["status", "--porcelain"])
    return {
        "commit": commit,
        "short": commit[:7],
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty": bool(status),
    }


def live_path(name):
    """Where a live input or output file currently sits.

    Inputs and outputs used to share one folder; they now live in inputs/ and
    results/, so every read of a live file goes through here.
    """
    return (INPUTS_DIR if name in INPUT_FILES else RESULTS_DIR) / name


def _relative_source(path):
    """How the file filling a role should be named in a manifest.

    A file in inputs/ is recorded by bare name, so the common case reads as
    "plants_ramping.csv". A file from anywhere else keeps enough path to be
    identifiable: relative to the repo root where it sits inside it, absolute
    otherwise, since a run may legitimately read a file from anywhere.
    """
    path = Path(path).resolve()
    try:
        path.relative_to(INPUTS_DIR.resolve())
        return path.name
    except ValueError:
        pass
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _ensure_dirs():
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def store_blob(path):
    """Copy a file into the content addressed store, skipping it if an
    identical copy is already there. Returns (hash, size)."""
    _ensure_dirs()
    digest = sha256_file(path)
    target = STORE_DIR / "{}{}".format(digest, Path(path).suffix)
    if not target.exists():
        shutil.copy2(str(path), str(target))
    return digest, Path(path).stat().st_size


def blob_path(digest, suffix=".csv"):
    return STORE_DIR / "{}{}".format(digest, suffix)


# --------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------

def compute_kpis(results, summary):
    """Headline numbers pulled out of a solved run, stored in the manifest so
    that listing and diffing runs never has to reopen the result CSVs."""
    demand = float(results["Demand (MWh)"].sum())
    prod = float(results["Production Cost ($)"].sum())
    market = float(results["Market Cost ($)"].sum())
    unserved = float(results["Unserved Energy (MWh)"].sum()) \
        if "Unserved Energy (MWh)" in results.columns else 0.0

    gen_total = float(summary["Total Generation (MWh)"].sum())

    profiled = summary[summary["Profiled"] == True] if "Profiled" in summary.columns \
        else summary.iloc[0:0]
    ren_used = float(profiled["Total Generation (MWh)"].sum()) if len(profiled) else 0.0
    ren_avail = float(profiled["Available Energy (MWh)"].sum()) if len(profiled) else 0.0
    curtailed = float(results["Curtailment (MWh)"].sum()) \
        if "Curtailment (MWh)" in results.columns else 0.0

    kpis = {
        "hours": int(len(results)),
        "energy_served_mwh": demand - unserved,
        "unserved_mwh": unserved,
        "energy_generated_mwh": gen_total,
        "production_cost": prod,
        "market_cost": market,
        "avg_production_cost": prod / gen_total if gen_total else 0.0,
        "time_weighted_price": float(results["Clearing Price ($/MWh)"].mean()),
        "load_weighted_price": market / demand if demand else 0.0,
        "market_surplus": market - prod,
        "renewable_used_mwh": ren_used,
        "renewable_available_mwh": ren_avail,
        "renewable_share_pct": 100.0 * ren_used / demand if demand else 0.0,
        "curtailed_mwh": curtailed,
        "curtailment_pct": 100.0 * curtailed / ren_avail if ren_avail else 0.0,
        "plants": [],
    }

    for _, r in summary.iterrows():
        # "Hours Setting Price" was renamed to "Hours Last in Stack" when
        # ramping made the clearing price the energy-balance dual, which is no
        # longer equal to any plant's marginal cost. The KPI key is left alone
        # so that runs archived before and after the rename still diff against
        # each other; only the column it is read from moved.
        last_in_stack = r["Hours Last in Stack"] if "Hours Last in Stack" in summary.columns \
            else r["Hours Setting Price"]
        kpis["plants"].append({
            "plant": r["Plant"],
            "technology": r["Technology"],
            "capacity_mw": float(r["Capacity (MW)"]),
            "profiled": bool(r["Profiled"]) if "Profiled" in summary.columns else False,
            "marginal_cost": float(r["Marginal Cost ($/MWh)"]),
            "generation_mwh": float(r["Total Generation (MWh)"]),
            "capacity_factor_pct": float(r["Capacity Factor (%)"]),
            "hours_running": int(r["Hours Running"]),
            "hours_setting_price": int(last_in_stack),
        })
    return kpis


def kpi_value(kpis, key):
    """Read a KPI, including defaults for result files archived before it existed."""
    if key == "unserved_mwh":
        return kpis.get(key, 0.0)
    if key == "market_surplus":
        return kpis.get(key, kpis.get("producer_surplus"))
    return kpis.get(key)


# --------------------------------------------------------------------------
# Archiving
# --------------------------------------------------------------------------

def archive_run(label=None, notes=None, solver_status=None, seconds=None,
                input_paths=None, results_dir=None, run_id=None):
    """Snapshot the current inputs and results as a new run.

    Reads the live files from inputs/ and results/, so it must be called after
    the results have been written. A run that read or wrote somewhere else says
    so with input_paths and results_dir, so that what gets archived is what the
    run actually used.

    input_paths maps each role in INPUT_FILES to the file that filled it. An
    input is always stored under its role, so a run using plants_ramping.csv
    stays directly comparable with one using plants_basic.csv; the file it
    really came from is kept as the entry's "source".

    run_id names the run folder outright, replacing any run of that name. Left
    out, the id is the timestamp with the label slugged onto the end, which is
    what keeps automatic snapshots from overwriting each other.
    """
    _ensure_dirs()

    results_dir = Path(results_dir) if results_dir else RESULTS_DIR
    paths = dict(input_paths or {})
    for name in INPUT_FILES:
        if name == "battery.csv" and name not in paths:
            continue
        paths.setdefault(name, live_path(name))

    def path_for(name):
        return Path(paths[name]) if name in INPUT_FILES else results_dir / name

    archive_inputs = [name for name in INPUT_FILES if name in paths]
    missing = [str(path_for(f)) for f in archive_inputs + OUTPUT_FILES
               if not path_for(f).exists()]
    if missing:
        raise FileNotFoundError(
            "Cannot archive, missing: {}".format(", ".join(missing)))

    created = datetime.now()

    if run_id:
        # A named run is a place, not an event: running the same case again
        # replaces it, so the name always points at the latest version of it.
        run_dir = RUNS_DIR / run_id
        if run_dir.exists():
            shutil.rmtree(str(run_dir))
    else:
        run_id = created.strftime("%Y%m%dT%H%M%S")
        slug = slugify(label)
        if slug:
            run_id = "{}_{}".format(run_id, slug)

        # A second run inside the same second would otherwise collide.
        run_dir = RUNS_DIR / run_id
        suffix = 1
        while run_dir.exists():
            suffix += 1
            run_dir = RUNS_DIR / "{}-{}".format(run_id, suffix)
        run_id = run_dir.name

    run_dir.mkdir(parents=True)

    inputs = {}
    for name in archive_inputs:
        path = path_for(name)
        digest, size = store_blob(path)
        entry = {"hash": digest, "size": size}
        source = _relative_source(path)
        # Recorded only when it differs, so a run over the plain names leaves
        # manifests exactly as they were and older ones stay comparable.
        if source != name:
            entry["source"] = source
        inputs[name] = entry

    for name in OUTPUT_FILES:
        shutil.copy2(str(path_for(name)), str(run_dir / name))

    results = pd.read_csv(run_dir / "dispatch_results.csv")
    summary = pd.read_csv(run_dir / "plant_summary.csv", keep_default_na=False)

    code = {}
    for name in CODE_FILES:
        # Always hashed from where the modules actually live in the repo, and
        # keyed by bare file name so manifests stay comparable across the move.
        path = REPO_ROOT / name
        if path.exists():
            code[Path(name).name] = sha256_file(path)

    manifest = {
        # A convenience copy of the folder name, so a run folder copied
        # elsewhere still says what it is. Readers take the id from the folder
        # (see list_runs), so renaming the folder later is safe and this value
        # is allowed to go stale.
        "id": run_id,
        "created": created.isoformat(timespec="seconds"),
        "label": label,
        "notes": notes,
        "git": git_state(),
        "code": code,
        "inputs": inputs,
        "outputs": {n: sha256_file(run_dir / n) for n in OUTPUT_FILES},
        "solver": {"status": solver_status, "seconds": seconds},
        "kpis": compute_kpis(results, summary),
    }

    with open(str(run_dir / MANIFEST_NAME), "w") as fh:
        json.dump(manifest, fh, indent=2)

    return manifest


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def list_runs():
    """All archived runs, newest first.

    The folder name is the run id. The manifest carries a copy of it, but that
    copy is only provenance for a folder that gets copied somewhere else; on
    read the filesystem wins. That is what makes renaming a run folder safe:
    the id every caller receives is, by construction, one that can be found
    again on disk.
    """
    if not RUNS_DIR.exists():
        return []
    out = []
    for child in RUNS_DIR.iterdir():
        if not child.is_dir() or child.name in ("_store", "__pycache__"):
            continue
        path = child / MANIFEST_NAME
        if not path.exists():
            continue
        try:
            with open(str(path)) as fh:
                manifest = json.load(fh)
        except (ValueError, OSError):
            continue
        manifest["id"] = child.name
        out.append(manifest)
    out.sort(key=lambda m: m.get("created", ""), reverse=True)
    return out


def get_manifest(run_id):
    path = RUNS_DIR / run_id / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError(
            "No such run folder: run_archive/{}".format(run_id))
    with open(str(path)) as fh:
        manifest = json.load(fh)
    # Same rule as list_runs: the folder the manifest was read from is the id.
    manifest["id"] = run_id
    return manifest


def resolve(run_ref):
    """Accept a full run id, a unique prefix, a label, or 'latest'.

    A run id is a folder name under run_archive/, so anything returned here
    can be path-joined straight back onto RUNS_DIR.
    """
    runs = list_runs()
    if not runs:
        raise FileNotFoundError("No runs have been archived yet.")

    if run_ref in (None, "", "latest"):
        return runs[0]["id"]

    ids = [m["id"] for m in runs]
    if run_ref in ids:
        return run_ref

    matches = [i for i in ids if i.startswith(run_ref)]
    if not matches:
        matches = [m["id"] for m in runs
                   if m.get("label") and slugify(m["label"]) == slugify(run_ref)]
    if not matches:
        raise FileNotFoundError("No run matches '{}'".format(run_ref))
    if len(matches) > 1:
        raise ValueError("'{}' matches {} runs: {}".format(
            run_ref, len(matches), ", ".join(matches[:5])))
    return matches[0]


def load_results(run_id):
    """The two result DataFrames for an archived run."""
    run_dir = RUNS_DIR / run_id
    results = pd.read_csv(run_dir / "dispatch_results.csv")
    summary = pd.read_csv(run_dir / "plant_summary.csv", keep_default_na=False)
    return results, summary


def load_input(run_id, name):
    """An archived input file, resolved through the content store."""
    manifest = get_manifest(run_id)
    entry = manifest["inputs"].get(name)
    if entry is None:
        raise FileNotFoundError("Run {} has no input {}".format(run_id, name))
    path = blob_path(entry["hash"])
    if not path.exists():
        raise FileNotFoundError(
            "Blob {} for {} is missing from the store.".format(entry["hash"], name))
    return path


# --------------------------------------------------------------------------
# Restore
# --------------------------------------------------------------------------

def restore_targets(manifest):
    """Where each of a run's inputs should be written back to.

    A run records the file that filled each role, so a restore puts that file
    back rather than materialising the role's plain name. Restoring a run that
    used plants_ramping.csv therefore rewrites inputs/plants_ramping.csv, which
    is the file a rerun will actually read. Manifests written before sources
    were recorded carry none, and fall back to the plain name.

    A source pointing outside inputs/ is deliberately not honoured: a restore
    should never write to an arbitrary path elsewhere on disk, so it lands on
    the plain name in inputs/ instead.
    """
    targets = {}
    for name in manifest.get("inputs", {}):
        source = (manifest.get("inputs", {}).get(name) or {}).get("source")
        if source and "/" not in source and "\\" not in source:
            targets[name] = INPUTS_DIR / source
        else:
            targets[name] = live_path(name)
    return targets


def check_writable(paths=None):
    """Paths that exist but cannot currently be written.

    Worth checking before a restore: these CSVs are routinely open in Excel,
    which locks them on Windows. Without this, a restore could overwrite two
    files, hit a lock on the third and leave an inconsistent input set that
    matches no run at all.
    """
    if paths is None:
        paths = [live_path(n) for n in INPUT_FILES if live_path(n).exists()]
    blocked = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        try:
            with open(str(path), "ab"):
                pass
        except (IOError, OSError):
            blocked.append(path.name)
    return blocked


def restore(run_ref, snapshot_first=True):
    """Copy an archived run's inputs back into inputs/.

    Each input goes back to the file it was read from, so that rerunning with
    the same choices reproduces the run. See restore_targets.

    This overwrites live input CSVs, so unless snapshot_first is turned off the
    current state is archived first and its id returned alongside.
    """
    run_id = resolve(run_ref)
    manifest = get_manifest(run_id)
    targets = restore_targets(manifest)

    # Fail before touching anything rather than part way through.
    blocked = check_writable(list(targets.values()))
    if blocked:
        raise IOError(
            "Cannot restore: {} {} locked by another program (Excel keeps CSVs "
            "open). Close the file(s) and try again. Nothing has been changed."
            .format(", ".join(blocked), "is" if len(blocked) == 1 else "are"))

    safety = None
    if snapshot_first:
        # Snapshots exactly the files about to be overwritten, so the safety
        # run is a faithful record of what was there. Only possible if a full
        # set is present to snapshot.
        have_all = (all(Path(p).exists() for p in targets.values())
                     and all(live_path(f).exists() for f in OUTPUT_FILES))
        if have_all:
            snapshot_inputs = dict(targets)
            battery_path = live_path("battery.csv")
            if battery_path.exists():
                snapshot_inputs["battery.csv"] = battery_path
            safety = archive_run(label=SAFETY_LABEL,
                                  notes="Automatic snapshot before restoring {}".format(run_id),
                                  input_paths=snapshot_inputs)

    restored = []
    for name in targets:
        src = load_input(run_id, name)
        target = Path(targets[name])
        shutil.copy2(str(src), str(target))
        restored.append(target.name)

    battery_path = live_path("battery.csv")
    if "battery.csv" not in targets and battery_path.exists():
        battery_path.unlink()

    return {
        "restored_run": run_id,
        "label": manifest.get("label"),
        "files": restored,
        "safety_run": safety["id"] if safety else None,
    }


def prune(keep=20, unlabelled_only=True):
    """Drop the oldest runs. Labelled runs are never removed by default, and
    the safety snapshots are treated as unlabelled so they can be cleared."""
    runs = list_runs()
    candidates = []
    for m in runs:
        label = m.get("label")
        is_safety = label == SAFETY_LABEL
        if unlabelled_only and label and not is_safety:
            continue
        candidates.append(m)

    doomed = candidates[keep:] if keep > 0 else candidates
    removed = []
    for m in doomed:
        # Deliberately not ignore_errors: a delete that fails silently but is
        # still reported as "Removed" is worse than a noisy failure, because
        # the run stays on disk while you believe it is gone. Anything that
        # goes wrong here (a locked folder, a permissions problem) should
        # stop the prune and say so.
        shutil.rmtree(str(RUNS_DIR / m["id"]))
        removed.append(m["id"])

    orphans = gc_store()
    return removed, orphans


def gc_store():
    """Delete stored blobs no longer referenced by any manifest."""
    if not STORE_DIR.exists():
        return []
    referenced = set()
    for m in list_runs():
        for entry in m.get("inputs", {}).values():
            referenced.add(entry["hash"])

    removed = []
    for blob in STORE_DIR.iterdir():
        if blob.stem not in referenced:
            blob.unlink()
            removed.append(blob.name)
    return removed


# --------------------------------------------------------------------------
# Diffing
# --------------------------------------------------------------------------

def _frame_from_blob(run_id, name):
    return pd.read_csv(load_input(run_id, name), keep_default_na=False)


def diff_small_csv(run_a, run_b, name):
    """Cell level differences between two versions of a small CSV."""
    a = _frame_from_blob(run_a, name)
    b = _frame_from_blob(run_b, name)

    key = a.columns[0]
    changes = []

    if list(a.columns) != list(b.columns):
        changes.append({"row": "-", "field": "columns",
                        "before": ", ".join(a.columns),
                        "after": ", ".join(b.columns)})
        return changes

    a_idx = a.set_index(key)
    b_idx = b.set_index(key)

    for missing in [k for k in a_idx.index if k not in b_idx.index]:
        changes.append({"row": missing, "field": "(row)",
                        "before": "present", "after": "removed"})
    for added in [k for k in b_idx.index if k not in a_idx.index]:
        changes.append({"row": added, "field": "(row)",
                        "before": "absent", "after": "added"})

    for k in [k for k in a_idx.index if k in b_idx.index]:
        for col in a_idx.columns:
            va, vb = a_idx.loc[k, col], b_idx.loc[k, col]
            if str(va) != str(vb):
                changes.append({"row": k, "field": col,
                                "before": va, "after": vb})
    return changes


def summarise_large_csv(run_id, name):
    """Shape and distribution of a large CSV, enough to characterise it
    without diffing tens of thousands of rows."""
    df = _frame_from_blob(run_id, name)
    numeric = df.select_dtypes("number")
    stats = {"rows": int(len(df)), "columns": list(df.columns), "series": {}}
    for col in numeric.columns:
        if col.lower() in ("hour", "hours"):
            continue
        stats["series"][col] = {
            "min": float(numeric[col].min()),
            "max": float(numeric[col].max()),
            "mean": float(numeric[col].mean()),
            "sum": float(numeric[col].sum()),
        }
    return stats


def diff(run_ref_a, run_ref_b):
    """Structured comparison of two runs: code, inputs and results."""
    a = resolve(run_ref_a)
    b = resolve(run_ref_b)
    ma, mb = get_manifest(a), get_manifest(b)

    # --- code ---
    code_changed = []
    for name in sorted(set(ma.get("code", {})) | set(mb.get("code", {}))):
        ha = ma.get("code", {}).get(name)
        hb = mb.get("code", {}).get(name)
        if ha != hb:
            code_changed.append({"file": name, "before": ha, "after": hb})

    # --- inputs ---
    input_changed = {}
    for name in INPUT_FILES:
        ea = ma["inputs"].get(name, {})
        eb = mb["inputs"].get(name, {})
        if ea.get("hash") == eb.get("hash"):
            continue
        if not ea or not eb:
            input_changed[name] = {"kind": "presence",
                                   "before": "present" if ea else "absent",
                                   "after": "present" if eb else "absent"}
            continue
        if name in SMALL_INPUTS:
            input_changed[name] = {"kind": "cells",
                                   "changes": diff_small_csv(a, b, name)}
        else:
            input_changed[name] = {
                "kind": "summary",
                "before": summarise_large_csv(a, name),
                "after": summarise_large_csv(b, name),
            }

    # --- results ---
    ka, kb = ma["kpis"], mb["kpis"]
    scalar_keys = (set(ka) | set(kb)) - {"plants", "producer_surplus"}
    if "market_surplus" in ka or "market_surplus" in kb \
            or "producer_surplus" in ka or "producer_surplus" in kb:
        scalar_keys.add("market_surplus")
    scalar_keys = sorted(scalar_keys)
    kpi_delta = []
    for k in scalar_keys:
        va, vb = kpi_value(ka, k), kpi_value(kb, k)
        if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
            continue
        delta = vb - va
        pct = (100.0 * delta / va) if va else None
        kpi_delta.append({"kpi": k, "before": va, "after": vb,
                          "delta": delta, "pct": pct})

    plants_a = {p["plant"]: p for p in ka.get("plants", [])}
    plants_b = {p["plant"]: p for p in kb.get("plants", [])}
    plant_delta = []
    for name in sorted(set(plants_a) | set(plants_b)):
        pa, pb = plants_a.get(name), plants_b.get(name)
        plant_delta.append({
            "plant": name,
            "in_a": pa is not None,
            "in_b": pb is not None,
            "capacity_before": pa["capacity_mw"] if pa else None,
            "capacity_after": pb["capacity_mw"] if pb else None,
            "generation_before": pa["generation_mwh"] if pa else None,
            "generation_after": pb["generation_mwh"] if pb else None,
            "price_hours_before": pa["hours_setting_price"] if pa else None,
            "price_hours_after": pb["hours_setting_price"] if pb else None,
        })

    return {
        "a": ma, "b": mb,
        "code_changed": code_changed,
        "same_code": not code_changed,
        "inputs_changed": input_changed,
        "same_inputs": not input_changed,
        "kpi_delta": kpi_delta,
        "plant_delta": plant_delta,
    }


def attribution(d):
    """One line explaining what actually differs between two runs, which is
    the whole point of keeping the archive."""
    if d["same_code"] and d["same_inputs"]:
        return "Identical code and inputs. Any difference is solver noise."
    if d["same_code"]:
        return "Code identical. Inputs changed: {}.".format(
            ", ".join(sorted(d["inputs_changed"])))
    if d["same_inputs"]:
        return "Inputs identical. Code changed: {}.".format(
            ", ".join(c["file"] for c in d["code_changed"]))
    return "Both code ({}) and inputs ({}) changed.".format(
        ", ".join(c["file"] for c in d["code_changed"]),
        ", ".join(sorted(d["inputs_changed"])))
