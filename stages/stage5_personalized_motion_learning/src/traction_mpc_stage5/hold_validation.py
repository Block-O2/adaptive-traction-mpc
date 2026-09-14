"""Engineering-only local loaded-HOLD validation for Stage 5."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.track_brake import BRAKE, TrackBrakeSupervisor

from .baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    InterfaceAwareHumanStateObserver,
)
from .geometry import STAGE5_GEOMETRY
from .hold_stabilizer import (
    LoadedEquilibriumHoldStabilizer,
    LoadedHoldEquilibrium,
    solve_loaded_hold_equilibrium,
)
from .human import STAGE5_HUMAN
from .ik import solve_stage5_ik
from .mechanics import NOMINAL_PHYSICS_DT_S
from .task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, GoalTaskSpec, at_goal


CONTROL_DT_S = 0.005
FIXED_HUMAN_MODEL_VERSION = "stage5_fixed_registered_human_v1"


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


def _robot_pose_from_interface(
    human_pose: RigidTransform,
    displacement_human_m: np.ndarray,
    rotation_error_human_rad: np.ndarray,
) -> RigidTransform:
    rest_x = np.asarray(CONTROLLER_NOMINAL_INTERFACE.rest_translation_human_m)
    rest_theta = np.asarray(
        CONTROLLER_NOMINAL_INTERFACE.rest_rotation_rotvec_human_rad
    )
    r_world = human_pose.rotation @ (rest_x + displacement_human_m)
    robot_rotation = (
        human_pose.rotation
        @ Rotation.from_rotvec(rotation_error_human_rad).as_matrix()
        @ Rotation.from_rotvec(rest_theta).as_matrix()
    )
    return RigidTransform(robot_rotation, human_pose.translation + r_world)


def _set_loaded_state(
    plant: Stage5SensorBoundaryPlant,
    human_model: Any,
    equilibrium: LoadedHoldEquilibrium,
    *,
    q_offset_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    translation_offset_human_m: np.ndarray,
    rotation_offset_human_rad: np.ndarray,
) -> None:
    q = equilibrium.q_goal_rad + np.asarray(q_offset_rad, dtype=float)
    human_pose = human_model.geometry.cuff_pose(q)
    robot_pose = _robot_pose_from_interface(
        human_pose,
        equilibrium.interface_displacement_human_m
        + np.asarray(translation_offset_human_m, dtype=float),
        equilibrium.interface_rotation_error_human_rad
        + np.asarray(rotation_offset_human_rad, dtype=float),
    )
    world_from_end_effector = robot_pose.compose(
        STAGE5_GEOMETRY.end_effector_from_cuff.inverse()
    )
    base_from_end_effector = STAGE5_GEOMETRY.world_from_base.inverse().compose(
        world_from_end_effector
    )
    robot_q = solve_stage5_ik(
        plant._ik_robot,
        base_from_end_effector,
        previous_q_rad=plant.data.qpos[plant.robot_qpos_indices].copy(),
    )
    plant.data.qpos[plant.human_qpos_indices] = q
    plant.data.qpos[plant.robot_qpos_indices] = robot_q
    plant.data.qvel[:] = 0.0
    plant.data.qvel[plant.human_dof_indices] = np.asarray(dq_rad_s, dtype=float)
    plant.data.ctrl[:] = 0.0
    plant.observe()


def _longest_true_interval(time_s: np.ndarray, predicate: np.ndarray) -> float:
    longest = 0.0
    start: float | None = None
    previous = 0.0
    for time, valid in zip(time_s, predicate, strict=True):
        if valid:
            if start is None:
                start = float(time)
            previous = float(time)
        elif start is not None:
            longest = max(longest, previous - start + CONTROL_DT_S)
            start = None
    if start is not None:
        longest = max(longest, previous - start + CONTROL_DT_S)
    return float(longest)


def _run_local_case(
    output_dir: Path,
    *,
    name: str,
    duration_s: float,
    spec: GoalTaskSpec,
    q_offset_deg: tuple[float, float] = (0.0, 0.0),
    dq_deg_s: tuple[float, float] = (0.0, 0.0),
    translation_offset_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_offset_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    start_truth = plant.reset(np.asarray(spec.start_return_target_rad))
    initial_measurement = CausalMeasurementLayer(
        MeasurementCase(name=f"{name}-model", update_rate_hz=200.0, latency_s=0.0),
        start_truth,
    ).current
    estimator = FixedStage5Estimator(
        initial_measurement.attachment_position_m,
        initial_measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    )
    _estimator_observe(estimator, initial_measurement)
    human_model = estimator.model
    allocator = default_engineering_cuff_allocator()
    equilibrium = solve_loaded_hold_equilibrium(spec, human_model, allocator)
    stabilizer = LoadedEquilibriumHoldStabilizer(equilibrium, human_model)
    plant.neutral_robot_q = initial_measurement.robot_q_rad.copy()
    _set_loaded_state(
        plant,
        human_model,
        equilibrium,
        q_offset_rad=np.radians(q_offset_deg),
        dq_rad_s=np.radians(dq_deg_s),
        translation_offset_human_m=1.0e-3 * np.asarray(translation_offset_mm),
        rotation_offset_human_rad=np.radians(rotation_offset_deg),
    )
    truth = plant.observe()
    measurement_layer = CausalMeasurementLayer(
        MeasurementCase(name=name, update_rate_hz=200.0, latency_s=0.0), truth
    )
    interface_observer = InterfaceAwareHumanStateObserver()
    supervisor = TrackBrakeSupervisor()
    physics_substeps = int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    time_trace: list[float] = []
    state_trace: list[np.ndarray] = []
    truth_state_trace: list[np.ndarray] = []
    force_trace: list[np.ndarray] = []
    moment_trace: list[np.ndarray] = []
    translation_trace: list[np.ndarray] = []
    rotation_trace: list[np.ndarray] = []
    predicate_trace: list[bool] = []
    action_trace: list[np.ndarray] = []
    stabilizer_runtime_ms: list[float] = []
    total_control_runtime_ms: list[float] = []
    safety_statuses: list[str] = []
    first_decomposition: dict[str, Any] | None = None
    force_gate_events = 0
    brake_events = 0
    continuous_hold_s = 0.0
    maximum_recovery_budget_s = 1.0

    steps = int(
        np.ceil((duration_s + maximum_recovery_budget_s) / CONTROL_DT_S)
    )
    for _ in range(steps + 1):
        truth = plant.observe()
        measurement = measurement_layer.update(truth)
        _estimator_observe(estimator, measurement)
        observation, interface_state = interface_observer.update(
            measurement,
            human_model,
            human_model_version=FIXED_HUMAN_MODEL_VERSION,
        )
        started = perf_counter()
        action_started = perf_counter()
        action, reference, filter_result, _ = stabilizer.filter_executable_command(
            plant=plant,
            measurement=measurement,
            observation=observation,
            interface_state=interface_state,
            cuff_allocator=allocator,
        )
        stabilizer_runtime_ms.append(1000.0 * (perf_counter() - action_started))
        decision = supervisor.command(
            plant=plant,
            measurement=measurement,
            estimated_state=observation.as_array(),
            human_model=human_model,
            cuff_allocator=allocator,
            track_reference=reference,
            proposed_action_nm=action,
            mpc_status=SAFE_ACTION,
            proposed_filter_result=filter_result,
        )
        total_control_runtime_ms.append(1000.0 * (perf_counter() - started))
        if decision.safety_filter is not None:
            safety_statuses.append(str(decision.safety_filter["status"]))
        brake_events += int(decision.mode == BRAKE)
        interface_truth, _, _ = plant.interface_diagnostics()
        estimated_state = observation.as_array()
        time_trace.append(float(truth.time_s))
        state_trace.append(estimated_state.copy())
        truth_state_trace.append(
            np.concatenate([truth.human_q_rad, truth.human_dq_rad_s])
        )
        force_trace.append(np.asarray(truth.cuff_force_vector_n).copy())
        moment_trace.append(np.asarray(truth.cuff_moment_vector_nm).copy())
        translation_trace.append(interface_truth.displacement_human_m.copy())
        rotation_trace.append(interface_truth.rotation_error_human_rad.copy())
        predicate = at_goal(
                spec,
                estimated_state[:2],
                estimated_state[2:],
                spec.outbound_goal_target_rad,
            )
        predicate_trace.append(predicate)
        continuous_hold_s = (
            continuous_hold_s + CONTROL_DT_S if predicate else 0.0
        )
        action_trace.append(action.copy())
        if continuous_hold_s >= duration_s - 1.0e-9:
            break
        if decision.executable_preview is None:
            break
        if first_decomposition is None:
            command = decision.executable_preview.command
            first_decomposition = {
                "force_position_n": command.force_position_n.tolist(),
                "force_velocity_n": command.force_velocity_n.tolist(),
                "force_allocator_n": command.force_allocator_n.tolist(),
                "force_total_n": command.force_total_n.tolist(),
                "moment_orientation_nm": command.moment_orientation_nm.tolist(),
                "moment_angular_velocity_nm": (
                    command.moment_angular_velocity_nm.tolist()
                ),
                "moment_allocator_nm": command.moment_allocator_nm.tolist(),
                "moment_total_nm": command.moment_total_nm.tolist(),
                "joint_torque_clipping_norm_nm": float(
                    np.linalg.norm(
                        command.joint_torque_command_nm
                        - command.unclipped_joint_torque_nm
                    )
                ),
            }
        if decision.mode == BRAKE or decision.terminate:
            break
        plant.apply_executable_command(decision.executable_preview.command)
        for _ in range(physics_substeps):
            truth = plant.step()
        if np.linalg.norm(truth.cuff_force_vector_n) > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9:
            force_gate_events += 1

    trace = {
        "time_s": np.asarray(time_trace),
        "estimated_state_rad_rad_s": np.asarray(state_trace),
        "evaluation_state_rad_rad_s": np.asarray(truth_state_trace),
        "physical_cuff_force_world_n": np.asarray(force_trace),
        "physical_cuff_moment_world_nm": np.asarray(moment_trace),
        "interface_translation_human_m": np.asarray(translation_trace),
        "interface_rotation_human_rad": np.asarray(rotation_trace),
        "at_goal": np.asarray(predicate_trace),
        "action_nm": np.asarray(action_trace),
    }
    case_dir = output_dir / name
    case_dir.mkdir(parents=True, exist_ok=False)
    np.savez(case_dir / "trace.npz", **trace)
    time_values = trace["time_s"]
    force_norm = np.linalg.norm(trace["physical_cuff_force_world_n"], axis=1)
    moment_norm = np.linalg.norm(trace["physical_cuff_moment_world_nm"], axis=1)
    state_error = trace["estimated_state_rad_rad_s"] - trace["evaluation_state_rad_rad_s"]
    invalid_indices = np.flatnonzero(~trace["at_goal"])
    settled_recovery_time_s = (
        0.0
        if not len(invalid_indices)
        else (
            float(time_values[invalid_indices[-1] + 1])
            if invalid_indices[-1] + 1 < len(time_values)
            else None
        )
    )
    result = {
        "name": name,
        "requested_duration_s": duration_s,
        "requested_continuous_hold_s": duration_s,
        "maximum_recovery_budget_s": maximum_recovery_budget_s,
        "completed_duration_s": float(time_values[-1]),
        "initialization": {
            "q_offset_deg": list(q_offset_deg),
            "dq_deg_s": list(dq_deg_s),
            "translation_offset_mm": list(translation_offset_mm),
            "rotation_offset_deg": list(rotation_offset_deg),
        },
        "longest_continuous_hold_s": _longest_true_interval(
            time_values, trace["at_goal"]
        ),
        "requested_continuous_hold_achieved": bool(
            _longest_true_interval(time_values, trace["at_goal"])
            >= duration_s - 1.0e-9
        ),
        "first_recovery_time_s": (
            float(time_values[np.flatnonzero(trace["at_goal"])[0]])
            if np.any(trace["at_goal"])
            else None
        ),
        "settled_recovery_time_s": settled_recovery_time_s,
        "terminal_q_error_deg": np.degrees(
            trace["estimated_state_rad_rad_s"][-1, :2] - equilibrium.q_goal_rad
        ).tolist(),
        "terminal_dq_deg_s": np.degrees(
            trace["estimated_state_rad_rad_s"][-1, 2:]
        ).tolist(),
        "peak_force_n": float(np.max(force_norm)),
        "cumulative_force_n_s": float(np.trapezoid(force_norm, time_values)),
        "peak_moment_nm": float(np.max(moment_norm)),
        "peak_interface_translation_mm": float(
            1000.0 * np.max(np.linalg.norm(trace["interface_translation_human_m"], axis=1))
        ),
        "peak_interface_rotation_deg": float(
            np.degrees(np.max(np.linalg.norm(trace["interface_rotation_human_rad"], axis=1)))
        ),
        "state_estimation_rmse": {
            "q_deg": np.degrees(
                np.sqrt(np.mean(state_error[:, :2] ** 2, axis=0))
            ).tolist(),
            "dq_deg_s": np.degrees(
                np.sqrt(np.mean(state_error[:, 2:] ** 2, axis=0))
            ).tolist(),
        },
        "stabilizer_runtime_ms": {
            "mean": float(np.mean(stabilizer_runtime_ms)),
            "p95": float(np.percentile(stabilizer_runtime_ms, 95.0)),
            "max": float(np.max(stabilizer_runtime_ms)),
        },
        "total_control_runtime_ms": {
            "mean": float(np.mean(total_control_runtime_ms)),
            "p95": float(np.percentile(total_control_runtime_ms, 95.0)),
            "max": float(np.max(total_control_runtime_ms)),
        },
        "safety_filter_status_counts": dict(Counter(safety_statuses)),
        "force_gate_event_count": force_gate_events,
        "brake_event_count": brake_events,
        "mujoco_warning_counts": plant.warning_counts(),
        "first_executable_decomposition": first_decomposition,
    }
    (case_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def _equilibrium_record(equilibrium: LoadedHoldEquilibrium) -> dict[str, Any]:
    return {
        "q_goal_deg": np.degrees(equilibrium.q_goal_rad).tolist(),
        "dq_goal_deg_s": [0.0, 0.0],
        "required_human_generalized_input_nm": (
            equilibrium.required_human_generalized_input_nm.tolist()
        ),
        "physical_human_wrench_world": equilibrium.physical_human_wrench_world.tolist(),
        "robot_site_support_wrench_world": (
            equilibrium.robot_site_support_wrench_world.tolist()
        ),
        "interface_translation_human_mm": (
            1000.0 * equilibrium.interface_displacement_human_m
        ).tolist(),
        "interface_rotation_error_human_deg": np.degrees(
            equilibrium.interface_rotation_error_human_rad
        ).tolist(),
        "human_cuff_position_world_m": equilibrium.human_cuff_pose_world.translation.tolist(),
        "human_cuff_rotation_world": equilibrium.human_cuff_pose_world.rotation.tolist(),
        "robot_cuff_position_world_m": equilibrium.robot_cuff_pose_world.translation.tolist(),
        "robot_cuff_rotation_world": equilibrium.robot_cuff_pose_world.rotation.tolist(),
        "equilibrium_feedback_force_world_n": (
            equilibrium.equilibrium_feedback_force_world_n.tolist()
        ),
        "equilibrium_feedback_moment_world_nm": (
            equilibrium.equilibrium_feedback_moment_world_nm.tolist()
        ),
        "controller_nominal_interface_version": (
            CONTROLLER_NOMINAL_INTERFACE.model_version
        ),
        "hardware_calibrated": False,
    }


def run_local_hold_validation(
    output_dir: Path,
    *,
    spec: GoalTaskSpec = PROVISIONAL_LOW_MODERATE_GOAL_TASK,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite validation output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    model_plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    truth = model_plant.reset(np.asarray(spec.start_return_target_rad))
    measurement = CausalMeasurementLayer(
        MeasurementCase(name="equilibrium-model", update_rate_hz=200.0, latency_s=0.0),
        truth,
    ).current
    model = FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        np.asarray(spec.start_return_target_rad),
    ).model
    equilibrium = solve_loaded_hold_equilibrium(
        spec, model, default_engineering_cuff_allocator()
    )
    cases = []
    combined = {
        # Small relative to the 20/35 deg task, but deliberately outside the
        # 1 deg / 2 deg/s GoalTaskSpec completion set at initialization.
        "q_offset_deg": (1.25, -1.40),
        "dq_deg_s": (3.0, -3.5),
        "translation_offset_mm": (0.25, 0.0, -0.20),
        "rotation_offset_deg": (0.0, 0.15, 0.0),
    }
    for duration in (0.5, 2.0, 5.0, 10.0):
        cases.append(
            _run_local_case(
                output_dir,
                name=f"combined_perturbation_{str(duration).replace('.', 'p')}s",
                duration_s=duration,
                spec=spec,
                **combined,
            )
        )
    cases.extend(
        [
            _run_local_case(
                output_dir,
                name="equilibrium_2p0s",
                duration_s=2.0,
                spec=spec,
            ),
            _run_local_case(
                output_dir,
                name="q_dq_perturbation_2p0s",
                duration_s=2.0,
                spec=spec,
                q_offset_deg=(1.25, -1.40),
                dq_deg_s=(3.0, -3.5),
            ),
            _run_local_case(
                output_dir,
                name="interface_perturbation_2p0s",
                duration_s=2.0,
                spec=spec,
                translation_offset_mm=(0.25, 0.0, -0.20),
                rotation_offset_deg=(0.0, 0.15, 0.0),
            ),
        ]
    )
    summary = {
        "evidence_category": "engineering_smoke_only",
        "controller": "stage5_loaded_equilibrium_local_hold_v1",
        "equilibrium": _equilibrium_record(equilibrium),
        "cases": cases,
        "learning_enabled": False,
        "plant_interface_mismatch": False,
        "stage3_stage4_modified": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


__all__ = ["run_local_hold_validation"]
