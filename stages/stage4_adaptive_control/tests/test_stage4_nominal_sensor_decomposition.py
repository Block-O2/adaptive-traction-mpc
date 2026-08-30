from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.run_stage4_nominal_sensor_decomposition import (
    EXPECTED_SENSOR_DEFINITIONS,
    REGISTERED_SENSOR_CASES,
    validate_preregistration,
)
from scripts.run_stage4_single_challenger_closed_loop_ab import run_paired_ab
from traction_mpc_stage3.human import HUMAN


STAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STAGE_ROOT.parents[1]


def test_nominal_sensor_preregistration_matches_existing_cases_and_baseline() -> None:
    observed, validation = validate_preregistration(
        stage_root=STAGE_ROOT, repo_root=REPO_ROOT
    )
    assert tuple(observed) == REGISTERED_SENSOR_CASES
    assert observed == EXPECTED_SENSOR_DEFINITIONS
    assert validation["true_beta_equals_population_prior"] is True
    assert validation["baseline_tag_resolves_to_expected_commit"] is True
    assert validation["baseline_is_ancestor_of_head"] is True


@pytest.mark.parametrize("sensor_name", REGISTERED_SENSOR_CASES)
def test_existing_sensor_case_can_use_frozen_nominal_pair(
    tmp_path: Path, sensor_name: str
) -> None:
    comparison, summaries, traces = run_paired_ab(
        tmp_path / sensor_name,
        sensor_case_name=sensor_name,
        true_human=HUMAN,
        true_metadata={"case": "nominal_reference"},
        human_label="nominal_reference",
        wall_time_limit_s=0.1,
        evidence_category="structural_smoke_non_scientific",
        write_comparison_outputs=False,
    )
    assert comparison["registered_configuration"]["sensor_case"] == sensor_name
    assert comparison["registered_configuration"]["measurement_model"] == (
        EXPECTED_SENSOR_DEFINITIONS[sensor_name]
    )
    assert comparison["mechanical_ab_isolation"]["prior_control_model_constant"]
    assert summaries["prior_only"]["true_human_case"] == "nominal_reference"
    assert summaries["trusted_adaptive"]["true_human_case"] == "nominal_reference"
    np.testing.assert_array_equal(
        traces["prior_only"]["measured_cuff_force_world_n"],
        traces["trusted_adaptive"]["measured_cuff_force_world_n"],
    )


def test_unknown_sensor_case_is_rejected_before_rollout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown existing sensor case"):
        run_paired_ab(
            tmp_path / "unknown",
            sensor_case_name="invented_noise_case",
            true_human=HUMAN,
            wall_time_limit_s=0.1,
            evidence_category="structural_smoke_non_scientific",
            write_comparison_outputs=False,
        )


def test_measurement_seed_override_changes_only_recorded_sensor_seed(
    tmp_path: Path,
) -> None:
    comparison, summaries, _ = run_paired_ab(
        tmp_path / "seed_override",
        sensor_case_name="noise_200hz",
        measurement_seed=54113,
        true_human=HUMAN,
        true_metadata={"case": "nominal_reference"},
        human_label="nominal_reference",
        wall_time_limit_s=0.1,
        evidence_category="structural_smoke_non_scientific",
        write_comparison_outputs=False,
    )
    config = comparison["registered_configuration"]
    assert config["measurement_seed"] == 54113
    assert config["measurement_model"]["random_seed"] == 54113
    assert config["mpc_seed"] == 20260824
    for arm in ("prior_only", "trusted_adaptive"):
        assert summaries[arm]["measurement_model"]["random_seed"] == 54113


@pytest.mark.parametrize("invalid_seed", (-1, True, 1.5))
def test_invalid_measurement_seed_is_rejected(
    tmp_path: Path, invalid_seed: object
) -> None:
    expected = (ValueError, TypeError)
    with pytest.raises(expected):
        run_paired_ab(
            tmp_path / "invalid_seed",
            sensor_case_name="noise_200hz",
            measurement_seed=invalid_seed,  # type: ignore[arg-type]
            true_human=HUMAN,
            wall_time_limit_s=0.1,
            evidence_category="structural_smoke_non_scientific",
            write_comparison_outputs=False,
        )
