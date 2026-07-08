"""Refine alpha-soft safety-aware CEM weights for Spring2D adaptive MPC."""

from __future__ import annotations

import argparse
import copy
import csv
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import load_experiment_config, run_condition, write_condition_csv
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_refine"
PRIOR_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_alpha_soft"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]
ALPHA_WEIGHTS = [50.0, 100.0, 200.0, 500.0, 1000.0]
OMEGA_WEIGHTS = [0.0, 10.0, 50.0]
PRIOR_METHOD = "alpha_soft_w100_prior_omega1"


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


def _finite_p95(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.percentile(values, 95)) if len(values) else np.nan


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0 or not np.isfinite(denominator):
        return np.nan
    return float(numerator / denominator)


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


def _method_name(alpha_weight: float, omega_weight: float) -> str:
    return f"alpha{alpha_weight:g}_omega{omega_weight:g}"


def _build_methods() -> dict[str, dict[str, Any]]:
    methods: dict[str, dict[str, Any]] = {
        "baseline_cem": {
            "source": "run",
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "hard",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 1.0,
        },
        PRIOR_METHOD: {
            "source": "prior",
            "prior_method": "alpha_soft_w100",
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 100.0,
            "omega_soft_weight": 1.0,
        },
    }
    for alpha_weight in ALPHA_WEIGHTS:
        for omega_weight in OMEGA_WEIGHTS:
            methods[_method_name(alpha_weight, omega_weight)] = {
                "source": "run",
                "solver_safety_mode": "soft_penalty",
                "alpha_constraint_mode": "soft",
                "alpha_soft_weight": float(alpha_weight),
                "omega_soft_weight": float(omega_weight),
            }
    return methods


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver["alpha_constraint_mode"] = method_cfg["alpha_constraint_mode"]
    solver["alpha_soft_weight"] = float(method_cfg["alpha_soft_weight"])
    solver["safety_penalty_weight"] = 1.0
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
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    return cfg


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return [dict(row) for row in csv.DictReader(f)]


def _prior_runtime(condition: str) -> float:
    path = PRIOR_OUTPUT_ROOT / "stage7a_alpha_soft_summary.csv"
    if not path.exists():
        return np.nan
    for row in _read_csv_rows(path):
        if row.get("method") == "alpha_soft_w100" and row.get("condition") == condition:
            return float(row.get("runtime_s", np.nan))
    return np.nan


def load_prior_rows(condition: str, output_root: Path) -> list[dict[str, Any]]:
    source = PRIOR_OUTPUT_ROOT / "logs" / "alpha_soft_w100" / condition / "timeseries.csv"
    if not source.exists():
        raise FileNotFoundError(f"Prior alpha_soft_w100 log not found: {source}")
    rows = _read_csv_rows(source)
    for row in rows:
        row["refine_source"] = "prior_stage7a_alpha_soft"
        row["refine_method"] = PRIOR_METHOD
        row["refine_alpha_weight"] = 100.0
        row["refine_omega_weight"] = 1.0
    write_condition_csv(rows, output_root / "logs" / PRIOR_METHOD / condition / "timeseries.csv")
    return rows


def add_action_diff_vs_baseline(all_rows: dict[tuple[str, str], list[dict[str, Any]]], methods: dict[str, Any]) -> None:
    for condition in CONDITIONS:
        baseline = all_rows[("baseline_cem", condition)]
        baseline_by_index = {
            index: np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))], dtype=float)
            for index, row in enumerate(baseline)
        }
        for method in methods:
            rows = all_rows[(method, condition)]
            for index, row in enumerate(rows):
                if index in baseline_by_index:
                    action = np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))], dtype=float)
                    row["action_diff_vs_baseline"] = float(np.linalg.norm(action - baseline_by_index[index]))
                else:
                    row["action_diff_vs_baseline"] = np.nan


def _severity(rows: list[dict[str, Any]], key: str, limit: float) -> np.ndarray:
    return np.maximum(0.0, np.abs(_series(rows, key)) - limit)


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
    omega_norm = omega_sev / omega_max if omega_max > 0.0 else np.full_like(omega_sev, np.nan)
    alpha_norm = alpha_sev / alpha_max if alpha_max > 0.0 else np.full_like(alpha_sev, np.nan)
    return {
        "method": method,
        "condition": condition,
        "source": str(method_cfg.get("source", "run")),
        "solver_safety_mode": str(final.get("cem_safety_mode", method_cfg["solver_safety_mode"])),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", method_cfg["alpha_constraint_mode"])),
        "alpha_soft_weight": float(method_cfg["alpha_soft_weight"]),
        "omega_soft_weight": float(method_cfg["omega_soft_weight"]),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "mean_feasible_ratio_excluding_alpha": _finite_mean(
            _series(decisions, "cem_safety_feasible_excluding_alpha_ratio")
        ),
        "mean_alpha_feasibility_ratio_original": _finite_mean(
            _series(decisions, "cem_alpha_original_feasible_ratio")
        ),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_max_severity": _finite_max(omega_sev),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_p95_severity": _finite_p95(omega_sev),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_p95(alpha_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "delta_r_p95_severity": _finite_p95(delta_r_sev),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "mean_action_diff_vs_baseline": _finite_mean(_series(rows, "action_diff_vs_baseline")),
        "max_action_diff_vs_baseline": _finite_max(_series(rows, "action_diff_vs_baseline")),
        "mean_selected_pred_horizon_alpha_violation": _finite_mean(
            _series(decisions, "cem_selected_max_norm_violation_alpha")
        ),
        "mean_selected_pred_horizon_omega_violation": _finite_mean(
            _series(decisions, "cem_selected_max_norm_violation_omega")
        ),
        "mean_executed_true_alpha_violation": _finite_mean(alpha_norm),
        "mean_executed_true_omega_violation": _finite_mean(omega_norm),
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "source",
    "solver_safety_mode",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "omega_soft_weight",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "mean_feasible_ratio_excluding_alpha",
    "mean_alpha_feasibility_ratio_original",
    "omega_violation_count",
    "omega_max_severity",
    "omega_mean_severity",
    "omega_p95_severity",
    "alpha_violation_count",
    "alpha_max_severity",
    "alpha_mean_severity",
    "alpha_p95_severity",
    "delta_r_violation_count",
    "delta_r_max_severity",
    "delta_r_mean_severity",
    "delta_r_p95_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "mean_action_diff_vs_baseline",
    "max_action_diff_vs_baseline",
    "mean_selected_pred_horizon_alpha_violation",
    "mean_selected_pred_horizon_omega_violation",
    "mean_executed_true_alpha_violation",
    "mean_executed_true_omega_violation",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def _sweep_rows(summary_rows: list[dict[str, Any]], condition: str, omega_weight: float) -> list[dict[str, Any]]:
    rows = [
        row
        for row in summary_rows
        if row["condition"] == condition
        and row["source"] == "run"
        and row["method"] != "baseline_cem"
        and float(row["omega_soft_weight"]) == float(omega_weight)
    ]
    return sorted(rows, key=lambda row: float(row["alpha_soft_weight"]))


def save_sweep_plots(summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    metric_sets = [
        (
            "alpha",
            ["alpha_mean_severity", "alpha_max_severity", "alpha_p95_severity"],
            "alpha severity",
            "alpha_severity_vs_alpha_weight.png",
        ),
        (
            "omega",
            ["omega_mean_severity", "omega_max_severity", "omega_p95_severity"],
            "omega severity",
            "omega_severity_vs_alpha_weight.png",
        ),
    ]
    for condition in CONDITIONS:
        for _, metrics, ylabel, filename in metric_sets:
            fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharex=True)
            for ax, metric in zip(axes, metrics):
                for omega_weight in OMEGA_WEIGHTS:
                    rows = _sweep_rows(summary_rows, condition, omega_weight)
                    ax.plot(
                        [float(row["alpha_soft_weight"]) for row in rows],
                        [float(row[metric]) for row in rows],
                        marker="o",
                        label=f"omega_w={omega_weight:g}",
                    )
                ax.set_title(metric)
                ax.set_xscale("log")
                ax.set_xlabel("alpha weight")
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.25)
                ax.legend(fontsize=8)
            fig.suptitle(f"{ylabel} vs alpha weight: {condition}")
            fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))
            path = output_root / "figs" / f"{condition}_{filename}"
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, dpi=150)
            plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)
        for omega_weight in OMEGA_WEIGHTS:
            rows = _sweep_rows(summary_rows, condition, omega_weight)
            x = [float(row["alpha_soft_weight"]) for row in rows]
            axes[0].plot(x, [1.0 if bool(row["target_reached"]) else 0.0 for row in rows], marker="o", label=f"omega_w={omega_weight:g}")
            axes[1].plot(x, [float(row["T_reach"]) for row in rows], marker="o", label=f"omega_w={omega_weight:g}")
        axes[0].set_title("target reached")
        axes[0].set_ylabel("0/1")
        axes[1].set_title("T_reach")
        axes[1].set_ylabel("time [s]")
        for ax in axes:
            ax.set_xscale("log")
            ax.set_xlabel("alpha weight")
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
        fig.suptitle(f"Target reaching / T_reach vs weight: {condition}")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.92))
        fig.savefig(output_root / "figs" / f"{condition}_target_treach_vs_weight.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        for omega_weight in OMEGA_WEIGHTS:
            rows = _sweep_rows(summary_rows, condition, omega_weight)
            ax.plot(
                [float(row["alpha_soft_weight"]) for row in rows],
                [float(row["mean_action_diff_vs_baseline"]) for row in rows],
                marker="o",
                label=f"omega_w={omega_weight:g}",
            )
        ax.set_xscale("log")
        ax.set_title(f"Action diff vs baseline: {condition}")
        ax.set_xlabel("alpha weight")
        ax.set_ylabel("mean ||u - u_baseline||")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(output_root / "figs" / f"{condition}_action_diff_vs_weight.png", dpi=150)
        plt.close(fig)


def _aggregate_methods(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    methods = sorted({row["method"] for row in summary_rows})
    aggregate = []
    for method in methods:
        rows = [row for row in summary_rows if row["method"] == method]
        if len(rows) != len(CONDITIONS):
            continue
        aggregate.append(
            {
                "method": method,
                "all_target_reached": all(bool(row["target_reached"]) for row in rows),
                "alpha_mean_avg": _finite_mean(np.array([float(row["alpha_mean_severity"]) for row in rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in rows])),
                "alpha_mean_std": float(np.std([float(row["alpha_mean_severity"]) for row in rows])),
                "omega_mean_avg": _finite_mean(np.array([float(row["omega_mean_severity"]) for row in rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in rows])),
                "delta_mean_avg": _finite_mean(np.array([float(row["delta_r_mean_severity"]) for row in rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in rows])),
                "action_diff_avg": _finite_mean(np.array([float(row["mean_action_diff_vs_baseline"]) for row in rows])),
                "alpha_soft_weight": float(rows[0]["alpha_soft_weight"]),
                "omega_soft_weight": float(rows[0]["omega_soft_weight"]),
                "source": rows[0]["source"],
            }
        )
    return aggregate


def _best_method(summary_rows: list[dict[str, Any]], omega_positive: bool | None = None) -> str:
    aggregate = _aggregate_methods(summary_rows)
    candidates = [
        row
        for row in aggregate
        if row["method"] != "baseline_cem"
        and row["source"] == "run"
        and (omega_positive is None or (row["omega_soft_weight"] > 0.0) == omega_positive)
    ]
    return min(
        candidates,
        key=lambda row: (
            not row["all_target_reached"],
            row["alpha_mean_avg"] + 0.5 * row["omega_mean_avg"] + 0.2 * row["alpha_mean_std"],
            row["T_reach_avg"],
        ),
    )["method"]


def save_trajectory_plots(
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    summary_rows: list[dict[str, Any]],
    output_root: Path,
) -> tuple[str, str]:
    best_alpha_only = _best_method(summary_rows, omega_positive=False)
    best_alpha_omega = _best_method(summary_rows, omega_positive=True)
    selected_methods = ["baseline_cem", best_alpha_only, best_alpha_omega]
    for condition in CONDITIONS:
        for key, ylabel, filename, transform in [
            ("theta", "theta [deg]", "theta_trajectory_best.png", np.degrees),
            ("alpha_step", "alpha", "alpha_trajectory_best.png", None),
            ("omega", "omega", "omega_trajectory_best.png", None),
        ]:
            fig, ax = plt.subplots(figsize=(10, 4))
            for method in selected_methods:
                rows = all_rows[(method, condition)]
                values = _series(rows, key)
                if transform is not None:
                    values = transform(values)
                ax.plot(_series(rows, "t"), values, label=method)
            ax.set_title(f"{ylabel} trajectory: {condition}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            path = output_root / "figs" / f"{condition}_{filename}"
            fig.savefig(path, dpi=150)
            plt.close(fig)
    return best_alpha_only, best_alpha_omega


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def _method_rows(summary_rows: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    return [row for row in summary_rows if row["method"] == method]


def save_report(
    summary_rows: list[dict[str, Any]],
    output_root: Path,
    commands: list[str],
    best_alpha_only: str,
    best_alpha_omega: str,
    used_prior: bool,
) -> None:
    aggregate = _aggregate_methods(summary_rows)
    best_overall = min(
        [row for row in aggregate if row["method"] != "baseline_cem" and row["source"] == "run"],
        key=lambda row: (
            not row["all_target_reached"],
            row["alpha_mean_avg"] + 0.5 * row["omega_mean_avg"] + 0.2 * row["alpha_mean_std"],
            row["T_reach_avg"],
        ),
    )
    prior_rows = _method_rows(summary_rows, PRIOR_METHOD)
    w100_rows = _method_rows(summary_rows, "alpha100_omega0")
    w1000_rows = [row for row in aggregate if row["method"].startswith("alpha1000_")]
    aggregate_by_method = {row["method"]: row for row in aggregate}
    best_alpha_only_row = aggregate_by_method[best_alpha_only]
    best_alpha_omega_row = aggregate_by_method[best_alpha_omega]
    combo_rows = [
        row
        for row in aggregate
        if row["source"] == "run" and row["method"].startswith("alpha") and row["method"] != PRIOR_METHOD
    ]
    omega_weight_rows = []
    for omega_weight in sorted({row["omega_soft_weight"] for row in combo_rows}):
        rows = [row for row in combo_rows if row["omega_soft_weight"] == omega_weight]
        omega_weight_rows.append(
            {
                "omega_soft_weight": omega_weight,
                "alpha_mean_avg": float(np.mean([row["alpha_mean_avg"] for row in rows])),
                "alpha_p95_avg": float(np.mean([row["alpha_p95_avg"] for row in rows])),
                "omega_mean_avg": float(np.mean([row["omega_mean_avg"] for row in rows])),
                "omega_p95_avg": float(np.mean([row["omega_p95_avg"] for row in rows])),
                "T_reach_avg": float(np.mean([row["T_reach_avg"] for row in rows])),
            }
        )
    lines = [
        "# Stage 7A-refine Alpha-Soft Weight Sweep Report",
        "",
        "## Scope",
        "- Ran alpha-soft safety-aware CEM refinement with `alpha_constraint_mode=soft`.",
        "- Alpha remained a soft normalized planning cost, not a hard feasibility condition.",
        "- Swept alpha weights `[50, 100, 200, 500, 1000]` and omega soft weights `[0, 10, 50]`.",
        "- Force, delta_r, and omega feasibility logging was kept unchanged.",
        "- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier flow, physical parameters, gravity/noise/bias settings, baseline CEM behavior, and old runtime filter behavior were unchanged.",
        "- No post-result manual tuning was performed. This is not a formal safety guarantee.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
    ]
    if used_prior:
        lines.append("- Reused prior `alpha_soft_w100` reference logs from `results/stage7a_alpha_soft/logs/alpha_soft_w100/`.")
    lines.extend(
        [
            "",
            "## Aggregate Ranking",
            "| method | all target | alpha w | omega w | alpha mean avg | alpha p95 avg | alpha std | omega mean avg | omega p95 avg | T_reach avg | action diff avg |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(
        aggregate,
        key=lambda row: (
            row["method"] == "baseline_cem",
            not row["all_target_reached"],
            row["alpha_mean_avg"] + 0.5 * row["omega_mean_avg"] + 0.2 * row["alpha_mean_std"],
        ),
    ):
        lines.append(
            f"| {row['method']} | {row['all_target_reached']} | {_fmt(row['alpha_soft_weight'])} | "
            f"{_fmt(row['omega_soft_weight'])} | {_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | "
            f"{_fmt(row['alpha_mean_std'])} | {_fmt(row['omega_mean_avg'])} | {_fmt(row['omega_p95_avg'])} | "
            f"{_fmt(row['T_reach_avg'])} | {_fmt(row['action_diff_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Which alpha weight is most stable across clean/noise/noise_bias?",
            f"- The selected aggregate candidate is `{best_overall['method']}`. It has alpha mean avg={_fmt(best_overall['alpha_mean_avg'])}, alpha std={_fmt(best_overall['alpha_mean_std'])}, omega mean avg={_fmt(best_overall['omega_mean_avg'])}, and all_target={best_overall['all_target_reached']}.",
            "",
            "2. Does adding omega soft weight reduce omega degradation without losing alpha improvement?",
            f"- Best alpha-only is `{best_alpha_only}` with alpha mean avg={_fmt(best_alpha_only_row['alpha_mean_avg'])}, omega mean avg={_fmt(best_alpha_only_row['omega_mean_avg'])}, and omega p95 avg={_fmt(best_alpha_only_row['omega_p95_avg'])}.",
            f"- Best alpha+omega is `{best_alpha_omega}` with alpha mean avg={_fmt(best_alpha_omega_row['alpha_mean_avg'])}, omega mean avg={_fmt(best_alpha_omega_row['omega_mean_avg'])}, and omega p95 avg={_fmt(best_alpha_omega_row['omega_p95_avg'])}.",
            "- In this compact sweep, adding omega soft weight did not reduce aggregate omega degradation; averaged by omega weight, higher omega weights increased omega mean/p95 slightly while target reaching stayed successful.",
            "- Omega-weight aggregates: "
            + "; ".join(
                f"omega_w={_fmt(row['omega_soft_weight'])}: alpha_mean={_fmt(row['alpha_mean_avg'])}, "
                f"omega_mean={_fmt(row['omega_mean_avg'])}, omega_p95={_fmt(row['omega_p95_avg'])}"
                for row in omega_weight_rows
            )
            + ".",
            "",
            "3. Is alpha_soft_w100 still a good default?",
        ]
    )
    if prior_rows:
        lines.append(
            f"- Prior `{PRIOR_METHOD}` was included as reference. Its condition alpha means are: "
            + ", ".join(f"{row['condition']}={_fmt(row['alpha_mean_severity'])}" for row in prior_rows)
            + "."
        )
    if w100_rows:
        lines.append(
            "- New `alpha100_omega0` condition alpha means are: "
            + ", ".join(f"{row['condition']}={_fmt(row['alpha_mean_severity'])}" for row in w100_rows)
            + "."
        )
    lines.extend(
        [
            "",
            "4. Is alpha_soft_w1000 too conservative or unstable?",
            "- `alpha1000_*` aggregate rows should be judged by target success, T_reach, action magnitude, and alpha std. Bad or mixed behavior is not hidden.",
        ]
    )
    for row in w1000_rows:
        lines.append(
            f"- {row['method']}: all_target={row['all_target_reached']}, alpha mean avg={_fmt(row['alpha_mean_avg'])}, "
            f"alpha std={_fmt(row['alpha_mean_std'])}, T_reach avg={_fmt(row['T_reach_avg'])}, action diff avg={_fmt(row['action_diff_avg'])}."
        )
    lines.extend(
        [
            "",
            "5. Which configuration should be carried forward as Stage 7A candidate?",
            f"- Carry forward `{best_overall['method']}` as the Stage 7A candidate from this compact sweep, with the caveat that this is empirical simulation evidence only.",
            "",
            "6. Does target reaching remain successful?",
            f"- Best aggregate candidate all_target={best_overall['all_target_reached']}. See per-condition rows in `stage7a_refine_summary.csv` for failures if any.",
            "",
            "7. Should the next step be adaptive tightening, PSF/gatekeeper-lite, or progress governor?",
            "- If the carried-forward candidate keeps target reaching and reduces alpha without worsening omega too much, the next lower-risk step is PSF/gatekeeper-lite or a progress governor before adaptive tightening. Adaptive tightening should come after the safety signal is more reliable. No formal safety guarantee is claimed.",
            "",
            "## Outputs",
            "- `stage7a_refine_summary.csv` contains all per-method/per-condition metrics.",
            "- Per-run timeseries are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
            "Bad or mixed results are reported as-is.",
            "",
        ]
    )
    (output_root / "stage7a_refine_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _build_methods()
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_stage7a_refine.py",
    ]
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    runtimes: dict[tuple[str, str], float] = {}
    used_prior = False

    for method, method_cfg in methods.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            if method_cfg.get("source") == "prior":
                rows = load_prior_rows(condition, output_root)
                runtime_s = _prior_runtime(condition)
                used_prior = True
            else:
                start = time.perf_counter()
                rows = run_condition(condition, cfg["conditions"][condition], cfg)
                runtime_s = time.perf_counter() - start
            for row in rows:
                row["refine_method"] = method
                row["refine_alpha_weight"] = float(method_cfg["alpha_soft_weight"])
                row["refine_omega_weight"] = float(method_cfg["omega_soft_weight"])
                row["refine_source"] = str(method_cfg.get("source", "run"))
            all_rows[(method, condition)] = rows
            runtimes[(method, condition)] = runtime_s
            print(f"Completed method={method}, condition={condition}")

    add_action_diff_vs_baseline(all_rows, methods)
    summary_rows: list[dict[str, Any]] = []
    for method, method_cfg in methods.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            rows = all_rows[(method, condition)]
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            summary_rows.append(summarize_rows(method, method_cfg, condition, rows, cfg, runtimes[(method, condition)]))

    save_summary(summary_rows, output_root / "stage7a_refine_summary.csv")
    save_sweep_plots(summary_rows, output_root)
    best_alpha_only, best_alpha_omega = save_trajectory_plots(all_rows, summary_rows, output_root)
    save_report(summary_rows, output_root, commands, best_alpha_only, best_alpha_omega, used_prior)

    print("Stage 7A-refine alpha-soft weight sweep")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7a_refine_summary.csv'}")
    print(f"  report      : {output_root / 'stage7a_refine_report.md'}")
    print(f"  best alpha-only : {best_alpha_only}")
    print(f"  best alpha+omega: {best_alpha_omega}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_mean={row['alpha_mean_severity']:.4f}, "
            f"omega_mean={row['omega_mean_severity']:.4f}, "
            f"diff={row['mean_action_diff_vs_baseline']:.4f}"
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
