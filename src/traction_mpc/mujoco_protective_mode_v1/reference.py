"""Human V2 reference and C2 boundary-polynomial utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class ReferenceSample:
    q: np.ndarray
    dq: np.ndarray
    ddq: np.ndarray


def quintic_progress(value: float) -> tuple[float, float, float]:
    """Return s, ds/dr, and d2s/dr2 for the standard minimum-jerk blend."""

    r = float(np.clip(value, 0.0, 1.0))
    s = 10 * r**3 - 15 * r**4 + 6 * r**5
    ds = 30 * r**2 - 60 * r**3 + 30 * r**4
    dds = 60 * r - 180 * r**2 + 120 * r**3
    return s, ds, dds


def human_v2_reference(time_s: float) -> ReferenceSample:
    """Exact Python transcription of slow_passive_flexion_v2."""

    q_start = np.radians([5.0, 10.0])
    q_peak = np.radians([45.0, 84.0])
    delta = q_peak - q_start
    if time_s < 1.0:
        alpha = dalpha = ddalpha = 0.0
    elif time_s < 7.5:
        s, ds, dds = quintic_progress((time_s - 1.0) / 6.5)
        alpha, dalpha, ddalpha = s, ds / 6.5, dds / 6.5**2
    elif time_s < 8.5:
        alpha, dalpha, ddalpha = 1.0, 0.0, 0.0
    elif time_s < 15.0:
        s, ds, dds = quintic_progress((time_s - 8.5) / 6.5)
        alpha, dalpha, ddalpha = 1 - s, -ds / 6.5, -dds / 6.5**2
    else:
        alpha = dalpha = ddalpha = 0.0
    return ReferenceSample(
        q=q_start + delta * alpha,
        dq=delta * dalpha,
        ddq=delta * ddalpha,
    )


def coordinated_posture(q2_rad: float) -> np.ndarray:
    """Continue the taught q1/q2 coordination line into near extension."""

    q1 = math.radians(5) + (q2_rad - math.radians(10)) * 40.0 / 74.0
    return np.array([q1, q2_rad], dtype=float)


def reference_crossing_time(q_switch_rad: float, returning: bool) -> float:
    """Find the taught-trajectory crossing without a SciPy dependency."""

    lower, upper = ((8.5, 15.0) if returning else (1.0, 7.5))
    for _ in range(80):
        middle = 0.5 * (lower + upper)
        q2 = human_v2_reference(middle).q[1]
        if returning:
            if q2 > q_switch_rad:
                lower = middle
            else:
                upper = middle
        elif q2 < q_switch_rad:
            lower = middle
        else:
            upper = middle
    return 0.5 * (lower + upper)


class QuinticBoundary:
    """Vector C2 quintic satisfying position, velocity, acceleration endpoints."""

    def __init__(
        self,
        duration_s: float,
        x0: np.ndarray,
        dx0: np.ndarray,
        ddx0: np.ndarray,
        xf: np.ndarray,
        dxf: np.ndarray,
        ddxf: np.ndarray,
    ) -> None:
        self.duration_s = float(duration_s)
        if self.duration_s <= 0:
            raise ValueError("duration_s must be positive")
        x0, dx0, ddx0 = (np.asarray(value, dtype=float) for value in (x0, dx0, ddx0))
        xf, dxf, ddxf = (np.asarray(value, dtype=float) for value in (xf, dxf, ddxf))
        t = self.duration_s
        a0, a1, a2 = x0, dx0, ddx0 / 2
        matrix = np.array(
            [[t**3, t**4, t**5], [3 * t**2, 4 * t**3, 5 * t**4], [6 * t, 12 * t**2, 20 * t**3]],
            dtype=float,
        )
        rhs = np.stack(
            [xf - a0 - a1 * t - a2 * t**2, dxf - a1 - 2 * a2 * t, ddxf - 2 * a2]
        )
        tail = np.linalg.solve(matrix, rhs)
        self.coefficients = np.stack([a0, a1, a2, tail[0], tail[1], tail[2]])

    def sample(self, time_s: float) -> ReferenceSample:
        t = float(np.clip(time_s, 0.0, self.duration_s))
        a = self.coefficients
        x = a[0] + a[1] * t + a[2] * t**2 + a[3] * t**3 + a[4] * t**4 + a[5] * t**5
        dx = a[1] + 2 * a[2] * t + 3 * a[3] * t**2 + 4 * a[4] * t**3 + 5 * a[5] * t**4
        ddx = 2 * a[2] + 6 * a[3] * t + 12 * a[4] * t**2 + 20 * a[5] * t**3
        return ReferenceSample(x, dx, ddx)
