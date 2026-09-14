from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from traction_mpc_stage5.controller_interface import EstimatedInterfaceState
from traction_mpc_stage5.hold_stabilizer import (
    BumplessExecutableReferenceHandoff,
    BumplessLoadedHoldHandoff,
    LoadedEquilibriumHoldStabilizer,
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    human_cuff_wrench_to_robot_cuff_command,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from traction_mpc_stage5.task_observation import make_task_observation


def _registered_model():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    measurement = plant.reset(np.asarray(spec.start_return_target_rad))
    return FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    ).model


def _controller_inputs(equilibrium):
    state = np.concatenate([equilibrium.q_goal_rad, np.zeros(2)])
    observation = make_task_observation(
        state,
        sample_timestamp_s=1.0,
        controller_timestamp_s=1.0,
        human_model_version="fixed-test-model",
    )
    interface = EstimatedInterfaceState(
        sample_timestamp_s=1.0,
        displacement_human_m=equilibrium.interface_displacement_human_m.copy(),
        velocity_human_m_s=np.zeros(3),
        rotation_error_human_rad=equilibrium.interface_rotation_error_human_rad.copy(),
        angular_velocity_human_rad_s=np.zeros(3),
        human_position_world_m=equilibrium.human_cuff_pose_world.translation.copy(),
        human_rotation_world=equilibrium.human_cuff_pose_world.rotation.copy(),
        human_velocity_world_m_s=np.zeros(3),
        human_angular_velocity_world_rad_s=np.zeros(3),
        measured_force_world_n=equilibrium.physical_human_wrench_world[:3].copy(),
        measured_moment_world_nm=equilibrium.physical_human_wrench_world[3:].copy(),
    )
    return observation, interface


def test_loaded_equilibrium_closes_human_interface_and_robot_pose() -> None:
    model = _registered_model()
    equilibrium = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        model,
        default_engineering_cuff_allocator(),
    )
    rotation = equilibrium.human_cuff_pose_world.rotation
    force_human = rotation.T @ equilibrium.physical_human_wrench_world[:3]
    np.testing.assert_allclose(
        25000.0 * equilibrium.interface_displacement_human_m,
        force_human,
        atol=1.0e-9,
    )
    displacement_world = rotation @ equilibrium.interface_displacement_human_m
    np.testing.assert_allclose(
        equilibrium.robot_cuff_pose_world.translation,
        equilibrium.human_cuff_pose_world.translation + displacement_world,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        equilibrium.required_human_generalized_input_nm,
        model.inverse_dynamics(
            equilibrium.q_goal_rad, np.zeros(2), np.zeros(2)
        ),
        atol=1.0e-12,
    )


def test_local_stabilizer_preserves_nonzero_support_at_equilibrium() -> None:
    model = _registered_model()
    equilibrium = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        model,
        default_engineering_cuff_allocator(),
    )
    observation, interface = _controller_inputs(equilibrium)
    action, reference, diagnostics = LoadedEquilibriumHoldStabilizer(
        equilibrium, model
    ).command(observation, interface)
    np.testing.assert_allclose(
        action, equilibrium.required_human_generalized_input_nm, atol=1.0e-12
    )
    np.testing.assert_allclose(diagnostics["desired_acceleration_rad_s2"], 0.0)
    np.testing.assert_allclose(
        reference.world_from_cuff.translation,
        equilibrium.robot_cuff_pose_world.translation,
        atol=1.0e-12,
    )
    assert diagnostics["uses_human_truth"] is False
    assert diagnostics["supporting_wrench_is_feedforward_not_feedback"] is True


def test_handoff_initial_reference_reproduces_previous_executable_wrench() -> None:
    model = _registered_model()
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, model, allocator
    )
    stabilizer = LoadedEquilibriumHoldStabilizer(equilibrium, model)
    handoff = BumplessLoadedHoldHandoff(stabilizer)
    observation, interface = _controller_inputs(equilibrium)
    measured_position = equilibrium.robot_cuff_pose_world.translation + np.array(
        [0.001, -0.0005, 0.0002]
    )
    measured_rotation = equilibrium.robot_cuff_pose_world.rotation
    measured_velocity = np.array([0.02, -0.01, 0.005])
    measured_omega = np.array([0.01, -0.02, 0.015])
    measurement = SimpleNamespace(
        attachment_position_m=measured_position,
        attachment_rotation_matrix=measured_rotation,
        attachment_velocity_m_s=measured_velocity,
        attachment_angular_velocity_rad_s=measured_omega,
    )
    action, _, _ = stabilizer.command(observation, interface)
    allocated_human = np.asarray(
        allocator.allocate(action, equilibrium.q_goal_rad, model)["wrench_world"]
    )
    allocated = human_cuff_wrench_to_robot_cuff_command(
        allocated_human,
        measured_position - interface.human_position_world_m,
    )
    previous = allocated + np.array([3.0, -2.0, 1.0, 0.4, -0.3, 0.2])
    handoff.activate(
        measurement=measurement,
        observation=observation,
        interface_state=interface,
        cuff_allocator=allocator,
        previous_executable_wrench_world=previous,
    )
    reference = handoff._reference()
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    reconstructed_force = (
        allocated[:3]
        + gains.position_n_per_m * (reference.world_from_cuff.translation - measured_position)
        - gains.velocity_ns_per_m * measured_velocity
    )
    orientation_error = Rotation.from_matrix(
        reference.world_from_cuff.rotation @ measured_rotation.T
    ).as_rotvec()
    reconstructed_moment = (
        allocated[3:]
        + gains.orientation_nm_per_rad * orientation_error
        - gains.angular_velocity_nms_per_rad * measured_omega
    )
    np.testing.assert_allclose(reconstructed_force, previous[:3], atol=1.0e-10)
    np.testing.assert_allclose(reconstructed_moment, previous[3:], atol=1.0e-10)


def test_generic_executable_reference_handoff_starts_from_previous_wrench() -> None:
    model = _registered_model()
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, model, allocator
    )
    stabilizer = LoadedEquilibriumHoldStabilizer(equilibrium, model)
    observation, interface = _controller_inputs(equilibrium)
    action, desired_reference, _ = stabilizer.command(observation, interface)
    measured_velocity = np.array([0.02, -0.01, 0.005])
    measured_omega = np.array([0.01, -0.02, 0.015])
    measurement = SimpleNamespace(
        attachment_position_m=equilibrium.robot_cuff_pose_world.translation.copy(),
        attachment_rotation_matrix=equilibrium.robot_cuff_pose_world.rotation.copy(),
        attachment_angular_velocity_rad_s=measured_omega,
    )
    plant = SimpleNamespace(
        control_feedback_velocity_snapshot=lambda _: SimpleNamespace(
            linear_velocity_world_m_s=measured_velocity
        )
    )
    previous = equilibrium.robot_site_support_wrench_world + np.array(
        [4.0, -3.0, 2.0, 0.4, -0.3, 0.2]
    )
    handoff = BumplessExecutableReferenceHandoff()
    handoff.activate(previous)
    reference, diagnostics = handoff.reference(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface,
        action_nm=action,
        human_model=model,
        cuff_allocator=allocator,
        desired_reference=desired_reference,
    )
    allocated_human = np.asarray(
        allocator.allocate(action, equilibrium.q_goal_rad, model)["wrench_world"]
    )
    allocated = human_cuff_wrench_to_robot_cuff_command(
        allocated_human,
        measurement.attachment_position_m - interface.human_position_world_m,
    )
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    reconstructed_force = (
        allocated[:3]
        + gains.position_n_per_m
        * (
            reference.world_from_cuff.translation
            - measurement.attachment_position_m
        )
        - gains.velocity_ns_per_m * measured_velocity
    )
    orientation_error = Rotation.from_matrix(
        reference.world_from_cuff.rotation
        @ measurement.attachment_rotation_matrix.T
    ).as_rotvec()
    reconstructed_moment = (
        allocated[3:]
        + gains.orientation_nm_per_rad * orientation_error
        - gains.angular_velocity_nms_per_rad * measured_omega
    )
    assert diagnostics["alpha"] == 0.0
    np.testing.assert_allclose(reconstructed_force, previous[:3], atol=1.0e-10)
    np.testing.assert_allclose(reconstructed_moment, previous[3:], atol=1.0e-10)
