#!/usr/bin/env python3
"""Offline saved-trace audit for Stage-5 Interface Identification v1.

This is an exploratory architecture/identifiability diagnostic.  It does not
run MuJoCo, change controller configuration, or publish parameters to control.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage5.interface_identification import (
    InactiveInterfaceIdentificationTrust,
    InterfaceIdentificationSeries,
    InterfaceParameterScales,
    WindowedInterfacePredictionErrorIdentifier,
    load_interface_identification_config,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_ROOT = STAGE5_ROOT / "results" / "interface_mismatch_v1_attempt03"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "interface_identification_v1_offline"
CASE_TRUTH = {
    "nominal_1p0": [1.0, 1.0, 1.0],
    "kt_0p7": [0.7, 1.0, 1.0],
    "kt_1p3": [1.3, 1.0, 1.0],
    "kr_0p7": [1.0, 0.7, 1.0],
    "kr_1p3": [1.0, 1.3, 1.0],
    "d_0p7": [1.0, 1.0, 0.7],
    "d_1p3": [1.0, 1.0, 1.3],
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


def _diag_record(diagnostics: Any) -> dict[str, Any]:
    return _jsonable(asdict(diagnostics))


def _fit_record(result: Any, true_parameters: np.ndarray, runtime_s: float) -> dict[str, Any]:
    fitted = result.parameter_scales.as_array()
    multistart_parameters = np.asarray(
        [item["fitted_parameter_scales"] for item in result.multistart_solutions],
        dtype=float,
    )
    multistart_fit = np.asarray(
        [item["fit_normalized_rmse"] for item in result.multistart_solutions],
        dtype=float,
    )
    multistart_validation = np.asarray(
        [item["validation_normalized_rmse"] for item in result.multistart_solutions],
        dtype=float,
    )
    return {
        "true_parameter_scales_evaluation_only": true_parameters.tolist(),
        "fitted_parameter_scales": fitted.tolist(),
        "absolute_parameter_error_evaluation_only": np.abs(fitted - true_parameters).tolist(),
        "parameter_error_l2_evaluation_only": float(np.linalg.norm(fitted - true_parameters)),
        "fit_normalized_rmse": result.fit_normalized_rmse,
        "validation_normalized_rmse": result.validation_normalized_rmse,
        "nominal_validation_normalized_rmse": result.nominal_validation_normalized_rmse,
        "validation_relative_improvement": result.validation_relative_improvement,
        "validation_component_normalized_rmse": dict(result.validation_component_normalized_rmse),
        "nominal_validation_component_normalized_rmse": dict(
            result.nominal_validation_component_normalized_rmse
        ),
        "fit_start_time_s": result.fit_start_time_s,
        "fit_end_time_s": result.fit_end_time_s,
        "validation_start_time_s": result.validation_start_time_s,
        "validation_end_time_s": result.validation_end_time_s,
        "validation_sample_count": result.validation_sample_count,
        "optimizer_success": result.success,
        "optimizer_reason": result.reason,
        "optimizer_nfev": result.optimizer_nfev,
        "optimizer_runtime_s": runtime_s,
        "parameter_bound_hit": result.bound_hit,
        "last_valid_fallback_used": result.last_valid_fallback_used,
        "identifiability": _diag_record(result.identifiability),
        "multistart": _jsonable(result.multistart_solutions),
        "multistart_parameter_span": (
            np.ptp(multistart_parameters, axis=0).tolist()
            if len(multistart_parameters)
            else [float("nan")] * 3
        ),
        "multistart_fit_rmse_span": float(np.ptp(multistart_fit)) if len(multistart_fit) else float("nan"),
        "multistart_validation_rmse_span": (
            float(np.ptp(multistart_validation))
            if len(multistart_validation)
            else float("nan")
        ),
    }


def _start_index(series: InterfaceIdentificationSeries, requested_s: float) -> int:
    return int(np.searchsorted(series.time_s, requested_s, side="left"))


def _phase_audit(
    series: InterfaceIdentificationSeries,
    identifier: WindowedInterfacePredictionErrorIdentifier,
) -> dict[str, Any]:
    result = {}
    for phase in ("OUTBOUND", "HOLD", "RETURN"):
        indices = np.flatnonzero(series.phase == phase)
        if len(indices) < 12:
            result[phase] = {"available": False, "sample_count": int(len(indices))}
            continue
        start = int(indices[min(5, len(indices) - 2)])
        available = int(indices[-1] - start)
        steps = min(20, available)
        if steps < 10:
            result[phase] = {"available": False, "sample_count": int(len(indices))}
            continue
        decision = np.r_[
            np.ones(3),
            series.arrival_human_state[start],
            series.arrival_interface_state[start],
        ]
        diagnostics = identifier.identifiability_diagnostics(
            decision, series, start, steps
        )
        record = _diag_record(diagnostics)
        record.update(
            {
                "available": True,
                "window_start_s": float(series.time_s[start]),
                "window_end_s": float(series.time_s[start + steps]),
                "information_energy": float(
                    np.sum(np.asarray(diagnostics.singular_values) ** 2)
                ),
            }
        )
        result[phase] = record
    return result


def _window_and_latent_audit(
    series: InterfaceIdentificationSeries,
    identifier: WindowedInterfacePredictionErrorIdentifier,
) -> list[dict[str, Any]]:
    config = identifier.config
    dt = float(np.median(np.diff(series.time_s)))
    start = _start_index(series, 0.10)
    base_state = np.r_[
        series.arrival_human_state[start], series.arrival_interface_state[start]
    ]
    rows = []
    for window_s in config.window_length_audit_s:
        steps = int(round(window_s / dt))
        if start + steps >= len(series.time_s):
            continue
        for offset_name, offset in zip(
            ("nominal_arrival", "positive_arrival_perturbation", "negative_arrival_perturbation"),
            config.multistart_initial_state_offsets_in_prior_scales,
            strict=True,
        ):
            state = base_state + np.asarray(offset) * config.initial_state_prior_scale
            diagnostics = identifier.identifiability_diagnostics(
                np.r_[np.ones(3), state], series, start, steps
            )
            rows.append(
                {
                    "window_s": window_s,
                    "initial_latent_case": offset_name,
                    **_diag_record(diagnostics),
                }
            )
    return rows


def run(trace_root: Path, output_dir: Path) -> dict[str, Any]:
    config = load_interface_identification_config()
    cases = {}
    phase_information = {}
    for case_name, truth in CASE_TRUTH.items():
        trace_path = trace_root / case_name / "trace.npz"
        if not trace_path.exists():
            startup_path = trace_root / case_name / "startup_abort.json"
            startup = json.loads(startup_path.read_text()) if startup_path.exists() else None
            cases[case_name] = {
                "dynamic_trace_available": False,
                "true_parameter_scales_evaluation_only": truth,
                "startup_abort": startup,
                "identification_interpretation": "no_dynamic_window_settled_start_reconstruction_failure",
            }
            phase_information[case_name] = {}
            continue
        series = InterfaceIdentificationSeries.from_saved_trace(trace_path)
        with np.load(trace_path, allow_pickle=False) as evaluation_trace:
            evaluation_wrench = np.column_stack(
                [
                    evaluation_trace["physical_cuff_force_world_n"],
                    evaluation_trace["physical_cuff_moment_world_nm"],
                ]
            )
        legacy_wrench_proxy_closure = float(
            np.max(np.abs(series.measured_wrench_world - evaluation_wrench))
        )
        identifier = WindowedInterfacePredictionErrorIdentifier(config)
        total_required = config.fit_window_s + config.validation_embargo_s + config.validation_window_s
        requested_start = 0.10
        if series.time_s[-1] < requested_start + total_required:
            requested_start = 0.02
        start = _start_index(series, requested_start)
        started = perf_counter()
        fit = identifier.fit(series, start_index=start, multistart=True)
        runtime_s = perf_counter() - started
        trust = InactiveInterfaceIdentificationTrust(config)
        trust.propose(fit)
        trust_decision = trust.resolve(decision_timestamp_s=fit.validation_end_time_s)
        cases[case_name] = {
            "dynamic_trace_available": True,
            "available_trace_duration_s": float(series.time_s[-1] - series.time_s[0]),
            "legacy_robot_measurement_reconstruction": series.legacy_measurement_reconstruction,
            "measurement_reconstruction_closure_max_abs": series.reconstruction_closure_max_abs,
            "legacy_wrench_proxy_vs_evaluation_truth_max_abs": legacy_wrench_proxy_closure,
            **_fit_record(fit, np.asarray(truth), runtime_s),
            "inactive_trust_decision": _jsonable(asdict(trust_decision)),
        }
        phase_information[case_name] = _phase_audit(series, identifier)

    window_length_and_latent = {}
    for case_name in ("nominal_1p0", "kt_0p7"):
        series = InterfaceIdentificationSeries.from_saved_trace(
            trace_root / case_name / "trace.npz"
        )
        window_length_and_latent[case_name] = _window_and_latent_audit(
            series, WindowedInterfacePredictionErrorIdentifier(config)
        )

    fitted_cases = [item for item in cases.values() if item["dynamic_trace_available"]]
    improved = int(sum(item["validation_relative_improvement"] > 0.0 for item in fitted_cases))
    trust_qualified = int(sum(
        item["inactive_trust_decision"]["status"]
        == "qualified_and_published_to_shadow_only"
        for item in fitted_cases
    ))
    bound_hits = int(sum(item["parameter_bound_hit"] for item in fitted_cases))
    multistart_unstable = int(sum(
        np.max(item["multistart_parameter_span"]) > 0.10
        and item["multistart_validation_rmse_span"] < 0.10
        for item in fitted_cases
    ))
    payload = {
        "schema": "stage5_interface_identification_v1_offline_audit",
        "evidence_category": "exploratory_saved_trace_architecture_and_identifiability_probe",
        "control_adaptation_active": False,
        "mujoco_truth_used_by_identifier": False,
        "truth_scales_used_for_post_fit_evaluation_only": True,
        "trace_root": str(trace_root),
        "configuration": _jsonable(asdict(config)),
        "infrastructure_audit": {
            "stage1_windowed_ls_nls": {
                "classification": "pattern_only",
                "reuse": ["bounded least_squares", "warm_start", "prior", "local residual diagnostics"],
                "not_reused": "one-step observed-state regressors because candidate-dependent interface inversion would be EIV/self-consistent",
            },
            "stage1_joint_state_parameter_mhe": {
                "classification": "pattern_only_and_selected_prototype_structure",
                "reuse": "jointly optimize only the window-initial Human/interface nuisance state and static parameters; exact single-shooting propagation",
                "not_reused": "Spring2D equations, thresholds, or its mass parameterization",
            },
            "stage4_integral_identifier": {
                "classification": "diagnostic_pattern_only",
                "reuse": ["data-only SVD/rank/condition", "correlation", "bound pressure", "last-valid fallback"],
                "not_reused": "Human inverse-dynamics integral regression because the cuff predictor is nonlinear and measurement-latent coupled",
            },
            "stage4_incumbent_challenger_trust": {
                "classification": "lifecycle_pattern_directly_reused_in_inactive_shell",
                "reuse": ["one challenger", "future embargo", "retained incumbent", "reject fallback", "bounded smoothed versioned shadow publication"],
                "not_reused": "Human-ID loss units, thresholds, HAC schedule, or control promotion",
            },
        },
        "cases": cases,
        "phase_information": phase_information,
        "window_length_and_initial_latent_state": window_length_and_latent,
        "aggregate": {
            "dynamic_case_count": len(fitted_cases),
            "held_out_improvement_count": improved,
            "inactive_trust_qualification_count": trust_qualified,
            "parameter_bound_hit_count": bound_hits,
            "multistart_material_parameter_nonuniqueness_count": multistart_unstable,
        },
        "architectural_decision": {
            "code": "C",
            "conclusion": "current task data do not support stable physical identification of all proposed interface scales",
            "reason": "future-measurement fit may improve in some windows, but truth-scale recovery, cross-case physical direction, and phase/window stability are insufficient for shadow-online parameter publication",
            "next_step": "reduce/reparameterize after a predeclared targeted non-task excitation and/or revise direct robot pose/twist logging; do not activate interface updates",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit.json").write_text(
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
    print(json.dumps(payload["aggregate"], indent=2))
    print(json.dumps(payload["architectural_decision"], indent=2))
    print(f"wrote {args.output_dir / 'audit.json'}")


if __name__ == "__main__":
    main()
