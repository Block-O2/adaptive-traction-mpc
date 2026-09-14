"""Deterministic Stage-5 IK branch selection for the above-table posture."""

from __future__ import annotations

import numpy as np

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.ik import _solve_candidates
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .config import STAGE5_CONFIG


STAGE5_IK_REFERENCE_SEED_RAD = np.radians(
    np.asarray(STAGE5_CONFIG["geometry"]["ik_reference_seed_deg"], dtype=float)
)


def solve_stage5_ik(
    robot: UR10eTorqueRobot,
    target: RigidTransform,
    *,
    previous_q_rad: np.ndarray | None = None,
) -> np.ndarray:
    """Solve on the registered above-table branch, then preserve continuity."""

    reference = (
        STAGE5_IK_REFERENCE_SEED_RAD
        if previous_q_rad is None
        else np.asarray(previous_q_rad, dtype=float)
    )
    seeds = [reference]
    candidates = _solve_candidates(
        robot,
        target,
        seeds,
        periodic_reference=reference,
    )
    exact = [candidate for error, candidate in candidates if error < 1.0e-8]
    if not exact:
        best_error = min(error for error, _ in candidates)
        raise RuntimeError(f"Stage-5 continuous IK failed: residual={best_error:.6g}")
    return min(exact, key=lambda candidate: np.linalg.norm(candidate - reference)).copy()
