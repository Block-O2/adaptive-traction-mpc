from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.run_stage4_patient_mismatch_robustness import (
    BASELINE_COMMIT,
    BASELINE_TAG,
    SMOKE_EVIDENCE_CATEGORY,
    SMOKE_MARKER,
    run_selected_patient_case,
    select_patient_case,
)
from scripts.run_stage4_single_challenger_closed_loop_ab import (
    REGISTERED_SENSOR_CASE,
    REGISTERED_WALL_LIMIT_S,
    run_paired_ab,
)
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.patient_mismatch import CASE_RESULT_REQUIRED_FIELDS


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "stage4_patient_mismatch_cases.json"
)


def _assert_no_nonfinite_json_numbers(value: object) -> None:
    # The standard-library encoder rejects NaN and infinities when allow_nan=False.
    json.dumps(value, allow_nan=False)


def test_case_selection_is_deterministic_and_unknown_case_is_rejected() -> None:
    selected, first = select_patient_case(CONFIG_PATH, "mass_mild_plus_05pct")
    selected_again, second = select_patient_case(
        CONFIG_PATH, "mass_mild_plus_05pct"
    )
    assert selected == selected_again
    assert first == second
    assert selected.case_id == "mass_mild_plus_05pct"
    with pytest.raises(ValueError, match="unknown patient case"):
        select_patient_case(CONFIG_PATH, "not_registered")


def test_extracted_paired_runner_keeps_formal_defaults() -> None:
    signature = inspect.signature(run_paired_ab)
    assert (
        signature.parameters["sensor_case_name"].default
        == REGISTERED_SENSOR_CASE
        == "noise_bias_drift_200hz"
    )
    assert signature.parameters["measurement_seed"].default is None
    assert signature.parameters["true_human"].default is None
    assert signature.parameters["true_metadata"].default is None
    assert (
        signature.parameters["human_label"].default
        == "registered_cold_start_perturbed_human"
    )
    assert (
        signature.parameters["wall_time_limit_s"].default
        == REGISTERED_WALL_LIMIT_S
        == 32.0
    )
    assert (
        signature.parameters["evidence_category"].default
        == "formal_user_run_unreviewed"
    )
    assert signature.parameters["write_comparison_outputs"].default is True


def test_extracted_runner_default_plant_matches_explicit_registered_anchor(
    tmp_path: Path,
) -> None:
    default_comparison, _, default_traces = run_paired_ab(
        tmp_path / "default",
        wall_time_limit_s=0.1,
        evidence_category=SMOKE_EVIDENCE_CATEGORY,
        write_comparison_outputs=False,
    )
    human, metadata = registered_cold_start_perturbed_human()
    explicit_comparison, _, explicit_traces = run_paired_ab(
        tmp_path / "explicit",
        true_human=human,
        true_metadata=metadata,
        wall_time_limit_s=0.1,
        evidence_category=SMOKE_EVIDENCE_CATEGORY,
        write_comparison_outputs=False,
    )

    for field in (
        "evidence_category",
        "single_scientific_variable",
        "registered_configuration",
        "shared_pre_post_split_wall_time_s",
        "mechanical_ab_isolation",
    ):
        assert default_comparison[field] == explicit_comparison[field]
    for arm in ("prior_only", "trusted_adaptive"):
        assert set(default_traces[arm]) == set(explicit_traces[arm])
        for key in default_traces[arm]:
            np.testing.assert_array_equal(
                default_traces[arm][key], explicit_traces[arm][key]
            )


@pytest.mark.parametrize(
    ("case_id", "geometry_changes"),
    (
        ("mass_mild_plus_05pct", False),
        ("registered_formal_perturbed_anchor", True),
    ),
)
def test_structural_smoke_injects_case_and_preserves_pair_isolation(
    tmp_path: Path, case_id: str, geometry_changes: bool
) -> None:
    result = run_selected_patient_case(
        case_config=CONFIG_PATH,
        case_id=case_id,
        output_root=tmp_path,
        smoke_duration_s=0.1,
    )
    case_dir = tmp_path / case_id

    assert result["schema_version"] == "stage4_patient_mismatch_paired_result_v1"
    assert result["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
    assert result["case_record"]["case_id"] == case_id
    assert result["case_record"]["geometry"]["changes"] is geometry_changes
    assert result["provenance"]["baseline_tag"] == BASELINE_TAG
    assert result["provenance"]["baseline_commit"] == BASELINE_COMMIT
    assert result["provenance"]["preregistered_case_count"] == 13
    assert result["provenance"]["runtime_allowance_s"] == 0.1
    assert result["provenance"]["structural_smoke"] is True
    assert set(CASE_RESULT_REQUIRED_FIELDS["top_level"]) <= set(result)
    assert set(result["arms"]) == {"prior_only", "trusted_adaptive"}

    isolation = result["ab_isolation"]
    assert isolation["selected_true_patient_equal_between_arms"] is True
    assert isolation["measurement_seed_and_realization_equal_before_promotion"] is True
    assert isolation["controller_population_prior_equal_to_nominal"] is True
    assert isolation["prior_only_control_beta_constant_population_prior"] is True
    assert isolation["trusted_control_beta_population_prior_before_promotion"] is True
    assert isolation["geometry_estimation_active_and_equal_before_promotion"] is True
    assert isolation["geometry_prior_uses_nominal_lengths_not_true_patient_oracle"] is True
    assert isolation["geometry_case_changes_true_plant"] is geometry_changes

    arm_fingerprints = set()
    for arm in ("prior_only", "trusted_adaptive"):
        arm_result = result["arms"][arm]
        assert set(CASE_RESULT_REQUIRED_FIELDS["arm"]) <= set(arm_result)
        assert arm_result["provenance"]["patient_case_id"] == case_id
        assert arm_result["provenance"]["evidence_category"] == (
            SMOKE_EVIDENCE_CATEGORY
        )
        arm_fingerprints.add(
            arm_result["provenance"]["frozen_controller_fingerprint_sha256"]
        )

        raw_summary = json.loads((case_dir / f"{arm}.json").read_text())
        assert raw_summary["evidence_category"] == SMOKE_EVIDENCE_CATEGORY
        assert raw_summary["true_human_case"] == case_id
        assert raw_summary["paired_ab_provenance"]["patient_case_id"] == case_id

    assert len(arm_fingerprints) == 1
    assert (
        result["arms"]["prior_only"]["trusted_adaptation_entered_control"]
        is False
    )
    assert (case_dir / "prior_only_trace.npz").is_file()
    assert (case_dir / "trusted_adaptive_trace.npz").is_file()
    assert (case_dir / "comparison_summary.json").is_file()
    assert (case_dir / "comparison_summary.md").is_file()
    assert (case_dir / SMOKE_MARKER).is_file()
    _assert_no_nonfinite_json_numbers(result)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_selected_patient_case(
            case_config=CONFIG_PATH,
            case_id=case_id,
            output_root=tmp_path,
            smoke_duration_s=0.1,
        )


def test_existing_output_override_is_restricted_to_marked_smoke(tmp_path: Path) -> None:
    case_dir = tmp_path / "mass_mild_plus_05pct"
    case_dir.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_selected_patient_case(
            case_config=CONFIG_PATH,
            case_id="mass_mild_plus_05pct",
            output_root=tmp_path,
            smoke_duration_s=0.1,
            debug_allow_existing_output=True,
        )
    with pytest.raises(ValueError, match="restricted to structural smoke"):
        run_selected_patient_case(
            case_config=CONFIG_PATH,
            case_id="mass_mild_plus_05pct",
            output_root=tmp_path,
            debug_allow_existing_output=True,
        )
