from pathlib import Path
import sys,os,pickle,time,json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1',FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9',FAST_NATIVE_INTERVALS='N12',FAST_NATIVE_BOOL_REDUCTIONS='N13')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_task_owner as owner,worker_allocation_reuse as reuse
owner.warm();reuse.install();rows=pickle.loads((S/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl').read_bytes());results=[];rng=np.random.default_rng(2026100727)
for row in rows:
 if 'expected' not in row:continue
 repeat=40 if row['phase']=='HOLD' else 5;times={False:[],True:[]};counts={False:[],True:[]};numeric=[]
 expected=pickle.loads(row['expected']);want={k:v for k,v in sc.clean(expected).items() if k!='runtime_ms'};reference_proofs=None
 for _ in range(repeat):
  for enabled in rng.permutation([False,True]).tolist():
   reuse.ENABLED=enabled;t=time.monotonic_ns();raw=owner.task_with_certificates(row['payload']);elapsed=(time.monotonic_ns()-t)/1e6
   assert {k:v for k,v in sc.clean(raw['value']).items() if k!='runtime_ms'}==want
   proofs=raw['multirate_mechanics_certificates']['proofs']
   if reference_proofs is None:reference_proofs=proofs
   assert proofs==reference_proofs
   times[enabled].append(elapsed);counts[enabled].append(raw['research_model_invocations'])
   if enabled:numeric.append(raw['multirate_mechanics_certificates']['worker_exact_reuse']['numeric_counts'])
 assert counts[False]==counts[True]
 results.append(dict(request_id=row['request_id'],phase=row['phase'],pairs=repeat,original_ms=dict(zip(('p50','p95','p99','max'),np.percentile(times[False],[50,95,99,100]).tolist())),W3_ms=dict(zip(('p50','p95','p99','max'),np.percentile(times[True],[50,95,99,100]).tolist())),paired_saving_median_ms=float(np.median(np.array(times[False])-np.array(times[True]))),same_model_calls=counts[True],numeric_counts=numeric))
out=dict(status='PASS',rows=results,no_physics=True,all_saved_decisions_and_proofs_bit_exact=True,all_original_model_API_preserved=True,scope='Randomized same-interpreter saved immutable TASK input pairs, controller/planner compute only; not host qualification.')
sc.save('W3_ALLOCATION_WORKER_PAIRED.json',out);print(json.dumps({**out,'rows':[{k:v for k,v in r.items() if k not in ('same_model_calls','numeric_counts')} for r in results]}))
