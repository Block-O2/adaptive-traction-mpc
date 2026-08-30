from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np

from scripts.run_stage4_nominal_sensor_decomposition import (
    EXPECTED_SENSOR_DEFINITIONS,
)
from scripts.run_stage4_nominal_sensor_multiseed import (
    REGISTERED_MEASUREMENT_SEEDS,
    _seed_invariant_fingerprint,
    expected_sensor_definition,
    validate_seed_set,
)
from scripts.run_stage4_single_challenger_closed_loop_ab import run_paired_ab
from scripts.summarize_stage4_nominal_sensor_multiseed import (
    _category,
    _distribution,
)
from traction_mpc_stage3.human import HUMAN


def test_multiseed_set_is_fixed_and_deterministic() -> None:
    validate_seed_set()
    assert REGISTERED_MEASUREMENT_SEEDS == (
        44104,
        54113,
        64122,
        74131,
        84140,
    )


def test_seeded_sensor_definition_changes_only_random_seed() -> None:
    base = EXPECTED_SENSOR_DEFINITIONS["noise_bias_drift_200hz"]
    observed = expected_sensor_definition(base, 74131)
    expected = deepcopy(base)
    expected["random_seed"] = 74131
    assert observed == expected
    assert base["random_seed"] == 44104


def test_ideal_sensor_is_seed_independent_and_pair_isolated(tmp_path: Path) -> None:
    comparisons = []
    traces_by_seed = []
    for seed in (44104, 54113):
        comparison, _, traces = run_paired_ab(
            tmp_path / str(seed),
            sensor_case_name="ideal_200hz",
            measurement_seed=seed,
            true_human=HUMAN,
            true_metadata={"case": "nominal_reference"},
            human_label="nominal_reference",
            wall_time_limit_s=0.1,
            evidence_category="structural_smoke_non_scientific",
            write_comparison_outputs=False,
        )
        comparisons.append(comparison)
        traces_by_seed.append(traces)
        assert comparison["mechanical_ab_isolation"][
            "first_qualification_times_equal"
        ]
    assert (
        _seed_invariant_fingerprint(comparisons[0])[
            "seed_invariant_runtime_configuration_sha256"
        ]
        == _seed_invariant_fingerprint(comparisons[1])[
            "seed_invariant_runtime_configuration_sha256"
        ]
    )
    for arm in ("prior_only", "trusted_adaptive"):
        for key in traces_by_seed[0][arm]:
            np.testing.assert_array_equal(
                traces_by_seed[0][arm][key], traces_by_seed[1][arm][key]
            )


def test_preregistered_outcome_categories_use_promotion_and_oracle_delta() -> None:
    prior = {
        "promotion_count": 0,
        "clean_oracle_control_model_prediction_rmse_nm": 0.0,
    }
    assert _category(prior, dict(prior)) == "A_no_trusted_promotion"
    promoted_worse = {
        "promotion_count": 1,
        "clean_oracle_control_model_prediction_rmse_nm": 0.2,
    }
    assert (
        _category(prior, promoted_worse)
        == "B_measured_improvement_oracle_degradation"
    )
    nonnominal_prior = {
        "promotion_count": 0,
        "clean_oracle_control_model_prediction_rmse_nm": 0.3,
    }
    promoted_better = {
        "promotion_count": 1,
        "clean_oracle_control_model_prediction_rmse_nm": 0.2,
    }
    assert (
        _category(nonnominal_prior, promoted_better)
        == "C_measured_and_oracle_improvement"
    )


def test_distribution_preserves_per_seed_values_and_registered_statistics() -> None:
    result = _distribution([(44104, 1.0), (54113, 3.0), (64122, 5.0)])
    assert result["count"] == 3
    assert result["minimum"] == 1.0
    assert result["median"] == 3.0
    assert result["maximum"] == 5.0
    assert result["values_by_seed"][1] == {
        "measurement_seed": 54113,
        "value": 3.0,
    }
