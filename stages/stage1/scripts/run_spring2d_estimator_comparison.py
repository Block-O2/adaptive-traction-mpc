"""Compare Spring2D observation estimators including UKF baselines."""

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


DEFAULT_CEM_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions_cem.yaml"
DEFAULT_CEM_FEASFIRST_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions_cem_feasfirst.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage4_ukf"


UKF_CONFIG = {
    "alpha": 0.5,
    "beta": 2.0,
    "kappa": 0.0,
    "initial_cov_diag": [0.01, 0.05, 0.001, 0.01],
    "process_noise_diag": [1.0e-5, 1.0e-3, 1.0e-6, 1.0e-4],
    "measurement_noise_diag_clean": [1.0e-8, 1.0e-8, 1.0e-8, 1.0e-8],
    "measurement_noise_diag_noise": [1.0e-4, 1.0e-3, 1.0e-5, 1.0e-4],
    "measurement_noise_diag_noise_bias": [1.0e-4, 1.0e-3, 1.0e-5, 1.0e-4],
    "covariance_jitter": 1.0e-9,
}

UKF_BIAS_CONFIG = {
    "alpha": 0.5,
    "beta": 2.0,
    "kappa": 0.0,
    "initial_state_cov_diag": [0.01, 0.05, 0.001, 0.01],
    "initial_bias_cov_diag": [1.0e-3, 1.0e-3, 1.0e-4, 1.0e-4],
    "process_noise_state_diag": [1.0e-5, 1.0e-3, 1.0e-6, 1.0e-4],
    "process_noise_bias_diag": [1.0e-7, 1.0e-7, 1.0e-8, 1.0e-8],
    "measurement_noise_diag_clean": [1.0e-8, 1.0e-8, 1.0e-8, 1.0e-8],
    "measurement_noise_diag_noise": [1.0e-4, 1.0e-3, 1.0e-5, 1.0e-4],
    "measurement_noise_diag_noise_bias": [1.0e-4, 1.0e-3, 1.0e-5, 1.0e-4],
    "covariance_jitter": 1.0e-9,
}

FILTER_CONFIGS: dict[str, dict[str, Any]] = {
    "raw": {
        "type": "raw",
        "identifier_input": "filtered",
    },
    "low_pass": {
        "type": "low_pass",
        "low_pass_lambda": 0.35,
        "identifier_input": "filtered",
    },
    "alpha_beta": {
        "type": "alpha_beta",
        "alpha_beta": {
            "theta_alpha": 0.55,
            "theta_beta": 0.08,
            "r_alpha": 0.55,
            "r_beta": 0.08,
        },
        "identifier_input": "filtered",
    },
    "ukf": {
        "type": "ukf",
        "identifier_input": "filtered",
        "ukf": UKF_CONFIG,
    },
    "ukf_bias": {
        "type": "ukf_bias",
        "identifier_input": "filtered",
        "ukf_bias": UKF_BIAS_CONFIG,
    },
    "oracle": {
        "type": "oracle",
        "identifier_input": "filtered",
        "simulation_only": True,
    },
}

PRIMARY_FILTERS = ["raw", "alpha_beta", "ukf", "ukf_bias", "oracle"]
SECONDARY_FILTERS = ["raw", "ukf", "ukf_bias", "oracle"]


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row[key]) for row in rows], dtype=float)


def _rms(rows: list[dict[str, Any]], key: str) -> float:
    values = _series(rows, key)
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite**2))) if len(finite) else np.nan


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


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0 or not np.isfinite(denominator):
        return np.nan
    return float(numerator / denominator)


def _finite_mean(rows: list[dict[str, Any]], key: str) -> float:
    values = _series(rows, key)
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if len(finite) else np.nan


def _finite_max(rows: list[dict[str, Any]], key: str) -> float:
    values = _series(rows, key)
    finite = values[np.isfinite(values)]
    return float(np.max(finite)) if len(finite) else np.nan


def summarize_rows(
    solver: str,
    filter_name: str,
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
    feasible_counts = [
        float(row["mpc_feasible_count"])
        for row in decisions
        if "mpc_feasible_count" in row and np.isfinite(float(row["mpc_feasible_count"]))
    ]
    raw_rms = {
        "theta": _rms(rows, "raw_error_theta"),
        "omega": _rms(rows, "raw_error_omega"),
        "r": _rms(rows, "raw_error_r"),
        "r_dot": _rms(rows, "raw_error_r_dot"),
    }
    filt_rms = {
        "theta": _rms(rows, "filter_error_theta"),
        "omega": _rms(rows, "filter_error_omega"),
        "r": _rms(rows, "filter_error_r"),
        "r_dot": _rms(rows, "filter_error_r_dot"),
    }
    omega_violation_severity = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_violation_severity = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    return {
        "solver": solver,
        "filter": filter_name,
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
        "total_mpc_decisions": int(len(decisions)),
        "feasible_mpc_decision_ratio": float(feasible_decisions / len(decisions)) if decisions else np.nan,
        "mean_feasible_count": float(np.mean(feasible_counts)) if feasible_counts else np.nan,
        "omega_violation_count": int(np.count_nonzero(np.abs(_series(rows, "omega")) > omega_max)),
        "alpha_violation_count": int(np.count_nonzero(np.abs(_series(rows, "alpha_step")) > alpha_max)),
        "max_omega_violation_severity": float(np.max(omega_violation_severity)),
        "max_alpha_violation_severity": float(np.max(alpha_violation_severity)),
        "rms_raw_theta": raw_rms["theta"],
        "rms_raw_omega": raw_rms["omega"],
        "rms_raw_r": raw_rms["r"],
        "rms_raw_r_dot": raw_rms["r_dot"],
        "rms_filt_theta": filt_rms["theta"],
        "rms_filt_omega": filt_rms["omega"],
        "rms_filt_r": filt_rms["r"],
        "rms_filt_r_dot": filt_rms["r_dot"],
        "rms_reduction_theta": raw_rms["theta"] - filt_rms["theta"],
        "rms_reduction_omega": raw_rms["omega"] - filt_rms["omega"],
        "rms_reduction_r": raw_rms["r"] - filt_rms["r"],
        "rms_reduction_r_dot": raw_rms["r_dot"] - filt_rms["r_dot"],
        "rms_reduction_ratio_theta": _safe_ratio(raw_rms["theta"] - filt_rms["theta"], raw_rms["theta"]),
        "rms_reduction_ratio_omega": _safe_ratio(raw_rms["omega"] - filt_rms["omega"], raw_rms["omega"]),
        "rms_reduction_ratio_r": _safe_ratio(raw_rms["r"] - filt_rms["r"], raw_rms["r"]),
        "rms_reduction_ratio_r_dot": _safe_ratio(raw_rms["r_dot"] - filt_rms["r_dot"], raw_rms["r_dot"]),
        "mean_innovation_norm": _finite_mean(rows, "innovation_norm"),
        "max_covariance_trace": _finite_max(rows, "covariance_trace"),
        "ukf_failure_count": int(sum(bool(row.get("ukf_failed", False)) for row in rows)),
        "done_reason": final.get("done_reason", ""),
        "runtime_s": float(runtime_s),
    }


def save_summary_table(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "solver",
        "filter",
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
        "mean_feasible_count",
        "omega_violation_count",
        "alpha_violation_count",
        "max_omega_violation_severity",
        "max_alpha_violation_severity",
        "rms_raw_theta",
        "rms_raw_omega",
        "rms_raw_r",
        "rms_raw_r_dot",
        "rms_filt_theta",
        "rms_filt_omega",
        "rms_filt_r",
        "rms_filt_r_dot",
        "rms_reduction_theta",
        "rms_reduction_omega",
        "rms_reduction_r",
        "rms_reduction_r_dot",
        "rms_reduction_ratio_theta",
        "rms_reduction_ratio_omega",
        "rms_reduction_ratio_r",
        "rms_reduction_ratio_r_dot",
        "mean_innovation_norm",
        "max_covariance_trace",
        "ukf_failure_count",
        "done_reason",
        "runtime_s",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_comparison_figure(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    filtered = [row for row in summary_rows if row["condition"] in {"noise", "noise_bias"}]
    labels = [f"{row['solver']}\n{row['filter']}\n{row['condition']}" for row in filtered]
    metrics = [
        ("rms_reduction_ratio_omega", "omega RMS reduction ratio"),
        ("feasible_mpc_decision_ratio", "feasible decision ratio"),
        ("max_alpha_violation_severity", "max alpha violation severity"),
        ("ukf_failure_count", "UKF failure count"),
    ]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(max(12, len(labels) * 0.62), 12), sharex=True)
    x = np.arange(len(filtered))
    for ax, (metric, ylabel) in zip(np.atleast_1d(axes), metrics):
        values = [float(row[metric]) for row in filtered]
        ax.bar(x, values)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
    axes[-1].set_xticks(x, labels, rotation=70, ha="right")
    fig.suptitle("Spring2D Adaptive MPC UKF Estimator Comparison")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 0.96))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _format_float(value: Any) -> str:
    value = float(value)
    return f"{value:.3f}" if np.isfinite(value) else "nan"


def _analysis_lines(summary_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for solver in sorted({str(row["solver"]) for row in summary_rows}):
        for condition in ["noise", "noise_bias"]:
            candidates = [
                row
                for row in summary_rows
                if row["solver"] == solver and row["condition"] == condition and row["filter"] in {"raw", "alpha_beta", "ukf", "ukf_bias"}
            ]
            if not candidates:
                continue
            best_rms = min(candidates, key=lambda row: float(row["rms_filt_omega"]))
            lines.append(
                f"- {solver}/{condition}: lowest omega filtered RMS among comparable filters was "
                f"{best_rms['filter']} ({_format_float(best_rms['rms_filt_omega'])})."
            )
    for row in summary_rows:
        if row["filter"] in {"ukf", "ukf_bias"} and int(row["ukf_failure_count"]) > 0:
            lines.append(
                f"- {row['solver']}/{row['filter']}/{row['condition']}: UKF failures logged = {row['ukf_failure_count']}."
            )
    for row in summary_rows:
        if row["condition"] == "noise_bias" and row["filter"] in {"ukf", "ukf_bias"}:
            lines.append(
                f"- {row['solver']}/{row['filter']}/noise_bias: target={row['target_reached']}, "
                f"feasible={row['feasible_mpc_decisions']}/{row['total_mpc_decisions']}, "
                f"max alpha severity={_format_float(row['max_alpha_violation_severity'])}."
            )
    return lines


def save_report(
    report_path: Path,
    summary_rows: list[dict[str, Any]],
    commands: list[str],
    primary_filters: list[str],
    secondary_filters: list[str],
    ran_secondary: bool,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 4 UKF Estimator Report",
        "",
        "## Files changed",
        "- Added `src/traction_mpc/estimation/ukf.py`.",
        "- Updated `src/traction_mpc/estimation/filters.py` for the common estimator interface and UKF factory support.",
        "- Updated `src/traction_mpc/estimation/__init__.py` exports.",
        "- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` to call estimator predict/update and log estimator diagnostics.",
        "- Added `scripts/run_spring2d_estimator_comparison.py`.",
        "",
        "## Scientific setup confirmation",
        "- Spring2D dynamics: unchanged.",
        "- MPC cost and base constraints: unchanged.",
        "- Solver algorithms: unchanged; CEM and feasibility-first CEM are selected from existing configs.",
        "- Identifier algorithm: unchanged; only input observation source is configurable as raw or filtered.",
        "- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.",
        "- No DREM, robust identifier, safe MPC, runtime safety filter, or explicit gravity compensation was added.",
        "- UKF prediction uses the current MPC/adaptive model parameters, not true physical parameters. Oracle remains the only clean-state simulation reference.",
        "",
        "## Estimator models",
        "- UKF: state `x = [theta, omega, r, r_dot]`, prediction `x_next = Phi_dt(x, u; theta_p) + w`, measurement `y = x + v`.",
        "- Bias-aware UKF: augmented state `z = [x, b]`, random-walk bias `b_next = b + w_b`, measurement `y = x + b + v`.",
        "- Bias-aware UKF estimates effective observation bias; it is not physical parameter identification.",
        "- Oracle uses the simulator true state and is simulation-only, included only as an upper-bound reference.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        f"Primary comparison: solver `cem`, filters {', '.join(primary_filters)}.",
        f"Secondary comparison: {'run' if ran_secondary else 'skipped'}, filters {', '.join(secondary_filters)}.",
        "",
        "## Summary",
        "| solver | filter | condition | target_reached | final theta deg | T_reach | feasible decisions | mean feasible_count | max omega sev | max alpha sev | RMS raw omega | RMS filt omega | omega RMS reduction | mean innovation | max cov trace | UKF failures | omega viol | alpha viol | done_reason | runtime s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['solver']} | {row['filter']} | {row['condition']} | {row['target_reached']} | "
            f"{float(row['final_theta_deg']):.3f} | {_format_float(row['T_reach'])} | "
            f"{row['feasible_mpc_decisions']}/{row['total_mpc_decisions']} | {_format_float(row['mean_feasible_count'])} | "
            f"{_format_float(row['max_omega_violation_severity'])} | {_format_float(row['max_alpha_violation_severity'])} | "
            f"{_format_float(row['rms_raw_omega'])} | {_format_float(row['rms_filt_omega'])} | "
            f"{_format_float(row['rms_reduction_omega'])} | {_format_float(row['mean_innovation_norm'])} | "
            f"{_format_float(row['max_covariance_trace'])} | {row['ukf_failure_count']} | "
            f"{row['omega_violation_count']} | {row['alpha_violation_count']} | {row['done_reason']} | "
            f"{float(row['runtime_s']):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Short analysis",
            "Did UKF reduce filtered state RMS error compared with raw and alpha-beta?",
            *_analysis_lines(summary_rows),
            "",
            "Did bias-aware UKF improve noise_bias?",
            *[
                f"- {row['solver']}/{row['filter']}/noise_bias: omega RMS reduction={_format_float(row['rms_reduction_omega'])}, "
                f"theta RMS reduction={_format_float(row['rms_reduction_theta'])}, done={row['done_reason']}."
                for row in summary_rows
                if row["condition"] == "noise_bias" and row["filter"] in {"ukf", "ukf_bias"}
            ],
            "",
            "Did UKF reduce omega/alpha violation severity or improve feasible decision ratio?",
            *[
                f"- {row['solver']}/{row['filter']}/{row['condition']}: feasible ratio={_format_float(row['feasible_mpc_decision_ratio'])}, "
                f"max omega severity={_format_float(row['max_omega_violation_severity'])}, "
                f"max alpha severity={_format_float(row['max_alpha_violation_severity'])}."
                for row in summary_rows
                if row["filter"] in {"ukf", "ukf_bias"} and row["condition"] in {"noise", "noise_bias"}
            ],
            "",
            "Did UKF hurt target reaching due to model bias or lag?",
            *[
                f"- {row['solver']}/{row['filter']}/{row['condition']}: target={row['target_reached']}, done={row['done_reason']}."
                for row in summary_rows
                if row["filter"] in {"ukf", "ukf_bias"} and not bool(row["target_reached"])
            ],
            "",
            "Did any UKF failure occur?",
            *[
                f"- {row['solver']}/{row['filter']}/{row['condition']}: failures={row['ukf_failure_count']}."
                for row in summary_rows
                if row["filter"] in {"ukf", "ukf_bias"}
            ],
            "",
            "Bad or mixed results were recorded as-is. No parameters were tuned after observing outputs.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def should_save_video(solver_name: str, filter_name: str, condition: str) -> bool:
    del solver_name
    return condition == "noise_bias" and filter_name in {"raw", "ukf", "ukf_bias", "oracle"}


def run(
    cem_config: Path,
    cem_feasfirst_config: Path,
    output_root: Path,
    primary_filters: list[str],
    secondary_filters: list[str],
    run_secondary: bool,
) -> list[dict[str, Any]]:
    solver_configs = {
        "cem": load_experiment_config(cem_config),
        "cem_feasibility_first": load_experiment_config(cem_feasfirst_config),
    }
    matrix: list[tuple[str, list[str]]] = [("cem", primary_filters)]
    if run_secondary:
        matrix.append(("cem_feasibility_first", secondary_filters))

    summary_rows: list[dict[str, Any]] = []
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_estimator_comparison.py",
    ]
    for solver_name, filter_names in matrix:
        base_cfg = solver_configs[solver_name]
        for filter_name in filter_names:
            filter_cfg = FILTER_CONFIGS[filter_name]
            cfg = dict(base_cfg)
            cfg["observation_filter"] = dict(filter_cfg)
            for condition_name, condition_cfg in cfg["conditions"].items():
                start = time.perf_counter()
                rows = run_condition(condition_name, condition_cfg, cfg)
                runtime_s = time.perf_counter() - start
                log_path = output_root / "logs" / solver_name / filter_name / condition_name / "timeseries.csv"
                write_condition_csv(rows, log_path)
                if should_save_video(solver_name, filter_name, condition_name):
                    save_spring2d_animation(
                        rows,
                        cfg["true_params"],
                        output_root / "videos" / f"{solver_name}_{filter_name}_{condition_name}.gif",
                        fps=int(cfg["outputs"].get("fps", 25)),
                    )
                summary_rows.append(summarize_rows(solver_name, filter_name, condition_name, rows, cfg, runtime_s))
            print(f"Completed solver={solver_name}, filter={filter_name}")

    summary_path = output_root / "tables" / "ukf_summary.csv"
    figure_path = output_root / "figures" / "ukf_comparison.png"
    report_path = PROJECT_ROOT / "results" / "reports" / "stage4_ukf_estimator_report.md"
    save_summary_table(summary_rows, summary_path)
    save_comparison_figure(summary_rows, figure_path)
    save_report(report_path, summary_rows, commands, primary_filters, secondary_filters, run_secondary)

    print("Spring2D adaptive MPC UKF estimator comparison")
    print(f"  output root   : {output_root}")
    print(f"  summary table : {summary_path}")
    print(f"  figure        : {figure_path}")
    print(f"  report        : {report_path}")
    for row in summary_rows:
        print(
            "  "
            f"{row['solver']}/{row['filter']}/{row['condition']}: "
            f"done={row['done_reason']}, target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"feasible={row['feasible_mpc_decisions']}/{row['total_mpc_decisions']}, "
            f"omega_viol={row['omega_violation_count']}, "
            f"alpha_viol={row['alpha_violation_count']}, "
            f"ukf_failures={row['ukf_failure_count']}"
        )
    return summary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cem-config", type=Path, default=DEFAULT_CEM_CONFIG)
    parser.add_argument("--cem-feasfirst-config", type=Path, default=DEFAULT_CEM_FEASFIRST_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--primary-filters", nargs="+", default=PRIMARY_FILTERS, choices=list(FILTER_CONFIGS.keys()))
    parser.add_argument("--secondary-filters", nargs="+", default=SECONDARY_FILTERS, choices=list(FILTER_CONFIGS.keys()))
    parser.add_argument("--skip-secondary", action="store_true")
    args = parser.parse_args()
    run(
        args.cem_config,
        args.cem_feasfirst_config,
        args.output_root,
        args.primary_filters,
        args.secondary_filters,
        run_secondary=not args.skip_secondary,
    )


if __name__ == "__main__":
    main()
