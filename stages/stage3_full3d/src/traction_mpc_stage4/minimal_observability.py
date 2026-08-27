"""Mechanical observability audit for the minimal prior-based estimator."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.reference import _world_from_cuff

from .estimator_v2 import AccumulatedCuffGeometryEstimator, dynamic_regressor_row, nominal_base_parameters
from .integral_identifier import integral_regression_block
from .minimal_adaptation import (
    CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
    CONTROL_RELEVANT_GEOMETRY_PARAMETER_NAMES,
    dynamic_scale_projection,
)
from .reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    cold_start_joint_reference,
)


AUDIT_DT_S = 0.02
AUDIT_HORIZONS_S = (1.0, 3.5, 6.5, 10.0, 13.0, 14.5, 17.0, 19.0, 22.0, 23.0)


def _rank_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    raw = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(raw, axis=0)
    normalized = raw / np.where(norms > 1e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1e-10 if len(singular) else 0.0
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1e-15
        # Keep the persisted artifact strict JSON while retaining the same
        # practical meaning as an infinite condition number.
        else float(np.finfo(float).max)
    )
    information_shape = normalized.T @ normalized
    covariance_shape = np.linalg.pinv(information_shape, rcond=1e-12)
    return {
        "rows": int(raw.shape[0]),
        "columns": int(raw.shape[1]),
        "rank": rank,
        "nullity": int(raw.shape[1] - rank),
        "column_normalized_condition_number": condition,
        "column_normalized_singular_values": singular.tolist(),
        "relative_covariance_shape_diagonal": np.diag(covariance_shape).tolist(),
    }


def _reference_history() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    times = np.arange(
        0.0,
        COLD_START_TEACHING_DURATION_S + 0.5 * AUDIT_DT_S,
        AUDIT_DT_S,
    )
    references = [cold_start_joint_reference(float(time)) for time in times]
    states = np.array(
        [np.concatenate([reference[0], reference[1]]) for reference in references]
    )
    accelerations = np.array([reference[2] for reference in references])
    return times, states, accelerations


def _geometry_jacobian(states: np.ndarray) -> np.ndarray:
    initial_pose = _world_from_cuff(states[0, :2])
    estimator = AccumulatedCuffGeometryEstimator(
        initial_pose.translation,
        initial_pose.rotation,
        states[0, :2],
    )
    poses = [_world_from_cuff(state[:2]) for state in states]
    positions = np.array(
        [
            [
                estimator.prior_plane_x_world @ (pose.translation - estimator.origin_world_m),
                estimator.prior_plane_z_world @ (pose.translation - estimator.origin_world_m),
            ]
            for pose in poses
        ]
    )
    rotations = np.array(
        [
            [
                [estimator.prior_plane_x_world @ pose.rotation[:, 0], estimator.prior_plane_x_world @ pose.rotation[:, 2]],
                [estimator.prior_plane_z_world @ pose.rotation[:, 0], estimator.prior_plane_z_world @ pose.rotation[:, 2]],
            ]
            for pose in poses
        ]
    )
    # The minimal prior fixes the initial hip anchor and retains only the
    # current estimator's leg-length and cuff-frame-vector columns.
    full = estimator._numerical_jacobian(estimator.prior, positions, rotations)
    return full[:, 2:5]


def _integral_dynamic_rows(
    times: np.ndarray, states: np.ndarray, accelerations: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    beta = nominal_base_parameters()
    torque = np.array(
        [
            dynamic_regressor_row(state[:2], state[2:], acceleration) @ beta
            for state, acceleration in zip(states, accelerations, strict=True)
        ]
    )
    end_times: list[float] = []
    rows: list[np.ndarray] = []
    window_samples = int(round(0.50 / AUDIT_DT_S))
    stride_samples = 5
    projection = dynamic_scale_projection(beta)
    for end in range(window_samples, len(times), stride_samples):
        start = end - window_samples
        full, _ = integral_regression_block(
            times[start : end + 1],
            states[start : end + 1],
            torque[start : end + 1],
        )
        rows.append(full @ projection)
        end_times.extend([float(times[end]), float(times[end])])
    return np.vstack(rows), np.asarray(end_times)


def run_minimal_observability_audit() -> dict[str, Any]:
    """Audit the requested subspace on the current 23 s high-flexion path."""

    times, states, accelerations = _reference_history()
    geometry = _geometry_jacobian(states)
    dynamics, dynamic_end_times = _integral_dynamic_rows(times, states, accelerations)
    geometry_progress: dict[str, Any] = {}
    dynamic_progress: dict[str, Any] = {}
    for horizon in AUDIT_HORIZONS_S:
        geometry_progress[f"{horizon:g}"] = _rank_diagnostics(
            geometry[times <= horizon + 1e-12]
        )
        selected = dynamics[dynamic_end_times <= horizon + 1e-12]
        dynamic_progress[f"{horizon:g}"] = _rank_diagnostics(selected)

    return {
        "evidence_category": "mechanical_structural_observability_audit",
        "formal_experiment": False,
        "trajectory": {
            "name": "stage4_population_prior_cold_start_high_flexion_23s",
            "duration_s": COLD_START_TEACHING_DURATION_S,
            "sample_period_s": AUDIT_DT_S,
            "waypoints": [
                {
                    "time_s": item.time_s,
                    "q_deg": list(item.q_deg),
                    "label": item.label,
                }
                for item in COLD_START_TEACHING_WAYPOINTS
            ],
        },
        "geometry": {
            "parameter_names": list(CONTROL_RELEVANT_GEOMETRY_PARAMETER_NAMES),
            "prior_fixed_quantities": [
                "initial hip anchor in the fitted motion plane",
                "common joint axis and plane basis from the existing geometry frontend",
            ],
            "cumulative": geometry_progress,
        },
        "dynamics": {
            "parameter_names": list(CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES),
            "integral_window_s": 0.50,
            "integral_block_stride_measurements": 5,
            "cumulative": dynamic_progress,
        },
        "limitations": [
            "reference-trajectory local structural audit; not noisy closed-loop recovery",
            "relative covariance shape is uncalibrated and overlapping windows are correlated",
            "fixed prior hip anchor can create geometry bias if initial alignment is wrong",
            "effective scales do not identify anatomical mass, COM, inertia, joint-specific stiffness, rest angle, or joint-specific damping",
        ],
        "prohibited_additions": {"tube_mpc": False, "ukf": False},
    }
