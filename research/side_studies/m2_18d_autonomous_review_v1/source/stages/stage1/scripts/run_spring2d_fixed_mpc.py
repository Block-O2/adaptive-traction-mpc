"""Run the fixed-model MPC baseline on Spring2DEnv."""

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
from traction_mpc.mpc.fixed_mpc import FixedModelMPC
from traction_mpc.visualization.animate_spring2d import (
    save_spring2d_animation,
    save_spring2d_summary,
)


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_fixed_mpc.yaml"


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open("r") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")
    return cfg


def load_config(path: Path) -> dict[str, Any]:
    cfg = load_yaml(path)
    base_path = _resolve_project_path(cfg.get("base_config", "configs/spring2d.yaml"))
    base_cfg = load_yaml(base_path)
    return {
        "params": base_cfg["params"],
        "mpc": cfg["mpc"],
        "run": cfg.get("run", {}),
        "outputs": cfg.get("outputs", {}),
    }


def run(config_path: Path) -> Spring2DEnv:
    cfg = load_config(config_path)
    params = cfg["params"]
    mpc_params = cfg["mpc"]
    run_cfg = cfg.get("run", {})
    outputs = cfg.get("outputs", {})

    env = Spring2DEnv(params)
    obs = env.reset()
    controller = FixedModelMPC(params, mpc_params)
    controller.reset()

    hold_steps = int(run_cfg.get("control_hold_steps", 1))
    max_steps = int(run_cfg.get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        action = controller.act(obs)
        for _ in range(hold_steps):
            obs = env.step(action)
            steps += 1
            if env.is_done() or steps >= max_steps:
                break

    csv_path = _resolve_project_path(outputs.get("timeseries_csv", "results/logs/spring2d_fixed_mpc/timeseries.csv"))
    gif_path = _resolve_project_path(outputs.get("gif", "results/videos/spring2d_fixed_mpc.gif"))
    summary_path = _resolve_project_path(outputs.get("summary_png", "results/figures/spring2d_fixed_mpc_summary.png"))
    env.save_history(csv_path)
    history = env.get_history()
    save_spring2d_summary(history, params, summary_path)
    save_spring2d_animation(history, params, gif_path, fps=int(outputs.get("fps", 25)))

    max_abs_delta_r = max(abs(row["delta_r"]) for row in history)
    max_abs_F_tan = max(abs(row["F_tan"]) for row in history)
    max_abs_F_rad = max(abs(row["F_rad"]) for row in history)
    max_abs_alpha = max(abs(row["omega_dot"]) for row in history)
    print("Spring2D fixed-model MPC")
    print(f"  config           : {config_path}")
    print("  solver           : random_shooting")
    print(f"  done reason      : {env.done_reason}")
    print(f"  steps            : {len(history)}")
    print(f"  final theta      : {np.degrees(history[-1]['theta']):.2f} deg")
    print(f"  final omega      : {history[-1]['omega']:.3f} rad/s")
    print(f"  max |delta_r|    : {max_abs_delta_r * 1000.0:.2f} mm")
    print(f"  max |F_tan|      : {max_abs_F_tan:.2f} N")
    print(f"  max |F_rad|      : {max_abs_F_rad:.2f} N")
    print(f"  max |alpha|      : {max_abs_alpha:.3f} rad/s^2")
    print(f"  csv              : {csv_path}")
    print(f"  gif              : {gif_path}")
    print(f"  figure           : {summary_path}")
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
