"""Immutable original TASK payload diagnostics; no plant and no new requests."""
from pathlib import Path
import sys,pickle,time,json,cProfile,pstats,io
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1');sys.path.insert(0,str(S/'code'))
CAPTURES={};COUNTS={}
def install():
 import study_common as sc
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 snapshot=sc.rt.snapshot_task_call;result=op.PlanLifecycle.result
 def capture(planner,args):
  payload=snapshot(planner,args);phase=args['phase'].value;count=COUNTS.get(phase,0);COUNTS[phase]=count+1
  import multirate
  life=multirate.RUNTIME.get('plan_lifecycle');request=life._outstanding
  if count<2:CAPTURES[request.request_id]=dict(request_id=request.request_id,phase=phase,original_source_sample_s=request.source_sample_time_s,original_source_capture_ns=request.sensor_capture_ns,payload=payload)
  return payload
 def collect(self,future):
  value=result(self,future);request=self._future_requests.get(future) if self.process_worker else self._outstanding
  if request is not None and request.request_id in CAPTURES:CAPTURES[request.request_id]['expected']=pickle.dumps(value,protocol=5)
  return value
 sc.rt.snapshot_task_call=capture;op.PlanLifecycle.result=collect
def finish(ident):
 (S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).write_bytes(pickle.dumps(list(CAPTURES.values()),protocol=5))
def main():
 import lean_instrumentation;lean_instrumentation.prime()
 import study_common as sc
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 from traction_mpc_stage4 import estimator_v2 as ma
 ident=sys.argv[1];rows=pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes())
 variant=sys.argv[2] if len(sys.argv)>2 else 'ORIGINAL'
 if variant in ('FAST_WORKER','FAST_WORKER_W2','FAST_WORKER_N5','FAST_WORKER_N5_A1','FAST_WORKER_N6_A1','FAST_WORKER_N8_A1','FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):
  if variant=='FAST_WORKER_W2':
   import os
   os.environ['FAST_WORKER_NUMERICAL_REUSE']='W2'
  if variant in ('FAST_WORKER_N5','FAST_WORKER_N5_A1','FAST_WORKER_N6_A1','FAST_WORKER_N8_A1','FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):
   import os
   os.environ['FAST_NATIVE_SMALL_KERNELS']='N5'
  if variant in ('FAST_WORKER_N5_A1','FAST_WORKER_N6_A1','FAST_WORKER_N8_A1','FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):os.environ['FAST_ADMISSION_KEY']='RAW_A1'
  if variant in ('FAST_WORKER_N6_A1','FAST_WORKER_N8_A1','FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):os.environ['FAST_NATIVE_GEOMETRY']='N6'
  if variant in ('FAST_WORKER_N8_A1','FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):os.environ['FAST_NATIVE_VALUE_TREE']='N8'
  if variant in ('FAST_WORKER_N9_A1','FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):os.environ['FAST_NATIVE_QUINTIC']='N9'
  if variant in ('FAST_WORKER_N12_A1','FAST_WORKER_N13_A1'):os.environ['FAST_NATIVE_INTERVALS']='N12'
  if variant=='FAST_WORKER_N13_A1':os.environ['FAST_NATIVE_BOOL_REDUCTIONS']='N13'
  import fast_task_owner
  fast_task_owner.warm()
 elif variant=='FAST_V2':
  import native_vectors
  native_vectors.install(expanded=True)
 else:assert variant=='ORIGINAL'
 records=[];profile=cProfile.Profile();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 for row in rows:
  if 'expected' not in row:continue
  t=time.monotonic_ns();raw=fast_task_owner.task_with_certificates(row['payload']) if variant.startswith('FAST_WORKER') else None;value=raw['value'] if raw is not None else op.execute_task_snapshot(row['payload']);elapsed=(time.monotonic_ns()-t)/1e6
  expected=pickle.loads(row['expected'])
  # The original native decision graph contains controller/planner arithmetic,
  # identity and certificates. Preserve it for an explicit field audit.
  actual=sc.clean(value);wanted=sc.clean(expected)
  mathematical_actual={k:v for k,v in actual.items() if k!='runtime_ms'};mathematical_expected={k:v for k,v in wanted.items() if k!='runtime_ms'}
  proof_equal=True
  if raw is not None:
   import admission_certificates
   proof_equal=admission_certificates.prepare(row['payload'],expected)['proofs']==raw['multirate_mechanics_certificates']['proofs']
  records.append(dict(request_id=row['request_id'],phase=row['phase'],worker_ms=elapsed,actual=actual,expected=wanted,raw_equal=actual==wanted,mathematics_bit_exact=mathematical_actual==mathematical_expected,proofs_bit_exact=proof_equal,worker_metadata=None if raw is None else {k:v for k,v in raw.items() if k!='value'}))
  profile.enable();fast_task_owner.task_with_certificates(row['payload']) if variant.startswith('FAST_WORKER') else op.execute_task_snapshot(row['payload']);profile.disable()
 output=dict(status='PASS' if all(row['mathematics_bit_exact'] and row['proofs_bit_exact'] for row in records) else 'FAIL',variant=variant,no_native_physics=True,input_sha256=sc.sha(S/'inputs'/(ident+'_TASK_CAUSAL.pkl')),excluded_fields=['top-level runtime_ms: original measured wall computation time only'],rows=records,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,profile_scope='one separate replay per input; never part of unprofiled latency or host qualification')
 sc.save(ident+'_TASK_'+variant+'_REPLAY.json',output)
 stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('tottime').print_stats(70);(S/'output'/(ident+'_TASK_'+variant+'_PROFILE.txt')).write_text(stream.getvalue())
 print(json.dumps(dict(status=output['status'],variant=variant,rows=[{k:v for k,v in row.items() if k not in ('actual','expected','worker_metadata')} for row in records],model_API_calls=output['model_API_calls'])))
if __name__=='__main__':main()
