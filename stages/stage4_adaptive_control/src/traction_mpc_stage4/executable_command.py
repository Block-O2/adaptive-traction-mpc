"""Stage-4 adapter for the shared Stage-3 executable-command contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import ExecutableCommandPreview
from traction_mpc_stage3.reference import CuffPoseReference


@dataclass(frozen=True)
class Stage4ExecutableCommandPreview:
    allocation: dict[str, Any]
    command: ExecutableCommandPreview


def preview_stage4_executable_command(
    *,
    plant: Any,
    measurement: Any,
    action_nm: np.ndarray,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> Stage4ExecutableCommandPreview:
    """Allocate the action once, then preview the exact executable command."""

    state = np.asarray(estimated_state, dtype=float)
    if state.shape != (4,) or not np.all(np.isfinite(state)):
        raise ValueError("estimated_state must be a finite four-vector")
    allocation = cuff_allocator.allocate(action_nm, state[:2], human_model)
    target_pose = human_model.geometry.cuff_pose(reference.q_rad)
    target_linear_velocity, target_angular_velocity = (
        human_model.geometry.cuff_velocity(reference.q_rad, reference.dq_rad_s)
    )
    command = plant.preview_measured_executable_command(
        measurement,
        target_pose.translation,
        target_linear_velocity,
        target_pose.rotation,
        target_angular_velocity,
        np.asarray(allocation["wrench_world"]),
    )
    return Stage4ExecutableCommandPreview(allocation=allocation, command=command)
