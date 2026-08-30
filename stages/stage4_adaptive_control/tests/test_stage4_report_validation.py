from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.run_stage4_report_validation import _phase_cases
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.mpc import HumanSpaceMPC
from traction_mpc_stage4.report_validation import (
    ExternalPhaseReferenceClock,
    PDHumanActionController,
    candidate_mechanically_eligible,
    controller_applies_qualified_model,
    controller_factory,
    gain_candidates,
    gain_lock_payload,
    load_gain_lock,
    load_report_validation_matrix,
    patient_spec_for_id,
    prepare_fresh_output_directory,
    run_structural_smoke,
    select_gain_candidate,
    sha256_file,
    structural_smoke_gain_lock,
    write_gain_lock,
)
from traction_mpc_stage4.artifact_paths import resolve_stage_artifact
from traction_mpc_stage4.trajectory_excitation import trajectory_reference


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "configs" / "stage4_report_validation_matrix.json"


@pytest.fixture(scope="module")
def matrix() -> dict:
    return load_report_validation_matrix(MATRIX_PATH)


@pytest.fixture(scope="module")
def report_smoke(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    output_dir = tmp_path_factory.mktemp("report_validation") / "smoke"
    result = run_structural_smoke(
        matrix_path=MATRIX_PATH,
        output_dir=output_dir,
        duration_s=0.05,
    )
    return output_dir, result


def _candidate_record(candidate: dict, *, rmse: float, maximum: float, force: float) -> dict:
    return {
        **candidate,
        "termination_reason": "completed",
        "reference_progress_fraction": 1.0,
        "tracking_combined_rmse_deg": rmse,
        "tracking_max_abs_error_deg": maximum,
        "cuff_force_rms_n": force,
        "safety_events": {
            "force_gate_events": 0,
            "rom_event_samples": 0,
            "unintended_contact_pairs": [],
            "mujoco_warning_counts": {},
            "mpc_solver_failures": 0,
        },
    }


def test_exact_nine_candidate_grid(matrix: dict) -> None:
    candidates = gain_candidates(matrix)
    assert len(candidates) == 9
    assert [(item["kp_scale"], item["kd_scale"]) for item in candidates] == [
        (0.5, 0.5),
        (0.5, 1.0),
        (0.5, 1.5),
        (1.0, 0.5),
        (1.0, 1.0),
        (1.0, 1.5),
        (1.5, 0.5),
        (1.5, 1.0),
        (1.5, 1.5),
    ]
    np.testing.assert_allclose(
        candidates[4]["kp_tau_nm_per_rad"],
        [381.2577801496745, 27.815317728811202],
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        candidates[4]["kd_tau_nms_per_rad"],
        [59.30676580106047, 4.37097850024176],
        rtol=0.0,
        atol=1e-12,
    )


def test_gain_selection_is_mechanical_first_and_deterministic(matrix: dict) -> None:
    candidates = gain_candidates(matrix)
    records = [
        _candidate_record(candidates[0], rmse=1.0, maximum=2.0, force=30.0),
        _candidate_record(candidates[4], rmse=0.8, maximum=2.5, force=28.0),
        _candidate_record(candidates[8], rmse=0.8, maximum=2.5, force=28.0),
    ]
    invalid_but_numerically_best = _candidate_record(
        candidates[1], rmse=0.1, maximum=0.2, force=5.0
    )
    invalid_but_numerically_best["safety_events"]["force_gate_events"] = 1
    records.append(invalid_but_numerically_best)
    assert candidate_mechanically_eligible(invalid_but_numerically_best) is False
    selected = select_gain_candidate(records, tie_tolerance=1e-12)
    assert selected["candidate_id"] == candidates[4]["candidate_id"]

    for record in records:
        record["termination_reason"] = "allocated_cuff_force_gate"
    with pytest.raises(RuntimeError, match="no preregistered gain candidate"):
        select_gain_candidate(records, tie_tolerance=1e-12)


def test_gain_lock_hash_round_trip_and_tamper_detection(
    matrix: dict, tmp_path: Path
) -> None:
    candidate = gain_candidates(matrix)[4]
    record = _candidate_record(candidate, rmse=0.8, maximum=2.5, force=28.0)
    payload = gain_lock_payload(
        matrix_sha256=sha256_file(MATRIX_PATH),
        candidate_records=[record],
        selected=candidate,
        lock_kind="formal",
    )
    assert payload["formal_gain_lock"] is True
    assert payload["scientific_interpretation_permitted"] is False
    path = tmp_path / "frozen_pd_gains.json"
    artifact_hash = write_gain_lock(path, payload)
    loaded, loaded_hash = load_gain_lock(path, required_kind="formal")
    assert loaded == payload
    assert loaded_hash == artifact_hash
    assert path.with_suffix(".json.sha256").is_file()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_gain_lock(path, payload)

    tampered = json.loads(path.read_text())
    tampered["kp_tau_nm_per_rad"][0] += 1.0
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="payload hash mismatch"):
        load_gain_lock(path)


def test_pd_and_pdff_are_exact_human_space_laws(matrix: dict) -> None:
    candidate = gain_candidates(matrix)[4]
    q_ref = np.array([0.30, 0.55])
    dq_ref = np.array([0.10, -0.20])
    reference = CuffPoseReference(
        q_ref,
        dq_ref,
        np.array([0.4, -0.3]),
        _world_from_cuff(q_ref),
    )
    reference_fn = lambda _: reference
    state = np.array([0.25, 0.50, 0.05, -0.10])
    expected_feedback = np.asarray(candidate["kp_tau_nm_per_rad"]) * (
        q_ref - state[:2]
    ) + np.asarray(candidate["kd_tau_nms_per_rad"]) * (dq_ref - state[2:])

    pd = controller_factory("pd_feedback", candidate)()
    action, diagnostics = pd.solve(state, 0.0, reference_fn, object())
    np.testing.assert_allclose(action, expected_feedback)
    np.testing.assert_allclose(diagnostics["nominal_feedforward_action_nm"], 0.0)

    class PriorModel:
        @staticmethod
        def inverse_dynamics(*_: object) -> np.ndarray:
            return np.array([3.0, -4.0])

    pdff = controller_factory("pd_nominal_inverse_dynamics_ff", candidate)()
    action_ff, diagnostics_ff = pdff.solve(
        state, 0.0, reference_fn, PriorModel()
    )
    np.testing.assert_allclose(action_ff, expected_feedback + [3.0, -4.0])
    np.testing.assert_allclose(
        diagnostics_ff["nominal_feedforward_action_nm"], [3.0, -4.0]
    )
    assert pd.kp.tolist() == pdff.kp.tolist()
    assert pd.kd.tolist() == pdff.kd.tolist()


def test_four_controller_definitions_and_beta_semantics(matrix: dict) -> None:
    lock = structural_smoke_gain_lock(matrix, sha256_file(MATRIX_PATH))
    assert isinstance(controller_factory("pd_feedback", lock)(), PDHumanActionController)
    assert isinstance(
        controller_factory("pd_nominal_inverse_dynamics_ff", lock)(),
        PDHumanActionController,
    )
    assert isinstance(controller_factory("fixed_mpc_prior_only", lock)(), HumanSpaceMPC)
    assert isinstance(controller_factory("trusted_adaptive_mpc", lock)(), HumanSpaceMPC)
    assert controller_applies_qualified_model("fixed_mpc_prior_only") is False
    assert controller_applies_qualified_model("trusted_adaptive_mpc") is True


def test_external_clock_hash_and_controller_independence(matrix: dict) -> None:
    trajectory_id = "registered_high_flexion_23s"
    trajectory_config = ROOT / matrix["source_artifacts"]["trajectory_config"]["path"]
    suite = json.loads(trajectory_config.read_text())
    trajectory = next(
        item for item in suite["cases"] if item["trajectory_id"] == trajectory_id
    )
    source = matrix["source_artifacts"]["shared_reference_phase_trace"]
    clock = ExternalPhaseReferenceClock(
        lambda time_s: trajectory_reference(trajectory, time_s),
        source_path=resolve_stage_artifact(ROOT, source["path"]),
        expected_sha256=source["sha256"],
        source_duration_s=23.0,
        trajectory_duration_s=23.0,
    )
    before = [clock.phase_time_s(value) for value in (0.0, 0.1, 1.0, 5.0)]
    for value in (0.0, 0.1, 1.0, 5.0):
        clock.update_from_estimator(value, object(), {"accepted": True}, {})
    after = [clock.phase_time_s(value) for value in (0.0, 0.1, 1.0, 5.0)]
    np.testing.assert_array_equal(before, after)
    assert clock.summary(5.0)["controller_confidence_affects_phase"] is False
    assert clock.summary(5.0)["reads_source_keys"] == [
        "time_s",
        "reference_phase_time_s",
    ]


def test_report_only_geometry_changes_lengths_only(matrix: dict) -> None:
    spec, source = patient_spec_for_id(
        matrix, MATRIX_PATH, "height_moderate_plus_03pct_report_only"
    )
    human = spec.build_human()
    assert source == "report_validation_only"
    assert human.height_m == pytest.approx(1.03 * HUMAN.height_m)
    assert human.thigh_length_m == pytest.approx(1.03 * HUMAN.thigh_length_m)
    assert human.shank_length_m == pytest.approx(1.03 * HUMAN.shank_length_m)
    assert human.body_mass_kg == HUMAN.body_mass_kg
    assert human.passive_stiffness_nm_rad == HUMAN.passive_stiffness_nm_rad
    assert human.passive_damping_nms_rad == HUMAN.passive_damping_nms_rad
    assert human.q_rest_rad == HUMAN.q_rest_rad
    assert human.sleeve_center_m == pytest.approx(1.03 * HUMAN.sleeve_center_m)


def test_matrix_phase_plans_are_exact_and_exclude_reused_demo(matrix: dict) -> None:
    benchmark = _phase_cases(matrix, "benchmark")
    demo = _phase_cases(matrix, "demo")
    assert len(benchmark) * 4 == 16
    assert len(demo) * 4 == 8
    assert {item["case_id"] for item in demo} == {
        "isolated_geometry_hip_dominant",
        "moderate_mixed_moderate_rom",
    }
    assert all(
        item["evidence_category"] == "report_validation_scientific_baseline"
        for item in benchmark
    )
    assert all(
        item["evidence_category"] == "visualization_demo_only" for item in demo
    )


def test_structural_smoke_covers_all_arms_and_has_no_state_leakage(
    report_smoke: tuple[Path, dict],
) -> None:
    output_dir, result = report_smoke
    assert result["scientific_interpretation_permitted"] is False
    assert result["formal_gain_selection_executed"] is False
    assert result["scientific_benchmark_executed"] is False
    assert result["demo_experiment_executed"] is False
    assert result["all_finite"] is True
    assert len(result["cases"]) == 2
    assert len(result["arms"]) == 8
    assert (output_dir / "smoke_manifest.json").is_file()

    for case in result["cases"]:
        arms = [item for item in result["arms"] if item["case_id"] == case["case_id"]]
        assert len(arms) == 4
        assert len({item["reference_trace_sha256"] for item in arms}) == 1
        assert len({item["measurement_schedule_sha256"] for item in arms}) == 1
        assert len({item["sensor_realization_definition_sha256"] for item in arms}) == 1
        assert len({tuple(item["initial_human_q_deg"]) for item in arms}) == 1
        assert len({tuple(item["initial_robot_q_rad"]) for item in arms}) == 1
        assert all(item["allocation_residual_peak_nm"] < 1e-8 for item in arms)
        for item in arms:
            np.testing.assert_allclose(
                item["initial_control_beta"], nominal_base_parameters(HUMAN)
            )

    fixed = [
        item for item in result["arms"] if item["controller_id"] == "fixed_mpc_prior_only"
    ]
    adaptive = [
        item for item in result["arms"] if item["controller_id"] == "trusted_adaptive_mpc"
    ]
    assert all(item["apply_qualified_model_to_control"] is False for item in fixed)
    assert all(item["apply_qualified_model_to_control"] is True for item in adaptive)

    pd_manifests = []
    for case in result["cases"]:
        for controller in ("pd_feedback", "pd_nominal_inverse_dynamics_ff"):
            path = (
                output_dir
                / case["case_id"]
                / controller
                / f"{controller}_manifest.json"
            )
            pd_manifests.append(json.loads(path.read_text()))
    assert len({item["gain_lock_sha256"] for item in pd_manifests}) == 1


def test_output_root_is_unique_and_overwrite_is_rejected(
    matrix: dict, tmp_path: Path
) -> None:
    path = tmp_path / "fresh"
    prepare_fresh_output_directory(path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_fresh_output_directory(path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_structural_smoke(
            matrix_path=MATRIX_PATH,
            output_dir=path,
            duration_s=0.05,
        )
    with pytest.raises(ValueError, match="structural smoke duration"):
        run_structural_smoke(
            matrix_path=MATRIX_PATH,
            output_dir=tmp_path / "too_long",
            duration_s=0.6,
        )
