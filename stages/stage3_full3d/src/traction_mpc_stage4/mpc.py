"""Constrained Human-space MPC used by fixed and adaptive Stage-4 controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
    HumanV2Parameters,
)
from traction_mpc_stage3.reference import CuffPoseReference

from .human_model import allocate_generalized_action, inverse_dynamics, step_dynamics


def _step_model(state: np.ndarray, action: np.ndarray, dt_s: float, human: Any) -> np.ndarray:
    if hasattr(human, "step_dynamics"):
        return human.step_dynamics(state, action, dt_s)
    return step_dynamics(state, action, dt_s, human)


def _inverse_model(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    ddq_rad_s2: np.ndarray,
    human: Any,
) -> np.ndarray:
    if hasattr(human, "inverse_dynamics"):
        return human.inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2)
    return inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2, human)


def _allocate_model(action: np.ndarray, q_rad: np.ndarray, human: Any) -> dict[str, Any]:
    if hasattr(human, "allocate_generalized_action"):
        return human.allocate_generalized_action(action, q_rad)
    return allocate_generalized_action(action, q_rad, human)


@dataclass(frozen=True)
class HumanMPCConfig:
    prediction_dt_s: float = 0.02
    horizon_steps: int = 15
    candidate_count: int = 32
    elite_count: int = 6
    cem_iterations: int = 2
    exploration_std_nm: tuple[float, float] = (10.0, 5.0)
    exploration_std_floor_nm: tuple[float, float] = (1.0, 0.5)
    random_seed: int = 20260824
    q_error_scale_rad: tuple[float, float] = (np.radians(2.0), np.radians(2.0))
    dq_error_scale_rad_s: tuple[float, float] = (np.radians(8.0), np.radians(8.0))
    action_scale_nm: tuple[float, float] = (60.0, 30.0)
    action_rate_scale_nm: tuple[float, float] = (20.0, 10.0)
    action_weight: float = 2.0e-3
    action_rate_weight: float = 5.0e-3


class HumanSpaceMPC:
    """Nonlinear shooting MPC over desired Human generalized cuff action."""

    def __init__(self, config: HumanMPCConfig = HumanMPCConfig()) -> None:
        self.config = config
        self.last_sequence: np.ndarray | None = None
        self.last_action = np.zeros(2)
        self.solve_count = 0
        self.failure_count = 0
        self.last_diagnostics: dict[str, Any] = {}
        self.rng = np.random.default_rng(config.random_seed)

    def reset(self) -> None:
        self.last_sequence = None
        self.last_action = np.zeros(2)
        self.solve_count = 0
        self.failure_count = 0
        self.last_diagnostics = {}
        self.rng = np.random.default_rng(self.config.random_seed)

    def _rollout(self, state: np.ndarray, sequence: np.ndarray, human: HumanV2Parameters) -> np.ndarray:
        states = [np.asarray(state, dtype=float)]
        for action in sequence:
            states.append(_step_model(states[-1], action, self.config.prediction_dt_s, human))
        return np.asarray(states)

    def _reference_arrays(
        self,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        references = [
            reference_fn(time_s + (index + 1) * self.config.prediction_dt_s)
            for index in range(self.config.horizon_steps)
        ]
        return (
            np.array([item.q_rad for item in references]),
            np.array([item.dq_rad_s for item in references]),
            np.array([item.ddq_rad_s2 for item in references]),
        )

    def _seed_sequence(
        self,
        state: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        ddq_ref: np.ndarray,
        human: HumanV2Parameters,
    ) -> np.ndarray:
        predicted = np.asarray(state, dtype=float).copy()
        actions = []
        for q_target, dq_target, qdd_target in zip(q_ref, dq_ref, ddq_ref, strict=True):
            qdd_command = (
                qdd_target
                - TRACKING_KP_RAD_S2_PER_RAD * (predicted[:2] - q_target)
                - TRACKING_KD_RAD_S2_PER_RAD_S * (predicted[2:] - dq_target)
            )
            action = _inverse_model(predicted[:2], predicted[2:], qdd_command, human)
            actions.append(action)
            predicted = _step_model(predicted, action, self.config.prediction_dt_s, human)
        heuristic = np.asarray(actions)
        if self.last_sequence is None:
            return heuristic
        warm = np.vstack([self.last_sequence[1:], self.last_sequence[-1]])
        return 0.35 * warm + 0.65 * heuristic

    def solve(
        self,
        state: np.ndarray,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
        human: HumanV2Parameters,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        x0 = np.asarray(state, dtype=float)
        q_ref, dq_ref, ddq_ref = self._reference_arrays(time_s, reference_fn)
        seed = self._seed_sequence(x0, q_ref, dq_ref, ddq_ref, human)
        shape = (self.config.horizon_steps, 2)
        q_scale = np.asarray(self.config.q_error_scale_rad)
        dq_scale = np.asarray(self.config.dq_error_scale_rad_s)
        action_scale = np.asarray(self.config.action_scale_nm)
        rate_scale = np.asarray(self.config.action_rate_scale_nm)

        def evaluate(sequence: np.ndarray) -> tuple[float, float, np.ndarray | None]:
            sequence = np.asarray(sequence).reshape(shape)
            if not np.all(np.isfinite(sequence)) or np.max(np.abs(sequence)) > 1.0e6:
                return 1.0e30, -1.0e6, None
            try:
                with np.errstate(over="raise", invalid="raise"):
                    states = self._rollout(x0, sequence, human)[1:]
            except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
                return 1.0e30, -1.0e6, None
            if not np.all(np.isfinite(states)) or np.max(np.abs(states)) > 1.0e6:
                return 1.0e30, -1.0e6, None
            q_cost = np.sum(((states[:, :2] - q_ref) / q_scale) ** 2)
            dq_cost = np.sum(((states[:, 2:] - dq_ref) / dq_scale) ** 2)
            effort = self.config.action_weight * np.sum((sequence / action_scale) ** 2)
            previous = np.vstack([self.last_action, sequence[:-1]])
            smoothness = self.config.action_rate_weight * np.sum(((sequence - previous) / rate_scale) ** 2)
            lower = states[:, :2] - np.asarray(human.q_min_rad)
            upper = np.asarray(human.q_max_rad) - states[:, :2]
            try:
                force_margin = np.array(
                    [
                        CUFF_TRANSLATIONAL_FORCE_GATE_N
                        - float(_allocate_model(action, state[:2], human)["force_norm_n"])
                        for action, state in zip(sequence, states, strict=True)
                    ]
                )
            except (ValueError, RuntimeError, FloatingPointError):
                return 1.0e30, -1.0e6, None
            margin = float(np.min(np.concatenate([lower.reshape(-1), upper.reshape(-1), force_margin])))
            return float(q_cost + dq_cost + effort + smoothness), margin, states

        mean = seed.copy()
        std = np.broadcast_to(np.asarray(self.config.exploration_std_nm), shape).copy()
        floor = np.broadcast_to(np.asarray(self.config.exploration_std_floor_nm), shape)
        best_sequence: np.ndarray | None = None
        best_cost = float("inf")
        best_margin = float("-inf")
        best_states: np.ndarray | None = None
        feasible_candidate_count = 0
        for _ in range(self.config.cem_iterations):
            candidates = self.rng.normal(mean, std, size=(self.config.candidate_count, *shape))
            candidates[0] = mean
            evaluations = [evaluate(candidate) for candidate in candidates]
            feasible = [index for index, (_, margin, states) in enumerate(evaluations) if states is not None and margin >= -1e-9]
            feasible_candidate_count += len(feasible)
            if not feasible:
                continue
            ordered = sorted(feasible, key=lambda index: evaluations[index][0])
            if evaluations[ordered[0]][0] < best_cost:
                selected = ordered[0]
                best_sequence = candidates[selected].copy()
                best_cost, best_margin, best_states = evaluations[selected]
            elites = candidates[ordered[: min(self.config.elite_count, len(ordered))]]
            mean = np.mean(elites, axis=0)
            std = np.maximum(np.std(elites, axis=0), floor)

        accepted = best_sequence is not None
        self.solve_count += 1
        if accepted:
            assert best_sequence is not None and best_states is not None
            self.last_sequence = best_sequence.copy()
            self.last_action = best_sequence[0].copy()
        else:
            self.failure_count += 1
            best_sequence = seed.copy()
            best_cost, best_margin, seed_states = evaluate(seed)
            best_states = seed_states
        predicted = np.vstack([x0, best_states]) if best_states is not None else self._rollout(x0, seed, human)
        peak_predicted_force = max(
            float(_allocate_model(action, state[:2], human)["force_norm_n"])
            for action, state in zip(best_sequence, predicted[1:], strict=True)
        )
        self.last_diagnostics = {
            "accepted": accepted,
            "optimizer_success": accepted,
            "optimizer": "feasible_first_cem",
            "optimizer_iterations": self.config.cem_iterations,
            "feasible_candidate_evaluations": feasible_candidate_count,
            "objective": best_cost,
            "minimum_constraint_margin": best_margin,
            "peak_predicted_force_n": peak_predicted_force,
            "predicted_rom_respected": bool(
                np.all(predicted[1:, :2] >= np.asarray(human.q_min_rad) - 1e-9)
                and np.all(predicted[1:, :2] <= np.asarray(human.q_max_rad) + 1e-9)
            ),
        }
        return best_sequence[0].copy(), dict(self.last_diagnostics)
