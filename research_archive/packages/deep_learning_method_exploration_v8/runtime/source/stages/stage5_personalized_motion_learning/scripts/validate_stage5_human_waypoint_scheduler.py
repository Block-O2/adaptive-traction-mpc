#!/usr/bin/env python3
"""Bounded CR12 validation of the deterministic Human-waypoint scheduler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_scheduler import (
    HUMAN_WAYPOINT_SCHEDULER_VERSION,
    QuinticHumanWaypointSchedule,
    QuinticHumanWaypointSchedulerV1,
    QuinticHumanWaypointSchedulerSession,
    WaypointGeometryInfeasible,
    shank_table_clearance_m,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _candidate,
    _jsonable,
    _prepare_runtime,
    _run_case,
)


SCHEMA = "stage5_human_waypoint_scheduler_validation_v1"
DEFAULT_PREVIOUS_RESULT = Path(
    "stages/stage5_personalized_motion_learning/results/engineering_validation/"
    "human_waypoint_shadow_v1_attempt_03/human_waypoint_validation.json"
)


class _GovernedTargetScheduler:
    """Advance one finite quintic path under the causal execution-semantic gate."""

    def __init__(
        self,
        scheduler: QuinticHumanWaypointSchedulerV1,
        candidate: HumanWaypointCandidate,
    ) -> None:
        self.scheduler = scheduler
        self.candidate = candidate
        self.last_high_level_time_s: float | None = None
        self.current_reference: HumanWaypointCandidate | None = None
        self.session: QuinticHumanWaypointSchedulerSession | None = None
        self.runtime_ms: list[float] = []

    def update(
        self,
        high_level_time_s: float,
        deployable_state: np.ndarray,
        phase_elapsed_s: float,
    ) -> HumanWaypointCandidate:
        if self.last_high_level_time_s != high_level_time_s:
            started = perf_counter()
            if self.session is None:
                self.session = self.scheduler.start_session(
                    current_q_hat_rad=deployable_state[:2],
                    current_dq_hat_rad_s=deployable_state[2:],
                    candidate=self.candidate,
                    phase_elapsed_s=phase_elapsed_s,
                )
            sample = self.session.advance(
                current_q_hat_rad=deployable_state[:2],
                current_dq_hat_rad_s=deployable_state[2:],
                phase_elapsed_s=phase_elapsed_s,
            )
            self.runtime_ms.append(1000.0 * (perf_counter() - started))
            self.current_reference = _candidate(
                f"{self.candidate.label}_scheduled_{high_level_time_s:.3f}",
                self.candidate.phase,
                sample.q_rad,
                sample.dq_rad_s,
            )
            self.last_high_level_time_s = high_level_time_s
        assert self.current_reference is not None
        return self.current_reference

    def __call__(
        self, high_level_time_s: float, deployable_state: np.ndarray
    ) -> HumanWaypointCandidate:
        return self.update(
            high_level_time_s, deployable_state, phase_elapsed_s=high_level_time_s
        )

    def summary(self) -> dict[str, Any]:
        runtime = np.asarray(self.runtime_ms, dtype=float)
        session_record = None if self.session is None else self.session.record()
        return {
            "mode": "finite_quintic_path_with_causal_5ms_progress_governor",
            "initial_plan_duration_s": (
                None
                if session_record is None
                else session_record["schedule"]["duration_s"]
            ),
            "minimum_planned_shank_clearance_m": (
                None
                if session_record is None
                else session_record["schedule"][
                    "minimum_reference_shank_clearance_m"
                ]
            ),
            "runtime_ms": {
                "count": int(len(runtime)),
                "p95": None if not len(runtime) else float(np.percentile(runtime, 95)),
                "maximum": None if not len(runtime) else float(np.max(runtime)),
            },
            "session": session_record,
        }


def _target_tracking(case: dict[str, Any], target_q_rad: np.ndarray) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    trace = case["trace"]
    elapsed = np.asarray([row["elapsed_s"] for row in trace])
    estimated = np.asarray([row["estimated_state_rad_rad_s"] for row in trace])
    q_error = estimated[:, :2] - target_q_rad
    dq_error = estimated[:, 2:]
    inside = np.all(
        np.abs(q_error) <= np.asarray(spec.joint_angle_completion_tolerance_rad),
        axis=1,
    ) & np.all(
        np.abs(dq_error)
        <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s),
        axis=1,
    )
    settling_time = None
    for index in np.flatnonzero(inside):
        if np.all(inside[index:]):
            settling_time = float(elapsed[index])
            break
    direction = np.sign(target_q_rad - np.radians(case["start_q_deg"]))
    overshoot = np.maximum(direction[None, :] * q_error, 0.0)
    return {
        "target_q_deg": np.degrees(target_q_rad),
        "final_target_q_error_deg": np.degrees(q_error[-1]),
        "final_target_dq_error_deg_s": np.degrees(dq_error[-1]),
        "peak_target_overshoot_deg": np.degrees(np.max(overshoot, axis=0)),
        "settling_time_to_target_with_existing_tolerances_s": settling_time,
        "final_target_inside_existing_tolerances": bool(inside[-1]),
    }


def _step_comparison(
    previous: dict[str, Any],
    scheduled_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    previous_by_name = {case["name"]: case for case in previous["cases"]}
    comparisons: list[dict[str, Any]] = []
    for case in scheduled_cases:
        before = previous_by_name[case["name"]]
        after_metrics = case.get("metrics")
        comparisons.append(
            {
                "name": case["name"],
                "step": {
                    "termination_reason": before["termination_reason"],
                    "peak_abs_20ms_acceleration_deg_s2": before[
                        "human_motion_authority"
                    ]["peak_abs_20ms_acceleration_deg_s2"],
                    "peak_cuff_force_n": before["interaction"]["peak_cuff_force_n"],
                    "peak_cuff_moment_nm": before["interaction"]["peak_cuff_moment_nm"],
                    "minimum_truth_shank_clearance_mm": before["execution_safety"][
                        "minimum_truth_shank_clearance_mm"
                    ],
                    "shank_bed_contact_sample_count": before["execution_safety"][
                        "shank_bed_contact_sample_count"
                    ],
                },
                "scheduled": (
                    {
                        "status": case["status"],
                        "reason": case["reason"],
                        "target_geometric_clearance_mm": case[
                            "target_geometric_clearance_mm"
                        ],
                    }
                    if after_metrics is None
                    else {
                        "status": case["status"],
                        "initial_transition_duration_s": case["scheduler"][
                            "initial_plan_duration_s"
                        ],
                        "termination_reason": after_metrics["termination_reason"],
                        "target_tracking": case["target_tracking"],
                        "peak_abs_20ms_acceleration_deg_s2": after_metrics[
                            "human_motion_authority"
                        ]["peak_abs_20ms_acceleration_deg_s2"],
                        "peak_cuff_force_n": after_metrics["interaction"][
                            "peak_cuff_force_n"
                        ],
                        "peak_cuff_moment_nm": after_metrics["interaction"][
                            "peak_cuff_moment_nm"
                        ],
                        "minimum_truth_shank_clearance_mm": after_metrics[
                            "execution_safety"
                        ]["minimum_truth_shank_clearance_mm"],
                        "shank_bed_contact_sample_count": after_metrics[
                            "execution_safety"
                        ]["shank_bed_contact_sample_count"],
                    }
                ),
            }
        )
    return comparisons


def _case_clean(case: dict[str, Any]) -> bool:
    metrics = case.get("metrics")
    if metrics is None:
        return False
    safety = metrics["execution_safety"]
    return bool(
        metrics["termination_reason"] is None
        and case["target_tracking"]["final_target_inside_existing_tolerances"]
        and metrics["human_motion_authority"]["violation_count"] == 0
        and safety["brake_cycle_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["torque_clip_event_count"] == 0
        and safety["shank_bed_contact_sample_count"] == 0
        and safety["minimum_truth_shank_clearance_mm"] >= 0.0
    )


def _phase_entry_inside_tolerance(
    trace: list[dict[str, Any]],
    phase: TaskPhase,
    target_q_rad: np.ndarray,
) -> bool:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    row = next((item for item in trace if item["phase"] == phase.value), None)
    if row is None:
        return False
    state = np.asarray(row["estimated_state_rad_rad_s"])
    return bool(
        np.all(
            np.abs(state[:2] - target_q_rad)
            <= np.asarray(spec.joint_angle_completion_tolerance_rad)
        )
        and np.all(
            np.abs(state[2:])
            <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s)
        )
    )


class _TaskSequenceController:
    """Validation-only phase driver using the registered completion and HOLD rules."""

    def __init__(
        self,
        scheduler: QuinticHumanWaypointSchedulerV1,
        start_q_rad: np.ndarray,
        goal_q_rad: np.ndarray,
    ) -> None:
        self.scheduler = scheduler
        self.spec = scheduler.spec
        self.start_q_rad = start_q_rad.copy()
        self.goal_q_rad = goal_q_rad.copy()
        self.phase = TaskPhase.OUTBOUND
        self.phase_start_s = 0.0
        self.completed_time_s: float | None = None
        self.outbound_governor = _GovernedTargetScheduler(
            scheduler,
            _candidate(
                "registered_outbound", TaskPhase.OUTBOUND, goal_q_rad, np.zeros(2)
            ),
        )
        self.hold_schedule: QuinticHumanWaypointSchedule | None = None
        self.return_governor: _GovernedTargetScheduler | None = None

    def _inside(self, state: np.ndarray, target_q_rad: np.ndarray) -> bool:
        return bool(
            np.all(
                np.abs(state[:2] - target_q_rad)
                <= np.asarray(self.spec.joint_angle_completion_tolerance_rad)
            )
            and np.all(
                np.abs(state[2:])
                <= np.asarray(self.spec.joint_velocity_completion_tolerance_rad_s)
            )
        )

    def __call__(
        self, high_level_time_s: float, deployable_state: np.ndarray
    ) -> HumanWaypointCandidate:
        phase_elapsed_s = high_level_time_s - self.phase_start_s
        if self.phase is TaskPhase.OUTBOUND:
            if self._inside(deployable_state, self.goal_q_rad):
                self.phase = TaskPhase.HOLD
                self.phase_start_s = high_level_time_s
                self.hold_schedule = self.scheduler.plan(
                    current_q_hat_rad=deployable_state[:2],
                    current_dq_hat_rad_s=deployable_state[2:],
                    candidate=_candidate(
                        "registered_hold",
                        TaskPhase.HOLD,
                        self.goal_q_rad,
                        np.zeros(2),
                    ),
                )
                phase_elapsed_s = 0.0
            else:
                return self.outbound_governor.update(
                    high_level_time_s,
                    deployable_state,
                    phase_elapsed_s,
                )
        if self.phase is TaskPhase.HOLD:
            assert self.hold_schedule is not None
            if phase_elapsed_s + 1.0e-12 >= self.spec.hold_duration_s:
                self.phase = TaskPhase.RETURN
                self.phase_start_s = high_level_time_s
                self.return_governor = _GovernedTargetScheduler(
                    self.scheduler,
                    _candidate(
                        "registered_return",
                        TaskPhase.RETURN,
                        self.start_q_rad,
                        np.zeros(2),
                    ),
                )
                phase_elapsed_s = 0.0
            else:
                sample = self.hold_schedule.sample(phase_elapsed_s)
                return _candidate(
                    "registered_hold",
                    TaskPhase.HOLD,
                    sample.q_rad,
                    sample.dq_rad_s,
                )
        assert self.return_governor is not None
        if (
            self.completed_time_s is None
            and self._inside(deployable_state, self.start_q_rad)
        ):
            self.completed_time_s = high_level_time_s
        return self.return_governor.update(
            high_level_time_s,
            deployable_state,
            phase_elapsed_s,
        )


def _plot(
    cases: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    sequence: dict[str, Any],
    path: Path,
) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(11, 8))
    trace = sequence["metrics"]["trace"]
    elapsed = np.asarray([row["elapsed_s"] for row in trace])
    requested = np.degrees(np.asarray([row["requested_q_rad"] for row in trace]))
    realized = np.degrees(
        np.asarray([row["estimated_state_rad_rad_s"] for row in trace])[:, :2]
    )
    for joint in range(2):
        axes[0].plot(elapsed, requested[:, joint], "--", label=f"requested q{joint + 1}")
        axes[0].plot(elapsed, realized[:, joint], label=f"realized q{joint + 1}")
    axes[0].set_title("Scheduled registered OUTBOUND / HOLD / RETURN")
    axes[0].set_ylabel("Human angle [deg]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=2)

    labels = [item["name"].replace("outbound_", "O-").replace("return_", "R-") for item in comparison]
    step_q2 = [item["step"]["peak_abs_20ms_acceleration_deg_s2"][1] for item in comparison]
    scheduled_q2 = [
        np.nan
        if item["scheduled"]["status"] != "EXECUTED"
        or item["scheduled"]["peak_abs_20ms_acceleration_deg_s2"][1] is None
        else item["scheduled"]["peak_abs_20ms_acceleration_deg_s2"][1]
        for item in comparison
    ]
    x = np.arange(len(labels))
    axes[1].bar(x - 0.2, step_q2, width=0.4, label="step waypoint")
    axes[1].bar(x + 0.2, scheduled_q2, width=0.4, label="scheduled waypoint")
    for index, case in enumerate(cases):
        if case["status"] != "EXECUTED":
            axes[1].text(index + 0.2, 10.0, "geometry\nrejected", ha="center", va="bottom")
    axes[1].set_xticks(x, labels, rotation=20)
    axes[1].set_ylabel("peak |q2 20 ms acceleration| [deg/s2]")
    axes[1].set_title("Matched step versus scheduled waypoint response")
    axes[1].grid(True, axis="y", alpha=0.3)
    axes[1].legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(output_dir: Path, previous_result_path: Path) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    previous = json.loads(previous_result_path.read_text(encoding="utf-8"))
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    return_start = start + 0.20 * (
        np.asarray(spec.outbound_goal_target_rad, dtype=float) - start
    )
    planning_runtime = _prepare_runtime("waypoint_scheduler_planning", start)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec,
        planning_runtime["human_model"],
        reference_period_s=CONTROL_DT_S,
    )
    definitions = [
        ("outbound_hip_biased", start, TaskPhase.OUTBOUND, np.radians([1.25, 0.50])),
        ("outbound_balanced", start, TaskPhase.OUTBOUND, np.radians([1.00, 1.00])),
        ("outbound_knee_biased", start, TaskPhase.OUTBOUND, np.radians([0.50, 3.00])),
        ("return_hip_biased", return_start, TaskPhase.RETURN, np.radians([-1.25, -0.50])),
        ("return_balanced", return_start, TaskPhase.RETURN, np.radians([-1.00, -1.00])),
        ("return_knee_biased", return_start, TaskPhase.RETURN, np.radians([-0.50, -3.00])),
    ]
    cases: list[dict[str, Any]] = []
    for name, initial_q, phase, delta in definitions:
        target_q = initial_q + delta
        candidate = _candidate(name, phase, target_q, np.zeros(2))
        try:
            scheduler.plan(
                current_q_hat_rad=initial_q,
                current_dq_hat_rad_s=np.zeros(2),
                candidate=candidate,
                phase_elapsed_s=0.0,
            )
        except WaypointGeometryInfeasible as error:
            cases.append(
                {
                    "name": name,
                    "status": "GEOMETRY_REJECTED",
                    "reason": str(error),
                    "target_q_deg": np.degrees(target_q),
                    "target_geometric_clearance_mm": 1000.0
                    * shank_table_clearance_m(target_q),
                    "scheduler": None,
                    "target_tracking": None,
                    "metrics": None,
                }
            )
            continue
        governed = _GovernedTargetScheduler(scheduler, candidate)
        metrics = _run_case(
            name=name,
            kind="scheduled_single_waypoint",
            start_q_rad=initial_q,
            duration_s=0.75,
            stateful_schedule=governed,
        )
        case = {
            "name": name,
            "status": "EXECUTED",
            "reason": None,
            "target_q_deg": np.degrees(target_q),
            "target_geometric_clearance_mm": 1000.0
            * shank_table_clearance_m(target_q),
            "scheduler": governed.summary(),
            "target_tracking": _target_tracking(metrics, target_q),
            "metrics": metrics,
        }
        cases.append(case)

    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    sequence_controller = _TaskSequenceController(scheduler, start, goal)
    sequence_metrics = _run_case(
        name="registered_outbound_hold_return",
        kind="scheduled_sequence",
        start_q_rad=start,
        duration_s=(
            2.0 * spec.phase_timeout_s + spec.hold_duration_s + CONTROL_DT_S
        ),
        stateful_schedule=sequence_controller,
        completion_check=lambda: sequence_controller.completed_time_s is not None,
    )
    sequence = {
        "name": "registered_outbound_hold_return",
        "scheduler": {
            "outbound": sequence_controller.outbound_governor.summary(),
            "hold": (
                None
                if sequence_controller.hold_schedule is None
                else sequence_controller.hold_schedule.record()
            ),
            "return": (
                None
                if sequence_controller.return_governor is None
                else sequence_controller.return_governor.summary()
            ),
        },
        "completed_time_s": sequence_controller.completed_time_s,
        "phase_entry_inside_existing_tolerances": {
            "HOLD": _phase_entry_inside_tolerance(
                sequence_metrics["trace"], TaskPhase.HOLD, goal
            ),
            "RETURN": _phase_entry_inside_tolerance(
                sequence_metrics["trace"], TaskPhase.RETURN, goal
            ),
        },
        "target_tracking": _target_tracking(sequence_metrics, start),
        "metrics": sequence_metrics,
    }
    comparison = _step_comparison(previous, cases)

    executed_cases = [case for case in cases if case["status"] == "EXECUTED"]
    rejected_cases = [case for case in cases if case["status"] != "EXECUTED"]
    scheduled_execution_reliable = all(_case_clean(case) for case in executed_cases)
    feasible_tracking_completed = all(
        case["metrics"]["termination_reason"] is None
        and case["target_tracking"]["final_target_inside_existing_tolerances"]
        for case in executed_cases
    )
    feasible_motion_envelope_preserved = all(
        case["metrics"]["human_motion_authority"]["violation_count"] == 0
        for case in executed_cases
    )
    feasible_noncontact_preserved = all(
        case["metrics"]["execution_safety"]["shank_bed_contact_sample_count"] == 0
        and case["metrics"]["execution_safety"]["minimum_truth_shank_clearance_mm"]
        >= 0.0
        for case in executed_cases
    )
    sequence_completed = bool(
        sequence_controller.completed_time_s is not None
        and sequence_metrics["termination_reason"] is None
        and sequence["target_tracking"]["final_target_inside_existing_tolerances"]
        and all(sequence["phase_entry_inside_existing_tolerances"].values())
    )
    sequence_clean = bool(
        sequence_completed
        and sequence_metrics["human_motion_authority"]["violation_count"] == 0
        and sequence_metrics["execution_safety"]["brake_cycle_count"] == 0
        and sequence_metrics["execution_safety"]["force_gate_event_count"] == 0
        and sequence_metrics["execution_safety"]["torque_clip_event_count"] == 0
        and sequence_metrics["execution_safety"]["shank_bed_contact_sample_count"] == 0
        and sequence_metrics["execution_safety"]["minimum_truth_shank_clearance_mm"]
        >= 0.0
    )
    if scheduled_execution_reliable and sequence_clean and not rejected_cases:
        decision = "WS-A — WAYPOINT SCHEDULING MAKES THE HUMAN-WAYPOINT ABSTRACTION EXECUTABLE"
        remaining_limitation = None
    elif scheduled_execution_reliable and sequence_clean and rejected_cases:
        decision = "WS-B — SCHEDULING HELPS, BUT SOME WAYPOINT REGIONS REMAIN INFEASIBLE"
        remaining_limitation = (
            "the requested Human waypoint itself lies outside the existing non-contact "
            "Human/shank-table geometry; temporal smoothing cannot make that state feasible"
        )
    else:
        decision = "WS-C — CURRENT EXECUTION LAYER CANNOT RELIABLY TRACK SCHEDULED HUMAN WAYPOINTS"
        if sequence_completed:
            remaining_limitation = (
                "the registered phases complete with monotonic governor progress and no "
                "motion-envelope violation, but the existing execution has brief "
                "Human-table contact and therefore does not satisfy the stricter clean "
                "non-contact validation criterion"
            )
        elif (
            sequence_metrics["termination_reason"] is not None
            and sequence_metrics["termination_reason"].startswith(
                "WAYPOINT_CONTRACT_REJECTED"
            )
        ):
            remaining_limitation = (
                "the reference-motion governor remains monotonic, but the unchanged "
                "downstream waypoint contract rejects the accepted reference using its "
                "instantaneous PD tracking-request acceleration check"
            )
        else:
            remaining_limitation = (
                "the unchanged CR12 execution response cannot sustain monotonic full-range "
                "Human-waypoint path progress under the existing acceleration request limits; "
                "the causal governor regresses or stalls before the registered goal"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "waypoint_scheduler_comparison.png"
    _plot(cases, comparison, sequence, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_shadow_engineering_validation",
            "decision": decision,
            "remaining_structural_limitation": remaining_limitation,
            "scheduler_contract": {
                "version": HUMAN_WAYPOINT_SCHEDULER_VERSION,
                "method": "shortest 5 ms-grid quintic with causal execution-semantic progress gating",
                "geometry_rule": "reject any sampled reference with analytic capsule clearance below 0 m",
                "clearance_margin_m": 0.0,
                "learned": False,
                "production_authority": False,
                "new_controller": False,
                "execution_gains_tuned": False,
            },
            "matched_single_waypoints": cases,
            "step_vs_scheduled": comparison,
            "sequence": sequence,
            "criteria_observed": {
                "geometrically_feasible_single_cases_execute_cleanly": scheduled_execution_reliable,
                "geometrically_feasible_single_cases_track_to_target": feasible_tracking_completed,
                "geometrically_feasible_single_cases_preserve_20ms_motion_envelope": (
                    feasible_motion_envelope_preserved
                ),
                "geometrically_feasible_single_cases_remain_noncontact": (
                    feasible_noncontact_preserved
                ),
                "rejected_waypoint_count": len(rejected_cases),
                "rejected_waypoints": [case["name"] for case in rejected_cases],
                "registered_outbound_hold_return_completes": sequence_completed,
                "registered_outbound_hold_return_clean_noncontact": sequence_clean,
            },
            "plot": str(plot_path),
            "previous_step_result": str(previous_result_path),
            "scope_invariants": {
                "production_mpc_replaced": False,
                "controller_or_execution_gain_changed": False,
                "safety_threshold_changed": False,
                "task_changed": False,
                "contact_model_changed": False,
                "stage3_or_stage4_changed": False,
                "rl_or_value_changed": False,
                "historical_result_changed": False,
            },
            "limitations": [
                "bounded deterministic simulation validation only",
                "ideal 200 Hz controller measurements",
                "provisional Stage-5 cuff/interface and CR12 simulation actuator semantics",
                "non-contact geometry check is kinematic and adds no contact dynamics",
                "no hardware or clinical safety claim",
            ],
        }
    )
    result_path = output_dir / "human_waypoint_scheduler_validation.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "stages/stage5_personalized_motion_learning/results/engineering_validation/"
            "human_waypoint_scheduler_v1_attempt_01"
        ),
    )
    parser.add_argument(
        "--previous-result", type=Path, default=DEFAULT_PREVIOUS_RESULT
    )
    args = parser.parse_args()
    result = run_validation(args.output_dir, args.previous_result)
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "criteria_observed": result["criteria_observed"],
                "remaining_structural_limitation": result[
                    "remaining_structural_limitation"
                ],
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
