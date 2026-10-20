#!/usr/bin/env python3
"""Run CR12 mechanical checks and a short unchanged-semantics Stage-5 smoke."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.cr12_validation import run_cr12_mechanical_validation
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN


def _plant_factory(parameters):
    return Stage5CR12SensorBoundaryPlant(
        STAGE5_HUMAN, interface_parameters=parameters
    )


def run_cr12_smoke(
    output_dir: Path,
    *,
    maximum_duration_s: float = 0.5,
    contract: str = "migration_v0",
    diagnostic_post_abort_continuation: bool = False,
) -> dict[str, object]:
    """Run one non-overwriting CR12 smoke under a named reporting contract."""

    if contract not in {"migration_v0", "provisional_cuff_baseline"}:
        raise ValueError("unsupported CR12 smoke contract")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite smoke output: {output_dir}")
    mechanical = run_cr12_mechanical_validation(output_dir / "mechanical")
    execution_started = perf_counter()
    smoke = run_goal_mpc_smoke(
        output_dir / "execution",
        maximum_duration_s=maximum_duration_s,
        plant_factory=_plant_factory,
        plant_case_name=(
            "cr12_provisional_cuff_baseline_smoke"
            if contract == "provisional_cuff_baseline"
            else "cr12_v0_robot_migration_smoke"
        ),
        diagnostic_post_abort_continuation=(
            diagnostic_post_abort_continuation
        ),
    )
    execution_wall_runtime_s = perf_counter() - execution_started
    trace = np.load(output_dir / "execution" / "trace.npz")
    critical_trace_fields = (
        "time_s",
        "estimated_state_rad_rad_s",
        "evaluation_human_q_rad",
        "evaluation_human_dq_rad_s",
        "deployable_realized_acceleration_rad_s2",
        "physical_cuff_force_world_n",
        "physical_cuff_moment_world_nm",
        "executed_generalized_action_nm",
        "executed_command_wrench_world",
        "deployable_robot_cuff_position_world_m",
        "deployable_robot_cuff_rotation_world",
        "deployable_robot_cuff_linear_velocity_world_m_s",
        "deployable_robot_cuff_angular_velocity_world_rad_s",
    )
    critical_trace_finite = {
        name: bool(np.all(np.isfinite(trace[name]))) for name in critical_trace_fields
    }
    shadow_fields = (
        "shadow_human_motion_acceleration_rad_s2",
        "shadow_human_motion_valid",
        "shadow_human_motion_history_coverage_s",
        "shadow_fast_motion_acceleration_rad_s2",
        "shadow_fast_motion_valid",
        "shadow_fast_alignment_interval_s",
        "shadow_cuff_wrench_world",
        "shadow_cuff_wrench_slew_world_per_s",
        "shadow_interface_translation_human_m",
        "shadow_interface_velocity_human_m_s",
        "shadow_command_wrench_world",
        "shadow_command_wrench_slew_world_per_s",
        "shadow_robot_joint_torque_command_nm",
        "shadow_robot_joint_torque_slew_nm_s",
        "shadow_robot_joint_torque_available",
        "shadow_robot_joint_torque_slew_valid",
    )
    shadow_fields_present = all(name in trace.files for name in shadow_fields)
    human_valid = np.asarray(trace["shadow_human_motion_valid"], dtype=bool)
    fast_valid = np.asarray(trace["shadow_fast_motion_valid"], dtype=bool)
    torque_slew_valid = np.asarray(
        trace["shadow_robot_joint_torque_slew_valid"], dtype=bool
    )
    shadow_validation = {
        "all_required_fields_present": shadow_fields_present,
        "shadow_only": smoke["split_acceleration_monitor_shadow"]["shadow_only"],
        "abort_authority": smoke["split_acceleration_monitor_shadow"][
            "abort_authority"
        ],
        "existing_monitor_remains_authoritative": smoke[
            "split_acceleration_monitor_shadow"
        ]["existing_model_based_monitor_remains_authoritative"],
        "human_motion_authority": smoke[
            "human_motion_acceleration_authority"
        ],
        "human_motion_valid_sample_count": int(np.count_nonzero(human_valid)),
        "human_motion_full_20ms_coverage": bool(
            np.allclose(
                trace["shadow_human_motion_history_coverage_s"][human_valid],
                0.020,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "human_motion_finite_when_valid": bool(
            np.all(
                np.isfinite(
                    trace["shadow_human_motion_acceleration_rad_s2"][human_valid]
                )
            )
        ),
        "fast_channel_valid_sample_count": int(np.count_nonzero(fast_valid)),
        "fast_channel_exactly_5ms_when_valid": bool(
            np.allclose(
                trace["shadow_fast_alignment_interval_s"][fast_valid],
                0.005,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "robot_joint_torque_available_all_samples": bool(
            np.all(trace["shadow_robot_joint_torque_available"])
        ),
        "robot_joint_torque_slew_finite_when_valid": bool(
            np.all(
                np.isfinite(
                    trace["shadow_robot_joint_torque_slew_nm_s"][torque_slew_valid]
                )
            )
        ),
    }
    response_artifact = json.loads(
        (output_dir / "execution" / "transition_response_shadow_v2.json").read_text(
            encoding="utf-8"
        )
    )
    response_validation = {
        "shadow_only": response_artifact["shadow_only"],
        "abort_authority": response_artifact["abort_authority"],
        "hard_threshold_active": response_artifact["hard_threshold_active"],
        "causal_append_only": response_artifact["causal_append_only"],
        "event_count": response_artifact["event_count"],
        "complete_window_count": response_artifact["complete_window_count"],
        "partial_window_count": response_artifact["partial_window_count"],
        "label_counts": response_artifact["label_counts"],
        "mpc_command_updates_recorded": bool(
            response_artifact["label_counts"].get("MPC_COMMAND_UPDATE", 0) > 0
        ),
        "terminal_task_transition_recorded": bool(
            response_artifact["label_counts"].get("TASK_PHASE_TRANSITION", 0) > 0
        ),
        "terminal_support_transition_recorded": bool(
            response_artifact["label_counts"].get(
                "SUPPORT_LOAD_STATE_TRANSITION", 0
            )
            > 0
        ),
    }
    mechanical_required = (
        "all_representative_poses_reachable",
        "all_representative_jacobians_full_rank",
        "no_active_robot_collision_contacts",
        "flange_to_cuff_transform_matches_stage5_geometry",
        "cuff_jacobian_matches_independent_cr12_offset",
        "cuff_jacobian_matches_finite_difference",
        "cuff_wrench_virtual_work_and_balance_finite",
        "execution_preview_finite_and_feasible",
    )
    mechanical_ready = all(
        bool(mechanical["mechanical_completeness"].get(name, False))
        for name in mechanical_required
    )
    torque_limits_nm = CR12TorqueRobot().torque_limits_nm
    torque_command = np.asarray(
        trace["shadow_robot_joint_torque_command_nm"], dtype=float
    )
    peak_abs_torque_nm = np.max(np.abs(torque_command), axis=0)
    torque_limit_status = {
        "official_limit_nm": torque_limits_nm.tolist(),
        "peak_abs_command_nm": peak_abs_torque_nm.tolist(),
        "peak_utilization": (peak_abs_torque_nm / torque_limits_nm).tolist(),
        "all_commands_within_limits": bool(
            np.all(peak_abs_torque_nm <= torque_limits_nm + 1.0e-9)
        ),
    }
    if contract == "provisional_cuff_baseline":
        if not mechanical_ready:
            classification = (
                "CR12-P-C — PROVISIONAL CUFF CANNOT BE CLEANLY REBOUND TO CR12"
            )
        elif smoke["task_status"] == "ABORTED":
            classification = (
                "CR12-P-B — INTEGRATION WORKS BUT BASELINE BLOCKED BY EXISTING "
                "MONITOR/EXECUTION ISSUE"
            )
        else:
            classification = "CR12-P-A — PROVISIONAL CUFF CR12 BASELINE READY"
        schema = "stage5_cr12_provisional_cuff_baseline_smoke_v1"
        filename = "cr12_provisional_cuff_baseline_summary.json"
    else:
        classification = mechanical["classification"]
        schema = "stage5_cr12_v0_smoke_summary"
        filename = "cr12_v0_smoke_summary.json"

    combined = {
        "schema": schema,
        "evidence_category": "smoke_engineering_validation_only",
        "contract": contract,
        "classification": classification,
        "model_scope": {
            "robot_geometry": "official ROKAE CR12",
            "end_effector_and_cuff_geometry": (
                "provisional Stage-5 surrogate; not hardware-faithful"
            ),
            "hex_h_qc_geometry_present": False,
        },
        "mechanical_ready": mechanical_ready,
        "mechanical_validation": mechanical["mechanical_completeness"],
        "provisional_cuff_rebind": mechanical["provisional_cuff_rebind"],
        "cuff_jacobian_consistency": mechanical["cuff_jacobian_consistency"],
        "cuff_wrench_validation": mechanical["cuff_wrench_validation"],
        "execution": {
            "task_duration_s": smoke["task_duration_s"],
            "task_status": smoke["task_status"],
            "phase_transitions": smoke["phase_transitions"],
            "phase_metrics": smoke["phase_metrics"],
            "abort_reason": smoke["abort_reason"],
            "mpc_solve_count": smoke["mpc_solve_count"],
            "mpc_status_counts": smoke["mpc_status_counts"],
            "mpc_failure_count": smoke["mpc_failure_count"],
            "force_gate_event_count": smoke["force_gate_event_count"],
            "human_motion_acceleration_event_count": smoke[
                "human_motion_acceleration_authority"
            ]["event_count"],
            "fast_transient_shadow": smoke[
                "split_acceleration_monitor_shadow"
            ]["fast_transient_channel"],
            "peak_physical_cuff_moment_nm": smoke[
                "peak_physical_cuff_moment_nm"
            ],
            "cumulative_physical_cuff_force_n_s": smoke[
                "cumulative_physical_cuff_force_n_s"
            ],
            "cr12_torque_limit_status": torque_limit_status,
            "runtime": {
                "simulation_task_duration_s": smoke["task_duration_s"],
                "execution_wall_runtime_s": execution_wall_runtime_s,
                "mpc_runtime_ms": smoke["mpc_runtime_ms"],
            },
            "brake_event_count": smoke["brake_event_count"],
            "peak_physical_cuff_force_n": smoke["peak_physical_cuff_force_n"],
            "registered_acceleration_limit_deg_s2": smoke[
                "acceleration_semantics"
            ]["registered_limit_deg_s2"],
            "peak_deployable_acceleration_deg_s2": smoke[
                "acceleration_semantics"
            ]["deployable_realized_acceleration"]["peak_abs_deg_s2"],
            "peak_human_motion_acceleration_deg_s2": smoke[
                "acceleration_semantics"
            ]["human_motion_acceleration_authority"][
                "peak_abs_deg_s2_on_valid_samples"
            ],
            "peak_evaluation_only_acceleration_deg_s2": smoke[
                "acceleration_semantics"
            ]["evaluation_only_truth_acceleration"]["peak_abs_deg_s2"],
            "mujoco_warning_counts": smoke["mujoco_warning_counts"],
            "critical_trace_finite": critical_trace_finite,
            "all_critical_trace_fields_finite": all(
                critical_trace_finite.values()
            ),
            "stopped_by_existing_acceleration_monitor": False,
            "stopped_by_existing_model_based_acceleration_monitor": False,
            "stopped_by_human_motion_acceleration_authority": bool(
                smoke["task_status"] == "ABORTED"
                and smoke["abort_reason"] == "TASK_ACCELERATION_LIMIT"
            ),
            "split_acceleration_monitor_shadow": shadow_validation,
            "transition_response_shadow_v2": response_validation,
        },
        "scientific_claim": False,
    }
    (output_dir / filename).write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return combined


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "cr12_migration_v0_smoke_20260918",
    )
    parser.add_argument(
        "--diagnostic-post-abort-continuation",
        action="store_true",
    )
    parser.add_argument("--maximum-duration-s", type=float, default=0.5)
    parser.add_argument(
        "--contract",
        choices=("migration_v0", "provisional_cuff_baseline"),
        default="migration_v0",
    )
    args = parser.parse_args()
    combined = run_cr12_smoke(
        args.output_dir,
        maximum_duration_s=args.maximum_duration_s,
        contract=args.contract,
        diagnostic_post_abort_continuation=(
            args.diagnostic_post_abort_continuation
        ),
    )
    print(json.dumps(combined, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
