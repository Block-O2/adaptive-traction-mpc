from __future__ import annotations

from dataclasses import replace

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.evaluation import Stage4CoupledPlant
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.sensor_realism import (
    MeasurementRouting,
    SensorBoundaryStage4Plant,
    _extrapolate_measurement_to_arrival,
    run_sensor_realism_case,
)


def test_ideal_measurement_layer_is_an_exact_robot_cuff_pass_through() -> None:
    plant = Stage4CoupledPlant()
    truth = plant.reset(np.radians([5.0, 10.0]))
    layer = CausalMeasurementLayer(sensor_realism_cases()[0], truth)
    measured = layer.current
    np.testing.assert_array_equal(measured.robot_q_rad, truth.robot_q_rad)
    np.testing.assert_array_equal(measured.robot_dq_rad_s, truth.robot_dq_rad_s)
    np.testing.assert_array_equal(
        measured.attachment_position_m, truth.attachment_position_m
    )
    np.testing.assert_array_equal(
        measured.attachment_rotation_matrix, truth.attachment_rotation_matrix
    )
    np.testing.assert_array_equal(
        measured.cuff_force_vector_n, truth.cuff_force_vector_n
    )
    assert not hasattr(measured, "human_q_rad")
    assert not hasattr(measured, "bed_force_n")


def test_common_delay_holds_aligned_measurement_timestamp() -> None:
    plant = Stage4CoupledPlant()
    truth = plant.reset(np.radians([5.0, 10.0]))
    delayed = replace(sensor_realism_cases()[3], noise=type(sensor_realism_cases()[3].noise)())
    layer = CausalMeasurementLayer(delayed, truth)
    for _ in range(5):
        truth = plant.step()
    measurement = layer.update(truth)
    assert measurement.sample_time_s == 0.0
    assert measurement.age_s == truth.time_s
    for _ in range(5):
        truth = plant.step()
    measurement = layer.update(truth)
    assert np.isclose(measurement.age_s, delayed.latency_s)


def test_short_ideal_sensor_boundary_rollout_is_finite() -> None:
    summary, trace = run_sensor_realism_case(sensor_realism_cases()[0], duration_s=0.10)
    assert summary["mechanically_completed_requested_duration"]
    assert summary["controller_or_estimator_clean_mujoco_truth_access"] is False
    assert summary["events"]["mujoco_warning_counts"] == {}
    assert summary["events"]["unintended_contact_pairs"] == []
    assert all(np.all(np.isfinite(value)) for value in trace.values())


def test_ideal_measured_low_level_law_matches_validated_stage4_law() -> None:
    original = SensorBoundaryStage4Plant(HUMAN)
    measured_plant = SensorBoundaryStage4Plant(HUMAN)
    q0 = np.radians([5.0, 10.0])
    original_truth = original.reset(q0)
    measured_truth = measured_plant.reset(q0)
    layer = CausalMeasurementLayer(sensor_realism_cases()[0], measured_truth)
    target_position = original_truth.attachment_position_m + np.array([1e-4, -2e-4, 1e-4])
    target_velocity = np.array([0.002, -0.001, 0.003])
    target_rotation = original_truth.attachment_rotation_matrix
    target_angular_velocity = np.array([0.0, 0.01, 0.0])
    feedforward = np.array([5.0, -3.0, 2.0, 0.1, -0.2, 0.3])
    original.apply_nominal_cartesian_control(
        target_position,
        target_velocity,
        target_rotation,
        target_angular_velocity,
        feedforward,
    )
    measured_plant.apply_measured_nominal_cartesian_control(
        layer.current,
        target_position,
        target_velocity,
        target_rotation,
        target_angular_velocity,
        feedforward,
    )
    np.testing.assert_allclose(
        measured_plant.last_unclipped_joint_torque,
        original.last_unclipped_joint_torque,
        atol=1e-10,
        rtol=1e-10,
    )


def test_timestamp_extrapolation_advances_pose_and_robot_state_only() -> None:
    plant = Stage4CoupledPlant()
    truth = plant.reset(np.radians([5.0, 10.0]))
    delayed = replace(sensor_realism_cases()[0], latency_s=0.010)
    layer = CausalMeasurementLayer(delayed, truth)
    for _ in range(10):
        truth = plant.step()
    measured = layer.update(truth)
    predicted = _extrapolate_measurement_to_arrival(measured)
    assert np.isclose(measured.age_s, 0.010)
    assert predicted.age_s == 0.0
    np.testing.assert_allclose(
        predicted.robot_q_rad,
        measured.robot_q_rad + 0.010 * measured.robot_dq_rad_s,
    )
    np.testing.assert_allclose(
        predicted.attachment_position_m,
        measured.attachment_position_m
        + 0.010 * measured.attachment_velocity_m_s,
    )
    np.testing.assert_array_equal(
        predicted.cuff_force_vector_n, measured.cuff_force_vector_n
    )


def test_independent_measurement_routing_is_reported() -> None:
    routing = MeasurementRouting(
        estimator_delay_s=0.010,
        mpc_state_delay_s=0.0,
        low_level_delay_s=0.0,
    )
    summary, _ = run_sensor_realism_case(
        sensor_realism_cases()[1],
        duration_s=0.10,
        estimator_architecture="integral_minimal",
        measurement_routing=routing,
        result_case_name="estimator_delay_only_short",
    )
    assert summary["mechanically_completed_requested_duration"]
    assert summary["case"] == "estimator_delay_only_short"
    assert summary["measurement_routing"] == {
        "estimator_delay_ms": 10.0,
        "mpc_state_delay_ms": 0.0,
        "low_level_delay_ms": 0.0,
        "low_level_timestamp_extrapolation": False,
    }
