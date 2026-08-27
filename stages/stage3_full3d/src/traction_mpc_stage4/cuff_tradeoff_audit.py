"""Exact one-dimensional cuff-allocation trade-off audit."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N

from .cuff_allocator import (
    CurrentForceMinimizingAllocator,
    cylindrical_surface_mapping,
    sagittal_allocation_matrix,
    sagittal_null_vector,
)
from .human_model import registered_cold_start_perturbed_human
from .reference import CONTINUOUS_TEACHING_DURATION_S
from .surface_loads import CylindricalSurfaceConfig, CylindricalSurfaceLoadModel


WEIGHT_RATIOS = np.concatenate(
    [np.array([0.0]), np.logspace(-4.0, 4.0, 81), np.array([np.inf])]
)


def quadratic_coefficients(
    w0: np.ndarray, null: np.ndarray, surface_mapping: np.ndarray
) -> dict[str, np.ndarray]:
    """Return [quadratic, linear, constant] coefficients in alpha."""

    base = np.asarray(w0, dtype=float)
    direction = np.asarray(null, dtype=float)
    base_patch = surface_mapping @ base
    null_patch = surface_mapping @ direction
    return {
        "force_squared": np.array(
            [
                direction[:2] @ direction[:2],
                2.0 * base[:2] @ direction[:2],
                base[:2] @ base[:2],
            ]
        ),
        "moment_squared": np.array(
            [direction[2] ** 2, 2.0 * base[2] * direction[2], base[2] ** 2]
        ),
        "surface_squared": np.array(
            [
                null_patch @ null_patch,
                2.0 * base_patch @ null_patch,
                base_patch @ base_patch,
            ]
        ),
    }


def _quadratic_minimizer(coefficients: np.ndarray) -> float:
    quadratic, linear, _ = np.asarray(coefficients, dtype=float)
    if quadratic <= 1e-18:
        return 0.0
    return float(-linear / (2.0 * quadratic))


def _weighted_alpha(
    force_coefficients: np.ndarray,
    surface_coefficients: np.ndarray,
    surface_to_force_weight_ratio: float,
) -> float:
    if np.isinf(surface_to_force_weight_ratio):
        return _quadratic_minimizer(surface_coefficients)
    combined = (
        force_coefficients
        + float(surface_to_force_weight_ratio) * surface_coefficients
    )
    return _quadratic_minimizer(combined)


def _strategy_metrics(
    name: str,
    alpha: np.ndarray,
    w0: np.ndarray,
    null: np.ndarray,
    surface_mappings: np.ndarray,
    allocation_matrices: np.ndarray,
    torque: np.ndarray,
) -> dict[str, Any]:
    wrench = w0 + alpha[:, np.newaxis] * null
    force = np.linalg.norm(wrench[:, :2], axis=1)
    moment = np.abs(wrench[:, 2])
    patch_vectors = np.einsum("tij,tj->ti", surface_mappings, wrench)
    surface = np.linalg.norm(patch_vectors, axis=1)
    patch_force = patch_vectors.reshape(len(wrench), -1, 3)
    maximum_local = np.max(np.linalg.norm(patch_force, axis=2), axis=1)
    residual = np.einsum("tij,tj->ti", allocation_matrices, wrench) - torque
    return {
        "name": name,
        "alpha_n": {
            "minimum": float(np.min(alpha)),
            "maximum": float(np.max(alpha)),
            "rms": float(np.sqrt(np.mean(alpha**2))),
        },
        "resultant_force_n": {
            "peak": float(np.max(force)),
            "rms": float(np.sqrt(np.mean(force**2))),
        },
        "abs_cuff_moment_nm": {
            "peak": float(np.max(moment)),
            "rms": float(np.sqrt(np.mean(moment**2))),
        },
        "cylindrical_surface_effort_proxy_n": {
            "peak": float(np.max(surface)),
            "rms": float(np.sqrt(np.mean(surface**2))),
        },
        "maximum_local_patch_force_proxy_n": float(np.max(maximum_local)),
        "force_gate_exceedance_sample_count": int(
            np.count_nonzero(force > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9)
        ),
        "equality_residual_nm": {
            "peak": float(np.max(np.linalg.norm(residual, axis=1))),
            "rms": float(np.sqrt(np.mean(residual**2))),
        },
    }


def run_cuff_tradeoff_audit(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    """Audit fixed-tau allocation choices on the saved registered trajectory."""

    time_full = np.asarray(trace["time_s"])
    phase_full = np.asarray(trace["reference_phase_time_s"])
    completion = np.flatnonzero(
        phase_full >= CONTINUOUS_TEACHING_DURATION_S - 1e-9
    )
    completion_index = int(completion[0]) if len(completion) else len(time_full) - 1
    # MPC holds tau_h for 20 plant samples.  Use its native update grid and
    # stop at reference completion so the final hold does not dominate RMS.
    selected = np.arange(0, completion_index + 1, 20, dtype=int)
    if selected[-1] != completion_index:
        selected = np.append(selected, completion_index)
    time = time_full[selected]
    phase = phase_full[selected]
    q = np.radians(np.asarray(trace["human_q_deg_god_view"])[selected])
    torque = np.asarray(trace["desired_human_action_nm"])[selected]

    human, metadata = registered_cold_start_perturbed_human()
    surface_model = CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    current_allocator = CurrentForceMinimizingAllocator()
    count = len(time)
    w0 = np.zeros((count, 3))
    null = np.zeros((count, 3))
    allocation_matrices = np.zeros((count, 2, 3))
    surface_mappings = np.zeros(
        (count, surface_model.config.patch_count * 3, 3)
    )
    coefficient_force = np.zeros((count, 3))
    coefficient_moment = np.zeros((count, 3))
    coefficient_surface = np.zeros((count, 3))
    for index, (q_item, torque_item) in enumerate(
        zip(q, torque, strict=True)
    ):
        allocation = current_allocator.allocate(torque_item, q_item, human)
        w0[index] = allocation["sagittal_wrench"]
        null[index] = sagittal_null_vector(q_item, human)
        allocation_matrices[index] = sagittal_allocation_matrix(q_item, human)
        surface_mappings[index] = cylindrical_surface_mapping(
            q_item, human, surface_model
        )
        coefficients = quadratic_coefficients(
            w0[index], null[index], surface_mappings[index]
        )
        coefficient_force[index] = coefficients["force_squared"]
        coefficient_moment[index] = coefficients["moment_squared"]
        coefficient_surface[index] = coefficients["surface_squared"]

    alpha_force = np.array(
        [_quadratic_minimizer(item) for item in coefficient_force]
    )
    alpha_moment = np.array(
        [_quadratic_minimizer(item) for item in coefficient_moment]
    )
    alpha_surface = np.array(
        [_quadratic_minimizer(item) for item in coefficient_surface]
    )
    alpha_one_to_one = np.array(
        [
            _weighted_alpha(force, surface, 1.0)
            for force, surface in zip(
                coefficient_force, coefficient_surface, strict=True
            )
        ]
    )
    strategies = {
        "minimum_force": _strategy_metrics(
            "minimum_force",
            alpha_force,
            w0,
            null,
            surface_mappings,
            allocation_matrices,
            torque,
        ),
        "minimum_moment": _strategy_metrics(
            "minimum_moment",
            alpha_moment,
            w0,
            null,
            surface_mappings,
            allocation_matrices,
            torque,
        ),
        "minimum_surface_proxy": _strategy_metrics(
            "minimum_surface_proxy",
            alpha_surface,
            w0,
            null,
            surface_mappings,
            allocation_matrices,
            torque,
        ),
        "current_one_to_one": _strategy_metrics(
            "current_one_to_one",
            alpha_one_to_one,
            w0,
            null,
            surface_mappings,
            allocation_matrices,
            torque,
        ),
    }

    pareto: list[dict[str, Any]] = []
    for ratio in WEIGHT_RATIOS:
        alpha = np.array(
            [
                _weighted_alpha(force, surface, float(ratio))
                for force, surface in zip(
                    coefficient_force, coefficient_surface, strict=True
                )
            ]
        )
        metrics = _strategy_metrics(
            "surface_to_force_weight_ratio",
            alpha,
            w0,
            null,
            surface_mappings,
            allocation_matrices,
            torque,
        )
        pareto.append(
            {
                "surface_to_force_weight_ratio": (
                    "infinity" if np.isinf(ratio) else float(ratio)
                ),
                **metrics,
            }
        )

    force_endpoint = strategies["minimum_force"]
    surface_endpoint = strategies["minimum_surface_proxy"]
    force_min = force_endpoint["resultant_force_n"]["rms"]
    force_max = surface_endpoint["resultant_force_n"]["rms"]
    surface_max = force_endpoint["cylindrical_surface_effort_proxy_n"]["rms"]
    surface_min = surface_endpoint["cylindrical_surface_effort_proxy_n"]["rms"]
    finite_front = pareto[1:-1]
    for point in finite_front:
        point["normalized_force_position"] = (
            point["resultant_force_n"]["rms"] - force_min
        ) / (force_max - force_min)
        point["normalized_surface_position"] = (
            point["cylindrical_surface_effort_proxy_n"]["rms"] - surface_min
        ) / (surface_max - surface_min)
        point["distance_below_endpoint_chord"] = (
            1.0
            - point["normalized_force_position"]
            - point["normalized_surface_position"]
        ) / np.sqrt(2.0)
    knee = max(finite_front, key=lambda item: item["distance_below_endpoint_chord"])
    one_to_one = next(
        item
        for item in finite_front
        if np.isclose(item["surface_to_force_weight_ratio"], 1.0)
    )

    representative_indices = sorted(
        {
            int(np.argmax(np.linalg.norm(w0[:, :2], axis=1))),
            int(
                np.argmax(
                    np.linalg.norm(
                        np.einsum("tij,tj->ti", surface_mappings, w0), axis=1
                    )
                )
            ),
            int(np.argmin(np.abs(phase - 13.0))),
        }
    )
    representatives = []
    for index in representative_indices:
        representatives.append(
            {
                "wall_time_s": float(time[index]),
                "reference_phase_s": float(phase[index]),
                "q_rad": q[index].tolist(),
                "fixed_tau_h_nm": torque[index].tolist(),
                "w0_Fx_Fz_My": w0[index].tolist(),
                "null_direction": null[index].tolist(),
                "quadratic_coefficients_order_alpha2_alpha_constant": {
                    "force_squared": coefficient_force[index].tolist(),
                    "moment_squared": coefficient_moment[index].tolist(),
                    "surface_squared": coefficient_surface[index].tolist(),
                },
                "alpha_n": {
                    "minimum_force": float(alpha_force[index]),
                    "minimum_moment": float(alpha_moment[index]),
                    "minimum_surface_proxy": float(alpha_surface[index]),
                    "one_to_one": float(alpha_one_to_one[index]),
                },
            }
        )

    return {
        "evidence_category": "stage4_exact_1d_cuff_allocation_tradeoff_audit",
        "formal_experiment": False,
        "source": {
            "trajectory": "existing_registered_continuous_high_flexion",
            "source_allocator": "current_force_minimizing_allocator rollout",
            "sample_grid": "native 20 ms MPC updates through phase completion",
            "sample_count": count,
            "fixed_tau_h_at_every_sample": True,
            "registered_human": metadata,
        },
        "analytic_contract": {
            "feasible_line": "w(alpha)=w0+alpha*n(q), B(q)n(q)=0",
            "force_squared": "||F0||^2+2*F0^T*nF*alpha+||nF||^2*alpha^2",
            "minimum_force_simplification": (
                "F0^T*nF=0 and ||nF||=1, hence ||F||^2=||F0||^2+alpha^2"
            ),
            "moment_squared": "My0^2+2*My0*nM*alpha+nM^2*alpha^2",
            "surface_squared": (
                "||G*w0||^2+2*(G*w0)^T*(G*n)*alpha+||G*n||^2*alpha^2"
            ),
            "surface_mapping": "G(q)=A_dagger*T_cuff_world(q)*S(q)",
            "proxy_interpretation": (
                "minimum-norm equivalent cylindrical patch-force effort; "
                "not pressure or comfort"
            ),
        },
        "strategies": strategies,
        "pareto_front": pareto,
        "knee_analysis": {
            "method": (
                "maximum perpendicular distance below the normalized RMS endpoint chord"
            ),
            "knee_point": knee,
            "current_one_to_one_point": one_to_one,
            "one_to_one_weight_ratio_over_knee_ratio": (
                1.0 / float(knee["surface_to_force_weight_ratio"])
            ),
            "maximum_possible_normalized_chord_distance": float(1.0 / np.sqrt(2.0)),
        },
        "representative_samples": representatives,
        "controller_or_allocator_modified": False,
        "safety_limits_modified": False,
    }
