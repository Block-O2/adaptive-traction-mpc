"""Cross-Entropy Method solver for Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc.mpc.constraints import Spring2DMPCConstraints
from traction_mpc.mpc.solvers.base import CandidateEvaluator, ConstraintFn, RolloutFn, CostFn, SolverResult


@dataclass(frozen=True)
class CEMSolverConfig:
    horizon: int
    prediction_dt: float
    num_samples: int
    num_elites: int
    iterations: int
    cem_alpha: float
    init_std: np.ndarray
    min_std: np.ndarray
    seed: int
    warm_start: bool = True
    selection: str = "penalized_cost"
    violation_weights: dict[str, float] | None = None
    safety_mode: str = "off"
    safety_violation_weights: dict[str, float] | None = None
    safety_penalty_weight: float = 1.0
    safety_control_dt: float = 0.0
    alpha_constraint_mode: str = "hard"
    alpha_soft_weight: float = 1.0
    alpha_relaxed_multiplier: float = 2.0
    gatekeeper_mode: str = "off"
    gatekeeper_horizon: int = 3
    gatekeeper_top_k: int = 20
    gatekeeper_alpha_max_weight: float = 4.0
    gatekeeper_alpha_sum_weight: float = 4.0
    gatekeeper_omega_max_weight: float = 4.0
    gatekeeper_omega_sum_weight: float = 4.0
    gatekeeper_delta_r_weight: float = 1.0
    gatekeeper_force_weight: float = 1.0
    collect_iteration_diagnostics: bool = False
    collect_sample_diagnostics: bool = False
    action_parameterization_mode: str = "standard"
    num_action_knots: int = 0
    move_block_size: int = 1
    lowpass_beta: float = 0.5
    L0: float = 0.0

    @classmethod
    def from_config(cls, cfg: dict[str, Any], model_params: dict[str, Any]) -> "CEMSolverConfig":
        num_samples = int(cfg.get("num_samples", 128))
        num_elites = int(cfg.get("num_elites", 16))
        if num_elites < 1 or num_elites > num_samples:
            raise ValueError("CEM num_elites must be in [1, num_samples].")
        dt = float(cfg.get("prediction_dt", model_params["dt"]))
        init_std = np.array(
            [
                float(cfg.get("init_std_F_tan", 4.0)),
                float(cfg.get("init_std_F_rad", 0.3)),
            ],
            dtype=float,
        )
        min_std = np.array(
            [
                float(cfg.get("min_std_F_tan", 0.2)),
                float(cfg.get("min_std_F_rad", 0.05)),
            ],
            dtype=float,
        )
        safety_weights = {
            "F_tan": float(cfg.get("safety_violation_weights", {}).get("F_tan", 1.0)),
            "F_rad": float(cfg.get("safety_violation_weights", {}).get("F_rad", 1.0)),
            "delta_r": float(cfg.get("safety_violation_weights", {}).get("delta_r", 1.0)),
            "omega": float(cfg.get("safety_violation_weights", {}).get("omega", 1.0)),
            "alpha": float(cfg.get("safety_violation_weights", {}).get("alpha", 1.0)),
        }
        alpha_constraint_mode = str(cfg.get("alpha_constraint_mode", "hard")).lower()
        if alpha_constraint_mode not in {"hard", "soft", "relaxed"}:
            raise ValueError("alpha_constraint_mode must be one of: hard, soft, relaxed.")
        gatekeeper_mode = str(cfg.get("gatekeeper_mode", "off")).lower()
        if gatekeeper_mode not in {"off", "candidate_select"}:
            raise ValueError("gatekeeper_mode must be one of: off, candidate_select.")
        action_parameterization_mode = str(cfg.get("action_parameterization_mode", "standard")).lower()
        if action_parameterization_mode not in {
            "standard",
            "u_knots",
            "du_knots",
            "move_blocking",
            "lowpass_perturb",
        }:
            raise ValueError(
                "action_parameterization_mode must be one of: "
                "standard, u_knots, du_knots, move_blocking, lowpass_perturb."
            )
        return cls(
            horizon=int(cfg.get("horizon", 18)),
            prediction_dt=dt,
            num_samples=num_samples,
            num_elites=num_elites,
            iterations=int(cfg.get("iterations", 3)),
            cem_alpha=float(cfg.get("cem_alpha", 0.7)),
            init_std=init_std,
            min_std=min_std,
            seed=int(cfg.get("seed", 7)),
            warm_start=bool(cfg.get("warm_start", True)),
            selection=str(cfg.get("selection", "penalized_cost")),
            violation_weights={
                "F_tan": float(cfg.get("violation_weights", {}).get("F_tan", 1.0)),
                "F_rad": float(cfg.get("violation_weights", {}).get("F_rad", 1.0)),
                "delta_r": float(cfg.get("violation_weights", {}).get("delta_r", 1.0)),
                "omega": float(cfg.get("violation_weights", {}).get("omega", 1.0)),
                "alpha": float(cfg.get("violation_weights", {}).get("alpha", 1.0)),
            },
            safety_mode=str(cfg.get("safety_mode", "off")).lower(),
            safety_violation_weights=safety_weights,
            safety_penalty_weight=float(cfg.get("safety_penalty_weight", 1.0)),
            safety_control_dt=float(cfg.get("safety_control_dt", model_params["dt"])),
            alpha_constraint_mode=alpha_constraint_mode,
            alpha_soft_weight=float(cfg.get("alpha_soft_weight", safety_weights["alpha"])),
            alpha_relaxed_multiplier=float(cfg.get("alpha_relaxed_multiplier", 2.0)),
            gatekeeper_mode=gatekeeper_mode,
            gatekeeper_horizon=int(cfg.get("gatekeeper_horizon", 3)),
            gatekeeper_top_k=int(cfg.get("gatekeeper_top_k", 20)),
            gatekeeper_alpha_max_weight=float(cfg.get("gatekeeper_alpha_max_weight", 4.0)),
            gatekeeper_alpha_sum_weight=float(cfg.get("gatekeeper_alpha_sum_weight", 4.0)),
            gatekeeper_omega_max_weight=float(cfg.get("gatekeeper_omega_max_weight", 4.0)),
            gatekeeper_omega_sum_weight=float(cfg.get("gatekeeper_omega_sum_weight", 4.0)),
            gatekeeper_delta_r_weight=float(cfg.get("gatekeeper_delta_r_weight", 1.0)),
            gatekeeper_force_weight=float(cfg.get("gatekeeper_force_weight", 1.0)),
            collect_iteration_diagnostics=bool(cfg.get("collect_iteration_diagnostics", False)),
            collect_sample_diagnostics=bool(cfg.get("collect_sample_diagnostics", False)),
            action_parameterization_mode=action_parameterization_mode,
            num_action_knots=int(cfg.get("num_action_knots", 0)),
            move_block_size=max(1, int(cfg.get("move_block_size", 1))),
            lowpass_beta=float(np.clip(float(cfg.get("lowpass_beta", 0.5)), 0.0, 1.0)),
            L0=float(model_params["L0"]),
        )


class CEMSolver:
    """Cross-Entropy Method optimizer over action sequences."""

    def __init__(
        self,
        solver_config: CEMSolverConfig,
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
        mean = self._initial_params(initial_sequence)
        std = np.tile(self.config.init_std.reshape(1, 2), (mean.shape[0], 1))
        min_std = np.tile(self.config.min_std.reshape(1, 2), (mean.shape[0], 1))
        evaluator = CandidateEvaluator(x0, rollout_fn, cost_fn, constraint_fn)

        best_sequence = self._params_to_sequence(mean)
        best_total_cost = np.inf
        best_task_cost = np.inf
        best_violation_score = np.inf
        best_ranking_cost = np.inf
        best_safety_score = np.inf
        best_safety_raw_score = np.inf
        best_safety_feasible = False
        best_safety_stats = {}
        best_feasible = False
        best_constraint = None
        best_sort_key = (True, np.inf, np.inf, np.inf)
        best_selected_from = "infeasible"
        best_elite_feasible_count = 0
        best_elite_safety_feasible_count = 0
        best_rank = 0
        feasible_count_total = 0
        safety_feasible_count_total = 0
        safety_feasible_excluding_alpha_count_total = 0
        alpha_original_feasible_count_total = 0
        alpha_relaxed_feasible_count_total = 0
        num_candidates_total = 0
        iteration_diagnostics: list[dict[str, Any]] = []
        sample_diagnostics: list[dict[str, Any]] = []
        gatekeeper_diagnostics = self._disabled_gatekeeper_diagnostics()

        for iteration_index in range(self.config.iterations):
            param_candidates = self._sample_param_candidates(mean, std)
            param_candidates[0] = mean
            candidates = np.asarray(
                [self._params_to_sequence(params) for params in param_candidates],
                dtype=float,
            )
            total_costs = np.empty(candidates.shape[0], dtype=float)
            ranking_costs = np.empty(candidates.shape[0], dtype=float)
            task_costs = np.empty(candidates.shape[0], dtype=float)
            violation_scores = np.empty(candidates.shape[0], dtype=float)
            safety_scores = np.empty(candidates.shape[0], dtype=float)
            safety_raw_scores = np.empty(candidates.shape[0], dtype=float)
            safety_feasible = np.empty(candidates.shape[0], dtype=bool)
            safety_feasible_excluding_alpha = np.empty(candidates.shape[0], dtype=bool)
            alpha_original_feasible = np.empty(candidates.shape[0], dtype=bool)
            alpha_relaxed_feasible = np.empty(candidates.shape[0], dtype=bool)
            feasible = np.empty(candidates.shape[0], dtype=bool)
            constraints = []
            safety_stats = []
            rollouts = []
            for i, sequence in enumerate(candidates):
                evaluation = evaluator.evaluate_detailed(sequence)
                total_costs[i] = evaluation.total_cost
                task_costs[i] = evaluation.task_cost
                feasible[i] = evaluation.feasible
                constraint = evaluation.constraint
                violation_scores[i] = self._violation_score(constraint)
                stats = self._safety_violation_stats(sequence, evaluation.rollout)
                safety_scores[i] = stats["total_normalized_score"]
                safety_raw_scores[i] = stats["total_raw_score"]
                safety_feasible[i] = stats["safety_feasible"]
                safety_feasible_excluding_alpha[i] = stats["safety_feasible_excluding_alpha"]
                alpha_original_feasible[i] = stats["alpha_original_feasible"]
                alpha_relaxed_feasible[i] = stats["alpha_relaxed_feasible"]
                ranking_costs[i] = self._ranking_cost(task_costs[i], total_costs[i], safety_scores[i])
                constraints.append(constraint)
                safety_stats.append(stats)
                rollouts.append(evaluation.rollout)

            feasible_count_total += int(np.count_nonzero(feasible))
            safety_feasible_count_total += int(np.count_nonzero(safety_feasible))
            safety_feasible_excluding_alpha_count_total += int(np.count_nonzero(safety_feasible_excluding_alpha))
            alpha_original_feasible_count_total += int(np.count_nonzero(alpha_original_feasible))
            alpha_relaxed_feasible_count_total += int(np.count_nonzero(alpha_relaxed_feasible))
            num_candidates_total += int(candidates.shape[0])
            order = self._candidate_order(
                feasible,
                safety_feasible,
                violation_scores,
                safety_scores,
                task_costs,
                total_costs,
                ranking_costs,
            )
            elite_order = order[: self.config.num_elites]
            elite_feasible_count = int(np.count_nonzero(feasible[elite_order]))
            elite_safety_feasible_count = int(np.count_nonzero(safety_feasible[elite_order]))
            best_idx = int(order[0])
            if self.config.collect_iteration_diagnostics:
                iteration_diagnostics.append(
                    self._iteration_diagnostics(
                        iteration_index + 1,
                        feasible,
                        safety_feasible,
                        task_costs,
                        safety_scores,
                        ranking_costs,
                        elite_order,
                        best_idx,
                        safety_stats,
                        candidates,
                    )
                )
            if self.config.collect_sample_diagnostics:
                sample_diagnostics.extend(
                    self._sample_diagnostics(
                        iteration_index + 1,
                        feasible,
                        safety_feasible,
                        task_costs,
                        safety_scores,
                        ranking_costs,
                        elite_order,
                        best_idx,
                        safety_stats,
                    )
                )
            candidate_sort_key = self._sort_key(
                bool(feasible[best_idx]),
                bool(safety_feasible[best_idx]),
                float(violation_scores[best_idx]),
                float(safety_scores[best_idx]),
                float(task_costs[best_idx]),
                float(total_costs[best_idx]),
                float(ranking_costs[best_idx]),
            )
            if self._is_better(candidate_sort_key, best_sort_key):
                best_sort_key = candidate_sort_key
                best_total_cost = float(total_costs[best_idx])
                best_task_cost = float(task_costs[best_idx])
                best_violation_score = float(violation_scores[best_idx])
                best_ranking_cost = float(ranking_costs[best_idx])
                best_safety_score = float(safety_scores[best_idx])
                best_safety_raw_score = float(safety_raw_scores[best_idx])
                best_safety_feasible = bool(safety_feasible[best_idx])
                best_safety_stats = dict(safety_stats[best_idx])
                best_sequence = candidates[best_idx].copy()
                best_feasible = bool(feasible[best_idx])
                best_constraint = constraints[best_idx]
                best_selected_from = "feasible" if best_feasible and best_safety_feasible else "infeasible"
                best_elite_feasible_count = elite_feasible_count
                best_elite_safety_feasible_count = elite_safety_feasible_count
                best_rank = 0

            if iteration_index == self.config.iterations - 1 and self.config.gatekeeper_mode == "candidate_select":
                (
                    gatekeeper_idx,
                    gatekeeper_rank,
                    gatekeeper_diagnostics,
                ) = self._gatekeeper_select(order, candidates, rollouts, task_costs)
                best_sequence = candidates[gatekeeper_idx].copy()
                best_total_cost = float(total_costs[gatekeeper_idx])
                best_task_cost = float(task_costs[gatekeeper_idx])
                best_violation_score = float(violation_scores[gatekeeper_idx])
                best_ranking_cost = float(ranking_costs[gatekeeper_idx])
                best_safety_score = float(safety_scores[gatekeeper_idx])
                best_safety_raw_score = float(safety_raw_scores[gatekeeper_idx])
                best_safety_feasible = bool(safety_feasible[gatekeeper_idx])
                best_safety_stats = dict(safety_stats[gatekeeper_idx])
                best_feasible = bool(feasible[gatekeeper_idx])
                best_constraint = constraints[gatekeeper_idx]
                best_selected_from = "gatekeeper_top_k" if gatekeeper_diagnostics["gatekeeper_intervened"] else "cem_nominal"
                best_elite_feasible_count = elite_feasible_count
                best_elite_safety_feasible_count = elite_safety_feasible_count
                best_rank = int(gatekeeper_rank)

            elites = param_candidates[elite_order]
            elite_mean = elites.mean(axis=0)
            elite_std = np.maximum(elites.std(axis=0), min_std)
            mean = (1.0 - self.config.cem_alpha) * mean + self.config.cem_alpha * elite_mean
            std = (1.0 - self.config.cem_alpha) * std + self.config.cem_alpha * elite_std
            mean = self._clip_params(mean)
            std = np.maximum(std, min_std)

        if best_constraint is None:
            raise RuntimeError("CEM did not evaluate any candidates.")
        action = self.constraints.clip_action(best_sequence[0])
        final_mean_sequence = self._params_to_sequence(mean)
        return SolverResult(
            best_action=action,
            best_sequence=best_sequence,
            best_cost=best_total_cost,
            feasible=best_feasible,
            feasible_count=feasible_count_total,
            num_candidates=num_candidates_total,
            max_pred_alpha=float(best_constraint.max_pred_alpha),
            max_pred_omega=float(best_constraint.max_pred_omega),
            max_pred_delta_r=float(best_constraint.max_pred_delta_r),
            diagnostics={
                "solver_type": "cem",
                "iterations": int(self.config.iterations),
                "num_samples": int(self.config.num_samples),
                "num_elites": int(self.config.num_elites),
                "cem_alpha": float(self.config.cem_alpha),
                "warm_start": bool(self.config.warm_start),
                "selection": self.config.selection,
                "safety_mode": self.config.safety_mode,
                "safety_penalty_weight": float(self.config.safety_penalty_weight),
                "safety_control_dt": float(self._safety_control_dt()),
                "alpha_constraint_mode": self.config.alpha_constraint_mode,
                "alpha_soft_weight": float(self.config.alpha_soft_weight),
                "alpha_relaxed_multiplier": float(self.config.alpha_relaxed_multiplier),
                "gatekeeper_mode": self.config.gatekeeper_mode,
                "gatekeeper_horizon": int(self.config.gatekeeper_horizon),
                "gatekeeper_top_k": int(self.config.gatekeeper_top_k),
                "gatekeeper_alpha_max_weight": float(self.config.gatekeeper_alpha_max_weight),
                "gatekeeper_alpha_sum_weight": float(self.config.gatekeeper_alpha_sum_weight),
                "gatekeeper_omega_max_weight": float(self.config.gatekeeper_omega_max_weight),
                "gatekeeper_omega_sum_weight": float(self.config.gatekeeper_omega_sum_weight),
                "gatekeeper_delta_r_weight": float(self.config.gatekeeper_delta_r_weight),
                "gatekeeper_force_weight": float(self.config.gatekeeper_force_weight),
                "collect_iteration_diagnostics": bool(self.config.collect_iteration_diagnostics),
                "collect_sample_diagnostics": bool(self.config.collect_sample_diagnostics),
                "action_parameterization_mode": self.config.action_parameterization_mode,
                "num_action_knots": int(self.config.num_action_knots),
                "move_block_size": int(self.config.move_block_size),
                "lowpass_beta": float(self.config.lowpass_beta),
                "best_task_cost": float(best_task_cost),
                "best_ranking_cost": float(best_ranking_cost),
                "best_violation_score": float(best_violation_score),
                "best_safety_score": float(best_safety_score),
                "best_safety_raw_score": float(best_safety_raw_score),
                "best_safety_feasible": bool(best_safety_feasible),
                "safety_feasible_count": int(safety_feasible_count_total),
                "safety_feasible_ratio": (
                    float(safety_feasible_count_total / num_candidates_total) if num_candidates_total else 0.0
                ),
                "safety_feasible_excluding_alpha_count": int(safety_feasible_excluding_alpha_count_total),
                "safety_feasible_excluding_alpha_ratio": (
                    float(safety_feasible_excluding_alpha_count_total / num_candidates_total)
                    if num_candidates_total
                    else 0.0
                ),
                "alpha_original_feasible_count": int(alpha_original_feasible_count_total),
                "alpha_original_feasible_ratio": (
                    float(alpha_original_feasible_count_total / num_candidates_total) if num_candidates_total else 0.0
                ),
                "alpha_relaxed_feasible_count": int(alpha_relaxed_feasible_count_total),
                "alpha_relaxed_feasible_ratio": (
                    float(alpha_relaxed_feasible_count_total / num_candidates_total) if num_candidates_total else 0.0
                ),
                "best_max_violation_F_tan": float(best_constraint.max_violation_F_tan),
                "best_max_violation_F_rad": float(best_constraint.max_violation_F_rad),
                "best_max_violation_delta_r": float(best_constraint.max_violation_delta_r),
                "best_max_violation_omega": float(best_constraint.max_violation_omega),
                "best_max_violation_alpha": float(best_constraint.max_violation_alpha),
                "elite_feasible_count": int(best_elite_feasible_count),
                "elite_safety_feasible_count": int(best_elite_safety_feasible_count),
                "selected_candidate_rank": int(best_rank),
                "best_selected_from": best_selected_from,
                "final_mean_first_F_tan": float(final_mean_sequence[0, 0]),
                "final_mean_first_F_rad": float(final_mean_sequence[0, 1]),
                "final_std_first_F_tan": float(std[0, 0]),
                "final_std_first_F_rad": float(std[0, 1]),
                "cem_iteration_diagnostics": iteration_diagnostics,
                "cem_sample_diagnostics": sample_diagnostics,
                **gatekeeper_diagnostics,
                **{f"selected_safety_{key}": value for key, value in best_safety_stats.items()},
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

    def _initial_params(self, initial_sequence: np.ndarray | None) -> np.ndarray:
        sequence = self._initial_mean(initial_sequence)
        mode = self.config.action_parameterization_mode
        if mode in {"standard", "lowpass_perturb"}:
            return sequence
        if mode == "move_blocking":
            block = max(1, int(self.config.move_block_size))
            starts = list(range(0, self.config.horizon, block))
            return sequence[starts].copy()
        knot_indices = self._knot_indices()
        if mode == "u_knots":
            return sequence[knot_indices].copy()
        if mode == "du_knots":
            deltas = np.diff(np.vstack([np.zeros((1, 2), dtype=float), sequence]), axis=0)
            return deltas[knot_indices].copy()
        raise ValueError(f"Unknown action_parameterization_mode: {mode}")

    def _sample_param_candidates(self, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        samples = self.rng.normal(loc=mean, scale=std, size=(self.config.num_samples, mean.shape[0], 2))
        if self.config.action_parameterization_mode == "lowpass_perturb":
            perturb = samples - mean.reshape(1, mean.shape[0], 2)
            filtered = perturb.copy()
            beta = float(self.config.lowpass_beta)
            for k in range(1, filtered.shape[1]):
                filtered[:, k, :] = beta * filtered[:, k - 1, :] + (1.0 - beta) * filtered[:, k, :]
            samples = mean.reshape(1, mean.shape[0], 2) + filtered
        return self._clip_param_candidates(samples)

    def _sample_candidates(self, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        samples = self._sample_param_candidates(mean, std)
        if self.config.action_parameterization_mode in {"standard", "lowpass_perturb"}:
            return samples
        return np.asarray([self._params_to_sequence(params) for params in samples], dtype=float)

    def _clip_param_candidates(self, samples: np.ndarray) -> np.ndarray:
        clipped = np.asarray(samples, dtype=float).copy()
        if self.config.action_parameterization_mode != "du_knots":
            clipped[..., 0] = np.clip(clipped[..., 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
            clipped[..., 1] = np.clip(clipped[..., 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return clipped

    def _clip_params(self, params: np.ndarray) -> np.ndarray:
        clipped = np.asarray(params, dtype=float).copy()
        if self.config.action_parameterization_mode != "du_knots":
            clipped[:, 0] = np.clip(clipped[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
            clipped[:, 1] = np.clip(clipped[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return clipped

    def _knot_count(self) -> int:
        if self.config.action_parameterization_mode in {"u_knots", "du_knots"}:
            default = min(6, self.config.horizon)
            return max(2, min(int(self.config.num_action_knots or default), self.config.horizon))
        return self.config.horizon

    def _knot_indices(self) -> np.ndarray:
        return np.unique(
            np.rint(np.linspace(0, self.config.horizon - 1, self._knot_count())).astype(int)
        )

    def _interpolate_knots(self, knots: np.ndarray) -> np.ndarray:
        knot_values = np.asarray(knots, dtype=float)
        knot_indices = self._knot_indices()
        if len(knot_indices) != len(knot_values):
            knot_indices = np.rint(np.linspace(0, self.config.horizon - 1, len(knot_values))).astype(int)
        horizon_indices = np.arange(self.config.horizon, dtype=float)
        sequence = np.column_stack(
            [
                np.interp(horizon_indices, knot_indices.astype(float), knot_values[:, action_index])
                for action_index in range(2)
            ]
        )
        return sequence

    def _params_to_sequence(self, params: np.ndarray) -> np.ndarray:
        mode = self.config.action_parameterization_mode
        param_values = np.asarray(params, dtype=float)
        if mode in {"standard", "lowpass_perturb"}:
            sequence = param_values.copy()
        elif mode == "move_blocking":
            sequence = np.repeat(param_values, max(1, int(self.config.move_block_size)), axis=0)[: self.config.horizon]
        elif mode == "u_knots":
            sequence = self._interpolate_knots(param_values)
        elif mode == "du_knots":
            delta_sequence = self._interpolate_knots(param_values)
            sequence = np.cumsum(delta_sequence, axis=0)
        else:
            raise ValueError(f"Unknown action_parameterization_mode: {mode}")
        sequence[:, 0] = np.clip(sequence[:, 0], -self.constraints.F_tan_max, self.constraints.F_tan_max)
        sequence[:, 1] = np.clip(sequence[:, 1], -self.constraints.F_rad_max, self.constraints.F_rad_max)
        return sequence

    def _candidate_order(
        self,
        feasible: np.ndarray,
        safety_feasible: np.ndarray,
        violation_scores: np.ndarray,
        safety_scores: np.ndarray,
        task_costs: np.ndarray,
        total_costs: np.ndarray,
        ranking_costs: np.ndarray,
    ) -> np.ndarray:
        if self.config.safety_mode == "soft_penalty":
            return np.argsort(ranking_costs)
        if self.config.safety_mode == "feasibility_first":
            if self.config.alpha_constraint_mode in {"soft", "relaxed"}:
                return np.lexsort((ranking_costs, np.logical_not(safety_feasible)))
            return np.lexsort((total_costs, np.logical_not(safety_feasible)))
        if self.config.safety_mode == "lexicographic":
            return np.lexsort((task_costs, safety_scores))
        if self.config.selection == "feasibility_first":
            return np.lexsort((task_costs, violation_scores, np.logical_not(feasible)))
        return np.argsort(total_costs)

    def _sort_key(
        self,
        feasible: bool,
        safety_feasible: bool,
        violation_score: float,
        safety_score: float,
        task_cost: float,
        total_cost: float,
        ranking_cost: float,
    ) -> tuple[bool, float, float, float]:
        if self.config.safety_mode == "soft_penalty":
            return (False, ranking_cost, total_cost, task_cost)
        if self.config.safety_mode == "feasibility_first":
            if self.config.alpha_constraint_mode in {"soft", "relaxed"}:
                return (not safety_feasible, ranking_cost, total_cost, task_cost)
            return (not safety_feasible, total_cost, safety_score, task_cost)
        if self.config.safety_mode == "lexicographic":
            return (False, safety_score, task_cost, total_cost)
        if self.config.selection == "feasibility_first":
            return (not feasible, violation_score, task_cost, total_cost)
        return (False, total_cost, task_cost, safety_score)

    def _is_better(
        self,
        candidate_key: tuple[bool, float, float, float],
        best_key: tuple[bool, float, float, float],
    ) -> bool:
        return candidate_key < best_key

    def _ranking_cost(self, task_cost: float, total_cost: float, safety_score: float) -> float:
        if self.config.safety_mode == "soft_penalty":
            if self.config.alpha_constraint_mode in {"soft", "relaxed"}:
                return float(task_cost + self.config.safety_penalty_weight * safety_score)
            return float(total_cost + self.config.safety_penalty_weight * safety_score)
        if self.config.safety_mode == "feasibility_first" and self.config.alpha_constraint_mode in {
            "soft",
            "relaxed",
        }:
            return float(task_cost + self.config.safety_penalty_weight * safety_score)
        return float(total_cost)

    def _violation_score(self, constraint) -> float:
        if self.config.selection == "feasibility_first" and not np.isfinite(constraint.penalty):
            return float("inf")
        weights = self.config.violation_weights or {}
        score = (
            float(weights.get("F_tan", 1.0)) * constraint.max_violation_F_tan**2
            + float(weights.get("F_rad", 1.0)) * constraint.max_violation_F_rad**2
            + float(weights.get("delta_r", 1.0)) * constraint.max_violation_delta_r**2
            + float(weights.get("omega", 1.0)) * constraint.max_violation_omega**2
            + float(weights.get("alpha", 1.0)) * constraint.max_violation_alpha**2
        )
        if not np.isfinite(score):
            return float("inf")
        if not np.isfinite(constraint.penalty):
            return float("inf")
        return float(score)

    def _safety_control_dt(self) -> float:
        return float(self.config.safety_control_dt)

    def _safety_violation_stats(self, sequence: np.ndarray, rollout) -> dict[str, Any]:
        if not rollout.valid or len(rollout.states) < 2:
            return self._invalid_safety_stats()
        total_normalized_score = 0.0
        total_normalized_score_excluding_alpha = 0.0
        total_normalized_alpha_score = 0.0
        total_raw_score = 0.0
        violation_count = 0
        max_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        mean_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        one_step_norm = {name: np.nan for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        one_step_score = np.nan
        steps = min(len(rollout.actions), max(0, len(rollout.states) - 1), len(sequence))
        for k in range(steps):
            raw_action = np.asarray(sequence[k], dtype=float)
            prev_x = np.asarray(rollout.states[k], dtype=float)
            x = np.asarray(rollout.states[k + 1], dtype=float)
            alpha = (float(x[1]) - float(prev_x[1])) / self._safety_control_dt()
            delta_r = float(x[2] - self.config.L0)
            raw = {
                "F_tan": max(0.0, abs(float(raw_action[0])) - self.constraints.F_tan_max),
                "F_rad": max(0.0, abs(float(raw_action[1])) - self.constraints.F_rad_max),
                "delta_r": max(0.0, abs(delta_r) - self.constraints.delta_r_max),
                "omega": max(0.0, abs(float(x[1])) - self.constraints.omega_max),
                "alpha": max(0.0, abs(alpha) - self.constraints.alpha_max),
            }
            norm = {
                "F_tan": self._normalize(raw["F_tan"], self.constraints.F_tan_max),
                "F_rad": self._normalize(raw["F_rad"], self.constraints.F_rad_max),
                "delta_r": self._normalize(raw["delta_r"], self.constraints.delta_r_max),
                "omega": self._normalize(raw["omega"], self.constraints.omega_max),
                "alpha": self._normalize(raw["alpha"], self.constraints.alpha_max),
            }
            step_raw_score = sum(self._safety_weight(name) * raw[name] ** 2 for name in raw)
            step_norm_score = sum(self._safety_weight(name) * norm[name] ** 2 for name in norm)
            step_norm_score_excluding_alpha = sum(
                self._safety_weight(name) * norm[name] ** 2
                for name in ["F_tan", "F_rad", "delta_r", "omega"]
            )
            step_alpha_score = self._safety_weight("alpha") * norm["alpha"] ** 2
            if k == 0:
                one_step_norm = {name: float(value) for name, value in norm.items()}
                one_step_score = float(step_norm_score)
            total_raw_score += step_raw_score
            total_normalized_score += step_norm_score
            total_normalized_score_excluding_alpha += step_norm_score_excluding_alpha
            total_normalized_alpha_score += step_alpha_score
            if step_norm_score > 0.0:
                violation_count += 1
            for name, value in norm.items():
                max_norm[name] = max(max_norm[name], float(value))
                mean_norm[name] += float(value)
        if steps > 0:
            for name in mean_norm:
                mean_norm[name] /= float(steps)
        if not np.isfinite(total_normalized_score) or not np.isfinite(total_raw_score):
            return self._invalid_safety_stats()
        safety_feasible_excluding_alpha = all(
            float(max_norm[name]) <= 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega"]
        )
        alpha_original_feasible = float(max_norm["alpha"]) <= 0.0
        alpha_relaxed_threshold = max(0.0, float(self.config.alpha_relaxed_multiplier) - 1.0)
        alpha_relaxed_feasible = float(max_norm["alpha"]) <= alpha_relaxed_threshold
        safety_feasible = self._safety_feasible(
            safety_feasible_excluding_alpha,
            alpha_original_feasible,
            alpha_relaxed_feasible,
        )
        stats = {
            "total_normalized_score": float(total_normalized_score),
            "total_normalized_score_excluding_alpha": float(total_normalized_score_excluding_alpha),
            "total_normalized_alpha_score": float(total_normalized_alpha_score),
            "total_raw_score": float(total_raw_score),
            "safety_feasible": bool(safety_feasible),
            "safety_feasible_excluding_alpha": bool(safety_feasible_excluding_alpha),
            "alpha_original_feasible": bool(alpha_original_feasible),
            "alpha_relaxed_feasible": bool(alpha_relaxed_feasible),
            "alpha_relaxed_threshold_normalized": float(alpha_relaxed_threshold),
            "violation_count": int(violation_count),
        }
        stats.update({f"max_normalized_violation_{name}": float(value) for name, value in max_norm.items()})
        stats.update({f"mean_normalized_violation_{name}": float(value) for name, value in mean_norm.items()})
        stats.update({f"one_step_normalized_violation_{name}": float(value) for name, value in one_step_norm.items()})
        stats["one_step_total_normalized_score"] = float(one_step_score)
        return stats

    def _safety_weight(self, name: str) -> float:
        if name == "alpha":
            return float(self.config.alpha_soft_weight)
        return float((self.config.safety_violation_weights or {}).get(name, 1.0))

    def _gatekeeper_select(
        self,
        order: np.ndarray,
        candidates: np.ndarray,
        rollouts: list[Any],
        task_costs: np.ndarray,
    ) -> tuple[int, int, dict[str, Any]]:
        top_k = max(1, min(int(self.config.gatekeeper_top_k), len(order)))
        top_indices = [int(index) for index in order[:top_k]]
        nominal_idx = int(order[0])
        nominal_rank = 0
        scores = {
            index: self._gatekeeper_score(candidates[index], rollouts[index])
            for index in top_indices
        }
        nominal_score = float(scores[nominal_idx]["score"])
        selected_idx = nominal_idx
        selected_rank = nominal_rank
        if nominal_score > 0.0:
            ranked = []
            for rank, index in enumerate(top_indices):
                ranked.append((float(scores[index]["score"]), float(task_costs[index]), rank, index))
            _, _, selected_rank, selected_idx = min(ranked)
        selected_score = float(scores[selected_idx]["score"])
        diagnostics = {
            "gatekeeper_mode": self.config.gatekeeper_mode,
            "gatekeeper_horizon": int(self.config.gatekeeper_horizon),
            "gatekeeper_top_k": int(top_k),
            "gatekeeper_intervened": bool(selected_idx != nominal_idx),
            "gatekeeper_nominal_rank": int(nominal_rank),
            "gatekeeper_selected_rank": int(selected_rank),
            "gatekeeper_nominal_candidate_index": int(nominal_idx),
            "gatekeeper_selected_candidate_index": int(selected_idx),
            "gatekeeper_nominal_safety_score": nominal_score,
            "gatekeeper_selected_safety_score": selected_score,
            "gatekeeper_nominal_task_cost": float(task_costs[nominal_idx]),
            "gatekeeper_selected_task_cost": float(task_costs[selected_idx]),
            "gatekeeper_alpha_max_weight": float(self.config.gatekeeper_alpha_max_weight),
            "gatekeeper_alpha_sum_weight": float(self.config.gatekeeper_alpha_sum_weight),
            "gatekeeper_omega_max_weight": float(self.config.gatekeeper_omega_max_weight),
            "gatekeeper_omega_sum_weight": float(self.config.gatekeeper_omega_sum_weight),
            "gatekeeper_delta_r_weight": float(self.config.gatekeeper_delta_r_weight),
            "gatekeeper_force_weight": float(self.config.gatekeeper_force_weight),
        }
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            diagnostics[f"gatekeeper_nominal_max_norm_violation_{name}"] = float(
                scores[nominal_idx][f"max_norm_{name}"]
            )
            diagnostics[f"gatekeeper_selected_max_norm_violation_{name}"] = float(
                scores[selected_idx][f"max_norm_{name}"]
            )
            diagnostics[f"gatekeeper_nominal_sum_norm_violation_{name}"] = float(
                scores[nominal_idx][f"sum_norm_{name}"]
            )
            diagnostics[f"gatekeeper_selected_sum_norm_violation_{name}"] = float(
                scores[selected_idx][f"sum_norm_{name}"]
            )
        return int(selected_idx), int(selected_rank), diagnostics

    def _gatekeeper_score(self, sequence: np.ndarray, rollout) -> dict[str, float]:
        if not rollout.valid or len(rollout.states) < 2:
            invalid = {"score": float("inf")}
            for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
                invalid[f"max_norm_{name}"] = float("inf")
                invalid[f"sum_norm_{name}"] = float("inf")
            return invalid
        max_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        sum_norm = {name: 0.0 for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}
        steps = min(
            int(self.config.gatekeeper_horizon),
            len(rollout.actions),
            max(0, len(rollout.states) - 1),
            len(sequence),
        )
        for k in range(steps):
            raw_action = np.asarray(sequence[k], dtype=float)
            prev_x = np.asarray(rollout.states[k], dtype=float)
            x = np.asarray(rollout.states[k + 1], dtype=float)
            alpha = (float(x[1]) - float(prev_x[1])) / self._safety_control_dt()
            delta_r = float(x[2] - self.config.L0)
            raw = {
                "F_tan": max(0.0, abs(float(raw_action[0])) - self.constraints.F_tan_max),
                "F_rad": max(0.0, abs(float(raw_action[1])) - self.constraints.F_rad_max),
                "delta_r": max(0.0, abs(delta_r) - self.constraints.delta_r_max),
                "omega": max(0.0, abs(float(x[1])) - self.constraints.omega_max),
                "alpha": max(0.0, abs(alpha) - self.constraints.alpha_max),
            }
            norm = {
                "F_tan": self._normalize(raw["F_tan"], self.constraints.F_tan_max),
                "F_rad": self._normalize(raw["F_rad"], self.constraints.F_rad_max),
                "delta_r": self._normalize(raw["delta_r"], self.constraints.delta_r_max),
                "omega": self._normalize(raw["omega"], self.constraints.omega_max),
                "alpha": self._normalize(raw["alpha"], self.constraints.alpha_max),
            }
            for name, value in norm.items():
                max_norm[name] = max(max_norm[name], float(value))
                sum_norm[name] += float(value)
        score = (
            float(self.config.gatekeeper_alpha_max_weight) * max_norm["alpha"]
            + float(self.config.gatekeeper_alpha_sum_weight) * sum_norm["alpha"]
            + float(self.config.gatekeeper_omega_max_weight) * max_norm["omega"]
            + float(self.config.gatekeeper_omega_sum_weight) * sum_norm["omega"]
            + float(self.config.gatekeeper_delta_r_weight) * (max_norm["delta_r"] + sum_norm["delta_r"])
            + float(self.config.gatekeeper_force_weight)
            * (
                max_norm["F_tan"]
                + sum_norm["F_tan"]
                + max_norm["F_rad"]
                + sum_norm["F_rad"]
            )
        )
        result = {"score": float(score)}
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            result[f"max_norm_{name}"] = float(max_norm[name])
            result[f"sum_norm_{name}"] = float(sum_norm[name])
        return result

    def _disabled_gatekeeper_diagnostics(self) -> dict[str, Any]:
        result = {
            "gatekeeper_mode": self.config.gatekeeper_mode,
            "gatekeeper_horizon": int(self.config.gatekeeper_horizon),
            "gatekeeper_top_k": int(self.config.gatekeeper_top_k),
            "gatekeeper_intervened": False,
            "gatekeeper_nominal_rank": 0,
            "gatekeeper_selected_rank": 0,
            "gatekeeper_nominal_candidate_index": 0,
            "gatekeeper_selected_candidate_index": 0,
            "gatekeeper_nominal_safety_score": 0.0,
            "gatekeeper_selected_safety_score": 0.0,
            "gatekeeper_nominal_task_cost": float("nan"),
            "gatekeeper_selected_task_cost": float("nan"),
            "gatekeeper_alpha_max_weight": float(self.config.gatekeeper_alpha_max_weight),
            "gatekeeper_alpha_sum_weight": float(self.config.gatekeeper_alpha_sum_weight),
            "gatekeeper_omega_max_weight": float(self.config.gatekeeper_omega_max_weight),
            "gatekeeper_omega_sum_weight": float(self.config.gatekeeper_omega_sum_weight),
            "gatekeeper_delta_r_weight": float(self.config.gatekeeper_delta_r_weight),
            "gatekeeper_force_weight": float(self.config.gatekeeper_force_weight),
        }
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            result[f"gatekeeper_nominal_max_norm_violation_{name}"] = float("nan")
            result[f"gatekeeper_selected_max_norm_violation_{name}"] = float("nan")
            result[f"gatekeeper_nominal_sum_norm_violation_{name}"] = float("nan")
            result[f"gatekeeper_selected_sum_norm_violation_{name}"] = float("nan")
        return result

    def _safety_feasible(
        self,
        safety_feasible_excluding_alpha: bool,
        alpha_original_feasible: bool,
        alpha_relaxed_feasible: bool,
    ) -> bool:
        if not safety_feasible_excluding_alpha:
            return False
        if self.config.alpha_constraint_mode == "soft":
            return True
        if self.config.alpha_constraint_mode == "relaxed":
            return bool(alpha_relaxed_feasible)
        return bool(alpha_original_feasible)

    def _iteration_diagnostics(
        self,
        iteration: int,
        feasible: np.ndarray,
        safety_feasible: np.ndarray,
        task_costs: np.ndarray,
        safety_scores: np.ndarray,
        ranking_costs: np.ndarray,
        elite_order: np.ndarray,
        best_idx: int,
        safety_stats: list[dict[str, Any]],
        candidates: np.ndarray,
    ) -> dict[str, Any]:
        per_constraint = self._per_constraint_feasibility(safety_stats)
        selected_stats = safety_stats[best_idx]
        one_step = self._first_step_violation(candidates[best_idx], selected_stats)
        num_samples = int(len(task_costs))
        row: dict[str, Any] = {
            "cem_iteration": int(iteration),
            "alpha_constraint_mode": self.config.alpha_constraint_mode,
            "alpha_soft_weight": float(self.config.alpha_soft_weight),
            "alpha_relaxed_multiplier": float(self.config.alpha_relaxed_multiplier),
            "num_sampled_trajectories": num_samples,
            "num_elites": int(len(elite_order)),
            "feasible_all_count": int(np.count_nonzero(feasible)),
            "feasible_all_ratio": self._safe_ratio(float(np.count_nonzero(feasible)), float(num_samples)),
            "safety_feasible_count": int(np.count_nonzero(safety_feasible)),
            "safety_feasible_ratio": self._safe_ratio(float(np.count_nonzero(safety_feasible)), float(num_samples)),
            "selected_trajectory_task_cost": float(task_costs[best_idx]),
            "selected_trajectory_safety_cost": float(safety_scores[best_idx]),
            "selected_trajectory_total_cost": float(ranking_costs[best_idx]),
            "selected_pred_one_step_violation": float(one_step["one_step_total_normalized_score"]),
            "selected_pred_horizon_violation": float(selected_stats["total_normalized_score"]),
            "selected_pred_horizon_violation_excluding_alpha": float(
                selected_stats["total_normalized_score_excluding_alpha"]
            ),
            "selected_pred_horizon_alpha_cost": float(selected_stats["total_normalized_alpha_score"]),
            "selected_pred_one_step_violation_F_tan": float(one_step["one_step_normalized_violation_F_tan"]),
            "selected_pred_one_step_violation_F_rad": float(one_step["one_step_normalized_violation_F_rad"]),
            "selected_pred_one_step_violation_delta_r": float(one_step["one_step_normalized_violation_delta_r"]),
            "selected_pred_one_step_violation_omega": float(one_step["one_step_normalized_violation_omega"]),
            "selected_pred_one_step_violation_alpha": float(one_step["one_step_normalized_violation_alpha"]),
        }
        row.update(per_constraint)
        row.update(self._distribution("task_cost", task_costs))
        row.update(self._distribution("safety_cost", safety_scores))
        row.update(self._distribution("total_cost_used_for_ranking", ranking_costs))
        row.update(self._distribution("elite_task_cost", task_costs[elite_order]))
        row.update(self._distribution("elite_safety_cost", safety_scores[elite_order]))
        row.update(self._distribution("elite_total_cost_used_for_ranking", ranking_costs[elite_order]))
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            row[f"selected_horizon_violation_{name}"] = float(
                selected_stats.get(f"max_normalized_violation_{name}", np.nan)
            )
        return row

    def _sample_diagnostics(
        self,
        iteration: int,
        feasible: np.ndarray,
        safety_feasible: np.ndarray,
        task_costs: np.ndarray,
        safety_scores: np.ndarray,
        ranking_costs: np.ndarray,
        elite_order: np.ndarray,
        best_idx: int,
        safety_stats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        elite_indices = {int(index) for index in elite_order}
        rows = []
        for index, stats in enumerate(safety_stats):
            row = {
                "cem_iteration": int(iteration),
                "candidate_index": int(index),
                "task_cost": float(task_costs[index]),
                "safety_cost": float(safety_scores[index]),
                "alpha_cost": float(stats.get("total_normalized_alpha_score", np.nan)),
                "safety_cost_excluding_alpha": float(stats.get("total_normalized_score_excluding_alpha", np.nan)),
                "total_cost_used_for_ranking": float(ranking_costs[index]),
                "base_feasible": bool(feasible[index]),
                "safety_feasible": bool(safety_feasible[index]),
                "safety_feasible_excluding_alpha": bool(stats.get("safety_feasible_excluding_alpha", False)),
                "alpha_original_feasible": bool(stats.get("alpha_original_feasible", False)),
                "alpha_relaxed_feasible": bool(stats.get("alpha_relaxed_feasible", False)),
                "is_elite": bool(index in elite_indices),
                "is_selected": bool(index == best_idx),
            }
            for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
                row[f"horizon_violation_{name}"] = float(
                    stats.get(f"max_normalized_violation_{name}", np.nan)
                )
            rows.append(row)
        return rows

    def _per_constraint_feasibility(self, safety_stats: list[dict[str, Any]]) -> dict[str, Any]:
        num_samples = float(len(safety_stats))

        def feasible_count(*names: str) -> int:
            count = 0
            for stats in safety_stats:
                values = [float(stats.get(f"max_normalized_violation_{name}", np.inf)) for name in names]
                if all(np.isfinite(value) and value <= 0.0 for value in values):
                    count += 1
            return count

        counts = {
            "excluding_alpha": feasible_count("F_tan", "F_rad", "delta_r", "omega"),
            "force_bounds": feasible_count("F_tan", "F_rad"),
            "delta_r": feasible_count("delta_r"),
            "omega": feasible_count("omega"),
            "alpha": feasible_count("alpha"),
            "F_tan": feasible_count("F_tan"),
            "F_rad": feasible_count("F_rad"),
        }
        result: dict[str, Any] = {}
        for name, count in counts.items():
            result[f"feasible_{name}_count"] = int(count)
            result[f"feasible_{name}_ratio"] = self._safe_ratio(float(count), num_samples)
        alpha_relaxed_count = 0
        for stats in safety_stats:
            if bool(stats.get("alpha_relaxed_feasible", False)):
                alpha_relaxed_count += 1
        result["feasible_alpha_relaxed_count"] = int(alpha_relaxed_count)
        result["feasible_alpha_relaxed_ratio"] = self._safe_ratio(float(alpha_relaxed_count), num_samples)
        return result

    def _first_step_violation(self, sequence: np.ndarray, stats: dict[str, Any]) -> dict[str, float]:
        result = {
            "one_step_total_normalized_score": float("nan"),
            "one_step_normalized_violation_F_tan": float("nan"),
            "one_step_normalized_violation_F_rad": float("nan"),
            "one_step_normalized_violation_delta_r": float("nan"),
            "one_step_normalized_violation_omega": float("nan"),
            "one_step_normalized_violation_alpha": float("nan"),
        }
        if not sequence.size:
            return result
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            value = float(stats.get(f"one_step_normalized_violation_{name}", np.nan))
            result[f"one_step_normalized_violation_{name}"] = float(value)
        result["one_step_total_normalized_score"] = float(stats.get("one_step_total_normalized_score", np.nan))
        return result

    @staticmethod
    def _distribution(prefix: str, values: np.ndarray) -> dict[str, float]:
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            return {
                f"{prefix}_min": float("nan"),
                f"{prefix}_mean": float("nan"),
                f"{prefix}_median": float("nan"),
                f"{prefix}_max": float("nan"),
            }
        return {
            f"{prefix}_min": float(np.min(values)),
            f"{prefix}_mean": float(np.mean(values)),
            f"{prefix}_median": float(np.median(values)),
            f"{prefix}_max": float(np.max(values)),
        }

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if denominator <= 0.0 or not np.isfinite(denominator):
            return float("nan")
        return float(numerator / denominator)

    def _invalid_safety_stats(self) -> dict[str, Any]:
        stats = {
            "total_normalized_score": float("inf"),
            "total_normalized_score_excluding_alpha": float("inf"),
            "total_normalized_alpha_score": float("inf"),
            "total_raw_score": float("inf"),
            "safety_feasible": False,
            "safety_feasible_excluding_alpha": False,
            "alpha_original_feasible": False,
            "alpha_relaxed_feasible": False,
            "alpha_relaxed_threshold_normalized": max(0.0, float(self.config.alpha_relaxed_multiplier) - 1.0),
            "violation_count": 1,
        }
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            stats[f"max_normalized_violation_{name}"] = float("inf")
            stats[f"mean_normalized_violation_{name}"] = float("inf")
            stats[f"one_step_normalized_violation_{name}"] = float("inf")
        stats["one_step_total_normalized_score"] = float("inf")
        return stats

    @staticmethod
    def _normalize(value: float, limit: float) -> float:
        if limit <= 0.0:
            return float("inf") if value > 0.0 else 0.0
        return float(value / limit)
