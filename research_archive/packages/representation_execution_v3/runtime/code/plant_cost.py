from pathlib import Path
import os,sys,time,json,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/ihear-lab/representation_execution_v3/runtime');sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
def main():
 cfg=json.loads(Path(sys.argv[1]).read_text());ident=cfg['id'];start=time.time()
 import lean_instrumentation;lean_instrumentation.prime()
 import study_common as sc,numpy as np,fast_attribution as a
 from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import fast_plant as fp
 if cfg.get('native_backend'):
  import native_interface_adapter;native_interface_adapter.install(so3=cfg.get('native_so3',False))
 if cfg.get('native_soft_limits'):
  import native_soft_limits;native_soft_limits.install()
 case,options=sc.load_case_options();human,geometry,spec,_=hidden_plant(case);runtime=None;steps=0
 from traction_mpc_stage4 import estimator_v2 as ma
 before_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 try:
  runtime=sc.rt._initialize_loaded_runtime('plant_cost_only',np.asarray(spec.start_return_target_rad),spec=spec,physical_human=human,physical_geometry=geometry,control_human=sc.rt.high_rom_deployable_prior(),startup_execution_pose_alignment=True,exact_cached_plant=True)
  plant=runtime['plant'];latency=[]
  for name,category in [('_refresh','refresh_native'),('_apply_interface','interface_apply'),('_evaluate_current_interface_value','interface_value'),('_attachment_state','attachment_extract'),('_apply_soft_limit','soft_limit')]:a.wrap(fp.CachedStage5CR12SensorBoundaryPlant,name,category)
  for name in ('mj_step1','mj_step2','mj_fwdPosition','mj_fwdVelocity','mj_forward','mj_applyFT','mj_objectVelocity'):a.wrap(fp.mujoco,name,'mujoco_'+name)
  before=dict(a.TOTAL);begin=time.monotonic_ns()
  for _ in range(cfg.get('native_steps',2000)):
   t=time.monotonic_ns();plant.step_native();latency.append(time.monotonic_ns()-t);steps+=1
   if not np.all(np.isfinite(plant.data.qpos)) or not np.all(np.isfinite(plant.data.qvel)):raise RuntimeError('NONFINITE_NATIVE_PLANT')
  elapsed=time.monotonic_ns()-begin;exclusive={k:v-before.get(k,0) for k,v in a.TOTAL.items()};exclusive['unwrapped_step_and_measurement']=elapsed-sum(exclusive.values())
  result=dict(id=ident,status='COMPLETE',inputs=cfg,wall_seconds=time.time()-start,metric=dict(native_physics_steps=steps,simulation_seconds=float(plant.data.time),main_model_inverse_dynamics_api_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before_calls,native_worker_model_inverse_dynamics_api_calls=0),native_step_ms=dict(zip(('p50','p95','p99','max'),np.percentile(np.asarray(latency)/1e6,[50,95,99,100]).tolist())),exclusive_mean_per_step_ms={k:v/steps/1e6 for k,v in exclusive.items()},calls=a.CALLS,same_model_case_key=case['case_key'],qualification='PLANT_COST_ATTRIBUTION_ONLY_CONSTANT_VALIDATED_INITIAL_SUPPORT; no closed-loop/task claim')
 except BaseException as e:result=dict(id=ident,status='FAILED',error=repr(e),traceback=traceback.format_exc(),inputs=cfg,metric=dict(native_physics_steps=steps,simulation_seconds=None if runtime is None else float(runtime['plant'].data.time)))
 sc.save(ident+'_RESULT.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
