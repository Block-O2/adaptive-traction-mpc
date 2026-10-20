"""N7 exact observer inversion; original update and timestamp guards retained."""
from pathlib import Path
import sys,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 sys.path.insert(0,str(S/'build'));import fast_native as native
 from traction_mpc_stage5 import controller_interface as ci
 C=ci.InterfaceAwareHumanStateObserver;original=C._invert_measurement
 def rotation(vector):return ci.Rotation.from_rotvec(vector).as_matrix()
 def invert(self,measurement,timestamp):
  p=self.parameters;names=('cuff_force_vector_n','cuff_moment_vector_nm','attachment_position_m','attachment_rotation_matrix','attachment_velocity_m_s','attachment_angular_velocity_rad_s');values=[np.asarray(getattr(measurement,name),dtype=float) for name in names]
  if any(v.shape!=((3,3) if i==3 else (3,)) or not np.all(np.isfinite(v)) for i,v in enumerate(values)) or not values[3].flags.c_contiguous:return original(self,measurement,timestamp)
  k=np.asarray(p.translation_stiffness_n_m);d=np.asarray(p.translation_damping_ns_m);x0=np.asarray(p.rest_translation_human_m);theta0=np.asarray(p.rest_rotation_rotvec_human_rad)
  if any(v.shape!=(3,) or v.dtype!=np.dtype('float64') for v in (k,d,x0,theta0)):return original(self,measurement,timestamp)
  initial=self._last is None;dt=0. if initial else timestamp-self._last.sample_timestamp_s
  if not initial and dt<=0:raise ValueError('interface observer requires increasing sample timestamps')
  prior=np.concatenate((x0,theta0)) if initial else np.concatenate((self._last.displacement_human_m,self._last.rotation_error_human_rad))
  if prior.shape!=(6,) or not np.all(np.isfinite(prior)):return original(self,measurement,timestamp)
  parameters=np.concatenate((k,d,x0,theta0,np.array([p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad])))
  result=native.observer_invert(np.concatenate([v.ravel() for v in values]),parameters,prior,dt,p.observer_fixed_point_iterations,initial,rotation)
  fields=('displacement_human_m','velocity_human_m_s','rotation_error_human_rad','angular_velocity_human_rad_s','human_position_world_m','human_rotation_world','human_velocity_world_m_s','human_angular_velocity_world_rad_s','measured_force_world_n','measured_moment_world_nm')
  return ci.EstimatedInterfaceState(sample_timestamp_s=timestamp,**dict(zip(fields,result)))
 C._invert_measurement=invert;INSTALLED=True;return original,invert
