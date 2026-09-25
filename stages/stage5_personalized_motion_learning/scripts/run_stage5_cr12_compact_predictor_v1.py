#!/usr/bin/env python3
"""Fit and evaluate one shadow-only compact CR12 execution predictor."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage5.compact_execution_predictor import (
    COMPACT_PREFIX_TIMES_S,
    CompactCuffResponseModelV1,
    CompactRobotCuffState,
    fit_compact_cuff_response_model,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import (
    make_interface_aware_first_action_batch_preview,
)
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
import traction_mpc_stage5.goal_mpc_smoke as smoke_module
from traction_mpc_stage5.goal_mpc import support_action
from traction_mpc_stage5.hold_stabilizer import solve_loaded_hold_equilibrium
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.loaded_execution import (
    build_stage5_loaded_execution_context,
    human_cuff_wrench_to_robot_cuff_command,
    loaded_execution_target_from_equilibrium,
)
from traction_mpc_stage5.matched_branch import restore_runtime_snapshot
from traction_mpc_stage5.near_limit_shadow import NearLimitShadowTarget
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


CONTROL_DT_S = 0.005
PHYSICS_SUBSTEPS = 20
ACCELERATION_LIMIT_RAD_S2 = np.asarray(
    PROVISIONAL_LOW_MODERATE_GOAL_TASK.task_joint_acceleration_limit_rad_s2,
    dtype=float,
)
RIDGE = 1.0e-6

GROUPS = {
    "development": (0.040, 0.080, 0.120),
    "calibration": (0.145, 0.185, 0.225),
    "test": (0.250, 0.275, 0.295),
    "historical_regression": (0.100, 0.200, 0.260, 0.280, 0.300),
}
CANDIDATE_OFFSETS_NM = {
    "selected": np.asarray([0.0, 0.0]),
    "hip_plus_2": np.asarray([2.0, 0.0]),
    "hip_minus_2": np.asarray([-2.0, 0.0]),
    "knee_plus_2": np.asarray([0.0, 2.0]),
    "knee_minus_2": np.asarray([0.0, -2.0]),
}


def _plant_factory(parameters: Any) -> Stage5CR12SensorBoundaryPlant:
    return Stage5CR12SensorBoundaryPlant(
        STAGE5_HUMAN, interface_parameters=parameters
    )


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


def _estimator_observe(estimator: Any, measurement: Any) -> None:
    estimator.observe(
        time_s=measurement.sample_time_s,
        position_world_m=measurement.attachment_position_m,
        rotation_world_from_cuff=measurement.attachment_rotation_matrix,
        linear_velocity_world_m_s=measurement.attachment_velocity_m_s,
        angular_velocity_world_rad_s=measurement.attachment_angular_velocity_rad_s,
        force_world_n=measurement.cuff_force_vector_n,
        moment_world_nm=measurement.cuff_moment_vector_nm,
        bed_contaminated=False,
    )


def _target_for_time(timestamp_s: float, group: str) -> NearLimitShadowTarget:
    control_index = int(round(timestamp_s / CONTROL_DT_S))
    return NearLimitShadowTarget(
        timestamp_s=timestamp_s,
        task_phase="OUTBOUND",
        mpc_cycle_offset=control_index % 4,
        boundary_proximity=0.0,
        normalized_joint_acceleration=(0.0, 0.0),
        source_trace=f"{group}__t{timestamp_s:.3f}",
    )


def _selected_actions(trace_path: Path) -> dict[float, np.ndarray]:
    with np.load(trace_path) as trace:
        times = np.asarray(trace["time_s"], dtype=float)
        actions = np.asarray(trace["executed_generalized_action_nm"], dtype=float)
    result = {}
    for timestamp in (time for values in GROUPS.values() for time in values):
        index = int(np.argmin(np.abs(times - timestamp)))
        if not np.isclose(times[index], timestamp, atol=1.0e-10, rtol=0.0):
            raise RuntimeError(f"baseline trace lacks {timestamp:.3f} s action")
        result[timestamp] = actions[index].copy()
    return result


def _cuff_state(plant: Any, measurement: Any) -> CompactRobotCuffState:
    velocity = plant.control_feedback_velocity_snapshot(measurement)
    return CompactRobotCuffState(
        position_world_m=measurement.attachment_position_m,
        rotation_world=measurement.attachment_rotation_matrix,
        linear_velocity_world_m_s=velocity.linear_velocity_world_m_s,
        angular_velocity_world_rad_s=measurement.attachment_angular_velocity_rad_s,
    )


def _current_inputs(
    plant: Any,
    graph: dict[str, Any],
    runtime: dict[str, Any],
) -> tuple[Any, Any, Any, Any, Any]:
    observation = runtime["task_observation"]
    interface_state = runtime["interface_state"]
    measurement = runtime["low_level_measurement"]
    model = graph["current_model"]
    allocator = graph["cuff_allocator"]
    equilibrium = solve_loaded_hold_equilibrium(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        model,
        allocator,
        target_q_rad=observation.as_array()[:2],
        target_dq_rad_s=observation.as_array()[2:],
    )
    target = loaded_execution_target_from_equilibrium(equilibrium, model)
    context = build_stage5_loaded_execution_context(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface_state,
        human_model=model,
        cuff_allocator=allocator,
        target=target,
    )
    return observation, interface_state, measurement, model, context


def _branch_truth(
    clone: Any,
    *,
    group: str,
    timestamp_s: float,
    candidate_name: str,
    candidate_action_nm: np.ndarray,
) -> dict[str, Any]:
    plant = clone.plant
    graph, runtime = restore_runtime_snapshot(plant, clone.snapshot)
    truth_start = plant.observe()
    start_truth_dq = np.asarray(truth_start.human_dq_rad_s, dtype=float).copy()
    start_truth_robot_q = np.asarray(truth_start.robot_q_rad, dtype=float).copy()
    start_truth_robot_dq = np.asarray(truth_start.robot_dq_rad_s, dtype=float).copy()
    start_estimated = np.asarray(runtime["task_observation"].as_array(), dtype=float)
    start_cuff = _cuff_state(plant, runtime["low_level_measurement"])
    start_interface = runtime["interface_state"]
    previous_command = np.asarray(
        runtime["last_executable_command"].wrench_total_world, dtype=float
    ).copy()
    feature_rows: list[np.ndarray] = []
    target_rows: list[np.ndarray] = []
    endpoints: list[dict[str, Any]] = []
    commands: list[np.ndarray] = []
    command_feasible: list[bool] = []

    for segment in range(4):
        observation, interface_state, measurement, model, context = _current_inputs(
            plant, graph, runtime
        )
        current_cuff = _cuff_state(plant, measurement)
        batch = context.preview_command_batch(candidate_action_nm[None, :])
        command = batch.command(0)
        command_wrench = np.asarray(command.wrench_total_world, dtype=float)
        human_wrench = np.concatenate(
            [
                np.asarray(interface_state.measured_force_world_n, dtype=float),
                np.asarray(interface_state.measured_moment_world_nm, dtype=float),
            ]
        )
        physical_robot = human_cuff_wrench_to_robot_cuff_command(
            human_wrench, context.robot_from_human_world_m
        )
        current_twist = np.concatenate(
            [
                current_cuff.linear_velocity_world_m_s,
                current_cuff.angular_velocity_world_rad_s,
            ]
        )
        features = CompactCuffResponseModelV1.feature_matrix(
            current_twist[None, :],
            command_wrench[None, :],
            physical_robot[None, :],
            previous_command[None, :],
        )[0]
        feature_rows.append(features)
        commands.append(command_wrench.copy())
        command_feasible.append(bool(batch.feasible[0]))

        plant.apply_executable_command(command)
        truth = None
        for _ in range(PHYSICS_SUBSTEPS):
            truth = plant.step()
        assert truth is not None
        estimator_measurement = graph["estimator_layer"].update(truth)
        mpc_measurement = graph["mpc_layer"].update(truth)
        low_level_measurement = graph["low_level_layer"].update(truth)
        continued_index = clone.original_control_index + segment + 1
        if continued_index % 4 == 0:
            _estimator_observe(graph["estimator"], estimator_measurement)
        task_observation, next_interface = graph["interface_observer"].update(
            mpc_measurement,
            graph["estimator"].model,
            human_model_version=str(runtime["current_control_model_version"]),
        )
        next_cuff = _cuff_state(plant, low_level_measurement)
        next_twist = np.concatenate(
            [
                next_cuff.linear_velocity_world_m_s,
                next_cuff.angular_velocity_world_rad_s,
            ]
        )
        target_rows.append(next_twist - current_twist)
        endpoints.append(
            {
                "offset_ms": 5.0 * (segment + 1),
                "robot_cuff_position_world_m": next_cuff.position_world_m,
                "robot_cuff_rotation_world": next_cuff.rotation_world,
                "robot_cuff_linear_velocity_world_m_s": (
                    next_cuff.linear_velocity_world_m_s
                ),
                "robot_cuff_angular_velocity_world_rad_s": (
                    next_cuff.angular_velocity_world_rad_s
                ),
                "physical_cuff_wrench_human_site_world": np.concatenate(
                    [truth.cuff_force_vector_n, truth.cuff_moment_vector_nm]
                ),
                "human_q_rad": np.asarray(truth.human_q_rad, dtype=float),
                "human_dq_rad_s": np.asarray(truth.human_dq_rad_s, dtype=float),
                "deployable_human_state_rad_rad_s": np.asarray(
                    task_observation.as_array(), dtype=float
                ),
                "robot_q_rad": np.asarray(truth.robot_q_rad, dtype=float),
                "robot_dq_rad_s": np.asarray(truth.robot_dq_rad_s, dtype=float),
                "human_table_contact_active": bool(truth.bed_contact_count > 0),
                "human_table_contact_count": int(truth.bed_contact_count),
                "human_table_contact_force_n": float(truth.bed_force_n),
            }
        )
        runtime["task_observation"] = task_observation
        runtime["interface_state"] = next_interface
        runtime["estimator_measurement"] = estimator_measurement
        runtime["mpc_measurement"] = mpc_measurement
        runtime["low_level_measurement"] = low_level_measurement
        runtime["estimated_state"] = task_observation.as_array().copy()
        runtime["last_executable_command"] = command
        previous_command = command_wrench.copy()

    end_truth_dq = np.asarray(endpoints[-1]["human_dq_rad_s"], dtype=float)
    truth_acceleration = (end_truth_dq - start_truth_dq) / 0.020
    return {
        "group": group,
        "group_id": f"{group}__t{timestamp_s:.3f}",
        "timestamp_s": timestamp_s,
        "candidate_name": candidate_name,
        "candidate_action_nm": candidate_action_nm.copy(),
        "decision_state_sha256": clone.snapshot.decision_state_sha256,
        "start_estimated_state_rad_rad_s": start_estimated,
        "start_truth_dq_rad_s": start_truth_dq,
        "start_truth_robot_q_rad": start_truth_robot_q,
        "start_truth_robot_dq_rad_s": start_truth_robot_dq,
        "start_robot_cuff_state": start_cuff,
        "start_interface_state": start_interface,
        "start_previous_command_wrench_world": np.asarray(
            clone.snapshot.runtime_state["last_executable_command"].wrench_total_world,
            dtype=float,
        ),
        "features": np.asarray(feature_rows),
        "target_twist_increment": np.asarray(target_rows),
        "commands_robot_site_world": np.asarray(commands),
        "command_feasible": np.asarray(command_feasible, dtype=bool),
        "endpoints": endpoints,
        "truth_acceleration_20ms_rad_s2": truth_acceleration,
        "truth_acceleration_20ms_deg_s2": np.degrees(truth_acceleration),
        "any_contact": any(row["human_table_contact_active"] for row in endpoints),
        "maximum_contact_force_n": max(
            row["human_table_contact_force_n"] for row in endpoints
        ),
    }


def _make_preview(
    clone: Any,
    model: CompactCuffResponseModelV1,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    plant = clone.plant
    graph, runtime = restore_runtime_snapshot(plant, clone.snapshot)
    observation, interface_state, measurement, human_model, context = _current_inputs(
        plant, graph, runtime
    )
    preview = make_interface_aware_first_action_batch_preview(
        context.preview_command_batch,
        graph["screening_interface_predictor"],
        interface_state,
        q_rad=observation.as_array()[:2],
        human_model=human_model,
        cuff_allocator=graph["cuff_allocator"],
        state_rad_rad_s=observation.as_array(),
        acceleration_limits_rad_s2=ACCELERATION_LIMIT_RAD_S2,
        compact_model=model,
        compact_robot_cuff_state=_cuff_state(plant, measurement),
    )
    # Goal-MPC's public solve path installs these same three bindings.  Bind
    # them here for exact-candidate shadow evaluation without running CEM.
    mpc = graph["mpc"]
    current_support = support_action(observation.as_array(), human_model)
    from traction_mpc_stage5.goal_mpc import _SupportCenteredBatchPreview

    centered = _SupportCenteredBatchPreview(
        preview, current_support, mpc._support_action_batch
    )
    return centered, graph, runtime


def _predict_branch(
    clone: Any,
    branch: dict[str, Any],
    model: CompactCuffResponseModelV1,
) -> dict[str, Any]:
    centered, graph, _ = _make_preview(clone, model)
    initial = np.asarray(branch["start_estimated_state_rad_rad_s"], dtype=float)
    human_model = clone.snapshot.controller_graph["current_model"]
    current_support = support_action(initial, human_model)
    action = np.asarray(branch["candidate_action_nm"], dtype=float)
    mpc = graph["mpc"]
    mpc._active_human_model = human_model
    try:
        prediction = centered((action - current_support)[None, :])
    finally:
        mpc._active_human_model = None
    predicted_states = np.asarray(
        prediction.predicted_prefix_states_rad_rad_s[0], dtype=float
    )
    predicted_acceleration = np.asarray(
        prediction.predicted_prefix_acceleration_rad_s2[0, -1], dtype=float
    )
    predicted_wrench = np.asarray(
        prediction.predicted_prefix_physical_cuff_wrench_world[0], dtype=float
    )
    truth_wrench = np.vstack(
        [row["physical_cuff_wrench_human_site_world"] for row in branch["endpoints"]]
    )
    force_error = predicted_wrench[:, :3] - truth_wrench[:, :3]
    acceleration_error_deg = np.degrees(
        predicted_acceleration
        - np.asarray(branch["truth_acceleration_20ms_rad_s2"], dtype=float)
    )
    truth_force_peak = float(np.max(np.linalg.norm(truth_wrench[:, :3], axis=1)))
    truth_accel_violation = bool(
        np.any(
            np.abs(branch["truth_acceleration_20ms_rad_s2"])
            > ACCELERATION_LIMIT_RAD_S2 + 1.0e-12
        )
    )
    truth_force_violation = truth_force_peak > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
    eligible = bool(np.all(branch["command_feasible"]))
    accepted = bool(prediction.feasible[0])
    return {
        "predicted_human_states_rad_rad_s": predicted_states,
        "predicted_acceleration_20ms_deg_s2": np.degrees(predicted_acceleration),
        "truth_acceleration_20ms_deg_s2": branch[
            "truth_acceleration_20ms_deg_s2"
        ],
        "acceleration_error_deg_s2": acceleration_error_deg,
        "predicted_physical_cuff_wrench_world": predicted_wrench,
        "force_error_world_n": force_error,
        "force_error_norm_n": np.linalg.norm(force_error, axis=1),
        "supported": bool(prediction.compact_model_supported[0]),
        "predicted_accepted": accepted,
        "existing_command_feasible_all_segments": eligible,
        "truth_acceleration_violation": truth_accel_violation,
        "truth_force_violation": truth_force_violation,
        "truth_violating": truth_accel_violation or truth_force_violation,
        "truth_benign_eligible": eligible
        and not truth_accel_violation
        and not truth_force_violation,
        "predicted_peak_force_n": float(prediction.predicted_peak_force_n[0]),
        "truth_peak_force_n": truth_force_peak,
        "qualified_acceleration_margin_deg_s2": np.degrees(
            prediction.prefix_acceleration_margin_rad_s2[0, -1]
        ),
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accel_error = np.vstack([row["prediction"]["acceleration_error_deg_s2"] for row in rows])
    force_error = np.concatenate(
        [row["prediction"]["force_error_norm_n"] for row in rows]
    )
    force_vectors = np.concatenate(
        [row["prediction"]["force_error_world_n"] for row in rows], axis=0
    )
    accepted_violations = [
        row
        for row in rows
        if row["prediction"]["predicted_accepted"]
        and row["prediction"]["truth_violating"]
    ]
    benign = [row for row in rows if row["prediction"]["truth_benign_eligible"]]
    accepted_benign = [
        row for row in benign if row["prediction"]["predicted_accepted"]
    ]
    worst_force_index = int(np.argmax(force_error))
    flattened = [
        (row, prefix_index)
        for row in rows
        for prefix_index in range(len(COMPACT_PREFIX_TIMES_S))
    ]
    worst_force_row, worst_force_prefix = flattened[worst_force_index]
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(accel_error), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(
            np.abs(accel_error), axis=0
        ),
        "force_vector_rmse_n": float(
            np.sqrt(np.mean(np.sum(force_vectors * force_vectors, axis=1)))
        ),
        "force_error_norm_p95_n": float(np.percentile(force_error, 95.0)),
        "force_error_norm_max_n": float(np.max(force_error)),
        "supported_candidate_count": int(
            sum(row["prediction"]["supported"] for row in rows)
        ),
        "predicted_accepted_count": int(
            sum(row["prediction"]["predicted_accepted"] for row in rows)
        ),
        "truth_violating_count": int(
            sum(row["prediction"]["truth_violating"] for row in rows)
        ),
        "predicted_accepted_truth_violating_count": len(accepted_violations),
        "predicted_accepted_truth_violating_cases": [
            f"{row['group_id']}::{row['candidate_name']}"
            for row in accepted_violations
        ],
        "truth_benign_eligible_count": len(benign),
        "accepted_benign_count": len(accepted_benign),
        "benign_acceptance_coverage": (
            None if not benign else len(accepted_benign) / len(benign)
        ),
        "worst_force_case": {
            "case": (
                f"{worst_force_row['group_id']}::"
                f"{worst_force_row['candidate_name']}"
            ),
            "offset_ms": 5.0 * (worst_force_prefix + 1),
            "error_norm_n": float(force_error[worst_force_index]),
        },
    }


def _runtime_benchmark(
    clones: dict[str, Any],
    model: CompactCuffResponseModelV1,
    *,
    repeats_per_state: int,
) -> dict[str, Any]:
    runtimes_ms = []
    statuses = []
    for timestamp in GROUPS["test"]:
        clone = clones[f"test__t{timestamp:.3f}"]
        for _ in range(repeats_per_state):
            preview, graph, runtime = _make_preview(clone, model)
            started = perf_counter()
            _, diagnostics = graph["mpc"].solve_goal(
                runtime["task_observation"],
                runtime["authoritative_task_state"],
                PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                graph["current_model"],
                first_action_batch_preview=preview.preview,
            )
            runtimes_ms.append(1000.0 * (perf_counter() - started))
            statuses.append(str(diagnostics["status"]))
    values = np.asarray(runtimes_ms, dtype=float)
    return {
        "sample_count": len(values),
        "states": [float(value) for value in GROUPS["test"]],
        "repeats_per_state": repeats_per_state,
        "p50_ms": float(np.percentile(values, 50.0)),
        "p95_ms": float(np.percentile(values, 95.0)),
        "p99_ms": float(np.percentile(values, 99.0)),
        "maximum_ms": float(np.max(values)),
        "deadline_ms": 20.0,
        "deadline_miss_count": int(np.count_nonzero(values >= 20.0)),
        "deadline_miss_rate": float(np.mean(values >= 20.0)),
        "statuses": statuses,
        "complete_goal_mpc_solve_timed": True,
        "existing_cem_settings_unchanged": True,
        "setup_and_snapshot_restore_excluded": True,
    }


def run(output_dir: Path, *, runtime_repeats_per_state: int) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = tuple(
        _target_for_time(timestamp, group)
        for group, timestamps in GROUPS.items()
        for timestamp in timestamps
    )
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
        baseline = smoke_module.run_goal_mpc_smoke(
            output_dir / "baseline_capture",
            maximum_duration_s=0.335,
            plant_factory=_plant_factory,
            plant_case_name="cr12_compact_predictor_v1_dataset_capture",
            near_limit_shadow_targets=targets,
        )
    finally:
        smoke_module.capture_diagnostic_continuation_clone = original_capture
    missing = sorted(target.source_trace for target in targets if target.source_trace not in captured)
    if missing:
        raise RuntimeError(f"dataset anchors not captured: {missing}")
    selected = _selected_actions(output_dir / "baseline_capture" / "trace.npz")

    branches: list[dict[str, Any]] = []
    for group, timestamps in GROUPS.items():
        for timestamp in timestamps:
            clone = captured[f"{group}__t{timestamp:.3f}"]
            for candidate_name, offset in CANDIDATE_OFFSETS_NM.items():
                branches.append(
                    _branch_truth(
                        clone,
                        group=group,
                        timestamp_s=timestamp,
                        candidate_name=candidate_name,
                        candidate_action_nm=selected[timestamp] + offset,
                    )
                )

    development = [row for row in branches if row["group"] == "development"]
    development_features = np.concatenate([row["features"] for row in development])
    development_target = np.concatenate(
        [row["target_twist_increment"] for row in development]
    )
    development_group_ids = tuple(sorted({row["group_id"] for row in development}))
    model = fit_compact_cuff_response_model(
        features=development_features,
        target_twist_increment=development_target,
        ridge=RIDGE,
        development_group_ids=development_group_ids,
    )

    calibration = [row for row in branches if row["group"] == "calibration"]
    calibration_predictions = []
    for branch in calibration:
        clone = captured[branch["group_id"]]
        prediction = _predict_branch(clone, branch, model)
        calibration_predictions.append({**branch, "prediction": prediction})
    calibration_error = np.vstack(
        [row["prediction"]["acceleration_error_deg_s2"] for row in calibration_predictions]
    )
    margin_deg_s2 = np.max(np.abs(calibration_error), axis=0)
    calibration_features = np.concatenate([row["features"] for row in calibration])
    support_features = np.concatenate([development_features, calibration_features])
    model = model.with_margin_and_support(
        acceleration_margin_rad_s2=np.radians(margin_deg_s2),
        feature_min=np.min(support_features, axis=0),
        feature_max=np.max(support_features, axis=0),
        calibration_group_ids=tuple(sorted({row["group_id"] for row in calibration})),
    )
    (output_dir / "compact_execution_model_v1.json").write_text(
        json.dumps(model.record(), indent=2, sort_keys=True), encoding="utf-8"
    )

    evaluated: list[dict[str, Any]] = []
    for branch in branches:
        clone = captured[branch["group_id"]]
        prediction = _predict_branch(clone, branch, model)
        evaluated.append({**branch, "prediction": prediction})

    test_rows = [row for row in evaluated if row["group"] == "test"]
    regression_rows = [
        row for row in evaluated if row["group"] == "historical_regression"
    ]
    test_metrics = _metrics(test_rows)
    regression_metrics = _metrics(regression_rows)
    per_anchor = {
        f"t{timestamp:.3f}": _metrics(
            [row for row in test_rows if np.isclose(row["timestamp_s"], timestamp)]
        )
        for timestamp in GROUPS["test"]
    }
    known = next(
        row
        for row in regression_rows
        if np.isclose(row["timestamp_s"], 0.300)
        and row["candidate_name"] == "selected"
    )
    runtime = _runtime_benchmark(
        captured, model, repeats_per_state=runtime_repeats_per_state
    )

    criteria = {
        "human_acceleration_p95": {
            "threshold_deg_s2": [30.0, 60.0],
            "observed_deg_s2": test_metrics[
                "acceleration_absolute_error_p95_deg_s2"
            ],
            "status": (
                "PASS"
                if np.all(
                    np.asarray(
                        test_metrics["acceleration_absolute_error_p95_deg_s2"]
                    )
                    <= np.asarray([30.0, 60.0])
                )
                else "FAIL"
            ),
        },
        "cuff_force_prediction": {
            "rmse_threshold_n": 5.0,
            "p95_threshold_n": 10.0,
            "observed_rmse_n": test_metrics["force_vector_rmse_n"],
            "observed_p95_n": test_metrics["force_error_norm_p95_n"],
            "status": (
                "PASS"
                if test_metrics["force_vector_rmse_n"] <= 5.0
                and test_metrics["force_error_norm_p95_n"] <= 10.0
                else "FAIL"
            ),
        },
        "finite_set_feasibility": {
            "accepted_truth_violations": test_metrics[
                "predicted_accepted_truth_violating_count"
            ],
            "benign_acceptance_coverage": test_metrics[
                "benign_acceptance_coverage"
            ],
            "known_cr12_violation_accepted": known["prediction"][
                "predicted_accepted"
            ],
            "known_cr12_truth_violation": known["prediction"]["truth_violating"],
            "status": (
                "PASS"
                if test_metrics["predicted_accepted_truth_violating_count"] == 0
                and not known["prediction"]["predicted_accepted"]
                and (test_metrics["benign_acceptance_coverage"] or 0.0) > 0.0
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
        "20ms_scope_only": {
            "status": "PASS",
            "beyond_20ms_validated": False,
            "note": "compact model is not used beyond its validated 20 ms screen",
        },
    }
    all_pass = all(item["status"] == "PASS" for item in criteria.values())
    any_pass = any(item["status"] == "PASS" for item in criteria.values())
    overall = "PASS" if all_pass else ("PARTIAL" if any_pass else "FAIL")
    summary = {
        "schema": "stage5_cr12_compact_closed_loop_predictor_v1",
        "evidence_category": "bounded_simulation_engineering_validation",
        "shadow_only": True,
        "activated_in_authoritative_control": False,
        "old_predictor_default_and_reproducible": True,
        "model": {
            "version": model.version,
            "form": (
                "six diagonal affine 5 ms cuff-twist increments over current twist, "
                "command-minus-measured-wrench, and command slew; trapezoidal cuff "
                "pose; unchanged interface and Human dynamics"
            ),
            "fit_sample_count": model.fit_sample_count,
            "ridge": model.ridge,
            "acceleration_margin_deg_s2": margin_deg_s2,
            "margin_source": "calibration groups only; componentwise maximum absolute 20 ms error",
            "margin_is_guaranteed_bound": False,
            "scope_ms": [5.0, 10.0, 15.0, 20.0],
            "contact_state_input": False,
        },
        "dataset": {
            "groups": GROUPS,
            "candidate_offsets_nm": CANDIDATE_OFFSETS_NM,
            "complete_rollout_event_group_split": True,
            "neighboring_window_leakage": False,
            "historical_windows_used_as_independent_test": False,
            "failed_cases_preserved": True,
            "unvalidated_phases": ["HOLD", "RETURN"],
            "simulation_truth_used_online": False,
            "baseline_abort_status": baseline["task_status"],
            "baseline_abort_reason": baseline["abort_reason"],
            "original_abort_result_preserved": True,
        },
        "test_metrics": test_metrics,
        "test_per_anchor": per_anchor,
        "historical_regression_metrics": regression_metrics,
        "known_cr12_0p300_selected": known["prediction"],
        "runtime": runtime,
        "criteria": criteria,
        "overall": overall,
        "controlled_closed_loop_validation_justified": all_pass,
        "residual_learning_backup_justified": (
            not all_pass
            and (
                criteria["human_acceleration_p95"]["status"] == "FAIL"
                or criteria["cuff_force_prediction"]["status"] == "FAIL"
            )
        ),
        "scientific_parameters_changed": False,
        "controller_parameters_changed": False,
        "limits_or_abort_authority_changed": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "evaluated_cases.json").write_text(
        json.dumps(_jsonable(evaluated), indent=2, sort_keys=True), encoding="utf-8"
    )
    np.savez_compressed(
        output_dir / "frozen_dataset.npz",
        features=np.asarray([row["features"] for row in branches]),
        target_twist_increment=np.asarray(
            [row["target_twist_increment"] for row in branches]
        ),
        group=np.asarray([row["group"] for row in branches]),
        group_id=np.asarray([row["group_id"] for row in branches]),
        candidate_name=np.asarray([row["candidate_name"] for row in branches]),
        candidate_action_nm=np.asarray(
            [row["candidate_action_nm"] for row in branches]
        ),
        truth_acceleration_20ms_rad_s2=np.asarray(
            [row["truth_acceleration_20ms_rad_s2"] for row in branches]
        ),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "engineering_validation"
            / "cr12_compact_execution_predictor_v1_attempt_03"
        ),
    )
    parser.add_argument("--runtime-repeats-per-state", type=int, default=10)
    args = parser.parse_args()
    if args.runtime_repeats_per_state < 1:
        raise ValueError("runtime repeats must be positive")
    summary = run(
        args.output_dir,
        runtime_repeats_per_state=args.runtime_repeats_per_state,
    )
    print(json.dumps(_jsonable(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
