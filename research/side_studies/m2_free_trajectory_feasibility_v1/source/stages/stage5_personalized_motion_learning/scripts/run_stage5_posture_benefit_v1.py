#!/usr/bin/env python3
"""Run the final Stage-5 matched posture-region benefit experiment."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.posture_benefit import (
    PostureRegion,
    PostureRegionIntervention,
    PostureRegionSpec,
    audit_posture_regions,
    outbound_normalized_progress,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase
from traction_mpc_stage5.trust_gamma_matched import (
    build_control_human_model,
    extract_supported_model,
    load_trust_gamma_contract,
)


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_posture_benefit_v1.json"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "posture_benefit_v1_formal_attempt_01"
SMOKE_OUTPUT = STAGE5_ROOT / "results" / "posture_benefit_v1_mechanical_smoke"


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_posture_benefit_v1":
        raise ValueError("unexpected posture-benefit config schema")
    if config.get("status") != "PREREGISTERED_USER_MANUAL_FORMAL_RUN_REQUIRED":
        raise ValueError("posture-benefit experiment status changed")
    condition = config["fixed_condition"]
    if (
        float(condition["gamma"]) != 0.5
        or condition["interface"] != "fixed_nominal"
        or condition["human_model_updates_enabled"]
        or condition["trust_to_gamma_authority"]
        or condition["learned_value_or_actor_control"]
        or condition["prefix_backend"] != "native"
    ):
        raise ValueError("posture-benefit isolation condition changed")
    design = config["formal_design"]
    if (
        len(design["starts"]) != 2
        or len(design["regions"]) != 3
        or len(design["cem_seeds"]) != 3
        or int(design["rollout_count"]) != 18
    ):
        raise ValueError("formal posture-benefit design must remain 2 x 3 x 3")
    if [row["name"] for row in design["regions"]] != [
        "hip_biased",
        "balanced",
        "knee_biased",
    ]:
        raise ValueError("posture-region order changed")
    return config


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def _truth_human():
    return replace(
        STAGE5_HUMAN,
        passive_damping_nms_rad=tuple(
            1.2 * np.asarray(STAGE5_HUMAN.passive_damping_nms_rad, dtype=float)
        ),
    )


def _fixed_pacing(_: dict[str, Any]) -> dict[str, float]:
    return {"gamma": 0.5, "gamma_target": 0.5, "gamma_rate_per_s": 0.0}


def _no_human_update(_: dict[str, Any]) -> dict[str, Any]:
    return {"apply_update": False, "reason": "frozen_posture_benefit_condition"}


def _strict_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _strict_jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _time_mean(values: np.ndarray, time_s: np.ndarray) -> float:
    duration = float(time_s[-1] - time_s[0])
    if duration <= 0.0:
        return float("nan")
    return float(np.trapezoid(values, time_s) / duration)


def _branch_metrics(
    run_dir: Path,
    summary: dict[str, Any],
    intervention: PostureRegionIntervention,
) -> dict[str, Any]:
    branch = summary["posture_region_branch"]
    if not branch["snapshot_captured"] or branch["activation_time_s"] is None:
        raise RuntimeError("posture-region start was not reached")
    with np.load(run_dir / "trace.npz") as loaded:
        trace = {name: loaded[name] for name in loaded.files}
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    activation = float(branch["activation_time_s"])
    release = (
        float(branch["release_time_s"])
        if branch["release_time_s"] is not None
        else float(branch["maximum_release_deadline_s"])
    )
    active = np.flatnonzero(
        (time >= activation - 1.0e-12) & (time <= release + 1.0e-12)
    )
    future = np.flatnonzero(time >= activation - 1.0e-12)
    if len(active) < 2 or len(future) < 2:
        raise RuntimeError("posture-region interval is absent from saved trace")
    progress = np.asarray(
        [
            outbound_normalized_progress(q, PROVISIONAL_LOW_MODERATE_GOAL_TASK)
            for q in state[active, :2]
        ]
    )
    center = np.asarray(branch["center_progress"], dtype=float)
    half_width = np.asarray(branch["half_width_progress"], dtype=float)
    normalized_error = np.max(np.abs(progress - center) / half_width, axis=1)
    closest_local = int(np.argmin(normalized_error))
    closest_index = int(active[closest_local])
    inside = np.all(np.abs(progress - center) <= half_width + 1.0e-12, axis=1)
    first_entry_index = None if not np.any(inside) else int(active[np.flatnonzero(inside)[0]])

    future_time = time[future]
    force = np.linalg.norm(
        np.asarray(trace["deployable_measured_cuff_force_world_n"])[future], axis=1
    )
    moment = np.linalg.norm(
        np.asarray(trace["deployable_measured_cuff_moment_world_nm"])[future], axis=1
    )
    generalized = np.linalg.norm(
        np.asarray(trace["deployable_measured_generalized_input_nm"])[future], axis=1
    )
    support = np.linalg.norm(
        np.asarray(trace["support_generalized_action_nm"])[future], axis=1
    )
    motion = np.linalg.norm(
        np.asarray(trace["motion_increment_generalized_action_nm"])[future], axis=1
    )
    duration = float(future_time[-1] - future_time[0])
    gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
    model_versions = np.asarray(trace["control_human_model_version"], dtype=str)
    safety = {
        "mpc_failure_count": int(summary["mpc_failure_count"]),
        "force_gate_event_count": int(summary["force_gate_event_count"]),
        "brake_event_count": int(summary["brake_event_count"]),
        "structural_event_count": int(summary["structural_event_count"]),
        "maximum_safety_filter_intervention_coordinate_norm": float(
            summary["maximum_safety_filter_intervention_coordinate_norm"]
        ),
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
    }
    motion_envelope = summary["motion_envelope"]
    safety_valid = bool(
        safety["mpc_failure_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["brake_event_count"] == 0
        and safety["structural_event_count"] == 0
        and safety["maximum_safety_filter_intervention_coordinate_norm"] <= 1.0e-12
        and not safety["mujoco_warning_counts"]
        and motion_envelope["estimated_velocity_satisfied"]
        and motion_envelope["deployable_realized_acceleration_satisfied"]
    )
    fixed_valid = bool(
        np.all(gamma == 0.5)
        and np.all(model_versions == branch["deployable_start"]["control_human_model_version"])
        and summary["human_model_control_transition"]["transition_count"] == 0
    )
    return {
        "start_name": branch["start_name"],
        "cem_seed": int(summary["goal_mpc_formulation"].get("random_seed", -1)),
        "region": branch["region"],
        "decision_state_sha256": branch["decision_state_sha256"],
        "starting_deployable_state": branch["deployable_start"],
        "target_center_progress": branch["center_progress"],
        "target_half_width_progress": branch["half_width_progress"],
        "activation_time_s": activation,
        "release_time_s": release,
        "waypoint_duration_s": release - activation,
        "maximum_waypoint_duration_s": float(branch["maximum_waypoint_duration_s"]),
        "waypoint_solve_count": int(branch["waypoint_solve_count"]),
        "all_waypoint_prefixes_feasible": bool(
            branch["all_waypoint_prefixes_feasible"]
        ),
        "region_reached": bool(np.any(inside)),
        "first_region_entry_time_s": (
            None if first_entry_index is None else float(time[first_entry_index])
        ),
        "closest_region_time_s": float(time[closest_index]),
        "closest_progress": progress[closest_local].tolist(),
        "closest_q_deg": np.degrees(state[closest_index, :2]).tolist(),
        "closest_normalized_region_error": float(normalized_error[closest_local]),
        "complete_q1_q2_path": {
            "artifact": str(run_dir / "trace.npz"),
            "fields": ["time_s", "estimated_state_rad_rad_s"],
            "sample_count": int(len(time)),
        },
        "remaining_task_duration_s": duration,
        "future_cumulative_measured_cuff_force_n_s": float(
            np.trapezoid(force, future_time)
        ),
        "future_mean_measured_cuff_force_n": _time_mean(force, future_time),
        "future_peak_measured_cuff_force_n": float(np.max(force)),
        "future_peak_measured_cuff_moment_nm": float(np.max(moment)),
        "future_generalized_human_effort_integral_nm_s": float(
            np.trapezoid(generalized, future_time)
        ),
        "future_mean_generalized_human_effort_norm_nm": _time_mean(
            generalized, future_time
        ),
        "future_mean_support_norm_nm": _time_mean(support, future_time),
        "future_mean_motion_increment_norm_nm": _time_mean(motion, future_time),
        "task_status": summary["task_status"],
        "task_complete": bool(summary["true_episode_complete"]),
        "phase_transitions": summary["phase_transitions"],
        "fixed_condition_valid": fixed_valid,
        "safety_valid": safety_valid,
        "safety_events": safety,
        "motion_envelope": motion_envelope,
        "truth_used_for_controller_or_branch_decision": False,
    }


def _group_analysis(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    starts = [row["name"] for row in config["formal_design"]["starts"]]
    seeds = config["formal_design"]["cem_seeds"]
    timing_limit = float(
        config["timing_contract"]["maximum_within_group_remaining_duration_range_s"]
    )
    separation_limit = float(
        config["feasibility_gates"]["minimum_actual_extreme_separation_normalized"]
    )
    joint_separation_limit_deg = np.asarray(
        config["feasibility_gates"]["minimum_actual_extreme_joint_separation_deg"],
        dtype=float,
    )
    for start in starts:
        for seed in seeds:
            matched = [
                row
                for row in rows
                if row["start_name"] == start and row["cem_seed"] == seed
            ]
            by_region = {row["region"]: row for row in matched}
            durations = np.asarray(
                [row["remaining_task_duration_s"] for row in matched], dtype=float
            )
            extreme_separation = (
                float(
                    np.linalg.norm(
                        np.asarray(by_region["hip_biased"]["closest_progress"])
                        - np.asarray(by_region["knee_biased"]["closest_progress"])
                    )
                )
                if len(by_region) == 3
                else float("nan")
            )
            extreme_joint_separation_deg = (
                np.abs(
                    np.asarray(by_region["hip_biased"]["closest_q_deg"])
                    - np.asarray(by_region["knee_biased"]["closest_q_deg"])
                )
                if len(by_region) == 3
                else np.full(2, np.nan)
            )
            integrals = {
                name: float(row["future_cumulative_measured_cuff_force_n_s"])
                for name, row in by_region.items()
            }
            biased = [name for name in ("hip_biased", "knee_biased") if name in integrals]
            best_biased = min(biased, key=integrals.get) if biased else None
            reduction = (
                (integrals["balanced"] - integrals[best_biased])
                / integrals["balanced"]
                if best_biased is not None and "balanced" in integrals
                else float("nan")
            )
            groups.append(
                {
                    "start_name": start,
                    "cem_seed": int(seed),
                    "branch_count": len(matched),
                    "same_start_digest": len(
                        {row["decision_state_sha256"] for row in matched}
                    )
                    == 1,
                    "all_regions_reached": bool(
                        matched and all(row["region_reached"] for row in matched)
                    ),
                    "actual_extreme_separation_normalized": extreme_separation,
                    "actual_extreme_joint_separation_deg": (
                        extreme_joint_separation_deg.tolist()
                    ),
                    "path_separation_passed": bool(
                        extreme_separation >= separation_limit
                        and np.all(
                            extreme_joint_separation_deg
                            >= joint_separation_limit_deg
                        )
                    ),
                    "remaining_duration_range_s": float(np.ptp(durations))
                    if len(durations)
                    else float("nan"),
                    "timing_matched": bool(
                        len(durations) == 3
                        and np.ptp(durations) <= timing_limit + 1.0e-12
                    ),
                    "force_integrals_n_s": integrals,
                    "best_biased_region": best_biased,
                    "best_biased_reduction_vs_balanced_fraction": reduction,
                    "all_complete": bool(
                        matched and all(row["task_complete"] for row in matched)
                    ),
                    "all_fixed_condition_valid": bool(
                        matched and all(row["fixed_condition_valid"] for row in matched)
                    ),
                    "all_safety_valid": bool(
                        matched and all(row["safety_valid"] for row in matched)
                    ),
                    "all_prefixes_feasible": bool(
                        matched
                        and all(row["all_waypoint_prefixes_feasible"] for row in matched)
                    ),
                }
            )

    benefit = config["benefit_gates"]
    required_repeat = int(
        benefit["minimum_repetitions_with_same_biased_winner_per_start"]
    )
    required_reduction_count = int(
        benefit["minimum_repetitions_meeting_reduction_per_start"]
    )
    minimum_reduction = float(benefit["minimum_relative_integral_reduction_vs_balanced"])
    repeatability: dict[str, Any] = {}
    for start in starts:
        selected = [row for row in groups if row["start_name"] == start]
        winners = [row["best_biased_region"] for row in selected]
        counts = {name: winners.count(name) for name in sorted(set(winners))}
        repeated_winner = (
            max(counts, key=counts.get) if counts and max(counts.values()) >= required_repeat else None
        )
        qualifying = sum(
            row["best_biased_region"] == repeated_winner
            and row["best_biased_reduction_vs_balanced_fraction"] >= minimum_reduction
            for row in selected
        )
        repeatability[start] = {
            "biased_winner_counts": counts,
            "repeated_biased_winner": repeated_winner,
            "qualifying_reduction_count": qualifying,
            "passed": bool(
                repeated_winner is not None and qualifying >= required_reduction_count
            ),
        }

    expected_rows = int(config["formal_design"]["rollout_count"])
    expected_groups = len(starts) * len(seeds)
    identity_valid = bool(
        len(rows) == expected_rows
        and len(groups) == expected_groups
        and all(group["branch_count"] == 3 for group in groups)
        and all(group["same_start_digest"] for group in groups)
        and all(group["all_fixed_condition_valid"] for group in groups)
        and all(
            not row["truth_used_for_controller_or_branch_decision"] for row in rows
        )
    )
    path_valid = bool(
        groups
        and all(group["all_regions_reached"] for group in groups)
        and all(group["path_separation_passed"] for group in groups)
        and all(group["all_prefixes_feasible"] for group in groups)
        and all(group["all_safety_valid"] for group in groups)
    )
    execution_valid = bool(groups and all(group["all_complete"] for group in groups))
    timing_valid = bool(groups and all(group["timing_matched"] for group in groups))
    benefit_valid = bool(
        repeatability and all(item["passed"] for item in repeatability.values())
    )
    if not identity_valid or not execution_valid:
        decision, label = "PB-D", "TIMING / SNAPSHOT / EXECUTION CONTRACT INVALID"
    elif not path_valid:
        decision, label = (
            "PB-C",
            "CURRENT TASK CANNOT PRODUCE SUFFICIENTLY SEPARATED FEASIBLE PATHS",
        )
    elif not timing_valid:
        decision, label = "PB-D", "TIMING / SNAPSHOT / EXECUTION CONTRACT INVALID"
    elif benefit_valid:
        decision, label = "PB-A", "CLEAR POSTURE-DEPENDENT COST BENEFIT CONFIRMED"
    else:
        decision, label = (
            "PB-B",
            "PATHS SEPARATED, BUT FORCE BENEFIT STILL TOO SMALL / INCONSISTENT",
        )
    return {
        "groups": groups,
        "benefit_repeatability": repeatability,
        "identity_gate_passed": identity_valid,
        "path_feasibility_gate_passed": path_valid,
        "execution_gate_passed": execution_valid,
        "timing_gate_passed": timing_valid,
        "force_integral_benefit_gate_passed": benefit_valid,
        "decision": decision,
        "decision_label": label,
    }


def run(output_dir: Path, *, mechanical_smoke: bool) -> dict[str, Any]:
    config = _load_config()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_PATH, output_dir / "config_used.json")

    design = config["formal_design"]
    condition = config["fixed_condition"]
    gates = config["feasibility_gates"]
    static_audit = audit_posture_regions(
        task=PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        starts=design["starts"],
        regions=design["regions"],
        maximum_waypoint_duration_s=float(design["maximum_waypoint_duration_s"]),
        effective_velocity_deg_s=condition[
            "effective_planning_joint_velocity_ceiling_deg_s"
        ],
        minimum_adjacent_center_distance=float(
            gates["minimum_adjacent_center_distance_normalized"]
        ),
        minimum_extreme_center_distance=float(
            gates["minimum_extreme_center_distance_normalized"]
        ),
    )
    (output_dir / "feasibility_audit.json").write_text(
        json.dumps(_strict_jsonable(static_audit), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not static_audit["passed"]:
        raise RuntimeError("frozen posture regions failed static feasibility audit")

    trust_contract = load_trust_gamma_contract()
    frozen = extract_supported_model(trust_contract)
    if frozen.model_id != condition["human_model_version"] or not np.array_equal(
        np.asarray(frozen.theta), np.asarray(condition["human_model_theta"])
    ):
        raise ValueError("configured Human model differs from supported artifact")
    control_model = build_control_human_model(_geometry(), frozen)
    truth_human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(truth_human, interface_parameters=parameters)

    seeds = design["cem_seeds"][:1] if mechanical_smoke else design["cem_seeds"]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for start in design["starts"]:
        for seed in seeds:
            for region in design["regions"]:
                intervention = PostureRegionIntervention(
                    PostureRegionSpec(
                        start_name=str(start["name"]),
                        start_phase=TaskPhase(str(start["phase"])),
                        start_minimum_progress=float(start["minimum_progress"]),
                        region=PostureRegion(str(region["name"])),
                        center_progress=tuple(float(x) for x in region["center_progress"]),
                        half_width_progress=tuple(
                            float(x) for x in region["half_width_progress"]
                        ),
                        maximum_waypoint_duration_s=float(
                            design["maximum_waypoint_duration_s"]
                        ),
                    )
                )
                run_dir = (
                    output_dir
                    / str(start["name"])
                    / f"seed_{seed}"
                    / str(region["name"])
                )
                try:
                    summary = run_goal_mpc_smoke(
                        run_dir,
                        maximum_duration_s=(
                            3.5
                            if mechanical_smoke and start["phase"] == "OUTBOUND"
                            else 9.75
                            if mechanical_smoke
                            else float(condition["maximum_duration_s"])
                        ),
                        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
                        plant_case_name=(
                            f"posture_benefit__{start['name']}__{seed}__{region['name']}"
                        ),
                        record_selected_horizon_diagnostics=False,
                        use_loaded_local_hold=True,
                        use_bumpless_return_handoff=True,
                        initialize_loaded_equilibrium_with_plant_truth=True,
                        interface_uncertainty_spec=None,
                        planning_physical_force_ceiling_n=float(
                            condition["planning_physical_force_ceiling_n"]
                        ),
                        planning_joint_velocity_ceiling_rad_s=tuple(
                            np.radians(
                                condition[
                                    "base_planning_joint_velocity_ceiling_deg_s"
                                ]
                            )
                        ),
                        mpc_config=HumanMPCConfig(random_seed=int(seed)),
                        plant_factory=plant_factory,
                        progress_pacing_callback=_fixed_pacing,
                        control_human_model_callback=_no_human_update,
                        control_human_model_callback_is_no_update_freeze=True,
                        initial_control_human_model=control_model,
                        initial_control_human_model_version=frozen.model_id,
                        prefix_backend=str(condition["prefix_backend"]),
                        matched_branch_intervention=intervention,
                        minimum_phase_duration_s=config["timing_contract"][
                            "minimum_phase_duration_s"
                        ],
                    )
                    row = _branch_metrics(run_dir, summary, intervention)
                    row["cem_seed"] = int(seed)
                    rows.append(row)
                except Exception as error:
                    failures.append(
                        {
                            "start_name": str(start["name"]),
                            "cem_seed": int(seed),
                            "region": str(region["name"]),
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "partial_output_directory": str(run_dir.relative_to(output_dir)),
                        }
                    )

    if mechanical_smoke:
        smoke_separation: list[dict[str, Any]] = []
        for start in design["starts"]:
            selected = {
                row["region"]: row
                for row in rows
                if row["start_name"] == start["name"]
            }
            if len(selected) != 3:
                continue
            hip = selected["hip_biased"]
            knee = selected["knee_biased"]
            normalized = float(
                np.linalg.norm(
                    np.asarray(hip["closest_progress"])
                    - np.asarray(knee["closest_progress"])
                )
            )
            joint_deg = np.abs(
                np.asarray(hip["closest_q_deg"])
                - np.asarray(knee["closest_q_deg"])
            )
            smoke_separation.append(
                {
                    "start_name": start["name"],
                    "actual_extreme_separation_normalized": normalized,
                    "actual_extreme_joint_separation_deg": joint_deg.tolist(),
                    "passed": bool(
                        normalized
                        >= float(
                            gates[
                                "minimum_actual_extreme_separation_normalized"
                            ]
                        )
                        and np.all(
                            joint_deg
                            >= np.asarray(
                                gates[
                                    "minimum_actual_extreme_joint_separation_deg"
                                ],
                                dtype=float,
                            )
                        )
                    ),
                }
            )
        analysis = {
            "formal_decision_emitted": False,
            "row_count": len(rows),
            "execution_failure_count": len(failures),
            "all_smoke_regions_reached": bool(
                rows and len(rows) == 6 and all(row["region_reached"] for row in rows)
            ),
            "all_smoke_prefixes_feasible": bool(
                rows and all(row["all_waypoint_prefixes_feasible"] for row in rows)
            ),
            "all_smoke_safety_valid": bool(
                rows and all(row["safety_valid"] for row in rows)
            ),
            "smoke_path_separation": smoke_separation,
            "all_smoke_path_separation_gates_passed": bool(
                len(smoke_separation) == 2
                and all(item["passed"] for item in smoke_separation)
            ),
            "force_metrics_used_to_change_regions": False,
        }
    elif failures:
        analysis = {
            "decision": "PB-D",
            "decision_label": "TIMING / SNAPSHOT / EXECUTION CONTRACT INVALID",
            "reason": "one or more formal branch executions failed",
        }
    else:
        analysis = _group_analysis(rows, config)

    result = {
        "schema": "stage5_posture_benefit_v1_result",
        "evidence_category": (
            "mechanical_smoke_not_scientific_evidence"
            if mechanical_smoke
            else "formal_user_executed_preregistered_posture_benefit_study"
        ),
        "config": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "static_feasibility_audit": static_audit,
        "fixed_condition": condition,
        "supported_human_model_provenance": {
            "model_id": frozen.model_id,
            "theta": list(frozen.theta),
            "support_evidence_id": frozen.support_evidence_id,
            "source_artifact_sha256": frozen.source_artifact_sha256,
        },
        "rows": rows,
        "execution_failures": failures,
        "analysis": analysis,
        "formal_decision_emitted": not mechanical_smoke,
        "force_or_moment_used_to_select_or_change_regions": False,
        "value_model_trained": False,
        "value_or_rl_connected_to_control": False,
        "stage3_or_stage4_modified_by_this_study": False,
    }
    (output_dir / "posture_benefit_results.json").write_text(
        json.dumps(_strict_jsonable(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--mechanical-smoke", action="store_true")
    args = parser.parse_args()
    output = args.output_dir or (SMOKE_OUTPUT if args.mechanical_smoke else DEFAULT_OUTPUT)
    result = run(output.resolve(), mechanical_smoke=args.mechanical_smoke)
    print(json.dumps(_strict_jsonable(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
