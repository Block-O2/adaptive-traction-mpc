"""Human-V2 prediction model used only by Stage-4 identification and MPC."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, mass_matrix, sleeve_jacobian, soft_limit_torque


@dataclass(frozen=True)
class ScaledHumanV2(HumanV2Parameters):
    thigh_com_scale: float = 1.0
    shank_com_scale: float = 1.0
    sleeve_center_scale: float = 1.0

    @property
    def thigh_com_m(self) -> float:
        return super().thigh_com_m * self.thigh_com_scale

    @property
    def shank_com_m(self) -> float:
        return super().shank_com_m * self.shank_com_scale

    @property
    def sleeve_center_m(self) -> float:
        return super().sleeve_center_m * self.sleeve_center_scale


PARAMETER_NAMES = (
    "mass_scale",
    "thigh_com_scale",
    "shank_com_scale",
    "stiffness_scale",
    "rest_hip_offset_rad",
    "rest_knee_offset_rad",
    "sleeve_center_scale",
)

PARAMETER_BOUNDS = {
    "mass_scale": (0.85, 1.20),
    "thigh_com_scale": (0.85, 1.15),
    "shank_com_scale": (0.85, 1.15),
    "stiffness_scale": (0.70, 1.40),
    "rest_hip_offset_rad": (math.radians(-5.0), math.radians(5.0)),
    "rest_knee_offset_rad": (math.radians(-5.0), math.radians(5.0)),
    "rest_common_offset_rad": (math.radians(-5.0), math.radians(5.0)),
    "sleeve_center_scale": (0.90, 1.10),
}


def nominal_parameter_vector(names: tuple[str, ...] = PARAMETER_NAMES) -> np.ndarray:
    defaults = {
        "mass_scale": 1.0,
        "thigh_com_scale": 1.0,
        "shank_com_scale": 1.0,
        "stiffness_scale": 1.0,
        "rest_hip_offset_rad": 0.0,
        "rest_knee_offset_rad": 0.0,
        "rest_common_offset_rad": 0.0,
        "sleeve_center_scale": 1.0,
    }
    return np.array([defaults[name] for name in names], dtype=float)


def parameterized_human(
    theta: np.ndarray,
    names: tuple[str, ...],
    *,
    nominal: HumanV2Parameters = HUMAN,
) -> ScaledHumanV2:
    values = dict(zip(names, np.asarray(theta, dtype=float), strict=True))
    mass_scale = float(values.get("mass_scale", 1.0))
    stiffness_scale = float(values.get("stiffness_scale", 1.0))
    common_rest_offset = float(values.get("rest_common_offset_rad", 0.0))
    rest_offset = common_rest_offset + np.array(
        [
            values.get("rest_hip_offset_rad", 0.0),
            values.get("rest_knee_offset_rad", 0.0),
        ],
        dtype=float,
    )
    return ScaledHumanV2(
        height_m=nominal.height_m,
        body_mass_kg=nominal.body_mass_kg * mass_scale,
        gravity_m_s2=nominal.gravity_m_s2,
        q_rest_rad=tuple(np.asarray(nominal.q_rest_rad) + rest_offset),
        passive_stiffness_nm_rad=tuple(
            np.asarray(nominal.passive_stiffness_nm_rad) * stiffness_scale
        ),
        passive_damping_nms_rad=nominal.passive_damping_nms_rad,
        q_min_rad=nominal.q_min_rad,
        q_max_rad=nominal.q_max_rad,
        soft_limit_margin_rad=nominal.soft_limit_margin_rad,
        soft_limit_numerical_tolerance_rad=nominal.soft_limit_numerical_tolerance_rad,
        soft_limit_boundary_torque_nm=nominal.soft_limit_boundary_torque_nm,
        soft_limit_damping_nms_rad=nominal.soft_limit_damping_nms_rad,
        thigh_com_scale=float(values.get("thigh_com_scale", 1.0)),
        shank_com_scale=float(values.get("shank_com_scale", 1.0)),
        sleeve_center_scale=float(values.get("sleeve_center_scale", 1.0)),
    )


def registered_moderate_human() -> tuple[ScaledHumanV2, dict[str, object]]:
    """Stage-2 registered ``moderate`` mismatch, copied without importing Stage 2."""

    human = ScaledHumanV2(
        body_mass_kg=HUMAN.body_mass_kg * 1.05,
        q_rest_rad=tuple(np.asarray(HUMAN.q_rest_rad) + np.radians([-2.0, -2.0])),
        passive_stiffness_nm_rad=tuple(np.asarray(HUMAN.passive_stiffness_nm_rad) * 1.10),
        thigh_com_scale=1.05,
        shank_com_scale=0.95,
        sleeve_center_scale=1.02,
    )
    return human, {
        "case": "moderate",
        "mass_scale": 1.05,
        "thigh_com_scale": 1.05,
        "shank_com_scale": 0.95,
        "stiffness_scale": 1.10,
        "rest_offset_deg": [-2.0, -2.0],
        "sleeve_center_scale": 1.02,
    }


def registered_cold_start_perturbed_human() -> tuple[ScaledHumanV2, dict[str, object]]:
    """Single registered geometry/dynamics perturbation for cold-start validation."""

    human = ScaledHumanV2(
        height_m=HUMAN.height_m * 1.06,
        body_mass_kg=HUMAN.body_mass_kg * 1.08,
        q_rest_rad=tuple(np.asarray(HUMAN.q_rest_rad) + np.radians([-2.0, 3.0])),
        passive_stiffness_nm_rad=tuple(
            np.asarray(HUMAN.passive_stiffness_nm_rad) * 1.15
        ),
        thigh_com_scale=1.04,
        shank_com_scale=0.96,
        sleeve_center_scale=0.94,
    )
    return human, {
        "case": "cold_start_perturbed",
        "height_scale": 1.06,
        "mass_scale": 1.08,
        "thigh_com_scale": 1.04,
        "shank_com_scale": 0.96,
        "stiffness_scale": 1.15,
        "rest_offset_deg": [-2.0, 3.0],
        "sleeve_center_scale": 0.94,
    }


def dynamic_terms(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    human: HumanV2Parameters,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
            -human.shank_mass_kg * human.gravity_m_s2 * human.shank_com_m * math.cos(phi),
        ]
    )
    passive = (
        np.asarray(human.passive_stiffness_nm_rad)
        * (q - np.asarray(human.q_rest_rad))
        + np.asarray(human.passive_damping_nms_rad) * dq
        - soft_limit_torque(q, dq, human)
    )
    return mass_matrix(q, human), coriolis, gravity, passive


def inverse_dynamics(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    qdd_rad_s2: np.ndarray,
    human: HumanV2Parameters,
) -> np.ndarray:
    mass, coriolis, gravity, passive = dynamic_terms(q_rad, dq_rad_s, human)
    return mass @ np.asarray(qdd_rad_s2, dtype=float) + coriolis + gravity + passive


def continuous_dynamics(
    state: np.ndarray,
    generalized_action_nm: np.ndarray,
    human: HumanV2Parameters,
) -> np.ndarray:
    x = np.asarray(state, dtype=float)
    q, dq = x[:2], x[2:]
    mass, coriolis, gravity, passive = dynamic_terms(q, dq, human)
    qdd = np.linalg.solve(
        mass,
        np.asarray(generalized_action_nm, dtype=float) - coriolis - gravity - passive,
    )
    return np.concatenate([dq, qdd])


def step_dynamics(
    state: np.ndarray,
    generalized_action_nm: np.ndarray,
    dt_s: float,
    human: HumanV2Parameters,
) -> np.ndarray:
    """One fixed-action RK4 transition for estimator and MPC prediction."""

    x = np.asarray(state, dtype=float)
    u = np.asarray(generalized_action_nm, dtype=float)
    dt = float(dt_s)
    k1 = continuous_dynamics(x, u, human)
    k2 = continuous_dynamics(x + 0.5 * dt * k1, u, human)
    k3 = continuous_dynamics(x + 0.5 * dt * k2, u, human)
    k4 = continuous_dynamics(x + dt * k3, u, human)
    return x + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def allocate_generalized_action(
    generalized_action_nm: np.ndarray,
    q_rad: np.ndarray,
    human: HumanV2Parameters,
) -> dict[str, np.ndarray | float]:
    """Minimum-translational-force rigid-cuff allocation with free sagittal moment."""

    torque = np.asarray(generalized_action_nm, dtype=float)
    force_map = sleeve_jacobian(q_rad, human)[[0, 2], :].T
    moment_map = np.array([1.0, -1.0])
    moment_orthogonal = np.array([1.0, 1.0]) / math.sqrt(2.0)
    projected_force_map = force_map.T @ moment_orthogonal
    denominator = float(projected_force_map @ projected_force_map)
    if denominator <= 1e-18:
        raise RuntimeError("rigid cuff allocation is singular")
    force_xz = projected_force_map * float(moment_orthogonal @ torque) / denominator
    my_nm = float(moment_map @ (torque - force_map @ force_xz) / (moment_map @ moment_map))
    residual = float(np.linalg.norm(force_map @ force_xz + moment_map * my_nm - torque))
    return {
        "force_xz_n": force_xz,
        "force_norm_n": float(np.linalg.norm(force_xz)),
        "my_nm": my_nm,
        "wrench_world": np.array([force_xz[0], 0.0, force_xz[1], 0.0, -my_nm, 0.0]),
        "allocation_residual_nm": residual,
    }
