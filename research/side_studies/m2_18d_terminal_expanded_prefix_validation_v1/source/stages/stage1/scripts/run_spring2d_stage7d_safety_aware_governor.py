"""Stage 7D safety-aware command governor comparison for Spring2D CEM-MPC."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7d_safety_aware_governor"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "baseline_cem",
    "alpha100_omega0",
    "alpha200_omega0",
    "fixed_rate_30",
    "gatekeeper_H3",
    "safety_aware_governor",
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


def _control_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        solve_count = int(float(row.get("mpc_solve_count", 0)))
        if solve_count <= 0 or solve_count in seen:
            continue
        seen.add(solve_count)
        result.append(row)
    return result


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
        "progress_governor": {"mode": "off"},
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
        "fixed_rate_30": {
            **base,
            "progress_governor": {"mode": "fixed_rate", "rate_deg_s": 30.0},
        },
        "gatekeeper_H3": {
            **base,
            "gatekeeper_mode": "candidate_select",
            "gatekeeper_horizon": 3,
        },
        "safety_aware_governor": {
            **base,
            "progress_governor": {
                "mode": "safety_aware",
                "candidate_rates_deg_s": [0.0, 10.0, 20.0, 30.0, 45.0],
                "horizon": 3,
                "safety_score_threshold": 0.0,
                "weights": {
                    "alpha_max": 10.0,
                    "alpha_sum": 5.0,
                    "omega_max": 5.0,
                    "omega_sum": 1.0,
                    "delta_r": 5.0,
                    "force": 5.0,
                },
            },
        },
    }


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = copy.deepcopy(method_cfg["progress_governor"])
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver["alpha_constraint_mode"] = method_cfg["alpha_constraint_mode"]
    solver["alpha_soft_weight"] = float(method_cfg["alpha_soft_weight"])
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["gatekeeper_mode"] = method_cfg["gatekeeper_mode"]
    solver["gatekeeper_horizon"] = int(method_cfg["gatekeeper_horizon"])
    solver["gatekeeper_top_k"] = int(method_cfg["gatekeeper_top_k"])
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
    control_rows = _control_rows(rows)
    hold_count = int(sum(bool(row.get("progress_governor_hold", False)) for row in control_rows))
    governor = method_cfg["progress_governor"]
    return {
        "method": method,
        "condition": condition,
        "progress_governor_mode": str(governor.get("mode", "off")),
        "gatekeeper_mode": str(method_cfg["gatekeeper_mode"]),
        "solver_safety_mode": str(final.get("cem_safety_mode", method_cfg["solver_safety_mode"])),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", method_cfg["alpha_constraint_mode"])),
        "alpha_soft_weight": float(method_cfg["alpha_soft_weight"]),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "theta_cmd_final_deg": float(np.degrees(float(final.get("theta_cmd", np.nan)))),
        "selected_command_rate_mean": _finite_mean(_series(control_rows, "progress_governor_selected_rate_deg_s")),
        "selected_command_rate_max": _finite_max(_series(control_rows, "progress_governor_selected_rate_deg_s")),
        "hold_count": hold_count,
        "decision_count": int(len(control_rows)),
        "hold_rate": float(hold_count / len(control_rows)) if control_rows else np.nan,
        "governor_safety_score_mean": _finite_mean(_series(control_rows, "progress_governor_safety_score")),
        "governor_pred_alpha_max_mean": _finite_mean(_series(control_rows, "progress_governor_pred_alpha_max")),
        "governor_pred_alpha_sum_mean": _finite_mean(_series(control_rows, "progress_governor_pred_alpha_sum")),
        "governor_pred_omega_max_mean": _finite_mean(_series(control_rows, "progress_governor_pred_omega_max")),
        "governor_pred_omega_sum_mean": _finite_mean(_series(control_rows, "progress_governor_pred_omega_sum")),
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
    "progress_governor_mode",
    "gatekeeper_mode",
    "solver_safety_mode",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "theta_cmd_final_deg",
    "selected_command_rate_mean",
    "selected_command_rate_max",
    "hold_count",
    "decision_count",
    "hold_rate",
    "governor_safety_score_mean",
    "governor_pred_alpha_max_mean",
    "governor_pred_alpha_sum_mean",
    "governor_pred_omega_max_mean",
    "governor_pred_omega_sum_mean",
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
                "hold_rate_avg": _finite_mean(np.array([float(row["hold_rate"]) for row in method_rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
            }
        )
    return rows


def save_plots(all_rows: dict[tuple[str, str], list[dict[str, Any]]], summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for condition in CONDITIONS:
        for key, ylabel, filename, transform in [
            ("theta", "theta [deg]", "theta_theta_cmd_target.png", np.degrees),
            ("progress_governor_selected_rate_deg_s", "selected command rate [deg/s]", "selected_command_rate.png", None),
            ("alpha_step", "alpha", "alpha_trajectory.png", None),
            ("omega", "omega", "omega_trajectory.png", None),
        ]:
            fig, ax = plt.subplots(figsize=(12, 4.8))
            for method in METHODS:
                rows = all_rows[(method, condition)]
                values = _series(rows, key)
                if transform is not None:
                    values = transform(values)
                ax.plot(_series(rows, "t"), values, label=method)
                if key == "theta" and method in {"fixed_rate_30", "safety_aware_governor"}:
                    ax.plot(
                        _series(rows, "t"),
                        np.degrees(_series(rows, "theta_cmd")),
                        linestyle="--",
                        linewidth=1.1,
                        label=f"{method} theta_cmd",
                    )
            if key == "theta":
                target = float(np.degrees(float(all_rows[(METHODS[0], condition)][-1].get("theta_target_final", np.nan))))
                if np.isfinite(target):
                    ax.axhline(target, color="black", linestyle=":", linewidth=1.2, label="theta_target")
            ax.set_title(f"{condition}: {ylabel}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=7, ncol=3)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}", dpi=150)
            plt.close(fig)

    x = np.arange(len(CONDITIONS))
    width = 0.12
    offsets = np.linspace(-2.5 * width, 2.5 * width, len(METHODS))
    for label, p95_metric, max_metric in [
        ("alpha", "alpha_p95_severity", "alpha_max_severity"),
        ("omega", "omega_p95_severity", "omega_max_severity"),
    ]:
        fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
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
        fig.suptitle(f"Stage 7D: {label} p95/max severity")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        fig.savefig(fig_dir / f"{label}_p95_max_bar.png", dpi=150)
        plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for method in METHODS:
        successes = [1.0 if bool(_row(summary_rows, method, condition)["target_reached"]) else 0.0 for condition in CONDITIONS]
        t_reach = [float(_row(summary_rows, method, condition)["T_reach"]) for condition in CONDITIONS]
        axes[0].plot(CONDITIONS, successes, marker="o", label=method)
        axes[1].plot(CONDITIONS, t_reach, marker="o", label=method)
    axes[0].set_ylabel("target success")
    axes[1].set_ylabel("T_reach [s]")
    axes[1].set_xlabel("condition")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=7, ncol=3)
    fig.suptitle("Stage 7D: target success and T_reach")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    fig.savefig(fig_dir / "target_success_T_reach.png", dpi=150)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = _aggregate(summary_rows)
    by_method = {row["method"]: row for row in aggregate}
    gov = by_method["safety_aware_governor"]
    baseline = by_method["baseline_cem"]
    alpha100 = by_method["alpha100_omega0"]
    alpha200 = by_method["alpha200_omega0"]
    fixed = by_method["fixed_rate_30"]
    gatekeeper = by_method["gatekeeper_H3"]
    alpha_soft_p95 = min(alpha100["alpha_p95_avg"], alpha200["alpha_p95_avg"])
    alpha_soft_max = min(alpha100["alpha_max_avg"], alpha200["alpha_max_avg"])
    preserves_target = gov["target_success_count"] == len(CONDITIONS)
    improves_alpha_all = (
        gov["alpha_p95_avg"] < baseline["alpha_p95_avg"]
        and gov["alpha_max_avg"] < baseline["alpha_max_avg"]
        and gov["alpha_p95_avg"] < alpha_soft_p95
        and gov["alpha_max_avg"] < alpha_soft_max
        and gov["alpha_p95_avg"] < fixed["alpha_p95_avg"]
        and gov["alpha_max_avg"] < fixed["alpha_max_avg"]
        and gov["alpha_p95_avg"] < gatekeeper["alpha_p95_avg"]
        and gov["alpha_max_avg"] < gatekeeper["alpha_max_avg"]
    )
    avoids_omega = gov["omega_p95_avg"] <= baseline["omega_p95_avg"] and gov["omega_max_avg"] <= baseline["omega_max_avg"]
    better_than_fixed = (
        gov["target_success_count"] >= fixed["target_success_count"]
        and gov["alpha_p95_avg"] < fixed["alpha_p95_avg"]
        and gov["alpha_max_avg"] < fixed["alpha_max_avg"]
    )
    continue_stress = preserves_target and improves_alpha_all and avoids_omega
    lines = [
        "# Stage 7D Safety-Aware Command Governor Report",
        "",
        "## Scope",
        "- Added `progress_governor_mode=safety_aware`.",
        "- The governor maintains `theta_cmd` and chooses among command rates `[0, 10, 20, 30, 45]` deg/s.",
        "- Safety-aware scoring uses a 3-step surrogate rollout and a fixed threshold; no retreat/backtracking, action projection, or extra rate tuning was added.",
        "- MPC tracks `theta_cmd` when the governor is enabled.",
        "- Dynamics, estimator/identifier flow, baseline CEM, runtime filter, alpha-soft CEM, and gatekeeper code were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | hold rate avg | T_reach avg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | "
            f"{_fmt(row['hold_rate_avg'])} | {_fmt(row['T_reach_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does safety-aware governor preserve target reaching?",
            f"- {'Yes' if preserves_target else 'No/mixed'}: safety-aware governor target={gov['target_success_count']}/{len(CONDITIONS)}.",
            "",
            "2. Does it reduce alpha p95/max vs baseline, alpha-soft, fixed-rate, and gatekeeper?",
            f"- {'Yes' if improves_alpha_all else 'No/mixed'}: safety-aware alpha p95/max avg={_fmt(gov['alpha_p95_avg'])}/{_fmt(gov['alpha_max_avg'])}; baseline={_fmt(baseline['alpha_p95_avg'])}/{_fmt(baseline['alpha_max_avg'])}; alpha-soft best={_fmt(alpha_soft_p95)}/{_fmt(alpha_soft_max)}; fixed_rate_30={_fmt(fixed['alpha_p95_avg'])}/{_fmt(fixed['alpha_max_avg'])}; gatekeeper_H3={_fmt(gatekeeper['alpha_p95_avg'])}/{_fmt(gatekeeper['alpha_max_avg'])}.",
            "",
            "3. Does it avoid worsening omega tail risk?",
            f"- {'Yes' if avoids_omega else 'No/mixed'}: safety-aware omega p95/max avg={_fmt(gov['omega_p95_avg'])}/{_fmt(gov['omega_max_avg'])}; baseline={_fmt(baseline['omega_p95_avg'])}/{_fmt(baseline['omega_max_avg'])}.",
            "",
            "4. How often does it hold progress?",
            f"- Average hold rate={_fmt(gov['hold_rate_avg'])}.",
            "",
            "5. Is it better than fixed-rate governor?",
            f"- {'Yes' if better_than_fixed else 'No/mixed'} by target success plus alpha p95/max vs `fixed_rate_30`.",
            "",
            "6. Should this continue to stress validation or be closed out?",
            f"- {'Continue to stress validation' if continue_stress else 'Close out or revise before stress validation'} based on this minimal Stage 7D evidence.",
            "",
            "## Outputs",
            "- `stage7d_summary.csv` contains per-method/per-condition metrics.",
            "- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
        ]
    )
    (output_root / "stage7d_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _method_configs()
    commands = [
        "conda run -n mpc_learn python -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests",
        "conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7d_safety_aware_governor.py",
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
                row["stage7d_method"] = method
                row["stage7d_condition"] = condition
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

    save_summary(summary_rows, output_root / "stage7d_summary.csv")
    save_plots(all_rows, summary_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 7D safety-aware command governor")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7d_summary.csv'}")
    print(f"  report      : {output_root / 'stage7d_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_p95={row['alpha_p95_severity']:.4f}, "
            f"alpha_max={row['alpha_max_severity']:.4f}, "
            f"omega_p95={row['omega_p95_severity']:.4f}, "
            f"hold_rate={row['hold_rate']:.4f}, "
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
