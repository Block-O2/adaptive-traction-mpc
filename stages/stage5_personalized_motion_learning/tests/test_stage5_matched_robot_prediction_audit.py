from __future__ import annotations

import numpy as np

import audit_stage5_matched_robot_prediction as audit


def test_match_mismatch_reports_exact_common_candidate_and_pose_offsets() -> None:
    identity = np.eye(3)
    cr12 = {
        "task_progress": 0.2,
        "truth_human_q_rad": np.radians([10.0, 20.0]),
        "truth_human_dq_rad_s": np.radians([1.0, 2.0]),
        "cuff_position_world_m": np.asarray([0.7, 0.0, 0.1]),
        "cuff_rotation_world": identity,
        "cuff_linear_velocity_world_m_s": np.asarray([0.01, 0.0, 0.0]),
        "measured_force_norm_n": 100.0,
        "interface_translation_norm_mm": 4.0,
        "shank_table_clearance_mm": 1.0,
        "applied_common_action_nm": np.asarray([40.0, -2.0]),
    }
    ur10e = {
        **cr12,
        "task_progress": 0.19,
        "truth_human_q_rad": np.radians([9.0, 20.0]),
        "cuff_position_world_m": np.asarray([0.699, 0.0, 0.1]),
        "measured_force_norm_n": 98.0,
        "shank_table_clearance_mm": 3.0,
    }
    result = audit._match_mismatch(cr12, ur10e)
    assert result["same_human_space_candidate"] is True
    assert np.isclose(result["human_q_difference_norm_deg"], 1.0)
    assert np.isclose(result["cuff_position_difference_mm"], 1.0)
    assert np.isclose(result["shank_clearance_difference_mm"], -2.0)


def test_ur10e_audit_adapter_does_not_invent_velocity_limit() -> None:
    robot = audit._AuditUR10eTorqueRobot()
    assert np.all(np.isinf(robot.velocity_limits_rad_s))
    assert robot.joint_limits_rad.shape == (6, 2)
