"""Torque-actuated UR10e execution model and robot-side accounting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .frames import RigidTransform


STAGE_ROOT = Path(__file__).resolve().parents[2]
TORQUE_MODEL_PATH = STAGE_ROOT / "models" / "ur10e_torque.xml"
VENDOR_MODEL_PATH = (
    STAGE_ROOT
    / "vendor"
    / "mujoco_menagerie"
    / "universal_robots_ur10e"
    / "ur10e.xml"
)

JOINT_NAMES = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)
ACTUATOR_NAMES = (
    "shoulder_pan_torque",
    "shoulder_lift_torque",
    "elbow_torque",
    "wrist_1_torque",
    "wrist_2_torque",
    "wrist_3_torque",
)
BODY_NAMES = (
    "base",
    "shoulder_link",
    "upper_arm_link",
    "forearm_link",
    "wrist_1_link",
    "wrist_2_link",
    "wrist_3_link",
)
ATTACHMENT_SITE_NAME = "attachment_site"


@dataclass(frozen=True)
class JacobianCheck:
    analytic_twist: np.ndarray
    finite_difference_twist: np.ndarray
    max_abs_error: float


class UR10eTorqueRobot:
    """Independent robot-only plant; no Human V2 or cuff constraint is present."""

    def __init__(self, model_path: Path = TORQUE_MODEL_PATH):
        self.model_path = Path(model_path)
        self.model = mujoco.MjModel.from_xml_path(str(self.model_path))
        self.data = mujoco.MjData(self.model)
        self.joint_ids = np.array([self.model.joint(name).id for name in JOINT_NAMES])
        self.qpos_indices = self.model.jnt_qposadr[self.joint_ids]
        self.dof_indices = self.model.jnt_dofadr[self.joint_ids]
        self.actuator_ids = np.array(
            [self.model.actuator(name).id for name in ACTUATOR_NAMES]
        )
        self.attachment_site_id = self.model.site(ATTACHMENT_SITE_NAME).id
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
            raise RuntimeError("UR10e torque limits are expected to be symmetric")
        return ranges[:, 1].copy()

    @property
    def home_q_rad(self) -> np.ndarray:
        key_id = self.model.key("home").id
        return self.model.key_qpos[key_id, self.qpos_indices].copy()

    def reset_home(self) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.model.key("home").id)
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def set_configuration(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray | None = None,
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
            raise ValueError("configuration violates modeled UR10e joint limits")
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

    def finite_difference_jacobian_check(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        *,
        epsilon_s: float = 1e-7,
    ) -> JacobianCheck:
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
        return JacobianCheck(
            analytic,
            numerical,
            float(np.max(np.abs(analytic - numerical))),
        )

    def command_torque(self, torque_nm: np.ndarray) -> np.ndarray:
        torque = np.asarray(torque_nm, dtype=float)
        if torque.shape != (6,) or not np.all(np.isfinite(torque)):
            raise ValueError("joint torque command must be a finite six-vector")
        if np.any(np.abs(torque) > self.torque_limits_nm + 1e-12):
            raise ValueError("joint torque command exceeds modeled actuator limits")
        self.data.ctrl[self.actuator_ids] = torque
        mujoco.mj_forward(self.model, self.data)
        return self.data.qfrc_actuator[self.dof_indices].copy()

    def bias_torque_nm(self) -> np.ndarray:
        mujoco.mj_forward(self.model, self.data)
        return self.data.qfrc_bias[self.dof_indices].copy()

    def wrench_to_joint_torque(self, wrench_base: np.ndarray) -> np.ndarray:
        wrench = np.asarray(wrench_base, dtype=float)
        if wrench.shape != (6,) or not np.all(np.isfinite(wrench)):
            raise ValueError("wrench must be a finite [force, moment] six-vector")
        return self.attachment_jacobian().T @ wrench

    def mujoco_applied_wrench_generalized_force(
        self,
        wrench_base: np.ndarray,
    ) -> np.ndarray:
        wrench = np.asarray(wrench_base, dtype=float)
        generalized = np.zeros(self.model.nv)
        mujoco.mj_applyFT(
            self.model,
            self.data,
            wrench[:3],
            wrench[3:],
            self.data.site_xpos[self.attachment_site_id],
            self.attachment_body_id,
            generalized,
        )
        return generalized[self.dof_indices]

    def warning_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for index in range(int(mujoco.mjtWarning.mjNWARNING)):
            warning_type = mujoco.mjtWarning(index)
            number = int(self.data.warning[index].number)
            if number:
                counts[warning_type.name] = number
        return counts

    def contact_pairs(self) -> list[tuple[str, str]]:
        pairs = []
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            geom1 = int(contact.geom1)
            geom2 = int(contact.geom2)
            pairs.append(
                (
                    self.model.geom(geom1).name or f"geom#{geom1}",
                    self.model.geom(geom2).name or f"geom#{geom2}",
                )
            )
        return pairs
