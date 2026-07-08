"""Diagnose Stage 7A safety-aware CEM selection behavior."""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_diagnosis"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise_bias"]
METHODS: dict[str, dict[str, Any]] = {
    "baseline_cem": {"solver_safety_mode": "off"},
    "cem_soft_penalty": {"solver_safety_mode": "soft_penalty"},
    "cem_feasibility_first": {"solver_safety_mode": "feasibility_first"},
    "cem_lexicographic": {"solver_safety_mode": "lexicographic"},
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


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0 or not np.isfinite(denominator):
        return np.nan
    return float(numerator / denominator)


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(mask) < 2:
        return np.nan
    x_valid = x[mask]
    y_valid = y[mask]
    if np.std(x_valid) <= 0.0 or np.std(y_valid) <= 0.0:
        return np.nan
    return float(np.corrcoef(x_valid, y_valid)[0, 1])


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


def _normalize(value: float, limit: float) -> float:
    if limit <= 0.0:
        return float("inf") if value > 0.0 else 0.0
    return float(value / limit)


def _executed_one_step_violation(
    action_exec: np.ndarray,
    history_row: dict[str, Any],
    alpha_step: float,
    cfg: dict[str, Any],
) -> dict[str, float]:
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    limits = {
        "F_tan": float(constraints.get("F_tan_max", true_params["F_tan_max"])),
        "F_rad": float(constraints.get("F_rad_max", true_params["F_rad_max"])),
        "delta_r": float(constraints.get("delta_r_max", true_params["delta_r_max"])),
        "omega": float(constraints.get("omega_max", true_params["omega_max"])),
        "alpha": float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf))),
    }
    raw = {
        "F_tan": max(0.0, abs(float(action_exec[0])) - limits["F_tan"]),
        "F_rad": max(0.0, abs(float(action_exec[1])) - limits["F_rad"]),
        "delta_r": max(0.0, abs(float(history_row.get("delta_r", 0.0))) - limits["delta_r"]),
        "omega": max(0.0, abs(float(history_row.get("omega", 0.0))) - limits["omega"]),
        "alpha": max(0.0, abs(float(alpha_step)) - limits["alpha"]),
    }
    normalized = {name: _normalize(value, limits[name]) for name, value in raw.items()}
    total = float(sum(value**2 for value in normalized.values()))
    result = {"executed_true_one_step_violation": total}
    result.update({f"executed_true_one_step_violation_{name}": float(value) for name, value in normalized.items()})
    return result


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver.setdefault("safety_penalty_weight", 1.0)
    solver.setdefault(
        "safety_violation_weights",
        {"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 1.0, "alpha": 1.0},
    )
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["collect_iteration_diagnostics"] = True
    solver["collect_sample_diagnostics"] = True
    return cfg


def make_diagnostics_callback(
    method: str,
    iteration_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
) -> Any:
    def callback(**kwargs: Any) -> None:
        solve_diag = kwargs["solve_diagnostics"]
        condition = kwargs["condition_name"]
        step = int(kwargs["step"])
        solve_count = int(solve_diag.get("mpc_solve_count", 0))
        time_value = float(kwargs["time"])
        base = {
            "method": method,
            "condition": condition,
            "timestep": step,
            "time": time_value,
            "mpc_solve_count": solve_count,
            "safety_mode": str(solve_diag.get("safety_mode", "off")),
        }
        for row in solve_diag.get("cem_iteration_diagnostics", []):
            iteration_rows.append({**base, **row})
        for row in solve_diag.get("cem_sample_diagnostics", []):
            sample_rows.append({**base, **row})

        executed = _executed_one_step_violation(
            np.asarray(kwargs["action_exec"], dtype=float),
            kwargs["history_row"],
            float(kwargs["alpha_step"]),
            kwargs["cfg"],
        )
        pred_one = float(solve_diag.get("selected_safety_one_step_total_normalized_score", np.nan))
        selected = {
            **base,
            "selected_action_F_tan": float(solve_diag.get("selected_sequence_first_F_tan", np.nan)),
            "selected_action_F_rad": float(solve_diag.get("selected_sequence_first_F_rad", np.nan)),
            "selected_trajectory_task_cost": float(solve_diag.get("best_task_cost", np.nan)),
            "selected_trajectory_safety_cost": float(solve_diag.get("best_safety_score", np.nan)),
            "selected_trajectory_total_cost": float(solve_diag.get("best_ranking_cost", np.nan)),
            "selected_pred_one_step_violation": pred_one,
            "selected_pred_horizon_violation": float(
                solve_diag.get("selected_safety_total_normalized_score", np.nan)
            ),
            "selected_pred_one_step_violation_F_tan": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_F_tan", np.nan)
            ),
            "selected_pred_one_step_violation_F_rad": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_F_rad", np.nan)
            ),
            "selected_pred_one_step_violation_delta_r": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_delta_r", np.nan)
            ),
            "selected_pred_one_step_violation_omega": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_omega", np.nan)
            ),
            "selected_pred_one_step_violation_alpha": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_alpha", np.nan)
            ),
            "selected_horizon_violation_F_tan": float(
                solve_diag.get("selected_safety_max_normalized_violation_F_tan", np.nan)
            ),
            "selected_horizon_violation_F_rad": float(
                solve_diag.get("selected_safety_max_normalized_violation_F_rad", np.nan)
            ),
            "selected_horizon_violation_delta_r": float(
                solve_diag.get("selected_safety_max_normalized_violation_delta_r", np.nan)
            ),
            "selected_horizon_violation_omega": float(
                solve_diag.get("selected_safety_max_normalized_violation_omega", np.nan)
            ),
            "selected_horizon_violation_alpha": float(
                solve_diag.get("selected_safety_max_normalized_violation_alpha", np.nan)
            ),
        }
        selected.update(executed)
        selected["predicted_vs_executed_one_step_violation_error"] = float(
            selected["executed_true_one_step_violation"] - pred_one
        )
        selection_rows.append(selected)

    return callback


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_run(
    method: str,
    condition: str,
    rows: list[dict[str, Any]],
    iteration_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
    runtime_s: float,
    action_diff_vs_baseline: float = np.nan,
) -> dict[str, Any]:
    final = rows[-1]
    decisions = _decision_rows(rows)
    feasible_decisions = sum(bool(row.get("mpc_result_feasible", False)) for row in decisions)
    constraints = rows[0]
    del constraints
    pred = _series(selection_rows, "selected_pred_one_step_violation")
    executed = _series(selection_rows, "executed_true_one_step_violation")
    feasible_fields = {
        "mean_feasible_all_ratio": _finite_mean(_series(iteration_rows, "feasible_all_ratio")),
        "mean_safety_feasible_ratio": _finite_mean(_series(iteration_rows, "safety_feasible_ratio")),
        "mean_force_feasible_ratio": _finite_mean(_series(iteration_rows, "feasible_force_bounds_ratio")),
        "mean_delta_r_feasible_ratio": _finite_mean(_series(iteration_rows, "feasible_delta_r_ratio")),
        "mean_omega_feasible_ratio": _finite_mean(_series(iteration_rows, "feasible_omega_ratio")),
        "mean_alpha_feasible_ratio": _finite_mean(_series(iteration_rows, "feasible_alpha_ratio")),
    }
    blocker_candidates = {
        "force_bounds": feasible_fields["mean_force_feasible_ratio"],
        "delta_r": feasible_fields["mean_delta_r_feasible_ratio"],
        "omega": feasible_fields["mean_omega_feasible_ratio"],
        "alpha": feasible_fields["mean_alpha_feasible_ratio"],
    }
    main_blocker = min(
        blocker_candidates,
        key=lambda key: blocker_candidates[key] if np.isfinite(blocker_candidates[key]) else np.inf,
    )
    return {
        "method": method,
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "feasible_mpc_decisions": int(feasible_decisions),
        "total_mpc_decisions": int(len(decisions)),
        "feasible_mpc_decision_ratio": _safe_ratio(feasible_decisions, len(decisions)),
        **feasible_fields,
        "main_feasibility_blocker": main_blocker,
        "mean_selected_task_cost": _finite_mean(_series(selection_rows, "selected_trajectory_task_cost")),
        "mean_selected_safety_cost": _finite_mean(_series(selection_rows, "selected_trajectory_safety_cost")),
        "mean_selected_ranking_cost": _finite_mean(_series(selection_rows, "selected_trajectory_total_cost")),
        "mean_selected_pred_one_step_violation": _finite_mean(pred),
        "mean_selected_pred_horizon_violation": _finite_mean(
            _series(selection_rows, "selected_pred_horizon_violation")
        ),
        "mean_executed_true_one_step_violation": _finite_mean(executed),
        "max_executed_true_one_step_violation": _finite_max(executed),
        "predicted_executed_one_step_corr": _correlation(pred, executed),
        "mean_predicted_executed_one_step_error": _finite_mean(
            _series(selection_rows, "predicted_vs_executed_one_step_violation_error")
        ),
        "mean_selected_horizon_violation_F_tan": _finite_mean(
            _series(selection_rows, "selected_horizon_violation_F_tan")
        ),
        "mean_selected_horizon_violation_F_rad": _finite_mean(
            _series(selection_rows, "selected_horizon_violation_F_rad")
        ),
        "mean_selected_horizon_violation_delta_r": _finite_mean(
            _series(selection_rows, "selected_horizon_violation_delta_r")
        ),
        "mean_selected_horizon_violation_omega": _finite_mean(
            _series(selection_rows, "selected_horizon_violation_omega")
        ),
        "mean_selected_horizon_violation_alpha": _finite_mean(
            _series(selection_rows, "selected_horizon_violation_alpha")
        ),
        "mean_abs_action_diff_vs_baseline": float(action_diff_vs_baseline),
        "runtime_s": float(runtime_s),
    }


def add_baseline_action_diffs(
    summary_rows: list[dict[str, Any]],
    selection_by_run: dict[tuple[str, str], list[dict[str, Any]]],
) -> None:
    for condition in CONDITIONS:
        baseline = {
            int(row["mpc_solve_count"]): np.array(
                [float(row["selected_action_F_tan"]), float(row["selected_action_F_rad"])],
                dtype=float,
            )
            for row in selection_by_run[("baseline_cem", condition)]
        }
        for row in summary_rows:
            if row["condition"] != condition:
                continue
            diffs = []
            for selected in selection_by_run[(row["method"], condition)]:
                solve_count = int(selected["mpc_solve_count"])
                if solve_count not in baseline:
                    continue
                action = np.array(
                    [float(selected["selected_action_F_tan"]), float(selected["selected_action_F_rad"])],
                    dtype=float,
                )
                diffs.append(float(np.linalg.norm(action - baseline[solve_count])))
            row["mean_abs_action_diff_vs_baseline"] = _finite_mean(np.asarray(diffs, dtype=float))


def _filter_sample_rows(
    sample_rows: list[dict[str, Any]],
    condition: str,
    method: str,
    solve_count: int,
) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in sample_rows
        if row["condition"] == condition
        and row["method"] == method
        and int(row["mpc_solve_count"]) == solve_count
    ]
    if not candidates:
        return []
    final_iteration = max(int(row["cem_iteration"]) for row in candidates)
    return [row for row in candidates if int(row["cem_iteration"]) == final_iteration]


def save_task_safety_scatter(sample_rows: list[dict[str, Any]], output_root: Path) -> None:
    for condition in CONDITIONS:
        fig, axes = plt.subplots(len(METHODS), 3, figsize=(12, 10), sharex=False, sharey=False)
        for row_index, method in enumerate(METHODS):
            solves = sorted(
                {
                    int(row["mpc_solve_count"])
                    for row in sample_rows
                    if row["condition"] == condition and row["method"] == method
                }
            )
            chosen = [solves[0], solves[len(solves) // 2], solves[-1]] if solves else []
            for col_index, solve_count in enumerate(chosen):
                ax = axes[row_index, col_index]
                rows = _filter_sample_rows(sample_rows, condition, method, solve_count)
                task = _series(rows, "task_cost")
                safety = _series(rows, "safety_cost")
                elite = np.array([bool(row.get("is_elite", False)) for row in rows], dtype=bool)
                finite = np.isfinite(task) & np.isfinite(safety)
                ax.scatter(task[finite & ~elite], safety[finite & ~elite], s=8, alpha=0.25, label="all")
                ax.scatter(task[finite & elite], safety[finite & elite], s=12, alpha=0.8, label="elite")
                ax.set_title(f"{method} solve {solve_count}", fontsize=8)
                ax.grid(True, alpha=0.25)
                if row_index == len(METHODS) - 1:
                    ax.set_xlabel("task cost")
                if col_index == 0:
                    ax.set_ylabel("safety cost")
            for col_index in range(len(chosen), 3):
                axes[row_index, col_index].axis("off")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, labels, loc="upper right")
        fig.suptitle(f"Task cost vs safety cost samples: {condition}")
        fig.tight_layout(rect=(0.0, 0.0, 0.98, 0.96))
        path = output_root / "figs" / f"{condition}_task_vs_safety_scatter.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)
        plt.close(fig)


def save_elite_distribution(sample_rows: list[dict[str, Any]], output_root: Path) -> None:
    for condition in CONDITIONS:
        labels = []
        data = []
        for method in METHODS:
            method_rows = [
                row for row in sample_rows if row["condition"] == condition and row["method"] == method
            ]
            all_values = _finite(_series(method_rows, "safety_cost"))
            elite_values = _finite(_series([row for row in method_rows if bool(row.get("is_elite", False))], "safety_cost"))
            labels.extend([f"{method}\nall", f"{method}\nelite"])
            data.extend([all_values, elite_values])
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.boxplot(data, labels=labels, showfliers=False)
        ax.set_ylabel("safety cost")
        ax.set_title(f"Elite vs all-sample safety cost distribution: {condition}")
        ax.grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        path = output_root / "figs" / f"{condition}_elite_vs_all_safety_distribution.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)
        plt.close(fig)


def save_time_plots(
    iteration_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    for condition in CONDITIONS:
        fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=False)
        for method in METHODS:
            selected = [row for row in selection_rows if row["condition"] == condition and row["method"] == method]
            iterations = [row for row in iteration_rows if row["condition"] == condition and row["method"] == method]
            t_sel = _series(selected, "time")
            axes[0].plot(t_sel, _series(selected, "selected_pred_horizon_violation"), label=method)
            axes[1].plot(t_sel, _series(selected, "selected_pred_one_step_violation"), label=f"{method} pred")
            axes[1].plot(
                t_sel,
                _series(selected, "executed_true_one_step_violation"),
                linestyle="--",
                label=f"{method} executed",
            )
            t_it = _series(iterations, "time")
            axes[2].plot(t_it, _series(iterations, "feasible_force_bounds_ratio"), label=f"{method} force")
            axes[2].plot(t_it, _series(iterations, "feasible_delta_r_ratio"), linestyle=":", label=f"{method} delta_r")
            axes[2].plot(t_it, _series(iterations, "feasible_omega_ratio"), linestyle="--", label=f"{method} omega")
            axes[3].plot(t_it, _series(iterations, "feasible_alpha_ratio"), label=method)
        axes[0].set_title("Selected trajectory horizon safety cost over time")
        axes[1].set_title("Selected predicted one-step vs executed true one-step violation")
        axes[2].set_title("Feasibility ratio by constraint over time")
        axes[3].set_title("Alpha feasibility ratio over time")
        for ax in axes:
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=7, loc="best")
            ax.set_xlabel("time [s]")
        fig.suptitle(f"Stage 7A diagnosis time plots: {condition}")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
        path = output_root / "figs" / f"{condition}_selection_and_feasibility_time_plots.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        _save_selected_horizon_safety_plot(condition, selection_rows, output_root)
        _save_predicted_executed_one_step_plot(condition, selection_rows, output_root)
        _save_feasibility_by_constraint_plot(condition, iteration_rows, output_root)
        _save_alpha_feasibility_plot(condition, iteration_rows, output_root)


def _save_selected_horizon_safety_plot(
    condition: str,
    selection_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    for method in METHODS:
        selected = [row for row in selection_rows if row["condition"] == condition and row["method"] == method]
        ax.plot(_series(selected, "time"), _series(selected, "selected_pred_horizon_violation"), label=method)
    ax.set_title(f"Selected trajectory safety cost over time: {condition}")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("selected_pred_horizon_violation")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = output_root / "figs" / f"{condition}_selected_horizon_safety_over_time.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_predicted_executed_one_step_plot(
    condition: str,
    selection_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    for method in METHODS:
        selected = [row for row in selection_rows if row["condition"] == condition and row["method"] == method]
        t = _series(selected, "time")
        ax.plot(t, _series(selected, "selected_pred_one_step_violation"), label=f"{method} pred")
        ax.plot(t, _series(selected, "executed_true_one_step_violation"), linestyle="--", label=f"{method} exec")
    ax.set_title(f"Selected predicted one-step vs executed true one-step violation: {condition}")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("normalized one-step violation")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    path = output_root / "figs" / f"{condition}_predicted_vs_executed_one_step_violation.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_feasibility_by_constraint_plot(
    condition: str,
    iteration_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    fig, axes = plt.subplots(len(METHODS), 1, figsize=(11, 9), sharex=True, sharey=True)
    for ax, method in zip(axes, METHODS):
        rows = [row for row in iteration_rows if row["condition"] == condition and row["method"] == method]
        t = _series(rows, "time")
        ax.plot(t, _series(rows, "feasible_force_bounds_ratio"), label="force")
        ax.plot(t, _series(rows, "feasible_delta_r_ratio"), label="delta_r")
        ax.plot(t, _series(rows, "feasible_omega_ratio"), label="omega")
        ax.plot(t, _series(rows, "feasible_alpha_ratio"), label="alpha")
        ax.set_title(method, fontsize=9)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
    axes[-1].set_xlabel("time [s]")
    fig.suptitle(f"Feasibility ratio by constraint over time: {condition}")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    path = output_root / "figs" / f"{condition}_feasibility_ratio_by_constraint_over_time.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_alpha_feasibility_plot(
    condition: str,
    iteration_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    for method in METHODS:
        rows = [row for row in iteration_rows if row["condition"] == condition and row["method"] == method]
        ax.plot(_series(rows, "time"), _series(rows, "feasible_alpha_ratio"), label=method)
    ax.set_title(f"Alpha feasibility ratio over time: {condition}")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("feasible_alpha_ratio")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = output_root / "figs" / f"{condition}_alpha_feasibility_ratio_over_time.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def _row(summary_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    return next(row for row in summary_rows if row["method"] == method and row["condition"] == condition)


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    lines = [
        "# Stage 7A CEM Selection Diagnosis",
        "",
        "## Scope",
        "- Added diagnostic logging only for CEM selection; no new controller method was added.",
        "- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier flow, physical parameters, gravity handling, noise/bias settings, baseline behavior, and existing safety-aware CEM behavior were not intentionally changed.",
        "- Safety quantities are standardized as `selected_pred_one_step_violation`, `selected_pred_horizon_violation`, and `executed_true_one_step_violation`.",
        "- No post-result tuning was performed. This is not a formal safety guarantee.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Compact Summary",
        "| method | condition | target | final theta deg | feasible decision ratio | safety feasible ratio | force ratio | delta_r ratio | omega ratio | alpha ratio | blocker | pred 1-step mean | executed 1-step mean | pred/exe corr | action diff vs baseline |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['method']} | {row['condition']} | {row['target_reached']} | "
            f"{_fmt(row['final_theta_deg'])} | {_fmt(row['feasible_mpc_decision_ratio'])} | "
            f"{_fmt(row['mean_safety_feasible_ratio'])} | {_fmt(row['mean_force_feasible_ratio'])} | "
            f"{_fmt(row['mean_delta_r_feasible_ratio'])} | {_fmt(row['mean_omega_feasible_ratio'])} | "
            f"{_fmt(row['mean_alpha_feasible_ratio'])} | {row['main_feasibility_blocker']} | "
            f"{_fmt(row['mean_selected_pred_one_step_violation'])} | "
            f"{_fmt(row['mean_executed_true_one_step_violation'])} | "
            f"{_fmt(row['predicted_executed_one_step_corr'])} | "
            f"{_fmt(row['mean_abs_action_diff_vs_baseline'])} |"
        )
    lines.extend(["", "## Required Answers"])
    for condition in CONDITIONS:
        baseline = _row(summary_rows, "baseline_cem", condition)
        soft = _row(summary_rows, "cem_soft_penalty", condition)
        feas = _row(summary_rows, "cem_feasibility_first", condition)
        lex = _row(summary_rows, "cem_lexicographic", condition)
        lines.extend(
            [
                "",
                f"### {condition}",
                "1. Are soft_penalty and feasibility_first actually changing CEM ranking?",
                f"- soft_penalty action-diff mean={_fmt(soft['mean_abs_action_diff_vs_baseline'])}; feasibility_first action-diff mean={_fmt(feas['mean_abs_action_diff_vs_baseline'])}. Near-zero values indicate no practical ranking change.",
                "2. If not, why?",
                f"- safety-feasible ratio is baseline={_fmt(baseline['mean_safety_feasible_ratio'])}, soft={_fmt(soft['mean_safety_feasible_ratio'])}, feasibility_first={_fmt(feas['mean_safety_feasible_ratio'])}. When this is zero, feasibility_first has no feasible group to prefer. soft_penalty must overcome the existing task-plus-constraint ranking scale; this diagnosis reports the scale mismatch instead of tuning it.",
                "3. Why is feasible ratio 0?",
                f"- The lowest per-constraint feasibility ratio points to `{baseline['main_feasibility_blocker']}` for baseline and `{soft['main_feasibility_blocker']}` for soft_penalty. This means sampled horizons usually violate at least one normalized constraint before all-constraint feasibility can be nonzero.",
                "4. Which constraint is the main feasibility blocker?",
                f"- baseline blocker={baseline['main_feasibility_blocker']}; soft={soft['main_feasibility_blocker']}; feasibility_first={feas['main_feasibility_blocker']}; lexicographic={lex['main_feasibility_blocker']}.",
                "5. Is alpha the dominant blocker?",
                f"- alpha feasibility ratios: baseline={_fmt(baseline['mean_alpha_feasible_ratio'])}, soft={_fmt(soft['mean_alpha_feasible_ratio'])}, feasibility_first={_fmt(feas['mean_alpha_feasible_ratio'])}, lexicographic={_fmt(lex['mean_alpha_feasible_ratio'])}. Compare these against omega/delta_r/force ratios in the table.",
                "6. Are predicted and executed one-step violations comparable after standardization?",
                f"- baseline pred/exe corr={_fmt(baseline['predicted_executed_one_step_corr'])}; soft={_fmt(soft['predicted_executed_one_step_corr'])}; feasibility_first={_fmt(feas['predicted_executed_one_step_corr'])}; lexicographic={_fmt(lex['predicted_executed_one_step_corr'])}. They are now the same one-step normalized quantity, but low/NaN correlation still means poor predictive alignment.",
                "7. Does lexicographic improve selected horizon safety or only change behavior randomly?",
                f"- lexicographic selected horizon safety mean={_fmt(lex['mean_selected_pred_horizon_violation'])}; baseline={_fmt(baseline['mean_selected_pred_horizon_violation'])}. Action-diff mean={_fmt(lex['mean_abs_action_diff_vs_baseline'])}. Lower horizon safety with nonzero action change supports a real ranking effect; otherwise the change is mixed/ambiguous.",
                "8. What minimal fix should be tested next?",
                "- Based on this diagnosis, the next minimal test should target the dominant blocker and ranking scale directly: if alpha feasibility is near zero, test alpha slack/feasibility definition first; if soft_penalty changes little while safety costs are much smaller than task/ranking costs, test weight scaling. Adaptive tightening or a progress governor should come after this diagnostic ambiguity is reduced.",
            ]
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "- `cem_iteration_diagnostics.csv` records CEM iteration-level feasibility and cost distributions.",
            "- `selection_diagnostics.csv` records selected predicted one-step, selected horizon, executed true one-step, and their error.",
            "- `stage7a_diagnosis_summary.csv` records compact per-method/per-condition metrics.",
            "- Figures are under `figs/`.",
            "",
            "Bad or ambiguous results are reported as-is.",
            "",
        ]
    )
    (output_root / "stage7a_diagnosis_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_stage7a_diagnosis.py",
    ]
    iteration_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    selection_by_run: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for method, method_cfg in METHODS.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            run_iteration_start = len(iteration_rows)
            run_selection_start = len(selection_rows)
            callback = make_diagnostics_callback(method, iteration_rows, selection_rows, sample_rows)
            start = time.perf_counter()
            rows = run_condition(condition, cfg["conditions"][condition], cfg, diagnostics_callback=callback)
            runtime_s = time.perf_counter() - start
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            run_iteration_rows = iteration_rows[run_iteration_start:]
            run_selection_rows = selection_rows[run_selection_start:]
            selection_by_run[(method, condition)] = list(run_selection_rows)
            summary_rows.append(
                summarize_run(method, condition, rows, run_iteration_rows, run_selection_rows, runtime_s)
            )
            print(f"Completed method={method}, condition={condition}")

    add_baseline_action_diffs(summary_rows, selection_by_run)
    _write_csv(iteration_rows, output_root / "cem_iteration_diagnostics.csv")
    _write_csv(selection_rows, output_root / "selection_diagnostics.csv")
    _write_csv(summary_rows, output_root / "stage7a_diagnosis_summary.csv")
    save_task_safety_scatter(sample_rows, output_root)
    save_elite_distribution(sample_rows, output_root)
    save_time_plots(iteration_rows, selection_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 7A CEM selection diagnosis")
    print(f"  output root : {output_root}")
    print(f"  iteration   : {output_root / 'cem_iteration_diagnostics.csv'}")
    print(f"  selection   : {output_root / 'selection_diagnostics.csv'}")
    print(f"  summary     : {output_root / 'stage7a_diagnosis_summary.csv'}")
    print(f"  report      : {output_root / 'stage7a_diagnosis_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"safety_feas={row['mean_safety_feasible_ratio']:.4f}, "
            f"alpha_feas={row['mean_alpha_feasible_ratio']:.4f}, "
            f"blocker={row['main_feasibility_blocker']}"
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
