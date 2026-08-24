"""Stage 7C-revise alpha-tail-aware gatekeeper comparison for Spring2D CEM-MPC."""

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
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7c_gatekeeper_alpha_tail"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "baseline_cem",
    "alpha100_omega0",
    "alpha200_omega0",
    "gatekeeper_H3",
    "alpha_tail_gatekeeper_w10",
    "alpha_tail_gatekeeper_w50",
    "alpha_tail_gatekeeper_w100",
]
GATEKEEPER_METHODS = [
    "gatekeeper_H3",
    "alpha_tail_gatekeeper_w10",
    "alpha_tail_gatekeeper_w50",
    "alpha_tail_gatekeeper_w100",
]


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


def _method_configs() -> dict[str, dict[str, Any]]:
    base = {
        "solver_safety_mode": "off",
        "alpha_constraint_mode": "soft",
        "alpha_soft_weight": 1.0,
        "omega_soft_weight": 0.0,
        "gatekeeper_mode": "off",
        "gatekeeper_horizon": 0,
        "gatekeeper_top_k": 20,
        "runtime_filter": {"enabled": False},
        "gatekeeper_alpha_max_weight": 4.0,
        "gatekeeper_alpha_sum_weight": 4.0,
        "gatekeeper_omega_max_weight": 4.0,
        "gatekeeper_omega_sum_weight": 4.0,
        "gatekeeper_delta_r_weight": 1.0,
        "gatekeeper_force_weight": 1.0,
    }

    def alpha_tail(alpha_max_weight: float) -> dict[str, Any]:
        return {
            **base,
            "gatekeeper_mode": "candidate_select",
            "gatekeeper_horizon": 3,
            "gatekeeper_alpha_max_weight": alpha_max_weight,
            "gatekeeper_alpha_sum_weight": 10.0,
            "gatekeeper_omega_max_weight": 5.0,
            "gatekeeper_omega_sum_weight": 1.0,
            "gatekeeper_delta_r_weight": 5.0,
            "gatekeeper_force_weight": 5.0,
        }

    return {
        "baseline_cem": dict(base),
        "alpha100_omega0": {
            **base,
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 100.0,
        },
        "alpha200_omega0": {
            **base,
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 200.0,
        },
        "gatekeeper_H3": {
            **base,
            "gatekeeper_mode": "candidate_select",
            "gatekeeper_horizon": 3,
        },
        "alpha_tail_gatekeeper_w10": alpha_tail(10.0),
        "alpha_tail_gatekeeper_w50": alpha_tail(50.0),
        "alpha_tail_gatekeeper_w100": alpha_tail(100.0),
    }


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = copy.deepcopy(method_cfg["runtime_filter"])
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver["alpha_constraint_mode"] = method_cfg["alpha_constraint_mode"]
    solver["alpha_soft_weight"] = float(method_cfg["alpha_soft_weight"])
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["gatekeeper_mode"] = method_cfg["gatekeeper_mode"]
    solver["gatekeeper_horizon"] = int(method_cfg["gatekeeper_horizon"])
    solver["gatekeeper_top_k"] = int(method_cfg["gatekeeper_top_k"])
    solver["gatekeeper_alpha_max_weight"] = float(method_cfg["gatekeeper_alpha_max_weight"])
    solver["gatekeeper_alpha_sum_weight"] = float(method_cfg["gatekeeper_alpha_sum_weight"])
    solver["gatekeeper_omega_max_weight"] = float(method_cfg["gatekeeper_omega_max_weight"])
    solver["gatekeeper_omega_sum_weight"] = float(method_cfg["gatekeeper_omega_sum_weight"])
    solver["gatekeeper_delta_r_weight"] = float(method_cfg["gatekeeper_delta_r_weight"])
    solver["gatekeeper_force_weight"] = float(method_cfg["gatekeeper_force_weight"])
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
    action = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(action, axis=1)
    action_smoothness = np.linalg.norm(np.diff(action, axis=0), axis=1) if len(action) > 1 else np.array([])
    alpha_sev = _severity(rows, "alpha_step", alpha_max)
    omega_sev = _severity(rows, "omega", omega_max)
    delta_r_sev = _severity(rows, "delta_r", delta_r_max)
    F_tan_sev = _severity(rows, "F_tan", F_tan_max)
    F_rad_sev = _severity(rows, "F_rad", F_rad_max)
    decisions = _decision_rows(rows)
    intervention_count = int(sum(bool(row.get("gatekeeper_intervened", False)) for row in decisions))
    return {
        "method": method,
        "condition": condition,
        "gatekeeper_mode": str(method_cfg["gatekeeper_mode"]),
        "gatekeeper_horizon": int(method_cfg["gatekeeper_horizon"]),
        "gatekeeper_top_k": int(method_cfg["gatekeeper_top_k"]),
        "gatekeeper_alpha_max_weight": float(method_cfg["gatekeeper_alpha_max_weight"]),
        "gatekeeper_alpha_sum_weight": float(method_cfg["gatekeeper_alpha_sum_weight"]),
        "gatekeeper_omega_max_weight": float(method_cfg["gatekeeper_omega_max_weight"]),
        "gatekeeper_omega_sum_weight": float(method_cfg["gatekeeper_omega_sum_weight"]),
        "gatekeeper_delta_r_weight": float(method_cfg["gatekeeper_delta_r_weight"]),
        "gatekeeper_force_weight": float(method_cfg["gatekeeper_force_weight"]),
        "solver_safety_mode": str(final.get("cem_safety_mode", method_cfg["solver_safety_mode"])),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", method_cfg["alpha_constraint_mode"])),
        "alpha_soft_weight": float(method_cfg["alpha_soft_weight"]),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "gatekeeper_intervention_count": intervention_count,
        "gatekeeper_decision_count": int(len(decisions)),
        "gatekeeper_intervention_rate": float(intervention_count / len(decisions)) if decisions else np.nan,
        "gatekeeper_selected_rank_mean": _finite_mean(_series(decisions, "gatekeeper_selected_rank")),
        "gatekeeper_selected_rank_max": _finite_max(_series(decisions, "gatekeeper_selected_rank")),
        "nominal_safety_score_mean": _finite_mean(_series(decisions, "gatekeeper_nominal_safety_score")),
        "selected_safety_score_mean": _finite_mean(_series(decisions, "gatekeeper_selected_safety_score")),
        "nominal_alpha_max_mean": _finite_mean(
            _series(decisions, "gatekeeper_nominal_max_norm_violation_alpha")
        ),
        "selected_alpha_max_mean": _finite_mean(
            _series(decisions, "gatekeeper_selected_max_norm_violation_alpha")
        ),
        "nominal_alpha_sum_mean": _finite_mean(
            _series(decisions, "gatekeeper_nominal_sum_norm_violation_alpha")
        ),
        "selected_alpha_sum_mean": _finite_mean(
            _series(decisions, "gatekeeper_selected_sum_norm_violation_alpha")
        ),
        "nominal_omega_max_mean": _finite_mean(
            _series(decisions, "gatekeeper_nominal_max_norm_violation_omega")
        ),
        "selected_omega_max_mean": _finite_mean(
            _series(decisions, "gatekeeper_selected_max_norm_violation_omega")
        ),
        "nominal_omega_sum_mean": _finite_mean(
            _series(decisions, "gatekeeper_nominal_sum_norm_violation_omega")
        ),
        "selected_omega_sum_mean": _finite_mean(
            _series(decisions, "gatekeeper_selected_sum_norm_violation_omega")
        ),
        "nominal_task_cost_mean": _finite_mean(_series(decisions, "gatekeeper_nominal_task_cost")),
        "selected_task_cost_mean": _finite_mean(_series(decisions, "gatekeeper_selected_task_cost")),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_p95(alpha_sev),
        "alpha_max_severity": _finite_max(alpha_sev),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_p95_severity": _finite_p95(omega_sev),
        "omega_max_severity": _finite_max(omega_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "delta_r_p95_severity": _finite_p95(delta_r_sev),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "gatekeeper_mode",
    "gatekeeper_horizon",
    "gatekeeper_top_k",
    "gatekeeper_alpha_max_weight",
    "gatekeeper_alpha_sum_weight",
    "gatekeeper_omega_max_weight",
    "gatekeeper_omega_sum_weight",
    "gatekeeper_delta_r_weight",
    "gatekeeper_force_weight",
    "solver_safety_mode",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "gatekeeper_intervention_count",
    "gatekeeper_decision_count",
    "gatekeeper_intervention_rate",
    "gatekeeper_selected_rank_mean",
    "gatekeeper_selected_rank_max",
    "nominal_safety_score_mean",
    "selected_safety_score_mean",
    "nominal_alpha_max_mean",
    "selected_alpha_max_mean",
    "nominal_alpha_sum_mean",
    "selected_alpha_sum_mean",
    "nominal_omega_max_mean",
    "selected_omega_max_mean",
    "nominal_omega_sum_mean",
    "selected_omega_sum_mean",
    "nominal_task_cost_mean",
    "selected_task_cost_mean",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_p95_severity",
    "alpha_max_severity",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_p95_severity",
    "omega_max_severity",
    "delta_r_violation_count",
    "delta_r_mean_severity",
    "delta_r_max_severity",
    "delta_r_p95_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def _row(summary_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    for row in summary_rows:
        if row["method"] == method and row["condition"] == condition:
            return row
    raise KeyError((method, condition))


def _aggregate(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        method_rows = [row for row in summary_rows if row["method"] == method]
        rows.append(
            {
                "method": method,
                "target_success_count": int(sum(bool(row["target_reached"]) for row in method_rows)),
                "alpha_mean_avg": _finite_mean(np.array([float(row["alpha_mean_severity"]) for row in method_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "intervention_rate_avg": _finite_mean(
                    np.array([float(row["gatekeeper_intervention_rate"]) for row in method_rows])
                ),
                "selected_rank_avg": _finite_mean(
                    np.array([float(row["gatekeeper_selected_rank_mean"]) for row in method_rows])
                ),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
            }
        )
    return rows


def _best_alpha_tail(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in aggregate_rows if row["method"].startswith("alpha_tail_gatekeeper_")]
    return min(
        candidates,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            row["alpha_p95_avg"],
            row["alpha_max_avg"],
            row["omega_p95_avg"],
            row["intervention_rate_avg"],
        ),
    )


def save_trajectory_plots(all_rows: dict[tuple[str, str], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for condition in CONDITIONS:
        for key, ylabel, filename, transform in [
            ("theta", "theta [deg]", "theta_trajectory.png", np.degrees),
            ("alpha_step", "alpha", "alpha_trajectory.png", None),
            ("omega", "omega", "omega_trajectory.png", None),
        ]:
            fig, ax = plt.subplots(figsize=(12, 4.5))
            for method in METHODS:
                rows = all_rows[(method, condition)]
                values = _series(rows, key)
                if transform is not None:
                    values = transform(values)
                ax.plot(_series(rows, "t"), values, label=method)
            ax.set_title(f"{condition}: {ylabel}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=7, ncol=3)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}", dpi=150)
            plt.close(fig)


def save_gatekeeper_plots(all_rows: dict[tuple[str, str], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for condition in CONDITIONS:
        fig, ax = plt.subplots(figsize=(11, 4.5))
        for method in GATEKEEPER_METHODS:
            decisions = _decision_rows(all_rows[(method, condition)])
            flags = np.array([1.0 if bool(row.get("gatekeeper_intervened", False)) else 0.0 for row in decisions])
            rate = np.cumsum(flags) / np.maximum(1, np.arange(1, len(flags) + 1))
            ax.plot(_series(decisions, "t"), rate, label=method)
        ax.set_title(f"{condition}: cumulative intervention rate")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("intervention rate")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_intervention_rate_over_time.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4.5))
        for method in GATEKEEPER_METHODS:
            decisions = _decision_rows(all_rows[(method, condition)])
            ax.plot(
                _series(decisions, "t"),
                _series(decisions, "gatekeeper_nominal_max_norm_violation_alpha"),
                label=f"{method} nominal",
            )
            ax.plot(
                _series(decisions, "t"),
                _series(decisions, "gatekeeper_selected_max_norm_violation_alpha"),
                linestyle="--",
                label=f"{method} selected",
            )
        ax.set_title(f"{condition}: nominal vs selected alpha max violation")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("normalized alpha max violation")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_nominal_vs_selected_alpha_max.png", dpi=150)
        plt.close(fig)


def save_bar_plots(summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(CONDITIONS))
    width = 0.11
    offsets = np.linspace(-3.0 * width, 3.0 * width, len(METHODS))
    for label, p95_metric, max_metric in [
        ("alpha", "alpha_p95_severity", "alpha_max_severity"),
        ("omega", "omega_p95_severity", "omega_max_severity"),
    ]:
        fig, axes = plt.subplots(2, 1, figsize=(14, 7.5), sharex=True)
        for offset, method in zip(offsets, METHODS):
            p95_values = [float(_row(summary_rows, method, condition)[p95_metric]) for condition in CONDITIONS]
            max_values = [float(_row(summary_rows, method, condition)[max_metric]) for condition in CONDITIONS]
            axes[0].bar(x + offset, p95_values, width=width, label=method)
            axes[1].bar(x + offset, max_values, width=width, label=method)
        axes[0].set_ylabel(f"{label} p95 severity")
        axes[1].set_ylabel(f"{label} max severity")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(CONDITIONS)
        for ax in axes:
            ax.grid(True, axis="y", alpha=0.25)
        axes[0].legend(fontsize=7, ncol=3)
        fig.suptitle(f"Stage 7C alpha-tail: {label} p95/max severity")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        fig.savefig(fig_dir / f"{label}_p95_max_bar.png", dpi=150)
        plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = _aggregate(summary_rows)
    by_method = {row["method"]: row for row in aggregate}
    best = _best_alpha_tail(aggregate)
    baseline = by_method["baseline_cem"]
    alpha100 = by_method["alpha100_omega0"]
    alpha200 = by_method["alpha200_omega0"]
    old_h3 = by_method["gatekeeper_H3"]
    alpha_soft_best_p95 = min(alpha100["alpha_p95_avg"], alpha200["alpha_p95_avg"])
    alpha_soft_best_max = min(alpha100["alpha_max_avg"], alpha200["alpha_max_avg"])
    tail_methods = [by_method[method] for method in METHODS if method.startswith("alpha_tail_gatekeeper_")]
    preserves_target = all(row["target_success_count"] == len(CONDITIONS) for row in tail_methods)
    improves_vs_old = best["alpha_p95_avg"] < old_h3["alpha_p95_avg"] and best["alpha_max_avg"] < old_h3["alpha_max_avg"]
    improves_vs_baseline = (
        best["alpha_p95_avg"] < baseline["alpha_p95_avg"] and best["alpha_max_avg"] < baseline["alpha_max_avg"]
    )
    improves_vs_alpha_soft = best["alpha_p95_avg"] < alpha_soft_best_p95 and best["alpha_max_avg"] < alpha_soft_best_max
    avoids_omega_tail = best["omega_p95_avg"] <= baseline["omega_p95_avg"] and best["omega_max_avg"] <= baseline[
        "omega_max_avg"
    ]
    continue_stress = preserves_target and improves_vs_old and improves_vs_baseline and avoids_omega_tail
    lines = [
        "# Stage 7C Alpha-Tail-Aware Gatekeeper Report",
        "",
        "## Scope",
        "- Revised gatekeeper-lite scoring only.",
        "- `gatekeeper_mode=candidate_select`, `H=3`, `K=20`; selection remains among top-K CEM candidate sequences.",
        "- No action clipping, scaling, or projection was added.",
        "- Alpha-tail methods used `alpha_max_weight` in `[10, 50, 100]` with fixed alpha/omega/delta_r/force weights.",
        "- Baseline CEM, runtime filter, alpha-soft CEM, progress governor, estimator/identifier flow, and Spring2D dynamics were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | intervention avg | selected rank avg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{_fmt(row['intervention_rate_avg'])} | {_fmt(row['selected_rank_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does alpha-tail-aware scoring reduce alpha p95/max vs old gatekeeper_H3?",
            f"- {'Yes' if improves_vs_old else 'No/mixed'}: best alpha-tail `{best['method']}` alpha p95/max avg={_fmt(best['alpha_p95_avg'])}/{_fmt(best['alpha_max_avg'])}; old H3={_fmt(old_h3['alpha_p95_avg'])}/{_fmt(old_h3['alpha_max_avg'])}.",
            "",
            "2. Does it improve alpha p95/max vs baseline and alpha-soft CEM?",
            f"- Vs baseline: {'Yes' if improves_vs_baseline else 'No/mixed'}; baseline alpha p95/max avg={_fmt(baseline['alpha_p95_avg'])}/{_fmt(baseline['alpha_max_avg'])}.",
            f"- Vs alpha-soft: {'Yes' if improves_vs_alpha_soft else 'No/mixed'}; best alpha-soft p95/max avg={_fmt(alpha_soft_best_p95)}/{_fmt(alpha_soft_best_max)}.",
            "",
            "3. Does it preserve target reaching?",
            f"- {'Yes' if preserves_target else 'No/mixed'}: alpha-tail methods target success counts are "
            + ", ".join(f"{row['method']}={row['target_success_count']}/{len(CONDITIONS)}" for row in tail_methods)
            + ".",
            "",
            "4. Does it still avoid omega tail risk?",
            f"- {'Yes' if avoids_omega_tail else 'No/mixed'} for best alpha-tail vs baseline using omega p95 and max: best={_fmt(best['omega_p95_avg'])}/{_fmt(best['omega_max_avg'])}, baseline={_fmt(baseline['omega_p95_avg'])}/{_fmt(baseline['omega_max_avg'])}.",
            "",
            "5. Which alpha_max_weight is best?",
            f"- `{best['method']}` is best by target success first, then alpha p95, alpha max, omega p95, and intervention rate.",
            "",
            "6. Should gatekeeper continue to stress validation, or be closed out?",
            f"- {'Continue to stress validation' if continue_stress else 'Close out or revise before stress validation'} based on this focused revision. Do not infer formal safety guarantees from this result.",
            "",
            "## Outputs",
            "- `stage7c_alpha_tail_summary.csv` contains per-method/per-condition metrics.",
            "- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
        ]
    )
    (output_root / "stage7c_alpha_tail_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _method_configs()
    commands = [
        "conda run -n mpc_learn python -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests",
        "conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7c_alpha_tail_gatekeeper.py",
    ]
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    runtimes: dict[tuple[str, str], float] = {}
    for method in METHODS:
        method_cfg = methods[method]
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            start = time.perf_counter()
            rows = run_condition(condition, cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            for row in rows:
                row["stage7c_alpha_tail_method"] = method
                row["stage7c_alpha_tail_condition"] = condition
            all_rows[(method, condition)] = rows
            runtimes[(method, condition)] = runtime_s
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            print(f"Completed method={method}, condition={condition}, runtime={runtime_s:.2f}s", flush=True)

    summary_rows: list[dict[str, Any]] = []
    for method in METHODS:
        method_cfg = methods[method]
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            rows = all_rows[(method, condition)]
            summary_rows.append(summarize_rows(method, method_cfg, condition, rows, cfg, runtimes[(method, condition)]))

    save_summary(summary_rows, output_root / "stage7c_alpha_tail_summary.csv")
    save_trajectory_plots(all_rows, output_root)
    save_gatekeeper_plots(all_rows, output_root)
    save_bar_plots(summary_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 7C alpha-tail-aware gatekeeper")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7c_alpha_tail_summary.csv'}")
    print(f"  report      : {output_root / 'stage7c_alpha_tail_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_p95={row['alpha_p95_severity']:.4f}, "
            f"alpha_max={row['alpha_max_severity']:.4f}, "
            f"omega_p95={row['omega_p95_severity']:.4f}, "
            f"gk_rate={row['gatekeeper_intervention_rate']:.4f}, "
            f"done={row['done_reason']}"
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
