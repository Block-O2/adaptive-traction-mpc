#!/usr/bin/env python3
"""Run the preregistered High-ROM constant-time-scale engineering audit."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Mapping

import mujoco
import numpy as np

from run_stage4_phase5_high_rom_system_pilot import (
    DEFAULT_MATRIX,
    HIGH_ROM_HUMAN,
    NOMINAL_PATH_DURATION_S,
    REPO_ROOT,
    TRAJECTORIES,
    _distribution,
    _smoothness,
)
from traction_mpc_stage3.coupled import (
    CONTROL_DT_S,
    SUSPENDED_SEATED_LIKE_SCENARIO,
)
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.confidence_execution import ReferenceManagerForceDecision
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.measurement import measurement_case_dict
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
    write_strict_json,
)
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
)
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.track_brake import TRACK, TrackBrakeSupervisor


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = STAGE_ROOT / "configs" / "high_rom_time_scale_scan_v1.json"
DEFAULT_SPEC_HASH = (
    "0075d137feab5787ac949f01901bd0bee9f72915900ba197af1bb51374f41ee3"
)
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "high_rom_time_scale_audit_20260902"
)
SIMULATION_DT_S = 0.001
FORCE_GATE_N = 200.0


def _norm_rows(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return np.linalg.norm(values, axis=1) if len(values) else np.zeros(0)


def _jsonable(value: Any) -> Any:
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rate_distribution(time_s: np.ndarray, vectors: np.ndarray) -> dict[str, Any]:
    time_s = np.asarray(time_s, dtype=float)
    vectors = np.asarray(vectors, dtype=float)
    if len(time_s) < 2:
        return {"count": 0, "rms": None, "p95": None, "peak": None}
    dt = np.diff(time_s)
    if np.any(dt <= 0.0):
        raise RuntimeError("command timestamps must be strictly increasing")
    rates = np.linalg.norm(np.diff(vectors, axis=0), axis=1) / dt
    return _distribution(rates)


class FixedExternalTimeScale:
    """Audit-local constant path clock; estimator and force pacing are shadowed."""

    def __init__(self, base_reference: Any, alpha_scan: float) -> None:
        self.base_reference = base_reference
        self.alpha_scan = float(alpha_scan)
        if not 0.0 < self.alpha_scan <= 1.0:
            raise ValueError("alpha_scan must satisfy 0 < alpha <= 1")
        self.shadow_estimator_update_count = 0
        self.force_update_count = 0
        self.force_filtered_count = 0
        self.force_infeasible_count = 0
        self.last_filter_status = SAFE_UNCHANGED
        self.last_force_margin_n = FORCE_GATE_N
        self.last_force_intervention_norm_n = 0.0
        self.last_moment_intervention_norm_nm = 0.0
        self.last_wrench_intervention_coordinate_norm = 0.0
        self.failure_callback: Any | None = None

    @property
    def mode(self) -> str:
        return "fixed_external_time_scale_audit"

    def phase_time_s(self, wall_time_s: float) -> float:
        return self.alpha_scan * float(wall_time_s)

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        base = self.base_reference(self.phase_time_s(wall_time_s))
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=self.alpha_scan * base.dq_rad_s,
            ddq_rad_s2=self.alpha_scan**2 * base.ddq_rad_s2,
            world_from_cuff=base.world_from_cuff,
        )

    def update_from_estimator(
        self,
        wall_time_s: float,
        estimator: Any,
        geometry_diagnostics: dict[str, Any],
        dynamic_diagnostics: dict[str, Any],
    ) -> None:
        del wall_time_s, estimator, geometry_diagnostics, dynamic_diagnostics
        self.shadow_estimator_update_count += 1

    def update_from_safety_filter(
        self,
        wall_time_s: float,
        filter_result: Mapping[str, Any] | Any,
    ) -> ReferenceManagerForceDecision:
        del wall_time_s
        metadata = (
            filter_result
            if isinstance(filter_result, Mapping)
            else filter_result.metadata()
        )
        status = str(metadata["status"])
        if status not in {SAFE_UNCHANGED, SAFE_FILTERED, FILTER_INFEASIBLE}:
            raise ValueError("unexpected Safety Filter status")
        self.last_filter_status = status
        self.force_update_count += 1
        self.last_force_margin_n = float(
            metadata.get("executable_force_margin_n", float("nan"))
        )
        self.last_force_intervention_norm_n = float(
            metadata.get("force_intervention_norm_n", 0.0)
        )
        self.last_moment_intervention_norm_nm = float(
            metadata.get("moment_intervention_norm_nm", 0.0)
        )
        self.last_wrench_intervention_coordinate_norm = float(
            metadata.get("intervention_coordinate_norm", 0.0)
        )
        if status == SAFE_FILTERED:
            self.force_filtered_count += 1
        if status == FILTER_INFEASIBLE:
            self.force_infeasible_count += 1
            if self.failure_callback is not None:
                self.failure_callback(status, metadata)
        return ReferenceManagerForceDecision(
            filter_status=status,
            alpha_force=(None if status == FILTER_INFEASIBLE else self.alpha_scan),
            force_severity=None,
            brake_required=status == FILTER_INFEASIBLE,
        )

    def status(self, wall_time_s: float) -> dict[str, float]:
        return {
            "reference_phase_time_s": self.phase_time_s(wall_time_s),
            "speed_scale": self.alpha_scan,
            "speed_scale_rate_per_s": 0.0,
            "alpha_cmd": self.alpha_scan,
            "alpha_trust": 1.0,
            "alpha_force": 1.0,
            "force_severity": 0.0,
            "force_margin_n": self.last_force_margin_n,
            "force_intervention_norm_n": self.last_force_intervention_norm_n,
            "moment_intervention_norm_nm": self.last_moment_intervention_norm_nm,
            "wrench_intervention_coordinate_norm": (
                self.last_wrench_intervention_coordinate_norm
            ),
            "geometry_model_confidence": 0.0,
            "dynamic_model_confidence": 0.0,
            "combined_model_confidence_raw": 0.0,
            "filtered_model_confidence": 0.0,
            "execution_confidence_high": 0.0,
            "geometry_information_confidence": 0.0,
            "dynamic_information_confidence": 0.0,
            "combined_information_confidence": 0.0,
            "geometry_confidence": 0.0,
            "dynamic_confidence": 0.0,
            "combined_confidence": 0.0,
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "alpha_scan": self.alpha_scan,
            "final_status": self.status(wall_time_s),
            "reference_phase_rule": "phase_s=alpha_scan*wall_simulation_time_s",
            "time_warp_kinematics": (
                "qdot=alpha_scan*q_phase; qddot=alpha_scan^2*q_phase_phase"
            ),
            "adaptive_trust_pacing_bypassed": True,
            "adaptive_force_pacing_bypassed": True,
            "shadow_estimator_update_count": self.shadow_estimator_update_count,
            "force_update_count": self.force_update_count,
            "force_filtered_count": self.force_filtered_count,
            "force_infeasible_count": self.force_infeasible_count,
            "last_force_filter_status": self.last_filter_status,
            "estimator_modified": False,
            "mpc_modified": False,
            "safety_limits_modified": False,
        }


class SnapshotCapturePlant(SensorBoundaryStage4Plant):
    """Frozen suspended plant with compact command and failure-state capture."""

    def __init__(self, human: Any) -> None:
        super().__init__(
            human,
            attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        )
        self.command_time_s: list[float] = []
        self.command_force_world_n: list[np.ndarray] = []
        self.command_moment_world_nm: list[np.ndarray] = []
        self.allocator_force_world_n: list[np.ndarray] = []
        self.allocator_moment_world_nm: list[np.ndarray] = []
        self.last_command_context: dict[str, Any] | None = None
        self.last_safe_state: np.ndarray | None = None
        self.last_safe_context: dict[str, Any] | None = None
        self.first_failure_state: np.ndarray | None = None
        self.first_failure_context: dict[str, Any] | None = None

    def _integration_state(self) -> np.ndarray:
        state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
        state = np.empty(mujoco.mj_stateSize(self.model, state_spec))
        mujoco.mj_getState(self.model, self.data, state, state_spec)
        return state

    def _context(self, observation: Any, event: str) -> dict[str, Any]:
        return {
            "event": event,
            "time_s": float(observation.time_s),
            "human_q_rad": observation.human_q_rad.tolist(),
            "human_dq_rad_s": observation.human_dq_rad_s.tolist(),
            "human_qdd_rad_s2": self.data.qacc[self.human_dof_indices].tolist(),
            "robot_q_rad": observation.robot_q_rad.tolist(),
            "robot_dq_rad_s": observation.robot_dq_rad_s.tolist(),
            "robot_qdd_rad_s2": self.data.qacc[self.robot_dof_indices].tolist(),
            "physical_cuff_force_world_n": observation.cuff_force_vector_n.tolist(),
            "physical_cuff_force_norm_n": float(
                np.linalg.norm(observation.cuff_force_vector_n)
            ),
            "physical_cuff_moment_world_nm": (
                observation.cuff_moment_vector_nm.tolist()
            ),
            "physical_cuff_moment_norm_nm": float(
                np.linalg.norm(observation.cuff_moment_vector_nm)
            ),
            "bed_force_n": float(observation.bed_force_n),
            "bed_contact_count": int(observation.bed_contact_count),
            "active_contact_count": int(self.data.ncon),
            "warning_counts": self.warning_counts(),
            "last_command": self.last_command_context,
        }

    def reset(self, human_q_rad: np.ndarray) -> Any:
        observation = super().reset(human_q_rad)
        self.last_safe_state = self._integration_state()
        self.last_safe_context = self._context(observation, "initial_safe_state")
        return observation

    def apply_executable_command(self, preview: Any) -> None:
        super().apply_executable_command(preview)
        self.command_time_s.append(float(self.data.time))
        self.command_force_world_n.append(preview.force_total_n.copy())
        self.command_moment_world_nm.append(preview.moment_total_nm.copy())
        self.allocator_force_world_n.append(preview.force_allocator_n.copy())
        self.allocator_moment_world_nm.append(preview.moment_allocator_nm.copy())
        self.last_command_context = {
            "time_s": float(self.data.time),
            "force_total_n": preview.force_total_n.tolist(),
            "force_total_norm_n": float(np.linalg.norm(preview.force_total_n)),
            "moment_total_nm": preview.moment_total_nm.tolist(),
            "moment_total_norm_nm": float(np.linalg.norm(preview.moment_total_nm)),
            "force_allocator_n": preview.force_allocator_n.tolist(),
            "moment_allocator_nm": preview.moment_allocator_nm.tolist(),
            "joint_torque_command_nm": preview.joint_torque_command_nm.tolist(),
            "unclipped_joint_torque_nm": preview.unclipped_joint_torque_nm.tolist(),
        }

    def step(self) -> Any:
        before_state = self._integration_state()
        before_observation = self.observe()
        before_context = self._context(before_observation, "last_safe_before_step")
        observation = super().step()
        human_limits = np.column_stack(
            [self.human.q_min_rad, self.human.q_max_rad]
        )
        robot_ranges = self.model.jnt_range[self.robot_joint_ids]
        failure_reasons: list[str] = []
        if np.linalg.norm(observation.cuff_force_vector_n) > FORCE_GATE_N + 1e-9:
            failure_reasons.append("physical_cuff_force_gate")
        if np.any(observation.human_q_rad < human_limits[:, 0] - 1e-9) or np.any(
            observation.human_q_rad > human_limits[:, 1] + 1e-9
        ):
            failure_reasons.append("human_rom")
        if np.any(observation.robot_q_rad < robot_ranges[:, 0] - 1e-9) or np.any(
            observation.robot_q_rad > robot_ranges[:, 1] + 1e-9
        ):
            failure_reasons.append("robot_joint_limit")
        if self.warning_counts():
            failure_reasons.append("mujoco_solver_warning")
        if observation.unintended_contact_pairs:
            failure_reasons.append("unintended_structural_contact")
        if failure_reasons and self.first_failure_state is None:
            self.last_safe_state = before_state
            self.last_safe_context = before_context
            self.first_failure_state = self._integration_state()
            self.first_failure_context = self._context(
                observation, "+".join(failure_reasons)
            )
        elif not failure_reasons:
            self.last_safe_state = self._integration_state()
            self.last_safe_context = self._context(observation, "safe_post_step")
        return observation

    def finalize_controller_failure(self, termination_reason: str) -> None:
        if self.first_failure_state is not None:
            return
        observation = self.observe()
        self.first_failure_state = self._integration_state()
        self.first_failure_context = self._context(
            observation, f"controller_termination:{termination_reason}"
        )
        if self.last_safe_state is None:
            self.last_safe_state = self.first_failure_state.copy()
            self.last_safe_context = self._context(
                observation, "same_state_before_controller_termination"
            )

    def capture_controller_failure(
        self, termination_reason: str, metadata: Mapping[str, Any]
    ) -> None:
        """Capture the state where an unrecovered controller transition starts."""

        if self.first_failure_state is not None:
            return
        observation = self.observe()
        self.first_failure_state = self._integration_state()
        self.first_failure_context = self._context(
            observation, f"controller_failure_entry:{termination_reason}"
        )
        self.first_failure_context["safety_filter"] = _jsonable(dict(metadata))
        if self.last_safe_state is None:
            self.last_safe_state = self.first_failure_state.copy()
            self.last_safe_context = self._context(
                observation, "same_state_before_controller_failure_entry"
            )


class BoundarySnapshotCaptured(RuntimeError):
    """Stop a deterministic prefix replay immediately after snapshot capture."""


def _scaled_horizon_s(alpha: float) -> float:
    ideal = NOMINAL_PATH_DURATION_S / float(alpha)
    return math.ceil(ideal / CONTROL_DT_S - 1.0e-12) * CONTROL_DT_S


def _alpha_key(alpha: float) -> str:
    return f"alpha_{alpha:.6f}".rstrip("0").rstrip(".").replace(".", "p")


def _status_counts(status: np.ndarray) -> dict[str, int]:
    return {
        name: int(np.count_nonzero(status == name))
        for name in (SAFE_UNCHANGED, SAFE_FILTERED, FILTER_INFEASIBLE)
    }


def _snapshot_payload(
    state: np.ndarray,
    context: dict[str, Any] | None,
    *,
    alpha: float,
    trajectory_name: str,
    kind: str,
) -> dict[str, np.ndarray]:
    context = context or {}
    last_command = context.get("last_command") or {}
    return {
        "mujoco_integration_state": np.asarray(state, dtype=float),
        "time_s": np.asarray(float(context.get("time_s", float("nan")))),
        "alpha_scan": np.asarray(float(alpha)),
        "trajectory_name": np.asarray(trajectory_name),
        "snapshot_kind": np.asarray(kind),
        "human_q_rad": np.asarray(context.get("human_q_rad", np.full(2, np.nan))),
        "human_dq_rad_s": np.asarray(
            context.get("human_dq_rad_s", np.full(2, np.nan))
        ),
        "robot_q_rad": np.asarray(context.get("robot_q_rad", np.full(6, np.nan))),
        "robot_dq_rad_s": np.asarray(
            context.get("robot_dq_rad_s", np.full(6, np.nan))
        ),
        "physical_cuff_force_world_n": np.asarray(
            context.get("physical_cuff_force_world_n", np.full(3, np.nan))
        ),
        "physical_cuff_moment_world_nm": np.asarray(
            context.get("physical_cuff_moment_world_nm", np.full(3, np.nan))
        ),
        "command_force_world_n": np.asarray(
            last_command.get("force_total_n", np.full(3, np.nan))
        ),
        "command_moment_world_nm": np.asarray(
            last_command.get("moment_total_nm", np.full(3, np.nan))
        ),
    }


def _save_snapshot(
    path: Path,
    state: np.ndarray,
    context: dict[str, Any] | None,
    *,
    alpha: float,
    trajectory_name: str,
    kind: str,
    termination_reason: str,
) -> None:
    np.savez_compressed(
        path,
        **_snapshot_payload(
            state,
            context,
            alpha=alpha,
            trajectory_name=trajectory_name,
            kind=kind,
        ),
    )
    write_strict_json(
        path.with_suffix(".json"),
        {
            "schema_version": "high_rom_time_scale_snapshot_v1",
            "evidence_category": "engineering_failure_boundary_snapshot",
            "npz": path.name,
            "mujoco_state_spec": "mjSTATE_INTEGRATION",
            "trajectory": trajectory_name,
            "alpha_scan": alpha,
            "snapshot_kind": kind,
            "termination_reason": termination_reason,
            "context": context,
        },
    )


def _compact_trace(
    trace: dict[str, np.ndarray], plant: SnapshotCapturePlant
) -> dict[str, np.ndarray]:
    time_s = np.asarray(trace["time_s"], dtype=float)
    sample = np.unique(
        np.concatenate([np.arange(0, len(time_s), 5), np.array([len(time_s) - 1])])
    )
    keys = (
        "time_s",
        "human_q_deg_god_view",
        "human_q_ref_deg",
        "cuff_force_local_n_god_view",
        "cuff_moment_local_nm_god_view",
        "bed_force_n_god_view",
        "reference_phase_time_s",
        "reference_speed_scale",
        "allocated_wrench_world",
    )
    payload = {key: np.asarray(trace[key])[sample] for key in keys}
    diagnostic_keys = (
        "executed_command_time_s",
        "executed_command_force_total_n",
        "safety_filter_time_s",
        "safety_filter_status",
        "safety_filter_lambda",
        "safety_filter_intervention_coordinate_norm",
        "safety_filter_force_intervention_norm_n",
        "safety_filter_moment_intervention_norm_nm",
        "safety_filter_torque_residual_nm",
        "safety_filter_nominal_executable_force_norm_n",
        "safety_filter_filtered_executable_force_norm_n",
    )
    payload.update({key: np.asarray(trace[key]) for key in diagnostic_keys})
    payload.update(
        {
            "command_time_s": np.asarray(plant.command_time_s),
            "command_force_world_n": np.asarray(plant.command_force_world_n),
            "command_moment_world_nm": np.asarray(plant.command_moment_world_nm),
            "allocator_force_world_n": np.asarray(plant.allocator_force_world_n),
            "allocator_moment_world_nm": np.asarray(
                plant.allocator_moment_world_nm
            ),
        }
    )
    return payload


def _run_metrics(
    trajectory: Any,
    alpha: float,
    scaled_horizon_s: float,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    plant: SnapshotCapturePlant,
) -> dict[str, Any]:
    command_force = _norm_rows(np.asarray(plant.command_force_world_n))
    physical_force = _norm_rows(trace["cuff_force_local_n_god_view"])
    physical_moment = _norm_rows(trace["cuff_moment_local_nm_god_view"])
    status = np.asarray(trace["safety_filter_status"])
    lambdas = np.asarray(trace["safety_filter_lambda"], dtype=float)
    intervention = np.asarray(
        trace["safety_filter_intervention_coordinate_norm"], dtype=float
    )
    force_intervention = np.asarray(
        trace["safety_filter_force_intervention_norm_n"], dtype=float
    )
    moment_intervention = np.asarray(
        trace["safety_filter_moment_intervention_norm_nm"], dtype=float
    )
    events = summary["events"]
    supervisor = summary["track_brake_supervisor"]
    completion = bool(summary["mechanically_completed_requested_duration"])
    endpoint = summary["termination_reason"] == "reference_completed"
    command_safe = bool(
        len(command_force) and np.max(command_force) <= FORCE_GATE_N + 1e-9
    )
    physical_safe = bool(
        len(physical_force) and np.max(physical_force) <= FORCE_GATE_N + 1e-9
    )
    warning_count = int(sum(events["mujoco_warning_counts"].values()))
    structural_event_count = len(events["unintended_contact_pairs"])
    no_events = bool(
        events["rom_event_samples"] == 0
        and events["mpc_solver_failures"] == 0
        and warning_count == 0
        and summary["robot"]["joint_position_limit_samples"] == 0
        and structural_event_count == 0
    )
    no_permanent_brake = bool(
        supervisor["active_mode"] == TRACK
        and supervisor["terminal_status"] is None
    )
    passed = bool(
        completion
        and endpoint
        and command_safe
        and physical_safe
        and no_events
        and no_permanent_brake
    )
    q_deg = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    alpha_trace = np.asarray(trace["reference_speed_scale"], dtype=float)
    beta = np.asarray(trace["dynamic_base_estimate"], dtype=float)
    expected_beta = nominal_base_parameters(HUMAN)
    prior_only_exact = bool(
        np.allclose(
            beta,
            np.broadcast_to(expected_beta, beta.shape),
            rtol=0.0,
            atol=1e-12,
        )
    )
    fixed_clock_exact = bool(
        np.allclose(alpha_trace, alpha, rtol=0.0, atol=1e-12)
    )
    return {
        "schema_version": "high_rom_time_scale_run_v1",
        "evidence_category": "engineering_feasibility_audit_not_formal",
        "trajectory": trajectory.name,
        "endpoint_deg": list(trajectory.endpoint_deg),
        "alpha_scan": alpha,
        "ideal_scaled_duration_s": NOMINAL_PATH_DURATION_S / alpha,
        "scheduled_grid_aligned_duration_s": scaled_horizon_s,
        "observed_duration_s": float(summary["completed_duration_s"]),
        "pass": passed,
        "completion": {
            "full_reference_progress": completion,
            "endpoint_completed": endpoint,
            "termination_reason": summary["termination_reason"],
            "final_reference_phase_s": float(
                trace["reference_phase_time_s"][-1]
            ),
            "permanent_brake": not no_permanent_brake,
            "timeout": summary["termination_reason"] == "completed" and not completion,
        },
        "angles_deg": {
            "final_hip_knee": q_deg[-1].tolist(),
            "peak_hip_knee": np.max(q_deg, axis=0).tolist(),
        },
        "tracking": {
            "rmse_hip_knee_deg": summary["tracking"]["rmse_deg"],
            "combined_rmse_deg": summary["tracking"]["combined_rmse_deg"],
            "max_abs_hip_knee_deg": summary["tracking"]["max_abs_error_deg"],
        },
        "command_force_norm_n": _distribution(command_force),
        "physical_force_norm_n": {
            **_distribution(physical_force),
            "over_limit_duration_s": float(
                SIMULATION_DT_S * np.count_nonzero(physical_force > FORCE_GATE_N)
            ),
        },
        "physical_cuff_moment_norm_nm": _distribution(physical_moment),
        "safety_filter": {
            "status_counts": _status_counts(status),
            "abs_lambda": _distribution(np.abs(lambdas)),
            "intervention_coordinate_norm": _distribution(intervention),
            "force_intervention_norm_n": _distribution(force_intervention),
            "moment_intervention_norm_nm": _distribution(moment_intervention),
            "maximum_torque_preservation_residual_nm": float(
                np.max(trace["safety_filter_torque_residual_nm"])
            ),
        },
        "wrench_slew": {
            "allocator_force_n_per_s": _rate_distribution(
                np.asarray(plant.command_time_s),
                np.asarray(plant.allocator_force_world_n),
            ),
            "allocator_moment_nm_per_s": _rate_distribution(
                np.asarray(plant.command_time_s),
                np.asarray(plant.allocator_moment_world_nm),
            ),
            "total_command_force_n_per_s": _rate_distribution(
                np.asarray(plant.command_time_s),
                np.asarray(plant.command_force_world_n),
            ),
            "total_command_moment_nm_per_s": _rate_distribution(
                np.asarray(plant.command_time_s),
                np.asarray(plant.command_moment_world_nm),
            ),
        },
        "brake": {
            "transition_count": supervisor["transition_count"],
            "cycle_count": supervisor["brake_cycle_count"],
            "duration_s": CONTROL_DT_S * supervisor["brake_cycle_count"],
            "trigger": supervisor["trigger"],
            "terminal_status": supervisor["terminal_status"],
            "active_mode": supervisor["active_mode"],
        },
        "motion": _smoothness(trace),
        "runtime": summary["computational_cost"],
        "events": {
            **events,
            "robot_joint_position_limit_samples": summary["robot"][
                "joint_position_limit_samples"
            ],
            "structural_event_count": structural_event_count,
        },
        "frozen_contract_checks": {
            "population_prior_exact_throughout": prior_only_exact,
            "fixed_external_alpha_exact_throughout": fixed_clock_exact,
            "all_executed_command_force_at_or_below_200n": command_safe,
            "suspended_bed_force_zero": bool(
                np.max(np.asarray(trace["bed_force_n_god_view"])) == 0.0
            ),
            "adaptive_model_applied": False,
            "controller_parameters_changed": False,
        },
    }


def _run_one(
    *,
    trajectory: Any,
    alpha: float,
    case: Any,
    matrix: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    scaled_horizon_s = _scaled_horizon_s(alpha)
    allocator = default_engineering_cuff_allocator()
    clock = FixedExternalTimeScale(trajectory.reference, alpha)
    supervisor = TrackBrakeSupervisor()
    plants: list[SnapshotCapturePlant] = []

    def plant_factory(human: Any) -> SnapshotCapturePlant:
        plant = SnapshotCapturePlant(human)
        plants.append(plant)
        return plant

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN,
        )

    summary, trace = run_sensor_realism_case(
        case,
        duration_s=scaled_horizon_s,
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__alpha_{alpha:.6f}",
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
        reference_execution=clock,
        reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
        capture_system_pilot_diagnostics=True,
        track_brake_supervisor=supervisor,
        mpc_factory=lambda: HumanSpaceMPC(cuff_allocator=allocator),
        cuff_allocator=allocator,
        estimator_factory=estimator_factory,
    )
    if len(plants) != 1:
        raise RuntimeError("time-scale run did not retain exactly one plant")
    plant = plants[0]
    metrics = _run_metrics(
        trajectory, alpha, scaled_horizon_s, summary, trace, plant
    )
    checks = metrics["frozen_contract_checks"]
    if not all(
        checks[name]
        for name in (
            "population_prior_exact_throughout",
            "fixed_external_alpha_exact_throughout",
            "all_executed_command_force_at_or_below_200n",
            "suspended_bed_force_zero",
        )
    ):
        raise RuntimeError(f"frozen audit contract failed: {checks}")
    run_dir.mkdir(parents=True)
    write_strict_json(run_dir / "metrics.json", metrics)
    np.savez_compressed(
        run_dir / "compact_trace.npz", **_compact_trace(trace, plant)
    )
    if metrics["pass"]:
        if plant.last_safe_state is None:
            raise RuntimeError("completed run has no final safe state")
        _save_snapshot(
            run_dir / "final_safe_snapshot.npz",
            plant.last_safe_state,
            plant.last_safe_context,
            alpha=alpha,
            trajectory_name=trajectory.name,
            kind="final_safe",
            termination_reason=metrics["completion"]["termination_reason"],
        )
    else:
        plant.finalize_controller_failure(
            metrics["completion"]["termination_reason"]
        )
        if plant.last_safe_state is None or plant.first_failure_state is None:
            raise RuntimeError("failed run did not retain boundary states")
        _save_snapshot(
            run_dir / "last_safe_snapshot.npz",
            plant.last_safe_state,
            plant.last_safe_context,
            alpha=alpha,
            trajectory_name=trajectory.name,
            kind="last_safe",
            termination_reason=metrics["completion"]["termination_reason"],
        )
        _save_snapshot(
            run_dir / "first_failure_snapshot.npz",
            plant.first_failure_state,
            plant.first_failure_context,
            alpha=alpha,
            trajectory_name=trajectory.name,
            kind="first_failure",
            termination_reason=metrics["completion"]["termination_reason"],
        )
    del trace
    return metrics


def _recapture_boundary_prefix(
    *,
    trajectory: Any,
    alpha: float,
    case: Any,
    run_dir: Path,
) -> dict[str, Any]:
    """Replay only to the registered run's first FILTER_INFEASIBLE state."""

    trace_path = run_dir / "compact_trace.npz"
    metrics_path = run_dir / "metrics.json"
    metrics_hash_before = _file_sha256(metrics_path)
    with np.load(trace_path, allow_pickle=False) as trace:
        statuses = np.asarray(trace["safety_filter_status"])
        indices = np.flatnonzero(statuses == FILTER_INFEASIBLE)
        if not len(indices):
            raise RuntimeError(f"boundary has no FILTER_INFEASIBLE: {run_dir}")
        expected_time_s = float(trace["safety_filter_time_s"][indices[0]])
    allocator = default_engineering_cuff_allocator()
    clock = FixedExternalTimeScale(trajectory.reference, alpha)
    supervisor = TrackBrakeSupervisor()
    plants: list[SnapshotCapturePlant] = []

    def plant_factory(human: Any) -> SnapshotCapturePlant:
        plant = SnapshotCapturePlant(human)
        plants.append(plant)
        return plant

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN,
        )

    def failure_callback(status: str, metadata: Mapping[str, Any]) -> None:
        if len(plants) != 1:
            raise RuntimeError("boundary replay has no unique plant")
        plants[0].capture_controller_failure(status, metadata)
        raise BoundarySnapshotCaptured(status)

    clock.failure_callback = failure_callback
    try:
        run_sensor_realism_case(
            case,
            duration_s=_scaled_horizon_s(alpha),
            estimator_architecture="integral_minimal",
            result_case_name=f"{trajectory.name}__alpha_{alpha:.6f}__snapshot_prefix",
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
            reference_execution=clock,
            reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
            capture_system_pilot_diagnostics=True,
            track_brake_supervisor=supervisor,
            mpc_factory=lambda: HumanSpaceMPC(cuff_allocator=allocator),
            cuff_allocator=allocator,
            estimator_factory=estimator_factory,
        )
    except BoundarySnapshotCaptured:
        pass
    else:
        raise RuntimeError("boundary prefix replay reached no controller failure")
    plant = plants[0]
    if plant.last_safe_state is None or plant.first_failure_state is None:
        raise RuntimeError("boundary prefix replay did not retain both states")
    captured_time_s = float(plant.first_failure_context["time_s"])
    if not np.isclose(captured_time_s, expected_time_s, rtol=0.0, atol=1.0e-9):
        raise RuntimeError(
            f"boundary replay time mismatch: {captured_time_s} vs {expected_time_s}"
        )
    termination_reason = str(
        json.loads(metrics_path.read_text())["completion"]["termination_reason"]
    )
    _save_snapshot(
        run_dir / "last_safe_snapshot.npz",
        plant.last_safe_state,
        plant.last_safe_context,
        alpha=alpha,
        trajectory_name=trajectory.name,
        kind="last_safe_before_permanent_brake_entry",
        termination_reason=termination_reason,
    )
    _save_snapshot(
        run_dir / "first_failure_snapshot.npz",
        plant.first_failure_state,
        plant.first_failure_context,
        alpha=alpha,
        trajectory_name=trajectory.name,
        kind="first_failure_permanent_brake_entry",
        termination_reason=termination_reason,
    )
    metrics_hash_after = _file_sha256(metrics_path)
    if metrics_hash_after != metrics_hash_before:
        raise RuntimeError("boundary recapture changed registered run metrics")
    return {
        "trajectory": trajectory.name,
        "alpha_scan": alpha,
        "expected_first_filter_infeasible_time_s": expected_time_s,
        "captured_first_failure_time_s": captured_time_s,
        "metrics_sha256_unchanged": metrics_hash_after,
        "prefix_replay_stopped_at_first_failure": True,
    }


def _is_monotone(results: dict[float, dict[str, Any]]) -> bool:
    seen_failure = False
    for alpha in sorted(results):
        if results[alpha]["pass"]:
            if seen_failure:
                return False
        else:
            seen_failure = True
    return True


def _write_progress(
    output_dir: Path,
    spec_path: Path,
    spec_hash: str,
    all_results: dict[str, dict[float, dict[str, Any]]],
) -> None:
    write_strict_json(
        output_dir / "scan_progress.json",
        {
            "schema_version": "high_rom_time_scale_progress_v1",
            "spec": str(spec_path),
            "spec_sha256": spec_hash,
            "results": {
                name: [results[alpha] for alpha in sorted(results)]
                for name, results in all_results.items()
            },
        },
    )


def _classify(results: dict[float, dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(results)
    if not _is_monotone(results):
        return {
            "classification": "D_NON_MONOTONE_CONTROLLER_SWITCH_LIMITED",
            "monotone_with_speed": False,
            "maximum_safe_alpha": None,
            "minimum_safe_completion_time_s": None,
            "limitation": "controller_switch_limited_nonmonotone",
        }
    if 0.125 in results and not results[0.125]["pass"]:
        return {
            "classification": "C_NOT_SPEED_RESOLVABLE",
            "monotone_with_speed": True,
            "maximum_safe_alpha": None,
            "minimum_safe_completion_time_s": None,
            "limitation": "persists_at_alpha_0.125_near_quasi_static_test",
        }
    if all(results[alpha]["pass"] for alpha in ordered) and max(ordered) >= 1.0:
        return {
            "classification": "B_FEASIBLE_THROUGH_TESTED_RANGE",
            "monotone_with_speed": True,
            "maximum_safe_alpha": 1.0,
            "minimum_safe_completion_time_s": results[1.0][
                "observed_duration_s"
            ],
            "limitation": "none_through_tested_range",
        }
    passes = [alpha for alpha in ordered if results[alpha]["pass"]]
    failures = [alpha for alpha in ordered if not results[alpha]["pass"]]
    if passes and failures and max(passes) < min(failures):
        best = max(passes)
        return {
            "classification": "A_SPEED_LIMITED_FEASIBLE",
            "monotone_with_speed": True,
            "maximum_safe_alpha": best,
            "minimum_safe_completion_time_s": results[best][
                "observed_duration_s"
            ],
            "limitation": "speed_dependent_with_registered_bracket",
            "safe_alpha_lower_bound": best,
            "failure_alpha_upper_bound": min(failures),
            "final_bracket_width": min(failures) - best,
        }
    raise RuntimeError("scan results do not match a registered classification")


def _boundary_manifest(
    trajectory_name: str,
    results: dict[float, dict[str, Any]],
    classification: dict[str, Any],
) -> dict[str, Any]:
    passes = sorted(alpha for alpha, item in results.items() if item["pass"])
    failures = sorted(alpha for alpha, item in results.items() if not item["pass"])
    if classification["classification"] == "A_SPEED_LIMITED_FEASIBLE":
        boundary = [max(passes), min(failures)]
    elif classification["classification"] == "B_FEASIBLE_THROUGH_TESTED_RANGE":
        boundary = [1.0]
    elif classification["classification"] == "C_NOT_SPEED_RESOLVABLE":
        boundary = [0.125]
    else:
        boundary = sorted(results)
    return {
        "trajectory": trajectory_name,
        "classification": classification["classification"],
        "boundary_alphas": boundary,
        "run_directories": [_alpha_key(alpha) for alpha in boundary],
        "snapshot_rule": (
            "passing boundary runs retain final_safe; failed boundary runs retain "
            "last_safe and first_failure"
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "trajectory",
        "alpha_scan",
        "ideal_scaled_duration_s",
        "observed_duration_s",
        "pass",
        "termination_reason",
        "final_hip_deg",
        "final_knee_deg",
        "peak_hip_deg",
        "peak_knee_deg",
        "tracking_combined_rmse_deg",
        "tracking_max_hip_deg",
        "tracking_max_knee_deg",
        "command_force_rms_n",
        "command_force_p95_n",
        "command_force_peak_n",
        "physical_force_rms_n",
        "physical_force_p95_n",
        "physical_force_peak_n",
        "physical_force_over_limit_duration_s",
        "cuff_moment_rms_nm",
        "cuff_moment_peak_nm",
        "safe_unchanged_count",
        "safe_filtered_count",
        "filter_infeasible_count",
        "peak_abs_lambda",
        "peak_filter_force_intervention_n",
        "peak_filter_moment_intervention_nm",
        "peak_filter_intervention_coordinate_norm",
        "maximum_torque_preservation_residual_nm",
        "peak_allocator_force_slew_n_per_s",
        "peak_allocator_moment_slew_nm_per_s",
        "peak_total_command_force_slew_n_per_s",
        "peak_total_command_moment_slew_nm_per_s",
        "brake_count",
        "brake_duration_s",
        "brake_trigger",
        "brake_terminal_status",
        "acceleration_rms_deg_s2",
        "jerk_rms_deg_s3",
        "mpc_p95_ms",
        "mpc_max_ms",
        "mpc_deadline_miss_count",
        "safety_filter_p95_ms",
        "safety_filter_max_ms",
        "safety_filter_deadline_miss_count",
        "rollout_wall_time_s",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _csv_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "trajectory": item["trajectory"],
        "alpha_scan": item["alpha_scan"],
        "ideal_scaled_duration_s": item["ideal_scaled_duration_s"],
        "observed_duration_s": item["observed_duration_s"],
        "pass": item["pass"],
        "termination_reason": item["completion"]["termination_reason"],
        "final_hip_deg": item["angles_deg"]["final_hip_knee"][0],
        "final_knee_deg": item["angles_deg"]["final_hip_knee"][1],
        "peak_hip_deg": item["angles_deg"]["peak_hip_knee"][0],
        "peak_knee_deg": item["angles_deg"]["peak_hip_knee"][1],
        "tracking_combined_rmse_deg": item["tracking"]["combined_rmse_deg"],
        "tracking_max_hip_deg": item["tracking"]["max_abs_hip_knee_deg"][0],
        "tracking_max_knee_deg": item["tracking"]["max_abs_hip_knee_deg"][1],
        "command_force_rms_n": item["command_force_norm_n"]["rms"],
        "command_force_p95_n": item["command_force_norm_n"]["p95"],
        "command_force_peak_n": item["command_force_norm_n"]["peak"],
        "physical_force_rms_n": item["physical_force_norm_n"]["rms"],
        "physical_force_p95_n": item["physical_force_norm_n"]["p95"],
        "physical_force_peak_n": item["physical_force_norm_n"]["peak"],
        "physical_force_over_limit_duration_s": item["physical_force_norm_n"][
            "over_limit_duration_s"
        ],
        "cuff_moment_rms_nm": item["physical_cuff_moment_norm_nm"]["rms"],
        "cuff_moment_peak_nm": item["physical_cuff_moment_norm_nm"]["peak"],
        "safe_unchanged_count": item["safety_filter"]["status_counts"][
            SAFE_UNCHANGED
        ],
        "safe_filtered_count": item["safety_filter"]["status_counts"][
            SAFE_FILTERED
        ],
        "filter_infeasible_count": item["safety_filter"]["status_counts"][
            FILTER_INFEASIBLE
        ],
        "peak_abs_lambda": item["safety_filter"]["abs_lambda"]["peak"],
        "peak_filter_force_intervention_n": item["safety_filter"][
            "force_intervention_norm_n"
        ]["peak"],
        "peak_filter_moment_intervention_nm": item["safety_filter"][
            "moment_intervention_norm_nm"
        ]["peak"],
        "peak_filter_intervention_coordinate_norm": item["safety_filter"][
            "intervention_coordinate_norm"
        ]["peak"],
        "maximum_torque_preservation_residual_nm": item["safety_filter"][
            "maximum_torque_preservation_residual_nm"
        ],
        "peak_allocator_force_slew_n_per_s": item["wrench_slew"][
            "allocator_force_n_per_s"
        ]["peak"],
        "peak_allocator_moment_slew_nm_per_s": item["wrench_slew"][
            "allocator_moment_nm_per_s"
        ]["peak"],
        "peak_total_command_force_slew_n_per_s": item["wrench_slew"][
            "total_command_force_n_per_s"
        ]["peak"],
        "peak_total_command_moment_slew_nm_per_s": item["wrench_slew"][
            "total_command_moment_nm_per_s"
        ]["peak"],
        "brake_count": item["brake"]["transition_count"],
        "brake_duration_s": item["brake"]["duration_s"],
        "brake_trigger": item["brake"]["trigger"] or "none",
        "brake_terminal_status": item["brake"]["terminal_status"] or "none",
        "acceleration_rms_deg_s2": item["motion"][
            "acceleration_combined_rms_deg_s2"
        ],
        "jerk_rms_deg_s3": item["motion"]["jerk_combined_rms_deg_s3"],
        "mpc_p95_ms": item["runtime"]["mpc"]["p95_ms"],
        "mpc_max_ms": item["runtime"]["mpc"]["max_ms"],
        "mpc_deadline_miss_count": item["runtime"]["mpc"][
            "deadline_miss_count"
        ],
        "safety_filter_p95_ms": item["runtime"]["safety_filter"]["p95_ms"],
        "safety_filter_max_ms": item["runtime"]["safety_filter"]["max_ms"],
        "safety_filter_deadline_miss_count": item["runtime"]["safety_filter"][
            "deadline_miss_count"
        ],
        "rollout_wall_time_s": item["runtime"]["rollout_wall_time_s"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--recapture-boundary-snapshots", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_path = args.spec.resolve()
    spec_hash = _file_sha256(spec_path)
    if spec_hash != DEFAULT_SPEC_HASH:
        raise RuntimeError(
            f"scan spec hash drifted: expected {DEFAULT_SPEC_HASH}, got {spec_hash}"
        )
    spec = json.loads(spec_path.read_text())
    if spec["single_changed_variable"] != "alpha_scan":
        raise RuntimeError("scan spec changed-variable contract drifted")
    if args.validate_only:
        print(
            json.dumps(
                {
                    "spec": str(spec_path),
                    "sha256": spec_hash,
                    "initial_alpha": spec["scan_rule"]["initial_alpha"],
                    "trajectory_count": len(spec["trajectories"]),
                    "no_runs_started": True,
                },
                sort_keys=True,
            )
        )
        return 0
    output_dir = args.output_dir.resolve()
    if args.recapture_boundary_snapshots:
        if not output_dir.exists():
            raise FileNotFoundError(f"scan output does not exist: {output_dir}")
    else:
        if output_dir.exists():
            raise FileExistsError(f"refusing to overwrite scan: {output_dir}")
        output_dir.mkdir(parents=True)
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix, measurement_seed=44104)
    if case.seed != 44104:
        raise RuntimeError("measurement seed drifted")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != spec["checkpoint_commit"]:
        raise RuntimeError(
            "audit must run from checkpoint commit plus uncommitted audit-only files"
        )
    if args.recapture_boundary_snapshots:
        registered = json.loads((output_dir / "scan_summary.json").read_text())
        records: list[dict[str, Any]] = []
        trajectories_by_name = {item.name: item for item in TRAJECTORIES}
        for name, boundary in registered["boundaries"].items():
            for alpha in boundary["boundary_alphas"]:
                run_dir = output_dir / name / _alpha_key(float(alpha))
                metrics = json.loads((run_dir / "metrics.json").read_text())
                if metrics["pass"]:
                    continue
                records.append(
                    _recapture_boundary_prefix(
                        trajectory=trajectories_by_name[name],
                        alpha=float(alpha),
                        case=case,
                        run_dir=run_dir,
                    )
                )
                print(json.dumps(records[-1], sort_keys=True), flush=True)
        write_strict_json(
            output_dir / "boundary_snapshot_recapture.json",
            {
                "schema_version": "high_rom_boundary_snapshot_recapture_v1",
                "reason": (
                    "replace endpoint/final controller snapshots with the exact "
                    "first FILTER_INFEASIBLE state that begins the permanent BRAKE"
                ),
                "registered_scan_metrics_changed": False,
                "records": records,
            },
        )
        return 0
    all_results: dict[str, dict[float, dict[str, Any]]] = {
        trajectory.name: {} for trajectory in TRAJECTORIES
    }

    def execute(trajectory: Any, alpha: float) -> dict[str, Any]:
        alpha = round(float(alpha), 6)
        results = all_results[trajectory.name]
        if alpha in results:
            return results[alpha]
        run_dir = output_dir / trajectory.name / _alpha_key(alpha)
        item = _run_one(
            trajectory=trajectory,
            alpha=alpha,
            case=case,
            matrix=matrix,
            run_dir=run_dir,
        )
        results[alpha] = item
        _write_progress(output_dir, spec_path, spec_hash, all_results)
        print(
            json.dumps(
                {
                    "trajectory": trajectory.name,
                    "alpha": alpha,
                    "pass": item["pass"],
                    "termination": item["completion"]["termination_reason"],
                    "duration_s": item["observed_duration_s"],
                    "physical_force_peak_n": item["physical_force_norm_n"]["peak"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return item

    classifications: dict[str, dict[str, Any]] = {}
    boundary_manifests: dict[str, dict[str, Any]] = {}
    resolution = float(spec["scan_rule"]["bisection_alpha_resolution"])
    for trajectory in TRAJECTORIES:
        initial = execute(trajectory, 0.25)
        results = all_results[trajectory.name]
        if not initial["pass"]:
            slow = execute(trajectory, 0.125)
            if slow["pass"]:
                low, high = 0.125, 0.25
                while high - low > resolution + 1.0e-12:
                    midpoint = round(0.5 * (low + high), 6)
                    item = execute(trajectory, midpoint)
                    if item["pass"]:
                        low = midpoint
                    else:
                        high = midpoint
            classification = _classify(results)
        else:
            for alpha in (0.5, 0.75, 1.0):
                execute(trajectory, alpha)
            if _is_monotone(results) and not all(
                item["pass"] for item in results.values()
            ):
                low = max(alpha for alpha, item in results.items() if item["pass"])
                high = min(
                    alpha for alpha, item in results.items() if not item["pass"]
                )
                while high - low > resolution + 1.0e-12:
                    midpoint = round(0.5 * (low + high), 6)
                    item = execute(trajectory, midpoint)
                    if item["pass"]:
                        low = midpoint
                    else:
                        high = midpoint
            classification = _classify(results)
        classifications[trajectory.name] = classification
        boundary_manifests[trajectory.name] = _boundary_manifest(
            trajectory.name, results, classification
        )
        write_strict_json(
            output_dir / trajectory.name / "boundary.json",
            boundary_manifests[trajectory.name],
        )

    rows = [
        _csv_row(all_results[name][alpha])
        for name in [trajectory.name for trajectory in TRAJECTORIES]
        for alpha in sorted(all_results[name])
    ]
    _write_csv(output_dir / "alpha_results.csv", rows)
    payload = {
        "schema_version": "high_rom_time_scale_audit_summary_v1",
        "evidence_category": "engineering_feasibility_audit_not_formal",
        "spec": str(spec_path),
        "spec_sha256": spec_hash,
        "checkpoint_commit": commit,
        "branch": "codex/high-rom-time-scale-audit",
        "measurement_case": measurement_case_dict(case),
        "mpc_config": asdict(HumanMPCConfig()),
        "single_changed_variable": "alpha_scan",
        "run_count": len(rows),
        "results": {
            name: [all_results[name][alpha] for alpha in sorted(all_results[name])]
            for name in all_results
        },
        "classifications": classifications,
        "boundaries": boundary_manifests,
        "controller_patched_based_on_results": False,
        "formal_scientific_run": False,
    }
    write_strict_json(output_dir / "scan_summary.json", payload)
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "run_count": len(rows),
                "classifications": {
                    name: item["classification"]
                    for name, item in classifications.items()
                },
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
