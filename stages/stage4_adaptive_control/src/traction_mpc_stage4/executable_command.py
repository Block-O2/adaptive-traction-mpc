"""Stage-4 adapter for the shared Stage-3 executable-command contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.executable_command import (
    ExecutableCommandBatchPreview,
    ExecutableCommandPreview,
    PreparedExecutableCommandContext,
    prepare_executable_command_context,
    preview_executable_command,
    preview_executable_commands_batch,
)
from traction_mpc_stage3.reference import CuffPoseReference


@dataclass(frozen=True)
class Stage4ExecutableCommandPreview:
    allocation: dict[str, Any]
    command: ExecutableCommandPreview


def preview_stage4_executable_command(
    *,
    plant: Any,
    measurement: Any,
    action_nm: np.ndarray,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> Stage4ExecutableCommandPreview:
    """Allocate the action once, then preview the exact executable command."""

    state = np.asarray(estimated_state, dtype=float)
    if state.shape != (4,) or not np.all(np.isfinite(state)):
        raise ValueError("estimated_state must be a finite four-vector")
    allocation = cuff_allocator.allocate(action_nm, state[:2], human_model)
    target_pose = human_model.geometry.cuff_pose(reference.q_rad)
    target_linear_velocity, target_angular_velocity = (
        human_model.geometry.cuff_velocity(reference.q_rad, reference.dq_rad_s)
    )
    command = plant.preview_measured_executable_command(
        measurement,
        target_pose.translation,
        target_linear_velocity,
        target_pose.rotation,
        target_angular_velocity,
        np.asarray(allocation["wrench_world"]),
    )
    return Stage4ExecutableCommandPreview(allocation=allocation, command=command)


def prepare_stage4_executable_command_context(
    *,
    plant: Any,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    reference: CuffPoseReference,
) -> tuple[np.ndarray, PreparedExecutableCommandContext]:
    """Bind candidate-invariant terms for one Stage-4 control instant."""

    state = np.asarray(estimated_state, dtype=float)
    if state.shape != (4,) or not np.all(np.isfinite(state)):
        raise ValueError("estimated_state must be a finite four-vector")
    target_pose = human_model.geometry.cuff_pose(reference.q_rad)
    target_linear_velocity, target_angular_velocity = (
        human_model.geometry.cuff_velocity(reference.q_rad, reference.dq_rad_s)
    )
    control_velocity = plant.control_feedback_velocity_snapshot(measurement)
    measured_robot = plant._measured_robot_model
    measured_robot.set_configuration(
        measurement.robot_q_rad,
        measurement.robot_dq_rad_s,
    )
    cuff_jacobian = measured_robot.rigid_offset_jacobian(
        plant.attachment_from_cuff.translation
    )
    bias_torque = measured_robot.bias_torque_nm()
    context = prepare_executable_command_context(
        attachment_position_m=measurement.attachment_position_m,
        attachment_rotation_matrix=measurement.attachment_rotation_matrix,
        attachment_velocity_m_s=control_velocity.linear_velocity_world_m_s,
        attachment_angular_velocity_rad_s=(
            measurement.attachment_angular_velocity_rad_s
        ),
        robot_q_rad=measurement.robot_q_rad,
        robot_dq_rad_s=measurement.robot_dq_rad_s,
        neutral_robot_q_rad=plant.neutral_robot_q,
        target_position_m=target_pose.translation,
        target_velocity_m_s=target_linear_velocity,
        target_rotation_matrix=target_pose.rotation,
        target_angular_velocity_rad_s=target_angular_velocity,
        robot_attachment_jacobian=cuff_jacobian,
        bias_torque_nm=bias_torque,
        torque_limits_nm=plant.torque_limits_nm,
    )
    return state, context


def make_stage4_first_action_preview(
    *,
    plant: Any,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> Callable[[np.ndarray], ExecutableCommandPreview]:
    """Bind one control instant for scalar equivalence/reference checks."""

    state, context = prepare_stage4_executable_command_context(
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        reference=reference,
    )

    def preview(action_nm: np.ndarray) -> ExecutableCommandPreview:
        allocation = cuff_allocator.allocate(action_nm, state[:2], human_model)
        wrench = np.asarray(allocation["wrench_world"], dtype=float)
        return preview_executable_commands_batch(
            context, wrench[np.newaxis, :]
        ).command(0)

    return preview


def make_stage4_first_action_batch_preview(
    *,
    plant: Any,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> Callable[[np.ndarray], ExecutableCommandBatchPreview]:
    """Bind one control instant and batch all candidate-dependent work."""

    state, context = prepare_stage4_executable_command_context(
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        reference=reference,
    )

    def preview(actions_nm: np.ndarray) -> ExecutableCommandBatchPreview:
        actions = np.asarray(actions_nm, dtype=float)
        allocate_batch = getattr(cuff_allocator, "allocate_wrenches_batch", None)
        if allocate_batch is None:
            wrenches = np.vstack(
                [
                    np.asarray(
                        cuff_allocator.allocate(action, state[:2], human_model)[
                            "wrench_world"
                        ],
                        dtype=float,
                    )
                    for action in actions
                ]
            )
        else:
            wrenches = allocate_batch(actions, state[:2], human_model)
        return preview_executable_commands_batch(context, wrenches)

    return preview
