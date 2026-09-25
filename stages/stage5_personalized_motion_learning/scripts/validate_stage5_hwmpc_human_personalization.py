#!/usr/bin/env python3
"""Matched CR12 validation of existing progressive Human ID on HWMPC."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_mpc import HumanWaypointMPCPrototypeV1
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.progressive_personalization import (
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    deployable_prediction_summary,
    initial_population_prior_model,
    parameter_direction_diagnostics,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

from validate_stage5_human_waypoint_mpc import _MPCRegisteredTaskController
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _jsonable,
    _prepare_runtime,
    _run_case,
)


SCHEMA = "stage5_hwmpc_human_personalization_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_human_personalization_v1.json"
)


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


def _truth_human(condition: dict[str, Any]) -> Any:
    scales = np.asarray(condition["truth_scales_evaluation_only"], dtype=float)
    if condition["name"] == "damping_plus_20pct":
        return replace(
            STAGE5_HUMAN,
            passive_damping_nms_rad=tuple(
                scales[2]
                * np.asarray(STAGE5_HUMAN.passive_damping_nms_rad, dtype=float)
            ),
        )
    if condition["name"] == "stiffness_plus_15pct":
        return replace(
            STAGE5_HUMAN,
            passive_stiffness_nm_rad=tuple(
                scales[1]
                * np.asarray(STAGE5_HUMAN.passive_stiffness_nm_rad, dtype=float)
            ),
        )
    raise ValueError(f"unsupported preregistered mismatch {condition['name']}")


def _prediction_trace(metrics: dict[str, Any]) -> dict[str, np.ndarray]:
    trace = metrics["trace"]
    return {
        "time_s": np.asarray([row["elapsed_s"] for row in trace], dtype=float),
        "estimated_state_rad_rad_s": np.asarray(
            [row["estimated_state_rad_rad_s"] for row in trace], dtype=float
        ),
        "deployable_measured_generalized_input_nm": np.asarray(
            [row["deployable_measured_generalized_input_nm"] for row in trace],
            dtype=float,
        ),
        "task_phase": np.asarray([row["phase"] for row in trace], dtype=str),
    }


def _run_repetition(
    *,
    condition: dict[str, Any],
    session: ProgressiveLongitudinalSession,
    repetition: int,
    session_time_s: float,
    coordination_r: float,
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    attempts_before = len(session.authority.service.attempts)
    history_before = len(session.authority.history)
    boundary = session.begin_repetition(repetition, session_time_s)
    active = session.active_model
    active_control_model = session.control_human_model
    truth_human = _truth_human(condition)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec, active_control_model, reference_period_s=CONTROL_DT_S
    )
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    controller = _MPCRegisteredTaskController(
        mpc,
        scheduler,
        coordination_preference_r=coordination_r,
    )

    def runtime_factory(name: str, start_q_rad: np.ndarray) -> dict[str, Any]:
        return _prepare_runtime(
            name,
            start_q_rad,
            truth_human=truth_human,
            control_human_model=active_control_model,
            control_human_model_version=active.model_id,
        )

    wall_start = perf_counter()
    metrics = _run_case(
        name=(
            f"hwmpc_personalization_{condition['name']}_{session.arm.value}_"
            f"rep{repetition:02d}"
        ),
        kind="hwmpc_progressive_human_personalization",
        start_q_rad=start,
        duration_s=(
            2.0 * spec.phase_timeout_s + spec.hold_duration_s + CONTROL_DT_S
        ),
        stateful_schedule=controller,
        completion_check=lambda: controller.completed_time_s is not None,
        schedule_context_hook=controller.bind_execution_context,
        runtime_factory=runtime_factory,
        deployable_sample_hook=session.observe,
    )
    wall_time_s = perf_counter() - wall_start
    finalized = session.finalize_repetition()
    trace = _prediction_trace(metrics)
    active_prediction = deployable_prediction_summary(trace, active.theta)
    prior_prediction = deployable_prediction_summary(trace, (1.0, 1.0, 1.0))
    decision_record = controller.record()
    decision_r = [
        float(item["coordination_preference_r"])
        for item in decision_record["mpc"]["decisions"]
    ]
    version_trace = {
        str(row["control_human_model_version"]) for row in metrics["trace"]
    }
    return {
        "arm": session.arm.value,
        "condition": condition["name"],
        "repetition": repetition,
        "session_start_time_s": session_time_s,
        "active_model_id": active.model_id,
        "active_theta": list(active.theta),
        "active_post_update_support_at_start": active.post_update_support.value,
        "activation": boundary.activation,
        "active_model_fixed_within_repetition": version_trace == {active.model_id},
        "control_model_version_trace": sorted(version_trace),
        "coordination_r_sequence": decision_r,
        "coordination_r_min": min(decision_r),
        "coordination_r_max": max(decision_r),
        "controller": decision_record,
        "metrics": metrics,
        "prediction": {
            "active_model": active_prediction,
            "population_prior": prior_prediction,
            "active_minus_prior_all_phase_loss_nms2": (
                active_prediction["ALL_PHASES"].get("mean_squared_loss_nms2", 0.0)
                - prior_prediction["ALL_PHASES"].get("mean_squared_loss_nms2", 0.0)
            ),
        },
        "authority_end": finalized,
        "new_identifier_attempts": session.authority.service.attempts[
            attempts_before:
        ],
        "new_authority_history": session.authority.history[history_before:],
        "wall_runtime_s": wall_time_s,
    }


def _run_arm(
    *,
    condition: dict[str, Any],
    arm: ProgressiveLongitudinalArm,
    repetitions: int,
    reset_gap_s: float,
    coordination_r: float,
) -> dict[str, Any]:
    session_id = f"hwmpc-{condition['name']}-{arm.value}"
    session = ProgressiveLongitudinalSession(
        _geometry(),
        arm,
        session_id=session_id,
        initial_active_model=initial_population_prior_model(session_id),
    )
    rows = []
    session_time_s = 0.0
    for repetition in range(1, repetitions + 1):
        row = _run_repetition(
            condition=condition,
            session=session,
            repetition=repetition,
            session_time_s=session_time_s,
            coordination_r=coordination_r,
        )
        rows.append(row)
        session_time_s += (
            float(row["metrics"]["executed_duration_s"]) + reset_gap_s
        )
    deltas = [
        model["bounded_transition_delta"]
        for model in session.authority.summary()["lineage"].values()
        if model["update_index"] > 0
    ]
    return {
        "arm": arm.value,
        "repetitions": rows,
        "authority": session.authority.summary(),
        "post_update_evidence_history": session.post_update_evidence_history,
        "blocked_qualified_proposals": session.blocked_qualified_proposals,
        "parameter_direction_diagnostics": parameter_direction_diagnostics(deltas),
    }


def _paired_summary(
    fixed: dict[str, Any], progressive: dict[str, Any], support: list[float]
) -> dict[str, Any]:
    fixed_rows = fixed["repetitions"]
    progressive_rows = progressive["repetitions"]
    pairs = []
    for fixed_row, progressive_row in zip(
        fixed_rows, progressive_rows, strict=True
    ):
        f = fixed_row["metrics"]
        p = progressive_row["metrics"]
        fixed_q_rmse = np.asarray(f["estimated_q_tracking_rmse_deg"], dtype=float)
        progressive_q_rmse = np.asarray(
            p["estimated_q_tracking_rmse_deg"], dtype=float
        )
        pairs.append(
            {
                "repetition": fixed_row["repetition"],
                "fixed_complete": fixed_row["controller"]["completed_time_s"] is not None,
                "progressive_complete": progressive_row["controller"]["completed_time_s"] is not None,
                "fixed_completion_time_s": fixed_row["controller"]["completed_time_s"],
                "progressive_completion_time_s": progressive_row["controller"]["completed_time_s"],
                "fixed_q_tracking_rmse_deg": fixed_q_rmse,
                "progressive_q_tracking_rmse_deg": progressive_q_rmse,
                "progressive_minus_fixed_q_rmse_norm_deg": float(
                    np.linalg.norm(progressive_q_rmse)
                    - np.linalg.norm(fixed_q_rmse)
                ),
                "progressive_active_minus_prior_prediction_loss_nms2": (
                    progressive_row["prediction"][
                        "active_minus_prior_all_phase_loss_nms2"
                    ]
                ),
                "fixed_motion_violations": f["human_motion_authority"]["violation_count"],
                "progressive_motion_violations": p["human_motion_authority"]["violation_count"],
                "fixed_contact_samples": f["execution_safety"]["shank_bed_contact_sample_count"],
                "progressive_contact_samples": p["execution_safety"]["shank_bed_contact_sample_count"],
            }
        )
    activation_count = sum(
        row["activation"] is not None for row in progressive_rows
    )
    all_rows = fixed_rows + progressive_rows
    r_inside = all(
        support[0] - 1.0e-12 <= row["coordination_r_min"]
        and row["coordination_r_max"] <= support[1] + 1.0e-12
        for row in all_rows
    )
    return {
        "pairs": pairs,
        "progressive_activation_count": activation_count,
        "all_active_models_fixed_within_repetition": all(
            row["active_model_fixed_within_repetition"] for row in all_rows
        ),
        "all_r_inside_frozen_support": r_inside,
    }


def _passes_control_contract(row: dict[str, Any]) -> bool:
    metrics = row["metrics"]
    safety = metrics["execution_safety"]
    return bool(
        row["controller"]["completed_time_s"] is not None
        and metrics["termination_reason"] is None
        and metrics["human_motion_authority"]["violation_count"] == 0
        and safety["shank_bed_contact_sample_count"] == 0
        and safety["brake_cycle_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["torque_clip_event_count"] == 0
    )


def _all_activated_successors_have_positive_post_update_evidence(
    result: dict[str, Any],
) -> bool:
    lineage = result["arms"][ProgressiveLongitudinalArm.PROGRESSIVE.value][
        "authority"
    ]["lineage"]
    successors = [
        model for model in lineage.values() if int(model["update_index"]) > 0
    ]
    return bool(successors) and all(
        model["post_update_support"] == "positive"
        and model["post_update_evidence_id"] is not None
        for model in successors
    )


def _plot(results: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(len(results), 2, figsize=(13, 5 * len(results)))
    if len(results) == 1:
        axes = np.asarray([axes])
    for row_index, result in enumerate(results):
        progressive = result["arms"][ProgressiveLongitudinalArm.PROGRESSIVE.value]
        fixed = result["arms"][ProgressiveLongitudinalArm.FIXED_POPULATION_PRIOR.value]
        repetitions = np.arange(1, len(progressive["repetitions"]) + 1)
        theta = np.asarray(
            [row["active_theta"] for row in progressive["repetitions"]], dtype=float
        )
        for index, label in enumerate(("alpha_M", "alpha_K", "alpha_D")):
            axes[row_index, 0].plot(repetitions, theta[:, index], marker="o", label=label)
        axes[row_index, 0].set_title(f"{result['condition']}: progressive theta_H")
        axes[row_index, 0].set_xlabel("repetition")
        axes[row_index, 0].grid(True, alpha=0.3)
        axes[row_index, 0].legend()

        fixed_rmse = [
            np.linalg.norm(row["metrics"]["estimated_q_tracking_rmse_deg"])
            for row in fixed["repetitions"]
        ]
        progressive_rmse = [
            np.linalg.norm(row["metrics"]["estimated_q_tracking_rmse_deg"])
            for row in progressive["repetitions"]
        ]
        axes[row_index, 1].plot(repetitions, fixed_rmse, marker="o", label="fixed prior")
        axes[row_index, 1].plot(repetitions, progressive_rmse, marker="o", label="progressive")
        axes[row_index, 1].set_title(f"{result['condition']}: q tracking RMSE norm")
        axes[row_index, 1].set_xlabel("repetition")
        axes[row_index, 1].set_ylabel("deg")
        axes[row_index, 1].grid(True, alpha=0.3)
        axes[row_index, 1].legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(output_dir: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_human_personalization_v1":
        raise ValueError("unexpected HWMPC personalization config schema")
    if config.get("status") != "PREREGISTERED_BEFORE_HWMPC_PERSONALIZATION_OUTCOMES":
        raise ValueError("HWMPC personalization study must remain preregistered")
    human_id = config["human_identification"]
    if (
        human_id["parameterization"] != ["alpha_M", "alpha_K", "alpha_D"]
        or human_id["lower_scales"] != [0.5, 0.5, 0.5]
        or human_id["upper_scales"] != [1.5, 1.5, 1.5]
        or human_id["smoothing_alpha"] != 0.1
        or human_id["maximum_update_fraction_of_span"] != 0.03
        or human_id["regularization_weight"] != 0.001
        or human_id["future_validation_blocks"] != [8, 10, 12]
    ):
        raise ValueError("existing progressive Human-ID contract changed")
    trajectory = config["trajectory"]
    support = [float(value) for value in trajectory["frozen_support_interval"]]
    coordination_r = float(trajectory["coordination_r"])
    if not support[0] <= coordination_r <= support[1]:
        raise ValueError("coordination r lies outside frozen support")
    if not trajectory["selection_is_force_neutral"]:
        raise ValueError("HWMPC personalization must remain force-neutral")

    results = []
    repetitions = int(config["repetitions_per_arm_condition"])
    reset_gap = float(config["physical_reset_gap_in_session_time_s"])
    for condition in config["mismatch_conditions"]:
        arms = {}
        for arm in (
            ProgressiveLongitudinalArm.FIXED_POPULATION_PRIOR,
            ProgressiveLongitudinalArm.PROGRESSIVE,
        ):
            arms[arm.value] = _run_arm(
                condition=condition,
                arm=arm,
                repetitions=repetitions,
                reset_gap_s=reset_gap,
                coordination_r=coordination_r,
            )
        results.append(
            {
                "condition": condition["name"],
                "truth_scales_evaluation_only": condition[
                    "truth_scales_evaluation_only"
                ],
                "arms": arms,
                "comparison": _paired_summary(
                    arms[ProgressiveLongitudinalArm.FIXED_POPULATION_PRIOR.value],
                    arms[ProgressiveLongitudinalArm.PROGRESSIVE.value],
                    support,
                ),
            }
        )

    all_rows = [
        row
        for result in results
        for arm in result["arms"].values()
        for row in arm["repetitions"]
    ]
    all_contracts_pass = all(_passes_control_contract(row) for row in all_rows)
    all_versions_causal = all(
        result["comparison"]["all_active_models_fixed_within_repetition"]
        for result in results
    )
    all_r_supported = all(
        result["comparison"]["all_r_inside_frozen_support"] for result in results
    )
    activations_sufficient = all(
        result["comparison"]["progressive_activation_count"]
        >= config["acceptance"]["minimum_progressive_activation_count_per_condition"]
        for result in results
    )
    all_successors_causally_validated = all(
        _all_activated_successors_have_positive_post_update_evidence(result)
        for result in results
    )
    final_prediction_preserved = all(
        result["arms"][ProgressiveLongitudinalArm.PROGRESSIVE.value][
            "repetitions"
        ][-1]["prediction"]["active_minus_prior_all_phase_loss_nms2"]
        <= 0.0
        for result in results
    )
    if (
        all_contracts_pass
        and all_versions_causal
        and all_r_supported
        and activations_sufficient
        and all_successors_causally_validated
        and final_prediction_preserved
    ):
        decision = "HP-A — HUMAN PERSONALIZATION IS COMPATIBLE WITH THE HWMPC BASELINE"
        limitation = None
    elif all_contracts_pass and all_versions_causal and all_r_supported:
        decision = "HP-B — PERSONALIZATION WORKS PARTIALLY BUT NEEDS ADAPTATION TO THE NEW ABSTRACTION"
        limitation = (
            "an activated successor lacked positive post-update support, or updates "
            "or predictive benefit were not established in every mismatch condition"
        )
    else:
        decision = "HP-C — EXISTING PERSONALIZATION IS NOT COMPATIBLE WITH HWMPC"
        limitation = "one or more HWMPC feasibility, causal authority, support-range, or safety contracts regressed"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "hwmpc_human_personalization.png"
    _plot(results, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "bounded_matched_engineering_validation",
            "decision": decision,
            "remaining_limitation": limitation,
            "config": config,
            "conditions": results,
            "acceptance_observed": {
                "all_control_contracts_passed": all_contracts_pass,
                "all_model_versions_causally_aligned": all_versions_causal,
                "all_r_inside_frozen_support": all_r_supported,
                "minimum_activation_count_met_each_condition": activations_sufficient,
                "all_activated_successors_have_positive_post_update_evidence": (
                    all_successors_causally_validated
                ),
                "final_prediction_preserved_each_condition": final_prediction_preserved,
            },
            "plot": str(plot_path),
            "scope_invariants": {
                "force_or_value_objective_active": False,
                "force_based_r_selection": False,
                "rl_imitation_or_value_learning_active": False,
                "human_id_update_semantics_changed": False,
                "r_support_bounds_changed": False,
                "controller_gain_threshold_task_or_contact_changed": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
            },
        }
    )
    result_path = output_dir / "hwmpc_human_personalization.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "acceptance_observed": payload["acceptance_observed"],
                "conditions": [
                    {
                        "condition": result["condition"],
                        "progressive_activation_count": result["comparison"][
                            "progressive_activation_count"
                        ],
                        "final_active_theta": result["arms"][
                            ProgressiveLongitudinalArm.PROGRESSIVE.value
                        ]["repetitions"][-1]["active_theta"],
                        "final_active_minus_prior_prediction_loss_nms2": result[
                            "arms"
                        ][ProgressiveLongitudinalArm.PROGRESSIVE.value][
                            "repetitions"
                        ][-1]["prediction"][
                            "active_minus_prior_all_phase_loss_nms2"
                        ],
                    }
                    for result in results
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
    run_validation(arguments.output_dir, arguments.config)


if __name__ == "__main__":
    main()
