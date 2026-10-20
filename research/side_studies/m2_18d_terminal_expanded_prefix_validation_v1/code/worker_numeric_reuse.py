"""W2: exact pure feature/Jacobian reuse in a single immutable TASK request.

Original inverse-dynamics and allocator methods still run and count normally.
Every hit returns a fresh array; no rounding, sample omission or proof omission.
"""
import numpy as np
INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 import fast_task_owner as owner
 import loaded_context_reuse as values
 from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as f
 from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
 features=f._state_residual_features;jacobian=PlanarCuffGeometry.translational_jacobian_world
 def memo(kind,key,function):
  scope=owner.SCOPE.get()
  if scope is None:return function()
  cache=scope.setdefault('numerical_cache',{});counts=scope.setdefault('numerical_counts',{})
  k=(kind,key)
  if k in cache:
   counts[kind+'_hit']=counts.get(kind+'_hit',0)+1;return cache[k].copy()
  result=function();cache[k]=result.copy();counts[kind+'_miss']=counts.get(kind+'_miss',0)+1;return result
 def state_features(state,rom_human=f.HUMAN):
  x=np.asarray(state,dtype=float)
  # Complete source dependencies of this pure function. Original validation
  # still executes on first exact key and invalid inputs never enter the cache.
  key=(x.shape,x.dtype.str,x.tobytes(),values.raw(rom_human.q_min_rad),
   values.raw(rom_human.q_max_rad),values.raw(f.STATE_RESIDUAL_VELOCITY_SCALE_RAD_S))
  return memo('features',key,lambda:features(state,rom_human))
 def geometry_jacobian(self,q_rad):
  q=np.asarray(q_rad,dtype=float);key=(values.raw(self),q.shape,q.dtype.str,q.tobytes())
  return memo('geometry_jacobian',key,lambda:jacobian(self,q_rad))
 values.aliases(features,state_features);PlanarCuffGeometry.translational_jacobian_world=geometry_jacobian
 INSTALLED=True
