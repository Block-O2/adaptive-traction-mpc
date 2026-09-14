from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from traction_mpc_stage5.task_observation import (
    DEPLOYABLE_ESTIMATOR_Q_DQ,
    TaskObservationContract,
    make_task_observation,
    task_observation_from_deployable_estimator_path,
)


class _Geometry:
    def __init__(self) -> None:
        self.received: tuple[np.ndarray, ...] | None = None

    def estimate_state(self, position, rotation, linear_velocity, angular_velocity):
        self.received = tuple(
            np.asarray(value, dtype=float).copy()
            for value in (position, rotation, linear_velocity, angular_velocity)
        )
        return np.radians([5.0, 10.0, 0.5, -0.25])


def test_deployable_observation_uses_only_cuff_measurement_fields() -> None:
    geometry = _Geometry()
    model = SimpleNamespace(geometry=geometry)
    measurement = SimpleNamespace(
        attachment_position_m=np.array([0.1, 0.2, 0.3]),
        attachment_rotation_matrix=np.eye(3),
        attachment_velocity_m_s=np.array([0.01, 0.0, -0.02]),
        attachment_angular_velocity_rad_s=np.array([0.0, 0.1, 0.0]),
        sample_time_s=1.000,
        arrival_time_s=1.010,
    )
    observation = task_observation_from_deployable_estimator_path(
        measurement,
        model,
        human_model_version="fixed-stage5-human-v1",
    )
    assert geometry.received is not None
    assert observation.source == DEPLOYABLE_ESTIMATOR_Q_DQ
    assert observation.age_s == pytest.approx(0.010)
    assert observation.state_rad_rad_s == pytest.approx(
        tuple(np.radians([5.0, 10.0, 0.5, -0.25]))
    )


def test_future_and_stale_task_observations_are_rejected() -> None:
    contract = TaskObservationContract(maximum_staleness_s=0.020)
    with pytest.raises(ValueError, match="future"):
        make_task_observation(
            np.zeros(4),
            sample_timestamp_s=1.001,
            controller_timestamp_s=1.000,
            human_model_version="fixed",
            contract=contract,
        )
    with pytest.raises(ValueError, match="stale"):
        make_task_observation(
            np.zeros(4),
            sample_timestamp_s=1.000,
            controller_timestamp_s=1.021,
            human_model_version="fixed",
            contract=contract,
        )


def test_exactly_one_mpc_period_of_age_is_accepted() -> None:
    observation = make_task_observation(
        np.zeros(4),
        sample_timestamp_s=1.000,
        controller_timestamp_s=1.020,
        human_model_version="fixed",
    )
    assert observation.age_s == pytest.approx(0.020)
