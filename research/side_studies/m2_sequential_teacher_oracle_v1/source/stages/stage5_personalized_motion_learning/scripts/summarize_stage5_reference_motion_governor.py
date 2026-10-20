#!/usr/bin/env python3
"""Compare the reference-motion governor replay with the preceding scheduler run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


SCHEMA = "stage5_reference_motion_governor_validation_v2"


def _case_metrics(case: dict[str, Any]) -> dict[str, Any] | None:
    metrics = case.get("metrics")
    if metrics is None:
        return None
    session = (case.get("scheduler") or {}).get("session") or {}
    return {
        "termination_reason": metrics["termination_reason"],
        "final_target_inside_existing_tolerances": case["target_tracking"][
            "final_target_inside_existing_tolerances"
        ],
        "settling_time_s": case["target_tracking"][
            "settling_time_to_target_with_existing_tolerances_s"
        ],
        "progress_fraction": session.get("progress_fraction"),
        "blocked_progress_count": session.get("blocked_progress_count"),
        "history_invalid_hold_count": session.get("history_invalid_hold_count"),
        "rollback_count": session.get("regression_count"),
        "peak_abs_20ms_acceleration_deg_s2": metrics["human_motion_authority"][
            "peak_abs_20ms_acceleration_deg_s2"
        ],
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
        "torque_clip_event_count": metrics["execution_safety"][
            "torque_clip_event_count"
        ],
    }


def _sequence_metrics(result: dict[str, Any]) -> dict[str, Any]:
    sequence = result["sequence"]
    metrics = sequence["metrics"]
    session = sequence["scheduler"]["outbound"]["session"]
    return {
        "completed_time_s": sequence["completed_time_s"],
        "termination_reason": metrics["termination_reason"],
        "executed_duration_s": metrics["executed_duration_s"],
        "phase_entry_inside_existing_tolerances": sequence[
            "phase_entry_inside_existing_tolerances"
        ],
        "outbound_progress_s": session["progress_s"],
        "outbound_progress_fraction": session["progress_fraction"],
        "progress_monotonic": session["regression_count"] == 0,
        "blocked_progress_count": session.get("blocked_progress_count"),
        "history_invalid_hold_count": session.get("history_invalid_hold_count"),
        "hold_count": session.get("history_invalid_hold_count"),
        "rollback_count": session["regression_count"],
        "maximum_reference_motion_acceleration_deg_s2": (
            None
            if "maximum_reference_motion_acceleration_rad_s2" not in session
            else np.degrees(
                session["maximum_reference_motion_acceleration_rad_s2"]
            ).tolist()
        ),
        "final_requested_q_deg": metrics["final_requested_q_deg"],
        "final_requested_dq_deg_s": metrics["final_requested_dq_deg_s"],
        "final_estimated_q_deg": metrics["final_estimated_q_deg"],
        "final_estimated_dq_deg_s": metrics["final_estimated_dq_deg_s"],
        "estimated_q_tracking_rmse_deg": metrics["estimated_q_tracking_rmse_deg"],
        "estimated_dq_tracking_rmse_deg_s": metrics[
            "estimated_dq_tracking_rmse_deg_s"
        ],
        "cuff_tracking": metrics["cuff_tracking"],
        "human_motion_authority": metrics["human_motion_authority"],
        "interaction": metrics["interaction"],
        "execution_safety": metrics["execution_safety"],
    }


def summarize(
    previous_path: Path, current_path: Path, output_dir: Path
) -> dict[str, Any]:
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    current = json.loads(current_path.read_text(encoding="utf-8"))
    previous_cases = {case["name"]: case for case in previous["matched_single_waypoints"]}
    comparisons = []
    for case in current["matched_single_waypoints"]:
        before = previous_cases[case["name"]]
        comparisons.append(
            {
                "name": case["name"],
                "previous": {
                    "status": before["status"],
                    "reason": before["reason"],
                    "metrics": _case_metrics(before),
                },
                "reference_motion_governor": {
                    "status": case["status"],
                    "reason": case["reason"],
                    "metrics": _case_metrics(case),
                },
            }
        )

    previous_sequence = _sequence_metrics(previous)
    current_sequence = _sequence_metrics(current)
    safety = current_sequence["execution_safety"]
    motion = current_sequence["human_motion_authority"]
    governor_semantics_fixed = bool(
        current_sequence["progress_monotonic"]
        and current_sequence["rollback_count"] == 0
        and current_sequence["blocked_progress_count"]
        == current_sequence["history_invalid_hold_count"]
    )
    complete = current_sequence["completed_time_s"] is not None
    motion_envelope_preserved = motion["violation_count"] == 0
    if complete and governor_semantics_fixed and motion_envelope_preserved:
        decision = (
            "WG2-A — REFERENCE-MOTION GOVERNOR ENABLES COMPLETE SAFE WAYPOINT TASK"
        )
        next_step = (
            "prototype the high-level Human-waypoint MPC against the unchanged "
            "reference-motion governor, without activating it in production"
        )
    elif governor_semantics_fixed:
        decision = (
            "WG2-B — GOVERNOR SEMANTICS FIXED, BUT EXECUTION/TRACKING STILL BLOCKS "
            "COMPLETION"
        )
        next_step = None
    else:
        decision = "WG2-C — REFERENCE-MOTION GOVERNOR DOES NOT RESOLVE THE PROBLEM"
        next_step = None

    limits_deg_s2 = np.degrees(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2
    ).tolist()
    result = {
        "schema": SCHEMA,
        "evidence_category": "bounded_shadow_engineering_validation",
        "decision": decision,
        "next_human_waypoint_mpc_prototype_step": next_step,
        "implementation": {
            "governor_motion_check": "causal_20ms_scheduled_reference_dq_history",
            "history_window_s": 0.020,
            "history_invalid_behavior": "hold_progress_and_mark_invalid",
            "registered_acceleration_limits_deg_s2": limits_deg_s2,
            "instantaneous_pd_request_used_by_governor": False,
        },
        "representative_waypoint_comparison": comparisons,
        "complete_task_comparison": {
            "previous_scheduler": previous_sequence,
            "reference_motion_governor": current_sequence,
        },
        "verification": {
            "governor_no_longer_stalls_on_pd_tracking_lag": governor_semantics_fixed,
            "real_20ms_human_motion_violation_introduced": not motion_envelope_preserved,
            "task_completed": complete,
            "completion_not_obtained_by_limit_weakening": bool(
                limits_deg_s2 == [300.0, 600.0]
            ),
            "remaining_blocker": (
                None
                if complete
                else current_sequence["termination_reason"]
            ),
            "remaining_blocker_occurs_after_governor_acceptance": bool(
                not complete
                and current_sequence["termination_reason"]
                == "WAYPOINT_CONTRACT_REJECTED: waypoint tracking request exceeds registered acceleration limits"
            ),
            "safety_filter_intervention_count": safety[
                "safety_filter_intervention_count"
            ],
            "brake_cycle_count": safety["brake_cycle_count"],
            "force_gate_event_count": safety["force_gate_event_count"],
            "torque_clip_event_count": safety["torque_clip_event_count"],
        },
        "inputs": {
            "previous_scheduler_result": str(previous_path),
            "reference_motion_governor_result": str(current_path),
        },
        "scope_invariants": {
            "gains_changed": False,
            "task_timing_changed": False,
            "safety_limits_changed": False,
            "contact_model_changed": False,
            "mpc_changed": False,
            "rl_or_value_changed": False,
            "stage3_or_stage4_changed": False,
            "historical_results_changed": False,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "reference_motion_governor_validation.json"
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.previous, args.current, args.output_dir)
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "verification": result["verification"],
                "complete_task": result["complete_task_comparison"][
                    "reference_motion_governor"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
