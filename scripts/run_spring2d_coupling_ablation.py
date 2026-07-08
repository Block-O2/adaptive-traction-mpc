"""Run estimator-identifier coupling ablations for Spring2D adaptive MPC."""

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
from run_spring2d_estimator_comparison import FILTER_CONFIGS
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_estimator_identifier_coupling.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage5_coupling"


COUPLING_CASES: dict[str, dict[str, str]] = {
    "case_A_current_adaptive": {
        "name": "case_A_current_adaptive",
        "mpc_state_input": "filtered",
        "identifier_input": "filtered",
        "identifier_mode": "adaptive",
        "estimator_model_params_source": "adaptive",
        "mpc_model_params_source": "adaptive",
    },
    "case_B_mpc_only_raw_identifier": {
        "name": "case_B_mpc_only_raw_identifier",
        "mpc_state_input": "filtered",
        "identifier_input": "raw",
        "identifier_mode": "adaptive",
        "estimator_model_params_source": "adaptive",
        "mpc_model_params_source": "adaptive",
    },
    "case_C_frozen_identifier": {
        "name": "case_C_frozen_identifier",
        "mpc_state_input": "filtered",
        "identifier_input": "none",
        "identifier_mode": "frozen",
        "estimator_model_params_source": "initial",
        "mpc_model_params_source": "initial",
    },
    "case_D_frozen_estimator_model": {
        "name": "case_D_frozen_estimator_model",
        "mpc_state_input": "filtered",
        "identifier_input": "filtered",
        "identifier_mode": "adaptive",
        "estimator_model_params_source": "initial",
        "mpc_model_params_source": "adaptive",
    },
    "case_E_oracle_identifier": {
        "name": "case_E_oracle_identifier",
        "mpc_state_input": "filtered",
        "identifier_input": "oracle_true_state",
        "identifier_mode": "adaptive",
        "estimator_model_params_source": "adaptive",
        "mpc_model_params_source": "adaptive",
    },
}


REFERENCE_RUNS: dict[str, tuple[str, dict[str, str]]] = {
    "ref_raw_adaptive": (
        "raw",
        {
            "name": "ref_raw_adaptive",
            "mpc_state_input": "filtered",
            "identifier_input": "filtered",
            "identifier_mode": "adaptive",
            "estimator_model_params_source": "adaptive",
            "mpc_model_params_source": "adaptive",
        },
    ),
    "ref_oracle_state": (
        "oracle",
        {
            "name": "ref_oracle_state",
            "mpc_state_input": "filtered",
            "identifier_input": "filtered",
            "identifier_mode": "adaptive",
            "estimator_model_params_source": "adaptive",
            "mpc_model_params_source": "adaptive",
        },
    ),
}


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row.get(key, np.nan)) for row in rows], dtype=float)


def _bool_series(rows: list[dict[str, Any]], key: str) -> list[bool]:
    return [bool(row.get(key, False)) for row in rows]


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def _rms(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.sqrt(np.mean(values**2))) if len(values) else np.nan


def _finite_mean(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.mean(values)) if len(values) else np.nan


def _finite_max(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.max(values)) if len(values) else np.nan


def _finite_std(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.std(values)) if len(values) else np.nan


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


def _true_bias(condition_cfg: dict[str, Any]) -> np.ndarray:
    noise = condition_cfg.get("observation_noise", {})
    return np.array(
        [
            float(noise.get("theta_bias", 0.0)),
            float(noise.get("omega_bias", 0.0)),
            float(noise.get("r_bias", 0.0)),
            float(noise.get("r_dot_bias", 0.0)),
        ],
        dtype=float,
    )


def summarize_rows(
    solver: str,
    filter_name: str,
    case_name: str,
    condition: str,
    condition_cfg: dict[str, Any],
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
    bias_hat = np.array(
        [
            float(final.get("bias_theta_hat", np.nan)),
            float(final.get("bias_omega_hat", np.nan)),
            float(final.get("bias_r_hat", np.nan)),
            float(final.get("bias_r_dot_hat", np.nan)),
        ],
        dtype=float,
    )
    bias_errors = np.vstack(
        [
            _series(rows, "bias_theta_hat") - _true_bias(condition_cfg)[0],
            _series(rows, "bias_omega_hat") - _true_bias(condition_cfg)[1],
            _series(rows, "bias_r_hat") - _true_bias(condition_cfg)[2],
            _series(rows, "bias_r_dot_hat") - _true_bias(condition_cfg)[3],
        ]
    )
    bias_rms_error = [
        float(np.sqrt(np.mean(vals[np.isfinite(vals)] ** 2))) if len(vals[np.isfinite(vals)]) else np.nan
        for vals in bias_errors
    ]
    return {
        "solver": solver,
        "filter": filter_name,
        "case": case_name,
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": final.get("done_reason", ""),
        "runtime_s": float(runtime_s),
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
        "ukf_failure_count": int(sum(_bool_series(rows, "ukf_failed"))),
        "final_bias_theta_hat": float(bias_hat[0]),
        "final_bias_omega_hat": float(bias_hat[1]),
        "final_bias_r_hat": float(bias_hat[2]),
        "final_bias_r_dot_hat": float(bias_hat[3]),
        "rms_bias_error_theta": bias_rms_error[0],
        "rms_bias_error_omega": bias_rms_error[1],
        "rms_bias_error_r": bias_rms_error[2],
        "rms_bias_error_r_dot": bias_rms_error[3],
        "final_m_hat": float(final.get("m_hat", np.nan)),
        "final_k_hat": float(final.get("k_hat", np.nan)),
        "final_b_r_hat": float(final.get("b_r_hat", np.nan)),
        "mean_m_hat": _finite_mean(rows, "m_hat"),
        "mean_k_hat": _finite_mean(rows, "k_hat"),
        "mean_b_r_hat": _finite_mean(rows, "b_r_hat"),
        "std_m_hat": _finite_std(rows, "m_hat"),
        "std_k_hat": _finite_std(rows, "k_hat"),
        "std_b_r_hat": _finite_std(rows, "b_r_hat"),
        "total_parameter_update_count": int(final.get("parameter_update_count", 0)),
        "mean_parameter_step_norm": _finite_mean(rows, "parameter_step_norm"),
        "max_parameter_step_norm": _finite_max(rows, "parameter_step_norm"),
        "bound_hit_count": int(sum(_bool_series(rows, "parameter_bound_hit"))),
        "mean_nls_residual": _finite_mean(rows, "nls_residual"),
        "mean_prediction_error": _finite_mean(rows, "prediction_error"),
    }


SUMMARY_FIELDS = [
    "solver",
    "filter",
    "case",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "runtime_s",
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
    "final_bias_theta_hat",
    "final_bias_omega_hat",
    "final_bias_r_hat",
    "final_bias_r_dot_hat",
    "rms_bias_error_theta",
    "rms_bias_error_omega",
    "rms_bias_error_r",
    "rms_bias_error_r_dot",
    "final_m_hat",
    "final_k_hat",
    "final_b_r_hat",
    "mean_m_hat",
    "mean_k_hat",
    "mean_b_r_hat",
    "std_m_hat",
    "std_k_hat",
    "std_b_r_hat",
    "total_parameter_update_count",
    "mean_parameter_step_norm",
    "max_parameter_step_norm",
    "bound_hit_count",
    "mean_nls_residual",
    "mean_prediction_error",
]


def save_summary_table(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_comparison_figure(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    filtered = [row for row in summary_rows if row["condition"] == "noise_bias"]
    labels = [f"{row['filter']}\n{row['case'].replace('case_', '')}" for row in filtered]
    metrics = [
        ("feasible_mpc_decision_ratio", "feasible ratio"),
        ("max_alpha_violation_severity", "max alpha severity"),
        ("rms_reduction_ratio_omega", "omega RMS reduction ratio"),
        ("total_parameter_update_count", "parameter updates"),
    ]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(max(14, len(labels) * 0.55), 12), sharex=True)
    x = np.arange(len(filtered))
    for ax, (metric, ylabel) in zip(np.atleast_1d(axes), metrics):
        ax.bar(x, [float(row[metric]) for row in filtered])
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
    axes[-1].set_xticks(x, labels, rotation=75, ha="right")
    fig.suptitle("Spring2D Estimator-Identifier Coupling Ablation (noise_bias)")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 0.96))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def save_diagnostic_plot(
    rows: list[dict[str, Any]],
    output_path: Path,
    title: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    t = _series(rows, "t")
    fig, axes = plt.subplots(6, 1, figsize=(12, 14), sharex=True)
    axes[0].plot(t, np.degrees(_series(rows, "theta")), label="theta deg")
    axes[0].plot(t, _series(rows, "omega"), label="omega")
    axes[0].plot(t, _series(rows, "alpha_step"), label="alpha_step")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(t, _series(rows, "true_omega"), label="true omega")
    axes[1].plot(t, _series(rows, "obs_omega"), label="obs omega", alpha=0.7)
    axes[1].plot(t, _series(rows, "filt_omega"), label="filtered omega", alpha=0.8)
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(t, _series(rows, "m_hat"), label="m_hat")
    axes[2].plot(t, _series(rows, "k_hat"), label="k_hat")
    axes[2].plot(t, _series(rows, "b_r_hat"), label="b_r_hat")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.25)

    axes[3].plot(t, _series(rows, "innovation_norm"), label="innovation_norm")
    axes[3].plot(t, _series(rows, "covariance_trace"), label="covariance_trace")
    axes[3].legend(loc="best")
    axes[3].grid(True, alpha=0.25)

    axes[4].plot(t, _series(rows, "bias_theta_hat"), label="bias theta")
    axes[4].plot(t, _series(rows, "bias_omega_hat"), label="bias omega")
    axes[4].plot(t, _series(rows, "bias_r_hat"), label="bias r")
    axes[4].plot(t, _series(rows, "bias_r_dot_hat"), label="bias r_dot")
    axes[4].legend(loc="best")
    axes[4].grid(True, alpha=0.25)

    axes[5].plot(t, _series(rows, "mpc_feasible_count"), label="feasible_count")
    axes[5].plot(t, _series(rows, "parameter_step_norm"), label="parameter_step_norm")
    axes[5].legend(loc="best")
    axes[5].grid(True, alpha=0.25)
    axes[5].set_xlabel("time [s]")
    fig.suptitle(title)
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 0.97))
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _format_float(value: Any) -> str:
    value = float(value)
    return f"{value:.3f}" if np.isfinite(value) else "nan"


def _lookup(summary_rows: list[dict[str, Any]], filter_name: str, case_name: str, condition: str) -> dict[str, Any] | None:
    for row in summary_rows:
        if row["filter"] == filter_name and row["case"] == case_name and row["condition"] == condition:
            return row
    return None


def save_report(report_path: Path, summary_rows: list[dict[str, Any]], commands: list[str]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 5 Estimator-Identifier Coupling Report",
        "",
        "## Files changed",
        "- Added `configs/spring2d_estimator_identifier_coupling.yaml`.",
        "- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` with backward-compatible coupling-ablation controls.",
        "- Added `scripts/run_spring2d_coupling_ablation.py`.",
        "",
        "## Scientific setup confirmation",
        "- Spring2D dynamics: unchanged.",
        "- MPC cost and base constraints: unchanged.",
        "- CEM solver algorithm: unchanged.",
        "- UKF/UKF-bias algorithm: unchanged.",
        "- Windowed NLS identifier algorithm: unchanged; only input source and update application are ablated.",
        "- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.",
        "- No DREM, robust identifier, EKF, safe MPC, runtime safety filter, or explicit gravity compensation was added.",
        "",
        "## Coupling cases",
        "- Case A: filtered state to MPC and identifier, adaptive identifier updates MPC, UKF uses adaptive model parameters.",
        "- Case B: filtered state to MPC, raw state to identifier, adaptive identifier updates MPC, UKF uses adaptive model parameters.",
        "- Case C: filtered state to MPC, identifier input none, identifier frozen, UKF and MPC use initial model parameters.",
        "- Case D: filtered state to MPC and identifier, adaptive identifier updates MPC, UKF uses initial model parameters.",
        "- Case E: filtered state to MPC, oracle true state to identifier, adaptive identifier updates MPC. This is simulation-only.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Summary",
        "| filter | case | condition | target | final theta deg | T_reach | feasible | max omega sev | max alpha sev | RMS filt omega | updates | max param step | final m | final k | final b_r | UKF fail | done | runtime s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['filter']} | {row['case']} | {row['condition']} | {row['target_reached']} | "
            f"{_format_float(row['final_theta_deg'])} | {_format_float(row['T_reach'])} | "
            f"{row['feasible_mpc_decisions']}/{row['total_mpc_decisions']} | "
            f"{_format_float(row['max_omega_violation_severity'])} | {_format_float(row['max_alpha_violation_severity'])} | "
            f"{_format_float(row['rms_filt_omega'])} | {row['total_parameter_update_count']} | "
            f"{_format_float(row['max_parameter_step_norm'])} | {_format_float(row['final_m_hat'])} | "
            f"{_format_float(row['final_k_hat'])} | {_format_float(row['final_b_r_hat'])} | "
            f"{row['ukf_failure_count']} | {row['done_reason']} | {_format_float(row['runtime_s'])} |"
        )

    def compare_lines(filter_name: str, condition: str, left: str, right: str, metric: str, label: str) -> list[str]:
        a = _lookup(summary_rows, filter_name, left, condition)
        b = _lookup(summary_rows, filter_name, right, condition)
        if a is None or b is None:
            return []
        return [
            f"- {filter_name}/{condition}: {label} {left}={_format_float(a[metric])}, {right}={_format_float(b[metric])}."
        ]

    analysis = []
    for filter_name in ["ukf", "ukf_bias"]:
        for condition in ["noise", "noise_bias"]:
            analysis.extend(
                compare_lines(
                    filter_name,
                    condition,
                    "case_A_current_adaptive",
                    "case_B_mpc_only_raw_identifier",
                    "feasible_mpc_decision_ratio",
                    "filtered-vs-raw identifier feasible ratio",
                )
            )
            analysis.extend(
                compare_lines(
                    filter_name,
                    condition,
                    "case_A_current_adaptive",
                    "case_C_frozen_identifier",
                    "max_alpha_violation_severity",
                    "adaptive-vs-frozen identifier max alpha severity",
                )
            )
            analysis.extend(
                compare_lines(
                    filter_name,
                    condition,
                    "case_A_current_adaptive",
                    "case_D_frozen_estimator_model",
                    "max_covariance_trace",
                    "adaptive-vs-frozen estimator covariance trace",
                )
            )
            analysis.extend(
                compare_lines(
                    filter_name,
                    condition,
                    "case_A_current_adaptive",
                    "case_E_oracle_identifier",
                    "mean_prediction_error",
                    "filtered-vs-oracle identifier prediction error",
                )
            )

    high_jump_rows = [
        row
        for row in summary_rows
        if np.isfinite(float(row["max_parameter_step_norm"])) and float(row["max_parameter_step_norm"]) > 50.0
    ]
    lines.extend(
        [
            "",
            "## Short analysis",
            "Does giving filtered UKF state to the identifier help or hurt compared with raw identifier input?",
            *(analysis or ["- See summary table; no pairwise rows were available."]),
            "",
            "Does freezing the identifier improve stability or hurt adaptation?",
            *[
                f"- {row['filter']}/{row['condition']}: frozen identifier target={row['target_reached']}, "
                f"feasible={row['feasible_mpc_decisions']}/{row['total_mpc_decisions']}, done={row['done_reason']}."
                for row in summary_rows
                if row["case"] == "case_C_frozen_identifier"
            ],
            "",
            "Does oracle identifier input improve parameter estimates or closed-loop behavior?",
            *[
                f"- {row['filter']}/{row['condition']}: oracle-identifier final theta={_format_float(row['final_theta_deg'])}, "
                f"final params=({_format_float(row['final_m_hat'])}, {_format_float(row['final_k_hat'])}, {_format_float(row['final_b_r_hat'])}), "
                f"target={row['target_reached']}."
                for row in summary_rows
                if row["case"] == "case_E_oracle_identifier"
            ],
            "",
            "Are UKF-bias target gains coming from better bias estimation or different controller behavior?",
            *[
                f"- ukf_bias/{row['case']}/{row['condition']}: final bias=({_format_float(row['final_bias_theta_hat'])}, "
                f"{_format_float(row['final_bias_omega_hat'])}, {_format_float(row['final_bias_r_hat'])}, "
                f"{_format_float(row['final_bias_r_dot_hat'])}), target={row['target_reached']}, feasible ratio={_format_float(row['feasible_mpc_decision_ratio'])}."
                for row in summary_rows
                if row["filter"] == "ukf_bias" and row["condition"] == "noise_bias"
            ],
            "",
            "Are parameter jumps correlated with innovation spikes, action jumps, or alpha violations?",
            *(
                [
                f"- {row['filter']}/{row['case']}/{row['condition']}: max parameter step={_format_float(row['max_parameter_step_norm'])}, "
                f"mean innovation={_format_float(row['mean_innovation_norm'])}, max alpha severity={_format_float(row['max_alpha_violation_severity'])}."
                for row in high_jump_rows[:12]
                ]
                or ["- No rows exceeded the report threshold for large parameter-step norm."]
            ),
            "",
            "Does estimator quality translate into lower alpha/omega violation, or are violations dominated by MPC constraints?",
            *[
                f"- {row['filter']}/{row['case']}/{row['condition']}: RMS omega reduction={_format_float(row['rms_reduction_omega'])}, "
                f"omega severity={_format_float(row['max_omega_violation_severity'])}, alpha severity={_format_float(row['max_alpha_violation_severity'])}."
                for row in summary_rows
                if row["condition"] == "noise_bias"
            ],
            "",
            "Bad or mixed results were recorded as-is. No parameters were tuned after observing outputs.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def should_save_video(filter_name: str, case_name: str, condition: str) -> bool:
    del filter_name
    return condition == "noise_bias" and case_name in {
        "case_A_current_adaptive",
        "case_C_frozen_identifier",
        "case_E_oracle_identifier",
        "ref_raw_adaptive",
        "ref_oracle_state",
    }


def run(config_path: Path, output_root: Path, filters: list[str], cases: list[str]) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    solver_name = "cem"
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_coupling_ablation.py",
    ]
    run_specs: list[tuple[str, str, dict[str, str]]] = []
    for filter_name in filters:
        for case_name in cases:
            run_specs.append((filter_name, case_name, COUPLING_CASES[case_name]))
    for reference_name, (filter_name, case_cfg) in REFERENCE_RUNS.items():
        run_specs.append((filter_name, reference_name, case_cfg))

    summary_rows: list[dict[str, Any]] = []
    representative_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for filter_name, case_name, case_cfg in run_specs:
        filter_cfg = dict(FILTER_CONFIGS[filter_name])
        cfg = dict(base_cfg)
        cfg["observation_filter"] = filter_cfg
        cfg["coupling_ablation"] = dict(case_cfg)
        for condition_name, condition_cfg in cfg["conditions"].items():
            start = time.perf_counter()
            rows = run_condition(condition_name, condition_cfg, cfg)
            runtime_s = time.perf_counter() - start
            log_path = output_root / "logs" / solver_name / filter_name / case_name / condition_name / "timeseries.csv"
            write_condition_csv(rows, log_path)
            if should_save_video(filter_name, case_name, condition_name):
                save_spring2d_animation(
                    rows,
                    cfg["true_params"],
                    output_root / "videos" / f"{solver_name}_{filter_name}_{case_name}_{condition_name}.gif",
                    fps=int(cfg["outputs"].get("fps", 25)),
                )
            if condition_name == "noise_bias":
                representative_rows[(filter_name, case_name, condition_name)] = rows
                save_diagnostic_plot(
                    rows,
                    output_root / "figures" / "diagnostics" / f"{solver_name}_{filter_name}_{case_name}_{condition_name}.png",
                    f"{solver_name}/{filter_name}/{case_name}/{condition_name}",
                )
            summary_rows.append(
                summarize_rows(solver_name, filter_name, case_name, condition_name, condition_cfg, rows, cfg, runtime_s)
            )
        print(f"Completed solver={solver_name}, filter={filter_name}, case={case_name}")

    summary_path = output_root / "tables" / "coupling_summary.csv"
    figure_path = output_root / "figures" / "coupling_comparison.png"
    report_path = PROJECT_ROOT / "results" / "reports" / "stage5_estimator_identifier_coupling_report.md"
    save_summary_table(summary_rows, summary_path)
    save_comparison_figure(summary_rows, figure_path)
    save_report(report_path, summary_rows, commands)

    print("Spring2D estimator-identifier coupling ablation")
    print(f"  output root   : {output_root}")
    print(f"  summary table : {summary_path}")
    print(f"  figure        : {figure_path}")
    print(f"  report        : {report_path}")
    for row in summary_rows:
        print(
            "  "
            f"{row['filter']}/{row['case']}/{row['condition']}: "
            f"done={row['done_reason']}, target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"feasible={row['feasible_mpc_decisions']}/{row['total_mpc_decisions']}, "
            f"updates={row['total_parameter_update_count']}, "
            f"ukf_failures={row['ukf_failure_count']}"
        )
    return summary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--filters", nargs="+", default=["ukf", "ukf_bias"], choices=["ukf", "ukf_bias"])
    parser.add_argument("--cases", nargs="+", default=list(COUPLING_CASES.keys()), choices=list(COUPLING_CASES.keys()))
    args = parser.parse_args()
    run(args.config, args.output_root, args.filters, args.cases)


if __name__ == "__main__":
    main()
