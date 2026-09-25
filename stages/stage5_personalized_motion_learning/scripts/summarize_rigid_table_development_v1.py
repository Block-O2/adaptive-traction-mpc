"""Read-only outcome and boundary-aligned mechanics summary for old24 DEV pairs."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.rigid_table_assembly_v1.assembly import _capsule_axis_gap


STAGE = Path(__file__).resolve().parents[1]
OLD_RUNS = STAGE / "results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2"
ASSEMBLY = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1"


def finite_min(values: np.ndarray) -> float | None:
    arr = np.asarray(values, dtype=float)
    good = arr[np.isfinite(arr)]
    return float(np.min(good)) if good.size else None


def one_row(mapping: dict, runs: Path) -> dict:
    key = mapping["case_key"]
    old_path = OLD_RUNS / key / "summary.json"
    old = json.loads(old_path.read_text()) if old_path.exists() else None
    valid = mapping["revised_validity"]["valid"]
    row = {"case_key": key,
           "original_proximal_gap_m": mapping["exact_required_assembly_changes"]["old_proximal_gap_m"],
           "revised_proximal_gap_m": mapping["exact_required_assembly_changes"]["new_proximal_gap_m"],
           "assembly_change_rule": mapping["exact_required_assembly_changes"]["rule"],
           "initial_endpoint_assembly_valid": valid,
           "assembly_reason": mapping["revised_validity"]["reason"],
           "old_dev_a_status": old["status"] if old else None,
           "old_dev_a_abort_reason": old.get("abort_reason") if old else None,
           "new_status": "NOT_EXECUTED_INVALID_ASSEMBLY" if not valid else None}
    if not valid:
        return row
    run = runs / key
    if not (run / "summary.json").exists():
        row["new_status"] = "MISSING_OR_INCOMPLETE_ARTIFACT"
        return row
    summary = json.loads((run / "summary.json").read_text())
    contact = json.loads((run / "contact_summary.json").read_text())
    case = json.loads((ASSEMBLY / "cases" / f"{key}.json").read_text())
    human, geometry, _, _ = hidden_plant(case)
    trace = np.load(run / "trace.npz", allow_pickle=True)
    stage = np.asarray(trace["stage"]).astype(str)
    time = np.asarray(trace["time_s"], dtype=float)
    q_true = np.asarray(trace["evaluation_only_human_state_rad_rad_s"], dtype=float)[:, :2]
    q_hat = np.asarray(trace["estimated_human_state_rad_rad_s"], dtype=float)[:, :2]
    q_ref = np.asarray(trace["reference_q_rad"], dtype=float)
    task_mask = stage == "TASK"
    commissioning_mask = stage == "COMMISSIONING"
    if len(stage) != len(time) or q_true.shape != q_ref.shape:
        raise RuntimeError(f"unaligned trace for {key}")
    if not summary["task"]["boundary_interval_relation_holds"]:
        raise RuntimeError(f"N/N+1 boundary interval relation failed for {key}")
    ref_commissioning_gaps = np.array([
        _capsule_axis_gap(q_ref[i], human, geometry)["shank_m"]
        for i in np.flatnonzero(commissioning_mask)])
    true_commissioning_gaps = np.array([
        _capsule_axis_gap(q_true[i], human, geometry)["shank_m"]
        for i in np.flatnonzero(commissioning_mask)])
    first_bad = np.flatnonzero(ref_commissioning_gaps < 0)
    commissioning_indices = np.flatnonzero(commissioning_mask)
    first_bad_idx = int(commissioning_indices[first_bad[0]]) if len(first_bad) else None
    cuff_f = np.linalg.norm(np.asarray(trace["physical_cuff_force_world_n"], dtype=float), axis=1)
    cuff_m = np.linalg.norm(np.asarray(trace["physical_cuff_moment_world_nm"], dtype=float), axis=1)
    planner = np.asarray(summary["timing"]["high_level_planning_runtime_ms"], dtype=float)
    task_error = q_true[task_mask] - q_ref[task_mask]
    task_estimation = q_hat[task_mask] - q_true[task_mask]
    physical_cost = np.asarray(trace["interval_force_cost_n_s"], dtype=float)
    row.update({
        "new_status": summary["status"],
        "new_abort_reason": summary.get("abort_reason"),
        "commissioning_completed": bool(summary.get("commissioning")),
        "recovery_entered": summary.get("dev_a_recovery", {}).get("entered"),
        "recovery_succeeded": summary.get("dev_a_recovery", {}).get("succeeded"),
        "recovery_duration_s": summary.get("dev_a_recovery", {}).get("duration_s"),
        "task_entered": bool(summary["task"]["integration_interval_count"] > 0),
        "task_physics_duration_s": summary["task"]["physics_duration_s"],
        "task_phase_transitions": summary["task"]["phase_transitions"],
        "task_q_rmse_deg": (np.degrees(np.sqrt(np.mean(task_error**2, axis=0))).tolist()
                            if len(task_error) else None),
        "task_estimation_rmse_deg": (np.degrees(np.sqrt(np.mean(task_estimation**2, axis=0))).tolist()
                                     if len(task_estimation) else None),
        "commissioning_endpoint_q_error_deg": (
            np.degrees(q_true[commissioning_indices[-1]] - q_ref[commissioning_indices[-1]]).tolist()
            if len(commissioning_indices) else None),
        "commissioning_reference_min_shank_gap_m": finite_min(ref_commissioning_gaps),
        "commissioning_actual_boundary_min_shank_gap_m": finite_min(true_commissioning_gaps),
        "commissioning_first_negative_reference_time_s": (
            float(time[first_bad_idx]) if first_bad_idx is not None else None),
        "commissioning_first_negative_reference_tracking_error_deg": (
            np.degrees(q_true[first_bad_idx] - q_ref[first_bad_idx]).tolist()
            if first_bad_idx is not None else None),
        "thigh_contact": contact["contacts"]["thigh"],
        "shank_contact": contact["contacts"]["shank"],
        "physical_interval_count": contact["physical_interval_count"],
        "physical_interval_duration_s": contact["duration_s"],
        "physical_cuff_force_peak_n_all_trace": float(np.max(cuff_f)),
        "physical_cuff_moment_peak_nm_all_trace": float(np.max(cuff_m)),
        "physical_cuff_force_integral_n_s_all_trace": float(np.nansum(physical_cost)),
        "task_cuff_force_peak_n": summary["task"]["peak_force_n"],
        "task_cuff_moment_peak_nm": summary["task"]["peak_moment_nm"],
        "task_cuff_force_integral_n_s": summary["task"]["force_integral_n_s"],
        "minimum_deployable_shank_clearance_m_all_trace": finite_min(
            np.asarray(trace["session_shank_clearance_m"], dtype=float)),
        "minimum_true_shank_clearance_m_evaluation_only_task":
            summary["task"]["minimum_true_physical_clearance_m_evaluation_only"],
        "actual_acceleration_violation_boundary_count_all_trace": int(np.sum(
            np.asarray(trace["acceleration_limit_violation"], dtype=bool))),
        "rom_violation_physical_steps": summary["qualification"]["true_physics"]["rom_violation_steps"],
        "accepted_beta_update_count_task": summary["task"]["accepted_beta_update_count"],
        "residual_update_count_task": summary["task"]["residual_update_count"],
        "planner_call_count": int(len(planner)),
        "planner_mean_ms": float(np.mean(planner)) if len(planner) else None,
        "planner_p95_ms": float(np.percentile(planner, 95)) if len(planner) else None,
        "planner_max_ms": float(np.max(planner)) if len(planner) else None,
        "planner_over_100ms_count": int(np.sum(planner > 100.0)),
        "timing_aware_physics_during_planning": summary["timing"][
            "physics_advances_under_controlled_planning_delay_replay"],
    })
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)
    mapping = json.loads((ASSEMBLY / "OLD_TO_NEW_CASE_MAPPING.json").read_text())
    rows = [one_row(item, args.runs) for item in mapping]
    counts = Counter(row["new_status"] for row in rows)
    aborts = Counter(row.get("new_abort_reason", "") for row in rows
                     if row["new_status"] == "ABORTED")
    full = [row for row in rows if row["new_status"] in {"COMPLETE", "ABORTED"}]
    completed = [row for row in rows if row["new_status"] == "COMPLETE"]
    result = {
        "schema": "rigid_table_v1_old24_unchanged_controller_development_summary",
        "evidence_category": "consumed_old24_versioned_assembly_development_not_fresh_qualification",
        "historical_case_count": len(mapping),
        "screened_valid_case_count": sum(row["initial_endpoint_assembly_valid"] for row in rows),
        "physical_run_count": len(full),
        "commissioning_completed_count": sum(bool(row.get("commissioning_completed")) for row in full),
        "recovery_entered_count": sum(bool(row.get("recovery_entered")) for row in full),
        "recovery_succeeded_count": sum(bool(row.get("recovery_succeeded")) for row in full),
        "task_entered_count": sum(bool(row.get("task_entered")) for row in full),
        "complete_count": len(completed),
        "status_counts": dict(counts),
        "abort_reason_counts": dict(aborts),
        "thigh_contact_case_count": sum(row["thigh_contact"]["contact_duration_s"] > 0 for row in full),
        "worst_thigh_normal_peak_n": max((row["thigh_contact"]["normal_peak_n"] for row in full), default=None),
        "worst_shank_normal_peak_n": max((row["shank_contact"]["normal_peak_n"] for row in full), default=None),
        "planner_over_100ms_total": sum(row["planner_over_100ms_count"] for row in full),
        "worst_planner_ms": max((row["planner_max_ms"] or 0 for row in full), default=None),
        "rows": rows,
    }
    (args.output / "DEVELOPMENT_SUMMARY.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
