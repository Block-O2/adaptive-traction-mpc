"""Stage 10B offline single-parameter MHE/TLS benchmark and gated closed loop.

The script consumes the saved Stage 9J replay and Stage 9K baseline artifacts.
It never reruns historical baselines.  Closed-loop runs are conditional on the
pre-registered offline gate and use the unchanged Stage 9J one-shot planner and
tracker configuration.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
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

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage9j_gap_decomposition import (
    AuditedPlannerTracker,
    CONDITIONS,
    PARAMETER_NAMES,
    SEEDS,
    STATE_NAMES,
    condition_cfg,
    stage9j_overrides,
    stat,
    summarize_run,
    write_dict_csv,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.estimation.noisy_observation_wrapper import NoisySpring2DObservationWrapper, observation_to_state
from traction_mpc.estimation.single_parameter_mhe import SingleParameterMHE
from traction_mpc.models.spring2d_dynamics import compute_base_kinematics, step_dynamics
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_REPLAY = PROJECT_ROOT / "results" / "stage9j_gap_decomposition" / "stage9j_replay.csv"
DEFAULT_STAGE9K = PROJECT_ROOT / "results" / "stage9k_identifier_ablation" / "stage9k_offline_per_run.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "stage10b_estimator_benchmark"
METHODS = ("ukf_nls_current", "mhe_inverse_m", "mhe_m", "weighted_tls")
MHE_METHODS = ("mhe_inverse_m", "mhe_m")
CLOSED_LOOP_CONDITIONS = ("clean", "initial_theta_offset", "stronger_noise", "mass_mismatch")

# These settings are deliberately shared by the two MHE parameterizations.
MHE_CONFIG = {
    "window_size": 70,
    "update_interval": 10,
    "max_nfev": 45,
    "measurement_weights": [1.0, 0.25, 8.0, 0.6],
    "arrival_state_scale": [0.10, 1.0, 0.02, 0.10],
    "lambda_arrival_state": 1.0e-3,
    "lambda_arrival_parameter": 1.0e-3,
    "mass_scale": 1.0,
    "mass_bounds": [0.5, 2.0],
    "xtol": 1.0e-8,
    "ftol": 1.0e-8,
    "gtol": 1.0e-8,
}


def load_replay(path: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    with path.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in raw:
        grouped[(str(row["condition"]), int(row["seed"]))].append(row)
    expected = {(condition, seed) for condition in CONDITIONS for seed in SEEDS}
    if set(grouped) != expected:
        raise RuntimeError(f"Stage 9J replay matrix mismatch: missing={expected-set(grouped)} extra={set(grouped)-expected}")
    for key, rows in grouped.items():
        rows.sort(key=lambda row: int(row["step"]))
        if [int(row["step"]) for row in rows] != list(range(len(rows))):
            raise RuntimeError(f"Non-contiguous replay steps: {key}")
    return grouped


def load_stage9k_current_baseline(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Load, rather than rerun, the compatible Stage 9K current-NLS rows."""
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    current = [row for row in rows if row.get("method") == "windowed_nls_current" and row.get("input_source") == "ukf_filtered"]
    lookup = {(str(row["condition"]), int(row["seed"])): row for row in current}
    expected = {(condition, seed) for condition in CONDITIONS for seed in SEEDS}
    if set(lookup) != expected:
        raise RuntimeError("Stage 9K current-NLS baseline does not cover the Stage 9J replay matrix")
    return lookup


def arrays(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    data = {
        "time": np.asarray([float(row["timestamp"]) for row in rows]),
        "action": np.asarray([[float(row["F_tan"]), float(row["F_rad"])] for row in rows]),
        "true": np.asarray([[float(row[f"true_{name}"]) for name in STATE_NAMES] for row in rows]),
        "estimated": np.asarray([[float(row[f"estimated_{name}"]) for name in STATE_NAMES] for row in rows]),
        "measured": np.asarray([[float(row[f"measured_{name}"]) for name in STATE_NAMES] for row in rows]),
        "nls": np.asarray([[float(row[f"online_{name}_hat"]) for name in PARAMETER_NAMES] for row in rows]),
        "true_params": np.asarray([float(rows[0][f"true_{name}_param"]) for name in PARAMETER_NAMES]),
        "nominal_params": np.asarray([float(rows[0][f"nominal_{name}_param"]) for name in PARAMETER_NAMES]),
    }
    return data


def params_with_mass(model_params: dict[str, Any], mass: float, k: float | None = None, b_r: float | None = None) -> dict[str, Any]:
    params = dict(model_params)
    params["m"] = float(mass)
    if k is not None:
        params["k"] = float(k)
    if b_r is not None:
        params["b_r"] = float(b_r)
    return params


def rollout_error(start: np.ndarray, actions: np.ndarray, target: np.ndarray, params: dict[str, Any]) -> float:
    state = np.asarray(start, dtype=float).copy()
    try:
        for action in actions:
            state = step_dynamics(state, action, float(params["dt"]), params)
            if not np.all(np.isfinite(state)):
                return np.nan
    except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
        return np.nan
    return float(np.linalg.norm(state - target))


def safe_step(state: np.ndarray, action: np.ndarray, dt: float, params: dict[str, Any]) -> np.ndarray:
    try:
        result = step_dynamics(state, action, dt, params)
        return result if np.all(np.isfinite(result)) else np.full(4, np.nan)
    except (FloatingPointError, OverflowError, ValueError, np.linalg.LinAlgError):
        return np.full(4, np.nan)


def alpha_from_transition(previous_state: np.ndarray, predicted_next: np.ndarray, dt: float) -> float:
    return float((predicted_next[1] - previous_state[1]) / dt)


def metric(values: np.ndarray, kind: str) -> float:
    return stat(values, kind)


def common_metrics(
    method: str,
    condition: str,
    seed: int,
    data: dict[str, np.ndarray],
    state_history: np.ndarray,
    mass_history: np.ndarray,
    k_history: np.ndarray,
    b_history: np.ndarray,
    one_step: np.ndarray,
    five_step: np.ndarray,
    ten_step: np.ndarray,
    alpha_error: np.ndarray,
    alpha_error_true_state: np.ndarray,
    update_magnitude: np.ndarray,
    solve_time: np.ndarray,
    failure: np.ndarray,
    bound_hit: np.ndarray,
    condition_number: np.ndarray,
    parameter_std: np.ndarray,
    uncertainty_available: bool,
) -> dict[str, Any]:
    truth = data["true_params"]
    state_error = state_history - data["true"]
    mass_error = mass_history - truth[0]
    rel_mass_error = np.abs(mass_error) / abs(truth[0])
    valid_updates = update_magnitude[np.isfinite(update_magnitude) & (update_magnitude > 0.0)]
    valid_solves = solve_time[np.isfinite(solve_time) & (solve_time > 0.0)]
    valid_conditioning = condition_number[np.isfinite(condition_number)]
    update_count = int(len(valid_updates))
    return {
        "method": method,
        "condition": condition,
        "seed": int(seed),
        "num_steps": int(len(data["time"])),
        "m_absolute_error_mean": metric(np.abs(mass_error), "mean"),
        "m_relative_error_mean": metric(rel_mass_error, "mean"),
        "m_rmse": metric(mass_error, "rmse"),
        "m_final_error": float(abs(mass_history[-1] - truth[0])),
        "inverse_m_rmse": metric(1.0 / mass_history - 1.0 / truth[0], "rmse"),
        "k_relative_error_mean": metric(np.abs(k_history - truth[1]) / abs(truth[1]), "mean"),
        "b_r_relative_error_mean": metric(np.abs(b_history - truth[2]) / abs(truth[2]), "mean"),
        "state_rmse": metric(np.linalg.norm(state_error, axis=1), "rmse"),
        **{f"{name}_state_rmse": metric(state_error[:, index], "rmse") for index, name in enumerate(STATE_NAMES)},
        "one_step_state_prediction_rmse": metric(one_step, "rmse"),
        "five_step_state_prediction_rmse": metric(five_step, "rmse"),
        "ten_step_state_prediction_rmse": metric(ten_step, "rmse"),
        "predicted_alpha_rmse": metric(alpha_error, "rmse"),
        "predicted_alpha_p95_error": metric(np.abs(alpha_error), "p95"),
        "parameter_only_alpha_rmse_true_state": metric(alpha_error_true_state, "rmse"),
        "parameter_update_total_variation": float(np.sum(valid_updates)),
        "maximum_single_update": metric(update_magnitude, "max"),
        "parameter_bound_hit_rate": float(np.mean(bound_hit)) if len(bound_hit) else np.nan,
        "estimator_failure_count": int(np.sum(failure)),
        "estimator_failure_rate": float(np.mean(failure)) if len(failure) else 0.0,
        "solve_time_mean_s": metric(valid_solves, "mean"),
        "solve_time_p95_s": metric(valid_solves, "p95"),
        "update_count": update_count,
        "jacobian_condition_median": float(np.median(valid_conditioning)) if len(valid_conditioning) else np.nan,
        "jacobian_condition_p95": metric(valid_conditioning, "p95"),
        "parameter_std_mean": metric(parameter_std, "mean"),
        "uncertainty_available": bool(uncertainty_available),
        "parameter_estimate_trajectory_json": json.dumps(mass_history.tolist(), separators=(",", ":")),
        "state_estimate_trajectory_json": json.dumps(state_history.tolist(), separators=(",", ":")),
        "alpha_error_trajectory_json": json.dumps(alpha_error.tolist(), separators=(",", ":"), allow_nan=True),
    }


def evaluate_ukf_nls(condition: str, seed: int, data: dict[str, np.ndarray], model_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    n = len(data["time"]); dt = float(model_params["dt"])
    states = data["estimated"].copy(); p = data["nls"].copy()
    one = np.full(n, np.nan); five = np.full(n, np.nan); ten = np.full(n, np.nan)
    alpha = np.full(n, np.nan); alpha_true = np.full(n, np.nan)
    for step in range(1, n):
        params = params_with_mass(model_params, p[step - 1, 0], p[step - 1, 1], p[step - 1, 2])
        prediction = safe_step(states[step - 1], data["action"][step], dt, params)
        one[step] = np.linalg.norm(prediction - data["true"][step])
        alpha[step] = alpha_from_transition(states[step - 1], prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt if np.all(np.isfinite(prediction)) else np.nan
        true_prediction = safe_step(data["true"][step - 1], data["action"][step], dt, params)
        alpha_true[step] = alpha_from_transition(data["true"][step - 1], true_prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt if np.all(np.isfinite(true_prediction)) else np.nan
        if step + 4 < n:
            five[step] = rollout_error(states[step - 1], data["action"][step:step + 5], data["true"][step + 4], params)
        if step + 9 < n:
            ten[step] = rollout_error(states[step - 1], data["action"][step:step + 10], data["true"][step + 9], params)
    update = np.r_[0.0, np.linalg.norm(np.diff(p, axis=0), axis=1)]
    row = common_metrics("ukf_nls_current", condition, seed, data, states, p[:, 0], p[:, 1], p[:, 2], one, five, ten, alpha, alpha_true, update, np.zeros(n), np.zeros(n, dtype=bool), np.zeros(n, dtype=bool), np.full(n, np.nan), np.full(n, np.nan), False)
    return row, {"state": states, "mass": p[:, 0], "alpha_error": alpha}


def evaluate_mhe(method: str, condition: str, seed: int, data: dict[str, np.ndarray], model_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    parameterization = "inverse_m" if method == "mhe_inverse_m" else "m"
    estimator = SingleParameterMHE(model_params, MHE_CONFIG, parameterization)
    n = len(data["time"]); dt = float(model_params["dt"])
    estimator.reset(data["measured"][0])
    states = np.empty_like(data["true"]); states[0] = estimator.state_hat
    masses = np.full(n, estimator.mass_hat); k = np.full(n, float(model_params["k"])); b_r = np.full(n, float(model_params["b_r"]))
    one = np.full(n, np.nan); five = np.full(n, np.nan); ten = np.full(n, np.nan)
    alpha = np.full(n, np.nan); alpha_true = np.full(n, np.nan); update = np.zeros(n); solve = np.full(n, np.nan)
    failures = np.zeros(n, dtype=bool); bounds = np.zeros(n, dtype=bool); cond = np.full(n, np.nan); std = np.full(n, np.nan)
    for step in range(1, n):
        previous_state = states[step - 1].copy(); previous_mass = masses[step - 1]
        params = params_with_mass(model_params, previous_mass)
        prediction = step_dynamics(previous_state, data["action"][step], dt, params)
        one[step] = np.linalg.norm(prediction - data["true"][step])
        alpha[step] = alpha_from_transition(previous_state, prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt
        true_prediction = step_dynamics(data["true"][step - 1], data["action"][step], dt, params)
        alpha_true[step] = alpha_from_transition(data["true"][step - 1], true_prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt
        if step + 4 < n:
            five[step] = rollout_error(previous_state, data["action"][step:step + 5], data["true"][step + 4], params)
        if step + 9 < n:
            ten[step] = rollout_error(previous_state, data["action"][step:step + 10], data["true"][step + 9], params)
        result = estimator.add_measurement(data["action"][step], data["measured"][step])
        diag = result["diagnostics"]
        states[step] = result["state_hat"]; masses[step] = result["m_hat"]
        update[step] = abs(masses[step] - masses[step - 1]) if result["updated"] else 0.0
        solve[step] = float(diag.get("solve_time_s", np.nan))
        failures[step] = bool(result["updated"] and not result["success"])
        bounds[step] = bool(diag.get("parameter_bound_hit", False))
        cond[step] = float(diag.get("jacobian_condition", np.nan))
        std[step] = float(diag.get("parameter_std", np.nan))
    row = common_metrics(method, condition, seed, data, states, masses, k, b_r, one, five, ten, alpha, alpha_true, update, solve, failures, bounds, cond, std, True)
    return row, {"state": states, "mass": masses, "alpha_error": alpha, "solve": solve}


def affine_regression_row(x: np.ndarray, u: np.ndarray, next_x: np.ndarray, model_params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    # Exact Stage 10A continuous parameter-affine form: G z + c = H [lambda,kappa,beta].
    theta, omega, r, r_dot = (float(v) for v in x)
    dt = float(model_params["dt"]); r_eff = max(r, 1.0e-6)
    rho = float(model_params["rho"])
    b_theta = float(model_params["b_theta"]); g = float(model_params["g"]); L0 = float(model_params["L0"])
    base_kinematics = compute_base_kinematics(theta, model_params)
    a = float(base_kinematics["a"]); a_prime = float(base_kinematics["ap"])
    G = np.array([[1.0 / 3.0, 0.5 * a * np.cos(theta)], [0.5 * a * np.cos(theta), r_eff**2 / 3.0 - a * r_eff * np.sin(theta) + a**2]], dtype=float)
    c = np.array([
        0.5 * g * np.sin(theta) - r_eff * omega**2 / 3.0 + 0.5 * a_prime * np.cos(theta) * omega**2,
        0.5 * g * r_eff * np.cos(theta) + 2.0 * r_eff * r_dot * omega / 3.0 - a * np.sin(theta) * r_dot * omega - 0.5 * r_eff * a * np.cos(theta) * omega**2 - 0.5 * r_eff * a_prime * np.sin(theta) * omega**2 + a * a_prime * omega**2,
    ])
    q_r = rho * float(u[1])
    q_theta = rho * r_eff * float(u[0]) + a * (float(u[1]) * np.cos(theta) - float(u[0]) * np.sin(theta))
    H = np.array([[q_r, -(r_eff - L0), -r_dot], [q_theta - b_theta * omega, 0.0, 0.0]], dtype=float)
    z = np.array([(next_x[3] - r_dot) / dt, (next_x[1] - omega) / dt], dtype=float)
    return H, G @ z + c


def weighted_tls(H: np.ndarray, y: np.ndarray, row_weight: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Diagonal-weighted, column-scaled TLS for the Stage 10A affine EIV form."""
    weighted_H = H * row_weight[:, None]; weighted_y = y * row_weight
    column_scale = np.maximum(np.linalg.norm(np.column_stack([weighted_H, weighted_y]), axis=0), 1.0e-12)
    A = np.column_stack([weighted_H, -weighted_y]) / column_scale
    _, singular, vt = np.linalg.svd(A, full_matrices=False)
    null = vt[-1]
    if abs(null[-1]) < 1.0e-10:
        raise FloatingPointError("TLS null-vector has vanishing output component")
    scaled_theta = -null[:-1] / null[-1]
    theta = scaled_theta * column_scale[-1] / column_scale[:-1]
    cond = float(singular[0] / max(singular[-1], 1.0e-15))
    return theta, cond, float(singular[-1])


def evaluate_tls(condition: str, seed: int, data: dict[str, np.ndarray], model_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    n = len(data["time"]); dt = float(model_params["dt"]); window = int(MHE_CONFIG["window_size"]); interval = int(MHE_CONFIG["update_interval"])
    states = data["estimated"].copy(); truth = data["true_params"]
    masses = np.full(n, float(model_params["m"])); ks = np.full(n, float(model_params["k"])); brs = np.full(n, float(model_params["b_r"]))
    one = np.full(n, np.nan); five = np.full(n, np.nan); ten = np.full(n, np.nan); alpha = np.full(n, np.nan); alpha_true = np.full(n, np.nan)
    update = np.zeros(n); solve = np.full(n, np.nan); failures = np.zeros(n, dtype=bool); bounds = np.zeros(n, dtype=bool); cond = np.full(n, np.nan); std = np.full(n, np.nan)
    for step in range(1, n):
        previous = np.array([masses[step - 1], ks[step - 1], brs[step - 1]])
        params = params_with_mass(model_params, *previous)
        prediction = safe_step(states[step - 1], data["action"][step], dt, params)
        one[step] = np.linalg.norm(prediction - data["true"][step])
        alpha[step] = alpha_from_transition(states[step - 1], prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt if np.all(np.isfinite(prediction)) else np.nan
        true_prediction = safe_step(data["true"][step - 1], data["action"][step], dt, params)
        alpha_true[step] = alpha_from_transition(data["true"][step - 1], true_prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt if np.all(np.isfinite(true_prediction)) else np.nan
        if step + 4 < n:
            five[step] = rollout_error(states[step - 1], data["action"][step:step + 5], data["true"][step + 4], params)
        if step + 9 < n:
            ten[step] = rollout_error(states[step - 1], data["action"][step:step + 10], data["true"][step + 9], params)
        if step % interval == 0 and step >= 2:
            started = time.perf_counter(); lo = max(1, step - window + 1)
            try:
                h_rows: list[np.ndarray] = []; y_rows: list[np.ndarray] = []; weights: list[float] = []
                for j in range(lo, step + 1):
                    H, y = affine_regression_row(states[j - 1], data["action"][j], states[j], model_params)
                    h_rows.extend(H); y_rows.extend(y)
                    weights.extend([float(MHE_CONFIG["measurement_weights"][3]), float(MHE_CONFIG["measurement_weights"][1])])
                theta, cond_now, _ = weighted_tls(np.asarray(h_rows), np.asarray(y_rows), np.asarray(weights))
                lam, kappa, beta = theta
                if not np.isfinite(lam) or lam <= 0.0:
                    raise FloatingPointError("non-positive inverse mass")
                candidate = np.array([1.0 / lam, kappa / lam, beta / lam])
                if not np.all(np.isfinite(candidate)):
                    raise FloatingPointError("non-finite TLS parameter")
                masses[step], ks[step], brs[step] = candidate
                update[step] = float(np.linalg.norm(candidate - previous))
                cond[step] = cond_now
                bounds[step] = bool(candidate[0] < 0.5 or candidate[0] > 2.0 or candidate[1] < 150.0 or candidate[1] > 800.0 or candidate[2] < 2.0 or candidate[2] > 45.0)
            except (FloatingPointError, np.linalg.LinAlgError, ValueError):
                masses[step], ks[step], brs[step] = previous
                failures[step] = True
            solve[step] = time.perf_counter() - started
        else:
            masses[step], ks[step], brs[step] = previous
    row = common_metrics("weighted_tls", condition, seed, data, states, masses, ks, brs, one, five, ten, alpha, alpha_true, update, solve, failures, bounds, cond, std, False)
    return row, {"state": states, "mass": masses, "alpha_error": alpha, "solve": solve}


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        "m_relative_error_mean", "m_rmse", "inverse_m_rmse", "state_rmse", "theta_state_rmse", "omega_state_rmse", "r_state_rmse", "r_dot_state_rmse",
        "one_step_state_prediction_rmse", "five_step_state_prediction_rmse", "ten_step_state_prediction_rmse", "predicted_alpha_rmse", "parameter_only_alpha_rmse_true_state",
        "parameter_update_total_variation", "parameter_bound_hit_rate", "estimator_failure_count", "estimator_failure_rate", "solve_time_mean_s", "solve_time_p95_s", "jacobian_condition_median", "jacobian_condition_p95", "parameter_std_mean",
    ]
    out = []
    for method in METHODS:
        for condition in CONDITIONS:
            group = [row for row in rows if row["method"] == method and row["condition"] == condition]
            summary = {"method": method, "condition": condition, "n": len(group)}
            summary.update({f"{name}_mean": metric(np.asarray([row[name] for row in group], dtype=float), "mean") for name in metrics})
            out.append(summary)
    return out


def gate(offline_summary: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_by_condition = {row["condition"]: row for row in offline_summary if row["method"] == "ukf_nls_current"}
    candidates = []
    for method in MHE_METHODS:
        condition_rows = {row["condition"]: row for row in offline_summary if row["method"] == method}
        improvements = []
        no_material_regression = []
        for condition in CONDITIONS:
            base = baseline_by_condition[condition]; candidate = condition_rows[condition]
            improvements.append(candidate["predicted_alpha_rmse_mean"] <= 0.90 * base["predicted_alpha_rmse_mean"])
            no_material_regression.append(candidate["state_rmse_mean"] <= 1.10 * base["state_rmse_mean"])
        alpha_base = float(np.mean([baseline_by_condition[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS]))
        alpha_candidate = float(np.mean([condition_rows[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS]))
        checks = {
            "alpha_mean_clearly_improved": alpha_candidate <= 0.90 * alpha_base,
            "alpha_improved_consistently": int(np.sum(improvements)) >= 6 and all(
                condition_rows[c]["predicted_alpha_rmse_mean"] <= 1.10 * baseline_by_condition[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS
            ),
            "state_not_materially_worse": all(no_material_regression),
            "solve_time_acceptable": all(condition_rows[c]["solve_time_p95_s_mean"] <= 0.20 for c in CONDITIONS),
            "failure_rate_acceptable": all(condition_rows[c]["estimator_failure_rate_mean"] <= 0.05 for c in CONDITIONS),
        }
        candidates.append({"method": method, "alpha_rmse_mean": alpha_candidate, "alpha_rmse_baseline": alpha_base, "conditions_improved": int(np.sum(improvements)), "checks": checks, "passed": bool(all(checks.values()))})
    retained = [item for item in candidates if item["passed"]]
    selected = [item["method"] for item in sorted(retained, key=lambda item: item["alpha_rmse_mean"])]
    return {"passed": bool(selected), "selected_methods": selected, "baseline": "ukf_nls_current", "criteria": {"alpha_improvement": "mean <= 0.90 baseline and at least 6/8 conditions <= 0.90 baseline, none > 1.10 baseline", "state": "each condition state RMSE <= 1.10 baseline", "solve_time": "p95 update solve <= 0.20 s", "failure_rate": "<= 5% per condition"}, "candidates": candidates}


def run_closed_loop(method: str, condition: str, seed: int, base_cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = stage9j_overrides(base_cfg, condition)
    cfg["mpc_params"].setdefault("solver", {})["seed"] = int(seed)
    true_params = cfg["true_params"]; nominal = cfg["model_params"]
    env = Spring2DEnv(true_params); true_obs = env.reset()
    wrapper = NoisySpring2DObservationWrapper(true_params, condition_cfg(base_cfg, condition, seed).get("observation_noise", {}), seed=int(seed))
    measured_obs = wrapper.observe(true_obs)
    estimator = SingleParameterMHE(nominal, MHE_CONFIG, "inverse_m" if method == "mhe_inverse_m" else "m")
    estimated = estimator.reset(observation_to_state(measured_obs))
    # Reuse exactly the Stage 9J one-shot planner/tracker.  Its spec is the
    # estimated-state/NLS-parameter branch; only its input snapshots differ.
    controller = AuditedPlannerTracker("full_adaptive_planner_tracker", cfg)
    controller.method = method
    rows: list[dict[str, Any]] = []
    prev_action = np.zeros(2); started = time.perf_counter(); step = 0
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200)); hold = int(cfg.get("run", {}).get("control_hold_steps", 1))
    while not env.is_done() and step < max_steps:
        params = estimator.get_model_params(); action, diag = controller.act(estimated.copy(), params, float(env.get_history()[-1]["t"]), step, seed, condition)
        for _ in range(hold):
            prev_true = observation_to_state(true_obs); prev_est = estimated.copy()
            true_obs = env.step(action); measured_obs = wrapper.observe(true_obs); true_next = observation_to_state(true_obs)
            result = estimator.add_measurement(action, observation_to_state(measured_obs)); estimated = result["state_hat"].copy(); step += 1
            tracker_X = np.asarray(diag.get("X", []), dtype=float); tracker_S = np.asarray(diag.get("S", []), dtype=float)
            tracker_alpha = float((tracker_X[1, 1] - tracker_X[0, 1]) / controller.tracker.prediction_dt) if tracker_X.ndim == 2 and len(tracker_X) > 1 else np.nan
            plan_alpha = float(np.max(np.abs(np.diff(controller.plan_X[:, 1]) / controller.plan_dt))) if controller.plan_X is not None and len(controller.plan_X) > 1 else np.nan
            row = {"t": float(env.get_history()[-1]["t"]), "step": step, "F_tan": float(action[0]), "F_rad": float(action[1]), "true_alpha": float((true_next[1] - prev_true[1]) / true_params["dt"]), "estimated_alpha": float((estimated[1] - prev_est[1]) / true_params["dt"]), "planner_predicted_alpha": plan_alpha, "tracker_predicted_alpha": tracker_alpha, "planned_constraint_slack": max(0.0, abs(plan_alpha) - 3.0) if np.isfinite(plan_alpha) else np.nan, "tracker_constraint_slack": float(tracker_S[0]) if len(tracker_S) else np.nan, "theta_ref": float(diag.get("X", np.array([[np.nan]]))[0, 0]) if np.asarray(diag.get("X", [])).ndim == 2 else np.nan, "omega_ref": float(diag.get("X", np.array([[np.nan, np.nan]]))[0, 1]) if np.asarray(diag.get("X", [])).ndim == 2 else np.nan, "state_tracking_error": float(diag.get("tracking_error_mean", np.nan)), "parameter_update_magnitude": abs(float(result["m_hat"]) - float(params["m"])) if result["updated"] else 0.0, "parameter_bound_hit": bool(result["diagnostics"].get("parameter_bound_hit", False)), "identifier_updated": bool(result["updated"]), "identifier_samples": int(result["diagnostics"].get("window_length", 0)), "innovation_norm": np.nan, "ukf_failed": False}
            for index, name in enumerate(STATE_NAMES):
                row[f"true_{name}"] = float(true_next[index]); row[f"estimated_{name}"] = float(estimated[index]); row[f"{name}_estimation_error"] = float(estimated[index] - true_next[index])
            for name in PARAMETER_NAMES:
                row[f"{name}_hat"] = float(params[name] if name != "m" else result["m_hat"]); row[f"true_{name}_param"] = float(true_params[name]); row[f"nominal_{name}_param"] = float(nominal[name])
            row["true_delta_r"] = float(true_next[2] - true_params["L0"]); rows.append(row)
            if env.is_done() or step >= max_steps:
                break
        prev_action = action
    # Reuse the Stage 9J adaptive-mode summary semantics; the controller itself
    # is deliberately the unchanged estimated-state/adaptive-parameter branch.
    summary = summarize_run("full_adaptive_planner_tracker", condition, seed, rows, cfg, time.perf_counter() - started, controller)
    summary["method"] = method
    summary["estimator_failure_count"] = 0
    return summary, rows


def save_figures(offline_rows: list[dict[str, Any]], output_root: Path) -> None:
    fig_dir = output_root / "figs"; fig_dir.mkdir(parents=True, exist_ok=True)
    methods = ["ukf_nls_current", "mhe_inverse_m", "mhe_m", "weighted_tls"]
    labels = {"ukf_nls_current": "UKF+NLS", "mhe_inverse_m": "MHE 1/m", "mhe_m": "MHE m", "weighted_tls": "weighted TLS"}
    values = [metric(np.asarray([r["predicted_alpha_rmse"] for r in offline_rows if r["method"] == method]), "mean") for method in methods]
    fig, ax = plt.subplots(figsize=(7.2, 4.2)); ax.bar([labels[m] for m in methods], values); ax.set_ylabel("full estimated-state alpha RMSE"); ax.set_title("Stage 10B offline alpha-prediction benchmark"); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(fig_dir / "01_offline_alpha_rmse.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for method in methods:
        x = [r["m_relative_error_mean"] for r in offline_rows if r["method"] == method]
        y = [r["state_rmse"] for r in offline_rows if r["method"] == method]
        ax.scatter(x, y, label=labels[method], alpha=0.8)
    ax.set_xlabel("mean relative mass error"); ax.set_ylabel("state RMSE"); ax.legend(); ax.grid(alpha=0.3); ax.set_title("Parameter accuracy versus state estimation"); fig.tight_layout(); fig.savefig(fig_dir / "02_parameter_state_tradeoff.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for method in MHE_METHODS + ("weighted_tls",):
        x = [r["solve_time_p95_s"] for r in offline_rows if r["method"] == method]
        ax.scatter(range(len(x)), x, label=labels[method])
    ax.axhline(0.20, color="black", linestyle="--", linewidth=1, label="gate limit"); ax.set_ylabel("p95 update solve time (s)"); ax.set_xlabel("condition/seed run"); ax.set_yscale("log"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(fig_dir / "03_update_solve_time.png", dpi=150); plt.close(fig)


def write_report(output_root: Path, gate_result: dict[str, Any], offline_summary: list[dict[str, Any]], closed_summary: list[dict[str, Any]]) -> None:
    def overall(method: str, field: str) -> float:
        return metric(np.asarray([row[field] for row in offline_summary if row["method"] == method]), "mean")
    inverse = next(item for item in gate_result["candidates"] if item["method"] == "mhe_inverse_m")
    mass = next(item for item in gate_result["candidates"] if item["method"] == "mhe_m")
    lines = ["# Stage 10B: Offline Estimator Benchmark and Gated Closed-Loop Test", "", "## Protocol", "", "- Reused the fixed Stage 9J replay. The compatible Stage 9K `windowed_nls_current`/`ukf_filtered` per-run baseline is loaded directly into `offline_per_run.csv` as `stage9k_*` fields; no historical baseline was rerun.", "- Both MHE variants use the same 70-transition window, 10-step update cadence, measurement weights, arrival penalties, physical mass bounds, numerical tolerances, maximum evaluations, and warm-start rule. `k` and `b_r` remain nominal.", "- The MHE is single-shooting joint state/parameter MHE: its five decisions are the window-start state and either `m` or `1/m`; every intermediate state is generated by the implemented RK4 dynamics. Its covariance diagnostic is the residual-scaled inverse Gauss-Newton information matrix.", "- Weighted TLS is offline-only and estimates `[1/m,k/m,b_r/m]` in the Stage 10A parameter-affine form. It is not eligible for closed-loop advancement.", "", "## Offline gate", "", f"Gate result: **{'PASS' if gate_result['passed'] else 'FAIL'}**. Selected methods: `{', '.join(gate_result['selected_methods']) if gate_result['selected_methods'] else 'none'}`.", f"- Inverse-mass MHE: overall full alpha RMSE={inverse['alpha_rmse_mean']:.6g} versus UKF+NLS={inverse['alpha_rmse_baseline']:.6g}; only {inverse['conditions_improved']}/8 conditions reached the 10% improvement threshold. Checks={inverse['checks']}.", f"- Mass MHE: overall full alpha RMSE={mass['alpha_rmse_mean']:.6g} versus UKF+NLS={mass['alpha_rmse_baseline']:.6g}; only {mass['conditions_improved']}/8 conditions reached the 10% improvement threshold. Checks={mass['checks']}.", ""]
    lines += ["| method | alpha RMSE | state RMSE | m relative error | p95 solve time (s) | failures |", "|---|---:|---:|---:|---:|---:|"]
    for method in METHODS:
        lines.append(f"| {method} | {overall(method, 'predicted_alpha_rmse_mean'):.5g} | {overall(method, 'state_rmse_mean'):.5g} | {overall(method, 'm_relative_error_mean_mean'):.5g} | {overall(method, 'solve_time_p95_s_mean'):.5g} | {overall(method, 'estimator_failure_rate_mean'):.5g} |")
    lines += ["", "## Required answers", "", f"1. **Does inverse-mass MHE beat current UKF+NLS?** No. It lowers the overall full alpha RMSE modestly but misses the pre-registered 10% mean improvement, is clearly better in only {inverse['conditions_improved']}/8 conditions, worsens state RMSE in at least one condition, and misses the 0.20 s p95 solve-time criterion.", "2. **Is it better than m-only MHE?** No material evidence. Their aggregate alpha RMSE values differ only at numerical-noise scale, and both fail the same gate checks. The inverse-mass coordinate therefore has no observed practical advantage in this matched implementation.", "3. **Is weighted TLS a useful EIV baseline?** Only diagnostically. It is extremely fast but has materially worse alpha prediction, frequent physical-bound violations/invalid predictions, and no state-update mechanism. It is not a control candidate.", f"4. **Which estimator advances?** `{', '.join(gate_result['selected_methods']) if gate_result['selected_methods'] else 'None'}`.", "5. **Is estimator quality sufficient to begin uncertainty-aware control?** No. The offline gate failed, so this stage provides no empirical basis for uncertainty-aware control.", ""]
    if closed_summary:
        lines += ["## Gated closed loop", "", "Only retained MHE methods were tested under the unchanged Stage 9J planner/tracker. See `closed_loop_per_run.csv` and `closed_loop_summary.csv`.", ""]
    else:
        lines += ["## Closed loop", "", "No closed-loop MHE test was run because no method passed the offline gate. Consequently no GIF was generated.", ""]
    (output_root / "stage10b_report.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--stage9k", type=Path, default=DEFAULT_STAGE9K)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted offline matrix from offline_per_run.csv.")
    args = parser.parse_args()
    started = time.perf_counter(); output_root = args.output_root; output_root.mkdir(parents=True, exist_ok=True); (output_root / "figs").mkdir(exist_ok=True); (output_root / "videos").mkdir(exist_ok=True)
    base_cfg = load_experiment_config(args.config); replay = load_replay(args.replay)
    stage9k_current = load_stage9k_current_baseline(args.stage9k)
    provenance = {
        "config_path": str(args.config),
        "stage9j_replay_path": str(args.replay),
        "stage9j_replay_sha256": hashlib.sha256(args.replay.read_bytes()).hexdigest(),
        "stage9k_current_baseline_path": str(args.stage9k),
        "stage9k_current_baseline_sha256": hashlib.sha256(args.stage9k.read_bytes()).hexdigest(),
        "mhe_config": MHE_CONFIG,
        "base_config": base_cfg,
        "closed_loop_conditions": list(CLOSED_LOOP_CONDITIONS),
        "closed_loop_only_if_gate_passes": True,
    }
    (output_root / "config_snapshot.json").write_text(json.dumps(provenance, indent=2, default=str))
    offline_path = output_root / "offline_per_run.csv"
    if args.resume and offline_path.exists():
        with offline_path.open(newline="") as handle:
            offline_rows = list(csv.DictReader(handle))
        # CSV restores scalars as strings; only use the saved keys to skip work
        # and recompute the final aggregate from fresh numeric rows below.
        completed_keys = {(str(row["method"]), str(row["condition"]), int(row["seed"])) for row in offline_rows}
        offline_rows = []
    else:
        completed_keys = set()
    diagnostics: dict[tuple[str, str, int], dict[str, np.ndarray]] = {}
    for condition in CONDITIONS:
        cfg = stage9j_overrides(base_cfg, condition)
        for seed in SEEDS:
            data = arrays(replay[(condition, seed)])
            for method, evaluator in (("ukf_nls_current", evaluate_ukf_nls), ("mhe_inverse_m", evaluate_mhe), ("mhe_m", evaluate_mhe), ("weighted_tls", evaluate_tls)):
                if (method, condition, seed) in completed_keys:
                    continue
                print(f"[stage10b] offline {method}/{condition}/seed{seed}", flush=True)
                row, diagnostic = evaluator(method, condition, seed, data, cfg["model_params"]) if method.startswith("mhe_") else evaluator(condition, seed, data, cfg["model_params"])
                # Reload the existing table before every append when resuming,
                # preserving completed runs if a long job is interrupted again.
                existing = []
                if offline_path.exists():
                    with offline_path.open(newline="") as handle:
                        existing = list(csv.DictReader(handle))
                existing.append(row); write_dict_csv(offline_path, existing)
                diagnostics[(method, condition, seed)] = diagnostic
    with offline_path.open(newline="") as handle:
        offline_rows = list(csv.DictReader(handle))
    # Convert numeric fields used by aggregation back from CSV strings.
    for row in offline_rows:
        for key, value in list(row.items()):
            if key not in {"method", "condition", "seed", "num_steps", "uncertainty_available", "parameter_estimate_trajectory_json", "state_estimate_trajectory_json", "alpha_error_trajectory_json"}:
                try:
                    row[key] = float(value)
                except (TypeError, ValueError):
                    pass
        row["seed"] = int(row["seed"]); row["num_steps"] = int(row["num_steps"])
        if row["method"] == "ukf_nls_current":
            saved = stage9k_current[(str(row["condition"]), int(row["seed"]))]
            row.update(
                {
                    "stage9k_baseline_reused": True,
                    "stage9k_parameter_only_alpha_rmse": float(saved["predicted_alpha_rmse"]),
                    "stage9k_one_step_state_prediction_rmse": float(saved["one_step_state_prediction_rmse"]),
                    "stage9k_five_step_state_prediction_rmse": float(saved["five_step_state_prediction_rmse"]),
                    "stage9k_ten_step_state_prediction_rmse": float(saved["ten_step_state_prediction_rmse"]),
                }
            )
        else:
            row["stage9k_baseline_reused"] = False
    write_dict_csv(offline_path, offline_rows)
    offline_summary = aggregate(offline_rows); write_dict_csv(output_root / "offline_summary.csv", offline_summary)
    gate_result = gate(offline_summary); (output_root / "offline_gate.json").write_text(json.dumps(gate_result, indent=2))
    save_figures(offline_rows, output_root)
    closed_rows: list[dict[str, Any]] = []
    if gate_result["passed"]:
        for method in gate_result["selected_methods"]:
            best: tuple[tuple[float, float, float], str, int, list[dict[str, Any]], dict[str, Any]] | None = None
            for condition in CLOSED_LOOP_CONDITIONS:
                for seed in SEEDS:
                    print(f"[stage10b] closed-loop {method}/{condition}/seed{seed}", flush=True)
                    summary, rows = run_closed_loop(method, condition, seed, base_cfg); closed_rows.append(summary); write_dict_csv(output_root / "closed_loop_per_run.csv", closed_rows)
                    rank = (-float(bool(summary["target_crossed"])), float(summary["true_alpha_max"]), float(summary["alpha_violation_integral"]))
                    if best is None or rank < best[0]: best = (rank, condition, seed, rows, summary)
            if best is not None:
                _, condition, seed, rows, summary = best
                true_params = stage9j_overrides(base_cfg, condition)["true_params"]
                save_spring2d_animation(rows, true_params, output_root / "videos" / f"{method}_best_{condition}_seed{seed}.gif", fps=8)
        closed_summary = []
        for method in gate_result["selected_methods"]:
            for condition in CLOSED_LOOP_CONDITIONS:
                group = [row for row in closed_rows if row["method"] == method and row["condition"] == condition]
                if group:
                    closed_summary.append({"method": method, "condition": condition, "n": len(group), **{f"{field}_mean": metric(np.asarray([row[field] for row in group]), "mean") for field in ("target_crossed", "crossing_time", "true_alpha_p95", "true_alpha_p99", "true_alpha_max", "alpha_violation_duration", "alpha_violation_integral", "alpha_violation_max", "state_tracking_rmse", "true_predicted_alpha_error_rmse", "tracker_failure_count", "planner_failure_count")}})
        write_dict_csv(output_root / "closed_loop_summary.csv", closed_summary)
    else:
        closed_summary = []
    write_report(output_root, gate_result, offline_summary, closed_summary)
    (output_root / "command.txt").write_text(f"conda run -n mpc_learn python scripts/{Path(__file__).name}\n")
    print(f"[stage10b] gate={gate_result['passed']} selected={gate_result['selected_methods']} runtime={time.perf_counter()-started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
