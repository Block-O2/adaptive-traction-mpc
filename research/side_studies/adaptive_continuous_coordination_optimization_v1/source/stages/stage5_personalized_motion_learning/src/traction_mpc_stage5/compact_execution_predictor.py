"""Shadow-only compact command-to-cuff closed-loop predictor.

The authoritative predictor remains unchanged.  This module implements one
bounded 20 ms cuff-space model for engineering evaluation through the existing
first-action preview protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from scipy.spatial.transform import Rotation

from .acceleration_semantics import screen_cumulative_prefix_acceleration
from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    EstimatedInterfaceState,
    InterfaceAwareFirstActionBatchPreview,
    InterfaceHoldPredictionBatch,
)


COMPACT_EXECUTION_PREDICTOR_VERSION = "compact_closed_loop_execution_v1"
COMPACT_PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])


def _finite(name: str, value: Any, shape: tuple[int, ...]) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result.copy()


@dataclass(frozen=True)
class CompactRobotCuffState:
    """Deployable robot-cuff state at the prediction timestamp."""

    position_world_m: np.ndarray
    rotation_world: np.ndarray
    linear_velocity_world_m_s: np.ndarray
    angular_velocity_world_rad_s: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "position_world_m",
            _finite("position_world_m", self.position_world_m, (3,)),
        )
        object.__setattr__(
            self,
            "rotation_world",
            _finite("rotation_world", self.rotation_world, (3, 3)),
        )
        object.__setattr__(
            self,
            "linear_velocity_world_m_s",
            _finite(
                "linear_velocity_world_m_s", self.linear_velocity_world_m_s, (3,)
            ),
        )
        object.__setattr__(
            self,
            "angular_velocity_world_rad_s",
            _finite(
                "angular_velocity_world_rad_s",
                self.angular_velocity_world_rad_s,
                (3,),
            ),
        )
        if not np.allclose(
            self.rotation_world.T @ self.rotation_world,
            np.eye(3),
            atol=1.0e-7,
            rtol=0.0,
        ) or np.linalg.det(self.rotation_world) <= 0.0:
            raise ValueError("rotation_world must be a proper rotation")


@dataclass(frozen=True)
class CompactCuffResponseModelV1:
    """Six independent affine 5 ms cuff-twist transitions."""

    coefficients: np.ndarray
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    feature_min: np.ndarray
    feature_max: np.ndarray
    acceleration_margin_rad_s2: np.ndarray
    ridge: float
    fit_sample_count: int
    development_group_ids: tuple[str, ...]
    calibration_group_ids: tuple[str, ...]
    version: str = COMPACT_EXECUTION_PREDICTOR_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "coefficients", _finite("coefficients", self.coefficients, (6, 4))
        )
        for name in ("feature_mean", "feature_scale", "feature_min", "feature_max"):
            object.__setattr__(
                self, name, _finite(name, getattr(self, name), (6, 3))
            )
        object.__setattr__(
            self,
            "acceleration_margin_rad_s2",
            _finite(
                "acceleration_margin_rad_s2",
                self.acceleration_margin_rad_s2,
                (2,),
            ),
        )
        if np.any(self.feature_scale <= 0.0):
            raise ValueError("feature scales must be positive")
        if np.any(self.feature_min > self.feature_max):
            raise ValueError("feature support bounds are reversed")
        if np.any(self.acceleration_margin_rad_s2 < 0.0):
            raise ValueError("acceleration margin must be nonnegative")
        if not np.isfinite(self.ridge) or self.ridge < 0.0:
            raise ValueError("ridge must be finite and nonnegative")
        if self.fit_sample_count < 1:
            raise ValueError("fit sample count must be positive")
        if self.version != COMPACT_EXECUTION_PREDICTOR_VERSION:
            raise ValueError("compact predictor version mismatch")

    @staticmethod
    def feature_matrix(
        twist_world: np.ndarray,
        command_wrench_world: np.ndarray,
        physical_robot_site_wrench_world: np.ndarray,
        previous_command_wrench_world: np.ndarray,
    ) -> np.ndarray:
        twist = np.asarray(twist_world, dtype=float)
        command = np.asarray(command_wrench_world, dtype=float)
        physical = np.asarray(physical_robot_site_wrench_world, dtype=float)
        previous = np.asarray(previous_command_wrench_world, dtype=float)
        if not (
            twist.shape == command.shape == physical.shape == previous.shape
            and twist.ndim == 2
            and twist.shape[1] == 6
        ):
            raise ValueError("compact predictor inputs must be aligned Nx6 arrays")
        return np.stack([twist, command - physical, command - previous], axis=2)

    def predict_twist_increment(
        self,
        twist_world: np.ndarray,
        command_wrench_world: np.ndarray,
        physical_robot_site_wrench_world: np.ndarray,
        previous_command_wrench_world: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        features = self.feature_matrix(
            twist_world,
            command_wrench_world,
            physical_robot_site_wrench_world,
            previous_command_wrench_world,
        )
        normalized = (features - self.feature_mean[None, :, :]) / self.feature_scale[
            None, :, :
        ]
        design = np.concatenate(
            [np.ones(features.shape[:2] + (1,)), normalized], axis=2
        )
        increment = np.einsum("nif,if->ni", design, self.coefficients)
        supported = np.all(
            (features >= self.feature_min[None, :, :] - 1.0e-12)
            & (features <= self.feature_max[None, :, :] + 1.0e-12),
            axis=(1, 2),
        )
        supported &= np.all(np.isfinite(features), axis=(1, 2))
        return increment, supported

    def with_margin_and_support(
        self,
        *,
        acceleration_margin_rad_s2: Sequence[float],
        feature_min: np.ndarray,
        feature_max: np.ndarray,
        calibration_group_ids: Sequence[str],
    ) -> "CompactCuffResponseModelV1":
        return replace(
            self,
            acceleration_margin_rad_s2=np.asarray(
                acceleration_margin_rad_s2, dtype=float
            ),
            feature_min=np.asarray(feature_min, dtype=float),
            feature_max=np.asarray(feature_max, dtype=float),
            calibration_group_ids=tuple(str(value) for value in calibration_group_ids),
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "coefficients": self.coefficients.tolist(),
            "feature_mean": self.feature_mean.tolist(),
            "feature_scale": self.feature_scale.tolist(),
            "feature_min": self.feature_min.tolist(),
            "feature_max": self.feature_max.tolist(),
            "acceleration_margin_rad_s2": self.acceleration_margin_rad_s2.tolist(),
            "ridge": self.ridge,
            "fit_sample_count": self.fit_sample_count,
            "development_group_ids": list(self.development_group_ids),
            "calibration_group_ids": list(self.calibration_group_ids),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "CompactCuffResponseModelV1":
        return cls(
            coefficients=np.asarray(record["coefficients"], dtype=float),
            feature_mean=np.asarray(record["feature_mean"], dtype=float),
            feature_scale=np.asarray(record["feature_scale"], dtype=float),
            feature_min=np.asarray(record["feature_min"], dtype=float),
            feature_max=np.asarray(record["feature_max"], dtype=float),
            acceleration_margin_rad_s2=np.asarray(
                record["acceleration_margin_rad_s2"], dtype=float
            ),
            ridge=float(record["ridge"]),
            fit_sample_count=int(record["fit_sample_count"]),
            development_group_ids=tuple(record["development_group_ids"]),
            calibration_group_ids=tuple(record["calibration_group_ids"]),
            version=str(record["version"]),
        )

    @classmethod
    def load(cls, path: Path) -> "CompactCuffResponseModelV1":
        return cls.from_record(json.loads(Path(path).read_text(encoding="utf-8")))


def fit_compact_cuff_response_model(
    *,
    features: np.ndarray,
    target_twist_increment: np.ndarray,
    ridge: float,
    development_group_ids: Sequence[str],
) -> CompactCuffResponseModelV1:
    """Fit only the single declared diagonal affine transition."""

    values = np.asarray(features, dtype=float)
    target = np.asarray(target_twist_increment, dtype=float)
    if values.ndim != 3 or values.shape[1:] != (6, 3):
        raise ValueError("fit features must have shape Nx6x3")
    if target.shape != (len(values), 6):
        raise ValueError("fit target must have shape Nx6")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(target)):
        raise ValueError("fit data must be finite")
    if ridge < 0.0 or not np.isfinite(ridge):
        raise ValueError("ridge must be finite and nonnegative")
    mean = np.mean(values, axis=0)
    scale = np.std(values, axis=0)
    scale = np.maximum(scale, 1.0e-9)
    normalized = (values - mean[None, :, :]) / scale[None, :, :]
    coefficients = np.empty((6, 4), dtype=float)
    penalty = np.eye(4) * ridge
    penalty[0, 0] = 0.0
    for axis in range(6):
        design = np.column_stack([np.ones(len(values)), normalized[:, axis, :]])
        coefficients[axis] = np.linalg.solve(
            design.T @ design + penalty, design.T @ target[:, axis]
        )
    return CompactCuffResponseModelV1(
        coefficients=coefficients,
        feature_mean=mean,
        feature_scale=scale,
        feature_min=np.min(values, axis=0),
        feature_max=np.max(values, axis=0),
        acceleration_margin_rad_s2=np.zeros(2),
        ridge=float(ridge),
        fit_sample_count=len(values),
        development_group_ids=tuple(str(value) for value in development_group_ids),
        calibration_group_ids=(),
    )


class CompactClosedLoopFirstActionBatchPreview(
    InterfaceAwareFirstActionBatchPreview
):
    """Protocol-compatible shadow preview for the compact 20 ms model."""

    def __init__(
        self,
        *args: Any,
        compact_model: CompactCuffResponseModelV1,
        robot_cuff_state: CompactRobotCuffState,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.compact_model = compact_model
        if not isinstance(robot_cuff_state, CompactRobotCuffState):
            raise TypeError("compact predictor requires CompactRobotCuffState")
        self.robot_cuff_state = robot_cuff_state

    @staticmethod
    def _human_pose_batch(
        states: np.ndarray, geometry: Any
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        state = np.asarray(states, dtype=float)
        q1 = state[:, 0]
        q2 = state[:, 1]
        dq = state[:, 2:]
        phi = q1 - q2
        plane_x = np.asarray(geometry.plane_x_world)
        plane_z = np.asarray(geometry.plane_z_world)
        axis = np.asarray(geometry.joint_axis_world)
        hip = np.asarray(geometry.origin_world_m) + (
            geometry.hip_plane_m[0] * plane_x
            + geometry.hip_plane_m[1] * plane_z
        )
        positions = (
            hip[None, :]
            + geometry.thigh_length_m
            * (
                np.cos(q1)[:, None] * plane_x
                + np.sin(q1)[:, None] * plane_z
            )
            + geometry.cuff_distance_m
            * (
                np.cos(phi)[:, None] * plane_x
                + np.sin(phi)[:, None] * plane_z
            )
        )
        jacobian, rotations = InterfaceAwareFirstActionBatchPreview._geometry_batch(
            state[:, :2], geometry
        )
        linear = np.einsum("nki,ni->nk", jacobian, dq)
        angular = axis[None, :] * (dq[:, 1] - dq[:, 0])[:, None]
        return positions, rotations, linear, angular, jacobian

    @staticmethod
    def _initial_robot_cuff_state(
        interface_state: EstimatedInterfaceState,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        p = CONTROLLER_NOMINAL_INTERFACE
        human_rotation = np.asarray(interface_state.human_rotation_world, dtype=float)
        relative_translation = np.asarray(p.rest_translation_human_m) + np.asarray(
            interface_state.displacement_human_m
        )
        r_world = human_rotation @ relative_translation
        relative_rotation = Rotation.from_rotvec(
            np.asarray(p.rest_rotation_rotvec_human_rad)
            + np.asarray(interface_state.rotation_error_human_rad)
        ).as_matrix()
        position = np.asarray(interface_state.human_position_world_m) + r_world
        rotation = human_rotation @ relative_rotation
        linear = (
            np.asarray(interface_state.human_velocity_world_m_s)
            + np.cross(
                np.asarray(interface_state.human_angular_velocity_world_rad_s),
                r_world,
            )
            + human_rotation @ np.asarray(interface_state.velocity_human_m_s)
        )
        angular = (
            np.asarray(interface_state.human_angular_velocity_world_rad_s)
            + human_rotation
            @ np.asarray(interface_state.angular_velocity_human_rad_s)
        )
        return position, rotation, linear, angular

    def _interface_state_and_wrench(
        self,
        human_states: np.ndarray,
        robot_position: np.ndarray,
        robot_rotation: np.ndarray,
        robot_linear: np.ndarray,
        robot_angular: np.ndarray,
    ) -> tuple[np.ndarray, ...]:
        p = CONTROLLER_NOMINAL_INTERFACE
        human_position, human_rotation, human_linear, human_angular, jacobian = (
            self._human_pose_batch(human_states, self.human_model.geometry)
        )
        r_world = robot_position - human_position
        x = np.einsum("nji,nj->ni", human_rotation, r_world)
        relative_rotation = np.einsum(
            "nji,njk->nik", human_rotation, robot_rotation
        )
        theta = Rotation.from_matrix(relative_rotation).as_rotvec()
        u = np.einsum(
            "nji,nj->ni",
            human_rotation,
            robot_linear - human_linear - np.cross(human_angular, r_world),
        )
        omega = np.einsum(
            "nji,nj->ni", human_rotation, robot_angular - human_angular
        )
        rest_x = np.asarray(p.rest_translation_human_m)
        rest_theta = np.asarray(p.rest_rotation_rotvec_human_rad)
        force_h = (
            np.asarray(p.translation_stiffness_n_m) * (x - rest_x)
            + np.asarray(p.translation_damping_ns_m) * u
        )
        couple_h = (
            p.rotation_stiffness_nm_rad * (theta - rest_theta)
            + p.rotation_damping_nms_rad * omega
        )
        moment_h = couple_h + np.cross(x, force_h)
        force_world = np.einsum("nij,nj->ni", human_rotation, force_h)
        moment_world = np.einsum("nij,nj->ni", human_rotation, moment_h)
        wrench = np.concatenate([force_world, moment_world], axis=1)
        return x, u, theta, omega, wrench, human_rotation, jacobian, r_world

    @staticmethod
    def _human_action_from_wrench(
        wrench: np.ndarray, jacobian: np.ndarray, joint_axis_world: np.ndarray
    ) -> np.ndarray:
        force_tau = np.einsum("nki,nk->ni", jacobian, wrench[:, :3])
        moment_axis = wrench[:, 3:] @ np.asarray(joint_axis_world)
        return force_tau + np.column_stack([-moment_axis, moment_axis])

    def _human_step(
        self, states: np.ndarray, actions_nm: np.ndarray, dt_s: float
    ) -> np.ndarray:
        dynamics = self._prefix_human_continuous_dynamics
        if dynamics is None:
            raise RuntimeError("compact predictor has no fixed Human dynamics binding")

        def evaluate(value: np.ndarray) -> np.ndarray:
            return np.asarray(dynamics(value, actions_nm, self.human_model), dtype=float)

        k1 = evaluate(states)
        k2 = evaluate(states + 0.5 * dt_s * k1)
        k3 = evaluate(states + 0.5 * dt_s * k2)
        k4 = evaluate(states + dt_s * k3)
        return states + dt_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

    @staticmethod
    def _robot_site_wrench(wrench_human_site: np.ndarray, r_world: np.ndarray) -> np.ndarray:
        result = np.asarray(wrench_human_site, dtype=float).copy()
        result[:, 3:] -= np.cross(r_world, result[:, :3])
        return result

    def _compact_prediction(
        self, actions_nm: np.ndarray, executable_batch: Any
    ) -> InterfaceHoldPredictionBatch:
        if (
            self.state_rad_rad_s is None
            or self.acceleration_limits_rad_s2 is None
            or self._prefix_support_provider is None
            or self._prefix_future_command_resolver is None
        ):
            raise RuntimeError("compact predictor is missing prefix bindings")
        actions = np.asarray(actions_nm, dtype=float)
        count = len(actions)
        states = np.broadcast_to(self.state_rad_rad_s, (count, 4)).copy()
        initial_dq = states[:, 2:].copy()
        initial_robot = self.robot_cuff_state
        robot_position = np.broadcast_to(
            initial_robot.position_world_m, (count, 3)
        ).copy()
        robot_rotation = np.broadcast_to(
            initial_robot.rotation_world, (count, 3, 3)
        ).copy()
        robot_linear = np.broadcast_to(
            initial_robot.linear_velocity_world_m_s, (count, 3)
        ).copy()
        robot_angular = np.broadcast_to(
            initial_robot.angular_velocity_world_rad_s, (count, 3)
        ).copy()
        command = np.column_stack(
            [executable_batch.force_total_n, executable_batch.moment_total_nm]
        )
        previous_command = np.broadcast_to(
            self.predictor.previous_executable_wrench_world, (count, 6)
        ).copy()
        physical_wrench = np.broadcast_to(
            np.concatenate(
                [
                    np.asarray(self.interface_state.measured_force_world_n),
                    np.asarray(self.interface_state.measured_moment_world_nm),
                ]
            ),
            (count, 6),
        ).copy()

        prefix_states = np.empty((count, 4, 4), dtype=float)
        prefix_x = np.empty((count, 4, 3), dtype=float)
        prefix_u = np.empty_like(prefix_x)
        prefix_theta = np.empty_like(prefix_x)
        prefix_omega = np.empty_like(prefix_x)
        prefix_command = np.empty((count, 4, 6), dtype=float)
        prefix_position = np.empty((count, 4, 3), dtype=float)
        prefix_rotation = np.empty((count, 4, 3, 3), dtype=float)
        prefix_linear = np.empty((count, 4, 3), dtype=float)
        prefix_angular = np.empty((count, 4, 3), dtype=float)
        prefix_wrench = np.empty((count, 4, 6), dtype=float)
        supported = np.ones(count, dtype=bool)
        dt_s = 0.005

        for segment in range(4):
            current_twist = np.concatenate([robot_linear, robot_angular], axis=1)
            x, u, theta, omega, computed_wrench, human_rotation, jacobian, r_world = (
                self._interface_state_and_wrench(
                    states,
                    robot_position,
                    robot_rotation,
                    robot_linear,
                    robot_angular,
                )
            )
            if segment > 0:
                physical_wrench = computed_wrench
            physical_robot = self._robot_site_wrench(physical_wrench, r_world)
            delta_twist, segment_supported = self.compact_model.predict_twist_increment(
                current_twist, command, physical_robot, previous_command
            )
            supported &= segment_supported
            next_twist = current_twist + delta_twist
            average_linear = 0.5 * (robot_linear + next_twist[:, :3])
            average_angular = 0.5 * (robot_angular + next_twist[:, 3:])
            next_position = robot_position + dt_s * average_linear
            next_rotation = np.empty_like(robot_rotation)
            for candidate in range(count):
                next_rotation[candidate] = (
                    Rotation.from_rotvec(dt_s * average_angular[candidate]).as_matrix()
                    @ robot_rotation[candidate]
                )

            next_states = states.copy()
            endpoint = None
            for _ in range(2):
                endpoint = self._interface_state_and_wrench(
                    next_states,
                    next_position,
                    next_rotation,
                    next_twist[:, :3],
                    next_twist[:, 3:],
                )
                endpoint_wrench = endpoint[4]
                mean_wrench = 0.5 * (physical_wrench + endpoint_wrench)
                mean_action = self._human_action_from_wrench(
                    mean_wrench,
                    jacobian,
                    np.asarray(self.human_model.geometry.joint_axis_world),
                )
                next_states = self._human_step(states, mean_action, dt_s)
            endpoint = self._interface_state_and_wrench(
                next_states,
                next_position,
                next_rotation,
                next_twist[:, :3],
                next_twist[:, 3:],
            )
            x_next, u_next, theta_next, omega_next, endpoint_wrench, next_human_rotation, next_jacobian, _ = endpoint

            prefix_states[:, segment] = next_states
            prefix_x[:, segment] = x_next
            prefix_u[:, segment] = u_next
            prefix_theta[:, segment] = theta_next
            prefix_omega[:, segment] = omega_next
            prefix_command[:, segment] = command
            prefix_position[:, segment] = next_position
            prefix_rotation[:, segment] = next_rotation
            prefix_linear[:, segment] = next_twist[:, :3]
            prefix_angular[:, segment] = next_twist[:, 3:]
            prefix_wrench[:, segment] = endpoint_wrench

            states = next_states
            robot_position = next_position
            robot_rotation = next_rotation
            robot_linear = next_twist[:, :3]
            robot_angular = next_twist[:, 3:]
            physical_wrench = endpoint_wrench
            previous_command = command
            if segment == 3:
                continue
            support_action = np.asarray(
                self._prefix_support_provider(states), dtype=float
            )
            requested_wrench = self._allocate_varying_q_batch(actions, states[:, :2])
            support_wrench = self._allocate_varying_q_batch(
                support_action, states[:, :2]
            )
            command = np.asarray(
                self._prefix_future_command_resolver(
                    states,
                    actions,
                    requested_wrench,
                    interface_displacement_human_m=x_next,
                    interface_velocity_human_m_s=u_next,
                    interface_rotation_human_rad=theta_next,
                    interface_angular_velocity_human_rad_s=omega_next,
                    human_rotation_world=next_human_rotation,
                    support_human_wrenches_world=support_wrench,
                ),
                dtype=float,
            )

        acceleration = screen_cumulative_prefix_acceleration(
            initial_dq,
            prefix_states[..., 2:],
            COMPACT_PREFIX_TIMES_S,
            self.acceleration_limits_rad_s2,
        )
        qualified_margin = (
            self.acceleration_limits_rad_s2[None, None, :]
            - np.abs(acceleration.acceleration_rad_s2)
            - self.compact_model.acceleration_margin_rad_s2[None, None, :]
        )
        qualified_acceleration_feasible = np.all(qualified_margin >= -1.0e-12, axis=(1, 2))
        force_norm = np.linalg.norm(prefix_wrench[..., :3], axis=2)
        moment_norm = np.linalg.norm(prefix_wrench[..., 3:], axis=2)
        peak_force = np.max(force_norm, axis=1)
        peak_moment = np.max(moment_norm, axis=1)
        force_margin = self.predictor.planning_force_ceiling_n - peak_force
        feasible = (
            np.asarray(executable_batch.feasible, dtype=bool)
            & supported
            & qualified_acceleration_feasible
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
                "compact_closed_loop_v1_cumulative_prefix_5_10_15_20ms"
            ),
            prefix_times_s=COMPACT_PREFIX_TIMES_S.copy(),
            predicted_prefix_states_rad_rad_s=prefix_states,
            predicted_prefix_acceleration_rad_s2=acceleration.acceleration_rad_s2,
            prefix_acceleration_margin_rad_s2=qualified_margin,
            prefix_acceleration_feasible=qualified_acceleration_feasible,
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
            compact_model_supported=supported,
        )

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        actions = np.asarray(actions_nm, dtype=float)
        allow_cached_subset = self._reuse_cached_subsets or len(actions) == 1
        cached = self._cached_prediction_for_actions(actions) if allow_cached_subset else None
        if cached is not None:
            self._last_actions = actions.copy()
            self._last_prediction = cached
            return cached
        prediction = self._compact_prediction(actions, self.executable_preview(actions))
        self._last_actions = actions.copy()
        self._last_prediction = prediction
        self._screen_cache.append((actions.copy(), prediction))
        if len(self._screen_cache) > 4:
            self._screen_cache.pop(0)
        return prediction


__all__ = [
    "COMPACT_EXECUTION_PREDICTOR_VERSION",
    "COMPACT_PREFIX_TIMES_S",
    "CompactCuffResponseModelV1",
    "CompactClosedLoopFirstActionBatchPreview",
    "CompactRobotCuffState",
    "fit_compact_cuff_response_model",
]
