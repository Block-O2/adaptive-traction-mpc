"""Durable model-call accounting for pure fixed-input analysis only."""
from pathlib import Path
import os,sys,time,json,runpy,hashlib,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
script=Path(sys.argv[1]).resolve();args=sys.argv[2:]
assert script.name in ('bool_scope_pair.py','hold_equilibrium_pair.py','allocation_reuse_regression.py','allocation_worker_pair.py','cross_shape_attribution.py','full_controller_replay.py','task_input_replay.py','loaded_context_regression.py','small_kernel_regression.py','hold_worker_profile.py','resource_guard_regression.py','geometry_reuse_regression.py','native_geometry_regression.py','native_interval_regression.py','interval_worker_pair.py','bool_reduction_regression.py','native_observer_regression.py','native_quintic_regression.py','native_mechanics_regression.py','value_tree_regression.py','admission_key_regression.py','a1_proof_inspect.py','admission_replay.py','causal_metadata_regression.py'),script
assert script.is_relative_to(S/'code') or script.is_relative_to(Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1'))
start=time.time();runid=f'{time.monotonic_ns()}_{script.stem}';row=dict(id=runid,script=str(script),arguments=args,source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),started_unix=start,physical_native_steps=0)
path=S/'OFFLINE_LEDGER.jsonl'
def append(value):
 with path.open('a') as stream:stream.write(json.dumps(value)+'\n');stream.flush();os.fsync(stream.fileno())
append(row|dict(event='START'));sys.argv=[str(script),*args];status='COMPLETE';error=None
try:runpy.run_path(str(script),run_name='__main__')
except BaseException as e:status='FAILED';error=f'{type(e).__name__}:{e}';traceback.print_exc()
finally:
 ma=sys.modules.get('traction_mpc_stage4.estimator_v2');count=0 if ma is None else ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 append(row|dict(event='END',status=status,error=error,ended_unix=time.time(),wall_seconds=time.time()-start,model_API_calls=count,counter_scope='entire fresh interpreter, including imports/warm/proof comparison/profile'))
 print('OFFLINE_ACCOUNTED',runid,status,count)
if status!='COMPLETE':sys.exit(1)
