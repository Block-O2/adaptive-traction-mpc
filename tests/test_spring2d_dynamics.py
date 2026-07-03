from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.models.spring2d_dynamics import compute_derivatives


def load_params() -> dict:
    with (PROJECT_ROOT / "configs" / "spring2d.yaml").open("r") as f:
        return yaml.safe_load(f)["params"]


def fixed_base_reference_derivatives(state: np.ndarray, action: np.ndarray, params: dict) -> np.ndarray:
    theta, omega, r, r_dot = np.asarray(state, dtype=float)
    F_tan, F_rad = np.asarray(action, dtype=float)
    m = float(params["m"])
    g = float(params["g"])
    L0 = float(params["L0"])
    k = float(params["k"])
    b_r = float(params["b_r"])
    b_theta = float(params["b_theta"])
    rho = float(params["rho"])
    r_eff = max(float(r), 1e-6)
    M_r = m / 3.0
    I = m * r_eff**2 / 3.0
    r_ddot = (
        M_r * r_eff * omega**2
        - k * (r_eff - L0)
        - b_r * r_dot
        - 0.5 * m * g * np.sin(theta)
        + rho * F_rad
    ) / M_r
    omega_dot = (
        rho * r_eff * F_tan
        - b_theta * omega
        - 0.5 * m * g * r_eff * np.cos(theta)
        - 2.0 * M_r * r_eff * r_dot * omega
    ) / I
    return np.array([omega, omega_dot, r_dot, r_ddot], dtype=float)


def test_linear_sin_zero_amp_matches_fixed_base_sanity() -> None:
    params = load_params()
    params["base_mode"] = "linear_sin"
    params["base_slide_amp"] = 0.0
    samples = [
        (np.array([0.2, 0.4, 0.35, -0.01]), np.array([3.0, 1.0])),
        (np.array([0.8, -0.2, 0.37, 0.02]), np.array([-2.0, 4.0])),
        (np.array([-0.3, 0.6, 0.34, -0.03]), np.array([1.5, -1.0])),
    ]

    for state, action in samples:
        actual = compute_derivatives(state, action, params)
        expected = fixed_base_reference_derivatives(state, action, params)
        np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)


def test_positive_tangential_force_pushes_theta_growth_trend() -> None:
    params = load_params()
    env = Spring2DEnv(params)
    initial = env.reset()

    for _ in range(30):
        env.step([0.5 * float(params["F_tan_max"]), 0.0])

    assert env.get_observation().theta > initial.theta


def test_positive_radial_force_pushes_r_growth_trend() -> None:
    params = load_params()
    params["theta_init"] = 0.0
    params["omega_init"] = 0.0
    params["r_dot_init"] = 0.0
    env = Spring2DEnv(params)
    initial = env.reset()

    for _ in range(20):
        env.step([0.0, 0.5 * float(params["F_rad_max"])])

    assert env.get_observation().r > initial.r
