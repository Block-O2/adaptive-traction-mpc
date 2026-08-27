from __future__ import annotations

import numpy as np

from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row, nominal_base_parameters
from traction_mpc_stage4.minimal_adaptation import (
    CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
    control_relevant_integral_regression_block,
    dynamic_scale_projection,
    effective_base_parameters,
    regression_confidence,
)
from traction_mpc_stage4.minimal_observability import run_minimal_observability_audit


def test_three_scale_prior_is_exact_and_does_not_add_anatomical_parameters() -> None:
    prior = nominal_base_parameters()
    projection = dynamic_scale_projection(prior)
    assert projection.shape == (11, 3)
    np.testing.assert_allclose(effective_base_parameters(np.ones(3), prior), prior)
    assert tuple(CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES) == (
        "effective_mass_scale",
        "effective_stiffness_scale",
        "effective_damping_scale",
    )


def test_projected_integral_regression_matches_effective_parameter_model() -> None:
    time = np.linspace(0.0, 1.0, 1001)
    q1 = 0.3 + 0.1 * np.sin(time)
    q2 = 0.5 + 0.08 * np.cos(1.3 * time)
    dq1 = 0.1 * np.cos(time)
    dq2 = -0.08 * 1.3 * np.sin(1.3 * time)
    ddq1 = -0.1 * np.sin(time)
    ddq2 = -0.08 * 1.3**2 * np.cos(1.3 * time)
    state = np.column_stack([q1, q2, dq1, dq2])
    scales = np.array([1.08, 1.15, 0.90])
    beta = effective_base_parameters(scales)
    torque = np.array(
        [
            dynamic_regressor_row(q, dq, ddq) @ beta
            for q, dq, ddq in zip(
                state[:, :2],
                state[:, 2:],
                np.column_stack([ddq1, ddq2]),
                strict=True,
            )
        ]
    )
    projected, target = control_relevant_integral_regression_block(
        time, state, torque
    )
    assert projected.shape == (2, 3)
    np.testing.assert_allclose(projected @ scales, target, atol=2e-7, rtol=2e-8)


def test_confidence_reports_rank_condition_residual_and_covariance() -> None:
    regressor = np.array(
        [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0], [1.0, 1.0, 1.0]]
    )
    residual = np.array([0.1, -0.1, 0.05, -0.05])
    confidence = regression_confidence(
        regressor,
        residual,
        CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
        accepted=True,
    )
    payload = confidence.to_dict()
    assert confidence.full_rank
    assert np.isfinite(confidence.condition_number)
    assert confidence.residual_rms > 0.0
    assert confidence.covariance.shape == (3, 3)
    assert np.all(confidence.standard_deviation > 0.0)
    assert payload["interpretation"] == "local_estimator_evidence_not_safety_probability"


def test_confidence_exposes_rank_deficiency_without_prior_masking() -> None:
    regressor = np.ones((5, 3))
    confidence = regression_confidence(
        regressor,
        np.zeros(5),
        CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES,
        accepted=False,
        reasons=("rank_deficient",),
    )
    assert confidence.rank == 1
    assert not confidence.full_rank
    assert np.isinf(confidence.condition_number)
    assert confidence.reasons == ("rank_deficient",)


def test_current_high_flexion_reference_observes_minimal_subspaces() -> None:
    audit = run_minimal_observability_audit()
    assert audit["trajectory"]["name"] == "stage4_population_prior_cold_start_high_flexion_23s"
    assert audit["geometry"]["cumulative"]["23"]["rank"] == 3
    assert audit["dynamics"]["cumulative"]["23"]["rank"] == 3
    assert audit["prohibited_additions"] == {"tube_mpc": False, "ukf": False}
