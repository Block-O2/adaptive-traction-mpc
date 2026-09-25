#!/usr/bin/env python3
"""Validate one causal five-state disturbance observer in shadow only."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
import traction_mpc_stage5.goal_mpc_smoke as smoke_module
from traction_mpc_stage5.goal_mpc import _SupportCenteredBatchPreview, support_action
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.matched_branch import restore_runtime_snapshot
from traction_mpc_stage5.near_limit_shadow import NearLimitShadowTarget
from traction_mpc_stage5.short_horizon_disturbance import (
    CausalShortHorizonDisturbanceObserver,
    DisturbanceCorrectedPreview,
    ShortHorizonDisturbanceState,
    predicted_physical_cuff_wrench_world,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

import run_stage5_cr12_compact_predictor_v1 as branch_util


CONTROL_DT_S = 0.005
PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])
ACCELERATION_LIMIT_RAD_S2 = np.asarray(
    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
    dtype=float,
)
CANDIDATE_OFFSETS_NM = branch_util.CANDIDATE_OFFSETS_NM
GROUPS = {
    "cr12": {
        "calibration": (0.070, 0.190, 0.270),
        "held_out": (0.125, 0.230, 0.290),
        "historical_regression": (0.040, 0.150, 0.255, 0.285, 0.300),
    },
    "ur10e": {
        "calibration": (0.075, 0.195, 0.285),
        "held_out": (0.130, 0.235, 0.335),
        "historical_regression": (0.040, 0.155, 0.270, 0.310, 0.315),
    },
}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported output type {type(value)!r}")


def _plant_factory(robot: str):
    plant_type = (
        Stage5CR12SensorBoundaryPlant
        if robot == "cr12"
        else Stage5SensorBoundaryPlant
    )

    def factory(parameters: Any):
        return plant_type(STAGE5_HUMAN, interface_parameters=parameters)

    return factory


def _all_observer_times(robot: str) -> tuple[float, ...]:
    maximum = 0.300 if robot == "cr12" else 0.340
    count = int(round((maximum - 0.020) / CONTROL_DT_S)) + 1
    return tuple(round(0.020 + index * CONTROL_DT_S, 3) for index in range(count))


def _target(robot: str, timestamp_s: float) -> NearLimitShadowTarget:
    control_index = int(round(timestamp_s / CONTROL_DT_S))
    return NearLimitShadowTarget(
        timestamp_s=timestamp_s,
        task_phase="OUTBOUND",
        mpc_cycle_offset=control_index % 4,
        boundary_proximity=0.0,
        normalized_joint_acceleration=(0.0, 0.0),
        source_trace=f"{robot}__observer__t{timestamp_s:.3f}",
    )


def _capture(robot: str, output_dir: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    targets = tuple(_target(robot, timestamp) for timestamp in _all_observer_times(robot))
    captured: dict[str, Any] = {}
    original = smoke_module.capture_diagnostic_continuation_clone

    def wrapper(**kwargs: Any):
        clone = original(**kwargs)
        source = kwargs["trigger_metadata"].get("selection_plan", {}).get(
            "source_trace"
        )
        if source is not None:
            captured[str(source)] = clone
        return clone

    smoke_module.capture_diagnostic_continuation_clone = wrapper
    try:
        rollout = output_dir / f"baseline_{robot}"
        summary = smoke_module.run_goal_mpc_smoke(
            rollout,
            maximum_duration_s=0.365,
            plant_factory=_plant_factory(robot),
            plant_case_name=f"short_horizon_disturbance_validation__{robot}",
            near_limit_shadow_targets=targets,
        )
    finally:
        smoke_module.capture_diagnostic_continuation_clone = original
    missing = [target.source_trace for target in targets if target.source_trace not in captured]
    if missing:
        raise RuntimeError(f"missing {robot} observer snapshots: {missing}")
    return summary, captured, rollout / "trace.npz"


def _trace(trace_path: Path) -> dict[float, dict[str, np.ndarray]]:
    with np.load(trace_path) as stored:
        time = np.asarray(stored["time_s"], dtype=float)
        action = np.asarray(stored["executed_generalized_action_nm"], dtype=float)
    return {
        round(float(timestamp), 12): {"action_nm": action[index].copy()}
        for index, timestamp in enumerate(time)
    }


def _clone(clones: dict[str, Any], robot: str, timestamp_s: float) -> Any:
    return clones[f"{robot}__observer__t{timestamp_s:.3f}"]


def _base_preview(
    robot: str, clone: Any, *, capture_substeps: bool = True
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    plant = clone.plant
    graph, runtime = restore_runtime_snapshot(plant, clone.snapshot)
    observation, interface, measurement, human_model, context = (
        branch_util._current_inputs(plant, graph, runtime)
    )
    preview = make_interface_aware_first_action_batch_preview(
        context.preview_command_batch,
        graph["screening_interface_predictor"],
        interface,
        q_rad=observation.as_array()[:2],
        human_model=human_model,
        cuff_allocator=graph["cuff_allocator"],
        state_rad_rad_s=observation.as_array(),
        acceleration_limits_rad_s2=ACCELERATION_LIMIT_RAD_S2,
        capture_prefix_diagnostics=True,
        capture_prefix_substeps=capture_substeps,
    )
    return preview, graph, runtime


def _predict(
    robot: str,
    clone: Any,
    action_nm: np.ndarray,
    *,
    disturbance_state: ShortHorizonDisturbanceState | None = None,
    acceleration_margin_rad_s2: np.ndarray | None = None,
    force_margin_n: float = 0.0,
) -> tuple[Any, dict[str, Any], dict[str, Any], Any]:
    preview, graph, runtime = _base_preview(robot, clone)
    if disturbance_state is not None:
        preview = DisturbanceCorrectedPreview(
            preview,
            disturbance_state,
            acceleration_error_margin_rad_s2=acceleration_margin_rad_s2,
            cuff_force_error_margin_n=force_margin_n,
        )
    observation = runtime["task_observation"]
    current_support = support_action(observation.as_array(), graph["current_model"])
    centered = _SupportCenteredBatchPreview(
        preview, current_support, graph["mpc"]._support_action_batch
    )
    graph["mpc"]._active_human_model = graph["current_model"]
    try:
        prediction = centered(
            (np.asarray(action_nm, dtype=float) - current_support)[None, :]
        )
    finally:
        graph["mpc"]._active_human_model = None
    return prediction, graph, runtime, preview


def _observer_history(
    robot: str,
    clones: dict[str, Any],
    trace: dict[float, dict[str, np.ndarray]],
) -> tuple[dict[float, ShortHorizonDisturbanceState], list[dict[str, Any]]]:
    observer = CausalShortHorizonDisturbanceObserver()
    states: dict[float, ShortHorizonDisturbanceState] = {}
    rows: list[dict[str, Any]] = []
    previous_prediction = None
    for timestamp_s in _all_observer_times(robot):
        clone = _clone(clones, robot, timestamp_s)
        preview, graph, runtime = _base_preview(robot, clone)
        observation = runtime["task_observation"]
        interface = runtime["interface_state"]
        if previous_prediction is not None:
            state = observer.update(
                previous_predicted_human_dq_rad_s=previous_prediction[
                    "human_dq_rad_s"
                ],
                measured_human_dq_hat_rad_s=observation.as_array()[2:],
                previous_predicted_cuff_force_world_n=previous_prediction[
                    "cuff_force_world_n"
                ],
                measured_cuff_force_world_n=interface.measured_force_world_n,
                prediction_supported=previous_prediction["supported"],
            )
        else:
            state = observer.state
        states[round(timestamp_s, 12)] = state
        action = trace[round(timestamp_s, 12)]["action_nm"]
        current_support = support_action(
            observation.as_array(), graph["current_model"]
        )
        centered = _SupportCenteredBatchPreview(
            preview,
            current_support,
            graph["mpc"]._support_action_batch,
        )
        graph_mpc = graph["mpc"]
        graph_mpc._active_human_model = graph["current_model"]
        try:
            prediction = centered((action - current_support)[None, :])
        finally:
            graph_mpc._active_human_model = None
        previous_prediction = {
            "human_dq_rad_s": np.asarray(
                prediction.predicted_prefix_states_rad_rad_s[0, 0, 2:], dtype=float
            ),
            "cuff_force_world_n": np.asarray(
                predicted_physical_cuff_wrench_world(preview, prediction)[0, 0, :3],
                dtype=float,
            ),
            "supported": bool(
                True
                if prediction.prediction_supported is None
                else prediction.prediction_supported[0]
            ),
        }
        rows.append(
            {
                "timestamp_s": timestamp_s,
                "state": state,
                "measured_human_dq_hat_rad_s": observation.as_array()[2:],
                "measured_cuff_force_world_n": interface.measured_force_world_n,
            }
        )
    return states, rows


def _evaluation(
    robot: str,
    group: str,
    timestamp_s: float,
    candidate_name: str,
    candidate_action_nm: np.ndarray,
    clone: Any,
    observer_state: ShortHorizonDisturbanceState,
    *,
    acceleration_margin_rad_s2: np.ndarray,
    force_margin_n: float,
) -> dict[str, Any]:
    branch = branch_util._branch_truth(
        clone,
        group=f"{robot}_{group}",
        timestamp_s=timestamp_s,
        candidate_name=candidate_name,
        candidate_action_nm=candidate_action_nm,
    )
    base, _, _, base_preview = _predict(robot, clone, candidate_action_nm)
    corrected, _, _, corrected_preview = _predict(
        robot,
        clone,
        candidate_action_nm,
        disturbance_state=observer_state,
        acceleration_margin_rad_s2=acceleration_margin_rad_s2,
        force_margin_n=force_margin_n,
    )
    truth_accel = np.asarray(branch["truth_acceleration_20ms_rad_s2"], dtype=float)
    truth_wrench = np.vstack(
        [row["physical_cuff_wrench_human_site_world"] for row in branch["endpoints"]]
    )

    def values(prediction: Any) -> dict[str, Any]:
        predicted_accel = np.asarray(
            prediction.predicted_prefix_acceleration_rad_s2[0, -1], dtype=float
        )
        prediction_preview = base_preview if prediction is base else corrected_preview
        predicted_force = predicted_physical_cuff_wrench_world(
            prediction_preview, prediction
        )[0, :, :3]
        return {
            "predicted_acceleration_20ms_deg_s2": np.degrees(predicted_accel),
            "acceleration_error_deg_s2": np.degrees(predicted_accel - truth_accel),
            "predicted_cuff_force_world_n": predicted_force,
            "force_error_world_n": predicted_force - truth_wrench[:, :3],
            "force_error_norm_n": np.linalg.norm(
                predicted_force - truth_wrench[:, :3], axis=1
            ),
            "predicted_accepted": bool(prediction.feasible[0]),
        }

    base_values = values(base)
    corrected_values = values(corrected)
    truth_force_peak = float(np.max(np.linalg.norm(truth_wrench[:, :3], axis=1)))
    truth_violating = bool(
        np.any(np.abs(truth_accel) > ACCELERATION_LIMIT_RAD_S2 + 1.0e-12)
        or truth_force_peak > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
    )
    persistence = []
    base_human = np.asarray(base.predicted_prefix_states_rad_rad_s[0], dtype=float)
    for index, endpoint in enumerate(branch["endpoints"]):
        deployable = np.asarray(
            endpoint["deployable_human_state_rad_rad_s"], dtype=float
        )
        realized_accel_residual = (
            deployable[2:] - base_human[index, 2:]
        ) / PREFIX_TIMES_S[index]
        realized_force_residual = (
            truth_wrench[index, :3]
            - np.asarray(base_values["predicted_cuff_force_world_n"][index], dtype=float)
        )
        persistence.append(
            {
                "offset_ms": 1000.0 * PREFIX_TIMES_S[index],
                "estimated_acceleration_residual_deg_s2": np.degrees(
                    observer_state.human_acceleration_residual_rad_s2
                ),
                "realized_deployable_acceleration_residual_deg_s2": np.degrees(
                    realized_accel_residual
                ),
                "estimated_force_residual_world_n": (
                    observer_state.cuff_force_residual_world_n
                ),
                "realized_force_residual_world_n": realized_force_residual,
            }
        )
    return {
        "robot": robot,
        "group": group,
        "group_id": f"{robot}_{group}__t{timestamp_s:.3f}",
        "timestamp_s": timestamp_s,
        "candidate_name": candidate_name,
        "candidate_action_nm": candidate_action_nm,
        "observer_state": observer_state,
        "base": base_values,
        "corrected": corrected_values,
        "truth_acceleration_20ms_deg_s2": np.degrees(truth_accel),
        "truth_force_peak_n": truth_force_peak,
        "truth_violating": truth_violating,
        "truth_benign": not truth_violating and bool(np.all(branch["command_feasible"])),
        "truth_any_contact": bool(branch["any_contact"]),
        "truth_maximum_contact_force_n": float(branch["maximum_contact_force_n"]),
        "persistence": persistence,
    }


def _metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    acceleration = np.vstack([row[key]["acceleration_error_deg_s2"] for row in rows])
    force_vector = np.concatenate([row[key]["force_error_world_n"] for row in rows])
    force_norm = np.linalg.norm(force_vector, axis=1)
    false_accept = [
        row for row in rows if row[key]["predicted_accepted"] and row["truth_violating"]
    ]
    benign = [row for row in rows if row["truth_benign"]]
    accepted_benign = [row for row in benign if row[key]["predicted_accepted"]]
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(acceleration), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(
            np.abs(acceleration), axis=0
        ),
        "cuff_force_vector_rmse_n": float(
            np.sqrt(np.mean(np.sum(force_vector * force_vector, axis=1)))
        ),
        "cuff_force_error_p95_n": float(np.percentile(force_norm, 95.0)),
        "cuff_force_error_max_n": float(np.max(force_norm)),
        "predicted_accepted_truth_violating_count": len(false_accept),
        "predicted_accepted_truth_violating_cases": [
            f"{row['group_id']}::{row['candidate_name']}" for row in false_accept
        ],
        "truth_benign_count": len(benign),
        "accepted_benign_count": len(accepted_benign),
        "benign_acceptance_coverage": (
            None if not benign else len(accepted_benign) / len(benign)
        ),
    }


def _persistence_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for prefix_index, time_ms in enumerate((5, 10, 15, 20)):
        estimated_accel = np.vstack(
            [
                row["persistence"][prefix_index][
                    "estimated_acceleration_residual_deg_s2"
                ]
                for row in rows
            ]
        )
        realized_accel = np.vstack(
            [
                row["persistence"][prefix_index][
                    "realized_deployable_acceleration_residual_deg_s2"
                ]
                for row in rows
            ]
        )
        estimated_force = np.vstack(
            [
                row["persistence"][prefix_index]["estimated_force_residual_world_n"]
                for row in rows
            ]
        )
        realized_force = np.vstack(
            [
                row["persistence"][prefix_index]["realized_force_residual_world_n"]
                for row in rows
            ]
        )
        accel_sign = np.mean(np.sign(estimated_accel) == np.sign(realized_accel), axis=0)
        force_dot = np.sum(estimated_force * realized_force, axis=1)
        force_denom = np.linalg.norm(estimated_force, axis=1) * np.linalg.norm(
            realized_force, axis=1
        )
        force_cosine = np.divide(
            force_dot,
            force_denom,
            out=np.zeros_like(force_dot),
            where=force_denom > 1.0e-12,
        )
        result[f"{time_ms}ms"] = {
            "acceleration_sign_agreement": accel_sign,
            "acceleration_residual_mae_deg_s2": np.mean(
                np.abs(estimated_accel - realized_accel), axis=0
            ),
            "force_residual_vector_rmse_n": float(
                np.sqrt(np.mean(np.sum((estimated_force - realized_force) ** 2, axis=1)))
            ),
            "force_direction_cosine_median": float(np.median(force_cosine)),
        }
    return result


def _runtime(
    held_out: list[dict[str, Any]],
    clones: dict[str, dict[str, Any]],
    states: dict[str, dict[float, ShortHorizonDisturbanceState]],
    acceleration_margin: np.ndarray,
    force_margin: float,
    repeats: int,
) -> dict[str, Any]:
    unique = {}
    for row in held_out:
        unique[(row["robot"], row["timestamp_s"])] = row
    samples = []
    statuses = []
    for (robot, timestamp_s), _ in unique.items():
        clone = _clone(clones[robot], robot, timestamp_s)
        for _ in range(repeats):
            preview, graph, runtime = _base_preview(
                robot, clone, capture_substeps=False
            )
            corrected = DisturbanceCorrectedPreview(
                preview,
                states[robot][round(timestamp_s, 12)],
                acceleration_error_margin_rad_s2=acceleration_margin,
                cuff_force_error_margin_n=force_margin,
            )
            started = perf_counter()
            _, diagnostics = graph["mpc"].solve_goal(
                runtime["task_observation"],
                runtime["authoritative_task_state"],
                PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                graph["current_model"],
                first_action_batch_preview=corrected,
            )
            samples.append(1000.0 * (perf_counter() - started))
            statuses.append(str(diagnostics["status"]))
    values = np.asarray(samples, dtype=float)
    return {
        "sample_count": len(values),
        "repeats_per_state": repeats,
        "p50_ms": float(np.percentile(values, 50.0)),
        "p95_ms": float(np.percentile(values, 95.0)),
        "p99_ms": float(np.percentile(values, 99.0)),
        "maximum_ms": float(np.max(values)),
        "deadline_miss_count": int(np.count_nonzero(values >= 20.0)),
        "statuses": statuses,
        "complete_goal_mpc_solve_timed": True,
        "existing_cem_settings_unchanged": True,
    }


def _plot(output_dir: Path, histories: dict[str, list[dict[str, Any]]]) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    colors = {"cr12": "#d95f02", "ur10e": "#1b9e77"}
    for robot, rows in histories.items():
        time = [row["timestamp_s"] for row in rows]
        accel = np.vstack(
            [row["state"].human_acceleration_residual_rad_s2 for row in rows]
        )
        force = np.vstack([row["state"].cuff_force_residual_world_n for row in rows])
        axes[0, 0].plot(time, np.degrees(accel[:, 0]), label=robot, color=colors[robot])
        axes[0, 1].plot(time, np.degrees(accel[:, 1]), label=robot, color=colors[robot])
        axes[1, 0].plot(time, np.linalg.norm(force, axis=1), label=robot, color=colors[robot])
        axes[1, 1].plot(
            time,
            [row["state"].history_coverage_s * 1000.0 for row in rows],
            label=robot,
            color=colors[robot],
        )
    axes[0, 0].set_ylabel("hip disturbance [deg/s2]")
    axes[0, 1].set_ylabel("knee disturbance [deg/s2]")
    axes[1, 0].set_ylabel("force disturbance norm [N]")
    axes[1, 1].set_ylabel("causal history coverage [ms]")
    for axis in axes.flat:
        axis.set_xlabel("rollout time [s]")
        axis.grid(alpha=0.25)
        axis.legend()
    path = output_dir / "disturbance_estimate_history.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path.name


def run(output_dir: Path, *, runtime_repeats: int) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    baselines: dict[str, Any] = {}
    clones: dict[str, dict[str, Any]] = {}
    traces: dict[str, dict[float, dict[str, np.ndarray]]] = {}
    states: dict[str, dict[float, ShortHorizonDisturbanceState]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    for robot in ("cr12", "ur10e"):
        baseline, captured, trace_path = _capture(robot, output_dir)
        baselines[robot] = baseline
        clones[robot] = captured
        traces[robot] = _trace(trace_path)
        states[robot], histories[robot] = _observer_history(
            robot, captured, traces[robot]
        )

    preliminary: list[dict[str, Any]] = []
    zero_margin = np.zeros(2)
    for robot in ("cr12", "ur10e"):
        for group, timestamps in GROUPS[robot].items():
            for timestamp_s in timestamps:
                clone = _clone(clones[robot], robot, timestamp_s)
                selected = traces[robot][round(timestamp_s, 12)]["action_nm"]
                state = states[robot][round(timestamp_s, 12)]
                for name, offset in CANDIDATE_OFFSETS_NM.items():
                    preliminary.append(
                        _evaluation(
                            robot,
                            group,
                            timestamp_s,
                            name,
                            selected + offset,
                            clone,
                            state,
                            acceleration_margin_rad_s2=zero_margin,
                            force_margin_n=0.0,
                        )
                    )
    calibration = [row for row in preliminary if row["group"] == "calibration"]
    acceleration_margin_deg = np.max(
        np.abs(
            np.vstack(
                [row["corrected"]["acceleration_error_deg_s2"] for row in calibration]
            )
        ),
        axis=0,
    )
    force_margin = float(
        np.max(
            np.concatenate(
                [row["corrected"]["force_error_norm_n"] for row in calibration]
            )
        )
    )

    evaluated: list[dict[str, Any]] = []
    for robot in ("cr12", "ur10e"):
        for group, timestamps in GROUPS[robot].items():
            for timestamp_s in timestamps:
                clone = _clone(clones[robot], robot, timestamp_s)
                selected = traces[robot][round(timestamp_s, 12)]["action_nm"]
                state = states[robot][round(timestamp_s, 12)]
                for name, offset in CANDIDATE_OFFSETS_NM.items():
                    evaluated.append(
                        _evaluation(
                            robot,
                            group,
                            timestamp_s,
                            name,
                            selected + offset,
                            clone,
                            state,
                            acceleration_margin_rad_s2=np.radians(
                                acceleration_margin_deg
                            ),
                            force_margin_n=force_margin,
                        )
                    )
    held_out = [row for row in evaluated if row["group"] == "held_out"]
    regression = [
        row for row in evaluated if row["group"] == "historical_regression"
    ]
    base_metrics = _metrics(held_out, "base")
    corrected_metrics = _metrics(held_out, "corrected")
    per_robot = {
        robot: {
            "base": _metrics([row for row in held_out if row["robot"] == robot], "base"),
            "corrected": _metrics(
                [row for row in held_out if row["robot"] == robot], "corrected"
            ),
        }
        for robot in ("cr12", "ur10e")
    }
    per_anchor = {
        f"{robot}_t{timestamp:.3f}": {
            "base": _metrics(
                [
                    row
                    for row in held_out
                    if row["robot"] == robot and np.isclose(row["timestamp_s"], timestamp)
                ],
                "base",
            ),
            "corrected": _metrics(
                [
                    row
                    for row in held_out
                    if row["robot"] == robot and np.isclose(row["timestamp_s"], timestamp)
                ],
                "corrected",
            ),
        }
        for robot in ("cr12", "ur10e")
        for timestamp in GROUPS[robot]["held_out"]
    }
    persistence = _persistence_metrics(held_out)
    runtime = _runtime(
        held_out,
        clones,
        states,
        np.radians(acceleration_margin_deg),
        force_margin,
        runtime_repeats,
    )
    criteria = {
        "human_acceleration": {
            "threshold_deg_s2": [30.0, 60.0],
            "observed_p95_deg_s2": corrected_metrics[
                "acceleration_absolute_error_p95_deg_s2"
            ],
            "status": (
                "PASS"
                if np.all(
                    np.asarray(
                        corrected_metrics["acceleration_absolute_error_p95_deg_s2"]
                    )
                    <= np.asarray([30.0, 60.0])
                )
                else "FAIL"
            ),
        },
        "cuff_force": {
            "rmse_threshold_n": 5.0,
            "p95_threshold_n": 10.0,
            "observed_rmse_n": corrected_metrics["cuff_force_vector_rmse_n"],
            "observed_p95_n": corrected_metrics["cuff_force_error_p95_n"],
            "status": (
                "PASS"
                if corrected_metrics["cuff_force_vector_rmse_n"] <= 5.0
                and corrected_metrics["cuff_force_error_p95_n"] <= 10.0
                else "FAIL"
            ),
        },
        "finite_set_feasibility": {
            "false_acceptance_count": corrected_metrics[
                "predicted_accepted_truth_violating_count"
            ],
            "benign_acceptance_coverage": corrected_metrics[
                "benign_acceptance_coverage"
            ],
            "status": (
                "PASS"
                if corrected_metrics[
                    "predicted_accepted_truth_violating_count"
                ]
                == 0
                and (corrected_metrics["benign_acceptance_coverage"] or 0.0) > 0.0
                else "FAIL"
            ),
        },
        "runtime": {
            "p95_threshold_ms": 20.0,
            "observed_p95_ms": runtime["p95_ms"],
            "observed_p99_ms": runtime["p99_ms"],
            "observed_maximum_ms": runtime["maximum_ms"],
            "deadline_miss_count": runtime["deadline_miss_count"],
            "status": "PASS" if runtime["p95_ms"] < 20.0 else "FAIL",
        },
    }
    critical_rows = [
        row
        for row in held_out
        if row["robot"] == "cr12" and np.isclose(row["timestamp_s"], 0.290)
    ]
    critical_base = _metrics(critical_rows, "base")
    critical_corrected = _metrics(critical_rows, "corrected")
    critical_accuracy_pass = bool(
        np.all(
            np.asarray(
                critical_corrected["acceleration_absolute_error_p95_deg_s2"]
            )
            <= np.asarray([30.0, 60.0])
        )
        and critical_corrected["cuff_force_vector_rmse_n"] <= 5.0
        and critical_corrected["cuff_force_error_p95_n"] <= 10.0
    )
    critical_acceleration_improved = bool(
        np.all(
            np.asarray(
                critical_corrected["acceleration_absolute_error_p95_deg_s2"]
            )
            < np.asarray(critical_base["acceleration_absolute_error_p95_deg_s2"])
        )
    )
    critical = {
        "base": critical_base,
        "corrected": critical_corrected,
        "contact_candidate_count": int(
            sum(row["truth_maximum_contact_force_n"] > 1.0e-6 for row in critical_rows)
        ),
        "observer_state_at_window_start": critical_rows[0]["observer_state"],
        "causal_estimate_available_before_branch": bool(
            critical_rows[0]["observer_state"].valid
        ),
        "early_correction_reduces_acceleration_error": (
            critical_acceleration_improved
        ),
        "early_correction_meets_accuracy_criteria": critical_accuracy_pass,
        "timeliness_interpretation": (
            "estimate is available before the contact-adjacent branch and reduces "
            "error, but it is not accurate enough to qualify critical candidates"
            if critical_acceleration_improved and not critical_accuracy_pass
            else (
                "estimate is available early enough and meets the finite accuracy "
                "criteria"
                if critical_accuracy_pass
                else "estimate does not provide useful pre-event correction"
            )
        ),
    }
    smooth_anchor_improvement = any(
        np.sum(
            np.asarray(metrics["corrected"]["acceleration_absolute_error_p95_deg_s2"])
        )
        < np.sum(np.asarray(metrics["base"]["acceleration_absolute_error_p95_deg_s2"]))
        for anchor, metrics in per_anchor.items()
        if anchor != "cr12_t0.290"
    )
    every_criterion_passes = all(item["status"] == "PASS" for item in criteria.values())
    if every_criterion_passes and critical_accuracy_pass:
        decision = "DO-A — LOW-DIMENSION DISTURBANCE ESTIMATION IS SUFFICIENT"
    elif smooth_anchor_improvement:
        decision = "DO-B — HELPS IN SMOOTH REGIONS BUT CANNOT HANDLE CRITICAL STATES"
    else:
        decision = (
            "DO-C — CURRENT ERROR CANNOT BE USEFULLY REPRESENTED BY THIS "
            "DISTURBANCE MODEL"
        )
    result = {
        "schema": "stage5_short_horizon_disturbance_observer_v1",
        "evidence_category": "bounded_shadow_engineering_validation",
        "decision": decision,
        "observer_contract": CausalShortHorizonDisturbanceObserver().record(),
        "base_predictor": "current_default_interface_aware_preview_frozen",
        "groups": GROUPS,
        "historical_windows_used_as_final_test": False,
        "complete_event_group_split": True,
        "calibration_qualification": {
            "acceleration_margin_deg_s2": acceleration_margin_deg,
            "force_margin_n": force_margin,
            "source": "calibration groups only; componentwise/max absolute error",
            "guaranteed_bound": False,
        },
        "held_out": {
            "base_metrics": base_metrics,
            "corrected_metrics": corrected_metrics,
            "per_robot": per_robot,
            "per_anchor": per_anchor,
            "persistence": persistence,
            "critical_contact_adjacent": critical,
        },
        "historical_regression": {
            "base": _metrics(regression, "base"),
            "corrected": _metrics(regression, "corrected"),
        },
        "runtime": runtime,
        "criteria": criteria,
        "baseline_results": {
            robot: {
                "task_status": baselines[robot]["task_status"],
                "abort_reason": baselines[robot]["abort_reason"],
            }
            for robot in ("cr12", "ur10e")
        },
        "observer_history": histories,
        "evaluated_cases": evaluated,
        "plot": _plot(output_dir, histories),
        "residual_learning_validation_justified": decision != (
            "DO-A — LOW-DIMENSION DISTURBANCE ESTIMATION IS SUFFICIENT"
        ),
        "one_next_step": (
            "validate one deployable-state residual learner for the interface/Human "
            "response, with held-out robot/event groups and explicit contact-adjacent "
            "timeliness scoring"
        ),
        "scope_invariants": {
            "shadow_only": True,
            "mujoco_truth_used_online": False,
            "mpc_actions_changed": False,
            "abort_authority_changed": False,
            "thresholds_changed": False,
            "task_changed": False,
            "human_model_changed": False,
            "contact_model_changed": False,
            "rl_or_value_changed": False,
            "stage3_or_stage4_changed": False,
        },
    }
    (output_dir / "disturbance_validation.json").write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "engineering_validation"
            / "short_horizon_disturbance_observer_v1_attempt_01"
        ),
    )
    parser.add_argument("--runtime-repeats", type=int, default=3)
    args = parser.parse_args()
    if args.runtime_repeats < 1:
        raise ValueError("runtime repeats must be positive")
    result = run(args.output_dir, runtime_repeats=args.runtime_repeats)
    compact = {
        "decision": result["decision"],
        "calibration_qualification": result["calibration_qualification"],
        "held_out_base_metrics": result["held_out"]["base_metrics"],
        "held_out_corrected_metrics": result["held_out"]["corrected_metrics"],
        "critical_contact_adjacent": result["held_out"][
            "critical_contact_adjacent"
        ],
        "persistence": result["held_out"]["persistence"],
        "runtime": result["runtime"],
        "criteria": result["criteria"],
    }
    print(json.dumps(_jsonable(compact), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
