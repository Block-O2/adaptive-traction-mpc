from pathlib import Path
import json,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
A=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1')
p=A/'source/results/Adev_ER';s=json.loads((p/'summary.json').read_text());z=np.load(p/'trace.npz')
print('TRACE',[(k,z[k].shape) for k in z.files]);print('SUMMARY',list(s));print('OPTIONS',s.get('autonomous_recovery'))
ix=z['stage']=='TASK';origin=z['time_s'][ix][0];count={}
for lr in s['learning_records']:
 d=s['decisions'][lr['decision_index']];ph=d['phase'];slot=count.get(ph,0);count[ph]=slot+1
 if ph=='RETURN':print('RETURN',slot,lr['decision_index'],d['decision_request_time_s']-origin,lr['start_time_s']-origin,lr['selected_plan']['schedule']['duration_s'],lr['selected_plan']['schedule']['start_q_rad'],lr['selected_plan']['schedule']['target_q_rad'])
 if ph=='RETURN' and slot==5:
  print('BELIEF',json.dumps(lr['adaptive_state']));print('DECISION',json.dumps(d)[:7000])
for t in [15.5,16.,16.4,16.5,16.895,17.,17.166,17.5,18.]:
 j=int(np.argmin(abs(z['time_s']-origin-t)));print('SAMPLE',t,{k:z[k][j].tolist() for k in z.files if any(x in k for x in ['acceleration','generalized','model_version','torque_component'])})
