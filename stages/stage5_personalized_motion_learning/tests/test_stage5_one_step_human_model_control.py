import inspect

import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.minimal_adaptation import effective_base_parameters
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    REDUCED_HUMAN_MODEL_VERSION_PREFIX,
    ReducedHumanModelPublication,
)
from traction_mpc_stage5.human_model_update import (
    FIXED_ONE_STEP_GAMMA,
    OneStepHumanModelArm,
    OneStepHumanModelControlAuthority,
    fixed_one_step_pacing_status,
)


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def _payload(time_s: float) -> dict:
    return {
        "episode_time_s": time_s,
        "estimated_human_state_rad_rad_s": np.zeros(4),
        "measured_human_cuff_force_world_n": np.zeros(3),
        "measured_human_cuff_moment_world_nm": np.zeros(3),
        "measured_generalized_human_input_nm": np.zeros(2),
        "task_phase": "OUTBOUND",
        "interface_model_version": "stage5_controller_nominal_kelvin_voigt_v1",
        "current_control_model_version": FIXED_HUMAN_MODEL_VERSION,
    }


def _install_publication_on_call(
    authority: OneStepHumanModelControlAuthority, publication_calls: set[int]
) -> None:
    service = authority.service
    call_count = 0

    def observe(measurement):
        nonlocal call_count
        call_count += 1
        if call_count not in publication_calls:
            return {}
        candidate = np.array([1.0005843909854664, 1.010424686528112, 1.1934798034676337])
        proposed = service.identifier.bounded_smoothed_step(
            service.retained_scales, candidate
        )
        index = len(service.attempts)
        timestamp = float(measurement.sample_time_s)
        attempt = {
            "challenger_index": index,
            "fit_end_time_s": timestamp - 1.8,
            "candidate_scales": candidate.tolist(),
            "proposed_model_scales": proposed.tolist(),
            "status": "published_to_shadow_incumbent",
            "qualified": True,
            "decision_time_s": timestamp,
            "decision_block_count": 8,
            "evidence_history": [
                {
                    "validation_windows": [
                        [timestamp - 1.6 + 0.2 * i, timestamp - 1.4 + 0.2 * i]
                        for i in range(8)
                    ]
                }
            ],
        }
        service.attempts.append(attempt)
        service.retained_scales = proposed.copy()
        beta = effective_base_parameters(
            proposed, nominal_base_parameters(STAGE5_HUMAN)
        )
        service.publication = ReducedHumanModelPublication(
            scales=proposed.copy(),
            beta=beta,
            version=f"{REDUCED_HUMAN_MODEL_VERSION_PREFIX}{index + 1}",
            timestamp_s=timestamp,
        )
        service.publication_history.append(service.publication.to_dict())
        return {}

    service.observe = observe


def test_one_step_transition_occurs_at_most_once() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {2, 3})
    assert not authority.observe(_payload(0.5))["apply_update"]
    assert authority.observe(_payload(2.0))["apply_update"]
    assert not authority.observe(_payload(4.0))["apply_update"]
    assert authority.application_count == 1


def test_fixed_arm_never_changes_current_human_model() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.FIXED,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {1})
    result = authority.observe(_payload(2.0))
    assert not result["apply_update"]
    assert authority.application_count == 0
    assert authority.control_model_version == FIXED_HUMAN_MODEL_VERSION


def test_adaptive_arm_changes_only_after_causal_qualification() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {2})
    before = authority.observe(_payload(0.5))
    after = authority.observe(_payload(2.0))
    assert not before["apply_update"]
    assert after["apply_update"]
    assert authority.transition_time_s == 2.0


def test_control_transition_respects_exact_frozen_bounded_rule() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {1})
    authority.observe(_payload(2.0))
    assert np.allclose(
        authority.applied_transition.successor_scales,
        [1.0000584390985465, 1.0010424686528112, 1.0193479803467633],
    )
    assert authority.applied_transition.smoothing_alpha == 0.1
    assert authority.applied_transition.maximum_step_fraction_of_span == 0.03


def test_successor_model_version_is_explicit() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {1})
    result = authority.observe(_payload(2.0))
    assert result["model_version"] == "stage5_control_human_scale3_v1"
    assert result["model_version"] != FIXED_HUMAN_MODEL_VERSION


def test_predecessor_remains_explicit_for_rollback_shadow_comparison() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {1})
    authority.observe(_payload(2.0))
    transition = authority.applied_transition
    assert transition.predecessor_version == FIXED_HUMAN_MODEL_VERSION
    assert transition.predecessor_scales == (1.0, 1.0, 1.0)


def test_post_update_evidence_uses_only_strictly_later_blocks() -> None:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), OneStepHumanModelArm.ONE_STEP,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
    )
    _install_publication_on_call(authority, {1})
    authority.observe(_payload(2.0))
    for index, timestamp in enumerate(np.arange(2.005, 2.506, 0.005)):
        state = np.array(
            [0.1 * np.sin(timestamp), 0.2 * np.sin(0.7 * timestamp),
             0.1 * np.cos(timestamp), 0.14 * np.cos(0.7 * timestamp)]
        )
        authority.service.raw_history.append(
            {
                "time_s": float(timestamp),
                "state": state,
                "generalized_input_nm": np.array([0.5, -0.25]),
                "contaminated": False,
                "task_phase": "OUTBOUND",
                "source_index": index,
                "episode_index": 0,
            }
        )
    evidence = authority.post_update_prediction_evidence()
    assert evidence["blocks"]
    assert all(item["start_time_s"] > 2.0 for item in evidence["blocks"])
    assert not any(
        item["overlaps_training_or_qualification"] for item in evidence["blocks"]
    )


def test_gamma_is_exactly_half_for_both_arms() -> None:
    assert FIXED_ONE_STEP_GAMMA == 0.5
    for arm in OneStepHumanModelArm:
        assert fixed_one_step_pacing_status({"arm": arm.value}) == {
            "gamma": 0.5,
            "gamma_rate_per_s": 0.0,
        }


def test_control_update_api_keeps_acceleration_monitor_separate() -> None:
    source = inspect.getsource(run_goal_mpc_smoke)
    assert "acceleration_monitor.update(\n                task_observation, interface_state, estimation_model" in source
    assert '"acceleration_monitor_model_version": FIXED_HUMAN_MODEL_VERSION' in source


def test_truth_fields_are_not_part_of_update_measurement_or_authority() -> None:
    payload = _payload(0.5)
    payload["evaluation_only_truth_scales"] = np.array([99.0, 99.0, 99.0])
    measurement = OneStepHumanModelControlAuthority._measurement(payload)
    assert not hasattr(measurement, "evaluation_only_truth_scales")
    assert "truth" not in inspect.getsource(
        OneStepHumanModelControlAuthority._measurement
    ).lower()


def test_transition_does_not_change_registered_monitor_or_limits_arguments() -> None:
    signature = inspect.signature(run_goal_mpc_smoke)
    assert "control_human_model_callback" in signature.parameters
    assert "completion_margin" in signature.parameters
    assert "planning_joint_velocity_ceiling_rad_s" in signature.parameters
