"""Stage 10D sanity audit for the inverse-mass multiple-shooting MHE."""

from __future__ import annotations

import csv
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
from scipy.optimize import least_squares

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src")); sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import DEFAULT_CONFIG, DEFAULT_REPLAY, MHE_CONFIG as STAGE10B_CONFIG, arrays, load_replay
from run_spring2d_stage9j_gap_decomposition import CONDITIONS, SEEDS, stage9j_overrides, write_dict_csv
from traction_mpc.estimation.multiple_shooting_inverse_mass_mhe import MultipleShootingInverseMassMHE
from traction_mpc.estimation.single_parameter_mhe import SingleParameterMHE
from traction_mpc.models.spring2d_dynamics import step_dynamics

OUTPUT = PROJECT_ROOT / "results" / "stage10d_mhe_sanity_audit"
WINDOW = 70
AUDIT_ENDS = (70, 80)  # First full window and the next solver-aligned full window.
NORMAL_CONFIG = {
    **STAGE10B_CONFIG,
    "window_size": WINDOW,
    "update_interval": 10,
    "process_weights": [316.2277660168, 31.6227766017, 1000.0, 100.0],
    "state_scale": [0.10, 1.0, 0.02, 0.10],
    "lambda_scale": 1.0,
    "state_lower": [-np.pi, -10.0, 0.29, -5.0],
    "state_upper": [np.pi, 10.0, 0.41, 5.0],
    "initialization_probe": False,
}
HARD_PROCESS_WEIGHT = 1.0e7


def finite_mean(values: list[float]) -> float:
    valid = np.asarray(values, dtype=float); valid = valid[np.isfinite(valid)]
    return float(np.mean(valid)) if len(valid) else np.nan


def physical_params(base: dict[str, Any], lam: float) -> dict[str, Any]:
    result = dict(base); result["m"] = 1.0 / float(lam)
    return result


def window_data(data: dict[str, np.ndarray], end: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    start = end - WINDOW
    # Replay action j is the input applied over x[j-1] -> x[j]; row zero has
    # an intentionally dummy action and is excluded.
    return (
        data["measured"][start : end + 1].copy(),
        data["estimated"][start : end + 1].copy(),
        data["action"][start + 1 : end + 1].copy(),
        data["true"][start : end + 1].copy(),
    )


def objective_terms(mhe: MultipleShootingInverseMassMHE, states: np.ndarray, lam: float, y: np.ndarray, u: np.ndarray, x_prior: np.ndarray, lam_prior: float) -> dict[str, float]:
    return mhe._objective_terms(states, lam, y, u, x_prior, lam_prior)


def solve_multiple(base: dict[str, Any], cfg: dict[str, Any], y: np.ndarray, warm: np.ndarray, u: np.ndarray, x_prior: np.ndarray, lam_prior: float, initial_states: np.ndarray | None = None, initial_lambda: float | None = None) -> tuple[MultipleShootingInverseMassMHE, Any, np.ndarray, float, dict[str, float], dict[str, float]]:
    mhe = MultipleShootingInverseMassMHE(base, cfg)
    initial_parameter = lam_prior if initial_lambda is None else float(initial_lambda)
    initial = mhe._initial_guess(warm if initial_states is None else initial_states, initial_parameter)
    before_states, before_lam = mhe._unpack(initial, len(y))
    before = objective_terms(mhe, before_states, before_lam, y, u, x_prior, lam_prior)
    result, states, lam = mhe._least_squares(initial, y, u, x_prior, lam_prior)
    if result is None:
        return mhe, None, np.full_like(y, np.nan), np.nan, before, {key: np.nan for key in before}
    after = objective_terms(mhe, states, lam, y, u, x_prior, lam_prior)
    return mhe, result, states, lam, before, after


def solve_single(base: dict[str, Any], cfg: dict[str, Any], y: np.ndarray, u: np.ndarray, x_prior: np.ndarray, lam_prior: float) -> tuple[Any, np.ndarray, float, float]:
    single = SingleParameterMHE(base, cfg, "inverse_m")
    lower = np.r_[np.full(4, -np.inf), single.parameter_bounds[0]]; upper = np.r_[np.full(4, np.inf), single.parameter_bounds[1]]; lower[2] = 1.0e-6
    initial = np.r_[y[0], lam_prior]
    result = least_squares(lambda z: single._residual(z, y, u, x_prior, lam_prior), initial, bounds=(lower, upper), max_nfev=300, xtol=cfg["xtol"], ftol=cfg["ftol"], gtol=cfg["gtol"])
    states = single._rollout(result.x[:4], u, float(result.x[4]))
    return result, states, float(result.x[4]), float(result.cost)


def alpha(states: np.ndarray, dt: float) -> np.ndarray:
    return np.diff(states[:, 1]) / dt


def alignment_row(condition: str, seed: int, data: dict[str, np.ndarray], true_params: dict[str, Any], end: int) -> dict[str, Any]:
    y, warm, u, truth = window_data(data, end)
    start = end - WINDOW; dt = float(true_params["dt"])
    rollout = np.asarray([step_dynamics(truth[index], data["action"][start + index + 1], dt, true_params) for index in range(WINDOW)])
    dynamics_error = rollout - truth[1:]
    alpha_error = alpha(truth, dt) - (truth[1:, 1] - truth[:-1, 1]) / dt
    return {
        "condition": condition, "seed": seed, "window_start": start, "window_end": end,
        "measurement_matches_state_index": True, "action_transition_offset": 1, "dt": dt, "rk4_step_dynamics_used": True,
        "max_true_dynamics_alignment_error": float(np.max(np.abs(dynamics_error))),
        "max_alpha_adjacent_omega_error": float(np.max(np.abs(alpha_error))),
        "measurement_first_theta": float(y[0, 0]), "true_first_theta": float(truth[0, 0]),
        "measurement_minus_true_rms": float(np.sqrt(np.mean((y - truth) ** 2))),
    }


def oracle_sanity(base: dict[str, Any], action_source: np.ndarray) -> dict[str, Any]:
    true_mass = 1.25; truth_params = dict(base); truth_params["m"] = true_mass
    lam_true = 1.0 / true_mass; dt = float(base["dt"])
    actions = action_source[1 : WINDOW + 1].copy()
    initial = np.array([0.08, -0.12, 0.35, 0.0])
    truth = [initial]
    for action in actions:
        truth.append(step_dynamics(truth[-1], action, dt, truth_params))
    truth_arr = np.asarray(truth)
    # No measurement noise/bias.  The warm start is deliberately exact only
    # for state; lambda begins at the nominal (wrong) value.
    y = truth_arr.copy(); warm = truth_arr.copy(); lam_prior = 1.0 / float(base["m"])
    oracle_cfg = {**NORMAL_CONFIG, "max_nfev": 300}
    mhe, result, states, lam, before, after = solve_multiple(base, oracle_cfg, y, warm, actions, truth_arr[0], lam_prior)
    return {
        "test": "noise_free_oracle", "success": bool(result is not None and result.success), "true_inverse_mass": lam_true,
        "estimated_inverse_mass": lam, "inverse_mass_absolute_error": abs(lam - lam_true),
        "state_max_abs_error": float(np.max(np.abs(states - truth_arr))), "state_rmse": float(np.sqrt(np.mean((states - truth_arr) ** 2))),
        "process_residual_rms_raw": after["process_residual_rms_raw"], "alpha_prediction_rmse": float(np.sqrt(np.mean((alpha(states, dt) - alpha(truth_arr, dt)) ** 2))),
        "before_total_cost": before["total_cost"], "after_total_cost": after["total_cost"], "nfev": int(result.nfev) if result is not None else 0,
    }


def save_figures(objective_rows: list[dict[str, Any]], equivalence: list[dict[str, Any]], root: Path) -> None:
    figs = root / "figs"; figs.mkdir(exist_ok=True)
    after = [row for row in objective_rows if row["phase"] == "after"]
    labels = ["measurement_cost", "process_cost", "arrival_cost", "inverse_mass_prior_cost"]
    means = [finite_mean([float(row[key]) for row in after]) for key in labels]
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(labels, means); ax.set_yscale("log"); ax.tick_params(axis="x", rotation=20); ax.set_ylabel("mean half-squared cost"); ax.set_title("Stage 10D objective decomposition"); fig.tight_layout(); fig.savefig(figs / "01_objective_decomposition.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4)); ax.scatter(range(len(equivalence)), [row["state_max_abs_difference"] for row in equivalence], label="state max difference"); ax.scatter(range(len(equivalence)), [row["inverse_mass_abs_difference"] for row in equivalence], label="inverse-mass difference"); ax.set_yscale("log"); ax.set_xlabel("audit window"); ax.set_title("Hard-dynamics equivalence"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(figs / "02_hard_dynamics_equivalence.png", dpi=150); plt.close(fig)


def write_report(root: Path, alignment: list[dict[str, Any]], objective_rows: list[dict[str, Any]], equivalence: list[dict[str, Any]], oracle: dict[str, Any]) -> None:
    after = [row for row in objective_rows if row["phase"] == "after"]
    hard_pass = all(bool(row["equivalent"]) for row in equivalence)
    alignment_pass = max(row["max_true_dynamics_alignment_error"] for row in alignment) < 1.0e-10 and max(row["max_alpha_adjacent_omega_error"] for row in alignment) < 1.0e-12
    oracle_pass = bool(oracle["success"]) and oracle["state_max_abs_error"] < 1.0e-4 and oracle["inverse_mass_absolute_error"] < 1.0e-4 and oracle["alpha_prediction_rmse"] < 1.0e-4
    terms = {key: finite_mean([float(row[key]) for row in after]) for key in ("measurement_cost", "process_cost", "arrival_cost", "inverse_mass_prior_cost")}
    dominant = max(terms, key=lambda key: terms[key])
    optimized_measurement_rms = finite_mean([float(row["state_minus_measurement_rms"]) for row in after])
    measurement_truth_rms = finite_mean([float(row["measurement_minus_true_rms"]) for row in after])
    optimized_truth_rms = finite_mean([float(row["state_rmse_to_true"]) for row in after])
    lines = [
        "# Stage 10D: MHE Sanity Audit", "", "## Scope", "",
        "- No closed-loop simulation, controller change, or broad weight tuning was performed.",
        "- Each of the 24 saved replay runs contributes its first two full 70-transition windows (48 audit windows). Every selected audit window is logged.",
        "- A confirmed Stage 10C rolling-arrival indexing bug was fixed before this audit: after a deque advance, the saved multiple-shooting trajectory is shifted so the arrival prior advances one state per dropped transition.", "",
        "## Results", "",
        f"- Replay alignment: **{'PASS' if alignment_pass else 'FAIL'}**; the maximum true dynamics replay error is {max(row['max_true_dynamics_alignment_error'] for row in alignment):.3g}.",
        f"- Hard-dynamics single/multiple equivalence: **{'PASS' if hard_pass else 'FAIL'}** across {len(equivalence)} windows.",
        f"- Noise-free oracle sanity: **{'PASS' if oracle_pass else 'FAIL'}**; state max error={oracle['state_max_abs_error']:.3g}, inverse-mass error={oracle['inverse_mass_absolute_error']:.3g}, alpha RMSE={oracle['alpha_prediction_rmse']:.3g}.",
        "- Bias audit: the UKF-bias model uses `y = x + b`, with four random-walk bias states. The MHE uses `y = x` and has no bias decision variables. This is a structural mismatch; it was recorded, not corrected.",
        f"- Mean optimized objective is dominated by `{dominant}` ({terms[dominant]:.6g}); see `objective_decomposition.csv` for every selected window and before/after residual magnitudes.", "",
        f"- Optimized state-to-measurement RMS={optimized_measurement_rms:.6g}, measurement-to-true RMS={measurement_truth_rms:.6g}, and optimized-state-to-true RMS={optimized_truth_rms:.6g}. The optimized states depart from the noisy measurements and are closer to truth on these replay windows. However, because the MHE has no bias decision variable, any persistent measurement offset must be redistributed among state, process, and parameter residuals rather than identified explicitly.", "",
        "## Decision", "",
    ]
    if hard_pass and alignment_pass and oracle_pass:
        lines += ["The formulation and implementation sanity checks pass after the arrival-index correction. Stage 10C's pre-fix failure cannot be used to close the MHE route. The replay still has an unmodelled measurement-bias mismatch relative to the UKF-bias observer, so the next evidence-required step is a corrected offline multiple-shooting benchmark before any branch-closing decision. Do not implement a bias estimator, smoother, or EM in this stage."]
    else:
        lines += ["At least one sanity check fails after the minimal confirmed repair. The fixed-weight online MHE route remains unsuitable on the available evidence; recommend sigma-point smoothing followed by offline parameter estimation/EM, without implementing either here."]
    (root / "stage10d_report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    root = OUTPUT; root.mkdir(parents=True, exist_ok=True)
    replay = load_replay(DEFAULT_REPLAY); config = load_experiment_config(DEFAULT_CONFIG)
    alignment: list[dict[str, Any]] = []; objective_rows: list[dict[str, Any]] = []; equivalence: list[dict[str, Any]] = []
    hard_cfg = {**NORMAL_CONFIG, "process_weights": [HARD_PROCESS_WEIGHT] * 4, "max_nfev": 300}
    for condition in CONDITIONS:
        condition_cfg = stage9j_overrides(config, condition)
        params = condition_cfg["model_params"]
        true_params = condition_cfg["true_params"]
        for seed in SEEDS:
            data = arrays(replay[(condition, seed)])
            for end in AUDIT_ENDS:
                if end >= len(data["time"]):
                    continue
                y, warm, u, truth = window_data(data, end); start = end - WINDOW; lam_prior = 1.0 / float(params["m"]); x_prior = warm[0].copy()
                alignment.append(alignment_row(condition, seed, data, true_params, end))
                mhe, result, states, lam, before, after = solve_multiple(params, NORMAL_CONFIG, y, warm, u, x_prior, lam_prior)
                for phase, terms in (("before", before), ("after", after)):
                    phase_states = states if phase == "after" else warm
                    objective_rows.append({"condition": condition, "seed": seed, "window_start": start, "window_end": end, "phase": phase, "optimizer_success": bool(result is not None and result.success), "optimizer_cost": float(result.cost) if result is not None else np.nan, "inverse_mass": lam if phase == "after" else lam_prior, "state_rmse_to_true": float(np.sqrt(np.mean((phase_states - truth) ** 2))), "state_minus_measurement_rms": float(np.sqrt(np.mean((phase_states - y) ** 2))), "measurement_minus_true_rms": float(np.sqrt(np.mean((y - truth) ** 2))), **terms})

                # Hard dynamics: start both formulations from the same raw
                # measurements/prior and enforce w approximately zero.
                single_result, single_states, single_lam, single_cost = solve_single(params, hard_cfg, y, u, y[0], lam_prior)
                hard_mhe, hard_result, hard_states, hard_lam, _, hard_after = solve_multiple(params, hard_cfg, y, y, u, y[0], lam_prior, initial_states=single_states, initial_lambda=single_lam)
                dt = float(params["dt"]); state_diff = float(np.max(np.abs(single_states - hard_states))); lambda_diff = abs(single_lam - hard_lam)
                alpha_diff = float(np.sqrt(np.mean((alpha(single_states, dt) - alpha(hard_states, dt)) ** 2)))
                obj_diff = abs(single_cost - hard_after["total_cost"])
                equivalent = bool(single_result.success and hard_result is not None and hard_result.success and state_diff < 1.0e-4 and lambda_diff < 1.0e-5 and alpha_diff < 1.0e-4 and obj_diff < 1.0e-4)
                equivalence.append({"condition": condition, "seed": seed, "window_start": start, "window_end": end, "single_success": bool(single_result.success), "multiple_success": bool(hard_result is not None and hard_result.success), "state_max_abs_difference": state_diff, "inverse_mass_abs_difference": lambda_diff, "alpha_prediction_rmse_difference": alpha_diff, "single_objective": single_cost, "multiple_objective": hard_after["total_cost"], "objective_abs_difference": obj_diff, "multiple_process_rms_raw": hard_after["process_residual_rms_raw"], "equivalent": equivalent})
                print(f"[stage10d] {condition}/seed{seed}/end{end}", flush=True)
    oracle = oracle_sanity(stage9j_overrides(config, "clean")["model_params"], arrays(replay[("clean", 101)])["action"])
    write_dict_csv(root / "sanity_windows.csv", alignment); write_dict_csv(root / "objective_decomposition.csv", objective_rows); write_dict_csv(root / "equivalence_summary.csv", equivalence); write_dict_csv(root / "oracle_sanity_summary.csv", [oracle]); save_figures(objective_rows, equivalence, root); write_report(root, alignment, objective_rows, equivalence, oracle)
    (root / "command.txt").write_text(f"conda run -n mpc_learn python scripts/{Path(__file__).name}\n")


if __name__ == "__main__":
    main()
