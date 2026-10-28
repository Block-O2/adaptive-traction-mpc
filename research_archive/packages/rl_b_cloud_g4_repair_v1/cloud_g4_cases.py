"""Bounded supplementary G4 tests. Never changes original task, model or safety.

Natural policies and TEST_ONLY phase-exit suppression have separate categories.
The latter uses genuine MuJoCo but is never substituted for natural failure evidence.
"""
from common import ROOT,put,clean
import argparse,os,time,json,numpy as np

def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--case',required=True,choices=['slow','return_hold','outbound_timeout_injection','hold_timeout_injection','return_timeout_injection','reset_maximal']);p.add_argument('--out',required=True);a=p.parse_args()
 if not a.enable or os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('EXPLICIT_ENABLE_AND_GUARD_REQUIRED')
 out=ROOT/a.out;out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 from runtime_setup import install
 install()
 from ready_env import ReadyEnv
 injected=a.case.endswith('_injection');target=a.case.removesuffix('_timeout_injection').upper() if injected else None
 class CaseEnv(ReadyEnv):
  def transition_allowed(self,state):
   if injected and state.phase.value==target:return False
   return super().transition_allowed(state)
 env=CaseEnv(out/'env',retain_trace=True);results=[];resets=[];initial_observations=[]
 try:
  for repeat in range(2 if a.case=='reset_maximal' else 1):
   obs,info=env.reset(seed=20261021);initial_observations.append(obs.copy());rows=[]
   reset={'episode_index':env.episode_index,'steps':env.steps,'force_integral':env.force_integral,'moment_integral':env.moment_integral,'reward_totals':dict(env.reward_totals),'action_rows':len(env.rows),'rejections':env.rejections,'accepted':env.accepted,'events_empty':env.events.empty(),'actions_empty':env.actions.empty(),'owner_alive':env.thread.is_alive(),'task_s':env.last_task_time,'seed':env.episode_seed}
   resets.append(reset);put(out/f'reset_{repeat}.json',reset)
   term=trunc=False;reward_sum=0.
   for i in range(128):
    phase=info.get('phase')
    value=-.8 if a.case=='slow' else (-1. if a.case=='return_hold' and phase=='RETURN' else 1.)
    action=np.full(2,value,np.float32);before=obs.copy();obs,reward,term,trunc,info=env.step(action);reward_sum+=reward
    rows.append((before,action,reward,obs.copy(),term,trunc));print('DECISION',repeat,i+1,env.last_task_time,info.get('phase'),flush=True)
    if term or trunc:break
   if not term and not trunc:raise RuntimeError('128_DECISION_BUDGET_WITHOUT_TERMINAL')
   metrics=env.metrics();metrics.update(status=info.get('status'),abort_reason=info.get('abort_reason'),success=info.get('success',False),terminated=term,truncated=trunc,seed=20261021,reward_sum=reward_sum)
   results.append(metrics);put(out/f'episode_{repeat}.json',metrics)
   np.savez_compressed(out/f'transitions_{repeat}.npz',obs=[x[0] for x in rows],actions=[x[1] for x in rows],rewards=[x[2] for x in rows],next_obs=[x[3] for x in rows],terminated=[x[4] for x in rows],truncated=[x[5] for x in rows])
   owner=env.thread;env.close()
   put(out/f'owner_close_{repeat}.json',{'owner_joined':not owner.is_alive(),'thread_cleared':env.thread is None,'capture_cleared':not env.capture,'summary_cleared':env.summary is None,'pending_cleared':not env.pending})
  reset_checks=None
  if len(results)==2:
   reset_checks={'initial_observations_equal':bool(np.array_equal(*initial_observations)),'both_reset_counters_clean':all(x['steps']==0 and x['force_integral']==0 and x['moment_integral']==0 and not any(x['reward_totals'].values()) and x['action_rows']==0 and x['accepted']==0 and x['rejections']==0 and x['events_empty'] and x['actions_empty'] for x in resets),'both_full_complete':all(x['success'] for x in results),'new_episode_directory':resets[1]['episode_index']==resets[0]['episode_index']+1}
  put(out/'RESULT.json',{'category':'TEST_ONLY_WITH_REAL_MUJOCO' if injected else 'NATURAL_LEGAL_ACTION_REAL_MUJOCO','case':a.case,'injection':{'suppressed_phase_exit':target,'original_deadline_unchanged':True} if injected else None,'episodes':results,'resets':resets,'reset_checks':reset_checks,'original_physics_task_safety_modified':False})
 finally:env.close()
if __name__=='__main__':main()
