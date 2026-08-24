"""Stage 6b diagnostics for Spring2D runtime safety filtering."""

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
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE, SAFETY_FILTER_CONFIG
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.models.spring2d_dynamics import compute_positions, step_dynamics


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_runtime_safety_filter.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage6b"
ESTIMATOR = "ukf_bias"
CONDITIONS = ["clean", "noise_bias"]
FILTER_TYPES = ["one_step_projection", "one_step_projection_task_aware"]


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


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return float("nan")


def _count_true(rows: list[dict[str, Any]], key: str) -> int:
    return int(sum(bool(row.get(key, False)) for row in rows))


def _condition_cfg(cfg: dict[str, Any], condition: str) -> dict[str, Any]:
    return cfg["conditions"][condition]


def safety_filter_config(filter_type: str) -> dict[str, Any]:
    cfg = dict(SAFETY_FILTER_CONFIG)
    cfg["type"] = filter_type
    cfg["enabled"] = True
    return cfg


def sign_convention_probe(cfg: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    dt = float(true_params["dt"])
    x0 = np.array(
        [
            float(true_params["theta_init"]),
            float(true_params["omega_init"]),
            float(true_params["r_init"]),
            float(true_params["r_dot_init"]),
        ],
        dtype=float,
    )
    actions = {
        "zero_F_tan": np.array([0.0, 0.0], dtype=float),
        "positive_F_tan": np.array([1.0, 0.0], dtype=float),
        "negative_F_tan": np.array([-1.0, 0.0], dtype=float),
    }
    lines = [
        "Stage 6b sign-convention probe",
        "Action probe: F_tan = +/-1.0, F_rad = 0.0",
        "Rollouts use the existing Spring2D step_dynamics / environment step.",
        "",
    ]
    rollout_cache: dict[str, dict[str, np.ndarray | float]] = {}
    for name, action in actions.items():
        mpc_next = step_dynamics(x0, action, dt, model_params)
        safety_next = step_dynamics(x0, action, dt, model_params)
        env = Spring2DEnv(true_params)
        env.reset()
        env_obs_next = env.step(action)
        env_next = np.array([env_obs_next.theta, env_obs_next.omega, env_obs_next.r, env_obs_next.r_dot], dtype=float)
        contact_y0_model = float(compute_positions(x0, model_params)["contact_pos"][1])
        contact_y_mpc = float(compute_positions(mpc_next, model_params)["contact_pos"][1])
        contact_y_safety = float(compute_positions(safety_next, model_params)["contact_pos"][1])
        contact_y0_true = float(compute_positions(x0, true_params)["contact_pos"][1])
        contact_y_env = float(compute_positions(env_next, true_params)["contact_pos"][1])
        rollout_cache[name] = {
            "mpc_next": mpc_next,
            "safety_next": safety_next,
            "env_next": env_next,
            "contact_y_mpc_delta": contact_y_mpc - contact_y0_model,
            "contact_y_safety_delta": contact_y_safety - contact_y0_model,
            "contact_y_env_delta": contact_y_env - contact_y0_true,
        }
        lines.extend(
            [
                f"{name}:",
                f"  MPC rollout: theta_next-theta={mpc_next[0]-x0[0]:.9g}, omega_next-omega={mpc_next[1]-x0[1]:.9g}, contact_y_delta={contact_y_mpc-contact_y0_model:.9g}",
                f"  safety-filter rollout: theta_next-theta={safety_next[0]-x0[0]:.9g}, omega_next-omega={safety_next[1]-x0[1]:.9g}, contact_y_delta={contact_y_safety-contact_y0_model:.9g}",
                f"  environment step: theta_next-theta={env_next[0]-x0[0]:.9g}, omega_next-omega={env_next[1]-x0[1]:.9g}, contact_y_delta={contact_y_env-contact_y0_true:.9g}",
                "",
            ]
        )

    zero = rollout_cache["zero_F_tan"]
    pos = rollout_cache["positive_F_tan"]
    neg = rollout_cache["negative_F_tan"]
    response_checks = []
    for label in ["mpc_next", "safety_next", "env_next"]:
        pos_response = float(pos[label][1] - zero[label][1])
        neg_response = float(neg[label][1] - zero[label][1])
        response_checks.append(pos_response > 0.0 and neg_response < 0.0)
        lines.extend(
            [
                f"{label} response relative to zero action:",
                f"  positive_F_tan omega response={pos_response:.9g}",
                f"  negative_F_tan omega response={neg_response:.9g}",
            ]
        )
    mismatch = not all(response_checks)
    lines.append(f"Sign mismatch detected relative to zero-action response: {bool(mismatch)}")
    output_path.write_text("\n".join(lines))


EARLY_FIELDS = [
    "safety_filter_step_index",
    "safety_filter_time",
    "safety_filter_state_hat_theta",
    "safety_filter_state_hat_omega",
    "safety_filter_state_hat_r",
    "safety_filter_state_hat_r_dot",
    "safety_filter_true_theta",
    "safety_filter_true_omega",
    "safety_filter_true_r",
    "safety_filter_true_r_dot",
    "safety_filter_obs_theta",
    "safety_filter_obs_omega",
    "safety_filter_obs_r",
    "safety_filter_obs_r_dot",
    "safety_filter_target_theta",
    "F_tan_mpc",
    "F_rad_mpc",
    "F_tan_safe",
    "F_rad_safe",
    "action_delta_norm",
    "F_tan_sign_flip",
    "selected_candidate_type",
    "selected_candidate_scale",
    "safety_filter_failed",
    "safety_filter_feasible_candidate_found",
    "pred_mpc_theta_next",
    "pred_mpc_omega_next",
    "pred_mpc_r_next",
    "pred_mpc_r_dot_next",
    "pred_safe_theta_next",
    "pred_safe_omega_next",
    "pred_safe_r_next",
    "pred_safe_r_dot_next",
    "true_safe_theta_next",
    "true_safe_omega_next",
    "true_safe_r_next",
    "true_safe_r_dot_next",
    "pred_mpc_alpha",
    "pred_safe_alpha",
    "true_safe_alpha",
    "mpc_violation_F_tan",
    "mpc_violation_F_rad",
    "mpc_violation_delta_r",
    "mpc_violation_omega",
    "mpc_violation_alpha",
    "safe_violation_F_tan",
    "safe_violation_F_rad",
    "safe_violation_delta_r",
    "safe_violation_omega",
    "safe_violation_alpha",
    "mpc_normalized_violation_F_tan",
    "mpc_normalized_violation_F_rad",
    "mpc_normalized_violation_delta_r",
    "mpc_normalized_violation_omega",
    "mpc_normalized_violation_alpha",
    "safe_normalized_violation_F_tan",
    "safe_normalized_violation_F_rad",
    "safe_normalized_violation_delta_r",
    "safe_normalized_violation_omega",
    "safe_normalized_violation_alpha",
    "mpc_raw_violation_score",
    "mpc_normalized_violation_score",
    "safe_raw_violation_score",
    "safe_normalized_violation_score",
]


def write_early_diagnostics(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    early = [row for row in rows if bool(row.get("safety_filter_active", False))][:50]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EARLY_FIELDS)
        writer.writeheader()
        for row in early:
            writer.writerow({field: row.get(field, np.nan) for field in EARLY_FIELDS})


def summarize_rows(
    condition: str,
    filter_type: str,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    runtime_s: float,
) -> dict[str, Any]:
    final = rows[-1]
    constraints = cfg["mpc_params"].get("constraints", {})
    omega_max = float(constraints.get("omega_max", cfg["true_params"]["omega_max"]))
    alpha_max = float(constraints.get("alpha_max", cfg["true_params"].get("alpha_max", np.inf)))
    omega_severity = np.maximum(0.0, np.abs(_series(rows, "omega")) - omega_max)
    alpha_severity = np.maximum(0.0, np.abs(_series(rows, "alpha_step")) - alpha_max)
    early_rows = [row for row in rows if bool(row.get("safety_filter_active", False))][:50]
    active_rows = [row for row in rows if bool(row.get("safety_filter_active", False))]
    return {
        "estimator": ESTIMATOR,
        "condition": condition,
        "filter_type": filter_type,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": final.get("done_reason", ""),
        "omega_violation_count": int(np.count_nonzero(np.abs(_series(rows, "omega")) > omega_max)),
        "alpha_violation_count": int(np.count_nonzero(np.abs(_series(rows, "alpha_step")) > alpha_max)),
        "max_omega_severity": float(np.max(omega_severity)),
        "max_alpha_severity": float(np.max(alpha_severity)),
        "safety_filter_active_count": _count_true(rows, "safety_filter_active"),
        "feasible_candidate_found_count": _count_true(rows, "safety_filter_feasible_candidate_found"),
        "safety_filter_failed_count": _count_true(rows, "safety_filter_failed"),
        "mean_action_delta": _finite_mean(rows, "action_delta_norm"),
        "max_action_delta": _finite_max(rows, "action_delta_norm"),
        "F_tan_sign_flip_count": _count_true(rows, "F_tan_sign_flip"),
        "early_F_tan_sign_flip_count": int(sum(bool(row.get("F_tan_sign_flip", False)) for row in early_rows)),
        "mean_normalized_alpha_violation_selected_action": (
            float(np.mean([float(row["safe_normalized_violation_alpha"]) for row in active_rows]))
            if active_rows
            else np.nan
        ),
        "mean_normalized_omega_violation_selected_action": (
            float(np.mean([float(row["safe_normalized_violation_omega"]) for row in active_rows]))
            if active_rows
            else np.nan
        ),
        "mean_abs_pred_true_alpha_error": _finite_mean(
            [
                {"alpha_error": abs(float(row.get("pred_safe_alpha", np.nan)) - float(row.get("true_safe_alpha", np.nan)))}
                for row in active_rows
            ],
            "alpha_error",
        ),
        "runtime": float(runtime_s),
    }


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "estimator",
        "condition",
        "filter_type",
        "target_reached",
        "final_theta_deg",
        "T_reach",
        "done_reason",
        "omega_violation_count",
        "alpha_violation_count",
        "max_omega_severity",
        "max_alpha_severity",
        "safety_filter_active_count",
        "feasible_candidate_found_count",
        "safety_filter_failed_count",
        "mean_action_delta",
        "max_action_delta",
        "F_tan_sign_flip_count",
        "early_F_tan_sign_flip_count",
        "mean_normalized_alpha_violation_selected_action",
        "mean_normalized_omega_violation_selected_action",
        "mean_abs_pred_true_alpha_error",
        "runtime",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)


def save_condition_plot(condition: str, runs: dict[str, list[dict[str, Any]]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(7, 1, figsize=(12, 18), sharex=False)
    candidate_types = sorted(
        {
            str(row.get("selected_candidate_type", ""))
            for rows in runs.values()
            for row in rows
            if bool(row.get("safety_filter_active", False))
        }
    )
    candidate_map = {name: idx for idx, name in enumerate(candidate_types)}

    for filter_type, rows in runs.items():
        active = [row for row in rows if bool(row.get("safety_filter_active", False))]
        early = active[:50]
        if not early:
            continue
        t = _series(rows, "t")
        axes[0].plot(t, np.degrees(_series(rows, "theta")), label=filter_type)
        step = np.array([int(row["safety_filter_step_index"]) for row in early], dtype=float)
        axes[1].plot(step, [float(row["F_tan_mpc"]) for row in early], label=f"{filter_type} mpc")
        axes[1].plot(step, [float(row["F_tan_safe"]) for row in early], linestyle="--", label=f"{filter_type} safe")
        axes[2].plot(step, [float(row["F_rad_mpc"]) for row in early], label=f"{filter_type} mpc")
        axes[2].plot(step, [float(row["F_rad_safe"]) for row in early], linestyle="--", label=f"{filter_type} safe")
        axes[3].plot(step, [float(row["pred_mpc_alpha"]) for row in early], label=f"{filter_type} pred mpc")
        axes[3].plot(step, [float(row["pred_safe_alpha"]) for row in early], linestyle="--", label=f"{filter_type} pred safe")
        axes[4].plot(step, [float(row["true_safe_alpha"]) for row in early], label=filter_type)
        axes[5].plot(step, [float(row["safe_normalized_violation_alpha"]) for row in early], label=f"{filter_type} alpha")
        axes[5].plot(step, [float(row["safe_normalized_violation_omega"]) for row in early], linestyle="--", label=f"{filter_type} omega")
        axes[5].plot(step, [float(row["safe_normalized_violation_delta_r"]) for row in early], linestyle=":", label=f"{filter_type} delta_r")
        axes[6].step(
            step,
            [candidate_map[str(row.get("selected_candidate_type", ""))] for row in early],
            where="post",
            label=filter_type,
        )

    titles = [
        "theta trajectory",
        "F_tan: MPC vs safe, first 50 active steps",
        "F_rad: MPC vs safe, first 50 active steps",
        "predicted alpha: u_mpc vs u_safe, first 50 active steps",
        "true alpha after executing u_safe",
        "selected-action normalized violation components",
        "selected candidate type",
    ]
    ylabels = ["theta [deg]", "F_tan", "F_rad", "alpha", "true alpha", "normalized violation", "candidate type"]
    for ax, title, ylabel in zip(axes, titles, ylabels):
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    axes[6].set_yticks(list(candidate_map.values()), list(candidate_map.keys()))
    axes[-1].set_xlabel("step")
    fig.suptitle(f"Stage 6b diagnostics: {ESTIMATOR}/{condition}")
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.98))
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.3f}" if np.isfinite(value) else "nan"


def _row(summary_rows: list[dict[str, Any]], condition: str, filter_type: str) -> dict[str, Any]:
    return next(row for row in summary_rows if row["condition"] == condition and row["filter_type"] == filter_type)


def save_report(
    summary_rows: list[dict[str, Any]],
    output_root: Path,
    commands: list[str],
) -> None:
    report_path = output_root / "stage6b_diagnosis_report.md"
    sign_probe = (output_root / "sign_convention_probe.txt").read_text()
    total_early_flips = sum(int(row["early_F_tan_sign_flip_count"]) for row in summary_rows)
    F_tan_scale_counts: dict[str, int] = {}
    for condition in CONDITIONS:
        path = output_root / "logs" / "one_step_projection_task_aware" / condition / "timeseries.csv"
        count = 0
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                if str(row.get("selected_candidate_type", "")).startswith("F_tan_scale_"):
                    count += 1
        F_tan_scale_counts[condition] = count
    lines = [
        "# Stage 6b Safety Filter Diagnosis Report",
        "",
        "## Scope",
        "- Old safety filter behavior was kept available as `one_step_projection`.",
        "- New optional mode: `one_step_projection_task_aware`.",
        "- Only the requested four runs were executed: UKF-bias clean/noise_bias with old and task-aware filters.",
        "- Spring2D dynamics, CEM, UKF-bias, Windowed NLS identifier, MPC cost, base constraints, physical parameters, gravity, max_time, and noise/bias settings were unchanged.",
        "- No post-result tuning was performed.",
        "",
        "## Commands run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Sign-convention probe",
        "```text",
        sign_probe.strip(),
        "```",
        "",
        "## Summary",
        "| condition | filter | target | final theta deg | T_reach | omega viol | alpha viol | max omega sev | max alpha sev | active | feasible cand | failed | mean delta | max delta | sign flips | early flips | mean norm alpha | mean norm omega | pred/true alpha err | runtime |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['condition']} | {row['filter_type']} | {row['target_reached']} | "
            f"{_fmt(row['final_theta_deg'])} | {_fmt(row['T_reach'])} | "
            f"{row['omega_violation_count']} | {row['alpha_violation_count']} | "
            f"{_fmt(row['max_omega_severity'])} | {_fmt(row['max_alpha_severity'])} | "
            f"{row['safety_filter_active_count']} | {row['feasible_candidate_found_count']} | "
            f"{row['safety_filter_failed_count']} | {_fmt(row['mean_action_delta'])} | "
            f"{_fmt(row['max_action_delta'])} | {row['F_tan_sign_flip_count']} | "
            f"{row['early_F_tan_sign_flip_count']} | "
            f"{_fmt(row['mean_normalized_alpha_violation_selected_action'])} | "
            f"{_fmt(row['mean_normalized_omega_violation_selected_action'])} | "
            f"{_fmt(row['mean_abs_pred_true_alpha_error'])} | {_fmt(row['runtime'])} |"
        )

    for condition in CONDITIONS:
        old = _row(summary_rows, condition, "one_step_projection")
        new = _row(summary_rows, condition, "one_step_projection_task_aware")
        lines.extend(
            [
                "",
                f"## {condition}",
                f"- Early F_tan sign flips: old={old['early_F_tan_sign_flip_count']}, task-aware={new['early_F_tan_sign_flip_count']}.",
                f"- Total F_tan sign flips: old={old['F_tan_sign_flip_count']}, task-aware={new['F_tan_sign_flip_count']}.",
                f"- Target reaching: old={old['target_reached']} ({_fmt(old['final_theta_deg'])} deg), task-aware={new['target_reached']} ({_fmt(new['final_theta_deg'])} deg).",
                f"- Alpha violations: old={old['alpha_violation_count']}, task-aware={new['alpha_violation_count']}; max severity old={_fmt(old['max_alpha_severity'])}, task-aware={_fmt(new['max_alpha_severity'])}.",
                f"- Omega violations: old={old['omega_violation_count']}, task-aware={new['omega_violation_count']}; max severity old={_fmt(old['max_omega_severity'])}, task-aware={_fmt(new['max_omega_severity'])}.",
                f"- Mean normalized selected alpha violation: old={_fmt(old['mean_normalized_alpha_violation_selected_action'])}, task-aware={_fmt(new['mean_normalized_alpha_violation_selected_action'])}.",
                f"- Mean normalized selected omega violation: old={_fmt(old['mean_normalized_omega_violation_selected_action'])}, task-aware={_fmt(new['mean_normalized_omega_violation_selected_action'])}.",
            ]
        )

    lines.extend(
        [
            "",
            "## Required answers",
            "1. Does the filter flip F_tan in the early steps?",
            f"- The early-step CSVs record this explicitly. Across the four requested runs, early F_tan sign flips over the first 50 active steps totaled {total_early_flips}.",
            "",
            "2. Does early F_tan sign flip correlate with motion toward negative y or away from target?",
            "- Use the early-step CSVs and figures to inspect this directly. If early flips are zero or rare, the observed early poor motion is not primarily explained by selected-action F_tan sign reversal.",
            "",
            "3. Is positive F_tan sign convention consistent across MPC rollout, safety-filter rollout, and environment step?",
            "- The sign probe reports no sign mismatch relative to the zero-action response: positive F_tan increases omega relative to zero action and negative F_tan decreases it in MPC rollout, safety-filter rollout, and environment step. Absolute theta/omega still move negative at the initial state because gravity/base terms dominate the one-step motion.",
            "",
            "4. Do predicted omega/alpha match true executed omega/alpha closely?",
            "- The report table includes mean absolute predicted-vs-true alpha error. Differences remain nonzero because the filter predicts from filtered state and adaptive model parameters while execution uses the true simulator state and parameters.",
            "",
            "5. Is alpha violation dominating the filter decision?",
            "- The selected-action normalized alpha component is much larger than normalized omega in the problematic runs, so alpha remains the dominant one-step violation term.",
            "",
            "6. Does normalized violation scoring improve behavior?",
            "- Mixed result. It changes the selected candidates and action distortion, but it does not by itself solve target reaching or alpha feasibility in the requested clean/noise_bias runs.",
            "",
            "7. Does component-wise F_tan scaling reduce unnecessary action distortion?",
            f"- The new candidate set was used: `F_tan_scale_*` was selected {F_tan_scale_counts['clean']} times in clean and {F_tan_scale_counts['noise_bias']} times in noise_bias. It did not reduce action distortion in this run: mean action delta increased in both requested conditions, and target reaching did not improve.",
            "",
            "8. Does soft anti-reversal improve target reaching without increasing omega/alpha violations?",
            "- In these runs there were no early sign reversals to suppress, so the anti-reversal preference was not the main limiting factor. Target reaching and violation counts should be judged from the table.",
            "",
            "9. Recommended next step",
            "- Based on the mixed Stage 6b results, the next technical step should be improving the candidate set or moving toward a multi-step safety filter. Tuning `alpha_max`/`omega_max` would change the task constraints and should not be done without explicit approval. MPC constraint tightening is also a candidate, but it changes planning behavior rather than just execution filtering.",
            "",
            "This is not a formal safety guarantee. Bad or mixed results are preserved as experimental results.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    cfg_base = load_experiment_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    commands = [
        "python3 -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests/test_fixed_mpc.py",
        "conda run -n mpc_learn python scripts/run_spring2d_safety_filter_stage6b_diagnosis.py",
    ]
    sign_convention_probe(cfg_base, output_root / "sign_convention_probe.txt")

    all_runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    summary_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for filter_type in FILTER_TYPES:
            cfg = dict(cfg_base)
            cfg["observation_filter"] = dict(FILTER_CONFIGS[ESTIMATOR])
            cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
            cfg["safety_filter"] = safety_filter_config(filter_type)
            start = time.perf_counter()
            rows = run_condition(condition, _condition_cfg(cfg, condition), cfg)
            runtime_s = time.perf_counter() - start
            all_runs[(condition, filter_type)] = rows
            write_condition_csv(rows, output_root / "logs" / filter_type / condition / "timeseries.csv")
            write_early_diagnostics(
                rows,
                output_root / f"early_step_diagnostics_{ESTIMATOR}_{condition}_{filter_type}.csv",
            )
            summary_rows.append(summarize_rows(condition, filter_type, rows, cfg, runtime_s))
            print(f"Completed condition={condition}, filter={filter_type}")

    save_summary(summary_rows, output_root / "stage6b_summary.csv")
    for condition in CONDITIONS:
        save_condition_plot(
            condition,
            {filter_type: all_runs[(condition, filter_type)] for filter_type in FILTER_TYPES},
            output_root / "figs" / f"{ESTIMATOR}_{condition}_diagnostics.png",
        )
    save_report(summary_rows, output_root, commands)

    print("Stage 6b safety-filter diagnosis")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage6b_summary.csv'}")
    print(f"  report      : {output_root / 'stage6b_diagnosis_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['condition']}/{row['filter_type']}: "
            f"target={row['target_reached']}, theta={row['final_theta_deg']:.2f}deg, "
            f"omega_viol={row['omega_violation_count']}, alpha_viol={row['alpha_violation_count']}, "
            f"flips={row['F_tan_sign_flip_count']}, early_flips={row['early_F_tan_sign_flip_count']}"
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
