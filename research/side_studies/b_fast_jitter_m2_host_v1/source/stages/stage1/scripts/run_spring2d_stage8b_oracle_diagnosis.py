"""Stage 8B single-link feasibility and oracle diagnosis for Spring2D CEM-MPC."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage8b_oracle_diagnosis"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "baseline_mainline",
    "oracle_cem",
    "high_budget_cem",
    "smooth_action_cem_diagnostic",
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


def _severity(rows: list[dict[str, Any]], key: str, limit: float) -> np.ndarray:
    return np.maximum(0.0, np.abs(_series(rows, key)) - float(limit))


def _method_specs() -> list[dict[str, Any]]:
    return [
        {
            "method": "baseline_mainline",
            "estimator_mode": "ukf_bias",
            "estimator_oracle": False,
            "identifier_mode": "filtered_windowed_nls",
            "identifier_oracle": False,
            "oracle_prediction_params": False,
            "diagnostic_notes": "default CEM budget with UKF-bias and filtered Windowed NLS",
        },
        {
            "method": "oracle_cem",
            "estimator_mode": "oracle_true_state",
            "estimator_oracle": True,
            "identifier_mode": "oracle_true_params_frozen",
            "identifier_oracle": True,
            "oracle_prediction_params": True,
            "diagnostic_notes": "true state and true physical parameters for MPC prediction; CEM budget unchanged",
        },
        {
            "method": "high_budget_cem",
            "estimator_mode": "ukf_bias",
            "estimator_oracle": False,
            "identifier_mode": "filtered_windowed_nls",
            "identifier_oracle": False,
            "oracle_prediction_params": False,
            "diagnostic_notes": "single explicit higher CEM budget: samples=256, elites=32, iterations=5, horizon=24",
        },
        {
            "method": "smooth_action_cem_diagnostic",
            "estimator_mode": "ukf_bias",
            "estimator_oracle": False,
            "identifier_mode": "filtered_windowed_nls",
            "identifier_oracle": False,
            "oracle_prediction_params": False,
            "diagnostic_notes": "single explicit action-rate penalty: w_F_tan_rate=0.05, w_F_rad_rate=1.0",
        },
    ]


def configure_run(base_cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    method = str(spec["method"])
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = "off"
    solver["alpha_constraint_mode"] = "soft"
    solver["alpha_soft_weight"] = 1.0
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["gatekeeper_mode"] = "off"
    solver["gatekeeper_horizon"] = 0
    solver["gatekeeper_top_k"] = 20
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False

    weights = cfg["mpc_params"].setdefault("weights", {})
    weights["w_action_rate"] = 0.0
    weights["w_F_tan_rate"] = 0.0
    weights["w_F_rad_rate"] = 0.0

    cfg["observation_filter"] = dict(FILTER_CONFIGS["ukf_bias"])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)

    if method == "oracle_cem":
        cfg["model_params"] = dict(cfg["true_params"])
        cfg["observation_filter"] = dict(FILTER_CONFIGS["oracle"])
        cfg["coupling_ablation"] = {
            "name": "oracle_true_state_true_params",
            "mpc_state_input": "oracle_true_state",
            "identifier_input": "none",
            "identifier_mode": "frozen",
            "estimator_model_params_source": "initial",
            "mpc_model_params_source": "initial",
        }
    elif method == "high_budget_cem":
        solver["num_samples"] = 256
        solver["num_elites"] = 32
        solver["iterations"] = 5
        solver["horizon"] = 24
    elif method == "smooth_action_cem_diagnostic":
        weights["w_F_tan_rate"] = 0.05
        weights["w_F_rad_rate"] = 1.0
    elif method != "baseline_mainline":
        raise ValueError(f"Unknown Stage 8B method: {method}")

    cfg["stage8b_method_spec"] = dict(spec)
    return cfg


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
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))

    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(actions, axis=1)
    action_smoothness = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.array([])
    alpha_sev = _severity(rows, "alpha_step", alpha_max)
    omega_sev = _severity(rows, "omega", omega_max)
    delta_r_sev = _severity(rows, "delta_r", delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    solver = cfg["mpc_params"].get("solver", {})
    weights = cfg["mpc_params"].get("weights", {})
    return {
        "method": str(spec["method"]),
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p90_severity": _finite_percentile(alpha_sev, 90),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_p95_severity": _finite_percentile(omega_sev, 95),
        "omega_max_severity": _finite_max(omega_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "force_violation_count": int(np.count_nonzero((F_tan_sev + F_rad_sev) > 0.0)),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "cem_num_samples": int(solver.get("num_samples", 0)),
        "cem_num_elites": int(solver.get("num_elites", 0)),
        "cem_iterations": int(solver.get("iterations", 0)),
        "cem_horizon": int(solver.get("horizon", 0)),
        "estimator_mode": str(spec["estimator_mode"]),
        "estimator_oracle": bool(spec["estimator_oracle"]),
        "identifier_mode": str(spec["identifier_mode"]),
        "identifier_oracle": bool(spec["identifier_oracle"]),
        "oracle_prediction_params": bool(spec["oracle_prediction_params"]),
        "w_action_rate": float(weights.get("w_action_rate", 0.0)),
        "w_F_tan_rate": float(weights.get("w_F_tan_rate", 0.0)),
        "w_F_rad_rate": float(weights.get("w_F_rad_rate", 0.0)),
        "runtime_s": float(runtime_s),
        "diagnostic_notes": str(spec["diagnostic_notes"]),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_p90_severity",
    "alpha_p95_severity",
    "alpha_p99_severity",
    "alpha_max_severity",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_p95_severity",
    "omega_max_severity",
    "delta_r_violation_count",
    "delta_r_mean_severity",
    "delta_r_max_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "force_violation_count",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "cem_num_samples",
    "cem_num_elites",
    "cem_iterations",
    "cem_horizon",
    "estimator_mode",
    "estimator_oracle",
    "identifier_mode",
    "identifier_oracle",
    "oracle_prediction_params",
    "w_action_rate",
    "w_F_tan_rate",
    "w_F_rad_rate",
    "runtime_s",
    "diagnostic_notes",
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
                "alpha_p99_avg": _finite_mean(np.array([float(row["alpha_p99_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "action_mag_avg": _finite_mean(np.array([float(row["mean_action_magnitude"]) for row in method_rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
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
        "baseline_mainline": "tab:blue",
        "oracle_cem": "tab:green",
        "high_budget_cem": "tab:orange",
        "smooth_action_cem_diagnostic": "tab:red",
    }
    for condition in CONDITIONS:
        fig, ax = plt.subplots(figsize=(11, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), np.degrees(_series(rows, "theta")), label=method, color=colors[method])
        target = float(np.degrees(float(all_rows[("baseline_mainline", condition)][-1]["theta_target_final"])))
        ax.axhline(target, color="black", linestyle=":", label="theta_target")
        ax.set_title(f"{condition}: theta trajectories")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("theta [deg]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_theta_trajectories.png", dpi=150)
        plt.close(fig)

        for key, label, filename in [
            ("alpha_step", "alpha [rad/s^2]", "alpha_trajectories"),
            ("omega", "omega [rad/s]", "omega_trajectories"),
        ]:
            fig, ax = plt.subplots(figsize=(11, 5))
            for method in METHODS:
                rows = all_rows[(method, condition)]
                ax.plot(_series(rows, "t"), _series(rows, key), label=method, color=colors[method])
            ax.set_title(f"{condition}: {filename.replace('_', ' ')}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(label)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}.png", dpi=150)
            plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        for method in METHODS:
            rows = all_rows[(method, condition)]
            t = _series(rows, "t")
            axes[0].plot(t, _series(rows, "F_tan"), label=method, color=colors[method])
            axes[1].plot(t, _series(rows, "F_rad"), label=method, color=colors[method])
        axes[0].set_ylabel("F_tan")
        axes[1].set_ylabel("F_rad")
        axes[1].set_xlabel("time [s]")
        for ax in axes:
            ax.grid(True, alpha=0.25)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"{condition}: action trajectories")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
        fig.savefig(fig_dir / f"{condition}_action_trajectories.png", dpi=150)
        plt.close(fig)

    x = np.arange(len(METHODS))
    width = 0.24
    offsets = np.linspace(-width, width, len(CONDITIONS))
    for label, p95_metric, max_metric, filename in [
        ("alpha", "alpha_p95_severity", "alpha_max_severity", "alpha_p95_max_by_method_condition.png"),
        ("omega", "omega_p95_severity", "omega_max_severity", "omega_p95_max_by_method_condition.png"),
    ]:
        fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
        for offset, condition in zip(offsets, CONDITIONS):
            axes[0].bar(
                x + offset,
                [float(_row(summary_rows, method, condition)[p95_metric]) for method in METHODS],
                width=width,
                label=condition,
            )
            axes[1].bar(
                x + offset,
                [float(_row(summary_rows, method, condition)[max_metric]) for method in METHODS],
                width=width,
                label=condition,
            )
        axes[0].set_ylabel(f"{label} p95 severity")
        axes[1].set_ylabel(f"{label} max severity")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(METHODS, rotation=25, ha="right")
        for ax in axes:
            ax.grid(True, axis="y", alpha=0.25)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"Stage 8B: {label} p95/max severity")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
        fig.savefig(fig_dir / filename, dpi=150)
        plt.close(fig)

    aggregate = _aggregate(summary_rows)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].bar(x, [float(row["action_smoothness_avg"]) for row in aggregate])
    axes[1].bar(x, [float(row["action_mag_avg"]) for row in aggregate])
    axes[0].set_ylabel("mean |du|")
    axes[1].set_ylabel("mean |u|")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(METHODS, rotation=25, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage 8B: action smoothness and magnitude comparison")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "action_smoothness_comparison.png", dpi=150)
    plt.close(fig)


def _method_delta(aggregate: dict[str, dict[str, Any]], method: str, metric: str) -> float:
    return float(aggregate[method][metric]) - float(aggregate["baseline_mainline"][metric])


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate_rows = _aggregate(summary_rows)
    aggregate = {row["method"]: row for row in aggregate_rows}
    baseline = aggregate["baseline_mainline"]
    candidates = [row for row in aggregate_rows if row["method"] != "baseline_mainline"]
    low_alpha_success = [
        row
        for row in candidates
        if int(row["target_success_count"]) == len(CONDITIONS)
        and float(row["alpha_p95_avg"]) < float(baseline["alpha_p95_avg"])
        and float(row["alpha_max_avg"]) < float(baseline["alpha_max_avg"])
    ]
    best_tail = min(
        aggregate_rows,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            float(row["alpha_p95_avg"]),
            float(row["alpha_max_avg"]),
            float(row["omega_p95_avg"]),
        ),
    )
    oracle_improves = (
        aggregate["oracle_cem"]["alpha_p95_avg"] < baseline["alpha_p95_avg"]
        and aggregate["oracle_cem"]["alpha_max_avg"] < baseline["alpha_max_avg"]
    )
    high_budget_improves = (
        aggregate["high_budget_cem"]["alpha_p95_avg"] < baseline["alpha_p95_avg"]
        and aggregate["high_budget_cem"]["alpha_max_avg"] < baseline["alpha_max_avg"]
    )
    smooth_improves = (
        aggregate["smooth_action_cem_diagnostic"]["alpha_p95_avg"] < baseline["alpha_p95_avg"]
        and aggregate["smooth_action_cem_diagnostic"]["alpha_max_avg"] < baseline["alpha_max_avg"]
    )
    if smooth_improves:
        cause = "action-sequence roughness appears to be a material contributor."
        next_step = "smooth / acceleration-aware CEM action generation."
    elif oracle_improves:
        cause = "estimator/identifier error appears to be a material contributor."
        next_step = "robust estimator/identifier validation before controller changes."
    elif high_budget_improves:
        cause = "CEM search budget appears to be a material contributor."
        next_step = "budget-aware or smoother CEM diagnostics, not linked rods yet."
    else:
        cause = "the evidence points more toward task/constraint conflict or the current action-generation formulation than estimator error alone."
        next_step = "task/constraint revision or a different action-generation formulation."
    linked_rods_safe = bool(low_alpha_success)
    lines = [
        "# Stage 8B Single-Link Oracle Diagnosis Report",
        "",
        "## Scope",
        "- Diagnosis only: checked whether low-alpha target-reaching trajectories exist in the current Spring2D single-link task.",
        "- Compared baseline mainline, oracle CEM, high-budget CEM, and a single smooth-action CEM diagnostic.",
        "- Conditions: clean, noise, noise_bias. Optional model_mismatch_light was not run to keep this diagnostic minimal.",
        "- Dynamics, estimator implementation, identifier implementation, existing baseline behavior, and Stage 7 methods were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Diagnostic Overrides",
        "- `oracle_cem`: true state for MPC state input; true physical parameters used as MPC prediction parameters; identifier frozen; default CEM budget.",
        "- `high_budget_cem`: samples=256, elites=32, iterations=5, horizon=24.",
        "- `smooth_action_cem_diagnostic`: default budget with action-rate cost weights `w_F_tan_rate=0.05`, `w_F_rad_rate=1.0`; all default/off methods keep action-rate weights at 0.",
        "",
        "## Aggregate Metrics",
        "| method | target successes | alpha mean | alpha p95 | alpha p99 | alpha max | omega p95 | omega max | action smoothness | T_reach avg | runtime avg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_p99_avg'])} | "
            f"{_fmt(row['alpha_max_avg'])} | {_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{_fmt(row['action_smoothness_avg'])} | {_fmt(row['T_reach_avg'])} | {_fmt(row['runtime_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Delta vs Baseline",
            "| method | delta alpha p95 | delta alpha max | delta omega p95 | delta action smoothness |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for method in METHODS:
        lines.append(
            f"| {method} | {_fmt(_method_delta(aggregate, method, 'alpha_p95_avg'))} | "
            f"{_fmt(_method_delta(aggregate, method, 'alpha_max_avg'))} | "
            f"{_fmt(_method_delta(aggregate, method, 'omega_p95_avg'))} | "
            f"{_fmt(_method_delta(aggregate, method, 'action_smoothness_avg'))} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does oracle CEM reduce alpha tail vs mainline baseline?",
            f"- {'Yes' if oracle_improves else 'No/mixed'}: oracle delta alpha p95/max = {_fmt(_method_delta(aggregate, 'oracle_cem', 'alpha_p95_avg'))}/{_fmt(_method_delta(aggregate, 'oracle_cem', 'alpha_max_avg'))}.",
            "",
            "2. Does high-budget CEM reduce alpha tail?",
            f"- {'Yes' if high_budget_improves else 'No/mixed'}: high-budget delta alpha p95/max = {_fmt(_method_delta(aggregate, 'high_budget_cem', 'alpha_p95_avg'))}/{_fmt(_method_delta(aggregate, 'high_budget_cem', 'alpha_max_avg'))}.",
            "",
            "3. Does smooth-action CEM reduce alpha tail?",
            f"- {'Yes' if smooth_improves else 'No/mixed'}: smooth-action delta alpha p95/max = {_fmt(_method_delta(aggregate, 'smooth_action_cem_diagnostic', 'alpha_p95_avg'))}/{_fmt(_method_delta(aggregate, 'smooth_action_cem_diagnostic', 'alpha_max_avg'))}.",
            "",
            "4. Does any diagnostic method preserve target reaching while reducing alpha p95/max?",
            "- "
            + (
                ", ".join(row["method"] for row in low_alpha_success)
                if low_alpha_success
                else "No method satisfied both full target reaching and lower alpha p95/max than baseline across the three conditions."
            ),
            "",
            "5. Is alpha tail mainly due to estimator/identifier error, CEM search budget, action-sequence roughness, or task/constraint conflict?",
            f"- {cause}",
            "",
            "6. Should next step be smooth/acceleration-aware CEM, robust identifier, or task/constraint revision?",
            f"- Recommended next step from this diagnostic: {next_step}",
            "",
            "7. Is it safe to move to linked rods now?",
            f"- {'Not yet with confidence' if not linked_rods_safe else 'Only cautiously, because one diagnostic found a lower-alpha target-reaching single-link case'}; this diagnosis is simulation evidence, not a formal safety guarantee. Best aggregate method was `{best_tail['method']}`.",
            "",
            "## Notes",
            "- Bad or mixed results are retained in the summary CSV and are not manually tuned after the run.",
        ]
    )
    (output_root / "stage8b_report.md").write_text("\n".join(lines) + "\n")


def run(output_root: Path, config_path: Path) -> None:
    base_cfg = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    commands = [f"python {Path(__file__).as_posix()} --config {config_path} --output-root {output_root}"]
    specs = _method_specs()

    for spec in specs:
        method = str(spec["method"])
        for condition in CONDITIONS:
            cfg = configure_run(base_cfg, spec)
            print(f"[stage8b] running {method} / {condition}", flush=True)
            start = time.perf_counter()
            rows = run_condition(condition, base_cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            summary = summarize_rows(spec, condition, rows, cfg, runtime_s)
            summary_rows.append(summary)
            print(
                "[stage8b] "
                f"{method}/{condition}: target={summary['target_reached']}, "
                f"alpha_p95={summary['alpha_p95_severity']:.4g}, "
                f"alpha_max={summary['alpha_max_severity']:.4g}, "
                f"runtime={runtime_s:.2f}s",
                flush=True,
            )

    save_summary(summary_rows, output_root / "stage8b_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands)
    print(f"[stage8b] summary: {output_root / 'stage8b_summary.csv'}", flush=True)
    print(f"[stage8b] report : {output_root / 'stage8b_report.md'}", flush=True)
    print(f"[stage8b] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
