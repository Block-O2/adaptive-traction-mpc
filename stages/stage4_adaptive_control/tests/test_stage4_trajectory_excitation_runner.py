from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from scripts.run_stage4_trajectory_excitation_generalization import (
    DEFAULT_PATIENT_CONFIG,
    DEFAULT_TRAJECTORY_CONFIG,
    REGISTERED_MEASUREMENT_SEED,
    REGISTERED_MPC_SEED,
    REGISTERED_PATIENT_ID,
    REGISTERED_SENSOR_CASE,
    RESULT_SCHEMA_VERSION,
    SMOKE_EVIDENCE_CATEGORY,
    SMOKE_MARKER,
    _promotions_follow_qualification,
    preregistered_runtime_limit_s,
    run_selected_trajectory,
    select_trajectory,
)
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.reference import cold_start_joint_reference
from traction_mpc_stage4.trajectory_excitation import (
    trajectory_joint_reference,
    trajectory_waypoints,
)


SMOKE_CASES = (
    "registered_high_flexion_23s",
    "slow_high_flexion_34p5s",
    "two_cycle_moderate_23s",
)


@pytest.fixture(scope="module")
def trajectory_smokes(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    output_root = tmp_path_factory.mktemp("trajectory_smokes")
    results = {
        trajectory_id: run_selected_trajectory(
            trajectory_config=DEFAULT_TRAJECTORY_CONFIG,
            trajectory_id=trajectory_id,
            patient_config=DEFAULT_PATIENT_CONFIG,
            output_root=output_root,
            smoke_duration_s=0.1,
        )
        for trajectory_id in SMOKE_CASES
    }
    return output_root, results


def test_trajectory_selection_is_deterministic_and_rejects_unknown_id() -> None:
    first, first_suite = select_trajectory(
        DEFAULT_TRAJECTORY_CONFIG, "slow_high_flexion_34p5s"
    )
    second, second_suite = select_trajectory(
        DEFAULT_TRAJECTORY_CONFIG, "slow_high_flexion_34p5s"
    )
    assert first == second
    assert first_suite == second_suite
    assert len(first_suite["cases"]) == 6
    with pytest.raises(KeyError, match="unknown trajectory id"):
        select_trajectory(DEFAULT_TRAJECTORY_CONFIG, "not_preregistered")


def test_preregistered_duration_to_runtime_mapping_is_exact() -> None:
    _, suite = select_trajectory(
        DEFAULT_TRAJECTORY_CONFIG, "registered_high_flexion_23s"
    )
    runtimes = {
        item["trajectory_id"]: preregistered_runtime_limit_s(item)
        for item in suite["cases"]
    }
    assert runtimes["registered_high_flexion_23s"] == 32.0
    assert runtimes["moderate_rom_23s"] == 32.0
    assert runtimes["hip_dominant_low_knee_23s"] == 32.0
    assert runtimes["knee_dominant_low_hip_23s"] == 32.0
    assert runtimes["two_cycle_moderate_23s"] == 32.0
    assert runtimes["slow_high_flexion_34p5s"] == 43.5


def test_promotions_are_matched_to_applied_qualification_events() -> None:
    summary = {
        "hierarchical_trust": {
            "qualifications": [
                {
                    "challenger_index": 0,
                    "qualification_time_s": 9.72,
                    "applied_to_control": True,
                }
            ],
            "control_promotions": [
                {"challenger_index": 0, "promotion_time_s": 9.72}
            ],
            "challengers": [
                {
                    "challenger_index": 0,
                    "status": "promoted_to_control_incumbent",
                    "applied_to_control": True,
                }
            ],
        }
    }
    assert _promotions_follow_qualification(summary) is True

    missing = deepcopy(summary)
    missing["hierarchical_trust"]["qualifications"] = []
    assert _promotions_follow_qualification(missing) is False

    out_of_order = deepcopy(summary)
    out_of_order["hierarchical_trust"]["control_promotions"][0][
        "promotion_time_s"
    ] = 9.71
    assert _promotions_follow_qualification(out_of_order) is False


def test_reference_start_end_and_anchor_consistency() -> None:
    _, suite = select_trajectory(
        DEFAULT_TRAJECTORY_CONFIG, "registered_high_flexion_23s"
    )
    for case in suite["cases"]:
        duration = float(case["duration_s"])
        start = trajectory_joint_reference(case, 0.0)
        end = trajectory_joint_reference(case, duration)
        np.testing.assert_allclose(start[0], end[0], rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(start[1], 0.0, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(start[2], 0.0, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(end[1], 0.0, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(end[2], 0.0, rtol=0.0, atol=1e-12)
        assert trajectory_waypoints(case)[-1].time_s == duration

    anchor = next(
        item
        for item in suite["cases"]
        if item["trajectory_id"] == "registered_high_flexion_23s"
    )
    for time_s in np.linspace(0.0, 23.0, 93):
        actual = trajectory_joint_reference(anchor, float(time_s))
        expected = cold_start_joint_reference(float(time_s))
        for actual_item, expected_item in zip(actual, expected, strict=True):
            np.testing.assert_array_equal(actual_item, expected_item)


def test_three_smokes_have_correct_labels_runtime_and_reference_injection(
    trajectory_smokes: tuple[Path, dict],
) -> None:
    output_root, results = trajectory_smokes
    definition_hashes = set()
    expected_runtime = {
        "registered_high_flexion_23s": 32.0,
        "slow_high_flexion_34p5s": 43.5,
        "two_cycle_moderate_23s": 32.0,
    }
    for trajectory_id, result in results.items():
        case, _ = select_trajectory(DEFAULT_TRAJECTORY_CONFIG, trajectory_id)
        case_dir = output_root / trajectory_id
        assert result["schema_version"] == RESULT_SCHEMA_VERSION
        assert result["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
        assert result["scientific_interpretation_permitted"] is False
        assert result["trajectory"]["trajectory_id"] == trajectory_id
        assert result["trajectory"]["trajectory_duration_s"] == case["duration_s"]
        assert (
            result["trajectory"]["preregistered_runtime_limit_s"]
            == expected_runtime[trajectory_id]
        )
        assert result["provenance"]["executed_wall_time_limit_s"] == 0.1
        assert result["provenance"]["postprocessing_mode"] == "fresh_run"
        assert result["registered_configuration"]["trajectory"] == trajectory_id
        assert (
            result["registered_configuration"]["reference_phase_duration_s"]
            == case["duration_s"]
        )
        definition_hashes.add(
            result["reference_validation"]["reference_definition_sha256"]
        )
        for sample in result["reference_validation"]["samples"]:
            expected = trajectory_joint_reference(case, sample["time_s"])
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
        raw = json.loads((case_dir / "comparison_summary.json").read_text())
        json.dumps(raw, allow_nan=False)
        for arm in ("prior_only", "trusted_adaptive"):
            raw_arm = json.loads((case_dir / f"{arm}.json").read_text())
            assert raw_arm["trajectory"] == trajectory_id
            assert raw_arm["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
    assert len(definition_hashes) == len(SMOKE_CASES)


def test_frozen_patient_controller_seeds_and_arm_provenance_are_identical(
    trajectory_smokes: tuple[Path, dict],
) -> None:
    _, results = trajectory_smokes
    controller_fingerprints = set()
    trajectory_config_hashes = set()
    for trajectory_id, result in results.items():
        provenance = result["provenance"]
        assert provenance["patient_id"] == REGISTERED_PATIENT_ID
        assert result["patient"]["patient_id"] == REGISTERED_PATIENT_ID
        assert provenance["sensor_regime"] == REGISTERED_SENSOR_CASE
        assert provenance["seeds"] == {
            "measurement": REGISTERED_MEASUREMENT_SEED,
            "mpc": REGISTERED_MPC_SEED,
        }
        assert provenance["estimator_trust_initialization"] == (
            "fresh_per_arm_per_trajectory"
        )
        controller_fingerprints.add(provenance["controller_fingerprint_sha256"])
        trajectory_config_hashes.add(provenance["trajectory_config_sha256"])
        for arm in ("prior_only", "trusted_adaptive"):
            arm_provenance = result["arms"][arm]["provenance"]
            assert arm_provenance["trajectory_id"] == trajectory_id
            assert arm_provenance["patient_id"] == REGISTERED_PATIENT_ID
            assert arm_provenance["arm"] == arm
            assert arm_provenance["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
            assert arm_provenance["controller_fingerprint_sha256"] == provenance[
                "controller_fingerprint_sha256"
            ]
    assert len(controller_fingerprints) == 1
    assert len(trajectory_config_hashes) == 1


def test_ab_isolation_and_no_estimator_warm_start_leakage(
    trajectory_smokes: tuple[Path, dict],
) -> None:
    _, results = trajectory_smokes
    prior = nominal_base_parameters()
    for result in results.values():
        isolation = result["ab_isolation"]
        assert isolation["selected_true_patient_equal_between_arms"] is True
        assert isolation[
            "measurement_seed_and_realization_equal_before_promotion"
        ] is True
        assert isolation["prior_only_control_beta_constant_population_prior"] is True
        assert isolation[
            "trusted_control_beta_population_prior_before_promotion"
        ] is True
        assert isolation["pre_promotion_trace_max_abs_difference"]
        assert all(
            value == 0.0
            for value in isolation[
                "pre_promotion_trace_max_abs_difference"
            ].values()
        )
        for arm in ("prior_only", "trusted_adaptive"):
            record = result["arms"][arm]
            np.testing.assert_allclose(record["initial_control_beta"], prior)
            np.testing.assert_allclose(record["final_control_beta"], prior)
            assert record["finite_trace"] is True
            assert record["control_promotion_count"] == 0
            assert record["qualified_count"] == 0
            assert record["promotion_only_after_valid_qualification"] is True
        assert result["arms"]["prior_only"][
            "trusted_adaptation_entered_control"
        ] is False


def test_output_overwrite_protection(
    trajectory_smokes: tuple[Path, dict],
) -> None:
    output_root, _ = trajectory_smokes
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_selected_trajectory(
            trajectory_config=DEFAULT_TRAJECTORY_CONFIG,
            trajectory_id="registered_high_flexion_23s",
            patient_config=DEFAULT_PATIENT_CONFIG,
            output_root=output_root,
            smoke_duration_s=0.1,
        )
