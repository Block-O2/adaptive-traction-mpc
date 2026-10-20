#!/usr/bin/env python3
"""Stage 11G exact-discrete local information audit.

The exact one-step Jacobian is evaluated at true parameters with deterministic
central differences.  Stage 11B metric definitions are reused directly.  No
fit, optimizer, estimator, identifier, or controller is executed, and the
generated report never applies the scientific classification automatically.
"""

from __future__ import annotations

import argparse
import ast
import csv
import inspect
import json
import os
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import (
    DEFAULT_CONFIG,
    DEFAULT_REPLAY,
    arrays,
    load_replay,
)
from run_spring2d_stage9j_gap_decomposition import (
    CONDITIONS,
    stage9j_overrides,
    write_dict_csv,
)
from run_stage11b_parameter_subspace_audit import (
    PARAMETER_ORDER,
    PHYSICAL_SCALE,
    ROW_SQRT_WEIGHTS,
    WINDOW_TRANSITIONS,
    build_affine_window,
    svd_metrics,
    verify_truth_metadata,
)
from run_stage11d_residual_coverage_audit import (
    STAGE11B_RUNNER,
    expected_identity_sets,
    repository_path,
    sha256_file,
    validate_and_index_stage11c_profiles,
    window_identity,
)
from run_stage11e_block_coverage_calibration import (
    validate_and_index_stage11d_diagnostics,
)
from run_stage11f_discrete_closure_audit import (
    REPLAY_TRANSITION_QUALNAME,
    SPRING2D_DYNAMICS_SOURCE,
    SPRING2D_ENV_SOURCE,
    replay_generation_transition,
    transition_reuse_checks,
)

STAGE11C_ROOT = ROOT / "results" / "stage11c_state_source_audit"
STAGE11C_MANIFEST = STAGE11C_ROOT / "run_manifest.json"
STAGE11C_PROFILES = STAGE11C_ROOT / "paired_profile_summary.csv"
STAGE11D_ROOT = ROOT / "results" / "stage11d_residual_coverage_audit"
STAGE11D_MANIFEST = STAGE11D_ROOT / "run_manifest.json"
STAGE11D_DIAGNOSTICS = STAGE11D_ROOT / "window_residual_diagnostics.csv"
STAGE11F_ROOT = ROOT / "results" / "stage11f_discrete_closure_audit"
STAGE11F_MANIFEST = STAGE11F_ROOT / "run_manifest.json"
STAGE11F_METRICS = STAGE11F_ROOT / "window_discrete_closure_metrics.csv"
STAGE11F_RUNNER = ROOT / "scripts" / "run_stage11f_discrete_closure_audit.py"

OUTPUT_FORMAL = ROOT / "results" / "stage11g_discrete_information_audit"
OUTPUT_SMOKE = (
    ROOT / "results" / "local" / "stage11g_discrete_information_audit_smoke"
)
STAGE11G_EXPERIMENT_ID = "stage11g_discrete_information_audit"
STAGE11G_EXPECTED_RUNS = 24
STAGE11G_EXPECTED_WINDOWS = 710
STAGE11G_REQUIRED_OUTPUTS = (
    "window_discrete_information_metrics.csv",
    "condition_discrete_information_summary.csv",
    "stage11g_report.md",
    "run_manifest.json",
    "command.txt",
    "mechanical_status.json",
)

CHANNEL_NAMES = ("radial", "angular")
PRIMARY_RELATIVE_STEP = 1.0e-5
HALF_STEP_FACTOR = 0.5
HALF_STEP_MAX_COLUMN_RELATIVE_DISCREPANCY = 1.0e-4
EXPECTED_JACOBIAN_SHAPE = (2 * WINDOW_TRANSITIONS, len(PARAMETER_ORDER))
DECLARED_UNTRACKED_INPUT_ROOTS = tuple(
    (ROOT / "results" / name).relative_to(ROOT).as_posix()
    for name in (
        "stage11c_state_source_audit",
        "stage11d_residual_coverage_audit",
        "stage11e_block_coverage_calibration",
        "stage11f_discrete_closure_audit",
    )
)

TransitionFunction = Callable[
    [np.ndarray, np.ndarray, float, dict[str, Any]], np.ndarray
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def physical_to_theta(params: dict[str, Any]) -> np.ndarray:
    mass = float(params["m"])
    stiffness = float(params["k"])
    damping = float(params["b_r"])
    if not np.all(np.isfinite([mass, stiffness, damping])) or min(
        mass, stiffness, damping
    ) <= 0.0:
        raise ValueError("m, k, and b_r must be finite and positive")
    return np.array(
        [1.0 / mass, stiffness / mass, damping / mass], dtype=float
    )


def theta_to_physical_params(
    theta: np.ndarray,
    template_params: dict[str, Any],
) -> dict[str, Any]:
    values = np.asarray(theta, dtype=float)
    if values.shape != (len(PARAMETER_ORDER),):
        raise ValueError("theta must have order [lambda, kappa, beta]")
    lam, kappa, beta = (float(value) for value in values)
    if not np.all(np.isfinite(values)) or lam <= 0.0:
        raise ValueError("theta must be finite with positive lambda")
    params = dict(template_params)
    params["m"] = 1.0 / lam
    params["k"] = kappa / lam
    params["b_r"] = beta / lam
    return params


def exact_discrete_output(
    state: np.ndarray,
    action: np.ndarray,
    theta: np.ndarray,
    template_params: dict[str, Any],
    transition_fn: TransitionFunction | None = None,
) -> np.ndarray:
    """Return [radial, angular] acceleration equivalents without replay x_next."""
    x_t = np.asarray(state, dtype=float)
    u_t = np.asarray(action, dtype=float)
    if x_t.shape != (4,) or u_t.shape != (2,):
        raise ValueError("state/action shapes must be (4,) and (2,)")
    params = theta_to_physical_params(theta, template_params)
    dt = float(params["dt"])
    transition = (
        replay_generation_transition if transition_fn is None else transition_fn
    )
    predicted_next = np.asarray(
        transition(x_t, u_t, dt, params), dtype=float
    )
    if predicted_next.shape != (4,):
        raise RuntimeError("exact transition must return a four-state vector")
    return np.array(
        [
            (predicted_next[3] - x_t[3]) / dt,
            (predicted_next[1] - x_t[1]) / dt,
        ],
        dtype=float,
    )


def central_difference_transition_jacobian(
    state: np.ndarray,
    action: np.ndarray,
    theta: np.ndarray,
    template_params: dict[str, Any],
    relative_step: float = PRIMARY_RELATIVE_STEP,
    transition_fn: TransitionFunction | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute dz/dtheta using deterministic componentwise central differences."""
    theta_values = np.asarray(theta, dtype=float)
    if theta_values.shape != (len(PARAMETER_ORDER),):
        raise ValueError("theta must have three ordered components")
    if not np.isfinite(relative_step) or relative_step <= 0.0:
        raise ValueError("relative_step must be finite and positive")
    steps = relative_step * np.maximum(np.abs(theta_values), 1.0)
    jacobian = np.empty((len(CHANNEL_NAMES), len(PARAMETER_ORDER)))
    for column, step_size in enumerate(steps):
        plus = theta_values.copy()
        minus = theta_values.copy()
        plus[column] += step_size
        minus[column] -= step_size
        if minus[0] <= 0.0:
            raise RuntimeError("central-difference lambda perturbation is nonpositive")
        z_plus = exact_discrete_output(
            state,
            action,
            plus,
            template_params,
            transition_fn=transition_fn,
        )
        z_minus = exact_discrete_output(
            state,
            action,
            minus,
            template_params,
            transition_fn=transition_fn,
        )
        jacobian[:, column] = (z_plus - z_minus) / (2.0 * step_size)
    if not np.all(np.isfinite(jacobian)):
        raise RuntimeError("central-difference Jacobian is non-finite")
    return jacobian, steps


def build_discrete_window_jacobians(
    data: dict[str, np.ndarray],
    window_start: int,
    window_end: int,
    true_params: dict[str, Any],
    transition_fn: TransitionFunction | None = None,
    cache: dict[int, tuple[np.ndarray, np.ndarray]] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stack 70 [radial, angular] blocks without reading replay x_(t+1)."""
    if window_end - window_start + 1 != WINDOW_TRANSITIONS:
        raise ValueError("exact discrete window must contain 70 transitions")
    true_states = np.asarray(data["true"], dtype=float)
    actions = np.asarray(data["action"], dtype=float)
    theta = physical_to_theta(true_params)
    primary_blocks: list[np.ndarray] = []
    half_blocks: list[np.ndarray] = []
    component_steps: np.ndarray | None = None
    shared_cache = {} if cache is None else cache
    for step in range(window_start, window_end + 1):
        if step not in shared_cache:
            x_t = true_states[step - 1]
            u_t = actions[step]
            primary, steps = central_difference_transition_jacobian(
                x_t,
                u_t,
                theta,
                true_params,
                relative_step=PRIMARY_RELATIVE_STEP,
                transition_fn=transition_fn,
            )
            half, half_steps = central_difference_transition_jacobian(
                x_t,
                u_t,
                theta,
                true_params,
                relative_step=PRIMARY_RELATIVE_STEP * HALF_STEP_FACTOR,
                transition_fn=transition_fn,
            )
            if not np.allclose(
                half_steps, steps * HALF_STEP_FACTOR, rtol=0.0, atol=0.0
            ):
                raise RuntimeError("half-step central-difference contract changed")
            shared_cache[step] = (primary, half)
            component_steps = steps
        primary, half = shared_cache[step]
        primary_blocks.append(primary)
        half_blocks.append(half)
    primary_window = np.vstack(primary_blocks)
    half_window = np.vstack(half_blocks)
    if primary_window.shape != EXPECTED_JACOBIAN_SHAPE:
        raise RuntimeError(
            f"exact Jacobian shape {primary_window.shape} != "
            f"{EXPECTED_JACOBIAN_SHAPE}"
        )
    if half_window.shape != EXPECTED_JACOBIAN_SHAPE:
        raise RuntimeError("half-step Jacobian shape differs from primary")
    if component_steps is None:
        component_steps = PRIMARY_RELATIVE_STEP * np.maximum(
            np.abs(theta), 1.0
        )
    return primary_window, half_window, component_steps


def half_step_stability(
    primary: np.ndarray,
    half_step: np.ndarray,
) -> dict[str, Any]:
    first = np.asarray(primary, dtype=float)
    second = np.asarray(half_step, dtype=float)
    if first.shape != second.shape:
        raise ValueError("primary and half-step Jacobians must share shape")
    difference = first - second
    floor = np.finfo(float).eps
    overall = float(
        np.linalg.norm(difference)
        / max(float(np.linalg.norm(second)), floor)
    )
    columns = np.array(
        [
            np.linalg.norm(difference[:, column])
            / max(float(np.linalg.norm(second[:, column])), floor)
            for column in range(first.shape[1])
        ],
        dtype=float,
    )
    maximum = float(np.max(columns))
    return {
        "overall_relative_discrepancy": overall,
        "column_relative_discrepancies": columns,
        "maximum_column_relative_discrepancy": maximum,
        "stable": bool(
            np.isfinite(maximum)
            and maximum <= HALF_STEP_MAX_COLUMN_RELATIVE_DISCREPANCY
        ),
    }


def direction_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    left = np.asarray(first, dtype=float)
    right = np.asarray(second, dtype=float)
    left /= np.linalg.norm(left)
    right /= np.linalg.norm(right)
    return float(
        np.degrees(
            np.arccos(np.clip(abs(float(left @ right)), 0.0, 1.0))
        )
    )


def validate_and_index_stage11f_metrics(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[tuple[str, int, int, int], dict[str, Any]]:
    indexed: dict[tuple[str, int, int, int], dict[str, Any]] = {}
    duplicates: list[tuple[str, int, int, int]] = []
    for row in rows:
        identity = window_identity(row)
        if identity in indexed:
            duplicates.append(identity)
        indexed[identity] = row
    if duplicates:
        raise RuntimeError(
            f"Stage 11F metrics contain duplicate windows: {duplicates[:3]}"
        )
    if len(indexed) != int(manifest["actual_windows"]):
        raise RuntimeError(
            "Stage 11F metric identity count does not match manifest"
        )
    invalid = [
        identity
        for identity, row in indexed.items()
        if int(row["transitions"]) != WINDOW_TRANSITIONS
        or str(row["state_source"]) != "true"
        or float(row["discrete_weighted_residual_rms"]) != 0.0
        or float(row["discrete_to_affine_weighted_rms_ratio"]) != 0.0
    ]
    if invalid:
        raise RuntimeError(
            "Stage 11F reviewed source must contain exact zero closure in "
            f"every true-state 70-transition window: {invalid[:3]}"
        )
    return indexed


def source_provenance_checks(
    stage11c_manifest: dict[str, Any],
    stage11d_manifest: dict[str, Any],
    stage11f_manifest: dict[str, Any],
) -> dict[str, bool]:
    current_replay_hash = sha256_file(Path(DEFAULT_REPLAY))
    current_config_hash = sha256_file(Path(DEFAULT_CONFIG))
    checks = {
        "source_stage11c_valid_full_run": (
            stage11c_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11c_manifest.get("mechanical_completeness"))
        ),
        "source_stage11d_valid_full_run": (
            stage11d_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11d_manifest.get("mechanical_completeness"))
        ),
        "source_stage11f_valid_full_run": (
            stage11f_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11f_manifest.get("mechanical_completeness"))
            and int(stage11f_manifest.get("actual_runs", -1))
            == STAGE11G_EXPECTED_RUNS
            and int(stage11f_manifest.get("actual_windows", -1))
            == STAGE11G_EXPECTED_WINDOWS
        ),
        "stage11c_manifest_matches_stage11d_and_stage11f": (
            stage11d_manifest.get("stage11c_manifest_sha256")
            == sha256_file(STAGE11C_MANIFEST)
            == stage11f_manifest.get("stage11c_manifest_sha256")
        ),
        "stage11c_profiles_match_stage11d_and_stage11f": (
            stage11d_manifest.get("stage11c_profile_sha256")
            == sha256_file(STAGE11C_PROFILES)
            == stage11f_manifest.get("stage11c_profiles_sha256")
        ),
        "stage11d_manifest_matches_stage11f": (
            stage11f_manifest.get("stage11d_manifest_sha256")
            == sha256_file(STAGE11D_MANIFEST)
        ),
        "stage11d_diagnostics_match_stage11f": (
            stage11f_manifest.get("stage11d_diagnostics_sha256")
            == sha256_file(STAGE11D_DIAGNOSTICS)
        ),
        "stage11f_runner_matches_manifest": (
            stage11f_manifest.get("script_sha256")
            == sha256_file(STAGE11F_RUNNER)
        ),
        "replay_matches_all_sources": (
            stage11c_manifest.get("replay_sha256")
            == current_replay_hash
            == stage11d_manifest.get("replay_sha256")
            == stage11f_manifest.get("replay_sha256")
        ),
        "config_matches_all_sources": (
            stage11c_manifest.get("config_sha256")
            == current_config_hash
            == stage11d_manifest.get("config_sha256")
            == stage11f_manifest.get("config_sha256")
        ),
        "stage11b_runner_matches_stage11c": (
            stage11c_manifest.get("script_sha256")
            == sha256_file(STAGE11B_RUNNER)
        ),
        "transition_sources_match_stage11f": (
            stage11f_manifest.get("spring2d_env_source_sha256")
            == sha256_file(SPRING2D_ENV_SOURCE)
            and stage11f_manifest.get("spring2d_dynamics_source_sha256")
            == sha256_file(SPRING2D_DYNAMICS_SOURCE)
        ),
    }
    checks.update(transition_reuse_checks())
    return checks


def validate_source_alignment(
    profile_index: dict[
        tuple[str, int, int, int], dict[str, dict[str, Any]]
    ],
    diagnostic_index: dict[
        tuple[str, int, int, int], dict[str, Any]
    ],
    closure_index: dict[
        tuple[str, int, int, int], dict[str, Any]
    ],
) -> None:
    expected = set(profile_index)
    if set(diagnostic_index) != expected or set(closure_index) != expected:
        raise RuntimeError(
            "Stage 11C/11D/11F window identities are not exactly aligned"
        )


def compute_window_information(
    identity: tuple[str, int, int, int],
    data: dict[str, np.ndarray],
    true_params: dict[str, Any],
    affine_model_params: dict[str, Any],
    transition_fn: TransitionFunction | None = None,
    derivative_cache: dict[int, tuple[np.ndarray, np.ndarray]] | None = None,
) -> dict[str, Any]:
    condition, seed, window_start, window_end = identity
    exact, half, component_steps = build_discrete_window_jacobians(
        data,
        window_start,
        window_end,
        true_params,
        transition_fn=transition_fn,
        cache=derivative_cache,
    )
    affine, _, reconstructed_start = build_affine_window(
        condition,
        seed,
        data,
        affine_model_params,
        window_end,
        state_source="true",
    )
    if reconstructed_start != window_start:
        raise RuntimeError(f"{identity}: affine window start changed")
    if affine.shape != EXPECTED_JACOBIAN_SHAPE:
        raise RuntimeError(f"{identity}: affine H shape changed")

    exact_metrics = svd_metrics(exact, y=None)
    affine_metrics = svd_metrics(affine, y=None)
    stability = half_step_stability(exact, half)
    affine_information = float(
        affine_metrics["conditional_lambda_information_abs"]
    )
    exact_information = float(
        exact_metrics["conditional_lambda_information_abs"]
    )
    if affine_information <= np.finfo(float).eps:
        raise RuntimeError(f"{identity}: affine conditional lambda information is zero")
    information_ratio = exact_information / affine_information
    weak_angle = direction_angle_deg(
        exact_metrics["physical_weak_direction"],
        affine_metrics["physical_weak_direction"],
    )
    exact_physical_singular = np.asarray(
        exact_metrics["physical_scaled_weighted_singular_values"], dtype=float
    )
    affine_physical_singular = np.asarray(
        affine_metrics["physical_scaled_weighted_singular_values"], dtype=float
    )
    exact_normalized_singular = np.asarray(
        exact_metrics["column_normalized_singular_values"], dtype=float
    )
    affine_normalized_singular = np.asarray(
        affine_metrics["column_normalized_singular_values"], dtype=float
    )

    row: dict[str, Any] = {
        "condition": condition,
        "seed": seed,
        "window_start": window_start,
        "window_end": window_end,
        "transitions": window_end - window_start + 1,
        "state_source": "true",
        "transition_function": REPLAY_TRANSITION_QUALNAME,
        "transition_alignment": "true[step-1],action[step]",
        "replay_next_state_used_for_exact_jacobian": False,
        "true_parameter_source": "stage9j_condition_true_params",
        "theta_order_json": json.dumps(list(PARAMETER_ORDER)),
        "true_theta_json": json.dumps(
            physical_to_theta(true_params).tolist(), separators=(",", ":")
        ),
        "central_difference_relative_step": PRIMARY_RELATIVE_STEP,
        "central_difference_component_steps_json": json.dumps(
            component_steps.tolist(), separators=(",", ":")
        ),
        "half_step_factor": HALF_STEP_FACTOR,
        "half_step_relative_discrepancy": float(
            stability["overall_relative_discrepancy"]
        ),
        "half_step_column_relative_discrepancies_json": json.dumps(
            stability["column_relative_discrepancies"].tolist(),
            separators=(",", ":"),
        ),
        "half_step_max_column_relative_discrepancy": float(
            stability["maximum_column_relative_discrepancy"]
        ),
        "half_step_stability_threshold": (
            HALF_STEP_MAX_COLUMN_RELATIVE_DISCREPANCY
        ),
        "numerical_derivative_stable": bool(stability["stable"]),
        "exact_jacobian_rows": int(exact.shape[0]),
        "exact_jacobian_columns": int(exact.shape[1]),
        "affine_jacobian_rows": int(affine.shape[0]),
        "affine_jacobian_columns": int(affine.shape[1]),
        "radial_channel_index": 0,
        "angular_channel_index": 1,
        "radial_row_sqrt_weight": float(ROW_SQRT_WEIGHTS[0]),
        "angular_row_sqrt_weight": float(ROW_SQRT_WEIGHTS[1]),
        "physical_scale_json": json.dumps(
            PHYSICAL_SCALE.tolist(), separators=(",", ":")
        ),
        "exact_rank": int(exact_metrics["rank"]),
        "affine_rank": int(affine_metrics["rank"]),
        "exact_rank3": int(exact_metrics["rank"]) == len(PARAMETER_ORDER),
        "affine_rank3": int(affine_metrics["rank"]) == len(PARAMETER_ORDER),
        "exact_raw_condition_number": float(
            exact_metrics["raw_condition_number_H"]
        ),
        "affine_raw_condition_number": float(
            affine_metrics["raw_condition_number_H"]
        ),
        "exact_physical_scale_condition_number": float(
            exact_metrics["physical_scale_condition_number_HS"]
        ),
        "affine_physical_scale_condition_number": float(
            affine_metrics["physical_scale_condition_number_HS"]
        ),
        "exact_column_normalized_condition_number": float(
            exact_metrics["column_normalized_geometric_condition_number"]
        ),
        "affine_column_normalized_condition_number": float(
            affine_metrics["column_normalized_geometric_condition_number"]
        ),
        "exact_conditional_lambda_information_abs": exact_information,
        "affine_conditional_lambda_information_abs": affine_information,
        "exact_to_affine_conditional_lambda_information_ratio": (
            information_ratio
        ),
        "exact_conditional_lambda_information_ratio": float(
            exact_metrics["conditional_lambda_information_ratio"]
        ),
        "affine_conditional_lambda_information_ratio": float(
            affine_metrics["conditional_lambda_information_ratio"]
        ),
        "exact_affine_physical_weak_direction_angle_deg": weak_angle,
        "exact_physical_weak_direction_json": json.dumps(
            np.asarray(
                exact_metrics["physical_weak_direction"], dtype=float
            ).tolist(),
            separators=(",", ":"),
        ),
        "affine_physical_weak_direction_json": json.dumps(
            np.asarray(
                affine_metrics["physical_weak_direction"], dtype=float
            ).tolist(),
            separators=(",", ":"),
        ),
        "exact_physical_scaled_weighted_singular_values_json": json.dumps(
            exact_physical_singular.tolist(), separators=(",", ":")
        ),
        "affine_physical_scaled_weighted_singular_values_json": json.dumps(
            affine_physical_singular.tolist(), separators=(",", ":")
        ),
        "exact_column_normalized_singular_values_json": json.dumps(
            exact_normalized_singular.tolist(), separators=(",", ":")
        ),
        "affine_column_normalized_singular_values_json": json.dumps(
            affine_normalized_singular.tolist(), separators=(",", ":")
        ),
        "optimizer_invoked": False,
        "parameter_fit_invoked": False,
        "estimator_invoked": False,
        "identifier_invoked": False,
        "controller_invoked": False,
    }
    for index in range(len(PARAMETER_ORDER)):
        number = index + 1
        row[f"exact_physical_scaled_weighted_sigma_{number}"] = float(
            exact_physical_singular[index]
        )
        row[f"affine_physical_scaled_weighted_sigma_{number}"] = float(
            affine_physical_singular[index]
        )
        row[f"exact_column_normalized_sigma_{number}"] = float(
            exact_normalized_singular[index]
        )
        row[f"affine_column_normalized_sigma_{number}"] = float(
            affine_normalized_singular[index]
        )
    return row


def aggregate_rows(
    window_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = [
        (
            condition,
            [row for row in window_rows if row["condition"] == condition],
        )
        for condition in CONDITIONS
        if any(row["condition"] == condition for row in window_rows)
    ]
    groups.append(("overall", window_rows))
    summaries: list[dict[str, Any]] = []
    for condition, rows in groups:
        def values(key: str) -> np.ndarray:
            return np.asarray([float(row[key]) for row in rows], dtype=float)

        summary: dict[str, Any] = {
            "condition": condition,
            "n_runs": len(
                {
                    (str(row["condition"]), int(row["seed"]))
                    for row in rows
                }
            ),
            "n_windows": len(rows),
            "exact_rank3_fraction": float(
                np.mean([bool(row["exact_rank3"]) for row in rows])
            ),
            "affine_rank3_fraction": float(
                np.mean([bool(row["affine_rank3"]) for row in rows])
            ),
            "exact_conditional_lambda_information_abs_median": float(
                np.median(values("exact_conditional_lambda_information_abs"))
            ),
            "affine_conditional_lambda_information_abs_median": float(
                np.median(values("affine_conditional_lambda_information_abs"))
            ),
            "exact_to_affine_conditional_lambda_information_ratio_median": float(
                np.median(
                    values(
                        "exact_to_affine_conditional_lambda_information_ratio"
                    )
                )
            ),
            "exact_to_affine_conditional_lambda_information_ratio_p95": float(
                np.percentile(
                    values(
                        "exact_to_affine_conditional_lambda_information_ratio"
                    ),
                    95,
                )
            ),
            "exact_affine_physical_weak_direction_angle_deg_median": float(
                np.median(
                    values(
                        "exact_affine_physical_weak_direction_angle_deg"
                    )
                )
            ),
            "exact_affine_physical_weak_direction_angle_deg_p95": float(
                np.percentile(
                    values(
                        "exact_affine_physical_weak_direction_angle_deg"
                    ),
                    95,
                )
            ),
            "half_step_relative_discrepancy_median": float(
                np.median(values("half_step_relative_discrepancy"))
            ),
            "half_step_max_column_relative_discrepancy_p95": float(
                np.percentile(
                    values("half_step_max_column_relative_discrepancy"), 95
                )
            ),
            "half_step_max_column_relative_discrepancy_max": float(
                np.max(
                    values("half_step_max_column_relative_discrepancy")
                )
            ),
            "numerical_derivative_stable_fraction": float(
                np.mean(
                    [bool(row["numerical_derivative_stable"]) for row in rows]
                )
            ),
            "fit_optimizer_estimator_identifier_controller_invoked_fraction": float(
                np.mean(
                    [
                        any(
                            bool(row[key])
                            for key in (
                                "optimizer_invoked",
                                "parameter_fit_invoked",
                                "estimator_invoked",
                                "identifier_invoked",
                                "controller_invoked",
                            )
                        )
                        for row in rows
                    ]
                )
            ),
        }
        for number in range(1, len(PARAMETER_ORDER) + 1):
            for source in ("exact", "affine"):
                key = f"{source}_physical_scaled_weighted_sigma_{number}"
                summary[f"{key}_median"] = float(np.median(values(key)))
        summaries.append(summary)
    return summaries


def choose_identities(
    identities: Iterable[tuple[str, int, int, int]],
    mode: str,
) -> list[tuple[str, int, int, int]]:
    order = {condition: index for index, condition in enumerate(CONDITIONS)}
    ordered = sorted(
        identities,
        key=lambda identity: (
            order.get(identity[0], len(order)),
            identity[1],
            identity[3],
        ),
    )
    if mode == "full":
        return ordered
    first_run = ordered[0][:2]
    return [
        identity for identity in ordered if identity[:2] == first_run
    ][:3]


def _git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def classify_git_status(
    status_lines: Iterable[str],
) -> tuple[list[str], list[str]]:
    allowed: list[str] = []
    unexpected: list[str] = []
    for raw_line in status_lines:
        line = str(raw_line)
        path = line[3:] if len(line) >= 4 else ""
        is_declared_input = any(
            path == root or path.startswith(f"{root}/")
            for root in DECLARED_UNTRACKED_INPUT_ROOTS
        )
        if line.startswith("?? ") and is_declared_input:
            allowed.append(line)
        else:
            unexpected.append(line)
    return allowed, unexpected


def git_context() -> dict[str, Any]:
    status_lines = [
        line
        for line in _git_output(
            "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
        if line
    ]
    allowed, unexpected = classify_git_status(status_lines)
    return {
        "commit": _git_output("rev-parse", "HEAD"),
        "status_lines": status_lines,
        "allowed_untracked_input_lines": allowed,
        "unexpected_status_lines": unexpected,
        "dirty": bool(status_lines),
        "clean_for_formal": not unexpected,
    }


def exact_identity_checks(
    mode: str,
    expected_runs: set[tuple[str, int]],
    expected_windows: set[tuple[str, int, int, int]],
    rows: list[dict[str, Any]],
    provenance_checks: dict[str, bool],
    source_alignment_complete: bool,
    git_clean_for_formal: bool,
    required_outputs_complete: bool,
) -> dict[str, bool]:
    observed_list = [window_identity(row) for row in rows]
    observed_counter = Counter(observed_list)
    observed_windows = set(observed_list)
    observed_runs = {
        (condition, seed)
        for condition, seed, _, _ in observed_windows
    }
    return {
        "source_provenance_complete": all(provenance_checks.values()),
        "source_window_alignment_complete": bool(source_alignment_complete),
        "run_identity_complete": observed_runs == expected_runs,
        "window_identity_complete": observed_windows == expected_windows,
        "no_duplicate_windows": (
            len(observed_list) == len(observed_windows)
            and all(count == 1 for count in observed_counter.values())
        ),
        "expected_matrix_size_valid": (
            len(expected_runs) == STAGE11G_EXPECTED_RUNS
            and len(expected_windows) == STAGE11G_EXPECTED_WINDOWS
            if mode == "full"
            else len(expected_runs) == 1
            and 1 <= len(expected_windows) <= 3
        ),
        "window_transitions_fixed": all(
            int(row["transitions"]) == WINDOW_TRANSITIONS for row in rows
        ),
        "jacobian_shapes_exact": all(
            int(row["exact_jacobian_rows"]) == EXPECTED_JACOBIAN_SHAPE[0]
            and int(row["exact_jacobian_columns"])
            == EXPECTED_JACOBIAN_SHAPE[1]
            and int(row["affine_jacobian_rows"])
            == EXPECTED_JACOBIAN_SHAPE[0]
            and int(row["affine_jacobian_columns"])
            == EXPECTED_JACOBIAN_SHAPE[1]
            for row in rows
        ),
        "true_state_action_parameter_alignment": all(
            str(row["state_source"]) == "true"
            and str(row["transition_alignment"])
            == "true[step-1],action[step]"
            and str(row["true_parameter_source"])
            == "stage9j_condition_true_params"
            for row in rows
        ),
        "replay_next_state_not_used": all(
            not bool(row["replay_next_state_used_for_exact_jacobian"])
            for row in rows
        ),
        "channel_order_weights_and_scale_fixed": all(
            int(row["radial_channel_index"]) == 0
            and int(row["angular_channel_index"]) == 1
            and float(row["radial_row_sqrt_weight"])
            == float(ROW_SQRT_WEIGHTS[0])
            and float(row["angular_row_sqrt_weight"])
            == float(ROW_SQRT_WEIGHTS[1])
            and np.array_equal(
                np.asarray(json.loads(row["physical_scale_json"]), dtype=float),
                PHYSICAL_SCALE,
            )
            for row in rows
        ),
        "central_difference_contract_fixed": all(
            float(row["central_difference_relative_step"])
            == PRIMARY_RELATIVE_STEP
            and float(row["half_step_factor"]) == HALF_STEP_FACTOR
            for row in rows
        ),
        "numerical_derivatives_stable": all(
            bool(row["numerical_derivative_stable"]) for row in rows
        ),
        "finite_primary_metrics": all(
            np.isfinite(
                float(
                    row[
                        "exact_to_affine_conditional_lambda_information_ratio"
                    ]
                )
            )
            and np.isfinite(
                float(row["exact_affine_physical_weak_direction_angle_deg"])
            )
            for row in rows
        ),
        "no_fit_optimizer_estimator_identifier_controller": all(
            not any(
                bool(row[key])
                for key in (
                    "optimizer_invoked",
                    "parameter_fit_invoked",
                    "estimator_invoked",
                    "identifier_invoked",
                    "controller_invoked",
                )
            )
            for row in rows
        ),
        "git_clean_for_formal": (
            bool(git_clean_for_formal) if mode == "full" else True
        ),
        "required_outputs_complete": bool(required_outputs_complete),
    }


def mechanical_status_for_run(
    mode: str,
    checks: dict[str, bool],
) -> str:
    if mode == "smoke":
        return "valid_smoke" if all(checks.values()) else "invalid_incomplete_run"
    if not checks["git_clean_for_formal"]:
        return "invalid_provenance"
    return "valid_full_run" if all(checks.values()) else "invalid_incomplete_run"


def required_outputs_exist(output_root: Path) -> bool:
    return all(
        (output_root / name).is_file() for name in STAGE11G_REQUIRED_OUTPUTS
    )


def exact_command(argv: list[str] | None = None) -> str:
    arguments = sys.argv[1:] if argv is None else argv
    return shlex.join(
        [sys.executable, str(Path(__file__).resolve()), *arguments]
    )


def build_manifest(
    args: argparse.Namespace,
    output_root: Path,
    git_state: dict[str, Any],
    command: str,
    stage11c_manifest: dict[str, Any],
    stage11d_manifest: dict[str, Any],
    stage11f_manifest: dict[str, Any],
    provenance_checks: dict[str, bool],
    expected_runs: set[tuple[str, int]],
    expected_windows: set[tuple[str, int, int, int]],
    rows: list[dict[str, Any]],
    checks: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    status = mechanical_status_for_run(args.mode, checks)
    observed_runs = {
        (str(row["condition"]), int(row["seed"])) for row in rows
    }
    manifest = {
        "experiment_id": STAGE11G_EXPERIMENT_ID,
        "execution_mode": args.mode,
        "evidence_level": "formal" if args.mode == "full" else "smoke",
        "authoritative": False,
        "scientific_status_assigned": False,
        "hypothesis_selected_automatically": False,
        "git_commit": git_state["commit"],
        "git_dirty_before_run": bool(git_state["dirty"]),
        "git_clean_for_formal": bool(git_state["clean_for_formal"]),
        "git_status_before_run": list(git_state["status_lines"]),
        "git_allowed_untracked_inputs": list(
            git_state["allowed_untracked_input_lines"]
        ),
        "git_unexpected_changes_before_run": list(
            git_state["unexpected_status_lines"]
        ),
        "exact_command": command,
        "effective_command": command,
        "conda_environment": os.environ.get("CONDA_DEFAULT_ENV", ""),
        "script_path": repository_path(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "replay_path": repository_path(Path(DEFAULT_REPLAY)),
        "replay_sha256": sha256_file(Path(DEFAULT_REPLAY)),
        "config_path": repository_path(Path(DEFAULT_CONFIG)),
        "config_sha256": sha256_file(Path(DEFAULT_CONFIG)),
        "stage11c_manifest_path": repository_path(STAGE11C_MANIFEST),
        "stage11c_manifest_sha256": sha256_file(STAGE11C_MANIFEST),
        "stage11c_profiles_path": repository_path(STAGE11C_PROFILES),
        "stage11c_profiles_sha256": sha256_file(STAGE11C_PROFILES),
        "stage11d_manifest_path": repository_path(STAGE11D_MANIFEST),
        "stage11d_manifest_sha256": sha256_file(STAGE11D_MANIFEST),
        "stage11d_diagnostics_path": repository_path(STAGE11D_DIAGNOSTICS),
        "stage11d_diagnostics_sha256": sha256_file(STAGE11D_DIAGNOSTICS),
        "stage11f_manifest_path": repository_path(STAGE11F_MANIFEST),
        "stage11f_manifest_sha256": sha256_file(STAGE11F_MANIFEST),
        "stage11f_metrics_path": repository_path(STAGE11F_METRICS),
        "stage11f_metrics_sha256": sha256_file(STAGE11F_METRICS),
        "stage11c_source_commit": stage11c_manifest.get("git_commit", ""),
        "stage11d_source_commit": stage11d_manifest.get("git_commit", ""),
        "stage11f_source_commit": stage11f_manifest.get("git_commit", ""),
        "source_provenance_checks": dict(provenance_checks),
        "transition_function": REPLAY_TRANSITION_QUALNAME,
        "spring2d_env_source_sha256": sha256_file(SPRING2D_ENV_SOURCE),
        "spring2d_dynamics_source_sha256": sha256_file(
            SPRING2D_DYNAMICS_SOURCE
        ),
        "source_state": "true",
        "window_transitions": WINDOW_TRANSITIONS,
        "exact_jacobian_shape": list(EXPECTED_JACOBIAN_SHAPE),
        "row_sqrt_weights": ROW_SQRT_WEIGHTS.tolist(),
        "channel_order": list(CHANNEL_NAMES),
        "parameter_order": list(PARAMETER_ORDER),
        "physical_scale": PHYSICAL_SCALE.tolist(),
        "primary_relative_step": PRIMARY_RELATIVE_STEP,
        "half_step_factor": HALF_STEP_FACTOR,
        "half_step_max_column_relative_discrepancy_threshold": (
            HALF_STEP_MAX_COLUMN_RELATIVE_DISCREPANCY
        ),
        "stage11b_svd_metrics_reused": True,
        "replay_next_state_used_for_exact_jacobian": False,
        "parameter_fit_invoked": False,
        "optimizer_invoked": False,
        "estimator_invoked": False,
        "identifier_invoked": False,
        "controller_invoked": False,
        "conditions": [
            condition
            for condition in CONDITIONS
            if condition in {run[0] for run in observed_runs}
        ],
        "seeds": sorted({run[1] for run in observed_runs}),
        "expected_runs": len(expected_runs),
        "actual_runs": len(observed_runs),
        "expected_windows": len(expected_windows),
        "actual_windows": len(rows),
        "output_root": repository_path(output_root),
        "mechanical_completeness": status in {"valid_smoke", "valid_full_run"},
        "mechanical_status": status,
        "smoke_non_authoritative": args.mode == "smoke",
    }
    mechanical = {
        "experiment_id": STAGE11G_EXPERIMENT_ID,
        "execution_mode": args.mode,
        "mechanical_status": status,
        "mechanical_completeness": manifest["mechanical_completeness"],
        **checks,
        "checks": checks,
    }
    return manifest, mechanical


def write_provenance(
    output_root: Path,
    manifest: dict[str, Any],
    mechanical: dict[str, Any],
) -> None:
    (output_root / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output_root / "command.txt").write_text(
        str(manifest["exact_command"]) + "\n"
    )
    (output_root / "mechanical_status.json").write_text(
        json.dumps(mechanical, indent=2, sort_keys=True) + "\n"
    )


def write_report(
    output_root: Path,
    manifest: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> None:
    lines = [
        "# Stage 11G: Exact-discrete Local Information Audit",
        "",
        "## Scope",
        "",
        f"- Execution mode: `{manifest['execution_mode']}`.",
        f"- Evidence level: `{manifest['evidence_level']}`; mechanical status: "
        f"`{manifest['mechanical_status']}`.",
        f"- Analyzed runs/windows: {manifest['actual_runs']}/"
        f"{manifest['actual_windows']}.",
        f"- Exact transition: `{manifest['transition_function']}`.",
        "- Exact output order: radial `r_dot` increment/dt, then angular "
        "`omega` increment/dt.",
        "- Jacobian: deterministic central differences at true "
        "`[lambda,kappa,beta]`, with relative step 1e-5 and a half-step repeat.",
        "- Every window stacks 70 transitions into a 140 x 3 Jacobian.",
        "- Stage 11B row weights, physical scaling, SVD, rank, physical weak "
        "direction, and conditional lambda information are reused directly.",
        "- Replay x_(t+1) is not consumed by the exact-discrete Jacobian.",
        "- No fit, optimizer, estimator, identifier, or controller is invoked.",
        "",
    ]
    if manifest["execution_mode"] == "smoke":
        lines += [
            "This local smoke artifact validates implementation mechanics only. "
            "It is non-authoritative and cannot support a scientific conclusion.",
            "",
        ]
    else:
        lines += [
            "This user-run formal artifact awaits human review. The generated "
            "report does not assign a scientific conclusion.",
            "",
        ]
    lines += [
        "## Neutral information summaries",
        "",
        "| Condition | Windows | Exact rank-3 | Affine rank-3 | Exact info | "
        "Affine info | Exact/affine info | Weak angle | Half-step max p95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {int(row['n_windows'])} | "
            f"{float(row['exact_rank3_fraction']):.3f} | "
            f"{float(row['affine_rank3_fraction']):.3f} | "
            f"{float(row['exact_conditional_lambda_information_abs_median']):.6g} | "
            f"{float(row['affine_conditional_lambda_information_abs_median']):.6g} | "
            f"{float(row['exact_to_affine_conditional_lambda_information_ratio_median']):.6g} | "
            f"{float(row['exact_affine_physical_weak_direction_angle_deg_median']):.4g} | "
            f"{float(row['half_step_max_column_relative_discrepancy_p95']):.3g} |"
        )
    lines += [
        "",
        "## Human review criteria (not automatically applied)",
        "",
        "- Exact-discrete local information retained: overall median "
        "exact/affine conditional-lambda-information ratio at least 0.5, at "
        "least 6 of 8 condition medians at least 0.25, and exact rank-3 "
        "fraction at least 0.95.",
        "- Exact-discrete information collapse: overall median ratio at most "
        "0.10 or at least 4 of 8 condition medians at most 0.10.",
        "- Otherwise: inconclusive.",
        "- Numerical derivative validity is a separate mechanical requirement.",
        "- These criteria are listed for human review only; this report does "
        "not select a category or assign PASS/FAIL/INCONCLUSIVE.",
        "",
        "## Limitations",
        "",
        "- Local true-state information does not establish estimator "
        "performance under state-estimation error or measurement noise.",
        "- Central differences evaluate local sensitivity only at true "
        "parameters.",
        "- Smoke metrics, if present, are implementation checks rather than "
        "scientific evidence.",
        "",
    ]
    (output_root / "stage11g_report.md").write_text("\n".join(lines))


def resolve_output_root(mode: str, output_root: Path | None) -> Path:
    if output_root is not None:
        return output_root.resolve()
    return OUTPUT_SMOKE if mode == "smoke" else OUTPUT_FORMAL


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--smoke", dest="mode", action="store_const", const="smoke")
    modes.add_argument("--full", dest="mode", action="store_const", const="full")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    args.output_root = resolve_output_root(args.mode, args.output_root)
    return args


def run(args: argparse.Namespace, argv: list[str] | None = None) -> Path:
    output_root = Path(args.output_root)
    git_state = git_context()
    if args.mode == "full" and not git_state["clean_for_formal"]:
        unexpected = "; ".join(git_state["unexpected_status_lines"][:5])
        raise SystemExit(
            "full mode requires clean committed Stage 11G source; only "
            "declared historical result roots are exceptions. "
            f"Unexpected status: {unexpected}"
        )
    if args.mode == "full" and output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(
            f"refusing to overwrite non-empty formal output root: {output_root}"
        )

    stage11c_manifest = json.loads(STAGE11C_MANIFEST.read_text())
    stage11d_manifest = json.loads(STAGE11D_MANIFEST.read_text())
    stage11f_manifest = json.loads(STAGE11F_MANIFEST.read_text())
    provenance_checks = source_provenance_checks(
        stage11c_manifest, stage11d_manifest, stage11f_manifest
    )
    if not all(provenance_checks.values()):
        failed = [
            name for name, valid in provenance_checks.items() if not valid
        ]
        raise RuntimeError(
            "Stage 11C/11D/11F or transition provenance mismatch before "
            "computation: " + ", ".join(failed)
        )

    profile_index = validate_and_index_stage11c_profiles(
        read_csv(STAGE11C_PROFILES), stage11c_manifest
    )
    diagnostic_index = validate_and_index_stage11d_diagnostics(
        read_csv(STAGE11D_DIAGNOSTICS), stage11d_manifest
    )
    closure_index = validate_and_index_stage11f_metrics(
        read_csv(STAGE11F_METRICS), stage11f_manifest
    )
    validate_source_alignment(
        profile_index, diagnostic_index, closure_index
    )
    full_expected_runs, full_expected_windows = expected_identity_sets(
        profile_index
    )
    if (
        len(full_expected_runs) != STAGE11G_EXPECTED_RUNS
        or len(full_expected_windows) != STAGE11G_EXPECTED_WINDOWS
    ):
        raise RuntimeError(
            "source matrix is not the expected 24-run, 710-window matrix"
        )

    selected = choose_identities(profile_index, args.mode)
    expected_windows = set(selected)
    expected_runs = {
        (condition, seed)
        for condition, seed, _, _ in expected_windows
    }
    if args.mode == "full" and (
        expected_runs != full_expected_runs
        or expected_windows != full_expected_windows
    ):
        raise RuntimeError("full mode did not select the exact formal matrix")

    output_root.mkdir(parents=True, exist_ok=True)
    replay = load_replay(DEFAULT_REPLAY)
    config = load_experiment_config(DEFAULT_CONFIG)
    cached_data: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    cached_true_params: dict[tuple[str, int], dict[str, Any]] = {}
    cached_affine_params: dict[tuple[str, int], dict[str, Any]] = {}
    derivative_caches: dict[
        tuple[str, int], dict[int, tuple[np.ndarray, np.ndarray]]
    ] = {}
    window_rows: list[dict[str, Any]] = []
    for identity in selected:
        condition, seed, _, _ = identity
        run_identity = (condition, seed)
        if run_identity not in replay:
            raise RuntimeError(f"source window is absent from replay: {identity}")
        if run_identity not in cached_data:
            data = arrays(replay[run_identity])
            verify_truth_metadata(condition, data, config)
            overrides = stage9j_overrides(config, condition)
            cached_data[run_identity] = data
            cached_true_params[run_identity] = dict(overrides["true_params"])
            cached_affine_params[run_identity] = dict(
                overrides["model_params"]
            )
            derivative_caches[run_identity] = {}
        window_rows.append(
            compute_window_information(
                identity,
                cached_data[run_identity],
                cached_true_params[run_identity],
                cached_affine_params[run_identity],
                derivative_cache=derivative_caches[run_identity],
            )
        )

    summaries = aggregate_rows(window_rows)
    write_dict_csv(
        output_root / "window_discrete_information_metrics.csv",
        window_rows,
    )
    write_dict_csv(
        output_root / "condition_discrete_information_summary.csv",
        summaries,
    )
    command = exact_command(argv)
    checks = exact_identity_checks(
        args.mode,
        expected_runs,
        expected_windows,
        window_rows,
        provenance_checks,
        source_alignment_complete=True,
        git_clean_for_formal=git_state["clean_for_formal"],
        required_outputs_complete=False,
    )
    manifest, mechanical = build_manifest(
        args,
        output_root,
        git_state,
        command,
        stage11c_manifest,
        stage11d_manifest,
        stage11f_manifest,
        provenance_checks,
        expected_runs,
        expected_windows,
        window_rows,
        checks,
    )
    write_provenance(output_root, manifest, mechanical)
    write_report(output_root, manifest, summaries)

    checks = exact_identity_checks(
        args.mode,
        expected_runs,
        expected_windows,
        window_rows,
        provenance_checks,
        source_alignment_complete=True,
        git_clean_for_formal=git_state["clean_for_formal"],
        required_outputs_complete=required_outputs_exist(output_root),
    )
    manifest, mechanical = build_manifest(
        args,
        output_root,
        git_state,
        command,
        stage11c_manifest,
        stage11d_manifest,
        stage11f_manifest,
        provenance_checks,
        expected_runs,
        expected_windows,
        window_rows,
        checks,
    )
    write_provenance(output_root, manifest, mechanical)
    write_report(output_root, manifest, summaries)
    if args.mode == "full" and not manifest["mechanical_completeness"]:
        raise RuntimeError(
            "full execution is mechanically invalid: "
            f"{manifest['mechanical_status']}"
        )
    return output_root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = run(args, argv)
    manifest = json.loads((output_root / "run_manifest.json").read_text())
    print(
        json.dumps(
            {
                "mode": args.mode,
                "output_root": str(output_root),
                "authoritative": False,
                "mechanical_status": manifest["mechanical_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
