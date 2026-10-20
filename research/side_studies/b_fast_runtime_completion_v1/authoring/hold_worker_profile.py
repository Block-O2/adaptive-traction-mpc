"""Saved original HOLD requests: measured worker plus separate profile, no plant."""
from pathlib import Path
import sys,pickle,time,json,cProfile,pstats,io,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1')
if len(sys.argv)>2 and sys.argv[2]=='N9':os.environ.update(FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9')
if len(sys.argv)>2 and sys.argv[2] in ('N12','N13'):os.environ.update(FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9',FAST_NATIVE_INTERVALS='N12')
if len(sys.argv)>2 and sys.argv[2]=='N13':os.environ.update(FAST_NATIVE_BOOL_REDUCTIONS='N13')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_task_owner,admission_certificates
from traction_mpc_stage4 import estimator_v2 as ma
import numpy as np
ident=sys.argv[1];rows=[r for r in pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes()) if r['phase']=='HOLD' and 'expected' in r]
assert len(rows)==2
fast_task_owner.warm();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS;results=[];profile=cProfile.Profile()
for row in rows:
 expected=pickle.loads(row['expected']);want={k:v for k,v in sc.clean(expected).items() if k!='runtime_ms'};times=[];decision=[];proof=[];calls=[]
 for repeat in range(16):
  start=time.monotonic_ns();raw=fast_task_owner.task_with_certificates(row['payload']);finish=time.monotonic_ns()
  assert {k:v for k,v in sc.clean(raw['value']).items() if k!='runtime_ms'}==want
  assert admission_certificates.prepare(row['payload'],expected)['proofs']==raw['multirate_mechanics_certificates']['proofs']
  times.append((finish-start)/1e6);decision.append((raw['native_decision_finish_ns']-raw['worker_start_ns'])/1e6);proof.append((raw['proposal_ready_ns']-raw['native_decision_finish_ns'])/1e6);calls.append(raw['research_model_invocations'])
 profile.enable();fast_task_owner.task_with_certificates(row['payload']);profile.disable()
 results.append(dict(request_id=row['request_id'],worker_ms=dict(zip(('p50','p95','p99','max'),[float(x) for x in np.percentile(times,[50,95,99,100])])),decision_ms=decision,proof_ms=proof,model_calls_per_request=calls,exact_reuse=raw['multirate_mechanics_certificates']['worker_exact_reuse']))
out=dict(status='PASS',rows=results,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,no_native_physics=True,variant=sys.argv[2] if len(sys.argv)>2 else 'N5',scope='saved original immutable HOLD payloads; complete decision and selected/escape proof, separate profiled replays',input_sha256=sc.sha(S/'inputs'/(ident+'_TASK_CAUSAL.pkl')))
sc.save(ident+'_'+(sys.argv[2] if len(sys.argv)>2 else 'N5')+'_HOLD_WORKER_PROFILE.json',out)
stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('tottime').print_stats(70);(S/'output'/(ident+'_'+(sys.argv[2] if len(sys.argv)>2 else 'N5')+'_HOLD_WORKER_PROFILE.txt')).write_text(stream.getvalue())
print(json.dumps(out))
