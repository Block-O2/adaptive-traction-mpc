"""Exact float64 three-vector cross only in measured FAST consumers."""
import sys,numpy as np
from native_interface_adapter import native
ORIGINAL=np.cross
def cross(a,b,*args,**kwargs):
 if not args and not kwargs and isinstance(a,np.ndarray) and isinstance(b,np.ndarray) and a.shape==(3,) and b.shape==(3,) and a.dtype==np.float64 and b.dtype==np.float64:
  return native.cross3(a,b)
 return ORIGINAL(a,b,*args,**kwargs)
class NumpyProxy:
 def __getattr__(self,name):return cross if name=='cross' else getattr(np,name)
def install():
 prefixes=('traction_mpc_stage5.controller_interface','traction_mpc_stage5.loaded_execution','traction_mpc_stage5.cr12_robot','traction_mpc_stage5.human_geometry','traction_mpc_stage4.cuff_allocator','traction_mpc_stage5.full3d_adaptive_integration_v1.runtime_coordination_residual_v2','traction_mpc_stage5.full3d_adaptive_integration_v1.command_response_history')
 proxy=NumpyProxy();patched=[]
 for name,module in list(sys.modules.items()):
  if name in prefixes and getattr(module,'np',None) is np:module.np=proxy;patched.append(name)
 return patched
