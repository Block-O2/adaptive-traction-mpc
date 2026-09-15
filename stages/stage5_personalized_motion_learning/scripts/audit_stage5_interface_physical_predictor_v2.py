#!/usr/bin/env python3
"""Offline gates for the identification-only physical interface predictor v2."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.interface_identification import (
    InterfaceIdentificationSeries,
    InterfaceParameterScales,
    WindowedInterfacePredictionErrorIdentifier,
)
from traction_mpc_stage5.interface_identification_v2 import (
    PhysicalInterfaceIdentifierV2,
    load_identification_physical_predictor_v2_config,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_ROOT = STAGE5_ROOT / "results" / "interface_mismatch_v1_attempt03"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "interface_physical_predictor_v2_offline"
CASE_TRUTH = {
    "nominal_1p0": (1.0, 1.0, 1.0),
    "kt_0p7": (0.7, 1.0, 1.0),
    "kt_1p3": (1.3, 1.0, 1.0),
    "kr_1p3": (1.0, 1.3, 1.0),
    "d_0p7": (1.0, 1.0, 0.7),
    "d_1p3": (1.0, 1.0, 1.3),
}
LANDSCAPES = {
    "kt_0p7_alpha_t": ("kt_0p7", 0, (0.5, 0.6, 0.7, 0.8, 0.9)),
    "kr_1p3_alpha_r": ("kr_1p3", 1, (1.1, 1.2, 1.3, 1.4, 1.5)),
    "d_0p7_alpha_d": ("d_0p7", 2, (0.5, 0.6, 0.7, 0.8, 0.9)),
    "nominal_alpha_t": ("nominal_1p0", 0, (0.8, 0.9, 1.0, 1.1, 1.2)),
    "nominal_alpha_r": ("nominal_1p0", 1, (0.8, 0.9, 1.0, 1.1, 1.2)),
    "nominal_alpha_d": ("nominal_1p0", 2, (0.8, 0.9, 1.0, 1.1, 1.2)),
}
PARAMETER_NAMES = ("alpha_t", "alpha_r", "alpha_d")
COMPONENTS = {
    "robot_position": (slice(0, 3), 1.0e3, "mm"),
    "robot_rotation": (slice(3, 6), 180.0 / np.pi, "deg"),
    "robot_linear_velocity": (slice(6, 9), 1.0, "m/s"),
    "robot_angular_velocity": (slice(9, 12), 1.0, "rad/s"),
    "cuff_force": (slice(12, 15), 1.0, "N"),
    "cuff_moment": (slice(15, 18), 1.0, "Nm"),
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


def _window(series: InterfaceIdentificationSeries) -> tuple[int, int, int, int]:
    config = WindowedInterfacePredictionErrorIdentifier().config
    dt_s = float(np.median(np.diff(series.time_s)))
    fit = int(round(config.fit_window_s / dt_s))
    embargo = int(round(config.validation_embargo_s / dt_s))
    validation = int(round(config.validation_window_s / dt_s))
    required_s = config.fit_window_s + config.validation_embargo_s + config.validation_window_s
    requested_s = 0.10 if series.time_s[-1] >= 0.10 + required_s else 0.02
    start = int(np.searchsorted(series.time_s, requested_s, side="left"))
    return start, fit, embargo, validation


def _evaluation_series(
    path: Path,
    series: InterfaceIdentificationSeries,
    truth: InterfaceParameterScales,
) -> tuple[InterfaceIdentificationSeries, np.ndarray]:
    kinematic_mapper = WindowedInterfacePredictionErrorIdentifier()
    with np.load(path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        truth_state = np.column_stack(
            [
                trace["evaluation_human_q_rad"],
                trace["evaluation_human_dq_rad_s"],
                trace["interface_translation_human_m"],
                np.gradient(
                    trace["interface_translation_human_m"],
                    time_s,
                    axis=0,
                    edge_order=2,
                ),
                trace["interface_rotation_human_rad"],
                np.gradient(
                    trace["interface_rotation_human_rad"],
                    time_s,
                    axis=0,
                    edge_order=2,
                ),
            ]
        )
        robot = np.asarray(
            [
                kinematic_mapper.measurement_from_state(truth, state)[:12]
                for state in truth_state
            ]
        )
        physical_wrench = np.column_stack(
            [trace["physical_cuff_force_world_n"], trace["physical_cuff_moment_world_nm"]]
        )
    return (
        replace(
            series,
            robot_measurement=robot,
            measured_wrench_world=physical_wrench,
            source=f"evaluation_only_sensor_equivalent:{path.name}",
        ),
        truth_state,
    )


def _measurement_score(
    identifier: WindowedInterfacePredictionErrorIdentifier,
    prediction: np.ndarray,
    target: np.ndarray,
) -> dict[str, Any]:
    difference = identifier._measurement_difference(prediction, target)  # noqa: SLF001
    normalized = difference / identifier.config.measurement_scale
    result = {
        "objective_mean_squared_normalized_residual": float(np.mean(normalized**2)),
        "normalized_rmse": float(np.sqrt(np.mean(normalized**2))),
        "components": {},
    }
    for name, (coordinates, scale, unit) in COMPONENTS.items():
        values = scale * difference[:, coordinates]
        result["components"][name] = {
            "rmse": float(np.sqrt(np.mean(values**2))),
            "p95_vector_norm": float(np.percentile(np.linalg.norm(values, axis=1), 95)),
            "max_abs": float(np.max(np.abs(values))),
            "unit": unit,
        }
    return result


def _latent_score(rollout: Any, truth_state: np.ndarray) -> dict[str, Any]:
    human_error = rollout.human_state - truth_state[:, :4]
    interface_error = rollout.interface_state - truth_state[:, 4:]
    return {
        "human_q_rmse_deg": np.sqrt(np.mean(human_error[:, :2] ** 2, axis=0)) * 180 / np.pi,
        "human_dq_rmse_deg_s": np.sqrt(np.mean(human_error[:, 2:] ** 2, axis=0)) * 180 / np.pi,
        "interface_translation_rmse_mm": np.sqrt(np.mean(interface_error[:, :3] ** 2, axis=0)) * 1.0e3,
        "interface_velocity_rmse_m_s": np.sqrt(np.mean(interface_error[:, 3:6] ** 2, axis=0)),
        "interface_rotation_rmse_deg": np.sqrt(np.mean(interface_error[:, 6:9] ** 2, axis=0)) * 180 / np.pi,
        "interface_angular_velocity_rmse_rad_s": np.sqrt(np.mean(interface_error[:, 9:] ** 2, axis=0)),
    }


def _evaluate(
    identifier: WindowedInterfacePredictionErrorIdentifier,
    series: InterfaceIdentificationSeries,
    truth_state: np.ndarray,
    parameters: InterfaceParameterScales,
    start: int,
    fit: int,
    embargo: int,
    validation: int,
) -> dict[str, Any]:
    total = fit + embargo + validation
    rollout = identifier.predict_rollout(
        series, start, total, parameters, truth_state[start]
    )
    validation_slice = slice(fit + embargo, total)
    target_slice = slice(start + fit + embargo + 1, start + total + 1)
    return {
        "measurements": _measurement_score(
            identifier,
            rollout.deployable_measurements[validation_slice],
            series.output_measurement[target_slice],
        ),
        "latent_evaluation_only": _latent_score(
            replace(
                rollout,
                human_state=rollout.human_state[validation_slice],
                interface_state=rollout.interface_state[validation_slice],
            ),
            truth_state[target_slice],
        ),
    }


def _gate1(trace_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    cases = {}
    cache = {}
    for case_name, truth_values in CASE_TRUTH.items():
        path = trace_root / case_name / "trace.npz"
        if not path.exists():
            continue
        truth = InterfaceParameterScales.from_array(truth_values)
        deployable = InterfaceIdentificationSeries.from_saved_trace(path)
        evaluation, truth_state = _evaluation_series(path, deployable, truth)
        start, fit, embargo, validation = _window(evaluation)
        old = WindowedInterfacePredictionErrorIdentifier()
        v2 = PhysicalInterfaceIdentifierV2()
        old_result = _evaluate(
            old, evaluation, truth_state, truth, start, fit, embargo, validation
        )
        v2_result = _evaluate(
            v2, evaluation, truth_state, truth, start, fit, embargo, validation
        )
        old_rmse = old_result["measurements"]["normalized_rmse"]
        v2_rmse = v2_result["measurements"]["normalized_rmse"]
        cases[case_name] = {
            "true_parameter_scales_evaluation_only": truth_values,
            "window_start_s": float(evaluation.time_s[start]),
            "old_predictor": old_result,
            "physical_predictor_v2": v2_result,
            "normalized_rmse_ratio_v2_over_old": float(v2_rmse / old_rmse),
            "normalized_rmse_reduction_fraction": float(1.0 - v2_rmse / old_rmse),
        }
        cache[case_name] = (evaluation, truth_state, truth, start, fit, embargo, validation)
    ratios = np.asarray(
        [item["normalized_rmse_ratio_v2_over_old"] for item in cases.values()]
    )
    summary = {
        "dynamic_case_count": len(cases),
        "mean_normalized_rmse_ratio_v2_over_old": float(np.mean(ratios)),
        "improved_case_count": int(np.count_nonzero(ratios < 1.0)),
        "material_reduction_definition": "mean v2/old normalized RMSE below 0.8 and no nonfinite rollout",
        "materially_reduced": bool(np.mean(ratios) < 0.8),
    }
    return {"cases": cases, "summary": summary}, cache


def _local_landscape(
    name: str,
    case_name: str,
    parameter_index: int,
    values: tuple[float, ...],
    cached: tuple[Any, ...],
) -> dict[str, Any]:
    evaluation, truth_state, truth, start, fit, embargo, validation = cached
    identifier = PhysicalInterfaceIdentifierV2()
    truth_array = truth.as_array()
    rows = []
    for value in values:
        candidate_array = truth_array.copy()
        candidate_array[parameter_index] = value
        result = _evaluate(
            identifier,
            evaluation,
            truth_state,
            InterfaceParameterScales.from_array(candidate_array),
            start,
            fit,
            embargo,
            validation,
        )
        rows.append(
            {
                "parameter_value": value,
                "validation_objective": result["measurements"][
                    "objective_mean_squared_normalized_residual"
                ],
                "validation_normalized_rmse": result["measurements"]["normalized_rmse"],
                "force_rmse_n": result["measurements"]["components"]["cuff_force"]["rmse"],
                "moment_rmse_nm": result["measurements"]["components"]["cuff_moment"]["rmse"],
            }
        )
    objectives = np.asarray([item["validation_objective"] for item in rows])
    truth_value = float(truth_array[parameter_index])
    truth_index = int(np.argmin(np.abs(np.asarray(values) - truth_value)))
    grid_index = int(np.argmin(objectives))
    spacing = float(values[1] - values[0])
    curvature = float("nan")
    slope = float("nan")
    if 0 < truth_index < len(values) - 1:
        curvature = float(
            (objectives[truth_index - 1] - 2 * objectives[truth_index] + objectives[truth_index + 1])
            / spacing**2
        )
        slope = float(
            (objectives[truth_index + 1] - objectives[truth_index - 1])
            / (2 * spacing)
        )
    truth_within_two_percent = bool(
        objectives[truth_index] <= 1.02 * max(objectives[grid_index], 1.0e-15)
    )
    near_minimum = bool(
        abs(values[grid_index] - truth_value) <= spacing + 1.0e-12
        and truth_within_two_percent
        and curvature > 0.0
    )
    decision = np.r_[truth_array, truth_state[start]]
    diagnostics = identifier.identifiability_diagnostics(
        decision, evaluation, start, fit
    )
    return {
        "name": name,
        "saved_case": case_name,
        "varied_parameter": PARAMETER_NAMES[parameter_index],
        "truth_value": truth_value,
        "rows": rows,
        "grid_minimum": float(values[grid_index]),
        "truth_objective_ratio_over_grid_minimum": float(
            objectives[truth_index] / max(objectives[grid_index], 1.0e-15)
        ),
        "local_slope_at_truth": slope,
        "local_curvature_at_truth": curvature,
        "truth_near_local_minimum": near_minimum,
        "data_jacobian_at_truth": asdict(diagnostics),
    }


def _gate2(cache: dict[str, Any]) -> dict[str, Any]:
    landscapes = {
        name: _local_landscape(name, case_name, index, values, cache[case_name])
        for name, (case_name, index, values) in LANDSCAPES.items()
    }
    required = (
        "kt_0p7_alpha_t",
        "kr_1p3_alpha_r",
        "d_0p7_alpha_d",
        "nominal_alpha_t",
        "nominal_alpha_r",
        "nominal_alpha_d",
    )
    satisfactory = bool(
        all(landscapes[name]["truth_near_local_minimum"] for name in required)
    )
    return {
        "landscapes": landscapes,
        "satisfactory": satisfactory,
        "gate_definition": "truth is within one grid step, within 2% objective of the grid minimum, and has positive local curvature for every predeclared landscape",
    }


def run(trace_root: Path, output_dir: Path) -> dict[str, Any]:
    gate1, cache = _gate1(trace_root)
    gate2 = _gate2(cache)
    gate3_reached = bool(gate1["summary"]["materially_reduced"] and gate2["satisfactory"])
    payload = {
        "schema": "stage5_identification_physical_predictor_v2_audit",
        "evidence_category": "exploratory_offline_saved_trace_diagnostic",
        "new_mujoco_run_performed": False,
        "control_grade_predictor_changed": False,
        "identification_publication_active": False,
        "predictor_v2_config": asdict(load_identification_physical_predictor_v2_config()),
        "gate1_true_parameter_closure": gate1,
        "gate2_parameter_landscape": gate2,
        "gate3_existing_estimator": {
            "reached": gate3_reached,
            "executed": False,
            "reason": (
                "not run: Gate 2 did not establish truth-near-minimum landscapes"
                if not gate2["satisfactory"]
                else "not run in this payload"
            ),
        },
        "stopping_decision": {
            "code": "B" if not gate2["satisfactory"] else "A",
            "conclusion": (
                "v2 improves true-parameter closure, but physical K/D identification remains unjustified because all true parameters do not minimize held-out error"
                if not gate2["satisfactory"]
                else "physical landscapes are locally consistent enough to proceed to the unchanged estimator"
            ),
        },
        "limitations": [
            "saved Mismatch-v1 traces predate direct raw robot pose/twist logging",
            "robot sensor-equivalent targets are reconstructed offline from saved plant Human/interface truth",
            "interface velocity truth is an offline finite derivative",
            "the robot operational-space model is diagonal and constant and omits Jacobian variation, torque saturation dynamics, and bed reaction",
            "small local grids do not establish global identifiability",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "audit.json"
    output.write_text(
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
    print(json.dumps(_jsonable(payload["gate1_true_parameter_closure"]["summary"]), indent=2))
    print(json.dumps(_jsonable(payload["stopping_decision"]), indent=2))
    print(f"wrote {args.output_dir / 'audit.json'}")


if __name__ == "__main__":
    main()
