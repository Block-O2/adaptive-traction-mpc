from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from traction_mpc_stage4.artifact_paths import resolve_stage_artifact


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "configs" / "stage4_report_generalization_matrix.json"
METRICS_PATH = ROOT / "configs" / "stage4_report_generalization_metrics.json"
SPEC_PATH = ROOT / "docs" / "research" / "STAGE4_REPORT_GENERALIZATION_SPEC.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generalization_sources_and_frozen_gain_lock_are_exact() -> None:
    matrix = _load(MATRIX_PATH)
    assert matrix["schema_version"] == (
        "stage4_report_generalization_matrix_v1_demo_reuse_amendment"
    )
    assert matrix["design_status"] == (
        "approved_prospective_demo_reuse_amendment_no_formal_execution"
    )
    assert matrix["preregistered_before_any_new_generalization_result"] is True
    amendment = matrix["prospective_amendment"]
    assert amendment["original_matrix_sha256"] == (
        "66cf1757c083cfdc9fa1868e18cbc48b9fe9eb51c6971e8cea4b0adc10155e90"
    )
    assert amendment["scientific_36_arm_matrix_changed"] is False
    assert amendment["visualization_evidence_category"] == (
        "professor_report_visualization"
    )
    assert matrix["frozen_start"] == {
        "tag": "stage4-robustness-final-v1",
        "commit": "cc04765761d08ffaf1914f0236f0201d9c7e1475",
        "branch": "codex/report-validation",
        "authoritative_stage4_mutation_allowed": False,
        "controller_retuning_allowed": False,
    }
    for key in (
        "report_validation_v2_config",
        "frozen_v2_gain_lock",
        "patient_config",
        "trajectory_config",
        "external_reference_clock",
    ):
        source = matrix["source_artifacts"][key]
        path = resolve_stage_artifact(ROOT, source["path"])
        assert path.is_file()
        assert _sha256(path) == source["sha256"]
    lock = matrix["source_artifacts"]["frozen_v2_gain_lock"]
    assert lock["selected_candidate_id"] == "kp_1.5__kd_0.5"
    assert lock["retuning_allowed"] is False
    lock_payload = _load(resolve_stage_artifact(ROOT, lock["path"]))
    assert lock_payload["formal_gain_lock"] is True
    assert lock_payload["selected_candidate_id"] == lock["selected_candidate_id"]
    assert lock_payload["selected_kp_scale"] == 1.5
    assert lock_payload["selected_kd_scale"] == 0.5
    assert lock_payload["payload_sha256"] == lock["payload_sha256"]


def test_main_matrix_is_exactly_four_by_three_by_three_without_pure_pd() -> None:
    matrix = _load(MATRIX_PATH)
    arms = matrix["main_statistical_matrix"]["arms"]
    patients = [item["patient_id"] for item in matrix["patients"]]
    controllers = [item["controller_id"] for item in matrix["controllers"]]
    seeds = matrix["shared_contract"]["measurement_seeds"]
    assert patients == [
        "nominal_reference",
        "mass_mild_plus_05pct",
        "height_moderate_plus_03pct_report_only",
        "registered_moderate_anchor",
    ]
    assert controllers == [
        "pd_nominal_inverse_dynamics_ff",
        "fixed_mpc_prior_only",
        "trusted_adaptive_mpc",
    ]
    assert seeds == [44104, 54113, 64122]
    assert "pd_feedback" not in controllers
    expected = set(itertools.product(patients, controllers, seeds))
    observed = {
        (arm["patient_id"], arm["controller_id"], arm["measurement_seed"])
        for arm in arms
    }
    assert observed == expected
    assert len(arms) == len(observed) == 36
    assert [arm["arm_id"] for arm in arms] == [
        f"G{index:02d}" for index in range(1, 37)
    ]
    assert matrix["main_statistical_matrix"]["trajectory_id"] == (
        "registered_high_flexion_23s"
    )


def test_patient_mechanisms_are_existing_or_explicitly_report_only() -> None:
    matrix = _load(MATRIX_PATH)
    patient_source = _load(
        ROOT / matrix["source_artifacts"]["patient_config"]["path"]
    )
    existing = {item["case_id"] for item in patient_source["cases"]}
    by_id = {item["patient_id"]: item for item in matrix["patients"]}
    assert {
        "nominal_reference",
        "mass_mild_plus_05pct",
        "registered_moderate_anchor",
    } <= existing
    geometry = by_id["height_moderate_plus_03pct_report_only"]
    assert geometry["patient_id"] not in existing
    assert geometry["stage4_canonical_evidence"] is False
    assert geometry["definition"] == {
        "height_scale": 1.03,
        "body_mass_scale": 1.0,
        "thigh_com_scale": 1.0,
        "shank_com_scale": 1.0,
        "passive_stiffness_scale": [1.0, 1.0],
        "passive_damping_scale": [1.0, 1.0],
        "rest_offset_deg": [0.0, 0.0],
        "sleeve_center_scale": 1.0,
    }
    assert "complementary" in by_id["registered_moderate_anchor"][
        "selection_reason"
    ]


def test_reuse_classification_respects_evidence_semantics() -> None:
    matrix = _load(MATRIX_PATH)
    audit = matrix["reuse_audit"]
    assert "evidence_semantics" in audit["required_exact_match_fields"]
    assert audit["baseline_candidate_matches_before_evidence_semantics_check"] == 9
    assert audit["reusable_rollout_count"] == 0
    assert audit["new_statistical_rollout_count"] == 36
    assert audit["source_artifacts_remain_read_only"] is True
    assert matrix["evidence_categories"]["stage4_authoritative_historical"][
        "mutable"
    ] is False
    assert matrix["evidence_categories"]["report_validation_baseline"][
        "mutable"
    ] is False


def test_demo_matrices_are_exact_and_separate() -> None:
    matrix = _load(MATRIX_PATH)
    patient_demo = matrix["patient_demo_matrix"]
    trajectory_demo = matrix["trajectory_demo_matrix"]
    assert patient_demo["measurement_seed"] == 44104
    assert patient_demo["trajectory_id"] == "registered_high_flexion_23s"
    assert len(patient_demo["arms"]) == patient_demo["logical_arm_count"] == 12
    assert patient_demo["new_rollout_count"] == 0
    assert patient_demo["reused_from_statistical_matrix"] == 12
    assert trajectory_demo["measurement_seed"] == 44104
    assert trajectory_demo["controller_id"] == "trusted_adaptive_mpc"
    assert len(trajectory_demo["arms"]) == trajectory_demo["logical_arm_count"] == 9
    assert trajectory_demo["new_rollout_count"] == 6
    assert trajectory_demo["reused_from_statistical_matrix"] == 3
    assert len(trajectory_demo["new_execution_arms"]) == 6
    assert all(
        item["trajectory_id"] != "registered_high_flexion_23s"
        for item in trajectory_demo["new_execution_arms"]
    )
    expected_trajectories = {
        "registered_high_flexion_23s",
        "moderate_rom_23s",
        "hip_dominant_low_knee_23s",
    }
    assert {arm["trajectory_id"] for arm in trajectory_demo["arms"]} == (
        expected_trajectories
    )


def test_metric_schema_freezes_motion_processing_and_descriptive_statistics() -> None:
    metrics = _load(METRICS_PATH)
    motion = metrics["motion_quality"]
    assert motion["saved_source_period_s"] == 0.005
    assert motion["subsample_stride"] == 4
    assert motion["subsample_phase_index"] == 0
    derivative = metrics["motion_quality"]["offline_derivative_method"]
    assert derivative == {
        "name": "fixed_savitzky_golay_velocity_derivatives",
        "implementation_contract": "scipy.signal.savgol_filter",
        "window_length_samples": 11,
        "window_duration_s": 0.22,
        "polynomial_order": 3,
        "boundary_mode": "interp",
        "acceleration_derivative_order": 1,
        "jerk_derivative_order": 2,
        "delta_s": 0.02,
        "additional_controller_specific_filtering": False,
        "causal_runtime_use": False,
        "note": (
            "one frozen offline differentiation method is applied identically "
            "to every saved causal velocity estimate"
        ),
    }
    assert metrics["interaction_and_constraints"]["cuff_force_rate"][
        "included"
    ] is False
    assert metrics["interaction_and_constraints"]["cuff_surface_proxy"][
        "included_as_primary_metric"
    ] is False
    generalization = metrics["generalization"]
    assert generalization["composite_generalization_score"] is False
    assert len(generalization["required_metrics"]) >= 6
    summary = metrics["cell_summary_across_three_seeds"]
    assert summary["statistics"] == [
        "arithmetic_mean",
        "sample_standard_deviation_ddof_1",
        "minimum",
        "maximum",
    ]
    assert "no_significance_tests" in summary["inference"]


def test_cost_counts_and_execution_stop_are_explicit() -> None:
    matrix = _load(MATRIX_PATH)
    cost = matrix["cost_estimate"]
    assert cost["total_new_rollouts"] == (
        cost["statistical_new_rollouts"]
        + cost["patient_demo_new_rollouts"]
        + cost["trajectory_demo_new_rollouts"]
    ) == 42
    assert cost["statistical_simulated_seconds"] == 36 * 32.0
    assert cost["all_planned_simulated_seconds"] == 42 * 32.0
    assert matrix["execution_authorization"] == {
        "formal_statistical_runs_now": False,
        "demo_simulations_now": False,
        "media_rendering_now": False,
        "infrastructure_implementation_authorized": True,
        "required_before_execution": [
            "user_approval_of_this_preregistration",
            "report_only_geometry_patient_resolution_implemented_and_schema_validated",
            "new_output_roots_confirmed_absent",
            "new_generalization_config_and_controller_fingerprints_frozen",
        ],
    }


def test_spec_preserves_scientific_claim_boundaries() -> None:
    spec = " ".join(SPEC_PATH.read_text(encoding="utf-8").lower().split())
    for text in (
        "no generalization formal rollout",
        "no controller is retuned",
        "motion-smoothness proxies only",
        "not pressure, tissue loading, comfort, or safety",
        "no composite generalization score",
        "no significance test",
        "zero old arms are classified reusable",
        "42 unique executions",
    ):
        assert text in spec
