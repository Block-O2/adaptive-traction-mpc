"""Limited no-learning Stage-5 replay through the inherited MPC/safety stack."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage3.spring_damper_interface import InterfaceParameters
from traction_mpc_stage4 import sensor_realism
from traction_mpc_stage4.estimator_v2 import (
    OneShotHumanEstimatorV2,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.measurement import MeasurementCase
from traction_mpc_stage4.reference import (
    COLD_START_TEACHING_WAYPOINTS,
    TEACHING_WAYPOINTS,
    cold_start_teaching_reference,
    teaching_reference,
)
from traction_mpc_stage4.sensor_realism import (
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
    RobotControlVelocitySnapshot,
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor

from .config import STAGE5_ROOT
from .geometry import STAGE5_GEOMETRY
from .human import STAGE5_HUMAN
from .mechanics import NOMINAL_PHYSICS_DT_S, STAGE5_RIGID_INTERFACE
from .plant import Stage5SpringDamperPlant


class FixedStage5Estimator(OneShotHumanEstimatorV2):
    """Exact registered Stage-5 geometry/dynamics with all updates disabled."""

    def __init__(
        self,
        initial_position_world_m: np.ndarray,
        initial_rotation_world_from_cuff: np.ndarray,
        initial_q_prior_rad: np.ndarray,
    ) -> None:
        super().__init__(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            initial_q_prior_rad,
        )
        rotation = STAGE5_GEOMETRY.world_from_human.rotation
        geometry = PlanarCuffGeometry(
            origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
            plane_x_world=rotation[:, 0].copy(),
            joint_axis_world=rotation[:, 1].copy(),
            plane_z_world=rotation[:, 2].copy(),
            hip_plane_m=np.zeros(2),
            thigh_length_m=STAGE5_HUMAN.thigh_length_m,
            knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
        )
        geometry_vector = np.array(
            [0.0, 0.0, STAGE5_HUMAN.thigh_length_m, STAGE5_HUMAN.sleeve_center_m, 0.0]
        )
        self.geometry_identifier.geometry = geometry
        self.geometry_identifier.prior = geometry_vector.copy()
        self.geometry_identifier.last_valid = geometry_vector.copy()
        self.geometry_identifier.last_diagnostics = self.geometry_identifier._empty_diagnostics(
            "fixed_stage5_registered_geometry_no_learning"
        )
        self.dynamic_identifier.last_valid = nominal_base_parameters(STAGE5_HUMAN)
        self.dynamic_identifier.last_diagnostics = self.dynamic_identifier._empty_diagnostics(
            "fixed_stage5_registered_dynamics_no_learning"
        )
        self.last_state = geometry.estimate_state(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            np.zeros(3),
            np.zeros(3),
        )

    def observe(self, **measurement: Any) -> tuple[np.ndarray, dict[str, Any]]:
        self.last_state = self.geometry.estimate_state(
            measurement["position_world_m"],
            measurement["rotation_world_from_cuff"],
            measurement["linear_velocity_world_m_s"],
            measurement["angular_velocity_world_rad_s"],
        )
        return self.last_state.copy(), {
            "geometry": self.geometry_identifier._empty_diagnostics(
                "fixed_stage5_registered_geometry_no_learning"
            ),
            "dynamics": self.dynamic_identifier._empty_diagnostics(
                "fixed_stage5_registered_dynamics_no_learning"
            ),
            "bed_contaminated": False,
            "soft_limit_contaminated": False,
        }


class Stage5SensorBoundaryPlant(Stage5SpringDamperPlant):
    """Stage-5 plant exposing the unchanged Stage-4 measured-control API."""

    robot_joint_control_velocity_snapshot = (
        SensorBoundaryStage4Plant.robot_joint_control_velocity_snapshot
    )
    control_feedback_velocity_snapshot = (
        SensorBoundaryStage4Plant.control_feedback_velocity_snapshot
    )
    apply_measured_nominal_cartesian_control = (
        SensorBoundaryStage4Plant.apply_measured_nominal_cartesian_control
    )
    preview_measured_executable_command = (
        SensorBoundaryStage4Plant.preview_measured_executable_command
    )

    def __init__(
        self,
        human: Any,
        *,
        interface_parameters: InterfaceParameters = STAGE5_RIGID_INTERFACE,
    ) -> None:
        self.interface_history: list[dict[str, Any]] = []
        super().__init__(
            interface_parameters,
            human,
            physics_dt_s=NOMINAL_PHYSICS_DT_S,
        )
        self.translational_velocity_feedback_source = (
            ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        )
        self._measured_robot_model = UR10eTorqueRobot()
        self._control_velocity_robot_model = UR10eTorqueRobot()
        self.last_robot_control_velocity_snapshot: RobotControlVelocitySnapshot | None = None

    def observe(self):
        observation = super().observe()
        interface = self._evaluate_current_interface()
        record = {
            "time_s": observation.time_s,
            "translation_m": interface.displacement_human_m.copy(),
            "rotation_rad": interface.rotation_error_human_rad.copy(),
        }
        if self.interface_history and abs(self.interface_history[-1]["time_s"] - observation.time_s) < 1.0e-12:
            self.interface_history[-1] = record
        else:
            self.interface_history.append(record)
        return observation


def _stage5_reference(source: Callable[[float], CuffPoseReference]) -> Callable[[float], CuffPoseReference]:
    def reference(time_s: float) -> CuffPoseReference:
        donor = source(time_s)
        return CuffPoseReference(
            donor.q_rad.copy(),
            donor.dq_rad_s.copy(),
            donor.ddq_rad_s2.copy(),
            STAGE5_GEOMETRY.world_from_cuff(donor.q_rad, STAGE5_HUMAN),
        )

    return reference


def _fixed_estimator(measurement: Any, initial_q: np.ndarray) -> FixedStage5Estimator:
    return FixedStage5Estimator(
        measurement.attachment_position_m,
        measurement.attachment_rotation_matrix,
        initial_q,
    )


def _case_metrics(
    name: str,
    requested_duration_s: float,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    plant: Stage5SensorBoundaryPlant,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    force = np.linalg.norm(trace["cuff_force_local_n_god_view"], axis=1)
    moment = np.linalg.norm(trace["cuff_moment_local_nm_god_view"], axis=1)
    force_rate = np.zeros_like(force)
    if len(time) > 1:
        force_rate[1:] = np.linalg.norm(
            np.diff(trace["cuff_force_local_n_god_view"], axis=0), axis=1
        ) / np.diff(time)
    interface_time = np.array([item["time_s"] for item in plant.interface_history])
    interface_translation = np.array([item["translation_m"] for item in plant.interface_history])
    interface_rotation = np.array([item["rotation_rad"] for item in plant.interface_history])
    filter_status = trace.get("safety_filter_status", np.array([], dtype=str))
    return {
        "name": name,
        "requested_duration_s": requested_duration_s,
        "completed_duration_s": float(time[-1]),
        "progress_fraction": float(min(time[-1] / requested_duration_s, 1.0)),
        "termination_reason": summary["termination_reason"],
        "mechanically_completed_requested_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "tracking_rmse_deg": summary["tracking"]["rmse_deg"],
        "tracking_combined_rmse_deg": summary["tracking"]["combined_rmse_deg"],
        "cumulative_force_integral_n_s": float(np.trapezoid(force, time)),
        "peak_force_n": float(np.max(force)),
        "rms_force_n": float(np.sqrt(np.mean(force**2))),
        "peak_force_slew_n_s": float(np.max(force_rate)),
        "peak_moment_nm": float(np.max(moment)),
        "peak_interface_translation_deformation_mm": float(
            1000.0 * np.max(np.linalg.norm(interface_translation, axis=1))
        ),
        "peak_interface_rotation_deformation_deg": float(
            np.degrees(np.max(np.linalg.norm(interface_rotation, axis=1)))
        ),
        "safety_filter_status_counts": dict(Counter(map(str, filter_status))),
        "track_brake_supervisor": summary.get("track_brake_supervisor", {}),
        "force_gate_event_count": summary["events"]["force_gate_events"],
        "mujoco_warning_counts": plant.warning_counts(),
        "interface_trace_sample_count": len(interface_time),
    }


def _run_case(spec: dict[str, Any], output_dir: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    holder: dict[str, Stage5SensorBoundaryPlant] = {}

    def factory(human: Any) -> Stage5SensorBoundaryPlant:
        plant = Stage5SensorBoundaryPlant(human)
        holder["plant"] = plant
        return plant

    control_substeps = int(round(sensor_realism.CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    if control_substeps * NOMINAL_PHYSICS_DT_S != sensor_realism.CONTROL_DT_S:
        raise RuntimeError("Stage-5 timestep does not divide the inherited control period")
    ideal = MeasurementCase(name="stage5_ideal_200hz", update_rate_hz=200.0, latency_s=0.0)
    with patch.object(sensor_realism, "CONTROL_SUBSTEPS", control_substeps):
        summary, trace = run_sensor_realism_case(
            ideal,
            duration_s=spec["duration_s"],
            estimator_architecture="instantaneous_v2",
            result_case_name=spec["name"],
            true_human_override=STAGE5_HUMAN,
            true_metadata_override={
                "case": "stage5_registered_human_fixed_no_learning",
                "cuff_fraction_of_shank": STAGE5_HUMAN.cuff_fraction_of_shank,
            },
            reference_fn=_stage5_reference(spec["reference_fn"]),
            trajectory_label=spec["trajectory_label"],
            trajectory_waypoints=spec["waypoints"],
            plant_factory=factory,
            track_brake_supervisor=TrackBrakeSupervisor(),
            estimator_factory=_fixed_estimator,
            capture_system_pilot_diagnostics=True,
        )
    plant = holder["plant"]
    metrics = _case_metrics(spec["name"], spec["duration_s"], summary, trace, plant)
    summary["stage5_limited_replay_metrics"] = metrics
    summary["stage5_execution_contract"] = {
        "plant": "Stage-5 Plant v1",
        "physics_dt_s": NOMINAL_PHYSICS_DT_S,
        "control_dt_s": sensor_realism.CONTROL_DT_S,
        "control_substeps_runtime_override": control_substeps,
        "prescribed_reference": True,
        "existing_model_based_mpc_cem": True,
        "existing_safety_filter_and_brake": True,
        "fixed_registered_model": True,
        "online_identification_or_learning": False,
        "controller_or_trajectory_tuning": False,
    }
    interface_trace = {
        "interface_time_s": np.array([item["time_s"] for item in plant.interface_history]),
        "interface_translation_m": np.array([item["translation_m"] for item in plant.interface_history]),
        "interface_rotation_rad": np.array([item["rotation_rad"] for item in plant.interface_history]),
    }
    combined_trace = {**trace, **interface_trace}
    (output_dir / f"{spec['name']}.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(output_dir / f"{spec['name']}_trace.npz", **combined_trace)
    return metrics, combined_trace


def run_limited_baseline_replay(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = (
        {
            "name": "low_moderate_cold_start_prefix_6p5s",
            "duration_s": 6.5,
            "reference_fn": cold_start_teaching_reference,
            "trajectory_label": "existing_stage4_cold_start_prefix_to_20deg_35deg",
            "waypoints": tuple(item for item in COLD_START_TEACHING_WAYPOINTS if item.time_s <= 6.5),
        },
        {
            "name": "higher_rom_teaching_prefix_9p5s",
            "duration_s": 9.5,
            "reference_fn": teaching_reference,
            "trajectory_label": "existing_stage4_teaching_prefix_through_38deg_80deg_hold",
            "waypoints": tuple(item for item in TEACHING_WAYPOINTS if item.time_s <= 9.5),
        },
    )
    cases = []
    traces = []
    for spec in specs:
        metrics, trace = _run_case(spec, output_dir)
        cases.append(metrics)
        traces.append((spec["name"], trace))
    report = {
        "schema": "stage5_limited_baseline_replay_v1",
        "evidence_category": "smoke_engineering_sanity_replay_only",
        "formal_stage5_baseline_campaign": False,
        "plant_release": "Stage-5 Plant v1",
        "selected_interface": {
            "translation_stiffness_n_m": list(STAGE5_RIGID_INTERFACE.translation_stiffness_n_m),
            "translation_damping_ns_m": list(STAGE5_RIGID_INTERFACE.translation_damping_ns_m),
            "rotation_stiffness_nm_rad": STAGE5_RIGID_INTERFACE.rotation_stiffness_nm_rad,
            "rotation_damping_nms_rad": STAGE5_RIGID_INTERFACE.rotation_damping_nms_rad,
        },
        "cases": cases,
        "learning_or_rl_run": False,
        "controller_or_trajectory_parameters_changed": False,
    }
    (output_dir / "baseline_replay_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for name, trace in traces:
        force = np.linalg.norm(trace["cuff_force_local_n_god_view"], axis=1)
        ax.plot(trace["time_s"], force, label=name)
    ax.set(
        xlabel="Time (s)",
        ylabel="Physical cuff-force norm (N)",
        title="Selected Stage-5 interface: limited prescribed-trajectory replay",
    )
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "E_baseline_replay_force_vs_time.png", dpi=180)
    plt.close(fig)
    return report
