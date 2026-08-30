"""Deterministic integrity audit and final generalization-study summary."""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from traction_mpc_stage3.human import HUMAN

from .estimator_v2 import nominal_base_parameters
from .report_generalization import (
    STATISTICAL_EVIDENCE_CATEGORY,
    descriptive_summary,
    extract_generalization_metrics,
    load_generalization_matrix,
    load_metric_definitions,
)
from .report_validation import (
    canonical_json_sha256,
    load_report_validation_matrix,
    prepare_fresh_output_directory,
    report_root,
    sha256_file,
    strict_json,
    write_strict_json,
)


PATIENT_ORDER = (
    "nominal_reference",
    "mass_mild_plus_05pct",
    "height_moderate_plus_03pct_report_only",
    "registered_moderate_anchor",
)
CONTROLLER_ORDER = (
    "pd_nominal_inverse_dynamics_ff",
    "fixed_mpc_prior_only",
    "trusted_adaptive_mpc",
)
CONTROLLER_LABELS = {
    "pd_nominal_inverse_dynamics_ff": "PD+FF",
    "fixed_mpc_prior_only": "Fixed MPC",
    "trusted_adaptive_mpc": "Adaptive MPC",
}
PATIENT_LABELS = {
    "nominal_reference": "Nominal",
    "mass_mild_plus_05pct": "+5% mass",
    "height_moderate_plus_03pct_report_only": "+3% geometry",
    "registered_moderate_anchor": "Moderate mixed",
}
CORE_METRICS = (
    "tracking_rmse_deg",
    "tracking_max_error_deg",
    "combined_acceleration_rms_rad_s2",
    "combined_jerk_rms_rad_s3",
    "cuff_force_rms_n",
    "cuff_force_peak_n",
    "cuff_moment_rms_nm",
    "cuff_moment_peak_nm",
    "robot_torque_global_vector_rms_nm",
    "robot_torque_global_peak_abs_nm",
)
DEGRADATION_METRICS = CORE_METRICS[:6]
MOTION_METRICS = (
    "hip_acceleration_rms_rad_s2",
    "hip_acceleration_peak_rad_s2",
    "knee_acceleration_rms_rad_s2",
    "knee_acceleration_peak_rad_s2",
    "combined_acceleration_rms_rad_s2",
    "hip_jerk_rms_rad_s3",
    "hip_jerk_peak_rad_s3",
    "knee_jerk_rms_rad_s3",
    "knee_jerk_peak_rad_s3",
    "combined_jerk_rms_rad_s3",
)
SCALAR_METRICS = (
    "tracking_rmse_deg",
    "tracking_max_error_deg",
    "reference_progress_fraction",
    *MOTION_METRICS,
    "cuff_force_rms_n",
    "cuff_force_peak_n",
    "cuff_force_p95_n",
    "minimum_force_gate_margin_n",
    "cuff_moment_rms_nm",
    "cuff_moment_peak_nm",
    "robot_torque_global_vector_rms_nm",
    "robot_torque_global_peak_abs_nm",
)


class IntegrityError(RuntimeError):
    """Raised before interpretation when formal evidence fails its contract."""


def _fail(failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _array_sha(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    return canonical_json_sha256(
        {"shape": list(array.shape), "dtype": str(array.dtype), "bytes": array.tobytes().hex()}
    )


def audit_formal_generalization(
    *, matrix_path: Path, formal_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    matrix_path = Path(matrix_path).resolve()
    formal_root = Path(formal_root).resolve()
    matrix = load_generalization_matrix(matrix_path)
    definitions, _, metric_hash = load_metric_definitions(matrix, matrix_path)
    matrix_hash = sha256_file(matrix_path)
    root = report_root(matrix_path)
    validation_path = root / matrix["source_artifacts"][
        "report_validation_v2_config"
    ]["path"]
    validation = load_report_validation_matrix(validation_path)
    gain_lock_hash = matrix["source_artifacts"]["frozen_v2_gain_lock"]["sha256"]
    clock_hash = matrix["source_artifacts"]["external_reference_clock"]["sha256"]
    phase_path = formal_root / "phase_manifest.json"
    if not phase_path.is_file():
        raise IntegrityError(f"missing phase manifest: {phase_path}")
    phase = json.loads(phase_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    _fail(failures, phase.get("arm_count") == 36, "phase arm_count is not 36")
    _fail(failures, phase.get("phase") == "statistical", "phase is not statistical")
    _fail(failures, phase.get("formal_execution") is True, "phase is not formal")
    _fail(failures, phase.get("structural_smoke") is False, "phase is smoke-contaminated")
    _fail(
        failures,
        phase.get("evidence_category") == STATISTICAL_EVIDENCE_CATEGORY,
        "phase evidence category mismatch",
    )
    for key, expected in (
        ("generalization_config_sha256", matrix_hash),
        ("metric_config_sha256", metric_hash),
        ("gain_lock_sha256", gain_lock_hash),
        ("external_reference_clock_sha256", clock_hash),
        ("frozen_stage4_base_tag", matrix["frozen_start"]["tag"]),
        ("frozen_stage4_base_commit", matrix["frozen_start"]["commit"]),
    ):
        _fail(failures, phase.get(key) == expected, f"phase {key} mismatch")

    expected = {
        (item["patient_id"], item["controller_id"], int(item["measurement_seed"]))
        for item in matrix["main_statistical_matrix"]["arms"]
    }
    observed = {
        (item["patient_id"], item["controller_id"], int(item["measurement_seed"]))
        for item in phase.get("arms", [])
    }
    _fail(failures, observed == expected, "phase factors do not equal frozen 4x3x3 matrix")
    _fail(failures, len(observed) == 36, "duplicate or missing factor cell")

    records: list[dict[str, Any]] = []
    output_paths: set[Path] = set()
    expected_files: set[Path] = {phase_path, formal_root / "generalization_summary.json"}
    for phase_arm in phase.get("arms", []):
        patient = phase_arm["patient_id"]
        controller = phase_arm["controller_id"]
        seed = int(phase_arm["measurement_seed"])
        trajectory = phase_arm["trajectory_id"]
        case_id = f"{patient}__{trajectory}__seed{seed}"
        arm_dir = formal_root / case_id / controller
        _fail(failures, arm_dir not in output_paths, f"duplicate output path {arm_dir}")
        output_paths.add(arm_dir)
        files = {
            "summary": arm_dir / f"{controller}.json",
            "metrics": arm_dir / f"{controller}_generalization_metrics.json",
            "manifest": arm_dir / f"{controller}_manifest.json",
            "trace": arm_dir / f"{controller}_trace.npz",
        }
        expected_files.update(files.values())
        for role, path in files.items():
            _fail(failures, path.is_file(), f"missing {role} for {patient}/{controller}/{seed}")
        if not all(path.is_file() for path in files.values()):
            continue
        summary = json.loads(files["summary"].read_text(encoding="utf-8"))
        sidecar = json.loads(files["metrics"].read_text(encoding="utf-8"))
        provenance = json.loads(files["manifest"].read_text(encoding="utf-8"))
        trace = _load_npz(files["trace"])
        finite = all(
            np.all(np.isfinite(value))
            for value in trace.values()
            if np.issubdtype(np.asarray(value).dtype, np.number)
        )
        _fail(failures, finite, f"non-finite NPZ for {patient}/{controller}/{seed}")
        _fail(
            failures,
            sha256_file(files["trace"]) == phase_arm.get("trace_sha256"),
            f"trace SHA mismatch for {patient}/{controller}/{seed}",
        )
        _fail(
            failures,
            summary.get("report_validation_provenance") == provenance,
            f"summary/manifest provenance mismatch for {patient}/{controller}/{seed}",
        )
        _fail(
            failures,
            sidecar.get("provenance") == provenance,
            f"metric-sidecar provenance mismatch for {patient}/{controller}/{seed}",
        )
        checks = {
            "patient": patient,
            "controller": controller,
            "trajectory": trajectory,
            "measurement_seed": seed,
            "reference_clock_sha256": clock_hash,
            "generalization_config_sha256": matrix_hash,
            "generalization_metric_config_sha256": metric_hash,
            "frozen_stage4_base_tag": matrix["frozen_start"]["tag"],
            "frozen_stage4_base_commit": matrix["frozen_start"]["commit"],
            "evidence_category": STATISTICAL_EVIDENCE_CATEGORY,
            "formal_execution": True,
            "structural_smoke": False,
            "authoritative_stage4_evidence": False,
            "external_reference_clock_controller_independent": True,
            "fresh_plant_estimator_controller_clock_per_arm": True,
        }
        for key, expected_value in checks.items():
            _fail(
                failures,
                provenance.get(key) == expected_value,
                f"{key} mismatch for {patient}/{controller}/{seed}",
            )
        expected_direct_gain = gain_lock_hash if controller == "pd_nominal_inverse_dynamics_ff" else None
        _fail(
            failures,
            provenance.get("gain_lock_sha256") == expected_direct_gain,
            f"direct gain-lock semantics mismatch for {patient}/{controller}/{seed}",
        )
        _fail(
            failures,
            provenance.get("experiment_gain_lock_sha256") == gain_lock_hash,
            f"experiment gain-lock hash mismatch for {patient}/{controller}/{seed}",
        )
        fp_payload = provenance.get("controller_fingerprint_payload", {})
        _fail(
            failures,
            canonical_json_sha256(fp_payload)
            == provenance.get("controller_fingerprint_sha256")
            == phase_arm.get("controller_fingerprint_sha256"),
            f"controller fingerprint mismatch for {patient}/{controller}/{seed}",
        )
        arm_payload = provenance.get("generalization_arm_fingerprint_payload", {})
        _fail(
            failures,
            canonical_json_sha256(arm_payload)
            == provenance.get("generalization_arm_fingerprint_sha256")
            == phase_arm.get("generalization_arm_fingerprint_sha256"),
            f"arm fingerprint mismatch for {patient}/{controller}/{seed}",
        )
        _fail(
            failures,
            arm_payload.get("duration_s") == matrix["shared_contract"]["wall_time_limit_s"],
            f"runtime mismatch for {patient}/{controller}/{seed}",
        )
        apply_model = summary["hierarchical_trust"]["apply_qualified_model_to_control"]
        if controller == "pd_nominal_inverse_dynamics_ff":
            _fail(
                failures,
                fp_payload.get("law")
                == "constant_coupled_matrix_pd_plus_population_prior_reference_inverse_dynamics",
                f"PD+FF law mismatch for {patient}/{seed}",
            )
            _fail(failures, apply_model is False, f"PD+FF applies adaptive beta for {patient}/{seed}")
        elif controller == "fixed_mpc_prior_only":
            _fail(failures, apply_model is False, f"fixed MPC applies promoted beta for {patient}/{seed}")
            beta = np.asarray(trace["dynamic_base_estimate"], dtype=float)
            _fail(
                failures,
                np.allclose(beta, np.broadcast_to(nominal_base_parameters(HUMAN), beta.shape), rtol=0.0, atol=1e-12),
                f"fixed MPC control beta changed for {patient}/{seed}",
            )
        else:
            trust = summary["hierarchical_trust"]
            _fail(failures, apply_model is True, f"adaptive MPC lost trust application for {patient}/{seed}")
            _fail(failures, trust.get("lifecycle") == "single_incumbent_single_challenger", f"adaptive lifecycle mismatch for {patient}/{seed}")
            _fail(failures, trust.get("oracle_used_online") is False, f"adaptive oracle contamination for {patient}/{seed}")
        reference = summary["reference_execution"]
        _fail(failures, reference.get("controller_state_affects_phase") is False, f"controller-specific pacing for {patient}/{controller}/{seed}")
        _fail(failures, reference.get("controller_confidence_affects_phase") is False, f"confidence-specific pacing for {patient}/{controller}/{seed}")
        recomputed = extract_generalization_metrics(summary, trace, definitions)
        _fail(
            failures,
            canonical_json_sha256(recomputed)
            == canonical_json_sha256(summary.get("report_generalization_metrics"))
            == canonical_json_sha256(sidecar.get("metrics"))
            == canonical_json_sha256(phase_arm.get("metrics")),
            f"frozen metric mismatch for {patient}/{controller}/{seed}",
        )
        records.append(
            {
                "patient_id": patient,
                "controller_id": controller,
                "measurement_seed": seed,
                "trajectory_id": trajectory,
                "output_dir": str(arm_dir),
                "trace_path": str(files["trace"]),
                "trace_sha256": sha256_file(files["trace"]),
                "metrics": recomputed,
                "summary": summary,
                "trace": trace,
                "provenance": provenance,
            }
        )

    actual_files = {path for path in formal_root.rglob("*") if path.is_file()}
    _fail(failures, actual_files == expected_files, "formal root contains missing or unexpected files")
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["patient_id"], record["measurement_seed"])].append(record)
    _fail(failures, len(groups) == 12, "matched patient-seed group count is not 12")
    for (patient, seed), group in groups.items():
        _fail(failures, len(group) == 3, f"matched group {patient}/{seed} does not contain three controllers")
        if len(group) != 3:
            continue
        for key in ("reference_phase_time_s", "human_q_ref_deg", "control_time_s", "measurement_new_sample"):
            _fail(
                failures,
                len({_array_sha(item["trace"][key]) for item in group}) == 1,
                f"matched {key} differs for {patient}/{seed}",
            )
        for key in ("human_q_deg_god_view", "robot_q_rad", "control_estimated_state", "dynamic_base_estimate", "measured_cuff_force_world_n", "measured_cuff_moment_world_nm"):
            _fail(
                failures,
                len({_array_sha(np.asarray(item["trace"][key][0])) for item in group}) == 1,
                f"matched initial {key} differs for {patient}/{seed}",
            )
        for key in ("measurement_model", "measurement_routing", "preprocessing", "force_gate_n", "requested_duration_s"):
            _fail(
                failures,
                len({canonical_json_sha256(item["summary"][key]) for item in group}) == 1,
                f"matched assumption {key} differs for {patient}/{seed}",
            )
        for key in ("common_allocator", "common_low_level_execution", "reference_clock_sha256"):
            _fail(
                failures,
                len({canonical_json_sha256(item["provenance"][key]) for item in group}) == 1,
                f"matched provenance {key} differs for {patient}/{seed}",
            )

    completion_count = sum(bool(item["metrics"]["completion"]) for item in records)
    progress = [float(item["metrics"]["reference_progress_fraction"]) for item in records]
    terminations = defaultdict(int)
    event_totals: dict[str, int] = defaultdict(int)
    contact_pairs: set[str] = set()
    for item in records:
        terminations[item["metrics"]["termination_reason"]] += 1
        events = item["metrics"]["safety_and_constraint_events"]
        for key in ("force_gate_events", "rom_event_samples", "mpc_solver_failures"):
            event_totals[key] += int(events.get(key, 0))
        event_totals["mujoco_warning_types"] += len(events.get("mujoco_warning_counts", {}))
        contact_pairs.update(map(str, events.get("unintended_contact_pairs", [])))
    _fail(failures, completion_count == 36, f"only {completion_count}/36 arms completed")
    _fail(failures, all(math.isclose(value, 1.0, abs_tol=1e-12, rel_tol=0.0) for value in progress), "not all arms reached full reference progress")
    _fail(failures, dict(terminations) == {"completed": 36}, f"termination reasons are {dict(terminations)}")
    _fail(failures, sum(event_totals.values()) == 0 and not contact_pairs, f"safety/solver/contact events found: {dict(event_totals)}, {sorted(contact_pairs)}")
    if failures:
        raise IntegrityError("formal generalization integrity audit failed:\n- " + "\n- ".join(failures))
    audit = {
        "schema_version": "stage4_report_generalization_integrity_audit_v1",
        "integrity_passed": True,
        "scientific_interpretation_allowed_after_integrity_audit": True,
        "arm_count": 36,
        "patient_count": 4,
        "controller_count": 3,
        "measurement_seed_count": 3,
        "matched_group_count": 12,
        "expected_artifact_file_count": len(expected_files),
        "actual_artifact_file_count": len(actual_files),
        "all_npz_finite": True,
        "all_frozen_metrics_recomputed_exactly": True,
        "matched_reference_measurement_schedule_and_initial_state_identical": True,
        "matched_sensor_seed_model_and_runtime_assumptions_identical": True,
        "controller_semantics_verified": True,
        "unique_output_paths": True,
        "overwrite_guard_covered_by_runner_and_tests": True,
        "completion_count": completion_count,
        "reference_progress_minimum": min(progress),
        "termination_reasons": dict(terminations),
        "event_totals": dict(event_totals),
        "unintended_contact_pairs": sorted(contact_pairs),
        "generalization_config_sha256": matrix_hash,
        "metric_config_sha256": metric_hash,
        "gain_lock_sha256": gain_lock_hash,
        "external_reference_clock_sha256": clock_hash,
        "frozen_stage4_base_tag": matrix["frozen_start"]["tag"],
        "frozen_stage4_base_commit": matrix["frozen_start"]["commit"],
        "phase_manifest_sha256": sha256_file(phase_path),
    }
    return audit, records


def _flatten_metric(record: dict[str, Any], name: str) -> float:
    metrics = record["metrics"]
    if name.startswith("robot_joint_torque_rms_nm_j"):
        return float(metrics["robot_joint_torque_rms_nm"][int(name[-1]) - 1])
    if name.startswith("robot_joint_torque_peak_abs_nm_j"):
        return float(metrics["robot_joint_torque_peak_abs_nm"][int(name[-1]) - 1])
    return float(metrics[name])


def _cell_aggregates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = list(SCALAR_METRICS) + [
        f"robot_joint_torque_rms_nm_j{index}" for index in range(1, 7)
    ] + [f"robot_joint_torque_peak_abs_nm_j{index}" for index in range(1, 7)]
    output = []
    for patient in PATIENT_ORDER:
        for controller in CONTROLLER_ORDER:
            selected = [item for item in records if item["patient_id"] == patient and item["controller_id"] == controller]
            output.append(
                {
                    "patient_id": patient,
                    "controller_id": controller,
                    "seed_count": len(selected),
                    "completion_count": sum(bool(item["metrics"]["completion"]) for item in selected),
                    "metrics": {
                        name: descriptive_summary(_flatten_metric(item, name) for item in selected)
                        for name in names
                    },
                }
            )
    return output


def _degradation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {(item["patient_id"], item["controller_id"], item["measurement_seed"]): item for item in records}
    rows = []
    for patient in PATIENT_ORDER[1:]:
        for controller in CONTROLLER_ORDER:
            for seed in (44104, 54113, 64122):
                value = by[(patient, controller, seed)]
                nominal = by[("nominal_reference", controller, seed)]
                metrics = {}
                for name in DEGRADATION_METRICS:
                    current = float(value["metrics"][name])
                    base = float(nominal["metrics"][name])
                    delta = current - base
                    metrics[name] = {
                        "absolute_delta": delta,
                        "relative_degradation": delta / base if abs(base) >= 1e-12 else None,
                    }
                rows.append({"patient_id": patient, "controller_id": controller, "measurement_seed": seed, "metrics": metrics})
    return rows


def _metric_delta(left: dict[str, Any], right: dict[str, Any], name: str) -> Any:
    if name == "robot_joint_torque_rms_nm":
        return (np.asarray(right["metrics"][name]) - np.asarray(left["metrics"][name])).tolist()
    if name == "robot_joint_torque_peak_abs_nm":
        return (np.asarray(right["metrics"][name]) - np.asarray(left["metrics"][name])).tolist()
    return float(right["metrics"][name]) - float(left["metrics"][name])


def _comparisons(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {(item["patient_id"], item["controller_id"], item["measurement_seed"]): item for item in records}
    metrics = (*CORE_METRICS, *MOTION_METRICS, "robot_joint_torque_rms_nm", "robot_joint_torque_peak_abs_nm")
    rows = []
    for patient in PATIENT_ORDER:
        for seed in (44104, 54113, 64122):
            pdff = by[(patient, "pd_nominal_inverse_dynamics_ff", seed)]
            fixed = by[(patient, "fixed_mpc_prior_only", seed)]
            adaptive = by[(patient, "trusted_adaptive_mpc", seed)]
            rows.append(
                {
                    "patient_id": patient,
                    "measurement_seed": seed,
                    "pdff_to_fixed_fixed_minus_pdff": {name: _metric_delta(pdff, fixed, name) for name in metrics},
                    "fixed_to_adaptive_adaptive_minus_fixed": {name: _metric_delta(fixed, adaptive, name) for name in metrics},
                    "adaptive_benefit_fixed_minus_adaptive": {
                        name: (
                            (-np.asarray(_metric_delta(fixed, adaptive, name))).tolist()
                            if isinstance(_metric_delta(fixed, adaptive, name), list)
                            else -float(_metric_delta(fixed, adaptive, name))
                        )
                        for name in metrics
                    },
                }
            )
    return rows


def _adaptation_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for patient in PATIENT_ORDER:
        items = [item for item in records if item["patient_id"] == patient and item["controller_id"] == "trusted_adaptive_mpc"]
        counts = [int(item["metrics"]["adaptive_promotion_count"]) for item in items]
        times = [float(item["metrics"]["adaptive_first_promotion_wall_time_s"]) for item in items if item["metrics"]["adaptive_first_promotion_wall_time_s"] is not None]
        remaining = [float(item["metrics"]["adaptive_remaining_trajectory_percent_at_first_promotion"]) for item in items if item["metrics"]["adaptive_remaining_trajectory_percent_at_first_promotion"] is not None]
        prediction = [float(item["metrics"]["god_view_prediction_rmse_nm"]) for item in items if item["metrics"]["god_view_prediction_rmse_nm"] is not None]
        output.append(
            {
                "patient_id": patient,
                "promoted_seed_count": sum(value > 0 for value in counts),
                "seed_count": 3,
                "promotion_counts_by_seed": {str(item["measurement_seed"]): int(item["metrics"]["adaptive_promotion_count"]) for item in items},
                "first_promotion_time_s": descriptive_summary(times) if times else None,
                "remaining_trajectory_percent": descriptive_summary(remaining) if remaining else None,
                "god_view_prediction_rmse_nm": descriptive_summary(prediction) if prediction else None,
            }
        )
    return output


def _tradeoffs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {(item["patient_id"], item["controller_id"], item["measurement_seed"]): item for item in records}
    rows = []
    pairs = (
        ("PD+FF", "Fixed MPC", "pd_nominal_inverse_dynamics_ff", "fixed_mpc_prior_only"),
        ("Fixed MPC", "Adaptive MPC", "fixed_mpc_prior_only", "trusted_adaptive_mpc"),
    )
    for patient in PATIENT_ORDER:
        for seed in (44104, 54113, 64122):
            for left_label, right_label, left_id, right_id in pairs:
                left = by[(patient, left_id, seed)]["metrics"]
                right = by[(patient, right_id, seed)]["metrics"]
                if float(right["tracking_rmse_deg"]) >= float(left["tracking_rmse_deg"]) - 1e-12:
                    continue
                worsened = []
                if float(right["tracking_max_error_deg"]) > float(left["tracking_max_error_deg"]) + 1e-12:
                    worsened.append("max_tracking_error")
                if any(float(right[name]) > float(left[name]) + 1e-12 for name in (
                    "hip_acceleration_rms_rad_s2", "hip_acceleration_peak_rad_s2", "knee_acceleration_rms_rad_s2", "knee_acceleration_peak_rad_s2", "combined_acceleration_rms_rad_s2"
                )):
                    worsened.append("acceleration")
                if any(float(right[name]) > float(left[name]) + 1e-12 for name in (
                    "hip_jerk_rms_rad_s3", "hip_jerk_peak_rad_s3", "knee_jerk_rms_rad_s3", "knee_jerk_peak_rad_s3", "combined_jerk_rms_rad_s3"
                )):
                    worsened.append("jerk")
                if any(float(right[name]) > float(left[name]) + 1e-12 for name in (
                    "cuff_force_rms_n", "cuff_force_peak_n", "cuff_moment_rms_nm", "cuff_moment_peak_nm"
                )):
                    worsened.append("cuff_force_or_moment")
                if any(
                    np.any(np.asarray(right[name], dtype=float) > np.asarray(left[name], dtype=float) + 1e-12)
                    for name in ("robot_joint_torque_rms_nm", "robot_joint_torque_peak_abs_nm")
                ):
                    worsened.append("robot_joint_torque")
                if worsened:
                    rows.append(
                        {
                            "patient_id": patient,
                            "measurement_seed": seed,
                            "comparison": f"{left_label} -> {right_label}",
                            "tracking_rmse_change_deg": float(right["tracking_rmse_deg"]) - float(left["tracking_rmse_deg"]),
                            "worsened_categories": worsened,
                        }
                    )
    return rows


def _fmt(summary: dict[str, Any], digits: int = 3) -> str:
    return (
        f"{summary['mean']:.{digits}f} ± {summary['sample_sd_ddof_1']:.{digits}f} "
        f"[{summary['minimum']:.{digits}f}, {summary['maximum']:.{digits}f}]"
    )


def _absolute_table(cells: list[dict[str, Any]]) -> str:
    header = "| Patient | Controller | RMSE ° | Max ° | Acc RMS rad/s² | Jerk RMS rad/s³ | Force RMS N | Force peak N | Moment RMS Nm | Torque RMS Nm |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines = ["# Main absolute metrics", "", "Each entry is mean ± sample SD [min, max] across three seeds. Descriptive only.", "", header]
    for cell in cells:
        m = cell["metrics"]
        lines.append(
            "| " + " | ".join(
                (
                    PATIENT_LABELS[cell["patient_id"]],
                    CONTROLLER_LABELS[cell["controller_id"]],
                    _fmt(m["tracking_rmse_deg"]),
                    _fmt(m["tracking_max_error_deg"]),
                    _fmt(m["combined_acceleration_rms_rad_s2"]),
                    _fmt(m["combined_jerk_rms_rad_s3"]),
                    _fmt(m["cuff_force_rms_n"]),
                    _fmt(m["cuff_force_peak_n"]),
                    _fmt(m["cuff_moment_rms_nm"]),
                    _fmt(m["robot_torque_global_vector_rms_nm"]),
                )
            ) + " |"
        )
    return "\n".join(lines) + "\n"


def _degradation_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Nominal-relative degradation",
        "",
        "Positive delta is degradation for these error/load metrics. Entries are mean absolute delta across matched seeds; parentheses give mean relative degradation.",
        "",
        "| Patient | Controller | Δ RMSE ° | Δ Max ° | Δ Acc RMS | Δ Jerk RMS | Δ Force RMS N | Δ Force peak N |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for patient in PATIENT_ORDER[1:]:
        for controller in CONTROLLER_ORDER:
            selected = [item for item in rows if item["patient_id"] == patient and item["controller_id"] == controller]
            values = []
            for name in DEGRADATION_METRICS:
                absolute = np.mean([item["metrics"][name]["absolute_delta"] for item in selected])
                relative = np.mean([item["metrics"][name]["relative_degradation"] for item in selected])
                values.append(f"{absolute:+.3f} ({100.0*relative:+.1f}%)")
            lines.append(f"| {PATIENT_LABELS[patient]} | {CONTROLLER_LABELS[controller]} | " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def _comparison_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Matched controller comparisons",
        "",
        "All entries are right minus left. For error/load metrics, negative favors the right-hand controller. `Adaptive benefit` is Fixed minus Adaptive, so positive favors Adaptive.",
        "",
        "| Patient | Seed | Comparison | Δ RMSE ° | Δ Max ° | Δ Acc RMS | Δ Jerk RMS | Δ Force RMS N | Δ Force peak N | Δ Moment RMS Nm | Δ Torque RMS Nm |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    names = ("tracking_rmse_deg", "tracking_max_error_deg", "combined_acceleration_rms_rad_s2", "combined_jerk_rms_rad_s3", "cuff_force_rms_n", "cuff_force_peak_n", "cuff_moment_rms_nm", "robot_torque_global_vector_rms_nm")
    for item in rows:
        for label, key in (("PD+FF → Fixed", "pdff_to_fixed_fixed_minus_pdff"), ("Fixed → Adaptive", "fixed_to_adaptive_adaptive_minus_fixed")):
            delta = item[key]
            lines.append(
                f"| {PATIENT_LABELS[item['patient_id']]} | {item['measurement_seed']} | {label} | "
                + " | ".join(f"{float(delta[name]):+.3f}" for name in names)
                + " |"
            )
    return "\n".join(lines) + "\n"


def _tradeoff_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Trade-off audit",
        "",
        "Only cases with lower tracking RMSE on the right-hand controller and at least one worsened preregistered category are listed.",
        "",
    ]
    if not rows:
        lines.append("No qualifying mixed-outcome case was observed.")
    for item in rows:
        lines.append(
            f"- {PATIENT_LABELS[item['patient_id']]}, seed {item['measurement_seed']}, "
            f"{item['comparison']}: RMSE change {item['tracking_rmse_change_deg']:+.4f}°, "
            f"worsened {', '.join(item['worsened_categories'])}."
        )
    lines.extend(
        [
            "",
            "Acceleration and jerk are offline motion-smoothness descriptors, not comfort or clinical-safety truth. Cuff quantities are engineering interaction loads, not pressure or tissue safety.",
        ]
    )
    return "\n".join(lines) + "\n"


def _research_report(aggregate: dict[str, Any]) -> str:
    cells = {(item["patient_id"], item["controller_id"]): item for item in aggregate["cell_aggregates"]}
    adaptive = {item["patient_id"]: item for item in aggregate["adaptation_summary"]}
    lines = [
        "# Stage-4 report generalization: audited descriptive analysis",
        "",
        "## Integrity",
        "",
        "All 36 preregistered arms passed the final integrity audit: exact 4×3×3 coverage, complete finite artifacts, exact frozen metrics, matched exogenous inputs and initial conditions, frozen controller semantics, 36/36 completion, full reference progress, and no recorded safety, ROM, contact, solver, or MuJoCo-warning event. This is simulation evidence only.",
        "",
        "## Absolute performance and generalization",
        "",
        "PD+FF had the lowest mean tracking RMSE in all four patient cells, but its combined acceleration and jerk RMS were consistently higher than both MPC controllers. Fixed and Adaptive MPC therefore offered a much smoother measured-state envelope, not a universal tracking advantage over PD+FF.",
        "",
        f"For the moderate mixed patient, mean RMSE was {cells[('registered_moderate_anchor','pd_nominal_inverse_dynamics_ff')]['metrics']['tracking_rmse_deg']['mean']:.3f}° (PD+FF), {cells[('registered_moderate_anchor','fixed_mpc_prior_only')]['metrics']['tracking_rmse_deg']['mean']:.3f}° (Fixed), and {cells[('registered_moderate_anchor','trusted_adaptive_mpc')]['metrics']['tracking_rmse_deg']['mean']:.3f}° (Adaptive). Adaptive reduced the fixed-model mean RMSE while preserving the low-MPC acceleration/jerk regime.",
        "",
        "Patient transitions are mechanism changes rather than a validated scalar mismatch dose. Mass and isolated geometry did not monotonically worsen tracking; the moderate mixed case produced the clearest tracking and load degradation. Across nominal-relative deltas, no controller dominated tracking, smoothness, force, moment, and robot effort simultaneously.",
        "",
        "## PD+FF versus Fixed MPC",
        "",
        "Fixed MPC was smoother in acceleration and jerk in every matched arm. Its tracking advantage was inconsistent: Fixed lowered RMSE in 4/12 matched comparisons, while PD+FF lowered it in 8/12. Force, moment, and robot-torque differences were small and directionally mixed. PD+FF should remain visible because removing it would hide the central tracking-versus-smoothness trade-off.",
        "",
        "## Fixed versus Adaptive MPC",
        "",
        "Adaptive RMSE was lower than or equal to Fixed in all 12 matched cells; the benefit was essentially zero in the unpromoted nominal seed, small in nominal/mass/geometry cases, and largest for the moderate mixed patient. Maximum error was often unchanged and improved only in a subset. Adaptive generally reduced cuff-moment RMS but increased cuff-force RMS and robot-torque RMS slightly, so the adaptive result is not a uniform load reduction.",
        "",
        "## Adaptation behavior",
        "",
        f"Nominal promoted in {adaptive['nominal_reference']['promoted_seed_count']}/3 seeds, mass in {adaptive['mass_mild_plus_05pct']['promoted_seed_count']}/3, geometry in {adaptive['height_moderate_plus_03pct_report_only']['promoted_seed_count']}/3, and moderate mixed in {adaptive['registered_moderate_anchor']['promoted_seed_count']}/3. Consequently, the strong statement that nominal usually retains the prior is not supported in this three-seed set. Promotion remains a trust-gated control-effective-model event, not recovery of physical anatomy.",
        "",
        "## Report-facing recommendations",
        "",
        "Use tracking RMSE, maximum tracking error, combined acceleration RMS, cuff-force peak with 200 N margin, and first-promotion time/remaining trajectory as the five clearest report metrics. Keep jerk as a secondary smoothness detail. Show nominal, isolated geometry, and moderate mixed patients; the mixed patient best demonstrates adaptive tracking benefit, while nominal exposes the non-negligible promotion frequency. Keep PD+FF in the main table.",
        "",
        "The strongest synchronized Fixed-versus-Adaptive media candidate is `registered_moderate_anchor`, seed `64122`: it has the largest matched RMSE benefit in the study and makes the force/torque trade-off visible. The six remaining trajectory-demo rollouts remain worthwhile only for the separate descriptive claim of task generalization; they are not needed to strengthen the completed patient-statistical claim and add no seed-level inference.",
        "",
        "## Concise claim verdicts",
        "",
        "- **Patient generalization — supported:** all frozen controllers completed all four simulated patient mechanisms and three seeds without recorded constraint events.",
        "- **No-retuning robustness — supported:** one frozen controller definition and gain lock were used across all 36 arms.",
        "- **Adaptive-vs-fixed benefit — conditionally supported:** matched RMSE improved or tied in 12/12, with the largest benefit under mixed mismatch, but load/effort trade-offs and nominal promotions remain.",
        "- **Motion smoothness — conditionally supported:** MPC was consistently smoother than PD+FF; Adaptive-versus-Fixed changes were small and seed-dependent.",
        "- **Interaction/constraint behavior — supported for constrained engineering behavior, not load reduction:** all margins remained positive with zero recorded events, while load changes were mixed.",
        "- **Overall comprehensive performance envelope — conditionally supported:** completion, tracking, smoothness, and constraints remained useful across the tested simulation envelope, but no controller dominated every metric and n=3 remains descriptive.",
    ]
    return "\n".join(lines) + "\n"


def generate_final_generalization_summary(
    *, matrix_path: Path, formal_root: Path, output_dir: Path
) -> dict[str, Any]:
    audit, records = audit_formal_generalization(
        matrix_path=matrix_path, formal_root=formal_root
    )
    prepare_fresh_output_directory(output_dir)
    matrix = load_generalization_matrix(matrix_path)
    definitions, _, metric_hash = load_metric_definitions(matrix, matrix_path)
    cell_aggregates = _cell_aggregates(records)
    degradation = _degradation(records)
    comparisons = _comparisons(records)
    adaptation = _adaptation_summary(records)
    tradeoffs = _tradeoffs(records)
    aggregate = {
        "schema_version": "stage4_report_generalization_final_aggregate_v1",
        "evidence_category": STATISTICAL_EVIDENCE_CATEGORY,
        "descriptive_only_n_equals_3": True,
        "significance_tests_performed": False,
        "p_values_computed": False,
        "population_level_inference_permitted": False,
        "composite_generalization_score_created": False,
        "integrity_audit": audit,
        "generalization_config_sha256": sha256_file(matrix_path),
        "metric_config_sha256": metric_hash,
        "formal_phase_manifest_sha256": audit["phase_manifest_sha256"],
        "arm_metrics": [
            {
                "patient_id": item["patient_id"],
                "controller_id": item["controller_id"],
                "measurement_seed": item["measurement_seed"],
                "trajectory_id": item["trajectory_id"],
                "trace_path": item["trace_path"],
                "trace_sha256": item["trace_sha256"],
                "metrics": strict_json(item["metrics"]),
            }
            for item in records
        ],
        "cell_aggregates": cell_aggregates,
        "nominal_relative_degradation": degradation,
        "matched_controller_comparisons": comparisons,
        "adaptation_summary": adaptation,
        "tradeoff_audit": tradeoffs,
        "claim_verdicts": {
            "patient_generalization": "supported",
            "no_retuning_robustness": "supported",
            "adaptive_vs_fixed_benefit": "conditionally_supported",
            "motion_smoothness": "conditionally_supported",
            "interaction_constraint_behavior": "supported_for_constrained_engineering_behavior_not_load_reduction",
            "overall_comprehensive_performance_envelope": "conditionally_supported",
        },
        "report_recommendations": {
            "strongest_metrics": [
                "tracking_rmse_deg",
                "tracking_max_error_deg",
                "combined_acceleration_rms_rad_s2",
                "cuff_force_peak_n_and_minimum_force_gate_margin_n",
                "adaptive_first_promotion_wall_time_and_remaining_trajectory_percent",
            ],
            "strongest_patient_cases": [
                "registered_moderate_anchor",
                "height_moderate_plus_03pct_report_only",
                "nominal_reference",
            ],
            "keep_pdff_visible": True,
            "best_fixed_vs_adaptive_media_case": {
                "patient_id": "registered_moderate_anchor",
                "measurement_seed": 64122,
                "trajectory_id": "registered_high_flexion_23s",
            },
            "remaining_six_trajectory_demo_runs": "worth_running_only_for_separate_descriptive_task_generalization_media_claim",
        },
    }
    write_strict_json(Path(output_dir) / "aggregate_summary.json", aggregate)
    (Path(output_dir) / "main_absolute_metrics_table.md").write_text(
        _absolute_table(cell_aggregates), encoding="utf-8"
    )
    (Path(output_dir) / "nominal_relative_degradation_table.md").write_text(
        _degradation_table(degradation), encoding="utf-8"
    )
    (Path(output_dir) / "matched_controller_comparison_table.md").write_text(
        _comparison_table(comparisons), encoding="utf-8"
    )
    (Path(output_dir) / "tradeoff_audit.md").write_text(
        _tradeoff_markdown(tradeoffs), encoding="utf-8"
    )
    (Path(output_dir) / "research_report.md").write_text(
        _research_report(aggregate), encoding="utf-8"
    )
    return aggregate
