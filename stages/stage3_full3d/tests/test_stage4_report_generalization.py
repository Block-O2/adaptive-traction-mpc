from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

import traction_mpc_stage4.report_generalization as generalization_module
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.report_generalization import (
    build_generalization_summary,
    descriptive_summary,
    load_generalization_matrix,
    load_metric_definitions,
    matched_nominal_degradation,
    run_generalization_phase,
    run_generalization_structural_smoke,
)
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    patient_spec_for_id,
    prepare_fresh_output_directory,
    sha256_file,
)
from traction_mpc_stage4.report_validation_renderer import (
    GENERALIZATION_CONTROLLER_ORDER,
    render_generalization_comparison,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "configs" / "stage4_report_generalization_matrix.json"
GAIN_LOCK_PATH = (
    ROOT
    / "results"
    / "stage4_report_validation_gain_tuning_formal_v2_coupled_pd"
    / "frozen_pd_gains.json"
)


@pytest.fixture(scope="module")
def generalization_matrix() -> dict:
    return load_generalization_matrix(MATRIX_PATH)


@pytest.fixture(scope="module")
def generalization_smoke(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict]:
    output = tmp_path_factory.mktemp("generalization_smoke") / "smoke"
    result = run_generalization_structural_smoke(
        matrix_path=MATRIX_PATH,
        gain_lock_path=GAIN_LOCK_PATH,
        output_dir=output,
        duration_s=0.25,
    )
    return output, result


def test_amended_matrix_keeps_36_and_executes_only_six_demo_arms(
    generalization_matrix: dict,
) -> None:
    assert len(generalization_matrix["main_statistical_matrix"]["arms"]) == 36
    demo = generalization_matrix["trajectory_demo_matrix"]
    assert len(demo["arms"]) == 9
    assert len(demo["new_execution_arms"]) == 6
    assert demo["reused_from_statistical_matrix"] == 3
    assert generalization_matrix["patient_demo_matrix"][
        "reused_from_statistical_matrix"
    ] == 12
    assert generalization_matrix["cost_estimate"]["total_new_rollouts"] == 42


def test_report_only_geometry_uses_validation_only_definition(
    generalization_matrix: dict,
) -> None:
    source = generalization_matrix["source_artifacts"][
        "report_validation_v2_config"
    ]
    validation_path = ROOT / source["path"]
    validation = load_report_validation_matrix(validation_path)
    patient, patient_source = patient_spec_for_id(
        validation,
        validation_path,
        "height_moderate_plus_03pct_report_only",
    )
    human = patient.build_human()
    assert patient_source == "report_validation_only"
    assert human.height_m == pytest.approx(1.03 * HUMAN.height_m)
    assert human.thigh_length_m == pytest.approx(1.03 * HUMAN.thigh_length_m)
    assert human.shank_length_m == pytest.approx(1.03 * HUMAN.shank_length_m)
    assert human.body_mass_kg == HUMAN.body_mass_kg
    assert human.passive_stiffness_nm_rad == HUMAN.passive_stiffness_nm_rad
    assert human.passive_damping_nms_rad == HUMAN.passive_damping_nms_rad


def test_structural_smoke_factor_injection_freshness_and_semantics(
    generalization_smoke: tuple[Path, dict],
) -> None:
    output, smoke = generalization_smoke
    assert smoke["formal_execution"] is False
    assert smoke["scientific_interpretation_permitted"] is False
    assert smoke["report_only_geometry_isolated"] is True
    assert smoke["matched_exogenous_inputs_identical"] is True
    assert smoke["fresh_state_per_arm"] is True
    assert smoke["all_finite"] is True
    assert smoke["deterministic_metric_extraction"] is True
    assert len(smoke["arms"]) == 4
    matched = [
        item for item in smoke["arms"] if item["case_id"] == "matched_nominal_group"
    ]
    assert [item["controller_id"] for item in matched] == list(
        GENERALIZATION_CONTROLLER_ORDER
    )
    assert len({item["reference_trace_sha256"] for item in matched}) == 1
    assert len({item["measurement_schedule_sha256"] for item in matched}) == 1
    assert len({tuple(item["initial_human_q_deg"]) for item in matched}) == 1
    assert len({tuple(item["initial_robot_q_rad"]) for item in matched}) == 1
    pdff, fixed, adaptive = matched
    assert pdff["gain_lock_sha256"] == sha256_file(GAIN_LOCK_PATH)
    assert fixed["apply_qualified_model_to_control"] is False
    assert adaptive["apply_qualified_model_to_control"] is True
    for item in smoke["arms"]:
        metrics = item["metrics"]
        assert metrics["motion_descriptor_sample_period_s"] == 0.02
        assert metrics["motion_descriptor_source_indices"] == "0::4"
        assert metrics["motion_descriptor_sample_count"] >= 11
        assert metrics["cuff_force_rate_included"] is False
        assert metrics["cuff_surface_proxy_primary_metric"] is False
        assert metrics["minimum_force_gate_margin_n"] == pytest.approx(
            200.0 - metrics["cuff_force_peak_n"]
        )
        assert Path(item["trace_path"]).is_file()
        assert sha256_file(Path(item["trace_path"])) == item["trace_sha256"]
    assert (output / "phase_manifest.json").is_file()


def test_savgol_metric_output_is_deterministic_and_finite(
    generalization_smoke: tuple[Path, dict], generalization_matrix: dict
) -> None:
    _, smoke = generalization_smoke
    definitions, _, _ = load_metric_definitions(
        generalization_matrix, MATRIX_PATH
    )
    method = definitions["motion_quality"]["offline_derivative_method"]
    assert method["window_length_samples"] == 11
    assert method["polynomial_order"] == 3
    assert method["boundary_mode"] == "interp"
    assert method["delta_s"] == 0.02
    assert method["acceleration_derivative_order"] == 1
    assert method["jerk_derivative_order"] == 2
    scalar_names = (
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
        "cuff_force_rms_n",
        "cuff_force_peak_n",
        "cuff_force_p95_n",
    )
    for item in smoke["arms"]:
        assert all(np.isfinite(item["metrics"][name]) for name in scalar_names)


def _synthetic_records(definitions: dict) -> list[dict]:
    names = definitions["generalization"]["required_metrics"]
    records = []
    patients = (
        "nominal_reference",
        "mass_mild_plus_05pct",
        "height_moderate_plus_03pct_report_only",
        "registered_moderate_anchor",
    )
    controllers = GENERALIZATION_CONTROLLER_ORDER
    seeds = (44104, 54113, 64122)
    for patient_index, patient in enumerate(patients):
        for controller_index, controller in enumerate(controllers):
            for seed_index, seed in enumerate(seeds):
                base = 1.0 + controller_index + 0.1 * seed_index
                metrics = {
                    name: base + 0.25 * patient_index for name in names
                }
                records.append(
                    {
                        "patient_id": patient,
                        "controller_id": controller,
                        "measurement_seed": seed,
                        "metrics": metrics,
                    }
                )
    return records


def test_degradation_and_n3_sample_sd_semantics(
    generalization_matrix: dict,
) -> None:
    definitions, _, _ = load_metric_definitions(
        generalization_matrix, MATRIX_PATH
    )
    records = _synthetic_records(definitions)
    names = definitions["generalization"]["required_metrics"]
    degradation = matched_nominal_degradation(records, metric_names=names)
    moderate = next(
        item
        for item in degradation
        if item["patient_id"] == "registered_moderate_anchor"
        and item["controller_id"] == "fixed_mpc_prior_only"
        and item["measurement_seed"] == 44104
    )
    assert moderate["metrics"][names[0]]["absolute_delta"] == pytest.approx(0.75)
    assert moderate["metrics"][names[0]]["relative_degradation"] == pytest.approx(
        0.75 / 2.0
    )
    aggregate = descriptive_summary([1.0, 2.0, 3.0])
    assert aggregate == {
        "count": 3,
        "mean": 2.0,
        "sample_sd_ddof_1": 1.0,
        "minimum": 1.0,
        "maximum": 3.0,
    }
    summary = build_generalization_summary(records, definitions)
    assert summary["descriptive_only_n_equals_3"] is True
    assert summary["significance_tests_performed"] is False
    assert summary["composite_score_created"] is False
    assert len(summary["absolute_cell_summaries"]) == 12
    assert all(
        item["seed_count"] == 3 for item in summary["absolute_cell_summaries"]
    )


def test_renderer_reuses_trace_by_verified_sha_and_separates_category(
    generalization_smoke: tuple[Path, dict], tmp_path: Path
) -> None:
    output, smoke = generalization_smoke
    case_dir = output / "matched_nominal_group"
    render_dir = tmp_path / "render"
    manifest = render_generalization_comparison(
        case_dir=case_dir,
        source_phase_manifest_path=output / "phase_manifest.json",
        generalization_matrix_path=MATRIX_PATH,
        output_dir=render_dir,
        fps=4,
        max_frames=2,
    )
    assert manifest["evidence_category"] == "professor_report_visualization"
    assert manifest["source_evidence_relabelled"] is False
    assert manifest["controllers"] == list(GENERALIZATION_CONTROLLER_ORDER)
    assert len(manifest["source_artifacts"]) == 3
    for source in manifest["source_artifacts"]:
        assert source["source_evidence_category"] == smoke["evidence_category"]
        assert sha256_file(Path(source["trace_path"])) == source["trace_sha256"]
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        render_generalization_comparison(
            case_dir=case_dir,
            source_phase_manifest_path=output / "phase_manifest.json",
            generalization_matrix_path=MATRIX_PATH,
            output_dir=render_dir,
            max_frames=1,
        )

    tampered = deepcopy(smoke)
    tampered["arms"][0]["trace_sha256"] = "0" * 64
    bad_manifest = tmp_path / "bad_phase_manifest.json"
    bad_manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="source trace SHA-256 mismatch"):
        render_generalization_comparison(
            case_dir=case_dir,
            source_phase_manifest_path=bad_manifest,
            generalization_matrix_path=MATRIX_PATH,
            output_dir=tmp_path / "bad_render",
            max_frames=1,
        )


def test_output_overwrite_protection(
    generalization_smoke: tuple[Path, dict], tmp_path: Path
) -> None:
    output, _ = generalization_smoke
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_generalization_structural_smoke(
            matrix_path=MATRIX_PATH,
            gain_lock_path=GAIN_LOCK_PATH,
            output_dir=output,
            duration_s=0.25,
        )
    fresh = tmp_path / "fresh"
    prepare_fresh_output_directory(fresh)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_fresh_output_directory(fresh)


def test_formal_phase_planning_writes_exact_36_and_6_without_simulation(
    generalization_matrix: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definitions, _, metric_hash = load_metric_definitions(
        generalization_matrix, MATRIX_PATH
    )

    def fake_context(*_: object) -> tuple:
        return (
            {},
            MATRIX_PATH,
            {"gain_definition": "constant_nominal_inertia_derived_coupled_torque_pd_v2"},
            sha256_file(GAIN_LOCK_PATH),
            definitions,
            metric_hash,
        )

    def fake_run_arm(**kwargs: object) -> dict:
        controller = str(kwargs["controller_id"])
        metrics = {
            name: 1.0 for name in definitions["generalization"]["required_metrics"]
        }
        return {
            "trace_path": str(Path(kwargs["output_dir"]) / f"{controller}_trace.npz"),
            "trace_sha256": "1" * 64,
            "provenance": {"controller_fingerprint_sha256": "2" * 64},
            "generalization_arm_fingerprint_sha256": "3" * 64,
            "summary": {"termination_reason": "completed"},
            "generalization_metrics": metrics,
        }

    monkeypatch.setattr(generalization_module, "_validation_context", fake_context)
    monkeypatch.setattr(generalization_module, "_run_arm", fake_run_arm)
    statistical_dir = tmp_path / "statistical"
    statistical = run_generalization_phase(
        matrix_path=MATRIX_PATH,
        gain_lock_path=GAIN_LOCK_PATH,
        phase="statistical",
        output_dir=statistical_dir,
    )
    assert statistical["arm_count"] == 36
    aggregate = json.loads(
        (statistical_dir / "generalization_summary.json").read_text()
    )
    assert len(aggregate["absolute_cell_summaries"]) == 12
    assert all(item["seed_count"] == 3 for item in aggregate["absolute_cell_summaries"])

    trajectory = run_generalization_phase(
        matrix_path=MATRIX_PATH,
        gain_lock_path=GAIN_LOCK_PATH,
        phase="trajectory-demo",
        output_dir=tmp_path / "trajectory",
    )
    assert trajectory["arm_count"] == 6
    assert all(
        item["trajectory_id"] != "registered_high_flexion_23s"
        for item in trajectory["arms"]
    )
