"""Traceable torque-actuated ROKAE xMateCR12 V0 MuJoCo adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform


STAGE5_ROOT = Path(__file__).resolve().parents[2]
CR12_MODEL_PATH = STAGE5_ROOT / "models" / "cr12_v0.xml"
CR12_VENDOR_ROOT = STAGE5_ROOT / "vendor" / "rokae_ros2_xmatecr12"

CR12_JOINT_NAMES = tuple(f"joint{index}" for index in range(1, 7))
CR12_ACTUATOR_NAMES = tuple(f"joint{index}_torque" for index in range(1, 7))
CR12_VELOCITY_LIMITS_RAD_S = np.array(
    [
        2.0943951023931953,
        2.0943951023931953,
        3.141592653589793,
        4.084070449666731,
        4.1887902047863905,
        4.1887902047863905,
    ]
)
CR12_BODY_NAMES = (
    "xMateCR12_base",
    "xMateCR12_link1",
    "xMateCR12_link2",
    "xMateCR12_link3",
    "xMateCR12_link4",
    "xMateCR12_link5",
    "xMateCR12_link6",
)
CR12_FLANGE_SITE_NAME = "attachment_site"


@dataclass(frozen=True)
class CR12JacobianCheck:
    analytic_twist: np.ndarray
    finite_difference_twist: np.ndarray
    max_abs_error: float


class CR12TorqueRobot:
    """Robot-only CR12 V0 using official chain, limits, inertials, and meshes."""

    def __init__(self, model_path: Path = CR12_MODEL_PATH):
        self.model_path = Path(model_path)
        self.model = mujoco.MjModel.from_xml_path(str(self.model_path))
        self.data = mujoco.MjData(self.model)
        self.joint_ids = np.array(
            [self.model.joint(name).id for name in CR12_JOINT_NAMES]
        )
        self.qpos_indices = self.model.jnt_qposadr[self.joint_ids]
        self.dof_indices = self.model.jnt_dofadr[self.joint_ids]
        self.actuator_ids = np.array(
            [self.model.actuator(name).id for name in CR12_ACTUATOR_NAMES]
        )
        self.attachment_site_id = self.model.site(CR12_FLANGE_SITE_NAME).id
        self.attachment_body_id = int(
            self.model.site_bodyid[self.attachment_site_id]
        )
        self.reset_home()

    @property
    def joint_limits_rad(self) -> np.ndarray:
        return self.model.jnt_range[self.joint_ids].copy()

    @property
    def torque_limits_nm(self) -> np.ndarray:
        ranges = self.model.actuator_ctrlrange[self.actuator_ids]
        if not np.allclose(ranges[:, 0], -ranges[:, 1]):
            raise RuntimeError("CR12 V0 torque ranges must be symmetric")
        return ranges[:, 1].copy()

    @property
    def velocity_limits_rad_s(self) -> np.ndarray:
        """Official URDF velocity limits; MuJoCo has no native joint-speed limit."""

        return CR12_VELOCITY_LIMITS_RAD_S.copy()

    @property
    def home_q_rad(self) -> np.ndarray:
        key_id = self.model.key("home").id
        return self.model.key_qpos[key_id, self.qpos_indices].copy()

    def reset_home(self) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.model.key("home").id)
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def set_configuration(
        self, q_rad: np.ndarray, dq_rad_s: np.ndarray | None = None
    ) -> None:
        q = np.asarray(q_rad, dtype=float)
        dq = np.zeros(6) if dq_rad_s is None else np.asarray(dq_rad_s, dtype=float)
        if (
            q.shape != (6,)
            or dq.shape != (6,)
            or not np.all(np.isfinite(q))
            or not np.all(np.isfinite(dq))
        ):
            raise ValueError("q and dq must be finite six-vectors")
        limits = self.joint_limits_rad
        if np.any(q < limits[:, 0]) or np.any(q > limits[:, 1]):
            raise ValueError("configuration violates modeled CR12 joint limits")
        self.data.qpos[self.qpos_indices] = q
        self.data.qvel[self.dof_indices] = dq
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def attachment_pose(self) -> RigidTransform:
        return RigidTransform(
            self.data.site_xmat[self.attachment_site_id].reshape(3, 3),
            self.data.site_xpos[self.attachment_site_id],
        )

    def attachment_jacobian(self) -> np.ndarray:
        jacobian_position = np.zeros((3, self.model.nv))
        jacobian_rotation = np.zeros((3, self.model.nv))
        mujoco.mj_jacSite(
            self.model,
            self.data,
            jacobian_position,
            jacobian_rotation,
            self.attachment_site_id,
        )
        return np.vstack(
            [
                jacobian_position[:, self.dof_indices],
                jacobian_rotation[:, self.dof_indices],
            ]
        )

    def rigid_offset_jacobian(self, offset_in_attachment_m: np.ndarray) -> np.ndarray:
        offset = np.asarray(offset_in_attachment_m, dtype=float)
        if offset.shape != (3,) or not np.all(np.isfinite(offset)):
            raise ValueError("offset_in_attachment_m must be a finite three-vector")
        jacobian = self.attachment_jacobian()
        offset_base = self.attachment_pose().rotation @ offset
        skew = np.array(
            [
                [0.0, -offset_base[2], offset_base[1]],
                [offset_base[2], 0.0, -offset_base[0]],
                [-offset_base[1], offset_base[0], 0.0],
            ]
        )
        return np.vstack([jacobian[:3] - skew @ jacobian[3:], jacobian[3:]])

    def finite_difference_jacobian_check(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        *,
        epsilon_s: float = 1e-7,
    ) -> CR12JacobianCheck:
        q = np.asarray(q_rad, dtype=float)
        dq = np.asarray(dq_rad_s, dtype=float)
        self.set_configuration(q)
        analytic = self.attachment_jacobian() @ dq
        self.set_configuration(q + epsilon_s * dq)
        plus = self.attachment_pose()
        self.set_configuration(q - epsilon_s * dq)
        minus = self.attachment_pose()
        linear = (plus.translation - minus.translation) / (2.0 * epsilon_s)
        angular = Rotation.from_matrix(
            plus.rotation @ minus.rotation.T
        ).as_rotvec() / (2.0 * epsilon_s)
        numerical = np.concatenate([linear, angular])
        self.set_configuration(q)
        return CR12JacobianCheck(
            analytic,
            numerical,
            float(np.max(np.abs(analytic - numerical))),
        )

    def bias_torque_nm(self) -> np.ndarray:
        mujoco.mj_forward(self.model, self.data)
        return self.data.qfrc_bias[self.dof_indices].copy()

    def warning_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for index in range(int(mujoco.mjtWarning.mjNWARNING)):
            number = int(self.data.warning[index].number)
            if number:
                counts[mujoco.mjtWarning(index).name] = number
        return counts

    def contact_pairs(self) -> list[tuple[str, str]]:
        return [
            (
                self.model.geom(int(self.data.contact[index].geom1)).name,
                self.model.geom(int(self.data.contact[index].geom2)).name,
            )
            for index in range(self.data.ncon)
        ]
