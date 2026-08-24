#!/usr/bin/env python3
"""Stage 11F exact discrete one-step closure audit.

The audit reuses the exact ``step_dynamics`` function called by
``Spring2DEnv.step``.  It performs no parameter fitting, optimization,
estimation, identification, or controller execution.  Generated reports are
neutral and never apply the preregistered scientific criteria automatically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    ROW_SQRT_WEIGHTS,
    WINDOW_TRANSITIONS,
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
from traction_mpc.envs import spring2d_env
from traction_mpc.models import spring2d_dynamics

STAGE11C_ROOT = ROOT / "results" / "stage11c_state_source_audit"
STAGE11C_MANIFEST = STAGE11C_ROOT / "run_manifest.json"
STAGE11C_PROFILES = STAGE11C_ROOT / "paired_profile_summary.csv"
STAGE11D_ROOT = ROOT / "results" / "stage11d_residual_coverage_audit"
STAGE11D_MANIFEST = STAGE11D_ROOT / "run_manifest.json"
STAGE11D_DIAGNOSTICS = STAGE11D_ROOT / "window_residual_diagnostics.csv"
STAGE11D_RUNNER = ROOT / "scripts" / "run_stage11d_residual_coverage_audit.py"
STAGE11E_ROOT = ROOT / "results" / "stage11e_block_coverage_calibration"
STAGE11E_MANIFEST = STAGE11E_ROOT / "run_manifest.json"
STAGE11E_SUMMARY = STAGE11E_ROOT / "condition_calibration_summary.csv"

SPRING2D_ENV_SOURCE = ROOT / "src" / "traction_mpc" / "envs" / "spring2d_env.py"
SPRING2D_DYNAMICS_SOURCE = (
    ROOT / "src" / "traction_mpc" / "models" / "spring2d_dynamics.py"
)
REPLAY_TRANSITION_QUALNAME = (
    "traction_mpc.models.spring2d_dynamics.step_dynamics"
)

OUTPUT_FORMAL = ROOT / "results" / "stage11f_discrete_closure_audit"
OUTPUT_SMOKE = (
    ROOT / "results" / "local" / "stage11f_discrete_closure_audit_smoke"
)
STAGE11F_EXPERIMENT_ID = "stage11f_discrete_closure_audit"
STAGE11F_EXPECTED_RUNS = 24
STAGE11F_EXPECTED_WINDOWS = 710
STAGE11F_REQUIRED_OUTPUTS = (
    "window_discrete_closure_metrics.csv",
    "condition_discrete_closure_summary.csv",
    "stage11f_report.md",
    "run_manifest.json",
    "command.txt",
    "mechanical_status.json",
)
STATE_NAMES = ("theta", "omega", "r", "r_dot")
CHANNEL_NAMES = ("radial", "angular")
DECLARED_UNTRACKED_INPUT_ROOTS = (
    STAGE11C_ROOT.relative_to(ROOT).as_posix(),
    STAGE11D_ROOT.relative_to(ROOT).as_posix(),
    STAGE11E_ROOT.relative_to(ROOT).as_posix(),
)

TransitionFunction = Callable[
    [np.ndarray, np.ndarray, float, dict[str, Any]], np.ndarray
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def replay_generation_transition(
    state: np.ndarray,
    action: np.ndarray,
    dt: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Call the exact function bound and used inside ``Spring2DEnv.step``."""
    return spring2d_env.step_dynamics(state, action, dt, params)


def transition_reuse_checks() -> dict[str, bool]:
    """Verify the environment and model expose the same transition object."""
    return {
        "environment_uses_model_step_dynamics_object": (
            spring2d_env.step_dynamics is spring2d_dynamics.step_dynamics
        ),
        "transition_function_source_is_spring2d_dynamics": (
            inspect.getmodule(spring2d_env.step_dynamics)
            is spring2d_dynamics
        ),
    }


def source_provenance_checks(
    stage11c_manifest: dict[str, Any],
    stage11d_manifest: dict[str, Any],
    stage11e_manifest: dict[str, Any],
) -> dict[str, bool]:
    current_replay_hash = sha256_file(Path(DEFAULT_REPLAY))
    current_config_hash = sha256_file(Path(DEFAULT_CONFIG))
    current_stage11b_hash = sha256_file(STAGE11B_RUNNER)
    checks = {
        "source_stage11c_valid_full_run": (
            stage11c_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11c_manifest.get("mechanical_completeness"))
        ),
        "source_stage11d_valid_full_run": (
            stage11d_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11d_manifest.get("mechanical_completeness"))
        ),
        "source_stage11e_valid_full_run": (
            stage11e_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11e_manifest.get("mechanical_completeness"))
            and int(stage11e_manifest.get("actual_runs", -1))
            == STAGE11F_EXPECTED_RUNS
            and int(stage11e_manifest.get("actual_windows", -1))
            == STAGE11F_EXPECTED_WINDOWS
        ),
        "stage11c_manifest_matches_stage11d": (
            stage11d_manifest.get("stage11c_manifest_sha256")
            == sha256_file(STAGE11C_MANIFEST)
        ),
        "stage11c_profiles_match_stage11d": (
            stage11d_manifest.get("stage11c_profile_sha256")
            == sha256_file(STAGE11C_PROFILES)
        ),
        "stage11d_manifest_matches_stage11e": (
            stage11e_manifest.get("stage11d_manifest_sha256")
            == sha256_file(STAGE11D_MANIFEST)
        ),
        "stage11d_diagnostics_match_stage11e": (
            stage11e_manifest.get("stage11d_diagnostics_sha256")
            == sha256_file(STAGE11D_DIAGNOSTICS)
        ),
        "stage11d_runner_matches_manifests": (
            stage11d_manifest.get("script_sha256")
            == sha256_file(STAGE11D_RUNNER)
            == stage11e_manifest.get("stage11d_runner_sha256")
        ),
        "replay_matches_all_sources": (
            stage11c_manifest.get("replay_sha256")
            == current_replay_hash
            == stage11d_manifest.get("replay_sha256")
            == stage11e_manifest.get("replay_sha256")
        ),
        "config_matches_all_sources": (
            stage11c_manifest.get("config_sha256")
            == current_config_hash
            == stage11d_manifest.get("config_sha256")
            == stage11e_manifest.get("config_sha256")
        ),
        "stage11b_runner_matches_stage11c": (
            stage11c_manifest.get("script_sha256")
            == current_stage11b_hash
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
) -> None:
    profile_identities = set(profile_index)
    diagnostic_identities = set(diagnostic_index)
    if profile_identities != diagnostic_identities:
        missing = sorted(profile_identities - diagnostic_identities)
        extra = sorted(diagnostic_identities - profile_identities)
        raise RuntimeError(
            "Stage 11C/11D window identities are not exactly aligned; "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )


def action_within_limits(
    action: np.ndarray,
    true_params: dict[str, Any],
) -> bool:
    values = np.asarray(action, dtype=float)
    return bool(
        values.shape == (2,)
        and np.all(np.isfinite(values))
        and abs(float(values[0]))
        <= float(true_params["F_tan_max"]) + 1.0e-12
        and abs(float(values[1]))
        <= float(true_params["F_rad_max"]) + 1.0e-12
    )


def acceleration_equivalent_channels(
    state_residuals: np.ndarray,
    dt: float,
) -> np.ndarray:
    """Return Stage 11D channel order: radial first, angular second."""
    residuals = np.asarray(state_residuals, dtype=float)
    if residuals.ndim != 2 or residuals.shape[1] != len(STATE_NAMES):
        raise ValueError("state residuals must have shape (transitions, 4)")
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt must be finite and positive")
    radial = residuals[:, 3] / float(dt)
    angular = residuals[:, 1] / float(dt)
    return np.column_stack([radial, angular])


def weighted_closure_channels(
    acceleration_channels: np.ndarray,
) -> np.ndarray:
    channels = np.asarray(acceleration_channels, dtype=float)
    if channels.ndim != 2 or channels.shape[1] != len(CHANNEL_NAMES):
        raise ValueError("acceleration channels must be [radial, angular]")
    return channels * ROW_SQRT_WEIGHTS[None, :]


def rms(values: np.ndarray) -> float:
    data = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(np.square(data))))


def compact_json(values: np.ndarray) -> str:
    return json.dumps(
        np.asarray(values, dtype=float).tolist(),
        separators=(",", ":"),
        allow_nan=False,
    )


def compute_window_closure(
    identity: tuple[str, int, int, int],
    data: dict[str, np.ndarray],
    true_params: dict[str, Any],
    stage11d_row: dict[str, Any],
    transition_fn: TransitionFunction | None = None,
) -> dict[str, Any]:
    """Evaluate exact one-step closure; no fit or optimizer is present."""
    condition, seed, window_start, window_end = identity
    transition = (
        replay_generation_transition if transition_fn is None else transition_fn
    )
    dt = float(true_params["dt"])
    true_states = np.asarray(data["true"], dtype=float)
    actions = np.asarray(data["action"], dtype=float)
    predicted_states: list[np.ndarray] = []
    target_states: list[np.ndarray] = []
    aligned_actions: list[np.ndarray] = []
    for step in range(window_start, window_end + 1):
        x_t = true_states[step - 1]
        u_t = actions[step]
        x_next = true_states[step]
        if not action_within_limits(u_t, true_params):
            raise RuntimeError(
                f"{identity}: replay action at step {step} is outside "
                "the environment action limits"
            )
        predicted = np.asarray(
            transition(x_t, u_t, dt, true_params), dtype=float
        )
        if predicted.shape != (len(STATE_NAMES),):
            raise RuntimeError(
                f"{identity}: transition returned shape {predicted.shape}"
            )
        predicted_states.append(predicted)
        target_states.append(x_next.copy())
        aligned_actions.append(u_t.copy())

    predicted_array = np.asarray(predicted_states, dtype=float)
    target_array = np.asarray(target_states, dtype=float)
    action_array = np.asarray(aligned_actions, dtype=float)
    residuals = predicted_array - target_array
    if residuals.shape != (WINDOW_TRANSITIONS, len(STATE_NAMES)):
        raise RuntimeError(
            f"{identity}: expected {WINDOW_TRANSITIONS} aligned transitions"
        )
    acceleration_channels = acceleration_equivalent_channels(residuals, dt)
    weighted_channels = weighted_closure_channels(acceleration_channels)

    affine_radial_weighted_rms = float(
        stage11d_row["truth_radial_weighted_residual_rms"]
    )
    affine_angular_weighted_rms = float(
        stage11d_row["truth_angular_weighted_residual_rms"]
    )
    affine_weighted_rms = float(
        np.sqrt(
            0.5
            * (
                affine_radial_weighted_rms**2
                + affine_angular_weighted_rms**2
            )
        )
    )
    discrete_weighted_rms = rms(weighted_channels)
    if affine_weighted_rms <= np.finfo(float).eps:
        raise RuntimeError(f"{identity}: affine baseline RMS is zero")
    ratio = discrete_weighted_rms / affine_weighted_rms

    row: dict[str, Any] = {
        "condition": condition,
        "seed": seed,
        "window_start": window_start,
        "window_end": window_end,
        "transitions": window_end - window_start + 1,
        "state_source": "true",
        "transition_function": REPLAY_TRANSITION_QUALNAME,
        "transition_alignment": "true[step-1],action[step]->true[step]",
        "true_parameter_source": "stage9j_condition_true_params",
        "dt": dt,
        "true_m": float(true_params["m"]),
        "true_k": float(true_params["k"]),
        "true_b_r": float(true_params["b_r"]),
        "all_recorded_actions_within_limits": all(
            action_within_limits(action, true_params)
            for action in action_array
        ),
        "radial_channel_index": 0,
        "angular_channel_index": 1,
        "radial_row_sqrt_weight": float(ROW_SQRT_WEIGHTS[0]),
        "angular_row_sqrt_weight": float(ROW_SQRT_WEIGHTS[1]),
        "discrete_radial_acceleration_equivalent_rms": rms(
            acceleration_channels[:, 0]
        ),
        "discrete_angular_acceleration_equivalent_rms": rms(
            acceleration_channels[:, 1]
        ),
        "discrete_radial_weighted_rms": rms(weighted_channels[:, 0]),
        "discrete_angular_weighted_rms": rms(weighted_channels[:, 1]),
        "discrete_weighted_residual_rms": discrete_weighted_rms,
        "affine_radial_weighted_residual_rms": (
            affine_radial_weighted_rms
        ),
        "affine_angular_weighted_residual_rms": (
            affine_angular_weighted_rms
        ),
        "affine_weighted_residual_rms": affine_weighted_rms,
        "discrete_to_affine_weighted_rms_ratio": ratio,
        "optimizer_invoked": False,
        "parameter_fit_invoked": False,
        "estimator_invoked": False,
        "identifier_invoked": False,
    }
    for index, name in enumerate(STATE_NAMES):
        component = residuals[:, index]
        row[f"{name}_residual_mean"] = float(np.mean(component))
        row[f"{name}_residual_rms"] = rms(component)
        row[f"{name}_residual_max_abs"] = float(
            np.max(np.abs(component))
        )
        row[f"{name}_residual_trajectory_json"] = compact_json(component)
    row["radial_acceleration_equivalent_trajectory_json"] = compact_json(
        acceleration_channels[:, 0]
    )
    row["angular_acceleration_equivalent_trajectory_json"] = compact_json(
        acceleration_channels[:, 1]
    )
    row["weighted_radial_residual_trajectory_json"] = compact_json(
        weighted_channels[:, 0]
    )
    row["weighted_angular_residual_trajectory_json"] = compact_json(
        weighted_channels[:, 1]
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
        ratio = np.asarray(
            [
                float(row["discrete_to_affine_weighted_rms_ratio"])
                for row in rows
            ]
        )
        discrete = np.asarray(
            [float(row["discrete_weighted_residual_rms"]) for row in rows]
        )
        affine = np.asarray(
            [float(row["affine_weighted_residual_rms"]) for row in rows]
        )
        summaries.append(
            {
                "condition": condition,
                "n_runs": len(
                    {
                        (str(row["condition"]), int(row["seed"]))
                        for row in rows
                    }
                ),
                "n_windows": len(rows),
                "discrete_weighted_residual_rms_median": float(
                    np.median(discrete)
                ),
                "discrete_weighted_residual_rms_p95": float(
                    np.percentile(discrete, 95)
                ),
                "affine_weighted_residual_rms_median": float(
                    np.median(affine)
                ),
                "affine_weighted_residual_rms_p95": float(
                    np.percentile(affine, 95)
                ),
                "discrete_to_affine_weighted_rms_ratio_median": float(
                    np.median(ratio)
                ),
                "discrete_to_affine_weighted_rms_ratio_p95": float(
                    np.percentile(ratio, 95)
                ),
                "discrete_to_affine_weighted_rms_ratio_max": float(
                    np.max(ratio)
                ),
                "all_recorded_actions_within_limits": all(
                    bool(row["all_recorded_actions_within_limits"])
                    for row in rows
                ),
                "optimizer_invoked_fraction": float(
                    np.mean([bool(row["optimizer_invoked"]) for row in rows])
                ),
                "parameter_fit_invoked_fraction": float(
                    np.mean(
                        [bool(row["parameter_fit_invoked"]) for row in rows]
                    )
                ),
                "estimator_invoked_fraction": float(
                    np.mean([bool(row["estimator_invoked"]) for row in rows])
                ),
                "identifier_invoked_fraction": float(
                    np.mean([bool(row["identifier_invoked"]) for row in rows])
                ),
            }
        )
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
            len(expected_runs) == STAGE11F_EXPECTED_RUNS
            and len(expected_windows) == STAGE11F_EXPECTED_WINDOWS
            if mode == "full"
            else len(expected_runs) == 1
            and 1 <= len(expected_windows) <= 3
        ),
        "window_transitions_fixed": all(
            int(row["transitions"]) == WINDOW_TRANSITIONS for row in rows
        ),
        "true_state_only": all(
            str(row["state_source"]) == "true" for row in rows
        ),
        "transition_function_exact": all(
            str(row["transition_function"]) == REPLAY_TRANSITION_QUALNAME
            for row in rows
        ),
        "transition_alignment_exact": all(
            str(row["transition_alignment"])
            == "true[step-1],action[step]->true[step]"
            for row in rows
        ),
        "true_condition_parameters_used": all(
            str(row["true_parameter_source"])
            == "stage9j_condition_true_params"
            for row in rows
        ),
        "recorded_actions_within_limits": all(
            bool(row["all_recorded_actions_within_limits"]) for row in rows
        ),
        "channel_order_and_weights_fixed": all(
            int(row["radial_channel_index"]) == 0
            and int(row["angular_channel_index"]) == 1
            and float(row["radial_row_sqrt_weight"])
            == float(ROW_SQRT_WEIGHTS[0])
            and float(row["angular_row_sqrt_weight"])
            == float(ROW_SQRT_WEIGHTS[1])
            for row in rows
        ),
        "no_fit_optimizer_estimator_identifier": all(
            not bool(row["optimizer_invoked"])
            and not bool(row["parameter_fit_invoked"])
            and not bool(row["estimator_invoked"])
            and not bool(row["identifier_invoked"])
            for row in rows
        ),
        "finite_primary_metric": all(
            np.isfinite(
                float(row["discrete_to_affine_weighted_rms_ratio"])
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
        (output_root / name).is_file() for name in STAGE11F_REQUIRED_OUTPUTS
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
    stage11e_manifest: dict[str, Any],
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
        "experiment_id": STAGE11F_EXPERIMENT_ID,
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
        "stage11e_manifest_path": repository_path(STAGE11E_MANIFEST),
        "stage11e_manifest_sha256": sha256_file(STAGE11E_MANIFEST),
        "stage11e_summary_path": repository_path(STAGE11E_SUMMARY),
        "stage11e_summary_sha256": sha256_file(STAGE11E_SUMMARY),
        "stage11c_source_commit": stage11c_manifest.get("git_commit", ""),
        "stage11d_source_commit": stage11d_manifest.get("git_commit", ""),
        "stage11e_source_commit": stage11e_manifest.get("git_commit", ""),
        "source_provenance_checks": dict(provenance_checks),
        "transition_function": REPLAY_TRANSITION_QUALNAME,
        "transition_call_path": "Spring2DEnv.step->step_dynamics",
        "spring2d_env_source_sha256": sha256_file(SPRING2D_ENV_SOURCE),
        "spring2d_dynamics_source_sha256": sha256_file(
            SPRING2D_DYNAMICS_SOURCE
        ),
        "source_state": "true",
        "window_transitions": WINDOW_TRANSITIONS,
        "row_sqrt_weights": ROW_SQRT_WEIGHTS.tolist(),
        "channel_order": list(CHANNEL_NAMES),
        "parameter_order": list(PARAMETER_ORDER),
        "parameter_fit_invoked": False,
        "optimizer_invoked": False,
        "estimator_invoked": False,
        "identifier_invoked": False,
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
        "experiment_id": STAGE11F_EXPERIMENT_ID,
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
        "# Stage 11F: Exact Discrete One-step Closure Audit",
        "",
        "## Scope",
        "",
        f"- Execution mode: `{manifest['execution_mode']}`.",
        f"- Evidence level: `{manifest['evidence_level']}`; mechanical status: "
        f"`{manifest['mechanical_status']}`.",
        f"- Analyzed runs/windows: {manifest['actual_runs']}/"
        f"{manifest['actual_windows']}.",
        f"- Reused transition: `{manifest['transition_function']}` through "
        "`Spring2DEnv.step -> step_dynamics`.",
        "- Alignment: replay `action[step]` maps replay true "
        "`state[step-1]` to true `state[step]`.",
        "- Parameters: exact Stage 9J condition true parameters and dt.",
        "- No parameter fit, optimizer, estimator, identifier, or controller "
        "is invoked.",
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
        "## Neutral closure summaries",
        "",
        "| Condition | Windows | Discrete weighted RMS | Affine weighted RMS | "
        "Median ratio | Ratio p95 | Actions in limits |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {int(row['n_windows'])} | "
            f"{float(row['discrete_weighted_residual_rms_median']):.6g} | "
            f"{float(row['affine_weighted_residual_rms_median']):.6g} | "
            f"{float(row['discrete_to_affine_weighted_rms_ratio_median']):.6g} | "
            f"{float(row['discrete_to_affine_weighted_rms_ratio_p95']):.6g} | "
            f"{bool(row['all_recorded_actions_within_limits'])} |"
        )
    lines += [
        "",
        "## Residual construction",
        "",
        "- Raw residual is exact predicted next state minus replay true next "
        "state in `[theta, omega, r, r_dot]` order.",
        "- Radial acceleration-equivalent residual is the `r_dot` one-step "
        "residual divided by dt.",
        "- Angular acceleration-equivalent residual is the `omega` one-step "
        "residual divided by dt.",
        "- Channels retain Stage 11D order `[radial, angular]` and square-root "
        "weights `[0.6, 0.25]`.",
        "- The primary ratio divides the combined discrete weighted RMS by the "
        "unchanged combined Stage 11D affine truth weighted RMS.",
        "",
        "## Human review criteria (not automatically applied)",
        "",
        "- Finite-difference/continuous-regression bias supported: overall "
        "median ratio at most 0.01 and at least 7 of 8 conditions have median "
        "ratio at most 0.05.",
        "- Discrete/model mismatch retained: overall median ratio at least "
        "0.25 or at least 4 of 8 conditions have median ratio at least 0.25.",
        "- Otherwise: inconclusive.",
        "- These criteria are listed for human review only; this report does "
        "not select a category or assign PASS/FAIL/INCONCLUSIVE.",
        "",
        "## Limitations",
        "",
        "- This is a replay-closure diagnostic, not a closed-loop experiment.",
        "- Saved replay actions are used directly after mechanically confirming "
        "that they lie within the environment action limits.",
        "- The discrete acceleration-equivalent residual and affine residual "
        "retain the same channel weights but arise from different residual "
        "constructions.",
        "",
    ]
    (output_root / "stage11f_report.md").write_text("\n".join(lines))


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
            "full mode requires clean committed Stage 11F source; only "
            "declared untracked Stage 11C/11D/11E result roots are exceptions. "
            f"Unexpected status: {unexpected}"
        )
    if args.mode == "full" and output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(
            f"refusing to overwrite non-empty formal output root: {output_root}"
        )

    stage11c_manifest = json.loads(STAGE11C_MANIFEST.read_text())
    stage11d_manifest = json.loads(STAGE11D_MANIFEST.read_text())
    stage11e_manifest = json.loads(STAGE11E_MANIFEST.read_text())
    provenance_checks = source_provenance_checks(
        stage11c_manifest, stage11d_manifest, stage11e_manifest
    )
    if not all(provenance_checks.values()):
        failed = [
            name for name, valid in provenance_checks.items() if not valid
        ]
        raise RuntimeError(
            "Stage 11C/11D/11E or transition provenance mismatch before "
            "computation: " + ", ".join(failed)
        )

    profile_index = validate_and_index_stage11c_profiles(
        read_csv(STAGE11C_PROFILES), stage11c_manifest
    )
    diagnostic_index = validate_and_index_stage11d_diagnostics(
        read_csv(STAGE11D_DIAGNOSTICS), stage11d_manifest
    )
    validate_source_alignment(profile_index, diagnostic_index)
    full_expected_runs, full_expected_windows = expected_identity_sets(
        profile_index
    )
    if (
        len(full_expected_runs) != STAGE11F_EXPECTED_RUNS
        or len(full_expected_windows) != STAGE11F_EXPECTED_WINDOWS
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
    window_rows: list[dict[str, Any]] = []
    for identity in selected:
        condition, seed, _, _ = identity
        run_identity = (condition, seed)
        if run_identity not in replay:
            raise RuntimeError(f"source window is absent from replay: {identity}")
        if run_identity not in cached_data:
            data = arrays(replay[run_identity])
            verify_truth_metadata(condition, data, config)
            cached_data[run_identity] = data
            cached_true_params[run_identity] = dict(
                stage9j_overrides(config, condition)["true_params"]
            )
        window_rows.append(
            compute_window_closure(
                identity,
                cached_data[run_identity],
                cached_true_params[run_identity],
                diagnostic_index[identity],
            )
        )

    summaries = aggregate_rows(window_rows)
    write_dict_csv(
        output_root / "window_discrete_closure_metrics.csv", window_rows
    )
    write_dict_csv(
        output_root / "condition_discrete_closure_summary.csv", summaries
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
        stage11e_manifest,
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
        stage11e_manifest,
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
