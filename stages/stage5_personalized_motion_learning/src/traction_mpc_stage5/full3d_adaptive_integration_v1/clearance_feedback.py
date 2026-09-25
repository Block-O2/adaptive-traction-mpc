"""Development-only causal sleeve clearance acceleration correction.

This is a controller-internal response approximation, not an invariance proof.
No case key, physical parameters, plant state or hidden joint state is accepted.
"""
from __future__ import annotations

import numpy as np
from traction_mpc_stage3.coupled import SLEEVE_HALF_LENGTH_M, SLEEVE_OUTER_RADIUS_M
from .rigid_table_reference import RigidTableReferenceEnvelopeV1


def project_acceleration_halfspaces(acceleration, normals, lower, limits):
    """Exact Euclidean projection in two dimensions, or an explicit empty-set result."""
    a=np.asarray(acceleration,dtype=float)
    A=np.vstack([np.asarray(normals,dtype=float),np.eye(2),-np.eye(2)])
    b=np.r_[np.asarray(lower,dtype=float),-np.asarray(limits),-np.asarray(limits)]
    feasible=lambda x:bool(np.all(A@x>=b-1e-10))
    if feasible(a):return a.copy(),True
    candidates=[]
    for n,c in zip(A,b):
        norm=float(n@n)
        if norm>1e-20:
            x=a+(c-float(n@a))/norm*n
            if feasible(x):candidates.append(x)
    for i in range(len(A)):
        for j in range(i):
            u,v=A[i],A[j];det=u[0]*v[1]-u[1]*v[0]
            if abs(det)>1e-14:
                x=np.array([(b[i]*v[1]-u[1]*b[j])/det,
                            (u[0]*b[j]-b[i]*v[0])/det])
                if feasible(x):candidates.append(x)
    if not candidates:return np.clip(a,-limits,limits),False
    return min(candidates,key=lambda x:float((x-a)@(x-a))).copy(),True


def clearance_acceleration_correction(model, state, acceleration, interface, limits,
                                      *, response_s=.04, adverse_acceleration_m_s2=.5,
                                      protect_conservative_shank=False):
    q, dq = np.asarray(state[:2]), np.asarray(state[2:])
    a = np.asarray(acceleration, dtype=float)
    env = RigidTableReferenceEnvelopeV1(model.geometry)
    gap = env.measured_sleeve_gap(interface.human_position_world_m, interface.human_rotation_world)
    axis = np.asarray(interface.human_rotation_world)[:, 0]
    az = float(axis[2])
    az_dot = float(np.cross(interface.human_angular_velocity_world_rad_s, axis)[2])
    gap_velocity = (float(interface.human_velocity_world_m_s[2])
                    + (-SLEEVE_HALF_LENGTH_M * np.sign(az)
                       + SLEEVE_OUTER_RADIUS_M * az / np.sqrt(max(1e-12, 1-az*az))) * az_dot)
    # Evaluate the model gradient only; its absolute position is replaced by
    # causal sleeve geometry. The 10 um reserve exceeds the 3.2 um observed
    # reconstruction error in the retained baseline; it is not a new limit.
    eps = 1e-5
    basis = np.eye(2) * eps
    gp = env.margins(q[None, :] + basis)['sleeve_m']
    gm = env.margins(q[None, :] - basis)['sleeve_m']
    grad = (gp-gm)/(2*eps)
    directional = (env.margins(q+eps*dq)['sleeve_m'][0]
                   - 2*env.margins(q)['sleeve_m'][0]
                   + env.margins(q-eps*dq)['sleeve_m'][0])/(eps*eps)
    required = 2*(1e-5-gap-response_s*gap_velocity)/(response_s**2) + adverse_acceleration_m_s2
    shortfall = max(0., required - float(grad@a) - float(directional))
    adjusted = a.copy()
    # Project onto a single gap-acceleration half-space within the original
    # joint-acceleration box. Explicit active-set solve, no hidden clipping.
    free = np.ones(2, dtype=bool)
    if shortfall > 0:
        adjusted = np.clip(adjusted, -limits, limits)
        for _ in range(3):
            remaining = required - float(grad@adjusted) - float(directional)
            if remaining <= 1e-10:
                break
            direction = np.where(free, grad, 0.)
            norm = float(direction@direction)
            if norm < 1e-15:
                break
            proposed = adjusted + remaining/norm * direction
            saturated = np.abs(proposed) > limits
            adjusted = np.clip(proposed, -limits, limits)
            free &= ~saturated
    shank_record=None
    if protect_conservative_shank:
        shank_gap=float(env.margins(q)['distal_shank_m'][0])
        shank_grad=(env.margins(q[None,:]+basis)['distal_shank_m']
                    -env.margins(q[None,:]-basis)['distal_shank_m'])/(2*eps)
        shank_curvature=float((env.margins(q+eps*dq)['distal_shank_m'][0]
                    -2*shank_gap+env.margins(q-eps*dq)['distal_shank_m'][0])/(eps*eps))
        shank_velocity=float(shank_grad@dq)
        shank_required=2*(-shank_gap-response_s*shank_velocity)/(response_s**2)+adverse_acceleration_m_s2
        adjusted,joint_feasible=project_acceleration_halfspaces(a,
            np.vstack([grad,shank_grad]),[required-directional,shank_required-shank_curvature],np.asarray(limits))
        shank_record={'source':'current causal model geometry/state with unchanged .46m shank upper bound and1mm margin',
            'gap_m':shank_gap,'gap_velocity_m_s':shank_velocity,'model_gap_gradient_m_rad':shank_grad,
            'model_curvature_m_s2':shank_curvature,'required_gap_acceleration_m_s2':shank_required,
            'joint_halfspace_box_feasible':joint_feasible,
            'constraint_satisfied':bool(shank_grad@adjusted+shank_curvature>=shank_required-1e-8)}
    correction = (model.inverse_dynamics(q,dq,adjusted)-model.inverse_dynamics(q,dq,a))
    record = {'gap_m':gap, 'gap_velocity_m_s':gap_velocity,
              'model_gap_gradient_m_rad':grad.copy(), 'model_curvature_m_s2':float(directional),
              'joint_acceleration_box_rad_s2':np.asarray(limits).copy(),
              'response_s':response_s,'adverse_acceleration_m_s2':adverse_acceleration_m_s2,
              'required_gap_acceleration_m_s2':required,'requested_acceleration_rad_s2':a,
              'adjusted_acceleration_rad_s2':adjusted,'correction_nm':correction,
              'active':shortfall>0,'constraint_satisfied':float(grad@adjusted)+directional>=required-1e-8}
    if shank_record is not None:
        record['conservative_shank']=shank_record
        record['active']=bool(np.any(np.abs(adjusted-a)>1e-12))
    return correction, record
