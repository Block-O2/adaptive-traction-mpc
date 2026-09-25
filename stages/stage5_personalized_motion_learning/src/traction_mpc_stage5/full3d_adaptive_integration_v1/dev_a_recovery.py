"""DEV-A physical recovery reference primitives; no model-update-law changes.

The initial robot-cuff pose bridge is an execution reference transition between
two already computed loaded models.  It never changes the geometry fit, beta,
residual estimate, physical plant, or hidden-case inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.reference import CuffPoseReference, quintic_progress

from ..human_waypoint_shadow import HumanWaypointCandidate, MappedHumanWaypoint
from ..loaded_execution import with_explicit_robot_target


@dataclass(frozen=True)
class RobotCuffPoseBridge:
    """C2 endpoint-continuous old-to-new loaded robot target over one segment."""

    old_world_from_cuff: RigidTransform
    new_world_from_cuff: RigidTransform
    duration_s: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.duration_s) or self.duration_s <= 0.0:
            raise ValueError("pose bridge duration must be positive")

    def sample(self, elapsed_s: float) -> tuple[RigidTransform, np.ndarray, np.ndarray]:
        fraction, first, _ = quintic_progress(float(elapsed_s) / self.duration_s)
        speed = first / self.duration_s
        old = self.old_world_from_cuff
        new = self.new_world_from_cuff
        displacement = new.translation - old.translation
        relative_rotation = Rotation.from_matrix(old.rotation.T @ new.rotation).as_rotvec()
        rotation = old.rotation @ Rotation.from_rotvec(fraction * relative_rotation).as_matrix()
        return (
            RigidTransform(rotation, old.translation + fraction * displacement),
            speed * displacement,
            speed * (old.rotation @ relative_rotation),
        )

    def endpoint_jumps(self) -> dict[str, float]:
        pose0, linear0, angular0 = self.sample(0.0)
        pose1, linear1, angular1 = self.sample(self.duration_s)
        return {
            "start_position_m": float(np.linalg.norm(pose0.translation - self.old_world_from_cuff.translation)),
            "end_position_m": float(np.linalg.norm(pose1.translation - self.new_world_from_cuff.translation)),
            "start_rotation_rad": float(np.linalg.norm(Rotation.from_matrix(
                self.old_world_from_cuff.rotation.T @ pose0.rotation).as_rotvec())),
            "end_rotation_rad": float(np.linalg.norm(Rotation.from_matrix(
                self.new_world_from_cuff.rotation.T @ pose1.rotation).as_rotvec())),
            "start_twist_norm": float(np.linalg.norm(np.r_[linear0, angular0])),
            "end_twist_norm": float(np.linalg.norm(np.r_[linear1, angular1])),
        }


def mapped_with_bridge(
    mapped: MappedHumanWaypoint,
    candidate: HumanWaypointCandidate,
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    ddq_rad_s2: np.ndarray,
    bridge: RobotCuffPoseBridge,
    elapsed_s: float,
) -> MappedHumanWaypoint:
    """Override only the robot execution pose/twist, preserving Human dynamics."""

    if mapped.candidate is not candidate:
        raise ValueError("recovery bridge candidate must match mapped waypoint")
    pose, linear, angular = bridge.sample(elapsed_s)
    reference = CuffPoseReference(
        q_rad=np.asarray(q_rad, dtype=float).copy(),
        dq_rad_s=np.asarray(dq_rad_s, dtype=float).copy(),
        ddq_rad_s2=np.asarray(ddq_rad_s2, dtype=float).copy(),
        world_from_cuff=pose,
    )
    target = with_explicit_robot_target(
        mapped.execution_target,
        reference,
        linear_velocity_world_m_s=linear,
        angular_velocity_world_rad_s=angular,
    )
    return replace(mapped, reference=reference, execution_target=target)
