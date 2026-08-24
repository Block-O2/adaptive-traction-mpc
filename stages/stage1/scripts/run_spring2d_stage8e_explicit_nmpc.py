"""Stage 8E explicit constrained NMPC baseline for Spring2D single-link."""

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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

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
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.cost import Spring2DMPCWeights, stage_cost, terminal_cost
from traction_mpc.mpc.safety_filter import SafetyFilterResult


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage8e_explicit_nmpc"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = ["baseline_cem", "alpha200_omega0", "nmpc_alpha_slack"]
NMPC_EXTRA_FIELDS = [
    "nmpc_solver_success",
    "nmpc_solver_failure",
    "nmpc_solve_time_s",
    "nmpc_solver_iterations",
    "nmpc_solver_message",
    "nmpc_cost",
    "nmpc_alpha_slack_mean",
    "nmpc_alpha_slack_max",
    "nmpc_alpha_slack_active_count",
    "nmpc_pred_alpha_max",
    "nmpc_pred_omega_max",
    "nmpc_pred_delta_r_max",
    "nmpc_horizon",
]


class DirectShootingAlphaSlackNMPC:
    """Small direct-shooting NMPC with implicit alpha slack penalties."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any]):
        self.model_params = dict(model_params)
        self.mpc_params = dict(mpc_params)
        self.target_theta = float(mpc_params.get("target_theta", model_params["theta_target"]))
        solver_cfg = dict(mpc_params.get("solver", {}))
        nmpc_cfg = dict(mpc_params.get("nmpc", {}))
        self.horizon = int(nmpc_cfg.get("horizon", min(18, int(solver_cfg.get("horizon", 18)))))
        self.prediction_dt = float(nmpc_cfg.get("prediction_dt", solver_cfg.get("prediction_dt", model_params["dt"])))
        self.maxiter = int(nmpc_cfg.get("maxiter", 18))
        self.maxfun = int(nmpc_cfg.get("maxfun", 220))
        self.ftol = float(nmpc_cfg.get("ftol", 1.0e-3))
        self.alpha_slack_l1 = float(nmpc_cfg.get("alpha_slack_l1", 2500.0))
        self.alpha_slack_l2 = float(nmpc_cfg.get("alpha_slack_l2", 250.0))
        self.state_violation_l2 = float(nmpc_cfg.get("state_violation_l2", 5.0e5))
        self.nominal_cfg = dict(mpc_params.get("nominal_policy", {}))
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.prediction_dt,
        )
        self.weights = Spring2DMPCWeights.from_config(mpc_params.get("weights", {}))
        self.last_solution = np.zeros((self.horizon, 2), dtype=float)
        self.last_action = np.zeros(2, dtype=float)
        self.solve_count = 0
        self.last_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.last_solution = np.zeros((self.horizon, 2), dtype=float)
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
        initial_sequence = self._initial_sequence(state)
        bounds = []
        for _ in range(self.horizon):
            bounds.append((-self.constraints.F_tan_max, self.constraints.F_tan_max))
            bounds.append((-self.constraints.F_rad_max, self.constraints.F_rad_max))
        start = time.perf_counter()
        result = minimize(
            self._objective,
            initial_sequence.reshape(-1),
            args=(state,),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": self.maxiter, "maxfun": self.maxfun, "ftol": self.ftol},
        )
        solve_time = time.perf_counter() - start
        if result.x is not None and np.all(np.isfinite(result.x)):
            sequence = np.asarray(result.x, dtype=float).reshape(self.horizon, 2)
        else:
            sequence = initial_sequence.copy()
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        stats = self._rollout_stats(state, sequence)
        self.last_solution = sequence.copy()
        self.last_action = self.constraints.clip_action(sequence[0])
        self.solve_count += 1
        self.last_diagnostics = {
            "nmpc_solver_success": bool(result.success),
            "nmpc_solver_failure": not bool(result.success),
            "nmpc_solve_time_s": float(solve_time),
            "nmpc_solver_iterations": int(getattr(result, "nit", 0)),
            "nmpc_solver_message": str(getattr(result, "message", "")),
            "nmpc_cost": float(result.fun) if np.isfinite(result.fun) else float("inf"),
            "nmpc_alpha_slack_mean": float(stats["alpha_slack_mean"]),
            "nmpc_alpha_slack_max": float(stats["alpha_slack_max"]),
            "nmpc_alpha_slack_active_count": int(stats["alpha_slack_active_count"]),
            "nmpc_pred_alpha_max": float(stats["pred_alpha_max"]),
            "nmpc_pred_omega_max": float(stats["pred_omega_max"]),
            "nmpc_pred_delta_r_max": float(stats["pred_delta_r_max"]),
            "nmpc_horizon": int(self.horizon),
            "mpc_solve_count": int(self.solve_count),
        }
        return self.last_action.copy()

    def get_last_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diagnostics)

    def _initial_sequence(self, state: np.ndarray) -> np.ndarray:
        shifted = np.zeros_like(self.last_solution)
        if len(self.last_solution) > 1:
            shifted[:-1] = self.last_solution[1:]
            shifted[-1] = self.last_solution[-1]
        heuristic = self._heuristic_sequence(state)
        blend = float(self.nominal_cfg.get("warm_start_blend", 0.35))
        sequence = blend * shifted + (1.0 - blend) * heuristic
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence

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

    def _objective(self, flat_sequence: np.ndarray, state: np.ndarray) -> float:
        sequence = np.asarray(flat_sequence, dtype=float).reshape(self.horizon, 2)
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        x = np.asarray(state, dtype=float).copy()
        total_cost = 0.0
        for action in sequence:
            prev_x = x.copy()
            try:
                x = step_dynamics(x, action, self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                return 1.0e12
            if not np.all(np.isfinite(x)):
                return 1.0e12
            total_cost += stage_cost(
                x,
                action,
                prev_x[1],
                self.prediction_dt,
                self.target_theta,
                self.model_params,
                self.weights,
            )
            alpha = (float(x[1]) - float(prev_x[1])) / self.prediction_dt
            alpha_slack = max(0.0, abs(alpha) - self.constraints.alpha_max)
            delta_r = float(x[2] - self.model_params["L0"])
            delta_slack = max(0.0, abs(delta_r) - self.constraints.delta_r_max)
            omega_slack = max(0.0, abs(float(x[1])) - self.constraints.omega_max)
            total_cost += self.alpha_slack_l1 * alpha_slack + self.alpha_slack_l2 * alpha_slack**2
            total_cost += self.state_violation_l2 * (delta_slack**2 + omega_slack**2)
        total_cost += terminal_cost(x, self.target_theta, self.model_params, self.weights)
        return float(total_cost) if np.isfinite(total_cost) else 1.0e12

    def _rollout_stats(self, state: np.ndarray, sequence: np.ndarray) -> dict[str, float]:
        x = np.asarray(state, dtype=float).copy()
        alpha_slacks = []
        pred_alpha_max = 0.0
        pred_omega_max = 0.0
        pred_delta_r_max = 0.0
        for action in sequence:
            prev_x = x.copy()
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                break
            if not np.all(np.isfinite(x)):
                break
            alpha = (float(x[1]) - float(prev_x[1])) / self.prediction_dt
            delta_r = float(x[2] - self.model_params["L0"])
            slack = max(0.0, abs(alpha) - self.constraints.alpha_max)
            alpha_slacks.append(slack)
            pred_alpha_max = max(pred_alpha_max, abs(alpha))
            pred_omega_max = max(pred_omega_max, abs(float(x[1])))
            pred_delta_r_max = max(pred_delta_r_max, abs(delta_r))
        values = np.asarray(alpha_slacks, dtype=float)
        return {
            "alpha_slack_mean": float(np.mean(values)) if len(values) else np.nan,
            "alpha_slack_max": float(np.max(values)) if len(values) else np.nan,
            "alpha_slack_active_count": int(np.count_nonzero(values > 0.0)),
            "pred_alpha_max": float(pred_alpha_max),
            "pred_omega_max": float(pred_omega_max),
            "pred_delta_r_max": float(pred_delta_r_max),
        }


class AdaptiveNMPC:
    estimated_parameter_names = ("m", "k", "b_r")

    def __init__(self, initial_model_params: dict[str, Any], mpc_params: dict[str, Any]):
        self.model_params = dict(initial_model_params)
        self.mpc_params = dict(mpc_params)
        self.current_model_params = dict(initial_model_params)
        self.controller = DirectShootingAlphaSlackNMPC(self.current_model_params, self.mpc_params)
        self.last_update_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.current_model_params = dict(self.model_params)
        self.controller = DirectShootingAlphaSlackNMPC(self.current_model_params, self.mpc_params)
        self.controller.reset()
        self.last_update_diagnostics = {}

    def act(self, observation: Any) -> np.ndarray:
        return self.controller.act(observation)

    def set_target_theta(self, target_theta: float) -> None:
        self.controller.set_target_theta(float(target_theta))

    def get_last_solve_diagnostics(self) -> dict[str, Any]:
        return self.controller.get_last_diagnostics()

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
        self.controller.set_model_params({name: float(new_params[name]) for name in self.estimated_parameter_names})
        self.last_update_diagnostics = {
            "mpc_recreated_on_update": False,
            "solver_recreated_on_update": False,
            "last_action_preserved_on_update": True,
            "last_solution_existed_before_update": True,
            "last_solution_preserved_on_update": True,
        }
        return self.get_current_parameter_estimate()


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row.get(key, np.nan)) for row in rows], dtype=float)


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def _finite_mean(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.mean(values)) if len(values) else np.nan


def _finite_max(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.max(values)) if len(values) else np.nan


def _finite_percentile(values: np.ndarray, q: float) -> float:
    values = _finite(values)
    return float(np.percentile(values, q)) if len(values) else np.nan


def _clipped_max_excluding_one(values: np.ndarray) -> float:
    values = np.sort(_finite(values))
    if len(values) == 0:
        return np.nan
    if len(values) == 1:
        return 0.0
    return float(values[-2])


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return np.nan


def _decision_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[int] = set()
    decisions = []
    for row in rows:
        solve_count = int(row.get(key, 0))
        if solve_count <= 0 or solve_count in seen:
            continue
        seen.add(solve_count)
        decisions.append(row)
    return decisions


def configure_cem_run(base_cfg: dict[str, Any], method: str) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["action_parameterization_mode"] = "standard"
    solver["gatekeeper_mode"] = "off"
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    if method == "baseline_cem":
        solver["safety_mode"] = "off"
        solver["alpha_constraint_mode"] = "soft"
        solver["alpha_soft_weight"] = 1.0
    elif method == "alpha200_omega0":
        solver["safety_mode"] = "soft_penalty"
        solver["alpha_constraint_mode"] = "soft"
        solver["alpha_soft_weight"] = 200.0
        solver["safety_penalty_weight"] = 1.0
        weights = dict(solver.get("safety_violation_weights", {}))
        weights.update({"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 0.0, "alpha": 1.0})
        solver["safety_violation_weights"] = weights
    else:
        raise ValueError(f"Unknown CEM method: {method}")
    return cfg


def configure_nmpc_run(base_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = "off"
    solver["alpha_constraint_mode"] = "soft"
    solver["alpha_soft_weight"] = 1.0
    cfg["mpc_params"]["nmpc"] = {
        "horizon": int(solver.get("horizon", 18)),
        "prediction_dt": float(solver.get("prediction_dt", cfg["true_params"]["dt"])),
        "maxiter": 18,
        "maxfun": 220,
        "ftol": 1.0e-3,
        "alpha_slack_l1": 2500.0,
        "alpha_slack_l2": 250.0,
        "state_violation_l2": 5.0e5,
    }
    return cfg


def _add_nmpc_fields(row: dict[str, Any], solve_diag: dict[str, Any] | None = None) -> dict[str, Any]:
    diag = solve_diag or {}
    enriched = dict(row)
    for key in NMPC_EXTRA_FIELDS:
        if key in {"nmpc_solver_success", "nmpc_solver_failure"}:
            enriched[key] = bool(diag.get(key, False))
        elif key == "nmpc_solver_message":
            enriched[key] = str(diag.get(key, ""))
        elif key in {"nmpc_solver_iterations", "nmpc_alpha_slack_active_count", "nmpc_horizon"}:
            enriched[key] = int(diag.get(key, 0))
        else:
            enriched[key] = float(diag.get(key, np.nan))
    enriched["nmpc_solve_count"] = int(diag.get("mpc_solve_count", 0))
    return enriched


def run_nmpc_condition(condition_name: str, condition_cfg: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    adaptive_cfg = cfg.get("adaptive", {})
    alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 0.5))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    target_theta = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    coupling_cfg = dict(cfg.get("coupling_ablation", {}))
    coupling_name = str(coupling_cfg.get("name", "stage8e_nmpc"))
    mpc_state_input = str(coupling_cfg.get("mpc_state_input", "filtered")).lower()
    identifier_input = str(coupling_cfg.get("identifier_input", "filtered")).lower()
    identifier_mode = str(coupling_cfg.get("identifier_mode", "adaptive")).lower()
    estimator_model_params_source = str(coupling_cfg.get("estimator_model_params_source", "adaptive")).lower()
    mpc_model_params_source = str(coupling_cfg.get("mpc_model_params_source", "adaptive")).lower()

    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(
        true_params,
        condition_cfg.get("observation_noise", {}),
        seed=int(condition_cfg.get("seed", 0)),
    )
    obs_meas = wrapper.observe(obs_true)
    controller = AdaptiveNMPC(model_params, cfg["mpc_params"])
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
    filt_state = obs_filter.reset(
        obs_meas,
        true_state=observation_to_state(obs_true),
        model_params=initial_filter_model_params,
    )
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
                result = identifier.add_transition(
                    observation_to_state(id_prev),
                    action_exec,
                    observation_to_state(id_next),
                )
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


def summarize_rows(
    method: str,
    condition: str,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
) -> dict[str, Any]:
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
    decisions = _decision_rows(rows, "nmpc_solve_count") if method == "nmpc_alpha_slack" else []
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
        "solver_failure_rate": (
            float(sum(bool(row.get("nmpc_solver_failure", False)) for row in decisions) / len(decisions))
            if decisions
            else np.nan
        ),
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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _aggregate(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        method_rows = [row for row in summary_rows if row["method"] == method]
        rows.append(
            {
                "method": method,
                "target_success_count": int(sum(_as_bool(row["target_reached"]) for row in method_rows)),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "solver_failure_rate_avg": _finite_mean(np.array([float(row["solver_failure_rate"]) for row in method_rows])),
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
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "runtime_avg": _finite_mean(np.array([float(row["runtime_s"]) for row in method_rows])),
            }
        )
    return rows


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_plots(
    summary_rows: list[dict[str, Any]],
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    output_root: Path,
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    colors = {"baseline_cem": "tab:blue", "alpha200_omega0": "tab:orange", "nmpc_alpha_slack": "tab:green"}
    for condition in CONDITIONS:
        for key, ylabel, filename in [
            ("theta", "theta [deg]", "theta_trajectories"),
            ("alpha_step", "alpha [rad/s^2]", "alpha_trajectories"),
            ("omega", "omega [rad/s]", "omega_trajectories"),
        ]:
            fig, ax = plt.subplots(figsize=(11, 5))
            for method in METHODS:
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
        for method in METHODS:
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

    aggregate = _aggregate(summary_rows)
    x = np.arange(len(METHODS))
    width = 0.18
    metric_specs = [
        ("alpha_p95_avg", "p95"),
        ("alpha_p99_avg", "p99"),
        ("alpha_max_avg", "max"),
        ("alpha_slack_max_avg", "slack max"),
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    for idx, (metric, label) in enumerate(metric_specs):
        ax.bar(x + (idx - 1.5) * width, [float(row[metric]) for row in aggregate], width=width, label=label)
    ax.set_ylabel("alpha severity / slack")
    ax.set_xticks(x)
    ax.set_xticklabels(METHODS, rotation=20, ha="right")
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
    axes[1].set_xticklabels(METHODS, rotation=20, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage 8E: solve time and solver failures")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "solve_time_solver_failures.png", dpi=150)
    plt.close(fig)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = {row["method"]: row for row in _aggregate(summary_rows)}
    baseline = aggregate["baseline_cem"]
    alpha200 = aggregate["alpha200_omega0"]
    nmpc = aggregate["nmpc_alpha_slack"]
    nmpc_preserves = int(nmpc["target_success_count"]) == len(CONDITIONS)
    nmpc_reduces_alpha = (
        float(nmpc["alpha_p95_avg"]) < float(baseline["alpha_p95_avg"])
        and float(nmpc["alpha_p99_avg"]) < float(baseline["alpha_p99_avg"])
        and float(nmpc["alpha_max_avg"]) < float(baseline["alpha_max_avg"])
    )
    nmpc_avoids_other = (
        float(nmpc["omega_p95_avg"]) <= float(baseline["omega_p95_avg"])
        and int(nmpc["delta_r_count_total"]) <= int(baseline["delta_r_count_total"])
        and int(nmpc["force_count_total"]) <= int(baseline["force_count_total"])
    )
    solve_time_ok = (
        np.isfinite(float(nmpc["solve_time_avg"]))
        and float(nmpc["solve_time_avg"]) < 0.25
        and np.isfinite(float(nmpc["solver_failure_rate_avg"]))
        and float(nmpc["solver_failure_rate_avg"]) < 0.2
    )
    if nmpc_preserves and nmpc_reduces_alpha and nmpc_avoids_other:
        next_step = "NMPC refinement and stress validation."
    elif nmpc_preserves and (float(nmpc["alpha_p95_avg"]) < float(baseline["alpha_p95_avg"])):
        next_step = "NMPC refinement, focused on alpha max and solve robustness."
    else:
        next_step = "task/constraint revision before linked rods; NMPC alone did not resolve the conflict."
    lines = [
        "# Stage 8E Explicit Constrained NMPC Report",
        "",
        "## Scope",
        "- Diagnosis only: tested a minimal explicit direct-shooting NMPC baseline with alpha slack.",
        "- Baseline CEM and alpha200 reference use existing CEM code.",
        "- NMPC freezes current estimated [m, k, b_r] over each horizon and updates between MPC solves via the existing filtered Windowed NLS flow.",
        "- Force bounds are hard via optimizer bounds; delta_r and omega are hard-ish quadratic penalties; alpha uses implicit L1+L2 slack penalty.",
        "- Dynamics, estimator/identifier implementations, baseline CEM, Stage 7/8 methods, and default configs were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | target | T_reach | fail rate | solve time | alpha p95 | alpha p99 | alpha max | duration | integral | slack mean | slack max | slack active | omega p95 | omega max | delta_r count | force count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in _aggregate(summary_rows):
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/3 | {_fmt(row['T_reach_avg'])} | "
            f"{_fmt(row['solver_failure_rate_avg'])} | {_fmt(row['solve_time_avg'])} | "
            f"{_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_p99_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['alpha_duration_avg'])} | {_fmt(row['alpha_integral_avg'])} | "
            f"{_fmt(row['alpha_slack_mean_avg'])} | {_fmt(row['alpha_slack_max_avg'])} | "
            f"{row['alpha_slack_active_total']} | {_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{row['delta_r_count_total']} | {row['force_count_total']} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does explicit NMPC preserve target reaching?",
            f"- {'Yes' if nmpc_preserves else 'No'}: NMPC target={nmpc['target_success_count']}/3.",
            "",
            "2. Does alpha slack NMPC reduce alpha p95/p99/max vs baseline CEM?",
            f"- {'Yes' if nmpc_reduces_alpha else 'No/mixed'}: NMPC alpha p95/p99/max={_fmt(nmpc['alpha_p95_avg'])}/{_fmt(nmpc['alpha_p99_avg'])}/{_fmt(nmpc['alpha_max_avg'])}; baseline={_fmt(baseline['alpha_p95_avg'])}/{_fmt(baseline['alpha_p99_avg'])}/{_fmt(baseline['alpha_max_avg'])}; alpha200={_fmt(alpha200['alpha_p95_avg'])}/{_fmt(alpha200['alpha_p99_avg'])}/{_fmt(alpha200['alpha_max_avg'])}.",
            "",
            "3. Does it avoid worsening omega/delta_r/force violations?",
            f"- {'Yes' if nmpc_avoids_other else 'No/mixed'}: NMPC omega p95/max={_fmt(nmpc['omega_p95_avg'])}/{_fmt(nmpc['omega_max_avg'])}, delta_r count={nmpc['delta_r_count_total']}, force count={nmpc['force_count_total']}.",
            "",
            "4. How often is alpha slack active?",
            f"- Active slack count across NMPC decision horizons: {nmpc['alpha_slack_active_total']}; mean/max slack={_fmt(nmpc['alpha_slack_mean_avg'])}/{_fmt(nmpc['alpha_slack_max_avg'])}.",
            "",
            "5. Is solve time acceptable for this small system?",
            f"- {'Yes for offline diagnosis' if solve_time_ok else 'No/marginal'}: mean NMPC solve time={_fmt(nmpc['solve_time_avg'])} s, failure rate={_fmt(nmpc['solver_failure_rate_avg'])}.",
            "",
            "6. Is NMPC worth developing further, or does this indicate task/constraint conflict?",
            f"- {('Worth developing further' if nmpc_preserves and nmpc_reduces_alpha else 'This still indicates task/constraint conflict or insufficient minimal NMPC formulation')}.",
            "",
            "7. Should next step be NMPC refinement, task/constraint revision, or linked rods?",
            f"- Recommended next step: {next_step}",
            "",
            "## Notes",
            "- Failures and mixed results are retained directly. No post-result tuning was applied.",
        ]
    )
    (output_root / "stage8e_report.md").write_text("\n".join(lines) + "\n")


def run(output_root: Path, config_path: Path) -> None:
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]
    for method in METHODS:
        for condition in CONDITIONS:
            print(f"[stage8e] running {method} / {condition}", flush=True)
            if method in {"baseline_cem", "alpha200_omega0"}:
                cfg = configure_cem_run(base_cfg, method)
                start = time.perf_counter()
                rows = run_condition(condition, base_cfg["conditions"][condition], cfg)
            else:
                cfg = configure_nmpc_run(base_cfg)
                start = time.perf_counter()
                rows = run_nmpc_condition(condition, base_cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            summary = summarize_rows(method, condition, rows, cfg, runtime_s)
            summary_rows.append(summary)
            print(
                "[stage8e] "
                f"{method}/{condition}: target={summary['target_reached']}, "
                f"T={summary['T_reach']:.4g}, "
                f"alpha_p95={summary['alpha_p95_severity']:.4g}, "
                f"alpha_max={summary['alpha_max_severity']:.4g}, "
                f"fail_rate={summary['solver_failure_rate']:.4g}, "
                f"solve={summary['mean_solve_time_s']:.4g}s, "
                f"runtime={runtime_s:.2f}s",
                flush=True,
            )
    save_summary(summary_rows, output_root / "stage8e_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands)
    print(f"[stage8e] summary: {output_root / 'stage8e_summary.csv'}", flush=True)
    print(f"[stage8e] report : {output_root / 'stage8e_report.md'}", flush=True)
    print(f"[stage8e] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
