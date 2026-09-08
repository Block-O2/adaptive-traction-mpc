from __future__ import annotations

from dataclasses import replace

import mujoco
import numpy as np
import pytest

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import OneShotHumanEstimatorV2
from traction_mpc_stage4.executable_command import (
    make_stage4_first_action_batch_preview,
    preview_stage4_executable_command,
)
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.reference import teaching_reference
from traction_mpc_stage4.safety_filter import prepare_executable_force_filter_context
from traction_mpc_stage4.sensor_realism import (
    PROCESSED_POSE_HISTORY_VELOCITY,
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)


def _fixture(source: str):
    plant = SensorBoundaryStage4Plant(
        HUMAN,
        attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
        translational_velocity_feedback_source=source,
    )
    truth = plant.reset(np.radians([5.0, 10.0]))
    dq = np.array([0.17, -0.23, 0.11, -0.07, 0.19, -0.13])
    plant.data.qvel[plant.robot_dof_indices] = dq
    mujoco.mj_forward(plant.model, plant.data)
    truth = plant.observe()
    measurement = CausalMeasurementLayer(sensor_realism_cases()[0], truth).current
    return plant, truth, measurement


def _model_state(measurement):
    model = OneShotHumanEstimatorV2(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.radians([5.0, 10.0]),
    ).model
    state = model.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    return model, state


def test_joint_jacobian_control_velocity_matches_mujoco_cuff_site_velocity() -> None:
    plant, truth, measurement = _fixture(ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY)
    snapshot = plant.robot_joint_control_velocity_snapshot(measurement)
    np.testing.assert_allclose(
        snapshot.linear_velocity_world_m_s,
        truth.attachment_velocity_m_s,
        atol=2.0e-12,
        rtol=2.0e-12,
    )
    np.testing.assert_allclose(
        snapshot.angular_velocity_world_rad_s,
        truth.attachment_angular_velocity_rad_s,
        atol=2.0e-12,
        rtol=2.0e-12,
    )
    assert snapshot.source == ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
    assert snapshot.sample_time_s == measurement.control_velocity_sample_time_s


def test_control_velocity_uses_world_frame_cuff_center_and_one_adapter_offset() -> None:
    plant, _, measurement = _fixture(ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY)
    robot = UR10eTorqueRobot()
    robot.set_configuration(
        measurement.control_robot_q_rad, measurement.control_robot_dq_rad_s
    )
    expected = robot.rigid_offset_jacobian(
        ENGINEERING_ATTACHMENT_FROM_CUFF.translation
    ) @ measurement.control_robot_dq_rad_s
    actual = plant.robot_joint_control_velocity_snapshot(measurement)
    np.testing.assert_allclose(
        np.concatenate(
            [
                actual.linear_velocity_world_m_s,
                actual.angular_velocity_world_rad_s,
            ]
        ),
        expected,
        atol=1.0e-14,
        rtol=1.0e-14,
    )
    assert np.linalg.norm(ENGINEERING_ATTACHMENT_FROM_CUFF.translation) == pytest.approx(
        0.14
    )


def test_new_control_velocity_rejects_missing_nonfinite_and_stale_snapshots() -> None:
    plant, _, measurement = _fixture(ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY)
    with pytest.raises(ValueError, match="unavailable"):
        plant.control_feedback_velocity_snapshot(
            replace(measurement, control_robot_dq_rad_s=None)
        )
    with pytest.raises(ValueError, match="nonfinite"):
        plant.control_feedback_velocity_snapshot(
            replace(
                measurement,
                control_robot_dq_rad_s=np.full(6, np.nan),
            )
        )
    with pytest.raises(ValueError, match="stale"):
        plant.control_feedback_velocity_snapshot(
            replace(measurement, arrival_time_s=measurement.arrival_time_s + 0.005001)
        )


def test_old_path_is_bitwise_preserved_when_new_path_is_disabled() -> None:
    plant, _, measurement = _fixture(PROCESSED_POSE_HISTORY_VELOCITY)
    historical = replace(
        measurement,
        attachment_velocity_m_s=np.array([0.012, -0.034, 0.056]),
        control_robot_q_rad=None,
        control_robot_dq_rad_s=None,
        control_velocity_sample_time_s=None,
    )
    selected = plant.control_feedback_velocity_snapshot(historical)
    np.testing.assert_array_equal(
        selected.linear_velocity_world_m_s, historical.attachment_velocity_m_s
    )
    assert selected.source == PROCESSED_POSE_HISTORY_VELOCITY


def test_screening_filter_supervisor_and_execution_share_new_velocity_snapshot() -> None:
    plant, _, measurement = _fixture(ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY)
    measurement = replace(
        measurement,
        attachment_velocity_m_s=np.array([0.4, -0.3, 0.2]),
    )
    model, state = _model_state(measurement)
    reference = teaching_reference(0.0)
    allocator = default_engineering_cuff_allocator()
    target_velocity, _ = model.geometry.cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    control_velocity = plant.robot_joint_control_velocity_snapshot(
        measurement
    ).linear_velocity_world_m_s
    expected_raw_force = DEFAULT_LOW_LEVEL_COMMAND_GAINS.velocity_ns_per_m * (
        target_velocity - control_velocity
    )

    direct = preview_stage4_executable_command(
        plant=plant,
        measurement=measurement,
        action_nm=np.zeros(2),
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    screening = make_stage4_first_action_batch_preview(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )(np.zeros((1, 2))).command(0)
    filtered_context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    ).command_context

    np.testing.assert_array_equal(direct.command.raw_force_velocity_n, expected_raw_force)
    np.testing.assert_array_equal(screening.raw_force_velocity_n, expected_raw_force)
    np.testing.assert_array_equal(
        filtered_context.raw_force_velocity_n, expected_raw_force
    )
    np.testing.assert_array_equal(
        direct.command.moment_angular_velocity_nm,
        DEFAULT_LOW_LEVEL_COMMAND_GAINS.angular_velocity_nms_per_rad
        * (
            model.geometry.cuff_velocity(reference.q_rad, reference.dq_rad_s)[1]
            - measurement.attachment_angular_velocity_rad_s
        ),
    )
    plant.apply_executable_command(direct.command)
    np.testing.assert_array_equal(plant.last_force, direct.command.force_total_n)


def test_new_velocity_is_sampled_once_per_200hz_command_period() -> None:
    summary, trace = run_sensor_realism_case(
        sensor_realism_cases()[0],
        duration_s=0.10,
        plant_factory=lambda human: SensorBoundaryStage4Plant(
            human,
            attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            translational_velocity_feedback_source=(
                ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
            ),
        ),
    )
    assert summary["mechanically_completed_requested_duration"]
    assert (
        summary["measurement_routing"][
            "translational_velocity_feedback_source"
        ]
        == ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
    )
    control_time = trace["control_time_s"]
    sample_time = trace["control_velocity_sample_time_s"]
    np.testing.assert_allclose(np.diff(control_time), 0.005, atol=1.0e-12)
    np.testing.assert_array_equal(sample_time, control_time)
    np.testing.assert_allclose(
        trace["control_velocity_selected_world_m_s"],
        trace["control_velocity_joint_jacobian_world_m_s"],
        atol=0.0,
        rtol=0.0,
    )
