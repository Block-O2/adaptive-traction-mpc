#!/usr/bin/env python3
"""Stage 11E block-aware lambda coverage calibration audit.

This runner keeps the Stage 11C true-state weighted least-squares point
estimate unchanged.  It calibrates only the lambda interval half-width with a
transition-level circular moving-block score bootstrap.  Generated reports are
neutral and never assign a scientific conclusion automatically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

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
    weighted_design,
)
from run_stage11d_residual_coverage_audit import (
    PROFILE_NAMES,
    STAGE11B_RUNNER,
    build_true_state_window,
    expected_identity_sets,
    parse_bool,
    repository_path,
    sha256_file,
    truth_affine_parameters,
    validate_and_index_stage11c_profiles,
    window_identity,
)

STAGE11C_ROOT = ROOT / "results" / "stage11c_state_source_audit"
STAGE11C_MANIFEST = STAGE11C_ROOT / "run_manifest.json"
STAGE11C_PROFILES = STAGE11C_ROOT / "paired_profile_summary.csv"
STAGE11D_ROOT = ROOT / "results" / "stage11d_residual_coverage_audit"
STAGE11D_MANIFEST = STAGE11D_ROOT / "run_manifest.json"
STAGE11D_DIAGNOSTICS = STAGE11D_ROOT / "window_residual_diagnostics.csv"
STAGE11D_RUNNER = ROOT / "scripts" / "run_stage11d_residual_coverage_audit.py"

OUTPUT_FORMAL = ROOT / "results" / "stage11e_block_coverage_calibration"
OUTPUT_SMOKE = (
    ROOT / "results" / "local" / "stage11e_block_coverage_calibration_smoke"
)
STAGE11E_EXPERIMENT_ID = "stage11e_block_coverage_calibration"
STAGE11E_EXPECTED_RUNS = 24
STAGE11E_EXPECTED_WINDOWS = 710
STAGE11E_REQUIRED_OUTPUTS = (
    "window_calibration_metrics.csv",
    "condition_calibration_summary.csv",
    "stage11e_report.md",
    "run_manifest.json",
    "command.txt",
    "mechanical_status.json",
)

IDENTITY_FIELDS = ("condition", "seed", "window_start", "window_end")
BLOCK_LENGTH = 10
BOOTSTRAP_REPLICATES = 2000
GLOBAL_BOOTSTRAP_SEED = 20260725
BOOTSTRAP_QUANTILE = 0.95
POINT_ESTIMATE_ATOL = 1.0e-10
DECLARED_UNTRACKED_INPUT_ROOTS = (
    STAGE11C_ROOT.relative_to(ROOT).as_posix(),
    STAGE11D_ROOT.relative_to(ROOT).as_posix(),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def validate_and_index_stage11d_diagnostics(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[tuple[str, int, int, int], dict[str, Any]]:
    """Validate one true-state Stage 11D row for every declared window."""
    indexed: dict[tuple[str, int, int, int], dict[str, Any]] = {}
    duplicates: list[tuple[str, int, int, int]] = []
    for row in rows:
        identity = window_identity(row)
        if identity in indexed:
            duplicates.append(identity)
        indexed[identity] = row
    if duplicates:
        raise RuntimeError(
            f"Stage 11D diagnostics contain duplicate windows: {duplicates[:3]}"
        )
    if len(indexed) != int(manifest["actual_windows"]):
        raise RuntimeError(
            "Stage 11D diagnostic identity count does not match its manifest: "
            f"{len(indexed)} != {manifest['actual_windows']}"
        )
    invalid = [
        identity
        for identity, row in indexed.items()
        if int(row["transitions"]) != WINDOW_TRANSITIONS
        or str(row["state_source"]) != "true"
        or not parse_bool(row["weighted_ls_lambda_matches_stage11c"])
    ]
    if invalid:
        raise RuntimeError(
            "Stage 11D rows must be true-state, 70-transition, reconciled "
            f"diagnostics; invalid identities: {invalid[:3]}"
        )
    return indexed


def source_provenance_checks(
    stage11c_manifest: dict[str, Any],
    stage11d_manifest: dict[str, Any],
) -> dict[str, bool]:
    """Bind Stage 11E to the exact saved Stage 11C/11D formal inputs."""
    current_replay_hash = sha256_file(Path(DEFAULT_REPLAY))
    current_config_hash = sha256_file(Path(DEFAULT_CONFIG))
    current_stage11b_hash = sha256_file(STAGE11B_RUNNER)
    return {
        "source_stage11c_valid_full_run": (
            stage11c_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11c_manifest.get("mechanical_completeness"))
        ),
        "source_stage11d_valid_full_run": (
            stage11d_manifest.get("mechanical_status") == "valid_full_run"
            and bool(stage11d_manifest.get("mechanical_completeness"))
        ),
        "stage11c_manifest_matches_stage11d": (
            stage11d_manifest.get("stage11c_manifest_sha256")
            == sha256_file(STAGE11C_MANIFEST)
        ),
        "stage11c_profiles_match_stage11d": (
            stage11d_manifest.get("stage11c_profile_sha256")
            == sha256_file(STAGE11C_PROFILES)
        ),
        "stage11d_runner_matches_manifest": (
            stage11d_manifest.get("script_sha256")
            == sha256_file(STAGE11D_RUNNER)
        ),
        "replay_matches_stage11c": (
            stage11c_manifest.get("replay_sha256") == current_replay_hash
        ),
        "replay_matches_stage11d": (
            stage11d_manifest.get("replay_sha256") == current_replay_hash
        ),
        "config_matches_stage11c": (
            stage11c_manifest.get("config_sha256") == current_config_hash
        ),
        "config_matches_stage11d": (
            stage11d_manifest.get("config_sha256") == current_config_hash
        ),
        "stage11b_runner_matches_stage11c": (
            stage11c_manifest.get("script_sha256") == current_stage11b_hash
        ),
        "stage11c_hash_checks_passed_in_stage11d": bool(
            stage11d_manifest.get("stage11c_input_hashes_match")
        ),
    }


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


def deterministic_window_seed(
    identity: tuple[str, int, int, int],
    global_seed: int = GLOBAL_BOOTSTRAP_SEED,
) -> int:
    payload = "|".join([str(int(global_seed)), *map(str, identity)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def transition_score_contributions(
    weighted_design_matrix: np.ndarray,
    weighted_residual: np.ndarray,
) -> np.ndarray:
    """Return paired-channel score contributions with shape (70, 3)."""
    matrix = np.asarray(weighted_design_matrix, dtype=float)
    residual = np.asarray(weighted_residual, dtype=float)
    expected_rows = WINDOW_TRANSITIONS * 2
    if matrix.shape != (expected_rows, len(PARAMETER_ORDER)):
        raise ValueError(
            f"weighted design must have shape "
            f"({expected_rows}, {len(PARAMETER_ORDER)})"
        )
    if residual.shape != (expected_rows,):
        raise ValueError(f"weighted residual must have shape ({expected_rows},)")
    paired_design = matrix.reshape(WINDOW_TRANSITIONS, 2, len(PARAMETER_ORDER))
    paired_residual = residual.reshape(WINDOW_TRANSITIONS, 2)
    channel_scores = paired_design * paired_residual[:, :, None]
    return np.sum(channel_scores, axis=1)


def circular_moving_block_indices(
    rng: np.random.Generator,
    replicates: int = BOOTSTRAP_REPLICATES,
    transitions: int = WINDOW_TRANSITIONS,
    block_length: int = BLOCK_LENGTH,
) -> np.ndarray:
    """Sample circular transition blocks and truncate each row exactly."""
    if transitions <= 0 or block_length <= 0 or replicates <= 0:
        raise ValueError("replicates, transitions, and block length must be positive")
    blocks_per_replicate = int(np.ceil(transitions / block_length))
    starts = rng.integers(
        0,
        transitions,
        size=(replicates, blocks_per_replicate),
        endpoint=False,
    )
    offsets = np.arange(block_length, dtype=int)
    sampled = (starts[:, :, None] + offsets[None, None, :]) % transitions
    return sampled.reshape(replicates, -1)[:, :transitions]


def calibrated_lambda_interval(
    H: np.ndarray,
    y: np.ndarray,
    bootstrap_seed: int,
) -> dict[str, Any]:
    """Calibrate interval width without accepting truth or refitting WLS."""
    Hw, yw = weighted_design(H, y, ROW_SQRT_WEIGHTS)
    optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0]
    weighted_residual = Hw @ optimum - yw
    transition_scores = transition_score_contributions(Hw, weighted_residual)
    score_sum = np.sum(transition_scores, axis=0)
    score_scale = max(
        float(np.linalg.norm(Hw) * np.linalg.norm(weighted_residual)),
        1.0,
    )
    if np.max(np.abs(score_sum)) > 1.0e-8 * score_scale:
        raise RuntimeError("weighted LS score is not numerically near zero")

    information = Hw.T @ Hw
    if np.linalg.matrix_rank(information) != len(PARAMETER_ORDER):
        raise RuntimeError("weighted information matrix is rank deficient")
    indices = circular_moving_block_indices(
        np.random.default_rng(int(bootstrap_seed)),
        replicates=BOOTSTRAP_REPLICATES,
        transitions=WINDOW_TRANSITIONS,
        block_length=BLOCK_LENGTH,
    )
    sampled_score_sums = np.sum(transition_scores[indices], axis=1)
    delta = -np.linalg.solve(information, sampled_score_sums.T).T
    half_width = float(
        np.quantile(np.abs(delta[:, 0]), BOOTSTRAP_QUANTILE)
    )
    lambda_optimum = float(optimum[0])
    return {
        "theta_wls": optimum.copy(),
        "lambda_wls": lambda_optimum,
        "half_width": half_width,
        "lower": lambda_optimum - half_width,
        "upper": lambda_optimum + half_width,
        "transition_scores": transition_scores,
        "bootstrap_indices": indices,
        "bootstrap_delta": delta,
        "information_condition_number": float(np.linalg.cond(information)),
        "wls_score_max_abs": float(np.max(np.abs(score_sum))),
    }


def evaluate_lambda_truth(
    interval: dict[str, Any],
    truth_lambda: float,
) -> bool:
    """Evaluate coverage only after the truth-free interval is constructed."""
    return bool(
        float(interval["lower"])
        <= float(truth_lambda)
        <= float(interval["upper"])
    )


def compute_window_calibration(
    identity: tuple[str, int, int, int],
    H: np.ndarray,
    y: np.ndarray,
    truth_lambda: float,
    lambda_profile: dict[str, Any],
    stage11d_row: dict[str, Any],
) -> dict[str, Any]:
    condition, seed, window_start, window_end = identity
    bootstrap_seed = deterministic_window_seed(identity)
    interval = calibrated_lambda_interval(H, y, bootstrap_seed)

    baseline_lambda = float(lambda_profile["true_lambda_at_minimum"])
    stage11d_lambda = float(stage11d_row["lambda_ls_optimum"])
    lambda_wls = float(interval["lambda_wls"])
    profile_abs_error = abs(lambda_wls - baseline_lambda)
    stage11d_abs_error = abs(lambda_wls - stage11d_lambda)
    point_estimate_unchanged = bool(
        np.isclose(
            lambda_wls,
            baseline_lambda,
            rtol=0.0,
            atol=POINT_ESTIMATE_ATOL,
        )
        and np.isclose(
            lambda_wls,
            stage11d_lambda,
            rtol=0.0,
            atol=POINT_ESTIMATE_ATOL,
        )
    )

    baseline_width = float(lambda_profile["true_lambda_region_width_95"])
    baseline_relative_width = float(
        lambda_profile["true_lambda_relative_width"]
    )
    calibrated_width = 2.0 * float(interval["half_width"])
    calibrated_relative_width = calibrated_width / max(
        abs(lambda_wls), 1.0e-12
    )
    width_inflation = (
        calibrated_width / baseline_width
        if baseline_width > np.finfo(float).eps
        else np.nan
    )
    baseline_coverage = parse_bool(
        lambda_profile["true_truth_in_region_95"]
    )
    calibrated_coverage = evaluate_lambda_truth(interval, truth_lambda)

    indices = np.asarray(interval["bootstrap_indices"], dtype=int)
    scores = np.asarray(interval["transition_scores"], dtype=float)
    return {
        "condition": condition,
        "seed": seed,
        "window_start": window_start,
        "window_end": window_end,
        "transitions": window_end - window_start + 1,
        "state_source": "true",
        "lambda_truth": float(truth_lambda),
        "lambda_wls_point_estimate": lambda_wls,
        "stage11c_lambda_point_estimate": baseline_lambda,
        "stage11d_lambda_point_estimate": stage11d_lambda,
        "stage11c_point_estimate_abs_error": profile_abs_error,
        "stage11d_point_estimate_abs_error": stage11d_abs_error,
        "point_estimate_comparison_atol": POINT_ESTIMATE_ATOL,
        "point_estimate_changed": not point_estimate_unchanged,
        "baseline_lambda_lower_95": float(
            lambda_profile["true_lambda_region_lower_95"]
        ),
        "baseline_lambda_upper_95": float(
            lambda_profile["true_lambda_region_upper_95"]
        ),
        "baseline_lambda_width_95": baseline_width,
        "baseline_lambda_relative_width_95": baseline_relative_width,
        "baseline_lambda_truth_coverage": baseline_coverage,
        "calibrated_lambda_half_width_95": float(interval["half_width"]),
        "calibrated_lambda_lower_95": float(interval["lower"]),
        "calibrated_lambda_upper_95": float(interval["upper"]),
        "calibrated_lambda_width_95": calibrated_width,
        "calibrated_lambda_relative_width_95": calibrated_relative_width,
        "calibrated_lambda_truth_coverage": calibrated_coverage,
        "coverage_gain_indicator": int(calibrated_coverage)
        - int(baseline_coverage),
        "width_inflation_factor": width_inflation,
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_block_length": BLOCK_LENGTH,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_transitions_per_replicate": int(indices.shape[1]),
        "bootstrap_min_transition_index": int(np.min(indices)),
        "bootstrap_max_transition_index": int(np.max(indices)),
        "paired_transition_score_rows": int(scores.shape[0]),
        "paired_transition_score_columns": int(scores.shape[1]),
        "information_condition_number": float(
            interval["information_condition_number"]
        ),
        "wls_score_max_abs": float(interval["wls_score_max_abs"]),
    }


def aggregate_rows(
    window_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: list[tuple[str, list[dict[str, Any]]]] = [
        (
            condition,
            [row for row in window_rows if row["condition"] == condition],
        )
        for condition in CONDITIONS
        if any(row["condition"] == condition for row in window_rows)
    ]
    grouped.append(("overall", window_rows))
    summaries: list[dict[str, Any]] = []
    for condition, rows in grouped:
        baseline = np.asarray(
            [bool(row["baseline_lambda_truth_coverage"]) for row in rows],
            dtype=float,
        )
        calibrated = np.asarray(
            [bool(row["calibrated_lambda_truth_coverage"]) for row in rows],
            dtype=float,
        )
        baseline_width = np.asarray(
            [float(row["baseline_lambda_relative_width_95"]) for row in rows]
        )
        calibrated_width = np.asarray(
            [float(row["calibrated_lambda_relative_width_95"]) for row in rows]
        )
        inflation = np.asarray(
            [float(row["width_inflation_factor"]) for row in rows]
        )
        inflation = inflation[np.isfinite(inflation)]
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
                "baseline_lambda_truth_coverage": float(np.mean(baseline)),
                "calibrated_lambda_truth_coverage": float(
                    np.mean(calibrated)
                ),
                "absolute_coverage_gain": float(
                    np.mean(calibrated) - np.mean(baseline)
                ),
                "baseline_relative_width_median": float(
                    np.median(baseline_width)
                ),
                "calibrated_relative_width_median": float(
                    np.median(calibrated_width)
                ),
                "width_inflation_factor_median": (
                    float(np.median(inflation)) if len(inflation) else np.nan
                ),
                "width_inflation_factor_p95": (
                    float(np.percentile(inflation, 95))
                    if len(inflation)
                    else np.nan
                ),
                "point_estimate_changed_fraction": float(
                    np.mean(
                        [bool(row["point_estimate_changed"]) for row in rows]
                    )
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
            len(expected_runs) == STAGE11E_EXPECTED_RUNS
            and len(expected_windows) == STAGE11E_EXPECTED_WINDOWS
            if mode == "full"
            else len(expected_runs) == 1
            and 1 <= len(expected_windows) <= 3
        ),
        "true_state_only": all(
            str(row["state_source"]) == "true" for row in rows
        ),
        "window_transitions_fixed": all(
            int(row["transitions"]) == WINDOW_TRANSITIONS for row in rows
        ),
        "paired_transition_scores_complete": all(
            int(row["paired_transition_score_rows"]) == WINDOW_TRANSITIONS
            and int(row["paired_transition_score_columns"])
            == len(PARAMETER_ORDER)
            for row in rows
        ),
        "bootstrap_contract_fixed": all(
            int(row["bootstrap_block_length"]) == BLOCK_LENGTH
            and int(row["bootstrap_replicates"]) == BOOTSTRAP_REPLICATES
            and int(row["bootstrap_transitions_per_replicate"])
            == WINDOW_TRANSITIONS
            for row in rows
        ),
        "wls_point_estimate_unchanged": all(
            not bool(row["point_estimate_changed"]) for row in rows
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
        (output_root / name).is_file() for name in STAGE11E_REQUIRED_OUTPUTS
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
        "experiment_id": STAGE11E_EXPERIMENT_ID,
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
        "stage11d_runner_path": repository_path(STAGE11D_RUNNER),
        "stage11d_runner_sha256": sha256_file(STAGE11D_RUNNER),
        "stage11c_source_commit": stage11c_manifest.get("git_commit", ""),
        "stage11d_source_commit": stage11d_manifest.get("git_commit", ""),
        "source_provenance_checks": dict(provenance_checks),
        "source_state": "true",
        "window_transitions": WINDOW_TRANSITIONS,
        "row_sqrt_weights": ROW_SQRT_WEIGHTS.tolist(),
        "parameter_order": list(PARAMETER_ORDER),
        "bootstrap_method": "transition_level_circular_moving_block_score",
        "bootstrap_global_seed": GLOBAL_BOOTSTRAP_SEED,
        "bootstrap_block_length": BLOCK_LENGTH,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_quantile": BOOTSTRAP_QUANTILE,
        "point_estimate_comparison_atol": POINT_ESTIMATE_ATOL,
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
        "experiment_id": STAGE11E_EXPERIMENT_ID,
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
        "# Stage 11E: Block-aware Lambda Coverage Calibration Audit",
        "",
        "## Scope",
        "",
        f"- Execution mode: `{manifest['execution_mode']}`.",
        f"- Evidence level: `{manifest['evidence_level']}`; mechanical status: "
        f"`{manifest['mechanical_status']}`.",
        f"- Analyzed runs/windows: {manifest['actual_runs']}/"
        f"{manifest['actual_windows']}.",
        "- Baseline: saved Stage 11C true-state one-dimensional lambda profile.",
        "- Treatment: transition-level circular moving-block score bootstrap.",
        "- The two weighted regression channels stay paired by transition.",
        f"- Fixed block length/replicates: {BLOCK_LENGTH}/"
        f"{BOOTSTRAP_REPLICATES}; every replicate contains exactly "
        f"{WINDOW_TRANSITIONS} transitions.",
        "- The original WLS optimum and Stage 11C profile calculation are not "
        "changed or refitted.",
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
        "## Neutral coverage and width summaries",
        "",
        "| Condition | Windows | Baseline coverage | Calibrated coverage | "
        "Absolute gain | Baseline rel. width | Calibrated rel. width | "
        "Median inflation | Point changed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {int(row['n_windows'])} | "
            f"{float(row['baseline_lambda_truth_coverage']):.3f} | "
            f"{float(row['calibrated_lambda_truth_coverage']):.3f} | "
            f"{float(row['absolute_coverage_gain']):.3f} | "
            f"{float(row['baseline_relative_width_median']):.4g} | "
            f"{float(row['calibrated_relative_width_median']):.4g} | "
            f"{float(row['width_inflation_factor_median']):.4g} | "
            f"{float(row['point_estimate_changed_fraction']):.3f} |"
        )
    lines += [
        "",
        "## Human review criteria (not automatically applied)",
        "",
        "- H1 materially supported: overall coverage gain at least 0.20 and "
        "at least 6 of 8 conditions gain at least 0.10.",
        "- H1 weakly supported or inconclusive: intermediate results.",
        "- H1 insufficient: overall gain below 0.10 and fewer than 4 of 8 "
        "conditions gain at least 0.10.",
        "- Practical calibration is a separate judgment requiring overall "
        "coverage at least 0.85 and median width inflation at most 5.",
        "- These criteria are listed for human review only; this report does "
        "not select any category or assign PASS/FAIL/INCONCLUSIVE.",
        "",
        "## Limitations",
        "",
        "- Passive rehabilitation trajectories only; no active excitation.",
        "- True-state regression is an oracle diagnostic, not a deployable "
        "estimator.",
        "- The moving-block result evaluates one fixed block length and one "
        "fixed bootstrap contract; no data-driven block selection is performed.",
        "- Truth lambda is used only to score coverage after interval "
        "construction.",
        "",
    ]
    (output_root / "stage11e_report.md").write_text("\n".join(lines))


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
            "full mode requires clean committed Stage 11E source; only the "
            "declared untracked Stage 11C/11D input roots are exceptions. "
            f"Unexpected status: {unexpected}"
        )
    if args.mode == "full" and output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(
            f"refusing to overwrite non-empty formal output root: {output_root}"
        )

    stage11c_manifest = json.loads(STAGE11C_MANIFEST.read_text())
    stage11d_manifest = json.loads(STAGE11D_MANIFEST.read_text())
    provenance_checks = source_provenance_checks(
        stage11c_manifest, stage11d_manifest
    )
    if not all(provenance_checks.values()):
        failed = [
            name for name, valid in provenance_checks.items() if not valid
        ]
        raise RuntimeError(
            "Stage 11C/11D provenance mismatch before computation: "
            + ", ".join(failed)
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
        len(full_expected_runs) != STAGE11E_EXPECTED_RUNS
        or len(full_expected_windows) != STAGE11E_EXPECTED_WINDOWS
    ):
        raise RuntimeError(
            "Stage 11C/11D source matrix is not the expected 24-run, "
            "710-window formal matrix"
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
    window_rows: list[dict[str, Any]] = []
    for identity in selected:
        condition, seed, expected_start, window_end = identity
        run_identity = (condition, seed)
        if run_identity not in replay:
            raise RuntimeError(f"source window is absent from replay: {identity}")
        if run_identity not in cached_data:
            cached_data[run_identity] = arrays(replay[run_identity])
            verify_truth_metadata(condition, cached_data[run_identity], config)
        data = cached_data[run_identity]
        model_params = stage9j_overrides(config, condition)["model_params"]
        H, y, actual_start, _ = build_true_state_window(
            condition, seed, data, model_params, window_end
        )
        if actual_start != expected_start:
            raise RuntimeError(
                f"source identity does not match reconstructed window: "
                f"{identity}, reconstructed start={actual_start}"
            )
        truth = truth_affine_parameters(data)
        window_rows.append(
            compute_window_calibration(
                identity,
                H,
                y,
                float(truth[0]),
                profile_index[identity]["lambda_1d"],
                diagnostic_index[identity],
            )
        )

    if any(bool(row["point_estimate_changed"]) for row in window_rows):
        raise RuntimeError(
            "WLS point estimate changed relative to Stage 11C/11D"
        )

    summaries = aggregate_rows(window_rows)
    write_dict_csv(output_root / "window_calibration_metrics.csv", window_rows)
    write_dict_csv(
        output_root / "condition_calibration_summary.csv", summaries
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
