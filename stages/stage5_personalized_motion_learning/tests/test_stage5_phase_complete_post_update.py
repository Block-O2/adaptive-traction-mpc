import numpy as np
import pytest

from traction_mpc_stage5.phase_complete_post_update import (
    PhaseCompletePostUpdateIdentity,
    PhaseCompletePostUpdateShadowV1,
)


def _identity() -> PhaseCompletePostUpdateIdentity:
    return PhaseCompletePostUpdateIdentity(
        predecessor_model_id="prior",
        successor_model_id="successor",
        predecessor_theta=(1.0, 1.0, 1.0),
        successor_theta=(1.01, 1.02, 1.03),
        successor_update_index=1,
        activation_repetition=2,
        activation_time_s=1.0,
    )


def _episode_records(
    *, episode_index: int, repetition: int, start_time_s: float
) -> list[dict]:
    records = []
    duration_s = 2.4
    for index, elapsed_s in enumerate(np.arange(0.005, duration_s + 0.001, 0.005)):
        if elapsed_s < 0.9:
            phase = "OUTBOUND"
        elif elapsed_s < 1.3:
            phase = "HOLD"
        else:
            phase = "RETURN"
        state = np.array(
            [
                0.20 + 0.01 * np.sin(elapsed_s),
                0.35 + 0.02 * np.sin(0.8 * elapsed_s),
                0.01 * np.cos(elapsed_s),
                0.016 * np.cos(0.8 * elapsed_s),
            ]
        )
        records.append(
            {
                "time_s": start_time_s + elapsed_s,
                "episode_index": episode_index,
                "repetition": repetition,
                "phase": phase,
                "state": state,
                "generalized_input_nm": np.zeros(2),
                "requested_q_rad": state[:2] - 0.001,
                "requested_dq_rad_s": state[2:] - 0.001,
                "control_model_version": "successor",
                "contaminated": False,
                "source_index": index,
            }
        )
    return records


def test_phase_complete_terminal_is_frozen_to_first_activation_cycle() -> None:
    evaluator = PhaseCompletePostUpdateShadowV1(_identity())
    first = _episode_records(episode_index=1, repetition=2, start_time_s=1.0)
    later = _episode_records(episode_index=2, repetition=3, start_time_s=4.0)
    for sample in [*first, *later]:
        evaluator.observe(sample)

    report = evaluator.report()

    assert report["shadow_only"]
    assert report["authority_effect"] == "none"
    assert report["historical_online_decision_rewritten"] is False
    assert report["phase_complete"]
    assert report["observed_phase_order"] == ["OUTBOUND", "HOLD", "RETURN"]
    assert report["terminal"]["block_count"] > 8
    assert report["later_shadow"]["all_block_count"] > report["terminal"]["block_count"]
    assert {
        row["episode_index"] for row in report["terminal"]["block_trajectory"]
    } == {1}
    assert report["terminal"]["phase_summary"]["OUTBOUND"]["tracking"][
        "available"
    ]


def test_phase_complete_shadow_rejects_noncausal_time_order() -> None:
    evaluator = PhaseCompletePostUpdateShadowV1(_identity())
    sample = _episode_records(
        episode_index=1, repetition=2, start_time_s=1.0
    )[0]
    evaluator.observe(sample)
    with pytest.raises(ValueError, match="time ordered"):
        evaluator.observe(sample)


def test_identity_requires_non_root_successor() -> None:
    with pytest.raises(ValueError, match="non-root"):
        PhaseCompletePostUpdateIdentity(
            predecessor_model_id="prior",
            successor_model_id="prior",
            predecessor_theta=(1.0, 1.0, 1.0),
            successor_theta=(1.0, 1.0, 1.0),
            successor_update_index=0,
            activation_repetition=1,
            activation_time_s=0.0,
        )
