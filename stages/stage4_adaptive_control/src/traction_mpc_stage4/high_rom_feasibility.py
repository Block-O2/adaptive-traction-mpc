"""Static high-ROM audit helpers for the frozen Human V2 / UR10e surrogate.

This module is evaluation-only.  It does not alter the frozen Human V2 ROM,
passive mechanics, collision policy, allocator, controller, or plant.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    BED_HEIGHT_M,
    HIP_HEIGHT_M,
    SHANK_RADIUS_M,
    SLEEVE_HALF_LENGTH_M,
    SLEEVE_OUTER_RADIUS_M,
    THIGH_RADIUS_M,
    CoupledUR10eHumanV2,
)
from traction_mpc_stage3.frames import base_from_attachment_target
from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    sleeve_jacobian,
    soft_limit_torque,
)
from traction_mpc_stage3.ik import _initial_solution, _pose_residual, _solve_candidates
from traction_mpc_stage3.reference import _world_from_cuff
from traction_mpc_stage3.robot import UR10eTorqueRobot

from .cuff_allocator import (
    CurrentForceMinimizingAllocator,
    default_engineering_cuff_allocator,
    sagittal_allocation_matrix,
)
from .human_model import dynamic_terms, inverse_dynamics


IK_EXACT_RESIDUAL = 1e-8
GEOMETRY_TOLERANCE_M = 1e-8


@dataclass(frozen=True)
class PoseIKResult:
    reachable: bool
    q_rad: np.ndarray | None
    residual_norm: float


def coordinate_description() -> dict[str, Any]:
    """Return conventions verified from the frozen Stage-3 port and MJCF."""

    return {
        "q1": (
            "hip flexion; positive rotation about world -Y from a thigh initially "
            "pointing along world +X"
        ),
        "q2": (
            "knee flexion relative to the thigh; positive rotation about the local "
            "+Y knee axis"
        ),
        "zero_configuration": (
            "q1=q2=0 places thigh and shank collinear along world +X, with the "
            "hip joint at z=0.062 m"
        ),
        "absolute_thigh_angle": "q1 above world +X",
        "absolute_shank_angle": "q1-q2 above world +X",
        "cuff_frame_rotation": "world_R_cuff = Ry(q2-q1)",
        "reference_angles": (
            "Stage-3 references store the same [q1,q2] coordinates; the frozen "
            "nominal peak is [45,84] deg"
        ),
        "mujoco_joints": {
            "hip_joint_axis": [0.0, -1.0, 0.0],
            "knee_joint_axis_local": [0.0, 1.0, 0.0],
            "hip_range_deg": list(np.degrees(HUMAN.q_min_rad)[0:1])
            + list(np.degrees(HUMAN.q_max_rad)[0:1]),
            "knee_range_deg": list(np.degrees(HUMAN.q_min_rad)[1:2])
            + list(np.degrees(HUMAN.q_max_rad)[1:2]),
        },
    }


def human_landmarks(q_rad: np.ndarray) -> dict[str, np.ndarray]:
    """Return planar Human V2 landmarks in the Stage-3 world frame."""

    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    hip = np.array([0.0, 0.0, HIP_HEIGHT_M])
    thigh_axis = np.array([math.cos(q1), 0.0, math.sin(q1)])
    shank_axis = np.array([math.cos(phi), 0.0, math.sin(phi)])
    knee = hip + HUMAN.thigh_length_m * thigh_axis
    ankle = knee + HUMAN.shank_length_m * shank_axis
    cuff = knee + HUMAN.sleeve_center_m * shank_axis
    sleeve_end_a = knee + (HUMAN.sleeve_center_m - SLEEVE_HALF_LENGTH_M) * shank_axis
    sleeve_end_b = knee + (HUMAN.sleeve_center_m + SLEEVE_HALF_LENGTH_M) * shank_axis
    return {
        "hip": hip,
        "knee": knee,
        "ankle": ankle,
        "cuff": cuff,
        "sleeve_end_a": sleeve_end_a,
        "sleeve_end_b": sleeve_end_b,
    }


def bed_clearances(q_rad: np.ndarray) -> dict[str, float]:
    """Analytic signed clearances from link/cuff surfaces to the bed plane."""

    points = human_landmarks(q_rad)
    return {
        "thigh_m": float(
            min(points["hip"][2], points["knee"][2])
            - THIGH_RADIUS_M
            - BED_HEIGHT_M
        ),
        "shank_m": float(
            min(points["knee"][2], points["ankle"][2])
            - SHANK_RADIUS_M
            - BED_HEIGHT_M
        ),
        "sleeve_m": float(
            min(points["sleeve_end_a"][2], points["sleeve_end_b"][2])
            - SLEEVE_OUTER_RADIUS_M
            - BED_HEIGHT_M
        ),
    }


def current_rom_valid(q_rad: np.ndarray) -> bool:
    q = np.asarray(q_rad, dtype=float)
    return bool(
        np.all(q >= np.asarray(HUMAN.q_min_rad) - 1e-12)
        and np.all(q <= np.asarray(HUMAN.q_max_rad) + 1e-12)
    )


def static_torque_requirements(q_rad: np.ndarray) -> dict[str, np.ndarray]:
    """Return frozen current-ROM and conditional no-soft-limit static torques."""

    q = np.asarray(q_rad, dtype=float)
    zero = np.zeros(2)
    current = inverse_dynamics(q, zero, zero, HUMAN)
    _, _, gravity, passive_current = dynamic_terms(q, zero, HUMAN)
    limit_torque = soft_limit_torque(q, zero, HUMAN)
    # In the frozen left-side convention passive_current = K(q-qrest)-tau_limit.
    without_soft_limit = gravity + passive_current + limit_torque
    return {
        "current_nm": current,
        "without_soft_limit_nm": without_soft_limit,
        "gravity_nm": gravity,
        "soft_limit_rhs_nm": limit_torque,
        "ordinary_passive_nm": passive_current + limit_torque,
    }


def solve_static_pose_ik(
    robot: UR10eTorqueRobot,
    q_human_rad: np.ndarray,
    *,
    continuation_seeds: Iterable[np.ndarray] = (),
) -> PoseIKResult:
    """Solve one exact full-pose UR10e cuff IK problem deterministically."""

    target = base_from_attachment_target(_world_from_cuff(q_human_rad))
    seeds = [np.asarray(seed, dtype=float) for seed in continuation_seeds]
    if seeds:
        candidates = _solve_candidates(robot, target, seeds)
        exact = [(error, q) for error, q in candidates if error < IK_EXACT_RESIDUAL]
        if exact:
            error, q = min(exact, key=lambda item: item[0])
            return PoseIKResult(True, q.copy(), float(error))

    try:
        q = _initial_solution(robot, target)
    except RuntimeError:
        standard = [
            robot.home_q_rad,
            np.zeros(6),
            np.radians([-70.0, -27.0, 82.0, 23.0, -105.0, -25.0]),
            np.radians([-60.0, -30.0, 90.0, 20.0, -100.0, -20.0]),
        ]
        candidates = _solve_candidates(robot, target, standard)
        error, q = min(candidates, key=lambda item: item[0])
        return PoseIKResult(False, None, float(error))
    error = float(np.linalg.norm(_pose_residual(robot, q, target)))
    return PoseIKResult(error < IK_EXACT_RESIDUAL, q.copy(), error)


def _minimum_geom_distance(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    first_ids: Iterable[int],
    second_ids: Iterable[int],
) -> tuple[float, tuple[str, str] | None]:
    minimum = math.inf
    pair: tuple[str, str] | None = None
    segment = np.zeros(6)
    for first in first_ids:
        for second in second_ids:
            distance = float(
                mujoco.mj_geomDistance(model, data, first, second, 10.0, segment)
            )
            if distance < minimum:
                minimum = distance
                def label(geom_id: int) -> str:
                    geom = model.geom(geom_id)
                    body = model.body(int(model.geom_bodyid[geom_id])).name or "world"
                    return geom.name or f"{body}/geom#{geom_id}"

                pair = (label(int(first)), label(int(second)))
    return minimum, pair


def static_collision_diagnostics(
    plant: CoupledUR10eHumanV2,
    q_human_rad: np.ndarray,
    q_robot_rad: np.ndarray,
) -> dict[str, Any]:
    """Query geometry distances without enabling excluded collision domains."""

    mujoco.mj_resetData(plant.model, plant.data)
    plant.data.eq_active[plant.weld_id] = 0
    plant.data.qpos[plant.human_qpos_indices] = np.asarray(q_human_rad)
    plant.data.qpos[plant.robot_qpos_indices] = np.asarray(q_robot_rad)
    mujoco.mj_forward(plant.model, plant.data)

    bed_ids = [int(plant.bed_geom_id)]
    human_ids = sorted(int(value) for value in plant.human_geom_ids)
    adapter_id = int(plant.adapter_geom_id)
    robot_ids = sorted(
        int(value)
        for value in plant.robot_collision_geom_ids
        if int(value) != adapter_id
    )
    sleeve_id = int(plant.sleeve_geom_id)
    robot_bed = _minimum_geom_distance(
        plant.model, plant.data, robot_ids, bed_ids
    )
    robot_human = _minimum_geom_distance(
        plant.model, plant.data, robot_ids, human_ids
    )
    adapter_human = _minimum_geom_distance(
        plant.model, plant.data, [adapter_id], human_ids
    )
    adapter_bed = _minimum_geom_distance(
        plant.model, plant.data, [adapter_id], bed_ids
    )
    sleeve_bed = _minimum_geom_distance(
        plant.model, plant.data, [sleeve_id], bed_ids
    )
    self_pairs = []
    for index in range(plant.data.ncon):
        contact = plant.data.contact[index]
        pair_ids = {int(contact.geom1), int(contact.geom2)}
        if pair_ids <= plant.robot_collision_geom_ids:
            self_pairs.append(
                (
                    plant.model.geom(int(contact.geom1)).name
                    or f"geom#{int(contact.geom1)}",
                    plant.model.geom(int(contact.geom2)).name
                    or f"geom#{int(contact.geom2)}",
                )
            )
    return {
        "robot_bed_min_distance_m": robot_bed[0],
        "robot_bed_closest_pair": robot_bed[1],
        "robot_human_min_distance_m": robot_human[0],
        "robot_human_closest_pair": robot_human[1],
        "adapter_human_min_distance_m": adapter_human[0],
        "adapter_human_closest_pair": adapter_human[1],
        "adapter_bed_min_distance_m": adapter_bed[0],
        "adapter_bed_closest_pair": adapter_bed[1],
        "sleeve_bed_min_distance_m": sleeve_bed[0],
        "sleeve_bed_closest_pair": sleeve_bed[1],
        "robot_self_contact_pairs": self_pairs,
        "policy_note": (
            "robot-bed, robot-Human, adapter-bed, and adapter-Human contacts are "
            "not controller collision dynamics; signed distances here are "
            "evaluation-only geometry queries"
        ),
    }


def audit_pose(
    q_deg: tuple[float, float],
    robot: UR10eTorqueRobot,
    plant: CoupledUR10eHumanV2,
    *,
    continuation_seeds: Iterable[np.ndarray] = (),
) -> tuple[dict[str, Any], np.ndarray | None]:
    """Audit one high-ROM configuration without dynamic simulation."""

    q = np.radians(q_deg)
    landmarks = human_landmarks(q)
    clearances = bed_clearances(q)
    rom_valid = current_rom_valid(q)
    torque = static_torque_requirements(q)
    current_allocator = default_engineering_cuff_allocator()
    minimum_force_allocator = CurrentForceMinimizingAllocator()
    current_allocation = current_allocator.allocate(torque["current_nm"], q, HUMAN)
    extended_allocation = current_allocator.allocate(
        torque["without_soft_limit_nm"], q, HUMAN
    )
    minimum_force = minimum_force_allocator.allocate(
        torque["without_soft_limit_nm"], q, HUMAN
    )
    matrix = sagittal_allocation_matrix(q, HUMAN)
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    translational_map = sleeve_jacobian(q, HUMAN)[[0, 2], :].T
    translational_singular_values = np.linalg.svd(
        translational_map, compute_uv=False
    )

    ik = solve_static_pose_ik(
        robot, q, continuation_seeds=continuation_seeds
    )
    collision: dict[str, Any] | None = None
    robot_metrics: dict[str, Any] = {
        "reachable": ik.reachable,
        "ik_residual_norm": ik.residual_norm,
    }
    if ik.reachable and ik.q_rad is not None:
        robot.set_configuration(ik.q_rad)
        jacobian_singular = np.linalg.svd(
            robot.attachment_jacobian(), compute_uv=False
        )
        limits = robot.joint_limits_rad
        joint_margin = np.minimum(
            ik.q_rad - limits[:, 0], limits[:, 1] - ik.q_rad
        )
        loaded_torque = (
            robot.bias_torque_nm()
            + robot.wrench_to_joint_torque(
                np.asarray(extended_allocation["wrench_world"])
            )
        )
        loaded_fraction = np.abs(loaded_torque) / robot.torque_limits_nm
        collision = static_collision_diagnostics(plant, q, ik.q_rad)
        robot_metrics.update(
            {
                "q_deg": np.degrees(ik.q_rad).tolist(),
                "minimum_joint_limit_margin_deg": float(
                    np.min(np.degrees(joint_margin))
                ),
                "minimum_6d_jacobian_singular_value": float(
                    jacobian_singular[-1]
                ),
                "jacobian_condition_number": float(
                    jacobian_singular[0] / jacobian_singular[-1]
                ),
                "gravity_plus_conditional_wrench_joint_torque_nm": (
                    loaded_torque.tolist()
                ),
                "peak_modeled_torque_limit_fraction": float(
                    np.max(loaded_fraction)
                ),
                "minimum_modeled_torque_margin_nm": float(
                    np.min(robot.torque_limits_nm - np.abs(loaded_torque))
                ),
            }
        )

    human_bed_clear = min(clearances.values()) >= -GEOMETRY_TOLERANCE_M
    intrinsic_mechanical_blockers: list[str] = []
    surrogate_geometry_blockers: list[str] = []
    if not human_bed_clear:
        intrinsic_mechanical_blockers.append("human_or_sleeve_bed_penetration")
    if not ik.reachable:
        intrinsic_mechanical_blockers.append("ur10e_full_pose_ik_unreachable")
    if collision is not None:
        if collision["robot_bed_min_distance_m"] < -GEOMETRY_TOLERANCE_M:
            surrogate_geometry_blockers.append("ur10e_bed_intersection")
        if collision["robot_human_min_distance_m"] < -GEOMETRY_TOLERANCE_M:
            surrogate_geometry_blockers.append("ur10e_human_intersection")
        if collision["adapter_human_min_distance_m"] < -GEOMETRY_TOLERANCE_M:
            surrogate_geometry_blockers.append("adapter_human_intersection")
        if collision["adapter_bed_min_distance_m"] < -GEOMETRY_TOLERANCE_M:
            surrogate_geometry_blockers.append("adapter_bed_intersection")
        if collision["robot_self_contact_pairs"]:
            intrinsic_mechanical_blockers.append("ur10e_self_collision")
    if robot_metrics.get("peak_modeled_torque_limit_fraction", 0.0) > 1.0:
        intrinsic_mechanical_blockers.append("ur10e_modeled_torque_limit")
    if extended_allocation["force_norm_n"] > CUFF_TRANSLATIONAL_FORCE_GATE_N:
        intrinsic_mechanical_blockers.append("conditional_cuff_force_gate")

    mechanical_blockers = (
        intrinsic_mechanical_blockers + surrogate_geometry_blockers
    )

    if intrinsic_mechanical_blockers:
        category = "geometric_or_robotic_infeasible"
    elif surrogate_geometry_blockers:
        category = "blocked_by_current_surrogate_collision_geometry"
    elif rom_valid:
        category = "valid_under_current_human_v2"
    else:
        category = "geometrically_feasible_if_human_rom_is_extended"

    soft_norm = float(np.linalg.norm(torque["soft_limit_rhs_nm"]))
    base_norm = float(np.linalg.norm(torque["without_soft_limit_nm"]))
    row: dict[str, Any] = {
        "q1_deg": float(q_deg[0]),
        "q2_deg": float(q_deg[1]),
        "absolute_thigh_deg": float(q_deg[0]),
        "absolute_shank_deg": float(q_deg[0] - q_deg[1]),
        "current_rom_valid": rom_valid,
        "current_soft_limit_active": soft_norm > 1e-12,
        "current_rom_model_dominated": bool(
            not rom_valid and soft_norm > base_norm
        ),
        "classification": category,
        "mechanical_blockers": mechanical_blockers,
        "intrinsic_mechanical_blockers": intrinsic_mechanical_blockers,
        "surrogate_geometry_blockers": surrogate_geometry_blockers,
        "landmarks_m": {key: value.tolist() for key, value in landmarks.items()},
        "bed_clearance": clearances,
        "static_torque": {
            key: value.tolist() for key, value in torque.items()
        },
        "current_model_allocation": {
            "force_norm_n": float(current_allocation["force_norm_n"]),
            "moment_abs_nm": abs(float(current_allocation["sagittal_wrench"][2])),
            "force_gate_margin_n": float(
                CUFF_TRANSLATIONAL_FORCE_GATE_N
                - current_allocation["force_norm_n"]
            ),
            "residual_nm": float(current_allocation["equality_residual_nm"]),
        },
        "conditional_without_soft_limit_allocation": {
            "force_norm_n": float(extended_allocation["force_norm_n"]),
            "moment_abs_nm": abs(float(extended_allocation["sagittal_wrench"][2])),
            "force_gate_margin_n": float(
                CUFF_TRANSLATIONAL_FORCE_GATE_N
                - extended_allocation["force_norm_n"]
            ),
            "residual_nm": float(extended_allocation["equality_residual_nm"]),
            "minimum_resultant_force_n": float(minimum_force["force_norm_n"]),
            "minimum_resultant_force_moment_abs_nm": abs(
                float(minimum_force["sagittal_wrench"][2])
            ),
        },
        "rigid_cuff_transmission": {
            "rank": int(np.linalg.matrix_rank(matrix)),
            "singular_values_raw_mixed_units": singular_values.tolist(),
            "condition_number_raw_mixed_units": float(
                singular_values[0] / singular_values[-1]
            ),
            "translational_force_only_rank": int(
                np.linalg.matrix_rank(translational_map)
            ),
            "translational_force_only_singular_values": (
                translational_singular_values.tolist()
            ),
        },
        "robot": robot_metrics,
        "collision_geometry": collision,
    }
    return row, None if ik.q_rad is None else ik.q_rad.copy()


def grid_values_deg() -> list[float]:
    """10-degree broad grid with 5-degree refinement above 80 degrees."""

    return sorted(
        set(float(value) for value in range(0, 121, 10))
        | set(float(value) for value in range(85, 121, 10))
    )


def flatten_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    collision = row["collision_geometry"] or {}
    robot = row["robot"]
    torque = row["static_torque"]
    conditional = row["conditional_without_soft_limit_allocation"]
    current = row["current_model_allocation"]
    transmission = row["rigid_cuff_transmission"]
    clearances = row["bed_clearance"]
    return {
        "q1_deg": row["q1_deg"],
        "q2_deg": row["q2_deg"],
        "absolute_shank_deg": row["absolute_shank_deg"],
        "current_rom_valid": row["current_rom_valid"],
        "current_soft_limit_active": row["current_soft_limit_active"],
        "current_rom_model_dominated": row["current_rom_model_dominated"],
        "classification": row["classification"],
        "mechanical_blockers": ";".join(row["mechanical_blockers"]),
        "intrinsic_mechanical_blockers": ";".join(
            row["intrinsic_mechanical_blockers"]
        ),
        "surrogate_geometry_blockers": ";".join(
            row["surrogate_geometry_blockers"]
        ),
        "thigh_bed_clearance_m": clearances["thigh_m"],
        "shank_bed_clearance_m": clearances["shank_m"],
        "sleeve_bed_clearance_m": clearances["sleeve_m"],
        "current_tau1_nm": torque["current_nm"][0],
        "current_tau2_nm": torque["current_nm"][1],
        "conditional_tau1_nm": torque["without_soft_limit_nm"][0],
        "conditional_tau2_nm": torque["without_soft_limit_nm"][1],
        "current_cuff_force_n": current["force_norm_n"],
        "current_cuff_moment_abs_nm": current["moment_abs_nm"],
        "conditional_cuff_force_n": conditional["force_norm_n"],
        "conditional_cuff_moment_abs_nm": conditional["moment_abs_nm"],
        "conditional_force_gate_margin_n": conditional["force_gate_margin_n"],
        "rigid_cuff_rank": transmission["rank"],
        "rigid_cuff_condition_raw": transmission[
            "condition_number_raw_mixed_units"
        ],
        "point_force_rank": transmission["translational_force_only_rank"],
        "ur10e_reachable": robot["reachable"],
        "ur10e_ik_residual": robot["ik_residual_norm"],
        "ur10e_joint_limit_margin_deg": robot.get(
            "minimum_joint_limit_margin_deg", math.nan
        ),
        "ur10e_jacobian_sigma_min": robot.get(
            "minimum_6d_jacobian_singular_value", math.nan
        ),
        "ur10e_jacobian_condition": robot.get(
            "jacobian_condition_number", math.nan
        ),
        "ur10e_peak_torque_fraction": robot.get(
            "peak_modeled_torque_limit_fraction", math.nan
        ),
        "robot_bed_min_distance_m": collision.get(
            "robot_bed_min_distance_m", math.nan
        ),
        "robot_human_min_distance_m": collision.get(
            "robot_human_min_distance_m", math.nan
        ),
        "adapter_human_min_distance_m": collision.get(
            "adapter_human_min_distance_m", math.nan
        ),
        "adapter_bed_min_distance_m": collision.get(
            "adapter_bed_min_distance_m", math.nan
        ),
        "robot_self_collision": bool(collision.get("robot_self_contact_pairs", [])),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        return {key: json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value
