"""Fixed-setting robust Windowed NLS variants for Stage 9K diagnostics."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from traction_mpc.identification.base_identifier import IdentifierResult
from traction_mpc.models.spring2d_dynamics import step_dynamics


class RobustWindowedLeastSquaresIdentifier:
    """Windowed NLS with MAD-standardized Huber or Cauchy residuals.

    The robust scale is frozen during each optimizer call.  The covariance is a
    local pseudo-inverse diagnostic and is not a formal confidence guarantee.
    """

    parameter_names = ("m", "k", "b_r")
    _F_SCALE = {"huber": 1.345, "cauchy": 2.3849}

    def __init__(
        self,
        model_params: dict[str, Any],
        cfg: dict[str, Any],
        loss: str,
        smoothing_alpha: float = 0.5,
    ):
        loss = str(loss).lower()
        if loss not in self._F_SCALE:
            raise ValueError("Robust NLS loss must be 'huber' or 'cauchy'.")
        self.base_model_params = dict(model_params)
        self.cfg = dict(cfg)
        self.loss = loss
        self.f_scale = float(self._F_SCALE[loss])
        self.smoothing_alpha = float(smoothing_alpha)
        self.window_size = int(cfg.get("window_size", 80))
        self.update_interval = int(cfg.get("update_interval", 10))
        self.lambda_reg = float(cfg.get("lambda_reg", 1.0e-3))
        self.max_nfev = int(cfg.get("max_nfev", 80))
        self.state_weights = np.asarray(cfg.get("state_weights", [1.0, 0.2, 6.0, 0.5]), dtype=float)
        self.param_scale = np.asarray(cfg.get("param_scale", [1.0, 450.0, 20.0]), dtype=float)
        self.bounds = self._parse_bounds(cfg.get("bounds", {}))
        self.theta0 = self._theta_from_params(self.base_model_params)
        self.theta_hat = self.theta0.copy()
        self.transitions: deque[tuple[np.ndarray, np.ndarray, np.ndarray]] = deque(maxlen=self.window_size)
        self.num_transitions = 0
        self.last_prediction_error = np.nan
        self.last_success = True
        self.last_diagnostics: dict[str, Any] = self._empty_diagnostics()

    def reset(self) -> None:
        self.theta_hat = self.theta0.copy()
        self.transitions.clear()
        self.num_transitions = 0
        self.last_prediction_error = np.nan
        self.last_success = True
        self.last_diagnostics = self._empty_diagnostics()

    def add_transition(self, x_obs: np.ndarray, action: np.ndarray, x_next_obs: np.ndarray) -> IdentifierResult:
        x = self._state_array(x_obs)
        u = self._action_array(action)
        x_next = self._state_array(x_next_obs)
        pred = self._predict_next(x, u, self.theta_hat)
        self.last_prediction_error = float(np.linalg.norm(x_next - pred))
        self.transitions.append((x, u, x_next))
        self.num_transitions += 1
        updated = False
        success = self.last_success
        if len(self.transitions) >= 2 and self.num_transitions % self.update_interval == 0:
            old = self.theta_hat.copy()
            scale = self._component_scale(old)
            result = least_squares(
                lambda theta: self._standardized_residuals(theta, scale, include_regularization=True),
                old,
                bounds=self.bounds,
                loss=self.loss,
                f_scale=self.f_scale,
                max_nfev=self.max_nfev,
            )
            candidate = np.asarray(result.x, dtype=float)
            success = bool(result.success and np.all(np.isfinite(candidate)))
            if success:
                smoothed = (1.0 - self.smoothing_alpha) * old + self.smoothing_alpha * candidate
                self.theta_hat = np.clip(smoothed, self.bounds[0], self.bounds[1])
            self.last_success = success
            updated = True
            self.last_diagnostics = self._diagnostics(scale, old, result, success)
        return IdentifierResult(
            theta_hat=self.get_parameter_estimate(),
            prediction_error=self.last_prediction_error,
            updated=updated,
            num_samples=len(self.transitions),
            success=success,
        )

    def get_parameter_estimate(self) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.parameter_names, self.theta_hat)}

    def get_model_params(self) -> dict[str, Any]:
        params = dict(self.base_model_params)
        params.update(self.get_parameter_estimate())
        return params

    def get_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diagnostics)

    def _component_scale(self, theta: np.ndarray) -> np.ndarray:
        matrix = self._weighted_residual_matrix(theta)
        median = np.median(matrix, axis=0)
        mad = 1.4826 * np.median(np.abs(matrix - median), axis=0)
        # Fixed floors are in the already weighted residual coordinates.
        floor = np.array([1.0e-3, 2.5e-3, 8.0e-4, 3.0e-3], dtype=float)
        return np.maximum(mad, floor)

    def _weighted_residual_matrix(self, theta: np.ndarray) -> np.ndarray:
        rows = []
        for x, u, x_next in self.transitions:
            rows.append(self.state_weights * (x_next - self._predict_next(x, u, theta)))
        return np.asarray(rows, dtype=float)

    def _standardized_residuals(self, theta: np.ndarray, scale: np.ndarray, include_regularization: bool) -> np.ndarray:
        data = (self._weighted_residual_matrix(np.asarray(theta, dtype=float)) / scale).reshape(-1)
        if not include_regularization:
            return data
        reg = np.sqrt(self.lambda_reg) * ((np.asarray(theta, dtype=float) - self.theta_hat) / self.param_scale)
        return np.concatenate([data, reg])

    def _numerical_jacobian(self, theta: np.ndarray, scale: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=float)
        columns = []
        for index in range(len(theta)):
            step = max(abs(theta[index]), self.param_scale[index]) * 1.0e-6
            plus = theta.copy(); plus[index] += step
            minus = theta.copy(); minus[index] -= step
            plus = np.clip(plus, self.bounds[0], self.bounds[1])
            minus = np.clip(minus, self.bounds[0], self.bounds[1])
            denominator = plus[index] - minus[index]
            columns.append((self._standardized_residuals(plus, scale, False) - self._standardized_residuals(minus, scale, False)) / denominator)
        return np.column_stack(columns)

    def _robust_weights(self, residuals: np.ndarray) -> np.ndarray:
        magnitude = np.abs(np.asarray(residuals, dtype=float))
        if self.loss == "huber":
            return np.where(magnitude <= self.f_scale, 1.0, self.f_scale / np.maximum(magnitude, 1.0e-12))
        return 1.0 / (1.0 + (magnitude / self.f_scale) ** 2)

    def _diagnostics(self, scale: np.ndarray, old: np.ndarray, result: Any, success: bool) -> dict[str, Any]:
        theta = self.theta_hat.copy()
        residuals = self._standardized_residuals(theta, scale, False)
        jacobian = self._numerical_jacobian(theta, scale)
        weights = self._robust_weights(residuals)
        info = jacobian.T @ (weights[:, None] * jacobian)
        info += self.lambda_reg * np.diag(1.0 / self.param_scale**2)
        dof = max(len(residuals) - len(theta), 1)
        sigma2 = float(np.sum(weights * residuals**2) / dof)
        covariance = sigma2 * np.linalg.pinv(info, rcond=1.0e-12)
        covariance = 0.5 * (covariance + covariance.T)
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        denom = np.outer(std, std)
        correlation = np.divide(covariance, denom, out=np.full_like(covariance, np.nan), where=denom > 0.0)
        singular_values = np.linalg.svd(jacobian, compute_uv=False)
        return {
            "valid_samples": len(self.transitions),
            "residual_norm": float(np.linalg.norm(residuals)),
            "robust_scale": scale.copy(),
            "jacobian_rank": int(np.linalg.matrix_rank(jacobian)),
            "singular_values": singular_values.copy(),
            "minimum_singular_value": float(np.min(singular_values)) if len(singular_values) else np.nan,
            "condition_number": float(np.linalg.cond(info)),
            "covariance": covariance.copy(),
            "correlation": correlation.copy(),
            "bound_hit": bool(np.any(np.isclose(theta, self.bounds[0])) or np.any(np.isclose(theta, self.bounds[1]))),
            "update_magnitude": float(np.linalg.norm(theta - old)),
            "optimizer_converged": bool(success),
            "optimizer_status": int(getattr(result, "status", 0)),
            "optimizer_message": str(getattr(result, "message", "")),
            "optimizer_iterations": int(getattr(result, "nfev", 0)),
        }

    @staticmethod
    def _empty_diagnostics() -> dict[str, Any]:
        return {
            "valid_samples": 0,
            "residual_norm": np.nan,
            "robust_scale": np.full(4, np.nan),
            "jacobian_rank": 0,
            "singular_values": np.full(3, np.nan),
            "minimum_singular_value": np.nan,
            "condition_number": np.nan,
            "covariance": np.full((3, 3), np.nan),
            "correlation": np.full((3, 3), np.nan),
            "bound_hit": False,
            "update_magnitude": 0.0,
            "optimizer_converged": True,
            "optimizer_status": 0,
            "optimizer_message": "not_updated",
            "optimizer_iterations": 0,
        }

    def _predict_next(self, x: np.ndarray, u: np.ndarray, theta: np.ndarray) -> np.ndarray:
        params = dict(self.base_model_params)
        params.update({name: float(value) for name, value in zip(self.parameter_names, theta)})
        return step_dynamics(x, u, float(params["dt"]), params)

    def _theta_from_params(self, params: dict[str, Any]) -> np.ndarray:
        return np.array([float(params[name]) for name in self.parameter_names], dtype=float)

    def _parse_bounds(self, bounds_cfg: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        lower, upper = [], []
        for name in self.parameter_names:
            values = bounds_cfg.get(name)
            if values is None or len(values) != 2:
                raise ValueError(f"Missing or invalid identifier bound for '{name}'.")
            lower.append(float(values[0])); upper.append(float(values[1]))
        return np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)

    @staticmethod
    def _state_array(values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=float)
        if raw.shape != (4,):
            raise ValueError("Identifier state must have shape (4,).")
        return raw

    @staticmethod
    def _action_array(values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=float)
        if raw.shape != (2,):
            raise ValueError("Identifier action must have shape (2,).")
        return raw
