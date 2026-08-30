"""Causal engineering measurement boundary for Stage-4 sensor-realism checks.

The controller-facing object contains only robot/cuff measurements.  Human
state, Human parameters, bed force, contacts, and other MuJoCo-only quantities
are deliberately absent.  The numerical settings below are engineering
assumptions for simulation sensitivity checks, not measured CR12 sensor data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class MeasurementNoise:
    robot_position_std_rad: float = 0.0
    robot_velocity_std_rad_s: float = 0.0
    cuff_position_std_m: float = 0.0
    cuff_orientation_std_rad: float = 0.0
    force_std_n: float = 0.0
    moment_std_nm: float = 0.0


@dataclass(frozen=True)
class MeasurementPreprocessing:
    lowpass_cutoff_hz: float = 8.0
    derivative_window_s: float = 0.120


@dataclass(frozen=True)
class MeasurementCase:
    name: str
    update_rate_hz: float
    latency_s: float
    noise: MeasurementNoise = MeasurementNoise()
    force_bias_n: tuple[float, float, float] = (0.0, 0.0, 0.0)
    force_bias_drift_n_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    moment_bias_nm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    moment_bias_drift_nm_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    preprocessing_enabled: bool = False
    seed: int = 44104

    @property
    def sample_period_s(self) -> float:
        return 1.0 / self.update_rate_hz


REALISTIC_NOISE = MeasurementNoise(
    robot_position_std_rad=math.radians(0.02),
    robot_velocity_std_rad_s=math.radians(0.10),
    cuff_position_std_m=0.00030,
    cuff_orientation_std_rad=math.radians(0.05),
    force_std_n=0.50,
    moment_std_nm=0.020,
)

COMMON_FORCE_BIAS_N = (1.50, -1.00, 0.80)
COMMON_FORCE_BIAS_DRIFT_N_S = (0.040, -0.030, 0.020)
COMMON_MOMENT_BIAS_NM = (0.030, -0.020, 0.015)
COMMON_MOMENT_BIAS_DRIFT_NM_S = (0.0010, -0.0008, 0.0006)


def sensor_realism_cases() -> tuple[MeasurementCase, ...]:
    """Return the fixed cumulative five-case engineering ladder."""

    ideal = MeasurementCase(name="ideal_200hz", update_rate_hz=200.0, latency_s=0.0)
    noise = MeasurementCase(
        name="noise_200hz",
        update_rate_hz=200.0,
        latency_s=0.0,
        noise=REALISTIC_NOISE,
        preprocessing_enabled=True,
    )
    biased = replace(
        noise,
        name="noise_bias_drift_200hz",
        force_bias_n=COMMON_FORCE_BIAS_N,
        force_bias_drift_n_s=COMMON_FORCE_BIAS_DRIFT_N_S,
        moment_bias_nm=COMMON_MOMENT_BIAS_NM,
        moment_bias_drift_nm_s=COMMON_MOMENT_BIAS_DRIFT_NM_S,
    )
    delayed = replace(biased, name="noise_bias_delay_200hz", latency_s=0.010)
    reduced = replace(
        delayed,
        name="noise_bias_delay_100hz",
        update_rate_hz=100.0,
    )
    return ideal, noise, biased, delayed, reduced


def architecture_comparison_sensor_cases() -> tuple[MeasurementCase, ...]:
    """Return the three fixed A/B cases; delay is diagnostic and bias-free."""

    ideal, noise, _, _, _ = sensor_realism_cases()
    delayed_noise = replace(
        noise,
        name="noise_delay_200hz",
        latency_s=0.010,
    )
    return ideal, noise, delayed_noise


@dataclass(frozen=True)
class ControllerMeasurement:
    arrival_time_s: float
    sample_time_s: float
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    attachment_position_m: np.ndarray
    attachment_rotation_matrix: np.ndarray
    attachment_velocity_m_s: np.ndarray
    attachment_angular_velocity_rad_s: np.ndarray
    cuff_force_vector_n: np.ndarray
    cuff_moment_vector_nm: np.ndarray
    new_sample: bool

    @property
    def age_s(self) -> float:
        return float(self.arrival_time_s - self.sample_time_s)


@dataclass(frozen=True)
class _ProcessedSample:
    sample_time_s: float
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    attachment_position_m: np.ndarray
    attachment_rotation_matrix: np.ndarray
    attachment_velocity_m_s: np.ndarray
    attachment_angular_velocity_rad_s: np.ndarray
    cuff_force_vector_n: np.ndarray
    cuff_moment_vector_nm: np.ndarray


class CausalMeasurementLayer:
    """Sample, perturb, filter, align, delay, and hold robot/cuff measurements."""

    def __init__(
        self,
        case: MeasurementCase,
        initial_truth: Any,
        preprocessing: MeasurementPreprocessing = MeasurementPreprocessing(),
    ) -> None:
        self.case = case
        self.preprocessing = preprocessing
        self.rng = np.random.default_rng(case.seed)
        self._next_capture_time_s = float(initial_truth.time_s)
        self._processed: list[_ProcessedSample] = []
        self._delivered_index = -1
        self._pose_history: list[tuple[float, np.ndarray, np.ndarray]] = []
        self._filtered_q: np.ndarray | None = None
        self._filtered_dq: np.ndarray | None = None
        self._filtered_position: np.ndarray | None = None
        self._filtered_rotation: np.ndarray | None = None
        self._filtered_force: np.ndarray | None = None
        self._filtered_moment: np.ndarray | None = None
        self._capture(initial_truth)
        self._next_capture_time_s += self.case.sample_period_s
        self._delivered_index = 0
        self._current = self._measurement_from_sample(
            self._processed[0], float(initial_truth.time_s), new_sample=True
        )

    @property
    def current(self) -> ControllerMeasurement:
        return self._current

    def update(self, truth: Any) -> ControllerMeasurement:
        arrival_time = float(truth.time_s)
        tolerance = 0.25e-9
        if arrival_time + tolerance >= self._next_capture_time_s:
            self._capture(truth)
            self._next_capture_time_s += self.case.sample_period_s

        eligible_time = arrival_time - self.case.latency_s + tolerance
        newest = self._delivered_index
        for index in range(self._delivered_index + 1, len(self._processed)):
            if self._processed[index].sample_time_s <= eligible_time:
                newest = index
            else:
                break
        is_new = newest != self._delivered_index
        if is_new:
            self._delivered_index = newest
        sample = self._processed[self._delivered_index]
        self._current = self._measurement_from_sample(sample, arrival_time, is_new)
        return self._current

    def _capture(self, truth: Any) -> None:
        t = float(truth.time_s)
        noise = self.case.noise
        q = np.asarray(truth.robot_q_rad, dtype=float) + self.rng.normal(
            0.0, noise.robot_position_std_rad, 6
        )
        dq = np.asarray(truth.robot_dq_rad_s, dtype=float) + self.rng.normal(
            0.0, noise.robot_velocity_std_rad_s, 6
        )
        position = np.asarray(truth.attachment_position_m, dtype=float) + self.rng.normal(
            0.0, noise.cuff_position_std_m, 3
        )
        orientation_noise = self.rng.normal(0.0, noise.cuff_orientation_std_rad, 3)
        rotation = Rotation.from_rotvec(orientation_noise).as_matrix() @ np.asarray(
            truth.attachment_rotation_matrix, dtype=float
        )
        force_bias = np.asarray(self.case.force_bias_n) + t * np.asarray(
            self.case.force_bias_drift_n_s
        )
        moment_bias = np.asarray(self.case.moment_bias_nm) + t * np.asarray(
            self.case.moment_bias_drift_nm_s
        )
        force = (
            np.asarray(truth.cuff_force_vector_n, dtype=float)
            + force_bias
            + self.rng.normal(0.0, noise.force_std_n, 3)
        )
        moment = (
            np.asarray(truth.cuff_moment_vector_nm, dtype=float)
            + moment_bias
            + self.rng.normal(0.0, noise.moment_std_nm, 3)
        )

        if not self.case.preprocessing_enabled:
            linear_velocity = np.asarray(truth.attachment_velocity_m_s, dtype=float).copy()
            angular_velocity = np.asarray(
                truth.attachment_angular_velocity_rad_s, dtype=float
            ).copy()
            processed = _ProcessedSample(
                t,
                q,
                dq,
                position,
                rotation,
                linear_velocity,
                angular_velocity,
                force,
                moment,
            )
            self._processed.append(processed)
            return

        previous_time = self._processed[-1].sample_time_s if self._processed else t
        dt = max(self.case.sample_period_s, t - previous_time)
        alpha = 1.0 - math.exp(-2.0 * math.pi * self.preprocessing.lowpass_cutoff_hz * dt)
        if self._filtered_q is None:
            self._filtered_q = q.copy()
            self._filtered_dq = dq.copy()
            self._filtered_position = position.copy()
            self._filtered_rotation = rotation.copy()
            self._filtered_force = force.copy()
            self._filtered_moment = moment.copy()
        else:
            self._filtered_q += alpha * (q - self._filtered_q)
            self._filtered_dq += alpha * (dq - self._filtered_dq)
            self._filtered_position += alpha * (position - self._filtered_position)
            delta = Rotation.from_matrix(rotation @ self._filtered_rotation.T).as_rotvec()
            self._filtered_rotation = (
                Rotation.from_rotvec(alpha * delta).as_matrix() @ self._filtered_rotation
            )
            self._filtered_force += alpha * (force - self._filtered_force)
            self._filtered_moment += alpha * (moment - self._filtered_moment)

        assert self._filtered_position is not None
        assert self._filtered_rotation is not None
        self._pose_history.append(
            (t, self._filtered_position.copy(), self._filtered_rotation.copy())
        )
        oldest = t - self.preprocessing.derivative_window_s
        self._pose_history = [item for item in self._pose_history if item[0] >= oldest - 1e-12]
        linear_velocity, angular_velocity = self._causal_twist()
        self._processed.append(
            _ProcessedSample(
                t,
                self._filtered_q.copy(),
                self._filtered_dq.copy(),
                self._filtered_position.copy(),
                self._filtered_rotation.copy(),
                linear_velocity,
                angular_velocity,
                self._filtered_force.copy(),
                self._filtered_moment.copy(),
            )
        )

    def _causal_twist(self) -> tuple[np.ndarray, np.ndarray]:
        if len(self._pose_history) < 3:
            return np.zeros(3), np.zeros(3)
        t_current, _, r_current = self._pose_history[-1]
        times = np.array([item[0] - t_current for item in self._pose_history])
        positions = np.array([item[1] for item in self._pose_history])
        rotvecs = np.array(
            [Rotation.from_matrix(item[2] @ r_current.T).as_rotvec() for item in self._pose_history]
        )
        degree = min(2, len(times) - 1)
        design = np.column_stack([times**power for power in range(degree + 1)])
        position_coefficients, _, _, _ = np.linalg.lstsq(design, positions, rcond=None)
        rotation_coefficients, _, _, _ = np.linalg.lstsq(design, rotvecs, rcond=None)
        return position_coefficients[1].copy(), rotation_coefficients[1].copy()

    @staticmethod
    def _measurement_from_sample(
        sample: _ProcessedSample, arrival_time_s: float, new_sample: bool
    ) -> ControllerMeasurement:
        return ControllerMeasurement(
            arrival_time_s=float(arrival_time_s),
            sample_time_s=float(sample.sample_time_s),
            robot_q_rad=sample.robot_q_rad.copy(),
            robot_dq_rad_s=sample.robot_dq_rad_s.copy(),
            attachment_position_m=sample.attachment_position_m.copy(),
            attachment_rotation_matrix=sample.attachment_rotation_matrix.copy(),
            attachment_velocity_m_s=sample.attachment_velocity_m_s.copy(),
            attachment_angular_velocity_rad_s=sample.attachment_angular_velocity_rad_s.copy(),
            cuff_force_vector_n=sample.cuff_force_vector_n.copy(),
            cuff_moment_vector_nm=sample.cuff_moment_vector_nm.copy(),
            new_sample=bool(new_sample),
        )


def measurement_case_dict(case: MeasurementCase) -> dict[str, Any]:
    return {
        "name": case.name,
        "update_rate_hz": case.update_rate_hz,
        "latency_s": case.latency_s,
        "noise_std": {
            "robot_position_deg": math.degrees(case.noise.robot_position_std_rad),
            "robot_velocity_deg_s": math.degrees(case.noise.robot_velocity_std_rad_s),
            "cuff_position_mm": 1000.0 * case.noise.cuff_position_std_m,
            "cuff_orientation_deg": math.degrees(case.noise.cuff_orientation_std_rad),
            "force_n": case.noise.force_std_n,
            "moment_nm": case.noise.moment_std_nm,
        },
        "force_bias_n": list(case.force_bias_n),
        "force_bias_drift_n_s": list(case.force_bias_drift_n_s),
        "moment_bias_nm": list(case.moment_bias_nm),
        "moment_bias_drift_nm_s": list(case.moment_bias_drift_nm_s),
        "preprocessing_enabled": case.preprocessing_enabled,
        "random_seed": case.seed,
        "actual_cr12_sensor_specification": False,
    }
