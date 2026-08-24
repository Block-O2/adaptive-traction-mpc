"""Structural audit for a geometry-free one-shot Stage-4 Estimator V2.

This module is audit-only.  It does not feed MuJoCo truth to a controller or
estimator and does not implement a bootstrap motion that the measurements do
not support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.linalg import qr

from traction_mpc_stage3.reference import quintic_progress


AUDIT_DURATION_S = 18.0
AUDIT_WAYPOINTS = (
    (0.0, (5.0, 10.0), "initial_hold"),
    (1.0, (5.0, 10.0), "hip_dominant_start"),
    (4.0, (45.0, 20.0), "hip_dominant_end"),
    (5.0, (45.0, 20.0), "knee_dominant_start"),
    (8.0, (75.0, 90.0), "high_flexion"),
    (9.5, (75.0, 90.0), "high_flexion_hold_end"),
    (12.0, (50.0, 55.0), "staged_extension_1"),
    (14.0, (30.0, 25.0), "staged_extension_2"),
    (17.0, (5.0, 10.0), "return"),
    (18.0, (5.0, 10.0), "final_hold"),
)


def audit_joint_reference(time_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = float(np.clip(time_s, 0.0, AUDIT_DURATION_S))
    for (ta, qa, _), (tb, qb, _) in zip(AUDIT_WAYPOINTS[:-1], AUDIT_WAYPOINTS[1:], strict=True):
        if time <= tb + 1e-12:
            duration = tb - ta
            q0 = np.radians(qa)
            delta = np.radians(np.asarray(qb) - np.asarray(qa))
            if np.allclose(delta, 0.0):
                return q0, np.zeros(2), np.zeros(2)
            s, ds, dds = quintic_progress((time - ta) / duration)
            return q0 + delta * s, delta * ds / duration, delta * dds / duration**2
    return np.radians(AUDIT_WAYPOINTS[-1][1]), np.zeros(2), np.zeros(2)


def _rank_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    raw = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(raw, axis=0)
    normalized = raw / np.where(norms > 0.0, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1e-10 if len(singular) else 0.0
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    _, _, pivots = qr(normalized, mode="economic", pivoting=True)
    return {
        "rows": int(raw.shape[0]),
        "columns": int(raw.shape[1]),
        "rank": rank,
        "nullity": int(raw.shape[1] - rank),
        "column_normalized_singular_values": singular.tolist(),
        "column_normalized_condition_number": (
            float(singular[0] / singular[-1])
            if len(singular) and singular[-1] > 1e-15
            else float("inf")
        ),
        "rrqr_pivot_order": [int(value) for value in pivots],
    }


def _kinematic_jacobian(times_s: np.ndarray) -> np.ndarray:
    q = np.array([audit_joint_reference(float(time))[0] for time in times_s])
    phi = q[:, 0] - q[:, 1]
    # A dimensionless, nonzero local scale is sufficient for structural-rank
    # analysis; no Human-V2 geometry is supplied to the audit formulation.
    thigh_length = 1.0
    count = len(times_s)
    # Unknowns: hip pivot in plane (2), thigh length (1), knee-to-cuff
    # vector expressed in the measured cuff frame (2), and hip angle at each
    # sample (N).  Cuff planar orientation is a measured input.
    jacobian = np.zeros((2 * count, 5 + count))
    for index, (angles, cuff_angle) in enumerate(zip(q, phi, strict=True)):
        rotation = np.array(
            [
                [np.cos(cuff_angle), -np.sin(cuff_angle)],
                [np.sin(cuff_angle), np.cos(cuff_angle)],
            ]
        )
        row = slice(2 * index, 2 * index + 2)
        jacobian[row, :2] = np.eye(2)
        jacobian[row, 2] = [np.cos(angles[0]), np.sin(angles[0])]
        jacobian[row, 3:5] = rotation
        jacobian[row, 5 + index] = thigh_length * np.array(
            [-np.sin(angles[0]), np.cos(angles[0])]
        )
    return jacobian


DYNAMIC_BASE_PARAMETER_NAMES = (
    "a_inertia_combination",
    "b_distal_inertia_combination",
    "d_mass_length_com_combination",
    "g1_proximal_gravity_combination",
    "g2_distal_gravity_combination",
    "k1_passive_stiffness",
    "k2_passive_stiffness",
    "rho1_stiffness_rest_combination",
    "rho2_stiffness_rest_combination",
    "bv1_viscous_damping",
    "bv2_viscous_damping",
)


def _dynamic_regressor(times_s: np.ndarray) -> np.ndarray:
    q = np.array([audit_joint_reference(float(time))[0] for time in times_s])
    dt = float(np.mean(np.diff(times_s)))
    dq = np.gradient(q, dt, axis=0)
    ddq = np.gradient(dq, dt, axis=0)
    blocks = []
    for angles, velocity, acceleration in zip(q, dq, ddq, strict=True):
        q1, q2 = angles
        dq1, dq2 = velocity
        ddq1, ddq2 = acceleration
        phi = q1 - q2
        cosine = np.cos(q2)
        sine = np.sin(q2)
        regressor = np.zeros((2, len(DYNAMIC_BASE_PARAMETER_NAMES)))
        regressor[0] = [
            ddq1,
            -ddq2,
            2.0 * cosine * ddq1
            - cosine * ddq2
            + sine * (-2.0 * dq1 * dq2 + dq2**2),
            np.cos(q1),
            np.cos(phi),
            q1,
            0.0,
            -1.0,
            0.0,
            dq1,
            0.0,
        ]
        regressor[1] = [
            0.0,
            -ddq1 + ddq2,
            -cosine * ddq1 + sine * dq1**2,
            0.0,
            -np.cos(phi),
            0.0,
            q2,
            0.0,
            -1.0,
            0.0,
            dq2,
        ]
        blocks.append(regressor)
    return np.vstack(blocks)


def run_estimator_v2_observability_audit() -> dict[str, Any]:
    horizons = (0.5, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0, 8.0, 12.0, 18.0)
    kinematic_progress = {}
    for horizon in horizons:
        count = max(6, int(round(horizon * 10.0)) + 1)
        times = np.linspace(0.0, horizon, count)
        kinematic_progress[f"{horizon:g}"] = _rank_diagnostics(
            _kinematic_jacobian(times)
        )

    full_times = np.linspace(0.0, AUDIT_DURATION_S, 901)
    full_dynamic = _dynamic_regressor(full_times)
    dynamic_progress = {}
    for horizon in horizons:
        sample_mask = full_times <= horizon + 1e-12
        dynamic_progress[f"{horizon:g}"] = _rank_diagnostics(
            full_dynamic[np.repeat(sample_mask, 2)]
        )

    q = np.array([audit_joint_reference(float(time))[0] for time in full_times])
    cuff_angle = q[:, 0] - q[:, 1]
    relative_rotation_vectors = np.column_stack(
        [np.zeros_like(cuff_angle), cuff_angle - cuff_angle[0], np.zeros_like(cuff_angle)]
    )
    axis_singular = np.linalg.svd(relative_rotation_vectors, compute_uv=False)

    return {
        "evidence_category": "structural_observability_identifiability_audit",
        "trajectory": {
            "duration_s": AUDIT_DURATION_S,
            "waypoints": [
                {"time_s": time, "q_deg": list(q_deg), "label": label}
                for time, q_deg, label in AUDIT_WAYPOINTS
            ],
            "maximum_q_deg": np.degrees(np.max(q, axis=0)).tolist(),
            "fixed_hip_knee_velocity_ratio": False,
        },
        "kinematic_observability": {
            "orientation_increment_rank": int(
                np.linalg.matrix_rank(relative_rotation_vectors)
            ),
            "orientation_increment_singular_values": axis_singular.tolist(),
            "observable_individually_or_by_convention": [
                "motion-plane normal / common joint axis, up to sign",
                "hip pivot projected into the motion plane",
                "thigh length",
                "knee-to-cuff vector expressed in the measured cuff frame",
                "hip and knee coordinate histories after the geometric fit",
            ],
            "observable_only_as_combinations": [
                "hip-pivot normal coordinate minus cuff normal offset",
                "knee-to-cuff distance and cuff alignment as one cuff-frame vector",
                "shank length and cuff fractional location cannot be separated without a distal landmark",
            ],
            "cumulative_rank": kinematic_progress,
        },
        "dynamic_base_identifiability": {
            "base_parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
            "anatomical_mass_com_inertia_individually_identifiable": False,
            "full_history": _rank_diagnostics(full_dynamic),
            "cumulative_rank": dynamic_progress,
        },
        "one_shot_causal_assessment": {
            "batch_history_structurally_sufficient": True,
            "causal_first_execution_controller_ready": False,
            "reason": (
                "The initial cuff pose and hold admit infinitely many 2R geometries and joint states. "
                "The intended joint-space cuff reference cannot be generated before the same motion "
                "needed to identify that geometry has already occurred."
            ),
            "minimum_missing_measurement": (
                "One independent initial observation of both hip and knee joint centers in the motion "
                "plane (equivalently, a known hip pivot plus one tracked knee point)."
            ),
            "true_human_state_or_parameters_used": False,
            "implementation_or_rollout_authorized_by_audit": False,
        },
    }
