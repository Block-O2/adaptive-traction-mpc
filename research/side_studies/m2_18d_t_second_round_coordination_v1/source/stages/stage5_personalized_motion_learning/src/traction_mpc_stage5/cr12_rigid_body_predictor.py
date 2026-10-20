"""Shadow-only CR12 rigid-body execution predictor for the first 20 ms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import mujoco
import numpy as np

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS

from .acceleration_semantics import screen_cumulative_prefix_acceleration
from .compact_execution_predictor import CompactClosedLoopFirstActionBatchPreview
from .controller_interface import (
    InterfaceAwareFirstActionBatchPreview,
    InterfaceHoldPredictionBatch,
)
from .cr12_robot import CR12TorqueRobot
from .geometry import STAGE5_GEOMETRY


CR12_RIGID_BODY_PREDICTOR_VERSION = "cr12_rigid_body_execution_v1"
CR12_RIGID_BODY_PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])


def _finite(name: str, value: Any, shape: tuple[int, ...]) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result.copy()


@dataclass(frozen=True)
class CR12RigidBodyPredictionState:
    """Deployable CR12 state and fixed execution-posture reference."""

    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    neutral_q_rad: np.ndarray

    def __post_init__(self) -> None:
        for name in ("q_rad", "dq_rad_s", "neutral_q_rad"):
            object.__setattr__(self, name, _finite(name, getattr(self, name), (6,)))


@dataclass(frozen=True)
class CR12RigidBodyPredictionContract:
    """Frozen integration and calibration-only qualification contract."""

    acceleration_margin_rad_s2: np.ndarray
    calibration_group_ids: tuple[str, ...]
    physics_dt_s: float = 0.00025
    version: str = CR12_RIGID_BODY_PREDICTOR_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acceleration_margin_rad_s2",
            _finite(
                "acceleration_margin_rad_s2",
                self.acceleration_margin_rad_s2,
                (2,),
            ),
        )
        if np.any(self.acceleration_margin_rad_s2 < 0.0):
            raise ValueError("acceleration margin must be nonnegative")
        if not np.isfinite(self.physics_dt_s) or self.physics_dt_s <= 0.0:
            raise ValueError("physics_dt_s must be finite and positive")
        if not np.isclose(0.005 / self.physics_dt_s, round(0.005 / self.physics_dt_s)):
            raise ValueError("physics_dt_s must divide the 5 ms command hold")
        if self.version != CR12_RIGID_BODY_PREDICTOR_VERSION:
            raise ValueError("CR12 rigid-body predictor version mismatch")

    def with_calibration_margin(
        self,
        margin_rad_s2: Sequence[float],
        calibration_group_ids: Sequence[str],
    ) -> "CR12RigidBodyPredictionContract":
        return CR12RigidBodyPredictionContract(
            acceleration_margin_rad_s2=np.asarray(margin_rad_s2, dtype=float),
            calibration_group_ids=tuple(str(value) for value in calibration_group_ids),
            physics_dt_s=self.physics_dt_s,
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "physics_dt_s": self.physics_dt_s,
            "acceleration_margin_rad_s2": self.acceleration_margin_rad_s2.tolist(),
            "calibration_group_ids": list(self.calibration_group_ids),
            "robot_model": "official_integrated_cr12_v0",
            "contact_prediction": False,
        }


class CR12RigidBodyFirstActionBatchPreview(InterfaceAwareFirstActionBatchPreview):
    """Protocol-compatible first-action preview with explicit CR12 dynamics."""

    _human_pose_batch = staticmethod(
        CompactClosedLoopFirstActionBatchPreview._human_pose_batch
    )
    _human_action_from_wrench = staticmethod(
        CompactClosedLoopFirstActionBatchPreview._human_action_from_wrench
    )
    _human_step = CompactClosedLoopFirstActionBatchPreview._human_step
    _interface_state_and_wrench = (
        CompactClosedLoopFirstActionBatchPreview._interface_state_and_wrench
    )

    def __init__(
        self,
        *args: Any,
        rigid_body_contract: CR12RigidBodyPredictionContract,
        robot_state: CR12RigidBodyPredictionState,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not isinstance(rigid_body_contract, CR12RigidBodyPredictionContract):
            raise TypeError("rigid_body_contract has the wrong type")
        if not isinstance(robot_state, CR12RigidBodyPredictionState):
            raise TypeError("robot_state has the wrong type")
        self.rigid_body_contract = rigid_body_contract
        self.robot_state = robot_state
        self._robot = CR12TorqueRobot()
        self._rotate_twist_to_world = np.block(
            [
                [STAGE5_GEOMETRY.world_from_base.rotation, np.zeros((3, 3))],
                [np.zeros((3, 3)), STAGE5_GEOMETRY.world_from_base.rotation],
            ]
        )

    def _robot_kinematics(
        self, q_rad: np.ndarray, dq_rad_s: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        self._robot.set_configuration(q_rad, dq_rad_s)
        base_from_flange = self._robot.attachment_pose()
        world_from_cuff = STAGE5_GEOMETRY.world_from_base.compose(
            base_from_flange.compose(STAGE5_GEOMETRY.end_effector_from_cuff)
        )
        jacobian_world = self._rotate_twist_to_world @ self._robot.rigid_offset_jacobian(
            STAGE5_GEOMETRY.end_effector_from_cuff.translation
        )
        twist = jacobian_world @ dq_rad_s
        return (
            world_from_cuff.translation,
            world_from_cuff.rotation,
            twist[:3],
            twist[3:],
            jacobian_world,
        )

    def _robot_forward_acceleration(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        torque_command_nm: np.ndarray,
        physical_robot_wrench_world: np.ndarray,
        jacobian_world: np.ndarray,
    ) -> np.ndarray:
        self._robot.set_configuration(q_rad, dq_rad_s)
        mass = np.empty((6, 6), dtype=float)
        mujoco.mj_fullM(self._robot.model, self._robot.data, mass)
        bias = self._robot.data.qfrc_bias[self._robot.dof_indices]
        generalized_external = jacobian_world.T @ physical_robot_wrench_world
        return np.linalg.solve(
            mass,
            np.asarray(torque_command_nm, dtype=float) + generalized_external - bias,
        )

    @staticmethod
    def _physical_robot_wrench(
        human_site_wrench_world: np.ndarray, robot_from_human_world_m: np.ndarray
    ) -> np.ndarray:
        force = np.asarray(human_site_wrench_world, dtype=float)[:, :3]
        human_moment = np.asarray(human_site_wrench_world, dtype=float)[:, 3:]
        pure_couple = human_moment - np.cross(robot_from_human_world_m, force)
        return np.concatenate([-force, -pure_couple], axis=1)

    def _joint_torque_batch(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        command_wrench_world: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
        torque = np.empty((len(q_rad), 6), dtype=float)
        jacobians = np.empty((len(q_rad), 6, 6), dtype=float)
        for index in range(len(q_rad)):
            _, _, _, _, jacobian = self._robot_kinematics(
                q_rad[index], dq_rad_s[index]
            )
            jacobians[index] = jacobian
            pinv = jacobian.T @ np.linalg.inv(
                jacobian @ jacobian.T + gains.cartesian_damping * np.eye(6)
            )
            nullspace = np.eye(6) - pinv @ jacobian
            posture = gains.posture_nm_per_rad * (
                self.robot_state.neutral_q_rad - q_rad[index]
            ) - gains.posture_damping_nms_per_rad * dq_rad_s[index]
            base = self._robot.bias_torque_nm() + nullspace.T @ posture
            unclipped = base + jacobian.T @ command_wrench_world[index]
            torque[index] = np.clip(
                unclipped,
                -self._robot.torque_limits_nm,
                self._robot.torque_limits_nm,
            )
        return torque, jacobians

    def _kinematics_batch(
        self, q_rad: np.ndarray, dq_rad_s: np.ndarray
    ) -> tuple[np.ndarray, ...]:
        count = len(q_rad)
        position = np.empty((count, 3), dtype=float)
        rotation = np.empty((count, 3, 3), dtype=float)
        linear = np.empty((count, 3), dtype=float)
        angular = np.empty((count, 3), dtype=float)
        jacobian = np.empty((count, 6, 6), dtype=float)
        for index in range(count):
            (
                position[index],
                rotation[index],
                linear[index],
                angular[index],
                jacobian[index],
            ) = self._robot_kinematics(q_rad[index], dq_rad_s[index])
        return position, rotation, linear, angular, jacobian

    def _rigid_body_prediction(
        self, actions_nm: np.ndarray, executable_batch: Any
    ) -> InterfaceHoldPredictionBatch:
        if (
            self.state_rad_rad_s is None
            or self.acceleration_limits_rad_s2 is None
            or self._prefix_support_provider is None
            or self._prefix_future_command_resolver is None
        ):
            raise RuntimeError("rigid-body predictor is missing prefix bindings")
        actions = np.asarray(actions_nm, dtype=float)
        count = len(actions)
        human_states = np.broadcast_to(self.state_rad_rad_s, (count, 4)).copy()
        initial_human_dq = human_states[:, 2:].copy()
        robot_q = np.broadcast_to(self.robot_state.q_rad, (count, 6)).copy()
        robot_dq = np.broadcast_to(self.robot_state.dq_rad_s, (count, 6)).copy()
        command = np.column_stack(
            [executable_batch.force_total_n, executable_batch.moment_total_nm]
        )
        torque = np.asarray(executable_batch.joint_torque_command_nm, dtype=float).copy()
        future_command_feasible = np.ones(count, dtype=bool)
        supported = np.ones(count, dtype=bool)

        prefix_human = np.empty((count, 4, 4), dtype=float)
        prefix_robot_q = np.empty((count, 4, 6), dtype=float)
        prefix_robot_dq = np.empty_like(prefix_robot_q)
        prefix_position = np.empty((count, 4, 3), dtype=float)
        prefix_rotation = np.empty((count, 4, 3, 3), dtype=float)
        prefix_linear = np.empty((count, 4, 3), dtype=float)
        prefix_angular = np.empty((count, 4, 3), dtype=float)
        prefix_x = np.empty((count, 4, 3), dtype=float)
        prefix_u = np.empty_like(prefix_x)
        prefix_theta = np.empty_like(prefix_x)
        prefix_omega = np.empty_like(prefix_x)
        prefix_wrench = np.empty((count, 4, 6), dtype=float)
        prefix_command = np.empty((count, 4, 6), dtype=float)

        dt_s = self.rigid_body_contract.physics_dt_s
        substeps = int(round(0.005 / dt_s))
        joint_limits = self._robot.joint_limits_rad
        velocity_limits = self._robot.velocity_limits_rad_s

        for segment in range(4):
            for _ in range(substeps):
                position, rotation, linear, angular, robot_jacobian = (
                    self._kinematics_batch(robot_q, robot_dq)
                )
                (
                    _,
                    _,
                    _,
                    _,
                    human_wrench,
                    _,
                    human_jacobian,
                    robot_from_human,
                ) = self._interface_state_and_wrench(
                    human_states, position, rotation, linear, angular
                )
                robot_wrench = self._physical_robot_wrench(
                    human_wrench, robot_from_human
                )
                robot_qdd = np.empty_like(robot_q)
                for candidate in range(count):
                    robot_qdd[candidate] = self._robot_forward_acceleration(
                        robot_q[candidate],
                        robot_dq[candidate],
                        torque[candidate],
                        robot_wrench[candidate],
                        robot_jacobian[candidate],
                    )
                human_action = self._human_action_from_wrench(
                    human_wrench,
                    human_jacobian,
                    np.asarray(self.human_model.geometry.joint_axis_world),
                )
                human_states = self._human_step(human_states, human_action, dt_s)
                robot_dq = robot_dq + dt_s * robot_qdd
                robot_q = robot_q + dt_s * robot_dq
                supported &= np.all(
                    (robot_q >= joint_limits[None, :, 0] - 1.0e-12)
                    & (robot_q <= joint_limits[None, :, 1] + 1.0e-12),
                    axis=1,
                )
                supported &= np.all(
                    np.abs(robot_dq) <= velocity_limits[None, :] + 1.0e-12,
                    axis=1,
                )
                supported &= np.all(np.isfinite(robot_q), axis=1) & np.all(
                    np.isfinite(robot_dq), axis=1
                )
                if not np.all(supported):
                    # Unsupported trajectories must never be passed back into
                    # MuJoCo state setters on a later substep.
                    robot_q = np.clip(
                        robot_q, joint_limits[None, :, 0], joint_limits[None, :, 1]
                    )

            position, rotation, linear, angular, _ = self._kinematics_batch(
                robot_q, robot_dq
            )
            endpoint = self._interface_state_and_wrench(
                human_states, position, rotation, linear, angular
            )
            x, u, theta, omega, human_wrench, human_rotation, _, _ = endpoint
            prefix_human[:, segment] = human_states
            prefix_robot_q[:, segment] = robot_q
            prefix_robot_dq[:, segment] = robot_dq
            prefix_position[:, segment] = position
            prefix_rotation[:, segment] = rotation
            prefix_linear[:, segment] = linear
            prefix_angular[:, segment] = angular
            prefix_x[:, segment] = x
            prefix_u[:, segment] = u
            prefix_theta[:, segment] = theta
            prefix_omega[:, segment] = omega
            prefix_wrench[:, segment] = human_wrench
            prefix_command[:, segment] = command

            if segment == 3:
                continue
            support_action = np.asarray(
                self._prefix_support_provider(human_states), dtype=float
            )
            requested_wrench = self._allocate_varying_q_batch(
                actions, human_states[:, :2]
            )
            support_wrench = self._allocate_varying_q_batch(
                support_action, human_states[:, :2]
            )
            command = np.asarray(
                self._prefix_future_command_resolver(
                    human_states,
                    actions,
                    requested_wrench,
                    interface_displacement_human_m=x,
                    interface_velocity_human_m_s=u,
                    interface_rotation_human_rad=theta,
                    interface_angular_velocity_human_rad_s=omega,
                    human_rotation_world=human_rotation,
                    support_human_wrenches_world=support_wrench,
                ),
                dtype=float,
            )
            future_command_feasible &= (
                np.linalg.norm(command[:, :3], axis=1)
                <= DEFAULT_LOW_LEVEL_COMMAND_GAINS.translational_force_gate_n
                + DEFAULT_LOW_LEVEL_COMMAND_GAINS.force_gate_tolerance_n
            )
            torque, _ = self._joint_torque_batch(robot_q, robot_dq, command)

        acceleration = screen_cumulative_prefix_acceleration(
            initial_human_dq,
            prefix_human[..., 2:],
            CR12_RIGID_BODY_PREFIX_TIMES_S,
            self.acceleration_limits_rad_s2,
        )
        qualified_margin = (
            self.acceleration_limits_rad_s2[None, None, :]
            - np.abs(acceleration.acceleration_rad_s2)
            - self.rigid_body_contract.acceleration_margin_rad_s2[None, None, :]
        )
        acceleration_feasible = np.all(qualified_margin >= -1.0e-12, axis=(1, 2))
        force_norm = np.linalg.norm(prefix_wrench[..., :3], axis=2)
        moment_norm = np.linalg.norm(prefix_wrench[..., 3:], axis=2)
        peak_force = np.max(force_norm, axis=1)
        peak_moment = np.max(moment_norm, axis=1)
        force_margin = self.predictor.planning_force_ceiling_n - peak_force
        feasible = (
            np.asarray(executable_batch.feasible, dtype=bool)
            & future_command_feasible
            & supported
            & acceleration_feasible
            & (force_margin >= -1.0e-9)
        )
        mean_wrench = np.mean(prefix_wrench, axis=1)
        return InterfaceHoldPredictionBatch(
            executable_batch=executable_batch,
            feasible=feasible,
            predicted_peak_force_n=peak_force,
            predicted_endpoint_force_world_n=prefix_wrench[:, -1, :3],
            predicted_mean_force_world_n=mean_wrench[:, :3],
            predicted_peak_moment_nm=peak_moment,
            predicted_endpoint_moment_world_nm=prefix_wrench[:, -1, 3:],
            predicted_mean_moment_world_nm=mean_wrench[:, 3:],
            margin_to_physical_force_gate_n=force_margin,
            acceleration_semantics_version=(
                "cr12_rigid_body_v1_cumulative_prefix_5_10_15_20ms"
            ),
            prefix_times_s=CR12_RIGID_BODY_PREFIX_TIMES_S.copy(),
            predicted_prefix_states_rad_rad_s=prefix_human,
            predicted_prefix_acceleration_rad_s2=acceleration.acceleration_rad_s2,
            prefix_acceleration_margin_rad_s2=qualified_margin,
            prefix_acceleration_feasible=acceleration_feasible,
            predicted_prefix_interface_displacement_human_m=prefix_x,
            predicted_prefix_interface_velocity_human_m_s=prefix_u,
            predicted_prefix_interface_rotation_human_rad=prefix_theta,
            predicted_prefix_interface_angular_velocity_human_rad_s=prefix_omega,
            predicted_prefix_executable_wrench_world=prefix_command,
            predicted_prefix_robot_cuff_position_world_m=prefix_position,
            predicted_prefix_robot_cuff_rotation_world=prefix_rotation,
            predicted_prefix_robot_cuff_linear_velocity_world_m_s=prefix_linear,
            predicted_prefix_robot_cuff_angular_velocity_world_rad_s=prefix_angular,
            predicted_prefix_physical_cuff_wrench_world=prefix_wrench,
            predicted_prefix_robot_q_rad=prefix_robot_q,
            predicted_prefix_robot_dq_rad_s=prefix_robot_dq,
            prediction_supported=supported,
        )

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        actions = np.asarray(actions_nm, dtype=float)
        allow_cached_subset = self._reuse_cached_subsets or len(actions) == 1
        cached = self._cached_prediction_for_actions(actions) if allow_cached_subset else None
        if cached is not None:
            self._last_actions = actions.copy()
            self._last_prediction = cached
            return cached
        prediction = self._rigid_body_prediction(
            actions, self.executable_preview(actions)
        )
        self._last_actions = actions.copy()
        self._last_prediction = prediction
        self._screen_cache.append((actions.copy(), prediction))
        if len(self._screen_cache) > 4:
            self._screen_cache.pop(0)
        return prediction


__all__ = [
    "CR12_RIGID_BODY_PREDICTOR_VERSION",
    "CR12_RIGID_BODY_PREFIX_TIMES_S",
    "CR12RigidBodyFirstActionBatchPreview",
    "CR12RigidBodyPredictionContract",
    "CR12RigidBodyPredictionState",
]
