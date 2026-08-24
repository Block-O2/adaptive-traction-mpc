"""
Hardcoded MuJoCo scene validation for the elastic rod setup.

This script intentionally does not import any traction controller. It drives the
UR5e end-effector along a known circular contact trajectory and checks whether
the MuJoCo scene, point connection, radial spring, and sensors behave coherently.

Example:
    python scripts/check_mujoco_scene.py --target-deg 60
"""

import argparse
import csv
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENE_XML = PROJECT_ROOT / "assets" / "mujoco" / "scene_rod.xml"
OUT_CSV = PROJECT_ROOT / "results" / "debug" / "mujoco_scene_validation" / "hardcoded_scene_check.csv"

ARM_JOINTS = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]
ARM_Q0 = np.array([-1.5708, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])

CONTACT_LOCAL = np.array([0.315, 0.0, 0.005])


def smoothstep(a):
    a = np.clip(a, 0.0, 1.0)
    return a * a * a * (10.0 - 15.0 * a + 6.0 * a * a)


def smoothstep_dot(a, duration):
    a = np.clip(a, 0.0, 1.0)
    return (30.0 * a * a - 60.0 * a * a * a + 30.0 * a**4) / duration


def joint_addr(model, name):
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if jid < 0:
        raise RuntimeError(f"Missing joint: {name}")
    return model.jnt_qposadr[jid], model.jnt_dofadr[jid]


def body_id(model, name):
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if bid < 0:
        raise RuntimeError(f"Missing body: {name}")
    return bid


def site_id(model, name):
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, name)
    if sid < 0:
        raise RuntimeError(f"Missing site: {name}")
    return sid


def sensor(model, data, name):
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
    if sid < 0:
        raise RuntimeError(f"Missing sensor: {name}")
    adr = model.sensor_adr[sid]
    dim = model.sensor_dim[sid]
    return data.sensordata[adr : adr + dim].copy()


def site_orientation_error_deg(data, site_a, site_b):
    Ra = data.site_xmat[site_a].reshape(3, 3)
    Rb = data.site_xmat[site_b].reshape(3, 3)
    R = Ra.T @ Rb
    cos_angle = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def set_arm_qpos(model, data, q):
    for value, name in zip(q, ARM_JOINTS):
        qadr, _ = joint_addr(model, name)
        data.qpos[qadr] = value


def arm_indices(model):
    qaddrs = []
    dofs = []
    for name in ARM_JOINTS:
        qadr, dof = joint_addr(model, name)
        qaddrs.append(qadr)
        dofs.append(dof)
    return np.array(qaddrs), np.array(dofs)


def refine_ik_to_contact(model, data, ee_sid, contact_sid, qaddrs, dofs):
    target = data.site_xpos[contact_sid].copy()
    set_arm_qpos(model, data, ARM_Q0)
    mujoco.mj_forward(model, data)

    best_err = np.linalg.norm(data.site_xpos[ee_sid] - target)
    best_q = data.qpos[qaddrs].copy()
    warm_starts = [
        np.array([-1.4709, 1.794, 1.1074, 1.7185, 0.4267, 1.1535]),
        np.array([-1.5, 1.8, 1.0, 1.7, 0.4, 1.2]),
        np.array([-1.3, 1.6, 1.2, 1.8, 0.5, 1.0]),
        ARM_Q0,
    ]

    for q in warm_starts:
        set_arm_qpos(model, data, q)
        mujoco.mj_forward(model, data)
        err = np.linalg.norm(data.site_xpos[ee_sid] - target)
        if err < best_err:
            best_err = err
            best_q = data.qpos[qaddrs].copy()

    data.qpos[qaddrs] = best_q
    for _ in range(3000):
        mujoco.mj_forward(model, data)
        err = target - data.site_xpos[ee_sid]
        err_norm = np.linalg.norm(err)
        if err_norm < 5e-4:
            break
        jacp = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, jacp, jacr, ee_sid)
        J = jacp[:, dofs]
        lam = max(1e-4, err_norm * 0.1)
        dq = J.T @ np.linalg.solve(J @ J.T + lam * np.eye(3), err)
        dq = np.clip(dq, -0.05, 0.05)
        data.qpos[qaddrs] += dq

    mujoco.mj_forward(model, data)
    return np.linalg.norm(data.site_xpos[ee_sid] - target)


def contact_target_from_known_geometry(model, data, theta):
    pivot_bid = body_id(model, "rod_pivot")
    pivot = data.xpos[pivot_bid].copy()

    # The scene uses hinge axis "0 -1 0", so positive rod_rotate lifts the
    # contact point toward positive world z.
    c = np.cos(theta)
    s = np.sin(theta)
    rot_y = np.array(
        [
            [c, 0.0, -s],
            [0.0, 1.0, 0.0],
            [s, 0.0, c],
        ]
    )
    return pivot + rot_y @ CONTACT_LOCAL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-deg", type=float, default=60.0)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--settle", type=float, default=2.0)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--kp", type=float, default=3000.0)
    parser.add_argument("--kd", type=float, default=180.0)
    parser.add_argument("--csv", type=Path, default=OUT_CSV)
    args = parser.parse_args()

    if not SCENE_XML.exists():
        raise FileNotFoundError(f"Missing scene XML: {SCENE_XML}")

    model = mujoco.MjModel.from_xml_path(str(SCENE_XML))
    data = mujoco.MjData(model)

    ee_sid = site_id(model, "attachment_site")
    contact_sid = site_id(model, "contact_site")
    qaddrs, dofs = arm_indices(model)
    rod_qadr, rod_dof = joint_addr(model, "rod_rotate")
    radial_qadr, _ = joint_addr(model, "rod_radial")

    mujoco.mj_resetData(model, data)
    data.qpos[rod_qadr] = 0.0
    data.qpos[radial_qadr] = 0.0
    mujoco.mj_forward(model, data)

    ik_err = refine_ik_to_contact(model, data, ee_sid, contact_sid, qaddrs, dofs)
    initial_site_orientation_err = site_orientation_error_deg(data, ee_sid, contact_sid)

    ctrl_dt = 1.0 / 100.0
    sim_steps = max(1, int(ctrl_dt / model.opt.timestep))

    def apply_task_pd(p_des, v_des):
        mujoco.mj_forward(model, data)
        ee_pos = data.site_xpos[ee_sid].copy()
        contact_pos = data.site_xpos[contact_sid].copy()

        jacp = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, jacp, jacr, ee_sid)
        J = jacp[:, dofs]

        contact_jacp = np.zeros((3, model.nv))
        contact_jacr = np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, contact_jacp, contact_jacr, contact_sid)
        contact_vel = contact_jacp @ data.qvel

        f_task = args.kp * (p_des - contact_pos) + args.kd * (v_des - contact_vel)
        tau = J.T @ f_task + data.qfrc_bias[dofs]
        tau = np.clip(tau, model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1])
        data.ctrl[:] = tau
        mujoco.mj_step(model, data)

    warmup_target = data.site_xpos[contact_sid].copy()
    for _ in range(int(args.warmup / ctrl_dt) * sim_steps):
        apply_task_pd(warmup_target, np.zeros(3))

    mujoco.mj_forward(model, data)
    theta0 = float(data.qpos[rod_qadr])
    delta_r0 = float(data.qpos[radial_qadr])
    theta_goal = np.radians(args.target_deg)
    n_steps = int((args.duration + args.settle) / ctrl_dt)

    rows = []
    max_track_err = 0.0
    max_connection_err = 0.0
    max_sensor_pos_err = 0.0
    max_angle_sensor_err = 0.0
    max_stretch_sensor_err = 0.0
    max_site_orientation_err = initial_site_orientation_err
    max_delta_r = 0.0
    max_task_delta_r = 0.0
    max_tau = 0.0

    for step in range(n_steps):
        t = step * ctrl_dt
        phase = min(t / args.duration, 1.0)
        blend = smoothstep(phase)
        blend_dot = smoothstep_dot(phase, args.duration)
        theta_des = theta0 + (theta_goal - theta0) * blend
        theta_dot_des = (theta_goal - theta0) * blend_dot
        p_des = contact_target_from_known_geometry(model, data, theta_des)

        # Analytic target velocity for the current x-z arc.
        r = CONTACT_LOCAL
        c = np.cos(theta_des)
        s = np.sin(theta_des)
        dp_dtheta = np.array(
            [
                -s * r[0] - c * r[2],
                0.0,
                c * r[0] - s * r[2],
            ]
        )
        v_des = dp_dtheta * theta_dot_des

        for _ in range(sim_steps):
            apply_task_pd(p_des, v_des)

        mujoco.mj_forward(model, data)
        ee_pos = data.site_xpos[ee_sid].copy()
        contact_pos = data.site_xpos[contact_sid].copy()
        theta = float(data.qpos[rod_qadr])
        delta_r = float(data.qpos[radial_qadr])
        ee_sensor = sensor(model, data, "ee_pos")
        contact_sensor = sensor(model, data, "contact_pos")
        theta_sensor = float(sensor(model, data, "rod_angle")[0])
        stretch_sensor = float(sensor(model, data, "rod_stretch")[0])

        track_err = float(np.linalg.norm(contact_pos - p_des))
        connection_err = float(np.linalg.norm(ee_pos - contact_pos))
        sensor_pos_err = max(
            float(np.linalg.norm(ee_sensor - ee_pos)),
            float(np.linalg.norm(contact_sensor - contact_pos)),
        )
        angle_sensor_err = abs(theta_sensor - theta)
        stretch_sensor_err = abs(stretch_sensor - delta_r)
        site_orientation_err = site_orientation_error_deg(data, ee_sid, contact_sid)

        max_track_err = max(max_track_err, track_err)
        max_connection_err = max(max_connection_err, connection_err)
        max_sensor_pos_err = max(max_sensor_pos_err, sensor_pos_err)
        max_angle_sensor_err = max(max_angle_sensor_err, angle_sensor_err)
        max_stretch_sensor_err = max(max_stretch_sensor_err, stretch_sensor_err)
        max_site_orientation_err = max(max_site_orientation_err, site_orientation_err)
        max_delta_r = max(max_delta_r, abs(delta_r))
        max_task_delta_r = max(max_task_delta_r, abs(delta_r - delta_r0))
        max_tau = max(max_tau, float(np.max(np.abs(data.ctrl))))

        rows.append(
            {
                "t": t,
                "theta_des_deg": np.degrees(theta_des),
                "theta_deg": np.degrees(theta),
                "delta_r_mm": delta_r * 1000.0,
                "delta_r_task_mm": (delta_r - delta_r0) * 1000.0,
                "track_err_mm": track_err * 1000.0,
                "connection_err_mm": connection_err * 1000.0,
                "sensor_pos_err_mm": sensor_pos_err * 1000.0,
                "site_orientation_err_deg": site_orientation_err,
                "max_abs_tau": float(np.max(np.abs(data.ctrl))),
                "ee_x": ee_pos[0],
                "ee_y": ee_pos[1],
                "ee_z": ee_pos[2],
                "contact_x": contact_pos[0],
                "contact_y": contact_pos[1],
                "contact_z": contact_pos[2],
            }
        )

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    final_theta = float(data.qpos[rod_qadr])
    final_angle_err = abs(final_theta - theta_goal)
    print("Hardcoded scene check")
    print(f"  scene              : {SCENE_XML}")
    print(f"  csv                : {args.csv}")
    print(f"  initial IK error   : {ik_err * 1000.0:.2f} mm")
    print(f"  initial site R err : {initial_site_orientation_err:.2f} deg")
    print(f"  warmup             : {args.warmup:.2f} s")
    print(f"  post-warmup angle  : {np.degrees(theta0):.2f} deg")
    print(f"  post-warmup dr     : {delta_r0 * 1000.0:.2f} mm")
    print(f"  target qpos angle  : {args.target_deg:.2f} deg")
    print(f"  final qpos angle   : {np.degrees(final_theta):.2f} deg")
    print(f"  final angle error  : {np.degrees(final_angle_err):.2f} deg")
    print(f"  max tracking error : {max_track_err * 1000.0:.2f} mm")
    print(f"  max connect error  : {max_connection_err * 1000.0:.2f} mm")
    print(f"  max |delta_r|      : {max_delta_r * 1000.0:.2f} mm")
    print(f"  max task |delta_r| : {max_task_delta_r * 1000.0:.2f} mm")
    print(f"  max site R err     : {max_site_orientation_err:.2f} deg")
    print(f"  max |tau|          : {max_tau:.2f} Nm")
    print(f"  max sensor pos err : {max_sensor_pos_err * 1000.0:.6f} mm")
    print(f"  max angle sens err : {max_angle_sensor_err:.6e} rad")
    print(f"  max stretch err    : {max_stretch_sensor_err:.6e} m")

    passed = (
        np.degrees(final_angle_err) < 2.0
        and max_connection_err < 0.005
        and max_sensor_pos_err < 1e-9
        and max_angle_sensor_err < 1e-12
        and max_stretch_sensor_err < 1e-12
    )
    print(f"  pass basic checks  : {passed}")


if __name__ == "__main__":
    main()
