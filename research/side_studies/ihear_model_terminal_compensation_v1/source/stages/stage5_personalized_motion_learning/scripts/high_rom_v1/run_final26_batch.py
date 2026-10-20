"""Run and score at most two frozen C08 High-ROM development cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

from runtime_benchmark import case_timing
from score_variable_start import score_one
from summarize_phase_b import score


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_runtime_v1"
PLAN = DOC / "CANDIDATE08_FINAL26_PLAN.json"
OUTPUT = STAGE / "results/high_rom_runtime_v1/candidate08_final26"
STOP = STAGE / "docs/high_rom_v1/STOP"
PROGRESS = DOC / "CANDIDATE08_FINAL26_PROGRESS.jsonl"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    assert len(plan["rows"]) == plan["denominator"] == 26
    if args.start < 0 or args.start + args.count > 26:
        raise ValueError("batch outside frozen denominator")
    if digest(DOC / "CANDIDATE08_FREEZE.json") != plan["candidate_freeze_sha256"]:
        raise RuntimeError("candidate freeze manifest drift")
    for relative, expected in plan["scoring_script_sha256"].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f"scoring/runner script drift: {relative}")
    frozen = json.loads((DOC / "CANDIDATE08_FREEZE.json").read_text())
    contract = json.loads((STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json").read_text())["scoring"]
    prior = json.loads((STAGE / "results/high_rom_runtime_v1/candidate08_gate/high_120_sync/HIGH_ROM_CASE_RESULT.json").read_text())
    identity = {"runner_source_files_sha256": prior["source_files_sha256"],
                "options_sha256": prior["options_sha256"],
                "runtime_relative_path": "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py"}
    for index in range(args.start, args.start + args.count):
        if STOP.exists():
            raise RuntimeError("HIGH_ROM_USER_STOP")
        for relative, expected in frozen["source_config_sha256"].items():
            if digest(ROOT / relative) != expected:
                raise RuntimeError(f"candidate source/config drift: {relative}")
        entry = plan["rows"][index]
        case_path = ROOT / entry["case"]
        if digest(case_path) != entry["case_sha256"]:
            raise RuntimeError(f"registered case drift: {entry['id']}")
        case_data = json.loads(case_path.read_text())
        if case_data["task"]["goal_deg"] != [120.0, 120.0]:
            raise RuntimeError(f"registered goal drift: {entry['id']}")
        dest = OUTPUT / entry["id"]
        if dest.exists():
            raise FileExistsError(dest)
        command = [sys.executable, str(STAGE / "scripts/high_rom_v1/run_dev_case.py"),
                   "--case", str(case_path), "--output", str(dest),
                   "--plant-mode", "high_rom", "--host-monitor-limit-s", "300"]
        started = monotonic()
        try:
            process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                     text=True, timeout=330, check=False)
            exit_code = process.returncode
            process_tail = process.stderr[-1000:]
        except subprocess.TimeoutExpired as exc:
            exit_code = None
            process_tail = f"TimeoutExpired: {exc}"
        launch_path = dest / "HIGH_ROM_CASE_RESULT.json"
        record = {"index": index, "id": entry["id"], "output": str(dest),
                  "exit_code": exit_code, "host_elapsed_s": monotonic() - started,
                  "runner_error_tail": process_tail, "confirmed": False}
        if launch_path.is_file():
            launch = json.loads(launch_path.read_text())
            record["status"] = launch["status"]
            record["abort_reason"] = launch.get("abort_reason")
            if (dest / "runtime_artifacts.json").is_file():
                case = {"case_key": entry["id"], "path": entry["case"],
                        "sha256": entry["case_sha256"],
                        "start_deg": case_data["task"]["start_deg"],
                        "goal_deg": case_data["task"]["goal_deg"]}
                try:
                    result = score_one(case, dest, contract,
                                       case_data.get("candidate", "high_rom_sync_feedback_v1"), identity)
                    result.update(score(dest, {**case,
                                               "physical_variant": "registered_interpolated",
                                               "candidate": case_data.get("candidate", "high_rom_sync_feedback_v1")},
                                        contract, goal_deg=case["goal_deg"], start_deg=case["start_deg"]))
                    snapshot = json.loads((dest / "config_snapshot.json").read_text())
                    native_valid = (result["native_arrival"] and result["native_valid_dwell_s"] >= .5
                                    and result["native_return"] and result["native_count_valid"]
                                    and result["native_load_count_valid"]
                                    and result["native_contact_steps"] == 0
                                    and result["native_rom_violation_steps"] == 0
                                    and result["native_peak_force_n"] <= 200.
                                    and result["native_peak_moment_nm"] <= 60.
                                    and result["native_minimum_shank_clearance_m"] >= 0.
                                    and result["native_phase_limit_violation_count"] == 0
                                    and not result["stale_activation_ids"])
                    plant_valid = (launch["plant_mode"] == "high_rom" and
                                   snapshot["human_hard_rom_deg"] == [[0.0, 125.0], [0.0, 125.0]])
                    confirmed = bool(result["pass"] and result["same_frozen_candidate"]
                                     and native_valid and plant_valid and
                                     launch["case_sha256"] == entry["case_sha256"])
                    timing = case_timing({"id": entry["id"], "plant": "high_rom",
                                          "case": str(case_path.relative_to(STAGE))}, dest)
                    timing.pop("_compute_values")
                    timing.pop("_age_values")
                    result.update(id=entry["id"], index=index, confirmed=confirmed,
                                  plant_valid=plant_valid, timing=timing)
                    (dest / "FINAL26_CASE_SCORE.json").write_text(
                        json.dumps(result, indent=2, allow_nan=False) + "\n")
                    record.update(confirmed=confirmed,
                                  native_dwell_s=result["native_valid_dwell_s"],
                                  min_native_clearance_m=result["native_minimum_shank_clearance_m"],
                                  stale_activated=len(result["stale_activation_ids"]),
                                  compute_p95_ms=timing["planning_compute_ms"]["p95"],
                                  activation_p95_ms=timing["sample_to_activation_ms"]["p95"],
                                  control_miss_ratio=timing["control_cycle_miss_ratio"])
                except BaseException as exc:
                    record["scoring_error"] = f"{type(exc).__name__}: {exc}"
        with PROGRESS.open("a") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
        print(json.dumps({key: record.get(key) for key in (
            "index", "id", "status", "confirmed", "host_elapsed_s",
            "compute_p95_ms", "activation_p95_ms", "control_miss_ratio",
            "scoring_error")}), flush=True)
        if not record["confirmed"]:
            raise RuntimeError(f"FINAL_FUNCTION_CONFIRMATION_FAIL: {entry['id']}")


if __name__ == "__main__":
    main()
