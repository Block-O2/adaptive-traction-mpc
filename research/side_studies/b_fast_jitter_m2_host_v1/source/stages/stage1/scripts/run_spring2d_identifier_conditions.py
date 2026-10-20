"""Run Spring2D parameter-mismatch identifier condition comparisons."""

from __future__ import annotations

import argparse
import csv
import sys
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.evaluation.plot_identifier_conditions import (
    save_identifier_conditions_comparison,
    save_identifier_summary_table,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.mpc.fixed_mpc import FixedModelMPC
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_identifier_conditions.yaml"


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


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_experiment_config(path: Path) -> dict[str, Any]:
    cfg = load_yaml(path)
    base_cfg = load_yaml(_resolve_project_path(cfg.get("base_config", "configs/spring2d.yaml")))
    mpc_cfg = load_yaml(_resolve_project_path(cfg.get("mpc_config", "configs/spring2d_fixed_mpc.yaml")))

    true_params = dict(base_cfg["params"])
    true_params.update(cfg.get("true_param_overrides", {}))
    model_params = dict(base_cfg["params"])
    model_params.update(cfg.get("initial_model_overrides", {}))
    mpc_params = deep_update(mpc_cfg["mpc"], cfg.get("mpc_overrides", {}))
    return {
        "true_params": true_params,
        "model_params": model_params,
        "mpc_params": mpc_params,
        "identifier": cfg["identifier"],
        "run": cfg.get("run", {}),
        "conditions": cfg["conditions"],
        "outputs": cfg["outputs"],
    }


def append_identifier_fields(
    row: dict[str, Any],
    obs_state: np.ndarray,
    result: Any,
) -> dict[str, Any]:
    enriched = dict(row)
    theta_hat = result.theta_hat
    enriched.update(
        {
            "theta_obs": float(obs_state[0]),
            "omega_obs": float(obs_state[1]),
            "r_obs": float(obs_state[2]),
            "r_dot_obs": float(obs_state[3]),
            "m_hat": float(theta_hat["m"]),
            "k_hat": float(theta_hat["k"]),
            "b_r_hat": float(theta_hat["b_r"]),
            "prediction_error": float(result.prediction_error),
            "identifier_updated": bool(result.updated),
            "identifier_samples": int(result.num_samples),
            "identifier_success": bool(result.success),
        }
    )
    return enriched


def initial_identifier_result(identifier: WindowedLeastSquaresIdentifier) -> Any:
    return SimpleNamespace(
        theta_hat=identifier.get_parameter_estimate(),
        prediction_error=np.nan,
        updated=False,
        num_samples=0,
        success=True,
    )


def run_condition(
    condition_name: str,
    condition_cfg: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(
        true_params,
        condition_cfg.get("observation_noise", {}),
        seed=int(condition_cfg.get("seed", 0)),
    )
    obs_meas = wrapper.observe(obs_true)
    controller = FixedModelMPC(model_params, cfg["mpc_params"])
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()

    rows: list[dict[str, Any]] = []
    rows.append(
        append_identifier_fields(
            env.get_history()[-1],
            observation_to_state(obs_meas),
            initial_identifier_result(identifier),
        )
    )

    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    while not env.is_done() and steps < max_steps:
        action = controller.act(obs_meas)
        for _ in range(hold_steps):
            prev_obs_meas = obs_meas
            obs_true = env.step(action)
            obs_meas = wrapper.observe(obs_true)
            result = identifier.add_transition(
                observation_to_state(prev_obs_meas),
                np.asarray(action, dtype=float),
                observation_to_state(obs_meas),
            )
            rows.append(
                append_identifier_fields(
                    env.get_history()[-1],
                    observation_to_state(obs_meas),
                    result,
                )
            )
            steps += 1
            if env.is_done() or steps >= max_steps:
                break

    return rows


def write_condition_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path) -> dict[str, list[dict[str, Any]]]:
    cfg = load_experiment_config(config_path)
    outputs = cfg["outputs"]
    log_dir = _resolve_project_path(outputs.get("log_dir", "results/logs/spring2d_identifier_conditions"))
    figure_path = _resolve_project_path(
        outputs.get(
            "figure",
            "results/figures/spring2d_identifier_conditions/identifier_conditions_comparison.png",
        )
    )
    summary_path = _resolve_project_path(
        outputs.get("summary_table", "results/figures/spring2d_identifier_conditions/summary_table.csv")
    )
    video_dir = _resolve_project_path(outputs.get("video_dir", "results/videos/spring2d_identifier_conditions"))
    fps = int(outputs.get("fps", 25))

    all_rows: dict[str, list[dict[str, Any]]] = {}
    for condition_name, condition_cfg in cfg["conditions"].items():
        rows = run_condition(condition_name, condition_cfg, cfg)
        all_rows[condition_name] = rows
        write_condition_csv(rows, log_dir / condition_name / "timeseries.csv")
        save_spring2d_animation(rows, cfg["true_params"], video_dir / f"{condition_name}.gif", fps=fps)

    save_identifier_conditions_comparison(all_rows, cfg["true_params"], figure_path)
    save_identifier_summary_table(all_rows, cfg["true_params"], summary_path)

    print("Spring2D identifier conditions")
    print(f"  config        : {config_path}")
    print(f"  log dir       : {log_dir}")
    print(f"  video dir     : {video_dir}")
    print(f"  figure        : {figure_path}")
    print(f"  summary table : {summary_path}")
    for condition_name, rows in all_rows.items():
        finite_errors = [float(row["prediction_error"]) for row in rows if np.isfinite(float(row["prediction_error"]))]
        first_err = finite_errors[0] if finite_errors else np.nan
        final_err = finite_errors[-1] if finite_errors else np.nan
        final = rows[-1]
        print(
            "  "
            f"{condition_name}: done={final['done_reason']}, "
            f"theta={np.degrees(float(final['theta'])):.2f}deg, "
            f"m_hat={float(final['m_hat']):.3f}, "
            f"k_hat={float(final['k_hat']):.2f}, "
            f"b_r_hat={float(final['b_r_hat']):.2f}, "
            f"pred_error={first_err:.5f}->{final_err:.5f}"
        )
    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
