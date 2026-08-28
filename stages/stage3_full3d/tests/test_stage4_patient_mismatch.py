from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import build_coupled_model_xml
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.confidence_execution import ConfidenceAwareExecutionConfig
from traction_mpc_stage4.cuff_allocator import REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG
from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row, nominal_base_parameters
from traction_mpc_stage4.human_model import (
    inverse_dynamics,
    registered_cold_start_perturbed_human,
    registered_moderate_human,
)
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage4.patient_mismatch import (
    CASE_RESULT_REQUIRED_FIELDS,
    FROZEN_SHARED_AB_CONTRACT,
    RESULT_SCHEMA_VERSION,
    load_patient_case_specs,
    paired_arm_contracts,
    patient_case_record,
)
from traction_mpc_stage4.statistical_trust import PRIMARY_STATISTICAL_L4


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_patient_mismatch_cases.json"
)


def _specs():
    return load_patient_case_specs(CONFIG_PATH)


def test_patient_case_construction_is_deterministic_and_config_is_stable() -> None:
    first = [patient_case_record(spec) for spec in _specs()]
    second = [patient_case_record(spec) for spec in _specs()]
    assert first == second
    json.dumps(first)
    assert len(first) == 13
    assert {item["case_id"] for item in first} == {
        "nominal_reference",
        "mass_mild_minus_05pct",
        "mass_mild_plus_05pct",
        "stiffness_moderate_minus_20pct",
        "stiffness_moderate_plus_20pct",
        "damping_moderate_minus_30pct",
        "damping_moderate_plus_30pct",
        "rest_equilibrium_moderate_minus_03deg",
        "rest_equilibrium_moderate_plus_03deg",
        "registered_stage2_mild_anchor",
        "registered_moderate_anchor",
        "registered_formal_perturbed_anchor",
        "registered_stage2_adverse_anchor",
    }


def test_raw_parameter_to_11_base_mapping_matches_inverse_dynamics() -> None:
    states = (
        (np.radians([20.0, 30.0]), np.array([0.10, -0.05]), np.array([0.20, -0.10])),
        (np.radians([42.0, 58.0]), np.array([0.21, -0.17]), np.array([0.34, -0.28])),
        (np.radians([65.0, 85.0]), np.array([-0.12, 0.19]), np.array([-0.25, 0.31])),
    )
    for spec in _specs():
        human = spec.build_human()
        beta = nominal_base_parameters(human)
        for q, dq, qdd in states:
            np.testing.assert_allclose(
                dynamic_regressor_row(q, dq, qdd) @ beta,
                inverse_dynamics(q, dq, qdd, human),
                rtol=1e-12,
                atol=1e-12,
            )


def test_all_preregistered_cases_are_physically_valid_and_inside_estimator_box() -> None:
    for spec in _specs():
        record = patient_case_record(spec)
        assert record["physically_valid"], (spec.case_id, record)
        assert record["representability"]["inside_current_estimator_box"], (
            spec.case_id,
            record["beta_11"],
        )
        assert record["representability"]["inside_current_model_family"]


def test_all_preregistered_humans_compile_as_mujoco_plants() -> None:
    for spec in _specs():
        model = mujoco.MjModel.from_xml_string(build_coupled_model_xml(spec.build_human()))
        assert model.nq > 0
        assert model.nv > 0


def test_existing_registered_anchors_are_copied_exactly() -> None:
    by_id = {spec.case_id: spec for spec in _specs()}
    expected_moderate, _ = registered_moderate_human()
    expected_formal, _ = registered_cold_start_perturbed_human()
    for case_id, expected in (
        ("registered_moderate_anchor", expected_moderate),
        ("registered_formal_perturbed_anchor", expected_formal),
    ):
        actual = by_id[case_id].build_human()
        np.testing.assert_allclose(
            nominal_base_parameters(actual), nominal_base_parameters(expected)
        )
        assert asdict(actual) == asdict(expected)


def test_stage2_mild_and_adverse_anchor_scales_are_copied_exactly() -> None:
    by_id = {spec.case_id: spec for spec in _specs()}
    mild = by_id["registered_stage2_mild_anchor"]
    adverse = by_id["registered_stage2_adverse_anchor"]
    assert (
        mild.body_mass_scale,
        mild.thigh_com_scale,
        mild.shank_com_scale,
        mild.passive_stiffness_scale,
        mild.rest_offset_deg,
        mild.sleeve_center_scale,
    ) == (1.05, 1.0, 1.0, (1.0, 1.0), (-2.0, -2.0), 1.0)
    assert (
        adverse.body_mass_scale,
        adverse.thigh_com_scale,
        adverse.shank_com_scale,
        adverse.passive_stiffness_scale,
        adverse.rest_offset_deg,
        adverse.sleeve_center_scale,
    ) == (1.10, 1.10, 0.90, (1.20, 1.20), (-2.0, -2.0), 1.05)


def test_ab_arms_differ_only_by_registered_control_application_flag() -> None:
    arms = paired_arm_contracts("mass_mild_plus_05pct")
    assert set(arms) == {"prior_only", "trusted_adaptive"}
    prior = dict(arms["prior_only"])
    adaptive = dict(arms["trusted_adaptive"])
    flag = "apply_statistically_qualified_dynamics_model_to_control"
    assert prior.pop(flag) is False
    assert adaptive.pop(flag) is True
    assert prior == adaptive


def test_frozen_contract_matches_stage4_runtime_defaults() -> None:
    mpc = HumanMPCConfig()
    assert FROZEN_SHARED_AB_CONTRACT["mpc_seed"] == mpc.random_seed
    assert FROZEN_SHARED_AB_CONTRACT["mpc_horizon_steps"] == mpc.horizon_steps
    assert FROZEN_SHARED_AB_CONTRACT["mpc_candidate_count"] == mpc.candidate_count
    assert FROZEN_SHARED_AB_CONTRACT["mpc_iteration_count"] == mpc.cem_iterations
    assert FROZEN_SHARED_AB_CONTRACT["mpc_elite_count"] == mpc.elite_count
    assert FROZEN_SHARED_AB_CONTRACT["mpc_interaction_weights"] == [
        mpc.resultant_force_weight,
        mpc.cylindrical_surface_effort_weight,
        mpc.wrench_slew_weight,
    ]
    assert PRIMARY_STATISTICAL_L4.name == FROZEN_SHARED_AB_CONTRACT["statistical_rule"]
    assert REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG.resultant_force_weight == 1.0
    assert REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG.cylindrical_surface_effort_weight == 1.0
    assert ConfidenceAwareExecutionConfig().nominal_speed_scale == 1.0
    assert nominal_base_parameters(HUMAN).shape == (11,)


def test_preregistered_result_schema_is_stable_and_json_serializable() -> None:
    assert RESULT_SCHEMA_VERSION == "stage4_patient_mismatch_paired_result_v1"
    assert CASE_RESULT_REQUIRED_FIELDS["top_level"] == (
        "schema_version",
        "case_record",
        "shared_ab_contract",
        "ab_isolation",
        "arms",
        "comparison",
    )
    assert "tracking_rmse_deg" in CASE_RESULT_REQUIRED_FIELDS["arm"]
    assert "generalized_torque_prediction_rmse_nm" in CASE_RESULT_REQUIRED_FIELDS["arm"]
    assert "trusted_adaptation_entered_control" in CASE_RESULT_REQUIRED_FIELDS["arm"]
    json.dumps(CASE_RESULT_REQUIRED_FIELDS)
