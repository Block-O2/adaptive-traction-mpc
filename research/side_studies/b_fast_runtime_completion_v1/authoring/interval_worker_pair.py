from pathlib import Path
import sys,os,pickle,time,json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1',FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9',FAST_NATIVE_INTERVALS='N12')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
slow=m.monotonic_certificate
import fast_task_owner
fast_task_owner.warm();fast=m.monotonic_certificate
ident='036_N9_V3_A1_C1c_science_nominal';rows=[x for x in pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes()) if x['phase']=='HOLD' and 'expected' in x]
results=[];rng=np.random.default_rng(2026100721)
for row in rows:
 want={k:v for k,v in sc.clean(pickle.loads(row['expected'])).items() if k!='runtime_ms'};samples={'N9':[],'N12':[]};deltas=[]
 for repeat in range(25):
  pair={}
  for label in rng.permutation(['N9','N12']):
   m.monotonic_certificate=slow if label=='N9' else fast;t=time.monotonic_ns();raw=fast_task_owner.task_with_certificates(row['payload']);pair[label]=(time.monotonic_ns()-t)/1e6
   assert {k:v for k,v in sc.clean(raw['value']).items() if k!='runtime_ms'}==want
  if repeat>=3:
   for label,value in pair.items():samples[label].append(value)
   deltas.append(pair['N9']-pair['N12'])
 results.append(dict(request_id=row['request_id'],samples_ms=samples,pair_saving_ms=deltas,median_ms={k:float(np.median(v)) for k,v in samples.items()},median_paired_saving_ms=float(np.median(deltas))))
out=dict(status='PASS',no_native_physics=True,pairs=50,unprofiled_randomized_order=True,discarded_initial_pairs_per_request=3,rows=results,interpretation='Same interpreter and immutable requests, complete original decision+proof. Local speed cannot establish host/R2 qualification.')
sc.save('N12_HOLD_WORKER_PAIRED.json',out);print(json.dumps(out))
