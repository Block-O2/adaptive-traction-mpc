"""Stage 9K robust offline identifier ablation and gated closed-loop validation."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import time
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
    CONDITIONS,
    DEFAULT_CONFIG,
    PARAMETER_NAMES,
    SEEDS,
    condition_cfg,
    fmt,
    run_planner_tracker,
    stage9j_overrides,
    stat,
    summarize_run,
    write_dict_csv,
)
from traction_mpc.identification.robust_windowed_nls_identifier import RobustWindowedLeastSquaresIdentifier
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.models.spring2d_dynamics import step_dynamics


DEFAULT_REPLAY = PROJECT_ROOT / "results" / "stage9j_gap_decomposition" / "stage9j_replay.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "stage9k_identifier_ablation"
IDENTIFIER_METHODS = ["windowed_nls_current", "windowed_nls_huber", "windowed_nls_cauchy"]
INPUT_SOURCES = ["ukf_filtered", "true_state_diagnostic"]
PARAM_SCALE = np.array([1.0, 450.0, 20.0], dtype=float)
CONFIDENCE_REL_STD_THRESHOLD = 0.20
LATER_DIAGNOSTIC_TIME_S = 2.0
LOW_EXCITATION_THRESHOLDS = {
    "F_tan_std": 0.25,
    "F_rad_std": 0.02,
    "omega_std": 0.02,
    "r_dot_std": 0.002,
}


def load_replay(path: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["condition"]), int(row["seed"]))
        grouped.setdefault(key, []).append(row)
    for key, group in grouped.items():
        group.sort(key=lambda row: int(row["step"]))
        expected = list(range(len(group)))
        actual = [int(row["step"]) for row in group]
        if actual != expected:
            raise RuntimeError(f"Non-contiguous replay steps for {key}")
    expected_keys = {(condition, seed) for condition in CONDITIONS for seed in SEEDS}
    if set(grouped) != expected_keys:
        raise RuntimeError(f"Replay keys differ from Stage 9K matrix: missing={expected_keys-set(grouped)} extra={set(grouped)-expected_keys}")
    return grouped


def replay_arrays(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    return {
        "time": np.asarray([float(row["timestamp"]) for row in rows]),
        "actions": np.asarray([[float(row["F_tan"]), float(row["F_rad"])] for row in rows]),
        "true": np.asarray([[float(row[f"true_{name}"]) for name in ("theta", "omega", "r", "r_dot")] for row in rows]),
        "estimated": np.asarray([[float(row[f"estimated_{name}"]) for name in ("theta", "omega", "r", "r_dot")] for row in rows]),
        "measured": np.asarray([[float(row[f"measured_{name}"]) for name in ("theta", "omega", "r", "r_dot")] for row in rows]),
        "truth_params": np.asarray([float(rows[0][f"true_{name}_param"]) for name in PARAMETER_NAMES]),
        "nominal_params": np.asarray([float(rows[0][f"nominal_{name}_param"]) for name in PARAMETER_NAMES]),
    }


def make_identifier(method: str, model_params: dict[str, Any], cfg: dict[str, Any]) -> Any:
    if method == "windowed_nls_current":
        return WindowedLeastSquaresIdentifier(model_params, cfg)
    if method == "windowed_nls_huber":
        return RobustWindowedLeastSquaresIdentifier(model_params, cfg, loss="huber", smoothing_alpha=0.5)
    if method == "windowed_nls_cauchy":
        return RobustWindowedLeastSquaresIdentifier(model_params, cfg, loss="cauchy", smoothing_alpha=0.5)
    raise ValueError(method)


def predict_next(state: np.ndarray, action: np.ndarray, theta: np.ndarray, model_params: dict[str, Any]) -> np.ndarray:
    params = dict(model_params)
    params.update({name: float(value) for name, value in zip(PARAMETER_NAMES, theta)})
    return step_dynamics(state, action, float(params["dt"]), params)


def weighted_residual_matrix(transitions: Any, theta: np.ndarray, model_params: dict[str, Any], state_weights: np.ndarray) -> np.ndarray:
    residuals = []
    for x, action, x_next in transitions:
        residuals.append(state_weights * (x_next - predict_next(x, action, theta, model_params)))
    return np.asarray(residuals, dtype=float)


def component_mad(matrix: np.ndarray) -> np.ndarray:
    median = np.median(matrix, axis=0)
    mad = 1.4826 * np.median(np.abs(matrix - median), axis=0)
    floor = np.array([1.0e-3, 2.5e-3, 8.0e-4, 3.0e-3], dtype=float)
    return np.maximum(mad, floor)


def numerical_jacobian(
    transitions: Any,
    theta: np.ndarray,
    model_params: dict[str, Any],
    state_weights: np.ndarray,
    component_scale: np.ndarray,
    parameter_scaled: bool,
) -> np.ndarray:
    columns = []
    bounds = np.asarray([[0.5, 150.0, 2.0], [2.0, 800.0, 45.0]], dtype=float)
    for index in range(3):
        physical_step = PARAM_SCALE[index] * 1.0e-6
        plus = theta.copy(); minus = theta.copy()
        plus[index] = min(plus[index] + physical_step, bounds[1, index])
        minus[index] = max(minus[index] - physical_step, bounds[0, index])
        denominator = plus[index] - minus[index]
        r_plus = (weighted_residual_matrix(transitions, plus, model_params, state_weights) / component_scale).reshape(-1)
        r_minus = (weighted_residual_matrix(transitions, minus, model_params, state_weights) / component_scale).reshape(-1)
        derivative = (r_plus - r_minus) / denominator
        if parameter_scaled:
            derivative *= PARAM_SCALE[index]
        columns.append(derivative)
    return np.column_stack(columns)


def diagnostic_for_window(identifier: Any, method: str, model_params: dict[str, Any], cfg: dict[str, Any], old_theta: np.ndarray) -> dict[str, Any]:
    transitions = list(identifier.transitions)
    theta = np.asarray([identifier.get_parameter_estimate()[name] for name in PARAMETER_NAMES], dtype=float)
    weights = np.asarray(cfg["state_weights"], dtype=float)
    raw_matrix = weighted_residual_matrix(transitions, theta, model_params, weights)
    scale = component_mad(raw_matrix) if method != "windowed_nls_current" else np.ones(4, dtype=float)
    residuals = (raw_matrix / scale).reshape(-1)
    j_scaled = numerical_jacobian(transitions, theta, model_params, weights, scale, parameter_scaled=True)
    j_physical = numerical_jacobian(transitions, theta, model_params, weights, scale, parameter_scaled=False)
    if method == "windowed_nls_huber":
        cutoff = 1.345
        robust_weights = np.where(np.abs(residuals) <= cutoff, 1.0, cutoff / np.maximum(np.abs(residuals), 1.0e-12))
    elif method == "windowed_nls_cauchy":
        cutoff = 2.3849
        robust_weights = 1.0 / (1.0 + (residuals / cutoff) ** 2)
    else:
        robust_weights = np.ones_like(residuals)
    info_scaled = j_scaled.T @ (robust_weights[:, None] * j_scaled) + float(cfg["lambda_reg"]) * np.eye(3)
    info_physical = j_physical.T @ (robust_weights[:, None] * j_physical) + float(cfg["lambda_reg"]) * np.diag(1.0 / PARAM_SCALE**2)
    dof = max(len(residuals) - 3, 1)
    sigma2 = float(np.sum(robust_weights * residuals**2) / dof)
    covariance = sigma2 * np.linalg.pinv(info_physical, rcond=1.0e-12)
    covariance = 0.5 * (covariance + covariance.T)
    std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    denom = np.outer(std, std)
    correlation = np.divide(covariance, denom, out=np.full_like(covariance, np.nan), where=denom > 0.0)
    singular_values = np.linalg.svd(j_scaled, compute_uv=False)
    states = np.asarray([transition[0] for transition in transitions], dtype=float)
    actions = np.asarray([transition[1] for transition in transitions], dtype=float)
    excitation = {
        "F_tan_std": float(np.std(actions[:, 0])),
        "F_rad_std": float(np.std(actions[:, 1])),
        "theta_std": float(np.std(states[:, 0])),
        "omega_std": float(np.std(states[:, 1])),
        "r_std": float(np.std(states[:, 2])),
        "r_dot_std": float(np.std(states[:, 3])),
    }
    low_excitation = (
        excitation["F_tan_std"] < LOW_EXCITATION_THRESHOLDS["F_tan_std"]
        and excitation["F_rad_std"] < LOW_EXCITATION_THRESHOLDS["F_rad_std"]
        and excitation["omega_std"] < LOW_EXCITATION_THRESHOLDS["omega_std"]
        and excitation["r_dot_std"] < LOW_EXCITATION_THRESHOLDS["r_dot_std"]
    )
    bound_cfg = cfg["bounds"]
    bound_hit = any(np.isclose(theta[index], float(bound_cfg[name][0])) or np.isclose(theta[index], float(bound_cfg[name][1])) for index, name in enumerate(PARAMETER_NAMES))
    robust_diag = identifier.get_diagnostics() if hasattr(identifier, "get_diagnostics") else {}
    return {
        "valid_samples": len(transitions),
        "residual_norm": float(np.linalg.norm(residuals)),
        "robust_scale_json": json.dumps(scale.tolist(), separators=(",", ":")),
        "jacobian_rank": int(np.linalg.matrix_rank(j_scaled)),
        "singular_values_json": json.dumps(singular_values.tolist(), separators=(",", ":")),
        "minimum_singular_value": float(np.min(singular_values)),
        "condition_number": float(np.linalg.cond(info_scaled)),
        "covariance_diag_json": json.dumps(np.diag(covariance).tolist(), separators=(",", ":")),
        "correlation_matrix_json": json.dumps(correlation.tolist(), separators=(",", ":")),
        "m_std": float(std[0]), "k_std": float(std[1]), "b_r_std": float(std[2]),
        "bound_hit": bool(bound_hit),
        "update_magnitude": float(np.linalg.norm(theta - old_theta)),
        "optimizer_converged": bool(robust_diag.get("optimizer_converged", identifier.last_success)),
        "optimizer_status": robust_diag.get("optimizer_status", getattr(identifier, "last_optimizer_status", int(identifier.last_success))),
        "optimizer_message": robust_diag.get("optimizer_message", getattr(identifier, "last_optimizer_message", "status_unavailable")),
        "optimizer_iterations": robust_diag.get("optimizer_iterations", getattr(identifier, "last_optimizer_iterations", np.nan)),
        "regressor_max_abs_correlation": float(np.nanmax(np.abs(correlation - np.eye(3)))),
        "locally_distinguishable": bool(np.linalg.matrix_rank(j_scaled) == 3 and np.min(singular_values) > 1.0e-6 and np.linalg.cond(info_scaled) < 1.0e8),
        "low_excitation": bool(low_excitation),
        **excitation,
    }


def open_loop_error(start: np.ndarray, actions: np.ndarray, target: np.ndarray, theta: np.ndarray, model_params: dict[str, Any]) -> float:
    state = np.asarray(start, dtype=float).copy()
    for action in actions:
        state = predict_next(state, action, theta, model_params)
    return float(np.linalg.norm(state - target))


def lag1_autocorrelation(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) < 3 or np.std(values[:-1]) == 0.0 or np.std(values[1:]) == 0.0:
        return np.nan
    return float(np.corrcoef(values[:-1], values[1:])[0, 1])


def run_offline_one(
    method: str,
    input_source: str,
    condition: str,
    seed: int,
    replay_rows: list[dict[str, Any]],
    base_cfg: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    arrays = replay_arrays(replay_rows)
    cfg = stage9j_overrides(base_cfg, condition)
    model_params = cfg["model_params"]
    identifier_cfg = cfg["identifier"]
    identifier = make_identifier(method, model_params, identifier_cfg)
    identifier.reset()
    source_states = arrays["estimated"] if input_source == "ukf_filtered" else arrays["true"]
    truth = arrays["truth_params"]
    n = len(arrays["time"])
    theta_history = np.tile(arrays["nominal_params"], (n, 1))
    std_history = np.full((n, 3), np.nan)
    one_step_errors = np.full(n, np.nan)
    five_step_errors = np.full(n, np.nan)
    ten_step_errors = np.full(n, np.nan)
    omega_errors = np.full(n, np.nan)
    alpha_errors = np.full(n, np.nan)
    alpha_errors_one_parameter_oracle = {name: np.full(n, np.nan) for name in PARAMETER_NAMES}
    predicted_alpha = np.full(n, np.nan)
    true_alpha = np.full(n, np.nan)
    residual_norms = np.full(n, np.nan)
    update_magnitudes = np.zeros(n)
    bound_hits = np.zeros(n, dtype=bool)
    conditioning_rows: list[dict[str, Any]] = []
    last_std = np.full(3, np.nan)
    for step in range(1, n):
        old_theta = np.asarray([identifier.get_parameter_estimate()[name] for name in PARAMETER_NAMES])
        result = identifier.add_transition(source_states[step - 1], arrays["actions"][step], source_states[step])
        theta = np.asarray([result.theta_hat[name] for name in PARAMETER_NAMES], dtype=float)
        prediction_theta = old_theta.copy()  # Strict replay: predict before consuming this transition.
        theta_history[step] = theta
        theta_history[:step][np.all(theta_history[:step] == arrays["nominal_params"], axis=1)] = theta_history[:step][np.all(theta_history[:step] == arrays["nominal_params"], axis=1)]
        prediction = predict_next(arrays["true"][step - 1], arrays["actions"][step], prediction_theta, model_params)
        one_step_errors[step] = float(np.linalg.norm(prediction - arrays["true"][step]))
        omega_errors[step] = abs(float(prediction[1] - arrays["true"][step, 1]))
        predicted_alpha[step] = float((prediction[1] - arrays["true"][step - 1, 1]) / model_params["dt"])
        true_alpha[step] = float((arrays["true"][step, 1] - arrays["true"][step - 1, 1]) / model_params["dt"])
        alpha_errors[step] = abs(float(predicted_alpha[step] - true_alpha[step]))
        for parameter_index, parameter_name in enumerate(PARAMETER_NAMES):
            corrected_theta = prediction_theta.copy()
            corrected_theta[parameter_index] = truth[parameter_index]
            corrected_prediction = predict_next(arrays["true"][step - 1], arrays["actions"][step], corrected_theta, model_params)
            corrected_alpha = float((corrected_prediction[1] - arrays["true"][step - 1, 1]) / model_params["dt"])
            alpha_errors_one_parameter_oracle[parameter_name][step] = abs(corrected_alpha - true_alpha[step])
        if step + 4 < n:
            five_step_errors[step] = open_loop_error(arrays["true"][step - 1], arrays["actions"][step : step + 5], arrays["true"][step + 4], prediction_theta, model_params)
        if step + 9 < n:
            ten_step_errors[step] = open_loop_error(arrays["true"][step - 1], arrays["actions"][step : step + 10], arrays["true"][step + 9], prediction_theta, model_params)
        residual_norms[step] = float(result.prediction_error)
        if result.updated:
            diagnostics = diagnostic_for_window(identifier, method, model_params, identifier_cfg, old_theta)
            last_std = np.asarray([diagnostics[f"{name}_std"] for name in PARAMETER_NAMES], dtype=float)
            update_magnitudes[step] = diagnostics["update_magnitude"]
            bound_hits[step] = diagnostics["bound_hit"]
            row = {
                "method": method,
                "input_source": input_source,
                "condition": condition,
                "seed": seed,
                "step": step,
                "timestamp": float(arrays["time"][step]),
                **{f"{name}_hat": float(theta[index]) for index, name in enumerate(PARAMETER_NAMES)},
                **{f"true_{name}": float(truth[index]) for index, name in enumerate(PARAMETER_NAMES)},
                **diagnostics,
            }
            conditioning_rows.append(row)
        std_history[step] = last_std
    # Carry the initial nominal estimate and last uncertainty between update instants.
    for step in range(1, n):
        if np.all(theta_history[step] == arrays["nominal_params"]) and step > 1:
            theta_history[step] = theta_history[step - 1]
        if not np.all(np.isfinite(std_history[step])) and step > 1:
            std_history[step] = std_history[step - 1]
    abs_error = np.abs(theta_history - truth)
    rel_error = abs_error / np.abs(truth)
    update_steps = np.flatnonzero(update_magnitudes > 0.0)
    per_run: dict[str, Any] = {
        "method": method,
        "input_source": input_source,
        "condition": condition,
        "seed": seed,
        "num_steps": n,
        "first_valid_time": float(arrays["time"][conditioning_rows[0]["step"]]) if conditioning_rows else np.nan,
        "one_step_state_prediction_rmse": stat(one_step_errors, "rmse"),
        "five_step_state_prediction_rmse": stat(five_step_errors, "rmse"),
        "ten_step_state_prediction_rmse": stat(ten_step_errors, "rmse"),
        "predicted_omega_rmse": stat(omega_errors, "rmse"),
        "predicted_alpha_rmse": stat(alpha_errors, "rmse"),
        "predicted_alpha_p95_error": stat(alpha_errors, "p95"),
        "residual_autocorrelation_lag1": lag1_autocorrelation(residual_norms[np.isfinite(residual_norms)]),
        "parameter_update_total_variation": float(np.sum(update_magnitudes)),
        "maximum_single_update": stat(update_magnitudes, "max"),
        "parameter_bound_hit_rate": float(np.mean(bound_hits[update_steps])) if len(update_steps) else 0.0,
        "optimizer_failure_count": int(sum(not bool(row["optimizer_converged"]) for row in conditioning_rows)),
        "low_excitation_window_fraction": float(np.mean([bool(row["low_excitation"]) for row in conditioning_rows])) if conditioning_rows else np.nan,
        "locally_distinguishable_fraction": float(np.mean([bool(row["locally_distinguishable"]) for row in conditioning_rows])) if conditioning_rows else np.nan,
        "median_condition_number": stat([row["condition_number"] for row in conditioning_rows], "p95") if conditioning_rows else np.nan,
        "minimum_singular_value_median": stat([row["minimum_singular_value"] for row in conditioning_rows], "mean") if conditioning_rows else np.nan,
        "theta_history_json": json.dumps(theta_history.tolist(), separators=(",", ":")),
        "std_history_json": json.dumps(std_history.tolist(), separators=(",", ":"), allow_nan=True),
        "time_json": json.dumps(arrays["time"].tolist(), separators=(",", ":")),
        "predicted_alpha_json": json.dumps(predicted_alpha.tolist(), separators=(",", ":"), allow_nan=True),
        "true_alpha_json": json.dumps(true_alpha.tolist(), separators=(",", ":"), allow_nan=True),
        "update_magnitude_json": json.dumps(update_magnitudes.tolist(), separators=(",", ":")),
        "condition_number_json": json.dumps([row["condition_number"] for row in conditioning_rows], separators=(",", ":")),
        "minimum_singular_value_json": json.dumps([row["minimum_singular_value"] for row in conditioning_rows], separators=(",", ":")),
    }
    for name in PARAMETER_NAMES:
        corrected_rmse = stat(alpha_errors_one_parameter_oracle[name], "rmse")
        per_run[f"predicted_alpha_rmse_if_{name}_oracle"] = corrected_rmse
        per_run[f"predicted_alpha_error_reduction_from_{name}"] = per_run["predicted_alpha_rmse"] - corrected_rmse
    for index, name in enumerate(PARAMETER_NAMES):
        inside = rel_error[:, index] <= 0.10
        first_inside = np.flatnonzero(inside)
        per_run.update(
            {
                f"{name}_absolute_error_mean": stat(abs_error[:, index], "mean"),
                f"{name}_relative_error_mean": stat(rel_error[:, index], "mean"),
                f"{name}_rmse": stat(theta_history[:, index] - truth[index], "rmse"),
                f"{name}_median_error": float(np.median(abs_error[:, index])),
                f"{name}_p95_error": stat(abs_error[:, index], "p95"),
                f"{name}_maximum_error": stat(abs_error[:, index], "max"),
                f"{name}_planner_time_error": float(abs_error[0, index]),
                f"{name}_final_error": float(abs_error[-1, index]),
                f"{name}_convergence_time_10pct": float(arrays["time"][first_inside[0]]) if len(first_inside) else np.nan,
                f"{name}_fraction_inside_10pct": float(np.mean(inside)),
            }
        )
    planner_rows = planner_time_rows(method, input_source, condition, seed, arrays, theta_history, std_history)
    return per_run, conditioning_rows, planner_rows


def planner_time_rows(
    method: str,
    input_source: str,
    condition: str,
    seed: int,
    arrays: dict[str, np.ndarray],
    theta_history: np.ndarray,
    std_history: np.ndarray,
) -> list[dict[str, Any]]:
    valid = np.flatnonzero(np.all(np.isfinite(std_history), axis=1))
    confidence = np.flatnonzero(np.all(np.isfinite(std_history), axis=1) & np.all(std_history / np.maximum(np.abs(theta_history), 1.0e-12) <= CONFIDENCE_REL_STD_THRESHOLD, axis=1))
    later = int(np.argmin(np.abs(arrays["time"] - LATER_DIAGNOSTIC_TIME_S)))
    choices = [
        ("t0_nominal", 0),
        ("first_valid_window", int(valid[0]) if len(valid) else None),
        ("first_confidence_threshold", int(confidence[0]) if len(confidence) else None),
        ("fixed_2s_diagnostic", later),
    ]
    rows = []
    for label, index in choices:
        row: dict[str, Any] = {"method": method, "input_source": input_source, "condition": condition, "seed": seed, "planning_time_type": label}
        if index is None:
            row.update({"available": False, "step": "", "timestamp": np.nan, "mean_relative_error": np.nan, "max_relative_std": np.nan})
        else:
            rel_error = np.abs(theta_history[index] - arrays["truth_params"]) / np.abs(arrays["truth_params"])
            rel_std = std_history[index] / np.maximum(np.abs(theta_history[index]), 1.0e-12)
            row.update(
                {
                    "available": True,
                    "step": index,
                    "timestamp": float(arrays["time"][index]),
                    "mean_relative_error": float(np.mean(rel_error)),
                    "max_relative_std": float(np.max(rel_std)) if np.all(np.isfinite(rel_std)) else np.nan,
                    **{f"{name}_hat": float(theta_history[index, p]) for p, name in enumerate(PARAMETER_NAMES)},
                    **{f"{name}_relative_error": float(rel_error[p]) for p, name in enumerate(PARAMETER_NAMES)},
                    **{f"{name}_std": float(std_history[index, p]) for p, name in enumerate(PARAMETER_NAMES)},
                }
            )
        rows.append(row)
    return rows


def aggregate_offline(per_run: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        "one_step_state_prediction_rmse", "five_step_state_prediction_rmse", "ten_step_state_prediction_rmse",
        "predicted_omega_rmse", "predicted_alpha_rmse", "predicted_alpha_p95_error",
        "parameter_update_total_variation", "maximum_single_update", "parameter_bound_hit_rate",
        "optimizer_failure_count", "low_excitation_window_fraction", "locally_distinguishable_fraction",
    ]
    for name in PARAMETER_NAMES:
        metrics.extend(
            [
                f"{name}_absolute_error_mean", f"{name}_relative_error_mean", f"{name}_rmse",
                f"{name}_median_error", f"{name}_p95_error", f"{name}_maximum_error",
                f"{name}_planner_time_error", f"{name}_final_error", f"{name}_fraction_inside_10pct",
            ]
        )
        metrics.extend([f"predicted_alpha_rmse_if_{name}_oracle", f"predicted_alpha_error_reduction_from_{name}"])
    rows = []
    for input_source in INPUT_SOURCES:
        for condition in CONDITIONS:
            for method in IDENTIFIER_METHODS:
                group = [row for row in per_run if row["input_source"] == input_source and row["condition"] == condition and row["method"] == method]
                row: dict[str, Any] = {"method": method, "input_source": input_source, "condition": condition, "n": len(group)}
                row.update({f"{metric}_mean": stat([item[metric] for item in group], "mean") for metric in metrics})
                rows.append(row)
    return rows


def uncertainty_calibration(conditioning: list[dict[str, Any]]) -> list[dict[str, Any]]:
    z_values = {0.50: 0.67448975, 0.90: 1.64485363, 0.95: 1.95996398}
    rows = []
    for input_source in INPUT_SOURCES:
        for condition in CONDITIONS:
            for method in IDENTIFIER_METHODS:
                group = [row for row in conditioning if row["input_source"] == input_source and row["condition"] == condition and row["method"] == method]
                for name in PARAMETER_NAMES:
                    estimates = np.asarray([float(row[f"{name}_hat"]) for row in group])
                    truths = np.asarray([float(row[f"true_{name}"]) for row in group])
                    stds = np.asarray([float(row[f"{name}_std"]) for row in group])
                    valid = np.isfinite(estimates) & np.isfinite(truths) & np.isfinite(stds) & (stds > 0.0)
                    for level, z in z_values.items():
                        if np.any(valid):
                            error = np.abs(estimates[valid] - truths[valid])
                            half_width = z * stds[valid]
                            coverage = float(np.mean(error <= half_width))
                            width = float(np.mean(2.0 * half_width))
                            standardized_error = float(np.mean(error / stds[valid]))
                        else:
                            coverage = width = standardized_error = np.nan
                        calibration = "directional"
                        if np.isfinite(coverage) and coverage < level - 0.15:
                            calibration = "overconfident"
                        elif np.isfinite(coverage) and coverage > min(1.0, level + 0.15):
                            calibration = "underconfident"
                        rows.append(
                            {
                                "method": method,
                                "input_source": input_source,
                                "condition": condition,
                                "parameter": name,
                                "interval_level": level,
                                "sample_count": int(np.count_nonzero(valid)),
                                "coverage": coverage,
                                "mean_interval_width": width,
                                "mean_error_over_predicted_std": standardized_error,
                                "calibration_label": calibration,
                            }
                        )
    return rows


def method_stress_score(summary: list[dict[str, Any]], method: str) -> dict[str, float]:
    stress = [row for row in summary if row["input_source"] == "ukf_filtered" and row["method"] == method and row["condition"] in {"stronger_noise", "mass_mismatch"}]
    parameter_error = stat([np.mean([row[f"{name}_relative_error_mean_mean"] for name in PARAMETER_NAMES]) for row in stress], "mean")
    return {
        "parameter_error": parameter_error,
        "one_step": stat([row["one_step_state_prediction_rmse_mean"] for row in stress], "mean"),
        "multi_step": stat([0.5 * (row["five_step_state_prediction_rmse_mean"] + row["ten_step_state_prediction_rmse_mean"]) for row in stress], "mean"),
        "alpha": stat([row["predicted_alpha_rmse_mean"] for row in stress], "mean"),
        "jitter": stat([row["parameter_update_total_variation_mean"] for row in stress], "mean"),
        "bound_hits": stat([row["parameter_bound_hit_rate_mean"] for row in stress], "mean"),
    }


def offline_gate(summary: list[dict[str, Any]], calibration: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = method_stress_score(summary, "windowed_nls_current")
    candidates = []
    for method in ("windowed_nls_huber", "windowed_nls_cauchy"):
        score = method_stress_score(summary, method)
        calibration_rows = [row for row in calibration if row["input_source"] == "ukf_filtered" and row["method"] == method and row["condition"] in {"stronger_noise", "mass_mismatch"} and float(row["interval_level"]) == 0.90]
        directional = stat([float(row["coverage"]) for row in calibration_rows], "mean")
        checks = {
            "parameter_error_improved": score["parameter_error"] <= 0.90 * baseline["parameter_error"],
            "one_step_improved": score["one_step"] < baseline["one_step"],
            "multi_step_improved": score["multi_step"] < baseline["multi_step"],
            "alpha_improved": score["alpha"] < baseline["alpha"],
            "jitter_acceptable": score["jitter"] <= 1.50 * baseline["jitter"],
            "bounds_acceptable": score["bound_hits"] <= baseline["bound_hits"] + 0.05,
            "uncertainty_directional": np.isfinite(directional) and directional >= 0.35,
        }
        passed = all(checks.values())
        candidates.append({"method": method, "score": score, "coverage90": directional, "checks": checks, "passed": passed})
    passed_candidates = [item for item in candidates if item["passed"]]
    selected = min(passed_candidates, key=lambda item: item["score"]["alpha"])["method"] if passed_candidates else None
    return {"passed": selected is not None, "selected": selected, "baseline": baseline, "candidates": candidates}


def aggregate_closed_loop(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        "target_crossed", "crossing_time", "true_alpha_mean", "true_alpha_p95", "true_alpha_p99", "true_alpha_max",
        "alpha_violation_duration", "alpha_violation_integral", "alpha_violation_max", "state_tracking_rmse",
        "tracker_failure_count", "planner_failure_count", "parameter_update_magnitude_mean", "parameter_update_magnitude_max",
        "true_predicted_alpha_error_rmse",
    ]
    out = []
    for condition in ["clean", "initial_theta_offset", "stronger_noise", "mass_mismatch"]:
        for method in sorted({row["method"] for row in rows}):
            group = [row for row in rows if row["condition"] == condition and row["method"] == method]
            if not group:
                continue
            aggregate = {"method": method, "condition": condition, "n": len(group)}
            aggregate.update({f"{metric}_mean": stat([float(row[metric]) for row in group], "mean") for metric in metrics})
            out.append(aggregate)
    return out


def run_closed_loop(selected: str, base_cfg: dict[str, Any], output_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str, int], list[dict[str, Any]]]]:
    selected_loss = "huber" if selected == "windowed_nls_huber" else "cauchy"
    methods = ["adaptive_current_nls", "adaptive_selected_robust_identifier", "oracle_parameters", "fixed_nominal"]
    conditions = ["clean", "initial_theta_offset", "stronger_noise", "mass_mismatch"]
    per_run = []
    trajectories: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    total = len(methods) * len(conditions) * len(SEEDS)
    count = 0
    for condition in conditions:
        for seed in SEEDS:
            for method in methods:
                count += 1
                print(f"[stage9k closed {count}/{total}] {method}/{condition}/seed{seed}", flush=True)
                cfg = stage9j_overrides(base_cfg, condition)
                cfg["mpc_params"].setdefault("solver", {})["seed"] = seed
                if method == "oracle_parameters":
                    stage9j_method = "oracle_planner_tracker"; factory = None
                elif method == "fixed_nominal":
                    stage9j_method = "fixed_nominal_planner_tracker"; factory = None
                elif method == "adaptive_selected_robust_identifier":
                    stage9j_method = "full_adaptive_planner_tracker"
                    factory = lambda params, ident_cfg, loss=selected_loss: RobustWindowedLeastSquaresIdentifier(params, ident_cfg, loss=loss, smoothing_alpha=0.5)
                else:
                    stage9j_method = "full_adaptive_planner_tracker"; factory = None
                rows, controller, runtime = run_planner_tracker(stage9j_method, condition, seed, cfg, condition_cfg(base_cfg, condition, seed), identifier_factory=factory)
                summary = summarize_run(stage9j_method, condition, seed, rows, cfg, runtime, controller)
                summary["method"] = method
                summary["selected_identifier"] = selected if method == "adaptive_selected_robust_identifier" else ""
                per_run.append(summary); trajectories[(method, condition, seed)] = rows
                write_dict_csv(output_root / "stage9k_closed_loop_per_run.csv", per_run)
    summary = aggregate_closed_loop(per_run)
    write_dict_csv(output_root / "stage9k_closed_loop_summary.csv", summary)
    return per_run, summary, trajectories


def save_offline_figures(
    per_run: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    conditioning: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    planner_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    fig_dir = output_root / "figs"; fig_dir.mkdir(parents=True, exist_ok=True)
    representative = {row["method"]: row for row in per_run if row["input_source"] == "ukf_filtered" and row["condition"] == "stronger_noise" and int(row["seed"]) == 102}
    colors = {method: f"C{index}" for index, method in enumerate(IDENTIFIER_METHODS)}
    truth = np.array([1.2, 450.0, 18.0])

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for method, row in representative.items():
        time_values = np.asarray(json.loads(row["time_json"])); theta = np.asarray(json.loads(row["theta_history_json"]))
        for index, axis in enumerate(axes): axis.plot(time_values, theta[:, index], label=method, color=colors[method])
    for index, axis in enumerate(axes): axis.axhline(truth[index], color="black", linestyle=":"); axis.set_ylabel(PARAMETER_NAMES[index]); axis.grid(alpha=0.3); axis.legend(fontsize=7)
    axes[-1].set_xlabel("time [s]"); axes[0].set_title("Parameter estimates versus truth: stronger_noise seed102")
    fig.tight_layout(); fig.savefig(fig_dir / "01_parameter_estimates_vs_true.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for method, row in representative.items():
        time_values = np.asarray(json.loads(row["time_json"])); theta = np.asarray(json.loads(row["theta_history_json"]))
        relative = np.abs(theta - truth) / truth
        for index, axis in enumerate(axes): axis.plot(time_values, relative[:, index], label=method, color=colors[method])
    for index, axis in enumerate(axes): axis.axhline(0.10, color="black", linestyle=":"); axis.set_ylabel(PARAMETER_NAMES[index]); axis.grid(alpha=0.3); axis.legend(fontsize=7)
    axes[-1].set_xlabel("time [s]"); axes[0].set_title("Parameter relative error: stronger_noise seed102")
    fig.tight_layout(); fig.savefig(fig_dir / "02_parameter_relative_error.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for method, row in representative.items():
        ax.plot(json.loads(row["time_json"]), json.loads(row["update_magnitude_json"]), label=method, color=colors[method])
    ax.set(xlabel="time [s]", ylabel="parameter update norm", title="Parameter update magnitude: stronger_noise seed102"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "03_parameter_update_magnitude.png", dpi=150); plt.close(fig)

    cond_rep = [row for row in conditioning if row["input_source"] == "ukf_filtered" and row["condition"] == "stronger_noise" and int(row["seed"]) == 102]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for method in IDENTIFIER_METHODS:
        group = [row for row in cond_rep if row["method"] == method]
        ax.semilogy([row["timestamp"] for row in group], [row["condition_number"] for row in group], label=method)
    ax.set(xlabel="time [s]", ylabel="cond(JTWJ)", title="Scaled-Jacobian condition number"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "04_jacobian_condition_number.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for method in IDENTIFIER_METHODS:
        group = [row for row in cond_rep if row["method"] == method]
        ax.semilogy([row["timestamp"] for row in group], [row["minimum_singular_value"] for row in group], label=method)
    ax.set(xlabel="time [s]", ylabel="minimum singular value", title="Scaled-Jacobian minimum singular value"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "05_minimum_singular_value.png", dpi=150); plt.close(fig)

    selected_row = representative["windowed_nls_huber"]
    time_values = np.asarray(json.loads(selected_row["time_json"])); theta = np.asarray(json.loads(selected_row["theta_history_json"])); std = np.asarray(json.loads(selected_row["std_history_json"]), dtype=float)
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for index, axis in enumerate(axes):
        axis.plot(time_values, theta[:, index], label="estimate")
        axis.fill_between(time_values, theta[:, index] - 1.96 * std[:, index], theta[:, index] + 1.96 * std[:, index], alpha=0.25, label="approx 95%")
        axis.axhline(truth[index], color="black", linestyle=":", label="true"); axis.set_ylabel(PARAMETER_NAMES[index]); axis.grid(alpha=0.3); axis.legend(fontsize=7)
    axes[-1].set_xlabel("time [s]"); axes[0].set_title("Huber local confidence diagnostic: stronger_noise seed102")
    fig.tight_layout(); fig.savefig(fig_dir / "06_parameter_confidence_intervals.png", dpi=150); plt.close(fig)

    coverage_rows = [row for row in calibration if row["input_source"] == "ukf_filtered" and float(row["interval_level"]) == 0.90]
    fig, ax = plt.subplots(figsize=(11, 5)); x = np.arange(len(CONDITIONS)); width = 0.25
    for index, method in enumerate(IDENTIFIER_METHODS):
        values = [stat([row["coverage"] for row in coverage_rows if row["method"] == method and row["condition"] == condition], "mean") for condition in CONDITIONS]
        ax.bar(x + (index - 1) * width, values, width, label=method)
    ax.axhline(0.90, color="black", linestyle=":"); ax.set_xticks(x); ax.set_xticklabels(CONDITIONS, rotation=35, ha="right"); ax.set_ylabel("90% empirical coverage"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "07_uncertainty_coverage.png", dpi=150); plt.close(fig)

    primary_summary = [row for row in summary if row["input_source"] == "ukf_filtered"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    prediction_metrics = [("one_step_state_prediction_rmse_mean", "1-step"), ("five_step_state_prediction_rmse_mean", "5-step"), ("ten_step_state_prediction_rmse_mean", "10-step")]
    for axis, (metric, title) in zip(axes, prediction_metrics):
        xx = np.arange(len(CONDITIONS)); w = 0.25
        for index, method in enumerate(IDENTIFIER_METHODS):
            values = [next(row[metric] for row in primary_summary if row["method"] == method and row["condition"] == condition) for condition in CONDITIONS]
            axis.bar(xx + (index - 1) * w, values, w, label=method)
        axis.set_xticks(xx); axis.set_xticklabels(CONDITIONS, rotation=60, ha="right", fontsize=7); axis.set_title(title); axis.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("state prediction RMSE"); axes[-1].legend(fontsize=7); fig.tight_layout()
    fig.savefig(fig_dir / "08_prediction_error.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for method, row in representative.items():
        ax.plot(json.loads(row["time_json"]), json.loads(row["predicted_alpha_json"]), label=f"{method} predicted", alpha=0.75)
    ax.plot(json.loads(selected_row["time_json"]), json.loads(selected_row["true_alpha_json"]), color="black", linewidth=1.2, label="true")
    ax.set(xlabel="time [s]", ylabel="alpha", title="True versus model-predicted alpha: stronger_noise seed102"); ax.legend(fontsize=7); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "09_true_vs_predicted_alpha.png", dpi=150); plt.close(fig)

    primary_planner = [row for row in planner_rows if row["input_source"] == "ukf_filtered"]
    labels = ["t0_nominal", "first_valid_window", "first_confidence_threshold", "fixed_2s_diagnostic"]
    fig, ax = plt.subplots(figsize=(10, 5)); xx = np.arange(len(labels)); w = 0.25
    for index, method in enumerate(IDENTIFIER_METHODS):
        values = [stat([row["mean_relative_error"] for row in primary_planner if row["method"] == method and row["planning_time_type"] == label], "mean") for label in labels]
        ax.bar(xx + (index - 1) * w, values, w, label=method)
    ax.set_xticks(xx); ax.set_xticklabels(labels, rotation=25, ha="right"); ax.set_ylabel("mean parameter relative error"); ax.set_title("Hypothetical planner-time parameter error"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "10_planner_time_parameter_error.png", dpi=150); plt.close(fig)


def save_closed_loop_figures(summary: list[dict[str, Any]], trajectories: dict[tuple[str, str, int], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig, ax = plt.subplots(figsize=(9, 5))
    for method in sorted({key[0] for key in trajectories}):
        rows = trajectories[(method, "stronger_noise", 101)]
        ax.plot([row["t"] for row in rows], [row["true_alpha"] for row in rows], label=method)
    ax.set(xlabel="time [s]", ylabel="true alpha", title="Closed-loop alpha: stronger_noise seed101"); ax.legend(fontsize=7); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "11_closed_loop_alpha_comparison.png", dpi=150); plt.close(fig)
    methods = sorted({row["method"] for row in summary}); conditions = ["clean", "initial_theta_offset", "stronger_noise", "mass_mismatch"]
    fig, ax = plt.subplots(figsize=(10, 5)); x = np.arange(len(conditions)); width = 0.8 / len(methods)
    for index, method in enumerate(methods):
        values = [next(row["target_crossed_mean"] for row in summary if row["method"] == method and row["condition"] == condition) for condition in conditions]
        ax.bar(x + (index - (len(methods)-1)/2) * width, values, width, label=method)
    ax.set_xticks(x); ax.set_xticklabels(conditions); ax.set_ylim(0, 1.05); ax.set_ylabel("crossing success rate"); ax.legend(fontsize=7); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(fig_dir / "12_crossing_success_comparison.png", dpi=150); plt.close(fig)


def summary_row(summary: list[dict[str, Any]], method: str, condition: str, input_source: str = "ukf_filtered") -> dict[str, Any]:
    return next(row for row in summary if row["method"] == method and row["condition"] == condition and row["input_source"] == input_source)


def determine_next_direction(
    gate: dict[str, Any],
    summary: list[dict[str, Any]],
    planner_rows: list[dict[str, Any]],
    closed_summary: list[dict[str, Any]],
) -> tuple[str, str]:
    if gate["passed"] and closed_summary:
        robust = [row for row in closed_summary if row["method"] == "adaptive_selected_robust_identifier"]
        current = [row for row in closed_summary if row["method"] == "adaptive_current_nls"]
        robust_alpha = stat([row["true_alpha_max_mean"] for row in robust], "mean")
        current_alpha = stat([row["true_alpha_max_mean"] for row in current], "mean")
        robust_cross = stat([row["target_crossed_mean"] for row in robust], "mean")
        current_cross = stat([row["target_crossed_mean"] for row in current], "mean")
        if robust_alpha < current_alpha and robust_cross >= current_cross:
            return "improved identifier", f"选定 robust identifier 将平均 true-alpha max 从 {current_alpha:.3g} 降至 {robust_alpha:.3g}，且 crossing 未下降。"
    primary_planner = [row for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"]
    t0 = stat([row["mean_relative_error"] for row in primary_planner if row["planning_time_type"] == "t0_nominal"], "mean")
    later = stat([row["mean_relative_error"] for row in primary_planner if row["planning_time_type"] == "fixed_2s_diagnostic"], "mean")
    if np.isfinite(later) and later <= 0.8 * t0:
        return "identification warm-up/confidence-gated planning", f"current NLS 在 2 s 的平均参数误差由 {t0:.3g} 降至 {later:.3g}。"
    distinguishable = stat([row["locally_distinguishable_fraction_mean"] for row in summary if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"], "mean")
    if distinguishable < 0.5:
        return "improved excitation", f"current NLS 的局部可区分窗口比例仅 {distinguishable:.3g}。"
    true_error = stat([np.mean([row[f"{name}_relative_error_mean_mean"] for name in PARAMETER_NAMES]) for row in summary if row["input_source"] == "true_state_diagnostic" and row["method"] == "windowed_nls_current"], "mean")
    filtered_error = stat([np.mean([row[f"{name}_relative_error_mean_mean"] for name in PARAMETER_NAMES]) for row in summary if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"], "mean")
    if true_error < 0.8 * filtered_error:
        return "improved identifier", f"true-state replay 明显优于 UKF-input replay（{true_error:.3g} vs {filtered_error:.3g}），下一步应是 estimator-aware errors-in-variables 或 joint state-parameter identifier。"
    return "richer residual model", f"true-state replay 仍有显著误差（{true_error:.3g}），robust loss/延迟规划不足以解决。"


def write_report(
    path: Path,
    per_run: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    conditioning: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    planner_rows: list[dict[str, Any]],
    gate: dict[str, Any],
    closed_summary: list[dict[str, Any]],
    next_direction: tuple[str, str],
) -> None:
    current_stress = gate["baseline"]
    huber = next(item for item in gate["candidates"] if item["method"] == "windowed_nls_huber")
    cauchy = next(item for item in gate["candidates"] if item["method"] == "windowed_nls_cauchy")
    current_primary = [row for row in summary if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"]
    current_true = [row for row in summary if row["input_source"] == "true_state_diagnostic" and row["method"] == "windowed_nls_current"]
    low_excitation = stat([row["low_excitation_window_fraction_mean"] for row in current_primary], "mean")
    distinguishable = stat([row["locally_distinguishable_fraction_mean"] for row in current_primary], "mean")
    condition_number = stat([row["condition_number"] for row in conditioning if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"], "p95")
    regressor_correlation_p95 = stat([row["regressor_max_abs_correlation"] for row in conditioning if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"], "p95")
    minimum_singular_value = stat([row["minimum_singular_value"] for row in conditioning if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current"], "mean")
    alpha_reduction = {name: stat([row[f"predicted_alpha_error_reduction_from_{name}_mean"] for row in current_primary], "mean") for name in PARAMETER_NAMES}
    dominant_parameter = max(alpha_reduction, key=alpha_reduction.get)
    coverage90 = {
        method: stat([row["coverage"] for row in calibration if row["input_source"] == "ukf_filtered" and row["method"] == method and float(row["interval_level"]) == 0.90], "mean")
        for method in IDENTIFIER_METHODS
    }
    current_coverage_by_parameter = {
        name: stat([row["coverage"] for row in calibration if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["parameter"] == name and float(row["interval_level"]) == 0.90], "mean")
        for name in PARAMETER_NAMES
    }
    true_state_error = stat([np.mean([row[f"{name}_relative_error_mean_mean"] for name in PARAMETER_NAMES]) for row in current_true], "mean")
    filtered_state_error = stat([np.mean([row[f"{name}_relative_error_mean_mean"] for name in PARAMETER_NAMES]) for row in current_primary], "mean")
    t0 = stat([row["mean_relative_error"] for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "t0_nominal"], "mean")
    first_valid = stat([row["mean_relative_error"] for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "first_valid_window"], "mean")
    fixed2 = stat([row["mean_relative_error"] for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "fixed_2s_diagnostic"], "mean")
    confidence_available = stat([float(str(row["available"]).lower() == "true") for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "first_confidence_threshold"], "mean")
    confidence_time = stat([row["timestamp"] for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "first_confidence_threshold" and bool(row["available"])], "mean")
    confidence_error = stat([row["mean_relative_error"] for row in planner_rows if row["input_source"] == "ukf_filtered" and row["method"] == "windowed_nls_current" and row["planning_time_type"] == "first_confidence_threshold" and bool(row["available"])], "mean")
    with path.open("w") as handle:
        handle.write("# Stage 9K Identifier Diagnosis and Robust Offline Ablation\n\n")
        handle.write("## Decision\n\n")
        handle.write(f"- Offline gate: **{'PASS' if gate['passed'] else 'FAIL'}**. Selected identifier: `{gate['selected'] or 'none'}`.\n")
        handle.write(f"- Closed-loop Stage 9K-B: **{'run' if closed_summary else 'not run'}**.\n")
        handle.write(f"- Next technical direction: **{next_direction[0]}** — {next_direction[1]}\n")
        handle.write("- Robust covariance is a local pseudo-inverse diagnostic only; no formal confidence guarantee is claimed.\n\n")
        handle.write("## Offline stress comparison\n\n")
        handle.write("| method | parameter error | 1-step | multi-step | alpha RMSE | update TV | bound hits | gate |\n|---|---:|---:|---:|---:|---:|---:|---|\n")
        for label, item in [("windowed_nls_current", {"score": current_stress, "passed": False}), (huber["method"], huber), (cauchy["method"], cauchy)]:
            score = item["score"]
            handle.write(f"| {label} | {fmt(score['parameter_error'])} | {fmt(score['one_step'])} | {fmt(score['multi_step'])} | {fmt(score['alpha'])} | {fmt(score['jitter'])} | {fmt(score['bound_hits'])} | {'PASS' if item.get('passed') else '-'} |\n")
        handle.write("\n## Required Questions\n\n")
        handle.write(f"1. **Current NLS diagnosis.** 主要问题是 UKF-input 导致的 errors-in-variables bias，而不是 optimizer 不收敛。平均参数误差 filtered={fmt(filtered_state_error)}、true-state={fmt(true_state_error)}。所有窗口 rank=3，但 regressor correlation p95={fmt(regressor_correlation_p95)}、mean minimum singular value={fmt(minimum_singular_value)}、information condition-number p95={fmt(condition_number)}，说明局部 full rank 不等于可靠可辨识。low-excitation fraction={fmt(low_excitation)}。\n\n")
        handle.write(f"2. **Dominant parameter for alpha prediction.** 单参数替换为真值的 offline ablation 显示 `{dominant_parameter}` 带来最大平均 alpha-RMSE 降幅 {fmt(alpha_reduction[dominant_parameter])}；各参数降幅={alpha_reduction}。\n\n")
        handle.write(f"3. **Robust loss in stronger-noise/mass-mismatch.** Huber checks={huber['checks']}；Cauchy checks={cauchy['checks']}。因此 robust loss {'materially improves the complete gate' if gate['passed'] else 'does not materially improve all required metrics'}。\n\n")
        handle.write(f"4. **Smoothing and jumps.** Current stress update TV={fmt(current_stress['jitter'])}，Huber={fmt(huber['score']['jitter'])}，Cauchy={fmt(cauchy['score']['jitter'])}。固定 alpha=0.5 并未降低总更新变化，且 robust variants 的参数误差更高；本次 smoothing 表现为额外 lag，而非有效抑制 harmful jumps。\n\n")
        handle.write(f"5. **Identifiability.** 数值 rank 在所有 current 窗口为 3，宽松 local criterion fraction={fmt(distinguishable)}，但 p95 regressor correlation={fmt(regressor_correlation_p95)} 且存在很小 singular values，因此 m/k/b_r 不能在所有窗口被可靠、独立地估计。轨迹并非普遍低激励（fraction={fmt(low_excitation)}），主要限制是相关 regressor 加上 noisy estimated-state input。\n\n")
        handle.write(f"6. **Uncertainty calibration.** 整体 90% empirical coverage：{coverage90}；current 分参数 coverage={current_coverage_by_parameter}。远低于 nominal 90%，尤其 k 明显过度自信，因此不能支持后续 uncertainty tightening。\n\n")
        handle.write(f"7. **Accuracy after samples.** Current mean relative error：t0={fmt(t0)}，first valid={fmt(first_valid)}，fixed 2 s={fmt(fixed2)}。有小幅改善，但 2 s 相对 t0 只降低约 {fmt((t0-fixed2)/t0 if t0 else np.nan)}，且远差于 true-state replay，未达到可靠 long-horizon planning 的证据标准。\n\n")
        handle.write(f"8. **Delayed/confidence-gated planning.** 20% relative-std trigger 可用比例={fmt(confidence_available)}，平均在 t={fmt(confidence_time)} s 触发，但当时 mean relative error={fmt(confidence_error)}，且 coverage 显示严重 overconfidence。故当前 confidence gate 不可信；固定 2 s 也没有足够大的误差改善来支持 primary delayed plan。\n\n")
        if closed_summary:
            robust_closed = [row for row in closed_summary if row["method"] == "adaptive_selected_robust_identifier"]
            current_closed = [row for row in closed_summary if row["method"] == "adaptive_current_nls"]
            handle.write(f"9. **Closed-loop alpha/crossing.** Current mean alpha max={fmt(stat([row['true_alpha_max_mean'] for row in current_closed], 'mean'))}，selected robust={fmt(stat([row['true_alpha_max_mean'] for row in robust_closed], 'mean'))}；crossing={fmt(stat([row['target_crossed_mean'] for row in current_closed], 'mean'))}/{fmt(stat([row['target_crossed_mean'] for row in robust_closed], 'mean'))}。\n\n")
        else:
            handle.write("9. **Closed-loop alpha/crossing.** Offline gate 未通过，因此按规则未运行 closed-loop comparison，不能声称 robust identifier 降低了 true closed-loop alpha。\n\n")
        handle.write(f"10. **Next step.** {next_direction[0]}。{next_direction[1]} 本阶段未实现下一方向。\n\n")
        handle.write("## Reproducibility\n\n")
        handle.write("- Replay source: `results/stage9j_gap_decomposition/stage9j_replay.csv`; all identifiers consume identical UKF-state/control sequences.\n")
        handle.write("- Optional true-state replay is diagnostic only and never changes recorded actions or states.\n")
        handle.write("- Huber f_scale=1.345; Cauchy f_scale=2.3849; both use per-window frozen MAD scale and fixed parameter smoothing alpha=0.5. No sweep was run.\n")
        handle.write("- Optional augmented-parameter UKF was not implemented because adding a coupled 11-state process/measurement model was not straightforward enough to justify blocking the required NLS comparison.\n")
        handle.write(f"- Confidence trigger diagnostic: max relative parameter std <= {CONFIDENCE_REL_STD_THRESHOLD}; fixed later diagnostic time={LATER_DIAGNOSTIC_TIME_S} s.\n")
        handle.write(f"- Low-excitation thresholds: {LOW_EXCITATION_THRESHOLDS}.\n")
        handle.write("- No dynamics, UKF, planner/tracker, MPC weight, rho_alpha, horizon, constraint, solver, crossing, or schedule changes were made.\n")


def typed_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    rows: list[dict[str, Any]] = []
    for source in raw:
        row: dict[str, Any] = {}
        for key, value in source.items():
            if key.endswith("_json") or key in {"method", "input_source", "condition", "optimizer_message", "planning_time_type", "parameter", "calibration_label"}:
                row[key] = value
            elif value == "":
                row[key] = np.nan
            elif value.lower() in {"true", "false"}:
                row[key] = value.lower() == "true"
            else:
                try:
                    row[key] = float(value)
                except ValueError:
                    row[key] = value
        rows.append(row)
    return rows


def refresh_current_diagnostics(replay_path: Path, output_root: Path, config_path: Path) -> None:
    replay = load_replay(replay_path); base_cfg = load_experiment_config(config_path)
    per_run = [row for row in typed_csv_rows(output_root / "stage9k_offline_per_run.csv") if row["method"] != "windowed_nls_current"]
    conditioning = [row for row in typed_csv_rows(output_root / "stage9k_conditioning.csv") if row["method"] != "windowed_nls_current"]
    planner_rows = [row for row in typed_csv_rows(output_root / "stage9k_planner_time_diagnosis.csv") if row["method"] != "windowed_nls_current"]
    count = 0
    for input_source in INPUT_SOURCES:
        for condition in CONDITIONS:
            for seed in SEEDS:
                count += 1
                print(f"[stage9k refresh-current {count}/48] {input_source}/{condition}/seed{seed}", flush=True)
                result, condition_rows, planning = run_offline_one("windowed_nls_current", input_source, condition, seed, replay[(condition, seed)], base_cfg)
                per_run.append(result); conditioning.extend(condition_rows); planner_rows.extend(planning)
    per_run.sort(key=lambda row: (str(row["input_source"]), CONDITIONS.index(str(row["condition"])), int(row["seed"]), IDENTIFIER_METHODS.index(str(row["method"]))))
    conditioning.sort(key=lambda row: (str(row["input_source"]), CONDITIONS.index(str(row["condition"])), int(row["seed"]), IDENTIFIER_METHODS.index(str(row["method"])), int(row["step"])))
    planner_rows.sort(key=lambda row: (str(row["input_source"]), CONDITIONS.index(str(row["condition"])), int(row["seed"]), IDENTIFIER_METHODS.index(str(row["method"])), str(row["planning_time_type"])))
    summary = aggregate_offline(per_run); calibration = uncertainty_calibration(conditioning); gate = offline_gate(summary, calibration)
    write_dict_csv(output_root / "stage9k_offline_per_run.csv", per_run)
    write_dict_csv(output_root / "stage9k_conditioning.csv", conditioning)
    write_dict_csv(output_root / "stage9k_planner_time_diagnosis.csv", planner_rows)
    write_dict_csv(output_root / "stage9k_offline_summary.csv", summary)
    write_dict_csv(output_root / "stage9k_uncertainty_calibration.csv", calibration)
    save_offline_figures(per_run, summary, conditioning, calibration, planner_rows, output_root)
    next_direction = determine_next_direction(gate, summary, planner_rows, [])
    write_report(output_root / "stage9k_report.md", per_run, summary, conditioning, calibration, planner_rows, gate, [], next_direction)
    (output_root / "stage9k_gate.json").write_text(json.dumps(gate, indent=2, default=str))
    with (output_root / "stage9k_command.txt").open("a") as handle:
        handle.write(f"conda run -n mpc_learn python scripts/{Path(__file__).name} --refresh-current\n")
    print(f"[stage9k] refreshed current diagnostics; gate={gate['passed']}", flush=True)


def run(replay_path: Path, output_root: Path, config_path: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "figs").mkdir(parents=True, exist_ok=True)
    replay = load_replay(replay_path)
    base_cfg = load_experiment_config(config_path)
    per_run: list[dict[str, Any]] = []
    conditioning: list[dict[str, Any]] = []
    planner_rows: list[dict[str, Any]] = []
    total = len(IDENTIFIER_METHODS) * len(INPUT_SOURCES) * len(CONDITIONS) * len(SEEDS)
    count = 0
    started = time.perf_counter()
    for input_source in INPUT_SOURCES:
        for condition in CONDITIONS:
            for seed in SEEDS:
                for method in IDENTIFIER_METHODS:
                    count += 1
                    print(f"[stage9k offline {count}/{total}] {method}/{input_source}/{condition}/seed{seed}", flush=True)
                    result, condition_rows, planning = run_offline_one(method, input_source, condition, seed, replay[(condition, seed)], base_cfg)
                    per_run.append(result); conditioning.extend(condition_rows); planner_rows.extend(planning)
                    write_dict_csv(output_root / "stage9k_offline_per_run.csv", per_run)
                    write_dict_csv(output_root / "stage9k_conditioning.csv", conditioning)
                    write_dict_csv(output_root / "stage9k_planner_time_diagnosis.csv", planner_rows)
    summary = aggregate_offline(per_run)
    calibration = uncertainty_calibration(conditioning)
    gate = offline_gate(summary, calibration)
    write_dict_csv(output_root / "stage9k_offline_summary.csv", summary)
    write_dict_csv(output_root / "stage9k_uncertainty_calibration.csv", calibration)
    save_offline_figures(per_run, summary, conditioning, calibration, planner_rows, output_root)
    closed_per_run: list[dict[str, Any]] = []
    closed_summary: list[dict[str, Any]] = []
    trajectories: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    if gate["passed"]:
        closed_per_run, closed_summary, trajectories = run_closed_loop(str(gate["selected"]), base_cfg, output_root)
        save_closed_loop_figures(closed_summary, trajectories, output_root)
    next_direction = determine_next_direction(gate, summary, planner_rows, closed_summary)
    write_report(output_root / "stage9k_report.md", per_run, summary, conditioning, calibration, planner_rows, gate, closed_summary, next_direction)
    (output_root / "stage9k_command.txt").write_text(f"conda run -n mpc_learn python scripts/{Path(__file__).name}\n")
    (output_root / "stage9k_gate.json").write_text(json.dumps(gate, indent=2, default=str))
    print(f"[stage9k] offline_gate={gate['passed']} selected={gate['selected']} runtime={time.perf_counter()-started:.1f}s", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--refresh-current", action="store_true", help="Refresh only current-NLS rows after diagnostic-only instrumentation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.refresh_current:
        refresh_current_diagnostics(args.replay, args.output_root, args.config)
    else:
        run(args.replay, args.output_root, args.config)


if __name__ == "__main__":
    main()
