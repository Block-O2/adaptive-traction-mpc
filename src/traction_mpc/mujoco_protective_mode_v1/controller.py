"""State machine and abstract Cartesian position/velocity actuator interface."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from .config import HumanV2Parameters, ProtectiveModeConfig
from .reference import (
    QuinticBoundary,
    ReferenceSample,
    coordinated_posture,
    human_v2_reference,
    quintic_progress,
    reference_crossing_time,
)


@dataclass(frozen=True)
class ActuatorCommand:
    mode: str
    q_reference: np.ndarray
    dq_reference: np.ndarray
    ddq_reference: np.ndarray
    position_m: np.ndarray
    velocity_m_s: np.ndarray
    acceleration_m_s2: np.ndarray
    automatic_force_veto: bool
    manual_veto_probe: bool


def cuff_kinematics(
    sample: ReferenceSample,
    parameters: HumanV2Parameters,
    config: ProtectiveModeConfig,
) -> ReferenceSample:
    """Map q/dq/ddq to the nominal distal-cuff x/z state."""

    q1, q2 = sample.q
    dq1, dq2 = sample.dq
    phi = q1 - q2
    l1, sc = parameters.thigh_length_m, parameters.cuff_location_m
    position = np.array(
        [
            l1 * math.cos(q1) + sc * math.cos(phi),
            config.hip_height_m + l1 * math.sin(q1) + sc * math.sin(phi),
        ]
    )
    jacobian = np.array(
        [
            [-l1 * math.sin(q1) - sc * math.sin(phi), sc * math.sin(phi)],
            [l1 * math.cos(q1) + sc * math.cos(phi), -sc * math.cos(phi)],
        ]
    )
    hessian_x = np.array(
        [
            [-l1 * math.cos(q1) - sc * math.cos(phi), sc * math.cos(phi)],
            [sc * math.cos(phi), -sc * math.cos(phi)],
        ]
    )
    hessian_z = np.array(
        [
            [-l1 * math.sin(q1) - sc * math.sin(phi), sc * math.sin(phi)],
            [sc * math.sin(phi), -sc * math.sin(phi)],
        ]
    )
    velocity = jacobian @ sample.dq
    acceleration = jacobian @ sample.ddq + np.array(
        [sample.dq @ hessian_x @ sample.dq, sample.dq @ hessian_z @ sample.dq]
    )
    return ReferenceSample(position, velocity, acceleration)


class ProtectiveModeController:
    """Measured-state C2 patch feeding a bounded MuJoCo x/z servo."""

    def __init__(
        self,
        parameters: HumanV2Parameters,
        config: ProtectiveModeConfig,
        initial_robot_position_m: np.ndarray,
        manual_veto_time_s: float | None = None,
    ) -> None:
        self.parameters = parameters
        self.config = config
        self.manual_veto_time_s = manual_veto_time_s
        self.flexion_crossing_s = reference_crossing_time(math.radians(config.q_switch_deg), False)
        self.return_crossing_s = reference_crossing_time(math.radians(config.q_switch_deg), True)
        self.normal_duration_s = self.return_crossing_s - self.flexion_crossing_s
        self.takeoff_start_s = config.bed_start_duration_s
        self.normal_start_s = self.takeoff_start_s + config.transition_duration_s
        self.landing_start_s = self.normal_start_s + self.normal_duration_s
        self.terminal_start_s = self.landing_start_s + config.transition_duration_s
        self.end_time_s = self.terminal_start_s + config.terminal_hold_duration_s
        self.takeoff_patch: QuinticBoundary | None = None
        self.takeoff_correction: QuinticBoundary | None = None
        self.landing_patch: QuinticBoundary | None = None
        self.landing_correction: QuinticBoundary | None = None
        self.veto_patch: QuinticBoundary | None = None
        self.veto_start_s: float | None = None
        self.veto_q = coordinated_posture(math.radians(config.q_terminal_deg))
        initial = np.asarray(initial_robot_position_m, dtype=float)
        self.last_command = ActuatorCommand(
            mode="BED_START",
            q_reference=self.veto_q.copy(),
            dq_reference=np.zeros(2),
            ddq_reference=np.zeros(2),
            position_m=initial.copy(),
            velocity_m_s=np.zeros(2),
            acceleration_m_s2=np.zeros(2),
            automatic_force_veto=False,
            manual_veto_probe=False,
        )
        self.mode = "BED_START"
        self.automatic_force_veto = False
        self.manual_veto_probe = False

    def command(
        self,
        time_s: float,
        measured_q: np.ndarray,
        measured_dq: np.ndarray,
        measured_robot_position_m: np.ndarray,
        interaction_force_n: float,
    ) -> ActuatorCommand:
        """Return a continuous Cartesian position/velocity servo command."""

        automatic = not math.isfinite(interaction_force_n) or (
            interaction_force_n > self.config.force_veto_limit_n
        )
        manual = self.manual_veto_time_s is not None and time_s >= self.manual_veto_time_s
        if (automatic or manual) and self.veto_start_s is None:
            self._start_veto(time_s)
            self.automatic_force_veto = automatic
            self.manual_veto_probe = manual and not automatic
        if self.veto_start_s is not None:
            command = self._veto_command(time_s)
        elif time_s < self.takeoff_start_s:
            command = self._bed_start_command()
        elif time_s < self.normal_start_s:
            if self.takeoff_patch is None:
                self._start_takeoff(measured_q, measured_dq)
            command = self._takeoff_command(time_s)
        elif time_s < self.landing_start_s:
            command = self._normal_command(time_s)
        elif time_s < self.terminal_start_s:
            if self.landing_patch is None:
                self._start_landing(measured_q, measured_dq)
            command = self._landing_command(time_s)
        else:
            command = self._terminal_command()
        self.mode = command.mode
        self.last_command = command
        return command

    def _bed_start_command(self) -> ActuatorCommand:
        q = coordinated_posture(math.radians(self.config.q_terminal_deg))
        sample = ReferenceSample(q, np.zeros(2), np.zeros(2))
        return self._assemble("BED_START", sample, 0.0, 0.0, 0.0)

    def _start_takeoff(self, measured_q: np.ndarray, measured_dq: np.ndarray) -> None:
        target = human_v2_reference(self.flexion_crossing_s)
        self.takeoff_patch = QuinticBoundary(
            self.config.transition_duration_s,
            measured_q,
            measured_dq,
            np.zeros(2),
            target.q,
            target.dq,
            target.ddq,
        )
        raw = self._raw_command(self.takeoff_patch.sample(0.0), 0.0, 0.0, 0.0)
        self.takeoff_correction = self._continuity_correction(raw)

    def _takeoff_command(self, time_s: float) -> ActuatorCommand:
        assert self.takeoff_patch is not None and self.takeoff_correction is not None
        elapsed = time_s - self.takeoff_start_s
        extension, velocity, acceleration = self._extension_sample(elapsed, rising=True)
        sample = self.takeoff_patch.sample(elapsed)
        return self._assemble_with_correction(
            "KINEMATIC_TAKEOFF", sample, extension, velocity, acceleration, self.takeoff_correction, elapsed
        )

    def _normal_command(self, time_s: float) -> ActuatorCommand:
        reference_time = self.flexion_crossing_s + time_s - self.normal_start_s
        sample = human_v2_reference(reference_time)
        return self._assemble("NORMAL_REHAB", sample, self.config.cuff_working_extension_m, 0.0, 0.0)

    def _start_landing(self, measured_q: np.ndarray, measured_dq: np.ndarray) -> None:
        target = coordinated_posture(math.radians(self.config.q_terminal_deg))
        return_sample = human_v2_reference(self.return_crossing_s)
        self.landing_patch = QuinticBoundary(
            self.config.transition_duration_s,
            measured_q,
            measured_dq,
            return_sample.ddq,
            target,
            np.zeros(2),
            np.zeros(2),
        )
        raw = self._raw_command(
            self.landing_patch.sample(0.0), self.config.cuff_working_extension_m, 0.0, 0.0
        )
        self.landing_correction = self._continuity_correction(raw)

    def _landing_command(self, time_s: float) -> ActuatorCommand:
        assert self.landing_patch is not None and self.landing_correction is not None
        elapsed = time_s - self.landing_start_s
        extension, velocity, acceleration = self._extension_sample(elapsed, rising=False)
        sample = self.landing_patch.sample(elapsed)
        return self._assemble_with_correction(
            "KINEMATIC_LANDING", sample, extension, velocity, acceleration, self.landing_correction, elapsed
        )

    def _terminal_command(self) -> ActuatorCommand:
        q = coordinated_posture(math.radians(self.config.q_terminal_deg))
        sample = ReferenceSample(q, np.zeros(2), np.zeros(2))
        return self._assemble("TERMINAL", sample, 0.0, 0.0, 0.0)

    def _start_veto(self, time_s: float) -> None:
        duration = 0.25
        stop_position = self.last_command.position_m + 0.5 * duration * self.last_command.velocity_m_s
        self.veto_patch = QuinticBoundary(
            duration,
            self.last_command.position_m,
            self.last_command.velocity_m_s,
            self.last_command.acceleration_m_s2,
            stop_position,
            np.zeros(2),
            np.zeros(2),
        )
        self.veto_start_s = time_s
        self.veto_q = self.last_command.q_reference.copy()

    def _veto_command(self, time_s: float) -> ActuatorCommand:
        assert self.veto_patch is not None and self.veto_start_s is not None
        sample = self.veto_patch.sample(time_s - self.veto_start_s)
        return ActuatorCommand(
            mode="PROTECTIVE_STOP",
            q_reference=self.veto_q.copy(),
            dq_reference=np.zeros(2),
            ddq_reference=np.zeros(2),
            position_m=sample.q,
            velocity_m_s=sample.dq,
            acceleration_m_s2=sample.ddq,
            automatic_force_veto=self.automatic_force_veto,
            manual_veto_probe=self.manual_veto_probe,
        )

    def _extension_sample(self, elapsed_s: float, rising: bool) -> tuple[float, float, float]:
        duration = self.config.transition_duration_s
        s, ds, dds = quintic_progress(elapsed_s / duration)
        scale = self.config.cuff_working_extension_m
        sign = 1.0 if rising else -1.0
        value = scale * (s if rising else 1 - s)
        return value, sign * scale * ds / duration, sign * scale * dds / duration**2

    def _raw_command(
        self, sample: ReferenceSample, extension: float, extension_velocity: float, extension_acceleration: float
    ) -> ReferenceSample:
        cuff = cuff_kinematics(sample, self.parameters, self.config)
        offset = np.array([0.0, self.config.cuff_rest_length_m + extension])
        offset_velocity = np.array([0.0, extension_velocity])
        offset_acceleration = np.array([0.0, extension_acceleration])
        return ReferenceSample(cuff.q + offset, cuff.dq + offset_velocity, cuff.ddq + offset_acceleration)

    def _continuity_correction(self, raw: ReferenceSample) -> QuinticBoundary:
        return QuinticBoundary(
            self.config.transition_duration_s,
            self.last_command.position_m - raw.q,
            self.last_command.velocity_m_s - raw.dq,
            self.last_command.acceleration_m_s2 - raw.ddq,
            np.zeros(2),
            np.zeros(2),
            np.zeros(2),
        )

    def _assemble_with_correction(
        self,
        mode: str,
        sample: ReferenceSample,
        extension: float,
        extension_velocity: float,
        extension_acceleration: float,
        correction: QuinticBoundary,
        elapsed_s: float,
    ) -> ActuatorCommand:
        raw = self._raw_command(sample, extension, extension_velocity, extension_acceleration)
        adjust = correction.sample(elapsed_s)
        return ActuatorCommand(
            mode=mode,
            q_reference=sample.q,
            dq_reference=sample.dq,
            ddq_reference=sample.ddq,
            position_m=raw.q + adjust.q,
            velocity_m_s=raw.dq + adjust.dq,
            acceleration_m_s2=raw.ddq + adjust.ddq,
            automatic_force_veto=False,
            manual_veto_probe=False,
        )

    def _assemble(
        self,
        mode: str,
        sample: ReferenceSample,
        extension: float,
        extension_velocity: float,
        extension_acceleration: float,
    ) -> ActuatorCommand:
        raw = self._raw_command(sample, extension, extension_velocity, extension_acceleration)
        return ActuatorCommand(
            mode=mode,
            q_reference=sample.q,
            dq_reference=sample.dq,
            ddq_reference=sample.ddq,
            position_m=raw.q,
            velocity_m_s=raw.dq,
            acceleration_m_s2=raw.ddq,
            automatic_force_veto=False,
            manual_veto_probe=False,
        )
