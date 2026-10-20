#!/usr/bin/env python3
"""Audit full-OUTBOUND Human-waypoint governor regressions without changing control."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_scheduler import _GovernedTargetScheduler
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _candidate,
    _jsonable,
    _prepare_runtime,
    _run_case,
)


SCHEMA = "stage5_waypoint_governor_regression_audit_v1"


def _percentiles(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {"minimum": None, "median": None, "p95": None, "maximum": None}
    return {
        "minimum": float(np.min(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "maximum": float(np.max(values)),
    }


def _event_record(event: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    limits = np.asarray(event["acceleration_limit_rad_s2"], dtype=float)
    realized_accel = np.asarray(
        row["deployable_20ms_acceleration_rad_s2"], dtype=float
    )
    accel_valid = bool(row["deployable_20ms_acceleration_valid"])
    accepted_q = np.asarray(event["accepted_q_reference_rad"], dtype=float)
    accepted_dq = np.asarray(event["accepted_dq_reference_rad_s"], dtype=float)
    estimated = np.asarray(row["estimated_state_rad_rad_s"], dtype=float)
    cuff_force = np.asarray(row["cuff_force_world_n"], dtype=float)
    cuff_moment = np.asarray(row["cuff_moment_world_nm"], dtype=float)
    proposed_request = np.asarray(
        event["proposed_acceleration_request_rad_s2"], dtype=float
    )
    accepted_request = np.asarray(
        event["accepted_acceleration_request_rad_s2"], dtype=float
    )
    return _jsonable(
        {
            "event_index": event["event_index"],
            "time_s": row["elapsed_s"],
            "event_type": (
                "ROLLBACK"
                if event["rollback"]
                else "HOLD"
                if event["held"]
                else "PARTIAL_ADVANCE"
                if event["blocked"]
                else "NOMINAL_ADVANCE"
            ),
            "q_hat_deg": np.degrees(event["current_q_hat_rad"]),
            "dq_hat_deg_s": np.degrees(event["current_dq_hat_rad_s"]),
            "progress_s": {
                "previous": event["previous_progress_s"],
                "nominal_next": event["nominal_next_progress_s"],
                "accepted": event["accepted_progress_s"],
            },
            "rollback_cause": {
                "criterion": event["criterion"],
                "proposed_violating_joints_one_based": [
                    int(index) + 1 for index in event["proposed_violating_joints"]
                ],
                "current_progress_feasible": event["current_progress_feasible"],
                "rejected_candidate_count": event["rejected_candidate_count"],
            },
            "requested": {
                "q_deg": np.degrees(accepted_q),
                "dq_deg_s": np.degrees(accepted_dq),
                "accepted_acceleration_proxy_deg_s2": np.degrees(accepted_request),
                "nominal_next_acceleration_proxy_deg_s2": np.degrees(
                    proposed_request
                ),
                "registered_limit_deg_s2": np.degrees(limits),
            },
            "realized": {
                "q_deg": np.degrees(estimated[:2]),
                "dq_deg_s": np.degrees(estimated[2:]),
                "acceleration_20ms_valid": accel_valid,
                "acceleration_20ms_deg_s2": (
                    np.degrees(realized_accel) if accel_valid else [None, None]
                ),
            },
            "tracking": {
                "human_q_reference_error_deg": np.degrees(
                    accepted_q - estimated[:2]
                ),
                "human_dq_reference_error_deg_s": np.degrees(
                    accepted_dq - estimated[2:]
                ),
                "cuff_position_error_mm": 1000.0 * row["cuff_position_error_m"],
                "cuff_orientation_error_deg": np.degrees(
                    row["cuff_orientation_error_rad"]
                ),
                "cuff_linear_twist_error_mm_s": (
                    1000.0 * row["cuff_linear_twist_error_m_s"]
                ),
                "cuff_angular_twist_error_deg_s": np.degrees(
                    row["cuff_angular_twist_error_rad_s"]
                ),
            },
            "interaction": {
                "cuff_force_world_n": cuff_force,
                "cuff_force_norm_n": np.linalg.norm(cuff_force),
                "cuff_moment_world_nm": cuff_moment,
                "cuff_moment_norm_nm": np.linalg.norm(cuff_moment),
                "maximum_robot_torque_fraction": row[
                    "maximum_robot_torque_fraction"
                ],
            },
            "geometry": {
                "shank_table_clearance_estimated_mm": (
                    1000.0 * row["shank_clearance_estimated_m"]
                ),
                "shank_table_clearance_truth_mm": (
                    1000.0 * row["shank_clearance_truth_m"]
                ),
                "shank_table_contact_truth": row["shank_bed_contact_truth"],
            },
        }
    )


def _tracking_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    return {
        "human_q_reference_error_norm_deg": _percentiles(
            np.asarray(
                [
                    np.linalg.norm(item["tracking"]["human_q_reference_error_deg"])
                    for item in records
                ]
            )
        ),
        "human_dq_reference_error_norm_deg_s": _percentiles(
            np.asarray(
                [
                    np.linalg.norm(
                        item["tracking"]["human_dq_reference_error_deg_s"]
                    )
                    for item in records
                ]
            )
        ),
        "cuff_position_error_mm": _percentiles(
            np.asarray(
                [item["tracking"]["cuff_position_error_mm"] for item in records]
            )
        ),
        "cuff_orientation_error_deg": _percentiles(
            np.asarray(
                [
                    item["tracking"]["cuff_orientation_error_deg"]
                    for item in records
                ]
            )
        ),
        "cuff_linear_twist_error_mm_s": _percentiles(
            np.asarray(
                [
                    item["tracking"]["cuff_linear_twist_error_mm_s"]
                    for item in records
                ]
            )
        ),
    }


def _plot(
    all_records: list[dict[str, Any]],
    blocked_records: list[dict[str, Any]],
    path: Path,
) -> None:
    time_s = np.asarray([item["time_s"] for item in all_records])
    previous = np.asarray(
        [item["progress_s"]["previous"] for item in all_records]
    )
    nominal = np.asarray(
        [item["progress_s"]["nominal_next"] for item in all_records]
    )
    accepted = np.asarray(
        [item["progress_s"]["accepted"] for item in all_records]
    )
    limits = np.asarray(
        [item["requested"]["registered_limit_deg_s2"] for item in all_records]
    )
    proxy = np.asarray(
        [
            item["requested"]["nominal_next_acceleration_proxy_deg_s2"]
            for item in all_records
        ]
    )
    realized = np.asarray(
        [
            [np.nan, np.nan]
            if not item["realized"]["acceleration_20ms_valid"]
            else item["realized"]["acceleration_20ms_deg_s2"]
            for item in all_records
        ],
        dtype=float,
    )
    proxy_utilization = np.max(np.abs(proxy) / limits, axis=1)
    realized_utilization = np.full(len(realized), np.nan)
    realized_valid = np.all(np.isfinite(realized), axis=1)
    realized_utilization[realized_valid] = np.max(
        np.abs(realized[realized_valid]) / limits[realized_valid], axis=1
    )

    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(time_s, nominal, "--", label="nominal next")
    axes[0].plot(time_s, previous, label="previous")
    axes[0].plot(time_s, accepted, label="accepted")
    if blocked_records:
        rollback = [item for item in blocked_records if item["event_type"] == "ROLLBACK"]
        axes[0].scatter(
            [item["time_s"] for item in rollback],
            [item["progress_s"]["accepted"] for item in rollback],
            s=14,
            color="tab:red",
            label="rollback",
            zorder=4,
        )
    axes[0].set_ylabel("path progress s [s]")
    axes[0].legend(ncol=4)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(time_s, proxy_utilization, label="nominal-next proxy / limit")
    axes[1].plot(time_s, realized_utilization, label="realized 20 ms / limit")
    axes[1].axhline(1.0, color="black", linestyle=":", label="registered limit")
    axes[1].set_ylabel("maximum joint utilization")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(
        time_s,
        [item["tracking"]["cuff_position_error_mm"] for item in all_records],
        label="cuff position error",
    )
    axes[2].plot(
        time_s,
        [item["geometry"]["shank_table_clearance_truth_mm"] for item in all_records],
        label="truth shank-table clearance",
    )
    axes[2].set_xlabel("OUTBOUND elapsed time [s]")
    axes[2].set_ylabel("distance [mm]")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_audit(output_dir: Path) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    runtime = _prepare_runtime("waypoint_governor_regression_audit", start)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec,
        runtime["human_model"],
        reference_period_s=CONTROL_DT_S,
    )
    governor = _GovernedTargetScheduler(
        scheduler,
        _candidate("registered_outbound", TaskPhase.OUTBOUND, goal, np.zeros(2)),
    )
    case = _run_case(
        name="registered_outbound_governor_audit",
        kind="shadow_governor_regression_audit",
        start_q_rad=start,
        duration_s=spec.phase_timeout_s + CONTROL_DT_S,
        stateful_schedule=governor,
    )
    if governor.session is None:
        raise RuntimeError("governor session was not created")
    events = governor.session.diagnostic_events
    trace = case["trace"]
    if len(events) != len(trace):
        raise RuntimeError(
            f"unaligned governor/plant histories: {len(events)} != {len(trace)}"
        )
    all_records = [_event_record(event, row) for event, row in zip(events, trace)]
    for event, row in zip(events, trace):
        if not np.isclose(
            event["phase_elapsed_s"], row["elapsed_s"], atol=1.0e-12, rtol=0.0
        ):
            raise RuntimeError("governor/plant timestamp mismatch")

    blocked = [item for item in all_records if item["event_type"] != "NOMINAL_ADVANCE"]
    rollbacks = [item for item in blocked if item["event_type"] == "ROLLBACK"]
    holds = [item for item in blocked if item["event_type"] == "HOLD"]
    partial = [item for item in blocked if item["event_type"] == "PARTIAL_ADVANCE"]
    nominal = [item for item in all_records if item["event_type"] == "NOMINAL_ADVANCE"]
    valid_rollbacks = [
        item for item in rollbacks if item["realized"]["acceleration_20ms_valid"]
    ]
    acceleration_limits_deg_s2 = np.degrees(
        np.asarray(spec.task_joint_acceleration_limit_rad_s2)
    )
    rollback_realized = np.asarray(
        [item["realized"]["acceleration_20ms_deg_s2"] for item in valid_rollbacks],
        dtype=float,
    )
    rollback_proxy = np.asarray(
        [
            item["requested"]["nominal_next_acceleration_proxy_deg_s2"]
            for item in rollbacks
        ],
        dtype=float,
    )
    violating_joint_counts = {
        "q1": int(
            sum(
                1
                for item in blocked
                if 1
                in item["rollback_cause"]["proposed_violating_joints_one_based"]
            )
        ),
        "q2": int(
            sum(
                1
                for item in blocked
                if 2
                in item["rollback_cause"]["proposed_violating_joints_one_based"]
            )
        ),
    }
    rollback_envelope_ok = (
        np.all(np.abs(rollback_realized) <= acceleration_limits_deg_s2, axis=1)
        if len(rollback_realized)
        else np.zeros(0, dtype=bool)
    )
    rollback_below_half = (
        np.all(
            np.abs(rollback_realized) <= 0.5 * acceleration_limits_deg_s2,
            axis=1,
        )
        if len(rollback_realized)
        else np.zeros(0, dtype=bool)
    )
    first_break = rollbacks[0] if rollbacks else None
    current_progress_infeasible = sum(
        not item["rollback_cause"]["current_progress_feasible"] for item in rollbacks
    )
    proxy_primary = bool(
        rollbacks
        and len(valid_rollbacks) == len(rollbacks)
        and np.all(rollback_envelope_ok)
        and violating_joint_counts["q1"] == len(blocked)
        and violating_joint_counts["q2"] == 0
        and current_progress_infeasible == len(rollbacks)
    )
    decision = (
        "WG-C — GOVERNOR FEASIBILITY PROXY IS OVERLY CONSERVATIVE"
        if proxy_primary
        else "WG-D — MULTIPLE CAUSES / EVIDENCE INSUFFICIENT"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "governor_progress_and_proxy.png"
    _plot(all_records, blocked, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "focused_shadow_engineering_diagnostic",
            "scope": {
                "robot": "official CR12 model with provisional Stage-5 cuff/interface",
                "task_segment": "registered full OUTBOUND",
                "control_period_s": CONTROL_DT_S,
                "controller_or_parameter_change": False,
            },
            "case_summary": {
                "termination_reason": case["termination_reason"],
                "executed_duration_s": case["executed_duration_s"],
                "schedule_duration_s": governor.session.schedule.duration_s,
                "final_progress_s": governor.session.progress_s,
                "final_progress_fraction": (
                    governor.session.progress_s / governor.session.schedule.duration_s
                ),
                "final_estimated_q_deg": case["final_estimated_q_deg"],
                "final_estimated_dq_deg_s": case["final_estimated_dq_deg_s"],
                "peak_abs_20ms_acceleration_deg_s2": case[
                    "human_motion_authority"
                ]["peak_abs_20ms_acceleration_deg_s2"],
                "peak_cuff_force_n": case["interaction"]["peak_cuff_force_n"],
                "peak_cuff_moment_nm": case["interaction"]["peak_cuff_moment_nm"],
                "human_motion_authority_violation_count": case[
                    "human_motion_authority"
                ]["violation_count"],
                "safety_filter_intervention_count": case["execution_safety"][
                    "safety_filter_intervention_count"
                ],
                "brake_cycle_count": case["execution_safety"][
                    "brake_cycle_count"
                ],
                "force_gate_event_count": case["execution_safety"][
                    "force_gate_event_count"
                ],
                "torque_clip_event_count": case["execution_safety"][
                    "torque_clip_event_count"
                ],
                "minimum_truth_shank_clearance_mm": case["execution_safety"][
                    "minimum_truth_shank_clearance_mm"
                ],
                "shank_bed_contact_sample_count": case["execution_safety"][
                    "shank_bed_contact_sample_count"
                ],
                "maximum_robot_torque_fraction": case["execution_safety"][
                    "maximum_robot_torque_fraction"
                ],
            },
            "progress_event_counts": {
                "total": len(all_records),
                "nominal_advance": len(nominal),
                "blocked_total": len(blocked),
                "partial_advance": len(partial),
                "hold": len(holds),
                "rollback": len(rollbacks),
            },
            "first_monotonic_progress_break": first_break,
            "rollback_semantics": {
                "rollback_count": len(rollbacks),
                "current_progress_already_proxy_infeasible_count": (
                    current_progress_infeasible
                ),
                "current_progress_already_proxy_infeasible_fraction": (
                    None
                    if not rollbacks
                    else current_progress_infeasible / len(rollbacks)
                ),
                "interpretation": (
                    "a freeze-only rule would still face the same instantaneous proxy rejection"
                    if rollbacks and current_progress_infeasible == len(rollbacks)
                    else "some rollback events could have held their previous progress under the proxy"
                ),
            },
            "acceleration_comparison": {
                "registered_limits_deg_s2": acceleration_limits_deg_s2,
                "blocked_nominal_next_violating_joint_counts": violating_joint_counts,
                "rollback_realized_valid_count": len(valid_rollbacks),
                "rollback_realized_within_registered_envelope_count": int(
                    np.count_nonzero(rollback_envelope_ok)
                ),
                "rollback_realized_within_registered_envelope_fraction": (
                    None
                    if not len(valid_rollbacks)
                    else float(np.mean(rollback_envelope_ok))
                ),
                "rollback_realized_below_half_limit_count_reporting_bin_only": int(
                    np.count_nonzero(rollback_below_half)
                ),
                "rollback_realized_below_half_limit_fraction_reporting_bin_only": (
                    None
                    if not len(valid_rollbacks)
                    else float(np.mean(rollback_below_half))
                ),
                "rollback_realized_abs_deg_s2": {
                    "q1": _percentiles(
                        np.abs(rollback_realized[:, 0])
                        if len(rollback_realized)
                        else np.asarray([])
                    ),
                    "q2": _percentiles(
                        np.abs(rollback_realized[:, 1])
                        if len(rollback_realized)
                        else np.asarray([])
                    ),
                },
                "rollback_nominal_next_proxy_abs_deg_s2": {
                    "q1": _percentiles(
                        np.abs(rollback_proxy[:, 0])
                        if len(rollback_proxy)
                        else np.asarray([])
                    ),
                    "q2": _percentiles(
                        np.abs(rollback_proxy[:, 1])
                        if len(rollback_proxy)
                        else np.asarray([])
                    ),
                },
                "half_limit_is_reporting_bin_not_new_threshold": True,
            },
            "tracking_comparison": {
                "nominal_advance": _tracking_stats(nominal),
                "all_blocked": _tracking_stats(blocked),
                "rollback": _tracking_stats(rollbacks),
            },
            "diagnosis": {
                "primary_mechanism": "instantaneous_pd_acceleration_request_proxy",
                "proxy_primary_evidence_rule_satisfied": proxy_primary,
                "decision": decision,
                "minimal_next_change": (
                    "replace the shared governor/contract instantaneous PD "
                    "acceleration-request feasibility proxy with one causal 20 ms "
                    "scheduled-reference motion-envelope check, while making insufficient "
                    "history hold progress"
                ),
            },
            "blocked_progress_events": blocked,
            "plot": str(plot_path),
            "scope_invariants": {
                "gains_changed": False,
                "timeout_changed": False,
                "acceleration_limits_changed": False,
                "task_changed": False,
                "controller_changed": False,
                "contact_model_changed": False,
                "rl_or_value_changed": False,
                "stage3_or_stage4_changed": False,
            },
        }
    )
    result_path = output_dir / "waypoint_governor_regression_audit.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "stages/stage5_personalized_motion_learning/results/engineering_validation/"
            "waypoint_governor_regression_audit_v1_attempt_01"
        ),
    )
    args = parser.parse_args()
    result = run_audit(args.output_dir)
    print(
        json.dumps(
            {
                "case_summary": result["case_summary"],
                "progress_event_counts": result["progress_event_counts"],
                "rollback_semantics": result["rollback_semantics"],
                "acceleration_comparison": result["acceleration_comparison"],
                "tracking_comparison": result["tracking_comparison"],
                "diagnosis": result["diagnosis"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
