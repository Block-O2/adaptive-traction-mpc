#!/usr/bin/env python3
"""Run one registered Adaptive-MPC interaction-objective engineering A/B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.human_model import (
    dynamic_terms,
    registered_cold_start_perturbed_human,
)
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.mpc import (
    INTERACTION_AWARE_MPC_CONFIG,
    HumanMPCConfig,
    HumanSpaceMPC,
)
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)


ROLLOUT_DURATION_S = 32.0
REGISTERED_MODES = {
    "current_adaptive_mpc": HumanMPCConfig(),
    "interaction_aware_adaptive_mpc": INTERACTION_AWARE_MPC_CONFIG,
}


def _first_phase_completion(time: np.ndarray, phase: np.ndarray) -> float | None:
    selected = np.flatnonzero(
        phase >= CONTINUOUS_TEACHING_DURATION_S - 1e-9
    )
    return None if not len(selected) else float(time[selected[0]])


def _peak(signal: np.ndarray, time: np.ndarray, phase: np.ndarray) -> dict[str, float]:
    index = int(np.argmax(signal))
    return {
        "value": float(signal[index]),
        "wall_time_s": float(time[index]),
        "reference_phase_s": float(phase[index]),
    }


def _estimator_trust(summary: dict[str, Any], time: np.ndarray, phase: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("geometry", "dynamic"):
        trusted_time = summary[f"{name}_identifier"]["trustworthy_time_s"]
        result[name] = {
            "wall_time_s": trusted_time,
            "reference_phase_s": (
                None
                if trusted_time is None
                else float(np.interp(float(trusted_time), time, phase))
            ),
            "accepted_updates": summary[f"{name}_identifier"]["accepted_updates"],
            "rejected_updates": summary[f"{name}_identifier"]["rejected_updates"],
        }
    result["dynamic_base_torque_prediction_combined_rmse_nm"] = summary[
        "dynamic_identifier"
    ]["god_view_base_model_torque_prediction_combined_rmse_nm"]
    return result


def _allocated_wrench_slew(
    wrench_world: np.ndarray, radius_m: float, control_dt_s: float
) -> dict[str, Any]:
    # The trace is sampled at the 1 ms plant step while MPC updates at 20 ms.
    # Sample once per MPC period so repeated commands and floating-point trace
    # noise are not counted as additional command updates.
    plant_trace_dt_s = 0.001
    stride = int(round(control_dt_s / plant_trace_dt_s))
    sampled = np.asarray(wrench_world)[::stride]
    delta = np.diff(sampled, axis=0)
    force_equivalent = np.sqrt(
        np.sum(delta[:, :3] ** 2, axis=1)
        + np.sum(delta[:, 3:] ** 2, axis=1) / radius_m**2
    )
    updates = force_equivalent if len(force_equivalent) else np.zeros(1)
    rate = updates / control_dt_s
    return {
        "update_count": int(len(force_equivalent)),
        "peak_force_equivalent_step": float(np.max(updates)),
        "rms_force_equivalent_step": float(np.sqrt(np.mean(updates**2))),
        "peak_force_equivalent_rate_per_s": float(np.max(rate)),
        "rms_force_equivalent_rate_per_s": float(np.sqrt(np.mean(rate**2))),
        "metric": "sqrt(||delta_F_world||^2 + ||delta_M_world/r_cuff||^2)",
    }


def _comparison_row(
    mode: str,
    config: HumanMPCConfig,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    surface_model: CylindricalSurfaceLoadModel,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    tracking = np.asarray(trace["tracking_error_deg_god_view"])
    wrench_cuff = np.asarray(trace["cuff_wrench_local_god_view"])
    force_norm = np.linalg.norm(wrench_cuff[:, :3], axis=1)
    moment_norm = np.linalg.norm(wrench_cuff[:, 3:], axis=1)
    equivalent_load = wrench_cuff @ surface_model.minimum_norm_operator.T
    equivalent_effort = np.linalg.norm(equivalent_load, axis=1)
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    robot = summary["robot"]
    return {
        "mode": mode,
        "interaction_aware": config.interaction_aware,
        "termination": summary["termination_reason"],
        "mechanically_completed_requested_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "reference_completion_time_s": _first_phase_completion(time, phase),
        "final_reference_phase_s": float(phase[-1]),
        "tracking": {
            "combined_rmse_deg": float(np.sqrt(np.mean(tracking**2))),
            "per_joint_rmse_deg": np.sqrt(np.mean(tracking**2, axis=0)).tolist(),
            "per_joint_max_abs_error_deg": np.max(np.abs(tracking), axis=0).tolist(),
            "combined_max_abs_error_deg": float(np.max(np.abs(tracking))),
        },
        "cuff_force": {
            "peak": _peak(force_norm, time, phase),
            "rms_n": float(np.sqrt(np.mean(force_norm**2))),
        },
        "cuff_moment": {
            "peak": _peak(moment_norm, time, phase),
            "rms_nm": float(np.sqrt(np.mean(moment_norm**2))),
        },
        "equivalent_cylindrical_surface_load": {
            "peak_effort_n": float(np.max(equivalent_effort)),
            "rms_effort_n": float(np.sqrt(np.mean(equivalent_effort**2))),
            "peak_wall_time_s": float(time[int(np.argmax(equivalent_effort))]),
            "peak_reference_phase_s": float(
                phase[int(np.argmax(equivalent_effort))]
            ),
            "definition": "||A_dagger*w_cuff||_2",
            "interpretation": (
                "minimum-norm equivalent cylindrical surface-load effort proxy; "
                "not real pressure"
            ),
        },
        "wrench_slew_and_rate": {
            "allocated_wrench": _allocated_wrench_slew(
                np.asarray(trace["allocated_wrench_world"]),
                surface_model.config.radius_m,
                config.prediction_dt_s,
            ),
            "measured_force_rate_peak_n_s": interaction["peak_force_rate_n_s"],
            "measured_force_rate_rms_n_s": interaction["rms_force_rate_n_s"],
            "measured_moment_rate_peak_nm_s": interaction[
                "peak_moment_rate_nm_s"
            ],
            "measured_moment_rate_rms_nm_s": interaction[
                "rms_moment_rate_nm_s"
            ],
        },
        "robot": {
            "peak_abs_commanded_joint_torque_nm": robot[
                "peak_abs_commanded_joint_torque_nm"
            ],
            "rms_commanded_joint_torque_nm": robot[
                "rms_commanded_joint_torque_nm"
            ],
            "peak_abs_joint_velocity_deg_s": robot[
                "peak_abs_joint_velocity_deg_s"
            ],
            "rms_joint_velocity_deg_s": robot["rms_joint_velocity_deg_s"],
            "peak_unclipped_torque_limit_fraction": robot[
                "peak_unclipped_torque_limit_fraction"
            ],
            "torque_saturation_control_samples": robot[
                "torque_saturation_control_samples"
            ],
        },
        "estimator": _estimator_trust(summary, time, phase),
        "safety_events": summary["events"],
        "force_gate_n": summary["force_gate_n"],
        "moment_limit_nm": summary["moment_limit_nm"],
        "mpc_objective": config.objective_contract(),
    }


def _current_mpc_peak_audit(
    trace: dict[str, np.ndarray], surface_model: CylindricalSurfaceLoadModel
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    wrench = np.asarray(trace["cuff_wrench_local_god_view"])
    force_norm = np.linalg.norm(wrench[:, :3], axis=1)
    index = int(np.argmax(force_norm))
    q = np.radians(np.asarray(trace["human_q_deg_god_view"]))
    dq = np.gradient(q, time, axis=0)
    ddq = np.gradient(dq, time, axis=0)
    human, metadata = registered_cold_start_perturbed_human()
    mass, coriolis, gravity, passive = dynamic_terms(q[index], dq[index], human)
    inertia = mass @ ddq[index]
    desired_action = np.asarray(trace["desired_human_action_nm"])[index]
    allocated = np.asarray(trace["allocated_wrench_world"])[index]
    equivalent = surface_model.minimum_norm_operator @ wrench[index]
    return {
        "peak_force_wall_time_s": float(time[index]),
        "peak_force_reference_phase_s": float(phase[index]),
        "registered_human": metadata,
        "true_dynamics_generalized_torque_breakdown_nm": {
            "inertia": inertia.tolist(),
            "coriolis": coriolis.tolist(),
            "gravity": gravity.tolist(),
            "passive_stiffness_damping_and_soft_limit": passive.tolist(),
            "sum": (inertia + coriolis + gravity + passive).tolist(),
        },
        "mpc_desired_generalized_action_nm": desired_action.tolist(),
        "desired_action_common_mode_nm": float(
            np.array([1.0, 1.0]) @ desired_action / np.sqrt(2.0)
        ),
        "desired_action_differential_mode_nm": float(
            np.array([1.0, -1.0]) @ desired_action / np.sqrt(2.0)
        ),
        "allocated_wrench_world": allocated.tolist(),
        "allocated_resultant_force_n": float(np.linalg.norm(allocated[:3])),
        "allocated_resultant_moment_nm": float(np.linalg.norm(allocated[3:])),
        "measured_resultant_force_n": float(force_norm[index]),
        "measured_resultant_moment_nm": float(np.linalg.norm(wrench[index, 3:])),
        "measured_equivalent_cylindrical_surface_effort_n": float(
            np.linalg.norm(equivalent)
        ),
        "allocation_explanation": (
            "rigid-cuff minimum-force allocation maps generalized-action common mode "
            "primarily to translation and differential mode to free sagittal moment"
        ),
    }


def _write_summary(output_dir: Path, comparison: dict[str, Any]) -> None:
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 interaction-aware Adaptive MPC engineering comparison",
        "",
        "One registered A/B only. No post-result tuning was performed.",
        "",
        "`||A_dagger w||` is a minimum-norm equivalent cylindrical surface-load effort proxy, not pressure.",
        "",
        "| mode | complete time | tracking RMSE / max | force peak / RMS | moment peak / RMS | surface effort peak / RMS | force-rate peak / RMS |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["rows"]:
        completion = row["reference_completion_time_s"]
        lines.append(
            f'| {row["mode"]} | '
            f'{"-" if completion is None else f"{completion:.3f} s"} | '
            f'{row["tracking"]["combined_rmse_deg"]:.3f} / '
            f'{row["tracking"]["combined_max_abs_error_deg"]:.3f} deg | '
            f'{row["cuff_force"]["peak"]["value"]:.2f} / '
            f'{row["cuff_force"]["rms_n"]:.2f} N | '
            f'{row["cuff_moment"]["peak"]["value"]:.2f} / '
            f'{row["cuff_moment"]["rms_nm"]:.2f} Nm | '
            f'{row["equivalent_cylindrical_surface_load"]["peak_effort_n"]:.2f} / '
            f'{row["equivalent_cylindrical_surface_load"]["rms_effort_n"]:.2f} N | '
            f'{row["wrench_slew_and_rate"]["measured_force_rate_peak_n_s"]:.1f} / '
            f'{row["wrench_slew_and_rate"]["measured_force_rate_rms_n_s"]:.1f} N/s |'
        )
    (output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="recompute reporting metrics without rerunning rollouts",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and not args.summarize_existing:
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")

    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    ideal_case = sensor_realism_cases()[0]
    rows: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    for mode, config in REGISTERED_MODES.items():
        if args.summarize_existing:
            summary = json.loads((args.output_dir / f"{mode}.json").read_text())
            with np.load(args.output_dir / f"{mode}_trace.npz") as stored:
                trace = {name: stored[name] for name in stored.files}
        else:
            execution = ReferenceExecutionLayer(
                continuous_teaching_reference, confidence_aware=True
            )
            summary, trace = run_sensor_realism_case(
                ideal_case,
                duration_s=ROLLOUT_DURATION_S,
                estimator_architecture="integral_minimal",
                result_case_name=mode,
                reference_fn=continuous_teaching_reference,
                trajectory_label="stage4_registered_continuous_high_flexion_23s",
                trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
                reference_execution=execution,
                mpc_factory=lambda config=config: HumanSpaceMPC(config),
            )
            save_sensor_case(args.output_dir, summary, trace)
        traces[mode] = trace
        rows.append(_comparison_row(mode, config, summary, trace, surface_model))

    if rows[0]["force_gate_n"] != rows[1]["force_gate_n"]:
        raise RuntimeError("A/B changed the force safety limit")
    if rows[0]["moment_limit_nm"] != rows[1]["moment_limit_nm"]:
        raise RuntimeError("A/B changed the moment safety limit")
    comparison = {
        "evidence_category": "stage4_interaction_aware_mpc_engineering_ab",
        "formal_experiment": False,
        "single_variable": "mpc_interaction_objective_terms",
        "shared": {
            "true_human": "registered_cold_start_perturbed",
            "trajectory": "stage4_registered_continuous_high_flexion_23s",
            "rollout_duration_s": ROLLOUT_DURATION_S,
            "measurement_case": "ideal_200hz",
            "estimator": "validated_integral_minimal_unchanged",
            "confidence_pacing": "split_confidence_execution_unchanged",
            "plant": "validated_rigid_cuff_unchanged",
            "safety_limits_changed": False,
        },
        "constraints": {
            "human_rom": "unchanged q_min <= q <= q_max",
            "resultant_force_gate_n": rows[0]["force_gate_n"],
            "moment_limit_nm": rows[0]["moment_limit_nm"],
            "new_constraints": [],
            "post_hoc_filter": False,
        },
        "registered_interaction_objective": (
            INTERACTION_AWARE_MPC_CONFIG.objective_contract()
        ),
        "current_mpc_peak_driver_audit": _current_mpc_peak_audit(
            traces["current_adaptive_mpc"], surface_model
        ),
        "rows": rows,
    }
    _write_summary(args.output_dir, comparison)


if __name__ == "__main__":
    main()
