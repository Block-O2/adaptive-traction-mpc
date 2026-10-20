#!/usr/bin/env python3
"""Audit the waypoint-contract acceleration gate and summarize unified semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.human import (
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


SCHEMA = "stage5_waypoint_contract_acceleration_semantics_audit_v1"


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def _trace_semantics(case: dict[str, Any]) -> dict[str, Any]:
    trace = case["trace"]
    requested_q = np.asarray([row["requested_q_rad"] for row in trace])
    requested_dq = np.asarray([row["requested_dq_rad_s"] for row in trace])
    estimated = np.asarray([row["estimated_state_rad_rad_s"] for row in trace])
    pd_request = (
        np.asarray(TRACKING_KP_RAD_S2_PER_RAD) * (requested_q - estimated[:, :2])
        + np.asarray(TRACKING_KD_RAD_S2_PER_RAD_S)
        * (requested_dq - estimated[:, 2:])
    )
    scheduled = np.full_like(pd_request, np.nan)
    scheduled[4:] = (requested_dq[4:] - requested_dq[:-4]) / 0.020
    realized = np.asarray(
        [row["deployable_20ms_acceleration_rad_s2"] for row in trace], dtype=float
    )
    scheduled_valid = np.all(np.isfinite(scheduled), axis=1)
    realized_valid = np.asarray(
        [row["deployable_20ms_acceleration_valid"] for row in trace], dtype=bool
    )
    limits = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2
    )
    pd_violation = np.any(np.abs(pd_request) > limits + 1.0e-12, axis=1)
    scheduled_violation = np.zeros(len(trace), dtype=bool)
    scheduled_violation[scheduled_valid] = np.any(
        np.abs(scheduled[scheduled_valid]) > limits + 1.0e-12, axis=1
    )
    realized_violation = np.zeros(len(trace), dtype=bool)
    realized_violation[realized_valid] = np.any(
        np.abs(realized[realized_valid]) > limits + 1.0e-12, axis=1
    )
    matched_valid = scheduled_valid & realized_valid
    pd_only = (
        matched_valid & pd_violation & ~scheduled_violation & ~realized_violation
    )
    return _jsonable(
        {
            "sample_count": len(trace),
            "valid_20ms_comparison_count": int(np.count_nonzero(matched_valid)),
            "pd_request_limit_exceeded_count": int(np.count_nonzero(pd_violation)),
            "scheduled_20ms_limit_exceeded_count": int(
                np.count_nonzero(scheduled_violation)
            ),
            "realized_20ms_limit_exceeded_count": int(
                np.count_nonzero(realized_violation)
            ),
            "pd_only_rejection_count": int(np.count_nonzero(pd_only)),
            "peak_abs_pd_request_deg_s2": np.degrees(
                np.max(np.abs(pd_request), axis=0)
            ),
            "peak_abs_scheduled_20ms_deg_s2": (
                [None, None]
                if not np.any(scheduled_valid)
                else np.degrees(
                    np.max(np.abs(scheduled[scheduled_valid]), axis=0)
                )
            ),
            "peak_abs_realized_20ms_deg_s2": (
                [None, None]
                if not np.any(realized_valid)
                else np.degrees(np.max(np.abs(realized[realized_valid]), axis=0))
            ),
            "final_sample": {
                "time_s": trace[-1]["elapsed_s"],
                "pd_request_deg_s2": np.degrees(pd_request[-1]),
                "scheduled_20ms_deg_s2": (
                    [None, None]
                    if not scheduled_valid[-1]
                    else np.degrees(scheduled[-1])
                ),
                "realized_20ms_deg_s2": (
                    [None, None]
                    if not realized_valid[-1]
                    else np.degrees(realized[-1])
                ),
            },
        }
    )


def _case_summary(case: dict[str, Any]) -> dict[str, Any]:
    metrics = case.get("metrics")
    if metrics is None:
        return {
            "name": case["name"],
            "status": case["status"],
            "reason": case["reason"],
        }
    session = case["scheduler"]["session"]
    return {
        "name": case["name"],
        "status": case["status"],
        "termination_reason": metrics["termination_reason"],
        "completed_target": case["target_tracking"][
            "final_target_inside_existing_tolerances"
        ],
        "settling_time_s": case["target_tracking"][
            "settling_time_to_target_with_existing_tolerances_s"
        ],
        "blocked_count": session["blocked_progress_count"],
        "hold_count": session["history_invalid_hold_count"],
        "rollback_count": session["regression_count"],
        "contract_acceleration": metrics["waypoint_contract_acceleration"],
        "peak_realized_20ms_acceleration_deg_s2": metrics[
            "human_motion_authority"
        ]["peak_abs_20ms_acceleration_deg_s2"],
        "human_motion_violation_count": metrics["human_motion_authority"][
            "violation_count"
        ],
        "peak_cuff_force_n": metrics["interaction"]["peak_cuff_force_n"],
        "peak_cuff_moment_nm": metrics["interaction"]["peak_cuff_moment_nm"],
        "maximum_robot_torque_fraction": metrics["execution_safety"][
            "maximum_robot_torque_fraction"
        ],
        "minimum_truth_shank_clearance_mm": metrics["execution_safety"][
            "minimum_truth_shank_clearance_mm"
        ],
        "shank_bed_contact_sample_count": metrics["execution_safety"][
            "shank_bed_contact_sample_count"
        ],
        "safety_filter_intervention_count": metrics["execution_safety"][
            "safety_filter_intervention_count"
        ],
        "brake_cycle_count": metrics["execution_safety"]["brake_cycle_count"],
        "force_gate_event_count": metrics["execution_safety"][
            "force_gate_event_count"
        ],
    }


def run_audit(failed_path: Path, unified_path: Path, output_dir: Path) -> dict[str, Any]:
    failed = json.loads(failed_path.read_text(encoding="utf-8"))
    unified = json.loads(unified_path.read_text(encoding="utf-8"))
    failed_sequence = failed["sequence"]["metrics"]
    sequence = unified["sequence"]
    metrics = sequence["metrics"]
    outbound = sequence["scheduler"]["outbound"]["session"]
    return_session = sequence["scheduler"]["return"]["session"]
    completed = bool(
        sequence["completed_time_s"] is not None
        and metrics["termination_reason"] is None
        and all(sequence["phase_entry_inside_existing_tolerances"].values())
        and sequence["target_tracking"][
            "final_target_inside_existing_tolerances"
        ]
    )
    decision = (
        "WC-A — WAYPOINT CONTRACT SEMANTICS UNIFIED; FULL TASK COMPLETES"
        if completed
        else "WC-B — SEMANTICS UNIFIED, BUT ANOTHER EXECUTION LIMITATION REMAINS"
    )
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_shadow_engineering_validation",
            "decision": decision,
            "audit": {
                "quantity_previously_rejected": (
                    "instantaneous Human PD tracking acceleration request"
                ),
                "original_repository_role": (
                    "initial Human-motion envelope proxy applied before inverse dynamics"
                ),
                "classification": "legacy_duplicate_human_motion_envelope_check",
                "independent_actuator_authority_role": False,
                "independent_tracking_stability_role": False,
                "pd_request_retained_role": (
                    "unchanged inverse-dynamics execution input and diagnostic telemetry"
                ),
                "independent_execution_guards": [
                    "robot_joint_torque_limits",
                    "Safety_Filter",
                    "BRAKE",
                    "force_gate",
                ],
            },
            "failed_full_waypoint_semantics": {
                "termination_reason": failed_sequence["termination_reason"],
                "executed_duration_s": failed_sequence["executed_duration_s"],
                "comparison": _trace_semantics(failed_sequence),
            },
            "implementation": {
                "shared_contract": (
                    "CausalScheduledReferenceMotionHistory at 5 ms over 20 ms"
                ),
                "full_valid_history_required": True,
                "invalid_history_behavior": (
                    "execute only an explicitly unchanged held reference; reject progress"
                ),
                "registered_limits_deg_s2": np.degrees(
                    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2
                ),
                "pd_request_is_rejection_gate": False,
            },
            "representative_waypoints": [
                _case_summary(case) for case in unified["matched_single_waypoints"]
            ],
            "complete_task": {
                "completed": completed,
                "completion_time_s": sequence["completed_time_s"],
                "termination_reason": metrics["termination_reason"],
                "phase_entry_inside_existing_tolerances": sequence[
                    "phase_entry_inside_existing_tolerances"
                ],
                "blocked_count": (
                    outbound["blocked_progress_count"]
                    + return_session["blocked_progress_count"]
                ),
                "hold_count": (
                    outbound["history_invalid_hold_count"]
                    + return_session["history_invalid_hold_count"]
                ),
                "rollback_count": (
                    outbound["regression_count"] + return_session["regression_count"]
                ),
                "q_tracking_rmse_deg": metrics["estimated_q_tracking_rmse_deg"],
                "dq_tracking_rmse_deg_s": metrics[
                    "estimated_dq_tracking_rmse_deg_s"
                ],
                "final_q_deg": metrics["final_estimated_q_deg"],
                "final_dq_deg_s": metrics["final_estimated_dq_deg_s"],
                "contract_acceleration": metrics[
                    "waypoint_contract_acceleration"
                ],
                "peak_realized_20ms_acceleration_deg_s2": metrics[
                    "human_motion_authority"
                ]["peak_abs_20ms_acceleration_deg_s2"],
                "human_motion_violation_count": metrics[
                    "human_motion_authority"
                ]["violation_count"],
                "cuff_tracking": metrics["cuff_tracking"],
                "interaction": metrics["interaction"],
                "execution_safety": metrics["execution_safety"],
            },
            "scope_invariants": {
                "gains_changed": False,
                "task_timing_changed": False,
                "thresholds_changed": False,
                "contact_model_changed": False,
                "mpc_changed": False,
                "rl_or_value_changed": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
            },
            "inputs": {
                "failed_full_waypoint_result": str(failed_path),
                "unified_contract_result": str(unified_path),
            },
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "waypoint_contract_semantics_audit.json"
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed", type=Path, required=True)
    parser.add_argument("--unified", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.failed, args.unified, args.output_dir)
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "failed_full_waypoint_semantics": result[
                    "failed_full_waypoint_semantics"
                ],
                "complete_task": result["complete_task"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
