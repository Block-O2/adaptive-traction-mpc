"""Predictive-fidelity audit for the proposed three-scale dynamics subspace.

This is an offline engineering audit.  It does not replace or modify the
validated geometry plus 11-base integral estimator.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN, HumanV2Parameters

from .estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from .human_model import (
    registered_cold_start_perturbed_human,
    registered_moderate_human,
)
from .integral_identifier import integral_regression_block
from .minimal_adaptation import (
    CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
    dynamic_scale_projection,
)
from .reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    cold_start_joint_reference,
)


AUDIT_DT_S = 0.02
INTEGRATION_WINDOW_S = 0.50
INTEGRATION_STRIDE_S = 0.10


def _rank_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    raw = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(raw, axis=0)
    normalized = raw / np.where(norms > 1e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1e-10 if len(singular) else 0.0
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1e-15
        else float(np.finfo(float).max)
    )
    return {
        "rows": int(raw.shape[0]),
        "columns": int(raw.shape[1]),
        "rank": rank,
        "nullity": int(raw.shape[1] - rank),
        "column_normalized_condition_number": condition,
        "column_normalized_singular_values": singular.tolist(),
    }


def _scaled_least_squares(matrix: np.ndarray, target: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=0)
    safe_norms = np.where(norms > 1e-15, norms, 1.0)
    normalized_solution, *_ = np.linalg.lstsq(
        matrix / safe_norms, target, rcond=1e-10
    )
    return normalized_solution / safe_norms


def _reference_history() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = np.arange(
        0.0,
        COLD_START_TEACHING_DURATION_S + 0.5 * AUDIT_DT_S,
        AUDIT_DT_S,
    )
    reference = [cold_start_joint_reference(float(item)) for item in time]
    state = np.array(
        [np.concatenate([q, dq]) for q, dq, _ in reference], dtype=float
    )
    acceleration = np.array([ddq for _, _, ddq in reference], dtype=float)
    return time, state, acceleration


def _integral_dataset(
    time: np.ndarray, state: np.ndarray, torque: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    window_samples = int(round(INTEGRATION_WINDOW_S / AUDIT_DT_S))
    stride_samples = int(round(INTEGRATION_STRIDE_S / AUDIT_DT_S))
    rows: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for end in range(window_samples, len(time), stride_samples):
        start = end - window_samples
        regressor, target = integral_regression_block(
            time[start : end + 1],
            state[start : end + 1],
            torque[start : end + 1],
        )
        rows.append(regressor)
        targets.append(target)
    return np.vstack(rows), np.concatenate(targets)


def _prediction_metrics(
    time: np.ndarray, true_torque: np.ndarray, prediction: np.ndarray
) -> dict[str, Any]:
    residual = prediction - true_torque
    combined_rmse = float(np.sqrt(np.mean(residual**2)))
    true_rms = float(np.sqrt(np.mean(true_torque**2)))
    segment_bias: list[dict[str, Any]] = []
    waypoints = COLD_START_TEACHING_WAYPOINTS
    for start, end in zip(waypoints[:-1], waypoints[1:], strict=True):
        selected = (time >= start.time_s) & (time <= end.time_s + 1e-12)
        segment_bias.append(
            {
                "start_phase_s": start.time_s,
                "end_phase_s": end.time_s,
                "label": end.label,
                "mean_residual_nm": np.mean(residual[selected], axis=0).tolist(),
            }
        )
    worst = max(
        segment_bias,
        key=lambda item: float(np.max(np.abs(item["mean_residual_nm"]))),
    )
    return {
        "combined_rmse_nm": combined_rmse,
        "normalized_combined_rmse_percent_of_true_torque_rms": (
            100.0 * combined_rmse / true_rms
        ),
        "per_joint_rmse_nm": np.sqrt(np.mean(residual**2, axis=0)).tolist(),
        "per_joint_mean_residual_nm": np.mean(residual, axis=0).tolist(),
        "per_joint_peak_abs_residual_nm": np.max(np.abs(residual), axis=0).tolist(),
        "phase_segment_mean_residuals": segment_bias,
        "worst_phase_segment_bias": worst,
    }


def _case_audit(
    case_name: str,
    human: HumanV2Parameters,
    metadata: dict[str, object],
    time: np.ndarray,
    state: np.ndarray,
    acceleration: np.ndarray,
) -> dict[str, Any]:
    true_beta = nominal_base_parameters(human)
    instantaneous_regressor = np.vstack(
        [
            dynamic_regressor_row(item[:2], item[2:], ddq)
            for item, ddq in zip(state, acceleration, strict=True)
        ]
    )
    true_torque = (instantaneous_regressor @ true_beta).reshape(-1, 2)
    integral_regressor, integral_target = _integral_dataset(time, state, true_torque)

    full_fit = _scaled_least_squares(integral_regressor, integral_target)
    projection = dynamic_scale_projection(nominal_base_parameters(HUMAN))
    reduced_regressor = integral_regressor @ projection
    reduced_scales = _scaled_least_squares(reduced_regressor, integral_target)
    reduced_beta = projection @ reduced_scales

    full_prediction = (instantaneous_regressor @ full_fit).reshape(-1, 2)
    reduced_prediction = (instantaneous_regressor @ reduced_beta).reshape(-1, 2)
    oracle_prediction = (instantaneous_regressor @ true_beta).reshape(-1, 2)
    lost_beta = true_beta - reduced_beta
    contribution_rms = np.sqrt(
        np.mean((instantaneous_regressor * lost_beta[np.newaxis, :]) ** 2, axis=0)
    )
    lost_order = np.argsort(contribution_rms)[::-1]

    return {
        "case": case_name,
        "registered_mismatch": metadata,
        "true_base_parameters": true_beta.tolist(),
        "integral_observability": {
            "full_11_base": _rank_diagnostics(integral_regressor),
            "reduced_3_scale": _rank_diagnostics(reduced_regressor),
        },
        "fits": {
            "full_11_base_parameters": full_fit.tolist(),
            "reduced_3_scales": reduced_scales.tolist(),
            "reduced_reconstructed_11_base_parameters": reduced_beta.tolist(),
        },
        "generalized_torque_prediction": {
            "oracle_true_11_base": _prediction_metrics(
                time, true_torque, oracle_prediction
            ),
            "integral_fit_11_base": _prediction_metrics(
                time, true_torque, full_prediction
            ),
            "best_integral_fit_reduced_3_scale": _prediction_metrics(
                time, true_torque, reduced_prediction
            ),
        },
        "lost_dynamics_directions": [
            {
                "base_parameter": DYNAMIC_BASE_PARAMETER_NAMES[index],
                "unrepresented_parameter_component": float(lost_beta[index]),
                "individual_trajectory_torque_contribution_rms_nm": float(
                    contribution_rms[index]
                ),
            }
            for index in lost_order
        ],
    }


def run_reduced_estimator_predictive_audit() -> dict[str, Any]:
    """Compare 3-scale best-fit fidelity with the retained 11-base model."""

    time, state, acceleration = _reference_history()
    moderate, moderate_metadata = registered_moderate_human()
    cold_start, cold_start_metadata = registered_cold_start_perturbed_human()
    cases = [
        _case_audit("nominal_sanity", HUMAN, {"case": "nominal"}, time, state, acceleration),
        _case_audit(
            "registered_moderate", moderate, moderate_metadata, time, state, acceleration
        ),
        _case_audit(
            "registered_cold_start_perturbed",
            cold_start,
            cold_start_metadata,
            time,
            state,
            acceleration,
        ),
    ]
    return {
        "evidence_category": "stage4_reduced_estimator_predictive_engineering_audit",
        "formal_experiment": False,
        "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
        "sample_period_s": AUDIT_DT_S,
        "integral_window_s": INTEGRATION_WINDOW_S,
        "integral_stride_s": INTEGRATION_STRIDE_S,
        "comparison_contract": {
            "full_model": "existing_exact_11_base_integral_representation",
            "reduced_model": list(CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES),
            "reduced_fit_advantage": "unconstrained_best_integral_least_squares",
            "estimator_replaced_or_modified": False,
            "controller_or_mpc_modified": False,
        },
        "cases": cases,
    }
