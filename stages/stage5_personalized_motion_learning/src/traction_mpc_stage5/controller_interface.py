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

from .acceleration_semantics import screen_cumulative_prefix_acceleration
from .config import STAGE5_ROOT
from .task_observation import ControllerTaskObservation, make_task_observation


try:  # Optional exact compiled backend; the NumPy reference remains complete.
    from . import _prefix_native
except ImportError:  # pragma: no cover - exercised by source-only fallback tests
    _prefix_native = None


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
    acceleration_semantics_version: str = "v1_full_20ms_only"
    prefix_times_s: np.ndarray | None = None
    predicted_prefix_states_rad_rad_s: np.ndarray | None = None
    predicted_prefix_acceleration_rad_s2: np.ndarray | None = None
    prefix_acceleration_margin_rad_s2: np.ndarray | None = None
    prefix_acceleration_feasible: np.ndarray | None = None
    predicted_prefix_interface_displacement_human_m: np.ndarray | None = None
    predicted_prefix_interface_velocity_human_m_s: np.ndarray | None = None
    predicted_prefix_interface_rotation_human_rad: np.ndarray | None = None
    predicted_prefix_interface_angular_velocity_human_rad_s: np.ndarray | None = None
    predicted_prefix_executable_wrench_world: np.ndarray | None = None

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
        planning_force_ceiling_n: float | None = None,
    ) -> None:
        self.parameters = parameters
        self.control_dt_s = float(control_dt_s)
        self.planning_force_ceiling_n = (
            parameters.engineering_force_gate_n
            if planning_force_ceiling_n is None
            else float(planning_force_ceiling_n)
        )
        if (
            not math.isfinite(self.planning_force_ceiling_n)
            or self.planning_force_ceiling_n <= 0.0
            or self.planning_force_ceiling_n > parameters.engineering_force_gate_n
        ):
            raise ValueError(
                "planning force ceiling must be positive and no greater than the "
                "unchanged engineering force gate"
            )
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
        # This predictor is used by MPC screening.  A caller may request a
        # conservative planning reserve below the unchanged 200 N physical
        # engineering gate; execution and plant supervision retain the latter.
        margin = self.planning_force_ceiling_n - peak_force
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
        *,
        state_rad_rad_s: np.ndarray | None = None,
        acceleration_limits_rad_s2: np.ndarray | None = None,
        use_optimized_prefix_numpy: bool = True,
        capture_prefix_diagnostics: bool = False,
        prefix_backend: str = "numpy",
        capture_prefix_substeps: bool = False,
    ) -> None:
        self.executable_preview = executable_preview
        self.predictor = predictor
        self.interface_state = interface_state
        self.q_rad = np.asarray(q_rad, dtype=float).copy()
        self.state_rad_rad_s = (
            None
            if state_rad_rad_s is None
            else np.asarray(state_rad_rad_s, dtype=float).copy()
        )
        self.acceleration_limits_rad_s2 = (
            None
            if acceleration_limits_rad_s2 is None
            else np.asarray(acceleration_limits_rad_s2, dtype=float).copy()
        )
        if self.state_rad_rad_s is not None:
            if self.state_rad_rad_s.shape != (4,) or not np.all(
                np.isfinite(self.state_rad_rad_s)
            ):
                raise ValueError("prefix screening state must be one finite state[4]")
            if not np.array_equal(self.state_rad_rad_s[:2], self.q_rad):
                raise ValueError("prefix screening state q must match q_rad")
        if self.acceleration_limits_rad_s2 is not None:
            if self.acceleration_limits_rad_s2.shape != (2,) or np.any(
                self.acceleration_limits_rad_s2 <= 0.0
            ) or not np.all(np.isfinite(self.acceleration_limits_rad_s2)):
                raise ValueError("prefix acceleration limits must be a positive pair")
            if self.state_rad_rad_s is None:
                raise ValueError("prefix acceleration limits require the full Human state")
        self.human_model = human_model
        self.cuff_allocator = cuff_allocator
        geometry = human_model.geometry
        self._prefix_plane_x_world = np.asarray(geometry.plane_x_world)
        self._prefix_plane_z_world = np.asarray(geometry.plane_z_world)
        self._prefix_joint_axis_world = np.asarray(geometry.joint_axis_world)
        self._prefix_thigh_length_m = float(geometry.thigh_length_m)
        self._prefix_cuff_distance_m = float(geometry.cuff_distance_m)
        self._prefix_cuff_offset_rad = float(geometry.cuff_offset_rad)
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
        # Diagnostic override exists only so the runtime regression test can
        # compare the former duplicate-subset path against the equivalent
        # cached path.  Production always keeps reuse enabled.
        self._reuse_cached_subsets = True
        self._prefix_support_provider: Callable[[np.ndarray], np.ndarray] | None = None
        self._prefix_human_continuous_dynamics: Callable[
            [np.ndarray, np.ndarray, Any], np.ndarray
        ] | None = None
        self._prefix_future_command_resolver: Callable[..., np.ndarray] | None = None
        # Disabled in production.  The runtime-floor audit enables this only on
        # frozen snapshots to time exact regions of the unchanged recurrence.
        self._profile_prefix_regions = False
        self.prefix_region_profiles_s: list[dict[str, float]] = []
        # Diagnostic switch retains the checkpoint implementation for strict
        # equivalence tests. Production uses the batched NumPy refactor.
        self._use_optimized_prefix_numpy = bool(use_optimized_prefix_numpy)
        self._capture_prefix_diagnostics = bool(capture_prefix_diagnostics)
        if prefix_backend not in {"numpy", "native", "auto"}:
            raise ValueError("prefix_backend must be numpy, native, or auto")
        self.prefix_backend_requested = prefix_backend
        self.prefix_backend_resolved = (
            "native"
            if prefix_backend == "native"
            or (prefix_backend == "auto" and _prefix_native is not None)
            else "numpy"
        )
        if self.prefix_backend_resolved == "native" and _prefix_native is None:
            raise RuntimeError(
                "native prefix backend requested but the extension is unavailable"
            )
        self._capture_prefix_substeps = bool(capture_prefix_substeps)
        self.last_prefix_substep_traces: list[np.ndarray] = []
        self._prefix_numpy_dynamics_available = bool(
            hasattr(human_model, "beta") and hasattr(human_model, "rom_human")
        )
        if self.prefix_backend_resolved == "native" and (
            not self._prefix_numpy_dynamics_available
            or not self._use_optimized_prefix_numpy
        ):
            raise RuntimeError(
                "native prefix backend requires the Stage-5 beta/ROM model and "
                "optimized NumPy semantics"
            )
        if self._prefix_numpy_dynamics_available:
            self._prefix_beta = np.asarray(human_model.beta, dtype=float)
            rom = human_model.rom_human
            self._prefix_soft_lower_rad = (
                np.asarray(rom.q_min_rad)
                + rom.soft_limit_margin_rad
                - rom.soft_limit_numerical_tolerance_rad
            )
            self._prefix_soft_upper_rad = (
                np.asarray(rom.q_max_rad)
                - rom.soft_limit_margin_rad
                + rom.soft_limit_numerical_tolerance_rad
            )
            interface = predictor.parameters
            geometry = human_model.geometry
            self._prefix_native_constants = np.ascontiguousarray(
                np.concatenate(
                    [
                        np.asarray(interface.translation_stiffness_n_m),
                        np.asarray(interface.translation_damping_ns_m),
                        np.asarray(interface.translation_effective_mass_kg),
                        np.asarray(interface.rest_translation_human_m),
                        np.asarray(interface.rest_rotation_rotvec_human_rad),
                        self._prefix_beta,
                        self._prefix_soft_lower_rad,
                        self._prefix_soft_upper_rad,
                        np.asarray(geometry.plane_x_world),
                        np.asarray(geometry.plane_z_world),
                        np.asarray(geometry.joint_axis_world),
                        np.asarray(
                            [
                                interface.rotation_stiffness_nm_rad,
                                interface.rotation_damping_nms_rad,
                                interface.rotation_effective_inertia_kg_m2,
                                rom.soft_limit_margin_rad,
                                rom.soft_limit_boundary_torque_nm,
                                rom.soft_limit_damping_nms_rad,
                                geometry.thigh_length_m,
                                geometry.cuff_distance_m,
                                geometry.cuff_offset_rad,
                                interface.prediction_substep_s,
                            ]
                        ),
                    ]
                ),
                dtype=np.float64,
            )
            if self._prefix_native_constants.shape != (49,):
                raise RuntimeError("native prefix constant layout is inconsistent")
        else:
            self._prefix_beta = None
            self._prefix_soft_lower_rad = None
            self._prefix_soft_upper_rad = None
            self._prefix_native_constants = None

    @property
    def last_prediction(self) -> InterfaceHoldPredictionBatch | None:
        """Expose the selected cached screen for Stage-5 diagnostics only."""

        return self._last_prediction

    def configure_prefix_screening(
        self,
        *,
        support_provider: Callable[[np.ndarray], np.ndarray],
        human_continuous_dynamics: Callable[
            [np.ndarray, np.ndarray, Any], np.ndarray
        ],
        future_command_resolver: Callable[..., np.ndarray],
    ) -> None:
        """Bind the same support, Human, and loaded-execution laws as Goal-MPC.

        The bindings are installed by the Stage-5 support-centered wrapper while
        a solve is active.  They are controller-model functions only; neither
        MuJoCo state nor plant-truth interface parameters cross this boundary.
        """

        self._prefix_support_provider = support_provider
        self._prefix_human_continuous_dynamics = human_continuous_dynamics
        self._prefix_future_command_resolver = future_command_resolver

    @staticmethod
    def _take_executable_batch(
        batch: ExecutableCommandBatchPreview, indices: np.ndarray
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
            name: np.asarray(getattr(batch, name))[indices].copy()
            for name in candidate_fields
        }
        return ExecutableCommandBatchPreview(
            **values,
            robot_attachment_jacobian=batch.robot_attachment_jacobian.copy(),
            control_dt_s=batch.control_dt_s,
        )

    @classmethod
    def _take_prediction(
        cls, prediction: InterfaceHoldPredictionBatch, indices: np.ndarray
    ) -> InterfaceHoldPredictionBatch:
        selected = np.asarray(indices, dtype=int)
        if selected.ndim != 1:
            raise ValueError("cached prediction indices must be one-dimensional")
        return InterfaceHoldPredictionBatch(
            executable_batch=cls._take_executable_batch(
                prediction.executable_batch, selected
            ),
            feasible=prediction.feasible[selected].copy(),
            predicted_peak_force_n=prediction.predicted_peak_force_n[selected].copy(),
            predicted_endpoint_force_world_n=(
                prediction.predicted_endpoint_force_world_n[selected].copy()
            ),
            predicted_mean_force_world_n=(
                prediction.predicted_mean_force_world_n[selected].copy()
            ),
            predicted_peak_moment_nm=prediction.predicted_peak_moment_nm[selected].copy(),
            predicted_endpoint_moment_world_nm=(
                prediction.predicted_endpoint_moment_world_nm[selected].copy()
            ),
            predicted_mean_moment_world_nm=(
                prediction.predicted_mean_moment_world_nm[selected].copy()
            ),
            margin_to_physical_force_gate_n=(
                prediction.margin_to_physical_force_gate_n[selected].copy()
            ),
            acceleration_semantics_version=prediction.acceleration_semantics_version,
            prefix_times_s=(
                None
                if prediction.prefix_times_s is None
                else prediction.prefix_times_s.copy()
            ),
            predicted_prefix_states_rad_rad_s=(
                None
                if prediction.predicted_prefix_states_rad_rad_s is None
                else prediction.predicted_prefix_states_rad_rad_s[selected].copy()
            ),
            predicted_prefix_acceleration_rad_s2=(
                None
                if prediction.predicted_prefix_acceleration_rad_s2 is None
                else prediction.predicted_prefix_acceleration_rad_s2[selected].copy()
            ),
            prefix_acceleration_margin_rad_s2=(
                None
                if prediction.prefix_acceleration_margin_rad_s2 is None
                else prediction.prefix_acceleration_margin_rad_s2[selected].copy()
            ),
            prefix_acceleration_feasible=(
                None
                if prediction.prefix_acceleration_feasible is None
                else prediction.prefix_acceleration_feasible[selected].copy()
            ),
            predicted_prefix_interface_displacement_human_m=(
                None
                if prediction.predicted_prefix_interface_displacement_human_m is None
                else prediction.predicted_prefix_interface_displacement_human_m[
                    selected
                ].copy()
            ),
            predicted_prefix_interface_velocity_human_m_s=(
                None
                if prediction.predicted_prefix_interface_velocity_human_m_s is None
                else prediction.predicted_prefix_interface_velocity_human_m_s[
                    selected
                ].copy()
            ),
            predicted_prefix_interface_rotation_human_rad=(
                None
                if prediction.predicted_prefix_interface_rotation_human_rad is None
                else prediction.predicted_prefix_interface_rotation_human_rad[
                    selected
                ].copy()
            ),
            predicted_prefix_interface_angular_velocity_human_rad_s=(
                None
                if prediction.predicted_prefix_interface_angular_velocity_human_rad_s
                is None
                else prediction.predicted_prefix_interface_angular_velocity_human_rad_s[
                    selected
                ].copy()
            ),
            predicted_prefix_executable_wrench_world=(
                None
                if prediction.predicted_prefix_executable_wrench_world is None
                else prediction.predicted_prefix_executable_wrench_world[selected].copy()
            ),
        )

    def _cached_prediction_for_actions(
        self, actions: np.ndarray
    ) -> InterfaceHoldPredictionBatch | None:
        """Return an exact cached row/subset/reordering, never an approximation."""

        for cached_actions, cached_prediction in reversed(self._screen_cache):
            matches = np.all(
                actions[:, None, :] == cached_actions[None, :, :], axis=2
            )
            if np.all(np.any(matches, axis=1)):
                selected = np.argmax(matches, axis=1)
                return self._take_prediction(
                    cached_prediction, np.asarray(selected, dtype=int)
                )
        return None

    def _batched_human_step_at_dt(
        self, states: np.ndarray, actions_nm: np.ndarray, dt_s: float
    ) -> np.ndarray:
        dynamics = self._prefix_human_continuous_dynamics
        if dynamics is None:
            raise RuntimeError("V2 prefix screen has no Human dynamics binding")
        dt = float(dt_s)
        optimized = (
            self._use_optimized_prefix_numpy
            and self._prefix_numpy_dynamics_available
        )
        if optimized:
            evaluate = self._prefix_continuous_dynamics_numpy
        else:
            evaluate = lambda state, action: dynamics(
                state, action, self.human_model
            )
        k1 = evaluate(states, actions_nm)
        k2 = evaluate(states + 0.5 * dt * k1, actions_nm)
        k3 = evaluate(states + 0.5 * dt * k2, actions_nm)
        k4 = evaluate(states + dt * k3, actions_nm)
        return states + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

    def _prefix_continuous_dynamics_numpy(
        self, state: np.ndarray, action: np.ndarray
    ) -> np.ndarray:
        """Stage-5 NumPy equivalent of the inherited two-joint dynamics."""

        human = self.human_model
        x = np.asarray(state, dtype=float)
        q1 = x[..., 0]
        q2 = x[..., 1]
        dq1 = x[..., 2]
        dq2 = x[..., 3]
        phi = q1 - q2
        cosine = np.cos(q2)
        sine = np.sin(q2)
        assert self._prefix_beta is not None
        beta = self._prefix_beta
        zero_acceleration = np.empty(x.shape[:-1] + (2,), dtype=float)
        zero_acceleration[..., 0] = (
            beta[2] * sine * (-2.0 * dq1 * dq2 + dq2**2)
            + beta[3] * np.cos(q1)
            + beta[4] * np.cos(phi)
            + beta[5] * q1
            - beta[7]
            + beta[9] * dq1
        )
        zero_acceleration[..., 1] = (
            beta[2] * sine * dq1**2
            - beta[4] * np.cos(phi)
            + beta[6] * q2
            - beta[8]
            + beta[10] * dq2
        )
        rom = human.rom_human
        assert self._prefix_soft_lower_rad is not None
        assert self._prefix_soft_upper_rad is not None
        lower = self._prefix_soft_lower_rad
        upper = self._prefix_soft_upper_rad
        outside_soft_region = np.any(
            (x[..., :2] < lower) | (x[..., :2] > upper)
        )
        if outside_soft_region:
            dynamics_owner = getattr(
                self._prefix_human_continuous_dynamics, "__self__", None
            )
            if dynamics_owner is None:
                raise RuntimeError("prefix Human dynamics has no bound owner")
            soft_limit = dynamics_owner._batched_soft_limit_torque(
                x[..., :2], x[..., 2:], rom
            )
        else:
            soft_limit = np.zeros_like(x[..., :2])
        zero_acceleration -= soft_limit
        mass_00 = beta[0] + 2.0 * beta[2] * cosine
        mass_01 = -(beta[1] + beta[2] * cosine)
        mass_11 = beta[1]
        right_hand_side = np.asarray(action, dtype=float) - zero_acceleration
        determinant = mass_00 * mass_11 - mass_01 * mass_01
        acceleration = np.empty_like(right_hand_side)
        acceleration[..., 0] = (
            mass_11 * right_hand_side[..., 0]
            - mass_01 * right_hand_side[..., 1]
        ) / determinant
        acceleration[..., 1] = (
            mass_00 * right_hand_side[..., 1]
            - mass_01 * right_hand_side[..., 0]
        ) / determinant
        return np.concatenate([x[..., 2:], acceleration], axis=-1)

    def _prefix_geometry_batch(
        self, q_rad: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Cached-invariant equivalent of ``_geometry_batch`` for the hot loop."""

        q = np.asarray(q_rad, dtype=float)
        q1 = q[:, 0]
        phi = q[:, 0] - q[:, 1]
        plane_x = self._prefix_plane_x_world
        plane_z = self._prefix_plane_z_world
        axis = self._prefix_joint_axis_world
        e1_perp = -np.sin(q1)[:, None] * plane_x + np.cos(q1)[:, None] * plane_z
        shank_perp = (
            -np.sin(phi)[:, None] * plane_x + np.cos(phi)[:, None] * plane_z
        )
        first = (
            self._prefix_thigh_length_m * e1_perp
            + self._prefix_cuff_distance_m * shank_perp
        )
        second = -self._prefix_cuff_distance_m * shank_perp
        jacobian = np.stack([first, second], axis=2)
        cuff_angle = phi - self._prefix_cuff_offset_rad
        cuff_x = (
            np.cos(cuff_angle)[:, None] * plane_x
            + np.sin(cuff_angle)[:, None] * plane_z
        )
        cuff_z = (
            -np.sin(cuff_angle)[:, None] * plane_x
            + np.cos(cuff_angle)[:, None] * plane_z
        )
        rotation = np.stack(
            [cuff_x, np.broadcast_to(axis, cuff_x.shape), cuff_z], axis=2
        )
        return jacobian, rotation

    def _propagate_prefix_segment_numpy(
        self,
        *,
        states: np.ndarray,
        x: np.ndarray,
        u: np.ndarray,
        theta: np.ndarray,
        omega: np.ndarray,
        rotation: np.ndarray,
        jacobian: np.ndarray,
        drive_world: np.ndarray,
        angular_drive_world: np.ndarray,
        substeps: int,
        region_timing: dict[str, float],
        profile: bool,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray | None,
    ]:
        """Readable exact reference for one 5 ms physical prefix segment."""

        p = self.predictor.parameters
        k = np.asarray(p.translation_stiffness_n_m)
        d = np.asarray(p.translation_damping_ns_m)
        mass = np.asarray(p.translation_effective_mass_kg)
        kr = np.full(3, p.rotation_stiffness_nm_rad)
        dr = np.full(3, p.rotation_damping_nms_rad)
        inertia = np.full(3, p.rotation_effective_inertia_kg_m2)
        rest_x = np.asarray(p.rest_translation_human_m)
        rest_theta = np.asarray(p.rest_rotation_rotvec_human_rad)
        dt = p.prediction_substep_s
        geometry_batch = (
            self._prefix_geometry_batch
            if self._use_optimized_prefix_numpy
            else lambda q: self._geometry_batch(q, self.human_model.geometry)
        )
        trace = (
            np.empty((substeps, len(states), 22), dtype=float)
            if self._capture_prefix_substeps
            else None
        )
        for substep in range(substeps):
            section_start = perf_counter() if profile else 0.0
            drive_human = np.einsum("nji,nj->ni", rotation, drive_world)
            angular_drive_human = np.einsum(
                "nji,nj->ni", rotation, angular_drive_world
            )
            if profile:
                region_timing["drive_frame_transforms"] += (
                    perf_counter() - section_start
                )
                section_start = perf_counter()
            translation_acceleration = (
                drive_human - k * (x - rest_x) - d * u
            ) / mass
            u = u + dt * translation_acceleration
            x = x + dt * u
            rotation_acceleration = (
                angular_drive_human
                - kr * (theta - rest_theta)
                - dr * omega
            ) / inertia
            omega = omega + dt * rotation_acceleration
            theta = theta + dt * omega
            force_human = k * (x - rest_x) + d * u
            couple_human = kr * (theta - rest_theta) + dr * omega
            moment_human = couple_human + np.cross(x + rest_x, force_human)
            force_world = np.einsum("nij,nj->ni", rotation, force_human)
            moment_world = np.einsum("nij,nj->ni", rotation, moment_human)
            force_tau = np.einsum("nki,nk->ni", jacobian, force_world)
            moment_axis = moment_world @ self._prefix_joint_axis_world
            if self._use_optimized_prefix_numpy:
                transmitted_action = force_tau.copy()
                transmitted_action[:, 0] -= moment_axis
                transmitted_action[:, 1] += moment_axis
            else:
                transmitted_action = force_tau + np.column_stack(
                    [-moment_axis, moment_axis]
                )
            if profile:
                region_timing["interface_state_and_wrench"] += (
                    perf_counter() - section_start
                )
                section_start = perf_counter()
            states = self._batched_human_step_at_dt(states, transmitted_action, dt)
            if profile:
                region_timing["human_forward_dynamics"] += (
                    perf_counter() - section_start
                )
                section_start = perf_counter()
            next_jacobian, next_rotation = geometry_batch(states[:, :2])
            frame_change = np.einsum("nji,njk->nik", next_rotation, rotation)
            x = np.einsum("nij,nj->ni", frame_change, x + rest_x) - rest_x
            u = np.einsum("nij,nj->ni", frame_change, u)
            theta = (
                np.einsum("nij,nj->ni", frame_change, theta + rest_theta)
                - rest_theta
            )
            omega = np.einsum("nij,nj->ni", frame_change, omega)
            rotation = next_rotation
            jacobian = next_jacobian
            if trace is not None:
                trace[substep, :, 0:4] = states
                trace[substep, :, 4:7] = x
                trace[substep, :, 7:10] = u
                trace[substep, :, 10:13] = theta
                trace[substep, :, 13:16] = omega
                trace[substep, :, 16:19] = force_world
                trace[substep, :, 19:22] = moment_world
            if profile:
                region_timing["geometry_and_frame_update"] += (
                    perf_counter() - section_start
                )
        return states, x, u, theta, omega, rotation, jacobian, trace

    def _propagate_prefix_segment_native(
        self,
        *,
        states: np.ndarray,
        x: np.ndarray,
        u: np.ndarray,
        theta: np.ndarray,
        omega: np.ndarray,
        rotation: np.ndarray,
        jacobian: np.ndarray,
        drive_world: np.ndarray,
        angular_drive_world: np.ndarray,
        substeps: int,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray | None,
    ]:
        """Run the same segment recurrence in one compiled batch call."""

        if _prefix_native is None or self._prefix_native_constants is None:
            raise RuntimeError("native prefix backend is unavailable")
        arrays = (states, x, u, theta, omega, rotation, jacobian)
        if not all(
            value.dtype == np.float64 and value.flags.c_contiguous
            for value in arrays
        ):
            raise ValueError("native prefix state arrays must be C-contiguous float64")
        drive = np.ascontiguousarray(drive_world, dtype=np.float64)
        angular_drive = np.ascontiguousarray(
            angular_drive_world, dtype=np.float64
        )
        trace = (
            np.empty((substeps, len(states), 22), dtype=np.float64)
            if self._capture_prefix_substeps
            else None
        )
        _prefix_native.propagate_segment(
            states,
            x,
            u,
            theta,
            omega,
            rotation,
            jacobian,
            drive,
            angular_drive,
            self._prefix_native_constants,
            substeps,
            trace,
        )
        return states, x, u, theta, omega, rotation, jacobian, trace

    def _apply_v2_prefix_acceleration_screen(
        self,
        actions_nm: np.ndarray,
        prediction: InterfaceHoldPredictionBatch,
    ) -> InterfaceHoldPredictionBatch:
        """Check cumulative 5/10/15/20 ms acceleration under loaded execution.

        Each 5 ms segment refreshes the loaded low-level command.  Within a
        segment, the existing 0.25 ms semi-implicit interface recurrence and
        fixed Human model are coupled at every physical substep. Prefix states
        are therefore propagated, not interpolated from the 20 ms endpoint.
        """

        if self.acceleration_limits_rad_s2 is None:
            return prediction
        profile = self._profile_prefix_regions
        region_timing = {
            "state_copy_and_setup": 0.0,
            "candidate_command_construction": 0.0,
            "drive_frame_transforms": 0.0,
            "interface_state_and_wrench": 0.0,
            "human_forward_dynamics": 0.0,
            "geometry_and_frame_update": 0.0,
            "native_prefix_recurrence": 0.0,
            "support_and_allocation_refresh": 0.0,
            "loaded_command_refresh": 0.0,
            "acceleration_and_feasibility": 0.0,
        }
        setup_start = perf_counter() if profile else 0.0
        if (
            self._prefix_support_provider is None
            or self._prefix_human_continuous_dynamics is None
            or self._prefix_future_command_resolver is None
        ):
            raise RuntimeError("V2 prefix screen bindings were not configured")
        assert self.state_rad_rad_s is not None
        count = len(actions_nm)
        prefix_dt_s = 0.005
        prefix_count = 4
        p = self.predictor.parameters
        substeps_float = prefix_dt_s / p.prediction_substep_s
        substeps = int(round(substeps_float))
        if substeps < 1 or not np.isclose(
            substeps_float, substeps, atol=1.0e-12, rtol=0.0
        ):
            raise ValueError("0.25 ms interface substep must divide 5 ms prefixes")
        if substeps > len(self.predictor._translation_step_powers):
            raise ValueError("predictor hold is shorter than one 5 ms prefix")
        prediction_state = self.predictor._require_current_state(self.interface_state)
        states = np.broadcast_to(self.state_rad_rad_s, (count, 4)).copy()
        initial_dq = states[:, 2:].copy()
        x = np.broadcast_to(
            self.interface_state.displacement_human_m, (count, 3)
        ).copy()
        u = np.broadcast_to(
            self.interface_state.velocity_human_m_s, (count, 3)
        ).copy()
        theta = np.broadcast_to(
            self.interface_state.rotation_error_human_rad, (count, 3)
        ).copy()
        omega = np.broadcast_to(
            self.interface_state.angular_velocity_human_rad_s, (count, 3)
        ).copy()
        rotation = np.broadcast_to(
            self.interface_state.human_rotation_world, (count, 3, 3)
        ).copy()
        drive_world = np.broadcast_to(
            prediction_state.base_drive_world_n, (count, 3)
        ).copy()
        angular_drive_world = np.broadcast_to(
            prediction_state.base_angular_drive_world_nm, (count, 3)
        ).copy()
        previous_command = np.broadcast_to(
            prediction_state.previous_executable_wrench_world, (count, 6)
        ).copy()
        if profile:
            region_timing["state_copy_and_setup"] += perf_counter() - setup_start
            section_start = perf_counter()
        command = np.column_stack(
            [
                prediction.executable_batch.force_total_n,
                prediction.executable_batch.moment_total_nm,
            ]
        )
        if profile:
            region_timing["candidate_command_construction"] += (
                perf_counter() - section_start
            )
            setup_start = perf_counter()
        prefix_states = np.empty((count, prefix_count, 4), dtype=float)
        prefix_x = (
            np.empty((count, prefix_count, 3), dtype=float)
            if self._capture_prefix_diagnostics
            else None
        )
        prefix_u = None if prefix_x is None else np.empty_like(prefix_x)
        prefix_theta = None if prefix_x is None else np.empty_like(prefix_x)
        prefix_omega = None if prefix_x is None else np.empty_like(prefix_x)
        prefix_command = (
            np.empty((count, prefix_count, 6), dtype=float)
            if self._capture_prefix_diagnostics
            else None
        )
        geometry_batch = (
            self._prefix_geometry_batch
            if self._use_optimized_prefix_numpy
            else lambda q: self._geometry_batch(q, self.human_model.geometry)
        )
        jacobian, rotation_from_q = geometry_batch(states[:, :2])
        # At the observation boundary the interface observer's Human frame and
        # the deployable q/dq geometry are the same controller estimate.  Keep
        # the observed frame for the first segment and q-propagated frames after.
        del rotation_from_q
        if profile:
            region_timing["state_copy_and_setup"] += perf_counter() - setup_start
        self.last_prefix_substep_traces = []
        for segment in range(prefix_count):
            drive_world += command[:, :3] - previous_command[:, :3]
            angular_drive_world += command[:, 3:] - previous_command[:, 3:]
            # Couple the existing 0.25 ms semi-implicit interface recurrence to
            # the fixed Human model.  This avoids compressing a fast startup
            # transient into one 5 ms mean-wrench Human step.
            section_start = perf_counter() if profile else 0.0
            propagate = (
                self._propagate_prefix_segment_native
                if self.prefix_backend_resolved == "native"
                else self._propagate_prefix_segment_numpy
            )
            propagated = propagate(
                states=states,
                x=x,
                u=u,
                theta=theta,
                omega=omega,
                rotation=rotation,
                jacobian=jacobian,
                drive_world=drive_world,
                angular_drive_world=angular_drive_world,
                substeps=substeps,
                **(
                    {}
                    if self.prefix_backend_resolved == "native"
                    else {"region_timing": region_timing, "profile": profile}
                ),
            )
            states, x, u, theta, omega, rotation, jacobian, substep_trace = (
                propagated
            )
            if substep_trace is not None:
                self.last_prefix_substep_traces.append(substep_trace)
            if profile and self.prefix_backend_resolved == "native":
                region_timing["native_prefix_recurrence"] += (
                    perf_counter() - section_start
                )
            prefix_states[:, segment] = states
            if prefix_x is not None:
                assert prefix_u is not None
                assert prefix_theta is not None
                assert prefix_omega is not None
                assert prefix_command is not None
                prefix_x[:, segment] = x
                prefix_u[:, segment] = u
                prefix_theta[:, segment] = theta
                prefix_omega[:, segment] = omega
                prefix_command[:, segment] = command
            previous_command = command
            if segment + 1 == prefix_count:
                continue
            section_start = perf_counter() if profile else 0.0
            support_action = np.asarray(
                self._prefix_support_provider(states), dtype=float
            )
            allocation_map = self._allocation_map_with_jacobian_batch(jacobian)
            requested_wrench = np.einsum(
                "nij,nj->ni", allocation_map, actions_nm
            )
            support_wrench = np.einsum(
                "nij,nj->ni", allocation_map, support_action
            )
            if profile:
                region_timing["support_and_allocation_refresh"] += (
                    perf_counter() - section_start
                )
                section_start = perf_counter()
            command = np.asarray(
                self._prefix_future_command_resolver(
                    states,
                    actions_nm,
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
            if profile:
                region_timing["loaded_command_refresh"] += (
                    perf_counter() - section_start
                )
        section_start = perf_counter() if profile else 0.0
        prefix_times = prefix_dt_s * np.arange(1, prefix_count + 1, dtype=float)
        screen = screen_cumulative_prefix_acceleration(
            initial_dq,
            prefix_states[..., 2:],
            prefix_times,
            self.acceleration_limits_rad_s2,
        )
        if profile:
            region_timing["acceleration_and_feasibility"] += (
                perf_counter() - section_start
            )
            self.prefix_region_profiles_s.append(region_timing)
        return InterfaceHoldPredictionBatch(
            executable_batch=prediction.executable_batch,
            feasible=np.asarray(prediction.feasible, dtype=bool) & screen.feasible,
            predicted_peak_force_n=prediction.predicted_peak_force_n,
            predicted_endpoint_force_world_n=prediction.predicted_endpoint_force_world_n,
            predicted_mean_force_world_n=prediction.predicted_mean_force_world_n,
            predicted_peak_moment_nm=prediction.predicted_peak_moment_nm,
            predicted_endpoint_moment_world_nm=prediction.predicted_endpoint_moment_world_nm,
            predicted_mean_moment_world_nm=prediction.predicted_mean_moment_world_nm,
            margin_to_physical_force_gate_n=prediction.margin_to_physical_force_gate_n,
            acceleration_semantics_version="v2_cumulative_prefix_5_10_15_20ms",
            prefix_times_s=prefix_times,
            predicted_prefix_states_rad_rad_s=prefix_states,
            predicted_prefix_acceleration_rad_s2=screen.acceleration_rad_s2,
            prefix_acceleration_margin_rad_s2=screen.margin_rad_s2,
            prefix_acceleration_feasible=screen.feasible,
            predicted_prefix_interface_displacement_human_m=prefix_x,
            predicted_prefix_interface_velocity_human_m_s=prefix_u,
            predicted_prefix_interface_rotation_human_rad=prefix_theta,
            predicted_prefix_interface_angular_velocity_human_rad_s=prefix_omega,
            predicted_prefix_executable_wrench_world=prefix_command,
        )

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        actions = np.asarray(actions_nm, dtype=float)
        # The inherited solver asks for the selected first action once more
        # after CEM, and the full-horizon rollout asks for the already-screened
        # feasible subset. Reuse exact cached rows instead of repeating loaded
        # execution plus the 80-substep V2 prefix propagation.
        allow_cached_subset = self._reuse_cached_subsets or len(actions) == 1
        cached = (
            self._cached_prediction_for_actions(actions)
            if allow_cached_subset
            else None
        )
        if cached is not None:
            self._last_actions = actions.copy()
            self._last_prediction = cached
            return cached
        prediction = self.predictor.predict_batch(
            self.interface_state, self.executable_preview(actions)
        )
        prediction = self._apply_v2_prefix_acceleration_screen(actions, prediction)
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
        initial_support_nm: np.ndarray | None = None,
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
            first_support = (
                np.asarray(action_resolver(initial_states), dtype=float)
                if initial_support_nm is None
                else np.broadcast_to(
                    np.asarray(initial_support_nm, dtype=float), (count, 2)
                )
            )
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
    state_rad_rad_s: np.ndarray | None = None,
    acceleration_limits_rad_s2: np.ndarray | None = None,
    use_optimized_prefix_numpy: bool = True,
    capture_prefix_diagnostics: bool = False,
    prefix_backend: str = "numpy",
    capture_prefix_substeps: bool = False,
) -> InterfaceAwareFirstActionBatchPreview:
    """Compose one batched executable-command and physical-interface screen."""

    return InterfaceAwareFirstActionBatchPreview(
        executable_preview,
        predictor,
        interface_state,
        q_rad,
        human_model,
        cuff_allocator,
        state_rad_rad_s=state_rad_rad_s,
        acceleration_limits_rad_s2=acceleration_limits_rad_s2,
        use_optimized_prefix_numpy=use_optimized_prefix_numpy,
        capture_prefix_diagnostics=capture_prefix_diagnostics,
        prefix_backend=prefix_backend,
        capture_prefix_substeps=capture_prefix_substeps,
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
