#!/usr/bin/env python3
"""Focused CR12 execution-chain audit without controller modifications."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    human_cuff_wrench_to_robot_cuff_command,
)


DURATION_S = 0.35
CONTROL_DT_S = 0.005


def _array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float).copy()


class AuditedCR12Plant(Stage5CR12SensorBoundaryPlant):
    """Append-only truth/control audit; records never feed back into control."""

    def __init__(self, human: Any, *, interface_parameters: Any) -> None:
        self.command_audit: list[dict[str, Any]] = []
        self.state_audit: list[dict[str, Any]] = []
        super().__init__(human, interface_parameters=interface_parameters)

    def _state_record(self, observation: Any) -> dict[str, Any]:
        return {
            "time_s": float(observation.time_s),
            "human_q_rad": _array(observation.human_q_rad),
            "human_dq_rad_s": _array(observation.human_dq_rad_s),
            "robot_q_rad": _array(observation.robot_q_rad),
            "robot_dq_rad_s": _array(observation.robot_dq_rad_s),
            "robot_cuff_position_world_m": _array(observation.attachment_position_m),
            "robot_cuff_rotation_world": _array(
                observation.attachment_rotation_matrix
            ),
            "robot_cuff_linear_velocity_world_m_s": _array(
                observation.attachment_velocity_m_s
            ),
            "robot_cuff_angular_velocity_world_rad_s": _array(
                observation.attachment_angular_velocity_rad_s
            ),
            "human_cuff_position_world_m": self.data.site_xpos[
                self.sleeve_site_id
            ].copy(),
            "physical_human_cuff_wrench_world": np.concatenate(
                [observation.cuff_force_vector_n, observation.cuff_moment_vector_nm]
            ),
            "human_generalized_input_nm": _array(
                observation.human_constraint_torque_nm
            ),
            "bed_force_n": float(observation.bed_force_n),
            "bed_contact_count": int(observation.bed_contact_count),
        }

    def observe(self):
        observation = super().observe()
        record = self._state_record(observation)
        if self.state_audit and math.isclose(
            self.state_audit[-1]["time_s"], record["time_s"], abs_tol=1.0e-12
        ):
            self.state_audit[-1] = record
        else:
            self.state_audit.append(record)
        return observation

    def apply_executable_command(self, preview: Any) -> None:
        observation = super().observe()
        jacobian = self.robot_attachment_jacobian()
        bias = self.data.qfrc_bias[self.robot_dof_indices].copy()
        wrench = _array(preview.wrench_total_world)
        jacobian_wrench_torque = jacobian.T @ wrench
        inferred_base_torque = (
            _array(preview.unclipped_joint_torque_nm) - jacobian_wrench_torque
        )
        record = {
            "time_s": float(self.data.time),
            "robot_q_rad": _array(observation.robot_q_rad),
            "robot_dq_rad_s": _array(observation.robot_dq_rad_s),
            "robot_attachment_jacobian": jacobian.copy(),
            "preview_robot_attachment_jacobian": _array(
                preview.robot_attachment_jacobian
            ),
            "robot_bias_torque_nm": bias,
            "inferred_joint_torque_base_nm": inferred_base_torque,
            "inferred_nullspace_posture_torque_nm": inferred_base_torque - bias,
            "jacobian_wrench_torque_nm": jacobian_wrench_torque,
            "force_position_n": _array(preview.force_position_n),
            "force_velocity_n": _array(preview.force_velocity_n),
            "force_allocator_n": _array(preview.force_allocator_n),
            "force_total_n": _array(preview.force_total_n),
            "raw_force_position_n": _array(preview.raw_force_position_n),
            "raw_force_velocity_n": _array(preview.raw_force_velocity_n),
            "feedback_force_before_clipping_n": _array(
                preview.feedback_force_before_clipping_n
            ),
            "feedback_force_after_clipping_n": _array(
                preview.feedback_force_after_clipping_n
            ),
            "moment_orientation_nm": _array(preview.moment_orientation_nm),
            "moment_angular_velocity_nm": _array(
                preview.moment_angular_velocity_nm
            ),
            "moment_allocator_nm": _array(preview.moment_allocator_nm),
            "moment_total_nm": _array(preview.moment_total_nm),
            "unclipped_joint_torque_nm": _array(
                preview.unclipped_joint_torque_nm
            ),
            "joint_torque_command_nm": _array(preview.joint_torque_command_nm),
            "torque_limits_nm": self.torque_limits_nm.copy(),
            "command_feasible": bool(preview.feasible),
            "control_dt_s": float(preview.control_dt_s),
        }
        super().apply_executable_command(preview)
        record["applied_ctrl_nm"] = self.data.ctrl[self.actuator_ids].copy()
        self.command_audit.append(record)


def _last_by_time(records: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    return {round(float(record["time_s"]), 12): record for record in records}


def _norm(value: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(value, dtype=float)))


def _command_row(
    command: dict[str, Any],
    state_now: dict[str, Any],
    state_next: dict[str, Any] | None,
) -> dict[str, Any]:
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    position_error = command["raw_force_position_n"] / gains.position_n_per_m
    velocity_error = command["raw_force_velocity_n"] / gains.velocity_ns_per_m
    orientation_error = command["moment_orientation_nm"] / gains.orientation_nm_per_rad
    angular_velocity_error = (
        command["moment_angular_velocity_nm"]
        / gains.angular_velocity_nms_per_rad
    )
    total_wrench = np.concatenate(
        [command["force_total_n"], command["moment_total_nm"]]
    )
    row = {
        "time_s": command["time_s"],
        "position_error_mm": 1000.0 * _norm(position_error),
        "linear_velocity_error_mm_s": 1000.0 * _norm(velocity_error),
        "orientation_error_deg": float(np.degrees(_norm(orientation_error))),
        "angular_velocity_error_deg_s": float(
            np.degrees(_norm(angular_velocity_error))
        ),
        "allocator_wrench_robot_site_world": np.concatenate(
            [command["force_allocator_n"], command["moment_allocator_nm"]]
        ).tolist(),
        "feedback_wrench_robot_site_world": np.concatenate(
            [
                command["force_position_n"] + command["force_velocity_n"],
                command["moment_orientation_nm"]
                + command["moment_angular_velocity_nm"],
            ]
        ).tolist(),
        "total_command_wrench_robot_site_world": total_wrench.tolist(),
        "joint_torque_command_nm": command["joint_torque_command_nm"].tolist(),
        "joint_torque_limit_fraction": (
            np.abs(command["joint_torque_command_nm"])
            / command["torque_limits_nm"]
        ).tolist(),
        "physical_human_cuff_wrench_world_at_command": state_now[
            "physical_human_cuff_wrench_world"
        ].tolist(),
        "human_q_deg_at_command": np.degrees(state_now["human_q_rad"]).tolist(),
        "human_dq_deg_s_at_command": np.degrees(
            state_now["human_dq_rad_s"]
        ).tolist(),
    }
    if state_next is not None:
        r_world = (
            state_next["robot_cuff_position_world_m"]
            - state_next["human_cuff_position_world_m"]
        )
        realized_robot_site = human_cuff_wrench_to_robot_cuff_command(
            state_next["physical_human_cuff_wrench_world"], r_world
        )
        row.update(
            {
                "response_time_s": state_next["time_s"],
                "realized_wrench_robot_site_world_after_5ms": (
                    realized_robot_site.tolist()
                ),
                "command_minus_realized_force_norm_n": _norm(
                    total_wrench[:3] - realized_robot_site[:3]
                ),
                "command_minus_realized_moment_norm_nm": _norm(
                    total_wrench[3:] - realized_robot_site[3:]
                ),
                "human_q_deg_after_5ms": np.degrees(
                    state_next["human_q_rad"]
                ).tolist(),
                "human_dq_deg_s_after_5ms": np.degrees(
                    state_next["human_dq_rad_s"]
                ).tolist(),
                "bed_force_n_after_5ms": state_next["bed_force_n"],
            }
        )
    return row


def _prediction_rows(trace: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    time = np.asarray(trace["time_s"], dtype=float)
    estimated_dq = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)[:, 2:]
    truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    prediction_time = np.asarray(
        trace["selected_v2_prefix_prediction_time_s"], dtype=float
    )
    predicted = np.asarray(
        trace["selected_v2_prefix_acceleration_rad_s2"], dtype=float
    )
    offsets = np.asarray([0.005, 0.010, 0.015, 0.020])
    rows = []
    for index, start in enumerate(prediction_time):
        start_index = int(np.argmin(np.abs(time - start)))
        realized = []
        truth = []
        for offset in offsets:
            end_index = int(np.argmin(np.abs(time - (start + offset))))
            realized.append((estimated_dq[end_index] - estimated_dq[start_index]) / offset)
            truth.append((truth_dq[end_index] - truth_dq[start_index]) / offset)
        realized_array = np.asarray(realized)
        truth_array = np.asarray(truth)
        rows.append(
            {
                "time_s": float(start),
                "prefix_times_s": offsets.tolist(),
                "predicted_acceleration_deg_s2": np.degrees(predicted[index]).tolist(),
                "deployable_realized_acceleration_deg_s2": np.degrees(
                    realized_array
                ).tolist(),
                "offline_truth_acceleration_deg_s2": np.degrees(
                    truth_array
                ).tolist(),
                "maximum_abs_prediction_minus_deployable_deg_s2": float(
                    np.max(np.abs(np.degrees(predicted[index] - realized_array)))
                ),
            }
        )
    return rows


def _audit_result(
    summary: dict[str, Any], trace: dict[str, np.ndarray], plant: AuditedCR12Plant
) -> dict[str, Any]:
    commands = _last_by_time(plant.command_audit)
    states = _last_by_time(plant.state_audit)
    command_rows = []
    for time, command in sorted(commands.items()):
        if time not in states:
            raise RuntimeError(f"missing state at command time {time}")
        next_state = states.get(round(time + CONTROL_DT_S, 12))
        command_rows.append(_command_row(command, states[time], next_state))

    independent = CR12TorqueRobot()
    jacobian_errors = []
    bias_errors = []
    torque_equation_errors = []
    applied_ctrl_errors = []
    clipping_counts = 0
    feedback_clipping_counts = 0
    control_periods = []
    ordered = [commands[key] for key in sorted(commands)]
    for previous, command in zip(ordered[:-1], ordered[1:], strict=True):
        control_periods.append(command["time_s"] - previous["time_s"])
    for command in ordered:
        independent.set_configuration(
            command["robot_q_rad"], command["robot_dq_rad_s"]
        )
        independent_jacobian = independent.rigid_offset_jacobian(
            plant.attachment_from_cuff.translation
        )
        independent_bias = independent.bias_torque_nm()
        jacobian_errors.append(
            np.max(
                np.abs(
                    command["robot_attachment_jacobian"]
                    - independent_jacobian
                )
            )
        )
        bias_errors.append(
            np.max(np.abs(command["robot_bias_torque_nm"] - independent_bias))
        )
        reconstructed = (
            command["inferred_joint_torque_base_nm"]
            + command["jacobian_wrench_torque_nm"]
        )
        torque_equation_errors.append(
            np.max(np.abs(reconstructed - command["unclipped_joint_torque_nm"]))
        )
        applied_ctrl_errors.append(
            np.max(
                np.abs(
                    command["applied_ctrl_nm"]
                    - command["joint_torque_command_nm"]
                )
            )
        )
        clipping_counts += int(
            not np.array_equal(
                command["joint_torque_command_nm"],
                command["unclipped_joint_torque_nm"],
            )
        )
        feedback_clipping_counts += int(
            not np.allclose(
                command["feedback_force_before_clipping_n"],
                command["feedback_force_after_clipping_n"],
                atol=0.0,
                rtol=0.0,
            )
        )

    trace_time = np.asarray(trace["time_s"], dtype=float)
    selected_time = np.asarray(
        trace["selected_v2_prefix_prediction_time_s"], dtype=float
    )
    selected_increment = np.asarray(
        trace["selected_v2_prefix_executable_wrench_increment_world"], dtype=float
    )
    selected_wrench = np.asarray(
        [
            trace["prediction_previous_executable_wrench_world"][
                int(np.argmin(np.abs(trace_time - time)))
            ]
            + increment
            for time, increment in zip(
                selected_time, selected_increment, strict=True
            )
        ],
        dtype=float,
    )
    actual_selected_wrench = np.asarray(
        [
            np.concatenate(
                [
                    commands[round(float(time), 12)]["force_total_n"],
                    commands[round(float(time), 12)]["moment_total_nm"],
                ]
            )
            for time in selected_time
        ]
    )
    torque_fraction = np.asarray(
        [
            np.abs(command["joint_torque_command_nm"])
            / command["torque_limits_nm"]
            for command in ordered
        ]
    )
    prediction_rows = _prediction_rows(trace)
    selected_samples = [
        row
        for row in command_rows
        if any(
            math.isclose(row["time_s"], target, abs_tol=1.0e-12)
            for target in (0.0, 0.005, 0.02, 0.04, 0.06, 0.1, 0.2, 0.28, 0.3, 0.305, 0.31, 0.315)
        )
    ]
    return {
        "schema": "stage5_cr12_execution_control_audit_v1",
        "evidence_category": "focused_engineering_diagnostic",
        "decision": "EX-C — EXECUTION/PREVIEW SEMANTIC MISMATCH REMAINS",
        "primary_mismatch": (
            "the selected first 5 ms executable command is shared exactly, but "
            "the remaining 20 ms screening recurrence does not propagate the "
            "CR12 joint state or realized cuff pose/twist response"
        ),
        "result": {
            "task_status": summary["task_status"],
            "abort_reason": summary["abort_reason"],
            "last_time_s": float(trace_time[-1]),
        },
        "execution_contract": {
            "pose_twist_are_feedback_targets": True,
            "allocated_cuff_wrench_is_feedforward": True,
            "robot_bias_torque_is_robot_gravity_coriolis_compensation": True,
            "human_support_action_is_separate_human_inverse_dynamics": True,
            "command_equation": "tau=clip(bias+N.T*tau_posture+J_cuff.T*(w_allocator+w_pose_twist_feedback))",
            "command_wrench_reference_point": "robot_adapter_cuff_site",
            "physical_wrench_reference_point": "human_sleeve_attach_site",
            "physical_wrench_transformed_before_comparison": True,
        },
        "implementation_checks": {
            "maximum_full_plant_vs_preview_jacobian_abs_error": float(
                max(jacobian_errors)
            ),
            "maximum_full_plant_vs_independent_bias_abs_error_nm": float(
                max(bias_errors)
            ),
            "maximum_joint_torque_equation_abs_error_nm": float(
                max(torque_equation_errors)
            ),
            "maximum_applied_ctrl_abs_error_nm": float(max(applied_ctrl_errors)),
            "joint_torque_clipping_cycle_count": clipping_counts,
            "feedback_force_clipping_cycle_count": feedback_clipping_counts,
            "maximum_joint_torque_limit_fraction": float(np.max(torque_fraction)),
            "control_period_min_s": float(min(control_periods)),
            "control_period_max_s": float(max(control_periods)),
            "measurement_age_min_s": float(
                np.min(np.asarray(trace["task_observation_age_s"], dtype=float))
            ),
            "measurement_age_max_s": float(
                np.max(np.asarray(trace["task_observation_age_s"], dtype=float))
            ),
            "maximum_selected_first_wrench_vs_executed_abs_error": float(
                np.max(np.abs(selected_wrench - actual_selected_wrench))
            ),
        },
        "screening_semantics": {
            "first_5ms_executable_command_uses_same_preview_as_execution": True,
            "first_selected_wrench_matches_execution": bool(
                np.allclose(selected_wrench, actual_selected_wrench, atol=1.0e-12)
            ),
            "later_prefix_propagates_cr12_joint_state": False,
            "later_prefix_propagates_cr12_cuff_pose_twist_tracking": False,
            "later_prefix_treats_executable_wrench_as_nominal_interface_drive": True,
            "semantic_match_over_full_20ms": False,
        },
        "prediction_vs_realization": prediction_rows,
        "selected_execution_samples": selected_samples,
        "safety": {
            "safety_filter_status_counts": summary["safety_filter_status_counts"],
            "brake_event_count": summary["brake_event_count"],
            "force_gate_event_count": summary["force_gate_event_count"],
            "human_motion_event_count": summary[
                "human_motion_acceleration_authority"
            ]["event_count"],
        },
        "scientific_changes": {
            "production_execution_code_changed": False,
            "controller_parameter_changed": False,
            "mpc_objective_changed": False,
            "task_changed": False,
            "human_model_changed": False,
            "safety_limit_changed": False,
            "cuff_geometry_changed": False,
            "contact_model_changed": False,
            "rl_or_value_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_execution_control_audit_attempt_01",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    holder: dict[str, AuditedCR12Plant] = {}

    def factory(parameters: Any) -> AuditedCR12Plant:
        plant = AuditedCR12Plant(STAGE5_HUMAN, interface_parameters=parameters)
        holder["plant"] = plant
        return plant

    summary = run_goal_mpc_smoke(
        output / "rollout",
        maximum_duration_s=DURATION_S,
        plant_factory=factory,
        plant_case_name="cr12_execution_control_audit",
    )
    trace_file = output / "rollout" / "trace.npz"
    with np.load(trace_file) as stored:
        trace = {name: stored[name].copy() for name in stored.files}
    result = _audit_result(summary, trace, holder["plant"])
    result_file = output / "execution_control_audit.json"
    result_file.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
