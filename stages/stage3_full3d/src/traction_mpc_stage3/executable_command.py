"""Single source of truth for Stage-3 low-level command realization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


EXECUTION_CONTROL_DT_S = 0.005


@dataclass(frozen=True)
class LowLevelCommandGains:
    position_n_per_m: float = 3000.0
    velocity_ns_per_m: float = 140.0
    orientation_nm_per_rad: float = 120.0
    angular_velocity_nms_per_rad: float = 12.0
    posture_nm_per_rad: float = 12.0
    posture_damping_nms_per_rad: float = 3.0
    cartesian_damping: float = 1.0e-4
    feedback_component_limit_n: float = 200.0
    translational_force_gate_n: float = 200.0
    force_gate_tolerance_n: float = 1.0e-9
    control_dt_s: float = EXECUTION_CONTROL_DT_S


DEFAULT_LOW_LEVEL_COMMAND_GAINS = LowLevelCommandGains()


@dataclass(frozen=True)
class ExecutableCommandPreview:
    """Exact command components and joint command for one 5 ms period."""

    force_position_n: np.ndarray
    force_velocity_n: np.ndarray
    force_allocator_n: np.ndarray
    force_total_n: np.ndarray
    raw_force_position_n: np.ndarray
    raw_force_velocity_n: np.ndarray
    feedback_force_before_clipping_n: np.ndarray
    feedback_force_after_clipping_n: np.ndarray
    feedback_force_clipping_delta_n: np.ndarray
    moment_orientation_nm: np.ndarray
    moment_angular_velocity_nm: np.ndarray
    moment_allocator_nm: np.ndarray
    moment_total_nm: np.ndarray
    translational_force_norm_n: float
    margin_to_force_gate_n: float
    feasible: bool
    robot_attachment_jacobian: np.ndarray
    unclipped_joint_torque_nm: np.ndarray
    joint_torque_command_nm: np.ndarray
    control_dt_s: float

    @property
    def wrench_total_world(self) -> np.ndarray:
        return np.concatenate([self.force_total_n, self.moment_total_nm])


@dataclass(frozen=True)
class ExecutableCommandBatchPreview:
    """Exact executable-command previews for one candidate batch."""

    force_position_n: np.ndarray
    force_velocity_n: np.ndarray
    force_allocator_n: np.ndarray
    force_total_n: np.ndarray
    raw_force_position_n: np.ndarray
    raw_force_velocity_n: np.ndarray
    feedback_force_before_clipping_n: np.ndarray
    feedback_force_after_clipping_n: np.ndarray
    feedback_force_clipping_delta_n: np.ndarray
    moment_orientation_nm: np.ndarray
    moment_angular_velocity_nm: np.ndarray
    moment_allocator_nm: np.ndarray
    moment_total_nm: np.ndarray
    translational_force_norm_n: np.ndarray
    margin_to_force_gate_n: np.ndarray
    feasible: np.ndarray
    robot_attachment_jacobian: np.ndarray
    unclipped_joint_torque_nm: np.ndarray
    joint_torque_command_nm: np.ndarray
    control_dt_s: float

    def __len__(self) -> int:
        return int(self.force_total_n.shape[0])

    def command(self, index: int) -> ExecutableCommandPreview:
        """Return one candidate using the scalar command data contract."""

        return ExecutableCommandPreview(
            force_position_n=self.force_position_n[index].copy(),
            force_velocity_n=self.force_velocity_n[index].copy(),
            force_allocator_n=self.force_allocator_n[index].copy(),
            force_total_n=self.force_total_n[index].copy(),
            raw_force_position_n=self.raw_force_position_n[index].copy(),
            raw_force_velocity_n=self.raw_force_velocity_n[index].copy(),
            feedback_force_before_clipping_n=(
                self.feedback_force_before_clipping_n[index].copy()
            ),
            feedback_force_after_clipping_n=(
                self.feedback_force_after_clipping_n[index].copy()
            ),
            feedback_force_clipping_delta_n=(
                self.feedback_force_clipping_delta_n[index].copy()
            ),
            moment_orientation_nm=self.moment_orientation_nm[index].copy(),
            moment_angular_velocity_nm=(
                self.moment_angular_velocity_nm[index].copy()
            ),
            moment_allocator_nm=self.moment_allocator_nm[index].copy(),
            moment_total_nm=self.moment_total_nm[index].copy(),
            translational_force_norm_n=float(
                self.translational_force_norm_n[index]
            ),
            margin_to_force_gate_n=float(self.margin_to_force_gate_n[index]),
            feasible=bool(self.feasible[index]),
            robot_attachment_jacobian=self.robot_attachment_jacobian.copy(),
            unclipped_joint_torque_nm=self.unclipped_joint_torque_nm[index].copy(),
            joint_torque_command_nm=self.joint_torque_command_nm[index].copy(),
            control_dt_s=self.control_dt_s,
        )


@dataclass(frozen=True)
class PreparedExecutableCommandContext:
    """Candidate-invariant realization terms for one control instant."""

    force_position_n: np.ndarray
    force_velocity_n: np.ndarray
    raw_force_position_n: np.ndarray
    raw_force_velocity_n: np.ndarray
    feedback_force_before_clipping_n: np.ndarray
    feedback_force_after_clipping_n: np.ndarray
    feedback_force_clipping_delta_n: np.ndarray
    moment_orientation_nm: np.ndarray
    moment_angular_velocity_nm: np.ndarray
    robot_attachment_jacobian: np.ndarray
    joint_torque_base_nm: np.ndarray
    torque_limits_nm: np.ndarray
    gains: LowLevelCommandGains


def _vector(name: str, value: np.ndarray, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {length}-vector")
    return result


def _matrix(name: str, value: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {shape[0]}x{shape[1]} matrix")
    return result


def _rotation_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
    from scipy.spatial.transform import Rotation

    target_rotation = _matrix("target_rotation_matrix", target, (3, 3))
    current_rotation = _matrix("attachment_rotation_matrix", current, (3, 3))
    return Rotation.from_matrix(target_rotation @ current_rotation.T).as_rotvec()


def prepare_executable_command_context(
    *,
    attachment_position_m: np.ndarray,
    attachment_rotation_matrix: np.ndarray,
    attachment_velocity_m_s: np.ndarray,
    attachment_angular_velocity_rad_s: np.ndarray,
    robot_q_rad: np.ndarray,
    robot_dq_rad_s: np.ndarray,
    neutral_robot_q_rad: np.ndarray,
    target_position_m: np.ndarray,
    target_velocity_m_s: np.ndarray,
    target_rotation_matrix: np.ndarray,
    target_angular_velocity_rad_s: np.ndarray,
    robot_attachment_jacobian: np.ndarray,
    bias_torque_nm: np.ndarray,
    torque_limits_nm: np.ndarray,
    gains: LowLevelCommandGains = DEFAULT_LOW_LEVEL_COMMAND_GAINS,
) -> PreparedExecutableCommandContext:
    """Precompute terms shared by candidate previews at one control instant."""

    position = _vector("attachment_position_m", attachment_position_m, 3)
    velocity = _vector("attachment_velocity_m_s", attachment_velocity_m_s, 3)
    angular_velocity = _vector(
        "attachment_angular_velocity_rad_s",
        attachment_angular_velocity_rad_s,
        3,
    )
    q = _vector("robot_q_rad", robot_q_rad, 6)
    dq = _vector("robot_dq_rad_s", robot_dq_rad_s, 6)
    neutral_q = _vector("neutral_robot_q_rad", neutral_robot_q_rad, 6)
    target_position = _vector("target_position_m", target_position_m, 3)
    target_velocity = _vector("target_velocity_m_s", target_velocity_m_s, 3)
    target_angular_velocity = _vector(
        "target_angular_velocity_rad_s", target_angular_velocity_rad_s, 3
    )
    jacobian = _matrix("robot_attachment_jacobian", robot_attachment_jacobian, (6, 6))
    bias = _vector("bias_torque_nm", bias_torque_nm, 6)
    torque_limits = _vector("torque_limits_nm", torque_limits_nm, 6)
    if np.any(torque_limits <= 0.0):
        raise ValueError("torque_limits_nm must be positive")
    if gains.control_dt_s != EXECUTION_CONTROL_DT_S:
        raise ValueError("Stage-3 executable command convention is fixed at 5 ms")

    raw_position_force = gains.position_n_per_m * (target_position - position)
    raw_velocity_force = gains.velocity_ns_per_m * (target_velocity - velocity)
    feedback_before_clipping = raw_position_force + raw_velocity_force
    feedback_after_clipping = np.clip(
        feedback_before_clipping,
        -gains.feedback_component_limit_n,
        gains.feedback_component_limit_n,
    )
    scale = np.ones(3)
    nonzero = np.abs(feedback_before_clipping) > 1.0e-15
    scale[nonzero] = (
        feedback_after_clipping[nonzero] / feedback_before_clipping[nonzero]
    )
    force_position = raw_position_force * scale
    force_velocity = feedback_after_clipping - force_position
    moment_orientation = gains.orientation_nm_per_rad * _rotation_error(
        target_rotation_matrix, attachment_rotation_matrix
    )
    moment_angular_velocity = gains.angular_velocity_nms_per_rad * (
        target_angular_velocity - angular_velocity
    )
    pinv = jacobian.T @ np.linalg.inv(
        jacobian @ jacobian.T + gains.cartesian_damping * np.eye(6)
    )
    nullspace = np.eye(6) - pinv @ jacobian
    posture = gains.posture_nm_per_rad * (neutral_q - q) - (
        gains.posture_damping_nms_per_rad * dq
    )
    return PreparedExecutableCommandContext(
        force_position_n=force_position.copy(),
        force_velocity_n=force_velocity.copy(),
        raw_force_position_n=raw_position_force.copy(),
        raw_force_velocity_n=raw_velocity_force.copy(),
        feedback_force_before_clipping_n=feedback_before_clipping.copy(),
        feedback_force_after_clipping_n=feedback_after_clipping.copy(),
        feedback_force_clipping_delta_n=(
            feedback_after_clipping - feedback_before_clipping
        ),
        moment_orientation_nm=moment_orientation.copy(),
        moment_angular_velocity_nm=moment_angular_velocity.copy(),
        robot_attachment_jacobian=jacobian.copy(),
        joint_torque_base_nm=(bias + nullspace.T @ posture),
        torque_limits_nm=torque_limits.copy(),
        gains=gains,
    )


def preview_executable_command(
    *,
    attachment_position_m: np.ndarray,
    attachment_rotation_matrix: np.ndarray,
    attachment_velocity_m_s: np.ndarray,
    attachment_angular_velocity_rad_s: np.ndarray,
    robot_q_rad: np.ndarray,
    robot_dq_rad_s: np.ndarray,
    neutral_robot_q_rad: np.ndarray,
    target_position_m: np.ndarray,
    target_velocity_m_s: np.ndarray,
    target_rotation_matrix: np.ndarray,
    target_angular_velocity_rad_s: np.ndarray,
    allocator_wrench_world: np.ndarray,
    robot_attachment_jacobian: np.ndarray,
    bias_torque_nm: np.ndarray,
    torque_limits_nm: np.ndarray,
    gains: LowLevelCommandGains = DEFAULT_LOW_LEVEL_COMMAND_GAINS,
    prepared_context: PreparedExecutableCommandContext | None = None,
) -> ExecutableCommandPreview:
    """Preview the exact low-level command without mutating plant state.

    The allocator wrench is the output of the caller's existing allocator.  A
    Stage-4 adapter owns the action-to-wrench call so preview and execution use
    the same allocator instance as well as this same realization function.
    """

    context = (
        prepare_executable_command_context(
            attachment_position_m=attachment_position_m,
            attachment_rotation_matrix=attachment_rotation_matrix,
            attachment_velocity_m_s=attachment_velocity_m_s,
            attachment_angular_velocity_rad_s=attachment_angular_velocity_rad_s,
            robot_q_rad=robot_q_rad,
            robot_dq_rad_s=robot_dq_rad_s,
            neutral_robot_q_rad=neutral_robot_q_rad,
            target_position_m=target_position_m,
            target_velocity_m_s=target_velocity_m_s,
            target_rotation_matrix=target_rotation_matrix,
            target_angular_velocity_rad_s=target_angular_velocity_rad_s,
            robot_attachment_jacobian=robot_attachment_jacobian,
            bias_torque_nm=bias_torque_nm,
            torque_limits_nm=torque_limits_nm,
            gains=gains,
        )
        if prepared_context is None
        else prepared_context
    )
    return preview_executable_command_from_context(
        context, allocator_wrench_world
    )


def preview_executable_command_from_context(
    context: PreparedExecutableCommandContext,
    allocator_wrench_world: np.ndarray,
) -> ExecutableCommandPreview:
    """Preview one command using an already prepared exact context."""

    allocator_wrench = _vector("allocator_wrench_world", allocator_wrench_world, 6)
    return preview_executable_commands_batch(
        context, allocator_wrench[np.newaxis, :]
    ).command(0)


def preview_executable_commands_batch(
    context: PreparedExecutableCommandContext,
    allocator_wrenches_world: np.ndarray,
) -> ExecutableCommandBatchPreview:
    """Preview a candidate batch under one exact Stage-3 command context."""

    allocator_wrenches = np.asarray(allocator_wrenches_world, dtype=float)
    if (
        allocator_wrenches.ndim != 2
        or allocator_wrenches.shape[1] != 6
        or not np.all(np.isfinite(allocator_wrenches))
    ):
        raise ValueError("allocator_wrenches_world must be a finite Nx6 matrix")
    count = allocator_wrenches.shape[0]
    repeated = (count, 3)
    force_position = np.broadcast_to(context.force_position_n, repeated).copy()
    force_velocity = np.broadcast_to(context.force_velocity_n, repeated).copy()
    force_allocator = allocator_wrenches[:, :3].copy()
    force_total = force_position + force_velocity + force_allocator
    moment_orientation = np.broadcast_to(
        context.moment_orientation_nm, repeated
    ).copy()
    moment_angular_velocity = np.broadcast_to(
        context.moment_angular_velocity_nm, repeated
    ).copy()
    moment_allocator = allocator_wrenches[:, 3:].copy()
    moment_total = moment_orientation + moment_angular_velocity + moment_allocator
    force_norm = np.linalg.norm(force_total, axis=1)
    margin = context.gains.translational_force_gate_n - force_norm
    feasible = force_norm <= (
        context.gains.translational_force_gate_n
        + context.gains.force_gate_tolerance_n
    )
    total_wrench = np.concatenate([force_total, moment_total], axis=1)
    unclipped_torque = (
        context.joint_torque_base_nm[np.newaxis, :]
        + total_wrench @ context.robot_attachment_jacobian
    )
    joint_torque = np.clip(
        unclipped_torque,
        -context.torque_limits_nm[np.newaxis, :],
        context.torque_limits_nm[np.newaxis, :],
    )
    return ExecutableCommandBatchPreview(
        force_position_n=force_position,
        force_velocity_n=force_velocity,
        force_allocator_n=force_allocator,
        force_total_n=force_total,
        raw_force_position_n=np.broadcast_to(
            context.raw_force_position_n, repeated
        ).copy(),
        raw_force_velocity_n=np.broadcast_to(
            context.raw_force_velocity_n, repeated
        ).copy(),
        feedback_force_before_clipping_n=np.broadcast_to(
            context.feedback_force_before_clipping_n, repeated
        ).copy(),
        feedback_force_after_clipping_n=np.broadcast_to(
            context.feedback_force_after_clipping_n, repeated
        ).copy(),
        feedback_force_clipping_delta_n=np.broadcast_to(
            context.feedback_force_clipping_delta_n, repeated
        ).copy(),
        moment_orientation_nm=moment_orientation,
        moment_angular_velocity_nm=moment_angular_velocity,
        moment_allocator_nm=moment_allocator,
        moment_total_nm=moment_total,
        translational_force_norm_n=force_norm,
        margin_to_force_gate_n=margin,
        feasible=feasible,
        robot_attachment_jacobian=context.robot_attachment_jacobian.copy(),
        unclipped_joint_torque_nm=unclipped_torque,
        joint_torque_command_nm=joint_torque,
        control_dt_s=context.gains.control_dt_s,
    )
