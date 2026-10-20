#!/usr/bin/env python3
"""Separate Interface-ID information limits from Stage-5 predictor bias.

The audit is offline and exploratory.  It uses no new MuJoCo rollout, never
publishes parameters, and does not connect the identifier to control.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage5.interface_identification import (
    InterfaceIdentificationMeasurement,
    InterfaceIdentificationSeries,
    InterfaceParameterScales,
    ShadowInterfaceIdentificationService,
    WindowedInterfacePredictionErrorIdentifier,
    fixed_stage5_human_model,
    load_interface_identification_config,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_ROOT = STAGE5_ROOT / "results" / "interface_mismatch_v1_attempt03"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "interface_model_form_v1_offline"
CASE_TRUTH = {
    "nominal_1p0": (1.0, 1.0, 1.0),
    "kt_0p7": (0.7, 1.0, 1.0),
    "kt_1p3": (1.3, 1.0, 1.0),
    "kr_1p3": (1.0, 1.3, 1.0),
    "d_0p7": (1.0, 1.0, 0.7),
    "d_1p3": (1.0, 1.0, 1.3),
}
SYNTHETIC_CASES = {
    "nominal": (1.0, 1.0, 1.0),
    "kt_low": (0.7, 1.0, 1.0),
    "kr_high": (1.0, 1.3, 1.0),
    "d_low": (1.0, 1.0, 0.7),
}
LANDSCAPES = {
    "kt_0p7": (0, (0.5, 0.7, 0.9)),
    "kr_1p3": (1, (1.1, 1.3, 1.5)),
    "d_0p7": (2, (0.5, 0.7, 0.9)),
}
COMPONENTS = {
    "robot_position": slice(0, 3),
    "robot_rotation": slice(3, 6),
    "robot_linear_velocity": slice(6, 9),
    "robot_angular_velocity": slice(9, 12),
    "cuff_force": slice(12, 15),
    "cuff_moment": slice(15, 18),
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _window_indices(series: InterfaceIdentificationSeries) -> tuple[int, int, int, int]:
    config = load_interface_identification_config()
    dt_s = float(np.median(np.diff(series.time_s)))
    fit = int(round(config.fit_window_s / dt_s))
    embargo = int(round(config.validation_embargo_s / dt_s))
    validation = int(round(config.validation_window_s / dt_s))
    required_s = config.fit_window_s + config.validation_embargo_s + config.validation_window_s
    requested_s = 0.10 if series.time_s[-1] >= 0.10 + required_s else 0.02
    start = int(np.searchsorted(series.time_s, requested_s, side="left"))
    return start, fit, embargo, validation


def _measurement_difference(
    identifier: WindowedInterfacePredictionErrorIdentifier,
    prediction: np.ndarray,
    target: np.ndarray,
) -> np.ndarray:
    return identifier._measurement_difference(prediction, target)  # noqa: SLF001


def _score(
    identifier: WindowedInterfacePredictionErrorIdentifier,
    prediction: np.ndarray,
    target: np.ndarray,
) -> dict[str, Any]:
    difference = _measurement_difference(identifier, prediction, target)
    normalized = difference / identifier.config.measurement_scale
    scale = {
        "robot_position": 1.0e3,
        "robot_rotation": 180.0 / np.pi,
        "robot_linear_velocity": 1.0,
        "robot_angular_velocity": 1.0,
        "cuff_force": 1.0,
        "cuff_moment": 1.0,
    }
    units = {
        "robot_position": "mm",
        "robot_rotation": "deg",
        "robot_linear_velocity": "m/s",
        "robot_angular_velocity": "rad/s",
        "cuff_force": "N",
        "cuff_moment": "Nm",
    }
    components = {}
    for name, coordinates in COMPONENTS.items():
        values = difference[:, coordinates] * scale[name]
        components[name] = {
            "rmse": float(np.sqrt(np.mean(values**2))),
            "p95_vector_norm": float(np.percentile(np.linalg.norm(values, axis=1), 95.0)),
            "max_abs": float(np.max(np.abs(values))),
            "unit": units[name],
        }
    return {
        "normalized_rmse": float(np.sqrt(np.mean(normalized**2))),
        "components": components,
    }


def _parameter_fit_record(result: Any, truth: np.ndarray) -> dict[str, Any]:
    fitted = result.parameter_scales.as_array()
    multistart = np.asarray(
        [item["fitted_parameter_scales"] for item in result.multistart_solutions],
        dtype=float,
    )
    validation = np.asarray(
        [item["validation_normalized_rmse"] for item in result.multistart_solutions],
        dtype=float,
    )
    return {
        "true_parameter_scales_generator_only": truth,
        "fitted_parameter_scales": fitted,
        "absolute_parameter_error": np.abs(fitted - truth),
        "parameter_error_l2": float(np.linalg.norm(fitted - truth)),
        "fit_normalized_rmse": result.fit_normalized_rmse,
        "validation_normalized_rmse": result.validation_normalized_rmse,
        "nominal_validation_normalized_rmse": result.nominal_validation_normalized_rmse,
        "held_out_relative_improvement_vs_nominal": result.validation_relative_improvement,
        "jacobian": asdict(result.identifiability),
        "multistart_parameter_span": np.ptp(multistart, axis=0),
        "multistart_validation_rmse_span": float(np.ptp(validation)),
        "multistart": result.multistart_solutions,
        "estimator_received_true_latent_or_parameters": False,
    }


def _synthetic_series(
    source: InterfaceIdentificationSeries,
    scales: InterfaceParameterScales,
    *,
    duration_s: float = 0.60,
) -> tuple[InterfaceIdentificationSeries, np.ndarray]:
    """Generate in-model raw measurements, then initialize through the service."""

    model = fixed_stage5_human_model()
    generator = WindowedInterfacePredictionErrorIdentifier(human_model=model)
    source_start = int(np.searchsorted(source.time_s, 0.10, side="left"))
    dt_s = float(np.median(np.diff(source.time_s)))
    sample_count = int(round(duration_s / dt_s)) + 1
    stop = source_start + sample_count
    if stop > len(source.time_s):
        raise ValueError("source command segment is too short for synthetic audit")
    time_s = source.time_s[source_start:stop] - source.time_s[source_start]
    initial_state = np.r_[
        source.arrival_human_state[source_start],
        source.arrival_interface_state[source_start],
    ]
    placeholder = InterfaceIdentificationSeries(
        time_s=time_s,
        phase=np.asarray(source.phase[source_start:stop], dtype=str),
        robot_measurement=np.zeros((sample_count, 12)),
        measured_wrench_world=np.zeros((sample_count, 6)),
        executed_wrench_world=source.executed_wrench_world[source_start:stop],
        base_drive_world_n=source.base_drive_world_n[source_start:stop],
        base_angular_drive_world_nm=source.base_angular_drive_world_nm[source_start:stop],
        arrival_human_state=np.tile(initial_state[:4], (sample_count, 1)),
        arrival_interface_state=np.tile(initial_state[4:], (sample_count, 1)),
        source="in_model_generator_placeholder",
        legacy_measurement_reconstruction=False,
        reconstruction_closure_max_abs=0.0,
    )
    rollout = generator.predict_rollout(
        placeholder, 0, sample_count - 1, scales, initial_state
    )
    raw = np.vstack(
        [generator.measurement_from_state(scales, initial_state), rollout.deployable_measurements]
    )
    base_force = np.vstack(
        [placeholder.base_drive_world_n[0], rollout.base_drive_world_n]
    )
    base_moment = np.vstack(
        [placeholder.base_angular_drive_world_nm[0], rollout.base_angular_drive_world_nm]
    )
    service = ShadowInterfaceIdentificationService(model)
    commands = placeholder.executed_wrench_world
    for index, (timestamp, row) in enumerate(zip(time_s, raw, strict=True)):
        service.ingest(
            InterfaceIdentificationMeasurement(
                sample_timestamp_s=float(timestamp),
                arrival_timestamp_s=float(timestamp),
                robot_cuff_position_world_m=row[:3],
                robot_cuff_rotation_world=Rotation.from_rotvec(row[3:6]).as_matrix(),
                robot_cuff_linear_velocity_world_m_s=row[6:9],
                robot_cuff_angular_velocity_world_rad_s=row[9:12],
                measured_cuff_force_world_n=row[12:15],
                measured_cuff_moment_world_nm=row[15:18],
                executed_command_wrench_world=commands[index],
                previous_executed_command_wrench_world=(
                    commands[index - 1] if index else commands[index]
                ),
                prediction_base_drive_world_n=base_force[index],
                prediction_base_angular_drive_world_nm=base_moment[index],
                fixed_human_model_version="stage5_fixed_human_model_v1",
            ),
            phase=str(placeholder.phase[index]),
        )
    return service.series(), initial_state


def _self_consistency(source: InterfaceIdentificationSeries) -> dict[str, Any]:
    cases = {}
    generated = {}
    for name, truth_tuple in SYNTHETIC_CASES.items():
        truth = np.asarray(truth_tuple, dtype=float)
        truth_parameters = InterfaceParameterScales.from_array(truth)
        series, generator_initial_state = _synthetic_series(source, truth_parameters)
        generated[name] = (series, generator_initial_state)
        identifier = WindowedInterfacePredictionErrorIdentifier()
        fit = identifier.fit(series, start_index=0, multistart=True)
        _, fit_steps, embargo_steps, validation_steps = _window_indices(series)
        total_steps = fit_steps + embargo_steps + validation_steps
        validation_slice = slice(fit_steps + embargo_steps, total_steps)
        target = series.output_measurement[1 : total_steps + 1][validation_slice]
        oracle_prediction = identifier.predict_measurements(
            series, 0, total_steps, truth_parameters, generator_initial_state
        )[validation_slice]
        fitted_true_initial = identifier.fit_initial_state_for_fixed_parameters(
            series,
            start_index=0,
            fit_window_s=identifier.config.fit_window_s,
            parameters=truth_parameters,
        )
        fitted_true_prediction = identifier.predict_measurements(
            series, 0, total_steps, truth_parameters, fitted_true_initial
        )[validation_slice]
        record = _parameter_fit_record(fit, truth)
        record.update(
            {
                "evaluation_only_true_parameters_and_generator_initial_state_validation": _score(
                    identifier, oracle_prediction, target
                ),
                "true_parameters_with_fit_window_initial_state_validation": _score(
                    identifier, fitted_true_prediction, target
                ),
                "fit_window_initial_state_distance_from_generator_truth_scaled_l2": float(
                    np.linalg.norm(
                        (fitted_true_initial - generator_initial_state)
                        / identifier.config.initial_state_prior_scale
                    )
                ),
            }
        )
        cases[name] = record

    window_rows = {}
    for case_name in ("kt_low", "kr_high"):
        series, _ = generated[case_name]
        rows = []
        for window_s in (0.10, 0.20, 0.40):
            identifier = WindowedInterfacePredictionErrorIdentifier()
            fit = identifier.fit(
                series,
                start_index=0,
                fit_window_s=window_s,
                embargo_s=identifier.config.validation_embargo_s,
                validation_window_s=identifier.config.validation_window_s,
                multistart=True,
            )
            row = _parameter_fit_record(
                fit, np.asarray(SYNTHETIC_CASES[case_name])
            )
            row["fit_window_s"] = window_s
            rows.append(row)
        window_rows[case_name] = rows
    return {
        "generator_and_identifier_use_same_transition_and_output_model": True,
        "raw_boundary_passed_through_online_initialization_service": True,
        "cases": cases,
        "window_length_dependence": window_rows,
    }


def _evaluation_truth(
    trace_path: Path,
    series: InterfaceIdentificationSeries,
    truth_parameters: InterfaceParameterScales,
    identifier: WindowedInterfacePredictionErrorIdentifier,
) -> tuple[InterfaceIdentificationSeries, np.ndarray]:
    """Build evaluation-only sensor-equivalent targets and true latent states."""

    with np.load(trace_path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        qdq = np.column_stack(
            [trace["evaluation_human_q_rad"], trace["evaluation_human_dq_rad_s"]]
        )
        x = np.asarray(trace["interface_translation_human_m"], dtype=float)
        theta = np.asarray(trace["interface_rotation_human_rad"], dtype=float)
        xdot = np.gradient(x, time_s, axis=0, edge_order=2)
        omega = np.gradient(theta, time_s, axis=0, edge_order=2)
        truth_state = np.column_stack([qdq, x, xdot, theta, omega])
        robot = np.asarray(
            [identifier.measurement_from_state(truth_parameters, state)[:12] for state in truth_state]
        )
        physical_wrench = np.column_stack(
            [trace["physical_cuff_force_world_n"], trace["physical_cuff_moment_world_nm"]]
        )
    return (
        replace(
            series,
            robot_measurement=robot,
            measured_wrench_world=physical_wrench,
            source=f"evaluation_only_sensor_equivalent:{trace_path}",
        ),
        truth_state,
    )


def _latent_score(
    prediction_human: np.ndarray,
    prediction_interface: np.ndarray,
    truth_state: np.ndarray,
) -> dict[str, Any]:
    human_error = prediction_human - truth_state[:, :4]
    interface_error = prediction_interface - truth_state[:, 4:]
    return {
        "human_q_rmse_deg": np.sqrt(np.mean(human_error[:, :2] ** 2, axis=0)) * 180.0 / np.pi,
        "human_dq_rmse_deg_s": np.sqrt(np.mean(human_error[:, 2:] ** 2, axis=0)) * 180.0 / np.pi,
        "interface_translation_rmse_mm": np.sqrt(np.mean(interface_error[:, :3] ** 2, axis=0)) * 1.0e3,
        "interface_velocity_rmse_m_s": np.sqrt(np.mean(interface_error[:, 3:6] ** 2, axis=0)),
        "interface_rotation_rmse_deg": np.sqrt(np.mean(interface_error[:, 6:9] ** 2, axis=0)) * 180.0 / np.pi,
        "interface_angular_velocity_rmse_rad_s": np.sqrt(np.mean(interface_error[:, 9:] ** 2, axis=0)),
    }


def _evaluate_parameters(
    identifier: WindowedInterfacePredictionErrorIdentifier,
    evaluation_series: InterfaceIdentificationSeries,
    truth_state: np.ndarray,
    parameters: InterfaceParameterScales,
    initial_state: np.ndarray,
    start: int,
    fit: int,
    embargo: int,
    validation: int,
) -> dict[str, Any]:
    total = fit + embargo + validation
    rollout = identifier.predict_rollout(
        evaluation_series, start, total, parameters, initial_state
    )
    validation_slice = slice(fit + embargo, total)
    target_slice = slice(start + fit + embargo + 1, start + total + 1)
    return {
        "held_out_deployable_prediction": _score(
            identifier,
            rollout.deployable_measurements[validation_slice],
            evaluation_series.output_measurement[target_slice],
        ),
        "held_out_latent_response_evaluation_only": _latent_score(
            rollout.human_state[validation_slice],
            rollout.interface_state[validation_slice],
            truth_state[target_slice],
        ),
    }


def _plant_model_form_audit(trace_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cases = {}
    cached: dict[str, Any] = {}
    for case_name, truth_tuple in CASE_TRUTH.items():
        trace_path = trace_root / case_name / "trace.npz"
        if not trace_path.exists():
            continue
        identifier = WindowedInterfacePredictionErrorIdentifier()
        series = InterfaceIdentificationSeries.from_saved_trace(trace_path)
        truth_parameters = InterfaceParameterScales.from_array(truth_tuple)
        evaluation_series, truth_state = _evaluation_truth(
            trace_path, series, truth_parameters, identifier
        )
        start, fit, embargo, validation = _window_indices(series)
        truth_initial = truth_state[start]
        fitted_initial = identifier.fit_initial_state_for_fixed_parameters(
            evaluation_series,
            start_index=start,
            fit_window_s=identifier.config.fit_window_s,
            parameters=truth_parameters,
        )
        cases[case_name] = {
            "true_parameter_scales_evaluation_only": truth_tuple,
            "window_start_s": float(series.time_s[start]),
            "truth_initial_state_source": "MuJoCo Human q/dq + plant interface displacement/rotation + evaluation-only offline finite derivative",
            "true_initial_state": _evaluate_parameters(
                identifier,
                evaluation_series,
                truth_state,
                truth_parameters,
                truth_initial,
                start,
                fit,
                embargo,
                validation,
            ),
            "best_fixed_true_parameter_initial_state_fitted_on_fit_window": _evaluate_parameters(
                identifier,
                evaluation_series,
                truth_state,
                truth_parameters,
                fitted_initial,
                start,
                fit,
                embargo,
                validation,
            ),
            "initial_state_fit_distance_from_evaluation_truth_scaled_l2": float(
                np.linalg.norm(
                    (fitted_initial - truth_initial)
                    / identifier.config.initial_state_prior_scale
                )
            ),
            "saved_raw_robot_pose_twist_available": False,
            "robot_target_for_audit": "evaluation-only sensor-equivalent kinematics reconstructed from plant Human/interface truth",
            "wrench_target_for_audit": "saved physical cuff wrench",
        }
        cached[case_name] = (
            identifier,
            evaluation_series,
            truth_state,
            truth_parameters,
            start,
            fit,
            embargo,
            validation,
        )
    return cases, cached


def _parameter_landscapes(cached: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for case_name, (parameter_index, values) in LANDSCAPES.items():
        (
            identifier,
            evaluation_series,
            truth_state,
            truth_parameters,
            start,
            fit,
            embargo,
            validation,
        ) = cached[case_name]
        truth_array = truth_parameters.as_array()
        rows = []
        for value in values:
            candidate_array = truth_array.copy()
            candidate_array[parameter_index] = value
            candidate = InterfaceParameterScales.from_array(candidate_array)
            fitted_initial = identifier.fit_initial_state_for_fixed_parameters(
                evaluation_series,
                start_index=start,
                fit_window_s=identifier.config.fit_window_s,
                parameters=candidate,
            )
            true_initial_result = _evaluate_parameters(
                identifier,
                evaluation_series,
                truth_state,
                candidate,
                truth_state[start],
                start,
                fit,
                embargo,
                validation,
            )
            fitted_initial_result = _evaluate_parameters(
                identifier,
                evaluation_series,
                truth_state,
                candidate,
                fitted_initial,
                start,
                fit,
                embargo,
                validation,
            )
            rows.append(
                {
                    "candidate_parameter_scales": candidate_array,
                    "varied_scale": value,
                    "true_initial_state_validation_normalized_rmse": true_initial_result[
                        "held_out_deployable_prediction"
                    ]["normalized_rmse"],
                    "fit_window_initial_state_validation_normalized_rmse": fitted_initial_result[
                        "held_out_deployable_prediction"
                    ]["normalized_rmse"],
                    "true_initial_state_force_rmse_n": true_initial_result[
                        "held_out_deployable_prediction"
                    ]["components"]["cuff_force"]["rmse"],
                    "fit_window_initial_state_force_rmse_n": fitted_initial_result[
                        "held_out_deployable_prediction"
                    ]["components"]["cuff_force"]["rmse"],
                }
            )
        direct = np.asarray(
            [item["true_initial_state_validation_normalized_rmse"] for item in rows]
        )
        refit = np.asarray(
            [item["fit_window_initial_state_validation_normalized_rmse"] for item in rows]
        )
        output[case_name] = {
            "varied_parameter": ("alpha_t", "alpha_r", "alpha_d")[parameter_index],
            "true_scale": float(truth_array[parameter_index]),
            "rows": rows,
            "minimum_with_true_initial_state": float(values[int(np.argmin(direct))]),
            "minimum_after_fit_window_initial_state_compensation": float(values[int(np.argmin(refit))]),
        }
    return output


def run(trace_root: Path, output_dir: Path) -> dict[str, Any]:
    nominal_series = InterfaceIdentificationSeries.from_saved_trace(
        trace_root / "nominal_1p0" / "trace.npz"
    )
    self_consistency = _self_consistency(nominal_series)
    model_form, cached = _plant_model_form_audit(trace_root)
    landscapes = _parameter_landscapes(cached)
    payload = {
        "schema": "stage5_interface_information_vs_model_form_v1",
        "evidence_category": "exploratory_offline_saved_trace_diagnostic",
        "new_mujoco_run_performed": False,
        "control_behavior_changed": False,
        "interface_adaptation_active": False,
        "truth_available_to_online_identifier": False,
        "self_consistency": self_consistency,
        "plant_vs_predictor": model_form,
        "counterfactual_parameter_landscapes": landscapes,
        "saved_evidence_limitations": [
            "Mismatch-v1 traces predate direct raw robot pose/twist logging.",
            "Robot pose/twist audit targets are reconstructed evaluation-only sensor equivalents from saved plant Human/interface truth.",
            "Interface velocity truth uses an offline finite derivative because MuJoCo interface velocity was not saved directly.",
            "Sparse OFAT traces and local grids do not establish a continuous identifiability or robustness guarantee.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "audit.json"
    output_path.write_text(
        json.dumps(_jsonable(payload), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.trace_root, args.output_dir)
    summary = {
        name: {
            "truth": item["true_parameter_scales_generator_only"],
            "fit": item["fitted_parameter_scales"],
            "error_l2": item["parameter_error_l2"],
            "validation_rmse": item["validation_normalized_rmse"],
        }
        for name, item in payload["self_consistency"]["cases"].items()
    }
    print(json.dumps(_jsonable(summary), indent=2))
    print(f"wrote {args.output_dir / 'audit.json'}")


if __name__ == "__main__":
    main()
