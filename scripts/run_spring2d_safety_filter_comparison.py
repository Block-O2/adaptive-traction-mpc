"""Compare runtime one-step safety filtering for Spring2D adaptive MPC."""

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


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_runtime_safety_filter.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage6_safety_filter"
REPORT_PATH = PROJECT_ROOT / "results" / "reports" / "stage6_runtime_safety_filter_report.md"

ESTIMATORS = ["ukf_bias", "ukf"]
SAFETY_FILTER_CONFIG = {
    "enabled": True,
    "type": "one_step_projection",
    "scales": [1.0, 0.8, 0.6, 0.4, 0.2, 0.0],
    "F_tan_offsets": [-2.0, -1.0, 0.0, 1.0, 2.0],
    "F_rad_offsets": [-0.2, -0.1, 0.0, 0.1, 0.2],
    "violation_weights": {
        "F_tan": 1.0,
        "F_rad": 1.0,
        "delta_r": 1.0,
        "omega": 1.0,
        "alpha": 1.0,
    },
}
SAFETY_MODES = {
    "safety_off": {"enabled": False},
    "safety_on": SAFETY_FILTER_CONFIG,
}
COUPLING_MAINLINE = {
    "name": "safety_filter_filtered_identifier_adaptive",
    "mpc_state_input": "filtered",
    "identifier_input": "filtered",
    "identifier_mode": "adaptive",
    "estimator_model_params_source": "adaptive",
    "mpc_model_params_source": "adaptive",
}


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row.get(key, np.nan)) for row in rows], dtype=float)


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def _finite_mean(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.mean(values)) if len(values) else np.nan


def _finite_max(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.max(values)) if len(values) else np.nan


def _rms(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.sqrt(np.mean(values**2))) if len(values) else np.nan


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


def _count_true(rows: list[dict[str, Any]], key: str) -> int:
    return int(sum(bool(row.get(key, False)) for row in rows))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0 or not np.isfinite(denominator):
        return np.nan
    return float(numerator / denominator)


def summarize_rows(
    estimator: str,
    safety_mode: str,
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
    omega_violation_severity = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_violation_severity = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    active_count = _count_true(rows, "safety_filter_active")
    action_delta = _series(rows, "action_delta_norm")
    violation_scores = _series(rows, "safety_filter_violation_score")
    return {
        "estimator": estimator,
        "safety_mode": safety_mode,
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "max_abs_F_rad": float(np.max(np.abs(_series(rows, "F_rad")))),
        "max_abs_delta_r": float(np.max(np.abs(_series(rows, "delta_r")))),
        "max_abs_omega": float(np.max(np.abs(_series(rows, "omega")))),
        "max_abs_alpha_step": float(np.max(np.abs(_series(rows, "alpha_step")))),
        "max_abs_F_tan": float(np.max(np.abs(_series(rows, "F_tan")))),
        "omega_violation_count": int(np.count_nonzero(np.abs(_series(rows, "omega")) > omega_max)),
        "alpha_violation_count": int(np.count_nonzero(np.abs(_series(rows, "alpha_step")) > alpha_max)),
        "max_omega_violation_severity": float(np.max(omega_violation_severity)),
        "max_alpha_violation_severity": float(np.max(alpha_violation_severity)),
        "feasible_mpc_decisions": int(feasible_decisions),
        "total_mpc_decisions": int(len(decisions)),
        "feasible_mpc_decision_ratio": float(feasible_decisions / len(decisions)) if decisions else np.nan,
        "mean_feasible_count": float(np.mean(feasible_counts)) if feasible_counts else np.nan,
        "safety_filter_active_count": active_count,
        "safety_filter_active_ratio": _safe_ratio(active_count, len(rows)),
        "feasible_candidate_found_count": _count_true(rows, "safety_filter_feasible_candidate_found"),
        "safety_filter_failed_count": _count_true(rows, "safety_filter_failed"),
        "mean_action_delta_norm": float(np.mean(_finite(action_delta))) if len(_finite(action_delta)) else np.nan,
        "max_action_delta_norm": float(np.max(_finite(action_delta))) if len(_finite(action_delta)) else np.nan,
        "mean_safety_filter_violation_score": (
            float(np.mean(_finite(violation_scores))) if len(_finite(violation_scores)) else np.nan
        ),
        "max_safety_filter_violation_score": (
            float(np.max(_finite(violation_scores))) if len(_finite(violation_scores)) else np.nan
        ),
        "rms_filt_omega_error": _rms(rows, "filter_error_omega"),
        "rms_filt_theta_error": _rms(rows, "filter_error_theta"),
        "mean_innovation_norm": _finite_mean(rows, "innovation_norm"),
        "max_covariance_trace": _finite_max(rows, "covariance_trace"),
        "ukf_failure_count": _count_true(rows, "ukf_failed"),
        "max_parameter_step_norm": _finite_max(rows, "parameter_step_norm"),
        "final_m_hat": float(final.get("m_hat", np.nan)),
        "final_k_hat": float(final.get("k_hat", np.nan)),
        "final_b_r_hat": float(final.get("b_r_hat", np.nan)),
        "done_reason": final.get("done_reason", ""),
        "runtime_s": float(runtime_s),
    }


def save_summary_table(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "estimator",
        "safety_mode",
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
        "omega_violation_count",
        "alpha_violation_count",
        "max_omega_violation_severity",
        "max_alpha_violation_severity",
        "feasible_mpc_decisions",
        "total_mpc_decisions",
        "feasible_mpc_decision_ratio",
        "mean_feasible_count",
        "safety_filter_active_count",
        "safety_filter_active_ratio",
        "feasible_candidate_found_count",
        "safety_filter_failed_count",
        "mean_action_delta_norm",
        "max_action_delta_norm",
        "mean_safety_filter_violation_score",
        "max_safety_filter_violation_score",
        "rms_filt_omega_error",
        "rms_filt_theta_error",
        "mean_innovation_norm",
        "max_covariance_trace",
        "ukf_failure_count",
        "max_parameter_step_norm",
        "final_m_hat",
        "final_k_hat",
        "final_b_r_hat",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_comparison_figure(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = [f"{row['estimator']}\n{row['safety_mode']}\n{row['condition']}" for row in summary_rows]
    metrics = [
        ("alpha_violation_count", "alpha violation count"),
        ("omega_violation_count", "omega violation count"),
        ("max_alpha_violation_severity", "max alpha severity"),
        ("final_theta_deg", "final theta [deg]"),
        ("safety_filter_failed_count", "filter failed count"),
        ("max_action_delta_norm", "max action delta"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(max(13, len(labels) * 0.58), 11), sharex=True)
    x = np.arange(len(summary_rows))
    for ax, (metric, ylabel) in zip(axes.ravel(), metrics):
        values = [float(row[metric]) for row in summary_rows]
        ax.bar(x, values)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
    axes[-1, 0].set_xticks(x, labels, rotation=70, ha="right")
    axes[-1, 1].set_xticks(x, labels, rotation=70, ha="right")
    fig.suptitle("Spring2D Runtime One-Step Safety Filter Comparison")
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 0.96))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _format_float(value: Any) -> str:
    value = float(value)
    return f"{value:.3f}" if np.isfinite(value) else "nan"


def _delta_line(summary_rows: list[dict[str, Any]], estimator: str, condition: str, metric: str) -> str:
    off = next(row for row in summary_rows if row["estimator"] == estimator and row["condition"] == condition and row["safety_mode"] == "safety_off")
    on = next(row for row in summary_rows if row["estimator"] == estimator and row["condition"] == condition and row["safety_mode"] == "safety_on")
    return f"{_format_float(off[metric])} -> {_format_float(on[metric])}"


def save_report(
    report_path: Path,
    summary_rows: list[dict[str, Any]],
    commands: list[str],
    config_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 6 Runtime One-Step Safety Filter Report",
        "",
        "## Files changed",
        "- Added `src/traction_mpc/mpc/safety_filter.py`.",
        "- Updated `scripts/run_spring2d_adaptive_mpc_conditions.py` to log MPC action, safe action, and safety-filter diagnostics.",
        "- Added `configs/spring2d_runtime_safety_filter.yaml`.",
        "- Added `scripts/run_spring2d_safety_filter_comparison.py`.",
        "",
        "## Unchanged setup confirmation",
        "- Spring2D dynamics: unchanged.",
        "- MPC cost definition: unchanged.",
        "- Base MPC constraints: unchanged and reused by the runtime filter.",
        "- CEM solver algorithm: unchanged.",
        "- UKF / UKF-bias algorithm: unchanged.",
        "- Windowed NLS identifier algorithm: unchanged.",
        "- Physical parameters, gravity handling, max_time, and observation noise/bias settings: unchanged.",
        "- No robust identifier, DREM, EKF, explicit gravity compensation, or post-result tuning was added.",
        "",
        "## One-step filter",
        "- The MPC proposes `u_mpc = [F_tan_mpc, F_rad_mpc]`; the environment executes `u_safe` when the filter is enabled.",
        "- The implemented selection approximates `argmin_u ||u - u_mpc||^2` over derivative-free candidates.",
        "- Candidate actions include `u_mpc`, clipped `u_mpc`, configured scaled actions, and a configured local grid around `u_mpc`; all candidates are clipped to input bounds.",
        "- Each candidate is rolled out one step with `x_next = Phi_dt(x_hat_t, u; theta_hat)`, `delta_r_next = r_next - L0`, and `alpha = (omega_next - omega_t) / control_dt`.",
        "- If a feasible candidate exists, the filter selects the feasible candidate with minimum action distance. Otherwise it selects the least-violating candidate by `(violation_score, action distance)` and logs `safety_filter_failed=True`.",
        "- This is an approximate execution-time one-step filter, not a formal invariant-set safety proof.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        f"Config used: `{config_path.relative_to(PROJECT_ROOT)}`.",
        "",
        "## Safety filter config",
        "- `enabled`: compared as `false` and `true`.",
        "- `type`: `one_step_projection`.",
        "- `scales`: `[1.0, 0.8, 0.6, 0.4, 0.2, 0.0]`.",
        "- `F_tan_offsets`: `[-2.0, -1.0, 0.0, 1.0, 2.0]`.",
        "- `F_rad_offsets`: `[-0.2, -0.1, 0.0, 0.1, 0.2]`.",
        "- `violation_weights`: all one.",
        "",
        "## Summary table",
        "| estimator | safety | condition | target | final theta deg | T_reach | feasible MPC | omega viol | alpha viol | max omega sev | max alpha sev | filter active | feasible cand | filter failed | mean action delta | max action delta | done | runtime s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['estimator']} | {row['safety_mode']} | {row['condition']} | {row['target_reached']} | "
            f"{_format_float(row['final_theta_deg'])} | {_format_float(row['T_reach'])} | "
            f"{row['feasible_mpc_decisions']}/{row['total_mpc_decisions']} | "
            f"{row['omega_violation_count']} | {row['alpha_violation_count']} | "
            f"{_format_float(row['max_omega_violation_severity'])} | {_format_float(row['max_alpha_violation_severity'])} | "
            f"{row['safety_filter_active_count']} | {row['feasible_candidate_found_count']} | "
            f"{row['safety_filter_failed_count']} | {_format_float(row['mean_action_delta_norm'])} | "
            f"{_format_float(row['max_action_delta_norm'])} | {row['done_reason']} | {_format_float(row['runtime_s'])} |"
        )

    lines.extend(
        [
            "",
            "## Analysis",
            "Did the filter reduce omega/alpha violation count?",
            *[
                f"- {estimator}/{condition}: omega count {_delta_line(summary_rows, estimator, condition, 'omega_violation_count')}, "
                f"alpha count {_delta_line(summary_rows, estimator, condition, 'alpha_violation_count')}."
                for estimator in ESTIMATORS
                for condition in ["clean", "noise", "noise_bias"]
            ],
            "",
            "Did it reduce max omega/alpha violation severity?",
            *[
                f"- {estimator}/{condition}: omega severity {_delta_line(summary_rows, estimator, condition, 'max_omega_violation_severity')}, "
                f"alpha severity {_delta_line(summary_rows, estimator, condition, 'max_alpha_violation_severity')}."
                for estimator in ESTIMATORS
                for condition in ["clean", "noise", "noise_bias"]
            ],
            "",
            "Did it hurt target reaching or increase T_reach?",
            *[
                f"- {row['estimator']}/{row['safety_mode']}/{row['condition']}: target={row['target_reached']}, "
                f"T_reach={_format_float(row['T_reach'])}, done={row['done_reason']}."
                for row in summary_rows
            ],
            "",
            "How often did it modify the action and how large were the modifications?",
            *[
                f"- {row['estimator']}/{row['condition']} safety_on: active={row['safety_filter_active_count']}, "
                f"mean_delta={_format_float(row['mean_action_delta_norm'])}, max_delta={_format_float(row['max_action_delta_norm'])}."
                for row in summary_rows
                if row["safety_mode"] == "safety_on"
            ],
            "",
            "How often did it fail to find a one-step feasible candidate?",
            *[
                f"- {row['estimator']}/{row['condition']} safety_on: failed={row['safety_filter_failed_count']}, "
                f"feasible_candidate_found={row['feasible_candidate_found_count']}."
                for row in summary_rows
                if row["safety_mode"] == "safety_on"
            ],
            "",
            "Was UKF or UKF-bias better with the safety filter enabled?",
            *[
                f"- {condition}: UKF-bias target={next(row for row in summary_rows if row['estimator'] == 'ukf_bias' and row['safety_mode'] == 'safety_on' and row['condition'] == condition)['target_reached']}, "
                f"UKF target={next(row for row in summary_rows if row['estimator'] == 'ukf' and row['safety_mode'] == 'safety_on' and row['condition'] == condition)['target_reached']}; "
                f"UKF-bias alpha violations={next(row for row in summary_rows if row['estimator'] == 'ukf_bias' and row['safety_mode'] == 'safety_on' and row['condition'] == condition)['alpha_violation_count']}, "
                f"UKF alpha violations={next(row for row in summary_rows if row['estimator'] == 'ukf' and row['safety_mode'] == 'safety_on' and row['condition'] == condition)['alpha_violation_count']}."
                for condition in ["clean", "noise", "noise_bias"]
            ],
            "",
            "Bad or mixed results are reported as-is. No parameters were tuned after observing outputs.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def should_save_video(estimator: str, safety_mode: str, condition: str) -> bool:
    del estimator, safety_mode
    return condition == "noise_bias"


def _verify_safe_action_execution(rows: list[dict[str, Any]], safety_mode: str) -> bool:
    if safety_mode != "safety_on":
        return True
    for row in rows:
        if not bool(row.get("safety_filter_active", False)):
            continue
        if not np.isclose(float(row["F_tan"]), float(row["F_tan_safe"]), atol=1.0e-9):
            return False
        if not np.isclose(float(row["F_rad"]), float(row["F_rad_safe"]), atol=1.0e-9):
            return False
    return True


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    summary_rows: list[dict[str, Any]] = []
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_safety_filter_comparison.py",
    ]

    for estimator in ESTIMATORS:
        for safety_mode, safety_cfg in SAFETY_MODES.items():
            cfg = dict(base_cfg)
            cfg["observation_filter"] = dict(FILTER_CONFIGS[estimator])
            cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
            cfg["safety_filter"] = dict(safety_cfg)
            for condition_name, condition_cfg in cfg["conditions"].items():
                start = time.perf_counter()
                rows = run_condition(condition_name, condition_cfg, cfg)
                runtime_s = time.perf_counter() - start
                if not _verify_safe_action_execution(rows, safety_mode):
                    raise RuntimeError(f"Executed action mismatch for {estimator}/{safety_mode}/{condition_name}")
                log_path = output_root / "logs" / estimator / safety_mode / condition_name / "timeseries.csv"
                write_condition_csv(rows, log_path)
                if should_save_video(estimator, safety_mode, condition_name):
                    save_spring2d_animation(
                        rows,
                        cfg["true_params"],
                        output_root / "videos" / f"{estimator}_{safety_mode}_{condition_name}.gif",
                        fps=int(cfg["outputs"].get("fps", 25)),
                    )
                summary_rows.append(summarize_rows(estimator, safety_mode, condition_name, rows, cfg, runtime_s))
            print(f"Completed estimator={estimator}, safety={safety_mode}")

    summary_path = output_root / "tables" / "safety_filter_summary.csv"
    figure_path = output_root / "figures" / "safety_filter_comparison.png"
    save_summary_table(summary_rows, summary_path)
    save_comparison_figure(summary_rows, figure_path)
    save_report(REPORT_PATH, summary_rows, commands, config_path)

    print("Spring2D runtime safety filter comparison")
    print(f"  config        : {config_path}")
    print(f"  output root   : {output_root}")
    print(f"  summary table : {summary_path}")
    print(f"  figure        : {figure_path}")
    print(f"  report        : {REPORT_PATH}")
    for row in summary_rows:
        print(
            "  "
            f"{row['estimator']}/{row['safety_mode']}/{row['condition']}: "
            f"done={row['done_reason']}, target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"omega_viol={row['omega_violation_count']}, "
            f"alpha_viol={row['alpha_violation_count']}, "
            f"filter_failed={row['safety_filter_failed_count']}"
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
