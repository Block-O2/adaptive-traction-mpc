"""Frozen generation-side conditional domain for fresh full-3D qualification.

This is never imported by the deployable controller.  All rejected proposals
are retained; no proposal is redrawn in response to controller outcomes.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from ..cr12_plant import Stage5CR12SensorBoundaryPlant, solve_cr12_stage5_ik
from .scenario import hidden_plant


TASK_FAMILIES = {
    "balanced": ((5., 10.), ((20., 35.), (42., 62.), (66., 84.))),
    "knee_dominant": ((6., 12.), ((18., 40.), (36., 70.), (60., 92.))),
    "hip_dominant": ((8., 12.), ((30., 30.), (55., 52.), (73., 74.))),
    "elevated_start": ((12., 20.), ((32., 43.), (52., 67.), (70., 90.))),
}
RANGE_CELLS = ("ordinary", "middle", "near_upper_current_rom")
REPLICATES = 2
MAX_PROPOSALS_PER_CELL = 30
MIN_STATIC_TRUE_CLEARANCE_M = 0.002


def _uniform(rng: np.random.Generator, lower: float, upper: float) -> float:
    return float(rng.uniform(lower, upper))


def draw_proposal(rng: np.random.Generator, *, family: str, range_index: int,
                  replicate: int, proposal_index: int) -> dict[str, Any]:
    start_base, goals = TASK_FAMILIES[family]
    start = [start_base[j] + _uniform(rng, -1.5, 1.5) for j in range(2)]
    goal = [goals[range_index][j] + _uniform(rng, -2.0, 2.0) for j in range(2)]
    waypoints = [start,
        [start[0] + 9., start[1] + 9.],
        [start[0] + 4., start[1] + 17.],
        [start[0] + 11., start[1] + 12.], start]
    return {
        "case_key": f"{family}_{RANGE_CELLS[range_index]}_r{replicate:02d}",
        "cell": {"family": family, "range": RANGE_CELLS[range_index],
                 "replicate": replicate},
        "proposal_index": proposal_index,
        "physical": {
            "height_m": _uniform(rng, 1.68, 1.76),
            "body_mass_kg": _uniform(rng, 67., 83.),
            "q_rest_deg": [_uniform(rng, 3., 8.), _uniform(rng, 7., 14.)],
            "passive_stiffness_nm_rad": [_uniform(rng, 7., 13.) for _ in range(2)],
            "passive_damping_nms_rad": [_uniform(rng, 3.5, 6.5) for _ in range(2)],
            "cuff_fraction_of_shank": _uniform(rng, 0.69, 0.75),
            "thigh_length_scale": _uniform(rng, 0.97, 1.03),
            "shank_length_scale": _uniform(rng, 0.97, 1.03),
            "thigh_mass_scale": _uniform(rng, 0.90, 1.10),
            "shank_mass_scale": _uniform(rng, 0.90, 1.10),
            "thigh_com_fraction": _uniform(rng, 0.40, 0.47),
            "shank_com_fraction": _uniform(rng, 0.40, 0.47),
            "thigh_inertia_radius_fraction": _uniform(rng, 0.27, 0.33),
            "shank_inertia_radius_fraction": _uniform(rng, 0.27, 0.33),
            "hip_translation_xz_m": [_uniform(rng, -0.010, 0.010),
                                       _uniform(rng, -0.006, 0.006)],
        },
        "task": {"start_deg": start, "goal_deg": goal,
                 "commissioning_waypoints_deg": waypoints},
    }


def _true_static_clearance(q_rad: np.ndarray, human: Any, geometry: Any) -> float:
    q1, q2 = np.asarray(q_rad, dtype=float)
    phi = q1 - q2
    # Stage-5 world_from_human already locates the hip at nominal z=0.062 m.
    # Adding the Stage-3 hip offset again would falsely accept bed collisions.
    hip = geometry.world_from_human.translation
    x_axis = geometry.world_from_human.rotation[:, 0]
    z_axis = geometry.world_from_human.rotation[:, 2]
    knee = hip + human.thigh_length_m * (math.cos(q1) * x_axis + math.sin(q1) * z_axis)
    ankle = knee + human.shank_length_m * (math.cos(phi) * x_axis + math.sin(phi) * z_axis)
    return float(min(knee[2], ankle[2]) - SHANK_RADIUS_M - BED_HEIGHT_M)


def mechanical_screen(case: dict[str, Any]) -> dict[str, Any]:
    """Arm-independent, pre-outcome static mechanics conditioning only."""
    try:
        human, geometry, spec, commissioning = hidden_plant(case)
        nodes = [np.asarray(spec.start_return_target_rad),
                 np.asarray(spec.outbound_goal_target_rad)]
        for left, right in ((nodes[0], nodes[1]), (nodes[1], nodes[0])):
            nodes.extend(left + t * (right - left) for t in np.linspace(0., 1., 21))
        clearances = [_true_static_clearance(q, human, geometry) for q in nodes]
        minimum = min(clearances)
        if minimum < MIN_STATIC_TRUE_CLEARANCE_M:
            return {"accepted": False, "reason": "STATIC_TRUE_SHANK_BED_CLEARANCE",
                    "minimum_static_true_clearance_m": minimum}
        plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        plant.reset(np.asarray(spec.start_return_target_rad))
        if any({int(plant.data.contact[i].geom1), int(plant.data.contact[i].geom2)}
               == {int(plant.bed_geom_id), int(plant.model.geom("shank_geom").id)}
               for i in range(plant.data.ncon)):
            return {"accepted": False, "reason": "START_SHANK_BED_CONTACT",
                    "minimum_static_true_clearance_m": minimum}
        robot_previous = plant.data.qpos[plant.robot_qpos_indices].copy()
        for q in (nodes[1], nodes[0]):
            target = geometry.base_from_end_effector_target(q, human)
            robot_previous = solve_cr12_stage5_ik(plant._ik_robot, target,
                                                 previous_q_rad=robot_previous)
        return {"accepted": True, "reason": "STATIC_MECHANICS_SCREEN_ACCEPTED",
                "minimum_static_true_clearance_m": minimum}
    except (ValueError, RuntimeError) as error:
        return {"accepted": False, "reason": f"STATIC_OR_IK:{type(error).__name__}:{error}"}


def generate_cases(seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Balanced 4 x 3 x 2 accepted cells; fixed max proposals, no outcome input."""
    cases, proposals = [], []
    for family in TASK_FAMILIES:
        for range_index in range(len(RANGE_CELLS)):
            for replicate in range(1, REPLICATES + 1):
                cell_seed = int.from_bytes(hashlib.sha256(
                    f"fresh_full3d_v1:{seed}:{family}:{range_index}:{replicate}".encode()
                ).digest()[:8], "big")
                rng = np.random.default_rng(cell_seed)
                accepted = None
                for proposal_index in range(1, MAX_PROPOSALS_PER_CELL + 1):
                    case = draw_proposal(rng, family=family,
                        range_index=range_index, replicate=replicate,
                        proposal_index=proposal_index)
                    screen = mechanical_screen(case)
                    proposals.append({"case": case, "screen": screen})
                    if screen["accepted"]:
                        accepted = case
                        break
                if accepted is None:
                    raise RuntimeError(f"pre-registered cell has no mechanically accepted proposal: {family}/{range_index}/{replicate}")
                cases.append(accepted)
    assert len(cases) == 24
    return cases, proposals


def canonical_json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()
