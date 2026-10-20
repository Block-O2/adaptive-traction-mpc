"""Summarize consumed-case DEV-A replays without post-outcome exclusions."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, start_episode


def _float(value):
    return None if value is None or not np.isfinite(value) else float(value)


def _quantiles(values):
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    return {
        "count": len(array), "mean": float(np.mean(array)),
        "median": float(np.median(array)), "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)), "max": float(np.max(array)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads((args.results / "batch_status.json").read_text(encoding="utf-8"))
    rows = []
    for batch_row in batch["rows"]:
        key = batch_row["case_key"]
        directory = args.results / key
        path = directory / "summary.json"
        if not path.exists():
            rows.append({"case_key": key, "status": "PRESERVED_RUNNER_EXCEPTION",
                         "abort_reason": batch_row.get("abort_reason")})
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        recovery = summary["dev_a_recovery"]
        registered_task = summary["qualification"]["hidden_case_evaluation_only"]["task"]
        spec = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                       start_return_target_rad=tuple(np.radians(registered_task["start_deg"])),
                       outbound_goal_target_rad=tuple(np.radians(registered_task["goal_deg"])))
        initial_recovery_state = np.asarray(recovery["start_estimated_state_rad_rad_s"])
        try:
            start_episode(spec, initial_recovery_state[:2], initial_recovery_state[2:],
                          acceleration_authority_valid=False)
            matched_old_handoff_eligible, matched_old_handoff_reason = True, None
        except ValueError as error:
            matched_old_handoff_eligible, matched_old_handoff_reason = False, str(error)
        trace = np.load(directory / "trace.npz")
        stages = trace["stage"]
        commissioning_indices = np.where(stages == "COMMISSIONING")[0]
        task_indices = np.where(stages == "TASK")[0]
        ref = trace["reference_q_rad"]
        truth = trace["evaluation_only_human_state_rad_rad_s"]
        estimated = trace["estimated_human_state_rad_rad_s"]
        commissioning_last = commissioning_indices[-1]
        error_deg = np.degrees(np.max(np.abs(
            truth[commissioning_last, :2] - ref[commissioning_last]
        )))
        planner = recovery["planner_decisions"]
        task_decisions = summary["decisions"]
        all_planning_ms = [float(item["runtime_ms"]) for item in planner]
        all_planning_ms += [float(item["planning_runtime_ms_measured"])
                            for item in task_decisions]
        recovery_indices = np.where(stages == "ACTIVE_RECOVERY")[0]
        recovery_torque = trace["cr12_actuator_command_nm"][recovery_indices]
        recovery_du = (np.linalg.norm(np.diff(recovery_torque, axis=0), axis=1)
                       if len(recovery_torque) > 1 else np.array([]))
        task_executed_intervals = int(summary["task"]["integration_interval_count"])
        task_rmse_deg = None
        if task_executed_intervals > 0 and len(task_indices):
            difference = np.degrees(truth[task_indices, :2] - ref[task_indices])
            task_rmse_deg = np.sqrt(np.mean(difference**2, axis=0)).tolist()
        true_physics = summary.get("qualification", {}).get("true_physics", {})
        row = {
            "case_key": key, "status": summary["status"],
            "abort_reason": summary.get("abort_reason"),
            "initialization_succeeded": True,
            "commissioning_completed": len(commissioning_indices) > 0,
            "commissioning_duration_s": summary["commissioning"]["duration_s"],
            "commissioning_endpoint_true_reference_max_abs_deg": error_deg,
            "commissioning_endpoint_estimated_reference_max_abs_deg": float(
                np.degrees(np.max(np.abs(estimated[commissioning_last, :2]
                                         - ref[commissioning_last])))
            ),
            "recovery_entered": recovery["entered"],
            "matched_old_immediate_handoff_eligible_from_same_post_commissioning_state":
                matched_old_handoff_eligible,
            "matched_old_immediate_handoff_reason": matched_old_handoff_reason,
            "recovery_succeeded": recovery["succeeded"],
            "recovery_abort_reason": recovery["abort_reason"],
            "recovery_duration_s": recovery["duration_s"],
            "recovery_endpoint_estimated_start_max_abs_deg": float(
                np.degrees(np.max(np.abs(np.asarray(recovery["end_estimated_state_rad_rad_s"])[:2]
                                         - ref[commissioning_last])))
            ),
            "recovery_endpoint_true_start_max_abs_deg_evaluation_only": float(
                np.degrees(np.max(np.abs(np.asarray(recovery["end_true_state_evaluation_only_rad_rad_s"])[:2]
                                         - ref[commissioning_last])))
            ),
            "task_entered": task_executed_intervals > 0,
            "task_full_complete": summary["status"] == "COMPLETE",
            "task_time_aligned_q_rmse_deg_evaluation_only": task_rmse_deg,
            "task_physics_duration_s": summary["task"]["physics_duration_s"],
            "recovery_peak_force_n": recovery["peak_force_n"],
            "recovery_peak_moment_nm": recovery["peak_moment_nm"],
            "recovery_force_integral_n_s": recovery["force_integral_n_s"],
            # An aborted case may have one TASK-labelled terminal boundary
            # without executing any TASK interval.  Do not call its measured
            # boundary wrench or clearance an executed-task metric.
            "task_peak_force_n": (summary["task"]["peak_force_n"]
                                  if task_executed_intervals else None),
            "task_peak_moment_nm": (summary["task"]["peak_moment_nm"]
                                    if task_executed_intervals else None),
            "task_force_integral_n_s": summary["task"]["force_integral_n_s"],
            "recovery_minimum_deployable_clearance_m": _float(
                recovery["minimum_session_clearance_m"]),
            "recovery_minimum_true_clearance_m_evaluation_only": _float(
                recovery.get("minimum_true_physical_clearance_m_evaluation_only")),
            "task_minimum_deployable_clearance_m": (summary["task"].get(
                "minimum_session_clearance_m_deployable")
                if task_executed_intervals else None),
            "task_minimum_true_clearance_m_evaluation_only": (summary["task"].get(
                "minimum_true_physical_clearance_m_evaluation_only")
                if task_executed_intervals else None),
            "recovery_contact_physical_steps_evaluation_only": recovery.get(
                "shank_bed_contact_physical_steps_evaluation_only"),
            "task_contact_physical_steps_evaluation_only": true_physics.get(
                "shank_bed_contact_steps", {}).get("TASK"),
            "recovery_planner_decisions": len(planner),
            "task_planner_decisions": len(task_decisions),
            "planner_runtime_ms": all_planning_ms,
            "planner_stale_decisions": sum(bool(item.get("stale")) for item in planner)
                + sum(item.get("activation_rejected_reason") == "STALE_PLAN_MAXIMUM_AGE"
                      for item in task_decisions),
            "first_fitted_model_torque_delta_norm_nm": recovery[
                "first_new_model_command_delta_norm_nm"],
            "recovery_consecutive_torque_delta_norm_nm": recovery_du.tolist(),
            "beta_update_count_during_recovery": recovery["beta_update_count_during_recovery"],
            "residual_update_count_during_recovery": recovery[
                "residual_update_count_during_recovery"],
            "task_adaptation_updates": summary["task"]["continual_adaptation_update_count"],
        }
        rows.append(row)
    complete_rows = [row for row in rows if row.get("initialization_succeeded")]
    all_planner_ms = [value for row in complete_rows for value in row["planner_runtime_ms"]]
    result = {
        "schema": "full3d_dev_a_development_regression_summary_v1",
        "evidence_category": "development_replay_of_consumed_formal_v1_cases",
        "case_count": len(rows),
        "initialization_succeeded_count": sum(row.get("initialization_succeeded", False)
                                               for row in rows),
        "commissioning_completed_count": sum(row.get("commissioning_completed", False)
                                              for row in rows),
        "recovery_entered_count": sum(row.get("recovery_entered", False) for row in rows),
        "matched_old_immediate_handoff_eligible_count": sum(
            row.get("matched_old_immediate_handoff_eligible_from_same_post_commissioning_state", False)
            for row in rows),
        "recovery_succeeded_count": sum(row.get("recovery_succeeded", False) for row in rows),
        "task_entered_count": sum(row.get("task_entered", False) for row in rows),
        "full_task_complete_count": sum(row.get("task_full_complete", False) for row in rows),
        "abort_reason_counts": dict(Counter(row.get("abort_reason") or "NONE" for row in rows)),
        "commissioning_endpoint_error_deg": _quantiles([
            row["commissioning_endpoint_true_reference_max_abs_deg"] for row in complete_rows]),
        "recovery_duration_s": _quantiles([
            row["recovery_duration_s"] for row in complete_rows if row["recovery_entered"]]),
        "planner_runtime_ms": _quantiles(all_planner_ms),
        "stale_planner_decision_count": sum(row["planner_stale_decisions"] for row in complete_rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
