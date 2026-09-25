"""Equation-equivalent private Kelvin-Voigt evaluator with cached constants.

Same SciPy SO(3) operations and original wrench/power/transport equations.
Only array construction, cross-product dispatch and constant conversion differ.
"""
import numpy as np
from scipy.spatial.transform import Rotation
from traction_mpc_stage3.spring_damper_interface import InterfaceState


def cross3(a,b):
    return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]])


def parameter_key(p):
    return (p.translation_stiffness_n_m,p.translation_damping_ns_m,
            p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad,
            p.rest_translation_human_m,p.rest_rotation_rotvec_human_rad)


class ExactInterfaceEvaluator:
    def __init__(self):
        self.key=None
    def evaluate(self,p,robot,human):
        key=parameter_key(p)
        if self.key!=key:
            rest_translation=np.asarray(p.rest_translation_human_m)
            rest_rotation=Rotation.from_rotvec(p.rest_rotation_rotvec_human_rad).as_matrix()
            stiffness=np.asarray(p.translation_stiffness_n_m)
            damping=np.asarray(p.translation_damping_ns_m)
            self.rest_translation,self.rest_rotation,self.k,self.d=rest_translation,rest_rotation,stiffness,damping
            self.key=key  # Publish only after all constants were constructed.
        r=robot.position_world_m-human.position_world_m
        rh=human.rotation_world
        x=rh.T@r-self.rest_translation
        u=rh.T@(robot.velocity_world_m_s-human.velocity_world_m_s-cross3(human.angular_velocity_world_rad_s,r))
        theta=Rotation.from_matrix(rh.T@robot.rotation_world@self.rest_rotation.T).as_rotvec()
        omega=rh.T@(robot.angular_velocity_world_rad_s-human.angular_velocity_world_rad_s)
        k,d=self.k,self.d;kr,dr=p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad
        force=rh@(k*x+d*u)
        couple=rh@(kr*theta+dr*omega)
        human_wrench=np.concatenate((force,couple+cross3(r,force)))
        robot_wrench=np.concatenate((-force,-couple))
        power=(human_wrench@np.concatenate((human.velocity_world_m_s,human.angular_velocity_world_rad_s))
               +robot_wrench@np.concatenate((robot.velocity_world_m_s,robot.angular_velocity_world_rad_s)))
        return InterfaceState(x,u,theta,omega,human_wrench,robot_wrench,
            float(.5*(x@(k*x)+kr*(theta@theta))),float(u@(d*u)+dr*(omega@omega)),
            float(power),float(x@(k*u)+kr*(theta@omega)))
