"""Executed CR12 commissioning-to-task adaptive loop.

This module is deliberately an integration layer.  It reuses the registered
CR12 plant, compliant cuff, measured low-level execution, recovered effective
geometry/beta/residual belief, and Human-waypoint planner.  MuJoCo Human state
is written only to the evaluation channel of the saved trace.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace, asdict
import json
import math
from pathlib import Path
from time import perf_counter, monotonic_ns
from types import SimpleNamespace
from typing import Any, Sequence

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry, nominal_base_parameters
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.safety_filter import FILTER_INFEASIBLE, SAFE_UNCHANGED
from traction_mpc_stage4.track_brake import BRAKE

from ..acceleration import measured_transmitted_human_input
from ..controller_interface import InterfaceAwareHumanStateObserver
from ..cr12_plant import Stage5CR12SensorBoundaryPlant, solve_cr12_stage5_ik
from ..cr12_robot import CR12_VELOCITY_LIMITS_RAD_S
from ..geometry import STAGE5_GEOMETRY
from ..hold_stabilizer import solve_loaded_hold_equilibrium
from ..human import STAGE5_HUMAN, Stage5HumanParameters
from ..high_rom_v1 import deployable_prior as high_rom_deployable_prior, CONFIG_PATH as high_rom_config_path
from ..human_waypoint_feedback_mpc import (
    HumanWaypointFeedbackMPCConfigV1,
    HumanWaypointFeedbackMPCV1,
)
from ..human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from ..human_waypoint_shadow import (
    HumanWaypointCandidate,
    HumanWaypointMPCShadowContractV1,
    WaypointExecutionContext,
)
from ..loaded_execution import (
    build_stage5_loaded_execution_context, with_explicit_robot_target,
)
from ..loaded_supervisor import Stage5LoadedTrackBrakeSupervisor
from ..mechanics import NOMINAL_PHYSICS_DT_S
from ..split_acceleration_monitor import HumanMotionAccelerationAuthorityV1, SplitAccelerationMonitorV1
from ..task import (
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    GoalTaskState,
    TaskPhase,
    abort_episode,
    at_goal,
    start_episode,
    task_limit_violation,
    transition_phase,
)
from ..architecture_recovery_v2.effective_model import CausalEffectiveGeometryEstimator
from ..architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
from ..architecture_recovery_v2.phase3_human_waypoint import (
    AdaptiveMechanicsScreenV22,
    AdaptiveHumanWaypointHWMPCV22,
    StateResidualBeliefUpdaterV22,
)
from .online_planning import PlanLifecycle, snapshot_task_call
from .wall_physics import WallPhysicsSession
from .scientific_scheduler import ScientificPhysicsSession
from .session_state import carryover_runtime_fields, FORBIDDEN_TRANSIENT_FIELDS, integrate_measured_wrench
from .execution_policy import ExecutionMode, ScientificPlanLifecycle, SimulationVersion
from .activation_validation import (validate_activation, validate_rolling_composite,
                                    clearance_geometry_signature,
                                    SensorSupportedTaskClock,
                                    reference_safe_task_transition, causal_return_projection,
                                    return_finalization_reason)
from .rolling_suffix_splice import RollingSuffixCompositeSchedule
from .safe_fallback import FallbackLatch
from .terminal_commit import (attempt_return_commit, attempt_scientific_return_commit,
                              terminal_sample_evidence)
from .applied_reference_history import AppliedReferenceMotionHistory
from .receipt_reference_governor import ReceiptReferenceGovernor, velocity_box
from .fast_plant import CachedStage5CR12SensorBoundaryPlant
from .terminal_reference import (
    TerminalSetHumanWaypointPlannerV1, in_original_terminal_box, select_terminal_reference,
    receipt_reference_at_sample,
)
from .handoff_reference import stationary_emitted_boundary, screen_cartesian_bridge
from .startup_alignment import (
    StartupExecutionPoseAlignment, tool_increment_certificate, validate_recovery_options,
    align_active_startup_reference,
)
from .dev_a_recovery import RobotCuffPoseBridge, mapped_with_bridge
from .bumpless_transfer import BumplessHumanActionTransfer
from .rigid_table_reference import (
    CombinedRigidTableClearanceV1,
    RigidTableReferenceEnvelopeV1,
    choose_feedback_commissioning_target,
)


SCHEMA = "full3d_adaptive_integration_v1.executed_case.v1"
CONTROL_DT_S = float(EXECUTION_CONTROL_DT_S)
ADAPTATION_DT_S = 0.020


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def nominal_control_geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def nominal_control_model(rom_human: Stage5HumanParameters = STAGE5_HUMAN) -> StateResidualHumanModel:
    return StateResidualHumanModel(
        nominal_control_geometry(),
        nominal_base_parameters(rom_human),
        rom_human,
        residual_weights_nm=np.zeros((2, 5)),
    )


@dataclass(frozen=True)
class SessionClearanceContract:
    """Deployable conservative clearance from the session effective geometry."""

    geometry: PlanarCuffGeometry
    shank_length_upper_m: float = 0.46
    margin_m: float = 0.001
    geometry_source: str = "ONLINE_EFFECTIVE_HIP_AND_THIGH_PLUS_STRUCTURAL_PRIOR_SHANK_LENGTH_SET"

    def evaluate(self, q_rad: np.ndarray) -> np.ndarray | float:
        q = np.asarray(q_rad, dtype=float)
        rows = np.atleast_2d(q)
        q1 = rows[:, 0]
        phi = rows[:, 0] - rows[:, 1]
        hip_world = (
            self.geometry.origin_world_m[None, :]
            + self.geometry.hip_plane_m[0] * self.geometry.plane_x_world[None, :]
            + self.geometry.hip_plane_m[1] * self.geometry.plane_z_world[None, :]
        )
        knee = (
            hip_world
            + self.geometry.thigh_length_m
            * (
                np.cos(q1)[:, None] * self.geometry.plane_x_world[None, :]
                + np.sin(q1)[:, None] * self.geometry.plane_z_world[None, :]
            )
        )
        ankle = (
            knee
            + self.shank_length_upper_m
            * (
                np.cos(phi)[:, None] * self.geometry.plane_x_world[None, :]
                + np.sin(phi)[:, None] * self.geometry.plane_z_world[None, :]
            )
        )
        clearance = (
            np.minimum(knee[:, 2], ankle[:, 2])
            - SHANK_RADIUS_M
            - BED_HEIGHT_M
            - self.margin_m
        )
        return float(clearance[0]) if q.ndim == 1 else clearance

    def record(self) -> dict[str, Any]:
        return {
            "source": self.geometry_source,
            "effective_geometry": {
                "origin_world_m": self.geometry.origin_world_m.tolist(),
                "plane_x_world": self.geometry.plane_x_world.tolist(),
                "plane_z_world": self.geometry.plane_z_world.tolist(),
                "hip_plane_m": self.geometry.hip_plane_m.tolist(),
                "thigh_length_m": self.geometry.thigh_length_m,
                "knee_to_cuff_m": self.geometry.cuff_distance_m,
            },
            "conservative_shank_length_upper_m": self.shank_length_upper_m,
            "bed_height_m": BED_HEIGHT_M,
            "shank_radius_m": SHANK_RADIUS_M,
            "additional_margin_m": self.margin_m,
            "hidden_geometry_consumed": False,
        }


def _candidate(label: str, phase: TaskPhase, q: np.ndarray, dq: np.ndarray,
               spec: Any = PROVISIONAL_LOW_MODERATE_GOAL_TASK,
               context: WaypointExecutionContext = WaypointExecutionContext.TASK,
               ) -> HumanWaypointCandidate:
    goal = (
        spec.start_return_target_rad
        if phase is TaskPhase.RETURN
        else spec.outbound_goal_target_rad
    )
    return HumanWaypointCandidate(
        label=label,
        phase=phase,
        phase_goal_rad=np.asarray(goal, dtype=float),
        q_waypoint_rad=np.asarray(q, dtype=float),
        dq_waypoint_rad_s=np.asarray(dq, dtype=float),
        execution_context=context,
    )


def _quintic_reference(q0: np.ndarray, q1: np.ndarray, elapsed: float, duration: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = float(np.clip(elapsed / duration, 0.0, 1.0))
    p = 10.0 * s**3 - 15.0 * s**4 + 6.0 * s**5
    dp = (30.0 * s**2 - 60.0 * s**3 + 30.0 * s**4) / duration
    ddp = (60.0 * s - 180.0 * s**2 + 120.0 * s**3) / duration**2
    delta = np.asarray(q1) - np.asarray(q0)
    return np.asarray(q0) + p * delta, dp * delta, ddp * delta


def _initialize_loaded_runtime(name: str, start_q: np.ndarray, *,
                               spec: Any = PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                               physical_human: Any = None,
                               physical_geometry: Any = None,
                               control_human: Stage5HumanParameters = STAGE5_HUMAN,
                               startup_execution_pose_alignment: bool = False,
                               exact_cached_plant: bool = False) -> dict[str, Any]:
    model = nominal_control_model(control_human)
    allocator = default_engineering_cuff_allocator()
    physical_human = STAGE5_HUMAN if physical_human is None else physical_human
    physical_geometry = STAGE5_GEOMETRY if physical_geometry is None else physical_geometry
    plant_type = CachedStage5CR12SensorBoundaryPlant if exact_cached_plant else Stage5CR12SensorBoundaryPlant
    plant = plant_type(
        physical_human, geometry=physical_geometry,
    )
    # The registered start target is public task data. The simulated physical
    # initial joint state is a separate generation-side value; only the sensor
    # measurement formed below, never this reset value, reaches the observer.
    physical_initial_q_rad = np.array(start_q, dtype=float, copy=True)
    plant.reset(physical_initial_q_rad)
    # Preserve the registered nominal loaded-support preload.  For a varied
    # physical setup, apply that same cuff-relative offset at the physical
    # cuff pose; hidden geometry is used only to construct the plant initial
    # condition and is never passed to the deployable model or controller.
    equilibrium = solve_loaded_hold_equilibrium(
        spec, model, allocator, target_q_rad=start_q, target_dq_rad_s=np.zeros(2)
    )
    nominal_cuff_pose = STAGE5_GEOMETRY.world_from_cuff(start_q)
    cuff_relative_support = nominal_cuff_pose.inverse().compose(equilibrium.robot_cuff_pose_world)
    robot_pose = physical_geometry.world_from_cuff(physical_initial_q_rad, physical_human).compose(cuff_relative_support)
    world_from_end_effector = robot_pose.compose(physical_geometry.end_effector_from_cuff.inverse())
    base_from_end_effector = physical_geometry.world_from_base.inverse().compose(world_from_end_effector)
    robot_q = solve_cr12_stage5_ik(
        plant._ik_robot,
        base_from_end_effector,
        previous_q_rad=plant.data.qpos[plant.robot_qpos_indices].copy(),
    )
    plant.data.qpos[plant.human_qpos_indices] = physical_initial_q_rad
    plant.data.qpos[plant.robot_qpos_indices] = robot_q
    plant.data.qvel[:] = 0.0
    plant.data.ctrl[:] = 0.0
    plant.neutral_robot_q = robot_q.copy()
    truth = plant.observe()
    measurements = CausalMeasurementLayer(
        MeasurementCase(name=name, update_rate_hz=200.0, latency_s=0.0), truth
    )
    observer = InterfaceAwareHumanStateObserver()
    observation, interface = observer.update(
        measurements.current, model, human_model_version="population_prior_v1"
    )
    contract = HumanWaypointMPCShadowContractV1(spec, model, allocator)
    initial_support_state = observation.as_array()
    support = contract.prepare(_candidate("initial_support", TaskPhase.OUTBOUND,
        initial_support_state[:2], initial_support_state[2:], spec,
        WaypointExecutionContext.STARTUP_SUPPORT))
    alignment = None
    startup_alignment_record = None
    if startup_execution_pose_alignment:
        alignment = StartupExecutionPoseAlignment.from_measurement(
            measurements.current, support.execution_target.robot_cuff_target.world_from_cuff)
        support = alignment.apply(support)
        aligned_pose = support.execution_target.robot_cuff_target.world_from_cuff
        startup_alignment_record = {**alignment.record(),
            "initial_robot_tool_check": tool_increment_certificate(aligned_pose, aligned_pose)}
        if not startup_alignment_record["initial_robot_tool_check"]["feasible"]:
            raise RuntimeError("STARTUP_ALIGNED_ROBOT_TOOL_GEOMETRY_REJECTED")
    initial = contract.command(
        plant=plant,
        measurement=measurements.current,
        observation=observation,
        interface_state=interface,
        mapped_waypoint=support,
    )
    if not initial.filter_result.feasible:
        raise RuntimeError("loaded start support is infeasible")
    command = initial.filter_result.filtered_preview.command
    plant.apply_executable_command(command)
    return {
        "plant": plant,
        "offline_support_setup": {"source_sample_time_s": float(measurements.current.sample_time_s),
            "receipt_index": 0,
            "selected_command_force_total_n": command.force_total_n.copy(),
            "selected_command_moment_total_nm": command.moment_total_nm.copy(),
            "command_source_robot_point_m": measurements.current.attachment_position_m.copy(),
            "command_torque_nm": command.joint_torque_command_nm.copy(),
            "mode": "TRACK", "q_ref_rad": support.candidate.q_waypoint_rad.copy(),
            "dq_ref_rad_s": support.candidate.dq_waypoint_rad_s.copy(),
            "reference_effective_physics_s": float(plant.data.time),
            "robot_target_position_m": support.execution_target.robot_cuff_target.world_from_cuff.translation.copy(),
            "robot_target_rotation": support.execution_target.robot_cuff_target.world_from_cuff.rotation.copy(),
            "robot_target_geometry": tool_increment_certificate(support.execution_target.robot_cuff_target.world_from_cuff, support.execution_target.robot_cuff_target.world_from_cuff, count=2),
            "scope": "mechanical assembly/preload and initial validated support before active epoch"},
        "measurement_layer": measurements,
        "observer": observer,
        "model": model,
        "allocator": allocator,
        "contract": contract,
        "supervisor": Stage5LoadedTrackBrakeSupervisor(),
        "monitor": SplitAccelerationMonitorV1(),
        "authority": HumanMotionAccelerationAuthorityV1(spec.task_joint_acceleration_limit_rad_s2),
        "last_command": command,
        "last_command_robot_position_m": measurements.current.attachment_position_m.copy(),
        "last_command_source_sample_s": float(measurements.current.sample_time_s),
        "last_command_receipt_physics_s": float(plant.data.time),
        "initial_support_state": initial_support_state.copy(),
        "startup_alignment": alignment,
        "startup_alignment_active": alignment is not None,
        "startup_alignment_record": startup_alignment_record,
        "last_aligned_robot_reference": support.execution_target.robot_cuff_target.world_from_cuff,
        "startup_alignment_geometry_checks": [],
    }


def _shank_bed_contact(plant: Stage5CR12SensorBoundaryPlant) -> bool:
    shank = int(plant.model.geom("shank_geom").id)
    return any(
        {int(plant.data.contact[index].geom1), int(plant.data.contact[index].geom2)}
        == {int(plant.bed_geom_id), shank}
        for index in range(plant.data.ncon)
    )


def _active_contact_pairs(plant: Stage5CR12SensorBoundaryPlant) -> list[list[str]]:
    pairs: set[tuple[str, str]] = set()
    for index in range(plant.data.ncon):
        contact = plant.data.contact[index]
        names = []
        for geom_id in (int(contact.geom1), int(contact.geom2)):
            name = mujoco.mj_id2name(
                plant.model, mujoco.mjtObj.mjOBJ_GEOM, geom_id
            )
            names.append(str(name) if name is not None else f"geom_{geom_id}")
        pairs.add(tuple(sorted(names)))
    return [list(pair) for pair in sorted(pairs)]


def _capture_boundary(runtime: dict[str, Any]) -> tuple[Any, Any]:
    wall = runtime.get("wall_session")
    if wall is not None:
        truth, measurement = wall.boundary()
        runtime["last_boundary"] = {"time_s": float(truth.time_s),
            "physics_time_s": float(runtime["plant"].data.time),
            "truth_state_evaluation_only": np.r_[truth.human_q_rad, truth.human_dq_rad_s].copy(),
            "robot_q_rad": truth.robot_q_rad.copy(), "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "measurement": asdict(measurement)}
        return truth, measurement
    lifecycle = runtime.get("plan_lifecycle")
    captured = lifecycle.clock() if lifecycle is not None else None
    truth = runtime["plant"].observe()
    measurement = runtime["measurement_layer"].update(truth)
    if lifecycle is not None:
        if abs(float(measurement.sample_time_s) - float(truth.time_s)) > 1e-10:
            raise RuntimeError("online timing requires the registered zero-latency observation stream")
        lifecycle.capture(measurement.sample_time_s, captured)
        runtime["last_boundary"] = {
            "time_s": float(truth.time_s),
            "truth_state_evaluation_only": np.r_[truth.human_q_rad, truth.human_dq_rad_s].copy(),
            "robot_q_rad": truth.robot_q_rad.copy(), "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "measurement": asdict(measurement),
        }
    return truth, measurement


def synchronize_request_outcomes(runtime):
    lifecycle = runtime.get("plan_lifecycle")
    if lifecycle is None:
        return
    records = lifecycle.records()
    items = [*runtime.get("commissioning_reference_events", []),
             *runtime.get("active_recovery_result", {}).get("planner_decisions", []),
             *runtime.get("task_decisions", [])]
    for item in items:
        request_id = item.get("timing_request_id")
        if request_id is None:
            continue
        record = records[request_id]
        item.update(activation_outcome=record["outcome"],
                    actual_activation_monotonic_ns=record.get("activation_ns"),
                    plan_activated=record.get("activation_ns") is not None,
                    activation_accepted_by_deadline=record["outcome"] == "ACTIVATED",
                    deadline_miss=record["outcome"] in ("EXPIRED", "ACTIVATION_DEADLINE_MISS"),
                    stale=record["outcome"] in ("EXPIRED", "ACTIVATION_DEADLINE_MISS"),
                    plan_age_s=(None if record["activation_age_ms"] is None else record["activation_age_ms"]/1000.),
                    disposition_age_ms=record["disposition_age_ms"], timing_authority="immutable lifecycle")


def observed_planner_physics_overlap(runtime):
    wall = runtime.get("wall_session")
    life = runtime.get("plan_lifecycle")
    if wall is None or life is None:
        return False
    intervals = [(r["worker_start_ns"], r.get("compute_finish_ns", wall.end_ns or wall.clock()))
                 for r in life.records() if r["asynchronous"] and "worker_start_ns" in r]
    return any(row["host_step_start_ns"] < end and row["host_step_finish_ns"] > begin
               for row in wall.native_states for begin, end in intervals)


def persist_runtime_artifacts(output_dir: Path, capture: dict[str, Any]) -> None:
    """All-outcome artifacts, including pre-task exceptions and pending work."""
    runtime = capture.get("runtime")
    if runtime is None:
        return
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    synchronize_request_outcomes(runtime)
    lifecycle = runtime.get("plan_lifecycle")
    records = [] if lifecycle is None else lifecycle.records()
    payload = {
        "schema": "autonomous_recovery_runtime_artifacts_v1",
        "execution_mode": runtime.get("execution_mode", ExecutionMode.REALTIME_CHARACTERIZATION.value),
        "timing_semantics": ("whole_session_wall_physics_v2" if runtime.get("wall_session") is not None else
                             "monotonic_acquisition_to_command; task worker concurrent with physics; "
                             "commissioning/recovery synchronous; no latency replay"
                             if lifecycle is not None else "historical_latency_replay"),
        "requests": records,
        "planner_worker": (None if lifecycle is None else {
            "backend": "spawned_process" if lifecycle.process_worker else "thread",
            "prewarm": lifecycle.prewarm_record}),
        "offline_support_setup": runtime.get("offline_support_setup"),
        "wall_physics": None if runtime.get("wall_session") is None else runtime["wall_session"].record(),
        "execution_attempts": runtime.get("execution_attempts", []),
        "reference_governor_records": runtime.get("reference_governor_records", []),
        "activation_validations": runtime.get("activation_validations", []),
        "future_handoff_bridges": runtime.get("future_handoff_bridges", []),
        "safe_fallback_events": runtime.get("safe_fallback_events", []),
        "rolling_splice_events": runtime.get("rolling_splice_events", []),
        "return_projection_guards": runtime.get("return_projection_guards", []),
        "return_projection_finalization": runtime.get("return_projection_finalization"),
        "return_commit_attempts": runtime.get("return_commit_attempts", []),
        "causal_tracking_request_snapshots": runtime.get("causal_tracking_request_snapshots", []),
        "sample_supported_dwell": (None if runtime.get("sensor_task_clock") is None
                                   else runtime["sensor_task_clock"].evidence),
        "sample_supported_arrival": (None if runtime.get("sensor_task_clock") is None
                                     else runtime["sensor_task_clock"].arrival_evidence),
        "executor_closed": None if lifecycle is None else lifecycle.closed,
        "execution_failure": runtime.get("execution_failure"),
        "exception": capture.get("exception"),
        "finalization_exception": capture.get("finalization_exception"),
        "trace": runtime.get("trace", []),
        "last_boundary": runtime.get("last_boundary"),
        "commissioning_reference_events": runtime.get("commissioning_reference_events", []),
        "commissioning_cuff_reference_origin": runtime.get("commissioning_cuff_reference_origin"),
        "handoff_boundary_verification": runtime.get("handoff_boundary_verification"),
        "active_recovery_result": runtime.get("active_recovery_result"),
        "startup_alignment": runtime.get("startup_alignment_record"),
        "startup_alignment_geometry_checks": runtime.get("startup_alignment_geometry_checks", []),
        "task_decisions": runtime.get("task_decisions", []),
    }
    (output_dir / "runtime_artifacts.json").write_text(
        json.dumps(_jsonable(payload), indent=2, allow_nan=False) + "\n")


def _execute_interval(
    runtime: dict[str, Any],
    *,
    observation: Any,
    interface: Any,
    measurement: Any,
    candidate: HumanWaypointCandidate,
    actuation_enabled: bool,
    mapped_override: Any | None = None,
) -> tuple[Any, dict[str, Any]]:
    plant = runtime["plant"]
    attempt = {"source_sample_time_s": float(observation.sample_timestamp_s),
               "start_physics_s": float(plant.data.time), "native_steps": 0,
               "applied": False, "attempted_reference_q_rad": candidate.q_waypoint_rad.copy()}
    runtime.setdefault("execution_attempts", []).append(attempt)
    runtime["last_execution_attempt"] = attempt
    if runtime.get("plan_to_activate") is not None:
        runtime["plan_lifecycle"].mark_once(runtime["plan_to_activate"], "validation_start_ns")
    contract = runtime["contract"]
    model = runtime["model"]
    transfer = runtime.get("model_transfer")
    mapped = contract.prepare(candidate) if mapped_override is None else mapped_override
    if runtime.get("startup_alignment_active", False) and not runtime.get("alignment_remove_pending"):
        mapped = align_active_startup_reference(runtime, mapped, observation.sample_timestamp_s)
    if mapped.candidate is not candidate:
        raise ValueError("mapped recovery candidate does not match execution candidate")
    preview_context = None

    def preview_transfer_actions(actions: np.ndarray) -> dict[str, np.ndarray]:
        nonlocal preview_context
        if preview_context is None:
            recovery_robot = (mapped.execution_target.robot_cuff_target
                              if candidate.execution_context is WaypointExecutionContext.ACTIVE_RECOVERY
                              else None)
            target = with_explicit_robot_target(
                mapped.execution_target, mapped.reference,
                linear_velocity_world_m_s=(None if recovery_robot is None
                                           else recovery_robot.linear_velocity_world_m_s),
                angular_velocity_world_rad_s=(None if recovery_robot is None
                                              else recovery_robot.angular_velocity_world_rad_s),
            )
            preview_context = build_stage5_loaded_execution_context(
                plant=plant, measurement=measurement, observation=observation,
                interface_state=interface, human_model=model,
                cuff_allocator=runtime["allocator"], target=target,
            )
        preview = preview_context.preview_command_batch(np.asarray(actions, dtype=float))
        return {"force": preview.force_total_n.copy(),
                "moment": preview.moment_total_nm.copy(),
                "torque": preview.joint_torque_command_nm.copy()}

    predecessor = runtime.get("last_command")
    previous_output = (None if predecessor is None else {
        "action": runtime.get("last_executed_generalized_action_nm"),
        "force": predecessor.force_total_n,
        "moment": predecessor.moment_total_nm,
        "torque": predecessor.joint_torque_command_nm,
    })
    clearance_feedback_record = None
    acceleration_request_record = None
    def transform_action(state, acceleration, action, timestamp):
        nonlocal clearance_feedback_record, acceleration_request_record
        if transfer is not None:
            action = transfer.apply(state, acceleration, action, timestamp,
                previous_executed_action_nm=runtime.get("last_executed_generalized_action_nm"),
                previous_action_verified=bool(runtime.get("last_action_executable_verified", False)),
                output_preview=(preview_transfer_actions if transfer.output_envelope is not None else None),
                previous_executed_output=previous_output)
        options = runtime.get("autonomous_recovery_options", {})
        if "requested_acceleration_fraction" in options:
            fraction=float(options["requested_acceleration_fraction"])
            bound=np.asarray(contract.spec.task_joint_acceleration_limit_rad_s2)*fraction
            projected=np.clip(acceleration,-bound,bound)
            correction=(model.inverse_dynamics(state[:2],state[2:],projected)
                        -model.inverse_dynamics(state[:2],state[2:],acceleration))
            acceleration_request_record={"source":"causal estimated-state PD request", "raw_rad_s2":acceleration.copy(),
                "projected_rad_s2":projected.copy(), "internal_bound_rad_s2":bound.copy(),
                "action_correction_nm":correction.copy(), "active":bool(np.any(projected!=acceleration))}
            attempt["acceleration_request_projection"] = acceleration_request_record
            action=action+correction
            acceleration=projected
        incremental_clearance = bool(options.get("incremental_clearance_response", False))
        if incremental_clearance:
            current_motion = runtime["monitor"].latest
            causal_history_ready = (current_motion is not None and current_motion.fast_motion_valid
                and abs(current_motion.sample_timestamp_s-observation.sample_timestamp_s)<=1e-10)
            if causal_history_ready:
                runtime["incremental_clearance_history_initialized"] = True
            elif runtime.get("incremental_clearance_history_initialized",False):
                raise RuntimeError("INCREMENTAL_CLEARANCE_LOST_ALIGNED_CAUSAL_HISTORY")
            else:
                incremental_clearance = False
                attempt["incremental_clearance_initialization"] = {
                    "fallback":"original measured-gap PD-centered correction until first valid causal acceleration history",
                    "source_sample_s":observation.sample_timestamp_s,
                    "synthetic_acceleration_used":False}
        if options.get("clearance_feedback", False) and not incremental_clearance:
            from .clearance_feedback import clearance_acceleration_correction
            correction, clearance_feedback_record = clearance_acceleration_correction(
                model, state, acceleration, interface,
                np.asarray(contract.spec.task_joint_acceleration_limit_rad_s2),
                response_s=float(options.get("clearance_response_s", .04)),
                adverse_acceleration_m_s2=float(options.get("clearance_adverse_acceleration_m_s2", .5)))
            action = action + correction
        task_acceleration_projection = ("incremental_acceleration_fraction" in options
                                       and candidate.execution_context is WaypointExecutionContext.TASK)
        if task_acceleration_projection or incremental_clearance:
            # Local command-response approximation centered on causal measured
            # acceleration. Previous commanded wrench is rebased from its logged
            # source-measured command-reference point to the CURRENT estimated Human point.
            # This cancels constant wrench/model bias but does not model CR12
            # inertia, held-joint-torque geometry change or interface delay.
            sample = runtime["monitor"].latest
            if (sample is None or not sample.fast_motion_valid or
                    abs(sample.sample_timestamp_s-observation.sample_timestamp_s)>1e-10):
                raise RuntimeError("INCREMENTAL_RESPONSE_REQUIRES_ALIGNED_CAUSAL_ACCELERATION")
            preview=preview_transfer_actions(action[None,:])
            human_point=preview_context.actual_human_cuff.world_from_cuff.translation
            previous_offset=runtime["last_command_robot_position_m"]-human_point
            previous_moment=predecessor.moment_total_nm+np.cross(previous_offset,predecessor.force_total_n)
            baseline_force = predecessor.force_total_n
            baseline_record = None
            if options.get('incremental_window_wrench_baseline', False):
                baseline_force, previous_moment, baseline_record = runtime['command_response_history'].average(
                    sample.sample_timestamp_s - sample.fast_alignment_interval_s,
                    sample.sample_timestamp_s, human_point)
            current_moment=preview["moment"][0]+np.cross(preview_context.robot_from_human_world_m,preview["force"][0])
            delta_tau=model.geometry.generalized_input_from_wrench(state[:2],
                preview["force"][0]-baseline_force,current_moment-previous_moment)
            measured_acceleration=sample.fast_motion_acceleration_rad_s2.copy()
            raw=measured_acceleration+np.linalg.solve(model.mass_matrix(state[:2]),delta_tau)
            bound=np.asarray(contract.spec.task_joint_acceleration_limit_rad_s2)*(
                float(options["incremental_acceleration_fraction"]) if task_acceleration_projection else 1.)
            projected=np.clip(raw,-bound,bound) if task_acceleration_projection else raw.copy()
            if incremental_clearance:
                # Same measured gap, gradient, response time, reserve and physical
                # bounds. Change only the response center from the PD request to
                # the aligned causal incremental total-command approximation.
                from .clearance_feedback import clearance_acceleration_correction
                _, clearance_feedback_record = clearance_acceleration_correction(
                    model,state,projected,interface,bound,
                    response_s=float(options.get("clearance_response_s",.04)),
                    adverse_acceleration_m_s2=float(options.get("clearance_adverse_acceleration_m_s2",.5)),
                    protect_conservative_shank=bool(options.get("incremental_conservative_shank",False)))
                projected=np.asarray(clearance_feedback_record["adjusted_acceleration_rad_s2"]).copy()
                clearance_feedback_record["response_center"]="causal_incremental_total_command"
            correction=model.mass_matrix(state[:2])@(projected-raw)
            action=action+correction
            attempt["incremental_acceleration_projection"]={
                "scope":"measured fast acceleration plus nominal incremental command wrench response; not a physical safety certificate",
                "source_sample_s":sample.sample_timestamp_s,"measurement_window_s":sample.fast_alignment_interval_s,
                "consumer":"campaign incremental controller feedback; overrides historical shadow-only consumer classification",
                "previous_command_source_sample_s":runtime["last_command_source_sample_s"],
                "previous_command_receipt_physics_s":runtime["last_command_receipt_physics_s"],
                "previous_receipt_inside_measurement_window":bool(runtime["last_command_receipt_physics_s"]>sample.sample_timestamp_s-sample.fast_alignment_interval_s+1e-12),
                "baseline_scope":"causal measured aggregate response; may mix commands within the 5ms window",
                "window_command_baseline":baseline_record,
                "baseline_command_force_n":baseline_force.copy(),
                "baseline_command_moment_about_current_human_point_nm":previous_moment.copy(),
                "measured_rad_s2":measured_acceleration,"raw_rad_s2":raw,"projected_rad_s2":projected,
                "internal_bound_rad_s2":bound,"action_correction_nm":correction,
                "previous_robot_point_m":runtime["last_command_robot_position_m"].copy(),
                "current_estimated_human_point_m":human_point.copy(),
                "active":bool(np.any(projected!=raw)),"observation_model_version":str(observation.human_model_version),
                "response_model_sequence":runtime.get("model_sequence"),"response_model_beta":model.beta.copy(),
                "response_mass_matrix":model.mass_matrix(state[:2]).copy()}
        if "combined_acceleration_fraction" in options and candidate.execution_context is WaypointExecutionContext.TASK:
            # Quasi-static total commanded cuff wrench, including the existing
            # robot Cartesian feedback. All inputs are current causal estimates
            # and known CR12 command terms; this is not actual/predicted plant truth.
            preview = preview_transfer_actions(action[None,:])
            force, moment = preview["force"][0], preview["moment"][0]
            moment_at_human = moment + np.cross(preview_context.robot_from_human_world_m, force)
            combined_tau = model.geometry.generalized_input_from_wrench(state[:2], force, moment_at_human)
            combined_acceleration = model.continuous_dynamics(state, combined_tau)[2:]
            bound=np.asarray(contract.spec.task_joint_acceleration_limit_rad_s2)*float(options["combined_acceleration_fraction"])
            projected=np.clip(combined_acceleration,-bound,bound)
            correction=(model.inverse_dynamics(state[:2],state[2:],projected)
                        -model.inverse_dynamics(state[:2],state[2:],combined_acceleration))
            action = action + correction
            attempt["combined_acceleration_projection"]={
                "scope":"quasi-static commanded total cuff wrench; excludes robot inertia and interface transient prediction",
                "raw_rad_s2":combined_acceleration.copy(),"projected_rad_s2":projected.copy(),
                "internal_bound_rad_s2":bound.copy(),"action_correction_nm":correction.copy(),
                "active":bool(np.any(projected!=combined_acceleration)),
                "observation_model_version":str(observation.human_model_version),
                "response_model_sequence":runtime.get("model_sequence"),"response_model_beta":model.beta.copy(),
                "scope_gate":"TASK_AFTER_FITTED_HANDOFF"}
            corrected_preview=preview_transfer_actions(action[None,:])
            corrected_force=corrected_preview["force"][0]
            corrected_moment=corrected_preview["moment"][0]+np.cross(preview_context.robot_from_human_world_m,corrected_force)
            corrected_tau=model.geometry.generalized_input_from_wrench(state[:2],corrected_force,corrected_moment)
            corrected_acceleration=model.continuous_dynamics(state,corrected_tau)[2:]
            attempt["combined_acceleration_projection"].update(post_correction_rad_s2=corrected_acceleration.copy(),
                algebraic_residual_rad_s2=(corrected_acceleration-projected).copy())
        if clearance_feedback_record is not None:
            attempt["clearance_feedback"] = clearance_feedback_record
        return action
    command_result = contract.command(
        plant=plant,
        measurement=measurement,
        observation=observation,
        interface_state=interface,
        mapped_waypoint=mapped,
        action_transform=transform_action,
    )
    runtime["supervisor"].bind_loaded_execution(observation, interface, mapped.execution_target)
    decision = runtime["supervisor"].command(
        plant=plant,
        measurement=measurement,
        estimated_state=observation.as_array(),
        human_model=model,
        cuff_allocator=runtime["allocator"],
        track_reference=mapped.reference,
        proposed_action_nm=command_result.generalized_action_nm,
        mpc_status=SAFE_ACTION,
        proposed_filter_result=command_result.filter_result,
    )
    if decision.executable_preview is None:
        runtime["execution_failure"] = {
            "reason": decision.terminate_reason or "NO_EXECUTABLE_COMMAND",
            "sample_timestamp_s": observation.sample_timestamp_s,
            "supervisor": runtime["supervisor"].summary(),
            "decision": {name: getattr(decision, name) for name in (
                "mode", "status", "trigger", "feasible_candidate_count",
                "selected_braking_rate_per_s", "terminate_reason", "safety_filter")},
            "filter": command_result.filter_result.metadata(),
            "proposed_generalized_action_nm": command_result.generalized_action_nm.copy(),
            "clearance_feedback": clearance_feedback_record,
            "candidate": asdict(candidate),
        }
        raise RuntimeError(decision.terminate_reason or "NO_EXECUTABLE_COMMAND")
    command = decision.executable_preview.command
    if "incremental_acceleration_projection" in attempt:
        record = attempt["incremental_acceleration_projection"]
        human_point=preview_context.actual_human_cuff.world_from_cuff.translation
        previous_moment=record['baseline_command_moment_about_current_human_point_nm']
        final_moment=command.moment_total_nm+np.cross(preview_context.robot_from_human_world_m,command.force_total_n)
        final_delta=model.geometry.generalized_input_from_wrench(observation.as_array()[:2],
            command.force_total_n-record['baseline_command_force_n'],final_moment-previous_moment)
        final_prediction=record["measured_rad_s2"]+np.linalg.solve(model.mass_matrix(observation.as_array()[:2]),final_delta)
        record["final_command_prediction_rad_s2"]=final_prediction.copy()
        record["post_filter_box_satisfied"]=bool(np.all(np.abs(final_prediction)<=record["internal_bound_rad_s2"]+1e-8))
        if clearance_feedback_record is not None and runtime.get("autonomous_recovery_options", {}).get("incremental_clearance_response",False):
            gap_prediction=float(np.asarray(clearance_feedback_record["model_gap_gradient_m_rad"])@final_prediction
                                 +clearance_feedback_record["model_curvature_m_s2"])
            clearance_feedback_record["post_filter_predicted_gap_acceleration_m_s2"]=gap_prediction
            clearance_feedback_record["post_filter_gap_constraint_satisfied"]=bool(
                gap_prediction>=clearance_feedback_record["required_gap_acceleration_m_s2"]-1e-8)
            if "conservative_shank" in clearance_feedback_record:
                shank=clearance_feedback_record["conservative_shank"]
                shank_prediction=float(np.asarray(shank["model_gap_gradient_m_rad"])@final_prediction+shank["model_curvature_m_s2"])
                shank["post_filter_predicted_gap_acceleration_m_s2"]=shank_prediction
                shank["post_filter_constraint_satisfied"]=bool(shank_prediction>=shank["required_gap_acceleration_m_s2"]-1e-8)
    if "combined_acceleration_projection" in attempt:
        force=command.force_total_n
        moment=command.moment_total_nm+np.cross(preview_context.robot_from_human_world_m,force)
        tau=model.geometry.generalized_input_from_wrench(observation.as_array()[:2],force,moment)
        attempt["combined_acceleration_projection"].update(
            selected_command_quasistatic_rad_s2=model.continuous_dynamics(observation.as_array(),tau)[2:].copy(),
            selected_supervisor_mode=str(decision.mode),
            selected_torque_unsaturated=bool(np.allclose(command.joint_torque_command_nm,command.unclipped_joint_torque_nm,rtol=0,atol=1e-10)))
    filter_unchanged = bool(
        command_result.filter_result.status == SAFE_UNCHANGED
        and decision.safety_filter is not None
        and decision.safety_filter.get("status") == SAFE_UNCHANGED
    )
    torque_unsaturated = bool(np.allclose(
        command.joint_torque_command_nm, command.unclipped_joint_torque_nm,
        rtol=0, atol=1e-10,
    ))
    activation_request = runtime.get("plan_to_activate")
    wall = runtime.get("wall_session")
    actual_target_pose = mapped.execution_target.robot_cuff_target.world_from_cuff
    actual_target_check = (None if actual_target_pose is None else
                           tool_increment_certificate(actual_target_pose, actual_target_pose, count=2))
    if wall is not None and actual_target_check is not None and not actual_target_check["feasible"]:
        raise RuntimeError("ACTUAL_LOADED_ROBOT_TARGET_GEOMETRY_REJECTED")
    attempt.update(construction_finish_ns=monotonic_ns(), mode=str(decision.mode),
                   actual_loaded_target_geometry=actual_target_check)

    def commit(receipt):
        # Transaction commit at actual command write, before any native step.
        # Preserve the exact selected wrench on every receipt, including the
        # terminal command and successful writes followed by hook exceptions.
        if wall is not None:
            receipt.update(selected_command_force_total_n=command.force_total_n.copy(),
                           selected_command_moment_total_nm=command.moment_total_nm.copy(),
                           command_source_robot_point_m=measurement.attachment_position_m.copy())
        if 'command_response_history' in runtime:
            history = runtime['command_response_history']
            # Physics receipts are episode-local; response history is continuous.
            # Its monotonically increasing identity is separate from the local
            # index used for TRACK ownership in this epoch.
            response_index = (history.rows[-1]['receipt_index'] + 1
                              if history.rows else 0)
            history.record(float(plant.data.time), observation.sample_timestamp_s,
                command.force_total_n, command.moment_total_nm, measurement.attachment_position_m,
                receipt_index=response_index)
            receipt['session_response_receipt_index'] = response_index
        robot_target = mapped.execution_target.robot_cuff_target
        target_pose = robot_target.world_from_cuff
        if target_pose is not None:
            runtime["last_aligned_robot_reference"] = target_pose
            receipt.update(mode=str(decision.mode), robot_target_position_m=target_pose.translation.copy(),
                robot_target_rotation=target_pose.rotation.copy(),
                target_scope="loaded execution target actually used by TRACK or BRAKE preview, held until next receipt",
                robot_target_geometry=actual_target_check)
        attempt.update(applied=True, apply_ns=receipt["apply_ns"],
                       applied_robot_tau_nm=command.joint_torque_command_nm.copy(),
                       generalized_action_nm=np.asarray(decision.action_nm).copy())
        if transfer is not None:
            transfer.note_execution(
                str(decision.mode), command.joint_torque_command_nm,
                actuation_enabled=actuation_enabled,
                filter_unchanged=filter_unchanged,
                torque_unsaturated=torque_unsaturated,
                desired_force_n=command.force_total_n,
                desired_moment_nm=command.moment_total_nm,
            )
        runtime["last_command"] = command
        if ("incremental_acceleration_fraction" in runtime.get("autonomous_recovery_options", {})
                or runtime.get("autonomous_recovery_options", {}).get("incremental_clearance_response",False)):
            runtime["last_command_robot_position_m"] = measurement.attachment_position_m.copy()
            runtime["last_command_source_sample_s"] = float(observation.sample_timestamp_s)
            runtime["last_command_receipt_physics_s"] = float(plant.data.time)
        runtime["last_action_executable_verified"] = bool(
            actuation_enabled and decision.mode == "TRACK" and filter_unchanged and torque_unsaturated)
        runtime["last_executed_generalized_action_nm"] = np.asarray(decision.action_nm, dtype=float).copy()
        history = getattr(contract, "reference_motion_history", None)
        if isinstance(history, AppliedReferenceMotionHistory):
            if decision.mode == "TRACK":
                history.commit_applied(float(plant.data.time), candidate.q_waypoint_rad, candidate.dq_waypoint_rad_s)
            else:
                history.invalidate(float(plant.data.time))
        if decision.mode == "TRACK":
            receipt.update(q_ref_rad=candidate.q_waypoint_rad.copy(), dq_ref_rad_s=candidate.dq_waypoint_rad_s.copy(),
                           reference_effective_physics_s=float(plant.data.time))
            robot_reference = mapped.execution_target.robot_cuff_target
            runtime["last_aligned_robot_reference"] = robot_reference.world_from_cuff
            emitted = runtime.setdefault("emitted_robot_reference_history", [])
            emitted.append({"time_s": float(plant.data.time), "apply_ns": receipt["apply_ns"],
                "source_sample_time_s": float(observation.sample_timestamp_s), "mode": "TRACK",
                "pose": robot_reference.world_from_cuff,
                "twist": np.r_[robot_reference.linear_velocity_world_m_s,
                               robot_reference.angular_velocity_world_rad_s].copy(),
                "q_ref_rad": candidate.q_waypoint_rad.copy()})
            del emitted[:-3]
            hook = runtime.pop("actual_activation_hook", None)
            if hook is not None:
                hook(receipt)
            progress_hook = runtime.pop("reference_progress_commit", None)
            if progress_hook is not None:
                progress_hook(receipt)
            if runtime.get("alignment_remove_pending"):
                runtime["startup_alignment_active"] = False
                runtime["startup_alignment_record"]["removal"] = {
                    **runtime.pop("alignment_remove_pending"), "apply_ns": receipt["apply_ns"],
                    "actual_physics_time_s": float(plant.data.time)}
        else:
            # A brake receipt is retained, but its attempted TRACK pose is not
            # represented as an actually emitted bridge origin.
            runtime.setdefault("emitted_robot_reference_history", []).clear()
            runtime.pop("reference_progress_commit", None)

    prepared_receipt = None
    def apply_actual():
        if wall is not None:
            wall.apply(command, lambda: plant.apply_executable_command(command),
                       source_sample_time_s=observation.sample_timestamp_s, commit=commit, catchup=False,
                       prepared=prepared_receipt)
        else:
            plant.apply_executable_command(command)
            commit({"apply_ns": monotonic_ns()})

    before_steps = float(plant.data.time)
    try:
        if wall is not None:
            # Fixed-ready mode integrates old ctrl to the completed command event
            # once; it does not chase a moving wall clock before defining readiness.
            if not runtime["autonomous_recovery_options"].get("fixed_command_ready", False):
                wall.catch_up("command_construction_and_validation")
            validator = runtime.get("activation_validator")
            if activation_request is not None and validator is not None:
                if runtime.get("validated_request_id") != activation_request.request_id:
                    validation = validator()
                    runtime["activation_validation"] = validation
                    runtime["validated_request_id"] = activation_request.request_id
                    runtime.setdefault("activation_validations", []).append(validation)
                validation = runtime["activation_validation"]
                if not validation["feasible"]:
                    runtime["plan_lifecycle"].finish(activation_request, "REJECTED", "CURRENT_MODEL_ACTIVATION_REVALIDATION")
                    raise RuntimeError("CURRENT_MODEL_ACTIVATION_REVALIDATION")
                if not runtime["autonomous_recovery_options"].get("fixed_command_ready", False):
                    wall.catch_up("activation_certificate_computation")
                if float(plant.data.time) > validation["phase_deadline_physics_s"]-validation["schedule_duration_s"]+1e-12:
                    runtime["plan_lifecycle"].finish(activation_request, "REJECTED", "ACTUAL_REMAINING_PHASE_TIME")
                    raise RuntimeError("ACTUAL_REMAINING_PHASE_TIME")
            splice_guard = runtime.pop("suffix_splice_apply_guard", None)
            if splice_guard is not None and not splice_guard():
                raise RuntimeError("ROLLING_SUFFIX_STALE_AT_APPLY")
        if wall is not None and actuation_enabled:
            if decision.mode == "TRACK":
                attempt["actual_reference_motion_check"] = contract.reference_motion_history.validate_at_apply(
                    candidate.q_waypoint_rad, candidate.dq_waypoint_rad_s, contract.spec.task_joint_acceleration_limit_rad_s2)
            if decision.mode == "TRACK" and runtime["autonomous_recovery_options"].get("receipt_reference_governor", False):
                lo, hi = velocity_box(contract.reference_motion_history, contract.spec.task_joint_acceleration_limit_rad_s2)
                if np.any(candidate.dq_waypoint_rad_s < lo-2e-14) or np.any(candidate.dq_waypoint_rad_s > hi+2e-14):
                    raise RuntimeError("REFERENCE_HOLD_20MS_ACCELERATION_LIMIT")
            prepared_receipt = wall.prepare_apply(command, source_sample_time_s=observation.sample_timestamp_s)
            if decision.mode == "TRACK":
                # The frozen ready/source epochs are untouched. Old-control
                # integration may move the actual 20ms receipt anchor.
                attempt["effective_reference_motion_check"] = contract.reference_motion_history.validate_at_apply(
                    candidate.q_waypoint_rad, candidate.dq_waypoint_rad_s, contract.spec.task_joint_acceleration_limit_rad_s2)
            prepared_receipt.update(validation_model_version=str(observation.human_model_version),
                validation_state=observation.as_array().copy(), validation_reference_q_rad=candidate.q_waypoint_rad.copy(),
                validation_reference_dq_rad_s=candidate.dq_waypoint_rad_s.copy(),
                supervisor_mode=str(decision.mode))
        if actuation_enabled:
            if activation_request is None:
                apply_actual()
            elif decision.mode != "TRACK":
                if runtime["plan_lifecycle"].expired(activation_request):
                    runtime["plan_lifecycle"].finish(activation_request, "EXPIRED", "STALE_PLAN_MAXIMUM_AGE")
                    raise RuntimeError("STALE_PLAN_MAXIMUM_AGE")
                apply_actual()
            else:
                runtime["plan_lifecycle"].activate(activation_request, apply_actual,
                    effective_activation_ns=(None if prepared_receipt is None else prepared_receipt["effective_activation_ns"]),
                    applied_receipt=prepared_receipt)
                runtime.pop("plan_to_activate", None)
                runtime.pop("activation_validator", None)
        else:
            plant.data.ctrl[plant.actuator_ids] = 0.0
            plant.last_joint_torque[:] = 0.0
            if activation_request is not None:
                runtime["plan_lifecycle"].finish(activation_request, "NOT_ACTIVATED", "ACTUATION_DISABLED")
                runtime.pop("plan_to_activate", None)
        if wall is not None:
            wall.next_control_tick()
        else:
            for _ in range(int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))):
                if hasattr(plant, "step_native"):
                    plant.step_native()
                else:
                    plant.step()
                if "true_physics_monitor" in runtime:
                    runtime["true_physics_monitor"].observe(plant)
        if activation_request is not None and decision.mode != "TRACK" and actuation_enabled:
            runtime["plan_lifecycle"].fallback(activation_request,
                float(plant.data.time)-before_steps, str(decision.mode))
    except BaseException as error:
        attempt["exception"] = f"{type(error).__name__}:{error}"
        if prepared_receipt is not None and not prepared_receipt["applied"]:
            prepared_receipt["cancelled_before_write_reason"] = str(error)
        raise
    finally:
        attempt["end_physics_s"] = float(plant.data.time)
        attempt["native_steps"] = int(round((float(plant.data.time)-before_steps)/NOMINAL_PHYSICS_DT_S))
        attempt["actual_duration_s"] = float(plant.data.time)-before_steps
        attempt["last_actual_robot_tau_nm"] = plant.last_joint_torque.copy()
    jacobian = command.robot_attachment_jacobian
    torque_components = {
        "base": command.unclipped_joint_torque_nm - command.wrench_total_world @ jacobian,
        "position": np.r_[command.force_position_n, command.moment_orientation_nm] @ jacobian,
        "velocity": np.r_[command.force_velocity_n, command.moment_angular_velocity_nm] @ jacobian,
        "allocator": np.r_[command.force_allocator_n, command.moment_allocator_nm] @ jacobian,
        "clipping": command.joint_torque_command_nm - command.unclipped_joint_torque_nm,
    }
    return command, {
        "actual_interval_duration_s": attempt["actual_duration_s"],
        "generalized_action_nm": command_result.generalized_action_nm.copy(),
        "clearance_feedback": clearance_feedback_record,
        "acceleration_request_projection": acceleration_request_record,
        "model_transfer": None if transfer is None else transfer.snapshot(),
        "robot_torque_components": torque_components,
        "desired_acceleration_rad_s2": command_result.desired_human_acceleration_rad_s2.copy(),
        "safety_mode": decision.mode,
        "safety_filter": decision.safety_filter,
        "brake": decision.mode == BRAKE,
        "force_gate": bool(
            command.margin_to_force_gate_n <= 0.0
            or (
                decision.safety_filter is not None
                and decision.safety_filter.get("status") == FILTER_INFEASIBLE
            )
        ),
    }


def _geometry_observation(interface: Any) -> tuple[np.ndarray, float]:
    rotation = np.asarray(interface.human_rotation_world, dtype=float)
    phi = math.atan2(float(rotation[2, 0]), float(rotation[0, 0]))
    position = np.asarray(interface.human_position_world_m, dtype=float)[[0, 2]]
    return position, phi


def _fit_and_replay_commissioning(samples: list[dict[str, Any]], rom_human: Stage5HumanParameters = STAGE5_HUMAN) -> tuple[Any, StateResidualBeliefUpdaterV22, list[dict[str, Any]]]:
    geometry_estimator = CausalEffectiveGeometryEstimator()
    for sample in samples:
        geometry_estimator.observe(sample["human_position_world_m"][[0, 2]], sample["phi_rad"])
    fit = geometry_estimator.attempt_fit()
    if not fit.accepted:
        raise RuntimeError(f"geometry_fit_rejected:{fit.reason}")
    updater = StateResidualBeliefUpdaterV22.from_accepted_geometry_fit(fit, rom_human=rom_human)
    model = updater.snapshot().human_model()
    aligned: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    for sample in samples:
        state = model.geometry.estimate_state(
            sample["human_position_world_m"],
            sample["human_rotation_world"],
            sample["human_velocity_world_m_s"],
            sample["human_angular_velocity_world_rad_s"],
        )
        torque = model.geometry.generalized_input_from_wrench(
            state[:2], sample["force_world_n"], sample["moment_world_nm"]
        )
        if last is not None:
            dt = float(sample["time_s"] - last["time_s"])
            if dt > 0.0:
                ddq = (state[2:] - last["state"][2:]) / dt
                beta_before = updater.dynamics.beta.copy()
                residual_before = updater.weights_nm.copy()
                diagnostics = updater.observe_dynamics(
                    q_rad=last["state"][:2],
                    dq_rad_s=last["state"][2:],
                    ddq_rad_s2=ddq,
                    applied_generalized_torque_nm=last["torque"],
                )
                aligned.append({
                    "time_s": sample["time_s"],
                    "ddq_rad_s2": ddq,
                    "beta_before": beta_before,
                    "beta_after": updater.dynamics.beta.copy(),
                    "residual_weights_before_nm": residual_before,
                    "residual_weights_after_nm": updater.weights_nm.copy(),
                    "belief_sequence_after": updater.sequence,
                    "diagnostics": diagnostics,
                })
                model = updater.snapshot().human_model()
        last = {"time_s": sample["time_s"], "state": state, "torque": torque}
    return fit, updater, aligned


def _run_dev_a_active_recovery(
    runtime: dict[str, Any],
    *,
    spec: Any,
    updater: StateResidualBeliefUpdaterV22,
    scheduler: QuinticHumanWaypointSchedulerV1,
    clearance: SessionClearanceContract,
    old_model: StateResidualHumanModel,
    old_robot_cuff_pose: Any,
    commissioning_segment_duration_s: float,
    trace: list[dict[str, Any]],
    simulate_planning_latency: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Bounded measured-feedback recovery before the unchanged task start gate.

    This is a versioned DEV-A execution path.  Commissioning identification is
    already complete; no estimator/update law is run or reset in recovery.
    Timing-aware planning advances the physical plant under the last reference.
    """

    plant = runtime["plant"]
    measurement_layer = runtime["measurement_layer"]
    observer = runtime["observer"]
    contract = runtime["contract"]
    lifecycle = runtime.get("plan_lifecycle")
    options = runtime.get("autonomous_recovery_options", {})
    coordinate_handoff = bool(options.get("fitted_coordinate_handoff", False))
    terminal_selection_enabled = bool(options.get("terminal_set_reference", False))
    target_model = updater.snapshot().human_model()
    belief = updater.snapshot()
    start_q = np.asarray(spec.start_return_target_rad, dtype=float)
    zeros = np.zeros(2)
    if runtime.get("wall_session") is not None:
        runtime["wall_session"].catch_up("active_recovery_phase_entry")
        runtime["wall_session"].set_phase("ACTIVE_RECOVERY", float(spec.phase_timeout_s))
    start_time_s = float(plant.data.time)
    timeout_s = float(spec.phase_timeout_s)
    dwell_s = float(config["settle_persistence_s"])
    minimum_duration_s = float(config["minimum_recovery_segment_duration_s"])
    maximum_age_s = float(config["planning_maximum_age_s"])
    if (not math.isclose(dwell_s, ADAPTATION_DT_S, abs_tol=1e-12)
            or not math.isclose(minimum_duration_s, commissioning_segment_duration_s, abs_tol=1e-12)
            or not math.isclose(maximum_age_s, 0.100, abs_tol=1e-12)):
        raise ValueError("DEV-A recovery config changed an inherited timing contract")
    if "true_physics_monitor" in runtime:
        runtime["true_physics_monitor"].stage = "ACTIVE_RECOVERY"
        runtime["true_physics_monitor"].observe(plant, integrated_step=False)

    prior_support = _candidate("recovery_prior_support", TaskPhase.RETURN,
                               start_q, zeros, spec,
                               WaypointExecutionContext.ACTIVE_RECOVERY)
    new_contract = HumanWaypointMPCShadowContractV1(spec, target_model, runtime["allocator"])
    new_start_pose = new_contract.prepare(prior_support).reference.world_from_cuff
    pose_shift_m = float(np.linalg.norm(
        new_start_pose.translation - old_robot_cuff_pose.translation))
    pose_shift_rad = float(np.linalg.norm(
        Rotation.from_matrix(old_robot_cuff_pose.rotation.T @ new_start_pose.rotation).as_rotvec()))
    truth, measurement = _capture_boundary(runtime)
    observation_new, _ = observer.update(
        measurement, target_model, human_model_version=f"belief_{belief.sequence}"
    )
    start_state = observation_new.as_array().copy()
    start_true = np.concatenate([truth.human_q_rad, truth.human_dq_rad_s])
    needs_recovery = bool(
        not at_goal(spec, start_state[:2], start_state[2:], start_q)
        or pose_shift_m > 1e-12 or pose_shift_rad > 1e-12
    )
    result: dict[str, Any] = {
        "schema": "full3d_dev_a_active_recovery_v1",
        "entered": needs_recovery,
        "succeeded": not needs_recovery,
        "abort_reason": None,
        "start_time_s": start_time_s,
        "end_time_s": start_time_s,
        "duration_s": 0.0,
        "start_estimated_state_rad_rad_s": start_state,
        "start_true_state_evaluation_only_rad_rad_s": start_true,
        "end_estimated_state_rad_rad_s": start_state.copy(),
        "end_true_state_evaluation_only_rad_rad_s": start_true.copy(),
        "old_to_new_robot_cuff_pose_shift_m": pose_shift_m,
        "old_to_new_robot_cuff_rotation_shift_rad": pose_shift_rad,
        "model_sequence": belief.sequence,
        "beta_start": belief.beta.copy(),
        "residual_weights_start_nm": belief.state_residual_weights_nm.copy(),
        "beta_update_count_during_recovery": 0,
        "residual_update_count_during_recovery": 0,
        "segments": [],
        "planner_decisions": [],
        "executed_interval_count": 0,
        "settle_persistence_s": dwell_s,
        "maximum_plan_age_s": maximum_age_s,
        "reference_boundary_q_dq_ddq_continuous": True,
        "reference_boundary_jumps": [],
        "pose_bridge_endpoint_continuity": None,
        "first_new_model_command_delta_norm_nm": None,
        "first_new_model_generalized_action_delta_norm_nm": None,
        "force_integral_n_s": 0.0,
        "peak_force_n": 0.0,
        "peak_moment_nm": 0.0,
        "minimum_session_clearance_m": float("inf"),
        "shank_bed_contact_boundary_count_evaluation_only": 0,
        "active_model_at_end": "fitted_belief" if not needs_recovery else "population_prior",
    }
    runtime["active_recovery_result"] = result
    if not needs_recovery:
        if runtime.get("startup_alignment_active", False):
            runtime["alignment_remove_pending"] = {
                "sample_time_s": float(observation_new.sample_timestamp_s),
                "method": "fitted target already matches actual emitted pose",
                "position_match_m": pose_shift_m, "rotation_match_rad": pose_shift_rad}
        if "model_transfer" in runtime:
            runtime["model_transfer"].offer(
                target_model, version=f"belief_{belief.sequence}", time_s=start_time_s
            )
        return result

    # The old screened controller remains active during the first planning
    # delay.  Only the continuous bridge activates the fitted model.
    runtime["model"] = old_model
    contract.human_model = old_model
    scheduler.human_model = target_model
    mechanics_screen = AdaptiveMechanicsScreenV22()
    active_segment: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
    phase = "CAPTURE"
    model_activated = False
    reference_q = start_state[:2].copy() if coordinate_handoff else start_q.copy()
    old_reference_q = (runtime["emitted_robot_reference_history"][-1]["q_ref_rad"].copy()
                       if coordinate_handoff else start_q.copy())
    result["coordinate_handoff"] = {
        "enabled": coordinate_handoff,
        "old_reference_q_rad": old_reference_q.copy(),
        "new_reference_origin_rad": reference_q.copy(),
        "coordinate_jump_rad": reference_q-old_reference_q,
        "origin_source": "fitted_causal_observation" if coordinate_handoff else "registered_start",
        "emitted_boundary_verification": runtime.get("handoff_boundary_verification"),
        "physical_state_or_history_reset": False,
    }
    recovery_reference_target = start_q.copy()
    if terminal_selection_enabled:
        if runtime.get("autonomous_recovery_options", {}).get("recovery_terminal_center",False):
            from .terminal_reference import select_robust_terminal_reference
            selection = select_robust_terminal_reference(spec=spec,goal=start_q,clearance=clearance,origin=reference_q)
        else:
            selection = select_terminal_reference(spec=spec, goal=start_q, clearance=clearance,
                                                   origin=reference_q)
        result["terminal_reference_selection"] = selection
        if not selection["feasible"]:
            result["abort_reason"] = "ACTIVE_RECOVERY_TERMINAL_REFERENCE_SEARCH_NO_FEASIBLE_POINT_FOUND"
            return result
        recovery_reference_target = np.asarray(selection["reference_target_rad"]).copy()
    reference_dq = zeros.copy()
    reference_ddq = zeros.copy()
    last_desired_pose = old_robot_cuff_pose
    settle_since_s: float | None = None
    last_generalized_action = np.asarray(
        next((row["generalized_action_nm"] for row in reversed(trace)
              if row["stage"] == "COMMISSIONING" and not row.get("terminal_boundary_node", False)),
        np.zeros(2)), dtype=float)
    prior_command_nm = runtime["last_command"].joint_torque_command_nm.copy()
    maximum_steps = int(math.ceil(timeout_s / CONTROL_DT_S))

    for step in range(maximum_steps + 1):
        truth, measurement = _capture_boundary(runtime)
        now_s = float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)
        active_model = target_model if model_activated else old_model
        observation, interface = observer.update(
            measurement, active_model,
            human_model_version=(f"belief_{belief.sequence}" if model_activated
                                 else "population_prior_v1"),
        )
        state = observation.as_array()

        if (active_segment is not None
                and now_s - active_segment["start_time_s"] + 1e-12
                >= active_segment["schedule"].duration_s):
            endpoint = active_segment["schedule"].sample(active_segment["schedule"].duration_s)
            reference_q = endpoint.q_rad.copy()
            reference_dq = endpoint.dq_rad_s.copy()
            reference_ddq = endpoint.ddq_rad_s2.copy()
            if active_segment["kind"] == "CAPTURE":
                # A zero-correction capture already ends at the registered
                # start.  Let the measured-state settle gate decide whether
                # more recovery is needed; do not add a fixed idle segment.
                phase = ("SETTLING" if np.allclose(
                    reference_q, recovery_reference_target, atol=1e-10, rtol=0.0)
                    else "RETURN_TO_START")
            else:
                phase = "SETTLING"
            result["segments"][-1]["actual_end_time_s"] = now_s
            active_segment = None

        if phase == "SETTLING" and active_segment is None and pending is None:
            if at_goal(spec, state[:2], state[2:], start_q):
                settle_since_s = now_s if settle_since_s is None else settle_since_s
                if now_s - settle_since_s + 1e-12 >= dwell_s:
                    result["succeeded"] = True
                    break
            else:
                settle_since_s = None
                phase = "CAPTURE"

        if now_s - start_time_s + 1e-12 >= timeout_s:
            result["abort_reason"] = "ACTIVE_RECOVERY_TIMEOUT"
            break

        if active_segment is None and pending is None and phase in ("CAPTURE", "RETURN_TO_START"):
            if now_s + minimum_duration_s > start_time_s + timeout_s + 1e-12:
                result["abort_reason"] = "ACTIVE_RECOVERY_TIMEOUT"
                break
            # The current measured lag determines a symmetric correction
            # waypoint about the registered start.  Scheduling *toward* the
            # lagging physical state would reward tracking error and can place
            # the reference below the unchanged task-endpoint clearance floor.
            # The emitted reference, not physical q, remains the C2 origin.
            target_observation, target_interface = observer.update(
                measurement, target_model, human_model_version=f"belief_{belief.sequence}"
            )
            timing_request = (None if lifecycle is None else lifecycle.request(
                "ACTIVE_RECOVERY", observation.sample_timestamp_s, asynchronous=False))
            if timing_request is not None:
                lifecycle.mark(timing_request, "worker_start_ns")
            planning_started = perf_counter()
            attempts: list[dict[str, Any]] = []
            selected: tuple[Any, Any, Any, Any] | None = None
            # The full symmetric correction is the first choice.  If that
            # lies outside the *unchanged* task/ROM/clearance/mechanics set,
            # contract toward the registered start.  Every rejection is
            # visible; no physical/safety check is removed or softened.
            fractions = (1.0, 0.5, 0.25, 0.125, 0.0) if phase == "CAPTURE" else (0.0,)
            for fraction in fractions:
                target_q = (recovery_reference_target + fraction *
                            (recovery_reference_target - target_observation.as_array()[:2])
                            if phase == "CAPTURE" else recovery_reference_target.copy())
                label = f"recovery_{phase.lower()}_{len(result['segments']):02d}_f{fraction:g}"
                planned_candidate = _candidate(
                    label, TaskPhase.RETURN, target_q, zeros, spec,
                    WaypointExecutionContext.ACTIVE_RECOVERY,
                )
                attempt = {
                    "label": label, "correction_fraction": fraction,
                    "target_q_rad": target_q.copy(),
                    "origin_clearance_m": float(clearance.evaluate(reference_q)),
                    "target_clearance_m": float(clearance.evaluate(target_q)),
                }
                try:
                    shortest = scheduler.plan_reference_contract(
                        current_q_hat_rad=reference_q,
                        current_dq_hat_rad_s=reference_dq,
                        candidate=planned_candidate,
                        phase_elapsed_s=0.0,
                    )
                    planned_duration_s = max(shortest.duration_s, minimum_duration_s)
                    schedule = scheduler.plan_fixed_duration_reference_contract(
                        current_q_hat_rad=reference_q,
                        current_dq_hat_rad_s=reference_dq,
                        candidate=planned_candidate,
                        duration_s=planned_duration_s,
                        phase_elapsed_s=0.0,
                    )
                    screen = mechanics_screen.evaluate(belief, planned_candidate, schedule)
                    if not screen["feasible"]:
                        raise ValueError(str(screen["rejection_reason"]))
                    if now_s + schedule.duration_s > start_time_s + timeout_s + 1e-12:
                        raise ValueError("recovery segment exceeds registered phase timeout")
                    bridge = None
                    if phase == "CAPTURE" and not model_activated:
                        terminal_pose = new_contract.prepare(planned_candidate).reference.world_from_cuff
                        bridge = RobotCuffPoseBridge(
                            old_robot_cuff_pose, terminal_pose, schedule.duration_s
                        )
                        if coordinate_handoff or runtime.get("startup_alignment") is not None:
                            bridge_screen = screen_cartesian_bridge(bridge, schedule, clearance.envelope)
                            attempt["cartesian_bridge_geometry"] = bridge_screen
                            if not bridge_screen["feasible"]:
                                raise ValueError("CARTESIAN_BRIDGE_GEOMETRY_SCREEN_REJECTED")
                            origin_candidate = _candidate(label+"_activation_preview", TaskPhase.RETURN,
                                reference_q, reference_dq, spec, WaypointExecutionContext.ACTIVE_RECOVERY)
                            origin_mapped = mapped_with_bridge(new_contract.prepare(origin_candidate),
                                origin_candidate, reference_q, reference_dq, reference_ddq, bridge, 0.0)
                            preview_context = build_stage5_loaded_execution_context(
                                plant=plant, measurement=measurement, observation=target_observation,
                                interface_state=target_interface, human_model=target_model,
                                cuff_allocator=runtime["allocator"], target=origin_mapped.execution_target)
                            estimated = target_observation.as_array()
                            acceleration = (new_contract.position_gain*(reference_q-estimated[:2])
                                            + new_contract.velocity_gain*(reference_dq-estimated[2:]))
                            action = target_model.inverse_dynamics(estimated[:2], estimated[2:], acceleration)
                            preview = preview_context.preview_command_batch(action[None, :])
                            initial_preview = {
                                "scope": "current measured activation boundary only; every subsequent interval retains supervisor",
                                "force_n": float(np.linalg.norm(preview.force_total_n[0])),
                                "moment_nm": float(np.linalg.norm(preview.moment_total_nm[0])),
                                "torque_fraction": float(np.max(np.abs(preview.unclipped_joint_torque_nm[0])/plant.torque_limits_nm)),
                            }
                            initial_preview["feasible"] = (initial_preview["force_n"] <= 200.0
                                and initial_preview["moment_nm"] <= 60.0 and initial_preview["torque_fraction"] <= 1.0)
                            attempt["activation_boundary_execution_preview"] = initial_preview
                            if not initial_preview["feasible"]:
                                raise ValueError("CARTESIAN_BRIDGE_ACTIVATION_PREVIEW_REJECTED")
                    attempt["feasible"] = True
                    attempts.append(attempt)
                    selected = (planned_candidate, schedule, screen, bridge)
                    break
                except (ValueError, RuntimeError) as error:
                    attempt["feasible"] = False
                    attempt["reason"] = f"{type(error).__name__}:{error}"
                    attempts.append(attempt)
            planning_ms = 1000.0 * (perf_counter() - planning_started)
            if timing_request is not None:
                lifecycle.mark(timing_request, "compute_finish_ns")
            if selected is None:
                if timing_request is not None:
                    lifecycle.finish(timing_request, "FAILED", "ACTIVE_RECOVERY_NO_FEASIBLE_SEGMENT")
                result["planner_decisions"].append({
                    "request_time_s": now_s, "runtime_ms": planning_ms,
                    "candidate_attempts": attempts, "selected": None,
                })
                result["abort_reason"] = "ACTIVE_RECOVERY_NO_FEASIBLE_SEGMENT"
                break
            planned_candidate, schedule, screen, bridge = selected
            delay_steps = (int(math.ceil(planning_ms / (1000.0 * CONTROL_DT_S)))
                           if simulate_planning_latency and lifecycle is None else 0)
            plan_age_s = delay_steps * CONTROL_DT_S
            pending = {
                "timing_request": timing_request,
                "kind": phase, "candidate": planned_candidate, "schedule": schedule,
                "bridge": bridge, "request_time_s": now_s,
                "planning_runtime_ms": planning_ms,
                "plan_age_s": plan_age_s,
                "remaining_wait_steps": min(delay_steps, int(round(maximum_age_s / CONTROL_DT_S))),
                "deadline_miss": plan_age_s > maximum_age_s + 1e-12,
                "screen": screen,
            }
            result["planner_decisions"].append({
                "timing_request_id": None if timing_request is None else timing_request.request_id,
                "label": label, "request_time_s": now_s,
                "request_measurement_time_s": observation.sample_timestamp_s,
                "runtime_ms": planning_ms, "plan_age_s": plan_age_s,
                "stale": pending["deadline_miss"],
                "candidate_attempts": attempts,
                "mechanics_screen": screen,
            })

        if pending is not None and pending["remaining_wait_steps"] == 0:
            if pending["deadline_miss"]:
                result["abort_reason"] = "ACTIVE_RECOVERY_STALE_PLAN_MAXIMUM_AGE"
                break
            boundary = pending["schedule"].sample(0.0)
            jumps = {
                "q_rad": (boundary.q_rad - reference_q).copy(),
                "dq_rad_s": (boundary.dq_rad_s - reference_dq).copy(),
                "ddq_rad_s2": (boundary.ddq_rad_s2 - reference_ddq).copy(),
            }
            result["reference_boundary_jumps"].append(jumps)
            if any(np.max(np.abs(value)) > 1e-10 for value in jumps.values()):
                result["reference_boundary_q_dq_ddq_continuous"] = False
                result["abort_reason"] = "ACTIVE_RECOVERY_REFERENCE_DISCONTINUITY"
                break
            if not model_activated:
                prior_command_nm = runtime["last_command"].joint_torque_command_nm.copy()
                model_activated = True
                if runtime.get("startup_alignment_active", False):
                    runtime["alignment_remove_pending"] = {
                        "sample_time_s": float(observation.sample_timestamp_s),
                        "method": "continuous actual-emitted-pose to fitted unshifted model bridge",
                        "coordinate_handoff_enabled": coordinate_handoff}
                runtime["model"] = target_model
                contract.human_model = target_model
                if "model_transfer" in runtime:
                    runtime["model_transfer"].offer(
                        target_model, version=f"belief_{belief.sequence}", time_s=now_s
                    )
                observation, interface = observer.update(
                    measurement, target_model,
                    human_model_version=f"belief_{belief.sequence}",
                )
                state = observation.as_array()
            active_segment = {
                **pending,
                "start_time_s": now_s,
            }
            result["segments"].append({
                "label": pending["candidate"].label,
                "kind": pending["kind"],
                "start_time_s": now_s,
                "duration_s": pending["schedule"].duration_s,
                "origin_reference_q_rad": reference_q.copy(),
                "target_q_rad": pending["candidate"].q_waypoint_rad.copy(),
                "bridge_endpoint_jumps": (
                    None if pending["bridge"] is None
                    else pending["bridge"].endpoint_jumps()
                ),
            })
            if pending["bridge"] is not None:
                result["pose_bridge_endpoint_continuity"] = pending["bridge"].endpoint_jumps()
            if pending.get("timing_request") is not None:
                runtime["plan_to_activate"] = pending["timing_request"]
                runtime["activation_validator"] = lambda: validate_activation(
                    belief=belief, request_sequence=belief.sequence, schedule=active_segment["schedule"],
                    clearance=clearance, phase=TaskPhase.RETURN, request_phase=TaskPhase.RETURN,
                    remaining_s=start_time_s+timeout_s-float(plant.data.time),
                    reference_state=np.r_[reference_q, reference_dq], now_physics_s=float(plant.data.time))
                def on_recovery_activation(receipt):
                    active_segment["start_time_s"] = float(plant.data.time)
                    result["segments"][-1]["start_time_s"] = float(plant.data.time)
                runtime["actual_activation_hook"] = on_recovery_activation
            pending = None

        if active_segment is not None:
            elapsed = min(now_s - active_segment["start_time_s"],
                          active_segment["schedule"].duration_s)
            sample = active_segment["schedule"].sample(max(0.0, elapsed))
            reference_q = sample.q_rad.copy()
            reference_dq = sample.dq_rad_s.copy()
            reference_ddq = sample.ddq_rad_s2.copy()
            subphase = active_segment["kind"]
        else:
            subphase = "PLANNING_WAIT" if pending is not None else "SETTLING"

        split = runtime["monitor"].update(
            sample_timestamp_s=observation.sample_timestamp_s,
            estimated_dq_rad_s=state[2:],
            cuff_force_world_n=interface.measured_force_world_n,
            cuff_moment_world_nm=interface.measured_moment_world_nm,
            interface_translation_human_m=interface.displacement_human_m,
            interface_velocity_human_m_s=interface.velocity_human_m_s,
            interface_rotation_human_rad=interface.rotation_error_human_rad,
            interface_angular_velocity_human_rad_s=interface.angular_velocity_human_rad_s,
            command_wrench_world=runtime["last_command"].wrench_total_world,
            robot_joint_torque_command_nm=runtime["last_command"].joint_torque_command_nm,
        )
        authority = runtime["authority"].evaluate(split)
        reason = authority.abort_reason if authority.violation else None
        if reason is None:
            reason = task_limit_violation(
                spec, state[:2], state[2:],
                split.human_motion_acceleration_rad_s2,
                acceleration_authority_valid=split.human_motion_valid,
            )
        force_norm = float(np.linalg.norm(interface.measured_force_world_n))
        moment_norm = float(np.linalg.norm(interface.measured_moment_world_nm))
        if reason is None and force_norm > float(config["cuff_force_limit_n"]) + 1e-9:
            reason = "REALIZED_CUFF_FORCE_LIMIT"
        if reason is None and moment_norm > float(config["cuff_moment_limit_nm"]) + 1e-9:
            reason = "REALIZED_CUFF_MOMENT_LIMIT"
        if reason is None and np.any(np.abs(measurement.robot_dq_rad_s)
                                     > CR12_VELOCITY_LIMITS_RAD_S + 1e-9):
            reason = "CR12_VELOCITY_LIMIT"
        robot_bounds = plant.model.jnt_range[plant.robot_joint_ids]
        if reason is None and np.any((measurement.robot_q_rad < robot_bounds[:, 0] - 1e-9)
                                     | (measurement.robot_q_rad > robot_bounds[:, 1] + 1e-9)):
            reason = "CR12_POSITION_LIMIT"
        session_clearance = float(clearance.evaluate(state[:2]))
        if reason is None and session_clearance < -1e-9:
            reason = "SESSION_CLEARANCE_LIMIT"

        candidate = _candidate(f"recovery_execute_{step:05d}", TaskPhase.RETURN,
                               old_reference_q if coordinate_handoff and not model_activated else reference_q,
                               reference_dq, spec,
                               WaypointExecutionContext.ACTIVE_RECOVERY if model_activated
                               else WaypointExecutionContext.COMMISSIONING)
        try:
            mapped = contract.prepare(candidate)
            if active_segment is not None and active_segment["bridge"] is not None:
                mapped = mapped_with_bridge(
                    mapped, candidate, reference_q, reference_dq, reference_ddq,
                    active_segment["bridge"], elapsed,
                )
            desired = mapped.reference.world_from_cuff
            desired_twist = np.r_[
                mapped.execution_target.robot_cuff_target.linear_velocity_world_m_s,
                mapped.execution_target.robot_cuff_target.angular_velocity_world_rad_s,
            ]
        except (ValueError, RuntimeError) as error:
            result["abort_reason"] = f"ACTIVE_RECOVERY_MAPPING:{error}"
            break

        row = {
            "stage": "ACTIVE_RECOVERY", "task_phase": "ACTIVE_RECOVERY",
            "recovery_subphase": subphase, "time_s": float(truth.time_s),
            "source_sample_time_s": float(observation.sample_timestamp_s),
            "control_boundary_physics_s": now_s,
            "reference_proposal_physics_s": now_s,
            "physics_steps": int(round(float(truth.time_s) / NOMINAL_PHYSICS_DT_S)),
            "q_ref_rad": reference_q.copy(), "dq_ref_rad_s": reference_dq.copy(),
            "ddq_ref_rad_s2": reference_ddq.copy(),
            "estimated_state": state.copy(),
            "truth_state": np.concatenate([truth.human_q_rad, truth.human_dq_rad_s]),
            "robot_q_rad": truth.robot_q_rad.copy(),
            "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "robot_tau_nm": runtime["last_command"].joint_torque_command_nm.copy(),
            "cuff_position_world_m": measurement.attachment_position_m.copy(),
            "cuff_rotation_world": measurement.attachment_rotation_matrix.copy(),
            "cuff_linear_velocity_world_m_s": measurement.attachment_velocity_m_s.copy(),
            "cuff_angular_velocity_world_rad_s": measurement.attachment_angular_velocity_rad_s.copy(),
            "cuff_force_world_n": interface.measured_force_world_n.copy(),
            "cuff_moment_world_nm": interface.measured_moment_world_nm.copy(),
            "desired_cuff_position_world_m": desired.translation.copy(),
            "desired_cuff_rotation_world": desired.rotation.copy(),
            "desired_cuff_twist_world": desired_twist.copy(),
            "belief_sequence": belief.sequence if model_activated else -1,
            "model_version": observation.human_model_version,
            "selected_schedule_label": (
                active_segment["candidate"].label if active_segment is not None else subphase
            ),
            "shank_clearance_session_m": (
                clearance.shank_contract.evaluate(state[:2])
                if isinstance(clearance, CombinedRigidTableClearanceV1)
                else session_clearance),
            "dev_d_envelope_clearance_m": (
                session_clearance if isinstance(clearance, CombinedRigidTableClearanceV1)
                else float("nan")),
            "shank_bed_contact_evaluation_only": _shank_bed_contact(plant),
            "active_contact_pairs_evaluation_only": _active_contact_pairs(plant),
            "actual_acceleration_rad_s2": split.human_motion_acceleration_rad_s2.copy(),
            "actual_acceleration_valid": split.human_motion_valid,
            "acceleration_violation": authority.violation,
            "interval_force_cost_n_s": 0.0 if reason is not None else force_norm * CONTROL_DT_S,
            "terminal_boundary_node": reason is not None,
        }
        if reason is not None:
            row["applied_robot_tau_nm"] = np.zeros(6)
            row["generalized_action_nm"] = np.zeros(2)
            trace.append(row)
            result["abort_reason"] = reason
            break
        try:
            command, execution = _execute_interval(
                runtime, observation=observation, interface=interface,
                measurement=measurement, candidate=candidate,
                actuation_enabled=True, mapped_override=mapped,
            )
        except (RuntimeError, ValueError) as error:
            result["abort_reason"] = f"ACTIVE_RECOVERY_LOW_LEVEL_EXECUTION:{error}"
            row.update(runtime.get("last_execution_attempt", {}))
            row["terminal_boundary_node"] = True
            trace.append(row)
            break
        if model_activated and result["first_new_model_command_delta_norm_nm"] is None:
            result["first_new_model_command_delta_norm_nm"] = float(np.linalg.norm(
                command.joint_torque_command_nm - prior_command_nm
            ))
            result["first_new_model_generalized_action_delta_norm_nm"] = float(np.linalg.norm(
                execution["generalized_action_nm"] - last_generalized_action
            ))
        row["applied_robot_tau_nm"] = command.joint_torque_command_nm.copy()
        row["allocated_wrench_world"] = command.wrench_total_world.copy()
        row["generalized_action_nm"] = execution["generalized_action_nm"].copy()
        row["model_transfer"] = execution["model_transfer"]
        row["robot_torque_components"] = execution["robot_torque_components"]
        row["safety_mode"] = str(execution["safety_mode"])
        trace.append(row)
        result["executed_interval_count"] += 1
        result["force_integral_n_s"] += force_norm * CONTROL_DT_S
        result["peak_force_n"] = max(result["peak_force_n"], force_norm)
        result["peak_moment_nm"] = max(result["peak_moment_nm"], moment_norm)
        result["minimum_session_clearance_m"] = min(
            result["minimum_session_clearance_m"], session_clearance
        )
        result["shank_bed_contact_boundary_count_evaluation_only"] += int(
            row["shank_bed_contact_evaluation_only"]
        )
        last_desired_pose = desired
        if pending is not None:
            pending["remaining_wait_steps"] -= 1

    truth, measurement = _capture_boundary(runtime)
    if not model_activated:
        runtime["model"] = target_model
        contract.human_model = target_model
    final_observation, _ = observer.update(
        measurement, target_model, human_model_version=f"belief_{belief.sequence}"
    )
    result["end_time_s"] = float(truth.time_s)
    result["duration_s"] = result["end_time_s"] - start_time_s
    result["end_estimated_state_rad_rad_s"] = final_observation.as_array().copy()
    result["end_true_state_evaluation_only_rad_rad_s"] = np.concatenate(
        [truth.human_q_rad, truth.human_dq_rad_s]
    )
    result["beta_end"] = updater.dynamics.beta.copy()
    result["residual_weights_end_nm"] = updater.weights_nm.copy()
    result["active_model_at_end"] = "fitted_belief"
    result["reference_end_q_rad"] = reference_q.copy()
    result["reference_end_dq_rad_s"] = reference_dq.copy()
    result["reference_end_ddq_rad_s2"] = reference_ddq.copy()
    result["desired_cuff_end_position_world_m"] = last_desired_pose.translation.copy()
    if not result["succeeded"] and result["abort_reason"] is None:
        result["abort_reason"] = "ACTIVE_RECOVERY_TIMEOUT"
    return result


def advance_inter_rep_boundary(session_context: dict[str, Any], *,
                               max_wait_s: float = 2.0,
                               stop_check: Any = None) -> dict[str, Any]:
    """Advance one continuous plant through explicit settle and hold states."""
    previous = session_context["runtime"]
    wall = previous["wall_session"]
    lifecycle = previous["plan_lifecycle"]
    if wall.active or lifecycle._outstanding is not None:
        raise RuntimeError("INTER_REP_PREVIOUS_EPISODE_OPEN")
    plant = previous["plant"]
    spec = session_context["spec"]
    config = session_context["config"]
    model = session_context["updater"].snapshot().human_model()
    geometry = model.geometry
    shank = SessionClearanceContract(geometry)
    clearance = CombinedRigidTableClearanceV1(
        shank, RigidTableReferenceEnvelopeV1(geometry),
        use_monotonic_certificate=bool(previous["autonomous_recovery_options"].get(
            "monotonic_clearance_certificate", False)))
    terminal_time = float(plant.data.time)
    terminal_qpos = plant.data.qpos.copy()
    terminal_qvel = plant.data.qvel.copy()
    trace = previous["trace"]
    last_reference = previous["contract"].reference_motion_history.last_reference()
    reference_settled = (last_reference is not None
        and np.allclose(last_reference[1], 0., atol=1e-10, rtol=0.)
        and np.allclose(trace[-1]["ddq_ref_rad_s2"], 0., atol=1e-10, rtol=0.))
    limit_steps = int(round(max_wait_s / CONTROL_DT_S))
    if limit_steps < 1:
        raise ValueError("inter-repetition maximum wait must cover one control interval")
    records = []
    phase = "INTER_REP_SETTLE"
    settle_intervals = hold_intervals = 0

    def sample():
        truth = plant.observe()
        measurement = previous["measurement_layer"].current
        if abs(float(measurement.sample_time_s)-float(truth.time_s)) > 1e-10:
            measurement = previous["measurement_layer"].update(truth)
        observation, interface = previous["observer"].update(
            measurement, model, human_model_version=f"belief_{session_context['updater'].sequence}")
        state = observation.as_array()
        try:
            start_episode(spec, state[:2], state[2:], acceleration_authority_valid=False)
            start_set = True
        except ValueError:
            start_set = False
        force = interface.measured_force_world_n.copy()
        moment = interface.measured_moment_world_nm.copy()
        clearance_m = float(clearance.evaluate(state[:2]))
        valid = bool(start_set and reference_settled
            and np.linalg.norm(force) <= float(config["cuff_force_limit_n"])+1e-9
            and np.linalg.norm(moment) <= float(config["cuff_moment_limit_nm"])+1e-9
            and clearance_m >= -1e-9
            and np.all(np.abs(measurement.robot_dq_rad_s) <= CR12_VELOCITY_LIMITS_RAD_S+1e-9))
        return {"state": phase, "time_s": float(truth.time_s),
            "human_q_rad_evaluation_only": truth.human_q_rad.copy(),
            "human_dq_rad_s_evaluation_only": truth.human_dq_rad_s.copy(),
            "cr12_q_rad_evaluation_only": truth.robot_q_rad.copy(),
            "cr12_dq_rad_s_evaluation_only": truth.robot_dq_rad_s.copy(),
            "force_world_n": force, "moment_world_nm": moment,
            "clearance_m": clearance_m, "start_set": start_set,
            "reference_settled": reference_settled, "gate": valid}

    records.append(sample())
    for _ in range(limit_steps):
        if phase == "INTER_REP_SETTLE" and records[-1]["gate"]:
            phase = "INTER_REP_HOLD"
        if stop_check is not None:
            stop_check()
        for _native in range(int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))):
            plant.step_native()
        previous["measurement_layer"].update(plant.observe())
        if phase == "INTER_REP_SETTLE":
            settle_intervals += 1
        else:
            hold_intervals += 1
        records.append(sample())
        if phase == "INTER_REP_HOLD":
            if records[-1]["gate"]:
                break
            phase = "INTER_REP_SETTLE"
    else:
        raise RuntimeError("INTER_REP_SETTLE_TIMEOUT")
    costs = integrate_measured_wrench(
        np.asarray([r["time_s"] for r in records]),
        np.asarray([r["force_world_n"] for r in records]),
        np.asarray([r["moment_world_nm"] for r in records]))
    result = {"schema": "inter_rep_boundary_v1", "status": "SETTLED_HELD",
        "from_repetition": session_context["repetition_index"],
        "to_repetition": session_context["repetition_index"]+1,
        "start_time_s": terminal_time, "end_time_s": float(plant.data.time),
        "settle_duration_s": settle_intervals*CONTROL_DT_S,
        "hold_duration_s": hold_intervals*CONTROL_DT_S,
        "cost": costs, "samples": records,
        "terminal_native_qpos_evaluation_only": terminal_qpos,
        "terminal_native_qvel_evaluation_only": terminal_qvel,
        "settled_native_qpos_evaluation_only": plant.data.qpos.copy(),
        "settled_native_qvel_evaluation_only": plant.data.qvel.copy(),
        "physical_object_unchanged": plant is previous["plant"],
        "updater_sequence": session_context["updater"].sequence}
    session_context["end_time_s"] = float(plant.data.time)
    session_context["final_belief"] = session_context["updater"].snapshot()
    session_context["last_boundary"] = result
    return result


def _bootstrap_fresh_track_reference(runtime: dict[str, Any], spec: Any,
                                     start_q: np.ndarray) -> dict[str, Any]:
    """Apply a new-epoch TRACK hold and prove its ownership before planning."""
    wall = runtime["wall_session"]
    sample = runtime["measurement_layer"].current
    observation, interface = runtime["observer"].update(
        sample, runtime["model"],
        human_model_version=f"belief_{runtime['model_sequence']}")
    before = float(runtime["plant"].data.time)
    force = interface.measured_force_world_n.copy()
    moment = interface.measured_moment_world_nm.copy()
    # The fresh split monitor needs two genuinely acquired 5 ms samples.
    # Keep the prior physical command during this reseed interval; it is a
    # boundary HOLD cost, never a new-episode TRACK receipt.
    wall.next_control_tick()
    sample = runtime["measurement_layer"].current
    observation, interface = runtime["observer"].update(
        sample, runtime["model"],
        human_model_version=f"belief_{runtime['model_sequence']}")
    warmup_end = float(runtime["plant"].data.time)
    warmup_force = interface.measured_force_world_n.copy()
    warmup_moment = interface.measured_moment_world_nm.copy()
    motion = runtime["monitor"].latest
    if (motion is None or not motion.fast_motion_valid
            or abs(motion.sample_timestamp_s-observation.sample_timestamp_s)>1e-10):
        raise RuntimeError("INTER_REP_CAUSAL_ACCELERATION_RESEED_FAILED")
    candidate = _candidate("fresh_episode_track_hold", TaskPhase.OUTBOUND,
                           start_q, np.zeros(2), spec)
    _command, execution = _execute_interval(
        runtime, observation=observation, interface=interface, measurement=sample,
        candidate=candidate, actuation_enabled=True)
    receipt = wall.applied_commands[wall.active_receipt_index]
    if receipt.get("mode") != "TRACK" or not receipt.get("applied"):
        raise RuntimeError("FRESH_EPISODE_TRACK_BOOTSTRAP_FAILED")
    source = runtime["measurement_layer"].current.sample_time_s
    ownership = receipt_reference_at_sample(wall.applied_commands, source)
    if ownership["receipt_index"] != wall.active_receipt_index:
        raise RuntimeError("FRESH_EPISODE_RECEIPT_OWNERSHIP_INVALID")
    end_truth = runtime["plant"].observe()
    end_measurement = runtime["measurement_layer"].current
    _end_observation, end_interface = runtime["observer"].update(
        end_measurement, runtime["model"],
        human_model_version=f"belief_{runtime['model_sequence']}")
    costs = integrate_measured_wrench(
        np.asarray([before, warmup_end, float(end_truth.time_s)]),
        np.asarray([force, warmup_force, end_interface.measured_force_world_n]),
        np.asarray([moment, warmup_moment, end_interface.measured_moment_world_nm]))
    return {"receipt_index": wall.active_receipt_index,
            "source_sample_time_s": float(source),
            "receipt_source_sample_time_s": float(receipt["source_sample_time_s"]),
            "reference": ownership, "execution_mode": str(execution["safety_mode"]),
            "start_time_s": before, "warmup_end_time_s": warmup_end,
            "end_time_s": float(end_truth.time_s),
            "cost": costs}


def _resume_session_runtime(session_context: dict[str, Any], spec: Any) -> dict[str, Any]:
    """Start a new task runtime around only the contracted persistent state."""
    previous = session_context["runtime"]
    prior_wall = previous.get("wall_session")
    prior_lifecycle = previous.get("plan_lifecycle")
    if prior_wall is None or prior_wall.active or (
            prior_lifecycle is not None and prior_lifecycle._outstanding is not None):
        raise RuntimeError("previous repetition not fully finalized")
    runtime = carryover_runtime_fields(previous)
    if set(runtime).intersection(FORBIDDEN_TRANSIENT_FIELDS):
        raise RuntimeError("transient state crossed repetition boundary")
    plant = runtime["plant"]
    if not math.isclose(float(plant.data.time), session_context["end_time_s"],
                        abs_tol=1.0e-12, rel_tol=0.0):
        raise RuntimeError("continuous plant time changed between repetitions")
    runtime["model"] = session_context["updater"].snapshot().human_model()
    runtime["model_sequence"] = session_context["updater"].sequence
    runtime["contract"] = HumanWaypointMPCShadowContractV1(
        spec, runtime["model"], runtime["allocator"])
    runtime["supervisor"] = Stage5LoadedTrackBrakeSupervisor()
    runtime["monitor"] = SplitAccelerationMonitorV1()
    runtime["authority"] = HumanMotionAccelerationAuthorityV1(
        spec.task_joint_acceleration_limit_rad_s2)
    runtime["offline_support_setup"] = {
        "scope": "previous repetition terminal command carried into next epoch",
        "source_sample_time_s": runtime["last_command_source_sample_s"],
        "receipt_index": 0}
    return runtime


def _start_applied_reference_history(runtime: dict[str, Any], start_q: np.ndarray,
                                     resumed: bool) -> AppliedReferenceMotionHistory:
    plant = runtime["plant"]
    if resumed:
        initial_q, initial_dq = start_q.copy(), np.zeros(2)
    else:
        initial_q, initial_dq = runtime["contract"].reference_motion_history.last_reference()[:2]
    return AppliedReferenceMotionHistory(
        lambda: float(plant.data.time), initial_q, initial_dq, float(plant.data.time))


def _start_scientific_session_epoch(runtime: dict[str, Any], output_dir: Path,
                                    runtime_capture: dict[str, Any] | None,
                                    host_delay_s: float, start_q: np.ndarray,
                                    resumed: bool) -> ScientificPlanLifecycle:
    plant = runtime["plant"]
    session = ScientificPhysicsSession(
        runtime, stop_check=(None if runtime_capture is None
                             else runtime_capture.get("stop_check")))
    runtime["wall_session"] = session

    def simulation_version():
        return SimulationVersion(
            episode_epoch=str(output_dir.resolve()),
            state_version=session.steps + len(session.samples),
            physics_step=session.steps,
            sim_time_s=float(plant.data.time),
            phase_version=len(session.phase_records)-1+int(runtime.get("task_phase_version", 0)),
            human_model_version=str(runtime.get("model_sequence", "population_prior_v1")),
            reference_version=str(len(session.applied_commands)))

    lifecycle = ScientificPlanLifecycle(
        session, version_provider=simulation_version,
        process_worker=bool(runtime["autonomous_recovery_options"].get(
            "planner_process_worker", False)),
        host_delay_s=host_delay_s)
    runtime["plan_lifecycle"] = lifecycle
    # The first epoch creates the measurement layer. Later epochs keep its
    # filter/RNG/delivery history and merely acquire a fresh boundary sample.
    session.capture(initial=not resumed)
    runtime["contract"].reference_motion_history = _start_applied_reference_history(
        runtime, start_q, resumed)
    return lifecycle


def _run_executed_case(
    output_dir: Path,
    *,
    actuation_enabled: bool = True,
    task_timeout_s: float = 30.0,
    simulate_planning_latency: bool = False,
    qualification_case: dict[str, Any] | None = None,
    qualification_arm: str = "continual_adaptive",
    formal_qualification: bool = False,
    qualification_contract: str | None = None,
    dev_a_recovery: bool = False,
    dev_c_bumpless_transfer: bool = False,
    dev_d_rigid_table_reference: bool = False,
    autonomous_recovery_options: dict[str, Any] | None = None,
    runtime_capture: dict[str, Any] | None = None,
    execution_mode: str = ExecutionMode.REALTIME_CHARACTERIZATION.value,
    scientific_host_delay_s: float = 0.0,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run physical commissioning and one event-driven OUTBOUND/HOLD/RETURN task."""

    output_dir = Path(output_dir)
    recovery_options = dict(autonomous_recovery_options or {})
    mode = ExecutionMode(execution_mode)
    scientific = mode is ExecutionMode.SCIENTIFIC_SIMULATION
    if scientific and not (recovery_options.get("whole_session_wall_physics")
                           and recovery_options.get("monotonic_async_planning")):
        raise ValueError("scientific mode requires the registered async worker and physical session")
    if not scientific and scientific_host_delay_s:
        raise ValueError("host delay injection is scientific-mode only")
    resumed = session_context is not None and "updater" in session_context
    if session_context is not None and not scientific:
        raise ValueError("continuous session requires SCIENTIFIC_SIMULATION")
    validate_recovery_options(recovery_options)
    if recovery_options and not dev_d_rigid_table_reference:
        raise ValueError("autonomous recovery options require the rigid-table closed-loop path")
    if not math.isfinite(task_timeout_s) or task_timeout_s <= 0.0:
        raise ValueError("task_timeout_s must be finite and positive")
    timeout_intervals = task_timeout_s / CONTROL_DT_S
    if not math.isclose(timeout_intervals, round(timeout_intervals), abs_tol=1.0e-10):
        raise ValueError("task_timeout_s must be an integer multiple of the 5 ms execution period")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = Path(__file__).resolve().parents[3] / "configs" / "full3d_adaptive_integration_v1" / "development_v1_1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    transfer_config = None
    if dev_c_bumpless_transfer:
        transfer_path = (Path(__file__).resolve().parents[3] / "configs"
                         / "full3d_adaptive_integration_v1" / "dev_c_bumpless_transfer_v3.json")
        transfer_config = json.loads(transfer_path.read_text(encoding="utf-8"))
        if (transfer_config["schema"] != "dev_c_bumpless_transfer_v3"
                or transfer_config["control_dt_s"] != CONTROL_DT_S
                or transfer_config["value_hook"] != 0.0
                or transfer_config["stale_plan_threshold_s"] != 0.100):
            raise ValueError("DEV-C transfer config changed a registered control contract")
    if qualification_arm not in {"continual_adaptive", "commissioning_only", "fixed_population"}:
        raise ValueError("unknown frozen full3d arm")
    if qualification_case is None and qualification_arm != "continual_adaptive":
        raise ValueError("baseline arm requires an explicit qualification case")
    campaign_qualification = qualification_contract == "autonomous_closed_loop_recovery_v1_fresh48_v1"
    if qualification_contract is not None and not campaign_qualification:
        raise ValueError("unknown qualification contract")
    if campaign_qualification and not (
            formal_qualification and qualification_case is not None and dev_a_recovery
            and dev_d_rigid_table_reference and not dev_c_bumpless_transfer
            and simulate_planning_latency and actuation_enabled and task_timeout_s == 30.0
            and qualification_arm == "continual_adaptive"
            and all(recovery_options.get(k) is True for k in (
                "whole_session_wall_physics", "monotonic_async_planning", "planner_process_worker",
                "fixed_command_ready", "receipt_reference_governor"))):
        raise ValueError("campaign qualification requires its frozen actual closed-loop timing/reference path")
    if formal_qualification and qualification_case is None:
        raise ValueError("formal qualification requires a registered physical case")
    if formal_qualification and dev_a_recovery and not campaign_qualification:
        raise ValueError("DEV-A recovery cases are development evidence, not fresh qualification")
    if formal_qualification and dev_c_bumpless_transfer:
        raise ValueError("DEV-C transfer is development-only pending a new formal preregistration")
    if dev_a_recovery and not simulate_planning_latency:
        raise ValueError("DEV-A requires timing-aware physical planning-delay replay")
    if dev_d_rigid_table_reference and ((formal_qualification and not campaign_qualification) or not dev_a_recovery
                                         or dev_c_bumpless_transfer
                                         or not simulate_planning_latency):
        raise ValueError("DEV-D reference is development-only with DEV-A on, DEV-C off and timing replay")
    physical_human = physical_geometry = None
    control_human = STAGE5_HUMAN
    if qualification_case is not None and qualification_case.get("research_model") == "high_rom_v1":
        control_human = high_rom_deployable_prior()
        config["human_hard_rom_deg"] = [[0.0, 125.0], [0.0, 125.0]]
        config["research_model_config_path"] = str(high_rom_config_path)
    if qualification_case is None:
        spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
        custom_commissioning = None
    else:
        from ..fresh_qualification_v1.scenario import hidden_plant
        physical_human, physical_geometry, spec, custom_commissioning = hidden_plant(qualification_case)
    start_q = np.asarray(spec.start_return_target_rad, dtype=float)
    if resumed:
        runtime = _resume_session_runtime(session_context, spec)
        plant = runtime["plant"]
    else:
        runtime = _initialize_loaded_runtime("full3d_adaptive_v1", start_q, spec=spec,
            physical_human=physical_human,physical_geometry=physical_geometry,
            control_human=control_human,
            startup_execution_pose_alignment=recovery_options.get("startup_execution_pose_alignment", False),
            exact_cached_plant=recovery_options.get("exact_cached_plant", False))
        plant = runtime["plant"]
    runtime["execution_mode"] = mode.value
    runtime["autonomous_recovery_options"] = recovery_options
    if recovery_options.get('incremental_window_wrench_baseline', False) and not resumed:
        from .command_response_history import CommandResponseHistory
        history = CommandResponseHistory()
        history.record(float(plant.data.time), runtime['last_command_source_sample_s'],
            runtime['last_command'].force_total_n, runtime['last_command'].moment_total_nm,
            runtime['last_command_robot_position_m'], receipt_index=0)
        runtime['command_response_history'] = history
    if runtime_capture is not None:
        runtime_capture["runtime"] = runtime
    online_timing = bool(recovery_options.get("monotonic_async_planning", False))
    lifecycle = (PlanLifecycle(process_worker=bool(recovery_options.get("planner_process_worker", False)))
                 if online_timing and not scientific else None)
    if lifecycle is not None:
        runtime["plan_lifecycle"] = lifecycle
    if scientific:
        lifecycle = _start_scientific_session_epoch(
            runtime, output_dir, runtime_capture, scientific_host_delay_s,
            start_q, resumed)
        if resumed:
            runtime["fresh_track_bootstrap"] = _bootstrap_fresh_track_reference(
                runtime, spec, start_q)
    elif recovery_options.get("whole_session_wall_physics", False):
        if not online_timing:
            raise ValueError("whole_session_wall_physics requires monotonic_async_planning")
        runtime["wall_session"] = WallPhysicsSession(runtime, stop_check=(
            None if runtime_capture is None else runtime_capture.get("stop_check")))
        runtime["wall_session"].capture(initial=True)
        runtime["contract"].reference_motion_history = _start_applied_reference_history(
            runtime, start_q, resumed)
    measurement_layer = runtime["measurement_layer"]
    observer = runtime["observer"]
    if qualification_case is not None:
        from .fast_physics_monitor import FastTruePhysicsMonitor
        runtime["true_physics_monitor"] = FastTruePhysicsMonitor()

    commissioning_waypoints = (
        np.radians(np.asarray(config["commissioning_reference"]["waypoints_deg"], dtype=float))
        if custom_commissioning is None else custom_commissioning
    )
    if qualification_case is not None and not resumed:
        # The first 20 ms must hold the causally reconstructed state that was
        # committed by initial support, not a hidden physical start angle.
        # Subsequent/terminal commissioning targets remain the registered path.
        commissioning_waypoints = commissioning_waypoints.copy()
        commissioning_waypoints[0] = runtime["initial_support_state"][:2]
    prescribed_commissioning_waypoints = commissioning_waypoints.copy()
    commissioning_reference_events: list[dict[str, Any]] = []
    commissioning_planned_segments: set[int] = set()
    commissioning_pending_wait_steps = 0
    commissioning_pending_stale = False
    commissioning_delay_elapsed_s = 0.0
    commissioning_envelope: RigidTableReferenceEnvelopeV1 | None = None
    segment_duration = float(config["commissioning_reference"]["segment_duration_s"])
    settle_duration = float(config["commissioning_reference"]["settle_duration_s"])
    history_warmup_s = ADAPTATION_DT_S
    commissioning_duration = (
        history_warmup_s
        + segment_duration * (len(commissioning_waypoints) - 1)
        + settle_duration
    )
    commissioning_samples: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    runtime["trace"] = trace
    runtime["commissioning_reference_events"] = commissioning_reference_events
    next_identification_time = 0.0
    commissioning_steps = -1 if resumed else int(round(commissioning_duration / CONTROL_DT_S))
    def dev_d_abort_record(reason: str, truth: Any, observation: Any,
                           interface: Any, **details: Any) -> None:
        """Persist the causal boundary plus separately labeled oracle state."""
        record = {
            "reason": reason, "time_s": float(truth.time_s),
            "estimated_state": observation.as_array().copy(),
            "truth_state_evaluation_only": np.concatenate(
                [truth.human_q_rad, truth.human_dq_rad_s]),
            "measured_cuff_position_world_m": interface.human_position_world_m.copy(),
            "measured_cuff_rotation_world": interface.human_rotation_world.copy(),
            "robot_q_rad": truth.robot_q_rad.copy(),
            "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "last_robot_command_nm": runtime["last_command"].joint_torque_command_nm.copy(),
            "reference_events": commissioning_reference_events,
            **details,
        }
        (output_dir / "dev_d_reference_abort.json").write_text(
            json.dumps(_jsonable(record), indent=2, allow_nan=False) + "\n")
    step = 0
    while step <= commissioning_steps:
        truth, measurement = _capture_boundary(runtime)
        observation, interface = observer.update(
            measurement, runtime["model"], human_model_version="population_prior_v1"
        )
        if dev_d_rigid_table_reference:
            observed_sleeve_gap = RigidTableReferenceEnvelopeV1(
                runtime["model"].geometry).measured_sleeve_gap(
                    interface.human_position_world_m, interface.human_rotation_world)
            if observed_sleeve_gap < -1e-9:
                reason = "COMMISSIONING_MEASURED_SLEEVE_PENETRATION"
                dev_d_abort_record(reason, truth, observation, interface,
                                   measured_sleeve_gap_m=observed_sleeve_gap)
                raise RuntimeError(reason)
        elapsed = (float(plant.data.time) if runtime.get("wall_session") is not None else step * CONTROL_DT_S)
        motion_elapsed = max(0.0, elapsed - history_warmup_s
                             - commissioning_delay_elapsed_s)
        segment = min(
            int(motion_elapsed // segment_duration),
            len(commissioning_waypoints) - 2,
        )
        local = motion_elapsed - segment * segment_duration
        if dev_d_rigid_table_reference and commissioning_pending_stale \
                and commissioning_pending_wait_steps == 0:
            reason = "COMMISSIONING_STALE_PLAN_MAXIMUM_AGE"
            dev_d_abort_record(reason, truth, observation, interface)
            raise RuntimeError(reason)
        if (dev_d_rigid_table_reference and elapsed + 1e-12 >= history_warmup_s
                and motion_elapsed < segment_duration * (len(commissioning_waypoints) - 1) - 1e-12
                and segment not in commissioning_planned_segments):
            if commissioning_envelope is None:
                # One causal interface pose does not identify hip/knee geometry.
                # The optional constant offset aligns only the tool-reference
                # center; all limb geometry and structural bounds stay intact.
                commissioning_envelope = RigidTableReferenceEnvelopeV1(
                    runtime["model"].geometry)
                if recovery_options.get("commissioning_cuff_reference_origin", False):
                    commissioning_envelope = commissioning_envelope.with_causal_cuff_reference_origin(
                        observation.as_array()[:2], interface.human_position_world_m,
                        state_sample_time_s=float(observation.sample_timestamp_s),
                        interface_sample_time_s=float(interface.sample_timestamp_s),
                        current_time_s=float(plant.data.time))
                    runtime["commissioning_cuff_reference_origin"] = {
                        "source": "existing causal interface observer pose and aligned prior q estimate",
                        "source_sample_time_s": float(observation.sample_timestamp_s),
                        "q_hat_rad": observation.as_array()[:2].copy(),
                        "cuff_position_world_m": interface.human_position_world_m.copy(),
                        "translation_world_m": commissioning_envelope.cuff_reference_translation_world_m,
                        "anatomical_geometry_identified": False,
                        "limb_geometry_changed": False,
                        "scope": "constant commissioning sleeve/bar/adapter reference center offset only; fitted recovery constructs a fresh zero-offset envelope",
                    }
            envelope = commissioning_envelope
            measured_sleeve_gap_m = envelope.measured_sleeve_gap(
                interface.human_position_world_m, interface.human_rotation_world)
            timing_request = (None if lifecycle is None else lifecycle.request(
                "COMMISSIONING", observation.sample_timestamp_s, asynchronous=False))
            if timing_request is not None:
                lifecycle.mark(timing_request, "worker_start_ns")
            planning_started = perf_counter()
            commissioning_terminal_selection = None
            prescribed_next = prescribed_commissioning_waypoints[segment + 1]
            if (recovery_options.get("commissioning_terminal_center",False)
                    and segment == len(commissioning_waypoints)-2):
                from .terminal_reference import select_robust_terminal_reference
                commissioning_clearance = CombinedRigidTableClearanceV1(
                    SessionClearanceContract(runtime["model"].geometry),envelope,
                    use_monotonic_certificate=bool(recovery_options.get("monotonic_clearance_certificate",False)))
                commissioning_terminal_selection = select_robust_terminal_reference(
                    spec=spec,goal=np.asarray(prescribed_next),clearance=commissioning_clearance,
                    origin=np.asarray(commissioning_waypoints[segment]))
                if commissioning_terminal_selection["feasible"]:
                    prescribed_next=commissioning_terminal_selection["reference_target_rad"]
            selection = choose_feedback_commissioning_target(
                envelope=envelope,
                reference_origin_q_rad=commissioning_waypoints[segment],
                estimated_current_q_rad=observation.as_array()[:2],
                prescribed_previous_q_rad=prescribed_commissioning_waypoints[segment],
                prescribed_next_q_rad=prescribed_next,
                q_bounds_rad=spec.q_bounds_rad,
                velocity_limits_rad_s=spec.task_joint_velocity_limit_rad_s,
                acceleration_limits_rad_s2=spec.task_joint_acceleration_limit_rad_s2,
                duration_s=segment_duration,
                final_return=segment == len(commissioning_waypoints) - 2,
            )
            if commissioning_terminal_selection is not None and selection["feasible"]:
                # The legacy selector may move its input during hip-lift search.
                # Recheck the actual endpoint, not merely the proposed center.
                final_target=np.asarray(selection["target_q_rad"])
                delta=final_target-np.asarray(commissioning_waypoints[segment])
                unit_coefficients=delta[:,None]*np.array([0.,0.,0.,10.,-15.,6.])
                unit_coefficients[:,0]=commissioning_waypoints[segment]
                final_lower=float(commissioning_clearance.certified_minimum(unit_coefficients,1.))
                box_ok=in_original_terminal_box(spec,final_target,np.asarray(prescribed_commissioning_waypoints[segment+1]))
                verification={"inside_original_return_box":box_ok,"combined_continuous_lower_m":final_lower,
                    "floor_m":commissioning_terminal_selection["floor_m"],"actual_final_target_rad":final_target.copy()}
                commissioning_terminal_selection["actual_selected_endpoint_verification"]=verification
                if not box_ok or final_lower<commissioning_terminal_selection["floor_m"]:
                    selection["feasible"]=False
                    selection["attempts"].append({"feasible":False,"reason":"FINAL_COMMISSIONING_CENTER_CERTIFICATE_FAILED",**verification})
            planning_ms = 1000.0 * (perf_counter() - planning_started)
            if timing_request is not None:
                lifecycle.mark(timing_request, "compute_finish_ns")
            event = {"timing_request_id": None if timing_request is None else timing_request.request_id,
                     "segment_index": segment, "request_time_s": float(truth.time_s),
                     "measurement_time_s": float(observation.sample_timestamp_s),
                     "runtime_ms": planning_ms,
                     "measured_sleeve_gap_m": measured_sleeve_gap_m,
                     "selected": bool(selection["feasible"]),
                     "attempts": selection["attempts"]}
            if commissioning_terminal_selection is not None:
                event["commissioning_terminal_center"] = commissioning_terminal_selection
            if selection["feasible"]:
                event["target_q_rad"] = selection["target_q_rad"].copy()
                event["selected_fraction"] = selection["selected_fraction"]
                event["hip_lift_rad"] = selection["hip_lift_rad"]
                event["minimum_path_m"] = selection["path"]["conservative_continuous_lower_m"]
                event["conservative_nonworsening_shank_escape"] = bool(
                    selection["path"].get("conservative_nonworsening_shank_escape", False))
            commissioning_reference_events.append(event)
            if measured_sleeve_gap_m < -1e-9 or not selection["feasible"]:
                reason = ("COMMISSIONING_MEASURED_SLEEVE_PENETRATION"
                          if measured_sleeve_gap_m < -1e-9 else
                          "COMMISSIONING_NO_RIGID_TABLE_FEASIBLE_SEGMENT")
                dev_d_abort_record(reason, truth, observation, interface,
                                   measured_sleeve_gap_m=measured_sleeve_gap_m,
                                   active_reference_origin_q_rad=commissioning_waypoints[segment].copy())
                raise RuntimeError(reason)
            commissioning_waypoints[segment + 1] = selection["target_q_rad"]
            commissioning_planned_segments.add(segment)
            requested_wait = int(math.ceil(planning_ms / (1000.0 * CONTROL_DT_S)))
            commissioning_pending_stale = False if online_timing else planning_ms > 100.0 + 1e-9
            commissioning_pending_wait_steps = 0 if online_timing else min(max(1, requested_wait), 20)
            if timing_request is not None:
                runtime["plan_to_activate"] = timing_request
                if runtime.get("wall_session") is not None:
                    # Segment starts at its emitted rest boundary, not the old
                    # sample time. Waiting consumes physical commissioning time.
                    local = 0.0
                    def on_commissioning_activation(receipt):
                        nonlocal commissioning_delay_elapsed_s, commissioning_duration, commissioning_steps
                        nominal_start = history_warmup_s+segment*segment_duration+commissioning_delay_elapsed_s
                        delay = max(0., float(plant.data.time)-nominal_start)
                        commissioning_delay_elapsed_s += delay
                        commissioning_duration += delay
                        commissioning_steps += int(math.ceil(delay/CONTROL_DT_S))
                        event["actual_segment_start_physics_s"] = float(plant.data.time)
                    runtime["actual_activation_hook"] = on_commissioning_activation
            event["replayed_pending_physical_steps"] = commissioning_pending_wait_steps
            event["deadline_miss"] = commissioning_pending_stale
            commissioning_steps += commissioning_pending_wait_steps
        if dev_d_rigid_table_reference and commissioning_pending_wait_steps > 0:
            q_ref, dq_ref, ddq_ref = (
                commissioning_waypoints[segment], np.zeros(2), np.zeros(2))
        elif elapsed < history_warmup_s:
            q_ref, dq_ref, ddq_ref = (
                commissioning_waypoints[0],
                np.zeros(2),
                np.zeros(2),
            )
        elif motion_elapsed >= segment_duration * (len(commissioning_waypoints) - 1):
            q_ref, dq_ref, ddq_ref = commissioning_waypoints[-1], np.zeros(2), np.zeros(2)
        else:
            q_ref, dq_ref, ddq_ref = _quintic_reference(
                commissioning_waypoints[segment], commissioning_waypoints[segment + 1], local, segment_duration
            )
        phase = TaskPhase.RETURN if segment == len(commissioning_waypoints) - 2 else TaskPhase.OUTBOUND
        position, phi = _geometry_observation(interface)
        if elapsed + 1.0e-12 >= next_identification_time:
            commissioning_samples.append({
                "time_s": float(truth.time_s),
                "human_position_world_m": interface.human_position_world_m.copy(),
                "human_rotation_world": interface.human_rotation_world.copy(),
                "human_velocity_world_m_s": interface.human_velocity_world_m_s.copy(),
                "human_angular_velocity_world_rad_s": interface.human_angular_velocity_world_rad_s.copy(),
                "phi_rad": phi,
                "force_world_n": interface.measured_force_world_n.copy(),
                "moment_world_nm": interface.measured_moment_world_nm.copy(),
            })
            next_identification_time += ADAPTATION_DT_S
        trace.append({
            "stage": "COMMISSIONING",
            "time_s": float(truth.time_s),
            "physics_steps": int(round(truth.time_s / NOMINAL_PHYSICS_DT_S)),
            "q_ref_rad": q_ref.copy(),
            "dq_ref_rad_s": dq_ref.copy(),
            "ddq_ref_rad_s2": ddq_ref.copy(),
            "estimated_state": observation.as_array().copy(),
            "truth_state": np.concatenate([truth.human_q_rad, truth.human_dq_rad_s]),
            "robot_q_rad": truth.robot_q_rad.copy(),
            "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "robot_tau_nm": runtime["last_command"].joint_torque_command_nm.copy(),
            "cuff_position_world_m": measurement.attachment_position_m.copy(),
            "cuff_rotation_world": measurement.attachment_rotation_matrix.copy(),
            "cuff_linear_velocity_world_m_s": measurement.attachment_velocity_m_s.copy(),
            "cuff_angular_velocity_world_rad_s": measurement.attachment_angular_velocity_rad_s.copy(),
            "cuff_force_world_n": interface.measured_force_world_n.copy(),
            "cuff_moment_world_nm": interface.measured_moment_world_nm.copy(),
            "belief_sequence": -1,
            "task_phase": "COMMISSIONING",
            "shank_bed_contact_evaluation_only": _shank_bed_contact(plant),
            "active_contact_pairs_evaluation_only": _active_contact_pairs(plant),
            "terminal_boundary_node": (elapsed >= commissioning_duration if runtime.get("wall_session") is not None else step == commissioning_steps),
            "dev_d_measured_sleeve_gap_m": (
                RigidTableReferenceEnvelopeV1(runtime["model"].geometry).measured_sleeve_gap(
                    interface.human_position_world_m, interface.human_rotation_world)
                if dev_d_rigid_table_reference else float("nan")),
        })
        if (elapsed >= commissioning_duration if runtime.get("wall_session") is not None else step == commissioning_steps):
            trace[-1]["applied_robot_tau_nm"] = np.zeros(6)
            trace[-1]["generalized_action_nm"] = np.zeros(2)
            break
        candidate = _candidate(f"commissioning_{step:05d}", phase, q_ref, dq_ref, spec,
                               WaypointExecutionContext.COMMISSIONING)
        command, execution = _execute_interval(
            runtime,
            observation=observation,
            interface=interface,
            measurement=measurement,
            candidate=candidate,
            # Commissioning always uses the physical CR12 chain.  The bounded
            # no-actuation diagnostic disables only task actuation so it shares
            # the same causally acquired commissioning belief.
            actuation_enabled=True,
        )
        trace[-1]["applied_robot_tau_nm"] = command.joint_torque_command_nm.copy()
        trace[-1]["allocated_wrench_world"] = command.wrench_total_world.copy()
        trace[-1]["generalized_action_nm"] = execution["generalized_action_nm"]
        if dev_d_rigid_table_reference and commissioning_pending_wait_steps > 0:
            commissioning_pending_wait_steps -= 1
            commissioning_delay_elapsed_s += CONTROL_DT_S
        step += 1

    commissioning_duration = (0.0 if resumed else
        float(plant.data.time) if runtime.get("wall_session") is not None
        else commissioning_steps * CONTROL_DT_S)

    old_commissioning_model = runtime["model"]
    if transfer_config is not None:
        runtime["model_transfer"] = BumplessHumanActionTransfer(
            old_commissioning_model, initial_version="population_prior_v1",
            duration_s=float(transfer_config["transfer_duration_s"]),
            small_direct_action_change_nm=float(transfer_config["small_direct_action_change_nm"]),
            duration_policy=transfer_config["duration_policy"],
            output_envelope=transfer_config["output_envelope"],
        )
    old_commissioning_pose = None
    if dev_a_recovery and not resumed and (recovery_options.get("fitted_coordinate_handoff", False)
                           or recovery_options.get("startup_execution_pose_alignment", False)):
        continuity = stationary_emitted_boundary(
            trace, runtime.get("emitted_robot_reference_history", []), settle_duration)
        runtime["handoff_boundary_verification"] = continuity
        if not continuity["stationary_verified"]:
            raise RuntimeError("HANDOFF_EMITTED_REFERENCE_NOT_STATIONARY")
        old_commissioning_pose = runtime["emitted_robot_reference_history"][-1]["pose"]
    elif dev_a_recovery and not resumed:
        terminal_support = _candidate(
            "commissioning_terminal_support", TaskPhase.RETURN,
            start_q, np.zeros(2), spec, WaypointExecutionContext.COMMISSIONING,
        )
        old_commissioning_pose = runtime["contract"].prepare(
            terminal_support).reference.world_from_cuff

    if resumed:
        fit = session_context["fit"]
        updater = session_context["updater"]
        commissioning_updates = []
    elif qualification_arm == "fixed_population":
        # Commissioning is still physically executed; the fixed arm deliberately
        # never fits the commissioned observations.  A rejected geometry fit
        # must not selectively turn this structurally fixed arm into a crash.
        fit = None
        commissioning_updates = []
        updater = StateResidualBeliefUpdaterV22(nominal_control_geometry(), rom_human=control_human)
    else:
        fit, updater, commissioning_updates = _fit_and_replay_commissioning(commissioning_samples, control_human)
    if runtime.get("wall_session") is not None:
        runtime["wall_session"].catch_up("commissioning_fit_and_replay")
    belief = updater.snapshot()
    if qualification_arm == "fixed_population":
        belief = replace(belief, geometry_source="FIXED_NOMINAL",
                         dynamics_source="FIXED_NOMINAL", residual_source="FIXED_NOMINAL")
    commissioning_handoff_belief = belief
    runtime["model"] = belief.human_model()
    runtime["model_sequence"] = belief.sequence
    runtime["contract"].human_model = runtime["model"]
    if transfer_config is not None and not dev_a_recovery:
        runtime["model_transfer"].offer(
            runtime["model"], version=f"belief_{belief.sequence}",
            time_s=float(plant.observe().time_s),
        )
    shank_clearance = SessionClearanceContract(runtime["model"].geometry,
        geometry_source=("FIXED_NOMINAL_HIP_AND_THIGH_PLUS_STRUCTURAL_PRIOR_SHANK_LENGTH_SET"
                         if qualification_arm == "fixed_population"
                         else "ONLINE_EFFECTIVE_HIP_AND_THIGH_PLUS_STRUCTURAL_PRIOR_SHANK_LENGTH_SET"))
    clearance = (CombinedRigidTableClearanceV1(
        shank_clearance, RigidTableReferenceEnvelopeV1(runtime["model"].geometry),
        use_monotonic_certificate=bool(recovery_options.get("monotonic_clearance_certificate", False)))
        if dev_d_rigid_table_reference else shank_clearance)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec,
        runtime["model"],
        reference_period_s=CONTROL_DT_S,
        clearance_evaluator=(clearance if dev_d_rigid_table_reference
                             else clearance.evaluate),
        clearance_source=("DEV_D_CAUSAL_EFFECTIVE_RIGID_TABLE_ENVELOPE"
                          if dev_d_rigid_table_reference else
                          "FIXED_NOMINAL_GEOMETRY_CONSERVATIVE_SHANK_SET"
                          if qualification_arm == "fixed_population" else
                          "ONLINE_EFFECTIVE_GEOMETRY_CONSERVATIVE_SHANK_SET"),
        preserve_task_endpoint_clearance_floor=True,
        require_continuous_nonpenetrating_path=dev_d_rigid_table_reference,
        use_duration_lower_bound=bool(recovery_options.get("duration_lower_bound", False)),
        reference_velocity_fraction=(recovery_options.get("reference_velocity_fraction", .6)
                                     if recovery_options.get("reference_pacing", False) else 1.0),
        reference_acceleration_fraction=(recovery_options.get("reference_acceleration_fraction", .5)
                                         if recovery_options.get("reference_pacing", False) else 1.0),
    )
    planner_type = (TerminalSetHumanWaypointPlannerV1
                    if recovery_options.get("terminal_set_reference", False)
                    else HumanWaypointFeedbackMPCV1)
    candidate_mode = (qualification_case or {}).get("coordination_candidate")
    if (qualification_case or {}).get("research_model") == "high_rom_v1":
        if candidate_mode == "high_rom_hip_leading_feedback_v1":
            directions = ((1.0, 0.5), (1.0, 0.75), (1.0, 1.0))
        elif candidate_mode in (None, "high_rom_sync_feedback_v1",
                                "synchronous_diagnostic_only_feedback_replanning_active"):
            directions = HumanWaypointFeedbackMPCConfigV1().normalized_coordination_directions
        else:
            raise ValueError("unknown High-ROM coordination candidate")
    else:
        directions = HumanWaypointFeedbackMPCConfigV1().normalized_coordination_directions
    planner = planner_type(
        spec,
        scheduler,
        HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True,
            normalized_coordination_directions=directions),
    )
    planner.robust_terminal_center = bool(recovery_options.get("robust_terminal_center", False))
    planner.robust_hold_reference = bool(recovery_options.get("robust_hold_reference", False))
    planner.causal_tracking_offset_clearance = bool(recovery_options.get("causal_tracking_offset_clearance", False))
    # This branch's High-ROM development candidate keeps the existing q lattice
    # and cost, but allows intermediate waypoints to be passed with bounded dq.
    smooth_waypoint_mode = (qualification_case or {}).get("research_model") == "high_rom_v1"
    planner.pass_through_waypoints = smooth_waypoint_mode
    planner.safe_fallback_enabled = bool(smooth_waypoint_mode and online_timing)
    adaptive_planner = AdaptiveHumanWaypointHWMPCV22(planner)

    recovery_result = None
    if dev_a_recovery:
        recovery_config_path = (Path(__file__).resolve().parents[3] / "configs"
                                / "full3d_adaptive_integration_v1" / "dev_a_recovery_v1.json")
        recovery_config = json.loads(recovery_config_path.read_text(encoding="utf-8"))
        if recovery_config["schema"] != "full3d_dev_a_recovery_v1" or recovery_config["value_hook"] != 0.0:
            raise ValueError("unexpected DEV-A recovery config")
        if not resumed:
            assert old_commissioning_pose is not None
            recovery_result = _run_dev_a_active_recovery(
                runtime, spec=spec, updater=updater, scheduler=scheduler,
                clearance=clearance, old_model=old_commissioning_model,
                old_robot_cuff_pose=old_commissioning_pose,
                commissioning_segment_duration_s=segment_duration,
                trace=trace, simulate_planning_latency=simulate_planning_latency,
                config={**config, **recovery_config},
            )

    truth, measurement = _capture_boundary(runtime)
    observation, interface = observer.update(
        measurement, runtime["model"], human_model_version=f"belief_{belief.sequence}"
    )
    state = observation.as_array()
    try:
        if recovery_result is not None and not recovery_result["succeeded"]:
            raise ValueError(str(recovery_result["abort_reason"]))
        task_state: GoalTaskState = start_episode(
            spec, state[:2], state[2:], acceleration_authority_valid=False
        )
    except ValueError as error:
        task_state = GoalTaskState(
            phase=TaskPhase.ABORTED,
            phase_elapsed_s=0.0,
            hold_elapsed_s=0.0,
            start_validated=False,
            outbound_hold_completed=False,
            abort_reason=(f"ACTIVE_RECOVERY_ABORTED:{error}"
                          if recovery_result is not None and recovery_result["entered"]
                          else f"REPETITION_START_NOT_SETTLED:{error}" if resumed
                          else f"COMMISSIONING_HANDOFF_NOT_SETTLED:{error}"),
        )

    active_schedule = None
    async_pending: dict[str, Any] | None = None
    prefetch_attempt_schedule = None
    future_handoff_bridges: list[dict[str, Any]] = []
    runtime["future_handoff_bridges"] = future_handoff_bridges
    rolling_splice_events: list[dict[str, Any]] = []
    runtime["rolling_splice_events"] = rolling_splice_events
    rolling_splice_pending = None
    task_expiry_retries = 0
    active_escape = None
    fallback_latch = None
    fallback_bridge = None
    fallback_stop_sample_s = None
    activation_backup = None
    fallback_events = runtime.setdefault("safe_fallback_events", [])
    readiness_hook = (runtime_capture or {}).get("future_result_ready")
    def result_ready(pending_request):
        if not pending_request["future"].done():
            return False
        if scientific:
            return True
        return readiness_hook is None or readiness_hook(pending_request, monotonic_ns())
    def fallback_event(name, **details):
        fallback_events.append(dict(event=name, host_ns=monotonic_ns(),
            physics_s=float(plant.data.time), phase=task_state.phase.value, **details))

    if runtime.get("wall_session") is not None:
        runtime["sensor_task_clock"] = SensorSupportedTaskClock(
            projected_dwell=bool(recovery_options.get('causal_dwell_projection',False)))
    planning_wait: dict[str, Any] | None = None
    schedule_start_time = float(truth.time_s)
    reference_state = (
        np.concatenate([start_q, np.zeros(2)])
        if recovery_result is None or "reference_end_q_rad" not in recovery_result
        else np.concatenate([
            recovery_result["reference_end_q_rad"],
            recovery_result["reference_end_dq_rad_s"],
        ])
    )
    reference_acceleration = (
        np.zeros(2) if recovery_result is None or "reference_end_ddq_rad_s2" not in recovery_result
        else recovery_result["reference_end_ddq_rad_s2"].copy()
    )
    decisions: list[dict[str, Any]] = []
    runtime["task_decisions"] = decisions
    active_decision_index: int | None = None
    transitions: list[dict[str, Any]] = []
    learning_records: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    adaptation_trace: list[dict[str, Any]] = []
    last_adaptation: dict[str, Any] | None = None
    next_adaptation_time = float(truth.time_s) + ADAPTATION_DT_S
    reference_governor = ReceiptReferenceGovernor() if recovery_options.get("receipt_reference_governor", False) else None
    if reference_governor is not None:
        runtime["reference_governor_records"] = reference_governor.records
    phase_previous = task_state.phase
    task_start_time = float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)
    task_last_physics_time = task_start_time
    if runtime.get("wall_session") is not None:
        runtime["wall_session"].set_phase("TASK", task_timeout_s)
    if qualification_case is not None:
        runtime["true_physics_monitor"].stage = "TASK"
        runtime["true_physics_monitor"].observe(plant, integrated_step=False)
    maximum_steps = int(math.ceil(task_timeout_s / CONTROL_DT_S))
    safety_counts: Counter[str] = Counter()
    executed_interval_count = 0

    for step in range(maximum_steps + 1):
        truth, measurement = _capture_boundary(runtime)
        belief = updater.snapshot()
        if qualification_arm == "fixed_population":
            belief = replace(belief, geometry_source="FIXED_NOMINAL",
                             dynamics_source="FIXED_NOMINAL", residual_source="FIXED_NOMINAL")
        runtime["model"] = belief.human_model()
        runtime["model_sequence"] = belief.sequence
        runtime["contract"].human_model = runtime["model"]
        scheduler.human_model = runtime["model"]
        observation, interface = observer.update(
            measurement,
            runtime["model"],
            human_model_version=f"belief_{belief.sequence}",
        )
        state = observation.as_array()
        if (
            active_schedule is not None
            and (reference_governor.is_complete(active_schedule) if reference_governor is not None else (float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)) - schedule_start_time + 1.0e-12 >= active_schedule.duration_s)
        ):
            # Consume the endpoint boundary before task-transition and replan
            # logic.  Otherwise a schedule can be replaced on the exact node
            # where it finishes without ever emitting its q/dq/ddq endpoint.
            endpoint = active_schedule.sample(active_schedule.duration_s)
            reference_state = np.concatenate([endpoint.q_rad, endpoint.dq_rad_s])
            reference_acceleration = endpoint.ddq_rad_s2.copy()
        torque = measured_transmitted_human_input(observation, interface, runtime["model"])
        if (float(observation.sample_timestamp_s) + 1.0e-12 >= next_adaptation_time
                and (last_adaptation is None or observation.sample_timestamp_s > last_adaptation["time_s"]+1e-12)):
            current = {"time_s": float(observation.sample_timestamp_s), "state": state.copy(), "torque": torque.copy()}
            if last_adaptation is not None and qualification_arm == "continual_adaptive":
                dt = current["time_s"] - last_adaptation["time_s"]
                ddq = (current["state"][2:] - last_adaptation["state"][2:]) / dt
                beta_before = updater.dynamics.beta.copy()
                residual_before = updater.weights_nm.copy()
                diagnostics = updater.observe_dynamics(
                    q_rad=last_adaptation["state"][:2],
                    dq_rad_s=last_adaptation["state"][2:],
                    ddq_rad_s2=ddq,
                    applied_generalized_torque_nm=last_adaptation["torque"],
                )
                adaptation_trace.append({
                    "time_s": current["time_s"],
                    "input_interval_s": dt,
                    "belief_sequence_before": belief.sequence,
                    "belief_sequence_after": updater.sequence,
                    "beta_before": beta_before.copy(),
                    "beta_after": updater.dynamics.beta.copy(),
                    "beta_step_l2": float(np.linalg.norm(updater.dynamics.beta - beta_before)),
                    "residual_weights_before_nm": residual_before,
                    "residual_weights_after_nm": updater.weights_nm.copy(),
                    "residual_step_l2": float(np.linalg.norm(updater.weights_nm - residual_before)),
                    "diagnostics": diagnostics,
                })
            last_adaptation = current
            next_adaptation_time = current["time_s"] + ADAPTATION_DT_S
            belief = updater.snapshot()
            if qualification_arm == "fixed_population":
                belief = replace(belief, geometry_source="FIXED_NOMINAL",
                                 dynamics_source="FIXED_NOMINAL", residual_source="FIXED_NOMINAL")
            runtime["model"] = belief.human_model()
            runtime["model_sequence"] = belief.sequence
            runtime["contract"].human_model = runtime["model"]
            scheduler.human_model = runtime["model"]
            if transfer_config is not None:
                runtime["model_transfer"].offer(
                    runtime["model"], version=f"belief_{belief.sequence}",
                    time_s=float(truth.time_s),
                )

        split = runtime["monitor"].update(
            sample_timestamp_s=observation.sample_timestamp_s,
            estimated_dq_rad_s=state[2:],
            cuff_force_world_n=interface.measured_force_world_n,
            cuff_moment_world_nm=interface.measured_moment_world_nm,
            interface_translation_human_m=interface.displacement_human_m,
            interface_velocity_human_m_s=interface.velocity_human_m_s,
            interface_rotation_human_rad=interface.rotation_error_human_rad,
            interface_angular_velocity_human_rad_s=interface.angular_velocity_human_rad_s,
            command_wrench_world=runtime["last_command"].wrench_total_world,
            robot_joint_torque_command_nm=runtime["last_command"].joint_torque_command_nm,
        )
        authority = runtime["authority"].evaluate(split)
        physical_now = float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)
        task_dt = max(0.0, physical_now-task_last_physics_time) if runtime.get("wall_session") is not None else CONTROL_DT_S
        task_last_physics_time = physical_now
        previous_task_state = task_state
        active_segment_complete = bool(
            active_schedule is not None
            and (reference_governor.is_complete(active_schedule) if reference_governor is not None else (float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)) - schedule_start_time + 1.0e-12 >= active_schedule.duration_s)
        )
        phase_goal = np.asarray(
            spec.start_return_target_rad
            if previous_task_state.phase is TaskPhase.RETURN
            else spec.outbound_goal_target_rad,
            dtype=float,
        )
        transition_reference_ready = bool(
            active_segment_complete
            and (in_original_terminal_box(spec, reference_state[:2], phase_goal)
                 if recovery_options.get("terminal_set_reference", False)
                 else np.allclose(reference_state[:2], phase_goal, atol=1.0e-10, rtol=0.0))
            and np.allclose(reference_state[2:], 0.0, atol=1.0e-10, rtol=0.0)
            and np.allclose(reference_acceleration, 0.0, atol=1.0e-10, rtol=0.0)
        )
        realized_abort_reason = authority.abort_reason if authority.violation else None
        if (realized_abort_reason is None and planning_wait is not None
                and float(truth.time_s) + 1.0e-12 >= planning_wait["abort_time_s"]):
            realized_abort_reason = planning_wait["abort_reason"]
        if realized_abort_reason is None and np.linalg.norm(
            interface.measured_force_world_n
        ) > float(config["cuff_force_limit_n"]) + 1.0e-9:
            realized_abort_reason = "REALIZED_CUFF_FORCE_LIMIT"
        if realized_abort_reason is None and np.linalg.norm(
            interface.measured_moment_world_nm
        ) > float(config["cuff_moment_limit_nm"]) + 1.0e-9:
            realized_abort_reason = "REALIZED_CUFF_MOMENT_LIMIT"
        if realized_abort_reason is None and np.any(
            np.abs(measurement.robot_dq_rad_s)
            > CR12_VELOCITY_LIMITS_RAD_S + 1.0e-9
        ):
            realized_abort_reason = "CR12_VELOCITY_LIMIT"
        if (
            realized_abort_reason is None
            and clearance.evaluate(state[:2]) < -1.0e-9
        ):
            realized_abort_reason = "SESSION_CLEARANCE_LIMIT"
        transition_function = (runtime["sensor_task_clock"].transition
                               if runtime.get("wall_session") is not None else transition_phase)
        dwell_options = ({"sample_time_s": float(observation.sample_timestamp_s),
                          "physical_time_s": physical_now,
                          "captured_samples": runtime["wall_session"].sampled_estimates[-max(2,int(task_dt/.005)+3):]}
                         if runtime.get("wall_session") is not None else {})
        proposed_task_state = transition_function(
            spec,
            previous_task_state,
            state[:2],
            state[2:],
            task_dt,
            ddq_rad_s2=split.human_motion_acceleration_rad_s2,
            acceleration_authority_valid=split.human_motion_valid,
            abort_reason=realized_abort_reason,
            **dwell_options,
        )
        if (recovery_options.get("causal_return_projection", False)
                and previous_task_state.phase is TaskPhase.RETURN
                and proposed_task_state.phase is TaskPhase.COMPLETE):
            wall = runtime["wall_session"]
            source_s = float(observation.sample_timestamp_s)
            capture_ns = wall.source_ns(source_s)
            guard = causal_return_projection(spec, state,
                split.fast_motion_acceleration_rad_s2, split.human_motion_acceleration_rad_s2,
                fast_valid=split.fast_motion_valid, slow_valid=split.human_motion_valid,
                aligned=abs(split.sample_timestamp_s-source_s) <= 1e-12,
                source_age_s=((float(plant.data.time)-source_s) if scientific
                              else (wall.clock()-capture_ns)/1e9), horizon_s=2*CONTROL_DT_S)
            guard.update(source_sample_time_s=source_s, source_capture_ns=capture_ns,
                         reference_ready=transition_reference_ready,
                         decision_host_ns=wall.clock(), belief_sequence=belief.sequence,
                         observation_model_version=observation.human_model_version)
            runtime.setdefault("return_projection_guards", []).append(guard)
            transition_reference_ready = transition_reference_ready and guard["ready"]
        task_state = reference_safe_task_transition(
            spec, previous_task_state, proposed_task_state, task_dt,
            transition_reference_ready,
            continuous_hold=bool(recovery_options.get("robust_hold_reference", False)))
        if (task_state.phase is TaskPhase.COMPLETE
                and recovery_options.get("causal_terminal_commit", False)):
            wall = runtime["wall_session"]
            commit_operation = (attempt_scientific_return_commit if scientific else attempt_return_commit)
            commit_record = commit_operation(wall, runtime["return_projection_guards"][-1],
                phase_elapsed_at_boundary_s=previous_task_state.phase_elapsed_s+task_dt,
                boundary_physics_s=physical_now, phase_timeout_s=spec.phase_timeout_s,
                task_start_s=task_start_time, task_timeout_s=task_timeout_s,
                inspect_sample=lambda obs, meas, iface, sample: terminal_sample_evidence(
                    spec, obs, meas, iface, sample, authority=runtime["authority"],
                    clearance=clearance, force_limit=float(config["cuff_force_limit_n"]),
                    moment_limit=float(config["cuff_moment_limit_nm"]),
                    robot_velocity_limits=CR12_VELOCITY_LIMITS_RAD_S))
            if commit_record["action"] == "DEFER":
                # The next iteration alone credits the physical tail. Keep the
                # old phase boundary and acquire a genuinely newer observation.
                task_state = replace(previous_task_state,
                    phase_elapsed_s=previous_task_state.phase_elapsed_s+task_dt)
                wall.next_control_tick()
                continue
            if commit_record["action"] == "ABORT":
                task_state = abort_episode(replace(previous_task_state,
                    phase_elapsed_s=commit_record["actual_return_elapsed_s"]),
                    commit_record["reason"])
            else:
                runtime["return_projection_finalization"] = commit_record
        if ((planning_wait is not None or (online_timing and async_pending is not None
                                           and not async_pending.get("fallback_discarded")))
                and task_state.phase is not previous_task_state.phase
                and task_state.phase not in (TaskPhase.ABORTED, TaskPhase.COMPLETE)):
            task_state = abort_episode(task_state, "PLANNING_WAIT_PHASE_CHANGED")
        if (step == maximum_steps or physical_now-task_start_time >= task_timeout_s) and task_state.phase not in (
            TaskPhase.COMPLETE,
            TaskPhase.ABORTED,
        ):
            task_state = abort_episode(task_state, "GLOBAL_TASK_TIMEOUT")
        if task_state.phase is not phase_previous:
            if scientific:
                runtime["task_phase_version"] = int(runtime.get("task_phase_version", 0)) + 1
            transitions.append({
                "time_s": float(truth.time_s),
                "from": phase_previous.value,
                "to": task_state.phase.value,
                "estimated_state": state.copy(),
                "trigger": "actual_estimated_arrival_settling_or_valid_hold_dwell",
            })
            if (task_state.phase is TaskPhase.COMPLETE
                    and recovery_options.get("causal_terminal_commit", False)):
                transitions[-1].update(state_source_time_s=float(truth.time_s),
                    time_s=commit_record["final_native_time_s"],
                    actual_completion_commit_ns=commit_record["final_host_ns"],
                    trigger="causal_return_actual_completion_commit")
            phase_previous = task_state.phase
            active_schedule = None
            active_escape = None
            fallback_latch = None
            fallback_bridge = None
            activation_backup = None
            prefetch_attempt_schedule = None
            if rolling_splice_pending is not None and not rolling_splice_pending["spliced"]:
                rolling_splice_pending["event"]["outcome"] = "CANCELLED_PHASE_CHANGED"
            rolling_splice_pending = None
            active_decision_index = None
            planner.reset_phase()
            if online_timing and async_pending is not None:
                lifecycle.discard(async_pending["request"], "CANCELLED", "TASK_PHASE_CHANGED")
                async_pending = None

        if task_state.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
            if pending is not None:
                pending["next_observation"] = state.copy()
                pending["next_adaptive_state"] = belief.value_state_record()
                pending["end_time_s"] = float(truth.time_s)
                pending["duration_s"] = max(
                    0.0, pending["end_time_s"] - pending["start_time_s"]
                )
                pending["selected_plan_activated"] = bool(
                    decisions[pending["decision_index"]]["plan_activated"]
                )
                pending["completion"] = task_state.phase.value
                if (task_state.phase is TaskPhase.COMPLETE
                        and recovery_options.get("causal_terminal_commit", False)):
                    pending["completion_physical_commit_s"] = commit_record["final_native_time_s"]
                    pending["completion_host_commit_ns"] = commit_record["final_host_ns"]
                    pending["end_observation_time_semantics"] = "causal source capture; separate physical completion commit"
                learning_records.append(pending)
                pending = None
            trace.append({
                "stage": "TASK",
                "time_s": float(truth.time_s),
                "task_elapsed_s": float(truth.time_s) - task_start_time,
                "physics_steps": int(round(truth.time_s / NOMINAL_PHYSICS_DT_S)),
                "task_phase": task_state.phase.value,
                "q_ref_rad": reference_state[:2].copy(),
                "dq_ref_rad_s": reference_state[2:].copy(),
                "ddq_ref_rad_s2": reference_acceleration.copy(),
                "estimated_state": state.copy(),
                "truth_state": np.concatenate([truth.human_q_rad, truth.human_dq_rad_s]),
                "robot_q_rad": truth.robot_q_rad.copy(),
                "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
                "robot_tau_nm": runtime["last_command"].joint_torque_command_nm.copy(),
                "applied_robot_tau_nm": np.zeros(6),
                "cuff_position_world_m": measurement.attachment_position_m.copy(),
                "cuff_rotation_world": measurement.attachment_rotation_matrix.copy(),
                "cuff_linear_velocity_world_m_s": measurement.attachment_velocity_m_s.copy(),
                "cuff_angular_velocity_world_rad_s": measurement.attachment_angular_velocity_rad_s.copy(),
                "cuff_force_world_n": interface.measured_force_world_n.copy(),
                "cuff_moment_world_nm": interface.measured_moment_world_nm.copy(),
                "belief_sequence": belief.sequence,
                "beta": belief.beta.copy(),
                "residual_weights_nm": belief.state_residual_weights_nm.copy(),
                "selected_schedule_label": None,
                "shank_clearance_session_m": shank_clearance.evaluate(state[:2]),
                "dev_d_envelope_clearance_m": (
                    clearance.evaluate(state[:2]) if dev_d_rigid_table_reference else float("nan")),
                "dev_d_measured_sleeve_gap_m": (
                    clearance.envelope.measured_sleeve_gap(
                        interface.human_position_world_m, interface.human_rotation_world)
                    if dev_d_rigid_table_reference else float("nan")),
                "shank_bed_contact_evaluation_only": _shank_bed_contact(plant),
                "active_contact_pairs_evaluation_only": _active_contact_pairs(plant),
                "actual_acceleration_rad_s2": split.human_motion_acceleration_rad_s2.copy(),
                "actual_acceleration_valid": split.human_motion_valid,
                "acceleration_violation": authority.violation,
                "interval_force_cost_n_s": 0.0,
                "terminal_boundary_node": True,
            })
            break

        if (fallback_latch is not None and fallback_latch.mode == "BRAKING"
                and active_schedule is fallback_bridge):
            stop = fallback_latch.bundle.stop
            first_stop = stop.sample(0.)
            jumps = np.r_[first_stop.q_rad-reference_state[:2],
                          first_stop.dq_rad_s-reference_state[2:],
                          first_stop.ddq_rad_s2-reference_acceleration]
            if np.max(np.abs(jumps)) > 1e-10:
                task_state = abort_episode(task_state, "FALLBACK_C2_ORIGIN")
                continue
            active_schedule = stop
            schedule_start_time = float(plant.data.time)
            active_decision_index = None
            if pending is not None:
                pending.update(next_observation=state.copy(), next_adaptive_state=belief.value_state_record(),
                    end_time_s=float(truth.time_s), duration_s=max(0.,float(truth.time_s)-pending["start_time_s"]),
                    completion="FALLBACK_COMMITTED", selected_plan_activated=True)
                learning_records.append(pending)
                pending = None
        schedule_done = bool(
            active_schedule is not None
            and (reference_governor.is_complete(active_schedule) if reference_governor is not None else (float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)) - schedule_start_time + 1.0e-12 >= active_schedule.duration_s)
        )
        waypoint_reached = bool(
            active_schedule is not None
            and np.all(np.abs(state[:2] - active_schedule.candidate.q_waypoint_rad) <= np.asarray(spec.joint_angle_completion_tolerance_rad))
            and np.all(np.abs(state[2:] - active_schedule.candidate.dq_waypoint_rad_s) <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s))
        )
        stationary_terminal_reference = bool(
            smooth_waypoint_mode and active_schedule is not None and schedule_done
            and task_state.phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN)
            and in_original_terminal_box(spec, active_schedule.candidate.q_waypoint_rad,
                spec.start_return_target_rad if task_state.phase is TaskPhase.RETURN
                else spec.outbound_goal_target_rad)
            and np.allclose(active_schedule.candidate.dq_waypoint_rad_s, 0.0,
                            atol=1e-10, rtol=0.0)
        )
        if (fallback_latch is not None and fallback_latch.mode == "BRAKING"
                and active_schedule is fallback_latch.bundle.stop and schedule_done):
            fallback_latch.stopped()
            fallback_stop_sample_s = float(observation.sample_timestamp_s)
            fallback_event("FALLBACK_STOPPED", q_rad=reference_state[:2].copy(),
                           dq_rad_s=reference_state[2:].copy(),ddq_rad_s2=reference_acceleration.copy())
            fallback_event("FALLBACK_HOLD", execution_state="SAFE_FALLBACK_HOLD")
        if (async_pending is not None and async_pending.get("pass_through_prefetch")
                and fallback_latch is not None and lifecycle.expired(async_pending["request"])):
            lifecycle.discard(async_pending["request"], "EXPIRED", "STALE_PLAN_MAXIMUM_AGE")
            async_pending["fallback_discarded"] = True
        if async_pending is not None and async_pending.get("fallback_discarded"):
            if result_ready(async_pending):
                old_request = async_pending["request"]
                lifecycle.mark_once(old_request, "result_collected_ns")
                try:
                    lifecycle.result(async_pending["future"])
                except Exception:
                    pass  # Immutable worker exception remains in the lifecycle.
                fallback_event("OLD_PRIMARY_DROPPED", request_id=old_request.request_id,
                    age_ms=(monotonic_ns()-old_request.sensor_capture_ns)/1e6,
                    stale=lifecycle.expired(old_request))
                async_pending = None
        if online_timing and async_pending is not None and not async_pending.get("fallback_discarded"):
            request = async_pending["request"]
            future = async_pending["future"]
            if lifecycle.expired(request):
                lifecycle.discard(request, "EXPIRED", "STALE_PLAN_MAXIMUM_AGE")
                if async_pending.get("pass_through_prefetch"):
                    task_state = abort_episode(task_state, "PASS_THROUGH_PREFETCH_EXPIRED")
                    continue
                if runtime.get("wall_session") is None:
                    task_state = abort_episode(task_state, "STALE_PLAN_MAXIMUM_AGE")
                    continue
                async_pending["expired"] = True
                if future.done():
                    lifecycle.mark_once(request, "result_collected_ns")
                    try:
                        lifecycle.result(future)
                    except BaseException:
                        pass  # Worker exception is already retained by lifecycle.
                    async_pending = None
                    task_expiry_retries += 1
                    if task_expiry_retries >= 3:
                        task_state = abort_episode(task_state, "TASK_EXPIRED_REQUEST_RETRY_LIMIT")
                        continue
            if (async_pending is not None and not async_pending.get("expired", False)
                    and result_ready(async_pending)
                    and (not async_pending.get("pass_through_prefetch") or schedule_done
                         or (async_pending.get("handoff_bridge_schedule") is not None
                             and active_schedule is async_pending["handoff_bridge_schedule"]))):
                activation_backup = (dict(schedule=active_schedule, start_time=schedule_start_time,
                    reference_state=reference_state.copy(), reference_acceleration=reference_acceleration.copy(),
                    request=request, latch=fallback_latch)
                    if fallback_latch is not None and fallback_latch.mode == "ARMED"
                    and active_schedule is fallback_bridge else None)
                lifecycle.mark(request, "result_collected_ns")
                try:
                    decision = lifecycle.result(future)
                except Exception as error:
                    decisions.append({
                        "timing_request_id": request.request_id,
                        "phase": task_state.phase.value, "plan_activated": False,
                        "planning_exception": f"{type(error).__name__}:{error}",
                        "planning_runtime_ms_measured": lifecycle.records()[request.request_id]["compute_ms"],
                        "reference_boundary_continuity": None,
                    })
                    if activation_backup is not None:
                        fallback_event("PRIMARY_REJECTED_ESCAPE_RETAINED", reason=str(error))
                        async_pending = None
                        activation_backup = None
                        continue
                    task_state = abort_episode(task_state, f"NO_FEASIBLE_WAYPOINT:{error}")
                    async_pending = None
                    continue
                suffix_schedule = decision.executed.schedule
                if (smooth_waypoint_mode and np.any(np.abs(suffix_schedule.candidate.dq_waypoint_rad_s)>1e-12)
                        and getattr(suffix_schedule, "safe_escape", None) is None):
                    raise RuntimeError("PASS_THROUGH_WITHOUT_PREVALIDATED_ESCAPE")
                rolling_composite = None
                if (async_pending.get("handoff_bridge_schedule") is not None
                        and async_pending["handoff_bridge_schedule"] is active_schedule
                        and not schedule_done):
                    prefix_progress = (reference_governor.progress_s
                                       if reference_governor is not None
                                       and reference_governor.schedule is active_schedule
                                       else min(active_schedule.duration_s,
                                                max(0., float(plant.data.time)-schedule_start_time)))
                    if prefix_progress < active_schedule.duration_s-1e-12:
                        try:
                            rolling_composite = RollingSuffixCompositeSchedule(
                                prefix=active_schedule, prefix_start_s=prefix_progress,
                                suffix=suffix_schedule, request_id=request.request_id)
                        except ValueError as error:
                            lifecycle.finish(request, "REJECTED", "ROLLING_SUFFIX_C2")
                            task_state = abort_episode(task_state, f"ROLLING_SUFFIX_C2:{error}")
                            async_pending = None
                            continue
                active_schedule = rolling_composite or suffix_schedule
                schedule_done = False
                schedule_start_time = float(truth.time_s)
                first = active_schedule.sample(0.0)
                continuity = {
                    "q_boundary_jump_rad": first.q_rad - reference_state[:2],
                    "dq_boundary_jump_rad_s": first.dq_rad_s - reference_state[2:],
                    "ddq_boundary_jump_rad_s2": first.ddq_rad_s2 - reference_acceleration,
                }
                if any(np.max(np.abs(v)) > 1e-10 for v in continuity.values()):
                    lifecycle.finish(request, "REJECTED", "ASYNC_REFERENCE_DISCONTINUITY")
                    task_state = abort_episode(task_state, "ASYNC_REFERENCE_DISCONTINUITY")
                    async_pending = None
                    continue
                record = decision.record()
                record.update({
                    "timing_request_id": request.request_id,
                    "decision_request_time_s": async_pending["request_time_s"],
                    "request_measurement_timestamp_s": request.source_sample_time_s,
                    "planning_runtime_ms_measured": lifecycle.records()[request.request_id]["compute_ms"],
                    "plan_activated": False, "activation_timestamp_s": None,
                    "activation_accepted_by_deadline": False,
                    "reference_boundary_continuity": continuity,
                    "belief_sequence_used": async_pending["belief_sequence"],
                    "value_hook_numeric_value": 0.0,
                    "deadline_wait_physical_intervals": async_pending["wait_intervals"],
                    "simulated_planning_delay_s": None,
                    "pass_through_prefetch": bool(async_pending.get("pass_through_prefetch")),
                    "future_handoff_bridge": bool(async_pending.get("handoff_bridge_schedule") is not None),
                    "rolling_composite": (None if rolling_composite is None
                                          else rolling_composite.record()),
                })
                decisions.append(record)
                active_decision_index = len(decisions) - 1
                if async_pending.get("pass_through_prefetch") and pending is not None:
                    pending.update(next_observation=state.copy(),
                                   next_adaptive_state=belief.value_state_record(),
                                   end_time_s=float(truth.time_s),
                                   duration_s=max(0.0, float(truth.time_s)-pending["start_time_s"]),
                                   selected_plan_activated=bool(decisions[pending["decision_index"]]["plan_activated"]),
                                   completion="SEGMENT_COMPLETE")
                    learning_records.append(pending)
                    pending = None
                planner.previous_executed_delta_q_rad = decision.executed.proposed_delta_q_rad.copy()
                planner.decisions.append(decision)
                if hasattr(planner, "note_accepted_decision"):
                    planner.note_accepted_decision(decision)
                adaptive_planner.belief_sequences_used.append(async_pending["belief_sequence"])
                pending = {
                    "schema": "full3d_adaptive_transition_v1",
                    "decision_index": active_decision_index,
                    "request_time_s": async_pending["request_time_s"],
                    "start_time_s": schedule_start_time,
                    "observation": async_pending["state"],
                    "adaptive_state": async_pending["belief_record"],
                    "candidate_set": [item.record() for item in decision.evaluations],
                    "selected_plan": decision.executed.record(),
                    "belief_sequence_at_request": async_pending["belief_sequence"],
                    "execution_belief_sequences": [],
                    "measured_force_integral_n_s": 0.0,
                    "planning_wait_force_integral_n_s": async_pending["wait_force_integral_n_s"],
                    "planner_ranking_cost": decision.executed.total_cost,
                    "physical_cost_source": "measured_cuff_force_interval_integral", "value_hook": 0.0,
                }
                request_sequence = async_pending["belief_sequence"]
                requested_phase = async_pending["phase"]
                handoff = bool(async_pending.get("handoff_bridge_schedule") is not None)
                revalidation_sample_s = float(observation.sample_timestamp_s)
                revalidation_capture_ns = (runtime["wall_session"].source_ns(revalidation_sample_s)
                                           if handoff else None)
                revalidation_state = state.copy()
                revalidation_ddq = split.human_motion_acceleration_rad_s2.copy()
                revalidation_accel_valid = bool(split.human_motion_valid)
                reference_ddq = reference_acceleration.copy()
                request_plan_version = suffix_schedule.version
                request_geometry_signature = async_pending["certificate_geometry_signature"]
                future_inputs = (dict(
                        spec=spec, estimated_state=revalidation_state,
                        estimated_acceleration=revalidation_ddq,
                        reference_acceleration=reference_ddq,
                        acceleration_valid=revalidation_accel_valid,
                        revalidation_capture_ns=revalidation_capture_ns,
                        request_plan_version=request_plan_version,
                        original_sample_s=request.source_sample_time_s,
                        revalidation_sample_s=revalidation_sample_s,
                        age_policy=("simulation" if scientific else "wall"),
                    ) if handoff else None)
                def validate_current_activation(reference_origin=reference_state.copy(),
                                                acceleration_origin=reference_acceleration.copy(),
                                                composite=rolling_composite,
                                                suffix=suffix_schedule,
                                                inputs=future_inputs):
                    current_inputs = (None if inputs is None else {
                        **inputs, "now_ns": monotonic_ns(),
                        "original_capture_ns": request.sensor_capture_ns})
                    common = dict(belief=belief, request_sequence=request_sequence,
                                  clearance=clearance, phase=task_state.phase,
                                  request_phase=requested_phase,
                                  remaining_s=spec.phase_timeout_s-task_state.phase_elapsed_s
                                      -max(0., float(plant.data.time)-physical_now),
                                  now_physics_s=float(plant.data.time))
                    if composite is not None:
                        return validate_rolling_composite(
                            composite=composite, spec=spec,
                            current_reference_state=reference_origin,
                            current_reference_acceleration=acceleration_origin,
                            future_handoff=current_inputs,
                            certificate_geometry_at_request=request_geometry_signature,
                            **common)
                    return validate_activation(
                        schedule=suffix, reference_state=reference_origin,
                        future_handoff=current_inputs,
                        certificate_geometry_at_request=request_geometry_signature,
                        **common)
                runtime["activation_validator"] = validate_current_activation
                splice_event = None
                if rolling_composite is not None:
                    splice_event = dict(
                        request_id=request.request_id,
                        original_request_sample_s=request.source_sample_time_s,
                        original_request_capture_ns=request.sensor_capture_ns,
                        planning_model_sequence=request_sequence,
                        suffix_version=suffix_schedule.version,
                        revalidation_sample_s=revalidation_sample_s,
                        revalidation_capture_ns=revalidation_capture_ns,
                        composite=rolling_composite.record(),
                        outcome="AWAITING_ACTIVATION")
                    rolling_splice_events.append(splice_event)
                def on_task_activation(receipt):
                    nonlocal schedule_start_time, rolling_splice_pending, active_escape
                    nonlocal fallback_latch, activation_backup
                    if fallback_latch is not None:
                        age_ns = (int(round((float(plant.data.time)-request.source_sample_time_s)*1e9))
                                  if scientific else int(receipt["apply_ns"])-request.sensor_capture_ns)
                        if fallback_latch.mode == "ARMED":
                            if not fallback_latch.choose_primary(validated=True, age_ns=age_ns):
                                raise RuntimeError("PRIMARY_AFTER_FALLBACK_COMMIT")
                        elif fallback_latch.mode == "SAFE_FALLBACK_HOLD":
                            if not fallback_latch.resume(fresh=request.source_sample_time_s >= fallback_stop_sample_s,
                                                         validated=True, age_ns=age_ns):
                                raise RuntimeError("INVALID_FALLBACK_RESUME")
                            fallback_event("RESUME_ACTIVATED", request_id=request.request_id,age_ms=age_ns/1e6)
                        else:
                            raise RuntimeError("PRIMARY_INTERRUPTED_BRAKING")
                        fallback_latch = None
                    active_escape = getattr(suffix_schedule, "safe_escape", None)
                    if active_escape is not None:
                        fallback_event("ESCAPE_ADMITTED", request_id=request.request_id,
                                       certificate=active_escape.certificate)
                    activation_backup = None
                    schedule_start_time = float(plant.data.time)
                    if pending is not None:
                        pending["start_time_s"] = schedule_start_time
                    decisions[active_decision_index]["actual_schedule_start_physics_s"] = schedule_start_time
                    if splice_event is not None:
                        apply_ns = int(receipt["apply_ns"])
                        splice_event.update(
                            outcome="COMPOSITE_ACTIVATED",
                            composite_activation_ns=apply_ns,
                            composite_activation_physics_s=schedule_start_time,
                            request_to_activation_ms=(apply_ns-request.sensor_capture_ns)/1e6,
                            revalidation_to_activation_ms=(apply_ns-revalidation_capture_ns)/1e6,
                            activation_model_sequence=belief.sequence)
                        rolling_splice_pending = dict(
                            composite=rolling_composite, request=request,
                            request_sequence=request_sequence,
                            request_phase=requested_phase,
                            certificate_geometry_signature=request_geometry_signature,
                            activation_revalidation_capture_ns=revalidation_capture_ns,
                            event=splice_event, spliced=False)
                runtime["actual_activation_hook"] = on_task_activation
                runtime["plan_to_activate"] = request
                async_pending = None
        if (online_timing and async_pending is not None
                and async_pending.get("pass_through_prefetch") and schedule_done
                and not async_pending.get("fallback_discarded")
                and not async_pending["future"].done()):
            task_state = abort_episode(task_state, "PASS_THROUGH_PREFETCH_NOT_READY_AT_ENDPOINT")
            continue
        prefetch_due = False
        if (online_timing and smooth_waypoint_mode and active_schedule is not None
                and active_schedule is not prefetch_attempt_schedule and schedule_done
                and task_state.phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN)
                and np.any(np.abs(active_schedule.candidate.dq_waypoint_rad_s) > 1e-12)):
            # Start a certified constant-velocity continuation at the actual
            # completed endpoint. Planning begins while this continuation is
            # executing, so request age contains one 40 ms bridge rather than
            # uncertain pre-endpoint progress plus the bridge. 40 ms is eight
            # registered control periods: measured ~30 ms p95 worker compute
            # plus two periods for worker/main scheduling. It leaves 15 ms
            # under the independently scored 55 ms activation gate.
            prefetch_due = True
        if online_timing and async_pending is None and (
                active_schedule is None or (schedule_done and waypoint_reached
                                            and not stationary_terminal_reference) or prefetch_due):
            if pending is not None and not prefetch_due:
                pending.update(next_observation=state.copy(), next_adaptive_state=belief.value_state_record(),
                               end_time_s=float(truth.time_s),
                               duration_s=max(0.0, float(truth.time_s) - pending["start_time_s"]),
                               selected_plan_activated=bool(decisions[pending["decision_index"]]["plan_activated"]),
                               completion="SEGMENT_COMPLETE")
                learning_records.append(pending)
                pending = None
            # Requests occur only at an old segment endpoint (or phase start).
            # Hold that emitted boundary under the existing supervisor while
            # the independent worker runs; physical time and task clocks advance.
            handoff_bridge = None
            if prefetch_due:
                if active_escape is None:
                    raise RuntimeError("PASS_THROUGH_WITHOUT_PREVALIDATED_ESCAPE")
                handoff_bridge = active_escape.bridge
                fallback_bridge = handoff_bridge
                fallback_latch = FallbackLatch(active_escape)
                future_handoff_bridges.append(dict(
                    request_sample_s=float(observation.sample_timestamp_s),
                    source_schedule_label=active_schedule.candidate.label,
                    bridge_duration_s=handoff_bridge.duration_s,
                    bridge_target_q_rad=handoff_bridge.candidate.q_waypoint_rad.copy(),
                    bridge_target_dq_rad_s=handoff_bridge.candidate.dq_waypoint_rad_s.copy(),
                    bridge_mechanics=active_escape.certificate["bridge_mechanics"],
                    fallback_commit_progress_s=active_escape.commit_progress_s,
                    prevalidated=True))
                first_bridge = handoff_bridge.sample(0.0)
                if any(np.max(np.abs(delta)) > 1e-10 for delta in (
                        first_bridge.q_rad-reference_state[:2],
                        first_bridge.dq_rad_s-reference_state[2:],
                        first_bridge.ddq_rad_s2-reference_acceleration)):
                    task_state = abort_episode(task_state, "FUTURE_HANDOFF_BRIDGE_C2")
                    continue
            request = lifecycle.request("TASK", observation.sample_timestamp_s, asynchronous=True)
            if fallback_latch is not None and fallback_latch.mode == "SAFE_FALLBACK_HOLD":
                fallback_event("FRESH_REPLAN_REQUESTED", request_id=request.request_id,
                    source_sample_s=request.source_sample_time_s, stopped_sample_s=fallback_stop_sample_s)
            request_reference = (np.r_[handoff_bridge.sample(handoff_bridge.duration_s).q_rad,
                                      handoff_bridge.sample(handoff_bridge.duration_s).dq_rad_s]
                                 if prefetch_due else reference_state.copy())
            if recovery_options.get("causal_tracking_offset_clearance", False):
                tracking_snapshot = receipt_reference_at_sample(
                    runtime["wall_session"].applied_commands, observation.sample_timestamp_s)
                tracking_snapshot.update(request_id=request.request_id,
                    source_state_rad_rad_s=state.copy(),
                    proposed_schedule_origin_rad_rad_s=request_reference.copy(),
                    belief_sequence=belief.sequence)
                runtime.setdefault("causal_tracking_request_snapshots", []).append(tracking_snapshot)
                planner.tracking_reference_snapshot = tracking_snapshot
            arguments = dict(belief=belief, current_deployable_state=state,
                             current_reference_state=request_reference, phase=task_state.phase,
                             phase_elapsed_s=task_state.phase_elapsed_s,
                             phase_remaining_s=spec.phase_timeout_s-task_state.phase_elapsed_s,
                             value_evaluator=None)
            payload = snapshot_task_call(adaptive_planner, arguments)
            lifecycle.mark(request, "snapshot_finish_ns")
            async_pending = {
                "request": request, "future": lifecycle.submit(request, payload),
                "phase": task_state.phase, "state": state.copy(), "belief_record": belief.value_state_record(),
                "belief_sequence": belief.sequence, "request_time_s": float(truth.time_s),
                "certificate_geometry_signature": clearance_geometry_signature(clearance),
                "wait_intervals": 0, "wait_force_integral_n_s": 0.0,
                "pass_through_prefetch": prefetch_due,
                "handoff_source_schedule": active_schedule if prefetch_due else None,
                "handoff_bridge_schedule": handoff_bridge,
            }
            if prefetch_due:
                prefetch_attempt_schedule = active_schedule
                active_schedule = handoff_bridge
                schedule_start_time = float(plant.data.time)
                schedule_done = False
                future_handoff_bridges[-1]["bridge_start_physics_s"] = schedule_start_time
            else:
                active_schedule = None
        if not online_timing and planning_wait is None and (active_schedule is None or (schedule_done and waypoint_reached)):
            if pending is not None:
                pending["next_observation"] = state.copy()
                pending["next_adaptive_state"] = belief.value_state_record()
                pending["end_time_s"] = float(truth.time_s)
                pending["duration_s"] = max(
                    0.0, pending["end_time_s"] - pending["start_time_s"]
                )
                pending["selected_plan_activated"] = bool(
                    decisions[pending["decision_index"]]["plan_activated"]
                )
                pending["completion"] = "SEGMENT_COMPLETE"
                learning_records.append(pending)
                pending = None
            started = perf_counter()
            try:
                decision = adaptive_planner.decide(
                    belief=belief,
                    current_deployable_state=state,
                    current_reference_state=reference_state,
                    phase=task_state.phase,
                    phase_elapsed_s=task_state.phase_elapsed_s,
                    phase_remaining_s=spec.phase_timeout_s - task_state.phase_elapsed_s,
                    value_evaluator=None,
                )
            except ValueError as error:
                planning_ms = 1000.0 * (perf_counter() - started)
                simulated_delay_s = (
                    math.ceil(planning_ms / (1000.0 * CONTROL_DT_S)) * CONTROL_DT_S
                    if simulate_planning_latency else 0.0
                )
                deadline_miss = simulated_delay_s > 0.100 + 1.0e-12
                failure_reason = ("STALE_PLAN_MAXIMUM_AGE" if deadline_miss
                                  else f"NO_FEASIBLE_WAYPOINT:{error}")
                decisions.append({
                    "phase": task_state.phase.value,
                    "planning_exception": f"{type(error).__name__}:{error}",
                    "terminal_reference_selection": getattr(error, "terminal_reference_selection", None),
                    "decision_request_time_s": float(truth.time_s),
                    "request_measurement_timestamp_s": observation.sample_timestamp_s,
                    "measurement_age_at_request_s": float(truth.time_s) - observation.sample_timestamp_s,
                    "planning_completion_timestamp_s": float(truth.time_s) + planning_ms / 1000.0,
                    "planning_runtime_ms_measured": planning_ms,
                    "simulated_planning_delay_s": simulated_delay_s,
                    "stale_plan_age_at_activation_s": simulated_delay_s,
                    "stale_plan_maximum_age_s": 0.100,
                    "activation_rejected_reason": ("STALE_PLAN_MAXIMUM_AGE" if deadline_miss
                                                   else "NO_FEASIBLE_WAYPOINT"),
                    "activation_accepted_by_deadline": False,
                    "plan_activated": False,
                    "activation_timestamp_s": None,
                    "proposed_activation_timestamp_s": None,
                    "reference_executed_while_planning": reference_state.copy(),
                    "belief_sequence_used": belief.sequence,
                    "candidate_count": 0,
                    "feasible_candidate_count": 0,
                    "evaluations": [],
                    "reference_boundary_continuity": None,
                    "value_hook_numeric_value": 0.0,
                    "deadline_wait_physical_intervals": 0,
                })
                active_decision_index = len(decisions) - 1
                planning_wait = {
                    "abort_time_s": float(truth.time_s) + min(simulated_delay_s, 0.100),
                    "abort_reason": failure_reason,
                    "held_reference_state": reference_state.copy(),
                    "held_reference_acceleration": reference_acceleration.copy(),
                }
                if simulated_delay_s <= 0.0:
                    task_state = abort_episode(task_state, failure_reason)
                    continue
            if planning_wait is None:
                planning_ms = 1000.0 * (perf_counter() - started)
                active_schedule = decision.executed.schedule
                assert active_schedule is not None
                simulated_delay_s = (
                    math.ceil(planning_ms / (1000.0 * CONTROL_DT_S)) * CONTROL_DT_S
                    if simulate_planning_latency else 0.0
                )
                schedule_start_time = float(truth.time_s) + simulated_delay_s
                start_sample = active_schedule.sample(0.0)
                continuity = {
                    "q_boundary_jump_rad": (start_sample.q_rad - reference_state[:2]).copy(),
                    "dq_boundary_jump_rad_s": (start_sample.dq_rad_s - reference_state[2:]).copy(),
                    "ddq_boundary_jump_rad_s2": (start_sample.ddq_rad_s2 - reference_acceleration).copy(),
                }
                record = decision.record()
                record.update({
                    "decision_request_time_s": float(truth.time_s),
                    "request_measurement_timestamp_s": observation.sample_timestamp_s,
                    "measurement_age_at_request_s": float(truth.time_s) - observation.sample_timestamp_s,
                    "planning_completion_timestamp_s": float(truth.time_s) + planning_ms / 1000.0,
                    "activation_timestamp_s": None,
                    "proposed_activation_timestamp_s": schedule_start_time,
                    "activation_accepted_by_deadline": simulated_delay_s <= 0.100 + 1.0e-12,
                    "plan_activated": False,
                    "simulated_planning_delay_s": simulated_delay_s,
                    "reference_executed_while_planning": reference_state.copy(),
                    "stale_plan_age_at_activation_s": simulated_delay_s,
                    "stale_plan_maximum_age_s": 0.100,
                    "belief_sequence_used": belief.sequence,
                    "planning_runtime_ms_measured": planning_ms,
                    "value_hook_numeric_value": 0.0,
                    "reference_boundary_continuity": continuity,
                    "activation_rejected_reason": (
                        "STALE_PLAN_MAXIMUM_AGE"
                        if simulated_delay_s > 0.100 + 1.0e-12 else None),
                    "deadline_wait_physical_intervals": 0,
                })
                decisions.append(record)
                active_decision_index = len(decisions) - 1
                if simulated_delay_s > 0.100 + 1.0e-12:
                    planning_wait = {
                        "abort_time_s": float(truth.time_s) + 0.100,
                        "abort_reason": "STALE_PLAN_MAXIMUM_AGE",
                        "held_reference_state": reference_state.copy(),
                        "held_reference_acceleration": reference_acceleration.copy(),
                    }
                else:
                    pending = {
                        "schema": "full3d_adaptive_transition_v1",
                        "decision_index": active_decision_index,
                        "request_time_s": float(truth.time_s),
                        "start_time_s": schedule_start_time,
                        "observation": state.copy(),
                        "adaptive_state": belief.value_state_record(),
                        "candidate_set": [item.record() for item in decision.evaluations],
                        "selected_plan": decision.executed.record(),
                        "belief_sequence_at_request": belief.sequence,
                        "execution_belief_sequences": [],
                        "measured_force_integral_n_s": 0.0,
                        "planning_wait_force_integral_n_s": 0.0,
                        "planner_ranking_cost": decision.executed.total_cost,
                        "physical_cost_source": "measured_cuff_force_interval_integral",
                        "value_hook": 0.0,
                    }

        if online_timing and async_pending is not None and active_schedule is None:
            reference = SimpleNamespace(q_rad=reference_state[:2].copy(),
                                        dq_rad_s=reference_state[2:].copy(),
                                        ddq_rad_s2=reference_acceleration.copy())
        elif planning_wait is not None:
            held = planning_wait["held_reference_state"]
            reference = SimpleNamespace(
                q_rad=held[:2].copy(), dq_rad_s=held[2:].copy(),
                ddq_rad_s2=planning_wait["held_reference_acceleration"].copy())
        else:
            assert active_schedule is not None
            schedule_elapsed = min((float(plant.data.time) if runtime.get("wall_session") is not None else float(truth.time_s)) - schedule_start_time, active_schedule.duration_s)
            # A received plan has not begun while command construction and
            # deadline validation are still running. Its first actual command
            # must use the C2 origin; the receipt hook establishes its clock.
            if reference_governor is not None:
                if fallback_latch is not None and active_schedule is fallback_bridge:
                    schedule_elapsed = fallback_latch.cap(schedule_elapsed)
                reference, progress_proposal = reference_governor.select(
                    active_schedule, max(0.0, schedule_elapsed), runtime["contract"].reference_motion_history,
                    spec.task_joint_acceleration_limit_rad_s2,
                    first=runtime.get("plan_to_activate") is not None)
                if (fallback_latch is not None and active_schedule is fallback_bridge
                        and fallback_latch.mode == "ARMED"
                        and progress_proposal["selected_progress_s"] >= fallback_latch.bundle.commit_progress_s-1e-12):
                    fallback_latch.commit()
                    fallback_event("FALLBACK_COMMITTED", commit_progress_s=fallback_latch.bundle.commit_progress_s,
                        selected_progress_s=progress_proposal["selected_progress_s"],
                        q_rad=reference.q_rad.copy(),dq_rad_s=reference.dq_rad_s.copy(),ddq_rad_s2=reference.ddq_rad_s2.copy())
                    if async_pending is not None:
                        lifecycle.discard(async_pending["request"], "CANCELLED", "FALLBACK_COMMITTED")
                        async_pending["fallback_discarded"] = True
                splice_commit_pending = None
                if (rolling_splice_pending is not None
                        and not rolling_splice_pending["spliced"]
                        and active_schedule is rolling_splice_pending["composite"]
                        and progress_proposal["selected_progress_s"]
                            > active_schedule.splice_elapsed_s+1e-12):
                    splice_request = rolling_splice_pending["request"]
                    splice_suffix = active_schedule.suffix
                    suffix_first = splice_suffix.sample(0.)
                    splice_sample_s = float(observation.sample_timestamp_s)
                    splice_capture_ns = runtime["wall_session"].source_ns(splice_sample_s)
                    splice_validation = validate_activation(
                        belief=belief,
                        request_sequence=rolling_splice_pending["request_sequence"],
                        schedule=splice_suffix, clearance=clearance,
                        phase=task_state.phase,
                        request_phase=rolling_splice_pending["request_phase"],
                        remaining_s=spec.phase_timeout_s-task_state.phase_elapsed_s,
                        reference_state=np.r_[suffix_first.q_rad, suffix_first.dq_rad_s],
                        now_physics_s=float(plant.data.time),
                        future_handoff=dict(
                            spec=spec, estimated_state=state.copy(),
                            observed_reference_state=reference_state.copy(),
                            estimated_acceleration=split.human_motion_acceleration_rad_s2.copy(),
                            reference_acceleration=suffix_first.ddq_rad_s2.copy(),
                            acceleration_valid=bool(split.human_motion_valid),
                            now_ns=monotonic_ns(),
                            original_capture_ns=splice_request.sensor_capture_ns,
                            revalidation_capture_ns=splice_capture_ns,
                            request_plan_version=splice_suffix.version,
                            original_sample_s=splice_request.source_sample_time_s,
                            revalidation_sample_s=splice_sample_s,
                            age_policy=("simulation" if scientific else "wall")),
                        certificate_geometry_at_request=rolling_splice_pending[
                            "certificate_geometry_signature"])
                    rolling_splice_pending["event"]["splice_revalidation"] = splice_validation
                    if not splice_validation["feasible"]:
                        rolling_splice_pending["event"]["outcome"] = "SPLICE_REJECTED"
                        task_state = abort_episode(task_state, "ROLLING_SUFFIX_SPLICE_REVALIDATION")
                        continue
                    splice_commit_pending = rolling_splice_pending
                    def splice_apply_guard(pending_splice=splice_commit_pending,
                                           fresh_ns=splice_capture_ns):
                        age_original = (int(round((float(plant.data.time)-pending_splice["request"].source_sample_time_s)*1e9))
                                        if scientific else monotonic_ns()-pending_splice["request"].sensor_capture_ns)
                        age_fresh = (int(round((float(plant.data.time)-splice_sample_s)*1e9))
                                     if scientific else monotonic_ns()-fresh_ns)
                        valid = 0 <= age_original < lifecycle.maximum_age_ns and (
                            0 <= age_fresh < lifecycle.maximum_age_ns)
                        if not valid:
                            pending_splice["event"]["outcome"] = "SPLICE_STALE_AT_APPLY"
                        return valid
                    runtime["suffix_splice_apply_guard"] = splice_apply_guard
                def commit_reference_progress(receipt, schedule=active_schedule, proposal=progress_proposal):
                    nonlocal schedule_start_time
                    reference_governor.commit(schedule, proposal, receipt)
                    schedule_start_time += proposal["delay_added_s"]
                    receipt["reference_progress"] = proposal
                    if splice_commit_pending is not None:
                        event = splice_commit_pending["event"]
                        apply_ns = int(receipt["apply_ns"])
                        validation_input = event["splice_revalidation"]["future_handoff_revalidation"]
                        event.update(
                            outcome="SPLICED",
                            actual_splice_ns=apply_ns,
                            actual_splice_physics_s=float(receipt["start_physics_s"]),
                            activation_revalidation_to_splice_ms=(
                                apply_ns-splice_commit_pending["activation_revalidation_capture_ns"])/1e6,
                            splice_revalidation_to_splice_ms=(
                                apply_ns-validation_input["revalidation_capture_ns"])/1e6,
                            suffix_model_provenance_age_ms=(
                                apply_ns-splice_commit_pending["request"].sensor_capture_ns)/1e6,
                            splice_model_sequence=belief.sequence)
                        splice_commit_pending["spliced"] = True
                runtime["reference_progress_commit"] = commit_reference_progress
            else:
                reference = active_schedule.sample(0.0 if runtime.get("plan_to_activate") is not None
                                                   else max(0.0, schedule_elapsed))
        reference_state = np.concatenate([reference.q_rad, reference.dq_rad_s])
        reference_acceleration = reference.ddq_rad_s2.copy()
        force_norm = float(np.linalg.norm(interface.measured_force_world_n))
        trace.append({
            "stage": "TASK",
            "time_s": float(truth.time_s),
            "task_elapsed_s": float(truth.time_s) - task_start_time,
            "physics_steps": int(round(truth.time_s / NOMINAL_PHYSICS_DT_S)),
            "task_phase": task_state.phase.value,
            "q_ref_rad": reference.q_rad.copy(),
            "dq_ref_rad_s": reference.dq_rad_s.copy(),
            "ddq_ref_rad_s2": reference.ddq_rad_s2.copy(),
            "estimated_state": state.copy(),
            "truth_state": np.concatenate([truth.human_q_rad, truth.human_dq_rad_s]),
            "robot_q_rad": truth.robot_q_rad.copy(),
            "robot_dq_rad_s": truth.robot_dq_rad_s.copy(),
            "robot_tau_nm": runtime["last_command"].joint_torque_command_nm.copy(),
            "cuff_position_world_m": measurement.attachment_position_m.copy(),
            "cuff_rotation_world": measurement.attachment_rotation_matrix.copy(),
            "cuff_linear_velocity_world_m_s": measurement.attachment_velocity_m_s.copy(),
            "cuff_angular_velocity_world_rad_s": measurement.attachment_angular_velocity_rad_s.copy(),
            "cuff_force_world_n": interface.measured_force_world_n.copy(),
            "cuff_moment_world_nm": interface.measured_moment_world_nm.copy(),
            "belief_sequence": belief.sequence,
            "beta": belief.beta.copy(),
            "residual_weights_nm": belief.state_residual_weights_nm.copy(),
            "selected_schedule_label": (
                "planning_wait_previous_reference" if planning_wait is not None or async_pending is not None
                else active_schedule.candidate.label),
            "shank_clearance_session_m": shank_clearance.evaluate(state[:2]),
            "dev_d_envelope_clearance_m": (
                clearance.evaluate(state[:2]) if dev_d_rigid_table_reference else float("nan")),
            "dev_d_measured_sleeve_gap_m": (
                clearance.envelope.measured_sleeve_gap(
                    interface.human_position_world_m, interface.human_rotation_world)
                if dev_d_rigid_table_reference else float("nan")),
            "shank_bed_contact_evaluation_only": _shank_bed_contact(plant),
            "active_contact_pairs_evaluation_only": _active_contact_pairs(plant),
            "actual_acceleration_rad_s2": split.human_motion_acceleration_rad_s2.copy(),
            "actual_acceleration_valid": split.human_motion_valid,
            "acceleration_violation": authority.violation,
            "interval_force_cost_n_s": force_norm * CONTROL_DT_S,
        })
        candidate = _candidate(
            f"execute_{len(decisions):03d}_{step:05d}",
            task_state.phase,
            reference.q_rad,
            reference.dq_rad_s,
            spec,
        )
        try:
            command, execution = _execute_interval(
                runtime,
                observation=observation,
                interface=interface,
                measurement=measurement,
                candidate=candidate,
                actuation_enabled=actuation_enabled,
            )
            executed_interval_count += 1
            if online_timing and async_pending is not None:
                lifecycle.fallback(async_pending["request"], execution["actual_interval_duration_s"], str(execution["safety_mode"]))
                async_pending["wait_intervals"] += 1
                async_pending["wait_force_integral_n_s"] += force_norm * execution["actual_interval_duration_s"]
            if planning_wait is not None and active_decision_index is not None:
                decisions[active_decision_index]["deadline_wait_physical_intervals"] += 1
            if (active_decision_index is not None
                    and planning_wait is None and async_pending is None
                    and float(truth.time_s) + 1.0e-12 >= schedule_start_time
                    and not decisions[active_decision_index]["plan_activated"]):
                decisions[active_decision_index]["plan_activated"] = bool(actuation_enabled) if online_timing else True
                decisions[active_decision_index]["activation_timestamp_s"] = float(truth.time_s)
                if online_timing:
                    timing_row = lifecycle.records()[decisions[active_decision_index]["timing_request_id"]]
                    decisions[active_decision_index]["plan_activated"] = timing_row.get("activation_ns") is not None
                    decisions[active_decision_index]["activation_accepted_by_deadline"] = timing_row["outcome"] == "ACTIVATED"
                    decisions[active_decision_index]["stale_plan_age_at_activation_s"] = (
                        None if timing_row["activation_age_ms"] is None else timing_row["activation_age_ms"] / 1000.0)
            safety_counts[str(execution["safety_mode"])] += 1
            trace[-1]["applied_robot_tau_nm"] = (
                command.joint_torque_command_nm.copy() if actuation_enabled else np.zeros(6)
            )
            trace[-1]["allocated_wrench_world"] = command.wrench_total_world.copy()
            trace[-1]["generalized_action_nm"] = execution["generalized_action_nm"]
            trace[-1]["model_transfer"] = execution["model_transfer"]
            trace[-1]["robot_torque_components"] = execution["robot_torque_components"]
            trace[-1]["safety_mode"] = str(execution["safety_mode"])
            if pending is not None:
                if float(truth.time_s) + 1.0e-12 < pending["start_time_s"]:
                    pending["planning_wait_force_integral_n_s"] += (
                        force_norm * CONTROL_DT_S
                    )
                else:
                    pending["measured_force_integral_n_s"] += (
                        force_norm * CONTROL_DT_S
                    )
                    if (
                        not pending["execution_belief_sequences"]
                        or pending["execution_belief_sequences"][-1]
                        != belief.sequence
                    ):
                        pending["execution_belief_sequences"].append(
                            belief.sequence
                        )
        except (RuntimeError, ValueError) as error:
            # The boundary row described a proposed interval that did not
            # execute. Remove it so costs, command traces, and N/N+1 counts do
            # not claim physical work that never occurred.
            attempt = runtime.get("last_execution_attempt", {})
            if attempt.get("applied") or attempt.get("native_steps", 0):
                trace[-1].update(attempt)
            else:
                trace[-1]["execution_rejected_before_apply"] = True
            if (activation_backup is not None and not attempt.get("applied")
                    and str(error) in ("CURRENT_MODEL_ACTIVATION_REVALIDATION", "STALE_PLAN_MAXIMUM_AGE",
                                       "ACTUAL_REMAINING_PHASE_TIME")):
                backup = activation_backup
                active_schedule = backup["schedule"]
                schedule_start_time = backup["start_time"]
                reference_state = backup["reference_state"]
                reference_acceleration = backup["reference_acceleration"]
                fallback_latch = backup["latch"]
                active_decision_index = None
                for key in ("plan_to_activate", "activation_validator", "actual_activation_hook", "reference_progress_commit"):
                    runtime.pop(key, None)
                fallback_event("PRIMARY_REJECTED_ESCAPE_RETAINED", reason=str(error),request_id=backup["request"].request_id)
                activation_backup = None
                continue
            task_state = abort_episode(task_state, f"LOW_LEVEL_EXECUTION:{error}")

    if task_state.phase not in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
        task_state = abort_episode(task_state, "GLOBAL_TASK_TIMEOUT")

    if runtime.get("wall_session") is not None:
        if runtime["wall_session"].active:
            runtime["wall_session"].catch_up("task_terminal_boundary")
            runtime["wall_session"].end_ns = runtime["wall_session"].clock()
            runtime["wall_session"].active = False
        runtime["wall_session"].release_runtime_maintenance()
        if (task_state.phase is TaskPhase.COMPLETE
                and recovery_options.get("causal_return_projection", False)
                and not recovery_options.get("causal_terminal_commit", False)):
            guard = runtime["return_projection_guards"][-1]
            wall = runtime["wall_session"]
            physical_age = float(plant.data.time)-guard["source_sample_time_s"]
            host_age = (wall.end_ns-guard["source_capture_ns"])/1e9
            covered = ((physical_age if scientific else max(physical_age, host_age))
                       <= guard["capture_anchored_horizon_s"]+1e-12)
            return_elapsed = previous_task_state.phase_elapsed_s + task_dt + max(
                0., float(plant.data.time)-physical_now)
            task_elapsed = float(plant.data.time)-task_start_time
            finalization_reason = return_finalization_reason(
                physical_age=physical_age, host_age=(physical_age if scientific else host_age),
                horizon_s=guard["capture_anchored_horizon_s"],
                return_elapsed_s=return_elapsed, phase_timeout_s=spec.phase_timeout_s,
                task_elapsed_s=task_elapsed, task_timeout_s=task_timeout_s)
            runtime["return_projection_finalization"] = {
                "source_sample_time_s": guard["source_sample_time_s"],
                "source_capture_ns": guard["source_capture_ns"],
                "final_native_time_s": float(plant.data.time), "final_host_ns": wall.end_ns,
                "source_to_final_physical_s": physical_age,
                "source_to_final_host_s": host_age,
                "capture_anchored_horizon_s": guard["capture_anchored_horizon_s"],
                "covered": covered, "truth_used_for_decision": False,
                "actual_return_elapsed_s": return_elapsed,
                "original_phase_timeout_s": spec.phase_timeout_s,
                "actual_task_elapsed_s": task_elapsed,
                "original_task_timeout_s": task_timeout_s,
                "reason": finalization_reason,
                "accepted": finalization_reason is None}
            if finalization_reason is not None:
                # Keep the real final native state. Reject the provisional
                # completion instead of shortening physics or changing its time.
                task_state = abort_episode(replace(previous_task_state,
                    phase_elapsed_s=return_elapsed), finalization_reason)
                trace[-1].update(task_phase=TaskPhase.ABORTED.value,
                    provisional_terminal_phase=TaskPhase.COMPLETE.value,
                    terminal_commit_physics_s=float(plant.data.time))
                transitions[-1].update(to=TaskPhase.ABORTED.value,
                    proposed_to=TaskPhase.COMPLETE.value,
                    state_source_time_s=guard["source_sample_time_s"],
                    time_s=float(plant.data.time), trigger=task_state.abort_reason)
                if learning_records and learning_records[-1].get("completion") == TaskPhase.COMPLETE.value:
                    learning_records[-1]["completion"] = TaskPhase.ABORTED.value
    if lifecycle is not None:
        if runtime_capture is not None:
            persist_runtime_artifacts(output_dir, runtime_capture)
        lifecycle.close(task_state.abort_reason or task_state.phase.value)
    if lifecycle is not None:
        timing_records = lifecycle.records()
        for item in decisions:
            if "timing_request_id" in item:
                record = timing_records[item["timing_request_id"]]
                item["plan_activated"] = record.get("activation_ns") is not None
                item["actual_activation_monotonic_ns"] = record.get("activation_ns")
                item["activation_accepted_by_deadline"] = record["outcome"] == "ACTIVATED"
                item["activation_outcome"] = record["outcome"]
                item["activation_rejected_reason"] = record["reason"]
    task_rows = [row for row in trace if row["stage"] == "TASK"]
    forces = np.asarray([row["cuff_force_world_n"] for row in task_rows]) if task_rows else np.empty((0, 3))
    moments = np.asarray([row["cuff_moment_world_nm"] for row in task_rows]) if task_rows else np.empty((0, 3))
    robot_tau = np.asarray([row.get("applied_robot_tau_nm", np.zeros(6)) for row in task_rows]) if task_rows else np.empty((0, 6))
    summary = {
        "schema": ("full3d_dev_a_recovery_v1.executed_case.v1" if dev_a_recovery else SCHEMA),
        "execution_mode": mode.value,
        "evidence_category": "development_full3d_physical_execution",
        "status": task_state.phase.value,
        "abort_reason": task_state.abort_reason,
        "actuation_enabled": actuation_enabled,
        "commissioning": {
            "duration_s": commissioning_duration,
            "sample_count": len(commissioning_samples),
            "effective_reference_waypoints_rad": commissioning_waypoints.copy(),
            "dev_d_reference_enabled": bool(dev_d_rigid_table_reference),
            "dev_d_reference_events": commissioning_reference_events,
            "cuff_reference_origin": runtime.get("commissioning_cuff_reference_origin"),
            "geometry_fit": (fit.record() if fit is not None else {
                "accepted": False, "reason": "NOT_ATTEMPTED_FIXED_POPULATION_ARM"}),
            "aligned_update_count": len(commissioning_updates),
            "aligned_update_history": commissioning_updates,
            "population_beta_initial": nominal_base_parameters(control_human),
            "population_residual_weights_initial_nm": np.zeros((2, 5)),
            "handoff_belief": commissioning_handoff_belief.value_state_record(),
            "history_preserved_at_handoff": True,
        },
        "task": {
            "physics_duration_s": 0.0 if not task_rows else task_rows[-1]["time_s"] - task_start_time,
            "trace_node_count": len(task_rows),
            "boundary_sample_count": len(task_rows),
            "integration_interval_count": executed_interval_count,
            "boundary_interval_relation_holds": bool(
                (not task_rows and executed_interval_count == 0)
                or len(task_rows) == executed_interval_count + 1
            ),
            "decision_count": len(decisions),
            "phase_transitions": transitions,
            "learning_transition_count": len(learning_records),
            "continual_adaptation_update_count": len(adaptation_trace),
            "final_belief_sequence": updater.sequence,
            "accepted_beta_update_count": updater.dynamics.accepted_updates,
            "residual_update_count": updater.residual_update_count,
            "peak_force_n": None if not len(forces) else float(np.max(np.linalg.norm(forces, axis=1))),
            "peak_moment_nm": None if not len(moments) else float(np.max(np.linalg.norm(moments, axis=1))),
            "force_integral_n_s": float(sum(row["interval_force_cost_n_s"] for row in task_rows)),
            "peak_robot_torque_fraction": None if not len(robot_tau) else float(np.max(np.abs(robot_tau) / plant.torque_limits_nm)),
            "shank_bed_contact_sample_count_evaluation_only": sum(bool(row["shank_bed_contact_evaluation_only"]) for row in task_rows),
            "active_contact_pair_counts_evaluation_only": dict(
                Counter(
                    " <-> ".join(pair)
                    for row in task_rows
                    for pair in row["active_contact_pairs_evaluation_only"]
                )
            ),
            "mujoco_warning_counts": plant.warning_counts(),
        },
        "session_clearance_contract": clearance.record(),
        "timing": {
            "physics_dt_s": NOMINAL_PHYSICS_DT_S,
            "low_level_dt_s": CONTROL_DT_S,
            "adaptation_dt_s": ADAPTATION_DT_S,
            "high_level_planning_runtime_ms": [row["planning_runtime_ms_measured"] for row in decisions],
            "requests": [] if lifecycle is None else lifecycle.records(),
            "commissioning_and_recovery_planning_synchronous": True,
            "asynchronous_physics_during_planning": observed_planner_physics_overlap(runtime),
            "whole_session_wall_physics": runtime.get("wall_session") is not None,
            "raw_all_outcome_timing_authority": "runtime_artifacts.json requests and wall_physics",
            "physics_advances_under_controlled_planning_delay_replay": bool(
                simulate_planning_latency and not online_timing
            ),
            "controlled_latency_replay": bool(simulate_planning_latency and not online_timing),
            "classification": (
                "monotonic_async_task_development_evidence" if online_timing else
                "timing_aware_full_physics_development_evidence"
                if simulate_planning_latency
                else "synchronous_debug_evidence_only"
            ),
            "all_reference_boundaries_q_dq_ddq_continuous": bool(
                all(
                    max(abs(value) for value in decision["reference_boundary_continuity"][field])
                    <= 1.0e-10
                    for decision in decisions
                    if decision["reference_boundary_continuity"] is not None
                    for field in (
                        "q_boundary_jump_rad",
                        "dq_boundary_jump_rad_s",
                        "ddq_boundary_jump_rad_s2",
                    )
                )
            ),
        },
        "truth_firewall": {
            "controller_inputs": ["robot_q_dq", "robot_cuff_pose_twist", "physical_cuff_force_moment", "registered_task", "prior_and_online_belief"],
            "human_q_dq_truth_in_controller": False,
            "hidden_geometry_in_controller": False,
            "evaluation_truth_saved_separately": True,
        },
        "decisions": decisions,
        "adaptation_trace": adaptation_trace,
        "dev_a_recovery": recovery_result,
        "startup_execution_pose_alignment": runtime.get("startup_alignment_record"),
        "high_rom_coordination_candidate": candidate_mode if (qualification_case or {}).get("research_model") == "high_rom_v1" else None,
        "reference_pacing": {"enabled": recovery_options.get("reference_pacing", False),
            "velocity_fraction": scheduler.reference_velocity_fraction,
            "acceleration_fraction": scheduler.reference_acceleration_fraction,
            "scope": "task_and_active_recovery_reference_schedules_only",
            "actual_limits_and_timeouts_unchanged": True},
        "dev_c_model_transfer": (None if transfer_config is None else {
            "config": transfer_config,
            "events": runtime["model_transfer"].events,
            "last_record": runtime["model_transfer"].snapshot(),
            "last_fully_realized_version": runtime["model_transfer"].last_realized_version,
            "latest_accepted_version": runtime["model_transfer"].accepted_version,
        }),
        "learning_records": learning_records,
        "safety_mode_counts": dict(safety_counts),
        "dependencies": {
            "plant": "Stage5CR12SensorBoundaryPlant",
            "robot": "CR12TorqueRobot / cr12_v0.xml",
            "interface": "SpringDamperCoupledUR10eHumanV2 explicit Kelvin-Voigt interface",
            "human": "Human V2 embedded in MuJoCo scene",
        },
        "provenance": {
            "config_path": str(config_path),
            "config_schema": config["schema"],
            "result_schema": ("full3d_dev_a_recovery_v1.executed_case.v1"
                              if dev_a_recovery else SCHEMA),
            "dev_a_recovery_mode": bool(dev_a_recovery),
            "dev_d_rigid_table_reference_mode": bool(dev_d_rigid_table_reference),
            "numpy_version": np.__version__,
            "mujoco_version": mujoco.__version__,
        },
    }
    if qualification_case is not None:
        physical_audit = runtime["true_physics_monitor"].record()
        summary["evidence_category"] = (
            "formal_fresh_full3d_qualification" if formal_qualification
            else "development_varied_full3d_physical_execution")
        summary["qualification"] = {
            "contract": qualification_contract,
            "case_key": qualification_case["case_key"],
            "arm": qualification_arm,
            "hidden_case_evaluation_only": qualification_case,
            "true_physics": physical_audit,
            "physical_interval_moment_integral_nm_s": float(sum(
                np.linalg.norm(task_rows[index]["cuff_moment_world_nm"])
                * (task_rows[index + 1]["time_s"] - task_rows[index]["time_s"])
                for index in range(min(executed_interval_count, max(0, len(task_rows) - 1)))
            )),
        }
        summary["task"]["minimum_true_physical_clearance_m_evaluation_only"] = (
            physical_audit["minimum_clearance_m"]["TASK"])
        summary["task"]["minimum_session_clearance_m_deployable"] = (
            None if not task_rows else min(float(row["shank_clearance_session_m"])
                                            for row in task_rows))
        if recovery_result is not None:
            recovery_result["minimum_true_physical_clearance_m_evaluation_only"] = (
                physical_audit["minimum_clearance_m"]["ACTIVE_RECOVERY"]
            )
            recovery_result["shank_bed_contact_physical_steps_evaluation_only"] = (
                physical_audit["shank_bed_contact_steps"]["ACTIVE_RECOVERY"]
            )
    (output_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "learning_transitions.jsonl").write_text(
        "".join(json.dumps(_jsonable(row), sort_keys=True) + "\n" for row in learning_records),
        encoding="utf-8",
    )
    snapshot_config = dict(config)
    if dev_a_recovery:
        snapshot_config["dev_a_recovery"] = recovery_config
    if transfer_config is not None:
        snapshot_config["dev_c_bumpless_transfer"] = transfer_config
    (output_dir / "config_snapshot.json").write_text(
        json.dumps(snapshot_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(
        output_dir / "trace.npz",
        time_s=np.asarray([row["time_s"] for row in trace]),
        stage=np.asarray([row["stage"] for row in trace]),
        estimated_human_state_rad_rad_s=np.asarray([row["estimated_state"] for row in trace]),
        evaluation_only_human_state_rad_rad_s=np.asarray([row["truth_state"] for row in trace]),
        reference_q_rad=np.asarray([row["q_ref_rad"] for row in trace]),
        reference_dq_rad_s=np.asarray([row["dq_ref_rad_s"] for row in trace]),
        cr12_q_rad=np.asarray([row["robot_q_rad"] for row in trace]),
        cr12_dq_rad_s=np.asarray([row["robot_dq_rad_s"] for row in trace]),
        cr12_actuator_command_nm=np.asarray(
            [row.get("applied_robot_tau_nm", row["robot_tau_nm"]) for row in trace]
        ),
        robot_torque_component_base_nm=np.asarray([
            row.get("robot_torque_components", {}).get("base", np.full(6, np.nan))
            for row in trace
        ]),
        robot_torque_component_position_nm=np.asarray([
            row.get("robot_torque_components", {}).get("position", np.full(6, np.nan))
            for row in trace
        ]),
        robot_torque_component_velocity_nm=np.asarray([
            row.get("robot_torque_components", {}).get("velocity", np.full(6, np.nan))
            for row in trace
        ]),
        robot_torque_component_allocator_nm=np.asarray([
            row.get("robot_torque_components", {}).get("allocator", np.full(6, np.nan))
            for row in trace
        ]),
        robot_torque_component_clipping_nm=np.asarray([
            row.get("robot_torque_components", {}).get("clipping", np.full(6, np.nan))
            for row in trace
        ]),
        physical_cuff_position_world_m=np.asarray(
            [row["cuff_position_world_m"] for row in trace]
        ),
        physical_cuff_rotation_world=np.asarray(
            [row["cuff_rotation_world"] for row in trace]
        ),
        physical_cuff_linear_velocity_world_m_s=np.asarray(
            [row["cuff_linear_velocity_world_m_s"] for row in trace]
        ),
        physical_cuff_angular_velocity_world_rad_s=np.asarray(
            [row["cuff_angular_velocity_world_rad_s"] for row in trace]
        ),
        physical_cuff_force_world_n=np.asarray([row["cuff_force_world_n"] for row in trace]),
        physical_cuff_moment_world_nm=np.asarray([row["cuff_moment_world_nm"] for row in trace]),
        applied_generalized_action_nm=np.asarray(
            [row.get("generalized_action_nm", np.zeros(2)) for row in trace]
        ),
        model_transfer_fraction_new=np.asarray([
            (float("nan") if row.get("model_transfer") is None
             else row["model_transfer"]["fraction_new"]) for row in trace
        ]),
        model_transfer_accepted_version=np.asarray([
            ("" if row.get("model_transfer") is None
             else row["model_transfer"]["accepted_version"]) for row in trace
        ]),
        model_transfer_fully_active_version=np.asarray([
            ("" if row.get("model_transfer") is None
             else row["model_transfer"]["fully_active_version"]) for row in trace
        ]),
        allocated_wrench_world=np.asarray(
            [row.get("allocated_wrench_world", np.full(6, np.nan)) for row in trace]
        ),
        belief_sequence=np.asarray([row["belief_sequence"] for row in trace]),
        task_beta=np.asarray([row["beta"] for row in task_rows]).reshape(-1, 11),
        task_residual_weights_nm=np.asarray(
            [row["residual_weights_nm"] for row in task_rows]).reshape(-1, 2, 5),
        task_phase=np.asarray([row["task_phase"] for row in trace]),
        selected_schedule_label=np.asarray(
            [
                str(row.get("selected_schedule_label") or "")
                if row["stage"] == "TASK"
                else str(row.get("selected_schedule_label") or row["stage"])
                for row in trace
            ]
        ),
        recovery_subphase=np.asarray(
            [str(row.get("recovery_subphase") or "") for row in trace]
        ),
        desired_cuff_position_world_m=np.asarray(
            [row.get("desired_cuff_position_world_m", np.full(3, np.nan)) for row in trace]
        ),
        desired_cuff_rotation_world=np.asarray(
            [row.get("desired_cuff_rotation_world", np.full((3, 3), np.nan)) for row in trace]
        ),
        desired_cuff_twist_world=np.asarray(
            [row.get("desired_cuff_twist_world", np.full(6, np.nan)) for row in trace]
        ),
        controller_model_version=np.asarray(
            [str(row.get("model_version") or "") for row in trace]
        ),
        terminal_boundary_node=np.asarray(
            [bool(row.get("terminal_boundary_node", False)) for row in trace]
        ),
        physics_steps=np.asarray([row["physics_steps"] for row in trace]),
        reference_ddq_rad_s2=np.asarray(
            [row.get("ddq_ref_rad_s2", np.zeros(2)) for row in trace]
        ),
        actual_human_acceleration_rad_s2=np.asarray(
            [row.get("actual_acceleration_rad_s2", np.full(2, np.nan)) for row in trace]
        ),
        actual_human_acceleration_valid=np.asarray(
            [bool(row.get("actual_acceleration_valid", False)) for row in trace]
        ),
        acceleration_limit_violation=np.asarray(
            [bool(row.get("acceleration_violation", False)) for row in trace]
        ),
        session_shank_clearance_m=np.asarray(
            [float(row.get("shank_clearance_session_m", np.nan)) for row in trace]
        ),
        dev_d_session_envelope_clearance_m=np.asarray(
            [float(row.get("dev_d_envelope_clearance_m", np.nan)) for row in trace]
        ),
        dev_d_measured_sleeve_gap_m=np.asarray(
            [float(row.get("dev_d_measured_sleeve_gap_m", np.nan)) for row in trace]
        ),
        shank_bed_contact_evaluation_only=np.asarray(
            [bool(row.get("shank_bed_contact_evaluation_only", False)) for row in trace]
        ),
        active_contact_pairs_evaluation_only_json=np.asarray(
            [
                json.dumps(row.get("active_contact_pairs_evaluation_only", []))
                for row in trace
            ]
        ),
        interval_force_cost_n_s=np.asarray(
            [float(row.get("interval_force_cost_n_s", 0.0)) for row in trace]
        ),
        safety_mode=np.asarray(
            [str(row.get("safety_mode", "")) for row in trace]
        ),
    )
    if session_context is not None:
        session_context.update(runtime=runtime, updater=updater, fit=fit,
                               spec=spec, config=config,
                               repetition_index=session_context.get("repetition_index", 0)+1,
                               end_time_s=float(plant.data.time),
                               final_belief=updater.snapshot())
    return summary


__all__ = [
    "SCHEMA",
    "SessionClearanceContract",
    "nominal_control_geometry",
    "nominal_control_model",
    "run_executed_case",
]


def run_executed_case(output_dir: Path, *, runtime_capture: dict[str, Any] | None = None,
                      **kwargs: Any) -> dict[str, Any]:
    """Run with guaranteed worker cleanup and campaign all-outcome persistence."""
    capture = {} if runtime_capture is None else runtime_capture
    enabled = bool(kwargs.get("autonomous_recovery_options"))
    try:
        return _run_executed_case(output_dir, runtime_capture=capture, **kwargs)
    except BaseException as error:
        capture["exception"] = f"{type(error).__name__}:{error}"
        lifecycle = capture.get("runtime", {}).get("plan_lifecycle")
        if lifecycle is not None and lifecycle._outstanding is not None:
            lifecycle.fail_pending(capture["exception"])
        raise
    finally:
        runtime = capture.get("runtime", {})
        wall = runtime.get("wall_session")
        if wall is not None and wall.active:
            try:
                wall.catch_up("active_session_finalization", finalizing=True)
            except BaseException as error:
                capture.setdefault("finalization_exception", f"{type(error).__name__}:{error}")
            wall.end_ns = wall.clock()
            wall.active = False
        if wall is not None:
            wall.release_runtime_maintenance()
        if enabled:
            persist_runtime_artifacts(output_dir, capture)
        lifecycle = runtime.get("plan_lifecycle")
        if lifecycle is not None:
            lifecycle.close(capture.get("exception", "RUN_ENDED_BEFORE_ACTIVATION"))
        if enabled:
            persist_runtime_artifacts(output_dir, capture)
