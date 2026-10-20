#!/usr/bin/env python3
"""Offline diagnosis of the CR12 early 20 ms Human-acceleration event."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np

from traction_mpc_stage4.human_model import dynamic_terms
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


EVENT_TIME_S = 0.300
PREFIX_TIMES_S = np.array([0.005, 0.010, 0.015, 0.020])
EPSILON_S = 1.0e-9


def _jsonable_summary(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        "start": array[0].tolist(),
        "end": array[-1].tolist(),
        "minimum": np.min(array, axis=0).tolist(),
        "maximum": np.max(array, axis=0).tolist(),
        "mean": np.mean(array, axis=0).tolist(),
    }


def _norm_summary(values: np.ndarray) -> dict[str, float]:
    norms = np.linalg.norm(np.asarray(values, dtype=float), axis=-1)
    return {
        "start": float(norms[0]),
        "end": float(norms[-1]),
        "minimum": float(np.min(norms)),
        "maximum": float(np.max(norms)),
        "mean": float(np.mean(norms)),
    }


def _index_at(time_s: np.ndarray, timestamp_s: float) -> int:
    matches = np.flatnonzero(np.isclose(time_s, timestamp_s, atol=EPSILON_S, rtol=0.0))
    if len(matches) != 1:
        raise ValueError(f"expected one sample at {timestamp_s:.3f} s, found {len(matches)}")
    return int(matches[0])


def _event_metadata(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        event
        for event in payload["events"]
        if math.isclose(event["event_timestamp_s"], EVENT_TIME_S, abs_tol=EPSILON_S)
        and "MPC_COMMAND_UPDATE" in event["labels"]
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one MPC event at {EVENT_TIME_S:.3f} s")
    event = matches[0]
    metadata = event["metadata"]
    before = np.asarray(metadata["command_wrench_before_world"], dtype=float)
    after = np.asarray(metadata["command_wrench_after_world"], dtype=float)
    torque_before = np.asarray(metadata["robot_joint_torque_before_nm"], dtype=float)
    torque_after = np.asarray(metadata["robot_joint_torque_after_nm"], dtype=float)
    return {
        "labels": event["labels"],
        "complete_0_to_20ms": event["complete_0_to_20ms"],
        "task_phase": metadata["task_phase"],
        "support_load_state": metadata["support_load_state"],
        "interface_load_state": metadata["interface_load_state"],
        "supervisor_mode": metadata["supervisor_mode"],
        "command_path": metadata["execution_state"]["command_path"],
        "mpc_status": metadata["mpc_status"],
        "safety_filter_status": metadata["safety_filter_status"],
        "phase_changed": metadata["phase_changed"],
        "context_transitions": metadata["context_transitions"],
        "command_wrench_before_world": before.tolist(),
        "command_wrench_after_world": after.tolist(),
        "command_force_step_norm_n": float(np.linalg.norm(after[:3] - before[:3])),
        "command_moment_step_norm_nm": float(np.linalg.norm(after[3:] - before[3:])),
        "robot_joint_torque_before_nm": torque_before.tolist(),
        "robot_joint_torque_after_nm": torque_after.tolist(),
        "robot_joint_torque_step_norm_nm": float(
            np.linalg.norm(torque_after - torque_before)
        ),
    }


def _prefix_comparison(trace: np.lib.npyio.NpzFile) -> dict[str, Any]:
    time_s = np.asarray(trace["time_s"], dtype=float)
    start = _index_at(time_s, EVENT_TIME_S)
    estimated = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    prediction_time = np.asarray(trace["selected_v2_prefix_prediction_time_s"], dtype=float)
    prediction_index = _index_at(prediction_time, EVENT_TIME_S)
    predicted = np.asarray(
        trace["selected_v2_prefix_acceleration_rad_s2"][prediction_index], dtype=float
    )
    margin = np.asarray(
        trace["selected_v2_prefix_acceleration_margin_rad_s2"][prediction_index],
        dtype=float,
    )
    deployable_rows = []
    truth_rows = []
    for prefix_s in PREFIX_TIMES_S:
        end = _index_at(time_s, EVENT_TIME_S + float(prefix_s))
        deployable_rows.append(
            (estimated[end, 2:] - estimated[start, 2:]) / float(prefix_s)
        )
        truth_rows.append((truth_dq[end] - truth_dq[start]) / float(prefix_s))
    deployable = np.asarray(deployable_rows)
    truth = np.asarray(truth_rows)
    limit = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
        dtype=float,
    )
    return {
        "prefix_times_ms": (PREFIX_TIMES_S * 1000.0).tolist(),
        "registered_limit_deg_s2": np.degrees(limit).tolist(),
        "mpc_predicted_cumulative_acceleration_deg_s2": np.degrees(predicted).tolist(),
        "mpc_predicted_margin_deg_s2": np.degrees(margin).tolist(),
        "deployable_realized_cumulative_acceleration_deg_s2": np.degrees(
            deployable
        ).tolist(),
        "offline_truth_cumulative_acceleration_deg_s2": np.degrees(truth).tolist(),
        "deployable_minus_prediction_deg_s2": np.degrees(
            deployable - predicted
        ).tolist(),
        "truth_minus_prediction_deg_s2": np.degrees(truth - predicted).tolist(),
        "mpc_selected_prefix_feasible": bool(
            trace["selected_v2_prefix_acceleration_feasible"][prediction_index]
        ),
        "deployable_20ms_violation": bool(np.any(np.abs(deployable[-1]) > limit)),
        "truth_20ms_violation": bool(np.any(np.abs(truth[-1]) > limit)),
    }


def _q2_decomposition(trace: np.lib.npyio.NpzFile) -> dict[str, Any]:
    time_s = np.asarray(trace["time_s"], dtype=float)
    indices = np.array(
        [_index_at(time_s, EVENT_TIME_S + float(dt)) for dt in np.r_[0.0, PREFIX_TIMES_S]]
    )
    q = np.asarray(trace["evaluation_human_q_rad"][indices], dtype=float)
    dq = np.asarray(trace["evaluation_human_dq_rad_s"][indices], dtype=float)
    qacc = np.asarray(
        trace["evaluation_only_instantaneous_acceleration_rad_s2"][indices],
        dtype=float,
    )
    deployable_cuff_tau = np.asarray(
        trace["deployable_measured_generalized_input_nm"][indices], dtype=float
    )
    contributions: dict[str, list[float]] = {
        "cuff_generalized_input": [],
        "gravity": [],
        "passive_stiffness_damping": [],
        "coriolis_coupling": [],
        "q1_q2_inertia_coupling": [],
    }
    rows: list[dict[str, Any]] = []
    residuals = []
    for timestamp, q_i, dq_i, qacc_i, deployable_tau_i in zip(
        time_s[indices], q, dq, qacc, deployable_cuff_tau, strict=True
    ):
        mass, coriolis, gravity, passive = dynamic_terms(q_i, dq_i, STAGE5_HUMAN)
        # At several saved control samples the truth qacc field and deployable
        # wrench field straddle a MuJoCo step.  Infer the same-instant external
        # generalized input from the truth equation of motion so this offline
        # decomposition closes exactly.  The deployable value remains logged
        # alongside it to expose that sampling offset.
        truth_required_cuff_tau = mass @ qacc_i + coriolis + gravity + passive
        values = {
            "cuff_generalized_input": truth_required_cuff_tau[1] / mass[1, 1],
            "gravity": -gravity[1] / mass[1, 1],
            "passive_stiffness_damping": -passive[1] / mass[1, 1],
            "coriolis_coupling": -coriolis[1] / mass[1, 1],
            "q1_q2_inertia_coupling": -mass[1, 0] * qacc_i[0] / mass[1, 1],
        }
        reconstructed = float(sum(values.values()))
        residual = float(qacc_i[1] - reconstructed)
        residuals.append(residual)
        for name, value in values.items():
            contributions[name].append(float(value))
        rows.append(
            {
                "time_s": float(timestamp),
                "truth_q1_acceleration_deg_s2": math.degrees(float(qacc_i[0])),
                "truth_q2_acceleration_deg_s2": math.degrees(float(qacc_i[1])),
                "offline_truth_required_cuff_q2_generalized_input_nm": float(
                    truth_required_cuff_tau[1]
                ),
                "deployable_saved_sample_cuff_q2_generalized_input_nm": float(
                    deployable_tau_i[1]
                ),
                "saved_sample_alignment_difference_nm": float(
                    deployable_tau_i[1] - truth_required_cuff_tau[1]
                ),
                "q2_contributions_deg_s2": {
                    name: math.degrees(value) for name, value in values.items()
                },
                "reconstructed_q2_acceleration_deg_s2": math.degrees(reconstructed),
                "balance_residual_deg_s2": math.degrees(residual),
            }
        )
    elapsed = time_s[indices] - time_s[indices[0]]
    sampled_means = {
        name: math.degrees(float(np.trapezoid(values, elapsed) / elapsed[-1]))
        for name, values in contributions.items()
    }
    truth_endpoint_mean = (
        np.asarray(trace["evaluation_human_dq_rad_s"][indices[-1]], dtype=float)[1]
        - np.asarray(trace["evaluation_human_dq_rad_s"][indices[0]], dtype=float)[1]
    ) / elapsed[-1]
    sampled_total = float(sum(sampled_means.values()))
    return {
        "equation": (
            "qdd2=(tau_cuff_2-C2-G2-P2-M21*qdd1)/M22; tau_cuff is the "
            "same-instant external generalized input required by MuJoCo truth "
            "q,dq,qdd and Human V2 dynamics"
        ),
        "sample_rows": rows,
        "trapezoidal_5ms_sampled_mean_contributions_deg_s2": sampled_means,
        "trapezoidal_5ms_sampled_sum_deg_s2": sampled_total,
        "exact_truth_endpoint_20ms_acceleration_deg_s2": math.degrees(
            float(truth_endpoint_mean)
        ),
        "maximum_instantaneous_balance_residual_deg_s2": math.degrees(
            float(np.max(np.abs(residuals)))
        ),
        "sampling_caveat": (
            "The offline instantaneous torque balance closes at each saved timestamp. "
            "The separately saved deployable cuff torque can straddle a physics "
            "step and is therefore reported but not substituted into this balance. "
            "The 5 ms trapezoidal contribution integral under-resolves the "
            "0.25 ms interface oscillation, so the endpoint dq difference is "
            "the exact realized-window total."
        ),
    }


def _trace_diagnosis(
    trace_path: Path, transition_path: Path, *, include_decomposition: bool
) -> dict[str, Any]:
    with np.load(trace_path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        window_indices = np.array(
            [_index_at(time_s, EVENT_TIME_S + float(dt)) for dt in np.r_[0.0, PREFIX_TIMES_S]]
        )
        checkpoints = []
        for timestamp in (0.0, 0.1, 0.2, 0.3, 0.32):
            if timestamp > time_s[-1] + EPSILON_S:
                continue
            index = _index_at(time_s, timestamp)
            checkpoints.append(
                {
                    "time_s": timestamp,
                    "q_truth_deg": np.degrees(
                        trace["evaluation_human_q_rad"][index]
                    ).tolist(),
                    "dq_truth_deg_s": np.degrees(
                        trace["evaluation_human_dq_rad_s"][index]
                    ).tolist(),
                    "dq_hat_deg_s": np.degrees(
                        trace["estimated_state_rad_rad_s"][index, 2:]
                    ).tolist(),
                    "cuff_force_norm_n": float(
                        np.linalg.norm(trace["physical_cuff_force_world_n"][index])
                    ),
                    "cuff_moment_norm_nm": float(
                        np.linalg.norm(trace["physical_cuff_moment_world_nm"][index])
                    ),
                    "human_generalized_input_nm": trace[
                        "deployable_measured_generalized_input_nm"
                    ][index].tolist(),
                    "command_wrench_world": trace["executed_command_wrench_world"][
                        index
                    ].tolist(),
                }
            )
        result = {
            "trace": str(trace_path.relative_to(STAGE5_ROOT)),
            "time_range_s": [float(time_s[0]), float(time_s[-1])],
            "checkpoints": checkpoints,
            "prefix_comparison": _prefix_comparison(trace),
            "window_0p300_to_0p320": {
                "cuff_force_norm_n": _norm_summary(
                    trace["physical_cuff_force_world_n"][window_indices]
                ),
                "cuff_moment_norm_nm": _norm_summary(
                    trace["physical_cuff_moment_world_nm"][window_indices]
                ),
                "human_generalized_input_nm": _jsonable_summary(
                    trace["deployable_measured_generalized_input_nm"][window_indices]
                ),
                "command_force_norm_n": _norm_summary(
                    trace["executed_command_wrench_world"][window_indices, :3]
                ),
                "command_moment_norm_nm": _norm_summary(
                    trace["executed_command_wrench_world"][window_indices, 3:]
                ),
                "interface_translation_norm_mm": {
                    key: value * 1000.0
                    for key, value in _norm_summary(
                        trace["interface_translation_human_m"][window_indices]
                    ).items()
                },
                "interface_translation_rate_norm_mm_s": {
                    key: value * 1000.0
                    for key, value in _norm_summary(
                        trace["estimated_interface_velocity_human_m_s"][window_indices]
                    ).items()
                },
                "robot_joint_torque_command_nm": _jsonable_summary(
                    trace["shadow_robot_joint_torque_command_nm"][window_indices]
                ),
            },
            "event_context": _event_metadata(transition_path),
        }
        if include_decomposition:
            result["offline_truth_q2_dynamic_decomposition"] = _q2_decomposition(trace)
        return result


def _armatures(path: Path) -> list[float]:
    root = ElementTree.parse(path).getroot()
    values = [float(joint.attrib["armature"]) for joint in root.iter("joint") if "armature" in joint.attrib]
    if not values:
        raise ValueError(f"no armature values in {path}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cr12-dir",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_split_authority_baseline_attempt_03/execution",
    )
    parser.add_argument(
        "--ur10e-dir",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_event_diagnosis_attempt_01/ur10e_matched",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_event_diagnosis_attempt_01/event_diagnosis.json",
    )
    parser.add_argument(
        "--physics-summary",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_event_diagnosis_attempt_01/cr12_physics_resolution_v4/physics_summary.json"
        ),
    )
    parser.add_argument(
        "--ur10e-physics-summary",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/cr12_event_diagnosis_attempt_01/ur10e_physics_resolution_v3/physics_summary.json"
        ),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    cr12_dir = args.cr12_dir.resolve()
    ur10e_dir = args.ur10e_dir.resolve()
    cr12 = _trace_diagnosis(
        cr12_dir / "trace.npz",
        cr12_dir / "transition_response_shadow_v2.json",
        include_decomposition=False,
    )
    ur10e = _trace_diagnosis(
        ur10e_dir / "trace.npz",
        ur10e_dir / "transition_response_shadow_v2.json",
        include_decomposition=False,
    )
    physics_summary = json.loads(
        args.physics_summary.resolve().read_text(encoding="utf-8")
    )
    ur10e_physics_summary = json.loads(
        args.ur10e_physics_summary.resolve().read_text(encoding="utf-8")
    )
    cr12["offline_truth_q2_dynamic_decomposition"] = physics_summary
    ur10e["offline_truth_q2_dynamic_decomposition"] = ur10e_physics_summary
    cr12_initial = cr12["checkpoints"][0]
    ur10e_initial = ur10e["checkpoints"][0]
    cr12_20 = np.asarray(
        cr12["prefix_comparison"]["deployable_realized_cumulative_acceleration_deg_s2"][-1]
    )
    ur10e_20 = np.asarray(
        ur10e["prefix_comparison"]["deployable_realized_cumulative_acceleration_deg_s2"][-1]
    )
    cr12_armatures = _armatures(STAGE5_ROOT / "models/cr12_v0.xml")
    ur10e_armatures = _armatures(
        STAGE5_ROOT.parent / "stage3_full3d/models/ur10e_torque.xml"
    )
    result = {
        "schema": "stage5_cr12_early_acceleration_event_diagnosis_v1",
        "evidence_category": "focused_offline_engineering_diagnosis",
        "event_window_s": [EVENT_TIME_S, EVENT_TIME_S + PREFIX_TIMES_S[-1]],
        "cr12": cr12,
        "ur10e_matched": ur10e,
        "matched_comparison": {
            "initial_q_truth_equal": bool(
                np.allclose(cr12_initial["q_truth_deg"], ur10e_initial["q_truth_deg"])
            ),
            "initial_dq_truth_equal": bool(
                np.allclose(cr12_initial["dq_truth_deg_s"], ur10e_initial["dq_truth_deg_s"])
            ),
            "initial_cuff_force_norm_difference_n": float(
                cr12_initial["cuff_force_norm_n"] - ur10e_initial["cuff_force_norm_n"]
            ),
            "initial_cuff_moment_norm_difference_nm": float(
                cr12_initial["cuff_moment_norm_nm"] - ur10e_initial["cuff_moment_norm_nm"]
            ),
            "cr12_minus_ur10e_deployable_20ms_acceleration_deg_s2": (
                cr12_20 - ur10e_20
            ).tolist(),
            "cr12_bed_contact_q2_mean_contribution_deg_s2": physics_summary[
                "q2_mean_contributions_deg_s2"
            ]["bed_contact_constraint"],
            "ur10e_bed_contact_q2_mean_contribution_deg_s2": ur10e_physics_summary[
                "q2_mean_contributions_deg_s2"
            ]["bed_contact_constraint"],
            "cr12_bed_contact_active_intervals_of_80": physics_summary[
                "human_constraint_activity"
            ]["active_physics_interval_count_event_window"],
            "ur10e_bed_contact_active_intervals_of_80": ur10e_physics_summary[
                "human_constraint_activity"
            ]["active_physics_interval_count_event_window"],
            "interpretation": (
                "The robot is the changed plant. Closed-loop state and commands "
                "therefore diverge after the identical loaded initial condition."
            ),
        },
        "startup_and_armature_audit": {
            "loaded_initial_condition_equal": True,
            "cr12_initial_0p1s_below_registered_acceleration_limit": True,
            "event_is_first_command_transition": False,
            "mpc_command_update_count_before_event_inclusive": 16,
            "event_has_support_load_or_task_phase_transition": False,
            "cr12_armature_kg_m2": cr12_armatures,
            "ur10e_armature_kg_m2": ur10e_armatures,
            "armature_value_is_robot_differentiator": sorted(set(cr12_armatures))
            != sorted(set(ur10e_armatures)),
            "cr12_armature_is_official_hardware_parameter": False,
            "zero_armature_diagnostic": {
                "completed": False,
                "failure_time_s": 0.0045,
                "mujoco_warning": "Nan, Inf or huge value in QACC at DOF 7",
                "interpretation": (
                    "Removing regularization is numerically unstable and does not "
                    "isolate armature as the cause of the 0.320 s event."
                ),
            },
        },
        "mpc_semantics": {
            "main_horizon_constraint": "successive predicted dq differences over 20 ms",
            "selected_first_action_constraint": (
                "cumulative predicted dq change from the observation at 5/10/15/20 ms"
            ),
            "authority_constraint": "causal realized dq_hat change over the full trailing 20 ms",
            "same_20ms_motion_quantity": True,
            "perfect_time_orientation_match": False,
            "time_orientation_note": (
                "MPC screens a forward 20 ms prediction at 0.300 s; authority "
                "later evaluates the realized causal window ending at 0.320 s."
            ),
            "safe_action_reason": (
                "The selected CR12 prefix prediction remained inside both joint "
                "limits, so the prediction-based feasibility result was SAFE_ACTION."
            ),
            "prediction_underestimates_or_mis-signs_realized_q2": True,
            "identified_missing_execution_term": (
                "intended Human-bed contact constraint response is present in "
                "MuJoCo execution but absent from the planar MPC Human dynamics"
            ),
        },
        "primary_cause": (
            "ED-B — MPC SEMANTICS MATCH, BUT MODEL/EXECUTION PREDICTION UNDERESTIMATES MOTION"
        ),
        "exactly_one_next_implementation": (
            "Replace the shared first-20-ms execution prefix recurrence with a "
            "CR12-specific closed-loop actuator/robot/cuff response predictor, "
            "while retaining the existing 5/10/15/20-ms constraint and limits."
        ),
        "authority_changed": False,
        "threshold_changed": False,
        "controller_parameter_changed": False,
        "scientific_parameter_changed": False,
    }
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
