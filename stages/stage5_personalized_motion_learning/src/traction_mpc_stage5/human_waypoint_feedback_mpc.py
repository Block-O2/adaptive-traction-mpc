"""Opt-in state-feedback Human-waypoint MPC candidate search for Stage 5."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Sequence

import numpy as np

from .human_waypoint_scheduler import (
    QuinticHumanWaypointSchedule,
    QuinticHumanWaypointSchedulerV1,
    WaypointGeometryInfeasible,
)
from .human_waypoint_shadow import HumanWaypointCandidate
from .task import GoalTaskSpec, TaskPhase


HUMAN_WAYPOINT_FEEDBACK_MPC_VERSION = "human_waypoint_feedback_mpc_shadow_v1"


def _vector(name: str, value: Any) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (2,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite two-vector")
    return result.copy()


@dataclass(frozen=True)
class HumanWaypointFeedbackMPCConfigV1:
    """Finite direct-Delta-q lattice and the unchanged first-prototype cost."""

    maximum_waypoint_step_fraction: float = 0.20
    action_scales: tuple[float, ...] = (0.5, 1.0)
    normalized_coordination_directions: tuple[tuple[float, float], ...] = (
        (1.0, 0.5),
        (1.0, 0.75),
        (1.0, 1.0),
        (0.75, 1.0),
        (0.5, 1.0),
    )
    goal_error_weight: float = 1.0
    waypoint_change_weight: float = 0.02
    incomplete_phase_weight: float = 0.25

    def __post_init__(self) -> None:
        if not 0.0 < self.maximum_waypoint_step_fraction <= 1.0:
            raise ValueError("maximum waypoint step fraction must lie in (0, 1]")
        if not self.action_scales or any(
            not np.isfinite(value) or not 0.0 < value <= 1.0
            for value in self.action_scales
        ):
            raise ValueError("action scales must lie in (0, 1]")
        if not self.normalized_coordination_directions:
            raise ValueError("at least one direct two-joint action direction is required")
        for direction in self.normalized_coordination_directions:
            value = np.asarray(direction, dtype=float)
            if value.shape != (2,) or np.any(value <= 0.0) or np.any(value > 1.0):
                raise ValueError("action directions must be positive normalized pairs")
        if any(
            not np.isfinite(value) or value < 0.0
            for value in (
                self.goal_error_weight,
                self.waypoint_change_weight,
                self.incomplete_phase_weight,
            )
        ):
            raise ValueError("cost weights must be finite and nonnegative")


@dataclass(frozen=True)
class FeedbackCandidateEvaluationV1:
    label: str
    proposed_delta_q_rad: np.ndarray
    target_q_rad: np.ndarray
    feasible: bool
    rejection_reason: str | None
    total_cost: float | None
    cost_terms: dict[str, float]
    schedule: QuinticHumanWaypointSchedule | None
    execution_screen: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposed_delta_q_rad",
            _vector("proposed_delta_q_rad", self.proposed_delta_q_rad),
        )
        object.__setattr__(self, "target_q_rad", _vector("target_q_rad", self.target_q_rad))

    def record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "proposed_delta_q_rad": self.proposed_delta_q_rad.tolist(),
            "proposed_delta_q_deg": np.degrees(self.proposed_delta_q_rad).tolist(),
            "target_q_rad": self.target_q_rad.tolist(),
            "feasible": self.feasible,
            "rejection_reason": self.rejection_reason,
            "total_cost": self.total_cost,
            "cost_terms": dict(self.cost_terms),
            "schedule": None if self.schedule is None else self.schedule.record(),
            "execution_screen": dict(self.execution_screen),
        }


@dataclass(frozen=True)
class HumanWaypointFeedbackDecisionV1:
    phase: TaskPhase
    phase_elapsed_s: float
    phase_remaining_s: float
    deployable_state: np.ndarray
    reference_state: np.ndarray
    greedy: FeedbackCandidateEvaluationV1
    executed: FeedbackCandidateEvaluationV1
    selection_mode: str
    exploration_rank: int
    evaluations: tuple[FeedbackCandidateEvaluationV1, ...]
    runtime_ms: float
    value_hook_configured: bool = False

    def record(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "phase_elapsed_s": self.phase_elapsed_s,
            "phase_remaining_s": self.phase_remaining_s,
            "deployable_state_rad_rad_s": self.deployable_state.tolist(),
            "reference_state_rad_rad_s": self.reference_state.tolist(),
            "tracking_error_rad_rad_s": (
                self.deployable_state - self.reference_state
            ).tolist(),
            "proposed_action_delta_q_rad": self.greedy.proposed_delta_q_rad.tolist(),
            "executed_action_delta_q_rad": self.executed.proposed_delta_q_rad.tolist(),
            "greedy_label": self.greedy.label,
            "executed_label": self.executed.label,
            "selection_mode": self.selection_mode,
            "exploration_rank": self.exploration_rank,
            "runtime_ms": self.runtime_ms,
            "value_hook_configured": self.value_hook_configured,
            "candidate_count": len(self.evaluations),
            "feasible_candidate_count": sum(item.feasible for item in self.evaluations),
            "evaluations": [item.record() for item in self.evaluations],
        }


class HumanWaypointFeedbackMPCV1:
    """Receding one-waypoint search with no robot/interface dynamics predictor."""

    def __init__(
        self,
        spec: GoalTaskSpec,
        scheduler: QuinticHumanWaypointSchedulerV1,
        config: HumanWaypointFeedbackMPCConfigV1 | None = None,
    ) -> None:
        self.spec = spec
        self.scheduler = scheduler
        self.config = config or HumanWaypointFeedbackMPCConfigV1()
        self.start_rad = np.asarray(spec.start_return_target_rad, dtype=float)
        self.goal_rad = np.asarray(spec.outbound_goal_target_rad, dtype=float)
        self.span_rad = np.abs(self.goal_rad - self.start_rad)
        if np.any(self.span_rad <= 0.0):
            raise ValueError("registered task span must be nonzero")
        self.previous_executed_delta_q_rad = np.zeros(2)
        self.decisions: list[HumanWaypointFeedbackDecisionV1] = []
        self.value_hook_evaluation_count = 0
        self.value_hook_nonzero_count = 0

    def reset_phase(self) -> None:
        self.previous_executed_delta_q_rad = np.zeros(2)

    def phase_goal(self, phase: TaskPhase) -> np.ndarray:
        if phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD):
            return self.goal_rad.copy()
        if phase is TaskPhase.RETURN:
            return self.start_rad.copy()
        raise ValueError("feedback HWMPC supports OUTBOUND, HOLD and RETURN only")

    def candidate_actions(
        self, current_q_rad: Sequence[float], phase: TaskPhase
    ) -> tuple[np.ndarray, ...]:
        current_q = _vector("current_q_rad", current_q_rad)
        goal = self.phase_goal(phase)
        if phase is TaskPhase.HOLD:
            return (goal - current_q,)
        remaining = goal - current_q
        sign = np.sign(remaining)
        actions: list[np.ndarray] = []
        for scale in self.config.action_scales:
            for direction in self.config.normalized_coordination_directions:
                requested = (
                    sign
                    * self.span_rad
                    * self.config.maximum_waypoint_step_fraction
                    * float(scale)
                    * np.asarray(direction, dtype=float)
                )
                action = sign * np.minimum(np.abs(requested), np.abs(remaining))
                if np.all(np.abs(action) <= 1.0e-12):
                    action = remaining.copy()
                if not any(np.allclose(action, item, atol=1.0e-12, rtol=0.0) for item in actions):
                    actions.append(action)
        return tuple(actions)

    def _evaluate(
        self,
        *,
        label: str,
        state: np.ndarray,
        reference_state: np.ndarray,
        phase: TaskPhase,
        phase_elapsed_s: float,
        phase_remaining_s: float,
        action: np.ndarray,
        execution_feasibility_checker: Callable[
            [HumanWaypointCandidate, QuinticHumanWaypointSchedule], dict[str, Any]
        ] | None,
        value_state_or_belief: Any,
        candidate_value_evaluator: Callable[
            [Any, HumanWaypointCandidate], float
        ] | None,
    ) -> FeedbackCandidateEvaluationV1:
        goal = self.phase_goal(phase)
        target = state[:2] + action
        reference_remaining = goal - reference_state[:2]
        target_remaining = goal - target
        if np.any(reference_remaining * (target - reference_state[:2]) < -1.0e-12) or np.any(
            np.abs(target_remaining) > np.abs(reference_remaining) + 1.0e-12
        ):
            return FeedbackCandidateEvaluationV1(
                label,
                action,
                target,
                False,
                "candidate would regress the emitted reference away from the phase goal",
                None,
                {},
                None,
                {"evaluated": False},
            )
        candidate = HumanWaypointCandidate(
            label=label,
            phase=phase,
            phase_goal_rad=goal,
            q_waypoint_rad=target,
            dq_waypoint_rad_s=np.zeros(2),
        )
        try:
            schedule = self.scheduler.plan_reference_contract(
                current_q_hat_rad=reference_state[:2],
                current_dq_hat_rad_s=reference_state[2:],
                candidate=candidate,
                phase_elapsed_s=phase_elapsed_s,
            )
            if schedule.duration_s > phase_remaining_s + 1.0e-12:
                raise ValueError("scheduled segment does not fit remaining replanning window")
        except (ValueError, WaypointGeometryInfeasible) as error:
            return FeedbackCandidateEvaluationV1(
                label, action, target, False, str(error), None, {}, None,
                {"evaluated": False},
            )
        screen = (
            {"evaluated": False, "feasible": True}
            if execution_feasibility_checker is None
            else dict(execution_feasibility_checker(candidate, schedule))
        )
        if screen.get("evaluated") and not screen.get("feasible"):
            return FeedbackCandidateEvaluationV1(
                label, action, target, False,
                str(screen.get("rejection_reason", "existing execution screen rejected candidate")),
                None, {}, schedule, screen,
            )
        normalized_goal_error = (target - goal) / self.span_rad
        normalized_change = (
            action - self.previous_executed_delta_q_rad
        ) / self.span_rad
        complete = bool(
            np.all(
                np.abs(target - goal)
                <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            )
        )
        terms = {
            "task_goal_error": self.config.goal_error_weight
            * float(normalized_goal_error @ normalized_goal_error),
            "waypoint_change": self.config.waypoint_change_weight
            * float(normalized_change @ normalized_change),
            "phase_completion": self.config.incomplete_phase_weight * float(not complete),
        }
        future_value = 0.0
        if candidate_value_evaluator is not None:
            future_value = float(candidate_value_evaluator(value_state_or_belief, candidate))
            if not np.isfinite(future_value):
                raise ValueError("candidate value hook must return a finite scalar")
            self.value_hook_evaluation_count += 1
            self.value_hook_nonzero_count += int(abs(future_value) > 0.0)
        terms["future_value"] = future_value
        return FeedbackCandidateEvaluationV1(
            label, action, target, True, None, float(sum(terms.values())),
            terms, schedule, screen,
        )

    def decide(
        self,
        *,
        current_deployable_state: Sequence[float],
        current_reference_state: Sequence[float],
        phase: TaskPhase,
        phase_elapsed_s: float,
        phase_remaining_s: float,
        exploration_rank: int = 0,
        execution_feasibility_checker: Callable[
            [HumanWaypointCandidate, QuinticHumanWaypointSchedule], dict[str, Any]
        ] | None = None,
        value_state_or_belief: Any = None,
        candidate_value_evaluator: Callable[
            [Any, HumanWaypointCandidate], float
        ] | None = None,
    ) -> HumanWaypointFeedbackDecisionV1:
        state = np.asarray(current_deployable_state, dtype=float)
        reference = np.asarray(current_reference_state, dtype=float)
        if state.shape != (4,) or reference.shape != (4,) or not (
            np.all(np.isfinite(state)) and np.all(np.isfinite(reference))
        ):
            raise ValueError("deployable and reference state must be finite state[4]")
        if not np.isfinite(phase_elapsed_s) or phase_elapsed_s < 0.0:
            raise ValueError("phase_elapsed_s must be finite and nonnegative")
        if not np.isfinite(phase_remaining_s) or phase_remaining_s <= 0.0:
            raise ValueError("phase_remaining_s must be finite and positive")
        if exploration_rank < 0:
            raise ValueError("exploration_rank must be nonnegative")

        started = perf_counter()
        actions = self.candidate_actions(state[:2], phase)
        evaluations = tuple(
            self._evaluate(
                label=f"{phase.value.lower()}_dq_{index:02d}",
                state=state,
                reference_state=reference,
                phase=phase,
                phase_elapsed_s=phase_elapsed_s,
                phase_remaining_s=phase_remaining_s,
                action=action,
                execution_feasibility_checker=execution_feasibility_checker,
                value_state_or_belief=value_state_or_belief,
                candidate_value_evaluator=candidate_value_evaluator,
            )
            for index, action in enumerate(actions)
        )
        feasible = sorted(
            (item for item in evaluations if item.feasible),
            key=lambda item: (float(item.total_cost), item.label),
        )
        if not feasible:
            reasons = sorted({item.rejection_reason or "unknown" for item in evaluations})
            raise ValueError(
                "state-feedback Human-waypoint MPC has no feasible candidate: "
                + "; ".join(reasons)
            )
        rank = min(int(exploration_rank), len(feasible) - 1)
        greedy = feasible[0]
        executed = feasible[rank]
        self.previous_executed_delta_q_rad = executed.proposed_delta_q_rad.copy()
        decision = HumanWaypointFeedbackDecisionV1(
            phase=phase,
            phase_elapsed_s=float(phase_elapsed_s),
            phase_remaining_s=float(phase_remaining_s),
            deployable_state=state.copy(),
            reference_state=reference.copy(),
            greedy=greedy,
            executed=executed,
            selection_mode="greedy" if rank == 0 else "bounded_top_k_exploration",
            exploration_rank=rank,
            evaluations=evaluations,
            runtime_ms=1000.0 * (perf_counter() - started),
            value_hook_configured=candidate_value_evaluator is not None,
        )
        self.decisions.append(decision)
        return decision

    def record(self) -> dict[str, Any]:
        runtime = np.asarray([item.runtime_ms for item in self.decisions], dtype=float)
        return {
            "version": HUMAN_WAYPOINT_FEEDBACK_MPC_VERSION,
            "action": "next_2d_human_waypoint_increment",
            "candidate_generation": "direct_delta_q_lattice_from_fresh_deployable_state",
            "fixed_r_or_path_template_used": False,
            "return_replays_outbound_path": False,
            "old_robot_interface_predictor_used": False,
            "force_or_value_objective_used": bool(
                self.value_hook_evaluation_count
            ),
            "value_hook": {
                "signature": "V(state_or_belief, candidate_next_waypoint)",
                "default_when_absent": 0.0,
                "evaluation_count": self.value_hook_evaluation_count,
                "nonzero_evaluation_count": self.value_hook_nonzero_count,
                "training_performed": False,
            },
            "learning_used": False,
            "runtime_ms": {
                "count": int(len(runtime)),
                "mean": None if not len(runtime) else float(np.mean(runtime)),
                "p95": None if not len(runtime) else float(np.percentile(runtime, 95)),
                "p99": None if not len(runtime) else float(np.percentile(runtime, 99)),
                "maximum": None if not len(runtime) else float(np.max(runtime)),
            },
            "decisions": [item.record() for item in self.decisions],
        }


__all__ = [
    "HUMAN_WAYPOINT_FEEDBACK_MPC_VERSION",
    "FeedbackCandidateEvaluationV1",
    "HumanWaypointFeedbackDecisionV1",
    "HumanWaypointFeedbackMPCConfigV1",
    "HumanWaypointFeedbackMPCV1",
]
