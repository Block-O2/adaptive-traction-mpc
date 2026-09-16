from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_stage5_pp2_latency_counterfactual_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_pp2_latency_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_alpha_025_counterfactual_keeps_registered_step_cap() -> None:
    predecessor = np.asarray([1.0000584391, 1.0010424687, 1.0193479803])
    candidate = np.asarray([1.0006776873, 1.0083091198, 1.1991144762])
    successor, cap = AUDIT.bounded_successor(
        predecessor, candidate, alpha=0.25
    )

    np.testing.assert_allclose(
        successor,
        predecessor
        + np.clip(0.25 * (candidate - predecessor), -0.03, 0.03),
        atol=0.0,
        rtol=0.0,
    )
    assert cap.tolist() == [False, False, True]


def test_deployable_trace_loader_never_returns_truth_and_is_read_only(tmp_path) -> None:
    path = tmp_path / "trace.npz"
    np.savez_compressed(
        path,
        time_s=np.asarray([0.0, 0.1, 0.2]),
        estimated_state_rad_rad_s=np.zeros((3, 4)),
        deployable_measured_generalized_input_nm=np.zeros((3, 2)),
        evaluation_human_q_rad=np.ones((3, 2)),
        evaluation_only_instantaneous_acceleration_rad_s2=np.ones((3, 2)),
    )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    loaded = AUDIT.load_deployable_trace(path, 2.0)
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert set(loaded) == {
        "session_time_s",
        "estimated_state_rad_rad_s",
        "deployable_measured_generalized_input_nm",
    }
    np.testing.assert_allclose(loaded["session_time_s"], [2.0, 2.1, 2.2])
    assert before == after


def test_actual_and_counterfactual_losses_use_the_same_block_objects() -> None:
    projection = np.zeros((11, 3))
    projection[0, 2] = 1.0
    projection[1, 2] = 0.5
    blocks = [
        {"regressor": np.eye(2, 11), "target": np.asarray([0.2, -0.1])},
        {"regressor": 2.0 * np.eye(2, 11), "target": np.asarray([0.3, 0.4])},
    ]
    actual = AUDIT.block_losses([1.0, 1.0, 1.1], blocks, projection)
    counterfactual = AUDIT.block_losses([1.0, 1.0, 1.2], blocks, projection)

    assert actual.shape == counterfactual.shape == (2,)
    assert np.all(np.isfinite(actual))
    assert np.all(np.isfinite(counterfactual))
    assert not np.array_equal(actual, counterfactual)
