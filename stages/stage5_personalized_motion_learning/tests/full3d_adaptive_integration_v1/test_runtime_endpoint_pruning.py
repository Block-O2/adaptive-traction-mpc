"""Necessary-condition pruning, retaining the original reference contract."""
import numpy as np
import pytest

import traction_mpc_stage5.human_waypoint_scheduler as mod
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import (
    SessionClearanceContract, nominal_control_model,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK as SPEC, TaskPhase


def setup_scheduler(evaluator=None, preserve=True):
    model=nominal_control_model()
    return mod.QuinticHumanWaypointSchedulerV1(SPEC,model,reference_period_s=.005,
        clearance_evaluator=evaluator or SessionClearanceContract(model.geometry).evaluate,
        preserve_task_endpoint_clearance_floor=preserve)


def test_impossible_endpoint_rejected_without_duration_enumeration(monkeypatch):
    scheduler=setup_scheduler()
    target=np.radians([7.488171756826749,15.07872615956084])
    candidate=HumanWaypointCandidate('endpoint',TaskPhase.RETURN,
        np.asarray(SPEC.start_return_target_rad),target,np.zeros(2))
    # Endpoint above zero but below the already-registered positive floor.
    clearance=scheduler._clearance_m(target)
    floor=scheduler._clearance_m(np.asarray(SPEC.start_return_target_rad))
    assert 0 < clearance < floor-1e-9
    def unexpected(*args,**kwargs):
        raise AssertionError('impossible boundary must not enumerate durations')
    monkeypatch.setattr(mod,'_quintic_coefficients',unexpected)
    with pytest.raises(ValueError,match='no quintic schedule'):
        scheduler.plan_reference_contract(current_q_hat_rad=np.radians([10.49,20.08]),
            current_dq_hat_rad_s=np.zeros(2),candidate=candidate,phase_elapsed_s=1.285)


def test_roundoff_guard_does_not_relax_path_acceptance(monkeypatch):
    # Synthetic smooth plane: endpoint violates by only 0.5nm. Early pruning
    # must not decide it, but the original 1pm acceptance tolerance still rejects.
    start=np.asarray(SPEC.start_return_target_rad)
    target=start+np.array([1e-5,1e-5])
    def clearance(q):
        rows=np.asarray(q)
        return .001-(rows[...,0]-start[0])*5e-5
    scheduler=setup_scheduler(clearance)
    candidate=HumanWaypointCandidate('guard',TaskPhase.RETURN,start,target,np.zeros(2))
    calls=[];original=mod._quintic_coefficients
    sample_counts=[];path_check=scheduler._path_clearance_is_valid
    def counted_path(values,c,**kwargs):
        sample_counts.append(len(values));return path_check(values,c,**kwargs)
    monkeypatch.setattr(scheduler,'_path_clearance_is_valid',counted_path)
    def counted(*args,**kwargs):
        calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(mod,'_quintic_coefficients',counted)
    assert not scheduler._path_clearance_is_valid(clearance(np.array([start,target])),candidate)
    with pytest.raises(ValueError,match='no quintic schedule'):
        scheduler.plan_reference_contract(current_q_hat_rad=start,current_dq_hat_rad_s=np.zeros(2),
            candidate=candidate,phase_elapsed_s=9.95)
    assert len(calls)==10
    assert max(sample_counts)>2


def test_hold_keeps_its_separate_contract():
    scheduler=setup_scheduler()
    goal=np.asarray(SPEC.outbound_goal_target_rad)
    candidate=HumanWaypointCandidate('hold',TaskPhase.HOLD,goal,goal,np.zeros(2))
    schedule=scheduler.plan_reference_contract(current_q_hat_rad=goal,
        current_dq_hat_rad_s=np.zeros(2),candidate=candidate)
    assert schedule.duration_s==SPEC.hold_duration_s
    np.testing.assert_array_equal(schedule.sample(schedule.duration_s).q_rad,goal)


def test_disabled_endpoint_floor_retains_legacy_positive_clearance_path():
    scheduler=setup_scheduler(preserve=False)
    candidate=HumanWaypointCandidate('legacy',TaskPhase.RETURN,
        np.asarray(SPEC.start_return_target_rad),
        np.radians([7.488171756826749,15.07872615956084]),np.zeros(2))
    schedule=scheduler.plan_reference_contract(current_q_hat_rad=np.radians([10.49,20.08]),
        current_dq_hat_rad_s=np.zeros(2),candidate=candidate,phase_elapsed_s=1.285)
    assert schedule.minimum_reference_shank_clearance_m > 0
