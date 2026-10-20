"""Alternating fixed-input controller calls; no coupled plant or physics."""
from pathlib import Path
import sys,pickle,json,time,copy
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_runtime,full_controller_replay as replay,hold_equilibrium_reuse as reuse,numpy as np
from traction_mpc_stage4 import estimator_v2 as ma
def main():
 ident='030_N5_V3_A1_C1c_science_nominal';cfg=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())['inputs']
 cfg.update(attribution=False,capture_controller_full=False,reuse_shadow=False,numerical_reuse=False,native_cross_expanded=True,loaded_context_reuse=True,native_small_kernels=True,native_geometry=True,native_value_tree=True,native_quintic=True,native_intervals=True,native_bool_reductions=True)
 fast_runtime.install(cfg);reuse.install();function=replay.kernel(sc.rt,extended=True)
 import loaded_context_reuse
 function=loaded_context_reuse.transaction(function)
 records=pickle.loads((S/'inputs'/(ident+'_FULL_CONTROLLER_CAUSAL.pkl')).read_bytes());plants={id(r):replay.ControllerPlant(pickle.loads(r['inputs'])[2]) for r in records}
 times={'ORIGINAL':[],'H1':[]};types_seen=[];saved_original=reuse.ORIGINAL
 def inspected(*args,**kwargs):
  types_seen.append([type(v).__module__+'.'+type(v).__qualname__ for v in args]);return saved_original(*args,**kwargs)
 reuse.ORIGINAL=inspected;before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS;comparisons=0
 for repeat in range(24):
  if repeat==1:reuse.ORIGINAL=saved_original
  for r in records:
   command_bytes=[]
   for label in (('ORIGINAL','H1') if repeat%2==0 else ('H1','ORIGINAL')):
    reuse.ENABLED=label=='H1';runtime,kw,public=pickle.loads(r['inputs']);plant=plants[id(r)];runtime['plant']=plant;plant.data.time=public['time_s'];plant.last_joint_torque=public['last_joint_torque'].copy();runtime.setdefault('startup_alignment_geometry_checks',[])
    start=time.monotonic_ns();obs,interface=runtime['observer'].update(kw['measurement'],runtime['model'],human_model_version=str(kw['observation'].human_model_version));command,_=function(runtime,**(kw|dict(observation=obs,interface=interface)));elapsed=(time.monotonic_ns()-start)/1e6
    expected=pickle.loads(r['expected_command'])
    for name,value in vars(expected).items():
     if isinstance(value,np.ndarray):assert np.array_equal(value,getattr(command,name)),(label,name)
    command_bytes.append(pickle.dumps(command,protocol=5));comparisons+=1
    if repeat>0:times[label].append(elapsed)
   # Pickle object alias/memo identity is not an arithmetic comparison; arrays
   # above match every saved original command on both branches.
 def q(values):return dict(zip(('p50','p95','p99','max'),np.percentile(values,[50,95,99,100]).tolist()))
 out=dict(status='PASS',inputs=len(records),paired_repeats=24,array_command_comparisons=comparisons,timing_ms={k:q(v) for k,v in times.items()},reuse_counts=dict(reuse.ROWS),cache_entries=len(reuse.CACHE),argument_types=sorted(set(tuple(v) for v in types_seen)),actual_model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,live_coupled_plant=False,scope='Same-process alternating controller-only causal-input replay; excludes actuator/receipt/async scheduling/physical integration. No host qualification.',unix=time.time())
 label=sys.argv[1] if len(sys.argv)>1 else 'INITIAL'
 assert label in ('INITIAL','FULL_KEY')
 (S/'output'/('H1_EQUILIBRIUM_PAIRED_CONTROLLER_'+label+'.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
