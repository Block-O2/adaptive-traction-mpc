import numpy as np
from traction_mpc_stage4.confidence_execution import ConfidenceAwareExecutionConfig
from traction_mpc_stage5.confidence_pacing import (
    CurrentModelTrustEvidence,
    CurrentModelTrustOutcome,
    Stage5ConfidencePacing,
    Stage5ConfidencePacingConfig,
    Stage5CurrentModelTrust,
    Stage5PacingEvidence,
    current_nominal_model_trust_from_shadow_service,
)


def _evidence(time_s: float, *, adequate: bool) -> Stage5PacingEvidence:
    return Stage5PacingEvidence(
        session_time_s=time_s,
        identification_informative=True,
        information_rank=3,
        information_condition_number=1.5,
        current_nominal_model_adequate=adequate,
        current_model_evidence_reason="test",
        challenger_status="pending_future_validation",
        shadow_publication_count=0,
    )


def test_historical_stage4_defaults_are_mapped_exactly() -> None:
    old = ConfidenceAwareExecutionConfig()
    new = Stage5ConfidencePacingConfig()
    assert new.minimum_gamma == old.minimum_speed_scale
    assert new.nominal_gamma == old.nominal_speed_scale
    assert new.recovery_rate_per_s == old.recovery_rate_per_s
    assert new.slowdown_rate_per_s == old.slowdown_rate_per_s
    assert (
        new.model_confidence_filter_time_constant_s
        == old.model_confidence_filter_time_constant_s
    )
    assert new.high_confidence_enter_threshold == old.high_confidence_enter_threshold
    assert new.high_confidence_exit_threshold == old.high_confidence_exit_threshold


def test_fit_information_and_pending_challenger_do_not_raise_gamma() -> None:
    pacing = Stage5ConfidencePacing()
    for time_s in (1.0, 2.0, 3.0):
        pacing.update(_evidence(time_s, adequate=False))
    status = pacing.status(3.0)
    assert status["gamma"] == 0.5
    assert status["execution_confidence_high"] is False
    assert pacing.evidence_history[-1]["information_affects_gamma"] is False
    assert pacing.evidence_history[-1]["challenger_publication_affects_gamma"] is False


def test_current_model_trust_is_filtered_hysteretic_and_rate_limited() -> None:
    pacing = Stage5ConfidencePacing()
    pacing.update(_evidence(1.0, adequate=True))
    assert pacing.status(1.0)["gamma"] == 0.5
    pacing.update(_evidence(2.0, adequate=True))
    assert pacing.status(2.0)["execution_confidence_high"] is True
    assert pacing.status(2.4)["gamma"] == 0.6
    assert pacing.status(4.0)["gamma"] == 1.0
    pacing.update(_evidence(4.0, adequate=False))
    assert np.isclose(pacing.status(4.1)["gamma"], 0.9)
    assert np.isclose(pacing.status(4.5)["gamma"], 0.5)
    pacing.update(_evidence(5.0, adequate=False))
    assert pacing.status(5.0)["execution_confidence_high"] is False
    assert pacing.status(5.1)["gamma"] == 0.5


def test_shadow_publication_never_pretends_nominal_is_trusted() -> None:
    supported, reason = current_nominal_model_trust_from_shadow_service(
        {
            "attempts": [
                {
                    "status": "published_to_shadow_incumbent",
                    "evidence_history": [{"promotion_supported": True}],
                }
            ]
        }
    )
    assert supported is False
    assert "shadow_only" in reason


def test_only_future_evidence_that_challenger_is_worse_supports_nominal() -> None:
    supported, _ = current_nominal_model_trust_from_shadow_service(
        {
            "attempts": [
                {
                    "status": "rejected_no_future_support",
                    "evidence_history": [
                        {
                            "statistically_worse_than_at_least_one_reference": True
                        }
                    ],
                }
            ]
        }
    )
    assert supported is True
    inconclusive, _ = current_nominal_model_trust_from_shadow_service(
        {
            "attempts": [
                {
                    "status": "rejected_no_future_support",
                    "evidence_history": [
                        {
                            "statistically_worse_than_at_least_one_reference": False
                        }
                    ],
                }
            ]
        }
    )
    assert inconclusive is False


def test_gamma_semantics_do_not_scale_support_hold_or_hard_limits() -> None:
    status = Stage5ConfidencePacing().status(0.0)
    assert status["planning_semantics"] == "v_plan_ceiling=gamma*[15,25]deg/s"
    assert status["support_scaled"] is False
    assert status["hold_equilibrium_scaled"] is False
    assert status["hard_motion_limits_scaled"] is False


def test_explicit_current_model_support_can_recover_gamma_after_filter_and_ramp() -> None:
    pacing = Stage5ConfidencePacing()
    rejected_status = Stage5PacingEvidence(
        session_time_s=1.0,
        identification_informative=True,
        information_rank=3,
        information_condition_number=1.5,
        current_nominal_model_adequate=True,
        current_model_evidence_reason="independent_future_support",
        challenger_status="rejected_no_future_support",
        shadow_publication_count=0,
    )
    pacing.update(rejected_status)
    pacing.update(
        Stage5PacingEvidence(
            **{
                **rejected_status.__dict__,
                "session_time_s": 2.0,
            }
        )
    )
    assert pacing.status(2.0)["execution_confidence_high"] is True
    assert pacing.status(2.4)["gamma"] == 0.6
    assert pacing.status(4.0)["gamma"] == 1.0


def test_information_quality_remains_separate_from_current_model_trust() -> None:
    pacing = Stage5ConfidencePacing()
    pacing.update(
        Stage5PacingEvidence(
            session_time_s=3.0,
            identification_informative=False,
            information_rank=0,
            information_condition_number=float("inf"),
            current_nominal_model_adequate=True,
            current_model_evidence_reason="independent_future_support",
            challenger_status="none",
            shadow_publication_count=0,
        )
    )
    assert pacing.filtered_current_model_confidence > 0.0
    assert pacing.evidence_history[-1]["information_affects_gamma"] is False


def test_inconclusive_rejection_does_not_erase_prior_current_model_support() -> None:
    trust = Stage5CurrentModelTrust("nominal-v1")
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=1.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version="attempt-0:look-2",
            reason="future_validation_supports_current_model",
        )
    )
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=2.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.NEUTRAL,
            evidence_version="attempt-1:look-2",
            reason="future_validation_inconclusive",
        )
    )
    assert trust.supported is True
    assert trust.status()["support_evidence_version"] == "attempt-0:look-2"


def test_unsupported_becomes_supported_only_from_valid_current_model_evidence() -> None:
    trust = Stage5CurrentModelTrust("nominal-v1")
    assert trust.supported is False
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=1.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version="attempt-0:look-2",
            reason="future_validation_supports_current_model",
        )
    )
    assert trust.supported is True
    assert trust.status()["support_evidence_time_s"] == 1.0


def test_information_quality_change_is_neutral_to_existing_support() -> None:
    trust = Stage5CurrentModelTrust("nominal-v1")
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=1.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version="support-1",
            reason="future_validation_supports_current_model",
        )
    )
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=2.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.NEUTRAL,
            evidence_version="information-rank-change",
            reason="information_quality_changed_without_model_evidence",
        )
    )
    assert trust.supported is True


def test_explicit_negative_current_model_evidence_revokes_support() -> None:
    trust = Stage5CurrentModelTrust("nominal-v1")
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=1.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version="support-1",
            reason="future_validation_supports_current_model",
        )
    )
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=2.0,
            current_model_version="nominal-v1",
            outcome=CurrentModelTrustOutcome.NEGATIVE,
            evidence_version="negative-2",
            reason="future_validation_rejects_current_model",
        )
    )
    assert trust.supported is False
    assert trust.status()["revocation_evidence_version"] == "negative-2"


def test_new_control_model_version_does_not_inherit_old_support() -> None:
    trust = Stage5CurrentModelTrust("model-A")
    trust.observe(
        CurrentModelTrustEvidence(
            session_time_s=1.0,
            current_model_version="model-A",
            outcome=CurrentModelTrustOutcome.SUPPORT,
            evidence_version="support-A",
            reason="future_validation_supports_current_model",
        )
    )
    trust.set_current_model("model-B", session_time_s=2.0)
    assert trust.supported is False
    assert trust.status()["current_model_version"] == "model-B"


def test_different_shadow_model_fit_or_publication_cannot_raise_current_trust() -> None:
    trust = Stage5CurrentModelTrust(
        "model-B", population_prior_model_version="model-A"
    )
    trust.observe_shadow_service(
        {
            "attempts": [
                {
                    "challenger_index": 0,
                    "status": "published_to_shadow_incumbent",
                    "evidence_history": [
                        {
                            "look_index": 0,
                            "against_population_prior": {
                                "lower_bound_nms2": -2.0,
                                "upper_bound_nms2": -1.0,
                            },
                        }
                    ],
                }
            ]
        },
        session_time_s=1.0,
    )
    assert trust.supported is False
    assert trust.history[-1]["applies_to_current_model"] is False


def test_shadow_service_maps_explicit_current_reference_support_and_negative() -> None:
    trust = Stage5CurrentModelTrust("nominal-v1")
    trust.observe_shadow_service(
        {
            "attempts": [
                {
                    "challenger_index": 0,
                    "status": "rejected_no_future_support",
                    "evidence_history": [
                        {
                            "look_index": 2,
                            "against_population_prior": {
                                "lower_bound_nms2": 1.0,
                                "upper_bound_nms2": 2.0,
                            },
                        }
                    ],
                }
            ]
        },
        session_time_s=1.0,
    )
    assert trust.supported is True
    trust.observe_shadow_service(
        {
            "attempts": [
                {
                    "challenger_index": 1,
                    "status": "published_to_shadow_incumbent",
                    "evidence_history": [
                        {
                            "look_index": 0,
                            "against_population_prior": {
                                "lower_bound_nms2": -2.0,
                                "upper_bound_nms2": -1.0,
                            },
                        }
                    ],
                }
            ]
        },
        session_time_s=2.0,
    )
    assert trust.supported is False


def test_historical_pre_support_gamma_matches_stateless_semantics() -> None:
    stateless = Stage5ConfidencePacing()
    persistent = Stage5ConfidencePacing()
    trust = Stage5CurrentModelTrust("nominal-v1")
    attempt_sequences = (
        [],
        [
            {
                "challenger_index": 0,
                "status": "published_to_shadow_incumbent",
                "evidence_history": [{"promotion_supported": True}],
            }
        ],
        [
            {
                "challenger_index": 0,
                "status": "published_to_shadow_incumbent",
                "evidence_history": [{"promotion_supported": True}],
            },
            {
                "challenger_index": 1,
                "status": "rejected_no_future_support",
                "evidence_history": [
                    {"statistically_worse_than_at_least_one_reference": False}
                ],
            },
        ],
    )
    for time_s, attempts in zip((0.0, 3.045, 5.645), attempt_sequences):
        old_supported, old_reason = current_nominal_model_trust_from_shadow_service(
            {"attempts": attempts}
        )
        trust.observe_shadow_service(
            {"attempts": attempts}, session_time_s=time_s
        )
        common = dict(
            session_time_s=time_s,
            identification_informative=bool(attempts),
            information_rank=3 if attempts else 0,
            information_condition_number=4.0 if attempts else float("inf"),
            challenger_status="none",
            shadow_publication_count=1 if attempts else 0,
        )
        stateless.update(
            Stage5PacingEvidence(
                **common,
                current_nominal_model_adequate=old_supported,
                current_model_evidence_reason=old_reason,
            )
        )
        persistent.update(
            Stage5PacingEvidence(
                **common,
                current_nominal_model_adequate=trust.supported,
                current_model_evidence_reason=trust.status()["state_reason"],
            )
        )
        assert persistent.status(time_s)["gamma"] == stateless.status(time_s)["gamma"]
        assert persistent.status(time_s)["gamma_target"] == stateless.status(time_s)[
            "gamma_target"
        ]
