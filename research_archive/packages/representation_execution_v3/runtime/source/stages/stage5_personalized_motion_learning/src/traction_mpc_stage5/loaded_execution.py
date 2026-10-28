"""Single Stage-5 authority for loaded cuff command realization.

The Human allocator defines a wrench about the Human cuff site.  The robot
command acts about the robot cuff site.  This module keeps those quantities
separate and binds the explicit loaded robot-side pose/twist used by the
low-level feedback and Safety Filter.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import (
    DEFAULT_LOW_LEVEL_COMMAND_GAINS,
    ExecutableCommandBatchPreview,
    PreparedExecutableCommandContext,
    prepare_executable_command_context,
    preview_executable_commands_batch,
)
from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import (
    sagittal_allocation_matrix,
    sagittal_null_vector,
    sagittal_wrench_to_world_matrix,
)
from traction_mpc_stage4.safety_filter import (
    ExecutableForceFilterContext,
    Stage4ExecutableForceFilter,
)

from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    ControllerNominalInterfaceParameters,
    EstimatedInterfaceState,
)
from .task_observation import ControllerTaskObservation


HUMAN_CUFF_SITE = "human_sleeve_attach_site"
ROBOT_CUFF_SITE = "robot_adapter_cuff_site"


def _vector(name: str, value: Any, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {length}-vector")
    return result.copy()


def _rotation(name: str, value: Any) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (3, 3) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite 3x3 rotation")
    return result.copy()


@dataclass(frozen=True)
class CuffPoseStateWorld:
    """Pose and twist at one explicitly named cuff reference point."""

    reference_point: str
    world_from_cuff: RigidTransform
    linear_velocity_world_m_s: np.ndarray
    angular_velocity_world_rad_s: np.ndarray

    def __post_init__(self) -> None:
        if self.reference_point not in {HUMAN_CUFF_SITE, ROBOT_CUFF_SITE}:
            raise ValueError("unknown cuff reference point")
        object.__setattr__(
            self,
            "linear_velocity_world_m_s",
            _vector("linear_velocity_world_m_s", self.linear_velocity_world_m_s, 3),
        )
        object.__setattr__(
            self,
            "angular_velocity_world_rad_s",
            _vector(
                "angular_velocity_world_rad_s",
                self.angular_velocity_world_rad_s,
                3,
            ),
        )


@dataclass(frozen=True)
class Stage5LoadedExecutionTarget:
    """Controller-nominal loaded target, with both cuff sites named."""

    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    human_cuff_target: CuffPoseStateWorld
    robot_cuff_target: CuffPoseStateWorld
    nominal_interface_displacement_human_m: np.ndarray
    nominal_interface_rotation_human_rad: np.ndarray
    support_human_cuff_wrench_world: np.ndarray
    support_robot_cuff_command_wrench_world: np.ndarray
    nominal_interface_model_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "q_rad", _vector("q_rad", self.q_rad, 2))
        object.__setattr__(self, "dq_rad_s", _vector("dq_rad_s", self.dq_rad_s, 2))
        for name, length in (
            ("nominal_interface_displacement_human_m", 3),
            ("nominal_interface_rotation_human_rad", 3),
            ("support_human_cuff_wrench_world", 6),
            ("support_robot_cuff_command_wrench_world", 6),
        ):
            object.__setattr__(self, name, _vector(name, getattr(self, name), length))
        if not self.nominal_interface_model_version:
            raise ValueError("nominal interface model version must be non-empty")

    @property
    def reference(self) -> CuffPoseReference:
        return CuffPoseReference(
            q_rad=self.q_rad.copy(),
            dq_rad_s=self.dq_rad_s.copy(),
            ddq_rad_s2=np.zeros(2),
            world_from_cuff=self.robot_cuff_target.world_from_cuff,
        )


def human_cuff_wrench_to_robot_cuff_command(
    human_cuff_wrench_world: np.ndarray,
    robot_from_human_world_m: np.ndarray,
) -> np.ndarray:
    """Move a physical wrench from the Human cuff point to the robot point.

    If ``r = p_robot - p_human``, then the same wrench written about the robot
    point is ``[F, M_human - r cross F]``.
    """

    wrench = np.asarray(human_cuff_wrench_world, dtype=float)
    r = np.asarray(robot_from_human_world_m, dtype=float)
    if wrench.shape[-1] != 6 or r.shape[-1] != 3:
        raise ValueError("wrench/reference-point arrays have invalid shape")
    result = wrench.copy()
    result[..., 3:] = wrench[..., 3:] - np.cross(r, wrench[..., :3])
    return result


def wrench_reference_transform_matrix(robot_from_human_world_m: np.ndarray) -> np.ndarray:
    """Return the 6x6 Human-point to robot-point wrench transform."""

    r = _vector("robot_from_human_world_m", robot_from_human_world_m, 3)
    skew = np.array(
        [[0.0, -r[2], r[1]], [r[2], 0.0, -r[0]], [-r[1], r[0], 0.0]]
    )
    transform = np.eye(6)
    transform[3:, :3] = -skew
    return transform


def loaded_execution_target_from_equilibrium(
    equilibrium: Any,
    human_model: Any,
    *,
    interface: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
) -> Stage5LoadedExecutionTarget:
    """Build the loaded robot target represented by one nominal equilibrium."""

    q = np.asarray(equilibrium.q_goal_rad, dtype=float)
    dq = np.asarray(equilibrium.low_level_reference.dq_rad_s, dtype=float)
    human_pose = equilibrium.human_cuff_pose_world
    human_linear, human_angular = human_model.geometry.cuff_velocity(q, dq)
    robot_pose = equilibrium.robot_cuff_pose_world
    r_world = robot_pose.translation - human_pose.translation
    robot_linear = human_linear + np.cross(human_angular, r_world)
    robot_angular = human_angular.copy()
    human_wrench = np.asarray(equilibrium.physical_human_wrench_world, dtype=float)
    robot_wrench = human_cuff_wrench_to_robot_cuff_command(human_wrench, r_world)
    return Stage5LoadedExecutionTarget(
        q_rad=q,
        dq_rad_s=dq,
        human_cuff_target=CuffPoseStateWorld(
            HUMAN_CUFF_SITE,
            human_pose,
            human_linear,
            human_angular,
        ),
        robot_cuff_target=CuffPoseStateWorld(
            ROBOT_CUFF_SITE,
            robot_pose,
            robot_linear,
            robot_angular,
        ),
        nominal_interface_displacement_human_m=(
            equilibrium.interface_displacement_human_m
        ),
        nominal_interface_rotation_human_rad=(
            equilibrium.interface_rotation_error_human_rad
        ),
        support_human_cuff_wrench_world=human_wrench,
        support_robot_cuff_command_wrench_world=robot_wrench,
        nominal_interface_model_version=interface.model_version,
    )


def with_explicit_robot_target(
    target: Stage5LoadedExecutionTarget,
    reference: CuffPoseReference,
    *,
    linear_velocity_world_m_s: np.ndarray | None = None,
    angular_velocity_world_rad_s: np.ndarray | None = None,
) -> Stage5LoadedExecutionTarget:
    """Replace only the robot-side low-level target, e.g. during a handoff."""

    robot = CuffPoseStateWorld(
        ROBOT_CUFF_SITE,
        reference.world_from_cuff,
        (
            np.zeros(3)
            if linear_velocity_world_m_s is None
            else linear_velocity_world_m_s
        ),
        (
            np.zeros(3)
            if angular_velocity_world_rad_s is None
            else angular_velocity_world_rad_s
        ),
    )
    return replace(
        target,
        q_rad=np.asarray(reference.q_rad),
        dq_rad_s=np.asarray(reference.dq_rad_s),
        robot_cuff_target=robot,
    )


class _RobotCuffReferencePointAllocator:
    """Expose robot-point commands while retaining Human-point allocation."""

    def __init__(self, allocator: Any, robot_from_human_world_m: np.ndarray) -> None:
        self.human_cuff_allocator = allocator
        self.robot_from_human_world_m = _vector(
            "robot_from_human_world_m", robot_from_human_world_m, 3
        )

    def allocate(self, action_nm: np.ndarray, q_rad: np.ndarray, human_model: Any):
        result = dict(self.human_cuff_allocator.allocate(action_nm, q_rad, human_model))
        human_wrench = np.asarray(result["wrench_world"], dtype=float)
        robot_wrench = human_cuff_wrench_to_robot_cuff_command(
            human_wrench, self.robot_from_human_world_m
        )
        result["human_cuff_wrench_world"] = human_wrench.copy()
        result["robot_cuff_command_wrench_world"] = robot_wrench.copy()
        # Stage-4's filter contract consumes this generic key.  Within the
        # Stage-5 wrapper it explicitly means a robot-site command wrench.
        result["wrench_world"] = robot_wrench
        return result

    def allocate_wrenches_batch(
        self, actions_nm: np.ndarray, q_rad: np.ndarray, human_model: Any
    ) -> np.ndarray:
        allocate = getattr(self.human_cuff_allocator, "allocate_wrenches_batch", None)
        if allocate is None:
            human = np.vstack(
                [
                    self.human_cuff_allocator.allocate(action, q_rad, human_model)[
                        "wrench_world"
                    ]
                    for action in np.asarray(actions_nm)
                ]
            )
        else:
            human = np.asarray(allocate(actions_nm, q_rad, human_model), dtype=float)
        r = np.broadcast_to(self.robot_from_human_world_m, (len(human), 3))
        return human_cuff_wrench_to_robot_cuff_command(human, r)


@dataclass(frozen=True)
class Stage5LoadedExecutionContext:
    """One measured control instant under the unified loaded authority."""

    target: Stage5LoadedExecutionTarget
    actual_human_cuff: CuffPoseStateWorld
    measured_robot_cuff: CuffPoseStateWorld
    estimated_interface_state: EstimatedInterfaceState
    robot_from_human_world_m: np.ndarray
    command_context: PreparedExecutableCommandContext
    safety_filter_context: ExecutableForceFilterContext

    def make_force_filter(self) -> Stage4ExecutableForceFilter:
        return Stage4ExecutableForceFilter(self.safety_filter_context)

    def preview_command_batch(
        self, actions_nm: np.ndarray
    ) -> ExecutableCommandBatchPreview:
        actions = np.asarray(actions_nm, dtype=float)
        if actions.ndim != 2 or actions.shape[1] != 2:
            raise ValueError("actions_nm must be an Nx2 matrix")
        wrenches = self.safety_filter_context.cuff_allocator.allocate_wrenches_batch(
            actions,
            self.safety_filter_context.estimated_state[:2],
            self.safety_filter_context.human_model,
        )
        return preview_executable_commands_batch(self.command_context, wrenches)


def build_stage5_loaded_execution_context(
    *,
    plant: Any,
    measurement: Any,
    observation: ControllerTaskObservation,
    interface_state: EstimatedInterfaceState,
    human_model: Any,
    cuff_allocator: Any,
    target: Stage5LoadedExecutionTarget,
) -> Stage5LoadedExecutionContext:
    """Bind the one explicit Stage-5 target used by screening and execution."""

    if interface_state.sample_timestamp_s != observation.sample_timestamp_s:
        raise ValueError("Human and interface estimates must share one sample time")
    state = observation.as_array()
    control_velocity = plant.control_feedback_velocity_snapshot(measurement)
    actual_human = CuffPoseStateWorld(
        HUMAN_CUFF_SITE,
        RigidTransform(
            _rotation("human_rotation_world", interface_state.human_rotation_world),
            _vector("human_position_world_m", interface_state.human_position_world_m, 3),
        ),
        interface_state.human_velocity_world_m_s,
        interface_state.human_angular_velocity_world_rad_s,
    )
    measured_robot = CuffPoseStateWorld(
        ROBOT_CUFF_SITE,
        RigidTransform(
            _rotation(
                "measurement.attachment_rotation_matrix",
                measurement.attachment_rotation_matrix,
            ),
            _vector(
                "measurement.attachment_position_m",
                measurement.attachment_position_m,
                3,
            ),
        ),
        control_velocity.linear_velocity_world_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    robot_from_human = (
        measured_robot.world_from_cuff.translation
        - actual_human.world_from_cuff.translation
    )
    measured_robot_model = plant._measured_robot_model
    measured_robot_model.set_configuration(
        measurement.robot_q_rad, measurement.robot_dq_rad_s
    )
    robot_jacobian = measured_robot_model.rigid_offset_jacobian(
        plant.attachment_from_cuff.translation
    )
    command_context = prepare_executable_command_context(
        attachment_position_m=measured_robot.world_from_cuff.translation,
        attachment_rotation_matrix=measured_robot.world_from_cuff.rotation,
        attachment_velocity_m_s=measured_robot.linear_velocity_world_m_s,
        attachment_angular_velocity_rad_s=(
            measured_robot.angular_velocity_world_rad_s
        ),
        robot_q_rad=measurement.robot_q_rad,
        robot_dq_rad_s=measurement.robot_dq_rad_s,
        neutral_robot_q_rad=plant.neutral_robot_q,
        target_position_m=target.robot_cuff_target.world_from_cuff.translation,
        target_velocity_m_s=target.robot_cuff_target.linear_velocity_world_m_s,
        target_rotation_matrix=target.robot_cuff_target.world_from_cuff.rotation,
        target_angular_velocity_rad_s=(
            target.robot_cuff_target.angular_velocity_world_rad_s
        ),
        robot_attachment_jacobian=robot_jacobian,
        bias_torque_nm=measured_robot_model.bias_torque_nm(),
        torque_limits_nm=plant.torque_limits_nm,
    )
    q = state[:2]
    allocation_matrix = sagittal_allocation_matrix(q, human_model)
    null = sagittal_null_vector(q, human_model)
    human_world_mapping = sagittal_wrench_to_world_matrix(q, human_model)
    reference_transform = wrench_reference_transform_matrix(robot_from_human)
    robot_world_mapping = reference_transform @ human_world_mapping
    robot_allocator = _RobotCuffReferencePointAllocator(
        cuff_allocator, robot_from_human
    )
    filter_context = ExecutableForceFilterContext(
        estimated_state=state.copy(),
        human_model=human_model,
        cuff_allocator=robot_allocator,
        command_context=command_context,
        allocation_matrix=allocation_matrix,
        sagittal_null_vector=null,
        world_mapping=robot_world_mapping,
        world_null_wrench=robot_world_mapping @ null,
    )
    return Stage5LoadedExecutionContext(
        target=target,
        actual_human_cuff=actual_human,
        measured_robot_cuff=measured_robot,
        estimated_interface_state=interface_state,
        robot_from_human_world_m=robot_from_human,
        command_context=command_context,
        safety_filter_context=filter_context,
    )


def future_loaded_command_wrench_batch(
    *,
    states: np.ndarray,
    total_human_cuff_wrenches_world: np.ndarray,
    support_human_cuff_wrenches_world: np.ndarray,
    interface_displacement_human_m: np.ndarray,
    interface_velocity_human_m_s: np.ndarray,
    interface_rotation_human_rad: np.ndarray,
    interface_angular_velocity_human_rad_s: np.ndarray,
    human_rotation_world: np.ndarray,
    interface: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
) -> np.ndarray:
    """Apply the same loaded-target and wrench-point semantics in the horizon."""

    state = np.asarray(states, dtype=float)
    total = np.asarray(total_human_cuff_wrenches_world, dtype=float)
    support = np.asarray(support_human_cuff_wrenches_world, dtype=float)
    x = np.asarray(interface_displacement_human_m, dtype=float)
    u = np.asarray(interface_velocity_human_m_s, dtype=float)
    theta = np.asarray(interface_rotation_human_rad, dtype=float)
    omega = np.asarray(interface_angular_velocity_human_rad_s, dtype=float)
    rotation = np.asarray(human_rotation_world, dtype=float)
    count = len(state)
    expected = {
        "total": (total, (count, 6)),
        "support": (support, (count, 6)),
        "x": (x, (count, 3)),
        "u": (u, (count, 3)),
        "theta": (theta, (count, 3)),
        "omega": (omega, (count, 3)),
        "rotation": (rotation, (count, 3, 3)),
    }
    for name, (value, shape) in expected.items():
        if value.shape != shape or not np.all(np.isfinite(value)):
            raise ValueError(f"future {name} has invalid shape/value")
    rest_x = np.asarray(interface.rest_translation_human_m)
    k = np.asarray(interface.translation_stiffness_n_m)
    current_r_human = rest_x + x
    current_r_world = np.einsum("nij,nj->ni", rotation, current_r_human)
    robot_command = human_cuff_wrench_to_robot_cuff_command(
        total, current_r_world
    )

    support_force_human = np.einsum("nji,nj->ni", rotation, support[:, :3])
    target_r_human = rest_x + support_force_human / k
    target_r_world = np.einsum("nij,nj->ni", rotation, target_r_human)
    support_couple_world = support[:, 3:] - np.cross(
        target_r_world, support[:, :3]
    )
    target_theta_human = np.asarray(
        interface.rest_rotation_rotvec_human_rad
    ) + (
        np.einsum("nji,nj->ni", rotation, support_couple_world)
        / interface.rotation_stiffness_nm_rad
    )

    position_error_world = target_r_world - current_r_world
    human_angular_world = (
        rotation[:, :, 1] * (state[:, 3] - state[:, 2])[:, None]
    )
    velocity_error_world = (
        np.cross(human_angular_world, position_error_world)
        - np.einsum("nij,nj->ni", rotation, u)
    )
    orientation_error_world = np.einsum(
        "nij,nj->ni", rotation, target_theta_human - theta
    )
    angular_velocity_error_world = -np.einsum(
        "nij,nj->ni", rotation, omega
    )
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    raw_force_feedback = (
        gains.position_n_per_m * position_error_world
        + gains.velocity_ns_per_m * velocity_error_world
    )
    force_feedback = np.clip(
        raw_force_feedback,
        -gains.feedback_component_limit_n,
        gains.feedback_component_limit_n,
    )
    moment_feedback = (
        gains.orientation_nm_per_rad * orientation_error_world
        + gains.angular_velocity_nms_per_rad * angular_velocity_error_world
    )
    robot_command[:, :3] += force_feedback
    robot_command[:, 3:] += moment_feedback
    return robot_command


__all__ = [
    "CuffPoseStateWorld",
    "HUMAN_CUFF_SITE",
    "ROBOT_CUFF_SITE",
    "Stage5LoadedExecutionContext",
    "Stage5LoadedExecutionTarget",
    "build_stage5_loaded_execution_context",
    "future_loaded_command_wrench_batch",
    "human_cuff_wrench_to_robot_cuff_command",
    "loaded_execution_target_from_equilibrium",
    "with_explicit_robot_target",
    "wrench_reference_transform_matrix",
]
