#!/usr/bin/env python3
"""Diagnose the preserved Phase-5 90/120 physical cuff-force event.

This is an engineering replay/audit.  It does not change controller settings,
select a new force margin, or produce formal/authoritative scientific evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    LYING_BED_SCENARIO,
    SUSPENDED_SEATED_LIKE_SCENARIO,
)
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage4.confidence_execution import UnifiedReferenceManager
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.mpc import HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
    write_strict_json,
)
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor

from run_stage4_phase5_high_rom_system_pilot import (
    DEFAULT_MATRIX,
    HIGH_ROM_HUMAN,
    NOMINAL_PATH_DURATION_S,
    TRAJECTORIES,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESERVED_TRACE = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase5_high_rom_system_pilot_20260902"
    / "knee_high_folding_90_120"
    / "trace.npz"
)
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase_a_high_rom_interaction_audit_20260902"
)
PRE_SPIKE_TIME_S = 16.045
CAPTURE_WINDOW_START_S = 15.995
FORCE_GATE_N = 200.0
REPLAY_WINDOW_S = 0.005


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
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _distribution(values: np.ndarray) -> dict[str, float | int]:
    array = np.asarray(values, dtype=float)
    return {
        "count": int(len(array)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
        "mean": float(np.mean(array)),
        "rms": float(np.sqrt(np.mean(array**2))),
        "p95": float(np.percentile(array, 95.0)),
    }


def _command_indices(sample_time_s: np.ndarray, command_time_s: np.ndarray) -> np.ndarray:
    return np.maximum(0, np.searchsorted(command_time_s, sample_time_s, side="right") - 1)


def audit_preserved_trace(trace_path: Path) -> dict[str, Any]:
    with np.load(trace_path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        force_local = np.asarray(trace["cuff_force_local_n_god_view"], dtype=float)
        moment_local = np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float)
        force_norm = np.linalg.norm(force_local, axis=1)
        moment_norm = np.linalg.norm(moment_local, axis=1)
        peak_index = int(np.argmax(force_norm))
        command_time = np.asarray(trace["executed_command_time_s"], dtype=float)
        command_force = np.asarray(trace["executed_command_force_total_n"], dtype=float)
        command_norm = np.linalg.norm(command_force, axis=1)
        command_index = _command_indices(time_s, command_time)
        aligned_command_norm = command_norm[command_index]
        norm_residual = force_norm - aligned_command_norm
        over = force_norm > FORCE_GATE_N + 1.0e-9
        groups: list[tuple[int, int]] = []
        starts = np.flatnonzero(over & np.r_[True, ~over[:-1]])
        ends = np.flatnonzero(over & np.r_[~over[1:], True])
        for start, end in zip(starts, ends, strict=True):
            groups.append((int(start), int(end)))
        dt = float(np.median(np.diff(time_s)))
        window = np.abs(time_s - time_s[peak_index]) <= 0.050 + 1.0e-12
        local_window = np.abs(time_s - time_s[peak_index]) <= 0.010 + 1.0e-12
        bed = np.asarray(trace["bed_force_n_god_view"], dtype=float)
        q_rad = np.radians(np.asarray(trace["human_q_deg_god_view"], dtype=float))
        human_dq_fd = np.gradient(q_rad, time_s, axis=0, edge_order=2)
        human_qdd_fd = np.gradient(human_dq_fd, time_s, axis=0, edge_order=2)
        robot_dq = np.asarray(trace["robot_dq_rad_s"], dtype=float)
        robot_qdd_fd = np.gradient(robot_dq, time_s, axis=0, edge_order=2)
        event_command_index = int(command_index[peak_index])
        return {
            "source": str(trace_path),
            "source_is_preserved_phase5_trace": True,
            "finest_saved_sample_period_s": dt,
            "event": {
                "index": peak_index,
                "time_s": float(time_s[peak_index]),
                "physical_cuff_force_local_n": force_local[peak_index].tolist(),
                "physical_cuff_force_norm_n": float(force_norm[peak_index]),
                "physical_cuff_moment_local_nm": moment_local[peak_index].tolist(),
                "physical_cuff_moment_norm_nm": float(moment_norm[peak_index]),
                "human_q_deg": np.degrees(q_rad[peak_index]).tolist(),
                "human_dq_finite_difference_deg_s": np.degrees(
                    human_dq_fd[peak_index]
                ).tolist(),
                "human_qdd_finite_difference_deg_s2": np.degrees(
                    human_qdd_fd[peak_index]
                ).tolist(),
                "robot_q_rad": np.asarray(trace["robot_q_rad"])[peak_index].tolist(),
                "robot_dq_rad_s": robot_dq[peak_index].tolist(),
                "robot_qdd_finite_difference_rad_s2": robot_qdd_fd[
                    peak_index
                ].tolist(),
                "finite_difference_note": (
                    "derived only because qdd and full-rate Human dq were not saved; "
                    "the instrumented replay records MuJoCo qacc directly"
                ),
                "bed_force_n": float(bed[peak_index]),
                "executed_command_time_s": float(command_time[event_command_index]),
                "executed_command_force_world_n": command_force[
                    event_command_index
                ].tolist(),
                "executed_command_force_norm_n": float(
                    command_norm[event_command_index]
                ),
                "command_to_physical_norm_residual_n": float(
                    norm_residual[peak_index]
                ),
                "safety_filter_status": str(
                    np.asarray(trace["safety_filter_status"])[event_command_index]
                ),
                "safety_filter_lambda": float(
                    np.asarray(trace["safety_filter_lambda"])[event_command_index]
                ),
                "safety_filter_force_intervention_norm_n": float(
                    np.asarray(trace["safety_filter_force_intervention_norm_n"])[
                        event_command_index
                    ]
                ),
                "safety_filter_moment_intervention_norm_nm": float(
                    np.asarray(trace["safety_filter_moment_intervention_norm_nm"])[
                        event_command_index
                    ]
                ),
                "reference_manager_alpha": float(
                    np.asarray(trace["reference_speed_scale"])[peak_index]
                ),
            },
            "over_200n_intervals": [
                {
                    "start_time_s": float(time_s[start]),
                    "end_time_s": float(time_s[end]),
                    "sample_count": end - start + 1,
                    "sample_span_s": float(time_s[end] - time_s[start]),
                    "represented_duration_s": float((end - start + 1) * dt),
                }
                for start, end in groups
            ],
            "command_to_physical_force_norm_residual_n": {
                "entire_preserved_trace": _distribution(norm_residual),
                "last_100ms": _distribution(
                    norm_residual[time_s >= time_s[peak_index] - 0.100 - 1.0e-12]
                ),
                "last_50ms": _distribution(norm_residual[window]),
                "last_10ms": _distribution(norm_residual[local_window]),
                "definition": "physical cuff force norm minus held executable command force norm",
                "vector_residual_unavailable_from_preserved_trace": True,
                "reason": (
                    "the preserved trace stores physical force in the cuff frame "
                    "and executable force in the world frame without the exact "
                    "attachment rotation history"
                ),
            },
            "bed_near_event": {
                "event_sample_force_n": float(bed[peak_index]),
                "last_10ms_peak_n": float(np.max(bed[local_window])),
                "last_50ms_peak_n": float(np.max(bed[window])),
                "last_50ms_nonzero_sample_count": int(np.count_nonzero(bed[window] > 0.0)),
                "last_50ms_material_sample_count_over_2n": int(
                    np.count_nonzero(bed[window] > 2.0)
                ),
            },
        }


class DiagnosticPlant(SensorBoundaryStage4Plant):
    """Capture raw MuJoCo quantities without changing the plant step."""

    def __init__(self, human: Any, *, engineering_scenario: str) -> None:
        super().__init__(
            human,
            attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=engineering_scenario,
        )
        self.command_records: list[dict[str, Any]] = []
        self.step_records: list[dict[str, Any]] = []
        self.pre_spike_integration_state: np.ndarray | None = None
        self.pre_spike_record: dict[str, Any] | None = None
        self.pre_spike_command: dict[str, Any] | None = None
        self.surface_model = CylindricalSurfaceLoadModel(
            CylindricalSurfaceConfig(0.080)
        )

    def _contacts(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        force = np.zeros(6)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            mujoco.mj_contactForce(self.model, self.data, index, force)
            records.append(
                {
                    "index": index,
                    "geom_pair": [
                        self.model.geom(int(contact.geom1)).name,
                        self.model.geom(int(contact.geom2)).name,
                    ],
                    "distance_m": float(contact.dist),
                    "position_world_m": np.asarray(contact.pos).tolist(),
                    "contact_frame": np.asarray(contact.frame).reshape(3, 3).tolist(),
                    "contact_force_torque_contact_frame": force.copy().tolist(),
                }
            )
        return records

    def diagnostic_record(self, label: str) -> dict[str, Any]:
        observation = self.observe()
        equality_type = int(mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        rows = np.flatnonzero(
            (self.data.efc_type[: self.data.nefc] == equality_type)
            & (self.data.efc_id[: self.data.nefc] == self.weld_id)
        )
        multipliers = np.zeros(self.data.nefc)
        multipliers[rows] = self.data.efc_force[rows]
        equality_qfrc = np.zeros(self.model.nv)
        mujoco.mj_mulJacTVec(self.model, self.data, equality_qfrc, multipliers)
        rotation = observation.attachment_rotation_matrix
        physical_wrench_local = np.concatenate(
            [
                rotation.T @ observation.cuff_force_vector_n,
                rotation.T @ observation.cuff_moment_vector_nm,
            ]
        )
        command_wrench_local = np.concatenate(
            [rotation.T @ self.last_force, rotation.T @ self.last_moment]
        )
        physical_surface = self.surface_model.decompose(
            physical_wrench_local[np.newaxis, :]
        ).patch_forces_cuff_n[0]
        command_surface = self.surface_model.decompose(
            command_wrench_local[np.newaxis, :]
        ).patch_forces_cuff_n[0]
        adapter_vector_world = (
            self.data.site_xpos[self.attachment_site_id]
            - self.data.site_xpos[self.flange_site_id]
        )
        return {
            "label": label,
            "scenario": self.engineering_scenario,
            "time_s": float(self.data.time),
            "human_q_rad": observation.human_q_rad.tolist(),
            "human_dq_rad_s": observation.human_dq_rad_s.tolist(),
            "human_qdd_rad_s2": self.data.qacc[self.human_dof_indices].tolist(),
            "robot_q_rad": observation.robot_q_rad.tolist(),
            "robot_dq_rad_s": observation.robot_dq_rad_s.tolist(),
            "robot_qdd_rad_s2": self.data.qacc[self.robot_dof_indices].tolist(),
            "physical_cuff_force_world_n": observation.cuff_force_vector_n.tolist(),
            "physical_cuff_force_local_n": physical_wrench_local[:3].tolist(),
            "physical_cuff_force_norm_n": float(
                np.linalg.norm(observation.cuff_force_vector_n)
            ),
            "physical_cuff_moment_world_nm": observation.cuff_moment_vector_nm.tolist(),
            "physical_cuff_moment_local_nm": physical_wrench_local[3:].tolist(),
            "physical_cuff_moment_norm_nm": float(
                np.linalg.norm(observation.cuff_moment_vector_nm)
            ),
            "command_force_world_n": self.last_force.tolist(),
            "command_force_norm_n": float(np.linalg.norm(self.last_force)),
            "command_moment_world_nm": self.last_moment.tolist(),
            "command_moment_norm_nm": float(np.linalg.norm(self.last_moment)),
            "command_to_physical_force_residual_world_n": (
                observation.cuff_force_vector_n - self.last_force
            ).tolist(),
            "command_to_physical_force_residual_norm_n": float(
                np.linalg.norm(observation.cuff_force_vector_n - self.last_force)
            ),
            "physical_norm_minus_command_norm_n": float(
                np.linalg.norm(observation.cuff_force_vector_n)
                - np.linalg.norm(self.last_force)
            ),
            "cuff_wrench_reconstruction_residual_nm": float(
                observation.cuff_wrench_reconstruction_residual_nm
            ),
            "human_constraint_torque_nm": observation.human_constraint_torque_nm.tolist(),
            "human_wrench_torque_nm": observation.human_wrench_torque_nm.tolist(),
            "human_wrench_torque_residual_nm": float(
                observation.human_wrench_torque_residual_nm
            ),
            "weld_position_error_m": float(observation.weld_position_error_m),
            "weld_rotation_error_rad": float(observation.weld_rotation_error_rad),
            "equality_constraint": {
                "row_indices": rows.tolist(),
                "row_count": int(len(rows)),
                "efc_force": self.data.efc_force[rows].tolist(),
                "efc_position": self.data.efc_pos[rows].tolist(),
                "efc_velocity": self.data.efc_vel[rows].tolist(),
                "efc_reference_acceleration": self.data.efc_aref[rows].tolist(),
                "generalized_force": equality_qfrc.tolist(),
            },
            "bed": {
                "force_n": float(observation.bed_force_n),
                "penetration_m": float(observation.bed_penetration_m),
                "contact_count": int(observation.bed_contact_count),
            },
            "active_contacts": self._contacts(),
            "active_contact_count": int(self.data.ncon),
            "qfrc_constraint": self.data.qfrc_constraint.tolist(),
            "solver": {
                "iterations_used": np.asarray(self.data.solver_niter).tolist(),
                "nonzeros": np.asarray(self.data.solver_nnz).tolist(),
                "forward_inverse_residual": np.asarray(
                    self.data.solver_fwdinv
                ).tolist(),
                "configured_iterations": int(self.model.opt.iterations),
                "configured_tolerance": float(self.model.opt.tolerance),
                "configured_timestep_s": float(self.model.opt.timestep),
                "warning_counts": self.warning_counts(),
            },
            "adapter": {
                "flange_to_cuff_vector_world_m": adapter_vector_world.tolist(),
                "flange_to_cuff_distance_m": float(np.linalg.norm(adapter_vector_world)),
                "command_force_lever_moment_about_flange_nm": np.cross(
                    adapter_vector_world, self.last_force
                ).tolist(),
                "command_force_lever_moment_norm_nm": float(
                    np.linalg.norm(np.cross(adapter_vector_world, self.last_force))
                ),
            },
            "surface_load_proxy": {
                "interpretation": (
                    "minimum-norm equivalent 4x4 cylindrical patch-force effort; "
                    "not pressure, comfort, or tissue load"
                ),
                "physical_maximum_patch_force_proxy_n": float(
                    np.max(np.linalg.norm(physical_surface, axis=1))
                ),
                "command_maximum_patch_force_proxy_n": float(
                    np.max(np.linalg.norm(command_surface, axis=1))
                ),
            },
        }

    def apply_executable_command(self, preview: Any) -> None:
        super().apply_executable_command(preview)
        if self.data.time >= CAPTURE_WINDOW_START_S - 1.0e-12:
            record = {"time_s": float(self.data.time)}
            for name, value in vars(preview).items():
                record[name] = _jsonable(value)
            self.command_records.append(record)
            if abs(self.data.time - PRE_SPIKE_TIME_S) <= 1.0e-9:
                self.pre_spike_command = record

    def step(self) -> Any:
        if abs(self.data.time - PRE_SPIKE_TIME_S) <= 1.0e-9:
            state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
            state = np.empty(mujoco.mj_stateSize(self.model, state_spec))
            mujoco.mj_getState(self.model, self.data, state, state_spec)
            self.pre_spike_integration_state = state
            self.pre_spike_record = self.diagnostic_record("pre_spike_pre_step")
        result = super().step()
        if self.data.time >= CAPTURE_WINDOW_START_S - 1.0e-12:
            self.step_records.append(self.diagnostic_record("post_step"))
        return result


def run_instrumented_reconstruction(
    matrix_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, np.ndarray],
    DiagnosticPlant,
    UnifiedReferenceManager,
    OnlineSingleChallengerTrustEstimator,
    HumanSpaceMPC,
    TrackBrakeSupervisor,
]:
    trajectory = TRAJECTORIES[0]
    matrix = load_report_validation_matrix(matrix_path)
    case = measurement_case(matrix, measurement_seed=44104)
    manager = UnifiedReferenceManager(trajectory.reference, confidence_aware=True)
    supervisor = TrackBrakeSupervisor()
    plant_holder: list[DiagnosticPlant] = []
    estimator_holder: list[OnlineSingleChallengerTrustEstimator] = []
    mpc_holder: list[HumanSpaceMPC] = []
    allocator = default_engineering_cuff_allocator()

    def plant_factory(human: Any) -> DiagnosticPlant:
        plant = DiagnosticPlant(human, engineering_scenario=LYING_BED_SCENARIO)
        plant_holder.append(plant)
        return plant

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        estimator = OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN,
        )
        estimator_holder.append(estimator)
        return estimator

    def mpc_factory() -> HumanSpaceMPC:
        mpc = HumanSpaceMPC(cuff_allocator=allocator)
        mpc_holder.append(mpc)
        return mpc

    summary, trace = run_sensor_realism_case(
        case,
        duration_s=PRE_SPIKE_TIME_S + 0.010,
        estimator_architecture="integral_minimal",
        result_case_name="knee_high_folding_90_120__phase_a_reconstruction",
        true_human_override=HIGH_ROM_HUMAN,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_0_125deg",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        plant_factory=plant_factory,
        reference_execution=manager,
        reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
        capture_system_pilot_diagnostics=True,
        track_brake_supervisor=supervisor,
        mpc_factory=mpc_factory,
        cuff_allocator=allocator,
        estimator_factory=estimator_factory,
    )
    if not plant_holder or not estimator_holder or not mpc_holder:
        raise RuntimeError("instrumented replay did not retain runtime objects")
    plant = plant_holder[0]
    if plant.pre_spike_integration_state is None or plant.pre_spike_record is None:
        raise RuntimeError("instrumented replay did not reach the pre-spike state")
    if plant.pre_spike_command is None:
        raise RuntimeError("instrumented replay did not capture the pre-spike command")
    return (
        summary,
        trace,
        plant,
        manager,
        estimator_holder[0],
        mpc_holder[0],
        supervisor,
    )


def _restore_replay_plant(
    integration_state: np.ndarray,
    command: dict[str, Any],
    *,
    scenario: str,
    timestep_s: float,
    iterations: int,
    tolerance: float,
) -> DiagnosticPlant:
    plant = DiagnosticPlant(HIGH_ROM_HUMAN, engineering_scenario=scenario)
    plant.model.opt.timestep = float(timestep_s)
    plant.model.opt.iterations = int(iterations)
    plant.model.opt.tolerance = float(tolerance)
    mujoco.mj_setState(
        plant.model,
        plant.data,
        np.asarray(integration_state, dtype=float),
        mujoco.mjtState.mjSTATE_INTEGRATION,
    )
    plant.last_force = np.asarray(command["force_total_n"], dtype=float)
    plant.last_moment = np.asarray(command["moment_total_nm"], dtype=float)
    plant.last_unclipped_joint_torque = np.asarray(
        command["unclipped_joint_torque_nm"], dtype=float
    )
    plant.last_joint_torque = np.asarray(
        command["joint_torque_command_nm"], dtype=float
    )
    plant.data.ctrl[plant.actuator_ids] = plant.last_joint_torque
    mujoco.mj_forward(plant.model, plant.data)
    return plant


def run_sensitivity_replay(
    integration_state: np.ndarray,
    command: dict[str, Any],
    *,
    scenario: str,
    timestep_s: float,
    iterations: int,
    tolerance: float,
) -> dict[str, Any]:
    plant = _restore_replay_plant(
        integration_state,
        command,
        scenario=scenario,
        timestep_s=timestep_s,
        iterations=iterations,
        tolerance=tolerance,
    )
    records = [plant.diagnostic_record("restored_pre_step")]
    step_count = int(round(REPLAY_WINDOW_S / timestep_s))
    if not np.isclose(step_count * timestep_s, REPLAY_WINDOW_S, atol=1.0e-15):
        raise ValueError("sensitivity timestep must divide the replay window")
    for _ in range(step_count):
        plant.step()
        records.append(plant.diagnostic_record("replay_post_step"))
    force = np.asarray([item["physical_cuff_force_norm_n"] for item in records])
    moment = np.asarray([item["physical_cuff_moment_norm_nm"] for item in records])
    residual = np.asarray(
        [item["command_to_physical_force_residual_norm_n"] for item in records]
    )
    return {
        "scenario": scenario,
        "timestep_s": timestep_s,
        "iterations": iterations,
        "tolerance": tolerance,
        "same_pre_spike_integration_state": True,
        "same_already_issued_joint_torque_command": True,
        "window_duration_s": REPLAY_WINDOW_S,
        "records": records,
        "peak_physical_force_n": float(np.max(force)),
        "end_physical_force_n": float(force[-1]),
        "peak_physical_moment_nm": float(np.max(moment)),
        "end_physical_moment_nm": float(moment[-1]),
        "peak_vector_residual_norm_n": float(np.max(residual)),
        "end_vector_residual_norm_n": float(residual[-1]),
        "over_200n_sample_count": int(np.count_nonzero(force[1:] > FORCE_GATE_N)),
    }


def save_snapshot(
    output_dir: Path,
    plant: DiagnosticPlant,
    trace: dict[str, np.ndarray],
    manager: UnifiedReferenceManager,
    estimator: OnlineSingleChallengerTrustEstimator,
    mpc: HumanSpaceMPC,
    supervisor: TrackBrakeSupervisor,
) -> dict[str, Any]:
    assert plant.pre_spike_integration_state is not None
    assert plant.pre_spike_record is not None
    assert plant.pre_spike_command is not None
    time_s = np.asarray(trace["time_s"], dtype=float)
    index = int(np.argmin(np.abs(time_s - PRE_SPIKE_TIME_S)))
    if abs(float(time_s[index]) - PRE_SPIKE_TIME_S) > 1.0e-9:
        raise RuntimeError("reconstruction trace lacks exact pre-spike sample")
    snapshot_path = output_dir / "pre_spike_replay_snapshot.npz"
    np.savez_compressed(
        snapshot_path,
        mujoco_integration_state=plant.pre_spike_integration_state,
        time_s=np.array(PRE_SPIKE_TIME_S),
        desired_human_action_nm=np.asarray(trace["desired_human_action_nm"])[index],
        allocated_wrench_world=np.asarray(trace["allocated_wrench_world"])[index],
        allocated_sagittal_wrench=np.asarray(trace["allocated_sagittal_wrench"])[index],
        estimated_human_state=np.concatenate(
            [
                np.radians(np.asarray(trace["estimated_human_q_deg"])[index]),
                np.radians(np.asarray(trace["estimated_human_dq_deg_s"])[index]),
            ]
        ),
        incumbent_dynamic_base_model=estimator.control_beta,
        geometry_estimate=np.asarray(trace["geometry_estimate"])[index],
        previous_safe_force_world_n=np.asarray(
            plant.pre_spike_command["force_total_n"], dtype=float
        ),
        previous_safe_moment_world_nm=np.asarray(
            plant.pre_spike_command["moment_total_nm"], dtype=float
        ),
        previous_safe_joint_torque_nm=np.asarray(
            plant.pre_spike_command["joint_torque_command_nm"], dtype=float
        ),
        previous_safe_unclipped_joint_torque_nm=np.asarray(
            plant.pre_spike_command["unclipped_joint_torque_nm"], dtype=float
        ),
        human_q_rad=np.asarray(plant.pre_spike_record["human_q_rad"]),
        human_dq_rad_s=np.asarray(plant.pre_spike_record["human_dq_rad_s"]),
        human_qdd_rad_s2=np.asarray(plant.pre_spike_record["human_qdd_rad_s2"]),
        robot_q_rad=np.asarray(plant.pre_spike_record["robot_q_rad"]),
        robot_dq_rad_s=np.asarray(plant.pre_spike_record["robot_dq_rad_s"]),
        robot_qdd_rad_s2=np.asarray(plant.pre_spike_record["robot_qdd_rad_s2"]),
    )
    manager_state = {
        key: _jsonable(value)
        for key, value in vars(manager).items()
        if key != "base_reference"
    }
    estimator_state = {
        "incumbent_beta": estimator.control_beta.tolist(),
        "geometry": _jsonable(estimator.geometry),
        "trust_summary": _jsonable(estimator.trust_summary()),
        "active_challenger": _jsonable(estimator.active_challenger),
        "control_promotions": _jsonable(estimator.control_promotions),
    }
    manifest = {
        "schema_version": "phase_a_pre_spike_replay_snapshot_v1",
        "evidence_category": "engineering_replay_not_formal_or_authoritative",
        "snapshot_npz": snapshot_path.name,
        "snapshot_time_s": PRE_SPIKE_TIME_S,
        "next_preserved_event_time_s": 16.046,
        "scenario": LYING_BED_SCENARIO,
        "mujoco_state_spec": "mjSTATE_INTEGRATION",
        "mujoco_state_size": int(len(plant.pre_spike_integration_state)),
        "previous_safe_command": plant.pre_spike_command,
        "pre_spike_physical_state": plant.pre_spike_record,
        "reference_manager_state": manager_state,
        "reference_manager_status": manager.status(PRE_SPIKE_TIME_S),
        "incumbent_model_state": estimator_state,
        "mpc": {
            "config": _jsonable(mpc.config),
            "rng_bit_generator_state": _jsonable(mpc.rng.bit_generator.state),
            "solve_count": int(mpc.solve_count),
            "failure_count": int(mpc.failure_count),
            "last_diagnostics": _jsonable(mpc.last_diagnostics),
        },
        "supervisor_state": _jsonable(vars(supervisor)),
        "replay_scope": (
            "exact physical replay of the already-issued 16.045-16.046 s command "
            "interval; controller/reference state is preserved for audit, but the "
            "snapshot does not serialize measurement-layer filter/RNG histories "
            "needed to continue a new closed-loop control cycle after 16.050 s"
        ),
    }
    write_strict_json(output_dir / "pre_spike_replay_snapshot.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--preserved-trace", type=Path, default=DEFAULT_PRESERVED_TRACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite Phase-A audit: {output_dir}")
    output_dir.mkdir(parents=True)
    preserved = audit_preserved_trace(args.preserved_trace.resolve())
    write_strict_json(output_dir / "preserved_trace_audit.json", preserved)

    (
        reconstruction_summary,
        reconstruction_trace,
        plant,
        manager,
        estimator,
        mpc,
        supervisor,
    ) = run_instrumented_reconstruction(args.matrix.resolve())
    with np.load(args.preserved_trace.resolve(), allow_pickle=False) as source:
        source_force = np.linalg.norm(source["cuff_force_local_n_god_view"], axis=1)
        replay_force = np.linalg.norm(
            reconstruction_trace["cuff_force_local_n_god_view"], axis=1
        )
        common = min(len(source_force), len(replay_force))
        reconstruction_check = {
            "source_sample_count": int(len(source_force)),
            "replay_sample_count": int(len(replay_force)),
            "common_sample_count": int(common),
            "maximum_abs_force_norm_difference_n": float(
                np.max(np.abs(source_force[:common] - replay_force[:common]))
            ),
            "source_peak_force_n": float(np.max(source_force)),
            "replay_peak_force_n": float(np.max(replay_force)),
            "source_peak_time_s": float(source["time_s"][np.argmax(source_force)]),
            "replay_peak_time_s": float(
                reconstruction_trace["time_s"][np.argmax(replay_force)]
            ),
            "termination_reason": reconstruction_summary["termination_reason"],
            "solver_warning_counts": reconstruction_summary["events"][
                "mujoco_warning_counts"
            ],
        }
    write_strict_json(output_dir / "reconstruction_check.json", reconstruction_check)
    write_strict_json(
        output_dir / "instrumented_event_window.json",
        {
            "window_start_s": CAPTURE_WINDOW_START_S,
            "pre_spike_time_s": PRE_SPIKE_TIME_S,
            "commands": plant.command_records,
            "steps": plant.step_records,
        },
    )
    snapshot_manifest = save_snapshot(
        output_dir,
        plant,
        reconstruction_trace,
        manager,
        estimator,
        mpc,
        supervisor,
    )

    variants = [
        ("lying_nominal", LYING_BED_SCENARIO, 0.001, 100, 1.0e-8),
        (
            "suspended_seated_like_nominal",
            SUSPENDED_SEATED_LIKE_SCENARIO,
            0.001,
            100,
            1.0e-8,
        ),
        ("lying_half_timestep", LYING_BED_SCENARIO, 0.0005, 100, 1.0e-8),
        ("lying_more_iterations", LYING_BED_SCENARIO, 0.001, 200, 1.0e-8),
        ("lying_tighter_tolerance", LYING_BED_SCENARIO, 0.001, 100, 1.0e-10),
    ]
    sensitivity = {
        name: run_sensitivity_replay(
            plant.pre_spike_integration_state,
            plant.pre_spike_command,
            scenario=scenario,
            timestep_s=timestep,
            iterations=iterations,
            tolerance=tolerance,
        )
        for name, scenario, timestep, iterations, tolerance in variants
    }
    sensitivity_payload = {
        "evidence_category": "short_same_state_same_command_engineering_replay",
        "window": [PRE_SPIKE_TIME_S, PRE_SPIKE_TIME_S + REPLAY_WINDOW_S],
        "limitations": [
            (
                "The suspended case starts from a state reached under the lying-bed "
                "history. This isolates the next 1 ms contact-law contribution but "
                "does not claim that a full suspended trajectory reaches that state."
            ),
            (
                "The half-timestep case reuses the nominal-step warm-start state; "
                "it tests local five-millisecond integration sensitivity, not a "
                "full-history timestep change."
            ),
        ],
        "variants": sensitivity,
    }
    write_strict_json(output_dir / "sensitivity_summary.json", sensitivity_payload)

    step_vector_residual = np.asarray(
        [
            item["command_to_physical_force_residual_norm_n"]
            for item in plant.step_records
        ],
        dtype=float,
    )
    step_norm_residual = np.asarray(
        [item["physical_norm_minus_command_norm_n"] for item in plant.step_records],
        dtype=float,
    )
    event_record = plant.step_records[-1]
    pre_record = plant.pre_spike_record
    assert pre_record is not None
    command_force = np.asarray(event_record["command_force_world_n"], dtype=float)
    physical_force = np.asarray(
        event_record["physical_cuff_force_world_n"], dtype=float
    )
    force_angle_deg = float(
        np.degrees(
            np.arccos(
                np.clip(
                    np.dot(command_force, physical_force)
                    / (np.linalg.norm(command_force) * np.linalg.norm(physical_force)),
                    -1.0,
                    1.0,
                )
            )
        )
    )
    lying_records = sensitivity["lying_nominal"]["records"]
    suspended_records = sensitivity["suspended_seated_like_nominal"]["records"]
    scenario_force_difference = np.asarray(
        [
            left["physical_cuff_force_norm_n"]
            - right["physical_cuff_force_norm_n"]
            for left, right in zip(lying_records, suspended_records, strict=True)
        ],
        dtype=float,
    )
    scenario_moment_difference = np.asarray(
        [
            left["physical_cuff_moment_norm_nm"]
            - right["physical_cuff_moment_norm_nm"]
            for left, right in zip(lying_records, suspended_records, strict=True)
        ],
        dtype=float,
    )
    pre_efc = np.asarray(pre_record["equality_constraint"]["efc_force"])
    event_efc = np.asarray(event_record["equality_constraint"]["efc_force"])
    diagnosis = {
        "classification": "C_genuine_closed_loop_interaction_amplification",
        "classification_qualifier": (
            "primary classification for the observed same-state event; preceding "
            "lying-bed contacts and the 140 mm adapter remain setup-specific "
            "secondary factors whose full-history effects were not isolated"
        ),
        "duration": {
            "preserved_trace": "one 1 ms sample before the gate terminated the run",
            "same_command_open_loop_replay": (
                "above 200 N at every saved sample throughout the complete 5 ms "
                "command interval"
            ),
            "lying_1ms_samples_over_200n": sensitivity["lying_nominal"][
                "over_200n_sample_count"
            ],
            "lying_half_ms_samples_over_200n": sensitivity[
                "lying_half_timestep"
            ]["over_200n_sample_count"],
        },
        "command_to_physical_residual": {
            "instrumented_last_50ms_vector_residual_norm_n": _distribution(
                step_vector_residual
            ),
            "instrumented_last_50ms_physical_norm_minus_command_norm_n": (
                _distribution(step_norm_residual)
            ),
            "event_vector_residual_world_n": event_record[
                "command_to_physical_force_residual_world_n"
            ],
            "event_vector_residual_norm_n": event_record[
                "command_to_physical_force_residual_norm_n"
            ],
            "event_physical_norm_minus_command_norm_n": event_record[
                "physical_norm_minus_command_norm_n"
            ],
            "event_command_physical_direction_angle_deg": force_angle_deg,
            "preserved_norm_statistics": preserved[
                "command_to_physical_force_norm_residual_n"
            ],
        },
        "constraint_and_acceleration": {
            "event_has_active_contact": bool(event_record["active_contact_count"]),
            "event_bed_force_n": event_record["bed"]["force_n"],
            "pre_event_bed_force_n": pre_record["bed"]["force_n"],
            "equality_multiplier_change": (event_efc - pre_efc).tolist(),
            "human_qdd_change_deg_s2": np.degrees(
                np.asarray(event_record["human_qdd_rad_s2"])
                - np.asarray(pre_record["human_qdd_rad_s2"])
            ).tolist(),
            "solver_iterations_used": event_record["solver"]["iterations_used"],
            "solver_warning_counts": event_record["solver"]["warning_counts"],
        },
        "bed_contact_contribution": {
            "initial_spike_force_difference_lying_minus_suspended_n": float(
                scenario_force_difference[1]
            ),
            "maximum_abs_force_norm_difference_over_5ms_n": float(
                np.max(np.abs(scenario_force_difference))
            ),
            "maximum_abs_moment_norm_difference_over_5ms_nm": float(
                np.max(np.abs(scenario_moment_difference))
            ),
            "interpretation": (
                "no direct bed/contact contribution at spike onset; a later bed "
                "contact changes the short-window force but does not create the crossing"
            ),
        },
        "timestep_solver_sensitivity": {
            "nominal_5ms_end_force_n": sensitivity["lying_nominal"][
                "end_physical_force_n"
            ],
            "half_timestep_5ms_end_force_n": sensitivity[
                "lying_half_timestep"
            ]["end_physical_force_n"],
            "half_timestep_end_difference_n": float(
                sensitivity["lying_half_timestep"]["end_physical_force_n"]
                - sensitivity["lying_nominal"]["end_physical_force_n"]
            ),
            "more_iterations_end_difference_n": float(
                sensitivity["lying_more_iterations"]["end_physical_force_n"]
                - sensitivity["lying_nominal"]["end_physical_force_n"]
            ),
            "tighter_tolerance_end_difference_n": float(
                sensitivity["lying_tighter_tolerance"]["end_physical_force_n"]
                - sensitivity["lying_nominal"]["end_physical_force_n"]
            ),
        },
        "moment_adapter_surface": {
            "command_moment_norm_nm": event_record["command_moment_norm_nm"],
            "physical_moment_norm_nm": event_record["physical_cuff_moment_norm_nm"],
            "safety_filter_moment_intervention_norm_nm": preserved["event"][
                "safety_filter_moment_intervention_norm_nm"
            ],
            "adapter_force_lever_moment_norm_nm": event_record["adapter"][
                "command_force_lever_moment_norm_nm"
            ],
            "physical_maximum_patch_force_proxy_n": event_record[
                "surface_load_proxy"
            ]["physical_maximum_patch_force_proxy_n"],
            "command_maximum_patch_force_proxy_n": event_record[
                "surface_load_proxy"
            ]["command_maximum_patch_force_proxy_n"],
            "surface_proxy_is_not_pressure_or_tissue_load": True,
        },
        "force_budget_decision": (
            "fixed evidence-based margin is not supported by this single event; "
            "actual measured interaction force must enter the future low-level "
            "safety/compliance loop with validated sampling, latency, and moment/load handling"
        ),
        "new_margin_selected": False,
        "recommended_next_architecture_step": (
            "in the next separately approved phase, specify measured-wrench feedback "
            "at the low-level safety/compliance boundary while retaining the executable "
            "command budget as an independent guard; include total force, moment, "
            "surface-load proxy, rate/latency, and contact confidence, without yet "
            "changing the Reference Manager or MPC objective"
        ),
    }
    write_strict_json(output_dir / "diagnosis.json", diagnosis)

    summary_payload = {
        "schema_version": "phase_a_high_rom_interaction_audit_v1",
        "evidence_category": "engineering_diagnosis_not_formal_or_authoritative",
        "canonical_plant_changed": False,
        "controller_or_reference_manager_changed": False,
        "force_margin_selected": False,
        "new_full_high_rom_pilot_run": False,
        "preserved_trace_event": preserved["event"],
        "over_200n_intervals": preserved["over_200n_intervals"],
        "reconstruction_check": reconstruction_check,
        "snapshot": {
            "status": "physical_event_exact_replay_snapshot_saved",
            "npz": "pre_spike_replay_snapshot.npz",
            "manifest": "pre_spike_replay_snapshot.json",
            "scope": snapshot_manifest["replay_scope"],
        },
        "sensitivity": {
            name: {
                key: value
                for key, value in result.items()
                if key != "records"
            }
            for name, result in sensitivity.items()
        },
        "diagnosis": diagnosis,
    }
    write_strict_json(output_dir / "phase_a_summary.json", summary_payload)
    print(json.dumps({"output": str(output_dir), "summary": summary_payload}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
