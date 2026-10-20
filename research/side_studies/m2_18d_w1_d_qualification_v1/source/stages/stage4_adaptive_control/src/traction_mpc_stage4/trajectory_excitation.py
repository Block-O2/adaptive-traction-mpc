"""Preregistered rehabilitation trajectory suite and offline excitation audit.

The audit evaluates exact nominal reference kinematics and the exact Human-V2
11-base inverse-dynamics model.  It is design evidence only: no closed-loop
controller, sensor stream, trust decision, or formal experiment is executed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff, quintic_progress

from .estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES, dynamic_regressor_row, nominal_base_parameters
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier, integral_regression_block
from .reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    TeachingWaypoint,
    cold_start_joint_reference,
)


DEFAULT_SUITE_PATH = Path(__file__).resolve().parents[2] / "configs" / "stage4_trajectory_excitation_suite.json"
PARAMETER_GROUPS = {
    "inertia_coupling": (0, 1, 2),
    "gravity": (3, 4),
    "passive_stiffness": (5, 6),
    "passive_rest_offset": (7, 8),
    "viscous_damping": (9, 10),
}


def load_trajectory_suite(path: Path = DEFAULT_SUITE_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "stage4_trajectory_excitation_suite_v1":
        raise ValueError("unsupported trajectory-excitation suite schema")
    cases = payload.get("cases", [])
    identifiers = [item.get("trajectory_id") for item in cases]
    if not cases or len(identifiers) != len(set(identifiers)):
        raise ValueError("trajectory suite must contain unique cases")
    return payload


def trajectory_case(trajectory_id: str, suite: dict[str, Any] | None = None) -> dict[str, Any]:
    source = load_trajectory_suite() if suite is None else suite
    matches = [item for item in source["cases"] if item["trajectory_id"] == trajectory_id]
    if len(matches) != 1:
        raise KeyError(f"unknown trajectory id {trajectory_id!r}")
    return matches[0]


def _piecewise_quintic_reference(case: dict[str, Any], time_s: float) -> tuple[np.ndarray, ...]:
    waypoints = case["waypoints"]
    time = float(np.clip(time_s, 0.0, float(case["duration_s"])))
    for start, end in zip(waypoints[:-1], waypoints[1:], strict=True):
        if time <= float(end["time_s"]) + 1e-12:
            duration = float(end["time_s"]) - float(start["time_s"])
            if duration <= 0.0:
                raise ValueError("trajectory waypoint times must strictly increase")
            q0 = np.radians(start["q_deg"])
            delta = np.radians(np.asarray(end["q_deg"], dtype=float) - np.asarray(start["q_deg"], dtype=float))
            if np.allclose(delta, 0.0):
                return q0, np.zeros(2), np.zeros(2)
            progress, velocity, acceleration = quintic_progress((time - float(start["time_s"])) / duration)
            return q0 + delta * progress, delta * velocity / duration, delta * acceleration / duration**2
    return np.radians(waypoints[-1]["q_deg"]), np.zeros(2), np.zeros(2)


def trajectory_joint_reference(case: dict[str, Any], time_s: float) -> tuple[np.ndarray, ...]:
    """Evaluate one preregistered joint trajectory and its first two derivatives."""

    construction = case["construction"]
    duration = float(case["duration_s"])
    time = float(np.clip(time_s, 0.0, duration))
    if construction == "registered_cold_start_anchor":
        if not np.isclose(duration, COLD_START_TEACHING_DURATION_S):
            raise ValueError("registered anchor duration changed")
        return cold_start_joint_reference(time)
    if construction == "anchor_excursion_scale":
        q, dq, ddq = cold_start_joint_reference(time)
        initial = cold_start_joint_reference(0.0)[0]
        scale = np.asarray(case["joint_excursion_scale"], dtype=float)
        return initial + scale * (q - initial), scale * dq, scale * ddq
    if construction == "anchor_time_scale":
        scale = float(case["time_scale"])
        if scale <= 0.0 or not np.isclose(duration, scale * COLD_START_TEACHING_DURATION_S):
            raise ValueError("invalid anchor time scale")
        q, dq, ddq = cold_start_joint_reference(time / scale)
        return q, dq / scale, ddq / scale**2
    if construction == "piecewise_quintic_waypoints":
        return _piecewise_quintic_reference(case, time)
    raise ValueError(f"unsupported trajectory construction {construction!r}")


def trajectory_reference(case: dict[str, Any], time_s: float) -> CuffPoseReference:
    q, dq, ddq = trajectory_joint_reference(case, time_s)
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))


def trajectory_waypoints(case: dict[str, Any]) -> tuple[TeachingWaypoint, ...]:
    """Return metadata waypoints derived from, but never modifying, the config."""

    construction = case["construction"]
    if construction == "registered_cold_start_anchor":
        return COLD_START_TEACHING_WAYPOINTS
    if construction == "anchor_excursion_scale":
        initial = np.asarray(COLD_START_TEACHING_WAYPOINTS[0].q_deg, dtype=float)
        scale = np.asarray(case["joint_excursion_scale"], dtype=float)
        return tuple(
            TeachingWaypoint(
                item.time_s,
                tuple(initial + scale * (np.asarray(item.q_deg) - initial)),
                item.label,
            )
            for item in COLD_START_TEACHING_WAYPOINTS
        )
    if construction == "anchor_time_scale":
        scale = float(case["time_scale"])
        return tuple(
            TeachingWaypoint(scale * item.time_s, item.q_deg, item.label)
            for item in COLD_START_TEACHING_WAYPOINTS
        )
    if construction == "piecewise_quintic_waypoints":
        return tuple(
            TeachingWaypoint(
                float(item["time_s"]),
                tuple(float(value) for value in item["q_deg"]),
                str(item["label"]),
            )
            for item in case["waypoints"]
        )
    raise ValueError(f"unsupported trajectory construction {construction!r}")


def _matrix_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = float(singular[0] * 1e-10) if len(singular) else 0.0
    rank = int(np.sum(singular > tolerance))
    condition = float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 0.0 else float("inf")
    return {
        "rank": rank,
        "nullity": int(matrix.shape[1] - rank),
        "rank_tolerance": tolerance,
        "condition_number": condition,
        "singular_values": singular.tolist(),
    }


def _weak_directions(matrix: np.ndarray, count: int = 3) -> list[dict[str, Any]]:
    _, singular, vh = np.linalg.svd(matrix, full_matrices=False)
    results: list[dict[str, Any]] = []
    for vector_index in range(1, min(count, len(singular)) + 1):
        vector = vh[-vector_index]
        component_order = np.argsort(np.abs(vector))[::-1]
        group_energy = {
            name: float(np.sum(vector[np.asarray(indices, dtype=int)] ** 2))
            for name, indices in PARAMETER_GROUPS.items()
        }
        results.append(
            {
                "singular_value": float(singular[-vector_index]),
                "span_normalized_direction": vector.tolist(),
                "dominant_components": [
                    {
                        "parameter": DYNAMIC_BASE_PARAMETER_NAMES[int(index)],
                        "loading": float(vector[index]),
                        "absolute_loading": float(abs(vector[index])),
                    }
                    for index in component_order[:4]
                ],
                "group_energy": group_energy,
            }
        )
    return results


def audit_trajectory_case(case: dict[str, Any], audit_config: dict[str, Any]) -> dict[str, Any]:
    dt = float(audit_config["sample_period_s"])
    window_s = float(audit_config["integral_window_s"])
    stride = int(audit_config["block_stride_measurements"])
    duration = float(case["duration_s"])
    times = np.arange(0.0, duration + 0.5 * dt, dt)
    references = [trajectory_joint_reference(case, float(time)) for time in times]
    q = np.asarray([item[0] for item in references])
    dq = np.asarray([item[1] for item in references])
    ddq = np.asarray([item[2] for item in references])
    state = np.column_stack([q, dq])
    beta = nominal_base_parameters()
    torque = np.asarray(
        [dynamic_regressor_row(q_i, dq_i, ddq_i) @ beta for q_i, dq_i, ddq_i in zip(q, dq, ddq, strict=True)]
    )
    window_samples = int(round(window_s / dt))
    if not np.isclose(window_samples * dt, window_s):
        raise ValueError("integral window must be an integer number of audit samples")
    rows: list[np.ndarray] = []
    target_errors: list[np.ndarray] = []
    end_times: list[float] = []
    for end in range(window_samples, len(times), stride):
        start = end - window_samples
        regressor, target = integral_regression_block(
            times[start : end + 1], state[start : end + 1], torque[start : end + 1]
        )
        rows.append(regressor)
        target_errors.append(regressor @ beta - target)
        end_times.extend([float(times[end]), float(times[end])])
    raw = np.vstack(rows)
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    scaled = raw * identifier.span
    column_norms = np.linalg.norm(scaled, axis=0)
    normalized = scaled / np.where(column_norms > 1e-15, column_norms, 1.0)
    information = scaled.T @ scaled
    normalized_information = normalized.T @ normalized
    residual = np.concatenate(target_errors)
    q_deg = np.degrees(q)
    dq_deg_s = np.degrees(dq)
    ddq_deg_s2 = np.degrees(ddq)
    return {
        "trajectory_id": case["trajectory_id"],
        "duration_s": duration,
        "sample_count": int(len(times)),
        "integral_block_count": int(len(rows)),
        "integral_regressor_rows": int(raw.shape[0]),
        "kinematics": {
            "minimum_q_deg": np.min(q_deg, axis=0).tolist(),
            "maximum_q_deg": np.max(q_deg, axis=0).tolist(),
            "rom_deg": np.ptp(q_deg, axis=0).tolist(),
            "peak_abs_velocity_deg_s": np.max(np.abs(dq_deg_s), axis=0).tolist(),
            "peak_abs_acceleration_deg_s2": np.max(np.abs(ddq_deg_s2), axis=0).tolist(),
        },
        "nominal_oracle_integral_identity": {
            "maximum_abs_error_nms": float(np.max(np.abs(residual))),
            "rms_error_nms": float(np.sqrt(np.mean(residual**2))),
        },
        "column_normalized_gate_diagnostics": _matrix_diagnostics(normalized),
        "estimator_span_scaled_diagnostics": _matrix_diagnostics(scaled),
        "estimator_span_scaled_information_matrix": information.tolist(),
        "column_normalized_information_matrix": normalized_information.tolist(),
        "information_matrix_summary": {
            "trace": float(np.trace(information)),
            "eigenvalues_ascending": np.linalg.eigvalsh(information).tolist(),
            "diagonal": np.diag(information).tolist(),
        },
        "weak_span_normalized_parameter_directions": _weak_directions(scaled),
        "integral_block_end_times_s": end_times,
    }


def run_trajectory_excitation_audit(path: Path = DEFAULT_SUITE_PATH) -> dict[str, Any]:
    suite = load_trajectory_suite(path)
    return {
        "schema_version": "stage4_trajectory_excitation_offline_audit_v1",
        "evidence_category": "offline_nominal_oracle_design_audit",
        "formal_experiment": False,
        "closed_loop_executed": False,
        "trajectory_redesign_after_audit_permitted": False,
        "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "parameter_groups": {name: [DYNAMIC_BASE_PARAMETER_NAMES[index] for index in indices] for name, indices in PARAMETER_GROUPS.items()},
        "audit_config": suite["audit"],
        "cases": [audit_trajectory_case(case, suite["audit"]) for case in suite["cases"]],
        "limitations": [
            "exact nominal reference kinematics and nominal Human-V2 inverse dynamics only",
            "overlapping integral windows make the accumulated matrix a design information proxy, not an independent-sample Fisher matrix",
            "no sensor, reconstruction, contact, controller, trust, pacing, or safety outcome is simulated",
            "weak singular directions are control-effective 11-base combinations, not separately identified anatomy",
        ],
    }
