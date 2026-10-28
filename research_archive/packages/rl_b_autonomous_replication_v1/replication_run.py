"""Single-environment, complete-episode PPO replication with fail-closed accounting.

Stage1 duplicates historical pilot rollout/update semantics. Scientific sources
and the actor/physical interface are copied byte-for-byte and never patched.
"""
from common import ROOT,put,clean
from pathlib import Path
import argparse,os,json,time,traceback,random,math,gzip,shutil,hashlib

def append(path,row):
 with Path(path).open('a') as f:f.write(json.dumps(clean(row),ensure_ascii=False,allow_nan=False)+'\n')
def read(path,default):return json.loads(path.read_text()) if path.exists() else default
def compress(run):
 for p in list(run.rglob('*.json'))+list(run.rglob('*.jsonl')):
  if p.stat().st_size>2*1024**2:
   with p.open('rb') as src,gzip.open(str(p)+'.gz','wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
   p.unlink()
def compact_training(run):
 from checkpoints import sha
 # Keep summaries, causal tick data, transitions, requests and applied receipts.
 # The native journal is transient audit input, never silently discarded.
 tomb=[]
 for p in list((run/'native_journals').glob('*'))+list(run.glob('env/episode_*/runtime_artifacts.json')):
  tomb.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p),'disposition':'TRAINING_TRANSIENT_RAW_REMOVED_AFTER_PASSED_INDEPENDENT_AUDIT'})
  if p.name=='runtime_artifacts.json':
   from stream_json import array_items,object_value
   fields=['trace','requests','activation_validations','future_handoff_bridges','safe_fallback_events','command_receipts']
   receipt={}
   for key in fields:
    try:receipt[key]=list(array_items(p,key))
    except (KeyError,ValueError):receipt[key]=[]
   put(p.parent/'COMPACT_CAUSAL_RECEIPTS.json',receipt)
  p.unlink()
 put(run/'TRANSIENT_RAW_DISPOSITION.json',{'evidence_category':'TRAINING_SUMMARY_ONLY','audit_passed_before_removal':True,'removed':tomb,'full_evaluation_raw':False})

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['initialize','train','evaluate'],required=True);p.add_argument('--seed',required=True,type=int);p.add_argument('--target',type=int);p.add_argument('--kind');p.add_argument('--checkpoint');p.add_argument('--stage',choices=['stage1','stage2'],default='stage1');a=p.parse_args()
 cfg=read(ROOT/'PPO_TRAINING_CONFIG.json',{});from checkpoints import contract,load,save,policy_hash
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_GUARD_REQUIRED')
 admission=read(ROOT/'LEVEL_A.json',{})
 if admission.get('status')!='DEVELOPMENT_TRAINING_ALLOWED' or admission.get('contract_sha256')!=contract():raise RuntimeError('DEVELOPMENT_ADMISSION_CLOSED')
 if a.seed not in cfg['seeds']:raise ValueError('UNREGISTERED_SEED')
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
 random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed)
 if a.stage=='stage2':
  from stage2_env import Stage2Env
  Env=Stage2Env
  stage2=read(ROOT/'STAGE2_FROZEN.json',{})
  if not stage2.get('gate_pass') or stage2['seed']!=a.seed:raise RuntimeError('STAGE2_GATE_CLOSED')
 else:Env=PilotEnv
 seedroot=ROOT/'seeds'/str(a.seed)/a.stage;seedroot.mkdir(parents=True,exist_ok=True)
 ledger_path=ROOT/'LEDGER.json';ledger=read(ledger_path,{'stage1_attempts':0,'stage2_attempts':0,'evaluation_attempts':0,'native_steps':0,'rl_decisions':0,'optimizer_steps':0,'physical_attempts':[]})
 progress=read(seedroot/'PROGRESS.json',{'completed_episodes':0,'training_decisions':0,'training_native_steps':0,'optimizer_steps':0,'ppo_train_calls':0,'ppo_epochs':0,'checkpoint':None,'successes':0})
 label='initialize' if a.mode=='initialize' else f'train_to_{a.target:03d}' if a.mode=='train' else 'eval_'+a.kind
 out=seedroot/'runs'/label;out.mkdir(parents=True,exist_ok=False)
 os.environ['IHEAR_RUN_DIR']=str(out)
 put(out/'START.json',{'unix':time.time(),'pid':os.getpid(),'arguments':vars(a),'contract_sha256':contract(),'category':'PROGRAM_ATTEMPT_NO_PHYSICS_UNTIL_EPISODE_START'})
 model=env=guard=None;error=None;episode_run=None;attempt_counted=False;native_counted=False;terminal_info=None;cp=None
 try:
  interface=Env(out/'model_interface/env',budget={**cfg,**ledger})
  if a.mode=='initialize':
   if progress['checkpoint'] is not None:raise RuntimeError('ALREADY_INITIALIZED')
   if a.stage=='stage1':
    model=PPO('MlpPolicy',interface,n_steps=128,batch_size=16,n_epochs=4,gamma=1.,gae_lambda=.95,learning_rate=3e-4,clip_range=.2,ent_coef=0.,vf_coef=.5,max_grad_norm=.5,seed=a.seed,device='cpu',policy_kwargs={'net_arch':dict(pi=[32,32],vf=[32,32])},verbose=0)
    model._total_timesteps=cfg['rl_decisions_hard_cap'];model._current_progress_remaining=1.
    parent=None
   else:
    parent=stage2['parent_checkpoint'];model,parent_record=load(ROOT/parent,interface)
   record=save(model,seedroot/'checkpoints/initial',{'seed':a.seed,'stage':a.stage,'teacher_used':False,'initialization':'SCRATCH_RANDOM' if a.stage=='stage1' else 'TASK_PRETRAINED_PPO_FINETUNING','parent':parent,'state_snapshot':snapshot(model),'training_episodes':0,'optimizer_step_calls':0})
   progress['checkpoint']=str((seedroot/'checkpoints/initial').relative_to(ROOT));progress['base_ppo_epochs']=model._n_updates
   put(seedroot/'PROGRESS.json',progress);put(out/'RESULT.json',record);interface.close();return
  cp=a.checkpoint or progress['checkpoint']
  if cp is None:raise RuntimeError('INITIALIZATION_REQUIRED')
  model,record=load(ROOT/cp,interface);interface.close()
  actual=snapshot(model);expected=record['state_snapshot'];checks={k:actual[k]==v for k,v in expected.items()}
  put(out/'RESUME_AUDIT.json',{'checkpoint':cp,'expected':expected,'actual':actual,'checks':checks,'pass':all(checks.values()),'fresh_physical_episode':True})
  if not all(checks.values()):raise RuntimeError('RESUME_STATE_MISMATCH')
  model.set_logger(configure(str(out/'ppo_logs'),['csv']))
  if a.mode=='train':
   allowed=[20,50,80] if a.stage=='stage1' else [10,20,30]
   if a.target not in allowed or a.target<=progress['completed_episodes']:raise RuntimeError('INVALID_PHASE_TARGET')
   previous=allowed[allowed.index(a.target)-1] if allowed.index(a.target) else 0
   if progress['completed_episodes']!=previous:raise RuntimeError('PHASE_SEQUENCE')
   if a.stage=='stage1' and a.target==80 and not read(ROOT/'EXTENSION_DECISION.json',{}).get('allow'):raise RuntimeError('EXTENSION_GATE_CLOSED')
   count=a.target-progress['completed_episodes']
  else:count=1
  for _ in range(count):
   if time.time()>=cfg['no_new_physics_after_unix']:raise RuntimeError('FINAL_60_MINUTES_NO_NEW_PHYSICS')
   if ledger['native_steps']+165000>cfg['native_steps_hard_cap']:raise RuntimeError('NATIVE_BUDGET_RESERVE')
   key=a.stage+'_attempts' if a.mode=='train' else 'evaluation_attempts';cap=cfg['training_episode_cap'] if a.stage=='stage1' else cfg['stage2_episode_cap']
   if ledger[key]>=(cap if a.mode=='train' else cfg['evaluation_episode_cap']):raise RuntimeError('EPISODE_BUDGET_EXHAUSTED')
   index=progress['completed_episodes']+1 if a.mode=='train' else ledger['evaluation_attempts']+1
   run=out/f'episode_{index:03d}';run.mkdir();episode_run=run;attempt_counted=False;native_counted=False;terminal_info=None;os.environ['IHEAR_RUN_DIR']=str(run)
   before_policy=policy_hash(model);before_optimizer=state_hash(model.policy.optimizer.state_dict())
   put(run/'START.json',{'unix':time.time(),'pid':os.getpid(),'mode':a.mode,'stage':a.stage,'seed':a.seed,'index':index,'checkpoint_before':cp,'policy_sha256':before_policy,'category':'DEVELOPMENT_TRAINING' if a.mode=='train' else 'FROZEN_NOMINAL_EVALUATION','seed_for_reset':cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed']})
   ledger[key]+=1;ledger['physical_attempts'].append(str(run.relative_to(ROOT)));put(ledger_path,ledger);attempt_counted=True
   guard=Guard(run,seconds=cfg['max_episode_wall_s'],min_available_gib=6,min_disk_gib=10,max_output_gib=1.5).start()
   env=Env(run/'env',budget={**cfg,**ledger},guard=guard,retain_trace=True,category='DEVELOPMENT_TRAINING' if a.mode=='train' else 'FROZEN_NOMINAL_EVALUATION')
   samples=[];entropy=[];obs,info=env.reset(seed=cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed'])
   for step in range(cfg['episode_decision_cap']):
    tensor=torch.as_tensor(obs.reshape(1,-1),device='cpu')
    with torch.no_grad():
     dist=model.policy.get_distribution(tensor);entropy.append(float(dist.entropy().sum().item()));raw,value,logp=model.policy(tensor,deterministic=a.mode!='train')
    raw=raw.cpu().numpy()[0];action=np.clip(raw,-1.,1.).astype(np.float32)
    if a.mode=='evaluate' and a.kind=='fixed_legal_plus_one':action=np.ones(2,np.float32)
    nxt,reward,term,trunc,info=env.step(action)
    if not np.isfinite(reward):raise RuntimeError('NONFINITE_REWARD')
    samples.append({'obs':obs.copy(),'raw_action':raw.copy(),'action':action.copy(),'reward':reward,'value':value.detach().cpu().reshape(1),'logp':logp.detach().cpu().reshape(1),'episode_start':step==0})
    obs=nxt
    if term or trunc:break
   else:raise RuntimeError('EPISODE_DECISION_CAP')
   info=dict(info);terminal_info=info;native=info['native_steps_total'];env.close();env=None;res=guard.close();guard=None
   ledger['native_steps']+=native;ledger['rl_decisions']+=len(samples);native_counted=True;put(ledger_path,ledger)
   independent=audit(run);put(run/'INDEPENDENT_AUDIT.json',independent)
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
     before=policy_hash(model);result=original_step(*args,**kwargs);gradient_steps.append({'gradient_l2':norm,'weights_changed':before!=policy_hash(model)});return result
    optimizer.step=instrumented_step
    try:model.train()
    finally:optimizer.step=original_step
    progress['completed_episodes']+=1;progress['training_decisions']+=len(samples);progress['training_native_steps']+=native;progress['optimizer_steps']+=len(gradient_steps);progress['ppo_train_calls']+=1;progress['ppo_epochs']=model._n_updates-progress.get('base_ppo_epochs',0);progress['successes']+=int(info['success']);ledger['optimizer_steps']+=len(gradient_steps)
    if index%5==0 or index==a.target:
     parent=cp;cp=str((seedroot/f'checkpoints/episode_{index:03d}').relative_to(ROOT))
     record=save(model,ROOT/cp,{'seed':a.seed,'stage':a.stage,'teacher_used':False,'initialization':'SCRATCH_RANDOM' if a.stage=='stage1' else 'TASK_PRETRAINED_PPO_FINETUNING','training_episodes':index,'parent':parent,'state_snapshot':snapshot(model),'optimizer_step_calls':progress['optimizer_steps']});progress['checkpoint']=cp
    losses={k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and isinstance(v,(int,float,np.number)) and np.isfinite(v)};model.logger.dump(model.num_timesteps)
   else:
    gradient_steps=[];losses={}
    if policy_hash(model)!=before_policy or state_hash(model.policy.optimizer.state_dict())!=before_optimizer:raise RuntimeError('FROZEN_POLICY_MUTATED')
   row={'mode':a.mode,'stage':a.stage,'kind':a.kind,'index':index,'unix':time.time(),'run':str(run.relative_to(ROOT)),'training_seed':a.seed,'environment_seed':cfg['environment_seed']+index if a.mode=='train' else cfg['environment_seed'],'checkpoint_after':cp,'policy_before':before_policy,'policy_after':policy_hash(model),'decisions':len(samples),'native_steps':native,'task_native_steps':info['task_native_steps'],'reward':sum(s['reward'] for s in samples),'reward_parts':info['reward_totals'],'entropy_mean':float(np.mean(entropy)),'success':info['success'],'status':info['status'],'abort_reason':info['abort_reason'],'task_s':info['task_s'],'phases':info['phases'],'JF':info['force_integral_N_s'],'JM':info['moment_integral_Nm_s'],'variation_integral':info['motion_variation_penalty_integral'],'accepted':info['accepted'],'rejections':info['rejections'],'fallback_events':len(independent['fallback_events']),'independent_audit_pass':independent['pass'],'gradient_steps':gradient_steps,'losses':losses,'resource':res}
   append(seedroot/('TRAINING_LOG.jsonl' if a.mode=='train' else 'EVALUATION_LOG.jsonl'),row);append(ROOT/('ALL_TRAINING_LOG.jsonl' if a.mode=='train' else 'ALL_EVALUATION_LOG.jsonl'),row)
   put(run/'END.json',{'unix':time.time(),'status':'COMPLETE_ATTEMPT','runtime_status':info['status'],'owner_joined':True,'row':row})
   put(seedroot/'PROGRESS.json',progress);put(ledger_path,ledger);put(ROOT/'LIVE_STATUS.json',{'unix':time.time(),'stage':a.stage,'mode':a.mode,'seed':a.seed,'phase_target':a.target,'progress':progress,'global_ledger':ledger})
   print(json.dumps({'mode':a.mode,'stage':a.stage,'seed':a.seed,'episode':index,'success':info['success'],'task_s':info['task_s'],'reward':row['reward'],'decisions':len(samples),'adam_updates':len(gradient_steps),'audit':True}),flush=True)
   if a.mode=='train':compact_training(run)
   compress(run);episode_run=None
  if a.mode=='train':
   rows=[json.loads(s) for s in (seedroot/'TRAINING_LOG.jsonl').read_text().splitlines()];segment=rows[-count:]
   put(seedroot/f'PHASE_GATE_{a.target:03d}.json',{'target':a.target,'all_audits_pass':all(x['independent_audit_pass'] for x in segment),'finite_nonzero_updates':all(x['gradient_steps'] and all(g['gradient_l2']>0 and g['weights_changed'] for g in x['gradient_steps']) for x in segment),'successes':sum(x['success'] for x in segment),'episodes':len(segment),'safety_or_reward_loophole_observed':False,'configuration_changed':False})
 except BaseException as e:
  error={'error':repr(e),'traceback':traceback.format_exc()};put(out/'FAILURE.json',error)
  if episode_run is not None and not native_counted:
   actual=env.metrics()['native_steps_total'] if env is not None and getattr(env,'capture',{}).get('runtime',{}).get('plant') is not None else 0
   ledger['native_steps']+=actual;ledger['rl_decisions']+=getattr(env,'steps',0) if env is not None else 0;put(ledger_path,ledger)
  if model is not None:
   try:save(model,out/'emergency_checkpoint',{'seed':a.seed,'stage':a.stage,'state_snapshot':snapshot(model),'partial_attempt':True,'ledger':ledger,'progress':progress})
   except BaseException as e2:put(out/'CHECKPOINT_FAILURE.json',{'error':repr(e2)})
  raise
 finally:
  if env is not None:env.close()
  if guard is not None:guard.close()
  if episode_run is not None and not (episode_run/'END.json').exists():put(episode_run/'END.json',{'unix':time.time(),'status':'PARTIAL_INFRASTRUCTURE_OR_AUDIT_FAILURE','error':error,'owner_joined':env is None or env.thread is None,'native_counted':True,'terminal_info':terminal_info,'raw_preserved':True})
  put(out/'END.json',{'unix':time.time(),'pid':os.getpid(),'error':error,'completed':error is None,'progress':progress,'ledger':ledger})
if __name__=='__main__':main()
