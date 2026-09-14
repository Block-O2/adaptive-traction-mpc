"""Reproducible engineering checks for provisional Stage-5 geometry/mechanics."""

from __future__ import annotations

import json
import math
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage3.spring_damper_interface import AttachmentState, evaluate_interface

from .config import STAGE5_CONFIG
from .geometry import STAGE5_GEOMETRY
from .human import STAGE5_HUMAN
from .ik import solve_stage5_ik
from .mechanics import (
    STAGE4_P1_INTERFACE,
    STAGE5_STIFF_INTERFACE,
    TIMESTEP_PROBE_S,
)
from .plant import Stage5SpringDamperPlant
from .visualization import render_cuff_closeup, render_top_view


def _zero_attachment() -> AttachmentState:
    return AttachmentState(
        position_world_m=np.zeros(3),
        rotation_world=np.eye(3),
        velocity_world_m_s=np.zeros(3),
        angular_velocity_world_rad_s=np.zeros(3),
    )


def _static_mechanics(parameters) -> dict[str, object]:
    human = _zero_attachment()
    translation = AttachmentState(
        position_world_m=np.array([0.001, 0.0, 0.0]),
        rotation_world=np.eye(3),
        velocity_world_m_s=np.zeros(3),
        angular_velocity_world_rad_s=np.zeros(3),
    )
    velocity = AttachmentState(
        position_world_m=np.zeros(3),
        rotation_world=np.eye(3),
        velocity_world_m_s=np.array([0.01, 0.0, 0.0]),
        angular_velocity_world_rad_s=np.zeros(3),
    )
    rotation = AttachmentState(
        position_world_m=np.zeros(3),
        rotation_world=Rotation.from_rotvec([0.0, 0.0, math.radians(1.0)]).as_matrix(),
        velocity_world_m_s=np.zeros(3),
        angular_velocity_world_rad_s=np.zeros(3),
    )
    translation_state = evaluate_interface(parameters, translation, human)
    velocity_state = evaluate_interface(parameters, velocity, human)
    rotation_state = evaluate_interface(parameters, rotation, human)
    k = np.asarray(parameters.translation_stiffness_n_m, dtype=float)
    return {
        "translation_stiffness_n_m": list(parameters.translation_stiffness_n_m),
        "translation_damping_ns_m": list(parameters.translation_damping_ns_m),
        "rotation_stiffness_nm_rad": parameters.rotation_stiffness_nm_rad,
        "rotation_damping_nms_rad": parameters.rotation_damping_nms_rad,
        "force_from_1mm_x_perturbation_n": translation_state.human_wrench_world[:3].tolist(),
        "force_norm_from_1mm_x_perturbation_n": float(
            np.linalg.norm(translation_state.human_wrench_world[:3])
        ),
        "damping_force_from_10mm_s_x_n": velocity_state.human_wrench_world[:3].tolist(),
        "moment_norm_from_1deg_rotation_nm": float(
            np.linalg.norm(rotation_state.human_wrench_world[3:])
        ),
        "static_deformation_mm_at_force_n": {
            str(force): (1000.0 * force / k).tolist() for force in (10.0, 50.0, 100.0)
        },
    }


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
                name1 = model.geom(geom1).name or (
                    f"{model.body(int(model.geom_bodyid[geom1])).name}/geom#{geom1}"
                )
                name2 = model.geom(geom2).name or (
                    f"{model.body(int(model.geom_bodyid[geom2])).name}/geom#{geom2}"
                )
                pair = (name1, name2)
    return minimum, pair


def _reachability_and_clearance() -> dict[str, object]:
    postures = np.radians(np.asarray(STAGE5_CONFIG["representative_postures_deg"], dtype=float))
    robot = UR10eTorqueRobot()
    plant = Stage5SpringDamperPlant()
    previous = None
    rows: list[dict[str, object]] = []
    for q in postures:
        target = STAGE5_GEOMETRY.base_from_end_effector_target(q, STAGE5_HUMAN)
        solution = solve_stage5_ik(robot, target, previous_q_rad=previous)
        robot.set_configuration(solution)
        actual = robot.attachment_pose()
        pose_error = np.r_[
            actual.translation - target.translation,
            Rotation.from_matrix(target.rotation @ actual.rotation.T).as_rotvec(),
        ]
        singular_values = np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)

        mujoco.mj_resetData(plant.model, plant.data)
        plant.data.qpos[plant.human_qpos_indices] = q
        plant.data.qpos[plant.robot_qpos_indices] = solution
        plant.data.eq_active[plant.weld_id] = 0
        mujoco.mj_forward(plant.model, plant.data)
        excluded_names = {"cuff_adapter_geom", "stage5_cuff_bar_geom"}
        robot_arm_geoms = [
            geom_id
            for geom_id in plant.robot_collision_geom_ids
            if plant.model.geom(geom_id).name not in excluded_names
        ]
        human_geoms = list(plant.human_geom_ids)
        human_clearance, human_pair = _minimum_geom_distance(
            plant.model, plant.data, robot_arm_geoms, human_geoms
        )
        articulated_robot_geoms = [
            geom_id
            for geom_id in robot_arm_geoms
            if plant.model.body(int(plant.model.geom_bodyid[geom_id])).name
            not in {"base", "shoulder_link"}
        ]
        bed_clearance, bed_pair = _minimum_geom_distance(
            plant.model, plant.data, articulated_robot_geoms, [plant.bed_geom_id]
        )
        self_contacts = []
        for index in range(plant.data.ncon):
            geom1 = int(plant.data.contact[index].geom1)
            geom2 = int(plant.data.contact[index].geom2)
            if geom1 in plant.robot_collision_geom_ids and geom2 in plant.robot_collision_geom_ids:
                self_contacts.append((plant.model.geom(geom1).name, plant.model.geom(geom2).name))
        joint_margin = np.minimum(
            solution - robot.joint_limits_rad[:, 0],
            robot.joint_limits_rad[:, 1] - solution,
        )
        rows.append(
            {
                "human_q_deg": np.degrees(q).tolist(),
                "robot_q_deg": np.degrees(solution).tolist(),
                "position_error_m": float(np.linalg.norm(pose_error[:3])),
                "rotation_error_rad": float(np.linalg.norm(pose_error[3:])),
                "minimum_6d_jacobian_singular_value": float(singular_values[-1]),
                "condition_number_6d_jacobian": float(singular_values[0] / singular_values[-1]),
                "minimum_joint_limit_margin_deg": float(np.degrees(np.min(joint_margin))),
                "minimum_robot_arm_to_human_clearance_m": human_clearance,
                "closest_robot_human_pair": human_pair,
                "minimum_articulated_arm_to_bed_clearance_m": bed_clearance,
                "closest_robot_bed_pair": bed_pair,
                "robot_self_contact_pairs": self_contacts,
            }
        )
        previous = solution.copy()
    return {
        "samples": rows,
        "all_reachable": all(row["position_error_m"] < 1.0e-8 and row["rotation_error_rad"] < 1.0e-8 for row in rows),
        "minimum_6d_jacobian_singular_value": min(row["minimum_6d_jacobian_singular_value"] for row in rows),
        "maximum_6d_jacobian_condition_number": max(row["condition_number_6d_jacobian"] for row in rows),
        "minimum_joint_limit_margin_deg": min(row["minimum_joint_limit_margin_deg"] for row in rows),
        "minimum_robot_arm_to_human_clearance_m": min(row["minimum_robot_arm_to_human_clearance_m"] for row in rows),
        "minimum_articulated_arm_to_bed_clearance_m": min(row["minimum_articulated_arm_to_bed_clearance_m"] for row in rows),
        "robot_self_contact_pairs": sorted({tuple(pair) for row in rows for pair in row["robot_self_contact_pairs"]}),
    }


def _timestep_probe(dt_s: float, duration_s: float = 0.05) -> dict[str, object]:
    plant = Stage5SpringDamperPlant(physics_dt_s=dt_s)
    initial_q = np.radians([5.0, 10.0])
    plant.reset(initial_q)
    cuff_rotation = plant.data.site_xmat[plant.sleeve_site_id].reshape(3, 3).copy()
    requested_displacement = cuff_rotation[:, 2] * 0.001
    jacobian = plant.robot_attachment_jacobian()[:3]
    delta_q = np.linalg.pinv(jacobian, rcond=1.0e-10) @ requested_displacement
    plant.data.qpos[plant.robot_qpos_indices] += delta_q
    mujoco.mj_forward(plant.model, plant.data)
    initial = plant.observe()
    forces = [float(np.linalg.norm(initial.cuff_force_vector_n))]
    deformations = [float(np.linalg.norm(plant._evaluate_current_interface().displacement_human_m))]
    finite = True
    steps = int(round(duration_s / dt_s))
    for _ in range(steps):
        mujoco.mj_forward(plant.model, plant.data)
        bias = plant.data.qfrc_bias[plant.robot_dof_indices]
        plant.data.ctrl[plant.actuator_ids] = np.clip(
            bias, -plant.torque_limits_nm, plant.torque_limits_nm
        )
        observation = plant.step()
        interface = plant._evaluate_current_interface()
        values = np.r_[
            plant.data.qpos,
            plant.data.qvel,
            observation.cuff_force_vector_n,
            interface.displacement_human_m,
        ]
        finite = finite and bool(np.all(np.isfinite(values)))
        forces.append(float(np.linalg.norm(observation.cuff_force_vector_n)))
        deformations.append(float(np.linalg.norm(interface.displacement_human_m)))
    return {
        "dt_s": dt_s,
        "duration_s": duration_s,
        "step_count": steps,
        "requested_initial_radial_perturbation_m": 0.001,
        "realized_initial_deformation_m": deformations[0],
        "initial_force_n": forces[0],
        "peak_force_n": max(forces),
        "final_force_n": forces[-1],
        "peak_deformation_m": max(deformations),
        "final_deformation_m": deformations[-1],
        "maximum_human_joint_excursion_deg": float(
            np.degrees(np.max(np.abs(plant.data.qpos[plant.human_qpos_indices] - initial_q)))
        ),
        "finite": finite,
        "warning_counts": plant.warning_counts(),
    }


def run_stage5_validation(output_dir: Path) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    geometry = {
        "T_WB": {
            "rotation": STAGE5_GEOMETRY.world_from_base.rotation.tolist(),
            "translation_m": STAGE5_GEOMETRY.world_from_base.translation.tolist(),
        },
        "T_WH": {
            "rotation": STAGE5_GEOMETRY.world_from_human.rotation.tolist(),
            "translation_m": STAGE5_GEOMETRY.world_from_human.translation.tolist(),
        },
        "T_EC": {
            "rotation": STAGE5_GEOMETRY.end_effector_from_cuff.rotation.tolist(),
            "translation_m": STAGE5_GEOMETRY.end_effector_from_cuff.translation.tolist(),
        },
        "base_alignment_fraction_of_shank_from_knee_neutral": STAGE5_GEOMETRY.base_alignment_fraction_of_shank(),
        "cuff_center_fraction_of_shank_from_knee": STAGE5_HUMAN.cuff_fraction_of_shank,
        "cuff_center_distance_from_knee_m": STAGE5_HUMAN.sleeve_center_m,
        "adapter_length_m": float(np.linalg.norm(STAGE5_GEOMETRY.end_effector_from_cuff.translation)),
        "bar_stem_dot_product": float(
            STAGE5_GEOMETRY.cuff_bar_axis_in_cuff
            @ (
                STAGE5_GEOMETRY.end_effector_from_cuff.rotation.T
                @ STAGE5_GEOMETRY.terminal_stem_axis_in_end_effector
            )
        ),
        "cuff_frame_axes": {
            "+X": "along shank and cuff bar",
            "+Y": "lateral/tangential around the shank",
            "+Z": "radial in the Human sagittal plane; principal contact-force direction; terminal stem is along -C +Z",
        },
    }
    reachability = _reachability_and_clearance()
    old_mechanics = _static_mechanics(STAGE4_P1_INTERFACE)
    stage5_mechanics = _static_mechanics(STAGE5_STIFF_INTERFACE)
    timestep = [_timestep_probe(dt) for dt in TIMESTEP_PROBE_S]
    finest = timestep[-1]
    for row in timestep:
        row["peak_force_difference_from_025ms_n"] = row["peak_force_n"] - finest["peak_force_n"]
        row["final_deformation_difference_from_025ms_m"] = row["final_deformation_m"] - finest["final_deformation_m"]
    report = {
        "schema": "stage5_geometry_mechanics_validation_v1",
        "evidence_category": "smoke_engineering_validation_only",
        "qualification_scope": "finite short perturbation probe; not strict numerical qualification, hardware validation, or clinical evidence",
        "geometry": geometry,
        "reachability_and_clearance": reachability,
        "mechanics": {
            "stage4_p1_reference": old_mechanics,
            "stage5_stiff_surrogate": stage5_mechanics,
            "human_joint_passive_parameters_changed": False,
            "rigid_weld_solver_parameters_changed": False,
            "bed_contact_parameters_changed": False,
            "timestep_probe": timestep,
        },
        "safety_contract": STAGE5_CONFIG["safety"],
        "summary": {
            "representative_posture_count": len(reachability["samples"]),
            "all_representative_postures_reachable": reachability["all_reachable"],
            "all_timestep_probes_finite": all(row["finite"] for row in timestep),
            "all_timestep_probes_warning_free": all(not row["warning_counts"] for row in timestep),
            "stage4_evidence_modified": False,
            "learning_or_rl_implemented": False,
        },
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    render_top_view(output_dir / "top_view_stage5_geometry.png")
    render_cuff_closeup(output_dir / "inverted_t_cuff_closeup.png")
    return report
