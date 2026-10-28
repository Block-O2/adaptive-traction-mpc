"""Aggregate matched confirmed-baseline and Stage-C runtime cases."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"
OLD = STAGE / "docs/high_rom_v1"
NEW_RUNS = STAGE / "results/high_rom_runtime_v1/candidate03_regression"


def stats(values):
    a = np.asarray(values, dtype=float)
    return {"count": len(a), "mean": float(a.mean()),
            "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def read_case(path):
    summary = json.loads((path / "summary.json").read_text())
    wall = json.loads((path / "runtime_artifacts.json").read_text())["wall_physics"]
    requests = summary["timing"]["requests"]
    compute = [float(x["compute_ms"]) for x in requests if x.get("compute_ms") is not None]
    activated = [x for x in requests if x.get("outcome") == "ACTIVATED"]
    ages = [float(x["activation_age_ms"]) for x in activated]
    with np.load(path / "trace.npz") as z:
        task = z["stage"] == "TASK"
        error = z["estimated_human_state_rad_rad_s"][task, :2] - z["evaluation_only_human_state_rad_rad_s"][task, :2]
        error_square_deg2 = np.square(np.degrees(error)).sum(axis=0)
        sample_count = len(error)
    return {"status": summary["status"], "compute": compute, "ages": ages,
            "request_outcomes": dict(Counter(x["outcome"] for x in requests)),
            "expired_activated": sum(x["activation_age_ms"] >= 100. for x in activated),
            "control_misses": wall["control_cycle_misses"],
            "control_grids": round(wall["physics_elapsed_s"] / .005),
            "force_integral_n_s": float(summary["task"]["force_integral_n_s"]),
            "estimation_error_square_deg2": error_square_deg2.tolist(),
            "estimation_sample_count": sample_count,
            "host_elapsed_s": float(json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())["elapsed_host_s"])}


def aggregate(rows):
    compute = [x for r in rows for x in r["compute"]]
    ages = [x for r in rows for x in r["ages"]]
    misses = sum(r["control_misses"] for r in rows)
    grids = sum(r["control_grids"] for r in rows)
    squares = np.sum([r["estimation_error_square_deg2"] for r in rows], axis=0)
    samples = sum(r["estimation_sample_count"] for r in rows)
    return {"cases": len(rows), "complete": sum(r["status"] == "COMPLETE" for r in rows),
            "planning_compute_ms": stats(compute), "sample_to_activation_ms": stats(ages),
            "control_cycle_misses": misses, "control_grid_count": grids,
            "control_cycle_miss_ratio": misses/grids,
            "request_outcomes": dict(sum((Counter(r["request_outcomes"]) for r in rows), Counter())),
            "expired_activated": sum(r["expired_activated"] for r in rows),
            "task_force_integral_n_s_mean": float(np.mean([r["force_integral_n_s"] for r in rows])),
            "task_estimation_q_rmse_deg": np.sqrt(squares/samples).tolist(),
            "summed_host_run_s": sum(r["host_elapsed_s"] for r in rows)}


def main():
    plan = json.loads((DOC / "CANDIDATE03_REGRESSION_PLAN.json").read_text())
    old = {}
    for name in ("PHASE_B_LOW_ROM_RESULTS.json", "PHASE_B_RESULTS.json",
                 "VARIABLE_START_REPAIR_AND_CONFIRMATION.json"):
        for row in json.loads((OLD / name).read_text())["rows"]:
            old[row["case_key"]] = Path(row["output"])
    pairs = []
    for item in plan["rows"]:
        key = item["id"].removeprefix("low_")
        baseline = read_case(old[key])
        candidate = read_case(NEW_RUNS / item["id"])
        pairs.append({"id": item["id"], "plant": item["plant"],
                      "baseline_path": str(old[key]), "candidate_path": str(NEW_RUNS / item["id"]),
                      "baseline": baseline, "candidate": candidate})
    result = {"schema": "high_rom_runtime_matched_corpus_v1", "denominator": len(pairs),
              "baseline": aggregate([p["baseline"] for p in pairs]),
              "candidate": aggregate([p["candidate"] for p in pairs]),
              "low_rom": {label: aggregate([p[label] for p in pairs[:23]]) for label in ("baseline", "candidate")},
              "high_rom": {label: aggregate([p[label] for p in pairs[23:]]) for label in ("baseline", "candidate")},
              "rows": pairs}
    output = DOC / "MATCHED_49_RUNTIME.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for label in ("baseline", "candidate"):
        print(label, {k: result[label][k] for k in ("cases", "complete", "planning_compute_ms",
                 "sample_to_activation_ms", "control_cycle_miss_ratio", "request_outcomes",
                 "expired_activated", "task_force_integral_n_s_mean", "task_estimation_q_rmse_deg",
                 "summed_host_run_s")})


if __name__ == "__main__":
    main()
