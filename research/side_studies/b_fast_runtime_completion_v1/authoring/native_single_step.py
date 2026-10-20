"""N11: consolidate one original native step; no events or rates are batched."""
import numpy as np
INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 import native_interface_adapter as a
 from native_soft_limits import parameter_key as soft_key
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_interface import parameter_key
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_plant import CachedStage5CR12SensorBoundaryPlant as C
 from traction_mpc_stage3.spring_damper_interface import InterfaceState
 original=C.step_native
 def step(self):
  if type(self) is not C:return original(self)
  # Complete parameter and index validation on EVERY step, as in N3/N4.
  p=self.interface_parameters;key=parameter_key(p)
  if getattr(self,'_native_parameter_key',None)!=key:
   self._native_interface=a.native.create(np.asarray(p.translation_stiffness_n_m),np.asarray(p.translation_damping_ns_m),np.asarray(p.rest_translation_human_m),a.Rotation.from_rotvec(p.rest_rotation_rotvec_human_rad).as_matrix(),p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad);self._native_parameter_key=key;self._native_tuple=None
  key=soft_key(self.human);indices=(*map(int,self.human_qpos_indices),*map(int,self.human_dof_indices))
  if getattr(self,'_native_soft_key',None)!=(key,indices):
   self._native_soft_key=(key,indices);self._native_soft_params=np.asarray(key,dtype=np.float64);self._native_soft_indices=indices
  rows=a.native.plant_single_step(self._native_interface,self.model._address,self.data._address,self.attachment_site_id,self.sleeve_site_id,self.weld_id,*indices,self._native_soft_params,a.ACTIVE_ROTVEC,self.interface_generalized_force)
  for row in rows:
   if row is not self._native_tuple:
    self._interface_value=InterfaceState(*row);self._native_tuple=row;self.interface_cache_misses+=1
   else:self.interface_cache_hits+=1
  state=self._interface_value
  record={'time_s':float(self.data.time),'translation_m':state.displacement_human_m.copy(),'rotation_rad':state.rotation_error_human_rad.copy()}
  if self.interface_history and abs(self.interface_history[-1]['time_s']-self.data.time)<1e-12:self.interface_history[-1]=record
  else:self.interface_history.append(record)
 C.step_native=step;INSTALLED=True
 return original,step
