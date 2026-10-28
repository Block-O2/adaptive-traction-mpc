"""TEST_ONLY injection and mathematical G4 checks. No physical qualification."""
from common import ROOT,put,load_config
from ready_env import ReadyEnv,completion_evidence
from traction_mpc_stage5.task import TaskPhase,GoalTaskState,transition_phase,abort_episode
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from types import SimpleNamespace
import numpy as np,time
tests=[]
def check(name,fn):
 try:fn();tests.append({'test':name,'pass':True})
 except BaseException as e:tests.append({'test':name,'pass':False,'error':repr(e)})
def assert_(condition):
 if not condition:raise AssertionError('check failed')
case,_=load_config();_,_,spec,_=hidden_plant(case)
for phase in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN):
 def timeout(phase=phase):
  state=GoalTaskState(phase,spec.phase_timeout_s-.001,0.,True,phase==TaskPhase.RETURN)
  q=np.radians([60.,60.]);s=transition_phase(spec,state,q,[0.,0.],.005,ddq_rad_s2=[0.,0.])
  assert_(s.phase==TaskPhase.ABORTED and s.abort_reason=='TIMEOUT_'+phase.value)
 check('TEST_ONLY_'+phase.value+'_timeout',timeout)
 def safety(phase=phase):
  s=transition_phase(spec,GoalTaskState(phase,0.,0.,True,phase==TaskPhase.RETURN),np.radians([60.,60.]),[0.,0.],.005,ddq_rad_s2=[0.,0.],abort_reason='TEST_ONLY_SAFETY_TRIGGER')
  assert_(s.phase==TaskPhase.ABORTED and s.abort_reason=='TEST_ONLY_SAFETY_TRIGGER')
 check('TEST_ONLY_'+phase.value+'_safety_stop',safety)
def hold():
 state=GoalTaskState(TaskPhase.HOLD,0.,0.,True,False)
 s=transition_phase(spec,state,spec.outbound_goal_target_rad,[0.,0.],.005,ddq_rad_s2=[0.,0.]);assert_(s.phase==TaskPhase.HOLD)
 s=transition_phase(spec,s,spec.start_return_target_rad,[0.,0.],.005,ddq_rad_s2=[0.,0.]);assert_(s.hold_elapsed_s==0 and not s.outbound_hold_completed)
check('TEST_ONLY_HOLD_cannot_skip_and_dwell_resets',hold)
def failure_bound():
 env=ReadyEnv(ROOT/'test_outputs')
 for phi in np.linspace(0,3,301):
  env._initialize();env.phi=float(phi);env._reward();r,p=env._reward(failure=True)
  assert_(abs(env.reward_totals['progress'])<1e-12 and env.reward_totals['completion']==-10. and sum(env.reward_totals.values())<=-10.)
 env.close()
check('TEST_ONLY_all_partial_low_JF_failures_have_no_success_or_progress',failure_bound)
def hold_zero_reward():
 env=ReadyEnv(ROOT/'test_outputs');env._initialize();r,p=env._reward();assert_(r==0 and p['completion']==0);env.force_integral=10;assert_(env._reward()[0]<0);env.close()
check('TEST_ONLY_no_motion_no_free_force_reward',hold_zero_reward)
def terminal(reason):
 env=ReadyEnv(ROOT/'test_outputs');env._initialize();env.host_start=time.perf_counter();env.pending=True;env.episode_dir=ROOT/'test_outputs'/reason;env.phases=['OUTBOUND'];env.phi=.9;env._reward()
 env.thread=SimpleNamespace(join=lambda timeout:None,is_alive=lambda:False)
 env.events.put(('terminal',None,{'status':'ABORTED','abort_reason':reason}));o,r,t,tr,info=env.step(np.ones(2,np.float32))
 assert_(t and not tr and np.all(o==0) and not info['success'] and info['reward_parts']['completion']==-10. and sum(env.reward_totals.values())<=-10.)
 try:env.step(np.ones(2,np.float32));raise AssertionError('terminal can be stepped twice')
 except RuntimeError as e:assert_('STEP_REQUIRES_RESET' in str(e))
 env.close()
for reason in ('TIMEOUT_OUTBOUND','TIMEOUT_HOLD','TIMEOUT_RETURN','GLOBAL_TASK_TIMEOUT','ABSOLUTE_SAFETY_STOP','REPEATED_REJECTION'):
 check('TEST_ONLY_terminal_'+reason,lambda reason=reason:terminal(reason))
def bogus_complete():
 env=ReadyEnv(ROOT/'test_outputs');env._initialize();env.summary={'status':'COMPLETE'}
 try:env._reward(success=True);raise AssertionError('bogus completion accepted')
 except RuntimeError as e:assert_('COMPLETE_WITHOUT_FULL_TASK_EVIDENCE' in str(e))
 env.close()
check('TEST_ONLY_bogus_COMPLETE_rejected',bogus_complete)
def clean_reset():
 env=ReadyEnv(ROOT/'test_outputs');env._initialize();env.force_integral=100;env.phi=2.8;env.rows=[1];env.previous_rejected=1;env._initialize()
 assert_(env.force_integral==0 and env.phi==0 and not env.rows and env.previous_rejected==0 and env.events.empty() and env.actions.empty());env.close()
check('TEST_ONLY_initialize_clears_episode_accounting',clean_reset)
def rejection_fallback():
 from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import FallbackLatch
 from native_rl_env import NativeProposalEnv
 latch=FallbackLatch(SimpleNamespace(commit_progress_s=.035));assert_(latch.cap(.04)==.035)
 for _ in range(20):assert_(not latch.choose_primary(validated=False,age_ns=0))
 assert_(latch.commit() and not latch.choose_primary(validated=True,age_ns=0));latch.stopped()
 assert_(not latch.resume(fresh=False,validated=True,age_ns=0) and not latch.resume(fresh=True,validated=True,age_ns=100_000_000))
 assert_(latch.resume(fresh=True,validated=True,age_ns=99_999_999))
 env=ReadyEnv(ROOT/'test_outputs');env._initialize()
 records=[{'stage':'TASK','outcome':'FAILED'}]*20+[{'stage':'TASK','outcome':'PENDING'}]
 env.capture={'runtime':{'plan_lifecycle':SimpleNamespace(records=lambda:records)}};env._refresh_action_status()
 assert_(env.rejections==20 and env.accepted==0 and env.previous_rejected==1.)
 env.close()
check('TEST_ONLY_repeated_rejections_legal_fallback_and_fresh_resume',rejection_fallback)
def success_protocol():
 env=ReadyEnv(ROOT/'test_outputs');env._initialize();env.phases=['OUTBOUND','HOLD','RETURN']
 transitions=[{'from':a,'to':b} for a,b in [('OUTBOUND','HOLD'),('HOLD','RETURN'),('RETURN','COMPLETE')]];transitions[-1]['trigger']='causal_return_actual_completion_commit'
 env.summary={'status':'COMPLETE','abort_reason':None,'task':{'phase_transitions':transitions,'physics_duration_s':19.03}}
 env.phi=3.;r,p=env._reward(success=True);assert_(p['completion']==20 and r==35.)
 env.close()
check('TEST_ONLY_full_task_complete_bonus_once_via_pending_guard',success_protocol)
out={'category':'TEST_ONLY_NO_PHYSICS','pass':all(t['pass'] for t in tests),'tests':tests,'full_G4_physical_pass':False}
put(ROOT/'G4_UNIT_RESULTS.json',out);print(out)
if not out['pass']:raise SystemExit(1)
