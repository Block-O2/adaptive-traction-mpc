"""Minimal fixed-rate progress governor comparison for Spring2D CEM-MPC."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7b_progress_governor"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS = [
    "baseline_cem",
    "alpha100_omega0",
    "alpha200_omega0",
    "fixed_rate_15",
    "fixed_rate_30",
    "fixed_rate_45",
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


def _severity(rows: list[dict[str, Any]], key: str, limit: float) -> np.ndarray:
    return np.maximum(0.0, np.abs(_series(rows, key)) - limit)


def _method_configs() -> dict[str, dict[str, Any]]:
    return {
        "baseline_cem": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "off"},
        },
        "alpha100_omega0": {
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 100.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "off"},
        },
        "alpha200_omega0": {
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 200.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "off"},
        },
        "fixed_rate_15": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "fixed_rate", "rate_deg_s": 15.0},
        },
        "fixed_rate_30": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "fixed_rate", "rate_deg_s": 30.0},
        },
        "fixed_rate_45": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": 1.0,
            "omega_soft_weight": 0.0,
            "progress_governor": {"mode": "fixed_rate", "rate_deg_s": 45.0},
        },
    }


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = dict(method_cfg["progress_governor"])
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
    governor = method_cfg["progress_governor"]
    return {
        "method": method,
        "condition": condition,
        "progress_governor_mode": str(governor.get("mode", "off")),
        "progress_governor_rate_deg_s": float(governor.get("rate_deg_s", np.nan)),
        "solver_safety_mode": str(final.get("cem_safety_mode", method_cfg["solver_safety_mode"])),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", method_cfg["alpha_constraint_mode"])),
        "alpha_soft_weight": float(method_cfg["alpha_soft_weight"]),
        "omega_soft_weight": float(method_cfg["omega_soft_weight"]),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "theta_cmd_final_deg": float(np.degrees(float(final.get("theta_cmd", np.nan)))),
        "theta_target_final_deg": float(np.degrees(float(final.get("theta_target_final", cfg["mpc_params"].get("target_theta", cfg["true_params"]["theta_target"]))))),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_p95_severity": _finite_p95(alpha_sev),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_max_severity": _finite_max(omega_sev),
        "omega_p95_severity": _finite_p95(omega_sev),
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
    "progress_governor_rate_deg_s",
    "solver_safety_mode",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "omega_soft_weight",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "theta_cmd_final_deg",
    "theta_target_final_deg",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_max_severity",
    "alpha_p95_severity",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_max_severity",
    "omega_p95_severity",
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
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in method_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in method_rows])),
                "alpha_mean_avg": _finite_mean(np.array([float(row["alpha_mean_severity"]) for row in method_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in method_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in method_rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in method_rows])),
                "action_smoothness_avg": _finite_mean(np.array([float(row["action_smoothness"]) for row in method_rows])),
                "action_magnitude_avg": _finite_mean(np.array([float(row["mean_action_magnitude"]) for row in method_rows])),
            }
        )
    return rows


def _best_rate(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in aggregate_rows if row["method"].startswith("fixed_rate_")]
    return min(
        candidates,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            row["alpha_p95_avg"],
            row["alpha_max_avg"],
            row["omega_p95_avg"],
            row["T_reach_avg"],
        ),
    )


def save_trajectory_plots(all_rows: dict[tuple[str, str], list[dict[str, Any]]], output_root: Path) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for condition in CONDITIONS:
        target = None
        for key, ylabel, filename in [
            ("theta", "theta [deg]", "theta_theta_cmd_trajectory.png"),
            ("alpha_step", "alpha", "alpha_trajectory.png"),
            ("omega", "omega", "omega_trajectory.png"),
        ]:
            fig, ax = plt.subplots(figsize=(11, 5))
            for method in METHODS:
                rows = all_rows[(method, condition)]
                t = _series(rows, "t")
                values = _series(rows, key)
                if key == "theta":
                    values = np.degrees(values)
                    cmd = np.degrees(_series(rows, "theta_cmd"))
                    target = float(np.degrees(float(rows[-1].get("theta_target_final", np.nan))))
                    ax.plot(t, values, label=f"{method} theta")
                    if method.startswith("fixed_rate_"):
                        ax.plot(t, cmd, linestyle="--", linewidth=1.2, label=f"{method} theta_cmd")
                else:
                    ax.plot(t, values, label=method)
            if key == "theta" and target is not None and np.isfinite(target):
                ax.axhline(target, color="black", linestyle=":", linewidth=1.2, label="theta_target")
            ax.set_title(f"{condition}: {ylabel}")
            ax.set_xlabel("time [s]")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=7, ncol=2)
            fig.tight_layout()
            fig.savefig(fig_dir / f"{condition}_{filename}", dpi=150)
            plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
        for method in METHODS:
            rows = all_rows[(method, condition)]
            t = _series(rows, "t")
            axes[0].plot(t, _series(rows, "F_tan"), label=method)
            axes[1].plot(t, _series(rows, "F_rad"), label=method)
        axes[0].set_ylabel("F_tan")
        axes[1].set_ylabel("F_rad")
        axes[1].set_xlabel("time [s]")
        for ax in axes:
            ax.grid(True, alpha=0.25)
        axes[0].legend(fontsize=7, ncol=3)
        fig.suptitle(f"{condition}: action trajectory")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        fig.savefig(fig_dir / f"{condition}_action_trajectory.png", dpi=150)
        plt.close(fig)


def save_bar_plot(summary_rows: list[dict[str, Any]], output_root: Path) -> None:
    x = np.arange(len(CONDITIONS))
    width = 0.13
    offsets = np.linspace(-2.5 * width, 2.5 * width, len(METHODS))
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    for offset, method in zip(offsets, METHODS):
        alpha_values = [float(_row(summary_rows, method, condition)["alpha_p95_severity"]) for condition in CONDITIONS]
        omega_values = [float(_row(summary_rows, method, condition)["omega_p95_severity"]) for condition in CONDITIONS]
        axes[0].bar(x + offset, alpha_values, width=width, label=method)
        axes[1].bar(x + offset, omega_values, width=width, label=method)
    axes[0].set_ylabel("alpha p95 severity")
    axes[1].set_ylabel("omega p95 severity")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(CONDITIONS)
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].legend(fontsize=7, ncol=3)
    fig.suptitle("Stage 7B minimal: alpha/omega p95 severity")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    path = output_root / "figs" / "alpha_omega_p95_bar.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = _aggregate(summary_rows)
    aggregate_by_method = {row["method"]: row for row in aggregate}
    best_rate = _best_rate(aggregate)
    baseline = aggregate_by_method["baseline_cem"]
    alpha100 = aggregate_by_method["alpha100_omega0"]
    alpha200 = aggregate_by_method["alpha200_omega0"]
    rate_rows = [row for row in aggregate if row["method"].startswith("fixed_rate_")]
    preserves_target = all(row["target_success_count"] == len(CONDITIONS) for row in rate_rows)
    best_beats_baseline_alpha = (
        best_rate["alpha_p95_avg"] < baseline["alpha_p95_avg"]
        and best_rate["alpha_max_avg"] < baseline["alpha_max_avg"]
    )
    best_beats_alpha_soft = (
        best_rate["alpha_p95_avg"] < min(alpha100["alpha_p95_avg"], alpha200["alpha_p95_avg"])
        and best_rate["alpha_max_avg"] < min(alpha100["alpha_max_avg"], alpha200["alpha_max_avg"])
    )
    avoids_omega_worse = best_rate["omega_p95_avg"] <= baseline["omega_p95_avg"]
    continue_safety_aware = preserves_target and best_beats_baseline_alpha and avoids_omega_worse
    lines = [
        "# Stage 7B-minimal Fixed-Rate Progress Governor Report",
        "",
        "## Scope",
        "- Added optional `progress_governor_mode`: `off` and `fixed_rate`.",
        "- Fixed-rate governor updates `theta_cmd` toward the final target and MPC tracks `theta_cmd` when enabled.",
        "- Tested fixed rates 15, 30, and 45 deg/s only. No extra tuning was performed.",
        "- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier flow, baseline CEM with governor off, old runtime filter, and Stage 7A alpha-soft implementation were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| method | target successes | alpha mean avg | alpha p95 avg | alpha max avg | omega p95 avg | omega max avg | T_reach avg | action smooth avg |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            f"| {row['method']} | {row['target_success_count']}/{len(CONDITIONS)} | "
            f"{_fmt(row['alpha_mean_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | {_fmt(row['T_reach_avg'])} | "
            f"{_fmt(row['action_smoothness_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does fixed-rate progress governor preserve target reaching?",
            f"- {'Yes' if preserves_target else 'No/mixed'}: fixed-rate target successes are "
            + ", ".join(f"{row['method']}={row['target_success_count']}/{len(CONDITIONS)}" for row in rate_rows)
            + ".",
            "",
            "2. Does it reduce alpha p95/max compared with baseline and alpha-soft CEM?",
            f"- Best fixed-rate method is `{best_rate['method']}` with alpha p95 avg={_fmt(best_rate['alpha_p95_avg'])} and alpha max avg={_fmt(best_rate['alpha_max_avg'])}.",
            f"- Compared with baseline: {'improved both p95 and max' if best_beats_baseline_alpha else 'did not improve both p95 and max'}.",
            f"- Compared with alpha-soft candidates: {'improved both p95 and max' if best_beats_alpha_soft else 'did not improve both p95 and max'}.",
            "",
            "3. Does it avoid worsening omega tail risk?",
            f"- {'Yes' if avoids_omega_worse else 'No/mixed'} for the best fixed-rate method using omega p95 avg vs baseline: best={_fmt(best_rate['omega_p95_avg'])}, baseline={_fmt(baseline['omega_p95_avg'])}.",
            "",
            "4. Which rate is best?",
            f"- `{best_rate['method']}` by target success first, then alpha p95, alpha max, omega p95, and T_reach.",
            "",
            "5. Should we continue to safety-aware governor next?",
            f"- {'Yes' if continue_safety_aware else 'Not yet / only with caution'}: the minimal fixed-rate governor evidence should be judged before adding safety-aware gating. If target reaching is preserved and alpha improves without omega degradation, continue to a safety-aware governor or PSF/gatekeeper-lite; otherwise report the mixed result without tuning more rates.",
            "",
            "## Outputs",
            "- `stage7b_minimal_summary.csv` contains per-method/per-condition metrics.",
            "- Per-run logs are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
        ]
    )
    (output_root / "stage7b_minimal_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _method_configs()
    commands = [
        "conda run -n mpc_learn python -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests",
        "conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage7b_progress_governor.py",
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
                row["stage7b_method"] = method
                row["stage7b_condition"] = condition
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

    save_summary(summary_rows, output_root / "stage7b_minimal_summary.csv")
    save_trajectory_plots(all_rows, output_root)
    save_bar_plot(summary_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 7B-minimal fixed-rate progress governor")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7b_minimal_summary.csv'}")
    print(f"  report      : {output_root / 'stage7b_minimal_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_p95={row['alpha_p95_severity']:.4f}, "
            f"omega_p95={row['omega_p95_severity']:.4f}, "
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
