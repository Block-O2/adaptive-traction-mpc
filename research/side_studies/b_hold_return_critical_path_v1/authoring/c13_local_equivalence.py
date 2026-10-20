from pathlib import Path
import os,sys,json,pickle,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage4 import estimator_v2 as ma
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
cfg=json.loads((S/'queue/035_C13_science_nominal.json').read_text());cfg['task_decode_once']=False
import fast_runtime;fast_runtime.install(cfg)
import fast_task_owner as w;w.warm()
import hold_static_mechanics as mech,hold_static_schedule as schedule,hold_compact_key as compact
mech.install();schedule.install();compact.install()
cases=[];baseline={}
for name in ('036_N9_V3_A1_C1c_science_nominal','019_N4_V2_C2_science_deviation'):
 p=O/'inputs'/f'{name}_TASK_CAUSAL.pkl'
 for row in pickle.loads(p.read_bytes()):
  if 'expected' not in row:continue
  cases.append((p,row));baseline[(name,row['request_id'])]=w.task_with_certificates(row['payload'])
import task_decode_once as d;d.install();os.environ['FAST_TASK_DECODE_ONCE']='C13';records=[]
for p,row in cases:
 wanted=baseline[(p.stem.removesuffix('_TASK_CAUSAL'),row['request_id'])]
 start=time.monotonic_ns();actual=w.task_with_certificates(row['payload']);elapsed=(time.monotonic_ns()-start)/1e6
 a=sc.clean(wanted['value']);b=sc.clean(actual['value']);a.pop('runtime_ms');b.pop('runtime_ms')
 proofs=wanted['multirate_mechanics_certificates']['proofs']==actual['multirate_mechanics_certificates']['proofs'];assert a==b and proofs
 decoded=pickle.loads(row['payload']);belief_before=pickle.dumps(decoded[1]['belief'],protocol=5)
 d.EXECUTE(decoded);assert belief_before==pickle.dumps(decoded[1]['belief'],protocol=5),'Original decision unexpectedly mutated belief'
 records.append(dict(input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),request_id=row['request_id'],phase=row['phase'],math_bit_exact=True,proofs_bit_exact=True,original_belief_unchanged=True,worker_ms=elapsed))
out=dict(status='PASS',rows=records,AST_provenance=d.EVIDENCE,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0)
p=S/'output/C13_LOCAL_EQUIVALENCE.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
