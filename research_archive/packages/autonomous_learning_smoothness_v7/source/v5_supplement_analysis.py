"""Evaluation-only counterfactual analysis; no fitting or physical execution."""
from pathlib import Path
import os,sys,json,datetime,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def metrics(i):
 r=read('attempts/'+i+'_RESULT.json');e=read('analysis/extended/'+i+'.json');w=read('analysis/native_wrench/'+i+'.json')
 accepted={p:0 for p in ['OUTBOUND','RETURN']};rejected=accepted.copy()
 for x in r['execution']:
  m=x.get('modal')
  if m and m['phase'] in accepted:
   if m['status']=='ACCEPTED':accepted[m['phase']]+=1
   if m['status']=='REJECTED':rejected[m['phase']]+=1
 return dict(id=i,qualified=r['qualified'],JF=r['JF'],JM=r['JM'],phase_cost=r['phase_cost'],native_phase_jerk_RMS={phase:stats['jerk_deg_s3']['rms'] for phase,stats in e['native_phases'].items()},native_jerk_RMS=e['native_motion']['jerk_deg_s3']['rms'],force_norm_rate_RMS=w['force']['norm_rate']['rms'],moment_norm_rate_RMS=w['moment']['norm_rate']['rms'],force_peak=w['force']['norm']['peak_abs'],force_RMS=w['force']['norm']['rms'],guard=e['guard'],accepted_modal_by_phase=accepted,rejected_modal_by_phase=rejected,tracking_RMS_deg=e['tracking_RMS_deg'],worst_motion_ratio=r['worst_ratio'])
def differences(a,b):
 return dict(JF_delta=a['JF']-b['JF'],JM_delta=a['JM']-b['JM'],jerk_RMS_percent=(100*(np.array(a['native_jerk_RMS'])/b['native_jerk_RMS']-1)).tolist(),force_norm_rate_percent=100*(a['force_norm_rate_RMS']/b['force_norm_rate_RMS']-1),force_peak_percent=100*(a['force_peak']/b['force_peak']-1),force_RMS_percent=100*(a['force_RMS']/b['force_RMS']-1),both_original_qualified=bool(a['qualified'] and b['qualified']))
def identity(a,b):
 checks={}
 for folder,filename in [('runtime/source/results','trace.npz'),('runtime/motion_series',None)]:
  ap=P/folder/a/filename if filename else P/folder/(a+'.npz');bp=P/folder/b/filename if filename else P/folder/(b+'.npz')
  fields=['time_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','cr12_q_rad','cr12_dq_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm'] if filename else ['time_s','true_q_rad','true_dq_rad_s','acceleration_rad_s2','jerk_rad_s3']
  with np.load(ap) as x,np.load(bp) as y:
   for k in fields:checks[folder+':'+k]=bool(np.array_equal(x[k],y[k],equal_nan=True))
 with np.load(P/'runtime/motion_series'/(a+'_NATIVE_WRENCH.npz')) as x,np.load(P/'runtime/motion_series'/(b+'_NATIVE_WRENCH.npz')) as y:
  for k in ['time_s','force_world_n','moment_world_nm']:checks['native_wrench:'+k]=bool(np.array_equal(x[k],y[k],equal_nan=True))
 return dict(a=a,b=b,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,scope='Actual physical/reference fields and native Human/wrench; extra diagnostic labels are intentionally not required equal.')
repair=read('analysis/PPO_REPAIR_GATE.json');repair_rows=[];repair_changes=[]
for i in ['PPOCHECK_FROZEN_MEAN','PPOCHECK_FROZEN_PLUS_RULE','PPOREPAIR01_TIME0','PPOREPAIR01_TIME0_RULE']:
 repair_rows.append(metrics(i))
rr={r['id']:r for r in repair_rows}
for a,b in [('PPOREPAIR01_TIME0','PPOCHECK_FROZEN_MEAN'),('PPOREPAIR01_TIME0_RULE','PPOCHECK_FROZEN_PLUS_RULE'),('PPOREPAIR01_TIME0_RULE','PPOREPAIR01_TIME0')]:repair_changes.append(dict(a=a,b=b,change=differences(rr[a],rr[b])))
if repair['validation_triggered']:
 val=[metrics('PPOREPAIRVAL_'+x) for x in ['B','BEST','MEAN','RULE','TIME0','TIME0_RULE']];v={r['id']:r for r in val}
 for a,b in [('TIME0','MEAN'),('TIME0_RULE','RULE'),('TIME0_RULE','TIME0'),('TIME0_RULE','BEST')]:repair_changes.append(dict(a='PPOREPAIRVAL_'+a,b='PPOREPAIRVAL_'+b,change=differences(v['PPOREPAIRVAL_'+a],v['PPOREPAIRVAL_'+b])))
 repair_rows+=val
repair_identity=identity('PPOREPAIR01_B','PPOCHECK_B');assert repair_identity['status']=='PASS','PPO_REPAIR_NOMINAL_BASELINE_IDENTITY'
rep=dict(nominal_B_replay_identity=repair_identity,status='COMPLETE_COUNTERFACTUAL_ANALYSIS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),gate=repair,rows=repair_rows,comparisons=repair_changes,scope='Frozen actor unchanged; TIME0 and TIME0_RULE are explicit execution repairs, not newly learned policies. Supplementary validation uses its own pre-frozen condition, not primary VAL feedback.',new_physical_START_in_analysis=0)
(P/'analysis/PPO_EXECUTION_REPAIR_RESULTS.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n')
rows=[metrics('TAILRESCUE01_'+t) for t in ['B','SPEEDP','ANT','BLINDM','BLINDP']];checks=[identity('TAILRESCUE01_B','TAILOT_B'),identity('TAILRESCUE01_SPEEDP','TAILOT_SPEEDP')];bad=[c['a'] for c in checks if c['status']!='PASS'];reg=read('experiments/TAIL_RESCUE_PREREGISTRATION.json');start=read('owned/TAIL_RESCUE_QUEUE_START.json');cfg=P/'experiments/TAILRESCUE01.json'
if sha(cfg)!=start['config_sha256']:bad.append('FROZEN_CONFIG_CHANGED')
if sha(P/'source/v5_bounded_anticipatory.py')!=reg['unchanged_branch_model_sha256']:bad.append('UNCHANGED_BRANCH_MODEL_CHANGED')
events=[json.loads(x) for x in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];global_freeze=read('audit/VALIDATION_CONTROL_SOURCE_FREEZE.json');model_frozen_unix=datetime.datetime.fromisoformat(global_freeze['frozen_utc']).timestamp();original_start=min(e['unix'] for e in events if e['event']=='START' and e['id']=='TAILOT_SPEEDP');original_end=max(e['unix'] for e in events if e['event']=='END' and e['id']=='TAILOT_SPEEDP');registration_unix=datetime.datetime.fromisoformat(reg['utc']).timestamp();replay_start=min(e['unix'] for e in events if e['event']=='START' and e.get('group')=='TAILRESCUE01')
if not model_frozen_unix<original_start<original_end<registration_unix<replay_start:bad.append('EXPOSED_FAILURE_REGISTRATION_CHRONOLOGY')
if global_freeze['files']['source/v5_bounded_anticipatory.py']!=reg['unchanged_branch_model_sha256']:bad.append('PRE_FAILURE_MODEL_SOURCE_IDENTITY')
chronology=dict(model_frozen_unix=model_frozen_unix,original_failed_candidate_START_unix=original_start,original_failed_candidate_END_unix=original_end,rescue_registered_unix=registration_unix,rescue_first_START_unix=replay_start)
choices=[];su=read('runtime/source/results/TAILRESCUE01_ANT/summary.json');fork=read('history/TAILRESCUE01_ANT_TAIL_CAUSAL.json')['fork_physical_s']
for lr in su['learning_records']:
 a=lr.get('selected_plan',{}).get('execution_screen',{}).get('v5_anticipatory')
 if a:
  choices.append(dict(request_time_s=lr['request_time_s'],fork_physical_s=fork,activated=lr.get('selected_plan_activated'),meta=a))
  if a.get('truth_used') or a.get('base_risk',{}).get('future_truth_used'):bad.append('CAUSAL_MODEL_FUTURE_TRUTH')
  if abs(lr['request_time_s']-fork)>1e-8:bad.append('ANT_OUTSIDE_CURRENT_DECISION')
res=dict(freeze_and_exposure_chronology=chronology,status='PASS_EVIDENCE_IDENTITY' if not bad else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,original_replay_identity=checks,unchanged_model_choices=choices,errors=bad,scope='Known exposed heldout failure replay, not independent unseen validation. Blind signs distinguish branch-information value from generic perturbation. Frozen Critic negative result is unchanged.',new_physical_START_in_analysis=0)
(P/'analysis/NEW_FAILURE_TAIL_RESCUE_RESULTS.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print('SUPPLEMENT_ANALYSIS',len(repair_rows),'repair rows;',len(rows),'tail rows; identity',res['status']);assert not bad,bad
