"""Compare alpha-soft safety-aware CEM variants for Spring2D adaptive MPC."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_alpha_soft"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]


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
        solve_count = int(row.get("mpc_solve_count", 0))
        if solve_count <= 0 or solve_count in seen:
            continue
        seen.add(solve_count)
        decisions.append(row)
    return decisions


def _build_methods(base_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    solver = base_cfg["mpc_params"].get("solver", {})
    alpha_weights = solver.get("alpha_soft_weight_list", [1, 10, 100, 1000])
    relaxed_multipliers = solver.get("alpha_relaxed_multiplier_list", [2.0, 3.0])
    methods: dict[str, dict[str, Any]] = {
        "baseline_cem": {
            "solver_safety_mode": "off",
            "alpha_constraint_mode": "hard",
            "alpha_soft_weight": float(solver.get("alpha_soft_weight", 1.0)),
            "alpha_relaxed_multiplier": float(solver.get("alpha_relaxed_multiplier", 2.0)),
        },
        "hard_alpha_feasfirst": {
            "solver_safety_mode": "feasibility_first",
            "alpha_constraint_mode": "hard",
            "alpha_soft_weight": float(solver.get("alpha_soft_weight", 1.0)),
            "alpha_relaxed_multiplier": float(solver.get("alpha_relaxed_multiplier", 2.0)),
        },
    }
    for weight in alpha_weights:
        value = float(weight)
        methods[f"alpha_soft_w{value:g}"] = {
            "solver_safety_mode": "soft_penalty",
            "alpha_constraint_mode": "soft",
            "alpha_soft_weight": value,
            "alpha_relaxed_multiplier": float(solver.get("alpha_relaxed_multiplier", 2.0)),
        }
    for multiplier in relaxed_multipliers:
        value = float(multiplier)
        methods[f"alpha_relaxed_m{value:g}"] = {
            "solver_safety_mode": "feasibility_first",
            "alpha_constraint_mode": "relaxed",
            "alpha_soft_weight": float(solver.get("alpha_soft_weight", 1.0)),
            "alpha_relaxed_multiplier": value,
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
    solver["alpha_relaxed_multiplier"] = float(method_cfg["alpha_relaxed_multiplier"])
    solver.setdefault("safety_penalty_weight", 1.0)
    solver.setdefault(
        "safety_violation_weights",
        {"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 1.0, "alpha": 1.0},
    )
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    return cfg


def add_action_diff_vs_baseline(all_rows: dict[tuple[str, str], list[dict[str, Any]]], methods: dict[str, Any]) -> None:
    for condition in CONDITIONS:
        baseline = all_rows[("baseline_cem", condition)]
        baseline_by_step = {
            int(row.get("step", index)): np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))])
            for index, row in enumerate(baseline)
        }
        for method in methods:
            for index, row in enumerate(all_rows[(method, condition)]):
                step = int(row.get("step", index))
                if step in baseline_by_step:
                    action = np.array([float(row.get("F_tan", 0.0)), float(row.get("F_rad", 0.0))])
                    row["action_diff_vs_baseline"] = float(np.linalg.norm(action - baseline_by_step[step]))
                else:
                    row["action_diff_vs_baseline"] = np.nan


def summarize_rows(
    method: str,
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
    omega_sev = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    alpha_norm = alpha_sev / alpha_max if alpha_max > 0.0 else np.full_like(alpha_sev, np.nan)
    return {
        "method": method,
        "condition": condition,
        "solver_safety_mode": str(final.get("cem_safety_mode", "")),
        "alpha_constraint_mode": str(final.get("cem_alpha_constraint_mode", "hard")),
        "alpha_soft_weight": float(final.get("cem_alpha_soft_weight", np.nan)),
        "alpha_relaxed_multiplier": float(final.get("cem_alpha_relaxed_multiplier", np.nan)),
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
        "mean_alpha_relaxed_feasibility_ratio": _finite_mean(
            _series(decisions, "cem_alpha_relaxed_feasible_ratio")
        ),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_max_severity": _finite_max(omega_sev),
        "omega_mean_severity": _finite_mean(omega_sev),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_max_severity": _finite_max(alpha_sev),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "delta_r_violation_count": int(np.count_nonzero(delta_r_sev > 0.0)),
        "delta_r_max_severity": _finite_max(delta_r_sev),
        "delta_r_mean_severity": _finite_mean(delta_r_sev),
        "F_tan_violation_count": int(np.count_nonzero(F_tan_sev > 0.0)),
        "F_rad_violation_count": int(np.count_nonzero(F_rad_sev > 0.0)),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "mean_action_diff_vs_baseline": _finite_mean(_series(rows, "action_diff_vs_baseline")),
        "max_action_diff_vs_baseline": _finite_max(_series(rows, "action_diff_vs_baseline")),
        "mean_selected_pred_one_step_alpha_violation": _finite_mean(
            _series(decisions, "cem_selected_one_step_norm_violation_alpha")
        ),
        "mean_selected_pred_horizon_alpha_violation": _finite_mean(
            _series(decisions, "cem_selected_max_norm_violation_alpha")
        ),
        "mean_selected_pred_horizon_alpha_cost": _finite_mean(
            _series(decisions, "cem_selected_total_normalized_alpha_score")
        ),
        "mean_executed_true_alpha_violation": _finite_mean(alpha_norm),
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "solver_safety_mode",
    "alpha_constraint_mode",
    "alpha_soft_weight",
    "alpha_relaxed_multiplier",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "mean_feasible_ratio_excluding_alpha",
    "mean_alpha_feasibility_ratio_original",
    "mean_alpha_relaxed_feasibility_ratio",
    "omega_violation_count",
    "omega_max_severity",
    "omega_mean_severity",
    "alpha_violation_count",
    "alpha_max_severity",
    "alpha_mean_severity",
    "delta_r_violation_count",
    "delta_r_max_severity",
    "delta_r_mean_severity",
    "F_tan_violation_count",
    "F_rad_violation_count",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "mean_action_diff_vs_baseline",
    "max_action_diff_vs_baseline",
    "mean_selected_pred_one_step_alpha_violation",
    "mean_selected_pred_horizon_alpha_violation",
    "mean_selected_pred_horizon_alpha_cost",
    "mean_executed_true_alpha_violation",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_condition_plots(
    condition: str,
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    methods: dict[str, Any],
    output_root: Path,
    cfg: dict[str, Any],
) -> None:
    constraints = cfg["mpc_params"].get("constraints", {})
    alpha_max = float(constraints.get("alpha_max", cfg["true_params"].get("alpha_max", np.inf)))

    def plot_series(key: str, ylabel: str, title: str, filename: str, transform: Any | None = None) -> None:
        fig, ax = plt.subplots(figsize=(12, 5))
        for method in methods:
            rows = all_rows[(method, condition)]
            values = _series(rows, key)
            if transform is not None:
                values = transform(values)
            ax.plot(_series(rows, "t"), values, label=method)
        ax.set_title(f"{title}: {condition}")
        ax.set_xlabel("time [s]")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
        fig.tight_layout()
        path = output_root / "figs" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)
        plt.close(fig)

    plot_series("theta", "theta [deg]", "Theta trajectory", f"{condition}_theta_trajectory.png", np.degrees)
    plot_series("alpha_step", "alpha", "Alpha trajectory", f"{condition}_alpha_trajectory.png")
    plot_series("omega", "omega", "Omega trajectory", f"{condition}_omega_trajectory.png")

    fig, ax = plt.subplots(figsize=(12, 5))
    for method in methods:
        rows = all_rows[(method, condition)]
        ax.plot(_series(rows, "t"), _series(rows, "F_tan"), label=f"{method} F_tan")
        ax.plot(_series(rows, "t"), _series(rows, "F_rad"), linestyle="--", label=f"{method} F_rad")
    ax.set_title(f"F_tan / F_rad trajectory: {condition}")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("force")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=6, loc="best", ncol=2)
    fig.tight_layout()
    fig.savefig(output_root / "figs" / f"{condition}_force_trajectory.png", dpi=150)
    plt.close(fig)

    plot_series(
        "alpha_step",
        "normalized alpha violation",
        "Alpha violation severity over time",
        f"{condition}_alpha_violation_severity.png",
        lambda values: np.maximum(0.0, np.abs(values) - alpha_max) / alpha_max,
    )
    plot_series(
        "action_diff_vs_baseline",
        "||u - u_baseline||",
        "Action diff vs baseline",
        f"{condition}_action_diff_vs_baseline.png",
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    for method in methods:
        decisions = _decision_rows(all_rows[(method, condition)])
        task = _series(decisions, "best_task_cost")
        alpha_cost = _series(decisions, "cem_selected_total_normalized_alpha_score")
        finite = np.isfinite(task) & np.isfinite(alpha_cost)
        ax.scatter(task[finite], alpha_cost[finite], s=12, alpha=0.45, label=method)
    ax.set_title(f"Selected trajectory alpha cost vs task cost: {condition}")
    ax.set_xlabel("selected task cost")
    ax.set_ylabel("selected alpha safety cost")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(output_root / "figs" / f"{condition}_alpha_cost_vs_task_cost.png", dpi=150)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def _best_soft(summary_rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    candidates = [
        row
        for row in summary_rows
        if row["condition"] == condition and str(row["method"]).startswith("alpha_soft_w")
    ]
    return min(
        candidates,
        key=lambda row: (
            not bool(row["target_reached"]),
            float(row["alpha_mean_severity"]),
            float(row["omega_mean_severity"]) + float(row["delta_r_mean_severity"]),
            -float(row["final_theta_deg"]),
        ),
    )


def _best_relaxed(summary_rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    candidates = [
        row
        for row in summary_rows
        if row["condition"] == condition and str(row["method"]).startswith("alpha_relaxed_m")
    ]
    return min(
        candidates,
        key=lambda row: (
            not bool(row["target_reached"]),
            float(row["alpha_mean_severity"]),
            float(row["omega_mean_severity"]) + float(row["delta_r_mean_severity"]),
            -float(row["final_theta_deg"]),
        ),
    )


def _row(summary_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    return next(row for row in summary_rows if row["method"] == method and row["condition"] == condition)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    lines = [
        "# Stage 7A-fix Alpha-Soft CEM Report",
        "",
        "## Scope",
        "- Added optional CEM `alpha_constraint_mode`: `hard`, `soft`, and `relaxed`.",
        "- `hard` preserves the previous alpha-hard safety-aware CEM behavior.",
        "- `soft` removes alpha from safety feasibility and keeps alpha only as a weighted normalized planning cost.",
        "- `relaxed` treats alpha as a feasibility failure only beyond `alpha_relaxed_multiplier * alpha_max`; alpha still contributes to cost.",
        "- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier data flow, physical parameters, gravity handling, noise/bias settings, baseline CEM behavior when `safety_mode=off`, and old runtime filter behavior were not changed.",
        "- No post-result manual tuning was performed. This is not a formal safety guarantee.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Summary",
        "| method | condition | target | final theta deg | feasible excl alpha | alpha feas orig | alpha feas relaxed | alpha viol count | alpha mean sev | omega viol count | omega mean sev | delta_r viol count | action diff | pred horizon alpha | exec alpha | runtime s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['method']} | {row['condition']} | {row['target_reached']} | "
            f"{_fmt(row['final_theta_deg'])} | {_fmt(row['mean_feasible_ratio_excluding_alpha'])} | "
            f"{_fmt(row['mean_alpha_feasibility_ratio_original'])} | "
            f"{_fmt(row['mean_alpha_relaxed_feasibility_ratio'])} | "
            f"{row['alpha_violation_count']} | {_fmt(row['alpha_mean_severity'])} | "
            f"{row['omega_violation_count']} | {_fmt(row['omega_mean_severity'])} | "
            f"{row['delta_r_violation_count']} | {_fmt(row['mean_action_diff_vs_baseline'])} | "
            f"{_fmt(row['mean_selected_pred_horizon_alpha_violation'])} | "
            f"{_fmt(row['mean_executed_true_alpha_violation'])} | {_fmt(row['runtime_s'])} |"
        )

    lines.extend(["", "## Required Answers"])
    for condition in CONDITIONS:
        baseline = _row(summary_rows, "baseline_cem", condition)
        hard = _row(summary_rows, "hard_alpha_feasfirst", condition)
        best_soft = _best_soft(summary_rows, condition)
        best_relaxed = _best_relaxed(summary_rows, condition)
        lines.extend(
            [
                "",
                f"### {condition}",
                "1. Does removing alpha from hard feasibility make safety-aware CEM actually change actions?",
                f"- Best soft action-diff mean={_fmt(best_soft['mean_action_diff_vs_baseline'])}; best relaxed action-diff mean={_fmt(best_relaxed['mean_action_diff_vs_baseline'])}; hard-alpha action-diff mean={_fmt(hard['mean_action_diff_vs_baseline'])}. Nonzero values indicate changed actions.",
                "2. Which alpha soft weight gives the best safety/task tradeoff?",
                f"- By target-reaching first, then alpha mean severity and omega/delta_r severity, `{best_soft['method']}` is the best soft-weight case in this compact sweep.",
                "3. Does relaxed alpha feasibility work better than pure soft alpha?",
                f"- Best soft `{best_soft['method']}`: alpha mean severity={_fmt(best_soft['alpha_mean_severity'])}, final theta={_fmt(best_soft['final_theta_deg'])}. Best relaxed `{best_relaxed['method']}`: alpha mean severity={_fmt(best_relaxed['alpha_mean_severity'])}, final theta={_fmt(best_relaxed['final_theta_deg'])}.",
                "4. Does target reaching remain successful?",
                f"- baseline={baseline['target_reached']}; hard-alpha={hard['target_reached']}; best soft={best_soft['target_reached']}; best relaxed={best_relaxed['target_reached']}.",
                "5. Does alpha severity decrease without increasing omega/delta_r violations too much?",
                f"- baseline alpha/omega/delta counts={baseline['alpha_violation_count']}/{baseline['omega_violation_count']}/{baseline['delta_r_violation_count']}; best soft={best_soft['alpha_violation_count']}/{best_soft['omega_violation_count']}/{best_soft['delta_r_violation_count']}; best relaxed={best_relaxed['alpha_violation_count']}/{best_relaxed['omega_violation_count']}/{best_relaxed['delta_r_violation_count']}.",
                "6. Is the controller becoming too conservative?",
                f"- Compare final theta and mean action: baseline theta={_fmt(baseline['final_theta_deg'])}, action={_fmt(baseline['mean_action_magnitude'])}; best soft theta={_fmt(best_soft['final_theta_deg'])}, action={_fmt(best_soft['mean_action_magnitude'])}; best relaxed theta={_fmt(best_relaxed['final_theta_deg'])}, action={_fmt(best_relaxed['mean_action_magnitude'])}. Lower action with failed/slow target reaching would indicate conservatism.",
                "7. Should the next step be weight refinement, adaptive tightening, PSF/gatekeeper-lite, or progress governor?",
                "- If a soft/relaxed case changes actions and reduces alpha severity while preserving target reaching, the next step is a small approved weight-refinement sweep. If all cases still have high alpha severity or poor target progress, prefer a progress governor or PSF/gatekeeper-lite before adaptive tightening. No automatic tuning was applied here.",
            ]
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "- `stage7a_alpha_soft_summary.csv` contains the compact comparison metrics.",
            "- Per-run timeseries are under `logs/{method}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
            "Bad or mixed results are reported as-is.",
            "",
        ]
    )
    (output_root / "stage7a_alpha_soft_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    methods = _build_methods(base_cfg)
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_stage7a_alpha_soft_constraint.py",
    ]
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    runtimes: dict[tuple[str, str], float] = {}

    for method, method_cfg in methods.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            start = time.perf_counter()
            rows = run_condition(condition, cfg["conditions"][condition], cfg)
            runtimes[(method, condition)] = time.perf_counter() - start
            all_rows[(method, condition)] = rows
            print(f"Completed method={method}, condition={condition}")

    add_action_diff_vs_baseline(all_rows, methods)
    summary_rows: list[dict[str, Any]] = []
    for method, method_cfg in methods.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            rows = all_rows[(method, condition)]
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            summary_rows.append(summarize_rows(method, condition, rows, cfg, runtimes[(method, condition)]))

    save_summary(summary_rows, output_root / "stage7a_alpha_soft_summary.csv")
    for condition in CONDITIONS:
        save_condition_plots(condition, all_rows, methods, output_root, base_cfg)
    save_report(summary_rows, output_root, commands)

    print("Stage 7A-fix alpha-soft CEM comparison")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7a_alpha_soft_summary.csv'}")
    print(f"  report      : {output_root / 'stage7a_alpha_soft_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"alpha_mean={row['alpha_mean_severity']:.4f}, "
            f"action_diff={row['mean_action_diff_vs_baseline']:.4f}, "
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
