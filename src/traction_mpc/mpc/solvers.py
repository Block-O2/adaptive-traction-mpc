"""Lightweight shooting solvers for Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.cost import Spring2DMPCWeights, stage_cost, terminal_cost


@dataclass(frozen=True)
class ShootingSolverConfig:
    horizon: int
    num_samples: int
    num_elites: int
    iterations: int
    prediction_dt: float
    action_std: np.ndarray
    min_std: np.ndarray
    seed: int

    @classmethod
    def from_config(cls, cfg: dict[str, Any], model_params: dict[str, Any]) -> "ShootingSolverConfig":
        num_samples = int(cfg.get("num_samples", 128))
        elite_frac = float(cfg.get("elite_frac", 0.15))
        num_elites = max(2, int(round(num_samples * elite_frac)))
        dt = float(cfg.get("prediction_dt", model_params["dt"]))
        return cls(
            horizon=int(cfg.get("horizon", 18)),
            num_samples=num_samples,
            num_elites=min(num_elites, num_samples),
            iterations=int(cfg.get("iterations", 2)),
            prediction_dt=dt,
            action_std=np.array(cfg.get("action_std", [3.0, 1.0]), dtype=float),
            min_std=np.array(cfg.get("min_std", [0.4, 0.2]), dtype=float),
            seed=int(cfg.get("seed", 7)),
        )


@dataclass
class ShootingResult:
    action: np.ndarray
    sequence: np.ndarray
    cost: float
    feasible: bool


class RandomShootingSolver:
    """Random shooting with elite refitting around a warm-start sequence."""

    def __init__(
        self,
        solver_config: ShootingSolverConfig,
        constraints: Spring2DMPCConstraints,
        weights: Spring2DMPCWeights,
        model_params: dict[str, Any],
    ):
        self.config = solver_config
        self.constraints = constraints
        self.weights = weights
        self.model_params = dict(model_params)
        self.rng = np.random.default_rng(self.config.seed)

    def solve(
        self,
        state: np.ndarray,
        target_theta: float,
        nominal_sequence: np.ndarray,
        prev_action: np.ndarray,
    ) -> ShootingResult:
        mean = np.asarray(nominal_sequence, dtype=float).copy()
        if mean.shape != (self.config.horizon, 2):
            raise ValueError("nominal_sequence must have shape (horizon, 2).")
        std = self.config.action_std.astype(float).copy()
        best_sequence = mean.copy()
        best_cost = np.inf
        best_feasible = False

        for _ in range(self.config.iterations):
            candidates = self._sample_candidates(mean, std)
            candidates[0] = mean
            costs = np.empty(candidates.shape[0], dtype=float)
            feasible = np.empty(candidates.shape[0], dtype=bool)
            for i, sequence in enumerate(candidates):
                costs[i], feasible[i] = self.evaluate_sequence(
                    state,
                    sequence,
                    target_theta,
                    prev_action,
                )

            order = np.argsort(costs)
            if costs[order[0]] < best_cost:
                best_cost = float(costs[order[0]])
                best_sequence = candidates[order[0]].copy()
                best_feasible = bool(feasible[order[0]])

            elites = candidates[order[: self.config.num_elites]]
            mean = elites.mean(axis=0)
            std = np.maximum(elites.std(axis=0).mean(axis=0), self.config.min_std)

        action = self.constraints.clip_action(best_sequence[0])
        return ShootingResult(action=action, sequence=best_sequence, cost=best_cost, feasible=best_feasible)

    def _sample_candidates(self, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        shape = (self.config.num_samples, self.config.horizon, 2)
        samples = self.rng.normal(loc=mean, scale=std.reshape(1, 1, 2), size=shape)
        samples[..., 0] = np.clip(samples[..., 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        samples[..., 1] = np.clip(samples[..., 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return samples

    def evaluate_sequence(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        target_theta: float,
        prev_action: np.ndarray,
    ) -> tuple[float, bool]:
        x = np.asarray(state, dtype=float).copy()
        cost = 0.0
        feasible = True

        for action in np.asarray(sequence, dtype=float):
            u = self.constraints.clip_action(action)
            prev_x = x
            try:
                x = step_dynamics(x, u, self.config.prediction_dt, self.model_params)
            except (FloatingPointError, OverflowError, ValueError):
                return float(self.constraints.violation_penalty * 1.0e6), False
            if not np.all(np.isfinite(x)):
                return float(self.constraints.violation_penalty * 1.0e6), False
            if abs(float(x[1])) > 10.0 * self.constraints.omega_max:
                return float(self.constraints.violation_penalty * 1.0e6), False
            if abs(float(x[2] - self.model_params["L0"])) > 10.0 * self.constraints.delta_r_max:
                return float(self.constraints.violation_penalty * 1.0e6), False
            cost += stage_cost(
                x,
                u,
                prev_x[1],
                self.config.prediction_dt,
                target_theta,
                self.model_params,
                self.weights,
            )

            violation = (
                self.constraints.action_violation(action)
                + self.constraints.state_violation(x, self.model_params)
                + self.constraints.transition_violation(prev_x, x)
            )
            if violation > 0.0:
                feasible = False
                cost += self.constraints.violation_penalty * violation

        cost += terminal_cost(x, target_theta, self.model_params, self.weights)
        return float(cost), feasible
