"""Cost terms for fixed-model Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Spring2DMPCWeights:
    w_theta: float
    w_terminal_theta: float
    terminal_theta: float
    w_delta_r: float
    w_F_tan: float
    w_F_rad: float
    w_alpha: float
    w_omega_progress: float
    w_action_rate: float = 0.0
    w_F_tan_rate: float = 0.0
    w_F_rad_rate: float = 0.0

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Spring2DMPCWeights":
        # Deprecated compatibility: older configs used w_delta_omega.
        # The formal MPC task uses angular acceleration alpha.
        w_alpha = cfg.get("w_alpha", cfg.get("w_delta_omega", 50.0))
        return cls(
            w_theta=float(cfg.get("w_theta", 90.0)),
            w_terminal_theta=float(cfg.get("w_terminal_theta", 520.0)),
            terminal_theta=float(cfg.get("terminal_theta", 520.0)),
            w_delta_r=float(cfg.get("w_delta_r", 300.0)),
            w_F_tan=float(cfg.get("w_F_tan", 0.008)),
            w_F_rad=float(cfg.get("w_F_rad", 300.0)),
            w_alpha=float(w_alpha),
            w_omega_progress=float(cfg.get("w_omega_progress", 10.0)),
            w_action_rate=float(cfg.get("w_action_rate", 0.0)),
            w_F_tan_rate=float(cfg.get("w_F_tan_rate", 0.0)),
            w_F_rad_rate=float(cfg.get("w_F_rad_rate", 0.0)),
        )


def stage_cost(
    state: np.ndarray,
    action: np.ndarray,
    prev_omega: float,
    prediction_dt: float,
    target_theta: float,
    model_params: dict[str, Any],
    weights: Spring2DMPCWeights,
) -> float:
    theta, omega, r, _ = np.asarray(state, dtype=float)
    F_tan, F_rad = np.asarray(action, dtype=float)
    theta_error = theta - float(target_theta)
    delta_r = r - float(model_params["L0"])
    alpha = (omega - float(prev_omega)) / float(prediction_dt)
    return float(
        weights.w_theta * theta_error**2
        + weights.w_delta_r * delta_r**2
        + weights.w_F_tan * F_tan**2
        + weights.w_F_rad * F_rad**2
        + weights.w_alpha * alpha**2
        - weights.w_omega_progress * omega
    )


def action_rate_cost(
    action: np.ndarray,
    prev_action: np.ndarray,
    weights: Spring2DMPCWeights,
) -> float:
    """Optional diagnostic action-rate cost; default weights keep baseline unchanged."""

    du = np.asarray(action, dtype=float) - np.asarray(prev_action, dtype=float)
    return float(
        weights.w_action_rate * float(np.dot(du, du))
        + weights.w_F_tan_rate * float(du[0] ** 2)
        + weights.w_F_rad_rate * float(du[1] ** 2)
    )


def terminal_cost(
    state: np.ndarray,
    target_theta: float,
    model_params: dict[str, Any],
    weights: Spring2DMPCWeights,
) -> float:
    theta, _, r, _ = np.asarray(state, dtype=float)
    theta_error = theta - float(target_theta)
    delta_r = r - float(model_params["L0"])
    return float(
        weights.w_terminal_theta * theta_error**2
        + weights.w_delta_r * delta_r**2
    )
