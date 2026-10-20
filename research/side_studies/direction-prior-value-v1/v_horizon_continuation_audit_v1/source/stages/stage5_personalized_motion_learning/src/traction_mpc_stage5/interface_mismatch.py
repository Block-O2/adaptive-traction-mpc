"""Small one-factor Stage-5 plant-interface mismatch sweep contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from traction_mpc_stage3.spring_damper_interface import InterfaceParameters
from traction_mpc_stage4.mpc import HumanMPCConfig

from .config import STAGE5_ROOT
from .controller_interface import CONTROLLER_NOMINAL_INTERFACE
from .mechanics import STAGE5_RIGID_INTERFACE
from .task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_interface_mismatch_v1.json"
CHECKPOINT_SUMMARY_PATH = (
    STAGE5_ROOT
    / "results"
    / "goal_mpc_runtime_v1"
    / "optimized_attempt_03_final"
    / "summary.json"
)


@dataclass(frozen=True)
class InterfaceMismatchCase:
    name: str
    factor: str
    scale: float
    plant_truth: InterfaceParameters


def interface_record(interface: Any) -> dict[str, Any]:
    return {
        "translation_stiffness_n_m": list(interface.translation_stiffness_n_m),
        "translation_damping_ns_m": list(interface.translation_damping_ns_m),
        "rotation_stiffness_nm_rad": float(interface.rotation_stiffness_nm_rad),
        "rotation_damping_nms_rad": float(interface.rotation_damping_nms_rad),
    }


def _assert_record_equal(name: str, actual: Mapping[str, Any], expected: Any) -> None:
    expected_record = interface_record(expected)
    for key, expected_value in expected_record.items():
        if not np.array_equal(
            np.asarray(actual[key], dtype=float),
            np.asarray(expected_value, dtype=float),
        ):
            raise ValueError(f"{name} {key} differs from the frozen checkpoint")


def load_and_validate_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema") != "stage5_interface_mismatch_v1":
        raise ValueError("unexpected interface-mismatch schema")
    if record.get("controller_retuning_allowed") is not False:
        raise ValueError("Interface Mismatch v1 forbids controller retuning")
    _assert_record_equal(
        "controller nominal",
        record["controller_nominal_interface"],
        CONTROLLER_NOMINAL_INTERFACE,
    )
    _assert_record_equal(
        "plant truth base",
        record["plant_truth_base_interface"],
        STAGE5_RIGID_INTERFACE,
    )
    expected_factors = {
        "translation_stiffness",
        "rotation_stiffness",
        "translation_and_rotation_damping",
    }
    sweeps = record.get("one_factor_sweeps", {})
    if set(sweeps) != expected_factors:
        raise ValueError("unexpected one-factor sweep definition")
    for factor, scales in sweeps.items():
        if not np.array_equal(np.asarray(scales, dtype=float), [0.7, 1.0, 1.3]):
            raise ValueError(f"unexpected scales for {factor}")
    defaults = HumanMPCConfig()
    expected_settings = {
        "task": PROVISIONAL_LOW_MODERATE_GOAL_TASK.name,
        "random_seed": defaults.random_seed,
        "prediction_dt_s": defaults.prediction_dt_s,
        "horizon_steps": defaults.horizon_steps,
        "candidate_count": defaults.candidate_count,
        "elite_count": defaults.elite_count,
        "cem_iterations": defaults.cem_iterations,
    }
    if record.get("shared_checkpoint_settings") != expected_settings:
        raise ValueError("shared task/CEM settings differ from the frozen checkpoint")
    return record


def scaled_plant_truth(factor: str, scale: float) -> InterfaceParameters:
    base = STAGE5_RIGID_INTERFACE
    kt = np.asarray(base.translation_stiffness_n_m, dtype=float)
    dt = np.asarray(base.translation_damping_ns_m, dtype=float)
    kr = float(base.rotation_stiffness_nm_rad)
    dr = float(base.rotation_damping_nms_rad)
    if factor == "translation_stiffness":
        kt *= scale
    elif factor == "rotation_stiffness":
        kr *= scale
    elif factor == "translation_and_rotation_damping":
        dt *= scale
        dr *= scale
    elif factor != "nominal":
        raise ValueError(f"unknown mismatch factor {factor!r}")
    return InterfaceParameters(
        translation_stiffness_n_m=tuple(float(value) for value in kt),
        translation_damping_ns_m=tuple(float(value) for value in dt),
        rotation_stiffness_nm_rad=kr,
        rotation_damping_nms_rad=dr,
    )


def unique_cases() -> tuple[InterfaceMismatchCase, ...]:
    load_and_validate_config()
    return (
        InterfaceMismatchCase("kt_0p7", "translation_stiffness", 0.7, scaled_plant_truth("translation_stiffness", 0.7)),
        InterfaceMismatchCase("nominal_1p0", "nominal", 1.0, scaled_plant_truth("nominal", 1.0)),
        InterfaceMismatchCase("kt_1p3", "translation_stiffness", 1.3, scaled_plant_truth("translation_stiffness", 1.3)),
        InterfaceMismatchCase("kr_0p7", "rotation_stiffness", 0.7, scaled_plant_truth("rotation_stiffness", 0.7)),
        InterfaceMismatchCase("kr_1p3", "rotation_stiffness", 1.3, scaled_plant_truth("rotation_stiffness", 1.3)),
        InterfaceMismatchCase("d_0p7", "translation_and_rotation_damping", 0.7, scaled_plant_truth("translation_and_rotation_damping", 0.7)),
        InterfaceMismatchCase("d_1p3", "translation_and_rotation_damping", 1.3, scaled_plant_truth("translation_and_rotation_damping", 1.3)),
    )


def expanded_matrix_rows() -> tuple[dict[str, Any], ...]:
    rows = []
    aliases = {
        "translation_stiffness": "Kt",
        "rotation_stiffness": "Kr",
        "translation_and_rotation_damping": "D",
    }
    for factor, label in aliases.items():
        for scale in (0.7, 1.0, 1.3):
            rows.append(
                {
                    "matrix_cell": f"{label}_x{scale:.1f}",
                    "factor": factor,
                    "scale": scale,
                    "source_case": (
                        "nominal_1p0"
                        if scale == 1.0
                        else f"{label.lower()}_{str(scale).replace('.', 'p')}"
                    ),
                }
            )
    return tuple(rows)


def _aligned_prediction_errors(trace: Mapping[str, np.ndarray]) -> dict[str, Any]:
    prediction_time = np.asarray(trace["selected_prediction_time_s"], dtype=float)
    if not len(prediction_time):
        return {"aligned_count": 0}
    time = np.asarray(trace["time_s"], dtype=float)
    indices = np.searchsorted(time, prediction_time + 0.020 - 1.0e-12)
    valid = indices < len(time)
    indices = indices[valid]

    def vector_norm_stats(error: np.ndarray, scale: float = 1.0) -> dict[str, float]:
        norm = scale * np.linalg.norm(error, axis=1)
        return {
            "rmse": float(np.sqrt(np.mean(norm**2))),
            "p95": float(np.percentile(norm, 95)),
            "max": float(np.max(norm)),
        }

    predicted_translation = np.asarray(
        trace["selected_prediction_first_interface_translation_human_m"]
    )[valid]
    predicted_rotation = np.asarray(
        trace["selected_prediction_first_interface_rotation_human_rad"]
    )[valid]
    estimated_translation = np.asarray(
        trace["estimated_interface_translation_human_m"]
    )[indices]
    estimated_rotation = np.asarray(
        trace["estimated_interface_rotation_human_rad"]
    )[indices]
    truth_translation = np.asarray(trace["interface_translation_human_m"])[indices]
    truth_rotation = np.asarray(trace["interface_rotation_human_rad"])[indices]
    predicted_state = np.asarray(
        trace["selected_prediction_first_state_rad_rad_s"]
    )[valid]
    estimated_state = np.asarray(trace["estimated_state_rad_rad_s"])[indices]
    truth_state = np.column_stack(
        [
            np.asarray(trace["evaluation_human_q_rad"])[indices],
            np.asarray(trace["evaluation_human_dq_rad_s"])[indices],
        ]
    )
    return {
        "aligned_count": int(np.count_nonzero(valid)),
        "translation_prediction_vs_deployable_estimate_mm": vector_norm_stats(
            predicted_translation - estimated_translation, 1000.0
        ),
        "translation_prediction_vs_plant_truth_mm": vector_norm_stats(
            predicted_translation - truth_translation, 1000.0
        ),
        "rotation_prediction_vs_deployable_estimate_deg": vector_norm_stats(
            predicted_rotation - estimated_rotation, 180.0 / np.pi
        ),
        "rotation_prediction_vs_plant_truth_deg": vector_norm_stats(
            predicted_rotation - truth_rotation, 180.0 / np.pi
        ),
        "human_q_prediction_vs_deployable_estimate_deg": vector_norm_stats(
            predicted_state[:, :2] - estimated_state[:, :2], 180.0 / np.pi
        ),
        "human_q_prediction_vs_truth_deg": vector_norm_stats(
            predicted_state[:, :2] - truth_state[:, :2], 180.0 / np.pi
        ),
        "human_dq_prediction_vs_deployable_estimate_deg_s": vector_norm_stats(
            predicted_state[:, 2:] - estimated_state[:, 2:], 180.0 / np.pi
        ),
        "human_dq_prediction_vs_truth_deg_s": vector_norm_stats(
            predicted_state[:, 2:] - truth_state[:, 2:], 180.0 / np.pi
        ),
    }


def compact_cell(
    case: InterfaceMismatchCase,
    summary: Mapping[str, Any],
    trace: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    transitions = {item["phase"]: item["time_s"] for item in summary["phase_transitions"]}
    terminal_time = float(summary["task_duration_s"])
    phase_timing = {
        "outbound_entry_s": transitions.get("OUTBOUND"),
        "hold_entry_s": transitions.get("HOLD"),
        "return_entry_s": transitions.get("RETURN"),
        "complete_entry_s": transitions.get("COMPLETE"),
        "termination_s": terminal_time,
    }
    velocity_limit = np.asarray(summary["task_spec"]["task_joint_velocity_limit_deg_s"])
    acceleration_limit = np.asarray(summary["task_spec"]["task_joint_acceleration_limit_deg_s2"])
    estimated_velocity = np.asarray(summary["peak_abs_estimated_joint_velocity_deg_s"])
    truth_velocity = np.asarray(summary["peak_abs_evaluation_only_joint_velocity_deg_s"])
    estimated_acceleration = np.asarray(summary["peak_abs_estimated_joint_acceleration_deg_s2"])
    truth_acceleration = np.asarray(summary["peak_abs_evaluation_only_joint_acceleration_deg_s2"])
    filter_counts = summary["safety_filter_status_counts"]
    intervention_count = sum(
        int(count) for status, count in filter_counts.items() if status != "SAFE_UNCHANGED"
    )
    controller = interface_record(CONTROLLER_NOMINAL_INTERFACE)
    plant = interface_record(case.plant_truth)
    return {
        "case": case.name,
        "factor": case.factor,
        "scale": case.scale,
        "controller_nominal_interface": controller,
        "plant_truth_interface": plant,
        "controller_minus_plant_explicit": {
            key: (np.asarray(controller[key]) - np.asarray(plant[key])).tolist()
            for key in controller
        },
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "phase_timing": phase_timing,
        "peak_estimated_velocity_deg_s": estimated_velocity.tolist(),
        "peak_truth_velocity_deg_s": truth_velocity.tolist(),
        "velocity_margin_estimated_deg_s": (velocity_limit - estimated_velocity).tolist(),
        "velocity_margin_truth_deg_s": (velocity_limit - truth_velocity).tolist(),
        "peak_deployable_acceleration_deg_s2": estimated_acceleration.tolist(),
        "peak_truth_acceleration_deg_s2": truth_acceleration.tolist(),
        "acceleration_margin_deployable_deg_s2": (
            acceleration_limit - estimated_acceleration
        ).tolist(),
        "acceleration_margin_truth_deg_s2": (
            acceleration_limit - truth_acceleration
        ).tolist(),
        "peak_physical_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_force_n_s": summary["cumulative_physical_cuff_force_n_s"],
        "peak_physical_moment_nm": summary["peak_physical_cuff_moment_nm"],
        "maximum_interface_translation_mm": summary["peak_interface_translation_mm"],
        "maximum_interface_rotation_deg": summary["peak_interface_rotation_deg"],
        "human_state_estimation_error": summary["human_state_estimation_error"],
        "interface_prediction_error": _aligned_prediction_errors(trace),
        "force_prediction_error": summary["physical_force_prediction_error"],
        "mpc_status_counts": summary["mpc_status_counts"],
        "mpc_failure_count": summary["mpc_failure_count"],
        "safety_filter_status_counts": filter_counts,
        "safety_filter_intervention_count": intervention_count,
        "maximum_safety_filter_intervention_coordinate_norm": summary[
            "maximum_safety_filter_intervention_coordinate_norm"
        ],
        "brake_event_count": summary["brake_event_count"],
        "force_gate_event_count": summary["force_gate_event_count"],
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
        "mpc_runtime_ms": summary["mpc_runtime_ms"],
        "maximum_normalized_q1_q2_progress_difference": summary[
            "maximum_normalized_q1_q2_progress_difference"
        ],
        "path_freedom": {
            "prescribed_full_q_reference_used": summary[
                "prescribed_full_q_reference_used"
            ],
            "fixed_q1_q2_coordination_ratio": summary[
                "fixed_q1_q2_coordination_ratio"
            ],
            "path_corridor_active": summary["path_corridor_active"],
        },
    }


def compact_startup_abort(
    case: InterfaceMismatchCase,
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve a t=0 task-start rejection without weakening task semantics."""

    estimated_q = np.asarray(diagnostics["estimated_q_rad"], dtype=float)
    estimated_dq = np.asarray(diagnostics["estimated_dq_rad_s"], dtype=float)
    truth_q = np.asarray(diagnostics["truth_q_rad"], dtype=float)
    truth_dq = np.asarray(diagnostics["truth_dq_rad_s"], dtype=float)
    estimated_acceleration = np.asarray(
        diagnostics["deployable_acceleration_rad_s2"], dtype=float
    )
    truth_acceleration = np.asarray(
        diagnostics["truth_acceleration_rad_s2"], dtype=float
    )
    velocity_limit = np.asarray(diagnostics["task_velocity_limit_rad_s"], dtype=float)
    acceleration_limit = np.asarray(
        diagnostics["task_acceleration_limit_rad_s2"], dtype=float
    )
    force = np.asarray(diagnostics["physical_force_world_n"], dtype=float)
    moment = np.asarray(diagnostics["physical_moment_world_nm"], dtype=float)
    truth_translation = np.asarray(
        diagnostics["truth_interface_translation_human_m"], dtype=float
    )
    truth_rotation = np.asarray(
        diagnostics["truth_interface_rotation_human_rad"], dtype=float
    )
    controller = interface_record(CONTROLLER_NOMINAL_INTERFACE)
    plant = interface_record(case.plant_truth)

    return {
        "case": case.name,
        "factor": case.factor,
        "scale": case.scale,
        "controller_nominal_interface": controller,
        "plant_truth_interface": plant,
        "controller_minus_plant_explicit": {
            key: (np.asarray(controller[key]) - np.asarray(plant[key])).tolist()
            for key in controller
        },
        "task_status": "ABORTED",
        "abort_reason": diagnostics["abort_reason"],
        "startup_validation_error": diagnostics["validation_error"],
        "phase_timing": {
            "outbound_entry_s": None,
            "hold_entry_s": None,
            "return_entry_s": None,
            "complete_entry_s": None,
            "termination_s": float(diagnostics["time_s"]),
        },
        "peak_estimated_velocity_deg_s": np.degrees(np.abs(estimated_dq)).tolist(),
        "peak_truth_velocity_deg_s": np.degrees(np.abs(truth_dq)).tolist(),
        "velocity_margin_estimated_deg_s": np.degrees(
            velocity_limit - np.abs(estimated_dq)
        ).tolist(),
        "velocity_margin_truth_deg_s": np.degrees(
            velocity_limit - np.abs(truth_dq)
        ).tolist(),
        "peak_deployable_acceleration_deg_s2": np.degrees(
            np.abs(estimated_acceleration)
        ).tolist(),
        "peak_truth_acceleration_deg_s2": np.degrees(
            np.abs(truth_acceleration)
        ).tolist(),
        "acceleration_margin_deployable_deg_s2": np.degrees(
            acceleration_limit - np.abs(estimated_acceleration)
        ).tolist(),
        "acceleration_margin_truth_deg_s2": np.degrees(
            acceleration_limit - np.abs(truth_acceleration)
        ).tolist(),
        "peak_physical_force_n": float(np.linalg.norm(force)),
        "cumulative_physical_force_n_s": 0.0,
        "peak_physical_moment_nm": float(np.linalg.norm(moment)),
        "maximum_interface_translation_mm": float(
            1000.0 * np.linalg.norm(truth_translation)
        ),
        "maximum_interface_rotation_deg": float(
            np.degrees(np.linalg.norm(truth_rotation))
        ),
        "human_state_estimation_error": {
            "q_rmse_deg": np.degrees(np.abs(estimated_q - truth_q)).tolist(),
            "q_peak_abs_deg": np.degrees(np.abs(estimated_q - truth_q)).tolist(),
            "dq_rmse_deg_s": np.degrees(np.abs(estimated_dq - truth_dq)).tolist(),
            "dq_peak_abs_deg_s": np.degrees(np.abs(estimated_dq - truth_dq)).tolist(),
            "truth_role": "evaluation_only",
        },
        "interface_prediction_error": {"aligned_count": 0},
        "force_prediction_error": {
            "aligned_prediction_count": 0,
            "vector_error_rmse_n": None,
            "vector_error_p95_n": None,
            "vector_error_max_n": None,
            "norm_error_rmse_n": None,
            "norm_error_p95_n": None,
            "norm_error_max_n": None,
        },
        "mpc_status_counts": {"SAFE_ACTION": 0, "NO_SAFE_ACTION": 0},
        "mpc_failure_count": 0,
        "safety_filter_status_counts": {},
        "safety_filter_intervention_count": 0,
        "maximum_safety_filter_intervention_coordinate_norm": 0.0,
        "brake_event_count": 0,
        "force_gate_event_count": 0,
        "mujoco_warning_counts": diagnostics["mujoco_warning_counts"],
        "mpc_runtime_ms": {
            "mean": None,
            "p95": None,
            "max": None,
            "replanning_period_ms": 20.0,
            "deadline_miss_count": 0,
            "deadline_miss_fraction": None,
        },
        "maximum_normalized_q1_q2_progress_difference": None,
        "path_freedom": {
            "prescribed_full_q_reference_used": False,
            "fixed_q1_q2_coordination_ratio": False,
            "path_corridor_active": False,
        },
    }


__all__ = [
    "CHECKPOINT_SUMMARY_PATH",
    "CONFIG_PATH",
    "InterfaceMismatchCase",
    "compact_cell",
    "compact_startup_abort",
    "expanded_matrix_rows",
    "interface_record",
    "load_and_validate_config",
    "scaled_plant_truth",
    "unique_cases",
]
