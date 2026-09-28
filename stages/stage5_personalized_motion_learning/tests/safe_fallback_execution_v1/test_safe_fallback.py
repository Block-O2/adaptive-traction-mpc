import json,pickle,sys
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'stages/stage5_personalized_motion_learning'
for p in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src','stages/stage3_full3d/src'):sys.path.insert(0,str(ROOT/p))
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision,FallbackLatch,braking_duration
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanLifecycle
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.human_waypoint_feedback_mpc import FeedbackCandidateEvaluationV1,HumanWaypointFeedbackDecisionV1
from traction_mpc_stage5.high_rom_v1 import deployable_prior,CONFIG_PATH
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase

@pytest.fixture(scope='module')
def prepared():
    doc=STAGE/'results/simulation_research_baseline_v1/development49/high_rom_function_fresh_03_v1/summary.json'
    d=json.loads(doc.read_text());rec=d['learning_records'][-1];b=rec['adaptive_state'];raw=d['decisions'][rec['decision_index']]
    g=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in b['effective_geometry'].items()})
    belief=AdaptiveHumanBeliefV22(geometry=g,rom_human=deployable_prior(),**{k:b[k] for k in ('beta','state_residual_weights_nm','sequence','dynamics_sample_count','accepted_beta_update_count','residual_update_count')})
    spec=replace(load_goal_task_spec(CONFIG_PATH),start_return_target_rad=tuple(np.radians([6.,11.])))
    clearance=CombinedRigidTableClearanceV1(SessionClearanceContract(g),RigidTableReferenceEnvelopeV1(g),True)
    scheduler=QuinticHumanWaypointSchedulerV1(spec,belief.human_model(),clearance_evaluator=clearance,require_continuous_nonpenetrating_path=True,preserve_task_endpoint_clearance_floor=True,reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
    selected=rec['selected_plan'];sr=selected['schedule'];phase=TaskPhase(sr['phase'])
    candidate=HumanWaypointCandidate(selected['label'],phase,np.asarray(spec.start_return_target_rad),np.asarray(sr['target_q_rad']),np.asarray(sr['target_dq_rad_s']))
    schedule=scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=sr['start_q_rad'],current_dq_hat_rad_s=sr['start_dq_rad_s'],candidate=candidate,duration_s=sr['duration_s'],phase_elapsed_s=raw['phase_elapsed_s'])
    evaluation=FeedbackCandidateEvaluationV1(**{k:selected[k] for k in ('label','proposed_delta_q_rad','target_q_rad','feasible','rejection_reason','total_cost','cost_terms','execution_screen')},schedule=schedule)
    decision=HumanWaypointFeedbackDecisionV1(phase,raw['phase_elapsed_s'],raw['phase_remaining_s'],np.asarray(raw['deployable_state_rad_rad_s']),np.asarray(raw['reference_state_rad_rad_s']),evaluation,evaluation,'greedy',0,(evaluation,),raw['runtime_ms'])
    return decision,prepare_decision(decision,SimpleNamespace(scheduler=scheduler),belief)

def test_normal_primary_has_no_fallback(prepared):
    original,new=prepared;latch=FallbackLatch(new.executed.schedule.safe_escape)
    assert latch.choose_primary(validated=True,age_ns=30_000_000)
    assert not latch.commit() and latch.mode=='PRIMARY'
    for t in np.linspace(0,original.executed.schedule.duration_s,101):
        a,b=original.executed.schedule.sample(t),new.executed.schedule.sample(t)
        for k in ('q_rad','dq_rad_s','ddq_rad_s2'):np.testing.assert_array_equal(getattr(a,k),getattr(b,k))

def test_candidate_ranking_unchanged(prepared):
    old,new=prepared
    assert old.executed.total_cost==new.executed.total_cost
    assert old.executed.cost_terms==new.executed.cost_terms
    assert old.executed.label==new.executed.label and len(old.evaluations)==len(new.evaluations)

def test_not_ready_is_committed_before_endpoint(prepared):
    b=prepared[1].executed.schedule.safe_escape;l=FallbackLatch(b)
    assert l.cap(100.)==b.commit_progress_s<b.bridge.duration_s
    assert l.commit() and l.mode=='BRAKING'

def test_c2_at_fork_and_stationary_end(prepared):
    b=prepared[1].executed.schedule.safe_escape;a=b.bridge.sample(b.commit_progress_s);z=b.stop.sample(0)
    for k in ('q_rad','dq_rad_s','ddq_rad_s2'):np.testing.assert_allclose(getattr(a,k),getattr(z,k),atol=1e-10,rtol=0)
    end=b.stop.sample(b.stop.duration_s)
    np.testing.assert_allclose(np.r_[end.dq_rad_s,end.ddq_rad_s2],0,atol=1e-10)

def test_late_valid_primary_cannot_interrupt(prepared):
    l=FallbackLatch(prepared[1].executed.schedule.safe_escape);l.commit()
    assert not l.choose_primary(validated=True,age_ns=50_000_000)
    assert not l.resume(fresh=True,validated=True,age_ns=0)
    assert l.mode=='BRAKING'

def test_hold_requires_fresh_valid_resume(prepared):
    l=FallbackLatch(prepared[1].executed.schedule.safe_escape);l.commit();l.stopped()
    assert not l.resume(fresh=False,validated=True,age_ns=20_000_000)
    assert not l.resume(fresh=True,validated=False,age_ns=20_000_000)
    assert not l.resume(fresh=True,validated=True,age_ns=100_000_000)
    assert l.resume(fresh=True,validated=True,age_ns=20_000_000)

@pytest.mark.parametrize('age',[100_000_000,200_000_000])
def test_original_lifecycle_stale_never_applies(age):
    clock=[0];l=PlanLifecycle(clock=lambda:clock[0]);l.capture(0.,0);r=l.request('TASK',0.,asynchronous=True)
    clock[0]=age;applied=[]
    assert l.expired(r)
    with pytest.raises(RuntimeError,match='STALE_PLAN_MAXIMUM_AGE'):l.activate(r,lambda:applied.append(True))
    assert not applied and l.records()[0]['outcome']=='EXPIRED'

def test_fresh_actual_lifecycle_resume():
    clock=[200_000_000];l=PlanLifecycle(clock=lambda:clock[0]);l.capture(2.,clock[0]);r=l.request('TASK',2.,asynchronous=True)
    clock[0]+=20_000_000;applied=[];l.activate(r,lambda:applied.append(True))
    assert applied and l.records()[0]['outcome']=='ACTIVATED'

def test_braking_duration_comes_from_limits():
    assert braking_duration(np.radians([-12,-20]),np.radians([75,150]),.005)==.24
    assert braking_duration(np.radians([-24,-40]),np.radians([75,150]),.005)==.48

def test_prevalidation_and_snapshot_survive_pickle(prepared):
    p=pickle.loads(pickle.dumps(prepared[1]));b=p.executed.schedule.safe_escape
    assert b.certificate['stop_mechanics']['feasible'] and not b.certificate['truth_consumed']
    assert b.certificate['shifted_rom_valid'] and b.certificate['shifted_lower_m']>=0
    assert b.commit_progress_s==.035
