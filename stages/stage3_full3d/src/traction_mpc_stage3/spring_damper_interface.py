"""Objective Kelvin--Voigt bushing; SI units, world poses, Human-frame strain.

No qualified material constants are provided. See SPRING_DAMPER_INTERFACE_V1.md
for the potential, transport couple, power identity, and numerical limitations.
"""
from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .coupled import CoupledObservation, CoupledUR10eHumanV2, LYING_BED_SCENARIO
from .frames import ATTACHMENT_FROM_CUFF, RigidTransform
from .human import HUMAN, HumanV2Parameters


@dataclass(frozen=True)
class InterfaceParameters:
    # Diagonal translation tensors expressed in the moving Human cuff frame.
    translation_stiffness_n_m: tuple[float, float, float]
    translation_damping_ns_m: tuple[float, float, float]
    # Isotropic SO(3) rotation spring, independently parameterized.
    rotation_stiffness_nm_rad: float
    rotation_damping_nms_rad: float
    rest_translation_human_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rest_rotation_rotvec_human_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        for name in ("translation_stiffness_n_m", "translation_damping_ns_m",
                     "rest_translation_human_m", "rest_rotation_rotvec_human_rad"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (3,) or not np.isfinite(value).all():
                raise ValueError(f"{name} must be a finite three-vector")
            object.__setattr__(self, name, tuple(float(x) for x in value))
        for name in ("translation_stiffness_n_m", "translation_damping_ns_m",
                     "rotation_stiffness_nm_rad", "rotation_damping_nms_rad"):
            value = np.asarray(getattr(self, name), dtype=float)
            if not np.isfinite(value).all() or np.any(value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")
        for name in ("rotation_stiffness_nm_rad", "rotation_damping_nms_rad"):
            if np.asarray(getattr(self, name)).shape != ():
                raise ValueError(f"{name} must be a scalar")


@dataclass(frozen=True)
class AttachmentState:
    position_world_m: np.ndarray
    rotation_world: np.ndarray
    velocity_world_m_s: np.ndarray
    angular_velocity_world_rad_s: np.ndarray


@dataclass(frozen=True)
class InterfaceState:
    displacement_human_m: np.ndarray
    velocity_human_m_s: np.ndarray
    rotation_error_human_rad: np.ndarray
    angular_velocity_human_rad_s: np.ndarray
    human_wrench_world: np.ndarray  # force then moment ABOUT HUMAN SITE
    robot_wrench_world: np.ndarray  # force then moment ABOUT ROBOT SITE
    spring_energy_j: float
    damping_dissipation_w: float
    mechanical_power_w: float
    spring_energy_rate_w: float


def evaluate_interface(
    parameters: InterfaceParameters, robot: AttachmentState, human: AttachmentState,
) -> InterfaceState:
    """Return the pair of site wrenches; does not mutate either plant or state.

    r = p_R-p_H; x = R_H.T r-r0; u = R_H.T(v_R-v_H-w_H cross r).
    Positive strain pulls the Human toward the robot. The Human transport
    couple r cross F is necessary for both angular momentum and passivity.
    """
    r = robot.position_world_m - human.position_world_m
    rh = human.rotation_world
    x = rh.T @ r - np.asarray(parameters.rest_translation_human_m)
    u = rh.T @ (robot.velocity_world_m_s - human.velocity_world_m_s
                - np.cross(human.angular_velocity_world_rad_s, r))
    r0 = Rotation.from_rotvec(parameters.rest_rotation_rotvec_human_rad).as_matrix()
    theta = Rotation.from_matrix(rh.T @ robot.rotation_world @ r0.T).as_rotvec()
    omega = rh.T @ (robot.angular_velocity_world_rad_s
                    - human.angular_velocity_world_rad_s)
    k = np.asarray(parameters.translation_stiffness_n_m)
    d = np.asarray(parameters.translation_damping_ns_m)
    kr = parameters.rotation_stiffness_nm_rad
    dr = parameters.rotation_damping_nms_rad
    force = rh @ (k * x + d * u)
    couple = rh @ (kr * theta + dr * omega)
    human_wrench = np.r_[force, couple + np.cross(r, force)]
    robot_wrench = np.r_[-force, -couple]
    power = (human_wrench @ np.r_[human.velocity_world_m_s,
                                  human.angular_velocity_world_rad_s]
             + robot_wrench @ np.r_[robot.velocity_world_m_s,
                                    robot.angular_velocity_world_rad_s])
    return InterfaceState(
        x, u, theta, omega, human_wrench, robot_wrench,
        float(0.5 * (x @ (k * x) + kr * (theta @ theta))),
        float(u @ (d * u) + dr * (omega @ omega)),
        float(power), float(x @ (k * u) + kr * (theta @ omega)),
    )


@dataclass(frozen=True)
class SoftInterfacePhysicalObservation(CoupledObservation):
    """Physical diagnostics, not a co-located robot-facing sensor sample."""
    cuff_wrench_reference_point: str = 'sleeve_attach_site'
    controller_measurement_requires_adapter: bool = True


class SpringDamperCoupledUR10eHumanV2(CoupledUR10eHumanV2):
    """Opt-in compliant plant, with the inherited six-row weld always disabled.

    Robot, Human, adapter, contacts, controller and force limits are inherited.
    The rigid class and its default timestep/stepping path are untouched.
    The applied velocity-dependent bushing force is explicit even with MuJoCo's
    implicitfast integrator: a small physics timestep remains necessary.
    """

    def __init__(self, parameters: InterfaceParameters,
                 human: HumanV2Parameters = HUMAN, *, physics_dt_s: float,
                 attachment_from_cuff: RigidTransform = ATTACHMENT_FROM_CUFF,
                 engineering_scenario: str = LYING_BED_SCENARIO) -> None:
        if not np.isfinite(physics_dt_s) or physics_dt_s <= 0:
            raise ValueError("physics_dt_s must be finite and positive")
        self.interface_parameters = parameters
        super().__init__(human, attachment_from_cuff=attachment_from_cuff,
                         engineering_scenario=engineering_scenario)
        self.model.opt.timestep = physics_dt_s
        self.model.eq_active0[self.weld_id] = 0
        self.data.eq_active[self.weld_id] = 0
        self.interface_generalized_force = np.zeros(self.model.nv)

    def _attachment_state(self, site_id: int) -> AttachmentState:
        angular, linear = self._site_velocity(site_id)
        return AttachmentState(
            self.data.site_xpos[site_id].copy(),
            self.data.site_xmat[site_id].reshape(3, 3).copy(), linear, angular,
        )

    def _evaluate_current_interface(self) -> InterfaceState:
        return evaluate_interface(self.interface_parameters,
                                  self._attachment_state(self.attachment_site_id),
                                  self._attachment_state(self.sleeve_site_id))

    def _apply_interface(self) -> None:
        state = self._evaluate_current_interface()
        self.interface_generalized_force[:] = 0.0
        for site_id, wrench in ((self.sleeve_site_id, state.human_wrench_world),
                                (self.attachment_site_id, state.robot_wrench_world)):
            mujoco.mj_applyFT(
                self.model, self.data, wrench[:3], wrench[3:],
                self.data.site_xpos[site_id], int(self.model.site_bodyid[site_id]),
                self.interface_generalized_force,
            )
        self.data.qfrc_applied[:] += self.interface_generalized_force

    def _refresh(self) -> None:
        # Also handles super().reset(): its temporary weld activation is removed
        # before returning any observation or integrating any physical time.
        self.data.eq_active[self.weld_id] = 0
        mujoco.mj_fwdPosition(self.model, self.data)
        mujoco.mj_fwdVelocity(self.model, self.data)
        self._apply_soft_limit()
        self._apply_interface()
        mujoco.mj_forward(self.model, self.data)

    def interface_diagnostics(self) -> tuple[InterfaceState, AttachmentState, AttachmentState]:
        self._refresh()
        return (self._evaluate_current_interface(),
                self._attachment_state(self.attachment_site_id),
                self._attachment_state(self.sleeve_site_id))

    def reconstruct_cuff_wrench(self) -> tuple[np.ndarray, float, np.ndarray, float]:
        # Compatibility observation fields now mean interface generalized load,
        # not an equality multiplier. The reported wrench is ABOUT HUMAN SITE.
        state = self._evaluate_current_interface()
        human_j = self._site_pose_jacobian(self.sleeve_site_id)
        robot_j = self._site_pose_jacobian(self.attachment_site_id)
        mapped = human_j.T @ state.human_wrench_world + robot_j.T @ state.robot_wrench_world
        tau = self.interface_generalized_force[self.human_dof_indices].copy()
        residual = np.linalg.norm(mapped - self.interface_generalized_force)
        tau_residual = np.linalg.norm(
            human_j[:, self.human_dof_indices].T @ state.human_wrench_world - tau)
        return state.human_wrench_world.copy(), float(residual), tau, float(tau_residual)

    def observe(self):
        self._refresh()
        return SoftInterfacePhysicalObservation(**vars(super().observe()))

    def step(self):
        self.data.eq_active[self.weld_id] = 0
        # Current qpos/qvel -> current site transforms/twists -> same-step loads.
        mujoco.mj_step1(self.model, self.data)
        self._apply_soft_limit()
        self._apply_interface()
        mujoco.mj_step2(self.model, self.data)
        # mj_step2 leaves derived site fields at the pre-integration state.
        return self.observe()
