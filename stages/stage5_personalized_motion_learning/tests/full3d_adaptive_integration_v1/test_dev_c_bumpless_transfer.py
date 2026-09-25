"""Finite control-effect transfer and causal update/rejection semantics."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pytest

from traction_mpc_stage5.full3d_adaptive_integration_v1.bumpless_transfer import (
    BumplessHumanActionTransfer,
)


@dataclass
class ToyModel:
    beta: np.ndarray
    residual_weights_nm: np.ndarray
    residual_limit_nm: float = 12.0

    def inverse_dynamics(self, q, dq, ddq):
        return np.array([self.beta[0] + q[0] + ddq[0],
                         self.beta[1] + dq[1] + ddq[1]])


def model(hip: float) -> ToyModel:
    beta = np.zeros(11)
    beta[0] = hip
    return ToyModel(beta, np.zeros((2, 5)))


STATE = np.array([.1, .2, .3, .4])
ACC = np.array([.5, .6])


def apply(manager, accepted, time):
    return manager.apply(STATE, ACC, accepted.inverse_dynamics(STATE[:2], STATE[2:], ACC), time)


def test_initial_transfer_reaches_exact_accepted_model_and_realization_is_distinct():
    old, new = model(0), model(18)
    transfer = BumplessHumanActionTransfer(old, initial_version="prior", duration_s=.25,
                                           small_direct_action_change_nm=.19)
    transfer.offer(new, version="belief_310", time_s=7.025)
    assert np.array_equal(apply(transfer, new, 7.025), old.inverse_dynamics(STATE[:2], STATE[2:], ACC))
    assert transfer.snapshot()["fraction_new"] == 0
    midpoint = apply(transfer, new, 7.150)
    assert np.allclose(midpoint, .5*(old.inverse_dynamics(STATE[:2], STATE[2:], ACC)
                                    + new.inverse_dynamics(STATE[:2], STATE[2:], ACC)))
    assert np.array_equal(apply(transfer, new, 7.275), new.inverse_dynamics(STATE[:2], STATE[2:], ACC))
    assert not transfer.transitioning
    assert transfer.active_version == "belief_310"
    transfer.note_execution("BRAKE", np.zeros(6), actuation_enabled=True,
                            filter_unchanged=True, torque_unsaturated=True)
    assert not transfer.snapshot()["realized_track"]
    apply(transfer, new, 7.280)
    transfer.note_execution("TRACK", np.zeros(6), actuation_enabled=True,
                            filter_unchanged=True, torque_unsaturated=True)
    assert transfer.snapshot()["realized_track"]
    assert transfer.last_realized_version == "belief_310"


def test_update_during_transfer_queues_latest_without_restarting_alpha():
    old, first, newer = model(0), model(10), model(20)
    transfer = BumplessHumanActionTransfer(old, initial_version="prior", duration_s=.25,
                                           small_direct_action_change_nm=.19)
    transfer.offer(first, version="belief_1", time_s=0)
    apply(transfer, first, 0)
    before=apply(transfer, first, .1)
    transfer.offer(newer, version="belief_2", time_s=.1)
    at_same_time=apply(transfer, newer, .1)
    assert np.array_equal(at_same_time,before)
    assert transfer.start_time_s==0
    assert transfer.snapshot()["accepted_version"]=="belief_2"
    assert transfer.snapshot()["locked_target_version"]=="belief_1"
    assert np.array_equal(apply(transfer,newer,.25),first.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.active_version=="belief_1"
    assert np.array_equal(apply(transfer,newer,.252),first.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.snapshot()["event"]=="WAITING_FOR_REALIZATION"
    transfer.note_execution("TRACK",np.zeros(6),actuation_enabled=True,
                            filter_unchanged=True,torque_unsaturated=True)
    assert np.array_equal(apply(transfer,newer,.255),first.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert np.array_equal(apply(transfer,newer,.505),newer.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.active_version=="belief_2"


def test_identical_and_small_updates_take_control_without_transition():
    old, equal, small = model(0), model(0), model(.1)
    transfer = BumplessHumanActionTransfer(old, initial_version="prior", duration_s=.25,
                                           small_direct_action_change_nm=.19)
    transfer.offer(equal,version="same",time_s=0)
    assert np.array_equal(apply(transfer,equal,0),equal.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.active_version=="same"
    transfer.offer(small,version="small",time_s=.005)
    assert np.array_equal(apply(transfer,small,.005),small.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert not transfer.transitioning
    assert transfer.active_version=="small"
    assert any(x["event"]=="DIRECT_SMALL_CHANGE" for x in transfer.events)


def test_invalid_promotion_fails_closed_without_reverse_snap():
    old, new, invalid = model(0), model(18), model(float("nan"))
    transfer = BumplessHumanActionTransfer(old, initial_version="prior", duration_s=.25,
                                           small_direct_action_change_nm=.19)
    transfer.offer(new,version="valid",time_s=0)
    apply(transfer,new,0)
    transfer.offer(invalid,version="invalid",time_s=.005)
    with pytest.raises(RuntimeError,match="MODEL_TRANSFER_REJECTED"):
        apply(transfer,new,.005)
    assert transfer.active_version=="prior"
    assert transfer.start_time_s==0
    assert any(x["event"]=="REJECTED_INVALID" for x in transfer.events)


def test_noncausal_timestamp_is_rejected():
    old=model(0)
    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                         small_direct_action_change_nm=.19)
    apply(transfer,old,1.0)
    with pytest.raises(RuntimeError,match="NONCAUSAL"):
        apply(transfer,old,.9)


def test_verified_executed_action_anchor_is_exact_and_exits_without_offset():
    old,new=model(0),model(18)
    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                         small_direct_action_change_nm=.19)
    transfer.offer(new,version="candidate",time_s=0)
    predecessor=np.array([3.25,-1.0])
    target=new.inverse_dynamics(STATE[:2],STATE[2:],ACC)
    assert np.array_equal(transfer.apply(STATE,ACC,target,0,
                          previous_executed_action_nm=predecessor,
                          previous_action_verified=True),predecessor)
    assert np.array_equal(transfer.apply(STATE,ACC,target,.25,
                          previous_executed_action_nm=predecessor,
                          previous_action_verified=True),target)
    assert transfer.snapshot()["fraction_new"]==1
    assert transfer.active_version=="candidate"


def test_unverified_predecessor_aborts_before_starting_transfer():
    old,new=model(0),model(18)
    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                         small_direct_action_change_nm=.19)
    transfer.offer(new,version="candidate",time_s=0)
    target=new.inverse_dynamics(STATE[:2],STATE[2:],ACC)
    with pytest.raises(RuntimeError,match="UNVERIFIED_PREVIOUS_ACTION"):
        transfer.apply(STATE,ACC,target,0,
                       previous_executed_action_nm=np.zeros(2),
                       previous_action_verified=False)
    assert not transfer.transitioning


def test_repeated_20ms_updates_preserve_locked_deadline_and_latest_queue():
    old, first = model(0), model(10)
    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                         small_direct_action_change_nm=.19)
    transfer.offer(first,version="belief_1",time_s=0)
    apply(transfer,first,0)
    latest=first
    for index in range(1,13):
        when=.02*index
        latest=model(10+index)
        transfer.offer(latest,version=f"belief_{index+1}",time_s=when)
        applied=apply(transfer,latest,when)
        alpha=transfer.snapshot()["fraction_new"]
        expected=(1-alpha)*old.inverse_dynamics(STATE[:2],STATE[2:],ACC)+alpha*first.inverse_dynamics(STATE[:2],STATE[2:],ACC)
        assert np.allclose(applied,expected)
        assert transfer.start_time_s==0
        assert transfer.snapshot()["locked_target_version"]=="belief_1"
    applied=apply(transfer,latest,.25)
    assert np.array_equal(applied,first.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.active_version=="belief_1"
    assert transfer.accepted_version=="belief_13"
    transfer.note_execution("TRACK",np.zeros(6),actuation_enabled=True,
                            filter_unchanged=True,torque_unsaturated=True)
    assert transfer.last_realized_version=="belief_1"
    assert np.array_equal(apply(transfer,latest,.255),applied)
    assert transfer.start_time_s==.255
    assert np.array_equal(apply(transfer,latest,.505),latest.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    transfer.note_execution("TRACK",np.zeros(6),actuation_enabled=True,
                            filter_unchanged=True,torque_unsaturated=True)
    assert transfer.last_realized_version=="belief_13"
    assert len([x for x in transfer.events if x["event"]=="QUEUED_SUPERSEDE"])==12


def test_action_gap_scaled_duration_is_finite_and_large_event_keeps_250ms():
    policy={"kind":"action_gap_scaled_quintic_rate",
            "minimum_duration_s":.05,"quintic_max_slope":1.875,
            "conservative_robot_to_human_action_mapping":2.0,
            "engineering_factor":1.25,"ordinary_robot_step_max_nm":.34350449,
            "robot_step_gate_nm":2.06}
    old=model(0)
    small=model(2)
    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                         small_direct_action_change_nm=.19,
                                         duration_policy=policy)
    transfer.offer(small,version="belief_1",time_s=0)
    assert np.array_equal(apply(transfer,small,0),old.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.current_duration_s==.05
    assert np.array_equal(apply(transfer,small,.05),small.inverse_dynamics(STATE[:2],STATE[2:],ACC))
    assert transfer.active_version=="belief_1"

    large=model(18.24)
    second=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.25,
                                       small_direct_action_change_nm=.19,
                                       duration_policy=policy)
    second.offer(large,version="belief_large",time_s=0)
    apply(second,large,0)
    assert .249 < second.current_duration_s < .250
    assert second.transitioning
    apply(second,large,.25)
    assert second.active_version=="belief_large"


def test_output_envelope_limits_control_effect_and_still_reaches_new_model():
    old,new=model(0),model(2)
    gates={"human_action_step_nm":1.30,"desired_force_step_n":2.69,
           "desired_moment_step_nm":.58,"cr12_torque_step_nm":2.06,
           "max_duration_multiplier":20.0}

    def preview(actions):
        values=np.asarray(actions)
        force=np.zeros((len(values),3))
        moment=np.zeros((len(values),3))
        torque=np.zeros((len(values),6))
        force[:,0]=5*values[:,0]
        moment[:,1]=values[:,0]
        torque[:,0]=50*values[:,0]
        return {"force":force,"moment":moment,"torque":torque}

    transfer=BumplessHumanActionTransfer(old,initial_version="prior",duration_s=.05,
                                         small_direct_action_change_nm=.19,
                                         output_envelope=gates)
    transfer.offer(new,version="belief_new",time_s=0)
    previous_action=old.inverse_dynamics(STATE[:2],STATE[2:],ACC)
    outputs=preview(previous_action[np.newaxis,:])
    previous={"action":previous_action,"force":outputs["force"][0],
              "moment":outputs["moment"][0],"torque":outputs["torque"][0]}
    for index in range(201):
        t=.005*index
        action=transfer.apply(
            STATE,ACC,new.inverse_dynamics(STATE[:2],STATE[2:],ACC),t,
            previous_executed_action_nm=previous["action"],
            previous_action_verified=True,
            output_preview=preview,previous_executed_output=previous,
        )
        shown=preview(action[np.newaxis,:])
        current={"action":action,"force":shown["force"][0],
                 "moment":shown["moment"][0],"torque":shown["torque"][0]}
        for field,gate in (("action",1.30),("force",2.69),
                           ("moment",.58),("torque",2.06)):
            assert np.linalg.norm(current[field]-previous[field])<=gate+1e-8
        transfer.note_execution("TRACK",current["torque"],actuation_enabled=True,
                                filter_unchanged=True,torque_unsaturated=True,
                                desired_force_n=current["force"],
                                desired_moment_nm=current["moment"])
        previous=current
        if transfer.last_realized_version=="belief_new":
            break
    assert t>.05
    assert t<1.0
    assert np.array_equal(action,new.inverse_dynamics(STATE[:2],STATE[2:],ACC))
