"""Analytical Stage-5 geometry identifiability audit.

This evaluation-only script demonstrates the exact L2/f equivalence in the
current Human-V2 cuff kinematics. It does not implement an estimator or expose
hidden values to a controller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


STAGE5_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = (
    STAGE5_ROOT
    / "configs"
    / "architecture_recovery_v1"
    / "identifiability_audit_v1.json"
)


def _cuff_position(q: np.ndarray, l1: float, l2: float, fraction: float) -> np.ndarray:
    q1, q2 = q
    phi = q1 - q2
    sc = fraction * l2
    return np.array(
        [l1 * np.cos(q1) + sc * np.cos(phi), l1 * np.sin(q1) + sc * np.sin(phi)]
    )


def _cuff_jacobian(q: np.ndarray, l1: float, l2: float, fraction: float) -> np.ndarray:
    q1, q2 = q
    phi = q1 - q2
    sc = fraction * l2
    return np.array(
        [
            [-l1 * np.sin(q1) - sc * np.sin(phi), sc * np.sin(phi)],
            [l1 * np.cos(q1) + sc * np.cos(phi), -sc * np.cos(phi)],
        ]
    )


def _ankle_position(q: np.ndarray, l1: float, l2: float) -> np.ndarray:
    q1, q2 = q
    phi = q1 - q2
    return np.array(
        [l1 * np.cos(q1) + l2 * np.cos(phi), l1 * np.sin(q1) + l2 * np.sin(phi)]
    )


def _rotation_2d(angle: float) -> np.ndarray:
    return np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )


def run(spec_path: Path, output_path: Path) -> dict[str, object]:
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    if spec.get("schema") != "stage5_architecture_recovery_identifiability_audit_v1":
        raise ValueError("unexpected audit schema")

    height_m = 1.72
    l1 = 0.254 * height_m
    l2_a = 0.233 * height_m
    f_a = 0.72
    sc = l2_a * f_a
    l2_b = float(spec["comparison_shank_length_m"])
    f_b = sc / l2_b
    if not 0.0 < f_b < 1.0 or np.isclose(l2_a, l2_b):
        raise ValueError("comparison pair must be distinct and physically legal")

    q_samples = np.radians(
        np.column_stack([spec["q1_deg"], spec["q2_deg"]]).astype(float)
    )
    wrench = np.asarray(spec["wrench_xz_n"], dtype=float)
    if q_samples.ndim != 2 or q_samples.shape[1] != 2 or wrench.shape != (2,):
        raise ValueError("invalid audit samples")

    pose_residuals = []
    jacobian_residuals = []
    generalized_effect_residuals = []
    ankle_differences = []
    q_zero_pose_residuals = []
    q_zero_orientation_residuals = []
    q_zero_jacobian_residuals = []
    observation_parameter_jacobian = []
    gamma = np.radians(float(spec["in_plane_gauge_rotation_deg"]))
    basis_a = np.eye(2)
    basis_b = basis_a @ _rotation_2d(gamma)
    for q in q_samples:
        phi = float(q[0] - q[1])
        direction = np.array([np.cos(phi), np.sin(phi)])
        pose_a = _cuff_position(q, l1, l2_a, f_a)
        pose_b = _cuff_position(q, l1, l2_b, f_b)
        jac_a = _cuff_jacobian(q, l1, l2_a, f_a)
        jac_b = _cuff_jacobian(q, l1, l2_b, f_b)
        pose_residuals.append(float(np.linalg.norm(pose_a - pose_b)))
        jacobian_residuals.append(float(np.linalg.norm(jac_a - jac_b)))
        generalized_effect_residuals.append(
            float(np.linalg.norm(jac_a.T @ wrench - jac_b.T @ wrench))
        )
        ankle_differences.append(
            float(np.linalg.norm(_ankle_position(q, l1, l2_a) - _ankle_position(q, l1, l2_b)))
        )
        # Cuff position is the only kinematic channel containing L2 and f.
        # Its two columns remain globally proportional for every motion sample.
        observation_parameter_jacobian.extend(
            np.column_stack([f_a * direction, l2_a * direction]).tolist()
        )
        q_gauge = np.array([q[0] - gamma, q[1]])
        phi_gauge = float(q_gauge[0] - q_gauge[1])
        pose_world_a = basis_a @ _cuff_position(q, l1, l2_a, f_a)
        pose_world_b = basis_b @ _cuff_position(q_gauge, l1, l2_a, f_a)
        shank_world_a = basis_a @ np.array([np.cos(phi), np.sin(phi)])
        shank_world_b = basis_b @ np.array(
            [np.cos(phi_gauge), np.sin(phi_gauge)]
        )
        jacobian_world_a = basis_a @ _cuff_jacobian(q, l1, l2_a, f_a)
        jacobian_world_b = basis_b @ _cuff_jacobian(
            q_gauge, l1, l2_a, f_a
        )
        q_zero_pose_residuals.append(
            float(np.linalg.norm(pose_world_a - pose_world_b))
        )
        q_zero_orientation_residuals.append(
            float(np.linalg.norm(shank_world_a - shank_world_b))
        )
        q_zero_jacobian_residuals.append(
            float(np.linalg.norm(jacobian_world_a - jacobian_world_b))
        )

    sensitivity = np.asarray(observation_parameter_jacobian, dtype=float)
    singular_values = np.linalg.svd(sensitivity, compute_uv=False)
    tolerance = float(singular_values[0] * 1.0e-12)
    rank = int(np.linalg.matrix_rank(sensitivity, tol=tolerance))
    null_direction = np.array([l2_a, -f_a], dtype=float)
    null_residual = float(np.linalg.norm(sensitivity @ null_direction))

    exact_equivalence = bool(
        max(pose_residuals) <= 1.0e-12
        and max(jacobian_residuals) <= 1.0e-12
        and max(generalized_effect_residuals) <= 1.0e-12
    )
    exact_q_zero_gauge = bool(
        max(q_zero_pose_residuals) <= 1.0e-12
        and max(q_zero_orientation_residuals) <= 1.0e-12
        and max(q_zero_jacobian_residuals) <= 1.0e-12
    )
    outcome = (
        "NON_IDENTIFIABLE"
        if (
            rank < 2
            and exact_equivalence
            and max(ankle_differences) > 1.0e-3
            and exact_q_zero_gauge
        )
        else "SEPARATELY_IDENTIFIABLE"
    )
    result: dict[str, object] = {
        "schema": "stage5_architecture_recovery_identifiability_result_v1",
        "evidence_category": "analytical_audit",
        "spec_sha256": hashlib.sha256(raw).hexdigest(),
        "outcome": outcome,
        "nominal_pair": {"L2_m": l2_a, "cuff_fraction": f_a, "sc_m": sc},
        "equivalent_pair": {"L2_m": l2_b, "cuff_fraction": f_b, "sc_m": l2_b * f_b},
        "sample_count": int(len(q_samples)),
        "stacked_observation_jacobian_rank": rank,
        "stacked_observation_jacobian_singular_values": singular_values.tolist(),
        "analytic_null_direction_L2_f": null_direction.tolist(),
        "analytic_null_residual": null_residual,
        "maximum_cuff_pose_residual_m": max(pose_residuals),
        "maximum_cuff_jacobian_residual": max(jacobian_residuals),
        "maximum_generalized_effect_residual_nm": max(generalized_effect_residuals),
        "ankle_position_difference_m": ankle_differences,
        "maximum_ankle_position_difference_m": max(ankle_differences),
        "in_plane_q1_gauge_rotation_deg": float(
            spec["in_plane_gauge_rotation_deg"]
        ),
        "maximum_q1_gauge_cuff_pose_residual_m": max(q_zero_pose_residuals),
        "maximum_q1_gauge_cuff_orientation_residual": max(
            q_zero_orientation_residuals
        ),
        "maximum_q1_gauge_world_jacobian_residual": max(
            q_zero_jacobian_residuals
        ),
        "q1_gauge_transformation": (
            "rotate the in-plane basis by gamma, set q1'=q1-gamma and q2'=q2"
        ),
        "interpretation": (
            "Allowed cuff kinematics and wrench mapping identify only sc=f*L2. "
            "The current shank/table clearance consumer needs L2 itself, so the "
            "two legal setups are observationally equivalent upstream but differ "
            "in a control-critical downstream geometry quantity. In addition, "
            "cuff kinematics alone do not fix the absolute in-plane q1 zero; a "
            "calibrated sagittal basis, known-q pose, anatomical landmark, or a "
            "separately proven gravity/dynamics identification is required."
        ),
        "controller_inputs_used": [],
        "simulation_truth_use": "evaluation-only construction and scoring",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.spec, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
