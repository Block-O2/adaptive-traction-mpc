"""Stage 8C task and alpha-constraint definition diagnosis for Spring2D CEM-MPC."""

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

from run_spring2d_adaptive_mpc_conditions import load_experiment_config, run_condition
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage8c_constraint_revision"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "default_task",
    "relaxed_time",
    "lower_terminal_urgency",
    "alpha100_eval",
    "alpha200_eval",
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


def _finite_percentile(values: np.ndarray, q: float) -> float:
    values = _finite(values)
    return float(np.percentile(values, q)) if len(values) else np.nan


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return np.nan


def _clipped_max_excluding_one(values: np.ndarray) -> float:
    values = np.sort(_finite(values))
    if len(values) == 0:
        return np.nan
    if len(values) == 1:
        return 0.0
    return float(values[-2])


def _method_specs() -> list[dict[str, Any]]:
    return [
        {
            "method": "default_task",
            "diagnostic_family": "default_task",
            "solver_safety_mode": "off",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "notes": "current target, current max_time/max_steps, current alpha logging",
        },
        {
            "method": "relaxed_time",
            "diagnostic_family": "relaxed_time",
            "solver_safety_mode": "off",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "notes": "max_time and max_steps doubled; target and controller weights unchanged",
        },
        {
            "method": "lower_terminal_urgency",
            "diagnostic_family": "lower_terminal_urgency",
            "solver_safety_mode": "off",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "notes": "single explicit tracking-weight reduction: w_theta=45, w_terminal_theta=180",
        },
        {
            "method": "alpha100_eval",
            "diagnostic_family": "optional_soft_alpha_eval",
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 100.0,
            "omega_soft_weight": 0.0,
            "notes": "optional re-evaluation of existing alpha100_omega0 using Stage 8C alpha metrics",
        },
        {
            "method": "alpha200_eval",
            "diagnostic_family": "optional_soft_alpha_eval",
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 200.0,
            "omega_soft_weight": 0.0,
            "notes": "optional re-evaluation of existing alpha200_omega0 using Stage 8C alpha metrics",
        },
    ]


def configure_run(base_cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    method = str(spec["method"])
    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}

    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = str(spec["solver_safety_mode"])
    solver["alpha_constraint_mode"] = "soft"
    solver["alpha_soft_weight"] = float(spec["alpha_soft_weight"])
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["gatekeeper_mode"] = "off"
    solver["gatekeeper_horizon"] = 0
    solver["gatekeeper_top_k"] = 20
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    violation_weights = dict(solver.get("safety_violation_weights", {}))
    violation_weights.update({"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 0.0, "alpha": 1.0})
    solver["safety_violation_weights"] = violation_weights

    weights = cfg["mpc_params"].setdefault("weights", {})
    weights["w_action_rate"] = 0.0
    weights["w_F_tan_rate"] = 0.0
    weights["w_F_rad_rate"] = 0.0
    if method == "relaxed_time":
        cfg["true_params"]["max_time"] = 2.0 * float(cfg["true_params"]["max_time"])
        cfg["run"]["max_steps"] = 2 * int(cfg["run"].get("max_steps", 1200))
    elif method == "lower_terminal_urgency":
        weights["w_theta"] = 45.0
        weights["w_terminal_theta"] = 180.0
    elif method not in {"default_task", "alpha100_eval", "alpha200_eval"}:
        raise ValueError(f"Unknown Stage 8C method: {method}")
    cfg["stage8c_method_spec"] = dict(spec)
    return cfg


def _severity_stats(values: np.ndarray, dt: float, times: np.ndarray) -> dict[str, float]:
    values = _finite(values)
    if len(values) == 0:
        return {
            "mean": np.nan,
            "p95": np.nan,
            "p99": np.nan,
            "max": np.nan,
            "clipped_max_excluding_top1": np.nan,
            "duration": 0.0,
            "integrated": 0.0,
        }
    return {
        "mean": _finite_mean(values),
        "p95": _finite_percentile(values, 95),
        "p99": _finite_percentile(values, 99),
        "max": _finite_max(values),
        "clipped_max_excluding_top1": _clipped_max_excluding_one(values),
        "duration": float(np.count_nonzero(values > 0.0) * dt),
        "integrated": float(np.sum(values) * dt),
    }


def summarize_rows(
    spec: dict[str, Any],
    condition: str,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
) -> dict[str, Any]:
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    t = _series(rows, "t")
    alpha_abs = np.abs(_series(rows, "alpha_step"))
    alpha_sev = np.maximum(0.0, alpha_abs - alpha_max)
    omega_abs = np.abs(_series(rows, "omega"))
    omega_sev = np.maximum(0.0, omega_abs - omega_max)
    early_mask = t <= 0.5
    late_mask = t > 0.5
    early = _severity_stats(alpha_sev[early_mask], dt, t[early_mask])
    late = _severity_stats(alpha_sev[late_mask], dt, t[late_mask])
    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(actions, axis=1)
    action_smoothness = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.array([])
    weights = cfg["mpc_params"].get("weights", {})
    solver = cfg["mpc_params"].get("solver", {})
    return {
        "method": str(spec["method"]),
        "diagnostic_family": str(spec["diagnostic_family"]),
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "alpha_limit": alpha_max,
        "alpha_abs_mean": _finite_mean(alpha_abs),
        "alpha_abs_p95": _finite_percentile(alpha_abs, 95),
        "alpha_abs_p99": _finite_percentile(alpha_abs, 99),
        "alpha_abs_max": _finite_max(alpha_abs),
        "alpha_abs_clipped_max_excluding_top1": _clipped_max_excluding_one(alpha_abs),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_clipped_max_excluding_top1": _clipped_max_excluding_one(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "alpha_integrated_violation": float(np.sum(alpha_sev) * dt),
        "early_alpha_mean_severity": early["mean"],
        "early_alpha_p95_severity": early["p95"],
        "early_alpha_p99_severity": early["p99"],
        "early_alpha_max_severity": early["max"],
        "early_alpha_violation_duration_s": early["duration"],
        "early_alpha_integrated_violation": early["integrated"],
        "late_alpha_mean_severity": late["mean"],
        "late_alpha_p95_severity": late["p95"],
        "late_alpha_p99_severity": late["p99"],
        "late_alpha_max_severity": late["max"],
        "late_alpha_violation_duration_s": late["duration"],
        "late_alpha_integrated_violation": late["integrated"],
        "omega_p95_severity": _finite_percentile(omega_sev, 95),
        "omega_max_severity": _finite_max(omega_sev),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "w_theta": float(weights.get("w_theta", np.nan)),
        "w_terminal_theta": float(weights.get("w_terminal_theta", np.nan)),
        "solver_safety_mode": str(solver.get("safety_mode", "off")),
        "alpha_soft_weight": float(solver.get("alpha_soft_weight", np.nan)),
        "max_time": float(cfg["true_params"]["max_time"]),
        "max_steps": int(cfg["run"].get("max_steps", 0)),
        "runtime_s": float(runtime_s),
        "notes": str(spec["notes"]),
    }


SUMMARY_FIELDS = [
    "method",
    "diagnostic_family",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "alpha_limit",
    "alpha_abs_mean",
    "alpha_abs_p95",
    "alpha_abs_p99",
    "alpha_abs_max",
    "alpha_abs_clipped_max_excluding_top1",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_p95_severity",
    "alpha_p99_severity",
    "alpha_max_severity",
    "alpha_clipped_max_excluding_top1",
    "alpha_violation_duration_s",
    "alpha_integrated_violation",
    "early_alpha_mean_severity",
    "early_alpha_p95_severity",
    "early_alpha_p99_severity",
    "early_alpha_max_severity",
    "early_alpha_violation_duration_s",
    "early_alpha_integrated_violation",
    "late_alpha_mean_severity",
    "late_alpha_p95_severity",
    "late_alpha_p99_severity",
    "late_alpha_max_severity",
    "late_alpha_violation_duration_s",
    "late_alpha_integrated_violation",
    "omega_p95_severity",
    "omega_max_severity",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "w_theta",
    "w_terminal_theta",
    "solver_safety_mode",
    "alpha_soft_weight",
    "max_time",
    "max_steps",
    "runtime_s",
    "notes",
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
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_p99_avg": _finite_mean(np.array([float(row["alpha_p99_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "alpha_clipped_max_avg": _finite_mean(
                    np.array([float(row["alpha_clipped_max_excluding_top1"]) for row in method_rows])
                ),
                "alpha_duration_avg": _finite_mean(np.array([float(row["alpha_violation_duration_s"]) for row in method_rows])),
                "alpha_integral_avg": _finite_mean(np.array([float(row["alpha_integrated_violation"]) for row in method_rows])),
                "early_alpha_max_avg": _finite_mean(np.array([float(row["early_alpha_max_severity"]) for row in method_rows])),
                "late_alpha_max_avg": _finite_mean(np.array([float(row["late_alpha_max_severity"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "runtime_avg": _finite_mean(np.array([float(row["runtime_s"]) for row in method_rows])),
            }
        )
    return rows


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_plots(
    summary_rows: list[dict[str, Any]],
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    output_root: Path,
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    colors = {
        "default_task": "tab:blue",
        "relaxed_time": "tab:green",
        "lower_terminal_urgency": "tab:orange",
        "alpha100_eval": "tab:red",
        "alpha200_eval": "tab:purple",
    }
    for condition in CONDITIONS:
        fig, ax = plt.subplots(figsize=(11, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), np.degrees(_series(rows, "theta")), label=method, color=colors[method])
        target = np.degrees(float(all_rows[("default_task", condition)][-1]["theta_target_final"]))
        ax.axhline(target, color="black", linestyle=":", label="theta_target")
        ax.set_title(f"{condition}: theta trajectory")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("theta [deg]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_theta_trajectory.png", dpi=150)
        plt.close(fig)

        alpha_limit = float(_row(summary_rows, "default_task", condition)["alpha_limit"])
        fig, ax = plt.subplots(figsize=(11, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), _series(rows, "alpha_step"), label=method, color=colors[method])
        ax.axhline(alpha_limit, color="black", linestyle=":", label="alpha threshold")
        ax.axhline(-alpha_limit, color="black", linestyle=":")
        ax.set_title(f"{condition}: alpha trajectory with threshold")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("alpha [rad/s^2]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_alpha_trajectory_threshold.png", dpi=150)
        plt.close(fig)

        default_rows = all_rows[("default_task", condition)]
        alpha_abs = np.abs(_series(default_rows, "alpha_step"))
        spike_t = float(_series(default_rows, "t")[int(np.nanargmax(alpha_abs))])
        fig, ax = plt.subplots(figsize=(11, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            t = _series(rows, "t")
            mask = (t >= spike_t - 0.25) & (t <= spike_t + 0.25)
            ax.plot(t[mask], _series(rows, "alpha_step")[mask], label=method, color=colors[method])
        ax.axhline(alpha_limit, color="black", linestyle=":", label="alpha threshold")
        ax.axhline(-alpha_limit, color="black", linestyle=":")
        ax.set_title(f"{condition}: zoomed alpha spike around default max")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("alpha [rad/s^2]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_alpha_spike_zoom.png", dpi=150)
        plt.close(fig)

    x = np.arange(len(METHODS))
    width = 0.18
    fig, ax = plt.subplots(figsize=(13, 6))
    aggregate = _aggregate(summary_rows)
    metric_specs = [
        ("alpha_p95_avg", "p95"),
        ("alpha_p99_avg", "p99"),
        ("alpha_max_avg", "max"),
        ("alpha_clipped_max_avg", "clipped max"),
    ]
    for idx, (metric, label) in enumerate(metric_specs):
        ax.bar(x + (idx - 1.5) * width, [float(row[metric]) for row in aggregate], width=width, label=label)
    ax.set_ylabel("alpha violation severity")
    ax.set_xticks(x)
    ax.set_xticklabels(METHODS, rotation=25, ha="right")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.suptitle("Stage 8C: alpha metric comparison")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "alpha_metric_comparison.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].bar(x, [float(row["alpha_duration_avg"]) for row in aggregate])
    axes[1].bar(x, [float(row["alpha_integral_avg"]) for row in aggregate])
    axes[0].set_ylabel("duration [s]")
    axes[1].set_ylabel("integrated violation")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(METHODS, rotation=25, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage 8C: alpha violation duration and integral")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "alpha_duration_integral.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    for row in aggregate:
        ax.scatter(float(row["T_reach_avg"]), float(row["alpha_p95_avg"]), label=f"{row['method']} p95")
        ax.scatter(float(row["T_reach_avg"]), float(row["alpha_max_avg"]), marker="x", label=f"{row['method']} max")
    ax.set_xlabel("T_reach avg [s]")
    ax.set_ylabel("alpha severity")
    ax.set_title("Stage 8C: T_reach vs alpha metrics")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(fig_dir / "T_reach_vs_alpha_metrics.png", dpi=150)
    plt.close(fig)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate_rows = _aggregate(summary_rows)
    by_method = {row["method"]: row for row in aggregate_rows}
    default = by_method["default_task"]
    relaxed = by_method["relaxed_time"]
    lower = by_method["lower_terminal_urgency"]
    isolated_ratio = (
        (float(default["alpha_max_avg"]) - float(default["alpha_clipped_max_avg"])) / float(default["alpha_max_avg"])
        if float(default["alpha_max_avg"]) > 0.0
        else 0.0
    )
    max_isolated = isolated_ratio >= 0.25
    p_metrics_differ = (
        float(default["alpha_p95_avg"]) < 0.75 * float(default["alpha_max_avg"])
        or float(default["alpha_clipped_max_avg"]) < 0.75 * float(default["alpha_max_avg"])
    )
    relaxed_reduces = (
        float(relaxed["alpha_p95_avg"]) < float(default["alpha_p95_avg"])
        and float(relaxed["alpha_max_avg"]) < float(default["alpha_max_avg"])
    )
    lower_reduces = (
        int(lower["target_success_count"]) == len(CONDITIONS)
        and float(lower["alpha_p95_avg"]) < float(default["alpha_p95_avg"])
        and float(lower["alpha_max_avg"]) < float(default["alpha_max_avg"])
    )
    current_conflict = not lower_reduces and not relaxed_reduces
    linked_ok = lower_reduces
    lines = [
        "# Stage 8C Task / Constraint Definition Revision Report",
        "",
        "## Scope",
        "- Diagnosis only: checked whether the current alpha metric/constraint is too strict, poorly defined, or conflicting with fast target reaching.",
        "- Mainline remains CEM + UKF-bias + filtered Windowed NLS.",
        "- Dynamics, estimator/identifier implementations, baseline CEM behavior, Stage 7 methods, and UKF settings were not intentionally changed.",
        "- Optional soft-alpha re-evaluation used existing alpha100/alpha200 settings only.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Diagnostic Overrides",
        "- `default_task`: current target, max_time/max_steps, and alpha logging.",
        "- `relaxed_time`: doubled `max_time` and `max_steps`; target and weights unchanged.",
        "- `lower_terminal_urgency`: single explicit reduction to `w_theta=45`, `w_terminal_theta=180`.",
        "- `alpha100_eval` / `alpha200_eval`: existing alpha-soft settings re-evaluated with Stage 8C metrics.",
        "",
        "## Aggregate Metrics",
        "| method | target successes | T_reach avg | alpha p95 | alpha p99 | alpha max | clipped max | duration | integrated | early max | late max | omega p95 | omega max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | {_fmt(row['T_reach_avg'])} | "
            f"{_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_p99_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['alpha_clipped_max_avg'])} | {_fmt(row['alpha_duration_avg'])} | {_fmt(row['alpha_integral_avg'])} | "
            f"{_fmt(row['early_alpha_max_avg'])} | {_fmt(row['late_alpha_max_avg'])} | "
            f"{_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Is alpha max dominated by isolated one-step spikes?",
            f"- {'Yes/partly' if max_isolated else 'No/not primarily'} for default_task: alpha max avg={_fmt(default['alpha_max_avg'])}, clipped max avg={_fmt(default['alpha_clipped_max_avg'])}, one-step reduction ratio={_fmt(isolated_ratio)}.",
            "",
            "2. Do p95/p99/duration/integrated violation tell a different story than max?",
            f"- {'Yes' if p_metrics_differ else 'No/mostly consistent'}: default p95/p99/max/clipped={_fmt(default['alpha_p95_avg'])}/{_fmt(default['alpha_p99_avg'])}/{_fmt(default['alpha_max_avg'])}/{_fmt(default['alpha_clipped_max_avg'])}, duration={_fmt(default['alpha_duration_avg'])}, integral={_fmt(default['alpha_integral_avg'])}.",
            "",
            "3. Does increasing allowed time reduce alpha tail?",
            f"- {'Yes' if relaxed_reduces else 'No'}: relaxed_time alpha p95/max={_fmt(relaxed['alpha_p95_avg'])}/{_fmt(relaxed['alpha_max_avg'])} vs default={_fmt(default['alpha_p95_avg'])}/{_fmt(default['alpha_max_avg'])}. Because the environment stops at target reach, relaxed time alone may not slow an already-reaching trajectory.",
            "",
            "4. Does lowering target urgency reduce alpha tail while preserving task completion?",
            f"- {'Yes' if lower_reduces else 'No/mixed'}: lower_terminal_urgency target={lower['target_success_count']}/{len(CONDITIONS)}, alpha p95/max={_fmt(lower['alpha_p95_avg'])}/{_fmt(lower['alpha_max_avg'])}.",
            "",
            "5. Is current alpha constraint better treated as hard safety, soft smoothness cost, or diagnostic metric?",
            "- Based on this diagnostic, treat raw alpha max as a diagnostic/tail-risk metric rather than a hard safety guarantee. p95/p99/duration/integral should be reported alongside any soft smoothness or safety cost.",
            "",
            "6. Should alpha evaluation use p95/p99/duration instead of raw max?",
            "- Use p95/p99/duration/integrated violation in addition to raw max, not as a silent replacement. Raw max remains useful for tail spikes, but alone can overstate or mischaracterize one-step events.",
            "",
            "7. Is the current task definition conflicting with the alpha requirement?",
            f"- {'Yes/likely' if current_conflict else 'Partly but reducible'} from this single-link diagnosis. The evidence should be read with Stage 8B: target-reaching and low alpha tail were not jointly achieved by simple oracle/budget/smoothness/time/urgency checks.",
            "",
            "8. Is it safe to move to linked rods after this, or should single-link task definition be revised first?",
            f"- {'Move only cautiously after documenting the single-link metric choice' if linked_ok else 'Revise the single-link task/alpha evaluation first'}; this is simulation evidence only and not a formal safety claim.",
            "",
            "## Notes",
            "- Bad or ambiguous results are retained directly. No post-result tuning was applied.",
        ]
    )
    (output_root / "stage8c_report.md").write_text("\n".join(lines) + "\n")


def run(output_root: Path, config_path: Path) -> None:
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]
    for spec in _method_specs():
        method = str(spec["method"])
        for condition in CONDITIONS:
            cfg = configure_run(base_cfg, spec)
            print(f"[stage8c] running {method} / {condition}", flush=True)
            start = time.perf_counter()
            rows = run_condition(condition, base_cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            summary = summarize_rows(spec, condition, rows, cfg, runtime_s)
            summary_rows.append(summary)
            print(
                "[stage8c] "
                f"{method}/{condition}: target={summary['target_reached']}, "
                f"T={summary['T_reach']:.4g}, "
                f"alpha_p95={summary['alpha_p95_severity']:.4g}, "
                f"alpha_max={summary['alpha_max_severity']:.4g}, "
                f"duration={summary['alpha_violation_duration_s']:.4g}, "
                f"runtime={runtime_s:.2f}s",
                flush=True,
            )
    save_summary(summary_rows, output_root / "stage8c_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands)
    print(f"[stage8c] summary: {output_root / 'stage8c_summary.csv'}", flush=True)
    print(f"[stage8c] report : {output_root / 'stage8c_report.md'}", flush=True)
    print(f"[stage8c] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
