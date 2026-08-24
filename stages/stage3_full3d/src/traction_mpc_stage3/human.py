"""Frozen Human V2 mechanics and nominal cuff-wrench allocation.

This is an explicit Stage-3 port.  It intentionally has no runtime import from
either frozen ``traction_mpc`` package.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .reference import CuffPoseReference


@dataclass(frozen=True)
class HumanV2Parameters:
    height_m: float = 1.72
    body_mass_kg: float = 75.0
    gravity_m_s2: float = 9.81
    q_rest_rad: tuple[float, float] = (math.radians(5.0), math.radians(10.0))
    passive_stiffness_nm_rad: tuple[float, float] = (10.0, 10.0)
    passive_damping_nms_rad: tuple[float, float] = (5.0, 5.0)
    q_min_rad: tuple[float, float] = (0.0, 0.0)
    q_max_rad: tuple[float, float] = (math.radians(80.0), math.radians(100.0))
    soft_limit_margin_rad: float = math.radians(5.0)
    soft_limit_numerical_tolerance_rad: float = 1e-9
    soft_limit_boundary_torque_nm: float = 25.0
    soft_limit_damping_nms_rad: float = 2.0

    @property
    def thigh_length_m(self) -> float:
        return 0.254 * self.height_m

    @property
    def shank_length_m(self) -> float:
        return 0.233 * self.height_m

    @property
    def thigh_mass_kg(self) -> float:
        return 0.099 * self.body_mass_kg

    @property
    def shank_mass_kg(self) -> float:
        return (0.046 + 0.014) * self.body_mass_kg

    @property
    def thigh_com_m(self) -> float:
        return 0.433 * self.thigh_length_m

    @property
    def shank_com_m(self) -> float:
        return 0.430 * self.shank_length_m

    @property
    def thigh_inertia_kg_m2(self) -> float:
        return self.thigh_mass_kg * (0.30 * self.thigh_length_m) ** 2

    @property
    def shank_inertia_kg_m2(self) -> float:
        return self.shank_mass_kg * (0.30 * self.shank_length_m) ** 2

    @property
    def sleeve_center_m(self) -> float:
        return 0.90 * self.shank_length_m


HUMAN = HumanV2Parameters()
TRACKING_KP_RAD_S2_PER_RAD = np.array([180.0, 140.0])
TRACKING_KD_RAD_S2_PER_RAD_S = np.array([28.0, 22.0])
CUFF_TRANSLATIONAL_FORCE_GATE_N = 200.0


def sleeve_position(q_rad: np.ndarray, human: HumanV2Parameters = HUMAN) -> np.ndarray:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    return np.array(
        [
            human.thigh_length_m * math.cos(q1)
            + human.sleeve_center_m * math.cos(phi),
            0.0,
            0.062
            + human.thigh_length_m * math.sin(q1)
            + human.sleeve_center_m * math.sin(phi),
        ]
    )


def sleeve_jacobian(q_rad: np.ndarray, human: HumanV2Parameters = HUMAN) -> np.ndarray:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    l1, sc = human.thigh_length_m, human.sleeve_center_m
    return np.array(
        [
            [-l1 * math.sin(q1) - sc * math.sin(phi), sc * math.sin(phi)],
            [0.0, 0.0],
            [l1 * math.cos(q1) + sc * math.cos(phi), -sc * math.cos(phi)],
        ]
    )


def mass_matrix(q_rad: np.ndarray, human: HumanV2Parameters = HUMAN) -> np.ndarray:
    q2 = float(np.asarray(q_rad)[1])
    b = human.shank_inertia_kg_m2 + human.shank_mass_kg * human.shank_com_m**2
    d = human.shank_mass_kg * human.thigh_length_m * human.shank_com_m
    a = (
        human.thigh_inertia_kg_m2
        + human.thigh_mass_kg * human.thigh_com_m**2
        + b
        + human.shank_mass_kg * human.thigh_length_m**2
    )
    return np.array(
        [
            [a + 2.0 * d * math.cos(q2), -(b + d * math.cos(q2))],
            [-(b + d * math.cos(q2)), b],
        ]
    )


def soft_limit_torque(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    human: HumanV2Parameters = HUMAN,
) -> np.ndarray:
    q = np.asarray(q_rad, dtype=float)
    dq = np.asarray(dq_rad_s, dtype=float)
    lower = np.asarray(human.q_min_rad) + human.soft_limit_margin_rad
    upper = np.asarray(human.q_max_rad) - human.soft_limit_margin_rad
    lower -= human.soft_limit_numerical_tolerance_rad
    upper += human.soft_limit_numerical_tolerance_rad
    torque = np.zeros(2)
    for index in range(2):
        if q[index] < lower[index]:
            z = (lower[index] - q[index]) / human.soft_limit_margin_rad
            torque[index] = human.soft_limit_boundary_torque_nm * z**3
            torque[index] += (
                human.soft_limit_damping_nms_rad
                * z**2
                * max(-dq[index], 0.0)
            )
        elif q[index] > upper[index]:
            z = (q[index] - upper[index]) / human.soft_limit_margin_rad
            torque[index] = -human.soft_limit_boundary_torque_nm * z**3
            torque[index] -= (
                human.soft_limit_damping_nms_rad
                * z**2
                * max(dq[index], 0.0)
            )
    return torque


def nominal_tracking_wrench(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    reference: CuffPoseReference,
    human: HumanV2Parameters = HUMAN,
) -> dict[str, np.ndarray | float]:
    """Port the frozen Stage-2 computed-acceleration and cuff allocation law."""

    q = np.asarray(q_rad, dtype=float)
    dq = np.asarray(dq_rad_s, dtype=float)
    q1, q2 = q
    phi = q1 - q2
    coupling = human.shank_mass_kg * human.thigh_length_m * human.shank_com_m
    coriolis = np.array(
        [
            coupling * math.sin(q2) * (-2.0 * dq[0] * dq[1] + dq[1] ** 2),
            coupling * math.sin(q2) * dq[0] ** 2,
        ]
    )
    gravity = np.array(
        [
            human.gravity_m_s2
            * (
                (human.thigh_mass_kg * human.thigh_com_m
                 + human.shank_mass_kg * human.thigh_length_m)
                * math.cos(q1)
                + human.shank_mass_kg * human.shank_com_m * math.cos(phi)
            ),
            -human.shank_mass_kg
            * human.gravity_m_s2
            * human.shank_com_m
            * math.cos(phi),
        ]
    )
    passive_left = (
        np.asarray(human.passive_stiffness_nm_rad)
        * (q - np.asarray(human.q_rest_rad))
        + np.asarray(human.passive_damping_nms_rad) * dq
        - soft_limit_torque(q, dq, human)
    )
    qdd_command = (
        np.asarray(reference.ddq_rad_s2)
        - TRACKING_KP_RAD_S2_PER_RAD * (q - np.asarray(reference.q_rad))
        - TRACKING_KD_RAD_S2_PER_RAD_S * (dq - np.asarray(reference.dq_rad_s))
    )
    tau_required = mass_matrix(q, human) @ qdd_command
    tau_required += coriolis + gravity + passive_left

    force_map = sleeve_jacobian(q, human)[[0, 2], :].T
    moment_map = np.array([1.0, -1.0])
    moment_orthogonal = np.array([1.0, 1.0]) / math.sqrt(2.0)
    projected_force_map = force_map.T @ moment_orthogonal
    projected_torque = float(moment_orthogonal @ tau_required)
    denominator = float(projected_force_map @ projected_force_map)
    if denominator <= 1e-18:
        raise RuntimeError("tracking cuff map cannot satisfy equilibrium")
    force_xz = projected_force_map * projected_torque / denominator
    my_nm = float(
        moment_map @ (tau_required - force_map @ force_xz)
        / (moment_map @ moment_map)
    )
    residual = float(
        np.linalg.norm(force_map @ force_xz + moment_map * my_nm - tau_required)
    )
    # MuJoCo world-y virtual work is [-1,+1]^T M_world, so M_world=-My.
    wrench_world = np.array([force_xz[0], 0.0, force_xz[1], 0.0, -my_nm, 0.0])
    return {
        "qdd_command_rad_s2": qdd_command,
        "tau_required_nm": tau_required,
        "force_xz_n": force_xz,
        "force_norm_n": float(np.linalg.norm(force_xz)),
        "my_nm": my_nm,
        "wrench_world": wrench_world,
        "allocation_residual_nm": residual,
    }
