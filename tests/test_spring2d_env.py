from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.envs.spring2d_env import SPRING2D_HISTORY_FIELDS, Spring2DEnv


def load_params() -> dict:
    with (PROJECT_ROOT / "configs" / "spring2d.yaml").open("r") as f:
        return yaml.safe_load(f)["params"]


def test_reset_returns_valid_observation() -> None:
    env = Spring2DEnv(load_params())
    obs = env.reset(seed=1)

    assert obs.t == 0.0
    assert np.isfinite([obs.theta, obs.omega, obs.r, obs.r_dot, obs.delta_r]).all()
    assert obs.base_pos.shape == (2,)
    assert obs.tip_pos.shape == (2,)
    assert obs.contact_pos.shape == (2,)
    assert obs.contact_vel.shape == (2,)
    assert isinstance(obs.r_ddot, float)
    assert isinstance(obs.omega_dot, float)
    assert isinstance(obs.base_x, float)
    assert isinstance(obs.base_a, float)
    assert isinstance(obs.base_ap, float)
    assert obs.done is False
    assert obs.done_reason is None
    assert list(env.get_history()[0].keys()) == SPRING2D_HISTORY_FIELDS


def test_step_advances_time() -> None:
    params = load_params()
    env = Spring2DEnv(params)
    env.reset()
    obs = env.step([0.0, 0.0])

    assert obs.t == pytest.approx(float(params["dt"]))
    assert len(env.get_history()) == 2


def test_invalid_action_shape_raises_clear_error() -> None:
    env = Spring2DEnv(load_params())
    env.reset()

    with pytest.raises(ValueError, match=r"shape \(2,\).*F_tan.*F_rad"):
        env.step([1.0])

    with pytest.raises(ValueError, match=r"shape \(2,\).*F_tan.*F_rad"):
        env.step([[1.0, 2.0]])


def test_get_observation_is_idempotent_for_contact_velocity() -> None:
    env = Spring2DEnv(load_params())
    env.reset()
    env.step([1.0, 0.0])

    obs_a = env.get_observation()
    obs_b = env.get_observation()

    np.testing.assert_allclose(obs_a.contact_vel, obs_b.contact_vel)


def test_save_history_uses_stable_columns(tmp_path: Path) -> None:
    env = Spring2DEnv(load_params())
    env.reset()
    env.step([0.0, 0.0])

    out_path = tmp_path / "timeseries.csv"
    env.save_history(out_path)
    header = out_path.read_text().splitlines()[0].split(",")

    assert header == SPRING2D_HISTORY_FIELDS
