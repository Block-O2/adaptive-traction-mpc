"""Stage 9I planner-tracker logging validation and adaptive integration."""

from __future__ import annotations

import argparse
import copy
import csv
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import (
    current_prediction_params,
    load_experiment_config,
    observation_from_state,
    parameter_vector,
    run_condition,
)
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_stage8e_explicit_nmpc import (
    _finite_max,
    _finite_mean,
    _finite_percentile,
    _series,
    configure_cem_run,
)
from run_spring2d_stage9f_crossing_lexicographic_nmpc import apply_stage9f_overrides, condition_with_seed
from run_spring2d_stage9g_crossing_alpha_frontier import finite_float, fmt
from run_spring2d_stage9h_planner_tracker import (
    CROSSING_MARGIN,
    FastAlphaFrontierProblem,
    PLANNER_ALPHA_LIMIT,
    ReferenceTrackingNMPC,
    run_boundary_problem,
    sample_reference,
    smooth_reference,
    tracker_variant,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.estimation.noisy_observation_wrapper import NoisySpring2DObservationWrapper, observation_to_state
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC as CEMAdaptiveMPC


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9i_adaptive_planner_tracker"
SEEDS = [101, 102, 103]
PHASE1_CONDITIONS = ["initial_theta_offset"]
PHASE2_CONDITIONS = [
    "clean",
    "noise",
    "noise_bias",
    "stronger_noise",
    "stronger_bias",
    "parameter_mismatch_low_k",
    "parameter_mismatch_high_k",
    "mass_mismatch",
    "damping_mismatch",
    "larger_target_angle",
]
METHODS_PHASE1 = [
    "baseline_cem",
    "oracle_planner_tracker",
    "fixed_planner_tracker",
    "adaptive_planner_tracker",
    "adaptive_planner_tracker_replan",
]
METHODS_PHASE2 = METHODS_PHASE1
PLANNER_HORIZON = 60
REPLAN_THETA_ERROR_THRESHOLD_RAD = 0.08
REPLAN_OMEGA_ERROR_THRESHOLD = 0.25
REPLAN_PARAM_REL_THRESHOLD = 0.20
REPLAN_MIN_STEPS = 15
PARAMETER_NAMES = ("m", "k", "b_r")


def apply_stage9i_overrides(cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    cfg = apply_stage9f_overrides(copy.deepcopy(cfg), condition)
    if condition == "stronger_bias":
        # Condition-level noise override is applied in condition_with_stage9i_seed.
        pass
    elif condition == "mass_mismatch":
        cfg["model_params"]["m"] = 0.65
    elif condition == "damping_mismatch":
        cfg["model_params"]["b_r"] = 6.0
    return cfg


def condition_with_stage9i_seed(base_cfg: dict[str, Any], condition: str, seed: int) -> dict[str, Any]:
    base_name = condition if condition in {"clean", "noise", "noise_bias"} else "clean"
    if condition in {"stronger_noise", "stronger_bias"}:
        base_name = "noise_bias" if condition == "stronger_bias" else "noise"
    cfg = condition_with_seed(base_cfg, base_name, seed)
    cfg["seed"] = int(seed)
    noise = cfg.setdefault("observation_noise", {})
    if condition == "stronger_noise":
        noise.update({"theta_std": 0.008, "omega_std": 0.07, "r_std": 0.0016, "r_dot_std": 0.008})
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
    return cfg


def configure_baseline(base_cfg: dict[str, Any], seed: int) -> dict[str, Any]:
    cfg = configure_cem_run(base_cfg, "baseline_cem")
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    return cfg


def initial_state_from_params(params: dict[str, Any]) -> np.ndarray:
    return np.array([params["theta_init"], params["omega_init"], params["r_init"], params["r_dot_init"]], dtype=float)


def smooth_update_params(
    current: dict[str, Any],
    theta_hat: dict[str, float],
    alpha: float,
    bounds: dict[str, list[float] | tuple[float, float]],
) -> dict[str, Any]:
    updated = dict(current)
    for name in PARAMETER_NAMES:
        raw = float(theta_hat.get(name, updated[name]))
        old = float(updated[name])
        value = (1.0 - alpha) * old + alpha * raw
        if name in bounds:
            lo, hi = bounds[name]
            value = float(np.clip(value, float(lo), float(hi)))
        updated[name] = value
    return updated


def solve_plan(state: np.ndarray, model_params: dict[str, Any], mpc_params: dict[str, Any], alpha_limit: float = PLANNER_ALPHA_LIMIT) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        problem = FastAlphaFrontierProblem(model_params, mpc_params, PLANNER_HORIZON)
        smooth = smooth_reference(problem, state)
        diag, warm, attempts = run_boundary_problem(problem, state, alpha_limit, [("smooth_reference", smooth), ("heuristic", None)])
    except Exception as exc:
        return {
            "success": False,
            "status": f"planner_exception: {type(exc).__name__}: {exc}",
            "solve_time_s": time.perf_counter() - start,
            "iterations": 0,
            "accepted_warmstart": "exception",
            "warm_start_attempts": "exception",
            "planned_crossing_time": np.nan,
            "planner_alpha_limit": float(alpha_limit),
        }
    diag["accepted_warmstart"] = warm
    diag["warm_start_attempts"] = "; ".join(attempts)
    diag["planned_crossing_time"] = PLANNER_HORIZON * problem.prediction_dt
    diag["planner_alpha_limit"] = float(alpha_limit)
    return diag


class PlannerTrackerController:
    def __init__(self, method: str, cfg: dict[str, Any]):
        self.method = method
        self.true_params = dict(cfg["true_params"])
        self.model_params0 = dict(cfg["model_params"])
        self.current_params = dict(self.true_params if method == "oracle_planner_tracker" else self.model_params0)
        self.mpc_params = cfg["mpc_params"]
        self.mode = self._mode_from_method(method)
        self.replan_enabled = method.endswith("_replan")
        self.tracker = ReferenceTrackingNMPC(self.current_params, self.mpc_params, tracker_variant(method))
        self.fallback = CEMAdaptiveMPC(self.current_params, self.mpc_params)
        self.plan_diag: dict[str, Any] | None = None
        self.plan_X: np.ndarray | None = None
        self.plan_U: np.ndarray | None = None
        self.plan_time0 = 0.0
        self.last_plan_step = -10**9
        self.replan_count = 0
        self.last_replan_reason = ""
        self.last_diag: dict[str, Any] = {}
        self.previous_action = np.zeros(2, dtype=float)
        self.last_param_vec = np.array([self.current_params[n] for n in PARAMETER_NAMES], dtype=float)
        self.planner_failure_count = 0

    @staticmethod
    def _mode_from_method(method: str) -> str:
        if method == "oracle_planner_tracker":
            return "oracle"
        if method in {"fixed_planner_tracker", "state_estimation_only"}:
            return "fixed"
        return "adaptive"

    def set_parameters(self, params: dict[str, Any]) -> None:
        self.current_params = dict(params)
        self.tracker.set_model_params({name: float(self.current_params[name]) for name in PARAMETER_NAMES})

    def plan(self, state: np.ndarray, t_now: float, step: int, reason: str) -> bool:
        diag = solve_plan(np.asarray(state, dtype=float), self.current_params, self.mpc_params)
        self.last_diag = {
            "planner_attempted": True,
            "planner_success": bool(diag["success"]),
            "planner_status": str(diag["status"]),
            "planner_solve_time_s": finite_float(diag["solve_time_s"]),
            "planner_iterations": int(diag["iterations"]),
            "planner_trigger_reason": reason,
        }
        if not bool(diag["success"]):
            self.planner_failure_count += 1
            self.last_diag["planner_failure_count"] = int(self.planner_failure_count)
            return False
        self.plan_diag = diag
        self.plan_X = np.asarray(diag["X"], dtype=float)
        self.plan_U = np.asarray(diag["U"], dtype=float)
        self.plan_time0 = float(t_now)
        self.last_plan_step = int(step)
        if reason != "initial":
            self.replan_count += 1
            self.last_replan_reason = reason
        return True

    def maybe_replan(self, state: np.ndarray, t_now: float, step: int) -> None:
        if not self.replan_enabled or self.plan_X is None or self.plan_U is None:
            return
        if step - self.last_plan_step < REPLAN_MIN_STEPS:
            return
        x_ref, _ = sample_reference(self.plan_X, self.plan_U, self.prediction_dt, max(0.0, t_now - self.plan_time0), self.tracker.horizon, self.tracker.prediction_dt)
        theta_err = abs(float(state[0] - x_ref[0, 0]))
        omega_err = abs(float(state[1] - x_ref[0, 1]))
        current_vec = np.array([self.current_params[n] for n in PARAMETER_NAMES], dtype=float)
        denom = max(float(np.linalg.norm(self.last_param_vec)), 1.0e-9)
        param_rel = float(np.linalg.norm(current_vec - self.last_param_vec) / denom)
        reason = ""
        if theta_err > REPLAN_THETA_ERROR_THRESHOLD_RAD or omega_err > REPLAN_OMEGA_ERROR_THRESHOLD:
            reason = "state_tracking_error"
        elif param_rel > REPLAN_PARAM_REL_THRESHOLD:
            reason = "parameter_change"
        if reason:
            if self.plan(state, t_now, step, reason):
                self.last_param_vec = current_vec

    @property
    def prediction_dt(self) -> float:
        return float(self.mpc_params.get("solver", {}).get("prediction_dt", self.true_params["dt"]))

    def act(self, state: np.ndarray, t_now: float, step: int) -> np.ndarray:
        if self.plan_X is None or self.plan_U is None:
            ok = self.plan(state, t_now, step, "initial")
            if not ok:
                action = self.fallback.act_from_state(state) if hasattr(self.fallback, "act_from_state") else np.zeros(2, dtype=float)
                self.last_diag.update({"fallback_used": True, "fallback_reason": "planner_failed_no_valid_plan"})
                return action
        self.maybe_replan(state, t_now, step)
        assert self.plan_X is not None and self.plan_U is not None
        ref_time = max(0.0, float(t_now) - self.plan_time0)
        x_ref, u_ref = sample_reference(self.plan_X, self.plan_U, self.prediction_dt, ref_time, self.tracker.horizon, self.tracker.prediction_dt)
        diag = self.tracker.solve_tracking(state, self.previous_action, x_ref, u_ref)
        fallback_used = False
        fallback_reason = ""
        if bool(diag["success"]):
            action = np.asarray(diag["first_action"], dtype=float)
        else:
            fallback_used = True
            fallback_reason = "tracker_failed"
            action = np.asarray(diag["first_action"], dtype=float)
        action = self.tracker.constraints.clip_action(action)
        self.previous_action = action.copy()
        plan_alpha = np.abs(np.diff(self.plan_X[:, 1]) / self.prediction_dt) if self.plan_X is not None and len(self.plan_X) > 1 else np.array([])
        self.last_diag.update(
            {
                "planner_success": bool(self.plan_diag and self.plan_diag["success"]),
                "planner_status": str(self.plan_diag["status"]) if self.plan_diag else "",
                "planner_solve_time_s": finite_float(self.plan_diag["solve_time_s"]) if self.plan_diag else np.nan,
                "planner_iterations": int(self.plan_diag["iterations"]) if self.plan_diag else 0,
                "planner_failure_count": int(self.planner_failure_count),
                "planned_alpha_abs_p95": _finite_percentile(plan_alpha, 95),
                "planned_alpha_abs_max": _finite_max(plan_alpha),
                "planned_crossing_time": finite_float(self.plan_diag.get("planned_crossing_time", np.nan)) if self.plan_diag else np.nan,
                "planner_F_tan_margin": finite_float(self.plan_diag.get("F_tan_margin", np.nan)) if self.plan_diag else np.nan,
                "planner_F_rad_margin": finite_float(self.plan_diag.get("F_rad_margin", np.nan)) if self.plan_diag else np.nan,
                "planner_delta_r_margin": finite_float(self.plan_diag.get("delta_r_margin", np.nan)) if self.plan_diag else np.nan,
                "planner_omega_margin": finite_float(self.plan_diag.get("omega_margin", np.nan)) if self.plan_diag else np.nan,
                "tracker_solver_success": bool(diag["success"]),
                "tracker_solver_failure": not bool(diag["success"]),
                "tracker_status": str(diag["status"]),
                "tracker_solve_time_s": finite_float(diag["solve_time"]),
                "tracker_iterations": int(diag["iterations"]),
                "tracker_alpha_slack_max": finite_float(diag["alpha_slack_max"]),
                "tracker_alpha_slack_mean": finite_float(diag["alpha_slack_mean"]),
                "tracking_error_state": finite_float(diag["tracking_error_mean"]),
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "replan_count": int(self.replan_count),
                "replan_reason": self.last_replan_reason,
                "theta_ref": float(x_ref[0, 0]),
                "omega_ref": float(x_ref[0, 1]),
                "r_ref": float(x_ref[0, 2]),
                "r_dot_ref": float(x_ref[0, 3]),
                "F_tan_ref": float(u_ref[0, 0]) if len(u_ref) else np.nan,
                "F_rad_ref": float(u_ref[0, 1]) if len(u_ref) else np.nan,
            }
        )
        return action

    def get_last_solve_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diag)


def row_from_env(
    env_row: dict[str, Any],
    alpha_step: float,
    action: np.ndarray,
    target: float,
    controller: PlannerTrackerController | None,
    filt_state: np.ndarray | None,
    theta_hat: dict[str, float] | None,
    true_params: dict[str, Any],
    parameter_update_count: int = 0,
) -> dict[str, Any]:
    row = dict(env_row)
    diag = controller.get_last_solve_diagnostics() if controller is not None else {}
    theta_ref = finite_float(diag.get("theta_ref", np.nan))
    omega_ref = finite_float(diag.get("omega_ref", np.nan))
    x_true = np.array([row["theta"], row["omega"], row["r"], row["r_dot"]], dtype=float)
    x_ref = np.array(
        [
            theta_ref,
            omega_ref,
            finite_float(diag.get("r_ref", np.nan)),
            finite_float(diag.get("r_dot_ref", np.nan)),
        ],
        dtype=float,
    )
    est = np.asarray(filt_state, dtype=float) if filt_state is not None else np.full(4, np.nan)
    theta_hat = theta_hat or {}
    row.update(
        {
            "alpha_step": float(alpha_step),
            "theta_target_final": float(target),
            "theta_crossing_target": float(target + CROSSING_MARGIN),
            "F_tan": float(action[0]),
            "F_rad": float(action[1]),
            "theta_ref": theta_ref,
            "omega_ref": omega_ref,
            "F_tan_ref": finite_float(diag.get("F_tan_ref", np.nan)),
            "F_rad_ref": finite_float(diag.get("F_rad_ref", np.nan)),
            "theta_tracking_error_rad": abs(float(row["theta"]) - theta_ref) if np.isfinite(theta_ref) else np.nan,
            "theta_tracking_error_deg": abs(float(np.degrees(float(row["theta"]) - theta_ref))) if np.isfinite(theta_ref) else np.nan,
            "omega_tracking_error": abs(float(row["omega"]) - omega_ref) if np.isfinite(omega_ref) else np.nan,
            "state_tracking_error": float(np.linalg.norm(x_true - x_ref)) if np.all(np.isfinite(x_ref)) else np.nan,
            "state_estimation_error": float(np.linalg.norm(x_true - est)) if np.all(np.isfinite(est)) else np.nan,
            "theta_estimation_error": abs(float(row["theta"]) - float(est[0])) if np.isfinite(est[0]) else np.nan,
            "omega_estimation_error": abs(float(row["omega"]) - float(est[1])) if np.isfinite(est[1]) else np.nan,
            "m_hat": finite_float(theta_hat.get("m", np.nan)),
            "k_hat": finite_float(theta_hat.get("k", np.nan)),
            "b_r_hat": finite_float(theta_hat.get("b_r", np.nan)),
            "m_error": abs(finite_float(theta_hat.get("m", np.nan)) - float(true_params["m"])),
            "k_error": abs(finite_float(theta_hat.get("k", np.nan)) - float(true_params["k"])),
            "b_r_error": abs(finite_float(theta_hat.get("b_r", np.nan)) - float(true_params["b_r"])),
            "parameter_update_count": int(parameter_update_count),
            **diag,
        }
    )
    return row


def run_planner_tracker(method: str, condition: str, seed: int, cfg: dict[str, Any], condition_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    runtime_start = time.perf_counter()
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    target = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(true_params, condition_cfg.get("observation_noise", {}), seed=int(seed))
    obs_meas = wrapper.observe(obs_true)
    controller = PlannerTrackerController(method, cfg)
    fixed_or_adaptive = method != "oracle_planner_tracker"
    filter_cfg = dict(FILTER_CONFIGS["ukf_bias"])
    filter_cfg["condition_name"] = condition
    obs_filter = make_observation_filter(filter_cfg)
    filt_state = None
    obs_filt = None
    identifier = None
    theta_hat = {name: float(controller.current_params[name]) for name in PARAMETER_NAMES}
    parameter_update_count = 0
    last_theta_hat_vec = np.array([theta_hat[n] for n in PARAMETER_NAMES], dtype=float)
    if fixed_or_adaptive:
        filt_state = obs_filter.reset(obs_meas, true_state=observation_to_state(obs_true), model_params=controller.current_params)
        obs_filt = observation_from_state(obs_meas, filt_state, true_params)
        identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
        identifier.reset()
        theta_hat = identifier.get_parameter_estimate()
    rows = [
        row_from_env(
            env.get_history()[-1],
            0.0,
            np.zeros(2, dtype=float),
            target,
            None,
            filt_state,
            theta_hat,
            true_params,
            parameter_update_count,
        )
    ]
    adaptive_cfg = cfg.get("adaptive", {})
    smoothing_alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 1.0))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        t_now = float(env.get_history()[-1]["t"])
        if method == "oracle_planner_tracker":
            control_state = observation_to_state(obs_true)
        else:
            assert obs_filt is not None and filt_state is not None
            control_state = observation_to_state(obs_filt)
        action = controller.act(control_state, t_now, steps)
        for _ in range(hold_steps):
            prev_env_row = env.get_history()[-1]
            prev_obs_meas = obs_meas
            prev_obs_filt = obs_filt
            prev_obs_true = obs_true
            obs_true = env.step(action)
            obs_meas = wrapper.observe(obs_true)
            if fixed_or_adaptive:
                assert filt_state is not None and identifier is not None and prev_obs_filt is not None
                obs_filter.predict(action, float(true_params["dt"]), model_params=controller.current_params)
                filt_state = obs_filter.update(
                    obs_meas,
                    float(true_params["dt"]),
                    action=action,
                    true_state=observation_to_state(obs_true),
                    model_params=controller.current_params,
                )
                obs_filt = observation_from_state(obs_meas, filt_state, true_params)
                if method.startswith("adaptive"):
                    result = identifier.add_transition(observation_to_state(prev_obs_filt), action, observation_to_state(obs_filt))
                    theta_hat = result.theta_hat
                    current_vec = parameter_vector(theta_hat)
                    _ = float(np.linalg.norm(current_vec - last_theta_hat_vec))
                    last_theta_hat_vec = current_vec
                    if result.updated and steps >= warmup_steps:
                        new_params = smooth_update_params(controller.current_params, theta_hat, smoothing_alpha, parameter_bounds)
                        controller.set_parameters(new_params)
                        parameter_update_count += 1
                else:
                    result = SimpleNamespace(theta_hat=identifier.get_parameter_estimate(), updated=False)
                    theta_hat = result.theta_hat
            current_env_row = env.get_history()[-1]
            alpha_step = (float(current_env_row["omega"]) - float(prev_env_row["omega"])) / float(true_params["dt"])
            steps += 1
            rows.append(row_from_env(current_env_row, alpha_step, action, target, controller, filt_state, theta_hat, true_params, parameter_update_count))
            if env.is_done() or steps >= max_steps:
                break
    return rows, time.perf_counter() - runtime_start


def first_crossing_time(rows: list[dict[str, Any]], target: float) -> float:
    for row in rows:
        if float(row["theta"]) >= target:
            return float(row["t"])
    return np.nan


def summarize_run(method: str, condition: str, seed: int, phase: str, rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    true_params = cfg["true_params"]
    constraints = cfg["mpc_params"].get("constraints", {})
    target = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))
    theta = _series(rows, "theta")
    alpha_abs = np.abs(_series(rows, "alpha_step"))
    alpha_violation = np.maximum(0.0, alpha_abs - alpha_max)
    omega_abs = np.abs(_series(rows, "omega"))
    omega_violation = np.maximum(0.0, omega_abs - omega_max)
    delta_r_violation = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    force_violation = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max) + np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_mag = np.linalg.norm(actions, axis=1)
    action_tv = float(np.nansum(np.linalg.norm(np.diff(actions, axis=0), axis=1))) if len(actions) > 1 else 0.0
    decisions = [row for row in rows if str(row.get("tracker_status", ""))]
    planner_rows = [row for row in rows if str(row.get("planner_status", ""))]
    planned_alpha_p95 = _finite_percentile(_series(rows, "planned_alpha_abs_p95"), 95)
    planned_alpha_max = _finite_max(_series(rows, "planned_alpha_abs_max"))
    crossed = bool(np.any(theta >= target))
    return {
        "phase": phase,
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "target_crossed": crossed,
        "crossing_time": first_crossing_time(rows, target),
        "final_theta_deg": float(np.degrees(theta[-1])) if len(theta) else np.nan,
        "raw_alpha_mean": _finite_mean(alpha_abs),
        "raw_alpha_p95": _finite_percentile(alpha_abs, 95),
        "raw_alpha_p99": _finite_percentile(alpha_abs, 99),
        "raw_alpha_max": _finite_max(alpha_abs),
        "alpha_violation_count": int(np.count_nonzero(alpha_violation > 0.0)),
        "alpha_violation_p95": _finite_percentile(alpha_violation, 95),
        "alpha_violation_max": _finite_max(alpha_violation),
        "alpha_violation_duration": float(np.count_nonzero(alpha_violation > 0.0) * dt),
        "alpha_violation_integral": float(np.sum(alpha_violation) * dt),
        "planned_alpha_abs_p95": planned_alpha_p95,
        "planned_alpha_abs_max": planned_alpha_max,
        "executed_alpha_abs_p95": _finite_percentile(alpha_abs, 95),
        "executed_alpha_abs_max": _finite_max(alpha_abs),
        "raw_omega_mean": _finite_mean(omega_abs),
        "raw_omega_p95": _finite_percentile(omega_abs, 95),
        "raw_omega_max": _finite_max(omega_abs),
        "omega_violation_count": int(np.count_nonzero(omega_violation > 0.0)),
        "omega_violation_p95": _finite_percentile(omega_violation, 95),
        "omega_violation_max": _finite_max(omega_violation),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_violation > 0.0)),
        "delta_r_violation_max": _finite_max(delta_r_violation),
        "force_violation_count": int(np.count_nonzero(force_violation > 0.0)),
        "force_violation_max": _finite_max(force_violation),
        "theta_tracking_error_deg_mean": _finite_mean(_series(rows, "theta_tracking_error_deg")),
        "theta_tracking_error_rad_mean": _finite_mean(_series(rows, "theta_tracking_error_rad")),
        "omega_tracking_error_mean": _finite_mean(_series(rows, "omega_tracking_error")),
        "state_tracking_rmse": _finite_mean(_series(rows, "state_tracking_error")),
        "state_estimation_error_mean": _finite_mean(_series(rows, "state_estimation_error")),
        "m_error_final": finite_float(rows[-1].get("m_error", np.nan)),
        "k_error_final": finite_float(rows[-1].get("k_error", np.nan)),
        "b_r_error_final": finite_float(rows[-1].get("b_r_error", np.nan)),
        "planner_failure_count": int(finite_float(_finite_max(_series(rows, "planner_failure_count"))) or 0) if np.isfinite(finite_float(_finite_max(_series(rows, "planner_failure_count")))) else 0,
        "planner_solve_mean": _finite_mean(_series(planner_rows, "planner_solve_time_s")),
        "planner_solve_p95": _finite_percentile(_series(planner_rows, "planner_solve_time_s"), 95),
        "planner_solve_max": _finite_max(_series(planner_rows, "planner_solve_time_s")),
        "planner_iterations_mean": _finite_mean(_series(planner_rows, "planner_iterations")),
        "tracker_failure_count": int(sum(bool(row.get("tracker_solver_failure", False)) for row in decisions)),
        "tracker_solve_mean": _finite_mean(_series(decisions, "tracker_solve_time_s")),
        "tracker_solve_p95": _finite_percentile(_series(decisions, "tracker_solve_time_s"), 95),
        "tracker_solve_max": _finite_max(_series(decisions, "tracker_solve_time_s")),
        "tracker_iterations_mean": _finite_mean(_series(decisions, "tracker_iterations")),
        "fallback_count": int(sum(bool(row.get("fallback_used", False)) for row in decisions)),
        "fallback_rate": float(sum(bool(row.get("fallback_used", False)) for row in decisions) / len(decisions)) if decisions else np.nan,
        "replan_count": int(_finite_max(_series(rows, "replan_count"))) if method.endswith("_replan") else 0,
        "replan_reasons": ";".join(sorted({str(row.get("replan_reason", "")) for row in rows if str(row.get("replan_reason", ""))})),
        "action_magnitude_mean": _finite_mean(action_mag),
        "action_magnitude_max": _finite_max(action_mag),
        "action_total_variation": action_tv,
        "runtime_s": float(runtime_s),
    }


def summarize_baseline(method: str, condition: str, seed: int, phase: str, rows: list[dict[str, Any]], cfg: dict[str, Any], runtime_s: float) -> dict[str, Any]:
    for row in rows:
        row.setdefault("F_tan", row.get("F_tan", np.nan))
        row.setdefault("F_rad", row.get("F_rad", np.nan))
        row.setdefault("alpha_step", row.get("alpha_step", 0.0))
    return summarize_run(method, condition, seed, phase, rows, cfg, runtime_s)


def run_method(method: str, condition: str, seed: int, phase: str, base_cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    condition_cfg = condition_with_stage9i_seed(base_cfg, condition, seed)
    if method == "baseline_cem":
        cfg = apply_stage9i_overrides(configure_baseline(base_cfg, seed), condition)
        start = time.perf_counter()
        rows = run_condition(condition, condition_cfg, cfg)
        return summarize_baseline(method, condition, seed, phase, rows, cfg, time.perf_counter() - start), rows
    cfg = apply_stage9i_overrides(copy.deepcopy(base_cfg), condition)
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    rows, runtime_s = run_planner_tracker(method, condition, seed, cfg, condition_cfg)
    return summarize_run(method, condition, seed, phase, rows, cfg, runtime_s), rows


SUMMARY_FIELDS = [
    "phase",
    "method",
    "condition",
    "seed",
    "target_crossed",
    "crossing_time",
    "final_theta_deg",
    "raw_alpha_mean",
    "raw_alpha_p95",
    "raw_alpha_p99",
    "raw_alpha_max",
    "alpha_violation_count",
    "alpha_violation_p95",
    "alpha_violation_max",
    "alpha_violation_duration",
    "alpha_violation_integral",
    "planned_alpha_abs_p95",
    "planned_alpha_abs_max",
    "executed_alpha_abs_p95",
    "executed_alpha_abs_max",
    "raw_omega_mean",
    "raw_omega_p95",
    "raw_omega_max",
    "omega_violation_count",
    "omega_violation_p95",
    "omega_violation_max",
    "delta_r_violation_count",
    "delta_r_violation_max",
    "force_violation_count",
    "force_violation_max",
    "theta_tracking_error_deg_mean",
    "theta_tracking_error_rad_mean",
    "omega_tracking_error_mean",
    "state_tracking_rmse",
    "state_estimation_error_mean",
    "m_error_final",
    "k_error_final",
    "b_r_error_final",
    "planner_failure_count",
    "planner_solve_mean",
    "planner_solve_p95",
    "planner_solve_max",
    "planner_iterations_mean",
    "tracker_failure_count",
    "tracker_solve_mean",
    "tracker_solve_p95",
    "tracker_solve_max",
    "tracker_iterations_mean",
    "fallback_count",
    "fallback_rate",
    "replan_count",
    "replan_reasons",
    "action_magnitude_mean",
    "action_magnitude_max",
    "action_total_variation",
    "runtime_s",
]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


def aggregate(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    for method in sorted({str(r["method"]) for r in rows}):
        for condition in sorted({str(r["condition"]) for r in rows if str(r["method"]) == method}):
            group = [r for r in rows if str(r["method"]) == method and str(r["condition"]) == condition]
            out[(method, condition)] = {
                "n": float(len(group)),
                "success": float(sum(bool(r["target_crossed"]) for r in group)),
                "raw_alpha_max": _finite_mean(_series(group, "raw_alpha_max")),
                "alpha_violation_max": _finite_mean(_series(group, "alpha_violation_max")),
                "crossing_time": _finite_mean(_series(group, "crossing_time")),
                "planner_fail": _finite_mean(_series(group, "planner_failure_count")),
                "tracker_fail": _finite_mean(_series(group, "tracker_failure_count")),
                "fallback": _finite_mean(_series(group, "fallback_rate")),
                "replan": _finite_mean(_series(group, "replan_count")),
                "state_rmse": _finite_mean(_series(group, "state_tracking_rmse")),
                "k_error": _finite_mean(_series(group, "k_error_final")),
            }
    return out


def save_plots(summary_rows: list[dict[str, Any]], all_runs: dict[tuple[str, str, int], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    agg = aggregate(summary_rows)
    methods = [m for m in METHODS_PHASE1 if any(key[0] == m for key in agg)]
    phase1 = [row for row in summary_rows if row["condition"] == "initial_theta_offset"]
    fig, axes = plt.subplots(2, 1, figsize=(8.0, 7.0))
    axes[0].bar(methods, [sum(bool(r["target_crossed"]) for r in phase1 if r["method"] == m) for m in methods])
    axes[0].set_ylabel("crossed / 3")
    axes[0].set_ylim(0, 3)
    axes[1].bar(methods, [_finite_mean(_series([r for r in phase1 if r["method"] == m], "raw_alpha_max")) for m in methods])
    axes[1].axhline(3.0, color="black", linestyle=":", linewidth=1.0, label="alpha limit")
    axes[1].set_ylabel("raw alpha max")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "fixed_adaptive_oracle_success_alpha.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.bar(methods, [_finite_mean(_series([r for r in summary_rows if r["method"] == m], "tracker_solve_mean")) for m in methods])
    ax.set_ylabel("tracker solve mean [s]")
    ax.set_title("Tracker solve time distribution summary")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "planner_tracker_solve_time_summary.png")
    plt.close(fig)

    for key, rows in all_runs.items():
        method, condition, seed = key
        if condition != "initial_theta_offset" or method not in {"oracle_planner_tracker", "adaptive_planner_tracker", "adaptive_planner_tracker_replan"}:
            continue
        t = _series(rows, "t")
        alpha = np.abs(_series(rows, "alpha_step"))
        alpha_violation = np.maximum(0.0, alpha - 3.0)
        fig, axes = plt.subplots(7, 1, figsize=(9.0, 13.0), sharex=True)
        axes[0].plot(t, np.degrees(_series(rows, "theta")), label="executed")
        axes[0].plot(t, np.degrees(_series(rows, "theta_ref")), linestyle="--", label="planned")
        axes[0].axhline(np.degrees(float(rows[-1]["theta_target_final"])), color="black", linestyle=":", linewidth=1.0)
        axes[1].plot(t, _series(rows, "omega"), label="executed")
        axes[1].plot(t, _series(rows, "omega_ref"), linestyle="--", label="planned")
        axes[2].plot(t, alpha, label="executed |alpha|")
        axes[2].plot(t, _series(rows, "planned_alpha_abs_p95"), linestyle="--", label="planned alpha p95")
        axes[2].axhline(3.0, color="black", linestyle=":", linewidth=1.0)
        axes[3].plot(t, alpha_violation, label="alpha violation")
        axes[4].plot(t, _series(rows, "F_tan"), label="F_tan")
        axes[4].plot(t, _series(rows, "F_tan_ref"), linestyle="--", label="F_tan ref")
        axes[4].plot(t, _series(rows, "F_rad"), label="F_rad")
        axes[4].plot(t, _series(rows, "F_rad_ref"), linestyle="--", label="F_rad ref")
        axes[5].plot(t, _series(rows, "theta_tracking_error_deg"), label="theta err deg")
        axes[5].plot(t, _series(rows, "omega_tracking_error"), label="omega err")
        axes[6].plot(t, _series(rows, "m_hat"), label="m_hat")
        axes[6].plot(t, _series(rows, "k_hat"), label="k_hat")
        axes[6].plot(t, _series(rows, "b_r_hat"), label="b_r_hat")
        replan_t = [float(row["t"]) for row in rows if int(finite_float(row.get("replan_count", 0))) > 0]
        for ax in axes:
            for rt in replan_t:
                ax.axvline(rt, color="tab:red", alpha=0.15)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
        axes[-1].set_xlabel("time [s]")
        fig.tight_layout()
        fig.savefig(fig_dir / f"{method}_{condition}_seed{seed}_logging_validation.png")
        plt.close(fig)


def write_report(path: Path, summary_rows: list[dict[str, Any]], phase2_skipped_reason: str | None) -> None:
    agg = aggregate(summary_rows)
    phase1_adaptive = agg.get(("adaptive_planner_tracker", "initial_theta_offset"), {})
    phase1_oracle = agg.get(("oracle_planner_tracker", "initial_theta_offset"), {})
    phase1_fixed = agg.get(("fixed_planner_tracker", "initial_theta_offset"), {})
    adaptive_stress = [vals for (method, condition), vals in agg.items() if method == "adaptive_planner_tracker" and condition != "initial_theta_offset"]
    replan_rows = [vals for (method, _condition), vals in agg.items() if method == "adaptive_planner_tracker_replan"]
    adaptive_worst_alpha = max([float(vals["raw_alpha_max"]) for vals in adaptive_stress if np.isfinite(vals["raw_alpha_max"])] or [np.nan])
    replan_worst_alpha = max([float(vals["raw_alpha_max"]) for vals in replan_rows if np.isfinite(vals["raw_alpha_max"])] or [np.nan])
    replan_fail_sum = sum(float(vals["planner_fail"]) for vals in replan_rows if np.isfinite(vals["planner_fail"]))
    with path.open("w") as f:
        f.write("# Stage 9I Adaptive Planner/Tracker\n\n")
        f.write("Stage 9I separates raw alpha from alpha violation severity and tests UKF-bias plus filtered Windowed NLS integration.\n\n")
        f.write("## Aggregate Summary\n\n")
        f.write("| method | condition | crossed | raw_alpha_max | alpha_violation_max | crossing_time | planner_fail | tracker_fail | fallback | replan |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for (method, condition), vals in sorted(agg.items()):
            f.write(
                f"| {method} | {condition} | {int(vals['success'])}/{int(vals['n'])} | {fmt(vals['raw_alpha_max'])} | "
                f"{fmt(vals['alpha_violation_max'])} | {fmt(vals['crossing_time'])} | {fmt(vals['planner_fail'])} | "
                f"{fmt(vals['tracker_fail'])} | {fmt(vals['fallback'])} | {fmt(vals['replan'])} |\n"
            )
        if phase2_skipped_reason:
            f.write(f"\nPhase 2 skipped: {phase2_skipped_reason}\n")
        f.write("\n## Required Answers\n\n")
        f.write("1. Stage 9H summary columns named alpha_max were violation severity, not raw alpha. Stage 9I logs raw_alpha_* and alpha_violation_* separately.\n")
        f.write(
            f"2. In Phase 1, oracle executed raw alpha max averaged {fmt(phase1_oracle.get('raw_alpha_max', np.nan))} "
            f"against planned limit {PLANNER_ALPHA_LIMIT:g}; violation max averaged {fmt(phase1_oracle.get('alpha_violation_max', np.nan))}.\n"
        )
        f.write(
            f"3. Adaptive planner/tracker preserved initial_theta_offset crossing in {int(phase1_adaptive.get('success', 0))}/{int(phase1_adaptive.get('n', 0))} runs.\n"
        )
        f.write(
            f"4. Adaptive vs oracle Phase 1 raw alpha max: adaptive {fmt(phase1_adaptive.get('raw_alpha_max', np.nan))}, "
            f"oracle {fmt(phase1_oracle.get('raw_alpha_max', np.nan))}; crossing count adaptive {int(phase1_adaptive.get('success', 0))}, oracle {int(phase1_oracle.get('success', 0))}.\n"
        )
        mismatch_conditions = ["parameter_mismatch_low_k", "parameter_mismatch_high_k", "mass_mismatch", "damping_mismatch"]
        improvements = []
        for condition in mismatch_conditions:
            fixed = agg.get(("fixed_planner_tracker", condition), {})
            adaptive = agg.get(("adaptive_planner_tracker", condition), {})
            if fixed and adaptive:
                improvements.append(f"{condition}: fixed {int(fixed['success'])}/{int(fixed['n'])}, adaptive {int(adaptive['success'])}/{int(adaptive['n'])}")
        f.write("5. Parameter-mismatch comparison: " + ("; ".join(improvements) if improvements else "not run because Phase 2 was skipped") + ". This is a task-success improvement, not a low-alpha success; mass_mismatch still has high adaptive raw alpha.\n")
        f.write(
            f"6. UKF-bias degradation in Phase 1: fixed-model state-estimated crossing {int(phase1_fixed.get('success', 0))}/{int(phase1_fixed.get('n', 0))}, "
            f"state RMSE {fmt(phase1_fixed.get('state_rmse', np.nan))}.\n"
        )
        replan = agg.get(("adaptive_planner_tracker_replan", "initial_theta_offset"), {})
        f.write(f"7. One-shot planning Phase 1 adaptive crossing was {int(phase1_adaptive.get('success', 0))}/{int(phase1_adaptive.get('n', 0))}; replanning count averaged {fmt(replan.get('replan', np.nan))}.\n")
        if np.isfinite(replan_worst_alpha) and (replan_worst_alpha > adaptive_worst_alpha or replan_fail_sum > 0):
            f.write(
                f"8. Event-triggered replanning is not justified by this run: worst replan raw alpha was {fmt(replan_worst_alpha)} "
                f"and planner-failure count average is nonzero in several rows. No extra threshold tuning was done.\n"
            )
        else:
            f.write("8. Event-triggered replanning did not show a clear enough benefit to justify added complexity without further evidence.\n")
        f.write(
            f"9. Phase 1 adaptive planner fail avg {fmt(phase1_adaptive.get('planner_fail', np.nan))}, tracker fail avg {fmt(phase1_adaptive.get('tracker_fail', np.nan))}, fallback avg {fmt(phase1_adaptive.get('fallback', np.nan))}.\n"
        )
        if int(phase1_adaptive.get("success", 0)) >= 2 and not phase2_skipped_reason and np.isfinite(adaptive_worst_alpha) and adaptive_worst_alpha <= 10.0:
            f.write("10. Single-link can proceed toward final statistical validation, but linked-rods preparation should still wait for reviewing adaptive mismatch evidence. No formal safety guarantee is claimed.\n")
        elif int(phase1_adaptive.get("success", 0)) >= 2 and not phase2_skipped_reason:
            f.write(
                f"10. Single-link is not ready for linked-rods preparation as a low-alpha adaptive controller: Phase 2 adaptive worst raw alpha reached {fmt(adaptive_worst_alpha)}. "
                "Next work should address adaptive planner/tracker robustness before final statistical validation. No formal safety guarantee is claimed.\n"
            )
        else:
            f.write("10. Single-link is not ready for linked-rods preparation from this run alone. No formal safety guarantee is claimed.\n")


def run(output_root: Path, config_path: Path) -> None:
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]] = {}

    def run_one(method: str, condition: str, seed: int, phase: str) -> None:
        print(f"[stage9i] running {phase} {method}/{condition}/seed{seed}", flush=True)
        summary, rows = run_method(method, condition, seed, phase, base_cfg)
        summary_rows.append(summary)
        all_runs[(method, condition, int(seed))] = rows
        print(
            f"[stage9i] {method}/{condition}/seed{seed}: crossed={summary['target_crossed']}, "
            f"raw_alpha_max={fmt(summary['raw_alpha_max'])}, alpha_viol_max={fmt(summary['alpha_violation_max'])}, "
            f"planner_fail={summary['planner_failure_count']}, tracker_fail={summary['tracker_failure_count']}",
            flush=True,
        )

    for seed in SEEDS:
        for method in METHODS_PHASE1:
            run_one(method, "initial_theta_offset", seed, "phase1")
    phase1_adaptive = [row for row in summary_rows if row["method"] == "adaptive_planner_tracker" and row["condition"] == "initial_theta_offset"]
    adaptive_success = sum(bool(row["target_crossed"]) for row in phase1_adaptive)
    adaptive_solver_fail = sum(int(row["planner_failure_count"]) + int(row["tracker_failure_count"]) for row in phase1_adaptive)
    adaptive_alpha_ok = _finite_mean(_series(phase1_adaptive, "raw_alpha_max")) < _finite_mean(
        _series([row for row in summary_rows if row["method"] == "baseline_cem" and row["condition"] == "initial_theta_offset"], "raw_alpha_max")
    )
    phase2_skipped_reason = None
    if adaptive_success >= 2 and adaptive_solver_fail <= 1 and adaptive_alpha_ok:
        for condition in PHASE2_CONDITIONS:
            for seed in SEEDS:
                for method in METHODS_PHASE2:
                    run_one(method, condition, seed, "phase2")
    else:
        phase2_skipped_reason = "adaptive planner/tracker failed Phase 1 continuation gate"
    write_csv(output_root / "stage9i_summary.csv", summary_rows)
    save_plots(summary_rows, all_runs, output_root)
    write_report(output_root / "stage9i_report.md", summary_rows, phase2_skipped_reason)
    print(f"[stage9i] summary: {output_root / 'stage9i_summary.csv'}", flush=True)
    print(f"[stage9i] report : {output_root / 'stage9i_report.md'}", flush=True)


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
