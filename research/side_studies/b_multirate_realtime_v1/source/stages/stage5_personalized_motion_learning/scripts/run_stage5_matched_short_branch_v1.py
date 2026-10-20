#!/usr/bin/env python3
"""Run and analyze the preregistered Stage-5 matched short-branch study."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.matched_branch import (
    BranchCoordination,
    MatchedBranchIntervention,
    ShortBranchSpec,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.task import TaskPhase
from traction_mpc_stage5.trust_gamma_matched import (
    build_control_human_model,
    extract_supported_model,
    load_trust_gamma_contract,
)


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_matched_short_branch_v1.json"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "matched_short_branch_v1_formal_attempt_01"
SMOKE_OUTPUT = STAGE5_ROOT / "results" / "matched_short_branch_v1_mechanical_smoke"


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_matched_short_branch_v1":
        raise ValueError("unexpected matched-branch config schema")
    if payload.get("status") != "PREREGISTERED_USER_AUTHORIZED_MANUAL_FORMAL_RUN_REQUIRED":
        raise ValueError("matched-branch contract status changed")
    source = payload["source_personalization_policy"]
    if (
        float(source["model_update_alpha"]) != 0.25
        or float(source["maximum_per_scale_step"]) != 0.04
        or source["frozen_for_this_study"] is not True
    ):
        raise ValueError("supported personalization condition changed")
    condition = payload["fixed_condition"]
    if (
        condition["human_model_updates_enabled"]
        or condition["trust_to_gamma_authority"]
        or condition["learned_value_or_actor_control"]
        or float(condition["gamma"]) != 0.5
        or condition["interface"] != "fixed_nominal"
        or condition["prefix_backend"] != "native"
    ):
        raise ValueError("matched-branch isolation condition changed")
    units = payload["matched_units"]
    if units["branches"] != ["hip_leading", "balanced", "knee_leading"]:
        raise ValueError("matched branch ordering changed")
    if len(units["anchors"]) != 3 or len(units["cem_seeds"]) != 3:
        raise ValueError("formal study requires three anchors and three seeds")
    return payload


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
    return {"apply_update": False, "reason": "frozen_matched_branch_condition"}


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


def _branch_metrics(
    run_dir: Path, summary: dict[str, Any], intervention: MatchedBranchIntervention
) -> dict[str, Any]:
    branch = summary["matched_short_branch"]
    if not branch["snapshot_captured"] or branch["activation_time_s"] is None:
        raise RuntimeError("branch anchor was not reached")
    with np.load(run_dir / "trace.npz") as loaded:
        trace = {name: loaded[name] for name in loaded.files}
    time = np.asarray(trace["time_s"], dtype=float)
    activation = float(branch["activation_time_s"])
    future = np.flatnonzero(time >= activation - 1.0e-12)
    if not len(future):
        raise RuntimeError("branch activation is absent from the trace")
    short = np.flatnonzero(
        (time >= activation - 1.0e-12)
        & (time <= activation + intervention.spec.duration_s + 1.0e-12)
    )
    measured_force = np.linalg.norm(
        trace["deployable_measured_cuff_force_world_n"][future], axis=1
    )
    measured_moment = np.linalg.norm(
        trace["deployable_measured_cuff_moment_world_nm"][future], axis=1
    )
    future_time = time[future]
    duration = float(future_time[-1] - future_time[0])
    force_integral = (
        float(np.trapezoid(measured_force, future_time))
        if len(future_time) > 1
        else 0.0
    )
    q = np.asarray(trace["estimated_state_rad_rad_s"][:, :2], dtype=float)
    gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
    model_versions = np.asarray(trace["control_human_model_version"], dtype=str)
    expected_model = str(branch["deployable_start"]["control_human_model_version"])
    fixed_condition_valid = bool(
        np.allclose(gamma, 0.5, atol=0.0, rtol=0.0)
        and np.all(model_versions == expected_model)
        and summary["human_model_control_transition"]["transition_count"] == 0
    )
    motion = summary["motion_envelope"]
    safety_valid = bool(
        summary["mpc_failure_count"] == 0
        and summary["force_gate_event_count"] == 0
        and summary["brake_event_count"] == 0
        and summary["structural_event_count"] == 0
        and summary["maximum_safety_filter_intervention_coordinate_norm"]
        <= 1.0e-12
        and not summary["mujoco_warning_counts"]
        and motion["estimated_velocity_satisfied"]
        and motion["deployable_realized_acceleration_satisfied"]
    )
    return {
        "anchor_name": intervention.spec.anchor_name,
        "coordination": intervention.spec.coordination.value,
        "cem_seed": int(summary["goal_mpc_formulation"].get("random_seed", -1)),
        "decision_state_sha256": branch["decision_state_sha256"],
        "starting_deployable_state": branch["deployable_start"],
        "short_motion": {
            "time_s": time[short].tolist(),
            "estimated_q_rad": q[short].tolist(),
            "estimated_q_deg": np.degrees(q[short]).tolist(),
            "delta_q_deg": np.degrees(q[short[-1]] - q[short[0]]).tolist(),
            "registered_action_bias_nm": branch["registered_action_bias_nm"],
            "biased_solve_count": branch["biased_solve_count"],
            "all_biased_prefixes_feasible": branch[
                "all_biased_prefixes_feasible"
            ],
        },
        "complete_q1_q2_path": {
            "artifact": str((run_dir / "trace.npz").relative_to(run_dir.parent.parent.parent)),
            "fields": ["time_s", "estimated_state_rad_rad_s"],
            "sample_count": int(len(time)),
        },
        "remaining_task_duration_s": duration,
        "future_cumulative_measured_cuff_force_n_s": force_integral,
        "future_mean_measured_cuff_force_n": (
            force_integral / duration if duration > 0.0 else None
        ),
        "future_peak_measured_cuff_force_n": float(np.max(measured_force)),
        "future_peak_measured_cuff_moment_nm": float(np.max(measured_moment)),
        "motion_envelope": motion,
        "safety_events": {
            "mpc_failure_count": summary["mpc_failure_count"],
            "force_gate_event_count": summary["force_gate_event_count"],
            "brake_event_count": summary["brake_event_count"],
            "structural_event_count": summary["structural_event_count"],
            "safety_filter_status_counts": summary["safety_filter_status_counts"],
            "maximum_safety_filter_intervention_coordinate_norm": summary[
                "maximum_safety_filter_intervention_coordinate_norm"
            ],
            "mujoco_warning_counts": summary["mujoco_warning_counts"],
        },
        "task_status": summary["task_status"],
        "task_complete": bool(summary["true_episode_complete"]),
        "fixed_condition_valid": fixed_condition_valid,
        "safety_valid": safety_valid,
        "truth_used_for_controller_or_branch_decision": False,
    }


def _group_results(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    timing_limit = float(
        config["timing_contract"]["maximum_within_group_remaining_duration_range_s"]
    )
    separation = config["separation_gates"]
    groups: list[dict[str, Any]] = []
    for anchor in config["matched_units"]["anchors"]:
        for seed in config["matched_units"]["cem_seeds"]:
            matched = [
                row
                for row in rows
                if row["anchor_name"] == anchor["name"] and row["cem_seed"] == seed
            ]
            if not matched:
                continue
            digests = {row["decision_state_sha256"] for row in matched}
            durations = np.asarray(
                [row["remaining_task_duration_s"] for row in matched], dtype=float
            )
            integrals = np.asarray(
                [row["future_cumulative_measured_cuff_force_n_s"] for row in matched],
                dtype=float,
            )
            means = np.asarray(
                [row["future_mean_measured_cuff_force_n"] for row in matched],
                dtype=float,
            )
            best_index = int(np.argmin(integrals))
            groups.append(
                {
                    "anchor_name": anchor["name"],
                    "cem_seed": seed,
                    "branch_count": len(matched),
                    "same_start_digest": len(digests) == 1,
                    "decision_state_sha256": next(iter(digests)) if len(digests) == 1 else None,
                    "remaining_duration_range_s": float(np.ptp(durations)),
                    "timing_comparable": bool(np.ptp(durations) <= timing_limit + 1.0e-12),
                    "best_branch_by_force_integral": matched[best_index]["coordination"],
                    "best_worst_force_integral_difference_n_s": float(np.ptp(integrals)),
                    "best_worst_mean_force_relative_difference": float(
                        np.ptp(means) / np.max(means)
                    ),
                    "all_complete": all(row["task_complete"] for row in matched),
                    "all_fixed_condition_valid": all(
                        row["fixed_condition_valid"] for row in matched
                    ),
                    "all_safety_valid": all(row["safety_valid"] for row in matched),
                    "all_branch_prefixes_feasible": all(
                        row["short_motion"]["all_biased_prefixes_feasible"]
                        for row in matched
                    ),
                }
            )
    expected_groups = len(config["matched_units"]["anchors"]) * len(
        config["matched_units"]["cem_seeds"]
    )
    validity = bool(
        len(rows) == 27
        and len(groups) == expected_groups
        and all(group["branch_count"] == 3 for group in groups)
        and all(group["same_start_digest"] for group in groups)
        and all(group["all_complete"] for group in groups)
        and all(group["all_fixed_condition_valid"] for group in groups)
        and all(group["all_safety_valid"] for group in groups)
        and all(group["all_branch_prefixes_feasible"] for group in groups)
    )
    timing = bool(groups) and all(group["timing_comparable"] for group in groups)
    anchor_repeatability: dict[str, Any] = {}
    for anchor in config["matched_units"]["anchors"]:
        names = [
            group["best_branch_by_force_integral"]
            for group in groups
            if group["anchor_name"] == anchor["name"]
        ]
        counts = {name: names.count(name) for name in set(names)}
        anchor_repeatability[anchor["name"]] = {
            "best_branch_counts": counts,
            "repeatable": bool(
                counts
                and max(counts.values())
                >= int(separation["minimum_seed_groups_with_same_best_branch_per_anchor"])
            ),
        }
    separation_passed = bool(
        groups
        and all(
            group["best_worst_force_integral_difference_n_s"]
            >= float(separation["minimum_best_worst_future_force_difference_n_s"])
            and group["best_worst_mean_force_relative_difference"]
            >= float(
                separation[
                    "minimum_best_worst_time_normalized_mean_force_relative_difference"
                ]
            )
            for group in groups
        )
        and all(item["repeatable"] for item in anchor_repeatability.values())
    )
    if not validity:
        decision = "BR-C"
        label = "SNAPSHOT/BRANCH EXPERIMENT NOT SCIENTIFICALLY VALID"
    elif timing and separation_passed:
        decision = "BR-A"
        label = "PATH/COST SEPARATION CONFIRMED"
    else:
        decision = "BR-B"
        label = "DIFFERENCES MAINLY EXPLAINED BY TIME / TOO SMALL"
    return {
        "groups": groups,
        "anchor_repeatability": anchor_repeatability,
        "validity_gate_passed": validity,
        "timing_gate_passed": timing,
        "separation_gate_passed": separation_passed,
        "decision": decision,
        "decision_label": label,
    }


def run(output_dir: Path, *, mechanical_smoke: bool) -> dict[str, Any]:
    config = _load_config()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    trust_contract = load_trust_gamma_contract()
    frozen = extract_supported_model(trust_contract)
    expected = config["fixed_condition"]
    if frozen.model_id != expected["human_model_version"] or not np.array_equal(
        np.asarray(frozen.theta), np.asarray(expected["human_model_theta"])
    ):
        raise ValueError("configured fixed Human model differs from supported artifact")
    control_model = build_control_human_model(_geometry(), frozen)
    units = config["matched_units"]
    anchors = units["anchors"]
    seeds = units["cem_seeds"][:1] if mechanical_smoke else units["cem_seeds"]
    branches = units["branches"]
    rows: list[dict[str, Any]] = []
    execution_failures: list[dict[str, Any]] = []
    truth_human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(
            truth_human, interface_parameters=parameters
        )

    for anchor in anchors:
        for seed in seeds:
            for branch_name in branches:
                intervention = MatchedBranchIntervention(
                    ShortBranchSpec(
                        anchor_name=str(anchor["name"]),
                        phase=TaskPhase(str(anchor["phase"])),
                        minimum_progress=float(anchor["minimum_progress"]),
                        duration_s=float(units["short_bias_duration_s"]),
                        hip_bias_nm=float(units["hip_bias_magnitude_nm"]),
                        knee_bias_nm=float(units["knee_bias_magnitude_nm"]),
                        coordination=BranchCoordination(branch_name),
                    )
                )
                run_dir = output_dir / anchor["name"] / f"seed_{seed}" / branch_name
                try:
                    summary = run_goal_mpc_smoke(
                        run_dir,
                        maximum_duration_s=(
                            {
                                "early_outbound": 2.0,
                                "mid_outbound": 3.5,
                                "mid_return": 7.0,
                            }[str(anchor["name"])]
                            if mechanical_smoke
                            else float(expected["maximum_duration_s"])
                        ),
                        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
                        plant_case_name=(
                            "matched_short_branch__"
                            f"{anchor['name']}__{seed}__{branch_name}"
                        ),
                        record_selected_horizon_diagnostics=False,
                        use_loaded_local_hold=True,
                        use_bumpless_return_handoff=True,
                        initialize_loaded_equilibrium_with_plant_truth=True,
                        interface_uncertainty_spec=None,
                        planning_physical_force_ceiling_n=float(
                            expected["planning_physical_force_ceiling_n"]
                        ),
                        planning_joint_velocity_ceiling_rad_s=tuple(
                            np.radians(
                                expected[
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
                        prefix_backend=str(expected["prefix_backend"]),
                        matched_branch_intervention=intervention,
                    )
                    row = _branch_metrics(run_dir, summary, intervention)
                    row["cem_seed"] = int(seed)
                    rows.append(row)
                except Exception as error:
                    execution_failures.append(
                        {
                            "anchor_name": str(anchor["name"]),
                            "cem_seed": int(seed),
                            "coordination": str(branch_name),
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "partial_output_directory": str(
                                run_dir.relative_to(output_dir)
                            ),
                        }
                    )
    if mechanical_smoke:
        analysis = None
    elif execution_failures:
        analysis = {
            "groups": [],
            "validity_gate_passed": False,
            "timing_gate_passed": False,
            "separation_gate_passed": False,
            "decision": "BR-C",
            "decision_label": "SNAPSHOT/BRANCH EXPERIMENT NOT SCIENTIFICALLY VALID",
            "reason": "one or more preregistered branch executions failed",
        }
    else:
        analysis = _group_results(rows, config)
    result = {
        "schema": "stage5_matched_short_branch_v1_result",
        "evidence_category": (
            "mechanical_smoke_not_scientific_evidence"
            if mechanical_smoke
            else "formal_user_executed_preregistered_branch_study"
        ),
        "config": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "fixed_condition": expected,
        "supported_human_model_provenance": {
            "model_id": frozen.model_id,
            "theta": list(frozen.theta),
            "support_evidence_id": frozen.support_evidence_id,
            "source_artifact_sha256": frozen.source_artifact_sha256,
        },
        "rows": rows,
        "execution_failures": execution_failures,
        "analysis": analysis,
        "formal_decision_emitted": not mechanical_smoke,
        "value_network_trained": False,
        "value_or_rl_connected_to_control": False,
        "stage3_or_stage4_modified_by_this_study": False,
    }
    result_path = output_dir / "matched_short_branch_results.json"
    result_path.write_text(
        json.dumps(_strict_jsonable(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--mechanical-smoke", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir or (
        SMOKE_OUTPUT if args.mechanical_smoke else DEFAULT_OUTPUT
    )
    result = run(output_dir, mechanical_smoke=args.mechanical_smoke)
    print(json.dumps(_strict_jsonable(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
