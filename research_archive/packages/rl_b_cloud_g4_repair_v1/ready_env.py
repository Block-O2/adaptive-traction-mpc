"""Isolated training-only accounting revision; native executor is byte-unchanged.

Failure telescopes progress back to zero. gamma=1 is mandatory in the finite
task PPO config so waiting/cycling cannot amplify potential shaping by discount.
Infrastructure/resource exceptions never become scientific task failures.
"""
from training_env import TrainingEvidenceEnv
from pure_rl_env import PureCoordinationEnv
from common import put
import numpy as np

def completion_evidence(summary,phases):
 if not summary or summary.get('status')!='COMPLETE' or summary.get('abort_reason'):return False
 task=summary.get('task',{});transitions=task.get('phase_transitions',[])
 return (phases==['OUTBOUND','HOLD','RETURN'] and
         [(x.get('from'),x.get('to')) for x in transitions]==[('OUTBOUND','HOLD'),('HOLD','RETURN'),('RETURN','COMPLETE')] and
         task.get('physics_duration_s',0)>=19.-1e-8 and task.get('physics_duration_s',float('inf'))<=30.+1e-8 and
         transitions[-1].get('trigger')=='causal_return_actual_completion_commit')

class ReadyEnv(TrainingEvidenceEnv):
 def __init__(self,*args,guard=None,**kwargs):
  self.guard=guard;self.seed_cursor=0;self.base_seed=None
  super().__init__(*args,**kwargs)
 def _stop_check(self):
  if self.guard:self.guard.check()
  super()._stop_check()
 def reset(self,*,seed=None,options=None):
  # Honor Gym/SB3 seed, and continue the actual env RNG on automatic resets.
  # Retained native nominal physics is deterministic; action RNG is seeded.
  if seed is not None:self.base_seed=int(seed);self.seed_cursor=0
  if self.base_seed is None:self.base_seed=20261021
  self.episode_seed=self.base_seed+self.seed_cursor;self.seed_cursor+=1
  if self.tick_stream is not None:self.tick_stream.close();self.tick_stream=None
  return PureCoordinationEnv.reset(self,seed=self.episode_seed,options=options)
 def _reward(self,success=False,failure=False):
  if success and not completion_evidence(self.summary,self.phases):raise RuntimeError('COMPLETE_WITHOUT_FULL_TASK_EVIDENCE')
  if failure:
   # The sum of all progress terms is exactly zero on a failed episode.
   self.phi=0.
  return super()._reward(success,failure)
 def step(self,action):
  result=super().step(action)
  if result[2]:
   info=result[4]
   info['termination_contract']='finite_task_terminal_v2'
   info['proposed_action']=np.asarray(action,dtype=float).tolist()
   info['proposal_is_applied_action']=False
   info['reward_success_evidence']=completion_evidence(self.summary,self.phases)
  return result
 def tick(self,*args,**kwargs):
  super().tick(*args,**kwargs)
  # Override only the reward contract metadata to disclose v2 failure shaping.
  if not getattr(self,'_contract_written_episode',None)==self.episode_index:
   self._contract_written_episode=self.episode_index
   put(self.episode_dir/'reward_v2_contract.json',{'gamma':1.,'failure_potential':0.,'failure_total_progress':0.,'completion_evidence':'native full OUTBOUND/HOLD/RETURN/COMPLETE + causal commit','hard_safety':'unchanged, independent of reward','timeouts':'finite observed MDP deadlines: terminated=True,truncated=False','resource_or_owner_stop':'exception, not a task terminal'})
