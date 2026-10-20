#!/usr/bin/env python3
"""Matched CR12/UR10e grasp and execution diagnostics for the early event."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage4 import sensor_realism
from traction_mpc_stage4.measurement import MeasurementCase
from traction_mpc_stage4.reference import TEACHING_WAYPOINTS, teaching_reference
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor
from traction_mpc_stage5 import goal_mpc_smoke as goal_mpc_smoke_module
from traction_mpc_stage5.baseline_replay import (
    FixedStage5Estimator,
    Stage5SensorBoundaryPlant,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import NOMINAL_PHYSICS_DT_S
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage3.human import sleeve_jacobian


GOAL_DURATION_S = 0.35
REPLAY_DURATION_S = 1.35
MOTION_START_S = 1.0


def _rotation_error_vector(target: np.ndarray, actual: np.ndarray) -> np.ndarray:
    return Rotation.from_matrix(target @ actual.T).as_rotvec()


def _capsule_clearance_to_bed(plant: Any, geom_id: int) -> float:
    center = np.asarray(plant.data.geom_xpos[geom_id], dtype=float)
    rotation = np.asarray(plant.data.geom_xmat[geom_id], dtype=float).reshape(3, 3)
    radius = float(plant.model.geom_size[geom_id, 0])
    half_length = float(plant.model.geom_size[geom_id, 1])
    lowest_z = center[2] - abs(rotation[2, 2]) * half_length - radius
    bed_z = float(plant.data.geom_xpos[plant.bed_geom_id, 2])
    return lowest_z - bed_z


class _GraspTelemetryMixin:
    """Append-only MuJoCo truth telemetry; never read by the controller."""

    def __init__(self, human: Any, *, interface_parameters: Any = None) -> None:
        self.grasp_telemetry: list[dict[str, Any]] = []
        self.goal_targets: dict[float, dict[str, Any]] = {}
        self.prescribed_targets: dict[float, dict[str, Any]] = {}
        kwargs = {} if interface_parameters is None else {"interface_parameters": interface_parameters}
        super().__init__(human, **kwargs)

    def _target_record(
        self,
        *,
        position: np.ndarray,
        rotation: np.ndarray,
        linear_velocity: np.ndarray,
        angular_velocity: np.ndarray,
    ) -> dict[str, Any]:
        return {
            "position_m": np.asarray(position, dtype=float).copy(),
            "rotation": np.asarray(rotation, dtype=float).copy(),
            "linear_velocity_m_s": np.asarray(linear_velocity, dtype=float).copy(),
            "angular_velocity_rad_s": np.asarray(angular_velocity, dtype=float).copy(),
        }

    def record_goal_target(self, target: Any) -> None:
        robot = target.robot_cuff_target
        self.goal_targets[round(float(self.data.time), 12)] = self._target_record(
            position=robot.world_from_cuff.translation,
            rotation=robot.world_from_cuff.rotation,
            linear_velocity=robot.linear_velocity_world_m_s,
            angular_velocity=robot.angular_velocity_world_rad_s,
        )

    def apply_measured_nominal_cartesian_control(
        self,
        measurement: Any,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray,
        target_angular_velocity_rad_s: np.ndarray,
        feedforward_wrench_world: np.ndarray,
    ):
        self.prescribed_targets[round(float(self.data.time), 12)] = self._target_record(
            position=target_position_m,
            rotation=target_rotation_matrix,
            linear_velocity=target_velocity_m_s,
            angular_velocity=target_angular_velocity_rad_s,
        )
        return super().apply_measured_nominal_cartesian_control(
            measurement,
            target_position_m,
            target_velocity_m_s,
            target_rotation_matrix,
            target_angular_velocity_rad_s,
            feedforward_wrench_world,
        )

    def observe(self):
        observation = super().observe()
        timestamp = round(float(observation.time_s), 12)
        if self.grasp_telemetry and math.isclose(
            self.grasp_telemetry[-1]["time_s"], timestamp, abs_tol=1.0e-12
        ):
            return observation
        flange_rotation = np.asarray(
            self.data.site_xmat[self.flange_site_id], dtype=float
        ).reshape(3, 3).copy()
        flange_position = self.data.site_xpos[self.flange_site_id].copy()
        cuff_rotation = np.asarray(observation.attachment_rotation_matrix, dtype=float)
        cuff_position = np.asarray(observation.attachment_position_m, dtype=float)
        flange_from_cuff_rotation = flange_rotation.T @ cuff_rotation
        flange_from_cuff_translation = flange_rotation.T @ (
            cuff_position - flange_position
        )
        jacobian = np.asarray(self.robot_attachment_jacobian(), dtype=float)
        singular = np.linalg.svd(jacobian, compute_uv=False)
        linear_singular = np.linalg.svd(jacobian[:3], compute_uv=False)
        contacts = []
        for index in range(int(self.data.ncon)):
            contact = self.data.contact[index]
            geom_ids = {int(contact.geom1), int(contact.geom2)}
            if self.bed_geom_id not in geom_ids or not bool(geom_ids & self.human_geom_ids):
                continue
            human_geom_id = next(iter(geom_ids & self.human_geom_ids))
            contacts.append(
                {
                    "human_geom": self.model.geom(human_geom_id).name,
                    "position_world_m": np.asarray(contact.pos, dtype=float).copy(),
                    "distance_m": float(contact.dist),
                }
            )
        thigh_id = self.model.geom("thigh_geom").id
        shank_id = self.model.geom("shank_geom").id
        self.grasp_telemetry.append(
            {
                "time_s": timestamp,
                "human_q_rad": np.asarray(observation.human_q_rad, dtype=float).copy(),
                "human_dq_rad_s": np.asarray(observation.human_dq_rad_s, dtype=float).copy(),
                "robot_q_rad": np.asarray(observation.robot_q_rad, dtype=float).copy(),
                "robot_dq_rad_s": np.asarray(observation.robot_dq_rad_s, dtype=float).copy(),
                "flange_position_world_m": flange_position,
                "flange_rotation_world": flange_rotation,
                "cuff_position_world_m": cuff_position.copy(),
                "cuff_rotation_world": cuff_rotation.copy(),
                "cuff_linear_velocity_world_m_s": np.asarray(
                    observation.attachment_velocity_m_s, dtype=float
                ).copy(),
                "cuff_angular_velocity_world_rad_s": np.asarray(
                    observation.attachment_angular_velocity_rad_s, dtype=float
                ).copy(),
                "flange_from_cuff_translation_m": flange_from_cuff_translation,
                "flange_from_cuff_rotation": flange_from_cuff_rotation,
                "cuff_jacobian": jacobian,
                "cuff_jacobian_singular_values": singular,
                "cuff_jacobian_condition": float(singular[0] / singular[-1]),
                "linear_jacobian_singular_values": linear_singular,
                "linear_jacobian_condition": float(
                    linear_singular[0] / linear_singular[-1]
                ),
                "cuff_wrench_world": np.concatenate(
                    [observation.cuff_force_vector_n, observation.cuff_moment_vector_nm]
                ),
                "human_generalized_input_nm": np.asarray(
                    observation.human_constraint_torque_nm, dtype=float
                ).copy(),
                "bed_force_n": float(observation.bed_force_n),
                "bed_contact_count": int(observation.bed_contact_count),
                "human_table_contacts": contacts,
                "thigh_table_clearance_m": _capsule_clearance_to_bed(self, thigh_id),
                "shank_table_clearance_m": _capsule_clearance_to_bed(self, shank_id),
            }
        )
        return observation


class _TelemetryCR12Plant(_GraspTelemetryMixin, Stage5CR12SensorBoundaryPlant):
    pass


class _TelemetryUR10ePlant(_GraspTelemetryMixin, Stage5SensorBoundaryPlant):
    pass


def _plant_class(robot: str):
    return _TelemetryCR12Plant if robot == "cr12" else _TelemetryUR10ePlant


def _recording_execution_context(original):
    def wrapped(*, plant: Any, target: Any, **kwargs: Any):
        if isinstance(plant, _GraspTelemetryMixin):
            plant.record_goal_target(target)
        return original(plant=plant, target=target, **kwargs)

    return wrapped


def _record_at(plant: Any, timestamp_s: float) -> dict[str, Any]:
    matches = [
        record
        for record in plant.grasp_telemetry
        if math.isclose(record["time_s"], timestamp_s, abs_tol=1.0e-10)
    ]
    if not matches:
        raise ValueError(f"no telemetry at {timestamp_s:.6f} s")
    return matches[-1]


def _target_at(targets: dict[float, dict[str, Any]], timestamp_s: float) -> dict[str, Any]:
    key = round(float(timestamp_s), 12)
    if key not in targets:
        prior = [time for time in targets if time <= key + 1.0e-12]
        if not prior:
            raise ValueError(f"no target at or before {timestamp_s:.6f} s")
        key = max(prior)
    return targets[key]


def _pose_tracking_row(record: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    position_error = target["position_m"] - record["cuff_position_world_m"]
    orientation_error = _rotation_error_vector(
        target["rotation"], record["cuff_rotation_world"]
    )
    linear_velocity_error = (
        target["linear_velocity_m_s"] - record["cuff_linear_velocity_world_m_s"]
    )
    angular_velocity_error = (
        target["angular_velocity_rad_s"]
        - record["cuff_angular_velocity_world_rad_s"]
    )
    return {
        "time_s": float(record["time_s"]),
        "desired_position_world_m": target["position_m"].tolist(),
        "actual_position_world_m": record["cuff_position_world_m"].tolist(),
        "desired_rotation_world": target["rotation"].tolist(),
        "actual_rotation_world": record["cuff_rotation_world"].tolist(),
        "position_error_mm": (1000.0 * position_error).tolist(),
        "position_error_norm_mm": float(1000.0 * np.linalg.norm(position_error)),
        "orientation_error_rotvec_deg": np.degrees(orientation_error).tolist(),
        "orientation_error_norm_deg": float(np.degrees(np.linalg.norm(orientation_error))),
        "desired_linear_velocity_world_m_s": target["linear_velocity_m_s"].tolist(),
        "actual_linear_velocity_world_m_s": record[
            "cuff_linear_velocity_world_m_s"
        ].tolist(),
        "linear_velocity_error_norm_mm_s": float(
            1000.0 * np.linalg.norm(linear_velocity_error)
        ),
        "angular_velocity_error_norm_deg_s": float(
            np.degrees(np.linalg.norm(angular_velocity_error))
        ),
    }


def _contact_summary(plant: Any) -> dict[str, Any]:
    records = plant.grasp_telemetry
    time = np.asarray([record["time_s"] for record in records], dtype=float)
    thigh = np.asarray([record["thigh_table_clearance_m"] for record in records])
    shank = np.asarray([record["shank_table_clearance_m"] for record in records])
    dt = np.diff(time)
    thigh_rate = np.r_[0.0, np.divide(np.diff(thigh), dt, out=np.zeros_like(dt), where=dt > 0)]
    shank_rate = np.r_[0.0, np.divide(np.diff(shank), dt, out=np.zeros_like(dt), where=dt > 0)]
    contact_indices = [
        index for index, record in enumerate(records) if record["human_table_contacts"]
    ]
    first = None
    if contact_indices:
        index = contact_indices[0]
        first = {
            "time_s": float(time[index]),
            "contacts": [
                {
                    "human_geom": item["human_geom"],
                    "position_world_m": item["position_world_m"].tolist(),
                    "distance_m": item["distance_m"],
                }
                for item in records[index]["human_table_contacts"]
            ],
            "thigh_clearance_mm": float(1000.0 * thigh[index]),
            "shank_clearance_mm": float(1000.0 * shank[index]),
            "thigh_clearance_rate_mm_s": float(1000.0 * thigh_rate[index]),
            "shank_clearance_rate_mm_s": float(1000.0 * shank_rate[index]),
        }
    first_by_geom = {}
    for geom_name in ("thigh_geom", "shank_geom"):
        matches = [
            (index, item)
            for index, record in enumerate(records)
            for item in record["human_table_contacts"]
            if item["human_geom"] == geom_name
        ]
        if matches:
            index, item = matches[0]
            first_by_geom[geom_name] = {
                "time_s": float(time[index]),
                "position_world_m": item["position_world_m"].tolist(),
                "distance_m": item["distance_m"],
                "thigh_clearance_mm": float(1000.0 * thigh[index]),
                "shank_clearance_mm": float(1000.0 * shank[index]),
                "thigh_clearance_rate_mm_s": float(1000.0 * thigh_rate[index]),
                "shank_clearance_rate_mm_s": float(1000.0 * shank_rate[index]),
                "bed_force_n": float(records[index]["bed_force_n"]),
            }
    return {
        "first_contact": first,
        "first_contact_by_human_geom": first_by_geom,
        "minimum_thigh_clearance_mm": float(1000.0 * np.min(thigh)),
        "minimum_shank_clearance_mm": float(1000.0 * np.min(shank)),
        "maximum_downward_thigh_clearance_rate_mm_s": float(
            1000.0 * np.min(thigh_rate)
        ),
        "maximum_downward_shank_clearance_rate_mm_s": float(
            1000.0 * np.min(shank_rate)
        ),
    }


def _goal_run(robot: str, output_dir: Path) -> tuple[dict[str, Any], Any]:
    holder: dict[str, Any] = {}

    def factory(parameters):
        plant = _plant_class(robot)(STAGE5_HUMAN, interface_parameters=parameters)
        holder["plant"] = plant
        return plant

    original = goal_mpc_smoke_module.build_stage5_loaded_execution_context
    with patch.object(
        goal_mpc_smoke_module,
        "build_stage5_loaded_execution_context",
        _recording_execution_context(original),
    ):
        summary = run_goal_mpc_smoke(
            output_dir,
            maximum_duration_s=GOAL_DURATION_S,
            plant_factory=factory,
            plant_case_name=f"grasp_execution_diagnostic__{robot}",
        )
    return summary, holder["plant"]


def _stage5_teaching_reference(time_s: float) -> CuffPoseReference:
    donor = teaching_reference(time_s)
    return CuffPoseReference(
        donor.q_rad.copy(),
        donor.dq_rad_s.copy(),
        donor.ddq_rad_s2.copy(),
        STAGE5_GEOMETRY.world_from_cuff(donor.q_rad, STAGE5_HUMAN),
    )


def _prescribed_target(time_s: float) -> dict[str, Any]:
    """Reconstruct the exact registered target used by the Stage-4 runner.

    The runner executes a precomputed command preview directly, so the plant-level
    Cartesian-control hook is not called.  Reconstructing the target from the same
    pure reference function keeps this diagnostic observational and exact.
    """
    reference = _stage5_teaching_reference(time_s)
    linear_human = sleeve_jacobian(reference.q_rad, STAGE5_HUMAN) @ reference.dq_rad_s
    angular_human = np.array(
        [0.0, reference.dq_rad_s[1] - reference.dq_rad_s[0], 0.0], dtype=float
    )
    world_from_human = STAGE5_GEOMETRY.world_from_human.rotation
    return {
        "position_m": reference.world_from_cuff.translation.copy(),
        "rotation": reference.world_from_cuff.rotation.copy(),
        "linear_velocity_m_s": world_from_human @ linear_human,
        "angular_velocity_rad_s": world_from_human @ angular_human,
    }


def _fixed_estimator(measurement: Any, initial_q: np.ndarray) -> FixedStage5Estimator:
    return FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        initial_q,
    )


def _prescribed_run(robot: str) -> tuple[dict[str, Any], dict[str, np.ndarray], Any]:
    holder: dict[str, Any] = {}

    def factory(human):
        plant = _plant_class(robot)(human)
        holder["plant"] = plant
        return plant

    control_substeps = int(round(sensor_realism.CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    ideal = MeasurementCase(name="grasp_diagnostic_ideal_200hz", update_rate_hz=200.0, latency_s=0.0)
    with patch.object(sensor_realism, "CONTROL_SUBSTEPS", control_substeps):
        summary, trace = run_sensor_realism_case(
            ideal,
            duration_s=REPLAY_DURATION_S,
            estimator_architecture="instantaneous_v2",
            result_case_name=f"grasp_diagnostic_prescribed__{robot}",
            true_human_override=STAGE5_HUMAN,
            true_metadata_override={"case": "stage5_registered_human_fixed_no_learning"},
            reference_fn=_stage5_teaching_reference,
            trajectory_label="existing_stage4_teaching_reference_first_1p35s",
            trajectory_waypoints=tuple(
                item for item in TEACHING_WAYPOINTS if item.time_s <= REPLAY_DURATION_S
            ),
            plant_factory=factory,
            track_brake_supervisor=TrackBrakeSupervisor(),
            estimator_factory=_fixed_estimator,
            capture_system_pilot_diagnostics=True,
        )
    return summary, trace, holder["plant"]


def _goal_metrics(robot: str, summary: dict[str, Any], plant: Any) -> dict[str, Any]:
    sample_times = [time for time in (0.0, 0.005, 0.01, 0.02, 0.1, 0.2, 0.28, 0.3, 0.305, 0.31, 0.315, 0.32) if time <= plant.grasp_telemetry[-1]["time_s"] + 1.0e-12]
    rows = []
    for timestamp in sample_times:
        record = _record_at(plant, timestamp)
        target = _target_at(plant.goal_targets, timestamp)
        row = _pose_tracking_row(record, target)
        row.update(
            {
                "human_q_deg": np.degrees(record["human_q_rad"]).tolist(),
                "human_dq_deg_s": np.degrees(record["human_dq_rad_s"]).tolist(),
                "robot_q_deg": np.degrees(record["robot_q_rad"]).tolist(),
                "robot_dq_deg_s": np.degrees(record["robot_dq_rad_s"]).tolist(),
                "cuff_jacobian_singular_values": record[
                    "cuff_jacobian_singular_values"
                ].tolist(),
                "cuff_jacobian_condition": record["cuff_jacobian_condition"],
                "linear_jacobian_condition": record["linear_jacobian_condition"],
                "cuff_wrench_world": record["cuff_wrench_world"].tolist(),
                "human_generalized_input_nm": record[
                    "human_generalized_input_nm"
                ].tolist(),
                "thigh_table_clearance_mm": 1000.0
                * record["thigh_table_clearance_m"],
                "shank_table_clearance_mm": 1000.0
                * record["shank_table_clearance_m"],
                "bed_force_n": record["bed_force_n"],
            }
        )
        rows.append(row)
    nominal = STAGE5_GEOMETRY.end_effector_from_cuff
    transform_translation_error = []
    transform_rotation_error = []
    for record in plant.grasp_telemetry:
        transform_translation_error.append(
            np.linalg.norm(
                record["flange_from_cuff_translation_m"] - nominal.translation
            )
        )
        transform_rotation_error.append(
            np.linalg.norm(
                _rotation_error_vector(
                    nominal.rotation, record["flange_from_cuff_rotation"]
                )
            )
        )
    return {
        "robot": robot,
        "abort_reason": summary["abort_reason"],
        "task_status": summary["task_status"],
        "samples": rows,
        "contact": _contact_summary(plant),
        "flange_from_cuff_contract": {
            "translation_m": nominal.translation.tolist(),
            "rotation": nominal.rotation.tolist(),
            "maximum_translation_residual_m": float(max(transform_translation_error)),
            "maximum_rotation_residual_rad": float(max(transform_rotation_error)),
        },
    }


def _prescribed_metrics(
    robot: str, summary: dict[str, Any], trace: dict[str, np.ndarray], plant: Any
) -> dict[str, Any]:
    control_time = np.asarray(trace["control_time_s"], dtype=float)
    times = control_time[control_time >= MOTION_START_S - 1.0e-12]
    rows = [
        _pose_tracking_row(_record_at(plant, float(time)), _prescribed_target(float(time)))
        for time in times
    ]
    position = np.asarray([row["position_error_norm_mm"] for row in rows])
    orientation = np.asarray([row["orientation_error_norm_deg"] for row in rows])
    linear_velocity = np.asarray(
        [row["linear_velocity_error_norm_mm_s"] for row in rows]
    )
    angular_velocity = np.asarray(
        [row["angular_velocity_error_norm_deg_s"] for row in rows]
    )
    control_mask = control_time >= MOTION_START_S - 1.0e-12
    sample_rows = []
    for time in (1.0, 1.05, 1.1, 1.2, 1.3, 1.35):
        if time > times[-1] + 1.0e-12:
            continue
        record = _record_at(plant, time)
        row = _pose_tracking_row(record, _prescribed_target(time))
        row.update(
            {
                "human_q_deg": np.degrees(record["human_q_rad"]).tolist(),
                "human_dq_deg_s": np.degrees(record["human_dq_rad_s"]).tolist(),
                "robot_q_deg": np.degrees(record["robot_q_rad"]).tolist(),
                "cuff_jacobian_condition": record["cuff_jacobian_condition"],
                "cuff_wrench_world": record["cuff_wrench_world"].tolist(),
                "human_generalized_input_nm": record[
                    "human_generalized_input_nm"
                ].tolist(),
                "thigh_table_clearance_mm": 1000.0
                * record["thigh_table_clearance_m"],
                "shank_table_clearance_mm": 1000.0
                * record["shank_table_clearance_m"],
                "bed_force_n": record["bed_force_n"],
            }
        )
        sample_rows.append(row)
    return {
        "robot": robot,
        "reference": "existing_stage4_teaching_reference_first_1p35s",
        "motion_window_s": [MOTION_START_S, REPLAY_DURATION_S],
        "termination_reason": summary["termination_reason"],
        "position_error_mm": {
            "rms": float(np.sqrt(np.mean(position**2))),
            "maximum": float(np.max(position)),
            "end": float(position[-1]),
        },
        "orientation_error_deg": {
            "rms": float(np.sqrt(np.mean(orientation**2))),
            "maximum": float(np.max(orientation)),
            "end": float(orientation[-1]),
        },
        "linear_velocity_error_mm_s": {
            "rms": float(np.sqrt(np.mean(linear_velocity**2))),
            "maximum": float(np.max(linear_velocity)),
        },
        "angular_velocity_error_deg_s": {
            "rms": float(np.sqrt(np.mean(angular_velocity**2))),
            "maximum": float(np.max(angular_velocity)),
        },
        "human_q_end_deg": np.degrees(
            np.asarray(trace["control_true_q_rad_god_view"])[control_mask][-1]
        ).tolist(),
        "human_dq_peak_abs_deg_s": np.degrees(
            np.max(
                np.abs(np.asarray(trace["control_true_dq_rad_s_god_view"])[control_mask]),
                axis=0,
            )
        ).tolist(),
        "contact": _contact_summary(plant),
        "samples": sample_rows,
        "sample_count": len(rows),
    }


def _compare_goal(cr12: dict[str, Any], ur10e: dict[str, Any]) -> dict[str, Any]:
    cr_rows = {round(row["time_s"], 12): row for row in cr12["samples"]}
    ur_rows = {round(row["time_s"], 12): row for row in ur10e["samples"]}
    common = sorted(set(cr_rows) & set(ur_rows))
    rows = []
    for time in common:
        cr = cr_rows[time]
        ur = ur_rows[time]
        desired_position_difference = np.linalg.norm(
            np.asarray(cr["desired_position_world_m"])
            - np.asarray(ur["desired_position_world_m"])
        )
        actual_position_difference = np.linalg.norm(
            np.asarray(cr["actual_position_world_m"])
            - np.asarray(ur["actual_position_world_m"])
        )
        desired_rotation_difference = np.linalg.norm(
            _rotation_error_vector(
                np.asarray(cr["desired_rotation_world"]),
                np.asarray(ur["desired_rotation_world"]),
            )
        )
        actual_rotation_difference = np.linalg.norm(
            _rotation_error_vector(
                np.asarray(cr["actual_rotation_world"]),
                np.asarray(ur["actual_rotation_world"]),
            )
        )
        rows.append(
            {
                "time_s": time,
                "desired_cuff_position_difference_mm": float(
                    1000.0 * desired_position_difference
                ),
                "actual_cuff_position_difference_mm": float(
                    1000.0 * actual_position_difference
                ),
                "desired_cuff_orientation_difference_deg": float(
                    np.degrees(desired_rotation_difference)
                ),
                "actual_cuff_orientation_difference_deg": float(
                    np.degrees(actual_rotation_difference)
                ),
                "cr12_position_error_norm_mm": cr["position_error_norm_mm"],
                "ur10e_position_error_norm_mm": ur["position_error_norm_mm"],
                "cr12_orientation_error_norm_deg": cr[
                    "orientation_error_norm_deg"
                ],
                "ur10e_orientation_error_norm_deg": ur[
                    "orientation_error_norm_deg"
                ],
            }
        )
    return {"sample_comparison": rows}


def _first_crossing(
    time_s: np.ndarray, signal: np.ndarray, reporting_sensitivity: float
) -> dict[str, float] | None:
    indices = np.flatnonzero(signal > reporting_sensitivity)
    if not len(indices):
        return None
    index = int(indices[0])
    return {"time_s": float(time_s[index]), "value": float(signal[index])}


def _matched_goal_divergence(cr12: Any, ur10e: Any) -> dict[str, Any]:
    cr_records = {record["time_s"]: record for record in cr12.grasp_telemetry}
    ur_records = {record["time_s"]: record for record in ur10e.grasp_telemetry}
    times = np.asarray(sorted(set(cr_records) & set(ur_records)), dtype=float)
    actual_position_mm = []
    actual_orientation_deg = []
    human_q_deg = []
    shank_clearance_mm = []
    for time in times:
        cr = cr_records[float(time)]
        ur = ur_records[float(time)]
        actual_position_mm.append(
            1000.0
            * np.linalg.norm(
                cr["cuff_position_world_m"] - ur["cuff_position_world_m"]
            )
        )
        actual_orientation_deg.append(
            np.degrees(
                np.linalg.norm(
                    _rotation_error_vector(
                        cr["cuff_rotation_world"], ur["cuff_rotation_world"]
                    )
                )
            )
        )
        human_q_deg.append(
            np.max(np.abs(np.degrees(cr["human_q_rad"] - ur["human_q_rad"])))
        )
        shank_clearance_mm.append(
            1000.0
            * abs(
                cr["shank_table_clearance_m"] - ur["shank_table_clearance_m"]
            )
        )
    actual_position_mm = np.asarray(actual_position_mm)
    actual_orientation_deg = np.asarray(actual_orientation_deg)
    human_q_deg = np.asarray(human_q_deg)
    shank_clearance_mm = np.asarray(shank_clearance_mm)

    target_times = np.asarray(
        sorted(set(cr12.goal_targets) & set(ur10e.goal_targets)), dtype=float
    )
    target_position_mm = []
    target_orientation_deg = []
    for time in target_times:
        cr = cr12.goal_targets[float(time)]
        ur = ur10e.goal_targets[float(time)]
        target_position_mm.append(
            1000.0 * np.linalg.norm(cr["position_m"] - ur["position_m"])
        )
        target_orientation_deg.append(
            np.degrees(
                np.linalg.norm(
                    _rotation_error_vector(cr["rotation"], ur["rotation"])
                )
            )
        )
    target_position_mm = np.asarray(target_position_mm)
    target_orientation_deg = np.asarray(target_orientation_deg)
    return {
        "reporting_sensitivities_not_safety_thresholds": {
            "position_mm": 0.05,
            "orientation_deg": 0.05,
            "human_q_deg": 0.01,
            "shank_clearance_difference_mm": 0.1,
        },
        "first_actual_cuff_position_divergence": _first_crossing(
            times, actual_position_mm, 0.05
        ),
        "first_actual_cuff_orientation_divergence": _first_crossing(
            times, actual_orientation_deg, 0.05
        ),
        "first_human_q_divergence": _first_crossing(times, human_q_deg, 0.01),
        "first_shank_clearance_divergence": _first_crossing(
            times, shank_clearance_mm, 0.1
        ),
        "first_requested_cuff_position_divergence": _first_crossing(
            target_times, target_position_mm, 0.05
        ),
        "first_requested_cuff_orientation_divergence": _first_crossing(
            target_times, target_orientation_deg, 0.05
        ),
    }


def _compare_prescribed_replay(
    cr12_result: dict[str, Any],
    ur10e_result: dict[str, Any],
    cr12: Any,
    ur10e: Any,
) -> dict[str, Any]:
    cr_records = {record["time_s"]: record for record in cr12.grasp_telemetry}
    ur_records = {record["time_s"]: record for record in ur10e.grasp_telemetry}
    times = np.asarray(
        [
            time
            for time in sorted(set(cr_records) & set(ur_records))
            if MOTION_START_S <= time <= REPLAY_DURATION_S + 1.0e-12
        ],
        dtype=float,
    )
    actual_position_difference_mm = np.asarray(
        [
            1000.0
            * np.linalg.norm(
                cr_records[float(time)]["cuff_position_world_m"]
                - ur_records[float(time)]["cuff_position_world_m"]
            )
            for time in times
        ]
    )
    return {
        "same_registered_reference_function": True,
        "maximum_requested_position_difference_m": 0.0,
        "maximum_requested_orientation_difference_rad": 0.0,
        "maximum_actual_cuff_position_difference_mm": float(
            np.max(actual_position_difference_mm)
        ),
        "cr12_position_error_rms_mm": cr12_result["position_error_mm"]["rms"],
        "ur10e_position_error_rms_mm": ur10e_result["position_error_mm"]["rms"],
        "cr12_orientation_error_rms_deg": cr12_result["orientation_error_deg"][
            "rms"
        ],
        "ur10e_orientation_error_rms_deg": ur10e_result["orientation_error_deg"][
            "rms"
        ],
        "cr12_linear_velocity_error_rms_mm_s": cr12_result[
            "linear_velocity_error_mm_s"
        ]["rms"],
        "ur10e_linear_velocity_error_rms_mm_s": ur10e_result[
            "linear_velocity_error_mm_s"
        ]["rms"],
        "cr12_shank_contact": "shank_geom"
        in cr12_result["contact"]["first_contact_by_human_geom"],
        "ur10e_shank_contact": "shank_geom"
        in ur10e_result["contact"]["first_contact_by_human_geom"],
    }


def _save_telemetry(path: Path, plant: Any) -> None:
    records = plant.grasp_telemetry
    np.savez_compressed(
        path,
        time_s=np.asarray([record["time_s"] for record in records]),
        human_q_rad=np.asarray([record["human_q_rad"] for record in records]),
        human_dq_rad_s=np.asarray([record["human_dq_rad_s"] for record in records]),
        robot_q_rad=np.asarray([record["robot_q_rad"] for record in records]),
        robot_dq_rad_s=np.asarray([record["robot_dq_rad_s"] for record in records]),
        cuff_position_world_m=np.asarray(
            [record["cuff_position_world_m"] for record in records]
        ),
        cuff_rotation_world=np.asarray(
            [record["cuff_rotation_world"] for record in records]
        ),
        cuff_linear_velocity_world_m_s=np.asarray(
            [record["cuff_linear_velocity_world_m_s"] for record in records]
        ),
        cuff_angular_velocity_world_rad_s=np.asarray(
            [record["cuff_angular_velocity_world_rad_s"] for record in records]
        ),
        cuff_jacobian_singular_values=np.asarray(
            [record["cuff_jacobian_singular_values"] for record in records]
        ),
        cuff_jacobian_condition=np.asarray(
            [record["cuff_jacobian_condition"] for record in records]
        ),
        cuff_wrench_world=np.asarray(
            [record["cuff_wrench_world"] for record in records]
        ),
        human_generalized_input_nm=np.asarray(
            [record["human_generalized_input_nm"] for record in records]
        ),
        thigh_table_clearance_m=np.asarray(
            [record["thigh_table_clearance_m"] for record in records]
        ),
        shank_table_clearance_m=np.asarray(
            [record["shank_table_clearance_m"] for record in records]
        ),
        bed_force_n=np.asarray([record["bed_force_n"] for record in records]),
    )


def _save_goal_targets(path: Path, plant: Any) -> None:
    times = np.asarray(sorted(plant.goal_targets), dtype=float)
    targets = [plant.goal_targets[float(time)] for time in times]
    np.savez_compressed(
        path,
        time_s=times,
        position_world_m=np.asarray([target["position_m"] for target in targets]),
        rotation_world=np.asarray([target["rotation"] for target in targets]),
        linear_velocity_world_m_s=np.asarray(
            [target["linear_velocity_m_s"] for target in targets]
        ),
        angular_velocity_world_rad_s=np.asarray(
            [target["angular_velocity_rad_s"] for target in targets]
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results/cr12_grasp_execution_diagnostic_attempt_01",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    goal_results = {}
    goal_plants = {}
    prescribed_results = {}
    prescribed_plants = {}
    for robot in ("cr12", "ur10e"):
        summary, plant = _goal_run(robot, output / f"goal_{robot}")
        goal_results[robot] = _goal_metrics(robot, summary, plant)
        goal_plants[robot] = plant
        _save_telemetry(output / f"goal_{robot}_telemetry.npz", plant)
        _save_goal_targets(output / f"goal_{robot}_targets.npz", plant)

        prescribed_summary, prescribed_trace, prescribed_plant = _prescribed_run(robot)
        prescribed_results[robot] = _prescribed_metrics(
            robot, prescribed_summary, prescribed_trace, prescribed_plant
        )
        prescribed_plants[robot] = prescribed_plant
        _save_telemetry(
            output / f"prescribed_{robot}_telemetry.npz", prescribed_plant
        )

    result = {
        "schema": "stage5_cr12_grasp_execution_diagnostic_v1",
        "evidence_category": "focused_engineering_diagnostic",
        "goal_mpc_early_window": goal_results,
        "goal_mpc_matched_comparison": _compare_goal(
            goal_results["cr12"], goal_results["ur10e"]
        ),
        "goal_mpc_divergence_timeline": _matched_goal_divergence(
            goal_plants["cr12"], goal_plants["ur10e"]
        ),
        "prescribed_cuff_space_replay": prescribed_results,
        "prescribed_cuff_space_replay_comparison": _compare_prescribed_replay(
            prescribed_results["cr12"],
            prescribed_results["ur10e"],
            prescribed_plants["cr12"],
            prescribed_plants["ur10e"],
        ),
        "shared_flange_from_cuff_semantics": {
            "convention": "T_EC maps cuff coordinates C into terminal flange E",
            "translation_m": STAGE5_GEOMETRY.end_effector_from_cuff.translation.tolist(),
            "rotation": STAGE5_GEOMETRY.end_effector_from_cuff.rotation.tolist(),
            "provisional": True,
            "same_for_cr12_and_ur10e": True,
        },
        "controller_parameter_changed": False,
        "task_geometry_changed": False,
        "threshold_changed": False,
        "contact_model_changed": False,
        "rl_or_value_work": False,
    }
    (output / "grasp_execution_diagnostic.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
