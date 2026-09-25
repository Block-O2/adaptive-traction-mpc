from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.compact_execution_predictor import (
    COMPACT_EXECUTION_PREDICTOR_VERSION,
    CompactCuffResponseModelV1,
    CompactRobotCuffState,
    fit_compact_cuff_response_model,
)


def test_diagonal_affine_fit_round_trip_and_support() -> None:
    rng = np.random.default_rng(811)
    features = rng.normal(size=(80, 6, 3))
    intercept = np.linspace(-0.03, 0.02, 6)
    slopes = rng.normal(scale=0.15, size=(6, 3))
    target = intercept[None, :] + np.einsum("nif,if->ni", features, slopes)

    model = fit_compact_cuff_response_model(
        features=features,
        target_twist_increment=target,
        ridge=0.0,
        development_group_ids=("development_a", "development_b"),
    )
    restored = CompactCuffResponseModelV1.from_record(model.record())
    twist = features[:4, :, 0]
    physical = np.zeros((4, 6))
    command = features[:4, :, 1]
    previous = command - features[:4, :, 2]
    predicted, supported = restored.predict_twist_increment(
        twist, command, physical, previous
    )

    np.testing.assert_allclose(predicted, target[:4], atol=1.0e-10, rtol=0.0)
    assert np.all(supported)
    assert restored.version == COMPACT_EXECUTION_PREDICTOR_VERSION
    assert restored.development_group_ids == ("development_a", "development_b")

    outside_command = command.copy()
    outside_command[0, 0] += 100.0
    _, outside_supported = restored.predict_twist_increment(
        twist, outside_command, physical, previous
    )
    assert not outside_supported[0]


def test_margin_and_support_update_is_immutable() -> None:
    features = np.arange(144.0).reshape(8, 6, 3) / 100.0
    target = np.arange(48.0).reshape(8, 6) / 1000.0
    model = fit_compact_cuff_response_model(
        features=features,
        target_twist_increment=target,
        ridge=1.0e-6,
        development_group_ids=("development",),
    )
    updated = model.with_margin_and_support(
        acceleration_margin_rad_s2=np.radians([30.0, 60.0]),
        feature_min=model.feature_min - 1.0,
        feature_max=model.feature_max + 1.0,
        calibration_group_ids=("calibration",),
    )

    np.testing.assert_array_equal(model.acceleration_margin_rad_s2, np.zeros(2))
    np.testing.assert_allclose(
        np.degrees(updated.acceleration_margin_rad_s2), [30.0, 60.0]
    )
    assert updated.calibration_group_ids == ("calibration",)


def test_robot_cuff_state_requires_a_proper_rotation() -> None:
    state = CompactRobotCuffState(
        position_world_m=np.zeros(3),
        rotation_world=np.eye(3),
        linear_velocity_world_m_s=np.zeros(3),
        angular_velocity_world_rad_s=np.zeros(3),
    )
    np.testing.assert_array_equal(state.rotation_world, np.eye(3))

    with pytest.raises(ValueError, match="proper rotation"):
        CompactRobotCuffState(
            position_world_m=np.zeros(3),
            rotation_world=np.diag([1.0, 1.0, -1.0]),
            linear_velocity_world_m_s=np.zeros(3),
            angular_velocity_world_rad_s=np.zeros(3),
        )
