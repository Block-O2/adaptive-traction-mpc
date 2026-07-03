"""Windowed nonlinear least-squares identifier for Spring2D."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from traction_mpc.identification.base_identifier import BaseIdentifier, IdentifierResult
from traction_mpc.models.spring2d_dynamics import step_dynamics


class WindowedLeastSquaresIdentifier(BaseIdentifier):
    """Estimate [m, k, b_r] from recent one-step transitions.

    The identifier is logging-only in the current experiment. Controllers should
    keep using their original fixed model unless explicitly changed elsewhere.
    """

    parameter_names = ("m", "k", "b_r")

    def __init__(self, model_params: dict[str, Any], cfg: dict[str, Any]):
        self.base_model_params = dict(model_params)
        self.cfg = dict(cfg)
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

    def reset(self) -> None:
        self.theta_hat = self.theta0.copy()
        self.transitions.clear()
        self.num_transitions = 0
        self.last_prediction_error = np.nan
        self.last_success = True

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
            result = least_squares(
                self._residuals,
                self.theta_hat,
                bounds=self.bounds,
                max_nfev=self.max_nfev,
            )
            if result.success and np.all(np.isfinite(result.x)):
                self.theta_hat = result.x.astype(float)
                success = True
            else:
                success = False
            self.last_success = success
            updated = True

        return IdentifierResult(
            theta_hat=self.get_parameter_estimate(),
            prediction_error=self.last_prediction_error,
            updated=updated,
            num_samples=len(self.transitions),
            success=success,
        )

    def get_parameter_estimate(self) -> dict[str, float]:
        return {
            name: float(value)
            for name, value in zip(self.parameter_names, self.theta_hat)
        }

    def get_model_params(self) -> dict[str, Any]:
        params = dict(self.base_model_params)
        params.update(self.get_parameter_estimate())
        return params

    def _residuals(self, theta: np.ndarray) -> np.ndarray:
        residuals = []
        theta_arr = np.asarray(theta, dtype=float)
        for x, u, x_next in self.transitions:
            pred = self._predict_next(x, u, theta_arr)
            residuals.extend(self.state_weights * (x_next - pred))
        reg = np.sqrt(self.lambda_reg) * ((theta_arr - self.theta_hat) / self.param_scale)
        residuals.extend(reg)
        return np.asarray(residuals, dtype=float)

    def _predict_next(self, x: np.ndarray, u: np.ndarray, theta: np.ndarray) -> np.ndarray:
        params = dict(self.base_model_params)
        params.update({name: float(value) for name, value in zip(self.parameter_names, theta)})
        return step_dynamics(x, u, float(params["dt"]), params)

    def _theta_from_params(self, params: dict[str, Any]) -> np.ndarray:
        return np.array([float(params[name]) for name in self.parameter_names], dtype=float)

    def _parse_bounds(self, bounds_cfg: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        lower = []
        upper = []
        for name in self.parameter_names:
            values = bounds_cfg.get(name)
            if values is None:
                raise ValueError(f"Missing identifier bound for parameter '{name}'.")
            if len(values) != 2:
                raise ValueError(f"Identifier bound for '{name}' must be [lower, upper].")
            lower.append(float(values[0]))
            upper.append(float(values[1]))
        return np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)

    def _state_array(self, values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=float)
        if raw.shape != (4,):
            raise ValueError("Identifier state must have shape (4,) as [theta, omega, r, r_dot].")
        return raw

    def _action_array(self, values: np.ndarray) -> np.ndarray:
        raw = np.asarray(values, dtype=float)
        if raw.shape != (2,):
            raise ValueError("Identifier action must have shape (2,) as [F_tan, F_rad].")
        return raw
