"""Professor-report generalization orchestration and offline metrics.

This module reuses the frozen report-validation controller/plant execution path.
Formal phases remain user-executed; the built-in smoke is duration-capped and
explicitly non-scientific.
"""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.signal import savgol_filter

from traction_mpc_stage3.human import HUMAN

from .artifact_paths import resolve_stage_artifact
from .estimator_v2 import nominal_base_parameters
from .report_validation import (
    canonical_json_sha256,
    controller_fingerprint_payload,
    load_gain_lock,
    load_report_validation_matrix,
    patient_spec_for_id,
    prepare_fresh_output_directory,
    report_root,
    run_report_arm,
    sha256_file,
    strict_json,
    write_strict_json,
)


GENERALIZATION_SCHEMA_VERSION = (
    "stage4_report_generalization_matrix_v1_demo_reuse_amendment"
)
GENERALIZATION_DESIGN_STATUS = (
    "approved_prospective_demo_reuse_amendment_no_formal_execution"
)
GENERALIZATION_SMOKE_MAX_DURATION_S = 0.5
STATISTICAL_EVIDENCE_CATEGORY = "report_generalization_statistical"
TRAJECTORY_DEMO_EVIDENCE_CATEGORY = "report_trajectory_demo_only"
SMOKE_EVIDENCE_CATEGORY = (
    "report_generalization_structural_smoke_non_scientific"
)
VISUALIZATION_EVIDENCE_CATEGORY = "professor_report_visualization"


def load_generalization_matrix(path: Path) -> dict[str, Any]:
    target = Path(path).resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_version") != GENERALIZATION_SCHEMA_VERSION:
        raise ValueError("unsupported report-generalization matrix schema")
    if payload.get("design_status") != GENERALIZATION_DESIGN_STATUS:
        raise ValueError("report-generalization matrix is not the amended design")
    if payload.get("preregistered_before_any_new_generalization_result") is not True:
        raise ValueError("generalization design is not prospective")
    root = report_root(target)
    for name, source in payload["source_artifacts"].items():
        source_path = resolve_stage_artifact(root, source["path"])
        if not source_path.is_file():
            raise FileNotFoundError(
                f"missing generalization source artifact {name}: {source_path}"
            )
        expected = source.get("sha256")
        if expected is not None and sha256_file(source_path) != expected:
            raise ValueError(f"generalization source hash mismatch for {name}")

    patients = [item["patient_id"] for item in payload["patients"]]
    controllers = [item["controller_id"] for item in payload["controllers"]]
    seeds = [int(value) for value in payload["shared_contract"]["measurement_seeds"]]
    arms = payload["main_statistical_matrix"]["arms"]
    observed = {
        (item["patient_id"], item["controller_id"], int(item["measurement_seed"]))
        for item in arms
    }
    expected = {
        (patient, controller, seed)
        for patient in patients
        for controller in controllers
        for seed in seeds
    }
    if observed != expected or len(arms) != len(observed) or len(arms) != 36:
        raise ValueError("generalization statistical matrix is not exact 4x3x3")
    if "pd_feedback" in controllers:
        raise ValueError("pure PD cannot enter the main generalization matrix")
    new_demo = payload["trajectory_demo_matrix"]["new_execution_arms"]
    if len(new_demo) != 6 or any(
        item["trajectory_id"] == "registered_high_flexion_23s"
        for item in new_demo
    ):
        raise ValueError("trajectory demo execution set is not the amended six arms")
    if int(payload["cost_estimate"]["total_new_rollouts"]) != 42:
        raise ValueError("generalization unique execution count is not 42")

    validation_source = payload["source_artifacts"]["report_validation_v2_config"]
    validation_path = resolve_stage_artifact(root, validation_source["path"])
    validation = load_report_validation_matrix(validation_path)
    generalization_geometry = next(
        item
        for item in payload["patients"]
        if item["patient_id"] == "height_moderate_plus_03pct_report_only"
    )["definition"]
    validation_geometry = next(
        item
        for item in validation["patient_cases"]["report_only"]
        if item["case_id"] == "height_moderate_plus_03pct_report_only"
    )
    for key, value in generalization_geometry.items():
        if validation_geometry.get(key) != value:
            raise ValueError(
                f"report-only geometry definition differs from validated path at {key}"
            )
    return payload


def load_metric_definitions(
    matrix: dict[str, Any], matrix_path: Path
) -> tuple[dict[str, Any], Path, str]:
    source = matrix["source_artifacts"]["metric_schema"]
    path = resolve_stage_artifact(report_root(matrix_path), source["path"])
    actual = sha256_file(path)
    if actual != source["sha256"]:
        raise ValueError("generalization metric-definition hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "stage4_report_generalization_metrics_v1":
        raise ValueError("unsupported generalization metric schema")
    return payload, path, actual


def _rms(values: np.ndarray, *, axis: int | None = None) -> np.ndarray | float:
    result = np.sqrt(np.mean(np.square(np.asarray(values, dtype=float)), axis=axis))
    if np.ndim(result) == 0:
        return float(result)
    return result


def _motion_descriptors(
    trace: dict[str, np.ndarray], definitions: dict[str, Any]
) -> dict[str, Any]:
    contract = definitions["motion_quality"]
    method = contract["offline_derivative_method"]
    raw_time = np.asarray(trace["control_time_s"], dtype=float)
    raw_state = np.asarray(trace["control_estimated_state"], dtype=float)
    if raw_time.ndim != 1 or raw_state.shape != (len(raw_time), 4):
        raise ValueError("saved control state has an unexpected shape")
    if len(raw_time) < 1 + int(method["window_length_samples"]) * int(
        contract["subsample_stride"]
    ):
        raise ValueError("trace is too short for the frozen 50 Hz metric window")
    raw_step = np.diff(raw_time)
    if not np.allclose(
        raw_step,
        float(contract["saved_source_period_s"]),
        rtol=0.0,
        atol=float(contract["uniform_period_tolerance_s"]),
    ):
        raise ValueError("saved measured-state series is not uniformly 200 Hz")
    stride = int(contract["subsample_stride"])
    phase = int(contract["subsample_phase_index"])
    selected_time = raw_time[phase::stride]
    velocity = raw_state[phase::stride, 2:4]
    if not np.allclose(
        np.diff(selected_time),
        float(contract["required_uniform_period_s"]),
        rtol=0.0,
        atol=float(contract["uniform_period_tolerance_s"]),
    ):
        raise ValueError("frozen velocity series is not exactly 50 Hz")
    kwargs = {
        "window_length": int(method["window_length_samples"]),
        "polyorder": int(method["polynomial_order"]),
        "delta": float(method["delta_s"]),
        "axis": 0,
        "mode": str(method["boundary_mode"]),
    }
    acceleration = savgol_filter(
        velocity, deriv=int(method["acceleration_derivative_order"]), **kwargs
    )
    jerk = savgol_filter(
        velocity, deriv=int(method["jerk_derivative_order"]), **kwargs
    )
    if not np.all(np.isfinite(acceleration)) or not np.all(np.isfinite(jerk)):
        raise ValueError("motion descriptors are non-finite")
    return {
        "motion_descriptor_sample_count": int(len(selected_time)),
        "motion_descriptor_sample_period_s": float(
            contract["required_uniform_period_s"]
        ),
        "motion_descriptor_source_indices": "0::4",
        "hip_acceleration_rms_rad_s2": _rms(acceleration[:, 0]),
        "hip_acceleration_peak_rad_s2": float(np.max(np.abs(acceleration[:, 0]))),
        "knee_acceleration_rms_rad_s2": _rms(acceleration[:, 1]),
        "knee_acceleration_peak_rad_s2": float(np.max(np.abs(acceleration[:, 1]))),
        "combined_acceleration_rms_rad_s2": float(
            np.sqrt(np.mean(np.sum(np.square(acceleration), axis=1)))
        ),
        "hip_jerk_rms_rad_s3": _rms(jerk[:, 0]),
        "hip_jerk_peak_rad_s3": float(np.max(np.abs(jerk[:, 0]))),
        "knee_jerk_rms_rad_s3": _rms(jerk[:, 1]),
        "knee_jerk_peak_rad_s3": float(np.max(np.abs(jerk[:, 1]))),
        "combined_jerk_rms_rad_s3": float(
            np.sqrt(np.mean(np.sum(np.square(jerk), axis=1)))
        ),
    }


def extract_generalization_metrics(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    definitions: dict[str, Any],
) -> dict[str, Any]:
    """Extract the preregistered deterministic offline metric record."""

    motion = _motion_descriptors(trace, definitions)
    force = np.linalg.norm(
        np.asarray(trace["cuff_force_local_n_god_view"], dtype=float), axis=1
    )
    moment = np.linalg.norm(
        np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float), axis=1
    )
    robot_torque = np.asarray(trace["robot_torque_nm"], dtype=float)
    if robot_torque.ndim != 2 or robot_torque.shape[1] != 6:
        raise ValueError("robot torque trace must contain six joints")
    if not all(
        np.all(np.isfinite(value)) for value in (force, moment, robot_torque)
    ):
        raise ValueError("interaction descriptor input is non-finite")
    validation_metrics = summary["report_validation_metrics"]
    trajectory_duration = float(
        summary["reference_execution"]["config"]["trajectory_duration_s"]
    )
    promotions = summary["hierarchical_trust"]["control_promotions"]
    first_promotion = (
        min(float(item["promotion_time_s"]) for item in promotions)
        if promotions
        else None
    )
    remaining_percent = None
    if first_promotion is not None:
        phase_at_promotion = float(
            np.interp(
                first_promotion,
                np.asarray(trace["time_s"], dtype=float),
                np.asarray(trace["reference_phase_time_s"], dtype=float),
            )
        )
        remaining_percent = 100.0 * max(
            trajectory_duration - phase_at_promotion, 0.0
        ) / trajectory_duration
    prediction = summary.get("dynamic_identifier", {}).get(
        "god_view_base_model_torque_prediction_combined_rmse_nm"
    )
    prediction = (
        float(prediction)
        if isinstance(prediction, (int, float)) and math.isfinite(float(prediction))
        else None
    )
    metrics = {
        "schema_version": "stage4_report_generalization_arm_metrics_v1",
        "scientific_interpretation_from_structural_smoke_permitted": False,
        "motion_quality_interpretation": (
            "offline_motion_smoothness_descriptors_not_comfort_or_safety_truth"
        ),
        "interaction_interpretation": (
            "engineering_interaction_not_pressure_tissue_or_clinical_safety"
        ),
        "tracking_rmse_deg": float(validation_metrics["tracking_combined_rmse_deg"]),
        "tracking_max_error_deg": float(
            validation_metrics["tracking_max_abs_error_deg"]
        ),
        "completion": bool(summary["mechanically_completed_requested_duration"]),
        "termination_reason": str(summary["termination_reason"]),
        "reference_progress_fraction": float(
            validation_metrics["reference_progress_fraction"]
        ),
        **motion,
        "cuff_force_rms_n": _rms(force),
        "cuff_force_peak_n": float(np.max(force)),
        "cuff_force_p95_n": float(np.quantile(force, 0.95, method="linear")),
        "minimum_force_gate_margin_n": 200.0 - float(np.max(force)),
        "cuff_moment_rms_nm": _rms(moment),
        "cuff_moment_peak_nm": float(np.max(moment)),
        "robot_joint_torque_rms_nm": _rms(robot_torque, axis=0).tolist(),
        "robot_joint_torque_peak_abs_nm": np.max(
            np.abs(robot_torque), axis=0
        ).tolist(),
        "robot_torque_global_vector_rms_nm": float(
            np.sqrt(np.mean(np.sum(np.square(robot_torque), axis=1)))
        ),
        "robot_torque_global_peak_abs_nm": float(np.max(np.abs(robot_torque))),
        "safety_and_constraint_events": strict_json(summary["events"]),
        "adaptive_promotion_count": int(len(promotions)),
        "adaptive_first_promotion_wall_time_s": first_promotion,
        "adaptive_remaining_trajectory_percent_at_first_promotion": (
            remaining_percent
        ),
        "god_view_prediction_rmse_nm": prediction,
        "cuff_force_rate_included": False,
        "cuff_surface_proxy_primary_metric": False,
    }
    numeric = [
        value
        for value in metrics.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not all(math.isfinite(float(value)) for value in numeric):
        raise ValueError("generalization metric record contains non-finite values")
    return metrics


def descriptive_summary(values: Iterable[float]) -> dict[str, float | int]:
    array = np.asarray(tuple(float(value) for value in values), dtype=float)
    if array.ndim != 1 or len(array) == 0 or not np.all(np.isfinite(array)):
        raise ValueError("descriptive summary requires finite scalar values")
    return {
        "count": int(len(array)),
        "mean": float(np.mean(array)),
        "sample_sd_ddof_1": float(np.std(array, ddof=1)) if len(array) >= 2 else 0.0,
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


def matched_nominal_degradation(
    records: Iterable[dict[str, Any]], *, metric_names: Iterable[str]
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in records]
    nominal = {
        (item["controller_id"], int(item["measurement_seed"])): item
        for item in rows
        if item["patient_id"] == "nominal_reference"
    }
    output: list[dict[str, Any]] = []
    for item in rows:
        key = (item["controller_id"], int(item["measurement_seed"]))
        if key not in nominal:
            raise ValueError(f"missing matched nominal arm for {key}")
        reference = nominal[key]
        metrics: dict[str, Any] = {}
        for name in metric_names:
            value = float(item["metrics"][name])
            base = float(reference["metrics"][name])
            delta = value - base
            metrics[name] = {
                "absolute_delta": delta,
                "relative_degradation": (
                    delta / base if math.isfinite(base) and abs(base) >= 1e-12 else None
                ),
            }
        output.append(
            {
                "patient_id": item["patient_id"],
                "controller_id": item["controller_id"],
                "measurement_seed": int(item["measurement_seed"]),
                "nominal_patient_id": "nominal_reference",
                "metrics": metrics,
            }
        )
    return output


def build_generalization_summary(
    records: Iterable[dict[str, Any]], definitions: dict[str, Any]
) -> dict[str, Any]:
    rows = [dict(item) for item in records]
    required_metrics = tuple(definitions["generalization"]["required_metrics"])
    degradation = matched_nominal_degradation(rows, metric_names=required_metrics)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        grouped[(item["patient_id"], item["controller_id"])].append(item)
    cells = []
    for (patient, controller), items in sorted(grouped.items()):
        cells.append(
            {
                "patient_id": patient,
                "controller_id": controller,
                "seed_count": len(items),
                "metrics": {
                    name: descriptive_summary(item["metrics"][name] for item in items)
                    for name in required_metrics
                },
            }
        )
    by_factor = {
        (item["patient_id"], int(item["measurement_seed"]), item["controller_id"]): item
        for item in rows
    }
    comparisons = []
    patients = sorted({item["patient_id"] for item in rows})
    seeds = sorted({int(item["measurement_seed"]) for item in rows})
    for patient in patients:
        for seed in seeds:
            pdff = by_factor[(patient, seed, "pd_nominal_inverse_dynamics_ff")]
            fixed = by_factor[(patient, seed, "fixed_mpc_prior_only")]
            adaptive = by_factor[(patient, seed, "trusted_adaptive_mpc")]
            comparisons.append(
                {
                    "patient_id": patient,
                    "measurement_seed": seed,
                    "pdff_vs_fixed_right_minus_left": {
                        name: float(fixed["metrics"][name])
                        - float(pdff["metrics"][name])
                        for name in required_metrics
                    },
                    "fixed_vs_adaptive_right_minus_left": {
                        name: float(adaptive["metrics"][name])
                        - float(fixed["metrics"][name])
                        for name in required_metrics
                    },
                    "adaptive_benefit_fixed_minus_adaptive": {
                        name: float(fixed["metrics"][name])
                        - float(adaptive["metrics"][name])
                        for name in required_metrics
                    },
                }
            )
    return {
        "schema_version": "stage4_report_generalization_summary_v1",
        "descriptive_only_n_equals_3": True,
        "significance_tests_performed": False,
        "composite_score_created": False,
        "absolute_cell_summaries": cells,
        "matched_nominal_relative_degradation": degradation,
        "matched_controller_comparisons": comparisons,
    }


def _validation_context(
    matrix: dict[str, Any], matrix_path: Path, gain_lock_path: Path
) -> tuple[dict[str, Any], Path, dict[str, Any], str, dict[str, Any], str]:
    root = report_root(matrix_path)
    validation_source = matrix["source_artifacts"]["report_validation_v2_config"]
    validation_path = resolve_stage_artifact(root, validation_source["path"])
    validation = load_report_validation_matrix(validation_path)
    configured_lock = matrix["source_artifacts"]["frozen_v2_gain_lock"]
    supplied_lock = Path(gain_lock_path).resolve()
    expected_lock = resolve_stage_artifact(root, configured_lock["path"])
    if supplied_lock != expected_lock or sha256_file(supplied_lock) != configured_lock["sha256"]:
        raise ValueError("supplied gain lock is not the frozen generalization lock")
    lock, lock_hash = load_gain_lock(supplied_lock, required_kind="formal")
    if lock["report_validation_config_sha256"] != sha256_file(validation_path):
        raise ValueError("frozen gain lock does not belong to validation v2 config")
    definitions, _, metric_hash = load_metric_definitions(matrix, matrix_path)
    return validation, validation_path, lock, lock_hash, definitions, metric_hash


def _run_arm(
    *,
    generalization_matrix: dict[str, Any],
    generalization_matrix_path: Path,
    validation_matrix: dict[str, Any],
    validation_matrix_path: Path,
    gain_lock: dict[str, Any],
    gain_lock_sha256: str,
    metric_definitions: dict[str, Any],
    metric_config_sha256: str,
    patient_id: str,
    controller_id: str,
    trajectory_id: str,
    measurement_seed: int,
    evidence_category: str,
    formal_execution: bool,
    duration_s: float,
    output_dir: Path,
) -> dict[str, Any]:
    study_hash = sha256_file(generalization_matrix_path)
    clock_hash = generalization_matrix["source_artifacts"]["external_reference_clock"][
        "sha256"
    ]
    controller_payload = controller_fingerprint_payload(
        controller_id,
        gain_lock_sha256=gain_lock_sha256,
        gain_definition=str(gain_lock["gain_definition"]),
        matrix_sha256=sha256_file(validation_matrix_path),
        matrix_schema_version=validation_matrix["schema_version"],
        reference_clock_sha256=clock_hash,
    )
    controller_hash = canonical_json_sha256(controller_payload)
    arm_payload = {
        "generalization_config_sha256": study_hash,
        "metric_config_sha256": metric_config_sha256,
        "controller_fingerprint_sha256": controller_hash,
        "patient": patient_id,
        "controller": controller_id,
        "trajectory": trajectory_id,
        "measurement_seed": int(measurement_seed),
        "duration_s": float(duration_s),
        "external_reference_clock_sha256": clock_hash,
        "gain_lock_sha256": gain_lock_sha256,
        "evidence_category": evidence_category,
        "formal_execution": bool(formal_execution),
    }
    arm_hash = canonical_json_sha256(arm_payload)
    result = run_report_arm(
        matrix=validation_matrix,
        matrix_path=validation_matrix_path,
        gain_lock=gain_lock,
        gain_lock_sha256=gain_lock_sha256,
        controller_id=controller_id,
        patient_id=patient_id,
        trajectory_id=trajectory_id,
        evidence_category=evidence_category,
        formal_execution=formal_execution,
        duration_s=float(duration_s),
        output_dir=output_dir,
        measurement_seed=int(measurement_seed),
        extra_provenance={
            "generalization_config_sha256": study_hash,
            "generalization_metric_config_sha256": metric_config_sha256,
            "generalization_arm_fingerprint_payload": arm_payload,
            "generalization_arm_fingerprint_sha256": arm_hash,
            "source_trace_sha256": None,
        },
    )
    metrics = extract_generalization_metrics(
        result["summary"], result["trace"], metric_definitions
    )
    result["summary"]["report_generalization_metrics"] = metrics
    write_strict_json(output_dir / f"{controller_id}.json", result["summary"])
    metric_sidecar = {
        "schema_version": "stage4_report_generalization_metric_sidecar_v1",
        "provenance": result["provenance"],
        "metrics": metrics,
    }
    write_strict_json(
        output_dir / f"{controller_id}_generalization_metrics.json", metric_sidecar
    )
    trace_path = output_dir / f"{controller_id}_trace.npz"
    return {
        **result,
        "generalization_metrics": metrics,
        "trace_path": str(trace_path),
        "trace_sha256": sha256_file(trace_path),
        "generalization_arm_fingerprint_sha256": arm_hash,
    }


def run_generalization_phase(
    *,
    matrix_path: Path,
    gain_lock_path: Path,
    phase: str,
    output_dir: Path,
) -> dict[str, Any]:
    if phase not in {"statistical", "trajectory-demo"}:
        raise ValueError("generalization phase must be statistical or trajectory-demo")
    matrix_path = Path(matrix_path).resolve()
    matrix = load_generalization_matrix(matrix_path)
    validation, validation_path, lock, lock_hash, definitions, metric_hash = (
        _validation_context(matrix, matrix_path, gain_lock_path)
    )
    prepare_fresh_output_directory(output_dir)
    if phase == "statistical":
        raw_arms = matrix["main_statistical_matrix"]["arms"]
        arms = [
            {
                **item,
                "trajectory_id": matrix["main_statistical_matrix"]["trajectory_id"],
            }
            for item in raw_arms
        ]
        evidence_category = STATISTICAL_EVIDENCE_CATEGORY
    else:
        raw_arms = matrix["trajectory_demo_matrix"]["new_execution_arms"]
        arms = [
            {
                **item,
                "controller_id": matrix["trajectory_demo_matrix"]["controller_id"],
                "measurement_seed": matrix["trajectory_demo_matrix"][
                    "measurement_seed"
                ],
            }
            for item in raw_arms
        ]
        evidence_category = TRAJECTORY_DEMO_EVIDENCE_CATEGORY
    records = []
    duration = float(matrix["shared_contract"]["wall_time_limit_s"])
    for arm in arms:
        case_id = (
            f"{arm['patient_id']}__{arm['trajectory_id']}__"
            f"seed{int(arm['measurement_seed'])}"
        )
        arm_dir = Path(output_dir) / case_id / arm["controller_id"]
        result = _run_arm(
            generalization_matrix=matrix,
            generalization_matrix_path=matrix_path,
            validation_matrix=validation,
            validation_matrix_path=validation_path,
            gain_lock=lock,
            gain_lock_sha256=lock_hash,
            metric_definitions=definitions,
            metric_config_sha256=metric_hash,
            patient_id=arm["patient_id"],
            controller_id=arm["controller_id"],
            trajectory_id=arm["trajectory_id"],
            measurement_seed=int(arm["measurement_seed"]),
            evidence_category=evidence_category,
            formal_execution=True,
            duration_s=duration,
            output_dir=arm_dir,
        )
        records.append(
            {
                **arm,
                "case_id": case_id,
                "output_dir": str(arm_dir),
                "trace_path": result["trace_path"],
                "trace_sha256": result["trace_sha256"],
                "controller_fingerprint_sha256": result["provenance"][
                    "controller_fingerprint_sha256"
                ],
                "generalization_arm_fingerprint_sha256": result[
                    "generalization_arm_fingerprint_sha256"
                ],
                "termination_reason": result["summary"]["termination_reason"],
                "metrics": result["generalization_metrics"],
            }
        )
    expected = 36 if phase == "statistical" else 6
    if len(records) != expected:
        raise RuntimeError(f"generalization {phase} arm count differs from {expected}")
    manifest = {
        "schema_version": "stage4_report_generalization_phase_manifest_v1",
        "phase": phase,
        "formal_execution": True,
        "structural_smoke": False,
        "evidence_category": evidence_category,
        "generalization_config_sha256": sha256_file(matrix_path),
        "metric_config_sha256": metric_hash,
        "gain_lock_sha256": lock_hash,
        "external_reference_clock_sha256": matrix["source_artifacts"][
            "external_reference_clock"
        ]["sha256"],
        "frozen_stage4_base_tag": matrix["frozen_start"]["tag"],
        "frozen_stage4_base_commit": matrix["frozen_start"]["commit"],
        "arm_count": len(records),
        "arms": records,
    }
    write_strict_json(Path(output_dir) / "phase_manifest.json", manifest)
    if phase == "statistical":
        aggregate = build_generalization_summary(records, definitions)
        aggregate["generalization_config_sha256"] = sha256_file(matrix_path)
        aggregate["metric_config_sha256"] = metric_hash
        aggregate["evidence_category"] = evidence_category
        write_strict_json(Path(output_dir) / "generalization_summary.json", aggregate)
    return manifest


def run_generalization_structural_smoke(
    *,
    matrix_path: Path,
    gain_lock_path: Path,
    output_dir: Path,
    duration_s: float,
) -> dict[str, Any]:
    if not 0.22 <= float(duration_s) <= GENERALIZATION_SMOKE_MAX_DURATION_S:
        raise ValueError("generalization smoke duration must be in [0.22,0.5] s")
    matrix_path = Path(matrix_path).resolve()
    matrix = load_generalization_matrix(matrix_path)
    validation, validation_path, lock, lock_hash, definitions, metric_hash = (
        _validation_context(matrix, matrix_path, gain_lock_path)
    )
    prepare_fresh_output_directory(output_dir)
    smoke_arms = [
        {
            "case_id": "matched_nominal_group",
            "patient_id": "nominal_reference",
            "controller_id": controller,
            "trajectory_id": "registered_high_flexion_23s",
            "measurement_seed": 44104,
        }
        for controller in (
            "pd_nominal_inverse_dynamics_ff",
            "fixed_mpc_prior_only",
            "trusted_adaptive_mpc",
        )
    ]
    smoke_arms.append(
        {
            "case_id": "report_only_geometry_trajectory_demo",
            "patient_id": "height_moderate_plus_03pct_report_only",
            "controller_id": "trusted_adaptive_mpc",
            "trajectory_id": "moderate_rom_23s",
            "measurement_seed": 44104,
        }
    )
    records = []
    for arm in smoke_arms:
        arm_dir = Path(output_dir) / arm["case_id"] / arm["controller_id"]
        result = _run_arm(
            generalization_matrix=matrix,
            generalization_matrix_path=matrix_path,
            validation_matrix=validation,
            validation_matrix_path=validation_path,
            gain_lock=lock,
            gain_lock_sha256=lock_hash,
            metric_definitions=definitions,
            metric_config_sha256=metric_hash,
            patient_id=arm["patient_id"],
            controller_id=arm["controller_id"],
            trajectory_id=arm["trajectory_id"],
            measurement_seed=arm["measurement_seed"],
            evidence_category=SMOKE_EVIDENCE_CATEGORY,
            formal_execution=False,
            duration_s=float(duration_s),
            output_dir=arm_dir,
        )
        repeated = extract_generalization_metrics(
            result["summary"], result["trace"], definitions
        )
        trace = result["trace"]
        records.append(
            {
                **arm,
                "output_dir": str(arm_dir),
                "trace_path": result["trace_path"],
                "trace_sha256": result["trace_sha256"],
                "metrics": result["generalization_metrics"],
                "deterministic_metric_extraction": (
                    canonical_json_sha256(repeated)
                    == canonical_json_sha256(result["generalization_metrics"])
                ),
                "finite_trace": all(
                    np.all(np.isfinite(value))
                    for value in trace.values()
                    if np.issubdtype(np.asarray(value).dtype, np.number)
                ),
                "reference_trace_sha256": canonical_json_sha256(
                    np.asarray(trace["reference_phase_time_s"]).tolist()
                ),
                "measurement_schedule_sha256": canonical_json_sha256(
                    np.asarray(trace["measurement_new_sample"], dtype=bool).tolist()
                ),
                "initial_human_q_deg": np.asarray(
                    trace["human_q_deg_god_view"][0]
                ).tolist(),
                "initial_robot_q_rad": np.asarray(trace["robot_q_rad"][0]).tolist(),
                "initial_control_beta": np.asarray(
                    trace["dynamic_base_estimate"][0]
                ).tolist(),
                "controller_fingerprint_sha256": result["provenance"][
                    "controller_fingerprint_sha256"
                ],
                "generalization_arm_fingerprint_sha256": result[
                    "generalization_arm_fingerprint_sha256"
                ],
                "gain_lock_sha256": result["provenance"]["gain_lock_sha256"],
                "apply_qualified_model_to_control": result["summary"][
                    "hierarchical_trust"
                ]["apply_qualified_model_to_control"],
            }
        )
    matched = [item for item in records if item["case_id"] == "matched_nominal_group"]
    if len({item["reference_trace_sha256"] for item in matched}) != 1:
        raise RuntimeError("matched smoke arms received different references")
    if len({item["measurement_schedule_sha256"] for item in matched}) != 1:
        raise RuntimeError("matched smoke arms received different measurement schedules")
    if len({tuple(item["initial_human_q_deg"]) for item in matched}) != 1:
        raise RuntimeError("matched smoke Human initial states differ")
    if len({tuple(item["initial_robot_q_rad"]) for item in matched}) != 1:
        raise RuntimeError("matched smoke robot initial states differ")
    for item in records:
        np.testing.assert_allclose(
            item["initial_control_beta"], nominal_base_parameters(HUMAN), atol=1e-12
        )
    pdff = next(
        item for item in matched if item["controller_id"] == "pd_nominal_inverse_dynamics_ff"
    )
    fixed = next(item for item in matched if item["controller_id"] == "fixed_mpc_prior_only")
    adaptive = next(
        item for item in matched if item["controller_id"] == "trusted_adaptive_mpc"
    )
    if pdff["gain_lock_sha256"] != lock_hash:
        raise RuntimeError("PD+FF did not use the frozen gain lock")
    if fixed["apply_qualified_model_to_control"] is not False:
        raise RuntimeError("fixed MPC may apply a promoted beta")
    if adaptive["apply_qualified_model_to_control"] is not True:
        raise RuntimeError("adaptive MPC lost frozen trust semantics")
    geometry_spec, geometry_source = patient_spec_for_id(
        validation,
        validation_path,
        "height_moderate_plus_03pct_report_only",
    )
    geometry_human = geometry_spec.build_human()
    geometry_isolated = bool(
        geometry_source == "report_validation_only"
        and math.isclose(geometry_human.height_m, 1.03 * HUMAN.height_m)
        and math.isclose(geometry_human.body_mass_kg, HUMAN.body_mass_kg)
        and geometry_human.passive_stiffness_nm_rad
        == HUMAN.passive_stiffness_nm_rad
    )
    manifest = {
        "schema_version": "stage4_report_generalization_smoke_manifest_v1",
        "evidence_category": SMOKE_EVIDENCE_CATEGORY,
        "formal_execution": False,
        "structural_smoke": True,
        "scientific_interpretation_permitted": False,
        "duration_s": float(duration_s),
        "generalization_config_sha256": sha256_file(matrix_path),
        "metric_config_sha256": metric_hash,
        "gain_lock_sha256": lock_hash,
        "report_only_geometry_isolated": geometry_isolated,
        "matched_exogenous_inputs_identical": True,
        "fresh_state_per_arm": True,
        "all_finite": all(item["finite_trace"] for item in records),
        "deterministic_metric_extraction": all(
            item["deterministic_metric_extraction"] for item in records
        ),
        "arms": records,
    }
    write_strict_json(Path(output_dir) / "phase_manifest.json", manifest)
    return manifest
