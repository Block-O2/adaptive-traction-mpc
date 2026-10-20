"""Stage 8D low-frequency and delta-knot CEM action generation diagnosis."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage8d_low_freq_cem"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "baseline_standard",
    "alpha100_omega0",
    "alpha200_omega0",
    "u_knots_4",
    "u_knots_6",
    "du_knots_4",
    "du_knots_6",
    "move_blocking_2",
    "move_blocking_3",
    "lowpass_perturb",
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


def _clipped_max_excluding_one(values: np.ndarray) -> float:
    values = np.sort(_finite(values))
    if len(values) == 0:
        return np.nan
    if len(values) == 1:
        return 0.0
    return float(values[-2])


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return np.nan


def _method_specs() -> list[dict[str, Any]]:
    base = {
        "solver_safety_mode": "off",
        "alpha_soft_weight": 1.0,
        "omega_soft_weight": 0.0,
        "num_action_knots": 0,
        "move_block_size": 1,
        "lowpass_beta": 0.5,
    }
    return [
        {
            **base,
            "method": "baseline_standard",
            "family": "standard",
            "action_parameterization_mode": "standard",
            "notes": "current standard full-horizon CEM action sequence",
        },
        {
            **base,
            "method": "alpha100_omega0",
            "family": "alpha_soft_reference",
            "action_parameterization_mode": "standard",
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 100.0,
            "notes": "Stage 7A alpha100_omega0 reference with standard action parameterization",
        },
        {
            **base,
            "method": "alpha200_omega0",
            "family": "alpha_soft_reference",
            "action_parameterization_mode": "standard",
            "solver_safety_mode": "soft_penalty",
            "alpha_soft_weight": 200.0,
            "notes": "Stage 7A alpha200_omega0 reference with standard action parameterization",
        },
        {
            **base,
            "method": "u_knots_4",
            "family": "u_knots",
            "action_parameterization_mode": "u_knots",
            "num_action_knots": 4,
            "notes": "sample 4 action knots and interpolate over horizon",
        },
        {
            **base,
            "method": "u_knots_6",
            "family": "u_knots",
            "action_parameterization_mode": "u_knots",
            "num_action_knots": 6,
            "notes": "sample 6 action knots and interpolate over horizon",
        },
        {
            **base,
            "method": "du_knots_4",
            "family": "du_knots",
            "action_parameterization_mode": "du_knots",
            "num_action_knots": 4,
            "notes": "sample 4 delta-action knots, interpolate deltas, integrate and clip actions",
        },
        {
            **base,
            "method": "du_knots_6",
            "family": "du_knots",
            "action_parameterization_mode": "du_knots",
            "num_action_knots": 6,
            "notes": "sample 6 delta-action knots, interpolate deltas, integrate and clip actions",
        },
        {
            **base,
            "method": "move_blocking_2",
            "family": "move_blocking",
            "action_parameterization_mode": "move_blocking",
            "move_block_size": 2,
            "notes": "share one action over blocks of 2 horizon steps",
        },
        {
            **base,
            "method": "move_blocking_3",
            "family": "move_blocking",
            "action_parameterization_mode": "move_blocking",
            "move_block_size": 3,
            "notes": "share one action over blocks of 3 horizon steps",
        },
        {
            **base,
            "method": "lowpass_perturb",
            "family": "lowpass_perturb",
            "action_parameterization_mode": "lowpass_perturb",
            "lowpass_beta": 0.65,
            "notes": "low-pass filter CEM perturbations before rollout",
        },
    ]


def configure_run(base_cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
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
    solver["action_parameterization_mode"] = str(spec["action_parameterization_mode"])
    solver["num_action_knots"] = int(spec["num_action_knots"])
    solver["move_block_size"] = int(spec["move_block_size"])
    solver["lowpass_beta"] = float(spec["lowpass_beta"])
    violation_weights = dict(solver.get("safety_violation_weights", {}))
    violation_weights.update({"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 0.0, "alpha": 1.0})
    solver["safety_violation_weights"] = violation_weights
    weights = cfg["mpc_params"].setdefault("weights", {})
    weights["w_action_rate"] = 0.0
    weights["w_F_tan_rate"] = 0.0
    weights["w_F_rad_rate"] = 0.0
    cfg["stage8d_method_spec"] = dict(spec)
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
    dt = float(true_params["dt"])
    alpha_max = float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf)))
    omega_max = float(constraints.get("omega_max", true_params["omega_max"]))
    delta_r_max = float(constraints.get("delta_r_max", true_params["delta_r_max"]))
    F_tan_max = float(constraints.get("F_tan_max", true_params["F_tan_max"]))
    F_rad_max = float(constraints.get("F_rad_max", true_params["F_rad_max"]))
    t = _series(rows, "t")
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    omega_sev = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    early_mask = t <= 0.5
    late_mask = t > 0.5
    actions = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(actions, axis=1)
    action_diff = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.array([])
    solver = cfg["mpc_params"].get("solver", {})
    return {
        "method": str(spec["method"]),
        "family": str(spec["family"]),
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_percentile(alpha_sev, 95),
        "alpha_p99_severity": _finite_percentile(alpha_sev, 99),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_clipped_max_excluding_top1": _clipped_max_excluding_one(alpha_sev),
        "alpha_violation_duration_s": float(np.count_nonzero(alpha_sev > 0.0) * dt),
        "alpha_integrated_violation": float(np.sum(alpha_sev) * dt),
        "early_alpha_mean_severity": _finite_mean(alpha_sev[early_mask]),
        "early_alpha_p95_severity": _finite_percentile(alpha_sev[early_mask], 95),
        "early_alpha_p99_severity": _finite_percentile(alpha_sev[early_mask], 99),
        "early_alpha_max_severity": _finite_max(alpha_sev[early_mask]),
        "late_alpha_mean_severity": _finite_mean(alpha_sev[late_mask]),
        "late_alpha_p95_severity": _finite_percentile(alpha_sev[late_mask], 95),
        "late_alpha_p99_severity": _finite_percentile(alpha_sev[late_mask], 99),
        "late_alpha_max_severity": _finite_max(alpha_sev[late_mask]),
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
        "action_smoothness": _finite_mean(action_diff),
        "action_total_variation": float(np.sum(_finite(action_diff))) if len(_finite(action_diff)) else 0.0,
        "cem_runtime_s": float(runtime_s),
        "action_parameterization_mode": str(solver.get("action_parameterization_mode", "standard")),
        "num_action_knots": int(solver.get("num_action_knots", 0)),
        "move_block_size": int(solver.get("move_block_size", 1)),
        "lowpass_beta": float(solver.get("lowpass_beta", np.nan)),
        "solver_safety_mode": str(solver.get("safety_mode", "off")),
        "alpha_soft_weight": float(solver.get("alpha_soft_weight", np.nan)),
        "notes": str(spec["notes"]),
    }


SUMMARY_FIELDS = [
    "method",
    "family",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
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
    "late_alpha_mean_severity",
    "late_alpha_p95_severity",
    "late_alpha_p99_severity",
    "late_alpha_max_severity",
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
    "action_total_variation",
    "cem_runtime_s",
    "action_parameterization_mode",
    "num_action_knots",
    "move_block_size",
    "lowpass_beta",
    "solver_safety_mode",
    "alpha_soft_weight",
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
                "family": method_rows[0]["family"],
                "target_success_count": int(sum(bool(row["target_reached"]) for row in method_rows)),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "alpha_mean_avg": _finite_mean(np.array([float(row["alpha_mean_severity"]) for row in method_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_p99_avg": _finite_mean(np.array([float(row["alpha_p99_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "alpha_clipped_max_avg": _finite_mean(
                    np.array([float(row["alpha_clipped_max_excluding_top1"]) for row in method_rows])
                ),
                "alpha_duration_avg": _finite_mean(np.array([float(row["alpha_violation_duration_s"]) for row in method_rows])),
                "alpha_integral_avg": _finite_mean(np.array([float(row["alpha_integrated_violation"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "action_total_variation_avg": _finite_mean(
                    np.array([float(row["action_total_variation"]) for row in method_rows])
                ),
                "runtime_avg": _finite_mean(np.array([float(row["cem_runtime_s"]) for row in method_rows])),
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
    cmap = plt.get_cmap("tab10")
    colors = {method: cmap(idx % 10) for idx, method in enumerate(METHODS)}
    for condition in CONDITIONS:
        fig, ax = plt.subplots(figsize=(13, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), np.degrees(_series(rows, "theta")), label=method, color=colors[method])
        target = np.degrees(float(all_rows[("baseline_standard", condition)][-1]["theta_target_final"]))
        ax.axhline(target, color="black", linestyle=":", label="theta_target")
        ax.set_title(f"{condition}: theta trajectories")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("theta [deg]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_theta_trajectories.png", dpi=150)
        plt.close(fig)

        alpha_limit = 3.0
        fig, ax = plt.subplots(figsize=(13, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), _series(rows, "alpha_step"), label=method, color=colors[method])
        ax.axhline(alpha_limit, color="black", linestyle=":", label="alpha threshold")
        ax.axhline(-alpha_limit, color="black", linestyle=":")
        ax.set_title(f"{condition}: alpha trajectories with threshold")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("alpha [rad/s^2]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_alpha_trajectories.png", dpi=150)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(13, 5))
        for method in METHODS:
            rows = all_rows[(method, condition)]
            ax.plot(_series(rows, "t"), _series(rows, "omega"), label=method, color=colors[method])
        ax.set_title(f"{condition}: omega trajectories")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("omega [rad/s]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{condition}_omega_trajectories.png", dpi=150)
        plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
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
        axes[0].legend(fontsize=7, ncol=2)
        fig.suptitle(f"{condition}: action trajectories")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
        fig.savefig(fig_dir / f"{condition}_action_trajectories.png", dpi=150)
        plt.close(fig)

    aggregate = _aggregate(summary_rows)
    x = np.arange(len(METHODS))
    width = 0.16
    metric_specs = [
        ("alpha_p95_avg", "p95"),
        ("alpha_p99_avg", "p99"),
        ("alpha_max_avg", "max"),
        ("alpha_duration_avg", "duration"),
        ("alpha_integral_avg", "integral"),
    ]
    fig, ax = plt.subplots(figsize=(14, 6))
    for idx, (metric, label) in enumerate(metric_specs):
        ax.bar(x + (idx - 2) * width, [float(row[metric]) for row in aggregate], width=width, label=label)
    ax.set_ylabel("alpha severity / duration / integral")
    ax.set_xticks(x)
    ax.set_xticklabels(METHODS, rotation=30, ha="right")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.suptitle("Stage 8D: alpha metric comparison")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "alpha_metrics_bar.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].bar(x, [float(row["action_smoothness_avg"]) for row in aggregate])
    axes[1].bar(x, [float(row["action_total_variation_avg"]) for row in aggregate])
    axes[0].set_ylabel("mean |du|")
    axes[1].set_ylabel("total variation")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(METHODS, rotation=30, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Stage 8D: action smoothness comparison")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    fig.savefig(fig_dir / "action_smoothness_comparison.png", dpi=150)
    plt.close(fig)


def _strict_alpha_improves(candidate: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return (
        int(candidate["target_success_count"]) == 3
        and float(candidate["alpha_p95_avg"]) < float(baseline["alpha_p95_avg"])
        and float(candidate["alpha_p99_avg"]) < float(baseline["alpha_p99_avg"])
        and float(candidate["alpha_max_avg"]) < float(baseline["alpha_max_avg"])
        and float(candidate["alpha_duration_avg"]) <= float(baseline["alpha_duration_avg"])
        and float(candidate["alpha_integral_avg"]) <= float(baseline["alpha_integral_avg"])
    )


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate_rows = _aggregate(summary_rows)
    by_method = {row["method"]: row for row in aggregate_rows}
    baseline = by_method["baseline_standard"]
    alpha_refs = [by_method["alpha100_omega0"], by_method["alpha200_omega0"]]
    low_freq_rows = [row for row in aggregate_rows if row["family"] not in {"standard", "alpha_soft_reference"}]
    best_low_freq = min(
        low_freq_rows,
        key=lambda row: (
            3 - int(row["target_success_count"]),
            float(row["alpha_p95_avg"]),
            float(row["alpha_p99_avg"]),
            float(row["alpha_max_avg"]),
            float(row["omega_p95_avg"]),
        ),
    )
    strict_improvements = [row for row in low_freq_rows if _strict_alpha_improves(row, baseline)]
    omega_ok = float(best_low_freq["omega_p95_avg"]) <= float(baseline["omega_p95_avg"]) and float(
        best_low_freq["omega_max_avg"]
    ) <= float(baseline["omega_max_avg"])
    best_alpha_ref = min(alpha_refs, key=lambda row: (float(row["alpha_p95_avg"]), float(row["alpha_max_avg"])))
    beats_alpha_soft = (
        float(best_low_freq["alpha_p95_avg"]) < float(best_alpha_ref["alpha_p95_avg"])
        and float(best_low_freq["alpha_max_avg"]) < float(best_alpha_ref["alpha_max_avg"])
        and int(best_low_freq["target_success_count"]) >= int(best_alpha_ref["target_success_count"])
    )
    continue_stress = bool(strict_improvements) and omega_ok
    if continue_stress:
        next_step = "stress validation for the best low-frequency CEM mode."
    elif any(int(row["target_success_count"]) == 3 for row in low_freq_rows):
        next_step = "task/constraint revision before stress validation; low-frequency parameterization alone is not decisive."
    else:
        next_step = "SQP/RTI NMPC or task/constraint revision; low-frequency CEM did not preserve task completion."
    lines = [
        "# Stage 8D Low-Frequency / Delta-Knot CEM Report",
        "",
        "## Scope",
        "- Diagnosis only: tested whether alpha tail comes from high-frequency or rough CEM action sequences.",
        "- Mainline estimator/identifier remains UKF-bias + filtered Windowed NLS.",
        "- No governor, no gatekeeper, no action projection, and no alpha-soft penalty for low-frequency modes.",
        "- Alpha100/alpha200 are reference runs using existing alpha-soft settings.",
        "- Dynamics, UKF settings, identifier, baseline CEM standard mode, Stage 7 methods, and default configs were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | family | target | T_reach | alpha mean | alpha p95 | alpha p99 | alpha max | clipped max | duration | integral | omega p95 | omega max | action smoothness | runtime |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | {row['family']} | {row['target_success_count']}/3 | {_fmt(row['T_reach_avg'])} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_p99_avg'])} | "
            f"{_fmt(row['alpha_max_avg'])} | {_fmt(row['alpha_clipped_max_avg'])} | {_fmt(row['alpha_duration_avg'])} | "
            f"{_fmt(row['alpha_integral_avg'])} | {_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{_fmt(row['action_smoothness_avg'])} | {_fmt(row['runtime_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does low-frequency action parameterization preserve target reaching?",
            "- "
            + (
                ", ".join(row["method"] for row in low_freq_rows if int(row["target_success_count"]) == 3)
                if any(int(row["target_success_count"]) == 3 for row in low_freq_rows)
                else "No low-frequency mode reached the target in all three conditions."
            ),
            "",
            "2. Does it reduce alpha p95/p99/max/duration/integral vs baseline?",
            "- "
            + (
                ", ".join(row["method"] for row in strict_improvements)
                if strict_improvements
                else "No low-frequency mode improved all requested alpha metrics while preserving 3/3 target reaching."
            ),
            "",
            "3. Does it avoid worsening omega tail risk?",
            f"- {'Yes' if omega_ok else 'No/mixed'} for the best low-frequency mode `{best_low_freq['method']}`: omega p95/max={_fmt(best_low_freq['omega_p95_avg'])}/{_fmt(best_low_freq['omega_max_avg'])} vs baseline={_fmt(baseline['omega_p95_avg'])}/{_fmt(baseline['omega_max_avg'])}.",
            "",
            "4. Which mode is best: u_knots, du_knots, move_blocking, or lowpass perturbation?",
            f"- Best aggregate low-frequency mode by target success, alpha p95/p99/max, and omega p95 is `{best_low_freq['method']}` ({best_low_freq['family']}).",
            "",
            "5. Does this outperform alpha100/alpha200?",
            f"- {'Yes' if beats_alpha_soft else 'No/mixed'}: best low-frequency `{best_low_freq['method']}` alpha p95/max={_fmt(best_low_freq['alpha_p95_avg'])}/{_fmt(best_low_freq['alpha_max_avg'])}; best alpha-soft reference `{best_alpha_ref['method']}` alpha p95/max={_fmt(best_alpha_ref['alpha_p95_avg'])}/{_fmt(best_alpha_ref['alpha_max_avg'])}.",
            "",
            "6. Is the next step stress validation, SQP/RTI NMPC, or task/constraint revision?",
            f"- Recommended next step: {next_step}",
            "",
            "## Notes",
            "- Bad or mixed results are reported directly. No post-result tuning was applied.",
        ]
    )
    (output_root / "stage8d_report.md").write_text("\n".join(lines) + "\n")


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
            print(f"[stage8d] running {method} / {condition}", flush=True)
            start = time.perf_counter()
            rows = run_condition(condition, base_cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            summary = summarize_rows(spec, condition, rows, cfg, runtime_s)
            summary_rows.append(summary)
            print(
                "[stage8d] "
                f"{method}/{condition}: target={summary['target_reached']}, "
                f"T={summary['T_reach']:.4g}, "
                f"alpha_p95={summary['alpha_p95_severity']:.4g}, "
                f"alpha_max={summary['alpha_max_severity']:.4g}, "
                f"omega_p95={summary['omega_p95_severity']:.4g}, "
                f"smooth={summary['action_smoothness']:.4g}, "
                f"runtime={runtime_s:.2f}s",
                flush=True,
            )
    save_summary(summary_rows, output_root / "stage8d_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands)
    print(f"[stage8d] summary: {output_root / 'stage8d_summary.csv'}", flush=True)
    print(f"[stage8d] report : {output_root / 'stage8d_report.md'}", flush=True)
    print(f"[stage8d] figs   : {output_root / 'figs'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.output_root, args.config)


if __name__ == "__main__":
    main()
