#!/usr/bin/env python3
"""Bounded CR12 validation of the first Human-waypoint MPC prototype."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_mpc import HumanWaypointMPCPrototypeV1
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerSession,
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_scheduler import (
    _phase_entry_inside_tolerance,
    _target_tracking,
)
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _candidate,
    _jsonable,
    _prepare_runtime,
    _run_case,
)


SCHEMA = "stage5_human_waypoint_mpc_prototype_v1"
DEFAULT_DETERMINISTIC_RESULT = Path(
    "stages/stage5_personalized_motion_learning/results/engineering_validation/"
    "human_waypoint_contract_20ms_v2_attempt_06/"
    "human_waypoint_scheduler_validation.json"
)


class _MPCPhaseController:
    """Execute sequential MPC waypoints through the unchanged scheduler contract."""

    def __init__(
        self,
        *,
        mpc: HumanWaypointMPCPrototypeV1,
        scheduler: QuinticHumanWaypointSchedulerV1,
        phase: TaskPhase,
        phase_start_s: float,
        coordination_preference_r: float = 0.0,
    ) -> None:
        self.mpc = mpc
        self.scheduler = scheduler
        self.spec = scheduler.spec
        self.phase = phase
        self.phase_start_s = float(phase_start_s)
        self.coordination_preference_r = float(coordination_preference_r)
        self.goal_q_rad = np.asarray(
            self.spec.start_return_target_rad
            if phase is TaskPhase.RETURN
            else self.spec.outbound_goal_target_rad,
            dtype=float,
        )
        self.session: QuinticHumanWaypointSchedulerSession | None = None
        self.current_waypoint: HumanWaypointCandidate | None = None
        self.completed_time_s: float | None = None
        self.selected_waypoints_rad: list[np.ndarray] = []
        self.execution_context: dict[str, Any] | None = None
        self.mpc.reset_phase()

    def bind_execution_context(self, **context: Any) -> None:
        self.execution_context = dict(context)

    def _execution_screen(
        self,
        candidate: HumanWaypointCandidate,
        schedule: Any,
    ) -> dict[str, Any]:
        if self.execution_context is None:
            raise RuntimeError("candidate execution screen has no current runtime context")
        context = self.execution_context
        observation = context["observation"]
        timestamp_s = float(observation.sample_timestamp_s)
        sample_time_s = 0.0 if timestamp_s <= 1.0e-12 else min(
            schedule.reference_period_s, schedule.duration_s
        )
        sample = schedule.sample(sample_time_s)
        screened_candidate = HumanWaypointCandidate(
            label=f"{candidate.label}_first_action_screen",
            phase=candidate.phase,
            phase_goal_rad=candidate.phase_goal_rad,
            q_waypoint_rad=sample.q_rad,
            dq_waypoint_rad_s=sample.dq_rad_s,
        )
        contract = copy.deepcopy(context["contract"])
        try:
            mapped = contract.prepare(screened_candidate)
            command = contract.command(
                plant=context["plant"],
                measurement=context["measurement"],
                observation=observation,
                interface_state=context["interface_state"],
                mapped_waypoint=mapped,
            )
        except ValueError as error:
            return {
                "evaluated": True,
                "feasible": False,
                "rejection_reason": str(error),
            }
        filter_result = command.filter_result
        if not filter_result.feasible or filter_result.filtered_preview is None:
            return {
                "evaluated": True,
                "feasible": False,
                "rejection_reason": "existing Safety Filter requires BRAKE",
                "safety_filter_status": filter_result.status,
            }
        executable = filter_result.filtered_preview.command
        torque_clipped = bool(
            not np.allclose(
                executable.unclipped_joint_torque_nm,
                executable.joint_torque_command_nm,
                atol=1.0e-12,
                rtol=0.0,
            )
        )
        force_gate_clear = bool(executable.margin_to_force_gate_n > 0.0)
        feasible = bool(not torque_clipped and force_gate_clear)
        return {
            "evaluated": True,
            "feasible": feasible,
            "rejection_reason": (
                None
                if feasible
                else "existing force-gate or CR12 torque-limit screen rejected candidate"
            ),
            "safety_filter_status": filter_result.status,
            "force_gate_margin_n": executable.margin_to_force_gate_n,
            "torque_clipped": torque_clipped,
            "maximum_robot_torque_fraction": float(
                np.max(
                    np.abs(executable.joint_torque_command_nm)
                    / context["plant"].torque_limits_nm
                )
            ),
        }

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

    def _select(self, state: np.ndarray, phase_elapsed_s: float) -> None:
        decision = self.mpc.decide(
            current_deployable_state=state,
            phase=self.phase,
            phase_elapsed_s=phase_elapsed_s,
            coordination_preference_r=self.coordination_preference_r,
            execution_feasibility_checker=self._execution_screen,
        )
        schedule = decision.selected.schedule
        if schedule is None:
            raise RuntimeError("selected Human-waypoint MPC candidate has no schedule")
        self.current_waypoint = HumanWaypointCandidate(
            label=f"mpc_{self.phase.value.lower()}_{len(self.selected_waypoints_rad):02d}",
            phase=self.phase,
            phase_goal_rad=self.goal_q_rad,
            q_waypoint_rad=decision.selected.q_waypoint_rad,
            dq_waypoint_rad_s=decision.selected.dq_waypoint_rad_s,
        )
        self.selected_waypoints_rad.append(decision.selected.q_waypoint_rad.copy())
        self.session = QuinticHumanWaypointSchedulerSession(
            scheduler=self.scheduler,
            schedule=schedule,
            phase_start_elapsed_s=phase_elapsed_s,
        )

    def __call__(
        self, global_time_s: float, deployable_state: np.ndarray
    ) -> HumanWaypointCandidate:
        phase_elapsed_s = float(global_time_s - self.phase_start_s)
        if self.session is None:
            self._select(deployable_state, phase_elapsed_s)
        assert self.session is not None
        assert self.current_waypoint is not None

        schedule_done = bool(
            self.session.progress_s + 1.0e-12 >= self.session.schedule.duration_s
        )
        reached_waypoint = self._inside(
            deployable_state, self.current_waypoint.q_waypoint_rad
        )
        reached_phase_goal = self._inside(deployable_state, self.goal_q_rad)
        hold_complete = bool(
            self.phase is TaskPhase.HOLD
            and phase_elapsed_s + 1.0e-12 >= self.spec.hold_duration_s
        )
        if reached_phase_goal and (
            self.phase is not TaskPhase.HOLD or hold_complete
        ):
            if self.completed_time_s is None:
                self.completed_time_s = float(global_time_s)
        elif schedule_done and reached_waypoint and self.phase is not TaskPhase.HOLD:
            self._select(deployable_state, phase_elapsed_s)

        sample = self.session.advance(
            current_q_hat_rad=deployable_state[:2],
            current_dq_hat_rad_s=deployable_state[2:],
            phase_elapsed_s=phase_elapsed_s,
        )
        return _candidate(
            f"{self.current_waypoint.label}_scheduled_{global_time_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def record(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "phase_start_s": self.phase_start_s,
            "coordination_preference_r": self.coordination_preference_r,
            "completed_time_s": self.completed_time_s,
            "selected_waypoints_rad": [
                item.tolist() for item in self.selected_waypoints_rad
            ],
            "selected_waypoint_count": len(self.selected_waypoints_rad),
            "mpc": self.mpc.record(),
        }


class _MPCRegisteredTaskController:
    """Registered OUTBOUND/HOLD/RETURN phase driver around one MPC prototype."""

    def __init__(
        self,
        mpc: HumanWaypointMPCPrototypeV1,
        scheduler: QuinticHumanWaypointSchedulerV1,
        coordination_preference_r: float = 0.0,
    ) -> None:
        self.mpc = mpc
        self.scheduler = scheduler
        self.spec = scheduler.spec
        self.coordination_preference_r = float(coordination_preference_r)
        self.phase = TaskPhase.OUTBOUND
        self.phase_controller = _MPCPhaseController(
            mpc=mpc,
            scheduler=scheduler,
            phase=TaskPhase.OUTBOUND,
            phase_start_s=0.0,
            coordination_preference_r=self.coordination_preference_r,
        )
        self.phase_records: list[_MPCPhaseController] = [self.phase_controller]
        self.completed_time_s: float | None = None
        self.execution_context: dict[str, Any] | None = None

    def bind_execution_context(self, **context: Any) -> None:
        self.execution_context = dict(context)
        self.phase_controller.bind_execution_context(**context)

    def __call__(
        self, global_time_s: float, deployable_state: np.ndarray
    ) -> HumanWaypointCandidate:
        if self.phase_controller.completed_time_s is not None:
            if self.phase is TaskPhase.OUTBOUND:
                self.phase = TaskPhase.HOLD
                self.phase_controller = _MPCPhaseController(
                    mpc=self.mpc,
                    scheduler=self.scheduler,
                    phase=TaskPhase.HOLD,
                    phase_start_s=global_time_s,
                    coordination_preference_r=self.coordination_preference_r,
                )
                self.phase_records.append(self.phase_controller)
                assert self.execution_context is not None
                self.phase_controller.bind_execution_context(**self.execution_context)
            elif self.phase is TaskPhase.HOLD:
                self.phase = TaskPhase.RETURN
                self.phase_controller = _MPCPhaseController(
                    mpc=self.mpc,
                    scheduler=self.scheduler,
                    phase=TaskPhase.RETURN,
                    phase_start_s=global_time_s,
                    coordination_preference_r=self.coordination_preference_r,
                )
                self.phase_records.append(self.phase_controller)
                assert self.execution_context is not None
                self.phase_controller.bind_execution_context(**self.execution_context)
            elif self.phase is TaskPhase.RETURN:
                self.completed_time_s = float(global_time_s)
        return self.phase_controller(global_time_s, deployable_state)

    def record(self) -> dict[str, Any]:
        return {
            "completed_time_s": self.completed_time_s,
            "coordination_preference_r": self.coordination_preference_r,
            "phases": [item.record() for item in self.phase_records],
            "mpc": self.mpc.record(),
        }


def _new_planner(name: str, start_q_rad: np.ndarray):
    runtime = _prepare_runtime(name, start_q_rad)
    scheduler = QuinticHumanWaypointSchedulerV1(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        runtime["human_model"],
        reference_period_s=CONTROL_DT_S,
    )
    mpc = HumanWaypointMPCPrototypeV1(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, scheduler
    )
    return scheduler, mpc


def _run_phase(
    *,
    name: str,
    phase: TaskPhase,
    start_q_rad: np.ndarray,
) -> dict[str, Any]:
    scheduler, mpc = _new_planner(f"{name}_planning", start_q_rad)
    controller = _MPCPhaseController(
        mpc=mpc,
        scheduler=scheduler,
        phase=phase,
        phase_start_s=0.0,
    )
    duration_s = (
        scheduler.spec.hold_duration_s + CONTROL_DT_S
        if phase is TaskPhase.HOLD
        else scheduler.spec.phase_timeout_s + CONTROL_DT_S
    )
    metrics = _run_case(
        name=name,
        kind=f"human_waypoint_mpc_{phase.value.lower()}",
        start_q_rad=start_q_rad,
        duration_s=duration_s,
        stateful_schedule=controller,
        completion_check=lambda: controller.completed_time_s is not None,
        schedule_context_hook=controller.bind_execution_context,
    )
    return {
        "phase": phase.value,
        "completed_time_s": controller.completed_time_s,
        "controller": controller.record(),
        "target_tracking": _target_tracking(metrics, controller.goal_q_rad),
        "metrics": metrics,
    }


def _baseline_summary(payload: dict[str, Any]) -> dict[str, Any]:
    sequence = payload["sequence"]
    metrics = sequence["metrics"]
    return {
        "completed_time_s": sequence["completed_time_s"],
        "estimated_q_tracking_rmse_deg": metrics["estimated_q_tracking_rmse_deg"],
        "estimated_dq_tracking_rmse_deg_s": metrics[
            "estimated_dq_tracking_rmse_deg_s"
        ],
        "peak_abs_20ms_acceleration_deg_s2": metrics["human_motion_authority"][
            "peak_abs_20ms_acceleration_deg_s2"
        ],
        "peak_cuff_force_n": metrics["interaction"]["peak_cuff_force_n"],
        "integral_cuff_force_n_s": metrics["interaction"][
            "integral_cuff_force_n_s"
        ],
        "peak_cuff_moment_nm": metrics["interaction"]["peak_cuff_moment_nm"],
        "maximum_robot_torque_fraction": metrics["execution_safety"][
            "maximum_robot_torque_fraction"
        ],
        "minimum_truth_shank_clearance_mm": metrics["execution_safety"][
            "minimum_truth_shank_clearance_mm"
        ],
        "shank_bed_contact_sample_count": metrics["execution_safety"][
            "shank_bed_contact_sample_count"
        ],
    }


def _plot(full: dict[str, Any], path: Path) -> None:
    trace = full["metrics"]["trace"]
    elapsed = np.asarray([row["elapsed_s"] for row in trace])
    requested = np.degrees(np.asarray([row["requested_q_rad"] for row in trace]))
    realized = np.degrees(
        np.asarray([row["estimated_state_rad_rad_s"] for row in trace])[:, :2]
    )
    waypoints = []
    for phase in full["controller"]["phases"]:
        waypoints.extend(phase["selected_waypoints_rad"])
    waypoint_array = np.degrees(np.asarray(waypoints))

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    for joint in range(2):
        axes[0].plot(elapsed, requested[:, joint], "--", label=f"reference q{joint + 1}")
        axes[0].plot(elapsed, realized[:, joint], label=f"realized q{joint + 1}")
    axes[0].set_xlabel("time [s]")
    axes[0].set_ylabel("Human joint angle [deg]")
    axes[0].set_title("Human-waypoint MPC registered task")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=2)

    axes[1].plot(requested[:, 0], requested[:, 1], "--", label="scheduled reference")
    axes[1].plot(realized[:, 0], realized[:, 1], label="realized Human path")
    if len(waypoint_array):
        axes[1].scatter(
            waypoint_array[:, 0], waypoint_array[:, 1], marker="x", s=55,
            label="MPC-selected waypoints",
        )
    axes[1].set_xlabel("q1 [deg]")
    axes[1].set_ylabel("q2 [deg]")
    axes[1].set_title("q1-q2 path")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(
    output_dir: Path, deterministic_result_path: Path
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    baseline = json.loads(deterministic_result_path.read_text(encoding="utf-8"))

    phase_cases = [
        _run_phase(name="human_waypoint_mpc_outbound", phase=TaskPhase.OUTBOUND, start_q_rad=start),
        _run_phase(name="human_waypoint_mpc_hold", phase=TaskPhase.HOLD, start_q_rad=goal),
        _run_phase(name="human_waypoint_mpc_return", phase=TaskPhase.RETURN, start_q_rad=goal),
    ]

    scheduler, mpc = _new_planner("human_waypoint_mpc_full_planning", start)
    task_controller = _MPCRegisteredTaskController(mpc, scheduler)
    full_metrics = _run_case(
        name="human_waypoint_mpc_registered_task",
        kind="human_waypoint_mpc_complete_task",
        start_q_rad=start,
        duration_s=2.0 * spec.phase_timeout_s + spec.hold_duration_s + CONTROL_DT_S,
        stateful_schedule=task_controller,
        completion_check=lambda: task_controller.completed_time_s is not None,
        schedule_context_hook=task_controller.bind_execution_context,
    )
    full = {
        "completed_time_s": task_controller.completed_time_s,
        "controller": task_controller.record(),
        "phase_entry_inside_existing_tolerances": {
            "HOLD": _phase_entry_inside_tolerance(
                full_metrics["trace"], TaskPhase.HOLD, goal
            ),
            "RETURN": _phase_entry_inside_tolerance(
                full_metrics["trace"], TaskPhase.RETURN, goal
            ),
        },
        "target_tracking": _target_tracking(full_metrics, start),
        "metrics": full_metrics,
    }

    phase_completion = all(
        item["completed_time_s"] is not None
        and item["metrics"]["termination_reason"] is None
        for item in phase_cases
    )
    full_completion = bool(
        full["completed_time_s"] is not None
        and full_metrics["termination_reason"] is None
        and full["target_tracking"]["final_target_inside_existing_tolerances"]
        and all(full["phase_entry_inside_existing_tolerances"].values())
    )
    safety_preserved = bool(
        full_metrics["human_motion_authority"]["violation_count"] == 0
        and full_metrics["execution_safety"]["brake_cycle_count"] == 0
        and full_metrics["execution_safety"]["force_gate_event_count"] == 0
        and full_metrics["execution_safety"]["torque_clip_event_count"] == 0
    )
    mpc_record = full["controller"]["mpc"]
    waypoint_count = sum(
        item["selected_waypoint_count"] for item in full["controller"]["phases"]
    )
    continuous_path = bool(
        waypoint_count >= 3
        and all(
            item["mpc"]["uses_old_robot_interface_predictor"] is False
            for item in full["controller"]["phases"]
        )
    )
    if phase_completion and full_completion and safety_preserved and continuous_path:
        decision = (
            "HWMPC-A — HUMAN-WAYPOINT MPC COMPLETES THE TASK AND IS READY AS THE NEW BASELINE"
        )
        limitation = None
    elif phase_completion or full_completion:
        decision = (
            "HWMPC-B — MPC ABSTRACTION WORKS, BUT COST/CANDIDATE DESIGN NEEDS FURTHER WORK"
        )
        limitation = "one or more completion, path-quality, or existing-safety criteria remain unmet"
    else:
        decision = (
            "HWMPC-C — HUMAN-WAYPOINT MPC DOES NOT PROVIDE A VIABLE CONTROL BASELINE"
        )
        limitation = "the reference-space MPC could not complete the registered task"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "human_waypoint_mpc_path.png"
    _plot(full, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_engineering_prototype_validation",
            "decision": decision,
            "remaining_limitation": limitation,
            "prototype_contract": {
                "action": "next Human q/dq waypoint",
                "prediction": "scheduled reference endpoint only",
                "cost_terms": [
                    "task progress and goal error",
                    "waypoint smoothness and change",
                    "phase completion",
                ],
                "old_robot_interface_predictor_used": False,
                "old_instantaneous_pd_acceleration_proxy_used": False,
                "cumulative_force_objective_used": False,
                "learning_or_value_used": False,
                "downstream_execution_protections_unchanged": True,
            },
            "phase_cases": phase_cases,
            "complete_task": full,
            "deterministic_waypoint_baseline": _baseline_summary(baseline),
            "criteria_observed": {
                "outbound_hold_return_individually_complete": phase_completion,
                "complete_registered_task": full_completion,
                "existing_motion_and_execution_authority_preserved": safety_preserved,
                "continuous_multi_waypoint_path": continuous_path,
                "selected_waypoint_count": waypoint_count,
                "mpc_runtime_ms": mpc_record["runtime_ms"],
            },
            "plot": str(plot_path),
            "inputs": {
                "deterministic_waypoint_result": str(deterministic_result_path),
            },
            "scope_invariants": {
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
                "safety_thresholds_changed": False,
                "task_or_timing_changed": False,
                "contact_model_changed": False,
                "execution_gains_changed": False,
                "rl_or_value_changed": False,
            },
            "limitations": [
                "bounded simulation engineering evidence only",
                "ideal 200 Hz controller measurements",
                "provisional Stage-5 cuff/interface and CR12 actuator semantics",
                "first prototype uses one-step reference-endpoint prediction",
                "no hardware, clinical, or formal safety claim",
            ],
        }
    )
    result_path = output_dir / "human_waypoint_mpc_validation.json"
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
            "stages/stage5_personalized_motion_learning/results/"
            "engineering_validation/human_waypoint_mpc_v1_attempt_01"
        ),
    )
    parser.add_argument(
        "--deterministic-result",
        type=Path,
        default=DEFAULT_DETERMINISTIC_RESULT,
    )
    args = parser.parse_args()
    result = run_validation(args.output_dir, args.deterministic_result)
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "criteria_observed": result["criteria_observed"],
                "remaining_limitation": result["remaining_limitation"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
