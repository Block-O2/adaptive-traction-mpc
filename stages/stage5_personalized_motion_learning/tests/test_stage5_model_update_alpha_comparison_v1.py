import inspect
import json

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.model_update_alpha_comparison import (
    ALPHA_COMPARISON_CONFIG_PATH,
    ARM_ALPHAS,
    FROZEN_PP2_REP5_LOSS_NMS2,
    LONGITUDINAL_CEM_SEEDS,
    baseline_reuse_audit,
    bounded_update_diagnostics,
    config_equivalence_except_alpha,
    human_id_config_for_alpha,
    load_contract,
)
from traction_mpc_stage5.progressive_human_model import PostUpdateSupport
from traction_mpc_stage5.progressive_personalization import (
    FROZEN_THETA_1,
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    fixed_progress_pacing_status,
)


RUNNER_PATH = (
    STAGE5_ROOT / "scripts" / "run_stage5_model_update_alpha_comparison_v1.py"
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


def _session(alpha: float = 0.25) -> ProgressiveLongitudinalSession:
    return ProgressiveLongitudinalSession(
        _geometry(),
        ProgressiveLongitudinalArm.PROGRESSIVE,
        session_id=f"alpha-test-{str(alpha).replace('.', 'p')}",
        human_id_config=human_id_config_for_alpha(alpha),
    )


def _install_proposal(session: ProgressiveLongitudinalSession) -> None:
    authority = session.authority
    candidate = np.array([1.0, 1.0, 1.2])
    proposed = authority.service.identifier.bounded_smoothed_step(
        np.asarray(authority.active_model.theta), candidate
    )
    authority.service.queued_publication = {
        "predecessor_model_version": authority.active_model.model_id,
        "predecessor_scales": list(authority.active_model.theta),
        "proposed_model_scales": proposed.tolist(),
        "candidate_scales": candidate.tolist(),
        "challenger_index": authority.active_model.update_index,
        "qualification_evidence_id": "alpha-test-evidence",
        "qualification_time_s": 3.0,
    }


def test_only_preregistered_model_update_alphas_are_0p10_and_0p25() -> None:
    contract = load_contract()
    assert ARM_ALPHAS == {"alpha_0p10": 0.10, "alpha_0p25": 0.25}
    assert {
        name: arm["model_update_alpha"]
        for name, arm in contract["arms"].items()
    } == ARM_ALPHAS
    with pytest.raises(ValueError, match="only preregistered"):
        human_id_config_for_alpha(0.50)


def test_both_arms_retain_exactly_the_same_0p03_step_cap() -> None:
    arm_a = human_id_config_for_alpha(0.10)
    arm_b = human_id_config_for_alpha(0.25)
    assert arm_a.identifier.maximum_update_fraction_of_span == 0.03
    assert arm_b.identifier.maximum_update_fraction_of_span == 0.03
    assert arm_a.identifier.lower_scales == arm_b.identifier.lower_scales
    assert arm_a.identifier.upper_scales == arm_b.identifier.upper_scales
    assert _session(0.25).authority.service.identifier.config.smoothing_alpha == 0.25


def test_same_candidate_produces_expected_different_bounded_successors() -> None:
    candidate = np.array([1.0, 1.0, 1.2])
    a = bounded_update_diagnostics(
        FROZEN_THETA_1, candidate, model_update_alpha=0.10
    )
    b = bounded_update_diagnostics(
        FROZEN_THETA_1, candidate, model_update_alpha=0.25
    )
    np.testing.assert_allclose(
        np.asarray(a["successor"]) - np.asarray(FROZEN_THETA_1),
        0.10 * (candidate - np.asarray(FROZEN_THETA_1)),
        atol=1.0e-15,
        rtol=0.0,
    )
    assert b["actual_limited_displacement"][2] == pytest.approx(0.03)
    assert b["successor"] != a["successor"]


def test_cap_binding_and_larger_alpha_equivalence_are_reported_per_scale() -> None:
    result = bounded_update_diagnostics(
        FROZEN_THETA_1,
        [1.0, 1.0, 1.2],
        model_update_alpha=0.25,
    )
    assert result["step_cap_active"] == [False, False, True]
    assert result["larger_alpha_would_produce_same_component"] == [False, False, True]


def test_alpha_is_the_only_human_id_or_evidence_configuration_difference() -> None:
    equivalence = config_equivalence_except_alpha()
    assert equivalence == {
        "changed_identifier_fields": ["smoothing_alpha"],
        "trust_configs_equal": True,
        "service_fields_equal_except_identifier": True,
    }


def test_gamma_and_native_prefix_contract_are_frozen() -> None:
    contract = load_contract()
    assert fixed_progress_pacing_status({}) == {
        "gamma": 0.5,
        "gamma_rate_per_s": 0.0,
    }
    assert contract["controller"]["prefix_backend"] == "native"
    assert contract["controller"]["prefix_times_ms"] == [5, 10, 15, 20]
    assert contract["controller"]["physical_propagation_timestep_ms"] == 0.25
    assert 'prefix_backend="native"' in RUNNER_PATH.read_text(encoding="utf-8")


def test_qualified_successor_never_activates_mid_repetition() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    active_id = session.active_model.model_id
    _install_proposal(session)
    session.authority.queue_service_qualified_successor(
        transition_source="test", qualification_repetition=1
    )
    assert session.active_model.model_id == active_id
    assert session.authority.queued_update is not None
    boundary = session.begin_repetition(2, 10.0)
    assert boundary.activation is not None
    assert session.active_model.model_id != active_id


def test_no_next_update_before_post_update_positive() -> None:
    session = _session()
    session.begin_repetition(1, 0.0)
    _install_proposal(session)
    session.authority.queue_service_qualified_successor(
        transition_source="test", qualification_repetition=1
    )
    session.begin_repetition(2, 10.0)
    assert session.active_model.post_update_support is PostUpdateSupport.NEUTRAL
    assert not session.authority.can_qualify_next


def test_truth_is_not_part_of_online_session_measurement_or_authority_api() -> None:
    measurement_source = inspect.getsource(ProgressiveLongitudinalSession._measurement)
    observe_source = inspect.getsource(ProgressiveLongitudinalSession.observe)
    assert "truth" not in measurement_source.lower()
    assert 'payload["truth' not in observe_source.lower()
    assert '"truth_consumed": False' in observe_source


def test_seed_schedule_and_frozen_endpoint_are_exact() -> None:
    contract = load_contract()
    assert tuple(contract["repetitions"]["matched_cem_seeds"]) == LONGITUDINAL_CEM_SEEDS
    assert LONGITUDINAL_CEM_SEEDS == (
        20260828,
        20260829,
        20260830,
        20260831,
        20260832,
    )
    assert (
        contract["frozen_primary_endpoint"]["mean_squared_loss_nms2"]
        == FROZEN_PP2_REP5_LOSS_NMS2
    )


def test_saved_pp2_baseline_reuse_audit_passes_when_local_evidence_exists() -> None:
    audit = baseline_reuse_audit()
    if audit.get("reason") == "saved PP2-A result artifact is unavailable":
        pytest.skip("ignored local PP2-A result artifact is unavailable")
    assert audit["eligible"], audit
    assert all(audit["checks"].values())


def test_contract_is_strict_json_and_formal_run_requires_explicit_flag() -> None:
    payload = json.loads(ALPHA_COMPARISON_CONFIG_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "PREREGISTERED_FORMAL_EXECUTION_AUTHORIZED"
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    assert "--execute-formal-arm-b" in runner
    assert "if not arguments.execute_formal_arm_b" in runner
