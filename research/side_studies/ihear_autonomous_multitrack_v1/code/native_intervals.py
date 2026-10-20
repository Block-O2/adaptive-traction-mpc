"""N12: exact outward interval arithmetic; original proof and eligibility."""
import numpy as np,math
INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 import native_interface_adapter as a
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 original=m.monotonic_certificate
 def certificate(envelope,coefficients):
  c=np.asarray(coefficients,dtype=float);g=envelope.geometry;tool=m.STAGE5_GEOMETRY.end_effector_from_cuff
  record={'method':'outward_interval_common_progress_v2','eligible':False,'lowers':{},'body_proofs':{},'proof_scope':'model reference geometry only; no physical invariance or state-estimation guarantee'}
  arrays=(c,g.origin_world_m,g.hip_plane_m,g.plane_x_world,g.plane_z_world,tool.translation,tool.rotation,envelope.cuff_reference_translation_world_m)
  if not all(np.all(np.isfinite(x)) for x in arrays):raise ValueError('nonfinite geometry or polynomial cannot be certified')
  if c.shape!=(2,6):return record
  if not (np.array_equal(g.plane_x_world,[1.,0.,0.]) and np.array_equal(g.plane_z_world,[0.,0.,1.]) and np.array_equal(tool.rotation,[[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]]) and tool.translation[0]==tool.translation[2]==0. and tool.translation[1]>m.SLEEVE_OUTER_RADIUS_M):return record
  vals=[g.thigh_length_m,g.cuff_distance_m,envelope.shank_length_upper_m]
  if not np.all(np.isfinite(vals)) or min(vals)<=0.:raise ValueError('invalid geometry dimensions')
  params=np.asarray([g.thigh_length_m,g.cuff_distance_m,envelope.shank_length_upper_m,m.SLEEVE_HALF_LENGTH_M,m.SLEEVE_OUTER_RADIUS_M,.5*m.STAGE5_GEOMETRY.cuff_bar_length_m,m.STAGE5_GEOMETRY.cuff_bar_radius_m,float(tool.translation[1]),envelope.registered_proximal_installation_gap_lower_m,envelope.existing_shank_margin_m,math.pi],dtype=float)
  # Conservative native interior avoids altering original overflow/errors.
  if not np.all(np.isfinite(params)) or np.max(np.abs(params))>1e4 or np.max(np.abs(c))>1e4:return original(envelope,coefficients)
  deltas=np.asarray([float(math.fsum(row)-row[0]) for row in c])
  def endpoints(*numbers):
   values=[]
   for offset in (0,4):
    q=(m.I(numbers[offset],numbers[offset+1]),m.I(numbers[offset+2],numbers[offset+3]))
    e=m.endpoint(envelope,q)
    for name in ('proximal_thigh_m','distal_shank_m','sleeve_m','cuff_bar_m','cuff_adapter_m'):values.extend((e[name].lo,e[name].hi))
   return np.asarray(values,dtype=float)
  core=a.native.interval_certificate(c,deltas,params,m._trig_bounds,endpoints)
  if core is not None:record.update(core)
  return record
 m.monotonic_certificate=certificate;INSTALLED=True
 return original,certificate
