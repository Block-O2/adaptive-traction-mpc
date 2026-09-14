from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage5.acceleration import (
    CausalModelAccelerationMonitor,
    MODEL_WRENCH_INSTANTANEOUS_ACCELERATION,
    MODEL_WRENCH_REALIZED_ACCELERATION,
    estimate_deployable_realized_acceleration,
)
from traction_mpc_stage5.baseline_replay import (
    FixedStage5Estimator,
    Stage5SensorBoundaryPlant,
)
from traction_mpc_stage5.controller_interface import InterfaceAwareHumanStateObserver
from traction_mpc_stage5.controller_interface import EstimatedInterfaceState
from traction_mpc_stage5.hold_stabilizer import (
    initialize_plant_at_loaded_equilibrium,
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from traction_mpc_stage5.task_observation import make_task_observation


def _loaded_acceleration_sample():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    unloaded = plant.reset(np.asarray(spec.start_return_target_rad))
    model = FixedStage5Estimator(
        unloaded.attachment_position_m,
        unloaded.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    ).model
    equilibrium = solve_loaded_hold_equilibrium(
        spec,
        model,
        default_engineering_cuff_allocator(),
        target_q_rad=np.asarray(spec.start_return_target_rad),
    )
    truth = initialize_plant_at_loaded_equilibrium(plant, model, equilibrium)
    measurement = CausalMeasurementLayer(
        MeasurementCase("acceleration-test", 200.0, 0.0), truth
    ).current
    observation, interface = InterfaceAwareHumanStateObserver().update(
        measurement,
        model,
        human_model_version="stage5_fixed_registered_human_v1",
    )
    return model, equilibrium, observation, interface


def test_loaded_equilibrium_model_wrench_acceleration_is_zero() -> None:
    model, equilibrium, observation, interface = _loaded_acceleration_sample()
    estimate = estimate_deployable_realized_acceleration(
        observation, interface, model
    )
    assert estimate.source == MODEL_WRENCH_INSTANTANEOUS_ACCELERATION
    np.testing.assert_allclose(
        estimate.generalized_human_input_nm,
        equilibrium.required_human_generalized_input_nm,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(estimate.acceleration_rad_s2, 0.0, atol=1.0e-9)


def test_acceleration_is_current_model_result_without_velocity_history() -> None:
    model, _, observation, interface = _loaded_acceleration_sample()
    first = estimate_deployable_realized_acceleration(observation, interface, model)
    second = estimate_deployable_realized_acceleration(observation, interface, model)
    expected = model.continuous_dynamics(
        observation.as_array(), first.generalized_human_input_nm
    )[2:]
    np.testing.assert_allclose(first.acceleration_rad_s2, expected)
    np.testing.assert_array_equal(second.acceleration_rad_s2, first.acceleration_rad_s2)


def test_acceleration_rejects_misaligned_state_and_wrench_timestamps() -> None:
    model, _, observation, interface = _loaded_acceleration_sample()
    with pytest.raises(ValueError, match="share one sample timestamp"):
        estimate_deployable_realized_acceleration(
            observation,
            replace(interface, sample_timestamp_s=interface.sample_timestamp_s + 0.005),
            model,
        )


def test_causal_monitor_uses_only_trailing_20ms_model_acceleration() -> None:
    class Geometry:
        @staticmethod
        def generalized_input_from_wrench(q, force, moment):
            del q, moment
            return np.asarray(force[:2], dtype=float)

    class Model:
        geometry = Geometry()

        @staticmethod
        def continuous_dynamics(state, action):
            return np.concatenate([np.asarray(state)[2:], np.asarray(action)])

    monitor = CausalModelAccelerationMonitor(interval_s=0.020)
    outputs = []
    for index in range(6):
        time_s = 0.005 * index
        observation = make_task_observation(
            np.zeros(4),
            sample_timestamp_s=time_s,
            controller_timestamp_s=time_s,
            human_model_version="test-model",
        )
        zeros = np.zeros(3)
        interface = EstimatedInterfaceState(
            sample_timestamp_s=time_s,
            displacement_human_m=zeros.copy(),
            velocity_human_m_s=zeros.copy(),
            rotation_error_human_rad=zeros.copy(),
            angular_velocity_human_rad_s=zeros.copy(),
            human_position_world_m=zeros.copy(),
            human_rotation_world=np.eye(3),
            human_velocity_world_m_s=zeros.copy(),
            human_angular_velocity_world_rad_s=zeros.copy(),
            measured_force_world_n=np.array([index, 2.0 * index, 0.0]),
            measured_moment_world_nm=zeros.copy(),
        )
        outputs.append(monitor.update(observation, interface, Model()))
    np.testing.assert_allclose(outputs[4].acceleration_rad_s2, [2.0, 4.0])
    np.testing.assert_allclose(outputs[5].acceleration_rad_s2, [3.0, 6.0])
    assert outputs[5].source == MODEL_WRENCH_REALIZED_ACCELERATION
    assert outputs[5].interval_start_timestamp_s == pytest.approx(0.005)
    np.testing.assert_allclose(outputs[4].acceleration_rad_s2, [2.0, 4.0])
