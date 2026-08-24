"""Explicit port of the frozen Stage-2 cuff pose reference.

This module intentionally does not import either frozen ``traction_mpc``
package. Constants and equations are copied from Stage 2 at tag
``stage2-rigid-cuff-final`` (ecea294) and regression-tested against it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .frames import RigidTransform


HUMAN_HEIGHT_M = 1.72
THIGH_LENGTH_M = 0.254 * HUMAN_HEIGHT_M
SHANK_LENGTH_M = 0.233 * HUMAN_HEIGHT_M
SLEEVE_CENTER_M = 0.90 * SHANK_LENGTH_M
HIP_HEIGHT_M = 0.062
PEAK_Q_RAD = np.radians([45.0, 84.0])


@dataclass(frozen=True)
class CuffPoseReference:
    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    ddq_rad_s2: np.ndarray
    world_from_cuff: RigidTransform


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


def _joint_reference(time_s: float, lower_q2_deg: float) -> tuple[np.ndarray, ...]:
    start = coordinated_posture(math.radians(lower_q2_deg))
    delta = PEAK_Q_RAD - start
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
    return start + delta * alpha, delta * dalpha, delta * ddalpha


def _world_from_cuff(q_rad: np.ndarray) -> RigidTransform:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    position = np.array(
        [
            THIGH_LENGTH_M * math.cos(q1) + SLEEVE_CENTER_M * math.cos(phi),
            0.0,
            HIP_HEIGHT_M
            + THIGH_LENGTH_M * math.sin(q1)
            + SLEEVE_CENTER_M * math.sin(phi),
        ]
    )
    angle = q2 - q1
    cosine = math.cos(angle)
    sine = math.sin(angle)
    rotation = np.array(
        [
            [cosine, 0.0, sine],
            [0.0, 1.0, 0.0],
            [-sine, 0.0, cosine],
        ]
    )
    return RigidTransform(rotation, position)


def stage2_cuff_pose_reference(
    time_s: float,
    *,
    lower_q2_deg: float = 3.0,
) -> CuffPoseReference:
    q, dq, ddq = _joint_reference(float(time_s), float(lower_q2_deg))
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))
