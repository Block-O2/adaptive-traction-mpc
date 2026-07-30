"""Stage 10E corrected multiple-shooting inverse-mass MHE benchmark."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/adaptive_traction_mpc_mplconfig")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/adaptive_traction_mpc_cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src")); sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10c_multiple_shooting_mhe import (
    BASELINE_METHOD,
    DEFAULT_CONFIG,
    DEFAULT_REPLAY,
    DEFAULT_STAGE10B,
    MULTIPLE_METHOD,
    SINGLE_METHOD,
    aggregate,
    arrays,
    evaluate_multiple,
    gate,
    load_replay,
    read_stage10b_rows,
)
from run_spring2d_stage9j_gap_decomposition import CONDITIONS, SEEDS, stage9j_overrides, write_dict_csv

OUTPUT = PROJECT_ROOT / "results" / "stage10e_corrected_mhe_benchmark"
BIAS_CONDITIONS = ("noise_bias",)
NO_BIAS_CONDITIONS = tuple(condition for condition in CONDITIONS if condition not in BIAS_CONDITIONS)


def values(rows: list[dict[str, Any]], method: str, field: str, conditions: tuple[str, ...] = CONDITIONS) -> list[float]:
    out = []
    for row in rows:
        if row["method"] == method and row["condition"] in conditions:
            value = float(row.get(field, np.nan))
            if np.isfinite(value):
                out.append(value)
    return out


def average(rows: list[dict[str, Any]], method: str, field: str, conditions: tuple[str, ...] = CONDITIONS) -> float:
    data = values(rows, method, field, conditions)
    return float(np.mean(data)) if data else np.nan


def group_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ("state_rmse", "m_relative_error_mean", "one_step_state_prediction_rmse", "five_step_state_prediction_rmse", "ten_step_state_prediction_rmse", "predicted_alpha_rmse", "parameter_only_alpha_rmse_true_state", "process_residual_rmse_mean", "objective_measurement_cost_mean", "objective_process_cost_mean", "objective_arrival_cost_mean", "objective_inverse_mass_prior_cost_mean", "objective_total_cost_mean", "parameter_bound_hit_rate", "estimator_failure_rate", "solve_time_p50_s", "solve_time_p95_s", "solve_time_max_s", "initialization_probe_relative_lambda_delta")
    out = []
    for group, conditions in (("no_bias", NO_BIAS_CONDITIONS), ("bias_noise_bias", BIAS_CONDITIONS)):
        for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD):
            subset = [row for row in rows if row["method"] == method and row["condition"] in conditions]
            record: dict[str, Any] = {"group": group, "method": method, "runs": len(subset)}
            for field in fields:
                record[field] = average(subset, method, field, conditions)
            out.append(record)
    return out


def save_figures(rows: list[dict[str, Any]], groups: list[dict[str, Any]], root: Path) -> None:
    figs = root / "figs"; figs.mkdir(exist_ok=True)
    methods = (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD); names = {BASELINE_METHOD: "UKF+NLS", SINGLE_METHOD: "single MHE", MULTIPLE_METHOD: "corrected multiple MHE"}
    fig, ax = plt.subplots(figsize=(8, 4)); ax.bar([names[m] for m in methods], [average(rows, m, "predicted_alpha_rmse") for m in methods]); ax.set_ylabel("full alpha prediction RMSE"); ax.set_title("Stage 10E corrected MHE"); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(figs / "01_alpha_rmse.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4));
    for index, group in enumerate(("no_bias", "bias_noise_bias")):
        selected = {row["method"]: row for row in groups if row["group"] == group}
        ax.bar(np.arange(len(methods)) + (index - 0.5) * 0.36, [selected[m]["predicted_alpha_rmse"] for m in methods], width=0.36, label=group)
    ax.set_xticks(np.arange(len(methods)), [names[m] for m in methods]); ax.set_ylabel("alpha RMSE"); ax.set_title("Bias-group comparison"); ax.legend(); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(figs / "02_bias_group_alpha.png", dpi=150); plt.close(fig)
    corrected = [row for row in rows if row["method"] == MULTIPLE_METHOD]
    fig, ax = plt.subplots(figsize=(8, 4)); ax.scatter(range(len(corrected)), [float(row["solve_time_p95_s"]) for row in corrected], label="p95 solve time"); ax.scatter(range(len(corrected)), [float(row["process_residual_rmse_mean"]) for row in corrected], label="process residual RMS"); ax.set_yscale("log"); ax.set_xlabel("condition/seed run"); ax.set_title("Corrected multiple MHE cost"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(figs / "03_runtime_process.png", dpi=150); plt.close(fig)


def write_report(root: Path, rows: list[dict[str, Any]], groups: list[dict[str, Any]], gate_result: dict[str, Any]) -> None:
    alpha = {method: average(rows, method, "predicted_alpha_rmse") for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD)}
    state = {method: average(rows, method, "state_rmse") for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD)}
    mass = {method: average(rows, method, "m_relative_error_mean") for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD)}
    corrected_no_bias = next(row for row in groups if row["group"] == "no_bias" and row["method"] == MULTIPLE_METHOD)
    corrected_bias = next(row for row in groups if row["group"] == "bias_noise_bias" and row["method"] == MULTIPLE_METHOD)
    time_p95 = average(rows, MULTIPLE_METHOD, "solve_time_p95_s")
    bias_dominant = corrected_bias["predicted_alpha_rmse"] > 1.5 * corrected_no_bias["predicted_alpha_rmse"] and corrected_bias["state_rmse"] > 1.5 * corrected_no_bias["state_rmse"]
    lines = ["# Stage 10E: Corrected Multiple-Shooting MHE Benchmark", "", "## Protocol", "", "- Reused saved Stage 10B UKF+NLS and single-shooting rows. Only the corrected multiple-shooting inverse-mass MHE was rerun.", "- The only source change is the Stage 10D rolling-arrival index correction. Lambda-only estimation, nominal k/b_r, 70-transition window, 10-step cadence, weights, bounds, scaling, solver settings, replay, metrics, and gate are unchanged.", "- No bias state was added. `noise_bias` is the bias/noise-bias group; all remaining conditions form the no-bias group.", "", "## Offline gate", "", f"Gate: **{'PASS' if gate_result['passed'] else 'FAIL'}**. Checks: `{gate_result['checks']}`.", f"Overall alpha RMSE: UKF+NLS={alpha[BASELINE_METHOD]:.6g}, single={alpha[SINGLE_METHOD]:.6g}, corrected multiple={alpha[MULTIPLE_METHOD]:.6g}.", f"Overall state RMSE: UKF+NLS={state[BASELINE_METHOD]:.6g}, single={state[SINGLE_METHOD]:.6g}, corrected multiple={state[MULTIPLE_METHOD]:.6g}.", f"Overall mass relative error: UKF+NLS={mass[BASELINE_METHOD]:.6g}, single={mass[SINGLE_METHOD]:.6g}, corrected multiple={mass[MULTIPLE_METHOD]:.6g}.", "", "## Bias split", "", f"- Corrected MHE no-bias alpha/state RMSE: {corrected_no_bias['predicted_alpha_rmse']:.6g} / {corrected_no_bias['state_rmse']:.6g}.", f"- Corrected MHE noise-bias alpha/state RMSE: {corrected_bias['predicted_alpha_rmse']:.6g} / {corrected_bias['state_rmse']:.6g}.", f"- Missing bias model is {'the dominant remaining limitation in this split' if bias_dominant else 'not established as the dominant limitation by this split'}.", "", "## Required conclusions", "", f"1. **How much of Stage 10C failure was caused by the arrival-index bug?** The pre-fix Stage 10C result is invalid as a performance comparison; Stage 10E is the corrected measurement. The corrected overall alpha RMSE is {alpha[MULTIPLE_METHOD]:.6g} versus the pre-fix 11.2992.", f"2. **Does corrected MHE beat UKF+NLS?** {'Yes under the offline gate.' if gate_result['checks']['alpha_mean_clearly_better_than_baseline'] and gate_result['checks']['state_not_materially_worse'] else 'No under the specified gate.'}", f"3. **Is bias mismatch now the main limitation?** {'Yes in the observed split.' if bias_dominant else 'No: the available no-bias versus noise-bias split does not establish it as dominant.'}", f"4. **Is solve time usable?** {'Yes.' if gate_result['checks']['solve_time_usable'] else f'No: average per-run p95 update time is {time_p95:.6g} s against the 0.20 s gate.'}", f"5. **Should the next step be bias-aware MHE or branch closure?** {'A bias-aware MHE is supported as the next isolated test.' if bias_dominant else 'Close the fixed-weight MHE branch unless a separate bias-aware formulation is explicitly authorized; this stage does not add one.'}", "", "## Closed loop", ""]
    lines.append("No closed-loop run or GIF was created because the offline gate failed." if not gate_result["passed"] else "The offline gate passed; closed-loop validation is required by the protocol.")
    (root / "stage10e_report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    root = OUTPUT; root.mkdir(parents=True, exist_ok=True); (root / "figs").mkdir(exist_ok=True); (root / "videos").mkdir(exist_ok=True)
    replay = load_replay(DEFAULT_REPLAY); config = load_experiment_config(DEFAULT_CONFIG); rows = read_stage10b_rows(DEFAULT_STAGE10B)
    for condition in CONDITIONS:
        params = stage9j_overrides(config, condition)["model_params"]
        for seed in SEEDS:
            print(f"[stage10e] corrected MHE/{condition}/seed{seed}", flush=True)
            rows.append(evaluate_multiple(condition, seed, arrays(replay[(condition, seed)]), params))
            write_dict_csv(root / "offline_per_run.csv", rows)
    summary = aggregate(rows); groups = group_summary(rows); gate_result = gate(summary)
    write_dict_csv(root / "offline_summary.csv", summary); write_dict_csv(root / "bias_group_summary.csv", groups); (root / "offline_gate.json").write_text(json.dumps(gate_result, indent=2)); save_figures(rows, groups, root); write_report(root, rows, groups, gate_result)
    (root / "command.txt").write_text(f"conda run -n mpc_learn python scripts/{Path(__file__).name}\n")


if __name__ == "__main__":
    main()
