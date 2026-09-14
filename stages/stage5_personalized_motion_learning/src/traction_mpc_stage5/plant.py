"""Stage-5-only assembly around the reused Stage-3 plant mechanics."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import (
    LYING_BED_SCENARIO,
    CoupledUR10eHumanV2,
    build_coupled_model_xml,
)
from traction_mpc_stage3.human import HumanV2Parameters
from traction_mpc_stage3.robot import ACTUATOR_NAMES, JOINT_NAMES, UR10eTorqueRobot
from traction_mpc_stage3.spring_damper_interface import (
    InterfaceParameters,
    SpringDamperCoupledUR10eHumanV2,
)

from .geometry import STAGE5_GEOMETRY, Stage5Geometry
from .human import STAGE5_HUMAN
from .ik import solve_stage5_ik
from .mechanics import NOMINAL_PHYSICS_DT_S, STAGE5_RIGID_INTERFACE


def _set_body_transform(element: ET.Element, transform) -> None:
    element.set(
        "pos", " ".join(f"{value:.12g}" for value in transform.translation)
    )
    quat_xyzw = Rotation.from_matrix(transform.rotation).as_quat()
    quat_wxyz = quat_xyzw[[3, 0, 1, 2]]
    element.set("quat", " ".join(f"{value:.12g}" for value in quat_wxyz))


def _set_robot_base_placement(element: ET.Element, transform) -> None:
    """Place the donor model without erasing its built-in UR base rotation."""

    element.set(
        "pos", " ".join(f"{value:.12g}" for value in transform.translation)
    )
    if not np.allclose(transform.rotation, np.eye(3), atol=1.0e-12):
        raise ValueError(
            "Stage-5 v1 supports the registered donor base axes only; "
            "a non-identity T_WB rotation needs an explicit frame audit"
        )


def build_stage5_model_xml(
    human: HumanV2Parameters = STAGE5_HUMAN,
    *,
    geometry: Stage5Geometry = STAGE5_GEOMETRY,
    engineering_scenario: str = LYING_BED_SCENARIO,
) -> str:
    """Patch only Stage-5 placement and visual tool geometry onto Stage 3."""

    root = ET.fromstring(
        build_coupled_model_xml(
            human,
            attachment_from_cuff=geometry.end_effector_from_cuff,
            engineering_scenario=engineering_scenario,
        )
    )
    root.set("model", "stage5_provisional_lab_geometry")
    base = root.find("./worldbody/body[@name='base']")
    hip = root.find("./worldbody/body[@name='hip']")
    wrist = root.find("./worldbody/body[@name='base']//body[@name='wrist_3_link']")
    cuff_site = wrist.find("site[@name='adapter_cuff_site']") if wrist is not None else None
    if base is None or hip is None or wrist is None or cuff_site is None:
        raise RuntimeError("Stage-3 donor XML is missing a required Stage-5 element")
    # Keep the donor body's fixed quat="0 0 0 -1". The Stage-3 IK model
    # includes that UR kinematic convention; replacing it would rotate the
    # solved robot a second time while the declared external B axes stay fixed.
    _set_robot_base_placement(base, geometry.world_from_base)
    _set_body_transform(hip, geometry.world_from_human)

    center = np.fromstring(cuff_site.get("pos", ""), sep=" ")
    quaternion_wxyz = np.fromstring(cuff_site.get("quat", ""), sep=" ")
    cuff_rotation_in_wrist = Rotation.from_quat(
        quaternion_wxyz[[1, 2, 3, 0]]
    ).as_matrix()
    half_bar = 0.5 * geometry.cuff_bar_length_m
    bar_axis_wrist = cuff_rotation_in_wrist @ geometry.cuff_bar_axis_in_cuff
    endpoints = np.concatenate(
        [center - half_bar * bar_axis_wrist, center + half_bar * bar_axis_wrist]
    )
    ET.SubElement(
        wrist,
        "geom",
        {
            "name": "stage5_cuff_bar_geom",
            "type": "cylinder",
            "fromto": " ".join(f"{value:.12g}" for value in endpoints),
            "size": f"{geometry.cuff_bar_radius_m:.12g}",
            "group": "3",
            "contype": "0",
            "conaffinity": "0",
            "rgba": "0.95 0.62 0.10 1",
        },
    )
    return ET.tostring(root, encoding="unicode")


class Stage5SpringDamperPlant(SpringDamperCoupledUR10eHumanV2):
    """Stage-3 dynamics with Stage-5 placement and interface parameters.

    The class lives entirely in Stage 5 so the donor Stage-3/Stage-4 source and
    historical evidence remain untouched.
    """

    def __init__(
        self,
        parameters: InterfaceParameters = STAGE5_RIGID_INTERFACE,
        human: HumanV2Parameters = STAGE5_HUMAN,
        *,
        physics_dt_s: float = NOMINAL_PHYSICS_DT_S,
        geometry: Stage5Geometry = STAGE5_GEOMETRY,
        engineering_scenario: str = LYING_BED_SCENARIO,
    ) -> None:
        if not np.isfinite(physics_dt_s) or physics_dt_s <= 0.0:
            raise ValueError("physics_dt_s must be finite and positive")
        self.geometry = geometry
        self.interface_parameters = parameters
        self.human = human
        self.attachment_from_cuff = geometry.end_effector_from_cuff
        self.engineering_scenario = engineering_scenario
        self.model = mujoco.MjModel.from_xml_string(
            build_stage5_model_xml(
                human, geometry=geometry, engineering_scenario=engineering_scenario
            )
        )
        self.model.opt.timestep = physics_dt_s
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
        self.flange_site_id = self.model.site("attachment_site").id
        self.attachment_site_id = self.model.site("adapter_cuff_site").id
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
            and int(self.model.geom_contype[geom_id]) != 0
        }
        self._ik_robot = UR10eTorqueRobot()
        self.neutral_robot_q = np.zeros(6)
        self.last_joint_torque = np.zeros(6)
        self.last_unclipped_joint_torque = np.zeros(6)
        self.last_force = np.zeros(3)
        self.last_moment = np.zeros(3)
        self.model.eq_active0[self.weld_id] = 0
        self.data.eq_active[self.weld_id] = 0
        self.interface_generalized_force = np.zeros(self.model.nv)

    def reset(self, human_q_rad: np.ndarray):
        q = np.asarray(human_q_rad, dtype=float)
        if q.shape != (2,) or not np.all(np.isfinite(q)):
            raise ValueError("human_q_rad must be a finite two-vector")
        limits = np.column_stack([self.human.q_min_rad, self.human.q_max_rad])
        if np.any(q < limits[:, 0]) or np.any(q > limits[:, 1]):
            raise ValueError("Human V2 reset posture violates ROM")
        target = self.geometry.base_from_end_effector_target(q, self.human)
        robot_q = solve_stage5_ik(self._ik_robot, target)
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


assert issubclass(Stage5SpringDamperPlant, CoupledUR10eHumanV2)
