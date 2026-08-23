"""Source-faithful port of the retained MATLAB normal force controller.

The equations and registered values in this module mirror
``bed_supported_v1_robot_controller.m`` and its retained dependencies.  The
port exists only so that the unchanged law can run inside a 2 ms MuJoCo loop;
it is not a new low-angle controller.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .config import HumanV2Parameters
from .kinematics import ReferenceSample, human_reference


@dataclass(frozen=True)
class NormalControllerConfig:
    dt_s: float = 0.002
    kp: tuple[float, float] = (180.0, 140.0)
    kd: tuple[float, float] = (28.0, 22.0)
    force_bound_n: float = 200.0
    force_slew_n_s: float = 250.0
    tau_scale_nm: float = 50.0
    force_scale_n: float = 400.0
    du_scale_n_s: float = 500.0
    lambda_ref: float = 1e-6
    lambda_du: float = 0.0
    svd_relative_tolerance: float = 1e-12
    residual_tolerance_nm: float = 1e-8
    bound_tolerance_n: float = 1e-8
    source_function: str = (
        "linkage/matlab/src/bed_supported_load_transfer_v1/"
        "bed_supported_v1_robot_controller.m"
    )


@dataclass(frozen=True)
class NormalControllerOutput:
    local_force_n: np.ndarray
    desired_unbounded_force_n: np.ndarray
    desired_robot_torque_nm: np.ndarray
    torque_residual_nm: np.ndarray
    force_saturated: bool
    slew_saturated: bool
    mapping_condition_number: float
    mapping_sigma_min: float
    soft_limit_active: np.ndarray


def _soft_limit_rhs(
    q: np.ndarray, dq: np.ndarray, human: HumanV2Parameters
) -> tuple[np.ndarray, np.ndarray]:
    margin = math.radians(5.0)
    tolerance = 1e-9
    lower = np.asarray(human.q_min_rad) + margin - tolerance
    upper = np.asarray(human.q_max_rad) - margin + tolerance
    torque = np.zeros(2)
    active = np.zeros(2, dtype=bool)
    for index in range(2):
        if q[index] < lower[index]:
            z = (lower[index] - q[index]) / margin
            torque[index] = 25.0 * z**3 + 2.0 * z**2 * max(-dq[index], 0.0)
            active[index] = True
        elif q[index] > upper[index]:
            z = (q[index] - upper[index]) / margin
            torque[index] = -(25.0 * z**3 + 2.0 * z**2 * max(dq[index], 0.0))
            active[index] = True
    return torque, active


def _passive_left(
    q: np.ndarray, dq: np.ndarray, human: HumanV2Parameters
) -> tuple[np.ndarray, np.ndarray]:
    soft_rhs, active = _soft_limit_rhs(q, dq, human)
    spring = np.asarray(human.passive_stiffness_nm_rad) * (
        q - np.asarray(human.q_rest_rad)
    )
    damping = np.asarray(human.passive_damping_nms_rad) * dq
    return spring + damping - soft_rhs, active


def _dynamics_terms(
    q: np.ndarray, dq: np.ndarray, human: HumanV2Parameters
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    q1, q2 = q
    dq1, dq2 = dq
    phi = q1 - q2
    b = human.shank_inertia_kg_m2 + human.shank_mass_kg * human.shank_com_m**2
    d = human.shank_mass_kg * human.thigh_length_m * human.shank_com_m
    a = (
        human.thigh_inertia_kg_m2
        + human.thigh_mass_kg * human.thigh_com_m**2
        + b
        + human.shank_mass_kg * human.thigh_length_m**2
    )
    mass = np.array(
        [
            [a + 2.0 * d * math.cos(q2), -(b + d * math.cos(q2))],
            [-(b + d * math.cos(q2)), b],
        ]
    )
    nonlinear = np.array(
        [
            d * math.sin(q2) * (-2.0 * dq1 * dq2 + dq2**2),
            d * math.sin(q2) * dq1**2,
        ]
    )
    gravity = np.array(
        [
            human.gravity_m_s2
            * (
                (
                    human.thigh_mass_kg * human.thigh_com_m
                    + human.shank_mass_kg * human.thigh_length_m
                )
                * math.cos(q1)
                + human.shank_mass_kg * human.shank_com_m * math.cos(phi)
            ),
            -human.shank_mass_kg
            * human.gravity_m_s2
            * human.shank_com_m
            * math.cos(phi),
        ]
    )
    return mass, nonlinear, gravity


def local_force_mapping(q: np.ndarray, human: HumanV2Parameters) -> np.ndarray:
    """Return the retained tangent/normal force-to-human-torque map."""

    q2 = float(q[1])
    return np.array(
        [
            [
                -human.thigh_length_m * math.sin(q2),
                human.thigh_length_m * math.cos(q2) + human.sleeve_center_m,
            ],
            [0.0, -human.sleeve_center_m],
        ]
    )


def local_force_rotation(q: np.ndarray) -> np.ndarray:
    """Map retained [tangent, normal] force into world [x, y, z]."""

    phi = float(q[0] - q[1])
    return np.array(
        [
            [math.cos(phi), -math.sin(phi)],
            [0.0, 0.0],
            [math.sin(phi), math.cos(phi)],
        ]
    )


def _stable_force_solve(
    mapping: np.ndarray, torque: np.ndarray, relative_tolerance: float
) -> tuple[np.ndarray, float, float]:
    left, singular_values, right_transpose = np.linalg.svd(mapping, full_matrices=False)
    threshold = relative_tolerance * max(1.0, float(singular_values[0]))
    inverse = np.zeros_like(singular_values)
    retained = singular_values > threshold
    inverse[retained] = 1.0 / singular_values[retained]
    force = right_transpose.T @ (inverse * (left.T @ torque))
    condition = (
        float(singular_values[0] / singular_values[-1])
        if singular_values[-1] > 0.0
        else math.inf
    )
    return force, condition, float(singular_values[-1])


def _solve_box_qp(
    hessian: np.ndarray,
    linear: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    statuses = np.array(
        [
            [0, 0],
            [-1, 0],
            [1, 0],
            [0, -1],
            [0, 1],
            [-1, -1],
            [-1, 1],
            [1, -1],
            [1, 1],
        ]
    )
    best_value = math.inf
    best = None
    tolerance = 1e-11
    for status in statuses:
        candidate = np.zeros(2)
        fixed = status != 0
        free = ~fixed
        candidate[status == -1] = lower[status == -1]
        candidate[status == 1] = upper[status == 1]
        if np.any(free):
            rhs = linear[free] + hessian[np.ix_(free, fixed)] @ candidate[fixed]
            candidate[free] = -np.linalg.solve(hessian[np.ix_(free, free)], rhs)
        if np.any(candidate < lower - tolerance) or np.any(candidate > upper + tolerance):
            continue
        candidate = np.minimum(np.maximum(candidate, lower), upper)
        value = float(candidate @ hessian @ candidate + 2.0 * linear @ candidate)
        if value < best_value - tolerance:
            best_value = value
            best = candidate.copy()
    if best is None:
        raise RuntimeError("retained two-dimensional box QP found no candidate")
    return best


def original_normal_controller(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    reference: ReferenceSample,
    bed_generalized_torque_nm: np.ndarray,
    previous_local_force_n: np.ndarray,
    human: HumanV2Parameters,
    config: NormalControllerConfig | None = None,
) -> NormalControllerOutput:
    """Evaluate the unchanged retained normal force-control law."""

    cfg = config or NormalControllerConfig()
    q = np.asarray(q_rad, dtype=float)
    dq = np.asarray(dq_rad_s, dtype=float)
    previous = np.asarray(previous_local_force_n, dtype=float)
    mass, nonlinear, gravity = _dynamics_terms(q, dq, human)
    passive_dynamic, soft_active = _passive_left(q, dq, human)
    feedback = -np.asarray(cfg.kp) * (q - reference.q)
    feedback -= np.asarray(cfg.kd) * (dq - reference.dq)
    total_desired = (
        gravity
        + passive_dynamic
        + mass @ reference.ddq
        + nonlinear
        + mass @ feedback
    )
    robot_desired = total_desired - np.asarray(bed_generalized_torque_nm)
    mapping = local_force_mapping(q, human)
    desired_force, condition, sigma_min = _stable_force_solve(
        mapping, robot_desired, cfg.svd_relative_tolerance
    )

    slew_step = cfg.force_slew_n_s * cfg.dt_s
    lower = np.maximum(-cfg.force_bound_n, previous - slew_step)
    upper = np.minimum(cfg.force_bound_n, previous + slew_step)
    scaled_mapping = mapping / cfg.tau_scale_nm
    scaled_torque = robot_desired / cfg.tau_scale_nm
    reference_weight = cfg.lambda_ref / cfg.force_scale_n**2
    du_denominator = cfg.du_scale_n_s * cfg.dt_s
    du_weight = cfg.lambda_du / du_denominator**2
    hessian = scaled_mapping.T @ scaled_mapping
    hessian += (reference_weight + du_weight) * np.eye(2)
    linear = -scaled_mapping.T @ scaled_torque
    linear -= reference_weight * desired_force + du_weight * previous
    force = _solve_box_qp(hessian, linear, lower, upper)
    residual = mapping @ force - robot_desired
    tolerance = cfg.bound_tolerance_n
    return NormalControllerOutput(
        local_force_n=force,
        desired_unbounded_force_n=desired_force,
        desired_robot_torque_nm=robot_desired,
        torque_residual_nm=residual,
        force_saturated=bool(
            np.any(np.abs(force + cfg.force_bound_n) <= tolerance)
            or np.any(np.abs(force - cfg.force_bound_n) <= tolerance)
        ),
        slew_saturated=bool(
            np.any(np.abs(force - lower) <= tolerance)
            or np.any(np.abs(force - upper) <= tolerance)
        ),
        mapping_condition_number=condition,
        mapping_sigma_min=sigma_min,
        soft_limit_active=soft_active,
    )


def taught_reference_time_for_q2(q2_deg: float) -> float:
    """Return the outbound taught-trajectory time at or above a candidate."""

    if q2_deg <= 10.0:
        return 1.0
    if q2_deg > 84.0:
        raise ValueError("q2 is outside the outbound taught trajectory")
    lower, upper = 1.0, 7.5
    for _ in range(80):
        midpoint = 0.5 * (lower + upper)
        if math.degrees(human_reference(midpoint).q[1]) < q2_deg:
            lower = midpoint
        else:
            upper = midpoint
    return 0.5 * (lower + upper)
