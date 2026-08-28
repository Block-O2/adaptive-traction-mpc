#!/usr/bin/env python3
"""User-run preregistered prior-only versus trusted-adaptive closed-loop A/B."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, soft_limit_torque
from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row, nominal_base_parameters
from traction_mpc_stage4.evaluation import BED_CONTACT_CONTAMINATION_FORCE_N
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    cold_start_teaching_reference,
)
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


REGISTERED_WALL_LIMIT_S = 32.0
REGISTERED_SENSOR_CASE = "noise_bias_drift_200hz"
REGISTERED_ARMS = {
    "prior_only": False,
    "trusted_adaptive": True,
}

SCALAR_COMPARISON_METRICS = (
    "tracking_combined_rmse_deg",
    "tracking_max_abs_error_deg",
    "cuff_force_peak_n",
    "cuff_force_rms_n",
    "cuff_moment_peak_nm",
    "cuff_moment_rms_nm",
    "cylindrical_surface_proxy_peak_n",
    "cylindrical_surface_proxy_rms_n",
    "speed_scale_mean",
    "speed_scale_minimum",
    "speed_scale_maximum",
)


def _first_time(time: np.ndarray, condition: np.ndarray) -> float | None:
    selected = np.flatnonzero(condition)
    return None if not len(selected) else float(time[selected[0]])


def _window_metrics(trace: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, Any]:
    if not np.any(mask):
        return {"available": False, "sample_count": 0}
    tracking = np.asarray(trace["tracking_error_deg_god_view"])[mask]
    wrench = np.asarray(trace["cuff_wrench_local_god_view"])[mask]
    force = np.linalg.norm(wrench[:, :3], axis=1)
    moment = np.linalg.norm(wrench[:, 3:], axis=1)
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    patch = np.einsum("ij,tj->ti", surface_model.minimum_norm_operator, wrench)
    surface = np.linalg.norm(patch, axis=1)
    torque = np.asarray(trace["robot_torque_nm"])[mask]
    velocity = np.asarray(trace["robot_dq_rad_s"])[mask]
    speed = np.asarray(trace["reference_speed_scale"])[mask]
    return {
        "available": True,
        "sample_count": int(np.sum(mask)),
        "tracking_combined_rmse_deg": float(np.sqrt(np.mean(tracking**2))),
        "tracking_max_abs_error_deg": float(np.max(np.abs(tracking))),
        "cuff_force_peak_n": float(np.max(force)),
        "cuff_force_rms_n": float(np.sqrt(np.mean(force**2))),
        "cuff_moment_peak_nm": float(np.max(moment)),
        "cuff_moment_rms_nm": float(np.sqrt(np.mean(moment**2))),
        "cylindrical_surface_proxy_peak_n": float(np.max(surface)),
        "cylindrical_surface_proxy_rms_n": float(np.sqrt(np.mean(surface**2))),
        "robot_torque_peak_abs_nm": np.max(np.abs(torque), axis=0).tolist(),
        "robot_torque_rms_nm": np.sqrt(np.mean(torque**2, axis=0)).tolist(),
        "robot_velocity_peak_abs_deg_s": np.degrees(
            np.max(np.abs(velocity), axis=0)
        ).tolist(),
        "robot_velocity_rms_deg_s": np.degrees(
            np.sqrt(np.mean(velocity**2, axis=0))
        ).tolist(),
        "speed_scale_mean": float(np.mean(speed)),
        "speed_scale_minimum": float(np.min(speed)),
        "speed_scale_maximum": float(np.max(speed)),
    }


def _time_varying_prediction_error(
    trace: dict[str, np.ndarray], true_beta: np.ndarray
) -> dict[str, Any]:
    control_time = np.asarray(trace["control_time_s"])
    q = np.asarray(trace["control_true_q_rad_god_view"])
    dq = np.asarray(trace["control_true_dq_rad_s_god_view"])
    if len(control_time) < 3:
        return {"sample_count": 0, "combined_rmse_nm": float("nan")}
    ddq = np.gradient(dq, control_time, axis=0, edge_order=2)
    full_time = np.asarray(trace["time_s"])
    beta_trace = np.asarray(trace["dynamic_base_estimate"])
    beta = np.column_stack(
        [np.interp(control_time, full_time, beta_trace[:, index]) for index in range(11)]
    )
    bed = np.interp(control_time, full_time, np.asarray(trace["bed_force_n_god_view"]))
    clean = bed <= BED_CONTACT_CONTAMINATION_FORCE_N
    errors = []
    times = []
    for index in range(len(control_time)):
        if np.linalg.norm(soft_limit_torque(q[index], dq[index], HUMAN)) > 1e-8:
            clean[index] = False
        if not clean[index]:
            continue
        regressor = dynamic_regressor_row(q[index], dq[index], ddq[index])
        errors.append(regressor @ (beta[index] - true_beta))
        times.append(control_time[index])
    error = np.asarray(errors)
    return {
        "sample_count": int(len(error)),
        "combined_rmse_nm": (
            float(np.sqrt(np.mean(error**2))) if len(error) else float("nan")
        ),
        "time_s": np.asarray(times),
        "error_nm": error,
    }


def _promotion_timeline(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    true_beta: np.ndarray,
    *,
    reference_phase_duration_s: float,
) -> list[dict[str, Any]]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    control_time = np.asarray(trace["control_time_s"])
    q = np.asarray(trace["control_true_q_rad_god_view"])
    dq = np.asarray(trace["control_true_dq_rad_s_god_view"])
    ddq = (
        np.gradient(dq, control_time, axis=0, edge_order=2)
        if len(control_time) >= 3
        else np.zeros_like(dq)
    )
    bed = np.interp(
        control_time, time, np.asarray(trace["bed_force_n_god_view"])
    )
    span = AccumulatedIntegralBaseDynamicIdentifier().span
    timeline = []
    for challenger in summary["hierarchical_trust"]["challengers"]:
        item = {
            "challenger_index": challenger["challenger_index"],
            "creation_time_s": challenger["fit_end_time_s"],
            "creation_reference_phase_s": float(
                np.interp(challenger["fit_end_time_s"], time, phase)
            ),
            "status": challenger["status"],
            "decision_time_s": challenger.get("decision_time_s"),
            "validation_duration_s": challenger.get("validation_duration_s"),
            "applied_to_control": challenger["applied_to_control"],
        }
        if challenger.get("decision_time_s") is not None:
            decision_phase = float(
                np.interp(challenger["decision_time_s"], time, phase)
            )
            item["decision_reference_phase_s"] = decision_phase
            item["remaining_reference_duration_s"] = max(
                0.0, reference_phase_duration_s - decision_phase
            )
            evidence = challenger["evidence_history"][-1]
            validation_blocks = evidence["validation_blocks"]
            item["validation_timeline"] = {
                "decision_look_block_count": evidence["look_block_count"],
                "first_block_start_time_s": validation_blocks[0]["start_time_s"],
                "first_block_start_reference_phase_s": float(
                    np.interp(validation_blocks[0]["start_time_s"], time, phase)
                ),
                "last_block_end_time_s": validation_blocks[-1]["end_time_s"],
                "last_block_end_reference_phase_s": float(
                    np.interp(validation_blocks[-1]["end_time_s"], time, phase)
                ),
                "all_evaluated_looks": [
                    {
                        "look_block_count": look["look_block_count"],
                        "decision_time_s": look["decision_time_s"],
                        "decision_reference_phase_s": float(
                            np.interp(look["decision_time_s"], time, phase)
                        ),
                        "promotion_supported": look["promotion_supported"],
                        "against_prior_upper_bound_nms2": look[
                            "against_population_prior"
                        ]["upper_bound_nms2"],
                        "against_fixed_incumbent_upper_bound_nms2": look[
                            "against_last_valid"
                        ]["upper_bound_nms2"],
                    }
                    for look in challenger["evidence_history"]
                ],
            }
            selected = np.zeros(len(control_time), dtype=bool)
            for block in validation_blocks:
                selected |= (
                    (control_time >= block["start_time_s"] - 1e-12)
                    & (control_time <= block["end_time_s"] + 1e-12)
                )
            proposed = np.asarray(challenger["proposed_model_beta"], dtype=float)
            incumbent = np.asarray(challenger["reference_incumbent_beta"], dtype=float)
            proposed_errors = []
            incumbent_errors = []
            for index in np.flatnonzero(selected):
                if bed[index] > BED_CONTACT_CONTAMINATION_FORCE_N:
                    continue
                if np.linalg.norm(soft_limit_torque(q[index], dq[index], HUMAN)) > 1e-8:
                    continue
                regressor = dynamic_regressor_row(q[index], dq[index], ddq[index])
                oracle = regressor @ true_beta
                proposed_errors.append(regressor @ proposed - oracle)
                incumbent_errors.append(regressor @ incumbent - oracle)
            proposed_error = np.asarray(proposed_errors)
            incumbent_error = np.asarray(incumbent_errors)
            proposed_rmse = (
                float(np.sqrt(np.mean(proposed_error**2)))
                if len(proposed_error)
                else float("nan")
            )
            incumbent_rmse = (
                float(np.sqrt(np.mean(incumbent_error**2)))
                if len(incumbent_error)
                else float("nan")
            )
            item["oracle_post_decision_only"] = {
                "sample_count": int(len(proposed_error)),
                "challenger_prediction_rmse_nm": proposed_rmse,
                "incumbent_prediction_rmse_nm": incumbent_rmse,
                "improvement_nm": incumbent_rmse - proposed_rmse,
                "challenger_true_beta_distance_span_l2": float(
                    np.linalg.norm((proposed - true_beta) / span)
                ),
                "incumbent_true_beta_distance_span_l2": float(
                    np.linalg.norm((incumbent - true_beta) / span)
                ),
                "used_online": False,
            }
        timeline.append(item)
    return timeline


def _row(
    arm: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    *,
    split_time_s: float | None,
    true_beta: np.ndarray,
    reference_phase_duration_s: float,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    completion = _first_time(
        time, phase >= reference_phase_duration_s - 1e-9
    )
    task_mask = phase <= reference_phase_duration_s + 1e-9
    if split_time_s is None:
        pre = task_mask
        post = np.zeros_like(task_mask)
    else:
        pre = task_mask & (time < split_time_s - 1e-12)
        post = task_mask & (time >= split_time_s - 1e-12)
    prediction = _time_varying_prediction_error(trace, true_beta)
    prediction_time = np.asarray(prediction.pop("time_s"))
    prediction_error = np.asarray(prediction.pop("error_nm"))
    prediction["pre_first_promotion_combined_rmse_nm"] = (
        float(np.sqrt(np.mean(prediction_error[prediction_time < split_time_s] ** 2)))
        if split_time_s is not None
        and np.any(prediction_time < split_time_s)
        else float("nan")
    )
    prediction["post_first_promotion_combined_rmse_nm"] = (
        float(np.sqrt(np.mean(prediction_error[prediction_time >= split_time_s] ** 2)))
        if split_time_s is not None
        and np.any(prediction_time >= split_time_s)
        else float("nan")
    )
    return {
        "arm": arm,
        "termination_reason": summary["termination_reason"],
        "wall_duration_s": summary["completed_duration_s"],
        "reference_completion_time_s": completion,
        "final_reference_phase_s": float(phase[-1]),
        "reference_progress_fraction": float(
            min(1.0, phase[-1] / reference_phase_duration_s)
        ),
        "promotion_timeline": _promotion_timeline(
            summary,
            trace,
            true_beta,
            reference_phase_duration_s=reference_phase_duration_s,
        ),
        "full_task": _window_metrics(trace, task_mask),
        "pre_first_trusted_adaptive_promotion": _window_metrics(trace, pre),
        "post_first_trusted_adaptive_promotion": _window_metrics(trace, post),
        "estimator_control_model_prediction_error_god_view": prediction,
        "confidence_pacing": summary["reference_execution"],
        "hierarchical_trust": summary["hierarchical_trust"],
        "robot": summary["robot"],
        "events": summary["events"],
        "mpc": summary["mpc"],
        "computational_cost": summary["computational_cost"],
    }


def _comparison_deltas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm = {item["arm"]: item for item in rows}
    prior = by_arm["prior_only"]
    adaptive = by_arm["trusted_adaptive"]
    result: dict[str, Any] = {
        "sign_convention": "trusted_adaptive_minus_prior_only",
        "reference_progress_fraction": (
            adaptive["reference_progress_fraction"]
            - prior["reference_progress_fraction"]
        ),
    }
    prior_completion = prior["reference_completion_time_s"]
    adaptive_completion = adaptive["reference_completion_time_s"]
    result["reference_completion_time_s"] = (
        None
        if prior_completion is None or adaptive_completion is None
        else float(adaptive_completion - prior_completion)
    )
    for window in (
        "full_task",
        "pre_first_trusted_adaptive_promotion",
        "post_first_trusted_adaptive_promotion",
    ):
        prior_window = prior[window]
        adaptive_window = adaptive[window]
        if not prior_window["available"] or not adaptive_window["available"]:
            result[window] = {"available": False}
            continue
        result[window] = {
            "available": True,
            **{
                metric: float(adaptive_window[metric] - prior_window[metric])
                for metric in SCALAR_COMPARISON_METRICS
            },
        }
    return result


def _verify_ab_isolation(
    summaries: dict[str, dict[str, Any]],
    traces: dict[str, dict[str, np.ndarray]],
    *,
    split_time_s: float | None,
) -> dict[str, Any]:
    prior_summary = summaries["prior_only"]
    adaptive_summary = summaries["trusted_adaptive"]
    shared_summary_fields = (
        "measurement_model",
        "measurement_routing",
        "trajectory",
        "requested_duration_s",
        "force_gate_n",
        "moment_limit_nm",
    )
    for field in shared_summary_fields:
        if prior_summary[field] != adaptive_summary[field]:
            raise RuntimeError(f"A/B shared configuration differs at {field}")
    prior_trust = prior_summary["hierarchical_trust"]
    adaptive_trust = adaptive_summary["hierarchical_trust"]
    if prior_trust["statistical_config"] != adaptive_trust["statistical_config"]:
        raise RuntimeError("A/B statistical trust configuration differs")
    for arm, trust in (
        ("prior_only", prior_trust),
        ("trusted_adaptive", adaptive_trust),
    ):
        if trust["superseded_count"] or trust["race_state_count"]:
            raise RuntimeError(f"{arm} entered a race or superseded state")
        if trust["maximum_concurrent_challengers"] > 1:
            raise RuntimeError(f"{arm} launched competing challengers")
    if prior_trust["counts"]["control_promotions"] != 0:
        raise RuntimeError("prior-only arm applied a dynamics promotion")

    prior_beta = np.asarray(traces["prior_only"]["dynamic_base_estimate"])
    if not np.allclose(prior_beta, prior_beta[0], rtol=0.0, atol=1e-12):
        raise RuntimeError("prior-only control dynamics changed during the rollout")

    first_qualification_times: dict[str, float | None] = {}
    for arm, trust in (
        ("prior_only", prior_trust),
        ("trusted_adaptive", adaptive_trust),
    ):
        qualifications = trust["qualifications"]
        first_qualification_times[arm] = (
            None
            if not qualifications
            else float(qualifications[0]["qualification_time_s"])
        )
    if first_qualification_times["prior_only"] != first_qualification_times[
        "trusted_adaptive"
    ]:
        raise RuntimeError("first causal qualification time differs before model application")

    pre_promotion_max_abs_difference: dict[str, float] = {}
    if split_time_s is not None:
        prior_time = np.asarray(traces["prior_only"]["time_s"])
        adaptive_time = np.asarray(traces["trusted_adaptive"]["time_s"])
        prior_mask = prior_time < split_time_s - 1e-12
        adaptive_mask = adaptive_time < split_time_s - 1e-12
        if not np.array_equal(prior_time[prior_mask], adaptive_time[adaptive_mask]):
            raise RuntimeError("pre-promotion A/B time grids differ")
        for key in (
            "reference_phase_time_s",
            "human_q_deg_god_view",
            "desired_human_action_nm",
            "allocated_wrench_world",
            "reference_speed_scale",
            "dynamic_base_estimate",
        ):
            prior_value = np.asarray(traces["prior_only"][key])[prior_mask]
            adaptive_value = np.asarray(traces["trusted_adaptive"][key])[adaptive_mask]
            maximum = float(np.max(np.abs(prior_value - adaptive_value)))
            pre_promotion_max_abs_difference[key] = maximum
            if not np.allclose(prior_value, adaptive_value, rtol=0.0, atol=1e-10):
                raise RuntimeError(f"pre-promotion A/B trace differs at {key}")
    return {
        "shared_configuration_fields_equal": True,
        "prior_control_model_constant": True,
        "first_qualification_times_s": first_qualification_times,
        "first_qualification_times_equal": True,
        "single_challenger_invariants_held": True,
        "pre_promotion_trace_max_abs_difference": pre_promotion_max_abs_difference,
    }


def _write_markdown_summary(path: Path, comparison: dict[str, Any]) -> None:
    lines = [
        "# Stage-4 Single-Challenger Closed-Loop A/B",
        "",
        f"Evidence: `{comparison['evidence_category']}`.",
        "",
        "The cylindrical quantity is a minimum-norm equivalent surface-load "
        "proxy, not pressure or comfort.",
        "",
        "| arm | termination | completion s | progress | first promotion s |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in comparison["rows"]:
        promotions = row["hierarchical_trust"]["control_promotions"]
        first = None if not promotions else promotions[0]["promotion_time_s"]
        completion = row["reference_completion_time_s"]
        lines.append(
            f"| {row['arm']} | {row['termination_reason']} | "
            f"{completion if completion is not None else 'not reached'} | "
            f"{row['reference_progress_fraction']:.6f} | "
            f"{first if first is not None else 'none'} |"
        )
    for window in (
        "full_task",
        "pre_first_trusted_adaptive_promotion",
        "post_first_trusted_adaptive_promotion",
    ):
        lines.extend(
            [
                "",
                f"## {window}",
                "",
                "| arm | tracking RMSE deg | max deg | F peak/RMS N | "
                "M peak/RMS Nm | surface proxy peak/RMS N |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in comparison["rows"]:
            metrics = row[window]
            if not metrics["available"]:
                lines.append(f"| {row['arm']} | unavailable | | | | |")
                continue
            lines.append(
                f"| {row['arm']} | {metrics['tracking_combined_rmse_deg']:.6g} | "
                f"{metrics['tracking_max_abs_error_deg']:.6g} | "
                f"{metrics['cuff_force_peak_n']:.6g} / {metrics['cuff_force_rms_n']:.6g} | "
                f"{metrics['cuff_moment_peak_nm']:.6g} / {metrics['cuff_moment_rms_nm']:.6g} | "
                f"{metrics['cylindrical_surface_proxy_peak_n']:.6g} / "
                f"{metrics['cylindrical_surface_proxy_rms_n']:.6g} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_paired_ab_comparison(
    summaries: dict[str, dict[str, Any]],
    traces: dict[str, dict[str, np.ndarray]],
    *,
    sensor_case_name: str,
    measurement_seed: int,
    true_human: HumanV2Parameters,
    human_label: str,
    wall_time_limit_s: float,
    evidence_category: str,
    reference_phase_duration_s: float,
    trajectory_label: str,
) -> dict[str, Any]:
    """Build the paired result from completed arm summaries and traces."""

    adaptive_promotions = summaries["trusted_adaptive"]["hierarchical_trust"][
        "control_promotions"
    ]
    split_time = (
        float(adaptive_promotions[0]["promotion_time_s"])
        if adaptive_promotions
        else None
    )
    true_beta = nominal_base_parameters(true_human)
    isolation = _verify_ab_isolation(
        summaries,
        traces,
        split_time_s=split_time,
    )
    rows = [
        _row(
            arm,
            summaries[arm],
            traces[arm],
            split_time_s=split_time,
            true_beta=true_beta,
            reference_phase_duration_s=reference_phase_duration_s,
        )
        for arm in REGISTERED_ARMS
    ]
    comparison = {
        "evidence_category": evidence_category,
        "production_default": False,
        "single_scientific_variable": "apply_statistically_qualified_dynamics_model_to_control",
        "registered_configuration": {
            "arms": REGISTERED_ARMS,
            "sensor_case": sensor_case_name,
            "measurement_seed": measurement_seed,
            "mpc_seed": 20260824,
            "wall_time_limit_s": wall_time_limit_s,
            "reference_phase_duration_s": reference_phase_duration_s,
            "human": human_label,
            "trajectory": trajectory_label,
            "estimator": "unchanged_11_base_integral",
            "trust": "four_layer_single_incumbent_challenger_anytime_alpha_spending",
            "allocator": "frozen_1_to_1_cuff_aware",
            "confidence_pacing": "existing_filtered_hysteretic_model_confidence",
            "mpc_controller_safety_changed": False,
            "oracle_used_online": False,
            "measurement_model": summaries["prior_only"]["measurement_model"],
            "measurement_routing": summaries["prior_only"]["measurement_routing"],
            "mpc_objective_contract": summaries["prior_only"]["mpc"][
                "objective_contract"
            ],
            "confidence_pacing_config": summaries["prior_only"][
                "reference_execution"
            ]["config"],
            "statistical_trust_config": summaries["prior_only"][
                "hierarchical_trust"
            ]["statistical_config"],
        },
        "shared_pre_post_split_wall_time_s": split_time,
        "mechanical_ab_isolation": isolation,
        "rows": rows,
    }
    comparison["trusted_adaptive_minus_prior_only"] = _comparison_deltas(rows)
    return comparison


def run_paired_ab(
    output_dir: Path,
    *,
    sensor_case_name: str = REGISTERED_SENSOR_CASE,
    measurement_seed: int | None = None,
    true_human: HumanV2Parameters | None = None,
    true_metadata: dict[str, Any] | None = None,
    human_label: str = "registered_cold_start_perturbed_human",
    wall_time_limit_s: float = REGISTERED_WALL_LIMIT_S,
    evidence_category: str = "formal_user_run_unreviewed",
    write_comparison_outputs: bool = True,
    reference_fn: Callable[[float], CuffPoseReference] = cold_start_teaching_reference,
    reference_phase_duration_s: float = COLD_START_TEACHING_DURATION_S,
    trajectory_label: str = "stage4_population_prior_cold_start_high_flexion_23s",
    trajectory_waypoints: tuple[Any, ...] = COLD_START_TEACHING_WAYPOINTS,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, np.ndarray]],
]:
    """Execute the frozen paired A/B path for one supplied true Human plant."""

    if reference_phase_duration_s <= 0.0:
        raise ValueError("reference phase duration must be positive")
    if wall_time_limit_s <= 0.0:
        raise ValueError("wall-time limit must be positive")
    if true_human is None:
        true_human, registered_metadata = registered_cold_start_perturbed_human()
        if true_metadata is None:
            true_metadata = registered_metadata
    if true_metadata is None:
        true_metadata = {"case": human_label}
    cases = {item.name: item for item in sensor_realism_cases()}
    if sensor_case_name not in cases:
        available = ", ".join(sorted(cases))
        raise ValueError(
            f"unknown existing sensor case {sensor_case_name!r}; available: {available}"
        )
    case = cases[sensor_case_name]
    if measurement_seed is not None:
        if isinstance(measurement_seed, bool) or not isinstance(measurement_seed, int):
            raise TypeError("measurement seed must be an integer")
        if measurement_seed < 0:
            raise ValueError("measurement seed must be nonnegative")
        case = replace(case, seed=measurement_seed)
    summaries: dict[str, dict[str, Any]] = {}
    traces: dict[str, dict[str, np.ndarray]] = {}
    for arm, apply_model in REGISTERED_ARMS.items():
        execution = ReferenceExecutionLayer(reference_fn, confidence_aware=True)

        def estimator_factory(
            measurement: Any,
            q_prior: np.ndarray,
            apply: bool = apply_model,
        ) -> Any:
            return OnlineSingleChallengerTrustEstimator(
                measurement,
                q_prior,
                measurement_case=case,
                apply_qualified_model=apply,
            )

        summary, trace = run_sensor_realism_case(
            case,
            duration_s=wall_time_limit_s,
            estimator_architecture="integral_minimal",
            result_case_name=arm,
            true_human_override=true_human,
            true_metadata_override=true_metadata,
            reference_fn=reference_fn,
            trajectory_label=trajectory_label,
            trajectory_waypoints=trajectory_waypoints,
            reference_execution=execution,
            estimator_factory=estimator_factory,
        )
        save_sensor_case(output_dir, summary, trace)
        summaries[arm] = summary
        traces[arm] = trace

    comparison = build_paired_ab_comparison(
        summaries,
        traces,
        sensor_case_name=sensor_case_name,
        measurement_seed=case.seed,
        true_human=true_human,
        human_label=human_label,
        wall_time_limit_s=wall_time_limit_s,
        evidence_category=evidence_category,
        reference_phase_duration_s=reference_phase_duration_s,
        trajectory_label=trajectory_label,
    )
    if write_comparison_outputs:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "comparison_summary.json").write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_markdown_summary(output_dir / "comparison_summary.md", comparison)
    return comparison, summaries, traces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    run_paired_ab(args.output_dir)


if __name__ == "__main__":
    main()
