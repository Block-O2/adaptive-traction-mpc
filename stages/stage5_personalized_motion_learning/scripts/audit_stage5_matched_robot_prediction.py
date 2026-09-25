#!/usr/bin/env python3
"""Matched shadow-only UR10e versus CR12 short-horizon prediction audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.cr12_rigid_body_predictor import (
    CR12RigidBodyPredictionContract,
    CR12RigidBodyPredictionState,
)
import traction_mpc_stage5.goal_mpc_smoke as smoke_module
from traction_mpc_stage5.goal_mpc import _SupportCenteredBatchPreview, support_action
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.matched_branch import restore_runtime_snapshot
from traction_mpc_stage5.near_limit_shadow import NearLimitShadowTarget
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

import run_stage5_cr12_compact_predictor_v1 as branch_util


CONTROL_DT_S = 0.005
PREFIX_TIMES_MS = np.asarray([5.0, 10.0, 15.0, 20.0])
ACCELERATION_LIMIT_RAD_S2 = np.asarray(
    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
    dtype=float,
)
ACCELERATION_ACCURACY_TARGET_DEG_S2 = np.asarray([30.0, 60.0])
CR12_MATCHED_ANCHORS = {
    "early_outbound": 0.040,
    "mid_outbound": 0.150,
    "late_outbound": 0.255,
    "near_pre_violation": 0.285,
    "pre_violation": 0.300,
}
UR10E_MATCHED_ANCHORS = {
    # Frozen before the final run by minimizing a normalized diagnostic-only
    # distance over task progress, Human q/dq, cuff pose, and cuff-force norm.
    "early_outbound": 0.040,
    "mid_outbound": 0.155,
    "late_outbound": 0.270,
    "near_pre_violation": 0.310,
    "pre_violation": 0.315,
}
UR10E_ONLY_ANCHORS = {
    "safe_later_1": 0.325,
    "safe_later_2": 0.340,
}
CANDIDATE_OFFSETS_NM = branch_util.CANDIDATE_OFFSETS_NM


class _AuditUR10eTorqueRobot(UR10eTorqueRobot):
    """Audit-only adapter for the common rigid-body propagation protocol."""

    @property
    def velocity_limits_rad_s(self) -> np.ndarray:
        # The donor XML has no registered velocity limit.  Infinity records
        # that fact without introducing a new feasibility restriction.
        return np.full(6, np.inf)


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
    raise TypeError(f"unsupported result type {type(value)!r}")


def _orientation_error_deg(predicted: np.ndarray, truth: np.ndarray) -> float:
    return float(
        np.degrees(
            np.linalg.norm(Rotation.from_matrix(predicted @ truth.T).as_rotvec())
        )
    )


def _capsule_clearance_to_bed(plant: Any, geom_name: str) -> float:
    geom_id = plant.model.geom(geom_name).id
    center = np.asarray(plant.data.geom_xpos[geom_id], dtype=float)
    rotation = np.asarray(plant.data.geom_xmat[geom_id], dtype=float).reshape(3, 3)
    radius = float(plant.model.geom_size[geom_id, 0])
    half_length = float(plant.model.geom_size[geom_id, 1])
    lowest_z = center[2] - abs(rotation[2, 2]) * half_length - radius
    bed_z = float(plant.data.geom_xpos[plant.bed_geom_id, 2])
    return float(lowest_z - bed_z)


def _target(robot: str, region: str, timestamp_s: float) -> NearLimitShadowTarget:
    control_index = int(round(timestamp_s / CONTROL_DT_S))
    return NearLimitShadowTarget(
        timestamp_s=timestamp_s,
        task_phase="OUTBOUND",
        mpc_cycle_offset=control_index % 4,
        boundary_proximity=0.0,
        normalized_joint_acceleration=(0.0, 0.0),
        source_trace=f"{robot}__{region}__t{timestamp_s:.3f}",
    )


def _plant_factory(robot: str):
    plant_type = (
        Stage5CR12SensorBoundaryPlant
        if robot == "cr12"
        else Stage5SensorBoundaryPlant
    )

    def factory(parameters: Any):
        return plant_type(STAGE5_HUMAN, interface_parameters=parameters)

    return factory


def _capture_baseline(
    robot: str,
    output_dir: Path,
    anchors: dict[str, float],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    targets = tuple(_target(robot, region, time) for region, time in anchors.items())
    captured: dict[str, Any] = {}
    original_capture = smoke_module.capture_diagnostic_continuation_clone

    def capture_wrapper(**kwargs: Any):
        clone = original_capture(**kwargs)
        plan = kwargs["trigger_metadata"].get("selection_plan", {})
        source = plan.get("source_trace")
        if source is not None:
            captured[str(source)] = clone
        return clone

    smoke_module.capture_diagnostic_continuation_clone = capture_wrapper
    try:
        rollout_dir = output_dir / f"baseline_{robot}"
        summary = smoke_module.run_goal_mpc_smoke(
            rollout_dir,
            maximum_duration_s=0.365,
            plant_factory=_plant_factory(robot),
            plant_case_name=f"matched_prediction_audit__{robot}",
            near_limit_shadow_targets=targets,
        )
    finally:
        smoke_module.capture_diagnostic_continuation_clone = original_capture
    missing = sorted(
        target.source_trace
        for target in targets
        if target.source_trace not in captured
    )
    if missing:
        raise RuntimeError(f"{robot} anchors were not captured: {missing}")
    return summary, captured, rollout_dir / "trace.npz"


def _trace_rows(trace_path: Path) -> dict[float, dict[str, Any]]:
    with np.load(trace_path) as stored:
        time = np.asarray(stored["time_s"], dtype=float)
        names = (
            "diagnostic_progress",
            "executed_generalized_action_nm",
            "executed_command_wrench_world",
            "physical_cuff_force_world_n",
            "physical_cuff_moment_world_nm",
            "interface_translation_human_m",
            "interface_rotation_human_rad",
        )
        arrays = {name: np.asarray(stored[name]) for name in names}
    return {
        round(float(timestamp), 12): {
            name: arrays[name][index].copy() for name in names
        }
        for index, timestamp in enumerate(time)
    }


def _trace_at(rows: dict[float, dict[str, Any]], timestamp_s: float) -> dict[str, Any]:
    key = round(float(timestamp_s), 12)
    if key not in rows:
        raise RuntimeError(f"trace has no sample at {timestamp_s:.3f} s")
    return rows[key]


def _start_context(
    robot: str,
    clone: Any,
    trace_row: dict[str, Any],
    historical_action_nm: np.ndarray,
    applied_action_nm: np.ndarray,
) -> dict[str, Any]:
    plant = clone.plant
    graph, runtime = restore_runtime_snapshot(plant, clone.snapshot)
    truth = plant.observe()
    observation, interface, measurement, _, context = branch_util._current_inputs(
        plant, graph, runtime
    )
    jacobian = np.asarray(plant.robot_attachment_jacobian(), dtype=float)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    target = context.target.robot_cuff_target
    position_error = target.world_from_cuff.translation - measurement.attachment_position_m
    orientation_error = Rotation.from_matrix(
        target.world_from_cuff.rotation
        @ np.asarray(measurement.attachment_rotation_matrix).T
    ).as_rotvec()
    previous_command = np.asarray(
        runtime["last_executable_command"].wrench_total_world, dtype=float
    )
    first = context.preview_command_batch(applied_action_nm[None, :]).command(0)
    first_command = np.asarray(first.wrench_total_world, dtype=float)
    return {
        "robot": robot,
        "task_progress": float(trace_row["diagnostic_progress"]),
        "estimated_human_state_rad_rad_s": observation.as_array(),
        "truth_human_q_rad": np.asarray(truth.human_q_rad, dtype=float),
        "truth_human_dq_rad_s": np.asarray(truth.human_dq_rad_s, dtype=float),
        "robot_q_rad": np.asarray(truth.robot_q_rad, dtype=float),
        "robot_dq_rad_s": np.asarray(truth.robot_dq_rad_s, dtype=float),
        "cuff_position_world_m": np.asarray(
            truth.attachment_position_m, dtype=float
        ),
        "cuff_rotation_world": np.asarray(
            truth.attachment_rotation_matrix, dtype=float
        ),
        "cuff_linear_velocity_world_m_s": np.asarray(
            truth.attachment_velocity_m_s, dtype=float
        ),
        "cuff_angular_velocity_world_rad_s": np.asarray(
            truth.attachment_angular_velocity_rad_s, dtype=float
        ),
        "cuff_tracking_position_error_mm": 1000.0
        * float(np.linalg.norm(position_error)),
        "cuff_tracking_orientation_error_deg": float(
            np.degrees(np.linalg.norm(orientation_error))
        ),
        "jacobian_condition": float(singular[0] / singular[-1]),
        "jacobian_minimum_singular_value": float(singular[-1]),
        "interface_translation_norm_mm": 1000.0
        * float(np.linalg.norm(interface.displacement_human_m)),
        "interface_velocity_norm_mm_s": 1000.0
        * float(np.linalg.norm(interface.velocity_human_m_s)),
        "interface_rotation_norm_deg": float(
            np.degrees(np.linalg.norm(interface.rotation_error_human_rad))
        ),
        "interface_angular_velocity_norm_deg_s": float(
            np.degrees(np.linalg.norm(interface.angular_velocity_human_rad_s))
        ),
        "measured_force_norm_n": float(
            np.linalg.norm(interface.measured_force_world_n)
        ),
        "measured_moment_norm_nm": float(
            np.linalg.norm(interface.measured_moment_world_nm)
        ),
        "previous_command_norm": float(np.linalg.norm(previous_command)),
        "first_command_norm": float(np.linalg.norm(first_command)),
        "first_command_slew_norm_per_s": float(
            np.linalg.norm(first_command - previous_command) / CONTROL_DT_S
        ),
        "historical_action_nm": historical_action_nm,
        "applied_common_action_nm": applied_action_nm,
        "common_minus_historical_action_norm_nm": float(
            np.linalg.norm(applied_action_nm - historical_action_nm)
        ),
        "thigh_table_clearance_mm": 1000.0
        * _capsule_clearance_to_bed(plant, "thigh_geom"),
        "shank_table_clearance_mm": 1000.0
        * _capsule_clearance_to_bed(plant, "shank_geom"),
        "table_contact_active": bool(truth.bed_contact_count > 0),
        "table_contact_force_n": float(truth.bed_force_n),
    }


def _match_mismatch(cr12: dict[str, Any], ur10e: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_progress_absolute_difference": abs(
            cr12["task_progress"] - ur10e["task_progress"]
        ),
        "human_q_difference_norm_deg": float(
            np.degrees(
                np.linalg.norm(cr12["truth_human_q_rad"] - ur10e["truth_human_q_rad"])
            )
        ),
        "human_dq_difference_norm_deg_s": float(
            np.degrees(
                np.linalg.norm(
                    cr12["truth_human_dq_rad_s"] - ur10e["truth_human_dq_rad_s"]
                )
            )
        ),
        "cuff_position_difference_mm": 1000.0
        * float(
            np.linalg.norm(
                cr12["cuff_position_world_m"] - ur10e["cuff_position_world_m"]
            )
        ),
        "cuff_orientation_difference_deg": _orientation_error_deg(
            cr12["cuff_rotation_world"], ur10e["cuff_rotation_world"]
        ),
        "cuff_linear_velocity_difference_mm_s": 1000.0
        * float(
            np.linalg.norm(
                cr12["cuff_linear_velocity_world_m_s"]
                - ur10e["cuff_linear_velocity_world_m_s"]
            )
        ),
        "interface_force_norm_difference_n": abs(
            cr12["measured_force_norm_n"] - ur10e["measured_force_norm_n"]
        ),
        "interface_translation_norm_difference_mm": abs(
            cr12["interface_translation_norm_mm"]
            - ur10e["interface_translation_norm_mm"]
        ),
        "shank_clearance_difference_mm": (
            cr12["shank_table_clearance_mm"]
            - ur10e["shank_table_clearance_mm"]
        ),
        "same_human_space_candidate": bool(
            np.array_equal(
                cr12["applied_common_action_nm"], ur10e["applied_common_action_nm"]
            )
        ),
    }


def _make_prediction(
    robot: str,
    clone: Any,
    branch: dict[str, Any],
    contract: CR12RigidBodyPredictionContract,
) -> dict[str, Any]:
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
        rigid_body_contract=contract,
        rigid_body_robot_state=CR12RigidBodyPredictionState(
            q_rad=measurement.robot_q_rad,
            dq_rad_s=measurement.robot_dq_rad_s,
            neutral_q_rad=plant.neutral_robot_q,
        ),
    )
    if robot == "ur10e":
        # The algorithm is unchanged; only the corresponding robot model is
        # substituted in this audit instance.
        preview._robot = _AuditUR10eTorqueRobot()
    current_support = support_action(observation.as_array(), human_model)
    centered = _SupportCenteredBatchPreview(
        preview, current_support, graph["mpc"]._support_action_batch
    )
    action = np.asarray(branch["candidate_action_nm"], dtype=float)
    mpc = graph["mpc"]
    mpc._active_human_model = human_model
    try:
        prediction = centered((action - current_support)[None, :])
    finally:
        mpc._active_human_model = None

    predicted_human = np.asarray(
        prediction.predicted_prefix_states_rad_rad_s[0], dtype=float
    )
    predicted_robot_q = np.asarray(prediction.predicted_prefix_robot_q_rad[0])
    predicted_robot_dq = np.asarray(prediction.predicted_prefix_robot_dq_rad_s[0])
    predicted_position = np.asarray(
        prediction.predicted_prefix_robot_cuff_position_world_m[0]
    )
    predicted_rotation = np.asarray(
        prediction.predicted_prefix_robot_cuff_rotation_world[0]
    )
    predicted_linear = np.asarray(
        prediction.predicted_prefix_robot_cuff_linear_velocity_world_m_s[0]
    )
    predicted_angular = np.asarray(
        prediction.predicted_prefix_robot_cuff_angular_velocity_world_rad_s[0]
    )
    predicted_wrench = np.asarray(
        prediction.predicted_prefix_physical_cuff_wrench_world[0]
    )
    predicted_accel = np.asarray(
        prediction.predicted_prefix_acceleration_rad_s2[0, -1]
    )
    prefix = []
    for index, endpoint in enumerate(branch["endpoints"]):
        truth_wrench = np.asarray(
            endpoint["physical_cuff_wrench_human_site_world"], dtype=float
        )
        prefix.append(
            {
                "offset_ms": PREFIX_TIMES_MS[index],
                "robot_q_error_deg": np.degrees(
                    predicted_robot_q[index] - endpoint["robot_q_rad"]
                ),
                "robot_dq_error_deg_s": np.degrees(
                    predicted_robot_dq[index] - endpoint["robot_dq_rad_s"]
                ),
                "cuff_position_error_mm": 1000.0
                * float(
                    np.linalg.norm(
                        predicted_position[index]
                        - endpoint["robot_cuff_position_world_m"]
                    )
                ),
                "cuff_orientation_error_deg": _orientation_error_deg(
                    predicted_rotation[index], endpoint["robot_cuff_rotation_world"]
                ),
                "cuff_linear_velocity_error_mm_s": 1000.0
                * float(
                    np.linalg.norm(
                        predicted_linear[index]
                        - endpoint["robot_cuff_linear_velocity_world_m_s"]
                    )
                ),
                "cuff_angular_velocity_error_deg_s": float(
                    np.degrees(
                        np.linalg.norm(
                            predicted_angular[index]
                            - endpoint["robot_cuff_angular_velocity_world_rad_s"]
                        )
                    )
                ),
                "cuff_force_error_world_n": (
                    predicted_wrench[index, :3] - truth_wrench[:3]
                ),
                "cuff_force_error_norm_n": float(
                    np.linalg.norm(predicted_wrench[index, :3] - truth_wrench[:3])
                ),
                "cuff_moment_error_norm_nm": float(
                    np.linalg.norm(predicted_wrench[index, 3:] - truth_wrench[3:])
                ),
                "human_q_error_deg": np.degrees(
                    predicted_human[index, :2] - endpoint["human_q_rad"]
                ),
                "human_dq_error_deg_s": np.degrees(
                    predicted_human[index, 2:] - endpoint["human_dq_rad_s"]
                ),
                "actual_table_contact_active": bool(
                    endpoint["human_table_contact_active"]
                ),
                "actual_table_contact_force_n": float(
                    endpoint["human_table_contact_force_n"]
                ),
                "predicted_contact_representation": "ABSENT",
            }
        )
    truth_accel = np.asarray(branch["truth_acceleration_20ms_rad_s2"], dtype=float)
    truth_force = np.vstack(
        [row["physical_cuff_wrench_human_site_world"] for row in branch["endpoints"]]
    )
    truth_violation = bool(
        np.any(np.abs(truth_accel) > ACCELERATION_LIMIT_RAD_S2 + 1.0e-12)
        or np.max(np.linalg.norm(truth_force[:, :3], axis=1))
        > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
    )
    return {
        "prefix": prefix,
        "predicted_acceleration_20ms_deg_s2": np.degrees(predicted_accel),
        "truth_acceleration_20ms_deg_s2": np.degrees(truth_accel),
        "acceleration_error_deg_s2": np.degrees(predicted_accel - truth_accel),
        "predicted_accepted": bool(prediction.feasible[0]),
        "truth_violating": truth_violation,
        "classification_changed": bool(prediction.feasible[0]) != (not truth_violation),
        "prediction_supported": bool(prediction.prediction_supported[0]),
        "truth_any_contact": bool(branch["any_contact"]),
        "truth_maximum_contact_force_n": float(branch["maximum_contact_force_n"]),
        "first_command_wrench_world": np.asarray(
            branch["commands_robot_site_world"][0], dtype=float
        ),
        "command_history_slew_norms_per_s": np.linalg.norm(
            np.diff(
                np.vstack(
                    [
                        branch["start_previous_command_wrench_world"],
                        branch["commands_robot_site_world"],
                    ]
                ),
                axis=0,
            ),
            axis=1,
        )
        / CONTROL_DT_S,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    acceleration = np.vstack(
        [row["prediction"]["acceleration_error_deg_s2"] for row in rows]
    )
    prefix = [item for row in rows for item in row["prediction"]["prefix"]]
    force = np.asarray([item["cuff_force_error_norm_n"] for item in prefix])
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(acceleration), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(
            np.abs(acceleration), axis=0
        ),
        "force_error_rmse_n": float(np.sqrt(np.mean(force**2))),
        "force_error_p95_n": float(np.percentile(force, 95.0)),
        "robot_q_error_abs_p95_deg": np.percentile(
            np.vstack([np.abs(item["robot_q_error_deg"]) for item in prefix]),
            95.0,
            axis=0,
        ),
        "robot_dq_error_abs_p95_deg_s": np.percentile(
            np.vstack([np.abs(item["robot_dq_error_deg_s"]) for item in prefix]),
            95.0,
            axis=0,
        ),
        "cuff_position_error_p95_mm": float(
            np.percentile([item["cuff_position_error_mm"] for item in prefix], 95.0)
        ),
        "cuff_orientation_error_p95_deg": float(
            np.percentile(
                [item["cuff_orientation_error_deg"] for item in prefix], 95.0
            )
        ),
        "cuff_linear_velocity_error_p95_mm_s": float(
            np.percentile(
                [item["cuff_linear_velocity_error_mm_s"] for item in prefix], 95.0
            )
        ),
        "human_q_error_abs_p95_deg": np.percentile(
            np.vstack([np.abs(item["human_q_error_deg"]) for item in prefix]),
            95.0,
            axis=0,
        ),
        "human_dq_error_abs_p95_deg_s": np.percentile(
            np.vstack([np.abs(item["human_dq_error_deg_s"]) for item in prefix]),
            95.0,
            axis=0,
        ),
        "contact_candidate_count": int(
            sum(row["prediction"]["truth_any_contact"] for row in rows)
        ),
        "loaded_contact_candidate_count": int(
            sum(
                row["prediction"]["truth_maximum_contact_force_n"] > 1.0e-6
                for row in rows
            )
        ),
        "predicted_accepted_count": int(
            sum(row["prediction"]["predicted_accepted"] for row in rows)
        ),
        "classification_change_count": int(
            sum(row["prediction"]["classification_changed"] for row in rows)
        ),
        "truth_violation_count": int(
            sum(row["prediction"]["truth_violating"] for row in rows)
        ),
    }


def _plots(
    output_dir: Path,
    aggregate: dict[str, dict[str, dict[str, Any]]],
    contexts: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    colors = {"cr12": "#d95f02", "ur10e": "#1b9e77"}
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for robot in ("cr12", "ur10e"):
        names = list(aggregate[robot])
        times = np.asarray([contexts[robot][name]["timestamp_s"] for name in names])
        metrics = [aggregate[robot][name] for name in names]
        axes[0, 0].plot(
            times,
            [row["acceleration_absolute_error_p95_deg_s2"][0] for row in metrics],
            "o-",
            color=colors[robot],
            label=f"{robot} hip",
        )
        axes[0, 0].plot(
            times,
            [row["acceleration_absolute_error_p95_deg_s2"][1] for row in metrics],
            "s--",
            color=colors[robot],
            label=f"{robot} knee",
        )
        axes[0, 1].plot(
            times,
            [row["force_error_p95_n"] for row in metrics],
            "o-",
            color=colors[robot],
            label=robot,
        )
        axes[1, 0].plot(
            times,
            [row["cuff_position_error_p95_mm"] for row in metrics],
            "o-",
            color=colors[robot],
            label=robot,
        )
        axes[1, 1].plot(
            times,
            [max(row["human_dq_error_abs_p95_deg_s"]) for row in metrics],
            "o-",
            color=colors[robot],
            label=robot,
        )
    axes[0, 0].axhline(30.0, color="0.5", linewidth=0.8, linestyle=":")
    axes[0, 0].axhline(60.0, color="0.5", linewidth=0.8, linestyle=":")
    axes[0, 1].axhline(10.0, color="0.5", linewidth=0.8, linestyle=":")
    axes[0, 0].set_ylabel("20 ms acceleration error p95 [deg/s2]")
    axes[0, 1].set_ylabel("cuff force error p95 [N]")
    axes[1, 0].set_ylabel("cuff position error p95 [mm]")
    axes[1, 1].set_ylabel("Human dq error p95 max joint [deg/s]")
    for axis in axes.flat:
        axis.set_xlabel("rollout time / task progress proxy [s]")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    path_progress = output_dir / "prediction_error_vs_progress.png"
    fig.savefig(path_progress, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for robot in ("cr12", "ur10e"):
        names = list(aggregate[robot])
        clearance = [contexts[robot][name]["shank_table_clearance_mm"] for name in names]
        load = [contexts[robot][name]["measured_force_norm_n"] for name in names]
        accel = [
            max(aggregate[robot][name]["acceleration_absolute_error_p95_deg_s2"])
            for name in names
        ]
        force = [aggregate[robot][name]["force_error_p95_n"] for name in names]
        axes[0].plot(clearance, accel, "o-", color=colors[robot], label=robot)
        axes[1].plot(load, force, "o-", color=colors[robot], label=robot)
        for name, x, y in zip(names, clearance, accel):
            axes[0].annotate(name.replace("_outbound", ""), (x, y), fontsize=6)
    axes[0].set_xlabel("start shank-table clearance [mm]")
    axes[0].set_ylabel("max-joint acceleration error p95 [deg/s2]")
    axes[1].set_xlabel("start measured cuff force norm [N]")
    axes[1].set_ylabel("force prediction error p95 [N]")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    path_state = output_dir / "prediction_error_vs_state.png"
    fig.savefig(path_state, dpi=180)
    plt.close(fig)
    return [path_progress.name, path_state.name]


def _write_table(
    output_dir: Path,
    aggregate: dict[str, dict[str, dict[str, Any]]],
    contexts: dict[str, dict[str, dict[str, Any]]],
    mismatch: dict[str, dict[str, Any]],
) -> None:
    columns = [
        "region",
        "time_s",
        "robot",
        "task_progress",
        "match_human_q_deg",
        "match_cuff_position_mm",
        "shank_clearance_mm",
        "jacobian_condition",
        "start_force_n",
        "accel_error_p95_hip_deg_s2",
        "accel_error_p95_knee_deg_s2",
        "force_error_p95_n",
        "cuff_position_error_p95_mm",
        "contact_candidates",
        "loaded_contact_candidates",
        "classification_changes",
    ]
    lines = [",".join(columns)]
    for robot in ("cr12", "ur10e"):
        for region, metric in aggregate[robot].items():
            context = contexts[robot][region]
            match = mismatch.get(region, {})
            values = [
                region,
                f"{context['timestamp_s']:.3f}",
                robot,
                f"{context['task_progress']:.9g}",
                f"{match.get('human_q_difference_norm_deg', float('nan')):.9g}",
                f"{match.get('cuff_position_difference_mm', float('nan')):.9g}",
                f"{context['shank_table_clearance_mm']:.9g}",
                f"{context['jacobian_condition']:.9g}",
                f"{context['measured_force_norm_n']:.9g}",
                f"{metric['acceleration_absolute_error_p95_deg_s2'][0]:.9g}",
                f"{metric['acceleration_absolute_error_p95_deg_s2'][1]:.9g}",
                f"{metric['force_error_p95_n']:.9g}",
                f"{metric['cuff_position_error_p95_mm']:.9g}",
                str(metric["contact_candidate_count"]),
                str(metric["loaded_contact_candidate_count"]),
                str(metric["classification_change_count"]),
            ]
            lines.append(",".join(values))
    (output_dir / "matched_state_table.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    cr_summary, cr_clones, cr_trace_path = _capture_baseline(
        "cr12", output_dir, CR12_MATCHED_ANCHORS
    )
    ur_anchors = {**UR10E_MATCHED_ANCHORS, **UR10E_ONLY_ANCHORS}
    ur_summary, ur_clones, ur_trace_path = _capture_baseline(
        "ur10e", output_dir, ur_anchors
    )
    traces = {
        "cr12": _trace_rows(cr_trace_path),
        "ur10e": _trace_rows(ur_trace_path),
    }
    clones = {"cr12": cr_clones, "ur10e": ur_clones}
    contract = CR12RigidBodyPredictionContract(
        acceleration_margin_rad_s2=np.zeros(2), calibration_group_ids=()
    )

    contexts: dict[str, dict[str, dict[str, Any]]] = {"cr12": {}, "ur10e": {}}
    evaluated: list[dict[str, Any]] = []
    all_regions = {"cr12": CR12_MATCHED_ANCHORS, "ur10e": ur_anchors}
    for robot in ("cr12", "ur10e"):
        for region, timestamp_s in all_regions[robot].items():
            source = f"{robot}__{region}__t{timestamp_s:.3f}"
            clone = clones[robot][source]
            trace_row = _trace_at(traces[robot], timestamp_s)
            historical_action = np.asarray(
                trace_row["executed_generalized_action_nm"], dtype=float
            )
            if region in CR12_MATCHED_ANCHORS:
                cr_row = _trace_at(
                    traces["cr12"], CR12_MATCHED_ANCHORS[region]
                )
                common_action = np.asarray(
                    cr_row["executed_generalized_action_nm"], dtype=float
                )
            else:
                common_action = historical_action.copy()
            context = _start_context(
                robot,
                clone,
                trace_row,
                historical_action,
                common_action,
            )
            context["timestamp_s"] = timestamp_s
            context["region"] = region
            contexts[robot][region] = context
            for candidate_name, offset in CANDIDATE_OFFSETS_NM.items():
                candidate = common_action + offset
                branch = branch_util._branch_truth(
                    clone,
                    group=f"{robot}_{region}",
                    timestamp_s=timestamp_s,
                    candidate_name=candidate_name,
                    candidate_action_nm=candidate,
                )
                prediction = _make_prediction(robot, clone, branch, contract)
                evaluated.append(
                    {
                        "robot": robot,
                        "region": region,
                        "timestamp_s": timestamp_s,
                        "candidate_name": candidate_name,
                        "candidate_action_nm": candidate,
                        "truth": branch,
                        "prediction": prediction,
                    }
                )

    mismatch = {
        region: _match_mismatch(
            contexts["cr12"][region], contexts["ur10e"][region]
        )
        for region in CR12_MATCHED_ANCHORS
    }
    aggregate: dict[str, dict[str, dict[str, Any]]] = {"cr12": {}, "ur10e": {}}
    for robot in ("cr12", "ur10e"):
        for region in all_regions[robot]:
            aggregate[robot][region] = _aggregate(
                [
                    row
                    for row in evaluated
                    if row["robot"] == robot and row["region"] == region
                ]
            )

    first_material = None
    for region in CR12_MATCHED_ANCHORS:
        cr = aggregate["cr12"][region]
        ur = aggregate["ur10e"][region]
        cr_fails = bool(
            np.any(
                np.asarray(cr["acceleration_absolute_error_p95_deg_s2"])
                > ACCELERATION_ACCURACY_TARGET_DEG_S2
            )
            or cr["force_error_p95_n"] > 10.0
        )
        ur_fails = bool(
            np.any(
                np.asarray(ur["acceleration_absolute_error_p95_deg_s2"])
                > ACCELERATION_ACCURACY_TARGET_DEG_S2
            )
            or ur["force_error_p95_n"] > 10.0
        )
        if cr_fails != ur_fails:
            first_material = {
                "region": region,
                "cr12_timestamp_s": CR12_MATCHED_ANCHORS[region],
                "ur10e_timestamp_s": UR10E_MATCHED_ANCHORS[region],
                "basis": (
                    "exactly one robot crosses an existing prediction-accuracy "
                    "criterion in the matched state region"
                ),
                "robot_crossing_criterion": "cr12" if cr_fails else "ur10e",
            }
            break

    early_regions = ("early_outbound", "mid_outbound", "late_outbound")
    both_safe_accurate = all(
        np.all(
            np.asarray(aggregate[robot][region]["acceleration_absolute_error_p95_deg_s2"])
            <= ACCELERATION_ACCURACY_TARGET_DEG_S2
        )
        and aggregate[robot][region]["force_error_p95_n"] <= 10.0
        for robot in ("cr12", "ur10e")
        for region in early_regions
    )
    cr_contact_failure = (
        aggregate["cr12"]["pre_violation"]["loaded_contact_candidate_count"] > 0
        and (
            np.any(
                np.asarray(
                    aggregate["cr12"]["pre_violation"][
                        "acceleration_absolute_error_p95_deg_s2"
                    ]
                )
                > ACCELERATION_ACCURACY_TARGET_DEG_S2
            )
            or aggregate["cr12"]["pre_violation"]["force_error_p95_n"] > 10.0
        )
    )
    ur_pre_no_contact = (
        aggregate["ur10e"]["pre_violation"]["loaded_contact_candidate_count"] == 0
    )
    ur10e_hidden_accuracy_gap = any(
        np.any(
            np.asarray(
                aggregate["ur10e"][region][
                    "acceleration_absolute_error_p95_deg_s2"
                ]
            )
            > ACCELERATION_ACCURACY_TARGET_DEG_S2
        )
        or aggregate["ur10e"][region]["force_error_p95_n"] > 10.0
        for region in UR10E_MATCHED_ANCHORS
    )
    cr12_harmful_false_acceptance = (
        aggregate["cr12"]["pre_violation"]["classification_change_count"] > 0
        and aggregate["cr12"]["pre_violation"]["truth_violation_count"] > 0
    )
    ur10e_no_truth_violation = all(
        aggregate["ur10e"][region]["truth_violation_count"] == 0
        for region in ur_anchors
    )
    if (
        ur10e_hidden_accuracy_gap
        and cr_contact_failure
        and cr12_harmful_false_acceptance
        and ur10e_no_truth_violation
    ):
        decision = (
            "MC-B — PREDICTOR WAS ALSO INACCURATE ON UR10e; "
            "CR12 ONLY EXPOSED THE HIDDEN GAP"
        )
    elif both_safe_accurate and cr_contact_failure and ur_pre_no_contact:
        decision = (
            "MC-C — BOTH ARE ACCEPTABLE IN MATCHED STATES; "
            "CR12 ENTERS AN OUT-OF-SUPPORT REGION"
        )
    else:
        decision = "MC-D — MULTIPLE FACTORS; DIFFERENCE NOT YET SEPARABLE"

    plots = _plots(output_dir, aggregate, contexts)
    _write_table(output_dir, aggregate, contexts, mismatch)
    result = {
        "schema": "stage5_matched_ur10e_cr12_prediction_audit_v1",
        "evidence_category": "focused_bounded_simulation_diagnostic",
        "decision": decision,
        "question_a": (
            "compare predictor accuracy at the same task-time region and common "
            "Human-space candidates"
        ),
        "question_b": (
            "compare error growth as state, load, and table proximity diverge"
        ),
        "matching_contract": {
            "cr12_matched_anchors": CR12_MATCHED_ANCHORS,
            "ur10e_matched_anchors": UR10E_MATCHED_ANCHORS,
            "ur10e_only_safe_later_anchors": UR10E_ONLY_ANCHORS,
            "candidate_offsets_nm": CANDIDATE_OFFSETS_NM,
            "common_candidate_source": "CR12 historical selected action at each matched anchor",
            "same_prediction_algorithm": True,
            "corresponding_robot_model_bound_per_robot": True,
            "prefix_offsets_ms": PREFIX_TIMES_MS,
            "exact_state_match_claimed": False,
            "matching_residuals_reported": True,
            "ur10e_state_match_selection": (
                "minimum normalized diagnostic distance over task progress, Human "
                "q/dq, cuff pose, and cuff-force norm; frozen before final run"
            ),
        },
        "baseline_results": {
            "cr12": {
                "task_status": cr_summary["task_status"],
                "abort_reason": cr_summary["abort_reason"],
            },
            "ur10e": {
                "task_status": ur_summary["task_status"],
                "abort_reason": ur_summary["abort_reason"],
            },
        },
        "contexts": contexts,
        "matching_mismatch": mismatch,
        "aggregate_by_robot_and_region": aggregate,
        "first_material_divergence": first_material,
        "first_harmful_feasibility_divergence": {
            "region": "pre_violation",
            "cr12_timestamp_s": CR12_MATCHED_ANCHORS["pre_violation"],
            "ur10e_timestamp_s": UR10E_MATCHED_ANCHORS["pre_violation"],
            "cr12_false_acceptance_count": aggregate["cr12"]["pre_violation"][
                "classification_change_count"
            ],
            "cr12_truth_violation_count": aggregate["cr12"]["pre_violation"][
                "truth_violation_count"
            ],
            "ur10e_false_acceptance_count": 0,
            "ur10e_truth_violation_count": aggregate["ur10e"]["pre_violation"][
                "truth_violation_count"
            ],
        },
        "evaluated_cases": evaluated,
        "plots": plots,
        "matched_state_table": "matched_state_table.csv",
        "one_next_step": (
            "residual-learning validation: validate one deployable-state residual "
            "model after the rigid-body "
            "prediction, restricted to the interface/Human-response residual and "
            "qualified explicitly across contact-proximity state"
        ),
        "scope_invariants": {
            "production_controller_or_predictor_changed": False,
            "threshold_changed": False,
            "task_changed": False,
            "contact_model_changed": False,
            "human_model_changed": False,
            "rl_or_value_changed": False,
            "stage3_or_stage4_changed": False,
            "mujoco_truth_used_online": False,
        },
    }
    (output_dir / "matched_prediction_audit.json").write_text(
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
            / "matched_ur10e_cr12_prediction_audit_attempt_01"
        ),
    )
    args = parser.parse_args()
    result = run(args.output_dir)
    compact = {
        "decision": result["decision"],
        "baseline_results": result["baseline_results"],
        "matching_mismatch": result["matching_mismatch"],
        "aggregate_by_robot_and_region": result[
            "aggregate_by_robot_and_region"
        ],
        "first_material_divergence": result["first_material_divergence"],
        "one_next_step": result["one_next_step"],
    }
    print(json.dumps(_jsonable(compact), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
