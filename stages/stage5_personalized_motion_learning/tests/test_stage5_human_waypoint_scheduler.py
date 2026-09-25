from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_scheduler import (
    SCHEDULED_REFERENCE_MOTION_WINDOW_S,
    QuinticHumanWaypointSchedulerV1,
    WaypointGeometryInfeasible,
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


def _candidate(
    label: str,
    phase: TaskPhase,
    target_deg: tuple[float, float],
) -> HumanWaypointCandidate:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    goal = (
        spec.start_return_target_rad
        if phase is TaskPhase.RETURN
        else spec.outbound_goal_target_rad
    )
    return HumanWaypointCandidate(
        label=label,
        phase=phase,
        phase_goal_rad=np.asarray(goal),
        q_waypoint_rad=np.radians(target_deg),
        dq_waypoint_rad_s=np.zeros(2),
    )


def test_quintic_schedule_is_deterministic_and_respects_registered_limits() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    candidate = _candidate("outbound_balanced", TaskPhase.OUTBOUND, (6.0, 11.0))
    kwargs = {
        "current_q_hat_rad": np.radians([5.0, 10.0]),
        "current_dq_hat_rad_s": np.zeros(2),
        "candidate": candidate,
        "phase_elapsed_s": 0.0,
    }

    first = scheduler.plan(**kwargs)
    second = scheduler.plan(**kwargs)

    assert first.duration_s == second.duration_s
    assert np.array_equal(first.coefficients, second.coefficients)
    assert np.all(
        first.maximum_reference_velocity_rad_s
        <= np.asarray(spec.task_joint_velocity_limit_rad_s) + 1.0e-12
    )
    assert np.all(
        first.maximum_reference_acceleration_rad_s2
        <= np.asarray(spec.task_joint_acceleration_limit_rad_s2) + 1.0e-12
    )
    start = first.sample(0.0)
    end = first.sample(first.duration_s)
    assert start.q_rad.tolist() == pytest.approx(np.radians([5.0, 10.0]))
    assert start.dq_rad_s.tolist() == pytest.approx([0.0, 0.0])
    assert end.q_rad.tolist() == pytest.approx(candidate.q_waypoint_rad)
    assert end.dq_rad_s.tolist() == pytest.approx(candidate.dq_waypoint_rad_s)


def test_scheduler_rejects_waypoint_inside_existing_shank_table_geometry() -> None:
    scheduler = _scheduler()
    candidate = _candidate("outbound_knee_biased", TaskPhase.OUTBOUND, (5.5, 13.0))

    assert shank_table_clearance_m(candidate.q_waypoint_rad) < 0.0
    with pytest.raises(WaypointGeometryInfeasible, match="target waypoint"):
        scheduler.plan(
            current_q_hat_rad=np.radians([5.0, 10.0]),
            current_dq_hat_rad_s=np.zeros(2),
            candidate=candidate,
        )


def test_return_knee_schedule_remains_inside_noncontact_geometry() -> None:
    scheduler = _scheduler()
    candidate = _candidate("return_knee_biased", TaskPhase.RETURN, (7.5, 12.0))
    schedule = scheduler.plan(
        current_q_hat_rad=np.radians([8.0, 15.0]),
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )

    samples = [
        schedule.sample(index * schedule.reference_period_s).q_rad
        for index in range(int(round(schedule.duration_s / schedule.reference_period_s)) + 1)
    ]
    assert np.min(shank_table_clearance_m(np.asarray(samples))) >= 0.0


def test_path_governor_uses_valid_causal_20ms_reference_motion_history() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    current_q = np.radians([5.0, 10.0])
    current_dq = np.zeros(2)
    candidate = _candidate("full_outbound", TaskPhase.OUTBOUND, (20.0, 35.0))

    session = scheduler.start_session(
        current_q_hat_rad=current_q,
        current_dq_hat_rad_s=current_dq,
        candidate=candidate,
    )
    for step in range(5):
        sample = session.advance(
            current_q_hat_rad=current_q,
            current_dq_hat_rad_s=current_dq,
            phase_elapsed_s=step * scheduler.reference_period_s,
        )

    assert len(session.diagnostic_events) == 5
    assert all(
        not event["reference_history_valid"]
        for event in session.diagnostic_events[:4]
    )
    assert all(event["held"] for event in session.diagnostic_events[:4])
    event = session.diagnostic_events[-1]
    assert event["reference_history_valid"]
    assert event["reference_history_coverage_s"] == pytest.approx(
        SCHEDULED_REFERENCE_MOTION_WINDOW_S
    )
    assert event["accepted_progress_s"] == pytest.approx(session.progress_s)
    assert session.progress_s > 0.0
    assert event["accepted_q_reference_rad"].tolist() == pytest.approx(sample.q_rad)
    assert event["accepted_dq_reference_rad_s"].tolist() == pytest.approx(
        sample.dq_rad_s
    )
    assert event["criterion"] == "causal_20ms_scheduled_reference_motion"
    assert np.all(
        np.abs(event["accepted_reference_motion_acceleration_rad_s2"])
        <= np.asarray(spec.task_joint_acceleration_limit_rad_s2) + 1.0e-12
    )


def test_reference_motion_governor_is_independent_of_pd_tracking_error() -> None:
    scheduler = _scheduler()
    candidate = _candidate("full_outbound", TaskPhase.OUTBOUND, (20.0, 35.0))
    nominal = scheduler.start_session(
        current_q_hat_rad=np.radians([5.0, 10.0]),
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )
    lagged = scheduler.start_session(
        current_q_hat_rad=np.radians([5.0, 10.0]),
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )

    for step in range(8):
        elapsed_s = step * scheduler.reference_period_s
        nominal_sample = nominal.advance(
            current_q_hat_rad=np.radians([5.0, 10.0]),
            current_dq_hat_rad_s=np.zeros(2),
            phase_elapsed_s=elapsed_s,
        )
        lagged_sample = lagged.advance(
            current_q_hat_rad=np.radians([7.0, 13.0]),
            current_dq_hat_rad_s=np.radians([-20.0, -30.0]),
            phase_elapsed_s=elapsed_s,
        )

    assert lagged.progress_s == pytest.approx(nominal.progress_s)
    assert lagged_sample.q_rad.tolist() == pytest.approx(nominal_sample.q_rad)
    assert lagged_sample.dq_rad_s.tolist() == pytest.approx(
        nominal_sample.dq_rad_s
    )


def test_reference_motion_governor_holds_on_incomplete_20ms_history() -> None:
    scheduler = _scheduler()
    current_q = np.radians([5.0, 10.0])
    candidate = _candidate("full_outbound", TaskPhase.OUTBOUND, (20.0, 35.0))
    session = scheduler.start_session(
        current_q_hat_rad=current_q,
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )

    for elapsed_s in (0.0, 0.005, 0.010, 0.020):
        sample = session.advance(
            current_q_hat_rad=current_q,
            current_dq_hat_rad_s=np.zeros(2),
            phase_elapsed_s=elapsed_s,
        )

    event = session.diagnostic_events[-1]
    assert event["reference_history_coverage_s"] == pytest.approx(0.020)
    assert not event["reference_history_contiguous"]
    assert not event["reference_history_valid"]
    assert event["held"]
    assert session.progress_s == 0.0
    assert sample.q_rad.tolist() == pytest.approx(current_q)


def test_path_governor_completes_under_ideal_reference_tracking() -> None:
    scheduler = _scheduler()
    current_q = np.radians([5.0, 10.0])
    current_dq = np.zeros(2)
    candidate = _candidate("outbound_balanced", TaskPhase.OUTBOUND, (6.0, 11.0))
    session = scheduler.start_session(
        current_q_hat_rad=current_q,
        current_dq_hat_rad_s=current_dq,
        candidate=candidate,
    )

    for step in range(300):
        sample = session.advance(
            current_q_hat_rad=current_q,
            current_dq_hat_rad_s=current_dq,
            phase_elapsed_s=step * scheduler.reference_period_s,
        )
        current_q = sample.q_rad
        current_dq = sample.dq_rad_s
        if session.progress_s == session.schedule.duration_s:
            break

    assert session.progress_s == session.schedule.duration_s
    assert session.regression_count == 0
    assert current_q.tolist() == pytest.approx(candidate.q_waypoint_rad)
    assert current_dq.tolist() == pytest.approx(candidate.dq_waypoint_rad_s)


def test_hold_schedule_uses_registered_hold_duration_and_zero_motion() -> None:
    scheduler = _scheduler()
    spec = scheduler.spec
    candidate = _candidate("hold", TaskPhase.HOLD, (20.0, 35.0))
    schedule = scheduler.plan(
        current_q_hat_rad=np.asarray(spec.outbound_goal_target_rad),
        current_dq_hat_rad_s=np.zeros(2),
        candidate=candidate,
    )

    assert schedule.duration_s == spec.hold_duration_s
    for elapsed_s in (0.0, schedule.duration_s / 2.0, schedule.duration_s):
        sample = schedule.sample(elapsed_s)
        assert sample.q_rad.tolist() == pytest.approx(candidate.q_waypoint_rad)
        assert sample.dq_rad_s.tolist() == pytest.approx([0.0, 0.0])
        assert sample.ddq_rad_s2.tolist() == pytest.approx([0.0, 0.0])
