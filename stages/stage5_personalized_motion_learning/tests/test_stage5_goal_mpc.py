from __future__ import annotations

from dataclasses import dataclass
import inspect

import numpy as np
import pytest

from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage5.goal_mpc import (
    GoalDirectedHumanSpaceMPC,
    _AnchoredMotionIncrementRNG,
    local_command_reference,
    support_action,
)
from traction_mpc_stage5.task import (
    GoalTaskState,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
    start_episode,
    transition_phase,
)
from traction_mpc_stage5.task_observation import make_task_observation


SPEC = PROVISIONAL_LOW_MODERATE_GOAL_TASK
START = np.asarray(SPEC.start_return_target_rad)
GOAL = np.asarray(SPEC.outbound_goal_target_rad)
STOPPED = np.zeros(2)


class _DirectIncrementHuman:
    q_min_rad = (0.0, 0.0)
    q_max_rad = (np.radians(80.0), np.radians(100.0))

    @staticmethod
    def step_dynamics(state, action, dt_s):
        del dt_s
        state = np.asarray(state, dtype=float).copy()
        state[:2] += np.asarray(action, dtype=float)
        state[2:] = 0.0
        return state

    @staticmethod
    def inverse_dynamics(q, dq, ddq):
        del q, dq, ddq
        return np.zeros(2)


class _ZeroWrenchAllocator:
    @staticmethod
    def allocate(action, q, human):
        del action, q, human
        return {
            "wrench_world": np.zeros(6),
            "force_norm_n": 0.0,
            "cylindrical_surface_effort_n": 0.0,
            "sagittal_wrench": np.zeros(3),
        }


class _IdentityHuman(_DirectIncrementHuman):
    @staticmethod
    def step_dynamics(state, action, dt_s):
        del action, dt_s
        return np.asarray(state, dtype=float).copy()


class _ConstantLoadedSupportHuman(_DirectIncrementHuman):
    SUPPORT = np.array([12.0, -4.0])

    @classmethod
    def inverse_dynamics(cls, q, dq, ddq):
        del q, dq
        return cls.SUPPORT + np.asarray(ddq, dtype=float)

    @classmethod
    def step_dynamics(cls, state, action, dt_s):
        state = np.asarray(state, dtype=float).copy()
        acceleration = np.asarray(action, dtype=float) - cls.SUPPORT
        state[:2] += dt_s * state[2:] + 0.5 * dt_s**2 * acceleration
        state[2:] += dt_s * acceleration
        return state


@dataclass(frozen=True)
class _AlwaysFeasiblePreview:
    feasible: bool = True
    force_position_n: np.ndarray = np.zeros(3)
    force_velocity_n: np.ndarray = np.zeros(3)
    force_allocator_n: np.ndarray = np.zeros(3)
    force_total_n: np.ndarray = np.zeros(3)
    translational_force_norm_n: float = 0.0
    margin_to_force_gate_n: float = 200.0
    control_dt_s: float = 0.005


def _controller() -> GoalDirectedHumanSpaceMPC:
    config = HumanMPCConfig(
        prediction_dt_s=1.0,
        horizon_steps=2,
        candidate_count=8,
        elite_count=2,
        cem_iterations=1,
        exploration_std_nm=(0.01, 0.01),
        exploration_std_floor_nm=(0.001, 0.001),
    )
    return GoalDirectedHumanSpaceMPC(
        config,
        cuff_allocator=_ZeroWrenchAllocator(),
        implementation="scalar",
        record_timing_breakdown=False,
    )


def _observation():
    return make_task_observation(
        np.concatenate([START, STOPPED]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="fixed-test-model",
    )


def test_goal_mpc_public_solve_has_no_time_reference_input() -> None:
    parameters = inspect.signature(GoalDirectedHumanSpaceMPC.solve_goal).parameters
    assert "reference_fn" not in parameters
    assert "time_s" not in parameters

    state = start_episode(SPEC, START, STOPPED, STOPPED)
    action, diagnostics = _controller().solve_goal(
        _observation(),
        state,
        SPEC,
        _DirectIncrementHuman(),
        first_action_preview=lambda action: _AlwaysFeasiblePreview(),
    )
    assert action is not None
    assert diagnostics["prescribed_full_q_reference_used"] is False
    assert diagnostics["fixed_q1_q2_coordination_ratio"] is False
    assert diagnostics["path_corridor_active"] is False
    assert diagnostics["learned_terminal_value"] == 0.0


def test_support_is_separate_from_the_optimized_motion_increment() -> None:
    controller = _controller()
    task_state = start_episode(SPEC, START, STOPPED, STOPPED)
    action, diagnostics = controller.solve_goal(
        _observation(),
        task_state,
        SPEC,
        _ConstantLoadedSupportHuman(),
        first_action_preview=lambda action: _AlwaysFeasiblePreview(),
    )
    assert action is not None
    np.testing.assert_allclose(
        diagnostics["support_action_nm"], _ConstantLoadedSupportHuman.SUPPORT
    )
    np.testing.assert_allclose(
        action,
        np.asarray(diagnostics["support_action_nm"])
        + np.asarray(diagnostics["selected_motion_increment_nm"]),
    )
    assert diagnostics["action_parameterization"] == (
        "u_total = u_support + delta_u_motion"
    )


def test_cem_motion_population_contains_support_and_continuation_anchors() -> None:
    continuation = np.array([[0.2, -0.1], [0.3, -0.2]])
    rng = _AnchoredMotionIncrementRNG(np.random.default_rng(5), continuation)
    samples = rng.normal(
        np.zeros((2, 2)), np.ones((2, 2)), size=(8, 2, 2)
    )
    np.testing.assert_allclose(samples[1], np.zeros((2, 2)))
    np.testing.assert_allclose(samples[2], continuation)


def test_diagnostic_continuations_shift_without_changing_task_semantics() -> None:
    controller = _controller()
    task_state = start_episode(SPEC, START, STOPPED, STOPPED)
    previous = np.array([[0.2, -0.1], [0.3, -0.2]])
    safest = np.array([[-0.4, 0.1], [-0.2, 0.3]])
    candidates = controller.build_deterministic_continuations(
        _observation(),
        task_state,
        SPEC,
        _ConstantLoadedSupportHuman(),
        previous_selected_sequence_nm=previous,
        previous_safest_sequence_nm=safest,
    )

    np.testing.assert_allclose(
        candidates["shifted_previous_selected"],
        np.array([[0.3, -0.2], [0.3, -0.2]]),
    )
    np.testing.assert_allclose(
        candidates["shifted_previous_safest"],
        np.array([[-0.2, 0.3], [-0.2, 0.3]]),
    )
    np.testing.assert_allclose(candidates["support_only"], np.zeros((2, 2)))
    assert candidates["model_based_braking"].shape == (2, 2)
    assert candidates["smooth_conservative_goal_progress"].shape == (2, 2)
    assert task_state.phase is TaskPhase.OUTBOUND


def test_support_action_is_zero_acceleration_inverse_dynamics() -> None:
    state = np.concatenate([START, np.radians([3.0, -2.0])])
    np.testing.assert_allclose(
        support_action(state, _ConstantLoadedSupportHuman()),
        _ConstantLoadedSupportHuman.SUPPORT,
    )


def test_two_different_intermediate_candidate_paths_reach_same_goal() -> None:
    controller = _controller()
    state = start_episode(SPEC, START, STOPPED, STOPPED)
    delta = GOAL - START
    q1_first = np.array([[delta[0], 0.0], [0.0, delta[1]]])
    q2_first = np.array([[0.0, delta[1]], [delta[0], 0.0]])

    first = controller.evaluate_candidate_sequence(
        _observation(), state, SPEC, _DirectIncrementHuman(), q1_first
    )
    second = controller.evaluate_candidate_sequence(
        _observation(), state, SPEC, _DirectIncrementHuman(), q2_first
    )
    assert first.feasible and second.feasible
    assert first.predicted_states is not None and second.predicted_states is not None
    assert not np.allclose(first.predicted_states[0, :2], second.predicted_states[0, :2])
    np.testing.assert_allclose(first.predicted_states[-1, :2], GOAL)
    np.testing.assert_allclose(second.predicted_states[-1, :2], GOAL)


def test_mpc_solve_does_not_mutate_or_complete_task_phase() -> None:
    task_state = start_episode(SPEC, START, STOPPED, STOPPED)
    original = task_state
    _controller().solve_goal(
        _observation(),
        task_state,
        SPEC,
        _DirectIncrementHuman(),
        first_action_preview=lambda action: _AlwaysFeasiblePreview(),
    )
    assert task_state == original
    assert task_state.phase is TaskPhase.OUTBOUND

    at_goal = transition_phase(
        SPEC, task_state, GOAL, STOPPED, 0.1, ddq_rad_s2=STOPPED
    )
    assert at_goal.phase is TaskPhase.HOLD


def test_local_command_reference_has_no_second_predicted_pose_authority() -> None:
    state = np.concatenate([START, np.radians([1.0, -2.0])])
    reference = local_command_reference(
        state,
        np.array([100.0, -50.0]),
        _DirectIncrementHuman(),
    )
    np.testing.assert_allclose(reference.q_rad, state[:2])
    np.testing.assert_allclose(reference.dq_rad_s, state[2:])
    np.testing.assert_allclose(reference.ddq_rad_s2, np.zeros(2))


def test_stage4_mpc_reference_contract_remains_separate_and_unchanged() -> None:
    stage4_parameters = inspect.signature(HumanSpaceMPC.solve).parameters
    assert "time_s" in stage4_parameters
    assert "reference_fn" in stage4_parameters
    assert not isinstance(HumanSpaceMPC(), GoalDirectedHumanSpaceMPC)


def test_hold_adds_running_position_and_velocity_without_changing_other_phases() -> None:
    controller = _controller()
    hold = GoalTaskState(
        phase=TaskPhase.HOLD,
        phase_elapsed_s=0.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )
    zero_sequence = np.zeros((2, 2))
    stopped = make_task_observation(
        np.concatenate([GOAL, STOPPED]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="fixed-test-model",
    )
    moving = make_task_observation(
        np.concatenate([GOAL, np.radians([8.0, -8.0])]),
        sample_timestamp_s=0.0,
        controller_timestamp_s=0.0,
        human_model_version="fixed-test-model",
    )
    stopped_cost = controller.evaluate_candidate_sequence(
        stopped, hold, SPEC, _IdentityHuman(), zero_sequence
    )
    moving_cost = controller.evaluate_candidate_sequence(
        moving, hold, SPEC, _IdentityHuman(), zero_sequence
    )
    assert stopped_cost.cost_terms["hold_set_violation"] == pytest.approx(0.0)
    assert stopped_cost.cost_terms["hold_inside_regulation"] == pytest.approx(0.0)
    assert moving_cost.cost_terms["hold_set_violation"] > 0.0
    assert moving_cost.cost_terms["hold_inside_regulation"] > 0.0
    assert moving_cost.total_cost > stopped_cost.total_cost
    assert not moving_cost.feasible

    outbound = start_episode(SPEC, START, STOPPED, STOPPED)
    outbound_cost = controller.evaluate_candidate_sequence(
        _observation(), outbound, SPEC, _IdentityHuman(), zero_sequence
    )
    assert outbound_cost.cost_terms["hold_set_violation"] == pytest.approx(0.0)
    assert outbound_cost.cost_terms["hold_inside_regulation"] == pytest.approx(0.0)
    assert outbound_cost.cost_terms["stage_target_distance"] > 0.0

    returning = GoalTaskState(
        phase=TaskPhase.RETURN,
        phase_elapsed_s=0.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=True,
    )
    return_cost = controller.evaluate_candidate_sequence(
        _observation(), returning, SPEC, _IdentityHuman(), zero_sequence
    )
    assert return_cost.cost_terms["hold_set_violation"] == pytest.approx(0.0)
    assert return_cost.cost_terms["hold_inside_regulation"] == pytest.approx(0.0)
