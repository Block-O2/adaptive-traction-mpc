"""Controller-owned nominal cuff interface observer and hold predictor.

This module deliberately does not import Stage-5 plant mechanics.  Its inputs
are deployable robot-side pose/twist and cuff-wrench measurements plus an
independent nominal parameter record.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.executable_command import (
    ExecutableCommandBatchPreview,
    ExecutableCommandPreview,
)

from .config import STAGE5_ROOT
from .task_observation import ControllerTaskObservation, make_task_observation


CONTROLLER_INTERFACE_CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_controller_nominal_interface_v1.json"
)
INTERFACE_AWARE_ESTIMATOR_Q_DQ = (
    "deployable_interface_observer_from_robot_pose_twist_and_cuff_wrench"
)


def _tuple3(name: str, value: Any, *, positive: bool = False) -> tuple[float, float, float]:
    array = np.asarray(value, dtype=float)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite three-vector")
    if positive and np.any(array <= 0.0):
        raise ValueError(f"{name} must be strictly positive")
    return tuple(float(item) for item in array)


@dataclass(frozen=True)
class ControllerNominalInterfaceParameters:
    """Immutable controller nominal model, separate from plant truth."""

    model_version: str
    translation_stiffness_n_m: tuple[float, float, float]
    translation_damping_ns_m: tuple[float, float, float]
    rotation_stiffness_nm_rad: float
    rotation_damping_nms_rad: float
    rest_translation_human_m: tuple[float, float, float]
    rest_rotation_rotvec_human_rad: tuple[float, float, float]
    translation_effective_mass_kg: tuple[float, float, float]
    rotation_effective_inertia_kg_m2: float
    prediction_substep_s: float
    observer_fixed_point_iterations: int
    engineering_force_gate_n: float
    provisional_not_hardware_calibrated: bool = True

    def __post_init__(self) -> None:
        if not self.model_version:
            raise ValueError("model_version must be non-empty")
        for name in (
            "translation_stiffness_n_m",
            "translation_damping_ns_m",
            "translation_effective_mass_kg",
        ):
            object.__setattr__(self, name, _tuple3(name, getattr(self, name), positive=True))
        for name in ("rest_translation_human_m", "rest_rotation_rotvec_human_rad"):
            object.__setattr__(self, name, _tuple3(name, getattr(self, name)))
        for name in (
            "rotation_stiffness_nm_rad",
            "rotation_damping_nms_rad",
            "rotation_effective_inertia_kg_m2",
            "prediction_substep_s",
            "engineering_force_gate_n",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if int(self.observer_fixed_point_iterations) < 1:
            raise ValueError("observer_fixed_point_iterations must be positive")
        object.__setattr__(
            self, "observer_fixed_point_iterations", int(self.observer_fixed_point_iterations)
        )
        if self.provisional_not_hardware_calibrated is not True:
            raise ValueError("controller nominal interface must remain labeled provisional")


def load_controller_nominal_interface(
    path: Path = CONTROLLER_INTERFACE_CONFIG_PATH,
) -> ControllerNominalInterfaceParameters:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_controller_nominal_interface_v1":
        raise ValueError("unexpected controller nominal interface schema")
    return ControllerNominalInterfaceParameters(
        model_version=str(payload["model_version"]),
        translation_stiffness_n_m=payload["translation_stiffness_n_m"],
        translation_damping_ns_m=payload["translation_damping_ns_m"],
        rotation_stiffness_nm_rad=payload["rotation_stiffness_nm_rad"],
        rotation_damping_nms_rad=payload["rotation_damping_nms_rad"],
        rest_translation_human_m=payload["rest_translation_human_m"],
        rest_rotation_rotvec_human_rad=payload["rest_rotation_rotvec_human_rad"],
        translation_effective_mass_kg=payload["translation_effective_mass_kg"],
        rotation_effective_inertia_kg_m2=payload["rotation_effective_inertia_kg_m2"],
        prediction_substep_s=payload["prediction_substep_s"],
        observer_fixed_point_iterations=payload["observer_fixed_point_iterations"],
        engineering_force_gate_n=payload["engineering_force_gate_n"],
        provisional_not_hardware_calibrated=payload[
            "provisional_not_hardware_calibrated"
        ],
    )


CONTROLLER_NOMINAL_INTERFACE = load_controller_nominal_interface()


@dataclass(frozen=True)
class EstimatedInterfaceState:
    sample_timestamp_s: float
    displacement_human_m: np.ndarray
    velocity_human_m_s: np.ndarray
    rotation_error_human_rad: np.ndarray
    angular_velocity_human_rad_s: np.ndarray
    human_position_world_m: np.ndarray
    human_rotation_world: np.ndarray
    human_velocity_world_m_s: np.ndarray
    human_angular_velocity_world_rad_s: np.ndarray
    measured_force_world_n: np.ndarray
    measured_moment_world_nm: np.ndarray


class InterfaceAwareHumanStateObserver:
    """Causal inversion of a nominal Kelvin--Voigt interface measurement."""

    def __init__(
        self,
        parameters: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
    ) -> None:
        self.parameters = parameters
        self._last: EstimatedInterfaceState | None = None

    @property
    def last_interface_state(self) -> EstimatedInterfaceState | None:
        return self._last

    def reset(self) -> None:
        self._last = None

    def update(
        self,
        measurement: Any,
        human_model: Any,
        *,
        human_model_version: str,
    ) -> tuple[ControllerTaskObservation, EstimatedInterfaceState]:
        timestamp = float(measurement.sample_time_s)
        if self._last is not None and timestamp < self._last.sample_timestamp_s - 1.0e-12:
            raise ValueError("interface observer received a noncausal timestamp")
        if self._last is not None and abs(timestamp - self._last.sample_timestamp_s) <= 1.0e-12:
            interface = self._last
        else:
            interface = self._invert_measurement(measurement, timestamp)
            self._last = interface
        state = human_model.geometry.estimate_state(
            interface.human_position_world_m,
            interface.human_rotation_world,
            interface.human_velocity_world_m_s,
            interface.human_angular_velocity_world_rad_s,
        )
        observation = make_task_observation(
            state,
            sample_timestamp_s=timestamp,
            controller_timestamp_s=float(measurement.arrival_time_s),
            human_model_version=human_model_version,
        )
        return observation, interface

    def _invert_measurement(self, measurement: Any, timestamp: float) -> EstimatedInterfaceState:
        p = self.parameters
        k = np.asarray(p.translation_stiffness_n_m)
        d = np.asarray(p.translation_damping_ns_m)
        x0 = np.asarray(p.rest_translation_human_m)
        theta0 = np.asarray(p.rest_rotation_rotvec_human_rad)
        force_world = np.asarray(measurement.cuff_force_vector_n, dtype=float)
        moment_world = np.asarray(measurement.cuff_moment_vector_nm, dtype=float)
        robot_position = np.asarray(measurement.attachment_position_m, dtype=float)
        robot_rotation = np.asarray(measurement.attachment_rotation_matrix, dtype=float)
        robot_velocity = np.asarray(measurement.attachment_velocity_m_s, dtype=float)
        robot_omega = np.asarray(measurement.attachment_angular_velocity_rad_s, dtype=float)
        if self._last is None:
            dt = None
            x_previous = x0.copy()
            theta_previous = theta0.copy()
        else:
            dt = timestamp - self._last.sample_timestamp_s
            if dt <= 0.0:
                raise ValueError("interface observer requires increasing sample timestamps")
            x_previous = self._last.displacement_human_m
            theta_previous = self._last.rotation_error_human_rad

        theta = theta_previous.copy()
        x = x_previous.copy()
        for _ in range(p.observer_fixed_point_iterations):
            relative_rotation = Rotation.from_rotvec(theta + theta0).as_matrix()
            human_rotation = robot_rotation @ relative_rotation.T
            force_human = human_rotation.T @ force_world
            if dt is None:
                x = x0 + force_human / k
                velocity = np.zeros(3)
            else:
                x = (force_human + d * x_previous / dt + k * x0) / (k + d / dt)
                velocity = (x - x_previous) / dt
            r_world = human_rotation @ (x + x0)
            pure_couple_world = moment_world - np.cross(r_world, force_world)
            couple_human = human_rotation.T @ pure_couple_world
            if dt is None:
                theta = theta0 + couple_human / p.rotation_stiffness_nm_rad
                angular_velocity = np.zeros(3)
            else:
                theta = (
                    couple_human
                    + p.rotation_damping_nms_rad * theta_previous / dt
                    + p.rotation_stiffness_nm_rad * theta0
                ) / (
                    p.rotation_stiffness_nm_rad
                    + p.rotation_damping_nms_rad / dt
                )
                angular_velocity = (theta - theta_previous) / dt

        relative_rotation = Rotation.from_rotvec(theta + theta0).as_matrix()
        human_rotation = robot_rotation @ relative_rotation.T
        r_world = human_rotation @ (x + x0)
        human_omega = robot_omega - human_rotation @ angular_velocity
        human_velocity = (
            robot_velocity
            - np.cross(human_omega, r_world)
            - human_rotation @ velocity
        )
        return EstimatedInterfaceState(
            sample_timestamp_s=timestamp,
            displacement_human_m=x.copy(),
            velocity_human_m_s=velocity.copy(),
            rotation_error_human_rad=theta.copy(),
            angular_velocity_human_rad_s=angular_velocity.copy(),
            human_position_world_m=(robot_position - r_world).copy(),
            human_rotation_world=human_rotation.copy(),
            human_velocity_world_m_s=human_velocity.copy(),
            human_angular_velocity_world_rad_s=human_omega.copy(),
            measured_force_world_n=force_world.copy(),
            measured_moment_world_nm=moment_world.copy(),
        )


@dataclass(frozen=True)
class InterfaceHoldPredictionBatch:
    executable_batch: ExecutableCommandBatchPreview
    feasible: np.ndarray
    predicted_peak_force_n: np.ndarray
    predicted_endpoint_force_world_n: np.ndarray
    predicted_mean_force_world_n: np.ndarray
    predicted_peak_moment_nm: np.ndarray
    predicted_endpoint_moment_world_nm: np.ndarray
    predicted_mean_moment_world_nm: np.ndarray
    margin_to_physical_force_gate_n: np.ndarray

    def command(self, index: int) -> ExecutableCommandPreview:
        return self.executable_batch.command(index)


@dataclass(frozen=True)
class InterfaceHorizonPredictionBatch:
    """Vectorized coupled Human/interface prediction for a CEM population."""

    predicted_human_states: np.ndarray
    requested_cuff_wrench_world: np.ndarray
    allocated_force_norm_n: np.ndarray
    transmitted_mean_wrench_world: np.ndarray
    predicted_peak_force_n: np.ndarray
    predicted_peak_moment_nm: np.ndarray
    interface_displacement_human_m: np.ndarray
    interface_velocity_human_m_s: np.ndarray
    interface_rotation_error_human_rad: np.ndarray
    interface_angular_velocity_human_rad_s: np.ndarray
    base_drive_world_n: np.ndarray
    base_angular_drive_world_nm: np.ndarray
    executable_wrench_world: np.ndarray
    timing_s: dict[str, float] | None = None


@dataclass(frozen=True)
class ExplicitInterfacePredictionState:
    """Complete controller-side state needed to continue interface prediction."""

    sample_timestamp_s: float
    displacement_human_m: np.ndarray
    velocity_human_m_s: np.ndarray
    rotation_error_human_rad: np.ndarray
    angular_velocity_human_rad_s: np.ndarray
    human_rotation_world: np.ndarray
    base_drive_world_n: np.ndarray
    base_angular_drive_world_nm: np.ndarray
    previous_executable_wrench_world: np.ndarray
    model_version: str
    transition_assumption: str = "zero_order_hold_plus_executable_wrench_increment"


class NominalInterfaceHoldPredictor:
    """Batch nominal interface propagation over one executable action hold."""

    def __init__(
        self,
        parameters: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
        *,
        control_dt_s: float = 0.005,
    ) -> None:
        self.parameters = parameters
        self.control_dt_s = float(control_dt_s)
        ratio = self.control_dt_s / parameters.prediction_substep_s
        self.substeps = int(round(ratio))
        if self.substeps < 1 or not np.isclose(ratio, self.substeps, atol=1.0e-12):
            raise ValueError("prediction substep must divide the control period")
        self._state: ExplicitInterfacePredictionState | None = None
        p = self.parameters
        self._translation_step_powers = self._semi_implicit_step_powers(
            np.asarray(p.translation_stiffness_n_m),
            np.asarray(p.translation_damping_ns_m),
            np.asarray(p.translation_effective_mass_kg),
            p.prediction_substep_s,
            self.substeps,
        )
        self._rotation_step_powers = self._semi_implicit_step_powers(
            np.full(3, p.rotation_stiffness_nm_rad),
            np.full(3, p.rotation_damping_nms_rad),
            np.full(3, p.rotation_effective_inertia_kg_m2),
            p.prediction_substep_s,
            self.substeps,
        )

    @staticmethod
    def _semi_implicit_step_powers(
        stiffness: np.ndarray,
        damping: np.ndarray,
        mass: np.ndarray,
        dt: float,
        substeps: int,
    ) -> np.ndarray:
        """Precompute exact powers of the existing semi-implicit step."""

        step = np.empty((3, 2, 2), dtype=float)
        step[:, 0, 0] = 1.0 - dt**2 * stiffness / mass
        step[:, 0, 1] = dt * (1.0 - dt * damping / mass)
        step[:, 1, 0] = -dt * stiffness / mass
        step[:, 1, 1] = 1.0 - dt * damping / mass
        return np.stack(
            [
                np.stack(
                    [np.linalg.matrix_power(step[axis], index + 1) for axis in range(3)]
                )
                for index in range(substeps)
            ]
        )

    @staticmethod
    def _constant_drive_trace(
        position: np.ndarray,
        velocity: np.ndarray,
        drive: np.ndarray,
        stiffness: np.ndarray,
        rest: np.ndarray,
        step_powers: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorize all substeps of the unchanged constant-drive recurrence."""

        equilibrium = drive / stiffness + rest
        initial_delta = np.stack([position - equilibrium, velocity], axis=-1)
        trace = np.einsum("sdij,ndj->nsdi", step_powers, initial_delta)
        trace[..., 0] += equilibrium[:, None, :]
        return trace[..., 0], trace[..., 1]

    @property
    def explicit_state(self) -> ExplicitInterfacePredictionState | None:
        return self._state

    @property
    def previous_executable_wrench_world(self) -> np.ndarray:
        return (
            np.zeros(6)
            if self._state is None
            else self._state.previous_executable_wrench_world.copy()
        )

    def _initialize_state(
        self,
        interface_state: EstimatedInterfaceState,
        previous_executable_wrench_world: np.ndarray,
    ) -> ExplicitInterfacePredictionState:
        """Initialize once from the deployable measured spring-damper state."""

        p = self.parameters
        k = np.asarray(p.translation_stiffness_n_m)
        d = np.asarray(p.translation_damping_ns_m)
        rest_x = np.asarray(p.rest_translation_human_m)
        kr = p.rotation_stiffness_nm_rad
        dr = p.rotation_damping_nms_rad
        rest_theta = np.asarray(p.rest_rotation_rotvec_human_rad)
        force = k * (interface_state.displacement_human_m - rest_x) + d * (
            interface_state.velocity_human_m_s
        )
        couple = kr * (interface_state.rotation_error_human_rad - rest_theta) + dr * (
            interface_state.angular_velocity_human_rad_s
        )
        rotation = np.asarray(interface_state.human_rotation_world, dtype=float)
        return ExplicitInterfacePredictionState(
            sample_timestamp_s=float(interface_state.sample_timestamp_s),
            displacement_human_m=interface_state.displacement_human_m.copy(),
            velocity_human_m_s=interface_state.velocity_human_m_s.copy(),
            rotation_error_human_rad=interface_state.rotation_error_human_rad.copy(),
            angular_velocity_human_rad_s=(
                interface_state.angular_velocity_human_rad_s.copy()
            ),
            human_rotation_world=rotation.copy(),
            base_drive_world_n=(rotation @ force).copy(),
            base_angular_drive_world_nm=(rotation @ couple).copy(),
            previous_executable_wrench_world=(
                previous_executable_wrench_world.copy()
            ),
            model_version=self.parameters.model_version,
        )

    def update_from_measurement(
        self,
        interface_state: EstimatedInterfaceState,
        *,
        previous_executable_wrench_world: np.ndarray | None = None,
    ) -> ExplicitInterfacePredictionState:
        """Causally reconcile observed interface coordinates without drive reset.

        Base drive is a zero-order-held explicit state.  A measurement updates
        the deployable interface coordinates and frame only; it never rebuilds
        drive from a short finite-difference acceleration.
        """

        if self._state is None:
            previous = (
                np.zeros(6)
                if previous_executable_wrench_world is None
                else np.asarray(previous_executable_wrench_world, dtype=float)
            )
            if previous.shape != (6,) or not np.all(np.isfinite(previous)):
                raise ValueError("previous executable wrench must be a finite six-vector")
            self._state = self._initialize_state(interface_state, previous)
            return self._state
        if interface_state.sample_timestamp_s < self._state.sample_timestamp_s - 1.0e-12:
            raise ValueError("predictor received a noncausal interface state")
        if previous_executable_wrench_world is not None:
            previous = np.asarray(previous_executable_wrench_world, dtype=float)
            if previous.shape != (6,) or not np.all(np.isfinite(previous)):
                raise ValueError("previous executable wrench must be a finite six-vector")
            if not np.allclose(
                previous,
                self._state.previous_executable_wrench_world,
                atol=1.0e-12,
                rtol=0.0,
            ):
                raise ValueError(
                    "measurement update cannot silently replace executable-wrench state"
                )
        self._state = ExplicitInterfacePredictionState(
            sample_timestamp_s=float(interface_state.sample_timestamp_s),
            displacement_human_m=interface_state.displacement_human_m.copy(),
            velocity_human_m_s=interface_state.velocity_human_m_s.copy(),
            rotation_error_human_rad=interface_state.rotation_error_human_rad.copy(),
            angular_velocity_human_rad_s=(
                interface_state.angular_velocity_human_rad_s.copy()
            ),
            human_rotation_world=interface_state.human_rotation_world.copy(),
            base_drive_world_n=self._state.base_drive_world_n.copy(),
            base_angular_drive_world_nm=(
                self._state.base_angular_drive_world_nm.copy()
            ),
            previous_executable_wrench_world=(
                self._state.previous_executable_wrench_world.copy()
            ),
            model_version=self._state.model_version,
        )
        return self._state

    def commit_executable_wrench(
        self, executable_wrench_world: np.ndarray
    ) -> ExplicitInterfacePredictionState:
        """Apply the known command increment to the explicit base-drive state."""

        if self._state is None:
            raise RuntimeError("prediction state must be initialized before commit")
        wrench = np.asarray(executable_wrench_world, dtype=float)
        if wrench.shape != (6,) or not np.all(np.isfinite(wrench)):
            raise ValueError("executable wrench must be a finite six-vector")
        delta = wrench - self._state.previous_executable_wrench_world
        self._state = ExplicitInterfacePredictionState(
            sample_timestamp_s=self._state.sample_timestamp_s,
            displacement_human_m=self._state.displacement_human_m.copy(),
            velocity_human_m_s=self._state.velocity_human_m_s.copy(),
            rotation_error_human_rad=self._state.rotation_error_human_rad.copy(),
            angular_velocity_human_rad_s=(
                self._state.angular_velocity_human_rad_s.copy()
            ),
            human_rotation_world=self._state.human_rotation_world.copy(),
            base_drive_world_n=self._state.base_drive_world_n + delta[:3],
            base_angular_drive_world_nm=(
                self._state.base_angular_drive_world_nm + delta[3:]
            ),
            previous_executable_wrench_world=wrench.copy(),
            model_version=self._state.model_version,
        )
        return self._state

    def _require_current_state(
        self, interface_state: EstimatedInterfaceState
    ) -> ExplicitInterfacePredictionState:
        if self._state is None:
            return self.update_from_measurement(interface_state)
        if not np.isclose(
            self._state.sample_timestamp_s,
            interface_state.sample_timestamp_s,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise RuntimeError(
                "prediction state timestamp is stale; call update_from_measurement"
            )
        return self._state

    def inferred_base_drive_human(
        self, interface_state: EstimatedInterfaceState
    ) -> tuple[np.ndarray, np.ndarray]:
        """Expose the explicit horizon-initial drive in the current Human frame."""

        state = self._require_current_state(interface_state)
        rotation = np.asarray(interface_state.human_rotation_world, dtype=float)
        return (
            state.base_drive_world_n @ rotation,
            state.base_angular_drive_world_nm @ rotation,
        )

    def synchronize(
        self,
        interface_state: EstimatedInterfaceState,
        previous_executable_wrench_world: np.ndarray | None = None,
    ) -> None:
        if self._state is None:
            self.update_from_measurement(
                interface_state,
                previous_executable_wrench_world=previous_executable_wrench_world,
            )
            return
        self.update_from_measurement(interface_state)
        if previous_executable_wrench_world is not None:
            self.commit_executable_wrench(previous_executable_wrench_world)

    def predict_batch(
        self,
        interface_state: EstimatedInterfaceState,
        executable_batch: ExecutableCommandBatchPreview,
    ) -> InterfaceHoldPredictionBatch:
        prediction_state = self._require_current_state(interface_state)
        p = self.parameters
        count = len(executable_batch)
        x = np.broadcast_to(interface_state.displacement_human_m, (count, 3)).copy()
        u = np.broadcast_to(interface_state.velocity_human_m_s, (count, 3)).copy()
        theta = np.broadcast_to(interface_state.rotation_error_human_rad, (count, 3)).copy()
        omega = np.broadcast_to(
            interface_state.angular_velocity_human_rad_s, (count, 3)
        ).copy()
        rotation = interface_state.human_rotation_world
        k = np.asarray(p.translation_stiffness_n_m)
        d = np.asarray(p.translation_damping_ns_m)
        mass = np.asarray(p.translation_effective_mass_kg)
        kr = p.rotation_stiffness_nm_rad
        dr = p.rotation_damping_nms_rad
        inertia = p.rotation_effective_inertia_kg_m2
        rest_x = np.asarray(p.rest_translation_human_m)
        rest_theta = np.asarray(p.rest_rotation_rotvec_human_rad)

        drive = prediction_state.base_drive_world_n @ rotation
        angular_drive = prediction_state.base_angular_drive_world_nm @ rotation
        candidate_force_human = executable_batch.force_total_n @ rotation
        previous_force_human = (
            prediction_state.previous_executable_wrench_world[:3] @ rotation
        )
        candidate_moment_human = executable_batch.moment_total_nm @ rotation
        previous_moment_human = (
            prediction_state.previous_executable_wrench_world[3:] @ rotation
        )
        drive = drive[np.newaxis, :] + candidate_force_human - previous_force_human
        angular_drive = (
            angular_drive[np.newaxis, :] + candidate_moment_human - previous_moment_human
        )
        peak_force = np.linalg.norm(interface_state.measured_force_world_n) * np.ones(count)
        peak_moment = np.linalg.norm(interface_state.measured_moment_world_nm) * np.ones(count)
        sampled_x, sampled_u = self._constant_drive_trace(
            x, u, drive, k, rest_x, self._translation_step_powers
        )
        sampled_theta, sampled_omega = self._constant_drive_trace(
            theta,
            omega,
            angular_drive,
            np.full(3, kr),
            rest_theta,
            self._rotation_step_powers,
        )
        sampled_force_human = (
            k[None, None, :] * (sampled_x - rest_x[None, None, :])
            + d[None, None, :] * sampled_u
        )
        sampled_couple_human = (
            kr * (sampled_theta - rest_theta[None, None, :])
            + dr * sampled_omega
        )
        sampled_moment_human = sampled_couple_human + np.cross(
            sampled_x + rest_x[None, None, :], sampled_force_human
        )
        endpoint_force_human = sampled_force_human[:, -1]
        endpoint_moment_human = sampled_moment_human[:, -1]
        force_sum_human = np.sum(sampled_force_human, axis=1)
        moment_sum_human = np.sum(sampled_moment_human, axis=1)
        peak_force = np.maximum(
            peak_force,
            np.max(np.linalg.norm(sampled_force_human, axis=2), axis=1),
        )
        peak_moment = np.maximum(
            peak_moment,
            np.max(np.linalg.norm(sampled_moment_human, axis=2), axis=1),
        )
        endpoint_force_world = endpoint_force_human @ rotation.T
        endpoint_moment_world = endpoint_moment_human @ rotation.T
        mean_force_world = (force_sum_human / self.substeps) @ rotation.T
        mean_moment_world = (moment_sum_human / self.substeps) @ rotation.T
        margin = p.engineering_force_gate_n - peak_force
        feasible = np.asarray(executable_batch.feasible, dtype=bool) & (margin >= -1.0e-9)
        return InterfaceHoldPredictionBatch(
            executable_batch=executable_batch,
            feasible=feasible,
            predicted_peak_force_n=peak_force,
            predicted_endpoint_force_world_n=endpoint_force_world,
            predicted_mean_force_world_n=mean_force_world,
            predicted_peak_moment_nm=peak_moment,
            predicted_endpoint_moment_world_nm=endpoint_moment_world,
            predicted_mean_moment_world_nm=mean_moment_world,
            margin_to_physical_force_gate_n=margin,
        )


class InterfaceAwareFirstActionBatchPreview:
    """Batched screen plus cached mean Human input for first-step prediction."""

    def __init__(
        self,
        executable_preview: Callable[[np.ndarray], ExecutableCommandBatchPreview],
        predictor: NominalInterfaceHoldPredictor,
        interface_state: EstimatedInterfaceState,
        q_rad: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
    ) -> None:
        self.executable_preview = executable_preview
        self.predictor = predictor
        self.interface_state = interface_state
        self.q_rad = np.asarray(q_rad, dtype=float).copy()
        self.human_model = human_model
        self.cuff_allocator = cuff_allocator
        geometry = human_model.geometry
        self._world_mapping = np.zeros((6, 3))
        self._world_mapping[:3, 0] = np.asarray(geometry.plane_x_world)
        self._world_mapping[:3, 1] = np.asarray(geometry.plane_z_world)
        self._world_mapping[3:, 2] = np.asarray(geometry.joint_axis_world)
        surface_operator = np.asarray(
            cuff_allocator.surface_model.minimum_norm_operator
        )
        surface_metric = surface_operator.T @ surface_operator
        config = cuff_allocator.config
        self._allocation_hessian_diagonal = np.array(
            [
                config.resultant_force_weight
                + config.cylindrical_surface_effort_weight * surface_metric[0, 0],
                config.resultant_force_weight
                + config.cylindrical_surface_effort_weight * surface_metric[2, 2],
                config.cylindrical_surface_effort_weight * surface_metric[4, 4],
            ]
        )
        self._last_actions: np.ndarray | None = None
        self._last_prediction: InterfaceHoldPredictionBatch | None = None
        self._screen_cache: list[
            tuple[np.ndarray, InterfaceHoldPredictionBatch]
        ] = []

    @staticmethod
    def _slice_executable_batch(
        batch: ExecutableCommandBatchPreview, index: int
    ) -> ExecutableCommandBatchPreview:
        candidate_fields = (
            "force_position_n",
            "force_velocity_n",
            "force_allocator_n",
            "force_total_n",
            "raw_force_position_n",
            "raw_force_velocity_n",
            "feedback_force_before_clipping_n",
            "feedback_force_after_clipping_n",
            "feedback_force_clipping_delta_n",
            "moment_orientation_nm",
            "moment_angular_velocity_nm",
            "moment_allocator_nm",
            "moment_total_nm",
            "translational_force_norm_n",
            "margin_to_force_gate_n",
            "feasible",
            "unclipped_joint_torque_nm",
            "joint_torque_command_nm",
        )
        values = {
            name: np.asarray(getattr(batch, name))[index : index + 1].copy()
            for name in candidate_fields
        }
        return ExecutableCommandBatchPreview(
            **values,
            robot_attachment_jacobian=batch.robot_attachment_jacobian.copy(),
            control_dt_s=batch.control_dt_s,
        )

    @classmethod
    def _slice_prediction(
        cls, prediction: InterfaceHoldPredictionBatch, index: int
    ) -> InterfaceHoldPredictionBatch:
        return InterfaceHoldPredictionBatch(
            executable_batch=cls._slice_executable_batch(
                prediction.executable_batch, index
            ),
            feasible=prediction.feasible[index : index + 1].copy(),
            predicted_peak_force_n=prediction.predicted_peak_force_n[
                index : index + 1
            ].copy(),
            predicted_endpoint_force_world_n=(
                prediction.predicted_endpoint_force_world_n[index : index + 1].copy()
            ),
            predicted_mean_force_world_n=(
                prediction.predicted_mean_force_world_n[index : index + 1].copy()
            ),
            predicted_peak_moment_nm=prediction.predicted_peak_moment_nm[
                index : index + 1
            ].copy(),
            predicted_endpoint_moment_world_nm=(
                prediction.predicted_endpoint_moment_world_nm[index : index + 1].copy()
            ),
            predicted_mean_moment_world_nm=(
                prediction.predicted_mean_moment_world_nm[index : index + 1].copy()
            ),
            margin_to_physical_force_gate_n=(
                prediction.margin_to_physical_force_gate_n[index : index + 1].copy()
            ),
        )

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        actions = np.asarray(actions_nm, dtype=float)
        # The inherited solver asks for the selected first action once more
        # after CEM.  Reuse its exact result from either population instead of
        # repeating executable-command and 20 ms interface propagation.
        if actions.shape == (1, 2):
            for cached_actions, cached_prediction in reversed(self._screen_cache):
                matches = np.flatnonzero(np.all(cached_actions == actions[0], axis=1))
                if len(matches):
                    prediction = self._slice_prediction(
                        cached_prediction, int(matches[0])
                    )
                    self._last_actions = actions.copy()
                    self._last_prediction = prediction
                    return prediction
        prediction = self.predictor.predict_batch(
            self.interface_state, self.executable_preview(actions)
        )
        self._last_actions = actions.copy()
        self._last_prediction = prediction
        self._screen_cache.append((actions.copy(), prediction))
        if len(self._screen_cache) > 4:
            self._screen_cache.pop(0)
        return prediction

    def effective_generalized_action_nm(self, actions_nm: np.ndarray) -> np.ndarray:
        """Return mean measured-side Human input over the screened hold."""

        actions = np.asarray(actions_nm, dtype=float)
        if (
            self._last_actions is None
            or self._last_prediction is None
            or self._last_actions.shape != actions.shape
            or not np.array_equal(self._last_actions, actions)
        ):
            self(actions)
        assert self._last_prediction is not None
        geometry = self.human_model.geometry
        force = self._last_prediction.predicted_mean_force_world_n
        moment = self._last_prediction.predicted_mean_moment_world_nm
        force_tau = force @ geometry.translational_jacobian_world(self.q_rad)
        moment_axis = moment @ np.asarray(geometry.joint_axis_world)
        return force_tau + np.column_stack([-moment_axis, moment_axis])

    @staticmethod
    def _geometry_batch(
        q_rad: np.ndarray, geometry: Any
    ) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(q_rad, dtype=float)
        q1 = q[:, 0]
        phi = q[:, 0] - q[:, 1]
        plane_x = np.asarray(geometry.plane_x_world)
        plane_z = np.asarray(geometry.plane_z_world)
        axis = np.asarray(geometry.joint_axis_world)
        e1_perp = -np.sin(q1)[:, None] * plane_x + np.cos(q1)[:, None] * plane_z
        shank_perp = (
            -np.sin(phi)[:, None] * plane_x + np.cos(phi)[:, None] * plane_z
        )
        first = geometry.thigh_length_m * e1_perp + geometry.cuff_distance_m * shank_perp
        second = -geometry.cuff_distance_m * shank_perp
        jacobian = np.stack([first, second], axis=2)
        cuff_angle = phi - geometry.cuff_offset_rad
        cuff_x = np.cos(cuff_angle)[:, None] * plane_x + np.sin(cuff_angle)[:, None] * plane_z
        cuff_z = -np.sin(cuff_angle)[:, None] * plane_x + np.cos(cuff_angle)[:, None] * plane_z
        rotation = np.stack(
            [cuff_x, np.broadcast_to(axis, cuff_x.shape), cuff_z], axis=2
        )
        return jacobian, rotation

    def _allocate_varying_q_batch(
        self, actions_nm: np.ndarray, q_rad: np.ndarray
    ) -> np.ndarray:
        """Vectorized registered cuff-aware allocation for varying candidate q."""

        jacobian, _ = self._geometry_batch(q_rad, self.human_model.geometry)
        return self._allocate_with_jacobian_batch(actions_nm, jacobian)

    def _allocate_with_jacobian_batch(
        self, actions_nm: np.ndarray, jacobian: np.ndarray
    ) -> np.ndarray:
        """Allocate using geometry already computed for coupled propagation."""

        action_to_world = self._allocation_map_with_jacobian_batch(jacobian)
        return np.einsum("nij,nj->ni", action_to_world, actions_nm)

    def _allocation_map_with_jacobian_batch(
        self, jacobian: np.ndarray
    ) -> np.ndarray:
        """Build the candidate-specific action-to-wrench map once per step."""

        geometry = self.human_model.geometry
        plane_x = np.asarray(geometry.plane_x_world)
        plane_z = np.asarray(geometry.plane_z_world)
        axis = np.asarray(geometry.joint_axis_world)
        force_basis = np.column_stack([plane_x, plane_z])
        sagittal_force = np.einsum("nki,kj->nij", jacobian, force_basis)
        count = len(jacobian)
        matrix = np.concatenate(
            [
                sagittal_force,
                np.broadcast_to(np.array([[[-1.0], [1.0]]]), (count, 2, 1)),
            ],
            axis=2,
        )
        # For the registered equal-area cylindrical grid, P.T@P is diagonal:
        # translational effort is isotropic and the sagittal moment is always
        # about cuff/world +Y.  Therefore the 3x3 allocation Hessian is constant
        # even though the equality matrix B(q) varies across candidates.
        inverse_hessian_bt = (
            np.swapaxes(matrix, 1, 2)
            / self._allocation_hessian_diagonal[None, :, None]
        )
        dual = np.einsum("nij,njk->nik", matrix, inverse_hessian_bt)
        dual_inverse = np.linalg.solve(
            dual, np.broadcast_to(np.eye(2), dual.shape)
        )
        action_to_sagittal = np.einsum(
            "nij,njk->nik", inverse_hessian_bt, dual_inverse
        )
        action_to_world = np.einsum(
            "ij,njk->nik", self._world_mapping, action_to_sagittal
        )
        return action_to_world

    @staticmethod
    def _constant_drive_step(
        position: np.ndarray,
        velocity: np.ndarray,
        drive: np.ndarray,
        stiffness: np.ndarray,
        damping: np.ndarray,
        mass: np.ndarray,
        rest: np.ndarray,
        dt: float,
        coefficients: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Exact underdamped diagonal step plus three-point peak samples."""

        if coefficients is None:
            omega_n = np.sqrt(stiffness / mass)
            alpha = damping / (2.0 * mass)
            omega_d = np.sqrt(np.maximum(omega_n**2 - alpha**2, 1.0e-12))
            sample_time = np.asarray([0.0, 0.5 * dt, dt])[:, None]
            decay = np.exp(-alpha[None, :] * sample_time)
            cosine = np.cos(omega_d[None, :] * sample_time)
            sine = np.sin(omega_d[None, :] * sample_time)
        else:
            omega_n, alpha, omega_d, samples = coefficients
            decay, cosine, sine = samples
        equilibrium = drive / stiffness + rest
        z0 = position - equilibrium
        z = decay[None, ...] * (
            z0[:, None, :] * cosine[None, ...]
            + (velocity + alpha * z0)[:, None, :] / omega_d[None, None, :]
            * sine[None, ...]
        )
        sample_positions = equilibrium[:, None, :] + z
        sample_velocities = decay[None, ...] * (
            velocity[:, None, :] * cosine[None, ...]
            - (
                alpha * velocity + omega_n**2 * z0
            )[:, None, :] / omega_d[None, None, :] * sine[None, ...]
        )
        endpoint_position = sample_positions[:, -1, :]
        endpoint_velocity = sample_velocities[:, -1, :]
        mean_force = drive - mass * (endpoint_velocity - velocity) / dt
        # Endpoint and midpoint sampling bounds the nominal future-step peak
        # without reproducing the plant's 0.25 ms integration in the MPC hot
        # loop. The first executed hold retains the denser 0.25 ms screen.
        sample_forces = (
            stiffness[None, None, :] * (sample_positions - rest[None, None, :])
            + damping[None, None, :] * sample_velocities
        )
        return (
            endpoint_position,
            endpoint_velocity,
            mean_force,
            sample_positions,
            sample_forces,
        )

    @staticmethod
    def _constant_drive_coefficients(
        stiffness: np.ndarray,
        damping: np.ndarray,
        mass: np.ndarray,
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        omega_n = np.sqrt(stiffness / mass)
        alpha = damping / (2.0 * mass)
        omega_d = np.sqrt(np.maximum(omega_n**2 - alpha**2, 1.0e-12))
        sample_time = np.asarray([0.0, 0.5 * dt, dt])[:, None]
        samples = np.stack(
            [
                np.exp(-alpha[None, :] * sample_time),
                np.cos(omega_d[None, :] * sample_time),
                np.sin(omega_d[None, :] * sample_time),
            ]
        )
        return omega_n, alpha, omega_d, samples

    def rollout_horizon(
        self,
        initial_human_state: np.ndarray,
        action_sequences_nm: np.ndarray,
        batched_human_step: Callable[[np.ndarray, np.ndarray, Any], np.ndarray],
        *,
        action_resolver: Callable[[np.ndarray], np.ndarray] | None = None,
        future_command_resolver: Callable[..., np.ndarray] | None = None,
    ) -> InterfaceHorizonPredictionBatch:
        """Propagate nominal interface and transmitted wrench through all steps.

        ``action_resolver`` is a Stage-5-only parameterization hook.  When
        present, ``action_sequences_nm`` contains motion increments and the
        resolver supplies the state-dependent inverse-dynamics support at each
        horizon step.  The interface, allocator, and Human predictor still see
        only the resulting total generalized action.
        """

        timing = {
            "horizon_setup": 0.0,
            "support_dynamics": 0.0,
            "geometry": 0.0,
            "cuff_allocation": 0.0,
            "loaded_execution_wrench_transforms": 0.0,
            "interface_state_propagation": 0.0,
            "human_dynamics_propagation": 0.0,
            "rollout_bookkeeping_numpy": 0.0,
        }
        setup_start = perf_counter()
        prediction_state = self.predictor._require_current_state(
            self.interface_state
        )
        actions = np.asarray(action_sequences_nm, dtype=float)
        count, horizon, _ = actions.shape
        initial_states = np.broadcast_to(
            np.asarray(initial_human_state, dtype=float), (count, 4)
        )
        first_actions = actions[:, 0, :]
        first_support = None
        if action_resolver is not None:
            section_start = perf_counter()
            first_support = np.asarray(action_resolver(initial_states), dtype=float)
            first_actions = first_actions + first_support
            timing["support_dynamics"] += perf_counter() - section_start
        if self._last_actions is None or self._last_prediction is None:
            self(first_actions)
        elif not np.array_equal(self._last_actions, first_actions):
            self(first_actions)
        assert self._last_prediction is not None
        first_commands = np.column_stack(
            [
                self._last_prediction.executable_batch.force_total_n,
                self._last_prediction.executable_batch.moment_total_nm,
            ]
        )
        p = self.predictor.parameters
        states = np.empty((count, horizon + 1, 4))
        states[:, 0, :] = np.asarray(initial_human_state, dtype=float)
        x = np.broadcast_to(self.interface_state.displacement_human_m, (count, 3)).copy()
        u = np.broadcast_to(self.interface_state.velocity_human_m_s, (count, 3)).copy()
        theta = np.broadcast_to(self.interface_state.rotation_error_human_rad, (count, 3)).copy()
        omega = np.broadcast_to(self.interface_state.angular_velocity_human_rad_s, (count, 3)).copy()
        drive_world = np.broadcast_to(
            prediction_state.base_drive_world_n, (count, 3)
        ).copy()
        angular_drive_world = np.broadcast_to(
            prediction_state.base_angular_drive_world_nm, (count, 3)
        ).copy()
        previous_command = np.broadcast_to(
            prediction_state.previous_executable_wrench_world, (count, 6)
        ).copy()
        mean_wrenches = np.empty((count, horizon, 6))
        requested_wrenches = np.empty((count, horizon, 6))
        allocated_force_norms = np.empty((count, horizon))
        peak_forces = np.empty((count, horizon))
        peak_moments = np.empty((count, horizon))
        x_trace = np.empty((count, horizon, 3))
        u_trace = np.empty((count, horizon, 3))
        theta_trace = np.empty((count, horizon, 3))
        omega_trace = np.empty((count, horizon, 3))
        drive_trace = np.empty((count, horizon, 3))
        angular_drive_trace = np.empty((count, horizon, 3))
        command_trace = np.empty((count, horizon, 6))
        k = np.asarray(p.translation_stiffness_n_m)
        d = np.asarray(p.translation_damping_ns_m)
        mass = np.asarray(p.translation_effective_mass_kg)
        kr = np.full(3, p.rotation_stiffness_nm_rad)
        dr = np.full(3, p.rotation_damping_nms_rad)
        inertia = np.full(3, p.rotation_effective_inertia_kg_m2)
        rest_x = np.asarray(p.rest_translation_human_m)
        rest_theta = np.asarray(p.rest_rotation_rotvec_human_rad)
        dt = self.predictor.control_dt_s
        translation_coefficients = self._constant_drive_coefficients(
            k, d, mass, dt
        )
        rotation_coefficients = self._constant_drive_coefficients(
            kr, dr, inertia, dt
        )
        geometry_start = perf_counter()
        jacobian, rotation = self._geometry_batch(
            states[:, 0, :2], self.human_model.geometry
        )
        timing["geometry"] += perf_counter() - geometry_start
        timing["horizon_setup"] += max(
            0.0,
            perf_counter()
            - setup_start
            - timing["support_dynamics"]
            - timing["geometry"],
        )

        for step in range(horizon):
            bookkeeping_start = perf_counter()
            total_action = actions[:, step, :]
            timing["rollout_bookkeeping_numpy"] += perf_counter() - bookkeeping_start
            if action_resolver is not None:
                section_start = perf_counter()
                support_action = (
                    first_support
                    if step == 0
                    else np.asarray(
                        action_resolver(states[:, step, :]), dtype=float
                    )
                )
                total_action = total_action + support_action
                timing["support_dynamics"] += perf_counter() - section_start
            section_start = perf_counter()
            allocation_map = self._allocation_map_with_jacobian_batch(jacobian)
            requested_wrench = np.einsum("nij,nj->ni", allocation_map, total_action)
            support_wrench = (
                None
                if action_resolver is None
                else np.einsum("nij,nj->ni", allocation_map, support_action)
            )
            timing["cuff_allocation"] += perf_counter() - section_start
            section_start = perf_counter()
            future_command = (
                requested_wrench
                if future_command_resolver is None
                else np.asarray(
                    future_command_resolver(
                        states[:, step, :],
                        total_action,
                        requested_wrench,
                        interface_displacement_human_m=x,
                        interface_velocity_human_m_s=u,
                        interface_rotation_human_rad=theta,
                        interface_angular_velocity_human_rad_s=omega,
                        human_rotation_world=rotation,
                        support_human_wrenches_world=support_wrench,
                    ),
                    dtype=float,
                )
            )
            timing["loaded_execution_wrench_transforms"] += (
                perf_counter() - section_start
            )
            if future_command.shape != requested_wrench.shape:
                raise ValueError("future command resolver returned an invalid shape")
            bookkeeping_start = perf_counter()
            command = (
                first_commands
                if step == 0
                else future_command
            )
            requested_wrenches[:, step] = requested_wrench
            allocated_force_norms[:, step] = np.linalg.norm(
                requested_wrench[:, :3], axis=1
            )
            drive_world += command[:, :3] - previous_command[:, :3]
            angular_drive_world += command[:, 3:] - previous_command[:, 3:]
            drive_trace[:, step] = drive_world
            angular_drive_trace[:, step] = angular_drive_world
            command_trace[:, step] = command
            drive_human = np.einsum("nji,nj->ni", rotation, drive_world)
            angular_drive_human = np.einsum(
                "nji,nj->ni", rotation, angular_drive_world
            )
            timing["rollout_bookkeeping_numpy"] += perf_counter() - bookkeeping_start
            section_start = perf_counter()
            x, u, mean_force_h, sampled_x, sampled_force_h = self._constant_drive_step(
                x,
                u,
                drive_human,
                k,
                d,
                mass,
                rest_x,
                dt,
                translation_coefficients,
            )
            theta, omega, mean_couple_h, sampled_theta, sampled_couple_h = (
                self._constant_drive_step(
                    theta,
                    omega,
                    angular_drive_human,
                    kr,
                    dr,
                    inertia,
                    rest_theta,
                    dt,
                    rotation_coefficients,
                )
            )
            sampled_moment_h = sampled_couple_h + np.cross(
                sampled_x + rest_x, sampled_force_h
            )
            mean_moment_h = np.mean(sampled_moment_h, axis=1)
            mean_force_world = np.einsum("nij,nj->ni", rotation, mean_force_h)
            mean_moment_world = np.einsum("nij,nj->ni", rotation, mean_moment_h)
            mean_wrenches[:, step, :3] = mean_force_world
            mean_wrenches[:, step, 3:] = mean_moment_world
            peak_forces[:, step] = np.max(
                np.linalg.norm(sampled_force_h, axis=2), axis=1
            )
            peak_moments[:, step] = np.max(
                np.linalg.norm(sampled_moment_h, axis=2), axis=1
            )
            timing["interface_state_propagation"] += perf_counter() - section_start
            section_start = perf_counter()
            force_tau = np.einsum("nki,nk->ni", jacobian, mean_force_world)
            moment_axis = mean_moment_world @ np.asarray(
                self.human_model.geometry.joint_axis_world
            )
            transmitted_action = force_tau + np.column_stack(
                [-moment_axis, moment_axis]
            )
            states[:, step + 1, :] = batched_human_step(
                states[:, step, :], transmitted_action, self.human_model
            )
            timing["human_dynamics_propagation"] += perf_counter() - section_start
            bookkeeping_start = perf_counter()
            x_trace[:, step] = x
            u_trace[:, step] = u
            theta_trace[:, step] = theta
            omega_trace[:, step] = omega
            previous_command = command
            timing["rollout_bookkeeping_numpy"] += perf_counter() - bookkeeping_start

            if step + 1 < horizon:
                geometry_start = perf_counter()
                next_jacobian, next_rotation = self._geometry_batch(
                    states[:, step + 1, :2], self.human_model.geometry
                )
                frame_change = np.einsum(
                    "nji,njk->nik", next_rotation, rotation
                )
                x = np.einsum("nij,nj->ni", frame_change, x + rest_x) - rest_x
                u = np.einsum("nij,nj->ni", frame_change, u)
                theta = (
                    np.einsum("nij,nj->ni", frame_change, theta + rest_theta)
                    - rest_theta
                )
                omega = np.einsum("nij,nj->ni", frame_change, omega)
                jacobian, rotation = next_jacobian, next_rotation
                timing["geometry"] += perf_counter() - geometry_start

        return InterfaceHorizonPredictionBatch(
            predicted_human_states=states[:, 1:, :],
            requested_cuff_wrench_world=requested_wrenches,
            allocated_force_norm_n=allocated_force_norms,
            transmitted_mean_wrench_world=mean_wrenches,
            predicted_peak_force_n=peak_forces,
            predicted_peak_moment_nm=peak_moments,
            interface_displacement_human_m=x_trace,
            interface_velocity_human_m_s=u_trace,
            interface_rotation_error_human_rad=theta_trace,
            interface_angular_velocity_human_rad_s=omega_trace,
            base_drive_world_n=drive_trace,
            base_angular_drive_world_nm=angular_drive_trace,
            executable_wrench_world=command_trace,
            timing_s=timing,
        )


def make_interface_aware_first_action_batch_preview(
    executable_preview: Callable[[np.ndarray], ExecutableCommandBatchPreview],
    predictor: NominalInterfaceHoldPredictor,
    interface_state: EstimatedInterfaceState,
    *,
    q_rad: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
) -> InterfaceAwareFirstActionBatchPreview:
    """Compose one batched executable-command and physical-interface screen."""

    return InterfaceAwareFirstActionBatchPreview(
        executable_preview,
        predictor,
        interface_state,
        q_rad,
        human_model,
        cuff_allocator,
    )


__all__ = [
    "CONTROLLER_NOMINAL_INTERFACE",
    "ControllerNominalInterfaceParameters",
    "EstimatedInterfaceState",
    "ExplicitInterfacePredictionState",
    "INTERFACE_AWARE_ESTIMATOR_Q_DQ",
    "InterfaceAwareHumanStateObserver",
    "InterfaceAwareFirstActionBatchPreview",
    "InterfaceHoldPredictionBatch",
    "InterfaceHorizonPredictionBatch",
    "NominalInterfaceHoldPredictor",
    "load_controller_nominal_interface",
    "make_interface_aware_first_action_batch_preview",
]
