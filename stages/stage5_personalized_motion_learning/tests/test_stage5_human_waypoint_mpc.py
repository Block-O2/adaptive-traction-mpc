from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_mpc import HumanWaypointMPCPrototypeV1
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1,
    shank_table_clearance_m,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def _scheduler() -> QuinticHumanWaypointSchedulerV1:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5CR12SensorBoundaryPlant(STAGE5_HUMAN)
    truth = plant.reset(np.asarray(spec.start_return_target_rad))
    estimator = FixedStage5Estimator(
        truth.attachment_position_m,
        truth.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    return QuinticHumanWaypointSchedulerV1(spec, estimator.model)


def test_reference_contract_plan_does_not_call_legacy_pd_preview(monkeypatch) -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    candidate = HumanWaypointCandidate(
        label="reference_only",
        phase=TaskPhase.OUTBOUND,
        phase_goal_rad=np.asarray(spec.outbound_goal_target_rad),
        q_waypoint_rad=np.radians([8.0, 15.0]),
        dq_waypoint_rad_s=np.zeros(2),
    )

    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("legacy instantaneous PD preview was used")

    monkeypatch.setattr(scheduler, "_nominal_tracking_check", forbidden)
    schedule = scheduler.plan_reference_contract(
        current_q_hat_rad=np.asarray(spec.start_return_target_rad),
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )

    assert schedule.feasibility_semantics == "causal_20ms_scheduled_reference_motion"
    assert np.all(
        schedule.maximum_causal_20ms_reference_acceleration_rad_s2
        <= np.asarray(spec.task_joint_acceleration_limit_rad_s2) + 1.0e-12
    )


def test_waypoint_mpc_selects_progressing_feasible_human_action() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    state = np.concatenate(
        [np.asarray(spec.start_return_target_rad, dtype=float), np.zeros(2)]
    )

    decision = mpc.decide(
        current_deployable_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
    )

    assert decision.selected.feasible
    assert decision.selected.schedule is not None
    assert decision.selected.schedule.feasibility_semantics == (
        "causal_20ms_scheduled_reference_motion"
    )
    assert np.all(decision.selected.q_waypoint_rad > state[:2])
    assert shank_table_clearance_m(decision.selected.q_waypoint_rad) >= 0.0
    assert not mpc.record()["uses_old_robot_interface_predictor"]
    assert not mpc.record()["uses_pd_acceleration_request_for_feasibility"]


def test_waypoint_mpc_reference_sequence_reaches_registered_outbound_goal() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    state = np.concatenate(
        [np.asarray(spec.start_return_target_rad, dtype=float), np.zeros(2)]
    )

    for index in range(10):
        decision = mpc.decide(
            current_deployable_state=state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.1 * index,
        )
        state = np.concatenate(
            [decision.selected.q_waypoint_rad, decision.selected.dq_waypoint_rad_s]
        )
        if np.allclose(
            state[:2],
            spec.outbound_goal_target_rad,
            atol=max(spec.joint_angle_completion_tolerance_rad),
            rtol=0.0,
        ):
            break

    assert state[:2].tolist() == pytest.approx(spec.outbound_goal_target_rad)
    assert 2 <= len(mpc.decisions) <= 10


def test_waypoint_mpc_hold_has_one_zero_velocity_goal_candidate() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    state = np.concatenate(
        [np.asarray(spec.outbound_goal_target_rad, dtype=float), np.zeros(2)]
    )

    decision = mpc.decide(
        current_deployable_state=state,
        phase=TaskPhase.HOLD,
        phase_elapsed_s=0.0,
    )

    assert len(decision.evaluations) == 1
    assert decision.selected.q_waypoint_rad.tolist() == pytest.approx(
        spec.outbound_goal_target_rad
    )
    assert decision.selected.dq_waypoint_rad_s.tolist() == pytest.approx([0.0, 0.0])


def test_waypoint_mpc_applies_existing_execution_screen_to_every_candidate() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    state = np.concatenate(
        [np.asarray(spec.start_return_target_rad, dtype=float), np.zeros(2)]
    )
    screened: list[str] = []

    def execution_screen(candidate, schedule):
        screened.append(candidate.label)
        assert schedule.feasibility_semantics == (
            "causal_20ms_scheduled_reference_motion"
        )
        return {
            "evaluated": True,
            "feasible": True,
            "safety_filter_status": "SAFE_UNCHANGED",
            "force_gate_margin_n": 1.0,
            "torque_clipped": False,
        }

    decision = mpc.decide(
        current_deployable_state=state,
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        execution_feasibility_checker=execution_screen,
    )

    feasible_count = sum(item.feasible for item in decision.evaluations)
    assert len(screened) == feasible_count
    assert all(
        item.execution_screen.get("evaluated")
        for item in decision.evaluations
        if item.schedule is not None
    )


def test_continuous_coordination_variable_changes_relative_joint_progress() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    state = np.concatenate(
        [np.asarray(spec.start_return_target_rad, dtype=float), np.zeros(2)]
    )
    span = np.asarray(spec.outbound_goal_target_rad) - np.asarray(
        spec.start_return_target_rad
    )

    decisions = {}
    for coordination_preference_r in (-0.25, 0.0, 0.137, 0.25):
        mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
        decisions[coordination_preference_r] = mpc.decide(
            current_deployable_state=state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.0,
            coordination_preference_r=coordination_preference_r,
        )

    progress = {
        key: (decision.selected.q_waypoint_rad - state[:2]) / span
        for key, decision in decisions.items()
    }
    assert progress[-0.25][0] < progress[-0.25][1]
    assert progress[0.25][0] > progress[0.25][1]
    assert progress[0.0][0] == pytest.approx(progress[0.0][1])
    assert not np.allclose(
        decisions[0.137].selected.q_waypoint_rad,
        decisions[0.0].selected.q_waypoint_rad,
    )
    assert not np.allclose(
        decisions[0.137].selected.q_waypoint_rad,
        decisions[0.25].selected.q_waypoint_rad,
    )
    assert decisions[0.137].coordination_preference_r == pytest.approx(0.137)


def test_coordination_variable_rejects_values_outside_registered_domain() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    state = np.concatenate(
        [np.asarray(spec.start_return_target_rad, dtype=float), np.zeros(2)]
    )

    with pytest.raises(ValueError, match="coordination_preference_r"):
        mpc.decide(
            current_deployable_state=state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.0,
            coordination_preference_r=1.01,
        )


def test_coordination_path_has_common_endpoints_and_reverses_on_return() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    span = goal - start
    r = 0.25

    outbound_mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    outbound_state = np.concatenate([start, np.zeros(2)])
    outbound_waypoints = []
    for index in range(10):
        decision = outbound_mpc.decide(
            current_deployable_state=outbound_state,
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=0.1 * index,
            coordination_preference_r=r,
        )
        outbound_waypoints.append(decision.selected.q_waypoint_rad.copy())
        outbound_state = np.concatenate(
            [decision.selected.q_waypoint_rad, np.zeros(2)]
        )
        if np.allclose(outbound_state[:2], goal, atol=1.0e-12, rtol=0.0):
            break

    return_mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    return_state = np.concatenate([goal, np.zeros(2)])
    return_waypoints = []
    for index in range(10):
        decision = return_mpc.decide(
            current_deployable_state=return_state,
            phase=TaskPhase.RETURN,
            phase_elapsed_s=0.1 * index,
            coordination_preference_r=r,
        )
        return_waypoints.append(decision.selected.q_waypoint_rad.copy())
        return_state = np.concatenate(
            [decision.selected.q_waypoint_rad, np.zeros(2)]
        )
        if np.allclose(return_state[:2], start, atol=1.0e-12, rtol=0.0):
            break

    assert outbound_waypoints[-1].tolist() == pytest.approx(goal)
    assert return_waypoints[-1].tolist() == pytest.approx(start)
    np.testing.assert_allclose(
        np.asarray(return_waypoints[-2::-1]),
        np.asarray(outbound_waypoints[:-1]),
        atol=1.0e-12,
        rtol=0.0,
    )
    for waypoint in outbound_waypoints[:-1]:
        progress = (waypoint - start) / span
        assert progress[0] > progress[1]
        assert shank_table_clearance_m(waypoint) >= 0.0
