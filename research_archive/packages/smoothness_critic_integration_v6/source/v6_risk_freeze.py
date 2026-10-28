from pathlib import Path
import os,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
from v6_model import fit_risk,predict_risk,fit_cost,predict_cost
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rows=json.loads((P/'data/LEGACY_B_CAUSAL_RISK_ROWS.json').read_text());model=fit_risk(rows);cv=[]
for g in sorted(set(r['group'] for r in rows)):
 train=[r for r in rows if r['group']!=g];m=fit_risk(train)
 for r in rows:
  if r['group']==g:
   prob=predict_risk(m,{'local_risk_features':r['features']});cv.append(dict(id=r['id'],group=g,observed_native_peak_failed=r['labels_evaluation_only']['already_native_peak_failed'],predicted_risk=prob,rejected=prob is not None and prob>=.5,transform_fit_on_training_groups_only=True))
put('models/OBSERVED_RISK_FROZEN.json',{'model':model,'source_sha256':sha(P/'source/v6_model.py'),'frozen_unix':time.time(),'training_data_sha256':sha(P/'data/LEGACY_B_CAUSAL_RISK_ROWS.json'),'cross_validation':cv,'warning':'5 positive branches from only two failure parents, correlated; probabilities are not calibrated and the whole motion contract is not predicted'})
legacy=[]
for g in ['TAILO1','TAILO2','TAILOT']:
 for r in json.loads((V/'models'/f'{g}_TAIL_LABELS.json').read_text()):
  if r['horizon_s']!=.5:continue
  r['group']=g;r['tag']=r['id'][len(g)+1:];r['phase']='OUTBOUND';r['local_risk_features']=next(x['features'] for x in rows if x['id']==r['id']);legacy.append(r)
cost=fit_cost(legacy,True);loo=[]
for g in ['TAILO1','TAILO2','TAILOT']:
 m=fit_cost([r for r in legacy if r['group']!=g]);ds=[]
 for r in legacy:
  if r['group']!=g:continue
  pr=predict_cost(m,r);ds.append({'tag':r['tag'],'distance':pr['distance'],'score':r['labels']['short_JF']+pr['mean'][0],'full_JF':r['labels']['full_remaining_JF'],'qualified':r['qualified']})
 loo.append({'group':g,'choice':min(ds,key=lambda x:x['score'])['tag'],'rows':ds})
bundle=dict(cost=cost,risk=model,score_index=0,ood_distance_limit=max(1.,max(x['distance'] for g in loo for x in g['rows'])+.25),continuation_policy='original B rolling/replan after exactly one candidate decision')
put('models/LEGACY_B_REVISED_FROZEN.json',{'phases':{'OUTBOUND':bundle},'frozen_unix':time.time(),'train_groups':['TAILO1','TAILO2','TAILOT'],'exposed_old_test_reclassified_as_training':True,'test_groups':['LEGACY_NEW_O'],'clock_floor_s':.5,'failure_costs_included':True,'full_cumulative_history_in_legacy_cost_features':False,'causal_local_history_in_separate_risk_head':True,'loo':loo,'source_sha256':sha(P/'source/v6_model.py')})
print('RISK_FROZEN',len(rows),'CV reject true',sum(x['rejected'] and x['observed_native_peak_failed'] for x in cv),'false',sum(x['rejected'] and not x['observed_native_peak_failed'] for x in cv),'positives',sum(x['observed_native_peak_failed'] for x in cv),flush=True)
