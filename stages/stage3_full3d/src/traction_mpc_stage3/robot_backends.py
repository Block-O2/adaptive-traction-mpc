"""Simulation implementation and non-transmitting CR12 dry-run skeleton."""

from __future__ import annotations

import mujoco
import numpy as np

from .coupled import CoupledUR10eHumanV2
from .frames import ATTACHMENT_FROM_CUFF, WORLD_FROM_BASE, RigidTransform
from .robot_interface import (
    CapabilityStatus,
    CommandMode,
    CommandReceipt,
    CommandValidator,
    FrameCalibration,
    FramedPose,
    RobotBackend,
    RobotCapabilities,
    RobotCommand,
    RobotMode,
    RobotState,
    WatchdogState,
    WatchdogStatus,
)


def stage3_simulation_calibration(plant: CoupledUR10eHumanV2) -> FrameCalibration:
    """Return the explicit Stage-3 simulation-only flange/adapter chain."""

    site_id = plant.attachment_site_id
    rotation = np.zeros(9)
    mujoco.mju_quat2Mat(rotation, plant.model.site_quat[site_id])
    return FrameCalibration(
        base_frame="ur10e_base",
        flange_frame="wrist_3_link",
        adapter_frame="attachment_site",
        cuff_frame="human_v2_cuff",
        flange_from_adapter=RigidTransform(
            rotation.reshape(3, 3), plant.model.site_pos[site_id]
        ),
        adapter_from_cuff=ATTACHMENT_FROM_CUFF,
        provenance=(
            "Stage-3 simulation: Menagerie attachment_site plus explicit "
            "provisional identity ATTACHMENT_FROM_CUFF; not hardware calibration"
        ),
    )


class Stage3SimulationBackend(RobotBackend):
    """Expose the coupled UR10e simulation through the hardware-neutral contract."""

    def __init__(
        self,
        plant: CoupledUR10eHumanV2,
        *,
        watchdog_timeout_s: float = 0.020,
    ) -> None:
        if watchdog_timeout_s <= 0.0:
            raise ValueError("simulation watchdog timeout must be positive")
        self.plant = plant
        self.watchdog_timeout_s = float(watchdog_timeout_s)
        self._connected = False
        self._enabled = False
        self._sequence = 0
        self._last_command_timestamp_s: float | None = None
        self._deadline_s: float | None = None
        modes = {
            CommandMode.DISABLED: CapabilityStatus.CONFIRMED,
            CommandMode.JOINT_POSITION: CapabilityStatus.NOT_SUPPORTED,
            CommandMode.JOINT_VELOCITY: CapabilityStatus.NOT_SUPPORTED,
            CommandMode.JOINT_TORQUE: CapabilityStatus.CONFIRMED,
        }
        self._capabilities = RobotCapabilities(
            backend_name="stage3_coupled_ur10e_simulation",
            robot_identity="Menagerie UR10e surrogate in MuJoCo; not CR12 hardware",
            dof=6,
            command_modes=modes,
            joint_state=CapabilityStatus.CONFIRMED,
            flange_pose=CapabilityStatus.CONFIRMED,
            tcp_pose=CapabilityStatus.CONFIRMED,
            jacobian=CapabilityStatus.CONFIRMED,
            measured_joint_torque=CapabilityStatus.NOT_SUPPORTED,
            measured_motor_current=CapabilityStatus.NOT_SUPPORTED,
            measured_ft_wrench=CapabilityStatus.NOT_SUPPORTED,
            stop_state=CapabilityStatus.CONFIRMED,
            watchdog=CapabilityStatus.CONFIRMED,
            command_frequency_hz=200.0,
            feedback_frequency_hz=1000.0,
            transport="in-process MuJoCo",
            evidence="Stage-3B/3C committed simulation model and tests",
        )
        limits = self.plant.torque_limits_nm
        self.validator = CommandValidator(
            self._capabilities,
            {CommandMode.JOINT_TORQUE: (-limits, limits)},
            limit_source="Stage-3 UR10e surrogate actuator model only",
        )
        self._calibration = stage3_simulation_calibration(plant)

    @property
    def capabilities(self) -> RobotCapabilities:
        return self._capabilities

    @property
    def calibration(self) -> FrameCalibration:
        return self._calibration

    def connect(self) -> None:
        self._connected = True
        self._enabled = False
        self._last_command_timestamp_s = None
        self._deadline_s = None

    def disconnect(self) -> None:
        self._connected = False
        self._enabled = False
        self._last_command_timestamp_s = None
        self._deadline_s = None
        self.plant.data.ctrl[self.plant.actuator_ids] = 0.0

    def _watchdog_state(self) -> WatchdogState:
        if self._deadline_s is None:
            status = WatchdogStatus.NOT_APPLICABLE
        elif self.plant.data.time > self._deadline_s + 1e-12:
            status = WatchdogStatus.EXPIRED
        else:
            status = WatchdogStatus.ARMED
        return WatchdogState(status, self._last_command_timestamp_s, self._deadline_s)

    def _base_from_world_pose(self, position: np.ndarray, rotation: np.ndarray) -> RigidTransform:
        return WORLD_FROM_BASE.inverse().compose(RigidTransform(rotation, position))

    def read_state(self) -> RobotState:
        observation = self.plant.observe()
        flange_id = self.plant.model.body("wrist_3_link").id
        flange_pose = self._base_from_world_pose(
            self.plant.data.xpos[flange_id],
            self.plant.data.xmat[flange_id].reshape(3, 3),
        )
        tcp_pose = self._base_from_world_pose(
            observation.attachment_position_m,
            observation.attachment_rotation_matrix,
        )
        watchdog = self._watchdog_state()
        if not self._connected:
            mode = RobotMode.DISCONNECTED
        elif watchdog.status is WatchdogStatus.EXPIRED:
            mode = RobotMode.FAULT
        elif self._enabled:
            mode = RobotMode.ENABLED
        else:
            mode = RobotMode.DISABLED
        return RobotState(
            timestamp_s=float(self.plant.data.time),
            sequence=self._sequence,
            q_rad=observation.robot_q_rad,
            dq_rad_s=observation.robot_dq_rad_s,
            base_from_flange=FramedPose(
                self.calibration.base_frame,
                self.calibration.flange_frame,
                flange_pose,
            ),
            base_from_tcp=FramedPose(
                self.calibration.base_frame,
                self.calibration.adapter_frame,
                tcp_pose,
            ),
            # BASE and WORLD axes are aligned in the validated simulation.
            jacobian_base_tcp=self.plant.robot_attachment_jacobian(),
            measured_joint_torque_nm=None,
            measured_motor_current_a=None,
            measured_tcp_wrench=None,
            robot_mode=mode,
            fault_code=("SIM_WATCHDOG_EXPIRED" if mode is RobotMode.FAULT else None),
            watchdog=watchdog,
        )

    def submit_command(self, command: RobotCommand) -> CommandReceipt:
        now = float(self.plant.data.time)
        if not self._connected:
            return CommandReceipt(False, False, "backend disconnected", now)
        try:
            independently_checked = self.validator.make_command(
                command.mode,
                command.vector,
                timestamp_s=command.timestamp_s,
                deadline_s=command.deadline_s,
                enable_requested=command.enable_requested,
            )
        except ValueError as error:
            return CommandReceipt(False, False, f"backend validation failed: {error}", now)
        if not independently_checked.software_limit_result.accepted:
            return CommandReceipt(
                False,
                False,
                "backend validation failed: "
                + "; ".join(independently_checked.software_limit_result.reasons),
                now,
            )
        if self._deadline_s is not None and now > self._deadline_s + 1e-12:
            return CommandReceipt(
                False,
                False,
                "simulation watchdog fault is latched; disconnect/reconnect required",
                now,
            )
        if not command.software_limit_result.accepted:
            return CommandReceipt(
                False,
                False,
                "; ".join(command.software_limit_result.reasons),
                now,
            )
        if command.timestamp_s > now + 1e-12:
            return CommandReceipt(False, False, "command timestamp is in the future", now)
        if now > command.deadline_s + 1e-12:
            return CommandReceipt(False, False, "command deadline expired", now)
        if command.mode is CommandMode.DISABLED:
            self.plant.data.ctrl[self.plant.actuator_ids] = 0.0
            self._enabled = False
        elif command.mode is CommandMode.JOINT_TORQUE:
            self.plant.data.ctrl[self.plant.actuator_ids] = command.vector
            self._enabled = True
        else:
            return CommandReceipt(False, False, "mode not implemented by simulation", now)
        self._last_command_timestamp_s = command.timestamp_s
        self._deadline_s = min(command.deadline_s, now + self.watchdog_timeout_s)
        self._sequence += 1
        return CommandReceipt(True, True, "applied to simulation only", now)

    def advance(self) -> RobotState:
        next_time = float(self.plant.data.time + self.plant.model.opt.timestep)
        if self._deadline_s is not None and next_time > self._deadline_s + 1e-12:
            self.plant.data.ctrl[self.plant.actuator_ids] = 0.0
            self._enabled = False
        self.plant.step()
        return self.read_state()


class CR12DryRunBackend(RobotBackend):
    """Non-networked placeholder: it cannot transmit any hardware command."""

    def __init__(self, calibration: FrameCalibration) -> None:
        self._calibration = calibration
        self._configured = False
        self._offline_state: RobotState | None = None
        self.audit_log: list[CommandReceipt] = []
        self.transmitted_command_count = 0
        unknown_modes = {
            CommandMode.DISABLED: CapabilityStatus.UNKNOWN,
            CommandMode.JOINT_POSITION: CapabilityStatus.UNKNOWN,
            CommandMode.JOINT_VELOCITY: CapabilityStatus.UNKNOWN,
            CommandMode.JOINT_TORQUE: CapabilityStatus.UNKNOWN,
        }
        self._capabilities = RobotCapabilities(
            backend_name="cr12_disabled_dry_run",
            robot_identity="laboratory CR12 exact model/controller unresolved",
            dof=None,
            command_modes=unknown_modes,
            joint_state=CapabilityStatus.UNKNOWN,
            flange_pose=CapabilityStatus.UNKNOWN,
            tcp_pose=CapabilityStatus.UNKNOWN,
            jacobian=CapabilityStatus.UNKNOWN,
            measured_joint_torque=CapabilityStatus.UNKNOWN,
            measured_motor_current=CapabilityStatus.UNKNOWN,
            measured_ft_wrench=CapabilityStatus.UNKNOWN,
            stop_state=CapabilityStatus.UNKNOWN,
            watchdog=CapabilityStatus.UNKNOWN,
            command_frequency_hz=None,
            feedback_frequency_hz=None,
            transport=None,
            evidence="No matching local controller identity, SDK or API documentation",
        )
        self.validator = CommandValidator(
            self._capabilities,
            {},
            limit_source="none: CR12 hardware limits unavailable",
        )

    @property
    def capabilities(self) -> RobotCapabilities:
        return self._capabilities

    @property
    def calibration(self) -> FrameCalibration:
        return self._calibration

    def connect(self) -> None:
        # This is intentionally local bookkeeping only. There is no socket,
        # SDK object, transport callback, or command transmitter in this class.
        self._configured = True

    def disconnect(self) -> None:
        self._configured = False

    def load_offline_state(self, state: RobotState) -> None:
        self._offline_state = state

    def read_state(self) -> RobotState:
        if not self._configured:
            raise RuntimeError("CR12 dry-run backend is not configured")
        if self._offline_state is None:
            raise RuntimeError("no documented CR12 state schema or offline state loaded")
        return self._offline_state

    def submit_command(self, command: RobotCommand) -> CommandReceipt:
        reason = "CR12 hardware transmission is disabled; dry-run audit only"
        if not command.software_limit_result.accepted:
            reason += "; " + "; ".join(command.software_limit_result.reasons)
        receipt = CommandReceipt(
            accepted=False,
            transmitted=False,
            reason=reason,
            backend_timestamp_s=(
                self._offline_state.timestamp_s if self._offline_state is not None else 0.0
            ),
        )
        self.audit_log.append(receipt)
        return receipt
