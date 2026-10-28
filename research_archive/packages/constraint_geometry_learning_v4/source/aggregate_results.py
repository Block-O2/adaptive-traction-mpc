"""Explicit attempt/resource accounting and descriptive paired results; no new search."""
from pathlib import Path
import os,sys,json,time,statistics,collections
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'));from acl2_shared import read,put,records,sha,utc
import numpy as np
events=records();starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];results=[json.loads(f.read_text()) for f in sorted((P/'attempts').glob('*_RESULT.json'))];by={r['id']:r for r in results};attempts=[]
for s in starts:
 ident=s['id'];ee=[e for e in ends if e['id']==ident];metric=None;source=None
 for suffix in ['_DATA.json','_PARTIAL_COMPUTE.json']:
  f=P/'runtime/output'/(ident+suffix)
  if f.exists():d=json.loads(f.read_text());metric=d.get('metric',d);source=str(f.relative_to(P));break
 native=None if metric is None else metric.get('actual_new_native_physics_steps');attempts.append(dict(id=ident,group=s.get('group'),kind=s.get('kind'),category=s.get('category'),START_unix=s['unix'],END_unix=ee[-1]['unix'] if ee else None,END_count=len(ee),exit_code=ee[-1].get('returncode') if ee else None,actual_new_native_steps=native,source=source,complete=bool(metric and metric.get('task_valid')),qualified=by.get(ident,{}).get('qualified'),wall_s=by.get(ident,{}).get('wall_s'),parent_hash_equal=ee[-1].get('parent_hash_equal') if ee else None))
complete=all(r['END_count']==1 and r['actual_new_native_steps'] is not None for r in attempts);groups={}
for group in sorted({r.get('group') for r in starts}):
 rr=[r for r in results if r['id'].startswith(group+'_')];gg=[r for r in attempts if r['group']==group];qualified=[r for r in rr if r['qualified']];groups[group]=dict(START=len(gg),END=sum(r['END_count'] for r in gg),new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in gg),candidate_complete=sum(r['complete'] for r in rr),candidate_qualified=len(qualified),candidate_count=len(rr),best_qualified_JF=min((r['JF'] for r in qualified),default=None),best_qualified_JM_at_JF=min(qualified,key=lambda r:r['JF'])['JM'] if qualified else None)
account=dict(status='PASS' if complete else 'IN_PROGRESS_OR_PARTIAL',updated_utc=utc(),activation=read('ACTIVATION.json'),physical_START=len(starts),physical_END=len(ends),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in attempts),native_dt_s=.00025,all_starts_accounted=complete,incomplete_ids=[r['id'] for r in attempts if r['END_count']!=1 or r['actual_new_native_steps'] is None],protected_task_failure_ids=[r['id'] for r in results if not r['complete']],motion_failure_ids=[r['id'] for r in results if r['complete'] and not r['qualified']],physical_wall_median_s=statistics.median(r['wall_s'] for r in results) if results else None,groups=groups,attempts=attempts,notes=['Parent cold prefix and all failed candidates counted; inherited full-task prefix included in JF but not double counted as new native physics.','Full cold-parent wall includes child waits, so do not sum parent/child wall as disjoint CPU use.','Startup/serialization/queue-launch failures added zero physical START, preserved in research decisions.','Guard replacements, optimization arms, Learning/PPO new physical attempts: zero. Menu rules share one frozen evaluation menu and are not independent arms.'])
put('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',account)
# Native paired comparisons on common actual physical timestamps.
def native_pair(a,b):
 with np.load(P/'runtime/motion_series'/(a+'.npz')) as x,np.load(P/'runtime/motion_series'/(b+'.npz')) as y:
  tx=x['time_s'];ty=y['time_s'];t=np.intersect1d(np.round(tx,8),np.round(ty,8));ix=np.searchsorted(np.round(tx,8),t);iy=np.searchsorted(np.round(ty,8),t)
  qerr=np.degrees(x['true_q_rad'][ix]-y['true_q_rad'][iy]);verr=np.degrees(x['true_dq_rad_s'][ix]-y['true_dq_rad_s'][iy]);return dict(common_native_rows=len(t),max_abs_q_difference_deg=np.max(abs(qerr),axis=0),max_abs_dq_difference_deg_s=np.max(abs(verr),axis=0),time_arrays_equal=bool(np.array_equal(tx,ty)),q_dq_exact_equal=bool(np.array_equal(x['true_q_rad'],y['true_q_rad']) and np.array_equal(x['true_dq_rad_s'],y['true_dq_rad_s'])))
branchfiles=list((P/'analysis/branches').glob('*.json'));branches={f.stem:json.loads(f.read_text()) for f in branchfiles};local=[]
for ident,b in branches.items():
 if ident.startswith('DEV_LOCAL_'):
  pr=b['prediction'];local.append(dict(id=ident,qualified=b['qualified'],predicted_pass=pr['predicted_motion_pass'],match=b['prediction_motion_match'],JF=b['JF'],JM=b['JM'],curvature=b['minimum_curvature_event']['guard']['model_curvature_m_s2'],predicted_curvature=pr['predicted_curvature_spike'],crosses=len(b['crossing_events']),native_jerk_RMS_deg_s3=b['native_motion']['jerk_deg_s3']['rms'],local_cell_prediction=b['local_cell_prediction'],vs_C19=native_pair('DEV_C19',ident)))
factors=[]
for name in ['BEST','C19']:
 rr=[]
 for lock,floor in [(0,0),(1,0),(0,1),(1,1)]:
  ident=f'FACT_{name}_L{lock}_D{floor}';b=branches.get(ident)
  if b is None:
   if ident in by:
    partial=by[ident];rr.append(dict(id=ident,endpoint_lock=bool(lock),duration_floor=bool(floor),complete=False,qualified=False,JF=None,JM=None,error=partial.get('error'),protected_task_failure=partial.get('protected_task_failure'),actual_new_native_steps=partial.get('actual_new_native_steps')))
   continue
  rr.append(dict(id=ident,complete=True,endpoint_lock=bool(lock),duration_floor=bool(floor),qualified=b['qualified'],JF=b['JF'],JM=b['JM'],curvature=b['minimum_curvature_event']['guard']['model_curvature_m_s2'],crosses=len(b['crossing_events']),jerk_RMS=b['native_motion']['jerk_deg_s3']['rms'],failed=b['motion_failed_requirements'],vs_original=native_pair('DEV_'+name,ident)))
 if rr:factors.append(dict(intent=name,rows=rr,all_four_attempted=len(rr)==4,full_task_count=sum(r['complete'] for r in rr)))
locked=[]
for group in ['VAL_A','VAL_B','VAL_C']:
 rr=[b for ident,b in branches.items() if ident.startswith(group+'_')]
 if rr:locked.append(dict(group=group,condition=read('experiments/'+group+'.json')['condition'],rows=[dict(id=b['id'],qualified=b['qualified'],JF=b['JF'],JM=b['JM'],failed=b['motion_failed_requirements'],crosses=len(b['crossing_events']),curvature=b['minimum_curvature_event']['guard']['model_curvature_m_s2'],prediction=b['prediction']) for b in rr]))
summary=dict(updated_utc=utc(),local_unseen=local,local_accuracy=None if not local else sum(r['match'] for r in local)/len(local),factors=factors,locked=locked,physical_groups=groups,frozen_menu_decision=read('predictions/FROZEN_MENU_DECISION.json'),guard_replacement='NOT_RUN',new_old_guard_equal_budget_optimization='NOT_RUN',learning='NOT_RUN',new_PPO_execution='NOT_RUN')
put('analysis/RESULT_SUMMARY.json',summary);print('ACCOUNT',len(starts),len(ends),'native',account['actual_new_native_steps'],'GROUPS',groups,'LOCAL',len(local),summary['local_accuracy'])
