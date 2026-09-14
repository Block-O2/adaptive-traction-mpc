from __future__ import annotations

import numpy as np

from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from traction_mpc_stage5.controller_interface import InterfaceAwareHumanStateObserver
from traction_mpc_stage5.goal_mpc import support_action
from traction_mpc_stage5.hold_stabilizer import (
    initialize_plant_at_loaded_equilibrium,
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    build_stage5_loaded_execution_context,
    future_loaded_command_wrench_batch,
    human_cuff_wrench_to_robot_cuff_command,
    loaded_execution_target_from_equilibrium,
)
from traction_mpc_stage5.loaded_supervisor import Stage5LoadedTrackBrakeSupervisor
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


MODEL_VERSION = "stage5_fixed_registered_human_v1"


def _loaded_context():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    unloaded = plant.reset(np.asarray(spec.start_return_target_rad))
    model = FixedStage5Estimator(
        unloaded.attachment_position_m,
        unloaded.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    ).model
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(
        spec,
        model,
        allocator,
        target_q_rad=np.asarray(spec.start_return_target_rad),
    )
    truth = initialize_plant_at_loaded_equilibrium(
        plant, model, equilibrium
    )
    measurement = CausalMeasurementLayer(
        MeasurementCase(
            name="loaded-execution-test", update_rate_hz=200.0, latency_s=0.0
        ),
        truth,
    ).current
    observation, interface = InterfaceAwareHumanStateObserver().update(
        measurement,
        model,
        human_model_version=MODEL_VERSION,
    )
    target = loaded_execution_target_from_equilibrium(equilibrium, model)
    context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface,
        human_model=model,
        cuff_allocator=allocator,
        target=target,
    )
    return (
        plant,
        measurement,
        model,
        allocator,
        equilibrium,
        observation,
        interface,
        target,
        context,
    )


def test_wrench_reference_point_transform_preserves_physical_wrench() -> None:
    wrench_human = np.array([12.0, -3.0, 25.0, 1.0, 4.0, -2.0])
    robot_from_human = np.array([0.02, -0.01, 0.04])
    wrench_robot = human_cuff_wrench_to_robot_cuff_command(
        wrench_human, robot_from_human
    )
    np.testing.assert_allclose(wrench_robot[:3], wrench_human[:3])
    np.testing.assert_allclose(
        wrench_robot[3:] + np.cross(robot_from_human, wrench_robot[:3]),
        wrench_human[3:],
    )


def test_loaded_support_uses_robot_target_without_unloading_feedback() -> None:
    _, _, model, _, equilibrium, observation, _, target, context = _loaded_context()
    action = support_action(observation.as_array(), model)
    command = context.preview_command_batch(action[np.newaxis, :]).command(0)
    np.testing.assert_allclose(command.force_position_n, 0.0, atol=1.0e-9)
    np.testing.assert_allclose(command.force_velocity_n, 0.0, atol=1.0e-9)
    np.testing.assert_allclose(command.moment_orientation_nm, 0.0, atol=1.0e-9)
    np.testing.assert_allclose(command.moment_angular_velocity_nm, 0.0, atol=1.0e-9)
    np.testing.assert_allclose(
        context.target.robot_cuff_target.world_from_cuff.translation,
        equilibrium.robot_cuff_pose_world.translation,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        command.wrench_total_world,
        target.support_robot_cuff_command_wrench_world,
        atol=1.0e-9,
    )


def test_future_loaded_support_command_matches_same_reference_point_law() -> None:
    _, _, model, _, _, observation, interface, target, _ = _loaded_context()
    state = observation.as_array()[np.newaxis, :]
    command = future_loaded_command_wrench_batch(
        states=state,
        total_human_cuff_wrenches_world=(
            target.support_human_cuff_wrench_world[np.newaxis, :]
        ),
        support_human_cuff_wrenches_world=(
            target.support_human_cuff_wrench_world[np.newaxis, :]
        ),
        interface_displacement_human_m=(
            interface.displacement_human_m[np.newaxis, :]
        ),
        interface_velocity_human_m_s=(
            interface.velocity_human_m_s[np.newaxis, :]
        ),
        interface_rotation_human_rad=(
            interface.rotation_error_human_rad[np.newaxis, :]
        ),
        interface_angular_velocity_human_rad_s=(
            interface.angular_velocity_human_rad_s[np.newaxis, :]
        ),
        human_rotation_world=interface.human_rotation_world[np.newaxis, :, :],
    )
    np.testing.assert_allclose(
        command[0], target.support_robot_cuff_command_wrench_world, atol=1.0e-9
    )


def test_brake_preview_ignores_inherited_unloaded_reference_authority() -> None:
    (
        plant,
        measurement,
        model,
        allocator,
        _,
        observation,
        interface,
        target,
        _,
    ) = _loaded_context()
    supervisor = Stage5LoadedTrackBrakeSupervisor()
    supervisor.bind_loaded_execution(observation, interface, target)
    state = observation.as_array()
    q = state[:2]
    dq = state[2:]
    action = support_action(state, model)
    inherited_unloaded_reference = CuffPoseReference(
        q_rad=q.copy(),
        dq_rad_s=dq.copy(),
        ddq_rad_s2=np.zeros(2, dtype=float),
        world_from_cuff=model.geometry.cuff_pose(q),
    )
    preview = supervisor._preview(
        plant=plant,
        measurement=measurement,
        estimated_state=observation.as_array(),
        human_model=model,
        cuff_allocator=allocator,
        action_nm=action,
        reference=inherited_unloaded_reference,
    )
    np.testing.assert_allclose(preview.command.force_position_n, 0.0, atol=1.0e-9)
    np.testing.assert_allclose(
        preview.command.moment_orientation_nm, 0.0, atol=1.0e-9
    )
    np.testing.assert_allclose(
        preview.command.wrench_total_world,
        target.support_robot_cuff_command_wrench_world,
        atol=1.0e-9,
    )
