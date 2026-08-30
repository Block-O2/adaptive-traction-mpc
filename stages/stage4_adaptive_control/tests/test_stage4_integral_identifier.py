from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import _world_from_cuff
from traction_mpc_stage4.estimator_v2 import (
    AccumulatedCuffGeometryEstimator,
    BaseParameterHumanModel,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case
from traction_mpc_stage4.state_ukf import StateOnlyHumanUKF


def test_integral_regression_matches_exact_instantaneous_model_without_qdd_input() -> None:
    time = np.linspace(0.0, 2.0, 20001)
    q1 = 0.35 + 0.18 * np.sin(1.1 * time) + 0.03 * np.sin(2.3 * time)
    q2 = 0.55 + 0.14 * np.cos(0.9 * time) - 0.02 * np.sin(1.7 * time)
    dq1 = 0.18 * 1.1 * np.cos(1.1 * time) + 0.03 * 2.3 * np.cos(2.3 * time)
    dq2 = -0.14 * 0.9 * np.sin(0.9 * time) - 0.02 * 1.7 * np.cos(1.7 * time)
    ddq1 = -0.18 * 1.1**2 * np.sin(1.1 * time) - 0.03 * 2.3**2 * np.sin(2.3 * time)
    ddq2 = -0.14 * 0.9**2 * np.cos(0.9 * time) + 0.02 * 1.7**2 * np.sin(1.7 * time)
    state = np.column_stack([q1, q2, dq1, dq2])
    beta = nominal_base_parameters()
    torque = np.array(
        [
            dynamic_regressor_row(q, dq, ddq) @ beta
            for q, dq, ddq in zip(
                state[:, :2], state[:, 2:], np.column_stack([ddq1, ddq2]), strict=True
            )
        ]
    )
    regressor, target = integral_regression_block(time, state, torque)
    np.testing.assert_allclose(regressor @ beta, target, atol=2e-7, rtol=2e-8)


def test_state_ukf_is_strictly_four_state_and_tracks_ideal_measurements() -> None:
    initial = cold_start_teaching_reference(0.0)
    geometry_identifier = AccumulatedCuffGeometryEstimator(
        initial.world_from_cuff.translation,
        initial.world_from_cuff.rotation,
        initial.q_rad,
    )
    model = BaseParameterHumanModel(
        geometry_identifier.geometry, nominal_base_parameters(HUMAN)
    )
    state = np.concatenate([initial.q_rad, np.zeros(2)])
    action = model.inverse_dynamics(state[:2], state[2:], np.zeros(2))
    ukf = StateOnlyHumanUKF(state, 0.0, action)
    for index in range(1, 21):
        state = model.step_dynamics(state, action, 0.02)
        estimate, diagnostics = ukf.step(
            time_s=0.02 * index,
            measured_state=state,
            measured_generalized_input_nm=action,
            model=model,
        )
    assert ukf.state_dimension == 4
    assert ukf.parameter_state_dimension == 0
    assert diagnostics["parameter_state_dimension"] == 0
    np.testing.assert_allclose(estimate, state, atol=2e-4)


def test_short_integral_architectures_share_the_same_safe_runner() -> None:
    for architecture in ("integral_minimal", "integral_state_ukf"):
        summary, _ = run_sensor_realism_case(
            sensor_realism_cases()[0],
            duration_s=0.10,
            estimator_architecture=architecture,
        )
        assert summary["mechanically_completed_requested_duration"]
        assert summary["events"]["force_gate_events"] == 0
        assert summary["estimator_architecture"]["augmented_or_parameter_ukf"] is False
    assert summary["state_ukf"]["state_dimension"] == 4
    assert summary["state_ukf"]["parameter_state_dimension"] == 0


def test_integral_identifier_excludes_contaminated_windows() -> None:
    initial = cold_start_teaching_reference(0.0)
    geometry_identifier = AccumulatedCuffGeometryEstimator(
        initial.world_from_cuff.translation,
        initial.world_from_cuff.rotation,
        initial.q_rad,
    )
    history = []
    for index, time in enumerate(np.arange(0.0, 1.01, 0.02)):
        history.append(
            {
                "time_s": float(time),
                "state": np.array([0.2 + 0.1 * time, 0.3 + 0.05 * time, 0.1, 0.05]),
                "force_world_n": np.zeros(3),
                "moment_world_nm": np.zeros(3),
                "contaminated": index == 25,
            }
        )
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    regressor, target, contaminated = identifier._integral_blocks(
        history, geometry_identifier.geometry
    )
    assert contaminated > 0
    assert len(regressor) == len(target)
    assert np.all(np.isfinite(regressor))
