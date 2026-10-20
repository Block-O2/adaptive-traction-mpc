"""Aggregate the frozen C08 final 26 without running simulation."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from runtime_benchmark import stats


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"
RUNS = STAGE / "results/high_rom_runtime_v1/candidate08_final26"
FILES = ("HIGH_ROM_CASE_RESULT.json", "FINAL26_CASE_SCORE.json",
         "config_snapshot.json", "summary.json", "trace.npz", "runtime_artifacts.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    plan = json.loads((DOC / "CANDIDATE08_FINAL26_PLAN.json").read_text())
    freeze = json.loads((DOC / "CANDIDATE08_FREEZE.json").read_text())
    assert sha256(DOC / "CANDIDATE08_FREEZE.json") == plan["candidate_freeze_sha256"]
    for relative, expected in freeze["source_config_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"C08 source/config drift: {relative}")
    for relative, expected in plan["scoring_script_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"scorer/runner drift: {relative}")
    progress = [json.loads(line) for line in
                (DOC / "CANDIDATE08_FINAL26_PROGRESS.jsonl").read_text().splitlines()]
    if len(progress) != 26:
        raise RuntimeError(f"expected 26 progress records, got {len(progress)}")
    rows = []
    raw_hashes = {}
    all_compute, all_ages = [], []
    for index, (entry, prior) in enumerate(zip(plan["rows"], progress)):
        if prior["index"] != index or prior["id"] != entry["id"]:
            raise RuntimeError(f"case order drift at {index}")
        case_path = ROOT / entry["case"]
        if sha256(case_path) != entry["case_sha256"]:
            raise RuntimeError(f"case payload drift: {entry['id']}")
        path = RUNS / entry["id"]
        raw_hashes[entry["id"]] = {name: sha256(path / name) for name in FILES}
        launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
        scored = json.loads((path / "FINAL26_CASE_SCORE.json").read_text())
        summary = json.loads((path / "summary.json").read_text())
        if launch["case_sha256"] != entry["case_sha256"] or launch["plant_mode"] != "high_rom":
            raise RuntimeError(f"launch identity mismatch: {entry['id']}")
        if not (prior["confirmed"] and scored["confirmed"] and
                scored["same_frozen_candidate"] and scored["pass"]):
            raise RuntimeError(f"case not confirmed: {entry['id']}")
        requests = summary["timing"]["requests"]
        all_compute.extend(float(x["compute_ms"]) for x in requests
                           if x.get("compute_ms") is not None)
        all_ages.extend(float(x["activation_age_ms"]) for x in requests
                        if x.get("outcome") == "ACTIVATED")
        timing = scored["timing"]
        rows.append({"index": index, "id": entry["id"],
                     "family": "fixed_start" if index < 10 else "variable_start",
                     "case_sha256": entry["case_sha256"], "output": str(path),
                     "status": launch["status"], "confirmed": scored["confirmed"],
                     "native_arrival": scored["native_arrival"],
                     "native_valid_dwell_s": scored["native_valid_dwell_s"],
                     "native_return": scored["native_return"],
                     "sampled_task_safety_pass": scored["pass"],
                     "native_count_valid": scored["native_count_valid"],
                     "native_load_count_valid": scored["native_load_count_valid"],
                     "native_contact_steps": scored["native_contact_steps"],
                     "native_rom_violation_steps": scored["native_rom_violation_steps"],
                     "native_minimum_clearance_m": scored["native_minimum_shank_clearance_m"],
                     "minimum_sampled_sleeve_gap_m": scored["minimum_measured_sleeve_gap_m"],
                     "native_peak_force_n": scored["native_peak_force_n"],
                     "native_peak_moment_nm": scored["native_peak_moment_nm"],
                     "maximum_activation_age_ms": scored.get(
                         "maximum_all_stage_plan_activation_age_ms",
                         scored["maximum_plan_activation_age_ms"]),
                     "stale_activated": len(scored["stale_activation_ids"]),
                     "planning_compute_ms": timing["planning_compute_ms"],
                     "sample_to_activation_ms": timing["sample_to_activation_ms"],
                     "control_cycle_misses": timing["control_cycle_misses"],
                     "control_grid_count": timing["control_grid_count"],
                     "control_miss_ratio": timing["control_cycle_miss_ratio"],
                     "host_elapsed_s": prior["host_elapsed_s"]})
    misses = sum(x["control_cycle_misses"] for x in rows)
    grids = sum(x["control_grid_count"] for x in rows)
    outcomes_count = Counter()
    for row in rows:
        scored = json.loads((RUNS / row["id"] / "FINAL26_CASE_SCORE.json").read_text())
        outcomes_count.update(scored["timing"]["request_outcomes"])
    outcomes = dict(outcomes_count)
    result = {"schema": "high_rom_runtime_candidate08_final26_development_confirmation_v1",
              "category": "same_source_development_not_fresh_qualification",
              "plan_sha256": sha256(DOC / "CANDIDATE08_FINAL26_PLAN.json"),
              "candidate_freeze_sha256": plan["candidate_freeze_sha256"],
              "denominator": 26, "executed": len(rows),
              "confirmed": sum(x["confirmed"] for x in rows),
              "fixed_start": {"denominator": 10,
                              "confirmed": sum(x["confirmed"] for x in rows[:10])},
              "variable_start": {"denominator": 16,
                                 "confirmed": sum(x["confirmed"] for x in rows[10:])},
              "minimum_native_valid_dwell_s": min(x["native_valid_dwell_s"] for x in rows),
              "minimum_native_clearance_m": min(x["native_minimum_clearance_m"] for x in rows),
              "minimum_sampled_sleeve_gap_m": min(x["minimum_sampled_sleeve_gap_m"] for x in rows),
              "maximum_native_force_n": max(x["native_peak_force_n"] for x in rows),
              "maximum_native_moment_nm": max(x["native_peak_moment_nm"] for x in rows),
              "maximum_activation_age_ms": max(x["maximum_activation_age_ms"] for x in rows),
              "stale_activated": sum(x["stale_activated"] for x in rows),
              "planning_compute_ms": stats(all_compute),
              "sample_to_activation_ms": stats(all_ages),
              "control_cycle_misses": misses, "control_grid_count": grids,
              "control_miss_ratio": misses / grids,
              "request_outcomes": outcomes,
              "total_host_elapsed_s": sum(x["host_elapsed_s"] for x in rows),
              "rows": rows}
    fingerprint = {
        "schema": "high_rom_runtime_final26_fingerprints_v1",
        "branch": freeze["branch"], "head_before_checkpoint": freeze["head"],
        "source_config_sha256": freeze["source_config_sha256"],
        "scoring_script_sha256": plan["scoring_script_sha256"],
        "aggregation_script_sha256": sha256(Path(__file__)),
        "plan_sha256": result["plan_sha256"],
        "progress_sha256": sha256(DOC / "CANDIDATE08_FINAL26_PROGRESS.jsonl"),
        "benchmark_spec_sha256": sha256(DOC / "BENCHMARK_SPEC.json"),
        "candidate08_benchmark_sha256": sha256(DOC / "CANDIDATE08_BENCHMARK.json"),
        "candidate08_function_sha256": sha256(DOC / "CANDIDATE08_FUNCTION.json"),
        "candidate08_low23_result_sha256": sha256(DOC / "CANDIDATE08_LOW23_RESULT.json"),
        "raw_case_files_sha256": raw_hashes}
    (DOC / "CANDIDATE08_FINAL26_RESULT.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n")
    fingerprint["final26_result_sha256"] = sha256(DOC / "CANDIDATE08_FINAL26_RESULT.json")
    (DOC / "PHASE_C_FINAL_FINGERPRINTS.json").write_text(
        json.dumps(fingerprint, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in (
        "denominator", "confirmed", "fixed_start", "variable_start",
        "minimum_native_valid_dwell_s", "minimum_native_clearance_m",
        "minimum_sampled_sleeve_gap_m", "maximum_native_force_n",
        "maximum_native_moment_nm", "maximum_activation_age_ms",
        "stale_activated", "planning_compute_ms", "sample_to_activation_ms",
        "control_miss_ratio", "request_outcomes", "total_host_elapsed_s")}, indent=2))


if __name__ == "__main__":
    main()
