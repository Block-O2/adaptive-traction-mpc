"""Observation noise wrapper for Spring2D experiments."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation
from traction_mpc.models.spring2d_dynamics import compute_physical_info, compute_positions


class NoisySpring2DObservationWrapper:
    """Create noisy observations without modifying environment dynamics."""

    def __init__(self, params: dict[str, Any], cfg: dict[str, Any], seed: int = 0):
        self.params = dict(params)
        self.cfg = dict(cfg)
        self.rng = np.random.default_rng(seed)
        self.std = np.array(
            [
                float(cfg.get("theta_std", 0.0)),
                float(cfg.get("omega_std", 0.0)),
                float(cfg.get("r_std", 0.0)),
                float(cfg.get("r_dot_std", 0.0)),
            ],
            dtype=float,
        )
        self.bias = np.array(
            [
                float(cfg.get("theta_bias", 0.0)),
                float(cfg.get("omega_bias", 0.0)),
                float(cfg.get("r_bias", 0.0)),
                float(cfg.get("r_dot_bias", 0.0)),
            ],
            dtype=float,
        )

    def observe(self, obs: Spring2DObservation) -> Spring2DObservation:
        x = np.array([obs.theta, obs.omega, obs.r, obs.r_dot], dtype=float)
        noisy_x = x + self.bias + self.rng.normal(0.0, self.std)
        noisy_x[2] = max(noisy_x[2], 1.0e-6)
        positions = compute_positions(noisy_x, self.params)
        action = np.array([obs.F_tan, obs.F_rad], dtype=float)
        physical_info = compute_physical_info(noisy_x, action, self.params)
        return replace(
            obs,
            theta=float(noisy_x[0]),
            omega=float(noisy_x[1]),
            r=float(noisy_x[2]),
            r_dot=float(noisy_x[3]),
            delta_r=float(noisy_x[2] - float(self.params["L0"])),
            base_pos=positions["base_pos"],
            tip_pos=positions["tip_pos"],
            contact_pos=positions["contact_pos"],
            r_ddot=float(physical_info["r_ddot"]),
            omega_dot=float(physical_info["omega_dot"]),
            base_x=float(physical_info["base_x"]),
            base_a=float(physical_info["base_a"]),
            base_ap=float(physical_info["base_ap"]),
            physical_info=physical_info,
        )


def observation_to_state(obs: Spring2DObservation) -> np.ndarray:
    return np.array([obs.theta, obs.omega, obs.r, obs.r_dot], dtype=float)
