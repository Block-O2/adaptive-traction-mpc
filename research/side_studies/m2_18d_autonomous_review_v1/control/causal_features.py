"""Describe exposed causal covariates; never fit a state admission rule."""
from pathlib import Path
import json,os,time,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');Q=P.parent/'m2_18d_baseline_qualification_v1'
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False)+'\n')
rows=[]
for group in ['N1','N2','N3','N4']:
 su=json.loads((Q/'source/results'/(group+'_E')/'summary.json').read_text());f=json.loads((Q/'audit'/(group+'_FORK_CONTEXT.json')).read_text());fork=f['physical_s']
 with np.load(Q/'motion_series'/(group+'_E.npz')) as z:
  i=int(np.argmax(abs(z['acceleration_rad_s2'][:,1])));peak=float(z['time_s'][i]);a=float(np.rad2deg(z['acceleration_rad_s2'][i,1]))
 with np.load(Q/'source/results'/(group+'_B')/'trace.npz') as z:
  ix=int(np.argmin(abs(z['time_s']-fork)));assert abs(z['time_s'][ix]-fork)<1e-8
  causal=dict(estimated_human_state_rad_rad_s=z['estimated_human_state_rad_rad_s'][ix],issued_q_rad=z['reference_q_rad'][ix],issued_dq_rad_s=z['reference_dq_rad_s'][ix],issued_ddq_rad_s2=z['reference_ddq_rad_s2'][ix],position_tracking_estimate_rad=z['estimated_human_state_rad_rad_s'][ix,:2]-z['reference_q_rad'][ix],velocity_tracking_estimate_rad_s=z['estimated_human_state_rad_rad_s'][ix,2:]-z['reference_dq_rad_s'][ix])
 schedule=[]
 for lr in su['learning_records']:
  d=su['decisions'][lr['decision_index']];ss=lr.get('selected_plan',{}).get('schedule',{});ts=d['decision_request_time_s'];act=d.get('actual_schedule_start_physics_s')
  schedule.append(dict(decision_index=lr['decision_index'],request_physics_s=ts,activation_physics_s=act,peak_minus_request_s=peak-ts,peak_minus_activation_s=None if act is None else peak-act,duration_s=ss.get('duration_s'),target_dq_deg_s=np.rad2deg(ss['target_dq_rad_s']) if 'target_dq_rad_s' in ss else None,reference_max_acceleration_deg_s2=np.rad2deg(ss['maximum_reference_acceleration_rad_s2']) if 'maximum_reference_acceleration_rad_s2' in ss else None))
 prior=[r for r in schedule if r['request_physics_s']<=peak];nearest=max(prior,key=lambda r:r['request_physics_s']) if prior else None
 rows.append(dict(group=group,causal_state_at_fork=causal,fork_physics_s=fork,fork_task_s=f['task_s'],evaluation_only_knee_peak=dict(physics_s=peak,task_s=peak-10.05,value_deg_s2=a),preceding_request=nearest,schedules=schedule))
put('derived/EXPOSED_CAUSAL_FEATURES.json',dict(unix=time.time(),historical_raw=True,new_physics=0,rows=rows,filter_trained=False,claim='Causal features are available but four exposed conditions do not justify a deployable risk boundary. Evaluation peak labels and truth must never enter online candidate choice.'))
print('CAUSAL_FEATURES',[(r['group'],r['evaluation_only_knee_peak']['value_deg_s2'],r['preceding_request']['peak_minus_request_s']) for r in rows])
