"""Evaluation-only initial/task-goal CR12 cuff pose and limit audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


STAGE = Path(__file__).resolve().parents[1]
ASSEMBLY = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1"


def one_pose(plant, geometry, human, human_q, robot_q) -> dict:
    plant.data.qpos[plant.human_qpos_indices] = human_q
    plant.data.qpos[plant.robot_qpos_indices] = robot_q
    plant.data.qvel[:] = 0
    mujoco.mj_forward(plant.model, plant.data)
    desired = geometry.world_from_cuff(human_q, human)
    robot_site = plant.attachment_site_id
    human_site = plant.sleeve_site_id
    robot_position = plant.data.site_xpos[robot_site]
    human_position = plant.data.site_xpos[human_site]
    robot_rotation = plant.data.site_xmat[robot_site].reshape(3, 3)
    human_rotation = plant.data.site_xmat[human_site].reshape(3, 3)
    limits = plant._ik_robot.joint_limits_rad
    return {
        "robot_q_rad": np.asarray(robot_q).tolist(),
        "robot_to_desired_cuff_position_error_m": float(np.linalg.norm(robot_position - desired.translation)),
        "human_to_desired_cuff_position_error_m": float(np.linalg.norm(human_position - desired.translation)),
        "robot_to_human_cuff_position_error_m": float(np.linalg.norm(robot_position - human_position)),
        "robot_to_desired_cuff_rotation_error_rad": float(np.linalg.norm(
            Rotation.from_matrix(desired.rotation @ robot_rotation.T).as_rotvec())),
        "robot_to_human_cuff_rotation_error_rad": float(np.linalg.norm(
            Rotation.from_matrix(human_rotation @ robot_rotation.T).as_rotvec())),
        "robot_joint_limit_min_margin_rad": float(np.min(np.minimum(
            robot_q - limits[:, 0], limits[:, 1] - robot_q))),
        "zero_twist_by_static_evaluation": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    mapping = json.loads((ASSEMBLY / "OLD_TO_NEW_CASE_MAPPING.json").read_text())
    rows = []
    for item in mapping:
        if not item["revised_validity"]["valid"]:
            continue
        case = json.loads((ASSEMBLY / "cases" / f"{item['case_key']}.json").read_text())
        human, geometry, spec, _ = hidden_plant(case)
        plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
        initial = item["revised_validity"]["initial"]["robot_q_rad"]
        goal = item["revised_validity"]["task_goal"]["robot_q_rad"]
        rows.append({"case_key": item["case_key"],
                     "initial": one_pose(plant, geometry, human,
                                         np.asarray(spec.start_return_target_rad), np.asarray(initial)),
                     "task_goal": one_pose(plant, geometry, human,
                                           np.asarray(spec.outbound_goal_target_rad), np.asarray(goal))})
    max_position = max(v["robot_to_desired_cuff_position_error_m"]
                       for row in rows for v in (row["initial"], row["task_goal"]))
    max_rotation = max(v["robot_to_desired_cuff_rotation_error_rad"]
                       for row in rows for v in (row["initial"], row["task_goal"]))
    min_joint_margin = min(v["robot_joint_limit_min_margin_rad"]
                           for row in rows for v in (row["initial"], row["task_goal"]))
    result = {"schema": "rigid_table_v1_evaluation_only_cuff_pose_audit",
              "case_count": len(rows),
              "max_robot_to_desired_cuff_position_error_m": max_position,
              "max_robot_to_desired_cuff_rotation_error_rad": max_rotation,
              "minimum_robot_joint_limit_margin_rad": min_joint_margin,
              "scope": "initial and task goal static geometry only; no IK proof for all intermediate poses",
              "controller_input": False,
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, sort_keys=True))


if __name__ == "__main__":
    main()
