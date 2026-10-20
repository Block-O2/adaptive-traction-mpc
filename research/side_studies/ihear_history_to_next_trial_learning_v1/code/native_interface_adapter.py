from pathlib import Path
import sys,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_history_to_next_trial_learning_v1');sys.path.insert(0,str(S/'build'))
from scipy.spatial.transform import Rotation
import fast_native as native
def rotvec(matrix):return Rotation.from_matrix(matrix).as_rotvec()
def rotvec_fast(matrix):return native.rotvec_exact(matrix,rotvec)
def install(so3=False):
 global ACTIVE_ROTVEC
 ACTIVE_ROTVEC=rotvec_fast if so3 else rotvec
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import fast_plant as fp
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_interface import parameter_key
 from traction_mpc_stage3.spring_damper_interface import InterfaceState
 C=fp.CachedStage5CR12SensorBoundaryPlant
 def value(self):
  p=self.interface_parameters;key=parameter_key(p)
  if getattr(self,'_native_parameter_key',None)!=key:
   self._native_interface=native.create(np.asarray(p.translation_stiffness_n_m),np.asarray(p.translation_damping_ns_m),np.asarray(p.rest_translation_human_m),Rotation.from_rotvec(p.rest_rotation_rotvec_human_rad).as_matrix(),p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad);self._native_parameter_key=key;self._native_tuple=None
  row=native.evaluate_data(self._native_interface,self.model._address,self.data._address,self.attachment_site_id,self.sleeve_site_id,rotvec_fast if so3 else rotvec)
  if row is not self._native_tuple:
   self._interface_value=InterfaceState(*row);self._native_tuple=row;self.interface_cache_misses+=1
  else:self.interface_cache_hits+=1
  return self._interface_value
 def apply(self):
  state=self._evaluate_current_interface_value()
  native.apply_wrenches(self.model._address,self.data._address,self.attachment_site_id,self.sleeve_site_id,state.human_wrench_world,state.robot_wrench_world,self.interface_generalized_force)
 C._evaluate_current_interface_value=value;C._apply_interface=apply
