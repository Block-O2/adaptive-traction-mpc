"""Deterministic smooth-subspace refinement after the unchanged Stage-4 CEM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .mpc import HumanMPCConfig, HumanSpaceMPC


SequenceEvaluation = tuple[float, float, np.ndarray | None]


@dataclass(frozen=True)
class SmoothTemporalRefinementConfig:
    """Fixed local stencil defined relative to the existing CEM floor.

    The residual box is one half of the configured CEM standard-deviation
    floor.  This ties the local scale to an existing optimizer quantity rather
    than to closed-loop outcomes.
    """

    residual_fraction_of_cem_floor: float = 0.5
    coefficient_levels: tuple[float, ...] = (-1.0, -0.5, 0.5, 1.0)

    def __post_init__(self) -> None:
        if not 0.0 < self.residual_fraction_of_cem_floor <= 1.0:
            raise ValueError("residual fraction must lie in (0, 1]")
        if not self.coefficient_levels:
            raise ValueError("at least one local coefficient is required")
        if any(not np.isfinite(value) or abs(value) > 1.0 for value in self.coefficient_levels):
            raise ValueError("local coefficients must be finite and within [-1, 1]")
        if any(value == 0.0 for value in self.coefficient_levels):
            raise ValueError("the unchanged CEM solution is evaluated separately")

    def as_dict(self, mpc_config: HumanMPCConfig) -> dict[str, Any]:
        floor = np.asarray(mpc_config.exploration_std_floor_nm, dtype=float)
        return {
            "temporal_basis": ["constant", "linear", "quadratic", "cubic"],
            "joint_directions": ["hip", "knee"],
            "coefficient_levels": list(self.coefficient_levels),
            "residual_fraction_of_cem_floor": self.residual_fraction_of_cem_floor,
            "cem_standard_deviation_floor_nm": floor.tolist(),
            "maximum_abs_residual_nm_per_action_element": (
                self.residual_fraction_of_cem_floor * floor
            ).tolist(),
            "cross_joint_combinations": False,
            "cross_joint_reason": (
                "the validated representative-call audit found its best local "
                "improvements on single smooth basis directions"
            ),
            "radius_selected_from_closed_loop_outcomes": False,
        }


def smooth_temporal_residuals(
    mpc_config: HumanMPCConfig,
    refinement_config: SmoothTemporalRefinementConfig,
) -> list[dict[str, Any]]:
    """Return the fixed 8-direction, four-level smooth local stencil."""

    horizon = mpc_config.horizon_steps
    time = np.linspace(-1.0, 1.0, horizon)
    basis = np.column_stack(
        [
            np.ones(horizon),
            time,
            0.5 * (3.0 * time**2 - 1.0),
            0.5 * (5.0 * time**3 - 3.0 * time),
        ]
    )
    basis /= np.max(np.abs(basis), axis=0, keepdims=True)
    bound = (
        refinement_config.residual_fraction_of_cem_floor
        * np.asarray(mpc_config.exploration_std_floor_nm, dtype=float)
    )
    records: list[dict[str, Any]] = []
    basis_names = ("constant", "linear", "quadratic", "cubic")
    for order, basis_name in enumerate(basis_names):
        for joint, joint_name in enumerate(("hip", "knee")):
            direction = np.zeros((horizon, 2))
            direction[:, joint] = bound[joint] * basis[:, order]
            for coefficient in refinement_config.coefficient_levels:
                records.append(
                    {
                        "name": f"{joint_name}_{basis_name}",
                        "coefficient": float(coefficient),
                        "delta_u_nm": coefficient * direction,
                    }
                )
    return records


class SmoothTemporalLocalRefiner:
    """Evaluate a fixed smooth stencil and retain only strict feasible improvement."""

    def __init__(
        self,
        mpc_config: HumanMPCConfig,
        config: SmoothTemporalRefinementConfig = SmoothTemporalRefinementConfig(),
    ) -> None:
        self.mpc_config = mpc_config
        self.config = config
        self.residuals = smooth_temporal_residuals(mpc_config, config)

    def refine(
        self,
        sequence: np.ndarray,
        evaluation: SequenceEvaluation,
        evaluate: Callable[[np.ndarray], SequenceEvaluation],
    ) -> tuple[np.ndarray, SequenceEvaluation, dict[str, Any]]:
        global_sequence = np.asarray(sequence, dtype=float)
        global_cost = float(evaluation[0])
        best_sequence = global_sequence
        best_evaluation = evaluation
        best_direction: dict[str, Any] | None = None
        feasible_count = 0
        candidate_records: list[dict[str, Any]] = []
        for residual in self.residuals:
            candidate = global_sequence + residual["delta_u_nm"]
            candidate_evaluation = evaluate(candidate)
            cost, margin, states = candidate_evaluation
            feasible = bool(states is not None and margin >= -1e-9)
            feasible_count += int(feasible)
            candidate_records.append(
                {
                    "name": residual["name"],
                    "coefficient": residual["coefficient"],
                    "objective": float(cost),
                    "minimum_constraint_margin": float(margin),
                    "feasible": feasible,
                }
            )
            if feasible and cost < best_evaluation[0]:
                best_sequence = candidate
                best_evaluation = candidate_evaluation
                best_direction = {
                    "name": residual["name"],
                    "coefficient": residual["coefficient"],
                    "maximum_abs_residual_nm_per_joint": np.max(
                        np.abs(residual["delta_u_nm"]), axis=0
                    ).tolist(),
                }

        numerical_tolerance = 1e-12 * max(1.0, abs(global_cost))
        accepted = bool(best_evaluation[0] < global_cost - numerical_tolerance)
        if not accepted:
            best_sequence = global_sequence
            best_evaluation = evaluation
            best_direction = None
        improvement = float(global_cost - best_evaluation[0])
        return best_sequence, best_evaluation, {
            "enabled": True,
            "accepted": accepted,
            "candidate_evaluations": len(self.residuals),
            "feasible_candidate_evaluations": feasible_count,
            "objective_before": global_cost,
            "objective_after": float(best_evaluation[0]),
            "objective_improvement": improvement,
            "relative_objective_improvement": (
                improvement / global_cost if np.isfinite(global_cost) and global_cost != 0.0 else 0.0
            ),
            "selected_direction": best_direction,
            "strict_improvement_numerical_tolerance": numerical_tolerance,
            "config": self.config.as_dict(self.mpc_config),
            "candidates": candidate_records,
        }


class HybridHumanSpaceMPC(HumanSpaceMPC):
    """Unchanged global CEM followed by deterministic smooth local refinement."""

    def __init__(
        self,
        config: HumanMPCConfig = HumanMPCConfig(),
        *,
        refinement_config: SmoothTemporalRefinementConfig = SmoothTemporalRefinementConfig(),
        refinement_eligibility: Callable[[], bool] | None = None,
        cuff_allocator: Any | None = None,
        candidate_audit_solve_indices: frozenset[int] | None = None,
    ) -> None:
        super().__init__(
            config,
            cuff_allocator=cuff_allocator,
            candidate_audit_solve_indices=candidate_audit_solve_indices,
        )
        self.refiner = SmoothTemporalLocalRefiner(config, refinement_config)
        self.refinement_eligibility = refinement_eligibility

    def _refine_selected_sequence(
        self,
        sequence: np.ndarray,
        evaluation: SequenceEvaluation,
        evaluate: Callable[[np.ndarray], SequenceEvaluation],
    ) -> tuple[np.ndarray, SequenceEvaluation, dict[str, Any]]:
        eligible = bool(
            True
            if self.refinement_eligibility is None
            else self.refinement_eligibility()
        )
        if not eligible:
            return sequence, evaluation, {
                "enabled": True,
                "eligible": False,
                "accepted": False,
                "candidate_evaluations": 0,
                "feasible_candidate_evaluations": 0,
                "objective_before": float(evaluation[0]),
                "objective_after": float(evaluation[0]),
                "objective_improvement": 0.0,
                "relative_objective_improvement": 0.0,
                "selected_direction": None,
                "config": self.refiner.config.as_dict(self.config),
                "reason": "existing_dynamics_estimator_not_yet_trusted",
            }
        refined_sequence, refined_evaluation, diagnostics = self.refiner.refine(
            sequence, evaluation, evaluate
        )
        diagnostics["eligible"] = True
        return refined_sequence, refined_evaluation, diagnostics
