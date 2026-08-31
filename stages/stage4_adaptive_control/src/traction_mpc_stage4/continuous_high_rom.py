"""Dense kinematic/collision audit for candidate high-ROM paths.

No controller or dynamic rollout is executed here.  Human joint paths are
sampled kinematically, UR10e IK is continued from the preceding sample, and
the frozen conditional no-soft-limit quasi-static convention is reused.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage3.frames import (
    WORLD_FROM_BASE,
    RigidTransform,
    base_from_attachment_target,
)
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage3.ik import _pose_residual, _solve_candidates
from traction_mpc_stage3.reference import _world_from_cuff, quintic_progress
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .cuff_allocator import default_engineering_cuff_allocator
from .high_rom_feasibility import (
    GEOMETRY_TOLERANCE_M,
    IK_EXACT_RESIDUAL,
    bed_clearances,
    static_collision_diagnostics,
    static_torque_requirements,
)


INITIAL_HUMAN_Q_DEG = np.array([5.0, 10.0])
PATH_SAMPLE_COUNT = 121
CANDIDATE_ENDPOINTS_DEG = {
    "hip_dominant_100_60": np.array([100.0, 60.0]),
    "both_high_90_90": np.array([90.0, 90.0]),
    "aggressive_120_90": np.array([120.0, 90.0]),
    "knee_dominant_60_100": np.array([60.0, 100.0]),
}


def smooth_joint_path(
    endpoint_deg: np.ndarray,
    *,
    sample_count: int = PATH_SAMPLE_COUNT,
) -> tuple[np.ndarray, np.ndarray]:
    if sample_count < 3:
        raise ValueError("sample_count must be at least three")
    endpoint = np.asarray(endpoint_deg, dtype=float)
    if endpoint.shape != (2,) or not np.all(np.isfinite(endpoint)):
        raise ValueError("endpoint_deg must be a finite two-vector")
    fraction = np.linspace(0.0, 1.0, sample_count)
    progress = np.array([quintic_progress(value)[0] for value in fraction])
    q_deg = INITIAL_HUMAN_Q_DEG + progress[:, None] * (
        endpoint - INITIAL_HUMAN_Q_DEG
    )
    return fraction, q_deg


def enumerate_initial_ik_branches(
    robot: UR10eTorqueRobot,
    *,
    random_seed_count: int = 40,
    world_from_base: RigidTransform = WORLD_FROM_BASE,
) -> list[np.ndarray]:
    target = base_from_attachment_target(
        _world_from_cuff(np.radians(INITIAL_HUMAN_Q_DEG)),
        world_from_base=world_from_base,
    )
    rng = np.random.default_rng(20260831)
    limits = robot.joint_limits_rad
    seeds = [
        robot.home_q_rad,
        np.zeros(6),
        np.radians([-70.0, -27.0, 82.0, 23.0, -105.0, -25.0]),
        np.radians([-60.0, -30.0, 90.0, 20.0, -100.0, -20.0]),
    ]
    seeds.extend(
        rng.uniform(limits[:, 0], limits[:, 1]) for _ in range(random_seed_count)
    )
    exact = [
        q
        for error, q in _solve_candidates(robot, target, seeds)
        if error < IK_EXACT_RESIDUAL
    ]
    unique: list[np.ndarray] = []
    for candidate in exact:
        if not any(np.linalg.norm(candidate - retained) < 1e-5 for retained in unique):
            unique.append(candidate.copy())
    return unique


def _intervals(
    mask: np.ndarray,
    fraction: np.ndarray,
    q_deg: np.ndarray,
) -> list[dict[str, Any]]:
    indices = np.flatnonzero(mask)
    if len(indices) == 0:
        return []
    groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
    return [
        {
            "start_sample": int(group[0]),
            "end_sample": int(group[-1]),
            "start_fraction": float(fraction[group[0]]),
            "end_fraction": float(fraction[group[-1]]),
            "start_q_deg": q_deg[group[0]].tolist(),
            "end_q_deg": q_deg[group[-1]].tolist(),
        }
        for group in groups
    ]


def _audit_branch(
    endpoint_name: str,
    endpoint_deg: np.ndarray,
    initial_robot_q: np.ndarray,
    *,
    sample_count: int,
) -> dict[str, Any]:
    robot = UR10eTorqueRobot()
    plant = CoupledUR10eHumanV2()
    allocator = default_engineering_cuff_allocator()
    fraction, q_path_deg = smooth_joint_path(
        endpoint_deg, sample_count=sample_count
    )
    robot_q: list[np.ndarray] = []
    ik_residual: list[float] = []
    sigma_min: list[float] = []
    condition: list[float] = []
    joint_margin_deg: list[float] = []
    force_n: list[float] = []
    moment_nm: list[float] = []
    clearances: dict[str, list[float]] = {
        "robot_human_m": [],
        "robot_bed_m": [],
        "adapter_human_m": [],
        "adapter_bed_m": [],
        "cuff_bed_m": [],
        "human_bed_m": [],
    }
    self_collision: list[bool] = []
    previous = np.asarray(initial_robot_q, dtype=float).copy()
    failure_sample: int | None = None

    for sample_index, q_deg in enumerate(q_path_deg):
        q_human = np.radians(q_deg)
        target = base_from_attachment_target(_world_from_cuff(q_human))
        if sample_index == 0:
            candidate = previous.copy()
            residual = float(np.linalg.norm(_pose_residual(robot, candidate, target)))
        else:
            candidates = _solve_candidates(
                robot,
                target,
                [previous],
                periodic_reference=previous,
            )
            residual, candidate = min(candidates, key=lambda item: item[0])
        if residual >= IK_EXACT_RESIDUAL:
            failure_sample = sample_index
            break
        robot.set_configuration(candidate)
        singular = np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)
        limits = robot.joint_limits_rad
        margins = np.minimum(candidate - limits[:, 0], limits[:, 1] - candidate)
        collision = static_collision_diagnostics(plant, q_human, candidate)
        human_bed = bed_clearances(q_human)
        torque = static_torque_requirements(q_human)["without_soft_limit_nm"]
        allocation = allocator.allocate(torque, q_human, HUMAN)

        robot_q.append(candidate.copy())
        ik_residual.append(float(residual))
        sigma_min.append(float(singular[-1]))
        condition.append(float(singular[0] / singular[-1]))
        joint_margin_deg.append(float(np.min(np.degrees(margins))))
        force_n.append(float(allocation["force_norm_n"]))
        moment_nm.append(abs(float(allocation["sagittal_wrench"][2])))
        clearances["robot_human_m"].append(
            float(collision["robot_human_min_distance_m"])
        )
        clearances["robot_bed_m"].append(
            float(collision["robot_bed_min_distance_m"])
        )
        clearances["adapter_human_m"].append(
            float(collision["adapter_human_min_distance_m"])
        )
        clearances["adapter_bed_m"].append(
            float(collision["adapter_bed_min_distance_m"])
        )
        clearances["cuff_bed_m"].append(
            float(collision["sleeve_bed_min_distance_m"])
        )
        clearances["human_bed_m"].append(
            float(min(human_bed["thigh_m"], human_bed["shank_m"]))
        )
        self_collision.append(bool(collision["robot_self_contact_pairs"]))
        previous = candidate.copy()

    completed = failure_sample is None
    retained_count = len(robot_q)
    retained_fraction = fraction[:retained_count]
    retained_human_q = q_path_deg[:retained_count]
    robot_q_array = np.asarray(robot_q)
    robot_step_deg = (
        np.degrees(np.linalg.norm(np.diff(robot_q_array, axis=0), axis=1))
        if len(robot_q_array) > 1
        else np.zeros(0)
    )
    clearance_arrays = {
        name: np.asarray(values, dtype=float) for name, values in clearances.items()
    }
    collision_masks = {
        name: values < -GEOMETRY_TOLERANCE_M
        for name, values in clearance_arrays.items()
    }
    collision_masks["robot_self_collision"] = np.asarray(self_collision, dtype=bool)
    force_array = np.asarray(force_n)
    condition_array = np.asarray(condition)
    sigma_array = np.asarray(sigma_min)
    margin_array = np.asarray(joint_margin_deg)
    all_clearance = np.concatenate(list(clearance_arrays.values()))
    per_sample_clearance = (
        np.min(np.column_stack(list(clearance_arrays.values())), axis=1)
        if retained_count
        else np.zeros(0)
    )
    combined_collision = np.zeros(retained_count, dtype=bool)
    for mask in collision_masks.values():
        combined_collision |= mask
    collision_indices = np.flatnonzero(combined_collision)
    suffix_start_sample = (
        int(collision_indices[-1] + 1) if len(collision_indices) else 0
    )
    suffix_exists = suffix_start_sample < retained_count
    strict_collision_free = bool(
        retained_count == sample_count
        and not any(np.any(mask) for mask in collision_masks.values())
    )
    algebraic_singularity = bool(
        len(sigma_array) == 0
        or np.any(sigma_array <= 0.0)
        or np.any(~np.isfinite(condition_array))
        or np.any(condition_array >= 1.0 / (6.0 * np.finfo(float).eps))
    )
    strict_feasible = bool(
        completed
        and strict_collision_free
        and not algebraic_singularity
        and np.all(force_array <= CUFF_TRANSLATIONAL_FORCE_GATE_N)
        and np.all(margin_array >= -1e-10)
    )
    current_max = np.degrees(HUMAN.q_max_rad)
    current_rom_valid = np.all(retained_human_q <= current_max + 1e-12, axis=1)
    required_upper = np.max(q_path_deg, axis=0)

    return {
        "endpoint_name": endpoint_name,
        "endpoint_deg": np.asarray(endpoint_deg, dtype=float).tolist(),
        "sample_count_requested": int(sample_count),
        "sample_count_completed": retained_count,
        "ik_completed": completed,
        "ik_failure_sample": failure_sample,
        "maximum_ik_residual": max(ik_residual, default=math.inf),
        "maximum_robot_joint_step_deg": float(
            np.max(robot_step_deg) if len(robot_step_deg) else 0.0
        ),
        "joint_flip_over_90deg_detected": bool(
            np.any(robot_step_deg > 90.0)
        ),
        "strict_continuous_path_feasible": strict_feasible,
        "strict_collision_free": strict_collision_free,
        "minimum_collision_clearance_m": float(
            np.min(all_clearance) if len(all_clearance) else -math.inf
        ),
        "minimum_clearance_by_domain_m": {
            name: float(np.min(values)) if len(values) else -math.inf
            for name, values in clearance_arrays.items()
        },
        "collision_free_suffix": {
            "exists": bool(suffix_exists and completed),
            "start_sample": suffix_start_sample if suffix_exists else None,
            "start_fraction": (
                float(retained_fraction[suffix_start_sample])
                if suffix_exists
                else None
            ),
            "start_q_deg": (
                retained_human_q[suffix_start_sample].tolist()
                if suffix_exists
                else None
            ),
            "minimum_clearance_m": (
                float(np.min(per_sample_clearance[suffix_start_sample:]))
                if suffix_exists
                else None
            ),
        },
        "collision_intervals": {
            name: _intervals(mask, retained_fraction, retained_human_q)
            for name, mask in collision_masks.items()
        },
        "robot": {
            "worst_jacobian_condition": float(
                np.max(condition_array) if len(condition_array) else math.inf
            ),
            "minimum_jacobian_singular_value": float(
                np.min(sigma_array) if len(sigma_array) else 0.0
            ),
            "algebraic_singularity_detected": algebraic_singularity,
            "minimum_joint_limit_margin_deg": float(
                np.min(margin_array) if len(margin_array) else -math.inf
            ),
        },
        "conditional_quasistatic": {
            "peak_cuff_force_n": float(
                np.max(force_array) if len(force_array) else math.inf
            ),
            "peak_cuff_moment_abs_nm": float(
                np.max(moment_nm) if moment_nm else math.inf
            ),
            "force_over_200n_intervals": _intervals(
                force_array > CUFF_TRANSLATIONAL_FORCE_GATE_N,
                retained_fraction,
                retained_human_q,
            ),
            "convention": (
                "gravity plus ordinary passive stiffness with the current "
                "soft-limit term removed; not an amended Human V2 model"
            ),
        },
        "current_human_v2_rom": {
            "current_q_max_deg": current_max.tolist(),
            "all_samples_valid": bool(
                retained_count == sample_count and np.all(current_rom_valid)
            ),
            "first_invalid_sample": (
                int(np.flatnonzero(~current_rom_valid)[0])
                if np.any(~current_rom_valid)
                else None
            ),
            "required_endpoint_upper_limit_deg": required_upper.tolist(),
            "required_upper_limit_to_avoid_5deg_soft_zone_deg": (
                np.maximum(
                    current_max,
                    required_upper + np.degrees(HUMAN.soft_limit_margin_rad),
                )
            ).tolist(),
            "passive_model_review_required": bool(
                np.any(required_upper > current_max - np.degrees(HUMAN.soft_limit_margin_rad))
            ),
        },
        "trace": {
            "path_fraction": retained_fraction.tolist(),
            "human_q_deg": retained_human_q.tolist(),
            "minimum_clearance_m": (
                per_sample_clearance.tolist()
            ),
            "robot_jacobian_condition": condition_array.tolist(),
            "cuff_force_n": force_array.tolist(),
            "cuff_moment_abs_nm": list(map(float, moment_nm)),
        },
        "cuff_human_geometry_note": (
            "the committed cuff is a solid cylinder enclosing the shank proxy; "
            "that intended enclosure is not treated as an unintended collision"
        ),
    }


def audit_candidate_path(
    endpoint_name: str,
    endpoint_deg: np.ndarray,
    initial_branches: list[np.ndarray],
    *,
    sample_count: int = PATH_SAMPLE_COUNT,
) -> dict[str, Any]:
    if not initial_branches:
        raise RuntimeError("no exact initial UR10e IK branch found")
    branches = [
        _audit_branch(
            endpoint_name,
            endpoint_deg,
            branch,
            sample_count=sample_count,
        )
        for branch in initial_branches
    ]

    def score(result: dict[str, Any]) -> tuple[float, ...]:
        collision_samples = sum(
            interval["end_sample"] - interval["start_sample"] + 1
            for intervals in result["collision_intervals"].values()
            for interval in intervals
        )
        return (
            float(result["strict_continuous_path_feasible"]),
            float(result["ik_completed"]),
            -float(collision_samples),
            float(result["minimum_collision_clearance_m"]),
            -float(result["robot"]["worst_jacobian_condition"]),
        )

    selected_index = max(range(len(branches)), key=lambda index: score(branches[index]))
    selected = dict(branches[selected_index])
    selected["initial_branch_count_evaluated"] = len(branches)
    selected["selected_initial_branch_index"] = selected_index
    selected["branch_selection_rule"] = (
        "prefer strict feasibility, IK completion, fewer collision samples, "
        "larger minimum clearance, then lower worst Jacobian condition"
    )
    return selected


def run_continuous_path_audit(
    *, sample_count: int = PATH_SAMPLE_COUNT
) -> dict[str, Any]:
    robot = UR10eTorqueRobot()
    initial_branches = enumerate_initial_ik_branches(robot)
    results = {
        name: audit_candidate_path(
            name,
            endpoint,
            initial_branches,
            sample_count=sample_count,
        )
        for name, endpoint in CANDIDATE_ENDPOINTS_DEG.items()
    }
    return {
        "audit_kind": "dense_static_continuous_ik_collision_audit",
        "controller_or_dynamic_rollout_run": False,
        "initial_human_q_deg": INITIAL_HUMAN_Q_DEG.tolist(),
        "sample_count_per_path": sample_count,
        "initial_exact_ik_branch_count": len(initial_branches),
        "paths": results,
    }
