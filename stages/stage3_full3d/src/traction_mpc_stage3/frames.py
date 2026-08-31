"""Explicit Stage-3 frame chain.

Transform names use ``PARENT_FROM_CHILD``: a point expressed in CHILD is mapped
into PARENT by ``p_parent = R_parent_child @ p_child + t_parent_child``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cuff_adapter import CUFF_ADAPTER


@dataclass(frozen=True)
class RigidTransform:
    rotation: np.ndarray
    translation: np.ndarray

    def __post_init__(self) -> None:
        rotation = np.asarray(self.rotation, dtype=float)
        translation = np.asarray(self.translation, dtype=float)
        if rotation.shape != (3, 3) or translation.shape != (3,):
            raise ValueError("RigidTransform requires a 3x3 rotation and 3-vector")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12):
            raise ValueError("rotation must be orthonormal")
        if np.linalg.det(rotation) < 0.0:
            raise ValueError("rotation must be right-handed")
        object.__setattr__(self, "rotation", rotation.copy())
        object.__setattr__(self, "translation", translation.copy())

    @classmethod
    def identity(cls) -> "RigidTransform":
        return cls(np.eye(3), np.zeros(3))

    def inverse(self) -> "RigidTransform":
        rotation = self.rotation.T
        return RigidTransform(rotation, -rotation @ self.translation)

    def compose(self, child_from_descendant: "RigidTransform") -> "RigidTransform":
        return RigidTransform(
            self.rotation @ child_from_descendant.rotation,
            self.rotation @ child_from_descendant.translation + self.translation,
        )


# Initial placement retained from the surrogate-selection audit. The UR10e base
# axes are aligned with the existing Stage-2 world axes; only translation differs.
WORLD_FROM_BASE = RigidTransform(
    np.eye(3),
    np.array([1.10, -0.62, 0.04], dtype=float),
)

# Parameterized simulation-only side standoff.  Positive attachment-frame Y
# places the robot attachment site on the negative world-Y side of the planar
# cuff.  The dimensions are derived in ``cuff_adapter.py`` from committed
# wrist/cuff/shank collision geometry; this is not CR12 hardware calibration.
ATTACHMENT_FROM_CUFF = RigidTransform(
    np.eye(3),
    np.array([0.0, CUFF_ADAPTER.cuff_center_standoff_m, 0.0]),
)


def base_from_attachment_target(
    world_from_cuff: RigidTransform,
    *,
    world_from_base: RigidTransform = WORLD_FROM_BASE,
    attachment_from_cuff: RigidTransform = ATTACHMENT_FROM_CUFF,
) -> RigidTransform:
    """Return the desired UR10e attachment pose in the model base frame."""

    world_from_attachment = world_from_cuff.compose(attachment_from_cuff.inverse())
    return world_from_base.inverse().compose(world_from_attachment)
