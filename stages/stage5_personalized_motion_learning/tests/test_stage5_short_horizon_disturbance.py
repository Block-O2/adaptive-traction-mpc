from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage5.short_horizon_disturbance import (
    CausalShortHorizonDisturbanceObserver,
    ShortHorizonDisturbanceState,
)


def test_observer_converges_causally_and_requires_full_history() -> None:
    observer = CausalShortHorizonDisturbanceObserver()
    acceleration_innovation = np.asarray([1.0, -2.0])
    force_innovation = np.asarray([3.0, -4.0, 5.0])
    target = np.concatenate([acceleration_innovation, force_innovation])

    for update_index in range(4):
        state = observer.update(
            previous_predicted_human_dq_rad_s=np.zeros(2),
            measured_human_dq_hat_rad_s=(
                acceleration_innovation * observer.control_dt_s
            ),
            previous_predicted_cuff_force_world_n=np.zeros(3),
            measured_cuff_force_world_n=force_innovation,
            prediction_supported=True,
        )
        assert state.valid is (update_index == 3)

    expected = target * (1.0 - (1.0 - observer.alpha) ** 4)
    np.testing.assert_allclose(state.vector, expected, atol=1.0e-12, rtol=0.0)
    assert state.history_coverage_s == pytest.approx(0.020)
    assert state.update_count == 4
    assert observer.record()["truth_input"] is False


def test_unsupported_prediction_clears_history_and_stale_estimate() -> None:
    observer = CausalShortHorizonDisturbanceObserver()
    for _ in range(4):
        observer.update(
            previous_predicted_human_dq_rad_s=np.zeros(2),
            measured_human_dq_hat_rad_s=np.asarray([0.005, -0.005]),
            previous_predicted_cuff_force_world_n=np.zeros(3),
            measured_cuff_force_world_n=np.ones(3),
            prediction_supported=True,
        )
    assert observer.state.valid
    state = observer.update(
        previous_predicted_human_dq_rad_s=np.zeros(2),
        measured_human_dq_hat_rad_s=np.zeros(2),
        previous_predicted_cuff_force_world_n=np.zeros(3),
        measured_cuff_force_world_n=np.zeros(3),
        prediction_supported=False,
    )
    assert not state.valid
    assert state.history_coverage_s == 0.0
    assert state.update_count == 0
    np.testing.assert_array_equal(state.vector, np.zeros(5))


def test_disturbance_state_rejects_invalid_vectors() -> None:
    with pytest.raises(ValueError, match="2-vector"):
        ShortHorizonDisturbanceState(
            human_acceleration_residual_rad_s2=np.zeros(3),
            cuff_force_residual_world_n=np.zeros(3),
            history_coverage_s=0.020,
            update_count=4,
            valid=True,
        )

