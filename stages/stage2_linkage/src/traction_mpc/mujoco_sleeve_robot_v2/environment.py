"""MuJoCo environment and Cartesian controller for plant V2."""

from __future__ import annotations

from dataclasses import dataclass
import math

import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .config import HumanV2Parameters, PlantV2Config, RobotV2Parameters
from .kinematics import coordinated_posture, sleeve_position, sleeve_rotation_matrix
from .model import build_plant_xml


class CuffForceCommandLimitError(RuntimeError):
    """Raised before applying a commanded cuff force above the retained gate."""

    def __init__(self, force_norm_n: float, force_bound_n: float) -> None:
        self.force_norm_n = force_norm_n
        self.force_bound_n = force_bound_n
        super().__init__(
            f"cuff force command {force_norm_n:.6g} N exceeds {force_bound_n:.6g} N"
        )


@dataclass(frozen=True)
class PlantObservation:
    time_s: float
    human_q_rad: np.ndarray
    human_dq_rad_s: np.ndarray
    robot_q_rad: np.ndarray
    robot_dq_rad_s: np.ndarray
    ee_position_m: np.ndarray
    ee_velocity_m_s: np.ndarray
    ee_rotation_matrix: np.ndarray
    ee_angular_velocity_rad_s: np.ndarray
    sleeve_position_m: np.ndarray
    sleeve_velocity_m_s: np.ndarray
    sleeve_rotation_matrix: np.ndarray
    sleeve_angular_velocity_rad_s: np.ndarray
    sleeve_force_vector_n: np.ndarray
    sleeve_force_n: float
    sleeve_moment_vector_nm: np.ndarray
    sleeve_moment_my_nm: float
    sleeve_wrench_reconstruction_residual_nm: float
    sleeve_deformation_m: float
    sleeve_relative_rotation_rad: float
    bed_force_n: float
    bed_penetration_m: float
    bed_contact_count: int
    fixture_reaction_nm: np.ndarray
    human_dynamics_residual_nm: np.ndarray
    cartesian_force_command_n: np.ndarray
    cartesian_moment_command_nm: np.ndarray
    joint_torque_command_nm: np.ndarray
    human_soft_limit_torque_nm: np.ndarray


@dataclass(frozen=True)
class PlantStep:
    observation: PlantObservation
    peak_sleeve_force_n: float
    peak_abs_sleeve_moment_my_nm: float
    peak_joint_torque_limit_fraction: float
    peak_sleeve_relative_position_m: float
    peak_sleeve_relative_rotation_rad: float
    peak_bed_force_n: float
    peak_bed_penetration_m: float
    bed_active_transitions: int
    bed_contact_count_transitions: int


@dataclass(frozen=True)
class PlantSnapshot:
    qpos: np.ndarray
    qvel: np.ndarray
    time_s: float
    eq_active: np.ndarray
    neutral_robot_q: np.ndarray
    neutral_ee_rotation_matrix: np.ndarray
    cartesian_force_command_n: np.ndarray
    cartesian_moment_command_nm: np.ndarray
    joint_torque_command_nm: np.ndarray


class SleeveRobotEnvironment:
    """Human V2, unilateral bed, bilateral sleeve, and 6-DoF serial arm."""

    def __init__(
        self,
        fixture_q2_deg: float | None = None,
        human: HumanV2Parameters | None = None,
        robot: RobotV2Parameters | None = None,
        config: PlantV2Config | None = None,
    ) -> None:
        self.human = human or HumanV2Parameters()
        self.robot = robot or RobotV2Parameters()
        self.config = config or PlantV2Config()
        self.fixture_q2_deg = fixture_q2_deg
        self.model = mujoco.MjModel.from_xml_string(
            build_plant_xml(self.human, self.robot, self.config, fixture_q2_deg)
        )
        self.data = mujoco.MjData(self.model)
        self._human_joint_names = ("hip_joint", "knee_joint")
        self._robot_joint_names = tuple(f"robot_joint_{index}" for index in range(1, 7))
        self._robot_dof_indices = np.array(
            [self.model.joint(name).dofadr[0] for name in self._robot_joint_names], dtype=int
        )
        self._robot_qpos_indices = np.array(
            [self.model.joint(name).qposadr[0] for name in self._robot_joint_names], dtype=int
        )
        self._ee_site_id = self.model.site("robot_ee_site").id
        self._sleeve_site_id = self.model.site("sleeve_attach_site").id
        self._bed_geom_id = self.model.geom("bed").id
        self._human_geom_ids = {
            self.model.geom("thigh_geom").id,
            self.model.geom("shank_geom").id,
        }
        self._sleeve_equality_id = self.model.equality("sleeve_connection").id
        self._fixture_equality_ids = []
        for name in ("fixture_hip", "fixture_knee"):
            equality_id = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_EQUALITY, name
            )
            if equality_id >= 0:
                self._fixture_equality_ids.append(equality_id)
        self.neutral_robot_q = np.zeros(6)
        self.neutral_ee_rotation_matrix = np.eye(3)
        self.last_cartesian_force_command_n = np.zeros(3)
        self.last_cartesian_moment_command_nm = np.zeros(3)
        self.last_joint_torque_command_nm = np.zeros(6)

    @property
    def fixture_active(self) -> bool:
        return bool(
            self._fixture_equality_ids
            and all(self.data.eq_active[index] for index in self._fixture_equality_ids)
        )

    def reset(self, q2_deg: float) -> PlantObservation:
        mujoco.mj_resetData(self.model, self.data)
        human_q = coordinated_posture(math.radians(q2_deg))
        for name, value in zip(self._human_joint_names, human_q, strict=True):
            self.data.joint(name).qpos[0] = value
        target = sleeve_position(human_q, self.human, self.config)
        target_rotation = sleeve_rotation_matrix(human_q)
        robot_q = self._solve_robot_ik(target, target_rotation)
        self.data.qpos[self._robot_qpos_indices] = robot_q
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = 0.0
        self.neutral_robot_q = robot_q.copy()
        self.neutral_ee_rotation_matrix = target_rotation.copy()
        self.last_cartesian_force_command_n = np.zeros(3)
        self.last_cartesian_moment_command_nm = np.zeros(3)
        self.last_joint_torque_command_nm = np.zeros(6)
        self.data.eq_active[self._sleeve_equality_id] = 1
        for equality_id in self._fixture_equality_ids:
            self.data.eq_active[equality_id] = 1
        self._apply_human_soft_limit()
        mujoco.mj_forward(self.model, self.data)
        ik_position_error = np.linalg.norm(self.data.site("robot_ee_site").xpos - target)
        ik_rotation_error = np.linalg.norm(
            self._rotation_error(
                target_rotation,
                self.data.site("robot_ee_site").xmat.reshape(3, 3),
            )
        )
        if ik_position_error > 1e-5 or ik_rotation_error > 1e-5:
            raise RuntimeError(
                "robot pose IK residual is "
                f"{ik_position_error:.6g} m / {ik_rotation_error:.6g} rad"
            )
        return self.observe()

    def release_fixture(self) -> None:
        for equality_id in self._fixture_equality_ids:
            self.data.eq_active[equality_id] = 0
        mujoco.mj_forward(self.model, self.data)

    def snapshot(self) -> PlantSnapshot:
        return PlantSnapshot(
            qpos=self.data.qpos.copy(),
            qvel=self.data.qvel.copy(),
            time_s=float(self.data.time),
            eq_active=self.data.eq_active.copy(),
            neutral_robot_q=self.neutral_robot_q.copy(),
            neutral_ee_rotation_matrix=self.neutral_ee_rotation_matrix.copy(),
            cartesian_force_command_n=self.last_cartesian_force_command_n.copy(),
            cartesian_moment_command_nm=self.last_cartesian_moment_command_nm.copy(),
            joint_torque_command_nm=self.last_joint_torque_command_nm.copy(),
        )

    def restore(self, snapshot: PlantSnapshot) -> None:
        self.data.qpos[:] = snapshot.qpos
        self.data.qvel[:] = snapshot.qvel
        self.data.time = snapshot.time_s
        self.data.eq_active[:] = snapshot.eq_active
        self.neutral_robot_q = snapshot.neutral_robot_q.copy()
        self.neutral_ee_rotation_matrix = snapshot.neutral_ee_rotation_matrix.copy()
        self.last_cartesian_force_command_n = snapshot.cartesian_force_command_n.copy()
        self.last_cartesian_moment_command_nm = snapshot.cartesian_moment_command_nm.copy()
        self.last_joint_torque_command_nm = snapshot.joint_torque_command_nm.copy()
        self._apply_human_soft_limit()
        mujoco.mj_forward(self.model, self.data)

    def observe(self) -> PlantObservation:
        human_q = np.array([self.data.joint(name).qpos[0] for name in self._human_joint_names])
        human_dq = np.array([self.data.joint(name).qvel[0] for name in self._human_joint_names])
        robot_q = self.data.qpos[self._robot_qpos_indices].copy()
        robot_dq = self.data.qvel[self._robot_dof_indices].copy()
        ee_position = self.data.site("robot_ee_site").xpos.copy()
        sleeve_position_world = self.data.site("sleeve_attach_site").xpos.copy()
        ee_rotation = self.data.site("robot_ee_site").xmat.reshape(3, 3).copy()
        sleeve_rotation = self.data.site("sleeve_attach_site").xmat.reshape(3, 3).copy()
        ee_angular_velocity, ee_velocity = self._site_velocity(self._ee_site_id)
        sleeve_angular_velocity, sleeve_velocity = self._site_velocity(
            self._sleeve_site_id
        )
        sleeve_wrench, wrench_residual = self._sleeve_wrench()
        sleeve_force = sleeve_wrench[:3]
        sleeve_moment = sleeve_wrench[3:]
        bed_force, penetration, contact_count = self._bed_contact_metrics()
        return PlantObservation(
            time_s=float(self.data.time),
            human_q_rad=human_q,
            human_dq_rad_s=human_dq,
            robot_q_rad=robot_q,
            robot_dq_rad_s=robot_dq,
            ee_position_m=ee_position,
            ee_velocity_m_s=ee_velocity,
            ee_rotation_matrix=ee_rotation,
            ee_angular_velocity_rad_s=ee_angular_velocity,
            sleeve_position_m=sleeve_position_world,
            sleeve_velocity_m_s=sleeve_velocity,
            sleeve_rotation_matrix=sleeve_rotation,
            sleeve_angular_velocity_rad_s=sleeve_angular_velocity,
            sleeve_force_vector_n=sleeve_force,
            sleeve_force_n=float(np.linalg.norm(sleeve_force)),
            sleeve_moment_vector_nm=sleeve_moment,
            sleeve_moment_my_nm=float(sleeve_moment[1]),
            sleeve_wrench_reconstruction_residual_nm=wrench_residual,
            sleeve_deformation_m=float(np.linalg.norm(ee_position - sleeve_position_world)),
            sleeve_relative_rotation_rad=float(
                np.linalg.norm(self._rotation_error(sleeve_rotation, ee_rotation))
            ),
            bed_force_n=bed_force,
            bed_penetration_m=penetration,
            bed_contact_count=contact_count,
            fixture_reaction_nm=self._fixture_reaction(),
            human_dynamics_residual_nm=self._human_dynamics_residual(),
            cartesian_force_command_n=self.last_cartesian_force_command_n.copy(),
            cartesian_moment_command_nm=self.last_cartesian_moment_command_nm.copy(),
            joint_torque_command_nm=self.last_joint_torque_command_nm.copy(),
            human_soft_limit_torque_nm=self._human_soft_limit_torque(),
        )

    def step_cartesian(
        self,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray | None = None,
        target_angular_velocity_rad_s: np.ndarray | None = None,
        feedforward_wrench_world: np.ndarray | None = None,
        enforce_force_norm_gate: bool = False,
    ) -> PlantStep:
        before = self.observe()
        previous_active = before.bed_force_n >= 2.0
        previous_count = before.bed_contact_count
        active_transitions = 0
        count_transitions = 0
        peak_sleeve = 0.0
        peak_abs_sleeve_moment_my = 0.0
        peak_joint_torque_fraction = 0.0
        peak_relative_position = 0.0
        peak_relative_rotation = 0.0
        peak_bed = 0.0
        peak_penetration = 0.0
        for _ in range(self.config.control_substeps):
            self._apply_cartesian_control(
                target_position_m,
                target_velocity_m_s,
                target_rotation_matrix,
                target_angular_velocity_rad_s,
                feedforward_wrench_world,
                enforce_force_norm_gate,
            )
            self._apply_human_soft_limit()
            mujoco.mj_step(self.model, self.data)
            observation = self.observe()
            active = observation.bed_force_n >= 2.0
            active_transitions += int(active != previous_active)
            count_transitions += int(observation.bed_contact_count != previous_count)
            previous_active = active
            previous_count = observation.bed_contact_count
            peak_sleeve = max(peak_sleeve, observation.sleeve_force_n)
            peak_abs_sleeve_moment_my = max(
                peak_abs_sleeve_moment_my,
                abs(observation.sleeve_moment_my_nm),
            )
            peak_joint_torque_fraction = max(
                peak_joint_torque_fraction,
                float(
                    np.max(
                        np.abs(observation.joint_torque_command_nm)
                        / np.asarray(self.robot.joint_torque_limits_nm)
                    )
                ),
            )
            peak_relative_position = max(
                peak_relative_position, observation.sleeve_deformation_m
            )
            peak_relative_rotation = max(
                peak_relative_rotation, observation.sleeve_relative_rotation_rad
            )
            peak_bed = max(peak_bed, observation.bed_force_n)
            peak_penetration = max(peak_penetration, observation.bed_penetration_m)
        return PlantStep(
            observation=observation,
            peak_sleeve_force_n=peak_sleeve,
            peak_abs_sleeve_moment_my_nm=peak_abs_sleeve_moment_my,
            peak_joint_torque_limit_fraction=peak_joint_torque_fraction,
            peak_sleeve_relative_position_m=peak_relative_position,
            peak_sleeve_relative_rotation_rad=peak_relative_rotation,
            peak_bed_force_n=peak_bed,
            peak_bed_penetration_m=peak_penetration,
            bed_active_transitions=active_transitions,
            bed_contact_count_transitions=count_transitions,
        )

    def _apply_cartesian_control(
        self,
        target_position_m: np.ndarray,
        target_velocity_m_s: np.ndarray,
        target_rotation_matrix: np.ndarray | None,
        target_angular_velocity_rad_s: np.ndarray | None,
        feedforward_wrench_world: np.ndarray | None,
        enforce_force_norm_gate: bool,
    ) -> None:
        observation = self.observe()
        force = self.config.cartesian_kp_n_m * (
            np.asarray(target_position_m) - observation.ee_position_m
        ) + self.config.cartesian_kd_ns_m * (
            np.asarray(target_velocity_m_s) - observation.ee_velocity_m_s
        )
        force = np.clip(
            force,
            -self.config.actuator_cartesian_force_bound_n,
            self.config.actuator_cartesian_force_bound_n,
        )
        target_rotation = (
            self.neutral_ee_rotation_matrix
            if target_rotation_matrix is None
            else np.asarray(target_rotation_matrix)
        )
        target_angular_velocity = (
            np.zeros(3)
            if target_angular_velocity_rad_s is None
            else np.asarray(target_angular_velocity_rad_s)
        )
        moment = self.config.orientation_kp_nm_rad * self._rotation_error(
            target_rotation, observation.ee_rotation_matrix
        )
        moment += self.config.orientation_kd_nms_rad * (
            target_angular_velocity - observation.ee_angular_velocity_rad_s
        )
        if feedforward_wrench_world is not None:
            feedforward = np.asarray(feedforward_wrench_world, dtype=float)
            if feedforward.shape != (6,) or not np.all(np.isfinite(feedforward)):
                raise ValueError("feedforward_wrench_world must be a finite 6-vector")
            force = force + feedforward[:3]
            moment = moment + feedforward[3:]
        force_norm = float(np.linalg.norm(force))
        if enforce_force_norm_gate and force_norm > self.config.force_veto_bound_n + 1e-9:
            raise CuffForceCommandLimitError(
                force_norm,
                self.config.force_veto_bound_n,
            )
        jacobian = self.ee_pose_jacobian()
        pinv = jacobian.T @ np.linalg.inv(
            jacobian @ jacobian.T + self.config.jacobian_damping * np.eye(6)
        )
        nullspace = np.eye(6) - pinv @ jacobian
        q = observation.robot_q_rad
        dq = observation.robot_dq_rad_s
        posture = self.config.nullspace_kp_nm_rad * (self.neutral_robot_q - q)
        posture -= self.config.nullspace_kd_nms_rad * dq
        torque = self.data.qfrc_bias[self._robot_dof_indices].copy()
        torque += jacobian.T @ np.concatenate([force, moment]) + nullspace.T @ posture
        limits = np.asarray(self.robot.joint_torque_limits_nm)
        torque = np.clip(torque, -limits, limits)
        self.data.ctrl[:] = torque
        self.last_cartesian_force_command_n = force
        self.last_cartesian_moment_command_nm = moment
        self.last_joint_torque_command_nm = torque

    def ee_jacobian(self) -> np.ndarray:
        return self.ee_pose_jacobian()[:3]

    def ee_pose_jacobian(self) -> np.ndarray:
        jacobian_position = np.zeros((3, self.model.nv))
        jacobian_rotation = np.zeros((3, self.model.nv))
        mujoco.mj_jacSite(
            self.model,
            self.data,
            jacobian_position,
            jacobian_rotation,
            self._ee_site_id,
        )
        return np.vstack(
            [
                jacobian_position[:, self._robot_dof_indices],
                jacobian_rotation[:, self._robot_dof_indices],
            ]
        )

    def _solve_robot_ik(
        self, target_position_m: np.ndarray, target_rotation_matrix: np.ndarray
    ) -> np.ndarray:
        for equality_id in range(self.model.neq):
            self.data.eq_active[equality_id] = 0
        lower = np.radians([limits[0] for limits in self.robot.joint_ranges_deg])
        upper = np.radians([limits[1] for limits in self.robot.joint_ranges_deg])
        base = np.asarray(self.robot.base_position_m)
        yaw = math.atan2(target_position_m[1] - base[1], target_position_m[0] - base[0])
        guesses = (
            np.array([yaw, 0.4, 1.2, 0.0, -0.7, 0.0]),
            np.array([yaw, 0.8, -1.2, 0.0, 0.5, 0.0]),
            np.array([yaw, -0.4, 1.5, 0.0, -0.8, 0.0]),
        )

        def residual(q: np.ndarray) -> np.ndarray:
            self.data.qpos[self._robot_qpos_indices] = q
            mujoco.mj_kinematics(self.model, self.data)
            position_error = self.data.site("robot_ee_site").xpos - target_position_m
            current_rotation = self.data.site("robot_ee_site").xmat.reshape(3, 3)
            rotation_error = self._rotation_error(target_rotation_matrix, current_rotation)
            return np.concatenate([position_error, rotation_error])

        best = None
        for guess in guesses:
            candidate = least_squares(
                residual,
                np.clip(guess, lower + 1e-6, upper - 1e-6),
                bounds=(lower, upper),
                xtol=1e-12,
                ftol=1e-12,
                gtol=1e-12,
                max_nfev=1000,
            )
            error = np.linalg.norm(residual(candidate.x))
            if best is None or error < best[0]:
                best = (error, candidate.x.copy())
        assert best is not None
        if best[0] > 1e-5:
            raise RuntimeError(f"CR12-like pose IK failed with residual {best[0]:.6g}")
        return best[1]

    def _sleeve_wrench(self) -> tuple[np.ndarray, float]:
        equality_type = int(mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        rows = np.flatnonzero(
            (self.data.efc_type[: self.data.nefc] == equality_type)
            & (self.data.efc_id[: self.data.nefc] == self._sleeve_equality_id)
        )
        if len(rows) != 6:
            return np.zeros(6), 0.0

        # Weld rotational constraint multipliers are internally scaled and are
        # not physical moments.  First reconstruct this equality's generalized
        # force, then solve virtual work at the coincident cuff sites for the
        # world-frame physical wrench acting on the human sleeve.
        equality_multipliers = np.zeros(self.data.nefc)
        equality_multipliers[rows] = self.data.efc_force[rows]
        equality_generalized_force = np.zeros(self.model.nv)
        mujoco.mj_mulJacTVec(
            self.model,
            self.data,
            equality_generalized_force,
            equality_multipliers,
        )
        robot_jacobian = self._site_pose_jacobian(self._ee_site_id)
        sleeve_jacobian = self._site_pose_jacobian(self._sleeve_site_id)
        wrench_map = (sleeve_jacobian - robot_jacobian).T
        wrench, _, _, _ = np.linalg.lstsq(
            wrench_map, equality_generalized_force, rcond=None
        )
        residual = float(
            np.linalg.norm(wrench_map @ wrench - equality_generalized_force)
        )
        return wrench, residual

    def _fixture_reaction(self) -> np.ndarray:
        reaction = np.zeros(2)
        equality_type = int(mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        for output_index, equality_id in enumerate(self._fixture_equality_ids):
            rows = np.flatnonzero(
                (self.data.efc_type[: self.data.nefc] == equality_type)
                & (self.data.efc_id[: self.data.nefc] == equality_id)
            )
            if len(rows) == 1:
                reaction[output_index] = self.data.efc_force[rows[0]]
        return reaction

    def _site_pose_jacobian(self, site_id: int) -> np.ndarray:
        jacobian_position = np.zeros((3, self.model.nv))
        jacobian_rotation = np.zeros((3, self.model.nv))
        mujoco.mj_jacSite(
            self.model,
            self.data,
            jacobian_position,
            jacobian_rotation,
            site_id,
        )
        return np.vstack([jacobian_position, jacobian_rotation])

    def _site_velocity(self, site_id: int) -> tuple[np.ndarray, np.ndarray]:
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(
            self.model,
            self.data,
            mujoco.mjtObj.mjOBJ_SITE,
            site_id,
            velocity,
            0,
        )
        return velocity[:3].copy(), velocity[3:].copy()

    @staticmethod
    def _rotation_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
        """World-frame rotation vector taking current orientation to target."""

        return Rotation.from_matrix(np.asarray(target) @ np.asarray(current).T).as_rotvec()

    def _human_soft_limit_torque(self) -> np.ndarray:
        q = np.array([self.data.joint(name).qpos[0] for name in self._human_joint_names])
        dq = np.array([self.data.joint(name).qvel[0] for name in self._human_joint_names])
        lower_start = np.asarray(self.human.q_min_rad) + self.human.soft_limit_margin_rad
        upper_start = np.asarray(self.human.q_max_rad) - self.human.soft_limit_margin_rad
        lower_activation = lower_start - self.human.soft_limit_numerical_tolerance_rad
        upper_activation = upper_start + self.human.soft_limit_numerical_tolerance_rad
        torque = np.zeros(2)
        for index in range(2):
            if q[index] < lower_activation[index]:
                z = (lower_activation[index] - q[index]) / self.human.soft_limit_margin_rad
                torque[index] = self.human.soft_limit_boundary_torque_nm * z**3
                torque[index] += (
                    self.human.soft_limit_damping_nms_rad
                    * z**2
                    * max(-dq[index], 0.0)
                )
            elif q[index] > upper_activation[index]:
                z = (q[index] - upper_activation[index]) / self.human.soft_limit_margin_rad
                torque[index] = -self.human.soft_limit_boundary_torque_nm * z**3
                torque[index] -= (
                    self.human.soft_limit_damping_nms_rad
                    * z**2
                    * max(dq[index], 0.0)
                )
        return torque

    def _apply_human_soft_limit(self) -> None:
        human_dofs = np.array(
            [self.model.joint(name).dofadr[0] for name in self._human_joint_names],
            dtype=int,
        )
        self.data.qfrc_applied[human_dofs] = self._human_soft_limit_torque()

    def _bed_contact_metrics(self) -> tuple[float, float, int]:
        total_force = 0.0
        penetration = 0.0
        count = 0
        contact_force = np.zeros(6)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            pair = {int(contact.geom1), int(contact.geom2)}
            if self._bed_geom_id not in pair or not (pair & self._human_geom_ids):
                continue
            mujoco.mj_contactForce(self.model, self.data, index, contact_force)
            total_force += max(0.0, float(contact_force[0]))
            penetration = max(penetration, max(0.0, -float(contact.dist)))
            count += 1
        return total_force, penetration, count

    def _human_dynamics_residual(self) -> np.ndarray:
        """Return the two human-DoF residuals of MuJoCo's forward dynamics."""

        mass_matrix = np.zeros((self.model.nv, self.model.nv))
        mujoco.mj_fullM(self.model, self.data, mass_matrix)
        residual = mass_matrix @ self.data.qacc
        residual += self.data.qfrc_bias
        residual -= self.data.qfrc_passive
        residual -= self.data.qfrc_actuator
        residual -= self.data.qfrc_applied
        residual -= self.data.qfrc_constraint
        human_dofs = np.array(
            [self.model.joint(name).dofadr[0] for name in self._human_joint_names],
            dtype=int,
        )
        return residual[human_dofs].copy()
