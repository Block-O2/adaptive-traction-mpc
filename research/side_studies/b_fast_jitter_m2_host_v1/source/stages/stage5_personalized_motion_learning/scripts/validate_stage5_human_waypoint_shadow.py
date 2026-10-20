#!/usr/bin/env python3
"""Bounded CR12 engineering validation of the shadow Human-waypoint contract."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.safety_filter import FILTER_INFEASIBLE, SAFE_FILTERED
from traction_mpc_stage4.track_brake import BRAKE

from traction_mpc_stage5.baseline_replay import FixedStage5Estimator
from traction_mpc_stage5.controller_interface import InterfaceAwareHumanStateObserver
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.cr12_plant import (
    Stage5CR12SensorBoundaryPlant,
    solve_cr12_stage5_ik,
)
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.hold_stabilizer import solve_loaded_hold_equilibrium
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.acceleration import measured_transmitted_human_input
from traction_mpc_stage5.human_waypoint_shadow import (
    HumanWaypointCandidate,
    HumanWaypointMPCShadowContractV1,
    MappedHumanWaypoint,
)
from traction_mpc_stage5.loaded_supervisor import Stage5LoadedTrackBrakeSupervisor
from traction_mpc_stage5.mechanics import NOMINAL_PHYSICS_DT_S
from traction_mpc_stage5.split_acceleration_monitor import (
    HumanMotionAccelerationAuthorityV1,
    SplitAccelerationMonitorV1,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


CONTROL_DT_S = EXECUTION_CONTROL_DT_S
HIGH_LEVEL_DT_S = 0.020
FIXED_HUMAN_MODEL_VERSION = "stage5_fixed_registered_human_v1"
SCHEMA = "stage5_human_waypoint_shadow_validation_v1"


def _jsonable(value: Any) -> Any:
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
    return value


def _estimator_observe(estimator: FixedStage5Estimator, measurement: Any) -> None:
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


def _initialize_cr12_loaded_equilibrium(
    plant: Stage5CR12SensorBoundaryPlant,
    equilibrium: Any,
) -> Any:
    robot_pose = equilibrium.robot_cuff_pose_world
    world_from_end_effector = robot_pose.compose(
        STAGE5_GEOMETRY.end_effector_from_cuff.inverse()
    )
    base_from_end_effector = STAGE5_GEOMETRY.world_from_base.inverse().compose(
        world_from_end_effector
    )
    robot_q = solve_cr12_stage5_ik(
        plant._ik_robot,
        base_from_end_effector,
        previous_q_rad=plant.data.qpos[plant.robot_qpos_indices].copy(),
    )
    plant.data.qpos[plant.human_qpos_indices] = equilibrium.q_goal_rad
    plant.data.qpos[plant.robot_qpos_indices] = robot_q
    plant.data.qvel[:] = 0.0
    plant.data.ctrl[:] = 0.0
    plant.neutral_robot_q = robot_q.copy()
    plant.last_joint_torque[:] = 0.0
    plant.last_unclipped_joint_torque[:] = 0.0
    plant.last_force[:] = 0.0
    plant.last_moment[:] = 0.0
    return plant.observe()


def _shank_clearance_m(q_rad: np.ndarray) -> float:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    plane_x = STAGE5_GEOMETRY.world_from_human.rotation[:, 0]
    plane_z = STAGE5_GEOMETRY.world_from_human.rotation[:, 2]
    hip_z = float(STAGE5_GEOMETRY.world_from_human.translation[2])
    knee_z = hip_z + STAGE5_HUMAN.thigh_length_m * (
        np.cos(q1) * plane_x[2] + np.sin(q1) * plane_z[2]
    )
    ankle_z = knee_z + STAGE5_HUMAN.shank_length_m * (
        np.cos(phi) * plane_x[2] + np.sin(phi) * plane_z[2]
    )
    return float(min(knee_z, ankle_z) - SHANK_RADIUS_M - BED_HEIGHT_M)


def _shank_bed_contact(plant: Stage5CR12SensorBoundaryPlant) -> bool:
    shank_geom_id = int(plant.model.geom("shank_geom").id)
    for index in range(plant.data.ncon):
        contact = plant.data.contact[index]
        pair = {int(contact.geom1), int(contact.geom2)}
        if plant.bed_geom_id in pair and shank_geom_id in pair:
            return True
    return False


def _phase_goal(phase: TaskPhase) -> np.ndarray:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    return np.asarray(
        spec.start_return_target_rad
        if phase is TaskPhase.RETURN
        else spec.outbound_goal_target_rad,
        dtype=float,
    )


def _candidate(
    label: str,
    phase: TaskPhase,
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
) -> HumanWaypointCandidate:
    return HumanWaypointCandidate(
        label=label,
        phase=phase,
        phase_goal_rad=_phase_goal(phase),
        q_waypoint_rad=np.asarray(q_rad, dtype=float),
        dq_waypoint_rad_s=np.asarray(dq_rad_s, dtype=float),
    )


def _prepare_runtime(
    name: str,
    start_q_rad: np.ndarray,
    *,
    truth_human: Any = STAGE5_HUMAN,
    control_human_model: Any | None = None,
    control_human_model_version: str = FIXED_HUMAN_MODEL_VERSION,
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    plant = Stage5CR12SensorBoundaryPlant(truth_human)
    reset_truth = plant.reset(start_q_rad)
    initial_measurement = CausalMeasurementLayer(
        MeasurementCase(name=f"{name}_initial", update_rate_hz=200.0, latency_s=0.0),
        reset_truth,
    ).current
    estimator = FixedStage5Estimator(
        initial_measurement.attachment_position_m,
        initial_measurement.attachment_rotation_matrix,
        start_q_rad,
    )
    _estimator_observe(estimator, initial_measurement)
    human_model = (
        estimator.model if control_human_model is None else control_human_model
    )
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(
        spec,
        human_model,
        allocator,
        target_q_rad=start_q_rad,
        target_dq_rad_s=np.zeros(2),
    )
    truth = _initialize_cr12_loaded_equilibrium(plant, equilibrium)
    measurement_layer = CausalMeasurementLayer(
        MeasurementCase(name=name, update_rate_hz=200.0, latency_s=0.0), truth
    )
    _estimator_observe(estimator, measurement_layer.current)
    interface_observer = InterfaceAwareHumanStateObserver()
    observation, interface_state = interface_observer.update(
        measurement_layer.current,
        human_model,
        human_model_version=control_human_model_version,
    )
    contract = HumanWaypointMPCShadowContractV1(spec, human_model, allocator)
    initial_candidate = _candidate(
        f"{name}_initial_support",
        TaskPhase.OUTBOUND,
        start_q_rad,
        np.zeros(2),
    )
    mapped = contract.prepare(initial_candidate)
    initial = contract.command(
        plant=plant,
        measurement=measurement_layer.current,
        observation=observation,
        interface_state=interface_state,
        mapped_waypoint=mapped,
    )
    if not initial.filter_result.feasible:
        raise RuntimeError("initial loaded Human-waypoint support is infeasible")
    command = initial.filter_result.filtered_preview.command
    plant.apply_executable_command(command)
    monitor = SplitAccelerationMonitorV1()
    authority = HumanMotionAccelerationAuthorityV1(
        spec.task_joint_acceleration_limit_rad_s2
    )
    return {
        "plant": plant,
        "measurement_layer": measurement_layer,
        "estimator": estimator,
        "human_model": human_model,
        "human_model_version": str(control_human_model_version),
        "allocator": allocator,
        "interface_observer": interface_observer,
        "contract": contract,
        "supervisor": Stage5LoadedTrackBrakeSupervisor(),
        "monitor": monitor,
        "authority": authority,
        "last_command": command,
        "start_q_rad": start_q_rad.copy(),
    }


Schedule = Callable[[float], HumanWaypointCandidate]
StatefulSchedule = Callable[[float, np.ndarray], HumanWaypointCandidate]


def _orientation_error_rad(target: np.ndarray, actual: np.ndarray) -> float:
    return float(Rotation.from_matrix(target @ actual.T).magnitude())


def _run_case(
    *,
    name: str,
    kind: str,
    start_q_rad: np.ndarray,
    duration_s: float,
    schedule: Schedule | None = None,
    stateful_schedule: StatefulSchedule | None = None,
    completion_check: Callable[[], bool] | None = None,
    schedule_context_hook: Callable[..., None] | None = None,
    runtime_factory: Callable[[str, np.ndarray], dict[str, Any]] | None = None,
    deployable_sample_hook: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    if (schedule is None) == (stateful_schedule is None):
        raise ValueError("provide exactly one schedule callback")
    runtime = (
        _prepare_runtime(name, start_q_rad)
        if runtime_factory is None
        else runtime_factory(name, start_q_rad)
    )
    plant = runtime["plant"]
    measurement_layer = runtime["measurement_layer"]
    estimator = runtime["estimator"]
    human_model = runtime["human_model"]
    human_model_version = str(runtime["human_model_version"])
    allocator = runtime["allocator"]
    observer = runtime["interface_observer"]
    contract = runtime["contract"]
    supervisor = runtime["supervisor"]
    monitor = runtime["monitor"]
    authority = runtime["authority"]
    last_command = runtime["last_command"]
    physics_substeps = int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    if not np.isclose(
        physics_substeps * NOMINAL_PHYSICS_DT_S,
        CONTROL_DT_S,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError("physics timestep does not divide the control period")

    records: list[dict[str, Any]] = []
    safety_statuses: Counter[str] = Counter()
    contract_runtimes_ms: list[float] = []
    brake_cycles = 0
    force_gate_events = 0
    torque_clip_events = 0
    authority_violations = 0
    termination_reason: str | None = None
    current_key: tuple[Any, ...] | None = None
    mapped: MappedHumanWaypoint | None = None
    executed_waypoint_keys: set[tuple[Any, ...]] = set()

    steps = int(round(duration_s / CONTROL_DT_S))
    for step in range(steps + 1):
        truth = plant.observe()
        measurement = measurement_layer.update(truth)
        _estimator_observe(estimator, measurement)
        observation, interface_state = observer.update(
            measurement,
            human_model,
            human_model_version=human_model_version,
        )
        elapsed_s = step * CONTROL_DT_S
        high_level_time_s = min(
            duration_s,
            np.floor((elapsed_s + 1.0e-12) / HIGH_LEVEL_DT_S) * HIGH_LEVEL_DT_S,
        )
        if schedule_context_hook is not None:
            schedule_context_hook(
                plant=plant,
                measurement=measurement,
                observation=observation,
                interface_state=interface_state,
                contract=contract,
            )
        try:
            candidate = (
                schedule(high_level_time_s)
                if schedule is not None
                else stateful_schedule(elapsed_s, observation.as_array())
            )
        except ValueError as error:
            termination_reason = f"WAYPOINT_SCHEDULER_REJECTED: {error}"
            break
        key = (
            candidate.label,
            candidate.phase.value,
            *candidate.q_waypoint_rad.tolist(),
            *candidate.dq_waypoint_rad_s.tolist(),
        )
        if key != current_key:
            mapped = contract.prepare(candidate)
            current_key = key
            executed_waypoint_keys.add(key)
        assert mapped is not None

        generalized_human_input_nm = measured_transmitted_human_input(
            observation, interface_state, human_model
        )
        if deployable_sample_hook is not None:
            hook_result = deployable_sample_hook(
                {
                    "episode_time_s": elapsed_s,
                    "estimated_human_state_rad_rad_s": observation.as_array().copy(),
                    "measured_human_cuff_force_world_n": (
                        interface_state.measured_force_world_n.copy()
                    ),
                    "measured_human_cuff_moment_world_nm": (
                        interface_state.measured_moment_world_nm.copy()
                    ),
                    "measured_generalized_human_input_nm": (
                        generalized_human_input_nm.copy()
                    ),
                    "task_phase": candidate.phase.value,
                    "interface_model_version": (
                        CONTROLLER_NOMINAL_INTERFACE.model_version
                    ),
                    "current_control_model_version": human_model_version,
                }
            )
            if not isinstance(hook_result, dict):
                raise TypeError("deployable sample hook must return a dict")
            if bool(hook_result.get("apply_update", False)):
                raise RuntimeError(
                    "Human-waypoint personalization cannot update mid-repetition"
                )

        split_sample = monitor.update(
            sample_timestamp_s=observation.sample_timestamp_s,
            estimated_dq_rad_s=observation.as_array()[2:],
            cuff_force_world_n=interface_state.measured_force_world_n,
            cuff_moment_world_nm=interface_state.measured_moment_world_nm,
            interface_translation_human_m=interface_state.displacement_human_m,
            interface_velocity_human_m_s=interface_state.velocity_human_m_s,
            interface_rotation_human_rad=interface_state.rotation_error_human_rad,
            interface_angular_velocity_human_rad_s=(
                interface_state.angular_velocity_human_rad_s
            ),
            command_wrench_world=last_command.wrench_total_world,
            robot_joint_torque_command_nm=last_command.joint_torque_command_nm,
        )
        authority_decision = authority.evaluate(split_sample)
        authority_violations += int(authority_decision.violation)

        target = mapped.execution_target.robot_cuff_target
        target_position = target.world_from_cuff.translation
        target_rotation = target.world_from_cuff.rotation
        estimated = observation.as_array()
        truth_state = np.concatenate([truth.human_q_rad, truth.human_dq_rad_s])
        torque_fraction = np.abs(last_command.joint_torque_command_nm) / plant.torque_limits_nm
        records.append(
            {
                "time_s": float(truth.time_s),
                "elapsed_s": elapsed_s,
                "phase": candidate.phase.value,
                "waypoint_label": candidate.label,
                "requested_q_rad": candidate.q_waypoint_rad.copy(),
                "requested_dq_rad_s": candidate.dq_waypoint_rad_s.copy(),
                "estimated_state_rad_rad_s": estimated.copy(),
                "truth_state_rad_rad_s": truth_state,
                "control_human_model_version": human_model_version,
                "deployable_measured_generalized_input_nm": (
                    generalized_human_input_nm.copy()
                ),
                "cuff_position_error_m": float(
                    np.linalg.norm(measurement.attachment_position_m - target_position)
                ),
                "cuff_orientation_error_rad": _orientation_error_rad(
                    target_rotation, measurement.attachment_rotation_matrix
                ),
                "cuff_linear_twist_error_m_s": float(
                    np.linalg.norm(
                        measurement.attachment_velocity_m_s
                        - target.linear_velocity_world_m_s
                    )
                ),
                "cuff_angular_twist_error_rad_s": float(
                    np.linalg.norm(
                        measurement.attachment_angular_velocity_rad_s
                        - target.angular_velocity_world_rad_s
                    )
                ),
                "cuff_force_world_n": np.asarray(
                    measurement.cuff_force_vector_n, dtype=float
                ).copy(),
                "cuff_moment_world_nm": np.asarray(
                    measurement.cuff_moment_vector_nm, dtype=float
                ).copy(),
                "deployable_20ms_acceleration_rad_s2": (
                    split_sample.human_motion_acceleration_rad_s2.copy()
                ),
                "deployable_20ms_acceleration_valid": (
                    split_sample.human_motion_valid
                ),
                "acceleration_authority_violation": authority_decision.violation,
                "maximum_robot_torque_fraction": float(np.max(torque_fraction)),
                "robot_torque_clipped": bool(
                    not np.allclose(
                        last_command.unclipped_joint_torque_nm,
                        last_command.joint_torque_command_nm,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "shank_clearance_estimated_m": _shank_clearance_m(estimated[:2]),
                "shank_clearance_truth_m": _shank_clearance_m(truth.human_q_rad),
                "shank_bed_contact_truth": _shank_bed_contact(plant),
            }
        )
        if completion_check is not None and completion_check():
            break
        if authority_decision.violation:
            termination_reason = authority_decision.abort_reason
            break
        if step == steps:
            break

        started = perf_counter()
        try:
            shadow_command = contract.command(
                plant=plant,
                measurement=measurement,
                observation=observation,
                interface_state=interface_state,
                mapped_waypoint=mapped,
            )
        except ValueError as error:
            termination_reason = f"WAYPOINT_CONTRACT_REJECTED: {error}"
            break
        contract_runtimes_ms.append(1000.0 * (perf_counter() - started))
        records[-1].update(
            {
                "contract_pd_acceleration_request_rad_s2": (
                    shadow_command.desired_human_acceleration_rad_s2.copy()
                ),
                "contract_scheduled_20ms_acceleration_rad_s2": (
                    shadow_command.motion_envelope_acceleration_rad_s2.copy()
                ),
                "contract_motion_history_valid": (
                    shadow_command.motion_envelope_history_valid
                ),
                "contract_motion_history_hold": shadow_command.motion_envelope_hold,
                "contract_pd_request_limit_exceeded_diagnostic": (
                    shadow_command.pd_request_limit_exceeded_diagnostic
                ),
                "contract_motion_acceleration_margin_rad_s2": (
                    shadow_command.acceleration_margin_rad_s2.copy()
                ),
            }
        )
        supervisor.bind_loaded_execution(
            observation, interface_state, mapped.execution_target
        )
        decision = supervisor.command(
            plant=plant,
            measurement=measurement,
            estimated_state=estimated,
            human_model=human_model,
            cuff_allocator=allocator,
            track_reference=mapped.reference,
            proposed_action_nm=shadow_command.generalized_action_nm,
            mpc_status=SAFE_ACTION,
            proposed_filter_result=shadow_command.filter_result,
        )
        if decision.safety_filter is not None:
            safety_statuses[str(decision.safety_filter["status"])] += 1
        brake_cycles += int(decision.mode == BRAKE)
        if decision.executable_preview is None:
            termination_reason = decision.terminate_reason or "NO_EXECUTABLE_COMMAND"
            break
        executable = decision.executable_preview.command
        force_gate_events += int(
            executable.margin_to_force_gate_n <= 0.0
            or (
                decision.safety_filter is not None
                and decision.safety_filter["status"] == FILTER_INFEASIBLE
            )
        )
        torque_clip_events += int(
            not np.allclose(
                executable.unclipped_joint_torque_nm,
                executable.joint_torque_command_nm,
                atol=1.0e-12,
                rtol=0.0,
            )
        )
        plant.apply_executable_command(executable)
        last_command = executable
        for _ in range(physics_substeps):
            plant.step()

    return _summarize_case(
        name=name,
        kind=kind,
        start_q_rad=start_q_rad,
        duration_s=duration_s,
        records=records,
        executed_waypoint_count=len(executed_waypoint_keys),
        safety_statuses=safety_statuses,
        brake_cycles=brake_cycles,
        force_gate_events=force_gate_events,
        torque_clip_events=torque_clip_events,
        authority_violations=authority_violations,
        termination_reason=termination_reason,
        contract_runtimes_ms=contract_runtimes_ms,
        supervisor_summary=supervisor.summary(),
        warning_counts=plant.warning_counts(),
    )


def _settling_time_s(
    elapsed_s: np.ndarray,
    q_error: np.ndarray,
    dq_error: np.ndarray,
) -> float | None:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    inside = np.all(
        np.abs(q_error)
        <= np.asarray(spec.joint_angle_completion_tolerance_rad),
        axis=1,
    ) & np.all(
        np.abs(dq_error)
        <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s),
        axis=1,
    )
    for index in np.flatnonzero(inside):
        if np.all(inside[index:]):
            return float(elapsed_s[index])
    return None


def _summarize_case(
    *,
    name: str,
    kind: str,
    start_q_rad: np.ndarray,
    duration_s: float,
    records: list[dict[str, Any]],
    executed_waypoint_count: int,
    safety_statuses: Counter[str],
    brake_cycles: int,
    force_gate_events: int,
    torque_clip_events: int,
    authority_violations: int,
    termination_reason: str | None,
    contract_runtimes_ms: list[float],
    supervisor_summary: dict[str, Any],
    warning_counts: dict[str, int],
) -> dict[str, Any]:
    if not records:
        raise RuntimeError("waypoint validation produced no records")
    elapsed = np.asarray([row["elapsed_s"] for row in records])
    requested_q = np.asarray([row["requested_q_rad"] for row in records])
    requested_dq = np.asarray([row["requested_dq_rad_s"] for row in records])
    estimated = np.asarray([row["estimated_state_rad_rad_s"] for row in records])
    truth = np.asarray([row["truth_state_rad_rad_s"] for row in records])
    q_error = estimated[:, :2] - requested_q
    dq_error = estimated[:, 2:] - requested_dq
    final_direction = requested_q[-1] - start_q_rad
    direction_sign = np.sign(final_direction)
    overshoot = np.maximum(
        direction_sign[None, :] * (estimated[:, :2] - requested_q), 0.0
    )
    force = np.asarray([row["cuff_force_world_n"] for row in records])
    moment = np.asarray([row["cuff_moment_world_nm"] for row in records])
    force_norm = np.linalg.norm(force, axis=1)
    moment_norm = np.linalg.norm(moment, axis=1)
    valid_accel = np.asarray(
        [row["deployable_20ms_acceleration_valid"] for row in records], dtype=bool
    )
    accel = np.asarray(
        [row["deployable_20ms_acceleration_rad_s2"] for row in records]
    )
    angle_tolerance = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.joint_angle_completion_tolerance_rad
    )
    velocity_tolerance = np.asarray(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK.joint_velocity_completion_tolerance_rad_s
    )
    final_within = bool(
        np.all(np.abs(q_error[-1]) <= angle_tolerance)
        and np.all(np.abs(dq_error[-1]) <= velocity_tolerance)
    )
    phase_summary: dict[str, Any] = {}
    phase_array = np.asarray([row["phase"] for row in records])
    for phase in ("OUTBOUND", "HOLD", "RETURN"):
        mask = phase_array == phase
        if not np.any(mask):
            continue
        phase_summary[phase] = {
            "sample_count": int(np.count_nonzero(mask)),
            "q_tracking_rmse_deg": np.degrees(
                np.sqrt(np.mean(q_error[mask] ** 2, axis=0))
            ),
            "dq_tracking_rmse_deg_s": np.degrees(
                np.sqrt(np.mean(dq_error[mask] ** 2, axis=0))
            ),
            "minimum_truth_clearance_mm": float(
                1000.0
                * min(row["shank_clearance_truth_m"] for row in np.asarray(records, dtype=object)[mask])
            ),
        }
    runtime = np.asarray(contract_runtimes_ms, dtype=float)
    contract_records = [
        row
        for row in records
        if "contract_pd_acceleration_request_rad_s2" in row
    ]
    contract_pd_acceleration = np.asarray(
        [row["contract_pd_acceleration_request_rad_s2"] for row in contract_records]
    )
    contract_scheduled_acceleration = np.asarray(
        [
            row["contract_scheduled_20ms_acceleration_rad_s2"]
            for row in contract_records
        ]
    )
    summary = {
        "name": name,
        "kind": kind,
        "requested_duration_s": duration_s,
        "executed_duration_s": float(elapsed[-1]),
        "termination_reason": termination_reason,
        "executed_waypoint_count": executed_waypoint_count,
        "start_q_deg": np.degrees(start_q_rad),
        "final_requested_q_deg": np.degrees(requested_q[-1]),
        "final_requested_dq_deg_s": np.degrees(requested_dq[-1]),
        "final_estimated_q_deg": np.degrees(estimated[-1, :2]),
        "final_estimated_dq_deg_s": np.degrees(estimated[-1, 2:]),
        "final_truth_q_deg": np.degrees(truth[-1, :2]),
        "final_truth_dq_deg_s": np.degrees(truth[-1, 2:]),
        "final_estimated_q_error_deg": np.degrees(q_error[-1]),
        "final_estimated_dq_error_deg_s": np.degrees(dq_error[-1]),
        "estimated_q_tracking_rmse_deg": np.degrees(
            np.sqrt(np.mean(q_error**2, axis=0))
        ),
        "estimated_dq_tracking_rmse_deg_s": np.degrees(
            np.sqrt(np.mean(dq_error**2, axis=0))
        ),
        "peak_waypoint_overshoot_deg": np.degrees(np.max(overshoot, axis=0)),
        "settling_time_to_existing_task_tolerance_s": _settling_time_s(
            elapsed, q_error, dq_error
        ),
        "final_within_existing_task_tolerance": final_within,
        "cuff_tracking": {
            "position_error_peak_mm": float(
                1000.0 * max(row["cuff_position_error_m"] for row in records)
            ),
            "orientation_error_peak_deg": float(
                np.degrees(max(row["cuff_orientation_error_rad"] for row in records))
            ),
            "linear_twist_error_peak_mm_s": float(
                1000.0
                * max(row["cuff_linear_twist_error_m_s"] for row in records)
            ),
            "angular_twist_error_peak_deg_s": float(
                np.degrees(
                    max(row["cuff_angular_twist_error_rad_s"] for row in records)
                )
            ),
        },
        "interaction": {
            "peak_cuff_force_n": float(np.max(force_norm)),
            "integral_cuff_force_n_s": float(np.trapezoid(force_norm, elapsed)),
            "peak_cuff_moment_nm": float(np.max(moment_norm)),
        },
        "human_motion_authority": {
            "valid_sample_count": int(np.count_nonzero(valid_accel)),
            "peak_abs_20ms_acceleration_deg_s2": (
                [None, None]
                if not np.any(valid_accel)
                else np.degrees(np.max(np.abs(accel[valid_accel]), axis=0))
            ),
            "violation_count": authority_violations,
        },
        "execution_safety": {
            "safety_filter_status_counts": dict(safety_statuses),
            "safety_filter_intervention_count": int(safety_statuses[SAFE_FILTERED]),
            "brake_cycle_count": brake_cycles,
            "force_gate_event_count": force_gate_events,
            "torque_clip_event_count": torque_clip_events,
            "maximum_robot_torque_fraction": float(
                max(row["maximum_robot_torque_fraction"] for row in records)
            ),
            "minimum_estimated_shank_clearance_mm": float(
                1000.0 * min(row["shank_clearance_estimated_m"] for row in records)
            ),
            "minimum_truth_shank_clearance_mm": float(
                1000.0 * min(row["shank_clearance_truth_m"] for row in records)
            ),
            "shank_bed_contact_sample_count": int(
                sum(bool(row["shank_bed_contact_truth"]) for row in records)
            ),
            "mujoco_warning_counts": warning_counts,
        },
        "phase_summary": phase_summary,
        "contract_runtime_ms": {
            "sample_count": int(len(runtime)),
            "mean": None if not len(runtime) else float(np.mean(runtime)),
            "p95": None if not len(runtime) else float(np.percentile(runtime, 95)),
            "maximum": None if not len(runtime) else float(np.max(runtime)),
        },
        "waypoint_contract_acceleration": {
            "command_count": len(contract_records),
            "history_invalid_hold_count": int(
                sum(
                    not bool(row["contract_motion_history_valid"])
                    and bool(row["contract_motion_history_hold"])
                    for row in contract_records
                )
            ),
            "pd_request_limit_exceeded_diagnostic_count": int(
                sum(
                    bool(row["contract_pd_request_limit_exceeded_diagnostic"])
                    for row in contract_records
                )
            ),
            "peak_abs_pd_acceleration_request_deg_s2": (
                [None, None]
                if not len(contract_records)
                else np.degrees(
                    np.max(np.abs(contract_pd_acceleration), axis=0)
                )
            ),
            "peak_abs_scheduled_20ms_acceleration_deg_s2": (
                [None, None]
                if not len(contract_records)
                else np.degrees(
                    np.max(np.abs(contract_scheduled_acceleration), axis=0)
                )
            ),
        },
        "supervisor": supervisor_summary,
        "trace": records,
    }
    return _jsonable(summary)


def _single_schedule(
    *,
    label: str,
    phase: TaskPhase,
    target_q_rad: np.ndarray,
) -> Schedule:
    candidate = _candidate(label, phase, target_q_rad, np.zeros(2))
    return lambda _elapsed_s: candidate


def _sequence_schedule(start_q_rad: np.ndarray) -> Schedule:
    delta = np.radians([2.0, 10.0 / 3.0])
    outbound_duration_s = 0.8
    hold_end_s = 1.2
    return_end_s = 2.0

    def smooth(progress: float, duration: float) -> tuple[float, float]:
        ratio = float(np.clip(progress / duration, 0.0, 1.0))
        position = 3.0 * ratio**2 - 2.0 * ratio**3
        velocity = 6.0 * ratio * (1.0 - ratio) / duration
        return position, velocity

    def schedule(elapsed_s: float) -> HumanWaypointCandidate:
        if elapsed_s < outbound_duration_s - 1.0e-12:
            position, velocity = smooth(elapsed_s, outbound_duration_s)
            return _candidate(
                f"sequence_outbound_{elapsed_s:.3f}",
                TaskPhase.OUTBOUND,
                start_q_rad + position * delta,
                velocity * delta,
            )
        if elapsed_s < hold_end_s - 1.0e-12:
            return _candidate(
                "sequence_hold",
                TaskPhase.HOLD,
                start_q_rad + delta,
                np.zeros(2),
            )
        if elapsed_s < return_end_s - 1.0e-12:
            position, velocity = smooth(
                elapsed_s - hold_end_s, return_end_s - hold_end_s
            )
            return _candidate(
                f"sequence_return_{elapsed_s:.3f}",
                TaskPhase.RETURN,
                start_q_rad + (1.0 - position) * delta,
                -velocity * delta,
            )
        return _candidate(
            "sequence_return_settle",
            TaskPhase.RETURN,
            start_q_rad,
            np.zeros(2),
        )

    return schedule


def _plot_cases(cases: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=False)
    for case in cases:
        trace = case["trace"]
        elapsed = np.asarray([row["elapsed_s"] for row in trace])
        estimated = np.degrees(
            np.asarray([row["estimated_state_rad_rad_s"] for row in trace])[:, :2]
        )
        requested = np.degrees(
            np.asarray([row["requested_q_rad"] for row in trace])
        )
        if case["kind"] == "sequence":
            for joint in range(2):
                axes[0].plot(
                    elapsed,
                    estimated[:, joint],
                    label=f"realized q{joint + 1}",
                )
                axes[0].plot(
                    elapsed,
                    requested[:, joint],
                    "--",
                    label=f"requested q{joint + 1}",
                )
            force = np.linalg.norm(
                np.asarray([row["cuff_force_world_n"] for row in trace]), axis=1
            )
            axes[1].plot(elapsed, force, label="sequence cuff force")
        else:
            error = estimated - requested
            axes[1].plot(elapsed, np.linalg.norm(error, axis=1), label=case["name"])
    axes[0].set_title("Short Human-waypoint OUTBOUND/HOLD/RETURN sequence")
    axes[0].set_ylabel("Human angle [deg]")
    axes[0].legend(ncol=2)
    axes[0].grid(True, alpha=0.3)
    axes[1].set_title("Single-waypoint joint-error norm and sequence cuff force")
    axes[1].set_xlabel("elapsed time [s]")
    axes[1].set_ylabel("deg or N")
    axes[1].legend(ncol=2, fontsize=8)
    axes[1].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(output_dir: Path) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    mid = start + 0.20 * (
        np.asarray(spec.outbound_goal_target_rad, dtype=float) - start
    )
    definitions = [
        ("outbound_hip_biased", start, TaskPhase.OUTBOUND, np.radians([1.25, 0.50])),
        ("outbound_balanced", start, TaskPhase.OUTBOUND, np.radians([1.00, 1.00])),
        ("outbound_knee_biased", start, TaskPhase.OUTBOUND, np.radians([0.50, 3.00])),
        ("return_hip_biased", mid, TaskPhase.RETURN, -np.radians([1.25, 0.50])),
        ("return_balanced", mid, TaskPhase.RETURN, -np.radians([1.00, 1.00])),
        ("return_knee_biased", mid, TaskPhase.RETURN, -np.radians([0.50, 3.00])),
    ]
    cases: list[dict[str, Any]] = []
    for name, initial_q, phase, delta in definitions:
        cases.append(
            _run_case(
                name=name,
                kind="single_waypoint",
                start_q_rad=initial_q,
                duration_s=0.75,
                schedule=_single_schedule(
                    label=name,
                    phase=phase,
                    target_q_rad=initial_q + delta,
                ),
            )
        )
    cases.append(
        _run_case(
            name="short_outbound_hold_return",
            kind="sequence",
            start_q_rad=start,
            duration_s=2.4,
            schedule=_sequence_schedule(start),
        )
    )

    single = [case for case in cases if case["kind"] == "single_waypoint"]
    sequence = next(case for case in cases if case["kind"] == "sequence")
    mapping_executed = all(case["executed_waypoint_count"] > 0 for case in cases)
    no_execution_termination = all(
        case["termination_reason"] is None for case in cases
    )
    all_single_settled = all(
        case["final_within_existing_task_tolerance"] for case in single
    )
    sequence_returned = bool(sequence["final_within_existing_task_tolerance"])
    no_authority_violation = all(
        case["human_motion_authority"]["violation_count"] == 0 for case in cases
    )
    no_brake = all(
        case["execution_safety"]["brake_cycle_count"] == 0 for case in cases
    )
    no_force_gate = all(
        case["execution_safety"]["force_gate_event_count"] == 0 for case in cases
    )
    no_torque_clip = all(
        case["execution_safety"]["torque_clip_event_count"] == 0 for case in cases
    )
    no_contact = all(
        case["execution_safety"]["shank_bed_contact_sample_count"] == 0
        and case["execution_safety"]["minimum_truth_shank_clearance_mm"] > 0.0
        for case in cases
    )
    ready = bool(
        mapping_executed
        and no_execution_termination
        and all_single_settled
        and sequence_returned
        and no_authority_violation
        and no_brake
        and no_force_gate
        and no_torque_clip
        and no_contact
    )
    sequence_executed = sequence["termination_reason"] is None
    outbound_executed = any(
        case["name"].startswith("outbound_") and case["termination_reason"] is None
        for case in single
    )
    return_executed = any(
        case["name"].startswith("return_") and case["termination_reason"] is None
        for case in single
    )
    feasible = bool(
        mapping_executed and sequence_executed and outbound_executed and return_executed
    )
    if ready:
        decision = "HW-A — HUMAN-WAYPOINT CONTRACT IS EXECUTABLE AND READY FOR MPC PROTOTYPE"
    elif feasible:
        decision = "HW-B — CONTRACT IS FEASIBLE BUT EXECUTION/TRACKING NEEDS FURTHER WORK"
    else:
        decision = "HW-C — HUMAN-WAYPOINT ABSTRACTION IS NOT VIABLE WITH CURRENT EXECUTION LAYER"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "human_waypoint_tracking.png"
    _plot_cases(cases, plot_path)
    result = {
        "schema": SCHEMA,
        "evidence_category": "bounded_shadow_engineering_validation",
        "decision": decision,
        "shadow_only": True,
        "production_mpc_replaced": False,
        "formal_scientific_claim": False,
        "contract": _prepare_runtime("contract_record", start)["contract"].contract_record(),
        "case_definition": {
            "single_waypoint_duration_s": 0.75,
            "single_waypoint_delta_deg": {
                name: np.degrees(delta).tolist()
                for name, _, _, delta in definitions
            },
            "sequence": {
                "outbound_duration_s": 0.8,
                "hold_duration_s": 0.4,
                "return_duration_s": 0.8,
                "return_settle_duration_s": 0.4,
                "excursion_deg": [2.0, 10.0 / 3.0],
                "waypoint_refresh_s": HIGH_LEVEL_DT_S,
            },
            "settling_definition": (
                "first sample after which q/dq remain inside the existing task "
                "completion tolerances; no new settling threshold"
            ),
        },
        "criteria_observed": {
            "all_mappings_executed": mapping_executed,
            "no_execution_termination": no_execution_termination,
            "all_single_waypoints_finish_inside_existing_task_tolerance": (
                all_single_settled
            ),
            "sequence_returns_inside_existing_task_tolerance": sequence_returned,
            "no_20ms_human_acceleration_violation": no_authority_violation,
            "no_brake": no_brake,
            "no_force_gate_event": no_force_gate,
            "no_torque_clipping": no_torque_clip,
            "no_shank_bed_contact": no_contact,
        },
        "comparison_with_current_torque_increment_mpc": {
            "current_action_semantics": (
                "support-centered Human generalized torque increment with nominal "
                "5/10/15/20 ms interface/Human screening"
            ),
            "waypoint_action_semantics": (
                "Human q/dq target mapped deterministically to cuff pose/twist and "
                "the existing executable command path"
            ),
            "short_horizon_robot_interface_prediction_required_by_waypoint_contract": False,
            "task_controllability_preserved_in_bounded_cases": bool(
                all_single_settled and sequence_returned
            ),
            "future_human_personalization_compatible": True,
            "future_cumulative_force_value_compatible": True,
            "compatibility_basis": (
                "candidate and realized state remain Human q/dq; measured cuff-force "
                "integral and execution-limit activity are causal outcome/context signals"
            ),
        },
        "cases": cases,
        "aggregate": {
            "case_count": len(cases),
            "peak_cuff_force_n": max(
                case["interaction"]["peak_cuff_force_n"] for case in cases
            ),
            "peak_cuff_moment_nm": max(
                case["interaction"]["peak_cuff_moment_nm"] for case in cases
            ),
            "peak_abs_20ms_acceleration_deg_s2": np.max(
                np.asarray(
                    [
                        case["human_motion_authority"][
                            "peak_abs_20ms_acceleration_deg_s2"
                        ]
                        for case in cases
                    ],
                    dtype=float,
                ),
                axis=0,
            ),
            "maximum_robot_torque_fraction": max(
                case["execution_safety"]["maximum_robot_torque_fraction"]
                for case in cases
            ),
            "minimum_truth_shank_clearance_mm": min(
                case["execution_safety"]["minimum_truth_shank_clearance_mm"]
                for case in cases
            ),
            "safety_filter_status_counts": dict(
                sum(
                    (
                        Counter(case["execution_safety"]["safety_filter_status_counts"])
                        for case in cases
                    ),
                    Counter(),
                )
            ),
        },
        "plot": str(plot_path),
        "scope_invariants": {
            "new_robot_controller_added": False,
            "gains_tuned": False,
            "thresholds_changed": False,
            "task_changed": False,
            "contact_model_changed": False,
            "stage3_or_stage4_changed": False,
            "rl_or_value_changed": False,
            "historical_results_changed": False,
        },
        "limitations": [
            "bounded small-waypoint simulation only, not a full rehabilitation campaign",
            "ideal 200 Hz controller measurements only",
            "provisional Stage-5 cuff/interface and CR12 simulation actuator semantics",
            "no hardware or clinical safety claim",
        ],
    }
    result = _jsonable(result)
    (output_dir / "human_waypoint_validation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "stages/stage5_personalized_motion_learning/results/engineering_validation/"
            "human_waypoint_shadow_v1_attempt_01"
        ),
    )
    args = parser.parse_args()
    result = run_validation(args.output_dir)
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "criteria_observed": result["criteria_observed"],
                "aggregate": result["aggregate"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
