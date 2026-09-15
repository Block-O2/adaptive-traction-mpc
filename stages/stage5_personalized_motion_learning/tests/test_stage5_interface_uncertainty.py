from __future__ import annotations

from dataclasses import replace

import numpy as np

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage5.acceleration import DeployableRealizedAcceleration
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from traction_mpc_stage5.controller_interface import EstimatedInterfaceState
from traction_mpc_stage5.hold_stabilizer import (
    initialize_plant_at_loaded_equilibrium,
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.interface_uncertainty import (
    InterfaceHypothesisEstimate,
    InterfaceUncertaintyEstimate,
    InterfaceUncertaintyMonitor,
    build_interface_hypotheses,
    load_interface_uncertainty_spec,
    start_episode_uncertainty_aware,
    transition_phase_uncertainty_aware,
    uncertainty_motion_violation,
)
from traction_mpc_stage5.task import (
    PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
)
from traction_mpc_stage5.task_observation import make_task_observation


def _loaded_measurement():
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    unloaded = plant.reset(np.asarray(task.start_return_target_rad))
    model = FixedStage5Estimator(
        unloaded.attachment_position_m,
        unloaded.attachment_rotation_matrix,
        np.asarray(task.start_return_target_rad),
    ).model
    equilibrium = solve_loaded_hold_equilibrium(
        task,
        model,
        default_engineering_cuff_allocator(),
        target_q_rad=np.asarray(task.start_return_target_rad),
    )
    truth = initialize_plant_at_loaded_equilibrium(plant, model, equilibrium)
    measurement = CausalMeasurementLayer(
        MeasurementCase("uncertainty-test", 200.0, 0.0), truth
    ).current
    return model, measurement


def _synthetic_estimate(accelerations_deg_s2: list[list[float]]):
    samples = []
    for index, acceleration_deg_s2 in enumerate(accelerations_deg_s2):
        observation = make_task_observation(
            np.radians([5.0, 10.0, 0.0, 0.0]),
            sample_timestamp_s=0.0,
            controller_timestamp_s=0.0,
            human_model_version="test",
        )
        zeros = np.zeros(3)
        interface = EstimatedInterfaceState(
            sample_timestamp_s=0.0,
            displacement_human_m=zeros,
            velocity_human_m_s=zeros,
            rotation_error_human_rad=zeros,
            angular_velocity_human_rad_s=zeros,
            human_position_world_m=zeros,
            human_rotation_world=np.eye(3),
            human_velocity_world_m_s=zeros,
            human_angular_velocity_world_rad_s=zeros,
            measured_force_world_n=zeros,
            measured_moment_world_nm=zeros,
        )
        acceleration = np.radians(acceleration_deg_s2)
        model_acceleration = DeployableRealizedAcceleration(
            sample_timestamp_s=0.0,
            interval_start_timestamp_s=0.0,
            generalized_human_input_nm=np.zeros(2),
            acceleration_rad_s2=acceleration,
            instantaneous_acceleration_rad_s2=acceleration,
        )
        samples.append(
            InterfaceHypothesisEstimate(
                name="nominal" if index == 0 else f"corner-{index}",
                observation=observation,
                interface_state=interface,
                model_acceleration=model_acceleration,
                causal_dq_acceleration_rad_s2=np.zeros(2),
                causal_dq_acceleration_available=False,
            )
        )
    return InterfaceUncertaintyEstimate(
        sample_timestamp_s=0.0,
        hypotheses=tuple(samples),
        method="test",
    )


def test_uncertainty_config_builds_nominal_plus_eight_box_corners() -> None:
    spec = load_interface_uncertainty_spec()
    hypotheses = build_interface_hypotheses(spec)
    assert len(hypotheses) == 9
    assert hypotheses[0][0] == "nominal"
    assert spec.translation_stiffness_scale_range == (0.9, 1.1)
    assert spec.rotation_stiffness_scale_range == (0.9, 1.1)
    assert spec.joint_damping_scale_range == (0.8, 1.2)
    assert spec.empirical_range_not_guaranteed_bound
    assert not spec.hardware_calibrated_confidence_interval


def test_nominal_loaded_start_is_valid_for_all_limited_hypotheses() -> None:
    model, measurement = _loaded_measurement()
    estimate = InterfaceUncertaintyMonitor(load_interface_uncertainty_spec()).update(
        measurement,
        model,
        human_model_version="test",
    )
    state = start_episode_uncertainty_aware(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, estimate
    )
    assert state.start_validated
    assert not estimate.truth_used


def test_any_hypothesis_acceleration_violation_is_not_silently_safe() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    estimate = _synthetic_estimate([[100.0, 200.0], [100.0, 601.0]])
    assert (
        uncertainty_motion_violation(task, estimate)
        == "INTERFACE_UNCERTAINTY_ACCELERATION_LIMIT"
    )


def test_registered_limits_are_not_changed_by_uncertainty_monitor() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    original_velocity = task.task_joint_velocity_limit_rad_s
    original_acceleration = task.task_joint_acceleration_limit_rad_s2
    estimate = _synthetic_estimate([[100.0, 200.0], [120.0, 300.0]])
    assert uncertainty_motion_violation(task, estimate) is None
    assert task.task_joint_velocity_limit_rad_s == original_velocity
    assert task.task_joint_acceleration_limit_rad_s2 == original_acceleration


def test_any_hypothesis_velocity_violation_is_not_silently_safe() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    estimate = _synthetic_estimate([[100.0, 200.0], [100.0, 200.0]])
    fast_observation = make_task_observation(
        np.radians([5.0, 10.0, 46.0, 0.0]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="test",
    )
    estimate = replace(
        estimate,
        hypotheses=(
            estimate.hypotheses[0],
            replace(estimate.hypotheses[1], observation=fast_observation),
        ),
    )
    assert (
        uncertainty_motion_violation(task, estimate)
        == "INTERFACE_UNCERTAINTY_VELOCITY_LIMIT"
    )


def test_phase_transition_waits_for_every_hypothesis_completion_set() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start_estimate = _synthetic_estimate([[0.0, 0.0], [0.0, 0.0]])
    state = start_episode_uncertainty_aware(task, start_estimate)
    nominal_goal = make_task_observation(
        np.radians([20.0, 35.0, 0.0, 0.0]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="test",
    )
    uncertain_outside = make_task_observation(
        np.radians([20.0, 33.0, 0.0, 0.0]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="test",
    )
    estimate = replace(
        start_estimate,
        hypotheses=(
            replace(start_estimate.hypotheses[0], observation=nominal_goal),
            replace(start_estimate.hypotheses[1], observation=uncertain_outside),
        ),
    )
    next_state = transition_phase_uncertainty_aware(
        task,
        state,
        estimate,
        0.005,
        completion_margin=PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
    )
    assert next_state.phase is state.phase
