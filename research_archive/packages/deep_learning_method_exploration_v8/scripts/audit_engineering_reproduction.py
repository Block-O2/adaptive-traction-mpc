from pathlib import Path
import os,sys,json,time,hashlib,itertools,signal
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'autonomous_learning_smoothness_v7'
sys.path.insert(0,str(P/'runtime/code'))
from stream_runtime_evidence import array_items
signal.alarm(300);start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out=[]
for tag in ['B','LATE_H150','EARLY_H150']:
 a=P/'runtime/source/results'/('V8ENGH01_'+tag);b=V/'runtime/source/results'/('EARLYH01_'+tag)
 errors=[];fields={}
 with np.load(a/'trace.npz') as x,np.load(b/'trace.npz') as y:
  assert set(x.files)==set(y.files)
  for k in x.files:
   same=x[k].shape==y[k].shape and (np.array_equal(x[k],y[k],equal_nan=True) if x[k].dtype.kind in 'fc' else np.array_equal(x[k],y[k]))
   fields[k]=bool(same)
   if not same:errors.append('TRACE:'+k)
  task=x['stage']=='TASK';t=x['time_s'][task]
  jf=float(np.linalg.norm(x['physical_cuff_force_world_n'][task][:-1],axis=1)@np.diff(t))
  jm=float(np.linalg.norm(x['physical_cuff_moment_world_nm'][task][:-1],axis=1)@np.diff(t))
 counts={}
 for name,keys in [('native_states_evaluation_only',['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']),('command_receipts',['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind'])]:
  n=0
  for x,y in itertools.zip_longest(array_items(a/'runtime_artifacts.json.gz',name),array_items(b/'runtime_artifacts.json.gz',name)):
   n+=1
   if x is None or y is None:errors.append(name+':LENGTH');break
   for k in keys:
    if x.get(k)!=y.get(k):errors.append(name+':'+k)
  counts[name]=n
 row=json.loads((P/'attempts'/('V8ENGH01_'+tag+'_RESULT.json')).read_text())
 if abs(jf-row['JF'])>1e-8 or abs(jm-row['JM'])>1e-8:errors.append('INTEGRAL')
 out.append(dict(tag=tag,status='PASS' if not errors else 'FAIL',errors=sorted(set(errors)),trace_fields=fields,counts=counts,JF_rebuilt=jf,JM_rebuilt=jm,original_qualified=row['qualified'],new_trace_sha256=sha(a/'trace.npz'),old_trace_sha256=sha(b/'trace.npz')))
 print('REPRODUCTION_AUDIT',tag,out[-1]['status'],counts,flush=True)
res=dict(status='PASS' if all(r['status']=='PASS' for r in out) else 'FAIL',rows=out,wall_s=time.time()-start,new_physics=0,source_sha256=sha(Path(__file__)),scope='Exact known exposed state and physical/scientific receipt fields; host wall timing excluded; not independent generalization')
(P/'audit/ENGINEERING_REPRODUCTION.json').write_text(json.dumps(res,indent=2)+'\n')
assert res['status']=='PASS',res
