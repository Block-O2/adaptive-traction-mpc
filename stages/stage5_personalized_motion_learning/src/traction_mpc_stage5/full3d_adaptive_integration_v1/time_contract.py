"""Timestamp and integration-interval contract for corrected evaluation.

Historical architecture-recovery artifacts remain immutable.  This module is
the V1 correction boundary used by new full-3D work and corrected replications.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class BoundaryTimeGrid:
    """Exact boundary samples and half-open integration intervals."""

    boundary_times_s: np.ndarray
    interval_durations_s: np.ndarray

    def __post_init__(self) -> None:
        boundaries = np.asarray(self.boundary_times_s, dtype=float)
        durations = np.asarray(self.interval_durations_s, dtype=float)
        if boundaries.ndim != 1 or durations.ndim != 1:
            raise ValueError("time grid arrays must be one-dimensional")
        if len(boundaries) != len(durations) + 1:
            raise ValueError("N intervals require N+1 boundary timestamps")
        if len(boundaries) < 2 or boundaries[0] != 0.0:
            raise ValueError("time grid must start at zero and contain an interval")
        if not np.all(np.isfinite(boundaries)) or not np.all(np.isfinite(durations)):
            raise ValueError("time grid must be finite")
        if np.any(durations <= 0.0) or np.any(np.diff(boundaries) <= 0.0):
            raise ValueError("time grid must be strictly increasing")
        if not np.allclose(np.diff(boundaries), durations, atol=1.0e-15, rtol=0.0):
            raise ValueError("interval durations must match boundary differences")
        object.__setattr__(self, "boundary_times_s", boundaries.copy())
        object.__setattr__(self, "interval_durations_s", durations.copy())

    @property
    def duration_s(self) -> float:
        return float(self.boundary_times_s[-1])

    @property
    def interval_count(self) -> int:
        return len(self.interval_durations_s)


def build_boundary_time_grid(duration_s: float, nominal_dt_s: float) -> BoundaryTimeGrid:
    """Return exact `[0,duration]` boundaries without an endpoint-only step."""

    if not math.isfinite(duration_s) or duration_s <= 0.0:
        raise ValueError("duration_s must be finite and positive")
    if not math.isfinite(nominal_dt_s) or nominal_dt_s <= 0.0:
        raise ValueError("nominal_dt_s must be finite and positive")
    interval_count = int(math.ceil(duration_s / nominal_dt_s - 1.0e-14))
    starts = nominal_dt_s * np.arange(interval_count, dtype=float)
    boundaries = np.concatenate([starts, np.array([duration_s])])
    boundaries[0] = 0.0
    durations = np.diff(boundaries)
    return BoundaryTimeGrid(boundaries, durations)


def integrate_interval_cost(
    interval_values: Iterable[float], interval_durations_s: Iterable[float]
) -> float:
    """Piecewise-constant interval integral with actual interval durations."""

    values = np.asarray(tuple(interval_values), dtype=float)
    durations = np.asarray(tuple(interval_durations_s), dtype=float)
    if values.ndim != 1 or durations.ndim != 1 or values.shape != durations.shape:
        raise ValueError("interval values and durations must be equal-length vectors")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(durations)):
        raise ValueError("interval cost inputs must be finite")
    if np.any(durations <= 0.0):
        raise ValueError("interval durations must be positive")
    return float(values @ durations)


def known_motion_alignment_diagnostic(
    *, speed_rad_s: float, duration_s: float, dt_s: float
) -> dict[str, float | int]:
    """Expose the historical post-state/pre-reference one-step error exactly."""

    grid = build_boundary_time_grid(duration_s, dt_s)
    true_at_boundaries = speed_rad_s * grid.boundary_times_s
    reference_at_boundaries = speed_rad_s * grid.boundary_times_s
    corrected_error = true_at_boundaries - reference_at_boundaries
    historical_error = true_at_boundaries[1:] - reference_at_boundaries[:-1]
    return {
        "interval_count": grid.interval_count,
        "boundary_sample_count": len(grid.boundary_times_s),
        "corrected_rmse_rad": float(np.sqrt(np.mean(corrected_error**2))),
        "historical_rmse_rad": float(np.sqrt(np.mean(historical_error**2))),
        "historical_first_error_rad": float(historical_error[0]),
        "historical_last_error_rad": float(historical_error[-1]),
    }
