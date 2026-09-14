from __future__ import annotations

import inspect
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from traction_mpc_stage3.executable_command import ExecutableCommandBatchPreview
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    EstimatedInterfaceState,
    InterfaceAwareFirstActionBatchPreview,
    InterfaceAwareHumanStateObserver,
    NominalInterfaceHoldPredictor,
)
from traction_mpc_stage5.goal_mpc import GoalDirectedHumanSpaceMPC
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.task import (
    GoalTaskState,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
    start_episode,
)


def _batch(force_world_n: np.ndarray) -> ExecutableCommandBatchPreview:
    force = np.atleast_2d(np.asarray(force_world_n, dtype=float))
    count = len(force)
    vectors = np.zeros((count, 3))
    torques = np.zeros((count, 6))
    return ExecutableCommandBatchPreview(
        force_position_n=vectors.copy(),
        force_velocity_n=vectors.copy(),
        force_allocator_n=force.copy(),
        force_total_n=force.copy(),
        raw_force_position_n=vectors.copy(),
        raw_force_velocity_n=vectors.copy(),
        feedback_force_before_clipping_n=vectors.copy(),
        feedback_force_after_clipping_n=vectors.copy(),
        feedback_force_clipping_delta_n=vectors.copy(),
        moment_orientation_nm=vectors.copy(),
        moment_angular_velocity_nm=vectors.copy(),
        moment_allocator_nm=vectors.copy(),
        moment_total_nm=vectors.copy(),
        translational_force_norm_n=np.linalg.norm(force, axis=1),
        margin_to_force_gate_n=200.0 - np.linalg.norm(force, axis=1),
        feasible=np.ones(count, dtype=bool),
        robot_attachment_jacobian=np.zeros((6, 6)),
        unclipped_joint_torque_nm=torques.copy(),
        joint_torque_command_nm=torques.copy(),
        control_dt_s=0.005,
    )


def test_controller_nominal_interface_is_an_independent_config_boundary() -> None:
    assert CONTROLLER_NOMINAL_INTERFACE.translation_stiffness_n_m == (
        25000.0,
        25000.0,
        25000.0,
    )
    assert CONTROLLER_NOMINAL_INTERFACE is not STAGE5_RIGID_INTERFACE
    source = inspect.getsource(
        __import__(
            "traction_mpc_stage5.controller_interface", fromlist=["unused"]
        )
    )
    assert "STAGE5_RIGID_INTERFACE" not in source
    assert "plant.interface_parameters" not in source


def test_interface_aware_observer_uses_deployable_measurement_and_matches_reset() -> None:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad))
    measurement = CausalMeasurementLayer(
        MeasurementCase(name="observer-test", update_rate_hz=200.0, latency_s=0.0),
        truth,
    ).current
    # The registered fixed estimator provides controller geometry; its Human
    # truth fields are used only below as an evaluation assertion.
    from traction_mpc_stage5.baseline_replay import FixedStage5Estimator

    estimator = FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    observation, interface = InterfaceAwareHumanStateObserver().update(
        measurement,
        estimator.model,
        human_model_version="fixed-test-model",
    )
    np.testing.assert_allclose(
        observation.as_array()[:2], truth.human_q_rad, atol=np.radians(0.01)
    )
    assert interface.sample_timestamp_s == measurement.sample_time_s


def test_hold_predictor_batches_and_catches_physical_transient() -> None:
    parameters = CONTROLLER_NOMINAL_INTERFACE
    displacement = np.array([190.0 / parameters.translation_stiffness_n_m[0], 0.0, 0.0])
    state = EstimatedInterfaceState(
        sample_timestamp_s=1.0,
        displacement_human_m=displacement,
        velocity_human_m_s=np.zeros(3),
        rotation_error_human_rad=np.zeros(3),
        angular_velocity_human_rad_s=np.zeros(3),
        human_position_world_m=np.zeros(3),
        human_rotation_world=np.eye(3),
        human_velocity_world_m_s=np.zeros(3),
        human_angular_velocity_world_rad_s=np.zeros(3),
        measured_force_world_n=np.array([190.0, 0.0, 0.0]),
        measured_moment_world_nm=np.zeros(3),
    )
    executable = _batch(np.array([[199.0, 0.0, 0.0], [0.0, 0.0, 0.0]]))
    result = NominalInterfaceHoldPredictor(control_dt_s=0.020).predict_batch(
        state, executable
    )
    assert result.feasible.shape == (2,)
    assert executable.feasible[0]
    assert result.predicted_peak_force_n[0] > 200.0
    assert not result.feasible[0]
    assert result.predicted_endpoint_force_world_n.shape == (2, 3)
    assert result.predicted_mean_force_world_n.shape == (2, 3)


def test_vectorized_hold_substeps_match_legacy_semi_implicit_recurrence() -> None:
    predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    parameters = predictor.parameters
    position = np.array([[0.002, -0.001, 0.003], [-0.004, 0.002, 0.001]])
    velocity = np.array([[0.2, -0.1, 0.3], [-0.2, 0.4, -0.1]])
    drive = np.array([[60.0, -30.0, 80.0], [-90.0, 50.0, 20.0]])
    stiffness = np.asarray(parameters.translation_stiffness_n_m)
    damping = np.asarray(parameters.translation_damping_ns_m)
    mass = np.asarray(parameters.translation_effective_mass_kg)
    rest = np.asarray(parameters.rest_translation_human_m)
    actual_position, actual_velocity = predictor._constant_drive_trace(
        position,
        velocity,
        drive,
        stiffness,
        rest,
        predictor._translation_step_powers,
    )

    expected_position = []
    expected_velocity = []
    x = position.copy()
    u = velocity.copy()
    dt = parameters.prediction_substep_s
    for _ in range(predictor.substeps):
        acceleration = (drive - stiffness * (x - rest) - damping * u) / mass
        u = u + dt * acceleration
        x = x + dt * u
        expected_position.append(x.copy())
        expected_velocity.append(u.copy())

    np.testing.assert_allclose(
        actual_position,
        np.stack(expected_position, axis=1),
        atol=2.0e-15,
        rtol=2.0e-13,
    )
    np.testing.assert_allclose(
        actual_velocity,
        np.stack(expected_velocity, axis=1),
        atol=2.0e-13,
        rtol=2.0e-13,
    )


def test_explicit_prediction_state_carries_drive_across_measurement_updates() -> None:
    _, interface, _ = _registered_model_and_interface()
    predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    initial_command = np.array([10.0, -2.0, 3.0, 0.5, -0.4, 0.2])
    predictor.update_from_measurement(
        interface, previous_executable_wrench_world=initial_command
    )
    initial = predictor.explicit_state
    assert initial is not None

    next_interface = replace(
        interface,
        sample_timestamp_s=interface.sample_timestamp_s + 0.005,
        velocity_human_m_s=np.array([0.2, -0.1, 0.3]),
        angular_velocity_human_rad_s=np.array([-0.4, 0.5, -0.6]),
    )
    predictor.update_from_measurement(next_interface)
    updated = predictor.explicit_state
    assert updated is not None
    np.testing.assert_allclose(updated.base_drive_world_n, initial.base_drive_world_n)
    np.testing.assert_allclose(
        updated.base_angular_drive_world_nm,
        initial.base_angular_drive_world_nm,
    )
    np.testing.assert_allclose(
        updated.previous_executable_wrench_world, initial_command
    )
    np.testing.assert_allclose(updated.velocity_human_m_s, [0.2, -0.1, 0.3])


def test_explicit_prediction_state_updates_drive_only_by_known_command_delta() -> None:
    _, interface, _ = _registered_model_and_interface()
    predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    previous = np.array([4.0, 5.0, 6.0, -1.0, 2.0, 3.0])
    predictor.update_from_measurement(
        interface, previous_executable_wrench_world=previous
    )
    before = predictor.explicit_state
    assert before is not None
    current = np.array([5.5, 2.0, 8.0, -0.5, 1.0, 4.5])
    predictor.commit_executable_wrench(current)
    after = predictor.explicit_state
    assert after is not None
    np.testing.assert_allclose(
        after.base_drive_world_n - before.base_drive_world_n,
        current[:3] - previous[:3],
    )
    np.testing.assert_allclose(
        after.base_angular_drive_world_nm - before.base_angular_drive_world_nm,
        current[3:] - previous[3:],
    )
    np.testing.assert_allclose(after.previous_executable_wrench_world, current)


def test_predictor_rejects_stale_explicit_state_instead_of_hidden_reinference() -> None:
    _, interface, _ = _registered_model_and_interface()
    predictor = NominalInterfaceHoldPredictor(control_dt_s=0.020)
    predictor.update_from_measurement(interface)
    newer = replace(
        interface, sample_timestamp_s=interface.sample_timestamp_s + 0.005
    )
    with pytest.raises(RuntimeError, match="update_from_measurement"):
        predictor.predict_batch(newer, _batch(np.zeros((1, 3))))


def test_selected_first_action_reuses_population_screen() -> None:
    state, interface, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    calls = 0

    def executable(actions):
        nonlocal calls
        calls += 1
        return _batch(np.zeros((len(actions), 3)))

    preview = InterfaceAwareFirstActionBatchPreview(
        executable,
        NominalInterfaceHoldPredictor(control_dt_s=0.020),
        interface,
        state[:2],
        model,
        allocator,
    )
    actions = np.array([[0.0, 0.0], [1.0, -0.5], [-0.5, 1.0]])
    population = preview(actions)
    selected = preview(actions[1:2])

    assert calls == 1
    np.testing.assert_allclose(
        selected.predicted_mean_force_world_n,
        population.predicted_mean_force_world_n[1:2],
    )
    np.testing.assert_allclose(
        selected.command(0).wrench_total_world,
        population.command(1).wrench_total_world,
    )


def _registered_model_and_interface():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad))
    measurement = CausalMeasurementLayer(
        MeasurementCase(name="horizon-test", update_rate_hz=200.0, latency_s=0.0),
        truth,
    ).current
    from traction_mpc_stage5.baseline_replay import FixedStage5Estimator

    estimator = FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    observation, interface = InterfaceAwareHumanStateObserver().update(
        measurement,
        estimator.model,
        human_model_version="fixed-test-model",
    )
    return observation.as_array(), interface, estimator.model


def test_vectorized_varying_q_allocation_matches_registered_allocator() -> None:
    state, interface, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    preview = InterfaceAwareFirstActionBatchPreview(
        lambda actions: _batch(np.zeros((len(actions), 3))),
        NominalInterfaceHoldPredictor(control_dt_s=0.020),
        interface,
        state[:2],
        model,
        allocator,
    )
    q = np.radians([[5.0, 10.0], [12.0, 22.0], [20.0, 35.0]])
    actions = np.array([[0.0, 0.0], [4.0, -2.0], [-3.0, 5.0]])
    actual = preview._allocate_varying_q_batch(actions, q)
    expected = np.stack(
        [allocator.allocate(action, pose, model)["wrench_world"] for action, pose in zip(actions, q)]
    )
    np.testing.assert_allclose(actual, expected, atol=1.0e-10, rtol=1.0e-10)


def test_one_allocation_map_matches_separate_total_and_support_allocations() -> None:
    state, interface, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    preview = InterfaceAwareFirstActionBatchPreview(
        lambda actions: _batch(np.zeros((len(actions), 3))),
        NominalInterfaceHoldPredictor(control_dt_s=0.020),
        interface,
        state[:2],
        model,
        allocator,
    )
    q = np.radians([[5.0, 10.0], [12.0, 22.0], [20.0, 35.0]])
    total = np.array([[40.0, -7.0], [42.0, -5.0], [38.0, -3.0]])
    support = np.array([[39.0, -7.5], [40.0, -5.5], [39.0, -3.5]])
    jacobian, _ = preview._geometry_batch(q, model.geometry)
    mapping = preview._allocation_map_with_jacobian_batch(jacobian)

    np.testing.assert_allclose(
        np.einsum("nij,nj->ni", mapping, total),
        preview._allocate_with_jacobian_batch(total, jacobian),
        atol=1.0e-12,
        rtol=1.0e-12,
    )
    np.testing.assert_allclose(
        np.einsum("nij,nj->ni", mapping, support),
        preview._allocate_with_jacobian_batch(support, jacobian),
        atol=1.0e-12,
        rtol=1.0e-12,
    )


def test_v13_full_horizon_propagates_interface_and_transmitted_wrench() -> None:
    state, interface, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    preview = InterfaceAwareFirstActionBatchPreview(
        lambda actions: _batch(np.zeros((len(actions), 3))),
        NominalInterfaceHoldPredictor(control_dt_s=0.020),
        interface,
        state[:2],
        model,
        allocator,
    )
    sequences = np.zeros((2, 4, 2))
    sequences[1, 1:, :] = np.array([2.0, -1.0])
    mpc = GoalDirectedHumanSpaceMPC(cuff_allocator=allocator)
    result = preview.rollout_horizon(state, sequences, mpc._batched_base_step)

    assert result.predicted_human_states.shape == (2, 4, 4)
    assert result.requested_cuff_wrench_world.shape == (2, 4, 6)
    assert result.allocated_force_norm_n.shape == (2, 4)
    assert result.transmitted_mean_wrench_world.shape == (2, 4, 6)
    assert result.interface_displacement_human_m.shape == (2, 4, 3)
    assert result.base_drive_world_n.shape == (2, 4, 3)
    assert result.base_angular_drive_world_nm.shape == (2, 4, 3)
    assert result.executable_wrench_world.shape == (2, 4, 6)
    assert result.timing_s is not None
    assert set(result.timing_s) == {
        "horizon_setup",
        "support_dynamics",
        "geometry",
        "cuff_allocation",
        "loaded_execution_wrench_transforms",
        "interface_state_propagation",
        "human_dynamics_propagation",
        "rollout_bookkeeping_numpy",
    }
    assert np.all(np.isfinite(result.predicted_human_states))
    assert np.all(np.isfinite(result.transmitted_mean_wrench_world))
    np.testing.assert_allclose(result.requested_cuff_wrench_world[:, 0], 0.0)
    assert not np.allclose(
        result.predicted_human_states[0, -1],
        result.predicted_human_states[1, -1],
    )


def test_v13_hold_set_enforces_when_sampled_feasible_and_recovers_otherwise() -> None:
    state, _, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    mpc = GoalDirectedHumanSpaceMPC(cuff_allocator=allocator)
    hold = GoalTaskState(
        phase=TaskPhase.HOLD,
        phase_elapsed_s=0.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )
    mpc._set_problem(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold)
    count = 2
    horizon = mpc.config.horizon_steps
    candidates = np.zeros((count, horizon, 2))

    def coupled_with_velocity(velocity_deg_s: np.ndarray):
        predicted = np.empty((count, horizon, 4))
        predicted[..., :2] = np.asarray(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad
        )
        predicted[..., 2:] = np.radians(velocity_deg_s)[:, None, :]
        return SimpleNamespace(
            predicted_human_states=predicted,
            predicted_peak_force_n=np.zeros((count, horizon)),
            allocated_force_norm_n=np.zeros((count, horizon)),
        )

    mpc._full_horizon_interface_rollout = (
        lambda initial, actions, step: coupled_with_velocity(
            np.array([[3.0, 3.0], [4.0, 4.0]])
        )
    )
    recovery = mpc._evaluate_population(state, candidates, None, None, model)
    assert all(item[1] >= 0.0 for item in recovery)
    assert mpc._population_constraint_audit[-1]["recovery_fallback_active"]

    candidates[1, 0, 0] = 1.0
    mpc._full_horizon_interface_rollout = (
        lambda initial, actions, step: coupled_with_velocity(
            np.array([[0.0, 0.0], [3.0, 3.0]])
        )
    )
    enforced = mpc._evaluate_population(state, candidates, None, None, model)
    assert enforced[0][1] >= 0.0
    assert enforced[1][1] < 0.0
    assert mpc._population_constraint_audit[-1]["hold_set_enforced"]


def test_v13_preserves_allocated_force_gate_alongside_physical_force_gate() -> None:
    state, _, model = _registered_model_and_interface()
    allocator = default_engineering_cuff_allocator()
    mpc = GoalDirectedHumanSpaceMPC(cuff_allocator=allocator)
    mpc._set_problem(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        start_episode(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK,
            state[:2],
            state[2:],
            np.zeros(2),
        ),
    )
    count = 2
    horizon = mpc.config.horizon_steps
    candidates = np.zeros((count, horizon, 2))
    predicted = np.broadcast_to(state, (count, horizon, 4)).copy()
    mpc._full_horizon_interface_rollout = lambda initial, actions, step: SimpleNamespace(
        predicted_human_states=predicted,
        predicted_peak_force_n=np.zeros((count, horizon)),
        allocated_force_norm_n=np.full((count, horizon), 201.0),
    )
    evaluations = mpc._evaluate_population(state, candidates, None, None, model)
    assert all(item[1] == pytest.approx(-1.0) for item in evaluations)
