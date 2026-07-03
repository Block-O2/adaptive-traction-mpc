"""Shared dataclasses for traction MPC environments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Spring2DState:
    """State for the 2D polar spring-rod model."""

    theta: float
    omega: float
    r: float
    r_dot: float

    def as_array(self) -> np.ndarray:
        return np.array([self.theta, self.omega, self.r, self.r_dot], dtype=float)

    @classmethod
    def from_array(cls, values: np.ndarray | list[float] | tuple[float, ...]) -> "Spring2DState":
        raw = np.asarray(values, dtype=float)
        if raw.shape != (4,):
            raise ValueError("Spring2D state must have shape (4,) as [theta, omega, r, r_dot].")
        theta, omega, r, r_dot = raw
        return cls(float(theta), float(omega), float(r), float(r_dot))


@dataclass
class Spring2DAction:
    """Tangential and radial force command for the 2D spring-rod model."""

    F_tan: float
    F_rad: float

    def as_array(self) -> np.ndarray:
        return np.array([self.F_tan, self.F_rad], dtype=float)

    @classmethod
    def from_array(cls, values: np.ndarray | list[float] | tuple[float, ...]) -> "Spring2DAction":
        raw = np.asarray(values, dtype=float)
        if raw.shape != (2,):
            raise ValueError("Spring2D action must have shape (2,) as [F_tan, F_rad].")
        F_tan, F_rad = raw
        return cls(float(F_tan), float(F_rad))


@dataclass
class Spring2DObservation:
    """Observation returned by Spring2DEnv."""

    t: float
    theta: float
    omega: float
    r: float
    r_dot: float
    delta_r: float
    base_pos: np.ndarray
    tip_pos: np.ndarray
    contact_pos: np.ndarray
    contact_vel: np.ndarray
    F_tan: float
    F_rad: float
    r_ddot: float
    omega_dot: float
    base_x: float
    base_a: float
    base_ap: float
    done: bool
    done_reason: str | None
    physical_info: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "theta": self.theta,
            "omega": self.omega,
            "r": self.r,
            "r_dot": self.r_dot,
            "delta_r": self.delta_r,
            "base_pos": self.base_pos,
            "tip_pos": self.tip_pos,
            "contact_pos": self.contact_pos,
            "contact_vel": self.contact_vel,
            "F_tan": self.F_tan,
            "F_rad": self.F_rad,
            "r_ddot": self.r_ddot,
            "omega_dot": self.omega_dot,
            "base_x": self.base_x,
            "base_a": self.base_a,
            "base_ap": self.base_ap,
            "done": self.done,
            "done_reason": self.done_reason,
            "physical_info": self.physical_info,
        }
