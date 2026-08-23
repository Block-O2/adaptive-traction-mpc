"""MuJoCo environment and sensor extraction for protective-mode V1."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import mujoco

from .config import HumanV2Parameters, ProtectiveModeConfig
from .controller import ActuatorCommand, cuff_kinematics
from .model import build_mjcf
from .reference import ReferenceSample, coordinated_posture


@dataclass(frozen=True)
class Observation:
    time_s: float
    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    robot_position_m: np.ndarray
    robot_velocity_m_s: np.ndarray
    interaction_force_n: float
    bed_force_n: float
    max_bed_penetration_m: float
    bed_contact_count: int
    cuff_length_m: float
    cuff_extension_m: float
    cuff_active: bool
    actuator_force_n: np.ndarray
    substep_peak_interaction_force_n: float
    substep_peak_bed_force_n: float
    substep_peak_penetration_m: float


class ProtectiveModeEnvironment:
    """Planar leg, unilateral bed, compliant cuff, and bounded x/z robot."""

    def __init__(
        self,
        parameters: HumanV2Parameters | None = None,
        config: ProtectiveModeConfig | None = None,
    ) -> None:
        self.parameters = parameters or HumanV2Parameters()
        self.config = config or ProtectiveModeConfig()
        self.model = mujoco.MjModel.from_xml_string(build_mjcf(self.parameters, self.config))
        self.data = mujoco.MjData(self.model)
        self._joint_names = ("hip_joint", "knee_joint")
        self._robot_joint_names = ("robot_x_joint", "robot_z_joint")
        self._bed_geom_id = self.model.geom("bed").id
        self._human_geom_ids = {self.model.geom("thigh_geom").id, self.model.geom("shank_geom").id}
        self._tendon_id = self.model.tendon("cuff_tendon").id
        self._robot_mass_kg = 0.5
        self.reset()

    def reset(self) -> Observation:
        mujoco.mj_resetData(self.model, self.data)
        q = coordinated_posture(math.radians(self.config.q_terminal_deg))
        self.data.joint("hip_joint").qpos[0] = q[0]
        self.data.joint("knee_joint").qpos[0] = q[1]
        cuff = cuff_kinematics(
            ReferenceSample(q, np.zeros(2), np.zeros(2)), self.parameters, self.config
        )
        robot = cuff.q + np.array([0.0, self.config.cuff_rest_length_m])
        self.data.joint("robot_x_joint").qpos[0] = robot[0]
        self.data.joint("robot_z_joint").qpos[0] = robot[1]
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        return self.observe()

    def observe(
        self,
        substep_peak_interaction_force_n: float | None = None,
        substep_peak_bed_force_n: float | None = None,
        substep_peak_penetration_m: float | None = None,
    ) -> Observation:
        q = np.array([self.data.joint(name).qpos[0] for name in self._joint_names])
        dq = np.array([self.data.joint(name).qvel[0] for name in self._joint_names])
        robot_position = np.array([self.data.joint(name).qpos[0] for name in self._robot_joint_names])
        robot_velocity = np.array([self.data.joint(name).qvel[0] for name in self._robot_joint_names])
        interaction = self._interaction_force()
        bed_force, penetration, contact_count = self._bed_contact_metrics()
        length = float(self.data.ten_length[self._tendon_id])
        extension = max(0.0, length - self.config.cuff_rest_length_m)
        cuff_active = interaction >= self.config.cuff_loss_force_n and (
            extension >= self.config.cuff_loss_extension_m
        )
        return Observation(
            time_s=float(self.data.time),
            q_rad=q,
            dq_rad_s=dq,
            robot_position_m=robot_position,
            robot_velocity_m_s=robot_velocity,
            interaction_force_n=interaction,
            bed_force_n=bed_force,
            max_bed_penetration_m=penetration,
            bed_contact_count=contact_count,
            cuff_length_m=length,
            cuff_extension_m=extension,
            cuff_active=cuff_active,
            actuator_force_n=self.data.ctrl.copy(),
            substep_peak_interaction_force_n=(
                interaction if substep_peak_interaction_force_n is None else substep_peak_interaction_force_n
            ),
            substep_peak_bed_force_n=(bed_force if substep_peak_bed_force_n is None else substep_peak_bed_force_n),
            substep_peak_penetration_m=(
                penetration if substep_peak_penetration_m is None else substep_peak_penetration_m
            ),
        )

    def step(self, command: ActuatorCommand) -> Observation:
        peak_interaction = 0.0
        peak_bed = 0.0
        peak_penetration = 0.0
        for _ in range(self.config.control_substeps):
            position = np.array([self.data.joint(name).qpos[0] for name in self._robot_joint_names])
            velocity = np.array([self.data.joint(name).qvel[0] for name in self._robot_joint_names])
            force = self.config.servo_kp_n_m * (command.position_m - position) + self.config.servo_kd_ns_m * (
                command.velocity_m_s - velocity
            )
            force[1] += self._robot_mass_kg * self.parameters.gravity_m_s2
            self.data.ctrl[:] = np.clip(
                force, -self.config.actuator_force_limit_n, self.config.actuator_force_limit_n
            )
            mujoco.mj_step(self.model, self.data)
            interaction = self._interaction_force()
            bed_force, penetration, _ = self._bed_contact_metrics()
            peak_interaction = max(peak_interaction, interaction)
            peak_bed = max(peak_bed, bed_force)
            peak_penetration = max(peak_penetration, penetration)
        return self.observe(peak_interaction, peak_bed, peak_penetration)

    def _bed_contact_metrics(self) -> tuple[float, float, int]:
        total_force = 0.0
        max_penetration = 0.0
        count = 0
        contact_force = np.zeros(6)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            pair = {int(contact.geom1), int(contact.geom2)}
            if self._bed_geom_id not in pair or not (pair & self._human_geom_ids):
                continue
            mujoco.mj_contactForce(self.model, self.data, index, contact_force)
            total_force += max(0.0, float(contact_force[0]))
            max_penetration = max(max_penetration, max(0.0, -float(contact.dist)))
            count += 1
        return total_force, max_penetration, count

    def _interaction_force(self) -> float:
        length = float(self.data.ten_length[self._tendon_id])
        velocity = float(self.data.ten_velocity[self._tendon_id])
        rest = float(self.model.tendon_lengthspring[self._tendon_id, 0])
        stretch = length - rest
        if stretch <= 0:
            return 0.0
        stiffness = float(self.model.tendon_stiffness[self._tendon_id])
        damping = float(self.model.tendon_damping[self._tendon_id])
        return max(0.0, stiffness * stretch + damping * velocity)
