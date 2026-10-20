"""Mechanical and execution-boundary validation for the Stage-5 CR12 baseline."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .config import STAGE5_CONFIG, STAGE5_ROOT
from .cr12_plant import Stage5CR12SpringDamperPlant, solve_cr12_stage5_ik
from .cr12_robot import (
    CR12_ACTUATOR_NAMES,
    CR12_BODY_NAMES,
    CR12_JOINT_NAMES,
    CR12_MODEL_PATH,
    CR12_VELOCITY_LIMITS_RAD_S,
    CR12_VENDOR_ROOT,
    CR12TorqueRobot,
)
from .geometry import STAGE5_GEOMETRY
from .human import STAGE5_HUMAN
from .task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


OFFICIAL_REPOSITORY = "https://github.com/RokaeRobot/rokae_ros2.git"
OFFICIAL_COMMIT = "d6a508c38513d4c39b2f10f14275d0e26df7fb43"
OFFICIAL_JOINT_ORIGINS_M = np.array(
    [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.35],
        [0.0, 0.0, 0.76],
        [0.0, 0.0, 0.54],
        [0.0, -0.15, 0.0],
        [0.0, 0.0, 0.127],
    ]
)
OFFICIAL_JOINT_AXES = np.array(
    [
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)
OFFICIAL_JOINT_LIMITS_RAD = np.array(
    [
        [-6.2832, 6.2832],
        [-2.9671, 2.9671],
        [-6.2832, 6.2832],
        [-6.2832, 6.2832],
        [-6.2832, 6.2832],
        [-6.2832, 6.2832],
    ]
)
OFFICIAL_EFFORT_LIMITS_NM = np.array([436.0, 436.0, 194.0, 102.0, 66.0, 66.0])
OFFICIAL_VELOCITY_LIMITS_RAD_S = CR12_VELOCITY_LIMITS_RAD_S.copy()
OFFICIAL_LINK_MASSES_KG = np.array([9.762, 13.748, 4.659, 4.015, 2.34, 1.142])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _independent_urdf_fk(q_rad: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rotation = np.eye(3)
    translation = np.zeros(3)
    for origin, axis, angle in zip(
        OFFICIAL_JOINT_ORIGINS_M, OFFICIAL_JOINT_AXES, q_rad, strict=True
    ):
        translation = translation + rotation @ origin
        rotation = rotation @ Rotation.from_rotvec(axis * angle).as_matrix()
    return rotation, translation


def _minimum_geom_distance(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    first: list[int],
    second: list[int],
) -> tuple[float, tuple[str, str] | None]:
    minimum = math.inf
    pair = None
    segment = np.zeros(6)
    for geom1 in first:
        for geom2 in second:
            if geom1 == geom2:
                continue
            distance = float(
                mujoco.mj_geomDistance(model, data, geom1, geom2, 10.0, segment)
            )
            if distance < minimum:
                minimum = distance
                pair = (model.geom(geom1).name, model.geom(geom2).name)
    return minimum, pair


def _source_audit() -> dict[str, object]:
    urdf_path = CR12_VENDOR_ROOT / "xMateCR12.urdf.xacro"
    root = ET.parse(urdf_path).getroot()
    joints = [root.find(f"joint[@name='joint{index}']") for index in range(1, 7)]
    if any(joint is None for joint in joints):
        raise RuntimeError("vendored official CR12 URDF does not contain joint1..joint6")
    mesh_paths = sorted((CR12_VENDOR_ROOT / "meshes").glob("*.stl"))
    return {
        "official_repository": OFFICIAL_REPOSITORY,
        "official_commit": OFFICIAL_COMMIT,
        "urdf_path": str(urdf_path.relative_to(STAGE5_ROOT)),
        "urdf_sha256": _sha256(urdf_path),
        "srdf_sha256": _sha256(CR12_VENDOR_ROOT / "xMateCR12.srdf"),
        "mesh_count": len(mesh_paths),
        "mesh_sha256": {path.name: _sha256(path) for path in mesh_paths},
        "joint_order": list(CR12_JOINT_NAMES),
        "joint_origins_m": OFFICIAL_JOINT_ORIGINS_M.tolist(),
        "joint_axes": OFFICIAL_JOINT_AXES.tolist(),
        "joint_limits_rad": OFFICIAL_JOINT_LIMITS_RAD.tolist(),
        "effort_limits_nm": OFFICIAL_EFFORT_LIMITS_NM.tolist(),
        "velocity_limits_rad_s": OFFICIAL_VELOCITY_LIMITS_RAD_S.tolist(),
        "link_masses_kg": OFFICIAL_LINK_MASSES_KG.tolist(),
        "official_urdf_separate_flange_or_tcp_frame": False,
        "official_urdf_tip_link": "xMateCR12_link6",
        "lab_end_effector_cad_status": (
            "audited separately; supplied Onshape ROS/STL export contains only "
            "the CR12 exterior and is not used by this provisional-cuff baseline"
        ),
    }


def run_cr12_mechanical_validation(output_dir: Path) -> dict[str, object]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite CR12 validation output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    robot = CR12TorqueRobot()
    plant = Stage5CR12SpringDamperPlant()
    official_fk_checks = []
    representative_rows = []
    previous = None
    postures_deg = list(STAGE5_CONFIG["representative_postures_deg"])
    required = [
        list(np.degrees(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)),
        list(np.degrees(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad)),
    ]
    for posture in required:
        if posture not in postures_deg:
            postures_deg.append(posture)

    for posture_deg in postures_deg:
        human_q = np.radians(posture_deg)
        target = STAGE5_GEOMETRY.base_from_end_effector_target(human_q, STAGE5_HUMAN)
        solution = solve_cr12_stage5_ik(
            robot, target, previous_q_rad=previous
        )
        robot.set_configuration(solution)
        actual = robot.attachment_pose()
        position_error = float(np.linalg.norm(actual.translation - target.translation))
        rotation_error = float(
            np.linalg.norm(
                Rotation.from_matrix(target.rotation @ actual.rotation.T).as_rotvec()
            )
        )
        flange_jacobian = robot.attachment_jacobian()
        cuff_jacobian = robot.rigid_offset_jacobian(
            STAGE5_GEOMETRY.end_effector_from_cuff.translation
        )
        flange_singular_values = np.linalg.svd(
            flange_jacobian, compute_uv=False
        )
        singular_values = np.linalg.svd(cuff_jacobian, compute_uv=False)
        joint_margin = np.minimum(
            solution - robot.joint_limits_rad[:, 0],
            robot.joint_limits_rad[:, 1] - solution,
        )

        urdf_rotation, urdf_translation = _independent_urdf_fk(solution)
        official_fk_checks.append(
            {
                "robot_q_rad": solution.tolist(),
                "position_error_m": float(
                    np.linalg.norm(actual.translation - urdf_translation)
                ),
                "rotation_error_rad": float(
                    np.linalg.norm(
                        Rotation.from_matrix(
                            urdf_rotation @ actual.rotation.T
                        ).as_rotvec()
                    )
                ),
            }
        )

        mujoco.mj_resetData(plant.model, plant.data)
        plant.data.qpos[plant.human_qpos_indices] = human_q
        plant.data.qpos[plant.robot_qpos_indices] = solution
        plant.data.eq_active[plant.weld_id] = 0
        mujoco.mj_forward(plant.model, plant.data)
        arm_geoms = [
            geom_id
            for geom_id in plant.robot_collision_geom_ids
            if plant.model.geom(geom_id).name not in {"cuff_adapter_geom"}
        ]
        articulated_geoms = [
            geom_id
            for geom_id in arm_geoms
            if plant.model.body(int(plant.model.geom_bodyid[geom_id])).name
            not in {"xMateCR12_base", "xMateCR12_link1"}
        ]
        human_clearance, human_pair = _minimum_geom_distance(
            plant.model, plant.data, arm_geoms, list(plant.human_geom_ids)
        )
        bed_clearance, bed_pair = _minimum_geom_distance(
            plant.model, plant.data, articulated_geoms, [plant.bed_geom_id]
        )
        adapter_geom_id = plant.model.geom("cuff_adapter_geom").id
        adapter_human_clearance, adapter_human_pair = _minimum_geom_distance(
            plant.model,
            plant.data,
            [adapter_geom_id],
            list(plant.human_geom_ids),
        )
        adapter_bed_clearance, adapter_bed_pair = _minimum_geom_distance(
            plant.model, plant.data, [adapter_geom_id], [plant.bed_geom_id]
        )
        active_contacts = list(plant.contact_pairs())
        robot_geom_names = {
            plant.model.geom(geom_id).name
            for geom_id in plant.robot_collision_geom_ids
        }
        active_robot_contacts = [
            pair
            for pair in active_contacts
            if pair[0] in robot_geom_names or pair[1] in robot_geom_names
        ]
        representative_rows.append(
            {
                "human_q_deg": list(posture_deg),
                "robot_q_deg": np.degrees(solution).tolist(),
                "position_error_m": position_error,
                "rotation_error_rad": rotation_error,
                "flange_jacobian_shape": list(flange_jacobian.shape),
                "jacobian_shape": list(flange_jacobian.shape),
                "jacobian_rank": int(np.linalg.matrix_rank(flange_jacobian)),
                "minimum_jacobian_singular_value": float(
                    flange_singular_values[-1]
                ),
                "jacobian_condition_number": float(
                    flange_singular_values[0] / flange_singular_values[-1]
                ),
                "cuff_jacobian_shape": list(cuff_jacobian.shape),
                "cuff_jacobian_rank": int(np.linalg.matrix_rank(cuff_jacobian)),
                "minimum_cuff_jacobian_singular_value": float(singular_values[-1]),
                "cuff_jacobian_condition_number": float(
                    singular_values[0] / singular_values[-1]
                ),
                "minimum_joint_limit_margin_deg": float(np.degrees(np.min(joint_margin))),
                "minimum_robot_arm_to_human_clearance_m": human_clearance,
                "closest_robot_human_pair": human_pair,
                "minimum_articulated_robot_to_bed_clearance_m": bed_clearance,
                "closest_robot_bed_pair": bed_pair,
                "provisional_adapter_to_human_clearance_m": (
                    adapter_human_clearance
                ),
                "closest_adapter_human_pair": adapter_human_pair,
                "provisional_adapter_to_bed_clearance_m": adapter_bed_clearance,
                "closest_adapter_bed_pair": adapter_bed_pair,
                "active_contact_pairs": [list(pair) for pair in active_contacts],
                "active_robot_contact_pairs": [
                    list(pair) for pair in active_robot_contacts
                ],
            }
        )
        previous = solution.copy()

    start_observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    start_robot_q = start_observation.robot_q_rad.copy()
    cuff_site_id = plant.attachment_site_id
    flange_site_id = plant.flange_site_id
    cuff_site_local_rotation = Rotation.from_quat(
        plant.model.site_quat[cuff_site_id][[1, 2, 3, 0]]
    ).as_matrix()
    frame_translation_error = float(
        np.linalg.norm(
            plant.model.site_pos[cuff_site_id]
            - STAGE5_GEOMETRY.end_effector_from_cuff.translation
        )
    )
    frame_rotation_error = float(
        np.linalg.norm(
            Rotation.from_matrix(
                STAGE5_GEOMETRY.end_effector_from_cuff.rotation
                @ cuff_site_local_rotation.T
            ).as_rotvec()
        )
    )

    cuff_jacobian = plant.robot_attachment_jacobian()
    robot.set_configuration(start_robot_q)
    independent_cuff_jacobian_base = robot.rigid_offset_jacobian(
        STAGE5_GEOMETRY.end_effector_from_cuff.translation
    )
    world_from_base_rotation = STAGE5_GEOMETRY.world_from_base.rotation
    rotate_twist = np.block(
        [
            [world_from_base_rotation, np.zeros((3, 3))],
            [np.zeros((3, 3)), world_from_base_rotation],
        ]
    )
    independent_cuff_jacobian_world = (
        rotate_twist @ independent_cuff_jacobian_base
    )
    cuff_jacobian_model_error = float(
        np.max(np.abs(cuff_jacobian - independent_cuff_jacobian_world))
    )
    finite_difference_direction = np.array([0.2, -0.1, 0.15, -0.05, 0.1, -0.2])
    finite_difference_epsilon_s = 1.0e-7
    analytic_cuff_twist = cuff_jacobian @ finite_difference_direction
    plant.data.qpos[plant.robot_qpos_indices] = (
        start_robot_q + finite_difference_epsilon_s * finite_difference_direction
    )
    mujoco.mj_forward(plant.model, plant.data)
    cuff_position_plus = plant.data.site_xpos[cuff_site_id].copy()
    cuff_rotation_plus = plant.data.site_xmat[cuff_site_id].reshape(3, 3).copy()
    plant.data.qpos[plant.robot_qpos_indices] = (
        start_robot_q - finite_difference_epsilon_s * finite_difference_direction
    )
    mujoco.mj_forward(plant.model, plant.data)
    cuff_position_minus = plant.data.site_xpos[cuff_site_id].copy()
    cuff_rotation_minus = plant.data.site_xmat[cuff_site_id].reshape(3, 3).copy()
    finite_difference_cuff_twist = np.r_[
        (cuff_position_plus - cuff_position_minus)
        / (2.0 * finite_difference_epsilon_s),
        Rotation.from_matrix(cuff_rotation_plus @ cuff_rotation_minus.T).as_rotvec()
        / (2.0 * finite_difference_epsilon_s),
    ]
    cuff_jacobian_finite_difference_error = float(
        np.max(np.abs(analytic_cuff_twist - finite_difference_cuff_twist))
    )

    plant.data.qpos[plant.robot_qpos_indices] = start_robot_q
    perturbation = np.zeros(6)
    perturbation[0] = 1.0e-4
    plant.data.qpos[plant.robot_qpos_indices] = start_robot_q + perturbation
    perturbed_observation = plant.observe()
    perturbed_interface = plant._evaluate_current_interface()
    human_site_position = plant.data.site_xpos[plant.sleeve_site_id].copy()
    robot_site_position = plant.data.site_xpos[plant.attachment_site_id].copy()
    common_origin_moment_balance = (
        perturbed_interface.human_wrench_world[3:]
        + np.cross(
            human_site_position,
            perturbed_interface.human_wrench_world[:3],
        )
        + perturbed_interface.robot_wrench_world[3:]
        + np.cross(
            robot_site_position,
            perturbed_interface.robot_wrench_world[:3],
        )
    )
    force_balance = (
        perturbed_interface.human_wrench_world[:3]
        + perturbed_interface.robot_wrench_world[:3]
    )

    start_observation = plant.reset(
        np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    )
    finite_difference = robot.finite_difference_jacobian_check(
        np.radians([-120.0, -64.0, 128.0, -30.0, -100.0, 89.0]),
        np.array([0.2, -0.1, 0.15, -0.05, 0.1, -0.2]),
    )
    current_pose = plant.observe()
    preview = plant.preview_executable_command(
        current_pose.attachment_position_m,
        np.zeros(3),
        current_pose.attachment_rotation_matrix,
        np.zeros(3),
        np.zeros(6),
    )
    inertia_positive = bool(
        np.all(np.isfinite(robot.model.body_inertia))
        and np.all(robot.model.body_inertia[2:] > 0.0)
        and np.allclose(robot.model.body_mass[2:], OFFICIAL_LINK_MASSES_KG)
    )
    summary = {
        "schema": "stage5_cr12_mechanical_validation_v0",
        "evidence_category": "smoke_engineering_validation_only",
        "classification": "CR12-B",
        "source_audit": _source_audit(),
        "model": {
            "model_path": str(CR12_MODEL_PATH.relative_to(STAGE5_ROOT)),
            "model_sha256": _sha256(CR12_MODEL_PATH),
            "nq": robot.model.nq,
            "nv": robot.model.nv,
            "nu": robot.model.nu,
            "joint_order": list(CR12_JOINT_NAMES),
            "actuator_order": list(CR12_ACTUATOR_NAMES),
            "body_order": list(CR12_BODY_NAMES),
            "joint_axes_match_official": bool(
                np.allclose(robot.model.jnt_axis[robot.joint_ids], OFFICIAL_JOINT_AXES)
            ),
            "joint_limits_match_official": bool(
                np.allclose(robot.joint_limits_rad, OFFICIAL_JOINT_LIMITS_RAD)
            ),
            "torque_limits_match_official_effort_limits": bool(
                np.allclose(robot.torque_limits_nm, OFFICIAL_EFFORT_LIMITS_NM)
            ),
            "velocity_limits_match_official": bool(
                np.allclose(
                    robot.velocity_limits_rad_s, OFFICIAL_VELOCITY_LIMITS_RAD_S
                )
            ),
            "moving_link_inertials_finite_positive_and_masses_match": inertia_positive,
            "moving_link_mass_sum_kg": float(np.sum(robot.model.body_mass[2:])),
            "mujoco_armature_kg_m2": robot.model.dof_armature[robot.dof_indices].tolist(),
            "armature_is_official_hardware_parameter": False,
        },
        "fk_against_independent_official_urdf_chain": official_fk_checks,
        "finite_difference_jacobian": {
            "max_abs_error": finite_difference.max_abs_error,
            "analytic_twist": finite_difference.analytic_twist.tolist(),
            "finite_difference_twist": finite_difference.finite_difference_twist.tolist(),
        },
        "provisional_cuff_rebind": {
            "flange_site_name": "attachment_site",
            "flange_site_body": plant.model.body(
                int(plant.model.site_bodyid[flange_site_id])
            ).name,
            "cuff_site_name": "adapter_cuff_site",
            "cuff_site_body": plant.model.body(
                int(plant.model.site_bodyid[cuff_site_id])
            ).name,
            "modeled_T_flange_cuff_translation_m": plant.model.site_pos[
                cuff_site_id
            ].tolist(),
            "modeled_T_flange_cuff_rotation": cuff_site_local_rotation.tolist(),
            "translation_error_against_stage5_geometry_m": frame_translation_error,
            "rotation_error_against_stage5_geometry_rad": frame_rotation_error,
            "cuff_frame_convention": (
                "+X along shank/cuff bar, +Y circumferential/tangential, "
                "+Z radial/principal contact-force direction"
            ),
            "flange_positive_y_maps_to_cuff_axis": "-Z",
            "adapter_geometry": {
                "type": "provisional cylinder",
                "radius_m": 0.018,
                "collision_enabled": True,
            },
            "cuff_bar_geometry": {
                "type": "provisional cylinder",
                "length_m": STAGE5_GEOMETRY.cuff_bar_length_m,
                "radius_m": STAGE5_GEOMETRY.cuff_bar_radius_m,
                "collision_enabled": bool(
                    plant.model.geom_contype[
                        plant.model.geom("stage5_cuff_bar_geom").id
                    ]
                ),
            },
            "hex_h_qc_geometry_present": False,
        },
        "cuff_jacobian_consistency": {
            "plant_vs_independent_cr12_offset_max_abs_error": (
                cuff_jacobian_model_error
            ),
            "analytic_vs_finite_difference_max_abs_error": (
                cuff_jacobian_finite_difference_error
            ),
            "analytic_twist_world": analytic_cuff_twist.tolist(),
            "finite_difference_twist_world": finite_difference_cuff_twist.tolist(),
            "rank": int(np.linalg.matrix_rank(cuff_jacobian)),
            "shape": list(cuff_jacobian.shape),
        },
        "cuff_wrench_validation": {
            "expression_frame": "WORLD",
            "reference_point": "Human sleeve_attach_site",
            "hex_h_qc_measurement": False,
            "validation_robot_joint_perturbation_rad": perturbation.tolist(),
            "wrench_world_force_moment": np.r_[
                perturbed_observation.cuff_force_vector_n,
                perturbed_observation.cuff_moment_vector_nm,
            ].tolist(),
            "generalized_force_reconstruction_residual": (
                perturbed_observation.cuff_wrench_reconstruction_residual_nm
            ),
            "human_torque_reconstruction_residual_nm": (
                perturbed_observation.human_wrench_torque_residual_nm
            ),
            "action_reaction_force_balance_norm_n": float(
                np.linalg.norm(force_balance)
            ),
            "common_origin_moment_balance_norm_nm": float(
                np.linalg.norm(common_origin_moment_balance)
            ),
            "all_finite": bool(
                np.all(
                    np.isfinite(
                        np.r_[
                            perturbed_observation.cuff_force_vector_n,
                            perturbed_observation.cuff_moment_vector_nm,
                            perturbed_observation.cuff_wrench_reconstruction_residual_nm,
                            perturbed_observation.human_wrench_torque_residual_nm,
                            force_balance,
                            common_origin_moment_balance,
                        ]
                    )
                )
            ),
        },
        "representative_pose_validation": representative_rows,
        "start_reset": {
            "human_q_deg": np.degrees(start_observation.human_q_rad).tolist(),
            "robot_q_deg": np.degrees(start_observation.robot_q_rad).tolist(),
            "cuff_position_error_m": start_observation.weld_position_error_m,
            "cuff_rotation_error_rad": start_observation.weld_rotation_error_rad,
            "unintended_contact_pairs": [
                list(pair) for pair in start_observation.unintended_contact_pairs
            ],
            "warning_counts": plant.warning_counts(),
        },
        "execution_boundary": {
            "preview_finite": bool(
                np.all(np.isfinite(preview.joint_torque_command_nm))
                and np.all(np.isfinite(preview.unclipped_joint_torque_nm))
            ),
            "preview_feasible": bool(preview.feasible),
            "joint_torque_command_nm": preview.joint_torque_command_nm.tolist(),
            "unclipped_joint_torque_nm": preview.unclipped_joint_torque_nm.tolist(),
        },
        "frame_chain": {
            "world_from_base_translation_m": (
                STAGE5_GEOMETRY.world_from_base.translation.tolist()
            ),
            "official_base_to_link6": "joint1..joint6 URDF chain",
            "link6_origin_used_as_provisional_flange": True,
            "flange_from_cuff_provisional_translation_m": (
                STAGE5_GEOMETRY.end_effector_from_cuff.translation.tolist()
            ),
            "flange_from_cuff_provisional_rotation": (
                STAGE5_GEOMETRY.end_effector_from_cuff.rotation.tolist()
            ),
            "hex_h_qc_sensor_frame": None,
        },
        "lab_end_effector_v1": {
            "built": False,
            "reason": (
                "lab-specific end-effector geometry remains unavailable; this "
                "baseline intentionally reuses the existing Stage-5 provisional cuff"
            ),
        },
    }
    summary["mechanical_completeness"] = {
        "all_representative_poses_reachable": all(
            row["position_error_m"] < 1.0e-8 and row["rotation_error_rad"] < 1.0e-8
            for row in representative_rows
        ),
        "all_representative_jacobians_full_rank": all(
            row["cuff_jacobian_rank"] == 6 for row in representative_rows
        ),
        "no_active_robot_collision_contacts": all(
            not row["active_robot_contact_pairs"] for row in representative_rows
        ),
        "minimum_robot_arm_to_human_clearance_m": min(
            row["minimum_robot_arm_to_human_clearance_m"]
            for row in representative_rows
        ),
        "minimum_articulated_robot_to_bed_clearance_m": min(
            row["minimum_articulated_robot_to_bed_clearance_m"]
            for row in representative_rows
        ),
        "minimum_provisional_adapter_to_human_clearance_m": min(
            row["provisional_adapter_to_human_clearance_m"]
            for row in representative_rows
        ),
        "minimum_provisional_adapter_to_bed_clearance_m": min(
            row["provisional_adapter_to_bed_clearance_m"]
            for row in representative_rows
        ),
        "flange_to_cuff_transform_matches_stage5_geometry": bool(
            frame_translation_error < 1.0e-12 and frame_rotation_error < 1.0e-12
        ),
        "cuff_jacobian_matches_independent_cr12_offset": bool(
            cuff_jacobian_model_error < 1.0e-10
        ),
        "cuff_jacobian_matches_finite_difference": bool(
            cuff_jacobian_finite_difference_error < 1.0e-7
        ),
        "cuff_wrench_virtual_work_and_balance_finite": bool(
            summary["cuff_wrench_validation"]["all_finite"]
            and perturbed_observation.cuff_wrench_reconstruction_residual_nm
            < 1.0e-9
            and perturbed_observation.human_wrench_torque_residual_nm < 1.0e-9
            and np.linalg.norm(force_balance) < 1.0e-12
            and np.linalg.norm(common_origin_moment_balance) < 1.0e-12
        ),
        "execution_preview_finite_and_feasible": bool(
            summary["execution_boundary"]["preview_finite"]
            and summary["execution_boundary"]["preview_feasible"]
        ),
        "maximum_official_fk_position_error_m": max(
            row["position_error_m"] for row in official_fk_checks
        ),
        "maximum_official_fk_rotation_error_rad": max(
            row["rotation_error_rad"] for row in official_fk_checks
        ),
    }
    (output_dir / "mechanical_validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


__all__ = ["run_cr12_mechanical_validation"]
