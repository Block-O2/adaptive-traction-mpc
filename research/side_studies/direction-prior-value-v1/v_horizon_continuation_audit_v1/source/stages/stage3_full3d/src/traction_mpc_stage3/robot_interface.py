"""Hardware-independent robot execution contract.

All timestamps use one backend-owned monotonic timebase.  No command mode is
assumed to exist on real hardware merely because a simulation backend supports
it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

import numpy as np

from .frames import RigidTransform


class CapabilityStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class CommandMode(str, Enum):
    DISABLED = "DISABLED"
    JOINT_POSITION = "JOINT_POSITION"
    JOINT_VELOCITY = "JOINT_VELOCITY"
    JOINT_TORQUE = "JOINT_TORQUE"


class RobotMode(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"
    PROTECTIVE_STOP = "PROTECTIVE_STOP"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    FAULT = "FAULT"
    DRY_RUN = "DRY_RUN"


class WatchdogStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    ARMED = "ARMED"
    EXPIRED = "EXPIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class FramedPose:
    parent_frame: str
    child_frame: str
    transform: RigidTransform

    def __post_init__(self) -> None:
        if not self.parent_frame or not self.child_frame:
            raise ValueError("pose frame names must be non-empty")
        if self.parent_frame == self.child_frame:
            raise ValueError("pose parent and child frames must differ")


@dataclass(frozen=True)
class FramedWrench:
    expressed_in_frame: str
    applied_at_frame: str
    force_n: np.ndarray
    moment_nm: np.ndarray

    def __post_init__(self) -> None:
        force = np.asarray(self.force_n, dtype=float)
        moment = np.asarray(self.moment_nm, dtype=float)
        if force.shape != (3,) or moment.shape != (3,):
            raise ValueError("wrench force and moment must be three-vectors")
        if not np.all(np.isfinite(force)) or not np.all(np.isfinite(moment)):
            raise ValueError("wrench must be finite")
        if not self.expressed_in_frame or not self.applied_at_frame:
            raise ValueError("wrench frame names must be non-empty")
        object.__setattr__(self, "force_n", force.copy())
        object.__setattr__(self, "moment_nm", moment.copy())


@dataclass(frozen=True)
class WatchdogState:
    status: WatchdogStatus
    last_command_timestamp_s: float | None
    active_deadline_s: float | None


@dataclass(frozen=True)
class RobotState:
    timestamp_s: float
    sequence: int
    q_rad: np.ndarray
    dq_rad_s: np.ndarray
    base_from_flange: FramedPose
    base_from_tcp: FramedPose
    jacobian_base_tcp: np.ndarray
    measured_joint_torque_nm: np.ndarray | None
    measured_motor_current_a: np.ndarray | None
    measured_tcp_wrench: FramedWrench | None
    robot_mode: RobotMode
    fault_code: str | None
    watchdog: WatchdogState

    def __post_init__(self) -> None:
        q = np.asarray(self.q_rad, dtype=float)
        dq = np.asarray(self.dq_rad_s, dtype=float)
        jacobian = np.asarray(self.jacobian_base_tcp, dtype=float)
        if self.timestamp_s < 0.0 or not np.isfinite(self.timestamp_s):
            raise ValueError("state timestamp must be finite and nonnegative")
        if self.sequence < 0 or q.ndim != 1 or q.size == 0 or dq.shape != q.shape:
            raise ValueError("state requires equally sized non-empty q and dq vectors")
        if jacobian.shape != (6, q.size):
            raise ValueError("TCP Jacobian must have shape (6, number of joints)")
        if not all(np.all(np.isfinite(value)) for value in (q, dq, jacobian)):
            raise ValueError("state q, dq, and Jacobian must be finite")
        for name in ("measured_joint_torque_nm", "measured_motor_current_a"):
            value = getattr(self, name)
            if value is not None:
                array = np.asarray(value, dtype=float)
                if array.shape != q.shape or not np.all(np.isfinite(array)):
                    raise ValueError(f"{name} must be absent or a finite joint vector")
                object.__setattr__(self, name, array.copy())
        object.__setattr__(self, "q_rad", q.copy())
        object.__setattr__(self, "dq_rad_s", dq.copy())
        object.__setattr__(self, "jacobian_base_tcp", jacobian.copy())


@dataclass(frozen=True)
class SoftwareLimitResult:
    accepted: bool
    checked_mode: CommandMode
    checked_at_s: float
    limit_source: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RobotCommand:
    mode: CommandMode
    vector: np.ndarray
    timestamp_s: float
    deadline_s: float
    enable_requested: bool
    software_limit_result: SoftwareLimitResult

    def __post_init__(self) -> None:
        vector = np.asarray(self.vector, dtype=float)
        if vector.ndim != 1 or not np.all(np.isfinite(vector)):
            raise ValueError("command vector must be finite and one-dimensional")
        if not np.isfinite(self.timestamp_s) or not np.isfinite(self.deadline_s):
            raise ValueError("command timestamp and deadline must be finite")
        if self.timestamp_s < 0.0 or self.deadline_s < self.timestamp_s:
            raise ValueError("command deadline must not precede its timestamp")
        if self.mode is CommandMode.DISABLED:
            if self.enable_requested or np.any(vector != 0.0):
                raise ValueError("DISABLED command must be disabled with a zero vector")
        elif not self.enable_requested:
            raise ValueError("motion command requires enable_requested=True")
        if self.software_limit_result.checked_mode is not self.mode:
            raise ValueError("software limit result mode does not match command mode")
        object.__setattr__(self, "vector", vector.copy())


@dataclass(frozen=True)
class CommandReceipt:
    accepted: bool
    transmitted: bool
    reason: str
    backend_timestamp_s: float


@dataclass(frozen=True)
class RobotCapabilities:
    backend_name: str
    robot_identity: str
    dof: int | None
    command_modes: Mapping[CommandMode, CapabilityStatus]
    joint_state: CapabilityStatus
    flange_pose: CapabilityStatus
    tcp_pose: CapabilityStatus
    jacobian: CapabilityStatus
    measured_joint_torque: CapabilityStatus
    measured_motor_current: CapabilityStatus
    measured_ft_wrench: CapabilityStatus
    stop_state: CapabilityStatus
    watchdog: CapabilityStatus
    command_frequency_hz: float | None
    feedback_frequency_hz: float | None
    transport: str | None
    evidence: str


@dataclass(frozen=True)
class FrameCalibration:
    """Replaceable physical chain BASE -> FLANGE -> ADAPTER -> CUFF."""

    base_frame: str
    flange_frame: str
    adapter_frame: str
    cuff_frame: str
    flange_from_adapter: RigidTransform
    adapter_from_cuff: RigidTransform
    provenance: str

    def __post_init__(self) -> None:
        names = (self.base_frame, self.flange_frame, self.adapter_frame, self.cuff_frame)
        if any(not name for name in names) or len(set(names)) != 4:
            raise ValueError("calibration requires four distinct non-empty frame names")
        if not self.provenance:
            raise ValueError("calibration provenance is required")

    @property
    def flange_from_cuff(self) -> RigidTransform:
        return self.flange_from_adapter.compose(self.adapter_from_cuff)


class CommandValidator:
    """Create commands only after explicit mode, dimension, deadline and limit checks."""

    def __init__(
        self,
        capabilities: RobotCapabilities,
        limits: Mapping[CommandMode, tuple[np.ndarray, np.ndarray]],
        *,
        limit_source: str,
    ) -> None:
        self.capabilities = capabilities
        self.limits = dict(limits)
        self.limit_source = limit_source

    def make_command(
        self,
        mode: CommandMode,
        vector: np.ndarray,
        *,
        timestamp_s: float,
        deadline_s: float,
        enable_requested: bool,
    ) -> RobotCommand:
        values = np.asarray(vector, dtype=float)
        reasons: list[str] = []
        status = self.capabilities.command_modes.get(mode, CapabilityStatus.UNKNOWN)
        if mode is not CommandMode.DISABLED and status is not CapabilityStatus.CONFIRMED:
            reasons.append(f"command mode {mode.value} is {status.value}")
        if deadline_s < timestamp_s:
            reasons.append("deadline precedes timestamp")
        expected_dof = self.capabilities.dof
        if expected_dof is not None and values.shape != (expected_dof,):
            reasons.append(f"command vector must contain {expected_dof} joints")
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            reasons.append("command vector is not finite and one-dimensional")
        if mode is CommandMode.DISABLED:
            if enable_requested or np.any(values != 0.0):
                reasons.append("disabled command requests enable or nonzero output")
        elif not enable_requested:
            reasons.append("motion command does not request enable")
        bounds = self.limits.get(mode)
        if mode is not CommandMode.DISABLED:
            if bounds is None:
                reasons.append("no documented software limits for command mode")
            elif values.ndim == 1:
                lower, upper = (np.asarray(item, dtype=float) for item in bounds)
                if values.shape != lower.shape or lower.shape != upper.shape:
                    reasons.append("software limit dimensions do not match command")
                elif np.any(values < lower) or np.any(values > upper):
                    reasons.append("command exceeds software limits")
        checked = SoftwareLimitResult(
            accepted=not reasons,
            checked_mode=mode,
            checked_at_s=float(timestamp_s),
            limit_source=self.limit_source,
            reasons=tuple(reasons),
        )
        # Invalid timestamps cannot form a RobotCommand by contract. Callers
        # receive an immediate ValueError before any backend can see it.
        return RobotCommand(
            mode=mode,
            vector=values,
            timestamp_s=float(timestamp_s),
            deadline_s=float(deadline_s),
            enable_requested=enable_requested,
            software_limit_result=checked,
        )


class RobotBackend(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> RobotCapabilities: ...

    @property
    @abstractmethod
    def calibration(self) -> FrameCalibration: ...

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def read_state(self) -> RobotState: ...

    @abstractmethod
    def submit_command(self, command: RobotCommand) -> CommandReceipt: ...
