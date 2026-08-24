"""State-only UKF for the planar Human-V2 state [q1,q2,dq1,dq2]."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from .estimator_v2 import BaseParameterHumanModel


@dataclass(frozen=True)
class StateUKFConfig:
    alpha: float = 0.70
    beta: float = 2.0
    kappa: float = 0.0
    nominal_update_period_s: float = 0.020
    process_q_std_rad: float = math.radians(0.03)
    process_dq_std_rad_s: float = math.radians(0.50)
    measurement_q_std_rad: float = math.radians(0.30)
    measurement_dq_std_rad_s: float = math.radians(2.0)
    initial_q_std_rad: float = math.radians(0.50)
    initial_dq_std_rad_s: float = math.radians(3.0)
    covariance_jitter: float = 1.0e-12

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": ["q1", "q2", "dq1", "dq2"],
            "parameter_state_dimension": 0,
            "alpha": self.alpha,
            "beta": self.beta,
            "kappa": self.kappa,
            "nominal_update_period_s": self.nominal_update_period_s,
            "Q_diagonal_at_nominal_period": [
                self.process_q_std_rad**2,
                self.process_q_std_rad**2,
                self.process_dq_std_rad_s**2,
                self.process_dq_std_rad_s**2,
            ],
            "R_diagonal": [
                self.measurement_q_std_rad**2,
                self.measurement_q_std_rad**2,
                self.measurement_dq_std_rad_s**2,
                self.measurement_dq_std_rad_s**2,
            ],
            "P0_diagonal": [
                self.initial_q_std_rad**2,
                self.initial_q_std_rad**2,
                self.initial_dq_std_rad_s**2,
                self.initial_dq_std_rad_s**2,
            ],
            "units": "rad and rad/s",
            "engineering_assumption_not_hardware_calibration": True,
        }


class StateOnlyHumanUKF:
    """Unscented state observer; geometry and parameters are never UKF states."""

    state_dimension = 4
    parameter_state_dimension = 0

    def __init__(
        self,
        initial_state: np.ndarray,
        initial_time_s: float,
        initial_generalized_input_nm: np.ndarray,
        config: StateUKFConfig = StateUKFConfig(),
    ) -> None:
        self.config = config
        self.mean = np.asarray(initial_state, dtype=float).copy()
        if self.mean.shape != (4,) or not np.all(np.isfinite(self.mean)):
            raise ValueError("initial UKF state must be a finite four-vector")
        self.covariance = np.diag(
            [
                config.initial_q_std_rad**2,
                config.initial_q_std_rad**2,
                config.initial_dq_std_rad_s**2,
                config.initial_dq_std_rad_s**2,
            ]
        )
        self.last_time_s = float(initial_time_s)
        self.last_input_nm = np.asarray(initial_generalized_input_nm, dtype=float).copy()
        self.update_count = 0
        self.last_diagnostics: dict[str, Any] = {
            "initialized": True,
            "innovation_norm": 0.0,
            "covariance_trace": float(np.trace(self.covariance)),
        }

    def _weights(self) -> tuple[float, np.ndarray, np.ndarray]:
        n = self.state_dimension
        lam = self.config.alpha**2 * (n + self.config.kappa) - n
        mean_weights = np.full(2 * n + 1, 1.0 / (2.0 * (n + lam)))
        covariance_weights = mean_weights.copy()
        mean_weights[0] = lam / (n + lam)
        covariance_weights[0] = (
            mean_weights[0]
            + 1.0
            - self.config.alpha**2
            + self.config.beta
        )
        return lam, mean_weights, covariance_weights

    def _sigma_points(self, mean: np.ndarray, covariance: np.ndarray) -> np.ndarray:
        lam, _, _ = self._weights()
        scaled = (self.state_dimension + lam) * covariance
        jitter = self.config.covariance_jitter
        for _ in range(6):
            try:
                root = np.linalg.cholesky(
                    scaled + jitter * np.eye(self.state_dimension)
                )
                break
            except np.linalg.LinAlgError:
                jitter *= 10.0
        else:
            raise np.linalg.LinAlgError("UKF covariance is not positive definite")
        points = [mean]
        points.extend(mean + root[:, index] for index in range(self.state_dimension))
        points.extend(mean - root[:, index] for index in range(self.state_dimension))
        return np.asarray(points)

    @staticmethod
    def _weighted_covariance(
        samples: np.ndarray,
        mean: np.ndarray,
        weights: np.ndarray,
    ) -> np.ndarray:
        centered = samples - mean
        return np.einsum("i,ij,ik->jk", weights, centered, centered)

    def step(
        self,
        *,
        time_s: float,
        measured_state: np.ndarray,
        measured_generalized_input_nm: np.ndarray,
        model: BaseParameterHumanModel,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        measurement = np.asarray(measured_state, dtype=float)
        current_input = np.asarray(measured_generalized_input_nm, dtype=float)
        if measurement.shape != (4,) or current_input.shape != (2,):
            raise ValueError("UKF measurement/input dimensions must be four/two")
        dt = float(time_s) - self.last_time_s
        if dt < -1e-12:
            raise ValueError("UKF timestamps must be causal")
        lam, mean_weights, covariance_weights = self._weights()
        del lam
        if dt > 1e-12:
            sigma = self._sigma_points(self.mean, self.covariance)
            propagated = np.array(
                [
                    model.step_dynamics(point, self.last_input_nm, dt)
                    for point in sigma
                ]
            )
            predicted_mean = mean_weights @ propagated
            predicted_covariance = self._weighted_covariance(
                propagated, predicted_mean, covariance_weights
            )
            scale = max(dt / self.config.nominal_update_period_s, 0.25)
            process_covariance = scale * np.diag(
                [
                    self.config.process_q_std_rad**2,
                    self.config.process_q_std_rad**2,
                    self.config.process_dq_std_rad_s**2,
                    self.config.process_dq_std_rad_s**2,
                ]
            )
            predicted_covariance += process_covariance
        else:
            propagated = self._sigma_points(self.mean, self.covariance)
            predicted_mean = self.mean.copy()
            predicted_covariance = self.covariance.copy()

        measurement_sigma = propagated.copy()
        predicted_measurement = mean_weights @ measurement_sigma
        measurement_covariance = self._weighted_covariance(
            measurement_sigma, predicted_measurement, covariance_weights
        )
        measurement_noise = np.diag(
            [
                self.config.measurement_q_std_rad**2,
                self.config.measurement_q_std_rad**2,
                self.config.measurement_dq_std_rad_s**2,
                self.config.measurement_dq_std_rad_s**2,
            ]
        )
        innovation_covariance = measurement_covariance + measurement_noise
        state_measurement_cross = np.einsum(
            "i,ij,ik->jk",
            covariance_weights,
            propagated - predicted_mean,
            measurement_sigma - predicted_measurement,
        )
        gain = np.linalg.solve(
            innovation_covariance.T, state_measurement_cross.T
        ).T
        innovation = measurement - predicted_measurement
        self.mean = predicted_mean + gain @ innovation
        self.covariance = (
            predicted_covariance - gain @ innovation_covariance @ gain.T
        )
        self.covariance = 0.5 * (self.covariance + self.covariance.T)
        eigenvalues, eigenvectors = np.linalg.eigh(self.covariance)
        self.covariance = (
            eigenvectors
            @ np.diag(np.maximum(eigenvalues, self.config.covariance_jitter))
            @ eigenvectors.T
        )
        self.last_time_s = float(time_s)
        self.last_input_nm = current_input.copy()
        self.update_count += 1
        self.last_diagnostics = {
            "initialized": True,
            "update_count": self.update_count,
            "dt_s": dt,
            "innovation_norm": float(np.linalg.norm(innovation)),
            "covariance_trace": float(np.trace(self.covariance)),
            "minimum_covariance_eigenvalue": float(
                np.min(np.linalg.eigvalsh(self.covariance))
            ),
            "state_dimension": self.state_dimension,
            "parameter_state_dimension": self.parameter_state_dimension,
        }
        return self.mean.copy(), dict(self.last_diagnostics)
