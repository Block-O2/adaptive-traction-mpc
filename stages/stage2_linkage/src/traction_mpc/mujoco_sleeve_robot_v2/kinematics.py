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


def human_reference(
    time_s: float, start_q_rad: np.ndarray | None = None
) -> ReferenceSample:
    start = (
        np.radians([5.0, 10.0])
        if start_q_rad is None
        else np.asarray(start_q_rad, dtype=float)
    )
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


def sleeve_rotation_matrix(q_rad: np.ndarray) -> np.ndarray:
    """Return the shank/cuff frame orientation in world coordinates."""

    q1, q2 = q_rad
    angle = q2 - q1
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [
            [cosine, 0.0, sine],
            [0.0, 1.0, 0.0],
            [-sine, 0.0, cosine],
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
