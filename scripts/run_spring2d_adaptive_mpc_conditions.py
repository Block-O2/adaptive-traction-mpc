"""Run adaptive MPC closed-loop conditions for Spring2D."""

from __future__ import annotations

import argparse
import copy
import csv
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.estimation.filters import make_observation_filter
from traction_mpc.evaluation.plot_adaptive_mpc_conditions import (
    save_adaptive_mpc_conditions_comparison,
    save_adaptive_mpc_summary_table,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.models.spring2d_dynamics import compute_physical_info, compute_positions, step_dynamics
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.safety_filter import SafetyFilterResult, make_safety_filter
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions.yaml"


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open("r") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")
    return cfg


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_experiment_config(path: Path) -> dict[str, Any]:
    cfg = load_yaml(path)
    source_cfg = load_yaml(_resolve_project_path(cfg["identifier_conditions_config"]))
    base_cfg = load_yaml(_resolve_project_path(source_cfg.get("base_config", "configs/spring2d.yaml")))
    mpc_cfg = load_yaml(_resolve_project_path(source_cfg.get("mpc_config", "configs/spring2d_fixed_mpc.yaml")))

    true_params = dict(base_cfg["params"])
    true_params.update(source_cfg.get("true_param_overrides", {}))
    model_params = dict(base_cfg["params"])
    model_params.update(source_cfg.get("initial_model_overrides", {}))
    mpc_params = deep_update(mpc_cfg["mpc"], source_cfg.get("mpc_overrides", {}))
    mpc_params = deep_update(mpc_params, cfg.get("mpc_overrides", {}))
    return {
        "true_params": true_params,
        "model_params": model_params,
        "mpc_params": mpc_params,
        "identifier": source_cfg["identifier"],
        "run": source_cfg.get("run", {}),
        "conditions": source_cfg["conditions"],
        "adaptive": cfg.get("adaptive", {}),
        "outputs": cfg["outputs"],
        "observation_filter": cfg.get("observation_filter", {"type": "raw", "identifier_input": "raw"}),
        "coupling_ablation": cfg.get("coupling_ablation", {}),
        "safety_filter": cfg.get("safety_filter", {"enabled": False}),
        "baseline_summary_table": cfg.get("baseline_summary_table"),
    }


def observation_from_state(
    template: Any,
    state: np.ndarray,
    params: dict[str, Any],
) -> Any:
    x = np.asarray(state, dtype=float).copy()
    x[2] = max(float(x[2]), 1.0e-6)
    positions = compute_positions(x, params)
    action = np.array([template.F_tan, template.F_rad], dtype=float)
    physical_info = compute_physical_info(x, action, params)
    return replace(
        template,
        theta=float(x[0]),
        omega=float(x[1]),
        r=float(x[2]),
        r_dot=float(x[3]),
        delta_r=float(x[2] - float(params["L0"])),
        base_pos=positions["base_pos"],
        tip_pos=positions["tip_pos"],
        contact_pos=positions["contact_pos"],
        r_ddot=float(physical_info["r_ddot"]),
        omega_dot=float(physical_info["omega_dot"]),
        base_x=float(physical_info["base_x"]),
        base_a=float(physical_info["base_a"]),
        base_ap=float(physical_info["base_ap"]),
        physical_info=physical_info,
    )


def current_prediction_params(base_model_params: dict[str, Any], controller: AdaptiveMPC) -> dict[str, Any]:
    params = dict(base_model_params)
    params.update(controller.get_current_parameter_estimate())
    return params


def select_observation_by_source(
    source: str,
    raw_observation: Any,
    filtered_observation: Any,
    true_observation: Any,
) -> Any:
    source = source.lower()
    if source == "raw":
        return raw_observation
    if source == "filtered":
        return filtered_observation
    if source == "oracle_true_state":
        return true_observation
    if source == "none":
        return None
    raise ValueError(f"Unknown observation source: {source}")


def parameter_vector(theta_hat: dict[str, float]) -> np.ndarray:
    return np.array([float(theta_hat["m"]), float(theta_hat["k"]), float(theta_hat["b_r"])], dtype=float)


def parameter_bound_hit(theta_hat: dict[str, float], bounds: dict[str, Any]) -> bool:
    for name, value in theta_hat.items():
        if name not in bounds:
            continue
        lower, upper = bounds[name]
        if np.isclose(float(value), float(lower)) or np.isclose(float(value), float(upper)):
            return True
    return False


def initial_identifier_result(identifier: WindowedLeastSquaresIdentifier) -> Any:
    return SimpleNamespace(
        theta_hat=identifier.get_parameter_estimate(),
        prediction_error=np.nan,
        updated=False,
        num_samples=0,
        success=True,
    )


def append_adaptive_fields(
    row: dict[str, Any],
    obs_state: np.ndarray,
    filt_state: np.ndarray,
    result: Any,
    controller: AdaptiveMPC,
    parameter_update_flag: bool,
    target_theta: float,
    alpha_step: float,
    solve_diagnostics: dict[str, Any] | None = None,
    update_diagnostics: dict[str, Any] | None = None,
    filter_diagnostics: dict[str, Any] | None = None,
    coupling_diagnostics: dict[str, Any] | None = None,
    safety_diagnostics: dict[str, Any] | None = None,
    theta_cmd: float | None = None,
    progress_governor_mode: str = "off",
    progress_governor_rate_deg_s: float = np.nan,
    progress_governor_selected_rate_deg_s: float = np.nan,
    progress_governor_hold: bool = False,
    progress_governor_safety_score: float = np.nan,
    progress_governor_pred_alpha_max: float = np.nan,
    progress_governor_pred_alpha_sum: float = np.nan,
    progress_governor_pred_omega_max: float = np.nan,
    progress_governor_pred_omega_sum: float = np.nan,
) -> dict[str, Any]:
    enriched = dict(row)
    theta_hat = result.theta_hat
    theta_mpc = controller.get_current_parameter_estimate()
    solve_diag = solve_diagnostics or {}
    update_diag = update_diagnostics or {}
    filter_diag = filter_diagnostics or {}
    coupling_diag = coupling_diagnostics or {}
    safety_diag = safety_diagnostics or SafetyFilterResult.disabled(
        np.array([row.get("F_tan", 0.0), row.get("F_rad", 0.0)], dtype=float)
    ).as_diagnostics()
    true_state = np.array([row["theta"], row["omega"], row["r"], row["r_dot"]], dtype=float)
    obs_state = np.asarray(obs_state, dtype=float)
    filt_state = np.asarray(filt_state, dtype=float)
    enriched.update(
        {
            "true_theta": float(true_state[0]),
            "true_omega": float(true_state[1]),
            "true_r": float(true_state[2]),
            "true_r_dot": float(true_state[3]),
            "theta_obs": float(obs_state[0]),
            "omega_obs": float(obs_state[1]),
            "r_obs": float(obs_state[2]),
            "r_dot_obs": float(obs_state[3]),
            "obs_theta": float(obs_state[0]),
            "obs_omega": float(obs_state[1]),
            "obs_r": float(obs_state[2]),
            "obs_r_dot": float(obs_state[3]),
            "filt_theta": float(filt_state[0]),
            "filt_omega": float(filt_state[1]),
            "filt_r": float(filt_state[2]),
            "filt_r_dot": float(filt_state[3]),
            "filter_error_theta": float(filt_state[0] - true_state[0]),
            "filter_error_omega": float(filt_state[1] - true_state[1]),
            "filter_error_r": float(filt_state[2] - true_state[2]),
            "filter_error_r_dot": float(filt_state[3] - true_state[3]),
            "raw_error_theta": float(obs_state[0] - true_state[0]),
            "raw_error_omega": float(obs_state[1] - true_state[1]),
            "raw_error_r": float(obs_state[2] - true_state[2]),
            "raw_error_r_dot": float(obs_state[3] - true_state[3]),
            "bias_theta_hat": float(filter_diag.get("bias_theta_hat", np.nan)),
            "bias_omega_hat": float(filter_diag.get("bias_omega_hat", np.nan)),
            "bias_r_hat": float(filter_diag.get("bias_r_hat", np.nan)),
            "bias_r_dot_hat": float(filter_diag.get("bias_r_dot_hat", np.nan)),
            "innovation_norm": float(filter_diag.get("innovation_norm", np.nan)),
            "covariance_trace": float(filter_diag.get("covariance_trace", np.nan)),
            "ukf_failed": bool(filter_diag.get("ukf_failed", False)),
            "filter_type": str(coupling_diag.get("filter_type", "")),
            "coupling_case": str(coupling_diag.get("coupling_case", "")),
            "mpc_state_input_source": str(coupling_diag.get("mpc_state_input_source", "")),
            "identifier_mode": str(coupling_diag.get("identifier_mode", "")),
            "identifier_input_source": str(coupling_diag.get("identifier_input_source", "")),
            "estimator_model_params_source": str(coupling_diag.get("estimator_model_params_source", "")),
            "mpc_model_params_source": str(coupling_diag.get("mpc_model_params_source", "")),
            "m_hat": float(theta_hat["m"]),
            "k_hat": float(theta_hat["k"]),
            "b_r_hat": float(theta_hat["b_r"]),
            "m_mpc": float(theta_mpc["m"]),
            "k_mpc": float(theta_mpc["k"]),
            "b_r_mpc": float(theta_mpc["b_r"]),
            "m_mpc_used": float(theta_mpc["m"]),
            "k_mpc_used": float(theta_mpc["k"]),
            "b_r_mpc_used": float(theta_mpc["b_r"]),
            "theta_mpc_used": f"{float(theta_mpc['m']):.9g},{float(theta_mpc['k']):.9g},{float(theta_mpc['b_r']):.9g}",
            "prediction_error": float(result.prediction_error),
            "identifier_updated": bool(result.updated),
            "identifier_samples": int(result.num_samples),
            "identifier_success": bool(result.success),
            "nls_success": bool(result.success),
            "nls_residual": float(result.prediction_error),
            "parameter_update_flag": bool(parameter_update_flag),
            "parameter_update_count": int(coupling_diag.get("parameter_update_count", 0)),
            "parameter_step_norm": float(coupling_diag.get("parameter_step_norm", np.nan)),
            "parameter_bound_hit": bool(coupling_diag.get("parameter_bound_hit", False)),
            "target_reached": bool(float(row["theta"]) >= target_theta),
            "theta_cmd": float(target_theta if theta_cmd is None else theta_cmd),
            "theta_target_final": float(target_theta),
            "progress_governor_mode": str(progress_governor_mode),
            "progress_governor_rate_deg_s": float(progress_governor_rate_deg_s),
            "progress_governor_selected_rate_deg_s": float(progress_governor_selected_rate_deg_s),
            "progress_governor_hold": bool(progress_governor_hold),
            "progress_governor_safety_score": float(progress_governor_safety_score),
            "progress_governor_pred_alpha_max": float(progress_governor_pred_alpha_max),
            "progress_governor_pred_alpha_sum": float(progress_governor_pred_alpha_sum),
            "progress_governor_pred_omega_max": float(progress_governor_pred_omega_max),
            "progress_governor_pred_omega_sum": float(progress_governor_pred_omega_sum),
            "alpha_step": float(alpha_step),
            "omega_dot_continuous": float(row.get("omega_dot", np.nan)),
            "mpc_recreated_on_update": bool(update_diag.get("mpc_recreated_on_update", False)) if parameter_update_flag else False,
            "solver_recreated_on_update": bool(update_diag.get("solver_recreated_on_update", False)) if parameter_update_flag else False,
            "mpc_recreated_flag": bool(update_diag.get("mpc_recreated_on_update", False)) if parameter_update_flag else False,
            "solver_recreated_flag": bool(update_diag.get("solver_recreated_on_update", False)) if parameter_update_flag else False,
            "last_action_preserved_on_update": bool(update_diag.get("last_action_preserved_on_update", False)) if parameter_update_flag else False,
            "last_solution_existed_before_update": bool(update_diag.get("last_solution_existed_before_update", False)) if parameter_update_flag else False,
            "last_solution_preserved_on_update": bool(update_diag.get("last_solution_preserved_on_update", False)) if parameter_update_flag else False,
            "mpc_solve_count": int(solve_diag.get("mpc_solve_count", 0)),
            "last_solution_existed_before_solve": bool(solve_diag.get("last_solution_existed_before_solve", False)),
            "last_solution_available_before_solve": bool(solve_diag.get("last_solution_existed_before_solve", False)),
            "warm_start_used": bool(solve_diag.get("warm_start_used", False)),
            "selected_sequence_first_F_tan": float(solve_diag.get("selected_sequence_first_F_tan", np.nan)),
            "selected_sequence_first_F_rad": float(solve_diag.get("selected_sequence_first_F_rad", np.nan)),
            "alpha_pred_max": float(solve_diag.get("alpha_pred_max", np.nan)),
            "omega_pred_max": float(solve_diag.get("omega_pred_max", np.nan)),
            "delta_r_pred_max": float(solve_diag.get("delta_r_pred_max", np.nan)),
            "mpc_result_cost": float(solve_diag.get("mpc_result_cost", np.nan)),
            "mpc_result_feasible": bool(solve_diag.get("mpc_result_feasible", False)),
            "mpc_feasible_count": int(solve_diag.get("mpc_feasible_count", 0)),
            "mpc_num_candidates": int(solve_diag.get("mpc_num_candidates", 0)),
            "mpc_feasible_ratio": float(solve_diag.get("mpc_feasible_ratio", np.nan)),
            "mpc_solver_type": str(solve_diag.get("mpc_solver_type", "")),
            "mpc_solver_selection": str(solve_diag.get("mpc_solver_selection", "")),
            "best_task_cost": float(solve_diag.get("best_task_cost", np.nan)),
            "best_violation_score": float(solve_diag.get("best_violation_score", np.nan)),
            "best_max_violation_F_tan": float(solve_diag.get("best_max_violation_F_tan", np.nan)),
            "best_max_violation_F_rad": float(solve_diag.get("best_max_violation_F_rad", np.nan)),
            "best_max_violation_delta_r": float(solve_diag.get("best_max_violation_delta_r", np.nan)),
            "best_max_violation_omega": float(solve_diag.get("best_max_violation_omega", np.nan)),
            "best_max_violation_alpha": float(solve_diag.get("best_max_violation_alpha", np.nan)),
            "elite_feasible_count": int(solve_diag.get("elite_feasible_count", 0)),
            "selected_candidate_rank": int(solve_diag.get("selected_candidate_rank", 0)),
            "best_selected_from": str(solve_diag.get("best_selected_from", "")),
            "cem_safety_mode": str(solve_diag.get("safety_mode", "off")),
            "cem_safety_penalty_weight": float(solve_diag.get("safety_penalty_weight", np.nan)),
            "cem_safety_control_dt": float(solve_diag.get("safety_control_dt", np.nan)),
            "cem_alpha_constraint_mode": str(solve_diag.get("alpha_constraint_mode", "hard")),
            "cem_alpha_soft_weight": float(solve_diag.get("alpha_soft_weight", np.nan)),
            "cem_alpha_relaxed_multiplier": float(solve_diag.get("alpha_relaxed_multiplier", np.nan)),
            "cem_gatekeeper_mode": str(solve_diag.get("gatekeeper_mode", "off")),
            "cem_gatekeeper_horizon": int(solve_diag.get("gatekeeper_horizon", 0)),
            "cem_gatekeeper_top_k": int(solve_diag.get("gatekeeper_top_k", 0)),
            "gatekeeper_intervened": bool(solve_diag.get("gatekeeper_intervened", False)),
            "gatekeeper_nominal_rank": int(solve_diag.get("gatekeeper_nominal_rank", 0)),
            "gatekeeper_selected_rank": int(solve_diag.get("gatekeeper_selected_rank", 0)),
            "gatekeeper_nominal_candidate_index": int(solve_diag.get("gatekeeper_nominal_candidate_index", 0)),
            "gatekeeper_selected_candidate_index": int(solve_diag.get("gatekeeper_selected_candidate_index", 0)),
            "gatekeeper_nominal_safety_score": float(solve_diag.get("gatekeeper_nominal_safety_score", np.nan)),
            "gatekeeper_selected_safety_score": float(solve_diag.get("gatekeeper_selected_safety_score", np.nan)),
            "gatekeeper_nominal_task_cost": float(solve_diag.get("gatekeeper_nominal_task_cost", np.nan)),
            "gatekeeper_selected_task_cost": float(solve_diag.get("gatekeeper_selected_task_cost", np.nan)),
            "gatekeeper_alpha_max_weight": float(solve_diag.get("gatekeeper_alpha_max_weight", np.nan)),
            "gatekeeper_alpha_sum_weight": float(solve_diag.get("gatekeeper_alpha_sum_weight", np.nan)),
            "gatekeeper_omega_max_weight": float(solve_diag.get("gatekeeper_omega_max_weight", np.nan)),
            "gatekeeper_omega_sum_weight": float(solve_diag.get("gatekeeper_omega_sum_weight", np.nan)),
            "gatekeeper_delta_r_weight": float(solve_diag.get("gatekeeper_delta_r_weight", np.nan)),
            "gatekeeper_force_weight": float(solve_diag.get("gatekeeper_force_weight", np.nan)),
            "gatekeeper_nominal_max_norm_violation_alpha": float(
                solve_diag.get("gatekeeper_nominal_max_norm_violation_alpha", np.nan)
            ),
            "gatekeeper_selected_max_norm_violation_alpha": float(
                solve_diag.get("gatekeeper_selected_max_norm_violation_alpha", np.nan)
            ),
            "gatekeeper_nominal_sum_norm_violation_alpha": float(
                solve_diag.get("gatekeeper_nominal_sum_norm_violation_alpha", np.nan)
            ),
            "gatekeeper_selected_sum_norm_violation_alpha": float(
                solve_diag.get("gatekeeper_selected_sum_norm_violation_alpha", np.nan)
            ),
            "gatekeeper_nominal_max_norm_violation_omega": float(
                solve_diag.get("gatekeeper_nominal_max_norm_violation_omega", np.nan)
            ),
            "gatekeeper_selected_max_norm_violation_omega": float(
                solve_diag.get("gatekeeper_selected_max_norm_violation_omega", np.nan)
            ),
            "gatekeeper_nominal_sum_norm_violation_omega": float(
                solve_diag.get("gatekeeper_nominal_sum_norm_violation_omega", np.nan)
            ),
            "gatekeeper_selected_sum_norm_violation_omega": float(
                solve_diag.get("gatekeeper_selected_sum_norm_violation_omega", np.nan)
            ),
            "cem_best_safety_score": float(solve_diag.get("best_safety_score", np.nan)),
            "cem_best_safety_raw_score": float(solve_diag.get("best_safety_raw_score", np.nan)),
            "cem_best_safety_feasible": bool(solve_diag.get("best_safety_feasible", False)),
            "cem_safety_feasible_count": int(solve_diag.get("safety_feasible_count", 0)),
            "cem_safety_feasible_ratio": float(solve_diag.get("safety_feasible_ratio", np.nan)),
            "cem_safety_feasible_excluding_alpha_count": int(
                solve_diag.get("safety_feasible_excluding_alpha_count", 0)
            ),
            "cem_safety_feasible_excluding_alpha_ratio": float(
                solve_diag.get("safety_feasible_excluding_alpha_ratio", np.nan)
            ),
            "cem_alpha_original_feasible_count": int(solve_diag.get("alpha_original_feasible_count", 0)),
            "cem_alpha_original_feasible_ratio": float(solve_diag.get("alpha_original_feasible_ratio", np.nan)),
            "cem_alpha_relaxed_feasible_count": int(solve_diag.get("alpha_relaxed_feasible_count", 0)),
            "cem_alpha_relaxed_feasible_ratio": float(solve_diag.get("alpha_relaxed_feasible_ratio", np.nan)),
            "cem_elite_safety_feasible_count": int(solve_diag.get("elite_safety_feasible_count", 0)),
            "cem_selected_total_normalized_violation": float(
                solve_diag.get("selected_safety_total_normalized_score", np.nan)
            ),
            "cem_selected_total_normalized_violation_excluding_alpha": float(
                solve_diag.get("selected_safety_total_normalized_score_excluding_alpha", np.nan)
            ),
            "cem_selected_total_normalized_alpha_score": float(
                solve_diag.get("selected_safety_total_normalized_alpha_score", np.nan)
            ),
            "cem_selected_total_raw_violation": float(solve_diag.get("selected_safety_total_raw_score", np.nan)),
            "cem_selected_safety_feasible": bool(solve_diag.get("selected_safety_safety_feasible", False)),
            "cem_selected_safety_feasible_excluding_alpha": bool(
                solve_diag.get("selected_safety_safety_feasible_excluding_alpha", False)
            ),
            "cem_selected_alpha_original_feasible": bool(
                solve_diag.get("selected_safety_alpha_original_feasible", False)
            ),
            "cem_selected_alpha_relaxed_feasible": bool(
                solve_diag.get("selected_safety_alpha_relaxed_feasible", False)
            ),
            "cem_selected_alpha_relaxed_threshold_normalized": float(
                solve_diag.get("selected_safety_alpha_relaxed_threshold_normalized", np.nan)
            ),
            "cem_selected_safety_violation_count": int(solve_diag.get("selected_safety_violation_count", 0)),
            "cem_selected_one_step_norm_violation_alpha": float(
                solve_diag.get("selected_safety_one_step_normalized_violation_alpha", np.nan)
            ),
            "cem_selected_max_norm_violation_F_tan": float(
                solve_diag.get("selected_safety_max_normalized_violation_F_tan", np.nan)
            ),
            "cem_selected_max_norm_violation_F_rad": float(
                solve_diag.get("selected_safety_max_normalized_violation_F_rad", np.nan)
            ),
            "cem_selected_max_norm_violation_delta_r": float(
                solve_diag.get("selected_safety_max_normalized_violation_delta_r", np.nan)
            ),
            "cem_selected_max_norm_violation_omega": float(
                solve_diag.get("selected_safety_max_normalized_violation_omega", np.nan)
            ),
            "cem_selected_max_norm_violation_alpha": float(
                solve_diag.get("selected_safety_max_normalized_violation_alpha", np.nan)
            ),
            "cem_selected_mean_norm_violation_F_tan": float(
                solve_diag.get("selected_safety_mean_normalized_violation_F_tan", np.nan)
            ),
            "cem_selected_mean_norm_violation_F_rad": float(
                solve_diag.get("selected_safety_mean_normalized_violation_F_rad", np.nan)
            ),
            "cem_selected_mean_norm_violation_delta_r": float(
                solve_diag.get("selected_safety_mean_normalized_violation_delta_r", np.nan)
            ),
            "cem_selected_mean_norm_violation_omega": float(
                solve_diag.get("selected_safety_mean_normalized_violation_omega", np.nan)
            ),
            "cem_selected_mean_norm_violation_alpha": float(
                solve_diag.get("selected_safety_mean_normalized_violation_alpha", np.nan)
            ),
            "F_tan_mpc": float(safety_diag.get("F_tan_mpc", np.nan)),
            "F_rad_mpc": float(safety_diag.get("F_rad_mpc", np.nan)),
            "F_tan_safe": float(safety_diag.get("F_tan_safe", np.nan)),
            "F_rad_safe": float(safety_diag.get("F_rad_safe", np.nan)),
            "action_delta_norm": float(safety_diag.get("action_delta_norm", np.nan)),
            "safety_filter_active": bool(safety_diag.get("safety_filter_active", False)),
            "safety_filter_feasible_candidate_found": bool(
                safety_diag.get("safety_filter_feasible_candidate_found", False)
            ),
            "safety_filter_failed": bool(safety_diag.get("safety_filter_failed", False)),
            "safety_filter_violation_score": float(safety_diag.get("safety_filter_violation_score", np.nan)),
            "one_step_pred_omega_next": float(safety_diag.get("one_step_pred_omega_next", np.nan)),
            "one_step_pred_alpha": float(safety_diag.get("one_step_pred_alpha", np.nan)),
            "one_step_pred_delta_r_next": float(safety_diag.get("one_step_pred_delta_r_next", np.nan)),
            "safety_filter_num_candidates": int(safety_diag.get("safety_filter_num_candidates", 0)),
            "safety_filter_selected_index": int(safety_diag.get("safety_filter_selected_index", -1)),
            "safety_filter_type": str(safety_diag.get("safety_filter_type", "")),
            "safety_filter_step_index": int(safety_diag.get("safety_filter_step_index", -1)),
            "safety_filter_time": float(safety_diag.get("safety_filter_time", np.nan)),
            "selected_candidate_type": str(safety_diag.get("selected_candidate_type", "")),
            "selected_candidate_scale": float(safety_diag.get("selected_candidate_scale", np.nan)),
            "F_tan_sign_flip": bool(safety_diag.get("F_tan_sign_flip", False)),
            "safety_filter_target_theta": float(safety_diag.get("safety_filter_target_theta", np.nan)),
            "safety_filter_state_hat_theta": float(safety_diag.get("safety_filter_state_hat_theta", np.nan)),
            "safety_filter_state_hat_omega": float(safety_diag.get("safety_filter_state_hat_omega", np.nan)),
            "safety_filter_state_hat_r": float(safety_diag.get("safety_filter_state_hat_r", np.nan)),
            "safety_filter_state_hat_r_dot": float(safety_diag.get("safety_filter_state_hat_r_dot", np.nan)),
            "safety_filter_true_theta": float(safety_diag.get("safety_filter_true_theta", np.nan)),
            "safety_filter_true_omega": float(safety_diag.get("safety_filter_true_omega", np.nan)),
            "safety_filter_true_r": float(safety_diag.get("safety_filter_true_r", np.nan)),
            "safety_filter_true_r_dot": float(safety_diag.get("safety_filter_true_r_dot", np.nan)),
            "safety_filter_obs_theta": float(safety_diag.get("safety_filter_obs_theta", np.nan)),
            "safety_filter_obs_omega": float(safety_diag.get("safety_filter_obs_omega", np.nan)),
            "safety_filter_obs_r": float(safety_diag.get("safety_filter_obs_r", np.nan)),
            "safety_filter_obs_r_dot": float(safety_diag.get("safety_filter_obs_r_dot", np.nan)),
            "pred_mpc_theta_next": float(safety_diag.get("pred_mpc_theta_next", np.nan)),
            "pred_mpc_omega_next": float(safety_diag.get("pred_mpc_omega_next", np.nan)),
            "pred_mpc_r_next": float(safety_diag.get("pred_mpc_r_next", np.nan)),
            "pred_mpc_r_dot_next": float(safety_diag.get("pred_mpc_r_dot_next", np.nan)),
            "pred_mpc_alpha": float(safety_diag.get("pred_mpc_alpha", np.nan)),
            "pred_safe_theta_next": float(safety_diag.get("pred_safe_theta_next", np.nan)),
            "pred_safe_omega_next": float(safety_diag.get("pred_safe_omega_next", np.nan)),
            "pred_safe_r_next": float(safety_diag.get("pred_safe_r_next", np.nan)),
            "pred_safe_r_dot_next": float(safety_diag.get("pred_safe_r_dot_next", np.nan)),
            "pred_safe_alpha": float(safety_diag.get("pred_safe_alpha", np.nan)),
            "true_safe_theta_next": float(safety_diag.get("true_safe_theta_next", np.nan)),
            "true_safe_omega_next": float(safety_diag.get("true_safe_omega_next", np.nan)),
            "true_safe_r_next": float(safety_diag.get("true_safe_r_next", np.nan)),
            "true_safe_r_dot_next": float(safety_diag.get("true_safe_r_dot_next", np.nan)),
            "true_safe_alpha": float(safety_diag.get("true_safe_alpha", np.nan)),
            "mpc_raw_violation_score": float(safety_diag.get("mpc_raw_violation_score", np.nan)),
            "mpc_normalized_violation_score": float(safety_diag.get("mpc_normalized_violation_score", np.nan)),
            "safe_raw_violation_score": float(safety_diag.get("safe_raw_violation_score", np.nan)),
            "safe_normalized_violation_score": float(safety_diag.get("safe_normalized_violation_score", np.nan)),
            "mpc_violation_F_tan": float(safety_diag.get("mpc_violation_F_tan", np.nan)),
            "mpc_violation_F_rad": float(safety_diag.get("mpc_violation_F_rad", np.nan)),
            "mpc_violation_delta_r": float(safety_diag.get("mpc_violation_delta_r", np.nan)),
            "mpc_violation_omega": float(safety_diag.get("mpc_violation_omega", np.nan)),
            "mpc_violation_alpha": float(safety_diag.get("mpc_violation_alpha", np.nan)),
            "safe_violation_F_tan": float(safety_diag.get("safe_violation_F_tan", np.nan)),
            "safe_violation_F_rad": float(safety_diag.get("safe_violation_F_rad", np.nan)),
            "safe_violation_delta_r": float(safety_diag.get("safe_violation_delta_r", np.nan)),
            "safe_violation_omega": float(safety_diag.get("safe_violation_omega", np.nan)),
            "safe_violation_alpha": float(safety_diag.get("safe_violation_alpha", np.nan)),
            "mpc_normalized_violation_F_tan": float(safety_diag.get("mpc_normalized_violation_F_tan", np.nan)),
            "mpc_normalized_violation_F_rad": float(safety_diag.get("mpc_normalized_violation_F_rad", np.nan)),
            "mpc_normalized_violation_delta_r": float(safety_diag.get("mpc_normalized_violation_delta_r", np.nan)),
            "mpc_normalized_violation_omega": float(safety_diag.get("mpc_normalized_violation_omega", np.nan)),
            "mpc_normalized_violation_alpha": float(safety_diag.get("mpc_normalized_violation_alpha", np.nan)),
            "safe_normalized_violation_F_tan": float(safety_diag.get("safe_normalized_violation_F_tan", np.nan)),
            "safe_normalized_violation_F_rad": float(safety_diag.get("safe_normalized_violation_F_rad", np.nan)),
            "safe_normalized_violation_delta_r": float(safety_diag.get("safe_normalized_violation_delta_r", np.nan)),
            "safe_normalized_violation_omega": float(safety_diag.get("safe_normalized_violation_omega", np.nan)),
            "safe_normalized_violation_alpha": float(safety_diag.get("safe_normalized_violation_alpha", np.nan)),
        }
    )
    return enriched


def run_condition(
    condition_name: str,
    condition_cfg: dict[str, Any],
    cfg: dict[str, Any],
    diagnostics_callback: Any | None = None,
) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    adaptive_cfg = cfg.get("adaptive", {})
    alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 0.5))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    target_theta = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))
    governor_cfg = dict(cfg.get("progress_governor", {}))
    progress_governor_mode = str(governor_cfg.get("mode", "off")).lower()
    if progress_governor_mode not in {"off", "fixed_rate", "safety_aware"}:
        raise ValueError("progress_governor mode must be one of: off, fixed_rate, safety_aware.")
    governor_rate_deg_s = float(governor_cfg.get("rate_deg_s", np.nan))
    governor_rate_rad_s = (
        np.radians(governor_rate_deg_s)
        if progress_governor_mode == "fixed_rate"
        else np.inf
    )
    governor_candidate_rates_deg_s = [
        float(value)
        for value in governor_cfg.get("candidate_rates_deg_s", [0.0, 10.0, 20.0, 30.0, 45.0])
    ]
    governor_horizon = int(governor_cfg.get("horizon", 3))
    governor_safety_threshold = float(governor_cfg.get("safety_score_threshold", 0.0))
    governor_weights = dict(
        {
            "alpha_max": 10.0,
            "alpha_sum": 5.0,
            "omega_max": 5.0,
            "omega_sum": 1.0,
            "delta_r": 5.0,
            "force": 5.0,
        },
        **governor_cfg.get("weights", {}),
    )
    coupling_cfg = dict(cfg.get("coupling_ablation", {}))
    coupling_name = str(coupling_cfg.get("name", "default"))
    mpc_state_input = str(coupling_cfg.get("mpc_state_input", "filtered")).lower()
    identifier_mode = str(coupling_cfg.get("identifier_mode", "adaptive")).lower()
    estimator_model_params_source = str(coupling_cfg.get("estimator_model_params_source", "adaptive")).lower()
    mpc_model_params_source = str(coupling_cfg.get("mpc_model_params_source", "adaptive")).lower()

    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    theta_cmd = (
        float(obs_true.theta)
        if progress_governor_mode in {"fixed_rate", "safety_aware"}
        else target_theta
    )
    wrapper = NoisySpring2DObservationWrapper(
        true_params,
        condition_cfg.get("observation_noise", {}),
        seed=int(condition_cfg.get("seed", 0)),
    )
    obs_meas = wrapper.observe(obs_true)

    controller = AdaptiveMPC(model_params, cfg["mpc_params"])
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()
    safety_constraints = Spring2DMPCConstraints.from_configs(
        model_params,
        cfg["mpc_params"].get("constraints", {}),
        prediction_dt=float(true_params["dt"]),
    )
    safety_filter = make_safety_filter(
        dict(cfg.get("safety_filter", {"enabled": False})),
        safety_constraints,
        control_dt=float(true_params["dt"]),
    )

    filter_cfg = dict(cfg.get("observation_filter", {"type": "raw", "identifier_input": "raw"}))
    filter_cfg["condition_name"] = condition_name
    filter_type = str(filter_cfg.get("type", "raw")).lower()
    identifier_input = str(coupling_cfg.get("identifier_input", filter_cfg.get("identifier_input", "raw"))).lower()
    obs_filter = make_observation_filter(filter_cfg)
    initial_filter_model_params = (
        model_params
        if estimator_model_params_source == "initial"
        else current_prediction_params(model_params, controller)
    )
    filt_state = obs_filter.reset(
        obs_meas,
        true_state=observation_to_state(obs_true),
        model_params=initial_filter_model_params,
    )
    obs_filt = observation_from_state(obs_meas, filt_state, true_params)
    obs_mpc = select_observation_by_source(mpc_state_input, obs_meas, obs_filt, obs_true)
    if obs_mpc is None:
        raise ValueError("mpc_state_input cannot be none.")

    parameter_update_count = 0
    last_theta_hat_vec = parameter_vector(identifier.get_parameter_estimate())

    def advance_theta_cmd(value: float, dt: float) -> float:
        if progress_governor_mode == "off":
            return target_theta
        diff = target_theta - float(value)
        max_step = float(governor_rate_rad_s) * float(dt)
        if abs(diff) <= max_step:
            return target_theta
        return float(value + np.sign(diff) * max_step)

    def safety_governor_score(
        state: np.ndarray,
        theta_cmd_candidate: float,
        prediction_params: dict[str, Any],
    ) -> dict[str, Any]:
        mpc_impl = controller.controller
        previous_target = float(mpc_impl.target_theta)
        try:
            mpc_impl.set_target_theta(theta_cmd_candidate)
            sequence = np.asarray(mpc_impl._nominal_sequence(state), dtype=float)
        finally:
            mpc_impl.set_target_theta(previous_target)

        max_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        sum_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        x = np.asarray(state, dtype=float).copy()
        steps_pred = min(governor_horizon, len(sequence))
        valid = True
        for k in range(steps_pred):
            raw_action = np.asarray(sequence[k], dtype=float)
            prev_x = x.copy()
            action = safety_constraints.clip_action(raw_action)
            try:
                x = step_dynamics(x, action, float(mpc_impl.prediction_dt), prediction_params)
            except (FloatingPointError, OverflowError, ValueError):
                valid = False
                break
            if not np.all(np.isfinite(x)):
                valid = False
                break
            alpha_pred = (float(x[1]) - float(prev_x[1])) / float(mpc_impl.prediction_dt)
            delta_r = float(x[2] - float(prediction_params["L0"]))
            raw = {
                "F_tan": max(0.0, abs(float(raw_action[0])) - safety_constraints.F_tan_max),
                "F_rad": max(0.0, abs(float(raw_action[1])) - safety_constraints.F_rad_max),
                "delta_r": max(0.0, abs(delta_r) - safety_constraints.delta_r_max),
                "omega": max(0.0, abs(float(x[1])) - safety_constraints.omega_max),
                "alpha": max(0.0, abs(alpha_pred) - safety_constraints.alpha_max),
            }
            norm = {
                "F_tan": raw["F_tan"] / safety_constraints.F_tan_max if safety_constraints.F_tan_max > 0.0 else 0.0,
                "F_rad": raw["F_rad"] / safety_constraints.F_rad_max if safety_constraints.F_rad_max > 0.0 else 0.0,
                "delta_r": raw["delta_r"] / safety_constraints.delta_r_max if safety_constraints.delta_r_max > 0.0 else 0.0,
                "omega": raw["omega"] / safety_constraints.omega_max if safety_constraints.omega_max > 0.0 else 0.0,
                "alpha": raw["alpha"] / safety_constraints.alpha_max if safety_constraints.alpha_max > 0.0 else 0.0,
            }
            for name, value in norm.items():
                max_norm[name] = max(max_norm[name], float(value))
                sum_norm[name] += float(value)
        if not valid:
            return {
                "score": float("inf"),
                "pred_alpha_max": float("inf"),
                "pred_alpha_sum": float("inf"),
                "pred_omega_max": float("inf"),
                "pred_omega_sum": float("inf"),
            }
        score = (
            float(governor_weights["alpha_max"]) * max_norm["alpha"]
            + float(governor_weights["alpha_sum"]) * sum_norm["alpha"]
            + float(governor_weights["omega_max"]) * max_norm["omega"]
            + float(governor_weights["omega_sum"]) * sum_norm["omega"]
            + float(governor_weights["delta_r"]) * (max_norm["delta_r"] + sum_norm["delta_r"])
            + float(governor_weights["force"])
            * (
                max_norm["F_tan"]
                + sum_norm["F_tan"]
                + max_norm["F_rad"]
                + sum_norm["F_rad"]
            )
        )
        return {
            "score": float(score),
            "pred_alpha_max": float(max_norm["alpha"]),
            "pred_alpha_sum": float(sum_norm["alpha"]),
            "pred_omega_max": float(max_norm["omega"]),
            "pred_omega_sum": float(sum_norm["omega"]),
        }

    def select_safety_aware_theta_cmd(state: np.ndarray, dt_control: float) -> dict[str, Any]:
        direction = float(np.sign(target_theta - theta_cmd))
        if direction == 0.0:
            return {
                "theta_cmd_next": target_theta,
                "selected_rate_deg_s": 0.0,
                "hold": False,
                "safety_score": 0.0,
                "pred_alpha_max": 0.0,
                "pred_alpha_sum": 0.0,
                "pred_omega_max": 0.0,
                "pred_omega_sum": 0.0,
            }
        prediction_params = current_prediction_params(model_params, controller)
        candidates: list[dict[str, Any]] = []
        for rate_deg_s in governor_candidate_rates_deg_s:
            step = direction * np.radians(rate_deg_s) * float(dt_control)
            if abs(step) >= abs(target_theta - theta_cmd):
                theta_candidate = target_theta
            else:
                theta_candidate = float(theta_cmd + step)
            risk = safety_governor_score(state, theta_candidate, prediction_params)
            candidates.append(
                {
                    "theta_cmd_next": theta_candidate,
                    "selected_rate_deg_s": float(rate_deg_s),
                    "hold": float(rate_deg_s) <= 0.0,
                    **risk,
                }
            )
        safe_candidates = [
            candidate
            for candidate in candidates
            if np.isfinite(float(candidate["score"]))
            and float(candidate["score"]) <= governor_safety_threshold
        ]
        if safe_candidates:
            return max(safe_candidates, key=lambda candidate: float(candidate["selected_rate_deg_s"]))
        hold_candidate = candidates[0]
        hold_candidate = dict(hold_candidate)
        hold_candidate["theta_cmd_next"] = float(theta_cmd)
        hold_candidate["selected_rate_deg_s"] = 0.0
        hold_candidate["hold"] = True
        return hold_candidate

    def coupling_diagnostics(result: Any, parameter_step_norm: float) -> dict[str, Any]:
        return {
            "filter_type": filter_type,
            "coupling_case": coupling_name,
            "mpc_state_input_source": mpc_state_input,
            "identifier_mode": identifier_mode,
            "identifier_input_source": identifier_input,
            "estimator_model_params_source": estimator_model_params_source,
            "mpc_model_params_source": mpc_model_params_source,
            "parameter_update_count": parameter_update_count,
            "parameter_step_norm": parameter_step_norm,
            "parameter_bound_hit": parameter_bound_hit(result.theta_hat, parameter_bounds),
        }

    rows: list[dict[str, Any]] = []
    initial_result = initial_identifier_result(identifier)
    rows.append(
        append_adaptive_fields(
            env.get_history()[-1],
            observation_to_state(obs_meas),
            filt_state,
            initial_result,
            controller,
            parameter_update_flag=False,
            target_theta=target_theta,
            alpha_step=0.0,
            filter_diagnostics=obs_filter.get_diagnostics(),
            coupling_diagnostics=coupling_diagnostics(initial_result, 0.0),
            safety_diagnostics=SafetyFilterResult.disabled(np.zeros(2, dtype=float)).as_diagnostics(),
            theta_cmd=theta_cmd,
            progress_governor_mode=progress_governor_mode,
            progress_governor_rate_deg_s=governor_rate_deg_s,
            progress_governor_selected_rate_deg_s=0.0,
            progress_governor_hold=progress_governor_mode == "safety_aware",
        )
    )

    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    solve_diagnostics: dict[str, Any] = {}
    while not env.is_done() and steps < max_steps:
        governor_decision = {
            "selected_rate_deg_s": governor_rate_deg_s if progress_governor_mode == "fixed_rate" else np.nan,
            "hold": False,
            "score": np.nan,
            "pred_alpha_max": np.nan,
            "pred_alpha_sum": np.nan,
            "pred_omega_max": np.nan,
            "pred_omega_sum": np.nan,
        }
        if progress_governor_mode == "safety_aware":
            governor_decision = select_safety_aware_theta_cmd(
                observation_to_state(obs_mpc),
                float(true_params["dt"]) * float(hold_steps),
            )
            theta_cmd = float(governor_decision["theta_cmd_next"])
        controller.set_target_theta(theta_cmd)
        action_mpc = controller.act(obs_mpc)
        solve_diagnostics = controller.get_last_solve_diagnostics()
        for hold_index in range(hold_steps):
            prev_obs_meas = obs_meas
            prev_obs_filt = obs_filt
            prev_obs_true = obs_true
            prev_history_row = env.get_history()[-1]
            pre_filt_state = np.asarray(filt_state, dtype=float).copy()
            safety_model_params = current_prediction_params(model_params, controller)
            if safety_filter is None:
                safety_result = SafetyFilterResult.disabled(np.asarray(action_mpc, dtype=float))
            else:
                safety_result = safety_filter.filter(
                    np.asarray(action_mpc, dtype=float),
                    pre_filt_state,
                    safety_model_params,
                    target_theta=target_theta,
                )
            action_exec = np.asarray(safety_result.action_safe, dtype=float)

            obs_true = env.step(action_exec)
            if progress_governor_mode == "fixed_rate":
                theta_cmd = advance_theta_cmd(theta_cmd, float(true_params["dt"]))
            obs_meas = wrapper.observe(obs_true)
            filter_model_params = (
                model_params
                if estimator_model_params_source == "initial"
                else current_prediction_params(model_params, controller)
            )
            obs_filter.predict(action_exec, float(true_params["dt"]), model_params=filter_model_params)
            filt_state = obs_filter.update(
                obs_meas,
                float(true_params["dt"]),
                action=action_exec,
                true_state=observation_to_state(obs_true),
                model_params=filter_model_params,
            )
            obs_filt = observation_from_state(obs_meas, filt_state, true_params)
            obs_mpc = select_observation_by_source(mpc_state_input, obs_meas, obs_filt, obs_true)
            if obs_mpc is None:
                raise ValueError("mpc_state_input cannot be none.")

            id_prev = select_observation_by_source(identifier_input, prev_obs_meas, prev_obs_filt, prev_obs_true)
            id_next = select_observation_by_source(identifier_input, obs_meas, obs_filt, obs_true)
            if identifier_mode == "frozen" or identifier_input == "none":
                result = SimpleNamespace(
                    theta_hat=identifier.get_parameter_estimate(),
                    prediction_error=np.nan,
                    updated=False,
                    num_samples=len(identifier.transitions),
                    success=True,
                )
            elif identifier_mode == "adaptive":
                result = identifier.add_transition(
                    observation_to_state(id_prev),
                    action_exec,
                    observation_to_state(id_next),
                )
            else:
                raise ValueError(f"Unknown identifier_mode: {identifier_mode}")
            steps += 1

            parameter_update_flag = False
            update_diagnostics: dict[str, Any] = {}
            current_theta_hat_vec = parameter_vector(result.theta_hat)
            parameter_step_norm = float(np.linalg.norm(current_theta_hat_vec - last_theta_hat_vec))
            last_theta_hat_vec = current_theta_hat_vec
            if (
                result.updated
                and steps >= warmup_steps
                and identifier_mode == "adaptive"
                and mpc_model_params_source == "adaptive"
            ):
                controller.update_parameters(result.theta_hat, alpha=alpha, bounds=parameter_bounds)
                update_diagnostics = controller.get_last_update_diagnostics()
                parameter_update_flag = True
                parameter_update_count += 1

            history_row = env.get_history()[-1]
            alpha_step = (float(history_row["omega"]) - float(prev_history_row["omega"])) / float(true_params["dt"])
            safety_diagnostics = safety_result.as_diagnostics()
            prev_true_state = observation_to_state(prev_obs_true)
            prev_obs_state = observation_to_state(prev_obs_meas)
            true_next_state = np.array(
                [
                    float(history_row["theta"]),
                    float(history_row["omega"]),
                    float(history_row["r"]),
                    float(history_row["r_dot"]),
                ],
                dtype=float,
            )
            safety_diagnostics.update(
                {
                    "safety_filter_step_index": steps,
                    "safety_filter_time": float(prev_history_row["t"]),
                    "safety_filter_target_theta": target_theta,
                    "safety_filter_true_theta": float(prev_true_state[0]),
                    "safety_filter_true_omega": float(prev_true_state[1]),
                    "safety_filter_true_r": float(prev_true_state[2]),
                    "safety_filter_true_r_dot": float(prev_true_state[3]),
                    "safety_filter_obs_theta": float(prev_obs_state[0]),
                    "safety_filter_obs_omega": float(prev_obs_state[1]),
                    "safety_filter_obs_r": float(prev_obs_state[2]),
                    "safety_filter_obs_r_dot": float(prev_obs_state[3]),
                    "true_safe_theta_next": float(true_next_state[0]),
                    "true_safe_omega_next": float(true_next_state[1]),
                    "true_safe_r_next": float(true_next_state[2]),
                    "true_safe_r_dot_next": float(true_next_state[3]),
                    "true_safe_alpha": alpha_step,
                }
            )
            enriched_row = append_adaptive_fields(
                history_row,
                observation_to_state(obs_meas),
                filt_state,
                result,
                controller,
                parameter_update_flag=parameter_update_flag,
                target_theta=target_theta,
                alpha_step=alpha_step,
                solve_diagnostics=solve_diagnostics,
                update_diagnostics=update_diagnostics,
                filter_diagnostics=obs_filter.get_diagnostics(),
                coupling_diagnostics=coupling_diagnostics(result, parameter_step_norm),
                safety_diagnostics=safety_diagnostics,
                theta_cmd=theta_cmd,
                progress_governor_mode=progress_governor_mode,
                progress_governor_rate_deg_s=governor_rate_deg_s,
                progress_governor_selected_rate_deg_s=float(governor_decision["selected_rate_deg_s"]),
                progress_governor_hold=bool(governor_decision["hold"]),
                progress_governor_safety_score=float(governor_decision["score"]),
                progress_governor_pred_alpha_max=float(governor_decision["pred_alpha_max"]),
                progress_governor_pred_alpha_sum=float(governor_decision["pred_alpha_sum"]),
                progress_governor_pred_omega_max=float(governor_decision["pred_omega_max"]),
                progress_governor_pred_omega_sum=float(governor_decision["pred_omega_sum"]),
            )
            rows.append(enriched_row)
            if diagnostics_callback is not None and hold_index == 0:
                diagnostics_callback(
                    condition_name=condition_name,
                    step=steps,
                    time=float(prev_history_row["t"]),
                    solve_diagnostics=solve_diagnostics,
                    action_mpc=np.asarray(action_mpc, dtype=float),
                    action_exec=action_exec,
                    prev_history_row=prev_history_row,
                    history_row=history_row,
                    enriched_row=enriched_row,
                    alpha_step=alpha_step,
                    cfg=cfg,
                )
            if env.is_done() or steps >= max_steps:
                break

    return rows


def write_condition_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path) -> dict[str, list[dict[str, Any]]]:
    cfg = load_experiment_config(config_path)
    outputs = cfg["outputs"]
    log_dir = _resolve_project_path(outputs.get("log_dir", "results/logs/spring2d_adaptive_mpc_conditions"))
    video_dir = _resolve_project_path(outputs.get("video_dir", "results/videos/spring2d_adaptive_mpc_conditions"))
    figure_path = _resolve_project_path(
        outputs.get(
            "figure",
            "results/figures/spring2d_adaptive_mpc_conditions/adaptive_conditions_comparison.png",
        )
    )
    summary_path = _resolve_project_path(
        outputs.get("summary_table", "results/figures/spring2d_adaptive_mpc_conditions/summary_table.csv")
    )
    baseline_path = (
        _resolve_project_path(cfg["baseline_summary_table"])
        if cfg.get("baseline_summary_table")
        else None
    )
    fps = int(outputs.get("fps", 25))

    all_rows: dict[str, list[dict[str, Any]]] = {}
    for condition_name, condition_cfg in cfg["conditions"].items():
        rows = run_condition(condition_name, condition_cfg, cfg)
        all_rows[condition_name] = rows
        write_condition_csv(rows, log_dir / condition_name / "timeseries.csv")
        save_spring2d_animation(rows, cfg["true_params"], video_dir / f"{condition_name}.gif", fps=fps)

    save_adaptive_mpc_conditions_comparison(
        all_rows,
        cfg["true_params"],
        figure_path,
        mpc_constraints=cfg["mpc_params"].get("constraints", {}),
    )
    save_adaptive_mpc_summary_table(all_rows, cfg["true_params"], summary_path, baseline_path)

    print("Spring2D adaptive MPC conditions")
    print(f"  config        : {config_path}")
    print(f"  log dir       : {log_dir}")
    print(f"  video dir     : {video_dir}")
    print(f"  figure        : {figure_path}")
    print(f"  summary table : {summary_path}")
    for condition_name, rows in all_rows.items():
        final = rows[-1]
        finite_errors = [float(row["prediction_error"]) for row in rows if np.isfinite(float(row["prediction_error"]))]
        first_err = finite_errors[0] if finite_errors else np.nan
        final_err = finite_errors[-1] if finite_errors else np.nan
        print(
            "  "
            f"{condition_name}: done={final['done_reason']}, "
            f"target_reached={final['target_reached']}, "
            f"theta={np.degrees(float(final['theta'])):.2f}deg, "
            f"m_mpc={float(final['m_mpc']):.3f}, "
            f"k_mpc={float(final['k_mpc']):.2f}, "
            f"b_r_mpc={float(final['b_r_mpc']):.2f}, "
            f"pred_error={first_err:.5f}->{final_err:.5f}"
        )
    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
