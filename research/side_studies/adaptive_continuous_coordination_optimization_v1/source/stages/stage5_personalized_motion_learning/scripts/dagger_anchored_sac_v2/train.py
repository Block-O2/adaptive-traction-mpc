from common import *
from stable_baselines3 import SAC
import copy,traceback
class Campaign:
 def __init__(self):
  self.cfg=read('PREREGISTRATION.json');c=self.cfg;random.seed(c['seed']);np.random.seed(c['seed']);torch.manual_seed(c['seed']);torch.cuda.manual_seed_all(c['seed'])
  self.sampler=np.random.default_rng(c['seed']+100);self.env=None;self.online=[];self.total=0;self.rows=[json.loads(x) for x in (L/'EVALUATIONS.jsonl').read_text().splitlines()] if (L/'EVALUATIONS.jsonl').exists() else [];self.eval_steps=sum(r['steps'] for r in self.rows);self.attempt=1;self.updates=0;self.actor_updates=0;self.checkpoints=[];self.best={};self.last_good=None;self.consecutive=0;self.lam=c['anchor_lambda'];self.started=time.time()
  self.sample_counts=dict(history=0,online=0,OUTBOUND=0,HOLD=0,RETURN=0);self.history={k:np.asarray(v) for k,v in np.load(O/'HISTORY_RL.npz').items()};self.imitation=np.load(O/'IMITATION_ONLY.npz');self.anchor_groups=[np.flatnonzero(self.imitation['phase']==p) for p in ('OUTBOUND','HOLD','RETURN')]
  self.model=SAC('MlpPolicy',gym.spaces.Box(-1,1,(1,))) if False else SAC('MlpPolicy',self.make_env('initial_never_started'),device='cuda',seed=c['seed'],learning_rate=c['critic_lr'],batch_size=256,buffer_size=50001,learning_starts=0,ent_coef=c['alpha'],gamma=c['gamma'],tau=c['tau'],policy_kwargs=dict(net_arch=[256,256]),verbose=0)
  self.env.close();self.env=None
  ck=torch.load(V/'qualified_actor.pt',map_location='cpu',weights_only=False);self.model.actor.load_state_dict(ck['state_dict']);self.pi0=copy.deepcopy(self.model.actor).eval().requires_grad_(False)
  self.set_std(c['exploration_log_std_candidates'][0]);self.model.actor.optimizer=torch.optim.Adam([p for p in self.model.actor.parameters() if p.requires_grad],lr=c['actor_lr']);assert not self.model.actor.optimizer.state and not self.model.critic.optimizer.state
  x=torch.as_tensor(self.imitation['observations'],device='cuda',dtype=torch.float32)
  with torch.no_grad():a=self.pi0(x,deterministic=True);b=self.model.actor(x,deterministic=True)
  assert torch.equal(a,b),'MEAN_IMPORT_NOT_BITWISE_IDENTICAL'
  cpu0=actor();cpu0.load_state_dict(ck['state_dict']);cpu1=actor();cpu1.load_state_dict(self.model.actor.state_dict())
  with torch.no_grad():u=cpu0(torch.as_tensor(self.imitation['observations']),True);v=cpu1(torch.as_tensor(self.imitation['observations']),True);ls=cpu0.get_action_dist_params(torch.as_tensor(self.imitation['observations']))[1].numpy()
  assert torch.equal(u,v)
  save('INITIALIZATION.json',dict(status='PASS',same_device_mean_actions_bitwise_equal=True,observations=len(x),CPU_mean_max_difference=float((u-v).abs().max()),fresh_critics_targets_optimizers=True,failed_v1_weights_loaded=False,student_untrained_log_std_min=ls.min(axis=0),student_untrained_log_std_median=np.median(ls,axis=0),student_untrained_log_std_max=ls.max(axis=0),student_untrained_std_median=np.median(np.exp(ls),axis=0),alpha=c['alpha'],log_std_frozen=True,uniform_random_warmup=0))
 def make_env(self,name):
  case,opt=load_case_options();self.env=SACExpertEnv(O/'online'/name,case,opt,.02,'NATIVE',False);return self.env
 def set_std(self,value):
  with torch.no_grad():self.model.actor.log_std.weight.zero_();self.model.actor.log_std.bias.fill_(value)
  self.model.actor.log_std.requires_grad_(False);self.std=value
 def evaluation(self,name,scope='NATIVE',stochastic=False,actor_state=None):
  name='legacy_predict_revision/'+name
  guard();assert self.env is None or self.env.thread is None,'CONCURRENT_PHYSICS_OWNERS'
  before=rngs(self.sampler,self.env);p=O/'evaluation_requests';p.mkdir(exist_ok=True);ap=p/(name.replace('/','_')+'.pt');torch.save(actor_state or {k:v.detach().cpu() for k,v in self.model.actor.state_dict().items()},ap)
  req=dict(name=name,scope=scope,stochastic=stochastic,actor=str(ap),seed=self.cfg['seed']+7919*(len(self.rows)+1),initial_condition_seed=self.cfg['initial_condition_seed'],result='EVAL_'+name.replace('/','_')+'.json');rp=p/(name.replace('/','_')+'.json');rp.write_text(json.dumps(req))
  subprocess.run([sys.executable,str(P/'evaluate.py'),str(rp)],check=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  after=rngs(self.sampler,self.env);assert digest(before)==digest(after),'EVALUATION_MUTATED_TRAINING_RNG'
  row=read(req['result']);self.eval_steps+=row['steps'];self.rows.append(row);log('EVALUATIONS.jsonl',row);return row
 def snapshot(self,name):
  folder=O/'checkpoints'/name;folder.mkdir(parents=True,exist_ok=False);self.model.num_timesteps=self.total;self.model._n_updates=self.updates;self.model.save(folder/'model');torch.save(self.model.actor.state_dict(),folder/'actor.pt')
  torch.save(dict(rng=rngs(self.sampler,self.env),online=self.online,updates=self.updates,actor_updates=self.actor_updates,lam=self.lam,std=self.std,actor_lr=self.model.actor.optimizer.param_groups[0]['lr'],attempt=self.attempt,total_consumed_at_snapshot=self.total,history_path=str(O/'HISTORY_RL.npz'),history_sha256=sha(O/'HISTORY_RL.npz'),fresh_cold_env_on_restore=True,sample_counts=self.sample_counts,checkpoints=self.checkpoints,best=self.best,last_good=str(self.last_good),consecutive=self.consecutive,formal_origin=getattr(self,'formal_origin',None),evaluation_only_steps=self.eval_steps),folder/'resume.pt')
  log('CHECKPOINTS.jsonl',dict(path=str(folder),total_online_steps=self.total,updates=self.updates,model_sha256=sha(folder/'model.zip'),resume_sha256=sha(folder/'resume.pt')));return folder
 def restore_good(self):
  consumed=self.total;folder=self.last_good;v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False);self.model.set_parameters(folder/'model.zip',exact_match=True,device='cuda');self.online=v['online'];self.updates=v['updates'];self.actor_updates=v['actor_updates'];self.lam=v['lam']*self.cfg['rescue']['anchor_multiplier'];self.set_std(v['std']+np.log(self.cfg['rescue']['std_multiplier']));self.model.actor.optimizer.param_groups[0]['lr']=v['actor_lr']*self.cfg['rescue']['actor_lr_multiplier'];restore(v['rng'],self.sampler);self.saved_env_rng=v['rng']['env'];self.attempt=2;self.total=consumed
  log('RESCUE.jsonl',dict(restored=str(folder),global_budget_not_rolled_back=self.total,restored_replay_steps=len(self.online),restored_updates=self.updates,actor_lr=self.model.actor.optimizer.param_groups[0]['lr'],std=self.std,anchor_lambda=self.lam,fixed_alpha=self.cfg['alpha'],environment='new cold commissioned episode; persisted RNG restored after construction; no in-flight physics rollback'))
 def sample(self,warm=False):
  nh=64;no=192;ids=self.sampler.integers(len(self.history['actions']),size=nh);oi=self.sampler.integers(len(self.online),size=no);keys=('observations','actions','next_observations','rewards','dones')
  h=self.history;values={k:[] for k in keys};phase=[]
  for i in ids:
   for k in keys:values[k].append((h['terminated'][i]|h['truncated'][i]) if k=='dones' else h[k][i])
   phase.append(str(h['phase'][i]))
  for i in oi:
   row=self.online[i]
   for k in keys:values[k].append(row[k])
   phase.append(row['phase'])
  self.last_sample=dict(history=nh,online=no,phase_counts={p:phase.count(p) for p in ('OUTBOUND','HOLD','RETURN')},source='real actual proposal transitions; labels excluded')
  self.sample_counts['history']+=nh;self.sample_counts['online']+=no
  for p in ('OUTBOUND','HOLD','RETURN'):self.sample_counts[p]+=phase.count(p)
  return {k:torch.as_tensor(np.asarray(v),device='cuda',dtype=torch.float32).reshape(-1,1) if k in ('rewards','dones') else torch.as_tensor(np.asarray(v),device='cuda',dtype=torch.float32) for k,v in values.items()}
 def update(self,allow_actor=False,force_actor=False):
  c=self.cfg;b=self.sample();a=self.model.actor;critic=self.model.critic;target=self.model.critic_target
  with torch.no_grad():
   na,lp=a.action_log_prob(b['next_observations']);q=torch.min(torch.cat(target(b['next_observations'],na),1),1,keepdim=True).values-c['alpha']*lp.reshape(-1,1);y=b['rewards']+(1-b['dones'])*c['gamma']*q
  qs=critic(b['observations'],b['actions']);loss=.5*sum(torch.nn.functional.mse_loss(x,y) for x in qs);assert torch.isfinite(loss),'NAN_CRITIC';critic.optimizer.zero_grad();loss.backward();critic.optimizer.step();self.updates+=1
  with torch.no_grad():
   for p,t in zip(critic.parameters(),target.parameters()):t.mul_(1-c['tau']).add_(p,alpha=c['tau'])
  row=dict(update=self.updates,critic_loss=float(loss.detach()),target_mean=float(y.mean()),target_min=float(y.min()),target_max=float(y.max()),TD_RMS=float(torch.sqrt(torch.mean((qs[0].detach()-y)**2))),sample=self.last_sample,cumulative_sample_counts=self.sample_counts)
  if allow_actor and (force_actor or self.updates%c['actor_every_critic']==0):
   idx=np.concatenate([self.sampler.choice(g,96) for g in self.anchor_groups]);x=torch.as_tensor(self.imitation['observations'][idx],device='cuda',dtype=torch.float32);ac,lp=a.action_log_prob(b['observations']);q=torch.min(torch.cat(critic(b['observations'],ac),1),1,keepdim=True).values;sl=(c['alpha']*lp.reshape(-1,1)-q).mean()
   with torch.no_grad():ref=self.pi0(x,True)
   al=torch.mean(torch.sum((a(x,True)-ref)**2,dim=1));combined=sl+self.lam*al;assert torch.isfinite(combined),'NAN_ACTOR';params=[p for p in a.parameters() if p.requires_grad]
   if self.actor_updates%100==0:
    gs=torch.autograd.grad(sl,params,retain_graph=True);ga=torch.autograd.grad(self.lam*al,params,retain_graph=True);row.update(SAC_gradient_norm=float(torch.sqrt(sum((g*g).sum() for g in gs))),weighted_anchor_gradient_norm=float(torch.sqrt(sum((g*g).sum() for g in ga))))
   a.optimizer.zero_grad();combined.backward();a.optimizer.step();self.actor_updates+=1;row.update(SAC_actor_loss=float(sl.detach()),anchor_MSE_sum=float(al.detach()),weighted_anchor_loss=float((self.lam*al).detach()),lambda_=self.lam,actor_updates=self.actor_updates,actor_lr=a.optimizer.param_groups[0]['lr'])
  if self.updates%100==0 or force_actor:log('UPDATES.jsonl',row)
  return row
 def collect(self,count,allow_actor=True):
  if count<=0:return
  env=self.make_env(f'attempt_{self.attempt}_from_{self.total:06d}');obs,info=env.reset(seed=self.cfg['initial_condition_seed'])
  if hasattr(self,'saved_env_rng') and self.saved_env_rng is not None:env.np_random.bit_generator.state=self.saved_env_rng;self.saved_env_rng=None
  data=[];start=time.time();done=False
  try:
   for collection_index in range(count):
    with torch.no_grad():ac,predict_state=self.model.predict(obs,deterministic=False)
    before=obs.copy();phase=info['phase'];obs,reward,term,trunc,info=env.step(ac);row=dict(observations=before,actions=ac.copy(),executed_actions=np.asarray(env.last_row['executed'],np.float32),next_observations=obs.copy(),rewards=reward,dones=float(term or trunc),terminated=term,truncated=trunc,phase=phase,scope='NATIVE',attempt=self.attempt,global_step=self.total+1)
    self.online.append(row);data.append(row);self.total+=1;done=term or trunc
    if allow_actor:self.update(True)
    if self.total%250==0:
     guard();state('ANCHORED_SAC_ONLINE' if allow_actor else 'FROZEN_POLICY_COLLECTION',total_online_steps=self.total,attempt=self.attempt,rescues=self.attempt-1,critic_updates=self.updates,actor_updates=self.actor_updates,steps_per_s=(collection_index+1)/max(.01,time.time()-start))
    if self.total%1000==0:resource('ONLINE_'+str(self.total));self.snapshot(f'resume_{self.attempt}_{self.total:06d}')
    if done:
     self.finish_episode(env,data,info);data=[]
     if collection_index+1<count:obs,info=env.reset(seed=self.cfg['initial_condition_seed']);done=False
   if data:
    self.persist_data(env,data,'PARTIAL_AT_EVALUATION_BOUNDARY');log('EPISODES.jsonl',dict(attempt=self.attempt,global_steps=self.total,steps=len(data),complete=False,reason='explicit cold-reset chunk boundary',not_synthetic_terminal=True))
  except BaseException:
   if data:self.persist_data(env,data,'INTERRUPTION')
   self.retain_failure(env,'INTERRUPTION');raise
  finally:env.close()
 def persist_data(self,env,data,label):
  np.savez_compressed(env.episode_dir/('TRANSITIONS_'+label+'.npz'),**{k:np.asarray([x[k] for x in data]) for k in data[0]})
 def finish_episode(self,env,data,info):
  self.persist_data(env,data,'COMPLETE' if info['physics_complete'] else 'FAILED')
  # Retain original full frequency failures from the existing runtime capture; successes are compact.
  if not info['physics_complete']:self.retain_failure(env,'FAILED')
  trace=env.capture.get('runtime',{}).get('trace',[]);nodes=[x for x in trace if x['stage']=='TASK'];ts={x['to']:x['time_s'] for x in env.summary['task']['phase_transitions']};start=nodes[0]['time_s'];end=nodes[-1]['time_s'];phases=dict(OUTBOUND=ts.get('HOLD',end)-start,HOLD=ts.get('RETURN',end)-ts.get('HOLD',end),RETURN=ts.get('COMPLETE',end)-ts.get('RETURN',end))
  episode=dict(attempt=self.attempt,global_steps=self.total,steps=len(data),complete=info['physics_complete'],termination=info['abort_reason'] or info['status'],J_F=info['J_F'],F_peak=info['force_peak'],M_integral=info['moment_integral'],M_peak=info['moment_peak'],duration=info['duration_s'],clearance=info['minimum_clearance_m'],rejections=info['rejections'],reward_total=info['reward_total'],safety_modes=env.summary['safety_mode_counts'],phase_durations=phases,episode_dir=str(env.episode_dir));(env.episode_dir/'EPISODE_METRICS.json').write_text(json.dumps(clean(episode),indent=2));log('EPISODES.jsonl',episode)
 def retain_failure(self,env,label):
  from sac_env import rt
  rt.persist_runtime_artifacts(env.episode_dir,env.capture);compact_archive(env)
  if env.summary is not None:(env.episode_dir/('SUMMARY_'+label+'.json')).write_text(json.dumps(clean(env.summary),indent=2))
 def ingest(self,row):
  self.eval_steps-=row['steps'];row['used_for_training']=True
  z=np.load(row['transitions'])
  for i in range(len(z['actions'])):
   self.online.append({k:np.asarray(z[k][i]).copy() for k in ('observations','actions','executed_actions','next_observations','rewards','terminated','truncated','phase') } | dict(dones=float(z['terminated'][i]|z['truncated'][i]),scope='NATIVE',attempt=self.attempt,global_step=self.total+1));self.total+=1
  log('BUDGET.jsonl',dict(source=row['name'],data_collection_steps=row['steps'],total_online_steps=self.total,evaluation_only=False))
 def diagnostic(self,row,label):
  z=np.load(row['transitions']);rewards=z['rewards'];returns=np.empty(len(rewards));acc=0.
  for i in reversed(range(len(rewards))):acc=float(rewards[i])+self.cfg['gamma']*acc;returns[i]=acc
  before=rngs(self.sampler,self.env)
  with torch.random.fork_rng(devices=[torch.cuda.current_device()]),torch.no_grad():
   x=torch.as_tensor(z['observations'],device='cuda',dtype=torch.float32);ac=torch.as_tensor(z['actions'],device='cuda',dtype=torch.float32);q=torch.min(torch.cat(self.model.critic(x,ac),1),1).values.cpu().numpy();nx=torch.as_tensor(z['next_observations'],device='cuda',dtype=torch.float32);na,lp=self.model.actor.action_log_prob(nx);nq=torch.min(torch.cat(self.model.critic_target(nx,na),1),1).values-self.cfg['alpha']*lp;y=torch.as_tensor(rewards,device='cuda')+self.cfg['gamma']*(1-torch.as_tensor(z['terminated']|z['truncated'],device='cuda').float())*nq;td=y.cpu().numpy()-q
  assert digest(before)==digest(rngs(self.sampler,self.env)),'CRITIC_DIAGNOSTIC_RNG_MUTATION'
  save('CRITIC_DIAGNOSTIC_'+label+'.json',dict(episode=row['name'],used_for_training=False,valid=row['valid'],training_RNG_unchanged=True,realized_discounted_reward_return_start=float(returns[0]),Q_start=float(q[0]),Q_range=[float(q.min()),float(q.max())],MC_range=[float(returns.min()),float(returns.max())],TD_RMS=float(np.sqrt(np.mean(td**2))),TD_median_abs=float(np.median(np.abs(td))),Q_vs_realized_reward_MC_RMSE=float(np.sqrt(np.mean((q-returns)**2))),interpretation='single independent frozen-policy realized return, not exact expected soft Q; entropy return differs; teacher return is never a Q target; budget fixed, no arbitrary accuracy gate'))
 def checkpoint_eval(self,point):
  folder=self.snapshot(f'candidate_attempt_{self.attempt}_point_{point:06d}_budget_{self.total:06d}');native=[self.evaluation(f'checkpoint/a{self.attempt}_p{point}_NATIVE_{j+1}') for j in range(2)];matched=[self.evaluation(f'checkpoint/a{self.attempt}_p{point}_MATCHED_{j+1}','MATCHED') for j in range(2)];stoch=self.evaluation(f'checkpoint/a{self.attempt}_p{point}_STOCHASTIC',stochastic=True)
  capable=all(r['valid'] for r in native);self.consecutive=self.consecutive+1 if capable else 0
  with torch.no_grad():
   x=torch.as_tensor(self.imitation['observations'],device='cuda',dtype=torch.float32);drift=self.model.actor(x,True)-self.pi0(x,True)
  rec=dict(attempt=self.attempt,point=point,total_online_steps=self.total,native_valid=sum(r['valid'] for r in native),matched_valid=sum(r['valid'] for r in matched),stochastic_valid=stoch['valid'],mean_drift_RMSE=float(torch.sqrt(torch.mean(drift**2))),mean_drift_peak=float(drift.abs().max()),checkpoint=str(folder),lambda_=self.lam,std=self.std);self.checkpoints.append(rec);log('CAPABILITY.jsonl',rec)
  if capable:self.last_good=folder
  self.record_best_and_results(point,folder,native,matched,stoch,rec)
  return capable
 def record_best_and_results(self,point,folder,native,matched,stoch,rec):
  for scope,rows in [('NATIVE',native),('MATCHED',matched)]:
   valid=[r for r in rows if r['valid']]
   if valid:
    cand=min(valid,key=lambda x:x['J_F'])
    if scope not in self.best or cand['J_F']<self.best[scope]['row']['J_F']-1e-6:
     confirmation=self.evaluation(f'best_confirmation/a{self.attempt}_p{point}_{scope}',scope);assert confirmation['valid'] and abs(confirmation['J_F']-cand['J_F'])<1e-5,'DETERMINISTIC_REPLAY_MISMATCH';self.best[scope]=dict(row=cand,confirmation=confirmation,checkpoint=str(folder),point=point,total_online_steps=self.total)
  save('RESULTS.json',dict(checkpoints=self.checkpoints,best=self.best,last_good=str(self.last_good),total_online_steps=self.total,evaluation_only_steps=self.eval_steps,rescues=self.attempt-1,evaluations=self.rows))
  state('CHECKPOINT_EVALUATED',point=point,total_online_steps=self.total,native_valid=rec['native_valid'],matched_valid=rec['matched_valid'],stochastic_valid=stoch['valid'],rescues=self.attempt-1)
 def complete_pending_result(self):
  existing={(r['attempt'],r['point']) for r in read('RESULTS.json')['checkpoints']}
  for rec in self.checkpoints:
   if (rec['attempt'],rec['point']) in existing:continue
   prefix=f"legacy_predict_revision/checkpoint/a{rec['attempt']}_p{rec['point']}_";native=[r for r in self.rows if r['name'].startswith(prefix+'NATIVE_')];matched=[r for r in self.rows if r['name'].startswith(prefix+'MATCHED_')];stoch=next(r for r in self.rows if r['name']==prefix+'STOCHASTIC');assert len(native)==len(matched)==2,'INCOMPLETE_CHECKPOINT_CACHED_ROWS';self.record_best_and_results(rec['point'],Path(rec['checkpoint']),native,matched,stoch,rec)
 def prerequisites(self):
  c=self.cfg;resource('INITIALIZATION');baseline=self.evaluation('baseline/frozen_student_NATIVE',actor_state=self.pi0.state_dict());assert baseline['valid'],'QUALIFIED_STUDENT_NOT_REPRODUCED';matched=self.evaluation('baseline/frozen_student_MATCHED','MATCHED',actor_state=self.pi0.state_dict());save('FROZEN_STUDENT_BASELINE.json',dict(NATIVE=baseline,MATCHED=matched))
  imported=self.evaluation('baseline/imported_SAC_NATIVE');assert imported['valid'] and abs(imported['J_F']-baseline['J_F'])<1e-5
  # Real insertion isolation test: live paused training environment, no seed resets in parent.
  env=self.make_env('rng_isolation_probe');obs,info=env.reset(seed=c['initial_condition_seed']);env.close();before=rngs(self.sampler,env)
  # Clone branch via exact RNG state, preserving the stream used by subsequent training.
  with torch.no_grad():expected,_=self.model.predict(obs,deterministic=False)
  restore(before,self.sampler,env);self.evaluation('rng_isolation/inserted_evaluation');after=rngs(self.sampler,env);assert digest(before)==digest(after)
  with torch.no_grad():actual,_=self.model.predict(obs,deterministic=False)
  assert np.array_equal(expected,actual);save('RNG_ISOLATION.json',dict(status='PASS',before_hash=digest(before),after_hash=digest(after),Python_NumPy_Torch_CPU_CUDA_sampler_env_unchanged=True,next_training_action_bitwise_equal=True,cloned_no_evaluation_action=expected,inserted_evaluation_action=actual,training_seed_reset_during_evaluation=False,mechanism='separate OS process, separate environment and RNG; exact state restoration solely to construct test counterfactual branch; normal evaluations never restore or reseed parent',training_environment_closed_before_child_physics=True));self.env=None
  calibration=[];selected=c['exploration_log_std_candidates'][-1]
  for value in c['exploration_log_std_candidates']:
   self.set_std(value);rows=[]
   for j in range(2):
    r=self.evaluation(f'calibration/std_{int(-value)}_{j+1}',stochastic=True);self.ingest(r);rows.append(r)
   calibration.append(dict(log_std=value,rows=rows,conservative_target_sigma_bound_deg=62.5*np.exp(value)))
   if all(r['valid'] for r in rows):selected=value;break
  self.set_std(selected)
  with torch.no_grad():x=torch.as_tensor(self.imitation['observations'],device='cuda');mean=self.model.actor(x,True).cpu().numpy();effective=62.5*(1-mean**2)*np.exp(selected)
  save('EXPLORATION_CALIBRATION.json',dict(candidates=calibration,selected_log_std=selected,latent_std=np.exp(selected),per_joint_local_target_sigma_median_deg=np.median(effective,axis=0),per_joint_local_target_sigma_peak_deg=effective.max(axis=0),actual_random_success=sum(r['valid'] for r in calibration[-1]['rows']),low_noise_is_not_proven_safe=True,frozen_after_selection=True))
 def resume_before_critic(self,folder):
  v=torch.load(Path(folder)/'resume.pt',map_location='cpu',weights_only=False);self.model.set_parameters(Path(folder)/'model.zip',exact_match=True,device='cuda');self.online=v['online'];self.total=v['total_consumed_at_snapshot'];self.updates=v['updates'];self.actor_updates=v['actor_updates'];self.lam=v['lam'];self.set_std(v['std']);restore(v['rng'],self.sampler);assert self.updates==self.actor_updates==0,'ONLY_PRECRITIC_ENGINEERING_RESUME';self.prerequisites_restored=True
  from stable_baselines3.common.save_util import load_from_zip_file
  _,params,_=load_from_zip_file(Path(folder)/'model.zip',device='cuda');actual=self.model.get_parameters();save('RESTORE_COMPONENT_AUDIT.json',{k:dict(expected=digest(params[k]),actual=digest(actual[k]),equal=digest(params[k])==digest(actual[k])) for k in params});assert all(digest(params[k])==digest(actual[k]) for k in params),'FULL_MODEL_OPTIMIZER_RESTORE_MISMATCH';assert digest(v['rng'])==digest(rngs(self.sampler,None)),'RESUME_RNG_MISMATCH'
  sources={json.loads(x)['source'] for x in (L/'BUDGET.jsonl').read_text().splitlines()};self.eval_steps=sum(r['steps'] for r in self.rows if r['name'] not in sources)
  for r in self.rows:r['used_for_training']=r['name'] in sources
  log('IMPLEMENTATION_RESUME.jsonl',dict(checkpoint=str(folder),total_online_steps=self.total,evaluation_only_steps=self.eval_steps,parameters_targets_optimizers_rng_replay_restored=True,no_learning_budget_reset=True,repair='Frozen-parameter native optimizer groups restored into same constructed model using set_parameters; plain SAC.load assumes unfrozen groups and is incompatible.'))
 def run(self):
  c=self.cfg
  if not getattr(self,'prerequisites_restored',False):self.prerequisites()
  elif not read('EXPLORATION_CALIBRATION.json').get('independent_confirmation_rows'):
   # Correct the two identically seeded calibration episodes, preserving their spent budget.
   confirmed=[]
   for j in range(2):
    row=self.evaluation(f'calibration_distinct_rng/std_8_{j+1}',stochastic=True);self.ingest(row);confirmed.append(row)
   if not all(r['valid'] for r in confirmed):
    self.set_std(c['exploration_log_std_candidates'][1]);lower=[]
    for j in range(2):
     row=self.evaluation(f'calibration_distinct_rng/std_10_{j+1}',stochastic=True);self.ingest(row);lower.append(row)
    confirmed=lower
   ex=read('EXPLORATION_CALIBRATION.json');ex.update(original_repeats_used_identical_rng=True,independent_confirmation_rows=confirmed,selected_log_std=self.std,latent_std=np.exp(self.std),actual_independent_random_success=sum(r['valid'] for r in confirmed),seed_repair_preserves_all_spent_collection_steps=True);save('EXPLORATION_CALIBRATION.json',ex)
  # Independent held-out frozen policy episode is excluded from all replay.
  held_name='EVAL_legacy_predict_revision_critic_held_out_before_resume_loader_repair.json';held=read(held_name) if (L/held_name).exists() else self.evaluation('critic/held_out_before_resume_loader_repair',stochastic=True);self.diagnostic(held,'before')
  for j in range(c['current_policy_seed_episodes']):
   name=f'critic/frozen_training_{j+1}';sources={json.loads(x)['source'] for x in (L/'BUDGET.jsonl').read_text().splitlines()}
   if 'legacy_predict_revision/'+name not in sources:row=self.evaluation(name,stochastic=True);self.ingest(row)
  start=time.time();state('CRITIC_ONLY',total_online_steps=self.total)
  initial={k:v.detach().clone() for k,v in self.model.actor.state_dict().items()}
  for u in range(c['critic_only_updates']):
   self.update(False)
   if (u+1)%2000==0:guard();state('CRITIC_ONLY',critic_updates=u+1,total_online_steps=self.total,updates_per_s=(u+1)/(time.time()-start))
  assert all(torch.equal(v,self.model.actor.state_dict()[k]) for k,v in initial.items()),'FROZEN_ACTOR_MOVED';self.diagnostic(held,'after');save('CRITIC_WARM_START.json',dict(updates=c['critic_only_updates'],actor_mean_and_log_std_bitwise_frozen=True,current_policy_entropy_targets=True,history_ratio=.25,critic_loss_not_sufficient_for_reliability=True,held_out_episode=held['name']))
  self.last_good=self.snapshot('last_good_frozen_warm_start');self.checkpoint_eval(0)
  for _ in range(c['small_actor_test_updates']):self.update(True,True)
  test=self.evaluation('actor_small_step_test/NATIVE');save('SMALL_ACTOR_TEST.json',dict(updates=c['small_actor_test_updates'],row=test))
  if not test['valid']:
   confirm=self.evaluation('actor_small_step_test/confirmation');self.snapshot('failed_small_actor_test')
   if not confirm['valid']:self.restore_good()
  self.bounded_training(self.total)
 def restore_interrupted(self,folder):
  from stable_baselines3.common.save_util import load_from_zip_file
  folder=Path(folder);v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False);self.model.set_parameters(folder/'model.zip',exact_match=True,device='cuda');self.online=v['online'];self.total=v['total_consumed_at_snapshot'];self.updates=v['updates'];self.actor_updates=v['actor_updates'];self.lam=v['lam'];self.set_std(v['std']);self.attempt=v['attempt'];restore(v['rng'],self.sampler);self.saved_env_rng=v['rng']['env'];_,params,_=load_from_zip_file(folder/'model.zip',device='cuda');actual=self.model.get_parameters();assert all(digest(params[k])==digest(actual[k]) for k in params),'INTERRUPTED_PARAMETERS_MISMATCH'
  probe=None
  if self.saved_env_rng is not None:probe=gym.Env();probe.reset(seed=0);probe.np_random.bit_generator.state=self.saved_env_rng
  assert digest(v['rng'])==digest(rngs(self.sampler,probe)),'INTERRUPTED_RNG_MISMATCH'
  result=read('RESULTS.json');self.checkpoints=v.get('checkpoints',result['checkpoints']);self.best=v.get('best',result['best']);self.last_good=Path(v.get('last_good',result['last_good']));self.consecutive=v.get('consecutive',1);self.formal_origin=v.get('formal_origin') or self.checkpoints[0]['total_online_steps'];sources={json.loads(x)['source'] for x in (L/'BUDGET.jsonl').read_text().splitlines()};self.eval_steps=sum(r['steps'] for r in self.rows if r['name'] not in sources)
  for r in self.rows:r['used_for_training']=r['name'] in sources
  self.sample_counts=v.get('sample_counts',json.loads((L/'UPDATES.jsonl').read_text().splitlines()[-1])['cumulative_sample_counts']);resource('INTERRUPTED_RESTORED');log('IMPLEMENTATION_RESUME.jsonl',dict(checkpoint=str(folder),total_online_steps=self.total,critic_updates=self.updates,actor_updates=self.actor_updates,formal_origin=self.formal_origin,parameters_targets_optimizers_rng_replay_verified=True,new_cold_episode_boundary=True,no_learning_or_budget_reset=True))
 def bounded_training(self,formal_origin):
  self.formal_origin=formal_origin;c=self.cfg;points=c['evaluation_points'][1:];status='COMPLETE_BUDGET';completed={r['point'] for r in self.checkpoints}
  for point in points:
   if point in completed:continue
   target=min(formal_origin+point,c['maximum_total_online_steps']);self.collect(max(0,target-self.total),True)
   capable=self.checkpoint_eval(point)
   if not capable:
    # The two independent NATIVE checkpoint executions already confirm loss.
    if self.attempt==1:self.restore_good();self.consecutive=0
    else:status='RESCUE_ABILITY_LOST';break
   if self.total>=c['maximum_total_online_steps']:break
   if self.attempt==1 and point>=20000 and self.consecutive>=2:self.lam=max(c['lambda_schedule']['floor'],c['anchor_lambda']*.9**((point-20000)//5000+1))
  self.snapshot('final_attempt_state');save('FINAL_STATUS.json',dict(status=status,total_online_steps=self.total,evaluation_only_steps=self.eval_steps,rescues=self.attempt-1,last_good=str(self.last_good),best=self.best,wall_s=time.time()-read('STATE.json')['started_unix']));state(status,total_online_steps=self.total,evaluation_only_steps=self.eval_steps,rescues=self.attempt-1)
def main():
 campaign=None
 try:
  campaign=Campaign()
  if len(sys.argv)>2 and sys.argv[2]=='online':campaign.restore_interrupted(sys.argv[1]);campaign.complete_pending_result();campaign.bounded_training(campaign.formal_origin)
  else:
   if len(sys.argv)>1:campaign.resume_before_critic(sys.argv[1])
   campaign.run()
 except BaseException as e:
  if campaign is not None:
   if campaign.env is not None:campaign.env.close()
   try:campaign.snapshot('paused_exception_'+str(int(time.time())))
   except BaseException:pass
  save('EXCEPTION.json',dict(error=str(e),traceback=traceback.format_exc()));state('PAUSED_REAL_BLOCKER',error=str(e));print(traceback.format_exc(),flush=True);raise
if __name__=='__main__':main()
