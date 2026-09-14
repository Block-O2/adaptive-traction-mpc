"""Observation-only hooks for a future Stage-5 exploration supervisor.

No threshold, state transition, action rejection, or controller is implemented
here. The contract only prevents future exploration code from omitting the
requested physical signals and existing execution-layer status.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ExplorationSafetyObservation:
    physical_cuff_force_n: np.ndarray
    physical_cuff_force_slew_n_s: np.ndarray
    interface_deformation_m: np.ndarray
    cuff_position_error_m: np.ndarray
    cuff_rotation_error_rad: np.ndarray
    executable_screening_status: str
    safety_filter_status: str
    brake_status: str

    def __post_init__(self) -> None:
        for name in (
            "physical_cuff_force_n",
            "physical_cuff_force_slew_n_s",
            "interface_deformation_m",
            "cuff_position_error_m",
            "cuff_rotation_error_rad",
        ):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (3,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be a finite three-vector")
            object.__setattr__(self, name, value.copy())
        for name in (
            "executable_screening_status",
            "safety_filter_status",
            "brake_status",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} must be non-empty")
