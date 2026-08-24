"""Shared interfaces for Spring2D MPC sequence solvers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np


@dataclass
class RolloutResult:
    states: np.ndarray
    actions: np.ndarray
    valid: bool = True
    invalid_reason: str = ""


@dataclass
class ConstraintResult:
    feasible: bool
    penalty: float
    max_pred_alpha: float
    max_pred_omega: float
    max_pred_delta_r: float
    violation_count: int = 0
    max_violation_F_tan: float = 0.0
    max_violation_F_rad: float = 0.0
    max_violation_delta_r: float = 0.0
    max_violation_omega: float = 0.0
    max_violation_alpha: float = 0.0


@dataclass
class CandidateEvaluation:
    total_cost: float
    task_cost: float
    feasible: bool
    constraint: ConstraintResult
    rollout: RolloutResult


@dataclass
class SolverResult:
    best_action: np.ndarray
    best_sequence: np.ndarray
    best_cost: float
    feasible: bool
    feasible_count: int
    num_candidates: int
    max_pred_alpha: float
    max_pred_omega: float
    max_pred_delta_r: float
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> np.ndarray:
        return self.best_action

    @property
    def sequence(self) -> np.ndarray:
        return self.best_sequence

    @property
    def cost(self) -> float:
        return self.best_cost


RolloutFn = Callable[[np.ndarray, np.ndarray], RolloutResult]
CostFn = Callable[[np.ndarray, np.ndarray, RolloutResult], float]
ConstraintFn = Callable[[np.ndarray, np.ndarray, RolloutResult], ConstraintResult]


class SequenceSolver(Protocol):
    def solve(
        self,
        x0: np.ndarray,
        rollout_fn: RolloutFn,
        cost_fn: CostFn,
        constraint_fn: ConstraintFn,
        initial_sequence: np.ndarray | None = None,
    ) -> SolverResult:
        ...


class CandidateEvaluator:
    """Evaluate candidate action sequences through shared MPC callbacks."""

    def __init__(
        self,
        x0: np.ndarray,
        rollout_fn: RolloutFn,
        cost_fn: CostFn,
        constraint_fn: ConstraintFn,
    ):
        self.x0 = np.asarray(x0, dtype=float)
        self.rollout_fn = rollout_fn
        self.cost_fn = cost_fn
        self.constraint_fn = constraint_fn

    def evaluate(self, sequence: np.ndarray) -> tuple[float, bool, ConstraintResult, RolloutResult]:
        evaluation = self.evaluate_detailed(sequence)
        return evaluation.total_cost, evaluation.feasible, evaluation.constraint, evaluation.rollout

    def evaluate_detailed(self, sequence: np.ndarray) -> CandidateEvaluation:
        rollout = self.rollout_fn(self.x0, np.asarray(sequence, dtype=float))
        constraint = self.constraint_fn(self.x0, np.asarray(sequence, dtype=float), rollout)
        if not rollout.valid:
            return CandidateEvaluation(
                total_cost=float(constraint.penalty),
                task_cost=float("inf"),
                feasible=False,
                constraint=constraint,
                rollout=rollout,
            )
        cost = self.cost_fn(self.x0, np.asarray(sequence, dtype=float), rollout)
        if not np.isfinite(cost):
            return CandidateEvaluation(
                total_cost=float(constraint.penalty),
                task_cost=float("inf"),
                feasible=False,
                constraint=constraint,
                rollout=rollout,
            )
        total_cost = float(cost + constraint.penalty)
        return CandidateEvaluation(
            total_cost=total_cost,
            task_cost=float(cost),
            feasible=bool(constraint.feasible),
            constraint=constraint,
            rollout=rollout,
        )
