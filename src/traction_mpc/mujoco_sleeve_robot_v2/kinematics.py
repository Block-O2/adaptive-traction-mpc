"""Human V2 posture and trajectory utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .config import HumanV2Parameters, PlantV2Config


@dataclass(frozen=True)
class ReferenceSample:
    q: np.ndarray
    dq: np.ndarray
    ddq: np.ndarray


def quintic_boundary_sample(
    time_s: float,
    duration_s: float,
    q0: np.ndarray,
    dq0: np.ndarray,
    qf: np.ndarray,
    dqf: np.ndarray | None = None,
) -> ReferenceSample:
    """C2 trajectory matching measured initial position and velocity."""

    if duration_s <= 0.0:
        raise ValueError("duration_s must be positive")
    q0 = np.asarray(q0, dtype=float)
    dq0 = np.asarray(dq0, dtype=float)
    qf = np.asarray(qf, dtype=float)
    dqf = np.zeros_like(q0) if dqf is None else np.asarray(dqf, dtype=float)
    elapsed = float(np.clip(time_s, 0.0, duration_s))
    matrix = np.array(
        [
            [duration_s**3, duration_s**4, duration_s**5],
            [3 * duration_s**2, 4 * duration_s**3, 5 * duration_s**4],
            [6 * duration_s, 12 * duration_s**2, 20 * duration_s**3],
        ]
    )
    rhs = np.vstack(
        [
            qf - q0 - dq0 * duration_s,
            dqf - dq0,
            np.zeros_like(q0),
        ]
    )
    coefficients = np.linalg.solve(matrix, rhs).T
    powers = np.array([elapsed**3, elapsed**4, elapsed**5])
    velocity_powers = np.array([3 * elapsed**2, 4 * elapsed**3, 5 * elapsed**4])
    acceleration_powers = np.array([6 * elapsed, 12 * elapsed**2, 20 * elapsed**3])
    return ReferenceSample(
        q=q0 + dq0 * elapsed + coefficients @ powers,
        dq=dq0 + coefficients @ velocity_powers,
        ddq=coefficients @ acceleration_powers,
    )


def quintic_progress(value: float) -> tuple[float, float, float]:
    r = float(np.clip(value, 0.0, 1.0))
    return (
        10 * r**3 - 15 * r**4 + 6 * r**5,
        30 * r**2 - 60 * r**3 + 30 * r**4,
        60 * r - 180 * r**2 + 120 * r**3,
    )


def coordinated_posture(q2_rad: float) -> np.ndarray:
    q1 = math.radians(5.0) + (q2_rad - math.radians(10.0)) * 40.0 / 74.0
    return np.array([q1, q2_rad], dtype=float)


def human_reference(time_s: float) -> ReferenceSample:
    start = np.radians([5.0, 10.0])
    peak = np.radians([45.0, 84.0])
    delta = peak - start
    if time_s < 1.0:
        alpha = dalpha = ddalpha = 0.0
    elif time_s < 7.5:
        s, ds, dds = quintic_progress((time_s - 1.0) / 6.5)
        alpha, dalpha, ddalpha = s, ds / 6.5, dds / 6.5**2
    elif time_s < 8.5:
        alpha, dalpha, ddalpha = 1.0, 0.0, 0.0
    elif time_s < 15.0:
        s, ds, dds = quintic_progress((time_s - 8.5) / 6.5)
        alpha, dalpha, ddalpha = 1.0 - s, -ds / 6.5, -dds / 6.5**2
    else:
        alpha = dalpha = ddalpha = 0.0
    return ReferenceSample(start + delta * alpha, delta * dalpha, delta * ddalpha)


def sleeve_position(
    q_rad: np.ndarray,
    human: HumanV2Parameters,
    config: PlantV2Config,
) -> np.ndarray:
    q1, q2 = q_rad
    phi = q1 - q2
    return np.array(
        [
            human.thigh_length_m * math.cos(q1)
            + human.sleeve_center_m * math.cos(phi),
            0.0,
            config.hip_height_m
            + human.thigh_length_m * math.sin(q1)
            + human.sleeve_center_m * math.sin(phi),
        ]
    )


def sleeve_jacobian(
    q_rad: np.ndarray,
    human: HumanV2Parameters,
) -> np.ndarray:
    q1, q2 = q_rad
    phi = q1 - q2
    l1, sc = human.thigh_length_m, human.sleeve_center_m
    return np.array(
        [
            [-l1 * math.sin(q1) - sc * math.sin(phi), sc * math.sin(phi)],
            [0.0, 0.0],
            [l1 * math.cos(q1) + sc * math.cos(phi), -sc * math.cos(phi)],
        ]
    )


def coordinated_sleeve_direction(
    q2_deg: float,
    human: HumanV2Parameters,
    config: PlantV2Config,
) -> np.ndarray:
    epsilon = math.radians(0.01)
    before = sleeve_position(coordinated_posture(math.radians(q2_deg) - epsilon), human, config)
    after = sleeve_position(coordinated_posture(math.radians(q2_deg) + epsilon), human, config)
    direction = after - before
    return direction / np.linalg.norm(direction)
