"""Selectable Stage-5 CR12 V0 plant; the UR10e donor remains unchanged."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2, LYING_BED_SCENARIO
from traction_mpc_stage3.human import HumanV2Parameters
from traction_mpc_stage3.spring_damper_interface import (
    InterfaceParameters,
    SpringDamperCoupledUR10eHumanV2,
)
from traction_mpc_stage4.sensor_realism import (
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
    RobotControlVelocitySnapshot,
    SensorBoundaryStage4Plant,
)

from .cr12_robot import (
    CR12_ACTUATOR_NAMES,
    CR12_JOINT_NAMES,
    CR12_MODEL_PATH,
    CR12_VENDOR_ROOT,
    CR12TorqueRobot,
)
from .geometry import STAGE5_GEOMETRY, Stage5Geometry
from .human import STAGE5_HUMAN
from .mechanics import NOMINAL_PHYSICS_DT_S, STAGE5_RIGID_INTERFACE
from .plant import build_stage5_model_xml


def _transform_attributes(transform) -> dict[str, str]:
    quaternion_xyzw = Rotation.from_matrix(transform.rotation).as_quat()
    quaternion_wxyz = quaternion_xyzw[[3, 0, 1, 2]]
    return {
        "pos": " ".join(f"{value:.12g}" for value in transform.translation),
        "quat": " ".join(f"{value:.12g}" for value in quaternion_wxyz),
    }


def _replace_single(root: ET.Element, tag: str, replacement: ET.Element) -> None:
    current = root.find(tag)
    if current is None:
        raise RuntimeError(f"Stage-5 donor XML has no {tag}")
    index = list(root).index(current)
    root.remove(current)
    root.insert(index, replacement)


def build_stage5_cr12_model_xml(
    human: HumanV2Parameters = STAGE5_HUMAN,
    *,
    geometry: Stage5Geometry = STAGE5_GEOMETRY,
    engineering_scenario: str = LYING_BED_SCENARIO,
) -> str:
    """Replace only the donor robot subtree with the traceable CR12 V0."""

    root = ET.fromstring(
        build_stage5_model_xml(
            human,
            geometry=geometry,
            engineering_scenario=engineering_scenario,
        )
    )
    source = ET.parse(CR12_MODEL_PATH).getroot()
    root.set("model", "stage5_cr12_v0_provisional_lab_geometry")

    compiler = root.find("compiler")
    if compiler is None:
        raise RuntimeError("Stage-5 donor XML has no compiler")
    compiler.set("meshdir", str((CR12_VENDOR_ROOT / "meshes").resolve()))

    source_asset = source.find("asset")
    source_actuator = source.find("actuator")
    source_contact = source.find("contact")
    if source_asset is None or source_actuator is None or source_contact is None:
        raise RuntimeError("CR12 V0 source adapter is incomplete")
    _replace_single(root, "asset", deepcopy(source_asset))
    _replace_single(root, "actuator", deepcopy(source_actuator))

    # Coupled resets set qpos explicitly, so a robot-only keyframe would have
    # ambiguous indexing after the two Human joints are inserted.
    keyframe = root.find("keyframe")
    if keyframe is not None:
        root.remove(keyframe)

    old_contact = root.find("contact")
    if old_contact is not None:
        root.remove(old_contact)
    equality = root.find("equality")
    if equality is None:
        raise RuntimeError("Stage-5 donor XML has no equality block")
    root.insert(list(root).index(equality), deepcopy(source_contact))

    worldbody = root.find("worldbody")
    source_worldbody = source.find("worldbody")
    if worldbody is None or source_worldbody is None:
        raise RuntimeError("robot model is missing worldbody")
    donor_base = worldbody.find("body[@name='base']")
    source_base = source_worldbody.find("body[@name='xMateCR12_base']")
    if donor_base is None or source_base is None:
        raise RuntimeError("robot model is missing its base body")
    donor_index = list(worldbody).index(donor_base)
    worldbody.remove(donor_base)
    cr12_base = deepcopy(source_base)
    cr12_base.set(
        "pos", " ".join(f"{value:.12g}" for value in geometry.world_from_base.translation)
    )
    quaternion_xyzw = Rotation.from_matrix(geometry.world_from_base.rotation).as_quat()
    quaternion_wxyz = quaternion_xyzw[[3, 0, 1, 2]]
    cr12_base.set("quat", " ".join(f"{value:.12g}" for value in quaternion_wxyz))
    worldbody.insert(donor_index, cr12_base)

    for light in list(worldbody.findall("light")):
        worldbody.remove(light)
    worldbody.insert(
        0,
        ET.Element(
            "light",
            {
                "name": "spotlight",
                "mode": "targetbodycom",
                "target": "xMateCR12_link5",
                "pos": "0 -1 2",
            },
        ),
    )

    link6 = cr12_base.find(".//body[@name='xMateCR12_link6']")
    if link6 is None:
        raise RuntimeError("CR12 V0 has no link6/flange body")
    ET.SubElement(
        link6,
        "site",
        {
            "name": "adapter_cuff_site",
            **_transform_attributes(geometry.end_effector_from_cuff),
            "size": "0.006",
            "rgba": "0.10 0.85 0.85 1",
        },
    )
    adapter_length = float(np.linalg.norm(geometry.end_effector_from_cuff.translation))
    if adapter_length > 1.0e-12:
        direction = geometry.end_effector_from_cuff.translation / adapter_length
        connector_end = max(0.0, adapter_length - 0.058) * direction
        ET.SubElement(
            link6,
            "geom",
            {
                "name": "cuff_adapter_geom",
                "type": "cylinder",
                "fromto": " ".join(
                    f"{value:.12g}" for value in np.r_[np.zeros(3), connector_end]
                ),
                "size": "0.018",
                "group": "3",
                "contype": "1",
                "conaffinity": "1",
                "rgba": "0.18 0.72 0.72 1",
            },
        )
    half_bar = 0.5 * geometry.cuff_bar_length_m
    bar_axis_link6 = (
        geometry.end_effector_from_cuff.rotation @ geometry.cuff_bar_axis_in_cuff
    )
    center = geometry.end_effector_from_cuff.translation
    ET.SubElement(
        link6,
        "geom",
        {
            "name": "stage5_cuff_bar_geom",
            "type": "cylinder",
            "fromto": " ".join(
                f"{value:.12g}"
                for value in np.r_[
                    center - half_bar * bar_axis_link6,
                    center + half_bar * bar_axis_link6,
                ]
            ),
            "size": f"{geometry.cuff_bar_radius_m:.12g}",
            "group": "3",
            "contype": "0",
            "conaffinity": "0",
            "rgba": "0.95 0.62 0.10 1",
        },
    )
    return ET.tostring(root, encoding="unicode")



def _select_initial_cr12_ik_candidate(
    candidates: list[np.ndarray], scores: list[float], nominal_q: np.ndarray
) -> np.ndarray:
    """Keep the best conditioning branch, resolving numerical ties canonically.

    A 6x6 Jacobian SVD has rounding error beyond a single float64 ULP.  The
    64-epsilon window is numerical resolution, not a physical score margin.
    """

    best = max(scores)
    score_resolution = 64.0 * np.finfo(np.float64).eps * max(1.0, abs(best))
    near_best = [
        i for i, score in enumerate(scores) if best - score <= score_resolution
    ]
    distances = [float(np.linalg.norm(candidates[i] - nominal_q)) for i in near_best]
    closest = min(distances)
    distance_resolution = 64.0 * np.finfo(np.float64).eps * max(1.0, closest)
    near_nominal = [
        i for i, distance in zip(near_best, distances)
        if distance - closest <= distance_resolution
    ]
    # The final key makes even a nominal-distance tie independent of seed order.
    return candidates[min(near_nominal, key=lambda i: tuple(candidates[i]))].copy()


def solve_cr12_stage5_ik(
    robot: CR12TorqueRobot,
    target,
    *,
    previous_q_rad: np.ndarray | None = None,
) -> np.ndarray:
    """Deterministic multi-start full-pose IK for the CR12 chain."""

    # Reuse the already validated numerical residual implementation; it relies
    # only on the six-DoF robot protocol implemented by CR12TorqueRobot.
    from traction_mpc_stage3.ik import _solve_candidates

    limits = robot.joint_limits_rad
    rng = np.random.default_rng(20260918)
    if previous_q_rad is None:
        seeds = [
            robot.home_q_rad,
            np.radians([90.0, -60.0, 90.0, 0.0, 60.0, 90.0]),
            np.radians([-90.0, 60.0, -90.0, 0.0, -60.0, -90.0]),
        ]
        seeds.extend(rng.uniform(limits[:, 0], limits[:, 1]) for _ in range(29))
        candidates = _solve_candidates(robot, target, seeds)
        exact = [candidate for error, candidate in candidates if error < 1.0e-8]
        if not exact:
            best_error = min(error for error, _ in candidates)
            raise RuntimeError(f"CR12 Stage-5 IK failed: residual={best_error:.6g}")

        def minimum_singular_value(q_rad: np.ndarray) -> float:
            robot.set_configuration(q_rad)
            return float(np.linalg.svd(robot.attachment_jacobian(), compute_uv=False)[-1])

        scores = [minimum_singular_value(candidate) for candidate in exact]
        return _select_initial_cr12_ik_candidate(exact, scores, robot.home_q_rad)

    previous = np.asarray(previous_q_rad, dtype=float)
    seeds = [previous]
    seeds.extend(
        np.clip(previous + rng.normal(0.0, 0.04, 6), limits[:, 0], limits[:, 1])
        for _ in range(5)
    )
    candidates = _solve_candidates(
        robot, target, seeds, periodic_reference=previous
    )
    exact = [candidate for error, candidate in candidates if error < 1.0e-8]
    if not exact:
        best_error = min(error for error, _ in candidates)
        raise RuntimeError(f"CR12 Stage-5 continuous IK failed: residual={best_error:.6g}")
    return min(exact, key=lambda candidate: np.linalg.norm(candidate - previous)).copy()


class Stage5CR12SpringDamperPlant(SpringDamperCoupledUR10eHumanV2):
    """Stage-5 Human/interface/controller semantics with only UR10e replaced."""

    robot_model_name = "cr12_v0"

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
            build_stage5_cr12_model_xml(
                human,
                geometry=geometry,
                engineering_scenario=engineering_scenario,
            )
        )
        self.model.opt.timestep = physics_dt_s
        self.data = mujoco.MjData(self.model)
        self.human_joint_names = ("hip_joint", "knee_joint")
        self.robot_joint_names = CR12_JOINT_NAMES
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
            [self.model.actuator(name).id for name in CR12_ACTUATOR_NAMES]
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
        self._ik_robot = CR12TorqueRobot()
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
        robot_q = solve_cr12_stage5_ik(self._ik_robot, target)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.human_qpos_indices] = q
        self.data.qpos[self.robot_qpos_indices] = robot_q
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self.data.eq_active[self.weld_id] = 0
        self.neutral_robot_q = robot_q.copy()
        self.last_joint_torque[:] = 0.0
        self.last_unclipped_joint_torque[:] = 0.0
        self.last_force[:] = 0.0
        self.last_moment[:] = 0.0
        self._apply_soft_limit()
        mujoco.mj_forward(self.model, self.data)
        return self.observe()


class Stage5CR12SensorBoundaryPlant(Stage5CR12SpringDamperPlant):
    """CR12 plant exposing the unchanged Stage-4 measured-control boundary."""

    robot_joint_control_velocity_snapshot = (
        SensorBoundaryStage4Plant.robot_joint_control_velocity_snapshot
    )
    control_feedback_velocity_snapshot = (
        SensorBoundaryStage4Plant.control_feedback_velocity_snapshot
    )
    apply_measured_nominal_cartesian_control = (
        SensorBoundaryStage4Plant.apply_measured_nominal_cartesian_control
    )
    preview_measured_executable_command = (
        SensorBoundaryStage4Plant.preview_measured_executable_command
    )

    def __init__(
        self,
        human: Any,
        *,
        interface_parameters: InterfaceParameters = STAGE5_RIGID_INTERFACE,
        geometry: Stage5Geometry = STAGE5_GEOMETRY,
    ) -> None:
        self.interface_history: list[dict[str, Any]] = []
        super().__init__(
            interface_parameters,
            human,
            physics_dt_s=NOMINAL_PHYSICS_DT_S,
            geometry=geometry,
        )
        self.translational_velocity_feedback_source = (
            ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        )
        self._measured_robot_model = CR12TorqueRobot()
        self._control_velocity_robot_model = CR12TorqueRobot()
        self.last_robot_control_velocity_snapshot: RobotControlVelocitySnapshot | None = None

    def observe(self):
        observation = super().observe()
        interface = self._evaluate_current_interface()
        record = {
            "time_s": observation.time_s,
            "translation_m": interface.displacement_human_m.copy(),
            "rotation_rad": interface.rotation_error_human_rad.copy(),
        }
        if (
            self.interface_history
            and abs(self.interface_history[-1]["time_s"] - observation.time_s) < 1.0e-12
        ):
            self.interface_history[-1] = record
        else:
            self.interface_history.append(record)
        return observation


def make_stage5_plant(robot_model: str = "ur10e", **kwargs):
    """Explicit robot selector preserving the historical UR10e default."""

    if robot_model == "ur10e":
        from .plant import Stage5SpringDamperPlant

        return Stage5SpringDamperPlant(**kwargs)
    if robot_model == "cr12_v0":
        return Stage5CR12SpringDamperPlant(**kwargs)
    raise ValueError("robot_model must be 'ur10e' or 'cr12_v0'")


assert issubclass(Stage5CR12SpringDamperPlant, CoupledUR10eHumanV2)
