"""Offline, oracle-labeled geometry/IK/static-load probe; no time integration."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
for relative in (
    "stages/stage5_personalized_motion_learning/src",
    "stages/stage4_adaptive_control/src",
    "stages/stage3_full3d/src",
):
    sys.path.insert(0, str(ROOT / relative))

import mujoco
import numpy as np
from dataclasses import replace
from traction_mpc_stage3.human import nominal_tracking_wrench, soft_limit_torque
from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant, solve_cr12_stage5_ik
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot, CR12_MODEL_PATH
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.task import GoalTaskSpec
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import nominal_control_geometry
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1

STAGE5 = ROOT / "stages/stage5_personalized_motion_learning"
CONFIG = STAGE5 / "configs/high_rom_v1/stage5_goal_task_120_v1.json"
BASE_TASK = STAGE5 / "configs/stage5_goal_task_v1.json"
DEVELOPMENT = STAGE5 / "configs/full3d_adaptive_integration_v1/development_v1_1.json"
FREEZE = STAGE5 / "docs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/ROUND19_FULL23_FREEZE.json"
OUTPUT = STAGE5 / "docs/high_rom_v1/phase_a_diagnostic.json"


def main() -> None:
    spec = json.loads(CONFIG.read_text())
    old = json.loads(BASE_TASK.read_text())
    dev = json.loads(DEVELOPMENT.read_text())
    freeze = json.loads(FREEZE.read_text())
    for key in ("joint_angle_completion_tolerance_deg", "joint_velocity_completion_tolerance_deg_s", "hold_duration_s", "phase_timeout_s", "task_joint_velocity_limit_deg_s", "task_joint_acceleration_limit_deg_s2", "start_return_target_deg", "controller_completion_margin", "trajectory_contract"):
        assert spec[key] == old[key], key
    task = GoalTaskSpec.from_mapping(spec)
    assert np.allclose(np.degrees(task.outbound_goal_target_rad), [120.0, 120.0])
    assert spec["outbound_goal_target_deg"] == [120.0, 120.0]
    assert spec["q_bounds_deg"] == [[0.0, 125.0], [0.0, 125.0]]
    assert dev["cuff_force_limit_n"] == 200.0 and dev["cuff_moment_limit_nm"] == 60.0
    assert dev["maximum_stale_plan_age_s"] == 0.1
    assert hashlib.sha256((ROOT / freeze["controller_options_file"]).read_bytes()).hexdigest() == freeze["controller_options_sha256"]
    assert spec["human_model"]["soft_limit_margin_deg"] == math.degrees(STAGE5_HUMAN.soft_limit_margin_rad)
    assert spec["human_model"]["passive_stiffness_nm_rad"] == list(STAGE5_HUMAN.passive_stiffness_nm_rad)
    assert spec["human_model"]["passive_damping_nms_rad"] == list(STAGE5_HUMAN.passive_damping_nms_rad)
    human = replace(STAGE5_HUMAN, q_max_rad=tuple(np.radians(np.asarray(spec["human_model"]["hard_rom_deg"])[:, 1])))
    assert np.allclose(np.degrees(human.q_max_rad), [125.0, 125.0])
    plant = Stage5CR12SpringDamperPlant(human=human)
    robot = CR12TorqueRobot()
    assert str(CR12_MODEL_PATH.resolve()).startswith(str(ROOT))
    assert str(Path(sys.modules["traction_mpc_stage5.cr12_plant"].__file__).resolve()).startswith(str(ROOT))
    hard_model = np.degrees(plant.model.jnt_range[plant.human_joint_ids])
    assert np.allclose(hard_model, [[0, 125], [0, 125]])
    envelope = RigidTableReferenceEnvelopeV1(nominal_control_geometry())
    start = np.radians(spec["start_return_target_deg"])
    goal = np.radians(spec["outbound_goal_target_deg"])
    delta = goal - start
    bed = int(plant.bed_geom_id)
    result = {
        "schema": "high_rom_phase_a_static_diagnostic_v1",
        "evidence_category": "exploratory_geometry_oracle_not_closed_loop_qualification",
        "source_root": str(ROOT),
        "baseline_commit": "c72760ae76a5b77a7291b9108ca20ff10b6c3be6",
        "model_hard_rom_deg": hard_model.tolist(),
        "soft_limit_onset_deg": (np.degrees(human.q_max_rad) - np.degrees(human.soft_limit_margin_rad)).tolist(),
        "passive_stiffness_nm_rad": human.passive_stiffness_nm_rad,
        "passive_soft_torque_at_goal_nm": soft_limit_torque(goal, np.zeros(2), human).tolist(),
        "limits": {key: dev[key] for key in ("cuff_force_limit_n", "cuff_moment_limit_nm", "robot_torque_limit_nm", "robot_velocity_limit_deg_s", "human_velocity_limit_deg_s", "human_acceleration_limit_deg_s2", "maximum_stale_plan_age_s")},
        "path_results": {},
    }
    for name, lead in (("synchronous", 0.0), ("hip_leads", 0.45), ("knee_leads", -0.45)):
        coeff = np.zeros((2, 6))
        coeff[:, 0] = start
        coeff[0, 1] = delta[0] * (1 + lead)
        coeff[0, 2] = -delta[0] * lead
        coeff[1, 1] = delta[1] * (1 - lead)
        coeff[1, 2] = delta[1] * lead
        certificate = envelope.check_quintic(coeff, 1.0)
        samples = []
        prior = None
        min_sigma = math.inf
        min_joint_margin = math.inf
        min_robot_bed = math.inf
        robot_bed_geom = None
        model_table_distances = {name: math.inf for name in ("thigh_geom", "shank_geom", "sleeve_geom", "stage5_cuff_bar_geom", "cuff_adapter_geom")}
        max_force = -math.inf
        max_moment = -math.inf
        max_tau_ratio = -math.inf
        target_load = None
        failures = []
        max_reconstruction_error_deg = 0.0
        for s in np.linspace(0.0, 1.0, 33):
            q = np.polynomial.polynomial.polyval(s, coeff.T)
            pose = STAGE5_GEOMETRY.world_from_cuff(q, human)
            q_reconstructed = envelope.geometry.estimate_q(pose.translation, pose.rotation)
            max_reconstruction_error_deg = max(max_reconstruction_error_deg, float(np.max(np.abs(np.degrees(q_reconstructed - q)))))
            ref = CuffPoseReference(q, np.zeros(2), np.zeros(2), pose)
            load = nominal_tracking_wrench(q, np.zeros(2), ref, human)
            force = float(load["force_norm_n"])
            moment = abs(float(load["my_nm"]))
            max_force = max(max_force, force)
            max_moment = max(max_moment, moment)
            if abs(s - 1.0) < 1e-12:
                target_load = {"force_n": force, "moment_nm": moment, "generalized_required_nm": load["tau_required_nm"].tolist()}
            target = STAGE5_GEOMETRY.base_from_end_effector_target(q, human)
            try:
                rq = solve_cr12_stage5_ik(robot, target, previous_q_rad=prior)
            except Exception as exc:
                failures.append({"progress": float(s), "q_deg": np.degrees(q).tolist(), "error": str(exc)})
                samples.append({"progress": float(s), "q_deg": np.degrees(q).tolist(), "ik": "FAIL"})
                continue
            prior = rq
            robot.set_configuration(rq)
            sigma = float(np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)[-1])
            min_sigma = min(min_sigma, sigma)
            limits = robot.joint_limits_rad
            margin = float(np.min(np.r_[rq - limits[:, 0], limits[:, 1] - rq]))
            min_joint_margin = min(min_joint_margin, math.degrees(margin))
            plant.data.qpos[plant.human_qpos_indices] = q
            plant.data.qpos[plant.robot_qpos_indices] = rq
            plant.data.qvel[:] = 0.0
            mujoco.mj_forward(plant.model, plant.data)
            for geom_name in model_table_distances:
                gid = plant.model.geom(geom_name).id
                distance = float(mujoco.mj_geomDistance(plant.model, plant.data, bed, gid, 2.0, None))
                model_table_distances[geom_name] = min(model_table_distances[geom_name], distance)
            for geom in plant.robot_collision_geom_ids:
                distance = float(mujoco.mj_geomDistance(plant.model, plant.data, bed, int(geom), 2.0, None))
                if distance < min_robot_bed:
                    min_robot_bed = distance
                    robot_bed_geom = mujoco.mj_id2name(plant.model, mujoco.mjtObj.mjOBJ_GEOM, int(geom))
            jacp = np.zeros((3, plant.model.nv))
            jacr = np.zeros((3, plant.model.nv))
            mujoco.mj_jacSite(plant.model, plant.data, jacp, jacr, plant.attachment_site_id)
            jt_load = jacp[:, plant.robot_dof_indices].T @ load["wrench_world"][:3] + jacr[:, plant.robot_dof_indices].T @ load["wrench_world"][3:]
            bias = plant.data.qfrc_bias[plant.robot_dof_indices]
            torque_limits = plant.torque_limits_nm
            ratio = max(float(np.max(np.abs((bias + jt_load) / torque_limits))), float(np.max(np.abs((bias - jt_load) / torque_limits))))
            max_tau_ratio = max(max_tau_ratio, ratio)
            samples.append({"progress": float(s), "q_deg": np.degrees(q).tolist(), "ik": "OK", "cr12_joint_deg": np.degrees(rq).tolist(), "ik_sigma_min": sigma, "robot_torque_bound_ratio": ratio})
        # A diagnostic 8 s smooth clock fits inside the unchanged 10 s phase
        # timeout. This is a kinematic screen, not an executed reference.
        clock_s = 8.0
        t = np.linspace(0.0, 1.0, 1001)
        u = 10*t**3 - 15*t**4 + 6*t**5
        du_dt = (30*t**2 - 60*t**3 + 30*t**4) / clock_s
        d2u_dt2 = (60*t - 180*t**2 + 120*t**3) / clock_s**2
        dq_du = coeff[:, 1, None] + 2*coeff[:, 2, None]*u[None, :]
        d2q_du2 = 2*coeff[:, 2, None]
        human_speed = np.max(np.abs(np.degrees(dq_du*du_dt[None, :])), axis=1)
        human_acc = np.max(np.abs(np.degrees(d2q_du2*du_dt[None, :]**2 + dq_du*d2u_dt2[None, :])), axis=1)
        success = [row for row in samples if row["ik"] == "OK"]
        robot_speed_est = None
        max_robot_step = None
        if len(success) == len(samples):
            robot_q_deg = np.asarray([row["cr12_joint_deg"] for row in success])
            progress = np.asarray([row["progress"] for row in success])
            derivative = np.gradient(robot_q_deg, progress, axis=0)
            robot_speed_est = (np.max(np.abs(derivative), axis=0) * (1.875/clock_s)).tolist()
            max_robot_step = float(np.max(np.abs(np.diff(robot_q_deg, axis=0))))
        timing_screen = {
            "clock_duration_s": clock_s,
            "human_speed_deg_s": human_speed.tolist(),
            "human_acceleration_deg_s2": human_acc.tolist(),
            "robot_speed_deg_s_finite_difference_estimate": robot_speed_est,
            "maximum_adjacent_robot_joint_step_deg": max_robot_step,
            "human_speed_within_existing_limit": bool(np.all(human_speed <= dev["human_velocity_limit_deg_s"])),
            "human_acceleration_within_existing_limit": bool(np.all(human_acc <= dev["human_acceleration_limit_deg_s2"])),
            "robot_speed_estimate_within_existing_limit": None if robot_speed_est is None else bool(np.all(np.asarray(robot_speed_est) <= dev["robot_velocity_limit_deg_s"])),
            "qualification": "kinematic_diagnostic_only_no_executed_timing_or_continuous_robot_bound",
        }
        result["path_results"][name] = {
            "coefficient_rad": coeff.tolist(),
            "timing_screen": timing_screen,
            "continuous_table_certificate": certificate,
            "ik_samples": len(samples),
            "ik_failures": failures,
            "minimum_ik_sigma_mixed_units": None if min_sigma == math.inf else min_sigma,
            "minimum_cr12_joint_margin_deg": None if min_joint_margin == math.inf else min_joint_margin,
            "minimum_modeled_robot_table_distance_m_discrete": None if min_robot_bed == math.inf else min_robot_bed,
            "robot_table_min_geom": robot_bed_geom,
            "modeled_body_table_distances_m_discrete": model_table_distances,
            "max_quasistatic_force_n_discrete": max_force,
            "max_quasistatic_moment_nm_discrete": max_moment,
            "max_robot_torque_limit_ratio_with_sign_ambiguity_discrete": None if max_tau_ratio == -math.inf else max_tau_ratio,
            "target_quasistatic_load": target_load,
            "max_cuff_angle_reconstruction_error_deg_discrete": max_reconstruction_error_deg,
            "samples": samples,
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({name: {key: value for key, value in path.items() if key not in ("samples", "coefficient_rad")} for name, path in result["path_results"].items()}, indent=2))


if __name__ == "__main__":
    main()
