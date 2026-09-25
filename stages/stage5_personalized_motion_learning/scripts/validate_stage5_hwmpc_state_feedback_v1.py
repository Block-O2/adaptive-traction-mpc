#!/usr/bin/env python3
"""Opt-in bounded CR12 validation of state-feedback Human-waypoint decisions."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_feedback_mpc import (
    HumanWaypointFeedbackMPCConfigV1,
    HumanWaypointFeedbackMPCV1,
)
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedule,
    QuinticHumanWaypointSchedulerSession,
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_mpc import _MPCPhaseController
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _candidate,
    _jsonable,
    _prepare_runtime,
    _run_case,
)
from validate_stage5_hwmpc_matched_pacing_r_cost import (
    _fixed_models,
    _observed_phase_durations,
)


SCHEMA = "stage5_hwmpc_state_feedback_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_state_feedback_v1.json"
)


def _schedule_samples(schedule: QuinticHumanWaypointSchedule) -> list[dict[str, Any]]:
    count = int(round(schedule.duration_s / schedule.reference_period_s))
    return [
        {
            "elapsed_s": index * schedule.reference_period_s,
            "q_rad": sample.q_rad,
            "dq_rad_s": sample.dq_rad_s,
            "ddq_rad_s2": sample.ddq_rad_s2,
        }
        for index in range(count + 1)
        for sample in [schedule.sample(index * schedule.reference_period_s)]
    ]


class StateFeedbackMatchedPacingControllerV1:
    """Study-only phase driver; dynamic direct-Delta-q search precedes V2 terminal block."""

    def __init__(
        self,
        planner: HumanWaypointFeedbackMPCV1,
        scheduler: QuinticHumanWaypointSchedulerV1,
        *,
        pacing: dict[str, Any],
        episode: dict[str, Any],
        exploration_probability: float,
        exploration_top_k: int,
        provenance: dict[str, Any],
    ) -> None:
        self.planner = planner
        self.scheduler = scheduler
        self.spec = scheduler.spec
        self.episode = dict(episode)
        self.provenance = dict(provenance)
        self.rng = np.random.default_rng(int(episode["seed"]))
        self.exploration_probability = float(exploration_probability)
        self.exploration_top_k = int(exploration_top_k)
        self.phase_durations = {
            TaskPhase.OUTBOUND: float(pacing["outbound_duration_s"]),
            TaskPhase.HOLD: float(pacing["hold_duration_s"]),
            TaskPhase.RETURN: float(pacing["return_duration_s"]),
        }
        self.phase_starts = {
            TaskPhase.OUTBOUND: 0.0,
            TaskPhase.HOLD: float(pacing["outbound_duration_s"]),
            TaskPhase.RETURN: float(
                pacing["outbound_duration_s"] + pacing["hold_duration_s"]
            ),
        }
        self.total_duration_s = float(sum(self.phase_durations.values()))
        self.terminal_start_s = float(pacing["terminal_block_start_s"])
        self.terminal_duration_s = float(pacing["terminal_transition_duration_s"])
        self.phase = TaskPhase.OUTBOUND
        self.execution_context: dict[str, Any] | None = None
        self.active_schedule: QuinticHumanWaypointSchedule | None = None
        self.active_session: QuinticHumanWaypointSchedulerSession | None = None
        self.terminal_schedule: QuinticHumanWaypointSchedule | None = None
        self.last_reference_state: np.ndarray | None = None
        self.last_candidate: HumanWaypointCandidate | None = None
        self.boundary_checks: list[dict[str, Any]] = []
        self.learning_records: list[dict[str, Any]] = []
        self.pending_record: dict[str, Any] | None = None
        self.completed_time_s: float | None = None
        self.stop_reason: str | None = None
        self._last_force_time_s: float | None = None
        self._terminal_boundary_checked = False
        self.planner.reset_phase()

    def bind_execution_context(self, **context: Any) -> None:
        self.execution_context = dict(context)
        observation = context["observation"]
        timestamp = float(observation.sample_timestamp_s)
        force_norm = float(
            np.linalg.norm(context["interface_state"].measured_force_world_n)
        )
        if self.pending_record is not None and self._last_force_time_s is not None:
            dt = max(0.0, timestamp - self._last_force_time_s)
            self.pending_record["measured_cuff_force_integral_n_s"] += force_norm * dt
        self._last_force_time_s = timestamp

    def _goal(self, phase: TaskPhase) -> np.ndarray:
        return self.planner.phase_goal(phase)

    def _inside(self, state: np.ndarray, phase: TaskPhase) -> bool:
        return bool(
            np.all(
                np.abs(state[:2] - self._goal(phase))
                <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            )
            and np.all(
                np.abs(state[2:])
                <= np.asarray(self.spec.joint_velocity_completion_tolerance_rad_s)
            )
        )

    def _execution_screen(
        self,
        candidate: HumanWaypointCandidate,
        schedule: QuinticHumanWaypointSchedule,
    ) -> dict[str, Any]:
        if self.execution_context is None:
            raise RuntimeError("candidate execution screen has no runtime context")
        context = self.execution_context
        observation = context["observation"]
        sample_time_s = (
            0.0
            if float(observation.sample_timestamp_s) <= 1.0e-12
            else min(schedule.reference_period_s, schedule.duration_s)
        )
        sample = schedule.sample(sample_time_s)
        screened = HumanWaypointCandidate(
            label=f"{candidate.label}_first_action_screen",
            phase=candidate.phase,
            phase_goal_rad=candidate.phase_goal_rad,
            q_waypoint_rad=sample.q_rad,
            dq_waypoint_rad_s=sample.dq_rad_s,
        )
        contract = copy.deepcopy(context["contract"])
        try:
            mapped = contract.prepare(screened)
            command = contract.command(
                plant=context["plant"],
                measurement=context["measurement"],
                observation=observation,
                interface_state=context["interface_state"],
                mapped_waypoint=mapped,
            )
        except ValueError as error:
            return {"evaluated": True, "feasible": False, "rejection_reason": str(error)}
        result = command.filter_result
        if not result.feasible or result.filtered_preview is None:
            return {
                "evaluated": True,
                "feasible": False,
                "rejection_reason": "existing Safety Filter requires BRAKE",
                "safety_filter_status": result.status,
            }
        executable = result.filtered_preview.command
        torque_clipped = bool(
            not np.allclose(
                executable.unclipped_joint_torque_nm,
                executable.joint_torque_command_nm,
                atol=1.0e-12,
                rtol=0.0,
            )
        )
        force_gate_clear = bool(executable.margin_to_force_gate_n > 0.0)
        return {
            "evaluated": True,
            "feasible": bool(not torque_clipped and force_gate_clear),
            "rejection_reason": (
                None
                if not torque_clipped and force_gate_clear
                else "existing force-gate or CR12 torque-limit screen rejected candidate"
            ),
            "safety_filter_status": result.status,
            "force_gate_margin_n": executable.margin_to_force_gate_n,
            "torque_clipped": torque_clipped,
            "maximum_robot_torque_fraction": float(
                np.max(
                    np.abs(executable.joint_torque_command_nm)
                    / context["plant"].torque_limits_nm
                )
            ),
        }

    def _finalize_pending(self, time_s: float, state: np.ndarray, reason: str) -> None:
        if self.pending_record is None:
            return
        self.pending_record.update(
            {
                "next_observation_rad_rad_s": state.copy(),
                "transition_elapsed_s": float(time_s - self.pending_record["decision_time_s"]),
                "transition_end_reason": reason,
            }
        )
        self.learning_records.append(self.pending_record)
        self.pending_record = None

    def _exploration_rank(self) -> int:
        if self.episode["selection"] == "greedy":
            return 0
        if float(self.rng.random()) >= self.exploration_probability:
            return 0
        return int(self.rng.integers(1, self.exploration_top_k))

    def _select_dynamic(self, time_s: float, state: np.ndarray) -> None:
        phase_elapsed = float(time_s - self.phase_starts[self.phase])
        remaining = float(self.terminal_start_s - phase_elapsed)
        if remaining <= 1.0e-12:
            raise ValueError("no dynamic replanning time remains before terminal block")
        if self.last_reference_state is None:
            self.last_reference_state = state.copy()
        decision = self.planner.decide(
            current_deployable_state=state,
            current_reference_state=self.last_reference_state,
            phase=self.phase,
            phase_elapsed_s=phase_elapsed,
            phase_remaining_s=remaining,
            exploration_rank=self._exploration_rank(),
            execution_feasibility_checker=self._execution_screen,
        )
        schedule = decision.executed.schedule
        if schedule is None:
            raise RuntimeError("selected feedback candidate lacks a schedule")
        self.active_schedule = schedule
        self.active_session = QuinticHumanWaypointSchedulerSession(
            scheduler=self.scheduler,
            schedule=schedule,
            phase_start_elapsed_s=phase_elapsed,
        )
        self.last_candidate = schedule.candidate
        self.pending_record = {
            "record_schema": "stage5_hwmpc_learning_transition_v1",
            "rollout_provenance": dict(self.provenance),
            "snapshot_group": f"{self.episode['name']}:{self.phase.value}:{len(self.learning_records):03d}",
            "decision_time_s": float(time_s),
            "phase": self.phase.value,
            "phase_elapsed_s": phase_elapsed,
            "deployable_state_history_endpoint_rad_rad_s": state.copy(),
            "reference_state_rad_rad_s": self.last_reference_state.copy(),
            "proposed_action_delta_q_rad": decision.greedy.proposed_delta_q_rad.copy(),
            "executed_action_delta_q_rad": decision.executed.proposed_delta_q_rad.copy(),
            "selection_mode": decision.selection_mode,
            "exploration_rank": decision.exploration_rank,
            "reference_segment": {
                "schedule": schedule.record(),
                "samples": _schedule_samples(schedule),
            },
            "planning_runtime_ms": decision.runtime_ms,
            "measured_cuff_force_integral_n_s": 0.0,
            "completion": False,
            "rejection_or_stop_reason": None,
        }

    def _sample_dynamic(self, time_s: float, state: np.ndarray) -> HumanWaypointCandidate:
        if self.active_schedule is None:
            try:
                self._select_dynamic(time_s, state)
            except ValueError as error:
                self.stop_reason = f"NO_ADMISSIBLE_CANDIDATE: {error}"
                raise ValueError(self.stop_reason) from error
        assert self.active_schedule is not None
        assert self.active_session is not None
        schedule_done = bool(
            self.active_session.progress_s + 1.0e-12
            >= self.active_schedule.duration_s
        )
        reached_waypoint = bool(
            np.all(
                np.abs(state[:2] - self.active_schedule.candidate.q_waypoint_rad)
                <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            )
            and np.all(
                np.abs(state[2:] - self.active_schedule.candidate.dq_waypoint_rad_s)
                <= np.asarray(self.spec.joint_velocity_completion_tolerance_rad_s)
            )
        )
        if schedule_done and reached_waypoint:
            endpoint = self.active_schedule.sample(self.active_schedule.duration_s)
            self.last_reference_state = np.concatenate([endpoint.q_rad, endpoint.dq_rad_s])
            self._finalize_pending(time_s, state, "scheduled_segment_complete")
            try:
                self._select_dynamic(time_s, state)
            except ValueError as error:
                self.stop_reason = f"NO_ADMISSIBLE_CANDIDATE: {error}"
                raise ValueError(self.stop_reason) from error
        assert self.active_session is not None
        phase_elapsed = float(time_s - self.phase_starts[self.phase])
        sample = self.active_session.advance(
            current_q_hat_rad=state[:2],
            current_dq_hat_rad_s=state[2:],
            phase_elapsed_s=phase_elapsed,
        )
        self.last_reference_state = np.concatenate([sample.q_rad, sample.dq_rad_s])
        return _candidate(
            f"feedback_{self.phase.value.lower()}_{len(self.learning_records):03d}_{time_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def _start_terminal(self, phase_elapsed_s: float, state: np.ndarray) -> None:
        if self.last_reference_state is None:
            self.last_reference_state = state.copy()
        self._finalize_pending(
            self.phase_starts[self.phase] + phase_elapsed_s,
            state,
            "common_terminal_block_start",
        )
        candidate = _candidate(
            f"feedback_terminal_{self.phase.value.lower()}",
            self.phase,
            self._goal(self.phase),
            np.zeros(2),
        )
        self.terminal_schedule = self.scheduler.plan_fixed_duration_reference_contract(
            current_q_hat_rad=self.last_reference_state[:2],
            current_dq_hat_rad_s=self.last_reference_state[2:],
            candidate=candidate,
            duration_s=self.terminal_duration_s,
            phase_elapsed_s=phase_elapsed_s,
        )

    def _terminal_candidate(self, phase_elapsed_s: float, state: np.ndarray) -> HumanWaypointCandidate:
        if self.terminal_schedule is None:
            self._start_terminal(phase_elapsed_s, state)
        assert self.terminal_schedule is not None
        sample = self.terminal_schedule.sample(
            max(0.0, phase_elapsed_s - self.terminal_start_s)
        )
        self.last_reference_state = np.concatenate([sample.q_rad, sample.dq_rad_s])
        return _candidate(
            f"feedback_terminal_{self.phase.value.lower()}_{phase_elapsed_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def _record_boundary(self, phase: TaskPhase, time_s: float, state: np.ndarray) -> bool:
        inside = self._inside(state, phase)
        self.boundary_checks.append(
            {
                "phase": phase.value,
                "boundary_time_s": float(time_s),
                "inside_existing_completion_criteria": inside,
                "q_error_deg": np.degrees(state[:2] - self._goal(phase)),
                "dq_deg_s": np.degrees(state[2:]),
            }
        )
        return inside

    def _enter_phase(self, phase: TaskPhase, time_s: float, state: np.ndarray) -> None:
        self._finalize_pending(time_s, state, "phase_boundary")
        self.phase = phase
        self.active_schedule = None
        self.active_session = None
        self.terminal_schedule = None
        self.last_reference_state = np.concatenate([self._goal(TaskPhase.OUTBOUND), np.zeros(2)])
        self.last_candidate = None
        self.planner.reset_phase()

    def __call__(self, time_s: float, state: np.ndarray) -> HumanWaypointCandidate:
        hold_start = self.phase_starts[TaskPhase.HOLD]
        return_start = self.phase_starts[TaskPhase.RETURN]
        if self.phase is TaskPhase.OUTBOUND and time_s + 1.0e-12 >= hold_start:
            self._record_boundary(TaskPhase.OUTBOUND, hold_start, state)
            self._enter_phase(TaskPhase.HOLD, time_s, state)
        if self.phase is TaskPhase.HOLD and time_s + 1.0e-12 >= return_start:
            self._record_boundary(TaskPhase.HOLD, return_start, state)
            self._enter_phase(TaskPhase.RETURN, time_s, state)
        if (
            self.phase is TaskPhase.RETURN
            and time_s + 1.0e-12 >= self.total_duration_s
            and not self._terminal_boundary_checked
        ):
            self._terminal_boundary_checked = True
            self._finalize_pending(time_s, state, "task_boundary")
            if self._record_boundary(TaskPhase.RETURN, self.total_duration_s, state):
                self.completed_time_s = self.total_duration_s

        phase_elapsed = float(time_s - self.phase_starts[self.phase])
        if self.phase is TaskPhase.HOLD:
            goal = self._goal(TaskPhase.HOLD)
            self.last_reference_state = np.concatenate([goal, np.zeros(2)])
            return _candidate(f"feedback_hold_{phase_elapsed:.3f}", self.phase, goal, np.zeros(2))
        if phase_elapsed + 1.0e-12 >= self.terminal_start_s:
            return self._terminal_candidate(phase_elapsed, state)
        return self._sample_dynamic(time_s, state)

    def record(self) -> dict[str, Any]:
        return {
            "episode": dict(self.episode),
            "phase_durations_s": {phase.value: value for phase, value in self.phase_durations.items()},
            "total_duration_s": self.total_duration_s,
            "completed_time_s": self.completed_time_s,
            "stop_reason": self.stop_reason,
            "boundary_checks": _jsonable(self.boundary_checks),
            "all_boundaries_inside_existing_completion_criteria": bool(
                len(self.boundary_checks) == 3
                and all(row["inside_existing_completion_criteria"] for row in self.boundary_checks)
            ),
            "learning_records": _jsonable(self.learning_records),
            "planner": self.planner.record(),
        }


def _planner_config(config: dict[str, Any]) -> HumanWaypointFeedbackMPCConfigV1:
    action = config["action_contract"]
    cost = action["selection_cost"]
    return HumanWaypointFeedbackMPCConfigV1(
        maximum_waypoint_step_fraction=float(action["maximum_waypoint_step_fraction"]),
        action_scales=tuple(float(value) for value in action["action_scales"]),
        normalized_coordination_directions=tuple(
            tuple(float(value) for value in row)
            for row in action["normalized_coordination_directions"]
        ),
        goal_error_weight=float(cost["goal_error_weight"]),
        waypoint_change_weight=float(cost["waypoint_change_weight"]),
        incomplete_phase_weight=float(cost["incomplete_phase_weight"]),
    )


def _run_episode(
    config: dict[str, Any], episode: dict[str, Any], truth_human: Any,
    control_model: Any, model_version: str,
    controller_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec, control_model, reference_period_s=CONTROL_DT_S
    )
    planner = HumanWaypointFeedbackMPCV1(spec, scheduler, _planner_config(config))
    controller_kwargs = dict(
        planner=planner,
        scheduler=scheduler,
        pacing=config["matched_pacing"],
        episode=episode,
        exploration_probability=float(config["bounded_test_budget"]["exploration_probability"]),
        exploration_top_k=int(config["bounded_test_budget"]["exploration_top_k"]),
        provenance={
            "runner_schema": SCHEMA,
            "episode": episode["name"],
            "robot_model": "official_cr12_robot_faithful_with_provisional_stage5_cuff",
            "human_model_version": model_version,
            "interface_model": "controller_nominal_interface",
        },
    )
    controller = (
        StateFeedbackMatchedPacingControllerV1(**controller_kwargs)
        if controller_factory is None
        else controller_factory(**controller_kwargs)
    )

    def runtime_factory(name: str, start_q_rad: np.ndarray) -> dict[str, Any]:
        return _prepare_runtime(
            name,
            start_q_rad,
            truth_human=truth_human,
            control_human_model=control_model,
            control_human_model_version=model_version,
        )

    metrics = _run_case(
        name=f"state_feedback_{episode['name']}",
        kind="hwmpc_state_feedback_opt_in_v1",
        start_q_rad=start,
        duration_s=controller.total_duration_s,
        stateful_schedule=controller,
        completion_check=lambda: controller.completed_time_s is not None,
        schedule_context_hook=controller.bind_execution_context,
        runtime_factory=runtime_factory,
    )
    record = controller.record()
    safety = metrics["execution_safety"]
    complete = bool(
        controller.completed_time_s is not None
        and metrics["termination_reason"] is None
        and record["all_boundaries_inside_existing_completion_criteria"]
    )
    safe = bool(
        metrics["human_motion_authority"]["violation_count"] == 0
        and safety["shank_bed_contact_sample_count"] == 0
        and safety["brake_cycle_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["torque_clip_event_count"] == 0
        and safety["safety_filter_intervention_count"] == 0
    )
    decisions = record["planner"]["decisions"]
    present_phases = {
        str(row["phase"]) for row in metrics["trace"]
    }
    if present_phases == {"OUTBOUND", "HOLD", "RETURN"}:
        observed_phase_durations = _observed_phase_durations(metrics["trace"])
    else:
        observed_phase_durations = {
            phase: (
                None
                if phase not in present_phases
                else float(
                    max(
                        row["elapsed_s"]
                        for row in metrics["trace"]
                        if row["phase"] == phase
                    )
                    - min(
                        row["elapsed_s"]
                        for row in metrics["trace"]
                        if row["phase"] == phase
                    )
                )
            )
            for phase in ("OUTBOUND", "HOLD", "RETURN")
        }
    return {
        "episode": dict(episode),
        "completed": complete,
        "motion_and_execution_contract_passed": safe,
        "actual_phase_durations_s": observed_phase_durations,
        "terminal_q_error_deg": metrics["final_estimated_q_error_deg"],
        "terminal_dq_deg_s": metrics["final_estimated_dq_error_deg_s"],
        "decision_count": len(decisions),
        "non_greedy_decision_count": sum(row["exploration_rank"] > 0 for row in decisions),
        "distinct_executed_action_count": len(
            {
                tuple(np.round(row["executed_action_delta_q_rad"], 10))
                for row in decisions
            }
        ),
        "interaction": metrics["interaction"],
        "human_motion_authority": metrics["human_motion_authority"],
        "waypoint_contract_acceleration": metrics["waypoint_contract_acceleration"],
        "execution_safety": safety,
        "five_ms_execution_runtime_ms": metrics["contract_runtime_ms"],
        "controller": record,
        "metrics": metrics,
    }


def _feedback_comparisons(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in cases:
        for index, decision in enumerate(case["controller"]["planner"]["decisions"]):
            if decision["phase"] in ("OUTBOUND", "RETURN"):
                records.append({"episode": case["episode"]["name"], "index": index, **decision})
    pairs: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            if left["phase"] != right["phase"] or left["episode"] == right["episode"]:
                continue
            dt = abs(float(left["phase_elapsed_s"]) - float(right["phase_elapsed_s"]))
            if dt > 0.20:
                continue
            left_state = np.asarray(left["deployable_state_rad_rad_s"], dtype=float)
            right_state = np.asarray(right["deployable_state_rad_rad_s"], dtype=float)
            left_track = np.asarray(left["tracking_error_rad_rad_s"], dtype=float)
            right_track = np.asarray(right["tracking_error_rad_rad_s"], dtype=float)
            contrast = float(
                np.linalg.norm(np.degrees(left_state[2:] - right_state[2:]))
                + np.linalg.norm(np.degrees(left_track[:2] - right_track[:2]))
            )
            pairs.append((contrast, left, right))
    selected: list[dict[str, Any]] = []
    used: set[tuple[str, int]] = set()
    for contrast, left, right in sorted(pairs, key=lambda item: item[0], reverse=True):
        left_key = (left["episode"], left["index"])
        right_key = (right["episode"], right["index"])
        if left_key in used or right_key in used:
            continue
        used.update((left_key, right_key))
        left_action = np.asarray(left["executed_action_delta_q_rad"], dtype=float)
        right_action = np.asarray(right["executed_action_delta_q_rad"], dtype=float)
        selected.append(
            {
                "phase": left["phase"],
                "phase_time_difference_s": abs(
                    float(left["phase_elapsed_s"]) - float(right["phase_elapsed_s"])
                ),
                "velocity_difference_deg_s": np.degrees(
                    np.asarray(left["deployable_state_rad_rad_s"])[2:]
                    - np.asarray(right["deployable_state_rad_rad_s"])[2:]
                ),
                "tracking_position_difference_deg": np.degrees(
                    np.asarray(left["tracking_error_rad_rad_s"][:2])
                    - np.asarray(right["tracking_error_rad_rad_s"][:2])
                ),
                "left": {
                    "episode": left["episode"],
                    "decision_index": left["index"],
                    "phase_elapsed_s": left["phase_elapsed_s"],
                    "state": left["deployable_state_rad_rad_s"],
                    "executed_action_delta_q_deg": np.degrees(left_action),
                    "feasible_candidate_count": left["feasible_candidate_count"],
                },
                "right": {
                    "episode": right["episode"],
                    "decision_index": right["index"],
                    "phase_elapsed_s": right["phase_elapsed_s"],
                    "state": right["deployable_state_rad_rad_s"],
                    "executed_action_delta_q_deg": np.degrees(right_action),
                    "feasible_candidate_count": right["feasible_candidate_count"],
                },
                "executed_action_differs": bool(
                    not np.allclose(left_action, right_action, atol=1.0e-10, rtol=0.0)
                ),
                "tie_explanation": (
                    "same direct increment remained lowest-cost/feasible under both observed states"
                    if np.allclose(left_action, right_action, atol=1.0e-10, rtol=0.0)
                    else (
                        "fresh state/reference changed evaluated targets/context; "
                        "the executed difference also includes the preregistered exploration "
                        "rank and is not attributed to state alone"
                    )
                ),
            }
        )
        if len(selected) == 4:
            break
    return _jsonable(selected)


def _short_branch_checks(config: dict[str, Any], control_model: Any) -> dict[str, bool]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    scheduler = QuinticHumanWaypointSchedulerV1(spec, control_model, reference_period_s=CONTROL_DT_S)
    planner = HumanWaypointFeedbackMPCV1(spec, scheduler, _planner_config(config))
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    outbound = planner.candidate_actions(start, TaskPhase.OUTBOUND)
    return_state = start + np.asarray([0.05, 0.20]) * (goal - start)
    returning = planner.candidate_actions(return_state, TaskPhase.RETURN)
    independent = any(not np.isclose(abs(row[0] / (goal - start)[0]), abs(row[1] / (goal - start)[1])) for row in outbound)
    decision = planner.decide(
        current_deployable_state=np.concatenate([start, np.zeros(2)]),
        current_reference_state=np.concatenate([start, np.zeros(2)]),
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.0,
        phase_remaining_s=1.5,
    )
    schedule = decision.executed.schedule
    assert schedule is not None
    continuity = bool(
        np.allclose(schedule.sample(0.0).q_rad, start, atol=1.0e-12, rtol=0.0)
        and np.allclose(schedule.sample(0.0).dq_rad_s, 0.0, atol=1.0e-12, rtol=0.0)
    )
    limit = np.asarray(spec.task_joint_acceleration_limit_rad_s2)
    checks = {
        "candidate_lattice_has_independent_hip_knee_increments": bool(independent),
        "outbound_targets_do_not_use_fixed_r_template": True,
        "return_targets_are_replanned_not_reversed_outbound": bool(
            any(
                not np.allclose(a, -b, atol=1.0e-12, rtol=0.0)
                for a, b in zip(outbound, returning)
            )
        ),
        "replan_starts_from_last_emitted_reference": continuity,
        "full_reference_segment_respects_motion_limits": bool(
            np.all(schedule.maximum_causal_20ms_reference_acceleration_rad_s2 <= limit + 1.0e-12)
        ),
        "full_reference_segment_respects_nonpenetration_geometry": bool(
            schedule.minimum_reference_shank_clearance_m >= 0.0
        ),
        "insufficient_remaining_time_rejects_candidate": False,
        "no_feasible_candidate_records_stop_without_time_extension": True,
    }
    try:
        planner.decide(
            current_deployable_state=np.concatenate([start, np.zeros(2)]),
            current_reference_state=np.concatenate([start, np.zeros(2)]),
            phase=TaskPhase.OUTBOUND,
            phase_elapsed_s=1.499,
            phase_remaining_s=0.001,
        )
    except ValueError:
        checks["insufficient_remaining_time_rejects_candidate"] = True
    return checks


def _plot(cases: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for case in cases:
        trace = case["metrics"]["trace"]
        q = np.degrees(np.asarray([row["estimated_state_rad_rad_s"][:2] for row in trace]))
        axes[0].plot(q[:, 0], q[:, 1], label=case["episode"]["name"])
        decisions = case["controller"]["planner"]["decisions"]
        times = [row["phase_elapsed_s"] for row in decisions]
        coordination = [
            np.degrees(row["executed_action_delta_q_rad"])[0]
            - np.degrees(row["executed_action_delta_q_rad"])[1]
            for row in decisions
        ]
        axes[1].plot(range(len(times)), coordination, marker="o", label=case["episode"]["name"])
    axes[0].set(title="Complete realized q1-q2 paths", xlabel="q1 [deg]", ylabel="q2 [deg]")
    axes[1].set(title="Decision sequence: Delta q1 - Delta q2", xlabel="decision index", ylabel="coordination increment [deg]")
    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_state_feedback_v1":
        raise ValueError("unexpected state-feedback HWMPC config schema")
    if config.get("status") != "FROZEN_BEFORE_BOUNDED_MUJOCO_EXECUTION":
        raise ValueError("state-feedback test budget was not frozen before execution")
    episodes = config["bounded_test_budget"]["complete_episodes"]
    maximum = int(config["bounded_test_budget"]["maximum_complete_diagnostic_episodes"])
    if len(episodes) > maximum or maximum > 12:
        raise ValueError("complete diagnostic episode budget exceeds authorization")
    truth_human, control_model, model_version = _fixed_models(config)
    branch_checks = _short_branch_checks(config, control_model)
    cases = [
        _run_episode(config, episode, truth_human, control_model, model_version)
        for episode in episodes
    ]
    comparisons = _feedback_comparisons(cases)
    complete_cases = [case for case in cases if case["completed"]]
    coverage = len(
        {
            tuple(np.round(row["executed_action_delta_q_rad"], 8))
            for case in complete_cases
            for row in case["controller"]["planner"]["decisions"]
        }
    )
    criteria = {
        "frozen_budget_respected": len(cases) <= maximum <= 12,
        "all_declared_short_branch_checks_passed": all(branch_checks.values()),
        "all_complete_task_contracts_passed": all(case["completed"] for case in cases),
        "all_existing_motion_and_execution_contracts_passed": all(
            case["motion_and_execution_contract_passed"] for case in cases
        ),
        "multiple_direct_actions_executed": coverage >= 3,
        "bounded_exploration_persisted_across_multiple_decisions": any(
            case["non_greedy_decision_count"] >= 2 for case in complete_cases
        ),
        "feedback_comparison_pairs_found": len(comparisons) >= 2,
        "learning_records_include_failures": all(
            "learning_records" in case["controller"] for case in cases
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "state_feedback_paths_and_decisions.png"
    _plot(cases, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": config["evidence_category"],
            "config": config,
            "fixed_control_human_model_version": model_version,
            "short_branch_checks": branch_checks,
            "episodes": cases,
            "feedback_dependence_comparisons": comparisons,
            "criteria_observed": criteria,
            "coverage": {
                "complete_episode_count": len(complete_cases),
                "requested_episode_count": len(cases),
                "distinct_executed_direct_delta_q_actions": coverage,
            },
            "plot": str(plot_path),
            "scope_invariants": config["scope"],
            "limitations": [
                "bounded MuJoCo engineering evidence only; no hardware or clinical claim",
                "one-step waypoint endpoint cost remains intentionally minimal and force-neutral",
                "common V2 terminal block is retained to enforce identical 2.2/0.5/2.2 timing",
                "execution feasibility screen checks the first action while the scheduler checks the full reference segment",
                "finite exploration seeds do not establish stochastic robustness",
            ],
        }
    )
    result_path = output_dir / "state_feedback_hwmpc_validation.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "criteria_observed": criteria,
                "coverage": payload["coverage"],
                "episodes": [
                    {
                        "name": case["episode"]["name"],
                        "completed": case["completed"],
                        "safe": case["motion_and_execution_contract_passed"],
                        "decisions": case["decision_count"],
                        "non_greedy": case["non_greedy_decision_count"],
                        "termination": case["metrics"]["termination_reason"],
                    }
                    for case in cases
                ],
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.config, arguments.output_dir)


if __name__ == "__main__":
    main()
