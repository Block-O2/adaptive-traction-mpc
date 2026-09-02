#!/usr/bin/env python3
"""Short engineering BRAKE windows at two historical force-failure states.

This is not a High-ROM rollout.  The two fixtures are the analytic reference
states at the failure times recorded by ``high-rom-exploration-v1``; the
original full plant-state NPZ files were not committed.  Unsafe TRACK actions
are reconstructed only to match the recorded executable-force magnitudes and
are not represented as the original CEM actions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import CONTROL_DT_S, CONTROL_SUBSTEPS, HIP_HEIGHT_M
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.executable_command import preview_stage4_executable_command
from traction_mpc_stage4.measurement import ControllerMeasurement
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant
from traction_mpc_stage4.track_brake import (
    BRAKE_INFEASIBLE,
    SAFE_BRAKE,
    TrackBrakeSupervisor,
)


HISTORICAL_SOURCE_COMMIT = "f87581b"
HISTORICAL_SOURCE_PATH = (
    "stages/stage4_adaptive_control/results/high_rom_feasibility/"
    "force_feasibility_recovery_pilot/force_feasibility_recovery_pilot.json"
)


@dataclass(frozen=True)
class FailureFixture:
    name: str
    endpoint_deg: tuple[float, float]
    failure_time_s: float
    rejected_executable_force_n: float
    old_hold_duration_s: float
    old_hold_termination: str
    old_acceleration_rms_deg_s2: float
    old_jerk_rms_deg_s3: float


FIXTURES = (
    FailureFixture(
        name="hip_dominant_100_60",
        endpoint_deg=(100.0, 60.0),
        failure_time_s=8.56,
        rejected_executable_force_n=212.81693018250718,
        old_hold_duration_s=0.30,
        old_hold_termination="hold_command_force_infeasible",
        old_acceleration_rms_deg_s2=467.33089320600965,
        old_jerk_rms_deg_s3=18471.68776797668,
    ),
    FailureFixture(
        name="aggressive_both_120_120",
        endpoint_deg=(120.0, 120.0),
        failure_time_s=7.75,
        rejected_executable_force_n=207.32100598486952,
        old_hold_duration_s=0.18,
        old_hold_termination="hold_command_force_infeasible",
        old_acceleration_rms_deg_s2=282.27143272184645,
        old_jerk_rms_deg_s3=10974.713426468446,
    ),
)


def _reference(fixture: FailureFixture) -> CuffPoseReference:
    initial_deg = np.array([5.0, 10.0])
    target_deg = np.asarray(fixture.endpoint_deg, dtype=float)
    normalized = (fixture.failure_time_s - 1.0) / 12.0
    progress = 10.0 * normalized**3 - 15.0 * normalized**4 + 6.0 * normalized**5
    velocity = (
        30.0 * normalized**2
        - 60.0 * normalized**3
        + 30.0 * normalized**4
    ) / 12.0
    acceleration = (
        60.0 * normalized
        - 180.0 * normalized**2
        + 120.0 * normalized**3
    ) / 12.0**2
    delta_deg = target_deg - initial_deg
    q = np.radians(initial_deg + progress * delta_deg)
    dq = np.radians(velocity * delta_deg)
    ddq = np.radians(acceleration * delta_deg)
    return CuffPoseReference(q, dq, ddq, _geometry().cuff_pose(q))


def _geometry() -> PlanarCuffGeometry:
    return PlanarCuffGeometry(
        origin_world_m=np.array([0.0, 0.0, HIP_HEIGHT_M]),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([HUMAN.sleeve_center_m, 0.0]),
    )


def _model() -> BaseParameterHumanModel:
    return BaseParameterHumanModel(_geometry(), nominal_base_parameters(HUMAN))


def _measurement(observation: Any) -> ControllerMeasurement:
    return ControllerMeasurement(
        arrival_time_s=float(observation.time_s),
        sample_time_s=float(observation.time_s),
        robot_q_rad=observation.robot_q_rad.copy(),
        robot_dq_rad_s=observation.robot_dq_rad_s.copy(),
        attachment_position_m=observation.attachment_position_m.copy(),
        attachment_rotation_matrix=observation.attachment_rotation_matrix.copy(),
        attachment_velocity_m_s=observation.attachment_velocity_m_s.copy(),
        attachment_angular_velocity_rad_s=(
            observation.attachment_angular_velocity_rad_s.copy()
        ),
        cuff_force_vector_n=observation.cuff_force_vector_n.copy(),
        cuff_moment_vector_nm=observation.cuff_moment_vector_nm.copy(),
        new_sample=True,
    )


def _initialize(reference: CuffPoseReference) -> SensorBoundaryStage4Plant:
    plant = SensorBoundaryStage4Plant(HUMAN)
    plant.reset(reference.q_rad)
    plant.data.qvel[plant.human_dof_indices] = reference.dq_rad_s
    linear, angular = _geometry().cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    robot_jacobian = plant.robot_attachment_jacobian()
    plant.data.qvel[plant.robot_dof_indices] = np.linalg.lstsq(
        robot_jacobian,
        np.concatenate([linear, angular]),
        rcond=None,
    )[0]
    mujoco.mj_forward(plant.model, plant.data)
    return plant


def _estimated_state(
    model: BaseParameterHumanModel,
    measurement: ControllerMeasurement,
) -> np.ndarray:
    return model.geometry.estimate_state(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        measurement.attachment_velocity_m_s,
        measurement.attachment_angular_velocity_rad_s,
    )


def _reconstructed_unsafe_action(
    *,
    fixture: FailureFixture,
    plant: SensorBoundaryStage4Plant,
    measurement: ControllerMeasurement,
    state: np.ndarray,
    model: BaseParameterHumanModel,
    reference: CuffPoseReference,
    allocator: Any,
) -> tuple[np.ndarray, float]:
    base = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )

    def force(scale: float) -> float:
        preview = preview_stage4_executable_command(
            plant=plant,
            measurement=measurement,
            action_nm=float(scale) * base,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=reference,
        )
        return preview.command.translational_force_norm_n

    lower, upper = 1.0, 2.0
    while force(upper) < fixture.rejected_executable_force_n:
        upper *= 2.0
        if upper > 1024.0:
            raise RuntimeError("could not reconstruct unsafe TRACK action")
    for _ in range(60):
        midpoint = 0.5 * (lower + upper)
        if force(midpoint) < fixture.rejected_executable_force_n:
            lower = midpoint
        else:
            upper = midpoint
    return upper * base, force(upper)


def _smoothness(time_s: np.ndarray, dq_rad_s: np.ndarray) -> dict[str, Any]:
    if len(time_s) < 4:
        acceleration = np.zeros_like(dq_rad_s)
        jerk = np.zeros_like(dq_rad_s)
    else:
        acceleration = np.gradient(dq_rad_s, time_s, axis=0, edge_order=2)
        jerk = np.gradient(acceleration, time_s, axis=0, edge_order=2)
    acceleration_deg = np.degrees(acceleration)
    jerk_deg = np.degrees(jerk)
    return {
        "acceleration_rms_per_joint_deg_s2": np.sqrt(
            np.mean(acceleration_deg**2, axis=0)
        ).tolist(),
        "acceleration_combined_rms_deg_s2": float(
            np.sqrt(np.mean(acceleration_deg**2))
        ),
        "jerk_rms_per_joint_deg_s3": np.sqrt(
            np.mean(jerk_deg**2, axis=0)
        ).tolist(),
        "jerk_combined_rms_deg_s3": float(
            np.sqrt(np.mean(jerk_deg**2))
        ),
    }


def _metrics(
    *,
    fixture: FailureFixture,
    reference: CuffPoseReference,
    times: list[float],
    q: list[np.ndarray],
    dq: list[np.ndarray],
    reference_q: list[np.ndarray],
    reference_dq: list[np.ndarray],
    command_force: list[float],
    measured_force: list[float],
    statuses: list[str],
    latencies_ms: list[float],
    termination: str,
    rom_events: int,
    robot_limit_events: int,
    warnings: dict[str, int],
) -> dict[str, Any]:
    time_array = np.asarray(times, dtype=float)
    q_array = np.asarray(q, dtype=float)
    dq_array = np.asarray(dq, dtype=float)
    ref_q = np.asarray(reference_q, dtype=float)
    ref_dq = np.asarray(reference_dq, dtype=float)
    speed_deg_s = np.linalg.norm(np.degrees(dq_array), axis=1)
    near = np.flatnonzero(speed_deg_s <= 1.0)
    latency = np.asarray(latencies_ms, dtype=float)
    return {
        "fixture": fixture.name,
        "fixture_kind": "analytic_reference_state_at_recorded_failure_time",
        "window_duration_s": float(time_array[-1] - time_array[0]),
        "termination": termination,
        "brake_feasible": bool(termination == "completed"),
        "statuses": sorted(set(statuses)),
        "executed_command_peak_n": float(np.max(command_force)),
        "executed_command_over_200_count": int(
            np.count_nonzero(np.asarray(command_force) > 200.0 + 1.0e-9)
        ),
        "measured_cuff_force_peak_n": float(np.max(measured_force)),
        "initial_q_deg": np.degrees(q_array[0]).tolist(),
        "final_q_deg": np.degrees(q_array[-1]).tolist(),
        "q_change_deg": np.degrees(q_array[-1] - q_array[0]).tolist(),
        "initial_dq_deg_s": np.degrees(dq_array[0]).tolist(),
        "final_dq_deg_s": np.degrees(dq_array[-1]).tolist(),
        "initial_speed_norm_deg_s": float(speed_deg_s[0]),
        "final_speed_norm_deg_s": float(speed_deg_s[-1]),
        "speed_reduction_percent": float(
            100.0 * (1.0 - speed_deg_s[-1] / speed_deg_s[0])
        ),
        "time_to_speed_norm_at_most_1deg_s": (
            float(time_array[near[0]] - time_array[0]) if len(near) else None
        ),
        "entry_reference_q_jump_deg": np.degrees(
            ref_q[0] - reference.q_rad
        ).tolist(),
        "entry_reference_dq_jump_deg_s": np.degrees(
            ref_dq[0] - reference.dq_rad_s
        ).tolist(),
        **_smoothness(time_array, dq_array),
        "brake_computation": {
            "count": int(len(latency)),
            "mean_ms": float(np.mean(latency)) if len(latency) else 0.0,
            "p95_ms": float(np.percentile(latency, 95.0)) if len(latency) else 0.0,
            "max_ms": float(np.max(latency)) if len(latency) else 0.0,
        },
        "events": {
            "rom_event_samples": rom_events,
            "robot_joint_limit_samples": robot_limit_events,
            "mujoco_warning_counts": warnings,
            "solver_failures": 0,
        },
    }


def _run_brake_window(
    fixture: FailureFixture,
    duration_s: float,
) -> dict[str, Any]:
    reference = _reference(fixture)
    model = _model()
    allocator = default_engineering_cuff_allocator()
    plant = _initialize(reference)
    measurement = _measurement(plant.observe())
    state = _estimated_state(model, measurement)
    unsafe_action, unsafe_force = _reconstructed_unsafe_action(
        fixture=fixture,
        plant=plant,
        measurement=measurement,
        state=state,
        model=model,
        reference=reference,
        allocator=allocator,
    )
    supervisor = TrackBrakeSupervisor()
    count = int(round(duration_s / CONTROL_DT_S))
    times: list[float] = []
    q: list[np.ndarray] = []
    dq: list[np.ndarray] = []
    reference_q: list[np.ndarray] = []
    reference_dq: list[np.ndarray] = []
    command_force: list[float] = []
    measured_force: list[float] = []
    statuses: list[str] = []
    latencies_ms: list[float] = []
    rom_events = 0
    robot_limit_events = 0
    termination = "completed"
    for index in range(count):
        observation = plant.observe()
        measurement = _measurement(observation)
        state = _estimated_state(model, measurement)
        decision = supervisor.command(
            plant=plant,
            measurement=measurement,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            track_reference=reference,
            proposed_action_nm=unsafe_action if index == 0 else None,
            mpc_status=SAFE_ACTION if index == 0 else None,
        )
        statuses.append(decision.status)
        latencies_ms.append(decision.computation_ms)
        if decision.status == BRAKE_INFEASIBLE:
            termination = BRAKE_INFEASIBLE
            break
        assert decision.status == SAFE_BRAKE
        assert decision.reference is not None
        assert decision.executable_preview is not None
        preview = decision.executable_preview.command
        times.append(float(observation.time_s))
        q.append(observation.human_q_rad.copy())
        dq.append(observation.human_dq_rad_s.copy())
        reference_q.append(decision.reference.q_rad.copy())
        reference_dq.append(decision.reference.dq_rad_s.copy())
        command_force.append(preview.translational_force_norm_n)
        measured_force.append(float(np.linalg.norm(observation.cuff_force_vector_n)))
        plant.apply_executable_command(preview)
        for _ in range(CONTROL_SUBSTEPS):
            observation = plant.step()
        human_q = observation.human_q_rad
        rom_events += int(
            np.any(human_q < np.asarray(HUMAN.q_min_rad) - 1.0e-9)
            or np.any(human_q > np.asarray(HUMAN.q_max_rad) + 1.0e-9)
        )
        robot_q = observation.robot_q_rad
        robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]
        robot_limit_events += int(
            np.any(robot_q < robot_ranges[:, 0] - 1.0e-9)
            or np.any(robot_q > robot_ranges[:, 1] + 1.0e-9)
        )
    result = _metrics(
        fixture=fixture,
        reference=reference,
        times=times,
        q=q,
        dq=dq,
        reference_q=reference_q,
        reference_dq=reference_dq,
        command_force=command_force,
        measured_force=measured_force,
        statuses=statuses,
        latencies_ms=latencies_ms,
        termination=termination,
        rom_events=rom_events,
        robot_limit_events=robot_limit_events,
        warnings=plant.warning_counts(),
    )
    result.update(
        {
            "historical_rejected_force_n": fixture.rejected_executable_force_n,
            "reconstructed_rejected_force_n": unsafe_force,
            "unsafe_track_action_rejected": supervisor.rejected_track_command_count == 1,
            "supervisor": supervisor.summary(),
        }
    )
    return result


def _run_abrupt_hold_window(
    fixture: FailureFixture,
    duration_s: float,
) -> dict[str, Any]:
    reference = _reference(fixture)
    hold = CuffPoseReference(
        q_rad=reference.q_rad.copy(),
        dq_rad_s=np.zeros(2),
        ddq_rad_s2=np.zeros(2),
        world_from_cuff=reference.world_from_cuff,
    )
    model = _model()
    allocator = default_engineering_cuff_allocator()
    plant = _initialize(reference)
    count = int(round(duration_s / CONTROL_DT_S))
    times: list[float] = []
    q: list[np.ndarray] = []
    dq: list[np.ndarray] = []
    reference_q: list[np.ndarray] = []
    reference_dq: list[np.ndarray] = []
    command_force: list[float] = []
    measured_force: list[float] = []
    statuses: list[str] = []
    latencies_ms: list[float] = []
    termination = "completed"
    rom_events = 0
    robot_limit_events = 0
    for _ in range(count):
        observation = plant.observe()
        measurement = _measurement(observation)
        state = _estimated_state(model, measurement)
        started = perf_counter()
        action = model.inverse_dynamics(state[:2], state[2:], np.zeros(2))
        preview = preview_stage4_executable_command(
            plant=plant,
            measurement=measurement,
            action_nm=action,
            estimated_state=state,
            human_model=model,
            cuff_allocator=allocator,
            reference=hold,
        )
        latencies_ms.append(1000.0 * (perf_counter() - started))
        if (
            not preview.command.feasible
            or float(preview.allocation["force_norm_n"])
            > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9
        ):
            termination = "abrupt_hold_command_force_infeasible"
            statuses.append("HOLD_INFEASIBLE")
            break
        statuses.append("ABRUPT_HOLD_EXECUTED")
        times.append(float(observation.time_s))
        q.append(observation.human_q_rad.copy())
        dq.append(observation.human_dq_rad_s.copy())
        reference_q.append(hold.q_rad.copy())
        reference_dq.append(hold.dq_rad_s.copy())
        command_force.append(preview.command.translational_force_norm_n)
        measured_force.append(float(np.linalg.norm(observation.cuff_force_vector_n)))
        plant.apply_executable_command(preview.command)
        for _ in range(CONTROL_SUBSTEPS):
            observation = plant.step()
        human_q = observation.human_q_rad
        rom_events += int(
            np.any(human_q < np.asarray(HUMAN.q_min_rad) - 1.0e-9)
            or np.any(human_q > np.asarray(HUMAN.q_max_rad) + 1.0e-9)
        )
        robot_q = observation.robot_q_rad
        robot_ranges = plant.model.jnt_range[plant.robot_joint_ids]
        robot_limit_events += int(
            np.any(robot_q < robot_ranges[:, 0] - 1.0e-9)
            or np.any(robot_q > robot_ranges[:, 1] + 1.0e-9)
        )
    return _metrics(
        fixture=fixture,
        reference=reference,
        times=times,
        q=q,
        dq=dq,
        reference_q=reference_q,
        reference_dq=reference_dq,
        command_force=command_force,
        measured_force=measured_force,
        statuses=statuses,
        latencies_ms=latencies_ms,
        termination=termination,
        rom_events=rom_events,
        robot_limit_events=robot_limit_events,
        warnings=plant.warning_counts(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=0.75)
    args = parser.parse_args()
    if not 0.5 <= args.duration_s <= 1.0:
        raise ValueError("brake validation window must be 0.5 to 1.0 seconds")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    runs = []
    for fixture in FIXTURES:
        brake = _run_brake_window(fixture, args.duration_s)
        abrupt = _run_abrupt_hold_window(fixture, args.duration_s)
        runs.append(
            {
                "fixture": fixture.__dict__,
                "brake": brake,
                "same_window_abrupt_hold": abrupt,
                "comparison": {
                    "representative_same_window_acceleration_rms_reduction_percent": 100.0
                    * (
                        1.0
                        - brake["acceleration_combined_rms_deg_s2"]
                        / abrupt["acceleration_combined_rms_deg_s2"]
                    ),
                    "representative_same_window_jerk_rms_reduction_percent": 100.0
                    * (
                        1.0
                        - brake["jerk_combined_rms_deg_s3"]
                        / abrupt["jerk_combined_rms_deg_s3"]
                    ),
                    "historical_full_run_acceleration_rms_reduction_percent": 100.0
                    * (
                        1.0
                        - brake["acceleration_combined_rms_deg_s2"]
                        / fixture.old_acceleration_rms_deg_s2
                    ),
                    "historical_full_run_jerk_rms_reduction_percent": 100.0
                    * (
                        1.0
                        - brake["jerk_combined_rms_deg_s3"]
                        / fixture.old_jerk_rms_deg_s3
                    ),
                    "historical_old_hold": {
                        "duration_s": fixture.old_hold_duration_s,
                        "termination": fixture.old_hold_termination,
                        "full_run_acceleration_rms_deg_s2": (
                            fixture.old_acceleration_rms_deg_s2
                        ),
                        "full_run_jerk_rms_deg_s3": fixture.old_jerk_rms_deg_s3,
                    },
                },
            }
        )
    payload = {
        "evidence_category": "short_engineering_brake_window_not_scientific",
        "historical_source_commit": HISTORICAL_SOURCE_COMMIT,
        "historical_source_path": HISTORICAL_SOURCE_PATH,
        "original_failure_npz_available": False,
        "fixture_limit": (
            "analytic reference states and force-matched reconstructed unsafe "
            "actions; not exact historical plant states or CEM actions"
        ),
        "comparison_limit": (
            "the same-window abrupt-HOLD reconstruction is a representative "
            "engineering comparator; historical acceleration/jerk values are "
            "full-run evidence and are not like-for-like short-window metrics"
        ),
        "duration_s": args.duration_s,
        "runs": runs,
        "full_high_rom_rollout_run": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
