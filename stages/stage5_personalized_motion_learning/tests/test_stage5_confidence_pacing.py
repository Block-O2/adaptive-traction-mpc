import numpy as np

from traction_mpc_stage4.confidence_execution import ConfidenceAwareExecutionConfig
from traction_mpc_stage5.confidence_pacing import (
    Stage5ConfidencePacing,
    Stage5ConfidencePacingConfig,
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
