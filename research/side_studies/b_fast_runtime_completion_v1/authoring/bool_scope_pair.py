"""N14 prospective scope trial: all six immutable TASK inputs, no live plant."""
from pathlib import Path
import sys,os,pickle,time,json,importlib,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1',FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9',FAST_NATIVE_INTERVALS='N12',FAST_NATIVE_BOOL_REDUCTIONS='N13')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_task_owner,admission_certificates,native_bool_reductions as b
from traction_mpc_stage4 import estimator_v2 as ma
fast_task_owner.warm()
mods=[importlib.import_module(n) for n in b.EXTRA_MODULES];old=[m.np for m in mods];expanded=[b.proxy_numpy(o) for o in old]
input_path=S/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl';rows=pickle.loads(input_path.read_bytes());times={};comparisons=[];before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
try:
 for row in rows:
  if 'expected' not in row:continue
  expected=pickle.loads(row['expected']);want={k:v for k,v in sc.clean(expected).items() if k!='runtime_ms'};expectedproof=admission_certificates.prepare(row['payload'],expected)['proofs']
  byvariant={'N13':[],'N14_SCOPE':[]}
  for rep in range(12):
   for label in (('N13','N14_SCOPE') if rep%2==0 else ('N14_SCOPE','N13')):
    for mod,val in zip(mods,old if label=='N13' else expanded):mod.np=val
    start=time.monotonic_ns();value=fast_task_owner.task_with_certificates(row['payload']);elapsed=(time.monotonic_ns()-start)/1e6
    assert {k:v for k,v in sc.clean(value['value']).items() if k!='runtime_ms'}==want
    assert value['multirate_mechanics_certificates']['proofs']==expectedproof
    if rep:byvariant[label].append(elapsed)
  times[str(row['request_id'])]={label:dict(zip(('p50','p95','p99','max'),np.percentile(v,[50,95,99,100]).tolist())) for label,v in byvariant.items()}
  comparisons.append(dict(request_id=row['request_id'],phase=row['phase'],math_and_proofs_bit_exact=True,paired_calls=24))
finally:
 for mod,val in zip(mods,old):mod.np=val
out=dict(status='PASS',physics_steps=0,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,input_sha256=sc.sha(input_path),timings=times,comparisons=comparisons,extra_scope=list(b.EXTRA_MODULES),native_backend_unchanged=True,scope='Alternating same-interpreter pure TASK replay; all24 calls per input compared to saved original math/proof. No host qualification.')
sc.save('N14_BOOL_SCOPE_PAIR.json',out);print(json.dumps(out))
