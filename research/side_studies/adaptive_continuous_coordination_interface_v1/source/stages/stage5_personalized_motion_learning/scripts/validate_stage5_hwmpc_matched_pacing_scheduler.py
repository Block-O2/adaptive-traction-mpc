#!/usr/bin/env python3
"""Audit V1 matched pacing and validate one boundary-conditioned V2 schedule."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_mpc import HumanWaypointMPCPrototypeV1
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedule,
    QuinticHumanWaypointSchedulerV1,
)
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


SCHEMA = "stage5_hwmpc_matched_pacing_scheduler_validation_v2"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_matched_pacing_scheduler_v2.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _suffix_start(mask: np.ndarray, times: np.ndarray) -> float | None:
    for index in range(len(mask)):
        if bool(np.all(mask[index:])):
            return float(times[index])
    return None


def _inside_intervals(
    times: np.ndarray, q_error_deg: np.ndarray, dq_deg_s: np.ndarray
) -> list[list[float]]:
    inside = np.all(np.abs(q_error_deg) <= 1.0 + 1.0e-12, axis=1) & np.all(
        np.abs(dq_deg_s) <= 2.0 + 1.0e-12, axis=1
    )
    indices = np.flatnonzero(inside)
    intervals: list[list[float]] = []
    if not len(indices):
        return intervals
    start = previous = int(indices[0])
    for index in indices[1:]:
        index = int(index)
        if index != previous + 1:
            intervals.append([float(times[start]), float(times[previous])])
            start = index
        previous = index
    intervals.append([float(times[start]), float(times[previous])])
    return intervals


def audit_v1_case(case: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the same phase-clock terminal opportunities from saved V1 data."""

    trace = case["metrics"]["trace"]
    phase_starts = {"OUTBOUND": 0.0, "RETURN": 2.7}
    goal_by_phase = {
        "OUTBOUND": np.asarray(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad, dtype=float
        ),
        "RETURN": np.asarray(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad, dtype=float
        ),
    }
    phases: dict[str, Any] = {}
    for phase in ("OUTBOUND", "RETURN"):
        rows = [row for row in trace if row["phase"] == phase]
        times = np.asarray([row["elapsed_s"] for row in rows], dtype=float)
        phase_times = times - phase_starts[phase]
        requested_q = np.asarray([row["requested_q_rad"] for row in rows])
        requested_dq = np.asarray([row["requested_dq_rad_s"] for row in rows])
        estimated = np.asarray(
            [row["estimated_state_rad_rad_s"] for row in rows], dtype=float
        )
        goal = goal_by_phase[phase]
        requested_q_error_deg = np.degrees(requested_q - goal)
        requested_dq_deg_s = np.degrees(requested_dq)
        realized_q_error_deg = np.degrees(estimated[:, :2] - goal)
        realized_dq_deg_s = np.degrees(estimated[:, 2:])
        speed = np.linalg.norm(requested_dq_deg_s, axis=1)
        late = np.flatnonzero(phase_times >= 1.4 - 1.0e-12)
        late_peak_index = int(late[np.argmax(speed[late])])
        requested_zero = np.all(np.abs(requested_dq_deg_s) <= 1.0e-6, axis=1)
        exact_terminal = requested_zero & np.all(
            np.abs(requested_q_error_deg) <= 1.0e-6, axis=1
        )
        intervals = _inside_intervals(
            phase_times, realized_q_error_deg, realized_dq_deg_s
        )
        boundary = next(
            row
            for row in case["controller"]["boundary_checks"]
            if row["phase"] == phase
        )
        phases[phase] = {
            "phase_duration_s": 2.2,
            "late_reference_speed_peak_time_s": float(phase_times[late_peak_index]),
            "late_reference_speed_peak_deg_s": float(speed[late_peak_index]),
            "deceleration_begins_after_late_peak_s": float(
                phase_times[min(late_peak_index + 1, len(phase_times) - 1)]
            ),
            "terminal_zero_velocity_reference_onset_s": _suffix_start(
                requested_zero, phase_times
            ),
            "exact_q_goal_zero_velocity_reference_onset_s": _suffix_start(
                exact_terminal, phase_times
            ),
            "terminal_requested_q_error_deg": requested_q_error_deg[-1],
            "terminal_requested_dq_deg_s": requested_dq_deg_s[-1],
            "terminal_realized_q_error_deg": realized_q_error_deg[-1],
            "terminal_realized_dq_deg_s": realized_dq_deg_s[-1],
            "completion_set_intervals_s": intervals,
            "entered_then_exited_completion_set": bool(
                intervals and intervals[-1][1] < 2.2 - 0.5 * CONTROL_DT_S
            ),
            "inside_at_fixed_boundary": bool(
                boundary["inside_existing_completion_criteria"]
            ),
            "natural_completion_time_s": boundary["natural_completion_time_s"],
        }
    return {
        "coordination_r": float(case["coordination_r"]),
        "order_seed": int(case["order_seed"]),
        "completed": bool(case["completed"]),
        "contact_sample_count": int(case["shank_bed_contact_sample_count"]),
        "phases": phases,
    }


def audit_v1(payload: dict[str, Any]) -> list[dict[str, Any]]:
    selected: dict[float, dict[str, Any]] = {}
    for case in sorted(
        payload["cases"], key=lambda row: (row["coordination_r"], row["order_seed"])
    ):
        selected.setdefault(float(case["coordination_r"]), case)
    return [audit_v1_case(selected[key]) for key in sorted(selected)]


class BoundaryConditionedMatchedPacingController:
    """V1 HWMPC path with one common exact-target terminal block per motion phase."""

    def __init__(
        self,
        mpc: HumanWaypointMPCPrototypeV1,
        scheduler: QuinticHumanWaypointSchedulerV1,
        *,
        coordination_r: float,
        pacing: dict[str, Any],
    ) -> None:
        self.mpc = mpc
        self.scheduler = scheduler
        self.coordination_r = float(coordination_r)
        self.phase_durations_s = {
            TaskPhase.OUTBOUND: float(pacing["outbound_duration_s"]),
            TaskPhase.HOLD: float(pacing["hold_duration_s"]),
            TaskPhase.RETURN: float(pacing["return_duration_s"]),
        }
        self.phase_starts_s = {
            TaskPhase.OUTBOUND: 0.0,
            TaskPhase.HOLD: float(pacing["outbound_duration_s"]),
            TaskPhase.RETURN: float(
                pacing["outbound_duration_s"] + pacing["hold_duration_s"]
            ),
        }
        self.total_duration_s = float(sum(self.phase_durations_s.values()))
        self.terminal_start_s = float(pacing["terminal_block_start_s"])
        self.terminal_transition_duration_s = float(
            pacing["terminal_transition_duration_s"]
        )
        self.terminal_settle_duration_s = float(
            pacing["terminal_settle_duration_s"]
        )
        expected_terminal = (
            self.terminal_start_s
            + self.terminal_transition_duration_s
            + self.terminal_settle_duration_s
        )
        for phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN):
            if not np.isclose(
                expected_terminal,
                self.phase_durations_s[phase],
                atol=1.0e-12,
                rtol=0.0,
            ):
                raise ValueError("terminal block must exactly fill both motion phases")
        self.phase = TaskPhase.OUTBOUND
        self.phase_controller = self._new_phase(TaskPhase.OUTBOUND)
        self.phase_records = [self.phase_controller]
        self.boundary_checks: list[dict[str, Any]] = []
        self.terminal_records: list[dict[str, Any]] = []
        self.terminal_schedule: QuinticHumanWaypointSchedule | None = None
        self.terminal_phase: TaskPhase | None = None
        self.last_executable_reference: Any | None = None
        self.execution_context: dict[str, Any] | None = None
        self.completed_time_s: float | None = None
        self._terminal_checked = False

    def _new_phase(self, phase: TaskPhase) -> _MPCPhaseController:
        return _MPCPhaseController(
            mpc=self.mpc,
            scheduler=self.scheduler,
            phase=phase,
            phase_start_s=self.phase_starts_s[phase],
            coordination_preference_r=self.coordination_r,
        )

    def bind_execution_context(self, **context: Any) -> None:
        self.execution_context = dict(context)
        self.phase_controller.bind_execution_context(**context)

    def _goal(self, phase: TaskPhase) -> np.ndarray:
        return np.asarray(
            self.scheduler.spec.start_return_target_rad
            if phase is TaskPhase.RETURN
            else self.scheduler.spec.outbound_goal_target_rad,
            dtype=float,
        )

    def _inside(self, state: np.ndarray, phase: TaskPhase) -> bool:
        return self.phase_controller._inside(state, self._goal(phase))

    def _record_boundary(
        self, phase: TaskPhase, time_s: float, state: np.ndarray
    ) -> bool:
        target = self._goal(phase)
        inside = self._inside(state, phase)
        self.boundary_checks.append(
            {
                "phase": phase.value,
                "boundary_time_s": float(time_s),
                "inside_existing_completion_criteria": inside,
                "q_error_deg": np.degrees(state[:2] - target),
                "dq_deg_s": np.degrees(state[2:]),
            }
        )
        return inside

    def _reset_terminal(self) -> None:
        self.terminal_schedule = None
        self.terminal_phase = None
        self.last_executable_reference = None

    def _start_terminal_schedule(
        self, phase_elapsed_s: float, state: np.ndarray
    ) -> None:
        if self.last_executable_reference is None:
            raise RuntimeError("terminal schedule has no preceding executable reference")
        goal = self._goal(self.phase)
        candidate = _candidate(
            f"matched_terminal_{self.phase.value.lower()}",
            self.phase,
            goal,
            np.zeros(2),
        )
        schedule = self.scheduler.plan_fixed_duration_reference_contract(
            current_q_hat_rad=self.last_executable_reference.q_waypoint_rad,
            current_dq_hat_rad_s=(
                self.last_executable_reference.dq_waypoint_rad_s
            ),
            candidate=candidate,
            duration_s=self.terminal_transition_duration_s,
            phase_elapsed_s=phase_elapsed_s,
        )
        self.terminal_schedule = schedule
        self.terminal_phase = self.phase
        self.terminal_records.append(
            {
                "phase": self.phase.value,
                "start_phase_elapsed_s": float(phase_elapsed_s),
                "transition_duration_s": self.terminal_transition_duration_s,
                "settle_duration_s": self.terminal_settle_duration_s,
                "start_state_rad_rad_s": state.copy(),
                "start_reference_q_rad": (
                    self.last_executable_reference.q_waypoint_rad.copy()
                ),
                "start_reference_dq_rad_s": (
                    self.last_executable_reference.dq_waypoint_rad_s.copy()
                ),
                "schedule": schedule.record(),
            }
        )

    def _terminal_candidate(
        self, phase_elapsed_s: float, state: np.ndarray
    ):
        if self.terminal_schedule is None or self.terminal_phase is not self.phase:
            self._start_terminal_schedule(phase_elapsed_s, state)
        assert self.terminal_schedule is not None
        elapsed = max(0.0, phase_elapsed_s - self.terminal_start_s)
        sample = self.terminal_schedule.sample(elapsed)
        return _candidate(
            f"matched_terminal_{self.phase.value.lower()}_{phase_elapsed_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def __call__(self, time_s: float, state: np.ndarray):
        hold_start = self.phase_starts_s[TaskPhase.HOLD]
        return_start = self.phase_starts_s[TaskPhase.RETURN]
        if self.phase is TaskPhase.OUTBOUND and time_s + 1.0e-12 >= hold_start:
            self._record_boundary(TaskPhase.OUTBOUND, hold_start, state)
            self.phase = TaskPhase.HOLD
            self._reset_terminal()
            self.phase_controller = self._new_phase(TaskPhase.HOLD)
            self.phase_records.append(self.phase_controller)
            if self.execution_context is not None:
                self.phase_controller.bind_execution_context(**self.execution_context)
        if self.phase is TaskPhase.HOLD and time_s + 1.0e-12 >= return_start:
            self._record_boundary(TaskPhase.HOLD, return_start, state)
            self.phase = TaskPhase.RETURN
            self._reset_terminal()
            self.phase_controller = self._new_phase(TaskPhase.RETURN)
            self.phase_records.append(self.phase_controller)
            if self.execution_context is not None:
                self.phase_controller.bind_execution_context(**self.execution_context)
        if (
            self.phase is TaskPhase.RETURN
            and time_s + 1.0e-12 >= self.total_duration_s
            and not self._terminal_checked
        ):
            self._terminal_checked = True
            if self._record_boundary(TaskPhase.RETURN, self.total_duration_s, state):
                self.completed_time_s = self.total_duration_s

        phase_elapsed_s = float(time_s - self.phase_starts_s[self.phase])
        if (
            self.phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN)
            and phase_elapsed_s + 1.0e-12 >= self.terminal_start_s
        ):
            return self._terminal_candidate(phase_elapsed_s, state)
        candidate = self.phase_controller(time_s, state)
        self.last_executable_reference = candidate
        return candidate

    def record(self) -> dict[str, Any]:
        return {
            "coordination_r": self.coordination_r,
            "phase_durations_s": {
                phase.value: value for phase, value in self.phase_durations_s.items()
            },
            "phase_starts_s": {
                phase.value: value for phase, value in self.phase_starts_s.items()
            },
            "total_duration_s": self.total_duration_s,
            "terminal_block": {
                "start_s": self.terminal_start_s,
                "transition_duration_s": self.terminal_transition_duration_s,
                "settle_duration_s": self.terminal_settle_duration_s,
                "target_dq_deg_s": [0.0, 0.0],
            },
            "completed_time_s": self.completed_time_s,
            "boundary_checks": _jsonable(self.boundary_checks),
            "all_boundaries_inside_existing_completion_criteria": bool(
                len(self.boundary_checks) == 3
                and all(
                    row["inside_existing_completion_criteria"]
                    for row in self.boundary_checks
                )
            ),
            "terminal_records": _jsonable(self.terminal_records),
            "phases": [item.record() for item in self.phase_records],
            "mpc": self.mpc.record(),
        }


def _run_profile(
    *,
    profile: dict[str, Any],
    config: dict[str, Any],
    truth_human: Any,
    control_human_model: Any,
    control_model_version: str,
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec, control_human_model, reference_period_s=CONTROL_DT_S
    )
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    controller = BoundaryConditionedMatchedPacingController(
        mpc,
        scheduler,
        coordination_r=float(profile["r"]),
        pacing=config["matched_pacing"],
    )

    def runtime_factory(name: str, start_q_rad: np.ndarray) -> dict[str, Any]:
        return _prepare_runtime(
            name,
            start_q_rad,
            truth_human=truth_human,
            control_human_model=control_human_model,
            control_human_model_version=control_model_version,
        )

    metrics = _run_case(
        name=f"matched_pacing_v2_{profile['name']}",
        kind="hwmpc_matched_pacing_scheduler_v2",
        start_q_rad=start,
        duration_s=controller.total_duration_s,
        stateful_schedule=controller,
        completion_check=lambda: controller.completed_time_s is not None,
        schedule_context_hook=controller.bind_execution_context,
        runtime_factory=runtime_factory,
    )
    record = controller.record()
    observed = _observed_phase_durations(metrics["trace"])
    maximum_duration_error = max(
        abs(observed[phase] - record["phase_durations_s"][phase])
        for phase in observed
    )
    safety = metrics["execution_safety"]
    complete = bool(
        controller.completed_time_s is not None
        and metrics["termination_reason"] is None
        and metrics["final_within_existing_task_tolerance"]
    )
    safe = bool(
        metrics["human_motion_authority"]["violation_count"] == 0
        and safety["shank_bed_contact_sample_count"] == 0
        and safety["brake_cycle_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["torque_clip_event_count"] == 0
    )
    exact_terminal_references = all(
        np.allclose(
            item["schedule"]["target_q_rad"],
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad
            if item["phase"] == "RETURN"
            else PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad,
            atol=1.0e-12,
            rtol=0.0,
        )
        and np.allclose(
            item["schedule"]["target_dq_rad_s"], 0.0, atol=1.0e-12, rtol=0.0
        )
        for item in record["terminal_records"]
    )
    interaction = metrics["interaction"]
    return {
        "profile_name": str(profile["name"]),
        "coordination_r": float(profile["r"]),
        "completed": complete,
        "terminal_completion_criteria_passed": bool(
            record["all_boundaries_inside_existing_completion_criteria"]
        ),
        "exact_terminal_references": bool(exact_terminal_references),
        "matched_pacing_contract_passed": bool(
            record["all_boundaries_inside_existing_completion_criteria"]
            and maximum_duration_error <= CONTROL_DT_S + 1.0e-12
            and len(record["terminal_records"]) == 2
            and exact_terminal_references
        ),
        "safety_contract_passed": safe,
        "actual_phase_durations_s": observed,
        "maximum_phase_duration_error_s": maximum_duration_error,
        "terminal_q_error_deg": metrics["final_estimated_q_error_deg"],
        "terminal_dq_deg_s": metrics["final_estimated_dq_deg_s"],
        "scheduled_peak_abs_20ms_acceleration_deg_s2": metrics[
            "waypoint_contract_acceleration"
        ]["peak_abs_scheduled_20ms_acceleration_deg_s2"],
        "realized_peak_abs_20ms_acceleration_deg_s2": metrics[
            "human_motion_authority"
        ]["peak_abs_20ms_acceleration_deg_s2"],
        "cumulative_measured_cuff_force_n_s": interaction[
            "integral_cuff_force_n_s"
        ],
        "peak_measured_cuff_force_n": interaction["peak_cuff_force_n"],
        "peak_measured_cuff_moment_nm": interaction["peak_cuff_moment_nm"],
        "maximum_robot_torque_fraction": safety["maximum_robot_torque_fraction"],
        "minimum_truth_shank_clearance_mm": safety[
            "minimum_truth_shank_clearance_mm"
        ],
        "shank_bed_contact_sample_count": safety[
            "shank_bed_contact_sample_count"
        ],
        "safety_filter_intervention_count": safety[
            "safety_filter_intervention_count"
        ],
        "brake_cycle_count": safety["brake_cycle_count"],
        "force_gate_event_count": safety["force_gate_event_count"],
        "torque_clip_event_count": safety["torque_clip_event_count"],
        "human_motion_violation_count": metrics["human_motion_authority"][
            "violation_count"
        ],
        "controller": record,
        "metrics": metrics,
    }


def _plot(audit: list[dict[str, Any]], cases: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    colors = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(cases)))
    for color, case in zip(colors, sorted(cases, key=lambda row: row["coordination_r"]), strict=True):
        trace = case["metrics"]["trace"]
        for phase, linestyle in (("OUTBOUND", "-"), ("RETURN", "--")):
            q = np.degrees(
                np.asarray(
                    [
                        row["estimated_state_rad_rad_s"][:2]
                        for row in trace
                        if row["phase"] == phase
                    ]
                )
            )
            axes[0].plot(q[:, 0], q[:, 1], color=color, linestyle=linestyle)
        axes[0].plot([], [], color=color, label=f"r={case['coordination_r']:+.3f}")
    axes[0].set(
        title="V2 realized q1-q2 paths",
        xlabel="q1 [deg]",
        ylabel="q2 [deg]",
    )
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    r_values = [row["coordination_r"] for row in audit]
    old_dq = [
        max(abs(value) for value in row["phases"]["RETURN"]["terminal_realized_dq_deg_s"])
        for row in audit
    ]
    new_dq = [
        max(abs(value) for value in case["terminal_dq_deg_s"])
        for case in sorted(cases, key=lambda row: row["coordination_r"])
    ]
    axes[1].plot(r_values, old_dq, marker="o", label="V1")
    axes[1].plot(r_values, new_dq, marker="o", label="V2")
    axes[1].axhline(2.0, color="black", linestyle=":", label="existing criterion")
    axes[1].set(
        title="RETURN terminal velocity quality",
        xlabel="coordination r",
        ylabel="max |dq| [deg/s]",
    )
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(
        [case["coordination_r"] for case in sorted(cases, key=lambda row: row["coordination_r"])],
        [case["minimum_truth_shank_clearance_mm"] for case in sorted(cases, key=lambda row: row["coordination_r"])],
        marker="o",
    )
    axes[2].axhline(0.0, color="black", linestyle=":")
    axes[2].set(
        title="V2 minimum shank-table clearance",
        xlabel="coordination r",
        ylabel="clearance [mm]",
    )
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_matched_pacing_scheduler_v2":
        raise ValueError("unexpected matched-pacing scheduler schema")
    if config.get("status") != "FROZEN_AFTER_V1_SCHEDULE_AUDIT_BEFORE_V2_EXECUTION":
        raise ValueError("matched-pacing V2 config was not frozen before execution")
    source = Path(config["audit_source"]["artifact"])
    if _sha256(source) != config["audit_source"]["sha256"]:
        raise ValueError("V1 matched-pacing audit source hash changed")
    v1_payload = json.loads(source.read_text(encoding="utf-8"))
    v1_audit = audit_v1(v1_payload)
    profiles = config["coordination"]["representative_profiles"]
    support = config["coordination"]["frozen_support_interval"]
    if profiles[0]["r"] != support[0] or profiles[-1]["r"] != support[1]:
        raise ValueError("representative set must retain both frozen r boundaries")
    pacing = config["matched_pacing"]
    if not np.isclose(
        pacing["hold_duration_s"],
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.hold_duration_s,
    ) or not np.isclose(pacing["control_period_s"], CONTROL_DT_S):
        raise ValueError("V2 changed registered HOLD or control timing")
    truth_human, control_model, model_version = _fixed_models(config)
    rng = np.random.default_rng(int(config["execution"]["order_seed"]))
    cases = [
        _run_profile(
            profile=profiles[int(index)],
            config=config,
            truth_human=truth_human,
            control_human_model=control_model,
            control_model_version=model_version,
        )
        for index in rng.permutation(len(profiles))
    ]
    cases.sort(key=lambda row: row["coordination_r"])
    all_valid = all(
        case["completed"]
        and case["matched_pacing_contract_passed"]
        and case["safety_contract_passed"]
        for case in cases
    )
    previous_unfair = any(
        row["phases"]["RETURN"]["entered_then_exited_completion_set"]
        for row in v1_audit
    ) and any(
        row["phases"]["RETURN"]["exact_q_goal_zero_velocity_reference_onset_s"]
        is None
        for row in v1_audit
    )
    any_improved = any(
        case["completed"]
        and not next(
            row for row in v1_audit if row["coordination_r"] == case["coordination_r"]
        )["completed"]
        for case in cases
    )
    if all_valid:
        decision = "MP-A — COMMON MATCHED-PACING SCHEDULE VALIDATED ACROSS USEFUL r RANGE"
    elif previous_unfair and any_improved:
        decision = (
            "MP-B — SCHEDULER IMPROVES FAIRNESS, BUT SOME r VALUES ARE GENUINELY "
            "INFEASIBLE AT THIS PACING"
        )
    else:
        decision = "MP-C — CURRENT FIXED PACING CANNOT SUPPORT A FAIR r COMPARISON"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "matched_pacing_scheduler_v2.png"
    _plot(v1_audit, cases, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": config["evidence_category"],
            "decision": decision,
            "config": config,
            "fixed_model_version": model_version,
            "v1_schedule_audit": v1_audit,
            "v2_cases": cases,
            "criteria_observed": {
                "v1_schedule_was_not_terminally_equivalent": previous_unfair,
                "all_v2_cases_completed": all(case["completed"] for case in cases),
                "all_v2_phase_duration_clocks_matched": all(
                    case["maximum_phase_duration_error_s"]
                    <= CONTROL_DT_S + 1.0e-12
                    for case in cases
                ),
                "all_v2_terminal_completion_criteria_passed": all(
                    case["terminal_completion_criteria_passed"] for case in cases
                ),
                "all_v2_motion_and_execution_contracts_passed": all(
                    case["safety_contract_passed"] for case in cases
                ),
                "all_terminal_references_used_exact_q_goal_and_zero_dq": all(
                    len(case["controller"]["terminal_records"]) == 2
                    and case["exact_terminal_references"]
                    for case in cases
                ),
            },
            "scope_invariants": config["scope"],
            "plot": str(plot_path),
        }
    )
    result_path = output_dir / "matched_pacing_scheduler_v2.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "criteria_observed": payload["criteria_observed"],
                "cases": [
                    {
                        "r": case["coordination_r"],
                        "completed": case["completed"],
                        "safe": case["safety_contract_passed"],
                        "terminal_q_error_deg": case["terminal_q_error_deg"],
                        "terminal_dq_deg_s": case["terminal_dq_deg_s"],
                        "minimum_clearance_mm": case[
                            "minimum_truth_shank_clearance_mm"
                        ],
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
