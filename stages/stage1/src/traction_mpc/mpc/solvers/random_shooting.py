"""Random-shooting solver for Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.solvers.base import CandidateEvaluator, ConstraintFn, RolloutFn, CostFn, SolverResult


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
    warm_start: bool = True

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
            warm_start=bool(cfg.get("warm_start", True)),
        )


class RandomShootingSolver:
    """Random shooting with elite refitting around a warm-start sequence."""

    def __init__(
        self,
        solver_config: ShootingSolverConfig,
        constraints: Spring2DMPCConstraints,
    ):
        self.config = solver_config
        self.constraints = constraints
        self.rng = np.random.default_rng(self.config.seed)

    def solve(
        self,
        x0: np.ndarray,
        rollout_fn: RolloutFn,
        cost_fn: CostFn,
        constraint_fn: ConstraintFn,
        initial_sequence: np.ndarray | None = None,
    ) -> SolverResult:
        mean = self._initial_mean(initial_sequence)
        std = self.config.action_std.astype(float).copy()
        evaluator = CandidateEvaluator(x0, rollout_fn, cost_fn, constraint_fn)
        best_sequence = mean.copy()
        best_cost = np.inf
        best_task_cost = np.inf
        best_violation_score = np.inf
        best_feasible = False
        best_constraint = None
        best_elite_feasible_count = 0
        feasible_count_total = 0
        num_candidates_total = 0

        for _ in range(self.config.iterations):
            candidates = self._sample_candidates(mean, std)
            candidates[0] = mean
            costs = np.empty(candidates.shape[0], dtype=float)
            task_costs = np.empty(candidates.shape[0], dtype=float)
            violation_scores = np.empty(candidates.shape[0], dtype=float)
            feasible = np.empty(candidates.shape[0], dtype=bool)
            constraints = []
            for i, sequence in enumerate(candidates):
                evaluation = evaluator.evaluate_detailed(sequence)
                costs[i] = evaluation.total_cost
                task_costs[i] = evaluation.task_cost
                feasible[i] = evaluation.feasible
                constraint = evaluation.constraint
                violation_scores[i] = self._violation_score(constraint)
                constraints.append(constraint)

            feasible_count_total += int(np.count_nonzero(feasible))
            num_candidates_total += int(candidates.shape[0])
            order = np.argsort(costs)
            if costs[order[0]] < best_cost:
                best_idx = int(order[0])
                best_cost = float(costs[best_idx])
                best_task_cost = float(task_costs[best_idx])
                best_violation_score = float(violation_scores[best_idx])
                best_sequence = candidates[best_idx].copy()
                best_feasible = bool(feasible[best_idx])
                best_constraint = constraints[best_idx]
                best_elite_feasible_count = int(np.count_nonzero(feasible[order[: self.config.num_elites]]))

            elites = candidates[order[: self.config.num_elites]]
            mean = elites.mean(axis=0)
            std = np.maximum(elites.std(axis=0).mean(axis=0), self.config.min_std)

        if best_constraint is None:
            raise RuntimeError("Random shooting did not evaluate any candidates.")
        action = self.constraints.clip_action(best_sequence[0])
        return SolverResult(
            best_action=action,
            best_sequence=best_sequence,
            best_cost=best_cost,
            feasible=best_feasible,
            feasible_count=feasible_count_total,
            num_candidates=num_candidates_total,
            max_pred_alpha=float(best_constraint.max_pred_alpha),
            max_pred_omega=float(best_constraint.max_pred_omega),
            max_pred_delta_r=float(best_constraint.max_pred_delta_r),
            diagnostics={
                "solver_type": "random_shooting",
                "iterations": int(self.config.iterations),
                "num_samples": int(self.config.num_samples),
                "num_elites": int(self.config.num_elites),
                "warm_start": bool(self.config.warm_start),
                "best_task_cost": float(best_task_cost),
                "best_violation_score": float(best_violation_score),
                "best_max_violation_F_tan": float(best_constraint.max_violation_F_tan),
                "best_max_violation_F_rad": float(best_constraint.max_violation_F_rad),
                "best_max_violation_delta_r": float(best_constraint.max_violation_delta_r),
                "best_max_violation_omega": float(best_constraint.max_violation_omega),
                "best_max_violation_alpha": float(best_constraint.max_violation_alpha),
                "elite_feasible_count": int(best_elite_feasible_count),
                "selected_candidate_rank": 0,
                "best_selected_from": "feasible" if best_feasible else "infeasible",
            },
        )

    def _initial_mean(self, initial_sequence: np.ndarray | None) -> np.ndarray:
        if initial_sequence is not None and self.config.warm_start:
            mean = np.asarray(initial_sequence, dtype=float).copy()
        else:
            mean = np.zeros((self.config.horizon, 2), dtype=float)
        if mean.shape != (self.config.horizon, 2):
            raise ValueError("initial_sequence must have shape (horizon, 2).")
        mean[:, 0] = np.clip(mean[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        mean[:, 1] = np.clip(mean[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return mean

    def _sample_candidates(self, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        shape = (self.config.num_samples, self.config.horizon, 2)
        samples = self.rng.normal(loc=mean, scale=std.reshape(1, 1, 2), size=shape)
        samples[..., 0] = np.clip(samples[..., 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        samples[..., 1] = np.clip(samples[..., 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return samples

    def _violation_score(self, constraint) -> float:
        score = (
            constraint.max_violation_F_tan**2
            + constraint.max_violation_F_rad**2
            + constraint.max_violation_delta_r**2
            + constraint.max_violation_omega**2
            + constraint.max_violation_alpha**2
        )
        return float(score) if np.isfinite(score) else float("inf")
