#!/usr/bin/env python3
"""Fit and report the Stage-5 offline shadow remaining-force value study."""

from __future__ import annotations

import argparse
from functools import partial
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.shadow_value import (
    FailurePenaltySpec,
    build_features,
    coefficient_report,
    load_episode_value_data,
    regression_metrics,
    select_ridge_alpha,
    trajectory_split_is_disjoint,
)


DEFAULT_CONFIG = STAGE5_ROOT / "configs" / "stage5_shadow_value_v1.json"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "shadow_value_v1_offline_smoke"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _feature_builder(task: dict[str, Any], kind: str):
    return partial(
        build_features,
        kind=kind,
        phase_timeout_s=float(task["phase_timeout_s"]),
        hold_duration_s=float(task["hold_duration_s"]),
        start_rad=np.radians(task["start_return_target_deg"]),
        goal_rad=np.radians(task["outbound_goal_target_deg"]),
        q_bounds_rad=np.radians(task["q_bounds_deg"]),
        velocity_limits_rad_s=np.radians(task["task_joint_velocity_limit_deg_s"]),
    )


def _stack(episodes, builder):
    matrices = [builder(episode) for episode in episodes]
    names = matrices[0].names
    if any(matrix.names != names for matrix in matrices):
        raise ValueError("feature schemas changed across episodes")
    values = np.vstack([matrix.values for matrix in matrices])
    targets = np.concatenate(
        [episode.target_remaining_force_n_s[episode.active_mask] for episode in episodes]
    )
    ids = np.concatenate(
        [
            np.full(np.count_nonzero(episode.active_mask), episode.episode_id, dtype=str)
            for episode in episodes
        ]
    )
    phases = np.concatenate([episode.phase[episode.active_mask] for episode in episodes])
    return type(matrices[0])(values, names), targets, ids, phases


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = _load_json(config_path)
    if config.get("schema") != "stage5_shadow_value_v1":
        raise ValueError("unexpected shadow-value config schema")
    task_path = STAGE5_ROOT / config["frozen_condition"]["goal_task_config"]
    task = _load_json(task_path)
    penalty_config = config["failure_target"]
    penalty = FailurePenaltySpec(
        engineering_force_gate_n=float(penalty_config["engineering_force_gate_n"]),
        phase_timeout_s=float(penalty_config["phase_timeout_s"]),
        minimum_equivalent_duration_s=float(
            penalty_config["minimum_equivalent_duration_s"]
        ),
    )
    condition = config["frozen_condition"]
    split_config = config["episode_split"]
    split_ids = {
        name: [row["episode_id"] for row in split_config[name]]
        for name in ("train", "validation", "test")
    }
    if not trajectory_split_is_disjoint(split_ids):
        raise ValueError("train/validation/test rollout split is not disjoint")

    episodes: dict[str, list[Any]] = {}
    for split_name in ("train", "validation", "test"):
        episodes[split_name] = []
        for row in split_config[split_name]:
            directory = STAGE5_ROOT / row["directory"]
            episodes[split_name].append(
                load_episode_value_data(
                    row["episode_id"],
                    directory / "trace.npz",
                    directory / "summary.json",
                    expected_model_version=condition["human_model_version"],
                    expected_gamma=float(condition["pacing"]["gamma"]),
                    expected_interface_version=condition["interface_version"],
                    failure_penalty=penalty,
                )
            )

    model_config = config["model"]
    fitted: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    coefficient_tables: dict[str, Any] = {}
    for kind in ("baseline", "candidate"):
        builder = _feature_builder(task, kind)
        train_matrix, train_target, train_ids, train_phase = _stack(
            episodes["train"], builder
        )
        validation_matrix, validation_target, _, validation_phase = _stack(
            episodes["validation"], builder
        )
        test_matrix, test_target, _, test_phase = _stack(episodes["test"], builder)
        model, alpha_rows = select_ridge_alpha(
            train_matrix,
            train_target,
            train_ids,
            validation_matrix,
            validation_target,
            feature_kind=kind,
            alphas=model_config["ridge_alphas"],
            support_abs_z_limit=float(model_config["support_abs_z_limit"]),
        )
        fitted[kind] = model
        metrics[kind] = {
            "alpha_selection": alpha_rows,
            "selected_alpha": model.ridge_alpha,
            "train": regression_metrics(
                model, train_matrix, train_target, train_phase
            ),
            "validation": regression_metrics(
                model, validation_matrix, validation_target, validation_phase
            ),
            "test": regression_metrics(model, test_matrix, test_target, test_phase),
        }
        coefficient_tables[kind] = coefficient_report(model)

    baseline_rmse = float(metrics["baseline"]["test"]["rmse_n_s"])
    candidate_rmse = float(metrics["candidate"]["test"]["rmse_n_s"])
    baseline_beaten = candidate_rmse < baseline_rmse
    all_episodes = sum(
        (episodes[name] for name in ("train", "validation", "test")), []
    )
    start_rad = np.radians(task["start_return_target_deg"])
    goal_rad = np.radians(task["outbound_goal_target_deg"])
    task_span = goal_rad - start_rad
    exploratory_rows = []
    for episode in all_episodes:
        state = episode.feature_context["estimated_state"]
        coordinate = (state[:, :2] - start_rad) / task_span
        coordination_difference = np.abs(coordinate[:, 0] - coordinate[:, 1])
        duration_s = float(episode.time_s[-1] - episode.time_s[0])
        force_integral_n_s = float(episode.target_remaining_force_n_s[0])
        exploratory_rows.append(
            {
                "episode_id": episode.episode_id,
                "duration_s": duration_s,
                "force_integral_n_s": force_integral_n_s,
                "time_normalized_mean_force_n": force_integral_n_s / duration_s,
                "mean_abs_q1_q2_task_coordinate_difference": float(
                    np.mean(coordination_difference)
                ),
                "p95_abs_q1_q2_task_coordinate_difference": float(
                    np.percentile(coordination_difference, 95)
                ),
            }
        )
    durations = np.asarray([row["duration_s"] for row in exploratory_rows])
    force_integrals = np.asarray(
        [row["force_integral_n_s"] for row in exploratory_rows]
    )
    mean_forces = np.asarray(
        [row["time_normalized_mean_force_n"] for row in exploratory_rows]
    )
    start_context_keys = (
        "estimated_state",
        "interface_translation",
        "interface_velocity",
        "interface_rotation",
        "interface_angular_velocity",
        "measured_force",
        "measured_moment",
    )
    deployable_starts_equal = all(
        np.array_equal(
            all_episodes[0].feature_context[key][0],
            episode.feature_context[key][0],
        )
        for episode in all_episodes[1:]
        for key in start_context_keys
    )
    exploratory_path_signal = {
        "status": "EXPLORATORY_CONFOUNDED_NOT_RANKING_EVIDENCE",
        "deployable_start_fields_equal": bool(deployable_starts_equal),
        "episodes": exploratory_rows,
        "duration_force_integral_correlation": (
            float(np.corrcoef(durations, force_integrals)[0, 1])
            if len(durations) >= 3
            else None
        ),
        "force_integral_range_fraction_of_mean": float(
            np.ptp(force_integrals) / np.mean(force_integrals)
        ),
        "time_normalized_mean_force_range_fraction_of_mean": float(
            np.ptp(mean_forces) / np.mean(mean_forces)
        ),
        "posture_value_signal_proven": False,
        "reason": (
            "The rollouts share the recorded deployable start and show small path "
            "variation, but they are whole-policy seed repetitions rather than "
            "controlled equal-duration short branches. Force integral tracks episode "
            "duration, so faster completion remains the dominant confound."
        ),
    }
    minimum_per_split = int(
        config["decision_gates"]["minimum_complete_rollouts_per_split_for_readiness"]
    )
    adequate_rollouts = all(
        len(episodes[name]) >= minimum_per_split
        for name in ("train", "validation", "test")
    )
    branch_config = config["matched_branch_validation"]
    ranking = {
        "status": "NOT_RUN_NO_MATCHED_BRANCH_MANIFEST",
        "manifest": branch_config["manifest"],
        "matched_group_count": 0,
        "pair_count": 0,
        "ranking_accuracy": None,
        "same_start_state_verified": False,
        "timing_comparable_verified": False,
        "note": (
            "Existing fixed-pacing rollouts are policy repetitions, not multiple "
            "feasible short q1/q2 branches from the same saved state. Duration or "
            "seed differences cannot be relabeled as posture-ranking evidence."
        ),
    }
    ranking_ready = False
    if adequate_rollouts and baseline_beaten and ranking_ready:
        decision = "V-A"
        label = "SHADOW VALUE READY FOR CONTROL A/B"
    elif adequate_rollouts and baseline_beaten:
        decision = "V-B"
        label = "VALUE PREDICTION WORKS, PATH RANKING EVIDENCE INSUFFICIENT"
    else:
        decision = "V-C"
        label = "CURRENT DATA/STATE REPRESENTATION NOT SUFFICIENT"

    result = {
        "schema": "stage5_shadow_value_v1_result",
        "evidence_category": "offline_shadow_smoke_not_formal_scientific_evidence",
        "config": str(config_path.relative_to(STAGE5_ROOT)),
        "frozen_condition": condition,
        "trajectory_split": {
            name: [episode.episode_id for episode in episodes[name]]
            for name in ("train", "validation", "test")
        },
        "split_disjoint": True,
        "target_audit": {
            name: [
                {
                    "episode_id": episode.episode_id,
                    "terminal_status": episode.terminal_status,
                    "terminal_penalty_n_s": episode.terminal_penalty_n_s,
                    "initial_remaining_force_n_s": float(
                        episode.target_remaining_force_n_s[0]
                    ),
                    "terminal_remaining_force_n_s": float(
                        episode.target_remaining_force_n_s[-1]
                    ),
                    "measured_force_field": "deployable_measured_cuff_force_world_n",
                }
                for episode in episodes[name]
            ]
            for name in ("train", "validation", "test")
        },
        "models": {name: model.to_dict() for name, model in fitted.items()},
        "metrics": metrics,
        "candidate_vs_baseline": {
            "baseline_test_rmse_n_s": baseline_rmse,
            "candidate_test_rmse_n_s": candidate_rmse,
            "candidate_strictly_beats_baseline": baseline_beaten,
            "relative_test_rmse_change": (
                (candidate_rmse - baseline_rmse) / baseline_rmse
                if baseline_rmse > 0.0
                else None
            ),
        },
        "exploratory_path_signal_audit": exploratory_path_signal,
        "coefficient_audit": coefficient_tables,
        "ranking": ranking,
        "support_gate": {
            "rule": config["control_authority"][
                "unsupported_terminal_rule_for_future_ab"
            ],
            "candidate_test_ood_fraction": metrics["candidate"]["test"][
                "ood_fraction"
            ],
            "unsupported_predictions_encoded_as_nan": True,
        },
        "readiness_gates": {
            "minimum_complete_rollouts_per_split": minimum_per_split,
            "adequate_rollout_count": adequate_rollouts,
            "candidate_beats_baseline": baseline_beaten,
            "matched_path_ranking_ready": ranking_ready,
        },
        "decision": {"code": decision, "label": label},
        "control_authority": {
            "value_connected_to_mpc": False,
            "learned_actor_or_policy": False,
            "goal_mpc_source_changed": False,
        },
        "open_issues": config["frozen_open_issues"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "shadow_value_results.json"
    with output_path.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.config, args.output_dir)


if __name__ == "__main__":
    main()
