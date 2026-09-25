"""Threshold-free ranking plan for shadow-only near-limit data collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


NEAR_LIMIT_SHADOW_VERSION = "near_limit_shadow_trigger_v1"


@dataclass(frozen=True)
class NearLimitShadowTarget:
    """One replay target selected only by rank below the existing boundary."""

    timestamp_s: float
    task_phase: str
    mpc_cycle_offset: int
    boundary_proximity: float
    normalized_joint_acceleration: tuple[float, float]
    source_trace: str

    def __post_init__(self) -> None:
        if not np.isfinite(self.timestamp_s) or self.timestamp_s < 0.0:
            raise ValueError("near-limit target timestamp is invalid")
        if not self.task_phase or self.task_phase in {"ABORTED", "COMPLETE"}:
            raise ValueError("near-limit target must be a nonterminal task state")
        if self.mpc_cycle_offset < 0:
            raise ValueError("near-limit target cycle offset is invalid")
        normalized = np.asarray(self.normalized_joint_acceleration, dtype=float)
        if normalized.shape != (2,) or not np.all(np.isfinite(normalized)):
            raise ValueError("normalized acceleration must be a finite two-vector")
        if np.any(normalized < 0.0) or np.any(normalized >= 1.0):
            raise ValueError("near-limit target must remain below existing authority")
        if not np.isclose(self.boundary_proximity, np.max(normalized)):
            raise ValueError("boundary proximity must equal the largest joint ratio")
        if not self.source_trace:
            raise ValueError("near-limit target requires a source trace")

    def record(self) -> dict[str, Any]:
        return {
            "timestamp_s": self.timestamp_s,
            "task_phase": self.task_phase,
            "mpc_cycle_offset": self.mpc_cycle_offset,
            "boundary_proximity": self.boundary_proximity,
            "normalized_joint_acceleration": list(
                self.normalized_joint_acceleration
            ),
            "source_trace": self.source_trace,
            "selection": (
                "highest ranked nonterminal sample below the existing registered "
                "joint acceleration boundary in this task-phase/cycle-offset context"
            ),
            "new_numeric_threshold": None,
            "control_authority": False,
        }


def select_near_limit_shadow_targets(
    *,
    time_s: Sequence[float],
    task_phase: Sequence[str],
    deployable_acceleration_rad_s2: Any,
    registered_limit_rad_s2: Sequence[float],
    high_level_steps: int,
    cycle_offsets: Sequence[int] = (2, 3),
    task_phases: Sequence[str] = ("OUTBOUND",),
    source_trace: str,
) -> tuple[NearLimitShadowTarget, ...]:
    """Rank, rather than threshold, non-abort samples within matched contexts."""

    time = np.asarray(time_s, dtype=float)
    phase = np.asarray(task_phase, dtype=str)
    acceleration = np.asarray(deployable_acceleration_rad_s2, dtype=float)
    limit = np.asarray(registered_limit_rad_s2, dtype=float)
    if time.ndim != 1 or phase.shape != time.shape:
        raise ValueError("time and task phase must be aligned one-dimensional arrays")
    if acceleration.shape != (len(time), 2):
        raise ValueError("deployable acceleration must align with time")
    if limit.shape != (2,) or np.any(limit <= 0.0) or not np.all(np.isfinite(limit)):
        raise ValueError("registered acceleration limit must be positive and finite")
    if high_level_steps < 1:
        raise ValueError("high-level scheduler period is invalid")
    offsets = tuple(dict.fromkeys(int(value) for value in cycle_offsets))
    if not offsets or any(value < 0 or value >= high_level_steps for value in offsets):
        raise ValueError("cycle offsets must lie inside the MPC period")
    selected_phases = tuple(dict.fromkeys(str(value) for value in task_phases))
    if not selected_phases or any(
        value in {"ABORTED", "COMPLETE"} or not value
        for value in selected_phases
    ):
        raise ValueError("task phases must be explicit nonterminal states")

    normalized = np.abs(acceleration) / limit
    finite = np.all(np.isfinite(normalized), axis=1)
    below_existing_boundary = np.all(normalized < 1.0, axis=1)
    nonterminal = ~np.isin(phase, ["ABORTED", "COMPLETE"])
    results = []
    for phase_name in selected_phases:
        for offset in offsets:
            indices = np.flatnonzero(
                finite
                & below_existing_boundary
                & nonterminal
                & (phase == phase_name)
                & (np.arange(len(time)) % high_level_steps == offset)
            )
            if not len(indices):
                continue
            proximity = np.max(normalized[indices], axis=1)
            selected = int(indices[int(np.argmax(proximity))])
            results.append(
                NearLimitShadowTarget(
                    timestamp_s=float(time[selected]),
                    task_phase=str(phase[selected]),
                    mpc_cycle_offset=offset,
                    boundary_proximity=float(np.max(normalized[selected])),
                    normalized_joint_acceleration=tuple(
                        float(value) for value in normalized[selected]
                    ),
                    source_trace=str(source_trace),
                )
            )
    return tuple(results)


__all__ = [
    "NEAR_LIMIT_SHADOW_VERSION",
    "NearLimitShadowTarget",
    "select_near_limit_shadow_targets",
]
