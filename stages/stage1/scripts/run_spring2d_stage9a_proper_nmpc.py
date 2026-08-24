"""Stage 9A proper multiple-shooting NMPC baseline for Spring2D single-link."""

from __future__ import annotations

import argparse
import copy
import csv
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import casadi as ca
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import (
    append_adaptive_fields,
    current_prediction_params,
    initial_identifier_result,
    load_experiment_config,
    observation_from_state,
    parameter_bound_hit,
    parameter_vector,
    run_condition,
    select_observation_by_source,
)
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE
from run_spring2d_stage8e_explicit_nmpc import (
    _as_bool,
    _clipped_max_excluding_one,
    _decision_rows,
    _finite_max,
    _finite_mean,
    _finite_percentile,
    _first_reach_time,
    _fmt,
    _series,
    configure_cem_run,
)
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC as CEMAdaptiveMPC
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.cost import Spring2DMPCWeights, action_rate_cost, stage_cost, terminal_cost
from traction_mpc.mpc.safety_filter import SafetyFilterResult


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9a_proper_nmpc"
CONDITIONS_MINIMAL = ["clean"]
CONDITIONS_STRESS = ["noise", "noise_bias"]
METHODS = [
    "baseline_cem",
    "alpha200_omega0",
    "nmpc_alpha_slack",
    "nmpc_alpha_slack_with_cem_fallback",
]
NMPC_METHODS = {"nmpc_alpha_slack", "nmpc_alpha_slack_with_cem_fallback"}


NMPC_EXTRA_FIELDS = [
    "nmpc_solver_success",
    "nmpc_solver_failure",
    "nmpc_fallback_used",
    "nmpc_fallback_mode",
    "nmpc_solve_time_s",
    "nmpc_solver_iterations",
    "nmpc_solver_message",
    "nmpc_cost_total",
    "nmpc_cost_task",
    "nmpc_cost_action",
    "nmpc_cost_action_rate",
    "nmpc_cost_alpha_slack_l1",
    "nmpc_cost_alpha_slack_l2",
    "nmpc_cost_state_violation",
    "nmpc_alpha_slack_mean",
    "nmpc_alpha_slack_max",
    "nmpc_alpha_slack_active_count",
    "nmpc_pred_alpha_max",
    "nmpc_pred_omega_max",
    "nmpc_pred_delta_r_max",
    "nmpc_horizon",
    "nmpc_solver_backend",
]


def _require_casadi() -> str:
    try:
        return str(ca.__version__)
    except Exception as exc:  # pragma: no cover - defensive import guard.
        raise RuntimeError("CasADi is required for Stage 9A multiple-shooting NMPC.") from exc


class CasadiMultipleShootingAlphaSlackNMPC:
    """CasADi multiple-shooting NMPC with explicit alpha slack variables."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any]):
        self.model_params = dict(model_params)
        self.mpc_params = dict(mpc_params)
        self.target_theta = float(mpc_params.get("target_theta", model_params["theta_target"]))
        solver_cfg = dict(mpc_params.get("solver", {}))
        nmpc_cfg = dict(mpc_params.get("stage9a_nmpc", {}))
        self.horizon = int(nmpc_cfg.get("horizon", solver_cfg.get("horizon", 18)))
        self.prediction_dt = float(nmpc_cfg.get("prediction_dt", solver_cfg.get("prediction_dt", model_params["dt"])))
        self.max_iter = int(nmpc_cfg.get("ipopt_max_iter", 80))
        self.tol = float(nmpc_cfg.get("ipopt_tol", 1.0e-4))
        self.acceptable_tol = float(nmpc_cfg.get("ipopt_acceptable_tol", 1.0e-3))
        self.alpha_slack_l1 = float(nmpc_cfg.get("alpha_slack_l1", 6000.0))
        self.alpha_slack_l2 = float(nmpc_cfg.get("alpha_slack_l2", 200.0))
        self.delta_r_penalty = float(nmpc_cfg.get("delta_r_penalty", 2.0e5))
        self.omega_penalty = float(nmpc_cfg.get("omega_penalty", 2.0e5))
        self.action_rate_weight = float(nmpc_cfg.get("action_rate_weight", 0.05))
        self.nominal_cfg = dict(mpc_params.get("nominal_policy", {}))
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.prediction_dt,
        )
        self.weights = Spring2DMPCWeights.from_config(mpc_params.get("weights", {}))
        self.last_x_solution: np.ndarray | None = None
        self.last_u_solution: np.ndarray | None = None
        self.last_s_solution: np.ndarray | None = None
        self.last_action = np.zeros(2, dtype=float)
        self.solve_count = 0
        self.last_diagnostics: dict[str, Any] = {}
        self.solver, self.nlp_info = self._build_solver()

    def reset(self) -> None:
        self.last_x_solution = None
        self.last_u_solution = None
        self.last_s_solution = None
        self.last_action = np.zeros(2, dtype=float)
        self.solve_count = 0
        self.last_diagnostics = {}

    def set_target_theta(self, target_theta: float) -> None:
        self.target_theta = float(target_theta)

    def set_model_params(self, theta_params: dict[str, float]) -> None:
        for name, value in theta_params.items():
            if name not in self.model_params:
                raise KeyError(f"Unknown NMPC model parameter: {name}")
            self.model_params[name] = float(value)

    def act(self, observation: Any) -> np.ndarray:
        state = np.array([observation.theta, observation.omega, observation.r, observation.r_dot], dtype=float)
        solve = self.solve(state, self.last_action)
        if solve["success"]:
            action = np.asarray(solve["U"][0], dtype=float)
        else:
            action = np.asarray(solve["fallback_action"], dtype=float)
        self.last_action = self.constraints.clip_action(action)
        self.solve_count += 1
        self.last_diagnostics = self._diagnostics_from_solve(solve, fallback_used=False, fallback_mode="none")
        return self.last_action.copy()

    def solve(self, state: np.ndarray, prev_action: np.ndarray) -> dict[str, Any]:
        x0, lbx, ubx, lbg, ubg = self._initial_guess_and_bounds(state)
        p = np.array(
            [
                float(state[0]),
                float(state[1]),
                float(state[2]),
                float(state[3]),
                float(self.target_theta),
                float(prev_action[0]),
                float(prev_action[1]),
                float(self.model_params["m"]),
                float(self.model_params["k"]),
                float(self.model_params["b_r"]),
            ],
            dtype=float,
        )
        start = time.perf_counter()
        success = False
        message = "not_solved"
        iterations = 0
        z = np.asarray(x0, dtype=float)
        objective = np.nan
        try:
            sol = self.solver(x0=x0, lbx=lbx, ubx=ubx, lbg=lbg, ubg=ubg, p=p)
            solve_time = time.perf_counter() - start
            stats = self.solver.stats()
            success = bool(stats.get("success", False))
            message = str(stats.get("return_status", ""))
            iterations = int(stats.get("iter_count", 0))
            z = np.asarray(sol["x"], dtype=float).reshape(-1)
            objective = float(sol["f"])
        except RuntimeError as exc:
            solve_time = time.perf_counter() - start
            message = f"RuntimeError: {exc}"
        X, U, S = self._unpack(z)
        U[:, 0] = np.clip(U[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        U[:, 1] = np.clip(U[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        S = np.maximum(S, 0.0)
        if success and np.all(np.isfinite(U)):
            self.last_x_solution = X.copy()
            self.last_u_solution = U.copy()
            self.last_s_solution = S.copy()
        fallback_action = self.constraints.clip_action(U[0] if len(U) else np.zeros(2, dtype=float))
        stats = self._rollout_stats(state, U, S, prev_action)
        return {
            "success": success,
            "solve_time": float(solve_time),
            "iterations": iterations,
            "message": message,
            "objective": objective,
            "X": X,
            "U": U,
            "S": S,
            "fallback_action": fallback_action,
            **stats,
        }

    def diagnostics_with_fallback(self, solve: dict[str, Any], fallback_used: bool, fallback_mode: str) -> dict[str, Any]:
        return self._diagnostics_from_solve(solve, fallback_used=fallback_used, fallback_mode=fallback_mode)

    def get_last_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diagnostics)

    def _build_solver(self) -> tuple[Any, dict[str, int]]:
        n = self.horizon
        X = ca.SX.sym("X", 4, n + 1)
        U = ca.SX.sym("U", 2, n)
        S = ca.SX.sym("S", n)
        P = ca.SX.sym("P", 10)
        x0_param = P[0:4]
        target = P[4]
        prev_action0 = P[5:7]
        dyn_params = {"m": P[7], "k": P[8], "b_r": P[9]}

        g = [X[:, 0] - x0_param]
        cost = 0
        prev_action = prev_action0
        for k in range(n):
            x_next = self._rk4_symbolic(X[:, k], U[:, k], dyn_params)
            g.append(X[:, k + 1] - x_next)
            alpha = (X[1, k + 1] - X[1, k]) / self.prediction_dt
            g.append(alpha - self.constraints.alpha_max - S[k])
            g.append(-alpha - self.constraints.alpha_max - S[k])
            delta_r = X[2, k + 1] - float(self.model_params["L0"])
            omega = X[1, k + 1]
            theta_error = X[0, k + 1] - target
            cost += (
                self.weights.w_theta * theta_error**2
                + self.weights.w_delta_r * delta_r**2
                + self.weights.w_F_tan * U[0, k] ** 2
                + self.weights.w_F_rad * U[1, k] ** 2
                + self.weights.w_alpha * alpha**2
                - self.weights.w_omega_progress * omega
            )
            du = U[:, k] - prev_action
            cost += self.action_rate_weight * ca.dot(du, du)
            cost += self.alpha_slack_l1 * S[k] + self.alpha_slack_l2 * S[k] ** 2
            cost += self.delta_r_penalty * ca.fmax(0, ca.fabs(delta_r) - self.constraints.delta_r_max) ** 2
            cost += self.omega_penalty * ca.fmax(0, ca.fabs(omega) - self.constraints.omega_max) ** 2
            prev_action = U[:, k]
        terminal_theta_error = X[0, n] - target
        terminal_delta_r = X[2, n] - float(self.model_params["L0"])
        cost += self.weights.w_terminal_theta * terminal_theta_error**2 + self.weights.w_delta_r * terminal_delta_r**2

        z = ca.vertcat(ca.reshape(X, -1, 1), ca.reshape(U, -1, 1), S)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": self.max_iter,
            "ipopt.tol": self.tol,
            "ipopt.acceptable_tol": self.acceptable_tol,
        }
        return ca.nlpsol("stage9a_nmpc", "ipopt", nlp, opts), {
            "x_size": 4 * (n + 1),
            "u_size": 2 * n,
            "s_size": n,
        }

    def _rk4_symbolic(self, x: ca.SX, u: ca.SX, dyn_params: dict[str, ca.SX]) -> ca.SX:
        h = self.prediction_dt
        k1 = self._derivatives_symbolic(x, u, dyn_params)
        k2 = self._derivatives_symbolic(x + 0.5 * h * k1, u, dyn_params)
        k3 = self._derivatives_symbolic(x + 0.5 * h * k2, u, dyn_params)
        k4 = self._derivatives_symbolic(x + h * k3, u, dyn_params)
        x_next = x + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        return ca.vertcat(x_next[0], x_next[1], ca.fmax(x_next[2], 1.0e-6), x_next[3])

    def _derivatives_symbolic(self, x: ca.SX, u: ca.SX, dyn_params: dict[str, ca.SX]) -> ca.SX:
        theta, omega, r, r_dot = x[0], x[1], x[2], x[3]
        F_tan, F_rad = u[0], u[1]
        m = dyn_params["m"]
        k = dyn_params["k"]
        b_r = dyn_params["b_r"]
        g = float(self.model_params["g"])
        L0 = float(self.model_params["L0"])
        b_theta = float(self.model_params["b_theta"])
        rho = float(self.model_params["rho"])
        r_eff = ca.fmax(r, 1.0e-6)
        base_mode = str(self.model_params.get("base_mode", "linear_sin"))
        theta_init = float(self.model_params.get("theta_init", 0.0))
        if base_mode == "linear_sin":
            amp = float(self.model_params.get("base_slide_amp", 0.0))
            a = amp * ca.cos(theta)
            ap = -amp * ca.sin(theta)
        elif base_mode == "tanh_sin":
            x_range = float(self.model_params.get("base_x_range", 0.0))
            beta = float(self.model_params.get("base_slide_beta", 1.0))
            z = beta * (ca.sin(theta) - np.sin(theta_init))
            tanh_z = ca.tanh(z)
            sech2 = 1.0 / ca.cosh(z) ** 2
            a = x_range * beta * sech2 * ca.cos(theta)
            ap = x_range * beta * sech2 * (-ca.sin(theta) - 2.0 * beta * tanh_z * ca.cos(theta) ** 2)
        else:
            raise ValueError(f"Unsupported base_mode for Stage 9A NMPC: {base_mode}")

        M11 = m / 3.0
        M12 = 0.5 * m * a * ca.cos(theta)
        M22 = m * (r_eff**2 / 3.0 - a * r_eff * ca.sin(theta) + a**2)
        Q_r = rho * F_rad
        Q_theta = rho * r_eff * F_tan + a * (F_rad * ca.cos(theta) - F_tan * ca.sin(theta))
        h_r = (
            b_r * r_dot
            + k * (r_eff - L0)
            + 0.5 * m * g * ca.sin(theta)
            - (m / 3.0) * r_eff * omega**2
            + 0.5 * m * ap * ca.cos(theta) * omega**2
        )
        h_theta = (
            b_theta * omega
            + 0.5 * m * g * r_eff * ca.cos(theta)
            + (2.0 / 3.0) * m * r_eff * r_dot * omega
            - m * a * ca.sin(theta) * r_dot * omega
            - 0.5 * m * r_eff * a * ca.cos(theta) * omega**2
            - 0.5 * m * r_eff * ap * ca.sin(theta) * omega**2
            + m * a * ap * omega**2
        )
        det = M11 * M22 - M12 * M12
        rhs1 = Q_r - h_r
        rhs2 = Q_theta - h_theta
        r_ddot = (M22 * rhs1 - M12 * rhs2) / det
        omega_dot = (-M12 * rhs1 + M11 * rhs2) / det
        return ca.vertcat(omega, omega_dot, r_dot, r_ddot)

    def _initial_guess_and_bounds(self, state: np.ndarray) -> tuple[np.ndarray, list[float], list[float], list[float], list[float]]:
        n = self.horizon
        if self.last_u_solution is not None and self.last_x_solution is not None and self.last_s_solution is not None:
            U = np.vstack([self.last_u_solution[1:], self.last_u_solution[-1:]])
            S = np.r_[self.last_s_solution[1:], self.last_s_solution[-1]]
        else:
            U = self._heuristic_sequence(state)
            S = np.zeros(n, dtype=float)
        X = self._simulate_guess(state, U)
        z0 = np.r_[X.reshape(-1, order="F"), U.reshape(-1, order="F"), S]

        lbx = [-np.inf] * (4 * (n + 1)) + [-self.constraints.F_tan_max, -self.constraints.F_rad_max] * n + [0.0] * n
        ubx = [np.inf] * (4 * (n + 1)) + [self.constraints.F_tan_max, self.constraints.F_rad_max] * n + [np.inf] * n
        for k in range(n + 1):
            lbx[4 * k + 2] = 1.0e-6
        lbg: list[float] = [0.0] * 4
        ubg: list[float] = [0.0] * 4
        for _ in range(n):
            lbg.extend([0.0] * 4)
            ubg.extend([0.0] * 4)
            lbg.extend([-np.inf, -np.inf])
            ubg.extend([0.0, 0.0])
        return z0, lbx, ubx, lbg, ubg

    def _unpack(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = self.horizon
        x_size = 4 * (n + 1)
        u_size = 2 * n
        X = np.asarray(z[:x_size], dtype=float).reshape((4, n + 1), order="F").T
        U = np.asarray(z[x_size : x_size + u_size], dtype=float).reshape((2, n), order="F").T
        S = np.asarray(z[x_size + u_size : x_size + u_size + n], dtype=float)
        return X, U, S

    def _heuristic_sequence(self, state: np.ndarray) -> np.ndarray:
        theta, omega, r, r_dot = np.asarray(state, dtype=float)
        theta_error = self.target_theta - theta
        kp_theta = float(self.nominal_cfg.get("kp_theta", 7.5))
        kd_omega = float(self.nominal_cfg.get("kd_omega", 1.6))
        radial_kp = float(self.nominal_cfg.get("radial_kp", 60.0))
        radial_kd = float(self.nominal_cfg.get("radial_kd", 8.0))
        taper = np.linspace(1.0, float(self.nominal_cfg.get("terminal_taper", 0.45)), self.horizon)
        F_tan = kp_theta * theta_error - kd_omega * omega
        F_rad = -radial_kp * (r - float(self.model_params["L0"])) - radial_kd * r_dot
        sequence = np.column_stack([F_tan * taper, np.full(self.horizon, F_rad)])
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence

    def _simulate_guess(self, state: np.ndarray, sequence: np.ndarray) -> np.ndarray:
        X = [np.asarray(state, dtype=float).copy()]
        x = X[0].copy()
        slacks = []
        for action in sequence:
            prev = x.copy()
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                x = prev.copy()
            if not np.all(np.isfinite(x)):
                x = prev.copy()
            alpha = (float(x[1]) - float(prev[1])) / self.prediction_dt
            slacks.append(max(0.0, abs(alpha) - self.constraints.alpha_max))
            X.append(x.copy())
        return np.asarray(X, dtype=float)

    def _rollout_stats(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        slacks: np.ndarray,
        prev_action: np.ndarray,
    ) -> dict[str, float]:
        x = np.asarray(state, dtype=float).copy()
        alpha_slacks = np.asarray(slacks, dtype=float)
        pred_alpha_max = 0.0
        pred_omega_max = 0.0
        pred_delta_r_max = 0.0
        cost_task = 0.0
        cost_action = 0.0
        cost_action_rate = 0.0
        cost_alpha_l1 = float(self.alpha_slack_l1 * np.sum(alpha_slacks))
        cost_alpha_l2 = float(self.alpha_slack_l2 * np.sum(alpha_slacks**2))
        cost_state = 0.0
        previous_action = np.asarray(prev_action, dtype=float).copy()
        for k, action in enumerate(sequence):
            prev_x = x.copy()
            action = self.constraints.clip_action(action)
            try:
                x = step_dynamics(x, action, self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                break
            if not np.all(np.isfinite(x)):
                break
            alpha = (float(x[1]) - float(prev_x[1])) / self.prediction_dt
            delta_r = float(x[2] - self.model_params["L0"])
            pred_alpha_max = max(pred_alpha_max, abs(alpha))
            pred_omega_max = max(pred_omega_max, abs(float(x[1])))
            pred_delta_r_max = max(pred_delta_r_max, abs(delta_r))
            cost_task += stage_cost(
                x,
                action,
                prev_x[1],
                self.prediction_dt,
                self.target_theta,
                self.model_params,
                self.weights,
            )
            cost_action += self.weights.w_F_tan * float(action[0] ** 2) + self.weights.w_F_rad * float(action[1] ** 2)
            cost_action_rate += self.action_rate_weight * float(np.dot(action - previous_action, action - previous_action))
            delta_slack = max(0.0, abs(delta_r) - self.constraints.delta_r_max)
            omega_slack = max(0.0, abs(float(x[1])) - self.constraints.omega_max)
            cost_state += self.delta_r_penalty * delta_slack**2 + self.omega_penalty * omega_slack**2
            previous_action = action.copy()
        cost_task += terminal_cost(x, self.target_theta, self.model_params, self.weights)
        return {
            "cost_task": float(cost_task),
            "cost_action": float(cost_action),
            "cost_action_rate": float(cost_action_rate),
            "cost_alpha_slack_l1": float(cost_alpha_l1),
            "cost_alpha_slack_l2": float(cost_alpha_l2),
            "cost_state_violation": float(cost_state),
            "alpha_slack_mean": float(np.mean(alpha_slacks)) if len(alpha_slacks) else np.nan,
            "alpha_slack_max": float(np.max(alpha_slacks)) if len(alpha_slacks) else np.nan,
            "alpha_slack_active_count": int(np.count_nonzero(alpha_slacks > 1.0e-8)),
            "pred_alpha_max": float(pred_alpha_max),
            "pred_omega_max": float(pred_omega_max),
            "pred_delta_r_max": float(pred_delta_r_max),
        }

    def _diagnostics_from_solve(self, solve: dict[str, Any], fallback_used: bool, fallback_mode: str) -> dict[str, Any]:
        return {
            "nmpc_solver_success": bool(solve["success"]),
            "nmpc_solver_failure": not bool(solve["success"]),
            "nmpc_fallback_used": bool(fallback_used),
            "nmpc_fallback_mode": str(fallback_mode),
            "nmpc_solve_time_s": float(solve["solve_time"]),
            "nmpc_solver_iterations": int(solve["iterations"]),
            "nmpc_solver_message": str(solve["message"]),
            "nmpc_cost_total": float(solve["objective"]) if np.isfinite(solve["objective"]) else np.nan,
            "nmpc_cost_task": float(solve["cost_task"]),
            "nmpc_cost_action": float(solve["cost_action"]),
            "nmpc_cost_action_rate": float(solve["cost_action_rate"]),
            "nmpc_cost_alpha_slack_l1": float(solve["cost_alpha_slack_l1"]),
            "nmpc_cost_alpha_slack_l2": float(solve["cost_alpha_slack_l2"]),
            "nmpc_cost_state_violation": float(solve["cost_state_violation"]),
            "nmpc_alpha_slack_mean": float(solve["alpha_slack_mean"]),
            "nmpc_alpha_slack_max": float(solve["alpha_slack_max"]),
            "nmpc_alpha_slack_active_count": int(solve["alpha_slack_active_count"]),
            "nmpc_pred_alpha_max": float(solve["pred_alpha_max"]),
            "nmpc_pred_omega_max": float(solve["pred_omega_max"]),
            "nmpc_pred_delta_r_max": float(solve["pred_delta_r_max"]),
            "nmpc_horizon": int(self.horizon),
            "nmpc_solver_backend": "casadi_ipopt",
            "mpc_solve_count": int(self.solve_count + 1),
        }


class AdaptiveProperNMPC:
    estimated_parameter_names = ("m", "k", "b_r")

    def __init__(self, initial_model_params: dict[str, Any], mpc_params: dict[str, Any], fallback_mode: str):
        self.model_params = dict(initial_model_params)
        self.mpc_params = dict(mpc_params)
        self.current_model_params = dict(initial_model_params)
        self.fallback_mode = str(fallback_mode)
        self.controller = CasadiMultipleShootingAlphaSlackNMPC(self.current_model_params, self.mpc_params)
        self.cem_fallback = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.last_update_diagnostics: dict[str, Any] = {}
        self.last_solve_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.current_model_params = dict(self.model_params)
        self.controller = CasadiMultipleShootingAlphaSlackNMPC(self.current_model_params, self.mpc_params)
        self.controller.reset()
        self.cem_fallback = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.cem_fallback.reset()
        self.last_update_diagnostics = {}
        self.last_solve_diagnostics = {}

    def act(self, observation: Any) -> np.ndarray:
        state = np.array([observation.theta, observation.omega, observation.r, observation.r_dot], dtype=float)
        solve = self.controller.solve(state, self.controller.last_action)
        fallback_used = False
        fallback_label = "none"
        if solve["success"]:
            action = np.asarray(solve["U"][0], dtype=float)
        elif self.fallback_mode == "cem":
            self.cem_fallback.set_target_theta(self.controller.target_theta)
            action = self.cem_fallback.act(observation)
            fallback_used = True
            fallback_label = "baseline_cem"
        else:
            action = solve["fallback_action"]
            fallback_used = True
            fallback_label = "failed_nmpc_candidate"
        self.controller.last_action = self.controller.constraints.clip_action(action)
        self.controller.solve_count += 1
        self.last_solve_diagnostics = self.controller.diagnostics_with_fallback(solve, fallback_used, fallback_label)
        return self.controller.last_action.copy()

    def set_target_theta(self, target_theta: float) -> None:
        self.controller.set_target_theta(float(target_theta))
        self.cem_fallback.set_target_theta(float(target_theta))

    def get_last_solve_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_solve_diagnostics)

    def get_last_update_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_update_diagnostics)

    def get_current_parameter_estimate(self) -> dict[str, float]:
        return {name: float(self.current_model_params[name]) for name in self.estimated_parameter_names}

    def update_parameters(
        self,
        theta_hat: dict[str, float],
        alpha: float,
        bounds: dict[str, list[float] | tuple[float, float]] | None = None,
    ) -> dict[str, float]:
        alpha_clipped = float(np.clip(alpha, 0.0, 1.0))
        new_params = dict(self.current_model_params)
        for name in self.estimated_parameter_names:
            old_value = float(self.current_model_params[name])
            target_value = float(theta_hat[name])
            smoothed = (1.0 - alpha_clipped) * old_value + alpha_clipped * target_value
            if bounds and name in bounds:
                lower, upper = bounds[name]
                smoothed = float(np.clip(smoothed, float(lower), float(upper)))
            new_params[name] = smoothed
        self.current_model_params = new_params
        update = {name: float(new_params[name]) for name in self.estimated_parameter_names}
        self.controller.set_model_params(update)
        self.cem_fallback.update_parameters(theta_hat, alpha=alpha, bounds=bounds)
        self.last_update_diagnostics = {
            "mpc_recreated_on_update": False,
            "solver_recreated_on_update": False,
            "last_action_preserved_on_update": True,
            "last_solution_existed_before_update": self.controller.last_u_solution is not None,
            "last_solution_preserved_on_update": self.controller.last_u_solution is not None,
        }
        return self.get_current_parameter_estimate()


def configure_nmpc_run(base_cfg: dict[str, Any], fallback_mode: str) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = "off"
    solver["gatekeeper_mode"] = "off"
    solver["alpha_constraint_mode"] = "soft"
    solver["action_parameterization_mode"] = "standard"
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    cfg["mpc_params"]["stage9a_nmpc"] = {
        "horizon": int(solver.get("horizon", 18)),
        "prediction_dt": float(solver.get("prediction_dt", cfg["true_params"]["dt"])),
        "ipopt_max_iter": 80,
        "ipopt_tol": 1.0e-4,
        "ipopt_acceptable_tol": 1.0e-3,
        "alpha_slack_l1": 6000.0,
        "alpha_slack_l2": 200.0,
        "delta_r_penalty": 2.0e5,
        "omega_penalty": 2.0e5,
        "action_rate_weight": 0.05,
        "fallback_mode": fallback_mode,
    }
    return cfg


def _add_nmpc_fields(row: dict[str, Any], solve_diag: dict[str, Any] | None = None) -> dict[str, Any]:
    diag = solve_diag or {}
    enriched = dict(row)
    for key in NMPC_EXTRA_FIELDS:
        if key in {"nmpc_solver_success", "nmpc_solver_failure", "nmpc_fallback_used"}:
            enriched[key] = bool(diag.get(key, False))
        elif key in {"nmpc_fallback_mode", "nmpc_solver_message", "nmpc_solver_backend"}:
            enriched[key] = str(diag.get(key, ""))
        elif key in {"nmpc_solver_iterations", "nmpc_alpha_slack_active_count", "nmpc_horizon"}:
            enriched[key] = int(diag.get(key, 0))
        else:
            enriched[key] = float(diag.get(key, np.nan))
    enriched["nmpc_solve_count"] = int(diag.get("mpc_solve_count", 0))
    return enriched


def run_nmpc_condition(
    method: str,
    condition_name: str,
    condition_cfg: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    adaptive_cfg = cfg.get("adaptive", {})
    alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 0.5))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    target_theta = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    coupling_cfg = dict(cfg.get("coupling_ablation", {}))
    coupling_name = str(coupling_cfg.get("name", "stage9a_nmpc"))
    mpc_state_input = str(coupling_cfg.get("mpc_state_input", "filtered")).lower()
    identifier_input = str(coupling_cfg.get("identifier_input", "filtered")).lower()
    identifier_mode = str(coupling_cfg.get("identifier_mode", "adaptive")).lower()
    estimator_model_params_source = str(coupling_cfg.get("estimator_model_params_source", "adaptive")).lower()
    mpc_model_params_source = str(coupling_cfg.get("mpc_model_params_source", "adaptive")).lower()
    fallback_mode = str(cfg["mpc_params"].get("stage9a_nmpc", {}).get("fallback_mode", "candidate"))

    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(
        true_params,
        condition_cfg.get("observation_noise", {}),
        seed=int(condition_cfg.get("seed", 0)),
    )
    obs_meas = wrapper.observe(obs_true)
    controller = AdaptiveProperNMPC(model_params, cfg["mpc_params"], fallback_mode=fallback_mode)
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()
    filter_cfg = dict(cfg.get("observation_filter", {"type": "ukf_bias", "identifier_input": "filtered"}))
    filter_cfg["condition_name"] = condition_name
    filter_type = str(filter_cfg.get("type", "ukf_bias")).lower()
    obs_filter = make_observation_filter(filter_cfg)
    initial_filter_model_params = (
        model_params
        if estimator_model_params_source == "initial"
        else current_prediction_params(model_params, controller)
    )
    filt_state = obs_filter.reset(obs_meas, true_state=observation_to_state(obs_true), model_params=initial_filter_model_params)
    obs_filt = observation_from_state(obs_meas, filt_state, true_params)
    obs_mpc = select_observation_by_source(mpc_state_input, obs_meas, obs_filt, obs_true)
    if obs_mpc is None:
        raise ValueError("mpc_state_input cannot be none.")

    parameter_update_count = 0
    last_theta_hat_vec = parameter_vector(identifier.get_parameter_estimate())

    def coupling_diagnostics(result: Any, parameter_step_norm: float) -> dict[str, Any]:
        return {
            "filter_type": filter_type,
            "coupling_case": coupling_name,
            "mpc_state_input_source": mpc_state_input,
            "identifier_mode": identifier_mode,
            "identifier_input_source": identifier_input,
            "estimator_model_params_source": estimator_model_params_source,
            "mpc_model_params_source": mpc_model_params_source,
            "parameter_update_count": parameter_update_count,
            "parameter_step_norm": parameter_step_norm,
            "parameter_bound_hit": parameter_bound_hit(result.theta_hat, parameter_bounds),
        }

    rows: list[dict[str, Any]] = []
    initial_result = initial_identifier_result(identifier)
    initial_row = append_adaptive_fields(
        env.get_history()[-1],
        observation_to_state(obs_meas),
        filt_state,
        initial_result,
        controller,
        parameter_update_flag=False,
        target_theta=target_theta,
        alpha_step=0.0,
        filter_diagnostics=obs_filter.get_diagnostics(),
        coupling_diagnostics=coupling_diagnostics(initial_result, 0.0),
        safety_diagnostics=SafetyFilterResult.disabled(np.zeros(2, dtype=float)).as_diagnostics(),
        theta_cmd=target_theta,
        progress_governor_mode="off",
    )
    rows.append(_add_nmpc_fields(initial_row))
    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        controller.set_target_theta(target_theta)
        action_mpc = controller.act(obs_mpc)
        solve_diagnostics = controller.get_last_solve_diagnostics()
        for _ in range(hold_steps):
            prev_obs_meas = obs_meas
            prev_obs_filt = obs_filt
            prev_obs_true = obs_true
            prev_history_row = env.get_history()[-1]
            action_exec = np.asarray(action_mpc, dtype=float)
            obs_true = env.step(action_exec)
            obs_meas = wrapper.observe(obs_true)
            filter_model_params = (
                model_params
                if estimator_model_params_source == "initial"
                else current_prediction_params(model_params, controller)
            )
            obs_filter.predict(action_exec, float(true_params["dt"]), model_params=filter_model_params)
            filt_state = obs_filter.update(
                obs_meas,
                float(true_params["dt"]),
                action=action_exec,
                true_state=observation_to_state(obs_true),
                model_params=filter_model_params,
            )
            obs_filt = observation_from_state(obs_meas, filt_state, true_params)
            obs_mpc = select_observation_by_source(mpc_state_input, obs_meas, obs_filt, obs_true)
            if obs_mpc is None:
                raise ValueError("mpc_state_input cannot be none.")
            id_prev = select_observation_by_source(identifier_input, prev_obs_meas, prev_obs_filt, prev_obs_true)
            id_next = select_observation_by_source(identifier_input, obs_meas, obs_filt, obs_true)
            if identifier_mode == "frozen" or identifier_input == "none":
                result = SimpleNamespace(
                    theta_hat=identifier.get_parameter_estimate(),
                    prediction_error=np.nan,
                    updated=False,
                    num_samples=len(identifier.transitions),
                    success=True,
                )
            elif identifier_mode == "adaptive":
                result = identifier.add_transition(observation_to_state(id_prev), action_exec, observation_to_state(id_next))
            else:
                raise ValueError(f"Unknown identifier_mode: {identifier_mode}")
            steps += 1
            parameter_update_flag = False
            update_diagnostics: dict[str, Any] = {}
            current_theta_hat_vec = parameter_vector(result.theta_hat)
            parameter_step_norm = float(np.linalg.norm(current_theta_hat_vec - last_theta_hat_vec))
            last_theta_hat_vec = current_theta_hat_vec
            if (
                result.updated
                and steps >= warmup_steps
                and identifier_mode == "adaptive"
                and mpc_model_params_source == "adaptive"
            ):
                controller.update_parameters(result.theta_hat, alpha=alpha, bounds=parameter_bounds)
                update_diagnostics = controller.get_last_update_diagnostics()
                parameter_update_flag = True
                parameter_update_count += 1
            history_row = env.get_history()[-1]
            alpha_step = (float(history_row["omega"]) - float(prev_history_row["omega"])) / float(true_params["dt"])
            safety_diagnostics = SafetyFilterResult.disabled(action_exec).as_diagnostics()
            safety_diagnostics.update({"true_safe_alpha": alpha_step})
            enriched_row = append_adaptive_fields(
                history_row,
                observation_to_state(obs_meas),
                filt_state,
                result,
                controller,
                parameter_update_flag=parameter_update_flag,
                target_theta=target_theta,
                alpha_step=alpha_step,
                solve_diagnostics=solve_diagnostics,
                update_diagnostics=update_diagnostics,
                filter_diagnostics=obs_filter.get_diagnostics(),
                coupling_diagnostics=coupling_diagnostics(result, parameter_step_norm),
                safety_diagnostics=safety_diagnostics,
                theta_cmd=target_theta,
                progress_governor_mode="off",
            )
            rows.append(_add_nmpc_fields(enriched_row, solve_diagnostics))
            if env.is_done() or steps >= max_steps:
                break
    return rows


def summarize_rows(method: str, condition: str, rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    omega_sev = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(actions, axis=1)
    action_diff = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.array([])
    decisions = _decision_rows(rows, "nmpc_solve_count") if method in NMPC_METHODS else []
    solve_times = _series(decisions, "nmpc_solve_time_s") if decisions else np.array([])
    slack_mean = _series(decisions, "nmpc_alpha_slack_mean") if decisions else np.array([])
    slack_max = _series(decisions, "nmpc_alpha_slack_max") if decisions else np.array([])
    slack_active = _series(decisions, "nmpc_alpha_slack_active_count") if decisions else np.array([])
    return {
        "method": method,
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "solver_success_count": int(sum(bool(row.get("nmpc_solver_success", False)) for row in decisions)),
        "solver_failure_count": int(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions)),
        "solver_failure_rate": float(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "fallback_count": int(sum(bool(row.get("nmpc_fallback_used", False)) for row in decisions)),
        "fallback_rate": float(sum(bool(row.get("nmpc_fallback_used", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "mean_solve_time_s": _finite_mean(solve_times),
        "max_solve_time_s": _finite_max(solve_times),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_clipped_max_excluding_top1": _clipped_max_excluding_one(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "alpha_integrated_violation": float(np.sum(alpha_sev) * dt),
        "alpha_slack_mean": _finite_mean(slack_mean),
        "alpha_slack_max": _finite_max(slack_max),
        "alpha_slack_active_count": int(np.nansum(slack_active)) if len(slack_active) else 0,
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_p95_severity": _finite_percentile(omega_sev, 95),
        "omega_max_severity": _finite_max(omega_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "force_violation_count": int(np.count_nonzero((F_tan_sev + F_rad_sev) > 0.0)),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_diff),
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "solver_success_count",
    "solver_failure_count",
    "solver_failure_rate",
    "fallback_count",
    "fallback_rate",
    "mean_solve_time_s",
    "max_solve_time_s",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_p95_severity",
    "alpha_p99_severity",
    "alpha_max_severity",
    "alpha_clipped_max_excluding_top1",
    "alpha_violation_duration_s",
    "alpha_integrated_violation",
    "alpha_slack_mean",
    "alpha_slack_max",
    "alpha_slack_active_count",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_p95_severity",
    "omega_max_severity",
    "delta_r_violation_count",
    "delta_r_mean_severity",
    "delta_r_max_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "force_violation_count",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def _aggregate(summary_rows: list[dict[str, Any]], methods: list[str], conditions: list[str]) -> list[dict[str, Any]]:
    rows = []
    for method in methods:
        method_rows = [row for row in summary_rows if row["method"] == method]
        rows.append(
            {
                "method": method,
                "target_success_count": int(sum(_as_bool(row["target_reached"]) for row in method_rows)),
                "num_conditions": len(method_rows),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "solver_failure_rate_avg": _finite_mean(np.array([float(row["solver_failure_rate"]) for row in method_rows])),
                "fallback_rate_avg": _finite_mean(np.array([float(row["fallback_rate"]) for row in method_rows])),
                "solve_time_avg": _finite_mean(np.array([float(row["mean_solve_time_s"]) for row in method_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_p99_avg": _finite_mean(np.array([float(row["alpha_p99_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "alpha_duration_avg": _finite_mean(np.array([float(row["alpha_violation_duration_s"]) for row in method_rows])),
                "alpha_integral_avg": _finite_mean(np.array([float(row["alpha_integrated_violation"]) for row in method_rows])),
                "alpha_slack_mean_avg": _finite_mean(np.array([float(row["alpha_slack_mean"]) for row in method_rows])),
                "alpha_slack_max_avg": _finite_mean(np.array([float(row["alpha_slack_max"]) for row in method_rows])),
                "alpha_slack_active_total": int(sum(int(row["alpha_slack_active_count"]) for row in method_rows)),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "delta_r_count_total": int(sum(int(row["delta_r_violation_count"]) for row in method_rows)),
                "force_count_total": int(sum(int(row["force_violation_count"]) for row in method_rows)),
                "runtime_avg": _finite_mean(np.array([float(row["runtime_s"]) for row in method_rows])),
            }
        )
    return rows


def save_plots(summary_rows: list[dict[str, Any]], all_rows: dict[tuple[str, str], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    keys = list(all_rows.keys())
    conditions = sorted({condition for _, condition in keys})
    methods = [method for method in METHODS if any((method, condition) in all_rows for condition in conditions)]
    colors = {
        "baseline_cem": "tab:blue",
        "alpha200_omega0": "tab:orange",
        "nmpc_alpha_slack": "tab:green",
        "nmpc_alpha_slack_with_cem_fallback": "tab:red",
    }
    for condition in conditions:
        for key, ylabel, filename in [
            ("theta", "theta [deg]", "theta_trajectories"),
            ("alpha_step", "alpha [rad/s^2]", "alpha_trajectories"),
            ("omega", "omega [rad/s]", "omega_trajectories"),
            ("nmpc_alpha_slack_max", "alpha slack", "alpha_slack_trajectory"),
        ]:
            fig, ax = plt.subplots(figsize=(11, 5))
            for method in methods:
                if (method, condition) not in all_rows:
                    continue
                rows = all_rows[(method, condition)]
                y = np.degrees(_series(rows, key)) if key == "theta" else _series(rows, key)
                ax.plot(_series(rows, "t"), y, label=method, color=colors[method])
            if key == "theta":
                target = np.degrees(float(all_rows[("baseline_cem", condition)][-1]["theta_target_final"]))
                ax.axhline(target, color="black", linestyle=":", label="theta_target")
            if key == "alpha_step":
                ax.axhline(3.0, color="black", linestyle=":", label="alpha threshold")
                ax.axhline(-3.0, color="black", linestyle=":")
            ax.set_title(f"{condition}: {filename.replace('_', ' ')}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}.png", dpi=150)
            plt.close(fig)
        fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        for method in methods:
            if (method, condition) not in all_rows:
                continue
            rows = all_rows[(method, condition)]
            t = _series(rows, "t")
            axes[0].plot(t, _series(rows, "F_tan"), label=method, color=colors[method])
            axes[1].plot(t, _series(rows, "F_rad"), label=method, color=colors[method])
        axes[0].set_ylabel("F_tan")
        axes[1].set_ylabel("F_rad")
        axes[1].set_xlabel("time [s]")
        for ax in axes:
            ax.grid(True, alpha=0.25)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"{condition}: action trajectories")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
        fig.savefig(fig_dir / f"{condition}_action_trajectories.png", dpi=150)
        plt.close(fig)

    aggregate = _aggregate(summary_rows, methods, conditions)
    x = np.arange(len(methods))
    width = 0.18
    fig, ax = plt.subplots(figsize=(10, 5))
    for idx, (metric, label) in enumerate(
        [
            ("alpha_p95_avg", "p95"),
            ("alpha_p99_avg", "p99"),
            ("alpha_max_avg", "max"),
            ("alpha_slack_max_avg", "slack max"),
        ]
    ):
        ax.bar(x + (idx - 1.5) * width, [float(row[metric]) for row in aggregate], width=width, label=label)
    ax.set_ylabel("alpha severity / slack")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=20, ha="right")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "alpha_p95_p99_max_slack.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].bar(x, [float(row["solve_time_avg"]) for row in aggregate])
    axes[1].bar(x, [float(row["solver_failure_rate_avg"]) for row in aggregate])
    axes[0].set_ylabel("mean solve time [s]")
    axes[1].set_ylabel("failure rate")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(methods, rotation=20, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage 9A: solve time and solver failures")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "solve_time_solver_failures.png", dpi=150)
    plt.close(fig)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str], casadi_version: str, stress_skipped_reason: str | None) -> None:
    conditions = sorted({row["condition"] for row in summary_rows})
    methods = [method for method in METHODS if any(row["method"] == method for row in summary_rows)]
    aggregate = {row["method"]: row for row in _aggregate(summary_rows, methods, conditions)}
    baseline = aggregate["baseline_cem"]
    nmpc = aggregate.get("nmpc_alpha_slack")
    nmpc_fb = aggregate.get("nmpc_alpha_slack_with_cem_fallback")
    clean_rows = {row["method"]: row for row in summary_rows if row["condition"] == "clean"}
    clean_fb = clean_rows.get("nmpc_alpha_slack_with_cem_fallback")
    clean_reliable = clean_fb is not None and float(clean_fb["solver_failure_rate"]) < 0.3
    clean_target = clean_fb is not None and _as_bool(clean_fb["target_reached"])
    fb_prevents = (
        nmpc is not None
        and nmpc_fb is not None
        and float(nmpc_fb["alpha_max_avg"]) < float(nmpc["alpha_max_avg"])
        and float(nmpc_fb["omega_max_avg"]) <= float(nmpc["omega_max_avg"])
    )
    nmpc_preserves = nmpc_fb is not None and int(nmpc_fb["target_success_count"]) == int(nmpc_fb["num_conditions"])
    nmpc_reduces_alpha = (
        nmpc_fb is not None
        and float(nmpc_fb["alpha_p95_avg"]) < float(baseline["alpha_p95_avg"])
        and float(nmpc_fb["alpha_p99_avg"]) < float(baseline["alpha_p99_avg"])
        and float(nmpc_fb["alpha_max_avg"]) < float(baseline["alpha_max_avg"])
    )
    nmpc_avoids_other = (
        nmpc_fb is not None
        and float(nmpc_fb["omega_p95_avg"]) <= float(baseline["omega_p95_avg"])
        and int(nmpc_fb["delta_r_count_total"]) <= int(baseline["delta_r_count_total"])
        and int(nmpc_fb["force_count_total"]) <= int(baseline["force_count_total"])
    )
    solve_time_ok = (
        nmpc_fb is not None
        and np.isfinite(float(nmpc_fb["solve_time_avg"]))
        and float(nmpc_fb["solve_time_avg"]) < 0.25
        and np.isfinite(float(nmpc_fb["solver_failure_rate_avg"]))
        and float(nmpc_fb["solver_failure_rate_avg"]) < 0.2
    )
    next_step = (
        "NMPC refinement and stress validation."
        if nmpc_preserves and nmpc_reduces_alpha and nmpc_avoids_other and clean_reliable
        else "revise task/alpha definition or NMPC formulation before linked rods."
    )
    lines = [
        "# Stage 9A Proper Multiple-Shooting NMPC Report",
        "",
        "## Scope",
        "- Diagnosis only: tested CasADi multiple-shooting NMPC with explicit state variables and explicit alpha slack variables.",
        f"- Solver availability: CasADi {casadi_version} available; acados_template unavailable in this environment.",
        "- Alpha is a high-priority soft path constraint through nonnegative slack; force bounds are hard optimizer bounds.",
        "- Delta_r and omega are hard-ish through strong path penalties.",
        "- Dynamics, UKF-bias, filtered Windowed NLS identifier, baseline CEM, Stage 7/8 methods, and default configs were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | target | T_reach | fail rate | fallback rate | solve time | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack active | omega p95 | omega max | delta_r count | force count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in _aggregate(summary_rows, methods, conditions):
        denom = int(row["num_conditions"])
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{denom} | {_fmt(row['T_reach_avg'])} | "
            f"{_fmt(row['solver_failure_rate_avg'])} | {_fmt(row['fallback_rate_avg'])} | {_fmt(row['solve_time_avg'])} | "
            f"{_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_p99_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['alpha_duration_avg'])} | {_fmt(row['alpha_integral_avg'])} | {_fmt(row['alpha_slack_mean_avg'])} | "
            f"{_fmt(row['alpha_slack_max_avg'])} | {row['alpha_slack_active_total']} | {_fmt(row['omega_p95_avg'])} | "
            f"{_fmt(row['omega_max_avg'])} | {row['delta_r_count_total']} | {row['force_count_total']} |"
        )
    if stress_skipped_reason:
        lines.extend(["", "## Stop Condition", f"- Stress conditions were skipped: {stress_skipped_reason}"])
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does proper multiple-shooting NMPC solve reliably on clean?",
            f"- {'Yes' if clean_reliable else 'No'}: clean fallback NMPC failure rate={_fmt(clean_fb['solver_failure_rate']) if clean_fb else 'nan'}.",
            "",
            "2. Does fallback prevent catastrophic closed-loop failure?",
            f"- {'Yes/mixed' if fb_prevents else 'No'}: CEM fallback kept the executed trajectory at baseline-like risk when IPOPT failed. Fallback alpha/omega max={_fmt(nmpc_fb['alpha_max_avg']) if nmpc_fb else 'nan'}/{_fmt(nmpc_fb['omega_max_avg']) if nmpc_fb else 'nan'} vs non-fallback failed-candidate execution={_fmt(nmpc['alpha_max_avg']) if nmpc else 'nan'}/{_fmt(nmpc['omega_max_avg']) if nmpc else 'nan'}. This does not mean NMPC solved successfully.",
            "",
            "3. Does NMPC preserve target reaching?",
            f"- {'Yes with fallback, not as a reliable NMPC solve' if nmpc_preserves else 'No'}: fallback NMPC target={nmpc_fb['target_success_count'] if nmpc_fb else 'nan'}/{nmpc_fb['num_conditions'] if nmpc_fb else 'nan'}, but solver success count on clean was {clean_fb['solver_success_count'] if clean_fb else 'nan'}.",
            "",
            "4. Does explicit alpha slack reduce alpha p95/p99/max vs baseline CEM?",
            f"- {'Yes' if nmpc_reduces_alpha else 'No/mixed'}: fallback NMPC alpha p95/p99/max={_fmt(nmpc_fb['alpha_p95_avg']) if nmpc_fb else 'nan'}/{_fmt(nmpc_fb['alpha_p99_avg']) if nmpc_fb else 'nan'}/{_fmt(nmpc_fb['alpha_max_avg']) if nmpc_fb else 'nan'}; baseline={_fmt(baseline['alpha_p95_avg'])}/{_fmt(baseline['alpha_p99_avg'])}/{_fmt(baseline['alpha_max_avg'])}.",
            "",
            "5. Does it avoid worsening omega/delta_r/force violations?",
            f"- {'Yes' if nmpc_avoids_other else 'No/mixed'}: fallback NMPC omega p95/max={_fmt(nmpc_fb['omega_p95_avg']) if nmpc_fb else 'nan'}/{_fmt(nmpc_fb['omega_max_avg']) if nmpc_fb else 'nan'}, delta_r count={nmpc_fb['delta_r_count_total'] if nmpc_fb else 'nan'}, force count={nmpc_fb['force_count_total'] if nmpc_fb else 'nan'}.",
            "",
            "6. How often and how strongly is alpha slack used?",
            f"- Slack active total={nmpc_fb['alpha_slack_active_total'] if nmpc_fb else 'nan'}; mean/max slack={_fmt(nmpc_fb['alpha_slack_mean_avg']) if nmpc_fb else 'nan'}/{_fmt(nmpc_fb['alpha_slack_max_avg']) if nmpc_fb else 'nan'}.",
            "",
            "7. Is solve time acceptable for this small system?",
            f"- {'Yes for this diagnostic' if solve_time_ok else 'No/marginal'}: mean solve time={_fmt(nmpc_fb['solve_time_avg']) if nmpc_fb else 'nan'} s, failure rate={_fmt(nmpc_fb['solver_failure_rate_avg']) if nmpc_fb else 'nan'}.",
            "",
            "8. Is NMPC worth developing further, or should we revise task/alpha definition?",
            f"- Recommended next step: {next_step}",
            "",
            "## Notes",
            "- Failures and mixed results are retained directly. No post-result tuning was applied.",
        ]
    )
    (output_root / "stage9a_report.md").write_text("\n".join(lines) + "\n")


def _clean_reasonable(summary_rows: list[dict[str, Any]]) -> tuple[bool, str | None]:
    row = next(row for row in summary_rows if row["method"] == "nmpc_alpha_slack_with_cem_fallback" and row["condition"] == "clean")
    if float(row["solver_failure_rate"]) >= 0.3:
        return False, f"clean fallback NMPC solver failure rate was {row['solver_failure_rate']:.3g}"
    if not bool(row["target_reached"]):
        return False, "clean fallback NMPC did not reach target"
    return True, None


def run(output_root: Path, config_path: Path) -> None:
    casadi_version = _require_casadi()
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]

    conditions_to_run = list(CONDITIONS_MINIMAL)
    stress_skipped_reason: str | None = None
    completed_clean = False
    while conditions_to_run:
        condition = conditions_to_run.pop(0)
        for method in METHODS:
            print(f"[stage9a] running {method} / {condition}", flush=True)
            if method in {"baseline_cem", "alpha200_omega0"}:
                cfg = configure_cem_run(base_cfg, method)
                start = time.perf_counter()
                rows = run_condition(condition, base_cfg["conditions"][condition], cfg)
            else:
                fallback_mode = "cem" if method.endswith("with_cem_fallback") else "candidate"
                cfg = configure_nmpc_run(base_cfg, fallback_mode=fallback_mode)
                start = time.perf_counter()
                rows = run_nmpc_condition(method, condition, base_cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            summary = summarize_rows(method, condition, rows, cfg, runtime_s)
            summary_rows.append(summary)
            print(
                "[stage9a] "
                f"{method}/{condition}: target={summary['target_reached']}, "
                f"T={summary['T_reach']:.4g}, alpha_p95={summary['alpha_p95_severity']:.4g}, "
                f"alpha_max={summary['alpha_max_severity']:.4g}, fail_rate={summary['solver_failure_rate']:.4g}, "
                f"fallback={summary['fallback_rate']:.4g}, solve={summary['mean_solve_time_s']:.4g}s, "
                f"runtime={runtime_s:.2f}s",
                flush=True,
            )
        if condition == "clean" and not completed_clean:
            completed_clean = True
            clean_ok, reason = _clean_reasonable(summary_rows)
            if clean_ok:
                conditions_to_run.extend(CONDITIONS_STRESS)
            else:
                stress_skipped_reason = reason
                conditions_to_run.clear()

    save_summary(summary_rows, output_root / "stage9a_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands, casadi_version, stress_skipped_reason)
    print(f"[stage9a] summary: {output_root / 'stage9a_summary.csv'}", flush=True)
    print(f"[stage9a] report : {output_root / 'stage9a_report.md'}", flush=True)
    print(f"[stage9a] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
