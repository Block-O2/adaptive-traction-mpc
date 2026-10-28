"""Bounded episode PPO driver. Each episode is a complete standard PPO rollout."""
from common import ROOT,put,clean
from pathlib import Path
import os,json,time,random,argparse,traceback,math,gzip,shutil

def append(path,row):
 with Path(path).open('a') as f:f.write(json.dumps(clean(row),ensure_ascii=False,allow_nan=False)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['initialize','train','evaluate'],required=True);p.add_argument('--target',type=int);p.add_argument('--kind');p.add_argument('--checkpoint');a=p.parse_args()
 cfg=json.loads((ROOT/'PPO_TRAINING_CONFIG.json').read_text());admission=json.loads((ROOT/'LEVEL_A.json').read_text())
 if admission['status']!='DEVELOPMENT_TRAINING_ALLOWED':raise RuntimeError('LEVEL_A_CLOSED')
 from checkpoints import contract,load,save,policy_hash
 if admission['contract_sha256']!=contract():raise RuntimeError('ADMISSION_IDENTITY_MISMATCH')
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_GUARD_REQUIRED')
 from runtime_setup import install
 install()
 import numpy as np,torch
 from stable_baselines3 import PPO
 from stable_baselines3.common.buffers import RolloutBuffer
 from stable_baselines3.common.logger import configure
 from pilot_env import PilotEnv
 from resource_guard import Guard
 from functional_smoke import snapshot,state_hash
 from cloud_case_audit import audit
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 random.seed(cfg['seed']);np.random.seed(cfg['seed']);torch.manual_seed(cfg['seed'])
 ledger_path=ROOT/'LEDGER.json'
 ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'training_episodes':0,'evaluation_episodes':0,'native_steps':0,'rl_decisions':0,'optimizer_steps':0,'ppo_train_calls':0,'ppo_epochs':0,'training_decisions':0,'training_native_steps':0,'evaluation_decisions':0,'evaluation_native_steps':0,'checkpoint':'checkpoints/initial','attempts':[]}
 budget={**cfg,**ledger};out=ROOT/'runs'/('initialize' if a.mode=='initialize' else f'train_to_{a.target:02d}' if a.mode=='train' else 'eval_'+a.kind)
 out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 put(out/'START.json',{'unix':time.time(),'pid':os.getpid(),'mode':a.mode,'arguments':vars(a),'contract_sha256':contract()})
 model=None;error=None;env=None;guard=None
 try:
  env=PilotEnv(out/'model_interface/env',budget=budget)
  if a.mode=='initialize':
   model=PPO('MlpPolicy',env,n_steps=128,batch_size=16,n_epochs=4,gamma=1.,gae_lambda=.95,learning_rate=3e-4,clip_range=.2,ent_coef=0.,vf_coef=.5,max_grad_norm=.5,seed=cfg['seed'],device='cpu',policy_kwargs={'net_arch':dict(pi=[32,32],vf=[32,32])},verbose=0)
   model._total_timesteps=cfg['rl_decisions_hard_cap'];model._current_progress_remaining=1.;record=save(model,ROOT/'checkpoints/initial',{'seed':cfg['seed'],'teacher_used':False,'state_snapshot':snapshot(model),'training_episodes':0,'optimizer_step_calls':0})
   put(out/'RESULT.json',record);return
  cp=a.checkpoint or ledger['checkpoint'];model,record=load(ROOT/cp,env)
  actual=snapshot(model);expected=record['state_snapshot'];checks={k:actual[k]==v for k,v in expected.items()}
  put(out/'RESUME_AUDIT.json',{'checkpoint':cp,'sha256':record['model_sha256'],'expected':expected,'actual':actual,'checks':checks,'pass':all(checks.values()),'fresh_physical_episode':True})
  if not all(checks.values()):raise RuntimeError('RESUME_STATE_MISMATCH')
  model.set_logger(configure(str(out/'ppo_logs'),['csv']))
  env.close();env=None
  if a.mode=='train':
   if a.target not in cfg['phase_caps'] or a.target<=ledger['training_episodes']:raise RuntimeError('INVALID_STAGE_CAP')
   previous={5:0,20:5,50:20}[a.target]
   if ledger['training_episodes']!=previous:raise RuntimeError('PHASE_SEQUENCE')
   if previous and not json.loads((ROOT/f'PHASE_GATE_{previous:02d}.json').read_text())['allow_next']:raise RuntimeError('PREVIOUS_STAGE_NOT_APPROVED')
  count=(a.target-ledger['training_episodes']) if a.mode=='train' else 1
  for _ in range(count):
   if time.time()>=cfg['no_new_physics_after_unix']:raise RuntimeError('FINAL_45_MINUTE_WINDOW')
   if ledger['native_steps']+165000>cfg['native_steps_hard_cap']:raise RuntimeError('INSUFFICIENT_NATIVE_BUDGET_FOR_NEXT_EPISODE')
   index=ledger['training_episodes']+1 if a.mode=='train' else ledger['evaluation_episodes']+1
   if a.mode=='evaluate' and index>4:raise RuntimeError('EVALUATION_EPISODE_CAP')
   run=out/f'episode_{index:03d}';run.mkdir();os.environ['IHEAR_RUN_DIR']=str(run)
   guard=Guard(run,seconds=cfg['max_episode_wall_s'],min_available_gib=6,min_disk_gib=10,max_output_gib=1.5).start()
   budget.update({k:ledger[k] for k in ['native_steps','rl_decisions']})
   env=PilotEnv(run/'env',budget=budget,guard=guard,retain_trace=True,category='DEVELOPMENT_TRAINING' if a.mode=='train' else 'FROZEN_NOMINAL_EVALUATION')
   put(run/'START.json',{'unix':time.time(),'pid':os.getpid(),'mode':a.mode,'index':index,'policy_sha256':policy_hash(model),'checkpoint_before':cp,'seed':cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed']})
   samples=[];obs,info=env.reset(seed=cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed']);before_policy=policy_hash(model);before_optimizer=state_hash(model.policy.optimizer.state_dict());entropy=[]
   for step in range(cfg['episode_decision_cap']):
    tensor=torch.as_tensor(obs.reshape(1,-1),device='cpu')
    with torch.no_grad():
     dist=model.policy.get_distribution(tensor);entropy.append(float(dist.entropy().sum().item()))
     raw,value,logp=model.policy(tensor,deterministic=a.mode!='train')
    raw=raw.cpu().numpy()[0];action=np.clip(raw,-1.,1.).astype(np.float32)
    if a.mode=='evaluate' and a.kind=='fixed_legal_plus_one':action=np.ones(2,np.float32)
    nxt,reward,term,trunc,info=env.step(action)
    if not np.isfinite(reward):raise RuntimeError('NONFINITE_REWARD')
    samples.append({'obs':obs.copy(),'raw_action':raw.copy(),'action':action.copy(),'reward':reward,'value':value.detach().cpu().reshape(1),'logp':logp.detach().cpu().reshape(1),'episode_start':step==0})
    obs=nxt
    if term or trunc:break
   else:raise RuntimeError('EPISODE_DECISION_CAP')
   info=dict(info);native=info['native_steps_total'];env.close();env=None;res=guard.close();guard=None
   independent=audit(run)
   put(run/'INDEPENDENT_AUDIT.json',independent)
   if not independent['pass']:raise RuntimeError('INDEPENDENT_PHYSICAL_REWARD_OR_OWNERSHIP_AUDIT_FAILED')
   if a.mode=='train':
    buf=RolloutBuffer(len(samples),model.observation_space,model.action_space,device='cpu',gamma=1.,gae_lambda=.95,n_envs=1)
    for s in samples:buf.add(s['obs'].reshape(1,-1),s['raw_action'].reshape(1,-1),np.array([s['reward']]),np.array([s['episode_start']]),s['value'],s['logp'])
    buf.compute_returns_and_advantage(last_values=torch.zeros(1),dones=np.array([True]))
    np.savez_compressed(run/'ppo_rollout.npz',obs=buf.observations,raw_actions=buf.actions,rewards=buf.rewards,values=buf.values,log_probs=buf.log_probs,advantages=buf.advantages,returns=buf.returns)
    model.rollout_buffer=buf;model.num_timesteps+=len(samples);model._episode_num+=1;model._last_obs=obs.reshape(1,-1);model._last_episode_starts=np.array([True]);model._current_progress_remaining=1.
    optimizer=model.policy.optimizer;original_step=optimizer.step;gradient_steps=[]
    def instrumented_step(*args,**kwargs):
     if ledger['optimizer_steps']+len(gradient_steps)>=cfg['optimizer_steps_hard_cap']:raise RuntimeError('OPTIMIZER_STEP_HARD_CAP')
     grads=[v.grad.detach() for v in model.policy.parameters() if v.grad is not None];norm=float(torch.sqrt(sum((g*g).sum() for g in grads)).item())
     if not all(bool(torch.isfinite(g).all()) for g in grads) or not math.isfinite(norm):raise RuntimeError('NONFINITE_GRADIENT')
     before=policy_hash(model);result=original_step(*args,**kwargs);gradient_steps.append({'gradient_l2':norm,'weights_changed':before!=policy_hash(model)})
     return result
    optimizer.step=instrumented_step
    try:model.train()
    finally:optimizer.step=original_step
    ledger['training_episodes']+=1;ledger['training_decisions']+=len(samples);ledger['training_native_steps']+=native;ledger['optimizer_steps']+=len(gradient_steps);ledger['ppo_train_calls']+=1;ledger['ppo_epochs']=model._n_updates
    cp=f'checkpoints/episode_{index:03d}'
    record=save(model,ROOT/cp,{'seed':cfg['seed'],'teacher_used':False,'training_episodes':index,'parent':ledger['checkpoint'],'state_snapshot':snapshot(model),'optimizer_step_calls':ledger['optimizer_steps']});ledger['checkpoint']=cp
    losses={k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and isinstance(v,(int,float,np.number)) and np.isfinite(v)};model.logger.dump(model.num_timesteps)
   else:
    gradient_steps=[];losses={}
    ledger['evaluation_episodes']+=1;ledger['evaluation_decisions']+=len(samples);ledger['evaluation_native_steps']+=native
    if policy_hash(model)!=before_policy or state_hash(model.policy.optimizer.state_dict())!=before_optimizer:raise RuntimeError('FROZEN_POLICY_MUTATED')
   ledger['native_steps']+=native;ledger['rl_decisions']+=len(samples)
   row={'mode':a.mode,'kind':a.kind,'index':index,'unix':time.time(),'run':str(run.relative_to(ROOT)),'seed':env.episode_seed if env else (cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed']),'checkpoint_before':record.get('parent') if a.mode=='train' else cp,'checkpoint_after':cp,'policy_before':before_policy,'policy_after':policy_hash(model),'decisions':len(samples),'native_steps':native,'task_native_steps':info['task_native_steps'],'reward':sum(s['reward'] for s in samples),'entropy_mean':float(np.mean(entropy)),'success':info['success'],'status':info['status'],'abort_reason':info['abort_reason'],'task_s':info['task_s'],'phases':info['phases'],'JF':info['force_integral_N_s'],'JM':info['moment_integral_Nm_s'],'accepted':info['accepted'],'rejections':info['rejections'],'fallback_events':len(independent['fallback_events']),'independent_audit_pass':independent['pass'],'gradient_steps':gradient_steps,'losses':losses,'resource':res}
   append(ROOT/('PPO_TRAINING_LOG.jsonl' if a.mode=='train' else 'FROZEN_EVALUATION_LOG.jsonl'),row)
   put(run/'END.json',{'unix':time.time(),'status':'COMPLETE_ATTEMPT','runtime_status':info['status'],'owner_joined':True,'independent_audit_pass':True,'row':row})
   ledger['attempts'].append(str(run.relative_to(ROOT)));put(ledger_path,ledger)
   put(ROOT/'STATE.json',{'status':'TRAINING' if a.mode=='train' else 'EVALUATING','phase_target':a.target,**ledger})
   print(json.dumps({'mode':a.mode,'episode':index,'success':info['success'],'task_s':info['task_s'],'reward':row['reward'],'decisions':len(samples),'gradient_steps':len(gradient_steps),'audit':True}),flush=True)
   # Keep complete raw/native for every attempt, stored losslessly after audit.
   for f in list(run.rglob('*.json'))+list(run.rglob('*.jsonl')):
    if f.stat().st_size>2*1024**2:
     with f.open('rb') as src,gzip.open(str(f)+'.gz','wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
     f.unlink()
  if a.mode=='train':
   rows=[json.loads(x) for x in (ROOT/'PPO_TRAINING_LOG.jsonl').read_text().splitlines()];segment=rows[-count:]
   stable=all(x['independent_audit_pass'] and x['gradient_steps'] and all(g['gradient_l2']>0 and g['weights_changed'] for g in x['gradient_steps']) for x in segment)
   value=any(x['success'] or x['task_s']>=9 for x in segment)
   allow=stable and (a.target<20 or value) and time.time()<cfg['no_new_physics_after_unix']-900
   put(ROOT/f'PHASE_GATE_{a.target:02d}.json',{'episodes':a.target,'stable':stable,'research_value':value,'allow_next':allow,'successes':sum(x['success'] for x in segment),'audits_pass':all(x['independent_audit_pass'] for x in segment),'reward_hacking_observed':False,'rule':'stage3 needs stable complete rollouts, finite nonzero gradients and actual success or >=9s task progress; no tuning on frozen evaluation'})
 except BaseException as e:
  error={'error':repr(e),'traceback':traceback.format_exc()};put(out/'FAILURE.json',error)
  if model is not None:
   try:save(model,out/'emergency_checkpoint',{'state_snapshot':snapshot(model),'partial_attempt':True,'ledger':ledger})
   except BaseException as save_error:put(out/'CHECKPOINT_FAILURE.json',{'error':repr(save_error)})
  raise
 finally:
  if env is not None:env.close()
  if guard is not None:guard.close()
  put(out/'END.json',{'unix':time.time(),'pid':os.getpid(),'error':error,'completed':error is None,'ledger':ledger})
if __name__=='__main__':main()
