"""Declarative patient/model-mismatch cases for the Stage-4 preregistration.

This module constructs Human-V2 plants and records their exact 11-base
representation.  It does not run a rollout or alter the frozen controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, mass_matrix

from .estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES, nominal_base_parameters
from .human_model import ScaledHumanV2
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier


CASE_SCHEMA_VERSION = "stage4_patient_mismatch_cases_v1"
CASE_RECORD_SCHEMA_VERSION = "stage4_patient_mismatch_case_record_v1"
RESULT_SCHEMA_VERSION = "stage4_patient_mismatch_paired_result_v1"

REGISTERED_ARMS = {
    "prior_only": False,
    "trusted_adaptive": True,
}

# This is a preregistered fingerprint of the existing Stage-4 A/B contract,
# not a second set of controller defaults.
FROZEN_SHARED_AB_CONTRACT: dict[str, Any] = {
    "reference": "continuous_high_flexion_23s",
    "reference_duration_s": 23.0,
    "wall_time_limit_s": 32.0,
    "sensor_case": "noise_bias_drift_200hz",
    "measurement_seed": 44104,
    "mpc_seed": 20260824,
    "mpc_implementation": "batched",
    "mpc_horizon_steps": 15,
    "mpc_candidate_count": 32,
    "mpc_iteration_count": 2,
    "mpc_elite_count": 6,
    "mpc_interaction_weights": [0.0, 0.0, 0.0],
    "dynamic_identifier": "causal_accumulated_integral_11_base_parameter_regression",
    "trust_lifecycle": "single_fixed_incumbent_at_most_one_challenger",
    "statistical_rule": "primary_single_challenger_hac_lag2",
    "confidence_pacing": "existing_lowpass_hysteretic_model_confidence",
    "allocator": "registered_1_to_1_cuff_aware",
    "plant_integration": "existing_mujoco_human_v2_rigid_cuff",
    "new_active_excitation": False,
    "ukf_or_kalman": False,
    "hybrid_optimizer": False,
    "tracking_corridor_or_tube": False,
}

CASE_RESULT_REQUIRED_FIELDS = {
    "top_level": (
        "schema_version",
        "case_record",
        "shared_ab_contract",
        "ab_isolation",
        "arms",
        "comparison",
    ),
    "arm": (
        "tracking_rmse_deg",
        "maximum_tracking_error_deg",
        "reference_progress_fraction",
        "termination_reason",
        "safety_events",
        "generalized_torque_prediction_rmse_nm",
        "first_challenger_qualification_time_s",
        "first_promotion_time_s",
        "promotion_timeline",
        "trajectory_remaining_after_first_promotion_s",
        "candidate_status",
        "active_bound_pressure",
        "trusted_adaptation_entered_control",
        "cuff_force_peak_n",
        "cuff_force_rms_n",
        "cuff_moment_peak_nm",
        "cuff_moment_rms_nm",
        "cylindrical_surface_proxy_peak_n",
        "cylindrical_surface_proxy_rms_n",
        "prior_to_true_beta_span_l2",
        "incumbent_to_true_beta_span_l2",
        "challenger_to_true_beta_span_l2",
    ),
}


@dataclass(frozen=True)
class PatientCaseSpec:
    case_id: str
    severity: str
    mechanism: str
    source: str
    height_scale: float
    body_mass_scale: float
    thigh_com_scale: float
    shank_com_scale: float
    passive_stiffness_scale: tuple[float, float]
    passive_damping_scale: tuple[float, float]
    rest_offset_deg: tuple[float, float]
    sleeve_center_scale: float
    expected_dominant_torque_effect: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PatientCaseSpec":
        payload = dict(raw)
        for key in (
            "passive_stiffness_scale",
            "passive_damping_scale",
            "rest_offset_deg",
        ):
            values = tuple(float(value) for value in payload[key])
            if len(values) != 2:
                raise ValueError(f"{key} must contain exactly two joint values")
            payload[key] = values
        return cls(**payload)

    def build_human(self, nominal: HumanV2Parameters = HUMAN) -> ScaledHumanV2:
        return ScaledHumanV2(
            height_m=nominal.height_m * self.height_scale,
            body_mass_kg=nominal.body_mass_kg * self.body_mass_scale,
            gravity_m_s2=nominal.gravity_m_s2,
            q_rest_rad=tuple(
                np.asarray(nominal.q_rest_rad, dtype=float)
                + np.radians(self.rest_offset_deg)
            ),
            passive_stiffness_nm_rad=tuple(
                np.asarray(nominal.passive_stiffness_nm_rad, dtype=float)
                * np.asarray(self.passive_stiffness_scale, dtype=float)
            ),
            passive_damping_nms_rad=tuple(
                np.asarray(nominal.passive_damping_nms_rad, dtype=float)
                * np.asarray(self.passive_damping_scale, dtype=float)
            ),
            q_min_rad=nominal.q_min_rad,
            q_max_rad=nominal.q_max_rad,
            soft_limit_margin_rad=nominal.soft_limit_margin_rad,
            soft_limit_numerical_tolerance_rad=(
                nominal.soft_limit_numerical_tolerance_rad
            ),
            soft_limit_boundary_torque_nm=nominal.soft_limit_boundary_torque_nm,
            soft_limit_damping_nms_rad=nominal.soft_limit_damping_nms_rad,
            thigh_com_scale=self.thigh_com_scale,
            shank_com_scale=self.shank_com_scale,
            sleeve_center_scale=self.sleeve_center_scale,
        )


def load_patient_case_specs(path: Path) -> tuple[PatientCaseSpec, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != CASE_SCHEMA_VERSION:
        raise ValueError("unsupported patient-case schema version")
    if payload.get("range_basis") != (
        "engineering_robustness_ranges_not_clinical_population_ranges"
    ):
        raise ValueError("patient-case ranges must be explicitly non-clinical")
    specs = tuple(PatientCaseSpec.from_dict(item) for item in payload["cases"])
    case_ids = [item.case_id for item in specs]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("patient case_id values must be unique")
    return specs


def estimator_beta_bounds() -> tuple[np.ndarray, np.ndarray]:
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    return identifier.lower.copy(), identifier.upper.copy()


def _raw_human_parameters(human: HumanV2Parameters) -> dict[str, Any]:
    return {
        "height_m": float(human.height_m),
        "body_mass_kg": float(human.body_mass_kg),
        "gravity_m_s2": float(human.gravity_m_s2),
        "thigh_length_m": float(human.thigh_length_m),
        "shank_length_m": float(human.shank_length_m),
        "thigh_mass_kg": float(human.thigh_mass_kg),
        "shank_mass_kg": float(human.shank_mass_kg),
        "thigh_com_m": float(human.thigh_com_m),
        "shank_com_m": float(human.shank_com_m),
        "thigh_inertia_kg_m2": float(human.thigh_inertia_kg_m2),
        "shank_inertia_kg_m2": float(human.shank_inertia_kg_m2),
        "sleeve_center_m": float(human.sleeve_center_m),
        "q_rest_rad": list(map(float, human.q_rest_rad)),
        "passive_stiffness_nm_rad": list(
            map(float, human.passive_stiffness_nm_rad)
        ),
        "passive_damping_nms_rad": list(
            map(float, human.passive_damping_nms_rad)
        ),
        "q_min_rad": list(map(float, human.q_min_rad)),
        "q_max_rad": list(map(float, human.q_max_rad)),
        "soft_limit_margin_rad": float(human.soft_limit_margin_rad),
        "soft_limit_boundary_torque_nm": float(
            human.soft_limit_boundary_torque_nm
        ),
        "soft_limit_damping_nms_rad": float(human.soft_limit_damping_nms_rad),
    }


def physical_validity_checks(human: HumanV2Parameters) -> dict[str, bool]:
    q2_grid = np.linspace(human.q_min_rad[1], human.q_max_rad[1], 101)
    positive_definite = all(
        np.all(np.linalg.eigvalsh(mass_matrix(np.array([0.0, q2]), human)) > 0.0)
        for q2 in q2_grid
    )
    return {
        "finite_raw_parameters": all(
            np.all(np.isfinite(np.asarray(value, dtype=float)))
            for value in _raw_human_parameters(human).values()
        ),
        "positive_height_and_mass": human.height_m > 0.0
        and human.body_mass_kg > 0.0,
        "positive_segment_lengths_and_masses": min(
            human.thigh_length_m,
            human.shank_length_m,
            human.thigh_mass_kg,
            human.shank_mass_kg,
        )
        > 0.0,
        "com_inside_segments": 0.0 < human.thigh_com_m < human.thigh_length_m
        and 0.0 < human.shank_com_m < human.shank_length_m,
        "cuff_center_on_shank": 0.0 < human.sleeve_center_m <= human.shank_length_m,
        "nonnegative_passive_coefficients": bool(
            min(
                *human.passive_stiffness_nm_rad,
                *human.passive_damping_nms_rad,
            )
            >= 0.0
        ),
        "rest_angles_inside_rom": bool(
            np.all(np.asarray(human.q_rest_rad) >= np.asarray(human.q_min_rad))
            and np.all(np.asarray(human.q_rest_rad) <= np.asarray(human.q_max_rad))
        ),
        "positive_definite_mass_matrix_over_rom": positive_definite,
        "soft_limit_definition_unchanged": (
            human.q_min_rad == HUMAN.q_min_rad
            and human.q_max_rad == HUMAN.q_max_rad
            and human.soft_limit_margin_rad == HUMAN.soft_limit_margin_rad
            and human.soft_limit_boundary_torque_nm
            == HUMAN.soft_limit_boundary_torque_nm
            and human.soft_limit_damping_nms_rad
            == HUMAN.soft_limit_damping_nms_rad
        ),
    }


def patient_case_record(spec: PatientCaseSpec) -> dict[str, Any]:
    human = spec.build_human()
    beta = nominal_base_parameters(human)
    prior = nominal_base_parameters(HUMAN)
    lower, upper = estimator_beta_bounds()
    span = upper - lower
    normalized = (beta - prior) / span
    geometry_fields = {
        "thigh_length_m": not math.isclose(
            human.thigh_length_m, HUMAN.thigh_length_m
        ),
        "shank_length_m": not math.isclose(
            human.shank_length_m, HUMAN.shank_length_m
        ),
        "sleeve_center_m": not math.isclose(
            human.sleeve_center_m, HUMAN.sleeve_center_m
        ),
    }
    checks = physical_validity_checks(human)
    inside_box = bool(np.all(beta >= lower) and np.all(beta <= upper))
    geometry_changes = any(geometry_fields.values())
    return {
        "schema_version": CASE_RECORD_SCHEMA_VERSION,
        "case_id": spec.case_id,
        "severity": spec.severity,
        "mechanism": spec.mechanism,
        "source": spec.source,
        "engineering_range_not_clinical": True,
        "variation_spec": asdict(spec),
        "raw_human_parameters": _raw_human_parameters(human),
        "base_parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "beta_11": beta.tolist(),
        "normalized_difference_from_prior": {
            "definition": "(beta_case-beta_population_prior)/(estimator_upper-estimator_lower)",
            "per_parameter": normalized.tolist(),
            "span_l2": float(np.linalg.norm(normalized)),
            "span_linf": float(np.max(np.abs(normalized))),
        },
        "physical_validity_checks": checks,
        "physically_valid": all(checks.values()),
        "geometry": {
            "changes": geometry_changes,
            "changed_fields": [key for key, changed in geometry_fields.items() if changed],
            "requires_separate_geometry_estimator": geometry_changes,
        },
        "expected_dominant_torque_effect": spec.expected_dominant_torque_effect,
        "representability": {
            "base_dynamics": "exact_11_base_when_soft_limit_torque_is_inactive",
            "geometry": (
                "current_separate_planar_geometry_estimator_required"
                if geometry_changes
                else "population_geometry_exact"
            ),
            "inside_current_estimator_box": inside_box,
            "inside_current_model_family": all(checks.values()),
            "soft_limit_caveat": (
                "11-base excludes nonlinear soft-limit torque; every preregistered "
                "case keeps the frozen soft-limit definition"
            ),
        },
    }


def paired_arm_contracts(case_id: str) -> dict[str, dict[str, Any]]:
    return {
        arm: {
            "case_id": case_id,
            "shared_contract": dict(FROZEN_SHARED_AB_CONTRACT),
            "apply_statistically_qualified_dynamics_model_to_control": apply_model,
        }
        for arm, apply_model in REGISTERED_ARMS.items()
    }
