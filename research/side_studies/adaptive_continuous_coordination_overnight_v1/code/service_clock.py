"""C2: actual next service opportunity follows the last control poll.

After an overrun, run one current service immediately. Never synthesize past
feedback calls or wait for an additional future grid merely because physics
catch-up has already crossed the next service deadline.
"""
def next_control_tick(self):
 target=self.epoch_ns+(self._last_poll_grid+1)*self.sensor_steps*self.dt_ns
 now=self.clock();delay=target-now
 if delay>0:self.sleeper(delay/1e9)
 self.catch_up('next_control_tick_C2_actual_opportunity')
def install(telemetry=False):
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp
 if not telemetry:
  wp.WallPhysicsSession.next_control_tick=next_control_tick
  return
 import multirate
 def measured(self):
  row=multirate.ROWS['fast'][-1] if multirate.ROWS['fast'] else None
  if row is not None and row.get('service_finish_ns') is None:
   row.update(service_finish_ns=self.clock(),physics_before_wait_s=float(self.plant.data.time),command_currently_applied=self.plant.last_joint_torque.copy(),receipt_index=self.active_receipt_index,service_finish_semantics='C2b owner work before next-tick wait/catch-up; earlier receipt integration is separately included in owner work')
  start=self.steps
  try:return next_control_tick(self)
  finally:
   if row is not None:row.update(physical_steps_in_tick=self.steps-start,physical_finish_s=float(self.plant.data.time),physical_finish_host_ns=self.clock())
 wp.WallPhysicsSession.next_control_tick=measured
 return measured
