"""Robot-only Stage-3B mechanical and numerical validation."""

from __future__ import annotations

import mujoco
import numpy as np

from .ik import solve_cuff_trajectory_ik
from .robot import ACTUATOR_NAMES, BODY_NAMES, JOINT_NAMES, UR10eTorqueRobot


SYNTHETIC_WRENCHES_BASE = {
    "force_x_100n": np.array([100.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "force_z_100n": np.array([0.0, 0.0, 100.0, 0.0, 0.0, 0.0]),
    "combined_80n_20nm": np.array([80.0, 0.0, 80.0, 0.0, 20.0, 0.0]),
}


def _gravity_compensated_hold(
    robot: UR10eTorqueRobot,
    q_rad: np.ndarray,
    duration_s: float,
) -> dict[str, float | dict[str, int]]:
    robot.set_configuration(q_rad)
    initial = robot.data.qpos[robot.qpos_indices].copy()
    steps = int(round(duration_s / robot.model.opt.timestep))
    peak_fraction = 0.0
    for _ in range(steps):
        bias = robot.bias_torque_nm()
        peak_fraction = max(
            peak_fraction,
            float(np.max(np.abs(bias) / robot.torque_limits_nm)),
        )
        robot.command_torque(bias)
        mujoco.mj_step(robot.model, robot.data)
    final = robot.data.qpos[robot.qpos_indices].copy()
    return {
        "duration_s": duration_s,
        "max_abs_joint_drift_rad": float(np.max(np.abs(final - initial))),
        "max_abs_joint_speed_rad_s": float(
            np.max(np.abs(robot.data.qvel[robot.dof_indices]))
        ),
        "peak_gravity_torque_limit_fraction": peak_fraction,
        "warning_counts": robot.warning_counts(),
    }


def run_robot_core_validation(
    *,
    sample_count: int = 301,
    gravity_hold_duration_s: float = 0.25,
) -> dict[str, object]:
    if sample_count < 31:
        raise ValueError("dense validation requires at least 31 samples")
    robot = UR10eTorqueRobot()

    body_parent_names = []
    for name in BODY_NAMES:
        body_id = robot.model.body(name).id
        parent_id = int(robot.model.body_parentid[body_id])
        body_parent_names.append(
            None if parent_id == 0 else robot.model.body(parent_id).name
        )

    robot.reset_home()
    home_pose = robot.attachment_pose()
    jacobian_q = np.radians([-70.0, -27.0, 82.0, 23.0, -105.0, -25.0])
    jacobian_dq = np.array([0.17, -0.11, 0.09, 0.13, -0.07, 0.05])
    jacobian_check = robot.finite_difference_jacobian_check(jacobian_q, jacobian_dq)

    robot.set_configuration(jacobian_q)
    probe_torque = np.array([10.0, -20.0, 30.0, -10.0, 5.0, -2.0])
    realized_torque = robot.command_torque(probe_torque)

    times = np.linspace(0.0, 15.0, sample_count)
    ik_samples = solve_cuff_trajectory_ik(robot, times)
    q_path = np.array([sample.q_rad for sample in ik_samples])
    limits = robot.joint_limits_rad
    lower_margin = q_path - limits[:, 0]
    upper_margin = limits[:, 1] - q_path
    joint_margin = np.minimum(lower_margin, upper_margin)
    step = np.diff(q_path, axis=0)

    peak_abs_gravity_torque = np.zeros(6)
    for sample in ik_samples:
        robot.set_configuration(sample.q_rad)
        peak_abs_gravity_torque = np.maximum(
            peak_abs_gravity_torque,
            np.abs(robot.bias_torque_nm()),
        )
    gravity_limit_fraction = peak_abs_gravity_torque / robot.torque_limits_nm

    midpoint = ik_samples[len(ik_samples) // 2]
    robot.set_configuration(midpoint.q_rad)
    wrench_checks: dict[str, object] = {}
    maximum_loaded_fraction = 0.0
    for name, wrench in SYNTHETIC_WRENCHES_BASE.items():
        jacobian_torque = robot.wrench_to_joint_torque(wrench)
        applied_force = robot.mujoco_applied_wrench_generalized_force(wrench)
        loaded_torque = robot.bias_torque_nm() + jacobian_torque
        fraction = np.abs(loaded_torque) / robot.torque_limits_nm
        maximum_loaded_fraction = max(maximum_loaded_fraction, float(np.max(fraction)))
        wrench_checks[name] = {
            "joint_torque_nm": jacobian_torque.tolist(),
            "mj_applyFT_max_abs_error_nm": float(
                np.max(np.abs(jacobian_torque - applied_force))
            ),
            "gravity_plus_load_peak_limit_fraction": float(np.max(fraction)),
            "minimum_modeled_torque_margin_nm": float(
                np.min(robot.torque_limits_nm - np.abs(loaded_torque))
            ),
        }

    trajectory_collision_pairs = sorted(
        {pair for sample in ik_samples for pair in sample.contact_pairs}
    )
    trajectory_warning_counts = robot.warning_counts()
    gravity_hold = _gravity_compensated_hold(
        robot,
        midpoint.q_rad,
        gravity_hold_duration_s,
    )

    return {
        "model_contract": {
            "nq": robot.model.nq,
            "nv": robot.model.nv,
            "nu": robot.model.nu,
            "joint_names": list(JOINT_NAMES),
            "joint_axes": robot.model.jnt_axis[robot.joint_ids].tolist(),
            "joint_limits_deg": np.degrees(robot.joint_limits_rad).tolist(),
            "actuator_names": list(ACTUATOR_NAMES),
            "modeled_torque_limits_nm": robot.torque_limits_nm.tolist(),
            "body_names": list(BODY_NAMES),
            "body_parent_names": body_parent_names,
            "attachment_site": "attachment_site",
            "attachment_site_body": robot.model.body(robot.attachment_body_id).name,
            "attachment_site_position_in_body_m": robot.model.site_pos[
                robot.attachment_site_id
            ].tolist(),
            "attachment_site_quaternion_in_body": robot.model.site_quat[
                robot.attachment_site_id
            ].tolist(),
            "total_body_mass_kg": float(np.sum(robot.model.body_mass)),
            "positive_inertia_body_count": int(
                np.sum(np.all(robot.model.body_inertia[1:] > 0.0, axis=1))
            ),
            "nonworld_body_count": robot.model.nbody - 1,
            "collision_geom_count": int(
                np.sum(
                    (robot.model.geom_contype != 0)
                    | (robot.model.geom_conaffinity != 0)
                )
            ),
            "visual_only_geom_count": int(
                np.sum(
                    (robot.model.geom_contype == 0)
                    & (robot.model.geom_conaffinity == 0)
                )
            ),
        },
        "fk": {
            "home_q_deg": np.degrees(robot.home_q_rad).tolist(),
            "home_attachment_position_base_m": home_pose.translation.tolist(),
            "home_attachment_rotation_base": home_pose.rotation.tolist(),
            "finite": bool(
                np.all(np.isfinite(home_pose.translation))
                and np.all(np.isfinite(home_pose.rotation))
            ),
        },
        "jacobian": {
            "q_deg": np.degrees(jacobian_q).tolist(),
            "analytic_twist": jacobian_check.analytic_twist.tolist(),
            "finite_difference_twist": jacobian_check.finite_difference_twist.tolist(),
            "max_abs_error": jacobian_check.max_abs_error,
        },
        "torque_actuator_mapping": {
            "command_nm": probe_torque.tolist(),
            "qfrc_actuator_nm": realized_torque.tolist(),
            "max_abs_error_nm": float(np.max(np.abs(probe_torque - realized_torque))),
            "hidden_bias_terms_zero": bool(
                np.allclose(robot.model.actuator_biasprm[robot.actuator_ids], 0.0)
            ),
        },
        "ik": {
            "sample_count": len(ik_samples),
            "maximum_position_error_m": max(
                sample.position_error_m for sample in ik_samples
            ),
            "maximum_rotation_error_rad": max(
                sample.rotation_error_rad for sample in ik_samples
            ),
            "maximum_individual_joint_step_deg": float(
                np.degrees(np.max(np.abs(step)))
            ),
            "maximum_joint_step_norm_deg": float(
                np.degrees(np.max(np.linalg.norm(step, axis=1)))
            ),
            "minimum_joint_limit_margin_deg": float(
                np.degrees(np.min(joint_margin))
            ),
            "q_min_deg": np.degrees(np.min(q_path, axis=0)).tolist(),
            "q_max_deg": np.degrees(np.max(q_path, axis=0)).tolist(),
            "minimum_6d_jacobian_singular_value": min(
                sample.minimum_singular_value for sample in ik_samples
            ),
            "maximum_6d_jacobian_condition_number": max(
                sample.condition_number for sample in ik_samples
            ),
        },
        "wrench_mapping": wrench_checks,
        "trajectory_gravity_torque": {
            "peak_abs_joint_torque_nm": peak_abs_gravity_torque.tolist(),
            "peak_joint_limit_fraction": float(np.max(gravity_limit_fraction)),
            "minimum_modeled_torque_margin_nm": float(
                np.min(robot.torque_limits_nm - peak_abs_gravity_torque)
            ),
        },
        "maximum_synthetic_gravity_plus_load_limit_fraction": maximum_loaded_fraction,
        "gravity_compensated_hold": gravity_hold,
        "mechanical": {
            "trajectory_self_collision_pairs": trajectory_collision_pairs,
            "trajectory_warning_counts": trajectory_warning_counts,
            "all_ik_states_finite": bool(np.all(np.isfinite(q_path))),
        },
    }
