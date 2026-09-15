#!/usr/bin/env python3
"""Diagnostic-only audit of the two frozen final-campaign issues.

The script reads the immutable campaign traces/summaries and produces compact
derived tables and plots.  It does not mutate controller state, parameters, or
campaign evidence and does not relabel the frozen EXIT-C result.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import resource
import statistics
import tempfile
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.mpc import HumanMPCConfig

from traction_mpc_stage5.controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    _estimator_observe,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.hold_stabilizer import (
    solve_loaded_hold_equilibrium,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    build_stage5_loaded_execution_context,
    human_cuff_wrench_to_robot_cuff_command,
    loaded_execution_target_from_equilibrium,
)
from traction_mpc_stage5.task import (
    GoalTaskState,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = (
    STAGE5_ROOT / "results" / "interface_robustness_final_campaign_v1"
)
DEFAULT_OUTPUT = CAMPAIGN_ROOT / "root_cause_audit_v1"
STARTUP_CONDITIONS = ("low_low_high", "high_low_high")
STARTUP_SEEDS = (20260824, 20260825, 20260826)
ACCEL_LIMIT_Q2_DEG_S2 = 600.0
MPC_INTERVAL_S = 0.020


def _fixed_human_model() -> Any:
    q0 = np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    pose = STAGE5_GEOMETRY.world_from_cuff(q0, STAGE5_HUMAN)
    return FixedStage5Estimator(pose.translation, pose.rotation, q0).model


FIXED_HUMAN_MODEL = _fixed_human_model()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _trace(condition: str, seed: int) -> dict[str, np.ndarray]:
    path = CAMPAIGN_ROOT / "core" / condition / f"seed_{seed}" / "trace.npz"
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _summary(condition: str, seed: int) -> dict[str, Any]:
    path = CAMPAIGN_ROOT / "core" / condition / f"seed_{seed}" / "summary.json"
    return json.loads(path.read_text())


def _norm(value: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(value, dtype=float)))


def _deg_pair(value: np.ndarray) -> list[float]:
    return [float(item) for item in np.degrees(np.asarray(value, dtype=float))]


def _initial_selected_index(trace: dict[str, np.ndarray]) -> int:
    """Return the first trace row affected by the t=0 selected command."""

    time_s = np.asarray(trace["time_s"], dtype=float)
    matches = np.flatnonzero(np.isclose(time_s, 0.005, atol=1.0e-12, rtol=0.0))
    if not len(matches):
        raise ValueError("saved trace has no t=5 ms command-effect row")
    return int(matches[0])


def _first_prediction(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    solve_times = np.asarray(trace["selected_prediction_time_s"], dtype=float)
    matches = np.flatnonzero(np.isclose(solve_times, 0.0, atol=1.0e-12, rtol=0.0))
    if not len(matches):
        raise ValueError("saved trace has no t=0 selected prediction")
    selected = int(matches[0])
    state0 = np.asarray(trace["estimated_state_rad_rad_s"][0], dtype=float)
    first_state = np.asarray(
        trace["selected_prediction_first_state_rad_rad_s"][selected], dtype=float
    )
    acceleration = (first_state[2:] - state0[2:]) / MPC_INTERVAL_S
    return {
        "solve_index": selected,
        "first_state": first_state,
        "acceleration_rad_s2": acceleration,
        "acceleration_deg_s2": _deg_pair(acceleration),
        "q2_margin_deg_s2": float(
            ACCEL_LIMIT_Q2_DEG_S2 - abs(np.degrees(acceleration[1]))
        ),
        "peak_force_n": float(
            trace["selected_prediction_first_hold_peak_force_n"][selected]
        ),
        "peak_moment_nm": float(
            trace["selected_prediction_first_hold_peak_moment_nm"][selected]
        ),
        "transmitted_wrench_world": np.asarray(
            trace["selected_prediction_first_transmitted_wrench_world"][selected]
        ).tolist(),
        "executable_wrench_world": np.asarray(
            trace["selected_prediction_first_executable_wrench_world"][selected]
        ).tolist(),
    }


def _low_level_components(
    trace: dict[str, np.ndarray], index: int
) -> dict[str, np.ndarray | float]:
    """Reconstruct the saved command's exact candidate-invariant feedback terms."""

    # trace row i samples the command that was built from the preceding 5 ms
    # controller observation and then applied over (t[i-1], t[i]].  The t=0
    # row contains the pre-loop support command built from the same t=0 state.
    source_index = max(0, index - 1)
    state = np.asarray(
        trace["estimated_state_rad_rad_s"][source_index], dtype=float
    )
    q, dq = state[:2], state[2:]
    action = np.asarray(trace["executed_generalized_action_nm"][index], dtype=float)
    allocator = default_engineering_cuff_allocator()
    human_wrench = np.asarray(
        allocator.allocate(action, q, FIXED_HUMAN_MODEL)["wrench_world"], dtype=float
    )
    human_rotation = FIXED_HUMAN_MODEL.geometry.cuff_pose(q).rotation
    rest = np.asarray(CONTROLLER_NOMINAL_INTERFACE.rest_translation_human_m)
    x_hat = np.asarray(
        trace["estimated_interface_translation_human_m"][source_index], dtype=float
    )
    r_world = human_rotation @ (rest + x_hat)
    robot_wrench = human_cuff_wrench_to_robot_cuff_command(human_wrench, r_world)

    operating_point = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        FIXED_HUMAN_MODEL,
        allocator,
        target_q_rad=q,
        target_dq_rad_s=dq,
    )
    target_position = operating_point.robot_cuff_pose_world.translation
    target_rotation = operating_point.robot_cuff_pose_world.rotation
    human_linear, human_angular = FIXED_HUMAN_MODEL.geometry.cuff_velocity(q, dq)
    target_r = target_position - operating_point.human_cuff_pose_world.translation
    target_linear = human_linear + np.cross(human_angular, target_r)
    target_angular = human_angular

    position = np.asarray(
        trace["deployable_robot_cuff_position_world_m"][source_index], dtype=float
    )
    velocity = np.asarray(
        trace["deployable_robot_cuff_linear_velocity_world_m_s"][source_index], dtype=float
    )
    rotation = np.asarray(
        trace["deployable_robot_cuff_rotation_world"][source_index], dtype=float
    )
    omega = np.asarray(
        trace["deployable_robot_cuff_angular_velocity_world_rad_s"][source_index], dtype=float
    )
    gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
    raw_position = gains.position_n_per_m * (target_position - position)
    raw_velocity = gains.velocity_ns_per_m * (target_linear - velocity)
    raw_feedback = raw_position + raw_velocity
    clipped = np.clip(
        raw_feedback,
        -gains.feedback_component_limit_n,
        gains.feedback_component_limit_n,
    )
    scale = np.ones(3)
    nonzero = np.abs(raw_feedback) > 1.0e-15
    scale[nonzero] = clipped[nonzero] / raw_feedback[nonzero]
    position_feedback = raw_position * scale
    velocity_feedback = clipped - position_feedback
    orientation_feedback = gains.orientation_nm_per_rad * Rotation.from_matrix(
        target_rotation @ rotation.T
    ).as_rotvec()
    angular_velocity_feedback = gains.angular_velocity_nms_per_rad * (
        target_angular - omega
    )
    saved_command = np.asarray(trace["executed_command_wrench_world"][index])
    reconstructed = np.concatenate(
        [
            robot_wrench[:3] + position_feedback + velocity_feedback,
            robot_wrench[3:] + orientation_feedback + angular_velocity_feedback,
        ]
    )
    return {
        "allocated_human_wrench_world": human_wrench,
        "allocated_robot_wrench_world": robot_wrench,
        "position_feedback_world_n": position_feedback,
        "velocity_feedback_world_n": velocity_feedback,
        "orientation_feedback_world_nm": orientation_feedback,
        "angular_velocity_feedback_world_nm": angular_velocity_feedback,
        "reconstructed_command_world": reconstructed,
        "saved_command_residual_norm": _norm(reconstructed - saved_command),
    }


def startup_audit(output_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    initial_vectors: dict[str, dict[str, np.ndarray]] = {}
    for condition in STARTUP_CONDITIONS:
        for seed in STARTUP_SEEDS:
            trace = _trace(condition, seed)
            summary = _summary(condition, seed)
            effect_index = _initial_selected_index(trace)
            prediction = _first_prediction(trace)
            key = f"{condition}/seed_{seed}"
            initial_vectors[key] = {
                name: np.asarray(trace[name][0]).copy()
                for name in (
                    "estimated_state_rad_rad_s",
                    "evaluation_human_q_rad",
                    "evaluation_human_dq_rad_s",
                    "interface_translation_human_m",
                    "interface_rotation_human_rad",
                    "estimated_interface_translation_human_m",
                    "estimated_interface_velocity_human_m_s",
                    "estimated_interface_rotation_human_rad",
                    "estimated_interface_angular_velocity_human_rad_s",
                    "prediction_base_drive_world_n",
                    "prediction_base_angular_drive_world_nm",
                    "prediction_previous_executable_wrench_world",
                    "executed_command_wrench_world",
                    "deployable_robot_cuff_position_world_m",
                    "deployable_robot_cuff_rotation_world",
                    "deployable_robot_cuff_linear_velocity_world_m_s",
                    "deployable_robot_cuff_angular_velocity_world_rad_s",
                    "deployable_measured_cuff_force_world_n",
                    "deployable_measured_cuff_moment_world_nm",
                )
            }
            selected_action = np.asarray(
                trace["executed_generalized_action_nm"][effect_index], dtype=float
            )
            support = np.asarray(
                trace["support_generalized_action_nm"][0], dtype=float
            )
            previous_action = np.asarray(
                trace["executed_generalized_action_nm"][0], dtype=float
            )
            first_cmd = np.asarray(
                trace["executed_command_wrench_world"][effect_index], dtype=float
            )
            previous_cmd = np.asarray(
                trace["executed_command_wrench_world"][0], dtype=float
            )
            online_peak = np.degrees(
                np.max(
                    np.abs(trace["deployable_realized_acceleration_rad_s2"]), axis=0
                )
            )
            truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
            time_s = np.asarray(trace["time_s"], dtype=float)
            truth_interval = np.empty((len(time_s), 2), dtype=float)
            for i, timestamp in enumerate(time_s):
                if i == 0:
                    truth_interval[i] = np.asarray(
                        trace["evaluation_only_instantaneous_acceleration_rad_s2"][i]
                    )
                else:
                    truth_interval[i] = (truth_dq[i] - truth_dq[0]) / timestamp
            truth_peak = np.degrees(np.max(np.abs(truth_interval), axis=0))
            comparisons.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "result": summary["task_status"],
                    "abort_reason": summary["abort_reason"],
                    "saved_duration_ms": 1000.0 * float(time_s[-1]),
                    "selected_total_action_nm": selected_action.tolist(),
                    "support_action_nm": support.tolist(),
                    "motion_increment_nm": (selected_action - support).tolist(),
                    "first_action_increment_norm_nm": _norm(
                        selected_action - previous_action
                    ),
                    "first_executable_wrench_increment_norm": _norm(
                        first_cmd - previous_cmd
                    ),
                    "predicted_q2_20ms_acceleration_deg_s2": (
                        prediction["acceleration_deg_s2"][1]
                    ),
                    "predicted_q2_margin_deg_s2": prediction["q2_margin_deg_s2"],
                    "online_peak_q2_acceleration_deg_s2": float(online_peak[1]),
                    "truth_peak_q2_interval_acceleration_deg_s2": float(truth_peak[1]),
                    "truth_minus_predicted_q2_deg_s2": float(
                        truth_peak[1]
                        - abs(prediction["acceleration_deg_s2"][1])
                    ),
                }
            )
            prediction_times = np.asarray(
                trace["selected_prediction_time_s"], dtype=float
            )
            for index, timestamp in enumerate(time_s):
                if timestamp > 0.060 + 1.0e-12:
                    break
                low_level = _low_level_components(trace, index)
                solve_match = np.flatnonzero(
                    np.isclose(prediction_times, timestamp, atol=1.0e-12, rtol=0.0)
                )
                pred_accel = (
                    np.degrees(
                        trace["selected_prediction_first_acceleration_rad_s2"][
                            int(solve_match[0])
                        ]
                    )
                    if len(solve_match)
                    else np.full(2, np.nan)
                )
                cmd = np.asarray(trace["executed_command_wrench_world"][index])
                previous = (
                    cmd
                    if index == 0
                    else np.asarray(trace["executed_command_wrench_world"][index - 1])
                )
                interface_x = np.asarray(trace["interface_translation_human_m"][index])
                interface_theta = np.asarray(trace["interface_rotation_human_rad"][index])
                rows.append(
                    {
                        "condition": condition,
                        "seed": seed,
                        "campaign_result": summary["task_status"],
                        "time_ms": 1000.0 * float(timestamp),
                        "q_hat_deg": _deg_pair(
                            trace["estimated_state_rad_rad_s"][index, :2]
                        ),
                        "dq_hat_deg_s": _deg_pair(
                            trace["estimated_state_rad_rad_s"][index, 2:]
                        ),
                        "q_truth_deg": _deg_pair(
                            trace["evaluation_human_q_rad"][index]
                        ),
                        "dq_truth_deg_s": _deg_pair(
                            trace["evaluation_human_dq_rad_s"][index]
                        ),
                        "online_accel_deg_s2": _deg_pair(
                            trace["deployable_realized_acceleration_rad_s2"][index]
                        ),
                        "truth_interval_accel_deg_s2": _deg_pair(truth_interval[index]),
                        "mpc_predicted_20ms_accel_deg_s2": pred_accel.tolist(),
                        "current_total_action_nm": np.asarray(
                            trace["executed_generalized_action_nm"][index]
                        ).tolist(),
                        "support_action_nm": np.asarray(
                            trace["support_generalized_action_nm"][index]
                        ).tolist(),
                        "motion_increment_nm": np.asarray(
                            trace["motion_increment_generalized_action_nm"][index]
                        ).tolist(),
                        "allocated_human_wrench_world": np.asarray(
                            low_level["allocated_human_wrench_world"]
                        ).tolist(),
                        "allocated_robot_wrench_world": np.asarray(
                            low_level["allocated_robot_wrench_world"]
                        ).tolist(),
                        "position_feedback_world_n": np.asarray(
                            low_level["position_feedback_world_n"]
                        ).tolist(),
                        "velocity_feedback_world_n": np.asarray(
                            low_level["velocity_feedback_world_n"]
                        ).tolist(),
                        "orientation_feedback_world_nm": np.asarray(
                            low_level["orientation_feedback_world_nm"]
                        ).tolist(),
                        "angular_velocity_feedback_world_nm": np.asarray(
                            low_level["angular_velocity_feedback_world_nm"]
                        ).tolist(),
                        "executable_wrench_world": cmd.tolist(),
                        "command_increment_world": (cmd - previous).tolist(),
                        "physical_wrench_world": np.concatenate(
                            [
                                trace["physical_cuff_force_world_n"][index],
                                trace["physical_cuff_moment_world_nm"][index],
                            ]
                        ).tolist(),
                        "actual_human_input_nm": np.asarray(
                            trace["deployable_measured_generalized_input_nm"][index]
                        ).tolist(),
                        "interface_translation_mm": (1000.0 * interface_x).tolist(),
                        "interface_velocity_mm_s": (
                            1000.0
                            * np.asarray(
                                trace["estimated_interface_velocity_human_m_s"][index]
                            )
                        ).tolist(),
                        "interface_rotation_deg": _deg_pair(interface_theta),
                        "interface_angular_velocity_deg_s": _deg_pair(
                            trace[
                                "estimated_interface_angular_velocity_human_rad_s"
                            ][index]
                        ),
                        "predictor_base_drive_world_n": np.asarray(
                            trace["prediction_base_drive_world_n"][index]
                        ).tolist(),
                        "predictor_base_angular_drive_world_nm": np.asarray(
                            trace["prediction_base_angular_drive_world_nm"][index]
                        ).tolist(),
                        "predictor_previous_executable_wrench_world": np.asarray(
                            trace["prediction_previous_executable_wrench_world"][index]
                        ).tolist(),
                        "command_reconstruction_residual_norm": float(
                            low_level["saved_command_residual_norm"]
                        ),
                    }
                )

    # Same-plant initial equivalence is evaluated independently for each condition.
    initial_equivalence: dict[str, Any] = {}
    for condition in STARTUP_CONDITIONS:
        reference = initial_vectors[f"{condition}/seed_{STARTUP_SEEDS[0]}"]
        field_differences: dict[str, float] = {}
        for field in reference:
            field_differences[field] = max(
                _norm(
                    initial_vectors[f"{condition}/seed_{seed}"][field]
                    - reference[field]
                )
                for seed in STARTUP_SEEDS[1:]
            )
        initial_equivalence[condition] = {
            "maximum_seedwise_norm_difference_by_field": field_differences,
            "all_saved_numeric_fields_identical_to_1e-12": bool(
                max(field_differences.values()) <= 1.0e-12
            ),
            "estimator_history": "one identical t=0 measurement",
            "acceleration_monitor_history": "one identical t=0 sample",
            "robot_joint_state_trace_availability": (
                "not serialized; exact cuff pose/twist and deterministic loaded "
                "initialization inputs are identical"
            ),
        }

    with (output_dir / "startup_timeline.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    with (output_dir / "startup_comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    fig, axes = plt.subplots(2, 1, figsize=(9.0, 7.0), sharex=True)
    colors = {20260824: "tab:red", 20260825: "tab:blue", 20260826: "tab:green"}
    for condition_index, condition in enumerate(STARTUP_CONDITIONS):
        axis = axes[condition_index]
        for seed in STARTUP_SEEDS:
            trace = _trace(condition, seed)
            t = 1000.0 * trace["time_s"]
            keep = t <= 60.0 + 1.0e-9
            axis.plot(
                t[keep],
                np.degrees(
                    trace["deployable_realized_acceleration_rad_s2"][keep, 1]
                ),
                marker="o",
                color=colors[seed],
                label=f"seed {seed} online",
            )
            dq = trace["evaluation_human_dq_rad_s"]
            truth = np.zeros(len(t))
            truth[0] = np.degrees(
                trace["evaluation_only_instantaneous_acceleration_rad_s2"][0, 1]
            )
            truth[1:] = np.degrees((dq[1:, 1] - dq[0, 1]) / trace["time_s"][1:])
            axis.plot(
                t[keep], truth[keep], linestyle="--", color=colors[seed], alpha=0.75
            )
        axis.axhline(ACCEL_LIMIT_Q2_DEG_S2, color="black", linestyle=":")
        axis.set_title(condition)
        axis.set_ylabel("q2 accel (deg/s²)")
        axis.grid(alpha=0.25)
    axes[-1].set_xlabel("time from episode start (ms)")
    axes[0].legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "startup_q2_acceleration.png", dpi=170)
    plt.close(fig)
    counterfactual = counterfactual_first_action_holds()
    _write_json(output_dir / "counterfactual_first_action_hold.json", counterfactual)
    return {
        "comparison": comparisons,
        "initial_equivalence": initial_equivalence,
        "timeline_rows": len(rows),
        "saved_failure_trace_limitation": (
            "Both failed runs end at 10 ms; no factual post-abort samples exist."
        ),
        "constraint_semantics": {
            "mpc": "future dq change over exactly 20 ms",
            "online_before_20ms": (
                "trapezoidal mean of every available causal instantaneous model "
                "acceleration sample since episode start (5/10/15 ms windows)"
            ),
            "same_startup_intervals": False,
        },
        "counterfactual_first_action_hold": counterfactual,
    }


def _condition_scales(condition: str) -> tuple[float, float, float]:
    mapping = {
        "low_low_high": (0.9, 0.9, 1.2),
        "high_low_high": (1.1, 0.9, 1.2),
    }
    return mapping[condition]


def counterfactual_first_action_holds() -> dict[str, Any]:
    """Continue only the already-selected first action to its 20 ms boundary.

    Production aborts the two failing runs at 10 ms.  This offline replay uses
    the unchanged plant/execution chain, suppresses no command constraint, and
    simply omits task-state transition/abort evaluation until the first action
    hold ends.  It is a counterfactual diagnostic, never campaign evidence.
    """

    results: list[dict[str, Any]] = []
    spec = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5)
    for condition in STARTUP_CONDITIONS:
        parameters = scaled_interface(*_condition_scales(condition))
        for seed in STARTUP_SEEDS:
            session: dict[str, Any] = {}
            with tempfile.TemporaryDirectory(
                prefix=f"stage5_first_hold_{condition}_{seed}_"
            ) as temp:
                run_goal_mpc_smoke(
                    Path(temp) / "setup_5ms",
                    spec=spec,
                    maximum_duration_s=0.005,
                    plant_interface_parameters=parameters,
                    plant_case_name=f"diagnostic_only__{condition}",
                    record_selected_horizon_diagnostics=True,
                    use_loaded_local_hold=True,
                    use_bumpless_return_handoff=True,
                    initialize_loaded_equilibrium_with_plant_truth=True,
                    planning_physical_force_ceiling_n=180.0,
                    planning_joint_velocity_ceiling_rad_s=tuple(
                        np.radians((15.0, 25.0))
                    ),
                    mpc_config=HumanMPCConfig(random_seed=seed),
                    session_context=session,
                )
                with np.load(Path(temp) / "setup_5ms" / "trace.npz") as archive:
                    setup_action = np.asarray(
                        archive["executed_generalized_action_nm"][1], dtype=float
                    ).copy()
                    initial_truth_dq = np.asarray(
                        archive["evaluation_human_dq_rad_s"][0], dtype=float
                    ).copy()
                    initial_estimated_dq = np.asarray(
                        archive["estimated_state_rad_rad_s"][0, 2:], dtype=float
                    ).copy()
                    predicted_acceleration = np.asarray(
                        archive["selected_prediction_first_acceleration_rad_s2"][0],
                        dtype=float,
                    ).copy()

            saved = _trace(condition, seed)
            saved_action = np.asarray(
                saved["executed_generalized_action_nm"][1], dtype=float
            )
            plant = session["plant"]
            estimator = session["estimator"]
            human_model = estimator.model
            allocator = session["cuff_allocator"]
            observer = session["interface_observer"]
            monitor = session["acceleration_monitor"]
            predictor = session["screening_interface_predictor"]
            action = np.asarray(session["current_action_nm"], dtype=float).copy()
            trajectory: list[dict[str, Any]] = []

            # The setup replay ended after exactly one 5 ms command period.
            for target_time in (0.005, 0.010, 0.015, 0.020):
                truth = plant.observe()
                estimator_measurement = session["estimator_layer"].update(truth)
                mpc_measurement = session["mpc_layer"].update(truth)
                low_measurement = session["low_level_layer"].update(truth)
                if abs(target_time % MPC_INTERVAL_S) <= 1.0e-12:
                    _estimator_observe(estimator, estimator_measurement)
                    human_model = estimator.model
                observation, interface_state = observer.update(
                    mpc_measurement,
                    human_model,
                    human_model_version=FIXED_HUMAN_MODEL_VERSION,
                )
                predictor.update_from_measurement(interface_state)
                if (
                    observation.sample_timestamp_s
                    > session["last_realized_acceleration"].sample_timestamp_s
                    + 1.0e-12
                ):
                    realized = monitor.update(
                        observation, interface_state, human_model
                    )
                    session["last_realized_acceleration"] = realized
                else:
                    realized = session["last_realized_acceleration"]
                truth_dq = np.asarray(truth.human_dq_rad_s, dtype=float)
                truth_interval = (truth_dq - initial_truth_dq) / target_time
                estimated_interval = (
                    observation.as_array()[2:] - initial_estimated_dq
                ) / target_time
                trajectory.append(
                    {
                        "time_ms": 1000.0 * target_time,
                        "truth_dq_deg_s": _deg_pair(truth_dq),
                        "estimated_dq_deg_s": _deg_pair(observation.as_array()[2:]),
                        "truth_interval_acceleration_deg_s2": _deg_pair(
                            truth_interval
                        ),
                        "estimated_dq_interval_acceleration_deg_s2": _deg_pair(
                            estimated_interval
                        ),
                        "online_model_mean_acceleration_deg_s2": _deg_pair(
                            realized.acceleration_rad_s2
                        ),
                        "physical_force_norm_n": _norm(
                            truth.cuff_force_vector_n
                        ),
                        "actual_human_input_nm": np.asarray(
                            realized.generalized_human_input_nm
                        ).tolist(),
                    }
                )
                if target_time >= MPC_INTERVAL_S - 1.0e-12:
                    continue
                state = observation.as_array()
                operating_point = solve_loaded_hold_equilibrium(
                    spec,
                    human_model,
                    allocator,
                    target_q_rad=state[:2],
                    target_dq_rad_s=state[2:],
                )
                context = build_stage5_loaded_execution_context(
                    plant=plant,
                    measurement=low_measurement,
                    observation=observation,
                    interface_state=interface_state,
                    human_model=human_model,
                    cuff_allocator=allocator,
                    target=loaded_execution_target_from_equilibrium(
                        operating_point, human_model
                    ),
                )
                force_filter = context.make_force_filter()
                force_filter(action[np.newaxis, :])
                filtered = force_filter.selected_result(action)
                if not filtered.feasible:
                    raise RuntimeError("saved first action became infeasible offline")
                command = filtered.filtered_preview.command
                plant.apply_executable_command(command)
                predictor.synchronize(interface_state, command.wrench_total_world)
                for _ in range(20):
                    plant.step()

            last = trajectory[-1]
            results.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "campaign_result": _summary(condition, seed)["task_status"],
                    "saved_vs_setup_selected_action_max_abs_error_nm": float(
                        np.max(np.abs(saved_action - setup_action))
                    ),
                    "selected_action_nm": action.tolist(),
                    "mpc_predicted_20ms_acceleration_deg_s2": _deg_pair(
                        predicted_acceleration
                    ),
                    "counterfactual_truth_20ms_acceleration_deg_s2": last[
                        "truth_interval_acceleration_deg_s2"
                    ],
                    "counterfactual_online_model_20ms_acceleration_deg_s2": last[
                        "online_model_mean_acceleration_deg_s2"
                    ],
                    "truth_minus_predicted_q2_deg_s2": float(
                        abs(last["truth_interval_acceleration_deg_s2"][1])
                        - abs(np.degrees(predicted_acceleration[1]))
                    ),
                    "truth_20ms_q2_limit_satisfied": bool(
                        abs(last["truth_interval_acceleration_deg_s2"][1])
                        <= ACCEL_LIMIT_Q2_DEG_S2 + 1.0e-9
                    ),
                    "trajectory": trajectory,
                }
            )
    return {
        "scope": (
            "offline same implementation; hold the already-selected t=0 action "
            "through 20 ms and omit only task abort evaluation"
        ),
        "campaign_statistics_changed": False,
        "results": results,
    }


def runtime_audit(output_dir: Path) -> dict[str, Any]:
    episode_rows: list[dict[str, Any]] = []
    component_names: set[str] = set()
    cumulative_control_samples = 0
    cumulative_physics_samples = 0
    for episode in range(1, 31):
        root = CAMPAIGN_ROOT / "repeatability" / f"episode_{episode:02d}"
        summary = json.loads((root / "summary.json").read_text())
        with np.load(root / "trace.npz", allow_pickle=False) as trace:
            control_samples = len(trace["time_s"])
            phase_counts = {
                str(phase): int(count)
                for phase, count in zip(
                    *np.unique(trace["task_phase"], return_counts=True), strict=True
                )
            }
        duration = float(summary["task_duration_s"])
        cumulative_control_samples += control_samples
        cumulative_physics_samples += int(round(duration / 0.00025)) + 1
        runtime = summary["mpc_runtime_ms"]
        breakdown = summary["mpc_runtime_breakdown_ms"]
        component_names.update(breakdown)
        row: dict[str, Any] = {
            "episode": episode,
            "solve_count": int(summary["mpc_solve_count"]),
            "runtime_mean_ms": float(runtime["mean"]),
            "runtime_p95_ms": float(runtime["p95"]),
            "runtime_max_ms": float(runtime["max"]),
            "deadline_misses": int(runtime["deadline_miss_count"]),
            "task_duration_s": duration,
            "control_samples_episode": control_samples,
            "control_samples_persistent": cumulative_control_samples,
            "plant_interface_history_estimated_persistent": cumulative_physics_samples,
            "measurement_processed_per_layer_persistent": cumulative_control_samples,
            "phase_counts_5ms": phase_counts,
        }
        for component, stats in breakdown.items():
            row[f"component_mean::{component}"] = float(stats["mean"])
            row[f"component_p95::{component}"] = float(stats["p95"])
        episode_rows.append(row)

    fields = [
        "episode",
        "solve_count",
        "runtime_mean_ms",
        "runtime_p95_ms",
        "runtime_max_ms",
        "deadline_misses",
        "task_duration_s",
        "control_samples_episode",
        "control_samples_persistent",
        "plant_interface_history_estimated_persistent",
        "measurement_processed_per_layer_persistent",
    ] + [f"component_mean::{name}" for name in sorted(component_names)]
    with (output_dir / "runtime_by_episode.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(episode_rows)

    x = np.arange(1, 31)
    mean = np.asarray([row["runtime_mean_ms"] for row in episode_rows])
    p95 = np.asarray([row["runtime_p95_ms"] for row in episode_rows])
    fig, axis = plt.subplots(figsize=(9.0, 4.5))
    axis.plot(x, mean, marker="o", label="episode mean")
    axis.plot(x, p95, marker=".", label="episode p95")
    axis.axhline(20.0, color="black", linestyle=":", label="20 ms replanning")
    axis.set_xlabel("episode index")
    axis.set_ylabel("Goal-MPC runtime (ms)")
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "runtime_by_episode.png", dpi=170)
    plt.close(fig)

    selected_components = [
        "stage5_human_dynamics_propagation",
        "stage5_interface_state_propagation",
        "stage5_loaded_execution_wrench_transforms",
        "stage5_cuff_allocation",
        "stage5_geometry",
        "first_action_executable_screening",
        "cost_constraint_evaluation",
        "candidate_sampling_generation",
        "elite_selection_cem_update",
        "other_python_numpy_overhead",
    ]
    fig, axis = plt.subplots(figsize=(10.0, 5.4))
    for component in selected_components:
        values = np.asarray(
            [row.get(f"component_mean::{component}", np.nan) for row in episode_rows]
        )
        axis.plot(x, values, label=component)
    axis.set_xlabel("episode index")
    axis.set_ylabel("mean component time (ms/solve)")
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=7)
    fig.tight_layout()
    fig.savefig(output_dir / "runtime_components_by_episode.png", dpi=170)
    plt.close(fig)

    slopes: dict[str, float] = {}
    first_last: dict[str, dict[str, float]] = {}
    for component in sorted(component_names):
        values = np.asarray(
            [row[f"component_mean::{component}"] for row in episode_rows]
        )
        slopes[component] = float(np.polyfit(x, values, 1)[0])
        first = float(np.mean(values[:5]))
        last = float(np.mean(values[-5:]))
        first_last[component] = {
            "first5_mean_ms": first,
            "last5_mean_ms": last,
            "delta_ms": last - first,
            "relative_change_percent": (
                float(100.0 * (last - first) / first) if first else float("nan")
            ),
        }

    runtime_inventory = [
        {
            "object": "plant.interface_history",
            "growth": "unbounded across continuous session",
            "estimated_final_length": cumulative_physics_samples,
            "mpc_hot_path": False,
            "access": "used only when final baseline metrics are assembled",
        },
        {
            "object": "three CausalMeasurementLayer._processed lists",
            "growth": "unbounded across continuous session",
            "estimated_final_length_each": cumulative_control_samples,
            "mpc_hot_path": False,
            "access": "measurement update precedes the solve timer; solve sees current sample only",
        },
        {
            "object": "CausalMeasurementLayer._pose_history",
            "growth": "bounded by derivative window; empty for ideal preprocessing-disabled case",
            "mpc_hot_path": False,
        },
        {
            "object": "CausalModelAccelerationMonitor._samples",
            "growth": "bounded to approximately the trailing 20 ms",
            "mpc_hot_path": False,
        },
        {
            "object": "GoalMPC candidate_audit_history",
            "growth": "empty because Stage-5 config freezes audit indices to empty",
            "mpc_hot_path": False,
        },
        {
            "object": "GoalMPC last sequence/diagnostics/safest sequence/RNG",
            "growth": "persistent fixed-size replacement",
            "mpc_hot_path": True,
        },
        {
            "object": "InterfaceAwareFirstActionBatchPreview._screen_cache",
            "growth": "bounded to four entries and object rebuilt each solve",
            "mpc_hot_path": True,
        },
        {
            "object": "episode trace/timing/status Python lists",
            "growth": "reset per episode",
            "mpc_hot_path": False,
            "access": "append occurs outside solve timer",
        },
        {
            "object": "Safety Filter/supervisor counters and last command",
            "growth": "fixed-size counters/state",
            "mpc_hot_path": False,
        },
    ]
    # Frozen evidence did not save per-solve timings/RSS/GC.  Record that limit
    # instead of reconstructing values that were never measured.
    return {
        "episode_rows": episode_rows,
        "component_first5_last5": first_last,
        "component_slopes_ms_per_episode": slopes,
        "persistent_state_inventory": runtime_inventory,
        "frozen_evidence_availability": {
            "per_solve_runtime": False,
            "phase_aligned_runtime": False,
            "rss": False,
            "gc_counters": False,
            "reason": (
                "summary.json stores per-episode mean/p95/max component aggregates; "
                "trace.npz stores phase at 5 ms but no per-solve timing series"
            ),
        },
        "gc_snapshot_during_offline_audit": {
            "enabled": gc.isenabled(),
            "counts": list(gc.get_count()),
            "tracked_objects": len(gc.get_objects()),
        },
        "process_snapshot_during_offline_audit": {
            "pid": os.getpid(),
            "max_rss_platform_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }


def summarize_benchmark_samples(
    wall_ms: list[float], process_ms: list[float], gc_events: int
) -> dict[str, Any]:
    """Pure summarizer used by the diagnostic benchmark and focused tests."""

    wall = np.asarray(wall_ms, dtype=float)
    process = np.asarray(process_ms, dtype=float)
    if wall.ndim != 1 or process.shape != wall.shape or not len(wall):
        raise ValueError("benchmark samples must be equal non-empty vectors")
    return {
        "repetitions": int(len(wall)),
        "wall_mean_ms": float(np.mean(wall)),
        "wall_p95_ms": float(np.percentile(wall, 95)),
        "wall_max_ms": float(np.max(wall)),
        "process_mean_ms": float(np.mean(process)),
        "process_p95_ms": float(np.percentile(process, 95)),
        "wall_minus_process_mean_ms": float(np.mean(wall - process)),
        "gc_events": int(gc_events),
    }


def _one_benchmark_window(
    *,
    mpc: Any,
    mpc_snapshot: dict[str, Any],
    observation: Any,
    task_state: GoalTaskState,
    spec: Any,
    human_model: Any,
    execution_context: Any,
    predictor: Any,
    interface_state: Any,
    repetitions: int,
) -> dict[str, Any]:
    wall_ms: list[float] = []
    process_ms: list[float] = []
    breakdowns: list[dict[str, float]] = []
    actions: list[np.ndarray] = []
    statuses: list[str] = []
    gc_events: list[dict[str, Any]] = []

    def gc_callback(phase: str, info: dict[str, Any]) -> None:
        if phase == "stop":
            gc_events.append(dict(info))

    gc.callbacks.append(gc_callback)
    try:
        for _ in range(repetitions):
            mpc.__dict__.clear()
            mpc.__dict__.update(deepcopy(mpc_snapshot))
            batch_preview = make_interface_aware_first_action_batch_preview(
                execution_context.preview_command_batch,
                predictor,
                interface_state,
                q_rad=observation.as_array()[:2],
                human_model=human_model,
                cuff_allocator=mpc.cuff_allocator,
            )
            process_start = time.process_time_ns()
            wall_start = time.perf_counter_ns()
            action, diagnostics = mpc.solve_goal(
                observation,
                task_state,
                spec,
                human_model,
                first_action_batch_preview=batch_preview,
            )
            wall_ms.append((time.perf_counter_ns() - wall_start) / 1.0e6)
            process_ms.append((time.process_time_ns() - process_start) / 1.0e6)
            if action is None:
                actions.append(np.full(2, np.nan))
            else:
                actions.append(np.asarray(action, dtype=float).copy())
            statuses.append(str(diagnostics["status"]))
            breakdowns.append(
                {
                    str(name): float(value)
                    for name, value in diagnostics["implementation_timing_ms"].items()
                }
            )
    finally:
        gc.callbacks.remove(gc_callback)
    summary = summarize_benchmark_samples(wall_ms, process_ms, len(gc_events))
    action_matrix = np.asarray(actions)
    summary.update(
        {
            "all_actions_bitwise_equal": bool(
                np.all(action_matrix == action_matrix[0])
            ),
            "selected_action_nm": action_matrix[0].tolist(),
            "status_counts": {
                status: statuses.count(status) for status in sorted(set(statuses))
            },
            "component_mean_ms": {
                name: float(np.mean([item.get(name, 0.0) for item in breakdowns]))
                for name in sorted({key for item in breakdowns for key in item})
            },
        }
    )
    return summary


def same_snapshot_benchmark(
    *, repetitions: int = 60, stress_repetitions: int = 600
) -> dict[str, Any]:
    """Benchmark one exact loaded OUTBOUND solve before/after process stress.

    The only run used to construct the snapshot is a 5 ms non-formal setup
    replay in a temporary directory.  It is not a campaign cell and its result
    is not counted.  Every timed solve restores identical MPC/RNG state and
    rebuilds the per-solve first-action cache, exactly as production does.
    """

    session: dict[str, Any] = {}
    spec = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5)
    with tempfile.TemporaryDirectory(prefix="stage5_runtime_snapshot_") as temp:
        run_goal_mpc_smoke(
            Path(temp) / "setup_5ms",
            spec=spec,
            maximum_duration_s=0.005,
            plant_interface_parameters=scaled_interface(0.9, 0.9, 0.8),
            plant_case_name="diagnostic_only_same_snapshot_setup",
            record_selected_horizon_diagnostics=True,
            use_loaded_local_hold=True,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            planning_physical_force_ceiling_n=180.0,
            planning_joint_velocity_ceiling_rad_s=tuple(np.radians((15.0, 25.0))),
            mpc_config=HumanMPCConfig(random_seed=20260824),
            session_context=session,
        )

    plant = session["plant"]
    human_model = session["estimator"].model
    measurement = session["mpc_layer"].current
    low_level_measurement = session["low_level_layer"].current
    observation, interface_state = session["interface_observer"].update(
        measurement,
        human_model,
        human_model_version=FIXED_HUMAN_MODEL_VERSION,
    )
    predictor = session["screening_interface_predictor"]
    predictor.update_from_measurement(interface_state)
    state = observation.as_array()
    operating_point = solve_loaded_hold_equilibrium(
        spec,
        human_model,
        session["cuff_allocator"],
        target_q_rad=state[:2],
        target_dq_rad_s=state[2:],
    )
    execution_context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=low_level_measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=human_model,
        cuff_allocator=session["cuff_allocator"],
        target=loaded_execution_target_from_equilibrium(
            operating_point, human_model
        ),
    )
    task_state = GoalTaskState(
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=0.005,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )
    mpc = session["mpc"]
    mpc_snapshot = deepcopy(mpc.__dict__)
    rss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    object_count_start = len(gc.get_objects())
    fresh = _one_benchmark_window(
        mpc=mpc,
        mpc_snapshot=mpc_snapshot,
        observation=observation,
        task_state=task_state,
        spec=spec,
        human_model=human_model,
        execution_context=execution_context,
        predictor=predictor,
        interface_state=interface_state,
        repetitions=repetitions,
    )

    # Reconstruct the major *diagnostic-only* late-session history.  The fixed
    # execution context and solve inputs are unchanged, and no controller-
    # required history is truncated or replaced.
    original_interface_history = list(plant.interface_history)
    existing = len(original_interface_history)
    estimated_late_length = int(round(30.0 * 5.5 / 0.00025))
    if plant.interface_history:
        plant.interface_history.extend(
            [plant.interface_history[-1]] * max(0, estimated_late_length - existing)
        )
    with_history = _one_benchmark_window(
        mpc=mpc,
        mpc_snapshot=mpc_snapshot,
        observation=observation,
        task_state=task_state,
        spec=spec,
        human_model=human_model,
        execution_context=execution_context,
        predictor=predictor,
        interface_state=interface_state,
        repetitions=repetitions,
    )
    plant.interface_history = original_interface_history
    history_ablated = _one_benchmark_window(
        mpc=mpc,
        mpc_snapshot=mpc_snapshot,
        observation=observation,
        task_state=task_state,
        spec=spec,
        human_model=human_model,
        execution_context=execution_context,
        predictor=predictor,
        interface_state=interface_state,
        repetitions=repetitions,
    )

    # Long-process stress uses the identical restored snapshot.  It changes no
    # model/control state and is not an episode or scientific experiment.
    stressed_windows: list[dict[str, Any]] = []
    block = max(1, min(100, stress_repetitions))
    completed = 0
    while completed < stress_repetitions:
        count = min(block, stress_repetitions - completed)
        stressed_windows.append(
            _one_benchmark_window(
                mpc=mpc,
                mpc_snapshot=mpc_snapshot,
                observation=observation,
                task_state=task_state,
                spec=spec,
                human_model=human_model,
                execution_context=execution_context,
                predictor=predictor,
                interface_state=interface_state,
                repetitions=count,
            )
        )
        completed += count
    late_process = _one_benchmark_window(
        mpc=mpc,
        mpc_snapshot=mpc_snapshot,
        observation=observation,
        task_state=task_state,
        spec=spec,
        human_model=human_model,
        execution_context=execution_context,
        predictor=predictor,
        interface_state=interface_state,
        repetitions=repetitions,
    )
    return {
        "snapshot": {
            "phase": "OUTBOUND",
            "time_s": float(observation.sample_timestamp_s),
            "state_rad_rad_s": state.tolist(),
            "plant_truth_condition": [0.9, 0.9, 0.8],
            "production_horizon_candidates_iterations": [15, 32, 2],
            "restored_identical_rng_and_mpc_state_each_repetition": True,
            "setup_replay_scope": "diagnostic-only 5 ms temporary replay",
        },
        "fresh_process_window": fresh,
        "late_diagnostic_history_window": with_history,
        "noncontrol_history_ablated_window": history_ablated,
        "long_process_stress_windows": stressed_windows,
        "post_stress_window": late_process,
        "stress_repetitions": stress_repetitions,
        "diagnostic_history": {
            "name": "plant.interface_history",
            "before_length": existing,
            "late_reconstructed_length": estimated_late_length,
            "post_ablation_length": len(plant.interface_history),
            "controller_hot_path": False,
            "controller_required_history_was_truncated": False,
        },
        "memory": {
            "max_rss_before_platform_units": rss_start,
            "max_rss_after_platform_units": resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss,
            "gc_tracked_objects_before": object_count_start,
            "gc_tracked_objects_after": len(gc.get_objects()),
        },
    }


def _write_benchmark_plot(path: Path, benchmark: dict[str, Any]) -> None:
    labels = ["fresh", "history", "ablated"]
    means = [
        benchmark["fresh_process_window"]["wall_mean_ms"],
        benchmark["late_diagnostic_history_window"]["wall_mean_ms"],
        benchmark["noncontrol_history_ablated_window"]["wall_mean_ms"],
    ]
    for index, window in enumerate(benchmark["long_process_stress_windows"], 1):
        labels.append(f"stress {index}")
        means.append(window["wall_mean_ms"])
    labels.append("post")
    means.append(benchmark["post_stress_window"]["wall_mean_ms"])
    fig, axis = plt.subplots(figsize=(9.0, 4.5))
    axis.plot(np.arange(len(means)), means, marker="o")
    axis.axhline(20.0, color="black", linestyle=":", label="20 ms")
    axis.set_xticks(np.arange(len(means)), labels, rotation=35, ha="right")
    axis.set_ylabel("identical-snapshot mean runtime (ms)")
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--benchmark-repetitions", type=int, default=60)
    parser.add_argument("--stress-repetitions", type=int, default=600)
    parser.add_argument("--skip-benchmark", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    benchmark = (
        None
        if args.skip_benchmark
        else same_snapshot_benchmark(
            repetitions=args.benchmark_repetitions,
            stress_repetitions=args.stress_repetitions,
        )
    )
    if benchmark is not None:
        _write_benchmark_plot(args.output_dir / "same_snapshot_benchmark.png", benchmark)
    startup = startup_audit(args.output_dir)
    runtime = runtime_audit(args.output_dir)
    payload = {
        "schema": "stage5_interface_robustness_remaining_issues_audit_v1",
        "scope": "diagnostic_only_saved_campaign_evidence",
        "campaign_result_preserved": "EXIT C — STOP THIS IMPLEMENTATION",
        "startup": startup,
        "runtime": runtime,
        "same_snapshot_benchmark": benchmark,
        "scientific_controller_or_parameter_change": False,
    }
    _write_json(args.output_dir / "audit_summary.json", payload)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "startup_rows": startup["timeline_rows"],
        "runtime_episodes": len(runtime["episode_rows"]),
    }, indent=2))


if __name__ == "__main__":
    main()
