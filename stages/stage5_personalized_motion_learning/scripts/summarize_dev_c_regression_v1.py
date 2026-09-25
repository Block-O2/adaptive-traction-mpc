"""Augment the consumed-case DEV-A metrics with DEV-C transfer provenance."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np


def quantiles(values: list[float]) -> dict | None:
    if not values:
        return None
    a = np.asarray(values, dtype=float)
    return {"count": len(a), "mean": float(np.mean(a)),
            "median": float(np.median(a)), "p90": float(np.quantile(a, .90)),
            "p95": float(np.quantile(a, .95)), "p99": float(np.quantile(a, .99)),
            "max": float(np.max(a))}


def max_step(a: np.ndarray, eligible: np.ndarray) -> float | None:
    steps = np.linalg.norm(np.diff(a, axis=0), axis=1)
    selected = steps[eligible & np.isfinite(steps)]
    return None if len(selected) == 0 else float(np.max(selected))


def worst_step_detail(a: np.ndarray, eligible: np.ndarray, t: np.ndarray,
                      stage: np.ndarray, fraction: np.ndarray) -> dict | None:
    steps = np.linalg.norm(np.diff(a, axis=0), axis=1)
    valid = np.where(eligible & np.isfinite(steps))[0]
    if not len(valid):
        return None
    i = int(valid[np.argmax(steps[valid])])
    return {"before_time_s": float(t[i]), "after_time_s": float(t[i+1]),
            "before_stage": str(stage[i]), "after_stage": str(stage[i+1]),
            "before_fraction_new": None if not np.isfinite(fraction[i]) else float(fraction[i]),
            "after_fraction_new": None if not np.isfinite(fraction[i+1]) else float(fraction[i+1]),
            "before": np.asarray(a[i], dtype=float).tolist(),
            "after": np.asarray(a[i+1], dtype=float).tolist(),
            "delta_norm": float(steps[i])}


def event_metrics(case_dir: Path, summary: dict) -> dict:
    transfer = summary["dev_c_model_transfer"]
    events = transfer["events"]
    starts = [event for event in events if event["event"] == "START"]
    trace = np.load(case_dir / "trace.npz")
    t = np.asarray(trace["time_s"], dtype=float)
    dt = np.diff(t)
    adjacent = np.isclose(dt, .005, rtol=0, atol=2e-6)
    near_transfer = np.zeros(len(dt), dtype=bool)
    transfer_accel = np.zeros(len(t), dtype=bool)
    for event in starts:
        start, end = float(event["time_s"]), float(event["time_s"] + event["duration_s"])
        near_transfer |= (t[1:] >= start - 2e-6) & (t[1:] <= end + 2e-6)
        transfer_accel |= (t >= start - 2e-6) & (t <= end + 2e-6)
    # Abort/terminal nodes carry zero/non-executed commands for trace
    # alignment. They are not 5 ms actuator command transitions.
    terminal = np.asarray(trace["terminal_boundary_node"], dtype=bool)
    eligible = adjacent & near_transfer & ~terminal[1:] & ~terminal[:-1]
    wrench = np.asarray(trace["allocated_wrench_world"], dtype=float)
    accel = np.asarray(trace["actual_human_acceleration_rad_s2"], dtype=float)
    accel_valid = np.asarray(trace["actual_human_acceleration_valid"], dtype=bool)
    acceleration_values = accel[transfer_accel & accel_valid]
    modes = Counter(event["event"] for event in events)
    torque = np.asarray(trace["cr12_actuator_command_nm"], dtype=float)
    fraction = np.asarray(trace["model_transfer_fraction_new"], dtype=float)
    return {
        "transfer_start_count": len(starts),
        "transfer_complete_count": modes["COMPLETE"],
        "transfer_fully_realized_count": modes["FULLY_REALIZED"],
        "direct_small_change_count": modes["DIRECT_SMALL_CHANGE"],
        "queued_supersede_count": modes["QUEUED_SUPERSEDE"],
        "noop_update_count": modes["NO_EFFECT_UPDATE"],
        "transfer_duration_s": quantiles([float(event["duration_s"]) for event in starts]),
        "latest_accepted_version": transfer["latest_accepted_version"],
        "last_fully_realized_version": transfer["last_fully_realized_version"],
        "latest_version_realized_at_termination": (
            transfer["latest_accepted_version"] == transfer["last_fully_realized_version"]),
        "max_transfer_adjacent_human_action_step_nm": max_step(
            np.asarray(trace["applied_generalized_action_nm"], dtype=float), eligible),
        "max_transfer_adjacent_desired_force_step_n": max_step(wrench[:, :3], eligible),
        "max_transfer_adjacent_desired_moment_step_nm": max_step(wrench[:, 3:], eligible),
        "max_transfer_adjacent_cr12_torque_step_nm": max_step(
            torque, eligible),
        "worst_transfer_robot_step_detail": worst_step_detail(
            torque, eligible, t, trace["stage"], fraction),
        "max_transfer_human_acceleration_component_abs_rad_s2": (
            None if not len(acceleration_values) else float(np.max(np.abs(acceleration_values)))),
        "acceleration_violation_count_all_phases": int(np.sum(trace["acceleration_limit_violation"])),
        "transfer_adjacent_step_count": int(np.sum(eligible)),
        "task_peak_robot_torque_fraction": summary["task"]["peak_robot_torque_fraction"],
        "evaluation_only_rom_violation_steps": summary["qualification"]["true_physics"]["rom_violation_steps"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--base-summary", type=Path, required=True)
    parser.add_argument("--dev-a-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = json.loads(args.base_summary.read_text(encoding="utf-8"))
    old = json.loads(args.dev_a_summary.read_text(encoding="utf-8"))
    old_rows = {row["case_key"]: row for row in old["rows"]}
    rows = []
    for row in base["rows"]:
        key = row["case_key"]
        enriched = dict(row)
        old_row = old_rows.get(key)
        enriched["dev_a_status"] = None if old_row is None else old_row["status"]
        enriched["dev_a_abort_reason"] = None if old_row is None else old_row["abort_reason"]
        enriched["status_changed_from_dev_a"] = (
            old_row is not None and row["status"] != old_row["status"])
        summary_path = args.results / key / "summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            enriched.update(event_metrics(args.results / key, summary))
        rows.append(enriched)
    if len(rows) != 24 or {row["case_key"] for row in rows} != set(old_rows):
        raise ValueError("DEV-C and DEV-A regression case sets differ or are incomplete")
    result = {
        "schema": "full3d_dev_c_consumed_development_regression_v1",
        "evidence_category": "development_replay_of_consumed_formal_v1_cases",
        "case_count": len(rows),
        "dev_c_config_schema": "dev_c_bumpless_transfer_v2",
        "counts": {
            "initialized": base["initialization_succeeded_count"],
            "commissioning": base["commissioning_completed_count"],
            "recovery_succeeded": base["recovery_succeeded_count"],
            "task_entered": base["task_entered_count"],
            "full_task_complete": base["full_task_complete_count"],
            "dev_a_full_task_complete": old["full_task_complete_count"],
            "status_changed_vs_dev_a": sum(row["status_changed_from_dev_a"] for row in rows),
            "latest_accepted_not_realized_at_termination": sum(
                not row.get("latest_version_realized_at_termination", False) for row in rows
                if "latest_version_realized_at_termination" in row),
            "planner_deadline_misses": base["stale_planner_decision_count"],
            "acceleration_violations": sum(
                row.get("acceleration_violation_count_all_phases", 0) for row in rows),
            "evaluation_only_rom_violation_steps": sum(
                sum(value.values()) if isinstance(value, dict) else value
                for row in rows for value in [row.get("evaluation_only_rom_violation_steps", 0)]),
        },
        "abort_reason_counts": base["abort_reason_counts"],
        "transfer_event_counts": {
            field: sum(int(row.get(field, 0)) for row in rows)
            for field in ("transfer_start_count", "transfer_complete_count",
                          "transfer_fully_realized_count", "direct_small_change_count",
                          "queued_supersede_count", "noop_update_count")
        },
        "transfer_maxima": {
            field: max((row[field] for row in rows if row.get(field) is not None), default=None)
            for field in ("max_transfer_adjacent_human_action_step_nm",
                          "max_transfer_adjacent_desired_force_step_n",
                          "max_transfer_adjacent_desired_moment_step_nm",
                          "max_transfer_adjacent_cr12_torque_step_nm",
                          "max_transfer_human_acceleration_component_abs_rad_s2")
        },
        "planner_runtime_ms": base["planner_runtime_ms"],
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
