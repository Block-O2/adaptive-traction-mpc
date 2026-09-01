from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CuffForceCommandLimitError,
    CoupledUR10eHumanV2,
)
from traction_mpc_stage3.executable_command import (
    prepare_executable_command_context,
    preview_executable_command,
    preview_executable_commands_batch,
)
from traction_mpc_stage3.frames import (
    ATTACHMENT_FROM_CUFF,
    ENGINEERING_ATTACHMENT_FROM_CUFF,
)
from traction_mpc_stage3.robot import UR10eTorqueRobot


def _targets(plant: CoupledUR10eHumanV2) -> tuple[np.ndarray, ...]:
    observation = plant.observe()
    return (
        observation.attachment_position_m + np.array([2.0e-4, -1.0e-4, 3.0e-4]),
        observation.attachment_velocity_m_s + np.array([0.002, -0.003, 0.001]),
        observation.attachment_rotation_matrix,
        observation.attachment_angular_velocity_rad_s + np.array([0.01, 0.0, -0.02]),
        np.array([4.0, -3.0, 2.0, 0.2, -0.1, 0.3]),
    )


def _prepared_context():
    return prepare_executable_command_context(
        attachment_position_m=np.array([0.1, -0.2, 0.3]),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.array([0.01, -0.02, 0.03]),
        attachment_angular_velocity_rad_s=np.array([0.02, -0.01, 0.03]),
        robot_q_rad=np.linspace(-0.2, 0.3, 6),
        robot_dq_rad_s=np.linspace(0.03, -0.02, 6),
        neutral_robot_q_rad=np.zeros(6),
        target_position_m=np.array([0.12, -0.19, 0.27]),
        target_velocity_m_s=np.array([0.02, -0.01, 0.01]),
        target_rotation_matrix=np.eye(3),
        target_angular_velocity_rad_s=np.zeros(3),
        robot_attachment_jacobian=np.eye(6),
        bias_torque_nm=np.linspace(-1.0, 1.0, 6),
        torque_limits_nm=np.full(6, 1000.0),
    )


def test_batch_preview_matches_scalar_candidate_by_candidate() -> None:
    context = _prepared_context()
    wrenches = np.array(
        [
            [5.0, -3.0, 2.0, 0.2, -0.1, 0.3],
            [180.0, 30.0, -40.0, -0.4, 0.5, -0.6],
            [240.0, 90.0, 80.0, 0.7, -0.8, 0.9],
        ]
    )
    batch = preview_executable_commands_batch(context, wrenches)
    scalar = [
        preview_executable_command(
            attachment_position_m=np.zeros(3),
            attachment_rotation_matrix=np.eye(3),
            attachment_velocity_m_s=np.zeros(3),
            attachment_angular_velocity_rad_s=np.zeros(3),
            robot_q_rad=np.zeros(6),
            robot_dq_rad_s=np.zeros(6),
            neutral_robot_q_rad=np.zeros(6),
            target_position_m=np.zeros(3),
            target_velocity_m_s=np.zeros(3),
            target_rotation_matrix=np.eye(3),
            target_angular_velocity_rad_s=np.zeros(3),
            allocator_wrench_world=wrench,
            robot_attachment_jacobian=np.eye(6),
            bias_torque_nm=np.zeros(6),
            torque_limits_nm=np.full(6, 1000.0),
            prepared_context=context,
        )
        for wrench in wrenches
    ]
    for index, command in enumerate(scalar):
        np.testing.assert_array_equal(
            batch.force_position_n[index], command.force_position_n
        )
        np.testing.assert_array_equal(
            batch.force_velocity_n[index], command.force_velocity_n
        )
        np.testing.assert_array_equal(
            batch.force_allocator_n[index], command.force_allocator_n
        )
        np.testing.assert_array_equal(batch.force_total_n[index], command.force_total_n)
        assert batch.translational_force_norm_n[index] == (
            command.translational_force_norm_n
        )
        assert batch.margin_to_force_gate_n[index] == command.margin_to_force_gate_n
        assert bool(batch.feasible[index]) is command.feasible


def test_preview_is_side_effect_free_and_execution_applies_identical_command() -> None:
    plant = CoupledUR10eHumanV2()
    plant.reset(np.radians([5.0, 10.0]))
    targets = _targets(plant)
    before = {
        "qpos": plant.data.qpos.copy(),
        "qvel": plant.data.qvel.copy(),
        "ctrl": plant.data.ctrl.copy(),
        "time": float(plant.data.time),
        "last_joint_torque": plant.last_joint_torque.copy(),
        "last_unclipped_joint_torque": plant.last_unclipped_joint_torque.copy(),
        "last_force": plant.last_force.copy(),
        "last_moment": plant.last_moment.copy(),
    }

    preview = plant.preview_executable_command(*targets)

    np.testing.assert_array_equal(plant.data.qpos, before["qpos"])
    np.testing.assert_array_equal(plant.data.qvel, before["qvel"])
    np.testing.assert_array_equal(plant.data.ctrl, before["ctrl"])
    assert plant.data.time == before["time"]
    for name in (
        "last_joint_torque",
        "last_unclipped_joint_torque",
        "last_force",
        "last_moment",
    ):
        np.testing.assert_array_equal(getattr(plant, name), before[name])

    applied_preview = plant.apply_nominal_cartesian_control(*targets)
    np.testing.assert_array_equal(
        applied_preview.joint_torque_command_nm,
        preview.joint_torque_command_nm,
    )
    np.testing.assert_array_equal(
        plant.data.ctrl[plant.actuator_ids], preview.joint_torque_command_nm
    )
    np.testing.assert_array_equal(
        plant.last_unclipped_joint_torque, preview.unclipped_joint_torque_nm
    )
    np.testing.assert_array_equal(plant.last_force, preview.force_total_n)
    np.testing.assert_array_equal(plant.last_moment, preview.moment_total_nm)


def test_reported_force_components_sum_to_exact_executable_force() -> None:
    plant = CoupledUR10eHumanV2()
    plant.reset(np.radians([5.0, 10.0]))
    targets = list(_targets(plant))
    targets[0] = targets[0] + np.array([0.2, -0.2, 0.2])
    preview = plant.preview_executable_command(*targets)
    np.testing.assert_array_equal(
        preview.force_total_n,
        preview.force_position_n
        + preview.force_velocity_n
        + preview.force_allocator_n,
    )
    np.testing.assert_array_equal(
        preview.feedback_force_after_clipping_n,
        np.clip(preview.feedback_force_before_clipping_n, -200.0, 200.0),
    )
    assert preview.control_dt_s == CONTROL_DT_S == 0.005


@pytest.mark.parametrize(
    ("force_n", "expected_feasible"),
    (
        (200.0, True),
        (200.0 + 0.5e-9, True),
        (200.0 + 2.0e-9, False),
    ),
)
def test_200n_margin_and_feasibility_match_execution_gate(
    force_n: float,
    expected_feasible: bool,
) -> None:
    preview = preview_executable_command(
        attachment_position_m=np.zeros(3),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.zeros(3),
        attachment_angular_velocity_rad_s=np.zeros(3),
        robot_q_rad=np.zeros(6),
        robot_dq_rad_s=np.zeros(6),
        neutral_robot_q_rad=np.zeros(6),
        target_position_m=np.zeros(3),
        target_velocity_m_s=np.zeros(3),
        target_rotation_matrix=np.eye(3),
        target_angular_velocity_rad_s=np.zeros(3),
        allocator_wrench_world=np.array([force_n, 0.0, 0.0, 0.0, 0.0, 0.0]),
        robot_attachment_jacobian=np.eye(6),
        bias_torque_nm=np.zeros(6),
        torque_limits_nm=np.full(6, 1000.0),
    )
    assert preview.margin_to_force_gate_n == 200.0 - force_n
    assert preview.feasible is expected_feasible

    plant = CoupledUR10eHumanV2()
    plant.reset(np.radians([5.0, 10.0]))
    if expected_feasible:
        plant.apply_executable_command(preview)
    else:
        with pytest.raises(CuffForceCommandLimitError):
            plant.apply_executable_command(preview)


def test_offset_cuff_translational_jacobian_matches_finite_difference() -> None:
    robot = UR10eTorqueRobot()
    q = robot.home_q_rad + np.radians([4.0, -3.0, 2.0, 1.0, -2.0, 3.0])
    dq = np.array([0.17, -0.11, 0.08, -0.05, 0.07, -0.03])
    offset = ENGINEERING_ATTACHMENT_FROM_CUFF.translation
    robot.set_configuration(q)
    analytic = robot.rigid_offset_jacobian(offset)[:3] @ dq
    epsilon = 1.0e-7
    positions = []
    for sign in (1.0, -1.0):
        robot.set_configuration(q + sign * epsilon * dq)
        pose = robot.attachment_pose()
        positions.append(pose.translation + pose.rotation @ offset)
    finite_difference = (positions[0] - positions[1]) / (2.0 * epsilon)
    np.testing.assert_allclose(analytic, finite_difference, atol=1.0e-7)


def test_legacy_default_geometry_reproduces_pre_contract_low_level_formula() -> None:
    assert np.array_equal(ATTACHMENT_FROM_CUFF.translation, np.zeros(3))
    plant = CoupledUR10eHumanV2()
    plant.reset(np.radians([5.0, 10.0]))
    targets = _targets(plant)
    observation = plant.observe()
    preview = plant.preview_executable_command(*targets)

    legacy_force = 3000.0 * (targets[0] - observation.attachment_position_m)
    legacy_force += 140.0 * (targets[1] - observation.attachment_velocity_m_s)
    legacy_force = np.clip(legacy_force, -200.0, 200.0) + targets[4][:3]
    legacy_moment = 120.0 * plant._rotation_error(
        targets[2], observation.attachment_rotation_matrix
    )
    legacy_moment += 12.0 * (
        targets[3] - observation.attachment_angular_velocity_rad_s
    )
    legacy_moment += targets[4][3:]
    jacobian = plant.robot_attachment_jacobian()
    pinv = jacobian.T @ np.linalg.inv(jacobian @ jacobian.T + 1.0e-4 * np.eye(6))
    nullspace = np.eye(6) - pinv @ jacobian
    posture = 12.0 * (plant.neutral_robot_q - observation.robot_q_rad)
    posture -= 3.0 * observation.robot_dq_rad_s
    legacy_torque = plant.data.qfrc_bias[plant.robot_dof_indices].copy()
    legacy_torque += jacobian.T @ np.concatenate([legacy_force, legacy_moment])
    legacy_torque += nullspace.T @ posture

    np.testing.assert_allclose(preview.force_total_n, legacy_force, atol=1e-14)
    np.testing.assert_allclose(preview.moment_total_nm, legacy_moment, atol=1e-14)
    np.testing.assert_allclose(
        preview.unclipped_joint_torque_nm, legacy_torque, atol=1e-12
    )


def test_engineering_geometry_uses_actual_140mm_cuff_point() -> None:
    assert np.linalg.norm(
        ENGINEERING_ATTACHMENT_FROM_CUFF.translation
    ) == pytest.approx(0.140)
    plant = CoupledUR10eHumanV2(
        attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF
    )
    observation = plant.reset(np.radians([5.0, 10.0]))
    robot = UR10eTorqueRobot()
    robot.set_configuration(observation.robot_q_rad, observation.robot_dq_rad_s)
    np.testing.assert_allclose(
        plant.robot_attachment_jacobian(),
        robot.rigid_offset_jacobian(ENGINEERING_ATTACHMENT_FROM_CUFF.translation),
        atol=1e-10,
    )
