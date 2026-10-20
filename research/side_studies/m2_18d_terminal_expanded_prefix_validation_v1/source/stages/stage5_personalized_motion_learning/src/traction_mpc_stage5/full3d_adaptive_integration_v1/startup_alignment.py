"""Explicit causal robot execution-pose offsets, without geometry estimation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform
from ..geometry import STAGE5_GEOMETRY
from ..loaded_execution import with_explicit_robot_target
from .handoff_reference import cartesian_tool_margins


def validate_recovery_options(options: dict[str, Any]) -> None:
    for name in ("startup_execution_pose_alignment", "reference_pacing", "whole_session_wall_physics", "exact_cached_plant", "causal_return_projection", "causal_terminal_commit", "commissioning_cuff_reference_origin", "causal_tracking_offset_clearance", "incremental_window_wrench_baseline", "causal_dwell_projection"):
        if name in options and not isinstance(options[name], bool):
            raise ValueError(f"{name} must be boolean")
    if options.get("causal_return_projection", False) and not options.get("whole_session_wall_physics", False):
        raise ValueError("causal return projection requires whole-session wall physics")
    if options.get('causal_dwell_projection',False) and not (
            options.get('whole_session_wall_physics',False) and options.get('robust_hold_reference',False)):
        raise ValueError('causal dwell projection requires actual samples and bounded continuous HOLD')
    if options.get("causal_terminal_commit", False) and not options.get("causal_return_projection", False):
        raise ValueError("causal terminal commit requires capture-anchored return projection")
    if options.get("causal_tracking_offset_clearance", False) and not (
            options.get("terminal_set_reference", False) and options.get("whole_session_wall_physics", False)):
        raise ValueError("tracking-offset clearance requires terminal-set planner and actual wall receipts")
    if options.get("incremental_window_wrench_baseline", False) and not (
            options.get("whole_session_wall_physics", False) and
            (options.get("incremental_clearance_response", False) or 'incremental_acceleration_fraction' in options)):
        raise ValueError('window wrench baseline requires actual wall receipts and incremental response')
    for name, default in (("reference_velocity_fraction", .6), ("reference_acceleration_fraction", .5), ("requested_acceleration_fraction", 1.0), ("combined_acceleration_fraction", 1.0), ("incremental_acceleration_fraction", 1.0)):
        value = options.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"{name} must be finite and in (0,1]")


def tool_increment_certificate(old: RigidTransform, new: RigidTransform, count: int = 33) -> dict[str, Any]:
    """Check the actual shifted command poses and their rigid interpolation.

    Endpoint poses are actual command targets. The interpolation is an extra
    hypothetical geometric screen, not the executed ZOH command signal or a
    future compliant physical tracking certificate. The registered Human reference envelope remains independently
    enforced, and every actual interval retains the ordinary supervisor.
    """
    u = np.linspace(0., 1., count)
    rotvec = Rotation.from_matrix(old.rotation.T@new.rotation).as_rotvec()
    rotations = old.rotation@Rotation.from_rotvec(u[:,None]*rotvec).as_matrix()
    positions = old.translation+u[:,None]*(new.translation-old.translation)
    minimum = {k: float(np.min(v)) for k,v in cartesian_tool_margins(positions,rotations).items()}
    geom = STAGE5_GEOMETRY
    radii = {"robot_cuff_bar_m": geom.cuff_bar_length_m/2+geom.cuff_bar_radius_m,
             "robot_cuff_adapter_m": np.linalg.norm(geom.end_effector_from_cuff.translation)+.018}
    lower = {k: value-(abs(new.translation[2]-old.translation[2])+radii[k]*np.linalg.norm(rotvec))/(2*(count-1))
             for k,value in minimum.items()}
    return {"feasible": min(lower.values()) >= 0., "minimum_sampled_m": minimum,
            "continuous_increment_lower_m": lower, "sample_count": count,
            "scope": "actual transformed command endpoint poses; additional hypothetical rigid interpolation, not the executed reference signal"}


@dataclass(frozen=True)
class StartupExecutionPoseAlignment:
    translation_world_m: np.ndarray
    left_rotation_world: np.ndarray
    source_sample_time_s: float

    @classmethod
    def from_measurement(cls, measurement: Any, nominal_robot_pose: RigidTransform):
        p = np.asarray(measurement.attachment_position_m, dtype=float)
        r = np.asarray(measurement.attachment_rotation_matrix, dtype=float)
        if p.shape != (3,) or r.shape != (3,3) or not np.all(np.isfinite(p)) or not np.all(np.isfinite(r)):
            raise ValueError("startup alignment requires a finite measured robot pose")
        if not np.allclose(r.T@r,np.eye(3),rtol=0,atol=1e-8) or np.linalg.det(r) <= 0:
            raise ValueError("startup alignment requires a proper measured robot rotation")
        return cls(p-nominal_robot_pose.translation, r@nominal_robot_pose.rotation.T,
                   float(measurement.sample_time_s))

    def pose(self, nominal: RigidTransform) -> RigidTransform:
        # Preserve world translation increments exactly. This is an explicit
        # pose offset, not a claim that the Human kinematic frame was identified.
        return RigidTransform(self.left_rotation_world@nominal.rotation,
                              nominal.translation+self.translation_world_m)

    def apply(self, mapped: Any) -> Any:
        robot = mapped.execution_target.robot_cuff_target
        reference = replace(mapped.reference, world_from_cuff=self.pose(robot.world_from_cuff))
        target = with_explicit_robot_target(mapped.execution_target, reference,
            linear_velocity_world_m_s=robot.linear_velocity_world_m_s,
            angular_velocity_world_rad_s=self.left_rotation_world@robot.angular_velocity_world_rad_s)
        return replace(mapped, reference=reference, execution_target=target)

    def record(self) -> dict[str, Any]:
        return {"source": "initial measured robot attachment minus population support target",
                "source_sample_time_s": self.source_sample_time_s,
                "translation_world_m": self.translation_world_m.copy(),
                "left_rotation_world": self.left_rotation_world.copy(),
                "nominal_human_geometry_changed": False,
                "individual_geometry_identified": False}


def align_active_startup_reference(runtime: dict[str, Any], mapped: Any, sample_time_s: float) -> Any:
    """Align every old-model support command while the explicit offset is active.

    Context names do not disable alignment: old support during recovery wait
    must retain its offset. Runtime deactivates it when the actual emitted-pose
    bridge activates, so a mapped bridge is never shifted twice.
    """
    if not runtime.get("startup_alignment_active", False):
        return mapped
    shifted = runtime["startup_alignment"].apply(mapped)
    pose = shifted.execution_target.robot_cuff_target.world_from_cuff
    check = tool_increment_certificate(runtime["last_aligned_robot_reference"],pose)
    runtime["startup_alignment_geometry_checks"].append({"sample_time_s":float(sample_time_s),**check})
    if not check["feasible"]:
        runtime["execution_failure"] = {"reason":"ALIGNED_ROBOT_TOOL_GEOMETRY_REJECTED","certificate":check}
        raise RuntimeError("ALIGNED_ROBOT_TOOL_GEOMETRY_REJECTED")
    return shifted
