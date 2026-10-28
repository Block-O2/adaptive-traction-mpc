from pathlib import Path
import json,time,hashlib,copy,os,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
from v6_model import fit_cost,predict_cost
from v6_eligibility import fit as fit_eligibility
from v6_selection import select
P=Path(__file__).resolve().parents[1]
fit_perf_start=time.perf_counter();fit_usage_start=resource.getrusage(resource.RUSAGE_SELF)
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
assert not (P/'models/COMMON_COMPOSE_FROZEN.json').exists(),'DO_NOT_OVERWRITE_FROZEN_MODEL'
menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];groups=json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups'];risk=json.loads((P/'models/WHOLE_HISTORY_RISK_V5_FROZEN.json').read_text())['model'];allrows=[]
for g in groups:
 done=json.loads((P/'jobs'/g/'WORKER_DONE.json').read_text());assert done['status'].startswith('PASS'),g
 allrows += [r for r in json.loads((P/'data'/f'{g}.json').read_text()) if r['horizon_s']==.5 and r['tag']!='B']
assert len(set(r['continuation_policy'] for r in allrows))==1,'MIXED_CONTINUATION_LABELS'
phases={};ablation={};validation=[];distributions=[];gate=[]
for phase in ['OUTBOUND','RETURN']:
 rows=[r for r in allrows if r['phase']==phase];gs=sorted(set(r['group'] for r in rows));cv=[]
 for history in [True,False]:
  for g in gs:
   train=[r for r in rows if r['group']!=g];test=[r for r in rows if r['group']==g and r['tag'] in menu];cost=fit_cost(train,history);elig=fit_eligibility(train)
   for index in [0,3]:
    b=dict(cost=cost,risk=risk,eligibility=elig,score_index=index,ood_distance_limit=1e9)
    inp=[{**r,'short_JF':r['labels']['short_JF']} for r in test];decision=select(b,inp);choice=next((r for r in test if r['tag']==decision['choice']),None);valid=[r for r in test if r['qualified']];best=min(valid,key=lambda r:r['labels']['full_remaining_JF']) if valid else None
    err=[p['mean'][0]-r['labels']['tail_JF'] for p,r in zip(decision['rows'],test)]
    cv.append(dict(phase=phase,group=g,history=history,score_index=index,choice=None if choice is None else choice['tag'],qualified=bool(choice is not None and choice['qualified']),no_qualified_candidate_in_actual_menu=not valid,abstained=choice is None,regret_N_s=choice['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'] if choice is not None and choice['qualified'] and best is not None else (0. if not valid and choice is None else None),absolute_tail_RMSE=float(np.sqrt(np.mean(np.array(err)**2))),max_heldout_distance=max(p['distance'] for p in decision['rows']),transformation_fit_on_training_folds_only=True))
 primary=[r for r in cv if r['history']];scores={i:(sum(not r['qualified'] and not (r['no_qualified_candidate_in_actual_menu'] and r['abstained']) for r in primary if r['score_index']==i),float(np.mean([r['regret_N_s'] if r['regret_N_s'] is not None else 1e6 for r in primary if r['score_index']==i]))) for i in [0,3]};score_index=min([3,0],key=lambda i:scores[i]);ood=min(3.,max(1.,max(r['max_heldout_distance'] for r in primary if r['score_index']==score_index)+.25));cost=fit_cost(rows,True);elig=fit_eligibility(rows)
 fixed={}
 for tag in menu:
  rr=[r for r in rows if r['tag']==tag];fixed[tag]={'qualified':sum(r['qualified'] for r in rr),'mean_remaining_JF':float(np.mean([r['labels']['full_remaining_JF'] for r in rr]))}
 fixed_tag=min(menu,key=lambda tag:(-fixed[tag]['qualified'],fixed[tag]['mean_remaining_JF']))
 phases[phase]=dict(cost=cost,risk=risk,eligibility=elig,score_index=score_index,ood_distance_limit=ood,fixed_training_policy_tag=fixed_tag,fixed_training_candidates=fixed,primary_menu=menu,continuation_policy='ONE_CURRENT_CANDIDATE_DECISION_THEN_COMMON_COMPOSE')
 ablation[phase]=dict(cost=fit_cost(rows,False),risk=risk,eligibility=elig,score_index=score_index,ood_distance_limit=ood,primary_menu=menu)
 validation += cv
 X=np.array([r['features'] for r in rows]);distributions.append({'phase':phase,'features':[dict(name=n,min=float(X[:,i].min()),max=float(X[:,i].max()),std=float(X[:,i].std()),scale=cost['x_scale'][i],floor=cost['scale_floor'][i],constant=bool(np.ptp(X[:,i])<=1e-8)) for i,n in enumerate(rows[0]['feature_names'])]})
 for g in gs:
  rr=[r for r in rows if r['group']==g and r['tag'] in menu];one=[r for r in json.loads((P/'data'/f'{g}.json').read_text()) if r['tag'] in menu and r['horizon_s']==1.];valid=[r for r in rr if r['qualified']];best=min(valid,key=lambda r:r['labels']['full_remaining_JF']) if valid else None;s=min(rr,key=lambda r:r['labels']['short_JF']);l=min(one,key=lambda r:r['labels']['short_JF']);gate.append({'group':g,'half':s['tag'],'one':l['tag'],'full':None if best is None else best['tag'],'half_regret_N_s':s['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'] if s['qualified'] and best is not None else None,'one_regret_N_s':l['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'] if l['qualified'] and best is not None else None})
freeze_unix=time.time();source={f'source/{n}':sha(P/'source'/n) for n in ['v6_model.py','v6_selection.py','v6_eligibility.py','v6_data.py','v6_features.py','v6_online.py','v6_fit_freeze.py','v6_common_worker.py','v6_coordinated_return_worker.py','v6_coordinated_return_audit_worker.py','v6_observed_history.py','v6_observed_risk.py']};out={'schema':'v6.common_compose.frozen.v1','frozen_unix':freeze_unix,'train_groups':groups,'phases':phases,'source_sha256':source,'train_data_sha256':{g:sha(P/'data'/f'{g}.json') for g in groups},'test_labels_opened':False,'history_ablation_is_secondary':True,'history_ablation_scope':'history_-prefixed cumulative fields removed from cost regression only; upstream context and both risk heads retained','observed_risk_corpus':'models/WHOLE_HISTORY_RISK_V5_FROZEN.json','all_timing_information_retained':True,'score_selection':'leave-one-whole-parent-out failure count, then true remaining JF regret; tie prefer menu-centered tail','physical_attempt_savings':0}
fit_usage=resource.getrusage(resource.RUSAGE_SELF);out['fit_resources']=dict(wall_s=time.perf_counter()-fit_perf_start,cpu_user_s=fit_usage.ru_utime-fit_usage_start.ru_utime,cpu_system_s=fit_usage.ru_stime-fit_usage_start.ru_stime,peak_process_rss_kib=fit_usage.ru_maxrss,new_native_steps=0,scope='both history variants and whole-parent cross-validation included')
put('models/COMMON_COMPOSE_FROZEN.json',out);put('models/COMMON_COMPOSE_NO_HISTORY_FROZEN.json',{'frozen_unix':freeze_unix,'phases':ablation,'source_sha256':source,'test_labels_opened':False});put('analysis/WHOLE_PARENT_CROSS_VALIDATION.json',validation);put('analysis/V6_TRAIN_FEATURE_DISTRIBUTIONS.json',distributions);put('analysis/PRIMARY_DECISION_GAP_GATE.json',gate)
print('COMMON_FROZEN',freeze_unix,'phases',{ph:{'score_index':b['score_index'],'ood':b['ood_distance_limit'],'fixed':b['fixed_training_policy_tag'],'full_risk_available':b['eligibility']['available']} for ph,b in phases.items()},flush=True)
