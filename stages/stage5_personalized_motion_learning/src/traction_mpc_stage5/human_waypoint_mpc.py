"""Minimal reference-space Human-waypoint MPC prototype for Stage 5."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import numpy as np

from .human_waypoint_scheduler import (
    QuinticHumanWaypointSchedule,
    QuinticHumanWaypointSchedulerV1,
    WaypointGeometryInfeasible,
)
from .human_waypoint_shadow import HumanWaypointCandidate
from .task import GoalTaskSpec, TaskPhase


HUMAN_WAYPOINT_MPC_VERSION = "human_waypoint_mpc_prototype_v1"


def _vector(name: str, value: Any) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (2,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite two-vector")
    return result.copy()


@dataclass(frozen=True)
class HumanWaypointMPCConfigV1:
    """Fixed first-prototype action lattice and transparent objective."""

    maximum_waypoint_step_fraction: float = 0.20
    action_scales: tuple[float, ...] = (0.5, 1.0)
    coordination_gain: float = 0.25
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
            raise ValueError("action scales must be finite values in (0, 1]")
        if (
            not np.isfinite(self.coordination_gain)
            or not 0.0 < self.coordination_gain < 1.0
        ):
            raise ValueError("coordination gain must be finite and lie in (0, 1)")
        weights = (
            self.goal_error_weight,
            self.waypoint_change_weight,
            self.incomplete_phase_weight,
        )
        if any(not np.isfinite(value) or value < 0.0 for value in weights):
            raise ValueError("MPC cost weights must be finite and nonnegative")


@dataclass(frozen=True)
class HumanWaypointCandidateEvaluationV1:
    label: str
    coordination_preference_r: float
    q_waypoint_rad: np.ndarray
    dq_waypoint_rad_s: np.ndarray
    feasible: bool
    rejection_reason: str | None
    total_cost: float | None
    cost_terms: dict[str, float]
    schedule: QuinticHumanWaypointSchedule | None
    execution_screen: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "q_waypoint_rad", _vector("q_waypoint_rad", self.q_waypoint_rad)
        )
        object.__setattr__(
            self,
            "dq_waypoint_rad_s",
            _vector("dq_waypoint_rad_s", self.dq_waypoint_rad_s),
        )

    def record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "coordination_preference_r": self.coordination_preference_r,
            "q_waypoint_rad": self.q_waypoint_rad.tolist(),
            "dq_waypoint_rad_s": self.dq_waypoint_rad_s.tolist(),
            "feasible": self.feasible,
            "rejection_reason": self.rejection_reason,
            "total_cost": self.total_cost,
            "cost_terms": dict(self.cost_terms),
            "schedule": None if self.schedule is None else self.schedule.record(),
            "execution_screen": dict(self.execution_screen),
        }


@dataclass(frozen=True)
class HumanWaypointMPCDecisionV1:
    phase: TaskPhase
    phase_elapsed_s: float
    coordination_preference_r: float
    selected: HumanWaypointCandidateEvaluationV1
    evaluations: tuple[HumanWaypointCandidateEvaluationV1, ...]
    runtime_ms: float

    def record(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "phase_elapsed_s": self.phase_elapsed_s,
            "coordination_preference_r": self.coordination_preference_r,
            "selected_label": self.selected.label,
            "selected_q_waypoint_rad": self.selected.q_waypoint_rad.tolist(),
            "selected_dq_waypoint_rad_s": (
                self.selected.dq_waypoint_rad_s.tolist()
            ),
            "selected_total_cost": self.selected.total_cost,
            "runtime_ms": self.runtime_ms,
            "candidate_count": len(self.evaluations),
            "feasible_candidate_count": sum(item.feasible for item in self.evaluations),
            "evaluations": [item.record() for item in self.evaluations],
        }


class HumanWaypointMPCPrototypeV1:
    """One-step receding-horizon search over short Human q/dq waypoints.

    The state transition used for cost evaluation is the candidate scheduled
    reference endpoint. Robot, interface and contact dynamics are deliberately
    absent. Their existing protections remain authoritative during execution.
    """

    def __init__(
        self,
        spec: GoalTaskSpec,
        scheduler: QuinticHumanWaypointSchedulerV1,
        config: HumanWaypointMPCConfigV1 | None = None,
    ) -> None:
        self.spec = spec
        self.scheduler = scheduler
        self.config = config or HumanWaypointMPCConfigV1()
        self.path_start_rad = np.asarray(
            spec.start_return_target_rad, dtype=float
        )
        self.path_goal_rad = np.asarray(
            spec.outbound_goal_target_rad, dtype=float
        )
        self.signed_registered_span_rad = self.path_goal_rad - self.path_start_rad
        self.registered_span_rad = np.abs(self.signed_registered_span_rad)
        if np.any(self.registered_span_rad <= 0.0):
            raise ValueError("registered Human task span must be nonzero")
        self.previous_waypoint_delta_rad = np.zeros(2)
        self.decisions: list[HumanWaypointMPCDecisionV1] = []

    def reset_phase(self) -> None:
        self.previous_waypoint_delta_rad = np.zeros(2)

    def _phase_goal(self, phase: TaskPhase) -> np.ndarray:
        if phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD):
            return np.asarray(self.spec.outbound_goal_target_rad, dtype=float)
        if phase is TaskPhase.RETURN:
            return np.asarray(self.spec.start_return_target_rad, dtype=float)
        raise ValueError("waypoint MPC only supports OUTBOUND, HOLD and RETURN")

    def _candidate_targets(
        self,
        current_q_rad: np.ndarray,
        phase: TaskPhase,
        coordination_preference_r: float,
    ) -> list[np.ndarray]:
        goal = self._phase_goal(phase)
        if phase is TaskPhase.HOLD:
            return [goal]
        normalized_joint_progress = (
            current_q_rad - self.path_start_rad
        ) / self.signed_registered_span_rad
        path_progress = float(np.clip(np.mean(normalized_joint_progress), 0.0, 1.0))
        direction = 1.0 if phase is TaskPhase.OUTBOUND else -1.0
        targets: list[np.ndarray] = []
        for progress_scale in self.config.action_scales:
            target_progress = float(
                np.clip(
                    path_progress
                    + direction
                    * self.config.maximum_waypoint_step_fraction
                    * float(progress_scale),
                    0.0,
                    1.0,
                )
            )
            coordination_offset = (
                self.config.coordination_gain
                * coordination_preference_r
                * np.sin(np.pi * target_progress)
            )
            joint_progress = np.asarray(
                [
                    target_progress + coordination_offset,
                    target_progress - coordination_offset,
                ],
                dtype=float,
            )
            target = (
                self.path_start_rad
                + joint_progress * self.signed_registered_span_rad
            )
            if not any(np.allclose(target, item, atol=1.0e-12, rtol=0.0) for item in targets):
                targets.append(target)
        return targets

    def _evaluate(
        self,
        *,
        label: str,
        current_state: np.ndarray,
        phase: TaskPhase,
        phase_elapsed_s: float,
        target_q_rad: np.ndarray,
        coordination_preference_r: float,
        execution_feasibility_checker: Callable[
            [HumanWaypointCandidate, QuinticHumanWaypointSchedule],
            dict[str, Any],
        ]
        | None,
    ) -> HumanWaypointCandidateEvaluationV1:
        goal = self._phase_goal(phase)
        candidate = HumanWaypointCandidate(
            label=label,
            phase=phase,
            phase_goal_rad=goal,
            q_waypoint_rad=target_q_rad,
            dq_waypoint_rad_s=np.zeros(2),
        )
        try:
            schedule = self.scheduler.plan_reference_contract(
                current_q_hat_rad=current_state[:2],
                current_dq_hat_rad_s=current_state[2:],
                candidate=candidate,
                phase_elapsed_s=phase_elapsed_s,
            )
        except (ValueError, WaypointGeometryInfeasible) as error:
            return HumanWaypointCandidateEvaluationV1(
                label=label,
                coordination_preference_r=coordination_preference_r,
                q_waypoint_rad=target_q_rad,
                dq_waypoint_rad_s=np.zeros(2),
                feasible=False,
                rejection_reason=str(error),
                total_cost=None,
                cost_terms={},
                schedule=None,
                execution_screen={"evaluated": False},
            )

        execution_screen = (
            {"evaluated": False, "feasible": True}
            if execution_feasibility_checker is None
            else dict(execution_feasibility_checker(candidate, schedule))
        )
        if execution_screen.get("evaluated") and not execution_screen.get("feasible"):
            return HumanWaypointCandidateEvaluationV1(
                label=label,
                coordination_preference_r=coordination_preference_r,
                q_waypoint_rad=target_q_rad,
                dq_waypoint_rad_s=np.zeros(2),
                feasible=False,
                rejection_reason=str(
                    execution_screen.get(
                        "rejection_reason", "existing execution screen rejected candidate"
                    )
                ),
                total_cost=None,
                cost_terms={},
                schedule=schedule,
                execution_screen=execution_screen,
            )

        delta = target_q_rad - current_state[:2]
        normalized_goal_error = (target_q_rad - goal) / self.registered_span_rad
        normalized_change = (
            delta - self.previous_waypoint_delta_rad
        ) / self.registered_span_rad
        inside_phase_target = bool(
            np.all(
                np.abs(target_q_rad - goal)
                <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            )
        )
        cost_terms = {
            "task_goal_error": self.config.goal_error_weight
            * float(normalized_goal_error @ normalized_goal_error),
            "waypoint_change": self.config.waypoint_change_weight
            * float(normalized_change @ normalized_change),
            "phase_completion": self.config.incomplete_phase_weight
            * float(not inside_phase_target),
        }
        return HumanWaypointCandidateEvaluationV1(
            label=label,
            coordination_preference_r=coordination_preference_r,
            q_waypoint_rad=target_q_rad,
            dq_waypoint_rad_s=np.zeros(2),
            feasible=True,
            rejection_reason=None,
            total_cost=float(sum(cost_terms.values())),
            cost_terms=cost_terms,
            schedule=schedule,
            execution_screen=execution_screen,
        )

    def decide(
        self,
        *,
        current_deployable_state: np.ndarray,
        phase: TaskPhase,
        phase_elapsed_s: float,
        coordination_preference_r: float = 0.0,
        execution_feasibility_checker: Callable[
            [HumanWaypointCandidate, QuinticHumanWaypointSchedule],
            dict[str, Any],
        ]
        | None = None,
    ) -> HumanWaypointMPCDecisionV1:
        state = np.asarray(current_deployable_state, dtype=float)
        if state.shape != (4,) or not np.all(np.isfinite(state)):
            raise ValueError("current deployable Human state must be finite state[4]")
        if not np.isfinite(phase_elapsed_s) or phase_elapsed_s < 0.0:
            raise ValueError("phase_elapsed_s must be finite and nonnegative")
        if (
            not np.isfinite(coordination_preference_r)
            or not -1.0 <= coordination_preference_r <= 1.0
        ):
            raise ValueError("coordination_preference_r must lie in [-1, 1]")

        started = perf_counter()
        targets = self._candidate_targets(
            state[:2], phase, float(coordination_preference_r)
        )
        evaluations = tuple(
            self._evaluate(
                label=(
                    f"{phase.value.lower()}_r{coordination_preference_r:+.4f}_"
                    f"candidate_{index}"
                ),
                current_state=state,
                phase=phase,
                phase_elapsed_s=phase_elapsed_s,
                target_q_rad=target,
                coordination_preference_r=float(coordination_preference_r),
                execution_feasibility_checker=execution_feasibility_checker,
            )
            for index, target in enumerate(targets)
        )
        feasible = [item for item in evaluations if item.feasible]
        if not feasible:
            reasons = sorted(
                {item.rejection_reason or "unknown" for item in evaluations}
            )
            raise ValueError(
                "Human-waypoint MPC has no feasible candidate: " + "; ".join(reasons)
            )
        selected = min(
            feasible,
            key=lambda item: (
                float(item.total_cost),
                item.label,
            ),
        )
        self.previous_waypoint_delta_rad = (
            selected.q_waypoint_rad - state[:2]
        )
        decision = HumanWaypointMPCDecisionV1(
            phase=phase,
            phase_elapsed_s=float(phase_elapsed_s),
            coordination_preference_r=float(coordination_preference_r),
            selected=selected,
            evaluations=evaluations,
            runtime_ms=1000.0 * (perf_counter() - started),
        )
        self.decisions.append(decision)
        return decision

    def record(self) -> dict[str, Any]:
        runtime = np.asarray([item.runtime_ms for item in self.decisions], dtype=float)
        return {
            "version": HUMAN_WAYPOINT_MPC_VERSION,
            "prediction_abstraction": (
                "one_step_scheduled_reference_endpoint_without_robot_interface_predictor"
            ),
            "coordination_path": (
                "p_hip=s+gain*r*sin(pi*s); "
                "p_knee=s-gain*r*sin(pi*s); same path reversed on RETURN"
            ),
            "action": "next_human_q_dq_waypoint",
            "config": {
                "maximum_waypoint_step_fraction": (
                    self.config.maximum_waypoint_step_fraction
                ),
                "action_scales": list(self.config.action_scales),
                "coordination_gain": self.config.coordination_gain,
                "goal_error_weight": self.config.goal_error_weight,
                "waypoint_change_weight": self.config.waypoint_change_weight,
                "incomplete_phase_weight": self.config.incomplete_phase_weight,
            },
            "runtime_ms": {
                "count": int(len(runtime)),
                "mean": None if not len(runtime) else float(np.mean(runtime)),
                "p95": None if not len(runtime) else float(np.percentile(runtime, 95)),
                "maximum": None if not len(runtime) else float(np.max(runtime)),
            },
            "decisions": [item.record() for item in self.decisions],
            "uses_old_robot_interface_predictor": False,
            "uses_pd_acceleration_request_for_feasibility": False,
            "uses_force_or_value_objective": False,
            "uses_learning": False,
        }


__all__ = [
    "HUMAN_WAYPOINT_MPC_VERSION",
    "HumanWaypointCandidateEvaluationV1",
    "HumanWaypointMPCConfigV1",
    "HumanWaypointMPCDecisionV1",
    "HumanWaypointMPCPrototypeV1",
]
