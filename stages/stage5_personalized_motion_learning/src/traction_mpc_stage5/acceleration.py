"""Deployable Stage-5 realized-acceleration semantics.

The online monitor uses the current causal Human state estimate and the
measured physical wrench transmitted at the Human cuff reference point. It
does not differentiate estimated velocity and never reads MuJoCo Human truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc_stage4.human_model import continuous_dynamics

from .controller_interface import EstimatedInterfaceState
from .task_observation import ControllerTaskObservation


MODEL_WRENCH_REALIZED_ACCELERATION = (
    "causal_interval_mean_model_based_q_dq_plus_measured_human_cuff_wrench"
)
MODEL_WRENCH_INSTANTANEOUS_ACCELERATION = (
    "instantaneous_model_based_q_dq_plus_measured_human_cuff_wrench"
)


def _finite_vector(name: str, value: Any, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {length}-vector")
    return result.copy()


@dataclass(frozen=True)
class DeployableRealizedAcceleration:
    """One timestamp-aligned causal acceleration estimate."""

    sample_timestamp_s: float
    interval_start_timestamp_s: float
    generalized_human_input_nm: np.ndarray
    acceleration_rad_s2: np.ndarray
    instantaneous_acceleration_rad_s2: np.ndarray
    source: str = MODEL_WRENCH_REALIZED_ACCELERATION
    wrench_reference_point: str = "human_sleeve_attach_site"

    def __post_init__(self) -> None:
        if not np.isfinite(self.sample_timestamp_s) or self.sample_timestamp_s < 0.0:
            raise ValueError(
                "acceleration sample timestamp must be finite and nonnegative"
            )
        if (
            not np.isfinite(self.interval_start_timestamp_s)
            or self.interval_start_timestamp_s < 0.0
            or self.interval_start_timestamp_s > self.sample_timestamp_s
        ):
            raise ValueError("acceleration interval start is invalid")
        object.__setattr__(
            self,
            "generalized_human_input_nm",
            _finite_vector(
                "generalized_human_input_nm", self.generalized_human_input_nm, 2
            ),
        )
        object.__setattr__(
            self,
            "acceleration_rad_s2",
            _finite_vector("acceleration_rad_s2", self.acceleration_rad_s2, 2),
        )
        object.__setattr__(
            self,
            "instantaneous_acceleration_rad_s2",
            _finite_vector(
                "instantaneous_acceleration_rad_s2",
                self.instantaneous_acceleration_rad_s2,
                2,
            ),
        )


def measured_transmitted_human_input(
    observation: ControllerTaskObservation,
    interface_state: EstimatedInterfaceState,
    human_model: Any,
) -> np.ndarray:
    """Map the measured Human-site cuff wrench to generalized Human input."""

    if interface_state.sample_timestamp_s != observation.sample_timestamp_s:
        raise ValueError("acceleration inputs must share one sample timestamp")
    state = observation.as_array()
    return np.asarray(
        human_model.geometry.generalized_input_from_wrench(
            state[:2],
            interface_state.measured_force_world_n,
            interface_state.measured_moment_world_nm,
        ),
        dtype=float,
    )


def estimate_deployable_realized_acceleration(
    observation: ControllerTaskObservation,
    interface_state: EstimatedInterfaceState,
    human_model: Any,
) -> DeployableRealizedAcceleration:
    """Evaluate the causal model-based acceleration at the current sample."""

    state = observation.as_array()
    generalized_input = measured_transmitted_human_input(
        observation, interface_state, human_model
    )
    if hasattr(human_model, "continuous_dynamics"):
        derivative = np.asarray(
            human_model.continuous_dynamics(state, generalized_input), dtype=float
        )
    else:
        derivative = np.asarray(
            continuous_dynamics(state, generalized_input, human_model), dtype=float
        )
    if derivative.shape != (4,) or not np.all(np.isfinite(derivative)):
        raise ValueError("Human model returned an invalid state derivative")
    return DeployableRealizedAcceleration(
        sample_timestamp_s=observation.sample_timestamp_s,
        interval_start_timestamp_s=observation.sample_timestamp_s,
        generalized_human_input_nm=generalized_input,
        acceleration_rad_s2=derivative[2:],
        instantaneous_acceleration_rad_s2=derivative[2:],
        source=MODEL_WRENCH_INSTANTANEOUS_ACCELERATION,
    )


class CausalModelAccelerationMonitor:
    """Time-average model-based qdd over the MPC's registered 20 ms interval.

    Before 20 ms of history exists, every available sample since episode start
    is used. This is a shorter causal interval, not a startup exemption.
    """

    def __init__(self, interval_s: float = 0.020) -> None:
        if not np.isfinite(interval_s) or interval_s <= 0.0:
            raise ValueError("acceleration interval must be finite and positive")
        self.interval_s = float(interval_s)
        self._samples: list[tuple[float, np.ndarray]] = []

    def reset(self) -> None:
        self._samples.clear()

    def update(
        self,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        human_model: Any,
    ) -> DeployableRealizedAcceleration:
        instantaneous = estimate_deployable_realized_acceleration(
            observation, interface_state, human_model
        )
        timestamp = instantaneous.sample_timestamp_s
        if self._samples and timestamp <= self._samples[-1][0]:
            raise ValueError("acceleration monitor requires increasing timestamps")
        self._samples.append(
            (timestamp, instantaneous.instantaneous_acceleration_rad_s2.copy())
        )
        cutoff = max(self._samples[0][0], timestamp - self.interval_s)
        points = self._window_points(cutoff)
        times = np.asarray([item[0] for item in points], dtype=float)
        values = np.asarray([item[1] for item in points], dtype=float)
        duration = float(timestamp - cutoff)
        mean = (
            values[-1].copy()
            if duration <= 1.0e-15
            else np.trapezoid(values, times, axis=0) / duration
        )
        while len(self._samples) > 2 and self._samples[1][0] <= cutoff:
            self._samples.pop(0)
        return DeployableRealizedAcceleration(
            sample_timestamp_s=timestamp,
            interval_start_timestamp_s=cutoff,
            generalized_human_input_nm=(
                instantaneous.generalized_human_input_nm
            ),
            acceleration_rad_s2=mean,
            instantaneous_acceleration_rad_s2=(
                instantaneous.instantaneous_acceleration_rad_s2
            ),
            source=MODEL_WRENCH_REALIZED_ACCELERATION,
        )

    def _window_points(self, cutoff: float) -> list[tuple[float, np.ndarray]]:
        first_after = next(
            (
                index
                for index, (time_s, _) in enumerate(self._samples)
                if time_s >= cutoff
            ),
            len(self._samples) - 1,
        )
        points: list[tuple[float, np.ndarray]] = []
        if self._samples[first_after][0] > cutoff and first_after > 0:
            left_t, left_value = self._samples[first_after - 1]
            right_t, right_value = self._samples[first_after]
            alpha = (cutoff - left_t) / (right_t - left_t)
            points.append(
                (cutoff, left_value + alpha * (right_value - left_value))
            )
        points.extend(self._samples[first_after:])
        return points


__all__ = [
    "CausalModelAccelerationMonitor",
    "DeployableRealizedAcceleration",
    "MODEL_WRENCH_INSTANTANEOUS_ACCELERATION",
    "MODEL_WRENCH_REALIZED_ACCELERATION",
    "estimate_deployable_realized_acceleration",
    "measured_transmitted_human_input",
]
