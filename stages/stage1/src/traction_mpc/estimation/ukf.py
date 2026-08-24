"""Unscented Kalman state estimators for Spring2D observations."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from traction_mpc.common.types import Spring2DObservation
from traction_mpc.estimation.filters import BaseObservationFilter, observation_state
from traction_mpc.models.spring2d_dynamics import step_dynamics


def _diag(values: list[float] | tuple[float, ...] | np.ndarray, size: int, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.shape != (size,):
        raise ValueError(f"{name} must contain {size} entries.")
    if np.any(arr < 0.0) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite and non-negative.")
    return np.diag(arr)


def _condition_measurement_noise(cfg: dict[str, Any], condition_name: str) -> list[float]:
    key = f"measurement_noise_diag_{condition_name}" if condition_name else ""
    if key and key in cfg:
        return list(cfg[key])
    if "measurement_noise_diag" in cfg:
        return list(cfg["measurement_noise_diag"])
    return list(cfg.get("measurement_noise_diag_noise", [1.0e-4, 1.0e-3, 1.0e-5, 1.0e-4]))


def _symmetric(matrix: np.ndarray) -> np.ndarray:
    return 0.5 * (matrix + matrix.T)


class _UnscentedCore:
    def __init__(self, dim: int, alpha: float, beta: float, kappa: float, jitter: float):
        self.dim = int(dim)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.kappa = float(kappa)
        self.jitter = float(jitter)
        self.lambda_ = self.alpha**2 * (self.dim + self.kappa) - self.dim
        self.scale = self.dim + self.lambda_
        if self.scale <= 0.0:
            raise ValueError("UKF alpha/beta/kappa produce non-positive sigma-point scale.")
        self.wm = np.full(2 * self.dim + 1, 0.5 / self.scale, dtype=float)
        self.wc = np.full(2 * self.dim + 1, 0.5 / self.scale, dtype=float)
        self.wm[0] = self.lambda_ / self.scale
        self.wc[0] = self.wm[0] + (1.0 - self.alpha**2 + self.beta)

    def sigma_points(self, mean: np.ndarray, covariance: np.ndarray) -> np.ndarray:
        mean = np.asarray(mean, dtype=float)
        cov = _symmetric(np.asarray(covariance, dtype=float))
        eye = np.eye(self.dim)
        last_error: Exception | None = None
        for multiplier in (1.0, 10.0, 100.0, 1000.0, 10000.0):
            try:
                chol = np.linalg.cholesky(cov + self.jitter * multiplier * eye)
                break
            except np.linalg.LinAlgError as exc:
                last_error = exc
        else:
            raise np.linalg.LinAlgError("Failed to factor UKF covariance.") from last_error

        sigma = np.empty((2 * self.dim + 1, self.dim), dtype=float)
        sigma[0] = mean
        spread = np.sqrt(self.scale) * chol
        for i in range(self.dim):
            sigma[1 + i] = mean + spread[:, i]
            sigma[1 + self.dim + i] = mean - spread[:, i]
        return sigma

    def mean_and_covariance(self, sigma: np.ndarray, noise_covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mean = np.sum(self.wm[:, None] * sigma, axis=0)
        delta = sigma - mean
        covariance = np.zeros((sigma.shape[1], sigma.shape[1]), dtype=float)
        for i in range(sigma.shape[0]):
            covariance += self.wc[i] * np.outer(delta[i], delta[i])
        covariance = _symmetric(covariance + noise_covariance)
        covariance += self.jitter * np.eye(covariance.shape[0])
        return mean, covariance


class UKFStateEstimator(BaseObservationFilter):
    """Model-based UKF over x = [theta, omega, r, r_dot]."""

    def __init__(self, cfg: dict[str, Any], condition_name: str = ""):
        super().__init__()
        self.cfg = dict(cfg)
        self.condition_name = condition_name
        self.core = _UnscentedCore(
            dim=4,
            alpha=float(self.cfg.get("alpha", 0.5)),
            beta=float(self.cfg.get("beta", 2.0)),
            kappa=float(self.cfg.get("kappa", 0.0)),
            jitter=float(self.cfg.get("covariance_jitter", 1.0e-9)),
        )
        self.initial_covariance = _diag(
            self.cfg.get("initial_cov_diag", [0.01, 0.05, 0.001, 0.01]),
            4,
            "initial_cov_diag",
        )
        self.process_noise = _diag(
            self.cfg.get("process_noise_diag", [1.0e-5, 1.0e-3, 1.0e-6, 1.0e-4]),
            4,
            "process_noise_diag",
        )
        self.measurement_noise = _diag(_condition_measurement_noise(self.cfg, condition_name), 4, "measurement_noise_diag")
        self.P = self.initial_covariance.copy()
        self._z = np.zeros(4, dtype=float)

    def reset(
        self,
        initial_observation: Spring2DObservation,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del true_state, model_params
        self._z = observation_state(initial_observation)
        self._z[2] = max(float(self._z[2]), 1.0e-6)
        self.P = self.initial_covariance.copy()
        self.x_hat = self._z.copy()
        self._diagnostics = self._diagnostics_from_state(False, np.nan)
        return self.get_state()

    def predict(
        self,
        action: np.ndarray,
        dt: float,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        if model_params is None:
            raise ValueError("UKFStateEstimator requires model_params for predict().")
        if self.x_hat is None:
            raise RuntimeError("UKFStateEstimator has not been reset.")
        try:
            sigma = self.core.sigma_points(self._z, self.P)
            propagated = np.asarray(
                [self._propagate_sigma_point(point, action, dt, model_params) for point in sigma],
                dtype=float,
            )
            if not np.all(np.isfinite(propagated)):
                raise FloatingPointError("UKF prediction produced non-finite sigma points.")
            self._z, self.P = self.core.mean_and_covariance(propagated, self.process_noise)
            self._z[2] = max(float(self._z[2]), 1.0e-6)
            self.x_hat = self._z.copy()
            self._diagnostics = self._diagnostics_from_state(False, np.nan)
        except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
            self._diagnostics = self._diagnostics_from_state(True, np.nan)
        return self.get_state()

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del dt, action, true_state, model_params
        y = observation_state(observation)
        prior_failed = bool(self._diagnostics.get("ukf_failed", False))
        try:
            innovation_norm = self._measurement_update(y, self._measurement_from_sigma)
            self._z[2] = max(float(self._z[2]), 1.0e-6)
            self.x_hat = self._z.copy()
            self._diagnostics = self._diagnostics_from_state(prior_failed, innovation_norm)
        except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
            if self.x_hat is None or not np.all(np.isfinite(self.x_hat)):
                self._z = y.copy()
                self._z[2] = max(float(self._z[2]), 1.0e-6)
                self.x_hat = self._z.copy()
            self._diagnostics = self._diagnostics_from_state(True, np.nan)
        return self.get_state()

    def _propagate_sigma_point(
        self,
        point: np.ndarray,
        action: np.ndarray,
        dt: float,
        model_params: dict[str, Any],
    ) -> np.ndarray:
        x_next = step_dynamics(point[:4], action, dt, model_params)
        if not np.all(np.isfinite(x_next)):
            raise FloatingPointError("Non-finite UKF propagated state.")
        return x_next

    def _measurement_from_sigma(self, sigma: np.ndarray) -> np.ndarray:
        return sigma[:, :4]

    def _measurement_update(self, y: np.ndarray, measurement_fn: Callable[[np.ndarray], np.ndarray]) -> float:
        sigma = self.core.sigma_points(self._z, self.P)
        y_sigma = np.asarray(measurement_fn(sigma), dtype=float)
        if not np.all(np.isfinite(y_sigma)):
            raise FloatingPointError("UKF measurement sigma points are non-finite.")
        y_pred = np.sum(self.core.wm[:, None] * y_sigma, axis=0)
        dy = y_sigma - y_pred
        dz = sigma - self._z
        S = np.zeros((4, 4), dtype=float)
        Pzy = np.zeros((self.core.dim, 4), dtype=float)
        for i in range(sigma.shape[0]):
            S += self.core.wc[i] * np.outer(dy[i], dy[i])
            Pzy += self.core.wc[i] * np.outer(dz[i], dy[i])
        S = _symmetric(S + self.measurement_noise)
        S += self.core.jitter * np.eye(4)
        innovation = y - y_pred
        gain = np.linalg.solve(S, Pzy.T).T
        self._z = self._z + gain @ innovation
        self.P = _symmetric(self.P - gain @ S @ gain.T)
        self.P += self.core.jitter * np.eye(self.core.dim)
        if not np.all(np.isfinite(self._z)) or not np.all(np.isfinite(self.P)):
            raise FloatingPointError("UKF update produced non-finite state or covariance.")
        return float(np.linalg.norm(innovation))

    def _diagnostics_from_state(self, failed: bool, innovation_norm: float) -> dict[str, Any]:
        diagnostics = self._default_diagnostics()
        diagnostics.update(
            {
                "innovation_norm": float(innovation_norm),
                "covariance_trace": float(np.trace(self.P)),
                "ukf_failed": bool(failed),
            }
        )
        return diagnostics


class BiasAwareUKFStateEstimator(UKFStateEstimator):
    """UKF over z = [x, b], with measurement y = x + b."""

    def __init__(self, cfg: dict[str, Any], condition_name: str = ""):
        BaseObservationFilter.__init__(self)
        self.cfg = dict(cfg)
        self.condition_name = condition_name
        self.core = _UnscentedCore(
            dim=8,
            alpha=float(self.cfg.get("alpha", 0.5)),
            beta=float(self.cfg.get("beta", 2.0)),
            kappa=float(self.cfg.get("kappa", 0.0)),
            jitter=float(self.cfg.get("covariance_jitter", 1.0e-9)),
        )
        state_covariance = _diag(
            self.cfg.get("initial_state_cov_diag", [0.01, 0.05, 0.001, 0.01]),
            4,
            "initial_state_cov_diag",
        )
        bias_covariance = _diag(
            self.cfg.get("initial_bias_cov_diag", [1.0e-3, 1.0e-3, 1.0e-4, 1.0e-4]),
            4,
            "initial_bias_cov_diag",
        )
        self.initial_covariance = np.block(
            [
                [state_covariance, np.zeros((4, 4), dtype=float)],
                [np.zeros((4, 4), dtype=float), bias_covariance],
            ]
        )
        state_noise = _diag(
            self.cfg.get("process_noise_state_diag", [1.0e-5, 1.0e-3, 1.0e-6, 1.0e-4]),
            4,
            "process_noise_state_diag",
        )
        bias_noise = _diag(
            self.cfg.get("process_noise_bias_diag", [1.0e-7, 1.0e-7, 1.0e-8, 1.0e-8]),
            4,
            "process_noise_bias_diag",
        )
        self.process_noise = np.block(
            [
                [state_noise, np.zeros((4, 4), dtype=float)],
                [np.zeros((4, 4), dtype=float), bias_noise],
            ]
        )
        self.measurement_noise = _diag(_condition_measurement_noise(self.cfg, condition_name), 4, "measurement_noise_diag")
        self.P = self.initial_covariance.copy()
        self._z = np.zeros(8, dtype=float)

    def reset(
        self,
        initial_observation: Spring2DObservation,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del true_state, model_params
        y = observation_state(initial_observation)
        y[2] = max(float(y[2]), 1.0e-6)
        self._z = np.zeros(8, dtype=float)
        self._z[:4] = y
        self.P = self.initial_covariance.copy()
        self.x_hat = self._z[:4].copy()
        self._diagnostics = self._diagnostics_from_state(False, np.nan)
        return self.get_state()

    def _propagate_sigma_point(
        self,
        point: np.ndarray,
        action: np.ndarray,
        dt: float,
        model_params: dict[str, Any],
    ) -> np.ndarray:
        x_next = step_dynamics(point[:4], action, dt, model_params)
        if not np.all(np.isfinite(x_next)):
            raise FloatingPointError("Non-finite bias-aware UKF propagated state.")
        z_next = point.copy()
        z_next[:4] = x_next
        return z_next

    def _measurement_from_sigma(self, sigma: np.ndarray) -> np.ndarray:
        return sigma[:, :4] + sigma[:, 4:8]

    def predict(
        self,
        action: np.ndarray,
        dt: float,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        super().predict(action, dt, model_params=model_params)
        self.x_hat = self._z[:4].copy()
        return self.get_state()

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        super().update(observation, dt, action=action, true_state=true_state, model_params=model_params)
        self.x_hat = self._z[:4].copy()
        self.x_hat[2] = max(float(self.x_hat[2]), 1.0e-6)
        self._z[:4] = self.x_hat
        return self.get_state()

    def _diagnostics_from_state(self, failed: bool, innovation_norm: float) -> dict[str, Any]:
        diagnostics = self._default_diagnostics()
        bias = self._z[4:8] if self._z.shape[0] >= 8 else np.full(4, np.nan)
        diagnostics.update(
            {
                "bias_theta_hat": float(bias[0]),
                "bias_omega_hat": float(bias[1]),
                "bias_r_hat": float(bias[2]),
                "bias_r_dot_hat": float(bias[3]),
                "innovation_norm": float(innovation_norm),
                "covariance_trace": float(np.trace(self.P)),
                "ukf_failed": bool(failed),
            }
        )
        return diagnostics
