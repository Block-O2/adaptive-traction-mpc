"""Compare adaptive MPC solver choices on the Spring2D conditions."""

from __future__ import annotations

import argparse
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
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_RANDOM_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions.yaml"
DEFAULT_CEM_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions_cem.yaml"
DEFAULT_CEM_FEASFIRST_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions_cem_feasfirst.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage2_cem_feasfirst"


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row[key]) for row in rows], dtype=float)


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return float("nan")


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


def summarize_rows(
    solver_type: str,
    condition: str,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
) -> dict[str, Any]:
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    omega_max = float(constraints.get("omega_max", cfg["true_params"]["omega_max"]))
    alpha_max = float(constraints.get("alpha_max", cfg["true_params"].get("alpha_max", np.inf)))
    decisions = _decision_rows(rows)
    feasible_decisions = sum(bool(row.get("mpc_result_feasible", False)) for row in decisions)
    total_decisions = len(decisions)
    candidate_ratios = [
        float(row["mpc_feasible_ratio"])
        for row in decisions
        if "mpc_feasible_ratio" in row and np.isfinite(float(row["mpc_feasible_ratio"]))
    ]
    feasible_counts = [
        float(row["mpc_feasible_count"])
        for row in decisions
        if "mpc_feasible_count" in row and np.isfinite(float(row["mpc_feasible_count"]))
    ]
    omega_violation_severity = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_violation_severity = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    delta_r_max = float(constraints.get("delta_r_max", cfg["true_params"]["delta_r_max"]))
    F_rad_max = float(constraints.get("F_rad_max", cfg["true_params"]["F_rad_max"]))
    delta_r_violation_severity = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_rad_violation_severity = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    return {
        "solver_type": solver_type,
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "max_abs_F_rad": float(np.max(np.abs(_series(rows, "F_rad")))),
        "max_abs_delta_r": float(np.max(np.abs(_series(rows, "delta_r")))),
        "max_abs_omega": float(np.max(np.abs(_series(rows, "omega")))),
        "max_abs_alpha_step": float(np.max(np.abs(_series(rows, "alpha_step")))),
        "max_abs_F_tan": float(np.max(np.abs(_series(rows, "F_tan")))),
        "feasible_mpc_decisions": int(feasible_decisions),
        "total_mpc_decisions": int(total_decisions),
        "feasible_mpc_decision_ratio": float(feasible_decisions / total_decisions) if total_decisions else np.nan,
        "mean_candidate_feasible_ratio": float(np.mean(candidate_ratios)) if candidate_ratios else np.nan,
        "mean_feasible_count": float(np.mean(feasible_counts)) if feasible_counts else np.nan,
        "min_feasible_count": float(np.min(feasible_counts)) if feasible_counts else np.nan,
        "max_feasible_count": float(np.max(feasible_counts)) if feasible_counts else np.nan,
        "max_omega_violation_severity": float(np.max(omega_violation_severity)),
        "max_alpha_violation_severity": float(np.max(alpha_violation_severity)),
        "sum_omega_violation_severity": float(np.sum(omega_violation_severity)),
        "sum_alpha_violation_severity": float(np.sum(alpha_violation_severity)),
        "max_delta_r_violation_severity": float(np.max(delta_r_violation_severity)),
        "max_F_rad_violation_severity": float(np.max(F_rad_violation_severity)),
        "omega_violation_count": int(np.count_nonzero(np.abs(_series(rows, "omega")) > omega_max)),
        "alpha_violation_count": int(np.count_nonzero(np.abs(_series(rows, "alpha_step")) > alpha_max)),
        "done_reason": final.get("done_reason", ""),
        "runtime_s": float(runtime_s),
    }


def save_summary_table(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "solver_type",
        "condition",
        "target_reached",
        "final_theta_deg",
        "T_reach",
        "max_abs_F_rad",
        "max_abs_delta_r",
        "max_abs_omega",
        "max_abs_alpha_step",
        "max_abs_F_tan",
        "feasible_mpc_decisions",
        "total_mpc_decisions",
        "feasible_mpc_decision_ratio",
        "mean_candidate_feasible_ratio",
        "mean_feasible_count",
        "min_feasible_count",
        "max_feasible_count",
        "max_omega_violation_severity",
        "max_alpha_violation_severity",
        "sum_omega_violation_severity",
        "sum_alpha_violation_severity",
        "max_delta_r_violation_severity",
        "max_F_rad_violation_severity",
        "omega_violation_count",
        "alpha_violation_count",
        "done_reason",
        "runtime_s",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_comparison_figure(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conditions = list(dict.fromkeys(row["condition"] for row in summary_rows))
    solvers = list(dict.fromkeys(row["solver_type"] for row in summary_rows))
    metrics = [
        ("final_theta_deg", "final theta [deg]"),
        ("feasible_mpc_decision_ratio", "feasible decision ratio"),
        ("max_abs_omega", "max |omega|"),
        ("max_abs_alpha_step", "max |alpha_step|"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    x = np.arange(len(conditions))
    width = 0.8 / max(1, len(solvers))
    for ax, (metric, ylabel) in zip(axes.ravel(), metrics):
        for idx, solver in enumerate(solvers):
            values = []
            for condition in conditions:
                match = next(row for row in summary_rows if row["solver_type"] == solver and row["condition"] == condition)
                values.append(float(match[metric]))
            offset = (idx - (len(solvers) - 1) / 2.0) * width
            ax.bar(x + offset, values, width=width, label=solver)
        ax.set_xticks(x, conditions)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=max(1, len(labels)), frameon=False)
    fig.suptitle("Spring2D Adaptive MPC Solver Comparison")
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.96))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _solver_settings_text(name: str, cfg: dict[str, Any]) -> str:
    solver = cfg["mpc_params"].get("solver", {})
    if str(solver.get("type", "")).lower() == "cem":
        keys = [
            "type",
            "selection",
            "horizon",
            "prediction_dt",
            "num_samples",
            "num_elites",
            "iterations",
            "cem_alpha",
            "init_std_F_tan",
            "init_std_F_rad",
            "min_std_F_tan",
            "min_std_F_rad",
            "seed",
            "warm_start",
            "violation_weights",
        ]
        solver = {key: solver[key] for key in keys if key in solver}
    items = ", ".join(f"{key}={value}" for key, value in solver.items())
    return f"- {name}: {items}"


def save_report(
    report_path: Path,
    summary_rows: list[dict[str, Any]],
    configs: dict[str, dict[str, Any]],
    commands: list[str],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 2 CEM Feasibility-First Solver Comparison Report",
        "",
        "## Code/files changed",
        "- Added/updated solver abstraction under `src/traction_mpc/mpc/solvers/`.",
        "- Updated `src/traction_mpc/mpc/solvers/cem.py` to support `selection: feasibility_first`.",
        "- Updated shared solver diagnostics for task cost and violation severity.",
        "- Updated `src/traction_mpc/mpc/fixed_mpc.py` to select solver by config.",
        "- Updated adaptive condition loading to accept top-level `mpc_overrides`.",
        "- Added `configs/spring2d_adaptive_mpc_conditions_cem.yaml`.",
        "- Added `configs/spring2d_adaptive_mpc_conditions_cem_feasfirst.yaml`.",
        "- Added `scripts/run_spring2d_solver_comparison.py`.",
        "",
        "## Scientific setup confirmation",
        "- Cost definition: unchanged; all solvers call the same `stage_cost` and `terminal_cost` callbacks.",
        "- Constraints: unchanged; all solvers call the same constraint callback and penalty.",
        "- Dynamics: unchanged; all solvers call the same Spring2D `step_dynamics` rollout callback.",
        "- Identifier: unchanged; all runs use the existing windowed least-squares identifier config.",
        "- Observation noise/bias settings: unchanged across clean/noise/noise_bias.",
        "- Physical parameters, gravity handling, and max_time were unchanged.",
        "- No safe/robust MPC, EKF/UKF, robust identifier, observation filtering, gravity compensation, or post-result tuning was added.",
        "",
        "## Selection rule change",
        "- Old CEM ranking: candidates and elites are ordered by penalized cost `J(U) + penalty(U)`.",
        "- Feasibility-first CEM ranking: candidates and elites are ordered lexicographically by `(not feasible(U), violation_score(U), task_cost(U))`.",
        "- This puts every feasible sequence ahead of every infeasible sequence; if none are feasible, the least-violating sequence is selected and task cost is only the tie-breaker.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Solver settings",
        *[_solver_settings_text(name, cfg) for name, cfg in configs.items()],
        "",
        "## Summary",
        "| solver | condition | target_reached | final theta deg | T_reach | max abs F_rad | max abs delta_r | max abs omega | max abs alpha_step | max abs F_tan | feasible decisions | mean feasible_count | max omega viol severity | max alpha viol severity | max delta_r viol severity | max F_rad viol severity | omega viol | alpha viol | done_reason | runtime s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in summary_rows:
        t_reach = row["T_reach"]
        t_text = f"{t_reach:.3f}" if np.isfinite(float(t_reach)) else "nan"
        lines.append(
            f"| {row['solver_type']} | {row['condition']} | {row['target_reached']} | "
            f"{row['final_theta_deg']:.3f} | {t_text} | {row['max_abs_F_rad']:.6g} | "
            f"{row['max_abs_delta_r']:.6g} | {row['max_abs_omega']:.6g} | "
            f"{row['max_abs_alpha_step']:.6g} | {row['max_abs_F_tan']:.6g} | "
            f"{row['feasible_mpc_decisions']}/{row['total_mpc_decisions']} | "
            f"{row['mean_feasible_count']:.3f} | {row['max_omega_violation_severity']:.6g} | "
            f"{row['max_alpha_violation_severity']:.6g} | {row['max_delta_r_violation_severity']:.6g} | "
            f"{row['max_F_rad_violation_severity']:.6g} | "
            f"{row['omega_violation_count']} | {row['alpha_violation_count']} | "
            f"{row['done_reason']} | {row['runtime_s']:.3f} |"
        )

    cem_by_condition = {row["condition"]: row for row in summary_rows if row["solver_type"] == "cem"}
    feas_by_condition = {row["condition"]: row for row in summary_rows if row["solver_type"] == "cem_feasibility_first"}
    ratio_notes = []
    theta_notes = []
    violation_notes = []
    problem_notes = []
    for condition, cem_row in cem_by_condition.items():
        feas_row = feas_by_condition.get(condition)
        if feas_row is None:
            continue
        ratio_notes.append(
            f"- {condition}: CEM {cem_row['feasible_mpc_decision_ratio']:.3f} -> "
            f"feasibility_first {feas_row['feasible_mpc_decision_ratio']:.3f}."
        )
        theta_notes.append(
            f"- {condition}: final theta {cem_row['final_theta_deg']:.3f} deg -> "
            f"{feas_row['final_theta_deg']:.3f} deg; target {cem_row['target_reached']} -> {feas_row['target_reached']}."
        )
        violation_notes.append(
            f"- {condition}: max omega severity {cem_row['max_omega_violation_severity']:.6g} -> {feas_row['max_omega_violation_severity']:.6g}; "
            f"max alpha severity {cem_row['max_alpha_violation_severity']:.6g} -> {feas_row['max_alpha_violation_severity']:.6g}; "
            f"counts omega {cem_row['omega_violation_count']} -> {feas_row['omega_violation_count']}, "
            f"alpha {cem_row['alpha_violation_count']} -> {feas_row['alpha_violation_count']}."
        )
        if condition in {"noise", "noise_bias"}:
            problem_notes.append(
                f"- {condition}: target reached CEM={cem_row['target_reached']}, feasibility_first={feas_row['target_reached']}; "
                f"feasible decisions CEM={cem_row['feasible_mpc_decisions']}/{cem_row['total_mpc_decisions']}, "
                f"feasibility_first={feas_row['feasible_mpc_decisions']}/{feas_row['total_mpc_decisions']}."
            )
        if cem_row["done_reason"] != "target_reached" or feas_row["done_reason"] != "target_reached":
            problem_notes.append(
                f"- {condition}: non-target termination observed "
                f"cem={cem_row['done_reason']}, feasibility_first={feas_row['done_reason']}."
            )

    lines.extend(
        [
            "",
            "## Short analysis",
            "Did feasibility-first CEM improve feasible decision ratio?",
            *(ratio_notes or ["- No comparable rows were available."]),
            "",
            "Did it reduce violation severity, not only violation count?",
            *(violation_notes or ["- No comparable rows were available."]),
            "",
            "Did it hurt target reaching?",
            *(theta_notes or ["- No comparable rows were available."]),
            "",
            "Did noise/noise_bias remain problematic?",
            *(problem_notes or ["- All compared runs ended by target_reached."]),
            "",
            "Bad or unexpected results were recorded as-is. No parameters were tuned after observing these outputs.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def run(
    random_config: Path,
    cem_config: Path,
    cem_feasfirst_config: Path | None,
    output_root: Path,
) -> list[dict[str, Any]]:
    configs = {
        "random_shooting": load_experiment_config(random_config),
        "cem": load_experiment_config(cem_config),
    }
    config_paths = {
        "random_shooting": random_config,
        "cem": cem_config,
    }
    if cem_feasfirst_config is not None:
        configs["cem_feasibility_first"] = load_experiment_config(cem_feasfirst_config)
        config_paths["cem_feasibility_first"] = cem_feasfirst_config
    summary_rows: list[dict[str, Any]] = []
    commands = [
        f"python scripts/run_spring2d_solver_comparison.py --random-config {random_config} --cem-config {cem_config}"
        + (f" --cem-feasfirst-config {cem_feasfirst_config}" if cem_feasfirst_config is not None else "")
        + f" --output-root {output_root}",
    ]

    for solver_type, cfg in configs.items():
        fps = int(cfg["outputs"].get("fps", 25))
        for condition_name, condition_cfg in cfg["conditions"].items():
            start = time.perf_counter()
            rows = run_condition(condition_name, condition_cfg, cfg)
            runtime_s = time.perf_counter() - start
            write_condition_csv(rows, output_root / "logs" / solver_type / condition_name / "timeseries.csv")
            save_spring2d_animation(
                rows,
                cfg["true_params"],
                output_root / "videos" / f"{solver_type}_{condition_name}.gif",
                fps=fps,
            )
            summary_rows.append(summarize_rows(solver_type, condition_name, rows, cfg, runtime_s))
        print(f"Completed {solver_type} config: {config_paths[solver_type]}")

    summary_path = output_root / "tables" / "solver_comparison_summary.csv"
    figure_path = output_root / "figures" / "solver_comparison.png"
    report_path = PROJECT_ROOT / "results" / "reports" / (
        "stage2_cem_feasfirst_report.md" if cem_feasfirst_config is not None else "stage2_cem_solver_comparison_report.md"
    )
    save_summary_table(summary_rows, summary_path)
    save_comparison_figure(summary_rows, figure_path)
    save_report(report_path, summary_rows, configs, commands)

    print("Spring2D adaptive MPC solver comparison")
    print(f"  random config : {random_config}")
    print(f"  cem config    : {cem_config}")
    if cem_feasfirst_config is not None:
        print(f"  feasfirst cfg : {cem_feasfirst_config}")
    print(f"  output root   : {output_root}")
    print(f"  summary table : {summary_path}")
    print(f"  figure        : {figure_path}")
    print(f"  report        : {report_path}")
    for row in summary_rows:
        print(
            "  "
            f"{row['solver_type']}/{row['condition']}: done={row['done_reason']}, "
            f"target_reached={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"feasible_decisions={row['feasible_mpc_decisions']}/{row['total_mpc_decisions']}, "
            f"omega_viol={row['omega_violation_count']}, "
            f"alpha_viol={row['alpha_violation_count']}"
        )
    return summary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-config", type=Path, default=DEFAULT_RANDOM_CONFIG)
    parser.add_argument("--cem-config", type=Path, default=DEFAULT_CEM_CONFIG)
    parser.add_argument("--cem-feasfirst-config", type=Path, default=DEFAULT_CEM_FEASFIRST_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    run(args.random_config, args.cem_config, args.cem_feasfirst_config, args.output_root)


if __name__ == "__main__":
    main()
