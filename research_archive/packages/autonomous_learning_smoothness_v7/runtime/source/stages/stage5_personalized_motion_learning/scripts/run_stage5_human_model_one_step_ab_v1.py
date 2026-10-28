#!/usr/bin/env python3
"""Run the authorized damping +20% one-step Human-model A/B checkpoint."""

from __future__ import annotations

import argparse
from collections import Counter
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
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_model_update import (
    FIXED_ONE_STEP_GAMMA,
    OneStepHumanModelArm,
    OneStepHumanModelControlAuthority,
    fixed_one_step_pacing_status,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_human_model_one_step_ab_v1.json"
)


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_human_model_one_step_ab_v1":
        raise ValueError("unexpected one-step A/B config schema")
    update = payload["bounded_update"]
    if (
        update["parameterization"] != ["alpha_M", "alpha_K", "alpha_D"]
        or update["smoothing_alpha"] != 0.1
        or update["maximum_step_fraction_of_span"] != 0.03
        or update["lower_scales"] != [0.5, 0.5, 0.5]
        or update["upper_scales"] != [1.5, 1.5, 1.5]
        or update["maximum_control_updates"] != 1
    ):
        raise ValueError("bounded Human-model transition contract changed")
    controller = payload["controller"]
    if controller["gamma"] != FIXED_ONE_STEP_GAMMA or controller["gamma_dynamic"]:
        raise ValueError("one-step A/B requires fixed gamma=0.5")
    if payload["human_truth_evaluation_only"]["scales"] != [1.0, 1.0, 1.2]:
        raise ValueError("one-step A/B is limited to damping +20%")
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


def _compact_attempt(authority: OneStepHumanModelControlAuthority) -> dict[str, Any]:
    attempt = authority.qualification_attempt
    if attempt is None:
        return {
            "qualified": False,
            "qualification_time_s": None,
            "candidate_scales": None,
            "proposed_model_scales": None,
        }
    return {
        "qualified": True,
        "challenger_index": int(attempt["challenger_index"]),
        "fit_end_time_s": float(attempt["fit_end_time_s"]),
        "qualification_time_s": float(authority.qualification_time_s),
        "decision_block_count": int(attempt["decision_block_count"]),
        "candidate_scales": list(attempt["candidate_scales"]),
        "proposed_model_scales": list(attempt["proposed_model_scales"]),
        "status": str(attempt["status"]),
    }


def _post_transition_force_prediction(
    trace: dict[str, np.ndarray], transition_time_s: float | None
) -> dict[str, Any]:
    if transition_time_s is None:
        return {"available": False, "aligned_count": 0}
    time = np.asarray(trace["time_s"], dtype=float)
    predicted = np.asarray(
        trace["predicted_next_physical_cuff_force_world_n"], dtype=float
    )
    physical = np.asarray(trace["physical_cuff_force_world_n"], dtype=float)
    valid = (time > transition_time_s + 1.0e-12) & np.all(
        np.isfinite(predicted), axis=1
    )
    if not np.any(valid):
        return {"available": False, "aligned_count": 0}
    vector_error = np.linalg.norm(predicted[valid] - physical[valid], axis=1)
    norm_error = np.abs(
        np.linalg.norm(predicted[valid], axis=1)
        - np.linalg.norm(physical[valid], axis=1)
    )
    return {
        "available": True,
        "aligned_count": int(np.count_nonzero(valid)),
        "vector_rmse_n": float(np.sqrt(np.mean(vector_error**2))),
        "vector_p95_n": float(np.percentile(vector_error, 95)),
        "vector_max_n": float(np.max(vector_error)),
        "norm_rmse_n": float(np.sqrt(np.mean(norm_error**2))),
    }


def _control_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "task_duration_s": summary["task_duration_s"],
        "phase_transitions": summary["phase_transitions"],
        "estimated_terminal_error_deg": summary["estimated_terminal_error_deg"],
        "estimated_terminal_dq_deg_s": summary["estimated_terminal_dq_deg_s"],
        "hold": summary["loaded_local_hold"],
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
        "peak_physical_cuff_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_cuff_force_n_s": summary[
            "cumulative_physical_cuff_force_n_s"
        ],
        "peak_physical_cuff_moment_nm": summary[
            "peak_physical_cuff_moment_nm"
        ],
        "physical_force_prediction_error": summary[
            "physical_force_prediction_error"
        ],
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
        "human_state_estimation_error": summary["human_state_estimation_error"],
        "path_freedom": {
            "maximum_normalized_q1_q2_progress_difference": summary[
                "maximum_normalized_q1_q2_progress_difference"
            ],
            "interpretation": summary["path_freedom_interpretation"],
        },
    }


def _run_arm(
    arm: OneStepHumanModelArm,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    authority = OneStepHumanModelControlAuthority(
        _geometry(), arm, predecessor_version=FIXED_HUMAN_MODEL_VERSION
    )
    human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

    controller = config["controller"]
    base_ceiling = tuple(
        np.radians(controller["base_planning_joint_velocity_ceiling_deg_s"])
    )
    arm_dir = output_dir / arm.value
    summary = run_goal_mpc_smoke(
        arm_dir,
        maximum_duration_s=25.5,
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"human_model_one_step_ab_v1__{arm.value}",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            controller["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=base_ceiling,
        mpc_config=HumanMPCConfig(random_seed=int(controller["cem_random_seed"])),
        plant_factory=plant_factory,
        progress_pacing_callback=fixed_one_step_pacing_status,
        control_human_model_callback=authority.observe,
    )
    with np.load(arm_dir / "trace.npz") as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
    if not np.allclose(gamma, FIXED_ONE_STEP_GAMMA, atol=0.0, rtol=0.0):
        raise RuntimeError("gamma changed during frozen one-step A/B")
    versions = np.asarray(trace["control_human_model_version"], dtype=str)
    if arm is OneStepHumanModelArm.FIXED and np.any(
        versions != FIXED_HUMAN_MODEL_VERSION
    ):
        raise RuntimeError("fixed arm changed Human control model")
    if authority.application_count > 1:
        raise RuntimeError("one-step authority applied more than one update")

    evidence = authority.post_update_prediction_evidence()
    transition = summary["human_model_control_transition"]
    return {
        "arm": arm.value,
        "human_id": {
            "measurement_count": len(authority.service.raw_history),
            "rejected_measurement_count": authority.service.rejected_measurements,
            "attempt_status_counts": dict(
                Counter(str(item["status"]) for item in authority.service.attempts)
            ),
            "publication_count_excluding_prior": (
                len(authority.service.publication_history) - 1
            ),
            "first_qualified_transition": _compact_attempt(authority),
            "truth_available_to_service": False,
        },
        "control_transition": transition,
        "post_update_model_feedback": evidence,
        "post_transition_force_prediction": _post_transition_force_prediction(
            trace, authority.transition_time_s
        ),
        "gamma": {
            "minimum": float(np.min(gamma)),
            "maximum": float(np.max(gamma)),
            "final": float(gamma[-1]),
            "fixed": True,
        },
        "active_model_versions": list(dict.fromkeys(versions.tolist())),
        "control": _control_metrics(summary),
        "artifacts": {
            "summary": f"{arm.value}/summary.json",
            "trace": f"{arm.value}/trace.npz",
        },
    }


def _closed_loop_consequence(fixed: dict[str, Any], adaptive: dict[str, Any]) -> str:
    a = fixed["control"]
    b = adaptive["control"]
    if a["task_status"] != "COMPLETE" and b["task_status"] == "COMPLETE":
        return "improved"
    regression = (
        (a["task_status"] == "COMPLETE" and b["task_status"] != "COMPLETE")
        or b["mpc_failure_count"] > a["mpc_failure_count"]
        or b["brake_event_count"] > a["brake_event_count"]
        or b["force_gate_event_count"] > a["force_gate_event_count"]
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
    )
    return "degraded" if regression else "approximately_unchanged"


def _decision(adaptive: dict[str, Any], consequence: str) -> dict[str, str]:
    feedback = adaptive["post_update_model_feedback"].get("classification")
    outcome = None if feedback is None else feedback.get("outcome")
    if outcome == "positive" and consequence != "degraded":
        return {
            "code": "C-A",
            "label": "ONE-STEP ADAPTIVE UPDATE SUPPORTED",
            "reason": "formal post-update model feedback is positive without a closed-loop regression",
        }
    if outcome == "negative" or consequence == "degraded":
        return {
            "code": "C-C",
            "label": "ONE-STEP UPDATE NOT SUPPORTED",
            "reason": "negative model feedback or a material closed-loop regression was observed",
        }
    return {
        "code": "C-B",
        "label": "MECHANISM WORKS, EVIDENCE INSUFFICIENT",
        "reason": "transition is operational but frozen post-update evidence is neutral or insufficient",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT / "results" / "human_model_one_step_ab_v1_attempt_01"
        ),
    )
    arguments = parser.parse_args()
    output_dir = arguments.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite A/B output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    fixed = _run_arm(OneStepHumanModelArm.FIXED, output_dir, config)
    adaptive = _run_arm(OneStepHumanModelArm.ONE_STEP, output_dir, config)
    consequence = _closed_loop_consequence(fixed, adaptive)
    payload = {
        "schema": "stage5_human_model_one_step_ab_results_v1",
        "evidence_category": "bounded_engineering_closed_loop_ab",
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "truth_condition_evaluation_only": [1.0, 1.0, 1.2],
        "truth_used_for_fit_validation_update_or_control": False,
        "gamma_fixed_both_arms": FIXED_ONE_STEP_GAMMA,
        "acceleration_monitor_changed": False,
        "interface_model_changed": False,
        "progressive_updates_enabled": False,
        "arms": [fixed, adaptive],
        "model_feedback_axis": adaptive["post_update_model_feedback"].get(
            "classification"
        ),
        "closed_loop_consequence_axis": consequence,
        "decision": _decision(adaptive, consequence),
        "runtime_optimized": False,
    }
    (output_dir / "one_step_ab_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
