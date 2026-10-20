"""
MuJoCo environment: elastic rod traction with UR5e.

nq: [hinge_slide(0), rod_rotate(1), rod_radial(2), arm(3..8)]
arm_start = 3
theta  = qpos[1]  (rod_rotate angle)
delta_r = qpos[2]  (rod_radial stretch)

Gravity compensation on arm joints (qfrc_bias).
"""
import numpy as np
from pathlib import Path

try:
    import mujoco
    MUJOCO_AVAILABLE = True
except ImportError:
    MUJOCO_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCENE_XML = PROJECT_ROOT / 'assets' / 'mujoco' / 'scene_rod.xml'
L_ROD     = 0.35
S_CONTACT = 0.315
ARM_Q0    = [-1.5708, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]


class ElasticRodMuJoCo:
    def __init__(self, noise_pos=5e-5, noise_vel=1e-3):
        if not MUJOCO_AVAILABLE:
            raise ImportError("pip install mujoco")
        if not SCENE_XML.exists():
            raise FileNotFoundError("Run scripts/make_mujoco_scene.py first.")

        self.model = mujoco.MjModel.from_xml_path(str(SCENE_XML))
        self.data  = mujoco.MjData(self.model)

        self._ctrl_dt   = 1 / 50
        self._sim_steps = max(1, int(self._ctrl_dt / self.model.opt.timestep))
        self._noise_pos = noise_pos
        self._noise_vel = noise_vel

        self._ee_id      = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, 'attachment_site')
        self._contact_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, 'contact_site')

        self._n_rod     = 3   # hinge_slide + rod_rotate + rod_radial
        self._n_arm     = self.model.nu  # 6
        self._arm_start = self._n_rod    # 3

        mujoco.mj_resetData(self.model, self.data)
        self._init()

    def _init(self):
        self.data.qpos[0] = 0.0    # hinge_slide
        self.data.qpos[1] = 0.05   # rod_rotate ~3 deg
        self.data.qpos[2] = 0.0    # rod_radial
        for i, q in enumerate(ARM_Q0):
            self.data.qpos[self._arm_start + i] = q
        mujoco.mj_forward(self.model, self.data)
        self._ik_refine()

    def _ik_refine(self):
        target = self.data.site_xpos[self._contact_id].copy()
        nv, na, a0 = self.model.nv, self._n_arm, self._arm_start
        warm = [
            [-1.4709, 1.794, 1.1074, 1.7185, 0.4267, 1.1535],
            [-1.5, 1.8, 1.0, 1.7, 0.4, 1.2],
            [-1.3, 1.6, 1.2, 1.8, 0.5, 1.0],
        ]
        best_err, best_q = 1e9, None
        for cfg in warm:
            for i, q in enumerate(cfg):
                self.data.qpos[a0 + i] = q
            mujoco.mj_forward(self.model, self.data)
            e = np.linalg.norm(self.data.site_xpos[self._ee_id] - target)
            if e < best_err:
                best_err = e; best_q = self.data.qpos[a0:a0+na].copy()
        self.data.qpos[a0:a0+na] = best_q
        print(f"[IK] warm-start err: {best_err*1000:.0f} mm")

        for it in range(5000):
            mujoco.mj_forward(self.model, self.data)
            err = target - self.data.site_xpos[self._ee_id]
            err_norm = np.linalg.norm(err)
            if err_norm < 5e-4:
                break
            jacp = np.zeros((3, nv)); jacr = np.zeros((3, nv))
            mujoco.mj_jacSite(self.model, self.data, jacp, jacr, self._ee_id)
            J = jacp[:, a0:a0+na]
            lam = max(1e-4, err_norm * 0.1)
            dq = J.T @ np.linalg.solve(J @ J.T + lam * np.eye(3), err)
            dq = np.clip(dq, -min(0.2, err_norm*0.5), min(0.2, err_norm*0.5))
            self.data.qpos[a0:a0+na] += dq

        mujoco.mj_forward(self.model, self.data)
        err = np.linalg.norm(self.data.site_xpos[self._ee_id] - target)
        print(f"[IK] final err: {err*1000:.2f} mm  ({it+1} iters)")

    def observe_pos(self):
        pos = self.data.site_xpos[self._contact_id]
        return np.array([pos[0], pos[2]]) + np.random.randn(2) * self._noise_pos

    def observe_vel(self):
        vel = self.data.sensor('ee_vel').data
        return np.array([vel[0], vel[2]]) + np.random.randn(2) * self._noise_vel

    def step(self, F_world):
        F_3d = np.array([F_world[0], 0.0, F_world[1]])
        nv, na, a0 = self.model.nv, self._n_arm, self._arm_start
        for _ in range(self._sim_steps):
            mujoco.mj_forward(self.model, self.data)
            jacp = np.zeros((3, nv)); jacr = np.zeros((3, nv))
            mujoco.mj_jacSite(self.model, self.data, jacp, jacr, self._ee_id)
            J = jacp[:, a0:a0+na]
            tau_task = J.T @ F_3d
            tau_grav = self.data.qfrc_bias[a0:a0+na]
            tau = np.clip(tau_task + tau_grav, -150.0, 150.0)
            self.data.ctrl[:na] = tau
            mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        return self.theta, self.delta_r

    @property
    def theta(self):
        return float(self.data.qpos[1])

    @property
    def delta_r(self):
        return float(self.data.qpos[2])

    def get_joint_torques(self):
        return self.data.ctrl.copy()

    def get_arm_qpos(self):
        return self.data.qpos[self._arm_start:self._arm_start+self._n_arm].copy()


if __name__ == '__main__':
    if not SCENE_XML.exists():
        print("Run make_scene.py first!")
    elif MUJOCO_AVAILABLE:
        env = ElasticRodMuJoCo()
        p = env.observe_pos()
        print(f"Contact: x={p[0]:.4f}  z={p[1]:.4f}")
        print(f"theta={np.degrees(env.theta):.1f} deg  delta_r={env.delta_r*1000:.2f} mm")
        th, dr = env.step(np.array([0.0, 5.0]))
        print(f"1 step:  theta={np.degrees(th):.2f} deg  delta_r={dr*1000:.2f} mm")
        print("OK")
