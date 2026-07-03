"""Gym-like 2D spring-rod environment without external simulator dependencies."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DAction, Spring2DObservation, Spring2DState
from traction_mpc.models.spring2d_dynamics import (
    compute_directions,
    compute_physical_info,
    compute_positions,
    step_dynamics,
)


SPRING2D_HISTORY_FIELDS = [
    "t",
    "theta",
    "omega",
    "r",
    "r_dot",
    "delta_r",
    "base_x",
    "base_y",
    "base_a",
    "base_ap",
    "tip_x",
    "tip_y",
    "contact_x",
    "contact_y",
    "contact_vx",
    "contact_vy",
    "F_tan",
    "F_rad",
    "force_x",
    "force_y",
    "e_rad_x",
    "e_rad_y",
    "e_tan_x",
    "e_tan_y",
    "I",
    "M_r",
    "M11",
    "M12",
    "M22",
    "Q_r",
    "Q_theta",
    "h_r",
    "h_theta",
    "spring_force",
    "gravity_force",
    "gravity_torque",
    "centrifugal_term",
    "radial_accel",
    "angular_accel",
    "r_ddot",
    "omega_dot",
    "done",
    "done_reason",
]


class Spring2DEnv:
    """2D polar spring-rod environment for controller prototyping."""

    history_fields = tuple(SPRING2D_HISTORY_FIELDS)

    def __init__(self, params: dict[str, Any]):
        self.params = dict(params)
        self.dt = float(self.params["dt"])
        self.t = 0.0
        self.state = self._initial_state()
        self.contact_vel = np.zeros(2, dtype=float)
        self.last_action = np.zeros(2, dtype=float)
        self.done_reason: str | None = None
        self.history: list[dict[str, Any]] = []

    def _initial_state(self) -> np.ndarray:
        return np.array(
            [
                float(self.params["theta_init"]),
                float(self.params["omega_init"]),
                float(self.params["r_init"]),
                float(self.params["r_dot_init"]),
            ],
            dtype=float,
        )

    def reset(self, seed: int | None = None) -> Spring2DObservation:
        if seed is not None:
            np.random.default_rng(seed)
        self.t = 0.0
        self.state = self._initial_state()
        self.contact_vel = np.zeros(2, dtype=float)
        self.last_action = np.zeros(2, dtype=float)
        self.done_reason = None
        self.history = []
        obs = self.get_observation()
        self._append_history(obs)
        return obs

    def _clip_action(self, action: np.ndarray | Spring2DAction | list[float] | tuple[float, float]) -> np.ndarray:
        if isinstance(action, Spring2DAction):
            raw = action.as_array()
        else:
            raw = np.asarray(action, dtype=float)
        if raw.shape != (2,):
            raise ValueError("Spring2D action must have shape (2,) as [F_tan, F_rad].")
        if not np.all(np.isfinite(raw)):
            raise ValueError("Spring2D action must contain finite values.")
        F_tan = np.clip(raw[0], -float(self.params["F_tan_max"]), float(self.params["F_tan_max"]))
        F_rad = np.clip(raw[1], -float(self.params["F_rad_max"]), float(self.params["F_rad_max"]))
        return np.array([F_tan, F_rad], dtype=float)

    def step(self, action: np.ndarray | Spring2DAction | list[float] | tuple[float, float]) -> Spring2DObservation:
        if self.done_reason is not None:
            return self.get_observation()

        action_arr = self._clip_action(action)
        old_contact_pos = compute_positions(self.state, self.params)["contact_pos"]
        self.state = step_dynamics(self.state, action_arr, self.dt, self.params)
        self.t += self.dt
        self.last_action = action_arr
        new_contact_pos = compute_positions(self.state, self.params)["contact_pos"]
        self.contact_vel = (new_contact_pos - old_contact_pos) / self.dt

        obs = self.get_observation()
        self.done_reason = self._compute_done_reason(obs)
        obs = self.get_observation()
        self._append_history(obs)
        return obs

    def _compute_done_reason(self, obs: Spring2DObservation) -> str | None:
        if obs.theta >= float(self.params["theta_target"]):
            return "target_reached"
        if abs(obs.delta_r) > float(self.params["delta_r_max"]):
            return "radial_limit"
        if abs(obs.omega) > float(self.params["omega_max"]):
            return "omega_limit"
        if self.t >= float(self.params["max_time"]):
            return "max_time"
        return None

    def is_done(self) -> bool:
        return self.done_reason is not None

    def get_observation(self) -> Spring2DObservation:
        positions = compute_positions(self.state, self.params)
        contact_pos = positions["contact_pos"]

        theta, omega, r, r_dot = self.state
        physical_info = compute_physical_info(self.state, self.last_action, self.params)
        return Spring2DObservation(
            t=float(self.t),
            theta=float(theta),
            omega=float(omega),
            r=float(r),
            r_dot=float(r_dot),
            delta_r=float(r - float(self.params["L0"])),
            base_pos=positions["base_pos"],
            tip_pos=positions["tip_pos"],
            contact_pos=contact_pos,
            contact_vel=self.contact_vel.copy(),
            F_tan=float(self.last_action[0]),
            F_rad=float(self.last_action[1]),
            r_ddot=float(physical_info["r_ddot"]),
            omega_dot=float(physical_info["omega_dot"]),
            base_x=float(physical_info["base_x"]),
            base_a=float(physical_info["base_a"]),
            base_ap=float(physical_info["base_ap"]),
            done=self.is_done(),
            done_reason=self.done_reason,
            physical_info=physical_info,
        )

    def _append_history(self, obs: Spring2DObservation) -> None:
        info = obs.physical_info
        e_rad, e_tan = compute_directions(obs.theta)
        row = {
                "t": obs.t,
                "theta": obs.theta,
                "omega": obs.omega,
                "r": obs.r,
                "r_dot": obs.r_dot,
                "delta_r": obs.delta_r,
                "base_x": float(obs.base_pos[0]),
                "base_y": float(obs.base_pos[1]),
                "base_a": float(info["base_a"]),
                "base_ap": float(info["base_ap"]),
                "tip_x": float(obs.tip_pos[0]),
                "tip_y": float(obs.tip_pos[1]),
                "contact_x": float(obs.contact_pos[0]),
                "contact_y": float(obs.contact_pos[1]),
                "contact_vx": float(obs.contact_vel[0]),
                "contact_vy": float(obs.contact_vel[1]),
                "F_tan": obs.F_tan,
                "F_rad": obs.F_rad,
                "force_x": float(info["force_xy"][0]),
                "force_y": float(info["force_xy"][1]),
                "e_rad_x": float(e_rad[0]),
                "e_rad_y": float(e_rad[1]),
                "e_tan_x": float(e_tan[0]),
                "e_tan_y": float(e_tan[1]),
                "I": float(info["I"]),
                "M_r": float(info["M_r"]),
                "M11": float(info["M11"]),
                "M12": float(info["M12"]),
                "M22": float(info["M22"]),
                "Q_r": float(info["Q_r"]),
                "Q_theta": float(info["Q_theta"]),
                "h_r": float(info["h_r"]),
                "h_theta": float(info["h_theta"]),
                "spring_force": float(info["spring_force"]),
                "gravity_force": float(info["gravity_force"]),
                "gravity_torque": float(info["gravity_torque"]),
                "centrifugal_term": float(info["centrifugal_term"]),
                "radial_accel": float(info["radial_accel"]),
                "angular_accel": float(info["angular_accel"]),
                "r_ddot": float(info["r_ddot"]),
                "omega_dot": float(info["omega_dot"]),
                "done": obs.done,
                "done_reason": obs.done_reason or "",
            }
        self.history.append({field: row[field] for field in SPRING2D_HISTORY_FIELDS})

    def get_state(self) -> Spring2DState:
        return Spring2DState.from_array(self.state)

    def get_history(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.history]

    def save_history(self, path: str | Path) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.history:
            raise ValueError("No Spring2D history to save.")
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SPRING2D_HISTORY_FIELDS)
            writer.writeheader()
            writer.writerows(self.history)
