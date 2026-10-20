"""Final stress validation for Stage 7A alpha-soft safety-aware CEM."""

from __future__ import annotations

import argparse
import copy
import csv
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

from run_spring2d_adaptive_mpc_conditions import load_experiment_config, run_condition, write_condition_csv
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE, SAFETY_FILTER_CONFIG


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_final_validation"
ESTIMATOR = "ukf_bias"
METHODS = ["baseline_cem", "runtime_filter_old", "alpha100_omega0", "alpha200_omega0"]
CONDITIONS = [
    "clean",
    "noise",
    "noise_bias",
    "model_mismatch_light",
    "model_mismatch_heavy",
    "larger_target",
    "worse_initial_state",
    "combined_stress",
]

DEG = float(np.pi / 180.0)
CONDITION_SPECS: dict[str, dict[str, Any]] = {
    "clean": {"base_condition": "clean", "seed": 201, "true_param_overrides": {}, "mpc_overrides": {}},
    "noise": {"base_condition": "noise", "seed": 202, "true_param_overrides": {}, "mpc_overrides": {}},
    "noise_bias": {"base_condition": "noise_bias", "seed": 203, "true_param_overrides": {}, "mpc_overrides": {}},
    "model_mismatch_light": {
        "base_condition": "clean",
        "seed": 204,
        "true_param_overrides": {"m": 1.32, "k": 495.0, "b_r": 14.4},
        "mpc_overrides": {},
    },
    "model_mismatch_heavy": {
        "base_condition": "clean",
        "seed": 205,
        "true_param_overrides": {"m": 1.50, "k": 540.0, "b_r": 10.8},
        "mpc_overrides": {},
    },
    "larger_target": {
        "base_condition": "clean",
        "seed": 206,
        "true_param_overrides": {"theta_target": 105.0 * DEG},
        "mpc_overrides": {"target_theta": 105.0 * DEG},
    },
    "worse_initial_state": {
        "base_condition": "clean",
        "seed": 207,
        "true_param_overrides": {"theta_init": 0.04, "omega_init": -0.18, "r_init": 0.33, "r_dot_init": -0.03},
        "mpc_overrides": {},
    },
    "combined_stress": {
        "base_condition": "noise_bias",
        "seed": 208,
        "true_param_overrides": {
            "m": 1.32,
            "k": 495.0,
            "b_r": 14.4,
            "theta_init": 0.04,
            "omega_init": -0.18,
            "r_init": 0.33,
            "r_dot_init": -0.03,
        },
        "mpc_overrides": {},
    },
}


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


def _finite_percentile(values: np.ndarray, percentile: float) -> float:
    values = _finite(values)
    return float(np.percentile(values, percentile)) if len(values) else np.nan


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return np.nan


def _decision_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    decisions: list[dict[str, Any]] = []
    for row in rows:
        solve_count = int(float(row.get("mpc_solve_count", 0)))
        if solve_count <= 0 or solve_count in seen:
            continue
        seen.add(solve_count)
        decisions.append(row)
    return decisions


def _severity(rows: list[dict[str, Any]], key: str, limit: float) -> np.ndarray:
    return np.maximum(0.0, np.abs(_series(rows, key)) - limit)


def _severity_stats(prefix: str, values: np.ndarray) -> dict[str, Any]:
    return {
        f"{prefix}_violation_count": int(np.count_nonzero(values > 0.0)),
        f"{prefix}_mean_severity": _finite_mean(values),
        f"{prefix}_max_severity": _finite_max(values),
        f"{prefix}_p90_severity": _finite_percentile(values, 90),
        f"{prefix}_p95_severity": _finite_percentile(values, 95),
        f"{prefix}_p99_severity": _finite_percentile(values, 99),
    }


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_csv(rows: list[dict[str, Any]], path: Path, fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    fieldnames = fields or list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _method_configs() -> dict[str, dict[str, Any]]:
    return {
        "baseline_cem": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "runtime_filter": {"enabled": False},
        },
        "runtime_filter_old": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "runtime_filter": copy.deepcopy(SAFETY_FILTER_CONFIG),
        },
        "alpha100_omega0": {
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 100.0,
            "omega_soft_weight": 0.0,
            "runtime_filter": {"enabled": False},
        },
        "alpha200_omega0": {
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 200.0,
            "omega_soft_weight": 0.0,
            "runtime_filter": {"enabled": False},
        },
    }


def _condition_cfg(base_cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    spec = CONDITION_SPECS[condition]
    base_condition = spec["base_condition"]
    condition_cfg = copy.deepcopy(base_cfg["conditions"][base_condition])
    condition_cfg["seed"] = int(spec["seed"])
    return condition_cfg


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = copy.deepcopy(method_cfg["runtime_filter"])

    spec = CONDITION_SPECS[condition]
    cfg["true_params"].update(copy.deepcopy(spec.get("true_param_overrides", {})))
    cfg["mpc_params"].update(copy.deepcopy(spec.get("mpc_overrides", {})))

    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver["alpha_constraint_mode"] = method_cfg["alpha_constraint_mode"]
    solver["alpha_soft_weight"] = float(method_cfg["alpha_soft_weight"])
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    weights = dict(solver.get("safety_violation_weights", {}))
    weights.update(
        {
            "F_tan": float(weights.get("F_tan", 1.0)),
            "F_rad": float(weights.get("F_rad", 1.0)),
            "delta_r": float(weights.get("delta_r", 1.0)),
            "omega": float(method_cfg["omega_soft_weight"]),
            "alpha": float(weights.get("alpha", 1.0)),
        }
    )
    solver["safety_violation_weights"] = weights
    return cfg


def add_action_diff_vs_baseline(all_rows: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
    for condition in CONDITIONS:
        baseline = all_rows[("baseline_cem", condition)]
        baseline_by_index = {
            index: np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))], dtype=float)
            for index, row in enumerate(baseline)
        }
        for method in METHODS:
            for index, row in enumerate(all_rows[(method, condition)]):
                if index in baseline_by_index:
                    action = np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))], dtype=float)
                    row["action_diff_vs_baseline"] = float(np.linalg.norm(action - baseline_by_index[index]))
                else:
                    row["action_diff_vs_baseline"] = np.nan


def summarize_rows(
    method: str,
    method_cfg: dict[str, Any],
    condition: str,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
) -> dict[str, Any]:
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))

    decisions = _decision_rows(rows)
    action = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(action, axis=1)
    action_smoothness = np.linalg.norm(np.diff(action, axis=0), axis=1) if len(action) > 1 else np.array([])
    omega_sev = _severity(rows, "omega", omega_max)
    alpha_sev = _severity(rows, "alpha_step", alpha_max)
    delta_r_sev = _severity(rows, "delta_r", delta_r_max)
    F_tan_sev = _severity(rows, "F_tan", F_tan_max)
    F_rad_sev = _severity(rows, "F_rad", F_rad_max)
    alpha_norm = alpha_sev / alpha_max if alpha_max > 0.0 else np.full_like(alpha_sev, np.nan)
    omega_norm = omega_sev / omega_max if omega_max > 0.0 else np.full_like(omega_sev, np.nan)
    spec = CONDITION_SPECS[condition]
    row: dict[str, Any] = {
        "method": method,
        "condition": condition,
        "base_condition": spec["base_condition"],
        "condition_seed": int(spec["seed"]),
        "true_param_overrides": repr(spec.get("true_param_overrides", {})),
        "mpc_overrides": repr(spec.get("mpc_overrides", {})),
        "solver_safety_mode": str(final.get("cem_safety_mode", method_cfg["solver_safety_mode"])),
        "runtime_filter_enabled": bool(final.get("safety_filter_active", False) or method == "runtime_filter_old"),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", method_cfg["alpha_constraint_mode"])),
        "alpha_soft_weight": float(method_cfg["alpha_soft_weight"]),
        "omega_soft_weight": float(method_cfg["omega_soft_weight"]),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "delta_r_p95_severity": _finite_percentile(delta_r_sev, 95),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "mean_feasible_ratio_excluding_alpha": _finite_mean(
            _series(decisions, "cem_safety_feasible_excluding_alpha_ratio")
        ),
        "original_alpha_feasibility_ratio": _finite_mean(_series(decisions, "cem_alpha_original_feasible_ratio")),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "mean_action_diff_vs_baseline": _finite_mean(_series(rows, "action_diff_vs_baseline")),
        "max_action_diff_vs_baseline": _finite_max(_series(rows, "action_diff_vs_baseline")),
        "selected_predicted_horizon_alpha_violation_mean": _finite_mean(
            _series(decisions, "cem_selected_max_norm_violation_alpha")
        ),
        "selected_predicted_horizon_alpha_violation_max": _finite_max(
            _series(decisions, "cem_selected_max_norm_violation_alpha")
        ),
        "executed_true_alpha_violation_mean": _finite_mean(alpha_norm),
        "executed_true_alpha_violation_max": _finite_max(alpha_norm),
        "selected_predicted_horizon_omega_violation_mean": _finite_mean(
            _series(decisions, "cem_selected_max_norm_violation_omega")
        ),
        "selected_predicted_horizon_omega_violation_max": _finite_max(
            _series(decisions, "cem_selected_max_norm_violation_omega")
        ),
        "executed_true_omega_violation_mean": _finite_mean(omega_norm),
        "executed_true_omega_violation_max": _finite_max(omega_norm),
        "runtime_s": float(runtime_s),
    }
    row.update(_severity_stats("alpha", alpha_sev))
    row.update(_severity_stats("omega", omega_sev))
    return row


SUMMARY_FIELDS = [
    "method",
    "condition",
    "base_condition",
    "condition_seed",
    "true_param_overrides",
    "mpc_overrides",
    "solver_safety_mode",
    "runtime_filter_enabled",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "omega_soft_weight",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_max_severity",
    "alpha_p90_severity",
    "alpha_p95_severity",
    "alpha_p99_severity",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_max_severity",
    "omega_p90_severity",
    "omega_p95_severity",
    "omega_p99_severity",
    "delta_r_violation_count",
    "delta_r_mean_severity",
    "delta_r_max_severity",
    "delta_r_p95_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "mean_feasible_ratio_excluding_alpha",
    "original_alpha_feasibility_ratio",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "mean_action_diff_vs_baseline",
    "max_action_diff_vs_baseline",
    "selected_predicted_horizon_alpha_violation_mean",
    "selected_predicted_horizon_alpha_violation_max",
    "executed_true_alpha_violation_mean",
    "executed_true_alpha_violation_max",
    "selected_predicted_horizon_omega_violation_mean",
    "selected_predicted_horizon_omega_violation_max",
    "executed_true_omega_violation_mean",
    "executed_true_omega_violation_max",
    "runtime_s",
]


def _row(summary_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    for row in summary_rows:
        if row["method"] == method and row["condition"] == condition:
            return row
    raise KeyError((method, condition))


def _method_rows(summary_rows: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    return [row for row in summary_rows if row["method"] == method]


def _aggregate(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        method_rows = _method_rows(summary_rows, method)
        rows.append(
            {
                "method": method,
                "target_success_count": int(sum(bool(row["target_reached"]) for row in method_rows)),
                "alpha_mean_avg": _finite_mean(np.array([float(row["alpha_mean_severity"]) for row in method_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "alpha_p95_std": float(np.std([float(row["alpha_p95_severity"]) for row in method_rows])),
                "omega_mean_avg": _finite_mean(np.array([float(row["omega_mean_severity"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "action_magnitude_avg": _finite_mean(np.array([float(row["mean_action_magnitude"]) for row in method_rows])),
                "runtime_avg": _finite_mean(np.array([float(row["runtime_s"]) for row in method_rows])),
            }
        )
    return rows


def _fmt(value: Any) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def _safe_delta(new: float, old: float) -> float:
    if not np.isfinite(new) or not np.isfinite(old):
        return np.nan
    return float(new - old)


def save_trajectory_plots(
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    output_root: Path,
    base_cfg: dict[str, Any],
    methods: dict[str, dict[str, Any]],
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for condition in CONDITIONS:
        cfg = configure_run(base_cfg, methods["baseline_cem"], condition)
        constraints = cfg["mpc_params"].get("constraints", {})
        target_theta = float(cfg["mpc_params"].get("target_theta", cfg["true_params"]["theta_target"]))
        omega_max = float(constraints.get("omega_max", cfg["true_params"]["omega_max"]))
        alpha_max = float(constraints.get("alpha_max", cfg["true_params"]["alpha_max"]))
        for key, ylabel, filename, transform, limit in [
            ("theta", "theta [deg]", "theta_trajectories.png", np.degrees, np.degrees(target_theta)),
            ("alpha_step", "alpha", "alpha_trajectories.png", None, alpha_max),
            ("omega", "omega", "omega_trajectories.png", None, omega_max),
        ]:
            fig, ax = plt.subplots(figsize=(10, 4.8))
            for method in METHODS:
                rows = all_rows[(method, condition)]
                values = _series(rows, key)
                if transform is not None:
                    values = transform(values)
                ax.plot(_series(rows, "t"), values, label=method)
            if key == "theta":
                ax.axhline(limit, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
            else:
                ax.axhline(limit, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
                ax.axhline(-limit, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
            ax.set_title(f"{condition}: {ylabel}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}", dpi=150)
            plt.close(fig)


def _grouped_bar(
    summary_rows: list[dict[str, Any]],
    metrics: tuple[str, str],
    ylabel: str,
    title: str,
    path: Path,
) -> None:
    x = np.arange(len(CONDITIONS))
    width = 0.18
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(METHODS))
    for ax, metric in zip(axes, metrics):
        for offset, method in zip(offsets, METHODS):
            values = [float(_row(summary_rows, method, condition)[metric]) for condition in CONDITIONS]
            ax.bar(x + offset, values, width=width, label=method)
        ax.set_ylabel(ylabel)
        ax.set_title(metric)
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].legend(fontsize=8, ncol=4)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(CONDITIONS, rotation=25, ha="right")
    fig.suptitle(title)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_summary_plots(summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    _grouped_bar(
        summary_rows,
        ("alpha_p95_severity", "alpha_max_severity"),
        "alpha severity",
        "Alpha p95/max severity by method and condition",
        fig_dir / "alpha_p95_max_severity_by_method_condition.png",
    )
    _grouped_bar(
        summary_rows,
        ("omega_p95_severity", "omega_max_severity"),
        "omega severity",
        "Omega p95/max severity by method and condition",
        fig_dir / "omega_p95_max_severity_by_method_condition.png",
    )
    _grouped_bar(
        summary_rows,
        ("action_smoothness", "mean_action_magnitude"),
        "action metric",
        "Action smoothness and magnitude summary",
        fig_dir / "action_smoothness_magnitude_summary.png",
    )

    x = np.arange(len(CONDITIONS))
    width = 0.18
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(METHODS))
    for offset, method in zip(offsets, METHODS):
        success = [1.0 if bool(_row(summary_rows, method, condition)["target_reached"]) else 0.0 for condition in CONDITIONS]
        times = [float(_row(summary_rows, method, condition)["T_reach"]) for condition in CONDITIONS]
        axes[0].bar(x + offset, success, width=width, label=method)
        axes[1].bar(x + offset, times, width=width, label=method)
    axes[0].set_ylabel("target reached")
    axes[0].set_ylim(-0.05, 1.05)
    axes[1].set_ylabel("T_reach [s]")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].legend(fontsize=8, ncol=4)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(CONDITIONS, rotation=25, ha="right")
    fig.suptitle("T_reach and target success summary")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    fig.savefig(fig_dir / "target_success_treach_summary.png", dpi=150)
    plt.close(fig)


def _comparison_counts(summary_rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    counts = {
        "target_success": 0,
        "alpha_mean_better": 0,
        "alpha_p95_better": 0,
        "alpha_max_better": 0,
        "omega_p95_worse": 0,
        "omega_max_worse": 0,
    }
    deltas = {key: [] for key in ["alpha_mean", "alpha_p95", "alpha_max", "omega_p95", "omega_max"]}
    for condition in CONDITIONS:
        row = _row(summary_rows, method, condition)
        baseline = _row(summary_rows, "baseline_cem", condition)
        counts["target_success"] += int(bool(row["target_reached"]))
        for metric, key in [
            ("alpha_mean_severity", "alpha_mean"),
            ("alpha_p95_severity", "alpha_p95"),
            ("alpha_max_severity", "alpha_max"),
            ("omega_p95_severity", "omega_p95"),
            ("omega_max_severity", "omega_max"),
        ]:
            deltas[key].append(_safe_delta(float(row[metric]), float(baseline[metric])))
        counts["alpha_mean_better"] += int(float(row["alpha_mean_severity"]) < float(baseline["alpha_mean_severity"]))
        counts["alpha_p95_better"] += int(float(row["alpha_p95_severity"]) < float(baseline["alpha_p95_severity"]))
        counts["alpha_max_better"] += int(float(row["alpha_max_severity"]) < float(baseline["alpha_max_severity"]))
        counts["omega_p95_worse"] += int(float(row["omega_p95_severity"]) > float(baseline["omega_p95_severity"]))
        counts["omega_max_worse"] += int(float(row["omega_max_severity"]) > float(baseline["omega_max_severity"]))
    counts.update({f"{key}_delta_avg": _finite_mean(np.array(values)) for key, values in deltas.items()})
    return counts


def _best_alpha_candidate(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in aggregate_rows if row["method"] in {"alpha100_omega0", "alpha200_omega0"}]
    return min(
        candidates,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            row["alpha_mean_avg"],
            row["alpha_p95_avg"],
            row["alpha_max_avg"],
            row["omega_p95_avg"],
            row["T_reach_avg"],
        ),
    )


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = _aggregate(summary_rows)
    aggregate_by_method = {row["method"]: row for row in aggregate}
    best_alpha = _best_alpha_candidate(aggregate)
    alpha100 = aggregate_by_method["alpha100_omega0"]
    alpha200 = aggregate_by_method["alpha200_omega0"]
    baseline = aggregate_by_method["baseline_cem"]
    runtime_filter = aggregate_by_method["runtime_filter_old"]
    alpha100_counts = _comparison_counts(summary_rows, "alpha100_omega0")
    alpha200_counts = _comparison_counts(summary_rows, "alpha200_omega0")
    alpha200_best = best_alpha["method"] == "alpha200_omega0"
    alpha100_more_stable = (
        alpha100["target_success_count"] >= alpha200["target_success_count"]
        and alpha100["alpha_p95_std"] < alpha200["alpha_p95_std"]
    )
    alpha_soft_success_count = min(alpha100["target_success_count"], alpha200["target_success_count"])
    alpha_soft_beats_filter = (
        alpha100["target_success_count"] > runtime_filter["target_success_count"]
        or alpha200["target_success_count"] > runtime_filter["target_success_count"]
        or best_alpha["alpha_mean_avg"] < runtime_filter["alpha_mean_avg"]
    )
    strong_enough = (
        best_alpha["target_success_count"] == len(CONDITIONS)
        and (
            alpha100_counts["alpha_mean_better"] >= 5
            or alpha200_counts["alpha_mean_better"] >= 5
        )
        and best_alpha["omega_p95_avg"] <= baseline["omega_p95_avg"] * 1.15
    )
    next_method = "progress governor" if best_alpha["target_success_count"] < len(CONDITIONS) else "PSF/gatekeeper-lite"

    lines = [
        "# Stage 7A-final Alpha-Soft CEM Stress Validation Report",
        "",
        "## 范围",
        "- 本脚本只做 Stage 7A-final stress validation；不是新的调参 sweep。",
        "- 对照方法固定为 `baseline_cem`, `runtime_filter_old`, `alpha100_omega0`, `alpha200_omega0`。",
        "- alpha-soft 方法使用 `alpha_constraint_mode=soft`，`omega` soft weight 为 0，alpha 不作为 hard feasibility constraint。",
        "- `runtime_filter_old` 复用旧 one-step runtime safety filter 配置；baseline CEM 行为保持 `safety_mode=off`。",
        "- Spring2D dynamics、UKF/UKF-bias、Windowed NLS identifier、estimator/identifier data flow、基础 cost/constraints、solver 设置、max_time/max_steps 均未在脚本中修改。",
        "- stress 条件只通过 per-run config override 显式注入，并记录在 summary CSV 中；没有 post-result manual tuning。",
        "- 以下结论是仿真经验结果，不是 formal safety guarantee。",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Stress Overrides",
        "| condition | base | true_param_overrides | mpc_overrides |",
        "|---|---|---|---|",
    ]
    for condition in CONDITIONS:
        spec = CONDITION_SPECS[condition]
        lines.append(
            f"| {condition} | {spec['base_condition']} | `{spec.get('true_param_overrides', {})}` | "
            f"`{spec.get('mpc_overrides', {})}` |"
        )
    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            "| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | alpha p95 std | omega p95 avg | omega max avg | T_reach avg | action smooth avg | runtime avg |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregate:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['alpha_p95_std'])} | {_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{_fmt(row['T_reach_avg'])} | {_fmt(row['action_smoothness_avg'])} | {_fmt(row['runtime_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            f"1. `alpha200_omega0` 是否仍是 stress validation 下最佳候选？",
            f"- {'是' if alpha200_best else '否'}。按 target success、alpha mean、alpha p95、alpha max、omega p95、T_reach 的固定排序，最佳 alpha-soft 候选是 `{best_alpha['method']}`。",
            f"- `alpha200_omega0`: target={alpha200['target_success_count']}/{len(CONDITIONS)}, alpha_mean_avg={_fmt(alpha200['alpha_mean_avg'])}, alpha_p95_avg={_fmt(alpha200['alpha_p95_avg'])}, omega_p95_avg={_fmt(alpha200['omega_p95_avg'])}。",
            f"- `alpha100_omega0`: target={alpha100['target_success_count']}/{len(CONDITIONS)}, alpha_mean_avg={_fmt(alpha100['alpha_mean_avg'])}, alpha_p95_avg={_fmt(alpha100['alpha_p95_avg'])}, omega_p95_avg={_fmt(alpha100['omega_p95_avg'])}。",
            "",
            "2. `alpha100_omega0` 是否比 `alpha200_omega0` 更稳定？",
            f"- {'是' if alpha100_more_stable else '否/不明显'}。这里用 target success 不更差且 alpha p95 跨条件标准差更低作为稳定性判据；alpha100 std={_fmt(alpha100['alpha_p95_std'])}, alpha200 std={_fmt(alpha200['alpha_p95_std'])}。",
            "",
            "3. alpha-soft CEM 是否一致保持 target reaching？",
            f"- 两个 alpha-soft 方法的较差 target success 为 {alpha_soft_success_count}/{len(CONDITIONS)}。若不是 {len(CONDITIONS)}/{len(CONDITIONS)}，则不能声称一致保持。",
            "",
            "4. 相比 baseline，是否降低 alpha mean、p95、max severity？",
            f"- `alpha100_omega0`: mean 改善 {alpha100_counts['alpha_mean_better']}/{len(CONDITIONS)} 条件，p95 改善 {alpha100_counts['alpha_p95_better']}/{len(CONDITIONS)}，max 改善 {alpha100_counts['alpha_max_better']}/{len(CONDITIONS)}；平均 delta mean/p95/max={_fmt(alpha100_counts['alpha_mean_delta_avg'])}/{_fmt(alpha100_counts['alpha_p95_delta_avg'])}/{_fmt(alpha100_counts['alpha_max_delta_avg'])}。",
            f"- `alpha200_omega0`: mean 改善 {alpha200_counts['alpha_mean_better']}/{len(CONDITIONS)} 条件，p95 改善 {alpha200_counts['alpha_p95_better']}/{len(CONDITIONS)}，max 改善 {alpha200_counts['alpha_max_better']}/{len(CONDITIONS)}；平均 delta mean/p95/max={_fmt(alpha200_counts['alpha_mean_delta_avg'])}/{_fmt(alpha200_counts['alpha_p95_delta_avg'])}/{_fmt(alpha200_counts['alpha_max_delta_avg'])}。",
            "",
            "5. 是否恶化 omega tail risk？",
            f"- `alpha100_omega0`: omega p95 比 baseline 更差 {alpha100_counts['omega_p95_worse']}/{len(CONDITIONS)} 条件，omega max 更差 {alpha100_counts['omega_max_worse']}/{len(CONDITIONS)}；平均 delta p95/max={_fmt(alpha100_counts['omega_p95_delta_avg'])}/{_fmt(alpha100_counts['omega_max_delta_avg'])}。",
            f"- `alpha200_omega0`: omega p95 比 baseline 更差 {alpha200_counts['omega_p95_worse']}/{len(CONDITIONS)} 条件，omega max 更差 {alpha200_counts['omega_max_worse']}/{len(CONDITIONS)}；平均 delta p95/max={_fmt(alpha200_counts['omega_p95_delta_avg'])}/{_fmt(alpha200_counts['omega_max_delta_avg'])}。",
            "",
            "6. 是否仍优于旧 one-step runtime filter？",
            f"- {'是' if alpha_soft_beats_filter else '否/不明显'}。旧 filter target={runtime_filter['target_success_count']}/{len(CONDITIONS)}, alpha_mean_avg={_fmt(runtime_filter['alpha_mean_avg'])}; 最佳 alpha-soft target={best_alpha['target_success_count']}/{len(CONDITIONS)}, alpha_mean_avg={_fmt(best_alpha['alpha_mean_avg'])}。",
            "",
            "7. alpha-soft CEM 是否强到可以作为 Stage 7A final candidate carry forward？",
            f"- {'是，作为 empirical final candidate carry forward；但不提供 formal safety guarantee。' if strong_enough else '否，当前 stress validation 证据不足以强 carry forward。'}",
            "",
            "8. 如果不够，下一步应是 progress governor 还是 PSF/gatekeeper-lite？",
            f"- 建议下一步是 `{next_method}`，而不是继续做 alpha-soft weight tuning；除非某个单一 stress 条件给出非常明确、可复现的权重敏感证据。",
            "",
            "9. 是否建议继续调 alpha-soft weight？",
            "- 不建议把下一步默认设为更多 alpha-soft weight tuning。本次验证只保留 `alpha100_omega0` 与 `alpha200_omega0` 的证据对照。",
            "",
            "## Outputs",
            "- `stage7a_final_summary.csv` contains all per-method/per-condition metrics.",
            "- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
            "Bad or mixed results are reported as-is.",
            "",
        ]
    )
    (output_root / "stage7a_final_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _method_configs()
    commands = [
        "conda run -n mpc_learn python -m compileall scripts/run_spring2d_stage7a_final_validation.py",
        "conda run -n mpc_learn python -m pytest tests",
        "conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7a_final_validation.py",
    ]
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    runtimes: dict[tuple[str, str], float] = {}

    for method in METHODS:
        method_cfg = methods[method]
        for condition in CONDITIONS:
            cfg = configure_run(base_cfg, method_cfg, condition)
            condition_cfg = _condition_cfg(base_cfg, condition)
            start = time.perf_counter()
            rows = run_condition(condition, condition_cfg, cfg)
            runtime_s = time.perf_counter() - start
            for row in rows:
                row["stage7a_final_method"] = method
                row["stage7a_final_condition"] = condition
                row["stage7a_final_condition_spec"] = repr(CONDITION_SPECS[condition])
            all_rows[(method, condition)] = rows
            runtimes[(method, condition)] = runtime_s
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            print(f"Completed method={method}, condition={condition}, runtime={runtime_s:.2f}s", flush=True)

    add_action_diff_vs_baseline(all_rows)
    summary_rows: list[dict[str, Any]] = []
    for method in METHODS:
        method_cfg = methods[method]
        for condition in CONDITIONS:
            cfg = configure_run(base_cfg, method_cfg, condition)
            rows = all_rows[(method, condition)]
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            summary_rows.append(summarize_rows(method, method_cfg, condition, rows, cfg, runtimes[(method, condition)]))

    _write_csv(summary_rows, output_root / "stage7a_final_summary.csv", SUMMARY_FIELDS)
    save_trajectory_plots(all_rows, output_root, base_cfg, methods)
    save_summary_plots(summary_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 7A-final alpha-soft CEM stress validation")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7a_final_summary.csv'}")
    print(f"  report      : {output_root / 'stage7a_final_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_mean={row['alpha_mean_severity']:.4f}, alpha_p95={row['alpha_p95_severity']:.4f}, "
            f"omega_p95={row['omega_p95_severity']:.4f}, done={row['done_reason']}"
        )
    return summary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.config, args.output_root)


if __name__ == "__main__":
    main()
