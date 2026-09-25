from __future__ import annotations

import json

import numpy as np
import pytest

from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.near_limit_shadow import (
    NearLimitShadowTarget,
    select_near_limit_shadow_targets,
)


def test_selector_ranks_below_existing_boundary_within_context() -> None:
    time = 0.005 * np.arange(12)
    phase = np.asarray(["OUTBOUND"] * 10 + ["ABORTED"] * 2)
    acceleration_deg_s2 = np.asarray(
        [
            [10.0, 20.0],
            [20.0, 50.0],
            [30.0, 100.0],
            [40.0, 120.0],
            [50.0, 150.0],
            [60.0, 180.0],
            [70.0, 500.0],
            [80.0, 550.0],
            [90.0, 200.0],
            [100.0, 300.0],
            [110.0, 590.0],
            [120.0, 610.0],
        ]
    )
    targets = select_near_limit_shadow_targets(
        time_s=time,
        task_phase=phase,
        deployable_acceleration_rad_s2=np.radians(acceleration_deg_s2),
        registered_limit_rad_s2=np.radians([300.0, 600.0]),
        high_level_steps=4,
        cycle_offsets=(2, 3),
        source_trace="unit-test",
    )

    assert [target.mpc_cycle_offset for target in targets] == [2, 3]
    assert [target.timestamp_s for target in targets] == [0.030, 0.035]
    assert all(target.boundary_proximity < 1.0 for target in targets)
    assert all(target.record()["new_numeric_threshold"] is None for target in targets)


def test_near_limit_clone_isolated_from_authoritative_rollout(tmp_path) -> None:
    baseline_dir = tmp_path / "baseline"
    collection_dir = tmp_path / "collection"
    baseline = run_goal_mpc_smoke(baseline_dir, maximum_duration_s=0.050)
    target = NearLimitShadowTarget(
        timestamp_s=0.025,
        task_phase="OUTBOUND",
        mpc_cycle_offset=1,
        boundary_proximity=0.5,
        normalized_joint_acceleration=(0.25, 0.5),
        source_trace="unit-test-plan",
    )
    collection = run_goal_mpc_smoke(
        collection_dir,
        maximum_duration_s=0.050,
        near_limit_shadow_targets=(target,),
    )

    assert collection["task_status"] == baseline["task_status"]
    assert collection["abort_reason"] == baseline["abort_reason"]
    assert collection["task_duration_s"] == baseline["task_duration_s"]
    with np.load(baseline_dir / "trace.npz", allow_pickle=False) as left, np.load(
        collection_dir / "trace.npz", allow_pickle=False
    ) as right:
        assert set(left.files) == set(right.files)
        for name in left.files:
            np.testing.assert_array_equal(left[name], right[name])

    artifact = json.loads(
        (collection_dir / "near_limit_diagnostic_continuations.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["shadow_only"] is True
    assert artifact["abort_authority"] is False
    assert artifact["hard_threshold_active"] is False
    assert artifact["planned_target_count"] == 1
    assert artifact["captured_target_count"] == 1
    assert artifact["missed_targets"] == []
    window = artifact["windows"][0]
    assert window["trigger"]["kind"] == "NEAR_LIMIT_BENIGN_TRIGGER"
    response = window["continuation"]["transition_response_shadow_v2"]["events"][0]
    assert response["labels"] == ["NEAR_LIMIT_BENIGN_TRIGGER"]
    assert response["complete_0_to_20ms"] is True
    assert [sample["response_elapsed_s"] for sample in response["samples"]] == pytest.approx([
        0.0,
        0.005,
        0.010,
        0.015,
        0.020,
    ])
    for sample in response["samples"][1:]:
        np.testing.assert_allclose(sample["command_wrench_slew_world_per_s"], 0.0)
        np.testing.assert_allclose(sample["robot_joint_torque_slew_nm_s"], 0.0)
