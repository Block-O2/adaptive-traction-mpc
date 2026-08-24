"""Engineering gates for the Stage-3C rigid-cuff integration."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    CuffForceCommandLimitError,
    CoupledObservation,
    CoupledUR10eHumanV2,
    human_cuff_velocity,
)
from .human import CUFF_TRANSLATIONAL_FORCE_GATE_N, nominal_tracking_wrench
from .reference import stage2_cuff_pose_reference


def _finite_observation(observation: CoupledObservation) -> bool:
    arrays = (
        observation.human_q_rad,
        observation.human_dq_rad_s,
        observation.robot_q_rad,
        observation.robot_dq_rad_s,
        observation.cuff_force_vector_n,
        observation.cuff_moment_vector_nm,
        observation.joint_torque_command_nm,
    )
    return all(np.all(np.isfinite(value)) for value in arrays)


def run_coupled_scenario(
    *,
    lower_q2_deg: float,
    duration_s: float,
    hold_only: bool,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run one explicitly bounded engineering smoke scenario."""

    plant = CoupledUR10eHumanV2()
    initial_reference = stage2_cuff_pose_reference(0.0, lower_q2_deg=lower_q2_deg)
    initial = plant.reset(initial_reference.q_rad)
    observations = [initial]
    references = [initial_reference.q_rad.copy()]
    allocated_forces = []
    allocated_my = []
    required_torque = []
    termination = "completed_hold" if hold_only else "completed_requested_duration"
    requested_control_steps = int(round(duration_s / CONTROL_DT_S))
    peak_force = float(np.linalg.norm(initial.cuff_force_vector_n))
    peak_moment = float(np.linalg.norm(initial.cuff_moment_vector_nm))
    peak_abs_my = abs(float(initial.cuff_moment_vector_nm[1]))
    peak_weld_position = initial.weld_position_error_m
    peak_weld_rotation = initial.weld_rotation_error_rad
    peak_bed_force = initial.bed_force_n
    peak_bed_penetration = initial.bed_penetration_m
    peak_wrench_residual = initial.cuff_wrench_reconstruction_residual_nm
    peak_human_tau_residual = initial.human_wrench_torque_residual_nm
    peak_torque_fraction = 0.0
    torque_saturation_samples = 0
    peak_robot_velocity = np.abs(initial.robot_dq_rad_s)
    initial_singular_values = np.linalg.svd(
        plant.robot_attachment_jacobian(), compute_uv=False
    )
    minimum_jacobian_singular_value = float(initial_singular_values[-1])
    worst_jacobian_condition_number = float(
        initial_singular_values[0] / initial_singular_values[-1]
    )
    unintended_contacts: set[tuple[str, str]] = set(initial.unintended_contact_pairs)
    physical_samples = 1
    bed_force_samples = [initial.bed_force_n]
    first_50ms_peak_force = peak_force
    first_50ms_peak_human_speed = float(np.max(np.abs(initial.human_dq_rad_s)))

    for _ in range(requested_control_steps):
        reference = (
            initial_reference
            if hold_only
            else stage2_cuff_pose_reference(
                float(plant.data.time), lower_q2_deg=lower_q2_deg
            )
        )
        current = plant.observe()
        allocation = nominal_tracking_wrench(
            current.human_q_rad,
            current.human_dq_rad_s,
            reference,
        )
        allocated_forces.append(float(allocation["force_norm_n"]))
        allocated_my.append(float(allocation["my_nm"]))
        required_torque.append(np.asarray(allocation["tau_required_nm"]).copy())
        if float(allocation["force_norm_n"]) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            termination = "allocated_cuff_force_gate"
            break
        target_linear_velocity, target_angular_velocity = human_cuff_velocity(
            reference.q_rad, reference.dq_rad_s
        )
        try:
            plant.apply_nominal_cartesian_control(
                reference.world_from_cuff.translation,
                target_linear_velocity,
                reference.world_from_cuff.rotation,
                target_angular_velocity,
                np.asarray(allocation["wrench_world"]),
            )
        except CuffForceCommandLimitError:
            termination = "total_commanded_cuff_force_gate"
            break

        limits = plant.torque_limits_nm
        unclipped_fraction = float(
            np.max(np.abs(plant.last_unclipped_joint_torque) / limits)
        )
        peak_torque_fraction = max(peak_torque_fraction, unclipped_fraction)
        torque_saturation_samples += int(unclipped_fraction >= 1.0 - 1e-9)
        for _ in range(CONTROL_SUBSTEPS):
            observation = plant.step()
            physical_samples += 1
            force_norm = float(np.linalg.norm(observation.cuff_force_vector_n))
            moment_norm = float(np.linalg.norm(observation.cuff_moment_vector_nm))
            peak_force = max(peak_force, force_norm)
            peak_moment = max(peak_moment, moment_norm)
            peak_abs_my = max(peak_abs_my, abs(float(observation.cuff_moment_vector_nm[1])))
            peak_weld_position = max(peak_weld_position, observation.weld_position_error_m)
            peak_weld_rotation = max(peak_weld_rotation, observation.weld_rotation_error_rad)
            peak_bed_force = max(peak_bed_force, observation.bed_force_n)
            peak_bed_penetration = max(peak_bed_penetration, observation.bed_penetration_m)
            peak_wrench_residual = max(
                peak_wrench_residual,
                observation.cuff_wrench_reconstruction_residual_nm,
            )
            peak_human_tau_residual = max(
                peak_human_tau_residual,
                observation.human_wrench_torque_residual_nm,
            )
            peak_robot_velocity = np.maximum(
                peak_robot_velocity, np.abs(observation.robot_dq_rad_s)
            )
            singular_values = np.linalg.svd(
                plant.robot_attachment_jacobian(), compute_uv=False
            )
            minimum_jacobian_singular_value = min(
                minimum_jacobian_singular_value, float(singular_values[-1])
            )
            worst_jacobian_condition_number = max(
                worst_jacobian_condition_number,
                float(singular_values[0] / singular_values[-1]),
            )
            unintended_contacts.update(observation.unintended_contact_pairs)
            bed_force_samples.append(observation.bed_force_n)
            if observation.time_s <= 0.050 + 1e-12:
                first_50ms_peak_force = max(first_50ms_peak_force, force_norm)
                first_50ms_peak_human_speed = max(
                    first_50ms_peak_human_speed,
                    float(np.max(np.abs(observation.human_dq_rad_s))),
                )
            if not _finite_observation(observation):
                termination = "nonfinite_state_or_wrench"
                break
            if plant.warning_counts():
                termination = "mujoco_solver_warning"
                break
            if force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
                termination = "physical_cuff_translational_force_gate"
                break
        observations.append(observation)
        logged_reference = (
            initial_reference
            if hold_only
            else stage2_cuff_pose_reference(
                float(observation.time_s), lower_q2_deg=lower_q2_deg
            )
        )
        references.append(logged_reference.q_rad.copy())
        if termination not in {"completed_hold", "completed_requested_duration"}:
            break

    time = np.array([item.time_s for item in observations])
    q = np.array([item.human_q_rad for item in observations])
    dq = np.array([item.human_dq_rad_s for item in observations])
    q_ref = np.array(references)
    tracking_error_deg = np.degrees(q - q_ref)
    robot_torque = np.array([item.joint_torque_command_nm for item in observations])
    cuff_force = np.array([item.cuff_force_vector_n for item in observations])
    cuff_moment = np.array([item.cuff_moment_vector_nm for item in observations])
    bed_force = np.asarray(bed_force_samples)
    completed = bool(
        termination in {"completed_hold", "completed_requested_duration"}
        and time[-1] >= duration_s - 0.5 * CONTROL_DT_S
    )
    rom_min = np.degrees(np.asarray(plant.human.q_min_rad))
    rom_max = np.degrees(np.asarray(plant.human.q_max_rad))
    q_deg = np.degrees(q)
    rom_violation = bool(np.any(q_deg < rom_min - 1e-9) or np.any(q_deg > rom_max + 1e-9))
    force_gate_respected = peak_force <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9
    torque_limits_respected = peak_torque_fraction < 1.0 - 1e-9
    # These are engineering regression tolerances for solver consistency, not
    # robot, treatment, or clinical safety limits.
    constraint_regression_sound = bool(
        peak_weld_position <= 1e-3
        and peak_weld_rotation <= math.radians(1.0)
        and peak_wrench_residual <= 1e-6
        and peak_human_tau_residual <= 1e-6
    )
    mechanically_sound = bool(
        completed
        and force_gate_respected
        and torque_limits_respected
        and not rom_violation
        and not unintended_contacts
        and not plant.warning_counts()
        and constraint_regression_sound
    )
    active = bed_force > 2.0
    summary = {
        "evidence_category": "engineering_validation_smoke",
        "scenario": "hold" if hold_only else "frozen_nominal_reference_prefix",
        "lower_q2_deg": lower_q2_deg,
        "requested_duration_s": duration_s,
        "completed_duration_s": float(time[-1]),
        "termination_reason": termination,
        "mechanically_complete_for_next_gate": mechanically_sound,
        "reset": {
            "human_q_deg": np.degrees(initial.human_q_rad).tolist(),
            "weld_position_error_mm": 1e3 * initial.weld_position_error_m,
            "weld_rotation_error_deg": math.degrees(initial.weld_rotation_error_rad),
            "initial_cuff_force_n": float(np.linalg.norm(initial.cuff_force_vector_n)),
            "initial_cuff_moment_norm_nm": float(np.linalg.norm(initial.cuff_moment_vector_nm)),
            "first_50ms_peak_cuff_force_n": first_50ms_peak_force,
            "first_50ms_peak_human_speed_deg_s": math.degrees(first_50ms_peak_human_speed),
        },
        "tracking": {
            "rmse_deg": np.sqrt(np.mean(tracking_error_deg**2, axis=0)).tolist(),
            "max_abs_error_deg": np.max(np.abs(tracking_error_deg), axis=0).tolist(),
            "terminal_error_deg": tracking_error_deg[-1].tolist(),
            "actual_q_min_deg": np.min(q_deg, axis=0).tolist(),
            "actual_q_max_deg": np.max(q_deg, axis=0).tolist(),
            "rom_violation": rom_violation,
        },
        "cuff": {
            "peak_translational_force_n": peak_force,
            "force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
            "force_gate_respected": force_gate_respected,
            "peak_moment_norm_nm": peak_moment,
            "peak_abs_world_my_nm": peak_abs_my,
            "moment_limit_nm": None,
            "peak_allocated_translational_force_n": max(allocated_forces, default=0.0),
            "peak_abs_allocated_my_nm": max((abs(v) for v in allocated_my), default=0.0),
            "peak_weld_position_error_mm": 1e3 * peak_weld_position,
            "peak_weld_rotation_error_deg": math.degrees(peak_weld_rotation),
            "max_wrench_reconstruction_residual_nm": peak_wrench_residual,
            "max_human_virtual_work_torque_residual_nm": peak_human_tau_residual,
            "raw_rotational_efc_force_used_as_moment": False,
        },
        "robot": {
            "joint_torque_limits_nm": plant.torque_limits_nm.tolist(),
            "peak_abs_commanded_joint_torque_nm": np.max(np.abs(robot_torque), axis=0).tolist(),
            "peak_unclipped_torque_limit_fraction": peak_torque_fraction,
            "peak_abs_joint_velocity_deg_s": np.degrees(peak_robot_velocity).tolist(),
            "minimum_6d_jacobian_singular_value": minimum_jacobian_singular_value,
            "worst_6d_jacobian_condition_number": worst_jacobian_condition_number,
            "torque_limits_respected_without_clipping_demand": torque_limits_respected,
            "torque_saturation_control_samples": torque_saturation_samples,
            "explicit_gear1_torque_interface": True,
            "position_servo_present": False,
        },
        "bed": {
            "peak_force_n": peak_bed_force,
            "peak_penetration_mm": 1e3 * peak_bed_penetration,
            "force_bearing_duration_over_2n_s": float(np.count_nonzero(active) * 0.001),
            "force_bearing_duty_fraction": float(np.mean(active)),
            "normal_impulse_ns": float(np.sum(bed_force) * 0.001),
        },
        "collision": {
            "unintended_contact_pairs": [list(pair) for pair in sorted(unintended_contacts)],
            "robot_self_collision_detection_retained": True,
            "human_bed_contact_retained": True,
        },
        "solver": {
            "warning_counts": plant.warning_counts(),
            "nonfinite_detected": termination == "nonfinite_state_or_wrench",
            "physical_substep_samples": physical_samples,
            "constraint_regression_sound": constraint_regression_sound,
        },
        "scientific_parameters_changed_for_run": False,
        "protective_logic_used": False,
    }
    trace = {
        "time_s": time,
        "human_q_deg": q_deg,
        "human_q_ref_deg": np.degrees(q_ref),
        "human_dq_deg_s": np.degrees(dq),
        "robot_q_rad": np.array([item.robot_q_rad for item in observations]),
        "robot_dq_rad_s": np.array([item.robot_dq_rad_s for item in observations]),
        "robot_torque_nm": robot_torque,
        "cuff_force_n": cuff_force,
        "cuff_moment_nm": cuff_moment,
        "allocated_force_n": np.asarray(allocated_forces),
        "allocated_my_nm": np.asarray(allocated_my),
        "required_human_torque_nm": np.asarray(required_torque),
    }
    return summary, trace


def write_scenario_artifacts(
    output_dir: Path,
    name: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{name}.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(output_dir / f"{name}_trace.npz", **trace)
