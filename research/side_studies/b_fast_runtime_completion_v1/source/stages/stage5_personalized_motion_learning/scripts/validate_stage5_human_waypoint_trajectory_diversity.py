#!/usr/bin/env python3
"""Validate continuous-r trajectory diversity on the Human-waypoint MPC baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_mpc import (
    _MPCRegisteredTaskController,
    _new_planner,
)
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _jsonable,
    _run_case,
)


SCHEMA = "stage5_human_waypoint_trajectory_diversity_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_human_waypoint_trajectory_diversity_v1.json"
)
DEFAULT_BASELINE_RESULT = Path(
    "stages/stage5_personalized_motion_learning/results/engineering_validation/"
    "human_waypoint_mpc_v1_attempt_03/human_waypoint_mpc_validation.json"
)
PATH_PROGRESS_GRID = np.linspace(0.0, 1.0, 101)


def _phase_progress(q_rad: np.ndarray, phase: str) -> np.ndarray:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    goal = np.asarray(spec.outbound_goal_target_rad, dtype=float)
    span = goal - start
    if phase == TaskPhase.OUTBOUND.value:
        return (q_rad - start) / span
    if phase == TaskPhase.RETURN.value:
        return (goal - q_rad) / span
    raise ValueError("phase progress is defined only for OUTBOUND and RETURN")


def _resample_phase_path(
    trace: list[dict[str, Any]],
    phase: str,
    state_key: str,
    q_slice: slice | None = None,
) -> dict[str, Any]:
    rows = [row for row in trace if row["phase"] == phase]
    if not rows:
        raise ValueError(f"trace has no {phase} samples")
    raw = np.asarray([row[state_key] for row in rows], dtype=float)
    q_rad = raw if q_slice is None else raw[:, q_slice]
    progress = _phase_progress(q_rad, phase)
    average_progress = np.clip(np.mean(progress, axis=1), 0.0, 1.0)
    monotone_progress = np.maximum.accumulate(average_progress)
    unique_progress, unique_indices = np.unique(monotone_progress, return_index=True)
    unique_q = q_rad[unique_indices]
    unique_separation = (progress[:, 0] - progress[:, 1])[unique_indices]
    if unique_progress[0] > 0.0:
        unique_progress = np.insert(unique_progress, 0, 0.0)
        unique_q = np.vstack([q_rad[0], unique_q])
        unique_separation = np.insert(unique_separation, 0, progress[0, 0] - progress[0, 1])
    if unique_progress[-1] < 1.0:
        unique_progress = np.append(unique_progress, 1.0)
        unique_q = np.vstack([unique_q, q_rad[-1]])
        unique_separation = np.append(
            unique_separation, progress[-1, 0] - progress[-1, 1]
        )
    q_resampled = np.column_stack(
        [
            np.interp(PATH_PROGRESS_GRID, unique_progress, unique_q[:, joint])
            for joint in range(2)
        ]
    )
    separation_resampled = np.interp(
        PATH_PROGRESS_GRID, unique_progress, unique_separation
    )
    return {
        "q_rad": q_resampled,
        "normalized_progress_separation": separation_resampled,
    }


def _path_distance(first: dict[str, Any], second: dict[str, Any]) -> dict[str, float]:
    delta_rad = np.asarray(first["q_rad"]) - np.asarray(second["q_rad"])
    delta_deg = np.degrees(delta_rad)
    euclidean_deg = np.linalg.norm(delta_deg, axis=1)
    span = np.abs(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad)
        - np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    normalized = np.linalg.norm(delta_rad / span, axis=1)
    return {
        "rms_distance_deg": float(np.sqrt(np.mean(euclidean_deg**2))),
        "maximum_distance_deg": float(np.max(euclidean_deg)),
        "rms_normalized_distance": float(np.sqrt(np.mean(normalized**2))),
        "maximum_normalized_distance": float(np.max(normalized)),
    }


def _waypoint_persistence(
    controller: dict[str, Any], coordination_preference_r: float
) -> dict[str, Any]:
    values: list[float] = []
    per_phase: dict[str, list[float]] = {}
    for phase in controller["phases"]:
        if phase["phase"] == TaskPhase.HOLD.value:
            continue
        waypoints = np.asarray(phase["selected_waypoints_rad"], dtype=float)
        if waypoints.size == 0:
            per_phase[phase["phase"]] = []
            continue
        progress = _phase_progress(waypoints, phase["phase"])
        separation = progress[:, 0] - progress[:, 1]
        per_phase[phase["phase"]] = separation.tolist()
        phase_r = (
            coordination_preference_r
            if phase["phase"] == TaskPhase.OUTBOUND.value
            else -coordination_preference_r
        )
        if abs(phase_r) <= 1.0e-12:
            phase_matching = np.abs(separation) <= 0.05
        else:
            phase_matching = np.sign(phase_r) * separation > 1.0e-9
        values.extend(phase_matching.tolist())
    matching = np.asarray(values, dtype=bool)
    return {
        "waypoint_progress_separation": per_phase,
        "persistent_matching_waypoint_count": int(np.count_nonzero(matching)),
        "evaluated_waypoint_count": int(len(matching)),
        "matching_fraction": float(np.mean(matching)) if len(matching) else 0.0,
    }


def _sequence_metrics(case: dict[str, Any], coordination_preference_r: float) -> dict[str, Any]:
    trace = case["metrics"]["trace"]
    available_phases = {
        row["phase"]
        for row in trace
        if row["phase"] in (TaskPhase.OUTBOUND.value, TaskPhase.RETURN.value)
    }
    realized_paths = {
        phase: _resample_phase_path(
            trace, phase, "estimated_state_rad_rad_s", slice(0, 2)
        )
        for phase in sorted(available_phases)
    }
    scheduled_paths = {
        phase: _resample_phase_path(trace, phase, "requested_q_rad")
        for phase in sorted(available_phases)
    }
    sample_indices = [25, 50, 75]
    progress_separation = {
        phase: {
            "scheduled_at_25_50_75_percent": [
                float(scheduled_paths[phase]["normalized_progress_separation"][index])
                for index in sample_indices
            ],
            "realized_at_25_50_75_percent": [
                float(realized_paths[phase]["normalized_progress_separation"][index])
                for index in sample_indices
            ],
            "scheduled_peak_abs": float(
                np.max(
                    np.abs(
                        scheduled_paths[phase]["normalized_progress_separation"]
                    )
                )
            ),
            "realized_peak_abs": float(
                np.max(
                    np.abs(realized_paths[phase]["normalized_progress_separation"])
                )
            ),
        }
        for phase in sorted(available_phases)
    }
    return {
        "realized_paths": realized_paths,
        "scheduled_paths": scheduled_paths,
        "progress_separation": progress_separation,
        "waypoint_persistence": _waypoint_persistence(
            case["controller"], coordination_preference_r
        ),
    }


def _run_profile(profile: dict[str, Any]) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    name = str(profile["name"])
    coordination_preference_r = float(profile["r"])
    scheduler, mpc = _new_planner(f"trajectory_diversity_{name}_planning", start)
    task_controller = _MPCRegisteredTaskController(
        mpc,
        scheduler,
        coordination_preference_r=coordination_preference_r,
    )
    metrics = _run_case(
        name=f"trajectory_diversity_{name}",
        kind="human_waypoint_mpc_trajectory_diversity",
        start_q_rad=start,
        duration_s=2.0 * spec.phase_timeout_s + spec.hold_duration_s + CONTROL_DT_S,
        stateful_schedule=task_controller,
        completion_check=lambda: task_controller.completed_time_s is not None,
        schedule_context_hook=task_controller.bind_execution_context,
    )
    record = task_controller.record()
    complete = bool(
        task_controller.completed_time_s is not None
        and metrics["termination_reason"] is None
        and metrics["final_within_existing_task_tolerance"]
    )
    constraint_compliant = bool(
        metrics["human_motion_authority"]["violation_count"] == 0
        and metrics["execution_safety"]["brake_cycle_count"] == 0
        and metrics["execution_safety"]["force_gate_event_count"] == 0
        and metrics["execution_safety"]["torque_clip_event_count"] == 0
        and metrics["execution_safety"]["shank_bed_contact_sample_count"] == 0
        and metrics["execution_safety"]["minimum_truth_shank_clearance_mm"] >= 0.0
    )
    case = {
        "name": name,
        "coordination_preference_r": coordination_preference_r,
        "completed": complete,
        "constraint_compliant": constraint_compliant,
        "completion_time_s": task_controller.completed_time_s,
        "controller": record,
        "metrics": metrics,
    }
    case["trajectory_metrics"] = _sequence_metrics(
        case, coordination_preference_r
    )
    return case


def _pairwise_distances(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for first_index, first in enumerate(cases):
        for second in cases[first_index + 1 :]:
            phases = {}
            shared_phases = sorted(
                set(first["trajectory_metrics"]["realized_paths"])
                & set(second["trajectory_metrics"]["realized_paths"])
            )
            for phase in shared_phases:
                phases[phase] = _path_distance(
                    first["trajectory_metrics"]["realized_paths"][phase],
                    second["trajectory_metrics"]["realized_paths"][phase],
                )
            records.append(
                {
                    "first": first["name"],
                    "second": second["name"],
                    "phases": phases,
                    "mean_phase_rms_distance_deg": (
                        None
                        if not phases
                        else float(
                            np.mean(
                                [
                                    phases[phase]["rms_distance_deg"]
                                    for phase in phases
                                ]
                            )
                        )
                    ),
                }
            )
    return records


def _baseline_distances(
    cases: list[dict[str, Any]], baseline_payload: dict[str, Any]
) -> list[dict[str, Any]]:
    trace = baseline_payload["complete_task"]["metrics"]["trace"]
    baseline_paths = {
        phase: _resample_phase_path(
            trace, phase, "estimated_state_rad_rad_s", slice(0, 2)
        )
        for phase in (TaskPhase.OUTBOUND.value, TaskPhase.RETURN.value)
    }
    results = []
    for case in cases:
        shared_phases = sorted(
            set(case["trajectory_metrics"]["realized_paths"])
            & set(baseline_paths)
        )
        phase_records = {
            phase: _path_distance(
                case["trajectory_metrics"]["realized_paths"][phase],
                baseline_paths[phase],
            )
            for phase in shared_phases
        }
        results.append(
            {
                "name": case["name"],
                "coordination_preference_r": case["coordination_preference_r"],
                "phases": phase_records,
                "mean_phase_rms_distance_deg": (
                    None
                    if not phase_records
                    else float(
                        np.mean(
                            [
                                phase_records[phase]["rms_distance_deg"]
                                for phase in phase_records
                            ]
                        )
                    )
                ),
            }
        )
    return results


def _plot(cases: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    colors = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(cases)))
    for color, case in zip(colors, cases):
        label = f"{case['name']} (r={case['coordination_preference_r']:+.3f})"
        trace = case["metrics"]["trace"]
        q_deg = np.degrees(
            np.asarray([row["estimated_state_rad_rad_s"][:2] for row in trace])
        )
        axes[0].plot(q_deg[:, 0], q_deg[:, 1], color=color, label=label)
        for phase in case["controller"]["phases"]:
            if phase["phase"] == TaskPhase.HOLD.value:
                continue
            waypoints = np.degrees(
                np.asarray(phase["selected_waypoints_rad"], dtype=float)
            )
            if waypoints.size == 0:
                continue
            axes[0].scatter(
                waypoints[:, 0], waypoints[:, 1], color=color, s=17, alpha=0.8
            )
        outbound_path = case["trajectory_metrics"]["realized_paths"].get(
            TaskPhase.OUTBOUND.value
        )
        if outbound_path is not None:
            axes[1].plot(
                PATH_PROGRESS_GRID,
                outbound_path["normalized_progress_separation"],
                color=color,
                label=label,
            )
    axes[0].set_xlabel("q1 [deg]")
    axes[0].set_ylabel("q2 [deg]")
    axes[0].set_title("Realized complete q1-q2 paths and MPC waypoints")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_xlabel("normalized OUTBOUND progress")
    axes[1].set_ylabel("hip progress - knee progress")
    axes[1].set_title("Persistent coordination separation")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(
    output_dir: Path,
    config_path: Path,
    baseline_result_path: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_human_waypoint_trajectory_diversity_v1":
        raise ValueError("unexpected trajectory-diversity config schema")
    baseline = json.loads(baseline_result_path.read_text(encoding="utf-8"))
    profiles = list(config["preregistered_profiles"])
    configured_gain = float(config["coordination_variable"]["coordination_gain"])
    _, contract_probe = _new_planner(
        "trajectory_diversity_contract_probe",
        np.asarray(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad,
            dtype=float,
        ),
    )
    if not np.isclose(
        configured_gain,
        contract_probe.config.coordination_gain,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise ValueError("trajectory-diversity config and MPC coordination gains differ")
    cases = [_run_profile(profile) for profile in profiles]
    completed_cases = [case for case in cases if case["completed"]]
    pairwise = _pairwise_distances(completed_cases)
    versus_baseline = _baseline_distances(cases, baseline)

    by_name = {case["name"]: case for case in cases}
    anchor_pair = next(
        (
            item
            for item in pairwise
            if {item["first"], item["second"]}
            == {"knee_anchor", "hip_anchor"}
        ),
        None,
    )
    anchor_rms_deg = (
        0.0
        if anchor_pair is None
        else float(anchor_pair["mean_phase_rms_distance_deg"])
    )
    anchor_shared_phases = sorted(
        set(by_name["hip_anchor"]["trajectory_metrics"]["progress_separation"])
        & set(by_name["knee_anchor"]["trajectory_metrics"]["progress_separation"])
    )
    anchor_peak_span = (
        0.0
        if not anchor_shared_phases
        else float(
            max(
                by_name["hip_anchor"]["trajectory_metrics"][
                    "progress_separation"
                ][phase]["realized_peak_abs"]
                + by_name["knee_anchor"]["trajectory_metrics"][
                    "progress_separation"
                ][phase]["realized_peak_abs"]
                for phase in anchor_shared_phases
            )
        )
    )
    completion_times = np.asarray(
        [case["completion_time_s"] for case in cases if case["completion_time_s"]]
    )
    pacing_ratio = float(np.max(completion_times) / np.min(completion_times))
    criteria = config["diversity_criteria"]
    complete_count = sum(case["completed"] for case in cases)
    all_compliant = all(case["constraint_compliant"] for case in cases)
    persistent_counts = {
        case["name"]: case["trajectory_metrics"]["waypoint_persistence"][
            "persistent_matching_waypoint_count"
        ]
        for case in cases
        if abs(case["coordination_preference_r"]) > 1.0e-12
    }
    criteria_observed = {
        "complete_profile_count": complete_count,
        "required_complete_profile_count": criteria[
            "required_complete_profile_count"
        ],
        "all_profiles_constraint_compliant": all_compliant,
        "anchor_pair_mean_phase_rms_distance_deg": anchor_rms_deg,
        "minimum_anchor_pair_rms_path_distance_deg": criteria[
            "minimum_anchor_pair_rms_path_distance_deg"
        ],
        "anchor_pair_peak_progress_separation_span": anchor_peak_span,
        "minimum_anchor_pair_peak_progress_separation_span": criteria[
            "minimum_anchor_pair_peak_progress_separation_span"
        ],
        "persistent_matching_waypoint_counts": persistent_counts,
        "minimum_persistent_biased_waypoint_count": criteria[
            "minimum_persistent_biased_waypoint_count"
        ],
        "completion_time_ratio": pacing_ratio,
        "maximum_completion_time_ratio": criteria[
            "maximum_completion_time_ratio"
        ],
    }
    criteria_met = bool(
        complete_count >= criteria["required_complete_profile_count"]
        and all_compliant
        and anchor_rms_deg
        >= criteria["minimum_anchor_pair_rms_path_distance_deg"]
        and anchor_peak_span
        >= criteria["minimum_anchor_pair_peak_progress_separation_span"]
        and all(
            count >= criteria["minimum_persistent_biased_waypoint_count"]
            for count in persistent_counts.values()
        )
        and pacing_ratio <= criteria["maximum_completion_time_ratio"]
    )
    any_diversity = bool(anchor_rms_deg > 0.0 and complete_count >= 2)
    if criteria_met:
        decision = (
            "TD-A — HWMPC CAN GENERATE MEANINGFULLY DIVERSE COMPLETE TRAJECTORIES"
        )
        limitation = None
    elif any_diversity:
        decision = (
            "TD-B — SOME DIVERSITY EXISTS, BUT PATHS COLLAPSE / COVERAGE IS TOO SMALL"
        )
        limitation = "one or more preregistered completeness, diversity, persistence, compliance, or pacing criteria were not met"
    else:
        decision = (
            "TD-C — CURRENT HWMPC CANNOT PRODUCE USEFUL TRAJECTORY DIVERSITY"
        )
        limitation = "the continuous coordination input did not yield distinct complete paths"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "human_waypoint_trajectory_diversity.png"
    _plot(cases, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_engineering_validation",
            "decision": decision,
            "remaining_limitation": limitation,
            "config": config,
            "profiles": cases,
            "pairwise_realized_path_distances": pairwise,
            "distances_versus_hwmpc_baseline": versus_baseline,
            "criteria_observed": criteria_observed,
            "plot": str(plot_path),
            "inputs": {
                "config": str(config_path),
                "hwmpc_baseline": str(baseline_result_path),
            },
            "scope_invariants": {
                "task_or_timing_changed": False,
                "scheduler_or_execution_changed": False,
                "safety_or_motion_limits_changed": False,
                "contact_model_changed": False,
                "force_objective_active": False,
                "learning_or_value_active": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
            },
            "limitations": [
                "bounded simulation engineering evidence only",
                "r is a prescribed continuous coordination input, not learned personalization",
                "force metrics are observational and not duration-normalized objectives",
                "provisional Stage-5 cuff/interface and CR12 actuator semantics",
                "no hardware, clinical, or formal safety claim",
            ],
        }
    )
    result_path = output_dir / "human_waypoint_trajectory_diversity.json"
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
            "engineering_validation/human_waypoint_trajectory_diversity_v1_attempt_01"
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--baseline-result", type=Path, default=DEFAULT_BASELINE_RESULT
    )
    args = parser.parse_args()
    result = run_validation(args.output_dir, args.config, args.baseline_result)
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
