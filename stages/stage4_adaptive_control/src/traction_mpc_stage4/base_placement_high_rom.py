"""Common UR10e base-placement search for high-ROM path feasibility.

This module is kinematic and quasi-static only.  It implements the revised
research collision policy: cuff/thigh/mid-shank contact with the support plane
is diagnostic rather than trajectory-failing, while robot/environment,
unintended robot/Human, robot self-collision, distal ankle-point clearance,
IK, joint, Jacobian, and the conditional 200 N cuff-force gate remain required.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import BED_HEIGHT_M, CoupledUR10eHumanV2
from traction_mpc_stage3.frames import RigidTransform, base_from_attachment_target
from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    HumanV2Parameters,
)
from traction_mpc_stage3.ik import _pose_residual, _solve_candidates
from traction_mpc_stage3.reference import _world_from_cuff
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .continuous_high_rom import (
    CANDIDATE_ENDPOINTS_DEG,
    INITIAL_HUMAN_Q_DEG,
    PATH_SAMPLE_COUNT,
    _intervals,
    enumerate_initial_ik_branches,
    smooth_joint_path,
)
from .cuff_allocator import default_engineering_cuff_allocator
from .human_model import inverse_dynamics
from .high_rom_feasibility import (
    GEOMETRY_TOLERANCE_M,
    IK_EXACT_RESIDUAL,
    bed_clearances,
    human_landmarks,
    static_collision_diagnostics,
    static_torque_requirements,
)


PRIMARY_ENDPOINT_NAMES = (
    "hip_dominant_100_60",
    "both_high_90_90",
    "aggressive_120_90",
)
COARSE_PATH_SAMPLE_COUNT = 21


@dataclass(frozen=True)
class BasePose:
    x_m: float
    y_m: float
    z_m: float
    yaw_deg: float

    def transform(self) -> RigidTransform:
        return RigidTransform(
            Rotation.from_euler("z", self.yaw_deg, degrees=True).as_matrix(),
            np.array([self.x_m, self.y_m, self.z_m], dtype=float),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "translation_m": [self.x_m, self.y_m, self.z_m],
            "yaw_deg": self.yaw_deg,
            "rotation_matrix": self.transform().rotation.tolist(),
        }


def coarse_base_candidates() -> list[BasePose]:
    """Return a finite bedside mounting grid, not an arbitrary 6-DoF search."""

    longitudinal_x_m = (0.90, 1.10, 1.30)
    lateral_y_m = (-0.62, -0.77, -0.92)
    base_height_m = (0.16, 0.24, 0.32)
    yaw_deg = (-20.0, 0.0, 20.0)
    return [
        BasePose(x, y, z, yaw)
        for x in longitudinal_x_m
        for y in lateral_y_m
        for z in base_height_m
        for yaw in yaw_deg
    ]


def local_refinement_candidates(center: BasePose) -> list[BasePose]:
    """Refine the four physically meaningful mounting coordinates locally."""

    candidates = {
        BasePose(
            round(center.x_m + dx, 6),
            round(center.y_m + dy, 6),
            round(center.z_m + dz, 6),
            round(center.yaw_deg + dyaw, 6),
        )
        for dx in (-0.10, 0.0, 0.10)
        for dy in (-0.075, 0.0, 0.075)
        for dz in (-0.04, 0.0, 0.04)
        for dyaw in (-10.0, 0.0, 10.0)
        if 0.75 <= center.x_m + dx <= 1.45
        and -1.05 <= center.y_m + dy <= -0.50
        and 0.12 <= center.z_m + dz <= 0.40
        and -35.0 <= center.yaw_deg + dyaw <= 35.0
    }
    return sorted(
        candidates,
        key=lambda item: (item.x_m, item.y_m, item.z_m, item.yaw_deg),
    )


def _branch_metrics(
    endpoint_name: str,
    endpoint_deg: np.ndarray,
    initial_robot_q: np.ndarray,
    *,
    world_from_base: RigidTransform,
    robot: UR10eTorqueRobot,
    plant: CoupledUR10eHumanV2,
    sample_count: int,
    retain_trace: bool,
    human: HumanV2Parameters = HUMAN,
    robot_bed_is_blocker: bool = True,
    use_actual_passive_model: bool = False,
) -> dict[str, Any]:
    allocator = default_engineering_cuff_allocator()
    fraction, q_path_deg = smooth_joint_path(endpoint_deg, sample_count=sample_count)
    previous = np.asarray(initial_robot_q, dtype=float).copy()
    robot_q: list[np.ndarray] = []
    ik_residuals: list[float] = []
    conditions: list[float] = []
    sigma_min: list[float] = []
    joint_margins_deg: list[float] = []
    force_n: list[float] = []
    moment_nm: list[float] = []
    self_collision: list[bool] = []
    clearances: dict[str, list[float]] = {
        "robot_bed_m": [],
        "adapter_bed_m": [],
        "robot_human_m": [],
        "adapter_human_m": [],
        "distal_ankle_support_plane_m": [],
    }
    ignored_support_clearances: dict[str, list[float]] = {
        "cuff_bed_m": [],
        "thigh_bed_m": [],
        "mid_shank_bed_m": [],
    }
    failure_sample: int | None = None

    for sample_index, q_deg in enumerate(q_path_deg):
        q_human = np.radians(q_deg)
        target = base_from_attachment_target(
            _world_from_cuff(q_human), world_from_base=world_from_base
        )
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
        singular_values = np.linalg.svd(
            robot.attachment_jacobian(), compute_uv=False
        )
        limits = robot.joint_limits_rad
        joint_margin = np.minimum(
            candidate - limits[:, 0], limits[:, 1] - candidate
        )
        collision = static_collision_diagnostics(plant, q_human, candidate)
        support = bed_clearances(q_human)
        ankle_clearance = float(
            human_landmarks(q_human)["ankle"][2] - BED_HEIGHT_M
        )
        torque = (
            inverse_dynamics(q_human, np.zeros(2), np.zeros(2), human)
            if use_actual_passive_model
            else static_torque_requirements(q_human)["without_soft_limit_nm"]
        )
        allocation = allocator.allocate(torque, q_human, human)

        robot_q.append(candidate.copy())
        ik_residuals.append(float(residual))
        sigma_min.append(float(singular_values[-1]))
        conditions.append(float(singular_values[0] / singular_values[-1]))
        joint_margins_deg.append(float(np.min(np.degrees(joint_margin))))
        force_n.append(float(allocation["force_norm_n"]))
        moment_nm.append(abs(float(allocation["sagittal_wrench"][2])))
        clearances["robot_bed_m"].append(
            float(collision["robot_bed_min_distance_m"])
        )
        clearances["adapter_bed_m"].append(
            float(collision["adapter_bed_min_distance_m"])
        )
        clearances["robot_human_m"].append(
            float(collision["robot_human_min_distance_m"])
        )
        clearances["adapter_human_m"].append(
            float(collision["adapter_human_min_distance_m"])
        )
        clearances["distal_ankle_support_plane_m"].append(ankle_clearance)
        ignored_support_clearances["cuff_bed_m"].append(
            float(collision["sleeve_bed_min_distance_m"])
        )
        ignored_support_clearances["thigh_bed_m"].append(float(support["thigh_m"]))
        ignored_support_clearances["mid_shank_bed_m"].append(
            float(support["shank_m"])
        )
        self_collision.append(bool(collision["robot_self_contact_pairs"]))
        previous = candidate.copy()

    completed_count = len(robot_q)
    completed = failure_sample is None
    retained_fraction = fraction[:completed_count]
    retained_q_deg = q_path_deg[:completed_count]
    arrays = {
        name: np.asarray(values, dtype=float) for name, values in clearances.items()
    }
    ignored_arrays = {
        name: np.asarray(values, dtype=float)
        for name, values in ignored_support_clearances.items()
    }
    robot_q_array = np.asarray(robot_q)
    robot_steps_deg = (
        np.degrees(np.linalg.norm(np.diff(robot_q_array, axis=0), axis=1))
        if completed_count > 1
        else np.zeros(0)
    )
    collision_masks = {
        name: values < -GEOMETRY_TOLERANCE_M for name, values in arrays.items()
    }
    collision_masks["robot_self_collision"] = np.asarray(
        self_collision, dtype=bool
    )
    force_array = np.asarray(force_n, dtype=float)
    condition_array = np.asarray(conditions, dtype=float)
    sigma_array = np.asarray(sigma_min, dtype=float)
    margin_array = np.asarray(joint_margins_deg, dtype=float)
    required_names = [
        "robot_human_m",
        "adapter_human_m",
        "distal_ankle_support_plane_m",
    ]
    if robot_bed_is_blocker:
        required_names = ["robot_bed_m", "adapter_bed_m", *required_names]
    required_masks = {
        name: collision_masks[name] for name in required_names
    }
    required_masks["robot_self_collision"] = collision_masks[
        "robot_self_collision"
    ]
    required_clearance = (
        np.min(np.column_stack([arrays[name] for name in required_names]), axis=1)
        if completed_count
        else np.zeros(0)
    )
    algebraic_singularity = bool(
        not completed_count
        or np.any(sigma_array <= 0.0)
        or np.any(~np.isfinite(condition_array))
    )
    force_over_gate = force_array > CUFF_TRANSLATIONAL_FORCE_GATE_N
    strict_feasible = bool(
        completed
        and not any(np.any(mask) for mask in required_masks.values())
        and not algebraic_singularity
        and np.all(~force_over_gate)
        and np.all(margin_array >= -1e-10)
    )
    result: dict[str, Any] = {
        "endpoint_name": endpoint_name,
        "endpoint_deg": np.asarray(endpoint_deg, dtype=float).tolist(),
        "sample_count_requested": sample_count,
        "sample_count_completed": completed_count,
        "ik_completed": completed,
        "ik_failure_sample": failure_sample,
        "maximum_ik_residual": max(ik_residuals, default=None),
        "maximum_robot_joint_step_deg": float(
            np.max(robot_steps_deg) if len(robot_steps_deg) else 0.0
        ),
        "joint_flip_over_90deg_detected": bool(np.any(robot_steps_deg > 90.0)),
        "revised_policy_continuous_feasible": strict_feasible,
        "minimum_required_clearance_m": (
            float(np.min(required_clearance)) if len(required_clearance) else None
        ),
        "minimum_clearance_by_required_domain_m": {
            name: float(np.min(values)) if len(values) else None
            for name, values in arrays.items()
        },
        "ignored_support_contact_diagnostics_m": {
            name: float(np.min(values)) if len(values) else None
            for name, values in ignored_arrays.items()
        },
        "failure_intervals": {
            name: _intervals(mask, retained_fraction, retained_q_deg)
            for name, mask in collision_masks.items()
        },
        "robot": {
            "worst_jacobian_condition": (
                float(np.max(condition_array)) if len(condition_array) else None
            ),
            "minimum_jacobian_singular_value": (
                float(np.min(sigma_array)) if len(sigma_array) else None
            ),
            "algebraic_singularity_detected": algebraic_singularity,
            "minimum_joint_limit_margin_deg": (
                float(np.min(margin_array)) if len(margin_array) else None
            ),
        },
        "conditional_quasistatic": {
            "peak_cuff_force_n": (
                float(np.max(force_array)) if len(force_array) else None
            ),
            "peak_cuff_moment_abs_nm": (
                float(np.max(moment_nm)) if moment_nm else None
            ),
            "force_over_200n_intervals": _intervals(
                force_over_gate, retained_fraction, retained_q_deg
            ),
            "convention": (
                "actual supplied Human V2 passive and soft-limit model"
                if use_actual_passive_model
                else "gravity plus ordinary passive stiffness with the current "
                "soft-limit term removed; not an amended Human V2 model"
            ),
        },
        "policy": {
            "required": [
                "robot-Human clearance",
                "adapter-Human clearance",
                "robot self-collision absence",
                "distal ankle-point support-plane clearance",
                "continuous IK, joint limits, non-singularity, and <=200 N cuff force",
            ],
            "ignored_as_failure": [
                *(
                    [
                        "robot-bed/environment clearance",
                        "adapter-bed/environment clearance",
                    ]
                    if not robot_bed_is_blocker
                    else []
                ),
                "finite cuff thickness versus support plane",
                "thigh versus support plane",
                "mid-shank versus support plane",
            ],
            "foot_model_added": False,
        },
    }
    if retain_trace:
        result["trace"] = {
            "path_fraction": retained_fraction.tolist(),
            "human_q_deg": retained_q_deg.tolist(),
            "minimum_required_clearance_m": required_clearance.tolist(),
            "robot_bed_clearance_m": arrays["robot_bed_m"].tolist(),
            "robot_human_clearance_m": arrays["robot_human_m"].tolist(),
            "adapter_human_clearance_m": arrays["adapter_human_m"].tolist(),
            "distal_ankle_support_plane_clearance_m": arrays[
                "distal_ankle_support_plane_m"
            ].tolist(),
            "robot_jacobian_condition": condition_array.tolist(),
        }
    return result


def audit_path_at_base(
    endpoint_name: str,
    endpoint_deg: np.ndarray,
    initial_branches: Iterable[np.ndarray],
    *,
    world_from_base: RigidTransform,
    sample_count: int,
    retain_trace: bool,
    human: HumanV2Parameters = HUMAN,
    robot_bed_is_blocker: bool = True,
    use_actual_passive_model: bool = False,
) -> dict[str, Any]:
    branches = list(initial_branches)
    if not branches:
        return {
            "endpoint_name": endpoint_name,
            "endpoint_deg": np.asarray(endpoint_deg, dtype=float).tolist(),
            "sample_count_requested": sample_count,
            "sample_count_completed": 0,
            "ik_completed": False,
            "revised_policy_continuous_feasible": False,
            "minimum_required_clearance_m": None,
            "initial_branch_count_evaluated": 0,
            "selected_initial_branch_index": None,
            "failure_reason": "no exact initial IK branch",
        }
    robot = UR10eTorqueRobot()
    plant = CoupledUR10eHumanV2(human, world_from_base=world_from_base)
    results = [
        _branch_metrics(
            endpoint_name,
            endpoint_deg,
            branch,
            world_from_base=world_from_base,
            robot=robot,
            plant=plant,
            sample_count=sample_count,
            retain_trace=retain_trace,
            human=human,
            robot_bed_is_blocker=robot_bed_is_blocker,
            use_actual_passive_model=use_actual_passive_model,
        )
        for branch in branches
    ]

    def score(result: dict[str, Any]) -> tuple[float, ...]:
        interval_samples = sum(
            interval["end_sample"] - interval["start_sample"] + 1
            for intervals in result["failure_intervals"].values()
            for interval in intervals
        )
        clearance = result["minimum_required_clearance_m"]
        condition = result["robot"]["worst_jacobian_condition"]
        margin = result["robot"]["minimum_joint_limit_margin_deg"]
        return (
            float(result["revised_policy_continuous_feasible"]),
            float(result["ik_completed"]),
            -float(interval_samples),
            -float(result["joint_flip_over_90deg_detected"]),
            float(clearance if clearance is not None else -math.inf),
            -float(condition if condition is not None else math.inf),
            float(margin if margin is not None else -math.inf),
        )

    selected_index = max(range(len(results)), key=lambda index: score(results[index]))
    selected = dict(results[selected_index])
    selected["initial_branch_count_evaluated"] = len(results)
    selected["selected_initial_branch_index"] = selected_index
    return selected


def audit_base_pose(
    pose: BasePose,
    *,
    sample_count: int = COARSE_PATH_SAMPLE_COUNT,
    retain_trace: bool = False,
    random_seed_count: int = 16,
) -> dict[str, Any]:
    world_from_base = pose.transform()
    robot = UR10eTorqueRobot()
    initial_branches = enumerate_initial_ik_branches(
        robot,
        random_seed_count=random_seed_count,
        world_from_base=world_from_base,
    )
    paths = {
        name: audit_path_at_base(
            name,
            CANDIDATE_ENDPOINTS_DEG[name],
            initial_branches,
            world_from_base=world_from_base,
            sample_count=sample_count,
            retain_trace=retain_trace,
        )
        for name in PRIMARY_ENDPOINT_NAMES
    }
    feasible_count = sum(
        path["revised_policy_continuous_feasible"] for path in paths.values()
    )
    ik_completed_count = sum(path["ik_completed"] for path in paths.values())
    clearances = [
        path.get("minimum_required_clearance_m") for path in paths.values()
    ]
    conditions = [
        path.get("robot", {}).get("worst_jacobian_condition")
        for path in paths.values()
    ]
    margins = [
        path.get("robot", {}).get("minimum_joint_limit_margin_deg")
        for path in paths.values()
    ]
    return {
        "base_pose": pose.as_dict(),
        "initial_exact_ik_branch_count": len(initial_branches),
        "sample_count_per_path": sample_count,
        "primary_feasible_count": int(feasible_count),
        "primary_ik_completed_count": int(ik_completed_count),
        "all_primary_feasible": feasible_count == len(PRIMARY_ENDPOINT_NAMES),
        "worst_primary_required_clearance_m": (
            min(clearances) if all(value is not None for value in clearances) else None
        ),
        "worst_primary_jacobian_condition": (
            max(conditions) if all(value is not None for value in conditions) else None
        ),
        "minimum_primary_joint_limit_margin_deg": (
            min(margins) if all(value is not None for value in margins) else None
        ),
        "paths": paths,
    }


def placement_score(result: dict[str, Any]) -> tuple[float, ...]:
    pose = result["base_pose"]
    x, y, z = pose["translation_m"]
    yaw = pose["yaw_deg"]
    clearance = result["worst_primary_required_clearance_m"]
    condition = result["worst_primary_jacobian_condition"]
    margin = result["minimum_primary_joint_limit_margin_deg"]
    normalized_mount_change = math.sqrt(
        ((x - 1.10) / 0.20) ** 2
        + ((y + 0.62) / 0.20) ** 2
        + ((z - 0.04) / 0.10) ** 2
        + (yaw / 20.0) ** 2
    )
    return (
        float(result["all_primary_feasible"]),
        float(result["primary_feasible_count"]),
        float(result["primary_ik_completed_count"]),
        float(
            round(clearance, 6) if clearance is not None else -math.inf
        ),
        -float(condition if condition is not None else math.inf),
        float(margin if margin is not None else -math.inf),
        -normalized_mount_change,
    )


def search_common_base(
    candidates: Iterable[BasePose],
    *,
    sample_count: int = COARSE_PATH_SAMPLE_COUNT,
    random_seed_count: int = 16,
) -> dict[str, Any]:
    results = [
        audit_base_pose(
            pose,
            sample_count=sample_count,
            retain_trace=False,
            random_seed_count=random_seed_count,
        )
        for pose in candidates
    ]
    selected_index = max(range(len(results)), key=lambda index: placement_score(results[index]))
    return {
        "candidate_count": len(results),
        "sample_count_per_path": sample_count,
        "selection_rule": (
            "lexicographic: all three feasible, feasible-path count, completed-IK "
            "path count, largest worst required clearance at 1 micrometre resolution, "
            "lower worst Jacobian condition, larger joint-limit margin, then smaller "
            "normalized mounting change"
        ),
        "selected_index": selected_index,
        "selected": results[selected_index],
        "candidates": results,
    }


def dense_reaudit(pose: BasePose) -> dict[str, Any]:
    return audit_base_pose(
        pose,
        sample_count=PATH_SAMPLE_COUNT,
        retain_trace=True,
        random_seed_count=40,
    )
