"""Finite-hypothesis Stage-5 interface uncertainty monitoring.

The controller nominal estimate remains the control point.  Additional
Kelvin--Voigt hypotheses consume the same deployable measurement and provide
an empirical range for task-state decisions.  MuJoCo truth is not an input.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import json
from pathlib import Path
from typing import Any

import numpy as np

from .acceleration import CausalModelAccelerationMonitor, DeployableRealizedAcceleration
from .config import STAGE5_ROOT
from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    ControllerNominalInterfaceParameters,
    EstimatedInterfaceState,
    InterfaceAwareHumanStateObserver,
)
from .task import (
    ControllerCompletionMargin,
    GoalTaskSpec,
    GoalTaskState,
    TaskPhase,
    abort_episode,
    at_goal,
    at_goal_for_online_completion,
    start_episode,
    transition_phase,
    within_q_bounds,
)
from .task_observation import ControllerTaskObservation


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_interface_uncertainty_v1.json"
NOMINAL_HYPOTHESIS_NAME = "nominal"


@dataclass(frozen=True)
class InterfaceUncertaintySpec:
    translation_stiffness_scale_range: tuple[float, float]
    rotation_stiffness_scale_range: tuple[float, float]
    joint_damping_scale_range: tuple[float, float]
    causal_derivative_window_s: float
    method: str
    empirical_range_not_guaranteed_bound: bool = True
    hardware_calibrated_confidence_interval: bool = False

    def __post_init__(self) -> None:
        for name in (
            "translation_stiffness_scale_range",
            "rotation_stiffness_scale_range",
            "joint_damping_scale_range",
        ):
            values = np.asarray(getattr(self, name), dtype=float)
            if (
                values.shape != (2,)
                or not np.all(np.isfinite(values))
                or not 0.0 < values[0] < 1.0 < values[1]
            ):
                raise ValueError(f"{name} must be a positive interval containing 1")
            object.__setattr__(self, name, tuple(float(value) for value in values))
        if not np.isfinite(self.causal_derivative_window_s) or self.causal_derivative_window_s <= 0.0:
            raise ValueError("causal derivative window must be finite and positive")
        if not self.method:
            raise ValueError("uncertainty method must be named")
        if not self.empirical_range_not_guaranteed_bound:
            raise ValueError("finite hypothesis range must not be labeled guaranteed")
        if self.hardware_calibrated_confidence_interval:
            raise ValueError("v1 range is not hardware calibrated")


def load_interface_uncertainty_spec(path: Path = CONFIG_PATH) -> InterfaceUncertaintySpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_interface_uncertainty_v1":
        raise ValueError("unexpected interface uncertainty schema")
    if payload.get("controller_nominal_model_unchanged") is not True:
        raise ValueError("controller nominal interface must remain unchanged")
    if payload.get("truth_available_online") is not False:
        raise ValueError("MuJoCo truth must remain unavailable online")
    return InterfaceUncertaintySpec(
        translation_stiffness_scale_range=tuple(payload["translation_stiffness_scale_range"]),
        rotation_stiffness_scale_range=tuple(payload["rotation_stiffness_scale_range"]),
        joint_damping_scale_range=tuple(payload["joint_damping_scale_range"]),
        causal_derivative_window_s=float(payload["causal_derivative_window_s"]),
        method=str(payload["method"]),
        empirical_range_not_guaranteed_bound=bool(
            payload["empirical_range_not_guaranteed_bound"]
        ),
        hardware_calibrated_confidence_interval=bool(
            payload["hardware_calibrated_confidence_interval"]
        ),
    )


def _scaled_parameters(
    name: str,
    kt_scale: float,
    kr_scale: float,
    damping_scale: float,
) -> ControllerNominalInterfaceParameters:
    nominal = CONTROLLER_NOMINAL_INTERFACE
    return replace(
        nominal,
        model_version=f"{nominal.model_version}__uncertainty_{name}",
        translation_stiffness_n_m=tuple(
            float(kt_scale * value) for value in nominal.translation_stiffness_n_m
        ),
        translation_damping_ns_m=tuple(
            float(damping_scale * value) for value in nominal.translation_damping_ns_m
        ),
        rotation_stiffness_nm_rad=float(
            kr_scale * nominal.rotation_stiffness_nm_rad
        ),
        rotation_damping_nms_rad=float(
            damping_scale * nominal.rotation_damping_nms_rad
        ),
    )


def build_interface_hypotheses(
    spec: InterfaceUncertaintySpec,
) -> tuple[tuple[str, ControllerNominalInterfaceParameters], ...]:
    hypotheses: list[tuple[str, ControllerNominalInterfaceParameters]] = [
        (NOMINAL_HYPOTHESIS_NAME, CONTROLLER_NOMINAL_INTERFACE)
    ]
    for kt_scale, kr_scale, damping_scale in product(
        spec.translation_stiffness_scale_range,
        spec.rotation_stiffness_scale_range,
        spec.joint_damping_scale_range,
    ):
        name = (
            f"corner_kt{kt_scale:.1f}_kr{kr_scale:.1f}_d{damping_scale:.1f}"
        )
        hypotheses.append(
            (
                name,
                _scaled_parameters(name, kt_scale, kr_scale, damping_scale),
            )
        )
    return tuple(hypotheses)


class _CausalDqDerivative:
    def __init__(self, window_s: float) -> None:
        self.window_s = float(window_s)
        self._samples: list[tuple[float, np.ndarray]] = []

    def update(self, timestamp_s: float, dq_rad_s: np.ndarray) -> tuple[np.ndarray, bool]:
        timestamp = float(timestamp_s)
        dq = np.asarray(dq_rad_s, dtype=float)
        if dq.shape != (2,) or not np.all(np.isfinite(dq)):
            raise ValueError("dq derivative input must be a finite two-vector")
        if self._samples and timestamp <= self._samples[-1][0]:
            raise ValueError("dq derivative requires increasing timestamps")
        self._samples.append((timestamp, dq.copy()))
        first_time = self._samples[0][0]
        if timestamp - first_time < self.window_s - 1.0e-12:
            return np.zeros(2), False
        cutoff = timestamp - self.window_s
        right_index = next(
            index
            for index, (sample_time, _) in enumerate(self._samples)
            if sample_time >= cutoff - 1.0e-12
        )
        right_time, right_value = self._samples[right_index]
        if right_time > cutoff + 1.0e-12 and right_index > 0:
            left_time, left_value = self._samples[right_index - 1]
            alpha = (cutoff - left_time) / (right_time - left_time)
            start_value = left_value + alpha * (right_value - left_value)
        else:
            start_value = right_value
        while len(self._samples) > 2 and self._samples[1][0] <= cutoff:
            self._samples.pop(0)
        return (dq - start_value) / self.window_s, True


@dataclass(frozen=True)
class InterfaceHypothesisEstimate:
    name: str
    observation: ControllerTaskObservation
    interface_state: EstimatedInterfaceState
    model_acceleration: DeployableRealizedAcceleration
    causal_dq_acceleration_rad_s2: np.ndarray
    causal_dq_acceleration_available: bool


@dataclass(frozen=True)
class InterfaceUncertaintyEstimate:
    sample_timestamp_s: float
    hypotheses: tuple[InterfaceHypothesisEstimate, ...]
    method: str
    empirical_range_not_guaranteed_bound: bool = True
    truth_used: bool = False

    @property
    def nominal(self) -> InterfaceHypothesisEstimate:
        for item in self.hypotheses:
            if item.name == NOMINAL_HYPOTHESIS_NAME:
                return item
        raise RuntimeError("nominal interface hypothesis is missing")

    @property
    def state_matrix(self) -> np.ndarray:
        return np.asarray([item.observation.as_array() for item in self.hypotheses])

    @property
    def model_acceleration_matrix(self) -> np.ndarray:
        return np.asarray(
            [item.model_acceleration.acceleration_rad_s2 for item in self.hypotheses]
        )

    @property
    def available_causal_acceleration_matrix(self) -> np.ndarray:
        return np.asarray(
            [
                item.causal_dq_acceleration_rad_s2
                for item in self.hypotheses
                if item.causal_dq_acceleration_available
            ]
        ).reshape(-1, 2)

    @property
    def decision_acceleration_matrix(self) -> np.ndarray:
        causal = self.available_causal_acceleration_matrix
        if len(causal):
            return np.concatenate([self.model_acceleration_matrix, causal], axis=0)
        return self.model_acceleration_matrix


class InterfaceUncertaintyMonitor:
    """Causal fixed-hypothesis monitor; it does not adapt or select a model."""

    def __init__(self, spec: InterfaceUncertaintySpec) -> None:
        self.spec = spec
        hypotheses = build_interface_hypotheses(spec)
        self._entries = tuple(
            (
                name,
                InterfaceAwareHumanStateObserver(parameters),
                CausalModelAccelerationMonitor(
                    interval_s=spec.causal_derivative_window_s
                ),
                _CausalDqDerivative(spec.causal_derivative_window_s),
            )
            for name, parameters in hypotheses
        )
        self._last: InterfaceUncertaintyEstimate | None = None

    def update(
        self,
        measurement: Any,
        human_model: Any,
        *,
        human_model_version: str,
    ) -> InterfaceUncertaintyEstimate:
        timestamp = float(measurement.sample_time_s)
        if self._last is not None and abs(timestamp - self._last.sample_timestamp_s) <= 1.0e-12:
            return self._last
        estimates = []
        for name, observer, acceleration_monitor, derivative_monitor in self._entries:
            observation, interface_state = observer.update(
                measurement,
                human_model,
                human_model_version=human_model_version,
            )
            model_acceleration = acceleration_monitor.update(
                observation, interface_state, human_model
            )
            causal_acceleration, available = derivative_monitor.update(
                observation.sample_timestamp_s,
                observation.as_array()[2:],
            )
            estimates.append(
                InterfaceHypothesisEstimate(
                    name=name,
                    observation=observation,
                    interface_state=interface_state,
                    model_acceleration=model_acceleration,
                    causal_dq_acceleration_rad_s2=causal_acceleration,
                    causal_dq_acceleration_available=available,
                )
            )
        self._last = InterfaceUncertaintyEstimate(
            sample_timestamp_s=timestamp,
            hypotheses=tuple(estimates),
            method=self.spec.method,
        )
        return self._last


def uncertainty_motion_violation(
    spec: GoalTaskSpec,
    estimate: InterfaceUncertaintyEstimate,
) -> str | None:
    states = estimate.state_matrix
    if any(not within_q_bounds(spec, state[:2]) for state in states):
        return "INTERFACE_UNCERTAINTY_Q_BOUNDS"
    if spec.task_joint_velocity_limit_rad_s is not None:
        limits = np.asarray(spec.task_joint_velocity_limit_rad_s, dtype=float)
        if np.any(np.abs(states[:, 2:]) > limits[None, :] + 1.0e-12):
            return "INTERFACE_UNCERTAINTY_VELOCITY_LIMIT"
    if spec.task_joint_acceleration_limit_rad_s2 is not None:
        limits = np.asarray(spec.task_joint_acceleration_limit_rad_s2, dtype=float)
        if np.any(
            np.abs(estimate.decision_acceleration_matrix)
            > limits[None, :] + 1.0e-12
        ):
            return "INTERFACE_UNCERTAINTY_ACCELERATION_LIMIT"
    return None


def uncertainty_motion_diagnostics(
    spec: GoalTaskSpec,
    estimate: InterfaceUncertaintyEstimate,
) -> dict[str, Any]:
    """Explain an empirical decision range without consulting plant truth."""

    names = [item.name for item in estimate.hypotheses]
    states = estimate.state_matrix
    model_acceleration = estimate.model_acceleration_matrix
    causal_items = [
        item
        for item in estimate.hypotheses
        if item.causal_dq_acceleration_available
    ]
    causal_acceleration = estimate.available_causal_acceleration_matrix
    result: dict[str, Any] = {
        "violation": uncertainty_motion_violation(spec, estimate),
        "maximum_abs_velocity_deg_s": np.degrees(
            np.max(np.abs(states[:, 2:]), axis=0)
        ).tolist(),
        "maximum_abs_model_acceleration_deg_s2": np.degrees(
            np.max(np.abs(model_acceleration), axis=0)
        ).tolist(),
        "model_acceleration_extreme_hypothesis": [
            names[int(np.argmax(np.abs(model_acceleration[:, joint])))]
            for joint in range(2)
        ],
        "causal_dq_acceleration_available": bool(len(causal_acceleration)),
        "truth_used": False,
    }
    if len(causal_acceleration):
        result.update(
            {
                "maximum_abs_causal_dq_acceleration_deg_s2": np.degrees(
                    np.max(np.abs(causal_acceleration), axis=0)
                ).tolist(),
                "causal_dq_acceleration_extreme_hypothesis": [
                    causal_items[
                        int(np.argmax(np.abs(causal_acceleration[:, joint])))
                    ].name
                    for joint in range(2)
                ],
            }
        )
    return result


def start_episode_uncertainty_aware(
    spec: GoalTaskSpec,
    estimate: InterfaceUncertaintyEstimate,
) -> GoalTaskState:
    violation = uncertainty_motion_violation(spec, estimate)
    if violation is not None:
        raise ValueError(f"cannot start episode: {violation}")
    if not all(
        at_goal(
            spec,
            item.observation.as_array()[:2],
            item.observation.as_array()[2:],
            spec.start_return_target_rad,
        )
        for item in estimate.hypotheses
    ):
        raise ValueError("cannot start episode: INTERFACE_UNCERTAINTY_START_NOT_SETTLED")
    nominal = estimate.nominal
    state = nominal.observation.as_array()
    return start_episode(
        spec,
        state[:2],
        state[2:],
        nominal.model_acceleration.acceleration_rad_s2,
    )


def _phase_target(spec: GoalTaskSpec, phase: TaskPhase) -> tuple[float, float]:
    if phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD):
        return spec.outbound_goal_target_rad
    return spec.start_return_target_rad


def transition_phase_uncertainty_aware(
    spec: GoalTaskSpec,
    state: GoalTaskState,
    estimate: InterfaceUncertaintyEstimate,
    dt_s: float,
    *,
    completion_margin: ControllerCompletionMargin,
    abort_reason: str | None = None,
) -> GoalTaskState:
    if abort_reason is not None:
        return abort_episode(state, abort_reason)
    violation = uncertainty_motion_violation(spec, estimate)
    if violation is not None:
        return abort_episode(state, violation)
    target = np.asarray(_phase_target(spec, state.phase), dtype=float)
    angle_tolerance, velocity_tolerance = completion_margin.tightened_tolerances(spec)
    angle_tolerance = np.asarray(angle_tolerance, dtype=float)
    velocity_tolerance = np.asarray(velocity_tolerance, dtype=float)

    def score(item: InterfaceHypothesisEstimate) -> float:
        sample = item.observation.as_array()
        return float(
            max(
                np.max(np.abs(sample[:2] - target) / angle_tolerance),
                np.max(np.abs(sample[2:]) / velocity_tolerance),
            )
        )

    representative = max(estimate.hypotheses, key=score)
    representative_state = representative.observation.as_array()
    result = transition_phase(
        spec,
        state,
        representative_state[:2],
        representative_state[2:],
        dt_s,
        ddq_rad_s2=representative.model_acceleration.acceleration_rad_s2,
        completion_margin=completion_margin,
    )
    if result.phase is not state.phase and result.phase is not TaskPhase.ABORTED:
        assert all(
            at_goal_for_online_completion(
                spec,
                item.observation.as_array()[:2],
                item.observation.as_array()[2:],
                target,
                completion_margin,
            )
            for item in estimate.hypotheses
        )
    return result


__all__ = [
    "CONFIG_PATH",
    "InterfaceHypothesisEstimate",
    "InterfaceUncertaintyEstimate",
    "InterfaceUncertaintyMonitor",
    "InterfaceUncertaintySpec",
    "build_interface_hypotheses",
    "load_interface_uncertainty_spec",
    "start_episode_uncertainty_aware",
    "transition_phase_uncertainty_aware",
    "uncertainty_motion_diagnostics",
    "uncertainty_motion_violation",
]
