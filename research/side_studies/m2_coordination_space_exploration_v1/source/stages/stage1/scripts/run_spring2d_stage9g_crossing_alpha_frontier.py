"""Stage 9G crossing-alpha feasibility frontier for Spring2D.

This script is an offline oracle diagnosis.  It does not implement or tune an
online controller.
"""

from __future__ import annotations

import argparse
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

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage9b_nmpc_diagnosis import DiagnosticCasadiNMPC
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.constraints import Spring2DMPCConstraints


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9g_crossing_alpha_frontier"
CROSSING_MARGIN = float(np.deg2rad(0.1))
HORIZONS = [18, 24, 30, 40, 60]
FIXED_ALPHA_LIMITS = [3.0, 4.0, 5.0, 7.0, 10.0]
INITIAL_THETA = 0.02
INITIAL_OMEGA = -0.15

STAGE_COMPARISONS = {
    "stage9d_nmpc_base_no_crossing": 3.138,
    "stage9f_baseline_cem_crossing": 9.142,
    "stage9f_weighted_crossing": 27.07,
    "stage9f_lexicographic_crossing": 72.25,
}


def finite_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return out if np.isfinite(out) else float("nan")


def safe_status(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text)).strip()
    return compact[:180]


def fmt(value: Any, digits: int = 4) -> str:
    value_f = finite_float(value)
    if not np.isfinite(value_f):
        return "nan"
    return f"{value_f:.{digits}g}"


class AlphaFrontierProblem:
    """Scaled multiple-shooting NLP minimizing peak alpha for terminal crossing."""

    _counter = 0

    def __init__(self, true_params: dict[str, Any], mpc_params: dict[str, Any], horizon: int):
        self.model_params = dict(true_params)
        self.mpc_params = dict(mpc_params)
        self.horizon = int(horizon)
        self.prediction_dt = float(mpc_params.get("solver", {}).get("prediction_dt", true_params["dt"]))
        self.target_theta = float(mpc_params.get("target_theta", true_params["theta_target"]))
        self.target_crossing = self.target_theta + CROSSING_MARGIN
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.prediction_dt,
        )
        self.nominal_cfg = dict(mpc_params.get("nominal_policy", {}))
        self.x_scale = np.array([np.pi, 2.0, max(float(true_params["L0"]), 1.0), 2.0], dtype=float)
        self.u_scale = np.array([self.constraints.F_tan_max, self.constraints.F_rad_max], dtype=float)
        self.alpha_scale = 10.0
        self._dyn = DiagnosticCasadiNMPC.__new__(DiagnosticCasadiNMPC)
        self._dyn.model_params = self.model_params
        self._dyn.prediction_dt = self.prediction_dt
        self._dyn.constraints = self.constraints
        AlphaFrontierProblem._counter += 1
        self.solver = self._build_solver(AlphaFrontierProblem._counter)

    def solve(
        self,
        x0: np.ndarray,
        warmstart: dict[str, np.ndarray] | None = None,
        fixed_alpha_limit: float | None = None,
        warmstart_label: str = "heuristic",
    ) -> dict[str, Any]:
        z0, lbx, ubx, lbg, ubg = self._initial_guess_and_bounds(x0, warmstart, fixed_alpha_limit)
        p = np.array(
            [
                float(x0[0]),
                float(x0[1]),
                float(x0[2]),
                float(x0[3]),
                float(self.target_crossing),
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
            status = safe_status(str(stats.get("return_status", "status_unavailable")))
            iterations = int(stats.get("iter_count", 0))
            objective = finite_float(sol["f"])
            z = np.asarray(sol["x"], dtype=float).reshape(-1)
        except RuntimeError as exc:
            solve_time = time.perf_counter() - start
            status = safe_status(f"RuntimeError: {exc}")
        X, U, alpha_peak = self._unpack(z)
        diag = self._diagnostics(X, U, alpha_peak, success, status, solve_time, iterations, objective)
        diag.update(
            {
                "X": X,
                "U": U,
                "alpha_peak": float(alpha_peak),
                "fixed_alpha_limit": np.nan if fixed_alpha_limit is None else float(fixed_alpha_limit),
                "warm_start": str(warmstart_label),
            }
        )
        return diag

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
                du = U[:, k] - U[:, k - 1]
                rate_cost += ca.dot(du, du)
        terminal_omega = X[1, n]
        g.append(target_crossing - X[0, n])
        cost = alpha_peak + 1.0e-7 * action_cost + 1.0e-7 * rate_cost + 1.0e-4 * terminal_omega**2
        z = ca.vertcat(ca.reshape(Xv, -1, 1), ca.reshape(Uv, -1, 1), Av)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": 800,
            "ipopt.tol": 1.0e-6,
            "ipopt.acceptable_tol": 1.0e-5,
            "ipopt.constr_viol_tol": 1.0e-6,
        }
        return ca.nlpsol(f"stage9g_alpha_frontier_{counter}", "ipopt", nlp, opts)

    def _rk4_symbolic(self, x: ca.SX, u: ca.SX, dyn_params: dict[str, ca.SX]) -> ca.SX:
        return DiagnosticCasadiNMPC._rk4_symbolic(self._dyn, x, u, dyn_params)

    def _initial_guess_and_bounds(
        self,
        x0: np.ndarray,
        warmstart: dict[str, np.ndarray] | None,
        fixed_alpha_limit: float | None,
    ) -> tuple[np.ndarray, list[float], list[float], list[float], list[float]]:
        n = self.horizon
        if warmstart is not None:
            U = np.asarray(warmstart["U"], dtype=float)
            X = np.asarray(warmstart["X"], dtype=float)
            alpha_guess = finite_float(warmstart.get("alpha_peak", self.constraints.alpha_max))
            U = self._resample_sequence(U, n)
            X = self._resample_states(X, n)
            X[0] = np.asarray(x0, dtype=float)
        else:
            U = self._heuristic_sequence(x0)
            X = self._simulate_guess(x0, U)
            alpha_guess = self._alpha_peak_from_X(X)
        if len(X) != n + 1:
            X = self._simulate_guess(x0, U)
        alpha_guess = max(float(alpha_guess), self._alpha_peak_from_X(X), 0.05)
        z0 = self._pack(X, U, alpha_guess)
        x_l: list[float] = []
        x_u: list[float] = []
        theta_bound = max(abs(float(self.target_crossing)) + 1.0, 4.0)
        for _ in range(n + 1):
            x_l.extend([-theta_bound / self.x_scale[0], -self.constraints.omega_max / self.x_scale[1], (float(self.model_params["L0"]) - self.constraints.delta_r_max) / self.x_scale[2], -np.inf])
            x_u.extend([theta_bound / self.x_scale[0], self.constraints.omega_max / self.x_scale[1], (float(self.model_params["L0"]) + self.constraints.delta_r_max) / self.x_scale[2], np.inf])
        u_l = [-1.0, -1.0] * n
        u_u = [1.0, 1.0] * n
        if fixed_alpha_limit is None:
            a_l = [0.0]
            a_u = [np.inf]
        else:
            fixed_scaled = float(fixed_alpha_limit) / self.alpha_scale
            a_l = [fixed_scaled]
            a_u = [fixed_scaled]
        lbx = x_l + u_l + a_l
        ubx = x_u + u_u + a_u
        lbg = [0.0] * 4
        ubg = [0.0] * 4
        for _ in range(n):
            lbg.extend([0.0] * 4)
            ubg.extend([0.0] * 4)
            lbg.extend([-np.inf, -np.inf])
            ubg.extend([0.0, 0.0])
        lbg.append(-np.inf)
        ubg.append(0.0)
        return z0, lbx, ubx, lbg, ubg

    def _pack(self, X: np.ndarray, U: np.ndarray, alpha_peak: float) -> np.ndarray:
        Xv = np.asarray(X, dtype=float) / self.x_scale
        Uv = np.asarray(U, dtype=float) / self.u_scale
        return np.concatenate([Xv.T.reshape(-1, order="F"), Uv.T.reshape(-1, order="F"), [float(alpha_peak) / self.alpha_scale]])

    def _unpack(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        n = self.horizon
        x_size = 4 * (n + 1)
        u_size = 2 * n
        Xv = np.asarray(z[:x_size], dtype=float).reshape((4, n + 1), order="F").T
        Uv = np.asarray(z[x_size : x_size + u_size], dtype=float).reshape((2, n), order="F").T
        alpha_v = finite_float(z[x_size + u_size]) if len(z) > x_size + u_size else np.nan
        return Xv * self.x_scale, Uv * self.u_scale, max(0.0, alpha_v * self.alpha_scale)

    def _heuristic_sequence(self, state: np.ndarray) -> np.ndarray:
        theta, omega, r, r_dot = np.asarray(state, dtype=float)
        theta_error = self.target_crossing - theta
        kp_theta = float(self.nominal_cfg.get("kp_theta", 7.5))
        kd_omega = float(self.nominal_cfg.get("kd_omega", 1.6))
        radial_kp = float(self.nominal_cfg.get("radial_kp", 60.0))
        radial_kd = float(self.nominal_cfg.get("radial_kd", 8.0))
        taper = np.linspace(1.0, float(self.nominal_cfg.get("terminal_taper", 0.45)), self.horizon)
        U = np.column_stack(
            [
                (kp_theta * theta_error - kd_omega * omega) * taper,
                np.full(self.horizon, -radial_kp * (r - float(self.model_params["L0"])) - radial_kd * r_dot),
            ]
        )
        U[:, 0] = np.clip(U[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        U[:, 1] = np.clip(U[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return U

    def _simulate_guess(self, state: np.ndarray, sequence: np.ndarray) -> np.ndarray:
        X = [np.asarray(state, dtype=float).copy()]
        x = X[0].copy()
        for action in np.asarray(sequence, dtype=float):
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                x = X[-1].copy()
            if not np.all(np.isfinite(x)):
                x = X[-1].copy()
            X.append(x.copy())
        return np.asarray(X, dtype=float)

    def _alpha_peak_from_X(self, X: np.ndarray) -> float:
        if len(X) < 2:
            return 0.0
        return float(np.nanmax(np.abs(np.diff(np.asarray(X)[:, 1]) / self.prediction_dt)))

    def _resample_sequence(self, U: np.ndarray, n: int) -> np.ndarray:
        U = np.asarray(U, dtype=float)
        if len(U) == n:
            return U.copy()
        if len(U) == 0:
            return np.zeros((n, 2), dtype=float)
        src = np.linspace(0.0, 1.0, len(U))
        dst = np.linspace(0.0, 1.0, n)
        return np.column_stack([np.interp(dst, src, U[:, j]) for j in range(2)])

    def _resample_states(self, X: np.ndarray, n: int) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if len(X) == n + 1:
            return X.copy()
        src = np.linspace(0.0, 1.0, len(X))
        dst = np.linspace(0.0, 1.0, n + 1)
        return np.column_stack([np.interp(dst, src, X[:, j]) for j in range(4)])

    def _diagnostics(
        self,
        X: np.ndarray,
        U: np.ndarray,
        alpha_peak: float,
        success: bool,
        status: str,
        solve_time: float,
        iterations: int,
        objective: float,
    ) -> dict[str, Any]:
        residuals = []
        for k, action in enumerate(U):
            dyn_next = step_dynamics(X[k], self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            residuals.append(np.abs(X[k + 1] - dyn_next))
        residual_arr = np.asarray(residuals, dtype=float).reshape(-1) if residuals else np.array([], dtype=float)
        alpha = np.diff(X[:, 1]) / self.prediction_dt if len(X) > 1 else np.array([], dtype=float)
        delta_r = X[:, 2] - float(self.model_params["L0"]) if len(X) else np.array([], dtype=float)
        omega_abs = np.abs(X[:, 1]) if len(X) else np.array([], dtype=float)
        force_abs = np.abs(U) if len(U) else np.zeros((0, 2), dtype=float)
        terminal_theta = float(X[-1, 0]) if len(X) else np.nan
        terminal_omega = float(X[-1, 1]) if len(X) else np.nan
        return {
            "success": bool(success),
            "status": status,
            "iterations": int(iterations),
            "solve_time_s": float(solve_time),
            "objective": objective,
            "dynamics_residual_max": float(np.nanmax(residual_arr)) if residual_arr.size else np.nan,
            "dynamics_residual_mean": float(np.nanmean(residual_arr)) if residual_arr.size else np.nan,
            "constraint_violation_max": self._constraint_violation_max(X, U, alpha, alpha_peak),
            "alpha_abs_max": float(np.nanmax(np.abs(alpha))) if alpha.size else np.nan,
            "alpha_abs_p95": float(np.nanpercentile(np.abs(alpha), 95)) if alpha.size else np.nan,
            "terminal_theta": terminal_theta,
            "terminal_theta_deg": float(np.degrees(terminal_theta)) if np.isfinite(terminal_theta) else np.nan,
            "terminal_omega": terminal_omega,
            "terminal_crossing_margin": terminal_theta - self.target_crossing if np.isfinite(terminal_theta) else np.nan,
            "terminal_crossing_margin_deg": float(np.degrees(terminal_theta - self.target_crossing)) if np.isfinite(terminal_theta) else np.nan,
            "F_tan_margin": float(self.constraints.F_tan_max - np.nanmax(force_abs[:, 0])) if len(force_abs) else np.nan,
            "F_rad_margin": float(self.constraints.F_rad_max - np.nanmax(force_abs[:, 1])) if len(force_abs) else np.nan,
            "delta_r_margin": float(self.constraints.delta_r_max - np.nanmax(np.abs(delta_r))) if len(delta_r) else np.nan,
            "omega_margin": float(self.constraints.omega_max - np.nanmax(omega_abs)) if len(omega_abs) else np.nan,
            "action_total_variation": float(np.nansum(np.linalg.norm(np.diff(U, axis=0), axis=1))) if len(U) > 1 else 0.0,
        }

    def _constraint_violation_max(self, X: np.ndarray, U: np.ndarray, alpha: np.ndarray, alpha_peak: float) -> float:
        violations: list[float] = []
        if len(X):
            violations.extend(np.maximum(0.0, np.abs(X[:, 1]) - self.constraints.omega_max).tolist())
            violations.extend(np.maximum(0.0, np.abs(X[:, 2] - float(self.model_params["L0"])) - self.constraints.delta_r_max).tolist())
            violations.append(max(0.0, self.target_crossing - float(X[-1, 0])))
        if len(U):
            violations.extend(np.maximum(0.0, np.abs(U[:, 0]) - self.constraints.F_tan_max).tolist())
            violations.extend(np.maximum(0.0, np.abs(U[:, 1]) - self.constraints.F_rad_max).tolist())
        if len(alpha):
            violations.extend(np.maximum(0.0, np.abs(alpha) - alpha_peak).tolist())
        return float(np.nanmax(violations)) if violations else np.nan


def build_stage9g_config(config_path: Path) -> dict[str, Any]:
    cfg = load_experiment_config(config_path)
    for key in ("true_params", "model_params"):
        cfg[key]["theta_init"] = INITIAL_THETA
        cfg[key]["omega_init"] = INITIAL_OMEGA
    cfg["mpc_params"]["target_theta"] = float(cfg["true_params"]["theta_target"])
    return cfg


def initial_state(true_params: dict[str, Any]) -> np.ndarray:
    return np.array(
        [
            float(true_params["theta_init"]),
            float(true_params["omega_init"]),
            float(true_params["r_init"]),
            float(true_params["r_dot_init"]),
        ],
        dtype=float,
    )


def row_from_diag(mode: str, horizon: int, problem: AlphaFrontierProblem, diag: dict[str, Any]) -> dict[str, Any]:
    success = bool(diag["success"])
    keep_limit = mode == "fixed_alpha_feasibility"
    return {
        "mode": mode,
        "horizon": int(horizon),
        "crossing_time_s": float(horizon * problem.prediction_dt),
        "fixed_alpha_limit": diag.get("fixed_alpha_limit", np.nan),
        "success": success,
        "status": str(diag["status"]),
        "iterations": int(diag["iterations"]),
        "solve_time_s": finite_float(diag["solve_time_s"]),
        "objective": finite_float(diag["objective"]),
        "alpha_peak": finite_float(diag["alpha_peak"]) if success or keep_limit else np.nan,
        "alpha_abs_max_check": finite_float(diag["alpha_abs_max"]) if success else np.nan,
        "alpha_abs_p95_check": finite_float(diag["alpha_abs_p95"]) if success else np.nan,
        "terminal_theta_deg": finite_float(diag["terminal_theta_deg"]) if success else np.nan,
        "terminal_omega": finite_float(diag["terminal_omega"]) if success else np.nan,
        "terminal_crossing_margin_deg": finite_float(diag["terminal_crossing_margin_deg"]) if success else np.nan,
        "F_tan_margin": finite_float(diag["F_tan_margin"]) if success else np.nan,
        "F_rad_margin": finite_float(diag["F_rad_margin"]) if success else np.nan,
        "delta_r_margin": finite_float(diag["delta_r_margin"]) if success else np.nan,
        "omega_margin": finite_float(diag["omega_margin"]) if success else np.nan,
        "action_total_variation": finite_float(diag["action_total_variation"]) if success else np.nan,
        "dynamics_residual_max": finite_float(diag["dynamics_residual_max"]),
        "dynamics_residual_mean": finite_float(diag["dynamics_residual_mean"]),
        "constraint_violation_max": finite_float(diag["constraint_violation_max"]),
        "warm_start": str(diag["warm_start"]),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "mode",
        "horizon",
        "crossing_time_s",
        "fixed_alpha_limit",
        "success",
        "status",
        "iterations",
        "solve_time_s",
        "objective",
        "alpha_peak",
        "alpha_abs_max_check",
        "alpha_abs_p95_check",
        "terminal_theta_deg",
        "terminal_omega",
        "terminal_crossing_margin_deg",
        "F_tan_margin",
        "F_rad_margin",
        "delta_r_margin",
        "omega_margin",
        "action_total_variation",
        "dynamics_residual_max",
        "dynamics_residual_mean",
        "constraint_violation_max",
        "warm_start",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def plot_min_alpha(rows: list[dict[str, Any]], out: Path) -> None:
    min_rows = [r for r in rows if r["mode"] == "min_alpha" and bool(r["success"])]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    if min_rows:
        times = [float(r["crossing_time_s"]) for r in min_rows]
        peaks = [float(r["alpha_peak"]) for r in min_rows]
        ax.plot(times, peaks, marker="o", linewidth=2.0, label="minimum alpha_peak")
    for label, value in STAGE_COMPARISONS.items():
        ax.axhline(value, linestyle="--", linewidth=1.0, label=label)
    ax.set_xlabel("allowed crossing time [s]")
    ax.set_ylabel("minimum alpha_peak [rad/s^2]")
    ax.set_title("Crossing-alpha feasibility frontier")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_feasibility_map(rows: list[dict[str, Any]], out: Path) -> None:
    fixed_rows = [r for r in rows if r["mode"] == "fixed_alpha_feasibility"]
    horizons = sorted({int(r["horizon"]) for r in fixed_rows})
    limits = sorted({float(r["fixed_alpha_limit"]) for r in fixed_rows})
    mat = np.full((len(limits), len(horizons)), np.nan)
    for r in fixed_rows:
        i = limits.index(float(r["fixed_alpha_limit"]))
        j = horizons.index(int(r["horizon"]))
        mat[i, j] = 1.0 if bool(r["success"]) else 0.0
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    im = ax.imshow(mat, aspect="auto", origin="lower", cmap="RdYlGn", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(horizons)), labels=[str(h) for h in horizons])
    ax.set_yticks(range(len(limits)), labels=[fmt(v, 3) for v in limits])
    ax.set_xlabel("horizon N")
    ax.set_ylabel("fixed alpha limit [rad/s^2]")
    ax.set_title("Fixed-alpha crossing feasibility")
    for i in range(len(limits)):
        for j in range(len(horizons)):
            text = "OK" if mat[i, j] == 1.0 else "FAIL"
            ax.text(j, i, text, ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, ticks=[0, 1], label="solver success")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_trajectories(solutions: dict[int, dict[str, Any]], problem_by_horizon: dict[int, AlphaFrontierProblem], out_dir: Path) -> None:
    feasible = {h: d for h, d in solutions.items() if bool(d["success"])}
    if not feasible:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 8.0), sharex=True)
    for horizon, diag in feasible.items():
        problem = problem_by_horizon[horizon]
        t = np.arange(horizon + 1) * problem.prediction_dt
        X = np.asarray(diag["X"], dtype=float)
        alpha = np.diff(X[:, 1]) / problem.prediction_dt
        axes[0].plot(t, np.degrees(X[:, 0]), label=f"N={horizon}")
        axes[1].plot(t, X[:, 1], label=f"N={horizon}")
        axes[2].step(t[:-1], alpha, where="post", label=f"N={horizon}")
    target_deg = np.degrees(next(iter(problem_by_horizon.values())).target_crossing)
    axes[0].axhline(target_deg, color="black", linestyle=":", linewidth=1.0, label="target + margin")
    axes[1].axhline(next(iter(problem_by_horizon.values())).constraints.omega_max, color="black", linestyle=":", linewidth=0.9)
    axes[1].axhline(-next(iter(problem_by_horizon.values())).constraints.omega_max, color="black", linestyle=":", linewidth=0.9)
    axes[0].set_ylabel("theta [deg]")
    axes[1].set_ylabel("omega [rad/s]")
    axes[2].set_ylabel("alpha [rad/s^2]")
    axes[2].set_xlabel("time [s]")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "state_alpha_trajectories.png")
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(8.0, 8.0), sharex=True)
    for horizon, diag in feasible.items():
        problem = problem_by_horizon[horizon]
        t_u = np.arange(horizon) * problem.prediction_dt
        t_x = np.arange(horizon + 1) * problem.prediction_dt
        X = np.asarray(diag["X"], dtype=float)
        U = np.asarray(diag["U"], dtype=float)
        delta_r_margin = problem.constraints.delta_r_max - np.abs(X[:, 2] - float(problem.model_params["L0"]))
        omega_margin = problem.constraints.omega_max - np.abs(X[:, 1])
        force_margin = np.minimum(problem.constraints.F_tan_max - np.abs(U[:, 0]), problem.constraints.F_rad_max - np.abs(U[:, 1]))
        axes[0].step(t_u, U[:, 0], where="post", label=f"F_tan N={horizon}")
        axes[0].step(t_u, U[:, 1], where="post", linestyle="--", label=f"F_rad N={horizon}")
        axes[1].plot(t_x, delta_r_margin, label=f"delta_r N={horizon}")
        axes[1].plot(t_x, omega_margin, linestyle="--", label=f"omega N={horizon}")
        axes[2].step(t_u, force_margin, where="post", label=f"N={horizon}")
    axes[0].set_ylabel("action [N]")
    axes[1].set_ylabel("state margin")
    axes[2].set_ylabel("force margin")
    axes[2].set_xlabel("time [s]")
    for ax in axes:
        ax.axhline(0.0, color="black", linestyle=":", linewidth=0.9)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "actions_and_margins.png")
    plt.close(fig)


def markdown_table(rows: list[dict[str, Any]], mode: str) -> list[str]:
    selected = [r for r in rows if r["mode"] == mode]
    lines = [
        "| mode | N | time_s | alpha_limit | success | alpha_peak | terminal_theta_deg | cross_margin_deg | omega_margin | delta_r_margin | status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in selected:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r["mode"]),
                    str(r["horizon"]),
                    fmt(r["crossing_time_s"], 4),
                    fmt(r["fixed_alpha_limit"], 4),
                    str(bool(r["success"])),
                    fmt(r["alpha_peak"], 5),
                    fmt(r["terminal_theta_deg"], 5),
                    fmt(r["terminal_crossing_margin_deg"], 5),
                    fmt(r["omega_margin"], 5),
                    fmt(r["delta_r_margin"], 5),
                    str(r["status"]),
                ]
            )
            + " |"
        )
    return lines


def write_report(
    path: Path,
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
    command: str,
    script_changed: str,
) -> None:
    min_rows = [r for r in rows if r["mode"] == "min_alpha" and bool(r["success"])]
    best = min(min_rows, key=lambda r: float(r["alpha_peak"])) if min_rows else None
    feasible_3_4 = [r for r in rows if r["mode"] == "fixed_alpha_feasibility" and bool(r["success"]) and float(r["fixed_alpha_limit"]) <= 4.0]
    baseline_alpha = STAGE_COMPARISONS["stage9f_baseline_cem_crossing"]
    if best is None:
        conclusion = "No tested horizon produced a solver-confirmed feasible crossing under the hard force/deformation/omega constraints."
        next_step = "task-definition revision or longer-time reachability study before online controller work."
    elif float(best["alpha_peak"]) <= 4.0 or feasible_3_4:
        conclusion = "Low-alpha crossing is feasible in the tested oracle problem when enough crossing time is allowed; the online crossing formulation is the main suspect."
        next_step = "reachability-aware online crossing constraint or trajectory planner plus NMPC tracking."
    elif float(best["alpha_peak"]) >= 0.8 * baseline_alpha:
        conclusion = "Crossing needs alpha near the baseline CEM crossing level in this horizon set; the current alpha requirement conflicts with the task."
        next_step = "alpha-limit or task-definition revision before linked-rods transfer."
    else:
        conclusion = "Crossing is feasible below baseline CEM alpha but not near 3-4; horizon/progress planning matters."
        next_step = "explicit crossing-time/progress planning, then constrained refinement."
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Stage 9G Crossing-Alpha Feasibility Frontier\n\n")
        f.write("This is an offline oracle feasibility study, not a new online controller.\n\n")
        f.write("## Setup\n\n")
        f.write(f"- Command: `{command}`\n")
        f.write(f"- Script: `{script_changed}`\n")
        f.write(f"- Initial state override: theta={INITIAL_THETA} rad, omega={INITIAL_OMEGA} rad/s.\n")
        f.write(f"- Target crossing: theta_N >= theta_target + {np.degrees(CROSSING_MARGIN):.3f} deg.\n")
        f.write("- Oracle assumptions: true state, true physical parameters, no estimator, no identifier, no observation noise, no fallback.\n")
        f.write("- Optimization: scaled CasADi multiple shooting with explicit X, U, and scalar alpha_peak.\n")
        f.write("- Primary objective: minimize alpha_peak; secondary action/action-rate/terminal-omega costs use small coefficients.\n")
        constraints = Spring2DMPCConstraints.from_configs(
            cfg["true_params"],
            cfg["mpc_params"].get("constraints", {}),
            prediction_dt=float(cfg["mpc_params"].get("solver", {}).get("prediction_dt", cfg["true_params"]["dt"])),
        )
        f.write(
            "- Hard constraints: "
            f"|F_tan|<={constraints.F_tan_max:g}, |F_rad|<={constraints.F_rad_max:g}, "
            f"|r-L0|<={constraints.delta_r_max:g}, |omega|<={constraints.omega_max:g}, terminal crossing, dynamics equality.\n"
        )
        f.write("- Alpha slack was not used in the primary frontier problem.\n\n")
        f.write("## Minimum-Alpha Frontier\n\n")
        f.write("\n".join(markdown_table(rows, "min_alpha")))
        f.write("\n\n## Fixed-Alpha Feasibility Check\n\n")
        f.write("\n".join(markdown_table(rows, "fixed_alpha_feasibility")))
        f.write("\n\n## Prior Reference Values\n\n")
        f.write("| reference | alpha max [rad/s^2] | note |\n")
        f.write("|---|---:|---|\n")
        f.write(f"| Stage 9D nmpc_base | {STAGE_COMPARISONS['stage9d_nmpc_base_no_crossing']:.3f} | no target crossing |\n")
        f.write(f"| Stage 9F baseline CEM | {STAGE_COMPARISONS['stage9f_baseline_cem_crossing']:.3f} | crossed |\n")
        f.write(f"| Stage 9F weighted crossing NMPC | {STAGE_COMPARISONS['stage9f_weighted_crossing']:.2f} | crossed with spike |\n")
        f.write(f"| Stage 9F lexicographic crossing NMPC | {STAGE_COMPARISONS['stage9f_lexicographic_crossing']:.2f} | crossed with large spike |\n\n")
        f.write("## Required Answers\n\n")
        if best is None:
            f.write("1. Low-alpha target crossing was not solver-confirmed in the tested horizons; all tested frontier solves failed or were infeasible.\n")
            f.write("2. The minimum achievable alpha peak is not established by this run because no feasible frontier solution was accepted.\n")
        else:
            f.write(
                f"1. Low-alpha target crossing is {'feasible' if float(best['alpha_peak']) <= 4.0 or feasible_3_4 else 'not near 3-4 in the accepted frontier'} "
                f"under the tested hard constraints, but only accepted at N={best['horizon']} in this horizon set.\n"
            )
            f.write(
                f"2. The lowest accepted alpha_peak is {float(best['alpha_peak']):.4g} rad/s^2 at N={best['horizon']} "
                f"({float(best['crossing_time_s']):.3f} s).\n"
            )
        if min_rows:
            trend = ", ".join(f"N={r['horizon']}: {fmt(r['alpha_peak'], 4)}" for r in min_rows)
            f.write(f"3. Minimum alpha versus horizon among accepted solves: {trend}.\n")
        else:
            f.write("3. No accepted minimum-alpha trend is available.\n")
        f.write(f"4. Alpha around 3-4 is {'compatible with crossing in at least one fixed-alpha check' if feasible_3_4 else 'not demonstrated compatible by the fixed-alpha checks'}.\n")
        if best is not None:
            if float(best["alpha_peak"]) < 0.7 * baseline_alpha:
                f.write("5. Baseline CEM alpha max around 9 appears unnecessarily aggressive relative to the oracle frontier.\n")
            elif float(best["alpha_peak"]) <= 1.2 * baseline_alpha:
                f.write("5. Baseline CEM alpha max around 9 is near the tested feasibility boundary.\n")
            else:
                f.write("5. The accepted frontier is above baseline CEM alpha, which suggests numerical or horizon effects must be inspected before interpreting baseline aggressiveness.\n")
        else:
            f.write("5. Baseline aggressiveness cannot be judged because the oracle frontier did not accept a feasible crossing solution.\n")
        if best is not None and float(best["alpha_peak"]) < STAGE_COMPARISONS["stage9f_weighted_crossing"]:
            f.write("6. Stage 9F crossing spikes were not forced at their observed magnitude by the offline oracle problem; the online formulation contributed substantially.\n")
        else:
            f.write("6. Stage 9F spikes cannot be cleanly separated from task feasibility using this run alone.\n")
        f.write(f"7. Recommended next step: {next_step}\n\n")
        f.write("## Conclusion\n\n")
        f.write(conclusion + "\n\n")
        f.write("No formal safety guarantee is claimed.\n")


def run(output_root: Path, config_path: Path) -> None:
    if ca is None:
        raise RuntimeError("CasADi is unavailable; Stage 9G requires a CasADi multiple-shooting solve.")
    cfg = build_stage9g_config(config_path)
    true_params = cfg["true_params"]
    mpc_params = cfg["mpc_params"]
    x0 = initial_state(true_params)
    output_root.mkdir(parents=True, exist_ok=True)
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    solutions: dict[int, dict[str, Any]] = {}
    problem_by_horizon: dict[int, AlphaFrontierProblem] = {}
    previous_solution: dict[str, np.ndarray] | None = None
    for horizon in HORIZONS:
        problem = AlphaFrontierProblem(true_params, mpc_params, horizon)
        problem_by_horizon[horizon] = problem
        warm_label = "interpolated_previous_horizon" if previous_solution is not None else "heuristic"
        diag = problem.solve(x0, warmstart=previous_solution, warmstart_label=warm_label)
        rows.append(row_from_diag("min_alpha", horizon, problem, diag))
        solutions[horizon] = diag
        if bool(diag["success"]):
            previous_solution = {"X": np.asarray(diag["X"], dtype=float), "U": np.asarray(diag["U"], dtype=float), "alpha_peak": np.asarray(diag["alpha_peak"])}
        for limit in FIXED_ALPHA_LIMITS:
            fixed_warm = {"X": np.asarray(diag["X"], dtype=float), "U": np.asarray(diag["U"], dtype=float), "alpha_peak": np.asarray(limit)}
            fixed_label = "frontier_solution" if bool(diag["success"]) else warm_label
            fixed_diag = problem.solve(x0, warmstart=fixed_warm, fixed_alpha_limit=limit, warmstart_label=fixed_label)
            rows.append(row_from_diag("fixed_alpha_feasibility", horizon, problem, fixed_diag))
    write_csv(output_root / "stage9g_summary.csv", rows)
    plot_min_alpha(rows, fig_dir / "minimum_alpha_peak_vs_crossing_time.png")
    plot_feasibility_map(rows, fig_dir / "fixed_alpha_feasibility_map.png")
    plot_trajectories(solutions, problem_by_horizon, fig_dir)
    command = "python scripts/run_spring2d_stage9g_crossing_alpha_frontier.py"
    write_report(
        output_root / "stage9g_report.md",
        cfg,
        rows,
        command=command,
        script_changed="scripts/run_spring2d_stage9g_crossing_alpha_frontier.py",
    )


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
