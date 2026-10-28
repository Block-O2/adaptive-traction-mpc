"""Freeze sources/candidates/models, then open preregistered validation once."""
from pathlib import Path
import json,time,copy,hashlib
import numpy as np
from acl2_shared import P,R,read,put,sha,utc,records,decision
def pred(x,model,table,base):
 x=np.asarray(x);center=np.asarray(table['center']);nom=center+x@np.asarray(table['linear']).T+(x*x)@np.asarray(table['quadratic']).T
 anchor=np.array([base['JF']+nom[0]-center[0],base['JM']+nom[1]-center[1],base['worst_ratio']]);sd=np.zeros(3)
 if model:
  X=np.asarray(model['x']);K=np.exp(-np.sum((x[None,:]-X)**2,axis=1)/(2*model['length']**2));mu=K@np.asarray(model['alpha'])*np.asarray(model['scale']);v=np.linalg.solve(np.asarray(model['L']),K);sd=np.sqrt(max(1e-10,1-v@v))*np.asarray(model['scale']);anchor+=mu
 completion_score=None
 if model and model.get('completion_x') is not None:
  cx=np.asarray(model['completion_x']);cy=np.asarray(model['completion_labels']);ck=np.exp(-np.sum((x[None,:]-cx)**2,axis=1)/(2*model['completion_length']**2));completion_score=float((.5+ck@cy)/(1+ck.sum()))
 return dict(kind='FROZEN_NO_FURTHER_UPDATE',empirical_completion_score=completion_score,predicted_outcome=anchor,predicted_sd=sd,actual_task='UNKNOWN',domain='same-prefix model; new legal prefix is out of training context',model_training_ids=model.get('training_attempt_ids',[]) if model else [])
def main():
 if (P/'VALIDATION_INPUT_LOCK.json').exists():raise RuntimeError('VALIDATION_ALREADY_LOCKED_NO_REOPEN')
 A=read('ACTIVATION.json');allocation=read('CORE_ALLOCATION_LOCK.json');history=read('history/RECOVERY_TEST_PLAN.json');rows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()];D={r['id']:r for r in rows};base=D.get('CORE_STRONG',D['RETIMED_STRONG']);candidates={};methods={}
 for arm in ['A','B','C']:
  own=[r for r in rows if r['id'].startswith('CORE_'+arm+'_') and r.get('qualified')];best=min([base]+own,key=lambda r:r['JF']);methods[arm]=dict(selected_development_id=best['id'],JF=best['JF'],no_new_qualified_beyond_parent=not any(r['JF']<base['JF'] for r in own));candidates[arm]=best['action']
 means=[r for r in rows if r['id'].startswith('PPO_SCRATCH_MEAN_') and r.get('qualified')]
 if means:
  best=min(means,key=lambda r:r['JF']);candidates['PPO']=best['action'];methods['PPO']=dict(selected_development_id=best['id'],JF=best['JF'],selection='best qualified frozen-mean development checkpoint; training-sample maximum not substituted')
 joint=[r for r in rows if r['id'].startswith('PARETO_SCOUT_SCOUT_') and r.get('qualified') and r['JF']<base['JF']-.01 and r['JM']<base['JM']-.01]
 if joint:
  best=min(joint,key=lambda r:r['JF']);candidates['PARETO']=best['action'];methods['PARETO']=dict(selected_development_id=best['id'],JF=best['JF'],JM=best['JM'],objective='secondary preregistered joint improvement relative same-chain strong; extra attempts not credited to A/B/C/PPO')
 response=[r for r in rows if r['id'].startswith('RESPONSE_MODEL_') and r.get('qualified')]
 if response:
  best=min(response,key=lambda r:r['JF']);candidates['RESPONSE']=best['action'];methods['RESPONSE']=dict(selected_development_id=best['id'],JF=best['JF'],JM=best['JM'],objective='supplementary causal-reference response model;17 prior tasks plus4 new tests and separate overhead',forward_prediction=best.get('prediction'))
 scalar=[r for r in rows if r['id']=='RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL' and r.get('qualified')]
 if scalar:
  best=scalar[0];candidates['NATIVE_RESPONSE']=best['action'];methods['NATIVE_RESPONSE']=dict(selected_development_id=best['id'],JF=best['JF'],JM=best['JM'],objective='traditional signed finite-difference cost surface on the identical common17 tasks and candidate pool; supplementary budget explicit')
 unique={};method_to_unique={}
 for method,action in candidates.items():
  key=json.dumps(action,sort_keys=True);tag=next((k for k,v in unique.items() if json.dumps(v,sort_keys=True)==key),None)
  if tag is None:tag=method;unique[tag]=action
  method_to_unique[method]=tag
 modelpaths=sorted((P/'models').glob('CORE_C_*.json'));model=json.loads(modelpaths[-1].read_text()) if modelpaths else None;table=read('models/MODAL_NOMINAL_TABLE.json')
 frozen=dict(frozen_utc=utc(),methods=methods,candidates=candidates,unique_candidates=unique,method_to_unique=method_to_unique,model_path=str(modelpaths[-1].relative_to(P)) if modelpaths else None,model_sha256=sha(modelpaths[-1]) if modelpaths else None,model=model,nominal_table_sha256=sha(P/'models/MODAL_NOMINAL_TABLE.json'),nominal_table=table,base=base,source_files={str(f.relative_to(P)):sha(f) for f in (P/'source').glob('*.py')},no_validation_feedback_to_selection=True)
 put('FROZEN_SELECTION.json',frozen)
 # Choose validation size from wall budget, before any held-out outcomes.
 ev=[r for r in records() if r['event']=='START' and r.get('group')=='CORE' and not r['id'].endswith('_parent')];times=[b['unix']-a['unix'] for a,b in zip(ev,ev[1:]) if 20<b['unix']-a['unix']<600];per=float(np.median(times))*1.10 if times else allocation['planning_s_per_attempt'];per=max(30.,per)
 changed=[r for r in rows if r['id'].startswith('CORE_C_') and (r.get('prediction') or {}).get('nominal_counterfactual',{} ) and r['prediction']['nominal_counterfactual'].get('changed_by_learning')][:2]
 nominal_actions=[dict(tag='B',action=dict(family='B')),dict(tag='H150',action=dict(family='legacy2',legacy=[0,0])),dict(tag='STRONG',action=base['action'])]
 for tag,action in unique.items():nominal_actions.append(dict(tag='FROZEN_'+tag,action=action,selected_development_id=methods[tag]['selected_development_id'],prediction=pred(action.get('x',[0]*8),model,table,base)))
 for i,r in enumerate(changed):
  nominal_actions.append(dict(tag='CF%02d_LEARNED'%(i+1),action=r['action'],original_proposal=r['id']))
  z=r['prediction']['nominal_counterfactual']['x'];nominal_actions.append(dict(tag='CF%02d_NOMINAL'%(i+1),action=dict(family='modal8_retimed',x=z,legacy=base['action']['legacy']),original_proposal=r['id']))
 rng=np.random.default_rng(2026102501)
 for i,x in enumerate(rng.uniform(-.65,.65,(6,8))):nominal_actions.append(dict(tag='FAILURE_DOMAIN_%02d'%(i+1),action=dict(family='modal8_retimed',x=x.tolist(),legacy=base['action']['legacy']),prediction=pred(x,model,table,base)))
 total_nominal=1+len(nominal_actions);per_state=4+len(unique);available=A['t0_unix']+9.2*3600-600-time.time()-600;nstate=max(0,min(4,int((available/per-total_nominal)//per_state)))
 if nstate==0 and available/per<total_nominal:nominal_actions=nominal_actions[:3+len(unique)]
 chosenstates=read('LOCKED_VALIDATION_PLAN.json')['conditions'][:nstate]
 put('VALIDATION_ALLOCATION.json',dict(utc=utc(),planning_seconds_per_attempt=per,nominal_actions=len(nominal_actions),independent_states=nstate,selected_prefixes_before_results=chosenstates,unrun_prefixes=read('LOCKED_VALIDATION_PLAN.json')['conditions'][nstate:],rule='first registered prefixes that fit measured remaining wall budget; no outcome-based state selection',earliest_two_changed_C_decisions_for_counterfactuals=[r['id'] for r in changed],failure_domain_seed=2026102501,failure_domain_count=6))
 jobs=[]
 def register(group,cond,actions,order):
  cond=copy.deepcopy(cond);cond['name']=group;acts=[]
  for a in actions:
   a=copy.deepcopy(a);a['category']='validation';acts.append(a)
  c=dict(group=group,condition=cond,B=history['arms'][0],H150=history['arms'][1],actions=acts,mode='validation',local_stop_unix=A['t0_unix']+9.2*3600)
  put('jobs/'+group+'_CONFIG.json',c);put('runtime/'+group+'_TEST_PLAN.json',dict(condition=cond,arms=history['arms']))
  j=dict(id=order+'_'+group,script='acl2_validation_worker.py',args=['jobs/'+group+'_CONFIG.json'],timeout_s=int((len(acts)+1)*per*1.25+300),latest_start_unix=A['t0_unix']+9*3600,requires=['VALIDATION_INPUT_LOCK.json']);jobs.append(j)
 register('LOCKED_REPEAT',history['condition'],nominal_actions,'010')
 for i,state in enumerate(chosenstates):
  actions=[dict(tag='B',action=dict(family='B')),dict(tag='H150',action=dict(family='legacy2',legacy=[0,0])),dict(tag='STRONG',action=base['action'])]
  for tag,action in unique.items():actions.append(dict(tag='FROZEN_'+tag,action=action,prediction=pred(action.get('x',[0]*8),model,table,base)))
  register('LOCKED_STATE_%d'%(i+1),state,actions,'%03d'%(11+i))
 lock=dict(utc=utc(),selection_sha256=sha(P/'FROZEN_SELECTION.json'),validation_allocation_sha256=sha(P/'VALIDATION_ALLOCATION.json'),configs={j['args'][0]:sha(P/j['args'][0]) for j in jobs},validation_worker_sha256=sha(P/'source/acl2_validation_worker.py'),no_later_training_or_tuning=True)
 put('VALIDATION_INPUT_LOCK.json',lock)
 for j in jobs:put('queue/'+j['id']+'.json',j)
 decision('Frozen candidates/models need actual same-state and unseen legal-prefix validation','Lock candidates and allocate unopened registered states',{'unique_candidates':len(unique),'independent_states':nstate,'nominal_actions':len(nominal_actions)},'All selection precedes new validation outcomes; repeated actions deduplicated and method identities retained','Execute locked queue; no retraining or parameter revision after opening',['FROZEN_SELECTION.json','VALIDATION_INPUT_LOCK.json','VALIDATION_ALLOCATION.json'])
 print('VALIDATION_LOCKED',nstate,'states',len(unique),'unique methods',flush=True)
if __name__=='__main__':main()
