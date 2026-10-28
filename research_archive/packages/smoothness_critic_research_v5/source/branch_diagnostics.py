"""Causal logging wrapper; return exactly the unmodified original correction.
No replacement guard, decision changes, truth access or model fitting.
"""
import numpy as np
from traction_mpc_stage3.coupled import BED_HEIGHT_M,SLEEVE_HALF_LENGTH_M as L,SLEEVE_OUTER_RADIUS_M as R

def install():
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import clearance_feedback as cf
 original=cf.clearance_acceleration_correction
 def observe(model,state,acceleration,interface,limits,**kw):
  correction,record=original(model,state,acceleration,interface,limits,**kw)
  q=np.asarray(state[:2]);dq=np.asarray(state[2:]);g=model.geometry;phi=q[0]-q[1];px,pz=g.plane_x_world[2],g.plane_z_world[2]
  az=float(px*np.cos(phi)+pz*np.sin(phi));azp=float(-px*np.sin(phi)+pz*np.cos(phi));rate=azp*float(dq[0]-dq[1]);axis=np.asarray(interface.human_rotation_world)[:,0];mz=float(axis[2]);mdot=float(np.cross(interface.human_angular_velocity_world_rad_s,axis)[2]);center=float(interface.human_position_world_m[2]);vel=float(interface.human_velocity_world_m_s[2]);rad=R*np.sqrt(max(0.,1-mz*mz));radfactor=R*mz/np.sqrt(max(1e-12,1-mz*mz))
  eps=1e-5;qm=q-eps*dq;qp=q+eps*dq
  axis_fn=lambda v:float(px*np.cos(v[0]-v[1])+pz*np.sin(v[0]-v[1]))
  record['v4_branch_diagnostic']=dict(model_axis_z=az,model_axis_rate_s_inv=rate,measured_axis_z=mz,measured_axis_rate_s_inv=mdot,model_axis_minus=axis_fn(qm),model_axis_plus=axis_fn(qp),directional_stencil_crosses=bool(axis_fn(qm)*axis_fn(qp)<=0),model_distance_to_crossing_stencil_ratio=abs(az)/max(1e-30,eps*abs(rate)),measured_endpoint_gaps_m=[center+s*L*mz-rad-BED_HEIGHT_M for s in [-1,1]],measured_endpoint_gap_rates_m_s=[vel+(s*L+radfactor)*mdot for s in [-1,1]],source='same causal model/state/interface passed to original guard',guard_action_unchanged=True,truth_used=False)
  return correction,record
 cf.clearance_acceleration_correction=observe
 return original
