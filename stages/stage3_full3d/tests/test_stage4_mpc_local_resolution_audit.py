from __future__ import annotations

from copy import deepcopy

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.mpc import INTERACTION_AWARE_MPC_CONFIG, HumanSpaceMPC
from traction_mpc_stage4.mpc_local_resolution_audit import (
    evaluate_local_sequence,
    structured_perturbations,
    summarize_local_landscape,
)
from traction_mpc_stage4.reference import teaching_reference


def test_structured_perturbations_are_smooth_local_and_include_zero() -> None:
    perturbations = structured_perturbations(15, (1.0, 0.5))
    assert len(perturbations) > 400
    zero = [item for item in perturbations if item["method"] == "registered_sequence"]
    assert len(zero) == 1
    np.testing.assert_allclose(zero[0]["delta_u_nm"], 0.0)
    for item in perturbations:
        delta = np.asarray(item["delta_u_nm"])
        assert np.max(np.abs(delta[:, 0])) <= 1.0 + 1e-12
        assert np.max(np.abs(delta[:, 1])) <= 0.5 + 1e-12


def test_local_evaluation_matches_registered_objective_contract() -> None:
    controller = HumanSpaceMPC(INTERACTION_AWARE_MPC_CONFIG)
    time_s = 3.0
    reference = teaching_reference(time_s)
    state = np.concatenate([reference.q_rad, reference.dq_rad_s])
    q_ref, dq_ref, ddq_ref = controller._reference_arrays(
        time_s, teaching_reference
    )
    sequence = controller._seed_sequence(state, q_ref, dq_ref, ddq_ref, HUMAN)
    result = evaluate_local_sequence(
        controller,
        state=state,
        sequence=sequence,
        previous_action=np.zeros(2),
        q_ref=q_ref,
        dq_ref=dq_ref,
        human=HUMAN,
    )
    assert result["feasible"]
    assert result["interaction_cost"] > 0.0
    np.testing.assert_allclose(
        result["total_interaction_aware_cost"],
        result["base_task_cost"] + result["interaction_cost"],
    )
    assert result["maximum_allocation_equality_residual_nm"] < 1e-10


def test_landscape_neighborhoods_are_monotone_reporting_slices() -> None:
    baseline = {
        "method": "registered_sequence",
        "coefficients": {},
        "maximum_abs_delta_per_joint_nm": [0.0, 0.0],
        "rms_delta_nm": 0.0,
        "feasible": True,
        "minimum_constraint_margin": 1.0,
        "tracking_cost": 10.0,
        "base_task_cost": 10.0,
        "interaction_cost": 5.0,
        "total_interaction_aware_cost": 15.0,
        "resultant_force_n": {"peak": 100.0, "rms": 90.0},
        "abs_sagittal_moment_nm": {"peak": 12.0, "rms": 10.0},
        "cylindrical_surface_proxy_n": {"peak": 120.0, "rms": 110.0},
        "maximum_allocation_equality_residual_nm": 0.0,
    }
    nearby = deepcopy(baseline)
    nearby.update(
        {
            "method": "single_temporal_direction",
            "coefficients": {"hip_constant": -0.1},
            "maximum_abs_delta_per_joint_nm": [0.1, 0.0],
            "rms_delta_nm": 0.05,
            "tracking_cost": 10.04,
            "base_task_cost": 10.04,
            "interaction_cost": 4.5,
            "total_interaction_aware_cost": 14.54,
            "resultant_force_n": {"peak": 95.0, "rms": 85.0},
            "abs_sagittal_moment_nm": {"peak": 11.5, "rms": 9.5},
            "cylindrical_surface_proxy_n": {"peak": 115.0, "rms": 105.0},
        }
    )
    summary = summarize_local_landscape([baseline, nearby])
    assert summary["neighborhoods"]["0.10_percent"]["candidate_count"] == 1
    assert summary["neighborhoods"]["0.50_percent"]["candidate_count"] == 2
    best = summary["neighborhoods"]["0.50_percent"][
        "minimum_interaction_cost_candidate"
    ]
    np.testing.assert_allclose(
        best["relative_change_vs_registered_sequence"]["interaction_cost"], -0.1
    )
