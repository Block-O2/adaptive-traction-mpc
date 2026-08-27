"""Non-default incumbent--challenger L4 prototype for Stage-4 trust.

L1/L2 semantics and L3 diagnostics are reused unchanged from
``hierarchical_trust``.  This module changes only offline control-model
promotion: at most one challenger is validated against a fixed incumbent using
clean, embargoed integral blocks and a finite set of pre-registered looks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Literal

import numpy as np
from scipy.stats import t as student_t

from traction_mpc_stage3.human import HUMAN, soft_limit_torque

from .dynamics_failure_audit import bound_diagnostics, unconstrained_candidate
from .estimator_v2 import (
    AccumulatedCuffGeometryEstimator,
    BaseParameterHumanModel,
    DYNAMIC_BASE_PARAMETER_NAMES,
    dynamic_regressor_row,
)
from .evaluation import BED_CONTACT_CONTAMINATION_FORCE_N
from .hierarchical_trust import (
    HierarchicalTrustPrototypeConfig,
    _apply_validated_estimator_step,
    _block_losses,
    _normalized_bound_violation,
    _oracle_prediction_error,
    _uncertainty_diagnostics,
    _validation_blocks,
    measurement_validity,
    state_geometry_validity,
)
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from .measurement import MeasurementCase
from .reference import CONTINUOUS_TEACHING_DURATION_S


@dataclass(frozen=True)
class StatisticalL4Config:
    """Pre-registered statistical settings; never selected using oracle data."""

    name: str = "primary_single_challenger_hac_lag2"
    method: Literal["hac", "moving_block_bootstrap"] = "hac"
    familywise_alpha: float = 0.05
    minimum_clean_blocks: int = 8
    look_step_blocks: int = 4
    maximum_clean_blocks: int = 16
    hac_lag_blocks: int = 2
    bootstrap_block_length: int = 2
    bootstrap_replicates: int = 4000
    bootstrap_seed: int = 481516

    def __post_init__(self) -> None:
        if not 0.0 < self.familywise_alpha < 0.5:
            raise ValueError("familywise_alpha must lie in (0, 0.5)")
        if self.minimum_clean_blocks < 3:
            raise ValueError("minimum_clean_blocks must be at least three")
        if self.look_step_blocks < 1:
            raise ValueError("look_step_blocks must be positive")
        if self.maximum_clean_blocks < self.minimum_clean_blocks:
            raise ValueError("maximum_clean_blocks must not precede the first look")
        if (
            self.maximum_clean_blocks - self.minimum_clean_blocks
        ) % self.look_step_blocks:
            raise ValueError("maximum_clean_blocks must fall on a scheduled look")
        if self.hac_lag_blocks < 0:
            raise ValueError("hac_lag_blocks cannot be negative")
        if self.bootstrap_block_length < 1:
            raise ValueError("bootstrap_block_length must be positive")
        if self.bootstrap_replicates < 1000:
            raise ValueError("bootstrap_replicates must be at least 1000")

    @property
    def scheduled_looks(self) -> tuple[int, ...]:
        return tuple(
            range(
                self.minimum_clean_blocks,
                self.maximum_clean_blocks + 1,
                self.look_step_blocks,
            )
        )

    def challenger_family_alpha(self, challenger_index: int) -> float:
        """Anytime alpha spending for a one-at-a-time challenger stream.

        With one-based j = challenger_index + 1, alpha_j = alpha/[j(j+1)].
        The telescoping sum over an unbounded stream is exactly alpha, so no
        task-duration-dependent maximum challenger count is required.
        """

        if challenger_index < 0:
            raise ValueError("challenger_index cannot be negative")
        j = challenger_index + 1
        return self.familywise_alpha / (j * (j + 1.0))

    def per_reference_per_look_alpha(self, challenger_index: int) -> float:
        # Conservative Bonferroni within a challenger over the two fixed
        # references and every allowed sequential look.
        return self.challenger_family_alpha(challenger_index) / (
            2.0 * len(self.scheduled_looks)
        )


PRIMARY_STATISTICAL_L4 = StatisticalL4Config()


SENSITIVITY_STATISTICAL_L4 = (
    StatisticalL4Config(
        name="sensitivity_single_challenger_hac_lag3_12_to_20",
        method="hac",
        minimum_clean_blocks=12,
        look_step_blocks=4,
        maximum_clean_blocks=20,
        hac_lag_blocks=3,
    ),
    StatisticalL4Config(
        name="sensitivity_single_challenger_moving_block_bootstrap_l2",
        method="moving_block_bootstrap",
        minimum_clean_blocks=8,
        look_step_blocks=4,
        maximum_clean_blocks=16,
        bootstrap_block_length=2,
        # The stricter rollout-level tail probability requires more than the
        # former 4,000 draws for a meaningful diagnostic quantile.
        bootstrap_replicates=40000,
        bootstrap_seed=481516,
    ),
)


def _hac_bounds(
    differences: np.ndarray,
    *,
    alpha: float,
    lag_blocks: int,
) -> dict[str, float]:
    values = np.asarray(differences, dtype=float)
    count = len(values)
    mean = float(np.mean(values))
    centered = values - mean
    lag = min(int(lag_blocks), count - 1)
    gamma0 = float(centered @ centered / count)
    long_run_variance = gamma0
    autocovariances = []
    for offset in range(1, lag + 1):
        gamma = float(centered[offset:] @ centered[:-offset] / count)
        weight = 1.0 - offset / (lag + 1.0)
        long_run_variance += 2.0 * weight * gamma
        autocovariances.append(gamma)
    long_run_variance = max(float(long_run_variance), 0.0)
    standard_error = math.sqrt(long_run_variance / count)
    critical = float(student_t.ppf(1.0 - alpha, df=count - 1))
    return {
        "mean_difference_nms2": mean,
        "lower_bound_nms2": float(mean - critical * standard_error),
        "upper_bound_nms2": float(mean + critical * standard_error),
        "standard_error_nms2": standard_error,
        "critical_value": critical,
        "hac_lag_blocks": lag,
        "long_run_variance_nms4": long_run_variance,
        "autocovariances_nms4": autocovariances,
    }


def _moving_block_bootstrap_bounds(
    differences: np.ndarray,
    *,
    alpha: float,
    block_length: int,
    replicates: int,
    seed: int,
) -> dict[str, float]:
    values = np.asarray(differences, dtype=float)
    count = len(values)
    length = min(int(block_length), count)
    rng = np.random.default_rng(seed)
    block_count = int(math.ceil(count / length))
    starts = rng.integers(0, count, size=(replicates, block_count))
    offsets = np.arange(length, dtype=int)
    indices = (starts[:, :, None] + offsets[None, None, :]) % count
    samples = values[indices.reshape(replicates, -1)[:, :count]]
    bootstrap_means = np.mean(samples, axis=1)
    mean = float(np.mean(values))
    centered_bootstrap = bootstrap_means - mean
    # Basic, centered one-sided bounds. Circular contiguous resampling retains
    # local block-level serial dependence instead of resampling raw samples.
    lower = mean - float(np.quantile(centered_bootstrap, 1.0 - alpha))
    upper = mean - float(np.quantile(centered_bootstrap, alpha))
    return {
        "mean_difference_nms2": mean,
        "lower_bound_nms2": lower,
        "upper_bound_nms2": upper,
        "bootstrap_block_length": length,
        "bootstrap_replicates": int(replicates),
        "bootstrap_seed": int(seed),
        "bootstrap_mean_standard_deviation_nms2": float(
            np.std(bootstrap_means, ddof=1)
        ),
    }


def paired_difference_bounds(
    differences: np.ndarray,
    *,
    config: StatisticalL4Config,
    challenger_index: int = 0,
    seed_offset: int = 0,
) -> dict[str, Any]:
    """Return a one-sided correlation-robust interval for a paired mean."""

    values = np.asarray(differences, dtype=float)
    if values.ndim != 1 or len(values) < config.minimum_clean_blocks:
        raise ValueError("paired differences do not reach the first scheduled look")
    if len(values) not in config.scheduled_looks:
        raise ValueError("paired differences must be evaluated at a scheduled look")
    alpha = config.per_reference_per_look_alpha(challenger_index)
    if config.method == "hac":
        result = _hac_bounds(
            values,
            alpha=alpha,
            lag_blocks=config.hac_lag_blocks,
        )
    else:
        result = _moving_block_bootstrap_bounds(
            values,
            alpha=alpha,
            block_length=config.bootstrap_block_length,
            replicates=config.bootstrap_replicates,
            seed=config.bootstrap_seed + int(seed_offset),
        )
    return {
        "method": config.method,
        "sample_unit": "nonoverlapping_clean_integral_block",
        "block_count": int(len(values)),
        "per_reference_per_look_alpha": alpha,
        "one_sided_confidence_level": 1.0 - alpha,
        "challenger_index": int(challenger_index),
        "challenger_family_alpha": config.challenger_family_alpha(
            challenger_index
        ),
        "differences_nms2": values.tolist(),
        **result,
    }


def paired_promotion_evidence(
    candidate_losses: np.ndarray,
    prior_losses: np.ndarray,
    last_valid_losses: np.ndarray,
    *,
    config: StatisticalL4Config,
    challenger_index: int = 0,
    seed_offset: int = 0,
) -> dict[str, Any]:
    """Evaluate paired support for improvement against both references."""

    candidate = np.asarray(candidate_losses, dtype=float)
    prior = np.asarray(prior_losses, dtype=float)
    last = np.asarray(last_valid_losses, dtype=float)
    if candidate.shape != prior.shape or candidate.shape != last.shape:
        raise ValueError("paired losses must have identical block alignment")
    prior_evidence = paired_difference_bounds(
        candidate - prior,
        config=config,
        challenger_index=challenger_index,
        seed_offset=2 * seed_offset,
    )
    last_evidence = paired_difference_bounds(
        candidate - last,
        config=config,
        challenger_index=challenger_index,
        seed_offset=2 * seed_offset + 1,
    )
    supported = bool(
        prior_evidence["upper_bound_nms2"] < 0.0
        and last_evidence["upper_bound_nms2"] < 0.0
    )
    statistically_worse = bool(
        prior_evidence["lower_bound_nms2"] > 0.0
        or last_evidence["lower_bound_nms2"] > 0.0
    )
    return {
        "against_population_prior": prior_evidence,
        "against_last_valid": last_evidence,
        "promotion_supported": supported,
        "statistically_worse_than_at_least_one_reference": statistically_worse,
    }


def _identification_status(
    diagnostics: dict[str, Any], active: list[dict[str, Any]], identifier: Any
) -> str:
    full_rank = bool(
        diagnostics["rank"] == len(DYNAMIC_BASE_PARAMETER_NAMES)
        and diagnostics["rrqr_rank"] == len(DYNAMIC_BASE_PARAMETER_NAMES)
    )
    conditioned = bool(
        np.isfinite(diagnostics["condition_number"])
        and diagnostics["condition_number"]
        <= identifier.config.maximum_condition_number
    )
    if not (full_rank and conditioned):
        return "weakly_identified"
    return "identified_boundary_pressured" if active else "identified_interior"


def _oracle_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        item
        for item in records
        if np.isfinite(item.get("oracle_improvement_vs_last_valid_nm", np.nan))
    ]
    if not usable:
        return {
            "count": 0,
            "oracle_improvement_median_nm": float("nan"),
            "oracle_improvement_mean_nm": float("nan"),
            "oracle_worsened_count": 0,
            "oracle_improved_count": 0,
            "truth_distance_median_span_l2": float("nan"),
            "active_bound_frequency": float("nan"),
        }
    improvements = np.asarray(
        [item["oracle_improvement_vs_last_valid_nm"] for item in usable]
    )
    truth = np.asarray(
        [item["proposed_model_distance_to_truth_span_l2"] for item in usable]
    )
    return {
        "count": len(usable),
        "oracle_improvement_median_nm": float(np.median(improvements)),
        "oracle_improvement_mean_nm": float(np.mean(improvements)),
        "oracle_worsened_count": int(np.sum(improvements <= 0.0)),
        "oracle_improved_count": int(np.sum(improvements > 0.0)),
        "truth_distance_median_span_l2": float(np.median(truth)),
        "active_bound_frequency": float(
            np.mean([item["l3"]["active_bound_count"] > 0 for item in usable])
        ),
    }


def _oracle_selection_audit(
    promoted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> dict[str, Any]:
    promoted_usable = [
        item for item in promoted if np.isfinite(item["oracle_improvement_vs_last_valid_nm"])
    ]
    rejected_usable = [
        item for item in rejected if np.isfinite(item["oracle_improvement_vs_last_valid_nm"])
    ]
    decided_nonpromoted = rejected_usable
    prediction_pairs = [
        rejected_item["oracle_improvement_vs_last_valid_nm"]
        > promoted_item["oracle_improvement_vs_last_valid_nm"]
        for rejected_item in decided_nonpromoted
        for promoted_item in promoted_usable
    ]
    truth_pairs = [
        rejected_item["proposed_model_distance_to_truth_span_l2"]
        < promoted_item["proposed_model_distance_to_truth_span_l2"]
        for rejected_item in decided_nonpromoted
        for promoted_item in promoted_usable
    ]
    return {
        "promoted": _oracle_group(promoted),
        "statistically_rejected": _oracle_group(rejected),
        "decided_nonpromoted": _oracle_group(decided_nonpromoted),
        "cross_pair_probability_decided_nonpromoted_has_greater_oracle_improvement": (
            float(np.mean(prediction_pairs)) if prediction_pairs else float("nan")
        ),
        "cross_pair_probability_decided_nonpromoted_is_closer_to_true_beta": (
            float(np.mean(truth_pairs)) if truth_pairs else float("nan")
        ),
        "oracle_used_in_online_decision": False,
        "competing_challenger_race_possible": False,
    }


def audit_statistical_trust_case(
    *,
    case: MeasurementCase,
    details: dict[str, np.ndarray],
    initial_q_prior_rad: np.ndarray,
    true_beta: np.ndarray,
    statistical_config: StatisticalL4Config = PRIMARY_STATISTICAL_L4,
    hierarchy_config: HierarchicalTrustPrototypeConfig = HierarchicalTrustPrototypeConfig(),
) -> dict[str, Any]:
    """Replay one saved case with one causal incumbent--challenger pair."""

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
    retained_epoch = 0
    raw_history: list[dict[str, Any]] = []
    l1_records: list[dict[str, Any]] = []
    l2_records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    promotions: list[dict[str, Any]] = []
    maximum_concurrent_challengers = 0
    previous_arrival: float | None = None
    previous_ingested_sample: float | None = None
    estimated_state_by_source = np.full((len(arrival), 4), np.nan)
    window_s = dynamic_identifier.config.integration_window_s
    minimum_ready_offset = window_s * (
        hierarchy_config.validation_embargo_integral_windows
        + statistical_config.minimum_clean_blocks
    )

    def resolve_ready(now_s: float) -> None:
        nonlocal retained_beta, retained_epoch
        if len(pending) > 1:
            raise RuntimeError("more than one active challenger")
        still_pending: list[dict[str, Any]] = []
        for record in pending:
            # No other challenger can be launched while this record is active,
            # so its incumbent epoch and reference cannot race or be superseded.
            if record["reference_epoch"] != retained_epoch:
                raise RuntimeError("single challenger incumbent reference changed")
            if now_s < record["minimum_validation_ready_time_s"] - 1e-12:
                still_pending.append(record)
                continue
            blocks = _validation_blocks(
                raw_history,
                fit_end_time_s=record["fit_end_time_s"],
                window_s=window_s,
                embargo_windows=hierarchy_config.validation_embargo_integral_windows,
                count=statistical_config.maximum_clean_blocks,
            )
            decided = False
            for look_index, look_count in enumerate(statistical_config.scheduled_looks):
                if look_count in record["evaluated_look_block_counts"]:
                    continue
                if len(blocks) < look_count:
                    break
                selected = blocks[:look_count]
                proposed = np.asarray(record["proposed_model_beta"], dtype=float)
                reference = np.asarray(record["reference_last_valid_beta"], dtype=float)
                candidate_losses = _block_losses(proposed, selected)
                prior_losses = _block_losses(dynamic_identifier.population_prior, selected)
                last_losses = _block_losses(reference, selected)
                evidence = paired_promotion_evidence(
                    candidate_losses,
                    prior_losses,
                    last_losses,
                    config=statistical_config,
                    challenger_index=record["challenger_index"],
                    seed_offset=10000 * record["challenger_index"] + 100 * look_index,
                )
                evidence.update(
                    {
                        "look_index": look_index,
                        "look_block_count": look_count,
                        "decision_time_s": float(now_s),
                        "validation_blocks": [
                            {
                                "index": block["index"],
                                "future_slot": block["future_slot"],
                                "start_time_s": block["start_time_s"],
                                "end_time_s": block["end_time_s"],
                            }
                            for block in selected
                        ],
                    }
                )
                record["evidence_history"].append(evidence)
                record["evaluated_look_block_counts"].append(look_count)
                physical = BaseParameterHumanModel(
                    geometry_identifier.geometry, proposed
                ).minimum_mass_matrix_eigenvalue() > 1e-6
                if evidence["promotion_supported"] and physical:
                    record.update(
                        {
                            "control_model_status": "promoted",
                            "decision_time_s": float(now_s),
                            "decision_reason": "upper_bounds_below_zero_against_both_references",
                            "decision_block_count": look_count,
                            "validation_duration_s": float(
                                now_s - record["fit_end_time_s"]
                            ),
                            "valid_measurement_count_at_decision": len(raw_history),
                            "valid_measurements_accumulated_during_validation": (
                                len(raw_history)
                                - record["training_valid_measurement_count"]
                            ),
                            "positive_definite_proposed_model": True,
                            "decision_source_indices": sorted(
                                {
                                    int(source_index)
                                    for block in selected
                                    for source_index in block["source_indices"]
                                }
                            ),
                        }
                    )
                    retained_beta = proposed.copy()
                    retained_epoch += 1
                    promotions.append(
                        {
                            "challenger_index": record["challenger_index"],
                            "fit_end_time_s": record["fit_end_time_s"],
                            "promotion_time_s": float(now_s),
                            "promotion_phase_time_s": float(now_s),
                            "promotion_reference_phase_fraction": float(
                                np.clip(
                                    now_s / CONTINUOUS_TEACHING_DURATION_S,
                                    0.0,
                                    1.0,
                                )
                            ),
                            "decision_block_count": look_count,
                            "validation_duration_s": float(
                                now_s - record["fit_end_time_s"]
                            ),
                            "valid_measurement_count_at_decision": len(raw_history),
                            "valid_measurements_accumulated_during_validation": (
                                len(raw_history)
                                - record["training_valid_measurement_count"]
                            ),
                            "retained_epoch": retained_epoch,
                            "retained_beta": retained_beta.tolist(),
                        }
                    )
                    decided = True
                    break
                if look_count == statistical_config.maximum_clean_blocks:
                    record.update(
                        {
                            "control_model_status": "rejected_no_statistical_support",
                            "decision_time_s": float(now_s),
                            "decision_reason": (
                                "statistically_worse_than_reference"
                                if evidence[
                                    "statistically_worse_than_at_least_one_reference"
                                ]
                                else "insufficient_support_at_maximum_blocks"
                            ),
                            "decision_block_count": look_count,
                            "validation_duration_s": float(
                                now_s - record["fit_end_time_s"]
                            ),
                            "valid_measurement_count_at_decision": len(raw_history),
                            "valid_measurements_accumulated_during_validation": (
                                len(raw_history)
                                - record["training_valid_measurement_count"]
                            ),
                            "positive_definite_proposed_model": bool(physical),
                            "decision_source_indices": sorted(
                                {
                                    int(source_index)
                                    for block in selected
                                    for source_index in block["source_indices"]
                                }
                            ),
                        }
                    )
                    decided = True
                    break
            if not decided:
                still_pending.append(record)
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
            values=(
                position[index],
                rotation[index],
                linear[index],
                angular[index],
                force[index],
                moment[index],
            ),
            saturated=None,
            config=hierarchy_config,
        )
        l1_records.append(
            {
                "source_index": index,
                "arrival_time_s": float(arrival[index]),
                "sample_time_s": float(sample[index]),
                **l1,
            }
        )
        previous_arrival = float(arrival[index])
        if not l1["valid"]:
            resolve_ready(float(arrival[index]))
            continue
        previous_ingested_sample = float(sample[index])
        provisional = geometry_identifier.geometry.estimate_state(
            position[index], rotation[index], linear[index], angular[index]
        )
        contaminated = bool(
            bed_force[index] > BED_CONTACT_CONTAMINATION_FORCE_N
            or np.linalg.norm(
                soft_limit_torque(provisional[:2], provisional[2:], HUMAN)
            )
            > 1e-8
        )
        geometry_identifier.add_pose(
            float(sample[index]),
            position[index],
            rotation[index],
            contaminated=contaminated,
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
            config=hierarchy_config,
        )
        l2_records.append(
            {"source_index": index, "sample_time_s": float(sample[index]), **l2}
        )
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

        if (
            l2["valid"]
            and geometry_identifier.trustworthy_time_s is not None
            and not pending
        ):
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
                proposed = _apply_validated_estimator_step(
                    dynamic_identifier, retained_beta, candidate
                )
                record = {
                    "challenger_index": len(candidates),
                    "source_index": index,
                    "fit_end_time_s": float(sample[index]),
                    "training_valid_measurement_count": len(raw_history),
                    "minimum_validation_ready_time_s": float(
                        sample[index] + minimum_ready_offset
                    ),
                    "reference_epoch": retained_epoch,
                    "reference_last_valid_beta": retained_beta.tolist(),
                    "candidate_beta": candidate.tolist(),
                    "proposed_model_beta": proposed.tolist(),
                    "unconstrained_beta": unconstrained.tolist(),
                    "parameter_identification_status": _identification_status(
                        diagnostics, active, dynamic_identifier
                    ),
                    "legacy_estimator_accepted": bool(diagnostics["accepted"]),
                    "legacy_estimator_reason": diagnostics["reason"],
                    "control_model_status": "pending_statistical_evidence",
                    "evidence_history": [],
                    "evaluated_look_block_counts": [],
                    "l3": {
                        "rank": int(diagnostics["rank"]),
                        "rrqr_rank": int(diagnostics["rrqr_rank"]),
                        "condition_number": float(diagnostics["condition_number"]),
                        "candidate_residual_rms_nms": float(
                            diagnostics["candidate_residual_rms_nms"]
                        ),
                        "old_residual_rms_nms": float(
                            diagnostics["old_residual_rms_nms"]
                        ),
                        "integral_block_count": int(
                            diagnostics["integral_block_count"]
                        ),
                        "contaminated_integral_windows": int(
                            contaminated_windows
                        ),
                        "active_bound_count": int(
                            sum(item["constrained_hit"] for item in active)
                        ),
                        "active_or_pressured_bounds": active,
                        "unconstrained_normalized_bound_violation": (
                            _normalized_bound_violation(
                                dynamic_identifier, unconstrained
                            )
                        ),
                        "uncertainty": _uncertainty_diagnostics(
                            dynamic_identifier, regressor, target, candidate
                        ),
                    },
                }
                candidates.append(record)
                pending.append(record)
                if len(pending) != 1:
                    raise RuntimeError("single challenger launch invariant violated")
                maximum_concurrent_challengers = max(
                    maximum_concurrent_challengers, len(pending)
                )

    resolve_ready(float(sample[-1]))
    for record in pending:
        record.update(
            {
                "control_model_status": "pending_insufficient_future_evidence",
                "decision_reason": "trace_ended_before_statistical_decision",
                "validation_elapsed_at_trace_end_s": float(
                    sample[-1] - record["fit_end_time_s"]
                ),
                "valid_measurement_count_at_trace_end": len(raw_history),
                "valid_measurements_accumulated_during_validation": (
                    len(raw_history) - record["training_valid_measurement_count"]
                ),
            }
        )

    valid_source = np.flatnonzero(
        np.all(np.isfinite(estimated_state_by_source), axis=1)
    )
    estimated_ddq = np.full((len(arrival), 2), np.nan)
    if len(valid_source) >= 3:
        estimated_ddq[valid_source] = np.gradient(
            estimated_state_by_source[valid_source, 2:],
            sample[valid_source],
            axis=0,
            edge_order=2,
        )
    for record in candidates:
        if "decision_time_s" not in record or "decision_source_indices" not in record:
            continue
        indices = record["decision_source_indices"]
        proposed = np.asarray(record["proposed_model_beta"], dtype=float)
        reference = np.asarray(record["reference_last_valid_beta"], dtype=float)
        candidate_error = _oracle_prediction_error(
            proposed,
            indices,
            estimated_state=estimated_state_by_source,
            estimated_ddq=estimated_ddq,
            true_state=true_state,
            true_ddq=true_ddq,
            true_beta=np.asarray(true_beta, dtype=float),
            clean=clean,
        )
        reference_error = _oracle_prediction_error(
            reference,
            indices,
            estimated_state=estimated_state_by_source,
            estimated_ddq=estimated_ddq,
            true_state=true_state,
            true_ddq=true_ddq,
            true_beta=np.asarray(true_beta, dtype=float),
            clean=clean,
        )
        record["oracle_proposed_model_error_nm"] = candidate_error
        record["oracle_last_valid_error_nm"] = reference_error
        record["oracle_improvement_vs_last_valid_nm"] = float(
            reference_error - candidate_error
        )
        record["proposed_model_distance_to_truth_span_l2"] = float(
            np.linalg.norm(
                (proposed - true_beta) / dynamic_identifier.span
            )
        )
        record["reference_model_distance_to_truth_span_l2"] = float(
            np.linalg.norm(
                (reference - true_beta) / dynamic_identifier.span
            )
        )
        record["proposed_model_distance_to_prior_span_l2"] = float(
            np.linalg.norm(
                (proposed - dynamic_identifier.population_prior)
                / dynamic_identifier.span
            )
        )

    promoted_records = [
        item for item in candidates if item["control_model_status"] == "promoted"
    ]
    statistically_rejected = [
        item
        for item in candidates
        if item["control_model_status"] == "rejected_no_statistical_support"
    ]
    pending_records = [
        item
        for item in candidates
        if item["control_model_status"] == "pending_insufficient_future_evidence"
    ]
    promotion_times = [item["promotion_time_s"] for item in promotions]
    boundaries = [float(sample[0]), *promotion_times, float(sample[-1])]
    gaps = np.diff(boundaries)
    full_source_indices = [
        int(index)
        for index in valid_source
        if bool(clean[index]) and np.all(np.isfinite(estimated_ddq[index]))
    ]
    final_oracle = _oracle_prediction_error(
        retained_beta,
        full_source_indices,
        estimated_state=estimated_state_by_source,
        estimated_ddq=estimated_ddq,
        true_state=true_state,
        true_ddq=true_ddq,
        true_beta=np.asarray(true_beta, dtype=float),
        clean=clean,
    )
    prior_oracle = _oracle_prediction_error(
        dynamic_identifier.population_prior,
        full_source_indices,
        estimated_state=estimated_state_by_source,
        estimated_ddq=estimated_ddq,
        true_state=true_state,
        true_ddq=true_ddq,
        true_beta=np.asarray(true_beta, dtype=float),
        clean=clean,
    )
    final_regressor, final_target, final_contaminated = dynamic_identifier._integral_blocks(
        raw_history, geometry_identifier.geometry
    )
    return {
        "case": case.name,
        "production_default": False,
        "oracle_entered_online_decision": False,
        "statistical_config": {
            **asdict(statistical_config),
            "scheduled_looks": list(statistical_config.scheduled_looks),
            "alpha_spending": "alpha_j=familywise_alpha/[j(j+1)], j>=1",
            "unbounded_challenger_stream_alpha_sum": (
                statistical_config.familywise_alpha
            ),
        },
        "causal_semantics": {
            "fit_validation_embargo_s": (
                hierarchy_config.validation_embargo_integral_windows * window_s
            ),
            "validation_block_s": window_s,
            "raw_samples_are_inference_units": False,
            "paired_nonoverlapping_integral_blocks_are_inference_units": True,
            "one_incumbent_at_a_time": True,
            "maximum_concurrent_challengers": maximum_concurrent_challengers,
            "reference_is_frozen_per_challenger": True,
            "competing_challengers_launched": False,
            "next_challenger_uses_all_data_through_previous_decision": True,
            "challenger_can_be_superseded": False,
            "failed_promotion_deletes_training_data": False,
            "oracle_used_for_promotion": False,
        },
        "L1": {
            "valid_count": int(sum(item["valid"] for item in l1_records)),
            "invalid_count": int(sum(not item["valid"] for item in l1_records)),
            "reason_counts": {
                reason: int(
                    sum(reason in item["reasons"] for item in l1_records)
                )
                for reason in sorted(
                    {reason for item in l1_records for reason in item["reasons"]}
                )
            },
        },
        "L2": {
            "valid_count": int(sum(item["valid"] for item in l2_records)),
            "invalid_count": int(sum(not item["valid"] for item in l2_records)),
            "reason_counts": {
                reason: int(
                    sum(reason in item["reasons"] for item in l2_records)
                )
                for reason in sorted(
                    {reason for item in l2_records for reason in item["reasons"]}
                )
            },
        },
        "challengers": candidates,
        "promotions": promotions,
        "counts": {
            "challenger_count": len(candidates),
            "promoted": len(promoted_records),
            "statistically_rejected": len(statistically_rejected),
            "pending": len(pending_records),
        },
        "starvation": {
            "first_promotion_time_s": (
                float(promotion_times[0]) if promotion_times else None
            ),
            "first_promotion_reference_phase_fraction": (
                float(promotions[0]["promotion_reference_phase_fraction"])
                if promotions
                else None
            ),
            "time_since_last_promotion_s": (
                float(sample[-1] - promotion_times[-1])
                if promotion_times
                else float(sample[-1] - sample[0])
            ),
            "longest_no_promotion_interval_s": (
                float(np.max(gaps)) if len(gaps) else float(sample[-1] - sample[0])
            ),
            "valid_measurements_accumulated": len(raw_history),
            "final_integral_block_count": int(len(final_target) // 2),
            "final_contaminated_integral_windows": int(final_contaminated),
            "challenger_evidence_look_count": int(
                sum(len(item["evidence_history"]) for item in candidates)
            ),
            "training_data_retained_after_negative_decision": True,
            "maximum_concurrent_challengers": maximum_concurrent_challengers,
            "all_challengers_have_fixed_incumbent_reference": bool(
                all(
                    item["reference_epoch"]
                    == sum(
                        promotion["promotion_time_s"]
                        <= item["fit_end_time_s"] + 1e-12
                        for promotion in promotions
                    )
                    for item in candidates
                )
            ),
        },
        "oracle_selection_audit": _oracle_selection_audit(
            promoted_records, statistically_rejected
        ),
        "compensation_diagnostic": {
            "promoted_with_oracle_worsening_count": int(
                sum(
                    item.get("oracle_improvement_vs_last_valid_nm", float("nan"))
                    <= 0.0
                    for item in promoted_records
                )
            ),
            "promoted_count_with_oracle_available": int(
                sum(
                    np.isfinite(
                        item.get(
                            "oracle_improvement_vs_last_valid_nm", float("nan")
                        )
                    )
                    for item in promoted_records
                )
            ),
        },
        "full_trace_oracle_prediction": {
            "population_prior_error_nm": prior_oracle,
            "final_retained_error_nm": final_oracle,
            "retrospective_not_online_decision_metric": True,
        },
        "population_prior_distance_to_truth_span_l2": float(
            np.linalg.norm(
                (dynamic_identifier.population_prior - true_beta)
                / dynamic_identifier.span
            )
        ),
        "final_retained_distance_to_truth_span_l2": float(
            np.linalg.norm((retained_beta - true_beta) / dynamic_identifier.span)
        ),
        "final_retained_beta": retained_beta.tolist(),
        "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "production_estimator_controller_modified": False,
    }
