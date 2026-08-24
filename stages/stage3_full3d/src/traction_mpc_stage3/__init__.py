"""Independent Stage-3 full-3D robot execution plant."""

from .frames import ATTACHMENT_FROM_CUFF, WORLD_FROM_BASE, RigidTransform
from .reference import CuffPoseReference, stage2_cuff_pose_reference
from .robot import UR10eTorqueRobot

__all__ = [
    "ATTACHMENT_FROM_CUFF",
    "WORLD_FROM_BASE",
    "CuffPoseReference",
    "RigidTransform",
    "UR10eTorqueRobot",
    "stage2_cuff_pose_reference",
]
