"""Stage-5 shadow-only Human base-dynamics identification service.

The service reuses the Stage-4 integral regression and future-validation
machinery, but its measurement boundary begins after the Stage-5 deployable
Human/interface observer.  No retained model from this module is connected to
Goal-MPC or execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    DYNAMIC_BASE_PARAMETER_NAMES,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.hierarchical_trust import (
    _apply_validated_estimator_step,
    _block_losses,
    _validation_blocks,
)
from traction_mpc_stage4.integral_identifier import (
    AccumulatedIntegralBaseDynamicIdentifier,
    IntegralDynamicIdentifierConfig,
)
from traction_mpc_stage4.statistical_trust import (
    StatisticalL4Config,
    paired_promotion_evidence,
)

from .controller_interface import CONTROLLER_NOMINAL_INTERFACE
from .human import STAGE5_HUMAN


SHADOW_HUMAN_MODEL_VERSION_PREFIX = "stage5_human_shadow_beta11_v"


@dataclass(frozen=True)
class Stage5HumanIDConfig:
    """Stage-5 diagnostic settings, independently declared from Stage 4.

    The 0.20 s integral window is long relative to the 5 ms sensor period but
    short enough to preserve OUTBOUND/HOLD/RETURN localization in a roughly
    five-second task.  Eight disjoint future blocks plus one-window embargo
    require at least 1.8 s of genuinely future evidence before qualification.
    These are shadow-study settings, not inherited safety thresholds.
    """

    accepted_interface_model_version: str = CONTROLLER_NOMINAL_INTERFACE.model_version
    identifier: IntegralDynamicIdentifierConfig = field(
        default_factory=lambda: IntegralDynamicIdentifierConfig(
            update_interval_measurements=50,
            integration_window_s=0.20,
            block_stride_measurements=10,
            minimum_integral_blocks=16,
            maximum_condition_number=1.0e5,
            residual_acceptance_ratio=1.02,
            residual_absolute_allowance_nms=0.025,
            regularization_weight=1.0e-3,
            smoothing_alpha=0.10,
            maximum_update_fraction_of_span=0.03,
        )
    )
    trust: StatisticalL4Config = field(
        default_factory=lambda: StatisticalL4Config(
            name="stage5_shadow_human_id_hac_lag2_8_to_12",
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
            raise ValueError("at least one full integral-window embargo is required")
        if self.generalized_input_consistency_tolerance_nm < 0.0:
            raise ValueError("generalized-input tolerance cannot be negative")


@dataclass(frozen=True)
class Stage5HumanIDMeasurement:
    """Truth-free deployable input contract for one new 200 Hz sample."""

    arrival_time_s: float
    sample_time_s: float
    estimated_human_state_rad_rad_s: np.ndarray
    measured_human_cuff_force_world_n: np.ndarray
    measured_human_cuff_moment_world_nm: np.ndarray
    measured_generalized_human_input_nm: np.ndarray
    task_phase: str
    interface_model_version: str
    new_sample: bool = True


@dataclass(frozen=True)
class HumanModelPublication:
    beta: np.ndarray
    version: str
    timestamp_s: float
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "beta": np.asarray(self.beta, dtype=float).tolist(),
            "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
            "version": self.version,
            "timestamp_s": float(self.timestamp_s),
            "shadow_only": bool(self.shadow_only),
            "applied_to_control": False,
        }


def _matrix_information(regressor: np.ndarray, span: np.ndarray) -> dict[str, Any]:
    scaled = np.asarray(regressor, dtype=float) * np.asarray(span, dtype=float)
    norms = np.linalg.norm(scaled, axis=0)
    normalized = scaled / np.where(norms > 1.0e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.linalg.matrix_rank(normalized, tol=(singular[0] * 1.0e-10)))
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1.0e-15
        else float("inf")
    )
    covariance_shape = np.linalg.pinv(scaled.T @ scaled, rcond=1.0e-12)
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
        "condition_number": condition,
        "singular_values": singular.tolist(),
        "correlation_matrix": correlation.tolist(),
        "maximum_abs_parameter_correlation": float(
            np.nanmax(np.abs(correlation))
        ),
    }


class ShadowHumanIdentificationService:
    """One-challenger, embargoed, shadow-publication Human-ID lifecycle."""

    def __init__(
        self,
        geometry: PlanarCuffGeometry,
        config: Stage5HumanIDConfig = Stage5HumanIDConfig(),
    ) -> None:
        self.geometry = geometry
        self.config = config
        self.identifier = AccumulatedIntegralBaseDynamicIdentifier(config.identifier)
        prior = nominal_base_parameters(STAGE5_HUMAN)
        if not np.allclose(self.identifier.population_prior, prior, atol=0.0, rtol=0.0):
            raise ValueError("Stage-5 dynamic prior differs from Stage-4 beta basis")
        self.retained_beta = prior.copy()
        self.publication = HumanModelPublication(
            beta=prior.copy(),
            version=f"{SHADOW_HUMAN_MODEL_VERSION_PREFIX}0",
            timestamp_s=0.0,
        )
        self.raw_history: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []
        self.active_challenger: dict[str, Any] | None = None
        self.publication_history: list[dict[str, Any]] = [self.publication.to_dict()]
        self.last_arrival_time_s: float | None = None
        self.last_sample_time_s: float | None = None
        self.rejected_measurements = 0
        self.first_trustworthy_candidate_time_s: float | None = None

    @property
    def retained_model(self) -> BaseParameterHumanModel:
        return BaseParameterHumanModel(self.geometry, self.retained_beta, STAGE5_HUMAN)

    @property
    def challenger_model(self) -> BaseParameterHumanModel | None:
        if self.active_challenger is None:
            return None
        return BaseParameterHumanModel(
            self.geometry,
            np.asarray(self.active_challenger["proposed_model_beta"], dtype=float),
            STAGE5_HUMAN,
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
        expected_shapes = ((4,), (3,), (3,), (2,))
        if any(np.asarray(value).shape != shape for value, shape in zip(arrays, expected_shapes, strict=True)):
            return "measurement_shape_invalid"
        if not all(np.all(np.isfinite(value)) for value in arrays) or not np.isfinite(
            [measurement.arrival_time_s, measurement.sample_time_s]
        ).all():
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
        mismatch = float(
            np.max(
                np.abs(
                    mapped
                    - np.asarray(
                        measurement.measured_generalized_human_input_nm, dtype=float
                    )
                )
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
            return self.status(update_diagnostics={"accepted": False, "reason": reason})

        self.last_sample_time_s = float(measurement.sample_time_s)
        state = np.asarray(measurement.estimated_human_state_rad_rad_s, dtype=float)
        contaminated = bool(
            np.linalg.norm(soft_limit_torque(state[:2], state[2:], STAGE5_HUMAN))
            > 1.0e-8
        )
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
                "contaminated": contaminated,
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
        identifier = self.identifier
        identifier.last_valid = self.retained_beta.copy()
        diagnostics = identifier.attempt_update(self.raw_history, self.geometry)
        identifier.last_valid = self.retained_beta.copy()
        if not diagnostics.get("attempted", False):
            return dict(diagnostics)

        attempt: dict[str, Any] = {
            "challenger_index": len(self.attempts),
            "fit_end_time_s": now_s,
            "training_diagnostics": dict(diagnostics),
            "status": "rejected_training_gate",
            "qualified": False,
            "applied_to_control": False,
        }
        if not diagnostics.get("accepted", False):
            self.attempts.append(attempt)
            return attempt

        regressor, target, contaminated_windows = identifier._integral_blocks(
            self.raw_history, self.geometry
        )
        candidate = np.asarray(diagnostics["candidate"], dtype=float)
        proposed = _apply_validated_estimator_step(
            identifier, self.retained_beta, candidate
        )
        information = _matrix_information(regressor, identifier.span)
        attempt.update(
            {
                "minimum_validation_ready_time_s": float(
                    now_s
                    + identifier.config.integration_window_s
                    * (
                        self.config.validation_embargo_integral_windows
                        + self.config.trust.minimum_clean_blocks
                    )
                ),
                "reference_incumbent_beta": self.retained_beta.tolist(),
                "candidate_beta": candidate.tolist(),
                "proposed_model_beta": proposed.tolist(),
                "status": "pending_future_validation",
                "evidence_history": [],
                "evaluated_look_block_counts": [],
                "contaminated_integral_windows": contaminated_windows,
                "information": information,
                "bound_pressure": {
                    "candidate_min_fraction_of_span": float(
                        np.min((candidate - identifier.lower) / identifier.span)
                    ),
                    "candidate_max_fraction_of_span": float(
                        np.max((candidate - identifier.lower) / identifier.span)
                    ),
                    "bound_hit": bool(diagnostics.get("bound_hit", False)),
                },
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
            window_s=self.identifier.config.integration_window_s,
            embargo_windows=self.config.validation_embargo_integral_windows,
            count=self.config.trust.maximum_clean_blocks,
        )
        proposed = np.asarray(record["proposed_model_beta"], dtype=float)
        reference = np.asarray(record["reference_incumbent_beta"], dtype=float)
        for look_index, look_count in enumerate(self.config.trust.scheduled_looks):
            if look_count in record["evaluated_look_block_counts"]:
                continue
            if len(blocks) < look_count:
                break
            selected = blocks[:look_count]
            evidence = paired_promotion_evidence(
                _block_losses(proposed, selected),
                _block_losses(self.identifier.population_prior, selected),
                _block_losses(reference, selected),
                config=self.config.trust,
                challenger_index=int(record["challenger_index"]),
                seed_offset=10000 * int(record["challenger_index"]) + 100 * look_index,
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
            positive_definite = (
                BaseParameterHumanModel(self.geometry, proposed, STAGE5_HUMAN)
                .minimum_mass_matrix_eigenvalue()
                > 1.0e-6
            )
            if evidence["promotion_supported"] and positive_definite:
                self.retained_beta = proposed.copy()
                version_index = len(self.publication_history)
                self.publication = HumanModelPublication(
                    beta=proposed.copy(),
                    version=f"{SHADOW_HUMAN_MODEL_VERSION_PREFIX}{version_index}",
                    timestamp_s=now_s,
                )
                self.publication_history.append(self.publication.to_dict())
                self.first_trustworthy_candidate_time_s = (
                    now_s
                    if self.first_trustworthy_candidate_time_s is None
                    else self.first_trustworthy_candidate_time_s
                )
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
            "challenger": (
                None
                if self.active_challenger is None
                else {
                    key: value
                    for key, value in self.active_challenger.items()
                    if key
                    in {
                        "challenger_index",
                        "fit_end_time_s",
                        "minimum_validation_ready_time_s",
                        "proposed_model_beta",
                        "status",
                        "information",
                        "bound_pressure",
                    }
                }
            ),
            "trust_state": trust_state,
            "model_version": self.publication.version,
            "model_timestamp_s": self.publication.timestamp_s,
            "measurement_count": len(self.raw_history),
            "rejected_measurement_count": self.rejected_measurements,
            "update_diagnostics": update_diagnostics,
            "prediction_diagnostics": (
                None
                if not self.attempts
                else self.attempts[-1].get("evidence_history", [])[-1]
                if self.attempts[-1].get("evidence_history")
                else self.attempts[-1].get("training_diagnostics")
            ),
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
            "schema": "stage5_shadow_human_identification_summary_v1",
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
    "HumanModelPublication",
    "SHADOW_HUMAN_MODEL_VERSION_PREFIX",
    "ShadowHumanIdentificationService",
    "Stage5HumanIDConfig",
    "Stage5HumanIDMeasurement",
]
