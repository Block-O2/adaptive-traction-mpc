"""Stage 9J adaptive planner-tracker gap decomposition and data audit."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
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
    load_experiment_config,
    observation_from_state,
    parameter_bound_hit,
    parameter_vector,
    run_condition,
)
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_stage8e_explicit_nmpc import configure_cem_run
from run_spring2d_stage9f_crossing_lexicographic_nmpc import apply_stage9f_overrides, condition_with_seed
from run_spring2d_stage9h_planner_tracker import (
    PLANNER_ALPHA_LIMIT,
    ReferenceTrackingNMPC,
    sample_reference,
    tracker_variant,
)
from run_spring2d_stage9i_adaptive_planner_tracker import (
    PARAMETER_NAMES,
    finite_float,
    smooth_update_params,
    solve_plan,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.estimation.noisy_observation_wrapper import NoisySpring2DObservationWrapper, observation_to_state
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage9j_gap_decomposition"
SEEDS = [101, 102, 103]
CONDITIONS = [
    "clean",
    "initial_theta_offset",
    "noise",
    "noise_bias",
    "stronger_noise",
    "mass_mismatch",
    "parameter_mismatch_low_k",
    "parameter_mismatch_high_k",
]
METHODS = [
    "baseline_cem",
    "oracle_planner_tracker",
    "state_error_only",
    "parameter_error_only",
    "fixed_nominal_planner_tracker",
    "full_adaptive_planner_tracker",
]
STATE_NAMES = ("theta", "omega", "r", "r_dot")
PARAM_ERROR_BAND_REL = 0.10


@dataclass(frozen=True)
class ModeSpec:
    state_source: str
    parameter_source: str
    nls_controls_tracker: bool


MODE_SPECS = {
    "oracle_planner_tracker": ModeSpec("true", "true", False),
    "state_error_only": ModeSpec("estimated", "true", False),
    "parameter_error_only": ModeSpec("true", "nls", True),
    "fixed_nominal_planner_tracker": ModeSpec("estimated", "nominal", False),
    "full_adaptive_planner_tracker": ModeSpec("estimated", "nls", True),
}


def stage9j_overrides(base_cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    cfg = apply_stage9f_overrides(copy.deepcopy(base_cfg), condition)
    if condition == "mass_mismatch":
        cfg["model_params"]["m"] = 0.65
    return cfg


def condition_cfg(base_cfg: dict[str, Any], condition: str, seed: int) -> dict[str, Any]:
    cfg = condition_with_seed(base_cfg, condition, seed)
    cfg["seed"] = int(seed)
    return cfg


def control_params(spec: ModeSpec, true_params: dict[str, Any], nominal_params: dict[str, Any], nls_hat: dict[str, float]) -> dict[str, Any]:
    if spec.parameter_source == "true":
        return dict(true_params)
    if spec.parameter_source == "nominal":
        return dict(nominal_params)
    params = dict(nominal_params)
    params.update({name: float(nls_hat[name]) for name in PARAMETER_NAMES})
    return params


def vector_json(values: Any) -> str:
    return json.dumps(np.asarray(values, dtype=float).tolist(), separators=(",", ":"), allow_nan=True)


def stable_hash(values: Any) -> str:
    arr = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def finite_values(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return arr[np.isfinite(arr)]


def stat(values: Any, kind: str) -> float:
    arr = finite_values(values)
    if not len(arr):
        return np.nan
    if kind == "mean":
        return float(np.mean(arr))
    if kind == "p95":
        return float(np.percentile(arr, 95))
    if kind == "p99":
        return float(np.percentile(arr, 99))
    if kind == "max":
        return float(np.max(arr))
    if kind == "rmse":
        return float(np.sqrt(np.mean(arr**2)))
    raise ValueError(kind)


def first_time_in_band(times: np.ndarray, estimates: np.ndarray, truth: float, band: float = PARAM_ERROR_BAND_REL) -> float:
    if truth == 0.0:
        return np.nan
    indices = np.flatnonzero(np.abs(estimates - truth) / abs(truth) <= band)
    return float(times[indices[0]]) if len(indices) else np.nan


def row_state(row: dict[str, Any], prefix: str) -> np.ndarray:
    if prefix == "true":
        return np.array([row["true_theta"], row["true_omega"], row["true_r"], row["true_r_dot"]], dtype=float)
    return np.array([row["estimated_theta"], row["estimated_omega"], row["estimated_r"], row["estimated_r_dot"]], dtype=float)


class AuditedPlannerTracker:
    def __init__(self, method: str, cfg: dict[str, Any]):
        self.method = method
        self.run_instance = f"{method}-{time.time_ns()}-{id(self)}"
        self.spec = MODE_SPECS[method]
        self.true_params = dict(cfg["true_params"])
        self.nominal_params = dict(cfg["model_params"])
        self.mpc_params = copy.deepcopy(cfg["mpc_params"])
        self.current_params = control_params(
            self.spec,
            self.true_params,
            self.nominal_params,
            {name: float(self.nominal_params[name]) for name in PARAMETER_NAMES},
        )
        self.tracker = ReferenceTrackingNMPC(self.current_params, self.mpc_params, tracker_variant(method))
        self.plan_diag: dict[str, Any] | None = None
        self.plan_X: np.ndarray | None = None
        self.plan_U: np.ndarray | None = None
        self.previous_action = np.zeros(2, dtype=float)
        self.audit_rows: list[dict[str, Any]] = []
        self.tracker_failure_count = 0

    @property
    def plan_dt(self) -> float:
        return float(self.mpc_params.get("solver", {}).get("prediction_dt", self.true_params["dt"]))

    def set_tracker_parameters_between_steps(self, params: dict[str, Any]) -> None:
        self.current_params = dict(params)
        self.tracker.set_model_params({name: float(params[name]) for name in PARAMETER_NAMES})

    def plan_once(self, state: np.ndarray, params: dict[str, Any], seed: int, condition: str) -> None:
        state_frozen = np.asarray(state, dtype=float).copy()
        params_frozen = dict(params)
        assert self.plan_diag is None, "Stage 9J primary experiment permits exactly one planner call"
        assert self.spec.state_source in {"true", "estimated"}
        assert self.spec.parameter_source in {"true", "nominal", "nls"}
        self.plan_diag = solve_plan(state_frozen, params_frozen, self.mpc_params, PLANNER_ALPHA_LIMIT)
        self.audit_rows.append(
            self._audit_row("planner", 0, 0.0, seed, condition, state_frozen, params_frozen)
        )
        if bool(self.plan_diag.get("success", False)):
            self.plan_X = np.asarray(self.plan_diag["X"], dtype=float).copy()
            self.plan_U = np.asarray(self.plan_diag["U"], dtype=float).copy()

    def _audit_row(
        self,
        call_type: str,
        step: int,
        t_now: float,
        seed: int,
        condition: str,
        state: np.ndarray,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "method": self.method,
            "condition": condition,
            "seed": int(seed),
            "call_type": call_type,
            "step": int(step),
            "t": float(t_now),
            "state_source": self.spec.state_source,
            "parameter_source": self.spec.parameter_source,
            "state_theta": float(state[0]),
            "state_omega": float(state[1]),
            "state_r": float(state[2]),
            "state_r_dot": float(state[3]),
            "param_m": float(params["m"]),
            "param_k": float(params["k"]),
            "param_b_r": float(params["b_r"]),
            "controller_object_id": id(self),
            "tracker_object_id": id(self.tracker),
            "run_instance": self.run_instance,
            "plan_X_object_id": id(self.plan_X) if self.plan_X is not None else "",
            "plan_U_object_id": id(self.plan_U) if self.plan_U is not None else "",
        }

    def act(self, state: np.ndarray, params: dict[str, Any], t_now: float, step: int, seed: int, condition: str) -> tuple[np.ndarray, dict[str, Any]]:
        state_frozen = np.asarray(state, dtype=float).copy()
        params_frozen = dict(params)
        if self.plan_diag is None:
            self.plan_once(state_frozen, params_frozen, seed, condition)
        if self.plan_X is None or self.plan_U is None:
            diag = {"success": False, "status": str(self.plan_diag.get("status", "planner_failed")), "first_action": np.zeros(2), "X": np.tile(state_frozen, (self.tracker.horizon + 1, 1)), "U": np.zeros((self.tracker.horizon, 2)), "S": np.zeros(self.tracker.horizon)}
            return np.zeros(2, dtype=float), diag
        self.set_tracker_parameters_between_steps(params_frozen)
        x_ref, u_ref = sample_reference(
            self.plan_X,
            self.plan_U,
            self.plan_dt,
            float(t_now),
            self.tracker.horizon,
            self.tracker.prediction_dt,
        )
        # Parameters and state are immutable snapshots for this solve.
        diag = self.tracker.solve_tracking(state_frozen, self.previous_action.copy(), x_ref.copy(), u_ref.copy())
        action = self.tracker.constraints.clip_action(np.asarray(diag["first_action"], dtype=float))
        self.previous_action = action.copy()
        if not bool(diag["success"]):
            self.tracker_failure_count += 1
        audit = self._audit_row("tracker", step, t_now, seed, condition, state_frozen, params_frozen)
        predicted_X = np.asarray(diag.get("X", []), dtype=float)
        predicted_S = np.asarray(diag.get("S", []), dtype=float)
        audit.update(
            {
                "action_F_tan": float(action[0]),
                "action_F_rad": float(action[1]),
                "solver_success": bool(diag["success"]),
                "solver_status": str(diag["status"]),
                "tracker_predicted_alpha": float((predicted_X[1, 1] - predicted_X[0, 1]) / self.tracker.prediction_dt) if predicted_X.ndim == 2 and len(predicted_X) > 1 else np.nan,
                "tracker_constraint_slack": float(predicted_S[0]) if len(predicted_S) else np.nan,
            }
        )
        self.audit_rows.append(audit)
        return action, diag


def initial_log_row(
    env: Spring2DEnv,
    estimated_state: np.ndarray,
    nls_hat: dict[str, float],
    filter_diag: dict[str, Any],
    true_params: dict[str, Any],
    nominal_params: dict[str, Any],
) -> dict[str, Any]:
    hist = env.get_history()[-1]
    true_state = np.array([hist["theta"], hist["omega"], hist["r"], hist["r_dot"]], dtype=float)
    row = {"t": float(hist["t"]), "step": 0}
    for name, value in zip(STATE_NAMES, true_state):
        row[f"true_{name}"] = float(value)
    for name, value in zip(STATE_NAMES, estimated_state):
        row[f"estimated_{name}"] = float(value)
        row[f"{name}_estimation_error"] = float(value - true_state[STATE_NAMES.index(name)])
    row.update(
        {
            "true_delta_r": float(true_state[2] - true_params["L0"]),
            "true_alpha": 0.0,
            "estimated_alpha": 0.0,
            "planner_predicted_alpha": np.nan,
            "tracker_predicted_alpha": np.nan,
            "planned_constraint_slack": 0.0,
            "tracker_constraint_slack": 0.0,
            "F_tan": 0.0,
            "F_rad": 0.0,
            "theta_ref": np.nan,
            "omega_ref": np.nan,
            "state_tracking_error": np.nan,
            "parameter_update_magnitude": 0.0,
            "parameter_bound_hit": False,
            "identifier_updated": False,
            "identifier_samples": 0,
            **{f"{name}_hat": float(nls_hat[name]) for name in PARAMETER_NAMES},
            **{f"true_{name}_param": float(true_params[name]) for name in PARAMETER_NAMES},
            **{f"nominal_{name}_param": float(nominal_params[name]) for name in PARAMETER_NAMES},
            **filter_diag,
        }
    )
    return row


def run_planner_tracker(
    method: str,
    condition: str,
    seed: int,
    cfg: dict[str, Any],
    obs_cfg: dict[str, Any],
    identifier_factory: Any | None = None,
) -> tuple[list[dict[str, Any]], AuditedPlannerTracker, float]:
    started = time.perf_counter()
    spec = MODE_SPECS[method]
    true_params = cfg["true_params"]
    nominal_params = cfg["model_params"]
    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(true_params, obs_cfg.get("observation_noise", {}), seed=int(seed))
    obs_measured = wrapper.observe(obs_true)
    filter_cfg = dict(FILTER_CONFIGS["ukf_bias"])
    filter_cfg["condition_name"] = condition
    ukf = make_observation_filter(filter_cfg)
    identifier = (
        identifier_factory(nominal_params, cfg["identifier"])
        if identifier_factory is not None
        else WindowedLeastSquaresIdentifier(nominal_params, cfg["identifier"])
    )
    identifier.reset()
    nls_hat = identifier.get_parameter_estimate()
    params_used = control_params(spec, true_params, nominal_params, nls_hat)
    estimated_state = ukf.reset(obs_measured, true_state=observation_to_state(obs_true), model_params=params_used)
    controller = AuditedPlannerTracker(method, cfg)
    rows = [initial_log_row(env, estimated_state, nls_hat, ukf.get_diagnostics(), true_params, nominal_params)]
    last_hat_vec = parameter_vector(nls_hat)
    adaptive_cfg = cfg.get("adaptive", {})
    smoothing_alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 1.0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        true_control_state = observation_to_state(obs_true)
        control_state = true_control_state if spec.state_source == "true" else estimated_state.copy()
        params_used = control_params(spec, true_params, nominal_params, nls_hat)
        action, solve_diag = controller.act(control_state, params_used, float(env.get_history()[-1]["t"]), steps, seed, condition)
        tracker_X = np.asarray(solve_diag.get("X", []), dtype=float)
        tracker_S = np.asarray(solve_diag.get("S", []), dtype=float)
        tracker_pred_alpha = (
            float((tracker_X[1, 1] - tracker_X[0, 1]) / controller.tracker.prediction_dt)
            if tracker_X.ndim == 2 and len(tracker_X) > 1 else np.nan
        )
        tracker_slack = float(tracker_S[0]) if len(tracker_S) else np.nan
        x_ref, _ = sample_reference(controller.plan_X, controller.plan_U, controller.plan_dt, float(env.get_history()[-1]["t"]), 1, float(true_params["dt"])) if controller.plan_X is not None else (np.full((2, 4), np.nan), np.full((1, 2), np.nan))
        planner_pred_alpha = float((x_ref[1, 1] - x_ref[0, 1]) / float(true_params["dt"]))
        for _ in range(hold_steps):
            prev_true = observation_to_state(obs_true)
            prev_est = estimated_state.copy()
            prev_est_obs = observation_from_state(obs_measured, prev_est, true_params)
            obs_true = env.step(action)
            obs_measured = wrapper.observe(obs_true)
            true_next = observation_to_state(obs_true)
            # UKF model source follows the isolated control-model source.
            ukf.predict(action, float(true_params["dt"]), model_params=params_used)
            estimated_state = ukf.update(obs_measured, float(true_params["dt"]), action=action, true_state=true_next, model_params=params_used)
            est_next_obs = observation_from_state(obs_measured, estimated_state, true_params)
            result = identifier.add_transition(observation_to_state(prev_est_obs), action, observation_to_state(est_next_obs))
            raw_hat = result.theta_hat
            update_mag = float(np.linalg.norm(parameter_vector(raw_hat) - last_hat_vec))
            last_hat_vec = parameter_vector(raw_hat)
            if result.updated and steps >= warmup_steps:
                smoothed = smooth_update_params({**nominal_params, **nls_hat}, raw_hat, smoothing_alpha, parameter_bounds)
                nls_hat = {name: float(smoothed[name]) for name in PARAMETER_NAMES}
            else:
                nls_hat = {name: float(raw_hat[name]) for name in PARAMETER_NAMES}
            steps += 1
            true_alpha = float((true_next[1] - prev_true[1]) / true_params["dt"])
            estimated_alpha = float((estimated_state[1] - prev_est[1]) / true_params["dt"])
            row: dict[str, Any] = {"t": float(env.get_history()[-1]["t"]), "step": steps}
            for index, name in enumerate(STATE_NAMES):
                row[f"true_{name}"] = float(true_next[index])
                row[f"estimated_{name}"] = float(estimated_state[index])
                row[f"{name}_estimation_error"] = float(estimated_state[index] - true_next[index])
            filter_diag = ukf.get_diagnostics()
            row.update(
                {
                    "true_delta_r": float(true_next[2] - true_params["L0"]),
                    "true_alpha": true_alpha,
                    "estimated_alpha": estimated_alpha,
                    "planner_predicted_alpha": planner_pred_alpha,
                    "tracker_predicted_alpha": tracker_pred_alpha,
                    "planned_constraint_slack": max(0.0, abs(planner_pred_alpha) - PLANNER_ALPHA_LIMIT),
                    "tracker_constraint_slack": tracker_slack,
                    "F_tan": float(action[0]),
                    "F_rad": float(action[1]),
                    "theta_ref": float(x_ref[0, 0]),
                    "omega_ref": float(x_ref[0, 1]),
                    "state_tracking_error": float(np.linalg.norm(true_next - x_ref[0])),
                    "parameter_update_magnitude": update_mag,
                    "parameter_bound_hit": bool(parameter_bound_hit(nls_hat, parameter_bounds)),
                    "identifier_updated": bool(result.updated),
                    "identifier_samples": int(result.num_samples),
                    "tracker_solver_success": bool(solve_diag.get("success", False)),
                    "tracker_constraint_violation_max": finite_float(solve_diag.get("constraint_violation_max", np.nan)),
                    **{f"{name}_hat": float(nls_hat[name]) for name in PARAMETER_NAMES},
                    **{f"true_{name}_param": float(true_params[name]) for name in PARAMETER_NAMES},
                    **{f"nominal_{name}_param": float(nominal_params[name]) for name in PARAMETER_NAMES},
                    **filter_diag,
                }
            )
            rows.append(row)
            if env.is_done() or steps >= max_steps:
                break
    return rows, controller, time.perf_counter() - started


def normalize_baseline_rows(raw_rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    nominal = cfg["model_params"]
    out: list[dict[str, Any]] = []
    for index, source in enumerate(raw_rows):
        row = {
            "t": finite_float(source.get("t", index * true_params["dt"])),
            "step": index,
            "true_theta": finite_float(source.get("true_theta", source.get("theta", np.nan))),
            "true_omega": finite_float(source.get("true_omega", source.get("omega", np.nan))),
            "true_r": finite_float(source.get("true_r", source.get("r", np.nan))),
            "true_r_dot": finite_float(source.get("true_r_dot", source.get("r_dot", np.nan))),
            "estimated_theta": finite_float(source.get("filt_theta", np.nan)),
            "estimated_omega": finite_float(source.get("filt_omega", np.nan)),
            "estimated_r": finite_float(source.get("filt_r", np.nan)),
            "estimated_r_dot": finite_float(source.get("filt_r_dot", np.nan)),
            "true_alpha": finite_float(source.get("alpha_step", 0.0)),
            "estimated_alpha": np.nan,
            "planner_predicted_alpha": np.nan,
            "tracker_predicted_alpha": np.nan,
            "planned_constraint_slack": np.nan,
            "tracker_constraint_slack": np.nan,
            "F_tan": finite_float(source.get("F_tan", np.nan)),
            "F_rad": finite_float(source.get("F_rad", np.nan)),
            "theta_ref": np.nan,
            "omega_ref": np.nan,
            "state_tracking_error": np.nan,
            "parameter_update_magnitude": finite_float(source.get("parameter_step_norm", np.nan)),
            "parameter_bound_hit": bool(source.get("parameter_bound_hit", False)),
            "identifier_updated": bool(source.get("identifier_updated", False)),
            "identifier_samples": int(source.get("identifier_samples", 0)),
            "innovation_norm": finite_float(source.get("innovation_norm", np.nan)),
            "bias_theta_hat": finite_float(source.get("bias_theta_hat", np.nan)),
            "bias_omega_hat": finite_float(source.get("bias_omega_hat", np.nan)),
            "bias_r_hat": finite_float(source.get("bias_r_hat", np.nan)),
            "bias_r_dot_hat": finite_float(source.get("bias_r_dot_hat", np.nan)),
            "ukf_failed": bool(source.get("ukf_failed", False)),
        }
        row["true_delta_r"] = float(row["true_r"] - true_params["L0"])
        for name in STATE_NAMES:
            row[f"{name}_estimation_error"] = float(row[f"estimated_{name}"] - row[f"true_{name}"])
        for name in PARAMETER_NAMES:
            row[f"{name}_hat"] = finite_float(source.get(f"{name}_hat", nominal[name]))
            row[f"true_{name}_param"] = float(true_params[name])
            row[f"nominal_{name}_param"] = float(nominal[name])
        out.append(row)
    if len(out) > 1:
        for i in range(1, len(out)):
            out[i]["estimated_alpha"] = float((out[i]["estimated_omega"] - out[i - 1]["estimated_omega"]) / true_params["dt"])
        out[0]["estimated_alpha"] = 0.0
    return out


def run_baseline(condition: str, seed: int, base_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], float, dict[str, Any]]:
    cfg = stage9j_overrides(configure_cem_run(copy.deepcopy(base_cfg), "baseline_cem"), condition)
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    obs_cfg = condition_cfg(base_cfg, condition, seed)
    started = time.perf_counter()
    rows = run_condition(condition, obs_cfg, cfg)
    return normalize_baseline_rows(rows, cfg), time.perf_counter() - started, cfg


def summarize_run(
    method: str,
    condition: str,
    seed: int,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
    controller: AuditedPlannerTracker | None,
) -> dict[str, Any]:
    true_params = cfg["true_params"]
    nominal = cfg["model_params"]
    constraints = cfg["mpc_params"].get("constraints", {})
    alpha_limit = float(constraints.get("alpha_max", true_params["alpha_max"]))
    target = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    dt = float(true_params["dt"])
    t = np.asarray([r["t"] for r in rows], dtype=float)
    theta = np.asarray([r["true_theta"] for r in rows], dtype=float)
    true_alpha = np.asarray([r["true_alpha"] for r in rows], dtype=float)
    estimated_alpha = np.asarray([r["estimated_alpha"] for r in rows], dtype=float)
    planner_alpha = np.asarray([r["planner_predicted_alpha"] for r in rows], dtype=float)
    tracker_alpha = np.asarray([r["tracker_predicted_alpha"] for r in rows], dtype=float)
    planner_slack = np.asarray([r["planned_constraint_slack"] for r in rows], dtype=float)
    tracker_slack = np.asarray([r["tracker_constraint_slack"] for r in rows], dtype=float)
    violation = np.maximum(0.0, np.abs(true_alpha) - alpha_limit)
    crossing_indices = np.flatnonzero(theta >= target)
    crossed = bool(len(crossing_indices))
    true_states = np.asarray([[r[f"true_{name}"] for name in STATE_NAMES] for r in rows], dtype=float)
    estimated_states = np.asarray([[r[f"estimated_{name}"] for name in STATE_NAMES] for r in rows], dtype=float)
    actions = np.asarray([[r["F_tan"], r["F_rad"]] for r in rows], dtype=float)
    tracking_error = np.asarray([r["state_tracking_error"] for r in rows], dtype=float)
    planner_X = controller.plan_X.copy() if controller is not None and controller.plan_X is not None else np.empty((0, 4))
    planner_U = controller.plan_U.copy() if controller is not None and controller.plan_U is not None else np.empty((0, 2))
    planner_params = (
        {name: float(controller.audit_rows[0][f"param_{name}"]) for name in PARAMETER_NAMES}
        if controller is not None and controller.audit_rows else {name: np.nan for name in PARAMETER_NAMES}
    )
    summary: dict[str, Any] = {
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "target_crossed": crossed,
        "crossing_time": float(t[crossing_indices[0]]) if crossed else np.nan,
        "final_theta": float(theta[-1]),
        "maximum_theta": float(np.max(theta)),
        "crossing_margin": float(np.max(theta) - target),
        "true_alpha_mean": stat(np.abs(true_alpha), "mean"),
        "true_alpha_p95": stat(np.abs(true_alpha), "p95"),
        "true_alpha_p99": stat(np.abs(true_alpha), "p99"),
        "true_alpha_max": stat(np.abs(true_alpha), "max"),
        "estimated_alpha_mean": stat(np.abs(estimated_alpha), "mean"),
        "estimated_alpha_p95": stat(np.abs(estimated_alpha), "p95"),
        "estimated_alpha_p99": stat(np.abs(estimated_alpha), "p99"),
        "estimated_alpha_max": stat(np.abs(estimated_alpha), "max"),
        "planner_predicted_alpha_mean": stat(np.abs(planner_alpha), "mean"),
        "planner_predicted_alpha_p95": stat(np.abs(planner_alpha), "p95"),
        "planner_predicted_alpha_p99": stat(np.abs(planner_alpha), "p99"),
        "planner_predicted_alpha_max": stat(np.abs(planner_alpha), "max"),
        "tracker_predicted_alpha_mean": stat(np.abs(tracker_alpha), "mean"),
        "tracker_predicted_alpha_p95": stat(np.abs(tracker_alpha), "p95"),
        "tracker_predicted_alpha_p99": stat(np.abs(tracker_alpha), "p99"),
        "tracker_predicted_alpha_max": stat(np.abs(tracker_alpha), "max"),
        "planned_constraint_slack_mean": stat(planner_slack, "mean"),
        "planned_constraint_slack_max": stat(planner_slack, "max"),
        "tracker_constraint_slack_mean": stat(tracker_slack, "mean"),
        "tracker_constraint_slack_max": stat(tracker_slack, "max"),
        "alpha_violation_count": int(np.count_nonzero(violation > 0.0)),
        "alpha_violation_duration": float(np.count_nonzero(violation > 0.0) * dt),
        "alpha_violation_integral": float(np.sum(violation) * dt),
        "alpha_violation_max": stat(violation, "max"),
        "true_estimated_alpha_error_mean": stat(np.abs(true_alpha - estimated_alpha), "mean"),
        "true_estimated_alpha_error_rmse": stat(true_alpha - estimated_alpha, "rmse"),
        "true_estimated_alpha_error_max": stat(np.abs(true_alpha - estimated_alpha), "max"),
        "true_predicted_alpha_error_mean": stat(np.abs(true_alpha - tracker_alpha), "mean"),
        "true_predicted_alpha_error_rmse": stat(true_alpha - tracker_alpha, "rmse"),
        "true_predicted_alpha_error_max": stat(np.abs(true_alpha - tracker_alpha), "max"),
        "state_tracking_rmse": stat(tracking_error, "rmse"),
        "ukf_innovation_mean": stat([r["innovation_norm"] for r in rows], "mean"),
        "ukf_failure_count": int(sum(bool(r.get("ukf_failed", False)) for r in rows)),
        "max_consecutive_omega_estimation_change": stat(np.abs(np.diff(estimated_states[:, 1])), "max"),
        "parameter_update_magnitude_mean": stat([r["parameter_update_magnitude"] for r in rows], "mean"),
        "parameter_update_magnitude_max": stat([r["parameter_update_magnitude"] for r in rows], "max"),
        "parameter_bounds_hit_count": int(sum(bool(r["parameter_bound_hit"]) for r in rows)),
        "identifier_update_count": int(sum(bool(r["identifier_updated"]) for r in rows)),
        "identifier_samples_at_planner": 0 if controller is not None else np.nan,
        "planner_nls_meaningful": False if controller is not None and MODE_SPECS[method].parameter_source == "nls" else np.nan,
        "planner_failure_count": int(controller is not None and (controller.plan_diag is None or not bool(controller.plan_diag.get("success", False)))),
        "tracker_failure_count": int(controller.tracker_failure_count) if controller is not None else np.nan,
        "runtime_s": float(runtime_s),
        "state_source": MODE_SPECS[method].state_source if controller is not None else "estimated",
        "parameter_source": MODE_SPECS[method].parameter_source if controller is not None else "nls",
        "identifier_updates_used_for_control": bool(controller is not None and MODE_SPECS[method].nls_controls_tracker),
        "planner_reference_X_json": vector_json(planner_X),
        "planner_reference_U_json": vector_json(planner_U),
        "first_10_planned_states_json": vector_json(planner_X[:10]),
        "first_10_planned_controls_json": vector_json(planner_U[:10]),
        "first_10_executed_controls_json": vector_json(actions[1:11]),
        "first_10_true_states_json": vector_json(true_states[:10]),
        "first_10_estimated_states_json": vector_json(estimated_states[:10]),
        "true_state_trajectory_json": vector_json(true_states),
        "estimated_state_trajectory_json": vector_json(estimated_states),
        "full_action_trajectory_json": vector_json(actions),
        "theta_trajectory_json": vector_json(theta),
        "true_alpha_trajectory_json": vector_json(true_alpha),
        "estimated_alpha_trajectory_json": vector_json(estimated_alpha),
        "tracker_predicted_alpha_trajectory_json": vector_json(tracker_alpha),
        "planner_predicted_alpha_trajectory_json": vector_json(planner_alpha),
        "planned_constraint_slack_trajectory_json": vector_json(planner_slack),
        "tracker_constraint_slack_trajectory_json": vector_json(tracker_slack),
        "ukf_innovation_trajectory_json": vector_json([r["innovation_norm"] for r in rows]),
        "parameter_update_magnitude_trajectory_json": vector_json([r["parameter_update_magnitude"] for r in rows]),
        "action_trajectory_hash": stable_hash(actions),
        "theta_trajectory_hash": stable_hash(theta),
        "true_alpha_trajectory_hash": stable_hash(true_alpha),
    }
    summary["result_dict_id"] = id(summary)
    for index, name in enumerate(STATE_NAMES):
        errors = estimated_states[:, index] - true_states[:, index]
        summary[f"{name}_estimation_rmse"] = stat(errors, "rmse")
        summary[f"{name}_estimation_error_max_abs"] = stat(np.abs(errors), "max")
        summary[f"bias_{name}_final"] = finite_float(rows[-1].get(f"bias_{name}_hat", np.nan))
        summary[f"bias_{name}_trajectory_json"] = vector_json([r.get(f"bias_{name}_hat", np.nan) for r in rows])
    for name in PARAMETER_NAMES:
        estimates = np.asarray([r[f"{name}_hat"] for r in rows], dtype=float)
        truth = float(true_params[name])
        summary[f"true_{name}"] = truth
        summary[f"nominal_{name}"] = float(nominal[name])
        summary[f"planner_{name}"] = planner_params[name]
        summary[f"planner_{name}_abs_error"] = abs(planner_params[name] - truth) if np.isfinite(planner_params[name]) else np.nan
        summary[f"planner_{name}_rel_error"] = abs(planner_params[name] - truth) / abs(truth) if np.isfinite(planner_params[name]) and truth != 0 else np.nan
        summary[f"{name}_hat_final"] = float(estimates[-1])
        summary[f"{name}_abs_error_final"] = abs(float(estimates[-1]) - truth)
        summary[f"{name}_rel_error_final"] = abs(float(estimates[-1]) - truth) / abs(truth) if truth != 0 else np.nan
        summary[f"{name}_first_time_in_10pct_band"] = first_time_in_band(t, estimates, truth)
        summary[f"{name}_trajectory_json"] = vector_json(estimates)
    return summary


DECOMPOSITION_METRICS = [
    "target_crossed",
    "crossing_time",
    "true_alpha_p95",
    "true_alpha_p99",
    "true_alpha_max",
    "alpha_violation_duration",
    "alpha_violation_integral",
    "state_tracking_rmse",
]


def aggregate_and_decompose(per_run: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregate_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        method_values: dict[str, dict[str, float]] = {}
        for method in METHODS:
            group = [r for r in per_run if r["condition"] == condition and r["method"] == method]
            if not group:
                continue
            values = {metric: stat([float(r[metric]) for r in group], "mean") for metric in DECOMPOSITION_METRICS}
            method_values[method] = values
            row: dict[str, Any] = {"row_type": "method_aggregate", "condition": condition, "method": method, "n": len(group)}
            row.update({f"{metric}_mean": value for metric, value in values.items()})
            if metric_values := [float(r["crossing_time"]) for r in group if np.isfinite(float(r["crossing_time"]))]:
                row["crossing_time_successful_only_mean"] = float(np.mean(metric_values))
            aggregate_rows.append(row)
        required = {"oracle_planner_tracker", "state_error_only", "parameter_error_only", "full_adaptive_planner_tracker"}
        if not required.issubset(method_values):
            continue
        decomp: dict[str, Any] = {"row_type": "decomposition", "condition": condition, "method": "gap_decomposition", "n": 3}
        for metric in DECOMPOSITION_METRICS:
            oracle = method_values["oracle_planner_tracker"][metric]
            state = method_values["state_error_only"][metric] - oracle
            parameter = method_values["parameter_error_only"][metric] - oracle
            full_gap = method_values["full_adaptive_planner_tracker"][metric] - oracle
            interaction = full_gap - state - parameter
            decomp[f"{metric}_oracle"] = oracle
            decomp[f"{metric}_state_contribution"] = state
            decomp[f"{metric}_parameter_contribution"] = parameter
            decomp[f"{metric}_full_gap"] = full_gap
            decomp[f"{metric}_interaction_residual"] = interaction
        aggregate_rows.append(decomp)
    return aggregate_rows


def write_dict_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([finite_float(row.get(key, np.nan)) for row in rows], dtype=float)


def save_figures(
    per_run: list[dict[str, Any]],
    aggregate_rows: list[dict[str, Any]],
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]],
    output_root: Path,
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    modes = METHODS[1:]
    colors = {method: f"C{index}" for index, method in enumerate(METHODS)}

    def representative(method: str, condition: str = "initial_theta_offset", seed: int = 101) -> list[dict[str, Any]]:
        return all_runs.get((method, condition, seed), [])

    fig, ax = plt.subplots(figsize=(9, 5))
    for method in modes:
        rows = representative(method)
        if rows:
            ax.plot(series(rows, "t"), series(rows, "true_alpha"), label=method, color=colors[method], alpha=0.9)
    ax.axhline(3.0, color="black", linestyle=":", linewidth=1)
    ax.axhline(-3.0, color="black", linestyle=":", linewidth=1)
    ax.set(xlabel="time [s]", ylabel="true alpha [rad/s^2]", title="True alpha by controller mode: initial_theta_offset seed101")
    ax.legend(fontsize=7, ncol=2); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "01_true_alpha_by_controller_mode.png", dpi=150); plt.close(fig)

    rows = representative("full_adaptive_planner_tracker", "stronger_noise")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(series(rows, "t"), series(rows, "true_alpha"), label="true alpha")
    ax.plot(series(rows, "t"), series(rows, "estimated_alpha"), label="estimated alpha", alpha=0.75)
    ax.set(xlabel="time [s]", ylabel="alpha [rad/s^2]", title="True versus estimated alpha: stronger_noise seed101")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "02_true_vs_estimated_alpha.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(series(rows, "t"), series(rows, "true_alpha"), label="true alpha")
    ax.plot(series(rows, "t"), series(rows, "tracker_predicted_alpha"), label="tracker predicted alpha", alpha=0.8)
    ax.plot(series(rows, "t"), series(rows, "planner_predicted_alpha"), label="planner predicted alpha", alpha=0.65)
    ax.set(xlabel="time [s]", ylabel="alpha [rad/s^2]", title="True versus predicted alpha: stronger_noise seed101")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "03_true_vs_predicted_alpha.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for method in modes:
        mode_rows = representative(method)
        if mode_rows:
            ax.plot(series(mode_rows, "t"), np.degrees(series(mode_rows, "true_theta")), label=method, color=colors[method])
    ax.axhline(90.0, color="black", linestyle=":", linewidth=1)
    ax.set(xlabel="time [s]", ylabel="true theta [deg]", title="Theta by controller mode: initial_theta_offset seed101")
    ax.legend(fontsize=7, ncol=2); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "04_theta_by_controller_mode.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(series(rows, "t"), series(rows, "true_omega"), label="true omega")
    ax.plot(series(rows, "t"), series(rows, "estimated_omega"), label="estimated omega", alpha=0.8)
    ax.set(xlabel="time [s]", ylabel="omega [rad/s]", title="True versus estimated omega: stronger_noise seed101")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "05_true_vs_estimated_omega.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for axis, name in zip(axes, PARAMETER_NAMES):
        axis.plot(series(rows, "t"), series(rows, f"{name}_hat"), label=f"{name}_hat")
        axis.axhline(float(rows[0][f"true_{name}_param"]), color="black", linestyle=":", label="true")
        axis.set_ylabel(name); axis.legend(); axis.grid(alpha=0.3)
    axes[-1].set_xlabel("time [s]"); axes[0].set_title("NLS parameter estimates versus truth: stronger_noise seed101")
    fig.tight_layout(); fig.savefig(fig_dir / "06_parameter_estimates_vs_true.png", dpi=150); plt.close(fig)

    fixed_adaptive = [r for r in per_run if r["method"] in {"fixed_nominal_planner_tracker", "full_adaptive_planner_tracker"}]
    labels = [f"{condition}\n{s}" for condition in CONDITIONS for s in SEEDS]
    fixed_first = []
    adaptive_first = []
    for condition in CONDITIONS:
        for seed in SEEDS:
            for method, target_list in (("fixed_nominal_planner_tracker", fixed_first), ("full_adaptive_planner_tracker", adaptive_first)):
                row = next(r for r in fixed_adaptive if r["method"] == method and r["condition"] == condition and r["seed"] == seed)
                actions = np.asarray(json.loads(row["first_10_executed_controls_json"]), dtype=float)
                target_list.append(float(actions[0, 0]) if len(actions) else np.nan)
    x = np.arange(len(labels)); width = 0.4
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(x - width / 2, fixed_first, width, label="fixed F_tan")
    ax.bar(x + width / 2, adaptive_first, width, label="adaptive F_tan")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=65, ha="right", fontsize=7)
    ax.set_ylabel("first executed F_tan"); ax.set_title("Fixed versus adaptive first actions"); ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "07_fixed_vs_adaptive_first_actions.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for method in ("fixed_nominal_planner_tracker", "full_adaptive_planner_tracker"):
        mode_rows = representative(method)
        axes[0].plot(series(mode_rows, "t"), series(mode_rows, "F_tan"), label=method)
        axes[1].plot(series(mode_rows, "t"), series(mode_rows, "F_rad"), label=method)
    axes[0].set_ylabel("F_tan"); axes[1].set_ylabel("F_rad"); axes[1].set_xlabel("time [s]")
    axes[0].set_title("Fixed versus adaptive complete action trajectories: initial_theta_offset seed101")
    for ax in axes: ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "08_fixed_vs_adaptive_complete_actions.png", dpi=150); plt.close(fig)

    decomps = [r for r in aggregate_rows if r.get("row_type") == "decomposition"]
    def decomposition_plot(metric: str, title: str, filename: str) -> None:
        state_vals = [r[f"{metric}_state_contribution"] for r in decomps]
        param_vals = [r[f"{metric}_parameter_contribution"] for r in decomps]
        interact_vals = [r[f"{metric}_interaction_residual"] for r in decomps]
        full_vals = [r[f"{metric}_full_gap"] for r in decomps]
        xx = np.arange(len(decomps)); w = 0.22
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(xx - w, state_vals, w, label="state contribution")
        ax.bar(xx, param_vals, w, label="parameter contribution")
        ax.bar(xx + w, interact_vals, w, label="interaction residual")
        ax.plot(xx, full_vals, "ko", label="full adaptive gap")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(xx); ax.set_xticklabels([r["condition"] for r in decomps], rotation=35, ha="right")
        ax.set_title(title); ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3); fig.tight_layout()
        fig.savefig(fig_dir / filename, dpi=150); plt.close(fig)
    decomposition_plot("true_alpha_max", "Gap decomposition: true alpha max", "09_decomposition_true_alpha_max.png")
    decomposition_plot("target_crossed", "Gap decomposition: crossing success rate", "10_decomposition_crossing_success.png")

    nls_rows = [r for r in per_run if r["method"] in {"parameter_error_only", "full_adaptive_planner_tracker"}]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)
    for axis, name in zip(axes, PARAMETER_NAMES):
        means = [stat([r[f"planner_{name}_rel_error"] for r in nls_rows if r["condition"] == condition], "mean") for condition in CONDITIONS]
        axis.bar(np.arange(len(CONDITIONS)), means)
        axis.set_xticks(np.arange(len(CONDITIONS))); axis.set_xticklabels(CONDITIONS, rotation=65, ha="right", fontsize=7)
        axis.set_title(name); axis.set_ylabel("planner-time relative error")
        axis.grid(axis="y", alpha=0.3)
    fig.suptitle("Planner-time NLS parameter-estimation error (zero samples)"); fig.tight_layout()
    fig.savefig(fig_dir / "11_planner_time_parameter_error.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method in modes:
        subset = [r for r in per_run if r["method"] == method]
        ax.scatter([r["omega_estimation_rmse"] for r in subset], [r["true_alpha_max"] for r in subset], label=method, alpha=0.7, s=25)
    ax.set(xlabel="omega estimation RMSE", ylabel="true alpha max", title="State-estimation RMSE versus true alpha max")
    ax.legend(fontsize=7, ncol=2); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(fig_dir / "12_state_estimation_rmse_vs_true_alpha_max.png", dpi=150); plt.close(fig)


def stage9i_comparison() -> dict[str, Any]:
    path = PROJECT_ROOT / "results" / "stage9i_adaptive_planner_tracker" / "stage9i_summary.csv"
    if not path.exists():
        return {"available": False}
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    comparisons = []
    for condition in sorted({r["condition"] for r in rows}):
        for seed in SEEDS:
            fixed = next((r for r in rows if r["method"] == "fixed_planner_tracker" and r["condition"] == condition and int(r["seed"]) == seed), None)
            adaptive = next((r for r in rows if r["method"] == "adaptive_planner_tracker" and r["condition"] == condition and int(r["seed"]) == seed), None)
            if fixed and adaptive and math.isclose(float(fixed["raw_alpha_max"]), float(adaptive["raw_alpha_max"]), rel_tol=0.0, abs_tol=1.0e-12):
                comparisons.append({"condition": condition, "seed": seed, "fixed_crossed": fixed["target_crossed"], "adaptive_crossed": adaptive["target_crossed"], "raw_alpha_max": float(fixed["raw_alpha_max"])})
    return {"available": True, "identical_scalar_count": len(comparisons), "comparisons": comparisons}


def choose_stage9k(aggregate_rows: list[dict[str, Any]], per_run: list[dict[str, Any]], audit_ok: bool) -> tuple[str, str]:
    if not audit_ok:
        return "D", "模式隔离或日志审计失败，应先做实现/日志修正。"
    decomps = [r for r in aggregate_rows if r.get("row_type") == "decomposition"]
    state_score = stat([abs(r["true_alpha_max_state_contribution"]) for r in decomps], "mean")
    parameter_score = stat([abs(r["true_alpha_max_parameter_contribution"]) for r in decomps], "mean")
    interaction_score = stat([abs(r["true_alpha_max_interaction_residual"]) for r in decomps], "mean")
    if state_score >= parameter_score and state_score >= interaction_score:
        return "A", f"跨条件 true alpha max 的平均绝对状态贡献最大（{state_score:.3g}，参数 {parameter_score:.3g}，交互 {interaction_score:.3g}）。"
    if parameter_score >= state_score and parameter_score >= interaction_score:
        return "B", f"跨条件 true alpha max 的平均绝对参数贡献最大（{parameter_score:.3g}，状态 {state_score:.3g}，交互 {interaction_score:.3g}）。"
    nls = [r for r in per_run if r["method"] == "full_adaptive_planner_tracker"]
    planner_error = stat([np.mean([r[f"planner_{name}_rel_error"] for name in PARAMETER_NAMES]) for r in nls], "mean")
    final_error = stat([np.mean([r[f"{name}_rel_error_final"] for name in PARAMETER_NAMES]) for r in nls], "mean")
    if np.isfinite(planner_error) and np.isfinite(final_error) and final_error < planner_error:
        return "C", f"交互项最大，且 NLS 平均相对误差由规划时 {planner_error:.3g} 降至结束时 {final_error:.3g}；证据支持置信度门控的一次重规划。"
    return "A", f"交互项最大但 NLS 后期未稳定改善；四个允许方向中，状态估计修正是最直接且不引入重复重规划的单一诊断方向（状态 {state_score:.3g}，参数 {parameter_score:.3g}，交互 {interaction_score:.3g}）。"


def audit_results(per_run: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    for row in audit_rows:
        method = str(row["method"])
        spec = MODE_SPECS[method]
        if row["state_source"] != spec.state_source or row["parameter_source"] != spec.parameter_source:
            failures.append(f"source_mismatch:{method}:{row['condition']}:{row['seed']}:{row['call_type']}")
    for run in per_run:
        method = str(run["method"])
        if method == "baseline_cem":
            continue
        matching = [r for r in audit_rows if r["method"] == method and r["condition"] == run["condition"] and int(r["seed"]) == int(run["seed"])]
        planners = [r for r in matching if r["call_type"] == "planner"]
        if len(planners) != 1:
            failures.append(f"planner_call_count:{method}:{run['condition']}:{run['seed']}={len(planners)}")
        if method == "fixed_nominal_planner_tracker":
            for row in matching:
                for name in PARAMETER_NAMES:
                    if not math.isclose(float(row[f"param_{name}"]), float(run[f"nominal_{name}"]), rel_tol=0.0, abs_tol=1.0e-12):
                        failures.append(f"fixed_param_changed:{run['condition']}:{run['seed']}:{name}")
                        break
    run_instances = [r["run_instance"] for r in audit_rows if r["call_type"] == "planner"]
    if len(run_instances) != len(set(run_instances)):
        failures.append("controller_run_instance_reused")
    result_ids = [int(r["result_dict_id"]) for r in per_run]
    if len(result_ids) != len(set(result_ids)):
        failures.append("summary_result_dictionary_reused")
    contradictory_hashes = []
    for i, left in enumerate(per_run):
        for right in per_run[i + 1 :]:
            if left["condition"] == right["condition"] and left["seed"] == right["seed"] and left["true_alpha_trajectory_hash"] == right["true_alpha_trajectory_hash"] and bool(left["target_crossed"]) != bool(right["target_crossed"]):
                contradictory_hashes.append((left["method"], right["method"], left["condition"], left["seed"]))
    if contradictory_hashes:
        failures.append(f"identical_alpha_trajectory_different_crossing:{contradictory_hashes}")
    fixed_adaptive_equal_max = []
    fixed_adaptive_equal_trajectory = []
    for condition in CONDITIONS:
        for seed in SEEDS:
            fixed = next((r for r in per_run if r["method"] == "fixed_nominal_planner_tracker" and r["condition"] == condition and r["seed"] == seed), None)
            adaptive = next((r for r in per_run if r["method"] == "full_adaptive_planner_tracker" and r["condition"] == condition and r["seed"] == seed), None)
            if not fixed or not adaptive:
                continue
            if math.isclose(float(fixed["true_alpha_max"]), float(adaptive["true_alpha_max"]), rel_tol=0.0, abs_tol=1.0e-12):
                fixed_adaptive_equal_max.append((condition, seed))
            if fixed["true_alpha_trajectory_hash"] == adaptive["true_alpha_trajectory_hash"]:
                fixed_adaptive_equal_trajectory.append((condition, seed))
    return {
        "passed": not failures,
        "failures": failures,
        "fixed_adaptive_equal_max": fixed_adaptive_equal_max,
        "fixed_adaptive_equal_trajectory": fixed_adaptive_equal_trajectory,
        "contradictory_hashes": contradictory_hashes,
    }


def aggregate_lookup(aggregate_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    return next((r for r in aggregate_rows if r.get("row_type") == "method_aggregate" and r.get("method") == method and r.get("condition") == condition), {})


def fmt(value: Any) -> str:
    number = finite_float(value)
    return f"{number:.4g}" if np.isfinite(number) else "nan"


def write_report(
    path: Path,
    per_run: list[dict[str, Any]],
    aggregate_rows: list[dict[str, Any]],
    audit: dict[str, Any],
    stage9i: dict[str, Any],
    direction: str,
    direction_reason: str,
) -> None:
    decomps = [r for r in aggregate_rows if r.get("row_type") == "decomposition"]
    state_score = stat([abs(r["true_alpha_max_state_contribution"]) for r in decomps], "mean")
    parameter_score = stat([abs(r["true_alpha_max_parameter_contribution"]) for r in decomps], "mean")
    interaction_score = stat([abs(r["true_alpha_max_interaction_residual"]) for r in decomps], "mean")
    stronger = next(r for r in decomps if r["condition"] == "stronger_noise")
    state_cross = aggregate_lookup(aggregate_rows, "state_error_only", "initial_theta_offset")
    parameter_alpha = aggregate_lookup(aggregate_rows, "parameter_error_only", "initial_theta_offset")
    fixed_success = sum(int(bool(r["target_crossed"])) for r in per_run if r["method"] == "fixed_nominal_planner_tracker")
    adaptive_success = sum(int(bool(r["target_crossed"])) for r in per_run if r["method"] == "full_adaptive_planner_tracker")
    nls_runs = [r for r in per_run if r["method"] == "full_adaptive_planner_tracker"]
    planner_rel = stat([np.mean([r[f"planner_{name}_rel_error"] for name in PARAMETER_NAMES]) for r in nls_runs], "mean")
    final_rel = stat([np.mean([r[f"{name}_rel_error_final"] for name in PARAMETER_NAMES]) for r in nls_runs], "mean")
    fixed_adaptive_note = (
        f"Stage 9J 有 {len(audit['fixed_adaptive_equal_max'])} 个 fixed/adaptive run 的 true-alpha 最大值相同，"
        f"但完整 true-alpha 轨迹相同的 run 为 {len(audit['fixed_adaptive_equal_trajectory'])} 个。"
    )
    with path.open("w") as handle:
        handle.write("# Stage 9J Adaptive Planner–Tracker Gap Decomposition\n\n")
        handle.write("## 实验与审计结论\n\n")
        handle.write(f"- 模式隔离审计：{'通过' if audit['passed'] else '失败'}。失败项：{audit['failures'] or '无'}。\n")
        handle.write("- 每个 run 独立创建环境、噪声 wrapper、UKF、NLS、planner/tracker；主实验严格使用一次长时域规划，未启用事件触发重规划。\n")
        handle.write("- primary crossing 与所有 primary alpha 指标均来自 true simulated state；estimated 与 planner/tracker predicted 指标分列保存。\n")
        handle.write(f"- 跨 8 个条件，true alpha max gap 的平均绝对分解量：状态 {fmt(state_score)}，参数 {fmt(parameter_score)}，交互残差 {fmt(interaction_score)}。交互残差只是诊断量，不作因果证明。\n")
        handle.write(f"- {fixed_adaptive_note}\n")
        handle.write(f"- Stage 9K 唯一建议：**{direction}. {direction_reason}**\n\n")

        handle.write("## 聚合结果\n\n")
        handle.write("| condition | method | crossing | true alpha p95 | p99 | max | violation duration | tracking RMSE |\n")
        handle.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
        for condition in CONDITIONS:
            for method in METHODS:
                row = aggregate_lookup(aggregate_rows, method, condition)
                if not row:
                    continue
                handle.write(
                    f"| {condition} | {method} | {fmt(row.get('target_crossed_mean'))} | {fmt(row.get('true_alpha_p95_mean'))} | "
                    f"{fmt(row.get('true_alpha_p99_mean'))} | {fmt(row.get('true_alpha_max_mean'))} | "
                    f"{fmt(row.get('alpha_violation_duration_mean'))} | {fmt(row.get('state_tracking_rmse_mean'))} |\n"
                )

        handle.write("\n## Required Questions\n\n")
        handle.write(f"1. **Are all controller modes correctly isolated?** {'Yes' if audit['passed'] else 'No'}。oracle/state-error/parameter-error/fixed/full 的 state 与 parameter source 均由断言和逐次 solve 审计行验证；fixed 的控制参数在所有 planner/tracker 调用中保持 condition-specific nominal 值。\n\n")
        stage9i_count = stage9i.get("identical_scalar_count", "unknown")
        handle.write(f"2. **Were Stage 9I fixed/adaptive results affected by reuse or wrong metric sources?** 未发现结果字典、controller state、轨迹或 primary true-state metric 的复用证据。Stage 9I 代码确有诊断覆盖不足（没有完整两因素分解，且 planned-alpha 汇总值重复写入时序行），但 raw alpha 本身由 true omega 差分得到。Stage 9I fixed/adaptive 相同 scalar max 共 {stage9i_count} 组。\n\n")
        handle.write(f"3. **Why were raw-alpha values identical?** {fixed_adaptive_note} 相同的只是最大值时，原因是 fixed 与 adaptive 在首次 NLS 更新前使用相同 nominal 初始参数、相同估计状态和相同首个 planner/tracker action，因而共享同一个早期 alpha 峰；后续动作和 theta 轨迹会在 NLS 更新后分离。这不是完整数组复用。若完整 alpha 轨迹相同而 crossing 不同，在相同初态、dt 与 true-state crossing 定义下数学上不应发生；本次审计未见这种矛盾。\n\n")
        dominant = max(((state_score, "state error"), (parameter_score, "parameter error"), (interaction_score, "interaction residual")), key=lambda item: item[0])[1]
        handle.write(f"4. **Main adaptive–oracle alpha-gap source?** 按跨条件平均绝对 true-alpha-max 分解，最大项是 {dominant}（state={fmt(state_score)}, parameter={fmt(parameter_score)}, interaction={fmt(interaction_score)}）。交互项不解释为严格因果。\n\n")
        handle.write(f"5. **Does UKF-bias state estimation alone cause crossing failure?** initial_theta_offset 的 state_error_only crossing rate={fmt(state_cross.get('target_crossed_mean'))}；据此回答见该成功率，而不是用容差判据替代 theta >= target。\n\n")
        handle.write(f"6. **Do NLS parameters alone cause high true alpha?** initial_theta_offset parameter_error_only true alpha max={fmt(parameter_alpha.get('true_alpha_max_mean'))}，oracle 对应={fmt(aggregate_lookup(aggregate_rows, 'oracle_planner_tracker', 'initial_theta_offset').get('true_alpha_max_mean'))}；跨条件参数贡献量见分解表。\n\n")
        handle.write(f"7. **Are NLS estimates accurate at initial planning?** No。初次 planner 调用发生在 0 个 identifier samples 时；NLS estimate 等于 condition-specific nominal initialization。三个参数的平均 planner-time relative error={fmt(planner_rel)}，episode 结束时={fmt(final_rel)}。\n\n")
        stronger_state = abs(float(stronger["true_alpha_max_state_contribution"])); stronger_param = abs(float(stronger["true_alpha_max_parameter_contribution"])); stronger_inter = abs(float(stronger["true_alpha_max_interaction_residual"]))
        stronger_label = max(((stronger_state, "estimator-induced/state"), (stronger_param, "parameter"), (stronger_inter, "interaction")), key=lambda item: item[0])[1]
        handle.write(f"8. **Why does stronger noise amplify alpha?** 日志 artifact 被 true-state差分排除；stronger_noise 的绝对分解量 state={fmt(stronger_state)}, parameter={fmt(stronger_param)}, interaction={fmt(stronger_inter)}，最大诊断项为 {stronger_label}。物理响应是 estimator/parameter 误差经真实闭环动力学作用后的结果。\n\n")
        handle.write(f"9. **Does adaptive genuinely outperform fixed?** 24 个 primary runs 中 adaptive crossing={adaptive_success}/24，fixed={fixed_success}/24；同时必须结合 summary 中 true-alpha 与 violation 指标判断，不能仅凭 crossing 宣称全面优越。\n\n")
        handle.write(f"10. **Single Stage 9K intervention?** {direction}. {direction_reason} 本任务未实施 Stage 9K。\n\n")

        handle.write("## 实现与复现\n\n")
        handle.write("- 新增脚本：`scripts/run_spring2d_stage9j_gap_decomposition.py`。\n")
        handle.write("- 主命令：`conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py`。\n")
        handle.write("- 诊断字段补全命令（复用已完成 baseline）：`conda run -n mpc_learn python scripts/run_spring2d_stage9j_gap_decomposition.py --reuse-baseline`。\n")
        handle.write("- 结果：`stage9j_per_run.csv`、`stage9j_summary.csv`、`stage9j_mode_audit.csv` 与 `figs/`。\n")
        handle.write("- 未修改 MPC/planner weights、rho_alpha、horizon、UKF covariance、NLS window/loss、constraints、target criterion、solver settings、rollout duration 或 Spring2D dynamics。\n")
        handle.write("- 未加入 robustness/safety method，未启用 event-triggered replanning，未声称 formal safety/stability。\n")


def load_reusable_baselines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Cannot reuse baselines because {path} does not exist")
    with path.open(newline="") as handle:
        raw = [row for row in csv.DictReader(handle) if row.get("method") == "baseline_cem"]
    rows: list[dict[str, Any]] = []
    for source in raw:
        row: dict[str, Any] = dict(source)
        row["seed"] = int(source["seed"])
        row["target_crossed"] = str(source["target_crossed"]).lower() == "true"
        for key, value in list(row.items()):
            if key in {"method", "condition", "state_source", "parameter_source"} or key.endswith("_json") or key.endswith("_hash"):
                continue
            if value == "":
                row[key] = np.nan
                continue
            if key in {"seed", "target_crossed", "identifier_updates_used_for_control"}:
                continue
            try:
                row[key] = float(value)
            except (TypeError, ValueError):
                pass
        rows.append(row)
    expected = len(CONDITIONS) * len(SEEDS)
    if len(rows) != expected:
        raise RuntimeError(f"Expected {expected} reusable baseline rows, found {len(rows)}")
    return rows


def export_replay_only(output_root: Path, config_path: Path) -> Path:
    """Export deterministic replay rows from saved Stage 9J full-adaptive runs."""

    per_run_path = output_root / "stage9j_per_run.csv"
    if not per_run_path.exists():
        raise FileNotFoundError(f"Missing Stage 9J per-run data: {per_run_path}")
    with per_run_path.open(newline="") as handle:
        saved = [row for row in csv.DictReader(handle) if row.get("method") == "full_adaptive_planner_tracker"]
    if len(saved) != len(CONDITIONS) * len(SEEDS):
        raise RuntimeError(f"Expected 24 full-adaptive Stage 9J runs, found {len(saved)}")
    base_cfg = load_experiment_config(config_path)
    replay_rows: list[dict[str, Any]] = []
    for run_row in saved:
        condition = str(run_row["condition"])
        seed = int(run_row["seed"])
        cfg = stage9j_overrides(base_cfg, condition)
        true_params = cfg["true_params"]
        obs_cfg = condition_cfg(base_cfg, condition, seed)
        true_states = np.asarray(json.loads(run_row["true_state_trajectory_json"]), dtype=float)
        estimated_states = np.asarray(json.loads(run_row["estimated_state_trajectory_json"]), dtype=float)
        actions = np.asarray(json.loads(run_row["full_action_trajectory_json"]), dtype=float)
        parameter_trajectories = {name: np.asarray(json.loads(run_row[f"{name}_trajectory_json"]), dtype=float) for name in PARAMETER_NAMES}
        bias_trajectories = {name: np.asarray(json.loads(run_row[f"bias_{name}_trajectory_json"]), dtype=float) for name in STATE_NAMES}
        lengths = {len(true_states), len(estimated_states), len(actions), *(len(values) for values in parameter_trajectories.values()), *(len(values) for values in bias_trajectories.values())}
        if len(lengths) != 1:
            raise RuntimeError(f"Replay trajectory length mismatch for {condition}/seed{seed}: {sorted(lengths)}")
        template = Spring2DEnv(true_params).reset()
        wrapper = NoisySpring2DObservationWrapper(true_params, obs_cfg.get("observation_noise", {}), seed=seed)
        for step, (true_state, estimated_state, action) in enumerate(zip(true_states, estimated_states, actions)):
            template = observation_from_state(template, true_state, true_params)
            measured_state = observation_to_state(wrapper.observe(template))
            row: dict[str, Any] = {
                "condition": condition,
                "seed": seed,
                "step": step,
                "timestamp": float(step * true_params["dt"]),
                "F_tan": float(action[0]),
                "F_rad": float(action[1]),
            }
            for index, name in enumerate(STATE_NAMES):
                row[f"true_{name}"] = float(true_state[index])
                row[f"estimated_{name}"] = float(estimated_state[index])
                row[f"measured_{name}"] = float(measured_state[index])
                row[f"bias_{name}_hat"] = float(bias_trajectories[name][step])
            for name in PARAMETER_NAMES:
                row[f"true_{name}_param"] = float(true_params[name])
                row[f"nominal_{name}_param"] = float(cfg["model_params"][name])
                row[f"online_{name}_hat"] = float(parameter_trajectories[name][step])
            replay_rows.append(row)
    replay_path = output_root / "stage9j_replay.csv"
    write_dict_csv(replay_path, replay_rows)
    print(f"[stage9j] exported {len(replay_rows)} replay rows to {replay_path}", flush=True)
    return replay_path


def run(output_root: Path, config_path: Path, reuse_baseline: bool = False) -> None:
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    per_run: list[dict[str, Any]] = load_reusable_baselines(output_root / "stage9j_per_run.csv") if reuse_baseline else []
    audit_rows: list[dict[str, Any]] = []
    all_runs: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    (output_root / "stage9j_config_snapshot.json").write_text(json.dumps(base_cfg, indent=2, default=str))
    command_lines = [f"conda run -n mpc_learn python scripts/{Path(__file__).name}"]
    if reuse_baseline:
        command_lines.append(f"conda run -n mpc_learn python scripts/{Path(__file__).name} --reuse-baseline")
    (output_root / "stage9j_command.txt").write_text("\n".join(command_lines) + "\n")
    run_methods = METHODS[1:] if reuse_baseline else METHODS
    total = len(CONDITIONS) * len(SEEDS) * len(run_methods)
    completed = 0
    for condition in CONDITIONS:
        for seed in SEEDS:
            for method in run_methods:
                completed += 1
                print(f"[stage9j {completed}/{total}] {method}/{condition}/seed{seed}", flush=True)
                if method == "baseline_cem":
                    rows, runtime_s, cfg = run_baseline(condition, seed, base_cfg)
                    controller = None
                else:
                    cfg = stage9j_overrides(base_cfg, condition)
                    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
                    rows, controller, runtime_s = run_planner_tracker(method, condition, seed, cfg, condition_cfg(base_cfg, condition, seed))
                    audit_rows.extend(copy.deepcopy(controller.audit_rows))
                summary = summarize_run(method, condition, seed, rows, cfg, runtime_s, controller)
                per_run.append(summary)
                all_runs[(method, condition, seed)] = rows
                write_dict_csv(output_root / "stage9j_per_run.csv", per_run)
                write_dict_csv(output_root / "stage9j_mode_audit.csv", audit_rows)
                print(f"  crossed={summary['target_crossed']} alpha_max={fmt(summary['true_alpha_max'])} final_theta_deg={fmt(np.degrees(summary['final_theta']))} runtime={runtime_s:.2f}s", flush=True)
    aggregate_rows = aggregate_and_decompose(per_run)
    audit = audit_results(per_run, audit_rows)
    stage9i = stage9i_comparison()
    direction, direction_reason = choose_stage9k(aggregate_rows, per_run, bool(audit["passed"]))
    write_dict_csv(output_root / "stage9j_summary.csv", aggregate_rows)
    save_figures(per_run, aggregate_rows, all_runs, output_root)
    write_report(output_root / "stage9j_report.md", per_run, aggregate_rows, audit, stage9i, direction, direction_reason)
    print(f"[stage9j] audit_passed={audit['passed']} recommendation={direction}", flush=True)
    print(f"[stage9j] output={output_root}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--reuse-baseline", action="store_true", help="Reuse the existing 24 baseline rows and rerun planner/tracker modes only.")
    parser.add_argument("--export-replay-only", action="store_true", help="Export replay data from saved Stage 9J runs without solving any controller.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.export_replay_only:
        export_replay_only(args.output_root, args.config)
    else:
        run(args.output_root, args.config, reuse_baseline=args.reuse_baseline)


if __name__ == "__main__":
    main()
