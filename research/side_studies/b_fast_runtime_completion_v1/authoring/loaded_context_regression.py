from pathlib import Path
import sys,pickle,copy,json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
import full_controller_replay as replay
from traction_mpc_stage5 import loaded_execution as le
import loaded_context_reuse as r
captured=[];old=le.build_stage5_loaded_execution_context
def recording(_original=old,**kw):captured.append(kw.copy());return _original(**kw)
r.aliases(recording.__defaults__[0],recording)
function=replay.kernel(sc.rt)
for row in pickle.loads((S/'inputs/012_N3_R2_science_nominal_FULL_CONTROLLER_CAUSAL.pkl').read_bytes()):
 runtime,kw,public=pickle.loads(row['inputs']);runtime['plant']=replay.ControllerPlant(public);runtime.setdefault('startup_alignment_geometry_checks',[])
 function(runtime,**kw)
r.aliases(recording,recording.__defaults__[0])
context,original=r.install();cases=0
for kw in captured:
 token=r.SCOPE.set({})
 try:
  expected=r.fingerprint(original(**kw));a=context(**kw);b=context(**kw)
  assert r.fingerprint(a)==expected==r.fingerprint(b);assert a is b;cases+=2
  next(v for v in vars(b.command_context).values() if isinstance(v,np.ndarray) and v.size).flat[0]+=1e-8
  c=context(**kw);assert c is not b and r.fingerprint(c)==expected;cases+=1
  # Deep-copy all non-plant inputs. Perturb numeric leaves in each raw input,
  # restoring them after each comparison; changes must not return stale data.
  for name in ('measurement','observation','interface_state','human_model','target'):
   obj=copy.deepcopy(kw[name]);vars_=vars(obj)
   arrays=[v for v in vars_.values() if isinstance(v,np.ndarray) and v.size]
   for array in arrays:
    oldvalue=array.flat[0];array.flat[0]=oldvalue+1e-8
    test=kw|{name:obj}
    try:
     actual=context(**test);ref=original(**test);assert r.fingerprint(actual)==r.fingerprint(ref)
    except ValueError as e:
     try:original(**test)
     except ValueError:pass
     else:raise AssertionError(('changed_input_rejected_only_in_fast',name,str(e)))
    finally:array.flat[0]=oldvalue
    cases+=1
  for name in ('neutral_robot_q','torque_limits_nm'):
   v=getattr(kw['plant'],name);prev=v[0];v[0]+=1e-8
   try:assert r.fingerprint(context(**kw))==r.fingerprint(original(**kw))
   finally:v[0]=prev
   cases+=1
 finally:r.SCOPE.reset(token)
 # Crossing a transaction boundary always has a new cache.
 token=r.SCOPE.set({})
 try:assert context(**kw) is not c;cases+=1
 finally:r.SCOPE.reset(token)
out=dict(status='PASS',native_physics_steps=0,captured_context_inputs=len(captured),cases=cases,counters=r.ROWS,
 scope='All fields compared bit-exact; fresh private velocity/J/bias reads; raw input and output mutation invalidation; transaction boundary invalidation.')
(S/'output/LOADED_CONTEXT_R3_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
