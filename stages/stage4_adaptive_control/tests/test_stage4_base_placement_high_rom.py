from __future__ import annotations

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage4.base_placement_high_rom import (
    BasePose,
    audit_base_pose,
    coarse_base_candidates,
)


def test_base_pose_translation_and_yaw_are_applied_to_coupled_robot() -> None:
    pose = BasePose(1.0, -0.75, 0.20, 15.0)
    plant = CoupledUR10eHumanV2(world_from_base=pose.transform())
    base_id = plant.model.body("base").id
    np.testing.assert_allclose(plant.model.body_pos[base_id], [1.0, -0.75, 0.20])
    base_rotation = np.zeros(9)
    mujoco.mju_quat2Mat(base_rotation, plant.model.body_quat[base_id])
    # The vendor model carries a fixed 180-degree base-body rotation.  The
    # requested world yaw composes with that intrinsic orientation.
    expected = pose.transform().rotation @ np.diag([-1.0, -1.0, 1.0])
    np.testing.assert_allclose(base_rotation.reshape(3, 3), expected, atol=1e-12)


def test_coarse_search_is_finite_four_coordinate_mounting_grid() -> None:
    candidates = coarse_base_candidates()
    assert len(candidates) == 81
    assert {candidate.x_m for candidate in candidates} == {0.90, 1.10, 1.30}
    assert {candidate.y_m for candidate in candidates} == {-0.62, -0.77, -0.92}
    assert {candidate.z_m for candidate in candidates} == {0.16, 0.24, 0.32}
    assert {candidate.yaw_deg for candidate in candidates} == {-20.0, 0.0, 20.0}


def test_revised_policy_retains_required_domains_and_ignores_support_proxies() -> None:
    result = audit_base_pose(
        BasePose(1.10, -0.62, 0.04, 0.0),
        sample_count=5,
        random_seed_count=8,
    )
    assert result["initial_exact_ik_branch_count"] >= 2
    for path in result["paths"].values():
        assert "robot_bed_m" in path["failure_intervals"]
        assert "distal_ankle_support_plane_m" in path["failure_intervals"]
        assert "cuff_bed_m" not in path["failure_intervals"]
        assert "thigh_bed_m" not in path["failure_intervals"]
        assert "mid_shank_bed_m" not in path["failure_intervals"]
        assert not path["policy"]["foot_model_added"]
        assert path["conditional_quasistatic"]["peak_cuff_force_n"] < 200.0
