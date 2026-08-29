"""Integrity audit and read-only source manifest for report visualization."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .report_generalization import (
    STATISTICAL_EVIDENCE_CATEGORY,
    TRAJECTORY_DEMO_EVIDENCE_CATEGORY,
    VISUALIZATION_EVIDENCE_CATEGORY,
    extract_generalization_metrics,
    load_generalization_matrix,
    load_metric_definitions,
)
from .report_validation import (
    canonical_json_sha256,
    prepare_fresh_output_directory,
    report_root,
    sha256_file,
    write_strict_json,
)


PATIENTS = (
    "nominal_reference",
    "height_moderate_plus_03pct_report_only",
    "registered_moderate_anchor",
)
TRAJECTORIES = (
    "registered_high_flexion_23s",
    "moderate_rom_23s",
    "hip_dominant_low_knee_23s",
)
CONTROLLERS = (
    "pd_nominal_inverse_dynamics_ff",
    "fixed_mpc_prior_only",
    "trusted_adaptive_mpc",
)
ADAPTIVE = "trusted_adaptive_mpc"
SEED = 44104


class VisualizationIntegrityError(RuntimeError):
    """Raised before a visualization manifest is created."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _arm_files(arm_dir: Path, controller: str) -> dict[str, Path]:
    return {
        "summary": arm_dir / f"{controller}.json",
        "metrics": arm_dir / f"{controller}_generalization_metrics.json",
        "manifest": arm_dir / f"{controller}_manifest.json",
        "trace": arm_dir / f"{controller}_trace.npz",
    }


def _event_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    events = metrics["safety_and_constraint_events"]
    return {
        "force_gate_events": int(events.get("force_gate_events", 0)),
        "rom_event_samples": int(events.get("rom_event_samples", 0)),
        "mpc_solver_failures": int(events.get("mpc_solver_failures", 0)),
        "unintended_contact_pairs": list(events.get("unintended_contact_pairs", [])),
        "mujoco_warning_counts": dict(events.get("mujoco_warning_counts", {})),
    }


def _source_item(
    *,
    phase: dict[str, Any],
    phase_path: Path,
    phase_arm: dict[str, Any],
    source_root: Path,
    matrix_hash: str,
    metric_hash: str,
) -> dict[str, Any]:
    trace_path = Path(phase_arm["trace_path"])
    if not trace_path.is_absolute():
        trace_path = source_root / trace_path
    trace_path = trace_path.resolve()
    controller = phase_arm["controller_id"]
    arm_dir = trace_path.parent
    summary_path = arm_dir / f"{controller}.json"
    summary = _load_json(summary_path)
    metrics = summary["report_generalization_metrics"]
    return {
        "patient_id": phase_arm["patient_id"],
        "trajectory_id": phase_arm["trajectory_id"],
        "controller_id": controller,
        "measurement_seed": int(phase_arm["measurement_seed"]),
        "source_evidence_category": phase["evidence_category"],
        "source_phase_manifest_path": str(phase_path.resolve()),
        "source_phase_manifest_sha256": sha256_file(phase_path),
        "source_summary_path": str(summary_path),
        "source_trace_path": str(trace_path),
        "source_trace_sha256": phase_arm["trace_sha256"],
        "controller_fingerprint_sha256": phase_arm[
            "controller_fingerprint_sha256"
        ],
        "generalization_arm_fingerprint_sha256": phase_arm[
            "generalization_arm_fingerprint_sha256"
        ],
        "generalization_config_sha256": matrix_hash,
        "metric_config_sha256": metric_hash,
        "promotion": {
            "count": int(metrics["adaptive_promotion_count"]),
            "first_promotion_wall_time_s": metrics[
                "adaptive_first_promotion_wall_time_s"
            ],
            "remaining_trajectory_percent_at_first_promotion": metrics[
                "adaptive_remaining_trajectory_percent_at_first_promotion"
            ],
        },
        "descriptive_metrics": {
            "completion": bool(metrics["completion"]),
            "reference_progress_fraction": float(
                metrics["reference_progress_fraction"]
            ),
            "termination_reason": metrics["termination_reason"],
            "tracking_rmse_deg": float(metrics["tracking_rmse_deg"]),
            "tracking_max_error_deg": float(metrics["tracking_max_error_deg"]),
            "combined_acceleration_rms_rad_s2": float(
                metrics["combined_acceleration_rms_rad_s2"]
            ),
            "cuff_force_peak_n": float(metrics["cuff_force_peak_n"]),
            "minimum_force_gate_margin_n": float(
                metrics["minimum_force_gate_margin_n"]
            ),
            "events": _event_summary(metrics),
        },
        "intended_media_evidence_category": VISUALIZATION_EVIDENCE_CATEGORY,
        "source_evidence_relabelled": False,
    }


def audit_trajectory_demo(
    *, matrix_path: Path, demo_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    matrix_path = Path(matrix_path).resolve()
    demo_root = Path(demo_root).resolve()
    matrix = load_generalization_matrix(matrix_path)
    definitions, _, metric_hash = load_metric_definitions(matrix, matrix_path)
    matrix_hash = sha256_file(matrix_path)
    expected_gain = matrix["source_artifacts"]["frozen_v2_gain_lock"]["sha256"]
    expected_clock = matrix["source_artifacts"]["external_reference_clock"]["sha256"]
    phase_path = demo_root / "phase_manifest.json"
    if not phase_path.is_file():
        raise VisualizationIntegrityError(f"missing demo phase manifest: {phase_path}")
    phase = _load_json(phase_path)
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    expected = {
        (item["patient_id"], item["trajectory_id"], ADAPTIVE, SEED)
        for item in matrix["trajectory_demo_matrix"]["new_execution_arms"]
    }
    observed = {
        (
            item["patient_id"],
            item["trajectory_id"],
            item["controller_id"],
            int(item["measurement_seed"]),
        )
        for item in phase.get("arms", [])
    }
    check(len(expected) == len(observed) == 6 and expected == observed, "demo matrix is not the frozen six-arm set")
    for key, value in (
        ("phase", "trajectory-demo"),
        ("formal_execution", True),
        ("structural_smoke", False),
        ("evidence_category", TRAJECTORY_DEMO_EVIDENCE_CATEGORY),
        ("generalization_config_sha256", matrix_hash),
        ("metric_config_sha256", metric_hash),
        ("gain_lock_sha256", expected_gain),
        ("external_reference_clock_sha256", expected_clock),
        ("frozen_stage4_base_tag", matrix["frozen_start"]["tag"]),
        ("frozen_stage4_base_commit", matrix["frozen_start"]["commit"]),
        ("arm_count", 6),
    ):
        check(phase.get(key) == value, f"phase {key} mismatch")

    expected_files = {phase_path}
    records: list[dict[str, Any]] = []
    output_paths: set[Path] = set()
    for arm in phase.get("arms", []):
        patient = arm["patient_id"]
        trajectory = arm["trajectory_id"]
        controller = arm["controller_id"]
        label = f"{patient}/{trajectory}"
        trace_path = Path(arm["trace_path"])
        if not trace_path.is_absolute():
            trace_path = report_root(matrix_path) / trace_path
        arm_dir = trace_path.resolve().parent
        check(arm_dir not in output_paths, f"duplicate output path for {label}")
        output_paths.add(arm_dir)
        files = _arm_files(arm_dir, controller)
        expected_files.update(files.values())
        for role, path in files.items():
            check(path.is_file(), f"missing {role} for {label}")
        if not all(path.is_file() for path in files.values()):
            continue
        summary = _load_json(files["summary"])
        sidecar = _load_json(files["metrics"])
        provenance = _load_json(files["manifest"])
        trace = _load_trace(files["trace"])
        check(
            all(
                np.all(np.isfinite(value))
                for value in trace.values()
                if np.issubdtype(np.asarray(value).dtype, np.number)
            ),
            f"non-finite trace array for {label}",
        )
        trace_hash = sha256_file(files["trace"])
        check(trace_hash == arm.get("trace_sha256"), f"trace SHA mismatch for {label}")
        check(summary.get("report_validation_provenance") == provenance, f"summary provenance mismatch for {label}")
        check(sidecar.get("provenance") == provenance, f"metric provenance mismatch for {label}")
        for key, value in (
            ("patient", patient),
            ("trajectory", trajectory),
            ("controller", ADAPTIVE),
            ("measurement_seed", SEED),
            ("evidence_category", TRAJECTORY_DEMO_EVIDENCE_CATEGORY),
            ("formal_execution", True),
            ("structural_smoke", False),
            ("authoritative_stage4_evidence", False),
            ("generalization_config_sha256", matrix_hash),
            ("generalization_metric_config_sha256", metric_hash),
            ("experiment_gain_lock_sha256", expected_gain),
            ("reference_clock_sha256", expected_clock),
            ("frozen_stage4_base_tag", matrix["frozen_start"]["tag"]),
            ("frozen_stage4_base_commit", matrix["frozen_start"]["commit"]),
            ("external_reference_clock_controller_independent", True),
            ("fresh_plant_estimator_controller_clock_per_arm", True),
        ):
            check(provenance.get(key) == value, f"{key} mismatch for {label}")
        controller_payload = provenance.get("controller_fingerprint_payload", {})
        arm_payload = provenance.get("generalization_arm_fingerprint_payload", {})
        check(
            canonical_json_sha256(controller_payload)
            == provenance.get("controller_fingerprint_sha256")
            == arm.get("controller_fingerprint_sha256"),
            f"controller fingerprint mismatch for {label}",
        )
        check(
            canonical_json_sha256(arm_payload)
            == provenance.get("generalization_arm_fingerprint_sha256")
            == arm.get("generalization_arm_fingerprint_sha256"),
            f"arm fingerprint mismatch for {label}",
        )
        check(
            math.isclose(
                float(arm_payload.get("duration_s", -1.0)),
                float(matrix["shared_contract"]["wall_time_limit_s"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ),
            f"runtime contract mismatch for {label}",
        )
        trust = summary.get("hierarchical_trust", {})
        check(trust.get("apply_qualified_model_to_control") is True, f"adaptive control disabled for {label}")
        check(trust.get("lifecycle") == "single_incumbent_single_challenger", f"trust lifecycle mismatch for {label}")
        reference = summary.get("reference_execution", {})
        check(reference.get("controller_state_affects_phase") is False, f"controller-specific pacing for {label}")
        check(reference.get("controller_confidence_affects_phase") is False, f"confidence-specific pacing for {label}")
        recomputed = extract_generalization_metrics(summary, trace, definitions)
        check(
            canonical_json_sha256(recomputed)
            == canonical_json_sha256(summary.get("report_generalization_metrics"))
            == canonical_json_sha256(sidecar.get("metrics"))
            == canonical_json_sha256(arm.get("metrics")),
            f"frozen metric mismatch for {label}",
        )
        events = _event_summary(recomputed)
        check(bool(recomputed["completion"]), f"incomplete rollout for {label}")
        check(math.isclose(float(recomputed["reference_progress_fraction"]), 1.0, abs_tol=1e-12, rel_tol=0.0), f"incomplete reference for {label}")
        check(recomputed["termination_reason"] == "completed", f"termination mismatch for {label}")
        check(
            events["force_gate_events"] == 0
            and events["rom_event_samples"] == 0
            and events["mpc_solver_failures"] == 0
            and not events["unintended_contact_pairs"]
            and not events["mujoco_warning_counts"],
            f"safety/solver/contact/MuJoCo event for {label}: {events}",
        )
        records.append(
            {
                "patient_id": patient,
                "trajectory_id": trajectory,
                "controller_id": controller,
                "measurement_seed": SEED,
                "trace_path": str(files["trace"]),
                "trace_sha256": trace_hash,
                "controller_fingerprint_sha256": provenance[
                    "controller_fingerprint_sha256"
                ],
                "generalization_arm_fingerprint_sha256": provenance[
                    "generalization_arm_fingerprint_sha256"
                ],
                "metrics": recomputed,
                "events": events,
            }
        )
    actual_files = {path for path in demo_root.rglob("*") if path.is_file()}
    check(actual_files == expected_files, "demo root contains missing or unexpected files")
    if failures:
        raise VisualizationIntegrityError(
            "trajectory-demo integrity audit failed:\n- " + "\n- ".join(failures)
        )
    return {
        "schema_version": "stage4_trajectory_demo_integrity_audit_v1",
        "integrity_passed": True,
        "arm_count": 6,
        "expected_artifact_file_count": len(expected_files),
        "actual_artifact_file_count": len(actual_files),
        "all_arrays_finite": True,
        "all_frozen_metrics_recomputed_exactly": True,
        "all_completed": True,
        "all_reference_progress_fraction": 1.0,
        "all_event_counts_zero": True,
        "unique_output_paths": True,
        "overwrite_protection_enforced_by_runner": True,
        "generalization_config_sha256": matrix_hash,
        "metric_config_sha256": metric_hash,
        "gain_lock_sha256": expected_gain,
        "phase_manifest_path": str(phase_path),
        "phase_manifest_sha256": sha256_file(phase_path),
    }, records


def build_visualization_source_manifest(
    *,
    matrix_path: Path,
    statistical_root: Path,
    demo_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    matrix_path = Path(matrix_path).resolve()
    statistical_root = Path(statistical_root).resolve()
    demo_root = Path(demo_root).resolve()
    audit, demo_records = audit_trajectory_demo(
        matrix_path=matrix_path, demo_root=demo_root
    )
    matrix = load_generalization_matrix(matrix_path)
    _, _, metric_hash = load_metric_definitions(matrix, matrix_path)
    matrix_hash = sha256_file(matrix_path)
    source_root = report_root(matrix_path)
    statistical_phase_path = statistical_root / "phase_manifest.json"
    demo_phase_path = demo_root / "phase_manifest.json"
    statistical_phase = _load_json(statistical_phase_path)
    demo_phase = _load_json(demo_phase_path)
    if statistical_phase.get("evidence_category") != STATISTICAL_EVIDENCE_CATEGORY:
        raise VisualizationIntegrityError("statistical source category was relabelled")
    phases = {
        STATISTICAL_EVIDENCE_CATEGORY: (statistical_phase, statistical_phase_path),
        TRAJECTORY_DEMO_EVIDENCE_CATEGORY: (demo_phase, demo_phase_path),
    }
    phase_index: dict[tuple[str, str, str, int], tuple[dict[str, Any], Path, dict[str, Any]]] = {}
    for phase, path in phases.values():
        if phase.get("generalization_config_sha256") != matrix_hash:
            raise VisualizationIntegrityError(f"source matrix hash mismatch: {path}")
        if phase.get("metric_config_sha256") != metric_hash:
            raise VisualizationIntegrityError(f"source metric hash mismatch: {path}")
        for arm in phase["arms"]:
            key = (
                arm["patient_id"],
                arm["trajectory_id"],
                arm["controller_id"],
                int(arm["measurement_seed"]),
            )
            phase_index[key] = (phase, path, arm)

    expected_reuse_hashes = {
        "nominal_reference": "43c7503830edffa4a77b203a351a30a9f3c087ec452064a01864309fcc4c5eef",
        "height_moderate_plus_03pct_report_only": "1372d0855d9821c7f31c4f32584f113b67e760f11a2be4f96f056f13a5c97b93",
        "registered_moderate_anchor": "0e5090f4e53b6394239fa915cd1a831955d6a017cd874d66014a218dd344bcc5",
    }

    def item_for(patient: str, trajectory: str, controller: str, seed: int) -> dict[str, Any]:
        phase, path, arm = phase_index[(patient, trajectory, controller, seed)]
        item = _source_item(
            phase=phase,
            phase_path=path,
            phase_arm=arm,
            source_root=source_root,
            matrix_hash=matrix_hash,
            metric_hash=metric_hash,
        )
        if sha256_file(Path(item["source_trace_path"])) != item["source_trace_sha256"]:
            raise VisualizationIntegrityError(
                f"source trace SHA mismatch: {item['source_trace_path']}"
            )
        return item

    trajectory_dataset = []
    for patient in PATIENTS:
        for trajectory in TRAJECTORIES:
            item = item_for(patient, trajectory, ADAPTIVE, SEED)
            expected_category = (
                STATISTICAL_EVIDENCE_CATEGORY
                if trajectory == "registered_high_flexion_23s"
                else TRAJECTORY_DEMO_EVIDENCE_CATEGORY
            )
            if item["source_evidence_category"] != expected_category:
                raise VisualizationIntegrityError(
                    f"source category mismatch for {patient}/{trajectory}"
                )
            if trajectory == "registered_high_flexion_23s" and item[
                "source_trace_sha256"
            ] != expected_reuse_hashes[patient]:
                raise VisualizationIntegrityError(
                    f"frozen reused SHA mismatch for {patient}"
                )
            trajectory_dataset.append(item)

    main_adaptation = [
        item_for("registered_moderate_anchor", "registered_high_flexion_23s", controller, 64122)
        for controller in ("fixed_mpc_prior_only", ADAPTIVE)
    ]
    patient_generalization = [
        item_for(patient, "registered_high_flexion_23s", controller, SEED)
        for patient in PATIENTS
        for controller in CONTROLLERS
    ]
    trajectory_generalization = [
        item
        for item in trajectory_dataset
        if item["patient_id"] == "registered_moderate_anchor"
    ]
    manifest = {
        "schema_version": "stage4_report_visualization_source_manifest_v1",
        "evidence_category": VISUALIZATION_EVIDENCE_CATEGORY,
        "source_evidence_relabelled": False,
        "source_traces_copied": False,
        "descriptive_visualization_only": True,
        "generalization_config_sha256": matrix_hash,
        "metric_config_sha256": metric_hash,
        "trajectory_demo_integrity_audit": audit,
        "trajectory_generalization_dataset": {
            "patient_count": 3,
            "trajectory_count": 3,
            "case_count": 9,
            "controller_id": ADAPTIVE,
            "measurement_seed": SEED,
            "items": trajectory_dataset,
        },
        "media_sets": {
            "main_adaptation_comparison": {
                "layout": "fixed_mpc_left_adaptive_mpc_right",
                "items": main_adaptation,
            },
            "patient_generalization_comparison": {
                "layout": "three_patient_scenes_each_with_pdff_fixed_adaptive",
                "items": patient_generalization,
            },
            "trajectory_generalization_comparison": {
                "layout": "moderate_mixed_three_trajectory_panels",
                "items": trajectory_generalization,
            },
        },
        "media_contract": {
            "live_overlay": [
                "controller_or_trajectory_label",
                "instantaneous_tracking_error",
                "cuff_force",
                "combined_acceleration_descriptor",
                "prior_or_adaptive_state_where_relevant",
                "promotion_marker",
            ],
            "excluded_from_live_overlay": [
                "jerk",
                "cuff_moment",
                "robot_torque",
                "prediction_rmse",
            ],
            "end_summary": [
                "tracking_rmse",
                "maximum_tracking_error",
                "combined_acceleration_rms",
                "peak_cuff_force",
                "200_n_force_margin",
                "safety_event_count",
            ],
            "later_outputs": ["gif", "still_png", "timeseries_pdf"],
            "optional_output": "mp4_if_dependency_available",
        },
        "renderer_compatibility": {
            "main_adaptation_comparison": "supported_by_existing_same_case_multi_controller_loader",
            "patient_generalization_comparison": "supported_as_three_separate_same_case_three_controller_scenes",
            "trajectory_generalization_comparison": "blocked_for_single_three_panel_comparison_existing_loader_rejects_cross_trajectory_sources",
            "live_overlay_contract": "blocked_existing_overlay_includes_cuff_moment_and_only_static_acceleration_rms",
            "end_summary_contract": "blocked_existing_renderer_has_no_end_card",
        },
    }
    prepare_fresh_output_directory(output_dir)
    write_strict_json(Path(output_dir) / "visualization_source_manifest.json", manifest)
    return manifest
