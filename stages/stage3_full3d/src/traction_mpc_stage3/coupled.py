"""UR10e--Human V2 plant with an explicit rigid six-constraint cuff."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .frames import WORLD_FROM_BASE, base_from_attachment_target
from .human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    HumanV2Parameters,
    sleeve_jacobian,
    soft_limit_torque,
)
from .ik import _initial_solution
from .reference import _world_from_cuff
from .robot import ACTUATOR_NAMES, JOINT_NAMES, TORQUE_MODEL_PATH, UR10eTorqueRobot


SIMULATION_DT_S = 0.001
CONTROL_DT_S = 0.005
CONTROL_SUBSTEPS = 5
BED_HEIGHT_M = 0.012
HIP_HEIGHT_M = 0.062
BED_FRICTION = 0.70
BED_SOLREF = (0.020, 1.0)
BED_SOLIMP = (0.90, 0.98, 0.003)
SLEEVE_SOLREF = (-6000.0, -120.0)
SLEEVE_SOLIMP = (0.97, 0.995, 0.0005)
SLEEVE_HALF_LENGTH_M = 0.040
SLEEVE_OUTER_RADIUS_M = 0.058
THIGH_RADIUS_M = 0.050
SHANK_RADIUS_M = 0.045


class CuffForceCommandLimitError(RuntimeError):
    def __init__(self, force_norm_n: float) -> None:
        self.force_norm_n = float(force_norm_n)
        super().__init__(
            f"cuff force command {force_norm_n:.6g} N exceeds "
            f"{CUFF_TRANSLATIONAL_FORCE_GATE_N:.6g} N"
        )


def build_coupled_model_xml(human: HumanV2Parameters = HUMAN) -> str:
    """Build the coupled MJCF from the committed torque-model structure."""

    root = ET.parse(TORQUE_MODEL_PATH).getroot()
    root.set("model", "ur10e_human_v2_rigid_cuff")
    compiler = root.find("compiler")
    assert compiler is not None
    asset_dir = TORQUE_MODEL_PATH.parent.parent / "vendor" / "mujoco_menagerie" / "universal_robots_ur10e" / "assets"
    compiler.set("meshdir", str(asset_dir.resolve()))
    option = root.find("option")
    assert option is not None
    option.set("timestep", f"{SIMULATION_DT_S:.9g}")
    option.set("gravity", f"0 0 -{human.gravity_m_s2:.9g}")
    option.set("integrator", "implicitfast")
    option.set("cone", "elliptic")
    option.set("iterations", "100")

    worldbody = root.find("worldbody")
    assert worldbody is not None
    base = worldbody.find("body[@name='base']")
    assert base is not None
    base.set("pos", " ".join(f"{value:.12g}" for value in WORLD_FROM_BASE.translation))
    # Collision bit domains preserve the intended mechanics while preventing
    # the newly combined models from adding robot--bed or robot--human contact:
    # robot self=bit 1, Human=bit 2, bed=bit 4. Human and bed cross-affinities
    # retain exactly the frozen unilateral contact law below.
    for geom in base.iter("geom"):
        geom_class = geom.get("class", "")
        if geom_class in {"collision", "eef_collision"}:
            geom.set("contype", "1")
            geom.set("conaffinity", "1")

    i1_half = 0.51 * human.thigh_inertia_kg_m2
    i2_half = 0.51 * human.shank_inertia_kg_m2
    sc = human.sleeve_center_m
    friction = f"{BED_FRICTION:.9g} 0.01 0.001"
    solref = f"{BED_SOLREF[0]:.9g} {BED_SOLREF[1]:.9g}"
    solimp = f"{BED_SOLIMP[0]:.9g} {BED_SOLIMP[1]:.9g} {BED_SOLIMP[2]:.9g}"
    human_xml = f"""
    <geom name="bed" type="plane" pos="0 0 {BED_HEIGHT_M:.9g}"
      size="1.6 1.0 0.05" rgba="0.55 0.70 0.82 1"
      contype="4" conaffinity="2"
      friction="{friction}" solref="{solref}" solimp="{solimp}"/>
    <body name="hip" pos="0 0 {HIP_HEIGHT_M:.9g}">
      <joint name="hip_joint" type="hinge" axis="0 -1 0"
        range="{human.q_min_rad[0]:.12g} {human.q_max_rad[0]:.12g}"
        armature="0" stiffness="{human.passive_stiffness_nm_rad[0]:.9g}"
        damping="{human.passive_damping_nms_rad[0]:.9g}"
        springref="{human.q_rest_rad[0]:.12g}"/>
      <inertial pos="{human.thigh_com_m:.12g} 0 0" mass="{human.thigh_mass_kg:.12g}"
        diaginertia="{i1_half:.12g} {human.thigh_inertia_kg_m2:.12g} {i1_half:.12g}"/>
      <geom name="thigh_geom" type="capsule"
        fromto="0 0 0 {human.thigh_length_m:.12g} 0 0" size="{THIGH_RADIUS_M:.9g}"
        contype="2" conaffinity="4"
        rgba="0.24 0.48 0.82 1" friction="{friction}" solref="{solref}" solimp="{solimp}"/>
      <body name="shank" pos="{human.thigh_length_m:.12g} 0 0">
        <joint name="knee_joint" type="hinge" axis="0 1 0"
          range="{human.q_min_rad[1]:.12g} {human.q_max_rad[1]:.12g}"
          armature="0" stiffness="{human.passive_stiffness_nm_rad[1]:.9g}"
          damping="{human.passive_damping_nms_rad[1]:.9g}"
          springref="{human.q_rest_rad[1]:.12g}"/>
        <inertial pos="{human.shank_com_m:.12g} 0 0" mass="{human.shank_mass_kg:.12g}"
          diaginertia="{i2_half:.12g} {human.shank_inertia_kg_m2:.12g} {i2_half:.12g}"/>
        <geom name="shank_geom" type="capsule"
          fromto="0 0 0 {human.shank_length_m:.12g} 0 0" size="{SHANK_RADIUS_M:.9g}"
          contype="2" conaffinity="4"
          rgba="0.90 0.48 0.18 1" friction="{friction}" solref="{solref}" solimp="{solimp}"/>
        <geom name="sleeve_geom" type="cylinder"
          fromto="{sc - SLEEVE_HALF_LENGTH_M:.12g} 0 0 {sc + SLEEVE_HALF_LENGTH_M:.12g} 0 0"
          size="{SLEEVE_OUTER_RADIUS_M:.9g}" rgba="0.62 0.22 0.80 0.75"
          contype="0" conaffinity="0"/>
        <site name="sleeve_attach_site" pos="{sc:.12g} 0 0"
          size="0.014" rgba="0.90 0.10 0.75 1"/>
      </body>
    </body>
    """
    human_elements = list(ET.fromstring(f"<elements>{human_xml}</elements>"))
    base_index = list(worldbody).index(base)
    for offset, element in enumerate(human_elements):
        worldbody.insert(base_index + offset, element)

    equality = root.find("equality")
    if equality is None:
        equality = ET.Element("equality")
        actuator = root.find("actuator")
        root.insert(list(root).index(actuator), equality)
    ET.SubElement(
        equality,
        "weld",
        {
            "name": "sleeve_connection",
            "site1": "attachment_site",
            "site2": "sleeve_attach_site",
            "solref": f"{SLEEVE_SOLREF[0]:.9g} {SLEEVE_SOLREF[1]:.9g}",
            "solimp": (
                f"{SLEEVE_SOLIMP[0]:.9g} {SLEEVE_SOLIMP[1]:.9g} "
                f"{SLEEVE_SOLIMP[2]:.9g}"
            ),
        },
    )
    return ET.tostring(root, encoding="unicode")


@dataclass(frozen=True)
class CoupledObservation:
    time_s: float
    human_q_rad: np.ndarray
    human_dq_rad_s: np.ndarray
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    attachment_position_m: np.ndarray
    attachment_rotation_matrix: np.ndarray
    attachment_velocity_m_s: np.ndarray
    attachment_angular_velocity_rad_s: np.ndarray
    cuff_force_vector_n: np.ndarray
    cuff_moment_vector_nm: np.ndarray
    cuff_wrench_reconstruction_residual_nm: float
    human_constraint_torque_nm: np.ndarray
    human_wrench_torque_nm: np.ndarray
    human_wrench_torque_residual_nm: float
    weld_position_error_m: float
    weld_rotation_error_rad: float
    bed_force_n: float
    bed_penetration_m: float
    bed_contact_count: int
    unintended_contact_pairs: tuple[tuple[str, str], ...]
    joint_torque_command_nm: np.ndarray
    unclipped_joint_torque_nm: np.ndarray
    cartesian_force_command_n: np.ndarray
    cartesian_moment_command_nm: np.ndarray


class CoupledUR10eHumanV2:
    """Eight-DoF plant: six UR10e joints and frozen planar Human V2."""

    def __init__(self, human: HumanV2Parameters = HUMAN) -> None:
        self.human = human
        self.model = mujoco.MjModel.from_xml_string(build_coupled_model_xml(human))
        self.data = mujoco.MjData(self.model)
        self.human_joint_names = ("hip_joint", "knee_joint")
        self.robot_joint_names = JOINT_NAMES
        self.human_joint_ids = np.array([self.model.joint(n).id for n in self.human_joint_names])
        self.robot_joint_ids = np.array([self.model.joint(n).id for n in self.robot_joint_names])
        self.human_qpos_indices = self.model.jnt_qposadr[self.human_joint_ids]
        self.robot_qpos_indices = self.model.jnt_qposadr[self.robot_joint_ids]
        self.human_dof_indices = self.model.jnt_dofadr[self.human_joint_ids]
        self.robot_dof_indices = self.model.jnt_dofadr[self.robot_joint_ids]
        self.actuator_ids = np.array([self.model.actuator(n).id for n in ACTUATOR_NAMES])
        self.attachment_site_id = self.model.site("attachment_site").id
        self.sleeve_site_id = self.model.site("sleeve_attach_site").id
        self.weld_id = self.model.equality("sleeve_connection").id
        self.bed_geom_id = self.model.geom("bed").id
        self.human_geom_ids = {
            self.model.geom("thigh_geom").id,
            self.model.geom("shank_geom").id,
        }
        self.robot_collision_geom_ids = {
            geom_id
            for geom_id in range(self.model.ngeom)
            if int(self.model.geom_group[geom_id]) == 3
        }
        self._ik_robot = UR10eTorqueRobot()
        self.neutral_robot_q = np.zeros(6)
        self.last_joint_torque = np.zeros(6)
        self.last_unclipped_joint_torque = np.zeros(6)
        self.last_force = np.zeros(3)
        self.last_moment = np.zeros(3)

    @property
    def torque_limits_nm(self) -> np.ndarray:
        return self.model.actuator_ctrlrange[self.actuator_ids, 1].copy()

    def reset(self, human_q_rad: np.ndarray) -> CoupledObservation:
        q = np.asarray(human_q_rad, dtype=float)
        if q.shape != (2,) or not np.all(np.isfinite(q)):
            raise ValueError("human_q_rad must be a finite two-vector")
        limits = np.column_stack([self.human.q_min_rad, self.human.q_max_rad])
        if np.any(q < limits[:, 0]) or np.any(q > limits[:, 1]):
            raise ValueError("Human V2 reset posture violates ROM")
        target = base_from_attachment_target(_world_from_cuff(q))
        robot_q = _initial_solution(self._ik_robot, target)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.human_qpos_indices] = q
        self.data.qpos[self.robot_qpos_indices] = robot_q
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self.data.eq_active[self.weld_id] = 1
        self.neutral_robot_q = robot_q.copy()
        self.last_joint_torque[:] = 0.0
        self.last_unclipped_joint_torque[:] = 0.0
        self.last_force[:] = 0.0
        self.last_moment[:] = 0.0
        self._apply_soft_limit()
        mujoco.mj_forward(self.model, self.data)
        return self.observe()

    def _site_pose_jacobian(self, site_id: int) -> np.ndarray:
        jp = np.zeros((3, self.model.nv))
        jr = np.zeros((3, self.model.nv))
        mujoco.mj_jacSite(self.model, self.data, jp, jr, site_id)
        return np.vstack([jp, jr])

    def robot_attachment_jacobian(self) -> np.ndarray:
        return self._site_pose_jacobian(self.attachment_site_id)[:, self.robot_dof_indices]

    def _site_velocity(self, site_id: int) -> tuple[np.ndarray, np.ndarray]:
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(
            self.model, self.data, mujoco.mjtObj.mjOBJ_SITE, site_id, velocity, 0
        )
        return velocity[:3].copy(), velocity[3:].copy()

    @staticmethod
    def _rotation_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
        return Rotation.from_matrix(np.asarray(target) @ np.asarray(current).T).as_rotvec()

    def reconstruct_cuff_wrench(self) -> tuple[np.ndarray, float, np.ndarray, float]:
        equality_type = int(mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        rows = np.flatnonzero(
            (self.data.efc_type[: self.data.nefc] == equality_type)
            & (self.data.efc_id[: self.data.nefc] == self.weld_id)
        )
        if len(rows) != 6:
            return np.zeros(6), 0.0, np.zeros(2), 0.0
        multipliers = np.zeros(self.data.nefc)
        multipliers[rows] = self.data.efc_force[rows]
        equality_qfrc = np.zeros(self.model.nv)
        mujoco.mj_mulJacTVec(self.model, self.data, equality_qfrc, multipliers)
        robot_j = self._site_pose_jacobian(self.attachment_site_id)
        human_j = self._site_pose_jacobian(self.sleeve_site_id)
        wrench_map = (human_j - robot_j).T
        wrench, _, _, _ = np.linalg.lstsq(wrench_map, equality_qfrc, rcond=None)
        reconstruction_residual = float(np.linalg.norm(wrench_map @ wrench - equality_qfrc))
        human_tau = human_j[:, self.human_dof_indices].T @ wrench
        constraint_tau = equality_qfrc[self.human_dof_indices]
        torque_residual = float(np.linalg.norm(human_tau - constraint_tau))
        return wrench, reconstruction_residual, constraint_tau, torque_residual

    def _bed_metrics(self) -> tuple[float, float, int]:
        total_force = 0.0
        penetration = 0.0
        count = 0
        contact_force = np.zeros(6)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            pair = {int(contact.geom1), int(contact.geom2)}
            if self.bed_geom_id not in pair or not (pair & self.human_geom_ids):
                continue
            mujoco.mj_contactForce(self.model, self.data, index, contact_force)
            total_force += max(0.0, float(contact_force[0]))
            penetration = max(penetration, max(0.0, -float(contact.dist)))
            count += 1
        return total_force, penetration, count

    def contact_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (
                self.model.geom(int(self.data.contact[i].geom1)).name,
                self.model.geom(int(self.data.contact[i].geom2)).name,
            )
            for i in range(self.data.ncon)
        )

    def _unintended_contact_pairs(self) -> tuple[tuple[str, str], ...]:
        unintended = []
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            ids = {int(contact.geom1), int(contact.geom2)}
            human_bed = self.bed_geom_id in ids and bool(ids & self.human_geom_ids)
            robot_self = ids <= self.robot_collision_geom_ids
            if not human_bed and not robot_self:
                unintended.append(
                    (
                        self.model.geom(int(contact.geom1)).name,
                        self.model.geom(int(contact.geom2)).name,
                    )
                )
        return tuple(unintended)

    def observe(self) -> CoupledObservation:
        attachment_position = self.data.site_xpos[self.attachment_site_id].copy()
        sleeve_position = self.data.site_xpos[self.sleeve_site_id].copy()
        attachment_rotation = self.data.site_xmat[self.attachment_site_id].reshape(3, 3).copy()
        sleeve_rotation = self.data.site_xmat[self.sleeve_site_id].reshape(3, 3).copy()
        angular_velocity, linear_velocity = self._site_velocity(self.attachment_site_id)
        wrench, residual, constraint_tau, tau_residual = self.reconstruct_cuff_wrench()
        bed_force, bed_penetration, bed_count = self._bed_metrics()
        return CoupledObservation(
            time_s=float(self.data.time),
            human_q_rad=self.data.qpos[self.human_qpos_indices].copy(),
            human_dq_rad_s=self.data.qvel[self.human_dof_indices].copy(),
            robot_q_rad=self.data.qpos[self.robot_qpos_indices].copy(),
            robot_dq_rad_s=self.data.qvel[self.robot_dof_indices].copy(),
            attachment_position_m=attachment_position,
            attachment_rotation_matrix=attachment_rotation,
            attachment_velocity_m_s=linear_velocity,
            attachment_angular_velocity_rad_s=angular_velocity,
            cuff_force_vector_n=wrench[:3].copy(),
            cuff_moment_vector_nm=wrench[3:].copy(),
            cuff_wrench_reconstruction_residual_nm=residual,
            human_constraint_torque_nm=constraint_tau.copy(),
            human_wrench_torque_nm=(
                self._site_pose_jacobian(self.sleeve_site_id)[:, self.human_dof_indices].T @ wrench
            ),
            human_wrench_torque_residual_nm=tau_residual,
            weld_position_error_m=float(np.linalg.norm(attachment_position - sleeve_position)),
            weld_rotation_error_rad=float(
                np.linalg.norm(self._rotation_error(sleeve_rotation, attachment_rotation))
            ),
            bed_force_n=bed_force,
            bed_penetration_m=bed_penetration,
            bed_contact_count=bed_count,
            unintended_contact_pairs=self._unintended_contact_pairs(),
            joint_torque_command_nm=self.last_joint_torque.copy(),
            unclipped_joint_torque_nm=self.last_unclipped_joint_torque.copy(),
            cartesian_force_command_n=self.last_force.copy(),
            cartesian_moment_command_nm=self.last_moment.copy(),
        )

    def _apply_soft_limit(self) -> None:
        q = self.data.qpos[self.human_qpos_indices]
        dq = self.data.qvel[self.human_dof_indices]
        self.data.qfrc_applied[:] = 0.0
        self.data.qfrc_applied[self.human_dof_indices] = soft_limit_torque(q, dq, self.human)

    def apply_nominal_cartesian_control(
        self,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray,
        target_angular_velocity_rad_s: np.ndarray,
        feedforward_wrench_world: np.ndarray,
    ) -> None:
        observation = self.observe()
        force = 3000.0 * (np.asarray(target_position_m) - observation.attachment_position_m)
        force += 140.0 * (np.asarray(target_velocity_m_s) - observation.attachment_velocity_m_s)
        force = np.clip(force, -200.0, 200.0)
        moment = 120.0 * self._rotation_error(
            np.asarray(target_rotation_matrix), observation.attachment_rotation_matrix
        )
        moment += 12.0 * (
            np.asarray(target_angular_velocity_rad_s)
            - observation.attachment_angular_velocity_rad_s
        )
        feedforward = np.asarray(feedforward_wrench_world, dtype=float)
        if feedforward.shape != (6,) or not np.all(np.isfinite(feedforward)):
            raise ValueError("feedforward_wrench_world must be a finite six-vector")
        force += feedforward[:3]
        moment += feedforward[3:]
        force_norm = float(np.linalg.norm(force))
        if force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9:
            raise CuffForceCommandLimitError(force_norm)

        jacobian = self.robot_attachment_jacobian()
        pinv = jacobian.T @ np.linalg.inv(jacobian @ jacobian.T + 1e-4 * np.eye(6))
        nullspace = np.eye(6) - pinv @ jacobian
        q = observation.robot_q_rad
        dq = observation.robot_dq_rad_s
        posture = 12.0 * (self.neutral_robot_q - q) - 3.0 * dq
        torque = self.data.qfrc_bias[self.robot_dof_indices].copy()
        torque += jacobian.T @ np.concatenate([force, moment]) + nullspace.T @ posture
        self.last_unclipped_joint_torque = torque.copy()
        torque = np.clip(torque, -self.torque_limits_nm, self.torque_limits_nm)
        self.data.ctrl[self.actuator_ids] = torque
        self.last_joint_torque = torque.copy()
        self.last_force = force.copy()
        self.last_moment = moment.copy()

    def step(self) -> CoupledObservation:
        self._apply_soft_limit()
        mujoco.mj_step(self.model, self.data)
        return self.observe()

    def warning_counts(self) -> dict[str, int]:
        counts = {}
        for index in range(int(mujoco.mjtWarning.mjNWARNING)):
            count = int(self.data.warning[index].number)
            if count:
                counts[mujoco.mjtWarning(index).name] = count
        return counts


def human_cuff_velocity(q_rad: np.ndarray, dq_rad_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    linear = sleeve_jacobian(q_rad) @ np.asarray(dq_rad_s)
    angular = np.array([0.0, dq_rad_s[1] - dq_rad_s[0], 0.0])
    return linear, angular
