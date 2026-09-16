"""Reduced three-scale Stage-5 Human identification in shadow mode only.

The estimator uses the exact Stage-4 control-effective projection already used
by the beta11 diagnostic.  It does not claim anatomical parameter recovery and
has no connection to Goal-MPC or execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any

import numpy as np
from scipy.optimize import lsq_linear

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.hierarchical_trust import _validation_blocks
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import (
    CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
    dynamic_scale_projection,
    effective_base_parameters,
)
from traction_mpc_stage4.statistical_trust import (
    StatisticalL4Config,
    paired_promotion_evidence,
)

from .controller_interface import CONTROLLER_NOMINAL_INTERFACE
from .human import STAGE5_HUMAN
from .human_identification import Stage5HumanIDMeasurement


REDUCED_HUMAN_MODEL_VERSION_PREFIX = "stage5_human_shadow_scale3_v"


@dataclass(frozen=True)
class ReducedScaleIdentifierConfig:
    """Task-local numerical settings for the dimensionless three-scale fit.

    Bounds are broad engineering bounds around the frozen population prior,
    not anatomical confidence intervals.  Conditioning is reported from data
    only; no arbitrary finite condition-number threshold is used as a GO gate.
    """

    update_interval_measurements: int = 50
    integration_window_s: float = 0.20
    block_stride_measurements: int = 10
    minimum_integral_blocks: int = 16
    lower_scales: tuple[float, float, float] = (0.50, 0.50, 0.50)
    upper_scales: tuple[float, float, float] = (1.50, 1.50, 1.50)
    regularization_weight: float = 1.0e-3
    smoothing_alpha: float = 0.10
    maximum_update_fraction_of_span: float = 0.03

    def __post_init__(self) -> None:
        lower = np.asarray(self.lower_scales, dtype=float)
        upper = np.asarray(self.upper_scales, dtype=float)
        if lower.shape != (3,) or upper.shape != (3,) or np.any(lower >= upper):
            raise ValueError("three finite ordered scale bounds are required")
        if not np.all(np.isfinite([*lower, *upper])):
            raise ValueError("scale bounds must be finite")
        if self.update_interval_measurements < 1 or self.minimum_integral_blocks < 1:
            raise ValueError("identifier counts must be positive")
        if self.integration_window_s <= 0.0 or self.block_stride_measurements < 1:
            raise ValueError("window and stride must be positive")
        if self.regularization_weight < 0.0:
            raise ValueError("regularization weight cannot be negative")
        if not 0.0 < self.smoothing_alpha <= 1.0:
            raise ValueError("smoothing alpha must lie in (0,1]")
        if not 0.0 < self.maximum_update_fraction_of_span <= 1.0:
            raise ValueError("maximum update fraction must lie in (0,1]")


@dataclass(frozen=True)
class Stage5ReducedHumanIDConfig:
    accepted_interface_model_version: str = CONTROLLER_NOMINAL_INTERFACE.model_version
    identifier: ReducedScaleIdentifierConfig = field(
        default_factory=ReducedScaleIdentifierConfig
    )
    trust: StatisticalL4Config = field(
        default_factory=lambda: StatisticalL4Config(
            name="stage5_shadow_human_scale3_hac_lag2_8_to_12",
            method="hac",
            familywise_alpha=0.05,
            minimum_clean_blocks=8,
            look_step_blocks=2,
            maximum_clean_blocks=12,
            hac_lag_blocks=2,
        )
    )
    validation_embargo_integral_windows: int = 1
    generalized_input_consistency_tolerance_nm: float = 1.0e-8

    def __post_init__(self) -> None:
        if not self.accepted_interface_model_version:
            raise ValueError("accepted interface model version must be explicit")
        if self.validation_embargo_integral_windows < 1:
            raise ValueError("at least one full-window embargo is required")
        if self.generalized_input_consistency_tolerance_nm < 0.0:
            raise ValueError("generalized-input tolerance cannot be negative")


@dataclass(frozen=True)
class ReducedHumanModelPublication:
    scales: np.ndarray
    beta: np.ndarray
    version: str
    timestamp_s: float
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "scales": np.asarray(self.scales, dtype=float).tolist(),
            "scale_names": list(CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES),
            "beta": np.asarray(self.beta, dtype=float).tolist(),
            "version": self.version,
            "timestamp_s": float(self.timestamp_s),
            "shadow_only": True,
            "applied_to_control": False,
            "interpretation": "control_effective_scales_not_anatomical_truth",
        }


def reduced_information(regressor: np.ndarray) -> dict[str, Any]:
    """Return unregularized, column-normalized information diagnostics."""

    matrix = np.asarray(regressor, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 3:
        raise ValueError("reduced regressor must be Nx3")
    if not len(matrix):
        return {
            "rank": 0,
            "dimension": 3,
            "condition_number": float("inf"),
            "singular_values": [],
            "correlation_matrix": np.full((3, 3), np.nan).tolist(),
            "maximum_abs_parameter_correlation": float("nan"),
            "regularization_counted_as_information": False,
        }
    norms = np.linalg.norm(matrix, axis=0)
    normalized = matrix / np.where(norms > 1.0e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1.0e-10
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    condition = (
        float(singular[0] / singular[-1])
        if singular[-1] > 1.0e-15
        else float("inf")
    )
    covariance_shape = np.linalg.pinv(matrix.T @ matrix, rcond=1.0e-12)
    std = np.sqrt(np.maximum(np.diag(covariance_shape), 0.0))
    denominator = np.outer(std, std)
    correlation = np.divide(
        covariance_shape,
        denominator,
        out=np.full_like(covariance_shape, np.nan),
        where=denominator > 0.0,
    )
    np.fill_diagonal(correlation, 0.0)
    return {
        "rank": rank,
        "dimension": 3,
        "condition_number": condition,
        "singular_values": singular.tolist(),
        "correlation_matrix": correlation.tolist(),
        "maximum_abs_parameter_correlation": float(
            np.nanmax(np.abs(correlation))
        ),
        "column_norms": norms.tolist(),
        "regularization_counted_as_information": False,
    }


class ReducedIntegralScaleIdentifier:
    """Bounded convex fit of the frozen three-scale projection."""

    def __init__(
        self,
        config: ReducedScaleIdentifierConfig = ReducedScaleIdentifierConfig(),
    ) -> None:
        self.config = config
        self.prior = np.ones(3)
        self.lower = np.asarray(config.lower_scales, dtype=float)
        self.upper = np.asarray(config.upper_scales, dtype=float)
        self.span = self.upper - self.lower
        self.last_attempt_measurement_count = 0

    def integral_blocks(
        self, raw_history: list[dict[str, Any]], geometry: PlanarCuffGeometry
    ) -> tuple[np.ndarray, np.ndarray, int]:
        times = np.asarray([item["time_s"] for item in raw_history], dtype=float)
        regressors: list[np.ndarray] = []
        targets: list[np.ndarray] = []
        contaminated_windows = 0
        projection = dynamic_scale_projection(nominal_base_parameters(STAGE5_HUMAN))
        for end in range(
            self.config.block_stride_measurements,
            len(raw_history),
            self.config.block_stride_measurements,
        ):
            start = int(
                np.searchsorted(
                    times,
                    times[end] - self.config.integration_window_s,
                    side="left",
                )
            )
            if times[end] - times[start] < 0.90 * self.config.integration_window_s:
                continue
            segment = raw_history[start : end + 1]
            if any(bool(item["contaminated"]) for item in segment):
                contaminated_windows += 1
                continue
            time = times[start : end + 1]
            state = np.asarray([item["state"] for item in segment], dtype=float)
            torque = np.asarray(
                [
                    geometry.generalized_input_from_wrench(
                        item["state"][:2],
                        item["force_world_n"],
                        item["moment_world_nm"],
                    )
                    for item in segment
                ],
                dtype=float,
            )
            full_regressor, target = integral_regression_block(time, state, torque)
            regressors.append(full_regressor @ projection)
            targets.append(target)
        if not regressors:
            return np.empty((0, 3)), np.empty(0), contaminated_windows
        return np.vstack(regressors), np.concatenate(targets), contaminated_windows

    def attempt(
        self,
        raw_history: list[dict[str, Any]],
        geometry: PlanarCuffGeometry,
        incumbent_scales: np.ndarray,
    ) -> dict[str, Any]:
        if (
            len(raw_history) - self.last_attempt_measurement_count
            < self.config.update_interval_measurements
        ):
            return self._empty("between_updates")
        self.last_attempt_measurement_count = len(raw_history)
        regressor, target, contaminated = self.integral_blocks(raw_history, geometry)
        block_count = len(target) // 2
        if block_count < self.config.minimum_integral_blocks:
            output = self._empty("insufficient_clean_integral_blocks")
            output.update(
                {
                    "integral_block_count": block_count,
                    "contaminated_integral_windows": contaminated,
                }
            )
            return output

        information = reduced_information(regressor * self.span)
        incumbent = np.asarray(incumbent_scales, dtype=float)
        old_residual = regressor @ incumbent - target
        regularization = math.sqrt(self.config.regularization_weight)
        augmented_a = np.vstack([regressor, regularization * np.diag(1.0 / self.span)])
        augmented_b = np.concatenate(
            [target, regularization * self.prior / self.span]
        )
        try:
            result = lsq_linear(
                augmented_a,
                augmented_b,
                bounds=(self.lower, self.upper),
                method="trf",
                lsmr_tol="auto",
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            output = self._empty(f"optimizer_exception:{type(error).__name__}")
            output["attempted"] = True
            return output
        candidate = np.asarray(result.x, dtype=float)
        candidate_residual = regressor @ candidate - target
        old_rms = float(np.sqrt(np.mean(old_residual**2)))
        candidate_rms = float(np.sqrt(np.mean(candidate_residual**2)))
        bound_hit = bool(
            np.any(np.isclose(candidate, self.lower, atol=1.0e-7, rtol=0.0))
            or np.any(np.isclose(candidate, self.upper, atol=1.0e-7, rtol=0.0))
        )
        beta = effective_base_parameters(
            candidate, nominal_base_parameters(STAGE5_HUMAN)
        )
        positive_definite = (
            BaseParameterHumanModel(geometry, beta, STAGE5_HUMAN)
            .minimum_mass_matrix_eigenvalue()
            > 1.0e-6
        )
        reasons: list[str] = []
        if not result.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if information["rank"] < 3:
            reasons.append("data_rank_deficient")
        if not np.isfinite(information["condition_number"]):
            reasons.append("nonfinite_data_condition")
        if candidate_rms > old_rms * (1.0 + 1.0e-9) + 1.0e-12:
            reasons.append("training_residual_worse_than_incumbent")
        if bound_hit:
            reasons.append("bound_hit")
        if not positive_definite:
            reasons.append("non_positive_definite_mass_matrix")
        return {
            "attempted": True,
            "accepted": not reasons,
            "reason": "accepted" if not reasons else ",".join(reasons),
            "raw_measurement_count": len(raw_history),
            "integral_block_count": block_count,
            "contaminated_integral_windows": contaminated,
            "integration_window_s": self.config.integration_window_s,
            "candidate_scales": candidate.tolist(),
            "candidate_beta": beta.tolist(),
            "incumbent_residual_rms_nms": old_rms,
            "candidate_residual_rms_nms": candidate_rms,
            "bound_hit": bound_hit,
            "bound_pressure": {
                "minimum_fraction_of_span": float(
                    np.min((candidate - self.lower) / self.span)
                ),
                "maximum_fraction_of_span": float(
                    np.max((candidate - self.lower) / self.span)
                ),
            },
            "positive_definite_mass_matrix": positive_definite,
            "information": information,
            "regularization_weight": self.config.regularization_weight,
            "regularization_counted_as_information": False,
            "last_valid_fallback_used": bool(reasons),
        }

    def bounded_smoothed_step(
        self, incumbent: np.ndarray, candidate: np.ndarray
    ) -> np.ndarray:
        retained = np.asarray(incumbent, dtype=float)
        raw = np.asarray(candidate, dtype=float)
        step = self.config.smoothing_alpha * (raw - retained)
        maximum_step = self.config.maximum_update_fraction_of_span * self.span
        return np.clip(
            retained + np.clip(step, -maximum_step, maximum_step),
            self.lower,
            self.upper,
        )

    @staticmethod
    def _empty(reason: str) -> dict[str, Any]:
        return {
            "attempted": False,
            "accepted": False,
            "reason": reason,
            "rank": 0,
            "condition_number": float("nan"),
            "last_valid_fallback_used": True,
        }


def _reduced_block_losses(
    scales: np.ndarray,
    blocks: list[dict[str, Any]],
    projection: np.ndarray,
) -> np.ndarray:
    values = np.asarray(scales, dtype=float)
    return np.asarray(
        [
            float(
                np.mean(
                    (block["regressor"] @ projection @ values - block["target"])
                    ** 2
                )
            )
            for block in blocks
        ],
        dtype=float,
    )


class ReducedShadowHumanIdentificationService:
    """One-challenger reduced Human-ID lifecycle with shadow-only publication."""

    def __init__(
        self,
        geometry: PlanarCuffGeometry,
        config: Stage5ReducedHumanIDConfig = Stage5ReducedHumanIDConfig(),
    ) -> None:
        self.geometry = geometry
        self.config = config
        self.identifier = ReducedIntegralScaleIdentifier(config.identifier)
        self.prior_beta = nominal_base_parameters(STAGE5_HUMAN)
        self.projection = dynamic_scale_projection(self.prior_beta)
        self.retained_scales = np.ones(3)
        self.publication = ReducedHumanModelPublication(
            scales=self.retained_scales.copy(),
            beta=effective_base_parameters(self.retained_scales, self.prior_beta),
            version=f"{REDUCED_HUMAN_MODEL_VERSION_PREFIX}0",
            timestamp_s=0.0,
        )
        self.raw_history: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []
        self.active_challenger: dict[str, Any] | None = None
        self.publication_history = [self.publication.to_dict()]
        self.last_arrival_time_s: float | None = None
        self.last_sample_time_s: float | None = None
        self.rejected_measurements = 0
        self.first_trustworthy_candidate_time_s: float | None = None

    @property
    def retained_model(self) -> BaseParameterHumanModel:
        return BaseParameterHumanModel(
            self.geometry, self.publication.beta, STAGE5_HUMAN
        )

    def _measurement_reason(self, measurement: Stage5HumanIDMeasurement) -> str | None:
        if measurement.interface_model_version != self.config.accepted_interface_model_version:
            return "interface_model_version_mismatch"
        arrays = (
            measurement.estimated_human_state_rad_rad_s,
            measurement.measured_human_cuff_force_world_n,
            measurement.measured_human_cuff_moment_world_nm,
            measurement.measured_generalized_human_input_nm,
        )
        shapes = ((4,), (3,), (3,), (2,))
        if any(np.asarray(value).shape != shape for value, shape in zip(arrays, shapes, strict=True)):
            return "measurement_shape_invalid"
        if not all(np.all(np.isfinite(value)) for value in arrays):
            return "nonfinite_measurement"
        if not np.isfinite([measurement.arrival_time_s, measurement.sample_time_s]).all():
            return "nonfinite_measurement"
        if not measurement.new_sample:
            return "duplicate_or_zoh_sample"
        if measurement.sample_time_s > measurement.arrival_time_s + 1.0e-12:
            return "future_sample"
        if self.last_arrival_time_s is not None and measurement.arrival_time_s <= self.last_arrival_time_s + 1.0e-12:
            return "nonmonotonic_arrival_time"
        if self.last_sample_time_s is not None and measurement.sample_time_s <= self.last_sample_time_s + 1.0e-12:
            return "nonmonotonic_sample_time"
        state = np.asarray(measurement.estimated_human_state_rad_rad_s, dtype=float)
        mapped = self.geometry.generalized_input_from_wrench(
            state[:2],
            measurement.measured_human_cuff_force_world_n,
            measurement.measured_human_cuff_moment_world_nm,
        )
        mismatch = np.max(
            np.abs(
                mapped
                - np.asarray(measurement.measured_generalized_human_input_nm, dtype=float)
            )
        )
        if mismatch > self.config.generalized_input_consistency_tolerance_nm:
            return "wrench_generalized_input_inconsistent"
        return None

    def observe(self, measurement: Stage5HumanIDMeasurement) -> dict[str, Any]:
        reason = self._measurement_reason(measurement)
        self.last_arrival_time_s = float(measurement.arrival_time_s)
        if reason is not None:
            self.rejected_measurements += 1
            return self.status(
                update_diagnostics={"accepted": False, "reason": reason}
            )
        self.last_sample_time_s = float(measurement.sample_time_s)
        state = np.asarray(measurement.estimated_human_state_rad_rad_s, dtype=float)
        self.raw_history.append(
            {
                "time_s": float(measurement.sample_time_s),
                "state": state.copy(),
                "force_world_n": np.asarray(
                    measurement.measured_human_cuff_force_world_n, dtype=float
                ).copy(),
                "moment_world_nm": np.asarray(
                    measurement.measured_human_cuff_moment_world_nm, dtype=float
                ).copy(),
                "generalized_input_nm": np.asarray(
                    measurement.measured_generalized_human_input_nm, dtype=float
                ).copy(),
                "contaminated": bool(
                    np.linalg.norm(
                        soft_limit_torque(state[:2], state[2:], STAGE5_HUMAN)
                    )
                    > 1.0e-8
                ),
                "source_index": len(self.raw_history),
                "task_phase": str(measurement.task_phase),
            }
        )
        validation = self._resolve_challenger(float(measurement.sample_time_s))
        proposal = None
        if self.active_challenger is None:
            proposal = self._launch_challenger(float(measurement.sample_time_s))
        return self.status(
            update_diagnostics={
                "accepted": True,
                "reason": "ingested",
                "proposal": proposal,
                "validation": validation,
            }
        )

    def _launch_challenger(self, now_s: float) -> dict[str, Any]:
        diagnostics = self.identifier.attempt(
            self.raw_history, self.geometry, self.retained_scales
        )
        if not diagnostics.get("attempted", False):
            return dict(diagnostics)
        attempt: dict[str, Any] = {
            "challenger_index": len(self.attempts),
            "fit_end_time_s": now_s,
            "training_diagnostics": dict(diagnostics),
            "status": "rejected_training_gate",
            "qualified": False,
            "applied_to_control": False,
            "shadow_only": True,
        }
        if not diagnostics.get("accepted", False):
            self.attempts.append(attempt)
            return attempt
        candidate = np.asarray(diagnostics["candidate_scales"], dtype=float)
        proposed = self.identifier.bounded_smoothed_step(
            self.retained_scales, candidate
        )
        attempt.update(
            {
                "minimum_validation_ready_time_s": float(
                    now_s
                    + self.config.identifier.integration_window_s
                    * (
                        self.config.validation_embargo_integral_windows
                        + self.config.trust.minimum_clean_blocks
                    )
                ),
                "reference_incumbent_scales": self.retained_scales.tolist(),
                "candidate_scales": candidate.tolist(),
                "proposed_model_scales": proposed.tolist(),
                "proposed_model_beta": effective_base_parameters(
                    proposed, self.prior_beta
                ).tolist(),
                "status": "pending_future_validation",
                "evidence_history": [],
                "evaluated_look_block_counts": [],
                "information": diagnostics["information"],
                "bound_pressure": diagnostics["bound_pressure"],
            }
        )
        self.attempts.append(attempt)
        self.active_challenger = attempt
        return attempt

    def _resolve_challenger(self, now_s: float) -> dict[str, Any] | None:
        record = self.active_challenger
        if record is None or now_s < record["minimum_validation_ready_time_s"] - 1.0e-12:
            return None
        blocks = _validation_blocks(
            self.raw_history,
            fit_end_time_s=float(record["fit_end_time_s"]),
            window_s=self.config.identifier.integration_window_s,
            embargo_windows=self.config.validation_embargo_integral_windows,
            count=self.config.trust.maximum_clean_blocks,
        )
        proposed = np.asarray(record["proposed_model_scales"], dtype=float)
        reference = np.asarray(record["reference_incumbent_scales"], dtype=float)
        for look_index, look_count in enumerate(self.config.trust.scheduled_looks):
            if look_count in record["evaluated_look_block_counts"]:
                continue
            if len(blocks) < look_count:
                break
            selected = blocks[:look_count]
            evidence = paired_promotion_evidence(
                _reduced_block_losses(proposed, selected, self.projection),
                _reduced_block_losses(np.ones(3), selected, self.projection),
                _reduced_block_losses(reference, selected, self.projection),
                config=self.config.trust,
                challenger_index=int(record["challenger_index"]),
                seed_offset=10000 * int(record["challenger_index"])
                + 100 * look_index,
            )
            evidence.update(
                {
                    "look_index": look_index,
                    "decision_time_s": now_s,
                    "validation_windows": [
                        [float(block["start_time_s"]), float(block["end_time_s"])]
                        for block in selected
                    ],
                }
            )
            record["evidence_history"].append(evidence)
            record["evaluated_look_block_counts"].append(look_count)
            beta = effective_base_parameters(proposed, self.prior_beta)
            positive_definite = (
                BaseParameterHumanModel(self.geometry, beta, STAGE5_HUMAN)
                .minimum_mass_matrix_eigenvalue()
                > 1.0e-6
            )
            if evidence["promotion_supported"] and positive_definite:
                self.retained_scales = proposed.copy()
                version_index = len(self.publication_history)
                self.publication = ReducedHumanModelPublication(
                    scales=proposed.copy(),
                    beta=beta,
                    version=f"{REDUCED_HUMAN_MODEL_VERSION_PREFIX}{version_index}",
                    timestamp_s=now_s,
                )
                self.publication_history.append(self.publication.to_dict())
                if self.first_trustworthy_candidate_time_s is None:
                    self.first_trustworthy_candidate_time_s = now_s
                record.update(
                    {
                        "status": "published_to_shadow_incumbent",
                        "qualified": True,
                        "decision_time_s": now_s,
                        "decision_block_count": look_count,
                        "positive_definite_proposed_model": True,
                    }
                )
                self.active_challenger = None
                return evidence
            if look_count == self.config.trust.maximum_clean_blocks:
                record.update(
                    {
                        "status": "rejected_no_future_support",
                        "qualified": False,
                        "decision_time_s": now_s,
                        "decision_block_count": look_count,
                        "positive_definite_proposed_model": bool(positive_definite),
                    }
                )
                self.active_challenger = None
                return evidence
        return None

    def status(
        self, *, update_diagnostics: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        trust_state = (
            "CHALLENGER_PENDING"
            if self.active_challenger is not None
            else (
                "SHADOW_INCUMBENT_VALIDATED"
                if len(self.publication_history) > 1
                else "PRIOR_ONLY"
            )
        )
        return {
            "retained_model": self.publication.to_dict(),
            "challenger": self.active_challenger,
            "trust_state": trust_state,
            "measurement_count": len(self.raw_history),
            "rejected_measurement_count": self.rejected_measurements,
            "update_diagnostics": update_diagnostics,
            "shadow_only": True,
            "applied_to_control": False,
            "accepted_interface_model_version": self.config.accepted_interface_model_version,
        }

    def summary(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for record in self.attempts:
            status = str(record["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "schema": "stage5_reduced_shadow_human_identification_summary_v1",
            "config": {
                "identifier": asdict(self.config.identifier),
                "trust": asdict(self.config.trust),
                "validation_embargo_integral_windows": self.config.validation_embargo_integral_windows,
                "accepted_interface_model_version": self.config.accepted_interface_model_version,
            },
            "measurement_count": len(self.raw_history),
            "rejected_measurement_count": self.rejected_measurements,
            "attempt_count": len(self.attempts),
            "attempt_status_counts": status_counts,
            "first_trustworthy_candidate_time_s": self.first_trustworthy_candidate_time_s,
            "retained_model": self.publication.to_dict(),
            "publication_history": list(self.publication_history),
            "attempts": list(self.attempts),
            "shadow_only": True,
            "control_model_changed": False,
            "truth_available_to_service": False,
        }


__all__ = [
    "REDUCED_HUMAN_MODEL_VERSION_PREFIX",
    "ReducedHumanModelPublication",
    "ReducedIntegralScaleIdentifier",
    "ReducedScaleIdentifierConfig",
    "ReducedShadowHumanIdentificationService",
    "Stage5ReducedHumanIDConfig",
    "reduced_information",
]
