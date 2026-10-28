"""Versioned pilot reward and complete-episode evidence, no native execution edits."""
from ready_env import ReadyEnv,completion_evidence
from common import ROOT,put,clean
import json,time,os,numpy as np

class PilotEnv(ReadyEnv):
 def __init__(self,*args,budget=None,category='DEVELOPMENT_TRAINING',**kwargs):
  self.budget=budget;self.category=category;self.end_written=True;self.rows_saved=[]
  super().__init__(*args,**kwargs)
 def _stop_check(self):
  super()._stop_check()
  if self.budget:
   if time.time()>=self.budget['hard_stop_unix']:raise RuntimeError('CAMPAIGN_HARD_STOP')
   plant=self.capture.get('runtime',{}).get('plant') if hasattr(self,'capture') else None
   current=round(float(plant.data.time)/.00025) if plant is not None else 0
   if self.budget['native_steps']+current>self.budget['native_steps_hard_cap']:raise RuntimeError('NATIVE_STEP_HARD_CAP')
 def reset(self,*,seed=None,options=None):
  if self.budget and time.time()>=self.budget['no_new_physics_after_unix']:raise RuntimeError('NO_NEW_PHYSICS_WINDOW')
  self.rows_saved=[]
  obs,info=super().reset(seed=seed,options=options);self.end_written=False
  put(self.episode_dir/'EPISODE_START.json',{'unix':time.time(),'pid':os.getpid(),'seed':self.episode_seed,'category':self.category,'physics_start_s':self.physics_at_reset,'reward':'pilot_v3_failure_cost_floor'})
  return obs,info
 def _reward(self,success=False,failure=False):
  r,parts=super()._reward(success,failure)
  if failure:
   cost=-self.reward_totals['force']-self.reward_totals['variation']
   padding=max(0.,1.5-cost)
   parts['completion']-=padding;self.reward_totals['completion']-=padding;r-=padding
  return r,parts
 def tick(self,*args,**kwargs):
  super().tick(*args,**kwargs)
  if getattr(self,'_pilot_contract_episode',None)!=self.episode_index:
   self._pilot_contract_episode=self.episode_index
   put(self.episode_dir/'pilot_reward_contract.json',{'version':'pilot_v3_failure_cost_floor','gamma':1.,'failure_cost_floor':1.5,'failure_progress_potential':0.,'failure_base_penalty':-10.,'failure_completion':'-10-max(0,1.5-observed_force_and_variation_cost)','failure_total_return':'-10-max(1.5,observed_cost)-5*initial_potential','cost_bound_derivation':'200N*30s*.02/100=1.2; normalized acceleration square integral <=30s gives .3; safety independent'})
 def step(self,action):
  if self.budget:
   self.budget['rl_decisions']+=1
   if self.budget['rl_decisions']>self.budget['rl_decisions_hard_cap']:raise RuntimeError('RL_DECISION_HARD_CAP')
  before=self.last_obs.copy();obs,r,t,tr,info=super().step(action)
  self.rows_saved.append((before,np.asarray(action).copy(),r,obs.copy(),t,tr))
  if t or tr:
   z=self.rows_saved
   np.savez_compressed(self.output_dir.parent/f'transitions_{self.episode_index-1}.npz',obs=[x[0] for x in z],actions=[x[1] for x in z],rewards=[x[2] for x in z],next_obs=[x[3] for x in z],terminated=[x[4] for x in z],truncated=[x[5] for x in z])
   put(self.output_dir.parent/f'episode_{self.episode_index-1}.json',info)
  return obs,r,t,tr,info
 def close(self):
  owner=getattr(self,'thread',None);ep=getattr(self,'episode_dir',None);summary=getattr(self,'summary',None)
  native=self.metrics()['native_steps_total'] if getattr(self,'capture',{}).get('runtime',{}).get('plant') is not None else 0
  super().close()
  if ep is not None and not self.end_written:
   put(ep/'EPISODE_END.json',{'unix':time.time(),'owner_joined':owner is None or not owner.is_alive(),'capture_cleared':not self.capture,'status':None if summary is None else summary.get('status'),'partial_abandoned':summary is None,'native_steps':native,'category':self.category})
   self.end_written=True
