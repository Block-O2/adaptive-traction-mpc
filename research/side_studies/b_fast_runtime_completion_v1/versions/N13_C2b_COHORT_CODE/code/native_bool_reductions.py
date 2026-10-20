"""N13: scoped NumPy all/any reduction for exact small Boolean ndarrays."""
import types,numpy as np
INSTALLED=False
MODULES=('traction_mpc_stage3.executable_command','traction_mpc_stage3.frames','traction_mpc_stage3.human','traction_mpc_stage4.safety_filter','traction_mpc_stage4.cuff_allocator','traction_mpc_stage4.estimator_v2','traction_mpc_stage4.sensor_realism','traction_mpc_stage5.loaded_execution','traction_mpc_stage5.human_waypoint_shadow','traction_mpc_stage5.human_waypoint_feedback_mpc','traction_mpc_stage5.controller_interface','traction_mpc_stage5.hold_stabilizer','traction_mpc_stage5.split_acceleration_monitor','traction_mpc_stage5.full3d_adaptive_integration_v1.clearance_feedback','traction_mpc_stage5.full3d_adaptive_integration_v1.runtime_coordination_residual_v2','traction_mpc_stage5.full3d_adaptive_integration_v1.startup_alignment','traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference','traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation')
def install():
 global INSTALLED
 if INSTALLED:return
 import importlib,native_interface_adapter as a
 def reducer(original,any_value):
  def reduce(value,*args,**kwargs):
   if not args and not kwargs and type(value) is np.ndarray and value.dtype==np.dtype('bool') and value.ndim<=2 and value.size<=2048:return a.native.small_bool_reduce(value,any_value)
   return original(value,*args,**kwargs)
  return reduce
 for name in MODULES:
  module=importlib.import_module(name);old=module.np;proxy=types.ModuleType(old.__name__);proxy.__dict__.update(vars(old));proxy.all=reducer(old.all,False);proxy.any=reducer(old.any,True);module.np=proxy
 INSTALLED=True
