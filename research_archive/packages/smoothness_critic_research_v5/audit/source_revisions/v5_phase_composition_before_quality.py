"""Finite historical phase-composition proposal model, not an oracle or safety certificate."""
from pathlib import Path
import os,sys,json,copy,datetime,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
from v5_search import objective
from optim_metrics_v1 import evaluate
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def parts(row):
 ident=row['id'];phase_parts={}
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:
  phase=z['phase'];j=np.degrees(z['jerk_rad_s3'])
  for ph in ['OUTBOUND','HOLD','RETURN']:
   k=phase==ph;phase_parts[ph]=dict(native_n=int(k.sum()),jerk_energy=np.sum(j[k]**2,axis=0).tolist(),JF=row['phase_cost'][ph]['J_F_N_s'],JM=row['phase_cost'][ph]['moment_integral_Nm_s'])
 su=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text())
 with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
  k=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][k];_,u=np.unique(t,return_index=True);k=k[u];t=z['time_s'][k];f=np.linalg.norm(z['physical_cuff_force_world_n'][k],axis=1)
 rate=np.gradient(f,t,edge_order=2);phase=np.full(len(t),'OUTBOUND',dtype='<U10')
 for tr in su['task']['phase_transitions']:
  if tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=tr['time_s']-1e-9]=tr['to']
 for ph in phase_parts:
  k=phase==ph;phase_parts[ph].update(force_n=int(k.sum()),force_rate_energy=float(np.sum(rate[k]**2)))
 return phase_parts
def prepare():
 baseline=evaluate('CORE01_BEST');base_j=float(np.linalg.norm(baseline['native_motion']['jerk_deg_s3']['rms']));base_f=baseline['wrench']['force']['norm_rate']['rms'];rows=[]
 for f in (P/'attempts').glob('*_RESULT.json'):
  r=json.loads(f.read_text());a=r['action']
  if r['id'].split('_')[0] not in ['HANDOFF01','OPT01'] or not r['qualified'] or a.get('family')!='modal8_retimed':continue
  if a.get('smooth_strength') or a.get('anticipatory'):continue
  e=evaluate(r['id'])
  if abs(e['duration_s']-baseline['duration_s'])>1e-8:continue
  score,_=objective(r,baseline);rows.append(dict(id=r['id'],action=a,parts=parts(r),score=score,raw_sha256=e['source_raw_sha256']))
 assert rows,'NO_LEGAL_COMPLETED_PHASE_HISTORY'
 byR={}
 for r in rows:byR.setdefault(tuple(round(r['action']['x'][k],12) for k in [5,7]),[]).append(r)
 spreads=[]
 for key,rr in byR.items():
  if len(rr)<2:continue
  jfs=[r['parts']['RETURN']['JF'] for r in rr];jerks=[np.sqrt(np.sum(r['parts']['RETURN']['jerk_energy'])/r['parts']['RETURN']['native_n']) for r in rr]
  spreads.append(dict(R_parameters=list(key),n=len(rr),JF_range=max(jfs)-min(jfs),combined_R_jerk_RMS_range=max(jerks)-min(jerks)))
 maxJF=max((r['JF_range'] for r in spreads),default=float('inf'));maxJ=max((r['combined_R_jerk_RMS_range'] for r in spreads),default=float('inf'))
 def prediction(o,r):
  pp=[o['parts']['OUTBOUND'],o['parts']['HOLD'],r['parts']['RETURN']];n=sum(p['native_n'] for p in pp);nf=sum(p['force_n'] for p in pp);j=np.sqrt(np.sum([p['jerk_energy'] for p in pp],axis=0)/n);fr=float(np.sqrt(sum(p['force_rate_energy'] for p in pp)/nf));jf=sum(p['JF'] for p in pp);jm=sum(p['JM'] for p in pp);score=.65*np.linalg.norm(j)/base_j+.35*fr/base_f+.004*(jf-baseline['JF'])+.004*(jm-baseline['JM']);return dict(score=float(score),JF=jf,JM=jm,jerk_RMS=j.tolist(),force_rate_RMS=fr)
 diagonal=max(abs(prediction(r,r)['score']-r['score']) for r in rows);best=min(r['score'] for r in rows);existing={tuple(np.round(r['action']['x'],12)) for r in rows};proposals=[];seen=set()
 if maxJF<.05 and maxJ<2. and diagonal<1e-8:
  for o in rows:
   for r in rows:
    a=copy.deepcopy(o['action'])
    for k in [2,3,5,7]:a['x'][k]=r['action']['x'][k]
    key=tuple(np.round(a['x'],12))
    if key in existing or key in seen:continue
    pred=prediction(o,r)
    if pred['score']>best-.005:continue
    seen.add(key);proposals.append(dict(action=a,original_OUTBOUND_and_HOLD=o['id'],original_RETURN=r['id'],prediction=pred))
 proposals=sorted(proposals,key=lambda r:r['prediction']['score'])[:3]
 model=dict(frozen_utc=utc(),source_history_count=len(rows),phase_rows=rows,repeat_R_spreads=spreads,max_R_JF_spread=maxJF,max_R_jerk_RMS_spread=maxJ,self_composition_score_error=diagonal,best_existing_S=best,minimum_prospective_score_gain=.005,selected_proposals=proposals,maximum_new_candidates=3,meaning='OUTBOUND+its following HOLD borrowed from one completed candidate, RETURN from another. This is an empirical nominal-Human composition model, never a safety certificate. Original full task/motion verification required.',fairness='Adaptive extra study with union of both primary optimization arms and Handoff histories; not credited to either fixed12-attempt result.')
 put('analysis/PHASE_COMPOSITION_MODEL.json',model)
 if not proposals:
  put('analysis/PHASE_COMPOSITION_DECISION.json',dict(status='NOT_RUN_NO_NOVEL_PREDICTED_GAIN_OR_STRUCTURE_GATE_FAILED',model='analysis/PHASE_COMPOSITION_MODEL.json'));return None
 c=json.loads((P/'experiments/CORE01.json').read_text());c.update(group='COMPOSE01',worker='v5_wrench_worker.py',actions=[dict(tag='B',action={'family':'B'},category='adaptive_phase_composition_anchor')],job_wall_cap_s=5400);c['condition']['name']='COMPOSE01'
 for i,r in enumerate(proposals,1):c['actions'].append(dict(tag=f'PAIR{i:02d}',action=r['action'],category='adaptive_phase_composition',prediction=dict(type='EMPIRICAL_PHASE_COMPOSITION',**r['prediction'],original_OUTBOUND_and_HOLD=r['original_OUTBOUND_and_HOLD'],original_RETURN=r['original_RETURN'],future_truth_used=False,all_inputs_completed_before_START=True)))
 put('experiments/COMPOSE01.json',c);put('runtime/COMPOSE01_TEST_PLAN.json',c);put('analysis/PHASE_COMPOSITION_DECISION.json',dict(status='FROZEN_NOVEL_CANDIDATES_BEFORE_START',candidate_count=len(proposals),config_sha256=hashlib.sha256((P/'experiments/COMPOSE01.json').read_bytes()).hexdigest()))
 return 'COMPOSE01'
