#!/usr/bin/env python3
"""Replay original v7 raw, native ownership, full motion, and wrench analysis offline.

No environment, MuJoCo, simulator, learner, or rollout module may be imported.
Original physical safety/task-audit inputs are identity checked and retained;
this tool does not repeat the physical simulation or acquire new safety evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

IDS = ["DEVPC02_B", "DEVPC02_TRAD_COMBO"]


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(2**20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(p.read_text())


def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def compare(actual, expected, path="", root_ignored=()):
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError("KEYS:" + path)
        for k in expected:
            if not path and k in root_ignored:
                continue
            compare(actual[k], expected[k], path + "/" + k)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError("LENGTH:" + path)
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, path + "/" + str(i))
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or not math.isfinite(actual) or abs(actual - expected) > 1e-8:
            raise AssertionError("NUMERIC:" + path)
    elif actual != expected:
        raise AssertionError("VALUE:" + path)


class OfflineOnly(importlib.abc.MetaPathFinder):
    blocked = {"mujoco", "torch", "gymnasium", "stable_baselines3", "study_common",
               "sac_env", "campaign_v6", "base_campaign", "v7_worker_v5",
               "wall_physics", "scientific_scheduler", "traction_mpc_stage5"}

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self.blocked:
            raise RuntimeError("OFFLINE_REPLAY_FORBIDS_IMPORT:" + fullname)
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True, help="A new scratch directory")
    args = ap.parse_args()
    if not __debug__:
        ap.error("Python -O/PYTHONOPTIMIZE disables original qualification assertions")
    repo, out = args.repo.resolve(), args.output.resolve()
    if out.exists():
        ap.error("Preserve previous evidence; --output must be a new directory")
    source = repo / "research_archive/packages/autonomous_learning_smoothness_v7"
    manifest_path = repo / "evidence_selection.json"
    manifest = load(manifest_path)
    selected = {r["path"]: r for r in manifest["entries"]}
    out.mkdir(parents=True)
    package = out / "package"
    launcher = Path(__file__).resolve().with_name("reproduce_trad_combo.py")
    if not launcher.is_file():
        launcher = repo / "deployment/reproduce_trad_combo.py"
    start = time.monotonic()
    # Preparation copies source/assets and rebinds literal paths; no physics import.
    subprocess.run([sys.executable, str(launcher), "--repo", str(repo),
                    "--output", str(package), "--prepare-only"], check=True)
    runtime = package / "runtime"
    inputs = []

    def preserve(relative):
        p = source / relative
        name = "autonomous_learning_smoothness_v7/" + relative
        row = selected.get(name)
        if row is None or not p.is_file() or p.stat().st_size != row["bytes"] or digest(p) != row["sha256"]:
            raise AssertionError("SELECTED_INPUT_IDENTITY:" + name)
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        inputs.append(dict(path=name, bytes=row["bytes"], sha256=row["sha256"]))

    for ident in IDS:
        for p in sorted((source / "runtime/source/results" / ident).iterdir()):
            if p.is_file():
                preserve(str(p.relative_to(source)))
        for suffix in ["", "_DATA", "_DECISIONS", "_ISSUED_REFERENCE", "_REFERENCE_OBJECTS", "_CAUSAL_STATE"]:
            preserve("runtime/output/" + ident + suffix + ".json")
        preserve("attempts/" + ident + "_RESULT.json") if "autonomous_learning_smoothness_v7/attempts/" + ident + "_RESULT.json" in selected else shutil.copy2(source / "attempts" / (ident + "_RESULT.json"), package / "attempts" / (ident + "_RESULT.json"))
    sys.dont_write_bytecode = True
    os.environ.update(ACL2_PACKAGE=str(package), OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    sys.meta_path.insert(0, OfflineOnly())
    sys.path[:0] = [str(package / "source"), str(runtime / "code")]
    modules = {}

    def original(name, relative):
        p = package / relative
        spec = importlib.util.spec_from_file_location(name, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        if not Path(m.__file__).resolve().is_relative_to(package):
            raise AssertionError("NONPORTABLE_MODULE:" + name)
        modules[name] = dict(path=str(p), sha256=digest(p))
        return m

    original("stream_runtime_evidence", "runtime/code/stream_runtime_evidence.py")
    original("attribution", "runtime/code/attribution.py")
    ec = original("explore_common", "runtime/code/explore_common.py")
    am = original("analyze_matched", "runtime/code/analyze_matched.py")
    original("acl2_shared", "source/acl2_shared.py")
    native = original("v7_metrics_v3", "source/v7_metrics_v3.py")
    am.S = ec.S = runtime
    measured, rows = {}, []
    for ident in IDS:
        expected = load(source / "runtime/reports" / (ident + "_MEASURED.json"))
        measured[ident] = am.measure(ident)
        compare(measured[ident], expected, root_ignored={"sources", "execution_lineage_path"})
        lineage = load(runtime / "reports" / (ident + "_EXECUTED_RESIDUAL_RECEIPTS.json"))
        if lineage["status"] != "PASS" or lineage["ownership_error_count"] or lineage["expired_actual_write_receipts"]:
            raise AssertionError("ORIGINAL_NATIVE_OWNERSHIP_FAILURE:" + ident)
        historical = load(source / "attempts" / (ident + "_RESULT.json"))
        comp = am.compare(measured[ident], measured["DEVPC02_B"])
        compare(comp, historical["motion_vs_B"])
        q = bool(comp["acceptance_pass"] and measured[ident]["axes"]["LEGACY_R2_MATCHED"] == "PASS"
                 and measured[ident]["native_physical_audit"]["pass_"]
                 and measured[ident]["axes"]["PHYSICAL_TASK_VALID"] == "PASS"
                 and measured[ident]["axes"]["SCIENTIFIC_EXECUTION_CAUSAL_VALID"] == "PASS")
        if not q or q != historical["qualified"] or not historical["complete"]:
            raise AssertionError("ORIGINAL_FULL_MOTION_QUALIFICATION:" + ident)
        # No cached native_metrics file is copied, so original evaluate must read raw.
        n = native.evaluate(ident)
        compare(n, load(source / "analysis/native_metrics" / (ident + ".json")))
        import numpy as np
        with np.load(runtime / "motion_series" / (ident + ".npz"), allow_pickle=False) as actual, np.load(source / "runtime/motion_series" / (ident + ".npz"), allow_pickle=False) as old:
            if set(actual.files) != set(old.files) or any(not np.array_equal(actual[k], old[k]) for k in old.files):
                raise AssertionError("ORIGINAL_COMPLETE_NATIVE_ARRAY:" + ident)
        rows.append(dict(id=ident, complete=True, original_qualified=q, JF=n["JF"], JM=n["JM"], native_samples=n["native_samples"], full_measured_fields="PASS", original_motion_comparison="PASS", raw_and_SG5_SG21_motion="PASS", native_ownership="PASS", native_wrench_metrics="PASS", complete_native_array="EXACT_PASS"))
        print("ORIGINAL_V7_RAW_MOTION_OWNERSHIP_REPLAY_PASS " + ident, flush=True)
    for r in inputs:
        if digest(repo / "research_archive/packages" / r["path"]) != r["sha256"]:
            raise AssertionError("ORIGINAL_INPUT_MODIFIED:" + r["path"])
    forbidden = sorted(set(sys.modules).intersection(OfflineOnly.blocked))
    if forbidden:
        raise AssertionError("FORBIDDEN_IMPORTED_MODULES:" + str(forbidden))
    report = dict(schema="ihear.archive.original_v7_offline_replay.v1", status="PASS", rows=rows,
                  wall_s=time.monotonic()-start, inputs=inputs, imported_original_modules=modules,
                  source_preparation="Unchanged original modules except recorded literal path rebasing",
                  archived_physical_task_safety_audits="IDENTITY_CHECKED_ORIGINAL_INPUTS_NOT_NEW_PHYSICS",
                  new_physics_starts=0, training_steps=0, hardware_actuation=False,
                  forbidden_modules_imported=forbidden, numerical_tolerance=1e-8,
                  new_dynamic_execution="NOT_RUN", host_realtime_qualification="NOT_EVALUABLE",
                  historical_identity_limit="Replays recorded measurements/receipt ownership and original motion gates; does not reconstruct old live parent or generate new physical safety evidence")
    dump(out / "RESULT.json", report)
    print(json.dumps(dict(status="PASS", result=str(out / "RESULT.json"), new_physics_starts=0)), flush=True)


if __name__ == "__main__":
    main()
