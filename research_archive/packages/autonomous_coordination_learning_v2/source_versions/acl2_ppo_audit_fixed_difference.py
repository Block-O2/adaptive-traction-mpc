"""Independent numerical replay of actual saved PPO generations and Adam."""
from pathlib import Path
import json,time
import numpy as np
from acl2_shared import P,put,read,sha,utc,records

def logdensity(z,mu,ls):
 # Independent change-of-variable formula (ordinary stable finite z here).
 x=np.tanh(z);return np.sum(-.5*((z-mu)/np.exp(ls))**2-ls-.5*np.log(2*np.pi)-np.log1p(-x*x),axis=-1)
def adam(theta,g,m,v,t,lr):
 m=.9*m+.1*g;v=.999*v+.001*g*g;t+=1
 return theta+lr*(m/(1-.9**t))/(np.sqrt(v/(1-.999**t))+1e-8),m,v,t
def objective(row,base):
 if not row.get('complete'):return -20.
 if not row.get('qualified'):return -10.-min(5.,max(0.,row['worst_ratio']-1.))
 return float(5*np.tanh((base['JF']-row['JF'])/5))
def audit(group='PPO_SCRATCH'):
 start=time.time();config=read('jobs/'+group+'_CONFIG.json');rollfile=P/'jobs'/group/'RL_ROLLOUTS.jsonl'
 if not rollfile.exists():return dict(status='NOT_RUN',group=group)
 roll=[json.loads(x) for x in rollfile.read_text().splitlines()];base=read('attempts/'+group+'_STRONG_RESULT.json');errors=[];out=[];maxerrors=dict(density=0.,raw_advantage=0.,normalized_advantage=0.,Adam_parameter=0.,Adam_m=0.,Adam_v=0.,reward=0.,RNG_sample=0.);rng=np.random.default_rng(config['ppo_seed'])
 mu=np.zeros(8);ls=np.full(8,np.log(.2));value=np.zeros(1);mm=np.zeros(8);mv=np.zeros(8);sm=np.zeros(8);sv=np.zeros(8);vm=np.zeros(1);vv=np.zeros(1);t=0;RL=0
 for bf in sorted((P/'models'/group).glob('generation_*_BEFORE.json')):
  b=json.loads(bf.read_text());generation=b['generation'];af=bf.with_name(bf.name.replace('_BEFORE','_AFTER'))
  if not af.exists():out.append(dict(generation=generation,status='PARTIAL_BATCH_UNUPDATED_PRESERVED'));continue
  a=json.loads(af.read_text());u=a['update'];z=np.asarray(b['sampled_pre_tanh_z']);x=np.asarray(b['exact_executed_x']);oldmu=np.asarray(b['mu']);oldls=np.asarray(b['log_std']);oldvalue=float(b['value']);size=len(z)
  if not np.allclose(mu,oldmu,atol=3e-6) or not np.allclose(ls,oldls,atol=3e-6):errors.append('ACTOR_CHECKPOINT_CHAIN_%d'%generation)
  sampled=rng.normal(size=z.shape)*np.exp(oldls)+oldmu;maxerrors['RNG_sample']=max(maxerrors['RNG_sample'],float(np.max(abs(sampled-z))))
  if not np.array_equal(np.tanh(z),x):errors.append('POST_SAMPLING_ACTION_CHANGED_%d'%generation)
  if rng.bit_generator.state!=b['rng_state']:errors.append('RNG_STATE_%d'%generation)
  oldlp=logdensity(z,oldmu,oldls);maxerrors['density']=max(maxerrors['density'],float(np.max(abs(oldlp-np.asarray(b['old_log_probability'])))))
  rs=[r for r in roll if r['generation']==generation]
  if len(rs)!=size:errors.append('ROLLOUT_GENERATION_SIZE_%d'%generation)
  rewards=[]
  for r in rs:
   native=read('attempts/'+r['id']+'_RESULT.json');rewards.append(objective(native,base))
   if r['behavior_id']!=b['behavior_id'] or not np.array_equal(np.asarray(r['mu']),oldmu) or not np.array_equal(np.asarray(r['log_std']),oldls):errors.append('BEHAVIOR_DENSITY_OWNERSHIP:'+r['id'])
   if native['action'].get('x')!=r['x']:errors.append('PROPOSAL_OWNERSHIP:'+r['id'])
  rewards=np.asarray(rewards);adv=rewards-oldvalue;norm=(adv-adv.mean())/(adv.std()+1e-8);maxerrors['reward']=max(maxerrors['reward'],float(np.max(abs(rewards-np.asarray(u['reward'])))));maxerrors['raw_advantage']=max(maxerrors['raw_advantage'],float(np.max(abs(adv-np.asarray(u['advantage_raw'])))));maxerrors['normalized_advantage']=max(maxerrors['normalized_advantage'],float(np.max(abs(norm-np.asarray(u['advantage_normalized'])))))
  epochchecks=[]
  for ep in u['epochs']:
   theta=np.r_[mu,ls]
   def f(theta):
    ratio=np.exp(logdensity(z,theta[:8],theta[8:])-oldlp);return float(np.mean(np.minimum(ratio*norm,np.clip(ratio,.8,1.2)*norm))+.002*np.sum(theta[8:]))
   # Five-point numerical differentiation checks clipping/sign/entropy together,
   # without importing or reusing the trainer's analytical gradient function.
   h=1e-5;grad=[]
   for k in range(16):
    d=np.eye(16)[k]*h;grad.append((f(theta-2*d)-8*f(theta-d)+8*f(theta+d)-f(theta+2*d))/(12*h))
   grad=np.asarray(grad);gnorm=float(np.linalg.norm(grad));grad*=min(1.,.5/max(gnorm,1e-12));mu,mm,mv,tm=adam(mu,grad[:8],mm,mv,t,config['mean_lr']);ls,sm,sv,ts=adam(ls,grad[8:],sm,sv,t,config['std_lr']);ls=np.clip(ls,np.log(.05),np.log(.7));value,vm,vv,tv=adam(value,np.array([np.mean(rewards-value[0])]),vm,vv,t,.05);t=tm
   exactkl=float(.5*np.sum((np.exp(2*oldls)+(oldmu-mu)**2)/np.exp(2*ls)-1+2*(ls-oldls)));ratio=np.exp(logdensity(z,mu,ls)-oldlp);approx=float(np.mean(ratio-1-np.log(ratio)));epochchecks.append(dict(Adam_policy_epoch=t,numerical_gradient_norm=gnorm,exact_Gaussian_KL=exactkl,empirical_ratio_KL=approx))
  pe=max(float(np.max(abs(mu-np.asarray(a['mu'])))),float(np.max(abs(ls-np.asarray(a['log_std'])))),float(np.max(abs(value-np.asarray([a['value']])))));me=max(float(np.max(abs(mm-np.asarray(a['Adam_mean']['m'])))),float(np.max(abs(sm-np.asarray(a['Adam_std']['m'])))),float(np.max(abs(vm-np.asarray(a['Adam_value']['m'])))));ve=max(float(np.max(abs(mv-np.asarray(a['Adam_mean']['v'])))),float(np.max(abs(sv-np.asarray(a['Adam_std']['v'])))),float(np.max(abs(vv-np.asarray(a['Adam_value']['v'])))))
  maxerrors['Adam_parameter']=max(maxerrors['Adam_parameter'],pe);maxerrors['Adam_m']=max(maxerrors['Adam_m'],me);maxerrors['Adam_v']=max(maxerrors['Adam_v'],ve);RL+=size
  if max(pe,me,ve)>2e-4:errors.append('NUMERICAL_ADAM_REPLAY_%d'%generation)
  out.append(dict(generation=generation,episodes=size,behavior_id=b['behavior_id'],policy_epochs=len(epochchecks),qualified=sum(r['qualified'] for r in rs),exact_analytic_actor_KL_available=True,epoch_checks=epochchecks,checkpoint_max_parameter_error=pe,checkpoint_max_Adam_m_error=me,checkpoint_max_Adam_v_error=ve,one_RL_decision_per_episode=True))
 if maxerrors['density']>1e-9 or maxerrors['RNG_sample']>1e-12 or maxerrors['reward']>1e-8 or maxerrors['raw_advantage']>1e-8 or maxerrors['normalized_advantage']>1e-8:errors.append('DENSITY_RNG_REWARD_ADVANTAGE_REPLAY')
 issued=[r for r in records() if r['event']=='START' and r['id'].startswith(group+'_TRAIN_')]
 return dict(status='PASS' if not errors else 'FAIL',group=group,utc=utc(),errors=errors,RL_decisions=len(issued),completed_rollout_records=len(roll),samples_used_in_completed_updates=RL,pending_or_incomplete_issued_decisions=len(issued)-RL,policy_update_epochs=t,Adam_parameter_group_updates=3*t,maximum_replay_errors=maxerrors,generations=out,method='independent density formula, seeded sample replay, original raw-qualification reward replay, one-step returns/advantage, five-point finite-difference clipped-objective gradient and separate Adam replay',limitation='Same agent and saved dataset; fixed single context, scalar critic is not evidence of multi-step/state-dependent value contribution.',wall_s=time.time()-start,source_sha256=sha(__file__))
def main():
 out=audit();put('audit/PPO_ON_POLICY_REPLAY.json',out);print('PPO_ON_POLICY_REPLAY',out['status'],flush=True)
if __name__=='__main__':main()
