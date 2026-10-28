"""Evaluation-only copy of the post-step wrench already computed by original plant."""
INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
 original=WallPhysicsSession._step
 def step(self):
  count=len(self.native_states)
  try:return original(self)
  finally:
   if len(self.native_states)>count:
    value=getattr(self.plant,'_interface_value',None);wrench=getattr(value,'human_wrench_world',None)
    if wrench is None or getattr(wrench,'shape',None)!=(6,):raise RuntimeError('NATIVE_WRENCH_ORIGINAL_CACHE_UNAVAILABLE')
    self.native_states[-1]['cuff_wrench_world_evaluation_only']=wrench.copy()
    self.native_states[-1]['wrench_sample_role']='original post-refresh interface cache; no extra observe/refresh/step'
 WallPhysicsSession._step=step;INSTALLED=True
 return original
