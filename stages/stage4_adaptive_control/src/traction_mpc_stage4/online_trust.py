"""Non-default online single incumbent--challenger trust adapter.

The validated geometry estimator and 11-base integral identifier are reused
unchanged.  This module owns only L1--L4 data routing, model promotion, and
diagnostics so the production estimator/controller remain untouched.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, soft_limit_torque

from .dynamics_failure_audit import bound_diagnostics, unconstrained_candidate
from .estimator_v2 import (
    AccumulatedCuffGeometryEstimator,
    BaseParameterHumanModel,
    DYNAMIC_BASE_PARAMETER_NAMES,
    PlanarCuffGeometry,
)
from .hierarchical_trust import (
    HierarchicalTrustPrototypeConfig,
    _apply_validated_estimator_step,
    _block_losses,
    _normalized_bound_violation,
    _uncertainty_diagnostics,
    _validation_blocks,
    measurement_validity,
    state_geometry_validity,
)
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from .measurement import ControllerMeasurement, MeasurementCase
from .statistical_trust import (
    PRIMARY_STATISTICAL_L4,
    StatisticalL4Config,
    _identification_status,
    paired_promotion_evidence,
)


class OnlineSingleChallengerTrustEstimator:
    """Estimator-compatible causal trust adapter for a preregistered A/B.

    ``apply_qualified_model=False`` keeps the control model at the population
    prior while running the same trust qualification process for pacing and
    diagnostics.  ``True`` promotes a qualified challenger to the incumbent.
    """

    use_state_ukf = False
    state_ukf = None

    def __init__(
        self,
        initial_measurement: ControllerMeasurement,
        initial_q_prior_rad: np.ndarray,
        *,
        measurement_case: MeasurementCase,
        apply_qualified_model: bool,
        statistical_config: StatisticalL4Config = PRIMARY_STATISTICAL_L4,
        hierarchy_config: HierarchicalTrustPrototypeConfig = (
            HierarchicalTrustPrototypeConfig()
        ),
        rom_human: HumanV2Parameters = HUMAN,
    ) -> None:
        self.measurement_case = measurement_case
        self.apply_qualified_model = bool(apply_qualified_model)
        self.statistical_config = statistical_config
        self.hierarchy_config = hierarchy_config
        self.rom_human = rom_human
        self.geometry_identifier = AccumulatedCuffGeometryEstimator(
            initial_measurement.attachment_position_m,
            initial_measurement.attachment_rotation_matrix,
            initial_q_prior_rad,
        )
        self.dynamic_identifier = AccumulatedIntegralBaseDynamicIdentifier()
        self.incumbent_beta = self.dynamic_identifier.population_prior.copy()
        self.raw_history: list[dict[str, Any]] = []
        self.geometry_diagnostics: list[dict[str, Any]] = []
        self.dynamic_diagnostics: list[dict[str, Any]] = []
        self.challengers: list[dict[str, Any]] = []
        self.qualifications: list[dict[str, Any]] = []
        self.control_promotions: list[dict[str, Any]] = []
        self.active_challenger: dict[str, Any] | None = None
        self.previous_arrival_time_s: float | None = None
        self.previous_ingested_sample_time_s: float | None = None
        self.stream_start_sample_time_s = float(initial_measurement.sample_time_s)
        self.l1_valid_count = 0
        self.l1_invalid_count = 0
        self.l2_valid_count = 0
        self.l2_invalid_count = 0
        self.last_state = self.geometry.estimate_state(
            initial_measurement.attachment_position_m,
            initial_measurement.attachment_rotation_matrix,
            initial_measurement.attachment_velocity_m_s,
            initial_measurement.attachment_angular_velocity_rad_s,
        )

    @property
    def geometry(self) -> PlanarCuffGeometry:
        return self.geometry_identifier.geometry

    @property
    def control_beta(self) -> np.ndarray:
        return self.incumbent_beta.copy()

    @property
    def model(self) -> BaseParameterHumanModel:
        return BaseParameterHumanModel(
            self.geometry, self.control_beta, self.rom_human
        )

    def _resolve_challenger(self, now_s: float) -> None:
        record = self.active_challenger
        if record is None:
            return
        if record["reference_incumbent_epoch"] != len(self.control_promotions):
            raise RuntimeError("incumbent changed during challenger validation")
        if now_s < record["minimum_validation_ready_time_s"] - 1e-12:
            return
        config = self.statistical_config
        window_s = self.dynamic_identifier.config.integration_window_s
        blocks = _validation_blocks(
            self.raw_history,
            fit_end_time_s=record["fit_end_time_s"],
            window_s=window_s,
            embargo_windows=self.hierarchy_config.validation_embargo_integral_windows,
            count=config.maximum_clean_blocks,
        )
        proposed = np.asarray(record["proposed_model_beta"], dtype=float)
        reference = np.asarray(record["reference_incumbent_beta"], dtype=float)
        for look_index, look_count in enumerate(config.scheduled_looks):
            if look_count in record["evaluated_look_block_counts"]:
                continue
            if len(blocks) < look_count:
                break
            selected = blocks[:look_count]
            evidence = paired_promotion_evidence(
                _block_losses(proposed, selected),
                _block_losses(self.dynamic_identifier.population_prior, selected),
                _block_losses(reference, selected),
                config=config,
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
                            "start_time_s": item["start_time_s"],
                            "end_time_s": item["end_time_s"],
                        }
                        for item in selected
                    ],
                }
            )
            record["evidence_history"].append(evidence)
            record["evaluated_look_block_counts"].append(look_count)
            physical = (
                BaseParameterHumanModel(
                    self.geometry, proposed, self.rom_human
                )
                .minimum_mass_matrix_eigenvalue()
                > 1e-6
            )
            if evidence["promotion_supported"] and physical:
                applied = self.apply_qualified_model
                if applied:
                    self.incumbent_beta = proposed.copy()
                    self.control_promotions.append(
                        {
                            "challenger_index": record["challenger_index"],
                            "promotion_time_s": float(now_s),
                            "incumbent_beta": self.incumbent_beta.tolist(),
                        }
                    )
                self.dynamic_identifier.last_valid = self.incumbent_beta.copy()
                self.dynamic_identifier.accepted_updates += 1
                if self.dynamic_identifier.trustworthy_time_s is None:
                    self.dynamic_identifier.trustworthy_time_s = float(now_s)
                record.update(
                    {
                        "status": (
                            "promoted_to_control_incumbent"
                            if applied
                            else "qualified_not_applied_prior_only"
                        ),
                        "decision_time_s": float(now_s),
                        "decision_block_count": look_count,
                        "validation_duration_s": float(
                            now_s - record["fit_end_time_s"]
                        ),
                        "qualified": True,
                        "applied_to_control": applied,
                        "positive_definite_proposed_model": True,
                        "valid_measurements_accumulated_during_validation": (
                            len(self.raw_history)
                            - record["training_valid_measurement_count"]
                        ),
                    }
                )
                self.qualifications.append(
                    {
                        "challenger_index": record["challenger_index"],
                        "qualification_time_s": float(now_s),
                        "applied_to_control": applied,
                    }
                )
                self.active_challenger = None
                return
            if look_count == config.maximum_clean_blocks:
                self.dynamic_identifier.rejected_updates += 1
                record.update(
                    {
                        "status": "rejected_no_statistical_support",
                        "decision_time_s": float(now_s),
                        "decision_block_count": look_count,
                        "validation_duration_s": float(
                            now_s - record["fit_end_time_s"]
                        ),
                        "qualified": False,
                        "applied_to_control": False,
                        "positive_definite_proposed_model": bool(physical),
                        "valid_measurements_accumulated_during_validation": (
                            len(self.raw_history)
                            - record["training_valid_measurement_count"]
                        ),
                    }
                )
                self.active_challenger = None
                return

    def _launch_challenger(self, now_s: float) -> dict[str, Any]:
        if self.active_challenger is not None:
            raise RuntimeError("competing challenger launch")
        identifier = self.dynamic_identifier
        identifier.last_valid = self.incumbent_beta.copy()
        before_accepted = identifier.accepted_updates
        before_rejected = identifier.rejected_updates
        before_trusted = identifier.trustworthy_time_s
        diagnostics = identifier.attempt_update(self.raw_history, self.geometry)
        identifier.last_valid = self.incumbent_beta.copy()
        identifier.accepted_updates = before_accepted
        identifier.rejected_updates = before_rejected
        identifier.trustworthy_time_s = before_trusted
        if not diagnostics.get("attempted", False):
            return diagnostics

        regressor, target, contaminated_windows = identifier._integral_blocks(
            self.raw_history, self.geometry
        )
        candidate = np.asarray(diagnostics["candidate"], dtype=float)
        unconstrained = unconstrained_candidate(identifier, regressor, target)
        active = bound_diagnostics(identifier, candidate, unconstrained)
        proposed = _apply_validated_estimator_step(
            identifier, self.incumbent_beta, candidate
        )
        window_s = identifier.config.integration_window_s
        record = {
            "challenger_index": len(self.challengers),
            "fit_end_time_s": float(now_s),
            "minimum_validation_ready_time_s": float(
                now_s
                + window_s
                * (
                    self.hierarchy_config.validation_embargo_integral_windows
                    + self.statistical_config.minimum_clean_blocks
                )
            ),
            "reference_incumbent_epoch": len(self.control_promotions),
            "reference_incumbent_beta": self.incumbent_beta.tolist(),
            "candidate_beta": candidate.tolist(),
            "proposed_model_beta": proposed.tolist(),
            "unconstrained_beta": unconstrained.tolist(),
            "training_valid_measurement_count": len(self.raw_history),
            "status": "pending_statistical_evidence",
            "qualified": False,
            "applied_to_control": False,
            "evidence_history": [],
            "evaluated_look_block_counts": [],
            "parameter_identification_status": _identification_status(
                diagnostics, active, identifier
            ),
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
                "integral_block_count": int(diagnostics["integral_block_count"]),
                "contaminated_integral_windows": int(contaminated_windows),
                "active_bound_count": int(
                    sum(item["constrained_hit"] for item in active)
                ),
                "active_or_pressured_bounds": active,
                "unconstrained_normalized_bound_violation": (
                    _normalized_bound_violation(identifier, unconstrained)
                ),
                "uncertainty": _uncertainty_diagnostics(
                    identifier, regressor, target, candidate
                ),
            },
        }
        self.challengers.append(record)
        self.active_challenger = record
        return diagnostics

    def observe_measurement(
        self, measurement: ControllerMeasurement
    ) -> tuple[np.ndarray, dict[str, Any]]:
        values = (
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            measurement.attachment_velocity_m_s,
            measurement.attachment_angular_velocity_rad_s,
            measurement.cuff_force_vector_n,
            measurement.cuff_moment_vector_nm,
        )
        l1 = measurement_validity(
            arrival_time_s=measurement.arrival_time_s,
            sample_time_s=measurement.sample_time_s,
            previous_arrival_time_s=self.previous_arrival_time_s,
            previous_ingested_sample_time_s=self.previous_ingested_sample_time_s,
            new_sample=measurement.new_sample,
            case=self.measurement_case,
            stream_start_sample_time_s=self.stream_start_sample_time_s,
            values=values,
            saturated=None,
            config=self.hierarchy_config,
        )
        self.previous_arrival_time_s = float(measurement.arrival_time_s)
        measured_state = self.geometry.estimate_state(*values[:4])
        if not l1["valid"]:
            self.l1_invalid_count += 1
            self._resolve_challenger(float(measurement.arrival_time_s))
            return measured_state, {
                "geometry": self.geometry_identifier._empty_diagnostics(
                    "l1_measurement_invalid"
                ),
                "dynamics": self.dynamic_identifier._empty_diagnostics(
                    "l1_measurement_invalid"
                ),
                "l1": l1,
                "l2": {"valid": False, "reasons": ["l1_measurement_invalid"]},
            }

        self.l1_valid_count += 1
        self.previous_ingested_sample_time_s = float(measurement.sample_time_s)
        contaminated = bool(
            np.linalg.norm(
                soft_limit_torque(
                    measured_state[:2], measured_state[2:], self.rom_human
                )
            )
            > 1e-8
        )
        geometry_diag = self.geometry_identifier.add_pose(
            measurement.sample_time_s,
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            contaminated=contaminated,
        )
        if geometry_diag.get("attempted", False):
            self.geometry_diagnostics.append(
                dict(geometry_diag, time_s=float(measurement.sample_time_s))
            )
        state = self.geometry.estimate_state(*values[:4])
        l2 = state_geometry_validity(
            geometry=self.geometry,
            state=state,
            measured_position_m=measurement.attachment_position_m,
            measured_rotation=measurement.attachment_rotation_matrix,
            measured_linear_velocity_m_s=measurement.attachment_velocity_m_s,
            measured_angular_velocity_rad_s=(
                measurement.attachment_angular_velocity_rad_s
            ),
            config=self.hierarchy_config,
        )
        if not l2["valid"]:
            self.l2_invalid_count += 1
            self._resolve_challenger(float(measurement.sample_time_s))
            return state, {
                "geometry": geometry_diag,
                "dynamics": self.dynamic_identifier._empty_diagnostics(
                    "l2_state_geometry_invalid"
                ),
                "l1": l1,
                "l2": l2,
            }

        self.l2_valid_count += 1
        self.last_state = state.copy()
        generalized_input = self.geometry.generalized_input_from_wrench(
            state[:2],
            measurement.cuff_force_vector_n,
            measurement.cuff_moment_vector_nm,
        )
        self.raw_history.append(
            {
                "time_s": float(measurement.sample_time_s),
                "state": state.copy(),
                "force_world_n": measurement.cuff_force_vector_n.copy(),
                "moment_world_nm": measurement.cuff_moment_vector_nm.copy(),
                "generalized_input_nm": generalized_input.copy(),
                "contaminated": contaminated,
                "source_index": len(self.raw_history),
            }
        )
        self._resolve_challenger(float(measurement.sample_time_s))
        if (
            self.geometry_identifier.trustworthy_time_s is not None
            and self.active_challenger is None
        ):
            dynamic_diag = self._launch_challenger(float(measurement.sample_time_s))
        else:
            dynamic_diag = self.dynamic_identifier._empty_diagnostics(
                "challenger_validation_active"
                if self.active_challenger is not None
                else "geometry_not_trustworthy"
            )
        if dynamic_diag.get("attempted", False):
            self.dynamic_diagnostics.append(
                dict(dynamic_diag, time_s=float(measurement.sample_time_s))
            )
        return self.last_state.copy(), {
            "geometry": geometry_diag,
            "dynamics": dynamic_diag,
            "l1": l1,
            "l2": l2,
        }

    def trust_summary(self) -> dict[str, Any]:
        pending = int(self.active_challenger is not None)
        rejected = sum(
            item["status"] == "rejected_no_statistical_support"
            for item in self.challengers
        )
        return {
            "production_default": False,
            "apply_qualified_model_to_control": self.apply_qualified_model,
            "lifecycle": "single_incumbent_single_challenger",
            "maximum_concurrent_challengers": 1 if self.challengers else 0,
            "superseded_count": 0,
            "race_state_count": 0,
            "statistical_config": {
                **asdict(self.statistical_config),
                "scheduled_looks": list(self.statistical_config.scheduled_looks),
                "alpha_spending": "alpha_j=0.05/[j(j+1)]",
            },
            "L1": {
                "valid": self.l1_valid_count,
                "invalid": self.l1_invalid_count,
            },
            "L2": {
                "valid": self.l2_valid_count,
                "invalid": self.l2_invalid_count,
            },
            "counts": {
                "challengers": len(self.challengers),
                "qualified": len(self.qualifications),
                "control_promotions": len(self.control_promotions),
                "rejected": int(rejected),
                "pending": pending,
            },
            "challengers": self.challengers,
            "qualifications": self.qualifications,
            "control_promotions": self.control_promotions,
            "oracle_used_online": False,
        }
