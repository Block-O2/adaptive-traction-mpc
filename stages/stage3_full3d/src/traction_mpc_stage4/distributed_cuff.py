"""Rejected explicit-penalty cuff diagnostic; not an active Stage-4 plant.

The robot attachment frame and the cuff are one rigid body.  Four axial
stations couple that body to matching shank stations with equal-and-opposite
point forces.  No station applies a direct moment; the resultant moment arises
only from force lever arms about the cuff center.

This module is retained only to reproduce the failed zero-preload engineering
experiment.  The recommended finite-surface model keeps the validated rigid
plant and uses :mod:`traction_mpc_stage4.surface_loads` for load decomposition.
Its stiffness and damping are engineering assumptions, not measured hardware.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from traction_mpc_stage3.coupled import (
    SLEEVE_OUTER_RADIUS_M,
    CoupledObservation,
    build_coupled_model_xml,
)
from traction_mpc_stage3.frames import base_from_attachment_target
from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, sleeve_position, soft_limit_torque
from traction_mpc_stage3.ik import _initial_solution
from traction_mpc_stage3.reference import _world_from_cuff
from traction_mpc_stage3.robot import ACTUATOR_NAMES, JOINT_NAMES, UR10eTorqueRobot

from .sensor_realism import SensorBoundaryStage4Plant


@dataclass(frozen=True)
class DistributedCuffConfig:
    station_count: int = 4
    cuff_length_m: float = 0.080
    translational_stiffness_per_length_n_m2: float = 10_000_000.0
    translational_damping_per_length_ns_m2: float = 1_000.0

    def __post_init__(self) -> None:
        if self.station_count != 4:
            raise ValueError("the first distributed-cuff plant requires exactly four stations")
        if not 0.0 < self.cuff_length_m:
            raise ValueError("cuff_length_m must be positive")
        if self.translational_stiffness_per_length_n_m2 <= 0.0:
            raise ValueError("translational stiffness per length must be positive")
        if self.translational_damping_per_length_ns_m2 < 0.0:
            raise ValueError("translational damping per length must be nonnegative")

    @property
    def station_segment_length_m(self) -> float:
        return self.cuff_length_m / self.station_count

    @property
    def station_offsets_m(self) -> np.ndarray:
        indices = np.arange(self.station_count, dtype=float)
        return ((indices + 0.5) / self.station_count - 0.5) * self.cuff_length_m

    @property
    def station_stiffness_n_m(self) -> float:
        return (
            self.translational_stiffness_per_length_n_m2
            * self.station_segment_length_m
        )

    @property
    def station_damping_ns_m(self) -> float:
        return (
            self.translational_damping_per_length_ns_m2
            * self.station_segment_length_m
        )

    @property
    def total_translational_stiffness_n_m(self) -> float:
        return self.translational_stiffness_per_length_n_m2 * self.cuff_length_m

    @property
    def sagittal_rotational_stiffness_nm_rad(self) -> float:
        return float(
            self.station_stiffness_n_m * np.sum(self.station_offsets_m**2)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "station_offsets_m": self.station_offsets_m.tolist(),
            "station_segment_length_m": self.station_segment_length_m,
            "station_stiffness_n_m": self.station_stiffness_n_m,
            "station_damping_ns_m": self.station_damping_ns_m,
            "total_translational_stiffness_n_m": self.total_translational_stiffness_n_m,
            "sagittal_rotational_stiffness_nm_rad": self.sagittal_rotational_stiffness_nm_rad,
            "hardware_measured": False,
            "surface_coupling_assumption": (
                "uniform axial line support; each Cartesian spring-damper station represents one equal cuff-length segment"
            ),
            "constitutive_note": (
                "explicit equal-and-opposite point force f_i = K_i delta_x_i + D_i delta_v_i; coefficients are engineering assumptions, not measured hardware"
            ),
        }


def build_distributed_cuff_model_xml(
    human: HumanV2Parameters = HUMAN,
    config: DistributedCuffConfig = DistributedCuffConfig(),
) -> str:
    """Replace the frozen single weld with four finite translational stations."""

    root = ET.fromstring(build_coupled_model_xml(human))
    root.set("model", "ur10e_human_v2_distributed_rigid_cuff")
    equality = root.find("equality")
    if equality is not None:
        for weld in list(equality.findall("weld")):
            if weld.get("name") == "sleeve_connection":
                equality.remove(weld)

    shank = root.find(".//body[@name='shank']")
    wrist = root.find(".//body[@name='wrist_3_link']")
    attachment_site = root.find(".//site[@name='attachment_site']")
    if shank is None or wrist is None or attachment_site is None:
        raise RuntimeError("required shank/wrist/attachment elements are missing")

    old_visual = shank.find("geom[@name='sleeve_geom']")
    if old_visual is not None:
        shank.remove(old_visual)

    cuff_body = ET.SubElement(
        wrist,
        "body",
        {
            "name": "rigid_cuff_body",
            "pos": attachment_site.get("pos", "0 0 0"),
            "quat": attachment_site.get("quat", "1 0 0 0"),
        },
    )
    half_length = 0.5 * config.cuff_length_m
    ET.SubElement(
        cuff_body,
        "geom",
        {
            "name": "distributed_cuff_visual",
            "type": "cylinder",
            "fromto": f"{-half_length:.12g} 0 0 {half_length:.12g} 0 0",
            "size": f"{SLEEVE_OUTER_RADIUS_M:.12g}",
            "rgba": "0.62 0.22 0.80 0.75",
            "group": "2",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    for index, offset in enumerate(config.station_offsets_m):
        position = f"{offset:.12g} 0 0"
        ET.SubElement(
            cuff_body,
            "site",
            {
                "name": f"cuff_station_{index}",
                "pos": position,
                "size": "0.006",
                "rgba": "0.95 0.20 0.85 1",
                "group": "4",
            },
        )
        ET.SubElement(
            shank,
            "site",
            {
                "name": f"shank_station_{index}",
                "pos": f"{human.sleeve_center_m + offset:.12g} 0 0",
                "size": "0.005",
                "rgba": "0.15 0.85 0.30 1",
                "group": "4",
            },
        )
    return ET.tostring(root, encoding="unicode")


@dataclass(frozen=True)
class DistributedCuffObservation(CoupledObservation):
    station_offsets_m: np.ndarray
    station_force_world_n: np.ndarray
    station_relative_translation_world_m: np.ndarray
    station_relative_speed_world_m_s: np.ndarray
    cuff_center_relative_translation_world_m: np.ndarray
    cuff_shank_relative_rotation_rad: float


class DistributedCuffStage4Plant(SensorBoundaryStage4Plant):
    """Stage-4 plant whose cuff-to-shank mechanics are distributed point forces."""

    def __init__(
        self,
        human: HumanV2Parameters = HUMAN,
        config: DistributedCuffConfig = DistributedCuffConfig(),
    ) -> None:
        self.human = human
        self.cuff_config = config
        self.model = mujoco.MjModel.from_xml_string(
            build_distributed_cuff_model_xml(human, config)
        )
        self.data = mujoco.MjData(self.model)
        self.human_joint_names = ("hip_joint", "knee_joint")
        self.robot_joint_names = JOINT_NAMES
        self.human_joint_ids = np.array(
            [self.model.joint(name).id for name in self.human_joint_names]
        )
        self.robot_joint_ids = np.array(
            [self.model.joint(name).id for name in self.robot_joint_names]
        )
        self.human_qpos_indices = self.model.jnt_qposadr[self.human_joint_ids]
        self.robot_qpos_indices = self.model.jnt_qposadr[self.robot_joint_ids]
        self.human_dof_indices = self.model.jnt_dofadr[self.human_joint_ids]
        self.robot_dof_indices = self.model.jnt_dofadr[self.robot_joint_ids]
        self.actuator_ids = np.array(
            [self.model.actuator(name).id for name in ACTUATOR_NAMES]
        )
        self.attachment_site_id = self.model.site("attachment_site").id
        self.sleeve_site_id = self.model.site("sleeve_attach_site").id
        self.cuff_station_site_ids = np.array(
            [self.model.site(f"cuff_station_{index}").id for index in range(4)]
        )
        self.shank_station_site_ids = np.array(
            [self.model.site(f"shank_station_{index}").id for index in range(4)]
        )
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
        self._measured_robot_model = UR10eTorqueRobot()
        self.neutral_robot_q = np.zeros(6)
        self.last_joint_torque = np.zeros(6)
        self.last_unclipped_joint_torque = np.zeros(6)
        self.last_force = np.zeros(3)
        self.last_moment = np.zeros(3)

    def reset(self, human_q_rad: np.ndarray) -> DistributedCuffObservation:
        q = np.asarray(human_q_rad, dtype=float)
        if q.shape != (2,) or not np.all(np.isfinite(q)):
            raise ValueError("human_q_rad must be a finite two-vector")
        limits = np.column_stack([self.human.q_min_rad, self.human.q_max_rad])
        if np.any(q < limits[:, 0]) or np.any(q > limits[:, 1]):
            raise ValueError("Human V2 reset posture violates ROM")
        nominal_pose = _world_from_cuff(q)
        true_pose = type(nominal_pose)(
            nominal_pose.rotation,
            sleeve_position(q, self.human),
        )
        robot_q = _initial_solution(
            self._ik_robot,
            base_from_attachment_target(true_pose),
        )
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.human_qpos_indices] = q
        self.data.qpos[self.robot_qpos_indices] = robot_q
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self.neutral_robot_q = robot_q.copy()
        self.last_joint_torque[:] = 0.0
        self.last_unclipped_joint_torque[:] = 0.0
        self.last_force[:] = 0.0
        self.last_moment[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self._apply_soft_limit()
        return self.observe()

    def _station_state(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        cuff_positions = self.data.site_xpos[self.cuff_station_site_ids].copy()
        shank_positions = self.data.site_xpos[self.shank_station_site_ids].copy()
        cuff_velocities = []
        shank_velocities = []
        for cuff_id, shank_id in zip(
            self.cuff_station_site_ids,
            self.shank_station_site_ids,
            strict=True,
        ):
            _, cuff_linear = self._site_velocity(int(cuff_id))
            _, shank_linear = self._site_velocity(int(shank_id))
            cuff_velocities.append(cuff_linear)
            shank_velocities.append(shank_linear)
        relative_translation = cuff_positions - shank_positions
        relative_speed = np.asarray(cuff_velocities) - np.asarray(shank_velocities)
        forces = (
            self.cuff_config.station_stiffness_n_m * relative_translation
            + self.cuff_config.station_damping_ns_m * relative_speed
        )
        return forces, relative_translation, relative_speed, shank_positions

    def _apply_soft_limit(self) -> None:
        q = self.data.qpos[self.human_qpos_indices]
        dq = self.data.qvel[self.human_dof_indices]
        self.data.qfrc_applied[:] = 0.0
        self.data.qfrc_applied[self.human_dof_indices] = soft_limit_torque(
            q, dq, self.human
        )
        forces, _, _, _ = self._station_state()
        for force, cuff_id, shank_id in zip(
            forces,
            self.cuff_station_site_ids,
            self.shank_station_site_ids,
            strict=True,
        ):
            cuff_jacobian = self._site_pose_jacobian(int(cuff_id))[:3]
            shank_jacobian = self._site_pose_jacobian(int(shank_id))[:3]
            self.data.qfrc_applied += (shank_jacobian - cuff_jacobian).T @ force

    def reconstruct_cuff_wrench(
        self,
    ) -> tuple[np.ndarray, float, np.ndarray, float]:
        forces, _, _, shank_positions = self._station_state()
        cuff_center = self.data.site_xpos[self.attachment_site_id]
        force = np.sum(forces, axis=0)
        moment_at_cuff = np.sum(
            np.cross(shank_positions - cuff_center, forces), axis=0
        )
        human_tau = np.zeros(2)
        for station_force, shank_id in zip(
            forces, self.shank_station_site_ids, strict=True
        ):
            human_tau += (
                self._site_pose_jacobian(int(shank_id))[:3, self.human_dof_indices].T
                @ station_force
            )
        human_center = self.data.site_xpos[self.sleeve_site_id]
        moment_at_human_center = moment_at_cuff + np.cross(
            cuff_center - human_center, force
        )
        wrench_at_human_center = np.concatenate([force, moment_at_human_center])
        wrench_tau = (
            self._site_pose_jacobian(self.sleeve_site_id)[:, self.human_dof_indices].T
            @ wrench_at_human_center
        )
        torque_residual = float(np.linalg.norm(wrench_tau - human_tau))
        wrench = np.concatenate([force, moment_at_cuff])
        return wrench, torque_residual, human_tau, torque_residual

    def observe(self) -> DistributedCuffObservation:
        attachment_position = self.data.site_xpos[self.attachment_site_id].copy()
        sleeve_position_world = self.data.site_xpos[self.sleeve_site_id].copy()
        attachment_rotation = self.data.site_xmat[self.attachment_site_id].reshape(3, 3).copy()
        sleeve_rotation = self.data.site_xmat[self.sleeve_site_id].reshape(3, 3).copy()
        angular_velocity, linear_velocity = self._site_velocity(self.attachment_site_id)
        forces, translations, relative_speeds, _ = self._station_state()
        wrench, residual, human_tau, tau_residual = self.reconstruct_cuff_wrench()
        bed_force, bed_penetration, bed_count = self._bed_metrics()
        rotation_error = self._rotation_error(sleeve_rotation, attachment_rotation)
        return DistributedCuffObservation(
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
            human_constraint_torque_nm=human_tau.copy(),
            human_wrench_torque_nm=human_tau.copy(),
            human_wrench_torque_residual_nm=tau_residual,
            weld_position_error_m=float(
                np.linalg.norm(attachment_position - sleeve_position_world)
            ),
            weld_rotation_error_rad=float(np.linalg.norm(rotation_error)),
            bed_force_n=bed_force,
            bed_penetration_m=bed_penetration,
            bed_contact_count=bed_count,
            unintended_contact_pairs=self._unintended_contact_pairs(),
            joint_torque_command_nm=self.last_joint_torque.copy(),
            unclipped_joint_torque_nm=self.last_unclipped_joint_torque.copy(),
            cartesian_force_command_n=self.last_force.copy(),
            cartesian_moment_command_nm=self.last_moment.copy(),
            station_offsets_m=self.cuff_config.station_offsets_m.copy(),
            station_force_world_n=forces.copy(),
            station_relative_translation_world_m=translations.copy(),
            station_relative_speed_world_m_s=relative_speeds.copy(),
            cuff_center_relative_translation_world_m=(
                attachment_position - sleeve_position_world
            ),
            cuff_shank_relative_rotation_rad=float(np.linalg.norm(rotation_error)),
        )

    def step(self) -> DistributedCuffObservation:
        self._apply_soft_limit()
        mujoco.mj_step(self.model, self.data)
        return self.observe()


def cuff_length_is_geometrically_supported(
    human: HumanV2Parameters,
    cuff_length_m: float,
) -> bool:
    half = 0.5 * cuff_length_m
    return bool(
        human.sleeve_center_m - half >= 0.0
        and human.sleeve_center_m + half <= human.shank_length_m
    )
