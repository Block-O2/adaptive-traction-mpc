"""Fixed-parameter MPC baseline for the Spring2D environment."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation
from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.base_mpc import BaseMPC
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.cost import Spring2DMPCWeights, stage_cost, terminal_cost
from traction_mpc.mpc.solvers import ConstraintResult, RolloutResult, ShootingResult, make_solver


class FixedModelMPC(BaseMPC):
    """Fixed-model sampled-shooting MPC using the frozen Spring2D dynamics."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any]):
        super().__init__(model_params, mpc_params)
        self.target_theta = float(mpc_params.get("target_theta", model_params["theta_target"]))
        self.solver_cfg = dict(mpc_params.get("solver", {}))
        self.solver_type = str(self.solver_cfg.get("type", "random_shooting")).lower()
        self.horizon = int(self.solver_cfg.get("horizon", 18))
        self.prediction_dt = float(self.solver_cfg.get("prediction_dt", self.model_params["dt"]))
        self.constraints = Spring2DMPCConstraints.from_configs(
            self.model_params,
            mpc_params.get("constraints", {}),
            prediction_dt=self.prediction_dt,
        )
        self.weights = Spring2DMPCWeights.from_config(mpc_params.get("weights", {}))
        self.solver = make_solver(self.solver_cfg, self.model_params, self.constraints)
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

    def set_target_theta(self, target_theta: float) -> None:
        """Update the MPC tracking target without resetting solver state."""

        self.target_theta = float(target_theta)

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
        result = self.solver.solve(
            state,
            self._rollout_sequence,
            self._sequence_cost,
            self._sequence_constraint,
            initial_sequence=nominal,
        )
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
            "alpha_pred_max": float(result.max_pred_alpha),
            "omega_pred_max": float(result.max_pred_omega),
            "delta_r_pred_max": float(result.max_pred_delta_r),
            "mpc_result_cost": float(result.cost),
            "mpc_result_feasible": bool(result.feasible),
            "mpc_feasible_count": int(result.feasible_count),
            "mpc_num_candidates": int(result.num_candidates),
            "mpc_feasible_ratio": float(result.feasible_count / result.num_candidates) if result.num_candidates else 0.0,
            "mpc_solver_type": self.solver_type,
            "mpc_solver_selection": str(result.diagnostics.get("selection", "")),
            "mpc_target_theta": float(self.target_theta),
            "best_task_cost": float(result.diagnostics.get("best_task_cost", np.nan)),
            "best_violation_score": float(result.diagnostics.get("best_violation_score", np.nan)),
            "best_max_violation_F_tan": float(result.diagnostics.get("best_max_violation_F_tan", np.nan)),
            "best_max_violation_F_rad": float(result.diagnostics.get("best_max_violation_F_rad", np.nan)),
            "best_max_violation_delta_r": float(result.diagnostics.get("best_max_violation_delta_r", np.nan)),
            "best_max_violation_omega": float(result.diagnostics.get("best_max_violation_omega", np.nan)),
            "best_max_violation_alpha": float(result.diagnostics.get("best_max_violation_alpha", np.nan)),
            "elite_feasible_count": int(result.diagnostics.get("elite_feasible_count", 0)),
            "selected_candidate_rank": int(result.diagnostics.get("selected_candidate_rank", 0)),
            "best_selected_from": str(result.diagnostics.get("best_selected_from", "feasible" if result.feasible else "infeasible")),
        }
        self.last_diagnostics.update(result.diagnostics)
        return result.action.copy()

    def get_last_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_diagnostics)

    def _selected_rollout_alpha_max(self, state: np.ndarray, sequence: np.ndarray) -> float:
        x = np.asarray(state, dtype=float).copy()
        max_abs_alpha = 0.0
        for action in np.asarray(sequence, dtype=float):
            prev_omega = float(x[1])
            try:
                x = step_dynamics(x, self.constraints.clip_action(action), self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                return float("nan")
            if not np.all(np.isfinite(x)):
                return float("nan")
            alpha = (float(x[1]) - prev_omega) / self.prediction_dt
            max_abs_alpha = max(max_abs_alpha, abs(alpha))
        return float(max_abs_alpha)

    def _rollout_sequence(self, state: np.ndarray, sequence: np.ndarray) -> RolloutResult:
        x = np.asarray(state, dtype=float).copy()
        actions = np.asarray(sequence, dtype=float)
        states = [x.copy()]
        applied_actions = []
        for action in actions:
            u = self.constraints.clip_action(action)
            applied_actions.append(u)
            try:
                x = step_dynamics(x, u, self.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                return RolloutResult(
                    states=np.asarray(states, dtype=float),
                    actions=np.asarray(applied_actions, dtype=float),
                    valid=False,
                    invalid_reason="dynamics_error",
                )
            if not np.all(np.isfinite(x)):
                states.append(np.asarray(x, dtype=float))
                return RolloutResult(
                    states=np.asarray(states, dtype=float),
                    actions=np.asarray(applied_actions, dtype=float),
                    valid=False,
                    invalid_reason="nonfinite_state",
                )
            if abs(float(x[1])) > 10.0 * self.constraints.omega_max:
                states.append(x.copy())
                return RolloutResult(
                    states=np.asarray(states, dtype=float),
                    actions=np.asarray(applied_actions, dtype=float),
                    valid=False,
                    invalid_reason="extreme_omega",
                )
            if abs(float(x[2] - self.model_params["L0"])) > 10.0 * self.constraints.delta_r_max:
                states.append(x.copy())
                return RolloutResult(
                    states=np.asarray(states, dtype=float),
                    actions=np.asarray(applied_actions, dtype=float),
                    valid=False,
                    invalid_reason="extreme_delta_r",
                )
            states.append(x.copy())
        return RolloutResult(
            states=np.asarray(states, dtype=float),
            actions=np.asarray(applied_actions, dtype=float),
            valid=True,
        )

    def _sequence_cost(self, state: np.ndarray, sequence: np.ndarray, rollout: RolloutResult) -> float:
        del state
        if not rollout.valid:
            return float("inf")
        cost = 0.0
        for k, action in enumerate(rollout.actions):
            prev_x = rollout.states[k]
            x = rollout.states[k + 1]
            cost += stage_cost(
                x,
                action,
                prev_x[1],
                self.prediction_dt,
                self.target_theta,
                self.model_params,
                self.weights,
            )
        cost += terminal_cost(rollout.states[-1], self.target_theta, self.model_params, self.weights)
        return float(cost)

    def _sequence_constraint(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        rollout: RolloutResult,
    ) -> ConstraintResult:
        del state
        if len(rollout.states) == 0:
            return ConstraintResult(
                feasible=False,
                penalty=float(self.constraints.violation_penalty * 1.0e6),
                max_pred_alpha=float("inf"),
                max_pred_omega=float("inf"),
                max_pred_delta_r=float("inf"),
                violation_count=1,
            )

        penalty = 0.0
        feasible = bool(rollout.valid)
        violation_count = 0
        max_pred_alpha = 0.0
        max_pred_omega = 0.0
        max_pred_delta_r = 0.0
        max_violation_F_tan = 0.0
        max_violation_F_rad = 0.0
        max_violation_delta_r = 0.0
        max_violation_omega = 0.0
        max_violation_alpha = 0.0
        steps = min(len(rollout.actions), max(0, len(rollout.states) - 1), len(sequence))
        for k in range(steps):
            raw_action = np.asarray(sequence[k], dtype=float)
            prev_x = rollout.states[k]
            x = rollout.states[k + 1]
            alpha = self.constraints.transition_alpha(prev_x, x)
            delta_r = float(x[2] - self.model_params["L0"])
            v_F_tan = max(0.0, abs(float(raw_action[0])) - self.constraints.F_tan_max)
            v_F_rad = max(0.0, abs(float(raw_action[1])) - self.constraints.F_rad_max)
            v_delta_r = max(0.0, abs(delta_r) - self.constraints.delta_r_max)
            v_omega = max(0.0, abs(float(x[1])) - self.constraints.omega_max)
            v_alpha = max(0.0, abs(float(alpha)) - self.constraints.alpha_max)
            max_pred_alpha = max(max_pred_alpha, abs(float(alpha)))
            max_pred_omega = max(max_pred_omega, abs(float(x[1])))
            max_pred_delta_r = max(max_pred_delta_r, abs(delta_r))
            max_violation_F_tan = max(max_violation_F_tan, v_F_tan)
            max_violation_F_rad = max(max_violation_F_rad, v_F_rad)
            max_violation_delta_r = max(max_violation_delta_r, v_delta_r)
            max_violation_omega = max(max_violation_omega, v_omega)
            max_violation_alpha = max(max_violation_alpha, v_alpha)
            violation = (
                self.constraints.action_violation(raw_action)
                + self.constraints.state_violation(x, self.model_params)
                + self.constraints.transition_violation(prev_x, x)
            )
            if violation > 0.0:
                feasible = False
                violation_count += 1
                penalty += self.constraints.violation_penalty * violation

        if not rollout.valid:
            feasible = False
            violation_count += 1
            if (
                max_violation_F_tan <= 0.0
                and max_violation_F_rad <= 0.0
                and max_violation_delta_r <= 0.0
                and max_violation_omega <= 0.0
                and max_violation_alpha <= 0.0
            ):
                max_violation_alpha = float("inf")
            penalty += self.constraints.violation_penalty * 1.0e6
        return ConstraintResult(
            feasible=feasible,
            penalty=float(penalty),
            max_pred_alpha=float(max_pred_alpha),
            max_pred_omega=float(max_pred_omega),
            max_pred_delta_r=float(max_pred_delta_r),
            violation_count=int(violation_count),
            max_violation_F_tan=float(max_violation_F_tan),
            max_violation_F_rad=float(max_violation_F_rad),
            max_violation_delta_r=float(max_violation_delta_r),
            max_violation_omega=float(max_violation_omega),
            max_violation_alpha=float(max_violation_alpha),
        )

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
