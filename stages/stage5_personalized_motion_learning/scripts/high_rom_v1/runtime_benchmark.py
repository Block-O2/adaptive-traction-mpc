"""Read-only timing accounting for a frozen High-ROM runtime corpus."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
SPEC = STAGE / "docs/high_rom_runtime_v1/BENCHMARK_SPEC.json"


def stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "p95": None, "max": None}
    a = np.asarray(values, dtype=float)
    return {"count": len(values), "mean": float(a.mean()),
            "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def case_timing(case: dict, path: Path) -> dict:
    summary = json.loads((path / "summary.json").read_text())
    artifact = json.loads((path / "runtime_artifacts.json").read_text())
    wall = artifact["wall_physics"]
    requests = summary["timing"]["requests"]
    compute = [float(x["compute_ms"]) for x in requests if x.get("compute_ms") is not None]
    activated = [x for x in requests if x.get("outcome") == "ACTIVATED"]
    ages = [float(x["activation_age_ms"]) for x in activated]
    components = {name: stats([float(x[name]) for x in requests if x.get(name) is not None])
                  for name in ("acquisition_to_request_ms", "snapshot_ms", "queue_ms",
                               "queue_and_snapshot_ms", "worker_to_main_scheduling_ms",
                               "compute_ms", "validation_scheduling_ms",
                               "validation_and_command_construction_ms")}
    last_grid = -1
    reconstructed_misses = longest = polls = 0
    for event in wall["catchup_intervals"]:
        if event["reason"] != "control_poll":
            continue
        grid = round((event["end_physics_s"] - wall["origin_physics_s"])
                     / wall["native_dt_s"]) // 20
        gap = max(0, grid - last_grid - 1)
        reconstructed_misses += gap
        longest = max(longest, gap)
        last_grid = grid
        polls += 1
    if reconstructed_misses != wall["control_cycle_misses"]:
        raise ValueError(f"control miss reconstruction mismatch: {case['id']}")
    total_grids = round(wall["physics_elapsed_s"] / .005)
    outcomes = dict(Counter(x["outcome"] for x in requests))
    return {"id": case["id"], "plant": case["plant"], "path": str(path),
            "case_sha256": hashlib.sha256((STAGE / case["case"]).read_bytes()).hexdigest(),
            "status": summary["status"], "request_outcomes": outcomes,
            "planning_compute_ms": stats(compute), "sample_to_activation_ms": stats(ages),
            "components_ms": components, "control_cycle_misses": reconstructed_misses,
            "control_grid_count": total_grids, "control_poll_count": polls,
            "control_cycle_miss_ratio": reconstructed_misses / total_grids,
            "longest_consecutive_control_misses": longest,
            "expired_activated": sum(x.get("activation_age_ms", 0) >= 100. for x in activated),
            "task_phase_transitions": summary["task"]["phase_transitions"],
            "task_duration_s": summary["task"]["physics_duration_s"],
            "task_peak_force_n": summary["task"]["peak_force_n"],
            "task_peak_moment_nm": summary["task"]["peak_moment_nm"],
            "task_minimum_session_clearance_m": summary["task"]["minimum_session_clearance_m_deployable"],
            "_compute_values": compute, "_age_values": ages}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text())
    base = (Path(spec["baseline_raw_root"]) if args.mode == "baseline"
            else args.candidate_root)
    if base is None:
        raise ValueError("candidate-root required")
    rows = []
    for case in spec["cases"]:
        relative = case["baseline"] if args.mode == "baseline" else case["id"]
        rows.append(case_timing(case, base / relative))
    compute = [v for x in rows for v in x.pop("_compute_values")]
    ages = [v for x in rows for v in x.pop("_age_values")]
    grids = sum(x["control_grid_count"] for x in rows)
    misses = sum(x["control_cycle_misses"] for x in rows)
    outcomes = dict(sum((Counter(x["request_outcomes"]) for x in rows), Counter()))
    result = {"schema": "high_rom_runtime_benchmark_result_v1", "mode": args.mode,
              "spec_sha256": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
              "planning_compute_ms": stats(compute), "sample_to_activation_ms": stats(ages),
              "control_cycle_misses": misses, "control_grid_count": grids,
              "control_cycle_miss_ratio": misses / grids,
              "longest_consecutive_control_misses": max(x["longest_consecutive_control_misses"] for x in rows),
              "request_outcomes": outcomes,
              "expired_activated": sum(x["expired_activated"] for x in rows),
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in (
        "mode", "planning_compute_ms", "sample_to_activation_ms", "control_cycle_misses",
        "control_cycle_miss_ratio", "longest_consecutive_control_misses",
        "request_outcomes", "expired_activated")}, indent=2))


if __name__ == "__main__":
    main()
