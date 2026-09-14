from __future__ import annotations

from pathlib import Path

import numpy as np

from traction_mpc_stage5.goal_mpc_consistency_audit import (
    replay_saved_action_sequence,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]


def test_saved_attempt02_actions_exactly_reproduce_primary_failure() -> None:
    primary_path = STAGE5_ROOT / "results/goal_mpc_smoke_v1/attempt_02/trace.npz"
    with np.load(primary_path) as archive:
        primary = {name: np.asarray(archive[name]).copy() for name in archive.files}
    replay = replay_saved_action_sequence(primary)

    np.testing.assert_array_equal(
        replay["state_raw_robot_side_rad_rad_s"],
        primary["estimated_state_rad_rad_s"],
    )
    np.testing.assert_array_equal(
        replay["replayed_physical_force_world_n"],
        primary["physical_cuff_force_world_n"],
    )
    np.testing.assert_array_equal(
        replay["replayed_physical_moment_world_nm"],
        primary["physical_cuff_moment_world_nm"],
    )
    assert set(replay["safety_filter_status"]) == {"SAFE_UNCHANGED"}

    physical = replay["replayed_physical_force_world_n"]
    constitutive = (
        replay["interface_spring_force_world_n"]
        + replay["interface_damping_force_world_n"]
    )
    np.testing.assert_allclose(physical, constitutive, rtol=0.0, atol=3.0e-14)


def test_full_human_side_pose_is_audit_only_exact_geometry_control() -> None:
    primary_path = STAGE5_ROOT / "results/goal_mpc_smoke_v1/attempt_02/trace.npz"
    with np.load(primary_path) as archive:
        primary = {name: np.asarray(archive[name]).copy() for name in archive.files}
    replay = replay_saved_action_sequence(primary)
    error = (
        replay["state_full_human_side_offline_rad_rad_s"]
        - replay["truth_state_rad_rad_s"]
    )
    assert np.max(np.abs(error)) < 2.0e-15
