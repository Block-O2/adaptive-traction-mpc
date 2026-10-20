"""Save/replay original current activation checks, without live plant state."""
from pathlib import Path
import sys,pickle,time,json,cProfile,pstats,io
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1');sys.path.insert(0,str(S/'code'))
CAPTURES=[];COUNTS={}
def install():
 import study_common as sc,admission_certificates as cert
 original=sc.rt.validate_activation
 def validate(**kw):
  phase=kw['phase'].value;count=COUNTS.get(phase,0);COUNTS[phase]=count+1
  row=None
  if count<2:row=dict(phase=phase,input=pickle.dumps(kw,protocol=5),proof_cache=pickle.dumps(cert.CACHE,protocol=5))
  result=original(**kw)
  if row is not None:row['expected']=pickle.dumps(result,protocol=5);CAPTURES.append(row)
  return result
 sc.rt.validate_activation=validate
def finish(ident):
 (S/'inputs'/(ident+'_ADMISSION_CAUSAL.pkl')).write_bytes(pickle.dumps(CAPTURES,protocol=5))
def main():
 import lean_instrumentation;lean_instrumentation.prime()
 import study_common as sc,admission_certificates as cert
 from traction_mpc_stage4 import estimator_v2 as ma
 ident=sys.argv[1];cfg=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())['inputs'];cfg.update(capture_admission=False,attribution=False,capture_controller_full=False)
 import fast_runtime
 fast_runtime.install(cfg);cert.install()
 rows=pickle.loads((S/'inputs'/(ident+'_ADMISSION_CAUSAL.pkl')).read_bytes());profiler=cProfile.Profile();timings=[];before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 for repeat in range(12):
  for row in rows:
   kw=pickle.loads(row['input']);cert.CACHE.clear();cert.CACHE.update(pickle.loads(row['proof_cache']))
   if repeat==11:profiler.enable()
   started=time.monotonic_ns();value=sc.rt.validate_activation(**kw);elapsed=(time.monotonic_ns()-started)/1e6
   if repeat==11:profiler.disable()
   assert sc.clean(value)==sc.clean(pickle.loads(row['expected'])),'ACTUAL_ADMISSION_MATH_CHANGED'
   if repeat!=11:timings.append(dict(phase=row['phase'],ms=elapsed))
 stream=io.StringIO();pstats.Stats(profiler,stream=stream).sort_stats('tottime').print_stats(55)
 (S/'output'/(ident+'_ADMISSION_REPLAY_PROFILE.txt')).write_text(stream.getvalue())
 out=dict(status='PASS',no_native_physics=True,causal_inputs=len(rows),model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,timings=timings,scope='Original current activation validator on saved immutable arguments plus the exact completed-worker proof cache. No live plant or new proposal, no host qualification.')
 sc.save(ident+'_ADMISSION_REPLAY.json',out);print(json.dumps({k:v for k,v in out.items() if k!='timings'}))
if __name__=='__main__':main()
