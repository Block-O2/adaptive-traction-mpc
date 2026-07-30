import numpy as np

from traction_mpc.estimation.single_parameter_mhe import SingleParameterMHE
from traction_mpc.models.spring2d_dynamics import step_dynamics


def _params():
    return {
        "m": 1.0, "k": 450.0, "b_r": 20.0, "b_theta": 0.02, "g": 9.81, "L0": 0.35,
        "rho": 1.0, "base_mode": "linear_sin", "base_slide_amp": 0.035, "theta_init": 0.0,
        "base_x0": 0.0, "base_y0": 0.0, "dt": 0.01,
    }


def _cfg():
    return {
        "window_size": 4, "update_interval": 1, "max_nfev": 20,
        "measurement_weights": [1.0, 0.25, 8.0, 0.6], "arrival_state_scale": [0.1, 1.0, 0.02, 0.1],
        "lambda_arrival_state": 1.0e-3, "lambda_arrival_parameter": 1.0e-3, "mass_scale": 1.0,
        "mass_bounds": [0.5, 2.0], "xtol": 1.0e-8, "ftol": 1.0e-8, "gtol": 1.0e-8,
    }


def test_single_parameter_mhe_preserves_nominal_mass_on_noise_free_transition():
    params = _params(); state = np.array([0.02, -0.15, 0.35, 0.0]); action = np.array([0.1, 0.0])
    next_state = step_dynamics(state, action, params["dt"], params)
    estimator = SingleParameterMHE(params, _cfg(), "inverse_m")
    estimator.reset(state)
    result = estimator.add_measurement(action, next_state)
    assert result["success"]
    assert np.isfinite(result["m_hat"])
    assert 0.5 <= result["m_hat"] <= 2.0
    assert np.all(np.isfinite(result["state_hat"]))
