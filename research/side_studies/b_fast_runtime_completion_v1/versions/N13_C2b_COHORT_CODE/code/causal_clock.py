"""C1: command availability first, ceil native grid, old command on unsimulated past.

Only actuator fields are staged/restored. No integrated qpos/qvel trajectory is
rewound. The command's real availability timestamp and original source survive.
"""
import hashlib
FIELDS=('last_joint_torque','last_unclipped_joint_torque','last_force','last_moment')
def snapshot(plant):
 return (plant.data.ctrl.copy() if hasattr(plant.data,'ctrl') else None,{n:getattr(plant,n).copy() for n in FIELDS if hasattr(plant,n)})
def restore(plant,state):
 ctrl,fields=state
 if ctrl is not None:plant.data.ctrl[:]=ctrl
 for n,v in fields.items():getattr(plant,n)[:]=v
def apply(self,command,write,*,source_sample_time_s,commit=None,catchup=True,prepared=None):
 if catchup:self.catch_up('before_actual_command_apply')
 receipt=prepared if prepared is not None else self.prepare_apply(command,source_sample_time_s=source_sample_time_s)
 if max(self.clock(),receipt['effective_activation_ns'])-receipt['source_capture_ns']>100_000_000:
  receipt['cancelled_before_write_reason']='STALE_COMMAND_SOURCE_MAXIMUM_AGE';raise RuntimeError('STALE_COMMAND_SOURCE_MAXIMUM_AGE')
 old=snapshot(self.plant)
 try:
  try:write()
  except BaseException:
   restore(self.plant,old);receipt['failed_write_rolled_back_before_physics']=True;raise
  available=self.clock();new=snapshot(self.plant)
  target=max(self.steps,(available-self.epoch_ns+self.dt_ns-1)//self.dt_ns)
  effective=self.epoch_ns+target*self.dt_ns
  receipt.update(apply_ns=available,actual_command_available_ns=available,effective_activation_ns=effective,
   conservative_activation_ns=effective,availability_target_step=int(target),quantization_delay_ns=effective-available,
   clock_version='C1b_CAUSAL_CEIL_GRID_WRITE_ONCE',command_id=receipt['receipt_index'],model_version=self.runtime.get('model_sequence'))
  assert 0<=effective-available<=self.dt_ns,'CAUSAL_GRID_QUANTIZATION'
  restore(self.plant,old)
  request=self.runtime.get('plan_to_activate');life=self.runtime.get('plan_lifecycle')
  if request is not None and life is not None:
   life.mark(request,'effective_activation_ns',effective)
   if effective-request.sensor_capture_ns>=life.maximum_age_ns:
    receipt.update(cancelled_before_write_reason='STALE_PLAN_MAXIMUM_AGE',applied=False)
    life.finish(request,'EXPIRED','STALE_PLAN_MAXIMUM_AGE')
    raise RuntimeError('STALE_PLAN_MAXIMUM_AGE')
  if effective-receipt['source_capture_ns']>100_000_000:
   receipt.update(cancelled_before_write_reason='COMMAND_AVAILABILITY_CROSSED_SOURCE_EXPIRATION',applied=False)
   raise RuntimeError('COMMAND_AVAILABILITY_CROSSED_SOURCE_EXPIRATION')
  # Integrate every old interval with its already-existing command. Sensors,
  # interface updates, safety samples and receipt accounting remain native.
  while self.steps<target:self._step()
  if self.limit_violations:raise RuntimeError(self.limit_violations[0]['reason'])
  receipt.update(start_physics_s=float(self.plant.data.time),end_physics_s=float(self.plant.data.time),applied=True,
   sensor_age_at_apply_ms=(effective-receipt['source_capture_ns'])/1e6,
   host_write_minus_effective_grid_ns=available-effective,owner_commit_host_ns=self.clock())
  arrays=(receipt.get('validation_reference_q_rad'),receipt.get('validation_reference_dq_rad_s'))
  receipt['reference_version']=hashlib.sha256(b''.join(x.tobytes() for x in arrays if x is not None)).hexdigest()
  restore(self.plant,new);self.active_receipt_index=receipt['receipt_index']
  if commit is not None:commit(receipt)
 except BaseException as error:
  if not receipt.get('applied',False):restore(self.plant,old)
  receipt['exception']=f'{type(error).__name__}:{error}';error.applied_receipt=receipt;raise
 finally:receipt['return_ns']=self.clock()
 return receipt
def install(integer_grid=False):
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp,online_planning as op
 original_activate=op.PlanLifecycle.activate
 def activate(self,request,write,*,effective_activation_ns=None,applied_receipt=None):
  # Ready-grid is a prospective catch-up target, not the actual write grid.
  # Preserve the original prewrite expiry test; record actual effective grid
  # exactly once inside the actual availability adapter, never amend an event.
  if effective_activation_ns is not None and max(self.clock(),effective_activation_ns)-request.sensor_capture_ns>=self.maximum_age_ns:
   return original_activate(self,request,write,effective_activation_ns=effective_activation_ns,applied_receipt=applied_receipt)
  return original_activate(self,request,write,effective_activation_ns=None,applied_receipt=applied_receipt)
 op.PlanLifecycle.activate=activate
 wp.WallPhysicsSession.apply=apply
 old=wp.WallPhysicsSession._step
 def step(self):
  before=self.steps;command_id=self.active_receipt_index
  try:return old(self)
  finally:
   if self.steps>before:
    if integer_grid:self.plant.data.time=self.origin_physics_s+self.steps*self.dt
    if self.native_states:
     row=self.native_states[-1];row.update(command_id=command_id,native_step_index=before,
      physical_interval_start_s=self.origin_physics_s+before*self.dt,
      physical_interval_end_s=self.origin_physics_s+self.steps*self.dt,
      native_grid_start_ns=self.epoch_ns+before*self.dt_ns,
      native_grid_end_ns=self.epoch_ns+self.steps*self.dt_ns)
 wp.WallPhysicsSession._step=step
