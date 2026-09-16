import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.progressive_human_model import PostUpdateSupport
from traction_mpc_stage5.progressive_personalization import (
    FROZEN_THETA_1,
    LONGITUDINAL_CEM_SEEDS,
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    fixed_progress_pacing_status,
    parameter_direction_diagnostics,
)


CONFIG_PATH = (
    STAGE5_ROOT
    / "configs"
    / "stage5_progressive_personalization_longitudinal_v1.json"
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


def _session(
    arm: ProgressiveLongitudinalArm = ProgressiveLongitudinalArm.PROGRESSIVE,
    session_id: str = "longitudinal-test",
) -> ProgressiveLongitudinalSession:
    return ProgressiveLongitudinalSession(_geometry(), arm, session_id=session_id)


def _install_proposal(
    session: ProgressiveLongitudinalSession,
    *,
    candidate=(1.0, 1.0, 1.2),
    predecessor_model_id=None,
    evidence_id="candidate-evidence",
    qualification_time_s=3.0,
) -> None:
    authority = session.authority
    proposed = authority.service.identifier.bounded_smoothed_step(
        np.asarray(authority.active_model.theta), np.asarray(candidate)
    )
    authority.service.queued_publication = {
        "predecessor_model_version": (
            authority.active_model.model_id
            if predecessor_model_id is None
            else predecessor_model_id
        ),
        "predecessor_scales": list(authority.active_model.theta),
        "proposed_model_scales": proposed.tolist(),
        "candidate_scales": list(candidate),
        "challenger_index": authority.active_model.update_index,
        "qualification_evidence_id": evidence_id,
        "qualification_time_s": qualification_time_s,
    }


def _queue_theta_2(session: ProgressiveLongitudinalSession) -> None:
    _install_proposal(session)
    session.authority.queue_service_qualified_successor(
        transition_source="test",
        qualification_repetition=1,
    )


def _payload(session: ProgressiveLongitudinalSession) -> dict:
    return {
        "episode_time_s": 0.005,
        "estimated_human_state_rad_rad_s": np.zeros(4),
        "measured_human_cuff_force_world_n": np.zeros(3),
        "measured_human_cuff_moment_world_nm": np.zeros(3),
        "measured_generalized_human_input_nm": np.zeros(2),
        "task_phase": "OUTBOUND",
        "interface_model_version": session.authority.service.config.accepted_interface_model_version,
        "current_control_model_version": session.active_model.model_id,
    }


def test_matched_longitudinal_seed_schedule_is_preregistered() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["status"] == "PREREGISTERED_BEFORE_NEW_OUTCOMES"
    assert tuple(config["repetitions"]["matched_cem_seeds"]) == LONGITUDINAL_CEM_SEEDS
    assert config["repetitions"]["same_seed_for_both_arms_at_each_repetition"]


def test_fixed_arm_remains_theta_1_for_all_repetition_boundaries() -> None:
    session = _session(ProgressiveLongitudinalArm.FIXED_THETA_1, "fixed-test")
    for repetition in range(1, 6):
        snapshot = session.begin_repetition(repetition, 10.0 * (repetition - 1))
        np.testing.assert_array_equal(snapshot.active_theta, FROZEN_THETA_1)
        assert snapshot.activation is None


def test_progressive_arm_starts_exactly_at_theta_1() -> None:
    session = _session()
    snapshot = session.begin_repetition(1, 0.0)
    np.testing.assert_array_equal(snapshot.active_theta, FROZEN_THETA_1)
    assert session.active_model.post_update_support is PostUpdateSupport.POSITIVE


def test_qualified_proposal_queues_without_mid_repetition_activation() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    model_id = session.active_model.model_id
    _queue_theta_2(session)
    assert session.active_model.model_id == model_id
    assert session.authority.queued_update is not None


def test_boundary_activation_occurs_once_and_active_model_is_fixed_afterward() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _queue_theta_2(session)
    snapshot = session.begin_repetition(2, 10.0)
    assert snapshot.activation is not None
    assert snapshot.active_model_id != session.authority.lineage[
        snapshot.activation["predecessor_model_id"]
    ].model_id
    assert session.finalize_repetition()["active_fixed_within_repetition"]


def test_observation_never_applies_a_mid_repetition_update(monkeypatch) -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    monkeypatch.setattr(
        session.authority.service,
        "observe",
        lambda measurement: {"trust_state": "PRIOR_ONLY"},
    )
    model_id = session.active_model.model_id
    result = session.observe(_payload(session))
    assert result["apply_update"] is False
    assert session.active_model.model_id == model_id


def test_post_update_neutral_blocks_next_applied_correction() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    assert session.active_model.post_update_support is PostUpdateSupport.NEUTRAL
    _install_proposal(session, evidence_id="candidate-3", qualification_time_s=12.0)
    with pytest.raises(RuntimeError, match="lacks POSITIVE"):
        session.authority.queue_service_qualified_successor(
            transition_source="test", qualification_repetition=2
        )


def test_post_update_positive_permits_next_transition_queue() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    model = session.active_model
    session.authority.record_post_update_evidence(
        PostUpdateSupport.POSITIVE,
        target_model_id=model.model_id,
        predecessor_model_id=str(model.predecessor_model_id),
        evidence_id="theta-2-positive",
        evidence_repetition=2,
        evidence_time_s=12.0,
    )
    _install_proposal(session, evidence_id="candidate-3", qualification_time_s=13.0)
    queued = session.authority.queue_service_qualified_successor(
        transition_source="test", qualification_repetition=2
    )
    assert queued.predecessor_model_id == model.model_id


def test_post_update_negative_blocks_progression() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    model = session.active_model
    session.authority.record_post_update_evidence(
        PostUpdateSupport.NEGATIVE,
        target_model_id=model.model_id,
        predecessor_model_id=str(model.predecessor_model_id),
        evidence_id="theta-2-negative",
        evidence_repetition=2,
        evidence_time_s=12.0,
    )
    _install_proposal(session, evidence_id="candidate-3", qualification_time_s=13.0)
    with pytest.raises(RuntimeError, match="blocked by negative"):
        session.authority.queue_service_qualified_successor(
            transition_source="test", qualification_repetition=2
        )


def test_stale_candidate_cannot_cross_model_version_change() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    theta_1_id = session.active_model.model_id
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    _install_proposal(
        session,
        predecessor_model_id=theta_1_id,
        evidence_id="stale-candidate",
        qualification_time_s=12.0,
    )
    with pytest.raises(RuntimeError, match="stale predecessor"):
        session.authority.queue_service_qualified_successor(
            transition_source="test", qualification_repetition=2
        )


def test_predecessor_and_rollback_lineage_remain_immediate() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    theta_1_id = session.active_model.model_id
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    assert session.active_model.predecessor_model_id == theta_1_id
    assert session.active_model.rollback_predecessor_id == theta_1_id


def test_repetition_reset_boundaries_are_explicit_in_service() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    session.authority.service.last_sample_time_s = 5.0
    session.begin_repetition(2, 5.25)
    assert session.authority.service.episode_boundaries[-1] == {
        "episode_index": 1,
        "session_start_time_s": 5.25,
    }
    assert session.authority.service.summary()["reset_boundary_windows_forbidden"]


def test_gamma_is_exactly_fixed_at_half() -> None:
    assert fixed_progress_pacing_status({}) == {
        "gamma": 0.5,
        "gamma_rate_per_s": 0.0,
    }


def test_acceleration_monitor_path_is_unchanged() -> None:
    source = inspect.getsource(run_goal_mpc_smoke)
    assert "acceleration_monitor.update(\n                task_observation, interface_state, estimation_model" in source
    assert "progressive_personalization" not in source


def test_population_prior_never_regains_immediate_transition_authority() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    summary = session.authority.summary()
    assert summary["population_prior"]["transition_authority"] is False
    assert session.authority.service.retained_model_version == session.active_model.model_id


def test_truth_cannot_enter_session_observation_or_authority_api() -> None:
    signature = inspect.signature(ProgressiveLongitudinalSession.observe)
    assert all("truth" not in name.lower() for name in signature.parameters)
    session = _session()
    assert session.authority.summary()["truth_available"] is False


def test_initial_active_model_is_injected_atomically_into_goal_mpc_api() -> None:
    signature = inspect.signature(run_goal_mpc_smoke)
    assert "initial_control_human_model" in signature.parameters
    assert "initial_control_human_model_version" in signature.parameters
    source = inspect.getsource(run_goal_mpc_smoke)
    assert "initial control Human model and version must be provided together" in source


def test_both_arms_share_identical_preregistered_repetition_semantics() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["arms"]["fixed_theta_1"]["active_model"] == "theta_1 for every repetition"
    assert config["arms"]["progressive"]["activation"] == "next valid repetition boundary only"
    assert len(config["repetitions"]["matched_cem_seeds"]) == 5


def test_no_more_than_one_activation_can_occur_at_a_boundary() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _queue_theta_2(session)
    session.begin_repetition(2, 10.0)
    with pytest.raises(ValueError, match="increase one at a time"):
        session.begin_repetition(2, 11.0)


def test_fixed_arm_qualified_candidate_remains_shadow_only() -> None:
    session = _session(ProgressiveLongitudinalArm.FIXED_THETA_1, "fixed-shadow")
    session.begin_repetition(1, 0.0)
    _install_proposal(session)
    session._record_blocked_proposal("fixed_theta_1_arm_has_no_update_authority")
    assert session.authority.queued_update is None
    assert session.blocked_qualified_proposals[0]["blocked_reason"].startswith("fixed")
    np.testing.assert_array_equal(session.active_model.theta, FROZEN_THETA_1)


def test_one_settling_direction_change_is_reported_but_not_called_oscillation() -> None:
    diagnostics = parameter_direction_diagnostics(
        [
            [6.0e-5, 7.0e-4, 1.8e-2],
            [-6.0e-6, -1.7e-4, 1.9e-2],
            [-9.0e-6, -1.5e-4, 1.7e-2],
        ]
    )
    assert diagnostics["reversal_count"] == {
        "alpha_M": 1,
        "alpha_K": 1,
        "alpha_D": 0,
    }
    assert diagnostics["oscillatory"] == {
        "alpha_M": False,
        "alpha_K": False,
        "alpha_D": False,
    }
