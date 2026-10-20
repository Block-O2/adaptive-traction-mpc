from pathlib import Path
import json,sys,pickle,os,time,copy,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage4 import estimator_v2 as ma
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
cfg=json.loads((S/'queue/014_C9_science_nominal.json').read_text())
import fast_runtime;fast_runtime.install(cfg)
import fast_task_owner as worker;worker.warm()
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1 as C
original=C._plan
import hold_static_mechanics as mechanics;mechanics.install()
cases=[];baseline={};budgets=[]
for name in ('036_N9_V3_A1_C1c_science_nominal','019_N4_V2_C2_science_deviation'):
 p=O/'inputs'/(name+'_TASK_CAUSAL.pkl')
 for row in pickle.loads(p.read_bytes()):
  if row['phase']!='HOLD' or 'expected' not in row:continue
  b=worker.task_with_certificates(row['payload']);cases.append((p,row));baseline[(name,row['request_id'])]=b
  planner,args=pickle.loads(row['payload']);scheduler=planner.planner.scheduler;scheduler.human_model=args['belief'].human_model();candidate=b['value'].executed.schedule.candidate
  # Original TerminalSet planner sets this at decide(), not in its snapshot.
  scheduler.continuous_hold_reference=bool(getattr(planner.planner,'robust_hold_reference',False))
  for elapsed in (0.,.51,1.,9.49,9.5,9.500000001,9.99,10.,-1.,float('nan')):
   kw=dict(current_q_hat_rad=args['current_reference_state'][:2],current_dq_hat_rad_s=args['current_reference_state'][2:],candidate=candidate,phase_elapsed_s=elapsed,use_legacy_nominal_tracking_preview=False)
   clone=pickle.loads(pickle.dumps(scheduler,protocol=5))
   try:out=original(clone,**kw);outcome=('PASS',sc.clean(out))
   except Exception as error:outcome=('REJECT',type(error).__name__,str(error))
   budgets.append((scheduler,kw,outcome))
import hold_static_schedule as cache;cache.install();checks=[]
for scheduler,kw,wanted in budgets:
 clone=pickle.loads(pickle.dumps(scheduler,protocol=5))
 try:out=clone._plan(**kw);actual=('PASS',sc.clean(out))
 except Exception as error:actual=('REJECT',type(error).__name__,str(error))
 assert wanted==actual,(kw['phase_elapsed_s'],wanted,actual)
 checks.append(dict(phase_elapsed_s=str(kw['phase_elapsed_s']),original_result=wanted[0],bit_exact=True))
records=[]
for p,row in cases:
 wanted=baseline[(p.stem.removesuffix('_TASK_CAUSAL'),row['request_id'])]
 # Production advisory path warms exact reference/model contexts only.
 mechanics.prepare_guarded(row['payload'],wanted['value'])
 prime=worker.task_with_certificates(row['payload']);start=time.monotonic_ns();actual=worker.task_with_certificates(row['payload']);elapsed=(time.monotonic_ns()-start)/1e6
 a=sc.clean(wanted['value']);b=sc.clean(actual['value']);a.pop('runtime_ms');b.pop('runtime_ms')
 proofs=wanted['multirate_mechanics_certificates']['proofs']==actual['multirate_mechanics_certificates']['proofs'];assert a==b and proofs
 records.append(dict(source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),request_id=row['request_id'],mathematics_bit_exact=True,proofs_bit_exact=True,cached_worker_ms=elapsed))
if not(cache.COUNTS['exact_input_current_budget_hit']>0 and cache.COUNTS['insufficient_current_budget_fallback']>0):
 fail=dict(status='FAIL_CACHE_NOT_EXERCISED',model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,schedule_cache=cache.evidence(),actual_scheduler_type=str(type(budgets[0][0])),mro=[str(x) for x in type(budgets[0][0]).__mro__],scheduler_flags={k:v for k,v in vars(budgets[0][0]).items() if isinstance(v,(bool,str,int,float))},checks=checks)
 (S/'reports/C9_LOCAL_CACHE_NOT_EXERCISED.json').write_text(json.dumps(fail,indent=2)+'\n');print(json.dumps(fail));raise RuntimeError('CACHE_NOT_EXERCISED')
out=dict(status='PASS',rows=records,budget_boundary_checks=checks,schedule_cache=cache.evidence(),mechanics_cache=mechanics.evidence(),model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,source_sha256=hashlib.sha256((S/'code/hold_static_schedule.py').read_bytes()).hexdigest(),no_current_admission_skipped=True)
p=S/'output/C9_LOCAL_EQUIVALENCE.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('status','rows','schedule_cache','model_API_calls','physics_steps')}))
