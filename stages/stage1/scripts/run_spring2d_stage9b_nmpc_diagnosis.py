"""Stage 9B NMPC feasibility and scaling diagnosis for Spring2D."""

from __future__ import annotations

import argparse
import copy
import csv
import os
import re
import sys
import time
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
from traction_mpc.mpc.cost import Spring2DMPCWeights, stage_cost, terminal_cost
from traction_mpc.mpc.safety_filter import SafetyFilterResult


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9b_nmpc_diagnosis"
CONDITION = "clean"
VARIANTS: list[dict[str, Any]] = [
    {"name": "baseline_cem", "type": "baseline"},
    {"name": "nmpc_no_alpha_basic", "horizon": 18, "alpha": False, "warmstart": "shift", "scaled": False},
    {"name": "nmpc_no_alpha_short_N5", "horizon": 5, "alpha": False, "warmstart": "shift", "scaled": False},
    {"name": "nmpc_no_alpha_short_N8", "horizon": 8, "alpha": False, "warmstart": "shift", "scaled": False},
    {"name": "nmpc_no_alpha_short_N10", "horizon": 10, "alpha": False, "warmstart": "shift", "scaled": False},
    {"name": "nmpc_cem_warmstart", "horizon": 18, "alpha": False, "warmstart": "cem", "scaled": False},
    {"name": "nmpc_alpha_slack_rho1", "horizon": 18, "alpha": True, "rho_l1": 1.0, "warmstart": "no_alpha", "scaled": False},
    {"name": "nmpc_alpha_slack_rho10", "horizon": 18, "alpha": True, "rho_l1": 10.0, "warmstart": "no_alpha", "scaled": False},
    {"name": "nmpc_alpha_slack_rho100", "horizon": 18, "alpha": True, "rho_l1": 100.0, "warmstart": "no_alpha", "scaled": False},
    {"name": "nmpc_alpha_slack_rho1000", "horizon": 18, "alpha": True, "rho_l1": 1000.0, "warmstart": "no_alpha", "scaled": False},
    {"name": "nmpc_scaled_variables", "horizon": 18, "alpha": True, "rho_l1": 100.0, "warmstart": "no_alpha", "scaled": True},
]
NMPC_VARIANTS = [v["name"] for v in VARIANTS if v.get("type") != "baseline"]


DIAG_FIELDS = [
    "nmpc_solver_success",
    "nmpc_solver_failure",
    "nmpc_fallback_would_be_used",
    "nmpc_solve_time_s",
    "nmpc_solver_iterations",
    "nmpc_solver_status",
    "nmpc_failure_reason",
    "nmpc_objective",
    "nmpc_dynamics_residual_max",
    "nmpc_dynamics_residual_mean",
    "nmpc_constraint_violation_max",
    "nmpc_constraint_violation_mean",
    "nmpc_alpha_slack_mean",
    "nmpc_alpha_slack_max",
    "nmpc_alpha_slack_active_count",
    "nmpc_first_F_tan",
    "nmpc_first_F_rad",
    "nmpc_first_action_diff_vs_cem",
    "nmpc_horizon",
    "nmpc_alpha_enabled",
    "nmpc_scaled_variables",
    "nmpc_warmstart_mode",
    "nmpc_alpha_rho_l1",
    "nmpc_alpha_rho_l2",
    "nmpc_x_scale_theta",
    "nmpc_x_scale_omega",
    "nmpc_x_scale_r",
    "nmpc_x_scale_r_dot",
    "nmpc_u_scale_F_tan",
    "nmpc_u_scale_F_rad",
    "nmpc_s_scale_alpha",
]


class DiagnosticCasadiNMPC:
    """Flexible multiple-shooting NLP for Stage 9B diagnosis."""

    _counter = 0

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any], variant: dict[str, Any]):
        self.model_params = dict(model_params)
        self.mpc_params = dict(mpc_params)
        self.variant = dict(variant)
        self.name = str(variant["name"])
        self.horizon = int(variant.get("horizon", mpc_params.get("solver", {}).get("horizon", 18)))
        self.prediction_dt = float(mpc_params.get("solver", {}).get("prediction_dt", model_params["dt"]))
        self.alpha_enabled = bool(variant.get("alpha", False))
        self.scaled = bool(variant.get("scaled", False))
        self.warmstart = str(variant.get("warmstart", "shift"))
        self.alpha_rho_l1 = float(variant.get("rho_l1", 0.0))
        self.alpha_rho_l2 = float(variant.get("rho_l2", 1.0e-2))
        self.target_theta = float(mpc_params.get("target_theta", model_params["theta_target"]))
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.prediction_dt,
        )
        self.weights = Spring2DMPCWeights.from_config(mpc_params.get("weights", {}))
        self.nominal_cfg = dict(mpc_params.get("nominal_policy", {}))
        self.x_scale = np.array([np.pi, 2.0, max(float(model_params["L0"]), 1.0), 2.0], dtype=float)
        self.u_scale = np.array([self.constraints.F_tan_max, self.constraints.F_rad_max], dtype=float)
        self.s_scale = float(max(self.constraints.alpha_max, 1.0))
        self.last_X: np.ndarray | None = None
        self.last_U: np.ndarray | None = None
        self.last_S: np.ndarray | None = None
        self.last_action = np.zeros(2, dtype=float)
        self.solve_count = 0
        self.solver = self._build_solver()

    def set_target_theta(self, target_theta: float) -> None:
        self.target_theta = float(target_theta)

    def set_model_params(self, theta_params: dict[str, float]) -> None:
        for name, value in theta_params.items():
            if name not in self.model_params:
                raise KeyError(f"Unknown NMPC model parameter: {name}")
            self.model_params[name] = float(value)

    def solve(
        self,
        state: np.ndarray,
        prev_action: np.ndarray,
        cem_sequence: np.ndarray | None = None,
        initial_override: dict[str, np.ndarray] | None = None,
    ) -> dict[str, Any]:
        z0, lbx, ubx, lbg, ubg = self._initial_guess_and_bounds(state, cem_sequence, initial_override)
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
        status = "not_solved"
        iterations = 0
        objective = np.nan
        z = np.asarray(z0, dtype=float)
        try:
            sol = self.solver(x0=z0, lbx=lbx, ubx=ubx, lbg=lbg, ubg=ubg, p=p)
            solve_time = time.perf_counter() - start
            stats = self.solver.stats()
            success = bool(stats.get("success", False))
            status = str(stats.get("return_status", "status_unavailable"))
            iterations = int(stats.get("iter_count", 0))
            objective = float(sol["f"])
            z = np.asarray(sol["x"], dtype=float).reshape(-1)
        except RuntimeError as exc:
            solve_time = time.perf_counter() - start
            status = f"RuntimeError: {exc}"
        X, U, S = self._unpack(z)
        U[:, 0] = np.clip(U[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        U[:, 1] = np.clip(U[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        S = np.maximum(S, 0.0)
        if success:
            self.last_X = X.copy()
            self.last_U = U.copy()
            self.last_S = S.copy()
        first = self.constraints.clip_action(U[0] if len(U) else np.zeros(2, dtype=float))
        self.last_action = first.copy()
        self.solve_count += 1
        diagnostics = self._diagnostics(X, U, S, solve_time, success, status, iterations, objective)
        diagnostics["fallback_would_be_used"] = not success
        diagnostics["first_action"] = first
        diagnostics["X"] = X
        diagnostics["U"] = U
        diagnostics["S"] = S
        return diagnostics

    def _build_solver(self) -> Any:
        n = self.horizon
        x_dim = 4
        u_dim = 2
        Xv = ca.SX.sym("X", x_dim, n + 1)
        Uv = ca.SX.sym("U", u_dim, n)
        Sv = ca.SX.sym("S", n) if self.alpha_enabled else ca.SX.zeros(0)
        P = ca.SX.sym("P", 10)
        x_scale = ca.DM(self.x_scale)
        u_scale = ca.DM(self.u_scale)
        s_scale = self.s_scale

        X = ca.diag(x_scale) @ Xv if self.scaled else Xv
        U = ca.diag(u_scale) @ Uv if self.scaled else Uv
        S = s_scale * Sv if (self.scaled and self.alpha_enabled) else Sv

        x0_param = P[0:4]
        target = P[4]
        prev_action = P[5:7]
        dyn_params = {"m": P[7], "k": P[8], "b_r": P[9]}
        g = [X[:, 0] - x0_param]
        cost = 0
        action_prev = prev_action
        for k in range(n):
            x_next = self._rk4_symbolic(X[:, k], U[:, k], dyn_params)
            g.append(X[:, k + 1] - x_next)
            alpha = (X[1, k + 1] - X[1, k]) / self.prediction_dt
            delta_r = X[2, k + 1] - float(self.model_params["L0"])
            theta_error = X[0, k + 1] - target
            cost += (
                self.weights.w_theta * theta_error**2
                + self.weights.w_delta_r * delta_r**2
                + self.weights.w_F_tan * U[0, k] ** 2
                + self.weights.w_F_rad * U[1, k] ** 2
            )
            du = U[:, k] - action_prev
            cost += 1.0e-3 * ca.dot(du, du)
            if self.alpha_enabled:
                g.append(alpha - self.constraints.alpha_max - S[k])
                g.append(-alpha - self.constraints.alpha_max - S[k])
                cost += self.alpha_rho_l1 * S[k] + self.alpha_rho_l2 * S[k] ** 2
            action_prev = U[:, k]
        terminal_theta = X[0, n] - target
        terminal_delta_r = X[2, n] - float(self.model_params["L0"])
        cost += self.weights.w_terminal_theta * terminal_theta**2 + self.weights.w_delta_r * terminal_delta_r**2
        if self.scaled:
            cost = cost / 1000.0
        z_parts = [ca.reshape(Xv, -1, 1), ca.reshape(Uv, -1, 1)]
        if self.alpha_enabled:
            z_parts.append(Sv)
        z = ca.vertcat(*z_parts)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": 80,
            "ipopt.tol": 1.0e-4,
            "ipopt.acceptable_tol": 1.0e-3,
        }
        DiagnosticCasadiNMPC._counter += 1
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", self.name)
        return ca.nlpsol(f"stage9b_{safe_name}_{DiagnosticCasadiNMPC._counter}", "ipopt", nlp, opts)

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
        mode = str(self.model_params.get("base_mode", "linear_sin"))
        theta_init = float(self.model_params.get("theta_init", 0.0))
        if mode == "linear_sin":
            amp = float(self.model_params.get("base_slide_amp", 0.0))
            a = amp * ca.cos(theta)
            ap = -amp * ca.sin(theta)
        elif mode == "tanh_sin":
            x_range = float(self.model_params.get("base_x_range", 0.0))
            beta = float(self.model_params.get("base_slide_beta", 1.0))
            z = beta * (ca.sin(theta) - np.sin(theta_init))
            tanh_z = ca.tanh(z)
            sech2 = 1.0 / ca.cosh(z) ** 2
            a = x_range * beta * sech2 * ca.cos(theta)
            ap = x_range * beta * sech2 * (-ca.sin(theta) - 2.0 * beta * tanh_z * ca.cos(theta) ** 2)
        else:
            raise ValueError(f"Unsupported base_mode: {mode}")
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

    def _initial_guess_and_bounds(
        self,
        state: np.ndarray,
        cem_sequence: np.ndarray | None,
        initial_override: dict[str, np.ndarray] | None,
    ) -> tuple[np.ndarray, list[float], list[float], list[float], list[float]]:
        n = self.horizon
        if initial_override is not None:
            U = np.asarray(initial_override["U"], dtype=float)[:n]
            S = np.asarray(initial_override.get("S", np.zeros(n)), dtype=float)[:n]
        elif self.warmstart == "cem" and cem_sequence is not None:
            U = np.asarray(cem_sequence, dtype=float)[:n]
            if len(U) < n:
                U = np.vstack([U, np.repeat(U[-1:], n - len(U), axis=0)])
            S = np.zeros(n, dtype=float)
        elif self.last_U is not None:
            U = np.vstack([self.last_U[1:], self.last_U[-1:]])
            S = np.r_[self.last_S[1:], self.last_S[-1]] if self.last_S is not None and len(self.last_S) else np.zeros(n)
        else:
            U = self._heuristic_sequence(state)
            S = np.zeros(n, dtype=float)
        X = self._simulate_guess(state, U)
        S = np.maximum(S, self._slack_from_trajectory(X)) if self.alpha_enabled else np.zeros(0, dtype=float)
        z0 = self._pack(X, U, S)
        x_l = [-np.inf] * (4 * (n + 1))
        x_u = [np.inf] * (4 * (n + 1))
        for k in range(n + 1):
            idx = 4 * k + 2
            x_l[idx] = 1.0e-6 / self.x_scale[2] if self.scaled else 1.0e-6
        if self.scaled:
            u_l = [-1.0, -1.0] * n
            u_u = [1.0, 1.0] * n
            s_l = [0.0] * n
            s_u = [np.inf] * n
        else:
            u_l = [-self.constraints.F_tan_max, -self.constraints.F_rad_max] * n
            u_u = [self.constraints.F_tan_max, self.constraints.F_rad_max] * n
            s_l = [0.0] * n
            s_u = [np.inf] * n
        lbx = x_l + u_l + (s_l if self.alpha_enabled else [])
        ubx = x_u + u_u + (s_u if self.alpha_enabled else [])
        lbg = [0.0] * 4
        ubg = [0.0] * 4
        for _ in range(n):
            lbg.extend([0.0] * 4)
            ubg.extend([0.0] * 4)
            if self.alpha_enabled:
                lbg.extend([-np.inf, -np.inf])
                ubg.extend([0.0, 0.0])
        return z0, lbx, ubx, lbg, ubg

    def _pack(self, X: np.ndarray, U: np.ndarray, S: np.ndarray) -> np.ndarray:
        Xv = X / self.x_scale if self.scaled else X
        Uv = U / self.u_scale if self.scaled else U
        parts = [Xv.T.reshape(-1, order="F"), Uv.T.reshape(-1, order="F")]
        if self.alpha_enabled:
            parts.append(S / self.s_scale if self.scaled else S)
        return np.concatenate(parts)

    def _unpack(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = self.horizon
        x_size = 4 * (n + 1)
        u_size = 2 * n
        Xv = np.asarray(z[:x_size], dtype=float).reshape((4, n + 1), order="F").T
        Uv = np.asarray(z[x_size : x_size + u_size], dtype=float).reshape((2, n), order="F").T
        X = Xv * self.x_scale if self.scaled else Xv
        U = Uv * self.u_scale if self.scaled else Uv
        if self.alpha_enabled:
            S = np.asarray(z[x_size + u_size : x_size + u_size + n], dtype=float)
            S = S * self.s_scale if self.scaled else S
        else:
            S = np.zeros(0, dtype=float)
        return X, U, S

    def _heuristic_sequence(self, state: np.ndarray) -> np.ndarray:
        theta, omega, r, r_dot = np.asarray(state, dtype=float)
        theta_error = self.target_theta - theta
        kp_theta = float(self.nominal_cfg.get("kp_theta", 7.5))
        kd_omega = float(self.nominal_cfg.get("kd_omega", 1.6))
        radial_kp = float(self.nominal_cfg.get("radial_kp", 60.0))
        radial_kd = float(self.nominal_cfg.get("radial_kd", 8.0))
        taper = np.linspace(1.0, float(self.nominal_cfg.get("terminal_taper", 0.45)), self.horizon)
        sequence = np.column_stack(
            [
                (kp_theta * theta_error - kd_omega * omega) * taper,
                np.full(self.horizon, -radial_kp * (r - float(self.model_params["L0"])) - radial_kd * r_dot),
            ]
        )
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence

    def _simulate_guess(self, state: np.ndarray, sequence: np.ndarray) -> np.ndarray:
        X = [np.asarray(state, dtype=float).copy()]
        x = X[0].copy()
        for action in sequence:
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                x = X[-1].copy()
            if not np.all(np.isfinite(x)):
                x = X[-1].copy()
            X.append(x.copy())
        return np.asarray(X, dtype=float)

    def _slack_from_trajectory(self, X: np.ndarray) -> np.ndarray:
        if len(X) < 2:
            return np.zeros(self.horizon, dtype=float)
        alpha = np.diff(X[:, 1]) / self.prediction_dt
        return np.maximum(0.0, np.abs(alpha) - self.constraints.alpha_max)

    def _diagnostics(
        self,
        X_decision: np.ndarray,
        U: np.ndarray,
        S: np.ndarray,
        solve_time: float,
        success: bool,
        status: str,
        iterations: int,
        objective: float,
    ) -> dict[str, Any]:
        residuals = []
        alpha_viol = []
        force_viol = []
        for k, action in enumerate(U):
            dyn_next = step_dynamics(X_decision[k], self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            residuals.append(np.abs(X_decision[k + 1] - dyn_next))
            alpha = (float(X_decision[k + 1, 1]) - float(X_decision[k, 1])) / self.prediction_dt
            if self.alpha_enabled:
                slack = float(S[k]) if k < len(S) else 0.0
                alpha_viol.append(max(0.0, abs(alpha) - self.constraints.alpha_max - slack))
            force_viol.append(max(0.0, abs(float(action[0])) - self.constraints.F_tan_max))
            force_viol.append(max(0.0, abs(float(action[1])) - self.constraints.F_rad_max))
        residual_arr = np.asarray(residuals, dtype=float).reshape(-1) if residuals else np.array([])
        constraint_arr = np.asarray(alpha_viol + force_viol, dtype=float)
        slacks = np.asarray(S, dtype=float)
        return {
            "success": bool(success),
            "solve_time": float(solve_time),
            "iterations": int(iterations),
            "status": str(status),
            "failure_reason": "" if success else str(status),
            "objective": float(objective) if np.isfinite(objective) else np.nan,
            "dynamics_residual_max": _finite_max(residual_arr),
            "dynamics_residual_mean": _finite_mean(residual_arr),
            "constraint_violation_max": _finite_max(constraint_arr),
            "constraint_violation_mean": _finite_mean(constraint_arr),
            "alpha_slack_mean": _finite_mean(slacks),
            "alpha_slack_max": _finite_max(slacks),
            "alpha_slack_active_count": int(np.count_nonzero(slacks > 1.0e-8)),
            "first_F_tan": float(U[0, 0]) if len(U) else np.nan,
            "first_F_rad": float(U[0, 1]) if len(U) else np.nan,
        }


class AdaptiveDiagnosticNMPC:
    estimated_parameter_names = ("m", "k", "b_r")

    def __init__(self, initial_model_params: dict[str, Any], mpc_params: dict[str, Any], variant: dict[str, Any]):
        self.model_params = dict(initial_model_params)
        self.current_model_params = dict(initial_model_params)
        self.mpc_params = dict(mpc_params)
        self.variant = dict(variant)
        self.controller = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, variant)
        self.cem = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.no_alpha_helper: DiagnosticCasadiNMPC | None = None
        if str(variant.get("warmstart", "")) == "no_alpha" and bool(variant.get("alpha", False)):
            helper_variant = dict(variant)
            helper_variant["name"] = str(variant["name"]) + "_helper_no_alpha"
            helper_variant["alpha"] = False
            helper_variant["rho_l1"] = 0.0
            helper_variant["warmstart"] = "shift"
            self.no_alpha_helper = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, helper_variant)
        self.last_diag: dict[str, Any] = {}
        self.last_update_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.current_model_params = dict(self.model_params)
        self.controller = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, self.variant)
        self.cem = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.cem.reset()
        self.no_alpha_helper = None
        if str(self.variant.get("warmstart", "")) == "no_alpha" and bool(self.variant.get("alpha", False)):
            helper_variant = dict(self.variant)
            helper_variant["name"] = str(self.variant["name"]) + "_helper_no_alpha"
            helper_variant["alpha"] = False
            helper_variant["rho_l1"] = 0.0
            helper_variant["warmstart"] = "shift"
            self.no_alpha_helper = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, helper_variant)
        self.last_diag = {}
        self.last_update_diagnostics = {}

    def set_target_theta(self, target_theta: float) -> None:
        self.controller.set_target_theta(target_theta)
        self.cem.set_target_theta(target_theta)
        if self.no_alpha_helper is not None:
            self.no_alpha_helper.set_target_theta(target_theta)

    def act(self, observation: Any) -> np.ndarray:
        state = observation_to_state(observation)
        cem_sequence = None
        cem_action = np.array([np.nan, np.nan], dtype=float)
        if str(self.variant.get("warmstart", "")) == "cem":
            cem_action = self.cem.act(observation)
            cem_sequence = self.cem.controller.last_solution.copy()
        initial_override = None
        if self.no_alpha_helper is not None:
            helper = self.no_alpha_helper.solve(state, self.controller.last_action)
            initial_override = {"U": helper["U"] if "U" in helper else self.controller._heuristic_sequence(state)}
        diag = self.controller.solve(state, self.controller.last_action, cem_sequence=cem_sequence, initial_override=initial_override)
        action = np.asarray(diag["first_action"], dtype=float)
        if np.any(np.isfinite(cem_action)):
            action_diff = float(np.linalg.norm(action - cem_action))
        else:
            action_diff = np.nan
        self.last_diag = {
            "nmpc_solver_success": bool(diag["success"]),
            "nmpc_solver_failure": not bool(diag["success"]),
            "nmpc_fallback_would_be_used": bool(diag["fallback_would_be_used"]),
            "nmpc_solve_time_s": float(diag["solve_time"]),
            "nmpc_solver_iterations": int(diag["iterations"]),
            "nmpc_solver_status": str(diag["status"]),
            "nmpc_failure_reason": str(diag["failure_reason"]),
            "nmpc_objective": float(diag["objective"]) if np.isfinite(diag["objective"]) else np.nan,
            "nmpc_dynamics_residual_max": float(diag["dynamics_residual_max"]),
            "nmpc_dynamics_residual_mean": float(diag["dynamics_residual_mean"]),
            "nmpc_constraint_violation_max": float(diag["constraint_violation_max"]),
            "nmpc_constraint_violation_mean": float(diag["constraint_violation_mean"]),
            "nmpc_alpha_slack_mean": float(diag["alpha_slack_mean"]),
            "nmpc_alpha_slack_max": float(diag["alpha_slack_max"]),
            "nmpc_alpha_slack_active_count": int(diag["alpha_slack_active_count"]),
            "nmpc_first_F_tan": float(action[0]),
            "nmpc_first_F_rad": float(action[1]),
            "nmpc_first_action_diff_vs_cem": action_diff,
            "nmpc_horizon": int(self.controller.horizon),
            "nmpc_alpha_enabled": bool(self.controller.alpha_enabled),
            "nmpc_scaled_variables": bool(self.controller.scaled),
            "nmpc_warmstart_mode": str(self.controller.warmstart),
            "nmpc_alpha_rho_l1": float(self.controller.alpha_rho_l1),
            "nmpc_alpha_rho_l2": float(self.controller.alpha_rho_l2),
            "nmpc_x_scale_theta": float(self.controller.x_scale[0]),
            "nmpc_x_scale_omega": float(self.controller.x_scale[1]),
            "nmpc_x_scale_r": float(self.controller.x_scale[2]),
            "nmpc_x_scale_r_dot": float(self.controller.x_scale[3]),
            "nmpc_u_scale_F_tan": float(self.controller.u_scale[0]),
            "nmpc_u_scale_F_rad": float(self.controller.u_scale[1]),
            "nmpc_s_scale_alpha": float(self.controller.s_scale),
            "mpc_solve_count": int(self.controller.solve_count),
        }
        return self.controller.constraints.clip_action(action)

    def get_last_solve_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diag)

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
        self.cem.update_parameters(theta_hat, alpha=alpha, bounds=bounds)
        if self.no_alpha_helper is not None:
            self.no_alpha_helper.set_model_params(update)
        self.last_update_diagnostics = {
            "mpc_recreated_on_update": False,
            "solver_recreated_on_update": False,
            "last_action_preserved_on_update": True,
            "last_solution_existed_before_update": self.controller.last_U is not None,
            "last_solution_preserved_on_update": self.controller.last_U is not None,
        }
        return self.get_current_parameter_estimate()


def configure_diagnostic_run(base_cfg: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
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
    solver["horizon"] = int(variant.get("horizon", solver.get("horizon", 18)))
    return cfg


def _add_diag_fields(row: dict[str, Any], diag: dict[str, Any] | None = None) -> dict[str, Any]:
    diag = diag or {}
    enriched = dict(row)
    for key in DIAG_FIELDS:
        if key in {"nmpc_solver_success", "nmpc_solver_failure", "nmpc_fallback_would_be_used", "nmpc_alpha_enabled", "nmpc_scaled_variables"}:
            enriched[key] = bool(diag.get(key, False))
        elif key in {"nmpc_solver_status", "nmpc_failure_reason", "nmpc_warmstart_mode"}:
            enriched[key] = str(diag.get(key, ""))
        elif key in {"nmpc_solver_iterations", "nmpc_alpha_slack_active_count", "nmpc_horizon"}:
            enriched[key] = int(diag.get(key, 0))
        else:
            enriched[key] = float(diag.get(key, np.nan))
    enriched["nmpc_solve_count"] = int(diag.get("mpc_solve_count", 0))
    return enriched


def run_diagnostic_condition(variant: dict[str, Any], condition_cfg: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    adaptive_cfg = cfg.get("adaptive", {})
    alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 0.5))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    target_theta = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    coupling_cfg = dict(cfg.get("coupling_ablation", {}))
    mpc_state_input = str(coupling_cfg.get("mpc_state_input", "filtered")).lower()
    identifier_input = str(coupling_cfg.get("identifier_input", "filtered")).lower()
    identifier_mode = str(coupling_cfg.get("identifier_mode", "adaptive")).lower()
    estimator_model_params_source = str(coupling_cfg.get("estimator_model_params_source", "adaptive")).lower()
    mpc_model_params_source = str(coupling_cfg.get("mpc_model_params_source", "adaptive")).lower()

    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(true_params, condition_cfg.get("observation_noise", {}), seed=int(condition_cfg.get("seed", 0)))
    obs_meas = wrapper.observe(obs_true)
    controller = AdaptiveDiagnosticNMPC(model_params, cfg["mpc_params"], variant)
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()
    filter_cfg = dict(cfg.get("observation_filter", {"type": "ukf_bias", "identifier_input": "filtered"}))
    filter_cfg["condition_name"] = CONDITION
    filter_type = str(filter_cfg.get("type", "ukf_bias")).lower()
    obs_filter = make_observation_filter(filter_cfg)
    initial_filter_model_params = model_params if estimator_model_params_source == "initial" else current_prediction_params(model_params, controller)
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
            "coupling_case": "stage9b_nmpc_diagnosis",
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
    rows.append(_add_diag_fields(initial_row))
    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        controller.set_target_theta(target_theta)
        action_mpc = controller.act(obs_mpc)
        solve_diag = controller.get_last_solve_diagnostics()
        for _ in range(hold_steps):
            prev_obs_meas = obs_meas
            prev_obs_filt = obs_filt
            prev_obs_true = obs_true
            prev_history_row = env.get_history()[-1]
            action_exec = np.asarray(action_mpc, dtype=float)
            obs_true = env.step(action_exec)
            obs_meas = wrapper.observe(obs_true)
            filter_model_params = model_params if estimator_model_params_source == "initial" else current_prediction_params(model_params, controller)
            obs_filter.predict(action_exec, float(true_params["dt"]), model_params=filter_model_params)
            filt_state = obs_filter.update(obs_meas, float(true_params["dt"]), action=action_exec, true_state=observation_to_state(obs_true), model_params=filter_model_params)
            obs_filt = observation_from_state(obs_meas, filt_state, true_params)
            obs_mpc = select_observation_by_source(mpc_state_input, obs_meas, obs_filt, obs_true)
            if obs_mpc is None:
                raise ValueError("mpc_state_input cannot be none.")
            id_prev = select_observation_by_source(identifier_input, prev_obs_meas, prev_obs_filt, prev_obs_true)
            id_next = select_observation_by_source(identifier_input, obs_meas, obs_filt, obs_true)
            if identifier_mode == "frozen" or identifier_input == "none":
                result = SimpleNamespace(theta_hat=identifier.get_parameter_estimate(), prediction_error=np.nan, updated=False, num_samples=len(identifier.transitions), success=True)
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
            if result.updated and steps >= warmup_steps and identifier_mode == "adaptive" and mpc_model_params_source == "adaptive":
                controller.update_parameters(result.theta_hat, alpha=alpha, bounds=parameter_bounds)
                update_diagnostics = controller.get_last_update_diagnostics()
                parameter_update_flag = True
                parameter_update_count += 1
            history_row = env.get_history()[-1]
            alpha_step = (float(history_row["omega"]) - float(prev_history_row["omega"])) / float(true_params["dt"])
            safety_diagnostics = SafetyFilterResult.disabled(action_exec).as_diagnostics()
            safety_diagnostics.update({"true_safe_alpha": alpha_step})
            enriched = append_adaptive_fields(
                history_row,
                observation_to_state(obs_meas),
                filt_state,
                result,
                controller,
                parameter_update_flag=parameter_update_flag,
                target_theta=target_theta,
                alpha_step=alpha_step,
                solve_diagnostics=solve_diag,
                update_diagnostics=update_diagnostics,
                filter_diagnostics=obs_filter.get_diagnostics(),
                coupling_diagnostics=coupling_diagnostics(result, parameter_step_norm),
                safety_diagnostics=safety_diagnostics,
                theta_cmd=target_theta,
                progress_governor_mode="off",
            )
            rows.append(_add_diag_fields(enriched, solve_diag))
            if env.is_done() or steps >= max_steps:
                break
    return rows


def summarize_rows(variant: dict[str, Any], rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    method = str(variant["name"])
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    decisions = _decision_rows(rows, "nmpc_solve_count") if method in NMPC_VARIANTS else []
    first_actions = np.column_stack([_series(decisions, "nmpc_first_F_tan"), _series(decisions, "nmpc_first_F_rad")]) if decisions else np.empty((0, 2))
    return {
        "variant": method,
        "condition": CONDITION,
        "family": str(variant.get("family", method)),
        "horizon": int(variant.get("horizon", 0)),
        "alpha_enabled": bool(variant.get("alpha", False)),
        "scaled_variables": bool(variant.get("scaled", False)),
        "warmstart_mode": str(variant.get("warmstart", "")),
        "rho_L1": float(variant.get("rho_l1", np.nan)),
        "rho_L2": float(variant.get("rho_l2", np.nan)),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "solver_success_count": int(sum(bool(row.get("nmpc_solver_success", False)) for row in decisions)),
        "solver_failure_count": int(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions)),
        "solver_failure_rate": float(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "fallback_would_count": int(sum(bool(row.get("nmpc_fallback_would_be_used", False)) for row in decisions)),
        "fallback_would_rate": float(sum(bool(row.get("nmpc_fallback_would_be_used", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "status_examples": "; ".join(sorted({str(row.get("nmpc_solver_status", ""))[:80] for row in decisions if str(row.get("nmpc_solver_status", ""))})[:3]),
        "iterations_mean": _finite_mean(_series(decisions, "nmpc_solver_iterations")) if decisions else np.nan,
        "solve_time_mean": _finite_mean(_series(decisions, "nmpc_solve_time_s")) if decisions else np.nan,
        "solve_time_max": _finite_max(_series(decisions, "nmpc_solve_time_s")) if decisions else np.nan,
        "objective_mean": _finite_mean(_series(decisions, "nmpc_objective")) if decisions else np.nan,
        "dynamics_residual_max": _finite_max(_series(decisions, "nmpc_dynamics_residual_max")) if decisions else np.nan,
        "dynamics_residual_mean": _finite_mean(_series(decisions, "nmpc_dynamics_residual_mean")) if decisions else np.nan,
        "constraint_violation_max": _finite_max(_series(decisions, "nmpc_constraint_violation_max")) if decisions else np.nan,
        "constraint_violation_mean": _finite_mean(_series(decisions, "nmpc_constraint_violation_mean")) if decisions else np.nan,
        "alpha_slack_mean": _finite_mean(_series(decisions, "nmpc_alpha_slack_mean")) if decisions else np.nan,
        "alpha_slack_max": _finite_max(_series(decisions, "nmpc_alpha_slack_max")) if decisions else np.nan,
        "alpha_slack_active_count": int(np.nansum(_series(decisions, "nmpc_alpha_slack_active_count"))) if decisions else 0,
        "first_F_tan_mean": _finite_mean(first_actions[:, 0]) if len(first_actions) else np.nan,
        "first_F_rad_mean": _finite_mean(first_actions[:, 1]) if len(first_actions) else np.nan,
        "first_action_diff_vs_cem_mean": _finite_mean(_series(decisions, "nmpc_first_action_diff_vs_cem")) if decisions else np.nan,
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_clipped_max": _clipped_max_excluding_one(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "runtime_s": float(runtime_s),
        "x_scale": ",".join(_fmt(rows[-1].get(key, np.nan)) for key in ["nmpc_x_scale_theta", "nmpc_x_scale_omega", "nmpc_x_scale_r", "nmpc_x_scale_r_dot"]),
        "u_scale": ",".join(_fmt(rows[-1].get(key, np.nan)) for key in ["nmpc_u_scale_F_tan", "nmpc_u_scale_F_rad"]),
        "s_scale": _fmt(rows[-1].get("nmpc_s_scale_alpha", np.nan)),
    }


SUMMARY_FIELDS = list(summarize_rows({"name": "_dummy"}, [{"theta": 0.0, "target_reached": False, "t": 0.0}], {"mpc_params": {"constraints": {}}, "true_params": {"dt": 0.01, "alpha_max": 3.0}}, 0.0).keys())


def save_summary(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def save_plots(summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    variants = [row["variant"] for row in summary_rows]
    x = np.arange(len(variants))

    def bar(metric: str, title: str, ylabel: str, filename: str) -> None:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(x, [float(row[metric]) for row in summary_rows])
        ax.set_xticks(x)
        ax.set_xticklabels(variants, rotation=30, ha="right")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(fig_dir / filename, dpi=150)
        plt.close(fig)

    bar("solver_failure_rate", "Stage 9B solver failure rate by variant", "failure rate", "solver_success_by_variant.png")
    bar("solve_time_mean", "Stage 9B solve time by variant", "mean solve time [s]", "solve_time_by_variant.png")
    bar("dynamics_residual_max", "Stage 9B dynamics residual by variant", "max residual", "dynamics_residual_by_variant.png")
    bar("constraint_violation_max", "Stage 9B constraint violation by variant", "max violation", "constraint_violation_by_variant.png")
    bar("first_F_tan_mean", "Stage 9B first F_tan by variant", "mean first F_tan", "first_action_comparison_vs_baseline.png")

    continuation = [row for row in summary_rows if str(row["variant"]).startswith("nmpc_alpha_slack_rho")]
    if continuation:
        fig, ax = plt.subplots(figsize=(8, 5))
        rho = [float(row["rho_L1"]) for row in continuation]
        slack = [float(row["alpha_slack_max"]) for row in continuation]
        fail = [float(row["solver_failure_rate"]) for row in continuation]
        ax.plot(rho, slack, marker="o", label="slack max")
        ax2 = ax.twinx()
        ax2.plot(rho, fail, marker="s", color="tab:red", label="failure rate")
        ax.set_xscale("log")
        ax.set_xlabel("rho_L1")
        ax.set_ylabel("alpha slack max")
        ax2.set_ylabel("failure rate")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(fig_dir / "alpha_slack_vs_penalty.png", dpi=150)
        plt.close(fig)


def _row(summary_rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(row for row in summary_rows if row["variant"] == name)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    no_alpha = _row(summary_rows, "nmpc_no_alpha_basic")
    short_rows = [_row(summary_rows, name) for name in ["nmpc_no_alpha_short_N5", "nmpc_no_alpha_short_N8", "nmpc_no_alpha_short_N10"]]
    cem_ws = _row(summary_rows, "nmpc_cem_warmstart")
    scaled = _row(summary_rows, "nmpc_scaled_variables")
    continuation = [_row(summary_rows, name) for name in ["nmpc_alpha_slack_rho1", "nmpc_alpha_slack_rho10", "nmpc_alpha_slack_rho100", "nmpc_alpha_slack_rho1000"]]
    first_failing_rho = next((row for row in continuation if float(row["solver_failure_rate"]) > 0.0), None)
    no_alpha_solves = float(no_alpha["solver_failure_rate"]) < 0.2
    full_no_alpha_fails = float(no_alpha["solver_failure_rate"]) > 0.0
    short_solves = [row for row in short_rows if float(row["solver_failure_rate"]) < float(no_alpha["solver_failure_rate"])]
    cem_improves = float(cem_ws["solver_failure_rate"]) < float(no_alpha["solver_failure_rate"])
    scaled_improves = float(scaled["solver_failure_rate"]) < float(_row(summary_rows, "nmpc_alpha_slack_rho100")["solver_failure_rate"])
    all_alpha_continuation_solves = first_failing_rho is None
    if not no_alpha_solves:
        cause = "formulation/scaling/initialization, because failures already occur without alpha slack."
        next_step = "proper scaled NMPC refinement before more alpha/task work."
    elif first_failing_rho is not None:
        cause = "alpha slack/task interaction, because no-alpha solves but alpha continuation fails."
        next_step = "alpha/task redesign before stress validation."
    elif all_alpha_continuation_solves:
        cause = "Stage 9A formulation details rather than the basic dynamics equality or alpha slack concept: no-alpha, short horizon, CEM warm-start, alpha continuation, and scaled variables all solved on clean."
        next_step = "proper scaled NMPC refinement, specifically reconciling Stage 9A cost/penalty/scaling choices with the Stage 9B solvable formulation."
    else:
        cause = "not isolated; current diagnostic variants did not expose a clean single failure mode."
        next_step = "proper scaled NMPC refinement."
    lines = [
        "# Stage 9B NMPC Diagnosis Report",
        "",
        "## Scope",
        "- Clean condition only.",
        "- Diagnosis only: tested solver feasibility, initialization, horizon, alpha slack continuation, and variable scaling.",
        "- No noise/noise_bias runs, no broad controller tuning, and no formal safety claims.",
        "- Dynamics, UKF-bias, filtered Windowed NLS identifier, baseline CEM, Stage 7/8/9A results, and default configs were not intentionally changed.",
        "",
        "## Commands Run",
        *[f"- `{cmd}`" for cmd in commands],
        "",
        "## Summary",
        "| variant | success/fail | status examples | N | alpha | scaled | warmstart | rho_L1 | solve mean/max | dyn residual max | constr viol max | slack mean/max/active | first action mean | target | alpha p95/p99/max |",
        "|---|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        success = int(row["solver_success_count"])
        fail = int(row["solver_failure_count"])
        lines.append(
            f"| {row['variant']} | {success}/{fail} | {row['status_examples']} | {row['horizon']} | "
            f"{row['alpha_enabled']} | {row['scaled_variables']} | {row['warmstart_mode']} | {_fmt(row['rho_L1'])} | "
            f"{_fmt(row['solve_time_mean'])}/{_fmt(row['solve_time_max'])} | {_fmt(row['dynamics_residual_max'])} | "
            f"{_fmt(row['constraint_violation_max'])} | {_fmt(row['alpha_slack_mean'])}/{_fmt(row['alpha_slack_max'])}/{row['alpha_slack_active_count']} | "
            f"{_fmt(row['first_F_tan_mean'])},{_fmt(row['first_F_rad_mean'])} | {row['target_reached']} | "
            f"{_fmt(row['alpha_p95_severity'])}/{_fmt(row['alpha_p99_severity'])}/{_fmt(row['alpha_max_severity'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Can NMPC solve clean without alpha?",
            f"- {'Yes' if no_alpha_solves else 'No'}: no-alpha basic failure rate={_fmt(no_alpha['solver_failure_rate'])}, statuses={no_alpha['status_examples']}.",
            "",
            "2. Does short horizon solve when full horizon fails?",
            f"- {'Not applicable: full-horizon no-alpha did not fail' if not full_no_alpha_fails else ('Yes/mixed' if short_solves else 'No')}: "
            f"full-horizon no-alpha failure rate={_fmt(no_alpha['solver_failure_rate'])}; short-horizon failure rates N5/N8/N10 = "
            f"{_fmt(short_rows[0]['solver_failure_rate'])}/{_fmt(short_rows[1]['solver_failure_rate'])}/{_fmt(short_rows[2]['solver_failure_rate'])}.",
            "",
            "3. Does CEM warm-start improve solver success?",
            f"- {'Yes' if cem_improves else 'No success-rate improvement'}: CEM warm-start failure rate={_fmt(cem_ws['solver_failure_rate'])} vs no-alpha basic={_fmt(no_alpha['solver_failure_rate'])}. It did reduce no-alpha mean solve time from {_fmt(no_alpha['solve_time_mean'])} s to {_fmt(cem_ws['solve_time_mean'])} s.",
            "",
            "4. Does variable scaling improve solver success?",
            f"- {'Yes' if scaled_improves else 'No success-rate improvement'}: scaled failure rate={_fmt(scaled['solver_failure_rate'])}; scales x={scaled['x_scale']}, u={scaled['u_scale']}, s={scaled['s_scale']}. It did reduce rho100 mean solve time from {_fmt(_row(summary_rows, 'nmpc_alpha_slack_rho100')['solve_time_mean'])} s to {_fmt(scaled['solve_time_mean'])} s.",
            "",
            "5. At what alpha penalty does slack formulation start failing?",
            f"- {'rho_L1=' + _fmt(first_failing_rho['rho_L1']) if first_failing_rho else 'No alpha-continuation failure observed in tested rho_L1 values'}."
            f" Continuation failure rates rho 1/10/100/1000 = "
            f"{_fmt(continuation[0]['solver_failure_rate'])}/{_fmt(continuation[1]['solver_failure_rate'])}/{_fmt(continuation[2]['solver_failure_rate'])}/{_fmt(continuation[3]['solver_failure_rate'])}.",
            "",
            "6. Is failure mainly due to formulation/scaling/initialization or task-alpha conflict?",
            f"- Current diagnosis points to {cause}",
            "",
            "7. Should next step be proper scaled NMPC refinement, alpha/task redesign, or closing NMPC for now?",
            f"- Recommended next step: {next_step}",
        ]
    )
    (output_root / "stage9b_report.md").write_text("\n".join(lines) + "\n")


def run(output_root: Path, config_path: Path) -> None:
    try:
        casadi_version = ca.__version__
    except Exception as exc:
        raise RuntimeError("CasADi/IPOPT status unavailable: CasADi import failed.") from exc
    print(f"[stage9b] CasADi {casadi_version}; clean condition only", flush=True)
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]
    summary_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        name = str(variant["name"])
        print(f"[stage9b] running {name}", flush=True)
        if variant.get("type") == "baseline":
            cfg = configure_cem_run(base_cfg, "baseline_cem")
            start = time.perf_counter()
            rows = run_condition(CONDITION, base_cfg["conditions"][CONDITION], cfg)
        else:
            cfg = configure_diagnostic_run(base_cfg, variant)
            start = time.perf_counter()
            rows = run_diagnostic_condition(variant, base_cfg["conditions"][CONDITION], cfg)
        runtime_s = time.perf_counter() - start
        summary = summarize_rows(variant, rows, cfg, runtime_s)
        summary_rows.append(summary)
        print(
            "[stage9b] "
            f"{name}: fail_rate={summary['solver_failure_rate']:.4g}, "
            f"solve={summary['solve_time_mean']:.4g}s, dyn_res={summary['dynamics_residual_max']:.4g}, "
            f"constr={summary['constraint_violation_max']:.4g}, target={summary['target_reached']}, "
            f"runtime={runtime_s:.2f}s",
            flush=True,
        )
    save_summary(summary_rows, output_root / "stage9b_summary.csv")
    save_plots(summary_rows, output_root)
    save_report(summary_rows, output_root, commands)
    print(f"[stage9b] summary: {output_root / 'stage9b_summary.csv'}", flush=True)
    print(f"[stage9b] report : {output_root / 'stage9b_report.md'}", flush=True)
    print(f"[stage9b] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
