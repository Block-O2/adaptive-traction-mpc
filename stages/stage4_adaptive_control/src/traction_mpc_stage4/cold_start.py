"""Cold-start one-shot Stage-4 Adaptive MPC rollout and presentation output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    CuffForceCommandLimitError,
)
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN, HumanV2Parameters

from .estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    OneShotHumanEstimatorV2,
    nominal_base_parameters,
)
from .evaluation import BED_CONTACT_CONTAMINATION_FORCE_N, Stage4CoupledPlant
from .human_model import registered_cold_start_perturbed_human
from .mpc import HumanSpaceMPC
from .reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    cold_start_teaching_reference,
)


COLD_START_VALIDATION_DURATION_S = 7.0


def _true_case(case: str) -> tuple[HumanV2Parameters, dict[str, Any]]:
    if case == "nominal":
        return HUMAN, {
            "case": "nominal",
            "height_scale": 1.0,
            "mass_scale": 1.0,
            "thigh_com_scale": 1.0,
            "shank_com_scale": 1.0,
            "stiffness_scale": 1.0,
            "rest_offset_deg": [0.0, 0.0],
            "sleeve_center_scale": 1.0,
        }
    if case == "cold_start_perturbed":
        return registered_cold_start_perturbed_human()
    raise ValueError("true_case must be nominal or cold_start_perturbed")


def _finite_controller_measurements(observation: Any) -> bool:
    return all(
        np.all(np.isfinite(value))
        for value in (
            observation.robot_q_rad,
            observation.robot_dq_rad_s,
            observation.attachment_position_m,
            observation.attachment_rotation_matrix,
            observation.attachment_velocity_m_s,
            observation.attachment_angular_velocity_rad_s,
            observation.cuff_force_vector_n,
            observation.cuff_moment_vector_nm,
            observation.joint_torque_command_nm,
        )
    )


def _geometry_vector(estimator: OneShotHumanEstimatorV2) -> np.ndarray:
    geometry = estimator.geometry
    return np.concatenate(
        [
            geometry.hip_plane_m,
            [geometry.thigh_length_m],
            geometry.knee_to_cuff_in_cuff_m,
            geometry.joint_axis_world,
        ]
    )


def run_cold_start_adaptive_case(
    *,
    true_case: str,
    duration_s: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run one population-prior adaptive execution without Human truth input."""

    true_human, true_metadata = _true_case(true_case)
    plant = Stage4CoupledPlant(true_human)
    initial_reference = cold_start_teaching_reference(0.0)
    # The true joint state is used only to initialize the simulated patient.
    # It is not passed across the controller/estimator boundary below.
    observation = plant.reset(initial_reference.q_rad)
    estimator = OneShotHumanEstimatorV2(
        observation.attachment_position_m,
        observation.attachment_rotation_matrix,
        initial_reference.q_rad,
    )
    mpc = HumanSpaceMPC()
    high_level_steps = int(round(mpc.config.prediction_dt_s / CONTROL_DT_S))
    if high_level_steps * CONTROL_DT_S != mpc.config.prediction_dt_s:
        raise RuntimeError("MPC period must be an integer number of control periods")

    estimated_state = estimator.geometry.estimate_state(
        observation.attachment_position_m,
        observation.attachment_rotation_matrix,
        observation.attachment_velocity_m_s,
        observation.attachment_angular_velocity_rad_s,
    )
    current_action = np.zeros(2)
    current_model = estimator.model
    current_allocation = current_model.allocate_generalized_action(
        current_action, estimated_state[:2]
    )
    current_geometry_diag = estimator.geometry_identifier.last_diagnostics
    current_dynamic_diag = estimator.dynamic_identifier.last_diagnostics

    observations = [observation]
    references = [initial_reference.q_rad.copy()]
    estimated_states = [estimated_state.copy()]
    desired_actions = [current_action.copy()]
    allocated_wrenches = [np.asarray(current_allocation["wrench_world"]).copy()]
    geometry_estimates = [_geometry_vector(estimator)]
    dynamic_estimates = [estimator.dynamic_identifier.last_valid.copy()]
    geometry_ranks = [0]
    geometry_conditions = [float("nan")]
    dynamic_ranks = [0]
    dynamic_conditions = [float("nan")]
    estimator_status = [0]
    local_forces = [
        observation.attachment_rotation_matrix.T @ observation.cuff_force_vector_n
    ]
    local_moments = [
        observation.attachment_rotation_matrix.T @ observation.cuff_moment_vector_nm
    ]
    torque_fractions = [0.0]
    unintended_contacts: set[tuple[str, str]] = set(observation.unintended_contact_pairs)
    rom_event_count = 0
    robot_position_limit_count = 0
    force_gate_event_count = 0
    torque_saturation_count = 0
    termination = "completed"
    requested_steps = int(round(duration_s / CONTROL_DT_S))
    mpc_diagnostics: list[dict[str, Any]] = []
    robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]

    for control_index in range(requested_steps):
        current = plant.observe()
        if control_index % high_level_steps == 0:
            estimated_state, diagnostics = estimator.observe(
                time_s=current.time_s,
                position_world_m=current.attachment_position_m,
                rotation_world_from_cuff=current.attachment_rotation_matrix,
                linear_velocity_world_m_s=current.attachment_velocity_m_s,
                angular_velocity_world_rad_s=current.attachment_angular_velocity_rad_s,
                force_world_n=current.cuff_force_vector_n,
                moment_world_nm=current.cuff_moment_vector_nm,
                bed_contaminated=current.bed_force_n > BED_CONTACT_CONTAMINATION_FORCE_N,
            )
            current_geometry_diag = diagnostics["geometry"]
            current_dynamic_diag = diagnostics["dynamics"]
            current_model = estimator.model
            current_action, solve_diag = mpc.solve(
                estimated_state,
                float(plant.data.time),
                cold_start_teaching_reference,
                current_model,
            )
            mpc_diagnostics.append(solve_diag)
        else:
            estimated_state = current_model.geometry.estimate_state(
                current.attachment_position_m,
                current.attachment_rotation_matrix,
                current.attachment_velocity_m_s,
                current.attachment_angular_velocity_rad_s,
            )
        current_allocation = current_model.allocate_generalized_action(
            current_action, estimated_state[:2]
        )
        if float(current_allocation["force_norm_n"]) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            termination = "allocated_cuff_force_gate"
            force_gate_event_count += 1
            break

        reference = cold_start_teaching_reference(float(plant.data.time))
        target_pose = current_model.geometry.cuff_pose(reference.q_rad)
        target_linear_velocity, target_angular_velocity = (
            current_model.geometry.cuff_velocity(
                reference.q_rad, reference.dq_rad_s
            )
        )
        try:
            plant.apply_nominal_cartesian_control(
                target_pose.translation,
                target_linear_velocity,
                target_pose.rotation,
                target_angular_velocity,
                np.asarray(current_allocation["wrench_world"]),
            )
        except CuffForceCommandLimitError:
            termination = "total_commanded_cuff_force_gate"
            force_gate_event_count += 1
            break
        unclipped_fraction = float(
            np.max(
                np.abs(plant.last_unclipped_joint_torque) / plant.torque_limits_nm
            )
        )
        torque_saturation_count += int(unclipped_fraction >= 1.0 - 1e-9)

        for _ in range(CONTROL_SUBSTEPS):
            observation = plant.step()
            q_estimated_state = current_model.geometry.estimate_state(
                observation.attachment_position_m,
                observation.attachment_rotation_matrix,
                observation.attachment_velocity_m_s,
                observation.attachment_angular_velocity_rad_s,
            )
            observations.append(observation)
            references.append(
                cold_start_teaching_reference(observation.time_s).q_rad.copy()
            )
            estimated_states.append(q_estimated_state)
            desired_actions.append(current_action.copy())
            allocated_wrenches.append(
                np.asarray(current_allocation["wrench_world"]).copy()
            )
            geometry_estimates.append(_geometry_vector(estimator))
            dynamic_estimates.append(estimator.dynamic_identifier.last_valid.copy())
            geometry_ranks.append(int(current_geometry_diag.get("rank", 0)))
            geometry_conditions.append(
                float(current_geometry_diag.get("condition_number", float("nan")))
            )
            dynamic_ranks.append(int(current_dynamic_diag.get("rank", 0)))
            dynamic_conditions.append(
                float(current_dynamic_diag.get("condition_number", float("nan")))
            )
            status_code = 0
            if current_geometry_diag.get("attempted", False):
                status_code = 1 if current_geometry_diag.get("accepted", False) else -1
            if current_dynamic_diag.get("attempted", False):
                status_code = 2 if current_dynamic_diag.get("accepted", False) else -2
            estimator_status.append(status_code)
            local_forces.append(
                observation.attachment_rotation_matrix.T
                @ observation.cuff_force_vector_n
            )
            local_moments.append(
                observation.attachment_rotation_matrix.T
                @ observation.cuff_moment_vector_nm
            )
            torque_fractions.append(unclipped_fraction)
            unintended_contacts.update(observation.unintended_contact_pairs)

            # Human state is read only in this God-view evaluation block.
            true_q = observation.human_q_rad
            rom_event_count += int(
                np.any(true_q < np.asarray(true_human.q_min_rad) - 1e-9)
                or np.any(true_q > np.asarray(true_human.q_max_rad) + 1e-9)
            )
            robot_position_limit_count += int(
                np.any(observation.robot_q_rad < robot_ranges[:, 0] - 1e-9)
                or np.any(observation.robot_q_rad > robot_ranges[:, 1] + 1e-9)
            )
            if (
                np.linalg.norm(observation.cuff_force_vector_n)
                > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9
            ):
                force_gate_event_count += 1
                termination = "physical_cuff_force_gate"
                break
            if not _finite_controller_measurements(observation):
                termination = "nonfinite_controller_measurement"
                break
            if plant.warning_counts():
                termination = "mujoco_solver_warning"
                break
        if termination != "completed":
            break

    time = np.array([item.time_s for item in observations])
    true_q = np.array([item.human_q_rad for item in observations])
    q_ref = np.array(references)
    q_est = np.asarray(estimated_states)[:, :2]
    force_local = np.asarray(local_forces)
    moment_local = np.asarray(local_moments)
    force_norm = np.linalg.norm(force_local, axis=1)
    force_rate = np.zeros_like(force_local)
    if len(force_local) > 1:
        force_rate[1:] = np.diff(force_local, axis=0) / 0.001
    force_rate_norm = np.linalg.norm(force_rate, axis=1)
    tracking_deg = np.degrees(true_q - q_ref)
    estimation_error_deg = np.degrees(q_est - true_q)
    robot_velocity = np.array([item.robot_dq_rad_s for item in observations])
    completed = bool(
        termination == "completed"
        and time[-1] >= duration_s - 0.5 * CONTROL_DT_S
    )
    true_beta = nominal_base_parameters(true_human)
    final_geometry = estimator.geometry
    final_beta = estimator.dynamic_identifier.last_valid.copy()
    last_geometry_attempt = (
        estimator.geometry_diagnostics[-1]
        if estimator.geometry_diagnostics
        else estimator.geometry_identifier.last_diagnostics
    )
    last_dynamic_attempt = (
        estimator.dynamic_diagnostics[-1]
        if estimator.dynamic_diagnostics
        else estimator.dynamic_identifier.last_diagnostics
    )
    summary = {
        "evidence_category": "stage4_cold_start_engineering_rollout",
        "controller": "population_prior_estimator_v2_adaptive_human_space_mpc",
        "true_human_case": true_case,
        "true_human_parameters_god_view_only": true_metadata,
        "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
        "trajectory_waypoints": [
            {
                "time_s": waypoint.time_s,
                "q_deg": list(waypoint.q_deg),
                "label": waypoint.label,
            }
            for waypoint in COLD_START_TEACHING_WAYPOINTS
        ],
        "requested_duration_s": float(duration_s),
        "completed_duration_s": float(time[-1]),
        "termination_reason": termination,
        "mechanically_completed_requested_duration": completed,
        "cold_start_boundary": {
            "controller_inputs": [
                "robot_joint_state_and_fk",
                "measured_cuff_pose_and_twist",
                "reconstructed_actual_cuff_wrench",
                "nominal_population_human_v2_prior",
            ],
            "true_human_state_or_parameters_feed_estimator_or_controller": False,
            "initial_target_anchored_to_measured_cuff_pose": True,
        },
        "geometry_identifier": {
            "estimated_quantities": [
                "motion_plane_joint_axis_up_to_sign",
                "hip_pivot_projection_in_plane",
                "thigh_length",
                "knee_to_cuff_vector_in_cuff_frame",
                "cuff_to_shank_planar_orientation_offset",
            ],
            "population_prior": [
                0.0,
                0.0,
                HUMAN.thigh_length_m,
                HUMAN.sleeve_center_m,
                0.0,
            ],
            "final_estimate": _geometry_vector(estimator).tolist(),
            "true_thigh_length_m_god_view": true_human.thigh_length_m,
            "true_cuff_distance_m_god_view": true_human.sleeve_center_m,
            "thigh_length_error_percent_god_view": float(
                100.0
                * (final_geometry.thigh_length_m - true_human.thigh_length_m)
                / true_human.thigh_length_m
            ),
            "cuff_distance_error_percent_god_view": float(
                100.0
                * (final_geometry.cuff_distance_m - true_human.sleeve_center_m)
                / true_human.sleeve_center_m
            ),
            "trustworthy_time_s": estimator.geometry_identifier.trustworthy_time_s,
            "accepted_updates": estimator.geometry_identifier.accepted_updates,
            "rejected_updates": estimator.geometry_identifier.rejected_updates,
            "excluded_contaminated_samples": estimator.geometry_identifier.rejected_contaminated_samples,
            "last_attempt": last_geometry_attempt,
            "joint_state_estimation_rmse_deg_god_view": np.sqrt(
                np.mean(estimation_error_deg**2, axis=0)
            ).tolist(),
        },
        "dynamic_identifier": {
            "base_parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
            "population_prior": nominal_base_parameters().tolist(),
            "final_estimate": final_beta.tolist(),
            "true_base_parameters_god_view": true_beta.tolist(),
            "relative_error_percent_god_view": (
                100.0 * (final_beta - true_beta) / np.maximum(np.abs(true_beta), 1e-9)
            ).tolist(),
            "trustworthy_time_s": estimator.dynamic_identifier.trustworthy_time_s,
            "accepted_updates": estimator.dynamic_identifier.accepted_updates,
            "rejected_updates": estimator.dynamic_identifier.rejected_updates,
            "last_attempt": last_dynamic_attempt,
        },
        "tracking": {
            "rmse_deg": np.sqrt(np.mean(tracking_deg**2, axis=0)).tolist(),
            "combined_rmse_deg": float(np.sqrt(np.mean(tracking_deg**2))),
            "max_abs_error_deg": np.max(np.abs(tracking_deg), axis=0).tolist(),
        },
        "interaction_metrics_engineering_not_clinical": {
            "peak_total_translational_force_n": float(np.max(force_norm)),
            "rms_total_translational_force_n": float(np.sqrt(np.mean(force_norm**2))),
            "peak_abs_task_axial_force_n": float(np.max(np.abs(force_local[:, 0]))),
            "rms_parasitic_shear_force_n": float(
                np.sqrt(np.mean(np.sum(force_local[:, 1:] ** 2, axis=1)))
            ),
            "peak_parasitic_shear_force_n": float(
                np.max(np.linalg.norm(force_local[:, 1:], axis=1))
            ),
            "peak_abs_sagittal_cuff_moment_nm": float(
                np.max(np.abs(moment_local[:, 1]))
            ),
            "peak_off_axis_cuff_moment_nm": float(
                np.max(np.linalg.norm(moment_local[:, [0, 2]], axis=1))
            ),
            "rms_force_rate_n_s": float(
                np.sqrt(np.mean(force_rate_norm[1:] ** 2))
            )
            if len(force_rate_norm) > 1
            else 0.0,
            "peak_force_rate_n_s": float(np.max(force_rate_norm)),
        },
        "robot": {
            "peak_unclipped_torque_limit_fraction": float(np.max(torque_fractions)),
            "torque_saturation_control_samples": torque_saturation_count,
            "joint_position_limit_samples": robot_position_limit_count,
            "peak_abs_joint_velocity_deg_s": np.degrees(
                np.max(np.abs(robot_velocity), axis=0)
            ).tolist(),
        },
        "events": {
            "force_gate_events": force_gate_event_count,
            "rom_event_samples": rom_event_count,
            "unintended_contact_pairs": [
                list(item) for item in sorted(unintended_contacts)
            ],
            "mujoco_warning_counts": plant.warning_counts(),
            "mpc_solver_failures": mpc.failure_count,
        },
        "force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
        "moment_limit_nm": None,
    }
    trace = {
        "time_s": time,
        "human_q_deg_god_view": np.degrees(true_q),
        "human_q_ref_deg": np.degrees(q_ref),
        "estimated_human_q_deg": np.degrees(q_est),
        "estimated_human_dq_deg_s": np.degrees(
            np.asarray(estimated_states)[:, 2:]
        ),
        "robot_q_rad": np.array([item.robot_q_rad for item in observations]),
        "robot_dq_rad_s": robot_velocity,
        "robot_torque_nm": np.array(
            [item.joint_torque_command_nm for item in observations]
        ),
        "robot_torque_limit_fraction": np.asarray(torque_fractions),
        "cuff_force_local_n": force_local,
        "cuff_moment_local_nm": moment_local,
        "cuff_force_rate_local_n_s": force_rate,
        "desired_human_action_nm": np.asarray(desired_actions),
        "allocated_wrench_world": np.asarray(allocated_wrenches),
        "geometry_estimate": np.asarray(geometry_estimates),
        "dynamic_base_estimate": np.asarray(dynamic_estimates),
        "geometry_rank": np.asarray(geometry_ranks),
        "geometry_condition_number": np.asarray(geometry_conditions),
        "dynamic_rank": np.asarray(dynamic_ranks),
        "dynamic_condition_number": np.asarray(dynamic_conditions),
        "estimator_status_code": np.asarray(estimator_status),
        "bed_force_n": np.array([item.bed_force_n for item in observations]),
        "bed_contact_count": np.array(
            [item.bed_contact_count for item in observations]
        ),
    }
    return summary, trace


def cold_start_mechanically_viable(summary: dict[str, Any]) -> bool:
    return bool(
        summary["mechanically_completed_requested_duration"]
        and summary["events"]["force_gate_events"] == 0
        and summary["events"]["rom_event_samples"] == 0
        and summary["robot"]["torque_saturation_control_samples"] == 0
        and summary["robot"]["joint_position_limit_samples"] == 0
        and not summary["events"]["unintended_contact_pairs"]
        and not summary["events"]["mujoco_warning_counts"]
        and summary["geometry_identifier"]["trustworthy_time_s"] is not None
    )


def save_case(
    output_dir: Path,
    name: str,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{name}.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(output_dir / f"{name}_trace.npz", **trace)
