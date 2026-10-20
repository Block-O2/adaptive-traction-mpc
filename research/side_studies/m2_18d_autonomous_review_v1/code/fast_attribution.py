"""Exclusive nested timing on the same actual control cycles; attribution only."""
import time,pickle,functools
STACK=[];TOTAL={};CALLS={};CYCLES=[];INPUTS=[];CURRENT=None
def wrap(obj,name,category):
 old=getattr(obj,name)
 @functools.wraps(old)
 def call(*a,**k):
  start=time.monotonic_ns();frame=[category,start,0];STACK.append(frame)
  try:return old(*a,**k)
  finally:
   end=time.monotonic_ns();STACK.pop();duration=end-start
   TOTAL[category]=TOTAL.get(category,0)+duration-frame[2]
   key=old.__module__+'.'+old.__qualname__;CALLS[key]=CALLS.get(key,0)+1
   if STACK:STACK[-1][2]+=duration
 return setattr(obj,name,call)
def install(cfg):
 import study_common as sc
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp,fast_plant as fp
 from traction_mpc_stage5 import loaded_execution as le,controller_interface as ci,human_waypoint_shadow as hw
 rt=sc.rt
 capture=rt._capture_boundary
 def boundary(runtime):
  global CURRENT
  now=time.monotonic_ns()
  if CURRENT is not None:
   row=CURRENT;row.update(end_ns=now,duration_ns=now-row['start_ns'],exclusive_ns={k:TOTAL.get(k,0)-row['initial'].get(k,0) for k in set(TOTAL)|set(row['initial'])});row['exclusive_ns']['unwrapped_control_and_scheduling']=row['duration_ns']-sum(row['exclusive_ns'].values());del row['initial'];CYCLES.append(row)
  CURRENT=dict(start_ns=now,initial=dict(TOTAL),phase=runtime.get('wall_session').phase_records[-1]['phase'] if runtime.get('wall_session') else 'SCI',model_version=runtime.get('model_sequence'))
  return capture(runtime)
 rt._capture_boundary=boundary
 for name in ('step_native',):wrap(fp.CachedStage5CR12SensorBoundaryPlant,name,'plant_native_wrapper')
 for name in ('capture',):wrap(wp.WallPhysicsSession,name,'sensor_capture_observer')
 for name in ('prepare_apply','apply'):wrap(wp.WallPhysicsSession,name,'command_receipt')
 wrap(rt,'validate_activation','current_admission')
 wrap(rt,'snapshot_task_call','immutable_request_snapshot')
 # The wall callback sleep is exclusive; native integration remains separately nested.
 original_init=wp.WallPhysicsSession.__init__
 def init(self,*a,**k):
  original_init(self,*a,**k);old=self.sleeper
  def sleep(t):
   start=time.monotonic_ns()
   try:return old(t)
   finally:
    duration=time.monotonic_ns()-start;TOTAL['wait']=TOTAL.get('wait',0)+duration
    if STACK:STACK[-1][2]+=duration
  self.sleeper=sleep
 wp.WallPhysicsSession.__init__=init
 wrap(hw.HumanWaypointMPCShadowContractV1,'command','feedback_transform_filter')
 if cfg.get('front_attribution'):
  from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,StateResidualBeliefUpdaterV22
  for obj,name,category in ((AdaptiveHumanBeliefV22,'human_model','belief_model_build'),(StateResidualBeliefUpdaterV22,'snapshot','belief_snapshot'),(rt.InterfaceAwareHumanStateObserver,'update','observer_update'),(rt.SplitAccelerationMonitorV1,'update','motion_monitor'),(rt.HumanMotionAccelerationAuthorityV1,'evaluate','motion_authority'),(rt.SensorSupportedTaskClock,'transition','task_phase_transition'),(rt,'measured_transmitted_human_input','measured_input'),(rt,'asdict','boundary_dataclass_copy')):wrap(obj,name,category)
 # Save prepared causal numerical contexts, with no live plant or future truth.
 old=le.Stage5LoadedExecutionContext.preview_command_batch
 def preview(self,actions):
  out=old(self,actions)
  if len(INPUTS)<48:
   INPUTS.append((self,actions.copy(),out))
  return out
 le.Stage5LoadedExecutionContext.preview_command_batch=preview
def finish(ident):
 import study_common as sc
 sc.save(ident+'_EXCLUSIVE_CYCLES.json',dict(schema='same_cycle_exclusive_v1',cycles=CYCLES,calls=CALLS,exclusive_totals_ns=TOTAL,attribution_only=True,qualifying_host=False,partitions='Nested wall durations deducted from parent; unwrapped remainder closes each complete actual cycle. Not sums of independent quantiles.'))
 try:
  payload=pickle.dumps(INPUTS,protocol=5);(sc.STUDY/'inputs'/(ident+'_controller_inputs.pkl')).write_bytes(payload)
  sc.save(ident+'_CONTROLLER_INPUT_CAPTURE.json',dict(status='SAVED',contexts=len(INPUTS),bytes=len(payload),scope='loaded executable command preview on causal context; not entire feedback controller and not physical qualification'))
 except Exception as e:sc.save(ident+'_CONTROLLER_INPUT_CAPTURE.json',dict(status='FAILED',error=repr(e)))
