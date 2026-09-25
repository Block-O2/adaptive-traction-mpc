"""Stage-5 loaded-equilibrium audit and deterministic local HOLD control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import (
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
)
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.safety_filter import ExecutableForceFilterResult

from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    ControllerNominalInterfaceParameters,
    EstimatedInterfaceState,
)
from .geometry import STAGE5_GEOMETRY
from .goal_mpc import _model_inverse_dynamics
from .ik import solve_stage5_ik
from .loaded_execution import (
    Stage5LoadedExecutionTarget,
    build_stage5_loaded_execution_context,
    human_cuff_wrench_to_robot_cuff_command,
    loaded_execution_target_from_equilibrium,
    with_explicit_robot_target,
)
from .task import GoalTaskSpec
from .task_observation import ControllerTaskObservation


@dataclass(frozen=True)
class LoadedHoldEquilibrium:
    """Controller-model loaded equilibrium at the outbound HOLD goal."""

    q_goal_rad: np.ndarray
    required_human_generalized_input_nm: np.ndarray
    physical_human_wrench_world: np.ndarray
    robot_site_support_wrench_world: np.ndarray
    interface_displacement_human_m: np.ndarray
    interface_rotation_error_human_rad: np.ndarray
    human_cuff_pose_world: RigidTransform
    robot_cuff_pose_world: RigidTransform
    low_level_reference: CuffPoseReference
    allocator_wrench_world: np.ndarray
    equilibrium_feedback_force_world_n: np.ndarray
    equilibrium_feedback_moment_world_nm: np.ndarray

    def __post_init__(self) -> None:
        vectors = {
            "q_goal_rad": (self.q_goal_rad, 2),
            "required_human_generalized_input_nm": (
                self.required_human_generalized_input_nm,
                2,
            ),
            "physical_human_wrench_world": (self.physical_human_wrench_world, 6),
            "robot_site_support_wrench_world": (
                self.robot_site_support_wrench_world,
                6,
            ),
            "interface_displacement_human_m": (
                self.interface_displacement_human_m,
                3,
            ),
            "interface_rotation_error_human_rad": (
                self.interface_rotation_error_human_rad,
                3,
            ),
            "allocator_wrench_world": (self.allocator_wrench_world, 6),
            "equilibrium_feedback_force_world_n": (
                self.equilibrium_feedback_force_world_n,
                3,
            ),
            "equilibrium_feedback_moment_world_nm": (
                self.equilibrium_feedback_moment_world_nm,
                3,
            ),
        }
        for name, (value, length) in vectors.items():
            array = np.asarray(value, dtype=float)
            if array.shape != (length,) or not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must be a finite {length}-vector")
            object.__setattr__(self, name, array.copy())


def solve_loaded_hold_equilibrium(
    spec: GoalTaskSpec,
    human_model: Any,
    cuff_allocator: Any,
    *,
    interface: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
    target_q_rad: np.ndarray | None = None,
    target_dq_rad_s: np.ndarray | None = None,
) -> LoadedHoldEquilibrium:
    """Close Human statics, interface strain, and robot-site support wrench."""

    q_goal = np.asarray(
        spec.outbound_goal_target_rad if target_q_rad is None else target_q_rad,
        dtype=float,
    )
    if q_goal.shape != (2,) or not np.all(np.isfinite(q_goal)):
        raise ValueError("loaded-equilibrium target must be a finite two-vector")
    zeros = np.zeros(2)
    target_dq = np.asarray(
        zeros if target_dq_rad_s is None else target_dq_rad_s, dtype=float
    )
    if target_dq.shape != (2,) or not np.all(np.isfinite(target_dq)):
        raise ValueError("loaded-equilibrium velocity must be a finite two-vector")
    required_input = _model_inverse_dynamics(
        q_goal, target_dq, zeros, human_model
    )
    allocation = cuff_allocator.allocate(required_input, q_goal, human_model)
    human_wrench = np.asarray(allocation["wrench_world"], dtype=float)
    human_pose = human_model.geometry.cuff_pose(q_goal)
    rotation_human = human_pose.rotation
    stiffness = np.asarray(interface.translation_stiffness_n_m, dtype=float)
    rest_translation = np.asarray(interface.rest_translation_human_m, dtype=float)
    displacement = rotation_human.T @ human_wrench[:3] / stiffness
    r_human = rest_translation + displacement
    r_world = rotation_human @ r_human
    pure_couple_world = human_wrench[3:] - np.cross(r_world, human_wrench[:3])
    theta = (
        rotation_human.T @ pure_couple_world
        / interface.rotation_stiffness_nm_rad
    )
    rest_rotation = Rotation.from_rotvec(
        interface.rest_rotation_rotvec_human_rad
    ).as_matrix()
    robot_rotation = (
        rotation_human @ Rotation.from_rotvec(theta).as_matrix() @ rest_rotation
    )
    robot_pose = RigidTransform(
        robot_rotation,
        human_pose.translation + r_world,
    )
    robot_site_support = np.concatenate(
        [human_wrench[:3], pure_couple_world]
    )
    # The unified Stage-5 execution adapter moves the Human-site allocator
    # wrench to the robot reference point explicitly. The loaded robot pose is
    # therefore a zero-feedback equilibrium.
    feedback_force = np.zeros(3)
    feedback_moment = np.zeros(3)
    reference = CuffPoseReference(
        q_rad=q_goal.copy(),
        dq_rad_s=target_dq.copy(),
        ddq_rad_s2=zeros.copy(),
        world_from_cuff=RigidTransform(robot_rotation, robot_pose.translation.copy()),
    )
    return LoadedHoldEquilibrium(
        q_goal_rad=q_goal,
        required_human_generalized_input_nm=required_input,
        physical_human_wrench_world=human_wrench,
        robot_site_support_wrench_world=robot_site_support,
        interface_displacement_human_m=displacement,
        interface_rotation_error_human_rad=theta,
        human_cuff_pose_world=human_pose,
        robot_cuff_pose_world=robot_pose,
        low_level_reference=reference,
        allocator_wrench_world=human_wrench,
        equilibrium_feedback_force_world_n=feedback_force,
        equilibrium_feedback_moment_world_nm=feedback_moment,
    )


def initialize_plant_at_loaded_equilibrium(
    plant: Any,
    human_model: Any,
    equilibrium: LoadedHoldEquilibrium,
) -> Any:
    """Set a time-zero loaded state without introducing a task phase.

    This is an engineering initial condition, not online controller access to
    plant-truth interface parameters.  Its strain comes from the controller
    nominal equilibrium and is used only for the matched smoke fixture.
    """

    human_pose = human_model.geometry.cuff_pose(equilibrium.q_goal_rad)
    robot_pose = equilibrium.robot_cuff_pose_world
    world_from_end_effector = robot_pose.compose(
        STAGE5_GEOMETRY.end_effector_from_cuff.inverse()
    )
    base_from_end_effector = STAGE5_GEOMETRY.world_from_base.inverse().compose(
        world_from_end_effector
    )
    robot_q = solve_stage5_ik(
        plant._ik_robot,
        base_from_end_effector,
        previous_q_rad=plant.data.qpos[plant.robot_qpos_indices].copy(),
    )
    plant.data.qpos[plant.human_qpos_indices] = equilibrium.q_goal_rad
    plant.data.qpos[plant.robot_qpos_indices] = robot_q
    plant.data.qvel[:] = 0.0
    plant.data.ctrl[:] = 0.0
    plant.neutral_robot_q = robot_q.copy()
    plant.last_joint_torque[:] = 0.0
    plant.last_unclipped_joint_torque[:] = 0.0
    plant.last_force[:] = 0.0
    plant.last_moment[:] = 0.0
    # observe() refreshes MuJoCo kinematics and the Stage-5 interface load.
    observation = plant.observe()
    if not np.allclose(
        human_pose.translation,
        plant._attachment_state(plant.sleeve_site_id).position_world_m,
        atol=1.0e-8,
    ):
        raise RuntimeError("loaded initialization changed the Human cuff pose")
    return observation


@dataclass(frozen=True)
class LocalHoldStabilizerConfig:
    """No new tuned gains: reuse the registered Human tracking acceleration law."""

    position_acceleration_gain_rad_s2_per_rad: tuple[float, float] = tuple(
        float(value) for value in TRACKING_KP_RAD_S2_PER_RAD
    )
    velocity_acceleration_gain_rad_s2_per_rad_s: tuple[float, float] = tuple(
        float(value) for value in TRACKING_KD_RAD_S2_PER_RAD_S
    )

    def __post_init__(self) -> None:
        for name, values in (
            ("position gain", self.position_acceleration_gain_rad_s2_per_rad),
            ("velocity gain", self.velocity_acceleration_gain_rad_s2_per_rad_s),
        ):
            array = np.asarray(values, dtype=float)
            if array.shape != (2,) or np.any(array <= 0.0) or not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must be a finite positive two-vector")


@dataclass(frozen=True)
class LoadedHoldHandoffConfig:
    """Provisional bumpless pose-reference transfer; not a HOLD gain."""

    duration_s: float = 0.10

    def __post_init__(self) -> None:
        if not np.isfinite(self.duration_s) or self.duration_s <= 0.0:
            raise ValueError("handoff duration must be finite and positive")


def filter_stage5_executable_action_with_pose(
    *,
    plant: Any,
    measurement: Any,
    observation: ControllerTaskObservation,
    interface_state: EstimatedInterfaceState,
    human_model: Any,
    cuff_allocator: Any,
    action_nm: np.ndarray,
    reference: CuffPoseReference,
    execution_target: Stage5LoadedExecutionTarget,
    explicit_robot_linear_velocity_world_m_s: np.ndarray | None = None,
    explicit_robot_angular_velocity_world_rad_s: np.ndarray | None = None,
) -> ExecutableForceFilterResult:
    """Run the inherited Safety Filter with one explicit Stage-5 pose authority."""

    action = np.asarray(action_nm, dtype=float)
    target = with_explicit_robot_target(
        execution_target, reference,
        linear_velocity_world_m_s=explicit_robot_linear_velocity_world_m_s,
        angular_velocity_world_rad_s=explicit_robot_angular_velocity_world_rad_s,
    )
    context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=human_model,
        cuff_allocator=cuff_allocator,
        target=target,
    )
    batch_filter = context.make_force_filter()
    batch_filter(action[np.newaxis, :])
    return batch_filter.selected_result(action)


class LoadedEquilibriumHoldStabilizer:
    """Computed-torque Human feedback around one nonzero-load equilibrium."""

    def __init__(
        self,
        equilibrium: LoadedHoldEquilibrium,
        human_model: Any,
        *,
        config: LocalHoldStabilizerConfig = LocalHoldStabilizerConfig(),
    ) -> None:
        self.equilibrium = equilibrium
        self.human_model = human_model
        self.config = config

    def command(
        self,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
    ) -> tuple[np.ndarray, CuffPoseReference, dict[str, Any]]:
        state = observation.as_array()
        if interface_state.sample_timestamp_s != observation.sample_timestamp_s:
            raise ValueError("Human and interface estimates must share one sample time")
        kp = np.asarray(self.config.position_acceleration_gain_rad_s2_per_rad)
        kd = np.asarray(self.config.velocity_acceleration_gain_rad_s2_per_rad_s)
        desired_acceleration = (
            -kp * (state[:2] - self.equilibrium.q_goal_rad)
            - kd * state[2:]
        )
        action = _model_inverse_dynamics(
            state[:2], state[2:], desired_acceleration, self.human_model
        )
        interface_translation_error = (
            interface_state.displacement_human_m
            - self.equilibrium.interface_displacement_human_m
        )
        interface_rotation_error = (
            interface_state.rotation_error_human_rad
            - self.equilibrium.interface_rotation_error_human_rad
        )
        return action, self.equilibrium.low_level_reference, {
            "controller": "stage5_loaded_equilibrium_local_hold_v1",
            "desired_acceleration_rad_s2": desired_acceleration.copy(),
            "q_error_rad": state[:2] - self.equilibrium.q_goal_rad,
            "dq_rad_s": state[2:].copy(),
            "interface_translation_error_m": interface_translation_error,
            "interface_rotation_error_rad": interface_rotation_error,
            "uses_human_truth": False,
            "supporting_wrench_is_feedforward_not_feedback": True,
        }

    def filter_executable_command(
        self,
        *,
        plant: Any,
        measurement: Any,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        cuff_allocator: Any,
        reference_override: CuffPoseReference | None = None,
    ) -> tuple[np.ndarray, CuffPoseReference, ExecutableForceFilterResult, dict[str, Any]]:
        """Use the existing safety filter with the explicit loaded robot pose."""

        action, reference, diagnostics = self.command(observation, interface_state)
        if reference_override is not None:
            reference = reference_override
        result = filter_stage5_executable_action_with_pose(
            plant=plant,
            measurement=measurement,
            observation=observation,
            interface_state=interface_state,
            human_model=self.human_model,
            cuff_allocator=cuff_allocator,
            action_nm=action,
            reference=reference,
            execution_target=loaded_execution_target_from_equilibrium(
                self.equilibrium, self.human_model
            ),
        )
        return action, reference, result, diagnostics


class BumplessExecutableReferenceHandoff:
    """Transfer one executable pose authority while keeping wrench continuous."""

    def __init__(
        self, *, config: LoadedHoldHandoffConfig = LoadedHoldHandoffConfig()
    ) -> None:
        self.config = config
        self._elapsed_s = 0.0
        self._active = False
        self._entry_wrench_world: np.ndarray | None = None
        self._target_wrench_world: np.ndarray | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def complete(self) -> bool:
        return self._active and self._elapsed_s >= self.config.duration_s

    def activate(self, previous_executable_wrench_world: np.ndarray) -> None:
        previous = np.asarray(previous_executable_wrench_world, dtype=float)
        if previous.shape != (6,) or not np.all(np.isfinite(previous)):
            raise ValueError("previous executable wrench must be a finite six-vector")
        self._entry_wrench_world = previous.copy()
        self._target_wrench_world = None
        self._elapsed_s = 0.0
        self._active = True

    @staticmethod
    def _quintic(value: float) -> float:
        s = float(np.clip(value, 0.0, 1.0))
        return 10.0 * s**3 - 15.0 * s**4 + 6.0 * s**5

    def reference(
        self,
        *,
        plant: Any,
        measurement: Any,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        action_nm: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
        desired_reference: CuffPoseReference,
    ) -> tuple[CuffPoseReference, dict[str, Any]]:
        if not self.active or self._entry_wrench_world is None:
            raise RuntimeError("handoff must be activated before use")
        action = np.asarray(action_nm, dtype=float)
        q = observation.as_array()[:2]
        allocation = cuff_allocator.allocate(action, q, human_model)
        human_cuff_wrench = np.asarray(allocation["wrench_world"], dtype=float)
        robot_from_human = (
            np.asarray(measurement.attachment_position_m, dtype=float)
            - np.asarray(interface_state.human_position_world_m, dtype=float)
        )
        allocator_wrench = human_cuff_wrench_to_robot_cuff_command(
            human_cuff_wrench, robot_from_human
        )
        gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
        control_velocity = plant.control_feedback_velocity_snapshot(measurement)
        measured_position = np.asarray(measurement.attachment_position_m, dtype=float)
        measured_rotation = np.asarray(
            measurement.attachment_rotation_matrix, dtype=float
        )
        linear_velocity = np.asarray(
            control_velocity.linear_velocity_world_m_s, dtype=float
        )
        angular_velocity = np.asarray(
            measurement.attachment_angular_velocity_rad_s, dtype=float
        )
        desired_force = (
            allocator_wrench[:3]
            + gains.position_n_per_m
            * (desired_reference.world_from_cuff.translation - measured_position)
            - gains.velocity_ns_per_m * linear_velocity
        )
        desired_orientation_error = Rotation.from_matrix(
            desired_reference.world_from_cuff.rotation @ measured_rotation.T
        ).as_rotvec()
        desired_moment = (
            allocator_wrench[3:]
            + gains.orientation_nm_per_rad * desired_orientation_error
            - gains.angular_velocity_nms_per_rad * angular_velocity
        )
        desired_wrench = np.concatenate([desired_force, desired_moment])
        if self._target_wrench_world is None:
            # Freeze the first target command. Re-optimizing the action while
            # the plant receives only a partial blend creates a prediction /
            # execution mismatch and can make the transfer self-exciting.
            self._target_wrench_world = desired_wrench.copy()
        alpha = self._quintic(self._elapsed_s / self.config.duration_s)
        target_wrench = (
            (1.0 - alpha) * self._entry_wrench_world
            + alpha * self._target_wrench_world
        )
        force_feedback = target_wrench[:3] - allocator_wrench[:3]
        moment_feedback = target_wrench[3:] - allocator_wrench[3:]
        target_position = measured_position + (
            force_feedback + gains.velocity_ns_per_m * linear_velocity
        ) / gains.position_n_per_m
        orientation_error = (
            moment_feedback
            + gains.angular_velocity_nms_per_rad * angular_velocity
        ) / gains.orientation_nm_per_rad
        target_rotation = (
            Rotation.from_rotvec(orientation_error).as_matrix()
            @ measured_rotation
        )
        reference = CuffPoseReference(
            q_rad=desired_reference.q_rad.copy(),
            dq_rad_s=desired_reference.dq_rad_s.copy(),
            ddq_rad_s2=desired_reference.ddq_rad_s2.copy(),
            world_from_cuff=RigidTransform(target_rotation, target_position),
        )
        return reference, {
            "elapsed_s": self._elapsed_s,
            "duration_s": self.config.duration_s,
            "alpha": alpha,
            "entry_wrench_world": self._entry_wrench_world.copy(),
            "desired_wrench_world": desired_wrench,
            "frozen_target_wrench_world": self._target_wrench_world.copy(),
            "target_wrench_world": target_wrench,
        }

    def advance(self, dt_s: float) -> None:
        self._elapsed_s += float(dt_s)


class BumplessLoadedHoldHandoff:
    """Blend one command-continuous entry reference to the loaded equilibrium."""

    def __init__(
        self,
        stabilizer: LoadedEquilibriumHoldStabilizer,
        *,
        config: LoadedHoldHandoffConfig = LoadedHoldHandoffConfig(),
    ) -> None:
        self.stabilizer = stabilizer
        self.config = config
        self._initial_pose: RigidTransform | None = None
        self._elapsed_s = 0.0

    @property
    def active(self) -> bool:
        return self._initial_pose is not None

    def activate(
        self,
        *,
        measurement: Any,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        cuff_allocator: Any,
        previous_executable_wrench_world: np.ndarray,
    ) -> None:
        action, _, _ = self.stabilizer.command(observation, interface_state)
        allocation = cuff_allocator.allocate(
            action, observation.as_array()[:2], self.stabilizer.human_model
        )
        human_cuff_wrench = np.asarray(allocation["wrench_world"], dtype=float)
        robot_from_human = (
            np.asarray(measurement.attachment_position_m, dtype=float)
            - np.asarray(interface_state.human_position_world_m, dtype=float)
        )
        allocator_wrench = human_cuff_wrench_to_robot_cuff_command(
            human_cuff_wrench, robot_from_human
        )
        previous = np.asarray(previous_executable_wrench_world, dtype=float)
        if previous.shape != (6,) or not np.all(np.isfinite(previous)):
            raise ValueError("previous executable wrench must be a finite six-vector")
        gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
        force_feedback = previous[:3] - allocator_wrench[:3]
        moment_feedback = previous[3:] - allocator_wrench[3:]
        target_position = np.asarray(measurement.attachment_position_m) + (
            force_feedback
            + gains.velocity_ns_per_m
            * np.asarray(measurement.attachment_velocity_m_s)
        ) / gains.position_n_per_m
        orientation_error = (
            moment_feedback
            + gains.angular_velocity_nms_per_rad
            * np.asarray(measurement.attachment_angular_velocity_rad_s)
        ) / gains.orientation_nm_per_rad
        target_rotation = (
            Rotation.from_rotvec(orientation_error).as_matrix()
            @ np.asarray(measurement.attachment_rotation_matrix)
        )
        self._initial_pose = RigidTransform(target_rotation, target_position)
        self._elapsed_s = 0.0

    @staticmethod
    def _quintic(value: float) -> float:
        s = float(np.clip(value, 0.0, 1.0))
        return 10.0 * s**3 - 15.0 * s**4 + 6.0 * s**5

    def _reference(self) -> CuffPoseReference:
        if self._initial_pose is None:
            raise RuntimeError("handoff must be activated before use")
        alpha = self._quintic(self._elapsed_s / self.config.duration_s)
        final = self.stabilizer.equilibrium.low_level_reference.world_from_cuff
        translation = (
            (1.0 - alpha) * self._initial_pose.translation
            + alpha * final.translation
        )
        relative = Rotation.from_matrix(
            final.rotation @ self._initial_pose.rotation.T
        ).as_rotvec()
        rotation = (
            Rotation.from_rotvec(alpha * relative).as_matrix()
            @ self._initial_pose.rotation
        )
        return CuffPoseReference(
            q_rad=self.stabilizer.equilibrium.q_goal_rad.copy(),
            dq_rad_s=np.zeros(2),
            ddq_rad_s2=np.zeros(2),
            world_from_cuff=RigidTransform(rotation, translation),
        )

    def command(
        self,
        *,
        plant: Any,
        measurement: Any,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        cuff_allocator: Any,
        dt_s: float,
    ) -> tuple[np.ndarray, CuffPoseReference, ExecutableForceFilterResult, dict[str, Any]]:
        if not self.active:
            raise RuntimeError("handoff must be activated before use")
        reference = self._reference()
        result = self.stabilizer.filter_executable_command(
            plant=plant,
            measurement=measurement,
            observation=observation,
            interface_state=interface_state,
            cuff_allocator=cuff_allocator,
            reference_override=reference,
        )
        diagnostics = dict(result[3])
        diagnostics.update(
            {
                "handoff_elapsed_s": self._elapsed_s,
                "handoff_duration_s": self.config.duration_s,
                "handoff_complete": self._elapsed_s >= self.config.duration_s,
            }
        )
        self._elapsed_s += float(dt_s)
        return result[0], result[1], result[2], diagnostics


__all__ = [
    "BumplessExecutableReferenceHandoff",
    "BumplessLoadedHoldHandoff",
    "LoadedHoldEquilibrium",
    "LoadedEquilibriumHoldStabilizer",
    "LoadedHoldHandoffConfig",
    "LocalHoldStabilizerConfig",
    "filter_stage5_executable_action_with_pose",
    "initialize_plant_at_loaded_equilibrium",
    "solve_loaded_hold_equilibrium",
]
