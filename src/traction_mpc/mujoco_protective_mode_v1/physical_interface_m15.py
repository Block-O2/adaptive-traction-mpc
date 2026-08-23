"""M1.5 physical-interface diagnostics for the protective-mode model.

The bilateral point connection in this module is an explicit MuJoCo
engineering hypothesis.  Nothing here claims a real cuff topology or robot
command contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import mujoco
import numpy as np

from .config import HumanV2Parameters, ProtectiveModeConfig
from .controller import cuff_kinematics
from .model import build_mjcf
from .reference import ReferenceSample, coordinated_posture, quintic_progress


INTERFACES = ("tension_only", "bilateral_point")
PROBE_POSTURES_DEG = (2.0, 10.0, 20.0, 30.0)


@dataclass(frozen=True)
class M15Config:
    equilibrium_duration_s: float = 3.0
    equilibrium_window_s: float = 0.5
    equilibrium_speed_tolerance_deg_s: float = 0.1
    # Reuses the V1 terminal acceptance scale; it is not a clinical threshold.
    equilibrium_q2_tolerance_deg: float = 1.0
    bed_active_force_n: float = 2.0
    probe_duration_s: float = 1.0
    probe_displacement_m: float = 0.002
    force_veto_n: float = 200.0


@dataclass(frozen=True)
class InterfaceObservation:
    time_s: float
    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    qacc_rad_s2: np.ndarray
    robot_position_m: np.ndarray
    robot_velocity_m_s: np.ndarray
    interaction_force_vector_n: np.ndarray
    interaction_force_n: float
    interface_deformation_m: float
    bed_force_n: float
    bed_penetration_m: float
    bed_contact_count: int
    actuator_force_n: np.ndarray


@dataclass(frozen=True)
class InterfaceStep:
    observation: InterfaceObservation
    peak_interaction_force_n: float
    peak_bed_force_n: float
    peak_bed_penetration_m: float
    bed_active_transitions: int
    bed_contact_count_transitions: int


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    arrays: dict[str, np.ndarray]
    metrics: dict[str, Any]


class PhysicalInterfaceEnvironment:
    """Native MuJoCo plant with a selectable cuff-interface topology."""

    def __init__(
        self,
        cuff_interface: str,
        parameters: HumanV2Parameters | None = None,
        config: ProtectiveModeConfig | None = None,
    ) -> None:
        if cuff_interface not in INTERFACES:
            raise ValueError(f"unsupported cuff interface: {cuff_interface}")
        self.cuff_interface = cuff_interface
        self.parameters = parameters or HumanV2Parameters()
        self.config = config or ProtectiveModeConfig()
        self.model = mujoco.MjModel.from_xml_string(
            build_mjcf(self.parameters, self.config, cuff_interface)
        )
        self.data = mujoco.MjData(self.model)
        self._bed_geom_id = self.model.geom("bed").id
        self._human_geom_ids = {
            self.model.geom("thigh_geom").id,
            self.model.geom("shank_geom").id,
        }
        self._tendon_id = self.model.tendon("cuff_tendon").id
        self._equality_id = (
            self.model.equality("cuff_bilateral_connection").id
            if cuff_interface == "bilateral_point"
            else None
        )
        self._robot_mass_kg = 0.5
        self.command_origin_m = np.zeros(2)

    def reset_at_posture(self, q2_deg: float) -> InterfaceObservation:
        mujoco.mj_resetData(self.model, self.data)
        q = coordinated_posture(math.radians(q2_deg))
        self.data.joint("hip_joint").qpos[0] = q[0]
        self.data.joint("knee_joint").qpos[0] = q[1]
        cuff = cuff_kinematics(
            ReferenceSample(q, np.zeros(2), np.zeros(2)), self.parameters, self.config
        ).q
        self.command_origin_m = cuff + np.array([0.0, self.config.cuff_rest_length_m])
        self.data.joint("robot_x_joint").qpos[0] = self.command_origin_m[0]
        self.data.joint("robot_z_joint").qpos[0] = self.command_origin_m[1]
        self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        return self.observe()

    def observe(self) -> InterfaceObservation:
        q = np.array(
            [self.data.joint("hip_joint").qpos[0], self.data.joint("knee_joint").qpos[0]]
        )
        dq = np.array(
            [self.data.joint("hip_joint").qvel[0], self.data.joint("knee_joint").qvel[0]]
        )
        qacc = np.array(
            [self.data.joint("hip_joint").qacc[0], self.data.joint("knee_joint").qacc[0]]
        )
        robot_position = np.array(
            [self.data.joint("robot_x_joint").qpos[0], self.data.joint("robot_z_joint").qpos[0]]
        )
        robot_velocity = np.array(
            [self.data.joint("robot_x_joint").qvel[0], self.data.joint("robot_z_joint").qvel[0]]
        )
        interaction_vector, deformation = self._interface_force()
        bed_force, penetration, count = self._bed_contact_metrics()
        return InterfaceObservation(
            time_s=float(self.data.time),
            q_rad=q,
            dq_rad_s=dq,
            qacc_rad_s2=qacc,
            robot_position_m=robot_position,
            robot_velocity_m_s=robot_velocity,
            interaction_force_vector_n=interaction_vector,
            interaction_force_n=float(np.linalg.norm(interaction_vector)),
            interface_deformation_m=deformation,
            bed_force_n=bed_force,
            bed_penetration_m=penetration,
            bed_contact_count=count,
            actuator_force_n=self.data.ctrl.copy(),
        )

    def step_servo(self, position_m: np.ndarray, velocity_m_s: np.ndarray) -> InterfaceStep:
        peak_interaction = 0.0
        peak_bed = 0.0
        peak_penetration = 0.0
        before = self.observe()
        previous_active = before.bed_force_n >= self.config.stable_bed_force_n
        previous_count = before.bed_contact_count
        active_transitions = 0
        count_transitions = 0
        for _ in range(self.config.control_substeps):
            observation = self.observe()
            force = self.config.servo_kp_n_m * (
                np.asarray(position_m) - observation.robot_position_m
            ) + self.config.servo_kd_ns_m * (
                np.asarray(velocity_m_s) - observation.robot_velocity_m_s
            )
            force[1] += self._robot_mass_kg * self.parameters.gravity_m_s2
            self.data.ctrl[:] = np.clip(
                force,
                -self.config.actuator_force_limit_n,
                self.config.actuator_force_limit_n,
            )
            mujoco.mj_step(self.model, self.data)
            observation = self.observe()
            active = observation.bed_force_n >= self.config.stable_bed_force_n
            active_transitions += int(active != previous_active)
            count_transitions += int(observation.bed_contact_count != previous_count)
            previous_active = active
            previous_count = observation.bed_contact_count
            peak_interaction = max(peak_interaction, observation.interaction_force_n)
            peak_bed = max(peak_bed, observation.bed_force_n)
            peak_penetration = max(peak_penetration, observation.bed_penetration_m)
        return InterfaceStep(
            observation=observation,
            peak_interaction_force_n=peak_interaction,
            peak_bed_force_n=peak_bed,
            peak_bed_penetration_m=peak_penetration,
            bed_active_transitions=active_transitions,
            bed_contact_count_transitions=count_transitions,
        )

    def generalized_force_balance(self) -> dict[str, np.ndarray | float]:
        mass = np.zeros((self.model.nv, self.model.nv))
        mujoco.mj_fullM(self.model, self.data, mass)
        inertia = mass @ self.data.qacc
        force_sum = (
            self.data.qfrc_passive
            + self.data.qfrc_actuator
            + self.data.qfrc_applied
            + self.data.qfrc_constraint
            - self.data.qfrc_bias
        )
        residual = force_sum - inertia
        return {
            "bias_nm": self.data.qfrc_bias[:2].copy(),
            "passive_nm": self.data.qfrc_passive[:2].copy(),
            "constraint_nm": self.data.qfrc_constraint[:2].copy(),
            "actuator_nm": self.data.qfrc_actuator[:2].copy(),
            "inertia_nm": inertia[:2].copy(),
            "residual_nm": residual[:2].copy(),
            "residual_norm_nm": float(np.linalg.norm(residual[:2])),
        }

    def _interface_force(self) -> tuple[np.ndarray, float]:
        cuff_position = self.data.site("cuff_site").xpos[[0, 2]].copy()
        cuff_velocity = self._site_linear_velocity("cuff_site")
        if self.cuff_interface == "tension_only":
            robot_position = self.data.site("robot_site").xpos[[0, 2]].copy()
            robot_velocity = self._site_linear_velocity("robot_site")
            delta = robot_position - cuff_position
            length = float(np.linalg.norm(delta))
            extension = max(0.0, length - self.config.cuff_rest_length_m)
            if length <= 1e-12 or extension <= 0.0:
                return np.zeros(2), extension
            length_rate = float(np.dot(delta / length, robot_velocity - cuff_velocity))
            magnitude = max(
                0.0,
                self.config.cuff_stiffness_n_m * extension
                + self.config.cuff_damping_ns_m * length_rate,
            )
            return magnitude * delta / length, extension

        attach_position = self.data.site("robot_cuff_attach_site").xpos[[0, 2]].copy()
        deformation = float(np.linalg.norm(attach_position - cuff_position))
        assert self._equality_id is not None
        equality_type = int(mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        rows = np.flatnonzero(
            (self.data.efc_type[: self.data.nefc] == equality_type)
            & (self.data.efc_id[: self.data.nefc] == self._equality_id)
        )
        if len(rows) != 3:
            raise RuntimeError(f"expected three equality rows, got {len(rows)}")
        # Connect rows are world x/y/z. efc_force acts on the robot site;
        # the equal-and-opposite x/z force below acts on the human cuff site.
        force_on_robot = self.data.efc_force[rows]
        return -force_on_robot[[0, 2]].copy(), deformation

    def _site_linear_velocity(self, site_name: str) -> np.ndarray:
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(
            self.model,
            self.data,
            mujoco.mjtObj.mjOBJ_SITE,
            self.model.site(site_name).id,
            velocity,
            0,
        )
        return velocity[3:][[0, 2]].copy()

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


def run_bed_start_equilibrium(
    diagnostic: M15Config | None = None,
    config: ProtectiveModeConfig | None = None,
) -> DiagnosticResult:
    """Settle the unchanged q2=2 degree V1 state with the robot held fixed."""

    diagnostic = diagnostic or M15Config()
    config = config or ProtectiveModeConfig()
    environment = PhysicalInterfaceEnvironment("tension_only", config=config)
    initial = environment.reset_at_posture(config.q_terminal_deg)
    records: list[dict[str, Any]] = []
    active_transitions = 0
    count_transitions = 0
    steps = int(round(diagnostic.equilibrium_duration_s / config.control_dt_s))
    for _ in range(steps):
        step = environment.step_servo(environment.command_origin_m, np.zeros(2))
        active_transitions += step.bed_active_transitions
        count_transitions += step.bed_contact_count_transitions
        records.append(_record_step(step, environment.command_origin_m, np.zeros(2)))
    arrays = _records_to_arrays(records)
    window = arrays["time_s"] >= arrays["time_s"][-1] - diagnostic.equilibrium_window_s
    balance = environment.generalized_force_balance()
    q_deg = np.degrees(arrays["q_rad"])
    dq_deg_s = np.degrees(arrays["dq_rad_s"])
    speed_peak = float(np.max(np.abs(dq_deg_s[window])))
    final_q2 = float(np.mean(q_deg[window, 1]))
    dynamics_settled = speed_peak <= diagnostic.equilibrium_speed_tolerance_deg_s
    terminal_held = abs(final_q2 - config.q_terminal_deg) <= diagnostic.equilibrium_q2_tolerance_deg
    metrics: dict[str, Any] = {
        "classification": (
            "STABLE_AT_REQUESTED_TERMINAL"
            if dynamics_settled and terminal_held
            else "SETTLED_OFF_REQUESTED_TERMINAL"
            if dynamics_settled
            else "NOT_SETTLED"
        ),
        "initial_q_deg": np.degrees(initial.q_rad).tolist(),
        "settled_q_deg": np.mean(q_deg[window], axis=0).tolist(),
        "terminal_q2_error_deg": abs(final_q2 - config.q_terminal_deg),
        "terminal_peak_speed_deg_s": speed_peak,
        "terminal_bed_force_mean_n": float(np.mean(arrays["bed_force_n"][window])),
        "peak_bed_force_n": float(np.max(arrays["peak_bed_force_n"])),
        "max_penetration_mm": float(1000 * np.max(arrays["peak_bed_penetration_m"])),
        "bed_active_transitions": active_transitions,
        "bed_contact_count_transitions": count_transitions,
        "first_half_second_contact_count_transitions": int(
            np.sum(arrays["bed_contact_count_transitions"][arrays["time_s"] <= 0.5])
        ),
        "last_half_second_contact_count_transitions": int(
            np.sum(arrays["bed_contact_count_transitions"][window])
        ),
        "settled_contact_count": int(round(np.median(arrays["bed_contact_count"][window]))),
        "settled_interaction_force_n": float(np.mean(arrays["interaction_force_n"][window])),
        "generalized_force_balance": {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in balance.items()
        },
        "dynamics_settled": dynamics_settled,
        "terminal_held": terminal_held,
    }
    return DiagnosticResult("bed_start_equilibrium", arrays, metrics)


def run_authority_probe(
    cuff_interface: str,
    q2_deg: float,
    direction_sign: int,
    diagnostic: M15Config | None = None,
    config: ProtectiveModeConfig | None = None,
) -> DiagnosticResult:
    """Run a paired short-horizon probe against an identical hold rollout.

    The hold/probe subtraction isolates actuator influence without inventing a
    hidden posture support.  Absolute posture drift is retained and reported.
    """

    if direction_sign not in {-1, 1}:
        raise ValueError("direction_sign must be -1 or +1")
    diagnostic = diagnostic or M15Config()
    config = config or ProtectiveModeConfig()
    hold = PhysicalInterfaceEnvironment(cuff_interface, config=config)
    probe = PhysicalInterfaceEnvironment(cuff_interface, config=config)
    hold.reset_at_posture(q2_deg)
    probe.reset_at_posture(q2_deg)
    direction = _coordinated_cuff_direction(q2_deg, probe.parameters, config)
    records: list[dict[str, Any]] = []
    vetoed = False
    steps = int(round(diagnostic.probe_duration_s / config.control_dt_s))
    for index in range(steps):
        time_s = index * config.control_dt_s
        s, ds, _ = quintic_progress(time_s / diagnostic.probe_duration_s)
        displacement = direction_sign * diagnostic.probe_displacement_m * s
        velocity = direction_sign * diagnostic.probe_displacement_m * ds / diagnostic.probe_duration_s
        hold_step = hold.step_servo(hold.command_origin_m, np.zeros(2))
        if vetoed:
            command_position = probe.observe().robot_position_m
            command_velocity = np.zeros(2)
        else:
            command_position = probe.command_origin_m + displacement * direction
            command_velocity = velocity * direction
        probe_step = probe.step_servo(command_position, command_velocity)
        if probe_step.peak_interaction_force_n >= diagnostic.force_veto_n:
            vetoed = True
        records.append(
            _record_probe_pair(
                hold_step,
                probe_step,
                command_position,
                command_velocity,
                direction,
            )
        )
    arrays = _records_to_arrays(records)
    final_slice = slice(max(0, len(arrays["time_s"]) - 20), None)
    differential_q2 = np.degrees(
        arrays["q_rad"][:, 1] - arrays["hold_q_rad"][:, 1]
    )
    differential_robot = arrays["robot_position_m"] - arrays["hold_robot_position_m"]
    projected_robot_mm = 1000 * differential_robot @ direction
    differential_robot_velocity = (
        arrays["robot_velocity_m_s"] - arrays["hold_robot_velocity_m_s"]
    )
    projected_robot_velocity_mm_s = 1000 * differential_robot_velocity @ direction
    force_projection = arrays["interaction_force_vector_n"] @ direction
    hold_force_projection = arrays["hold_interaction_force_vector_n"] @ direction
    differential_force = force_projection - hold_force_projection
    final_dx = float(np.mean(projected_robot_mm[final_slice]))
    final_dq2 = float(np.mean(differential_q2[final_slice]))
    effective_authority = final_dq2 / final_dx if abs(final_dx) > 1e-6 else None
    effective_stiffness = (
        float(np.mean(differential_force[final_slice])) / final_dx
        if abs(final_dx) > 1e-6
        else None
    )
    final_deformation_change_mm = float(
        1000
        * np.mean(
            arrays["interface_deformation_m"][final_slice]
            - arrays["hold_interface_deformation_m"][final_slice]
        )
    )
    absorbed_ratio = (
        abs(final_deformation_change_mm / final_dx) if abs(final_dx) > 1e-6 else None
    )
    absolute_q2 = np.degrees(arrays["q_rad"][:, 1])
    hold_q2 = np.degrees(arrays["hold_q_rad"][:, 1])
    metrics = {
        "interface": cuff_interface,
        "requested_q2_deg": q2_deg,
        "direction": "flexion" if direction_sign > 0 else "extension",
        "absolute_final_q2_deg": float(np.mean(absolute_q2[final_slice])),
        "hold_final_q2_deg": float(np.mean(hold_q2[final_slice])),
        "differential_q2_deg": final_dq2,
        "differential_robot_displacement_mm": final_dx,
        "peak_differential_robot_velocity_mm_s": float(
            np.max(np.abs(projected_robot_velocity_mm_s))
        ),
        "peak_command_velocity_mm_s": (
            1.875 * diagnostic.probe_displacement_m / diagnostic.probe_duration_s * 1000
        ),
        "effective_delta_q2_deg_per_mm": effective_authority,
        "effective_force_per_displacement_n_per_mm": effective_stiffness,
        "interface_deformation_change_mm": final_deformation_change_mm,
        "motion_absorbed_by_interface_ratio": absorbed_ratio,
        "peak_interaction_force_n": float(np.max(arrays["peak_interaction_force_n"])),
        "peak_actuator_axis_force_n": float(np.max(np.abs(arrays["actuator_force_n"]))),
        "peak_bed_force_n": float(np.max(arrays["peak_bed_force_n"])),
        "max_bed_penetration_mm": float(1000 * np.max(arrays["peak_bed_penetration_m"])),
        "bed_contact_count_transitions": int(np.sum(arrays["bed_contact_count_transitions"])),
        "final_bed_contact_count": int(round(np.median(arrays["bed_contact_count"][final_slice]))),
        "bed_active_sample_fraction": float(
            np.mean(arrays["bed_force_n"] >= diagnostic.bed_active_force_n)
        ),
        "force_veto_triggered": vetoed,
        "initial_posture_not_equilibrium": bool(
            abs(float(np.mean(hold_q2[final_slice])) - q2_deg) > 1.0
        ),
    }
    name = f"{cuff_interface}_{q2_deg:g}deg_{metrics['direction']}"
    arrays["probe_direction"] = np.tile(direction, (len(arrays["time_s"]), 1))
    return DiagnosticResult(name, arrays, metrics)


def _coordinated_cuff_direction(
    q2_deg: float,
    parameters: HumanV2Parameters,
    config: ProtectiveModeConfig,
) -> np.ndarray:
    epsilon = math.radians(0.01)
    positions = []
    for offset in (-epsilon, epsilon):
        q = coordinated_posture(math.radians(q2_deg) + offset)
        positions.append(
            cuff_kinematics(
                ReferenceSample(q, np.zeros(2), np.zeros(2)), parameters, config
            ).q
        )
    direction = positions[1] - positions[0]
    return direction / np.linalg.norm(direction)


def _record_step(
    step: InterfaceStep,
    command_position_m: np.ndarray,
    command_velocity_m_s: np.ndarray,
) -> dict[str, Any]:
    observation = step.observation
    return {
        "time_s": observation.time_s,
        "q_rad": observation.q_rad,
        "dq_rad_s": observation.dq_rad_s,
        "qacc_rad_s2": observation.qacc_rad_s2,
        "robot_position_m": observation.robot_position_m,
        "robot_velocity_m_s": observation.robot_velocity_m_s,
        "robot_command_position_m": np.asarray(command_position_m).copy(),
        "robot_command_velocity_m_s": np.asarray(command_velocity_m_s).copy(),
        "interaction_force_vector_n": observation.interaction_force_vector_n,
        "interaction_force_n": observation.interaction_force_n,
        "interface_deformation_m": observation.interface_deformation_m,
        "bed_force_n": observation.bed_force_n,
        "bed_penetration_m": observation.bed_penetration_m,
        "bed_contact_count": observation.bed_contact_count,
        "actuator_force_n": observation.actuator_force_n,
        "peak_interaction_force_n": step.peak_interaction_force_n,
        "peak_bed_force_n": step.peak_bed_force_n,
        "peak_bed_penetration_m": step.peak_bed_penetration_m,
        "bed_active_transitions": step.bed_active_transitions,
        "bed_contact_count_transitions": step.bed_contact_count_transitions,
    }


def _record_probe_pair(
    hold_step: InterfaceStep,
    probe_step: InterfaceStep,
    command_position_m: np.ndarray,
    command_velocity_m_s: np.ndarray,
    direction: np.ndarray,
) -> dict[str, Any]:
    record = _record_step(probe_step, command_position_m, command_velocity_m_s)
    hold = hold_step.observation
    record.update(
        {
            "hold_q_rad": hold.q_rad,
            "hold_robot_position_m": hold.robot_position_m,
            "hold_robot_velocity_m_s": hold.robot_velocity_m_s,
            "hold_interaction_force_vector_n": hold.interaction_force_vector_n,
            "hold_interaction_force_n": hold.interaction_force_n,
            "hold_interface_deformation_m": hold.interface_deformation_m,
            "hold_bed_force_n": hold.bed_force_n,
            "command_projection_m": float(np.dot(command_position_m, direction)),
        }
    )
    return record


def _records_to_arrays(records: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    return {
        key: np.asarray([record[key] for record in records])
        for key in records[0]
    }
