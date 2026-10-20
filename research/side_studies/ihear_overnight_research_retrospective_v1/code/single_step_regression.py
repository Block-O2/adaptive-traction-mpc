from pathlib import Path
import os,sys,time,json,traceback,numpy as np
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1');sys.path.insert(0,str(S/'code'))
def main():
 cfg=json.loads(Path(sys.argv[1]).read_text());ident=cfg['id'];start=time.time();steps=0;calls_before=0
 import lean_instrumentation;lean_instrumentation.prime()
 import study_common as sc,native_interface_adapter as a,native_soft_limits,native_single_step as n
 from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
 from traction_mpc_stage4 import estimator_v2 as ma
 calls_before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 a.install(so3=True);native_soft_limits.install();case,options=sc.load_case_options();human,geometry,spec,_=hidden_plant(case)
 try:
  plants=[]
  for i in range(2):
   runtime=sc.rt._initialize_loaded_runtime('single_step_local',np.asarray(spec.start_return_target_rad),spec=spec,physical_human=human,physical_geometry=geometry,control_human=sc.rt.high_rom_deployable_prior(),startup_execution_pose_alignment=True,exact_cached_plant=True)
   plants.append(runtime['plant'])
  original,native=n.install();latencies=[[],[]];fields=('qpos','qvel','qacc','qfrc_applied','qfrc_bias','qfrc_constraint','site_xpos','site_xmat','cvel','act','ctrl','eq_active')
  comparisons=0
  for index in range(cfg.get('comparison_steps',3000)):
   for k,fn in enumerate((original,native)):
    t=time.monotonic_ns();fn(plants[k]);latencies[k].append(time.monotonic_ns()-t);steps+=1
   x,y=plants
   assert x.data.time==y.data.time
   for field in fields:
    assert np.array_equal(getattr(x.data,field),getattr(y.data,field)),(index,field);comparisons+=1
   assert np.array_equal(x.interface_generalized_force,y.interface_generalized_force)
   assert x.interface_cache_hits==y.interface_cache_hits and x.interface_cache_misses==y.interface_cache_misses
   assert sc.clean(x._interface_value)==sc.clean(y._interface_value)
   assert sc.clean(x.interface_history[-1])==sc.clean(y.interface_history[-1])
  # Cache validity and defensive history ownership without any extra physics.
  for plant in plants:
   prior=plant._interface_value.displacement_human_m.copy();plant.interface_history[-1]['translation_m'][:]=999
   assert np.array_equal(prior,plant._interface_value.displacement_human_m)
  result=dict(id=ident,status='COMPLETE',gate='PASS',bit_exact=True,inputs=cfg,wall_seconds=time.time()-start,metric=dict(native_physics_steps=steps,simulation_seconds=steps*.00025,main_model_inverse_dynamics_api_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-calls_before,native_worker_model_inverse_dynamics_api_calls=0),pairs=cfg.get('comparison_steps',3000),array_comparisons=comparisons,original_step_us=dict(zip(('p50','p95','p99','max'),np.percentile(np.asarray(latencies[0])/1000,[50,95,99,100]).tolist())),native_step_us=dict(zip(('p50','p95','p99','max'),np.percentile(np.asarray(latencies[1])/1000,[50,95,99,100]).tolist())),scope='Two identical hidden plants on original validated constant initial support; cost/equivalence only, no closed-loop qualification. Both force updates and exact MuJoCo call order retained.')
 except BaseException as e:result=dict(id=ident,status='FAILED',gate='FAIL',inputs=cfg,error=repr(e),traceback=traceback.format_exc(),wall_seconds=time.time()-start,metric=dict(native_physics_steps=steps,simulation_seconds=steps*.00025,main_model_inverse_dynamics_api_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-calls_before,native_worker_model_inverse_dynamics_api_calls=0))
 sc.save(ident+'_RESULT.json',result);print(json.dumps(result),flush=True)
 sc.save('N11_SINGLE_STEP_LOCAL_GATE.json',dict(status=result['gate'],result_id=ident,bit_exact=result.get('bit_exact',False),source_sha256=sc.sha(S/'native/fast_native.cpp')))
if __name__=='__main__':main()
