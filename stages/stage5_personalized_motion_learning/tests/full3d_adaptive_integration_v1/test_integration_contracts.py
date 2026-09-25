import numpy as np
import pytest

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import (
    SessionClearanceContract,
    nominal_control_model,
)
from traction_mpc_stage5.human_waypoint_feedback_mpc import (
    HumanWaypointFeedbackMPCConfigV1,
    HumanWaypointFeedbackMPCV1,
)
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def test_session_clearance_uses_effective_geometry_and_conservative_set():
    contract = SessionClearanceContract(nominal_control_model().geometry)
    values = contract.evaluate(np.radians([[5.0, 10.0], [20.0, 35.0]]))
    assert values.shape == (2,)
    assert np.all(np.isfinite(values))
    assert np.all(values > 0.0)
    assert contract.record()["hidden_geometry_consumed"] is False


def test_mechanics_duration_search_retains_limits_and_selects_longer_schedule():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    model = nominal_control_model()
    clearance = SessionClearanceContract(model.geometry)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec,
        model,
        clearance_evaluator=clearance.evaluate,
        clearance_source="TEST_SESSION_EFFECTIVE_GEOMETRY",
    )
    planner = HumanWaypointFeedbackMPCV1(
        spec,
        scheduler,
        HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True),
    )

    def screen(candidate, schedule):
        del candidate
        return {
            "evaluated": True,
            "feasible": schedule.duration_s >= 0.8,
            "rejection_reason": "test_minimum_mechanics_duration",
        }

    start = np.radians([5.0, 10.0])
    decision = planner.decide(
        current_deployable_state=np.r_[start, np.zeros(2)],
        current_reference_state=np.r_[start, np.zeros(2)],
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=2.0,
        execution_feasibility_checker=screen,
    )
    assert decision.executed.schedule is not None
    assert decision.executed.schedule.duration_s >= 0.8
    assert decision.executed.execution_screen["duration_search_used"] is True


def test_task_endpoint_clearance_floor_rejects_near_bed_return_detour():
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    model = nominal_control_model()
    clearance = SessionClearanceContract(model.geometry)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec,
        model,
        clearance_evaluator=clearance.evaluate,
        clearance_source="TEST_SESSION_EFFECTIVE_GEOMETRY",
        preserve_task_endpoint_clearance_floor=True,
    )
    candidate = HumanWaypointCandidate(
        label="audited_near_bed_return_detour",
        phase=TaskPhase.RETURN,
        phase_goal_rad=np.asarray(spec.start_return_target_rad),
        q_waypoint_rad=np.radians([7.488171756826749, 15.07872615956084]),
        dq_waypoint_rad_s=np.zeros(2),
    )
    with pytest.raises(ValueError, match="no quintic schedule"):
        scheduler.plan_reference_contract(
            current_q_hat_rad=np.radians([10.488171756826748, 20.07872615956084]),
            current_dq_hat_rad_s=np.zeros(2),
            candidate=candidate,
            phase_elapsed_s=1.285,
        )
