"""Offline/shadow-only Stage-5 cuff-interface identification prototype.

The prototype deliberately predicts *future deployable measurements*.  A
candidate interface model is never allowed to manufacture a deformation or a
Human state and then score itself against that same reconstruction.  The
window-initial Human/interface coordinates are nuisance states with arrival
priors, while future robot-cuff pose/twist and cuff wrench are the measurement
residuals.

Nothing in this module is connected to Goal-MPC, the observer, task decisions,
or execution.  MuJoCo truth is not represented in the service input types.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)

from .config import STAGE5_ROOT
from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    ControllerNominalInterfaceParameters,
    InterfaceAwareHumanStateObserver,
)
from .geometry import STAGE5_GEOMETRY
from .human import STAGE5_HUMAN


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_interface_identification_v1.json"
PARAMETER_NAMES = ("alpha_t", "alpha_r", "alpha_d")


def _finite_vector(values: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result.copy()


@dataclass(frozen=True)
class InterfaceParameterScales:
    """Low-dimensional candidate scaling of the frozen controller nominal model."""

    alpha_t: float = 1.0
    alpha_r: float = 1.0
    alpha_d: float = 1.0

    def __post_init__(self) -> None:
        values = self.as_array()
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("interface parameter scales must be finite and positive")

    def as_array(self) -> np.ndarray:
        return np.asarray([self.alpha_t, self.alpha_r, self.alpha_d], dtype=float)

    @classmethod
    def from_array(cls, values: Any) -> "InterfaceParameterScales":
        array = _finite_vector(values, (3,), "interface parameter scales")
        return cls(*[float(value) for value in array])

    def scaled_parameters(
        self,
        nominal: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
        *,
        model_version: str = "stage5_interface_id_candidate",
    ) -> ControllerNominalInterfaceParameters:
        return replace(
            nominal,
            model_version=model_version,
            translation_stiffness_n_m=tuple(
                float(self.alpha_t * value)
                for value in nominal.translation_stiffness_n_m
            ),
            rotation_stiffness_nm_rad=float(
                self.alpha_r * nominal.rotation_stiffness_nm_rad
            ),
            translation_damping_ns_m=tuple(
                float(self.alpha_d * value)
                for value in nominal.translation_damping_ns_m
            ),
            rotation_damping_nms_rad=float(
                self.alpha_d * nominal.rotation_damping_nms_rad
            ),
        )


@dataclass(frozen=True)
class InactiveTrustConfig:
    minimum_future_validation_samples: int
    minimum_relative_prediction_improvement: float
    maximum_data_condition_number: float
    publication_smoothing_alpha: float
    maximum_publication_step_fraction_of_parameter_span: float
    control_publication_enabled: bool = False

    def __post_init__(self) -> None:
        if self.minimum_future_validation_samples < 1:
            raise ValueError("future validation requires at least one sample")
        if not 0.0 < self.minimum_relative_prediction_improvement < 1.0:
            raise ValueError("relative prediction improvement must lie in (0, 1)")
        if self.maximum_data_condition_number <= 1.0:
            raise ValueError("data condition limit must exceed one")
        if not 0.0 < self.publication_smoothing_alpha <= 1.0:
            raise ValueError("publication smoothing must lie in (0, 1]")
        if not 0.0 < self.maximum_publication_step_fraction_of_parameter_span <= 1.0:
            raise ValueError("publication step fraction must lie in (0, 1]")
        if self.control_publication_enabled:
            raise ValueError("Interface Identification v1 must remain shadow-only")


@dataclass(frozen=True)
class InterfaceIdentificationConfig:
    lower: np.ndarray
    upper: np.ndarray
    parameter_prior_scale: np.ndarray
    parameter_prior_weight: float
    initial_state_prior_scale: np.ndarray
    initial_state_prior_weight: float
    measurement_scale: np.ndarray
    fit_window_s: float
    validation_embargo_s: float
    validation_window_s: float
    window_length_audit_s: tuple[float, ...]
    maximum_function_evaluations: int
    finite_difference_relative_step: float
    data_rank_relative_tolerance: float
    multistart_parameter_scales: tuple[tuple[float, float, float], ...]
    multistart_initial_state_offsets_in_prior_scales: tuple[tuple[float, ...], ...]
    inactive_trust: InactiveTrustConfig
    active_in_control: bool = False
    truth_available_to_service: bool = False

    def __post_init__(self) -> None:
        for name in ("lower", "upper", "parameter_prior_scale"):
            object.__setattr__(self, name, _finite_vector(getattr(self, name), (3,), name))
        object.__setattr__(
            self,
            "initial_state_prior_scale",
            _finite_vector(self.initial_state_prior_scale, (16,), "initial state prior scale"),
        )
        object.__setattr__(
            self,
            "measurement_scale",
            _finite_vector(self.measurement_scale, (18,), "measurement residual scale"),
        )
        if np.any(self.lower <= 0.0) or np.any(self.upper <= self.lower):
            raise ValueError("parameter bounds must be positive and ordered")
        if np.any(self.parameter_prior_scale <= 0.0):
            raise ValueError("parameter prior scale must be positive")
        if np.any(self.initial_state_prior_scale <= 0.0):
            raise ValueError("initial-state prior scale must be positive")
        if np.any(self.measurement_scale <= 0.0):
            raise ValueError("measurement scales must be positive")
        if self.active_in_control or self.truth_available_to_service:
            raise ValueError("Interface Identification v1 is shadow-only and truth-free")
        if len(self.multistart_parameter_scales) != len(
            self.multistart_initial_state_offsets_in_prior_scales
        ):
            raise ValueError("parameter and initial-state multistarts must align")
        if any(
            len(offset) != 16
            for offset in self.multistart_initial_state_offsets_in_prior_scales
        ):
            raise ValueError("every initial-state multistart offset must have 16 values")


def load_interface_identification_config(
    path: Path = CONFIG_PATH,
) -> InterfaceIdentificationConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_interface_identification_v1":
        raise ValueError("unexpected interface-identification schema")
    residual = payload["measurement_residual_scale"]
    measurement_scale = np.concatenate(
        [
            residual["robot_position_m"],
            residual["robot_rotation_rad"],
            residual["robot_linear_velocity_m_s"],
            residual["robot_angular_velocity_rad_s"],
            residual["cuff_force_n"],
            residual["cuff_moment_nm"],
        ]
    )
    trust = payload["inactive_trust"]
    return InterfaceIdentificationConfig(
        lower=np.asarray(payload["parameter_bounds"]["lower"], dtype=float),
        upper=np.asarray(payload["parameter_bounds"]["upper"], dtype=float),
        parameter_prior_scale=np.asarray(payload["parameter_prior_scale"], dtype=float),
        parameter_prior_weight=float(payload["parameter_prior_weight"]),
        initial_state_prior_scale=np.asarray(payload["initial_state_prior_scale"], dtype=float),
        initial_state_prior_weight=float(payload["initial_state_prior_weight"]),
        measurement_scale=np.asarray(measurement_scale, dtype=float),
        fit_window_s=float(payload["fit_window_s"]),
        validation_embargo_s=float(payload["validation_embargo_s"]),
        validation_window_s=float(payload["validation_window_s"]),
        window_length_audit_s=tuple(float(v) for v in payload["window_length_audit_s"]),
        maximum_function_evaluations=int(payload["maximum_function_evaluations"]),
        finite_difference_relative_step=float(payload["finite_difference_relative_step"]),
        data_rank_relative_tolerance=float(payload["data_rank_relative_tolerance"]),
        multistart_parameter_scales=tuple(
            tuple(float(v) for v in row)
            for row in payload["multistart_parameter_scales"]
        ),
        multistart_initial_state_offsets_in_prior_scales=tuple(
            tuple(float(v) for v in row)
            for row in payload["multistart_initial_state_offsets_in_prior_scales"]
        ),
        inactive_trust=InactiveTrustConfig(**trust),
        active_in_control=bool(payload["active_in_control"]),
        truth_available_to_service=bool(payload["truth_available_to_service"]),
    )


@dataclass(frozen=True)
class InterfaceIdentificationMeasurement:
    """One truth-free service sample at the deployable measurement boundary."""

    sample_timestamp_s: float
    arrival_timestamp_s: float
    robot_cuff_position_world_m: np.ndarray
    robot_cuff_rotation_world: np.ndarray
    robot_cuff_linear_velocity_world_m_s: np.ndarray
    robot_cuff_angular_velocity_world_rad_s: np.ndarray
    measured_cuff_force_world_n: np.ndarray
    measured_cuff_moment_world_nm: np.ndarray
    executed_command_wrench_world: np.ndarray
    previous_executed_command_wrench_world: np.ndarray
    prediction_base_drive_world_n: np.ndarray
    prediction_base_angular_drive_world_nm: np.ndarray
    fixed_human_model_version: str

    def __post_init__(self) -> None:
        if not np.isfinite(self.sample_timestamp_s) or not np.isfinite(self.arrival_timestamp_s):
            raise ValueError("identification timestamps must be finite")
        if self.arrival_timestamp_s < self.sample_timestamp_s - 1.0e-12:
            raise ValueError("arrival timestamp cannot precede sample timestamp")
        vectors = {
            "robot_cuff_position_world_m": ("robot cuff position", (3,)),
            "robot_cuff_rotation_world": ("robot cuff rotation", (3, 3)),
            "robot_cuff_linear_velocity_world_m_s": ("robot cuff linear velocity", (3,)),
            "robot_cuff_angular_velocity_world_rad_s": ("robot cuff angular velocity", (3,)),
            "measured_cuff_force_world_n": ("measured cuff force", (3,)),
            "measured_cuff_moment_world_nm": ("measured cuff moment", (3,)),
            "executed_command_wrench_world": ("executed command wrench", (6,)),
            "previous_executed_command_wrench_world": ("previous executed command wrench", (6,)),
            "prediction_base_drive_world_n": ("base drive", (3,)),
            "prediction_base_angular_drive_world_nm": ("base angular drive", (3,)),
        }
        for field_name, (label, shape) in vectors.items():
            object.__setattr__(
                self,
                field_name,
                _finite_vector(getattr(self, field_name), shape, label),
            )
        rotation = np.asarray(self.robot_cuff_rotation_world)
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1.0e-7):
            raise ValueError("robot cuff rotation must be orthonormal")
        if not self.fixed_human_model_version:
            raise ValueError("fixed Human model version is required")

    # Read-only aliases let the existing deployable nominal observer consume
    # this service record without a second measurement authority.
    @property
    def sample_time_s(self) -> float:
        return self.sample_timestamp_s

    @property
    def arrival_time_s(self) -> float:
        return self.arrival_timestamp_s

    @property
    def attachment_position_m(self) -> np.ndarray:
        return self.robot_cuff_position_world_m

    @property
    def attachment_rotation_matrix(self) -> np.ndarray:
        return self.robot_cuff_rotation_world

    @property
    def attachment_velocity_m_s(self) -> np.ndarray:
        return self.robot_cuff_linear_velocity_world_m_s

    @property
    def attachment_angular_velocity_rad_s(self) -> np.ndarray:
        return self.robot_cuff_angular_velocity_world_rad_s

    @property
    def cuff_force_vector_n(self) -> np.ndarray:
        return self.measured_cuff_force_world_n

    @property
    def cuff_moment_vector_nm(self) -> np.ndarray:
        return self.measured_cuff_moment_world_nm


def fixed_stage5_human_model() -> BaseParameterHumanModel:
    """Return the same fixed registered Human/geometry model used by Stage 5."""

    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    geometry = PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )
    return BaseParameterHumanModel(
        geometry, nominal_base_parameters(STAGE5_HUMAN), STAGE5_HUMAN
    )


@dataclass(frozen=True)
class InterfaceIdentificationSeries:
    """Aligned deployable data plus candidate-independent arrival warm states."""

    time_s: np.ndarray
    phase: np.ndarray
    robot_measurement: np.ndarray
    measured_wrench_world: np.ndarray
    executed_wrench_world: np.ndarray
    base_drive_world_n: np.ndarray
    base_angular_drive_world_nm: np.ndarray
    arrival_human_state: np.ndarray
    arrival_interface_state: np.ndarray
    source: str
    legacy_measurement_reconstruction: bool
    reconstruction_closure_max_abs: float

    def __post_init__(self) -> None:
        n = len(self.time_s)
        shapes = {
            "robot_measurement": (n, 12),
            "measured_wrench_world": (n, 6),
            "executed_wrench_world": (n, 6),
            "base_drive_world_n": (n, 3),
            "base_angular_drive_world_nm": (n, 3),
            "arrival_human_state": (n, 4),
            "arrival_interface_state": (n, 12),
        }
        _finite_vector(self.time_s, (n,), "time")
        if np.any(np.diff(self.time_s) <= 0.0):
            raise ValueError("identification series timestamps must increase")
        if np.asarray(self.phase).shape != (n,):
            raise ValueError("phase must align with time")
        for name, shape in shapes.items():
            _finite_vector(getattr(self, name), shape, name)

    @property
    def output_measurement(self) -> np.ndarray:
        return np.column_stack([self.robot_measurement, self.measured_wrench_world])

    @classmethod
    def from_saved_trace(
        cls,
        path: Path,
        human_model: BaseParameterHumanModel | None = None,
    ) -> "InterfaceIdentificationSeries":
        """Adapt legacy saved evidence without exposing evaluation truth to fitting.

        Old mismatch traces did not retain the raw robot pose/twist.  The
        nominal observer's stored Human and interface coordinates are composed
        once to recover the original robot-side measurement.  This operation
        is independent of every fitted candidate; only the resulting robot
        measurement is used as the future residual target.
        """

        model = fixed_stage5_human_model() if human_model is None else human_model
        with np.load(Path(path), allow_pickle=False) as trace:
            time_s = np.asarray(trace["time_s"], dtype=float)
            human = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
            interface = np.column_stack(
                [
                    trace["estimated_interface_translation_human_m"],
                    trace["estimated_interface_velocity_human_m_s"],
                    trace["estimated_interface_rotation_human_rad"],
                    trace["estimated_interface_angular_velocity_human_rad_s"],
                ]
            )
            reconstructed_robot = []
            closure = []
            for state, latent in zip(human, interface, strict=True):
                x, velocity, theta, omega = np.split(latent, 4)
                pose = model.geometry.cuff_pose(state[:2])
                human_linear, human_angular = model.geometry.cuff_velocity(
                    state[:2], state[2:]
                )
                lever_world = pose.rotation @ x
                robot_rotation = pose.rotation @ Rotation.from_rotvec(theta).as_matrix()
                robot_position = pose.translation + lever_world
                robot_linear = (
                    human_linear
                    + np.cross(human_angular, lever_world)
                    + pose.rotation @ velocity
                )
                robot_angular = human_angular + pose.rotation @ omega
                reconstructed_robot.append(
                    np.concatenate(
                        [
                            robot_position,
                            Rotation.from_matrix(robot_rotation).as_rotvec(),
                            robot_linear,
                            robot_angular,
                        ]
                    )
                )
                # Algebraic round-trip closure: the same fixed measurement must
                # recover the stored Human-side position relation.
                closure.append(np.max(np.abs(robot_position - pose.translation - lever_world)))
            reconstructed_robot = np.asarray(reconstructed_robot, dtype=float)
            raw_keys = (
                "deployable_robot_cuff_position_world_m",
                "deployable_robot_cuff_rotation_world",
                "deployable_robot_cuff_linear_velocity_world_m_s",
                "deployable_robot_cuff_angular_velocity_world_rad_s",
            )
            has_raw_robot_measurement = all(key in trace.files for key in raw_keys)
            if has_raw_robot_measurement:
                raw_rotation = np.asarray(trace[raw_keys[1]], dtype=float)
                robot_measurement = np.column_stack(
                    [
                        trace[raw_keys[0]],
                        Rotation.from_matrix(raw_rotation).as_rotvec(),
                        trace[raw_keys[2]],
                        trace[raw_keys[3]],
                    ]
                )
                closure.append(
                    float(np.max(np.abs(robot_measurement - reconstructed_robot)))
                )
            else:
                robot_measurement = reconstructed_robot
            has_raw_wrench_measurement = all(
                key in trace.files
                for key in (
                    "deployable_measured_cuff_force_world_n",
                    "deployable_measured_cuff_moment_world_nm",
                )
            )
            if has_raw_wrench_measurement:
                measured_wrench = np.column_stack(
                    [
                        trace["deployable_measured_cuff_force_world_n"],
                        trace["deployable_measured_cuff_moment_world_nm"],
                    ]
                )
            else:
                nominal = CONTROLLER_NOMINAL_INTERFACE
                k = np.asarray(nominal.translation_stiffness_n_m)
                d = np.asarray(nominal.translation_damping_ns_m)
                reconstructed_wrench = []
                for state, latent in zip(human, interface, strict=True):
                    x, velocity, theta, omega = np.split(latent, 4)
                    rotation = model.geometry.cuff_pose(state[:2]).rotation
                    force_human = k * x + d * velocity
                    couple_human = (
                        nominal.rotation_stiffness_nm_rad * theta
                        + nominal.rotation_damping_nms_rad * omega
                    )
                    moment_human = couple_human + np.cross(x, force_human)
                    reconstructed_wrench.append(
                        np.r_[rotation @ force_human, rotation @ moment_human]
                    )
                measured_wrench = np.asarray(reconstructed_wrench, dtype=float)
            return cls(
                time_s=time_s,
                phase=np.asarray(trace["task_phase"], dtype=str),
                robot_measurement=robot_measurement,
                measured_wrench_world=measured_wrench,
                executed_wrench_world=np.asarray(
                    trace["executed_command_wrench_world"], dtype=float
                ),
                base_drive_world_n=np.asarray(
                    trace["prediction_base_drive_world_n"], dtype=float
                ),
                base_angular_drive_world_nm=np.asarray(
                    trace["prediction_base_angular_drive_world_nm"], dtype=float
                ),
                arrival_human_state=human,
                arrival_interface_state=interface,
                source=str(Path(path)),
                legacy_measurement_reconstruction=not has_raw_robot_measurement,
                reconstruction_closure_max_abs=float(max(closure, default=0.0)),
            )


class ShadowInterfaceIdentificationService:
    """Causal truth-free buffer for a future shadow-online identifier.

    The nominal observer output is retained only as a numerical arrival prior.
    The scoring target remains the raw robot pose/twist and measured wrench in
    ``InterfaceIdentificationMeasurement``.
    """

    def __init__(
        self,
        human_model: BaseParameterHumanModel,
        *,
        nominal_interface: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
    ) -> None:
        self.human_model = human_model
        self.nominal_interface = nominal_interface
        self.observer = InterfaceAwareHumanStateObserver(nominal_interface)
        self._records: list[InterfaceIdentificationMeasurement] = []
        self._phase: list[str] = []
        self._human_arrival: list[np.ndarray] = []
        self._interface_arrival: list[np.ndarray] = []

    def ingest(
        self,
        measurement: InterfaceIdentificationMeasurement,
        *,
        phase: str,
    ) -> None:
        if self._records and (
            measurement.sample_timestamp_s
            <= self._records[-1].sample_timestamp_s + 1.0e-12
        ):
            raise ValueError("interface identification samples must be causal")
        if self._records and not np.allclose(
            measurement.previous_executed_command_wrench_world,
            self._records[-1].executed_command_wrench_world,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise ValueError("executed-command history is discontinuous")
        observation, interface = self.observer.update(
            measurement,
            self.human_model,
            human_model_version=measurement.fixed_human_model_version,
        )
        self._records.append(measurement)
        self._phase.append(str(phase))
        self._human_arrival.append(observation.as_array())
        self._interface_arrival.append(
            np.concatenate(
                [
                    interface.displacement_human_m,
                    interface.velocity_human_m_s,
                    interface.rotation_error_human_rad,
                    interface.angular_velocity_human_rad_s,
                ]
            )
        )

    def series(self) -> InterfaceIdentificationSeries:
        if len(self._records) < 2:
            raise RuntimeError("at least two samples are required")
        robot = np.asarray(
            [
                np.concatenate(
                    [
                        item.robot_cuff_position_world_m,
                        Rotation.from_matrix(item.robot_cuff_rotation_world).as_rotvec(),
                        item.robot_cuff_linear_velocity_world_m_s,
                        item.robot_cuff_angular_velocity_world_rad_s,
                    ]
                )
                for item in self._records
            ],
            dtype=float,
        )
        return InterfaceIdentificationSeries(
            time_s=np.asarray(
                [item.sample_timestamp_s for item in self._records], dtype=float
            ),
            phase=np.asarray(self._phase, dtype=str),
            robot_measurement=robot,
            measured_wrench_world=np.asarray(
                [
                    np.r_[
                        item.measured_cuff_force_world_n,
                        item.measured_cuff_moment_world_nm,
                    ]
                    for item in self._records
                ],
                dtype=float,
            ),
            executed_wrench_world=np.asarray(
                [item.executed_command_wrench_world for item in self._records],
                dtype=float,
            ),
            base_drive_world_n=np.asarray(
                [item.prediction_base_drive_world_n for item in self._records],
                dtype=float,
            ),
            base_angular_drive_world_nm=np.asarray(
                [item.prediction_base_angular_drive_world_nm for item in self._records],
                dtype=float,
            ),
            arrival_human_state=np.asarray(self._human_arrival, dtype=float),
            arrival_interface_state=np.asarray(self._interface_arrival, dtype=float),
            source="shadow_interface_identification_service",
            legacy_measurement_reconstruction=False,
            reconstruction_closure_max_abs=0.0,
        )


@dataclass(frozen=True)
class InterfaceIdentifiabilityDiagnostics:
    singular_values: np.ndarray
    rank: int
    condition_number: float
    correlation: np.ndarray
    maximum_abs_parameter_correlation: float
    parameter_information_retained_after_latent_projection: np.ndarray
    regularization_included: bool = False


@dataclass(frozen=True)
class InterfaceFitResult:
    success: bool
    reason: str
    parameter_scales: InterfaceParameterScales
    initial_state: np.ndarray
    fit_normalized_rmse: float
    validation_normalized_rmse: float
    nominal_validation_normalized_rmse: float
    validation_relative_improvement: float
    validation_component_normalized_rmse: Mapping[str, float]
    nominal_validation_component_normalized_rmse: Mapping[str, float]
    optimizer_nfev: int
    optimizer_cost: float
    bound_hit: bool
    fit_start_time_s: float
    fit_end_time_s: float
    validation_start_time_s: float
    validation_end_time_s: float
    validation_sample_count: int
    identifiability: InterfaceIdentifiabilityDiagnostics
    multistart_solutions: tuple[Mapping[str, Any], ...]
    last_valid_fallback_used: bool


@dataclass(frozen=True)
class InterfacePredictionRollout:
    """Diagnostic rollout of the exact identification prediction model.

    The public estimator scores only ``deployable_measurements``.  The latent
    arrays are exposed solely so offline model-form audits can compare the
    predictor with evaluation truth without duplicating or subtly changing the
    transition equations used by identification.
    """

    deployable_measurements: np.ndarray
    human_state: np.ndarray
    interface_state: np.ndarray
    base_drive_world_n: np.ndarray
    base_angular_drive_world_nm: np.ndarray


class WindowedInterfacePredictionErrorIdentifier:
    """Small single-shooting joint initial-state/parameter MHE prototype."""

    def __init__(
        self,
        config: InterfaceIdentificationConfig | None = None,
        *,
        human_model: BaseParameterHumanModel | None = None,
        nominal_interface: ControllerNominalInterfaceParameters = CONTROLLER_NOMINAL_INTERFACE,
    ) -> None:
        self.config = load_interface_identification_config() if config is None else config
        self.human_model = fixed_stage5_human_model() if human_model is None else human_model
        self.nominal_interface = nominal_interface
        self.last_valid = InterfaceParameterScales()

    def _step_interface(
        self,
        position: np.ndarray,
        velocity: np.ndarray,
        drive: np.ndarray,
        stiffness: np.ndarray,
        damping: np.ndarray,
        mass: np.ndarray,
        dt_s: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        omega_n = np.sqrt(stiffness / mass)
        alpha = damping / (2.0 * mass)
        omega_d = np.sqrt(np.maximum(omega_n**2 - alpha**2, 1.0e-12))
        equilibrium = drive / stiffness
        z0 = position - equilibrium
        sample_time = np.asarray([0.0, 0.5 * dt_s, dt_s])[:, None]
        decay = np.exp(-alpha[None, :] * sample_time)
        cosine = np.cos(omega_d[None, :] * sample_time)
        sine = np.sin(omega_d[None, :] * sample_time)
        sampled_position = equilibrium + decay * (
            z0 * cosine + (velocity + alpha * z0) / omega_d * sine
        )
        sampled_velocity = decay * (
            velocity * cosine
            - (alpha * velocity + omega_n**2 * z0) / omega_d * sine
        )
        mean_force = drive - mass * (sampled_velocity[-1] - velocity) / dt_s
        sampled_force = stiffness * sampled_position + damping * sampled_velocity
        return (
            sampled_position[-1],
            sampled_velocity[-1],
            mean_force,
            sampled_position,
            sampled_force,
        )

    def measurement_from_state(
        self,
        parameters: InterfaceParameterScales,
        state: np.ndarray,
    ) -> np.ndarray:
        """Map one joint Human/interface state to deployable measurements."""

        joint_state = _finite_vector(state, (16,), "joint MHE state")
        interface = parameters.scaled_parameters(self.nominal_interface)
        qdq = joint_state[:4]
        x, velocity, theta, omega = np.split(joint_state[4:], 4)
        pose = self.human_model.geometry.cuff_pose(qdq[:2])
        human_linear, human_angular = self.human_model.geometry.cuff_velocity(
            qdq[:2], qdq[2:]
        )
        lever_world = pose.rotation @ x
        robot_rotation = pose.rotation @ Rotation.from_rotvec(theta).as_matrix()
        robot_position = pose.translation + lever_world
        robot_linear = (
            human_linear
            + np.cross(human_angular, lever_world)
            + pose.rotation @ velocity
        )
        robot_angular = human_angular + pose.rotation @ omega
        force_human = (
            np.asarray(interface.translation_stiffness_n_m) * x
            + np.asarray(interface.translation_damping_ns_m) * velocity
        )
        moment_human = (
            interface.rotation_stiffness_nm_rad * theta
            + interface.rotation_damping_nms_rad * omega
            + np.cross(x, force_human)
        )
        return np.concatenate(
            [
                robot_position,
                Rotation.from_matrix(robot_rotation).as_rotvec(),
                robot_linear,
                robot_angular,
                pose.rotation @ force_human,
                pose.rotation @ moment_human,
            ]
        )

    def predict_rollout(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> InterfacePredictionRollout:
        """Propagate the exact identification model after the window start."""

        state = _finite_vector(initial_state, (16,), "joint MHE initial state")
        if start_index < 0 or start_index + step_count >= len(series.time_s):
            raise ValueError("prediction window is outside the saved series")
        interface = parameters.scaled_parameters(self.nominal_interface)
        qdq = state[:4].copy()
        x, velocity, theta, omega = [item.copy() for item in np.split(state[4:], 4)]
        k = np.asarray(interface.translation_stiffness_n_m)
        d = np.asarray(interface.translation_damping_ns_m)
        mass = np.asarray(interface.translation_effective_mass_kg)
        kr = np.full(3, interface.rotation_stiffness_nm_rad)
        dr = np.full(3, interface.rotation_damping_nms_rad)
        inertia = np.full(3, interface.rotation_effective_inertia_kg_m2)
        drive_world = series.base_drive_world_n[start_index].copy()
        angular_drive_world = series.base_angular_drive_world_nm[start_index].copy()
        previous_command = series.executed_wrench_world[start_index].copy()
        outputs: list[np.ndarray] = []
        human_states: list[np.ndarray] = []
        interface_states: list[np.ndarray] = []
        drive_states: list[np.ndarray] = []
        angular_drive_states: list[np.ndarray] = []
        for offset in range(step_count):
            sample_index = start_index + offset + 1
            dt_s = float(series.time_s[sample_index] - series.time_s[sample_index - 1])
            command = series.executed_wrench_world[sample_index]
            drive_world += command[:3] - previous_command[:3]
            angular_drive_world += command[3:] - previous_command[3:]
            previous_command = command
            human_pose = self.human_model.geometry.cuff_pose(qdq[:2])
            human_rotation = human_pose.rotation
            x, velocity, mean_force_human, sampled_x, sampled_force_human = (
                self._step_interface(
                    x,
                    velocity,
                    human_rotation.T @ drive_world,
                    k,
                    d,
                    mass,
                    dt_s,
                )
            )
            theta, omega, _, _, sampled_couple_human = self._step_interface(
                theta,
                omega,
                human_rotation.T @ angular_drive_world,
                kr,
                dr,
                inertia,
                dt_s,
            )
            sampled_moment_human = sampled_couple_human + np.cross(
                sampled_x, sampled_force_human
            )
            mean_moment_human = np.mean(sampled_moment_human, axis=0)
            mean_force_world = human_rotation @ mean_force_human
            mean_moment_world = human_rotation @ mean_moment_human
            generalized_input = self.human_model.geometry.generalized_input_from_wrench(
                qdq[:2], mean_force_world, mean_moment_world
            )
            next_qdq = self.human_model.step_dynamics(qdq, generalized_input, dt_s)
            next_rotation = self.human_model.geometry.cuff_pose(next_qdq[:2]).rotation
            frame_change = next_rotation.T @ human_rotation
            x = frame_change @ x
            velocity = frame_change @ velocity
            theta = frame_change @ theta
            omega = frame_change @ omega
            qdq = next_qdq
            joint_state = np.r_[qdq, x, velocity, theta, omega]
            outputs.append(self.measurement_from_state(parameters, joint_state))
            human_states.append(qdq.copy())
            interface_states.append(np.r_[x, velocity, theta, omega])
            drive_states.append(drive_world.copy())
            angular_drive_states.append(angular_drive_world.copy())
        return InterfacePredictionRollout(
            deployable_measurements=np.asarray(outputs, dtype=float),
            human_state=np.asarray(human_states, dtype=float),
            interface_state=np.asarray(interface_states, dtype=float),
            base_drive_world_n=np.asarray(drive_states, dtype=float),
            base_angular_drive_world_nm=np.asarray(angular_drive_states, dtype=float),
        )

    def predict_measurements(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameters: InterfaceParameterScales,
        initial_state: np.ndarray,
    ) -> np.ndarray:
        """Predict robot pose/twist and wrench after the window start."""

        return self.predict_rollout(
            series, start_index, step_count, parameters, initial_state
        ).deployable_measurements

    def fit_initial_state_for_fixed_parameters(
        self,
        series: InterfaceIdentificationSeries,
        *,
        start_index: int,
        fit_window_s: float,
        parameters: InterfaceParameterScales,
    ) -> np.ndarray:
        """Fit only the nuisance window-initial state from deployable data."""

        dt_s = float(np.median(np.diff(series.time_s)))
        fit_steps = int(round(float(fit_window_s) / dt_s))
        if start_index + fit_steps >= len(series.time_s):
            raise ValueError("fixed-parameter fit window exceeds the saved trace")
        prior = np.r_[
            series.arrival_human_state[start_index],
            series.arrival_interface_state[start_index],
        ]
        decision = self._fit_fixed_parameters(
            series,
            start_index,
            fit_steps,
            parameters.as_array(),
            prior,
        )
        return np.asarray(decision[3:], dtype=float)

    def _measurement_residual(
        self,
        decision: np.ndarray,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
    ) -> np.ndarray:
        parameters = InterfaceParameterScales.from_array(decision[:3])
        prediction = self.predict_measurements(
            series, start_index, step_count, parameters, decision[3:]
        )
        target = series.output_measurement[start_index + 1 : start_index + step_count + 1]
        difference = self._measurement_difference(prediction, target)
        return (difference / self.config.measurement_scale).reshape(-1)

    @staticmethod
    def _measurement_difference(
        prediction: np.ndarray, target: np.ndarray
    ) -> np.ndarray:
        difference = np.asarray(prediction, dtype=float) - np.asarray(
            target, dtype=float
        )
        # Rotation is stored as a rotvec only for compact arrays.  Score its
        # proper relative rotation rather than subtracting wrapped coordinates.
        predicted_rotation = Rotation.from_rotvec(prediction[:, 3:6])
        target_rotation = Rotation.from_rotvec(target[:, 3:6])
        difference[:, 3:6] = (
            target_rotation.inv() * predicted_rotation
        ).as_rotvec()
        return difference

    def _joint_residual(
        self,
        decision: np.ndarray,
        series: InterfaceIdentificationSeries,
        start_index: int,
        step_count: int,
        parameter_prior: np.ndarray,
        initial_state_prior: np.ndarray,
        *,
        fix_parameters: bool,
    ) -> np.ndarray:
        data = self._measurement_residual(decision, series, start_index, step_count)
        parameter = np.asarray(decision[:3], dtype=float)
        state = np.asarray(decision[3:], dtype=float)
        regularization = [
            np.sqrt(self.config.initial_state_prior_weight)
            * (state - initial_state_prior)
            / self.config.initial_state_prior_scale
        ]
        if not fix_parameters:
            regularization.insert(
                0,
                np.sqrt(self.config.parameter_prior_weight)
                * (parameter - parameter_prior)
                / self.config.parameter_prior_scale,
            )
        return np.concatenate([data, *regularization])

    def _bounds(self, parameter: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        q_lower = np.asarray(self.human_model.q_min_rad, dtype=float)
        q_upper = np.asarray(self.human_model.q_max_rad, dtype=float)
        lower_state = np.concatenate(
            [q_lower, np.full(2, -3.0), np.full(3, -0.03), np.full(3, -1.0), np.full(3, -0.30), np.full(3, -10.0)]
        )
        upper_state = np.concatenate(
            [q_upper, np.full(2, 3.0), np.full(3, 0.03), np.full(3, 1.0), np.full(3, 0.30), np.full(3, 10.0)]
        )
        return np.r_[parameter, lower_state], np.r_[parameter, upper_state]

    def _free_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        lower, upper = self._bounds(self.config.lower)
        lower[:3] = self.config.lower
        upper[:3] = self.config.upper
        return lower, upper

    def _fit_fixed_parameters(
        self,
        series: InterfaceIdentificationSeries,
        start_index: int,
        fit_steps: int,
        parameters: np.ndarray,
        initial_state_prior: np.ndarray,
    ) -> np.ndarray:
        epsilon = 1.0e-12
        lower, upper = self._bounds(parameters)
        lower[:3] -= epsilon
        upper[:3] += epsilon
        initial = np.r_[parameters, initial_state_prior]
        result = least_squares(
            lambda z: self._joint_residual(
                z,
                series,
                start_index,
                fit_steps,
                parameters,
                initial_state_prior,
                fix_parameters=True,
            ),
            initial,
            bounds=(lower, upper),
            max_nfev=self.config.maximum_function_evaluations,
            x_scale="jac",
        )
        return np.asarray(result.x, dtype=float)

    def _numerical_data_jacobian(
        self,
        decision: np.ndarray,
        series: InterfaceIdentificationSeries,
        start_index: int,
        fit_steps: int,
    ) -> np.ndarray:
        base = np.asarray(decision, dtype=float)
        columns = []
        for index in range(len(base)):
            step = self.config.finite_difference_relative_step * max(
                abs(base[index]),
                self.config.parameter_prior_scale[index] if index < 3 else self.config.initial_state_prior_scale[index - 3],
            )
            plus = base.copy()
            minus = base.copy()
            plus[index] += step
            minus[index] -= step
            denominator = plus[index] - minus[index]
            columns.append(
                (
                    self._measurement_residual(plus, series, start_index, fit_steps)
                    - self._measurement_residual(minus, series, start_index, fit_steps)
                )
                / denominator
            )
        return np.column_stack(columns)

    def identifiability_diagnostics(
        self,
        decision: np.ndarray,
        series: InterfaceIdentificationSeries,
        start_index: int,
        fit_steps: int,
    ) -> InterfaceIdentifiabilityDiagnostics:
        jacobian = self._numerical_data_jacobian(
            decision, series, start_index, fit_steps
        )
        parameter_jacobian = jacobian[:, :3]
        nuisance_jacobian = jacobian[:, 3:]
        nuisance_coefficients = np.linalg.lstsq(
            nuisance_jacobian, parameter_jacobian, rcond=1.0e-10
        )[0]
        effective = parameter_jacobian - nuisance_jacobian @ nuisance_coefficients
        singular = np.linalg.svd(effective, compute_uv=False)
        tolerance = (
            self.config.data_rank_relative_tolerance * singular[0]
            if len(singular) and singular[0] > 0.0
            else 0.0
        )
        rank = int(np.sum(singular > tolerance))
        condition = (
            float(singular[0] / singular[-1])
            if len(singular) and singular[-1] > tolerance
            else float("inf")
        )
        covariance = np.linalg.pinv(effective.T @ effective, rcond=1.0e-12)
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        denominator = np.outer(std, std)
        correlation = np.divide(
            covariance,
            denominator,
            out=np.full_like(covariance, np.nan),
            where=denominator > 0.0,
        )
        off_diagonal = correlation.copy()
        np.fill_diagonal(off_diagonal, 0.0)
        retained = np.linalg.norm(effective, axis=0) / np.maximum(
            np.linalg.norm(parameter_jacobian, axis=0), 1.0e-15
        )
        return InterfaceIdentifiabilityDiagnostics(
            singular_values=singular,
            rank=rank,
            condition_number=condition,
            correlation=correlation,
            maximum_abs_parameter_correlation=float(np.nanmax(np.abs(off_diagonal))),
            parameter_information_retained_after_latent_projection=retained,
            regularization_included=False,
        )

    def fit(
        self,
        series: InterfaceIdentificationSeries,
        *,
        start_index: int,
        fit_window_s: float | None = None,
        embargo_s: float | None = None,
        validation_window_s: float | None = None,
        multistart: bool = True,
    ) -> InterfaceFitResult:
        dt = float(np.median(np.diff(series.time_s)))
        fit_steps = int(round((self.config.fit_window_s if fit_window_s is None else fit_window_s) / dt))
        embargo_steps = int(round((self.config.validation_embargo_s if embargo_s is None else embargo_s) / dt))
        validation_steps = int(round((self.config.validation_window_s if validation_window_s is None else validation_window_s) / dt))
        total_steps = fit_steps + embargo_steps + validation_steps
        if start_index + total_steps >= len(series.time_s):
            raise ValueError("fit/embargo/validation window exceeds the saved trace")
        initial_state_prior = np.r_[
            series.arrival_human_state[start_index],
            series.arrival_interface_state[start_index],
        ]
        parameter_prior = self.last_valid.as_array()
        parameter_starts = (
            self.config.multistart_parameter_scales
            if multistart
            else (tuple(float(v) for v in parameter_prior),)
        )
        state_offsets = (
            self.config.multistart_initial_state_offsets_in_prior_scales
            if multistart
            else ((0.0,) * 16,)
        )
        lower, upper = self._free_bounds()
        solutions = []
        for parameter_start, state_offset in zip(
            parameter_starts, state_offsets, strict=True
        ):
            state_start = initial_state_prior + (
                np.asarray(state_offset, dtype=float)
                * self.config.initial_state_prior_scale
            )
            initial = np.r_[
                np.clip(np.asarray(parameter_start, dtype=float), self.config.lower, self.config.upper),
                np.clip(state_start, lower[3:], upper[3:]),
            ]
            result = least_squares(
                lambda z: self._joint_residual(
                    z,
                    series,
                    start_index,
                    fit_steps,
                    parameter_prior,
                    initial_state_prior,
                    fix_parameters=False,
                ),
                initial,
                bounds=(lower, upper),
                max_nfev=self.config.maximum_function_evaluations,
                x_scale="jac",
            )
            data_rmse = float(
                np.sqrt(
                    np.mean(
                        self._measurement_residual(
                            result.x, series, start_index, fit_steps
                        )
                        ** 2
                    )
                )
            )
            solutions.append((result, data_rmse))
        result, fit_rmse = min(solutions, key=lambda item: item[1])
        candidate = np.asarray(result.x, dtype=float)
        success = bool(result.success and np.all(np.isfinite(candidate)))
        if success:
            parameters = InterfaceParameterScales.from_array(candidate[:3])
        else:
            parameters = self.last_valid
            candidate[:3] = parameters.as_array()
        prediction = self.predict_measurements(
            series, start_index, total_steps, parameters, candidate[3:]
        )
        validation_slice = slice(fit_steps + embargo_steps, total_steps)
        target = series.output_measurement[start_index + 1 : start_index + total_steps + 1]
        validation_difference = self._measurement_difference(
            prediction[validation_slice], target[validation_slice]
        )
        validation_rmse = float(
            np.sqrt(np.mean((validation_difference / self.config.measurement_scale) ** 2))
        )
        nominal_decision = self._fit_fixed_parameters(
            series,
            start_index,
            fit_steps,
            np.ones(3),
            initial_state_prior,
        )
        nominal_prediction = self.predict_measurements(
            series,
            start_index,
            total_steps,
            InterfaceParameterScales(),
            nominal_decision[3:],
        )
        nominal_difference = self._measurement_difference(
            nominal_prediction[validation_slice], target[validation_slice]
        )
        nominal_validation_rmse = float(
            np.sqrt(np.mean((nominal_difference / self.config.measurement_scale) ** 2))
        )
        improvement = 1.0 - validation_rmse / max(nominal_validation_rmse, 1.0e-15)
        component_slices = {
            "robot_position": slice(0, 3),
            "robot_rotation": slice(3, 6),
            "robot_linear_velocity": slice(6, 9),
            "robot_angular_velocity": slice(9, 12),
            "cuff_force": slice(12, 15),
            "cuff_moment": slice(15, 18),
        }
        component_rmse = {
            name: float(
                np.sqrt(
                    np.mean(
                        (
                            validation_difference[:, coordinates]
                            / self.config.measurement_scale[coordinates]
                        )
                        ** 2
                    )
                )
            )
            for name, coordinates in component_slices.items()
        }
        nominal_component_rmse = {
            name: float(
                np.sqrt(
                    np.mean(
                        (
                            nominal_difference[:, coordinates]
                            / self.config.measurement_scale[coordinates]
                        )
                        ** 2
                    )
                )
            )
            for name, coordinates in component_slices.items()
        }
        diagnostics = self.identifiability_diagnostics(
            candidate, series, start_index, fit_steps
        )
        bound_hit = bool(
            np.any(np.isclose(candidate[:3], self.config.lower, atol=1.0e-6))
            or np.any(np.isclose(candidate[:3], self.config.upper, atol=1.0e-6))
        )
        multistart_records_list = []
        for index, item in enumerate(solutions):
            start_prediction = self.predict_measurements(
                series,
                start_index,
                total_steps,
                InterfaceParameterScales.from_array(item[0].x[:3]),
                np.asarray(item[0].x[3:], dtype=float),
            )
            start_validation_difference = self._measurement_difference(
                start_prediction[validation_slice], target[validation_slice]
            )
            multistart_records_list.append(
                {
                    "initial_parameter_scales": list(parameter_starts[index]),
                    "initial_state_offset_in_prior_scales": list(state_offsets[index]),
                    "fitted_parameter_scales": np.asarray(item[0].x[:3]).tolist(),
                    "fit_normalized_rmse": float(item[1]),
                    "validation_normalized_rmse": float(
                        np.sqrt(
                            np.mean(
                                (
                                    start_validation_difference
                                    / self.config.measurement_scale
                                )
                                ** 2
                            )
                        )
                    ),
                    "success": bool(item[0].success),
                    "nfev": int(item[0].nfev),
                }
            )
        multistart_records = tuple(multistart_records_list)
        if success:
            self.last_valid = parameters
        return InterfaceFitResult(
            success=success,
            reason="optimizer_converged" if success else "optimizer_failed_last_valid_retained",
            parameter_scales=parameters,
            initial_state=candidate[3:].copy(),
            fit_normalized_rmse=fit_rmse,
            validation_normalized_rmse=validation_rmse,
            nominal_validation_normalized_rmse=nominal_validation_rmse,
            validation_relative_improvement=improvement,
            validation_component_normalized_rmse=component_rmse,
            nominal_validation_component_normalized_rmse=nominal_component_rmse,
            optimizer_nfev=int(result.nfev),
            optimizer_cost=float(result.cost),
            bound_hit=bound_hit,
            fit_start_time_s=float(series.time_s[start_index]),
            fit_end_time_s=float(series.time_s[start_index + fit_steps]),
            validation_start_time_s=float(series.time_s[start_index + fit_steps + embargo_steps + 1]),
            validation_end_time_s=float(series.time_s[start_index + total_steps]),
            validation_sample_count=validation_steps,
            identifiability=diagnostics,
            multistart_solutions=multistart_records,
            last_valid_fallback_used=not success,
        )


@dataclass(frozen=True)
class InterfaceModelVersion:
    version: str
    parameters: InterfaceParameterScales
    published_timestamp_s: float
    source_fit_end_timestamp_s: float


@dataclass(frozen=True)
class InterfaceChallengerDecision:
    status: str
    reasons: tuple[str, ...]
    candidate_validation_rmse: float
    incumbent_validation_rmse: float
    relative_improvement: float
    shadow_incumbent: InterfaceModelVersion
    control_model_changed: bool = False


class InactiveInterfaceIdentificationTrust:
    """One-challenger, future-validation publication shell, disconnected from control."""

    def __init__(self, config: InterfaceIdentificationConfig | None = None) -> None:
        self.config = load_interface_identification_config() if config is None else config
        self.shadow_incumbent = InterfaceModelVersion(
            version="stage5_interface_shadow_incumbent_v0_nominal",
            parameters=InterfaceParameterScales(),
            published_timestamp_s=0.0,
            source_fit_end_timestamp_s=0.0,
        )
        self.active_challenger: InterfaceFitResult | None = None

    def propose(self, fit: InterfaceFitResult) -> None:
        if self.active_challenger is not None:
            raise RuntimeError("only one interface challenger may be active")
        self.active_challenger = fit

    def resolve(
        self,
        *,
        decision_timestamp_s: float,
    ) -> InterfaceChallengerDecision:
        challenger = self.active_challenger
        if challenger is None:
            raise RuntimeError("no active interface challenger")
        reasons = []
        trust = self.config.inactive_trust
        if challenger.validation_start_time_s <= challenger.fit_end_time_s:
            reasons.append("validation_not_future_embargoed")
        if challenger.validation_sample_count < trust.minimum_future_validation_samples:
            reasons.append("insufficient_future_validation_samples")
        if challenger.validation_relative_improvement < trust.minimum_relative_prediction_improvement:
            reasons.append("insufficient_future_prediction_improvement")
        if challenger.identifiability.rank < 3:
            reasons.append("data_rank_deficient_after_latent_projection")
        if (
            not np.isfinite(challenger.identifiability.condition_number)
            or challenger.identifiability.condition_number
            > trust.maximum_data_condition_number
        ):
            reasons.append("data_ill_conditioned_after_latent_projection")
        if challenger.bound_hit:
            reasons.append("parameter_bound_hit")
        if not challenger.success:
            reasons.append("optimizer_failure")
        if reasons:
            status = "rejected_shadow_last_valid_retained"
        else:
            previous = self.shadow_incumbent.parameters.as_array()
            proposed = challenger.parameter_scales.as_array()
            span = self.config.upper - self.config.lower
            step = trust.publication_smoothing_alpha * (proposed - previous)
            maximum_step = (
                trust.maximum_publication_step_fraction_of_parameter_span * span
            )
            published = np.clip(
                previous + np.clip(step, -maximum_step, maximum_step),
                self.config.lower,
                self.config.upper,
            )
            self.shadow_incumbent = InterfaceModelVersion(
                version=f"stage5_interface_shadow_incumbent_{int(decision_timestamp_s * 1000):010d}",
                parameters=InterfaceParameterScales.from_array(published),
                published_timestamp_s=float(decision_timestamp_s),
                source_fit_end_timestamp_s=challenger.fit_end_time_s,
            )
            status = "qualified_and_published_to_shadow_only"
        self.active_challenger = None
        return InterfaceChallengerDecision(
            status=status,
            reasons=tuple(reasons),
            candidate_validation_rmse=challenger.validation_normalized_rmse,
            incumbent_validation_rmse=challenger.nominal_validation_normalized_rmse,
            relative_improvement=challenger.validation_relative_improvement,
            shadow_incumbent=self.shadow_incumbent,
            control_model_changed=False,
        )


__all__ = [
    "InactiveInterfaceIdentificationTrust",
    "InterfaceChallengerDecision",
    "InterfaceFitResult",
    "InterfaceIdentificationConfig",
    "InterfaceIdentificationMeasurement",
    "InterfaceIdentificationSeries",
    "InterfaceIdentifiabilityDiagnostics",
    "InterfaceModelVersion",
    "InterfaceParameterScales",
    "ShadowInterfaceIdentificationService",
    "WindowedInterfacePredictionErrorIdentifier",
    "fixed_stage5_human_model",
    "load_interface_identification_config",
]
