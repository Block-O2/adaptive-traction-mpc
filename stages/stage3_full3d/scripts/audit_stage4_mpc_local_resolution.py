#!/usr/bin/env python3
"""Audit smooth local action perturbations around saved Stage-4 MPC optima."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, HIP_HEIGHT_M
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import (
    DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG,
)
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
)
from traction_mpc_stage4.mpc import INTERACTION_AWARE_MPC_CONFIG, HumanSpaceMPC
from traction_mpc_stage4.mpc_local_resolution_audit import (
    evaluate_local_sequence,
    structured_perturbations,
    summarize_local_landscape,
)
from traction_mpc_stage4.reference import continuous_teaching_reference


def _estimated_model(trace: dict[str, np.ndarray], trace_index: int) -> BaseParameterHumanModel:
    vector = np.asarray(trace["geometry_estimate"][trace_index], dtype=float)
    axis = vector[5:8].copy()
    axis /= np.linalg.norm(axis)
    prior_x = np.array([1.0, 0.0, 0.0])
    plane_x = prior_x - axis * float(axis @ prior_x)
    plane_x /= np.linalg.norm(plane_x)
    plane_z = np.cross(plane_x, axis)
    plane_z /= np.linalg.norm(plane_z)
    geometry = PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=plane_x,
        joint_axis_world=axis,
        plane_z_world=plane_z,
        hip_plane_m=vector[:2].copy(),
        thigh_length_m=float(vector[2]),
        knee_to_cuff_in_cuff_m=vector[3:5].copy(),
    )
    return BaseParameterHumanModel(
        geometry=geometry,
        beta=np.asarray(trace["dynamic_base_estimate"][trace_index], dtype=float).copy(),
    )


def _saved_timewarp_reference(
    trace: dict[str, np.ndarray],
) -> Callable[[float], CuffPoseReference]:
    time = np.asarray(trace["time_s"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    speed = np.asarray(trace["reference_speed_scale"], dtype=float)
    speed_rate = np.asarray(trace["reference_speed_scale_rate_per_s"], dtype=float)

    def reference(wall_time_s: float) -> CuffPoseReference:
        query = float(wall_time_s)
        phase_now = float(np.interp(query, time, phase))
        speed_now = float(np.interp(query, time, speed))
        speed_rate_now = float(np.interp(query, time, speed_rate))
        base = continuous_teaching_reference(phase_now)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=speed_now * base.dq_rad_s,
            ddq_rad_s2=(
                speed_now**2 * base.ddq_rad_s2
                + speed_rate_now * base.dq_rad_s
            ),
            world_from_cuff=base.world_from_cuff,
        )

    return reference


def _trace_index_after_call(time: np.ndarray, wall_time_s: float) -> int:
    return min(int(np.searchsorted(time, wall_time_s + 0.5e-3)), len(time) - 1)


def _capture_registered_sequences(
    trace: dict[str, np.ndarray], representatives: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    selected = {int(item["solve_index"]): item for item in representatives}
    controller = HumanSpaceMPC(INTERACTION_AWARE_MPC_CONFIG)
    reference = _saved_timewarp_reference(trace)
    control_time = np.asarray(trace["control_time_s"])
    control_state = np.asarray(trace["control_estimated_state"])
    trace_time = np.asarray(trace["time_s"])
    stored_action = np.asarray(trace["desired_human_action_nm"])
    stride = int(round(controller.config.prediction_dt_s / CONTROL_DT_S))
    captured: list[dict[str, Any]] = []
    replay_errors: list[float] = []
    for solve_index in range(max(selected) + 1):
        control_index = solve_index * stride
        wall_time = float(control_time[control_index])
        trace_index = _trace_index_after_call(trace_time, wall_time)
        state = np.asarray(control_state[control_index]).copy()
        model = _estimated_model(trace, trace_index)
        previous_action = controller.last_action.copy()
        action, _ = controller.solve(state, wall_time, reference, model)
        replay_errors.append(float(np.linalg.norm(action - stored_action[trace_index])))
        if solve_index in selected:
            q_ref, dq_ref, _ = controller._reference_arrays(wall_time, reference)
            captured.append(
                {
                    **selected[solve_index],
                    "state": state,
                    "model": model,
                    "previous_action_nm": previous_action,
                    "registered_sequence_nm": controller.last_sequence.copy(),
                    "q_ref": q_ref,
                    "dq_ref": dq_ref,
                }
            )
    return captured, {
        "compared_call_count": len(replay_errors),
        "rms_action_replay_error_nm": float(
            np.sqrt(np.mean(np.asarray(replay_errors) ** 2))
        ),
        "maximum_action_replay_error_nm": float(np.max(replay_errors)),
    }


def _jsonable_local_record(
    perturbation: dict[str, Any], evaluation: dict[str, Any], sequence: np.ndarray
) -> dict[str, Any]:
    return {
        "method": perturbation["method"],
        "coefficients": perturbation["coefficients"],
        "maximum_abs_delta_per_joint_nm": perturbation[
            "maximum_abs_delta_per_joint_nm"
        ],
        "rms_delta_nm": perturbation["rms_delta_nm"],
        "first_generalized_torque_nm": np.asarray(sequence[0]).tolist(),
        **evaluation,
    }


def _write_summary(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Stage 4 local MPC optimizer-resolution audit",
        "",
        "Offline saved-context replay only. No controller, CEM, estimator, allocator, or safety change.",
        "",
        "`A_dagger w` is a minimum-norm cylindrical surface-load proxy, not pressure.",
        "",
        "| phase | neighborhood | local candidates | interaction change | force RMS change | moment RMS change | surface RMS change |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for call in result["calls"]:
        for name, neighborhood in call["landscape"]["neighborhoods"].items():
            best = neighborhood["minimum_interaction_cost_candidate"]
            change = best["relative_change_vs_registered_sequence"]
            lines.append(
                f'| {call["reference_phase_s"]:.3f} s | {name} | '
                f'{neighborhood["candidate_count"]} | '
                f'{100.0 * change["interaction_cost"]:+.3f}% | '
                f'{100.0 * change["force_rms"]:+.3f}% | '
                f'{100.0 * change["moment_rms"]:+.3f}% | '
                f'{100.0 * change["surface_proxy_rms"]:+.3f}% |'
            )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--cem-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    with np.load(args.trace) as stored:
        trace = {name: stored[name] for name in stored.files}
    cem_audit = json.loads(args.cem_audit.read_text(encoding="utf-8"))
    representatives = cem_audit["representative_calls"]
    contexts, replay = _capture_registered_sequences(trace, representatives)
    perturbations = structured_perturbations(
        INTERACTION_AWARE_MPC_CONFIG.horizon_steps,
        INTERACTION_AWARE_MPC_CONFIG.exploration_std_floor_nm,
    )
    calls: list[dict[str, Any]] = []
    for context in contexts:
        evaluator = HumanSpaceMPC(INTERACTION_AWARE_MPC_CONFIG)
        records: list[dict[str, Any]] = []
        for perturbation in perturbations:
            sequence = (
                context["registered_sequence_nm"] + perturbation["delta_u_nm"]
            )
            evaluation = evaluate_local_sequence(
                evaluator,
                state=context["state"],
                sequence=sequence,
                previous_action=context["previous_action_nm"],
                q_ref=context["q_ref"],
                dq_ref=context["dq_ref"],
                human=context["model"],
            )
            records.append(
                _jsonable_local_record(perturbation, evaluation, sequence)
            )
        calls.append(
            {
                "solve_index": context["solve_index"],
                "wall_time_s": context["wall_time_s"],
                "reference_phase_s": context["reference_phase_s"],
                "labels": context["labels"],
                "registered_sequence_nm": context["registered_sequence_nm"].tolist(),
                "previous_action_nm": context["previous_action_nm"].tolist(),
                "landscape": summarize_local_landscape(records),
                "all_local_candidates": records,
            }
        )
    prior_calls = cem_audit["modes"]["registered_interaction_objective"]["calls"]
    result = {
        "evidence_category": "stage4_mpc_local_optimizer_resolution_audit",
        "formal_experiment": False,
        "source": {
            "trace": str(args.trace),
            "previous_cem_candidate_audit": str(args.cem_audit),
            "trajectory": "existing_registered_continuous_high_flexion",
            "human": "registered_cold_start_perturbed",
            "plant_rerun": False,
            "estimator_rerun": False,
            "saved_context_replay_validation": replay,
        },
        "method": {
            "local_envelope_nm_per_action_element": list(
                INTERACTION_AWARE_MPC_CONFIG.exploration_std_floor_nm
            ),
            "local_envelope_over_initial_cem_standard_deviation": [0.1, 0.1],
            "temporal_basis": ["constant", "linear", "quadratic", "cubic"],
            "structured_combinations": [
                "single_direction_dense_sweeps",
                "same_order_cross_joint_pairs",
                "adjacent_order_same_joint_pairs",
                "mixed_half_envelope_direction_pairs",
            ],
            "principal_cem_covariance_directions_used": False,
            "principal_cem_covariance_directions_reason": (
                "saved production diagnostics do not retain elite covariance; "
                "the configured CEM covariance is diagonal and its coordinate "
                "directions are not smooth whole-horizon modes"
            ),
            "relative_cost_neighborhoods_are_reporting_slices_not_acceptance_thresholds": True,
        },
        "frozen_allocator": DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG.as_dict(),
        "unchanged_mpc_objective": INTERACTION_AWARE_MPC_CONFIG.objective_contract(),
        "previous_cem_resolution": [
            {
                "solve_index": item["solve_index"],
                "reference_phase_s": item["reference_phase_s"],
                "sampled_candidate_count": item["sampled_candidate_count"],
                "feasible_candidate_count": item["feasible_candidate_count"],
                "candidate_counts_in_tracking_neighborhoods": {
                    name: item["tracking_bands"][name]["candidate_count"]
                    for name in (
                        "1_percent",
                        "2_percent",
                        "5_percent",
                        "10_percent",
                    )
                },
            }
            for item in prior_calls
        ],
        "calls": calls,
        "scientific_settings_changed": False,
        "controller_changed": False,
        "cem_changed": False,
        "estimator_changed": False,
        "allocator_changed": False,
        "safety_limits_changed": False,
        "tracking_corridor_or_tube_added": False,
    }
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_summary(args.output_dir, result)


if __name__ == "__main__":
    main()
