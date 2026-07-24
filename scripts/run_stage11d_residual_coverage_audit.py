#!/usr/bin/env python3
"""Stage 11D true-state residual and lambda-profile coverage diagnostic.

The diagnostic is deliberately read-only with respect to Stage 11C.  It uses
the exact Stage 11C window identities and the unchanged Stage 11B affine
regression/weighting functions.  Generated reports are descriptive and never
choose between the competing scientific explanations automatically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

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
    build_affine_window,
    verify_truth_metadata,
    weighted_design,
)

STAGE11C_ROOT = ROOT / "results" / "stage11c_state_source_audit"
STAGE11C_MANIFEST = STAGE11C_ROOT / "run_manifest.json"
STAGE11C_PROFILES = STAGE11C_ROOT / "paired_profile_summary.csv"
OUTPUT_FORMAL = ROOT / "results" / "stage11d_residual_coverage_audit"
OUTPUT_SMOKE = ROOT / "results" / "local" / "stage11d_residual_coverage_audit_smoke"
PROFILE_NAMES = frozenset({"lambda_1d", "lambda_kappa_2d"})
CHANNEL_NAMES = ("radial", "angular")
LAGS = (1, 5, 10)
PROXY_NAMES = ("state_magnitude", "state_rate_magnitude", "action_magnitude")
IDENTITY_FIELDS = ("condition", "seed", "window_start", "window_end")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def window_identity(row: dict[str, Any]) -> tuple[str, int, int, int]:
    return (
        str(row["condition"]),
        int(row["seed"]),
        int(row["window_start"]),
        int(row["window_end"]),
    )


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"cannot parse boolean value {value!r}")


def validate_and_index_stage11c_profiles(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[tuple[str, int, int, int], dict[str, dict[str, Any]]]:
    """Validate exact Stage 11C profile identities and index them by window."""
    grouped: dict[
        tuple[str, int, int, int], dict[str, dict[str, Any]]
    ] = defaultdict(dict)
    duplicate_profiles: list[tuple[tuple[str, int, int, int], str]] = []
    for row in rows:
        identity = window_identity(row)
        profile = str(row["profile"])
        if profile in grouped[identity]:
            duplicate_profiles.append((identity, profile))
        grouped[identity][profile] = row
    if duplicate_profiles:
        raise RuntimeError(
            f"Stage 11C profile rows contain duplicates: {duplicate_profiles[:3]}"
        )
    invalid = [
        identity
        for identity, profiles in grouped.items()
        if set(profiles) != PROFILE_NAMES
    ]
    if invalid:
        raise RuntimeError(
            "Stage 11C windows must each contain exactly lambda_1d and "
            f"lambda_kappa_2d profiles; invalid identities: {invalid[:3]}"
        )
    expected_windows = int(manifest["actual_windows"])
    if len(grouped) != expected_windows:
        raise RuntimeError(
            "Stage 11C profile identity count does not match its manifest: "
            f"{len(grouped)} != {expected_windows}"
        )
    observed_runs = {(identity[0], identity[1]) for identity in grouped}
    expected_runs = {
        (str(condition), int(seed))
        for condition in manifest["conditions"]
        for seed in manifest["seeds"]
    }
    if observed_runs != expected_runs:
        missing = sorted(expected_runs - observed_runs)
        extra = sorted(observed_runs - expected_runs)
        raise RuntimeError(
            f"Stage 11C run identities differ from manifest; "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    return dict(grouped)


def split_residual_channels(residual: np.ndarray) -> dict[str, np.ndarray]:
    values = np.asarray(residual, dtype=float)
    if values.ndim != 1 or len(values) % len(CHANNEL_NAMES):
        raise ValueError("residual must be a flat sequence of complete two-channel rows")
    matrix = values.reshape(-1, len(CHANNEL_NAMES))
    return {
        channel: matrix[:, index].copy()
        for index, channel in enumerate(CHANNEL_NAMES)
    }


def lag_autocorrelation(values: np.ndarray, lag: int) -> float:
    series = np.asarray(values, dtype=float)
    if lag <= 0 or lag >= len(series):
        return np.nan
    centered = series - np.mean(series)
    denominator = float(centered @ centered)
    if denominator <= np.finfo(float).eps:
        return np.nan
    return float(centered[:-lag] @ centered[lag:] / denominator)


def safe_correlation(left: np.ndarray, right: np.ndarray) -> float:
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(valid) < 3:
        return np.nan
    x = x[valid]
    y = y[valid]
    if np.std(x) <= np.finfo(float).eps or np.std(y) <= np.finfo(float).eps:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def residual_statistics(values: np.ndarray) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(data)),
        "std": float(np.std(data)),
        "rms": float(np.sqrt(np.mean(np.square(data)))),
    }


def normalized_scores(
    design: np.ndarray,
    residual: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(design, dtype=float)
    error = np.asarray(residual, dtype=float)
    raw = matrix.T @ error
    residual_norm = float(np.linalg.norm(error))
    denominators = np.linalg.norm(matrix, axis=0) * residual_norm
    normalized = np.divide(
        raw,
        denominators,
        out=np.full_like(raw, np.nan, dtype=float),
        where=denominators > np.finfo(float).eps,
    )
    return raw, normalized


def build_true_state_window(
    condition: str,
    seed: int,
    data: dict[str, np.ndarray],
    model_params: dict[str, Any],
    window_end: int,
) -> tuple[np.ndarray, np.ndarray, int, dict[str, np.ndarray]]:
    """Build unchanged affine rows and aligned proxies from replay true states."""
    H, y, window_start = build_affine_window(
        condition,
        seed,
        data,
        model_params,
        window_end,
        state_source="true",
    )
    true_states = np.asarray(data["true"], dtype=float)
    actions = np.asarray(data["action"], dtype=float)
    destination_states = true_states[window_start : window_end + 1]
    aligned_actions = actions[window_start : window_end + 1]
    if len(destination_states) != WINDOW_TRANSITIONS:
        raise RuntimeError("true-state proxy window does not contain 70 transitions")
    if len(aligned_actions) != WINDOW_TRANSITIONS:
        raise RuntimeError("action proxy window does not contain 70 transitions")
    proxies = {
        "state_magnitude": np.linalg.norm(destination_states[:, [0, 2]], axis=1),
        "state_rate_magnitude": np.linalg.norm(
            destination_states[:, [1, 3]], axis=1
        ),
        "action_magnitude": np.linalg.norm(aligned_actions, axis=1),
    }
    return H, y, window_start, proxies


def truth_affine_parameters(data: dict[str, np.ndarray]) -> np.ndarray:
    mass, stiffness, damping = np.asarray(data["true_params"], dtype=float)
    return np.array([1.0 / mass, stiffness / mass, damping / mass], dtype=float)


def compute_window_diagnostic(
    identity: tuple[str, int, int, int],
    H: np.ndarray,
    y: np.ndarray,
    truth: np.ndarray,
    proxies: dict[str, np.ndarray],
    lambda_profile: dict[str, Any],
) -> dict[str, Any]:
    """Compute neutral residual diagnostics for one fixed Stage 11C window."""
    condition, seed, window_start, window_end = identity
    Hw, yw = weighted_design(H, y, ROW_SQRT_WEIGHTS)
    optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0]
    residuals = {
        "truth": np.asarray(H, dtype=float) @ truth - np.asarray(y, dtype=float),
        "ls": np.asarray(H, dtype=float) @ optimum - np.asarray(y, dtype=float),
    }
    weighted_residuals = {
        "truth": Hw @ truth - yw,
        "ls": Hw @ optimum - yw,
    }
    truth_score_raw, truth_score_normalized = normalized_scores(
        Hw, weighted_residuals["truth"]
    )
    ls_score_raw, ls_score_normalized = normalized_scores(
        Hw, weighted_residuals["ls"]
    )
    score_scale = max(
        float(np.linalg.norm(Hw) * np.linalg.norm(weighted_residuals["ls"])),
        1.0,
    )
    if np.max(np.abs(ls_score_raw)) > 1.0e-8 * score_scale:
        raise RuntimeError(
            f"{identity}: weighted LS normal-equation score is not near zero"
        )

    row: dict[str, Any] = {
        "condition": condition,
        "seed": seed,
        "window_start": window_start,
        "window_end": window_end,
        "transitions": window_end - window_start + 1,
        "state_source": "true",
        "lambda_truth": float(truth[0]),
        "kappa_truth": float(truth[1]),
        "beta_truth": float(truth[2]),
        "lambda_ls_optimum": float(optimum[0]),
        "kappa_ls_optimum": float(optimum[1]),
        "beta_ls_optimum": float(optimum[2]),
        "lambda_profile_minimum": float(
            lambda_profile["true_lambda_at_minimum"]
        ),
        "lambda_truth_inclusion_95": parse_bool(
            lambda_profile["true_truth_in_region_95"]
        ),
        "lambda_optimum_relative_error": float(
            lambda_profile["true_lambda_optimum_relative_error"]
        ),
        "lambda_profile_width_95": float(
            lambda_profile["true_lambda_region_width_95"]
        ),
        "lambda_profile_relative_width_95": float(
            lambda_profile["true_lambda_relative_width"]
        ),
    }
    for index, parameter in enumerate(PARAMETER_ORDER):
        row[f"truth_score_{parameter}_raw"] = float(truth_score_raw[index])
        row[f"truth_score_{parameter}_normalized"] = float(
            truth_score_normalized[index]
        )
        row[f"ls_score_{parameter}_raw"] = float(ls_score_raw[index])
        row[f"ls_score_{parameter}_normalized"] = float(
            ls_score_normalized[index]
        )

    for residual_kind in ("truth", "ls"):
        unweighted_channels = split_residual_channels(residuals[residual_kind])
        weighted_channels = split_residual_channels(
            weighted_residuals[residual_kind]
        )
        for channel in CHANNEL_NAMES:
            prefix = f"{residual_kind}_{channel}"
            for metric, value in residual_statistics(
                unweighted_channels[channel]
            ).items():
                row[f"{prefix}_residual_{metric}"] = value
            for metric, value in residual_statistics(
                weighted_channels[channel]
            ).items():
                row[f"{prefix}_weighted_residual_{metric}"] = value
            for lag in LAGS:
                row[f"{prefix}_weighted_autocorr_lag{lag}"] = (
                    lag_autocorrelation(weighted_channels[channel], lag)
                )
            squared = np.square(weighted_channels[channel])
            for proxy_name in PROXY_NAMES:
                row[f"{prefix}_weighted_squared_corr_{proxy_name}"] = (
                    safe_correlation(squared, proxies[proxy_name])
                )
    if not all(
        np.isfinite(float(value))
        for key, value in row.items()
        if key not in {"condition", "state_source"}
        and "autocorr" not in key
        and "corr_" not in key
        and "normalized" not in key
    ):
        raise RuntimeError(f"{identity}: non-finite required diagnostic")
    return row


def finite_values(rows: Iterable[dict[str, Any]], key: str) -> np.ndarray:
    values = np.asarray([float(row.get(key, np.nan)) for row in rows], dtype=float)
    return values[np.isfinite(values)]


def aggregate_rows(
    window_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = [
        (condition, [row for row in window_rows if row["condition"] == condition])
        for condition in CONDITIONS
        if any(row["condition"] == condition for row in window_rows)
    ]
    groups.append(("overall", window_rows))
    summaries: list[dict[str, Any]] = []
    for condition, rows in groups:
        summary: dict[str, Any] = {
            "condition": condition,
            "n_runs": len({(row["condition"], int(row["seed"])) for row in rows}),
            "n_windows": len(rows),
            "lambda_truth_inclusion_fraction": float(
                np.mean([bool(row["lambda_truth_inclusion_95"]) for row in rows])
            ),
        }
        base_keys = (
            "lambda_optimum_relative_error",
            "lambda_profile_width_95",
            "lambda_profile_relative_width_95",
        )
        for key in base_keys:
            values = finite_values(rows, key)
            summary[f"{key}_median"] = (
                float(np.median(values)) if len(values) else np.nan
            )
            summary[f"{key}_p95"] = (
                float(np.percentile(values, 95)) if len(values) else np.nan
            )
        for residual_kind in ("truth", "ls"):
            for channel in CHANNEL_NAMES:
                keys = [
                    f"{residual_kind}_{channel}_weighted_residual_rms",
                    *[
                        f"{residual_kind}_{channel}_weighted_autocorr_lag{lag}"
                        for lag in LAGS
                    ],
                    *[
                        f"{residual_kind}_{channel}_weighted_squared_corr_{proxy}"
                        for proxy in PROXY_NAMES
                    ],
                ]
                for key in keys:
                    values = finite_values(rows, key)
                    summary[f"{key}_median"] = (
                        float(np.median(values)) if len(values) else np.nan
                    )
                    summary[f"{key}_median_abs"] = (
                        float(np.median(np.abs(values))) if len(values) else np.nan
                    )
        for parameter in PARAMETER_ORDER:
            key = f"truth_score_{parameter}_normalized"
            values = finite_values(rows, key)
            summary[f"{key}_median"] = (
                float(np.median(values)) if len(values) else np.nan
            )
            summary[f"{key}_median_abs"] = (
                float(np.median(np.abs(values))) if len(values) else np.nan
            )
            summary[f"{key}_p95_abs"] = (
                float(np.percentile(np.abs(values), 95))
                if len(values)
                else np.nan
            )
        summaries.append(summary)
    return summaries


def write_report(
    output_root: Path,
    manifest: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> None:
    lines = [
        "# Stage 11D: Residual and Coverage Diagnostic",
        "",
        "## Scope",
        "",
        f"- Execution mode: `{manifest['execution_mode']}`.",
        f"- Analyzed runs/windows: {manifest['actual_runs']}/{manifest['actual_windows']}.",
        "- State source: replay true states only.",
        "- Window identities, actions, 70-transition rule, row weights, affine "
        "parameterization, LS construction, and Stage 11C profile values are unchanged.",
        "",
    ]
    if manifest["execution_mode"] == "smoke":
        lines += [
            "This is local implementation validation only. It is non-authoritative "
            "and is not evidence for either competing explanation.",
            "",
        ]
    lines += [
        "## Metric definitions",
        "",
        "- Regression channels are evaluated separately as radial and angular; "
        "autocorrelation never uses the interleaved residual sequence.",
        "- Heteroscedasticity proxies use correlations between weighted squared "
        "residuals and raw destination-state/action magnitudes.",
        "- The normalized truth score is the cosine-normalized projection "
        "`(H_w[:,j]^T e_w)/(||H_w[:,j]|| ||e_w||)`.",
        "- State magnitude uses `[theta, r]`; state-rate magnitude uses "
        "`[omega, r_dot]`. These raw-unit norms are descriptive proxies only.",
        "",
        "## Neutral summaries",
        "",
        "| Condition | Windows | Lambda coverage | Lambda error (median) | "
        "Lambda rel. width (median) | Truth RMS radial/angular | "
        "Abs. lambda score (median) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {int(row['n_windows'])} | "
            f"{float(row['lambda_truth_inclusion_fraction']):.3f} | "
            f"{float(row['lambda_optimum_relative_error_median']):.4g} | "
            f"{float(row['lambda_profile_relative_width_95_median']):.4g} | "
            f"{float(row['truth_radial_weighted_residual_rms_median']):.4g}/"
            f"{float(row['truth_angular_weighted_residual_rms_median']):.4g} | "
            f"{float(row['truth_score_lambda_normalized_median_abs']):.4g} |"
        )
    lines += [
        "",
        "## Residual dependence and score summaries",
        "",
        "| Condition | LS RMS radial/angular | Truth ACF lag 1 radial/angular | "
        "Truth ACF lag 5 radial/angular | Truth ACF lag 10 radial/angular | "
        "Squared-residual corr. state/rate/action (radial) | "
        "Abs. normalized truth score lambda/kappa/beta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | "
            f"{float(row['ls_radial_weighted_residual_rms_median']):.4g}/"
            f"{float(row['ls_angular_weighted_residual_rms_median']):.4g} | "
            f"{float(row['truth_radial_weighted_autocorr_lag1_median']):.4g}/"
            f"{float(row['truth_angular_weighted_autocorr_lag1_median']):.4g} | "
            f"{float(row['truth_radial_weighted_autocorr_lag5_median']):.4g}/"
            f"{float(row['truth_angular_weighted_autocorr_lag5_median']):.4g} | "
            f"{float(row['truth_radial_weighted_autocorr_lag10_median']):.4g}/"
            f"{float(row['truth_angular_weighted_autocorr_lag10_median']):.4g} | "
            f"{float(row['truth_radial_weighted_squared_corr_state_magnitude_median']):.4g}/"
            f"{float(row['truth_radial_weighted_squared_corr_state_rate_magnitude_median']):.4g}/"
            f"{float(row['truth_radial_weighted_squared_corr_action_magnitude_median']):.4g} | "
            f"{float(row['truth_score_lambda_normalized_median_abs']):.4g}/"
            f"{float(row['truth_score_kappa_normalized_median_abs']):.4g}/"
            f"{float(row['truth_score_beta_normalized_median_abs']):.4g} |"
        )
    lines += [
        "",
        "## Competing explanations",
        "",
        "- H1 concerns residual dependence or non-constant residual scale.",
        "- H2 concerns structured truth residual projected onto the lambda column.",
        "- This generated report presents the requested diagnostics without "
        "automatically selecting H1 or H2 and without assigning a scientific outcome.",
        "",
        "## Limitations",
        "",
        "- Passive rehabilitation trajectories only; no active excitation.",
        "- True-state regression is an oracle diagnostic, not a deployable estimator.",
        "- Magnitude proxies combine variables with different physical units; no "
        "new normalization or threshold was introduced.",
        "",
    ]
    (output_root / "stage11d_report.md").write_text("\n".join(lines))


def exact_command(argv: list[str] | None = None) -> str:
    arguments = sys.argv[1:] if argv is None else argv
    return shlex.join(
        [sys.executable, str(Path(__file__).resolve()), *arguments]
    )


def git_context() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


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


def choose_identities(
    profile_index: dict[
        tuple[str, int, int, int], dict[str, dict[str, Any]]
    ],
    mode: str,
) -> list[tuple[str, int, int, int]]:
    order = {condition: index for index, condition in enumerate(CONDITIONS)}
    identities = sorted(
        profile_index,
        key=lambda identity: (
            order.get(identity[0], len(order)),
            identity[1],
            identity[3],
        ),
    )
    if mode == "full":
        return identities
    first_run = identities[0][:2]
    return [identity for identity in identities if identity[:2] == first_run][:3]


def run(args: argparse.Namespace, argv: list[str] | None = None) -> Path:
    output_root = Path(args.output_root)
    if args.mode == "full" and output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(
            f"refusing to overwrite non-empty complete output root: {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)

    stage11c_manifest = json.loads(STAGE11C_MANIFEST.read_text())
    if stage11c_manifest.get("mechanical_status") != "valid_full_run":
        raise RuntimeError("Stage 11C source manifest is not a valid full run")
    profile_rows = read_csv(STAGE11C_PROFILES)
    profile_index = validate_and_index_stage11c_profiles(
        profile_rows, stage11c_manifest
    )
    selected = choose_identities(profile_index, args.mode)

    replay = load_replay(DEFAULT_REPLAY)
    config = load_experiment_config(DEFAULT_CONFIG)
    cached_data: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    diagnostics: list[dict[str, Any]] = []
    for identity in selected:
        condition, seed, expected_start, window_end = identity
        run_identity = (condition, seed)
        if run_identity not in replay:
            raise RuntimeError(f"Stage 11C identity is absent from replay: {identity}")
        if run_identity not in cached_data:
            cached_data[run_identity] = arrays(replay[run_identity])
            verify_truth_metadata(condition, cached_data[run_identity], config)
        data = cached_data[run_identity]
        model_params = stage9j_overrides(config, condition)["model_params"]
        H, y, actual_start, proxies = build_true_state_window(
            condition, seed, data, model_params, window_end
        )
        if actual_start != expected_start:
            raise RuntimeError(
                f"Stage 11C window identity does not match the unchanged rule: "
                f"{identity}, reconstructed start={actual_start}"
            )
        diagnostics.append(
            compute_window_diagnostic(
                identity,
                H,
                y,
                truth_affine_parameters(data),
                proxies,
                profile_index[identity]["lambda_1d"],
            )
        )

    if {window_identity(row) for row in diagnostics} != set(selected):
        raise RuntimeError("generated Stage 11D identities do not exactly align")
    summaries = aggregate_rows(diagnostics)
    write_dict_csv(output_root / "window_residual_diagnostics.csv", diagnostics)
    write_dict_csv(output_root / "condition_residual_summary.csv", summaries)

    commit, dirty = git_context()
    manifest = {
        "experiment_id": "stage11d_residual_coverage_audit",
        "execution_mode": args.mode,
        "authoritative": args.mode == "full",
        "scientific_status_assigned": False,
        "hypothesis_selected_automatically": False,
        "git_commit": commit,
        "git_dirty_before_run": dirty,
        "exact_command": exact_command(argv),
        "conda_environment": (
            Path(sys.prefix).name if Path(sys.prefix).name else "unknown"
        ),
        "script_path": str(Path(__file__).resolve().relative_to(ROOT)),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "replay_path": str(Path(DEFAULT_REPLAY).resolve().relative_to(ROOT)),
        "replay_sha256": sha256_file(Path(DEFAULT_REPLAY)),
        "config_path": str(Path(DEFAULT_CONFIG).resolve().relative_to(ROOT)),
        "config_sha256": sha256_file(Path(DEFAULT_CONFIG)),
        "stage11c_manifest_path": str(STAGE11C_MANIFEST.relative_to(ROOT)),
        "stage11c_manifest_sha256": sha256_file(STAGE11C_MANIFEST),
        "stage11c_profile_path": str(STAGE11C_PROFILES.relative_to(ROOT)),
        "stage11c_profile_sha256": sha256_file(STAGE11C_PROFILES),
        "source_state": "true",
        "window_transitions": WINDOW_TRANSITIONS,
        "row_sqrt_weights": ROW_SQRT_WEIGHTS.tolist(),
        "parameter_order": list(PARAMETER_ORDER),
        "source_stage11c_windows": len(profile_index),
        "actual_runs": len({identity[:2] for identity in selected}),
        "actual_windows": len(diagnostics),
        "window_identity_aligned": True,
        "output_root": str(output_root),
        "smoke_non_authoritative": args.mode == "smoke",
    }
    (output_root / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    write_report(output_root, manifest, summaries)
    return output_root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = run(args, argv)
    print(
        json.dumps(
            {
                "mode": args.mode,
                "output_root": str(output_root),
                "authoritative": args.mode == "full",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
