"""Run a small policy suite for Spring2D moving-base environment validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.visualization.animate_spring2d import (
    save_spring2d_animation,
    save_spring2d_summary,
)


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_policies.yaml"

PolicyFn = Callable[[Spring2DEnv, dict[str, Any], dict[str, Any]], np.ndarray]


def load_config(path: Path) -> dict[str, Any]:
    with Path(path).open("r") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")
    return cfg


def load_policy_config(path: Path) -> dict[str, Any]:
    policy_cfg = load_config(path)
    base_config = policy_cfg.get("base_config", "configs/spring2d.yaml")
    base_path = _resolve_project_path(base_config)
    cfg = load_config(base_path)
    cfg["run"] = policy_cfg.get("run", cfg.get("run", {}))
    cfg["policies"] = policy_cfg.get("policies", {})
    cfg["outputs"] = policy_cfg.get("outputs", cfg.get("outputs", {}))
    return cfg


def policy_zero_force(
    env: Spring2DEnv,
    policy_cfg: dict[str, Any],
    full_cfg: dict[str, Any],
) -> np.ndarray:
    return np.array([0.0, 0.0], dtype=float)


def policy_constant_tangential_force(
    env: Spring2DEnv,
    policy_cfg: dict[str, Any],
    full_cfg: dict[str, Any],
) -> np.ndarray:
    return np.array([float(policy_cfg["F_tan_const"]), 0.0], dtype=float)


def policy_constant_radial_force(
    env: Spring2DEnv,
    policy_cfg: dict[str, Any],
    full_cfg: dict[str, Any],
) -> np.ndarray:
    return np.array([0.0, float(policy_cfg["F_rad_const"])], dtype=float)


def policy_omega_tracking_pd(
    env: Spring2DEnv,
    policy_cfg: dict[str, Any],
    full_cfg: dict[str, Any],
) -> np.ndarray:
    _, omega, _, _ = env.state
    omega_dot = 0.0
    if env.history:
        omega_dot = float(env.history[-1].get("omega_dot", 0.0))

    F_tan = (
        float(policy_cfg["Kp_omega"]) * (float(policy_cfg["omega_ref"]) - float(omega))
        - float(policy_cfg["Kd_omega"]) * omega_dot
    )
    return np.array([F_tan, 0.0], dtype=float)


POLICIES: dict[str, PolicyFn] = {
    "zero_force": policy_zero_force,
    "constant_tangential_force": policy_constant_tangential_force,
    "constant_radial_force": policy_constant_radial_force,
    "omega_tracking_pd": policy_omega_tracking_pd,
}


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _series(history: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([row[key] for row in history], dtype=float)


def run_single_policy(
    policy_name: str,
    cfg: dict[str, Any],
    log_dir: Path,
    video_dir: Path,
    figure_dir: Path,
) -> Spring2DEnv:
    if policy_name not in POLICIES:
        raise ValueError(f"Unknown policy '{policy_name}'. Options: {sorted(POLICIES)}")

    params = cfg["params"]
    policy_cfg = cfg.get("policies", {}).get(policy_name, {})
    env = Spring2DEnv(params)
    env.reset()
    policy = POLICIES[policy_name]

    while not env.is_done():
        action = policy(env, policy_cfg, cfg)
        env.step(action)

    csv_path = log_dir / policy_name / "timeseries.csv"
    gif_path = video_dir / f"{policy_name}.gif"
    summary_path = figure_dir / f"{policy_name}_summary.png"

    env.save_history(csv_path)
    history = env.get_history()
    save_spring2d_summary(history, params, summary_path)
    save_spring2d_animation(
        history,
        params,
        gif_path,
        fps=int(cfg.get("outputs", {}).get("fps", 25)),
    )

    return env


def save_policy_comparison(
    histories: dict[str, list[dict[str, Any]]],
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    panels = [
        ("theta", "theta [deg]", lambda h: np.degrees(_series(h, "theta"))),
        ("omega", "omega [rad/s]", lambda h: _series(h, "omega")),
        ("r", "r [m]", lambda h: _series(h, "r")),
        ("delta_r", "delta_r [mm]", lambda h: 1000.0 * _series(h, "delta_r")),
        ("F_tan", "F_tan [N]", lambda h: _series(h, "F_tan")),
        ("F_rad", "F_rad [N]", lambda h: _series(h, "F_rad")),
        ("base_x", "base_x [m]", lambda h: _series(h, "base_x")),
    ]

    fig, axes = plt.subplots(4, 2, figsize=(13, 12), sharex=False)
    axes_flat = axes.ravel()
    for ax, (_, ylabel, getter) in zip(axes_flat, panels):
        for policy_name, history in histories.items():
            t = _series(history, "t")
            ax.plot(t, getter(history), label=policy_name)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)

    axes_flat[len(panels)].axis("off")
    axes_flat[len(panels)].legend(
        *axes_flat[0].get_legend_handles_labels(),
        loc="center",
        frameon=False,
    )
    for ax in axes_flat[-2:]:
        ax.set_xlabel("time [s]")

    fig.suptitle("Spring2D Open-Loop / Hand-Coded Policy Comparison")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def summarize_env(policy_name: str, env: Spring2DEnv) -> dict[str, Any]:
    history = env.history
    return {
        "policy": policy_name,
        "done_reason": env.done_reason,
        "steps": len(history),
        "final_time": float(history[-1]["t"]),
        "final_theta_deg": float(np.degrees(history[-1]["theta"])),
        "final_omega": float(history[-1]["omega"]),
        "max_abs_delta_r_mm": float(max(abs(row["delta_r"]) for row in history) * 1000.0),
        "max_abs_F_tan": float(max(abs(row["F_tan"]) for row in history)),
        "max_abs_F_rad": float(max(abs(row["F_rad"]) for row in history)),
    }


def run(config_path: Path) -> dict[str, Spring2DEnv]:
    cfg = load_policy_config(config_path)
    outputs = cfg.get("outputs", {})
    log_dir = _resolve_project_path(outputs.get("log_dir", "results/logs/spring2d_policies"))
    video_dir = _resolve_project_path(outputs.get("video_dir", "results/videos/spring2d_policies"))
    figure_dir = _resolve_project_path(outputs.get("figure_dir", "results/figures/spring2d_policies"))
    comparison_path = _resolve_project_path(
        outputs.get("comparison_png", "results/figures/spring2d_policies/policy_comparison.png")
    )

    policy_order = cfg.get("run", {}).get("policy_order", list(POLICIES))
    envs: dict[str, Spring2DEnv] = {}
    summaries = []
    for policy_name in policy_order:
        env = run_single_policy(policy_name, cfg, log_dir, video_dir, figure_dir)
        envs[policy_name] = env
        summaries.append(summarize_env(policy_name, env))

    save_policy_comparison({name: env.history for name, env in envs.items()}, comparison_path)

    print("Spring2D policy validation")
    print(f"  config     : {config_path}")
    print(f"  log dir    : {log_dir}")
    print(f"  video dir  : {video_dir}")
    print(f"  figure dir : {figure_dir}")
    print(f"  comparison : {comparison_path}")
    for item in summaries:
        print(
            "  "
            f"{item['policy']}: done={item['done_reason']}, "
            f"steps={item['steps']}, "
            f"t={item['final_time']:.2f}s, "
            f"theta={item['final_theta_deg']:.2f}deg, "
            f"omega={item['final_omega']:.3f}rad/s, "
            f"max|dr|={item['max_abs_delta_r_mm']:.2f}mm, "
            f"max|Ftan|={item['max_abs_F_tan']:.2f}N, "
            f"max|Frad|={item['max_abs_F_rad']:.2f}N"
        )
    return envs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
