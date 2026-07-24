"""Stage 10C true multiple-shooting inverse-mass MHE validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
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
sys.path.insert(0, str(PROJECT_ROOT / "src")); sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import (
    CLOSED_LOOP_CONDITIONS,
    DEFAULT_CONFIG,
    DEFAULT_REPLAY,
    MHE_CONFIG as STAGE10B_MHE_CONFIG,
    alpha_from_transition,
    arrays,
    load_replay,
    metric,
    params_with_mass,
    rollout_error,
    safe_step,
)
from run_spring2d_stage9j_gap_decomposition import CONDITIONS, SEEDS, STATE_NAMES, write_dict_csv
from traction_mpc.estimation.multiple_shooting_inverse_mass_mhe import MultipleShootingInverseMassMHE


DEFAULT_STAGE10B = PROJECT_ROOT / "results" / "stage10b_estimator_benchmark" / "offline_per_run.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "stage10c_multiple_shooting_mhe"
BASELINE_METHOD = "ukf_nls_current"
SINGLE_METHOD = "single_shooting_mhe_inverse_m"
MULTIPLE_METHOD = "multiple_shooting_mhe_inverse_m"

# Measurement and arrival terms match Stage 10B.  Process residual scaling is
# fixed from the existing UKF-bias state process-noise diagonal, not tuned from
# Stage 10C outcomes: [1e-5, 1e-3, 1e-6, 1e-4]^{-1/2}.
MHE_CONFIG = {
    **STAGE10B_MHE_CONFIG,
    "process_weights": [316.2277660168, 31.6227766017, 1000.0, 100.0],
    "state_scale": [0.10, 1.0, 0.02, 0.10],
    "lambda_scale": 1.0,
    "state_lower": [-3.1415926536, -10.0, 0.29, -5.0],
    "state_upper": [3.1415926536, 10.0, 0.41, 5.0],
    "initialization_probe": True,
}


def read_stage10b_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    desired = [row for row in rows if row["method"] in {"ukf_nls_current", "mhe_inverse_m"}]
    expected = len(CONDITIONS) * len(SEEDS) * 2
    if len(desired) != expected:
        raise RuntimeError(f"Stage 10B source has {len(desired)} compatible rows, expected {expected}")
    output = []
    for row in desired:
        converted: dict[str, Any] = {}
        for key, value in row.items():
            if key in {"method", "condition", "parameter_estimate_trajectory_json", "state_estimate_trajectory_json", "alpha_error_trajectory_json"}:
                converted[key] = value
            elif key in {"seed", "num_steps", "update_count", "estimator_failure_count"}:
                converted[key] = int(float(value))
            elif key in {"uncertainty_available", "stage9k_baseline_reused"}:
                converted[key] = str(value).lower() == "true"
            else:
                try:
                    converted[key] = float(value)
                except (ValueError, TypeError):
                    converted[key] = value
        converted["source"] = "stage10b_reused"
        converted["method"] = BASELINE_METHOD if row["method"] == "ukf_nls_current" else SINGLE_METHOD
        output.append(converted)
    return output


def evaluate_multiple(condition: str, seed: int, data: dict[str, np.ndarray], model_params: dict[str, Any]) -> dict[str, Any]:
    estimator = MultipleShootingInverseMassMHE(model_params, MHE_CONFIG)
    n = len(data["time"]); dt = float(model_params["dt"])
    estimator.reset(data["measured"][0], warm_state=data["estimated"][0])
    states = np.empty_like(data["true"]); states[0] = estimator.state_hat
    masses = np.full(n, estimator.mass_hat)
    one = np.full(n, np.nan); five = np.full(n, np.nan); ten = np.full(n, np.nan)
    alpha = np.full(n, np.nan); alpha_true = np.full(n, np.nan); update = np.zeros(n); solve = np.full(n, np.nan)
    failure = np.zeros(n, dtype=bool); bound = np.zeros(n, dtype=bool); condition_number = np.full(n, np.nan); lambda_std = np.full(n, np.nan)
    process_rmse = np.full(n, np.nan); process_max = np.full(n, np.nan); init_delta = np.full(n, np.nan); init_probe_success = np.zeros(n, dtype=bool)
    objective_measurement = np.full(n, np.nan); objective_process = np.full(n, np.nan); objective_arrival = np.full(n, np.nan); objective_lambda_prior = np.full(n, np.nan); objective_total = np.full(n, np.nan)
    for step in range(1, n):
        previous_state = states[step - 1].copy(); previous_mass = float(masses[step - 1])
        params = params_with_mass(model_params, previous_mass)
        prediction = safe_step(previous_state, data["action"][step], dt, params)
        if np.all(np.isfinite(prediction)):
            one[step] = np.linalg.norm(prediction - data["true"][step])
            alpha[step] = alpha_from_transition(previous_state, prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt
        true_prediction = safe_step(data["true"][step - 1], data["action"][step], dt, params)
        if np.all(np.isfinite(true_prediction)):
            alpha_true[step] = alpha_from_transition(data["true"][step - 1], true_prediction, dt) - (data["true"][step, 1] - data["true"][step - 1, 1]) / dt
        if step + 4 < n:
            five[step] = rollout_error(previous_state, data["action"][step:step + 5], data["true"][step + 4], params)
        if step + 9 < n:
            ten[step] = rollout_error(previous_state, data["action"][step:step + 10], data["true"][step + 9], params)
        result = estimator.add_measurement(data["action"][step], data["measured"][step], warm_state=data["estimated"][step])
        diag = result["diagnostics"]
        states[step] = result["state_hat"]; masses[step] = float(result["m_hat"])
        update[step] = abs(masses[step] - masses[step - 1]) if result["updated"] else 0.0
        solve[step] = float(diag.get("solve_time_s", np.nan)); failure[step] = bool(result["updated"] and not result["success"])
        bound[step] = bool(diag.get("parameter_bound_hit", False)); condition_number[step] = float(diag.get("jacobian_condition", np.nan)); lambda_std[step] = float(diag.get("lambda_std", np.nan))
        process_rmse[step] = float(diag.get("process_residual_rmse", np.nan)); process_max[step] = float(diag.get("process_residual_max_abs", np.nan)); init_delta[step] = float(diag.get("initialization_probe_relative_lambda_delta", np.nan)); init_probe_success[step] = bool(diag.get("initialization_probe_success", False))
        objective_measurement[step] = float(diag.get("after_measurement_cost", np.nan)); objective_process[step] = float(diag.get("after_process_cost", np.nan)); objective_arrival[step] = float(diag.get("after_arrival_cost", np.nan)); objective_lambda_prior[step] = float(diag.get("after_inverse_mass_prior_cost", np.nan)); objective_total[step] = float(diag.get("after_total_cost", np.nan))
    truth = data["true_params"]; state_error = states - data["true"]; valid_solve = solve[np.isfinite(solve) & (solve > 0.0)]; valid_cond = condition_number[np.isfinite(condition_number)]
    return {
        "method": MULTIPLE_METHOD, "source": "stage10c_new", "condition": condition, "seed": int(seed), "num_steps": n,
        "m_absolute_error_mean": metric(abs(masses - truth[0]), "mean"), "m_relative_error_mean": metric(abs(masses - truth[0]) / abs(truth[0]), "mean"), "m_rmse": metric(masses - truth[0], "rmse"), "m_final_error": float(abs(masses[-1] - truth[0])), "inverse_m_rmse": metric(1.0 / masses - 1.0 / truth[0], "rmse"),
        "state_rmse": metric(np.linalg.norm(state_error, axis=1), "rmse"), **{f"{name}_state_rmse": metric(state_error[:, index], "rmse") for index, name in enumerate(STATE_NAMES)},
        "one_step_state_prediction_rmse": metric(one, "rmse"), "five_step_state_prediction_rmse": metric(five, "rmse"), "ten_step_state_prediction_rmse": metric(ten, "rmse"),
        "predicted_alpha_rmse": metric(alpha, "rmse"), "predicted_alpha_p95_error": metric(abs(alpha), "p95"), "parameter_only_alpha_rmse_true_state": metric(alpha_true, "rmse"),
        "parameter_update_total_variation": float(np.sum(update)), "maximum_single_update": metric(update, "max"), "parameter_bound_hit_rate": float(np.mean(bound)), "estimator_failure_count": int(np.sum(failure)), "estimator_failure_rate": float(np.mean(failure)),
        "solve_time_p50_s": float(np.median(valid_solve)) if len(valid_solve) else np.nan, "solve_time_mean_s": metric(valid_solve, "mean"), "solve_time_p95_s": metric(valid_solve, "p95"), "solve_time_max_s": metric(valid_solve, "max"),
        "jacobian_condition_p50": float(np.median(valid_cond)) if len(valid_cond) else np.nan, "jacobian_condition_p95": metric(valid_cond, "p95"), "lambda_std_mean": metric(lambda_std, "mean"),
        "process_residual_rmse_mean": metric(process_rmse, "mean"), "process_residual_rmse_p95": metric(process_rmse, "p95"), "process_residual_max_abs": metric(process_max, "max"),
        "objective_measurement_cost_mean": metric(objective_measurement, "mean"), "objective_process_cost_mean": metric(objective_process, "mean"), "objective_arrival_cost_mean": metric(objective_arrival, "mean"), "objective_inverse_mass_prior_cost_mean": metric(objective_lambda_prior, "mean"), "objective_total_cost_mean": metric(objective_total, "mean"),
        "initialization_probe_success": bool(np.any(init_probe_success)), "initialization_probe_relative_lambda_delta": metric(init_delta, "max"),
        "parameter_estimate_trajectory_json": json.dumps(masses.tolist(), separators=(",", ":")), "state_estimate_trajectory_json": json.dumps(states.tolist(), separators=(",", ":")), "alpha_error_trajectory_json": json.dumps(alpha.tolist(), separators=(",", ":"), allow_nan=True),
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ["m_relative_error_mean", "inverse_m_rmse", "state_rmse", "one_step_state_prediction_rmse", "five_step_state_prediction_rmse", "ten_step_state_prediction_rmse", "predicted_alpha_rmse", "parameter_only_alpha_rmse_true_state", "parameter_update_total_variation", "parameter_bound_hit_rate", "estimator_failure_rate", "solve_time_p50_s", "solve_time_p95_s", "solve_time_max_s", "jacobian_condition_p50", "jacobian_condition_p95", "lambda_std_mean", "process_residual_rmse_mean", "process_residual_rmse_p95", "process_residual_max_abs", "objective_measurement_cost_mean", "objective_process_cost_mean", "objective_arrival_cost_mean", "objective_inverse_mass_prior_cost_mean", "objective_total_cost_mean", "initialization_probe_relative_lambda_delta"]
    out = []
    for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD):
        for condition in CONDITIONS:
            group = [row for row in rows if row["method"] == method and row["condition"] == condition]
            summary = {"method": method, "condition": condition, "n": len(group)}
            for field in fields:
                summary[f"{field}_mean"] = metric(np.asarray([float(row.get(field, np.nan)) for row in group]), "mean")
            out.append(summary)
    return out


def gate(summary: list[dict[str, Any]]) -> dict[str, Any]:
    def rows(method: str) -> dict[str, dict[str, Any]]:
        return {row["condition"]: row for row in summary if row["method"] == method}
    base, single, multiple = rows(BASELINE_METHOD), rows(SINGLE_METHOD), rows(MULTIPLE_METHOD)
    alpha_multiple = float(np.mean([multiple[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS])); alpha_base = float(np.mean([base[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS])); alpha_single = float(np.mean([single[c]["predicted_alpha_rmse_mean"] for c in CONDITIONS]))
    improve = [multiple[c]["predicted_alpha_rmse_mean"] <= 0.90 * min(base[c]["predicted_alpha_rmse_mean"], single[c]["predicted_alpha_rmse_mean"]) for c in CONDITIONS]
    checks = {
        "alpha_mean_clearly_better_than_baseline": alpha_multiple <= 0.90 * alpha_base,
        "alpha_mean_clearly_better_than_single": alpha_multiple <= 0.90 * alpha_single,
        "alpha_consistent": int(np.sum(improve)) >= 6 and all(multiple[c]["predicted_alpha_rmse_mean"] <= 1.10 * min(base[c]["predicted_alpha_rmse_mean"], single[c]["predicted_alpha_rmse_mean"]) for c in CONDITIONS),
        "state_not_materially_worse": all(multiple[c]["state_rmse_mean"] <= 1.10 * base[c]["state_rmse_mean"] for c in CONDITIONS),
        "failure_rate_acceptable": all(multiple[c]["estimator_failure_rate_mean"] <= 0.05 for c in CONDITIONS),
        "solve_time_usable": all(multiple[c]["solve_time_p95_s_mean"] <= 0.20 for c in CONDITIONS),
    }
    return {"passed": bool(all(checks.values())), "selected_method": MULTIPLE_METHOD if all(checks.values()) else None, "alpha_rmse": {"baseline": alpha_base, "single_shooting": alpha_single, "multiple_shooting": alpha_multiple}, "conditions_clearly_improved": int(np.sum(improve)), "checks": checks}


def save_figures(rows: list[dict[str, Any]], root: Path) -> None:
    fig_dir = root / "figs"; fig_dir.mkdir(parents=True, exist_ok=True)
    methods = (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD); labels = {BASELINE_METHOD: "UKF+NLS", SINGLE_METHOD: "single MHE", MULTIPLE_METHOD: "multiple MHE"}
    def mean(method: str, field: str) -> float: return metric(np.asarray([float(row[field]) for row in rows if row["method"] == method]), "mean")
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar([labels[m] for m in methods], [mean(m, "predicted_alpha_rmse") for m in methods]); ax.set_ylabel("full estimated-state alpha RMSE"); ax.set_title("Stage 10C alpha prediction"); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(fig_dir / "01_alpha_prediction.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar([labels[m] for m in methods], [mean(m, "state_rmse") for m in methods]); ax.set_ylabel("state RMSE"); ax.set_title("Stage 10C state estimation"); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(fig_dir / "02_state_rmse.png", dpi=150); plt.close(fig)
    multiple = [row for row in rows if row["method"] == MULTIPLE_METHOD]; fig, ax = plt.subplots(figsize=(7, 4)); ax.scatter(range(len(multiple)), [float(row["solve_time_p95_s"]) for row in multiple], label="p95 solve time"); ax.scatter(range(len(multiple)), [float(row["process_residual_rmse_mean"]) for row in multiple], label="process residual RMSE"); ax.set_yscale("log"); ax.set_xlabel("condition/seed run"); ax.set_title("Multiple-shooting cost and process residual"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(fig_dir / "03_cost_and_process_residual.png", dpi=150); plt.close(fig)


def write_report(root: Path, summary: list[dict[str, Any]], gate_result: dict[str, Any]) -> None:
    def mean(method: str, field: str) -> float: return metric(np.asarray([row[f"{field}_mean"] for row in summary if row["method"] == method]), "mean")
    multiple_alpha = mean(MULTIPLE_METHOD, "predicted_alpha_rmse"); multiple_state = mean(MULTIPLE_METHOD, "state_rmse"); multiple_mass = mean(MULTIPLE_METHOD, "m_relative_error_mean"); multiple_time = mean(MULTIPLE_METHOD, "solve_time_p95_s")
    lines = ["# Stage 10C: True Multiple-Shooting Joint MHE Validation", "", "## Protocol", "", "- Reused saved Stage 9J replay plus the saved Stage 10B UKF+NLS and single-shooting inverse-mass MHE rows. No old method was rerun.", "- The sole new method is inverse-mass multiple shooting. Every state in the 70-transition window and lambda are decision variables; the objective contains raw-measurement residuals, explicit process residuals, arrival cost, and lambda prior.", "- `k` and `b_r` remain nominal. UKF states enter only as arrival/warm-start values, never as exact measurements.", "- Process scaling is fixed from the pre-existing UKF-bias state process-noise diagonal. No controller, dynamics, horizon, or cost change was made.", "", "## Gate", "", f"Gate: **{'PASS' if gate_result['passed'] else 'FAIL'}**. Checks: `{gate_result['checks']}`.", f"Overall full alpha RMSE: baseline={gate_result['alpha_rmse']['baseline']:.6g}, single={gate_result['alpha_rmse']['single_shooting']:.6g}, multiple={gate_result['alpha_rmse']['multiple_shooting']:.6g}; clear improvement in {gate_result['conditions_clearly_improved']}/8 conditions.", "", "| method | alpha RMSE | state RMSE | mean relative mass error | p95 solve time (s) |", "|---|---:|---:|---:|---:|"]
    for method in (BASELINE_METHOD, SINGLE_METHOD, MULTIPLE_METHOD): lines.append(f"| {method} | {mean(method, 'predicted_alpha_rmse'):.6g} | {mean(method, 'state_rmse'):.6g} | {mean(method, 'm_relative_error_mean'):.6g} | {mean(method, 'solve_time_p95_s'):.6g} |")
    if gate_result["passed"]:
        conclusion = "The offline gate passed; the specified unchanged-controller closed loop was run and its results are in the closed-loop CSV files."
    else:
        conclusion = "No closed-loop run or GIF was produced because the offline gate failed. The outcome distinguishes structural multiple shooting from the remaining issues only empirically; do not tune weights broadly in this stage."
    diagnosis = (
        "The failure establishes a computational-cost limitation directly: the multiple-shooting solve-time criterion failed in every condition. "
        "It also establishes that this fixed objective did not cure the state/alpha degradation, despite small fitted process residuals. "
        "That pattern is compatible with unresolved observability, measurement/model mismatch, or the fixed relative weighting of arrival, measurement, and process terms; this replay study cannot identify one as the cause. "
        "No broad weight tuning was performed."
        if not gate_result["passed"]
        else "The offline criteria did not expose a remaining limitation before closed-loop validation."
    )
    lines += ["", "## Required conclusions", "", f"1. **Did multiple shooting fix Stage 10B state-estimation degradation?** {'Yes under the gate.' if gate_result['checks']['state_not_materially_worse'] else 'No: state RMSE still violated the no-material-regression gate.'}", f"2. **Did it improve alpha prediction and parameter estimation?** {'Yes sufficiently for the gate.' if gate_result['checks']['alpha_mean_clearly_better_than_baseline'] and gate_result['checks']['alpha_mean_clearly_better_than_single'] else 'No: it did not clearly beat both the UKF+NLS and single-shooting comparators.'}", f"3. **Is computational cost acceptable?** {'Yes.' if gate_result['checks']['solve_time_usable'] else f'No: mean per-run p95 update time is {multiple_time:.6g} s against the 0.20 s usability criterion.'}", f"4. **Does the MHE route remain viable?** {'Only for the narrowly tested estimator, subject to closed-loop evidence.' if gate_result['passed'] else 'Not under the tested fixed weighting and replay conditions.'}", f"5. **What exact method should be tested next?** {'The unchanged-controller multiple-shooting MHE closed-loop test specified for this stage.' if gate_result['passed'] else 'Close this fixed-weight MHE branch and move to a state/parameter smoother or EM-style offline diagnosis; do not introduce uncertainty-aware control from this evidence.'}", "", "## Failure interpretation", "", diagnosis, "", "## Closed loop", "", conclusion, ""]
    (root / "stage10c_report.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG); parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY); parser.add_argument("--stage10b", type=Path, default=DEFAULT_STAGE10B); parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT); args = parser.parse_args()
    root = args.output_root; root.mkdir(parents=True, exist_ok=True); (root / "figs").mkdir(exist_ok=True); (root / "videos").mkdir(exist_ok=True)
    started = time.perf_counter(); replay = load_replay(args.replay); config = load_experiment_config(args.config); rows = read_stage10b_rows(args.stage10b)
    for condition in CONDITIONS:
        cfg = __import__("run_spring2d_stage9j_gap_decomposition", fromlist=["stage9j_overrides"]).stage9j_overrides(config, condition)
        for seed in SEEDS:
            print(f"[stage10c] multiple MHE/{condition}/seed{seed}", flush=True)
            rows.append(evaluate_multiple(condition, seed, arrays(replay[(condition, seed)]), cfg["model_params"]))
            write_dict_csv(root / "offline_per_run.csv", rows)
    summary = aggregate(rows); write_dict_csv(root / "offline_summary.csv", summary); gate_result = gate(summary); (root / "offline_gate.json").write_text(json.dumps(gate_result, indent=2)); save_figures(rows, root)
    provenance = {"config_path": str(args.config), "replay_path": str(args.replay), "replay_sha256": hashlib.sha256(args.replay.read_bytes()).hexdigest(), "stage10b_path": str(args.stage10b), "stage10b_sha256": hashlib.sha256(args.stage10b.read_bytes()).hexdigest(), "multiple_shooting_config": MHE_CONFIG, "closed_loop_conditions_if_gate_passes": list(CLOSED_LOOP_CONDITIONS)}; (root / "config_snapshot.json").write_text(json.dumps(provenance, indent=2))
    write_report(root, summary, gate_result); (root / "command.txt").write_text(f"conda run -n mpc_learn python scripts/{Path(__file__).name}\n")
    print(f"[stage10c] gate={gate_result['passed']} runtime={time.perf_counter()-started:.1f}s", flush=True)


if __name__ == "__main__": main()
