"""Small Stage-4 sensor-realism engineering suite.

This module keeps the frozen plant, estimator, MPC, trajectory, gains, and
limits.  It changes only the controller-facing observation boundary.  MuJoCo
Human state and contact truth are read exclusively in the evaluation blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
import time as wall_time
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    CONTROL_SUBSTEPS,
    CuffForceCommandLimitError,
    HIP_HEIGHT_M,
)
from traction_mpc_stage3.frames import ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HumanV2Parameters,
    soft_limit_torque,
)
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage3.robot import UR10eTorqueRobot
from scipy.spatial.transform import Rotation

from .adaptive_estimators import IntegralAdaptiveHumanEstimator
from .cold_start import _geometry_vector
from .confidence_execution import ReferenceExecutionLayer
from .cuff_allocator import default_engineering_cuff_allocator
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


@dataclass(frozen=True)
class MeasurementRouting:
    """Independent timestamp delays for the three controller-facing loops."""

    estimator_delay_s: float = 0.0
    mpc_state_delay_s: float = 0.0
    low_level_delay_s: float = 0.0
    extrapolate_low_level_to_arrival: bool = False


def _measurement_with_delay(case: MeasurementCase, delay_s: float, name: str) -> MeasurementCase:
    return replace(case, name=name, latency_s=float(delay_s))


def _extrapolate_measurement_to_arrival(
    measurement: ControllerMeasurement,
) -> ControllerMeasurement:
    dt = max(0.0, measurement.age_s)
    rotation = (
        Rotation.from_rotvec(measurement.attachment_angular_velocity_rad_s * dt).as_matrix()
        @ measurement.attachment_rotation_matrix
    )
    return ControllerMeasurement(
        arrival_time_s=measurement.arrival_time_s,
        sample_time_s=measurement.arrival_time_s,
        robot_q_rad=measurement.robot_q_rad + measurement.robot_dq_rad_s * dt,
        robot_dq_rad_s=measurement.robot_dq_rad_s.copy(),
        attachment_position_m=(
            measurement.attachment_position_m
            + measurement.attachment_velocity_m_s * dt
        ),
        attachment_rotation_matrix=rotation,
        attachment_velocity_m_s=measurement.attachment_velocity_m_s.copy(),
        attachment_angular_velocity_rad_s=measurement.attachment_angular_velocity_rad_s.copy(),
        cuff_force_vector_n=measurement.cuff_force_vector_n.copy(),
        cuff_moment_vector_nm=measurement.cuff_moment_vector_nm.copy(),
        new_sample=measurement.new_sample,
    )


class SensorBoundaryStage4Plant(Stage4CoupledPlant):
    """Frozen plant with the same low-level law evaluated from measurements."""

    def __init__(self, human: Any) -> None:
        super().__init__(human)
        self._measured_robot_model = UR10eTorqueRobot()

    def preview_measured_nominal_cartesian_command(
        self,
        measurement: ControllerMeasurement,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray,
        target_angular_velocity_rad_s: np.ndarray,
        feedforward_wrench_world: np.ndarray,
    ) -> dict[str, np.ndarray | float]:
        position_feedback = 3000.0 * (
            np.asarray(target_position_m) - measurement.attachment_position_m
        )
        velocity_feedback = 140.0 * (
            np.asarray(target_velocity_m_s) - measurement.attachment_velocity_m_s
        )
        feedback_force = np.clip(
            position_feedback + velocity_feedback, -200.0, 200.0
        )
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
        force = feedback_force + feedforward[:3]
        moment += feedforward[3:]
        return {
            "force_world_n": force,
            "moment_world_nm": moment,
            "position_feedback_world_n": position_feedback,
            "velocity_feedback_world_n": velocity_feedback,
            "clipped_feedback_world_n": feedback_force,
            "feedforward_force_world_n": feedforward[:3].copy(),
            "force_norm_n": float(np.linalg.norm(force)),
        }

    def apply_measured_nominal_cartesian_control(
        self,
        measurement: ControllerMeasurement,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray,
        target_angular_velocity_rad_s: np.ndarray,
        feedforward_wrench_world: np.ndarray,
    ) -> None:
        command = self.preview_measured_nominal_cartesian_command(
            measurement,
            target_position_m,
            target_velocity_m_s,
            target_rotation_matrix,
            target_angular_velocity_rad_s,
            feedforward_wrench_world,
        )
        force = np.asarray(command["force_world_n"], dtype=float)
        moment = np.asarray(command["moment_world_nm"], dtype=float)
        force_norm = float(command["force_norm_n"])
        if force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            raise CuffForceCommandLimitError(force_norm)

        self._measured_robot_model.set_configuration(
            measurement.robot_q_rad, measurement.robot_dq_rad_s
        )
        jacobian = self._measured_robot_model.rigid_offset_jacobian(
            ATTACHMENT_FROM_CUFF.translation
        )
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
    measurement_routing: MeasurementRouting | None = None,
    result_case_name: str | None = None,
    true_human_override: HumanV2Parameters | None = None,
    true_metadata_override: dict[str, Any] | None = None,
    reference_fn: Callable[[float], CuffPoseReference] = cold_start_teaching_reference,
    trajectory_label: str = "stage4_population_prior_cold_start_high_flexion_23s",
    trajectory_waypoints: tuple[Any, ...] = COLD_START_TEACHING_WAYPOINTS,
    plant_factory: Callable[[HumanV2Parameters], SensorBoundaryStage4Plant] | None = None,
    reference_execution: Any | None = None,
    reference_completion_phase_s: float | None = None,
    mpc_factory: Callable[[], HumanSpaceMPC] | None = None,
    cuff_allocator: Any | None = None,
    estimator_factory: Callable[[ControllerMeasurement, np.ndarray], Any] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run the registered perturbed Human through one fixed sensor case."""

    if cuff_allocator is None:
        cuff_allocator = default_engineering_cuff_allocator()

    default_human, default_metadata = registered_cold_start_perturbed_human()
    true_human = default_human if true_human_override is None else true_human_override
    true_metadata = (
        default_metadata if true_metadata_override is None else true_metadata_override
    )
    routing = measurement_routing
    if routing is None:
        routing = MeasurementRouting(
            estimator_delay_s=case.latency_s,
            mpc_state_delay_s=case.latency_s,
            low_level_delay_s=case.latency_s,
        )
    plant = (
        SensorBoundaryStage4Plant(true_human)
        if plant_factory is None
        else plant_factory(true_human)
    )
    def executed_reference(time_s: float) -> CuffPoseReference:
        return (
            reference_fn(time_s)
            if reference_execution is None
            else reference_execution.reference(time_s)
        )

    def execution_status(time_s: float) -> dict[str, float]:
        if reference_execution is None:
            return {
                "reference_phase_time_s": float(time_s),
                "speed_scale": 1.0,
                "speed_scale_rate_per_s": 0.0,
                "geometry_confidence": 0.0,
                "dynamic_confidence": 0.0,
                "combined_confidence": 0.0,
                "geometry_model_confidence": 0.0,
                "dynamic_model_confidence": 0.0,
                "combined_model_confidence_raw": 0.0,
                "filtered_model_confidence": 0.0,
                "execution_confidence_high": 0.0,
                "geometry_information_confidence": 0.0,
                "dynamic_information_confidence": 0.0,
                "combined_information_confidence": 0.0,
            }
        return reference_execution.status(time_s)

    initial_reference = executed_reference(0.0)
    truth = plant.reset(initial_reference.q_rad)
    estimator_layer = CausalMeasurementLayer(
        _measurement_with_delay(case, routing.estimator_delay_s, "estimator_channel"),
        truth,
    )
    mpc_layer = CausalMeasurementLayer(
        _measurement_with_delay(case, routing.mpc_state_delay_s, "mpc_state_channel"),
        truth,
    )
    low_level_layer = CausalMeasurementLayer(
        _measurement_with_delay(case, routing.low_level_delay_s, "low_level_channel"),
        truth,
    )
    estimator_measurement = estimator_layer.current
    mpc_measurement = mpc_layer.current
    low_level_measurement = low_level_layer.current
    # The retained posture target is a robot-known startup measurement, not a
    # hidden copy of the simulator's clean initial joint configuration.
    plant.neutral_robot_q = low_level_measurement.robot_q_rad.copy()
    if estimator_factory is not None:
        estimator = estimator_factory(estimator_measurement, initial_reference.q_rad)
    elif estimator_architecture == "instantaneous_v2":
        estimator = OneShotHumanEstimatorV2(
            estimator_measurement.attachment_position_m,
            estimator_measurement.attachment_rotation_matrix,
            initial_reference.q_rad,
        )
    elif estimator_architecture in {"integral_minimal", "integral_state_ukf"}:
        estimator = IntegralAdaptiveHumanEstimator(
            estimator_measurement.attachment_position_m,
            estimator_measurement.attachment_rotation_matrix,
            initial_reference.q_rad,
            use_state_ukf=estimator_architecture == "integral_state_ukf",
            initial_time_s=estimator_measurement.sample_time_s,
        )
    else:
        raise ValueError(
            "estimator_architecture must be instantaneous_v2, integral_minimal, "
            "or integral_state_ukf"
        )
    mpc = HumanSpaceMPC() if mpc_factory is None else mpc_factory()
    high_level_steps = int(round(mpc.config.prediction_dt_s / CONTROL_DT_S))
    if high_level_steps * CONTROL_DT_S != mpc.config.prediction_dt_s:
        raise RuntimeError("MPC period must be an integer number of control periods")

    estimated_state = estimator.geometry.estimate_state(
        mpc_measurement.attachment_position_m,
        mpc_measurement.attachment_rotation_matrix,
        mpc_measurement.attachment_velocity_m_s,
        mpc_measurement.attachment_angular_velocity_rad_s,
    )
    current_action = np.zeros(2)
    current_model = estimator.model
    current_allocation = cuff_allocator.allocate(
        current_action, estimated_state[:2], current_model
    )
    current_geometry_diag = estimator.geometry_identifier.last_diagnostics
    current_dynamic_diag = estimator.dynamic_identifier.last_diagnostics

    observations = [truth]
    references = [initial_reference.q_rad.copy()]
    estimated_states = [estimated_state.copy()]
    desired_actions = [current_action.copy()]
    allocated_wrenches = [np.asarray(current_allocation["wrench_world"]).copy()]
    allocation_equality_residuals = [
        float(
            current_allocation.get(
                "equality_residual_nm",
                current_allocation.get("allocation_residual_nm", 0.0),
            )
        )
    ]
    allocated_sagittal_wrenches = [
        np.asarray(current_allocation.get("sagittal_wrench", np.zeros(3))).copy()
    ]
    geometry_estimates = [_geometry_vector(estimator)]
    dynamic_estimates = [
        np.asarray(
            getattr(
                estimator,
                "control_beta",
                estimator.dynamic_identifier.last_valid,
            ),
            dtype=float,
        ).copy()
    ]
    estimator_status = [0]
    local_forces = [truth.attachment_rotation_matrix.T @ truth.cuff_force_vector_n]
    local_moments = [truth.attachment_rotation_matrix.T @ truth.cuff_moment_vector_nm]
    torque_fractions = [0.0]
    execution_statuses = [execution_status(truth.time_s)]
    distributed_cuff_enabled = hasattr(truth, "station_force_world_n")
    station_forces_world = (
        [truth.station_force_world_n.copy()] if distributed_cuff_enabled else []
    )
    station_relative_translations = (
        [truth.station_relative_translation_world_m.copy()]
        if distributed_cuff_enabled
        else []
    )
    center_relative_translations = (
        [truth.cuff_center_relative_translation_world_m.copy()]
        if distributed_cuff_enabled
        else []
    )
    cuff_shank_relative_rotations = (
        [float(truth.cuff_shank_relative_rotation_rad)]
        if distributed_cuff_enabled
        else []
    )
    measurement_ages: list[float] = []
    estimator_measurement_ages: list[float] = []
    mpc_measurement_ages: list[float] = []
    low_level_measurement_ages: list[float] = []
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
    mpc_compute_times_s: list[float] = []
    high_level_cycle_compute_s: list[float] = []
    mpc_selection_times: list[float] = []
    mpc_selected_alphas: list[float] = []
    mpc_selected_predicted_command_force: list[float] = []
    mpc_selected_executed_command_force: list[float] = []
    mpc_path_prediction_times: list[float] = []
    mpc_path_predicted_command_force: list[float] = []
    mpc_path_executed_command_force: list[float] = []
    held_interval_command_prediction: np.ndarray | None = None
    unintended_contacts: set[tuple[str, str]] = set(truth.unintended_contact_pairs)
    rom_event_count = 0
    robot_position_limit_count = 0
    force_gate_event_count = 0
    torque_saturation_count = 0
    commanded_force_norms: list[float] = []
    commanded_force_times: list[float] = []
    termination = "completed"
    requested_steps = int(round(duration_s / CONTROL_DT_S))
    robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]
    rollout_wall_start = wall_time.perf_counter()

    for control_index in range(requested_steps):
        new_mpc_diagnostics: dict[str, Any] | None = None
        deferred_high_level_timing = False
        high_level_cycle_start: float | None = None
        current_truth = plant.observe()
        estimator_measurement = estimator_layer.update(current_truth)
        mpc_measurement = mpc_layer.update(current_truth)
        low_level_measurement_raw = low_level_layer.update(current_truth)
        low_level_measurement = (
            _extrapolate_measurement_to_arrival(low_level_measurement_raw)
            if routing.extrapolate_low_level_to_arrival
            else low_level_measurement_raw
        )
        if not all(
            _finite_measurement(item)
            for item in (
                estimator_measurement,
                mpc_measurement,
                low_level_measurement,
            )
        ):
            termination = "nonfinite_controller_measurement"
            break
        if control_index % high_level_steps == 0:
            high_level_cycle_start = wall_time.perf_counter()
            estimator_start = wall_time.perf_counter()
            if hasattr(estimator, "observe_measurement"):
                estimator_output_state, diagnostics = estimator.observe_measurement(
                    estimator_measurement
                )
            else:
                estimator_output_state, diagnostics = estimator.observe(
                    time_s=estimator_measurement.sample_time_s,
                    position_world_m=estimator_measurement.attachment_position_m,
                    rotation_world_from_cuff=estimator_measurement.attachment_rotation_matrix,
                    linear_velocity_world_m_s=estimator_measurement.attachment_velocity_m_s,
                    angular_velocity_world_rad_s=estimator_measurement.attachment_angular_velocity_rad_s,
                    force_world_n=estimator_measurement.cuff_force_vector_n,
                    moment_world_nm=estimator_measurement.cuff_moment_vector_nm,
                    # No MuJoCo bed/contact truth crosses the measurement boundary.
                    bed_contaminated=False,
                )
            estimator_compute_s.append(wall_time.perf_counter() - estimator_start)
            current_geometry_diag = diagnostics["geometry"]
            current_dynamic_diag = diagnostics["dynamics"]
            current_model = estimator.model
            if reference_execution is not None and hasattr(
                reference_execution, "update_from_estimator"
            ):
                reference_execution.update_from_estimator(
                    float(mpc_measurement.arrival_time_s),
                    estimator,
                    current_geometry_diag,
                    current_dynamic_diag,
                )
            if estimator_architecture == "integral_state_ukf":
                estimated_state = estimator_output_state
            else:
                estimated_state = current_model.geometry.estimate_state(
                    mpc_measurement.attachment_position_m,
                    mpc_measurement.attachment_rotation_matrix,
                    mpc_measurement.attachment_velocity_m_s,
                    mpc_measurement.attachment_angular_velocity_rad_s,
                )
            if reference_execution is not None and hasattr(
                reference_execution, "update_from_prediction"
            ):
                reference_execution.update_from_prediction(
                    float(mpc_measurement.arrival_time_s),
                    estimated_state,
                    current_model,
                    mpc,
                    cuff_allocator,
                )
            mpc_start = wall_time.perf_counter()
            current_action, new_mpc_diagnostics = mpc.solve(
                estimated_state,
                float(mpc_measurement.arrival_time_s),
                executed_reference,
                current_model,
            )
            mpc_compute_s.append(wall_time.perf_counter() - mpc_start)
            mpc_compute_times_s.append(float(mpc_measurement.arrival_time_s))
            if reference_execution is not None and hasattr(
                reference_execution, "update_from_mpc_selection"
            ):
                reference_execution.update_from_mpc_selection(
                    float(mpc_measurement.arrival_time_s),
                    new_mpc_diagnostics,
                )
            if (
                "selected_first_control_interval_predicted_command_force_n"
                in new_mpc_diagnostics
            ):
                held_interval_command_prediction = np.asarray(
                    new_mpc_diagnostics[
                        "selected_first_control_interval_predicted_command_force_n"
                    ],
                    dtype=float,
                )
            deferred_high_level_timing = bool(
                reference_execution is not None
                and hasattr(reference_execution, "filter_executable_command")
            )
            if not deferred_high_level_timing:
                high_level_cycle_compute_s.append(
                    wall_time.perf_counter() - high_level_cycle_start
                )
        else:
            if estimator_architecture == "integral_state_ukf":
                estimated_state = estimator.last_state.copy()
            else:
                estimated_state = current_model.geometry.estimate_state(
                    mpc_measurement.attachment_position_m,
                    mpc_measurement.attachment_rotation_matrix,
                    mpc_measurement.attachment_velocity_m_s,
                    mpc_measurement.attachment_angular_velocity_rad_s,
                )
        reference = executed_reference(float(low_level_measurement.arrival_time_s))
        current_allocation = cuff_allocator.allocate(
            current_action, estimated_state[:2], current_model
        )
        if reference_execution is not None and hasattr(
            reference_execution, "filter_executable_command"
        ):
            def evaluate_executable_command(
                action: np.ndarray, candidate_reference: CuffPoseReference
            ) -> dict[str, Any]:
                allocation = cuff_allocator.allocate(
                    np.asarray(action, dtype=float), estimated_state[:2], current_model
                )
                target_pose = current_model.geometry.cuff_pose(
                    candidate_reference.q_rad
                )
                target_linear_velocity, target_angular_velocity = (
                    current_model.geometry.cuff_velocity(
                        candidate_reference.q_rad,
                        candidate_reference.dq_rad_s,
                    )
                )
                preview = plant.preview_measured_nominal_cartesian_command(
                    low_level_measurement,
                    target_pose.translation,
                    target_linear_velocity,
                    target_pose.rotation,
                    target_angular_velocity,
                    np.asarray(allocation["wrench_world"], dtype=float),
                )
                return {
                    "action": np.asarray(action, dtype=float).copy(),
                    "reference": candidate_reference,
                    "allocation": allocation,
                    "preview": preview,
                }

            proposed_command = evaluate_executable_command(
                current_action, reference
            )
            filtered_command = reference_execution.filter_executable_command(
                wall_time_s=float(low_level_measurement.arrival_time_s),
                estimated_state=np.asarray(estimated_state, dtype=float),
                proposed_command=proposed_command,
                mpc_diagnostics=new_mpc_diagnostics,
                mpc=mpc,
                evaluate_command=evaluate_executable_command,
            )
            if deferred_high_level_timing:
                assert high_level_cycle_start is not None
                high_level_cycle_compute_s.append(
                    wall_time.perf_counter() - high_level_cycle_start
                )
            requested_termination = filtered_command.get("terminate_reason")
            if requested_termination is not None:
                termination = str(requested_termination)
                break
            current_action = np.asarray(filtered_command["action"], dtype=float)
            reference = filtered_command["reference"]
            current_allocation = filtered_command["allocation"]
        if float(current_allocation["force_norm_n"]) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            commanded_force_norms.append(float(current_allocation["force_norm_n"]))
            commanded_force_times.append(float(current_truth.time_s))
            termination = "allocated_cuff_force_gate"
            force_gate_event_count += 1
            break

        target_pose = current_model.geometry.cuff_pose(reference.q_rad)
        target_linear_velocity, target_angular_velocity = current_model.geometry.cuff_velocity(
            reference.q_rad, reference.dq_rad_s
        )
        try:
            plant.apply_measured_nominal_cartesian_control(
                low_level_measurement,
                target_pose.translation,
                target_linear_velocity,
                target_pose.rotation,
                target_angular_velocity,
                np.asarray(current_allocation["wrench_world"]),
            )
        except CuffForceCommandLimitError as error:
            commanded_force_norms.append(error.force_norm_n)
            commanded_force_times.append(float(current_truth.time_s))
            if new_mpc_diagnostics is not None and (
                "selected_first_predicted_command_force_n" in new_mpc_diagnostics
            ):
                mpc_selection_times.append(float(current_truth.time_s))
                mpc_selected_alphas.append(
                    float(new_mpc_diagnostics["selected_alpha"])
                )
                mpc_selected_predicted_command_force.append(
                    float(
                        new_mpc_diagnostics[
                            "selected_first_predicted_command_force_n"
                        ]
                    )
                )
                mpc_selected_executed_command_force.append(error.force_norm_n)
            if held_interval_command_prediction is not None:
                interval_index = control_index % high_level_steps
                mpc_path_prediction_times.append(float(current_truth.time_s))
                mpc_path_predicted_command_force.append(
                    float(held_interval_command_prediction[interval_index])
                )
                mpc_path_executed_command_force.append(error.force_norm_n)
            termination = "total_commanded_cuff_force_gate"
            force_gate_event_count += 1
            break
        commanded_force_norms.append(float(np.linalg.norm(plant.last_force)))
        commanded_force_times.append(float(current_truth.time_s))
        if new_mpc_diagnostics is not None and (
            "selected_first_predicted_command_force_n" in new_mpc_diagnostics
        ):
            mpc_selection_times.append(float(current_truth.time_s))
            mpc_selected_alphas.append(
                float(new_mpc_diagnostics["selected_alpha"])
            )
            mpc_selected_predicted_command_force.append(
                float(
                    new_mpc_diagnostics[
                        "selected_first_predicted_command_force_n"
                    ]
                )
            )
            mpc_selected_executed_command_force.append(
                float(np.linalg.norm(plant.last_force))
            )
        if held_interval_command_prediction is not None:
            interval_index = control_index % high_level_steps
            mpc_path_prediction_times.append(float(current_truth.time_s))
            mpc_path_predicted_command_force.append(
                float(held_interval_command_prediction[interval_index])
            )
            mpc_path_executed_command_force.append(
                float(np.linalg.norm(plant.last_force))
            )
        unclipped_fraction = float(
            np.max(np.abs(plant.last_unclipped_joint_torque) / plant.torque_limits_nm)
        )
        torque_saturation_count += int(unclipped_fraction >= 1.0 - 1e-9)
        control_times.append(current_truth.time_s)
        control_true_q.append(current_truth.human_q_rad.copy())
        control_true_dq.append(current_truth.human_dq_rad_s.copy())
        control_estimated_state.append(estimated_state.copy())
        control_bed_force.append(float(current_truth.bed_force_n))
        measurement_ages.append(low_level_measurement_raw.age_s)
        estimator_measurement_ages.append(estimator_measurement.age_s)
        mpc_measurement_ages.append(mpc_measurement.age_s)
        low_level_measurement_ages.append(low_level_measurement_raw.age_s)
        measurement_new.append(low_level_measurement_raw.new_sample)
        measured_forces.append(estimator_measurement.cuff_force_vector_n.copy())
        measured_moments.append(estimator_measurement.cuff_moment_vector_nm.copy())
        control_truth_forces.append(current_truth.cuff_force_vector_n.copy())
        control_truth_moments.append(current_truth.cuff_moment_vector_nm.copy())

        for _ in range(CONTROL_SUBSTEPS):
            truth = plant.step()
            observations.append(truth)
            references.append(executed_reference(truth.time_s).q_rad.copy())
            estimated_states.append(estimated_state.copy())
            desired_actions.append(current_action.copy())
            allocated_wrenches.append(np.asarray(current_allocation["wrench_world"]).copy())
            allocation_equality_residuals.append(
                float(
                    current_allocation.get(
                        "equality_residual_nm",
                        current_allocation.get("allocation_residual_nm", 0.0),
                    )
                )
            )
            allocated_sagittal_wrenches.append(
                np.asarray(
                    current_allocation.get("sagittal_wrench", np.zeros(3))
                ).copy()
            )
            geometry_estimates.append(_geometry_vector(estimator))
            dynamic_estimates.append(
                np.asarray(
                    getattr(
                        estimator,
                        "control_beta",
                        estimator.dynamic_identifier.last_valid,
                    ),
                    dtype=float,
                ).copy()
            )
            status_code = 0
            if current_geometry_diag.get("attempted", False):
                status_code = 1 if current_geometry_diag.get("accepted", False) else -1
            if current_dynamic_diag.get("attempted", False):
                status_code = 2 if current_dynamic_diag.get("accepted", False) else -2
            estimator_status.append(status_code)
            local_forces.append(truth.attachment_rotation_matrix.T @ truth.cuff_force_vector_n)
            local_moments.append(truth.attachment_rotation_matrix.T @ truth.cuff_moment_vector_nm)
            torque_fractions.append(unclipped_fraction)
            execution_statuses.append(execution_status(truth.time_s))
            if distributed_cuff_enabled:
                station_forces_world.append(truth.station_force_world_n.copy())
                station_relative_translations.append(
                    truth.station_relative_translation_world_m.copy()
                )
                center_relative_translations.append(
                    truth.cuff_center_relative_translation_world_m.copy()
                )
                cuff_shank_relative_rotations.append(
                    float(truth.cuff_shank_relative_rotation_rad)
                )
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
            if (
                reference_completion_phase_s is not None
                and execution_statuses[-1]["reference_phase_time_s"]
                >= float(reference_completion_phase_s) - 1e-12
            ):
                termination = "reference_completed"
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
    moment_norm = np.linalg.norm(moment_local, axis=1)
    force_rate = np.zeros_like(force_local)
    moment_rate = np.zeros_like(moment_local)
    if len(force_local) > 1:
        force_rate[1:] = np.diff(force_local, axis=0) / 0.001
        moment_rate[1:] = np.diff(moment_local, axis=0) / 0.001
    force_rate_norm = np.linalg.norm(force_rate, axis=1)
    moment_rate_norm = np.linalg.norm(moment_rate, axis=1)
    tracking_deg = np.degrees(true_q - q_ref)
    estimation_error_deg = np.degrees(q_est - true_q)
    robot_velocity = np.array([item.robot_dq_rad_s for item in observations])
    if reference_completion_phase_s is None:
        completed = bool(
            termination == "completed"
            and time[-1] >= duration_s - 0.5 * CONTROL_DT_S
        )
    else:
        completed = bool(
            execution_statuses[-1]["reference_phase_time_s"]
            >= float(reference_completion_phase_s) - 1e-12
            and termination in {"completed", "reference_completed"}
        )
    rollout_wall_elapsed_s = wall_time.perf_counter() - rollout_wall_start
    execution_phase = np.asarray(
        [item["reference_phase_time_s"] for item in execution_statuses], dtype=float
    )
    execution_speed = np.asarray(
        [item["speed_scale"] for item in execution_statuses], dtype=float
    )
    execution_speed_rate = np.asarray(
        [item["speed_scale_rate_per_s"] for item in execution_statuses],
        dtype=float,
    )
    geometry_confidence = np.asarray(
        [item["geometry_confidence"] for item in execution_statuses], dtype=float
    )
    dynamic_confidence = np.asarray(
        [item["dynamic_confidence"] for item in execution_statuses], dtype=float
    )
    combined_confidence = np.asarray(
        [item["combined_confidence"] for item in execution_statuses], dtype=float
    )
    geometry_model_confidence = np.asarray(
        [item["geometry_model_confidence"] for item in execution_statuses],
        dtype=float,
    )
    dynamic_model_confidence = np.asarray(
        [item["dynamic_model_confidence"] for item in execution_statuses],
        dtype=float,
    )
    combined_model_confidence_raw = np.asarray(
        [item["combined_model_confidence_raw"] for item in execution_statuses],
        dtype=float,
    )
    filtered_model_confidence = np.asarray(
        [item["filtered_model_confidence"] for item in execution_statuses],
        dtype=float,
    )
    execution_confidence_high = np.asarray(
        [item["execution_confidence_high"] for item in execution_statuses],
        dtype=float,
    )
    geometry_information_confidence = np.asarray(
        [item["geometry_information_confidence"] for item in execution_statuses],
        dtype=float,
    )
    dynamic_information_confidence = np.asarray(
        [item["dynamic_information_confidence"] for item in execution_statuses],
        dtype=float,
    )
    combined_information_confidence = np.asarray(
        [item["combined_information_confidence"] for item in execution_statuses],
        dtype=float,
    )

    control_time = np.asarray(control_times)
    control_dq_true = np.asarray(control_true_dq)
    control_state_est = np.asarray(control_estimated_state)
    if len(control_time) >= 3:
        estimated_ddq = np.gradient(
            control_state_est[:, 2:], control_time, axis=0, edge_order=2
        )
        true_ddq = np.gradient(control_dq_true, control_time, axis=0, edge_order=2)
    elif len(control_time) == 2:
        estimated_ddq = np.gradient(
            control_state_est[:, 2:], control_time, axis=0, edge_order=1
        )
        true_ddq = np.gradient(control_dq_true, control_time, axis=0, edge_order=1)
    else:
        estimated_ddq = np.zeros((len(control_time), 2))
        true_ddq = np.zeros((len(control_time), 2))
    acceleration_error = estimated_ddq - true_ddq

    true_beta = nominal_base_parameters(true_human)
    final_beta = np.asarray(
        getattr(estimator, "control_beta", estimator.dynamic_identifier.last_valid),
        dtype=float,
    ).copy()
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
    command_prediction = np.asarray(mpc_selected_predicted_command_force)
    command_execution = np.asarray(mpc_selected_executed_command_force)
    command_prediction_error = command_execution - command_prediction
    path_command_prediction = np.asarray(mpc_path_predicted_command_force)
    path_command_execution = np.asarray(mpc_path_executed_command_force)
    path_command_prediction_error = path_command_execution - path_command_prediction
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
        "case": result_case_name or case.name,
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
        "measurement_routing": {
            "estimator_delay_ms": 1000.0 * routing.estimator_delay_s,
            "mpc_state_delay_ms": 1000.0 * routing.mpc_state_delay_s,
            "low_level_delay_ms": 1000.0 * routing.low_level_delay_s,
            "low_level_timestamp_extrapolation": routing.extrapolate_low_level_to_arrival,
        },
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
        "true_human_case": str(true_metadata.get("case", "custom_override")),
        "true_human_parameters_god_view_only": true_metadata,
        "trajectory": trajectory_label,
        "trajectory_waypoints": [
            {"time_s": item.time_s, "q_deg": list(item.q_deg), "label": item.label}
            for item in trajectory_waypoints
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
            "mpc_max_ms": float(1000.0 * np.max(mpc_compute_s)),
            "mpc_deadline_misses_over_20ms": int(
                np.sum(np.asarray(mpc_compute_s) > 0.020)
            ),
            "mpc_effective_hz_from_mean": float(
                1.0 / max(float(np.mean(mpc_compute_s)), 1e-12)
            ),
            "high_level_cycle_including_estimator_and_mpc_mean_ms": float(
                1000.0 * np.mean(high_level_cycle_compute_s)
            ),
            "high_level_cycle_including_estimator_and_mpc_p95_ms": float(
                1000.0 * np.percentile(high_level_cycle_compute_s, 95.0)
            ),
            "high_level_cycle_including_estimator_and_mpc_max_ms": float(
                1000.0 * np.max(high_level_cycle_compute_s)
            ),
            "high_level_cycle_deadline_misses_over_20ms": int(
                np.sum(np.asarray(high_level_cycle_compute_s) > 0.020)
            ),
            "high_level_cycle_effective_hz_from_mean": float(
                1.0 / max(float(np.mean(high_level_cycle_compute_s)), 1e-12)
            ),
        },
        "selected_command_force_prediction": {
            "sample_count": int(len(command_prediction_error)),
            "prediction_matches_selected_final_cem_action": bool(
                len(command_prediction_error) > 0
            ),
            "signed_error_executed_minus_predicted_mean_n": float(
                np.mean(command_prediction_error)
            )
            if len(command_prediction_error)
            else 0.0,
            "absolute_error_mean_n": float(
                np.mean(np.abs(command_prediction_error))
            )
            if len(command_prediction_error)
            else 0.0,
            "absolute_error_p95_n": float(
                np.percentile(np.abs(command_prediction_error), 95.0)
            )
            if len(command_prediction_error)
            else 0.0,
            "absolute_error_max_n": float(
                np.max(np.abs(command_prediction_error))
            )
            if len(command_prediction_error)
            else 0.0,
            "predicted_peak_n": float(np.max(command_prediction))
            if len(command_prediction)
            else 0.0,
            "executed_peak_n": float(np.max(command_execution))
            if len(command_execution)
            else 0.0,
        },
        "selected_control_path_command_force_prediction": {
            "sample_count": int(len(path_command_prediction_error)),
            "prediction_uses_selected_final_cem_action_at_each_5ms_hold_substep": bool(
                len(path_command_prediction_error) > 0
            ),
            "signed_error_executed_minus_predicted_mean_n": float(
                np.mean(path_command_prediction_error)
            )
            if len(path_command_prediction_error)
            else 0.0,
            "absolute_error_mean_n": float(
                np.mean(np.abs(path_command_prediction_error))
            )
            if len(path_command_prediction_error)
            else 0.0,
            "absolute_error_p95_n": float(
                np.percentile(np.abs(path_command_prediction_error), 95.0)
            )
            if len(path_command_prediction_error)
            else 0.0,
            "absolute_error_max_n": float(
                np.max(np.abs(path_command_prediction_error))
            )
            if len(path_command_prediction_error)
            else 0.0,
            "predicted_peak_n": float(np.max(path_command_prediction))
            if len(path_command_prediction)
            else 0.0,
            "executed_peak_n": float(np.max(path_command_execution))
            if len(path_command_execution)
            else 0.0,
        },
        "measurement_and_derivative_quality_god_view": {
            "mean_measurement_age_ms": float(1000.0 * np.mean(measurement_ages)),
            "max_measurement_age_ms": float(1000.0 * np.max(measurement_ages)),
            "mean_estimator_measurement_age_ms": float(
                1000.0 * np.mean(estimator_measurement_ages)
            ),
            "mean_mpc_state_measurement_age_ms": float(
                1000.0 * np.mean(mpc_measurement_ages)
            ),
            "mean_low_level_measurement_age_ms": float(
                1000.0 * np.mean(low_level_measurement_ages)
            ),
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
            "peak_total_cuff_moment_nm": float(np.max(moment_norm)),
            "rms_total_cuff_moment_nm": float(np.sqrt(np.mean(moment_norm**2))),
            "peak_abs_task_axial_force_n": float(np.max(np.abs(force_local[:, 0]))),
            "rms_parasitic_shear_force_n": float(np.sqrt(np.mean(np.sum(force_local[:, 1:] ** 2, axis=1)))),
            "peak_parasitic_shear_force_n": float(np.max(np.linalg.norm(force_local[:, 1:], axis=1))),
            "peak_abs_sagittal_cuff_moment_nm": float(np.max(np.abs(moment_local[:, 1]))),
            "peak_off_axis_cuff_moment_nm": float(np.max(np.linalg.norm(moment_local[:, [0, 2]], axis=1))),
            "rms_force_rate_n_s": float(np.sqrt(np.mean(force_rate_norm[1:] ** 2))) if len(force_rate_norm) > 1 else 0.0,
            "peak_force_rate_n_s": float(np.max(force_rate_norm)),
            "rms_moment_rate_nm_s": float(
                np.sqrt(np.mean(moment_rate_norm[1:] ** 2))
            ) if len(moment_rate_norm) > 1 else 0.0,
            "peak_moment_rate_nm_s": float(np.max(moment_rate_norm)),
        },
        "robot": {
            "peak_unclipped_torque_limit_fraction": float(np.max(torque_fractions)),
            "torque_saturation_control_samples": torque_saturation_count,
            "joint_position_limit_samples": robot_position_limit_count,
            "peak_abs_joint_velocity_deg_s": np.degrees(np.max(np.abs(robot_velocity), axis=0)).tolist(),
            "rms_joint_velocity_deg_s": np.degrees(
                np.sqrt(np.mean(robot_velocity**2, axis=0))
            ).tolist(),
            "peak_abs_commanded_joint_torque_nm": np.max(
                np.abs(np.array([item.joint_torque_command_nm for item in observations])),
                axis=0,
            ).tolist(),
            "rms_commanded_joint_torque_nm": np.sqrt(
                np.mean(
                    np.array(
                        [item.joint_torque_command_nm for item in observations]
                    )
                    ** 2,
                    axis=0,
                )
            ).tolist(),
        },
        "events": {
            "force_gate_events": force_gate_event_count,
            "peak_commanded_translational_force_n": (
                max(commanded_force_norms) if commanded_force_norms else 0.0
            ),
            "minimum_commanded_force_gate_margin_n": (
                CUFF_TRANSLATIONAL_FORCE_GATE_N - max(commanded_force_norms)
                if commanded_force_norms
                else CUFF_TRANSLATIONAL_FORCE_GATE_N
            ),
            "rom_event_samples": rom_event_count,
            "unintended_contact_pairs": [list(item) for item in sorted(unintended_contacts)],
            "mujoco_warning_counts": plant.warning_counts(),
            "mpc_solver_failures": mpc.failure_count,
        },
        "force_gate_n": CUFF_TRANSLATIONAL_FORCE_GATE_N,
        "moment_limit_nm": None,
        "mpc": {
            "interaction_aware": mpc.config.interaction_aware,
            "objective_contract": mpc.config.objective_contract(),
            "solve_count": mpc.solve_count,
            "failure_count": mpc.failure_count,
            "last_diagnostics": mpc.last_diagnostics,
        },
    }
    if reference_execution is not None:
        summary["reference_execution"] = {
            **reference_execution.summary(float(time[-1])),
            "mean_speed_scale": float(np.mean(execution_speed)),
            "minimum_observed_speed_scale": float(np.min(execution_speed)),
            "maximum_observed_speed_scale": float(np.max(execution_speed)),
            "final_reference_phase_time_s": float(execution_phase[-1]),
        }
    if hasattr(estimator, "trust_summary"):
        summary["hierarchical_trust"] = estimator.trust_summary()
    if distributed_cuff_enabled:
        station_force_world = np.asarray(station_forces_world)
        attachment_rotations = np.asarray(
            [item.attachment_rotation_matrix for item in observations]
        )
        station_force_local = np.einsum(
            "tji,tnj->tni", attachment_rotations, station_force_world
        )
        station_force_norm = np.linalg.norm(station_force_local, axis=2)
        station_shear_norm = np.linalg.norm(station_force_local[:, :, 1:], axis=2)
        relative_translation = np.asarray(station_relative_translations)
        center_relative_translation = np.asarray(center_relative_translations)
        station_offsets = np.asarray(truth.station_offsets_m)
        force_balance_residual = np.linalg.norm(
            np.sum(station_force_world, axis=1)
            - np.asarray([item.cuff_force_vector_n for item in observations]),
            axis=1,
        )
        summary["cuff_plant"] = {
            "mechanics": "finite_length_four_station_translational_coupling",
            "robot_to_cuff_connection": "rigid",
            "station_direct_moments": False,
            "resultant_wrench_only_to_estimator_controller": True,
            "center_placement_sc_m_god_view_plant_only": true_human.sleeve_center_m,
            "config": plant.cuff_config.as_dict(),
            "station_force_distribution_engineering": {
                "station_offsets_m": station_offsets.tolist(),
                "peak_force_norm_n": np.max(station_force_norm, axis=0).tolist(),
                "rms_force_norm_n": np.sqrt(
                    np.mean(station_force_norm**2, axis=0)
                ).tolist(),
                "peak_abs_axial_force_n": np.max(
                    np.abs(station_force_local[:, :, 0]), axis=0
                ).tolist(),
                "peak_transverse_force_n": np.max(
                    station_shear_norm, axis=0
                ).tolist(),
                "proximal_station_peak_force_n": float(
                    np.max(station_force_norm[:, 0])
                ),
                "distal_station_peak_force_n": float(
                    np.max(station_force_norm[:, -1])
                ),
                "peak_sum_station_force_balance_residual_n": float(
                    np.max(force_balance_residual)
                ),
            },
            "relative_motion": {
                "peak_center_translation_mm": float(
                    1000.0
                    * np.max(np.linalg.norm(center_relative_translation, axis=1))
                ),
                "peak_station_translation_mm": float(
                    1000.0 * np.max(np.linalg.norm(relative_translation, axis=2))
                ),
                "peak_station_translation_mm_per_station": (
                    1000.0
                    * np.max(np.linalg.norm(relative_translation, axis=2), axis=0)
                ).tolist(),
                "peak_cuff_shank_rotation_deg": float(
                    np.degrees(np.max(cuff_shank_relative_rotations))
                ),
            },
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
        "allocated_sagittal_wrench": np.asarray(allocated_sagittal_wrenches),
        "allocation_equality_residual_nm": np.asarray(
            allocation_equality_residuals
        ),
        "geometry_estimate": np.asarray(geometry_estimates),
        "dynamic_base_estimate": np.asarray(dynamic_estimates),
        "estimator_status_code": np.asarray(estimator_status),
        "control_time_s": control_time,
        "control_estimated_state": control_state_est,
        "control_true_q_rad_god_view": np.asarray(control_true_q),
        "control_true_dq_rad_s_god_view": control_dq_true,
        "measurement_age_s": np.asarray(measurement_ages),
        "estimator_measurement_age_s": np.asarray(estimator_measurement_ages),
        "mpc_state_measurement_age_s": np.asarray(mpc_measurement_ages),
        "low_level_measurement_age_s": np.asarray(low_level_measurement_ages),
        "measurement_new_sample": np.asarray(measurement_new, dtype=bool),
        "measured_cuff_force_world_n": measured_force_array,
        "measured_cuff_moment_world_nm": measured_moment_array,
        "bed_force_n_god_view": np.array([item.bed_force_n for item in observations]),
        "tracking_error_deg_god_view": tracking_deg,
        "cuff_wrench_local_god_view": np.column_stack([force_local, moment_local]),
        "reference_phase_time_s": execution_phase,
        "reference_speed_scale": execution_speed,
        "reference_speed_scale_rate_per_s": execution_speed_rate,
        "geometry_confidence_level": geometry_confidence,
        "dynamic_confidence_level": dynamic_confidence,
        "combined_confidence_level": combined_confidence,
        "geometry_model_confidence": geometry_model_confidence,
        "dynamic_model_confidence": dynamic_model_confidence,
        "combined_model_confidence_raw": combined_model_confidence_raw,
        "filtered_model_confidence": filtered_model_confidence,
        "execution_confidence_high": execution_confidence_high,
        "geometry_information_confidence": geometry_information_confidence,
        "dynamic_information_confidence": dynamic_information_confidence,
        "combined_information_confidence": combined_information_confidence,
        "force_speed_scale": np.asarray(
            [item.get("force_speed_scale", 1.0) for item in execution_statuses],
            dtype=float,
        ),
        "force_speed_target_scale": np.asarray(
            [
                item.get("force_speed_target_scale", 1.0)
                for item in execution_statuses
            ],
            dtype=float,
        ),
        "force_recovery_mode_code": np.asarray(
            [item.get("force_recovery_mode_code", 0.0) for item in execution_statuses],
            dtype=float,
        ),
        "force_recovery_hold_active": np.asarray(
            [item.get("force_recovery_hold_active", 0.0) for item in execution_statuses],
            dtype=float,
        ),
        "governor_predicted_peak_command_force_n": np.asarray(
            [
                item.get("governor_predicted_peak_command_force_n", 0.0)
                for item in execution_statuses
            ],
            dtype=float,
        ),
        "commanded_force_time_s": np.asarray(commanded_force_times),
        "commanded_translational_force_norm_n": np.asarray(
            commanded_force_norms
        ),
        "mpc_selection_time_s": np.asarray(mpc_selection_times),
        "mpc_selected_alpha": np.asarray(mpc_selected_alphas),
        "mpc_selected_predicted_command_force_n": command_prediction,
        "mpc_selected_executed_command_force_n": command_execution,
        "mpc_selected_command_force_prediction_error_n": (
            command_prediction_error
        ),
        "mpc_control_path_prediction_time_s": np.asarray(
            mpc_path_prediction_times
        ),
        "mpc_control_path_predicted_command_force_n": path_command_prediction,
        "mpc_control_path_executed_command_force_n": path_command_execution,
        "mpc_control_path_command_force_prediction_error_n": (
            path_command_prediction_error
        ),
        "mpc_cycle_compute_ms": 1000.0 * np.asarray(mpc_compute_s),
        "mpc_cycle_time_s": np.asarray(mpc_compute_times_s),
        "high_level_cycle_compute_ms": (
            1000.0 * np.asarray(high_level_cycle_compute_s)
        ),
    }
    if distributed_cuff_enabled:
        trace.update(
            {
                "station_force_world_n": np.asarray(station_forces_world),
                "station_relative_translation_world_m": np.asarray(
                    station_relative_translations
                ),
                "cuff_center_relative_translation_world_m": np.asarray(
                    center_relative_translations
                ),
                "cuff_shank_relative_rotation_rad": np.asarray(
                    cuff_shank_relative_rotations
                ),
            }
        )
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
