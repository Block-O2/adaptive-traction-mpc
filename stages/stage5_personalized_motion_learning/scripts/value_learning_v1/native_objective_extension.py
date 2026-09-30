"""Native-scheduler objective supplement; matched study remains frozen.

Native feedback after declared horizon matches the prior exploration behavior.
No scheduling or feasibility constraints change. Native source expressivity is
verified separately before optimization. Native and matched Q data stay separate.
"""
from datetime import datetime,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,time
import numpy as np
from research_campaign import C,D,RAW,OLD,RUNS,OD,START,launch,save,targets,sha
from confirm_references import normalize_descriptor

def native_sources():
 old=json.loads((OD/'ALL_COORDINATION_ROLLOUTS.json').read_text())
 return {c:min([r for r in old if r['condition_id']==c and r['arm']=='NATIVE' and r['status']=='VALID'],key=lambda r:r['J_F_task_n_s']) for c in C['reference_search']['conditions']}

def freeze():
 sources=native_sources();matrix=json.loads((OD/'CONDITION_MATRIX.json').read_text())
 if (D/'OBJECTIVE_SCOPE_SUPPLEMENT.json').exists():return sources
 audit=[]
 for c,old in sources.items():
  condition=next(r for r in matrix['conditions'] if r['id']==c)
  baseline=json.loads((OLD/condition['baseline_run_id']/'rollout_result.json').read_text())
  audit.append({'condition':c,'native_baseline_J_F_n_s':baseline['J_F_task_n_s'],'native_previous_best_J_F_n_s':old['J_F_task_n_s'],'native_previous_best_run_id':old['run_id'],'native_pattern':old['pattern'],'native_baseline_duration_s':baseline['duration_s']})
 save(D/'PRIMARY_OBJECTIVE_NATIVE_AUDIT.json',{'status':'PASS','rows':audit,'finding':'Native historical costs are below fixed 1.3-duration matched costs; matched coordination progress is a conditional result and cannot be called unrestricted primary-objective improvement.'})
 save(D/'OBJECTIVE_SCOPE_SUPPLEMENT.json',{'status':'FROZEN_BEFORE_NATIVE_EXTENSION','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'original_contract_sha256':sha(D/'LEARNING_RESEARCH_V1_CONTRACT.json'),'original_contract_preserved':True,
  'primary_objective_unchanged':'completed task measured cuff-force integral; safety hard gate',
  'reason':'Include L0 native baseline/best references in absolute primary-objective comparison, supplement native CEM without weakening safety.',
  'learning_study_scope':'original matched-duration dataset/model/8-rep pilot remains a conditional coordination study; native data not silently pooled',
  'native_interface':'original _evaluate native scheduler; original feedback after H1/H2/H3 declared horizon; same production execution/activation stack',
  'native_budget':{'conditions':list(sources),'levels':[1,2,3],'restarts':2,'generations':2,'population':4,'elite':2,'fresh_uniform_fraction':.25,'maximum':288,'cutoff_campaign_hours':6.0},
  'timing_isolation':'Native objective comparisons record actual duration; do not attribute timing-confounded changes to coordination alone',
  'no_controller_math_human_dynamics_safety_or_split_changes':True})
 return sources

def expressivity(sources):
 rows=[]
 for i,c in enumerate(('sync_120','variable_start_120','balanced_high','hip_ordinary')):
  old=sources[c];source=OLD/old['run_id'];original=json.loads((source/'rollout_result.json').read_text())
  record=launch({'condition':c,'arm':'NATIVE','run_id':f'native_expressivity_{i:02d}_v1',
   'spec':{'mode':'REPLAY','timing_policy':'NATIVE_SCHEDULER','replay_targets':original['planned_segments'],'descriptor':normalize_descriptor(old['pattern']),'matched_duration_factor':0.}})
  check={'condition':c,'source_run_id':old['run_id'],'run_id':record['run_id'],'status':record['status'],'pass':False}
  if record['status']=='VALID':
   a=np.asarray(targets(source));b=np.asarray(targets(RUNS/record['run_id']))
   check['target_max_error_rad']=None if a.shape!=b.shape else float(np.max(np.abs(a-b)))
   ta=np.load(next(source.glob('rep_*/trace.npz')));tb=np.load(next((RUNS/record['run_id']).glob('rep_*/trace.npz')))
   for label,key in [('realized_q_max_error_rad','evaluation_only_human_state_rad_rad_s'),('force_max_error_n','physical_cuff_force_world_n')]:
    x=ta[key][ta['stage']=='TASK'];y=tb[key][tb['stage']=='TASK']
    if label.startswith('realized_q'):x=x[:,:2];y=y[:,:2]
    check[label]=None if x.shape!=y.shape else float(np.max(np.abs(x-y)))
   check['J_F_abs_error_n_s']=abs(record['J_F_task_n_s']-old['J_F_task_n_s'])
   check['pass']=all(check.get(k) is not None and check[k]<=v for k,v in C['expressivity']['tolerances'].items())
  rows.append(check);save(D/'NATIVE_ACTION_EXPRESSIVITY_GATE.json',{'status':'RUNNING','rows':rows})
 save(D/'NATIVE_ACTION_EXPRESSIVITY_GATE.json',{'status':'PASS' if all(r['pass'] for r in rows) else 'FAIL','rows':rows,'same_safety_and_native_scheduler':True})
 return all(r['pass'] for r in rows)

def summarize(sources):
 attempts=[];rows=[];curve=[]
 for path in sorted((RAW/'native_search_proposals').glob('*.json')):
  entry=json.loads(path.read_text());rp=RUNS/entry['run_id']/'rollout_result.json'
  if not rp.exists():continue
  result=json.loads(rp.read_text())
  if result['status']=='RUNNING':continue
  attempts.append({**entry,'status':result['status'],'J_F_n_s':result.get('J_F_task_n_s'),'duration_s':result.get('duration_s'),'completion_epoch_s':rp.stat().st_mtime})
 for c,old in sources.items():
  candidates=sorted([r for r in attempts if r['condition']==c],key=lambda r:r['completion_epoch_s']);best=old['J_F_task_n_s'];winner=None
  for count,r in enumerate(candidates,1):
   if r['status']=='VALID' and r['J_F_n_s']<best:best=r['J_F_n_s'];winner=r
   curve.append({'condition':c,'evaluation':count,'level':r['level'],'restart':r['restart'],'generation':r['generation'],'status':r['status'],'J_F_n_s':r['J_F_n_s'],'best_known_J_F_n_s':best})
  audit=next(r for r in json.loads((D/'PRIMARY_OBJECTIVE_NATIVE_AUDIT.json').read_text())['rows'] if r['condition']==c)
  rows.append({'condition':c,'native_baseline_J_F_n_s':audit['native_baseline_J_F_n_s'],'previous_best_J_F_n_s':old['J_F_task_n_s'],'best_known_J_F_n_s':best,
   'improvement_over_previous_n_s':old['J_F_task_n_s']-best,'best_source':'previous' if winner is None else 'native_extension',
   'best_run_id':old['run_id'] if winner is None else winner['run_id'],'best_descriptor':normalize_descriptor(old['pattern']) if winner is None else winner['spec']['descriptor'],
   'evaluations':len(candidates),'valid':sum(r['status']=='VALID' for r in candidates),
   'level_evaluations':{str(l):sum(r['level']==l for r in candidates) for l in (1,2,3)},
   'best_vs_level':{str(l):min([r['J_F_n_s'] for r in candidates if r['status']=='VALID' and r['level']<=l]+[old['J_F_task_n_s']]) for l in (0,1,2,3)},
   'duration_s':old['duration_s'] if winner is None else winner['duration_s'],'baseline_duration_s':audit['native_baseline_duration_s'],
   'timing_isolated_claim':False,'benefit_n_s':audit['native_baseline_J_F_n_s']-best})
 save(D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json',{'status':'RUNNING','rows':rows,'evaluations':len(attempts),'scope':'native scheduler + bounded coordination interface; no global optimality'})
 save(D/'NATIVE_REFERENCE_SEARCH_CONVERGENCE.json',curve)
 print(json.dumps({'native_evaluations':len(attempts),'best':[{k:r[k] for k in ('condition','best_known_J_F_n_s','improvement_over_previous_n_s')} for r in rows]}),flush=True)
 return attempts

def search(sources,workers=1):
 cutoff=START+6.*3600
 with ThreadPoolExecutor(max_workers=workers) as pool:
  for generation in range(2):
   for level,dimension in ((1,2),(2,5),(3,7)):
    for restart in (0,1):
     for ci,c in enumerate(sources):
      if time.time()>=cutoff:summarize(sources);return
      prefix=f'{c}_L{level}_R{restart}'
      history=[r for r in summarize(sources) if r['condition']==c and r['level']==level and r['restart']==restart and r['status']=='VALID']
      old=normalize_descriptor(sources[c]['pattern']);warm=old if not history else min(history,key=lambda r:r['J_F_n_s'])['spec']['descriptor']
      mean=np.array((warm['parameters']+[0]*dimension)[:dimension],float)
      lower=np.array([-.2,.2]+[-.1]*(dimension-2));upper=np.array([.2,.8]+[.1]*(dimension-2))
      rng=np.random.default_rng(20261001+ci*1000+level*100+restart*10+generation*10000)
      scale=np.array([.035,.09]+[.02]*(dimension-2))*(.65 if generation else 1.)
      if generation and history:
       elite=sorted(history,key=lambda r:r['J_F_n_s'])[:2]
       elite_vectors=np.array([r['spec']['descriptor']['parameters'] for r in elite])
       mean=np.mean(elite_vectors,axis=0)
       scale=np.maximum(np.std(elite_vectors,axis=0),np.array([.01,.03]+[.008]*(dimension-2)))
      vectors=np.clip(rng.normal(mean,scale,(4,dimension)),lower,upper);vectors[-1]=rng.uniform(lower,upper)
      if generation==0:vectors[0]=[0.,.5]+[0.]*(dimension-2);vectors[1]=mean
      entries=[]
      for index,vector in enumerate(vectors):
       horizon=warm['horizon'] if index in (1,2) else ('H3' if index==0 else ('H1','H2','H3','H4')[int(rng.integers(4))])
       descriptor={**warm,'parameters':vector.tolist(),'horizon':horizon,'level':level}
       if index==0 and generation==0:
        descriptor.update(synchronous=False,return_reverse=False)
       elif index not in (1,2):
        descriptor.update(synchronous=bool(rng.random()<.2),return_reverse=bool(rng.random()<.5))
       elif index==2:
        descriptor['synchronous']=False
       run_id=f'native_search_{prefix}_G{generation}_C{index:02d}'
       entry={'condition':c,'run_id':run_id,'arm':'NATIVE','level':level,'restart':restart,'generation':generation,
        'spec':{'mode':'NATIVE_PATH','timing_policy':'NATIVE_SCHEDULER','matched_duration_factor':0.,'descriptor':descriptor}}
       proposal_path=RAW/'native_search_proposals'/(run_id+'.json')
       if proposal_path.exists():entry=json.loads(proposal_path.read_text())
       else:save(proposal_path,entry)
       entries.append(entry)
      for future in as_completed([pool.submit(launch,e) for e in entries]):future.result()
      summarize(sources)

if __name__=='__main__':
 sources=freeze()
 if expressivity(sources):search(sources)
 else:print('Native extension gate FAIL; preserved source references remain objective comparators',flush=True)
