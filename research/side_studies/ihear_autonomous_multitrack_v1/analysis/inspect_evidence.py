from pathlib import Path
import json, os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies'); A=S/'m2_18d_early_return_motion_repair_v1'
I='repair_ER110_R4_120'; p=A/'source/results'/I
su=json.loads((p/'summary.json').read_text());tr=np.load(p/'trace.npz');m=json.loads((A/'reports'/(I+'_MEASURED.json')).read_text())
print('METRIC_KEYS',list(m));print('RAW_FILES',[x.name for x in p.iterdir()]);print('SUMMARY_KEYS',list(su));print('TRACE_FIELDS',tr.files)
origin=float(tr['time_s'][tr['stage']=='TASK'][0]);counts={}
for lr in su['learning_records']:
 d=su['decisions'][lr['decision_index']];ph=d['phase'];slot=counts.get(ph,0);counts[ph]=slot+1
 if ph=='RETURN':
  sc=lr['selected_plan']['schedule'];print(json.dumps(dict(slot=slot,index=lr['decision_index'],request=d['decision_request_time_s']-origin,activation=lr['start_time_s']-origin,schedule=sc,record_keys=list(lr),decision_keys=list(d)),default=str))
print('MOTION_KEYS',m['motion'].keys());print('METRIC_SMALL',json.dumps({k:v for k,v in m.items() if k not in ['motion','native_physical_audit','branch','receipt_audit','request_trace']},default=str)[:10000])
