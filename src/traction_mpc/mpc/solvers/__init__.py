"""MPC sequence solver implementations."""

from __future__ import annotations

from typing import Any

from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.solvers.base import CandidateEvaluation, ConstraintResult, RolloutResult, SequenceSolver, SolverResult
from traction_mpc.mpc.solvers.cem import CEMSolver, CEMSolverConfig
from traction_mpc.mpc.solvers.random_shooting import RandomShootingSolver, ShootingSolverConfig

ShootingResult = SolverResult


def make_solver(
    solver_cfg: dict[str, Any],
    model_params: dict[str, Any],
    constraints: Spring2DMPCConstraints,
):
    solver_type = str(solver_cfg.get("type", "random_shooting")).lower()
    if solver_type in {"random_shooting", "shooting"}:
        return RandomShootingSolver(ShootingSolverConfig.from_config(solver_cfg, model_params), constraints)
    if solver_type == "cem":
        return CEMSolver(CEMSolverConfig.from_config(solver_cfg, model_params), constraints)
    raise ValueError(f"Unknown MPC solver type: {solver_type}")


__all__ = [
    "CEMSolver",
    "CEMSolverConfig",
    "CandidateEvaluation",
    "ConstraintResult",
    "RandomShootingSolver",
    "RolloutResult",
    "SequenceSolver",
    "ShootingResult",
    "ShootingSolverConfig",
    "SolverResult",
    "make_solver",
]
