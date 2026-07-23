import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.estimation.multiple_shooting_inverse_mass_mhe import MultipleShootingInverseMassMHE
from traction_mpc.models.spring2d_dynamics import step_dynamics


def _params():
    return {
        "m": 1.0, "k": 450.0, "b_r": 20.0, "b_theta": 0.02, "g": 9.81, "L0": 0.35,
        "rho": 1.0, "base_mode": "linear_sin", "base_slide_amp": 0.035, "theta_init": 0.0,
        "base_x0": 0.0, "base_y0": 0.0, "dt": 0.01,
    }


def _cfg():
    return {
        "window_size": 3, "update_interval": 1, "max_nfev": 12,
        "measurement_weights": [1.0, 0.25, 8.0, 0.6], "process_weights": [316.2278, 31.6228, 1000.0, 100.0],
        "state_scale": [0.1, 1.0, 0.02, 0.1], "arrival_state_scale": [0.1, 1.0, 0.02, 0.1], "lambda_scale": 1.0,
        "lambda_arrival_state": 1.0e-3, "lambda_arrival_parameter": 1.0e-3, "mass_bounds": [0.5, 2.0],
        "state_lower": [-3.1416, -10.0, 0.29, -5.0], "state_upper": [3.1416, 10.0, 0.41, 5.0],
        "xtol": 1.0e-8, "ftol": 1.0e-8, "gtol": 1.0e-8, "initialization_probe": False,
    }


def test_multiple_shooting_mhe_has_state_decision_for_each_window_sample():
    params = _params(); action = np.array([0.1, 0.0]); state = np.array([0.02, -0.15, 0.35, 0.0])
    estimator = MultipleShootingInverseMassMHE(params, _cfg()); estimator.reset(state, warm_state=state)
    for _ in range(3):
        state = step_dynamics(state, action, params["dt"], params)
        result = estimator.add_measurement(action, state, warm_state=state)
    assert result["success"]
    assert estimator.last_states is not None and estimator.last_states.shape == (4, 4)
    assert np.isfinite(result["m_hat"]) and 0.5 <= result["m_hat"] <= 2.0
    assert np.isfinite(result["diagnostics"]["process_residual_rmse"])


def test_multiple_shooting_arrival_prior_advances_with_each_dropped_transition():
    cfg = _cfg(); cfg["update_interval"] = 100
    estimator = MultipleShootingInverseMassMHE(_params(), cfg)
    state = np.array([0.02, -0.15, 0.35, 0.0])
    estimator.reset(state, warm_state=state)
    states = np.array([state + [0.01 * index, 0.0, 0.0, 0.0] for index in range(4)])
    estimator.last_states = states.copy()
    for _ in range(cfg["window_size"]):
        estimator.actions.append(np.zeros(2))

    estimator.add_measurement(np.zeros(2), state, warm_state=state)
    assert np.allclose(estimator.arrival_state, states[1])
    estimator.add_measurement(np.zeros(2), state, warm_state=state)
    assert np.allclose(estimator.arrival_state, states[2])


def test_failed_update_propagates_current_state_and_discards_stale_window_solution(monkeypatch):
    cfg = _cfg(); cfg["update_interval"] = 1
    params = _params(); state = np.array([0.02, -0.15, 0.35, 0.0]); action = np.array([0.1, 0.0])
    estimator = MultipleShootingInverseMassMHE(params, cfg); estimator.reset(state, warm_state=state)
    estimator.last_states = np.tile(state, (4, 1))
    monkeypatch.setattr(estimator, "_least_squares", lambda *args: (None, np.empty((0, 4)), np.nan))
    result = estimator.add_measurement(action, state, warm_state=state)
    expected = step_dynamics(state, action, params["dt"], params)
    assert not result["success"]
    assert np.allclose(result["state_hat"], expected)
    assert estimator.last_states is None
