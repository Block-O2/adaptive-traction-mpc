from pathlib import Path
import json,importlib.util,itertools
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
sp=importlib.util.spec_from_file_location('raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
def read(n):return json.loads((P/n).read_text())
out=[]
for g in ['R0','O0']:
 if not (P/(g+'_DONE.json')).exists():continue
 p=P/'source/results'/'W1_B';q=P/'source/results'/(g+'_B');errors=[]
 with np.load(p/'trace.npz') as a,np.load(q/'trace.npz') as b:
  sa=a['stage']!='TASK';sb=b['stage']!='TASK'
  # Only pre-TASK commissioning is used; no future COMPLETE rows.
  firsta=np.flatnonzero(a['stage']=='TASK')[0];firstb=np.flatnonzero(b['stage']=='TASK')[0]
  for k in a.files:
   x=a[k][:firsta];y=b[k][:firstb]
   same=x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y))
   if not same:errors.append('COMMISSIONING_TRACE:'+k)
  origin=float(a['time_s'][firsta]);assert abs(origin-b['time_s'][firstb])<1e-10
 n=0
 for x,y in itertools.zip_longest(raw.array_items(p/'runtime_artifacts.json.gz','native_states_evaluation_only'),raw.array_items(q/'runtime_artifacts.json.gz','native_states_evaluation_only')):
  if x is not None and x['time_s']>=origin-1e-9:break
  n+=1
  if x is None or y is None:errors.append('COMMISSIONING_NATIVE_LENGTH');break
  for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']:
   if x.get(k)!=y.get(k):errors.append('COMMISSIONING_NATIVE:'+k)
 modela=read('reports/W1_B_MEASURED.json')['commissioning'];modelb=read('reports/'+g+'_B_MEASURED.json')['commissioning']
 if modela!=modelb:errors.append('COMMISSIONING_BELIEF_OR_INITIAL_STATE')
 snap_a=read('output/W1_B_DATA.json')['branch_start'];snap_b=read('output/'+g+'_B_DATA.json')['branch_start']
 out.append(dict(control=g,status='PASS' if not errors else 'FAIL',commissioning_native_rows_checked=n,commissioning_and_initial_observables_exact=not errors,errors=sorted(set(errors)),fork_native_hash_W1=snap_a['native_hash'],fork_native_hash_control=snap_b['native_hash'],fork_native_hash_equal=snap_a['native_hash']==snap_b['native_hash'],full_fork_hash_claim='full-state equality is required only within B/T/D of each condition; across conditions future prefix rule deliberately differs',scope='same seed + exact recorded commissioning native/command/history and initial belief checks, followed by only registered background change; no reconstructed Human state assignment'))
assert all(r['status']=='PASS' for r in out),out
(P/'audit/BACKGROUND_MATCHING_AUDIT.json').write_text(json.dumps(dict(status='PASS',conditions=out),indent=2)+'\n')
print(json.dumps(out),flush=True)
