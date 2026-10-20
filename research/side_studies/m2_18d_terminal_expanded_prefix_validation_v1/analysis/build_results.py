"""Assemble full per-attempt results; comparisons never change acceptance."""
from pathlib import Path
import os,json,sys,time,gzip,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np

L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def numeric_difference(a,b):
 if isinstance(a,dict):return {k:numeric_difference(v,b[k]) for k,v in a.items()}
 return np.asarray(a)-np.asarray(b)
def comparison_metrics(m):
 return dict(J_F_N_s=m['J_F_N_s'],phase_J_F_N_s={ph:m['phase_cost']['phases'][ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN']},phase_durations_s=m['phase_durations'],task_duration_s=m['dose']['duration_s'],native_full_burden=m['motion']['raw']['full'],native_phase_burden=m['motion']['raw']['phases'],tracking_RMS_deg=m['tracking_RMS_deg'],moment_integral_Nm_s=m['moment_integral_Nm_s'],clearance_m=m['clearance'],force_peak_N=m['force_peak_N'],moment_peak_Nm=m['moment_peak_Nm'],excursion_deg=m['dose']['excursion_deg'],cumulative_travel_deg=m['dose']['cumulative_travel_deg'],endpoint_deg=m['dose']['endpoint_deg'])
records=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in records if r['event']=='START'];ends={r['id']:r for r in records if r['event']=='END'};attempts=[];groups=[]
for start in starts:
 ident=start['id'];end=ends.get(ident);mf=P/'output'/(ident+'_DATA.json');pf=P/'output'/(ident+'_PARTIAL_COMPUTE.json');data=json.loads(mf.read_text()) if mf.exists() else {};metric=data.get('metric',{});partial=json.loads(pf.read_text()) if pf.exists() else None
 if metric:
  inherited=0 if data.get('child') is None else data['child']['physics_step_at_fork']
  assert metric['actual_new_native_physics_steps']+inherited==metric['native_physics_steps']
  independent=read('derived/'+ident+'_INDEPENDENT.json');assert independent['actual_new_native_steps']==metric['actual_new_native_physics_steps']
 attempts.append(dict(id=ident,kind=start.get('kind'),START=start,END=end,returncode=None if end is None else end.get('returncode'),partial=partial is not None or end is None,actual_new_native_steps=metric.get('actual_new_native_physics_steps',None if partial is None else partial.get('actual_new_native_physics_steps')),total_including_inherited_native_steps=metric.get('native_physics_steps'),failure_reason=None if end is None else end.get('error'),physical_metrics_source=str(mf) if mf.exists() else None,partial_evidence=partial))
for g in sys.argv[1:] or ['V1','V2']:
 rr=read(g+'_RESULTS.json');by={r['arm']:r for r in rr['rows']};rowout=[]
 assert read(g+'_DONE.json')['all_children_joined'] and read(g+'_OWNER.json')['returncode']==0
 for r in rr['rows']:
  ident=r['id'];m=read('reports/'+ident+'_MEASURED.json');su=read('source/results/'+ident+'/summary.json');runtime=json.loads(gzip.open(P/'source/results'/ident/'runtime_artifacts.json.gz','rt').read());t0=next(x['start_physics_s'] for x in runtime['wall_physics']['phase_boundaries'] if x['phase']=='TASK');sched=[]
  for lr in su['learning_records']:
   d=su['decisions'][lr['decision_index']];sp=lr['selected_plan'];ss=sp['schedule'];comp=d.get('rolling_composite') or {};splice=comp.get('splice_elapsed_s',0.)
   sched.append(dict(index=lr['decision_index'],request_id=d.get('timing_request_id'),request_task_s=d['decision_request_time_s']-t0,activation_task_s=d.get('actual_schedule_start_physics_s',np.nan)-t0,splice_elapsed_s=splice,suffix_start_task_s=d.get('actual_schedule_start_physics_s',np.nan)-t0+splice,duration_s=ss['duration_s'],target_q_rad=ss['target_q_rad'],target_dq_rad_s=ss['target_dq_rad_s'],free_trajectory=sp['execution_screen'].get('free_trajectory'),terminal_intervention=sp['execution_screen'].get('terminal_duration_intervention'),activated=lr.get('selected_plan_activated'),activation_rejected_reason=d.get('activation_rejected_reason')))
  rowout.append(dict(**r,measured=m,delta_vs_B=dict(**numeric_difference(comparison_metrics(m),comparison_metrics(read('reports/'+g+'_B_MEASURED.json'))),force_reduction_percent=r['motion']['gain_percent']),delta_vs_frozen_18D=numeric_difference(comparison_metrics(m),comparison_metrics(read('reports/'+g+'_E_MEASURED.json'))),execution=dict(schedules=sched,rolling_splice_events=runtime['rolling_splice_events'],fallback_events=runtime['safe_fallback_events'],original_executor_closed=runtime.get('executor_closed'),command_receipt_report=str(P/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')),independent_raw=read('derived/'+ident+'_INDEPENDENT.json'))))
 groups.append(dict(group=g,condition=rr['condition'],rows=rowout,pair_gate=read(g+'_PAIR_GATE.json'),parent_gate=read(g+'_PARENT_GATE.json'),repeat_gate=read('audit/'+g+'_T_REPEAT.json') if (P/'audit'/(g+'_T_REPEAT.json')).exists() else None,independent_raw=read('audit/INDEPENDENT_'+g+'.json')))
put('EXPERIMENT_RESULTS.json',dict(status='COMPLETE',evidence_level='PHYSICAL_LEVEL1',clock='SCIENTIFIC_SIMULATION',same_Human=True,full_task_includes_shared_prefix=True,groups=groups,historical_C_R='Retained as failures in prior package; no additional C/R run',no_threshold_changes=True,no_training=True,host_level2_level3='NOT_ESTABLISHED'))
assert len(starts)==len(ends) and all(a['returncode']==0 and not a['partial'] for a in attempts)
put('ATTEMPT_ACCOUNTING.json',dict(status='PASS',physical_START=len(starts),physical_END=len(ends),limit=30,actual_new_native_steps=sum(a['actual_new_native_steps'] for a in attempts),attempts=attempts,serial_execution='One flock owner; parent paused across serial os.fork branches; each child joined before next START. Parent interval encloses its paused forks and is not simultaneous integration.',no_partial=True,no_physics_for_initial_diagnosis=True,attempts_do_not_include_read_only_math=True))

print('ASSEMBLED',len(groups),'groups',len(starts),'START',flush=True)
