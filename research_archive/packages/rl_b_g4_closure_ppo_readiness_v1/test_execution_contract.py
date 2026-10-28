"""Adversarial interface/lifecycle unit tests; never labelled real physics."""
from common import ROOT,put
from types import SimpleNamespace
from pathlib import Path
import numpy as np,ast,time
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanLifecycle
from traction_mpc_stage5.full3d_adaptive_integration_v1.execution_policy import ScientificPlanLifecycle,SimulationVersion
from traction_mpc_stage5.full3d_adaptive_integration_v1.rl_native_proposal import NativeRateProposalPlanner
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.task import TaskPhase
results=[]
def test(name,fn):
    try:fn();results.append({'test':name,'pass':True})
    except BaseException as e:results.append({'test':name,'pass':False,'error':repr(e)})
def raises(fn):
    try:fn()
    except (ValueError,RuntimeError,KeyError):return
    raise AssertionError('negative test unexpectedly accepted')
def immutable_capture():
    life=PlanLifecycle(clock=lambda:30);life.capture(1.,10);life.capture(1.,20)
    req=life.request('TASK',1.,asynchronous=False);assert req.sensor_capture_ns==10
    life.mark(req,'worker_start_ns',11);raises(lambda:life.mark(req,'worker_start_ns',12));life.close('TEST')
def expiry():
    plant=SimpleNamespace(data=SimpleNamespace(time=1.));session=SimpleNamespace(plant=plant)
    epoch=['A']
    def version():return SimulationVersion(epoch[0],0,round(plant.data.time/.00025),plant.data.time,0,'b','r')
    life=ScientificPlanLifecycle(session,version_provider=version);life.capture(1.,1)
    req=life.request('TASK',1.,asynchronous=False);life.mark(req,'worker_start_ns');life.mark(req,'compute_finish_ns')
    plant.data.time=1.095;assert not life.expired(req)
    plant.data.time=1.100;assert life.expired(req)
    called=[];raises(lambda:life.activate(req,lambda:called.append(True)));assert not called;life.close('TEST')
def epoch_stale():
    plant=SimpleNamespace(data=SimpleNamespace(time=1.));epoch=['A']
    def version():return SimulationVersion(epoch[0],0,4000,1.,0,'b','r')
    life=ScientificPlanLifecycle(SimpleNamespace(plant=plant),version_provider=version);life.capture(1.,1)
    req=life.request('TASK',1.,asynchronous=False);life.mark(req,'worker_start_ns');life.mark(req,'compute_finish_ns');epoch[0]='B'
    assert life.expired(req);life.close('TEST')
def action_contract():
    p=NativeRateProposalPlanner.__new__(NativeRateProposalPlanner)
    p.config=HumanWaypointFeedbackMPCConfigV1();p.span_rad=np.radians([115.,110.]);p.internal_reference_target_rad=np.radians([120.,120.])
    start=np.radians([5.,10.])
    for bad in ([np.nan,0],[2,0],[0],np.inf):raises(lambda:p.set_rl_action(bad,0,0.))
    p.set_rl_action([-1,-1],0,0.);assert np.array_equal(p.candidate_actions(start,TaskPhase.OUTBOUND)[0],np.zeros(2))
    p.set_rl_action([1,1],1,0.);assert np.allclose(p.candidate_actions(start,TaskPhase.OUTBOUND)[0],p.span_rad*.2)
    assert np.allclose(p.candidate_actions(start,TaskPhase.HOLD)[0],p.internal_reference_target_rad-start)
    near=np.radians([119.9,119.9]);assert np.allclose(p.candidate_actions(near,TaskPhase.OUTBOUND)[0],p.internal_reference_target_rad-near)
def actor_firewall():
    for filename,names in [('pure_rl_env.py',{'_observation'}),('native_rl_env.py',{'_callback','_refresh_action_status'})]:
        tree=ast.parse((ROOT/filename).read_text());nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
        assert nodes
        for n in nodes:
            attrs={x.attr for x in ast.walk(n) if isinstance(x,ast.Attribute)}
            assert not (attrs&{'qpos','qvel','qacc','native_states','plant','human_qpos_indices'}),attrs
def runtime_branch():
    from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as rt
    src=Path(rt.__file__).read_text()
    assert src.count('native_proposal_callback(')==1
    block=src[src.index('if native_proposal_callback is not None:\n                    # One policy'):src.index('payload = snapshot_task_call(adaptive_planner, arguments)')]
    assert block.index('native_proposal_callback(')<block.index('lifecycle.request(')
    assert 'planner.set_rl_action(' in block and 'source_sample_s' in block
for n,fn in [('source_age_not_refreshed',immutable_capture),('100ms_expiry_rejects_before_apply',expiry),('episode_epoch_mismatch',epoch_stale),('action_boundary_nan_and_hold',action_contract),('actor_source_allowlist',actor_firewall),('policy_before_original_snapshot_request',runtime_branch)]:test(n,fn)
out={'evidence_category':'SOURCE_AND_INTERFACE_UNIT_TESTS_ONLY','tests':results,'pass':all(x['pass'] for x in results),'physical_parity':'NOT_ESTABLISHED_BY_UNIT_TESTS'}
put(ROOT/'EXECUTION_CONTRACT_TESTS.json',out);print(out)
