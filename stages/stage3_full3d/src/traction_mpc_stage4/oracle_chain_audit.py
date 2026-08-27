"""Offline oracle audit for the Stage-4 measurement/estimator/prediction chain.

Oracle quantities in this module are evaluation-only.  They are never passed
to the estimator and never affect a saved controller rollout.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import HIP_HEIGHT_M
from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .adaptive_estimators import IntegralAdaptiveHumanEstimator
from .dynamics_failure_audit import bound_diagnostics, unconstrained_candidate
from .estimator_v2 import PlanarCuffGeometry, dynamic_regressor_row, nominal_base_parameters
from .evaluation import BED_CONTACT_CONTAMINATION_FORCE_N
from .human_model import registered_cold_start_perturbed_human
from .measurement import CausalMeasurementLayer, MeasurementCase
from .reference import cold_start_teaching_reference


@dataclass(frozen=True)
class _ReplayTruth:
    time_s: float
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    attachment_position_m: np.ndarray
    attachment_rotation_matrix: np.ndarray
    attachment_velocity_m_s: np.ndarray
    attachment_angular_velocity_rad_s: np.ndarray
    cuff_force_vector_n: np.ndarray
    cuff_moment_vector_nm: np.ndarray


def _nearest_indices(reference: np.ndarray, query: np.ndarray) -> np.ndarray:
    right = np.searchsorted(reference, query, side="left")
    right = np.clip(right, 0, len(reference) - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(query - reference[left]) <= np.abs(reference[right] - query)
    return np.where(choose_left, left, right)


def _true_geometry(
    human: Any,
    initial_position_world_m: np.ndarray,
    initial_rotation_world_from_cuff: np.ndarray,
    initial_q_rad: np.ndarray,
) -> PlanarCuffGeometry:
    q1, q2 = np.asarray(initial_q_rad, dtype=float)
    phi = q1 - q2
    rotation = np.asarray(initial_rotation_world_from_cuff, dtype=float)
    cuff_x = rotation[:, 0]
    cuff_z = rotation[:, 2]
    plane_x = math.cos(phi) * cuff_x - math.sin(phi) * cuff_z
    plane_z = math.sin(phi) * cuff_x + math.cos(phi) * cuff_z
    axis = rotation[:, 1].copy()
    thigh_vector = human.thigh_length_m * (
        math.cos(q1) * plane_x + math.sin(q1) * plane_z
    )
    cuff_vector = human.sleeve_center_m * (
        math.cos(phi) * plane_x + math.sin(phi) * plane_z
    )
    origin = np.asarray(initial_position_world_m, dtype=float) - thigh_vector - cuff_vector
    return PlanarCuffGeometry(
        origin_world_m=origin,
        plane_x_world=plane_x,
        joint_axis_world=axis,
        plane_z_world=plane_z,
        hip_plane_m=np.zeros(2),
        thigh_length_m=float(human.thigh_length_m),
        knee_to_cuff_in_cuff_m=np.array([human.sleeve_center_m, 0.0]),
    )


def _vector_metrics(error: np.ndarray, scale: float = 1.0) -> dict[str, Any]:
    values = scale * np.asarray(error, dtype=float)
    norms = np.linalg.norm(values, axis=1)
    if not len(values):
        return {
            "bias": [],
            "component_rmse": [],
            "combined_rmse": float("nan"),
            "peak_norm": float("nan"),
        }
    return {
        "bias": np.mean(values, axis=0).tolist(),
        "component_rmse": np.sqrt(np.mean(values**2, axis=0)).tolist(),
        "combined_rmse": float(np.sqrt(np.mean(values**2))),
        "peak_norm": float(np.max(norms)),
    }


def _rotation_error_vectors(
    measured: np.ndarray, truth: np.ndarray
) -> np.ndarray:
    return np.asarray(
        [
            Rotation.from_matrix(measured_item @ truth_item.T).as_rotvec()
            for measured_item, truth_item in zip(measured, truth, strict=True)
        ]
    )


def _trend(values: np.ndarray, time_s: np.ndarray) -> list[float]:
    raw = np.asarray(values, dtype=float)
    time = np.asarray(time_s, dtype=float)
    if len(time) < 2:
        return [float("nan")] * raw.shape[1]
    design = np.column_stack([np.ones(len(time)), time - time[0]])
    coefficients, *_ = np.linalg.lstsq(design, raw, rcond=None)
    return coefficients[1].tolist()


def _rmse(error: np.ndarray, clean: np.ndarray) -> dict[str, Any]:
    values = np.asarray(error, dtype=float)[np.asarray(clean, dtype=bool)]
    if not len(values):
        return {
            "combined_rmse_nm": float("nan"),
            "per_joint_rmse_nm": [float("nan"), float("nan")],
            "sample_count": 0,
        }
    return {
        "combined_rmse_nm": float(np.sqrt(np.mean(values**2))),
        "per_joint_rmse_nm": np.sqrt(np.mean(values**2, axis=0)).tolist(),
        "sample_count": int(len(values)),
    }


def _beta_distance(beta: np.ndarray, target: np.ndarray, span: np.ndarray) -> float:
    return float(np.linalg.norm((np.asarray(beta) - np.asarray(target)) / span))


def _geometry_metrics(geometry: PlanarCuffGeometry, human: Any) -> dict[str, float]:
    hip_world = (
        geometry.origin_world_m
        + geometry.hip_plane_m[0] * geometry.plane_x_world
        + geometry.hip_plane_m[1] * geometry.plane_z_world
    )
    alignment_deg = math.degrees(
        math.atan2(
            float(geometry.knee_to_cuff_in_cuff_m[1]),
            float(geometry.knee_to_cuff_in_cuff_m[0]),
        )
    )
    return {
        "hip_position_error_mm": float(
            1000.0 * np.linalg.norm(hip_world - np.array([0.0, 0.0, HIP_HEIGHT_M]))
        ),
        "thigh_length_error_percent": float(
            100.0
            * (geometry.thigh_length_m - human.thigh_length_m)
            / human.thigh_length_m
        ),
        "cuff_distance_error_percent": float(
            100.0
            * (geometry.cuff_distance_m - human.sleeve_center_m)
            / human.sleeve_center_m
        ),
        "joint_axis_error_deg": float(
            math.degrees(
                math.acos(
                    np.clip(
                        abs(float(geometry.joint_axis_world @ np.array([0.0, 1.0, 0.0]))),
                        -1.0,
                        1.0,
                    )
                )
            )
        ),
        "cuff_alignment_error_deg": alignment_deg,
    }


def _model_predictions(beta: np.ndarray, states: np.ndarray, ddq: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            dynamic_regressor_row(state[:2], state[2:], acceleration) @ beta
            for state, acceleration in zip(states, ddq, strict=True)
        ]
    )


def _prediction_metrics(
    beta: np.ndarray,
    *,
    estimated_states: np.ndarray,
    estimated_ddq: np.ndarray,
    true_sample_states: np.ndarray,
    true_sample_ddq: np.ndarray,
    true_arrival_states: np.ndarray,
    true_arrival_ddq: np.ndarray,
    measurement_target: np.ndarray,
    measurement_target_true_geometry: np.ndarray,
    oracle_wrench_target_true_geometry: np.ndarray,
    true_beta: np.ndarray,
    clean_sample: np.ndarray,
    clean_arrival: np.ndarray,
) -> dict[str, Any]:
    predicted_chain = _model_predictions(beta, estimated_states, estimated_ddq)
    oracle_sample = _model_predictions(true_beta, true_sample_states, true_sample_ddq)
    oracle_arrival = _model_predictions(true_beta, true_arrival_states, true_arrival_ddq)
    parameter_only = _model_predictions(beta, true_sample_states, true_sample_ddq)
    state_geometry_only = _model_predictions(
        true_beta, estimated_states, estimated_ddq
    )
    return {
        "E_meas_instantaneous": _rmse(
            predicted_chain - measurement_target, clean_sample
        ),
        "E_oracle_sample_aligned_full_chain": _rmse(
            predicted_chain - oracle_sample, clean_sample
        ),
        "E_oracle_arrival_aligned_full_chain": _rmse(
            predicted_chain - oracle_arrival, clean_arrival
        ),
        "E_oracle_parameter_only": _rmse(
            parameter_only - oracle_sample, clean_sample
        ),
        "E_oracle_state_geometry_only_with_true_beta": _rmse(
            state_geometry_only - oracle_sample, clean_sample
        ),
        "measurement_target_to_oracle": _rmse(
            measurement_target - oracle_sample, clean_sample
        ),
        "measurement_target_true_geometry_to_oracle": _rmse(
            measurement_target_true_geometry - oracle_sample, clean_sample
        ),
        "oracle_wrench_target_true_geometry_to_oracle": _rmse(
            oracle_wrench_target_true_geometry - oracle_sample, clean_sample
        ),
        "estimated_vs_true_geometry_generalized_input": _rmse(
            measurement_target - measurement_target_true_geometry, clean_sample
        ),
    }


def _effective_q_lag_ms(
    measurement_q: np.ndarray,
    arrival_time: np.ndarray,
    true_time: np.ndarray,
    true_q: np.ndarray,
) -> dict[str, float]:
    lags = np.arange(0.0, 0.201, 0.005)
    errors = []
    for lag in lags:
        comparison = np.column_stack(
            [
                np.interp(arrival_time - lag, true_time, true_q[:, joint])
                for joint in range(2)
            ]
        )
        errors.append(float(np.sqrt(np.mean((measurement_q - comparison) ** 2))))
    best = int(np.argmin(errors))
    return {
        "best_grid_lag_ms": float(1000.0 * lags[best]),
        "rmse_at_best_lag_deg": float(np.degrees(errors[best])),
        "lag_grid_step_ms": 5.0,
    }


def audit_saved_sensor_case(
    source_dir: Path,
    case: MeasurementCase,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Replay one saved truth trajectory through the unchanged current frontend/estimator."""

    path = Path(source_dir) / f"{case.name}_trace.npz"
    with np.load(path) as stored:
        trace = {name: stored[name] for name in stored.files}
    human, metadata = registered_cold_start_perturbed_human()
    true_beta = nominal_base_parameters(human)

    time_low = np.asarray(trace["time_s"], dtype=float)
    control_time = np.asarray(trace["control_time_s"], dtype=float)
    low_index = _nearest_indices(time_low, control_time)
    robot_q = np.asarray(trace["robot_q_rad"], dtype=float)[low_index]
    robot_dq = np.asarray(trace["robot_dq_rad_s"], dtype=float)[low_index]
    force_local = np.asarray(trace["cuff_force_local_n_god_view"], dtype=float)[low_index]
    moment_local = np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float)[low_index]
    bed_force = np.asarray(trace["bed_force_n_god_view"], dtype=float)[low_index]
    true_q = np.asarray(trace["control_true_q_rad_god_view"], dtype=float)
    true_dq = np.asarray(trace["control_true_dq_rad_s_god_view"], dtype=float)
    true_ddq = np.gradient(true_dq, control_time, axis=0, edge_order=2)

    robot = UR10eTorqueRobot()
    positions = []
    rotations = []
    linear_velocities = []
    angular_velocities = []
    force_world = []
    moment_world = []
    truths = []
    initial_q = cold_start_teaching_reference(0.0).q_rad
    robot.set_configuration(robot_q[0], robot_dq[0])
    robot_initial_position = robot.attachment_pose().translation
    q1_initial, q2_initial = initial_q
    phi_initial = q1_initial - q2_initial
    physical_initial_position = np.array(
        [
            human.thigh_length_m * math.cos(q1_initial)
            + human.sleeve_center_m * math.cos(phi_initial),
            0.0,
            HIP_HEIGHT_M
            + human.thigh_length_m * math.sin(q1_initial)
            + human.sleeve_center_m * math.sin(phi_initial),
        ]
    )
    coupled_world_translation = physical_initial_position - robot_initial_position
    for t, q_robot, dq_robot, local_f, local_m in zip(
        control_time, robot_q, robot_dq, force_local, moment_local, strict=True
    ):
        robot.set_configuration(q_robot, dq_robot)
        pose = robot.attachment_pose()
        twist = robot.attachment_jacobian() @ dq_robot
        world_f = pose.rotation @ local_f
        world_m = pose.rotation @ local_m
        position_world = pose.translation + coupled_world_translation
        positions.append(position_world.copy())
        rotations.append(pose.rotation.copy())
        linear_velocities.append(twist[:3].copy())
        angular_velocities.append(twist[3:].copy())
        force_world.append(world_f)
        moment_world.append(world_m)
        truths.append(
            _ReplayTruth(
                float(t),
                q_robot.copy(),
                dq_robot.copy(),
                position_world.copy(),
                pose.rotation.copy(),
                twist[:3].copy(),
                twist[3:].copy(),
                world_f.copy(),
                world_m.copy(),
            )
        )
    positions = np.asarray(positions)
    rotations = np.asarray(rotations)
    linear_velocities = np.asarray(linear_velocities)
    angular_velocities = np.asarray(angular_velocities)
    force_world = np.asarray(force_world)
    moment_world = np.asarray(moment_world)
    true_geometry = _true_geometry(
        human, positions[0], rotations[0], initial_q
    )

    layer = CausalMeasurementLayer(case, truths[0])
    measurements = [layer.update(item) for item in truths]
    sample_time = np.asarray([item.sample_time_s for item in measurements])
    sample_index = _nearest_indices(control_time, sample_time)
    measured_position = np.asarray([item.attachment_position_m for item in measurements])
    measured_rotation = np.asarray(
        [item.attachment_rotation_matrix for item in measurements]
    )
    measured_linear = np.asarray([item.attachment_velocity_m_s for item in measurements])
    measured_angular = np.asarray(
        [item.attachment_angular_velocity_rad_s for item in measurements]
    )
    measured_force = np.asarray([item.cuff_force_vector_n for item in measurements])
    measured_moment = np.asarray([item.cuff_moment_vector_nm for item in measurements])
    measured_robot_q = np.asarray([item.robot_q_rad for item in measurements])
    measured_robot_dq = np.asarray([item.robot_dq_rad_s for item in measurements])
    measured_frontend_state = np.asarray(
        [
            true_geometry.estimate_state(position, rotation, linear, angular)
            for position, rotation, linear, angular in zip(
                measured_position,
                measured_rotation,
                measured_linear,
                measured_angular,
                strict=True,
            )
        ]
    )

    recorded_force = np.asarray(trace["measured_cuff_force_world_n"], dtype=float)
    recorded_moment = np.asarray(trace["measured_cuff_moment_world_nm"], dtype=float)
    replay_validation = {
        "maximum_force_difference_from_saved_trace_n": float(
            np.max(np.abs(measured_force - recorded_force))
        ),
        "maximum_moment_difference_from_saved_trace_nm": float(
            np.max(np.abs(measured_moment - recorded_moment))
        ),
    }

    aligned_q = true_q[sample_index]
    aligned_dq = true_dq[sample_index]
    measurement = {
        "duration_s": float(control_time[-1]),
        "sample_count": int(len(control_time)),
        "new_sample_count": int(sum(item.new_sample for item in measurements)),
        "mean_age_ms": float(1000.0 * np.mean(control_time - sample_time)),
        "max_age_ms": float(1000.0 * np.max(control_time - sample_time)),
        "new_sample_fraction": float(np.mean([item.new_sample for item in measurements])),
        "aligned": {
            "human_q_deg": _vector_metrics(measured_frontend_state[:, :2] - aligned_q, 180.0 / math.pi),
            "human_dq_deg_s": _vector_metrics(measured_frontend_state[:, 2:] - aligned_dq, 180.0 / math.pi),
            "cuff_position_mm": _vector_metrics(measured_position - positions[sample_index], 1000.0),
            "cuff_orientation_deg": _vector_metrics(
                _rotation_error_vectors(measured_rotation, rotations[sample_index]),
                180.0 / math.pi,
            ),
            "cuff_force_n": _vector_metrics(measured_force - force_world[sample_index]),
            "cuff_moment_nm": _vector_metrics(measured_moment - moment_world[sample_index]),
            "robot_q_deg": _vector_metrics(measured_robot_q - robot_q[sample_index], 180.0 / math.pi),
            "robot_dq_deg_s": _vector_metrics(measured_robot_dq - robot_dq[sample_index], 180.0 / math.pi),
        },
        "arrival_aligned": {
            "human_q_deg": _vector_metrics(measured_frontend_state[:, :2] - true_q, 180.0 / math.pi),
            "human_dq_deg_s": _vector_metrics(measured_frontend_state[:, 2:] - true_dq, 180.0 / math.pi),
            "cuff_position_mm": _vector_metrics(measured_position - positions, 1000.0),
            "cuff_orientation_deg": _vector_metrics(
                _rotation_error_vectors(measured_rotation, rotations), 180.0 / math.pi
            ),
            "cuff_force_n": _vector_metrics(measured_force - force_world),
            "cuff_moment_nm": _vector_metrics(measured_moment - moment_world),
        },
        "aligned_force_error_linear_trend_n_s": _trend(
            measured_force - force_world[sample_index], control_time
        ),
        "aligned_moment_error_linear_trend_nm_s": _trend(
            measured_moment - moment_world[sample_index], control_time
        ),
        "effective_human_q_lag": _effective_q_lag_ms(
            measured_frontend_state[:, :2], control_time, control_time, true_q
        ),
        "deterministic_replay_validation": replay_validation,
    }

    high_level_index = np.arange(0, len(control_time), 4, dtype=int)
    first = measurements[0]
    estimator = IntegralAdaptiveHumanEstimator(
        first.attachment_position_m,
        first.attachment_rotation_matrix,
        initial_q,
        use_state_ukf=False,
        initial_time_s=first.sample_time_s,
    )
    estimated_states = []
    true_sample_states = []
    true_arrival_states = []
    high_sample_times = []
    high_arrival_times = []
    measurement_targets = []
    measurement_targets_true_geometry = []
    oracle_wrench_targets_true_geometry = []
    clean_sample = []
    clean_arrival = []
    geometry_history = []
    beta_history = []
    attempt_records: list[dict[str, Any]] = []
    for high_count, control_index in enumerate(high_level_index):
        measured = measurements[control_index]
        before_beta = estimator.dynamic_identifier.last_valid.copy()
        state, diagnostics = estimator.observe(
            time_s=measured.sample_time_s,
            position_world_m=measured.attachment_position_m,
            rotation_world_from_cuff=measured.attachment_rotation_matrix,
            linear_velocity_world_m_s=measured.attachment_velocity_m_s,
            angular_velocity_world_rad_s=measured.attachment_angular_velocity_rad_s,
            force_world_n=measured.cuff_force_vector_n,
            moment_world_nm=measured.cuff_moment_vector_nm,
            bed_contaminated=False,
        )
        sample_i = sample_index[control_index]
        estimated_states.append(state.copy())
        true_sample_states.append(np.concatenate([true_q[sample_i], true_dq[sample_i]]))
        true_arrival_states.append(np.concatenate([true_q[control_index], true_dq[control_index]]))
        high_sample_times.append(measured.sample_time_s)
        high_arrival_times.append(control_time[control_index])
        measurement_targets.append(
            estimator.geometry.generalized_input_from_wrench(
                state[:2], measured.cuff_force_vector_n, measured.cuff_moment_vector_nm
            )
        )
        frontend_state = true_geometry.estimate_state(
            measured.attachment_position_m,
            measured.attachment_rotation_matrix,
            measured.attachment_velocity_m_s,
            measured.attachment_angular_velocity_rad_s,
        )
        measurement_targets_true_geometry.append(
            true_geometry.generalized_input_from_wrench(
                frontend_state[:2],
                measured.cuff_force_vector_n,
                measured.cuff_moment_vector_nm,
            )
        )
        oracle_wrench_targets_true_geometry.append(
            true_geometry.generalized_input_from_wrench(
                true_q[sample_i], force_world[sample_i], moment_world[sample_i]
            )
        )
        clean_sample.append(
            bed_force[sample_i] <= BED_CONTACT_CONTAMINATION_FORCE_N
            and np.linalg.norm(soft_limit_torque(true_q[sample_i], true_dq[sample_i], human)) <= 1e-8
        )
        clean_arrival.append(
            bed_force[control_index] <= BED_CONTACT_CONTAMINATION_FORCE_N
            and np.linalg.norm(soft_limit_torque(true_q[control_index], true_dq[control_index], human)) <= 1e-8
        )
        geometry_history.append(_geometry_metrics(estimator.geometry, human))
        beta_history.append(estimator.dynamic_identifier.last_valid.copy())
        dynamic = diagnostics["dynamics"]
        if dynamic.get("attempted", False):
            regressor, target, _ = estimator.dynamic_identifier._integral_blocks(
                estimator.raw_history, estimator.geometry
            )
            raw_beta = unconstrained_candidate(
                estimator.dynamic_identifier, regressor, target
            )
            candidate = np.asarray(dynamic["candidate"], dtype=float)
            applied = np.asarray(dynamic["applied"], dtype=float)
            span = estimator.dynamic_identifier.span
            attempt_records.append(
                {
                    "attempt_index": len(attempt_records),
                    "high_level_index": high_count,
                    "arrival_time_s": float(control_time[control_index]),
                    "sample_time_s": float(measured.sample_time_s),
                    "accepted": bool(dynamic["accepted"]),
                    "reason": dynamic["reason"],
                    "rank": int(dynamic["rank"]),
                    "rrqr_rank": int(dynamic["rrqr_rank"]),
                    "condition_number": float(dynamic["condition_number"]),
                    "candidate_residual_rms_nms": float(dynamic["candidate_residual_rms_nms"]),
                    "old_residual_rms_nms": float(dynamic["old_residual_rms_nms"]),
                    "bound_hit": bool(dynamic["bound_hit"]),
                    "positive_definite_mass_matrix": bool(dynamic["positive_definite_mass_matrix"]),
                    "candidate_beta": candidate.tolist(),
                    "unconstrained_beta": raw_beta.tolist(),
                    "last_valid_before_beta": before_beta.tolist(),
                    "last_valid_after_beta": applied.tolist(),
                    "active_or_pressured_bounds": bound_diagnostics(
                        estimator.dynamic_identifier, candidate, raw_beta
                    ),
                    "candidate_distance_to_truth_span_l2": _beta_distance(candidate, true_beta, span),
                    "last_valid_before_distance_to_truth_span_l2": _beta_distance(before_beta, true_beta, span),
                    "last_valid_after_distance_to_truth_span_l2": _beta_distance(applied, true_beta, span),
                    "last_valid_after_distance_to_prior_span_l2": _beta_distance(
                        applied, estimator.dynamic_identifier.population_prior, span
                    ),
                }
            )

    estimated_states_array = np.asarray(estimated_states)
    true_sample_states_array = np.asarray(true_sample_states)
    true_arrival_states_array = np.asarray(true_arrival_states)
    high_sample_times_array = np.asarray(high_sample_times)
    high_arrival_times_array = np.asarray(high_arrival_times)
    measurement_targets_array = np.asarray(measurement_targets)
    measurement_targets_true_geometry_array = np.asarray(
        measurement_targets_true_geometry
    )
    oracle_wrench_targets_true_geometry_array = np.asarray(
        oracle_wrench_targets_true_geometry
    )
    clean_sample_array = np.asarray(clean_sample, dtype=bool)
    clean_arrival_array = np.asarray(clean_arrival, dtype=bool)
    estimated_ddq = np.gradient(
        estimated_states_array[:, 2:], high_arrival_times_array, axis=0, edge_order=2
    )
    sample_ddq = np.column_stack(
        [
            np.interp(high_sample_times_array, control_time, true_ddq[:, joint])
            for joint in range(2)
        ]
    )
    arrival_ddq = np.column_stack(
        [
            np.interp(high_arrival_times_array, control_time, true_ddq[:, joint])
            for joint in range(2)
        ]
    )
    for attempt in attempt_records:
        stop = int(attempt["high_level_index"]) + 1
        arguments = {
            "estimated_states": estimated_states_array[:stop],
            "estimated_ddq": estimated_ddq[:stop],
            "true_sample_states": true_sample_states_array[:stop],
            "true_sample_ddq": sample_ddq[:stop],
            "true_arrival_states": true_arrival_states_array[:stop],
            "true_arrival_ddq": arrival_ddq[:stop],
            "measurement_target": measurement_targets_array[:stop],
            "measurement_target_true_geometry": measurement_targets_true_geometry_array[:stop],
            "oracle_wrench_target_true_geometry": oracle_wrench_targets_true_geometry_array[:stop],
            "true_beta": true_beta,
            "clean_sample": clean_sample_array[:stop],
            "clean_arrival": clean_arrival_array[:stop],
        }
        attempt["candidate_prediction"] = _prediction_metrics(
            np.asarray(attempt["candidate_beta"]), **arguments
        )
        attempt["last_valid_after_prediction"] = _prediction_metrics(
            np.asarray(attempt["last_valid_after_beta"]), **arguments
        )
        attempt["last_valid_before_prediction"] = _prediction_metrics(
            np.asarray(attempt["last_valid_before_beta"]), **arguments
        )
        before_prediction = attempt["last_valid_before_prediction"]
        candidate_prediction = attempt["candidate_prediction"]
        attempt["candidate_measurement_fit_improves_without_oracle_improvement"] = bool(
            candidate_prediction["E_meas_instantaneous"]["combined_rmse_nm"]
            < before_prediction["E_meas_instantaneous"]["combined_rmse_nm"]
            and candidate_prediction["E_oracle_sample_aligned_full_chain"]["combined_rmse_nm"]
            >= before_prediction["E_oracle_sample_aligned_full_chain"]["combined_rmse_nm"]
        )
        attempt["accepted_update_movement"] = (
            "not_accepted"
            if not attempt["accepted"]
            else (
                "toward_truth"
                if attempt["last_valid_after_distance_to_truth_span_l2"]
                < attempt["last_valid_before_distance_to_truth_span_l2"]
                else "away_from_truth"
            )
        )

    final_beta = estimator.dynamic_identifier.last_valid.copy()
    span = estimator.dynamic_identifier.span
    prior = estimator.dynamic_identifier.population_prior
    final_prediction = _prediction_metrics(
        final_beta,
        estimated_states=estimated_states_array,
        estimated_ddq=estimated_ddq,
        true_sample_states=true_sample_states_array,
        true_sample_ddq=sample_ddq,
        true_arrival_states=true_arrival_states_array,
        true_arrival_ddq=arrival_ddq,
        measurement_target=measurement_targets_array,
        measurement_target_true_geometry=measurement_targets_true_geometry_array,
        oracle_wrench_target_true_geometry=oracle_wrench_targets_true_geometry_array,
        true_beta=true_beta,
        clean_sample=clean_sample_array,
        clean_arrival=clean_arrival_array,
    )
    prior_prediction = _prediction_metrics(
        prior,
        estimated_states=estimated_states_array,
        estimated_ddq=estimated_ddq,
        true_sample_states=true_sample_states_array,
        true_sample_ddq=sample_ddq,
        true_arrival_states=true_arrival_states_array,
        true_arrival_ddq=arrival_ddq,
        measurement_target=measurement_targets_array,
        measurement_target_true_geometry=measurement_targets_true_geometry_array,
        oracle_wrench_target_true_geometry=oracle_wrench_targets_true_geometry_array,
        true_beta=true_beta,
        clean_sample=clean_sample_array,
        clean_arrival=clean_arrival_array,
    )
    parameter_rows = []
    for index, name in enumerate(estimator.dynamic_identifier.parameter_estimate()):
        parameter_rows.append(
            {
                "name": name,
                "population_prior": float(prior[index]),
                "registered_true": float(true_beta[index]),
                "final_last_valid": float(final_beta[index]),
                "normalized_error_fraction_of_span": float(
                    (final_beta[index] - true_beta[index]) / span[index]
                ),
                "absolute_error": float(final_beta[index] - true_beta[index]),
            }
        )
    accepted = [item for item in attempt_records if item["accepted"]]
    estimator_summary = {
        "architecture": "current_integral_minimal_offline_replay",
        "oracle_entered_estimator": False,
        "geometry": {
            "trustworthy_time_s": estimator.geometry_identifier.trustworthy_time_s,
            "accepted_updates": estimator.geometry_identifier.accepted_updates,
            "rejected_updates": estimator.geometry_identifier.rejected_updates,
            "final": _geometry_metrics(estimator.geometry, human),
            "state_sample_aligned_q_deg": _vector_metrics(
                estimated_states_array[:, :2] - true_sample_states_array[:, :2],
                180.0 / math.pi,
            ),
            "state_sample_aligned_dq_deg_s": _vector_metrics(
                estimated_states_array[:, 2:] - true_sample_states_array[:, 2:],
                180.0 / math.pi,
            ),
            "state_arrival_aligned_q_deg": _vector_metrics(
                estimated_states_array[:, :2] - true_arrival_states_array[:, :2],
                180.0 / math.pi,
            ),
            "state_arrival_aligned_dq_deg_s": _vector_metrics(
                estimated_states_array[:, 2:] - true_arrival_states_array[:, 2:],
                180.0 / math.pi,
            ),
        },
        "dynamics": {
            "trustworthy_time_s": estimator.dynamic_identifier.trustworthy_time_s,
            "accepted_updates": estimator.dynamic_identifier.accepted_updates,
            "rejected_updates": estimator.dynamic_identifier.rejected_updates,
            "attempt_count": len(attempt_records),
            "active_bound_attempt_count": int(sum(item["bound_hit"] for item in attempt_records)),
            "population_prior_distance_to_truth_span_l2": _beta_distance(prior, true_beta, span),
            "final_distance_to_truth_span_l2": _beta_distance(final_beta, true_beta, span),
            "accepted_updates_toward_truth": int(
                sum(item["accepted_update_movement"] == "toward_truth" for item in accepted)
            ),
            "accepted_updates_away_from_truth": int(
                sum(item["accepted_update_movement"] == "away_from_truth" for item in accepted)
            ),
            "parameters": parameter_rows,
            "attempts": attempt_records,
        },
    }
    prediction_summary = {
        "population_prior": prior_prediction,
        "final_last_valid": final_prediction,
        "sensor_bias_compensation_flag": bool(
            final_prediction["E_meas_instantaneous"]["combined_rmse_nm"]
            < prior_prediction["E_meas_instantaneous"]["combined_rmse_nm"]
            and final_prediction["E_oracle_sample_aligned_full_chain"]["combined_rmse_nm"]
            >= prior_prediction["E_oracle_sample_aligned_full_chain"]["combined_rmse_nm"]
        ),
        "warning": (
            "Instantaneous prediction uses offline qdd differentiation; exact online "
            "candidate residual remains candidate_residual_rms_nms."
        ),
    }
    details = {
        "control_time_s": control_time,
        "sample_time_s": sample_time,
        "measurement_frontend_state": measured_frontend_state,
        "true_state_arrival": np.column_stack([true_q, true_dq]),
        "true_state_sample": np.column_stack([aligned_q, aligned_dq]),
        "measured_position_m": measured_position,
        "true_position_arrival_m": positions,
        "true_position_sample_m": positions[sample_index],
        "measured_force_world_n": measured_force,
        "true_force_arrival_world_n": force_world,
        "true_force_sample_world_n": force_world[sample_index],
        "high_level_time_s": high_arrival_times_array,
        "high_level_sample_time_s": high_sample_times_array,
        "high_level_new_sample": np.asarray(
            [measurements[index].new_sample for index in high_level_index],
            dtype=bool,
        ),
        "high_level_measured_position_m": measured_position[high_level_index],
        "high_level_measured_rotation": measured_rotation[high_level_index],
        "high_level_measured_linear_velocity_m_s": measured_linear[high_level_index],
        "high_level_measured_angular_velocity_rad_s": measured_angular[
            high_level_index
        ],
        "high_level_measured_force_world_n": measured_force[high_level_index],
        "high_level_measured_moment_world_nm": measured_moment[high_level_index],
        "high_level_bed_force_n": bed_force[sample_index[high_level_index]],
        "estimated_state": estimated_states_array,
        "true_high_level_state_sample": true_sample_states_array,
        "true_high_level_state_arrival": true_arrival_states_array,
        "true_high_level_ddq_sample": sample_ddq,
        "true_high_level_ddq_arrival": arrival_ddq,
        "clean_high_level_sample": clean_sample_array,
        "clean_high_level_arrival": clean_arrival_array,
        "measurement_generalized_input_nm": measurement_targets_array,
        "dynamic_beta_history": np.asarray(beta_history),
    }
    return {
        "case": case.name,
        "source_trace": str(path),
        "registered_human": metadata,
        "measurement": measurement,
        "estimator": estimator_summary,
        "prediction": prediction_summary,
        "saved_rollout_termination": None,
    }, details
