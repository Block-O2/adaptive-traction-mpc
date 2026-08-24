"""Constraint helpers for fixed-model Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Spring2DMPCConstraints:
    F_tan_max: float
    F_rad_max: float
    delta_r_max: float
    omega_max: float
    alpha_max: float
    prediction_dt: float
    violation_penalty: float = 1.0e6

    @classmethod
    def from_configs(
        cls,
        model_params: dict[str, Any],
        constraint_params: dict[str, Any],
        prediction_dt: float | None = None,
    ) -> "Spring2DMPCConstraints":
        dt = float(prediction_dt if prediction_dt is not None else model_params["dt"])
        # Deprecated compatibility: older configs used delta_omega_max.
        # Convert it to alpha_max only when alpha_max is not specified.
        alpha_max = constraint_params.get("alpha_max")
        if alpha_max is None and "delta_omega_max" in constraint_params:
            alpha_max = float(constraint_params["delta_omega_max"]) / dt
        if alpha_max is None:
            alpha_max = constraint_params.get("alpha_max", model_params.get("alpha_max", 3.0))
        return cls(
            F_tan_max=float(constraint_params.get("F_tan_max", model_params["F_tan_max"])),
            F_rad_max=float(constraint_params.get("F_rad_max", model_params["F_rad_max"])),
            delta_r_max=float(constraint_params.get("delta_r_max", model_params["delta_r_max"])),
            omega_max=float(constraint_params.get("omega_max", model_params["omega_max"])),
            alpha_max=float(alpha_max),
            prediction_dt=dt,
            violation_penalty=float(constraint_params.get("violation_penalty", 1.0e6)),
        )

    def clip_action(self, action: np.ndarray) -> np.ndarray:
        raw = np.asarray(action, dtype=float)
        if raw.shape != (2,):
            raise ValueError("MPC action must have shape (2,) as [F_tan, F_rad].")
        return np.array(
            [
                np.clip(raw[0], -self.F_tan_max, self.F_tan_max),
                np.clip(raw[1], -self.F_rad_max, self.F_rad_max),
            ],
            dtype=float,
        )

    def action_violation(self, action: np.ndarray) -> float:
        F_tan, F_rad = np.asarray(action, dtype=float)
        return float(
            max(0.0, abs(F_tan) - self.F_tan_max) ** 2
            + max(0.0, abs(F_rad) - self.F_rad_max) ** 2
        )

    def state_violation(self, state: np.ndarray, model_params: dict[str, Any]) -> float:
        _, omega, r, _ = np.asarray(state, dtype=float)
        delta_r = r - float(model_params["L0"])
        return float(
            max(0.0, abs(delta_r) - self.delta_r_max) ** 2
            + max(0.0, abs(omega) - self.omega_max) ** 2
        )

    def transition_alpha(self, prev_state: np.ndarray, next_state: np.ndarray) -> float:
        prev_omega = float(np.asarray(prev_state, dtype=float)[1])
        next_omega = float(np.asarray(next_state, dtype=float)[1])
        return float((next_omega - prev_omega) / self.prediction_dt)

    def transition_violation(self, prev_state: np.ndarray, next_state: np.ndarray) -> float:
        alpha = self.transition_alpha(prev_state, next_state)
        return float(max(0.0, abs(alpha) - self.alpha_max) ** 2)

    def is_action_feasible(self, action: np.ndarray) -> bool:
        return self.action_violation(action) <= 0.0

    def is_state_feasible(self, state: np.ndarray, model_params: dict[str, Any]) -> bool:
        return self.state_violation(state, model_params) <= 0.0

    def is_transition_feasible(self, prev_state: np.ndarray, next_state: np.ndarray) -> bool:
        return self.transition_violation(prev_state, next_state) <= 0.0
