"""Versioned generation/evaluation-only rigid-table assembly checks.

The historical fresh_qualification_v1 generator and screens are intentionally
not edited.  Physical truth reaches only the simulator builder and this screen.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    BED_HEIGHT_M, SHANK_RADIUS_M, THIGH_RADIUS_M,
)

from ..cr12_plant import Stage5CR12SensorBoundaryPlant, solve_cr12_stage5_ik
from ..geometry import STAGE5_GEOMETRY
from ..fresh_qualification_v1.scenario import hidden_plant


# Numerical classification is separate from physical setup clearance.  The
# 0.1 mm design gap is a pre-outcome installation rule, not a MuJoCo contact
# tolerance or a new controller constraint; its solver check is archived.
NUMERICAL_PENETRATION_TOLERANCE_M = 1.0e-9
MIN_PROXIMAL_GAP_M = 1.0e-4
MAX_HIP_UPWARD_SHIFT_M = 0.006


def proximal_gap_m(case: Mapping[str, Any]) -> float:
    nominal_hip_z = float(STAGE5_GEOMETRY.world_from_human.translation[2])
    hidden_shift_z = float(case["physical"]["hip_translation_xz_m"][1])
    return nominal_hip_z + hidden_shift_z - THIGH_RADIUS_M - BED_HEIGHT_M


def repaired_counterpart(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mirror old illegal downward installation above the fixed table.

    This is a *development counterpart*, not a matched physical-state branch
    or a fresh randomized draw.  Mirroring retains magnitude of installation
    variation without mapping every illegal location onto one boundary point.
    Existing legal placements at or above the design gap are bitwise unchanged.
    """
    revised = deepcopy(dict(case))
    old_gap = proximal_gap_m(case)
    if old_gap >= MIN_PROXIMAL_GAP_M:
        new_gap = old_gap
        rule = "unchanged_legal_placement"
    elif old_gap < -NUMERICAL_PENETRATION_TOLERANCE_M:
        new_gap = max(-old_gap, MIN_PROXIMAL_GAP_M)
        rule = "reflect_illegal_downward_installation"
    else:
        new_gap = MIN_PROXIMAL_GAP_M
        rule = "replace_tangency_with_positive_installation_gap"
    if new_gap > MAX_HIP_UPWARD_SHIFT_M + NUMERICAL_PENETRATION_TOLERANCE_M:
        raise ValueError("counterpart exceeds registered 6 mm upward placement span")
    nominal_gap = (float(STAGE5_GEOMETRY.world_from_human.translation[2])
                   - THIGH_RADIUS_M - BED_HEIGHT_M)
    new_shift = new_gap - nominal_gap
    if rule != "unchanged_legal_placement":
        revised["physical"]["hip_translation_xz_m"][1] = float(new_shift)
    else:
        new_shift = float(case["physical"]["hip_translation_xz_m"][1])
    return revised, {
        "rule": rule,
        "old_proximal_gap_m": old_gap,
        "new_proximal_gap_m": proximal_gap_m(revised),
        "old_hidden_hip_shift_z_m": float(case["physical"]["hip_translation_xz_m"][1]),
        "new_hidden_hip_shift_z_m": float(new_shift),
        "changed_fields": ([] if rule == "unchanged_legal_placement" else
                           ["physical.hip_translation_xz_m[1]", "derived_world_from_human",
                            "recomputed_CR12_initial_IK_and_cuff_initialization"]),
    }


def _capsule_axis_gap(q_rad: np.ndarray, human: Any, geometry: Any) -> dict[str, float]:
    q1, q2 = np.asarray(q_rad, dtype=float)
    hip = geometry.world_from_human.translation
    x_axis = geometry.world_from_human.rotation[:, 0]
    z_axis = geometry.world_from_human.rotation[:, 2]
    knee = hip + human.thigh_length_m * (math.cos(q1) * x_axis + math.sin(q1) * z_axis)
    ankle = knee + human.shank_length_m * (
        math.cos(q1 - q2) * x_axis + math.sin(q1 - q2) * z_axis)
    return {
        "thigh_m": float(min(hip[2], knee[2]) - THIGH_RADIUS_M - BED_HEIGHT_M),
        "shank_m": float(min(knee[2], ankle[2]) - SHANK_RADIUS_M - BED_HEIGHT_M),
    }


def _distance(plant: Stage5CR12SensorBoundaryPlant, first: list[int],
              second: list[int]) -> dict[str, Any]:
    minimum = math.inf
    nearest: tuple[str, str] | None = None
    segment = np.zeros(6)
    for left in first:
        for right in second:
            if left == right:
                continue
            value = float(mujoco.mj_geomDistance(
                plant.model, plant.data, left, right, 10.0, segment))
            if value < minimum:
                minimum = value
                nearest = (plant.model.geom(left).name, plant.model.geom(right).name)
    return {"minimum_signed_distance_m": minimum, "nearest_pair": nearest}


def _initial_geometry(plant: Stage5CR12SensorBoundaryPlant) -> dict[str, Any]:
    model = plant.model
    bed = [plant.bed_geom_id]
    thigh = [model.geom("thigh_geom").id]
    shank = [model.geom("shank_geom").id]
    sleeve = [model.geom("sleeve_geom").id]
    cuff_bar = [model.geom("stage5_cuff_bar_geom").id]
    adapter = [model.geom("cuff_adapter_geom").id]
    robot_geoms = [i for i in sorted(plant.robot_collision_geom_ids)
                   if model.geom(i).name != "cuff_adapter_geom"]
    mount = [i for i in robot_geoms
             if model.body(int(model.geom_bodyid[i])).name
             in {"xMateCR12_base", "xMateCR12_link1"}]
    arm = [i for i in robot_geoms if i not in mount]
    names = ["thigh", "shank", "sleeve", "cuff_bar", "adapter",
             "articulated_robot", "fixed_robot_mount"]
    groups = [thigh, shank, sleeve, cuff_bar, adapter, arm, mount]
    distances = {name: _distance(plant, group, bed)
                 for name, group in zip(names, groups, strict=True)}
    distances["articulated_robot_to_human"] = _distance(plant, arm, thigh + shank)
    distances["adapter_to_human"] = _distance(plant, adapter, thigh + shank)
    contacts = []
    for i in range(plant.data.ncon):
        contact = plant.data.contact[i]
        contacts.append({
            "pair": [model.geom(int(contact.geom1)).name,
                     model.geom(int(contact.geom2)).name],
            "signed_distance_m": float(contact.dist),
        })
    collision_inventory = {}
    for name, group in zip(names, groups, strict=True):
        collision_inventory[name] = [{
            "geom": model.geom(i).name,
            "body": model.body(int(model.geom_bodyid[i])).name,
            "contype": int(model.geom_contype[i]),
            "conaffinity": int(model.geom_conaffinity[i]),
        } for i in group]
    collision_inventory["bed"] = [{
        "geom": model.geom(plant.bed_geom_id).name,
        "type": "infinite_collision_plane_with_finite_visual_size",
        "contype": int(model.geom_contype[plant.bed_geom_id]),
        "conaffinity": int(model.geom_conaffinity[plant.bed_geom_id]),
    }]
    return {"distances": distances, "contacts": contacts,
            "collision_inventory": collision_inventory,
            "robot_q_rad": plant.data.qpos[plant.robot_qpos_indices].tolist()}


def _forbidden_initial_overlap(geometry_record: Mapping[str, Any]) -> str | None:
    distances = geometry_record["distances"]
    for key in ("thigh", "shank", "sleeve", "cuff_bar", "adapter",
                "articulated_robot", "articulated_robot_to_human",
                "adapter_to_human"):
        if distances[key]["minimum_signed_distance_m"] < -NUMERICAL_PENETRATION_TOLERANCE_M:
            return key
    return None


def assess_assembly(case: Mapping[str, Any], *, verify_robot: bool = True) -> dict[str, Any]:
    """Check the entire initial physical assembly before any controller run.

    A failed IK is called an initialization-search failure, never proof of
    physical infeasibility.  Truth is used here only for evaluation/generation.
    """
    result: dict[str, Any] = {
        "schema": "rigid_table_assembly_v1",
        "case_key": str(case["case_key"]),
        "proximal_gap_m": proximal_gap_m(case),
        "minimum_required_gap_m": MIN_PROXIMAL_GAP_M,
        "numerical_penetration_tolerance_m": NUMERICAL_PENETRATION_TOLERANCE_M,
    }
    if result["proximal_gap_m"] < MIN_PROXIMAL_GAP_M - NUMERICAL_PENETRATION_TOLERANCE_M:
        result.update(valid=False, category="INVALID_FIXED_GEOMETRY",
                      reason="proximal thigh capsule lacks positive rigid-table installation gap")
        return result
    try:
        human, geometry, spec, commissioning = hidden_plant(case)
        start = np.asarray(spec.start_return_target_rad)
        goal = np.asarray(spec.outbound_goal_target_rad)
        task_nodes = [start, goal]
        for left, right in ((start, goal), (goal, start)):
            task_nodes.extend(left + t * (right - left) for t in np.linspace(0., 1., 21))
        all_nodes = [*task_nodes, *commissioning]
        task_gaps = [_capsule_axis_gap(q, human, geometry) for q in task_nodes]
        all_gaps = [_capsule_axis_gap(q, human, geometry) for q in all_nodes]
        result["minimum_static_thigh_gap_m"] = min(row["thigh_m"] for row in all_gaps)
        result["minimum_static_shank_gap_m"] = min(row["shank_m"] for row in task_gaps)
        result["minimum_commissioning_shank_gap_m"] = min(
            _capsule_axis_gap(q, human, geometry)["shank_m"] for q in commissioning)
        if result["minimum_static_thigh_gap_m"] < -NUMERICAL_PENETRATION_TOLERANCE_M:
            result.update(valid=False, category="INVALID_FIXED_GEOMETRY",
                          reason="thigh capsule penetrates table on registered pose family")
            return result
        # Historical 2 mm shank screen is preserved as a pre-outcome feasibility
        # condition; moving segment contact during physical motion is monitored.
        if result["minimum_static_shank_gap_m"] < 0.002:
            result.update(valid=False, category="INVALID_REGISTERED_SHANK_GEOMETRY",
                          reason="registered static shank screen below 2 mm")
            return result
        if not verify_robot:
            result.update(valid=True, category="GEOMETRY_ONLY_VALID", reason="robot not evaluated")
            return result
        plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        plant.reset(np.asarray(spec.start_return_target_rad))
        result["initial"] = _initial_geometry(plant)
        bad_initial = _forbidden_initial_overlap(result["initial"])
        if bad_initial is not None:
            result.update(valid=False, category="INVALID_FIXED_GEOMETRY",
                          reason=f"MuJoCo reset overlap: {bad_initial}")
            return result
        robot_previous = plant.data.qpos[plant.robot_qpos_indices].copy()
        result["robot_initial_joint_limit_margin_rad"] = float(np.min(np.minimum(
            robot_previous - plant._ik_robot.joint_limits_rad[:, 0],
            plant._ik_robot.joint_limits_rad[:, 1] - robot_previous)))
        for q in (goal, start):
            target = geometry.base_from_end_effector_target(q, human)
            robot_previous = solve_cr12_stage5_ik(
                plant._ik_robot, target, previous_q_rad=robot_previous)
            if q is goal:
                plant.data.qpos[plant.human_qpos_indices] = goal
                plant.data.qpos[plant.robot_qpos_indices] = robot_previous
                mujoco.mj_forward(plant.model, plant.data)
                result["task_goal"] = _initial_geometry(plant)
                bad_goal = _forbidden_initial_overlap(result["task_goal"])
                if bad_goal is not None:
                    result.update(valid=False, category="INVALID_ENDPOINT_ASSEMBLY",
                                  reason=f"MuJoCo task-goal overlap: {bad_goal}")
                    return result
        result.update(valid=True, category="ASSEMBLY_VALID",
                      reason="positive fixed clearance; static limb and reset/IK checks passed")
    except (ValueError, RuntimeError) as error:
        result.update(valid=False, category="INITIALIZATION_OR_IK_SEARCH_FAILED",
                      reason=f"{type(error).__name__}: {error}")
    return result
