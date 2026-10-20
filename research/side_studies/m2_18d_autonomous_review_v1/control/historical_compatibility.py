"""Exact N2 archival comparison; independent streaming parser, no controller imports."""
from pathlib import Path
import os,sys,json,time,itertools,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');Q=P.parent/'m2_18d_baseline_qualification_v1'
spec=importlib.util.spec_from_file_location('independent_arithmetic',P/'control/independent_recompute.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=[]
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
for arm in ['B','E']:
 ident='N2_'+arm;assert any(r['event']=='END' and r['id']==ident and r['returncode']==0 for r in events)
 a=P/'source/results'/ident;b=Q/'source/results'/ident;fields={};errors=[];counts={}
 with np.load(a/'trace.npz') as x,np.load(b/'trace.npz') as y:
  assert set(x.files)==set(y.files)
  for k in x.files:
   fields[k]=bool(x[k].shape==y[k].shape and (np.array_equal(x[k],y[k],equal_nan=True) if x[k].dtype.kind in 'fc' else np.array_equal(x[k],y[k])))
   if not fields[k]:errors.append('trace:'+k)
 for array,keys in [('native_states_evaluation_only',['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']),('command_receipts',['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind'])]:
  count=0
  for x,y in itertools.zip_longest(module.array_items(a/'runtime_artifacts.json.gz',array),module.array_items(b/'runtime_artifacts.json.gz',array)):
   count+=1
   if x is None or y is None:errors.append(array+':length');break
   for k in keys:
    if x.get(k)!=y.get(k):errors.append(array+':'+k)
  counts[array]=count
 rows.append(dict(id=ident,status='PASS' if not errors else 'FAIL',trace_fields=fields,counts=counts,errors=sorted(set(errors)),source=str(b),new_physical=str(a)))
 assert not errors,(ident,errors[:10])
assert not any(n in sys.modules for n in ['mujoco','study_common','campaign','sac_env'])
(P/'audit/N2_HISTORICAL_EXACT_GATE.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),rows=rows,new_physics=0,comparison='Entire trace plus native body/contact/torque and scientific receipt fields, host profiling excluded'),indent=2)+'\n')
print('N2_HISTORICAL_EXACT_PASS')
