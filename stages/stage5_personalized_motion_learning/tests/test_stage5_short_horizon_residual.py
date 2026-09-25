from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.short_horizon_residual import (
    RESIDUAL_MODEL_VERSION,
    StateDependentHumanTransitionResidualV1,
    fit_state_dependent_human_transition_residual_v1,
)


def test_ridge_residual_round_trip_and_support() -> None:
    rng = np.random.default_rng(20260921)
    features = rng.normal(size=(80, 5))
    weights = rng.normal(scale=0.1, size=(5, 8))
    target = (features @ weights).reshape(80, 4, 2)
    model = fit_state_dependent_human_transition_residual_v1(
        features=features,
        dq_residual_rad_s=target,
        feature_names=tuple(f"feature_{index}" for index in range(5)),
        training_group_ids=("train_a", "train_b"),
        ridge=1.0e-8,
    )
    predicted, supported = model.predict(features[:6])

    np.testing.assert_allclose(predicted, target[:6], atol=1.0e-8, rtol=0.0)
    assert np.all(supported)
    assert model.record()["version"] == RESIDUAL_MODEL_VERSION
    assert model.record()["independent_force_pose_or_acceleration_head"] is False

    outside = features[:1].copy()
    outside[0, 0] = np.max(features[:, 0]) + 10.0
    _, supported = model.predict(outside)
    assert not supported[0]


def test_calibration_can_expand_support_without_refitting() -> None:
    rng = np.random.default_rng(91)
    features = rng.normal(size=(30, 3))
    target = rng.normal(scale=0.01, size=(30, 4, 2))
    model = fit_state_dependent_human_transition_residual_v1(
        features=features,
        dq_residual_rad_s=target,
        feature_names=("a", "b", "c"),
        training_group_ids=("train",),
    )
    calibration = features[:1].copy()
    calibration[0, 0] = np.max(features[:, 0]) + 0.5
    _, before = model.predict(calibration)
    expanded = model.with_calibration_support(calibration)
    _, after = expanded.predict(calibration)

    assert not before[0]
    assert after[0]
    np.testing.assert_array_equal(model.coefficients, expanded.coefficients)


def test_model_rejects_inconsistent_coefficient_shape() -> None:
    with pytest.raises(ValueError, match="coefficients"):
        StateDependentHumanTransitionResidualV1(
            feature_names=("a", "b"),
            feature_mean=np.zeros(2),
            feature_scale=np.ones(2),
            support_min_standardized=-np.ones(2),
            support_max_standardized=np.ones(2),
            target_mean_rad_s=np.zeros(8),
            target_scale_rad_s=np.ones(8),
            coefficients=np.zeros((2, 8)),
            ridge=1.0,
            training_group_ids=("train",),
        )
