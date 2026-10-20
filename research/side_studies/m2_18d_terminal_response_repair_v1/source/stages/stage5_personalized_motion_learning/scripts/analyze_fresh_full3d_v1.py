"""Apply only preregistered, time-aligned metrics/gates to frozen formal arms."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from run_fresh_full3d_batch_v1 import ARMS


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {key: None for key in ("mean", "median", "p90", "p95", "p99", "max")}
    arr = np.asarray(values, dtype=float)
    return {"mean": float(np.mean(arr)), "median": float(np.median(arr)),
            "p90": float(np.percentile(arr, 90)), "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)), "max": float(np.max(arr))}


def _episode(path: Path, case_key: str, arm: str) -> dict:
    exception = path / "runner_exception.json"
    if exception.exists() and not (path / "summary.json").exists():
        return {"case_key": case_key, "arm": arm, "status": "RUNNER_EXCEPTION",
                "abort_reason": json.loads(exception.read_text())["error"],
                "artifact_path": str(path)}
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    with np.load(path / "trace.npz") as trace:
        mask = trace["stage"] == "TASK"
        t = np.asarray(trace["time_s"][mask], dtype=float)
        actual = np.asarray(trace["evaluation_only_human_state_rad_rad_s"][mask], dtype=float)
        estimated = np.asarray(trace["estimated_human_state_rad_rad_s"][mask], dtype=float)
        qref = np.asarray(trace["reference_q_rad"][mask], dtype=float)
        dqref = np.asarray(trace["reference_dq_rad_s"][mask], dtype=float)
        force = np.asarray(trace["physical_cuff_force_world_n"][mask], dtype=float)
        moment = np.asarray(trace["physical_cuff_moment_world_nm"][mask], dtype=float)
        accel = np.asarray(trace["acceleration_limit_violation"][mask], dtype=bool)
        n = int(summary["task"]["integration_interval_count"])
        boundaries_valid = len(t) == n + 1 and (len(t) < 2 or
            bool(np.allclose(np.diff(t), 0.005, atol=1.0e-10, rtol=0)))
        if not boundaries_valid:
            raise ValueError(f"boundary/interval contract fails: {path}")
        q_error_deg = np.rad2deg(actual[:, :2] - qref) if len(t) else np.empty((0, 2))
        dq_error_deg_s = np.rad2deg(actual[:, 2:] - dqref) if len(t) else np.empty((0, 2))
        estimate_error_deg = np.rad2deg(estimated[:, :2] - actual[:, :2]) if len(t) else np.empty((0, 2))
        interval_dt = np.diff(t)
        force_integral = float(np.sum(np.linalg.norm(force[:-1], axis=1) * interval_dt))
        moment_integral = float(np.sum(np.linalg.norm(moment[:-1], axis=1) * interval_dt))
        if not math.isclose(force_integral, float(summary["task"]["force_integral_n_s"]),
                            rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError(f"force integral inconsistent with N physical intervals: {path}")
        true_state_final = actual[-1] if len(t) else np.full(4, np.nan)
    case = summary["qualification"]["hidden_case_evaluation_only"]
    transitions = summary["task"]["phase_transitions"]
    adaptive_trace = summary["adaptation_trace"]
    beta_attempts = [row for row in adaptive_trace if row["diagnostics"].get("beta_update", {}).get("attempted")]
    beta_accepts = [row for row in beta_attempts if row["diagnostics"]["beta_update"].get("accepted")]
    cap_count = sum(bool(row["diagnostics"]["beta_update"].get("rate_limit_hit", False)) for row in beta_accepts)
    residual_nonzero = sum(row["residual_step_l2"] > 1e-12 for row in adaptive_trace)
    decisions = summary["decisions"]
    proposed_ages = [float(row["stale_plan_age_at_activation_s"]) for row in decisions
                     if row.get("stale_plan_age_at_activation_s") is not None]
    activated_ages = [float(row["activation_timestamp_s"] - row["request_measurement_timestamp_s"])
                      for row in decisions if row.get("plan_activated") and
                      row.get("activation_timestamp_s") is not None]
    miss_count = sum(row.get("activation_rejected_reason") == "STALE_PLAN_MAXIMUM_AGE" or
                     (row.get("stale_plan_age_at_activation_s") is not None and
                      row["stale_plan_age_at_activation_s"] > 0.1 + 1e-12)
                     for row in decisions)
    activated_stale = sum(bool(row.get("plan_activated")) and
                          row.get("activation_timestamp_s") is not None and
                          row["activation_timestamp_s"] - row["request_measurement_timestamp_s"] > 0.1 + 1e-12
                          for row in decisions)
    phase_times = {"OUTBOUND": None, "HOLD": None, "RETURN": None}
    time_zero = t[0] if len(t) else None
    previous = time_zero
    for transition in transitions:
        phase = transition["from"]
        if phase in phase_times and previous is not None:
            phase_times[phase] = float(transition["time_s"] - previous)
        previous = float(transition["time_s"])
    if summary["status"] != "COMPLETE" and previous is not None and len(t):
        current_phase = transitions[-1]["to"] if transitions else "OUTBOUND"
        if current_phase in phase_times:
            phase_times[current_phase] = float(t[-1] - previous)
    start = np.asarray(case["task"]["start_deg"], dtype=float)
    result = {
        "case_key": case_key, "arm": arm, "cell": case.get("cell"),
        "evidence_category": summary["evidence_category"],
        "status": summary["status"], "abort_reason": summary["abort_reason"],
        "artifact_path": str(path), "time_alignment_valid": boundaries_valid,
        "task_duration_s": float(summary["task"]["physics_duration_s"]),
        "phase_durations_s": phase_times,
        "hold_valid": any(row["from"] == "HOLD" and row["to"] == "RETURN"
                          for row in transitions),
        "q_rmse_combined_deg": None if not len(q_error_deg) else float(np.sqrt(np.mean(q_error_deg**2))),
        "q_rmse_joint_deg": None if not len(q_error_deg) else np.sqrt(np.mean(q_error_deg**2, axis=0)).tolist(),
        "q_abs_p95_deg": None if not len(q_error_deg) else float(np.percentile(np.abs(q_error_deg), 95)),
        "q_abs_max_deg": None if not len(q_error_deg) else float(np.max(np.abs(q_error_deg))),
        "dq_rmse_combined_deg_s": None if not len(dq_error_deg_s) else float(np.sqrt(np.mean(dq_error_deg_s**2))),
        "estimate_q_rmse_combined_deg": None if not len(estimate_error_deg) else float(np.sqrt(np.mean(estimate_error_deg**2))),
        "terminal_q_error_deg": (np.rad2deg(true_state_final[:2]) - start).tolist(),
        "terminal_dq_deg_s": np.rad2deg(true_state_final[2:]).tolist(),
        "peak_cuff_force_n": summary["task"]["peak_force_n"],
        "peak_cuff_moment_nm": summary["task"]["peak_moment_nm"],
        "force_integral_n_s": force_integral, "moment_integral_nm_s": moment_integral,
        "minimum_deployable_clearance_m": summary["task"]["minimum_session_clearance_m_deployable"],
        "minimum_true_clearance_m": summary["task"]["minimum_true_physical_clearance_m_evaluation_only"],
        "task_shank_bed_contact_steps": summary["qualification"]["true_physics"]["shank_bed_contact_steps"]["TASK"],
        "commissioning_shank_bed_contact_steps": summary["qualification"]["true_physics"]["shank_bed_contact_steps"]["COMMISSIONING"],
        "task_rom_violation_steps": summary["qualification"]["true_physics"]["rom_violation_steps"]["TASK"],
        "actual_acceleration_violation_boundaries": int(np.sum(accel)),
        "peak_robot_torque_fraction": summary["task"]["peak_robot_torque_fraction"],
        "beta_attempt_count": len(beta_attempts), "beta_accept_count": len(beta_accepts),
        "beta_rate_limit_hit_count": cap_count,
        "beta_step_last_ten_accepted_l2": [row["beta_step_l2"] for row in beta_accepts[-10:]],
        "beta_step_last_ten_proposals_l2": [row["beta_step_l2"] for row in beta_attempts[-10:]],
        "residual_nonzero_update_count": residual_nonzero,
        "residual_update_count": summary["task"]["residual_update_count"],
        "final_belief_sequence": summary["task"]["final_belief_sequence"],
        "planner_runtime_ms": _percentiles([float(row["planning_runtime_ms_measured"]) for row in decisions]),
        "planner_decision_count": len(decisions), "deadline_miss_count": miss_count,
        "planner_infeasible_count": sum(row.get("activation_rejected_reason") == "NO_FEASIBLE_WAYPOINT"
                                        for row in decisions),
        "activated_stale_plan_count": activated_stale,
        "proposed_plan_age_s": _percentiles(proposed_ages),
        "activated_plan_age_s": _percentiles(activated_ages),
        "measurement_age_at_request_s": _percentiles([
            float(row["measurement_age_at_request_s"]) for row in decisions]),
        "value_hook_zero": all(row.get("value_hook_numeric_value") == 0.0 for row in decisions),
        "truth_firewall_record": summary["truth_firewall"],
    }
    # Keep complete boundary errors available for pooled p95 and independent audit.
    result["q_absolute_error_deg"] = np.abs(q_error_deg).ravel().tolist()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-bundle", type=Path, required=True)
    parser.add_argument("--formal-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.formal_root / "ANALYSIS.json"
    if output.exists():
        raise FileExistsError(output)
    generation = json.loads((args.case_bundle / "generation_summary.json").read_text())
    rows = []
    for key in generation["case_keys"]:
        for arm in ARMS:
            rows.append(_episode(args.formal_root / key / arm, key, arm))
    adaptive = [row for row in rows if row["arm"] == "continual_adaptive"]
    completed = [row for row in adaptive if row["status"] == "COMPLETE"]
    by_key = {(row["case_key"], row["arm"]): row for row in rows}
    jointly_complete = [key for key in generation["case_keys"] if
                        all(by_key[(key, arm)]["status"] == "COMPLETE" for arm in ARMS)]
    paired = {}
    for comparator in ARMS[1:]:
        a = np.array([by_key[(key, "continual_adaptive")]["q_rmse_combined_deg"]
                      for key in jointly_complete])
        b = np.array([by_key[(key, comparator)]["q_rmse_combined_deg"]
                      for key in jointly_complete])
        paired[comparator] = {
            "joint_completion_count": len(jointly_complete),
            "adaptive_complete_comparator_failed_count": sum(
                by_key[(key, "continual_adaptive")]["status"] == "COMPLETE" and
                by_key[(key, comparator)]["status"] != "COMPLETE"
                for key in generation["case_keys"]),
            "comparator_complete_adaptive_failed_count": sum(
                by_key[(key, comparator)]["status"] == "COMPLETE" and
                by_key[(key, "continual_adaptive")]["status"] != "COMPLETE"
                for key in generation["case_keys"]),
            "comparator_total_completed": sum(
                by_key[(key, comparator)]["status"] == "COMPLETE"
                for key in generation["case_keys"]),
            "adaptive_median_rmse_deg": None if not len(a) else float(np.median(a)),
            "comparator_median_rmse_deg": None if not len(b) else float(np.median(b)),
            "median_ratio": None if not len(a) else float(np.median(a) / np.median(b)),
            "adaptive_win_count": int(np.sum(a < b)),
        }
    completed_cells = {tuple(row["cell"][field] for field in ("family", "range"))
                       for row in completed}
    pooled_error = [value for row in completed for value in row["q_absolute_error_deg"]]
    safety_failures = []
    for row in adaptive:
        if row["status"] == "RUNNER_EXCEPTION":
            safety_failures.append({"case_key": row["case_key"], "reason": "RUNNER_EXCEPTION"})
            continue
        checks = {"true_clearance": row["minimum_true_clearance_m"] is not None and row["minimum_true_clearance_m"] < 0,
                  "shank_bed_contact": row["task_shank_bed_contact_steps"] > 0,
                  "rom": row["task_rom_violation_steps"] > 0,
                  "acceleration": row["actual_acceleration_violation_boundaries"] > 0,
                  "force": row["peak_cuff_force_n"] is not None and row["peak_cuff_force_n"] > 200,
                  "moment": row["peak_cuff_moment_nm"] is not None and row["peak_cuff_moment_nm"] > 60,
                  "robot_torque": row["peak_robot_torque_fraction"] is not None and row["peak_robot_torque_fraction"] > 1.0 + 1e-12}
        safety_failures.extend({"case_key": row["case_key"], "reason": name}
                               for name, fail in checks.items() if fail)
    gates = {
        "g1_provenance_and_count_pre_audit": len(rows) == 72 and all(
            row["status"] == "RUNNER_EXCEPTION" or
            (row["evidence_category"] == "formal_fresh_full3d_qualification" and
             row["time_alignment_valid"] and row["value_hook_zero"] and
             not row["truth_firewall_record"]["human_q_dq_truth_in_controller"])
            for row in rows),
        "g2_completion_and_cell_coverage": len(completed) >= 20 and len(completed_cells) == 12
            and all(row["hold_valid"] for row in completed),
        "g3_adaptive_physical_safety": not safety_failures,
        "g4_stale_plan_contract": all(row["status"] != "RUNNER_EXCEPTION" and
            row["activated_stale_plan_count"] == 0 for row in rows)
            and all(row["status"] != "RUNNER_EXCEPTION" and row["deadline_miss_count"] == 0
                    for row in adaptive),
        "g5_time_aligned_tracking": bool(completed) and
            float(np.median([row["q_rmse_combined_deg"] for row in completed])) <= 2.0 and
            float(np.percentile(pooled_error, 95)) <= 5.0 and
            float(np.median([row["dq_rmse_combined_deg_s"] for row in completed])) <= 5.0,
        "g6_adaptation_exercised": sum(row["status"] != "RUNNER_EXCEPTION" and
            row["beta_attempt_count"] >= 1 and row["beta_accept_count"] >= 1 and
            row["residual_nonzero_update_count"] >= 1 for row in adaptive) >= 18,
        "g7_paired_effect": all(
            len(completed) >= paired[arm]["comparator_total_completed"] + 4
            and paired[arm]["adaptive_complete_comparator_failed_count"] >= 4
            and paired[arm]["comparator_complete_adaptive_failed_count"] <= 1
            for arm in ARMS[1:]),
    }
    for row in rows:
        row.pop("q_absolute_error_deg", None)
    result = {"schema": "fresh_full3d_qualification_v1_analysis",
        "case_count": len(generation["case_keys"]), "arm_count": len(rows),
        "completion_by_arm": {arm: sum(row["arm"] == arm and row["status"] == "COMPLETE"
                                  for row in rows) for arm in ARMS},
        "jointly_complete_keys": jointly_complete, "paired": paired,
        "adaptive_safety_failures": safety_failures,
        "adaptive_pooled_completed_q_abs_p95_deg": None if not pooled_error else float(np.percentile(pooled_error, 95)),
        "adaptive_planner_runtime_ms": _percentiles([value for row in adaptive
            if row["status"] != "RUNNER_EXCEPTION" for value in
            json.loads((Path(row["artifact_path"]) / "summary.json").read_text())["timing"]["high_level_planning_runtime_ms"]]),
        "gates_pre_independent_audit": gates, "all_numeric_gates_pass": all(gates.values()),
        "rows": rows}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_numeric_gates_pass": result["all_numeric_gates_pass"],
                      "completion_by_arm": result["completion_by_arm"],
                      "analysis_path": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
