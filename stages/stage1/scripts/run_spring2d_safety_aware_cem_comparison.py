"""Compare safety-aware CEM modes for Spring2D adaptive MPC."""

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
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE, SAFETY_FILTER_CONFIG


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage7a_safety_aware_cem"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise", "noise_bias"]
METHODS: dict[str, dict[str, Any]] = {
    "baseline_cem": {
        "solver_safety_mode": "off",
        "runtime_filter": {"enabled": False},
    },
    "runtime_filter_old": {
        "solver_safety_mode": "off",
        "runtime_filter": dict(SAFETY_FILTER_CONFIG),
    },
    "cem_soft_penalty": {
        "solver_safety_mode": "soft_penalty",
        "runtime_filter": {"enabled": False},
    },
    "cem_feasibility_first": {
        "solver_safety_mode": "feasibility_first",
        "runtime_filter": {"enabled": False},
    },
    "cem_lexicographic": {
        "solver_safety_mode": "lexicographic",
        "runtime_filter": {"enabled": False},
    },
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


def _safe_ratio(num: float, denom: float) -> float:
    if denom <= 0.0 or not np.isfinite(denom):
        return np.nan
    return float(num / denom)


def _normalize(value: float, limit: float) -> float:
    if limit <= 0.0:
        return float("inf") if value > 0.0 else 0.0
    return float(value / limit)


def add_executed_safety_fields(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = cfg["mpc_params"].get("constraints", {})
    true_params = cfg["true_params"]
    limits = {
        "F_tan": float(constraints.get("F_tan_max", true_params["F_tan_max"])),
        "F_rad": float(constraints.get("F_rad_max", true_params["F_rad_max"])),
        "delta_r": float(constraints.get("delta_r_max", true_params["delta_r_max"])),
        "omega": float(constraints.get("omega_max", true_params["omega_max"])),
        "alpha": float(constraints.get("alpha_max", true_params.get("alpha_max", np.inf))),
    }
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        raw = {
            "F_tan": max(0.0, abs(float(row.get("F_tan", 0.0))) - limits["F_tan"]),
            "F_rad": max(0.0, abs(float(row.get("F_rad", 0.0))) - limits["F_rad"]),
            "delta_r": max(0.0, abs(float(row.get("delta_r", 0.0))) - limits["delta_r"]),
            "omega": max(0.0, abs(float(row.get("omega", 0.0))) - limits["omega"]),
            "alpha": max(0.0, abs(float(row.get("alpha_step", 0.0))) - limits["alpha"]),
        }
        normalized = {name: _normalize(value, limits[name]) for name, value in raw.items()}
        total = float(sum(value**2 for value in normalized.values()))
        enriched.update(
            {
                "executed_safety_violation_F_tan": float(raw["F_tan"]),
                "executed_safety_violation_F_rad": float(raw["F_rad"]),
                "executed_safety_violation_delta_r": float(raw["delta_r"]),
                "executed_safety_violation_omega": float(raw["omega"]),
                "executed_safety_violation_alpha": float(raw["alpha"]),
                "executed_normalized_violation_F_tan": float(normalized["F_tan"]),
                "executed_normalized_violation_F_rad": float(normalized["F_rad"]),
                "executed_normalized_violation_delta_r": float(normalized["delta_r"]),
                "executed_normalized_violation_omega": float(normalized["omega"]),
                "executed_normalized_violation_alpha": float(normalized["alpha"]),
                "executed_total_normalized_safety_violation": total,
            }
        )
        enriched_rows.append(enriched)
    return enriched_rows


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(mask) < 2:
        return np.nan
    x_valid = x[mask]
    y_valid = y[mask]
    if np.std(x_valid) <= 0.0 or np.std(y_valid) <= 0.0:
        return np.nan
    return float(np.corrcoef(x_valid, y_valid)[0, 1])


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
    feasible_decisions = sum(bool(row.get("mpc_result_feasible", False)) for row in decisions)
    action = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(action, axis=1)
    action_smoothness = np.linalg.norm(np.diff(action, axis=0), axis=1) if len(action) > 1 else np.array([])
    omega_sev = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_sev = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    delta_r_sev = np.maximum(0.0, np.abs(_series(rows, "delta_r")) - delta_r_max)
    F_tan_sev = np.maximum(0.0, np.abs(_series(rows, "F_tan")) - F_tan_max)
    F_rad_sev = np.maximum(0.0, np.abs(_series(rows, "F_rad")) - F_rad_max)
    predicted = _series(rows, "cem_selected_total_normalized_violation")
    executed = _series(rows, "executed_total_normalized_safety_violation")
    return {
        "method": method,
        "condition": condition,
        "solver_safety_mode": str(final.get("cem_safety_mode", "")),
        "runtime_filter_enabled": bool(final.get("safety_filter_active", False) or method == "runtime_filter_old"),
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": final.get("done_reason", ""),
        "feasible_mpc_decisions": int(feasible_decisions),
        "total_mpc_decisions": int(len(decisions)),
        "feasible_ratio": _safe_ratio(feasible_decisions, len(decisions)),
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
        "mean_cem_predicted_total_safety_violation": _finite_mean(predicted),
        "max_cem_predicted_total_safety_violation": _finite_max(predicted),
        "mean_executed_true_total_safety_violation": _finite_mean(executed),
        "max_executed_true_total_safety_violation": _finite_max(executed),
        "predicted_executed_safety_corr": _correlation(predicted, executed),
        "mean_cem_selected_alpha_norm_violation": _finite_mean(_series(rows, "cem_selected_mean_norm_violation_alpha")),
        "mean_cem_selected_omega_norm_violation": _finite_mean(_series(rows, "cem_selected_mean_norm_violation_omega")),
        "runtime_s": float(runtime_s),
    }


SUMMARY_FIELDS = [
    "method",
    "condition",
    "solver_safety_mode",
    "runtime_filter_enabled",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "feasible_mpc_decisions",
    "total_mpc_decisions",
    "feasible_ratio",
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
    "mean_cem_predicted_total_safety_violation",
    "max_cem_predicted_total_safety_violation",
    "mean_executed_true_total_safety_violation",
    "max_executed_true_total_safety_violation",
    "predicted_executed_safety_corr",
    "mean_cem_selected_alpha_norm_violation",
    "mean_cem_selected_omega_norm_violation",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def configure_run(base_cfg: dict[str, Any], method_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = copy.deepcopy(method_cfg["runtime_filter"])
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = method_cfg["solver_safety_mode"]
    solver.setdefault("safety_penalty_weight", 1.0)
    solver.setdefault(
        "safety_violation_weights",
        {"F_tan": 1.0, "F_rad": 1.0, "delta_r": 1.0, "omega": 1.0, "alpha": 1.0},
    )
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    return cfg


def save_condition_figure(condition: str, method_rows: dict[str, list[dict[str, Any]]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(6, 1, figsize=(13, 17), sharex=True)
    for method, rows in method_rows.items():
        t = _series(rows, "t")
        axes[0].plot(t, np.degrees(_series(rows, "theta")), label=method)
        axes[1].plot(t, _series(rows, "omega"), label=method)
        axes[2].plot(t, _series(rows, "alpha_step"), label=method)
        axes[3].plot(t, _series(rows, "F_tan"), label=f"{method} F_tan")
        axes[3].plot(t, _series(rows, "F_rad"), linestyle="--", label=f"{method} F_rad")
        axes[4].plot(t, _series(rows, "cem_selected_total_normalized_violation"), label=f"{method} predicted")
        axes[4].plot(t, _series(rows, "executed_total_normalized_safety_violation"), linestyle="--", label=f"{method} executed")
        axes[5].plot(t, _series(rows, "cem_best_safety_score"), label=method)
    titles = [
        "theta trajectory",
        "omega trajectory",
        "alpha trajectory",
        "executed F_tan and F_rad",
        "predicted vs executed normalized safety violation",
        "CEM selected trajectory safety cost",
    ]
    ylabels = ["theta [deg]", "omega", "alpha", "force", "safety violation", "CEM safety cost"]
    for ax, title, ylabel in zip(axes, titles, ylabels):
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
    axes[-1].set_xlabel("time [s]")
    fig.suptitle(f"Stage 7A safety-aware CEM: {condition}")
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.98))
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.3f}" if np.isfinite(value) else "nan"


def _method_condition(summary_rows: list[dict[str, Any]], method: str, condition: str) -> dict[str, Any]:
    return next(row for row in summary_rows if row["method"] == method and row["condition"] == condition)


def _best_by_condition(summary_rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    candidates = [
        row
        for row in summary_rows
        if row["condition"] == condition and row["method"] in {"cem_soft_penalty", "cem_feasibility_first", "cem_lexicographic"}
    ]
    return min(
        candidates,
        key=lambda row: (
            not bool(row["target_reached"]),
            int(row["alpha_violation_count"]) + int(row["omega_violation_count"]),
            float(row["alpha_max_severity"]) + float(row["omega_max_severity"]),
            -float(row["final_theta_deg"]),
        ),
    )


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    report_path = output_root / "stage7a_report.md"
    lines = [
        "# Stage 7A Safety-Aware CEM-MPC Report",
        "",
        "## Scope",
        "- Added optional CEM `safety_mode` values: `off`, `soft_penalty`, `feasibility_first`, and `lexicographic`.",
        "- Safety-aware modes compute horizon-level normalized violations for F_tan, F_rad, delta_r, omega, and alpha during CEM rollout.",
        "- `alpha_k = (omega_{k+1} - omega_k) / control_dt`; this is computed at each predicted transition.",
        "- Runtime one-step filter behavior remains available and unchanged.",
        "- Spring2D dynamics, UKF/UKF-bias, Windowed NLS identifier, estimator/identifier data flow, MPC task cost, base constraints, physical parameters, gravity, max_time, and noise/bias settings were unchanged.",
        "- No post-result manual tuning was performed. This is not a formal safety guarantee.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Summary",
        "| method | condition | target | final theta deg | T_reach | done | feasible ratio | omega viol | omega max sev | alpha viol | alpha max sev | delta_r viol | F_tan/F_rad viol | mean action | smoothness | pred safety mean | executed safety mean | pred/exe corr | runtime s |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['method']} | {row['condition']} | {row['target_reached']} | "
            f"{_fmt(row['final_theta_deg'])} | {_fmt(row['T_reach'])} | {row['done_reason']} | "
            f"{_fmt(row['feasible_ratio'])} | {row['omega_violation_count']} | {_fmt(row['omega_max_severity'])} | "
            f"{row['alpha_violation_count']} | {_fmt(row['alpha_max_severity'])} | {row['delta_r_violation_count']} | "
            f"{row['F_tan_violation_count']}/{row['F_rad_violation_count']} | {_fmt(row['mean_action_magnitude'])} | "
            f"{_fmt(row['action_smoothness'])} | {_fmt(row['mean_cem_predicted_total_safety_violation'])} | "
            f"{_fmt(row['mean_executed_true_total_safety_violation'])} | {_fmt(row['predicted_executed_safety_corr'])} | "
            f"{_fmt(row['runtime_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Does moving safety into CEM restore target reaching compared with one-step filter?",
            *[
                f"- {condition}: runtime filter target={_method_condition(summary_rows, 'runtime_filter_old', condition)['target_reached']}; "
                f"best safety-aware mode={_best_by_condition(summary_rows, condition)['method']} target={_best_by_condition(summary_rows, condition)['target_reached']} "
                f"final theta={_fmt(_best_by_condition(summary_rows, condition)['final_theta_deg'])} deg."
                for condition in CONDITIONS
            ],
            "",
            "2. Does it reduce omega/alpha violation count or severity compared with baseline?",
            *[
                f"- {condition}: baseline omega/alpha counts="
                f"{_method_condition(summary_rows, 'baseline_cem', condition)['omega_violation_count']}/"
                f"{_method_condition(summary_rows, 'baseline_cem', condition)['alpha_violation_count']}; "
                f"best safety-aware counts={_best_by_condition(summary_rows, condition)['omega_violation_count']}/"
                f"{_best_by_condition(summary_rows, condition)['alpha_violation_count']}."
                for condition in CONDITIONS
            ],
            "",
            "3. Which mode is best: soft_penalty, feasibility_first, or lexicographic?",
            *[
                f"- {condition}: {_best_by_condition(summary_rows, condition)['method']} by target-reaching first, then omega/alpha violations and severity."
                for condition in CONDITIONS
            ],
            "",
            "4. Does safety-aware CEM become too conservative?",
            *[
                f"- {row['method']}/{row['condition']}: target={row['target_reached']}, final theta={_fmt(row['final_theta_deg'])} deg, mean action={_fmt(row['mean_action_magnitude'])}."
                for row in summary_rows
                if row["method"] in {"cem_soft_penalty", "cem_feasibility_first", "cem_lexicographic"}
            ],
            "",
            "5. Does predicted safety correlate with executed safety?",
            *[
                f"- {row['method']}/{row['condition']}: correlation={_fmt(row['predicted_executed_safety_corr'])}, "
                f"predicted mean={_fmt(row['mean_cem_predicted_total_safety_violation'])}, executed mean={_fmt(row['mean_executed_true_total_safety_violation'])}."
                for row in summary_rows
            ],
            "",
            "6. Should the next step be adaptive tightening, PSF/gatekeeper-lite, or progress governor?",
            "- If Stage 7A improves target reaching while reducing violations, the next step is adaptive tightening around the safety-aware CEM. If it remains conservative or poorly correlated with execution, a PSF/gatekeeper-lite or progress governor is the next lower-risk layer before changing constraints. Constraint tuning is not recommended without explicit approval because it changes the task definition.",
            "",
            "Bad or mixed results are reported as-is.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_safety_aware_cem_comparison.py",
    ]
    summary_rows: list[dict[str, Any]] = []
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for method, method_cfg in METHODS.items():
        cfg = configure_run(base_cfg, method_cfg)
        for condition in CONDITIONS:
            start = time.perf_counter()
            rows = run_condition(condition, cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            rows = add_executed_safety_fields(rows, cfg)
            all_rows[(method, condition)] = rows
            write_condition_csv(rows, output_root / "logs" / method / condition / "timeseries.csv")
            summary_rows.append(summarize_rows(method, condition, rows, cfg, runtime_s))
            print(f"Completed method={method}, condition={condition}")

    save_summary(summary_rows, output_root / "stage7a_summary.csv")
    for condition in CONDITIONS:
        save_condition_figure(
            condition,
            {method: all_rows[(method, condition)] for method in METHODS},
            output_root / "figs" / f"{condition}_safety_aware_cem.png",
        )
    save_report(summary_rows, output_root, commands)

    print("Stage 7A safety-aware CEM comparison")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage7a_summary.csv'}")
    print(f"  report      : {output_root / 'stage7a_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['method']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"omega_viol={row['omega_violation_count']}, alpha_viol={row['alpha_violation_count']}, "
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
