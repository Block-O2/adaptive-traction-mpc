"""Evaluation-only DEV-D aggregation; no result exclusions or control inputs."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from diagnose_rigid_table_reference_v1 import gaps
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


def finite_percentiles(values: list[float]) -> dict[str, float | int | None]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return {"count": 0, "mean": None, "median": None, "p90": None,
                "p95": None, "p99": None, "maximum": None}
    return {"count": int(len(x)), "median": float(np.median(x)),
            "mean": float(np.mean(x)), "p90": float(np.percentile(x, 90)),
            "p95": float(np.percentile(x, 95)),
            "p99": float(np.percentile(x, 99)), "maximum": float(np.max(x))}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    batch = json.loads((args.batch / "batch_status.json").read_text())
    rows = []
    task_planner_ms: list[float] = []
    commissioning_plan_ms: list[float] = []
    for listed in batch["rows"]:
        key = listed["case_key"]
        run = args.batch / key
        manifest = json.loads((run / "dev_d_run_manifest.json").read_text())
        contact = json.loads((run / "contact_summary.json").read_text())
        summary_path = run / "summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
        row = {"case_key": key, "status": listed["status"],
               "abort_reason": listed["abort_reason"],
               "case_sha256": manifest["case_sha256"],
               "initial_assembly_valid": manifest["assembly_screen"]["valid"],
               "physical_interval_count": contact["physical_interval_count"],
               "thigh_contact_peak_n": contact["contacts"]["thigh"]["normal_peak_n"],
               "shank_contact_peak_n": contact["contacts"]["shank"]["normal_peak_n"],
               "commissioning_completed": summary is not None,
               "geometry_fit_accepted": None,
               "task_entered": False,
               "task_complete": listed["status"] == "COMPLETE",
               "true_geometry_margins_evaluation_only": None}
        if summary is not None:
            commissioning = summary["commissioning"]
            fit = commissioning["geometry_fit"]
            events = commissioning.get("dev_d_reference_events", [])
            plan_ms = [float(event["runtime_ms"]) for event in events]
            commissioning_plan_ms.extend(plan_ms)
            decisions = summary.get("decisions", [])
            this_planner = [float(d["planning_runtime_ms_measured"]) for d in decisions]
            task_planner_ms.extend(this_planner)
            row.update({
                "geometry_fit_accepted": bool(fit["accepted"]),
                "geometry_fit_sample_count": int(fit["sample_count"]),
                "geometry_fit_angular_span_rad": float(fit["angular_span_rad"]),
                "geometry_fit_condition_number": float(fit["condition_number"]),
                "commissioning_reference_plan_count": len(events),
                "commissioning_reference_plan_max_ms": max(plan_ms, default=None),
                "commissioning_reference_deadline_misses": sum(
                    bool(event.get("deadline_miss")) for event in events),
                "conservative_nonworsening_shank_escape_count": sum(
                    bool(event.get("conservative_nonworsening_shank_escape")) for event in events),
                "recovery_entered": bool(summary["dev_a_recovery"]["entered"]),
                "recovery_succeeded": bool(summary["dev_a_recovery"]["succeeded"]),
                "task_entered": summary["task"]["integration_interval_count"] > 0,
                "task_interval_count": int(summary["task"]["integration_interval_count"]),
                "task_planning_count": len(decisions),
                "task_planner_max_ms": max(this_planner, default=None),
                "task_plan_deadline_misses": sum(
                    d.get("activation_rejected_reason") == "STALE_PLAN_MAXIMUM_AGE"
                    for d in decisions),
                "task_beta_accepts": int(summary["task"]["accepted_beta_update_count"]),
                "task_residual_updates": int(summary["task"]["residual_update_count"]),
                "task_peak_cuff_force_n": float(summary["task"]["peak_force_n"]),
                "task_peak_cuff_moment_nm": float(summary["task"]["peak_moment_nm"]),
                "task_force_integral_n_s": float(summary["task"]["force_integral_n_s"]),
                "minimum_deployable_clearance_m": float(
                    summary["task"]["minimum_session_clearance_m_deployable"]),
            })
            with np.load(run / "trace.npz", allow_pickle=True) as trace:
                tmask = trace["stage"] == "TASK"
                qref = np.asarray(trace["reference_q_rad"], dtype=float)
                qtrue = np.asarray(trace["evaluation_only_human_state_rad_rad_s"], dtype=float)[:, :2]
                qhat = np.asarray(trace["estimated_human_state_rad_rad_s"], dtype=float)[:, :2]
                if np.any(tmask):
                    row["task_tracking_rmse_deg"] = (
                        np.sqrt(np.mean((qtrue[tmask] - qref[tmask]) ** 2, axis=0))
                        * 180 / np.pi).tolist()
                row["commissioning_observed_q_span_deg_evaluation_only"] = (
                    np.ptp(qtrue[trace["stage"] == "COMMISSIONING"], axis=0)
                    * 180 / np.pi).tolist()
                row["minimum_measured_sleeve_gap_m"] = float(np.nanmin(
                    trace["dev_d_measured_sleeve_gap_m"]))
                row["minimum_deployable_envelope_clearance_m"] = float(np.nanmin(
                    trace["dev_d_session_envelope_clearance_m"]))
                force = np.asarray(trace["physical_cuff_force_world_n"], dtype=float)
                moment = np.asarray(trace["physical_cuff_moment_world_nm"], dtype=float)
                row["full_session_peak_cuff_force_n"] = float(np.max(np.linalg.norm(force, axis=1)))
                row["full_session_peak_cuff_moment_nm"] = float(np.max(np.linalg.norm(moment, axis=1)))
                row["full_session_cuff_force_integral_n_s"] = float(np.sum(
                    np.asarray(trace["interval_force_cost_n_s"], dtype=float)))
                actual_accel = np.asarray(trace["actual_human_acceleration_rad_s2"], dtype=float)
                actual_accel_valid = np.asarray(trace["actual_human_acceleration_valid"], dtype=bool)
                row["full_session_max_actual_human_acceleration_rad_s2"] = (
                    np.max(np.abs(actual_accel[actual_accel_valid]), axis=0).tolist()
                    if np.any(actual_accel_valid) else None)
                row["actual_acceleration_violation_count"] = int(np.sum(
                    np.asarray(trace["acceleration_limit_violation"], dtype=bool)))
                case = json.loads(Path(manifest["case_path"]).read_text())
                human, geometry, _, _ = hidden_plant(case)
                requested = gaps(qref, human, geometry)
                actual = gaps(qtrue, human, geometry)
                row["true_geometry_margins_evaluation_only"] = {
                    "requested_min_m": {name: float(np.min(x)) for name, x in requested.items()},
                    "actual_min_m": {name: float(np.min(x)) for name, x in actual.items()},
                    "requested_first_negative_s": {
                        name: (float(trace["time_s"][np.flatnonzero(x < -1e-9)[0]])
                               if np.any(x < -1e-9) else None)
                        for name, x in requested.items()},
                    "actual_first_negative_s": {
                        name: (float(trace["time_s"][np.flatnonzero(x < -1e-9)[0]])
                               if np.any(x < -1e-9) else None)
                        for name, x in actual.items()},
                }
                row["task_estimation_rmse_deg_evaluation_only"] = (
                    np.sqrt(np.mean((qhat[tmask] - qtrue[tmask]) ** 2, axis=0))
                    * 180 / np.pi).tolist() if np.any(tmask) else None
        else:
            abort_path = run / "dev_d_reference_abort.json"
            if abort_path.exists():
                abort = json.loads(abort_path.read_text())
                row["abort_time_s"] = float(abort["time_s"])
                row["minimum_measured_sleeve_gap_m"] = abort.get("measured_sleeve_gap_m")
                row["commissioning_reference_plan_count"] = len(abort["reference_events"])
                row["commissioning_reference_plan_max_ms"] = max(
                    [float(e["runtime_ms"]) for e in abort["reference_events"]], default=None)
        rows.append(row)
    counts = Counter(row["status"] for row in rows)
    reasons = Counter((row["abort_reason"] or "COMPLETE").split(":")[0] for row in rows)
    report = {
        "schema": "dev_d_consumed_development_aggregate_v1",
        "evidence_category": "DEVELOPMENT_CONSUMED_NOT_FRESH",
        "batch_dir": str(args.batch),
        "selected_count": len(batch["selected_case_keys"]),
        "completed_artifact_count": len(rows),
        "status_counts": counts,
        "reason_counts": reasons,
        "commissioning_completed_count": sum(r["commissioning_completed"] for r in rows),
        "geometry_fit_accepted_count": sum(r["geometry_fit_accepted"] is True for r in rows),
        "recovery_succeeded_count": sum(r.get("recovery_succeeded", False) for r in rows),
        "task_entered_count": sum(r["task_entered"] for r in rows),
        "complete_count": sum(r["task_complete"] for r in rows),
        "thigh_contact_case_count": sum(r["thigh_contact_peak_n"] > 0 for r in rows),
        "shank_contact_case_count": sum(r["shank_contact_peak_n"] > 0 for r in rows),
        "measured_sleeve_penetration_case_count": sum(
            r.get("minimum_measured_sleeve_gap_m") is not None and
            r["minimum_measured_sleeve_gap_m"] < -1e-9 for r in rows),
        "task_planner_ms": finite_percentiles(task_planner_ms),
        "commissioning_planner_ms": finite_percentiles(commissioning_plan_ms),
        "task_deadline_miss_count": sum(r.get("task_plan_deadline_misses", 0) for r in rows),
        "actual_acceleration_violation_count": sum(
            r.get("actual_acceleration_violation_count", 0) for r in rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in (
        "selected_count", "status_counts", "reason_counts", "commissioning_completed_count",
        "geometry_fit_accepted_count", "recovery_succeeded_count", "task_entered_count",
        "complete_count", "task_planner_ms", "task_deadline_miss_count")}, indent=2))


if __name__ == "__main__":
    main()
