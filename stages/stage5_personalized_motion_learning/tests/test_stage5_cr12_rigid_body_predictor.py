from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.cr12_rigid_body_predictor import (
    CR12RigidBodyFirstActionBatchPreview,
    CR12RigidBodyPredictionContract,
    CR12RigidBodyPredictionState,
)
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


def test_contract_and_state_reject_invalid_values() -> None:
    contract = CR12RigidBodyPredictionContract(
        acceleration_margin_rad_s2=np.radians([30.0, 60.0]),
        calibration_group_ids=("calibration",),
    )
    assert contract.physics_dt_s == 0.00025
    assert contract.record()["contact_prediction"] is False

    with pytest.raises(ValueError, match="divide"):
        CR12RigidBodyPredictionContract(
            acceleration_margin_rad_s2=np.zeros(2),
            calibration_group_ids=(),
            physics_dt_s=0.0003,
        )
    with pytest.raises(ValueError, match="shape"):
        CR12RigidBodyPredictionState(
            q_rad=np.zeros(5),
            dq_rad_s=np.zeros(6),
            neutral_q_rad=np.zeros(6),
        )


def test_robot_fk_and_cuff_twist_match_integrated_cr12_model() -> None:
    plant = Stage5CR12SensorBoundaryPlant(STAGE5_HUMAN)
    observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    predictor = object.__new__(CR12RigidBodyFirstActionBatchPreview)
    predictor._robot = CR12TorqueRobot()
    predictor._rotate_twist_to_world = np.block(
        [
            [STAGE5_GEOMETRY.world_from_base.rotation, np.zeros((3, 3))],
            [np.zeros((3, 3)), STAGE5_GEOMETRY.world_from_base.rotation],
        ]
    )
    position, rotation, linear, angular, jacobian = predictor._robot_kinematics(
        observation.robot_q_rad, observation.robot_dq_rad_s
    )

    np.testing.assert_allclose(
        position, observation.attachment_position_m, atol=1.0e-10, rtol=0.0
    )
    np.testing.assert_allclose(
        rotation, observation.attachment_rotation_matrix, atol=1.0e-10, rtol=0.0
    )
    np.testing.assert_allclose(linear, np.zeros(3), atol=1.0e-12, rtol=0.0)
    np.testing.assert_allclose(angular, np.zeros(3), atol=1.0e-12, rtol=0.0)
    np.testing.assert_allclose(
        jacobian, plant.robot_attachment_jacobian(), atol=1.0e-10, rtol=0.0
    )


def test_physical_robot_wrench_preserves_common_origin_balance() -> None:
    human_wrench = np.asarray(
        [[12.0, -4.0, 7.0, 1.5, -2.0, 0.8]], dtype=float
    )
    robot_from_human = np.asarray([[0.04, 0.13, -0.02]], dtype=float)
    robot_wrench = CR12RigidBodyFirstActionBatchPreview._physical_robot_wrench(
        human_wrench, robot_from_human
    )
    np.testing.assert_allclose(
        robot_wrench[:, :3] + human_wrench[:, :3], 0.0, atol=1.0e-12
    )
    common_origin_moment = (
        human_wrench[:, 3:]
        + robot_wrench[:, 3:]
        + np.cross(robot_from_human, robot_wrench[:, :3])
    )
    np.testing.assert_allclose(common_origin_moment, 0.0, atol=1.0e-12)
