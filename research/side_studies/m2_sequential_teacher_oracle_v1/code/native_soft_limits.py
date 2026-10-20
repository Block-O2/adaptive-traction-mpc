import numpy as np
def parameter_key(h):
 return (*h.q_min_rad,*h.q_max_rad,h.soft_limit_margin_rad,h.soft_limit_numerical_tolerance_rad,h.soft_limit_boundary_torque_nm,h.soft_limit_damping_nms_rad)
def install():
 import native_interface_adapter as a
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_plant import CachedStage5CR12SensorBoundaryPlant as C
 def apply(self):
  key=parameter_key(self.human)
  indices=(*map(int,self.human_qpos_indices),*map(int,self.human_dof_indices))
  if getattr(self,'_native_soft_key',None)!=(key,indices):
   self._native_soft_key=(key,indices);self._native_soft_params=np.asarray(key,dtype=np.float64);self._native_soft_indices=indices
  a.native.apply_soft_limits(self.model._address,self.data._address,*indices,self._native_soft_params)
 C._apply_soft_limit=apply
