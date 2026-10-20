"""Opt-in engineering cubic cuff bushing; global relative-frame motion, SI units.

Not measured tissue. The potential defines a passive two-port constitutive law;
explicit time integration still requires independent numerical qualification.
"""
from dataclasses import dataclass
import numpy as np
from scipy.spatial.transform import Rotation
from .spring_damper_interface import AttachmentState, InterfaceState, SpringDamperCoupledUR10eHumanV2


@dataclass(frozen=True)
class ProgressiveParameters:
    k1_n_m: float
    k3_n_m3: float
    damping_ns_m: float
    kr1_nm_rad: float
    kr3_nm_rad3: float
    rotational_damping_nms_rad: float

    def __post_init__(self):
        values=np.asarray(list(vars(self).values()),dtype=float)
        if values.shape!=(6,) or not np.isfinite(values).all() or np.any(values<0):
            raise ValueError('Progressive coefficients must be finite nonnegative scalars')
        if self.k1_n_m<=0 or self.kr1_nm_rad<=0:
            raise ValueError('Positive small-motion translation and rotation stiffness required')


def radial_load(displacement,k1,k3):
    x=np.asarray(displacement,dtype=float)
    return (k1+k3*float(x@x))*x


def tangent_stiffness(displacement,k1,k3):
    x=np.asarray(displacement,dtype=float)
    return (k1+k3*float(x@x))*np.eye(3)+2*k3*np.outer(x,x)


def evaluate_progressive(parameters:ProgressiveParameters,robot:AttachmentState,human:AttachmentState)->InterfaceState:
    r=robot.position_world_m-human.position_world_m
    rh=human.rotation_world
    x=rh.T@r
    u=rh.T@(robot.velocity_world_m_s-human.velocity_world_m_s-np.cross(human.angular_velocity_world_rad_s,r))
    theta=Rotation.from_matrix(rh.T@robot.rotation_world).as_rotvec()
    omega=rh.T@(robot.angular_velocity_world_rad_s-human.angular_velocity_world_rad_s)
    elastic=radial_load(x,parameters.k1_n_m,parameters.k3_n_m3)
    elastic_rot=radial_load(theta,parameters.kr1_nm_rad,parameters.kr3_nm_rad3)
    force=rh@(elastic+parameters.damping_ns_m*u)
    couple=rh@(elastic_rot+parameters.rotational_damping_nms_rad*omega)
    wh=np.r_[force,couple+np.cross(r,force)]
    wr=np.r_[-force,-couple]
    xx=float(x@x); tt=float(theta@theta)
    energy=.5*parameters.k1_n_m*xx+.25*parameters.k3_n_m3*xx**2+.5*parameters.kr1_nm_rad*tt+.25*parameters.kr3_nm_rad3*tt**2
    loss=parameters.damping_ns_m*float(u@u)+parameters.rotational_damping_nms_rad*float(omega@omega)
    power=float(wr@np.r_[robot.velocity_world_m_s,robot.angular_velocity_world_rad_s]+wh@np.r_[human.velocity_world_m_s,human.angular_velocity_world_rad_s])
    return InterfaceState(x,u,theta,omega,wh,wr,float(energy),float(loss),power,float(elastic@u+elastic_rot@omega))


class ProgressiveCoupledUR10eHumanV2(SpringDamperCoupledUR10eHumanV2):
    """Explicit opt-in: new constitutive law, inherited two-site application/step.

    Pass ProgressiveParameters explicitly. Rest is fixed coincident frames;
    constructor/solver/controller defaults are inherited, never retuned here.
    """
    def _evaluate_current_interface(self):
        if not isinstance(self.interface_parameters,ProgressiveParameters):
            raise TypeError('ProgressiveParameters required; old linear candidate is retired')
        return evaluate_progressive(self.interface_parameters,
            self._attachment_state(self.attachment_site_id),self._attachment_state(self.sleeve_site_id))
