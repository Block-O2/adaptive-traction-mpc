"""Saved causal controller-only replay; never imports a coupled/live plant.

Extract the unchanged numerical prefix of _execute_interval through original
feedback, transform, Safety Filter, TRACK/BRAKE selection and final checks.
Actuator writes, admission transaction and integration are excluded and reported.
"""
from pathlib import Path
import sys,pickle,ast,types,time,json,copy,cProfile,pstats,io,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');sys.path.insert(0,str(S/'code'))
CAPTURES=[];PHASES={}
class FrozenClock:
 def __init__(self,value):self.value=float(value)
 def __call__(self):return self.value
def freeze_runtime(runtime,now):
 selected={k:runtime[k] for k in KEYS if k in runtime}
 # Replace only the live-plant clock closure in a snapshot, never in runtime.
 contract=copy.copy(selected['contract']);history=copy.copy(contract.reference_motion_history)
 history.clock=FrozenClock(now);contract.reference_motion_history=history;selected['contract']=contract
 return selected
KEYS=('contract','model','model_transfer','autonomous_recovery_options','monitor','last_command','last_executed_generalized_action_nm','last_action_executable_verified','allocator','last_command_robot_position_m','last_command_source_sample_s','last_command_receipt_physics_s','command_response_history','incremental_clearance_history_initialized','startup_alignment_active','alignment_remove_pending','startup_alignment','startup_alignment_record','last_aligned_robot_reference','emitted_robot_reference_history','supervisor','observer')
def install():
 import study_common as sc
 original=sc.rt._execute_interval
 def interval(runtime,**kw):
  phase=runtime['wall_session'].phase_records[-1]['phase'] if runtime.get('wall_session') else 'SCI'
  if phase=='TASK':phase+='_'+kw['candidate'].phase.value
  count=PHASES.get(phase,0);PHASES[phase]=count+1
  capture=count in ((20,100) if phase=='TASK_HOLD' else (20,200)) and runtime.get('plan_to_activate') is None and len(CAPTURES)<16
  row=None
  if capture:
   plant=runtime['plant'];public_plant=dict(neutral_robot_q=plant.neutral_robot_q.copy(),torque_limits_nm=plant.torque_limits_nm.copy(),attachment_from_cuff=plant.attachment_from_cuff,translational_velocity_feedback_source=plant.translational_velocity_feedback_source,time_s=float(plant.data.time),last_joint_torque=plant.last_joint_torque.copy(),measured_robot_model_path=str(plant._measured_robot_model.model_path),control_velocity_model_path=str(plant._control_velocity_robot_model.model_path))
   selected=freeze_runtime(runtime,public_plant['time_s'])
   row=dict(phase=phase,source_sample_time_s=kw['measurement'].sample_time_s,inputs=pickle.dumps((selected,kw,public_plant),protocol=5))
  out=original(runtime,**kw)
  if row is not None:row['expected_command']=pickle.dumps(out[0],protocol=5);CAPTURES.append(row)
  return out
 sc.rt._execute_interval=interval
def finish(ident):
 (S/'inputs'/(ident+'_FULL_CONTROLLER_CAUSAL.pkl')).write_bytes(pickle.dumps(CAPTURES,protocol=5))
class ControllerPlant:
 def __init__(self,public):
  from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
  from traction_mpc_stage4 import sensor_realism as sensor
  self.__dict__.update(public);self.data=types.SimpleNamespace(time=public['time_s'])
  self._measured_robot_model=CR12TorqueRobot(Path(public['measured_robot_model_path']))
  self._control_velocity_robot_model=CR12TorqueRobot(Path(public['control_velocity_model_path']))
  # Locate inherited original measurement methods; use no coupled plant state.
  methods={name:getattr(cls,name) for cls in vars(sensor).values() if isinstance(cls,type) for name in ('robot_joint_control_velocity_snapshot','control_feedback_velocity_snapshot') if hasattr(cls,name)}
  for name,method in methods.items():setattr(self,name,types.MethodType(method,self))
def kernel(rt,extended=False):
 source=Path(rt.__file__).read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_execute_interval');text=ast.get_source_segment(source,node)
 text=text.split('    def commit(receipt):' if extended else '    filter_unchanged = bool(',1)[0]+'    return command, command_result\n'
 namespace=dict(rt.__dict__);exec(compile(text,'<offline original controller numerical prefix>','exec'),namespace);return namespace['_execute_interval']
def main():
 import study_common as sc
 ident=sys.argv[1];p=S/'inputs'/(ident+'_FULL_CONTROLLER_CAUSAL.pkl');rows=pickle.loads(p.read_bytes());assert rows,'No full controller causal inputs saved'
 variant=sys.argv[2] if len(sys.argv)>2 else 'ORIGINAL'
 extended=variant.endswith('_TAIL');base_variant=variant[:-5] if extended else variant
 variant_label=variant;variant=base_variant
 if variant in ('FAST','FAST_V2','FAST_V3','FAST_N5','FAST_N6','FAST_N8','FAST_N13'):
  import fast_runtime
  cfg=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())['inputs'];cfg.update(attribution=False,capture_controller_full=False,reuse_shadow=False)
  if variant in ('FAST_V2','FAST_V3','FAST_N5','FAST_N6','FAST_N8','FAST_N13'):cfg.update(numerical_reuse=False,native_cross_expanded=True)
  if variant in ('FAST_V3','FAST_N5','FAST_N6','FAST_N8','FAST_N13'):cfg.update(loaded_context_reuse=True)
  if variant in ('FAST_N5','FAST_N6','FAST_N8','FAST_N13'):cfg.update(native_small_kernels=True)
  if variant in ('FAST_N6','FAST_N8','FAST_N13'):cfg.update(native_geometry=True)
  if variant in ('FAST_N8','FAST_N13'):cfg.update(native_value_tree=True)
  if variant=='FAST_N13':cfg.update(native_quintic=True,native_intervals=True,native_bool_reductions=True)
  fast_runtime.install(cfg)
 else:assert variant=='ORIGINAL'
 function=kernel(sc.rt,extended=extended);timing=[];comparisons=[];model_calls_before=None;profiler=cProfile.Profile()
 if variant in ('FAST_V3','FAST_N5','FAST_N6','FAST_N8','FAST_N13'):
  import loaded_context_reuse
  function=loaded_context_reuse.transaction(function)
 from traction_mpc_stage4 import estimator_v2 as ma
 model_calls_before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 plants={}
 for r in rows:
  runtime,kw,public=pickle.loads(r['inputs']);plants[id(r)]=ControllerPlant(public)
 for repeat in range(12):
  for r in rows:
   runtime,kw,public=pickle.loads(r['inputs']);runtime['plant']=plants[id(r)]
   runtime.setdefault('startup_alignment_geometry_checks',[])
   runtime['plant'].data.time=public['time_s'];runtime['plant'].last_joint_torque=public['last_joint_torque'].copy()
   # Saved observer state and original measured sample; no later observation.
   if repeat==11:profiler.enable()
   t=time.monotonic_ns();observation,interface=runtime['observer'].update(kw['measurement'],runtime['model'],human_model_version=str(kw['observation'].human_model_version));command,_=function(runtime,**(kw|dict(observation=observation,interface=interface)));elapsed=(time.monotonic_ns()-t)/1e6
   if repeat==11:profiler.disable()
   expected=pickle.loads(r['expected_command']);errors={name:float(np.max(np.abs(np.asarray(value)-np.asarray(getattr(command,name))))) for name,value in vars(expected).items() if isinstance(value,np.ndarray)}
   assert all(v==0 for v in errors.values()),errors
   if repeat!=11:timing.append(elapsed)
   if repeat==0:comparisons.append(dict(phase=r['phase'],source_sample_time_s=r['source_sample_time_s'],command_bit_exact=True,max_errors=errors))
 profile_text=io.StringIO();pstats.Stats(profiler,stream=profile_text).sort_stats('tottime').print_stats(55)
 (S/'output'/(ident+'_FULL_CONTROLLER_'+variant_label+'_PROFILE.txt')).write_text(profile_text.getvalue())
 out=dict(status='PASS',variant=variant,no_physics=True,live_coupled_plant_created=False,input_sha256=sc.sha(p),causal_inputs=len(rows),unprofiled_calls=len(timing),profiled_calls=len(rows),controller_ms=dict(zip(('p50','p95','p99','max'),np.percentile(timing,[50,95,99,100]).tolist())),model_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_calls_before,comparisons=comparisons,scope='Original observer + full feedback/transform/current Safety Filter/TRACK-BRAKE numerical selection. Excludes actuator transaction, asynchronous admission/IPC, physics and research logging. Does not qualify host or replace exclusive whole-cycle budget.')
 if variant in ('FAST_V3','FAST_N5','FAST_N6','FAST_N8','FAST_N13'):out['reuse_counters']=loaded_context_reuse.ROWS
 out['variant']=variant_label
 if extended:out['scope']='Original observer + full feedback/transform/current Safety Filter/TRACK-BRAKE selection and original actual loaded target geometry certificate. Excludes asynchronous admission/IPC, actuator/receipt transaction, physics and research logging. Saved input replay only, not host qualification.'
 sc.save(ident+'_FULL_CONTROLLER_'+variant_label+'_REPLAY.json',out);print(json.dumps({k:v for k,v in out.items() if k!='comparisons'}))
if __name__=='__main__':main()
