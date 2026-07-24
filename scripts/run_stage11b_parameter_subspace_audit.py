"""Stage 11B passive affine parameter-subspace audit (offline only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10a_dynamics_audit import AFFINE_SCALE, column_correlation
from run_spring2d_stage10b_estimator_benchmark import (
    DEFAULT_CONFIG,
    DEFAULT_REPLAY,
    affine_regression_row,
    arrays,
    load_replay,
)
from run_spring2d_stage9j_gap_decomposition import CONDITIONS, SEEDS, stage9j_overrides, write_dict_csv

OUTPUT = ROOT / "results" / "stage11b_parameter_subspace_audit"
OUTPUT_STAGE11C_SMOKE = ROOT / "results" / "local" / "stage11c_state_source_audit_smoke"
OUTPUT_STAGE11C_FORMAL = ROOT / "results" / "stage11c_state_source_audit"
OUTPUT_STAGE11C = OUTPUT_STAGE11C_FORMAL
PARAMETER_ORDER = ("lambda", "kappa", "beta")
PHYSICAL_SCALE = AFFINE_SCALE.copy()
ROW_SQRT_WEIGHTS = np.array([0.6, 0.25])
WINDOW_TRANSITIONS = 70
UPDATE_INTERVAL = 10
DEFAULT_PROFILE_GRID_SIZE = 15
STAGE11C_EXPERIMENT_ID = "stage11c_state_source_audit"
STAGE11C_EXPECTED_RUNS = 24
STAGE11C_EXPECTED_WINDOWS = 710
STAGE11C_PROFILE_NAMES = frozenset({"lambda_1d", "lambda_kappa_2d"})
STAGE11C_REQUIRED_OUTPUTS = (
    "paired_window_metrics.csv",
    "paired_profile_summary.csv",
    "state_source_summary.csv",
    "run_manifest.json",
    "command.txt",
    "mechanical_status.json",
    "resolved_config_snapshot.json",
    "stage11c_report.md",
)
PROFILE_CONFIDENCE = 0.95
PROFILE_MAX_EXPANSIONS = 8
PROFILE_MAX_REFINEMENTS = 4
PROFILE_WIDTH_TOL = 0.01


def weighted_design(H: np.ndarray, y: np.ndarray, sqrt_weights: np.ndarray = ROW_SQRT_WEIGHTS) -> tuple[np.ndarray, np.ndarray]:
    repeated = np.tile(np.asarray(sqrt_weights, dtype=float), len(y) // len(sqrt_weights))
    return H * repeated[:, None], y * repeated


def residual_cost(H: np.ndarray, y: np.ndarray, theta: np.ndarray, sqrt_weights: np.ndarray = ROW_SQRT_WEIGHTS) -> float:
    Hw, yw = weighted_design(H, y, sqrt_weights)
    residual = Hw @ np.asarray(theta, dtype=float) - yw
    return float(residual @ residual)


def weighted_ls_optimum(H: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    Hw, yw = weighted_design(H, y)
    optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0]
    cost = residual_cost(H, y, optimum)
    residual_rms = float(np.sqrt(cost / max(Hw.shape[0], 1)))
    return optimum, cost, residual_rms


def profile_lambda(H: np.ndarray, y: np.ndarray, lambda_grid: np.ndarray) -> list[dict[str, float]]:
    Hw, yw = weighted_design(H, y)
    g, nuisance = Hw[:, 0], Hw[:, 1:]
    rows = []
    for lam in np.asarray(lambda_grid, dtype=float):
        nuisance_hat = np.linalg.lstsq(nuisance, yw - g * lam, rcond=None)[0]
        theta = np.r_[lam, nuisance_hat]
        rows.append({"lambda": float(lam), "kappa_hat": float(theta[1]), "beta_hat": float(theta[2]), "cost": residual_cost(H, y, theta)})
    return rows


def profile_lambda_kappa(H: np.ndarray, y: np.ndarray, lambda_grid: np.ndarray, kappa_grid: np.ndarray) -> list[dict[str, float]]:
    Hw, yw = weighted_design(H, y)
    beta_column = Hw[:, 2]
    denominator = max(float(beta_column @ beta_column), 1.0e-15)
    rows = []
    for lam in np.asarray(lambda_grid, dtype=float):
        for kappa in np.asarray(kappa_grid, dtype=float):
            fixed = Hw[:, :2] @ np.array([lam, kappa])
            beta = float(beta_column @ (yw - fixed) / denominator)
            theta = np.array([lam, kappa, beta])
            rows.append({"lambda": float(lam), "kappa": float(kappa), "beta_hat": beta, "cost": residual_cost(H, y, theta)})
    return rows


def _profile_threshold(minimum_cost: float, residual_dof: int, dimensions: int, weighted_y: np.ndarray) -> float:
    numerical_floor = np.finfo(float).eps * max(float(weighted_y @ weighted_y), 1.0)
    variance = max(float(minimum_cost) / max(residual_dof, 1), numerical_floor)
    return float(minimum_cost + variance * chi2.ppf(PROFILE_CONFIDENCE, dimensions))


def _initial_profile_range(optimum: float, truth: float) -> tuple[float, float]:
    scale = max(abs(float(optimum)), abs(float(truth)), 1.0e-6)
    padding = max(1.5 * abs(float(optimum) - float(truth)), 0.1 * scale, 1.0e-6)
    return min(float(optimum), float(truth)) - padding, max(float(optimum), float(truth)) + padding


def _bisect_profile_boundary(cost_function: Any, inside: float, outside: float, threshold: float) -> tuple[float, int]:
    inside_value, outside_value = float(inside), float(outside)
    assert cost_function(inside_value) <= threshold and cost_function(outside_value) > threshold
    iterations = 0
    for iterations in range(1, 61):
        midpoint = 0.5 * (inside_value + outside_value)
        if cost_function(midpoint) <= threshold:
            inside_value = midpoint
        else:
            outside_value = midpoint
        if abs(outside_value - inside_value) <= 1.0e-8 * max(1.0, abs(midpoint)):
            break
    return 0.5 * (inside_value + outside_value), iterations


def adaptive_profile_lambda(
    H: np.ndarray,
    y: np.ndarray,
    truth_lambda: float,
    grid_size: int = 9,
    max_expansions: int = PROFILE_MAX_EXPANSIONS,
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    optimum, minimum_cost, _ = weighted_ls_optimum(H, y)
    optimum_lambda = float(optimum[0])
    _, weighted_y = weighted_design(H, y)
    threshold = _profile_threshold(minimum_cost, H.shape[0] - H.shape[1], 1, weighted_y)
    cache: dict[float, dict[str, float]] = {}

    def evaluate(value: float) -> dict[str, float]:
        key = float(value)
        if key not in cache:
            cache[key] = profile_lambda(H, y, np.array([key]))[0]
        return cache[key]

    low, high = _initial_profile_range(optimum_lambda, truth_lambda)
    expansions = 0
    boundary_hit = True
    grid_size = max(5, int(grid_size) | 1)
    for expansions in range(max_expansions + 1):
        grid = np.unique(np.r_[np.linspace(low, high, grid_size), optimum_lambda, truth_lambda])
        rows = [evaluate(value) for value in grid]
        left_hit = evaluate(low)["cost"] <= threshold
        right_hit = evaluate(high)["cost"] <= threshold
        boundary_hit = left_hit or right_hit
        if not boundary_hit:
            break
        span = high - low
        if left_hit:
            low -= span
        if right_hit:
            high += span

    left_resolved = evaluate(low)["cost"] > threshold
    right_resolved = evaluate(high)["cost"] > threshold
    left_root, left_iterations = _bisect_profile_boundary(lambda value: evaluate(value)["cost"], optimum_lambda, low, threshold) if left_resolved else (low, 0)
    right_root, right_iterations = _bisect_profile_boundary(lambda value: evaluate(value)["cost"], optimum_lambda, high, threshold) if right_resolved else (high, 0)
    boundary_hit = not (left_resolved and right_resolved)
    evaluate(left_root); evaluate(right_root); evaluate(truth_lambda); evaluate(optimum_lambda)
    rows = sorted(cache.values(), key=lambda row: row["lambda"])
    accepted_count = sum(row["cost"] <= threshold for row in rows)
    truth_cost = evaluate(truth_lambda)["cost"]
    summary = {
        "minimum_cost": minimum_cost,
        "confidence_cost_threshold_95": threshold,
        "lambda_at_minimum": optimum_lambda,
        "truth_profile_cost": truth_cost,
        "truth_in_region_95": bool(truth_cost <= threshold),
        "lambda_region_lower_95": left_root,
        "lambda_region_upper_95": right_root,
        "lambda_region_width_95": right_root - left_root,
        "boundary_hit": bool(boundary_hit),
        "expansion_count": int(expansions),
        "refinement_count": int(max(left_iterations, right_iterations)),
        "accepted_point_count": int(accepted_count),
        "region_resolved": bool(not boundary_hit),
    }
    return summary, rows


def ridge_direction_from_accepted(accepted: list[dict[str, float]]) -> list[float] | None:
    if len(accepted) < 3:
        return None
    accepted_points = np.array([[row["lambda"], row["kappa"]] for row in accepted])
    centered = accepted_points - np.mean(accepted_points, axis=0)
    if np.linalg.matrix_rank(centered) < 1:
        return None
    ridge_vector = np.linalg.svd(centered, full_matrices=False)[2][0]
    return (ridge_vector / np.linalg.norm(ridge_vector)).tolist()


def adaptive_profile_lambda_kappa(
    H: np.ndarray,
    y: np.ndarray,
    truth_lambda_kappa: np.ndarray,
    grid_size: int = 9,
    max_expansions: int = PROFILE_MAX_EXPANSIONS,
    max_refinements: int = PROFILE_MAX_REFINEMENTS,
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    optimum, minimum_cost, _ = weighted_ls_optimum(H, y)
    optimum_pair = np.asarray(optimum[:2], dtype=float)
    truth_pair = np.asarray(truth_lambda_kappa, dtype=float)
    weighted_H, weighted_y = weighted_design(H, y)
    threshold = _profile_threshold(minimum_cost, H.shape[0] - H.shape[1], 2, weighted_y)
    delta_cost = max(threshold - minimum_cost, np.finfo(float).eps)
    beta_column = weighted_H[:, 2:3]
    projected_pair = (np.eye(len(weighted_H)) - beta_column @ np.linalg.pinv(beta_column)) @ weighted_H[:, :2]
    profile_information = projected_pair.T @ projected_pair
    information_eigenvalues = np.linalg.eigvalsh(profile_information)
    locally_bounded = bool(information_eigenvalues[0] > 1.0e-12 * max(information_eigenvalues[-1], 1.0))
    profile_covariance = np.linalg.pinv(profile_information, rcond=1.0e-12)
    local_extent = np.sqrt(np.maximum(delta_cost * np.diag(profile_covariance), 0.0))
    local_extent = np.maximum(local_extent, 1.0e-8 * np.maximum(np.abs(optimum_pair), 1.0))
    lambda_low, lambda_high = _initial_profile_range(optimum_pair[0], truth_pair[0])
    kappa_low, kappa_high = _initial_profile_range(optimum_pair[1], truth_pair[1])
    grid_size = max(5, int(grid_size) | 1)
    expansions = 0
    boundary_hit = True
    cache: dict[tuple[float, float], dict[str, float]] = {}

    def evaluate_grid(lambda_grid: np.ndarray, kappa_grid: np.ndarray) -> list[dict[str, float]]:
        missing_lambda, missing_kappa = [], []
        for lam in np.asarray(lambda_grid, dtype=float):
            for kappa in np.asarray(kappa_grid, dtype=float):
                key = (float(lam), float(kappa))
                if key not in cache:
                    missing_lambda.append(float(lam)); missing_kappa.append(float(kappa))
        for lam, kappa in zip(missing_lambda, missing_kappa):
            cache[(lam, kappa)] = profile_lambda_kappa(H, y, np.array([lam]), np.array([kappa]))[0]
        return [cache[(float(lam), float(kappa))] for lam in np.asarray(lambda_grid, dtype=float) for kappa in np.asarray(kappa_grid, dtype=float)]

    def global_grid(points: int) -> list[dict[str, float]]:
        lambda_grid = np.unique(np.r_[np.linspace(lambda_low, lambda_high, points), optimum_pair[0], truth_pair[0]])
        kappa_grid = np.unique(np.r_[np.linspace(kappa_low, kappa_high, points), optimum_pair[1], truth_pair[1]])
        return evaluate_grid(lambda_grid, kappa_grid)

    for expansions in range(max_expansions + 1):
        rows = global_grid(grid_size)
        accepted = [row for row in rows if row["cost"] <= threshold]
        lambda_tolerance = 1.0e-12 * max(1.0, abs(lambda_low), abs(lambda_high))
        kappa_tolerance = 1.0e-12 * max(1.0, abs(kappa_low), abs(kappa_high))
        hits = {
            "lambda_low": any(abs(row["lambda"] - lambda_low) <= lambda_tolerance for row in accepted),
            "lambda_high": any(abs(row["lambda"] - lambda_high) <= lambda_tolerance for row in accepted),
            "kappa_low": any(abs(row["kappa"] - kappa_low) <= kappa_tolerance for row in accepted),
            "kappa_high": any(abs(row["kappa"] - kappa_high) <= kappa_tolerance for row in accepted),
        }
        boundary_hit = any(hits.values())
        if not boundary_hit:
            break
        lambda_span, kappa_span = lambda_high - lambda_low, kappa_high - kappa_low
        if hits["lambda_low"]: lambda_low -= lambda_span
        if hits["lambda_high"]: lambda_high += lambda_span
        if hits["kappa_low"]: kappa_low -= kappa_span
        if hits["kappa_high"]: kappa_high += kappa_span

    previous_widths: np.ndarray | None = None
    refinement_count = 0
    points = grid_size
    for refinement_count in range(1, max_refinements + 1):
        points = 2 * points - 1
        local_lambda = np.linspace(optimum_pair[0] - 1.25 * local_extent[0], optimum_pair[0] + 1.25 * local_extent[0], points)
        local_kappa = np.linspace(optimum_pair[1] - 1.25 * local_extent[1], optimum_pair[1] + 1.25 * local_extent[1], points)
        evaluate_grid(local_lambda, local_kappa)
        global_grid(grid_size)
        rows = list(cache.values())
        accepted = [row for row in rows if row["cost"] <= threshold]
        if accepted:
            widths = np.array([
                max(row["lambda"] for row in accepted) - min(row["lambda"] for row in accepted),
                max(row["kappa"] for row in accepted) - min(row["kappa"] for row in accepted),
            ])
            if previous_widths is not None:
                relative_change = np.max(np.abs(widths - previous_widths) / np.maximum(np.abs(widths), 1.0e-12))
                if relative_change <= PROFILE_WIDTH_TOL:
                    break
            previous_widths = widths

    rows = list(cache.values())
    accepted = [row for row in rows if row["cost"] <= threshold]
    lambda_tolerance = 1.0e-12 * max(1.0, abs(lambda_low), abs(lambda_high))
    kappa_tolerance = 1.0e-12 * max(1.0, abs(kappa_low), abs(kappa_high))
    boundary_hit = (not locally_bounded) or any(
        abs(row["lambda"] - lambda_low) <= lambda_tolerance
        or abs(row["lambda"] - lambda_high) <= lambda_tolerance
        or abs(row["kappa"] - kappa_low) <= kappa_tolerance
        or abs(row["kappa"] - kappa_high) <= kappa_tolerance
        for row in accepted
    )
    truth_row = profile_lambda_kappa(H, y, np.array([truth_pair[0]]), np.array([truth_pair[1]]))[0]
    lambda_values = [row["lambda"] for row in accepted]
    kappa_values = [row["kappa"] for row in accepted]
    region_resolved = bool(locally_bounded and len(accepted) >= 3 and not boundary_hit)
    ridge = ridge_direction_from_accepted(accepted) if region_resolved else None
    summary = {
        "minimum_cost": minimum_cost,
        "confidence_cost_threshold_95": threshold,
        "lambda_at_minimum": float(optimum_pair[0]),
        "kappa_at_minimum": float(optimum_pair[1]),
        "truth_profile_cost": float(truth_row["cost"]),
        "truth_in_region_95": bool(truth_row["cost"] <= threshold),
        "lambda_region_lower_95": float(min(lambda_values)) if region_resolved else np.nan,
        "lambda_region_upper_95": float(max(lambda_values)) if region_resolved else np.nan,
        "lambda_region_width_95": float(max(lambda_values) - min(lambda_values)) if region_resolved else np.nan,
        "kappa_region_lower_95": float(min(kappa_values)) if region_resolved else np.nan,
        "kappa_region_upper_95": float(max(kappa_values)) if region_resolved else np.nan,
        "kappa_region_width_95": float(max(kappa_values) - min(kappa_values)) if region_resolved else np.nan,
        "ridge_direction_lambda_kappa_json": json.dumps(ridge) if ridge is not None else "undefined",
        "boundary_hit": bool(boundary_hit),
        "expansion_count": int(expansions),
        "refinement_count": int(refinement_count),
        "accepted_point_count": int(len(accepted)),
        "region_resolved": region_resolved,
    }
    return summary, sorted(rows, key=lambda row: (row["lambda"], row["kappa"]))


def svd_metrics(H: np.ndarray, y: np.ndarray | None = None) -> dict[str, Any]:
    Hw, yw = weighted_design(H, np.zeros(H.shape[0]) if y is None else y)
    column_scale = np.maximum(np.linalg.norm(Hw, axis=0), 1.0e-15)
    normalized = Hw / column_scale
    _, singular, vt = np.linalg.svd(normalized, full_matrices=False)
    assert np.allclose(normalized, np.linalg.svd(normalized, full_matrices=False)[0] @ np.diag(singular) @ vt)
    normalized_directions = vt / np.linalg.norm(vt, axis=1, keepdims=True)
    physical_directions = normalized_directions / column_scale[None, :]
    physical_directions /= np.linalg.norm(physical_directions, axis=1, keepdims=True)
    raw_singular = np.linalg.svd(H, compute_uv=False)
    physical_scaled_singular = np.linalg.svd(H @ np.diag(PHYSICAL_SCALE), compute_uv=False)
    weighted_physical_scaled_singular = np.linalg.svd(Hw @ np.diag(PHYSICAL_SCALE), compute_uv=False)
    g, B = Hw[:, 0], Hw[:, 1:]
    projection = np.eye(len(g)) - B @ np.linalg.pinv(B, rcond=1.0e-12)
    information_abs = max(float(g @ projection @ g), 0.0)
    information_ratio = information_abs / max(float(g @ g), 1.0e-15)
    correlation = column_correlation(Hw)
    if y is None:
        residual_rms = np.nan
        absolute_sensitivity_to_residual = np.nan
    else:
        weighted_optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0]
        weighted_residual = Hw @ weighted_optimum - yw
        residual_rms = float(np.sqrt(np.mean(weighted_residual**2)))
        absolute_sensitivity_to_residual = float(weighted_physical_scaled_singular[-1] / max(residual_rms, 1.0e-15))
    return {
        "rank": int(np.linalg.matrix_rank(Hw)),
        "raw_condition_number_H": float(raw_singular[0] / max(raw_singular[-1], 1.0e-15)),
        "physical_scale_condition_number_HS": float(physical_scaled_singular[0] / max(physical_scaled_singular[-1], 1.0e-15)),
        "column_normalized_geometric_condition_number": float(singular[0] / max(singular[-1], 1.0e-15)),
        "physical_scaled_weighted_singular_values": weighted_physical_scaled_singular,
        "weighted_residual_rms": residual_rms,
        "physical_scaled_sigma_min_over_residual_rms": absolute_sensitivity_to_residual,
        "column_normalized_singular_values": singular,
        "normalized_right_singular_directions": normalized_directions,
        "physical_right_singular_directions": physical_directions,
        "normalized_weak_direction": normalized_directions[-1],
        "physical_weak_direction": physical_directions[-1],
        "conditional_lambda_information_abs": information_abs,
        "conditional_lambda_information_ratio": information_ratio,
        "correlation": correlation,
    }


def aggregate_directions(directions: np.ndarray) -> dict[str, Any]:
    unit = np.asarray(directions, dtype=float)
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    projector = np.mean([np.outer(v, v) for v in unit], axis=0)
    eigenvalues, eigenvectors = np.linalg.eigh(projector)
    direction = eigenvectors[:, -1]
    angles = np.degrees(np.arccos(np.clip(np.abs(unit @ direction), 0.0, 1.0)))
    return {
        "direction": direction,
        "projector_eigenvalues": eigenvalues,
        "angular_dispersion_mean_deg": float(np.mean(angles)),
        "angular_dispersion_p95_deg": float(np.percentile(angles, 95)),
        "stability_concentration": float(eigenvalues[-1] / max(np.sum(eigenvalues), 1.0e-15)),
    }


def aggregate_subspaces(bases: np.ndarray, dimension: int) -> dict[str, Any]:
    orthonormal = []
    for basis in np.asarray(bases, dtype=float):
        q, _ = np.linalg.qr(np.asarray(basis, dtype=float).T)
        orthonormal.append(q[:, :dimension])
    projector = np.mean([q @ q.T for q in orthonormal], axis=0)
    eigenvalues, eigenvectors = np.linalg.eigh(projector)
    order = np.argsort(eigenvalues)[::-1]
    consensus = eigenvectors[:, order[:dimension]]
    angles = []
    for q in orthonormal:
        singular = np.linalg.svd(q.T @ consensus, compute_uv=False)
        angles.append(float(np.degrees(np.arccos(np.clip(np.min(singular), 0.0, 1.0)))))
    return {
        "basis": consensus.T,
        "projector_eigenvalues": eigenvalues,
        "angular_dispersion_mean_deg": float(np.mean(angles)),
        "angular_dispersion_p95_deg": float(np.percentile(angles, 95)),
        "stability_concentration": float(np.sum(eigenvalues[order[:dimension]]) / dimension),
    }


def verify_truth_metadata(condition: str, data: dict[str, np.ndarray], config: dict[str, Any]) -> None:
    override = stage9j_overrides(config, condition)
    replay_truth = np.asarray(data["true_params"], dtype=float)
    configured_truth = np.array([override["true_params"][name] for name in ("m", "k", "b_r")], dtype=float)
    nominal = np.asarray(data["nominal_params"], dtype=float)
    if not np.all(np.isfinite(replay_truth)) or np.any(replay_truth <= 0.0):
        raise RuntimeError(f"{condition}: replay true_params are non-finite or non-physical")
    if not np.allclose(replay_truth, configured_truth, rtol=0.0, atol=1.0e-12):
        raise RuntimeError(f"{condition}: replay true_params do not match the Stage 9J plant configuration")
    required_difference = {"mass_mismatch": 0, "parameter_mismatch_low_k": 1, "parameter_mismatch_high_k": 1}
    if condition in required_difference and np.isclose(replay_truth[required_difference[condition]], nominal[required_difference[condition]]):
        raise RuntimeError(f"{condition}: replay truth metadata is nominal or ambiguous for the mismatched parameter")


def build_affine_window(
    condition: str,
    seed: int,
    data: dict[str, np.ndarray],
    model_params: dict[str, Any],
    end: int,
    state_source: str = "estimated",
) -> tuple[np.ndarray, np.ndarray, int]:
    if state_source not in {"estimated", "true"}:
        raise ValueError(f"state_source must be estimated or true, got {state_source!r}")
    if end < WINDOW_TRANSITIONS:
        raise ValueError(f"{condition}/{seed}: end={end} cannot form a {WINDOW_TRANSITIONS}-transition window")
    start = end - WINDOW_TRANSITIONS + 1
    states = np.asarray(data[state_source], dtype=float)
    H_blocks, y_blocks = [], []
    for step in range(start, end + 1):
        H, y = affine_regression_row(states[step - 1], data["action"][step], states[step], model_params)
        assert H.shape == (2, 3) and y.shape == (2,)
        H_blocks.append(H)
        y_blocks.append(y)
    H = np.vstack(H_blocks)
    y = np.hstack(y_blocks)
    assert H.shape[1] == len(PARAMETER_ORDER)
    assert len(H_blocks) == WINDOW_TRANSITIONS
    assert np.all(np.isfinite(H)) and np.all(np.isfinite(y))
    return H, y, start


def analyze_window(
    condition: str,
    seed: int,
    data: dict[str, np.ndarray],
    model_params: dict[str, Any],
    end: int,
    grid_size: int,
    state_source: str = "estimated",
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    H, y, start = build_affine_window(condition, seed, data, model_params, end, state_source)
    diagnostic = svd_metrics(H, y)
    truth = np.array([1.0 / data["true_params"][0], data["true_params"][1] / data["true_params"][0], data["true_params"][2] / data["true_params"][0]])
    one_summary, one_grid = adaptive_profile_lambda(H, y, truth[0], grid_size)
    two_summary, two_grid = adaptive_profile_lambda_kappa(H, y, truth[:2], grid_size)
    base = {"condition": condition, "seed": seed, "window_start": start, "window_end": end, "state_source": state_source}
    window = {
        **base,
        "transitions": end - start + 1,
        "rank": diagnostic["rank"],
        "raw_condition_number_H": diagnostic["raw_condition_number_H"],
        "physical_scale_condition_number_HS": diagnostic["physical_scale_condition_number_HS"],
        "column_normalized_geometric_condition_number": diagnostic["column_normalized_geometric_condition_number"],
        "column_normalized_singular_values_json": json.dumps(diagnostic["column_normalized_singular_values"].tolist()),
        "physical_scaled_weighted_singular_values_json": json.dumps(diagnostic["physical_scaled_weighted_singular_values"].tolist()),
        "weighted_residual_rms": diagnostic["weighted_residual_rms"],
        "physical_scaled_sigma_min_over_residual_rms": diagnostic["physical_scaled_sigma_min_over_residual_rms"],
        "normalized_right_singular_directions_json": json.dumps(diagnostic["normalized_right_singular_directions"].tolist()),
        "physical_right_singular_directions_json": json.dumps(diagnostic["physical_right_singular_directions"].tolist()),
        "normalized_weak_direction_json": json.dumps(diagnostic["normalized_weak_direction"].tolist()),
        "physical_weak_direction_json": json.dumps(diagnostic["physical_weak_direction"].tolist()),
        "conditional_lambda_information_abs": diagnostic["conditional_lambda_information_abs"],
        "conditional_lambda_information_ratio": diagnostic["conditional_lambda_information_ratio"],
        "corr_lambda_kappa": float(diagnostic["correlation"][0, 1]),
        "corr_lambda_beta": float(diagnostic["correlation"][0, 2]),
        "corr_kappa_beta": float(diagnostic["correlation"][1, 2]),
        "truth_lambda": truth[0], "truth_kappa": truth[1], "truth_beta": truth[2],
    }
    profile_truth = {"truth_lambda": truth[0], "truth_kappa": truth[1], "truth_beta": truth[2]}
    profile_rows = [
        {**base, **profile_truth, "profile": "lambda_1d", **one_summary},
        {**base, **profile_truth, "profile": "lambda_kappa_2d", **two_summary},
    ]
    raw_grid = [{**base, "profile": "lambda_1d", **row} for row in one_grid] + [{**base, "profile": "lambda_kappa_2d", **row} for row in two_grid]
    return window, profile_rows, raw_grid


def _direction_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=float) / np.linalg.norm(first)
    second = np.asarray(second, dtype=float) / np.linalg.norm(second)
    return float(np.degrees(np.arccos(np.clip(abs(float(first @ second)), 0.0, 1.0))))


def _subspace_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    first_q, _ = np.linalg.qr(np.asarray(first, dtype=float).T)
    second_q, _ = np.linalg.qr(np.asarray(second, dtype=float).T)
    singular = np.linalg.svd(first_q[:, :2].T @ second_q[:, :2], compute_uv=False)
    return float(np.degrees(np.arccos(np.clip(np.min(singular), 0.0, 1.0))))


def pair_window_rows(estimated: dict[str, Any], true: dict[str, Any]) -> dict[str, Any]:
    identity = ("condition", "seed", "window_start", "window_end", "transitions")
    if any(estimated[key] != true[key] for key in identity):
        raise AssertionError("estimated and true windows are not aligned")
    estimated_v = np.asarray(json.loads(estimated["physical_right_singular_directions_json"]), dtype=float)
    true_v = np.asarray(json.loads(true["physical_right_singular_directions_json"]), dtype=float)
    metrics = (
        "weighted_residual_rms",
        "physical_scale_condition_number_HS",
        "conditional_lambda_information_abs",
        "conditional_lambda_information_ratio",
    )
    row = {key: estimated[key] for key in identity}
    for source, source_row in (("estimated", estimated), ("true", true)):
        for key, value in source_row.items():
            if key not in identity and key != "state_source":
                row[f"{source}_{key}"] = value
    for metric in metrics:
        estimate, oracle = float(estimated[metric]), float(true[metric])
        row[f"estimated_{metric}"] = estimate
        row[f"true_{metric}"] = oracle
        row[f"true_minus_estimated_{metric}"] = oracle - estimate
    row["v1_estimated_true_angle_deg"] = _direction_angle_deg(estimated_v[0], true_v[0])
    row["v12_estimated_true_principal_angle_deg"] = _subspace_angle_deg(estimated_v[:2], true_v[:2])
    return row


def _relative_optimum_error(profile: dict[str, Any], parameter: str) -> float:
    truth_key = f"truth_{parameter}"
    if truth_key not in profile:
        raise KeyError(f"missing {truth_key} in profile row")
    return abs(float(profile[f"{parameter}_at_minimum"]) - float(profile[truth_key])) / max(abs(float(profile[truth_key])), 1.0e-12)


def pair_profile_rows(estimated_profiles: list[dict[str, Any]], true_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identity = ("condition", "seed", "window_start", "window_end", "profile")
    estimated_by_key = {tuple(row[key] for key in identity): row for row in estimated_profiles}
    true_by_key = {tuple(row[key] for key in identity): row for row in true_profiles}
    if set(estimated_by_key) != set(true_by_key):
        raise AssertionError("estimated and true profile rows are not aligned")
    paired = []
    for key in sorted(estimated_by_key):
        estimated, true = estimated_by_key[key], true_by_key[key]
        row = dict(zip(identity, key))
        for source, source_row in (("estimated", estimated), ("true", true)):
            for field, value in source_row.items():
                if field not in identity and field != "state_source":
                    row[f"{source}_{field}"] = value
        for metric in ("truth_in_region_95", "truth_profile_cost", "lambda_region_width_95", "boundary_hit", "region_resolved"):
            estimate, oracle = estimated[metric], true[metric]
            row[f"estimated_{metric}"] = estimate
            row[f"true_{metric}"] = oracle
            if metric == "truth_in_region_95":
                row["true_minus_estimated_truth_inclusion"] = int(bool(oracle)) - int(bool(estimate))
            elif metric not in {"boundary_hit", "region_resolved"}:
                row[f"true_minus_estimated_{metric}"] = float(oracle) - float(estimate)
        row["estimated_lambda_optimum_relative_error"] = _relative_optimum_error(estimated, "lambda")
        row["true_lambda_optimum_relative_error"] = _relative_optimum_error(true, "lambda")
        row["true_minus_estimated_lambda_optimum_relative_error"] = row["true_lambda_optimum_relative_error"] - row["estimated_lambda_optimum_relative_error"]
        row["estimated_lambda_relative_width"] = float(estimated["lambda_region_width_95"]) / max(abs(float(estimated["lambda_at_minimum"])), 1.0e-12)
        row["true_lambda_relative_width"] = float(true["lambda_region_width_95"]) / max(abs(float(true["lambda_at_minimum"])), 1.0e-12)
        row["true_minus_estimated_lambda_relative_width"] = row["true_lambda_relative_width"] - row["estimated_lambda_relative_width"]
        if row["profile"] == "lambda_kappa_2d":
            for source, profile in (("estimated", estimated), ("true", true)):
                row[f"{source}_kappa_optimum_relative_error"] = _relative_optimum_error(profile, "kappa")
                row[f"{source}_kappa_relative_width"] = float(profile["kappa_region_width_95"]) / max(abs(float(profile["kappa_at_minimum"])), 1.0e-12)
            row["true_minus_estimated_kappa_optimum_relative_error"] = row["true_kappa_optimum_relative_error"] - row["estimated_kappa_optimum_relative_error"]
            row["true_minus_estimated_kappa_relative_width"] = row["true_kappa_relative_width"] - row["estimated_kappa_relative_width"]
        paired.append(row)
    return paired


def restore_paired_source_rows(paired_rows: list[dict[str, str]], state_source: str, profile: bool = False) -> list[dict[str, Any]]:
    identity = ("condition", "seed", "window_start", "window_end", "profile") if profile else ("condition", "seed", "window_start", "window_end", "transitions")
    prefix = f"{state_source}_"
    restored = []
    for paired in paired_rows:
        row: dict[str, Any] = {key: paired[key] for key in identity}
        for key, value in paired.items():
            if key.startswith(prefix):
                row[key[len(prefix):]] = value
        row["state_source"] = state_source
        restored.append(row)
    return restored


def summarize_windows(rows: list[dict[str, Any]], profile_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scopes = [("overall", rows)] + [(condition, [row for row in rows if row["condition"] == condition]) for condition in sorted({row["condition"] for row in rows})]
    condition_names = sorted({str(row["condition"]) for row in rows})
    condition_v1, condition_v12 = [], []
    for condition in condition_names:
        matrices = np.array([json.loads(row["physical_right_singular_directions_json"]) for row in rows if row["condition"] == condition])
        condition_v1.append(aggregate_directions(matrices[:, 0, :])["direction"])
        condition_v12.append(aggregate_subspaces(matrices[:, :2, :], 2)["basis"])
    cross_condition_v1 = aggregate_directions(np.asarray(condition_v1))
    cross_condition_v12 = aggregate_subspaces(np.asarray(condition_v12), 2)
    cross_stable_1d = cross_condition_v1["stability_concentration"] >= 0.8 and cross_condition_v1["angular_dispersion_p95_deg"] <= 20.0
    cross_stable_2d = cross_condition_v12["stability_concentration"] >= 0.8 and cross_condition_v12["angular_dispersion_p95_deg"] <= 20.0
    condition_rows, subspace_rows = [], []
    for scope, group in scopes:
        direction_matrices = np.array([json.loads(row["physical_right_singular_directions_json"]) for row in group])
        aggregates = [aggregate_directions(direction_matrices[:, index, :]) for index in range(3)]
        aggregate_v12 = aggregate_subspaces(direction_matrices[:, :2, :], 2)
        singular_values = np.array([json.loads(row["column_normalized_singular_values_json"]) for row in group])
        physical_singular_values = np.array([json.loads(row["physical_scaled_weighted_singular_values_json"]) for row in group])
        rank_fraction = {dimension: float(np.mean([int(row["rank"]) >= dimension for row in group])) for dimension in (1, 2, 3)}
        profiles = profile_rows if scope == "overall" else [row for row in profile_rows if row["condition"] == scope]
        one_profiles = [row for row in profiles if row["profile"] == "lambda_1d"]
        two_profiles = [row for row in profiles if row["profile"] == "lambda_kappa_2d"]
        lambda_relative_width = float(np.nanmedian([float(row["lambda_region_width_95"]) / max(abs(float(row["lambda_at_minimum"])), 1.0e-12) for row in one_profiles]))
        two_lambda_relative_width = float(np.nanmedian([float(row["lambda_region_width_95"]) / max(abs(float(row["lambda_at_minimum"])), 1.0e-12) for row in two_profiles]))
        two_kappa_relative_width = float(np.nanmedian([float(row["kappa_region_width_95"]) / max(abs(float(row["kappa_at_minimum"])), 1.0e-12) for row in two_profiles]))
        truth_inclusion_1d = float(np.mean([str(row["truth_in_region_95"]).lower() in {"true", "1"} for row in one_profiles]))
        truth_inclusion_2d = float(np.mean([str(row["truth_in_region_95"]).lower() in {"true", "1"} for row in two_profiles]))
        boundary_fraction = float(np.mean([str(row["boundary_hit"]).lower() in {"true", "1"} for row in profiles]))
        resolved_fraction = float(np.mean([str(row["region_resolved"]).lower() in {"true", "1"} for row in profiles]))
        within_stable_1d = aggregates[0]["stability_concentration"] >= 0.8 and aggregates[0]["angular_dispersion_p95_deg"] <= 20.0
        within_stable_2d = aggregate_v12["stability_concentration"] >= 0.8 and aggregate_v12["angular_dispersion_p95_deg"] <= 20.0
        sensitivity_ratio = float(np.median([float(row["physical_scaled_sigma_min_over_residual_rms"]) for row in group]))
        physical_condition = float(np.median([float(row["physical_scale_condition_number_HS"]) for row in group]))
        profile_evidence = boundary_fraction <= 0.05 and resolved_fraction >= 0.95 and truth_inclusion_1d >= 0.8 and truth_inclusion_2d >= 0.8
        sensitivity_evidence = sensitivity_ratio >= 1.0 and physical_condition <= 100.0
        practical_status = "established" if profile_evidence and sensitivity_evidence and (within_stable_1d or within_stable_2d) else "not established"
        common = {
            "scope": scope, "windows": len(group),
            "rank1_fraction": rank_fraction[1], "rank2_fraction": rank_fraction[2], "rank3_fraction": rank_fraction[3],
            "normalized_sigma1_median": float(np.median(singular_values[:, 0])),
            "normalized_sigma2_median": float(np.median(singular_values[:, 1])),
            "normalized_sigma3_median": float(np.median(singular_values[:, 2])),
            "physical_scaled_sigma1_median": float(np.median(physical_singular_values[:, 0])),
            "physical_scaled_sigma2_median": float(np.median(physical_singular_values[:, 1])),
            "physical_scaled_sigma3_median": float(np.median(physical_singular_values[:, 2])),
            "raw_condition_median": float(np.median([row["raw_condition_number_H"] for row in group])),
            "physical_scale_condition_median": physical_condition,
            "column_normalized_condition_median": float(np.median([row["column_normalized_geometric_condition_number"] for row in group])),
            "weighted_residual_rms_median": float(np.median([float(row["weighted_residual_rms"]) for row in group])),
            "physical_scaled_sigma_min_over_residual_rms_median": sensitivity_ratio,
            "conditional_lambda_information_abs_median": float(np.median([row["conditional_lambda_information_abs"] for row in group])),
            "conditional_lambda_information_ratio_median": float(np.median([row["conditional_lambda_information_ratio"] for row in group])),
            "abs_corr_lambda_kappa_median": float(np.median([abs(float(row["corr_lambda_kappa"])) for row in group])),
            "abs_corr_lambda_beta_median": float(np.median([abs(float(row["corr_lambda_beta"])) for row in group])),
            "abs_corr_kappa_beta_median": float(np.median([abs(float(row["corr_kappa_beta"])) for row in group])),
            "lambda_1d_relative_width_median": lambda_relative_width,
            "lambda_kappa_2d_lambda_relative_width_median": two_lambda_relative_width,
            "lambda_kappa_2d_kappa_relative_width_median": two_kappa_relative_width,
            "profile_truth_inclusion_1d_fraction": truth_inclusion_1d,
            "profile_truth_inclusion_2d_fraction": truth_inclusion_2d,
            "profile_boundary_hit_fraction": boundary_fraction,
            "profile_region_resolved_fraction": resolved_fraction,
            "within_scope_stable_1d_subspace": within_stable_1d,
            "within_scope_stable_2d_subspace": within_stable_2d,
            "practical_identifiability": practical_status,
        }
        condition_rows.append(common)
        subspace_rows.append({
            **common,
            **{
                f"physical_v{index + 1}_{field}": value
                for index, aggregate in enumerate(aggregates)
                for field, value in {
                    "direction_json": json.dumps(aggregate["direction"].tolist()),
                    "projector_eigenvalues_json": json.dumps(aggregate["projector_eigenvalues"].tolist()),
                    "angular_dispersion_mean_deg": aggregate["angular_dispersion_mean_deg"],
                    "angular_dispersion_p95_deg": aggregate["angular_dispersion_p95_deg"],
                    "stability_concentration": aggregate["stability_concentration"],
                }.items()
            },
            "physical_v12_basis_json": json.dumps(aggregate_v12["basis"].tolist()),
            "physical_v12_projector_eigenvalues_json": json.dumps(aggregate_v12["projector_eigenvalues"].tolist()),
            "physical_v12_angular_dispersion_mean_deg": aggregate_v12["angular_dispersion_mean_deg"],
            "physical_v12_angular_dispersion_p95_deg": aggregate_v12["angular_dispersion_p95_deg"],
            "physical_v12_stability_concentration": aggregate_v12["stability_concentration"],
            "cross_condition_v1_direction_json": json.dumps(cross_condition_v1["direction"].tolist()),
            "cross_condition_v1_angular_dispersion_p95_deg": cross_condition_v1["angular_dispersion_p95_deg"],
            "cross_condition_v1_stability_concentration": cross_condition_v1["stability_concentration"],
            "cross_condition_v12_basis_json": json.dumps(cross_condition_v12["basis"].tolist()),
            "cross_condition_v12_angular_dispersion_p95_deg": cross_condition_v12["angular_dispersion_p95_deg"],
            "cross_condition_v12_stability_concentration": cross_condition_v12["stability_concentration"],
            "cross_condition_stable_1d_subspace": cross_stable_1d,
            "cross_condition_stable_2d_subspace": cross_stable_2d,
        })
    return condition_rows, subspace_rows


def _as_bool(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).lower() in {"true", "1"}


def summarize_state_sources(
    estimated_windows: list[dict[str, Any]],
    estimated_profiles: list[dict[str, Any]],
    true_windows: list[dict[str, Any]],
    true_profiles: list[dict[str, Any]],
    paired_windows: list[dict[str, Any]],
    paired_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    source_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for source, windows, profiles in (("estimated", estimated_windows, estimated_profiles), ("true", true_windows, true_profiles)):
        _, subspace = summarize_windows(windows, profiles)
        source_maps[source] = {str(row["scope"]): row for row in subspace}
        summaries.extend([{**row, "state_source": source, "summary_kind": "state_source"} for row in subspace])
    scopes = ["overall"] + sorted({str(row["condition"]) for row in paired_windows})
    for scope in scopes:
        windows = paired_windows if scope == "overall" else [row for row in paired_windows if row["condition"] == scope]
        profiles = paired_profiles if scope == "overall" else [row for row in paired_profiles if row["condition"] == scope]
        one_profiles = [row for row in profiles if row["profile"] == "lambda_1d"]
        two_profiles = [row for row in profiles if row["profile"] == "lambda_kappa_2d"]
        estimated_summary, true_summary = source_maps["estimated"][scope], source_maps["true"][scope]
        summaries.append({
            "scope": scope,
            "state_source": "paired",
            "summary_kind": "paired_difference",
            "windows": len(windows),
            "true_minus_estimated_residual_rms_median": float(np.median([row["true_minus_estimated_weighted_residual_rms"] for row in windows])),
            "true_minus_estimated_physical_condition_median": float(np.median([row["true_minus_estimated_physical_scale_condition_number_HS"] for row in windows])),
            "true_minus_estimated_conditional_lambda_information_abs_median": float(np.median([row["true_minus_estimated_conditional_lambda_information_abs"] for row in windows])),
            "true_minus_estimated_conditional_lambda_information_ratio_median": float(np.median([row["true_minus_estimated_conditional_lambda_information_ratio"] for row in windows])),
            "true_minus_estimated_v1_angle_median_deg": float(np.median([row["v1_estimated_true_angle_deg"] for row in windows])),
            "true_minus_estimated_v12_principal_angle_median_deg": float(np.median([row["v12_estimated_true_principal_angle_deg"] for row in windows])),
            "true_minus_estimated_truth_inclusion_1d": float(np.mean([row["true_minus_estimated_truth_inclusion"] for row in one_profiles])),
            "true_minus_estimated_truth_inclusion_2d": float(np.mean([row["true_minus_estimated_truth_inclusion"] for row in two_profiles])),
            "true_minus_estimated_lambda_optimum_error_median": float(np.median([row["true_minus_estimated_lambda_optimum_relative_error"] for row in profiles])),
            "true_minus_estimated_lambda_width_median": float(np.nanmedian([row["true_minus_estimated_lambda_relative_width"] for row in profiles])),
            "estimated_v1_stability_concentration": estimated_summary["physical_v1_stability_concentration"],
            "true_v1_stability_concentration": true_summary["physical_v1_stability_concentration"],
            "true_minus_estimated_v1_stability_concentration": float(true_summary["physical_v1_stability_concentration"] - estimated_summary["physical_v1_stability_concentration"]),
            "estimated_v12_stability_concentration": estimated_summary["physical_v12_stability_concentration"],
            "true_v12_stability_concentration": true_summary["physical_v12_stability_concentration"],
            "true_minus_estimated_v12_stability_concentration": float(true_summary["physical_v12_stability_concentration"] - estimated_summary["physical_v12_stability_concentration"]),
            "estimated_cross_condition_stable_1d": estimated_summary["cross_condition_stable_1d_subspace"],
            "true_cross_condition_stable_1d": true_summary["cross_condition_stable_1d_subspace"],
            "estimated_cross_condition_stable_2d": estimated_summary["cross_condition_stable_2d_subspace"],
            "true_cross_condition_stable_2d": true_summary["cross_condition_stable_2d_subspace"],
        })
    return summaries


def write_stage11c_report(
    manifest: dict[str, Any],
    state_source_summary: list[dict[str, Any]],
    paired_profiles: list[dict[str, Any]],
    output_root: Path | None = None,
) -> None:
    output_root = OUTPUT_STAGE11C if output_root is None else Path(output_root)
    execution_mode = str(manifest.get("execution_mode", manifest.get("mode", "unknown")))
    smoke = execution_mode == "smoke"
    paired = next(row for row in state_source_summary if row["state_source"] == "paired" and row["scope"] == "overall") if manifest["state_source"] == "paired" else None
    source_overall = {
        str(row["state_source"]): row
        for row in state_source_summary
        if row["scope"] == "overall" and row["state_source"] in {"estimated", "true"}
    }
    lines = [
        "# Stage 11C: Estimated-State vs True-State Paired Subspace Audit", "", "## Dataset coverage", "",
        f"- Mode: `{execution_mode}`; state source: `{manifest['state_source']}`; runs={manifest.get('actual_runs', manifest.get('runs'))}; windows={manifest.get('actual_windows', manifest.get('windows'))}; transitions/window={WINDOW_TRANSITIONS}.",
        f"- Mechanical status: `{manifest.get('mechanical_status', 'not_recorded')}`.",
        "- Both sources use identical actions, window ends, weights, parameterization, adaptive profiles, and SVD/subspace diagnostics.", "",
    ]
    if smoke:
        lines += ["## Smoke-test status", "", "This is implementation validation only. Paired scientific conclusions are intentionally withheld until a full paired result exists.", ""]
    else:
        lines += [
            "## Scientific interpretation", "",
            "Scientific interpretation is pending review against the approved Experiment Spec.",
            "This report presents observed metrics only and does not assign scientific PASS, FAIL, or INCONCLUSIVE.", "",
        ]
    lines += ["## State-source metrics", ""]
    for source in ("estimated", "true"):
        if source not in source_overall:
            continue
        row = source_overall[source]
        lines.append(
            f"- `{source}`: practical identifiability={row['practical_identifiability']}; "
            f"1D/2D truth inclusion=({float(row['profile_truth_inclusion_1d_fraction']):.3f}, "
            f"{float(row['profile_truth_inclusion_2d_fraction']):.3f}); "
            f"1D/2D stable=({row['cross_condition_stable_1d_subspace']}, "
            f"{row['cross_condition_stable_2d_subspace']})."
        )
    lines += ["## Paired differences", ""]
    if paired is not None:
        lines += [
            f"- True minus estimated truth inclusion: 1D={paired['true_minus_estimated_truth_inclusion_1d']:.3f}; 2D={paired['true_minus_estimated_truth_inclusion_2d']:.3f}.",
            f"- Median true-minus-estimated residual RMS={paired['true_minus_estimated_residual_rms_median']:.3g}; physical-scale condition={paired['true_minus_estimated_physical_condition_median']:.3g}; conditional lambda information ratio change={paired['true_minus_estimated_conditional_lambda_information_ratio_median']:.3g}.",
            f"- Median estimated-vs-true direction angle: 1D={paired['true_minus_estimated_v1_angle_median_deg']:.2f} deg; 2D principal angle={paired['true_minus_estimated_v12_principal_angle_median_deg']:.2f} deg.",
            f"- Direction concentration change: v1={paired['true_minus_estimated_v1_stability_concentration']:.3g}; v12={paired['true_minus_estimated_v12_stability_concentration']:.3g}.",
        ]
    lines += ["", "## Limitations", "", "- Passive rehabilitation trajectories only; no active excitation.", "- True-state regression is an oracle diagnostic, not an implementable online estimator."]
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "stage11c_report.md").write_text("\n".join(lines) + "\n")


def identifiability_conclusion(overall: dict[str, Any]) -> str:
    valid_profiles = (
        float(overall["profile_boundary_hit_fraction"]) <= 0.05
        and float(overall["profile_region_resolved_fraction"]) >= 0.95
        and float(overall["profile_truth_inclusion_1d_fraction"]) >= 0.8
        and float(overall["profile_truth_inclusion_2d_fraction"]) >= 0.8
    )
    sensitivity_supported = (
        float(overall["physical_scaled_sigma_min_over_residual_rms_median"]) >= 1.0
        and float(overall["physical_scale_condition_median"]) <= 100.0
    )
    v1 = np.asarray(json.loads(str(overall["cross_condition_v1_direction_json"])), dtype=float)
    v12 = np.asarray(json.loads(str(overall["cross_condition_v12_basis_json"])), dtype=float)
    lambda_alignment = abs(float(v1[0]))
    coordinate_plane = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    plane_alignment = float(np.min(np.linalg.svd(v12 @ coordinate_plane.T, compute_uv=False)))
    if (
        valid_profiles and sensitivity_supported and bool(overall["cross_condition_stable_1d_subspace"])
        and lambda_alignment >= np.cos(np.deg2rad(20.0))
        and float(overall["lambda_1d_relative_width_median"]) <= 0.5
    ):
        return "lambda-only supported"
    if (
        valid_profiles and sensitivity_supported and bool(overall["cross_condition_stable_2d_subspace"])
        and plane_alignment >= np.cos(np.deg2rad(20.0))
        and float(overall["lambda_kappa_2d_lambda_relative_width_median"]) <= 0.5
        and float(overall["lambda_kappa_2d_kappa_relative_width_median"]) <= 0.5
    ):
        return "[lambda,kappa] supported"
    if valid_profiles and sensitivity_supported and bool(overall["cross_condition_stable_1d_subspace"]):
        return "only a stable parameter combination supported"
    return "no stable passive parameter subspace established"


def write_report(manifest: dict[str, Any], condition_rows: list[dict[str, Any]], subspace_rows: list[dict[str, Any]], profile_rows: list[dict[str, Any]]) -> None:
    smoke = manifest["mode"] == "smoke"
    overall = next(row for row in subspace_rows if row["scope"] == "overall")
    lines = [
        "# Stage 11B: Passive Parameter-Subspace Audit", "", "## Dataset coverage", "",
        f"- Mode: `{manifest['mode']}`; runs={manifest['runs']}, windows={manifest['windows']}, transitions/window={WINDOW_TRANSITIONS}.",
        f"- Adaptive profiles: initial grid={manifest['profile_grid_size']} points per dimension, with automatic boundary expansion and local refinement.",
        "- Parameter order: `[lambda, kappa, beta]`.", "", "## Mathematical conventions", "",
        "- Profile cost is the complete weighted residual sum of squares; nuisance parameters are least-squares profiled at every grid point.",
        "- Numerical rank, practical conditioning, and direction stability are reported separately.",
        "- Normalized and physical-coordinate SVD directions are distinct; physical directions use division by the column norms.", "",
    ]
    if smoke:
        lines += ["## Smoke-test status", "", "These outputs validate implementation only. No scientific conclusion is drawn from one condition/run and at most three windows.", ""]
    else:
        conclusion = identifiability_conclusion(overall)
        lines += [
            "## Full-audit interpretation", "",
            f"Required conclusion: **{conclusion}**.",
            f"Numerical rank-3 fraction is {overall['rank3_fraction']:.3f}, while practical identifiability is `{overall['practical_identifiability']}` under the combined physical-scale, profile, absolute-sensitivity, and direction-stability checks.",
            f"Across-condition stability: 1D={overall['cross_condition_stable_1d_subspace']} (concentration={overall['cross_condition_v1_stability_concentration']:.3f}, angular p95={overall['cross_condition_v1_angular_dispersion_p95_deg']:.2f} deg); 2D={overall['cross_condition_stable_2d_subspace']} (concentration={overall['cross_condition_v12_stability_concentration']:.3f}, angular p95={overall['cross_condition_v12_angular_dispersion_p95_deg']:.2f} deg).", "",
        ]
    lines += ["## Condition summaries", ""]
    for row in condition_rows:
        lines.append(f"- `{row['scope']}`: windows={row['windows']}, rank3={row['rank3_fraction']:.3f}, physical-scale cond={row['physical_scale_condition_median']:.3g}, sigma_min/residual={row['physical_scaled_sigma_min_over_residual_rms_median']:.3g}, conditional lambda abs/ratio=({row['conditional_lambda_information_abs_median']:.3g}, {row['conditional_lambda_information_ratio_median']:.3g}), practical={row['practical_identifiability']}.")
    lines += [
        "", "## Profile statistics", "",
        f"Profile summaries contain {len(profile_rows)} compact rows. Overall median relative widths: lambda 1D={overall['lambda_1d_relative_width_median']:.3g}; lambda in 2D={overall['lambda_kappa_2d_lambda_relative_width_median']:.3g}; kappa in 2D={overall['lambda_kappa_2d_kappa_relative_width_median']:.3g}.",
        f"Truth inclusion fractions: 1D={overall['profile_truth_inclusion_1d_fraction']:.3f}, 2D={overall['profile_truth_inclusion_2d_fraction']:.3f}; resolved-region fraction={overall['profile_region_resolved_fraction']:.3f}; unresolved boundary fraction={overall['profile_boundary_hit_fraction']:.3f}.",
        "Each row records the LS optimum, truth cost/inclusion, 95% widths, boundary status, expansion/refinement counts, accepted-point count, and a ridge only when at least three accepted 2D points exist.",
        "", "## Limitations", "", "- Passive rehabilitation trajectories only; no active excitation.", "- Numerical rank does not by itself imply practical or separate parameter identifiability.",
        "- The practical-support decision uses declared conservative diagnostics; smoke output is implementation validation only.",
    ]
    (OUTPUT / "stage11b_report.md").write_text("\n".join(lines) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def coerce_summary_row(row: dict[str, str]) -> dict[str, Any]:
    integer_fields = {"windows"}
    text_fields = {"scope", "practical_identifiability", "state_source", "summary_kind"}
    output: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            output[key] = np.nan
        elif key in text_fields or key.endswith("_json"):
            output[key] = value
        elif value.lower() in {"true", "false"}:
            output[key] = value.lower() == "true"
        elif key in integer_fields:
            output[key] = int(value)
        else:
            output[key] = float(value)
    return output


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    execution = parser.add_mutually_exclusive_group(required=True)
    execution.add_argument("--smoke", dest="execution_mode", action="store_const", const="smoke")
    execution.add_argument("--full", dest="execution_mode", action="store_const", const="full")
    execution.add_argument("--report-only", dest="execution_mode", action="store_const", const="report-only")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--conditions", nargs="*")
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--max-windows", type=int)
    parser.add_argument("--profile-grid-size", type=int, default=DEFAULT_PROFILE_GRID_SIZE)
    parser.add_argument("--compute-only", action="store_true")
    parser.add_argument("--state-source", choices=("estimated", "true", "paired"), default="paired")
    parser.add_argument("--output-root", type=Path)
    return parser


def resolve_output_root(execution_mode: str, output_root: Path | None) -> Path:
    if output_root is not None:
        candidate = Path(output_root)
        return candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()
    if execution_mode == "smoke":
        return OUTPUT_STAGE11C_SMOKE
    return OUTPUT_STAGE11C_FORMAL


def validate_full_options(args: argparse.Namespace) -> None:
    if args.state_source != "paired":
        raise ValueError("full mode requires --state-source paired")
    if args.compute_only:
        raise ValueError("full mode rejects --compute-only")
    if args.resume:
        raise ValueError("full mode rejects --resume")
    if args.conditions is not None and (
        len(args.conditions) != len(CONDITIONS) or set(args.conditions) != set(CONDITIONS)
    ):
        raise ValueError("full mode requires the complete condition matrix")
    if args.max_runs is not None:
        raise ValueError("full mode rejects --max-runs")
    if args.max_windows is not None:
        raise ValueError("full mode rejects --max-windows")
    if args.profile_grid_size != DEFAULT_PROFILE_GRID_SIZE:
        raise ValueError(
            f"full mode requires --profile-grid-size {DEFAULT_PROFILE_GRID_SIZE}"
        )


def parse_cli_args(argv: list[str] | None = None) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if args.execution_mode == "full":
        try:
            validate_full_options(args)
        except ValueError as exc:
            parser.error(str(exc))
    if args.execution_mode == "report-only" and args.resume:
        parser.error("--resume cannot be combined with --report-only")
    args.output_root = resolve_output_root(args.execution_mode, args.output_root)
    return parser, args


def _git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_state_before_run() -> tuple[str, bool]:
    return _git_output("rev-parse", "HEAD"), bool(_git_output("status", "--porcelain"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def exact_command() -> str:
    return shlex.join([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])


def effective_command() -> str:
    return exact_command()


def output_root_is_nonempty(output_root: Path) -> bool:
    return output_root.exists() and any(output_root.iterdir())


def write_resolved_config_snapshot(
    output_root: Path,
    config: dict[str, Any],
) -> str:
    snapshot = output_root / "resolved_config_snapshot.json"
    snapshot.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    return sha256_file(snapshot)


def required_outputs_exist(output_root: Path) -> bool:
    return all((output_root / name).is_file() for name in STAGE11C_REQUIRED_OUTPUTS)


def run_identity(row: dict[str, Any]) -> tuple[str, int]:
    return str(row["condition"]), int(row["seed"])


def window_identity(row: dict[str, Any]) -> tuple[str, int, int, int]:
    return (
        str(row["condition"]),
        int(row["seed"]),
        int(row["window_start"]),
        int(row["window_end"]),
    )


def expected_identity_matrix(
    replay: dict[tuple[str, int], list[dict[str, Any]]],
    conditions: list[str],
    max_runs: int,
    max_windows: int,
) -> tuple[set[tuple[str, int]], set[tuple[str, int, int, int]]]:
    expected_runs: set[tuple[str, int]] = set()
    expected_windows: set[tuple[str, int, int, int]] = set()
    for condition in conditions:
        for seed in SEEDS:
            if len(expected_runs) >= max_runs:
                break
            data = arrays(replay[(condition, seed)])
            expected_runs.add((condition, int(seed)))
            ends = [
                end
                for end in range(UPDATE_INTERVAL, len(data["time"]), UPDATE_INTERVAL)
                if end >= WINDOW_TRANSITIONS
            ][-max_windows:]
            for end in ends:
                start = end - WINDOW_TRANSITIONS + 1
                expected_windows.add((condition, int(seed), start, end))
        if len(expected_runs) >= max_runs:
            break
    return expected_runs, expected_windows


def exact_identity_checks(
    execution_mode: str,
    state_source: str,
    expected_runs: set[tuple[str, int]],
    expected_windows: set[tuple[str, int, int, int]],
    paired_windows: list[dict[str, Any]],
    paired_profiles: list[dict[str, Any]],
    estimated_windows: list[dict[str, Any]],
    true_windows: list[dict[str, Any]],
    profile_grid_size: int,
    git_dirty_before_run: bool,
    required_outputs_complete: bool,
) -> dict[str, bool]:
    observed_window_list = [window_identity(row) for row in paired_windows]
    observed_window_counter = Counter(observed_window_list)
    observed_window_set = set(observed_window_list)
    observed_run_set = {run_identity(row) for row in paired_windows}
    expected_profile_ids = {
        (*identity, profile)
        for identity in expected_windows
        for profile in STAGE11C_PROFILE_NAMES
    }
    observed_profile_counter = Counter(
        (*window_identity(row), str(row["profile"])) for row in paired_profiles
    )
    estimated_counter = Counter(window_identity(row) for row in estimated_windows)
    true_counter = Counter(window_identity(row) for row in true_windows)
    paired_counter = Counter(observed_window_list)
    return {
        "state_source_valid": state_source == "paired",
        "run_identity_complete": observed_run_set == expected_runs,
        "window_identity_complete": observed_window_set == expected_windows,
        "expected_matrix_size_valid": (
            len(expected_runs) == STAGE11C_EXPECTED_RUNS
            and len(expected_windows) == STAGE11C_EXPECTED_WINDOWS
            if execution_mode == "full"
            else len(expected_runs) >= 1 and len(expected_windows) >= 1
        ),
        "no_duplicate_windows": all(count == 1 for count in observed_window_counter.values()),
        "profile_identity_complete": (
            set(observed_profile_counter) == expected_profile_ids
            and all(count == 1 for count in observed_profile_counter.values())
        ),
        "paired_identity_complete": (
            estimated_counter == true_counter == paired_counter
            and set(paired_counter) == expected_windows
            and all(count == 1 for count in estimated_counter.values())
            and all(count == 1 for count in true_counter.values())
            and all(count == 1 for count in paired_counter.values())
        ),
        "runs_complete": len(observed_run_set) == len(expected_runs),
        "windows_complete": len(paired_windows) == len(expected_windows),
        "window_transitions_fixed": all(
            int(row["transitions"]) == WINDOW_TRANSITIONS for row in paired_windows
        ),
        "profile_grid_valid": (
            profile_grid_size == DEFAULT_PROFILE_GRID_SIZE
            if execution_mode == "full"
            else profile_grid_size >= 5
        ),
        "git_clean_for_formal": (
            not git_dirty_before_run if execution_mode == "full" else True
        ),
        "required_outputs_complete": bool(required_outputs_complete),
    }


def mechanical_status_for_run(
    execution_mode: str,
    checks: dict[str, bool],
) -> str:
    if execution_mode == "smoke":
        status = "valid_smoke" if all(checks.values()) else "invalid_incomplete_run"
    elif not checks["git_clean_for_formal"]:
        status = "invalid_provenance"
    elif all(checks.values()):
        status = "valid_full_run"
    else:
        status = "invalid_incomplete_run"
    return status


def build_run_manifest(
    execution_mode: str,
    output_root: Path,
    state_source: str,
    conditions: list[str],
    seeds: list[int],
    expected_runs: int,
    actual_runs: int,
    expected_windows: int,
    actual_windows: int,
    profile_grid_size: int,
    git_commit: str,
    git_dirty_before_run: bool,
    command: str,
    effective_command_value: str,
    conda_environment: str,
    resolved_config_sha256: str,
    checks: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    status = mechanical_status_for_run(execution_mode, checks)
    script_path = Path(__file__).resolve()
    replay_path = Path(DEFAULT_REPLAY).resolve()
    config_path = Path(DEFAULT_CONFIG).resolve()
    manifest = {
        "experiment_id": STAGE11C_EXPERIMENT_ID,
        "execution_mode": execution_mode,
        "git_commit": git_commit,
        "git_dirty_before_run": bool(git_dirty_before_run),
        "exact_command": command,
        "effective_command": effective_command_value,
        "conda_environment": conda_environment,
        "script_path": repository_path(script_path),
        "script_sha256": sha256_file(script_path),
        "replay_path": repository_path(replay_path),
        "replay_sha256": sha256_file(replay_path),
        "config_path": repository_path(config_path),
        "config_sha256": sha256_file(config_path),
        "resolved_config_snapshot": "resolved_config_snapshot.json",
        "resolved_config_sha256": resolved_config_sha256,
        "state_source": state_source,
        "conditions": conditions,
        "seeds": seeds,
        "expected_runs": expected_runs,
        "actual_runs": actual_runs,
        "expected_windows": expected_windows,
        "actual_windows": actual_windows,
        "window_transitions": WINDOW_TRANSITIONS,
        "profile_grid_size": profile_grid_size,
        "output_root": repository_path(output_root),
        "mechanical_completeness": status in {"valid_smoke", "valid_full_run"},
        "mechanical_status": status,
        "parameter_column_order": PARAMETER_ORDER,
        "profile_mode": "adaptive_expand_and_refine",
    }
    mechanical = {
        "experiment_id": STAGE11C_EXPERIMENT_ID,
        "execution_mode": execution_mode,
        "mechanical_status": status,
        "mechanical_completeness": manifest["mechanical_completeness"],
        **checks,
        "checks": checks,
    }
    return manifest, mechanical


def write_run_provenance(
    output_root: Path,
    manifest: dict[str, Any],
    mechanical: dict[str, Any],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output_root / "command.txt").write_text(str(manifest["exact_command"]) + "\n")
    (output_root / "mechanical_status.json").write_text(
        json.dumps(mechanical, indent=2) + "\n"
    )


def main(argv: list[str] | None = None) -> None:
    parser, args = parse_cli_args(argv)
    output_root = Path(args.output_root)
    if args.execution_mode == "report-only":
        manifest = json.loads((output_root / "run_manifest.json").read_text())
        summary = [
            coerce_summary_row(row)
            for row in read_csv(output_root / "state_source_summary.csv")
        ]
        write_stage11c_report(
            manifest,
            summary,
            read_csv(output_root / "paired_profile_summary.csv"),
            output_root,
        )
        print((output_root / "stage11c_report.md").read_text())
        return
    git_commit, git_dirty_before_run = git_state_before_run()
    if args.execution_mode == "full" and git_dirty_before_run:
        parser.error("full mode requires a clean Git worktree before execution")
    if args.execution_mode == "full" and output_root_is_nonempty(output_root):
        parser.error("full mode requires an absent or empty output root")
    output_root.mkdir(parents=True, exist_ok=True)
    conditions = args.conditions or list(CONDITIONS)
    max_runs = args.max_runs if args.max_runs is not None else (1 if args.execution_mode == "smoke" else 10**9)
    max_windows = args.max_windows if args.max_windows is not None else (3 if args.execution_mode == "smoke" else 10**9)
    grid_size = min(args.profile_grid_size, 5) if args.execution_mode == "smoke" else args.profile_grid_size
    replay = load_replay(DEFAULT_REPLAY); config = load_experiment_config(DEFAULT_CONFIG)
    expected_runs, expected_windows = expected_identity_matrix(
        replay, conditions, max_runs, max_windows
    )
    sources = ("estimated", "true") if args.state_source == "paired" else (args.state_source,)
    source_windows: dict[str, list[dict[str, Any]]] = {source: [] for source in sources}
    source_profiles: dict[str, list[dict[str, Any]]] = {source: [] for source in sources}
    paired_windows: list[dict[str, Any]] = []
    paired_profiles: list[dict[str, Any]] = []
    if args.resume and args.state_source == "paired" and (output_root / "paired_window_metrics.csv").exists():
        paired_windows = read_csv(output_root / "paired_window_metrics.csv")
        paired_profiles = read_csv(output_root / "paired_profile_summary.csv")
        for source in sources:
            source_windows[source] = restore_paired_source_rows(paired_windows, source)
            source_profiles[source] = restore_paired_source_rows(paired_profiles, source, profile=True)
    done = {(str(row["condition"]), int(row["seed"]), int(row["window_end"])) for row in paired_windows}
    def run_count() -> int:
        return len({(str(row["condition"]), int(row["seed"])) for row in source_windows[sources[0]]})
    for condition in conditions:
        for seed in SEEDS:
            if run_count() >= max_runs: break
            data = arrays(replay[(condition, seed)]); verify_truth_metadata(condition, data, config)
            ends = [end for end in range(UPDATE_INTERVAL, len(data["time"]), UPDATE_INTERVAL) if end >= WINDOW_TRANSITIONS][-max_windows:]
            model_params = stage9j_overrides(config, condition)["model_params"]
            for end in ends:
                if (condition, seed, end) in done: continue
                for source in sources:
                    window, profiles, _ = analyze_window(condition, seed, data, model_params, end, grid_size, source)
                    source_windows[source].append(window); source_profiles[source].extend(profiles)
                if args.state_source == "paired":
                    paired_windows.append(pair_window_rows(source_windows["estimated"][-1], source_windows["true"][-1]))
                    paired_profiles.extend(pair_profile_rows(source_profiles["estimated"][-2:], source_profiles["true"][-2:]))
                done.add((condition, seed, end))
            if run_count() >= max_runs: break
        if run_count() >= max_runs: break
    if args.state_source != "paired":
        source = sources[0]
        paired_windows = [{"state_source": source, **row} for row in source_windows[source]]
        paired_profiles = [{"state_source": source, **row} for row in source_profiles[source]]
        source_summary_rows = [{**row, "state_source": source, "summary_kind": "state_source"} for row in summarize_windows(source_windows[source], source_profiles[source])[1]]
    else:
        assert paired_windows and len(paired_profiles) == 2 * len(paired_windows)
        source_summary_rows = summarize_state_sources(source_windows["estimated"], source_profiles["estimated"], source_windows["true"], source_profiles["true"], paired_windows, paired_profiles)
    assert all(np.isfinite(float(row["estimated_column_normalized_geometric_condition_number"])) for row in paired_windows) if args.state_source == "paired" else True
    write_dict_csv(output_root / "paired_window_metrics.csv", paired_windows)
    write_dict_csv(output_root / "paired_profile_summary.csv", paired_profiles)
    write_dict_csv(output_root / "state_source_summary.csv", source_summary_rows)
    resolved_config_sha256 = write_resolved_config_snapshot(output_root, config)
    run_pairs = {(str(row["condition"]), int(row["seed"])) for row in paired_windows}
    observed_conditions = [
        condition for condition in CONDITIONS if condition in {str(row["condition"]) for row in paired_windows}
    ]
    observed_seeds = sorted({int(row["seed"]) for row in paired_windows})
    checks = exact_identity_checks(
        args.execution_mode,
        args.state_source,
        expected_runs,
        expected_windows,
        paired_windows,
        paired_profiles,
        source_windows.get("estimated", []),
        source_windows.get("true", []),
        grid_size,
        git_dirty_before_run,
        required_outputs_complete=False,
    )
    command = exact_command()
    effective = effective_command()
    conda_environment = os.environ.get("CONDA_DEFAULT_ENV", "")
    manifest, mechanical = build_run_manifest(
        args.execution_mode,
        output_root,
        args.state_source,
        observed_conditions,
        observed_seeds,
        len(expected_runs),
        len(run_pairs),
        len(expected_windows),
        len(paired_windows),
        grid_size,
        git_commit,
        git_dirty_before_run,
        command,
        effective,
        conda_environment,
        resolved_config_sha256,
        checks,
    )
    write_run_provenance(output_root, manifest, mechanical)
    if not args.compute_only:
        write_stage11c_report(
            manifest, source_summary_rows, paired_profiles, output_root
        )
    checks = exact_identity_checks(
        args.execution_mode,
        args.state_source,
        expected_runs,
        expected_windows,
        paired_windows,
        paired_profiles,
        source_windows.get("estimated", []),
        source_windows.get("true", []),
        grid_size,
        git_dirty_before_run,
        required_outputs_complete=required_outputs_exist(output_root),
    )
    manifest, mechanical = build_run_manifest(
        args.execution_mode,
        output_root,
        args.state_source,
        observed_conditions,
        observed_seeds,
        len(expected_runs),
        len(run_pairs),
        len(expected_windows),
        len(paired_windows),
        grid_size,
        git_commit,
        git_dirty_before_run,
        command,
        effective,
        conda_environment,
        resolved_config_sha256,
        checks,
    )
    write_run_provenance(output_root, manifest, mechanical)
    if not args.compute_only:
        write_stage11c_report(
            manifest, source_summary_rows, paired_profiles, output_root
        )
    print(
        json.dumps(
            {
                "execution_mode": manifest["execution_mode"],
                "state_source": args.state_source,
                "actual_runs": manifest["actual_runs"],
                "actual_windows": manifest["actual_windows"],
                "mechanical_status": manifest["mechanical_status"],
                "output": str(output_root),
            },
            indent=2,
        )
    )
    if args.execution_mode == "full" and not manifest["mechanical_completeness"]:
        raise RuntimeError(
            f"full execution is mechanically invalid: {manifest['mechanical_status']}"
        )


if __name__ == "__main__":
    main()
