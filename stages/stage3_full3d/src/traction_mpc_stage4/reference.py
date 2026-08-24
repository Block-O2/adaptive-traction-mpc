"""Independent two-joint teaching reference for Stage 4.

The frozen Stage-3C reference remains in :mod:`traction_mpc_stage3.reference`.
This module only adds the richer Stage-4 trajectory requested for identification.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff, quintic_progress


TEACHING_DURATION_S = 18.0
COLD_START_TEACHING_DURATION_S = 23.0


@dataclass(frozen=True)
class TeachingWaypoint:
    time_s: float
    q_deg: tuple[float, float]
    label: str


TEACHING_WAYPOINTS = (
    TeachingWaypoint(0.0, (5.0, 10.0), "initial_hold"),
    TeachingWaypoint(1.0, (5.0, 10.0), "hip_lift_start"),
    TeachingWaypoint(4.0, (30.0, 25.0), "hip_lift_end"),
    TeachingWaypoint(5.0, (30.0, 25.0), "knee_flexion_start"),
    TeachingWaypoint(8.0, (38.0, 80.0), "knee_flexion_end"),
    TeachingWaypoint(9.5, (38.0, 80.0), "knee_extension_start"),
    TeachingWaypoint(12.0, (45.0, 30.0), "knee_extension_end"),
    TeachingWaypoint(13.0, (45.0, 30.0), "return_start"),
    TeachingWaypoint(17.0, (5.0, 10.0), "return_end"),
    TeachingWaypoint(18.0, (5.0, 10.0), "final_hold"),
)


# The original Stage-4 teaching trajectory above is retained unchanged.  This
# population-prior trajectory makes its early excitation deliberately small,
# then increases it within the same single execution.
COLD_START_TEACHING_WAYPOINTS = (
    TeachingWaypoint(0.0, (5.0, 10.0), "initial_hold"),
    TeachingWaypoint(1.0, (5.0, 10.0), "small_hip_start"),
    TeachingWaypoint(3.5, (18.0, 12.0), "small_hip_end"),
    TeachingWaypoint(4.0, (18.0, 12.0), "small_knee_start"),
    TeachingWaypoint(6.5, (20.0, 35.0), "small_knee_end"),
    TeachingWaypoint(7.0, (20.0, 35.0), "larger_flexion_start"),
    TeachingWaypoint(10.0, (48.0, 60.0), "larger_flexion_end"),
    TeachingWaypoint(13.0, (75.0, 90.0), "high_flexion"),
    TeachingWaypoint(14.5, (75.0, 90.0), "high_flexion_hold_end"),
    TeachingWaypoint(17.0, (50.0, 55.0), "staged_return_1"),
    TeachingWaypoint(19.0, (28.0, 25.0), "staged_return_2"),
    TeachingWaypoint(22.0, (5.0, 10.0), "return"),
    TeachingWaypoint(23.0, (5.0, 10.0), "final_hold"),
)


def _joint_reference(time_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = float(np.clip(time_s, 0.0, TEACHING_DURATION_S))
    for start, end in zip(TEACHING_WAYPOINTS[:-1], TEACHING_WAYPOINTS[1:], strict=True):
        if time <= end.time_s + 1e-12:
            duration = end.time_s - start.time_s
            q0 = np.radians(start.q_deg)
            delta = np.radians(np.asarray(end.q_deg) - np.asarray(start.q_deg))
            if np.allclose(delta, 0.0):
                return q0, np.zeros(2), np.zeros(2)
            progress, velocity, acceleration = quintic_progress((time - start.time_s) / duration)
            return (
                q0 + delta * progress,
                delta * velocity / duration,
                delta * acceleration / duration**2,
            )
    final = np.radians(TEACHING_WAYPOINTS[-1].q_deg)
    return final, np.zeros(2), np.zeros(2)


def teaching_reference(time_s: float) -> CuffPoseReference:
    """Return the 18 s independently varying hip/knee teaching reference."""

    q, dq, ddq = _joint_reference(time_s)
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))


def cold_start_joint_reference(time_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Conservative-to-high-flexion joint reference for one-shot cold start."""

    time = float(np.clip(time_s, 0.0, COLD_START_TEACHING_DURATION_S))
    for start, end in zip(
        COLD_START_TEACHING_WAYPOINTS[:-1],
        COLD_START_TEACHING_WAYPOINTS[1:],
        strict=True,
    ):
        if time <= end.time_s + 1e-12:
            duration = end.time_s - start.time_s
            q0 = np.radians(start.q_deg)
            delta = np.radians(np.asarray(end.q_deg) - np.asarray(start.q_deg))
            if np.allclose(delta, 0.0):
                return q0, np.zeros(2), np.zeros(2)
            progress, velocity, acceleration = quintic_progress(
                (time - start.time_s) / duration
            )
            return (
                q0 + delta * progress,
                delta * velocity / duration,
                delta * acceleration / duration**2,
            )
    final = np.radians(COLD_START_TEACHING_WAYPOINTS[-1].q_deg)
    return final, np.zeros(2), np.zeros(2)


def cold_start_teaching_reference(time_s: float) -> CuffPoseReference:
    q, dq, ddq = cold_start_joint_reference(time_s)
    # This nominal pose is only a population-prior placeholder.  The cold-start
    # rollout replaces it with the online geometry model anchored at measured
    # cuff pose before sending any target to the robot.
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))
