from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math

import pytest

from traction_mpc_stage5.task import (
    PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    ControllerCompletionMargin,
    GoalTaskSpec,
    TaskPhase,
    at_goal,
    at_goal_for_online_completion,
    diagnostic_normalized_progress,
    start_episode,
    transition_phase,
    true_episode_complete,
)


SPEC = PROVISIONAL_LOW_MODERATE_GOAL_TASK
START = SPEC.start_return_target_rad
GOAL = SPEC.outbound_goal_target_rad
STOPPED = (0.0, 0.0)
ZERO_ACCELERATION = (0.0, 0.0)


def _advance_hold(state, duration_s: float, step_s: float = 0.1):
    count = int(round(duration_s / step_s))
    for _ in range(count):
        state = transition_phase(
            SPEC,
            state,
            GOAL,
            STOPPED,
            step_s,
            ddq_rad_s2=ZERO_ACCELERATION,
        )
    return state


def test_spec_is_immutable_and_configuration_has_no_prescribed_path() -> None:
    assert isinstance(SPEC, GoalTaskSpec)
    assert SPEC.source_fixture == "Stage-5 low/moderate cold-start prefix endpoints"
    with pytest.raises(FrozenInstanceError):
        SPEC.hold_duration_s = 1.0  # type: ignore[misc]


def test_normal_outbound_hold_return_complete() -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    assert state.phase is TaskPhase.OUTBOUND

    state = transition_phase(
        SPEC, state, GOAL, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.HOLD
    state = _advance_hold(state, SPEC.hold_duration_s)
    assert state.phase is TaskPhase.RETURN

    state = transition_phase(
        SPEC, state, START, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.COMPLETE
    assert true_episode_complete(state)


def test_goal_angle_with_excessive_velocity_does_not_count() -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    excessive = (
        2.0 * SPEC.joint_velocity_completion_tolerance_rad_s[0],
        0.0,
    )
    state = transition_phase(
        SPEC, state, GOAL, excessive, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.OUTBOUND
    assert not true_episode_complete(state)


def test_hold_timer_resets_when_target_is_lost() -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    state = transition_phase(
        SPEC, state, GOAL, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    state = _advance_hold(state, 0.3)
    assert state.phase is TaskPhase.HOLD
    assert state.hold_elapsed_s == pytest.approx(0.3)

    lost_goal = (
        GOAL[0] + 2.0 * SPEC.joint_angle_completion_tolerance_rad[0],
        GOAL[1],
    )
    state = transition_phase(
        SPEC, state, lost_goal, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.HOLD
    assert state.hold_elapsed_s == 0.0

    state = _advance_hold(state, 0.4)
    assert state.phase is TaskPhase.HOLD
    state = _advance_hold(state, 0.1)
    assert state.phase is TaskPhase.RETURN


def test_timeout_and_explicit_abort_are_terminal_non_success() -> None:
    short = replace(SPEC, hold_duration_s=0.1, phase_timeout_s=0.2)
    state = start_episode(short, START, STOPPED, ZERO_ACCELERATION)
    intermediate = tuple((a + b) / 2.0 for a, b in zip(START, GOAL, strict=True))
    state = transition_phase(
        short, state, intermediate, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    state = transition_phase(
        short, state, intermediate, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.ABORTED
    assert state.abort_reason == "TIMEOUT_OUTBOUND"
    assert not true_episode_complete(state)

    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    state = transition_phase(
        SPEC,
        state,
        intermediate,
        STOPPED,
        0.1,
        ddq_rad_s2=ZERO_ACCELERATION,
        abort_reason="SAFETY_FILTER_ABORT",
    )
    assert state.phase is TaskPhase.ABORTED
    assert state.abort_reason == "SAFETY_FILTER_ABORT"


def test_no_premature_completion() -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    state = transition_phase(
        SPEC, state, START, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.OUTBOUND

    state = transition_phase(
        SPEC, state, GOAL, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.HOLD
    state = transition_phase(
        SPEC,
        state,
        GOAL,
        STOPPED,
        SPEC.hold_duration_s - 1.0e-3,
        ddq_rad_s2=ZERO_ACCELERATION,
    )
    assert state.phase is TaskPhase.HOLD
    assert not true_episode_complete(state)


@pytest.mark.parametrize(
    "intermediate",
    [
        pytest.param(lambda: (GOAL[0], START[1]), id="q1-first"),
        pytest.param(lambda: (START[0], GOAL[1]), id="q2-first"),
    ],
)
def test_different_intermediate_paths_can_reach_same_goal(intermediate) -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    waypoint = intermediate()
    state = transition_phase(
        SPEC, state, waypoint, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.OUTBOUND
    assert 0.0 <= diagnostic_normalized_progress(SPEC, state.phase, waypoint) <= 1.0

    state = transition_phase(
        SPEC, state, GOAL, STOPPED, 0.1, ddq_rad_s2=ZERO_ACCELERATION
    )
    assert state.phase is TaskPhase.HOLD
    assert diagnostic_normalized_progress(SPEC, state.phase, GOAL) == pytest.approx(1.0)


def test_provisional_default_values_are_the_registered_low_moderate_fixture() -> None:
    assert tuple(map(math.degrees, START)) == pytest.approx((5.0, 10.0))
    assert tuple(map(math.degrees, GOAL)) == pytest.approx((20.0, 35.0))
    q_bounds_deg = tuple(
        (math.degrees(a), math.degrees(b)) for a, b in SPEC.q_bounds_rad
    )
    assert q_bounds_deg[0] == pytest.approx((0.0, 80.0))
    assert q_bounds_deg[1] == pytest.approx((0.0, 100.0))
    assert tuple(map(math.degrees, SPEC.joint_angle_completion_tolerance_rad)) == pytest.approx(
        (1.0, 1.0)
    )
    assert tuple(
        map(math.degrees, SPEC.joint_velocity_completion_tolerance_rad_s)
    ) == pytest.approx((2.0, 2.0))
    assert SPEC.hold_duration_s == 0.5
    assert SPEC.phase_timeout_s == 10.0
    assert tuple(map(math.degrees, SPEC.task_joint_velocity_limit_rad_s)) == pytest.approx(
        (45.0, 75.0)
    )
    assert tuple(
        map(math.degrees, SPEC.task_joint_acceleration_limit_rad_s2)
    ) == pytest.approx((300.0, 600.0))


def test_controller_completion_margin_is_conservative_only() -> None:
    margin = PROVISIONAL_CONTROLLER_COMPLETION_MARGIN
    angle, velocity = margin.tightened_tolerances(SPEC)
    assert tuple(map(math.degrees, angle)) == pytest.approx((0.95, 0.90))
    assert tuple(map(math.degrees, velocity)) == pytest.approx((1.25, 0.50))

    # This state satisfies the immutable task definition, but the online
    # decision waits because its q2 speed is not robust to observed bias.
    marginal_dq = (0.0, math.radians(1.0))
    assert at_goal(SPEC, GOAL, marginal_dq, GOAL)
    assert not at_goal_for_online_completion(SPEC, GOAL, marginal_dq, GOAL, margin)

    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    waiting = transition_phase(
        SPEC,
        state,
        GOAL,
        marginal_dq,
        0.1,
        ddq_rad_s2=ZERO_ACCELERATION,
        completion_margin=margin,
    )
    assert waiting.phase is TaskPhase.OUTBOUND


def test_completion_margin_cannot_relax_actual_task_tolerance() -> None:
    invalid = ControllerCompletionMargin(
        joint_angle_margin_rad=SPEC.joint_angle_completion_tolerance_rad,
        joint_velocity_margin_rad_s=(0.0, 0.0),
    )
    with pytest.raises(ValueError, match="below task tolerances"):
        invalid.tightened_tolerances(SPEC)


def test_motion_envelope_is_jointwise_and_aborts_observed_violations() -> None:
    state = start_episode(SPEC, START, STOPPED, ZERO_ACCELERATION)
    q1_velocity_violation = (
        1.01 * SPEC.task_joint_velocity_limit_rad_s[0],
        0.0,
    )
    result = transition_phase(
        SPEC,
        state,
        START,
        q1_velocity_violation,
        0.005,
        ddq_rad_s2=ZERO_ACCELERATION,
    )
    assert result.phase is TaskPhase.ABORTED
    assert result.abort_reason == "TASK_VELOCITY_LIMIT"


def test_acceleration_authority_waits_for_valid_history_without_skipping_other_limits() -> None:
    state = start_episode(
        SPEC,
        START,
        STOPPED,
        None,
        acceleration_authority_valid=False,
    )
    warming = transition_phase(
        SPEC,
        state,
        START,
        STOPPED,
        0.005,
        ddq_rad_s2=None,
        acceleration_authority_valid=False,
    )
    assert warming.phase is TaskPhase.OUTBOUND

    velocity_violation = transition_phase(
        SPEC,
        warming,
        START,
        (1.01 * SPEC.task_joint_velocity_limit_rad_s[0], 0.0),
        0.005,
        ddq_rad_s2=None,
        acceleration_authority_valid=False,
    )
    assert velocity_violation.phase is TaskPhase.ABORTED
    assert velocity_violation.abort_reason == "TASK_VELOCITY_LIMIT"
