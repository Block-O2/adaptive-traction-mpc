"""Stage 8A UKF-bias covariance sensitivity check for Spring2D CEM-MPC."""

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
from run_spring2d_estimator_comparison import FILTER_CONFIGS, UKF_BIAS_CONFIG
from run_spring2d_safety_filter_comparison import COUPLING_MAINLINE


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_safety_aware_cem.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "results" / "stage8a_ukf_sensitivity"
CONDITIONS = ["clean", "noise", "noise_bias"]
STATE_KEYS = ["theta", "omega", "r", "r_dot"]
BIAS_KEYS = ["theta", "omega", "r", "r_dot"]
PARAM_KEYS = ["m", "k", "b_r"]


def _series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([float(row.get(key, np.nan)) for row in rows], dtype=float)


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def _finite_mean(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.mean(values)) if len(values) else np.nan


def _finite_std(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.std(values)) if len(values) else np.nan


def _finite_max(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.max(values)) if len(values) else np.nan


def _finite_p95(values: np.ndarray) -> float:
    values = _finite(values)
    return float(np.percentile(values, 95)) if len(values) else np.nan


def _rmse(rows: list[dict[str, Any]], key: str) -> float:
    values = _finite(_series(rows, key))
    return float(np.sqrt(np.mean(values**2))) if len(values) else np.nan


def _first_reach_time(rows: list[dict[str, Any]]) -> float:
    for row in rows:
        if bool(row.get("target_reached", False)):
            return float(row["t"])
    return np.nan


def _severity(rows: list[dict[str, Any]], key: str, limit: float) -> np.ndarray:
    return np.maximum(0.0, np.abs(_series(rows, key)) - limit)


def _scale_list(values: list[float], scale: float) -> list[float]:
    return [float(scale) * float(value) for value in values]


def _setting_specs() -> list[dict[str, Any]]:
    specs = [{"setting": "default", "factor": "default", "scale": 1.0}]
    for scale in [0.3, 3.0]:
        specs.append({"setting": f"Q_{scale:g}", "factor": "Q", "scale": scale})
    for scale in [0.3, 3.0]:
        specs.append({"setting": f"R_{scale:g}", "factor": "R", "scale": scale})
    for scale in [0.1, 10.0]:
        specs.append({"setting": f"biasQ_{scale:g}", "factor": "bias_process_noise", "scale": scale})
    for scale in [0.3, 3.0]:
        specs.append({"setting": f"P0_{scale:g}", "factor": "P0", "scale": scale})
    return specs


def _scaled_ukf_bias_config(spec: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(UKF_BIAS_CONFIG)
    factor = str(spec["factor"])
    scale = float(spec["scale"])
    if factor == "Q":
        cfg["process_noise_state_diag"] = _scale_list(cfg["process_noise_state_diag"], scale)
    elif factor == "R":
        for key in ["measurement_noise_diag_clean", "measurement_noise_diag_noise", "measurement_noise_diag_noise_bias"]:
            cfg[key] = _scale_list(cfg[key], scale)
    elif factor == "bias_process_noise":
        cfg["process_noise_bias_diag"] = _scale_list(cfg["process_noise_bias_diag"], scale)
    elif factor == "P0":
        cfg["initial_state_cov_diag"] = _scale_list(cfg["initial_state_cov_diag"], scale)
        cfg["initial_bias_cov_diag"] = _scale_list(cfg["initial_bias_cov_diag"], scale)
    elif factor != "default":
        raise ValueError(f"Unknown sensitivity factor: {factor}")
    return cfg


def configure_run(base_cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    cfg["observation_filter"] = {
        "type": "ukf_bias",
        "identifier_input": "filtered",
        "ukf_bias": _scaled_ukf_bias_config(spec),
    }
    cfg["coupling_ablation"] = dict(COUPLING_MAINLINE)
    cfg["safety_filter"] = {"enabled": False}
    cfg["progress_governor"] = {"mode": "off"}
    solver = cfg["mpc_params"].setdefault("solver", {})
    solver["safety_mode"] = "off"
    solver["alpha_constraint_mode"] = "soft"
    solver["alpha_soft_weight"] = 1.0
    solver["safety_penalty_weight"] = 1.0
    solver["safety_control_dt"] = float(cfg["true_params"]["dt"])
    solver["gatekeeper_mode"] = "off"
    solver["gatekeeper_horizon"] = 0
    solver["gatekeeper_top_k"] = 20
    solver["collect_iteration_diagnostics"] = False
    solver["collect_sample_diagnostics"] = False
    weights = dict(solver.get("safety_violation_weights", {}))
    weights.update(
        {
            "F_tan": float(weights.get("F_tan", 1.0)),
            "F_rad": float(weights.get("F_rad", 1.0)),
            "delta_r": float(weights.get("delta_r", 1.0)),
            "omega": 0.0,
            "alpha": float(weights.get("alpha", 1.0)),
        }
    )
    solver["safety_violation_weights"] = weights
    return cfg


def summarize_rows(
    spec: dict[str, Any],
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
    action = np.column_stack([_series(rows, "F_tan"), _series(rows, "F_rad")])
    action_magnitude = np.linalg.norm(action, axis=1)
    action_smoothness = np.linalg.norm(np.diff(action, axis=0), axis=1) if len(action) > 1 else np.array([])
    alpha_sev = _severity(rows, "alpha_step", alpha_max)
    omega_sev = _severity(rows, "omega", omega_max)
    row: dict[str, Any] = {
        "setting": str(spec["setting"]),
        "factor": str(spec["factor"]),
        "scale": float(spec["scale"]),
        "condition": condition,
        "target_reached": bool(final.get("target_reached", False)),
        "final_theta_deg": float(np.degrees(float(final["theta"]))),
        "T_reach": _first_reach_time(rows),
        "done_reason": str(final.get("done_reason", "")),
        "alpha_violation_count": int(np.count_nonzero(alpha_sev > 0.0)),
        "alpha_mean_severity": _finite_mean(alpha_sev),
        "alpha_p95_severity": _finite_p95(alpha_sev),
        "alpha_max_severity": _finite_max(alpha_sev),
        "omega_violation_count": int(np.count_nonzero(omega_sev > 0.0)),
        "omega_mean_severity": _finite_mean(omega_sev),
        "omega_p95_severity": _finite_p95(omega_sev),
        "omega_max_severity": _finite_max(omega_sev),
        "mean_action_magnitude": _finite_mean(action_magnitude),
        "max_action_magnitude": _finite_max(action_magnitude),
        "action_smoothness": _finite_mean(action_smoothness),
        "mean_innovation_norm": _finite_mean(_series(rows, "innovation_norm")),
        "max_covariance_trace": _finite_max(_series(rows, "covariance_trace")),
        "ukf_failure_count": int(sum(bool(item.get("ukf_failed", False)) for item in rows)),
        "runtime_s": float(runtime_s),
    }
    for key in STATE_KEYS:
        row[f"rmse_{key}"] = _rmse(rows, f"filter_error_{key}")
    for key in BIAS_KEYS:
        values = _series(rows, f"bias_{key}_hat")
        row[f"bias_{key}_mean"] = _finite_mean(values)
        row[f"bias_{key}_std"] = _finite_std(values)
        row[f"bias_{key}_final"] = float(final.get(f"bias_{key}_hat", np.nan))
    for key in PARAM_KEYS:
        values = _series(rows, f"{key}_hat")
        row[f"{key}_mean"] = _finite_mean(values)
        row[f"{key}_std"] = _finite_std(values)
        row[f"{key}_final"] = float(final.get(f"{key}_hat", np.nan))
    return row


SUMMARY_FIELDS = [
    "setting",
    "factor",
    "scale",
    "condition",
    "target_reached",
    "final_theta_deg",
    "T_reach",
    "done_reason",
    "rmse_theta",
    "rmse_omega",
    "rmse_r",
    "rmse_r_dot",
    "bias_theta_mean",
    "bias_theta_std",
    "bias_theta_final",
    "bias_omega_mean",
    "bias_omega_std",
    "bias_omega_final",
    "bias_r_mean",
    "bias_r_std",
    "bias_r_final",
    "bias_r_dot_mean",
    "bias_r_dot_std",
    "bias_r_dot_final",
    "m_mean",
    "m_std",
    "m_final",
    "k_mean",
    "k_std",
    "k_final",
    "b_r_mean",
    "b_r_std",
    "b_r_final",
    "alpha_violation_count",
    "alpha_mean_severity",
    "alpha_p95_severity",
    "alpha_max_severity",
    "omega_violation_count",
    "omega_mean_severity",
    "omega_p95_severity",
    "omega_max_severity",
    "mean_action_magnitude",
    "max_action_magnitude",
    "action_smoothness",
    "mean_innovation_norm",
    "max_covariance_trace",
    "ukf_failure_count",
    "runtime_s",
]


def save_summary(summary_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)


def _row(summary_rows: list[dict[str, Any]], setting: str, condition: str) -> dict[str, Any]:
    for row in summary_rows:
        if row["setting"] == setting and row["condition"] == condition:
            return row
    raise KeyError((setting, condition))


def _aggregate(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for spec in _setting_specs():
        setting = str(spec["setting"])
        setting_rows = [row for row in summary_rows if row["setting"] == setting]
        rows.append(
            {
                "setting": setting,
                "factor": str(spec["factor"]),
                "scale": float(spec["scale"]),
                "target_success_count": int(sum(bool(row["target_reached"]) for row in setting_rows)),
                "rmse_theta_avg": _finite_mean(np.array([float(row["rmse_theta"]) for row in setting_rows])),
                "rmse_omega_avg": _finite_mean(np.array([float(row["rmse_omega"]) for row in setting_rows])),
                "rmse_r_avg": _finite_mean(np.array([float(row["rmse_r"]) for row in setting_rows])),
                "rmse_r_dot_avg": _finite_mean(np.array([float(row["rmse_r_dot"]) for row in setting_rows])),
                "alpha_p95_avg": _finite_mean(np.array([float(row["alpha_p95_severity"]) for row in setting_rows])),
                "alpha_max_avg": _finite_mean(np.array([float(row["alpha_max_severity"]) for row in setting_rows])),
                "omega_p95_avg": _finite_mean(np.array([float(row["omega_p95_severity"]) for row in setting_rows])),
                "omega_max_avg": _finite_mean(np.array([float(row["omega_max_severity"]) for row in setting_rows])),
                "T_reach_avg": _finite_mean(np.array([float(row["T_reach"]) for row in setting_rows])),
            }
        )
    return rows


def _best_setting(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        aggregate_rows,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            row["alpha_p95_avg"],
            row["alpha_max_avg"],
            row["omega_p95_avg"],
            row["rmse_omega_avg"],
        ),
    )


def _worst_setting(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        aggregate_rows,
        key=lambda row: (
            len(CONDITIONS) - int(row["target_success_count"]),
            row["alpha_p95_avg"],
            row["alpha_max_avg"],
            row["omega_p95_avg"],
            row["rmse_omega_avg"],
        ),
    )


def _factor_sensitivity(aggregate_rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    result = {}
    for factor in ["Q", "R", "bias_process_noise", "P0"]:
        values = [float(row[metric]) for row in aggregate_rows if row["factor"] == factor]
        values = [value for value in values if np.isfinite(value)]
        result[factor] = float(max(values) - min(values)) if values else np.nan
    return result


def save_plots(
    summary_rows: list[dict[str, Any]],
    all_rows: dict[tuple[str, str], list[dict[str, Any]]],
    output_root: Path,
) -> None:
    fig_dir = output_root / "figs"
    fig_dir.mkdir(parents=True, exist_ok=True)
    settings = [spec["setting"] for spec in _setting_specs()]
    x = np.arange(len(settings))
    for condition in CONDITIONS:
        fig, axes = plt.subplots(4, 1, figsize=(13, 10), sharex=True)
        for idx, state_key in enumerate(STATE_KEYS):
            values = [float(_row(summary_rows, setting, condition)[f"rmse_{state_key}"]) for setting in settings]
            axes[idx].bar(x, values)
            axes[idx].set_ylabel(f"RMSE {state_key}")
            axes[idx].grid(True, axis="y", alpha=0.25)
        axes[-1].set_xticks(x)
        axes[-1].set_xticklabels(settings, rotation=45, ha="right")
        fig.suptitle(f"{condition}: state estimation RMSE by UKF-bias setting")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        fig.savefig(fig_dir / f"{condition}_estimation_rmse_by_setting.png", dpi=150)
        plt.close(fig)

    for label, p95_metric, max_metric in [
        ("alpha", "alpha_p95_severity", "alpha_max_severity"),
        ("omega", "omega_p95_severity", "omega_max_severity"),
    ]:
        fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
        width = 0.25
        offsets = np.linspace(-width, width, len(CONDITIONS))
        for offset, condition in zip(offsets, CONDITIONS):
            p95_values = [float(_row(summary_rows, setting, condition)[p95_metric]) for setting in settings]
            max_values = [float(_row(summary_rows, setting, condition)[max_metric]) for setting in settings]
            axes[0].bar(x + offset, p95_values, width=width, label=condition)
            axes[1].bar(x + offset, max_values, width=width, label=condition)
        axes[0].set_ylabel(f"{label} p95 severity")
        axes[1].set_ylabel(f"{label} max severity")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(settings, rotation=45, ha="right")
        for ax in axes:
            ax.grid(True, axis="y", alpha=0.25)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"Stage 8A: {label} p95/max by UKF-bias setting")
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
        fig.savefig(fig_dir / f"{label}_p95_max_by_setting.png", dpi=150)
        plt.close(fig)

    for condition in ["noise_bias"]:
        for group, keys, filename in [
            ("bias estimate", [f"bias_{key}_hat" for key in BIAS_KEYS], "bias_estimate_trajectories.png"),
            ("parameter estimate", [f"{key}_hat" for key in PARAM_KEYS], "parameter_estimate_trajectories.png"),
        ]:
            fig, axes = plt.subplots(len(keys), 1, figsize=(12, 9), sharex=True)
            for ax, key in zip(np.atleast_1d(axes), keys):
                for setting in settings:
                    rows = all_rows[(setting, condition)]
                    ax.plot(_series(rows, "t"), _series(rows, key), label=setting)
                ax.set_ylabel(key)
                ax.grid(True, alpha=0.25)
            axes[0].legend(fontsize=7, ncol=3)
            axes[-1].set_xlabel("time [s]")
            fig.suptitle(f"{condition}: {group} trajectories")
            fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
            fig.savefig(fig_dir / f"{condition}_{filename}", dpi=150)
            plt.close(fig)

    aggregate = _aggregate(summary_rows)
    best = _best_setting(aggregate)["setting"]
    worst = _worst_setting(aggregate)["setting"]
    fig, ax = plt.subplots(figsize=(11, 5))
    for setting in ["default", best, worst]:
        rows = all_rows[(setting, "noise_bias")]
        ax.plot(_series(rows, "t"), np.degrees(_series(rows, "theta")), label=setting)
    target = float(np.degrees(float(all_rows[("default", "noise_bias")][-1].get("theta_target_final", np.nan))))
    if np.isfinite(target):
        ax.axhline(target, color="black", linestyle=":", label="theta_target")
    ax.set_title("noise_bias: theta trajectory for default vs best/worst sensitivity case")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("theta [deg]")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "noise_bias_theta_default_best_worst.png", dpi=150)
    plt.close(fig)


def _fmt(value: Any) -> str:
    value = float(value)
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def save_report(summary_rows: list[dict[str, Any]], output_root: Path, commands: list[str]) -> None:
    aggregate = _aggregate(summary_rows)
    by_setting = {row["setting"]: row for row in aggregate}
    default = by_setting["default"]
    best = _best_setting(aggregate)
    target_hurt = [row for row in aggregate if int(row["target_success_count"]) < len(CONDITIONS)]
    alpha_sensitivity = _factor_sensitivity(aggregate, "alpha_p95_avg")
    omega_sensitivity = _factor_sensitivity(aggregate, "omega_p95_avg")
    rmse_sensitivity = _factor_sensitivity(aggregate, "rmse_omega_avg")
    dominant_factor = max(
        ["Q", "R", "bias_process_noise", "P0"],
        key=lambda factor: max(
            alpha_sensitivity.get(factor, np.nan),
            omega_sensitivity.get(factor, np.nan),
            rmse_sensitivity.get(factor, np.nan),
        ),
    )
    improves_tail = (
        best["alpha_p95_avg"] < default["alpha_p95_avg"]
        and best["alpha_max_avg"] < default["alpha_max_avg"]
        and best["omega_p95_avg"] <= default["omega_p95_avg"]
    )
    robust = (
        not target_hurt
        and max(float(row["alpha_p95_avg"]) for row in aggregate if np.isfinite(float(row["alpha_p95_avg"])))
        <= 1.5 * float(default["alpha_p95_avg"])
    )
    lines = [
        "# Stage 8A UKF-Bias Covariance Sensitivity Report",
        "",
        "## Scope",
        "- Sanity check for UKF-bias covariance sensitivity only.",
        "- Mainline remains CEM + UKF-bias + filtered Windowed NLS identifier.",
        "- Swept one factor at a time: process noise Q, measurement noise R, bias process noise, and initial covariance P0.",
        "- No full Cartesian product was run.",
        "- Dynamics, CEM controller, identifier structure, cost, constraints, Stage 7 methods, and baseline behavior were not intentionally changed.",
        "- No formal safety claims are made.",
        "",
        "## Commands Run",
        *[f"- `{command}`" for command in commands],
        "",
        "## Aggregate Metrics",
        "| setting | factor | scale | target successes | RMSE theta | RMSE omega | alpha p95 | alpha max | omega p95 | omega max | T_reach avg |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            f"| {row['setting']} | {row['factor']} | {_fmt(row['scale'])} | "
            f"{row['target_success_count']}/{len(CONDITIONS)} | {_fmt(row['rmse_theta_avg'])} | "
            f"{_fmt(row['rmse_omega_avg'])} | {_fmt(row['alpha_p95_avg'])} | {_fmt(row['alpha_max_avg'])} | "
            f"{_fmt(row['omega_p95_avg'])} | {_fmt(row['omega_max_avg'])} | {_fmt(row['T_reach_avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Sensitivity Ranges",
            "| factor | alpha p95 range | omega p95 range | omega RMSE range |",
            "|---|---:|---:|---:|",
        ]
    )
    for factor in ["Q", "R", "bias_process_noise", "P0"]:
        lines.append(
            f"| {factor} | {_fmt(alpha_sensitivity[factor])} | {_fmt(omega_sensitivity[factor])} | "
            f"{_fmt(rmse_sensitivity[factor])} |"
        )
    lines.extend(
        [
            "",
            "## Required Answers",
            "1. Are current UKF-bias covariance settings reasonably robust?",
            f"- {'Yes/mostly' if robust else 'No/mixed'} based on this one-factor sweep. Default target={default['target_success_count']}/{len(CONDITIONS)}, alpha p95 avg={_fmt(default['alpha_p95_avg'])}, omega p95 avg={_fmt(default['omega_p95_avg'])}.",
            "",
            "2. Which parameter matters most: Q, R, bias noise, or P0?",
            f"- `{dominant_factor}` showed the largest combined spread across alpha p95, omega p95, and omega RMSE in this sweep.",
            "",
            "3. Does tuning UKF-bias reduce alpha/omega tail risk?",
            f"- {'Yes/mixed' if improves_tail else 'No/mixed'}: best setting `{best['setting']}` alpha p95/max={_fmt(best['alpha_p95_avg'])}/{_fmt(best['alpha_max_avg'])}, omega p95/max={_fmt(best['omega_p95_avg'])}/{_fmt(best['omega_max_avg'])}; default={_fmt(default['alpha_p95_avg'])}/{_fmt(default['alpha_max_avg'])}, omega={_fmt(default['omega_p95_avg'])}/{_fmt(default['omega_max_avg'])}.",
            "",
            "4. Does any setting hurt target reaching?",
            "- "
            + (
                "No setting lost target reaching."
                if not target_hurt
                else ", ".join(f"{row['setting']} target={row['target_success_count']}/{len(CONDITIONS)}" for row in target_hurt)
            ),
            "",
            "5. Should we keep default UKF-bias settings or change them?",
            f"- {'Keep default' if not improves_tail else 'Consider changing only with stress validation'} based on this sanity check; do not treat a small covariance improvement as a controller fix.",
            "",
            "6. Is estimator tuning likely the main cause of alpha tail risk?",
            f"- {'Unlikely' if not improves_tail else 'Not proven'} from this sweep. Alpha tail risk remains primarily a controller/action-generation issue unless a covariance setting consistently reduces alpha p95/max without hurting target reaching or omega risk.",
            "",
            "## Outputs",
            "- `stage8a_ukf_sensitivity_summary.csv` contains per-setting/per-condition metrics.",
            "- Per-run timeseries logs are under `logs/{setting}/{condition}/timeseries.csv`.",
            "- Plots are under `figs/`.",
            "",
        ]
    )
    (output_root / "stage8a_ukf_sensitivity_report.md").write_text("\n".join(lines))


def run(config_path: Path, output_root: Path) -> list[dict[str, Any]]:
    base_cfg = load_experiment_config(config_path)
    specs = _setting_specs()
    commands = [
        "conda run -n mpc_learn python -m compileall src scripts",
        "conda run -n mpc_learn python -m pytest tests",
        "conda run --no-capture-output -n mpc_learn python scripts/run_spring2d_stage8a_ukf_sensitivity.py",
    ]
    all_rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    runtimes: dict[tuple[str, str], float] = {}
    for spec in specs:
        cfg = configure_run(base_cfg, spec)
        setting = str(spec["setting"])
        for condition in CONDITIONS:
            start = time.perf_counter()
            rows = run_condition(condition, cfg["conditions"][condition], cfg)
            runtime_s = time.perf_counter() - start
            for row in rows:
                row["stage8a_setting"] = setting
                row["stage8a_factor"] = str(spec["factor"])
                row["stage8a_scale"] = float(spec["scale"])
            all_rows[(setting, condition)] = rows
            runtimes[(setting, condition)] = runtime_s
            write_condition_csv(rows, output_root / "logs" / setting / condition / "timeseries.csv")
            print(f"Completed setting={setting}, condition={condition}, runtime={runtime_s:.2f}s", flush=True)

    summary_rows: list[dict[str, Any]] = []
    for spec in specs:
        cfg = configure_run(base_cfg, spec)
        setting = str(spec["setting"])
        for condition in CONDITIONS:
            summary_rows.append(
                summarize_rows(
                    spec,
                    condition,
                    all_rows[(setting, condition)],
                    cfg,
                    runtimes[(setting, condition)],
                )
            )

    save_summary(summary_rows, output_root / "stage8a_ukf_sensitivity_summary.csv")
    save_plots(summary_rows, all_rows, output_root)
    save_report(summary_rows, output_root, commands)

    print("Stage 8A UKF-bias covariance sensitivity")
    print(f"  output root : {output_root}")
    print(f"  summary     : {output_root / 'stage8a_ukf_sensitivity_summary.csv'}")
    print(f"  report      : {output_root / 'stage8a_ukf_sensitivity_report.md'}")
    for row in summary_rows:
        print(
            "  "
            f"{row['setting']}/{row['condition']}: target={row['target_reached']}, "
            f"theta={row['final_theta_deg']:.2f}deg, "
            f"rmse_omega={row['rmse_omega']:.4f}, "
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
