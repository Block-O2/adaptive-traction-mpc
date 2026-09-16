from dataclasses import replace
import inspect

import numpy as np
import pytest

import traction_mpc_stage5.human_identification_reduced as reduced_module
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    ReducedShadowHumanIdentificationService,
    Stage5ReducedHumanIDConfig,
    _session_validation_blocks,
    progressive_transition_evidence,
)
from traction_mpc_stage5.progressive_human_model import (
    ActiveHumanModel,
    POPULATION_PRIOR_THETA,
    PostUpdateSupport,
    ProgressiveHumanModelAuthority,
    human_model_id,
)


THETA_0 = np.ones(3)
THETA_1 = np.array(
    [1.0000584390985465, 1.0010424686528112, 1.0193479803467633]
)
CANDIDATE = np.array([1.0, 1.0, 1.2])


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


def _theta_0_model() -> ActiveHumanModel:
    return ActiveHumanModel.create(
        session_id="progressive-test",
        update_index=0,
        theta=THETA_0,
        predecessor_model_id=None,
        provenance="population_prior",
        activation_repetition=1,
        activation_time_s=0.0,
        rollback_predecessor_id=None,
        candidate_evidence_id=None,
        post_update_support=PostUpdateSupport.POSITIVE,
    )


def _theta_1_model() -> ActiveHumanModel:
    predecessor = _theta_0_model()
    return ActiveHumanModel.create(
        session_id="progressive-test",
        update_index=1,
        theta=THETA_1,
        predecessor_model_id=predecessor.model_id,
        provenance="RPL-A_frozen_successor_replication",
        activation_repetition=1,
        activation_time_s=0.0,
        rollback_predecessor_id=predecessor.model_id,
        candidate_evidence_id="rpl-a-theta-1",
        bounded_transition_delta=THETA_1 - THETA_0,
        qualification_repetition=0,
        qualification_time_s=0.0,
        post_update_support=PostUpdateSupport.POSITIVE,
    )


def _authority(*, updates_enabled: bool = True) -> ProgressiveHumanModelAuthority:
    authority = ProgressiveHumanModelAuthority(
        _geometry(), _theta_1_model(), updates_enabled=updates_enabled
    )
    authority.begin_repetition(1, 0.0)
    return authority


def _install_qualified_service_proposal(
    authority: ProgressiveHumanModelAuthority,
    *,
    candidate: np.ndarray = CANDIDATE,
    predecessor_model_id: str | None = None,
    evidence_id: str = "candidate-2-future-validation",
    qualification_time_s: float = 3.2,
) -> None:
    predecessor = predecessor_model_id or authority.active_model.model_id
    proposed = authority.service.identifier.bounded_smoothed_step(
        np.asarray(authority.active_model.theta), np.asarray(candidate)
    )
    authority.service.queued_publication = {
        "predecessor_model_version": predecessor,
        "predecessor_scales": list(authority.active_model.theta),
        "proposed_model_scales": proposed.tolist(),
        "candidate_scales": np.asarray(candidate).tolist(),
        "challenger_index": authority.active_model.update_index,
        "qualification_evidence_id": evidence_id,
        "qualification_time_s": qualification_time_s,
    }


def _queue_theta_2(authority: ProgressiveHumanModelAuthority):
    _install_qualified_service_proposal(authority)
    return authority.queue_service_qualified_successor(
        transition_source="registered_reduced_human_id",
        qualification_repetition=1,
    )


def _activate_theta_2() -> tuple[ProgressiveHumanModelAuthority, str, str]:
    authority = _authority()
    theta_1_id = authority.active_model.model_id
    queued = _queue_theta_2(authority)
    authority.begin_repetition(2, 10.0)
    return authority, theta_1_id, queued.successor_model_id


def test_initialization_loads_matching_non_nominal_active_model() -> None:
    authority = _authority()
    assert authority.active_model.theta == tuple(THETA_1)
    assert authority.service.retained_model_version == authority.active_model.model_id
    np.testing.assert_array_equal(authority.service.retained_scales, THETA_1)
    assert authority.service.status()["trust_state"] == "ACTIVE_INCUMBENT"
    np.testing.assert_allclose(
        authority.control_human_model.beta, authority.service.retained_model.beta
    )


def test_non_nominal_successor_is_bounded_from_theta_1() -> None:
    authority = _authority()
    queued = _queue_theta_2(authority)
    expected = THETA_1 + 0.10 * (CANDIDATE - THETA_1)
    np.testing.assert_allclose(queued.successor_theta, expected, atol=1.0e-15)
    assert not np.allclose(queued.successor_theta, THETA_0 + 0.1 * (CANDIDATE - THETA_0))


def test_transition_authority_uses_active_predecessor_not_population_prior() -> None:
    count = Stage5ReducedHumanIDConfig().trust.minimum_clean_blocks
    evidence = progressive_transition_evidence(
        np.full(count, 0.9),
        np.full(count, 0.8),
        np.full(count, 1.0),
        config=Stage5ReducedHumanIDConfig().trust,
    )
    assert evidence["against_population_prior"]["lower_bound_nms2"] > 0.0
    assert evidence["against_last_valid"]["upper_bound_nms2"] < 0.0
    assert evidence["legacy_dual_reference_supported_diagnostic"] is False
    assert evidence["transition_authority_supported"] is True
    assert evidence["population_prior_authoritative"] is False


def test_human_id_proposal_uses_non_nominal_retained_incumbent() -> None:
    service = ReducedShadowHumanIdentificationService(
        _geometry(),
        initial_incumbent_scales=THETA_1,
        initial_model_version=_theta_1_model().model_id,
        defer_qualified_publication=True,
    )
    service.identifier.attempt = lambda history, geometry, incumbent: {
        "attempted": True,
        "accepted": True,
        "candidate_scales": CANDIDATE.tolist(),
        "information": {"rank": 3},
        "bound_pressure": {},
    }
    attempt = service._launch_challenger(1.0)
    expected = THETA_1 + 0.1 * (CANDIDATE - THETA_1)
    assert attempt["reference_incumbent_model_version"] == _theta_1_model().model_id
    np.testing.assert_array_equal(attempt["reference_incumbent_scales"], THETA_1)
    np.testing.assert_allclose(attempt["proposed_model_scales"], expected)
    assert attempt["population_prior_scales"] == list(POPULATION_PRIOR_THETA)


def test_authority_consumes_matching_deferred_service_proposal() -> None:
    authority = _authority()
    expected = THETA_1 + 0.1 * (CANDIDATE - THETA_1)
    authority.service.queued_publication = {
        "predecessor_model_version": authority.active_model.model_id,
        "predecessor_scales": list(THETA_1),
        "proposed_model_scales": expected.tolist(),
        "candidate_scales": CANDIDATE.tolist(),
        "challenger_index": 2,
        "qualification_evidence_id": "service-challenger-2",
        "qualification_time_s": 3.2,
    }
    queued = authority.queue_service_qualified_successor(
        transition_source="registered_reduced_human_id",
        qualification_repetition=1,
    )
    np.testing.assert_allclose(queued.successor_theta, expected)
    authority.begin_repetition(2, 10.0)
    assert authority.service.queued_publication is None
    assert authority.service.retained_model_version == queued.successor_model_id


def test_service_qualification_defers_incumbent_change_until_boundary(
    monkeypatch,
) -> None:
    model = _theta_1_model()
    service = ReducedShadowHumanIdentificationService(
        _geometry(),
        initial_incumbent_scales=THETA_1,
        initial_model_version=model.model_id,
        defer_qualified_publication=True,
    )
    expected = service.identifier.bounded_smoothed_step(THETA_1, CANDIDATE)
    service.active_challenger = {
        "challenger_index": 4,
        "fit_end_time_s": 0.0,
        "minimum_validation_ready_time_s": 0.0,
        "proposed_model_scales": expected.tolist(),
        "reference_incumbent_scales": THETA_1.tolist(),
        "candidate_scales": CANDIDATE.tolist(),
        "evaluated_look_block_counts": [],
        "evidence_history": [],
    }
    monkeypatch.setattr(
        reduced_module,
        "_session_validation_blocks",
        lambda *args, **kwargs: [
            {
                "regressor": np.zeros((2, 11)),
                "target": np.zeros(2),
                "start_time_s": 0.2 * index,
                "end_time_s": 0.2 * (index + 1),
                "episode_index": 0,
            }
            for index in range(8)
        ],
    )
    monkeypatch.setattr(
        reduced_module,
        "progressive_transition_evidence",
        lambda *args, **kwargs: {
            "transition_authority_supported": True,
            "transition_authority_negative": False,
            "population_prior_authoritative": False,
        },
    )
    service._resolve_challenger(2.0)
    np.testing.assert_array_equal(service.retained_scales, THETA_1)
    assert service.retained_model_version == model.model_id
    assert service.queued_publication["predecessor_model_version"] == model.model_id
    assert service.attempts == []
    assert service.active_challenger is None


def test_qualified_successor_is_queued_without_mid_repetition_activation() -> None:
    authority = _authority()
    active_before = authority.active_model
    queued = _queue_theta_2(authority)
    assert authority.active_model == active_before
    assert authority.queued_update == queued
    assert queued.target_activation_repetition == 2


def test_queued_successor_activates_once_at_next_repetition_boundary() -> None:
    authority = _authority()
    queued = _queue_theta_2(authority)
    result = authority.begin_repetition(2, 10.0)
    assert authority.active_model.model_id == queued.successor_model_id
    assert result["activation"]["active_model_id"] == queued.successor_model_id
    assert authority.queued_update is None
    assert authority.service.retained_model_version == queued.successor_model_id


def test_theta_2_lineage_names_theta_1_as_predecessor_and_rollback() -> None:
    authority, theta_1_id, theta_2_id = _activate_theta_2()
    theta_2 = authority.lineage[theta_2_id]
    assert theta_2.predecessor_model_id == theta_1_id
    assert theta_2.rollback_predecessor_id == theta_1_id
    assert theta_1_id in authority.lineage


def test_post_update_neutral_holds_theta_2_and_blocks_theta_3() -> None:
    authority, theta_1_id, theta_2_id = _activate_theta_2()
    authority.record_post_update_evidence(
        PostUpdateSupport.NEUTRAL,
        target_model_id=theta_2_id,
        predecessor_model_id=theta_1_id,
        evidence_id="theta-2-neutral",
        evidence_repetition=2,
        evidence_time_s=13.0,
    )
    assert authority.active_model.model_id == theta_2_id
    assert authority.can_qualify_next is False
    _install_qualified_service_proposal(
        authority,
        evidence_id="candidate-3",
        qualification_time_s=14.0,
    )
    with pytest.raises(RuntimeError, match="lacks POSITIVE"):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=2,
        )


def test_post_update_positive_enables_theta_3_queue_and_activation() -> None:
    authority, theta_1_id, theta_2_id = _activate_theta_2()
    authority.record_post_update_evidence(
        PostUpdateSupport.POSITIVE,
        target_model_id=theta_2_id,
        predecessor_model_id=theta_1_id,
        evidence_id="theta-2-positive",
        evidence_repetition=2,
        evidence_time_s=13.0,
    )
    assert authority.can_qualify_next
    _install_qualified_service_proposal(
        authority,
        evidence_id="candidate-3",
        qualification_time_s=14.0,
    )
    queued = authority.queue_service_qualified_successor(
        transition_source="test",
        qualification_repetition=2,
    )
    authority.begin_repetition(3, 20.0)
    assert authority.active_model.model_id == queued.successor_model_id
    assert authority.active_model.predecessor_model_id == theta_2_id


def test_post_update_negative_blocks_progression_and_preserves_rollback() -> None:
    authority, theta_1_id, theta_2_id = _activate_theta_2()
    authority.record_post_update_evidence(
        PostUpdateSupport.NEGATIVE,
        target_model_id=theta_2_id,
        predecessor_model_id=theta_1_id,
        evidence_id="theta-2-negative",
        evidence_repetition=2,
        evidence_time_s=13.0,
    )
    assert authority.progression_blocked
    assert authority.active_model.rollback_predecessor_id == theta_1_id
    assert theta_1_id in authority.lineage
    _install_qualified_service_proposal(
        authority,
        evidence_id="candidate-3",
        qualification_time_s=14.0,
    )
    with pytest.raises(RuntimeError, match="blocked by negative"):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=2,
        )


def test_at_most_one_model_transition_per_repetition() -> None:
    authority = _authority()
    _queue_theta_2(authority)
    authority.service.queued_publication = {
        **authority.service.queued_publication,
        "qualification_evidence_id": "different-candidate",
    }
    with pytest.raises(RuntimeError, match="already queued"):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=1,
        )
    authority.begin_repetition(2, 10.0)
    with pytest.raises(ValueError, match="increase one at a time"):
        authority.begin_repetition(2, 11.0)


def test_stale_candidate_cannot_modify_newer_active_model() -> None:
    authority, theta_1_id, theta_2_id = _activate_theta_2()
    authority.record_post_update_evidence(
        PostUpdateSupport.POSITIVE,
        target_model_id=theta_2_id,
        predecessor_model_id=theta_1_id,
        evidence_id="theta-2-positive",
        evidence_repetition=2,
        evidence_time_s=13.0,
    )
    _install_qualified_service_proposal(
        authority,
        predecessor_model_id=theta_1_id,
        evidence_id="stale-candidate",
        qualification_time_s=14.0,
    )
    with pytest.raises(RuntimeError, match="stale predecessor"):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=2,
        )


def test_model_version_and_theta_mismatch_raises_explicit_error() -> None:
    model = _theta_1_model()
    with pytest.raises(ValueError, match="id and theta"):
        replace(model, model_id=human_model_id(model.session_id, 1, THETA_0))


def test_reset_boundary_blocks_never_mix_repetitions() -> None:
    def records(episode: int, start: float):
        return [
            {
                "time_s": start + 0.005 * index,
                "state": np.array([0.2, 0.3, 0.01, 0.02]),
                "generalized_input_nm": np.array([1.0, -0.2]),
                "contaminated": False,
                "source_index": episode * 1000 + index,
                "episode_index": episode,
            }
            for index in range(51)
        ]

    history = records(0, 0.0) + records(1, 1.0)
    blocks = _session_validation_blocks(
        history,
        fit_end_time_s=-0.2,
        window_s=0.2,
        embargo_windows=1,
        count=8,
    )
    assert blocks
    for block in blocks:
        episode_prefixes = {index // 1000 for index in block["source_indices"]}
        assert episode_prefixes == {block["episode_index"]}


def test_population_prior_remains_reference_only_after_theta_1() -> None:
    authority = _authority()
    roles = authority.service.status()["model_roles"]
    assert roles["population_prior_scales"] == list(POPULATION_PRIOR_THETA)
    assert roles["active_incumbent_scales"] == list(THETA_1)
    assert authority.summary()["population_prior"]["transition_authority"] is False


def test_truth_cannot_enter_progressive_authority_api() -> None:
    authority = _authority()
    signature = inspect.signature(authority.queue_service_qualified_successor)
    assert all("truth" not in name.lower() for name in signature.parameters)
    with pytest.raises(TypeError):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=1,
            truth_scales=np.array([9.0, 9.0, 9.0]),
        )
    assert authority.summary()["truth_available"] is False


def test_progressive_authority_never_modifies_gamma() -> None:
    authority = _authority()
    assert authority.pacing_status() == {"gamma": 0.5, "gamma_rate_per_s": 0.0}
    _queue_theta_2(authority)
    authority.begin_repetition(2, 10.0)
    assert authority.pacing_status() == {"gamma": 0.5, "gamma_rate_per_s": 0.0}
    assert authority.summary()["gamma_authority"] is False


def test_acceleration_monitor_path_remains_unchanged() -> None:
    source = inspect.getsource(run_goal_mpc_smoke)
    assert "acceleration_monitor.update(\n                task_observation, interface_state, estimation_model" in source
    assert "ProgressiveHumanModelAuthority" not in source


def test_fixed_arm_never_changes_theta_1() -> None:
    authority = _authority(updates_enabled=False)
    _install_qualified_service_proposal(authority)
    with pytest.raises(RuntimeError, match="fixed-model arm"):
        authority.queue_service_qualified_successor(
            transition_source="test",
            qualification_repetition=1,
        )
    assert authority.active_model.theta == tuple(THETA_1)
