"""Existing artifacts only. No environment imports, physics, backward, or updates."""
from pathlib import Path
import json,hashlib,collections,math,sys,os,platform,importlib.metadata,random
import numpy as np
import torch
from stable_baselines3 import PPO
r=Path(__file__).resolve().parents[1];c=r.parent/'rl_b_autonomous_replication_v1'
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
def forbidden(*a,**kw):raise RuntimeError('READ_ONLY_DIAGNOSIS_FORBIDS_TRAINING')
PPO.train=forbidden;PPO.learn=forbidden;torch.Tensor.backward=forbidden;torch.autograd.backward=forbidden;torch.optim.Adam.step=forbidden

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,o):
 def clean(x):
  if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
  if isinstance(x,(list,tuple)):return [clean(v) for v in x]
  if isinstance(x,np.ndarray):return clean(x.tolist())
  if isinstance(x,np.generic):return clean(x.item())
  if isinstance(x,float) and not math.isfinite(x):return None
  return x
 (r/name).write_text(json.dumps(clean(o),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(x):
 a=np.asarray(x,dtype=float)
 return {'n':int(a.size),'min':float(a.min()),'mean':float(a.mean()),'max':float(a.max()),'std':float(a.std()),'median':float(np.median(a))} if a.size else {'n':0}
def state_hash(obj):
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
def policy_hash(model):
 h=hashlib.sha256()
 for n,t in model.policy.state_dict().items():h.update(n.encode());h.update(t.detach().cpu().numpy().tobytes())
 return h.hexdigest()
def weights_hash(model,kind):return state_hash({k:v for k,v in model.policy.state_dict().items() if ('policy_net' in k or k.startswith(('action_net','log_std'))) if kind=='actor'}) if False else state_hash({k:v for k,v in model.policy.state_dict().items() if (('policy_net' in k or k.startswith(('action_net','log_std'))) if kind=='actor' else ('value_net' in k))})
def distribution(model,obs):
 with torch.no_grad():
  d=model.policy.get_distribution(torch.as_tensor(obs,dtype=torch.float32));return d.distribution.mean.numpy().copy(),d.distribution.stddev.numpy().copy()
def loadrows(name):return [json.loads(s) for s in (c/name).read_text().splitlines()]
train=loadrows('ALL_TRAINING_LOG.jsonl');evals=loadrows('ALL_EVALUATION_LOG.jsonl');seeds=sorted({x['training_seed'] for x in train});cfg=json.loads((c/'PPO_TRAINING_CONFIG.json').read_text());records=[];rollouts=[];checkpoints=[];pairs=[];series=[];evaluation=[]
for row in train:
 p=c/row['run'];z=np.load(p/'ppo_rollout.npz');a=z['raw_actions'].reshape(-1,2);obs=z['obs'].reshape(-1,41);rewards=z['rewards'].reshape(-1);values=z['values'].reshape(-1);adv=z['advantages'].reshape(-1);returns=z['returns'].reshape(-1);trans=np.load(p/'transitions_0.npz')
 gae=0.;calc=np.zeros_like(rewards)
 for i in reversed(range(len(rewards))):
  vnext=values[i+1] if i+1<len(values) else 0.;delta=rewards[i]+vnext-values[i];gae=delta+.95*gae;calc[i]=gae
 phases=np.argmax(obs[:,22:25],axis=1)
 x={'seed':row['training_seed'],'episode':row['index'],'run':row['run'],'success':row['success'],'decisions':len(a),'reward':row['reward'],'reward_parts':row['reward_parts'],'task_s':row['task_s'],'abort_reason':row['abort_reason'],'phases':row['phases'],'losses':row['losses'],'entropy':row['entropy_mean'],'adam_updates':len(row['gradient_steps']),'raw_action_stats':[stats(a[:,j]) for j in range(2)],'raw_clip_component_fraction':float(np.mean(np.abs(a)>1)),'raw_clip_any_fraction':float(np.mean(np.any(np.abs(a)>1,axis=1))),'raw_actions_clip_match_executed_proposal':bool(np.array_equal(np.clip(a,-1,1),trans['actions'])),'advantage':stats(adv),'return':stats(returns),'old_value':stats(values),'positive_advantage_fraction':float(np.mean(adv>0)),'positive_reward_transitions':int(np.sum(rewards>0)),'negative_reward_transitions':int(np.sum(rewards<0)),'GAE_recompute_max_abs_difference':float(np.max(np.abs(adv-calc))),'return_identity_max_abs_difference':float(np.max(np.abs(returns-(adv+values)))),'reward_sum_error':float(abs(rewards.sum()-row['reward'])),'single_transition_episode':len(a)==1,'singleton_minibatch_per_epoch':len(a)%16==1,'minibatches_per_epoch':math.ceil(len(a)/16),'recorded_gradient_norm':stats([g['gradient_l2'] for g in row['gradient_steps']]),'accepted':row['accepted'],'rejections':row['rejections'],'fallback_events':row['fallback_events'],'phase_positives':{p: {'n':int(np.sum(phases==j)),'positive_advantages':int(np.sum((phases==j)&(adv>0)))} for j,p in enumerate(['OUTBOUND','HOLD','RETURN'])}}
 rollouts.append(x)
for seed in seeds:
 tr=[x for x in train if x['training_seed']==seed];ev=[x for x in evals if x['training_seed']==seed];alls=tr+ev
 common=np.concatenate([np.load(c/x['run']/'transitions_0.npz')['obs'] for x in alls]).astype(np.float32);commonsha=hashlib.sha256(common.tobytes()).hexdigest();models={}
 for path in sorted((c/f'seeds/{seed}/stage1/checkpoints').glob('*.json')):
  base=path.with_suffix('');meta=json.loads(path.read_text());model=PPO.load(str(base)+'.zip',device='cpu',force_reset=True);model.policy.set_training_mode(False)
  rng=torch.load(str(base)+'.rng.pt',weights_only=False,map_location='cpu');ph=policy_hash(model);opt=state_hash(model.policy.optimizer.state_dict());rh=state_hash(rng);m,s=distribution(model,common)
  chk={'seed':seed,'episode':meta['training_episodes'],'checkpoint':str(base),'model_sha256':sha(str(base)+'.zip'),'rng_sha256':sha(str(base)+'.rng.pt'),'metadata_sha256':sha(path),'policy_sha256':ph,'actor_sha256':weights_hash(model,'actor'),'critic_sha256':weights_hash(model,'critic'),'optimizer_sha256':opt,'rng_state_sha256':rh,'contract_sha256':meta['contract_sha256'],'model_hash_match':sha(str(base)+'.zip')==meta['model_sha256'],'rng_hash_match':sha(str(base)+'.rng.pt')==meta['rng_sha256'],'policy_hash_match':ph==meta['policy_sha256'],'optimizer_snapshot_match':opt==meta['state_snapshot']['optimizer'],'rng_snapshot_match':rh==meta['state_snapshot']['rng'],'decisions':model.num_timesteps,'ppo_epochs':model._n_updates,'adam_updates':meta['optimizer_step_calls'],'learning_rate':model.learning_rate,'optimizer_lr':[x['lr'] for x in model.policy.optimizer.param_groups],'n_epochs':model.n_epochs,'batch_size':model.batch_size,'gamma':model.gamma,'gae_lambda':model.gae_lambda,'normalize_advantage':model.normalize_advantage,'target_kl':model.target_kl,'log_std':model.policy.log_std.numpy().tolist(),'std':np.exp(model.policy.log_std.numpy()).tolist(),'common_obs_sha256':commonsha,'common_obs_n':len(common),'mean_on_common_obs':m.mean(0).tolist(),'common_mean_min':m.min(0).tolist(),'common_mean_max':m.max(0).tolist(),'modules':[type(x).__name__ for x in model.policy.modules()],'vecnormalize':model.get_vec_normalize_env() is not None,'policy_training':model.policy.training}
  checkpoints.append(chk);models[meta['training_episodes']]=model
 b=models[50];d=models[80];mb,sb=distribution(b,common);md,sd=distribution(d,common);kl=np.sum(np.log(sd/sb)+(sb**2+(mb-md)**2)/(2*sd**2)-.5,axis=1)
 idx=[x for x in checkpoints if x['seed']==seed];p50=next(x for x in idx if x['episode']==50);p80=next(x for x in idx if x['episode']==80)
 pair={'seed':seed,'checkpoint050':p50,'checkpoint080':p80,'mean_abs_mean_action_drift':np.abs(mb-md).mean(0).tolist(),'max_abs_mean_action_drift':np.abs(mb-md).max(0).tolist(),'analytic_Gaussian_KL_050_to_080_on_common_obs':stats(kl),'training_after_050':{'episodes':30,'decisions':p80['decisions']-p50['decisions'],'adam_updates':p80['adam_updates']-p50['adam_updates'],'ppo_epochs':p80['ppo_epochs']-p50['ppo_epochs']},'mean_drift_is_offline_conditional_not_counterfactual_physics':True};pairs.append(pair)
 for ep in [0,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80]:
  m,s=distribution(models[ep],common);q=next(x for x in idx if x['episode']==ep);series.append({k:q[k] for k in ['seed','episode','decisions','ppo_epochs','adam_updates','mean_on_common_obs','std','log_std']}|{'mean_abs_drift_from_050':np.abs(m-mb).mean(0).tolist(),'common_obs_sha256':commonsha})
 for row in ev:
  p=c/row['run'];z=np.load(p/'transitions_0.npz');start=json.loads((p/'START.json').read_text());meta=json.loads((c/start['checkpoint_before']).with_suffix('.json').read_text());ep=meta['training_episodes'];model=models[ep];means,std=distribution(model,z['obs']);expected=np.clip(means,-1,1);actual=z['actions'];fixed=row['kind']=='fixed_legal_plus_one'
  proposals=json.loads((p/'env/episode_0001/native_rl_proposals.json').read_text());requests=json.loads((p/'env/episode_0001/native_rl_requests.json').read_text());req={x['request_id']:x for x in requests};details=[]
  for i,prop in enumerate(proposals):
   receipt=req.get(prop['request_id'],{});mu=means[i];sigma=std[i];tail=[]
   for j in range(2):tail.append(.5*math.erfc((1-mu[j])/(sigma[j]*math.sqrt(2)))+.5*math.erfc((1+mu[j])/(sigma[j]*math.sqrt(2))))
   details.append({'action_id':i,'task_s':prop['task_s'],'phase':prop['phase'],'deterministic_mean':means[i].tolist(),'std':std[i].tolist(),'bounded_proposal':actual[i].tolist(),'native_proposal':prop['action'],'request_id':prop['request_id'],'admission_outcome':receipt.get('outcome'),'admission_reason':receipt.get('reason'),'fallback_physics_s':receipt.get('fallback_physics_s'),'activation_simulation_version':receipt.get('activation_simulation_version'),'raw_sampling_tail_probability_by_component':tail})
  f={'seed':seed,'kind':row['kind'],'episode_checkpoint':ep,'run':row['run'],'status':row['status'],'success':row['success'],'failure_reason':row['abort_reason'],'task_s':row['task_s'],'decisions':row['decisions'],'accepted':row['accepted'],'rejections':row['rejections'],'fallback_events':row['fallback_events'],'reset_seed':start['seed_for_reset'],'first_obs_sha256':hashlib.sha256(z['obs'][0].tobytes()).hexdigest(),'deterministic_recompute_max_abs_difference':None if fixed else float(np.max(np.abs(expected-actual))),'proposal_matches_native':all(np.array_equal(actual[i],prop['action']) for i,prop in enumerate(proposals)),'checkpoint_matches_start':meta['policy_sha256']==start['policy_sha256'],'actions':details,'runtime_not_implied_by_policy_weights':True,'JF_N_s':row['JF'],'JM_Nm_s':row['JM']};evaluation.append(f)
 for lo,hi in [(1,20),(21,50),(51,80)]:
  rows=[x for x in rollouts if x['seed']==seed and lo<=x['episode']<=hi];losskeys=sorted({k for x in rows for k in x['losses']});fail=[x for x in rows if not x['success']]
  records.append({'seed':seed,'episode_range':[lo,hi],'episodes':len(rows),'successes':sum(x['success'] for x in rows),'decisions':sum(x['decisions'] for x in rows),'adam_updates':sum(x['adam_updates'] for x in rows),'task_s':stats([x['task_s'] for x in rows]),'decisions_per_episode':stats([x['decisions'] for x in rows]),'losses':{k:stats([x['losses'][k] for x in rows if k in x['losses']]) for k in losskeys},'failed_return':stats([x['reward'] for x in fail]),'success_return':stats([x['reward'] for x in rows if x['success']]),'positive_advantage_fraction_failed':stats([x['positive_advantage_fraction'] for x in fail]),'single_transition_episodes':sum(x['single_transition_episode'] for x in rows),'singleton_minibatch_episodes':sum(x['singleton_minibatch_per_epoch'] for x in rows),'reasons':dict(collections.Counter(x['abort_reason'] for x in fail)),'last_phases':dict(collections.Counter(next((p for p in reversed(x['phases']) if p!='ABORTED'),'NONE') for x in fail)),'raw_clipped_any_fraction_episode_mean':float(np.mean([x['raw_clip_any_fraction'] for x in rows])),'reward_parts':{k:stats([x['reward_parts'][k] for x in rows]) for k in rows[0]['reward_parts']}})
checks={'training_episodes':len(rollouts),'checkpoints':len(checkpoints),'all_checkpoint_identity_pass':all(all(x[k] for k in ['model_hash_match','rng_hash_match','policy_hash_match','optimizer_snapshot_match','rng_snapshot_match']) for x in checkpoints),'all_raw_clip_matches_proposal':all(x['raw_actions_clip_match_executed_proposal'] for x in rollouts),'all_GAE_recomputed':max(x['GAE_recompute_max_abs_difference'] for x in rollouts)<1e-4,'GAE_max_difference':max(x['GAE_recompute_max_abs_difference'] for x in rollouts),'all_eval_policy_recomputed':all(x['deterministic_recompute_max_abs_difference'] is None or x['deterministic_recompute_max_abs_difference']<1e-6 for x in evaluation),'all_native_proposals_match':all(x['proposal_matches_native'] for x in evaluation),'all_eval_checkpoint_matches_start':all(x['checkpoint_matches_start'] for x in evaluation),'eval_first_obs_hashes':sorted(set(x['first_obs_sha256'] for x in evaluation)),'gradient_updates':0,'new_physics':0,'unavailable_metrics':['pre_clip_gradient_norm','per_minibatch_actor_critic_gradients','post_80_independent_initial_state_outcomes','per_update_true_environment_KL']}
dump('stability/TRAINING_OPTIMIZATION_AUDIT.json',{'segments':records,'episodes':rollouts,'checks':checks});dump('CHECKPOINT_050_080_COMPARISON.json',{'comparisons':pairs,'all_generations':checkpoints,'policy_drift_timeline':series,'checks':checks});dump('stability/FROZEN_ACTION_EXECUTION_AUDIT.json',{'evaluations':evaluation,'checks':checks});dump('audit/DIAGNOSTIC_RUNTIME.json',{'python':platform.python_version(),'prefix':sys.prefix,'versions':{p:importlib.metadata.version(p) for p in ['numpy','scipy','torch','stable_baselines3','gymnasium']},'grad_enabled':torch.is_grad_enabled(),'imported_mujoco':'mujoco' in sys.modules,'training_updates':0,'physics_steps':0,'checks':checks})
print(json.dumps(checks,indent=2))
for x in records:print(json.dumps({k:x[k] for k in ['seed','episode_range','successes','decisions','adam_updates','failed_return','single_transition_episodes','singleton_minibatch_episodes','last_phases']}))
for x in pairs:print(json.dumps({'seed':x['seed'],'drift':x['mean_abs_mean_action_drift'],'kl':x['analytic_Gaussian_KL_050_to_080_on_common_obs']}))
