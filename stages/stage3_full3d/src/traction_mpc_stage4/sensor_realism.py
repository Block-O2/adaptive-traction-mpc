"""Small Stage-4 sensor-realism engineering suite.

This module keeps the frozen plant, estimator, MPC, trajectory, gains, and
limits.  It changes only the controller-facing observation boundary.  MuJoCo
Human state and contact truth are read exclusively in the evaluation blocks.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import time as wall_time
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    CuffForceCommandLimitError,
    HIP_HEIGHT_M,
)
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, soft_limit_torque
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .adaptive_estimators import IntegralAdaptiveHumanEstimator
from .cold_start import _geometry_vector
from .estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    OneShotHumanEstimatorV2,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from .evaluation import BED_CONTACT_CONTAMINATION_FORCE_N, Stage4CoupledPlant
from .human_model import registered_cold_start_perturbed_human
from .measurement import (
    CausalMeasurementLayer,
    ControllerMeasurement,
    MeasurementCase,
    MeasurementPreprocessing,
    measurement_case_dict,
)
from .mpc import HumanSpaceMPC
from .reference import COLD_START_TEACHING_DURATION_S, COLD_START_TEACHING_WAYPOINTS, cold_start_teaching_reference
from .state_ukf import StateUKFConfig


class SensorBoundaryStage4Plant(Stage4CoupledPlant):
    """Frozen plant with the same low-level law evaluated from measurements."""

    def __init__(self, human: Any) -> None:
        super().__init__(human)
        self._measured_robot_model = UR10eTorqueRobot()

    def apply_measured_nominal_cartesian_control(
        self,
        measurement: ControllerMeasurement,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray,
        target_angular_velocity_rad_s: np.ndarray,
        feedforward_wrench_world: np.ndarray,
    ) -> None:
        force = 3000.0 * (
            np.asarray(target_position_m) - measurement.attachment_position_m
        )
        force += 140.0 * (
            np.asarray(target_velocity_m_s) - measurement.attachment_velocity_m_s
        )
        force = np.clip(force, -200.0, 200.0)
        moment = 120.0 * self._rotation_error(
            np.asarray(target_rotation_matrix), measurement.attachment_rotation_matrix
        )
        moment += 12.0 * (
            np.asarray(target_angular_velocity_rad_s)
            - measurement.attachment_angular_velocity_rad_s
        )
        feedforward = np.asarray(feedforward_wrench_world, dtype=float)
        if feedforward.shape != (6,) or not np.all(np.isfinite(feedforward)):
            raise ValueError("feedforward_wrench_world must be a finite six-vector")
        force += feedforward[:3]
        moment += feedforward[3:]
        force_norm = float(np.linalg.norm(force))
        if force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            raise CuffForceCommandLimitError(force_norm)

        self._measured_robot_model.set_configuration(
            measurement.robot_q_rad, measurement.robot_dq_rad_s
        )
        jacobian = self._measured_robot_model.attachment_jacobian()
        pinv = jacobian.T @ np.linalg.inv(jacobian @ jacobian.T + 1e-4 * np.eye(6))
        nullspace = np.eye(6) - pinv @ jacobian
        posture = (
            12.0 * (self.neutral_robot_q - measurement.robot_q_rad)
            - 3.0 * measurement.robot_dq_rad_s
        )
        torque = self._measured_robot_model.bias_torque_nm()
        torque += jacobian.T @ np.concatenate([force, moment]) + nullspace.T @ posture
        self.last_unclipped_joint_torque = torque.copy()
        clipped = np.clip(torque, -self.torque_limits_nm, self.torque_limits_nm)
        self.data.ctrl[self.actuator_ids] = clipped
        self.last_joint_torque = clipped.copy()
        self.last_force = force.copy()
        self.last_moment = moment.copy()


def _finite_measurement(measurement: ControllerMeasurement) -> bool:
    return all(
        np.all(np.isfinite(value))
        for value in (
            measurement.robot_q_rad,
            measurement.robot_dq_rad_s,
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            measurement.attachment_velocity_m_s,
            measurement.attachment_angular_velocity_rad_s,
            measurement.cuff_force_vector_n,
            measurement.cuff_moment_vector_nm,
        )
    )


def _relative_parameter_metrics(estimate: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    relative = 100.0 * (estimate - truth) / np.maximum(np.abs(truth), 1e-9)
    return {
        "relative_l2_error_percent": float(100.0 * np.linalg.norm(estimate - truth) / np.linalg.norm(truth)),
        "median_abs_relative_error_percent": float(np.median(np.abs(relative))),
        "per_parameter_relative_error_percent": relative.tolist(),
    }


def run_sensor_realism_case(
    case: MeasurementCase,
    *,
    duration_s: float = COLD_START_TEACHING_DURATION_S,
    estimator_architecture: str = "instantaneous_v2",
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run the registered perturbed Human through one fixed sensor case."""

    true_human, true_metadata = registered_cold_start_perturbed_human()
    plant = SensorBoundaryStage4Plant(true_human)
    initial_reference = cold_start_teaching_reference(0.0)
    truth = plant.reset(initial_reference.q_rad)
    measurement_layer = CausalMeasurementLayer(case, truth)
    measurement = measurement_layer.current
    # The retained posture target is a robot-known startup measurement, not a
    # hidden copy of the simulator's clean initial joint configuration.
    plant.neutral_robot_q = measurement.robot_q_rad.copy()
    if estimator_architecture == "instantaneous_v2":
        estimator = OneShotHumanEstimatorV2(
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            initial_reference.q_rad,
        )
    elif estimator_architecture in {"integral_minimal", "integral_state_ukf"}:
        estimator = IntegralAdaptiveHumanEstimator(
            measurement.attachment_position_m,
            measurement.attachment_rotation_matrix,
            initial_reference.q_rad,
            use_state_ukf=estimator_architecture == "integral_state_ukf",
            initial_time_s=measurement.sample_time_s,
        )
    else:
        raise ValueError(
            "estimator_architecture must be instantaneous_v2, integral_minimal, "
            "or integral_state_ukf"
        )
    mpc = HumanSpaceMPC()
    high_level_steps = int(round(mpc.config.prediction_dt_s / CONTROL_DT_S))
    if high_level_steps * CONTROL_DT_S != mpc.config.prediction_dt_s:
        raise RuntimeError("MPC period must be an integer number of control periods")

    estimated_state = estimator.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )
    current_action = np.zeros(2)
    current_model = estimator.model
    current_allocation = current_model.allocate_generalized_action(current_action, estimated_state[:2])
    current_geometry_diag = estimator.geometry_identifier.last_diagnostics
    current_dynamic_diag = estimator.dynamic_identifier.last_diagnostics

    observations = [truth]
    references = [initial_reference.q_rad.copy()]
    estimated_states = [estimated_state.copy()]
    desired_actions = [current_action.copy()]
    allocated_wrenches = [np.asarray(current_allocation["wrench_world"]).copy()]
    geometry_estimates = [_geometry_vector(estimator)]
    dynamic_estimates = [estimator.dynamic_identifier.last_valid.copy()]
    estimator_status = [0]
    local_forces = [truth.attachment_rotation_matrix.T @ truth.cuff_force_vector_n]
    local_moments = [truth.attachment_rotation_matrix.T @ truth.cuff_moment_vector_nm]
    torque_fractions = [0.0]
    measurement_ages: list[float] = []
    measurement_new: list[bool] = []
    measured_forces: list[np.ndarray] = []
    measured_moments: list[np.ndarray] = []
    control_truth_forces: list[np.ndarray] = []
    control_truth_moments: list[np.ndarray] = []
    control_times: list[float] = []
    control_true_q: list[np.ndarray] = []
    control_true_dq: list[np.ndarray] = []
    control_estimated_state: list[np.ndarray] = []
    control_bed_force: list[float] = []
    estimator_compute_s: list[float] = []
    mpc_compute_s: list[float] = []
    unintended_contacts: set[tuple[str, str]] = set(truth.unintended_contact_pairs)
    rom_event_count = 0
    robot_position_limit_count = 0
    force_gate_event_count = 0
    torque_saturation_count = 0
    termination = "completed"
    requested_steps = int(round(duration_s / CONTROL_DT_S))
    robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]
    rollout_wall_start = wall_time.perf_counter()

    for control_index in range(requested_steps):
        current_truth = plant.observe()
        measurement = measurement_layer.update(current_truth)
        if not _finite_measurement(measurement):
            termination = "nonfinite_controller_measurement"
            break
        if control_index % high_level_steps == 0:
            estimator_start = wall_time.perf_counter()
            estimated_state, diagnostics = estimator.observe(
                time_s=measurement.sample_time_s,
                position_world_m=measurement.attachment_position_m,
                rotation_world_from_cuff=measurement.attachment_rotation_matrix,
                linear_velocity_world_m_s=measurement.attachment_velocity_m_s,
                angular_velocity_world_rad_s=measurement.attachment_angular_velocity_rad_s,
                force_world_n=measurement.cuff_force_vector_n,
                moment_world_nm=measurement.cuff_moment_vector_nm,
                # No MuJoCo bed/contact truth crosses the measurement boundary.
                bed_contaminated=False,
            )
            estimator_compute_s.append(wall_time.perf_counter() - estimator_start)
            current_geometry_diag = diagnostics["geometry"]
            current_dynamic_diag = diagnostics["dynamics"]
            current_model = estimator.model
            mpc_start = wall_time.perf_counter()
            current_action, _ = mpc.solve(
                estimated_state,
                float(measurement.arrival_time_s),
                cold_start_teaching_reference,
                current_model,
            )
            mpc_compute_s.append(wall_time.perf_counter() - mpc_start)
        else:
            if estimator_architecture == "integral_state_ukf":
                estimated_state = estimator.last_state.copy()
            else:
                estimated_state = current_model.geometry.estimate_state(
                    measurement.attachment_position_m,
                    measurement.attachment_rotation_matrix,
                    measurement.attachment_velocity_m_s,
                    measurement.attachment_angular_velocity_rad_s,
                )
        current_allocation = current_model.allocate_generalized_action(
            current_action, estimated_state[:2]
        )
        if float(current_allocation["force_norm_n"]) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            termination = "allocated_cuff_force_gate"
            force_gate_event_count += 1
            break

        reference = cold_start_teaching_reference(float(measurement.arrival_time_s))
        target_pose = current_model.geometry.cuff_pose(reference.q_rad)
        target_linear_velocity, target_angular_velocity = current_model.geometry.cuff_velocity(
            reference.q_rad, reference.dq_rad_s
        )
        try:
            plant.apply_measured_nominal_cartesian_control(
                measurement,
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
            np.max(np.abs(plant.last_unclipped_joint_torque) / plant.torque_limits_nm)
        )
        torque_saturation_count += int(unclipped_fraction >= 1.0 - 1e-9)
        control_times.append(current_truth.time_s)
        control_true_q.append(current_truth.human_q_rad.copy())
        control_true_dq.append(current_truth.human_dq_rad_s.copy())
        control_estimated_state.append(estimated_state.copy())
        control_bed_force.append(float(current_truth.bed_force_n))
        measurement_ages.append(measurement.age_s)
        measurement_new.append(measurement.new_sample)
        measured_forces.append(measurement.cuff_force_vector_n.copy())
        measured_moments.append(measurement.cuff_moment_vector_nm.copy())
        control_truth_forces.append(current_truth.cuff_force_vector_n.copy())
        control_truth_moments.append(current_truth.cuff_moment_vector_nm.copy())

        for _ in range(CONTROL_SUBSTEPS):
            truth = plant.step()
            observations.append(truth)
            references.append(cold_start_teaching_reference(truth.time_s).q_rad.copy())
            estimated_states.append(estimated_state.copy())
            desired_actions.append(current_action.copy())
            allocated_wrenches.append(np.asarray(current_allocation["wrench_world"]).copy())
            geometry_estimates.append(_geometry_vector(estimator))
            dynamic_estimates.append(estimator.dynamic_identifier.last_valid.copy())
            status_code = 0
            if current_geometry_diag.get("attempted", False):
                status_code = 1 if current_geometry_diag.get("accepted", False) else -1
            if current_dynamic_diag.get("attempted", False):
                status_code = 2 if current_dynamic_diag.get("accepted", False) else -2
            estimator_status.append(status_code)
            local_forces.append(truth.attachment_rotation_matrix.T @ truth.cuff_force_vector_n)
            local_moments.append(truth.attachment_rotation_matrix.T @ truth.cuff_moment_vector_nm)
            torque_fractions.append(unclipped_fraction)
            unintended_contacts.update(truth.unintended_contact_pairs)

            true_q = truth.human_q_rad
            rom_event_count += int(
                np.any(true_q < np.asarray(true_human.q_min_rad) - 1e-9)
                or np.any(true_q > np.asarray(true_human.q_max_rad) + 1e-9)
            )
            robot_position_limit_count += int(
                np.any(truth.robot_q_rad < robot_ranges[:, 0] - 1e-9)
                or np.any(truth.robot_q_rad > robot_ranges[:, 1] + 1e-9)
            )
            if np.linalg.norm(truth.cuff_force_vector_n) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
                force_gate_event_count += 1
                termination = "physical_cuff_force_gate"
                break
            if plant.warning_counts():
                termination = "mujoco_solver_warning"
                break
        if termination != "completed":
            break

    time = np.array([item.time_s for item in observations])
    true_q = np.array([item.human_q_rad for item in observations])
    q_ref = np.asarray(references)
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
    completed = bool(termination == "completed" and time[-1] >= duration_s - 0.5 * CONTROL_DT_S)
    rollout_wall_elapsed_s = wall_time.perf_counter() - rollout_wall_start

    control_time = np.asarray(control_times)
    control_dq_true = np.asarray(control_true_dq)
    control_state_est = np.asarray(control_estimated_state)
    estimated_ddq = np.gradient(control_state_est[:, 2:], control_time, axis=0, edge_order=2)
    true_ddq = np.gradient(control_dq_true, control_time, axis=0, edge_order=2)
    acceleration_error = estimated_ddq - true_ddq

    true_beta = nominal_base_parameters(true_human)
    final_beta = estimator.dynamic_identifier.last_valid.copy()
    final_geometry = estimator.geometry
    clean_prediction = np.asarray(control_bed_force) <= BED_CONTACT_CONTAMINATION_FORCE_N
    for index, (angles, velocity) in enumerate(
        zip(np.asarray(control_true_q), control_dq_true, strict=True)
    ):
        if np.linalg.norm(soft_limit_torque(angles, velocity, true_human)) > 1e-8:
            clean_prediction[index] = False
    true_prediction: list[np.ndarray] = []
    estimated_prediction: list[np.ndarray] = []
    for angles, velocity, acceleration, keep in zip(
        np.asarray(control_true_q),
        control_dq_true,
        true_ddq,
        clean_prediction,
        strict=True,
    ):
        if not keep:
            continue
        regressor = dynamic_regressor_row(angles, velocity, acceleration)
        true_prediction.append(regressor @ true_beta)
        estimated_prediction.append(regressor @ final_beta)
    prediction_error = np.asarray(estimated_prediction) - np.asarray(true_prediction)
    true_hip_world = np.array([0.0, 0.0, HIP_HEIGHT_M])
    hip_delta = true_hip_world - final_geometry.origin_world_m
    true_hip_plane = np.array(
        [final_geometry.plane_x_world @ hip_delta, final_geometry.plane_z_world @ hip_delta]
    )
    geometry_metrics = {
        "hip_pivot_plane_error_mm_god_view": float(1000.0 * np.linalg.norm(final_geometry.hip_plane_m - true_hip_plane)),
        "thigh_length_error_percent_god_view": float(100.0 * (final_geometry.thigh_length_m - true_human.thigh_length_m) / true_human.thigh_length_m),
        "cuff_distance_error_percent_god_view": float(100.0 * (final_geometry.cuff_distance_m - true_human.sleeve_center_m) / true_human.sleeve_center_m),
        "joint_axis_error_deg_god_view": float(math.degrees(math.acos(np.clip(abs(final_geometry.joint_axis_world @ np.array([0.0, 1.0, 0.0])), -1.0, 1.0)))),
        "joint_state_estimation_rmse_deg_god_view": np.sqrt(np.mean(estimation_error_deg**2, axis=0)).tolist(),
    }

    measured_force_array = np.asarray(measured_forces)
    measured_moment_array = np.asarray(measured_moments)
    control_truth_force = np.asarray(control_truth_forces)
    control_truth_moment = np.asarray(control_truth_moments)
    common = min(len(measured_force_array), len(control_truth_force))
    force_measurement_error = measured_force_array[:common] - control_truth_force[:common]
    moment_measurement_error = measured_moment_array[:common] - control_truth_moment[:common]

    last_geometry_attempt = estimator.geometry_diagnostics[-1] if estimator.geometry_diagnostics else estimator.geometry_identifier.last_diagnostics
    last_dynamic_attempt = estimator.dynamic_diagnostics[-1] if estimator.dynamic_diagnostics else estimator.dynamic_identifier.last_diagnostics
    summary = {
        "evidence_category": "stage4_sensor_realism_engineering_rollout",
        "case": case.name,
        "estimator_architecture": {
            "name": estimator_architecture,
            "state_observer": "state_only_ukf"
            if estimator_architecture == "integral_state_ukf"
            else "none",
            "dynamic_identifier": "causal_accumulated_integral_11_base_parameter_regression"
            if estimator_architecture.startswith("integral_")
            else "legacy_instantaneous_acceleration_regression",
            "augmented_or_parameter_ukf": False,
            "ukf_config": StateUKFConfig().as_dict()
            if estimator_architecture == "integral_state_ukf"
            else None,
        },
        "measurement_model": measurement_case_dict(case),
        "preprocessing": {
            "shared_across_all_nonideal_cases": True,
            "lowpass_cutoff_hz": MeasurementPreprocessing().lowpass_cutoff_hz,
            "causal_local_quadratic_derivative_window_s": MeasurementPreprocessing().derivative_window_s,
            "pose_state_wrench_timestamp_alignment": "single sampled timestamp before common delay",
            "ft_bias_estimation_or_subtraction": False,
            "bed_contact_truth_fed_to_estimator": False,
        },
        "controller_or_estimator_clean_mujoco_truth_access": False,
        "truth_scope": "god_view_evaluation_and_simulated_plant_only",
        "true_human_case": "cold_start_perturbed",
        "true_human_parameters_god_view_only": true_metadata,
        "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
        "trajectory_waypoints": [
            {"time_s": item.time_s, "q_deg": list(item.q_deg), "label": item.label}
            for item in COLD_START_TEACHING_WAYPOINTS
        ],
        "requested_duration_s": float(duration_s),
        "completed_duration_s": float(time[-1]),
        "termination_reason": termination,
        "mechanically_completed_requested_duration": completed,
        "geometry_identifier": {
            "trustworthy_time_s": estimator.geometry_identifier.trustworthy_time_s,
            "accepted_updates": estimator.geometry_identifier.accepted_updates,
            "rejected_updates": estimator.geometry_identifier.rejected_updates,
            "final_estimate": _geometry_vector(estimator).tolist(),
            "last_attempt": last_geometry_attempt,
            **geometry_metrics,
        },
        "dynamic_identifier": {
            "trustworthy_time_s": estimator.dynamic_identifier.trustworthy_time_s,
            "accepted_updates": estimator.dynamic_identifier.accepted_updates,
            "rejected_updates": estimator.dynamic_identifier.rejected_updates,
            "base_parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
            "final_estimate": final_beta.tolist(),
            "true_base_parameters_god_view": true_beta.tolist(),
            "last_attempt": last_dynamic_attempt,
            **_relative_parameter_metrics(final_beta, true_beta),
            "god_view_base_model_torque_prediction_rmse_nm": np.sqrt(
                np.mean(prediction_error**2, axis=0)
            ).tolist()
            if len(prediction_error)
            else [float("nan"), float("nan")],
            "god_view_base_model_torque_prediction_combined_rmse_nm": float(
                np.sqrt(np.mean(prediction_error**2))
            )
            if len(prediction_error)
            else float("nan"),
            "god_view_clean_prediction_sample_count": int(len(prediction_error)),
        },
        "state_ukf": {
            "enabled": estimator_architecture == "integral_state_ukf",
            "state_dimension": 4 if estimator_architecture == "integral_state_ukf" else 0,
            "parameter_state_dimension": 0,
            "last_diagnostics": getattr(
                getattr(estimator, "state_ukf", None), "last_diagnostics", None
            ),
        },
        "computational_cost": {
            "rollout_wall_time_s": rollout_wall_elapsed_s,
            "wall_time_per_simulated_second": rollout_wall_elapsed_s
            / max(float(time[-1]), 1e-12),
            "estimator_mean_ms": float(1000.0 * np.mean(estimator_compute_s)),
            "estimator_p95_ms": float(1000.0 * np.percentile(estimator_compute_s, 95.0)),
            "mpc_mean_ms": float(1000.0 * np.mean(mpc_compute_s)),
            "mpc_p95_ms": float(1000.0 * np.percentile(mpc_compute_s, 95.0)),
        },
        "measurement_and_derivative_quality_god_view": {
            "mean_measurement_age_ms": float(1000.0 * np.mean(measurement_ages)),
            "max_measurement_age_ms": float(1000.0 * np.max(measurement_ages)),
            "delivered_new_sample_count": int(np.sum(measurement_new)),
            "force_vector_measurement_error_rms_n": float(np.sqrt(np.mean(force_measurement_error**2))),
            "moment_vector_measurement_error_rms_nm": float(np.sqrt(np.mean(moment_measurement_error**2))),
            "acceleration_estimation_rmse_rad_s2": np.sqrt(np.mean(acceleration_error**2, axis=0)).tolist(),
            "state_estimation_rmse_deg": np.sqrt(np.mean(estimation_error_deg**2, axis=0)).tolist(),
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
            "rms_parasitic_shear_force_n": float(np.sqrt(np.mean(np.sum(force_local[:, 1:] ** 2, axis=1)))),
            "peak_parasitic_shear_force_n": float(np.max(np.linalg.norm(force_local[:, 1:], axis=1))),
            "peak_abs_sagittal_cuff_moment_nm": float(np.max(np.abs(moment_local[:, 1]))),
            "peak_off_axis_cuff_moment_nm": float(np.max(np.linalg.norm(moment_local[:, [0, 2]], axis=1))),
            "rms_force_rate_n_s": float(np.sqrt(np.mean(force_rate_norm[1:] ** 2))) if len(force_rate_norm) > 1 else 0.0,
            "peak_force_rate_n_s": float(np.max(force_rate_norm)),
        },
        "robot": {
            "peak_unclipped_torque_limit_fraction": float(np.max(torque_fractions)),
            "torque_saturation_control_samples": torque_saturation_count,
            "joint_position_limit_samples": robot_position_limit_count,
            "peak_abs_joint_velocity_deg_s": np.degrees(np.max(np.abs(robot_velocity), axis=0)).tolist(),
        },
        "events": {
            "force_gate_events": force_gate_event_count,
            "rom_event_samples": rom_event_count,
            "unintended_contact_pairs": [list(item) for item in sorted(unintended_contacts)],
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
        "estimated_human_dq_deg_s": np.degrees(np.asarray(estimated_states)[:, 2:]),
        "robot_q_rad": np.array([item.robot_q_rad for item in observations]),
        "robot_dq_rad_s": robot_velocity,
        "robot_torque_nm": np.array([item.joint_torque_command_nm for item in observations]),
        "robot_torque_limit_fraction": np.asarray(torque_fractions),
        "cuff_force_local_n_god_view": force_local,
        "cuff_moment_local_nm_god_view": moment_local,
        "desired_human_action_nm": np.asarray(desired_actions),
        "allocated_wrench_world": np.asarray(allocated_wrenches),
        "geometry_estimate": np.asarray(geometry_estimates),
        "dynamic_base_estimate": np.asarray(dynamic_estimates),
        "estimator_status_code": np.asarray(estimator_status),
        "control_time_s": control_time,
        "control_estimated_state": control_state_est,
        "control_true_q_rad_god_view": np.asarray(control_true_q),
        "control_true_dq_rad_s_god_view": control_dq_true,
        "measurement_age_s": np.asarray(measurement_ages),
        "measurement_new_sample": np.asarray(measurement_new, dtype=bool),
        "measured_cuff_force_world_n": measured_force_array,
        "measured_cuff_moment_world_nm": measured_moment_array,
        "bed_force_n_god_view": np.array([item.bed_force_n for item in observations]),
    }
    return summary, trace


def save_sensor_case(
    output_dir: Path,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = str(summary["case"])
    (output_dir / f"{name}.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(output_dir / f"{name}_trace.npz", **trace)
