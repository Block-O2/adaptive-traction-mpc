from pathlib import Path
import sys,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
A=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1')
sys.path.insert(0,str(A/'control'));from independent_recompute import array_items
import numpy as np
for arm in ['E','T']:
 f=A/'source/results'/('N2_'+arm);s=json.loads((f/'summary.json').read_text())
 print('ARM',arm,'TOP',list(s),flush=True)
 print('TASK',json.dumps(s['task']),flush=True)
 print('DECISIONS',json.dumps(s['decisions'][5:]),flush=True)
 lr=s['learning_records'][5];print('LR_KEYS',list(lr),flush=True)
 print('PLAN',json.dumps(lr['selected_plan']),flush=True)
 with np.load(f/'trace.npz') as z:
  print('TRACE',[(k,z[k].shape) for k in z.files],flush=True)
  t0=z['time_s'][z['stage']=='TASK'][0];print('T0',t0,flush=True)
 for name in ['command_receipts','native_states_evaluation_only']:
  found=0
  for row in array_items(f/'runtime_artifacts.json.gz',name):
   t=row.get('start_physics_s',row.get('time_s',0))
   if 6.78+t0<=t<=7.30+t0:
    print(name,json.dumps(row),flush=True);found+=1
    if found>=2:break
