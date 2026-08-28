from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

import scripts.run_stage4_crossed_excitation_replication as crossed_runner
from scripts.run_stage4_crossed_excitation_replication import (
    DEFAULT_MATRIX_CONFIG,
    DEFAULT_PATIENT_CONFIG,
    DEFAULT_TRAJECTORY_CONFIG,
    REUSED_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SMOKE_EVIDENCE_CATEGORY,
    SMOKE_MARKER,
    analysis_matrix_entries,
    load_crossed_replication_matrix,
    output_path_for_case,
    run_selected_crossed_case,
    select_crossed_case,
    verify_reused_evidence,
)
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.trajectory_excitation import trajectory_joint_reference


SMOKE_CASE_IDS = (
    "registered_stage2_mild_anchor__registered_high_flexion_23s__seed54113",
    "registered_moderate_anchor__hip_dominant_low_knee_23s__seed44104",
    "registered_stage2_mild_anchor__two_cycle_moderate_23s__seed44104",
)
REUSED_CASE_IDS = (
    "registered_formal_perturbed_anchor__registered_high_flexion_23s__seed44104",
    "registered_formal_perturbed_anchor__two_cycle_moderate_23s__seed44104",
)


@pytest.fixture(scope="module")
def crossed_smokes(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, dict]]:
    output_root = tmp_path_factory.mktemp("crossed_replication_smokes")
    results = {
        case_id: run_selected_crossed_case(
            matrix_config=DEFAULT_MATRIX_CONFIG,
            case_id=case_id,
            patient_config=DEFAULT_PATIENT_CONFIG,
            trajectory_config=DEFAULT_TRAJECTORY_CONFIG,
            output_root=output_root,
            smoke_duration_s=0.1,
        )
        for case_id in SMOKE_CASE_IDS
    }
    return output_root, results


def test_matrix_parsing_and_selection_are_deterministic() -> None:
    first = load_crossed_replication_matrix(DEFAULT_MATRIX_CONFIG)
    second = load_crossed_replication_matrix(DEFAULT_MATRIX_CONFIG)
    assert first == second
    assert len(first["cases"]) == 18
    selected, selected_matrix = select_crossed_case(
        DEFAULT_MATRIX_CONFIG, SMOKE_CASE_IDS[0]
    )
    selected_again, matrix_again = select_crossed_case(
        DEFAULT_MATRIX_CONFIG, SMOKE_CASE_IDS[0]
    )
    assert selected == selected_again
    assert selected_matrix == matrix_again
    with pytest.raises(ValueError, match="unknown crossed-replication case"):
        select_crossed_case(DEFAULT_MATRIX_CONFIG, "not_preregistered")


def test_exact_matrix_classification_and_output_paths_are_unique(tmp_path: Path) -> None:
    matrix = load_crossed_replication_matrix(DEFAULT_MATRIX_CONFIG)
    new_cases = [x for x in matrix["cases"] if x["execution_source"] == "new_formal_run"]
    reused = [
        x
        for x in matrix["cases"]
        if x["execution_source"] == "read_only_existing_formal_bridge"
    ]
    assert len(new_cases) == 16
    assert {x["case_id"] for x in reused} == set(REUSED_CASE_IDS)
    paths = [output_path_for_case(tmp_path, case) for case in matrix["cases"]]
    assert len(paths) == len(set(paths)) == 18

    entries = analysis_matrix_entries(DEFAULT_MATRIX_CONFIG, tmp_path)
    assert len(entries) == 18
    assert sum(x["reused_vs_newly_executed"] == "new_execution_required" for x in entries) == 16
    assert sum(x["reused_vs_newly_executed"] == "reused_read_only" for x in entries) == 2


def test_smokes_inject_exact_factors_runtime_reference_and_provenance(
    crossed_smokes: tuple[Path, dict[str, dict]],
) -> None:
    output_root, results = crossed_smokes
    matrix_hash = crossed_runner._sha256(DEFAULT_MATRIX_CONFIG)
    patient_hash = crossed_runner._sha256(DEFAULT_PATIENT_CONFIG)
    trajectory_hash = crossed_runner._sha256(DEFAULT_TRAJECTORY_CONFIG)
    for case_id, result in results.items():
        case, _ = select_crossed_case(DEFAULT_MATRIX_CONFIG, case_id)
        case_dir = output_root / case_id
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["case_id"] == case_id
        assert result["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
        assert result["scientific_interpretation_permitted"] is False
        assert result["patient"]["case_id"] == case["patient_id"]
        assert result["trajectory"]["trajectory_id"] == case["trajectory_id"]
        assert result["matrix_case"] == case

        provenance = result["provenance"]
        assert provenance["patient_id"] == case["patient_id"]
        assert provenance["trajectory_id"] == case["trajectory_id"]
        assert provenance["measurement_seed"] == case["measurement_seed"]
        assert provenance["matrix_config_sha256"] == matrix_hash
        assert provenance["patient_config_sha256"] == patient_hash
        assert provenance["trajectory_config_sha256"] == trajectory_hash
        assert provenance["preregistered_runtime_limit_s"] == 32.0
        assert provenance["executed_wall_time_limit_s"] == 0.1
        assert provenance["reused_vs_newly_executed"] == "newly_executed"
        assert provenance["matrix_execution_class"] == "new_formal_run"
        assert provenance["execution_source"] == "structural_smoke_fresh_run"
        assert provenance["structural_smoke"] is True

        registered = result["registered_configuration"]
        assert registered["human"] == case["patient_id"]
        assert registered["trajectory"] == case["trajectory_id"]
        assert registered["measurement_seed"] == case["measurement_seed"]
        assert registered["mpc_seed"] == 20260824
        assert registered["sensor_case"] == "noise_bias_drift_200hz"
        assert registered["reference_phase_duration_s"] == 23.0
        assert registered["wall_time_limit_s"] == 0.1
        assert registered["measurement_model"]["random_seed"] == case[
            "measurement_seed"
        ]

        for sample in result["reference_validation"]["samples"]:
            expected = trajectory_joint_reference(result["trajectory"], sample["time_s"])
            np.testing.assert_allclose(sample["q_rad"], expected[0])
            np.testing.assert_allclose(sample["dq_rad_s"], expected[1])
            np.testing.assert_allclose(sample["ddq_rad_s2"], expected[2])
        for filename in (
            "prior_only.json",
            "trusted_adaptive.json",
            "prior_only_trace.npz",
            "trusted_adaptive_trace.npz",
            "comparison_summary.json",
            "comparison_summary.md",
            SMOKE_MARKER,
        ):
            assert (case_dir / filename).is_file()
        json.dumps(result, allow_nan=False)


def test_ab_isolation_fresh_state_and_frozen_controller_hold_across_cases(
    crossed_smokes: tuple[Path, dict[str, dict]],
) -> None:
    _, results = crossed_smokes
    prior = nominal_base_parameters()
    fingerprints = set()
    initial_patient_states = []
    for result in results.values():
        isolation = result["ab_isolation"]
        assert isolation["selected_true_patient_equal_between_arms"] is True
        assert isolation["measurement_seed_and_realization_equal_before_promotion"] is True
        assert isolation["prior_only_control_beta_constant_population_prior"] is True
        assert isolation["trusted_control_beta_population_prior_before_promotion"] is True
        assert all(
            value == 0.0
            for value in isolation["pre_promotion_trace_max_abs_difference"].values()
        )
        assert all(result["fresh_state_validation"].values())
        fingerprints.add(result["provenance"]["controller_fingerprint_sha256"])

        for arm in ("prior_only", "trusted_adaptive"):
            arm_result = result["arms"][arm]
            np.testing.assert_allclose(arm_result["initial_control_beta"], prior)
            assert arm_result["finite_trace"] is True
            assert arm_result["qualification_count"] == 0
            assert arm_result["promotion_count"] == 0
            assert arm_result["rejection_count"] == 0
            arm_provenance = arm_result["provenance"]
            assert arm_provenance["arm"] == arm
            assert {
                "patient_id",
                "trajectory_id",
                "measurement_seed",
                "matrix_config_sha256",
                "patient_config_sha256",
                "trajectory_config_sha256",
                "controller_fingerprint_sha256",
                "baseline_tag",
                "baseline_commit",
                "arm",
                "evidence_category",
                "matrix_execution_class",
                "execution_source",
                "reused_vs_newly_executed",
            } <= set(arm_provenance)
            assert arm_provenance["execution_source"] == (
                "structural_smoke_fresh_run"
            )
        initial_patient_states.append(result["patient"]["case_id"])
    assert len(fingerprints) == 1
    assert initial_patient_states == [
        "registered_stage2_mild_anchor",
        "registered_moderate_anchor",
        "registered_stage2_mild_anchor",
    ]


def test_reused_evidence_is_verified_and_never_executes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden_execution(*args: object, **kwargs: object) -> None:
        raise AssertionError("reused evidence entered run_paired_ab")

    monkeypatch.setattr(crossed_runner, "run_paired_ab", forbidden_execution)
    for case_id in REUSED_CASE_IDS:
        direct = verify_reused_evidence(DEFAULT_MATRIX_CONFIG, case_id)
        resolved = run_selected_crossed_case(
            matrix_config=DEFAULT_MATRIX_CONFIG,
            case_id=case_id,
            patient_config=DEFAULT_PATIENT_CONFIG,
            trajectory_config=DEFAULT_TRAJECTORY_CONFIG,
            output_root=tmp_path,
            smoke_duration_s=0.1,
        )
        assert direct == resolved
        assert resolved["schema_version"] == REUSED_SCHEMA_VERSION
        assert resolved["artifact_hashes_verified"] is True
        assert resolved["config_and_provenance_verified"] is True
        assert resolved["finite_traces_verified"] is True
        assert resolved["executed_by_crossed_runner"] is False
        assert resolved["reused_vs_newly_executed"] == "reused_read_only"
        assert not (tmp_path / case_id).exists()


def test_reused_hash_tampering_is_rejected(tmp_path: Path) -> None:
    matrix = json.loads(DEFAULT_MATRIX_CONFIG.read_text(encoding="utf-8"))
    case_id = REUSED_CASE_IDS[0]
    tampered = deepcopy(matrix)
    tampered["read_only_bridge_artifact_hashes"][case_id][
        "comparison_summary.json"
    ] = "0" * 64
    config_path = tmp_path / "tampered_matrix.json"
    config_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RuntimeError, match="reused evidence hash mismatch"):
        verify_reused_evidence(config_path, case_id)


def test_output_overwrite_protection(
    crossed_smokes: tuple[Path, dict[str, dict]],
) -> None:
    output_root, _ = crossed_smokes
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_selected_crossed_case(
            matrix_config=DEFAULT_MATRIX_CONFIG,
            case_id=SMOKE_CASE_IDS[0],
            patient_config=DEFAULT_PATIENT_CONFIG,
            trajectory_config=DEFAULT_TRAJECTORY_CONFIG,
            output_root=output_root,
            smoke_duration_s=0.1,
        )
