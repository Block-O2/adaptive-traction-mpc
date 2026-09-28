"""Score only preregistered rolling-suffix development cases already on disk."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = Path(__file__).resolve().parent
sys.path[:0] = [str(STAGE / "scripts/high_rom_v1"),
                str(STAGE / "docs/waypoint_smoothness_v1")]

from analyze_repair import inspect  # noqa: E402
from runtime_benchmark import case_timing  # noqa: E402
from summarize_phase_b import score  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quota-used", type=int, required=True)
    args = parser.parse_args()
    freeze = json.loads((DOC / "ROLLING_SUFFIX_SPLICE_FREEZE.json").read_text())
    for relative, expected in freeze["source_config_sha256"].items():
        if sha(STAGE / relative) != expected:
            raise RuntimeError("frozen source/config drift: " + relative)
    contract = json.loads((STAGE / "docs/high_rom_v1/PHASE_B_MATRIX.json").read_text())["scoring"]
    rows = []
    for entry in freeze["cases"]:
        path = STAGE / "results/rolling_suffix_splice_v1/eight_case" / entry["id"]
        case_path = STAGE / entry["case"]
        if sha(case_path) != entry["case_sha256"]:
            raise RuntimeError("registered case drift: " + entry["id"])
        if not (path / "HIGH_ROM_CASE_RESULT.json").exists():
            continue
        case = json.loads(case_path.read_text())
        launch = json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())
        row = dict(id=entry["id"], plant=entry["plant"], output=str(path),
                   case_sha256=entry["case_sha256"], status=launch["status"],
                   abort_reason=launch.get("abort_reason"),
                   host_elapsed_s=launch["elapsed_host_s"],
                   runtime_sha256=launch["runtime_sha256"],
                   result_sha256=sha(path / "HIGH_ROM_CASE_RESULT.json"))
        if (path / "summary.json").exists() and (path / "trace.npz").exists():
            scored = score(path, dict(
                case_key=case["case_key"], path=str(case_path.relative_to(ROOT)),
                sha256=entry["case_sha256"], candidate=case.get(
                    "coordination_candidate", "original_low_rom"),
                physical_variant=("original_low_rom" if entry["plant"] == "low_rom"
                                  else "registered_interpolated")),
                contract, goal_deg=case["task"]["goal_deg"],
                start_deg=case["task"]["start_deg"])
            smooth, _ = inspect(path)
            timing = case_timing(entry, path)
            ref_stop = smooth["non_task_reference_near_stop_longest_s"]
            baseline = freeze["scoring"]["low_rom_reference_near_stop_baseline_s"].get(entry["id"])
            smooth_pass = (ref_stop <= freeze["scoring"]["high_rom_reference_near_stop_s_max"]
                           if entry["plant"] == "high_rom"
                           else ref_stop <= baseline + freeze["scoring"]["low_rom_comparison_tolerance_s"])
            runtime_pass = bool(
                timing["planning_compute_ms"]["p95"] <= 30.
                and timing["sample_to_activation_ms"]["p95"] <= 55.
                and timing["control_cycle_miss_ratio"] < .1182
                and timing["expired_activated"] == 0)
            row.update(task_safety_pass=scored["pass"],
                       task_safety_failed=[k for k, v in scored["conditions"].items() if not v],
                       true_goal_dwell_s=scored["true_goal_continuous_dwell_s"],
                       actual_return=scored["true_return"],
                       reference_near_stop_s=ref_stop,
                       actual_near_stop_s=smooth["non_task_actual_near_stop_longest_s"],
                       smoothness_pass=smooth_pass,
                       switch_jumps_deg_deg_s_deg_s2=[smooth[k] for k in (
                           "exact_switch_max_q_jump_deg",
                           "exact_switch_max_dq_jump_deg_s",
                           "exact_switch_max_ddq_jump_deg_s2")],
                       robot_velocity_valley_deg_s=smooth["switch_robot_speed_valley_deg_s"],
                       cuff_force_slew_5ms_n_s=smooth["cuff_vector_force_slew_n_s_5ms"],
                       peak_force_n=scored["peak_force_n"],
                       peak_moment_nm=scored["peak_moment_nm"],
                       minimum_session_clearance_m=scored["minimum_session_shank_clearance_m"],
                       compute_ms=timing["planning_compute_ms"],
                       activation_ms=timing["sample_to_activation_ms"],
                       control_miss_ratio=timing["control_cycle_miss_ratio"],
                       stale_activated=timing["expired_activated"],
                       request_outcomes=timing["request_outcomes"],
                       runtime_pass=runtime_pass,
                       pass_all=bool(scored["pass"] and smooth_pass and runtime_pass))
        else:
            row.update(task_safety_pass=False, smoothness_pass=False,
                       runtime_pass=False, pass_all=False,
                       classification="INCOMPLETE_OR_RUNTIME_EXCEPTION")
        rows.append(row)
    result = dict(schema="rolling_suffix_splice_v1_eight_case_progress",
                  freeze_sha256=sha(DOC / "ROLLING_SUFFIX_SPLICE_FREEZE.json"),
                  completed=len(rows), passed=sum(r["pass_all"] for r in rows),
                  remaining=[x["id"] for x in freeze["cases"]
                             if x["id"] not in {r["id"] for r in rows}],
                  rows=rows)
    (DOC / "EIGHT_CASE_PROGRESS.json").write_text(json.dumps(result, indent=2) + "\n")
    state = json.loads((DOC / "STATE.json").read_text())
    state.update(phase="EIGHT_CASE_IN_PROGRESS" if result["remaining"] else "EIGHT_CASE_COMPLETE",
                 latest_used_percent=args.quota_used,
                 eight_case_completed=[r["id"] for r in rows],
                 eight_case_remaining=result["remaining"],
                 eight_case_passed=result["passed"],
                 next_action=("Check quota and run the next frozen case without edits"
                              if result["remaining"] else "Finalize report and optional read-only audit"))
    (DOC / "STATE.json").write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(dict(completed=result["completed"], passed=result["passed"],
                          remaining=result["remaining"],
                          last=None if not rows else dict(id=rows[-1]["id"],
                                                           pass_all=rows[-1]["pass_all"],
                                                           runtime_pass=rows[-1]["runtime_pass"]))))


if __name__ == "__main__":
    main()
