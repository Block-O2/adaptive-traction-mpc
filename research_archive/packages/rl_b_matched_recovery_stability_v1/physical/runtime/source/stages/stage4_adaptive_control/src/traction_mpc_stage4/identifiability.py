"""Offline Stage-4 parameter sensitivity and replay audit."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .human_model import (
    PARAMETER_BOUNDS,
    PARAMETER_NAMES,
    inverse_dynamics,
    nominal_parameter_vector,
    parameterized_human,
    registered_moderate_human,
)
from .reference import TEACHING_DURATION_S, teaching_reference


def _replay_data(sample_dt_s: float = 0.02) -> tuple[np.ndarray, ...]:
    times = np.arange(0.0, TEACHING_DURATION_S + 0.5 * sample_dt_s, sample_dt_s)
    references = [teaching_reference(float(t)) for t in times]
    q = np.array([item.q_rad for item in references])
    dq = np.array([item.dq_rad_s for item in references])
    qdd = np.array([item.ddq_rad_s2 for item in references])
    true_human, _ = registered_moderate_human()
    torque = np.array(
        [inverse_dynamics(qi, dqi, qddi, true_human) for qi, dqi, qddi in zip(q, dq, qdd, strict=True)]
    )
    return times, q, dq, qdd, torque


def _torque_prediction(theta: np.ndarray, names: tuple[str, ...], q: np.ndarray, dq: np.ndarray, qdd: np.ndarray) -> np.ndarray:
    human = parameterized_human(theta, names)
    return np.array(
        [inverse_dynamics(qi, dqi, qddi, human) for qi, dqi, qddi in zip(q, dq, qdd, strict=True)]
    )


def _scaled_jacobian(theta: np.ndarray, names: tuple[str, ...], q: np.ndarray, dq: np.ndarray, qdd: np.ndarray) -> np.ndarray:
    columns = []
    for index, name in enumerate(names):
        lower, upper = PARAMETER_BOUNDS[name]
        step = max(1e-7, 1e-5 * (upper - lower))
        plus = theta.copy(); minus = theta.copy()
        plus[index] = min(upper, plus[index] + step)
        minus[index] = max(lower, minus[index] - step)
        derivative = (
            _torque_prediction(plus, names, q, dq, qdd)
            - _torque_prediction(minus, names, q, dq, qdd)
        ) / (plus[index] - minus[index])
        columns.append((derivative * (upper - lower)).reshape(-1))
    return np.column_stack(columns)


def audit_parameter_set(names: tuple[str, ...]) -> dict[str, Any]:
    _, q, dq, qdd, observed = _replay_data()
    initial = nominal_parameter_vector(names)
    lower = np.array([PARAMETER_BOUNDS[name][0] for name in names])
    upper = np.array([PARAMETER_BOUNDS[name][1] for name in names])
    result = least_squares(
        lambda theta: (_torque_prediction(theta, names, q, dq, qdd) - observed).reshape(-1),
        initial,
        bounds=(lower, upper),
        loss="huber",
        f_scale=0.5,
        max_nfev=300,
        xtol=1e-12,
        ftol=1e-12,
        gtol=1e-12,
    )
    theta = np.asarray(result.x)
    residual = (_torque_prediction(theta, names, q, dq, qdd) - observed).reshape(-1)
    jacobian = _scaled_jacobian(theta, names, q, dq, qdd)
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular_values[0] * 1e-10)) if len(singular_values) else 0
    info = jacobian.T @ jacobian
    covariance = np.linalg.pinv(info, rcond=1e-12)
    std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    denom = np.outer(std, std)
    correlation = np.divide(covariance, denom, out=np.full_like(covariance, np.nan), where=denom > 0.0)
    off_diagonal = correlation.copy()
    np.fill_diagonal(off_diagonal, 0.0)
    return {
        "parameter_names": list(names),
        "rank": rank,
        "parameter_count": len(names),
        "scaled_singular_values": singular_values.tolist(),
        "scaled_condition_number": float(singular_values[0] / singular_values[-1]) if len(singular_values) and singular_values[-1] > 0.0 else float("inf"),
        "fit_rmse_nm": float(np.sqrt(np.mean(residual**2))),
        "fit_max_abs_nm": float(np.max(np.abs(residual))),
        "estimate": {name: float(value) for name, value in zip(names, theta, strict=True)},
        "bound_hit": bool(np.any(np.isclose(theta, lower, rtol=0.0, atol=1e-7)) or np.any(np.isclose(theta, upper, rtol=0.0, atol=1e-7))),
        "correlation": correlation.tolist(),
        "max_abs_off_diagonal_correlation": float(np.nanmax(np.abs(off_diagonal))),
        "optimizer_success": bool(result.success),
    }


def run_offline_identifiability_audit() -> dict[str, Any]:
    full = audit_parameter_set(PARAMETER_NAMES)
    candidates = (
        ("mass_scale", "stiffness_scale"),
        ("mass_scale", "stiffness_scale", "rest_common_offset_rad"),
        ("mass_scale", "stiffness_scale", "rest_hip_offset_rad", "rest_knee_offset_rad"),
        ("mass_scale", "thigh_com_scale", "shank_com_scale", "stiffness_scale", "rest_hip_offset_rad", "rest_knee_offset_rad"),
    )
    subspaces = [audit_parameter_set(names) for names in candidates]
    return {
        "evidence_category": "offline_identifiability_replay",
        "trajectory": "stage4_teaching_18s",
        "sample_dt_s": 0.02,
        "true_case": "stage2_registered_moderate",
        "full_candidate_audit": full,
        "candidate_subspaces": subspaces,
    }
