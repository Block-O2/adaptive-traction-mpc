"""Run adaptive MPC closed-loop conditions for Spring2D."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traction_mpc.estimation.noisy_observation_wrapper import (
    NoisySpring2DObservationWrapper,
    observation_to_state,
)
from traction_mpc.evaluation.plot_adaptive_mpc_conditions import (
    save_adaptive_mpc_conditions_comparison,
    save_adaptive_mpc_summary_table,
)
from traction_mpc.envs.spring2d_env import Spring2DEnv
from traction_mpc.identification.windowed_ls_identifier import WindowedLeastSquaresIdentifier
from traction_mpc.mpc.adaptive_mpc import AdaptiveMPC
from traction_mpc.visualization.animate_spring2d import save_spring2d_animation


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "spring2d_adaptive_mpc_conditions.yaml"


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
    source_cfg = load_yaml(_resolve_project_path(cfg["identifier_conditions_config"]))
    base_cfg = load_yaml(_resolve_project_path(source_cfg.get("base_config", "configs/spring2d.yaml")))
    mpc_cfg = load_yaml(_resolve_project_path(source_cfg.get("mpc_config", "configs/spring2d_fixed_mpc.yaml")))

    true_params = dict(base_cfg["params"])
    true_params.update(source_cfg.get("true_param_overrides", {}))
    model_params = dict(base_cfg["params"])
    model_params.update(source_cfg.get("initial_model_overrides", {}))
    mpc_params = deep_update(mpc_cfg["mpc"], source_cfg.get("mpc_overrides", {}))
    return {
        "true_params": true_params,
        "model_params": model_params,
        "mpc_params": mpc_params,
        "identifier": source_cfg["identifier"],
        "run": source_cfg.get("run", {}),
        "conditions": source_cfg["conditions"],
        "adaptive": cfg.get("adaptive", {}),
        "outputs": cfg["outputs"],
        "baseline_summary_table": cfg.get("baseline_summary_table"),
    }


def initial_identifier_result(identifier: WindowedLeastSquaresIdentifier) -> Any:
    return SimpleNamespace(
        theta_hat=identifier.get_parameter_estimate(),
        prediction_error=np.nan,
        updated=False,
        num_samples=0,
        success=True,
    )


def append_adaptive_fields(
    row: dict[str, Any],
    obs_state: np.ndarray,
    result: Any,
    controller: AdaptiveMPC,
    parameter_update_flag: bool,
    target_theta: float,
    alpha_step: float,
    solve_diagnostics: dict[str, Any] | None = None,
    update_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(row)
    theta_hat = result.theta_hat
    theta_mpc = controller.get_current_parameter_estimate()
    solve_diag = solve_diagnostics or {}
    update_diag = update_diagnostics or {}
    enriched.update(
        {
            "theta_obs": float(obs_state[0]),
            "omega_obs": float(obs_state[1]),
            "r_obs": float(obs_state[2]),
            "r_dot_obs": float(obs_state[3]),
            "m_hat": float(theta_hat["m"]),
            "k_hat": float(theta_hat["k"]),
            "b_r_hat": float(theta_hat["b_r"]),
            "m_mpc": float(theta_mpc["m"]),
            "k_mpc": float(theta_mpc["k"]),
            "b_r_mpc": float(theta_mpc["b_r"]),
            "m_mpc_used": float(theta_mpc["m"]),
            "k_mpc_used": float(theta_mpc["k"]),
            "b_r_mpc_used": float(theta_mpc["b_r"]),
            "theta_mpc_used": f"{float(theta_mpc['m']):.9g},{float(theta_mpc['k']):.9g},{float(theta_mpc['b_r']):.9g}",
            "prediction_error": float(result.prediction_error),
            "identifier_updated": bool(result.updated),
            "identifier_samples": int(result.num_samples),
            "identifier_success": bool(result.success),
            "parameter_update_flag": bool(parameter_update_flag),
            "target_reached": bool(float(row["theta"]) >= target_theta),
            "alpha_step": float(alpha_step),
            "omega_dot_continuous": float(row.get("omega_dot", np.nan)),
            "mpc_recreated_on_update": bool(update_diag.get("mpc_recreated_on_update", False)) if parameter_update_flag else False,
            "solver_recreated_on_update": bool(update_diag.get("solver_recreated_on_update", False)) if parameter_update_flag else False,
            "mpc_recreated_flag": bool(update_diag.get("mpc_recreated_on_update", False)) if parameter_update_flag else False,
            "solver_recreated_flag": bool(update_diag.get("solver_recreated_on_update", False)) if parameter_update_flag else False,
            "last_action_preserved_on_update": bool(update_diag.get("last_action_preserved_on_update", False)) if parameter_update_flag else False,
            "last_solution_existed_before_update": bool(update_diag.get("last_solution_existed_before_update", False)) if parameter_update_flag else False,
            "last_solution_preserved_on_update": bool(update_diag.get("last_solution_preserved_on_update", False)) if parameter_update_flag else False,
            "mpc_solve_count": int(solve_diag.get("mpc_solve_count", 0)),
            "last_solution_existed_before_solve": bool(solve_diag.get("last_solution_existed_before_solve", False)),
            "last_solution_available_before_solve": bool(solve_diag.get("last_solution_existed_before_solve", False)),
            "warm_start_used": bool(solve_diag.get("warm_start_used", False)),
            "selected_sequence_first_F_tan": float(solve_diag.get("selected_sequence_first_F_tan", np.nan)),
            "selected_sequence_first_F_rad": float(solve_diag.get("selected_sequence_first_F_rad", np.nan)),
            "alpha_pred_max": float(solve_diag.get("alpha_pred_max", np.nan)),
            "mpc_result_cost": float(solve_diag.get("mpc_result_cost", np.nan)),
            "mpc_result_feasible": bool(solve_diag.get("mpc_result_feasible", False)),
        }
    )
    return enriched


def run_condition(
    condition_name: str,
    condition_cfg: dict[str, Any],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    true_params = cfg["true_params"]
    model_params = cfg["model_params"]
    adaptive_cfg = cfg.get("adaptive", {})
    alpha = float(adaptive_cfg.get("parameter_smoothing_alpha", 0.5))
    warmup_steps = int(adaptive_cfg.get("warmup_steps", 0))
    parameter_bounds = adaptive_cfg.get("parameter_bounds", cfg["identifier"].get("bounds", {}))
    target_theta = float(cfg["mpc_params"].get("target_theta", true_params["theta_target"]))

    env = Spring2DEnv(true_params)
    obs_true = env.reset()
    wrapper = NoisySpring2DObservationWrapper(
        true_params,
        condition_cfg.get("observation_noise", {}),
        seed=int(condition_cfg.get("seed", 0)),
    )
    obs_meas = wrapper.observe(obs_true)

    controller = AdaptiveMPC(model_params, cfg["mpc_params"])
    controller.reset()
    identifier = WindowedLeastSquaresIdentifier(model_params, cfg["identifier"])
    identifier.reset()

    rows: list[dict[str, Any]] = []
    rows.append(
        append_adaptive_fields(
            env.get_history()[-1],
            observation_to_state(obs_meas),
            initial_identifier_result(identifier),
            controller,
            parameter_update_flag=False,
            target_theta=target_theta,
            alpha_step=0.0,
        )
    )

    hold_steps = int(cfg.get("run", {}).get("control_hold_steps", 1))
    max_steps = int(cfg.get("run", {}).get("max_steps", 1200))
    steps = 0
    solve_diagnostics: dict[str, Any] = {}
    while not env.is_done() and steps < max_steps:
        action = controller.act(obs_meas)
        solve_diagnostics = controller.get_last_solve_diagnostics()
        for _ in range(hold_steps):
            prev_obs_meas = obs_meas
            prev_history_row = env.get_history()[-1]
            obs_true = env.step(action)
            obs_meas = wrapper.observe(obs_true)
            result = identifier.add_transition(
                observation_to_state(prev_obs_meas),
                np.asarray(action, dtype=float),
                observation_to_state(obs_meas),
            )
            steps += 1

            parameter_update_flag = False
            update_diagnostics: dict[str, Any] = {}
            if result.updated and steps >= warmup_steps:
                controller.update_parameters(result.theta_hat, alpha=alpha, bounds=parameter_bounds)
                update_diagnostics = controller.get_last_update_diagnostics()
                parameter_update_flag = True

            history_row = env.get_history()[-1]
            alpha_step = (float(history_row["omega"]) - float(prev_history_row["omega"])) / float(true_params["dt"])
            rows.append(
                append_adaptive_fields(
                    history_row,
                    observation_to_state(obs_meas),
                    result,
                    controller,
                    parameter_update_flag=parameter_update_flag,
                    target_theta=target_theta,
                    alpha_step=alpha_step,
                    solve_diagnostics=solve_diagnostics,
                    update_diagnostics=update_diagnostics,
                )
            )
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
    log_dir = _resolve_project_path(outputs.get("log_dir", "results/logs/spring2d_adaptive_mpc_conditions"))
    video_dir = _resolve_project_path(outputs.get("video_dir", "results/videos/spring2d_adaptive_mpc_conditions"))
    figure_path = _resolve_project_path(
        outputs.get(
            "figure",
            "results/figures/spring2d_adaptive_mpc_conditions/adaptive_conditions_comparison.png",
        )
    )
    summary_path = _resolve_project_path(
        outputs.get("summary_table", "results/figures/spring2d_adaptive_mpc_conditions/summary_table.csv")
    )
    baseline_path = (
        _resolve_project_path(cfg["baseline_summary_table"])
        if cfg.get("baseline_summary_table")
        else None
    )
    fps = int(outputs.get("fps", 25))

    all_rows: dict[str, list[dict[str, Any]]] = {}
    for condition_name, condition_cfg in cfg["conditions"].items():
        rows = run_condition(condition_name, condition_cfg, cfg)
        all_rows[condition_name] = rows
        write_condition_csv(rows, log_dir / condition_name / "timeseries.csv")
        save_spring2d_animation(rows, cfg["true_params"], video_dir / f"{condition_name}.gif", fps=fps)

    save_adaptive_mpc_conditions_comparison(
        all_rows,
        cfg["true_params"],
        figure_path,
        mpc_constraints=cfg["mpc_params"].get("constraints", {}),
    )
    save_adaptive_mpc_summary_table(all_rows, cfg["true_params"], summary_path, baseline_path)

    print("Spring2D adaptive MPC conditions")
    print(f"  config        : {config_path}")
    print(f"  log dir       : {log_dir}")
    print(f"  video dir     : {video_dir}")
    print(f"  figure        : {figure_path}")
    print(f"  summary table : {summary_path}")
    for condition_name, rows in all_rows.items():
        final = rows[-1]
        finite_errors = [float(row["prediction_error"]) for row in rows if np.isfinite(float(row["prediction_error"]))]
        first_err = finite_errors[0] if finite_errors else np.nan
        final_err = finite_errors[-1] if finite_errors else np.nan
        print(
            "  "
            f"{condition_name}: done={final['done_reason']}, "
            f"target_reached={final['target_reached']}, "
            f"theta={np.degrees(float(final['theta'])):.2f}deg, "
            f"m_mpc={float(final['m_mpc']):.3f}, "
            f"k_mpc={float(final['k_mpc']):.2f}, "
            f"b_r_mpc={float(final['b_r_mpc']):.2f}, "
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
