"""True multiple-shooting inverse-mass joint MHE for Spring2D Stage 10C."""

from __future__ import annotations

from collections import deque
import time
from typing import Any

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

from traction_mpc.models.spring2d_dynamics import step_dynamics


class MultipleShootingInverseMassMHE:
    """Joint state/parameter MHE with a decision variable for every window state.

    The decision vector is ``[x_0, ..., x_N, lambda]``.  Process residuals
    explicitly represent ``w_i = x_{i+1} - f(x_i, u_i, lambda)``.  Raw
    measurements enter only through the measurement residual; UKF states may
    seed the numerical iterate and form the arrival prior, but are never used
    as equality constraints or pseudo-measurements.
    """

    def __init__(self, model_params: dict[str, Any], cfg: dict[str, Any]):
        self.base_model_params = dict(model_params)
        self.cfg = dict(cfg)
        self.window_size = int(cfg["window_size"])
        self.update_interval = int(cfg["update_interval"])
        self.max_nfev = int(cfg["max_nfev"])
        self.measurement_weights = np.asarray(cfg["measurement_weights"], dtype=float)
        self.process_weights = np.asarray(cfg["process_weights"], dtype=float)
        self.state_scale = np.asarray(cfg["state_scale"], dtype=float)
        self.arrival_state_scale = np.asarray(cfg["arrival_state_scale"], dtype=float)
        self.lambda_scale = float(cfg["lambda_scale"])
        self.lambda_arrival_state = float(cfg["lambda_arrival_state"])
        self.lambda_arrival_parameter = float(cfg["lambda_arrival_parameter"])
        self.max_initialization_probe = bool(cfg.get("initialization_probe", True))
        self.nominal_k = float(self.base_model_params["k"])
        self.nominal_b_r = float(self.base_model_params["b_r"])
        self.nominal_lambda = 1.0 / float(self.base_model_params["m"])
        mass_bounds = tuple(float(value) for value in cfg["mass_bounds"])
        self.lambda_bounds = (1.0 / mass_bounds[1], 1.0 / mass_bounds[0])
        self.state_lower = np.asarray(cfg["state_lower"], dtype=float)
        self.state_upper = np.asarray(cfg["state_upper"], dtype=float)
        self.measurements: deque[np.ndarray] = deque(maxlen=self.window_size + 1)
        self.warm_states: deque[np.ndarray] = deque(maxlen=self.window_size + 1)
        self.actions: deque[np.ndarray] = deque(maxlen=self.window_size)
        self.arrival_state: np.ndarray | None = None
        self.lambda_hat = self.nominal_lambda
        self.state_hat: np.ndarray | None = None
        self.last_states: np.ndarray | None = None
        self.last_diagnostics: dict[str, Any] = {}
        self.num_transitions = 0
        self._initialization_probed = False

    def reset(self, measurement: np.ndarray, warm_state: np.ndarray | None = None) -> np.ndarray:
        y = self._measurement(measurement)
        warm = self._state(warm_state if warm_state is not None else y)
        self.measurements.clear(); self.warm_states.clear(); self.actions.clear()
        self.measurements.append(y); self.warm_states.append(warm)
        self.arrival_state = warm.copy()
        self.lambda_hat = self.nominal_lambda
        self.state_hat = warm.copy()
        self.last_states = None
        self.last_diagnostics = {"updated": False, "success": True, "status": "reset"}
        self.num_transitions = 0; self._initialization_probed = False
        return self.state_hat.copy()

    def add_measurement(self, action: np.ndarray, measurement: np.ndarray, warm_state: np.ndarray | None = None) -> dict[str, Any]:
        if self.state_hat is None or self.arrival_state is None:
            raise RuntimeError("MultipleShootingInverseMassMHE must be reset before use")
        action_arr = np.asarray(action, dtype=float)
        y = self._measurement(measurement)
        warm = self._state(warm_state if warm_state is not None else y)
        if len(self.actions) == self.window_size:
            # Keep the arrival prior aligned with the deque's next window start.
            if self.last_states is not None and len(self.last_states) > 1:
                self.arrival_state = self.last_states[1].copy()
                # The solver trajectory is indexed on the *current* window.
                # Shift it after consuming its next state so that, between two
                # solver calls, repeated deque advances do not repeatedly use
                # the same stale x_1 as the arrival prior.
                self.last_states = self.last_states[1:].copy()
            else:
                params = self._physical_params(self.lambda_hat)
                self.arrival_state = self._safe_step(self.arrival_state, self.actions[0], params)
        self.actions.append(action_arr.copy()); self.measurements.append(y); self.warm_states.append(warm)
        self.num_transitions += 1
        updated = False
        if self.num_transitions % self.update_interval == 0:
            updated = True
            success = self._solve_window()
        else:
            params = self._physical_params(self.lambda_hat)
            self.state_hat = self._safe_step(self.state_hat, action_arr, params)
            success = bool(self.last_diagnostics.get("success", True))
            self.last_diagnostics = {**self.last_diagnostics, "updated": False, "success": success, "status": "propagated", "solve_time_s": 0.0}
        return {
            "state_hat": self.state_hat.copy(), "lambda_hat": float(self.lambda_hat), "m_hat": self.mass_hat,
            "updated": updated, "success": success, "diagnostics": dict(self.last_diagnostics),
        }

    @property
    def mass_hat(self) -> float:
        return float(1.0 / self.lambda_hat)

    def get_model_params(self) -> dict[str, Any]:
        return self._physical_params(self.lambda_hat)

    def _solve_window(self) -> bool:
        started = time.perf_counter()
        measurements = np.asarray(self.measurements, dtype=float)
        warm_states = np.asarray(self.warm_states, dtype=float)
        actions = np.asarray(self.actions, dtype=float)
        if len(measurements) != len(actions) + 1:
            raise RuntimeError("MHE window alignment failure")
        x_prior = np.asarray(self.arrival_state, dtype=float); lambda_prior = float(self.lambda_hat)
        primary_initial = self._initial_guess(warm_states, lambda_prior)
        initial_states, initial_parameter = self._unpack(primary_initial, len(measurements))
        before_terms = self._objective_terms(initial_states, initial_parameter, measurements, actions, x_prior, lambda_prior)
        result, states, parameter = self._least_squares(primary_initial, measurements, actions, x_prior, lambda_prior)
        success = result is not None and bool(result.success) and np.all(np.isfinite(result.x))
        probe_delta = np.nan; probe_success = False
        if success and self.max_initialization_probe and not self._initialization_probed and len(actions) >= self.window_size:
            self._initialization_probed = True
            raw_initial = self._initial_guess(measurements, lambda_prior)
            probe, probe_states, probe_parameter = self._least_squares(raw_initial, measurements, actions, x_prior, lambda_prior)
            probe_success = probe is not None and bool(probe.success) and np.all(np.isfinite(probe.x))
            if probe_success:
                probe_delta = abs(float(probe_parameter) - float(parameter)) / max(abs(float(parameter)), 1.0e-12)
        if success and result is not None:
            self.last_states = states.copy(); self.state_hat = states[-1].copy(); self.arrival_state = states[0].copy(); self.lambda_hat = float(parameter)
            residual = np.asarray(result.fun, dtype=float)
            jacobian_raw = result.jac
            jac = jacobian_raw.toarray() if hasattr(jacobian_raw, "toarray") else np.asarray(jacobian_raw, dtype=float)
            information = jac.T @ jac
            dof = max(len(residual) - len(result.x), 1)
            covariance = float(residual @ residual / dof) * np.linalg.pinv(information, rcond=1.0e-12)
            lambda_std = float(np.sqrt(max(covariance[-1, -1], 0.0))) * self.lambda_scale
            singular = np.linalg.svd(jac, compute_uv=False)
            process = self._process_residuals(states, actions, float(parameter))
            after_terms = self._objective_terms(states, float(parameter), measurements, actions, x_prior, lambda_prior)
            failure_message = ""
        else:
            # A failed solve must still advance the reported current estimate
            # through the transition that has just been appended.  Retaining a
            # stale state would label x_{k-1} as x_k and make subsequent
            # controls/action alignment drift.  The old trajectory is no
            # longer valid for arrival shifting, so fall back to one-step
            # propagation of the existing arrival prior on later deque moves.
            params = self._physical_params(self.lambda_hat)
            self.state_hat = self._safe_step(self.state_hat, actions[-1], params)
            self.last_states = None
            jac = np.empty((0, 0)); lambda_std = np.nan; singular = np.empty(0); process = np.full((len(actions), 4), np.nan)
            after_terms = {key: np.nan for key in before_terms}
            failure_message = "optimizer_failure" if result is None else str(result.message)
        self.last_diagnostics = {
            "updated": True, "success": bool(success), "status": str(result.message) if success and result is not None else failure_message,
            "nfev": int(result.nfev) if result is not None else 0, "cost": float(result.cost) if result is not None else np.nan,
            "solve_time_s": float(time.perf_counter() - started), "window_length": int(len(actions)), "lambda_std": lambda_std,
            "jacobian_rank": int(np.linalg.matrix_rank(jac)) if jac.size else 0,
            "jacobian_condition": float(np.linalg.cond(jac)) if jac.size else np.nan,
            "minimum_singular_value": float(np.min(singular)) if singular.size else np.nan,
            "process_residual_rmse": float(np.sqrt(np.nanmean(process**2))) if np.any(np.isfinite(process)) else np.nan,
            "process_residual_max_abs": float(np.nanmax(np.abs(process))) if np.any(np.isfinite(process)) else np.nan,
            "parameter_bound_hit": bool(np.isclose(self.lambda_hat, self.lambda_bounds[0]) or np.isclose(self.lambda_hat, self.lambda_bounds[1])),
            "fallback_applied": bool(not success), "reported_current_is_final_window_state": bool(success),
            "arrival_prior_state": x_prior.copy(), "warm_start_states": warm_states.copy(),
            **{f"before_{key}": value for key, value in before_terms.items()},
            **{f"after_{key}": value for key, value in after_terms.items()},
            "initialization_probe_success": bool(probe_success), "initialization_probe_relative_lambda_delta": probe_delta,
        }
        return bool(success)

    def _least_squares(self, initial: np.ndarray, measurements: np.ndarray, actions: np.ndarray, x_prior: np.ndarray, lambda_prior: float) -> tuple[Any | None, np.ndarray, float]:
        lower, upper = self._bounds(len(measurements))
        try:
            result = least_squares(
                lambda z: self._residual(z, measurements, actions, x_prior, lambda_prior), initial,
                bounds=(lower, upper), jac_sparsity=self._jacobian_sparsity(len(measurements)), method="trf", tr_solver="lsmr",
                max_nfev=self.max_nfev, xtol=float(self.cfg["xtol"]), ftol=float(self.cfg["ftol"]), gtol=float(self.cfg["gtol"]),
            )
            states, parameter = self._unpack(result.x, len(measurements))
            return result, states, parameter
        except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
            return None, np.empty((0, 4)), np.nan

    def _residual(self, decision: np.ndarray, measurements: np.ndarray, actions: np.ndarray, x_prior: np.ndarray, lambda_prior: float) -> np.ndarray:
        states, parameter = self._unpack(decision, len(measurements))
        measurement = ((states - measurements) * self.measurement_weights).reshape(-1)
        process = (self._process_residuals(states, actions, parameter) * self.process_weights).reshape(-1)
        arrival_state = np.sqrt(self.lambda_arrival_state) * (states[0] - x_prior) / self.arrival_state_scale
        arrival_lambda = np.sqrt(self.lambda_arrival_parameter) * (parameter - lambda_prior) / self.lambda_scale
        if not np.all(np.isfinite(process)):
            return np.full(len(measurement) + len(process) + 5, 1.0e12)
        return np.concatenate([measurement, process, arrival_state, [arrival_lambda]])

    def _process_residuals(self, states: np.ndarray, actions: np.ndarray, parameter: float) -> np.ndarray:
        params = self._physical_params(parameter)
        residuals = []
        for index, action in enumerate(actions):
            predicted = self._safe_step(states[index], action, params)
            residuals.append(states[index + 1] - predicted)
        return np.asarray(residuals, dtype=float)

    def _objective_terms(
        self,
        states: np.ndarray,
        parameter: float,
        measurements: np.ndarray,
        actions: np.ndarray,
        x_prior: np.ndarray,
        lambda_prior: float,
    ) -> dict[str, float]:
        """Return half-squared residual contributions for audit logging."""
        measurement = ((states - measurements) * self.measurement_weights).reshape(-1)
        process = (self._process_residuals(states, actions, parameter) * self.process_weights).reshape(-1)
        arrival_state = np.sqrt(self.lambda_arrival_state) * (states[0] - x_prior) / self.arrival_state_scale
        arrival_lambda = np.sqrt(self.lambda_arrival_parameter) * (parameter - lambda_prior) / self.lambda_scale
        state_bound_hits = np.isclose(states, self.state_lower[None, :]) | np.isclose(states, self.state_upper[None, :])
        return {
            "measurement_cost": float(0.5 * measurement @ measurement),
            "process_cost": float(0.5 * process @ process),
            "arrival_cost": float(0.5 * arrival_state @ arrival_state),
            "inverse_mass_prior_cost": float(0.5 * arrival_lambda * arrival_lambda),
            "total_cost": float(0.5 * (measurement @ measurement + process @ process + arrival_state @ arrival_state + arrival_lambda * arrival_lambda)),
            "measurement_residual_rms": float(np.sqrt(np.mean(measurement**2))),
            "process_residual_rms_weighted": float(np.sqrt(np.mean(process**2))),
            "process_residual_rms_raw": float(np.sqrt(np.mean((self._process_residuals(states, actions, parameter)) ** 2))),
            "state_bound_hit_count": int(np.sum(state_bound_hits)),
            "parameter_bound_hit": int(np.isclose(parameter, self.lambda_bounds[0]) or np.isclose(parameter, self.lambda_bounds[1])),
        }

    def _physical_params(self, parameter: float) -> dict[str, Any]:
        params = dict(self.base_model_params)
        params.update({"m": 1.0 / float(parameter), "k": self.nominal_k, "b_r": self.nominal_b_r})
        return params

    def _initial_guess(self, warm_states: np.ndarray, parameter: float) -> np.ndarray:
        states = np.asarray(warm_states, dtype=float).copy()
        states[:, 2] = np.maximum(states[:, 2], self.state_lower[2])
        scaled = (states / self.state_scale).reshape(-1)
        return np.concatenate([scaled, [parameter / self.lambda_scale]])

    def _unpack(self, decision: np.ndarray, n_states: int) -> tuple[np.ndarray, float]:
        states = np.asarray(decision[: 4 * n_states], dtype=float).reshape(n_states, 4) * self.state_scale
        parameter = float(decision[-1] * self.lambda_scale)
        return states, parameter

    def _bounds(self, n_states: int) -> tuple[np.ndarray, np.ndarray]:
        lower_state = np.tile(self.state_lower / self.state_scale, n_states)
        upper_state = np.tile(self.state_upper / self.state_scale, n_states)
        return np.r_[lower_state, self.lambda_bounds[0] / self.lambda_scale], np.r_[upper_state, self.lambda_bounds[1] / self.lambda_scale]

    def _jacobian_sparsity(self, n_states: int) -> Any:
        n_process = n_states - 1; rows = 4 * n_states + 4 * n_process + 5; cols = 4 * n_states + 1
        sparsity = lil_matrix((rows, cols), dtype=int)
        # Measurement residuals depend only on their corresponding state.
        for state_index in range(n_states):
            r0 = 4 * state_index; c0 = 4 * state_index
            sparsity[r0:r0 + 4, c0:c0 + 4] = 1
        # Every process block depends on x_i, x_{i+1}, and lambda.
        process_offset = 4 * n_states
        for index in range(n_process):
            r0 = process_offset + 4 * index; c0 = 4 * index
            sparsity[r0:r0 + 4, c0:c0 + 8] = 1; sparsity[r0:r0 + 4, -1] = 1
        arrival_offset = process_offset + 4 * n_process
        sparsity[arrival_offset:arrival_offset + 4, :4] = 1; sparsity[arrival_offset + 4, -1] = 1
        return sparsity.tocsr()

    def _safe_step(self, state: np.ndarray, action: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        try:
            result = step_dynamics(state, action, float(params["dt"]), params)
            if not np.all(np.isfinite(result)):
                return np.full(4, np.nan)
            return result
        except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
            return np.full(4, np.nan)

    def _state(self, values: np.ndarray) -> np.ndarray:
        state = np.asarray(values, dtype=float).copy()
        if state.shape != (4,) or not np.all(np.isfinite(state)):
            raise ValueError("MHE state must be finite with shape (4,)")
        return np.clip(state, self.state_lower, self.state_upper)

    @staticmethod
    def _measurement(values: np.ndarray) -> np.ndarray:
        measurement = np.asarray(values, dtype=float).copy()
        if measurement.shape != (4,) or not np.all(np.isfinite(measurement)):
            raise ValueError("MHE measurement must be finite with shape (4,)")
        measurement[2] = max(float(measurement[2]), 1.0e-6)
        return measurement
