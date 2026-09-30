"""Resumable gated campaign: real scientific simulation for every proposal."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, csv, hashlib, json, os, subprocess, sys, time
import numpy as np
R=Path(__file__).resolve().parents[4]
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/value_learning_research_v1'; RAW=S/'results/value_learning_research_v1'; RUNS=RAW/'runs'
OLD=S/'results/coordination_pacing_exploration_v1/runs'
OD=S/'docs/coordination_pacing_exploration_v1'
RUNNER=Path(__file__).with_name('run_research_rollout.py')
C=json.loads((D/'LEARNING_RESEARCH_V1_CONTRACT.json').read_text())
ENV={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
START=datetime.fromisoformat(C['campaign_start_utc']).timestamp()

def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n'); tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def state(phase,**kw):
 old=json.loads((D/'STATE.json').read_text())
 save(D/'STATE.json',{**old,'phase':phase,'updated_utc':datetime.now(timezone.utc).isoformat(),**kw})
def launch(e):
 p=RUNS/e['run_id']/'rollout_result.json'
 if p.exists():
  old=json.loads(p.read_text())
  if old['status']!='RUNNING':return old
  # A partial unit is evidence. Never overwrite it or treat as completed.
  raise RuntimeError('interrupted unit requires separately named retry:'+e['run_id'])
 spec=RAW/'specs'/(e['run_id']+'.json'); save(spec,e.get('spec'))
 command=[sys.executable,str(RUNNER),'--condition',e['condition'],'--arm',e.get('arm','MATCHED'),'--run-id',e['run_id']]
 if e.get('spec') is not None:command+=['--pattern-file',str(spec)]
 t=time.monotonic()
 proc=subprocess.run(command,env=ENV,capture_output=True,text=True,timeout=300)
 save(RAW/'launches'/(e['run_id']+'.json'),{'entry':e,'command':command,'returncode':proc.returncode,'wall_s':time.monotonic()-t,'stdout':proc.stdout[-3000:],'stderr':proc.stderr[-6000:]})
 if proc.returncode or not p.exists():raise RuntimeError('rollout infrastructure:'+e['run_id']+':'+proc.stderr[-1000:])
 row=json.loads(p.read_text());print(json.dumps({k:row.get(k) for k in ('run_id','condition_id','status','J_F_task_n_s','elapsed_host_s','failure_reason')}),flush=True)
 return row
def targets(p):
 a=json.loads(next(p.glob('rep_*/runtime_artifacts.json')).read_text())
 return [[x['target_q_rad'] for x in d['evaluations'] if x['label']==d['executed_label']][0] for d in a['task_decisions'] if 'evaluations'in d]
def gate():
 if json.loads((D/'SOURCE_RAW_VERIFICATION.json').read_text())['status']!='PASS':raise RuntimeError('invalid provenance')
 state('BASELINE_REPRODUCTION',next_action='reproduce checkpoint baseline then four beneficial paths')
 b=launch({'condition':'low_ordinary_early','arm':'BASELINE','run_id':'baseline_reproduction_v1','spec':None})
 original=json.loads((OLD/'baseline_low_ordinary_early_a/rollout_result.json').read_text())
 baseline_ok=b['status']=='VALID' and abs(b.get('J_F_task_n_s',0)-original['J_F_task_n_s'])<=1e-6
 save(D/'BASELINE_REPRODUCTION.json',{'status':'PASS' if baseline_ok else 'FAIL','original_cost_n_s':original['J_F_task_n_s'],'reproduced':b,'abs_error_n_s':abs(b.get('J_F_task_n_s',0)-original['J_F_task_n_s'])})
 if not baseline_ok:raise RuntimeError('SCIENTIFIC_BASELINE_CANNOT_REPRODUCE')
 state('ACTION_EXPRESSIVITY_GATE')
 rows=[]
 for i,source in enumerate(C['expressivity']['sources']):
  old=json.loads((OLD/source/'rollout_result.json').read_text())
  spec={'mode':'REPLAY','replay_targets':old['planned_segments'],'matched_duration_factor':1.,'descriptor':{'parameters':[old['pattern']['lead']*old['pattern']['amplitude'],old['pattern']['peak']],'horizon':old['pattern']['horizon'],'return_reverse':old['pattern']['return_reverse'],'synchronous':old['pattern']['synchronous']}}
  row=launch({'condition':old['condition_id'],'run_id':f'expressivity_{i:02d}_v1','spec':spec})
  metrics={'source_run_id':source,'replay_run_id':row['run_id'],'status':row['status'],'feasible':row['status']=='VALID'}
  if row['status']=='VALID':
   target_a=np.asarray(targets(OLD/source));target_b=np.asarray(targets(RUNS/row['run_id']))
   metrics['target_max_error_rad']=float(np.max(np.abs(target_a-target_b))) if target_a.shape==target_b.shape else None
   ta=np.load(next((OLD/source).glob('rep_*/trace.npz')));tb=np.load(next((RUNS/row['run_id']).glob('rep_*/trace.npz')))
   for label,key in [('realized_q_max_error_rad','evaluation_only_human_state_rad_rad_s'),('force_max_error_n','physical_cuff_force_world_n')]:
    x=ta[key][ta['stage']=='TASK'];y=tb[key][tb['stage']=='TASK']
    if label.startswith('realized_q'):x=x[:,:2];y=y[:,:2]
    metrics[label]=float(np.max(np.abs(x-y))) if x.shape==y.shape else None
   metrics['J_F_abs_error_n_s']=abs(row['J_F_task_n_s']-old['J_F_task_n_s'])
   metrics['pass']=all(metrics.get(k) is not None and metrics[k]<=v for k,v in C['expressivity']['tolerances'].items())
  else:metrics['pass']=False;metrics['failure_reason']=row.get('failure_reason')
  rows.append(metrics);save(D/'ACTION_EXPRESSIVITY_GATE.json',{'status':'RUNNING','rows':rows})
 passed=all(x['pass'] for x in rows)
 result={'status':'PASS' if passed else 'FAIL','rows':rows,'baseline_reproduction_pass':baseline_ok,'training_permitted':passed,'interface':'ResearchPlanner.screen_target shared by REPLAY, path search, one-step branches and VALUE_RANK; original production execution downstream','safety_relaxed':False}
 save(D/'ACTION_EXPRESSIVITY_GATE.json',result)
 (D/'ACTION_EXPRESSIVITY_GATE.md').write_text('# Action expressivity gate\n\n'+json.dumps(result,indent=2)+'\n')
 state('EXPRESSIVITY_COMPLETE' if passed else 'EXPRESSIVITY_REPAIR_REQUIRED',next_action='CEM reference search' if passed else 'diagnose replay differences without weakening safety')
 if not passed:raise RuntimeError('EXPRESSIVITY_FAILED')

def reference_records():
 rows=[]
 for p in sorted((RAW/'search_proposals').glob('*.json')):
  entry=json.loads(p.read_text());rp=RUNS/entry['run_id']/'rollout_result.json'
  if not rp.exists():continue
  r=json.loads(rp.read_text())
  if r['status']=='RUNNING':continue
  rows.append({**entry,'status':r['status'],'J_F_task_n_s':r.get('J_F_task_n_s'),'elapsed_host_s':r.get('elapsed_host_s'),'failure_reason':r.get('failure_reason'),'duration_s':r.get('duration_s'),'outbound_duration_s':r.get('outbound_duration_s'),'return_duration_s':r.get('return_duration_s'),'planned_segments':r.get('planned_segments')})
 return rows
def summarize_reference():
 rows=reference_records();curve=[];tables=[]
 oldrows=json.loads((OD/'ALL_COORDINATION_ROLLOUTS.json').read_text())
 for condition in C['reference_search']['conditions']:
  selected=sorted([x for x in rows if x['condition']==condition],key=lambda x:x['evaluation_index'])
  previous=[x for x in oldrows if x['condition_id']==condition and x.get('timing_isolated')]
  best_old=min(previous,key=lambda x:x['J_F_task_n_s'])
  baseline=json.loads((OLD/f'matched_baseline_{condition}_certified/rollout_result.json').read_text())
  best=best_old['J_F_task_n_s'];new_best=None
  for i,row in enumerate(selected):
   if row['status']=='VALID' and row['J_F_task_n_s']<best:best=row['J_F_task_n_s'];new_best=row
   curve.append({'condition':condition,'evaluation_count':i+1,'level':row['level'],'restart':row['restart'],'generation':row['generation'],'status':row['status'],'candidate_J_F_n_s':row['J_F_task_n_s'],'best_known_J_F_n_s':best,'path_degrees_of_freedom':{1:2,2:5,3:7}[row['level']]})
  valid=[x for x in selected if x['status']=='VALID']
  level_best={str(level):min([x['J_F_task_n_s'] for x in valid if x['level']<=level]+[best_old['J_F_task_n_s']]) for level in (0,1,2,3)}
  restart_best={f'L{lev}_R{rst}':min([x['J_F_task_n_s'] for x in valid if x['level']==lev and x['restart']==rst],default=None) for lev in (1,2,3) for rst in (0,1)}
  best_run=best_old['run_id'] if new_best is None else new_best['run_id']
  record=json.loads(((OLD if new_best is None else RUNS)/best_run/'rollout_result.json').read_text())
  same_count=all(len(record['planned_segments'][p])==len(baseline['planned_segments'][p]) for p in ('OUTBOUND','RETURN'))
  residual={p:record[p.lower()+'_duration_s']-baseline[p.lower()+'_duration_s'] for p in ('OUTBOUND','RETURN')}
  tables.append({'condition':condition,'baseline_J_F_n_s':baseline['J_F_task_n_s'],'previous_best_J_F_n_s':best_old['J_F_task_n_s'],'best_known_J_F_n_s':best,'improvement_over_previous_n_s':best_old['J_F_task_n_s']-best,'benefit_n_s':baseline['J_F_task_n_s']-best,'best_run_id':best_run,'best_source':'previous' if new_best is None else 'this_search','best_parameters':best_old['pattern'] if new_best is None else new_best['spec']['descriptor'],'evaluations':len(selected),'valid':len(valid),'feasibility_fraction':len(valid)/len(selected) if selected else None,'best_vs_level':level_best,'restart_best':restart_best,'phase_timing_residual_s':residual,'timing_isolated':same_count and max(abs(x) for x in residual.values())<=.025+1e-9,'baseline_duration_s':baseline['duration_s'],'best_duration_s':record['duration_s']})
 save(D/'BEST_KNOWN_REFERENCE_TABLE.json',{'schema':'best_known_reference_v1','rows':tables,'optimization_claim':'best-known observed valid reference, no global optimality','search_evaluations':len(rows),'timing_warning':'Full-task cost optimization includes governor/terminal timing effects. Timing-isolated coordination claims only for flagged equal-count <=25ms phase residual rows.'})
 save(D/'REFERENCE_SEARCH_CONVERGENCE.json',curve)
 if curve:
  with (D/'REFERENCE_SEARCH_CONVERGENCE.csv').open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(curve[0]));writer.writeheader();writer.writerows(curve)
 state('REFERENCE_SEARCH',search_evaluations=len(rows),search_valid=sum(x['status']=='VALID' for x in rows),last_search_summary=tables)
 print(json.dumps({'reference_progress':len(rows),'best':[{k:x[k] for k in ('condition','best_known_J_F_n_s','improvement_over_previous_n_s')} for x in tables]}),flush=True)
 return rows

def search(workers=3):
 if json.loads((D/'ACTION_EXPRESSIVITY_GATE.json').read_text())['status']!='PASS':raise RuntimeError('expressivity gate')
 cutoff=START+4.75*3600
 save(D/'REFERENCE_SEARCH_SETUP.json',{'frozen':C['reference_search'],'workers':workers,'launch_environment':{k:ENV[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},'resource_cutoff_epoch':cutoff})
 (D/'BEST_KNOWN_REFERENCE_SEARCH.md').write_text('# Best-known reference search\n\nNested endpoint-zero smooth coordination basis, CEM with two restarts, baseline/known hip-leading seeds and independent uniform exploration. Every proposal executes through the actual frozen Scientific Simulation. Rejections remain infeasible. Resource cutoff reserves dataset, model, benchmark and pilot work. See setup, raw proposals, result hashes, convergence curves and reference table. All historical/test outcomes remain excluded from model fitting where required.\n')
 all_conditions=C['reference_search']['conditions']
 pool=ThreadPoolExecutor(max_workers=workers)
 try:
  # Interleave conditions within each level to preserve diverse coverage.
  for level,dimension in ((1,2),(2,5),(3,7)):
   for restart in (0,1):
    for ci,condition in enumerate(all_conditions):
     if time.time()>=cutoff:summarize_reference();return
     prior=[r for r in reference_records() if r['condition']==condition and r['status']=='VALID']
     warm=min(prior,key=lambda x:x['J_F_task_n_s'])['spec']['descriptor']['parameters'] if prior else [.12,.5]
     mean=np.asarray((warm+[0]*dimension)[:dimension]);scale=np.array([.08,.16]+[.035]*(dimension-2))
     lower=np.array([-.20,.20]+[-.10]*(dimension-2));upper=np.array([.20,.80]+[.10]*(dimension-2))
     rng=np.random.default_rng(20260930+ci*1000+level*100+restart*10)
     history=[]
     for gen in range(3):
      if time.time()>=cutoff:summarize_reference();return
      vectors=np.clip(rng.normal(mean,scale,size=(8,dimension)),lower,upper)
      vectors[-2:]=rng.uniform(lower,upper,size=(2,dimension))
      if gen==0:
       vectors[0]=np.array([0,.5]+[0]*(dimension-2));vectors[1]=np.array([.12,.5]+[0]*(dimension-2));vectors[2]=mean
       vectors[3]=np.array([-.02,.3]+[0]*(dimension-2))
      entries=[]
      for j,vector in enumerate(vectors):
       # Discrete horizon kept exploratory; no surrogate objective.
       horizon='H3' if j in (0,1,2) else ('H1','H2','H4','H3')[int(rng.integers(4))]
       descriptor={'parameters':vector.tolist(),'horizon':horizon,'return_reverse':False,'level':level}
       run_id=f'search_{condition}_L{level}_R{restart}_G{gen}_C{j:02d}'
       entry={'condition':condition,'run_id':run_id,'level':level,'restart':restart,'generation':gen,'candidate_index':j,'evaluation_index':level*10000+restart*1000+gen*10+j,'spec':{'mode':'PATH','descriptor':descriptor,'matched_duration_factor':1.3}}
       pp=RAW/'search_proposals'/(run_id+'.json')
       if pp.exists():entry=json.loads(pp.read_text())
       else:save(pp,entry)
       entries.append(entry)
      futures={pool.submit(launch,e):e for e in entries};batch=[]
      for f in as_completed(futures):
       e=futures[f];r=f.result();batch.append((e,r));history.append((e,r))
      valid=sorted([(e,r) for e,r in history if r['status']=='VALID'],key=lambda pair:pair[1]['J_F_task_n_s'])
      if valid:
       elite=np.array([e['spec']['descriptor']['parameters'] for e,r in valid[:3]])
       mean=.3*mean+.7*np.mean(elite,axis=0)
       scale=np.maximum(.3*scale+.7*np.std(elite,axis=0),np.array([.012,.04]+[.01]*(dimension-2)))
      save(RAW/'optimizer_states'/f'{condition}_L{level}_R{restart}_G{gen}.json',{'mean':mean.tolist(),'std':scale.tolist(),'valid_elites':[e['run_id'] for e,r in valid[:3]],'all_attempts':[e['run_id'] for e,r in history]})
      summarize_reference()
 finally:pool.shutdown(wait=True)
 summarize_reference();state('REFERENCE_SEARCH_COMPLETE',next_action='targeted immutable-state one-step branch data')

def branches(workers=3):
 if json.loads((D/'ACTION_EXPRESSIVITY_GATE.json').read_text())['status']!='PASS':raise RuntimeError('expressivity gate')
 conditions=[x['id'] for x in json.loads((OD/'CONDITION_MATRIX.json').read_text())['conditions']]
 entries=[]
 for condition in conditions:
  for phase,index in [('OUTBOUND',0),('OUTBOUND',2),('RETURN',0)]:
   for j,offset in enumerate([0.,-.04,-.02,.02,.04]):
    run_id=f'branch_{condition}_{phase.lower()}_{index:02d}_A{j}'
    entries.append({'condition':condition,'run_id':run_id,'spec':{'mode':'BRANCH','descriptor':{'parameters':[0,.5],'horizon':'H4'},'matched_duration_factor':1.3,'branch':{'phase':phase,'index':index,'offset':offset}},'branch_group':f'{condition}:{phase}:{index}','action_index':j})
 pp=D/'ONE_STEP_BRANCH_PLAN.json'
 if pp.exists():entries=json.loads(pp.read_text())['entries']
 else:save(pp,{'status':'FROZEN_BEFORE_BRANCH_ROLLOUTS','entries':entries,'common_continuation':'matched baseline path after one changed target','checkpoint_rule':'identical source checkpoint and deterministic identical prefix; state/reference/model hashes must match before comparing local actions'})
 state('ONE_STEP_BRANCH_DATA')
 results=[]
 with ThreadPoolExecutor(max_workers=workers) as pool:
  futures={pool.submit(launch,e):e for e in entries}
  for f in as_completed(futures):
   e=futures[f];r=f.result();results.append({'entry':e,'status':r['status'],'J_F_task_n_s':r.get('J_F_task_n_s'),'failure_reason':r.get('failure_reason')})
   if len(results)%10==0:save(D/'ONE_STEP_BRANCH_RESULTS.json',results);state('ONE_STEP_BRANCH_DATA',branch_attempts=len(results))
 save(D/'ONE_STEP_BRANCH_RESULTS.json',results);state('BRANCH_DATA_COMPLETE',next_action='extract/validate per-decision actual measured returns and train ridge/MLP')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['gate','search','branches']);p.add_argument('--workers',type=int,default=3);args=p.parse_args()
 if args.phase=='gate':gate()
 elif args.phase=='search':search(args.workers)
 else:branches(args.workers)
