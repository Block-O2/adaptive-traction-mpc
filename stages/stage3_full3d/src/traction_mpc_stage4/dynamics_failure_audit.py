"""Offline diagnostics for Stage-4 integral dynamics-ID candidate rejection."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import patch

import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, HIP_HEIGHT_M
from traction_mpc_stage3.human import HUMAN, soft_limit_torque

from .estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from .mpc import INTERACTION_AWARE_MPC_CONFIG
from .reference import CONTINUOUS_TEACHING_DURATION_S, continuous_teaching_reference


def geometry_from_trace_vector(vector: np.ndarray) -> PlanarCuffGeometry:
    values = np.asarray(vector, dtype=float)
    axis = values[5:8].copy()
    axis /= np.linalg.norm(axis)
    plane_x = np.array([1.0, 0.0, 0.0])
    plane_x -= axis * float(axis @ plane_x)
    plane_x /= np.linalg.norm(plane_x)
    plane_z = np.cross(plane_x, axis)
    plane_z /= np.linalg.norm(plane_z)
    return PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=plane_x,
        joint_axis_world=axis,
        plane_z_world=plane_z,
        hip_plane_m=values[:2].copy(),
        thigh_length_m=float(values[2]),
        knee_to_cuff_in_cuff_m=values[3:5].copy(),
    )


def unconstrained_candidate(
    identifier: AccumulatedIntegralBaseDynamicIdentifier,
    regressor: np.ndarray,
    target: np.ndarray,
) -> np.ndarray:
    scaled = regressor * identifier.span
    augmented_a = np.vstack(
        [
            scaled,
            math.sqrt(identifier.config.regularization_weight)
            * np.eye(len(identifier.last_valid)),
        ]
    )
    augmented_b = np.concatenate(
        [
            target - regressor @ identifier.population_prior,
            np.zeros(len(identifier.last_valid)),
        ]
    )
    normalized, *_ = np.linalg.lstsq(augmented_a, augmented_b, rcond=None)
    return identifier.population_prior + identifier.span * normalized


def bound_diagnostics(
    identifier: AccumulatedIntegralBaseDynamicIdentifier,
    candidate: np.ndarray,
    unconstrained: np.ndarray,
) -> list[dict[str, Any]]:
    constrained = np.asarray(candidate, dtype=float)
    raw = np.asarray(unconstrained, dtype=float)
    records: list[dict[str, Any]] = []
    for index, name in enumerate(DYNAMIC_BASE_PARAMETER_NAMES):
        lower = float(identifier.lower[index])
        upper = float(identifier.upper[index])
        lower_violation = max(lower - float(raw[index]), 0.0)
        upper_violation = max(float(raw[index]) - upper, 0.0)
        hit_lower = bool(np.isclose(constrained[index], lower, atol=1e-7, rtol=0.0))
        hit_upper = bool(np.isclose(constrained[index], upper, atol=1e-7, rtol=0.0))
        if not (hit_lower or hit_upper or lower_violation > 0.0 or upper_violation > 0.0):
            continue
        direction = "lower" if hit_lower or lower_violation > 0.0 else "upper"
        violation = lower_violation if direction == "lower" else upper_violation
        records.append(
            {
                "index": index,
                "name": name,
                "direction": direction,
                "constrained_hit": bool(hit_lower or hit_upper),
                "bound": lower if direction == "lower" else upper,
                "constrained_candidate": float(constrained[index]),
                "unconstrained_candidate": float(raw[index]),
                "unconstrained_violation": float(violation),
                "unconstrained_violation_fraction_of_span": float(
                    violation / identifier.span[index]
                ),
                "constrained_distance_to_bound": float(
                    abs(constrained[index] - (lower if direction == "lower" else upper))
                ),
            }
        )
    return records


def _distance(
    candidate: np.ndarray, target: np.ndarray, span: np.ndarray
) -> dict[str, float]:
    delta = np.asarray(candidate, dtype=float) - np.asarray(target, dtype=float)
    return {
        "raw_l2": float(np.linalg.norm(delta)),
        "span_normalized_l2": float(np.linalg.norm(delta / span)),
        "span_normalized_rms": float(np.sqrt(np.mean((delta / span) ** 2))),
    }


def _torque_prediction_error(
    beta: np.ndarray,
    true_beta: np.ndarray,
    q: np.ndarray,
    dq: np.ndarray,
    ddq: np.ndarray,
    clean: np.ndarray,
) -> dict[str, Any]:
    selected = np.flatnonzero(clean)
    if not len(selected):
        return {
            "combined_rmse_nm": float("nan"),
            "per_joint_rmse_nm": [float("nan"), float("nan")],
            "sample_count": 0,
        }
    errors = np.asarray(
        [
            dynamic_regressor_row(q[index], dq[index], ddq[index])
            @ (np.asarray(beta) - np.asarray(true_beta))
            for index in selected
        ]
    )
    return {
        "combined_rmse_nm": float(np.sqrt(np.mean(errors**2))),
        "per_joint_rmse_nm": np.sqrt(np.mean(errors**2, axis=0)).tolist(),
        "sample_count": int(len(errors)),
    }


def replay_dynamics_candidates(
    trace: dict[str, np.ndarray],
    *,
    geometry_trusted_time_s: float,
    true_human: Any,
    bound_detection_atol: float | None = None,
) -> dict[str, Any]:
    """Rebuild every causal dynamics-ID attempt from a saved engineering trace."""

    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    high_level_stride = int(
        round(INTERACTION_AWARE_MPC_CONFIG.prediction_dt_s / CONTROL_DT_S)
    )
    control_time = np.asarray(trace["control_time_s"], dtype=float)[::high_level_stride]
    estimated_state = np.asarray(trace["control_estimated_state"], dtype=float)[
        ::high_level_stride
    ]
    true_q = np.asarray(trace["control_true_q_rad_god_view"], dtype=float)[
        ::high_level_stride
    ]
    true_dq = np.asarray(trace["control_true_dq_rad_s_god_view"], dtype=float)[
        ::high_level_stride
    ]
    force = np.asarray(trace["measured_cuff_force_world_n"], dtype=float)[
        ::high_level_stride
    ]
    moment = np.asarray(trace["measured_cuff_moment_world_nm"], dtype=float)[
        ::high_level_stride
    ]
    trace_time = np.asarray(trace["time_s"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    geometry_trace = np.asarray(trace["geometry_estimate"], dtype=float)
    if len(control_time) >= 3:
        true_ddq = np.gradient(true_dq, control_time, axis=0, edge_order=2)
    else:
        true_ddq = np.zeros_like(true_dq)
    true_beta = nominal_base_parameters(true_human)
    validation_phase = np.linspace(0.0, CONTINUOUS_TEACHING_DURATION_S, 2301)
    validation_reference = [
        continuous_teaching_reference(item) for item in validation_phase
    ]
    validation_q = np.asarray([item.q_rad for item in validation_reference])
    validation_dq = np.asarray([item.dq_rad_s for item in validation_reference])
    validation_ddq = np.asarray([item.ddq_rad_s2 for item in validation_reference])
    validation_clean = np.ones(len(validation_phase), dtype=bool)
    raw_history: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for index, time_s in enumerate(control_time):
        trace_index = min(
            int(np.searchsorted(trace_time, time_s + 0.5e-3)), len(trace_time) - 1
        )
        geometry = geometry_from_trace_vector(geometry_trace[trace_index])
        contaminated = bool(
            np.linalg.norm(
                soft_limit_torque(
                    estimated_state[index, :2], estimated_state[index, 2:], HUMAN
                )
            )
            > 1e-8
        )
        raw_history.append(
            {
                "time_s": float(time_s),
                "state": estimated_state[index].copy(),
                "force_world_n": force[index].copy(),
                "moment_world_nm": moment[index].copy(),
                "contaminated": contaminated,
            }
        )
        if time_s < geometry_trusted_time_s - 1e-9:
            continue
        if bound_detection_atol is None:
            diagnostics = identifier.attempt_update(raw_history, geometry)
        else:
            original_isclose = np.isclose

            def diagnostic_isclose(
                first: Any,
                second: Any,
                *,
                atol: float = 1e-8,
                rtol: float = 1e-5,
                **kwargs: Any,
            ) -> np.ndarray:
                del atol, rtol
                return original_isclose(
                    first,
                    second,
                    atol=float(bound_detection_atol),
                    rtol=0.0,
                    **kwargs,
                )

            with patch(
                "traction_mpc_stage4.integral_identifier.np.isclose",
                new=diagnostic_isclose,
            ):
                diagnostics = identifier.attempt_update(raw_history, geometry)
        if not diagnostics.get("attempted", False):
            continue
        regressor, target, _ = identifier._integral_blocks(raw_history, geometry)
        raw_candidate = unconstrained_candidate(identifier, regressor, target)
        candidate = np.asarray(diagnostics["candidate"], dtype=float)
        clean = np.asarray(
            [
                np.linalg.norm(soft_limit_torque(q, velocity, true_human)) <= 1e-8
                for q, velocity in zip(true_q[: index + 1], true_dq[: index + 1], strict=True)
            ],
            dtype=bool,
        )
        attempts.append(
            {
                "attempt_index": len(attempts),
                "wall_time_s": float(time_s),
                "reference_phase_s": float(np.interp(time_s, trace_time, phase)),
                "accepted": bool(diagnostics["accepted"]),
                "reason": diagnostics["reason"],
                "rank": int(diagnostics["rank"]),
                "rrqr_rank": int(diagnostics["rrqr_rank"]),
                "condition_number": float(diagnostics["condition_number"]),
                "candidate_residual_rms_nms": float(
                    diagnostics["candidate_residual_rms_nms"]
                ),
                "old_residual_rms_nms": float(
                    diagnostics["old_residual_rms_nms"]
                ),
                "candidate_beta": candidate.tolist(),
                "unconstrained_candidate_beta": raw_candidate.tolist(),
                "applied_beta_after_attempt": diagnostics["applied"],
                "bound_hit": bool(diagnostics["bound_hit"]),
                "bound_components": bound_diagnostics(
                    identifier, candidate, raw_candidate
                ),
                "distance_to_population_prior": _distance(
                    candidate, identifier.population_prior, identifier.span
                ),
                "distance_to_registered_true_beta": _distance(
                    candidate, true_beta, identifier.span
                ),
                "candidate_generalized_torque_prediction_error": (
                    _torque_prediction_error(
                        candidate,
                        true_beta,
                        true_q[: index + 1],
                        true_dq[: index + 1],
                        true_ddq[: index + 1],
                        clean,
                    )
                ),
                "registered_full_trajectory_generalized_torque_prediction_error": (
                    _torque_prediction_error(
                        candidate,
                        true_beta,
                        validation_q,
                        validation_dq,
                        validation_ddq,
                        validation_clean,
                    )
                ),
                "retained_model_generalized_torque_prediction_error": (
                    _torque_prediction_error(
                        identifier.last_valid,
                        true_beta,
                        true_q[: index + 1],
                        true_dq[: index + 1],
                        true_ddq[: index + 1],
                        clean,
                    )
                ),
                "integral_block_count": int(diagnostics["integral_block_count"]),
                "contaminated_integral_windows": int(
                    diagnostics["contaminated_integral_windows"]
                ),
                "positive_definite_mass_matrix": bool(
                    diagnostics["positive_definite_mass_matrix"]
                ),
            }
        )
    return {
        "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "population_prior_beta": identifier.population_prior.tolist(),
        "registered_true_beta": true_beta.tolist(),
        "registered_full_trajectory_population_prior_prediction_error": (
            _torque_prediction_error(
                identifier.population_prior,
                true_beta,
                validation_q,
                validation_dq,
                validation_ddq,
                validation_clean,
            )
        ),
        "lower_bounds": identifier.lower.tolist(),
        "upper_bounds": identifier.upper.tolist(),
        "span": identifier.span.tolist(),
        "attempts": attempts,
        "accepted_count": int(sum(item["accepted"] for item in attempts)),
        "rejected_count": int(sum(not item["accepted"] for item in attempts)),
        "reconstructed_trustworthy_time_s": identifier.trustworthy_time_s,
        "final_retained_beta": identifier.last_valid.tolist(),
        "diagnostic_bound_detection_atol": bound_detection_atol,
    }
