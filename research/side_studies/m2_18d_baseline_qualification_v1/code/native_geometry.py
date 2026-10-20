"""N6: exact NumPy trigonometry/constants plus fixed elementwise margins."""
from pathlib import Path
import sys,numpy as np,math
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1');INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 sys.path.insert(0,str(S/'build'));import fast_native as n
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import rigid_table_reference as r
 original=r.RigidTableReferenceEnvelopeV1.margins
 def margins(self,q):
  rows=np.atleast_2d(np.asarray(q,dtype=float))
  if rows.ndim!=2 or rows.shape[1]!=2 or not np.all(np.isfinite(rows)):return original(self,q)
  g=self.geometry;e=r.STAGE5_GEOMETRY.end_effector_from_cuff;t=np.asarray(e.translation,dtype=float)
  if any(np.asarray(getattr(g,name)).dtype!=np.dtype('float64') for name in ('origin_world_m','plane_x_world','plane_z_world','hip_plane_m','knee_to_cuff_in_cuff_m')):return original(self,q)
  px=float(g.plane_x_world[2]);pz=float(g.plane_z_world[2]);hip=(float(g.origin_world_m[2])+g.hip_plane_m[0]*px)+g.hip_plane_m[1]*pz
  norm=float(np.linalg.norm(t));length=max(0.,norm-r.SLEEVE_OUTER_RADIUS_M)
  offset=np.asarray(e.rotation).T@t
  frame_y=float(np.cross(g.plane_z_world,g.plane_x_world)[2])
  params=np.asarray([px,pz,hip,g.thigh_length_m,self.shank_length_upper_m,g.cuff_distance_m,self.cuff_reference_translation_world_m[2],r.SLEEVE_HALF_LENGTH_M,.5*r.STAGE5_GEOMETRY.cuff_bar_length_m,self.registered_proximal_installation_gap_lower_m,r.THIGH_RADIUS_M,r.BED_HEIGHT_M,r.SHANK_RADIUS_M,self.existing_shank_margin_m,r.SLEEVE_OUTER_RADIUS_M,r.STAGE5_GEOMETRY.cuff_bar_radius_m,length,offset[0],frame_y*offset[1],offset[2],norm,math.pi],dtype=float)
  if not np.all(np.isfinite(params)):return original(self,q)
  phi=rows[:,0]-rows[:,1];trigs=np.asarray([np.cos(rows[:,0]),np.sin(rows[:,0]),np.cos(phi),np.sin(phi)])
  out=n.table_margins(rows,trigs,params)
  return {name:out[i] for i,name in enumerate(('proximal_thigh_m','distal_shank_m','sleeve_m','cuff_bar_m','cuff_adapter_m'))}
 from traction_mpc_stage4 import estimator_v2 as ma
 original_j=ma.PlanarCuffGeometry.translational_jacobian_world;original_regressor=ma.dynamic_regressor_row
 def jacobian(self,q_rad):
  q=np.asarray(q_rad,dtype=float);px=np.asarray(self.plane_x_world);pz=np.asarray(self.plane_z_world)
  if q.shape!=(2,) or px.shape!=(3,) or pz.shape!=(3,) or px.dtype!=np.dtype('float64') or pz.dtype!=np.dtype('float64') or not np.all(np.isfinite(q)):return original_j(self,q_rad)
  return n.planar_jacobian(q,px,pz,self.thigh_length_m,self.cuff_distance_m)
 def regressor(q_rad,dq_rad_s,ddq_rad_s2):
  q=np.asarray(q_rad,dtype=float);v=np.asarray(dq_rad_s,dtype=float);a=np.asarray(ddq_rad_s2,dtype=float)
  if any(x.shape!=(2,) or not np.all(np.isfinite(x)) for x in (q,v,a)):return original_regressor(q_rad,dq_rad_s,ddq_rad_s2)
  return n.regressor2(q,v,a)
 from loaded_context_reuse import aliases
 ma.PlanarCuffGeometry.translational_jacobian_world=jacobian;aliases(original_regressor,regressor)
 r.RigidTableReferenceEnvelopeV1.margins=margins;INSTALLED=True
 return original,margins,original_j,jacobian,original_regressor,regressor
