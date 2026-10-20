"""Stage 9H long-horizon crossing planner plus short-horizon NMPC tracker."""

from __future__ import annotations

import argparse
import copy
import csv
import os
import re
import sys
import time
from pathlib import Path
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

from run_spring2d_adaptive_mpc_conditions import load_experiment_config, run_condition
from run_spring2d_stage8e_explicit_nmpc import (
    _clipped_max_excluding_one,
    _decision_rows,
    _finite_max,
    _finite_mean,
    _finite_percentile,
    _first_reach_time,
    _series,
)
from run_spring2d_stage9b_nmpc_diagnosis import DiagnosticCasadiNMPC
from run_spring2d_stage9f_crossing_lexicographic_nmpc import (
    CROSSING_MARGIN,
    apply_stage9f_overrides,
    condition_with_seed,
    configure_cem_seeded,
    configure_nmpc_run,
    run_nmpc_condition,
    summarize_rows as summarize_stage9f_rows,
)
from run_spring2d_stage9g_crossing_alpha_frontier import AlphaFrontierProblem, finite_float, fmt
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.estimation.noisy_observation_wrapper import observation_to_state
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC as CEMAdaptiveMPC


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9h_planner_tracker"
BOUNDARY_HORIZONS = [42, 45, 48, 50, 54, 57, 60]
BOUNDARY_FIXED_ALPHA = [3.0, 4.0]
SEEDS = [101, 102, 103]
PHASE1_CONDITIONS = ["initial_theta_offset"]
PHASE2_CONDITIONS = [
    "clean",
    "noise",
    "noise_bias",
    "stronger_noise",
    "larger_target_angle",
    "parameter_mismatch_low_k",
    "parameter_mismatch_high_k",
]
REFERENCE_METHODS = ["baseline_cem", "nmpc_base", "nmpc_crossing_weighted"]
TRACKER_METHODS = ["oracle_planner_nmpc_tracker", "oracle_planner_nmpc_tracker_with_cem_fallback"]
METHODS = REFERENCE_METHODS + TRACKER_METHODS
PLANNER_ALPHA_LIMIT = 3.0
STAGE9F_BASELINE_ALPHA_MAX = 9.142


def safe_status(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()[:180]


def initial_state(params: dict[str, Any]) -> np.ndarray:
    return np.array(
        [
            float(params["theta_init"]),
            float(params["omega_init"]),
            float(params["r_init"]),
            float(params["r_dot_init"]),
        ],
        dtype=float,
    )


def smooth_reference(problem: AlphaFrontierProblem, x0: np.ndarray) -> dict[str, np.ndarray]:
    n = problem.horizon
    dt = problem.prediction_dt
    T = n * dt
    times = np.arange(n + 1, dtype=float) * dt
    theta0 = float(x0[0])
    omega0 = float(x0[1])
    thetaT = float(problem.target_crossing)
    omegaT = min(0.8 * problem.constraints.omega_max, max(0.0, (thetaT - theta0) / max(T, 1.0e-6)))
    a0 = theta0
    a1 = omega0
    rhs1 = thetaT - a0 - a1 * T
    rhs2 = omegaT - a1
    mat = np.array([[T**2, T**3], [2.0 * T, 3.0 * T**2]], dtype=float)
    a2, a3 = np.linalg.solve(mat, np.array([rhs1, rhs2], dtype=float))
    theta = a0 + a1 * times + a2 * times**2 + a3 * times**3
    omega = a1 + 2.0 * a2 * times + 3.0 * a3 * times**2
    r = np.full(n + 1, float(problem.model_params["L0"]))
    r_dot = np.zeros(n + 1, dtype=float)
    X = np.column_stack([theta, omega, r, r_dot])
    U = np.zeros((n, 2), dtype=float)
    alpha_peak = float(np.nanmax(np.abs(np.diff(omega) / dt))) if n > 0 else 0.0
    return {"X": X, "U": U, "alpha_peak": np.asarray(max(alpha_peak, 0.1))}


class FastAlphaFrontierProblem(AlphaFrontierProblem):
    """Stage 9H-local frontier solver with bounded IPOPT time for infeasible cases."""

    def _build_solver(self, counter: int) -> Any:
        n = self.horizon
        Xv = ca.SX.sym("X", 4, n + 1)
        Uv = ca.SX.sym("U", 2, n)
        Av = ca.SX.sym("alpha_peak")
        P = ca.SX.sym("P", 8)
        X = ca.diag(ca.DM(self.x_scale)) @ Xv
        U = ca.diag(ca.DM(self.u_scale)) @ Uv
        alpha_peak = self.alpha_scale * Av
        x0_param = P[0:4]
        target_crossing = P[4]
        dyn_params = {"m": P[5], "k": P[6], "b_r": P[7]}
        g: list[Any] = [X[:, 0] - x0_param]
        action_cost = 0
        rate_cost = 0
        for k in range(n):
            x_next = self._rk4_symbolic(X[:, k], U[:, k], dyn_params)
            g.append(X[:, k + 1] - x_next)
            alpha = (X[1, k + 1] - X[1, k]) / self.prediction_dt
            g.append(alpha - alpha_peak)
            g.append(-alpha - alpha_peak)
            action_cost += ca.dot(U[:, k], U[:, k])
            if k > 0:
                rate_cost += ca.dot(U[:, k] - U[:, k - 1], U[:, k] - U[:, k - 1])
        terminal_omega = X[1, n]
        g.append(target_crossing - X[0, n])
        cost = alpha_peak + 1.0e-7 * action_cost + 1.0e-7 * rate_cost + 1.0e-4 * terminal_omega**2
        z = ca.vertcat(ca.reshape(Xv, -1, 1), ca.reshape(Uv, -1, 1), Av)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": 250,
            "ipopt.max_cpu_time": 8.0,
            "ipopt.tol": 1.0e-6,
            "ipopt.acceptable_tol": 1.0e-5,
            "ipopt.constr_viol_tol": 1.0e-6,
        }
        return ca.nlpsol(f"stage9h_alpha_frontier_{counter}", "ipopt", nlp, opts)


def run_boundary_problem(
    problem: AlphaFrontierProblem,
    x0: np.ndarray,
    fixed_alpha_limit: float | None,
    warmstarts: list[tuple[str, dict[str, np.ndarray] | None]],
) -> tuple[dict[str, Any], str, list[str]]:
    attempts: list[str] = []
    last_diag: dict[str, Any] | None = None
    for label, warm in warmstarts:
        diag = problem.solve(x0, warmstart=warm, fixed_alpha_limit=fixed_alpha_limit, warmstart_label=label)
        attempts.append(f"{label}:{diag['status']}")
        last_diag = diag
        if bool(diag["success"]):
            return diag, label, attempts
    assert last_diag is not None
    return last_diag, str(last_diag.get("warm_start", "unknown")), attempts


def boundary_row(
    mode: str,
    horizon: int,
    problem: AlphaFrontierProblem,
    diag: dict[str, Any],
    accepted_warmstart: str,
    attempts: list[str],
) -> dict[str, Any]:
    success = bool(diag["success"])
    return {
        "section": "boundary",
        "mode": mode,
        "horizon": int(horizon),
        "crossing_time_s": float(horizon * problem.prediction_dt),
        "fixed_alpha_limit": finite_float(diag.get("fixed_alpha_limit", np.nan)),
        "success": success,
        "status": str(diag["status"]),
        "iterations": int(diag["iterations"]),
        "solve_time_s": finite_float(diag["solve_time_s"]),
        "alpha_peak": finite_float(diag["alpha_peak"]) if success or mode.startswith("fixed_alpha") else np.nan,
        "terminal_theta_deg": finite_float(diag["terminal_theta_deg"]) if success else np.nan,
        "terminal_omega": finite_float(diag["terminal_omega"]) if success else np.nan,
        "terminal_crossing_margin_deg": finite_float(diag["terminal_crossing_margin_deg"]) if success else np.nan,
        "F_tan_margin": finite_float(diag["F_tan_margin"]) if success else np.nan,
        "F_rad_margin": finite_float(diag["F_rad_margin"]) if success else np.nan,
        "delta_r_margin": finite_float(diag["delta_r_margin"]) if success else np.nan,
        "omega_margin": finite_float(diag["omega_margin"]) if success else np.nan,
        "action_total_variation": finite_float(diag["action_total_variation"]) if success else np.nan,
        "warm_start": accepted_warmstart,
        "warm_start_attempts": "; ".join(attempts),
    }


def run_part_a_boundary(base_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    cfg = apply_stage9f_overrides(copy.deepcopy(base_cfg), "initial_theta_offset")
    true_params = cfg["true_params"]
    mpc_params = cfg["mpc_params"]
    x0 = initial_state(true_params)
    rows: list[dict[str, Any]] = []
    successful: dict[int, dict[str, Any]] = {}
    nearest_longer: dict[str, np.ndarray] | None = None
    for horizon in sorted(BOUNDARY_HORIZONS, reverse=True):
        print(f"[stage9h] Part A boundary horizon N={horizon}", flush=True)
        problem = FastAlphaFrontierProblem(true_params, mpc_params, horizon)
        smooth = smooth_reference(problem, x0)
        warmstarts: list[tuple[str, dict[str, np.ndarray] | None]] = []
        if nearest_longer is not None:
            warmstarts.append(("interpolated_nearest_successful_longer_horizon", nearest_longer))
        warmstarts.extend([("smooth_reference", smooth), ("heuristic", None)])
        min_diag, min_warm, min_attempts = run_boundary_problem(problem, x0, None, warmstarts)
        rows.append(boundary_row("min_alpha", horizon, problem, min_diag, min_warm, min_attempts))
        if bool(min_diag["success"]):
            nearest_longer = {
                "X": np.asarray(min_diag["X"], dtype=float),
                "U": np.asarray(min_diag["U"], dtype=float),
                "alpha_peak": np.asarray(min_diag["alpha_peak"]),
            }
            successful[horizon] = {"problem": problem, "diag": min_diag}
        for alpha_limit in BOUNDARY_FIXED_ALPHA:
            fixed_warmstarts: list[tuple[str, dict[str, np.ndarray] | None]] = []
            if bool(min_diag["success"]):
                fixed_warmstarts.append(
                    (
                        "minimum_alpha_solution",
                        {"X": np.asarray(min_diag["X"], dtype=float), "U": np.asarray(min_diag["U"], dtype=float), "alpha_peak": np.asarray(alpha_limit)},
                    )
                )
            if nearest_longer is not None:
                fixed_warmstarts.append(("interpolated_nearest_successful_longer_horizon", nearest_longer))
            fixed_warmstarts.extend([("smooth_reference", smooth), ("heuristic", None)])
            fixed_diag, fixed_warm, fixed_attempts = run_boundary_problem(problem, x0, alpha_limit, fixed_warmstarts)
            rows.append(boundary_row(f"fixed_alpha_{alpha_limit:g}", horizon, problem, fixed_diag, fixed_warm, fixed_attempts))
    rows.sort(key=lambda row: (int(row["horizon"]), str(row["mode"])))
    return rows, successful


class ReferenceTrackingNMPC(DiagnosticCasadiNMPC):
    """Stage 9D-style scaled NMPC that tracks a time-varying planner reference."""

    _counter = 0

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any], variant: dict[str, Any]):
        self.delta_r_penalty = float(variant.get("delta_r_penalty", 2.0e5))
        self.omega_penalty = float(variant.get("omega_penalty", 2.0e5))
        self.theta_ref_weight = float(variant.get("theta_ref_weight", 180.0))
        self.omega_ref_weight = float(variant.get("omega_ref_weight", 18.0))
        self.r_ref_weight = float(variant.get("r_ref_weight", 30.0))
        self.rdot_ref_weight = float(variant.get("rdot_ref_weight", 2.0))
        self.u_ref_weight = float(variant.get("u_ref_weight", 2.0e-3))
        super().__init__(model_params, mpc_params, variant)

    def solve_tracking(
        self,
        state: np.ndarray,
        prev_action: np.ndarray,
        x_ref: np.ndarray,
        u_ref: np.ndarray,
    ) -> dict[str, Any]:
        z0, lbx, ubx = self._tracking_initial_guess_and_bounds(state, x_ref, u_ref)
        n = self.horizon
        p = np.concatenate(
            [
                np.asarray(state, dtype=float),
                np.asarray(prev_action, dtype=float),
                np.array([float(self.model_params["m"]), float(self.model_params["k"]), float(self.model_params["b_r"])], dtype=float),
                np.asarray(x_ref, dtype=float).reshape(-1),
                np.asarray(u_ref, dtype=float).reshape(-1),
            ]
        )
        lbg = [0.0] * 4
        ubg = [0.0] * 4
        for _ in range(n):
            lbg.extend([0.0] * 4)
            ubg.extend([0.0] * 4)
            lbg.extend([-np.inf, -np.inf])
            ubg.extend([0.0, 0.0])
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
            status = safe_status(str(stats.get("return_status", "status_unavailable")))
            iterations = int(stats.get("iter_count", 0))
            objective = finite_float(sol["f"])
            z = np.asarray(sol["x"], dtype=float).reshape(-1)
        except RuntimeError as exc:
            solve_time = time.perf_counter() - start
            status = safe_status(f"RuntimeError: {exc}")
        X, U, S = self._unpack(z)
        S = np.maximum(S, 0.0)
        if success:
            self.last_X = X.copy()
            self.last_U = U.copy()
            self.last_S = S.copy()
        first = self.constraints.clip_action(U[0] if len(U) else np.zeros(2, dtype=float))
        self.last_action = first.copy()
        self.solve_count += 1
        diag = self._tracking_diagnostics(X, U, S, x_ref, u_ref, solve_time, success, status, iterations, objective)
        diag.update({"first_action": first, "X": X, "U": U, "S": S})
        return diag

    def _build_solver(self) -> Any:
        n = self.horizon
        Xv = ca.SX.sym("X", 4, n + 1)
        Uv = ca.SX.sym("U", 2, n)
        Sv = ca.SX.sym("S", n)
        p_len = 4 + 2 + 3 + 4 * (n + 1) + 2 * n
        P = ca.SX.sym("P", p_len)
        X = ca.diag(ca.DM(self.x_scale)) @ Xv
        U = ca.diag(ca.DM(self.u_scale)) @ Uv
        S = self.s_scale * Sv
        x0_param = P[0:4]
        prev_action = P[4:6]
        dyn_params = {"m": P[6], "k": P[7], "b_r": P[8]}
        ref_start = 9
        Xref = ca.reshape(P[ref_start : ref_start + 4 * (n + 1)], 4, n + 1).T
        Uref = ca.reshape(P[ref_start + 4 * (n + 1) :], 2, n).T
        g = [X[:, 0] - x0_param]
        cost = 0
        action_prev = prev_action
        for k in range(n):
            x_next = self._rk4_symbolic(X[:, k], U[:, k], dyn_params)
            g.append(X[:, k + 1] - x_next)
            alpha = (X[1, k + 1] - X[1, k]) / self.prediction_dt
            g.append(alpha - self.constraints.alpha_max - S[k])
            g.append(-alpha - self.constraints.alpha_max - S[k])
            x_err = X[:, k + 1] - Xref[k + 1, :].T
            u_err = U[:, k] - Uref[k, :].T
            delta_r = X[2, k + 1] - float(self.model_params["L0"])
            omega = X[1, k + 1]
            du = U[:, k] - action_prev
            cost += (
                self.theta_ref_weight * x_err[0] ** 2
                + self.omega_ref_weight * x_err[1] ** 2
                + self.r_ref_weight * x_err[2] ** 2
                + self.rdot_ref_weight * x_err[3] ** 2
                + self.u_ref_weight * ca.dot(u_err, u_err)
                + 1.0e-3 * ca.dot(du, du)
                + self.alpha_rho_l1 * S[k]
                + self.alpha_rho_l2 * S[k] ** 2
                + self.delta_r_penalty * ca.fmax(0, ca.fabs(delta_r) - self.constraints.delta_r_max) ** 2
                + self.omega_penalty * ca.fmax(0, ca.fabs(omega) - self.constraints.omega_max) ** 2
            )
            action_prev = U[:, k]
        terminal_err = X[:, n] - Xref[n, :].T
        cost += self.theta_ref_weight * terminal_err[0] ** 2 + self.omega_ref_weight * terminal_err[1] ** 2
        cost = cost / 1000.0
        z = ca.vertcat(ca.reshape(Xv, -1, 1), ca.reshape(Uv, -1, 1), Sv)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": 100,
            "ipopt.tol": 1.0e-4,
            "ipopt.acceptable_tol": 1.0e-3,
        }
        ReferenceTrackingNMPC._counter += 1
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", self.name)
        return ca.nlpsol(f"stage9h_tracker_{safe_name}_{ReferenceTrackingNMPC._counter}", "ipopt", nlp, opts)

    def _tracking_initial_guess_and_bounds(
        self,
        state: np.ndarray,
        x_ref: np.ndarray,
        u_ref: np.ndarray,
    ) -> tuple[np.ndarray, list[float], list[float]]:
        n = self.horizon
        if self.last_U is not None:
            U = np.vstack([self.last_U[1:], self.last_U[-1:]])
        else:
            U = np.asarray(u_ref, dtype=float).copy()
        U = np.clip(U, [-self.constraints.F_tan_max, -self.constraints.F_rad_max], [self.constraints.F_tan_max, self.constraints.F_rad_max])
        X = np.asarray(x_ref, dtype=float).copy()
        X[0] = np.asarray(state, dtype=float)
        S = np.maximum(0.0, self._slack_from_trajectory(X))
        z0 = self._pack(X, U, S)
        x_l = [-np.inf] * (4 * (n + 1))
        x_u = [np.inf] * (4 * (n + 1))
        for k in range(n + 1):
            x_l[4 * k + 2] = 1.0e-6 / self.x_scale[2]
        u_l = [-1.0, -1.0] * n
        u_u = [1.0, 1.0] * n
        s_l = [0.0] * n
        s_u = [np.inf] * n
        return z0, x_l + u_l + s_l, x_u + u_u + s_u

    def _tracking_diagnostics(
        self,
        X: np.ndarray,
        U: np.ndarray,
        S: np.ndarray,
        x_ref: np.ndarray,
        u_ref: np.ndarray,
        solve_time: float,
        success: bool,
        status: str,
        iterations: int,
        objective: float,
    ) -> dict[str, Any]:
        residuals = []
        violations = []
        for k, action in enumerate(U):
            dyn_next = step_dynamics(X[k], self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            residuals.append(np.abs(X[k + 1] - dyn_next))
            alpha = (float(X[k + 1, 1]) - float(X[k, 1])) / self.prediction_dt
            delta_r = float(X[k + 1, 2] - self.model_params["L0"])
            slack = float(S[k]) if k < len(S) else 0.0
            violations.extend(
                [
                    max(0.0, abs(alpha) - self.constraints.alpha_max - slack),
                    max(0.0, abs(float(X[k + 1, 1])) - self.constraints.omega_max),
                    max(0.0, abs(delta_r) - self.constraints.delta_r_max),
                    max(0.0, abs(float(action[0])) - self.constraints.F_tan_max),
                    max(0.0, abs(float(action[1])) - self.constraints.F_rad_max),
                ]
            )
        track_err = np.linalg.norm(np.asarray(X, dtype=float)[:, :2] - np.asarray(x_ref, dtype=float)[:, :2], axis=1)
        return {
            "success": bool(success),
            "solve_time": float(solve_time),
            "iterations": int(iterations),
            "status": str(status),
            "failure_reason": "" if success else str(status),
            "objective": objective,
            "dynamics_residual_max": _finite_max(np.asarray(residuals).reshape(-1) if residuals else np.array([])),
            "constraint_violation_max": _finite_max(np.asarray(violations, dtype=float)),
            "alpha_slack_mean": _finite_mean(S),
            "alpha_slack_max": _finite_max(S),
            "tracking_error_mean": _finite_mean(track_err),
            "tracking_error_max": _finite_max(track_err),
            "first_F_tan": float(U[0, 0]) if len(U) else np.nan,
            "first_F_rad": float(U[0, 1]) if len(U) else np.nan,
        }


def tracker_variant(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "horizon": 18,
        "alpha": True,
        "rho_l1": 100.0,
        "rho_l2": 1.0e-2,
        "warmstart": "shift",
        "scaled": True,
        "delta_r_penalty": 2.0e5,
        "omega_penalty": 2.0e5,
    }


def sample_reference(plan_X: np.ndarray, plan_U: np.ndarray, plan_dt: float, start_time: float, horizon: int, dt: float) -> tuple[np.ndarray, np.ndarray]:
    state_times = np.arange(len(plan_X), dtype=float) * plan_dt
    action_times = np.arange(len(plan_U), dtype=float) * plan_dt
    query_x = np.clip(start_time + np.arange(horizon + 1, dtype=float) * dt, state_times[0], state_times[-1])
    query_u = np.clip(start_time + np.arange(horizon, dtype=float) * dt, action_times[0], action_times[-1] if len(action_times) else 0.0)
    x_ref = np.column_stack([np.interp(query_x, state_times, plan_X[:, j]) for j in range(4)])
    if len(plan_U):
        u_ref = np.column_stack([np.interp(query_u, action_times, plan_U[:, j]) for j in range(2)])
    else:
        u_ref = np.zeros((horizon, 2), dtype=float)
    return x_ref, u_ref


def solve_episode_planner(cfg: dict[str, Any], alpha_limit: float) -> dict[str, Any]:
    true_params = cfg["true_params"]
    x0 = initial_state(true_params)
    problem = FastAlphaFrontierProblem(true_params, cfg["mpc_params"], 60)
    smooth = smooth_reference(problem, x0)
    warmstarts = [("smooth_reference", smooth), ("heuristic", None)]
    diag, warm, attempts = run_boundary_problem(problem, x0, alpha_limit, warmstarts)
    diag["accepted_warmstart"] = warm
    diag["warm_start_attempts"] = "; ".join(attempts)
    diag["planner_horizon"] = 60
    diag["planned_crossing_time"] = 60 * problem.prediction_dt
    diag["planner_alpha_limit"] = alpha_limit
    return diag


def run_planner_tracker_condition(method: str, condition: str, seed: int, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    start_runtime = time.perf_counter()
    true_params = cfg["true_params"]
    target = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    target_crossing = target + CROSSING_MARGIN
    env = Spring2DEnv(true_params)
    obs = env.reset()
    planner_diag = solve_episode_planner(cfg, PLANNER_ALPHA_LIMIT)
    rows: list[dict[str, Any]] = []
    if not bool(planner_diag["success"]):
        initial = env.get_history()[-1]
        row = dict(initial)
        row.update(
            {
                "alpha_step": 0.0,
                "theta_target_final": target,
                "theta_crossing_target": target_crossing,
                "planner_success": False,
                "planner_status": str(planner_diag["status"]),
                "tracker_solver_success": False,
                "tracker_solver_failure": False,
                "fallback_used": False,
            }
        )
        return [row], time.perf_counter() - start_runtime
    plan_X = np.asarray(planner_diag["X"], dtype=float)
    plan_U = np.asarray(planner_diag["U"], dtype=float)
    plan_dt = float(cfg["mpc_params"].get("solver", {}).get("prediction_dt", true_params["dt"]))
    tracker = ReferenceTrackingNMPC(true_params, cfg["mpc_params"], tracker_variant(method))
    fallback_cem = CEMAdaptiveMPC(true_params, cfg["mpc_params"])
    fallback_cem.reset()
    previous_action = np.zeros(2, dtype=float)
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    steps = 0

    def append_row(alpha_step: float, action: np.ndarray, diag: dict[str, Any] | None, x_ref_now: np.ndarray, u_ref_now: np.ndarray, fallback_used: bool) -> None:
        hist = dict(env.get_history()[-1])
        x_true = np.array([hist["theta"], hist["omega"], hist["r"], hist["r_dot"]], dtype=float)
        hist.update(
            {
                "alpha_step": float(alpha_step),
                "theta_target_final": target,
                "theta_crossing_target": target_crossing,
                "planner_success": bool(planner_diag["success"]),
                "planner_status": str(planner_diag["status"]),
                "planner_solve_time_s": finite_float(planner_diag["solve_time_s"]),
                "planner_iterations": int(planner_diag["iterations"]),
                "planner_alpha_peak": finite_float(planner_diag["alpha_abs_max"]),
                "planned_crossing_time": finite_float(planner_diag["planned_crossing_time"]),
                "planner_terminal_crossing_margin_deg": finite_float(planner_diag["terminal_crossing_margin_deg"]),
                "planner_F_tan_margin": finite_float(planner_diag["F_tan_margin"]),
                "planner_F_rad_margin": finite_float(planner_diag["F_rad_margin"]),
                "planner_delta_r_margin": finite_float(planner_diag["delta_r_margin"]),
                "planner_omega_margin": finite_float(planner_diag["omega_margin"]),
                "tracker_solver_success": bool(diag.get("success", False)) if diag else False,
                "tracker_solver_failure": not bool(diag.get("success", True)) if diag else False,
                "tracker_status": str(diag.get("status", "")) if diag else "",
                "tracker_solve_time_s": finite_float(diag.get("solve_time", np.nan)) if diag else np.nan,
                "tracker_iterations": int(diag.get("iterations", 0)) if diag else 0,
                "tracker_objective": finite_float(diag.get("objective", np.nan)) if diag else np.nan,
                "tracker_alpha_slack_mean": finite_float(diag.get("alpha_slack_mean", np.nan)) if diag else np.nan,
                "tracker_alpha_slack_max": finite_float(diag.get("alpha_slack_max", np.nan)) if diag else np.nan,
                "tracking_error": float(np.linalg.norm(x_true[:2] - np.asarray(x_ref_now, dtype=float)[:2])),
                "theta_ref": float(x_ref_now[0]),
                "omega_ref": float(x_ref_now[1]),
                "r_ref": float(x_ref_now[2]),
                "r_dot_ref": float(x_ref_now[3]),
                "F_tan_ref": float(u_ref_now[0]),
                "F_rad_ref": float(u_ref_now[1]),
                "fallback_used": bool(fallback_used),
                "F_tan": float(action[0]),
                "F_rad": float(action[1]),
            }
        )
        rows.append(hist)

    append_row(0.0, np.zeros(2, dtype=float), None, plan_X[0], plan_U[0], False)
    while not env.is_done() and steps < max_steps:
        t_now = float(env.get_history()[-1]["t"])
        state = observation_to_state(obs)
        x_ref, u_ref = sample_reference(plan_X, plan_U, plan_dt, t_now, tracker.horizon, tracker.prediction_dt)
        diag = tracker.solve_tracking(state, previous_action, x_ref, u_ref)
        fallback_used = False
        if bool(diag["success"]):
            action = np.asarray(diag["first_action"], dtype=float)
        elif method.endswith("_with_cem_fallback"):
            action = fallback_cem.act(obs)
            fallback_used = True
        else:
            action = np.asarray(diag["first_action"], dtype=float)
        action = tracker.constraints.clip_action(action)
        for _ in range(hold_steps):
            prev = env.get_history()[-1]
            obs = env.step(action)
            current = env.get_history()[-1]
            alpha_step = (float(current["omega"]) - float(prev["omega"])) / float(true_params["dt"])
            steps += 1
            append_row(alpha_step, action, diag, x_ref[0], u_ref[0], fallback_used)
            if env.is_done() or steps >= max_steps:
                break
        previous_action = action.copy()
    return rows, time.perf_counter() - start_runtime


def summarize_tracker_rows(method: str, condition: str, seed: int, phase: str, rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    true_params = cfg["true_params"]
    constraints = cfg["mpc_params"].get("constraints", {})
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))
    target = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    theta = _series(rows, "theta")
    t = _series(rows, "t")
    alpha_abs = np.abs(_series(rows, "alpha_step"))
    alpha_sev = np.maximum(0.0, alpha_abs - alpha_max)
    omega_abs = np.abs(_series(rows, "omega"))
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    action = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_mag = np.linalg.norm(action, axis=1)
    action_tv = np.nansum(np.linalg.norm(np.diff(action, axis=0), axis=1)) if len(action) > 1 else 0.0
    decisions = [row for row in rows if str(row.get("tracker_status", ""))]
    crossed = bool(np.any(theta >= target))
    crossing_indices = np.flatnonzero(theta >= target)
    crossing_time = float(t[crossing_indices[0]]) if len(crossing_indices) and len(t) else np.nan
    return {
        "phase": phase,
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "target_crossed": crossed,
        "target_reached": crossed,
        "actual_crossing_time": crossing_time,
        "T_reach": crossing_time,
        "final_theta_deg": float(np.degrees(theta[-1])) if len(theta) else np.nan,
        "final_theta_error_signed_deg": float(np.degrees(theta[-1] - target)) if len(theta) else np.nan,
        "planner_success": bool(rows[-1].get("planner_success", False)),
        "planner_status": str(rows[-1].get("planner_status", "")),
        "planner_solve_time_s": finite_float(rows[-1].get("planner_solve_time_s", np.nan)),
        "planner_iterations": int(rows[-1].get("planner_iterations", 0)),
        "planned_alpha_peak": finite_float(rows[-1].get("planner_alpha_peak", np.nan)),
        "planned_crossing_time": finite_float(rows[-1].get("planned_crossing_time", np.nan)),
        "planner_terminal_crossing_margin_deg": finite_float(rows[-1].get("planner_terminal_crossing_margin_deg", np.nan)),
        "planner_F_tan_margin": finite_float(rows[-1].get("planner_F_tan_margin", np.nan)),
        "planner_F_rad_margin": finite_float(rows[-1].get("planner_F_rad_margin", np.nan)),
        "planner_delta_r_margin": finite_float(rows[-1].get("planner_delta_r_margin", np.nan)),
        "planner_omega_margin": finite_float(rows[-1].get("planner_omega_margin", np.nan)),
        "tracker_solver_success_count": int(sum(bool(row.get("tracker_solver_success", False)) for row in decisions)),
        "tracker_solver_failure_count": int(sum(bool(row.get("tracker_solver_failure", False)) for row in decisions)),
        "tracker_solver_failure_rate": float(sum(bool(row.get("tracker_solver_failure", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "fallback_count": int(sum(bool(row.get("fallback_used", False)) for row in decisions)),
        "fallback_rate": float(sum(bool(row.get("fallback_used", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "tracker_solve_time_mean": _finite_mean(_series(decisions, "tracker_solve_time_s")) if decisions else np.nan,
        "tracker_solve_time_max": _finite_max(_series(decisions, "tracker_solve_time_s")) if decisions else np.nan,
        "tracking_error_mean": _finite_mean(_series(rows, "tracking_error")),
        "tracking_error_max": _finite_max(_series(rows, "tracking_error")),
        "alpha_abs_mean": _finite_mean(alpha_abs),
        "alpha_abs_p95": _finite_percentile(alpha_abs, 95),
        "alpha_abs_p99": _finite_percentile(alpha_abs, 99),
        "alpha_abs_max": _finite_max(alpha_abs),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "alpha_integrated_violation": float(np.sum(alpha_sev) * dt),
        "alpha_clipped_max": _clipped_max_excluding_one(alpha_sev),
        "raw_omega_p95": _finite_percentile(omega_abs, 95),
        "raw_omega_max": _finite_max(omega_abs),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_violation_max": _finite_max(delta_r_sev),
        "force_violation_count": int(np.count_nonzero(F_tan_sev > 0.0) + np.count_nonzero(F_rad_sev > 0.0)),
        "force_violation_max": max(_finite_max(F_tan_sev), _finite_max(F_rad_sev)),
        "action_magnitude_mean": _finite_mean(action_mag),
        "action_magnitude_max": _finite_max(action_mag),
        "action_total_variation": float(action_tv),
        "runtime_s": float(runtime_s),
    }


def normalize_reference_summary(row: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    out = {
        "phase": row.get("phase", ""),
        "method": row.get("method", ""),
        "condition": row.get("condition", ""),
        "seed": row.get("seed", ""),
        "target_crossed": row.get("target_crossed", row.get("target_reached", False)),
        "target_reached": row.get("target_reached", False),
        "actual_crossing_time": row.get("first_crossing_time", row.get("T_reach", np.nan)),
        "T_reach": row.get("T_reach", np.nan),
        "final_theta_deg": row.get("final_theta_deg", np.nan),
        "final_theta_error_signed_deg": row.get("final_theta_error_signed_deg", np.nan),
        "planner_success": np.nan,
        "planner_status": "",
        "planner_solve_time_s": np.nan,
        "planner_iterations": np.nan,
        "planned_alpha_peak": np.nan,
        "planned_crossing_time": np.nan,
        "planner_terminal_crossing_margin_deg": np.nan,
        "planner_F_tan_margin": np.nan,
        "planner_F_rad_margin": np.nan,
        "planner_delta_r_margin": np.nan,
        "planner_omega_margin": np.nan,
        "tracker_solver_success_count": row.get("solver_success_count", np.nan),
        "tracker_solver_failure_count": row.get("solver_failure_count", np.nan),
        "tracker_solver_failure_rate": row.get("solver_failure_rate", np.nan),
        "fallback_count": row.get("fallback_count", np.nan),
        "fallback_rate": row.get("fallback_rate", np.nan),
        "tracker_solve_time_mean": row.get("solve_time_mean", np.nan),
        "tracker_solve_time_max": row.get("solve_time_max", np.nan),
        "tracking_error_mean": np.nan,
        "tracking_error_max": np.nan,
        "alpha_abs_mean": np.nan,
        "alpha_abs_p95": np.nan,
        "alpha_abs_p99": np.nan,
        "alpha_abs_max": np.nan,
        "alpha_p95_severity": row.get("alpha_p95_severity", np.nan),
        "alpha_p99_severity": row.get("alpha_p99_severity", np.nan),
        "alpha_max_severity": row.get("alpha_max_severity", np.nan),
        "alpha_violation_duration_s": row.get("alpha_violation_duration_s", np.nan),
        "alpha_integrated_violation": row.get("alpha_integrated_violation", np.nan),
        "alpha_clipped_max": row.get("alpha_clipped_max", np.nan),
        "raw_omega_p95": row.get("raw_omega_p95", np.nan),
        "raw_omega_max": row.get("raw_omega_max", np.nan),
        "delta_r_violation_count": row.get("delta_r_violation_count", np.nan),
        "delta_r_violation_max": row.get("delta_r_violation_max", np.nan),
        "force_violation_count": row.get("force_violation_count", np.nan),
        "force_violation_max": row.get("force_violation_max", np.nan),
        "action_magnitude_mean": row.get("action_magnitude_mean", np.nan),
        "action_magnitude_max": row.get("action_magnitude_max", np.nan),
        "action_total_variation": row.get("action_smoothness", row.get("action_total_variation", np.nan)),
        "runtime_s": runtime_s,
    }
    return out


def run_reference_method(method: str, condition: str, seed: int, phase: str, base_cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    condition_cfg = condition_with_seed(base_cfg, condition, seed)
    if method == "baseline_cem":
        cfg = apply_stage9f_overrides(configure_cem_seeded(base_cfg, method, seed), condition)
        start = time.perf_counter()
        rows = run_condition(condition, condition_cfg, cfg)
    else:
        cfg = apply_stage9f_overrides(configure_nmpc_run(base_cfg, method, seed), condition)
        start = time.perf_counter()
        rows = run_nmpc_condition(method, condition, seed, condition_cfg, cfg)
    runtime_s = time.perf_counter() - start
    summary = summarize_stage9f_rows(method, condition, seed, phase, rows, cfg, runtime_s)
    return normalize_reference_summary(summary, runtime_s), rows


def run_tracker_method(method: str, condition: str, seed: int, phase: str, base_cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = apply_stage9f_overrides(copy.deepcopy(base_cfg), condition)
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    rows, runtime_s = run_planner_tracker_condition(method, condition, seed, cfg)
    return summarize_tracker_rows(method, condition, seed, phase, rows, cfg, runtime_s), rows


def save_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "phase",
        "method",
        "condition",
        "seed",
        "target_crossed",
        "target_reached",
        "actual_crossing_time",
        "T_reach",
        "final_theta_deg",
        "final_theta_error_signed_deg",
        "planner_success",
        "planner_status",
        "planner_solve_time_s",
        "planner_iterations",
        "planned_alpha_peak",
        "planned_crossing_time",
        "planner_terminal_crossing_margin_deg",
        "planner_F_tan_margin",
        "planner_F_rad_margin",
        "planner_delta_r_margin",
        "planner_omega_margin",
        "tracker_solver_success_count",
        "tracker_solver_failure_count",
        "tracker_solver_failure_rate",
        "fallback_count",
        "fallback_rate",
        "tracker_solve_time_mean",
        "tracker_solve_time_max",
        "tracking_error_mean",
        "tracking_error_max",
        "alpha_abs_mean",
        "alpha_abs_p95",
        "alpha_abs_p99",
        "alpha_abs_max",
        "alpha_p95_severity",
        "alpha_p99_severity",
        "alpha_max_severity",
        "alpha_violation_duration_s",
        "alpha_integrated_violation",
        "alpha_clipped_max",
        "raw_omega_p95",
        "raw_omega_max",
        "delta_r_violation_count",
        "delta_r_violation_max",
        "force_violation_count",
        "force_violation_max",
        "action_magnitude_mean",
        "action_magnitude_max",
        "action_total_variation",
        "runtime_s",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def save_boundary(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "section",
        "mode",
        "horizon",
        "crossing_time_s",
        "fixed_alpha_limit",
        "success",
        "status",
        "iterations",
        "solve_time_s",
        "alpha_peak",
        "terminal_theta_deg",
        "terminal_omega",
        "terminal_crossing_margin_deg",
        "F_tan_margin",
        "F_rad_margin",
        "delta_r_margin",
        "omega_margin",
        "action_total_variation",
        "warm_start",
        "warm_start_attempts",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def aggregate(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    for method in sorted({str(r["method"]) for r in rows}):
        for condition in sorted({str(r["condition"]) for r in rows if str(r["method"]) == method}):
            group = [r for r in rows if str(r["method"]) == method and str(r["condition"]) == condition]
            out[(method, condition)] = {
                "n": float(len(group)),
                "cross_success": float(sum(bool(r.get("target_crossed", False)) for r in group)),
                "alpha_max_avg": _finite_mean(_series(group, "alpha_max_severity")),
                "alpha_p95_avg": _finite_mean(_series(group, "alpha_p95_severity")),
                "omega_max_avg": _finite_mean(_series(group, "raw_omega_max")),
                "tracker_fail_avg": _finite_mean(_series(group, "tracker_solver_failure_rate")),
                "fallback_avg": _finite_mean(_series(group, "fallback_rate")),
                "tracking_error_avg": _finite_mean(_series(group, "tracking_error_mean")),
            }
    return out


def save_plots(summary_rows: list[dict[str, Any]], boundary_rows: list[dict[str, Any]], all_runs: dict[tuple[str, str, int], list[dict[str, Any]]], out_dir: Path) -> None:
    fig_dir = out_dir / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    min_rows = [r for r in boundary_rows if r["mode"] == "min_alpha" and bool(r["success"])]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    if min_rows:
        ax.plot([r["crossing_time_s"] for r in min_rows], [r["alpha_peak"] for r in min_rows], marker="o", label="min alpha")
    fixed3 = [r for r in boundary_rows if r["mode"] == "fixed_alpha_3"]
    ax.scatter([r["crossing_time_s"] for r in fixed3], [3.0 if bool(r["success"]) else np.nan for r in fixed3], marker="s", label="fixed alpha 3 feasible")
    ax.axhline(3.0, color="black", linestyle=":", linewidth=1.0)
    ax.set_xlabel("crossing time [s]")
    ax.set_ylabel("alpha [rad/s^2]")
    ax.set_title("Stage 9H low-alpha boundary")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "part_a_crossing_boundary.png")
    plt.close(fig)

    phase1 = [r for r in summary_rows if r["condition"] == "initial_theta_offset"]
    methods = list(dict.fromkeys(str(r["method"]) for r in phase1))
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 7.0))
    success = [sum(bool(r.get("target_crossed", False)) for r in phase1 if r["method"] == method) for method in methods]
    alpha_max = [_finite_mean(_series([r for r in phase1 if r["method"] == method], "alpha_max_severity")) for method in methods]
    axes[0].bar(methods, success)
    axes[0].set_ylabel("crossed count / 3")
    axes[0].set_ylim(0, 3)
    axes[1].bar(methods, alpha_max)
    axes[1].axhline(STAGE9F_BASELINE_ALPHA_MAX, color="black", linestyle=":", linewidth=1.0, label="Stage9F baseline ref")
    axes[1].set_ylabel("alpha max severity")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "phase1_success_alpha_summary.png")
    plt.close(fig)

    success_boundary = [r for r in boundary_rows if bool(r["success"])]
    if success_boundary:
        fig, ax = plt.subplots(figsize=(8.0, 4.2))
        labels = [f"{r['mode']}\nN={r['horizon']}" for r in success_boundary]
        x = np.arange(len(labels))
        ax.plot(x, [r["F_rad_margin"] for r in success_boundary], marker="o", label="F_rad margin")
        ax.plot(x, [r["delta_r_margin"] for r in success_boundary], marker="o", label="delta_r margin")
        ax.plot(x, [r["omega_margin"] for r in success_boundary], marker="o", label="omega margin")
        ax.axhline(0.0, color="black", linestyle=":", linewidth=1.0)
        ax.set_xticks(x, labels=labels, rotation=35, ha="right")
        ax.set_ylabel("minimum margin")
        ax.set_title("Planner constraint margins for accepted boundary solves")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / "planner_constraint_margins.png")
        plt.close(fig)

    tracker_rows = [r for r in summary_rows if str(r["method"]) in TRACKER_METHODS]
    if tracker_rows:
        fig, ax = plt.subplots(figsize=(8.0, 4.2))
        methods = list(dict.fromkeys(str(r["method"]) for r in tracker_rows))
        x = np.arange(len(methods))
        planner_times = [_finite_mean(_series([r for r in tracker_rows if r["method"] == method], "planner_solve_time_s")) for method in methods]
        tracker_times = [_finite_mean(_series([r for r in tracker_rows if r["method"] == method], "tracker_solve_time_mean")) for method in methods]
        width = 0.38
        ax.bar(x - width / 2, planner_times, width, label="planner solve")
        ax.bar(x + width / 2, tracker_times, width, label="tracker solve mean")
        ax.set_xticks(x, labels=methods, rotation=25, ha="right")
        ax.set_ylabel("solve time [s]")
        ax.set_title("Planner and tracker solve time")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / "planner_tracker_solve_time.png")
        plt.close(fig)

    for key, rows in all_runs.items():
        method, condition, seed = key
        if condition != "initial_theta_offset" or method not in TRACKER_METHODS:
            continue
        t = _series(rows, "t")
        fig, axes = plt.subplots(5, 1, figsize=(8.5, 10.0), sharex=True)
        axes[0].plot(t, np.degrees(_series(rows, "theta")), label="executed")
        axes[0].plot(t, np.degrees(_series(rows, "theta_ref")), linestyle="--", label="planner ref")
        axes[0].axhline(np.degrees(float(rows[-1]["theta_crossing_target"])), color="black", linestyle=":", linewidth=1.0, label="crossing")
        axes[1].plot(t, _series(rows, "omega"), label="executed")
        axes[1].plot(t, _series(rows, "omega_ref"), linestyle="--", label="planner ref")
        axes[2].plot(t, np.abs(_series(rows, "alpha_step")), label="executed |alpha|")
        axes[2].axhline(3.0, color="black", linestyle=":", linewidth=1.0)
        axes[3].plot(t, _series(rows, "F_tan"), label="F_tan")
        axes[3].plot(t, _series(rows, "F_rad"), label="F_rad")
        axes[3].plot(t, _series(rows, "F_tan_ref"), linestyle="--", label="F_tan ref")
        axes[4].plot(t, _series(rows, "tracking_error"), label="tracking error")
        labels = ["theta [deg]", "omega", "|alpha|", "action", "track err"]
        for ax, label in zip(axes, labels):
            ax.set_ylabel(label)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
        axes[-1].set_xlabel("time [s]")
        fig.tight_layout()
        fig.savefig(fig_dir / f"{method}_{condition}_seed{seed}_planner_tracking.png")
        plt.close(fig)


def save_report(output_root: Path, boundary_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], phase2_skipped_reason: str | None) -> None:
    agg = aggregate(summary_rows)
    phase1_oracle = agg.get(("oracle_planner_nmpc_tracker", "initial_theta_offset"), {})
    shortest_fixed3 = min(
        (r for r in boundary_rows if r["mode"] == "fixed_alpha_3" and bool(r["success"])),
        key=lambda r: int(r["horizon"]),
        default=None,
    )
    shortest_min = min(
        (r for r in boundary_rows if r["mode"] == "min_alpha" and bool(r["success"])),
        key=lambda r: int(r["horizon"]),
        default=None,
    )
    with (output_root / "stage9h_report.md").open("w") as f:
        f.write("# Stage 9H Planner + Tracker\n\n")
        f.write("This stage tests a hierarchical long-horizon crossing planner plus short-horizon NMPC tracker. It does not change Spring2D dynamics, baseline CEM, Stage 9D/9F results, or the target crossing success definition.\n\n")
        f.write("## Part A Boundary\n\n")
        f.write("| mode | N | time_s | success | alpha_peak | warm_start | status |\n")
        f.write("|---|---:|---:|---:|---:|---|---|\n")
        for row in boundary_rows:
            if row["mode"] not in {"min_alpha", "fixed_alpha_3", "fixed_alpha_4"}:
                continue
            f.write(
                f"| {row['mode']} | {row['horizon']} | {fmt(row['crossing_time_s'])} | {row['success']} | "
                f"{fmt(row['alpha_peak'])} | {row['warm_start']} | {row['status']} |\n"
            )
        f.write("\n")
        f.write("Multiple warm starts were attempted; a single IPOPT failure was not treated as physical infeasibility.\n\n")
        f.write("## Phase 1 Aggregate\n\n")
        f.write("| method | condition | crossed | alpha_p95 | alpha_max | tracker_fail | fallback | tracking_error |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
        for (method, condition), vals in sorted(agg.items()):
            if condition != "initial_theta_offset":
                continue
            f.write(
                f"| {method} | {condition} | {int(vals['cross_success'])}/{int(vals['n'])} | "
                f"{fmt(vals['alpha_p95_avg'])} | {fmt(vals['alpha_max_avg'])} | {fmt(vals['tracker_fail_avg'])} | "
                f"{fmt(vals['fallback_avg'])} | {fmt(vals['tracking_error_avg'])} |\n"
            )
        if phase2_skipped_reason:
            f.write(f"\nPhase 2 skipped: {phase2_skipped_reason}\n")
        phase2_rows = [row for row in summary_rows if str(row.get("phase", "")).startswith("phase2")]
        if phase2_rows:
            f.write("\n## Phase 2 Aggregate\n\n")
            f.write("| method | condition | crossed | alpha_p95 | alpha_max | tracker_fail | fallback | tracking_error |\n")
            f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
            for (method, condition), vals in sorted(agg.items()):
                if condition == "initial_theta_offset":
                    continue
                f.write(
                    f"| {method} | {condition} | {int(vals['cross_success'])}/{int(vals['n'])} | "
                    f"{fmt(vals['alpha_p95_avg'])} | {fmt(vals['alpha_max_avg'])} | {fmt(vals['tracker_fail_avg'])} | "
                    f"{fmt(vals['fallback_avg'])} | {fmt(vals['tracking_error_avg'])} |\n"
                )
            f.write(
                "\nNote: oracle planner/tracker rows use true state and true physical parameters for architecture validation. "
                "The parameter_mismatch rows mainly stress the reference adaptive methods; adaptive planner/tracker integration is not included here.\n"
            )
        f.write("\n## Required Answers\n\n")
        if shortest_fixed3 is not None:
            f.write(f"1. The shortest practically feasible alpha<=3 crossing horizon found in Part A is N={shortest_fixed3['horizon']} ({fmt(shortest_fixed3['crossing_time_s'])} s). ")
        elif shortest_min is not None:
            f.write(f"1. The shortest accepted minimum-alpha crossing horizon is N={shortest_min['horizon']} ({fmt(shortest_min['crossing_time_s'])} s), but alpha<=3 was not solver-confirmed. ")
        else:
            f.write("1. Part A did not find a solver-confirmed low-alpha crossing horizon. ")
        if shortest_fixed3 is not None and int(shortest_fixed3["horizon"]) < 60:
            f.write("The refined alpha<=3 boundary is below N=60, but it still requires a long crossing horizon relative to the short N=18 tracker.\n")
        else:
            f.write("The practical boundary remains near N=60 in this tested set.\n")
        crossed = int(phase1_oracle.get("cross_success", 0.0))
        total = int(phase1_oracle.get("n", 0.0))
        f.write(f"2. The oracle planner + tracker crossed under initial_theta_offset in {crossed}/{total} runs.\n")
        f.write(f"3. Actual alpha relative to the plan: phase-1 oracle alpha max severity average was {fmt(phase1_oracle.get('alpha_max_avg', np.nan))}; planned hard alpha limit was {PLANNER_ALPHA_LIMIT:g} rad/s^2.\n")
        if np.isfinite(phase1_oracle.get("alpha_max_avg", np.nan)) and float(phase1_oracle["alpha_max_avg"]) < STAGE9F_BASELINE_ALPHA_MAX:
            f.write("4. It avoided Stage 9F-like alpha spikes in the aggregate metric used here.\n")
        else:
            f.write("4. It did not clearly avoid Stage 9F-like alpha spikes; inspect trajectories before carrying forward.\n")
        f.write(f"5. Tracker failure average for oracle planner + tracker was {fmt(phase1_oracle.get('tracker_fail_avg', np.nan))}; fallback average was {fmt(phase1_oracle.get('fallback_avg', np.nan))}.\n")
        if phase1_oracle.get("tracking_error_avg", np.nan) and np.isfinite(phase1_oracle.get("tracking_error_avg", np.nan)):
            f.write("6. One-shot planning is plausible only if tracking error stays bounded; this run logs tracking error but does not prove replanning is unnecessary.\n")
        else:
            f.write("6. One-shot planning was not sufficient to judge replanning need.\n")
        f.write("7. Adaptive state/parameter integration was not mixed into the oracle architecture in this script; it remains a gated Part C follow-up after oracle evidence is accepted.\n")
        if crossed >= 2:
            f.write("8. The single-link architecture is a candidate for final adaptive ablation before linked-rods preparation, but not a formal safety result.\n")
        else:
            f.write("8. The single-link architecture is not ready for linked-rods preparation from this run alone.\n")
        f.write("\nNo formal safety guarantee is claimed.\n")


def run(output_root: Path, config_path: Path) -> None:
    try:
        _ = ca.__version__
    except Exception as exc:
        raise RuntimeError("CasADi is required for Stage 9H.") from exc
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    boundary_rows, _ = run_part_a_boundary(base_cfg)
    save_boundary(output_root / "stage9h_boundary_summary.csv", boundary_rows)
    summary_rows: list[dict[str, Any]] = []
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]] = {}

    def run_one(method: str, condition: str, seed: int, phase: str) -> None:
        print(f"[stage9h] running {phase} {method}/{condition}/seed{seed}", flush=True)
        if method in REFERENCE_METHODS:
            summary, rows = run_reference_method(method, condition, seed, phase, base_cfg)
        else:
            summary, rows = run_tracker_method(method, condition, seed, phase, base_cfg)
        summary_rows.append(summary)
        all_runs[(method, condition, int(seed))] = rows
        print(
            f"[stage9h] {method}/{condition}/seed{seed}: crossed={summary['target_crossed']}, "
            f"alpha_max={fmt(summary.get('alpha_max_severity', np.nan))}, "
            f"tracker_fail={fmt(summary.get('tracker_solver_failure_rate', np.nan))}",
            flush=True,
        )

    for seed in SEEDS:
        for method in METHODS:
            run_one(method, "initial_theta_offset", seed, "phase1_initial_theta_offset")
    agg = aggregate(summary_rows)
    oracle = agg.get(("oracle_planner_nmpc_tracker", "initial_theta_offset"), {})
    phase2_skipped_reason: str | None = None
    if int(oracle.get("cross_success", 0.0)) >= 2:
        for condition in PHASE2_CONDITIONS:
            for seed in SEEDS:
                for method in METHODS:
                    run_one(method, condition, seed, "phase2_regression")
    else:
        phase2_skipped_reason = "oracle planner + tracker did not reach >=2/3 crossing success in Phase 1"
    save_summary(output_root / "stage9h_summary.csv", summary_rows)
    save_plots(summary_rows, boundary_rows, all_runs, output_root)
    save_report(output_root, boundary_rows, summary_rows, phase2_skipped_reason)
    print(f"[stage9h] summary: {output_root / 'stage9h_summary.csv'}", flush=True)
    print(f"[stage9h] report : {output_root / 'stage9h_report.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
