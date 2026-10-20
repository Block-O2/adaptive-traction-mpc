"""C1d: one old-control catch-up after actual availability, not two.

Only the pure receipt-backed ZOH reference-history check uses the same
prospective ready grid that original prepare_apply would have integrated to.
No observer/current-state/phase admission reads are projected. Every pending
native interval still integrates the old command through actual availability.
"""
INSTALLED=False
def clear(history):
 if history is not None and hasattr(history,'_fast_prepared_reference_grid'):
  delattr(history,'_fast_prepared_reference_grid')
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp
 from traction_mpc_stage5.full3d_adaptive_integration_v1.applied_reference_history import AppliedReferenceMotionHistory as H
 old_prepare=wp.WallPhysicsSession.prepare_apply;old_apply=wp.WallPhysicsSession.apply;old_validate=H.validate_at_apply
 def prepare(self,command,*,source_sample_time_s):
  history=getattr(self.runtime.get('contract'),'reference_motion_history',None)
  if type(self) is not wp.WallPhysicsSession or not isinstance(history,H) or not self.runtime.get('autonomous_recovery_options',{}).get('fixed_command_ready',False):return old_prepare(self,command,source_sample_time_s=source_sample_time_s)
  ready=self.clock();target=max(self.steps,(ready-self.epoch_ns+self.dt_ns-1)//self.dt_ns)
  projected=float(self.plant.data.time)
  for _ in range(target-self.steps):projected+=self.dt
  receipt=dict(command_ready_ns=ready,attempt_ns=ready,receipt_index=len(self.applied_commands),source_sample_time_s=float(source_sample_time_s),source_capture_ns=self.source_ns(source_sample_time_s),native_steps=0,applied=False,command_torque_nm=command.joint_torque_command_nm.copy(),effective_activation_ns=self.epoch_ns+target*self.dt_ns,start_physics_s=float(self.plant.data.time),end_physics_s=float(self.plant.data.time),prepare_version='C1d_DEFER_OLD_INTERVALS_UNTIL_AFTER_AVAILABLE',prospective_ready_step=int(target),prospective_ready_reference_time_s=projected,actual_steps_at_prepare=self.steps)
  self.applied_commands.append(receipt)
  if self.limit_violations:
   receipt['exception']='RuntimeError:'+self.limit_violations[0]['reason'];raise RuntimeError(self.limit_violations[0]['reason'])
  history._fast_prepared_reference_grid=(receipt['receipt_index'],projected)
  return receipt
 def validate(self,q,dq,limits):
  marker=getattr(self,'_fast_prepared_reference_grid',None)
  if marker is None:return old_validate(self,q,dq,limits)
  # The original prepare checked this known receipt ZOH at this same grid.
  # Only reference-history time is substituted for the duration of the call.
  old_clock=self.clock
  try:
   self.clock=lambda:marker[1]
   return old_validate(self,q,dq,limits)
  finally:
   self.clock=old_clock;clear(self)
 def apply(self,*args,**kwargs):
  history=getattr(self.runtime.get('contract'),'reference_motion_history',None)
  clear(history)
  try:return old_apply(self,*args,**kwargs)
  finally:clear(history)
 wp.WallPhysicsSession.prepare_apply=prepare;wp.WallPhysicsSession.apply=apply;H.validate_at_apply=validate;INSTALLED=True
 return old_prepare,prepare,old_validate,validate
