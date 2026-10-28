"""On-policy PPO on one committed modal plan per legal complete task.

Single nominal context: a diagonal Gaussian actor has eight mean/std pairs;
no neural capacity is needed to represent that context's optimum. New semantics,
scratch training, no historical actor/checkpoint or rollout reuse.
"""
import copy,json,hashlib,time
import numpy as np
from acl2_shared import P,put,read,append,utc,sha,records

def logprob(z,mu,ls):
 z=np.asarray(z);base=np.sum(-.5*((z-mu)/np.exp(ls))**2-ls-.5*np.log(2*np.pi),axis=-1)
 jac=np.sum(2*(np.log(2.)-z-np.logaddexp(0.,-2*z)),axis=-1)
 return base-jac
def adam(theta,g,state,lr):
 state['t']+=1;state['m']=.9*state['m']+.1*g;state['v']=.999*state['v']+.001*g*g
 return theta+lr*(state['m']/(1-.9**state['t']))/(np.sqrt(state['v']/(1-.999**state['t']))+1e-8)
def objective(row,base):
 if not row.get('complete'):return -20.
 if not row.get('qualified'):return -10.-min(5.,max(0.,row['worst_ratio']-1.))
 return float(5*np.tanh((base['JF']-row['JF'])/5))
def sequence(study,C):
 assert read(C.get('interface_gate','audit/INTERFACE_GATE.json'))['new_modes_executable'],'INTERFACE_GATE_REQUIRED'
 family=C.get('family','modal8');center=C.get('center_legacy',[0.,0.])
 for tag,fam in [('B','B'),('H150','legacy2')]:yield dict(tag=tag,action=dict(family=fam,legacy=[0,0]))
 if C.get('center_legacy') is not None:yield dict(tag='STRONG',action=dict(family='legacy2',legacy=center))
 base=copy.deepcopy(study.last_row);rng=np.random.default_rng(C['ppo_seed']);mu=np.zeros(8);ls=np.full(8,np.log(.2));value=0.;mode='SCRATCH_NEW_MODAL8_SEMANTICS'
 if C.get('teacher_action') is not None:
  x=np.asarray(C['teacher_action']['x']);assert np.all(abs(x)<1);mu=np.arctanh(x);mode='TEACHER_INITIALIZED_NEW_ACTOR';assert C.get('teacher_evidence_ids')
 am=dict(t=0,m=np.zeros(8),v=np.zeros(8));asl=copy.deepcopy(am);av=dict(t=0,m=np.zeros(1),v=np.zeros(1));episodes=[];evals=[];updates=[];generation=0
 for batch_start in range(0,C['train_episodes'],C['batch_size']):
  generation+=1;oldmu=mu.copy();oldls=ls.copy();oldvalue=float(value);size=min(C['batch_size'],C['train_episodes']-batch_start)
  z=rng.normal(size=(size,8))*np.exp(oldls)+oldmu;x=np.tanh(z);lp=logprob(z,oldmu,oldls);behavior_id=hashlib.sha256(np.r_[oldmu,oldls,oldvalue,generation].tobytes()).hexdigest()
  put('models/'+study.condition['name']+'/generation_%03d_BEFORE.json'%generation,dict(utc=utc(),mode=mode,generation=generation,behavior_id=behavior_id,mu=oldmu,log_std=oldls,value=oldvalue,rng_state=rng.bit_generator.state,sampled_pre_tanh_z=z,exact_executed_x=x,old_log_probability=lp,action_transform='tanh, no post-sampling clip',one_RL_decision_per_committed_plan=True,teacher_evidence_ids=C.get('teacher_evidence_ids',[])))
  rewards=[];batch=[]
  for j in range(size):
   ep=batch_start+j+1;proposal=dict(training_mode=mode,generation=generation,behavior_id=behavior_id,pre_tanh_z=z[j],mu=oldmu,log_std=oldls,bounded_action=x[j],log_probability=lp[j],sampling_density='exact tanh transformed Gaussian; one frozen behavior per batch',source='causal fixed-prefix context; no future-state inputs')
   yield dict(tag='TRAIN_%04d'%ep,action=dict(family=family,x=x[j].tolist(),legacy=center),category='PPO',prediction=proposal)
   row=copy.deepcopy(study.last_row);reward=objective(row,base);rewards.append(reward);batch.append(row)
   record=dict(episode=ep,RL_decision=ep,id=row['id'],generation=generation,behavior_id=behavior_id,z=z[j],x=x[j],mu=oldmu,log_std=oldls,old_log_probability=lp[j],reward=reward,value_before_update=oldvalue,complete=row.get('complete'),qualified=row.get('qualified'),JF=row.get('JF'),JM=row.get('JM'),worst_ratio=row.get('worst_ratio'),native_steps=row['actual_new_native_steps']);episodes.append(record);append('jobs/'+study.condition['name']+'/RL_ROLLOUTS.jsonl',record)
  rewards=np.asarray(rewards);adv=rewards-oldvalue;normalized=(adv-adv.mean())/(adv.std()+1e-8);epochrows=[]
  # All Adam updates use exactly this generation's complete on-policy batch.
  for epoch in range(C['epochs']):
   newlp=logprob(z,mu,ls);ratio=np.exp(np.clip(newlp-lp,-40,40));clipped=np.clip(ratio,.8,1.2);eligible=~(((normalized>=0)&(ratio>1.2))|((normalized<0)&(ratio<.8)))
   w=eligible*normalized*ratio;dmu=np.mean(w[:,None]*(z-mu)/np.exp(2*ls),axis=0);dls=np.mean(w[:,None]*(((z-mu)/np.exp(ls))**2-1),axis=0)+.002
   norm=np.sqrt(np.sum(dmu*dmu)+np.sum(dls*dls));scale=min(1.,.5/max(norm,1e-12));dmu*=scale;dls*=scale
   before=np.r_[mu,ls].copy();mu=adam(mu,dmu,am,C['mean_lr']);ls=adam(ls,dls,asl,C['std_lr']);ls=np.clip(ls,np.log(.05),np.log(.7));value=float(adam(np.array([value]),np.array([np.mean(rewards-value)]),av,.05)[0])
   logratio=logprob(z,mu,ls)-lp;approxkl=float(np.mean((np.exp(logratio)-1)-logratio));exactkl=float(.5*np.sum((np.exp(2*oldls)+(oldmu-mu)**2)/np.exp(2*ls)-1+2*(ls-oldls)));obj=float(np.mean(np.minimum(ratio*normalized,clipped*normalized)))
   epochrows.append(dict(epoch=epoch+1,Adam_update=am['t'],policy_objective_before_update=obj,ratio_min=float(ratio.min()),ratio_max=float(ratio.max()),clip_fraction=float(np.mean(abs(ratio-1)>.2)),approx_KL_after_update=approxkl,exact_Gaussian_KL_after_update=exactkl,KL_invariant_under_bijective_tanh=True,mean_rms_drift=float(np.sqrt(np.mean((mu-oldmu)**2))),parameter_step_norm=float(np.linalg.norm(np.r_[mu,ls]-before)),gradient_global_norm=float(norm),generation=generation))
   if max(approxkl,exactkl)>.03:break
  update=dict(generation=generation,behavior_id=behavior_id,episodes=[r['id'] for r in batch],reward=rewards,value_before=oldvalue,advantage_raw=adv,advantage_normalized=normalized,returns=rewards,gamma=1.,episode_length_RL_decisions=1,GAE_lambda_irrelevant_for_one_decision=True,epochs=epochrows,mu=mu,log_std=ls,value=value)
  updates.append(update);put('models/'+study.condition['name']+'/generation_%03d_AFTER.json'%generation,dict(utc=utc(),mode=mode,generation=generation,mu=mu,log_std=ls,value=value,Adam_mean=am,Adam_std=asl,Adam_value=av,rng_state=rng.bit_generator.state,training_episodes=len(episodes),RL_decisions=len(episodes),update=update,checkpoint_resume_rule='new unique job/attempt IDs; repeat legal commissioning and count its native steps; retain original T0; never reuse partial rollout as old behavior'))
  append('jobs/'+study.condition['name']+'/PPO_UPDATES.jsonl',update)
  if len(episodes) in C['checkpoints'] or len(episodes)==C['train_episodes']:
   yield dict(tag='MEAN_%04d'%len(episodes),action=dict(family=family,x=np.tanh(mu).tolist(),legacy=center),category='PPO',prediction=dict(generation=generation,kind='FROZEN_MEAN_EVALUATION_NO_UPDATE',training_episodes=len(episodes),RL_decisions=len(episodes),Adam_updates=am['t'],mode=mode))
   ev=copy.deepcopy(study.last_row);evals.append(ev);put('jobs/'+study.condition['name']+'/CHECKPOINT_%04d.json'%len(episodes),dict(utc=utc(),train_episodes=len(episodes),total_physical_branch_attempts=(3 if C.get('center_legacy') is not None else 2)+len(episodes)+len(evals),group_actual_physical_START=sum(r['event']=='START' and r.get('group')==study.condition['name'] for r in records()),cold_parent_counted_in_group_actual_START=True,RL_decisions=len(episodes),Adam_updates=am['t'],mean_evaluation=ev,best_sample=min([r for r in episodes if r['qualified']],key=lambda r:r['JF'],default=None),mu=mu,log_std=ls))
   print('PPO_CHECKPOINT',len(episodes),'mean',ev.get('JF'),'qualified',ev.get('qualified'),'Adam',am['t'],flush=True)
 put('jobs/'+study.condition['name']+'/PPO_RESULTS.json',dict(mode=mode,training_episodes=len(episodes),RL_decisions=len(episodes),Adam_updates=am['t'],episodes=episodes,mean_evaluations=evals,updates=updates,final_mu=mu,final_log_std=ls,base=base,teacher_evidence_ids=C.get('teacher_evidence_ids',[]),no_old_checkpoint_reuse=True,multi_step_value_gap='NOT_TESTED: one committed high-level action per trajectory'))

def preflight():
 rng=np.random.default_rng(4);z=rng.normal(size=(12,8));mu=np.linspace(-.2,.2,8);ls=np.full(8,-1.6);a=rng.normal(size=12)
 analytic=np.mean(a[:,None]*(z-mu)/np.exp(2*ls),axis=0);numeric=[]
 for k in range(8):
  d=np.eye(8)[k]*1e-6;numeric.append(np.mean(a*(logprob(z,mu+d,ls)-logprob(z,mu-d,ls)))/(2e-6))
 err=float(np.max(abs(analytic-numeric)));assert err<1e-7
 assert np.array_equal(np.exp(logprob(z,mu,ls)-logprob(z,mu,ls)),np.ones(12))
 put('audit/PPO_DENSITY_PREFLIGHT.json',dict(status='PASS',mean_gradient_max_error=err,initial_ratio_exact_one=True,source_sha256=sha(__file__),semantics='pre-tanh policy gradients, exact transformed log density, no rollout mixing'))
if __name__=='__main__':preflight()
