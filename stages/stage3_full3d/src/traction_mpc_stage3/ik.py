"""Continuous full-pose inverse kinematics for the frozen cuff reference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .frames import RigidTransform, base_from_attachment_target
from .reference import stage2_cuff_pose_reference
from .robot import UR10eTorqueRobot


@dataclass(frozen=True)
class IKSample:
    time_s: float
    q_rad: np.ndarray
    position_error_m: float
    rotation_error_rad: float
    minimum_singular_value: float
    condition_number: float
    contact_pairs: tuple[tuple[str, str], ...]


def _pose_residual(
    robot: UR10eTorqueRobot,
    q_rad: np.ndarray,
    base_from_attachment: RigidTransform,
) -> np.ndarray:
    robot.set_configuration(q_rad)
    actual = robot.attachment_pose()
    rotation_error = Rotation.from_matrix(
        base_from_attachment.rotation @ actual.rotation.T
    ).as_rotvec()
    return np.concatenate(
        [actual.translation - base_from_attachment.translation, rotation_error]
    )


def _solve_candidates(
    robot: UR10eTorqueRobot,
    target: RigidTransform,
    seeds: list[np.ndarray],
    *,
    periodic_reference: np.ndarray | None = None,
) -> list[tuple[float, np.ndarray]]:
    limits = robot.joint_limits_rad
    lower = limits[:, 0]
    upper = limits[:, 1]
    candidates: list[tuple[float, np.ndarray]] = []
    for seed in seeds:
        clipped = np.clip(np.asarray(seed), lower + 1e-9, upper - 1e-9)
        solution = least_squares(
            lambda q: _pose_residual(robot, q, target),
            clipped,
            bounds=(lower, upper),
            xtol=1e-12,
            ftol=1e-12,
            gtol=1e-12,
            max_nfev=1600,
        )
        q = solution.x.copy()
        # The Menagerie model permits two full turns on five joints. Use the
        # principal representation initially, then the equivalent angle nearest
        # the previous sample so crossing +/-pi cannot create a false 360-deg jump.
        for index, (low, high) in enumerate(limits):
            if high - low > 2.0 * np.pi + 1e-6:
                equivalent = [
                    q[index] + turns * 2.0 * np.pi
                    for turns in range(-2, 3)
                    if low <= q[index] + turns * 2.0 * np.pi <= high
                ]
                reference = (
                    0.0
                    if periodic_reference is None
                    else float(periodic_reference[index])
                )
                q[index] = min(equivalent, key=lambda value: abs(value - reference))
        error = float(np.linalg.norm(_pose_residual(robot, q, target)))
        candidates.append((error, q))
    return candidates


def _initial_solution(
    robot: UR10eTorqueRobot,
    target: RigidTransform,
) -> np.ndarray:
    rng = np.random.default_rng(20260824)
    limits = robot.joint_limits_rad
    seeds = [
        robot.home_q_rad,
        np.zeros(6),
        np.radians([-70.0, -27.0, 82.0, 23.0, -105.0, -25.0]),
        np.radians([-60.0, -30.0, 90.0, 20.0, -100.0, -20.0]),
    ]
    seeds.extend(rng.uniform(limits[:, 0], limits[:, 1]) for _ in range(12))
    exact = [q for error, q in _solve_candidates(robot, target, seeds) if error < 1e-8]
    if not exact:
        raise RuntimeError("no full-pose UR10e IK branch reaches the initial cuff pose")

    def conditioning(q: np.ndarray) -> float:
        robot.set_configuration(q)
        return float(np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)[-1])

    # Select the most nonsingular exact initial branch once. Subsequent samples
    # are selected only by continuity from this branch.
    return max(exact, key=conditioning).copy()


def solve_cuff_trajectory_ik(
    robot: UR10eTorqueRobot,
    times_s: np.ndarray,
    *,
    lower_q2_deg: float = 3.0,
) -> list[IKSample]:
    times = np.asarray(times_s, dtype=float)
    if times.ndim != 1 or len(times) < 2 or np.any(np.diff(times) < 0.0):
        raise ValueError("times_s must be a nondecreasing vector with at least two samples")

    samples: list[IKSample] = []
    previous: np.ndarray | None = None
    rng = np.random.default_rng(20260824)
    for time_s in times:
        reference = stage2_cuff_pose_reference(
            float(time_s), lower_q2_deg=lower_q2_deg
        )
        target = base_from_attachment_target(reference.world_from_cuff)
        if previous is None:
            q = _initial_solution(robot, target)
        else:
            seeds = [previous]
            seeds.extend(
                np.clip(
                    previous + rng.normal(0.0, 0.03, 6),
                    robot.joint_limits_rad[:, 0],
                    robot.joint_limits_rad[:, 1],
                )
                for _ in range(2)
            )
            candidates = _solve_candidates(
                robot,
                target,
                seeds,
                periodic_reference=previous,
            )
            exact = [candidate for error, candidate in candidates if error < 1e-8]
            if not exact:
                best_error, _ = min(candidates, key=lambda item: item[0])
                raise RuntimeError(
                    f"continuous full-pose IK failed at t={time_s:g}s: "
                    f"residual={best_error:.6g}"
                )
            q = min(exact, key=lambda candidate: np.linalg.norm(candidate - previous))

        residual = _pose_residual(robot, q, target)
        singular_values = np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)
        samples.append(
            IKSample(
                time_s=float(time_s),
                q_rad=q.copy(),
                position_error_m=float(np.linalg.norm(residual[:3])),
                rotation_error_rad=float(np.linalg.norm(residual[3:])),
                minimum_singular_value=float(singular_values[-1]),
                condition_number=float(singular_values[0] / singular_values[-1]),
                contact_pairs=tuple(robot.contact_pairs()),
            )
        )
        previous = q.copy()
    return samples
