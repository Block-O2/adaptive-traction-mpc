from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage3.human import (
    HUMAN,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
    mass_matrix,
)
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff
from traction_mpc_stage4.mpc import HumanSpaceMPC
from traction_mpc_stage4.report_validation import (
    MATRIX_SCHEMA_VERSION_V1,
    MATRIX_SCHEMA_VERSION_V2,
    PDHumanActionController,
    canonical_json_sha256,
    controller_applies_qualified_model,
    controller_factory,
    controller_fingerprint_payload,
    gain_candidates,
    gain_lock_payload,
    load_gain_lock,
    load_report_validation_matrix,
    run_coupled_pd_gain_smoke,
    sha256_file,
    write_gain_lock,
)


ROOT = Path(__file__).resolve().parents[1]
V1_MATRIX_PATH = ROOT / "configs" / "stage4_report_validation_matrix.json"
V2_MATRIX_PATH = (
    ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
)
V1_STATUS_PATH = (
    ROOT
    / "results"
    / "negative_evidence"
    / "pd_gain_selection_v1"
    / "gain_selection_status.json"
)
V1_MATRIX_SHA256 = "128fbadbedb5d204f767eeb126c26d13f2d81c410646689d5a1f2be4594886c2"
V1_STATUS_SHA256 = "e78cc4b6e5ed9fa8641d8232410298ada2b9dff90ce3a06fcea739b5aa0ef61f"


@pytest.fixture(scope="module")
def v2_matrix() -> dict:
    return load_report_validation_matrix(V2_MATRIX_PATH)


def test_v1_contract_and_failed_formal_evidence_are_immutable() -> None:
    assert sha256_file(V1_MATRIX_PATH) == V1_MATRIX_SHA256
    assert sha256_file(V1_STATUS_PATH) == V1_STATUS_SHA256
    status = json.loads(V1_STATUS_PATH.read_text(encoding="utf-8"))
    assert status["status"] == "no_mechanically_eligible_candidate"
    assert status["formal_gain_lock_created"] is False
    assert not (V1_STATUS_PATH.parent / "frozen_pd_gains.json").exists()
    v1_matrix = load_report_validation_matrix(V1_MATRIX_PATH)
    historical_hashes = {
        item["candidate_id"]: item["candidate_definition_sha256"]
        for item in status["candidate_records"]
    }
    assert {
        item["candidate_id"]: canonical_json_sha256(item)
        for item in gain_candidates(v1_matrix)
    } == historical_hashes


def test_v2_matrix_records_prospective_amendment(v2_matrix: dict) -> None:
    assert v2_matrix["schema_version"] == MATRIX_SCHEMA_VERSION_V2
    amendment = v2_matrix["amendment"]
    assert amendment["terminology"] == (
        "constant nominal-inertia-derived coupled torque PD"
    )
    assert amendment["runtime_mass_matrix_evaluation"] is False
    assert amendment["runtime_dynamics_model_in_pd"] is False
    assert amendment[
        "defined_prospectively_before_any_v2_formal_gain_tuning_or_benchmark_result"
    ] is True
    assert amendment["v1_formal_gain_selection"]["status_sha256"] == (
        V1_STATUS_SHA256
    )
    assert v2_matrix["planned_output_roots"]["gain_tuning"] == (
        "results/stage4_report_validation_gain_tuning_formal_v2_coupled_pd"
    )


def test_coupled_gain_matrices_exactly_preserve_nominal_computed_acceleration(
    v2_matrix: dict,
) -> None:
    tuning = v2_matrix["gain_tuning"]
    q0 = np.radians(tuning["initial_q_deg"])
    nominal_mass = mass_matrix(q0, HUMAN)
    kp = np.asarray(tuning["base_kp_tau_matrix_nm_per_rad"])
    kd = np.asarray(tuning["base_kd_tau_matrix_nms_per_rad"])
    expected_kp = nominal_mass @ np.diag(TRACKING_KP_RAD_S2_PER_RAD)
    expected_kd = nominal_mass @ np.diag(TRACKING_KD_RAD_S2_PER_RAD_S)
    assert kp.shape == kd.shape == (2, 2)
    np.testing.assert_allclose(kp, expected_kp, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(kd, expected_kd, rtol=0.0, atol=1e-12)
    assert np.all(np.abs(kp[[0, 1], [1, 0]]) > 0.0)
    assert np.all(np.abs(kd[[0, 1], [1, 0]]) > 0.0)

    error_pairs = (
        (np.array([0.03, -0.07]), np.array([0.4, -0.2])),
        (np.array([-0.11, 0.02]), np.array([-0.3, 0.8])),
        (np.array([0.09, 0.13]), np.array([1.2, -0.6])),
    )
    for q_error, dq_error in error_pairs:
        matrix_pd = kp @ q_error + kd @ dq_error
        computed_acceleration_feedback = nominal_mass @ (
            np.diag(TRACKING_KP_RAD_S2_PER_RAD) @ q_error
            + np.diag(TRACKING_KD_RAD_S2_PER_RAD_S) @ dq_error
        )
        np.testing.assert_allclose(
            matrix_pd,
            computed_acceleration_feedback,
            rtol=0.0,
            atol=1e-12,
        )


def test_v2_grid_is_exactly_nine_scaled_matrix_candidates(v2_matrix: dict) -> None:
    candidates = gain_candidates(v2_matrix)
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
    base = candidates[4]
    assert base["gain_definition"] == (
        "constant_nominal_inertia_derived_coupled_torque_pd_v2"
    )
    assert np.asarray(base["kp_tau_matrix_nm_per_rad"]).shape == (2, 2)
    assert np.asarray(base["kd_tau_matrix_nms_per_rad"]).shape == (2, 2)


def test_v2_gain_lock_preserves_coupled_matrices(
    v2_matrix: dict, tmp_path: Path
) -> None:
    selected = gain_candidates(v2_matrix)[4]
    record = {
        **selected,
        "termination_reason": "completed",
        "reference_progress_fraction": 1.0,
        "tracking_combined_rmse_deg": 1.0,
        "tracking_max_abs_error_deg": 2.0,
        "cuff_force_rms_n": 50.0,
        "safety_events": {},
    }
    payload = gain_lock_payload(
        matrix_sha256=sha256_file(V2_MATRIX_PATH),
        candidate_records=[record],
        selected=selected,
        lock_kind="formal",
    )
    assert payload["schema_version"] == (
        "stage4_report_validation_pd_gain_lock_v2_coupled_pd"
    )
    assert "kp_tau_nm_per_rad" not in payload
    assert np.asarray(payload["kp_tau_matrix_nm_per_rad"]).shape == (2, 2)
    lock_path = tmp_path / "frozen_pd_gains.json"
    artifact_hash = write_gain_lock(lock_path, payload)
    loaded, loaded_hash = load_gain_lock(lock_path, required_kind="formal")
    assert loaded == payload
    assert loaded_hash == artifact_hash


def test_pd_uses_matrix_multiplication_and_pdff_shares_feedback(
    v2_matrix: dict,
) -> None:
    candidate = gain_candidates(v2_matrix)[4]
    q_ref = np.array([0.30, 0.55])
    dq_ref = np.array([0.10, -0.20])
    reference = CuffPoseReference(
        q_ref,
        dq_ref,
        np.array([0.4, -0.3]),
        _world_from_cuff(q_ref),
    )
    state = np.array([0.25, 0.50, 0.05, -0.10])
    kp = np.asarray(candidate["kp_tau_matrix_nm_per_rad"])
    kd = np.asarray(candidate["kd_tau_matrix_nms_per_rad"])
    expected = kp @ (q_ref - state[:2]) + kd @ (dq_ref - state[2:])

    pd = controller_factory("pd_feedback", candidate)()
    action, diagnostics = pd.solve(state, 0.0, lambda _: reference, object())
    assert isinstance(pd, PDHumanActionController)
    assert pd.kp.shape == pd.kd.shape == (2, 2)
    np.testing.assert_allclose(action, expected, rtol=0.0, atol=1e-12)
    assert diagnostics["gain_definition"].endswith("coupled_torque_pd_v2")

    class PriorModel:
        @staticmethod
        def inverse_dynamics(*_: object) -> np.ndarray:
            return np.array([3.0, -4.0])

    pdff = controller_factory("pd_nominal_inverse_dynamics_ff", candidate)()
    action_ff, _ = pdff.solve(state, 0.0, lambda _: reference, PriorModel())
    np.testing.assert_array_equal(pd.kp, pdff.kp)
    np.testing.assert_array_equal(pd.kd, pdff.kd)
    np.testing.assert_allclose(action_ff, expected + [3.0, -4.0])


def test_mpc_definitions_unchanged_and_v2_fingerprint_is_distinct(
    v2_matrix: dict,
) -> None:
    v1_matrix = load_report_validation_matrix(V1_MATRIX_PATH)
    v1_candidate = gain_candidates(v1_matrix)[4]
    v2_candidate = gain_candidates(v2_matrix)[4]
    assert isinstance(
        controller_factory("fixed_mpc_prior_only", v2_candidate)(), HumanSpaceMPC
    )
    assert isinstance(
        controller_factory("trusted_adaptive_mpc", v2_candidate)(), HumanSpaceMPC
    )
    assert controller_applies_qualified_model("fixed_mpc_prior_only") is False
    assert controller_applies_qualified_model("trusted_adaptive_mpc") is True

    common = {
        "controller_id": "pd_feedback",
        "gain_lock_sha256": "same-placeholder",
        "matrix_sha256": "same-placeholder",
        "reference_clock_sha256": "same-reference",
    }
    v1_fingerprint = canonical_json_sha256(
        controller_fingerprint_payload(
            **common,
            gain_definition=v1_candidate.get(
                "gain_definition", "diagonal_torque_pd_v1"
            ),
            matrix_schema_version=MATRIX_SCHEMA_VERSION_V1,
        )
    )
    v2_fingerprint = canonical_json_sha256(
        controller_fingerprint_payload(
            **common,
            gain_definition=v2_candidate["gain_definition"],
            matrix_schema_version=MATRIX_SCHEMA_VERSION_V2,
        )
    )
    assert v1_fingerprint != v2_fingerprint


def test_coupled_pd_smoke_schema_and_fresh_outputs(
    v2_matrix: dict, tmp_path: Path
) -> None:
    output_dir = tmp_path / "v2_gain_smoke"
    result = run_coupled_pd_gain_smoke(
        matrix_path=V2_MATRIX_PATH,
        output_dir=output_dir,
        duration_s=0.10,
    )
    assert result["formal_execution"] is False
    assert result["scientific_interpretation_permitted"] is False
    assert len(result["arms"]) == 3
    assert all(item["finite_trace"] for item in result["arms"])
    assert all(item["allocation_residual_peak_nm"] < 1e-8 for item in result["arms"])
    assert len({item["reference_trace_sha256"] for item in result["arms"]}) == 1
    assert len({item["measurement_schedule_sha256"] for item in result["arms"]}) == 1
    assert (output_dir / "coupled_pd_gain_smoke_manifest.json").is_file()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_coupled_pd_gain_smoke(
            matrix_path=V2_MATRIX_PATH,
            output_dir=output_dir,
            duration_s=0.10,
        )
