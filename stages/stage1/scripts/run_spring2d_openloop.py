"""Run open-loop / hand-coded policies in the Spring2D environment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.models.spring2d_dynamics import compute_base_position, compute_derivatives
from traction_mpc.visualization.animate_spring2d import (
    save_spring2d_animation,
    save_spring2d_summary,
)


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d.yaml"
DEFAULT_LOG_DIR = PROJECT_ROOT / "results" / "logs" / "spring2d_openloop"
DEFAULT_GIF = PROJECT_ROOT / "results" / "videos" / "spring2d_openloop.gif"
DEFAULT_FIGURE = PROJECT_ROOT / "results" / "figures" / "spring2d_summary.png"


def load_config(path: Path) -> dict[str, Any]:
    with Path(path).open("r") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")
    return cfg


def policy_zero_force(env: Spring2DEnv, cfg: dict[str, Any]) -> np.ndarray:
    return np.array([0.0, 0.0], dtype=float)


def policy_constant_tangential(env: Spring2DEnv, cfg: dict[str, Any]) -> np.ndarray:
    return np.array([float(cfg["policy"]["constant_F_tan"]), 0.0], dtype=float)


def policy_pd_theta(env: Spring2DEnv, cfg: dict[str, Any]) -> np.ndarray:
    gains = cfg["policy"]
    theta_target = float(env.params["theta_target"])
    theta, omega, _, _ = env.state
    F_tan = float(gains["kp_theta"]) * (theta_target - theta) - float(gains["kd_theta"]) * omega
    return np.array([F_tan, 0.0], dtype=float)


def policy_pd_omega(env: Spring2DEnv, cfg: dict[str, Any]) -> np.ndarray:
    gains = cfg["policy"]
    theta, omega, _, _ = env.state
    theta_target = float(env.params["theta_target"])
    omega_des = float(gains["omega_des"])
    if theta > theta_target - np.radians(float(gains.get("slowdown_deg", 8.0))):
        omega_des = 0.0
    F_tan = float(gains["kp_omega"]) * (omega_des - omega)
    F_rad = float(gains.get("radial_bias", 0.0))
    return np.array([F_tan, F_rad], dtype=float)


POLICIES = {
    "zero": policy_zero_force,
    "constant_tangential": policy_constant_tangential,
    "pd_theta": policy_pd_theta,
    "pd_omega": policy_pd_omega,
}


def fixed_base_reference_derivatives(state: np.ndarray, action: np.ndarray, params: dict[str, Any]) -> np.ndarray:
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


def run_sanity_checks(params: dict[str, Any]) -> dict[str, bool]:
    results: dict[str, bool] = {}

    fixed_param_sets = []
    fixed_linear = dict(params)
    fixed_linear["base_mode"] = "linear_sin"
    fixed_linear["base_slide_amp"] = 0.0
    fixed_param_sets.append(fixed_linear)

    fixed_tanh = dict(params)
    fixed_tanh["base_mode"] = "tanh_sin"
    fixed_tanh["base_x_range"] = 0.0
    fixed_param_sets.append(fixed_tanh)

    samples = [
        (np.array([0.2, 0.4, 0.35, -0.01]), np.array([3.0, 1.0])),
        (np.array([0.8, -0.2, 0.37, 0.02]), np.array([-2.0, 4.0])),
        (np.array([-0.3, 0.6, 0.34, -0.03]), np.array([1.5, -1.0])),
    ]
    fixed_ok = True
    for fixed_params in fixed_param_sets:
        for state, action in samples:
            moving = compute_derivatives(state, action, fixed_params)
            reference = fixed_base_reference_derivatives(state, action, fixed_params)
            fixed_ok = fixed_ok and bool(np.allclose(moving, reference, atol=1e-10, rtol=1e-10))
    results["fixed_base"] = fixed_ok

    zero_env = Spring2DEnv(params)
    zero_obs0 = zero_env.reset()
    for _ in range(40):
        zero_env.step([0.0, 0.0])
    zero_obs = zero_env.get_observation()
    results["zero_force_gravity"] = zero_obs.theta < zero_obs0.theta

    tan_env = Spring2DEnv(params)
    tan_obs0 = tan_env.reset()
    for _ in range(30):
        tan_env.step([0.5 * float(params["F_tan_max"]), 0.0])
    tan_obs = tan_env.get_observation()
    results["positive_F_tan"] = tan_obs.theta > tan_obs0.theta

    rad_params = dict(params)
    rad_params["theta_init"] = 0.0
    rad_params["omega_init"] = 0.0
    rad_params["r_dot_init"] = 0.0
    rad_env = Spring2DEnv(rad_params)
    rad_obs0 = rad_env.reset()
    for _ in range(20):
        rad_env.step([0.0, 0.5 * float(rad_params["F_rad_max"])])
    rad_obs = rad_env.get_observation()
    results["positive_F_rad"] = rad_obs.r > rad_obs0.r

    thetas = np.linspace(float(params["theta_init"]), float(params["theta_target"]), 50)
    base_x = np.array([compute_base_position(th, params)[0] for th in thetas])
    finite = np.all(np.isfinite(base_x))
    smooth = np.max(np.abs(np.diff(base_x))) < 0.25
    changes = abs(base_x[-1] - base_x[0]) > 1e-5
    results["base_x_smooth"] = bool(finite and smooth and changes)

    failed = [name for name, ok in results.items() if not ok]
    if failed:
        raise AssertionError(f"Spring2D sanity checks failed: {failed}")
    return results


def run(config_path: Path, policy_name: str | None = None) -> Spring2DEnv:
    cfg = load_config(config_path)
    params = cfg["params"]
    sanity = run_sanity_checks(params)
    selected_policy = policy_name or cfg.get("run", {}).get("policy", "pd_omega")
    if selected_policy not in POLICIES:
        raise ValueError(f"Unknown policy '{selected_policy}'. Options: {sorted(POLICIES)}")

    env = Spring2DEnv(params)
    env.reset()
    policy = POLICIES[selected_policy]

    while not env.is_done():
        action = policy(env, cfg)
        env.step(action)

    csv_path = PROJECT_ROOT / cfg["outputs"].get("timeseries_csv", str(DEFAULT_LOG_DIR / "timeseries.csv"))
    gif_path = PROJECT_ROOT / cfg["outputs"].get("gif", str(DEFAULT_GIF))
    figure_path = PROJECT_ROOT / cfg["outputs"].get("summary_png", str(DEFAULT_FIGURE))

    env.save_history(csv_path)
    history = env.get_history()
    save_spring2d_summary(history, params, figure_path)
    save_spring2d_animation(history, params, gif_path, fps=int(cfg["outputs"].get("fps", 25)))

    print("Spring2D open-loop run")
    print(f"  config      : {config_path}")
    print(f"  policy      : {selected_policy}")
    print(f"  sanity      : {', '.join(name for name, ok in sanity.items() if ok)}")
    print(f"  done reason : {env.done_reason}")
    print(f"  steps       : {len(env.history)}")
    print(f"  final theta : {np.degrees(env.history[-1]['theta']):.2f} deg")
    print(f"  max |dr|    : {max(abs(row['delta_r']) for row in env.history) * 1000.0:.2f} mm")
    print(f"  csv         : {csv_path}")
    print(f"  gif         : {gif_path}")
    print(f"  figure      : {figure_path}")
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--policy", choices=sorted(POLICIES), default=None)
    args = parser.parse_args()
    run(args.config, args.policy)


if __name__ == "__main__":
    main()
