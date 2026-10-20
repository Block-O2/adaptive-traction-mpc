#!/usr/bin/env python3
"""Run three preregistered paired replications of the frozen theta_1 model."""

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
from traction_mpc_stage5.human_model_replication import (
    FROZEN_THETA_0,
    FROZEN_THETA_1,
    FrozenSuccessorArm,
    FrozenSuccessorReplicationAuthority,
    FrozenSuccessorReplicationSpec,
    aggregate_replication_units,
)
from traction_mpc_stage5.human_model_update import fixed_one_step_pacing_status
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


CONFIG_PATH = (
    STAGE5_ROOT
    / "configs"
    / "stage5_human_model_frozen_successor_replication_v1.json"
)


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_human_model_frozen_successor_replication_v1":
        raise ValueError("unexpected frozen-successor replication schema")
    if payload.get("status") != "PREREGISTERED_BEFORE_NEW_OUTCOMES":
        raise ValueError("replication must remain preregistered")
    pair = payload["model_pair"]
    if tuple(pair["theta_0"]) != FROZEN_THETA_0:
        raise ValueError("theta_0 changed")
    if not np.allclose(pair["theta_1"], FROZEN_THETA_1, atol=0.0, rtol=0.0):
        raise ValueError("theta_1 changed")
    if payload["replications"]["fixed_cem_seeds"] != [20260825, 20260826, 20260827]:
        raise ValueError("preregistered seed units changed")
    if payload["controller"]["gamma"] != 0.5:
        raise ValueError("replication gamma must remain 0.5")
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


def _control_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "task_duration_s": summary["task_duration_s"],
        "phase_transitions": summary["phase_transitions"],
        "estimated_terminal_error_deg": summary["estimated_terminal_error_deg"],
        "estimated_terminal_dq_deg_s": summary["estimated_terminal_dq_deg_s"],
        "hold": {
            "longest_continuous_goal_set_interval_s": summary[
                "loaded_local_hold"
            ]["longest_continuous_goal_set_interval_s"],
            "return_entry_observed": summary["loaded_local_hold"][
                "return_entry_observed"
            ],
        },
        "peak_physical_cuff_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_cuff_force_n_s": summary[
            "cumulative_physical_cuff_force_n_s"
        ],
        "peak_physical_cuff_moment_nm": summary[
            "peak_physical_cuff_moment_nm"
        ],
        "peak_abs_estimated_joint_velocity_deg_s": summary[
            "peak_abs_estimated_joint_velocity_deg_s"
        ],
        "peak_abs_evaluation_only_joint_velocity_deg_s": summary[
            "peak_abs_evaluation_only_joint_velocity_deg_s"
        ],
        "peak_abs_deployable_acceleration_deg_s2": summary[
            "peak_abs_estimated_joint_acceleration_deg_s2"
        ],
        "peak_abs_evaluation_only_acceleration_deg_s2": summary[
            "peak_abs_evaluation_only_joint_acceleration_deg_s2"
        ],
        "motion_envelope": summary["motion_envelope"],
        "mpc_status_counts": summary["mpc_status_counts"],
        "mpc_failure_count": summary["mpc_failure_count"],
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "maximum_safety_filter_intervention_coordinate_norm": summary[
            "maximum_safety_filter_intervention_coordinate_norm"
        ],
        "brake_event_count": summary["brake_event_count"],
        "force_gate_event_count": summary["force_gate_event_count"],
        "structural_event_count": summary["structural_event_count"],
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
        "mpc_runtime_ms": summary["mpc_runtime_ms"],
        "path_freedom": {
            "maximum_normalized_q1_q2_progress_difference": summary[
                "maximum_normalized_q1_q2_progress_difference"
            ],
            "interpretation": summary["path_freedom_interpretation"],
        },
    }


def _run_arm(
    output_dir: Path,
    replication_id: str,
    seed: int,
    arm: FrozenSuccessorArm,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    transition_config = config["transition"]
    authority = FrozenSuccessorReplicationAuthority(
        _geometry(),
        arm,
        replication_id=replication_id,
        cem_seed=seed,
        spec=FrozenSuccessorReplicationSpec(
            trigger_time_s=float(transition_config["trigger_time_s"]),
            post_transition_embargo_s=float(
                transition_config["post_transition_embargo_s"]
            ),
        ),
    )
    truth_human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(
            truth_human, interface_parameters=parameters
        )

    controller = config["controller"]
    arm_dir = output_dir / replication_id / arm.value
    summary = run_goal_mpc_smoke(
        arm_dir,
        maximum_duration_s=float(controller["maximum_duration_s"]),
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"frozen_successor_replication__{replication_id}__{arm.value}",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            controller["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(controller["base_planning_joint_velocity_ceiling_deg_s"])
        ),
        mpc_config=HumanMPCConfig(random_seed=seed),
        plant_factory=plant_factory,
        progress_pacing_callback=fixed_one_step_pacing_status,
        control_human_model_callback=authority.observe,
    )
    with np.load(arm_dir / "trace.npz") as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
    if not np.allclose(gamma, 0.5, atol=0.0, rtol=0.0):
        raise RuntimeError("replication gamma changed")
    if arm is FrozenSuccessorArm.PREDECESSOR and authority.application_count:
        raise RuntimeError("predecessor arm changed control model")
    if authority.application_count > 1:
        raise RuntimeError("frozen successor applied more than once")
    record = {
        "arm": arm.value,
        "replication_id": replication_id,
        "cem_seed": seed,
        "human_identification_active": False,
        "theta_1_refit": False,
        "application_count": authority.application_count,
        "transition_time_s": authority.transition_time_s,
        "control_transition": summary["human_model_control_transition"],
        "prediction_evidence": authority.prediction_evidence(),
        "gamma_minimum": float(np.min(gamma)),
        "gamma_maximum": float(np.max(gamma)),
        "control": _control_metrics(summary),
        "artifacts": {
            "summary": str((arm_dir / "summary.json").relative_to(output_dir)),
            "trace": str((arm_dir / "trace.npz").relative_to(output_dir)),
        },
    }
    return record, trace


def _pretransition_pair_audit(
    predecessor: dict[str, np.ndarray],
    successor: dict[str, np.ndarray],
    trigger_time_s: float,
) -> dict[str, Any]:
    predecessor_indices = np.flatnonzero(
        predecessor["time_s"] <= trigger_time_s + 1.0e-12
    )
    successor_indices = np.flatnonzero(
        successor["time_s"] <= trigger_time_s + 1.0e-12
    )
    keys = (
        "time_s",
        "estimated_state_rad_rad_s",
        "evaluation_human_q_rad",
        "evaluation_human_dq_rad_s",
        "executed_generalized_action_nm",
        "physical_cuff_force_world_n",
        "physical_cuff_moment_world_nm",
    )
    comparisons = {}
    for key in keys:
        left = predecessor[key][predecessor_indices]
        right = successor[key][successor_indices]
        comparisons[key] = {
            "exactly_equal": bool(np.array_equal(left, right)),
            "maximum_abs_difference": (
                0.0
                if np.array_equal(left, right)
                else float(np.max(np.abs(left - right)))
            ),
        }
    return {
        "sample_count": int(len(predecessor_indices)),
        "same_seed_within_pair": True,
        "all_pretransition_quantities_exactly_equal": all(
            item["exactly_equal"] for item in comparisons.values()
        ),
        "comparisons": comparisons,
    }


def _closed_loop_degraded(predecessor: dict[str, Any], successor: dict[str, Any]) -> bool:
    a = predecessor["control"]
    b = successor["control"]
    return bool(
        (a["task_status"] == "COMPLETE" and b["task_status"] != "COMPLETE")
        or b["mpc_failure_count"] > a["mpc_failure_count"]
        or b["force_gate_event_count"] > a["force_gate_event_count"]
        or b["brake_event_count"] > a["brake_event_count"]
        or b["maximum_safety_filter_intervention_coordinate_norm"]
        > a["maximum_safety_filter_intervention_coordinate_norm"] + 1.0e-12
        or (
            a["motion_envelope"]["deployable_realized_acceleration_satisfied"]
            and not b["motion_envelope"][
                "deployable_realized_acceleration_satisfied"
            ]
        )
        or (
            a["motion_envelope"]["evaluation_only_acceleration_satisfied"]
            and not b["motion_envelope"]["evaluation_only_acceleration_satisfied"]
        )
        or bool(b["mujoco_warning_counts"])
    )


def _decision(
    aggregate: dict[str, Any],
    successor_units: list[dict[str, Any]],
    any_degradation: bool,
) -> dict[str, str]:
    formal_outcomes = [
        item["prediction_evidence"]["classification"]["outcome"]
        for item in successor_units
    ]
    moving_repeated = all(
        all(
            item["prediction_evidence"]["phase_summary"].get(phase, {}).get(
                "mean_paired_difference_nms2", 0.0
            )
            < 0.0
            for phase in ("OUTBOUND", "RETURN")
        )
        for item in successor_units
    )
    if (
        aggregate["favorable_rollout_count"] == len(successor_units)
        and "negative" not in formal_outcomes
        and moving_repeated
        and not any_degradation
    ):
        return {
            "code": "RPL-A",
            "label": "FROZEN SUCCESSOR REPLICATED",
            "reason": "all independent rollout means and both moving phases repeat the favorable direction without a matched regression",
        }
    if aggregate["favorable_rollout_count"] >= 2 and not any_degradation:
        return {
            "code": "RPL-B",
            "label": "DIRECTION FAVORABLE BUT STILL INSUFFICIENT",
            "reason": "most rollout units favor theta_1, but replication direction or phase/formal evidence remains insufficient",
        }
    return {
        "code": "RPL-C",
        "label": "SUCCESSOR NOT REPRODUCIBLE",
        "reason": "predictive direction is not repeated across independent units or a matched closed-loop regression occurred",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "human_model_frozen_successor_replication_v1_attempt_01"
        ),
    )
    arguments = parser.parse_args()
    output_dir = arguments.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite replication output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    seeds = list(config["replications"]["fixed_cem_seeds"])
    pairs = []
    successor_units = []
    degradation_flags = []
    for index, seed in enumerate(seeds, start=1):
        replication_id = f"replication_{index:02d}_seed_{seed}"
        predecessor, predecessor_trace = _run_arm(
            output_dir,
            replication_id,
            seed,
            FrozenSuccessorArm.PREDECESSOR,
            config,
        )
        successor, successor_trace = _run_arm(
            output_dir,
            replication_id,
            seed,
            FrozenSuccessorArm.FROZEN_SUCCESSOR,
            config,
        )
        pair_audit = _pretransition_pair_audit(
            predecessor_trace,
            successor_trace,
            float(config["transition"]["trigger_time_s"]),
        )
        if not pair_audit["all_pretransition_quantities_exactly_equal"]:
            raise RuntimeError("matched A/B trajectories diverged before transition")
        degraded = _closed_loop_degraded(predecessor, successor)
        degradation_flags.append(degraded)
        pairs.append(
            {
                "replication_id": replication_id,
                "cem_seed": seed,
                "predecessor": predecessor,
                "frozen_successor": successor,
                "pretransition_pair_audit": pair_audit,
                "matched_closed_loop_degraded": degraded,
            }
        )
        successor_units.append(successor)
    aggregate = aggregate_replication_units(
        [item["prediction_evidence"] for item in successor_units]
    )
    payload = {
        "schema": "stage5_human_model_frozen_successor_replication_results_v1",
        "evidence_category": "small_independent_paired_replication",
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "model_pair_frozen_before_execution": {
            "theta_0": list(FROZEN_THETA_0),
            "theta_1": list(FROZEN_THETA_1),
            "theta_1_refit": False,
        },
        "truth_scales_evaluation_only": [1.0, 1.0, 1.2],
        "truth_used_online": False,
        "same_seed_exact_rerun_counted_as_new_replication": False,
        "pairs": pairs,
        "between_run_analysis": aggregate,
        "within_run_blocks_pooled_as_independent": False,
        "any_matched_closed_loop_degradation": any(degradation_flags),
        "decision": _decision(
            aggregate, successor_units, any(degradation_flags)
        ),
        "acceleration_monitor_changed": False,
        "runtime_optimized": False,
        "interface_model_changed": False,
    }
    (output_dir / "frozen_successor_replication_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
