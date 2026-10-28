"""Actual counterexample recovery, blind controls and forecast-timing audit."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');rows=[];forecasts=[];identities=[]
for tag in ['FAIL9','ANT9','BLINDM9','BLINDP9','C19','ANTC19','BLINDMC19','BLINDPC19']:
 i='BRANCH02_'+tag;r=json.loads((P/'attempts'/(i+'_RESULT.json')).read_text());e=json.loads((P/'analysis/extended'/(i+'.json')).read_text());w=json.loads((P/'analysis/native_wrench'/(i+'.json')).read_text());rows.append(dict(id=i,qualified=r['qualified'],JF=r['JF'],JM=r['JM'],native_jerk_RMS=e['native_motion']['jerk_deg_s3']['rms'],native_force_norm_rate_RMS=w['force']['norm_rate']['rms'],guard_active=e['guard']['active'],guard_unsatisfied=e['guard']['unsatisfied'],guard_stencil_cross=e['guard']['stencil_cross_count']))
for anti,original in [('ANT9','FAIL9'),('ANTC19','C19')]:
 i='BRANCH02_'+anti;su=json.loads((P/'runtime/source/results'/i/'summary.json').read_text());orig=json.loads((P/'analysis/extended'/('BRANCH02_'+original+'.json')).read_text());events=[r['time_s'] for r in orig['guard']['crossing_records']]
 for lr in su['learning_records']:
  a=lr.get('selected_plan',{}).get('execution_screen',{}).get('v5_anticipatory')
  if not a or not a['changed']:continue
  pred=lr['request_time_s']+a['base_risk']['predicted_event_local_s'];forecasts.append(dict(id=i,decision_index=lr['decision_index'],phase=a['phase'],slot=a['slot'],delta_deg=a['delta_deg'],request_time_s=lr['request_time_s'],predicted_local_s=a['base_risk']['predicted_event_local_s'],predicted_from_request_physical_s=pred,actual_unperturbed_stencil_events_physical_s=events,nearest_absolute_error_s=None if not events else min(abs(t-pred) for t in events),scope='Base-schedule heuristic compared post hoc to a separately executed identical-prefix unperturbed case. This is not a safety certificate; request-to-activation latency and later replans are not modeled.'))
fields=['time_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','cr12_q_rad','cr12_dq_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']
for a,b in [('ANT9','BLINDP9'),('ANTC19','BLINDMC19')]:
 ia='BRANCH02_'+a;ib='BRANCH02_'+b;checks={}
 with np.load(P/'runtime/source/results'/ia/'trace.npz') as x,np.load(P/'runtime/source/results'/ib/'trace.npz') as y:
  for f in fields:checks[f]=bool(np.array_equal(x[f],y[f],equal_nan=True))
 with np.load(P/'runtime/motion_series'/(ia+'.npz')) as x,np.load(P/'runtime/motion_series'/(ib+'.npz')) as y:
  for f in ['time_s','true_q_rad','true_dq_rad_s','acceleration_rad_s2','jerk_rad_s3']:checks['native_'+f]=bool(np.array_equal(x[f],y[f],equal_nan=True))
 identities.append(dict(a=ia,b=ib,physical_and_reference_identity=all(checks.values()),fields=checks,scope='Every listed physical/reference field and native Human series; labels and extra planner diagnostics intentionally differ. Both trials remain separately charged.'))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,forecast_timing=forecasts,anti_vs_matching_blind_physical_identity=identities,conclusions={'recovery_beyond_single_C19':'CONFIRMED on the two known local failure contexts only','causal_candidate_change':'CONFIRMED: selected signed microshifts activated and actual motion improved','independent_branch_information_recovery_value':'NOT_ESTABLISHED: both pre-registered blind signs also recovered both cases','generalization_or_forecast_reliability':'NOT_TESTED outside these local cases; forecast timing reported separately','guard_replacement':'NOT_RUN; original guard and all thresholds unchanged'},new_native_steps_in_analysis=0)
(P/'analysis/BRANCH_BLIND_COUNTERFACTUAL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['id'],r['qualified'],'JF',r['JF'],'jerk',r['native_jerk_RMS'])
print('FORECAST_ERRORS',[(r['id'],r['nearest_absolute_error_s']) for r in forecasts]);print('MATCHING_BLIND_IDENTITIES',[r['physical_and_reference_identity'] for r in identities])
