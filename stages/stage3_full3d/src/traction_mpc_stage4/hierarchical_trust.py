"""Offline prototype of hierarchical Stage-4 estimator trust.

The production estimator and its gates are intentionally untouched.  This
module wraps the validated geometry and 11-base integral identifiers for an
offline, causal promotion audit.  Oracle quantities are appended only after a
promotion decision has been made.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN, soft_limit_torque

from .dynamics_failure_audit import bound_diagnostics, unconstrained_candidate
from .estimator_v2 import (
    AccumulatedCuffGeometryEstimator,
    BaseParameterHumanModel,
    DYNAMIC_BASE_PARAMETER_NAMES,
    PlanarCuffGeometry,
    dynamic_regressor_row,
)
from .evaluation import BED_CONTACT_CONTAMINATION_FORCE_N
from .integral_identifier import (
    AccumulatedIntegralBaseDynamicIdentifier,
    integral_regression_block,
)
from .measurement import MeasurementCase, MeasurementPreprocessing


@dataclass(frozen=True)
class HierarchicalTrustPrototypeConfig:
    """Structural audit settings; none are fitted from oracle outcomes."""

    validation_embargo_integral_windows: int = 1
    validation_integral_windows: int = 2
    rotation_numerical_tolerance: float = 1.0e-6
    timestamp_numerical_tolerance_s: float = 1.0e-9


def _finite(*values: np.ndarray | float) -> bool:
    return bool(all(np.all(np.isfinite(value)) for value in values))


def measurement_validity(
    *,
    arrival_time_s: float,
    sample_time_s: float,
    previous_arrival_time_s: float | None,
    previous_ingested_sample_time_s: float | None,
    new_sample: bool,
    case: MeasurementCase,
    stream_start_sample_time_s: float,
    values: tuple[np.ndarray, ...],
    preprocessing: MeasurementPreprocessing = MeasurementPreprocessing(),
    dropout: bool = False,
    saturated: bool | None = None,
    config: HierarchicalTrustPrototypeConfig = HierarchicalTrustPrototypeConfig(),
) -> dict[str, Any]:
    """L1: reject only measurement-integrity failures.

    The saved engineering frontend has no sensor saturation flag or registered
    hardware range.  Consequently ``saturated=None`` is reported as
    unavailable and finite wrench magnitude is never used as a rejection gate.
    """

    tolerance = config.timestamp_numerical_tolerance_s
    reasons: list[str] = []
    age_s = float(arrival_time_s - sample_time_s)
    maximum_contract_age_s = float(case.latency_s + case.sample_period_s)
    if not _finite(arrival_time_s, sample_time_s, *values):
        reasons.append("nonfinite_measurement_or_timestamp")
    if previous_arrival_time_s is not None and arrival_time_s <= previous_arrival_time_s + tolerance:
        reasons.append("nonmonotonic_arrival_timestamp")
    if sample_time_s > arrival_time_s + tolerance or age_s < -tolerance:
        reasons.append("future_sample_timestamp")
    if age_s > maximum_contract_age_s + tolerance:
        reasons.append("sample_age_exceeds_registered_timing_contract")
    if dropout:
        reasons.append("sensor_dropout")
    if saturated is True:
        reasons.append("sensor_reported_saturation")
    if not new_sample or (
        previous_ingested_sample_time_s is not None
        and sample_time_s <= previous_ingested_sample_time_s + tolerance
    ):
        reasons.append("duplicate_or_stale_zoh_sample")
    warmup_s = preprocessing.derivative_window_s if case.preprocessing_enabled else 0.0
    if sample_time_s < stream_start_sample_time_s + warmup_s - tolerance:
        reasons.append("preprocessing_warmup")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "age_s": age_s,
        "maximum_contract_age_s": maximum_contract_age_s,
        "preprocessing_warmup_s": warmup_s,
        "sensor_saturation_status_available": saturated is not None,
    }


def state_geometry_validity(
    *,
    geometry: PlanarCuffGeometry,
    state: np.ndarray,
    measured_position_m: np.ndarray,
    measured_rotation: np.ndarray,
    measured_linear_velocity_m_s: np.ndarray,
    measured_angular_velocity_rad_s: np.ndarray,
    config: HierarchicalTrustPrototypeConfig = HierarchicalTrustPrototypeConfig(),
) -> dict[str, Any]:
    """L2: algebraic/causal reconstruction validity, not fit quality gating."""

    state = np.asarray(state, dtype=float)
    measured_rotation = np.asarray(measured_rotation, dtype=float)
    axes = np.column_stack(
        [geometry.plane_x_world, geometry.joint_axis_world, geometry.plane_z_world]
    )
    rotation_orthogonality_error = float(
        np.linalg.norm(measured_rotation.T @ measured_rotation - np.eye(3))
    )
    rotation_determinant_error = float(abs(np.linalg.det(measured_rotation) - 1.0))
    geometry_orthogonality_error = float(np.linalg.norm(axes.T @ axes - np.eye(3)))
    geometry_determinant_error = float(abs(abs(np.linalg.det(axes)) - 1.0))
    jacobian = np.vstack(
        [
            geometry.translational_jacobian_world(state[:2]),
            np.column_stack(
                [-geometry.joint_axis_world, geometry.joint_axis_world]
            ),
        ]
    )
    jacobian_rank = int(np.linalg.matrix_rank(jacobian)) if _finite(jacobian) else 0
    reasons: list[str] = []
    if not _finite(
        state,
        measured_position_m,
        measured_rotation,
        measured_linear_velocity_m_s,
        measured_angular_velocity_rad_s,
        axes,
        jacobian,
    ):
        reasons.append("nonfinite_state_or_geometry")
    if (
        rotation_orthogonality_error > config.rotation_numerical_tolerance
        or rotation_determinant_error > config.rotation_numerical_tolerance
    ):
        reasons.append("invalid_rotation_matrix")
    if (
        geometry_orthogonality_error > config.rotation_numerical_tolerance
        or geometry_determinant_error > config.rotation_numerical_tolerance
    ):
        reasons.append("invalid_geometry_basis")
    if jacobian_rank < 2:
        reasons.append("state_reconstruction_jacobian_rank_deficient")

    # These residuals are recorded for causal consistency, but deliberately do
    # not reject a finite reconstruction merely because an estimator fits poorly.
    predicted_pose = geometry.cuff_pose(state[:2])
    predicted_linear, predicted_angular = geometry.cuff_velocity(
        state[:2], state[2:]
    )
    return {
        "valid": not reasons,
        "reasons": reasons,
        "jacobian_rank": jacobian_rank,
        "rotation_orthogonality_error": rotation_orthogonality_error,
        "rotation_determinant_error": rotation_determinant_error,
        "geometry_orthogonality_error": geometry_orthogonality_error,
        "geometry_determinant_error": geometry_determinant_error,
        "position_closure_error_m": float(
            np.linalg.norm(predicted_pose.translation - measured_position_m)
        ),
        "linear_velocity_closure_error_m_s": float(
            np.linalg.norm(predicted_linear - measured_linear_velocity_m_s)
        ),
        "angular_velocity_closure_error_rad_s": float(
            np.linalg.norm(predicted_angular - measured_angular_velocity_rad_s)
        ),
    }


def _uncertainty_diagnostics(
    identifier: AccumulatedIntegralBaseDynamicIdentifier,
    regressor: np.ndarray,
    target: np.ndarray,
    candidate: np.ndarray,
) -> dict[str, Any]:
    scaled = np.asarray(regressor, dtype=float) * identifier.span
    covariance_shape = np.linalg.pinv(scaled.T @ scaled, rcond=1e-12)
    residual = regressor @ candidate - target
    rank = int(np.linalg.matrix_rank(scaled))
    degrees_of_freedom = max(int(len(target) - rank), 0)
    residual_variance = (
        float(residual @ residual / degrees_of_freedom)
        if degrees_of_freedom > 0
        else float("nan")
    )
    covariance_scaled = (
        residual_variance * covariance_shape
        if np.isfinite(residual_variance)
        else np.full_like(covariance_shape, np.nan)
    )
    std = np.sqrt(np.maximum(np.diag(covariance_scaled), 0.0))
    shape_std = np.sqrt(np.maximum(np.diag(covariance_shape), 0.0))
    denominator = np.outer(shape_std, shape_std)
    correlation = np.divide(
        covariance_shape,
        denominator,
        out=np.full_like(covariance_shape, np.nan),
        where=denominator > 0.0,
    )
    np.fill_diagonal(correlation, 0.0)
    return {
        "degrees_of_freedom": degrees_of_freedom,
        "residual_variance_nms2": residual_variance,
        "normalized_parameter_std": std.tolist(),
        "maximum_normalized_parameter_std": float(np.nanmax(std)),
        "covariance_shape_trace": float(np.trace(covariance_shape)),
        "maximum_abs_parameter_correlation": float(
            np.nanmax(np.abs(correlation))
        ),
    }


def _normalized_bound_violation(
    identifier: AccumulatedIntegralBaseDynamicIdentifier,
    unconstrained: np.ndarray,
) -> dict[str, Any]:
    raw = np.asarray(unconstrained, dtype=float)
    lower = np.maximum((identifier.lower - raw) / identifier.span, 0.0)
    upper = np.maximum((raw - identifier.upper) / identifier.span, 0.0)
    signed = np.where(lower > 0.0, -lower, upper)
    return {
        "per_parameter_signed_fraction_of_span": signed.tolist(),
        "l2_fraction_of_span": float(np.linalg.norm(signed)),
        "maximum_fraction_of_span": float(np.max(np.abs(signed))),
    }


def _apply_validated_estimator_step(
    identifier: AccumulatedIntegralBaseDynamicIdentifier,
    retained: np.ndarray,
    candidate: np.ndarray,
) -> np.ndarray:
    step = identifier.config.smoothing_alpha * (candidate - retained)
    maximum_step = identifier.config.maximum_update_fraction_of_span * identifier.span
    return np.clip(
        retained + np.clip(step, -maximum_step, maximum_step),
        identifier.lower,
        identifier.upper,
    )


def _validation_blocks(
    raw_history: list[dict[str, Any]],
    *,
    fit_end_time_s: float,
    window_s: float,
    embargo_windows: int,
    count: int,
) -> list[dict[str, Any]]:
    first_start = fit_end_time_s + embargo_windows * window_s
    blocks: list[dict[str, Any]] = []
    if not raw_history:
        return blocks
    latest_time = float(raw_history[-1]["time_s"])
    slot = 0
    while len(blocks) < count:
        start = first_start + slot * window_s
        end = start + window_s
        slot += 1
        if end > latest_time + 1e-12:
            break
        segment = [
            item
            for item in raw_history
            if item["time_s"] >= start - 1e-12 and item["time_s"] <= end + 1e-12
        ]
        if len(segment) < 3 or segment[-1]["time_s"] - segment[0]["time_s"] < 0.90 * window_s:
            continue
        if any(bool(item["contaminated"]) for item in segment):
            continue
        time = np.asarray([item["time_s"] for item in segment], dtype=float)
        state = np.asarray([item["state"] for item in segment], dtype=float)
        target = np.asarray([item["generalized_input_nm"] for item in segment], dtype=float)
        regressor, integrated_target = integral_regression_block(time, state, target)
        blocks.append(
            {
                "index": len(blocks),
                "future_slot": slot - 1,
                "start_time_s": float(time[0]),
                "end_time_s": float(time[-1]),
                "regressor": regressor,
                "target": integrated_target,
                "source_indices": [int(item["source_index"]) for item in segment],
            }
        )
    return blocks


def _block_losses(beta: np.ndarray, blocks: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [
            float(np.mean((block["regressor"] @ beta - block["target"]) ** 2))
            for block in blocks
        ],
        dtype=float,
    )


def _oracle_prediction_error(
    beta: np.ndarray,
    source_indices: list[int],
    *,
    estimated_state: np.ndarray,
    estimated_ddq: np.ndarray,
    true_state: np.ndarray,
    true_ddq: np.ndarray,
    true_beta: np.ndarray,
    clean: np.ndarray,
) -> float:
    selected = sorted(set(source_indices))
    errors = []
    for index in selected:
        if not bool(clean[index]):
            continue
        predicted = dynamic_regressor_row(
            estimated_state[index, :2],
            estimated_state[index, 2:],
            estimated_ddq[index],
        ) @ beta
        oracle = dynamic_regressor_row(
            true_state[index, :2], true_state[index, 2:], true_ddq[index]
        ) @ true_beta
        errors.append(predicted - oracle)
    return (
        float(np.sqrt(np.mean(np.asarray(errors) ** 2)))
        if errors
        else float("nan")
    )


def _group_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "count": 0,
            "oracle_error_mean_nm": float("nan"),
            "oracle_error_median_nm": float("nan"),
            "truth_distance_mean_span_l2": float("nan"),
            "truth_distance_median_span_l2": float("nan"),
            "active_bound_frequency": float("nan"),
            "prior_distance_mean_span_l2": float("nan"),
            "oracle_improvement_vs_last_valid_mean_nm": float("nan"),
            "oracle_improvement_vs_last_valid_median_nm": float("nan"),
            "oracle_improvement_vs_prior_mean_nm": float("nan"),
            "truth_distance_change_from_last_valid_mean_span_l2": float("nan"),
        }
    oracle = np.asarray([item["oracle_proposed_model_error_nm"] for item in records])
    truth = np.asarray([item["proposed_model_distance_to_truth_span_l2"] for item in records])
    prior = np.asarray([item["proposed_model_distance_to_prior_span_l2"] for item in records])
    improvement_last = np.asarray(
        [item["oracle_improvement_vs_last_valid_nm"] for item in records]
    )
    improvement_prior = np.asarray(
        [item["oracle_improvement_vs_prior_nm"] for item in records]
    )
    truth_change = np.asarray(
        [item["truth_distance_change_from_last_valid_span_l2"] for item in records]
    )
    return {
        "count": len(records),
        "oracle_error_mean_nm": float(np.nanmean(oracle)),
        "oracle_error_median_nm": float(np.nanmedian(oracle)),
        "truth_distance_mean_span_l2": float(np.nanmean(truth)),
        "truth_distance_median_span_l2": float(np.nanmedian(truth)),
        "active_bound_frequency": float(np.mean([item["l3"]["active_bound_count"] > 0 for item in records])),
        "prior_distance_mean_span_l2": float(np.nanmean(prior)),
        "oracle_improvement_vs_last_valid_mean_nm": float(
            np.nanmean(improvement_last)
        ),
        "oracle_improvement_vs_last_valid_median_nm": float(
            np.nanmedian(improvement_last)
        ),
        "oracle_improvement_vs_prior_mean_nm": float(
            np.nanmean(improvement_prior)
        ),
        "truth_distance_change_from_last_valid_mean_span_l2": float(
            np.nanmean(truth_change)
        ),
    }


def _selection_comparison(
    promoted: list[dict[str, Any]], nonpromoted: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons = []
    truth_comparisons = []
    prior_comparisons = []
    for rejected in nonpromoted:
        for accepted in promoted:
            comparisons.append(
                rejected["oracle_improvement_vs_last_valid_nm"]
                > accepted["oracle_improvement_vs_last_valid_nm"]
            )
            truth_comparisons.append(
                rejected["proposed_model_distance_to_truth_span_l2"]
                < accepted["proposed_model_distance_to_truth_span_l2"]
            )
            prior_comparisons.append(
                rejected["proposed_model_distance_to_prior_span_l2"]
                < accepted["proposed_model_distance_to_prior_span_l2"]
            )
    return {
        "promoted": _group_summary(promoted),
        "valid_nonpromoted": _group_summary(nonpromoted),
        "cross_pair_probability_nonpromoted_has_greater_phase_matched_oracle_improvement": (
            float(np.mean(comparisons)) if comparisons else float("nan")
        ),
        "cross_pair_probability_nonpromoted_is_closer_to_true_beta": (
            float(np.mean(truth_comparisons))
            if truth_comparisons
            else float("nan")
        ),
        "cross_pair_probability_nonpromoted_is_closer_to_population_prior": (
            float(np.mean(prior_comparisons))
            if prior_comparisons
            else float("nan")
        ),
        "interpretation_rule": (
            "Values above 0.5 indicate that a randomly paired non-promoted candidate "
            "more often improves oracle torque prediction relative to its own last-valid "
            "reference; oracle did not enter promotion."
        ),
    }


def audit_hierarchical_trust_case(
    *,
    case: MeasurementCase,
    details: dict[str, np.ndarray],
    initial_q_prior_rad: np.ndarray,
    true_beta: np.ndarray,
    config: HierarchicalTrustPrototypeConfig = HierarchicalTrustPrototypeConfig(),
) -> dict[str, Any]:
    """Causally replay one saved case through the non-default trust prototype."""

    arrival = np.asarray(details["high_level_time_s"], dtype=float)
    sample = np.asarray(details["high_level_sample_time_s"], dtype=float)
    new_sample = np.asarray(details["high_level_new_sample"], dtype=bool)
    position = np.asarray(details["high_level_measured_position_m"], dtype=float)
    rotation = np.asarray(details["high_level_measured_rotation"], dtype=float)
    linear = np.asarray(details["high_level_measured_linear_velocity_m_s"], dtype=float)
    angular = np.asarray(details["high_level_measured_angular_velocity_rad_s"], dtype=float)
    force = np.asarray(details["high_level_measured_force_world_n"], dtype=float)
    moment = np.asarray(details["high_level_measured_moment_world_nm"], dtype=float)
    bed_force = np.asarray(details["high_level_bed_force_n"], dtype=float)
    true_state = np.asarray(details["true_high_level_state_sample"], dtype=float)
    true_ddq = np.asarray(details["true_high_level_ddq_sample"], dtype=float)
    clean = np.asarray(details["clean_high_level_sample"], dtype=bool)

    geometry_identifier = AccumulatedCuffGeometryEstimator(
        position[0], rotation[0], initial_q_prior_rad
    )
    dynamic_identifier = AccumulatedIntegralBaseDynamicIdentifier()
    retained_beta = dynamic_identifier.population_prior.copy()
    raw_history: list[dict[str, Any]] = []
    l1_records: list[dict[str, Any]] = []
    l2_records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    promotions: list[dict[str, Any]] = []
    retained_history = []
    previous_arrival: float | None = None
    previous_ingested_sample: float | None = None
    estimated_state_by_source = np.full((len(arrival), 4), np.nan)

    window_s = dynamic_identifier.config.integration_window_s
    ready_offset_s = window_s * (
        config.validation_embargo_integral_windows
        + config.validation_integral_windows
    )

    def resolve_ready(now_s: float) -> None:
        nonlocal retained_beta
        still_pending = []
        for record in pending:
            if now_s < record["validation_ready_time_s"] - 1e-12:
                still_pending.append(record)
                continue
            blocks = _validation_blocks(
                raw_history,
                fit_end_time_s=record["fit_end_time_s"],
                window_s=window_s,
                embargo_windows=config.validation_embargo_integral_windows,
                count=config.validation_integral_windows,
            )
            if not blocks:
                still_pending.append(record)
                continue
            if len(blocks) < config.validation_integral_windows:
                still_pending.append(record)
                continue
            proposed = _apply_validated_estimator_step(
                dynamic_identifier,
                retained_beta,
                np.asarray(record["candidate_beta"], dtype=float),
            )
            candidate_losses = _block_losses(proposed, blocks)
            prior_losses = _block_losses(dynamic_identifier.population_prior, blocks)
            retained_losses = _block_losses(retained_beta, blocks)
            physical = BaseParameterHumanModel(
                geometry_identifier.geometry,
                proposed,
            ).minimum_mass_matrix_eigenvalue() > 1e-6
            improves_prior = float(np.sum(candidate_losses)) < float(np.sum(prior_losses))
            improves_retained = float(np.sum(candidate_losses)) < float(np.sum(retained_losses))
            promoted = bool(physical and improves_prior and improves_retained)
            record.update(
                {
                    "control_model_status": (
                        "promoted" if promoted else "valid_unpromoted_not_heldout_better"
                    ),
                    "promotion_time_s": float(now_s),
                    "proposed_model_beta": proposed.tolist(),
                    "reference_last_valid_beta": retained_beta.tolist(),
                    "validation_blocks": [
                        {
                            "index": block["index"],
                            "future_slot": block["future_slot"],
                            "start_time_s": block["start_time_s"],
                            "end_time_s": block["end_time_s"],
                        }
                        for block in blocks
                    ],
                    "validation_candidate_block_mse_nms2": candidate_losses.tolist(),
                    "validation_prior_block_mse_nms2": prior_losses.tolist(),
                    "validation_last_valid_block_mse_nms2": retained_losses.tolist(),
                    "validation_candidate_total_mse_nms2": float(np.sum(candidate_losses)),
                    "validation_prior_total_mse_nms2": float(np.sum(prior_losses)),
                    "validation_last_valid_total_mse_nms2": float(np.sum(retained_losses)),
                    "heldout_improves_population_prior": improves_prior,
                    "heldout_improves_last_valid": improves_retained,
                    "positive_definite_proposed_model": bool(physical),
                }
            )
            if promoted:
                retained_beta = proposed.copy()
                promotions.append(
                    {
                        "candidate_index": record["candidate_index"],
                        "fit_end_time_s": record["fit_end_time_s"],
                        "promotion_time_s": float(now_s),
                        "retained_beta": retained_beta.tolist(),
                    }
                )
        pending[:] = still_pending

    for index in range(len(arrival)):
        l1 = measurement_validity(
            arrival_time_s=float(arrival[index]),
            sample_time_s=float(sample[index]),
            previous_arrival_time_s=previous_arrival,
            previous_ingested_sample_time_s=previous_ingested_sample,
            new_sample=bool(new_sample[index]),
            case=case,
            stream_start_sample_time_s=float(sample[0]),
            values=(position[index], rotation[index], linear[index], angular[index], force[index], moment[index]),
            saturated=None,
            config=config,
        )
        l1_records.append({"source_index": index, "arrival_time_s": float(arrival[index]), "sample_time_s": float(sample[index]), **l1})
        previous_arrival = float(arrival[index])
        if not l1["valid"]:
            resolve_ready(float(arrival[index]))
            retained_history.append(retained_beta.copy())
            continue
        previous_ingested_sample = float(sample[index])

        provisional = geometry_identifier.geometry.estimate_state(
            position[index], rotation[index], linear[index], angular[index]
        )
        contaminated = bool(
            bed_force[index] > BED_CONTACT_CONTAMINATION_FORCE_N
            or np.linalg.norm(soft_limit_torque(provisional[:2], provisional[2:], HUMAN)) > 1e-8
        )
        geometry_identifier.add_pose(
            float(sample[index]), position[index], rotation[index], contaminated=contaminated
        )
        state = geometry_identifier.geometry.estimate_state(
            position[index], rotation[index], linear[index], angular[index]
        )
        l2 = state_geometry_validity(
            geometry=geometry_identifier.geometry,
            state=state,
            measured_position_m=position[index],
            measured_rotation=rotation[index],
            measured_linear_velocity_m_s=linear[index],
            measured_angular_velocity_rad_s=angular[index],
            config=config,
        )
        l2_records.append({"source_index": index, "sample_time_s": float(sample[index]), **l2})
        if l2["valid"]:
            estimated_state_by_source[index] = state
            generalized_input = geometry_identifier.geometry.generalized_input_from_wrench(
                state[:2], force[index], moment[index]
            )
            raw_history.append(
                {
                    "time_s": float(sample[index]),
                    "state": state.copy(),
                    "force_world_n": force[index].copy(),
                    "moment_world_nm": moment[index].copy(),
                    "generalized_input_nm": generalized_input.copy(),
                    "contaminated": contaminated,
                    "source_index": index,
                }
            )

        resolve_ready(float(sample[index]))

        if l2["valid"] and geometry_identifier.trustworthy_time_s is not None:
            dynamic_identifier.last_valid = retained_beta.copy()
            before_accepted = dynamic_identifier.accepted_updates
            before_rejected = dynamic_identifier.rejected_updates
            before_trusted = dynamic_identifier.trustworthy_time_s
            diagnostics = dynamic_identifier.attempt_update(
                raw_history, geometry_identifier.geometry
            )
            dynamic_identifier.last_valid = retained_beta.copy()
            dynamic_identifier.accepted_updates = before_accepted
            dynamic_identifier.rejected_updates = before_rejected
            dynamic_identifier.trustworthy_time_s = before_trusted
            if diagnostics.get("attempted", False):
                regressor, target, contaminated_windows = dynamic_identifier._integral_blocks(
                    raw_history, geometry_identifier.geometry
                )
                candidate = np.asarray(diagnostics["candidate"], dtype=float)
                unconstrained = unconstrained_candidate(
                    dynamic_identifier, regressor, target
                )
                active = bound_diagnostics(
                    dynamic_identifier, candidate, unconstrained
                )
                full_rank = bool(
                    diagnostics["rank"] == len(DYNAMIC_BASE_PARAMETER_NAMES)
                    and diagnostics["rrqr_rank"] == len(DYNAMIC_BASE_PARAMETER_NAMES)
                )
                conditioned = bool(
                    np.isfinite(diagnostics["condition_number"])
                    and diagnostics["condition_number"]
                    <= dynamic_identifier.config.maximum_condition_number
                )
                identification_status = (
                    "weakly_identified"
                    if not (full_rank and conditioned)
                    else (
                        "identified_boundary_pressured"
                        if active
                        else "identified_interior"
                    )
                )
                record = {
                    "candidate_index": len(candidates),
                    "source_index": index,
                    "fit_end_time_s": float(sample[index]),
                    "validation_ready_time_s": float(sample[index] + ready_offset_s),
                    "candidate_beta": candidate.tolist(),
                    "unconstrained_beta": unconstrained.tolist(),
                    "parameter_identification_status": identification_status,
                    "legacy_estimator_accepted": bool(diagnostics["accepted"]),
                    "legacy_estimator_reason": diagnostics["reason"],
                    "control_model_status": "pending_causal_holdout",
                    "l3": {
                        "rank": int(diagnostics["rank"]),
                        "rrqr_rank": int(diagnostics["rrqr_rank"]),
                        "condition_number": float(diagnostics["condition_number"]),
                        "candidate_residual_rms_nms": float(diagnostics["candidate_residual_rms_nms"]),
                        "old_residual_rms_nms": float(diagnostics["old_residual_rms_nms"]),
                        "integral_block_count": int(diagnostics["integral_block_count"]),
                        "contaminated_integral_windows": int(contaminated_windows),
                        "active_bound_count": int(sum(item["constrained_hit"] for item in active)),
                        "active_or_pressured_bounds": active,
                        "unconstrained_normalized_bound_violation": _normalized_bound_violation(dynamic_identifier, unconstrained),
                        "uncertainty": _uncertainty_diagnostics(dynamic_identifier, regressor, target, candidate),
                    },
                }
                candidates.append(record)
                pending.append(record)
        retained_history.append(retained_beta.copy())

    for record in pending:
        record["control_model_status"] = "pending_insufficient_future_validation"

    valid_source = np.flatnonzero(np.all(np.isfinite(estimated_state_by_source), axis=1))
    estimated_ddq = np.full((len(arrival), 2), np.nan)
    if len(valid_source) >= 3:
        estimated_ddq[valid_source] = np.gradient(
            estimated_state_by_source[valid_source, 2:],
            sample[valid_source],
            axis=0,
            edge_order=2,
        )
    for record in candidates:
        proposed = record.get("proposed_model_beta")
        if proposed is None:
            record["oracle_proposed_model_error_nm"] = float("nan")
            record["oracle_prior_error_nm"] = float("nan")
            record["oracle_last_valid_error_nm"] = float("nan")
            record["oracle_improvement_vs_last_valid_nm"] = float("nan")
            record["oracle_improvement_vs_prior_nm"] = float("nan")
            record["proposed_model_distance_to_truth_span_l2"] = float("nan")
            record["proposed_model_distance_to_prior_span_l2"] = float("nan")
            continue
        source_indices: list[int] = []
        blocks = _validation_blocks(
            raw_history,
            fit_end_time_s=record["fit_end_time_s"],
            window_s=window_s,
            embargo_windows=config.validation_embargo_integral_windows,
            count=config.validation_integral_windows,
        )
        for block in blocks:
            source_indices.extend(block["source_indices"])
        beta = np.asarray(proposed, dtype=float)
        record["oracle_proposed_model_error_nm"] = _oracle_prediction_error(
            beta,
            source_indices,
            estimated_state=estimated_state_by_source,
            estimated_ddq=estimated_ddq,
            true_state=true_state,
            true_ddq=true_ddq,
            true_beta=np.asarray(true_beta, dtype=float),
            clean=clean,
        )
        record["oracle_prior_error_nm"] = _oracle_prediction_error(
            dynamic_identifier.population_prior,
            source_indices,
            estimated_state=estimated_state_by_source,
            estimated_ddq=estimated_ddq,
            true_state=true_state,
            true_ddq=true_ddq,
            true_beta=np.asarray(true_beta, dtype=float),
            clean=clean,
        )
        record["oracle_last_valid_error_nm"] = _oracle_prediction_error(
            np.asarray(record["reference_last_valid_beta"], dtype=float),
            source_indices,
            estimated_state=estimated_state_by_source,
            estimated_ddq=estimated_ddq,
            true_state=true_state,
            true_ddq=true_ddq,
            true_beta=np.asarray(true_beta, dtype=float),
            clean=clean,
        )
        record["oracle_improvement_vs_last_valid_nm"] = float(
            record["oracle_last_valid_error_nm"]
            - record["oracle_proposed_model_error_nm"]
        )
        record["oracle_improvement_vs_prior_nm"] = float(
            record["oracle_prior_error_nm"]
            - record["oracle_proposed_model_error_nm"]
        )
        record["proposed_model_distance_to_truth_span_l2"] = float(
            np.linalg.norm((beta - true_beta) / dynamic_identifier.span)
        )
        record["reference_model_distance_to_truth_span_l2"] = float(
            np.linalg.norm(
                (
                    np.asarray(record["reference_last_valid_beta"], dtype=float)
                    - true_beta
                )
                / dynamic_identifier.span
            )
        )
        record["truth_distance_change_from_last_valid_span_l2"] = float(
            record["proposed_model_distance_to_truth_span_l2"]
            - record["reference_model_distance_to_truth_span_l2"]
        )
        record["proposed_model_distance_to_prior_span_l2"] = float(
            np.linalg.norm(
                (beta - dynamic_identifier.population_prior) / dynamic_identifier.span
            )
        )

    promoted_records = [item for item in candidates if item["control_model_status"] == "promoted"]
    nonpromoted_records = [item for item in candidates if item["control_model_status"] == "valid_unpromoted_not_heldout_better"]
    promotion_times = [item["promotion_time_s"] for item in promotions]
    boundaries = [float(sample[0]), *promotion_times, float(sample[-1])]
    intervals = np.diff(boundaries) if len(boundaries) >= 2 else np.asarray([])
    final_regressor, final_target, final_contaminated = dynamic_identifier._integral_blocks(
        raw_history, geometry_identifier.geometry
    )
    all_valid_sources = [
        int(index)
        for index in valid_source
        if bool(clean[index]) and np.all(np.isfinite(estimated_ddq[index]))
    ]
    final_oracle_error = _oracle_prediction_error(
        retained_beta,
        all_valid_sources,
        estimated_state=estimated_state_by_source,
        estimated_ddq=estimated_ddq,
        true_state=true_state,
        true_ddq=true_ddq,
        true_beta=np.asarray(true_beta, dtype=float),
        clean=clean,
    )
    prior_oracle_error = _oracle_prediction_error(
        dynamic_identifier.population_prior,
        all_valid_sources,
        estimated_state=estimated_state_by_source,
        estimated_ddq=estimated_ddq,
        true_state=true_state,
        true_ddq=true_ddq,
        true_beta=np.asarray(true_beta, dtype=float),
        clean=clean,
    )
    return {
        "case": case.name,
        "production_default": False,
        "oracle_entered_trust_decision": False,
        "semantics": {
            "L1": "measurement_integrity_only",
            "L2": "finite_algebraically_valid_causal_state_geometry_reconstruction",
            "L3": "diagnostic_identification_quality_no_bound_auto_reject",
            "L4": "future_embargoed_integral_prediction_beats_population_prior_and_current_last_valid",
        },
        "causal_validation": {
            "fit_validation_embargo_s": config.validation_embargo_integral_windows * window_s,
            "validation_window_s": window_s,
            "validation_window_count": config.validation_integral_windows,
            "minimum_candidate_to_decision_delay_s": ready_offset_s,
            "promotion_uses_oracle": False,
            "point_improvement_rule": "strictly lower summed heldout block MSE than both population prior and current last-valid model",
        },
        "L1": {
            "sample_count": len(l1_records),
            "valid_count": int(sum(item["valid"] for item in l1_records)),
            "invalid_count": int(sum(not item["valid"] for item in l1_records)),
            "reason_counts": {
                reason: int(sum(reason in item["reasons"] for item in l1_records))
                for reason in sorted({reason for item in l1_records for reason in item["reasons"]})
            },
            "saturation_status_available": False,
            "records": l1_records,
        },
        "L2": {
            "checked_count": len(l2_records),
            "valid_count": int(sum(item["valid"] for item in l2_records)),
            "invalid_count": int(sum(not item["valid"] for item in l2_records)),
            "reason_counts": {
                reason: int(sum(reason in item["reasons"] for item in l2_records))
                for reason in sorted({reason for item in l2_records for reason in item["reasons"]})
            },
            "maximum_position_closure_error_m": float(max((item["position_closure_error_m"] for item in l2_records), default=float("nan"))),
            "maximum_linear_velocity_closure_error_m_s": float(max((item["linear_velocity_closure_error_m_s"] for item in l2_records), default=float("nan"))),
            "records": l2_records,
        },
        "L3_L4_candidates": candidates,
        "promotions": promotions,
        "selection_bias_oracle_audit": _selection_comparison(promoted_records, nonpromoted_records),
        "starvation": {
            "trajectory_duration_s": float(arrival[-1] - arrival[0]),
            "first_promotion_time_s": float(promotion_times[0]) if promotion_times else None,
            "time_to_first_promotion_s": float(promotion_times[0] - sample[0]) if promotion_times else None,
            "time_since_last_promotion_s": float(sample[-1] - promotion_times[-1]) if promotion_times else float(sample[-1] - sample[0]),
            "longest_no_promotion_interval_s": float(np.max(intervals)) if len(intervals) else float(sample[-1] - sample[0]),
            "valid_candidate_count": len(candidates),
            "promoted_candidate_count": len(promoted_records),
            "valid_but_unpromoted_candidate_count": len(nonpromoted_records),
            "pending_insufficient_future_validation_count": int(sum(item["control_model_status"] == "pending_insufficient_future_validation" for item in candidates)),
            "invalid_or_missing_holdout_count": int(sum(item["control_model_status"] == "valid_unpromoted_invalid_or_missing_holdout" for item in candidates)),
            "valid_measurements_accumulated": len(raw_history),
            "final_integral_block_count": int(len(final_target) // 2),
            "final_contaminated_integral_windows": int(final_contaminated),
            "useful_data_retained_after_failed_promotion": True,
        },
        "final_retained_beta": retained_beta.tolist(),
        "full_trace_oracle_prediction": {
            "population_prior_error_nm": prior_oracle_error,
            "final_retained_error_nm": final_oracle_error,
            "final_improvement_vs_prior_nm": float(
                prior_oracle_error - final_oracle_error
            ),
            "sample_count": len(all_valid_sources),
        },
        "final_distance_to_truth_span_l2": float(
            np.linalg.norm((retained_beta - true_beta) / dynamic_identifier.span)
        ),
        "population_prior_distance_to_truth_span_l2": float(
            np.linalg.norm(
                (dynamic_identifier.population_prior - true_beta)
                / dynamic_identifier.span
            )
        ),
        "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "production_estimator_or_controller_modified": False,
    }
