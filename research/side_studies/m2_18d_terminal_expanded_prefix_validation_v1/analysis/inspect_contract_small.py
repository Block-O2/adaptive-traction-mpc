from pathlib import Path
import json,sys,os,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
A=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1');sys.path.insert(0,str(A/'control'));from independent_recompute import array_items
import numpy as np
for arm in ['E','T']:
 f=A/'source/results'/('N2_'+arm);s=json.loads((f/'summary.json').read_text());z=np.load(f/'trace.npz');t0=z['time_s'][z['stage']=='TASK'][0]
 print('ARM',arm,'t0',t0,'TIMING',json.dumps(s['timing'])[:1800],flush=True)
 print('PHASE',[(r['to'],r['time_s']-t0) for r in s['task']['phase_transitions']],flush=True)
 print('DECISIONS', [{k:d.get(k) for k in ['phase','phase_elapsed_s','decision_request_time_s','actual_schedule_start_physics_s','executed_label','rolling_composite']} for d in s['decisions'][5:7]],flush=True)
 print('ONLINE_SCHEMA',str(s['online_reference_records'])[:450],flush=True)
 receipts=list(array_items(f/'runtime_artifacts.json.gz','command_receipts'))
 for tm in [6.83,7.05,7.16,7.3,8,9,9.005]:
  r=min(receipts,key=lambda r:abs(r['start_physics_s']-t0-tm))
  print('RECEIPT',tm,{k:r.get(k) for k in ['receipt_index','start_physics_s','end_physics_s','plan_request_id','command_kind','mode','q_ref_rad','dq_ref_rad_s','reference_progress','native_steps']},flush=True)
 print('COUNTS',collections.Counter(r.get('mode') for r in receipts if 6.83<=r['start_physics_s']-t0<9.005),flush=True)
