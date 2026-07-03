"""Fixed-parameter MPC baseline for the Spring2D environment."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.base_mpc import BaseMPC
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.cost import Spring2DMPCWeights
from traction_mpc.mpc.solvers import RandomShootingSolver, ShootingResult, ShootingSolverConfig


class FixedModelMPC(BaseMPC):
    """Fixed-model sampled-shooting MPC using the frozen Spring2D dynamics."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any]):
        super().__init__(model_params, mpc_params)
        self.target_theta = float(mpc_params.get("target_theta", model_params["theta_target"]))
        self.horizon = int(mpc_params.get("solver", {}).get("horizon", 18))
        self.solver_config = ShootingSolverConfig.from_config(
            mpc_params.get("solver", {}),
            self.model_params,
        )
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.solver_config.prediction_dt,
        )
        self.weights = Spring2DMPCWeights.from_config(mpc_params.get("weights", {}))
        self.solver = RandomShootingSolver(
            self.solver_config,
            self.constraints,
            self.weights,
            self.model_params,
        )
        self.nominal_cfg = dict(mpc_params.get("nominal_policy", {}))
        self.last_action = np.zeros(2, dtype=float)
        self.last_solution = np.zeros((self.horizon, 2), dtype=float)
        self.last_result: ShootingResult | None = None
        self.solve_count = 0
        self.last_diagnostics: dict[str, Any] = {}

    def set_model_params(self, theta_params: dict[str, float]) -> None:
        """Update prediction model parameters without resetting solver state."""

        for name, value in theta_params.items():
            if name not in self.model_params:
                raise KeyError(f"Unknown MPC model parameter: {name}")
            numeric_value = float(value)
            self.model_params[name] = numeric_value
            self.solver.model_params[name] = numeric_value

    def reset(self) -> None:
        self.last_action = np.zeros(2, dtype=float)
        self.last_solution = np.zeros((self.horizon, 2), dtype=float)
        self.last_result = None
        self.solve_count = 0
        self.last_diagnostics = {}

    def act(self, observation: Spring2DObservation) -> np.ndarray:
        state = self._state_from_observation(observation)
        last_solution_existed = self.last_result is not None
        nominal = self._nominal_sequence(state)
        result = self.solver.solve(state, self.target_theta, nominal, self.last_action)
        self.last_result = result
        self.last_action = result.action.copy()
        self.last_solution = result.sequence.copy()
        self.solve_count += 1
        first_action = np.asarray(result.sequence[0], dtype=float)
        self.last_diagnostics = {
            "mpc_solve_count": int(self.solve_count),
            "last_solution_existed_before_solve": bool(last_solution_existed),
            "warm_start_used": bool(last_solution_existed and float(self.nominal_cfg.get("warm_start_blend", 0.35)) > 0.0),
            "selected_sequence_first_F_tan": float(first_action[0]),
            "selected_sequence_first_F_rad": float(first_action[1]),
            "alpha_pred_max": self._selected_rollout_alpha_max(state, result.sequence),
            "mpc_result_cost": float(result.cost),
            "mpc_result_feasible": bool(result.feasible),
        }
        return result.action.copy()

    def get_last_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diagnostics)

    def _selected_rollout_alpha_max(self, state: np.ndarray, sequence: np.ndarray) -> float:
        x = np.asarray(state, dtype=float).copy()
        max_abs_alpha = 0.0
        for action in np.asarray(sequence, dtype=float):
            prev_omega = float(x[1])
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.solver_config.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                return float("nan")
            if not np.all(np.isfinite(x)):
                return float("nan")
            alpha = (float(x[1]) - prev_omega) / self.solver_config.prediction_dt
            max_abs_alpha = max(max_abs_alpha, abs(alpha))
        return float(max_abs_alpha)

    def _state_from_observation(self, observation: Spring2DObservation) -> np.ndarray:
        return np.array(
            [observation.theta, observation.omega, observation.r, observation.r_dot],
            dtype=float,
        )

    def _nominal_sequence(self, state: np.ndarray) -> np.ndarray:
        warm = self._shift_previous_solution()
        heuristic = self._heuristic_sequence(state)
        blend = float(self.nominal_cfg.get("warm_start_blend", 0.35))
        sequence = blend * warm + (1.0 - blend) * heuristic
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence

    def _shift_previous_solution(self) -> np.ndarray:
        shifted = np.zeros_like(self.last_solution)
        if len(self.last_solution) > 1:
            shifted[:-1] = self.last_solution[1:]
            shifted[-1] = self.last_solution[-1]
        return shifted

    def _heuristic_sequence(self, state: np.ndarray) -> np.ndarray:
        theta, omega, r, r_dot = np.asarray(state, dtype=float)
        theta_error = self.target_theta - theta
        kp_theta = float(self.nominal_cfg.get("kp_theta", 7.5))
        kd_omega = float(self.nominal_cfg.get("kd_omega", 1.6))
        radial_kp = float(self.nominal_cfg.get("radial_kp", 60.0))
        radial_kd = float(self.nominal_cfg.get("radial_kd", 8.0))
        taper = np.linspace(1.0, float(self.nominal_cfg.get("terminal_taper", 0.45)), self.horizon)

        F_tan = kp_theta * theta_error - kd_omega * omega
        F_rad = -radial_kp * (r - float(self.model_params["L0"])) - radial_kd * r_dot
        sequence = np.column_stack([F_tan * taper, np.full(self.horizon, F_rad)])
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence
