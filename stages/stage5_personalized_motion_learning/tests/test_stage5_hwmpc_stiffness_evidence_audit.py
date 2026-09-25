import numpy as np

from audit_stage5_hwmpc_stiffness_evidence import (
    _extended_prefix_evidence,
    _future_blocks,
)


def _record(time_s: float, episode: int) -> dict:
    return {
        "time_s": time_s,
        "episode_index": episode,
        "repetition": episode + 1,
        "phase": "OUTBOUND" if episode == 0 else "RETURN",
        "state": np.array([0.15, 0.25, 0.0, 0.0]),
        "generalized_input_nm": np.zeros(2),
        "contaminated": False,
        "source_index": int(round(time_s * 1000.0)),
    }


def test_future_blocks_never_cross_episode_reset() -> None:
    records = [
        *[_record(index * 0.005, 0) for index in range(81)],
        *[_record(1.0 + index * 0.005, 1) for index in range(81)],
    ]

    blocks = _future_blocks(records, activation_time_s=0.0)

    assert len(blocks) == 3
    assert [block["episode_index"] for block in blocks] == [0, 1, 1]
    assert blocks[0]["start_time_s"] >= 0.005
    assert blocks[0]["end_time_s"] <= 0.4
    assert all(block["start_time_s"] >= 1.0 for block in blocks[1:])


def test_extended_prefixes_are_explicitly_offline_beyond_registered_looks() -> None:
    blocks = [
        {
            "regressor": np.array([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]]),
            "target": np.array([1.1, 1.1]),
            "repetition": 2,
            "phase": "OUTBOUND",
        }
        for _ in range(16)
    ]

    evidence = _extended_prefix_evidence(
        blocks,
        predecessor=(1.0, 1.0, 1.0),
        successor=(1.0, 1.1, 1.0),
        transition_index=1,
    )

    flags = {
        row["block_count"]: row["registered_online_look"]
        for row in evidence["prefixes"]
    }
    assert flags[8]
    assert flags[10]
    assert flags[12]
    assert flags[16] is False
    assert "do not alter the historical decision" in evidence["semantics"]
