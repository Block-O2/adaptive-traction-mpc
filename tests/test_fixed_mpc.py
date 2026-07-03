from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.mpc.fixed_mpc import FixedModelMPC


def load_configs() -> tuple[dict, dict]:
    with (PROJECT_ROOT / "configs" / "spring2d.yaml").open("r") as f:
        params = yaml.safe_load(f)["params"]
    with (PROJECT_ROOT / "configs" / "spring2d_fixed_mpc.yaml").open("r") as f:
        mpc = yaml.safe_load(f)["mpc"]
    return params, mpc


def test_fixed_mpc_returns_feasible_action() -> None:
    params, mpc = load_configs()
    fast_mpc = dict(mpc)
    fast_mpc["solver"] = dict(mpc["solver"])
    fast_mpc["solver"]["num_samples"] = 12
    fast_mpc["solver"]["iterations"] = 1

    env = Spring2DEnv(params)
    obs = env.reset()
    controller = FixedModelMPC(params, fast_mpc)
    action = controller.act(obs)

    assert action.shape == (2,)
    assert np.isfinite(action).all()
    assert abs(action[0]) <= params["F_tan_max"]
    assert abs(action[1]) <= params["F_rad_max"]


def test_fixed_mpc_short_rollout_increases_theta() -> None:
    params, mpc = load_configs()
    fast_mpc = dict(mpc)
    fast_mpc["solver"] = dict(mpc["solver"])
    fast_mpc["solver"]["num_samples"] = 16
    fast_mpc["solver"]["iterations"] = 1

    env = Spring2DEnv(params)
    obs = env.reset()
    theta0 = obs.theta
    controller = FixedModelMPC(params, fast_mpc)
    for _ in range(8):
        action = controller.act(obs)
        obs = env.step(action)
        if env.is_done():
            break

    assert obs.theta > theta0
