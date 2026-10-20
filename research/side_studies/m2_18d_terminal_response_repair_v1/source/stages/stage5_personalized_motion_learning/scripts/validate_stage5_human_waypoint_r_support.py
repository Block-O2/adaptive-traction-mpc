#!/usr/bin/env python3
"""Bounded CR12 validation of a continuous Human-waypoint r support range."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.human_waypoint_scheduler import shank_table_clearance_m
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_shadow import _jsonable
from validate_stage5_human_waypoint_trajectory_diversity import (
    PATH_PROGRESS_GRID,
    _path_distance,
    _run_profile,
)


SCHEMA = "stage5_human_waypoint_r_support_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_human_waypoint_r_support_v1.json"
)


def _geometry_scan(config: dict[str, Any]) -> dict[str, Any]:
    scan = config["geometry_scan"]
    step = float(scan["r_step"])
    r_values = np.arange(
        float(scan["r_min"]),
        float(scan["r_max"]) + 0.5 * step,
        step,
    )
    s_values = np.linspace(0.0, 1.0, int(scan["path_sample_count"]))
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    span = (
        np.asarray(spec.outbound_goal_target_rad, dtype=float) - start
    )
    gain = float(config["trajectory_family"]["coordination_gain"])
    minimum_clearance_m = []
    for r_value in r_values:
        offset = gain * float(r_value) * np.sin(np.pi * s_values)
        progress = np.column_stack((s_values + offset, s_values - offset))
        q_rad = start + progress * span
        minimum_clearance_m.append(
            float(np.min(shank_table_clearance_m(q_rad)))
        )
    minimum_clearance_m = np.asarray(minimum_clearance_m, dtype=float)
    feasible = minimum_clearance_m >= 0.0
    zero_index = int(np.argmin(np.abs(r_values)))
    if not feasible[zero_index]:
        raise RuntimeError("the balanced trajectory is not geometry-feasible")
    lower_index = zero_index
    upper_index = zero_index
    while lower_index > 0 and feasible[lower_index - 1]:
        lower_index -= 1
    while upper_index + 1 < len(feasible) and feasible[upper_index + 1]:
        upper_index += 1
    return {
        "r_values": r_values,
        "minimum_clearance_m": minimum_clearance_m,
        "feasible": feasible,
        "component_containing_balanced": {
            "lower_r": float(r_values[lower_index]),
            "upper_r": float(r_values[upper_index]),
            "lower_minimum_clearance_mm": float(
                1000.0 * minimum_clearance_m[lower_index]
            ),
            "upper_minimum_clearance_mm": float(
                1000.0 * minimum_clearance_m[upper_index]
            ),
        },
        "sample_count": int(len(r_values)),
        "path_sample_count": int(len(s_values)),
        "r_step": step,
    }


def _case_passes(case: dict[str, Any], acceptance: dict[str, Any]) -> bool:
    metrics = case["metrics"]
    safety = metrics["execution_safety"]
    return bool(
        case["completed"]
        and metrics["human_motion_authority"]["violation_count"]
        <= acceptance["maximum_human_motion_violation_count"]
        and safety["shank_bed_contact_sample_count"]
        <= acceptance["maximum_contact_sample_count"]
        and safety["minimum_truth_shank_clearance_mm"] >= 0.0
        and safety["brake_cycle_count"]
        <= acceptance["maximum_brake_cycle_count"]
        and safety["force_gate_event_count"]
        <= acceptance["maximum_force_gate_event_count"]
        and safety["torque_clip_event_count"]
        <= acceptance["maximum_torque_clip_event_count"]
    )


def _widest_passing_segment(
    cases: list[dict[str, Any]], geometry_lower_r: float, geometry_upper_r: float
) -> list[dict[str, Any]]:
    ordered = sorted(cases, key=lambda item: item["coordination_preference_r"])
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for case in ordered:
        r_value = float(case["coordination_preference_r"])
        inside_geometry = geometry_lower_r <= r_value <= geometry_upper_r
        if inside_geometry and case["support_contract_passed"]:
            current.append(case)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    if not segments:
        return []
    return max(
        segments,
        key=lambda segment: (
            segment[-1]["coordination_preference_r"]
            - segment[0]["coordination_preference_r"],
            len(segment),
        ),
    )


def _boundary_diversity(segment: list[dict[str, Any]]) -> dict[str, Any]:
    if len(segment) < 2:
        return {
            "mean_phase_rms_path_distance_deg": 0.0,
            "progress_separation_span": 0.0,
            "phases": {},
        }
    lower = segment[0]
    upper = segment[-1]
    shared_phases = sorted(
        set(lower["trajectory_metrics"]["realized_paths"])
        & set(upper["trajectory_metrics"]["realized_paths"])
    )
    phase_distances = {
        phase: _path_distance(
            lower["trajectory_metrics"]["realized_paths"][phase],
            upper["trajectory_metrics"]["realized_paths"][phase],
        )
        for phase in shared_phases
    }
    mean_distance = float(
        np.mean(
            [item["rms_distance_deg"] for item in phase_distances.values()]
        )
    )
    separation_span = float(
        max(
            np.max(
                lower["trajectory_metrics"]["realized_paths"][phase][
                    "normalized_progress_separation"
                ]
            )
            - np.min(
                upper["trajectory_metrics"]["realized_paths"][phase][
                    "normalized_progress_separation"
                ]
            )
            for phase in shared_phases
        )
    )
    return {
        "lower_profile": lower["name"],
        "upper_profile": upper["name"],
        "mean_phase_rms_path_distance_deg": mean_distance,
        "progress_separation_span": separation_span,
        "phases": phase_distances,
    }


def _plot(
    cases: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    geometry: dict[str, Any],
    path: Path,
) -> None:
    accepted_names = {case["name"] for case in accepted}
    figure, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, max(1, len(accepted))))
    for color, case in zip(colors, accepted):
        label = f"r={case['coordination_preference_r']:+.3f}"
        outbound = case["trajectory_metrics"]["realized_paths"][
            TaskPhase.OUTBOUND.value
        ]
        q_deg = np.degrees(np.asarray(outbound["q_rad"], dtype=float))
        axes[0].plot(q_deg[:, 0], q_deg[:, 1], color=color, label=label)
        axes[1].plot(
            PATH_PROGRESS_GRID,
            outbound["normalized_progress_separation"],
            color=color,
            label=label,
        )
    axes[0].set(title="Accepted realized OUTBOUND paths", xlabel="q1 [deg]", ylabel="q2 [deg]")
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set(
        title="Accepted coordination separation",
        xlabel="normalized OUTBOUND progress",
        ylabel="hip progress - knee progress",
    )
    for axis in axes[:2]:
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=7, ncol=2)

    r_values = np.asarray(geometry["r_values"], dtype=float)
    clearance_mm = 1000.0 * np.asarray(
        geometry["minimum_clearance_m"], dtype=float
    )
    axes[2].plot(r_values, clearance_mm, color="black", label="reference geometry")
    for case in cases:
        r_value = float(case["coordination_preference_r"])
        truth_clearance = float(
            case["metrics"]["execution_safety"][
                "minimum_truth_shank_clearance_mm"
            ]
        )
        accepted_case = case["name"] in accepted_names
        axes[2].scatter(
            [r_value],
            [truth_clearance],
            color="tab:green" if accepted_case else "tab:red",
            marker="o" if accepted_case else "x",
            zorder=3,
        )
    axes[2].axhline(0.0, color="tab:red", linewidth=0.8)
    axes[2].set(
        title="Geometry scan and realized audit",
        xlabel="coordination r",
        ylabel="minimum shank-table clearance [mm]",
    )
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(output_dir: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_human_waypoint_r_support_v1":
        raise ValueError("unexpected r-support config schema")
    geometry = _geometry_scan(config)
    component = geometry["component_containing_balanced"]
    cases = []
    acceptance = config["support_acceptance"]
    for index, r_value in enumerate(config["dynamic_boundary_audit_r"]):
        case = _run_profile(
            {"name": f"r_audit_{index:02d}_{float(r_value):+.3f}", "r": r_value}
        )
        case["support_contract_passed"] = _case_passes(case, acceptance)
        cases.append(case)
    segment = _widest_passing_segment(
        cases,
        float(component["lower_r"]),
        float(component["upper_r"]),
    )
    diversity = _boundary_diversity(segment)
    enough_points = len(segment) >= int(
        acceptance["minimum_representative_point_count"]
    )
    useful_diversity = bool(
        diversity["mean_phase_rms_path_distance_deg"]
        >= acceptance["minimum_boundary_pair_rms_path_distance_deg"]
        and diversity["progress_separation_span"]
        >= acceptance["minimum_boundary_progress_separation_span"]
    )
    if segment and enough_points and useful_diversity:
        decision = "RS-A — CONTINUOUS r SUPPORT RANGE VALIDATED WITH USEFUL PATH DIVERSITY"
        limitation = None
    elif segment and enough_points:
        decision = "RS-B — FEASIBLE RANGE EXISTS BUT DIVERSITY IS TOO SMALL"
        limitation = "the widest passing interval did not meet the frozen path-diversity criteria"
    else:
        decision = "RS-C — NO USEFUL CONTINUOUS r RANGE SATISFIES THE CURRENT CONTRACT"
        limitation = "no sufficiently sampled contiguous interval passed the complete execution contract"

    support_interval = None
    if segment:
        support_interval = {
            "lower_r": float(segment[0]["coordination_preference_r"]),
            "upper_r": float(segment[-1]["coordination_preference_r"]),
            "representative_r": [
                float(case["coordination_preference_r"]) for case in segment
            ],
            "representative_point_count": len(segment),
            "all_representatives_passed": all(
                case["support_contract_passed"] for case in segment
            ),
            "finite_dynamic_validation_not_formal_continuum_guarantee": True,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "human_waypoint_r_support.png"
    _plot(cases, segment, geometry, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_engineering_validation",
            "decision": decision,
            "remaining_limitation": limitation,
            "config": config,
            "geometry_scan": geometry,
            "dynamic_audit_profiles": cases,
            "validated_support_interval": support_interval,
            "boundary_diversity": diversity,
            "plot": str(plot_path),
            "scope_invariants": {
                "hwmpc_or_scheduler_changed": False,
                "cr12_execution_changed": False,
                "task_timing_or_safety_limit_changed": False,
                "geometry_or_contact_model_changed": False,
                "force_used_for_support_selection": False,
                "personalization_learning_or_value_active": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
            },
        }
    )
    result_path = output_dir / "human_waypoint_r_support.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "geometry_component": component,
                "validated_support_interval": support_interval,
                "boundary_diversity": diversity,
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.output_dir, arguments.config)


if __name__ == "__main__":
    main()
