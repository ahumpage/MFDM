"""
Run archive for the dispatch model
==================================

Every solve is snapshotted so that a past result can be inspected, compared
or restored. The archive answers a question git cannot: given that today's
numbers differ from last week's, was that the code or the inputs?

Layout
------
    runs/
        _store/<sha256-16>.csv          deduped input blobs
        <run id>/
            manifest.json
            dispatch_results.csv
            plant_summary.csv

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
RUNS_DIR = BASE_DIR / "runs"
STORE_DIR = RUNS_DIR / "_store"

INPUT_FILES = ["plants.csv", "fuel.csv", "demand.csv", "profiles.csv"]
OUTPUT_FILES = ["dispatch_results.csv", "plant_summary.csv"]
CODE_FILES = ["MFDM.py", "dashboard.py", "runstore.py", "runs.py"]

# Inputs small enough that a cell by cell diff is readable and useful.
SMALL_INPUTS = {"plants.csv", "fuel.csv"}

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
    """Filesystem safe fragment for a run id."""
    if not text:
        return ""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(text).strip().lower())
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

    gen_total = float(summary["Total Generation (MWh)"].sum())

    profiled = summary[summary["Profiled"] == True] if "Profiled" in summary.columns \
        else summary.iloc[0:0]
    ren_used = float(profiled["Total Generation (MWh)"].sum()) if len(profiled) else 0.0
    ren_avail = float(profiled["Available Energy (MWh)"].sum()) if len(profiled) else 0.0
    curtailed = float(results["Curtailment (MWh)"].sum()) \
        if "Curtailment (MWh)" in results.columns else 0.0

    kpis = {
        "hours": int(len(results)),
        "energy_served_mwh": demand,
        "energy_generated_mwh": gen_total,
        "production_cost": prod,
        "market_cost": market,
        "avg_production_cost": prod / demand if demand else 0.0,
        "time_weighted_price": float(results["Clearing Price ($/MWh)"].mean()),
        "load_weighted_price": market / demand if demand else 0.0,
        "producer_surplus": market - prod,
        "renewable_used_mwh": ren_used,
        "renewable_available_mwh": ren_avail,
        "renewable_share_pct": 100.0 * ren_used / demand if demand else 0.0,
        "curtailed_mwh": curtailed,
        "curtailment_pct": 100.0 * curtailed / ren_avail if ren_avail else 0.0,
        "plants": [],
    }

    for _, r in summary.iterrows():
        kpis["plants"].append({
            "plant": r["Plant"],
            "technology": r["Technology"],
            "capacity_mw": float(r["Capacity (MW)"]),
            "profiled": bool(r["Profiled"]) if "Profiled" in summary.columns else False,
            "marginal_cost": float(r["Marginal Cost ($/MWh)"]),
            "generation_mwh": float(r["Total Generation (MWh)"]),
            "capacity_factor_pct": float(r["Capacity Factor (%)"]),
            "hours_running": int(r["Hours Running"]),
            "hours_setting_price": int(r["Hours Setting Price"]),
        })
    return kpis


# --------------------------------------------------------------------------
# Archiving
# --------------------------------------------------------------------------

def archive_run(label=None, notes=None, solver_status=None, seconds=None,
                base_dir=None):
    """Snapshot the current inputs and results as a new run.

    Reads the files sitting in the working folder, so it must be called after
    the results have been written.
    """
    base = Path(base_dir) if base_dir else BASE_DIR
    _ensure_dirs()

    missing = [f for f in INPUT_FILES + OUTPUT_FILES if not (base / f).exists()]
    if missing:
        raise FileNotFoundError(
            "Cannot archive, missing: {}".format(", ".join(missing)))

    created = datetime.now()
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
    for name in INPUT_FILES:
        digest, size = store_blob(base / name)
        inputs[name] = {"hash": digest, "size": size}

    for name in OUTPUT_FILES:
        shutil.copy2(str(base / name), str(run_dir / name))

    results = pd.read_csv(run_dir / "dispatch_results.csv")
    summary = pd.read_csv(run_dir / "plant_summary.csv", keep_default_na=False)

    code = {}
    for name in CODE_FILES:
        # Always hashed from where the modules actually live, not from
        # base_dir, which may be a scratch folder holding only data.
        path = BASE_DIR / name
        if path.exists():
            code[name] = sha256_file(path)

    manifest = {
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
    """All archived runs, newest first."""
    if not RUNS_DIR.exists():
        return []
    out = []
    for child in RUNS_DIR.iterdir():
        if not child.is_dir() or child.name == "_store":
            continue
        path = child / MANIFEST_NAME
        if not path.exists():
            continue
        try:
            with open(str(path)) as fh:
                out.append(json.load(fh))
        except (ValueError, OSError):
            continue
    out.sort(key=lambda m: m.get("created", ""), reverse=True)
    return out


def get_manifest(run_id):
    path = RUNS_DIR / run_id / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError("No such run: {}".format(run_id))
    with open(str(path)) as fh:
        return json.load(fh)


def resolve(run_ref):
    """Accept a full run id, a unique prefix, a label, or 'latest'."""
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

def check_writable(base_dir=None, names=None):
    """Names of files that exist but cannot currently be written.

    Worth checking before a restore: these CSVs are routinely open in Excel,
    which locks them on Windows. Without this, a restore could overwrite two
    files, hit a lock on the third and leave an inconsistent input set that
    matches no run at all.
    """
    base = Path(base_dir) if base_dir else BASE_DIR
    blocked = []
    for name in (names or INPUT_FILES):
        path = base / name
        if not path.exists():
            continue
        try:
            with open(str(path), "ab"):
                pass
        except (IOError, OSError):
            blocked.append(name)
    return blocked


def restore(run_ref, base_dir=None, snapshot_first=True):
    """Copy an archived run's inputs back into the working folder.

    This overwrites the live input CSVs, so unless snapshot_first is turned
    off the current state is archived first and its id returned alongside.
    """
    base = Path(base_dir) if base_dir else BASE_DIR
    run_id = resolve(run_ref)
    manifest = get_manifest(run_id)

    # Fail before touching anything rather than part way through.
    blocked = check_writable(base)
    if blocked:
        raise IOError(
            "Cannot restore: {} {} locked by another program (Excel keeps CSVs "
            "open). Close the file(s) and try again. Nothing has been changed."
            .format(", ".join(blocked), "is" if len(blocked) == 1 else "are"))

    safety = None
    if snapshot_first:
        # Only possible if a full set of files is present to snapshot.
        have_all = all((base / f).exists() for f in INPUT_FILES + OUTPUT_FILES)
        if have_all:
            safety = archive_run(label=SAFETY_LABEL,
                                 notes="Automatic snapshot before restoring {}".format(run_id),
                                 base_dir=base)

    restored = []
    for name in INPUT_FILES:
        src = load_input(run_id, name)
        shutil.copy2(str(src), str(base / name))
        restored.append(name)

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
        shutil.rmtree(str(RUNS_DIR / m["id"]), ignore_errors=True)
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
    scalar_keys = [k for k in ka if k != "plants"]
    kpi_delta = []
    for k in scalar_keys:
        va, vb = ka.get(k), kb.get(k)
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
