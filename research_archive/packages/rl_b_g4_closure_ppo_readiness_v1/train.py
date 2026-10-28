"""One-env native-event PPO. Explicit enable plus content-addressed G4 gate."""
from common import ROOT,put,clean
import argparse,json,os,time,random,hashlib
def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--profile',choices=['smoke','pilot','future_1m'],default='smoke');p.add_argument('--seed',type=int,default=20261021);p.add_argument('--out',required=True);p.add_argument('--resume');p.add_argument('--decisions',type=int);a=p.parse_args()
 if not a.enable:raise RuntimeError('DISABLED_REQUIRE_EXPLICIT_ENABLE')
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_RESOURCE_GUARD_REQUIRED')
 from checkpoints import contract
 from preflight import runtime
 gate=json.loads((ROOT/'READINESS.json').read_text())
 if not all(gate.get(k)=='PASS' for k in ('G4_TERMINATION_REWARD_PASS','RL_EXECUTION_CONTRACT_PASS','RL_TASK_REACHABILITY_PASS')) or gate.get('contract_sha256')!=contract() or gate.get('runtime')!=runtime():raise RuntimeError('CURRENT_RUNTIME_QUALIFICATION_REQUIRED')
 cfg=json.loads((ROOT/'CLOUD_TRAINING_CONFIG.json').read_text());profile=cfg['profiles'][a.profile]
 if a.seed not in cfg['seeds'] or cfg['gamma']!=1. or cfg['physics_envs']!=1:raise ValueError('TRAINING_CONTRACT')
 out=(ROOT/a.out).resolve()
 if not out.is_relative_to(ROOT/'runs'):raise ValueError('OUTPUT_MUST_BE_INSIDE_RUNS')
 out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 from runtime_setup import install
 install()
 import numpy as np,torch
 from stable_baselines3 import PPO
 from stable_baselines3.common.callbacks import BaseCallback
 from ready_env import ReadyEnv
 from resource_guard import Guard
 from checkpoints import save,load,policy_hash
 torch.set_num_threads(1);torch.set_num_interop_threads(1);random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed)
 guard=Guard(out,seconds=profile['wall_seconds']-10,max_output_gib=profile['output_limit_GiB']);guard.start()
 env=ReadyEnv(out/'env',retain_trace=True,guard=guard);episodes=[];updates=[];error=None;initial=None;model=None;started=time.monotonic();parent=None
 try:
  kwargs={k:cfg[k] for k in ('learning_rate','gamma','gae_lambda','clip_range','ent_coef','vf_coef','max_grad_norm')}
  kwargs.update({k:profile[k] for k in ('n_steps','batch_size','n_epochs')})
  model=PPO('MlpPolicy',env,seed=a.seed,device='cpu',policy_kwargs={'net_arch':dict(pi=cfg['policy_hidden_layers'],vf=cfg['policy_hidden_layers'])},verbose=0,**kwargs) if not a.resume else load(ROOT/a.resume,env)[0]
  if a.resume:
   parent=json.loads((ROOT/a.resume).with_suffix('.json').read_text())
   if parent['seed']!=a.seed:raise ValueError('RESUME_SEED_MISMATCH')
  env.base_seed=a.seed;env.seed_cursor=0 if not parent else parent['episodes_completed']+1
  if parent:model.get_env().seed(a.seed+env.seed_cursor)
  initial=policy_hash(model);base_steps=model.num_timesteps;previous_episodes=0 if not parent else parent['episodes_completed'];sampled=[]
  if base_steps>=profile['decisions']:raise ValueError('CUMULATIVE_DECISION_CAP')
  save(model,out/'checkpoints/initial',{'seed':a.seed,'episodes_completed':previous_episodes,'parent':a.resume,'teacher_used':False})
  class Callback(BaseCallback):
   def _on_step(self):
    guard.check()
    for i,info in enumerate(self.locals['infos']):
     if self.locals['dones'][i]:
      episodes.append({'decision':self.num_timesteps,'info':info})
      with (out/'episodes.jsonl').open('a') as f:f.write(json.dumps(clean(episodes[-1]))+'\n')
    return len(episodes)+previous_episodes<profile['completed_episode_limit'] and time.monotonic()-started<profile['wall_seconds']-30
  original=model.train
  def train_update():
   guard.check();begin=time.monotonic();original();row={'decisions':model.num_timesteps,'updates':model._n_updates,'train_wall_s':time.monotonic()-begin,'metrics':{k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and isinstance(v,(int,float,np.number))}};updates.append(row)
   with (out/'updates.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
   save(model,out/f'checkpoints/update_{model._n_updates:06d}',{'seed':a.seed,'episodes_completed':previous_episodes+len(episodes),'parent':a.resume,'teacher_used':False})
  model.train=train_update
  # SB3 rounds to full rollouts; request only the remaining whole-rollout cap.
  remaining=((profile['decisions']-model.num_timesteps)//model.n_steps)*model.n_steps
  if a.decisions is not None:
   if a.decisions<model.n_steps or a.decisions%model.n_steps or a.decisions>remaining:raise ValueError('WHOLE_ROLLOUT_WITHIN_CUMULATIVE_CAP_REQUIRED')
   remaining=a.decisions
  model.learn(remaining,callback=Callback(),reset_num_timesteps=a.resume is None)
  save(model,out/'checkpoints/final',{'seed':a.seed,'episodes_completed':previous_episodes+len(episodes),'parent':a.resume,'teacher_used':False})
 except BaseException as e:error=f'{type(e).__name__}:{e}';raise
 finally:
  env.close();resource=guard.close()
  put(out/'RESULT.json',{'category':'PPO_MECHANICAL_SMOKE' if a.profile=='smoke' else 'BOUNDED_PPO_TRAINING','initial_policy_sha256':initial,'final_policy_sha256':None if model is None else policy_hash(model),'updates_this_attempt':len(updates),'episodes_this_attempt':len(episodes),'error':error,'wall_s':time.monotonic()-started,'resources':resource,'learning_success_claim':False})
if __name__=='__main__':main()
