from pathlib import Path
import json,sys,pickle,os,time,hashlib,dataclasses
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage4 import estimator_v2 as ma
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
cfg=json.loads((S/'queue/019_C10_science_nominal.json').read_text())
import fast_runtime;fast_runtime.install(cfg)
import fast_task_owner as worker
worker.warm()
paths=[O/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl',O/'inputs/019_N4_V2_C2_science_deviation_TASK_CAUSAL.pkl']
inputs=[]
for p in paths:
 for row in pickle.loads(p.read_bytes()):
  if row['phase']=='HOLD' and 'expected' in row:inputs.append((p,row))
base={}
for p,row in inputs:base[(p.name,row['request_id'])]=worker.task_with_certificates(row['payload'])
import hold_static_mechanics as c;c.install()
import hold_static_schedule as schedule_cache;schedule_cache.install()
import hold_compact_key as compact;compact.install()
records=[]
for p,row in inputs:
 wanted=base[(p.name,row['request_id'])]
 # Prime the pure key using an actual SAVED input; production preparation uses
 # past deployable state and known reference endpoint, never this saved oracle.
 first=worker.task_with_certificates(row['payload']);counts=dict(c.COUNTS)
 begin=time.monotonic_ns();actual=worker.task_with_certificates(row['payload']);elapsed=(time.monotonic_ns()-begin)/1e6
 x=sc.clean(wanted['value']);y=sc.clean(actual['value']);x.pop('runtime_ms');y.pop('runtime_ms')
 proofs=wanted['multirate_mechanics_certificates']['proofs']==actual['multirate_mechanics_certificates']['proofs']
 assert x==y and proofs
 planner,args=pickle.loads(row['payload']);screen=planner.mechanics_screen;schedule=actual['value'].executed.schedule
 k=c.key(screen,args['belief'],schedule.candidate,schedule)
 changed=dataclasses.replace(args['belief'],sequence=args['belief'].sequence+1)
 assert k!=c.key(screen,changed,schedule.candidate,schedule)
 coefficients=schedule.coefficients.copy();coefficients[0,0]+=1e-9
 assert k!=c.key(screen,args['belief'],schedule.candidate,dataclasses.replace(schedule,coefficients=coefficients))
 assert k!=c.key(screen,args['belief'],schedule.candidate,dataclasses.replace(schedule,duration_s=schedule.duration_s+.005))
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule as Q
 original_sample=Q.sample
 try:
  Q.sample=lambda self,x:original_sample(self,x)
  assert c.key(screen,args['belief'],schedule.candidate,schedule) is None
 finally:Q.sample=original_sample
 different=dataclasses.replace(screen,force_limit_n=screen.force_limit_n+1.)
 assert k!=c.key(different,args['belief'],schedule.candidate,schedule)
 # Calling advisory preparation exercises the known-reference-only path.
 c.prepare(row['payload'],actual['value'])
 records.append(dict(input_path=str(p),input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),request_id=row['request_id'],mathematics_bit_exact=x==y,proofs_bit_exact=proofs,cached_worker_ms=elapsed,cache_hit_delta=c.COUNTS['actual_request_hit']-counts.get('actual_request_hit',0),changed_model_misses=True,changed_screen_misses=True))
assert records and all(r['cache_hit_delta']>=1 for r in records)
if hasattr(c,'prepare_guarded'):
 c.prepare_guarded(b'invalid provisional payload',None)
 assert c.ROWS[-1]['event']=='NON_AUTHORITATIVE_PREPARATION_DISCARDED'
out=dict(status='PASS',rows=records,prep_evidence=c.evidence(),model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,source_sha256=hashlib.sha256((S/'code/hold_compact_key.py').read_bytes()).hexdigest(),no_live_plant=True)
name=sys.argv[1] if len(sys.argv)>1 else 'C10_LOCAL_EQUIVALENCE'
target=S/'output'/(name+'.json');assert not target.exists(),'Never overwrite a prior equivalence result';target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],rows=records,model_API_calls=out['model_API_calls'],prep_evidence=c.evidence())))
