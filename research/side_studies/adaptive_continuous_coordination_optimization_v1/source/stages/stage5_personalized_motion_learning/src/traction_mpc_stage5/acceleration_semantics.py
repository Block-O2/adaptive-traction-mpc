"""Pure Stage-5 acceleration-envelope semantics shared by planning/tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PrefixAccelerationScreen:
    """Result of cumulative acceleration checks at causal prefix endpoints."""

    prefix_times_s: np.ndarray
    acceleration_rad_s2: np.ndarray
    margin_rad_s2: np.ndarray
    feasible: np.ndarray


def screen_cumulative_prefix_acceleration(
    initial_dq_rad_s: np.ndarray,
    prefix_dq_rad_s: np.ndarray,
    prefix_times_s: np.ndarray,
    limits_rad_s2: np.ndarray,
) -> PrefixAccelerationScreen:
    """Apply the registered ``abs(delta dq / delta t) <= limit`` contract.

    The last two axes of ``prefix_dq_rad_s`` are prefix and joint.  This pure
    calculation neither interpolates a 20 ms endpoint nor accepts truth-only
    state; the caller must supply causally predicted or measured velocities.
    """

    initial = np.asarray(initial_dq_rad_s, dtype=float)
    prefix = np.asarray(prefix_dq_rad_s, dtype=float)
    times = np.asarray(prefix_times_s, dtype=float)
    limits = np.asarray(limits_rad_s2, dtype=float)
    if initial.shape[-1:] != (2,) or prefix.shape[-1:] != (2,):
        raise ValueError("acceleration screening requires two Human joints")
    if prefix.ndim < 2 or prefix.shape[-2] != len(times):
        raise ValueError("prefix velocity/time dimensions do not match")
    if limits.shape != (2,) or np.any(limits <= 0.0):
        raise ValueError("registered acceleration limits must be a positive pair")
    if np.any(times <= 0.0) or np.any(np.diff(times) <= 0.0):
        raise ValueError("prefix times must be finite, positive, and increasing")
    if not all(
        np.all(np.isfinite(value)) for value in (initial, prefix, times, limits)
    ):
        raise ValueError("acceleration screening inputs must be finite")
    acceleration = (prefix - np.expand_dims(initial, axis=-2)) / times.reshape(
        (1,) * (prefix.ndim - 2) + (len(times), 1)
    )
    margin = limits - np.abs(acceleration)
    feasible = np.all(margin >= 0.0, axis=(-2, -1))
    return PrefixAccelerationScreen(
        prefix_times_s=times.copy(),
        acceleration_rad_s2=acceleration,
        margin_rad_s2=margin,
        feasible=np.asarray(feasible, dtype=bool),
    )


__all__ = ["PrefixAccelerationScreen", "screen_cumulative_prefix_acceleration"]
