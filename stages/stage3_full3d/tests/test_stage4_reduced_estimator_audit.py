from __future__ import annotations

import numpy as np

from traction_mpc_stage4.reduced_estimator_audit import (
    run_reduced_estimator_predictive_audit,
)


def test_reduced_estimator_audit_is_full_rank_but_checks_prediction() -> None:
    result = run_reduced_estimator_predictive_audit()
    assert result["comparison_contract"]["estimator_replaced_or_modified"] is False
    assert len(result["cases"]) == 3
    for case in result["cases"]:
        observability = case["integral_observability"]
        assert observability["full_11_base"]["rank"] == 11
        assert observability["reduced_3_scale"]["rank"] == 3
        assert np.isfinite(
            observability["reduced_3_scale"][
                "column_normalized_condition_number"
            ]
        )


def test_reduced_model_is_exact_for_nominal_but_loses_registered_mismatch_directions() -> None:
    result = run_reduced_estimator_predictive_audit()
    nominal, moderate, cold_start = result["cases"]
    nominal_reduced = nominal["generalized_torque_prediction"][
        "best_integral_fit_reduced_3_scale"
    ]
    assert nominal_reduced["combined_rmse_nm"] < 1e-3
    for mismatch in (moderate, cold_start):
        prediction = mismatch["generalized_torque_prediction"]
        assert prediction["integral_fit_11_base"]["combined_rmse_nm"] < 1e-2
        assert (
            prediction["best_integral_fit_reduced_3_scale"]["combined_rmse_nm"]
            > 10.0 * prediction["integral_fit_11_base"]["combined_rmse_nm"]
        )
        assert any(
            item["individual_trajectory_torque_contribution_rms_nm"] > 1e-3
            for item in mismatch["lost_dynamics_directions"]
        )
