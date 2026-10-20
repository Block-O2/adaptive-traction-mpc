#!/usr/bin/env python3
"""Validate one low-capacity state-dependent Human transition residual."""

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
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc import support_action
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.matched_branch import restore_runtime_snapshot
from traction_mpc_stage5.short_horizon_disturbance import (
    DisturbanceCorrectedPreview,
    predicted_physical_cuff_wrench_world,
)
from traction_mpc_stage5.short_horizon_residual import (
    ResidualCorrectedPreview,
    fit_state_dependent_human_transition_residual_v1,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

import run_stage5_cr12_compact_predictor_v1 as branch_util
import validate_stage5_short_horizon_disturbance as disturbance_util


CONTROL_DT_S = 0.005
PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])
ACCELERATION_LIMIT_RAD_S2 = np.asarray(
    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
    dtype=float,
)
CANDIDATE_OFFSETS_NM = branch_util.CANDIDATE_OFFSETS_NM
SPLITS = {
    "cr12": {
        "train": (0.045, 0.065, 0.145, 0.170, 0.190, 0.250),
        "calibration": (0.090, 0.210, 0.270),
        "held_out": (0.115, 0.235, 0.310),
        "historical_regression": (0.100, 0.200, 0.260, 0.280, 0.285, 0.290, 0.300, 0.305),
    },
    "ur10e": {
        "train": (0.045, 0.065, 0.145, 0.170, 0.195, 0.220, 0.285),
        "calibration": (0.090, 0.235, 0.325),
        "held_out": (0.125, 0.260, 0.350),
        "historical_regression": (0.100, 0.200, 0.270, 0.310, 0.315, 0.335),
    },
}
HELD_OUT_REGIONS = {
    ("cr12", 0.115): "smooth",
    ("cr12", 0.235): "near_limit",
    ("cr12", 0.310): "contact_adjacent",
    ("ur10e", 0.125): "smooth",
    ("ur10e", 0.260): "near_limit",
    ("ur10e", 0.350): "near_limit",
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
    raise TypeError(f"unsupported JSON value {type(value)!r}")


def _all_times(robot: str) -> tuple[float, ...]:
    maximum = 0.310 if robot == "cr12" else 0.350
    count = int(round((maximum - 0.020) / CONTROL_DT_S)) + 1
    return tuple(round(0.020 + index * CONTROL_DT_S, 3) for index in range(count))


def _shank_clearance_from_q_hat(q_rad: np.ndarray) -> float:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    plane_x = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 0])
    plane_z = np.asarray(STAGE5_GEOMETRY.world_from_human.rotation[:, 2])
    hip = np.asarray(STAGE5_GEOMETRY.world_from_human.translation)
    knee = hip + STAGE5_HUMAN.thigh_length_m * (
        np.cos(q1) * plane_x + np.sin(q1) * plane_z
    )
    ankle = knee + STAGE5_HUMAN.shank_length_m * (
        np.cos(phi) * plane_x + np.sin(phi) * plane_z
    )
    return float(min(knee[2], ankle[2]) - SHANK_RADIUS_M - BED_HEIGHT_M)


def _feature_context(
    robot: str,
    clone: Any,
    trace: dict[float, dict[str, np.ndarray]],
    timestamp_s: float,
) -> tuple[dict[str, Any], Any]:
    plant = clone.plant
    graph, runtime = restore_runtime_snapshot(plant, clone.snapshot)
    observation, interface, measurement, _, _ = branch_util._current_inputs(
        plant, graph, runtime
    )
    q_hat = observation.as_array()[:2]
    previous_action = trace[round(timestamp_s - CONTROL_DT_S, 12)]["action_nm"]
    older_action = trace[round(timestamp_s - 2.0 * CONTROL_DT_S, 12)]["action_nm"]
    rotation_vector = Rotation.from_matrix(
        np.asarray(measurement.attachment_rotation_matrix, dtype=float)
    ).as_rotvec()
    blocks = [
        ("robot_q", np.asarray(measurement.robot_q_rad, dtype=float)),
        ("robot_dq", np.asarray(measurement.robot_dq_rad_s, dtype=float)),
        ("human", observation.as_array()),
        ("cuff_position", np.asarray(measurement.attachment_position_m, dtype=float)),
        ("cuff_rotvec", rotation_vector),
        ("cuff_linear_velocity", np.asarray(measurement.attachment_velocity_m_s, dtype=float)),
        ("cuff_angular_velocity", np.asarray(measurement.attachment_angular_velocity_rad_s, dtype=float)),
        ("interface_displacement", np.asarray(interface.displacement_human_m, dtype=float)),
        ("interface_velocity", np.asarray(interface.velocity_human_m_s, dtype=float)),
        ("interface_rotation", np.asarray(interface.rotation_error_human_rad, dtype=float)),
        ("interface_angular_velocity", np.asarray(interface.angular_velocity_human_rad_s, dtype=float)),
        ("measured_force", np.asarray(interface.measured_force_world_n, dtype=float)),
        ("measured_moment", np.asarray(interface.measured_moment_world_nm, dtype=float)),
        ("previous_action", np.asarray(previous_action, dtype=float)),
        ("previous_action_delta", np.asarray(previous_action - older_action, dtype=float)),
        ("shank_clearance", np.asarray([_shank_clearance_from_q_hat(q_hat)])),
        ("robot_identity_cr12", np.asarray([1.0 if robot == "cr12" else 0.0])),
    ]
    static = np.concatenate([value for _, value in blocks])
    names = []
    for name, value in blocks:
        names.extend(f"{name}_{index}" for index in range(len(value)))
    names.extend(("candidate_action_0", "candidate_action_1"))
    names.extend(("candidate_minus_previous_0", "candidate_minus_previous_1"))

    def feature_batch(actions_nm: np.ndarray) -> np.ndarray:
        actions = np.asarray(actions_nm, dtype=float)
        if actions.ndim == 1:
            actions = actions[None, :]
        return np.column_stack(
            [
                np.broadcast_to(static, (len(actions), len(static))),
                actions,
                actions - previous_action[None, :],
            ]
        )

    context = {
        "feature_names": tuple(names),
        "initial_human_state_rad_rad_s": observation.as_array(),
        "shank_clearance_m": _shank_clearance_from_q_hat(q_hat),
        "previous_action_nm": previous_action,
    }
    return context, feature_batch


def _corrected_states(
    base_states: np.ndarray, dq_residual: np.ndarray
) -> np.ndarray:
    states = np.asarray(base_states, dtype=float).copy()
    states[..., 2:] += dq_residual
    q_residual = np.zeros((len(states), 2), dtype=float)
    previous = np.zeros((len(states), 2), dtype=float)
    previous_time = 0.0
    for index, time_s in enumerate(PREFIX_TIMES_S):
        dt = time_s - previous_time
        q_residual += 0.5 * dt * (previous + dq_residual[:, index])
        states[:, index, :2] += q_residual
        previous = dq_residual[:, index]
        previous_time = time_s
    return states


def _build_case(
    robot: str,
    split: str,
    timestamp_s: float,
    candidate_name: str,
    action_nm: np.ndarray,
    clone: Any,
    trace: dict[float, dict[str, np.ndarray]],
    observer_state: Any,
) -> dict[str, Any]:
    context, feature_batch = _feature_context(robot, clone, trace, timestamp_s)
    feature = feature_batch(action_nm)[0]
    base, graph, _, preview = disturbance_util._predict(robot, clone, action_nm)
    branch = branch_util._branch_truth(
        clone,
        group=f"residual_{robot}_{split}",
        timestamp_s=timestamp_s,
        candidate_name=candidate_name,
        candidate_action_nm=action_nm,
    )
    truth_states = np.vstack(
        [endpoint["deployable_human_state_rad_rad_s"] for endpoint in branch["endpoints"]]
    )
    base_states = np.asarray(base.predicted_prefix_states_rad_rad_s[0], dtype=float)
    base_wrench = predicted_physical_cuff_wrench_world(preview, base)[0]
    truth_wrench = np.vstack(
        [endpoint["physical_cuff_wrench_human_site_world"] for endpoint in branch["endpoints"]]
    )
    truth_acceleration = (
        truth_states[:, 2:] - context["initial_human_state_rad_rad_s"][None, 2:]
    ) / PREFIX_TIMES_S[:, None]
    base_acceleration = np.asarray(
        base.predicted_prefix_acceleration_rad_s2[0], dtype=float
    )
    return {
        "robot": robot,
        "split": split,
        "region": HELD_OUT_REGIONS.get((robot, timestamp_s), "regression"),
        "group_id": f"{robot}_{split}_t{timestamp_s:.3f}",
        "timestamp_s": timestamp_s,
        "candidate_name": candidate_name,
        "candidate_action_nm": np.asarray(action_nm, dtype=float),
        "feature": feature,
        "feature_context": context,
        "base_states": base_states,
        "truth_states": truth_states,
        "base_wrench": base_wrench,
        "truth_wrench": truth_wrench,
        "base_acceleration": base_acceleration,
        "truth_acceleration": truth_acceleration,
        "target_dq_residual_rad_s": truth_states[:, 2:] - base_states[:, 2:],
        "base_predicted_accepted": bool(base.feasible[0]),
        "base_executable_feasible": bool(base.executable_batch.feasible[0]),
        "base_force_margin_n": float(base.margin_to_physical_force_gate_n[0]),
        "planning_force_ceiling_n": float(preview.predictor.planning_force_ceiling_n),
        "observer_state": observer_state,
        "truth_command_feasible": bool(np.all(branch["command_feasible"])),
        "truth_any_contact": bool(branch["any_contact"]),
        "truth_maximum_contact_force_n": float(branch["maximum_contact_force_n"]),
    }


def _prediction_values(
    row: dict[str, Any],
    *,
    states: np.ndarray,
    wrench: np.ndarray,
    accepted: bool,
    supported: bool,
) -> dict[str, Any]:
    acceleration = (
        states[:, 2:]
        - row["feature_context"]["initial_human_state_rad_rad_s"][None, 2:]
    ) / PREFIX_TIMES_S[:, None]
    truth_acceleration = row["truth_acceleration"]
    truth_force = row["truth_wrench"][:, :3]
    predicted_force = wrench[:, :3]
    return {
        "predicted_states_rad_rad_s": states,
        "predicted_acceleration_deg_s2": np.degrees(acceleration),
        "acceleration_error_deg_s2": np.degrees(acceleration - truth_acceleration),
        "predicted_cuff_force_world_n": predicted_force,
        "force_error_world_n": predicted_force - truth_force,
        "force_error_norm_n": np.linalg.norm(predicted_force - truth_force, axis=1),
        "predicted_accepted": bool(accepted),
        "supported": bool(supported),
    }


def _truth_labels(row: dict[str, Any]) -> tuple[bool, bool]:
    truth_force_peak = float(
        np.max(np.linalg.norm(row["truth_wrench"][:, :3], axis=1))
    )
    violating = bool(
        np.any(np.abs(row["truth_acceleration"][-1]) > ACCELERATION_LIMIT_RAD_S2)
        or truth_force_peak > CUFF_TRANSLATIONAL_FORCE_GATE_N
    )
    benign = not violating and row["truth_command_feasible"]
    return violating, benign


def _apply_models(
    rows: list[dict[str, Any]],
    model: Any,
    residual_acceleration_margin: np.ndarray,
    residual_force_margin_n: float,
    observer_acceleration_margin: np.ndarray,
    observer_force_margin_n: float,
) -> None:
    for row in rows:
        feature = row["feature"][None, :]
        residual_dq, residual_supported = model.predict(feature)
        residual_states = _corrected_states(
            row["base_states"][None, ...], residual_dq
        )[0]
        observer = row["observer_state"]
        observer_states = row["base_states"].copy()
        acceleration_residual = observer.human_acceleration_residual_rad_s2
        observer_states[:, :2] += 0.5 * PREFIX_TIMES_S[:, None] ** 2 * acceleration_residual
        observer_states[:, 2:] += PREFIX_TIMES_S[:, None] * acceleration_residual
        observer_wrench = row["base_wrench"].copy()
        observer_wrench[:, :3] += observer.cuff_force_residual_world_n

        def accepted(
            states: np.ndarray,
            wrench: np.ndarray,
            supported: bool,
            accel_margin: np.ndarray,
            force_margin_n: float,
        ) -> bool:
            acceleration = (
                states[:, 2:]
                - row["feature_context"]["initial_human_state_rad_rad_s"][None, 2:]
            ) / PREFIX_TIMES_S[:, None]
            acceleration_ok = np.all(
                np.abs(acceleration) + accel_margin[None, :]
                <= ACCELERATION_LIMIT_RAD_S2[None, :] + 1.0e-12
            )
            force_ok = (
                np.max(np.linalg.norm(wrench[:, :3], axis=1)) + force_margin_n
                <= row["planning_force_ceiling_n"] + 1.0e-9
            )
            return bool(
                row["base_executable_feasible"]
                and supported
                and acceleration_ok
                and force_ok
            )

        row["base"] = _prediction_values(
            row,
            states=row["base_states"],
            wrench=row["base_wrench"],
            accepted=row["base_predicted_accepted"],
            supported=True,
        )
        row["residual"] = _prediction_values(
            row,
            states=residual_states,
            wrench=row["base_wrench"],
            accepted=accepted(
                residual_states,
                row["base_wrench"],
                bool(residual_supported[0]),
                residual_acceleration_margin,
                residual_force_margin_n,
            ),
            supported=bool(residual_supported[0]),
        )
        row["observer"] = _prediction_values(
            row,
            states=observer_states,
            wrench=observer_wrench,
            accepted=accepted(
                observer_states,
                observer_wrench,
                bool(observer.valid),
                observer_acceleration_margin,
                observer_force_margin_n,
            ),
            supported=bool(observer.valid),
        )
        row["truth_violating"], row["truth_benign"] = _truth_labels(row)


def _calibration_margins(rows: list[dict[str, Any]], model: Any) -> dict[str, Any]:
    residual_acceleration = []
    residual_force = []
    observer_acceleration = []
    observer_force = []
    for row in rows:
        residual_dq, _ = model.predict(row["feature"][None, :])
        residual_states = _corrected_states(
            row["base_states"][None, ...], residual_dq
        )[0]
        residual_acceleration.append(
            np.abs(
                (
                    residual_states[:, 2:]
                    - row["feature_context"]["initial_human_state_rad_rad_s"][None, 2:]
                )
                / PREFIX_TIMES_S[:, None]
                - row["truth_acceleration"]
            )
        )
        residual_force.append(
            np.linalg.norm(
                row["base_wrench"][:, :3] - row["truth_wrench"][:, :3], axis=1
            )
        )
        observer = row["observer_state"]
        observer_states = row["base_states"].copy()
        observer_states[:, :2] += (
            0.5
            * PREFIX_TIMES_S[:, None] ** 2
            * observer.human_acceleration_residual_rad_s2
        )
        observer_states[:, 2:] += (
            PREFIX_TIMES_S[:, None]
            * observer.human_acceleration_residual_rad_s2
        )
        observer_acceleration.append(
            np.abs(
                (
                    observer_states[:, 2:]
                    - row["feature_context"]["initial_human_state_rad_rad_s"][None, 2:]
                )
                / PREFIX_TIMES_S[:, None]
                - row["truth_acceleration"]
            )
        )
        observer_force.append(
            np.linalg.norm(
                row["base_wrench"][:, :3]
                + observer.cuff_force_residual_world_n[None, :]
                - row["truth_wrench"][:, :3],
                axis=1,
            )
        )
    return {
        "residual_acceleration_rad_s2": np.max(
            np.concatenate(residual_acceleration), axis=0
        ),
        "residual_force_n": float(np.max(np.concatenate(residual_force))),
        "observer_acceleration_rad_s2": np.max(
            np.concatenate(observer_acceleration), axis=0
        ),
        "observer_force_n": float(np.max(np.concatenate(observer_force))),
    }


def _metrics(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    acceleration = np.vstack([row[method]["acceleration_error_deg_s2"][-1] for row in rows])
    force = np.concatenate([row[method]["force_error_world_n"] for row in rows])
    force_norm = np.linalg.norm(force, axis=1)
    false_accept = [
        row for row in rows if row[method]["predicted_accepted"] and row["truth_violating"]
    ]
    benign = [row for row in rows if row["truth_benign"]]
    accepted_benign = [row for row in benign if row[method]["predicted_accepted"]]
    worst_accel_index = np.unravel_index(np.argmax(np.abs(acceleration)), acceleration.shape)
    worst_row = rows[worst_accel_index[0]]
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(acceleration), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(np.abs(acceleration), axis=0),
        "cuff_force_vector_rmse_n": float(
            np.sqrt(np.mean(np.sum(force * force, axis=1)))
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
        "supported_count": int(sum(row[method]["supported"] for row in rows)),
        "worst_acceleration_case": {
            "case": f"{worst_row['group_id']}::{worst_row['candidate_name']}",
            "joint": ("hip", "knee")[worst_accel_index[1]],
            "absolute_error_deg_s2": float(abs(acceleration[worst_accel_index])),
        },
    }


def _runtime(
    held_out: list[dict[str, Any]],
    clones: dict[str, dict[str, Any]],
    traces: dict[str, dict[float, dict[str, np.ndarray]]],
    model: Any,
    acceleration_margin: np.ndarray,
    force_margin_n: float,
    repeats: int,
) -> dict[str, Any]:
    samples = []
    statuses = []
    groups = {(row["robot"], row["timestamp_s"]) for row in held_out}
    for robot, timestamp_s in sorted(groups):
        clone = disturbance_util._clone(clones[robot], robot, timestamp_s)
        for _ in range(repeats):
            preview, graph, runtime = disturbance_util._base_preview(
                robot, clone, capture_substeps=False
            )
            context, feature_batch = _feature_context(
                robot, clone, traces[robot], timestamp_s
            )
            corrected = ResidualCorrectedPreview(
                preview,
                model,
                feature_batch,
                initial_human_dq_rad_s=context["initial_human_state_rad_rad_s"][2:],
                acceleration_limits_rad_s2=ACCELERATION_LIMIT_RAD_S2,
                acceleration_error_margin_rad_s2=acceleration_margin,
                cuff_force_error_margin_n=force_margin_n,
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
    values = np.asarray(samples)
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


def _plot(output_dir: Path, per_region: dict[str, Any]) -> str:
    regions = ("smooth", "near_limit", "contact_adjacent")
    methods = ("base", "observer", "residual")
    colors = {"base": "#666666", "observer": "#1b9e77", "residual": "#d95f02"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    x = np.arange(len(regions))
    width = 0.24
    for index, method in enumerate(methods):
        hip = [per_region[region][method]["acceleration_absolute_error_p95_deg_s2"][0] for region in regions]
        knee = [per_region[region][method]["acceleration_absolute_error_p95_deg_s2"][1] for region in regions]
        axes[0].bar(x + (index - 1) * width, hip, width, label=method, color=colors[method])
        axes[1].bar(x + (index - 1) * width, knee, width, label=method, color=colors[method])
    axes[0].axhline(30.0, color="black", linestyle="--", linewidth=1)
    axes[1].axhline(60.0, color="black", linestyle="--", linewidth=1)
    for axis, joint in zip(axes, ("hip", "knee")):
        axis.set_xticks(x, regions, rotation=15)
        axis.set_ylabel(f"{joint} 20 ms error p95 [deg/s2]")
        axis.grid(axis="y", alpha=0.25)
        axis.legend()
    path = output_dir / "heldout_error_by_region.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path.name


def run(output_dir: Path, *, runtime_repeats: int) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    disturbance_util._all_observer_times = _all_times
    baselines = {}
    clones = {}
    traces = {}
    observer_states = {}
    for robot in ("cr12", "ur10e"):
        baseline, captured, trace_path = disturbance_util._capture(robot, output_dir)
        baselines[robot] = baseline
        clones[robot] = captured
        traces[robot] = disturbance_util._trace(trace_path)
        observer_states[robot], _ = disturbance_util._observer_history(
            robot, captured, traces[robot]
        )

    rows = []
    feature_names = None
    for robot in ("cr12", "ur10e"):
        for split, timestamps in SPLITS[robot].items():
            for timestamp_s in timestamps:
                clone = disturbance_util._clone(clones[robot], robot, timestamp_s)
                selected = traces[robot][round(timestamp_s, 12)]["action_nm"]
                for name, offset in CANDIDATE_OFFSETS_NM.items():
                    row = _build_case(
                        robot,
                        split,
                        timestamp_s,
                        name,
                        selected + offset,
                        clone,
                        traces[robot],
                        observer_states[robot][round(timestamp_s, 12)],
                    )
                    feature_names = row["feature_context"]["feature_names"]
                    rows.append(row)

    train = [row for row in rows if row["split"] == "train"]
    calibration = [row for row in rows if row["split"] == "calibration"]
    held_out = [row for row in rows if row["split"] == "held_out"]
    regression = [row for row in rows if row["split"] == "historical_regression"]
    assert feature_names is not None
    model = fit_state_dependent_human_transition_residual_v1(
        features=np.vstack([row["feature"] for row in train]),
        dq_residual_rad_s=np.stack(
            [row["target_dq_residual_rad_s"] for row in train]
        ),
        feature_names=feature_names,
        training_group_ids=tuple(sorted({row["group_id"] for row in train})),
        ridge=5.0,
    )
    model = model.with_calibration_support(
        np.vstack([row["feature"] for row in calibration])
    )
    margins = _calibration_margins(calibration, model)
    _apply_models(
        rows,
        model,
        margins["residual_acceleration_rad_s2"],
        margins["residual_force_n"],
        margins["observer_acceleration_rad_s2"],
        margins["observer_force_n"],
    )
    held_metrics = {method: _metrics(held_out, method) for method in ("base", "observer", "residual")}
    per_robot = {
        robot: {method: _metrics([row for row in held_out if row["robot"] == robot], method) for method in ("base", "observer", "residual")}
        for robot in ("cr12", "ur10e")
    }
    per_region = {
        region: {method: _metrics([row for row in held_out if row["region"] == region], method) for method in ("base", "observer", "residual")}
        for region in ("smooth", "near_limit", "contact_adjacent")
    }
    runtime = _runtime(
        held_out,
        clones,
        traces,
        model,
        margins["residual_acceleration_rad_s2"],
        margins["residual_force_n"],
        runtime_repeats,
    )
    residual_metrics = held_metrics["residual"]
    criteria = {
        "human_acceleration": {
            "threshold_deg_s2": [30.0, 60.0],
            "observed_p95_deg_s2": residual_metrics["acceleration_absolute_error_p95_deg_s2"],
            "status": "PASS" if np.all(np.asarray(residual_metrics["acceleration_absolute_error_p95_deg_s2"]) <= np.asarray([30.0, 60.0])) else "FAIL",
        },
        "cuff_force": {
            "rmse_threshold_n": 5.0,
            "p95_threshold_n": 10.0,
            "observed_rmse_n": residual_metrics["cuff_force_vector_rmse_n"],
            "observed_p95_n": residual_metrics["cuff_force_error_p95_n"],
            "status": "PASS" if residual_metrics["cuff_force_vector_rmse_n"] <= 5.0 and residual_metrics["cuff_force_error_p95_n"] <= 10.0 else "FAIL",
        },
        "finite_set_feasibility": {
            "false_acceptance_count": residual_metrics["predicted_accepted_truth_violating_count"],
            "benign_acceptance_coverage": residual_metrics["benign_acceptance_coverage"],
            "status": "PASS" if residual_metrics["predicted_accepted_truth_violating_count"] == 0 and (residual_metrics["benign_acceptance_coverage"] or 0.0) > 0.0 else "FAIL",
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
    all_pass = all(item["status"] == "PASS" for item in criteria.values())
    improves = np.sum(np.asarray(residual_metrics["acceleration_absolute_error_p95_deg_s2"])) < np.sum(np.asarray(held_metrics["base"]["acceleration_absolute_error_p95_deg_s2"]))
    decision = (
        "RL-A — RESIDUAL PREDICTION MEETS ACCURACY + RUNTIME REQUIREMENTS"
        if all_pass
        else (
            "RL-B — RESIDUAL HELPS BUT IS STILL INSUFFICIENT"
            if improves
            else "RL-C — RESIDUAL LEARNING DOES NOT JUSTIFY FURTHER PREDICTOR COMPLEXITY"
        )
    )
    compact_summary_path = (
        STAGE5_ROOT
        / "results"
        / "engineering_validation"
        / "cr12_compact_execution_predictor_v1_attempt_03"
        / "summary.json"
    )
    compact_reference = json.loads(compact_summary_path.read_text(encoding="utf-8"))
    result = {
        "schema": "stage5_short_horizon_state_dependent_residual_v1",
        "evidence_category": "bounded_shadow_engineering_validation",
        "decision": decision,
        "base_predictor": "current_default_interface_aware_preview_frozen",
        "model": model.record(),
        "splits": SPLITS,
        "complete_event_group_split": True,
        "previous_failure_windows_used_as_final_test": False,
        "calibration_margins": margins,
        "held_out": {
            "metrics": held_metrics,
            "per_robot": per_robot,
            "per_region": per_region,
        },
        "historical_regression": {method: _metrics(regression, method) for method in ("base", "observer", "residual")},
        "compact_affine_historical_reference": {
            "comparison_is_not_same_split": True,
            "source": str(compact_summary_path.relative_to(STAGE5_ROOT)),
            "test_metrics": compact_reference["test_metrics"],
            "runtime": compact_reference["runtime"],
        },
        "runtime": runtime,
        "criteria": criteria,
        "timeliness": {
            "contact_adjacent_metrics": per_region["contact_adjacent"],
            "prediction_available_before_candidate_execution": True,
            "uses_future_or_truth_online": False,
            "interpretation": (
                "pre-execution correction meets the registered contact-adjacent accuracy targets"
                if np.all(np.asarray(per_region["contact_adjacent"]["residual"]["acceleration_absolute_error_p95_deg_s2"]) <= np.asarray([30.0, 60.0]))
                else "pre-execution correction does not meet the registered contact-adjacent accuracy targets"
            ),
        },
        "baseline_results": {robot: {"task_status": baselines[robot]["task_status"], "abort_reason": baselines[robot]["abort_reason"]} for robot in ("cr12", "ur10e")},
        "plot": _plot(output_dir, per_region),
        "next_decision_is_control_abstraction_change": decision != "RL-A — RESIDUAL PREDICTION MEETS ACCURACY + RUNTIME REQUIREMENTS",
        "one_next_decision": (
            "evaluate a contact/proximity-aware MPC control abstraction that treats Human-table interaction as an explicit execution mode/support-domain boundary; do not enlarge the residual learner"
            if decision != "RL-A — RESIDUAL PREDICTION MEETS ACCURACY + RUNTIME REQUIREMENTS"
            else "controlled closed-loop shadow-to-active validation, without automatic activation"
        ),
        "scope_invariants": {
            "shadow_only": True,
            "activated_in_mpc": False,
            "abort_authority_changed": False,
            "mujoco_truth_used_online": False,
            "task_changed": False,
            "human_model_changed": False,
            "contact_model_changed": False,
            "thresholds_changed": False,
            "value_or_long_horizon_rl_changed": False,
            "stage3_or_stage4_changed": False,
        },
        "evaluated_cases": rows,
    }
    (output_dir / "residual_model_v1.json").write_text(
        json.dumps(_jsonable(model.record()), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "residual_validation.json").write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(STAGE5_ROOT / "results" / "engineering_validation" / "short_horizon_residual_v1_attempt_01"),
    )
    parser.add_argument("--runtime-repeats", type=int, default=5)
    args = parser.parse_args()
    result = run(args.output_dir, runtime_repeats=args.runtime_repeats)
    compact = {
        "decision": result["decision"],
        "calibration_margins": result["calibration_margins"],
        "held_out": result["held_out"],
        "runtime": result["runtime"],
        "criteria": result["criteria"],
        "timeliness": result["timeliness"],
        "one_next_decision": result["one_next_decision"],
    }
    print(json.dumps(_jsonable(compact), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
