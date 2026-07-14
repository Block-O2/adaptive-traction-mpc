"""Stage 9D NMPC logging sanity check and stress validation."""

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
from run_spring2d_stage9b_nmpc_diagnosis import DiagnosticCasadiNMPC
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC as CEMAdaptiveMPC
from traction_mpc.mpc.cost import stage_cost, terminal_cost
from traction_mpc.mpc.safety_filter import SafetyFilterResult


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9d_nmpc_stress_validation"
SANITY_CONDITIONS = ["clean", "noise", "noise_bias"]
STRESS_CONDITIONS = [
    "stronger_noise",
    "stronger_bias",
    "parameter_mismatch_low_k",
    "parameter_mismatch_high_k",
    "initial_theta_offset",
    "larger_target_angle",
    "tighter_alpha_limit",
]
CONDITIONS = SANITY_CONDITIONS + STRESS_CONDITIONS
SEEDS = [101, 102, 103]
SLACK_ACTIVE_THRESHOLDS = (1.0e-5, 1.0e-4, 1.0e-3)
PRIMARY_SLACK_ACTIVE_THRESHOLD = SLACK_ACTIVE_THRESHOLDS[0]

METHODS = [
    "baseline_cem",
    "alpha200_omega0",
    "nmpc_rho100_scaled",
    "nmpc_rho1000_scaled",
    "nmpc_rho100_scaled_with_cem_fallback",
]
NMPC_METHODS = {
    "nmpc_rho100_scaled",
    "nmpc_rho1000_scaled",
    "nmpc_rho100_scaled_with_cem_fallback",
}


EXTRA_FIELDS = [
    "nmpc_solver_success",
    "nmpc_solver_failure",
    "nmpc_fallback_used",
    "nmpc_fallback_mode",
    "nmpc_solve_time_s",
    "nmpc_solver_iterations",
    "nmpc_solver_status",
    "nmpc_failure_reason",
    "nmpc_objective",
    "nmpc_cost_task",
    "nmpc_cost_action",
    "nmpc_cost_action_rate",
    "nmpc_cost_alpha_slack_l1",
    "nmpc_cost_alpha_slack_l2",
    "nmpc_cost_state_violation",
    "nmpc_dynamics_residual_max",
    "nmpc_dynamics_residual_mean",
    "nmpc_constraint_violation_max",
    "nmpc_constraint_violation_mean",
    "nmpc_alpha_slack_mean_raw",
    "nmpc_alpha_slack_max_raw",
    "nmpc_alpha_slack_active_count_gt_1e_5",
    "nmpc_alpha_slack_active_count_gt_1e_4",
    "nmpc_alpha_slack_active_count_gt_1e_3",
    "nmpc_first_F_tan",
    "nmpc_first_F_rad",
    "nmpc_first_action_diff_vs_cem",
    "nmpc_horizon",
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


class ScaledValidationNMPC(DiagnosticCasadiNMPC):
    """Stage 9B scaled formulation with Stage 9C state path penalties."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any], variant: dict[str, Any]):
        self.delta_r_penalty = float(variant.get("delta_r_penalty", 2.0e5))
        self.omega_penalty = float(variant.get("omega_penalty", 2.0e5))
        super().__init__(model_params, mpc_params, variant)

    def _build_solver(self) -> Any:
        n = self.horizon
        Xv = ca.SX.sym("X", 4, n + 1)
        Uv = ca.SX.sym("U", 2, n)
        Sv = ca.SX.sym("S", n)
        P = ca.SX.sym("P", 10)
        x_scale = ca.DM(self.x_scale)
        u_scale = ca.DM(self.u_scale)
        X = ca.diag(x_scale) @ Xv
        U = ca.diag(u_scale) @ Uv
        S = self.s_scale * Sv
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
            )
            du = U[:, k] - action_prev
            cost += 1.0e-3 * ca.dot(du, du)
            cost += self.alpha_rho_l1 * S[k] + self.alpha_rho_l2 * S[k] ** 2
            cost += self.delta_r_penalty * ca.fmax(0, ca.fabs(delta_r) - self.constraints.delta_r_max) ** 2
            cost += self.omega_penalty * ca.fmax(0, ca.fabs(omega) - self.constraints.omega_max) ** 2
            action_prev = U[:, k]
        terminal_theta = X[0, n] - target
        terminal_delta_r = X[2, n] - float(self.model_params["L0"])
        cost += self.weights.w_terminal_theta * terminal_theta**2 + self.weights.w_delta_r * terminal_delta_r**2
        cost = cost / 1000.0
        z = ca.vertcat(ca.reshape(Xv, -1, 1), ca.reshape(Uv, -1, 1), Sv)
        nlp = {"x": z, "f": cost, "g": ca.vertcat(*g), "p": P}
        opts = {
            "print_time": False,
            "ipopt.print_level": 0,
            "ipopt.sb": "yes",
            "ipopt.max_iter": 80,
            "ipopt.tol": 1.0e-4,
            "ipopt.acceptable_tol": 1.0e-3,
        }
        ScaledValidationNMPC._counter += 1
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", self.name)
        return ca.nlpsol(f"stage9d_{safe_name}_{ScaledValidationNMPC._counter}", "ipopt", nlp, opts)

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
        violations = []
        for k, action in enumerate(U):
            dyn_next = step_dynamics(X_decision[k], self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            residuals.append(np.abs(X_decision[k + 1] - dyn_next))
            alpha = (float(X_decision[k + 1, 1]) - float(X_decision[k, 1])) / self.prediction_dt
            delta_r = float(X_decision[k + 1, 2] - self.model_params["L0"])
            slack = float(S[k]) if k < len(S) else 0.0
            violations.extend(
                [
                    max(0.0, abs(alpha) - self.constraints.alpha_max - slack),
                    max(0.0, abs(float(X_decision[k + 1, 1])) - self.constraints.omega_max),
                    max(0.0, abs(delta_r) - self.constraints.delta_r_max),
                    max(0.0, abs(float(action[0])) - self.constraints.F_tan_max),
                    max(0.0, abs(float(action[1])) - self.constraints.F_rad_max),
                ]
            )
        residual_arr = np.asarray(residuals, dtype=float).reshape(-1) if residuals else np.array([])
        violation_arr = np.asarray(violations, dtype=float)
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
            "constraint_violation_max": _finite_max(violation_arr),
            "constraint_violation_mean": _finite_mean(violation_arr),
            "alpha_slack_mean": _finite_mean(slacks),
            "alpha_slack_max": _finite_max(slacks),
            "alpha_slack_active_count_gt_1e_5": int(np.count_nonzero(slacks > 1.0e-5)),
            "alpha_slack_active_count_gt_1e_4": int(np.count_nonzero(slacks > 1.0e-4)),
            "alpha_slack_active_count_gt_1e_3": int(np.count_nonzero(slacks > 1.0e-3)),
            "first_F_tan": float(U[0, 0]) if len(U) else np.nan,
            "first_F_rad": float(U[0, 1]) if len(U) else np.nan,
        }


class AdaptiveScaledValidationNMPC:
    estimated_parameter_names = ("m", "k", "b_r")

    def __init__(self, initial_model_params: dict[str, Any], mpc_params: dict[str, Any], variant: dict[str, Any]):
        self.model_params = dict(initial_model_params)
        self.current_model_params = dict(initial_model_params)
        self.mpc_params = dict(mpc_params)
        self.variant = dict(variant)
        self.fallback_mode = str(variant.get("fallback_mode", "none"))
        self.controller = ScaledValidationNMPC(self.current_model_params, self.mpc_params, variant)
        helper_variant = dict(variant)
        helper_variant["name"] = str(variant["name"]) + "_helper_no_alpha"
        helper_variant["alpha"] = False
        helper_variant["rho_l1"] = 0.0
        helper_variant["warmstart"] = "shift"
        helper_variant["scaled"] = True
        self.no_alpha_helper = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, helper_variant)
        self.cem_fallback = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.last_diag: dict[str, Any] = {}
        self.last_update_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.current_model_params = dict(self.model_params)
        self.controller = ScaledValidationNMPC(self.current_model_params, self.mpc_params, self.variant)
        helper_variant = dict(self.variant)
        helper_variant["name"] = str(self.variant["name"]) + "_helper_no_alpha"
        helper_variant["alpha"] = False
        helper_variant["rho_l1"] = 0.0
        helper_variant["warmstart"] = "shift"
        helper_variant["scaled"] = True
        self.no_alpha_helper = DiagnosticCasadiNMPC(self.current_model_params, self.mpc_params, helper_variant)
        self.cem_fallback = CEMAdaptiveMPC(self.current_model_params, self.mpc_params)
        self.cem_fallback.reset()
        self.last_diag = {}
        self.last_update_diagnostics = {}

    def set_target_theta(self, target_theta: float) -> None:
        self.controller.set_target_theta(target_theta)
        self.no_alpha_helper.set_target_theta(target_theta)
        self.cem_fallback.set_target_theta(target_theta)

    def act(self, observation: Any) -> np.ndarray:
        state = observation_to_state(observation)
        helper = self.no_alpha_helper.solve(state, self.controller.last_action)
        initial_override = {"U": helper["U"]}
        diag = self.controller.solve(state, self.controller.last_action, initial_override=initial_override)
        fallback_used = False
        fallback_mode = "none"
        if bool(diag["success"]):
            action = np.asarray(diag["first_action"], dtype=float)
        elif self.fallback_mode == "cem":
            action = self.cem_fallback.act(observation)
            fallback_used = True
            fallback_mode = "baseline_cem"
        else:
            action = np.asarray(diag["first_action"], dtype=float)
        action = self.controller.constraints.clip_action(action)
        cost_terms = self._cost_terms(state, diag["U"], diag["S"], self.controller.last_action)
        self.controller.last_action = action.copy()
        self.last_diag = {
            "nmpc_solver_success": bool(diag["success"]),
            "nmpc_solver_failure": not bool(diag["success"]),
            "nmpc_fallback_used": bool(fallback_used),
            "nmpc_fallback_mode": fallback_mode,
            "nmpc_solve_time_s": float(diag["solve_time"]),
            "nmpc_solver_iterations": int(diag["iterations"]),
            "nmpc_solver_status": str(diag["status"]),
            "nmpc_failure_reason": str(diag["failure_reason"]),
            "nmpc_objective": float(diag["objective"]) if np.isfinite(diag["objective"]) else np.nan,
            **cost_terms,
            "nmpc_dynamics_residual_max": float(diag["dynamics_residual_max"]),
            "nmpc_dynamics_residual_mean": float(diag["dynamics_residual_mean"]),
            "nmpc_constraint_violation_max": float(diag["constraint_violation_max"]),
            "nmpc_constraint_violation_mean": float(diag["constraint_violation_mean"]),
            "nmpc_alpha_slack_mean_raw": float(diag["alpha_slack_mean"]),
            "nmpc_alpha_slack_max_raw": float(diag["alpha_slack_max"]),
            "nmpc_alpha_slack_active_count_gt_1e_5": int(diag["alpha_slack_active_count_gt_1e_5"]),
            "nmpc_alpha_slack_active_count_gt_1e_4": int(diag["alpha_slack_active_count_gt_1e_4"]),
            "nmpc_alpha_slack_active_count_gt_1e_3": int(diag["alpha_slack_active_count_gt_1e_3"]),
            "nmpc_first_F_tan": float(diag["first_action"][0]),
            "nmpc_first_F_rad": float(diag["first_action"][1]),
            "nmpc_first_action_diff_vs_cem": np.nan,
            "nmpc_horizon": int(self.controller.horizon),
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
        return action

    def _cost_terms(self, state: np.ndarray, U: np.ndarray, S: np.ndarray, prev_action: np.ndarray) -> dict[str, float]:
        x = np.asarray(state, dtype=float).copy()
        previous_action = np.asarray(prev_action, dtype=float).copy()
        task = 0.0
        action_cost = 0.0
        rate_cost = 0.0
        state_violation = 0.0
        for action in np.asarray(U, dtype=float):
            prev_x = x.copy()
            x = step_dynamics(x, self.controller.constraints.clip_action(action), self.controller.prediction_dt, self.controller.model_params)
            task += stage_cost(
                x,
                action,
                prev_x[1],
                self.controller.prediction_dt,
                self.controller.target_theta,
                self.controller.model_params,
                self.controller.weights,
            )
            action_cost += self.controller.weights.w_F_tan * float(action[0] ** 2) + self.controller.weights.w_F_rad * float(action[1] ** 2)
            rate_cost += 1.0e-3 * float(np.dot(action - previous_action, action - previous_action))
            delta_slack = max(0.0, abs(float(x[2] - self.controller.model_params["L0"])) - self.controller.constraints.delta_r_max)
            omega_slack = max(0.0, abs(float(x[1])) - self.controller.constraints.omega_max)
            state_violation += self.controller.delta_r_penalty * delta_slack**2 + self.controller.omega_penalty * omega_slack**2
            previous_action = np.asarray(action, dtype=float)
        task += terminal_cost(x, self.controller.target_theta, self.controller.model_params, self.controller.weights)
        slacks = np.asarray(S, dtype=float)
        return {
            "nmpc_cost_task": float(task),
            "nmpc_cost_action": float(action_cost),
            "nmpc_cost_action_rate": float(rate_cost),
            "nmpc_cost_alpha_slack_l1": float(self.controller.alpha_rho_l1 * np.sum(slacks)),
            "nmpc_cost_alpha_slack_l2": float(self.controller.alpha_rho_l2 * np.sum(slacks**2)),
            "nmpc_cost_state_violation": float(state_violation),
        }

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
        self.no_alpha_helper.set_model_params(update)
        self.cem_fallback.update_parameters(theta_hat, alpha=alpha, bounds=bounds)
        self.last_update_diagnostics = {
            "mpc_recreated_on_update": False,
            "solver_recreated_on_update": False,
            "last_action_preserved_on_update": True,
            "last_solution_existed_before_update": self.controller.last_U is not None,
            "last_solution_preserved_on_update": self.controller.last_U is not None,
        }
        return self.get_current_parameter_estimate()


def method_variant(method: str) -> dict[str, Any]:
    if method == "nmpc_rho100_scaled":
        rho = 100.0
        fallback = "none"
    elif method == "nmpc_rho1000_scaled":
        rho = 1000.0
        fallback = "none"
    elif method == "nmpc_rho100_scaled_with_cem_fallback":
        rho = 100.0
        fallback = "cem"
    else:
        raise ValueError(f"Not an NMPC method: {method}")
    return {
        "name": method,
        "horizon": 18,
        "alpha": True,
        "rho_l1": rho,
        "rho_l2": 1.0e-2,
        "warmstart": "no_alpha",
        "scaled": True,
        "fallback_mode": fallback,
        "delta_r_penalty": 2.0e5,
        "omega_penalty": 2.0e5,
    }


def configure_nmpc_run(base_cfg: dict[str, Any], method: str, seed: int) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["seed"] = int(seed)
    solver["safety_mode"] = "off"
    solver["gatekeeper_mode"] = "off"
    solver["alpha_constraint_mode"] = "soft"
    solver["action_parameterization_mode"] = "standard"
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    solver["horizon"] = 18
    cfg["mpc_params"]["stage9d_nmpc"] = method_variant(method)
    return cfg


def configure_cem_seeded(base_cfg: dict[str, Any], method: str, seed: int) -> dict[str, Any]:
    cfg = configure_cem_run(base_cfg, method)
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    return cfg


def _base_condition_name(condition: str) -> str:
    if condition == "stronger_noise":
        return "noise"
    if condition == "stronger_bias":
        return "noise_bias"
    return condition if condition in {"clean", "noise", "noise_bias"} else "clean"


def condition_with_seed(base_cfg: dict[str, Any], condition: str, seed: int) -> dict[str, Any]:
    condition_cfg = copy.deepcopy(base_cfg["conditions"][_base_condition_name(condition)])
    condition_cfg["seed"] = int(seed)
    noise = condition_cfg.setdefault("observation_noise", {})
    if condition == "stronger_noise":
        noise.update(
            {
                "theta_std": 0.008,
                "omega_std": 0.07,
                "r_std": 0.0016,
                "r_dot_std": 0.008,
                "theta_bias": 0.0,
                "omega_bias": 0.0,
                "r_bias": 0.0,
                "r_dot_bias": 0.0,
            }
        )
    elif condition == "stronger_bias":
        noise.update(
            {
                "theta_std": 0.004,
                "omega_std": 0.035,
                "r_std": 0.0008,
                "r_dot_std": 0.004,
                "theta_bias": 0.02,
                "omega_bias": -0.04,
                "r_bias": 0.003,
                "r_dot_bias": 0.004,
            }
        )
    return condition_cfg


def stress_override_note(condition: str) -> str:
    notes = {
        "clean": "default clean condition",
        "noise": "default noise condition",
        "noise_bias": "default noise_bias condition",
        "stronger_noise": "observation noise std doubled vs default noise",
        "stronger_bias": "observation bias doubled vs default noise_bias",
        "parameter_mismatch_low_k": "initial/model k set to 270; true dynamics unchanged",
        "parameter_mismatch_high_k": "initial/model k set to 600; true dynamics unchanged",
        "initial_theta_offset": "theta_init=0.02 rad and omega_init=-0.15 rad/s explicit run override",
        "larger_target_angle": "theta_target=105 deg explicit run override",
        "tighter_alpha_limit": "alpha_max constraint/evaluation set to 2.0 rad/s^2",
    }
    return notes.get(condition, "")


def apply_stage9d_overrides(cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    cfg = copy.deepcopy(cfg)
    if condition == "parameter_mismatch_low_k":
        cfg["model_params"]["k"] = 270.0
    elif condition == "parameter_mismatch_high_k":
        cfg["model_params"]["k"] = 600.0
    elif condition == "initial_theta_offset":
        cfg["true_params"]["theta_init"] = 0.02
        cfg["true_params"]["omega_init"] = -0.15
        cfg["model_params"]["theta_init"] = 0.02
        cfg["model_params"]["omega_init"] = -0.15
    elif condition == "larger_target_angle":
        target = float(np.deg2rad(105.0))
        cfg["true_params"]["theta_target"] = target
        cfg["model_params"]["theta_target"] = target
        cfg["mpc_params"]["target_theta"] = target
    elif condition == "tighter_alpha_limit":
        cfg["true_params"]["alpha_max"] = 2.0
        cfg["model_params"]["alpha_max"] = 2.0
        cfg["mpc_params"].setdefault("constraints", {})["alpha_max"] = 2.0
    return cfg


def _add_extra_fields(row: dict[str, Any], diag: dict[str, Any] | None = None) -> dict[str, Any]:
    diag = diag or {}
    enriched = dict(row)
    for key in EXTRA_FIELDS:
        if key in {"nmpc_solver_success", "nmpc_solver_failure", "nmpc_fallback_used"}:
            enriched[key] = bool(diag.get(key, False))
        elif key in {"nmpc_fallback_mode", "nmpc_solver_status", "nmpc_failure_reason"}:
            enriched[key] = str(diag.get(key, ""))
        elif key in {
            "nmpc_solver_iterations",
            "nmpc_alpha_slack_active_count_gt_1e_5",
            "nmpc_alpha_slack_active_count_gt_1e_4",
            "nmpc_alpha_slack_active_count_gt_1e_3",
            "nmpc_horizon",
        }:
            enriched[key] = int(diag.get(key, 0))
        else:
            enriched[key] = float(diag.get(key, np.nan))
    enriched["nmpc_solve_count"] = int(diag.get("mpc_solve_count", 0))
    return enriched


def run_nmpc_condition(method: str, condition: str, seed: int, condition_cfg: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
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
    wrapper = NoisySpring2DObservationWrapper(true_params, condition_cfg.get("observation_noise", {}), seed=int(condition_cfg.get("seed", seed)))
    obs_meas = wrapper.observe(obs_true)
    controller = AdaptiveScaledValidationNMPC(model_params, cfg["mpc_params"], method_variant(method))
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()
    filter_cfg = dict(cfg.get("observation_filter", {"type": "ukf_bias", "identifier_input": "filtered"}))
    filter_cfg["condition_name"] = condition
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
            "coupling_case": "stage9d_nmpc_stress_validation",
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
    rows.append(_add_extra_fields(initial_row))
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
            rows.append(_add_extra_fields(enriched, solve_diag))
            if env.is_done() or steps >= max_steps:
                break
    return rows


def _early_late(alpha_sev: np.ndarray, rows: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    t = _series(rows, "t")
    early = alpha_sev[t <= 0.5]
    late = alpha_sev[t > 0.5]
    return (
        _finite_percentile(early, 95),
        _finite_max(early),
        _finite_percentile(late, 95),
        _finite_max(late),
    )


def summarize_rows(method: str, condition: str, seed: int, phase: str, rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    final = rows[-1]
    true_params = cfg["true_params"]
    constraints = cfg["mpc_params"].get("constraints", {})
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    omega_abs = np.abs(_series(rows, "omega"))
    omega_sev = np.maximum(0.0, omega_abs - omega_max)
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_mag = np.linalg.norm(actions, axis=1)
    action_diff = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.array([])
    decisions = _decision_rows(rows, "nmpc_solve_count") if method in NMPC_METHODS else []
    early_p95, early_max, late_p95, late_max = _early_late(alpha_sev, rows)
    return {
        "phase": phase,
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "stress_override": stress_override_note(condition),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "solver_status_examples": "; ".join(sorted({str(row.get("nmpc_solver_status", ""))[:80] for row in decisions if str(row.get("nmpc_solver_status", ""))})[:3]),
        "solver_success_count": int(sum(bool(row.get("nmpc_solver_success", False)) for row in decisions)),
        "solver_failure_count": int(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions)),
        "solver_failure_rate": float(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "fallback_count": int(sum(bool(row.get("nmpc_fallback_used", False)) for row in decisions)),
        "fallback_rate": float(sum(bool(row.get("nmpc_fallback_used", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "solve_time_mean": _finite_mean(_series(decisions, "nmpc_solve_time_s")) if decisions else np.nan,
        "solve_time_max": _finite_max(_series(decisions, "nmpc_solve_time_s")) if decisions else np.nan,
        "ipopt_iterations_mean": _finite_mean(_series(decisions, "nmpc_solver_iterations")) if decisions else np.nan,
        "ipopt_iterations_max": _finite_max(_series(decisions, "nmpc_solver_iterations")) if decisions else np.nan,
        "objective_mean": _finite_mean(_series(decisions, "nmpc_objective")) if decisions else np.nan,
        "cost_task_mean": _finite_mean(_series(decisions, "nmpc_cost_task")) if decisions else np.nan,
        "cost_action_mean": _finite_mean(_series(decisions, "nmpc_cost_action")) if decisions else np.nan,
        "cost_action_rate_mean": _finite_mean(_series(decisions, "nmpc_cost_action_rate")) if decisions else np.nan,
        "cost_alpha_slack_l1_mean": _finite_mean(_series(decisions, "nmpc_cost_alpha_slack_l1")) if decisions else np.nan,
        "cost_alpha_slack_l2_mean": _finite_mean(_series(decisions, "nmpc_cost_alpha_slack_l2")) if decisions else np.nan,
        "cost_state_violation_mean": _finite_mean(_series(decisions, "nmpc_cost_state_violation")) if decisions else np.nan,
        "dynamics_residual_max": _finite_max(_series(decisions, "nmpc_dynamics_residual_max")) if decisions else np.nan,
        "dynamics_residual_mean": _finite_mean(_series(decisions, "nmpc_dynamics_residual_mean")) if decisions else np.nan,
        "constraint_violation_max": _finite_max(_series(decisions, "nmpc_constraint_violation_max")) if decisions else np.nan,
        "constraint_violation_mean": _finite_mean(_series(decisions, "nmpc_constraint_violation_mean")) if decisions else np.nan,
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_clipped_max": _clipped_max_excluding_one(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "alpha_integrated_violation": float(np.sum(alpha_sev) * dt),
        "alpha_early_p95": early_p95,
        "alpha_early_max": early_max,
        "alpha_late_p95": late_p95,
        "alpha_late_max": late_max,
        "slack_mean_raw": _finite_mean(_series(decisions, "nmpc_alpha_slack_mean_raw")) if decisions else np.nan,
        "slack_max_raw": _finite_max(_series(decisions, "nmpc_alpha_slack_max_raw")) if decisions else np.nan,
        "slack_active_count_gt_1e_5": int(np.nansum(_series(decisions, "nmpc_alpha_slack_active_count_gt_1e_5"))) if decisions else 0,
        "slack_active_count_gt_1e_4": int(np.nansum(_series(decisions, "nmpc_alpha_slack_active_count_gt_1e_4"))) if decisions else 0,
        "slack_active_count_gt_1e_3": int(np.nansum(_series(decisions, "nmpc_alpha_slack_active_count_gt_1e_3"))) if decisions else 0,
        "omega_abs_mean": _finite_mean(omega_abs),
        "omega_abs_p95": _finite_percentile(omega_abs, 95),
        "omega_abs_p99": _finite_percentile(omega_abs, 99),
        "omega_abs_max": _finite_max(omega_abs),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_violation_mean": _finite_mean(omega_sev),
        "omega_violation_p95": _finite_percentile(omega_sev, 95),
        "omega_violation_max": _finite_max(omega_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "force_violation_count": int(np.count_nonzero((F_tan_sev + F_rad_sev) > 0.0)),
        "force_max_severity": _finite_max(F_tan_sev + F_rad_sev),
        "mean_action_magnitude": _finite_mean(action_mag),
        "max_action_magnitude": _finite_max(action_mag),
        "action_smoothness": _finite_mean(action_diff),
        "action_total_variation": float(np.sum(action_diff)) if len(action_diff) else 0.0,
        "first_action_diff_vs_cem_mean": _finite_mean(_series(decisions, "nmpc_first_action_diff_vs_cem")) if decisions else np.nan,
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = list(
    summarize_rows(
        "baseline_cem",
        "clean",
        0,
        "dummy",
        [{"theta": 0.0, "omega": 0.0, "delta_r": 0.0, "F_tan": 0.0, "F_rad": 0.0, "alpha_step": 0.0, "target_reached": False, "t": 0.0}],
        {"true_params": {"dt": 0.01, "alpha_max": 3.0, "omega_max": 1.2, "delta_r_max": 0.06, "F_tan_max": 35.0, "F_rad_max": 1.0}, "mpc_params": {"constraints": {}}},
        0.0,
    ).keys()
)


def save_summary(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    keys = sorted({(row["method"], row["condition"]) for row in rows})
    for method, condition in keys:
        group = [row for row in rows if row["method"] == method and row["condition"] == condition]
        out.append(
            {
                "method": method,
                "condition": condition,
                "n": len(group),
                "target_success": int(sum(_as_bool(row["target_reached"]) for row in group)),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in group])),
                "solver_failure_rate_avg": _finite_mean(np.array([float(row["solver_failure_rate"]) for row in group])),
                "fallback_rate_avg": _finite_mean(np.array([float(row["fallback_rate"]) for row in group])),
                "solve_time_avg": _finite_mean(np.array([float(row["solve_time_mean"]) for row in group])),
                "ipopt_iter_avg": _finite_mean(np.array([float(row["ipopt_iterations_mean"]) for row in group])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in group])),
                "alpha_p99_avg": _finite_mean(np.array([float(row["alpha_p99_severity"]) for row in group])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in group])),
                "alpha_duration_avg": _finite_mean(np.array([float(row["alpha_violation_duration_s"]) for row in group])),
                "alpha_integral_avg": _finite_mean(np.array([float(row["alpha_integrated_violation"]) for row in group])),
                "slack_mean_avg": _finite_mean(np.array([float(row["slack_mean_raw"]) for row in group])),
                "slack_max_avg": _finite_mean(np.array([float(row["slack_max_raw"]) for row in group])),
                "slack_active_gt_1e_5_total": int(sum(int(row["slack_active_count_gt_1e_5"]) for row in group)),
                "slack_active_gt_1e_4_total": int(sum(int(row["slack_active_count_gt_1e_4"]) for row in group)),
                "slack_active_gt_1e_3_total": int(sum(int(row["slack_active_count_gt_1e_3"]) for row in group)),
                "omega_abs_p95_avg": _finite_mean(np.array([float(row["omega_abs_p95"]) for row in group])),
                "omega_abs_p99_avg": _finite_mean(np.array([float(row["omega_abs_p99"]) for row in group])),
                "omega_abs_max_avg": _finite_mean(np.array([float(row["omega_abs_max"]) for row in group])),
                "omega_violation_count_total": int(sum(int(row["omega_violation_count"]) for row in group)),
                "omega_violation_p95_avg": _finite_mean(np.array([float(row["omega_violation_p95"]) for row in group])),
                "omega_violation_max_avg": _finite_mean(np.array([float(row["omega_violation_max"]) for row in group])),
                "delta_r_count_total": int(sum(int(row["delta_r_violation_count"]) for row in group)),
                "force_count_total": int(sum(int(row["force_violation_count"]) for row in group)),
                "action_tv_avg": _finite_mean(np.array([float(row["action_total_variation"]) for row in group])),
            }
        )
    return out


def _agg_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["method"], row["condition"]): row for row in aggregate(rows)}


def save_plots(
    summary_rows: list[dict[str, Any]],
    output_root: Path,
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]] | None = None,
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    agg = aggregate(summary_rows)
    methods = [method for method in METHODS if any(row["method"] == method for row in agg)]
    conditions = [condition for condition in CONDITIONS if any(row["condition"] == condition for row in agg)]
    for metric, ylabel, filename in [
        ("alpha_p95_avg", "alpha p95 severity", "alpha_p95_bar.png"),
        ("alpha_p99_avg", "alpha p99 severity", "alpha_p99_bar.png"),
        ("alpha_max_avg", "alpha max severity", "alpha_max_bar.png"),
        ("alpha_duration_avg", "alpha violation duration [s]", "alpha_duration_bar.png"),
        ("alpha_integral_avg", "integrated alpha violation", "alpha_integral_bar.png"),
        ("slack_max_avg", "slack max", "slack_max_bar.png"),
        ("slack_active_gt_1e_5_total", "slack active count >1e-5", "slack_active_gt_1e_5_bar.png"),
        ("slack_active_gt_1e_4_total", "slack active count >1e-4", "slack_active_gt_1e_4_bar.png"),
        ("slack_active_gt_1e_3_total", "slack active count >1e-3", "slack_active_gt_1e_3_bar.png"),
        ("omega_abs_p95_avg", "raw |omega| p95 [rad/s]", "raw_omega_p95_bar.png"),
        ("omega_abs_max_avg", "raw |omega| max [rad/s]", "raw_omega_max_bar.png"),
        ("omega_violation_p95_avg", "omega violation p95", "omega_violation_p95_bar.png"),
        ("omega_violation_max_avg", "omega violation max", "omega_violation_max_bar.png"),
        ("solve_time_avg", "solve time [s]", "solve_time_bar.png"),
        ("solver_failure_rate_avg", "solver failure rate", "solver_failure_bar.png"),
        ("target_success", "target successes", "target_success_bar.png"),
    ]:
        fig, ax = plt.subplots(figsize=(12, 5))
        x = np.arange(len(methods))
        width = 0.8 / max(len(conditions), 1)
        for j, condition in enumerate(conditions):
            vals = []
            for method in methods:
                match = next((row for row in agg if row["method"] == method and row["condition"] == condition), None)
                vals.append(float(match[metric]) if match else np.nan)
            ax.bar(x + (j - (len(conditions) - 1) / 2) * width, vals, width=width, label=condition)
        ax.set_xticks(x)
        ax.set_xticklabels(methods, rotation=25, ha="right")
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / filename, dpi=150)
        plt.close(fig)

    if not all_runs:
        return
    colors = {
        "baseline_cem": "tab:blue",
        "alpha200_omega0": "tab:orange",
        "nmpc_rho100_scaled": "tab:green",
        "nmpc_rho1000_scaled": "tab:purple",
        "nmpc_rho100_scaled_with_cem_fallback": "tab:red",
    }
    for condition in [condition for condition in CONDITIONS if any(key[1] == condition for key in all_runs)]:
        for key, ylabel, filename in [
            ("theta", "theta [deg]", "theta_trajectories"),
            ("alpha_step", "alpha [rad/s^2]", "alpha_trajectories"),
            ("omega", "raw omega [rad/s]", "raw_omega_trajectories"),
            ("nmpc_alpha_slack_max_raw", "alpha slack max", "alpha_slack_trajectories"),
        ]:
            fig, ax = plt.subplots(figsize=(12, 5))
            for method in METHODS:
                matching = [(seed, rows) for (m, c, seed), rows in all_runs.items() if m == method and c == condition]
                for idx, (seed, rows) in enumerate(sorted(matching)):
                    y = _series(rows, key)
                    if key == "theta":
                        y = np.degrees(y)
                    label = method if idx == 0 else None
                    ax.plot(_series(rows, "t"), y, color=colors[method], alpha=0.35, linewidth=1.0, label=label)
            if key == "theta":
                sample = next(rows for (m, c, seed), rows in all_runs.items() if c == condition)
                target = np.degrees(float(sample[-1]["theta_target_final"]))
                ax.axhline(target, color="black", linestyle=":", linewidth=1.0, label="theta_target")
            if key == "alpha_step":
                alpha_threshold = 2.0 if condition == "tighter_alpha_limit" else 3.0
                ax.axhline(alpha_threshold, color="black", linestyle=":", linewidth=1.0, label="alpha threshold")
                ax.axhline(-alpha_threshold, color="black", linestyle=":", linewidth=1.0)
            ax.set_title(f"{condition}: {filename.replace('_', ' ')}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}.png", dpi=150)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))
        omega_limit = 1.2
        for method in METHODS:
            matching = [(seed, rows) for (m, c, seed), rows in all_runs.items() if m == method and c == condition]
            for idx, (seed, rows) in enumerate(sorted(matching)):
                label = method if idx == 0 else None
                omega_violation = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_limit)
                ax.plot(_series(rows, "t"), omega_violation, color=colors[method], alpha=0.35, linewidth=1.0, label=label)
        ax.set_title(f"{condition}: omega violation trajectories")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("omega violation [rad/s]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_omega_violation_trajectories.png", dpi=150)
        plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        for method in METHODS:
            matching = [(seed, rows) for (m, c, seed), rows in all_runs.items() if m == method and c == condition]
            for idx, (seed, rows) in enumerate(sorted(matching)):
                label = method if idx == 0 else None
                t = _series(rows, "t")
                axes[0].plot(t, _series(rows, "F_tan"), color=colors[method], alpha=0.35, linewidth=1.0, label=label)
                axes[1].plot(t, _series(rows, "F_rad"), color=colors[method], alpha=0.35, linewidth=1.0)
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


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str], stress_skipped_reason: str | None) -> None:
    agg = _agg_map(summary_rows)
    aggregate_rows = aggregate(summary_rows)

    def row(method: str, condition: str) -> dict[str, Any] | None:
        return agg.get((method, condition))

    def count_conditions(predicate: Any) -> int:
        return sum(1 for condition in CONDITIONS if row("baseline_cem", condition) and row("nmpc_rho100_scaled", condition) and predicate(condition))

    available_conditions = [condition for condition in CONDITIONS if row("nmpc_rho100_scaled", condition)]
    n_available = len(available_conditions)
    target_preserved_conditions = count_conditions(
        lambda condition: int(row("nmpc_rho100_scaled", condition)["target_success"]) >= int(row("baseline_cem", condition)["target_success"])
    )
    alpha_reduced_conditions = count_conditions(
        lambda condition: (
            float(row("nmpc_rho100_scaled", condition)["alpha_p95_avg"]) < float(row("baseline_cem", condition)["alpha_p95_avg"])
            and float(row("nmpc_rho100_scaled", condition)["alpha_p99_avg"]) < float(row("baseline_cem", condition)["alpha_p99_avg"])
            and float(row("nmpc_rho100_scaled", condition)["alpha_max_avg"]) < float(row("baseline_cem", condition)["alpha_max_avg"])
            and float(row("nmpc_rho100_scaled", condition)["alpha_duration_avg"]) <= float(row("baseline_cem", condition)["alpha_duration_avg"])
            and float(row("nmpc_rho100_scaled", condition)["alpha_integral_avg"]) < float(row("baseline_cem", condition)["alpha_integral_avg"])
        )
    )
    raw_omega_not_worse_conditions = count_conditions(
        lambda condition: float(row("nmpc_rho100_scaled", condition)["omega_abs_max_avg"]) <= float(row("baseline_cem", condition)["omega_abs_max_avg"]) + 1.0e-9
    )
    delta_r_not_worse_conditions = count_conditions(
        lambda condition: int(row("nmpc_rho100_scaled", condition)["delta_r_count_total"]) <= int(row("baseline_cem", condition)["delta_r_count_total"])
    )
    force_not_worse_conditions = count_conditions(
        lambda condition: int(row("nmpc_rho100_scaled", condition)["force_count_total"]) <= int(row("baseline_cem", condition)["force_count_total"])
    )
    rho1000_better_conditions = sum(
        1
        for condition in available_conditions
        if row("nmpc_rho1000_scaled", condition)
        and float(row("nmpc_rho1000_scaled", condition)["alpha_max_avg"]) < float(row("nmpc_rho100_scaled", condition)["alpha_max_avg"])
        and int(row("nmpc_rho1000_scaled", condition)["target_success"]) >= int(row("nmpc_rho100_scaled", condition)["target_success"])
    )
    fallback_help_conditions = sum(
        1
        for condition in available_conditions
        if row("nmpc_rho100_scaled_with_cem_fallback", condition)
        and (
            float(row("nmpc_rho100_scaled_with_cem_fallback", condition)["fallback_rate_avg"]) > 0.0
            or int(row("nmpc_rho100_scaled_with_cem_fallback", condition)["target_success"]) > int(row("nmpc_rho100_scaled", condition)["target_success"])
        )
    )
    break_conditions = [
        condition
        for condition in available_conditions
        if int(row("nmpc_rho100_scaled", condition)["target_success"]) < int(row("nmpc_rho100_scaled", condition)["n"])
        or float(row("nmpc_rho100_scaled", condition)["solver_failure_rate_avg"]) > 0.2
    ]
    clean_nmpc = row("nmpc_rho100_scaled", "clean")
    stress_successful = (
        stress_skipped_reason is None
        and n_available == len(CONDITIONS)
        and target_preserved_conditions == n_available
        and alpha_reduced_conditions >= max(1, n_available - 1)
        and clean_nmpc is not None
        and float(clean_nmpc["solver_failure_rate_avg"]) <= 0.05
    )
    if stress_skipped_reason:
        next_step = "NMPC refinement; stress validation was stopped."
    elif stress_successful and not break_conditions:
        next_step = "paper/report consolidation or linked rods preparation, while keeping NMPC refinement as engineering follow-up."
    elif alpha_reduced_conditions >= max(1, n_available // 2) and target_preserved_conditions == n_available:
        next_step = "NMPC refinement before linked rods preparation."
    else:
        next_step = "alpha/task redesign before linked rods preparation."
    lines = [
        "# Stage 9D NMPC Sanity Check and Stress Validation Report",
        "",
        "## Scope",
        "- Logging sanity check plus stress validation for the Stage 9C scaled multiple-shooting alpha-slack NMPC.",
        "- Stage 9C omega p95/max columns were omega violation severity, not raw omega. Stage 9D logs raw omega and violation severity separately.",
        f"- Slack activity is reported at thresholds {', '.join(f'{x:g}' for x in SLACK_ACTIVE_THRESHOLDS)}.",
        f"- Seeds: {SEEDS}. Three seeds are used because this stress matrix covers 10 conditions x 5 methods.",
        "- No broad tuning and no formal safety claims.",
        "",
        "## Commands Run",
        *[f"- `{cmd}`" for cmd in commands],
        "",
        "## Aggregate Metrics",
        "| method | condition | target | fail rate | fallback | solve | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack >1e-5/>1e-4/>1e-3 | raw omega p95/max | omega viol p95/max | delta_r | force |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row_data in aggregate_rows:
        lines.append(
            f"| {row_data['method']} | {row_data['condition']} | {row_data['target_success']}/{row_data['n']} | "
            f"{_fmt(row_data['solver_failure_rate_avg'])} | {_fmt(row_data['fallback_rate_avg'])} | {_fmt(row_data['solve_time_avg'])} | "
            f"{_fmt(row_data['alpha_p95_avg'])} | {_fmt(row_data['alpha_p99_avg'])} | {_fmt(row_data['alpha_max_avg'])} | "
            f"{_fmt(row_data['alpha_duration_avg'])} | {_fmt(row_data['alpha_integral_avg'])} | {_fmt(row_data['slack_mean_avg'])} | "
            f"{_fmt(row_data['slack_max_avg'])} | {row_data['slack_active_gt_1e_5_total']}/{row_data['slack_active_gt_1e_4_total']}/{row_data['slack_active_gt_1e_3_total']} | "
            f"{_fmt(row_data['omega_abs_p95_avg'])}/{_fmt(row_data['omega_abs_max_avg'])} | "
            f"{_fmt(row_data['omega_violation_p95_avg'])}/{_fmt(row_data['omega_violation_max_avg'])} | "
            f"{row_data['delta_r_count_total']} | {row_data['force_count_total']} |"
        )
    if stress_skipped_reason:
        lines.extend(["", "## Stop Condition", f"- Stress validation skipped/stopped: {stress_skipped_reason}"])
    lines.extend(
        [
            "",
            "## Stress Overrides",
            *[f"- `{condition}`: {stress_override_note(condition)}" for condition in CONDITIONS],
            "",
            "## Required Answers",
            "1. Was omega logging in Stage 9C raw omega or omega violation?",
            "- Stage 9C reported omega violation severity. Stage 9D distinguishes `omega_abs_*` raw absolute omega from `omega_violation_*` severity.",
            "",
            "2. Is alpha slack genuinely active, or mostly numerical boundary contact?",
            f"- Use the threshold split. Across available rho100 conditions, slack active counts are >1e-5/>1e-4/>1e-3 = "
            f"{sum(int(row_data['slack_active_gt_1e_5_total']) for row_data in aggregate_rows if row_data['method'] == 'nmpc_rho100_scaled')}/"
            f"{sum(int(row_data['slack_active_gt_1e_4_total']) for row_data in aggregate_rows if row_data['method'] == 'nmpc_rho100_scaled')}/"
            f"{sum(int(row_data['slack_active_gt_1e_3_total']) for row_data in aggregate_rows if row_data['method'] == 'nmpc_rho100_scaled')}. "
            "If the count collapses at 1e-4 or 1e-3, most activity is numerical boundary contact rather than meaningful slack.",
            "",
            "3. Does NMPC preserve target reaching under stress?",
            f"- {'Yes' if target_preserved_conditions == n_available else 'No/mixed'}: rho100 target success is at least baseline in {target_preserved_conditions}/{n_available} available conditions.",
            "",
            "4. Does NMPC reduce alpha p95/p99/max/duration/integral vs baseline under stress?",
            f"- {'Yes' if alpha_reduced_conditions == n_available else 'Mixed'}: rho100 improves all tracked alpha aggregate metrics vs baseline in {alpha_reduced_conditions}/{n_available} available conditions.",
            "",
            "5. Does NMPC avoid worsening raw omega, delta_r, and force safety?",
            f"- Raw omega max is not worse than baseline in {raw_omega_not_worse_conditions}/{n_available} conditions; delta_r count not worse in {delta_r_not_worse_conditions}/{n_available}; force count not worse in {force_not_worse_conditions}/{n_available}.",
            "",
            "6. Is rho100 enough, or does rho1000 improve robustness?",
            f"- rho1000 beats rho100 on alpha max without target loss in {rho1000_better_conditions}/{n_available} available conditions. Treat rho100 as sufficient unless this count is broad and material.",
            "",
            "7. Does fallback materially improve robustness?",
            f"- {'Yes/mixed' if fallback_help_conditions else 'No material effect observed'}: fallback has nonzero use or target improvement in {fallback_help_conditions}/{n_available} available conditions.",
            "",
            "8. Which stress condition breaks NMPC first, if any?",
            f"- {'No break condition observed' if not break_conditions else ', '.join(break_conditions)}.",
            "",
            "9. Is solve time acceptable for this small system?",
            f"- {'Yes for offline/small-system validation' if clean_nmpc and float(clean_nmpc['solve_time_avg']) < 0.1 else 'No/marginal'}: clean rho100 mean solve time={_fmt(clean_nmpc['solve_time_avg']) if clean_nmpc else 'nan'} s.",
            "",
            "10. Should the next step be NMPC refinement, alpha/task redesign, linked rods preparation, or paper/report consolidation?",
            f"- Recommended next step: {next_step}",
        ]
    )
    (output_root / "stage9d_report.md").write_text("\n".join(lines) + "\n")


def sanity_phase_reasonable(summary_rows: list[dict[str, Any]]) -> tuple[bool, str | None]:
    agg = _agg_map(summary_rows)
    for condition in SANITY_CONDITIONS:
        row = agg.get(("nmpc_rho100_scaled", condition))
        if row is None:
            return False, f"missing {condition} nmpc_rho100_scaled result"
        if float(row["solver_failure_rate_avg"]) > 0.2:
            return False, f"{condition} solver failure rate was {row['solver_failure_rate_avg']:.3g}"
    return True, None


def run(output_root: Path, config_path: Path) -> None:
    try:
        casadi_version = ca.__version__
    except Exception as exc:
        raise RuntimeError("CasADi unavailable for Stage 9D.") from exc
    print(f"[stage9d] CasADi {casadi_version}; seeds={SEEDS}", flush=True)
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]
    summary_rows: list[dict[str, Any]] = []
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]] = {}

    def run_one(method: str, condition: str, seed: int, phase: str) -> None:
        print(f"[stage9d] running {phase} {method}/{condition}/seed{seed}", flush=True)
        condition_cfg = condition_with_seed(base_cfg, condition, seed)
        if method in {"baseline_cem", "alpha200_omega0"}:
            cfg = apply_stage9d_overrides(configure_cem_seeded(base_cfg, method, seed), condition)
            start = time.perf_counter()
            rows = run_condition(condition, condition_cfg, cfg)
        else:
            cfg = apply_stage9d_overrides(configure_nmpc_run(base_cfg, method, seed), condition)
            start = time.perf_counter()
            rows = run_nmpc_condition(method, condition, seed, condition_cfg, cfg)
        runtime_s = time.perf_counter() - start
        all_runs[(method, condition, int(seed))] = rows
        summary = summarize_rows(method, condition, seed, phase, rows, cfg, runtime_s)
        summary_rows.append(summary)
        print(
            "[stage9d] "
            f"{method}/{condition}/seed{seed}: target={summary['target_reached']}, "
            f"fail={summary['solver_failure_rate']:.4g}, alpha_p95={summary['alpha_p95_severity']:.4g}, "
            f"alpha_max={summary['alpha_max_severity']:.4g}, solve={summary['solve_time_mean']:.4g}s, runtime={runtime_s:.2f}s",
            flush=True,
        )

    for condition in SANITY_CONDITIONS:
        for seed in SEEDS:
            for method in METHODS:
                run_one(method, condition, seed, "sanity")
    ok, reason = sanity_phase_reasonable(summary_rows)
    stress_skipped_reason = None
    if ok:
        for condition in STRESS_CONDITIONS:
            for seed in SEEDS:
                for method in METHODS:
                    run_one(method, condition, seed, "stress")
    else:
        stress_skipped_reason = reason
    save_summary(summary_rows, output_root / "stage9d_summary.csv")
    save_plots(summary_rows, output_root, all_runs)
    save_report(summary_rows, output_root, commands, stress_skipped_reason)
    print(f"[stage9d] summary: {output_root / 'stage9d_summary.csv'}", flush=True)
    print(f"[stage9d] report : {output_root / 'stage9d_report.md'}", flush=True)
    print(f"[stage9d] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
