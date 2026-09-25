import json

import numpy as np
import pytest

from traction_mpc_stage5.confidence_pacing import Stage5PacingEvidence
from traction_mpc_stage5.trust_gamma_matched import (
    TRUST_GAMMA_CEM_SEEDS,
    extract_supported_model,
    initialize_supported_trust,
    load_trust_gamma_contract,
    source_artifact_path,
)


def _evidence(time_s: float, supported: bool) -> Stage5PacingEvidence:
    return Stage5PacingEvidence(
        session_time_s=time_s,
        identification_informative=False,
        information_rank=0,
        information_condition_number=float("inf"),
        current_nominal_model_adequate=supported,
        current_model_evidence_reason="restored_supported_personalized_model",
        challenger_status="disabled_no_model_updates",
        shadow_publication_count=0,
    )


def _local_supported_model():
    contract = load_trust_gamma_contract()
    if not source_artifact_path(contract).exists():
        pytest.skip("ignored local formal max-step artifact is unavailable")
    return extract_supported_model(contract)


def test_contract_freezes_three_matched_repetitions_and_existing_pacing() -> None:
    contract = load_trust_gamma_contract()
    assert tuple(contract["repetitions"]["matched_cem_seeds"]) == (
        TRUST_GAMMA_CEM_SEEDS
    )
    assert contract["source_personalization_policy"] == {
        "model_update_alpha": 0.25,
        "maximum_per_scale_step": 0.04,
        "frozen_for_this_study": True,
    }
    assert contract["fixed_conditions"]["prefix_backend"] == "native"
    assert contract["fixed_conditions"]["prefix_times_ms"] == [5, 10, 15, 20]


def test_exact_supported_model_is_extracted_from_hashed_formal_artifact() -> None:
    frozen = _local_supported_model()
    assert frozen.support_outcome == "positive"
    assert frozen.model_id.endswith(":u005:540e39f0c5ef")
    assert frozen.theta == (
        1.0000989140471204,
        1.0012127972091571,
        1.1539417660360922,
    )
    assert frozen.support_evidence_id == (
        "post-update:stage5-human:max-step-v1-step_0p04:"
        "u005:540e39f0c5ef:positive:rep-5"
    )


def test_supported_provenance_restores_raw_trust_not_filtered_confidence() -> None:
    frozen = _local_supported_model()
    trust, pacing = initialize_supported_trust(frozen)
    assert trust.supported is True
    assert trust.status()["support_evidence_version"] == frozen.support_evidence_id
    assert pacing.filtered_current_model_confidence == 0.0
    assert pacing.status(0.0)["gamma"] == 0.5


def test_existing_filter_hysteresis_and_ramp_causally_recover_gamma() -> None:
    frozen = _local_supported_model()
    trust, pacing = initialize_supported_trust(frozen)
    for time_s in np.arange(0.0, 4.0 + 0.5 * 0.005, 0.005):
        pacing.update(_evidence(float(time_s), trust.supported))
    status = pacing.status(4.0)
    assert status["execution_confidence_high"] is True
    assert status["filtered_current_model_confidence"] > 0.99
    assert status["gamma"] == 1.0


def test_fixed_artifact_does_not_enable_successor_or_model_update_authority() -> None:
    contract = load_trust_gamma_contract()
    fixed = contract["fixed_conditions"]
    assert fixed["human_model_updates_enabled"] is False
    assert fixed["successor_activation_enabled"] is False
    assert fixed["human_identification_control_authority"] is False


def test_contract_is_strict_json() -> None:
    contract = load_trust_gamma_contract()
    assert json.loads(json.dumps(contract, allow_nan=False)) == contract


def test_local_formal_result_preserves_frozen_model_and_safety_semantics() -> None:
    result_path = (
        source_artifact_path(load_trust_gamma_contract()).parents[1]
        / "trust_gamma_matched_v1_formal_attempt_01"
        / "trust_gamma_matched_results.json"
    )
    if not result_path.exists():
        pytest.skip("ignored local formal trust-gamma result is unavailable")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["decision"]["code"] == "TG-A"
    assert payload["same_active_model_both_arms"] is True
    assert payload["human_model_updates_or_successor_activations"] == 0
    assert payload["truth_available_to_online_trust_pacing_or_control"] is False
    assert payload["acceleration_monitor_changed"] is False
    assert payload["analysis"]["registered_constraint_regression"] is False
    for arm in payload["arms"].values():
        assert len(arm["repetitions"]) == 3
        assert all(
            repetition["control"]["task_status"] == "COMPLETE"
            for repetition in arm["repetitions"]
        )
