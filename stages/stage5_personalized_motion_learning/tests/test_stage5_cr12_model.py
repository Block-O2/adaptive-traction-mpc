from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage5.cr12_plant import (
    Stage5CR12SpringDamperPlant,
    make_stage5_plant,
)
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


def test_cr12_robot_contract_matches_official_urdf_values() -> None:
    robot = CR12TorqueRobot()
    assert robot.model.nq == robot.model.nv == robot.model.nu == 6
    np.testing.assert_allclose(
        robot.joint_limits_rad,
        [
            [-6.2832, 6.2832],
            [-2.9671, 2.9671],
            [-6.2832, 6.2832],
            [-6.2832, 6.2832],
            [-6.2832, 6.2832],
            [-6.2832, 6.2832],
        ],
    )
    np.testing.assert_allclose(robot.torque_limits_nm, [436, 436, 194, 102, 66, 66])
    np.testing.assert_allclose(
        robot.velocity_limits_rad_s,
        [
            2.0943951023931953,
            2.0943951023931953,
            3.141592653589793,
            4.084070449666731,
            4.1887902047863905,
            4.1887902047863905,
        ],
    )
    np.testing.assert_allclose(robot.model.dof_armature[robot.dof_indices], 0.1)
    assert np.all(np.isfinite(robot.model.body_inertia[2:]))
    assert np.all(robot.model.body_inertia[2:] > 0.0)


def test_cr12_jacobian_matches_finite_difference() -> None:
    robot = CR12TorqueRobot()
    check = robot.finite_difference_jacobian_check(
        np.radians([-120.0, -64.0, 128.0, -30.0, -100.0, 89.0]),
        np.array([0.2, -0.1, 0.15, -0.05, 0.1, -0.2]),
    )
    assert check.max_abs_error < 1.0e-7


def test_cr12_stage5_start_and_goal_reset_are_reachable() -> None:
    plant = Stage5CR12SpringDamperPlant()
    for human_q in (
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad,
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad,
    ):
        observation = plant.reset(np.asarray(human_q))
        assert observation.weld_position_error_m < 1.0e-8
        assert observation.weld_rotation_error_rad < 1.0e-8
        assert not observation.unintended_contact_pairs
        jacobian = plant.robot_attachment_jacobian()
        assert jacobian.shape == (6, 6)
        assert np.linalg.matrix_rank(jacobian) == 6


def test_cr12_provisional_cuff_is_bound_to_link6_with_stage5_transform() -> None:
    plant = Stage5CR12SpringDamperPlant()
    cuff_site_id = plant.model.site("adapter_cuff_site").id
    assert plant.model.body(int(plant.model.site_bodyid[cuff_site_id])).name == (
        "xMateCR12_link6"
    )
    np.testing.assert_allclose(
        plant.model.site_pos[cuff_site_id],
        STAGE5_GEOMETRY.end_effector_from_cuff.translation,
        atol=1.0e-12,
    )
    modeled_rotation = Rotation.from_quat(
        plant.model.site_quat[cuff_site_id][[1, 2, 3, 0]]
    ).as_matrix()
    np.testing.assert_allclose(
        modeled_rotation,
        STAGE5_GEOMETRY.end_effector_from_cuff.rotation,
        atol=1.0e-12,
    )
    assert plant.model.geom_contype[plant.model.geom("cuff_adapter_geom").id] == 1
    assert plant.model.geom_contype[plant.model.geom("stage5_cuff_bar_geom").id] == 0


def test_cr12_cuff_jacobian_matches_independent_flange_offset() -> None:
    plant = Stage5CR12SpringDamperPlant()
    observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    robot = CR12TorqueRobot()
    robot.set_configuration(observation.robot_q_rad)
    independent = robot.rigid_offset_jacobian(
        STAGE5_GEOMETRY.end_effector_from_cuff.translation
    )
    np.testing.assert_allclose(
        plant.robot_attachment_jacobian(), independent, atol=1.0e-12
    )


def test_cr12_provisional_interface_wrench_mapping_is_finite_and_balanced() -> None:
    plant = Stage5CR12SpringDamperPlant()
    observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    perturbed_q = observation.robot_q_rad.copy()
    perturbed_q[0] += 1.0e-4
    plant.data.qpos[plant.robot_qpos_indices] = perturbed_q
    observation = plant.observe()
    interface = plant._evaluate_current_interface()
    human_position = plant.data.site_xpos[plant.sleeve_site_id]
    robot_position = plant.data.site_xpos[plant.attachment_site_id]
    common_origin_moment_balance = (
        interface.human_wrench_world[3:]
        + np.cross(human_position, interface.human_wrench_world[:3])
        + interface.robot_wrench_world[3:]
        + np.cross(robot_position, interface.robot_wrench_world[:3])
    )

    assert np.linalg.norm(observation.cuff_force_vector_n) > 0.0
    assert observation.cuff_wrench_reconstruction_residual_nm < 1.0e-12
    assert observation.human_wrench_torque_residual_nm < 1.0e-12
    np.testing.assert_allclose(
        interface.human_wrench_world[:3] + interface.robot_wrench_world[:3],
        0.0,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(common_origin_moment_balance, 0.0, atol=1.0e-12)


def test_cr12_actuator_boundary_accepts_unchanged_stage5_command_contract() -> None:
    plant = Stage5CR12SpringDamperPlant()
    observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    preview = plant.preview_executable_command(
        observation.attachment_position_m,
        np.zeros(3),
        observation.attachment_rotation_matrix,
        np.zeros(3),
        np.zeros(6),
    )
    assert preview.feasible
    assert np.all(np.isfinite(preview.joint_torque_command_nm))
    assert np.all(np.abs(preview.joint_torque_command_nm) <= plant.torque_limits_nm)
    plant.apply_executable_command(preview)
    np.testing.assert_allclose(
        plant.data.ctrl[plant.actuator_ids], preview.joint_torque_command_nm
    )


def test_robot_selector_preserves_ur10e_default() -> None:
    assert type(make_stage5_plant()).__name__ == "Stage5SpringDamperPlant"
    assert type(make_stage5_plant("cr12_v0")).__name__ == (
        "Stage5CR12SpringDamperPlant"
    )
