"""UNQUALIFIED_TRAINING_SMOKE only. Does not open or modify formal readiness gates."""
from common import ROOT,put,clean,digest
from pathlib import Path
import argparse,os,time,json,random,hashlib,resource,traceback

def state_hash(obj):
 import torch,numpy as np
 h=hashlib.sha256()
 def visit(x):
  if isinstance(x,torch.Tensor):h.update(b'T');h.update(str(x.dtype).encode());h.update(str(tuple(x.shape)).encode());h.update(x.detach().cpu().numpy().tobytes())
  elif isinstance(x,np.ndarray):h.update(b'N');h.update(str(x.dtype).encode());h.update(x.tobytes())
  elif isinstance(x,dict):
   for k in sorted(x,key=str):visit(str(k));visit(x[k])
  elif isinstance(x,(list,tuple)):
   h.update(str(type(x)).encode())
   for v in x:visit(v)
  else:h.update(repr(x).encode())
 visit(obj);return h.hexdigest()
def snapshot(model):
 import torch,numpy as np
 from checkpoints import policy_hash
 return {'policy':policy_hash(model),'optimizer':state_hash(model.policy.optimizer.state_dict()),'rng':state_hash({'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state()}),'num_timesteps':model.num_timesteps,'n_updates':model._n_updates,'total_timesteps':model._total_timesteps,'progress_remaining':model._current_progress_remaining,'episode_num':model._episode_num}
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['initial','resume','evaluation'],required=True);p.add_argument('--out',required=True);p.add_argument('--checkpoint');a=p.parse_args()
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_RESOURCE_GUARD_REQUIRED')
 plan=json.loads((ROOT/'RUN_PLAN.json').read_text())
 if time.time()>=plan['no_new_physics_after_unix']:raise RuntimeError('NO_NEW_PHYSICS_TIME_BOUND')
 out=ROOT/a.out;out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 from runtime_setup import install
 install()
 import numpy as np,torch
 from stable_baselines3 import PPO
 from stable_baselines3.common.callbacks import BaseCallback
 from ready_env import ReadyEnv
 from resource_guard import Guard
 from checkpoints import save,load,contract,sha
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 seed=plan['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
 guard=Guard(out,seconds=550,max_output_gib=1.5).start()
 class EvidenceEnv(ReadyEnv):
  def __init__(self,*args,**kwargs):
   self.saved_rows=[];self.completed=[];self.end_written=True;self.eval_tail_decisions=0
   super().__init__(*args,**kwargs)
  def reset(self,*,seed=None,options=None):
   count=len(list((ROOT/'runs').glob('**/EPISODE_START.json')))
   if count>=plan['max_new_episodes'] or time.time()>=plan['no_new_physics_after_unix']:raise RuntimeError('EPISODE_OR_TIME_CAP')
   result=super().reset(seed=seed,options=options);self.saved_rows=[];self.end_written=False
   put(self.episode_dir/'EPISODE_START.json',{'unix':self.host_start,'pid':os.getpid(),'seed':self.episode_seed,'category':'UNQUALIFIED_TRAINING_SMOKE','contract_sha256':contract(),'task_plant_safety_unchanged':True,'stage':a.stage})
   return result
  def step(self,action):
   before=self.last_obs.copy();result=super().step(action);obs,r,t,tr,info=result
   self.saved_rows.append((before,np.asarray(action).copy(),r,obs.copy(),t,tr))
   if t or tr:
    i=self.episode_index-1;rows=self.saved_rows
    np.savez_compressed(out/f'transitions_{i}.npz',obs=[x[0] for x in rows],actions=[x[1] for x in rows],rewards=[x[2] for x in rows],next_obs=[x[3] for x in rows],terminated=[x[4] for x in rows],truncated=[x[5] for x in rows])
    self.completed.append({'episode_index':self.episode_index,'info':info})
    put(out/f'episode_{i}.json',info)
   return result
  def close(self):
   owner=getattr(self,'thread',None);ep=getattr(self,'episode_dir',None);summary=getattr(self,'summary',None)
   super().close()
   if ep is not None and not self.end_written:
    put(ep/'EPISODE_END.json',{'unix':time.time(),'owner_joined':owner is None or not owner.is_alive(),'capture_cleared':not self.capture,'terminal_status':None if summary is None else summary.get('status'),'partial_abandoned':summary is None,'category':'UNQUALIFIED_TRAINING_SMOKE'})
    self.end_written=True
 env=EvidenceEnv(out/'env',retain_trace=True,guard=guard)
 result={'category':'UNQUALIFIED_TRAINING_SMOKE','stage':a.stage,'pid':os.getpid(),'seed':seed,'learning_success_claim':False,'teacher_used':False};started=time.monotonic();updates=[];optimizer_steps=[];error=None;model=None
 try:
  if a.stage=='initial':
   model=PPO('MlpPolicy',env,n_steps=8,batch_size=4,n_epochs=1,gamma=1.,gae_lambda=.95,learning_rate=3e-4,clip_range=.2,ent_coef=0.,vf_coef=.5,max_grad_norm=.5,seed=seed,device='cpu',policy_kwargs={'net_arch':dict(pi=[16,16],vf=[16,16])},verbose=0)
  else:
   if not a.checkpoint:raise ValueError('CHECKPOINT_REQUIRED')
   model,metadata=load(ROOT/a.checkpoint,env)
   restored=snapshot(model);expected=metadata['state_snapshot'];checks={k:restored[k]==v for k,v in expected.items()}
   result['resume']={'expected':expected,'restored':restored,'checks':checks,'pass':all(checks.values()),'parent_sha256':metadata['model_sha256'],'fresh_physical_episode':True,'partial_rollout_discarded':True}
   if not all(checks.values()):raise RuntimeError('FULL_TRAINING_STATE_RESTORE_MISMATCH')
  result['before']=snapshot(model)
  if a.stage!='evaluation':
   optimizer=model.policy.optimizer;original_step=optimizer.step
   def step(*args,**kwargs):
    grads=[p.grad.detach() for p in model.policy.parameters() if p.grad is not None]
    norm=float(torch.sqrt(sum((g*g).sum() for g in grads)).item());finite=all(bool(torch.isfinite(g).all()) for g in grads)
    before=state_hash(model.policy.state_dict());value=original_step(*args,**kwargs)
    optimizer_steps.append({'gradient_l2':norm,'finite':finite,'weights_changed':before!=state_hash(model.policy.state_dict()),'optimizer_steps':sorted(set(int(s['step'].item()) for s in optimizer.state.values()))})
    return value
   optimizer.step=step
   original_train=model.train
   def train():
    original_train();updates.append({'num_timesteps':model.num_timesteps,'n_updates':model._n_updates,'losses':{k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and isinstance(v,(int,float,np.number))}})
   model.train=train
   class Callback(BaseCallback):
    def _on_step(self):guard.check();return True
   model.learn(total_timesteps=8,callback=Callback(),reset_num_timesteps=a.stage=='initial')
   # Finish the current real episode for independent terminal/reward audits.
   # These extra transitions do not enter PPO or its timestep counter.
   if env.pending:
    obs=env.last_obs.copy()
    for _ in range(128):
     action,_=model.predict(obs,deterministic=False);obs,_,t,tr,_=env.step(action);env.eval_tail_decisions+=1
     if t or tr:break
    else:raise RuntimeError('TAIL_DECISION_CAP')
   # Exclude instrumentation from SB3 serialization, retain native optimizer state.
   model.train=original_train;optimizer.step=original_step
   state=snapshot(model)
   record=save(model,out/'checkpoints/final',{'seed':seed,'episodes_completed':len(env.completed),'parent':a.checkpoint,'teacher_used':False,'state_snapshot':state,'category_label':'UNQUALIFIED_TRAINING_SMOKE','gradient_optimizer_steps_total':sum(int(s['step'].item()) for s in optimizer.state.values())})
   result['checkpoint']=record
  else:
   before_eval=snapshot(model);obs,_=env.reset(seed=seed)
   for _ in range(128):
    action,_=model.predict(obs,deterministic=True);obs,_,t,tr,info=env.step(action)
    if t or tr:break
   else:raise RuntimeError('EVALUATION_DECISION_CAP')
   result['evaluation']={'episodes':len(env.completed),'runtime_task_success':bool(info.get('success')),'task_s':info.get('task_s'),'status':info.get('status'),'abort_reason':info.get('abort_reason'),'policy_frozen':snapshot(model)['policy']==before_eval['policy'],'optimizer_frozen':snapshot(model)['optimizer']==before_eval['optimizer']}
  result['after']=snapshot(model);result['updates']=updates;result['optimizer_steps']=optimizer_steps;result['tail_decisions_not_used_in_update']=env.eval_tail_decisions;result['episodes']=env.completed
  result['update_pass']=bool(updates and optimizer_steps and all(x['finite'] and x['gradient_l2']>0 and x['weights_changed'] for x in optimizer_steps) and result['after']['policy']!=result['before']['policy']) if a.stage!='evaluation' else None
 except BaseException as e:
  error=f'{type(e).__name__}:{e}';result['traceback']=traceback.format_exc();raise
 finally:
  try:env.close()
  finally:
   result.update(error=error,wall_s=time.monotonic()-started,resources=guard.close(),cpu_user_s=resource.getrusage(resource.RUSAGE_SELF).ru_utime,cpu_system_s=resource.getrusage(resource.RUSAGE_SELF).ru_stime,peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
   put(out/'RESULT.json',result)
if __name__=='__main__':main()
