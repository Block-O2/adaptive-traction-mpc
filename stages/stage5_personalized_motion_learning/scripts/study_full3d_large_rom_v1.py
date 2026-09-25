#!/usr/bin/env python3
"""Frozen kinematic/mechanics map for the requested 120--130 degree region."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage3.coupled import BED_HEIGHT_M, SHANK_RADIUS_M
from traction_mpc_stage5.cr12_plant import solve_cr12_stage5_ik
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import nominal_control_model
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN


def run(config_path: Path, output_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["status"] != "FROZEN_BEFORE_EXECUTION":
        raise ValueError("large-ROM study was not frozen")
    robot = CR12TorqueRobot()
    model = nominal_control_model()
    rows = []
    previous = None
    for hip_deg in config["hip_flexion_deg"]:
        for knee_deg in config["knee_flexion_deg"]:
            q = np.radians([hip_deg, knee_deg])
            phi = q[0] - q[1]
            hip_z = float(STAGE5_GEOMETRY.world_from_human.translation[2])
            knee_z = hip_z + STAGE5_HUMAN.thigh_length_m * np.sin(q[0])
            ankle_z = knee_z + STAGE5_HUMAN.shank_length_m * np.sin(phi)
            clearance = float(min(knee_z, ankle_z) - SHANK_RADIUS_M - BED_HEIGHT_M)
            inside_rom = bool(
                np.all(q >= np.asarray(STAGE5_HUMAN.q_min_rad))
                and np.all(q <= np.asarray(STAGE5_HUMAN.q_max_rad))
            )
            target = STAGE5_GEOMETRY.base_from_end_effector_target(q, STAGE5_HUMAN)
            ik_error = None
            robot_q = None
            sigma_min = None
            try:
                robot_q = solve_cr12_stage5_ik(robot, target, previous_q_rad=previous)
            except (RuntimeError, ValueError):
                try:
                    robot_q = solve_cr12_stage5_ik(robot, target)
                except (RuntimeError, ValueError) as error:
                    ik_error = str(error)
            if robot_q is not None:
                previous = robot_q.copy()
                robot.set_configuration(robot_q)
                sigma_min = float(np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)[-1])
            static_action = model.inverse_dynamics(q, np.zeros(2), np.zeros(2))
            allocation = model.allocate_generalized_action(static_action, q)
            mechanically_reachable = bool(robot_q is not None and clearance >= 0.0)
            if inside_rom and mechanically_reachable:
                classification = "REGISTERED_KINEMATIC_CANDIDATE_ONLY"
            elif mechanically_reachable:
                classification = "REACHABLE_AND_CLEAR_BUT_OUTSIDE_REGISTERED_HUMAN_ROM"
            elif clearance < 0.0:
                classification = "BED_GEOMETRY_INFEASIBLE_IN_CURRENT_PLACEMENT"
            else:
                classification = "CR12_FULL_POSE_IK_NOT_FOUND"
            rows.append({
                "q_deg": [hip_deg, knee_deg],
                "inside_original_human_rom": inside_rom,
                "clearance_m": clearance,
                "cr12_ik_found": robot_q is not None,
                "cr12_ik_error": ik_error,
                "cr12_q_deg": None if robot_q is None else np.degrees(robot_q).tolist(),
                "cr12_jacobian_minimum_singular_value": sigma_min,
                "current_model_static_generalized_action_nm": static_action.tolist(),
                "current_model_static_allocated_force_n": allocation["force_norm_n"],
                "current_model_static_allocated_moment_nm": abs(allocation["my_nm"]),
                "classification": classification,
            })
    result = {
        "schema": config["schema"],
        "evidence_category": config["evidence_category"],
        "coordinate_convention": {
            "q1": "hip flexion from +X toward +Z",
            "q2": "relative knee flexion; shank absolute angle phi=q1-q2",
        },
        "original_human_rom_deg": [[0.0, 80.0], [0.0, 100.0]],
        "closed_loop_executed": False,
        "plant_limits_changed": False,
        "rows": rows,
        "counts": {
            label: sum(row["classification"] == label for row in rows)
            for label in sorted({row["classification"] for row in rows})
        },
        "interpretation": (
            "Passing IK and clearance outside 100 deg only removes two kinematic obstacles. "
            "It does not validate anatomy, passive mechanics, the Human joint model, cuff "
            "pressure, dynamic torque, or closed-loop control, and it does not authorize a ROM change."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.config, args.output)
    print(json.dumps(result["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
