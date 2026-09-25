"""Deployable-only split channels for Stage-5 acceleration monitoring.

The signal monitor itself does not mutate task state.  Its Human-motion channel
uses only full causal ``dq_hat`` history and is consumed by the separate
``HumanMotionAccelerationAuthorityV1`` decision contract.  The fast channel
keeps measured/interface/command quantities aligned to the same completed
control interval and remains shadow-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


HUMAN_MOTION_WINDOW_S = 0.020
FAST_TRANSIENT_WINDOW_S = 0.005
SPLIT_ACCELERATION_MONITOR_VERSION = "split_acceleration_monitor_v1_shadow_only"
HUMAN_MOTION_ACCELERATION_AUTHORITY_VERSION = (
    "human_motion_acceleration_authority_v1"
)


def _vector(name: str, value: Any, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {length}-vector")
    return result.copy()


def _optional_vector(name: str, value: Any | None, length: int) -> np.ndarray:
    if value is None:
        return np.full(length, np.nan)
    return _vector(name, value, length)


@dataclass(frozen=True)
class SplitAccelerationShadowSample:
    """One event-aligned, deployable-only shadow observation."""

    sample_timestamp_s: float
    human_motion_acceleration_rad_s2: np.ndarray
    human_motion_valid: bool
    human_motion_history_coverage_s: float
    human_motion_history_sample_count: int
    fast_motion_acceleration_rad_s2: np.ndarray
    fast_motion_valid: bool
    fast_alignment_interval_s: float
    cuff_wrench_world: np.ndarray
    cuff_wrench_slew_world_per_s: np.ndarray
    interface_translation_human_m: np.ndarray
    interface_velocity_human_m_s: np.ndarray
    interface_rotation_human_rad: np.ndarray
    interface_angular_velocity_human_rad_s: np.ndarray
    command_wrench_world: np.ndarray
    command_wrench_slew_world_per_s: np.ndarray
    robot_joint_torque_command_nm: np.ndarray
    robot_joint_torque_slew_nm_s: np.ndarray
    robot_joint_torque_available: bool
    robot_joint_torque_slew_valid: bool
    version: str = SPLIT_ACCELERATION_MONITOR_VERSION
    shadow_only: bool = True
    abort_authority: bool = False

    def __post_init__(self) -> None:
        if not np.isfinite(self.sample_timestamp_s) or self.sample_timestamp_s < 0.0:
            raise ValueError("sample timestamp must be finite and nonnegative")
        if (
            not np.isfinite(self.human_motion_history_coverage_s)
            or self.human_motion_history_coverage_s < 0.0
            or self.human_motion_history_coverage_s
            > HUMAN_MOTION_WINDOW_S + 1.0e-12
        ):
            raise ValueError("Human-motion history coverage is invalid")
        if self.human_motion_history_sample_count < 1:
            raise ValueError("Human-motion history must contain the current sample")
        if (
            not np.isfinite(self.fast_alignment_interval_s)
            and not np.isnan(self.fast_alignment_interval_s)
        ):
            raise ValueError("fast alignment interval is invalid")
        for name, value, length in (
            ("human_motion_acceleration_rad_s2", self.human_motion_acceleration_rad_s2, 2),
            ("fast_motion_acceleration_rad_s2", self.fast_motion_acceleration_rad_s2, 2),
            ("cuff_wrench_world", self.cuff_wrench_world, 6),
            ("cuff_wrench_slew_world_per_s", self.cuff_wrench_slew_world_per_s, 6),
            ("interface_translation_human_m", self.interface_translation_human_m, 3),
            ("interface_velocity_human_m_s", self.interface_velocity_human_m_s, 3),
            ("interface_rotation_human_rad", self.interface_rotation_human_rad, 3),
            (
                "interface_angular_velocity_human_rad_s",
                self.interface_angular_velocity_human_rad_s,
                3,
            ),
            ("command_wrench_world", self.command_wrench_world, 6),
            (
                "command_wrench_slew_world_per_s",
                self.command_wrench_slew_world_per_s,
                6,
            ),
            ("robot_joint_torque_command_nm", self.robot_joint_torque_command_nm, 6),
            ("robot_joint_torque_slew_nm_s", self.robot_joint_torque_slew_nm_s, 6),
        ):
            array = np.asarray(value, dtype=float)
            if array.shape != (length,):
                raise ValueError(f"{name} must be a {length}-vector")
            object.__setattr__(self, name, array.copy())
        if self.human_motion_valid and not np.all(
            np.isfinite(self.human_motion_acceleration_rad_s2)
        ):
            raise ValueError("valid Human-motion acceleration must be finite")
        if self.fast_motion_valid:
            for value in (
                self.fast_motion_acceleration_rad_s2,
                self.cuff_wrench_slew_world_per_s,
                self.command_wrench_slew_world_per_s,
            ):
                if not np.all(np.isfinite(value)):
                    raise ValueError("valid fast-transient fields must be finite")
        if self.robot_joint_torque_available and not np.all(
            np.isfinite(self.robot_joint_torque_command_nm)
        ):
            raise ValueError("available robot joint torque must be finite")
        if self.robot_joint_torque_slew_valid and not np.all(
            np.isfinite(self.robot_joint_torque_slew_nm_s)
        ):
            raise ValueError("valid robot joint-torque slew must be finite")
        if not self.shadow_only or self.abort_authority:
            raise ValueError("SplitAccelerationMonitorV1 must remain shadow-only")


@dataclass(frozen=True)
class HumanMotionAccelerationAuthorityDecision:
    """One authority decision based only on a full 20 ms ``dq_hat`` window."""

    sample_timestamp_s: float
    acceleration_rad_s2: np.ndarray
    limit_rad_s2: np.ndarray
    history_valid: bool
    history_coverage_s: float
    history_sample_count: int
    authority_active: bool
    violation: bool
    abort_reason: str | None
    source: str = "full_causal_20ms_deployable_dq_hat_history"
    version: str = HUMAN_MOTION_ACCELERATION_AUTHORITY_VERSION
    truth_used_online: bool = False
    model_based_qdd_used: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acceleration_rad_s2",
            np.asarray(self.acceleration_rad_s2, dtype=float).copy(),
        )
        object.__setattr__(
            self,
            "limit_rad_s2",
            _vector("limit_rad_s2", self.limit_rad_s2, 2),
        )
        if self.acceleration_rad_s2.shape != (2,):
            raise ValueError("Human-motion authority acceleration must be a two-vector")
        if self.authority_active != self.history_valid:
            raise ValueError("Human-motion authority requires valid full history")
        if self.authority_active and not np.all(
            np.isfinite(self.acceleration_rad_s2)
        ):
            raise ValueError("active Human-motion authority must be finite")
        if self.violation != (self.abort_reason == "TASK_ACCELERATION_LIMIT"):
            raise ValueError("Human-motion violation reason is inconsistent")
        if self.violation and not self.authority_active:
            raise ValueError("invalid history cannot request a Human-motion abort")
        if self.truth_used_online or self.model_based_qdd_used:
            raise ValueError("Human-motion authority must remain deployable-only")


class HumanMotionAccelerationAuthorityV1:
    """Apply the existing limits only to valid full-window Human motion."""

    def __init__(self, limit_rad_s2: Any) -> None:
        self.limit_rad_s2 = _vector("limit_rad_s2", limit_rad_s2, 2)
        if np.any(self.limit_rad_s2 <= 0.0):
            raise ValueError("Human-motion acceleration limits must be positive")

    def evaluate(
        self, sample: SplitAccelerationShadowSample
    ) -> HumanMotionAccelerationAuthorityDecision:
        coverage_full = bool(
            np.isclose(
                sample.human_motion_history_coverage_s,
                HUMAN_MOTION_WINDOW_S,
                atol=1.0e-10,
                rtol=0.0,
            )
        )
        if sample.human_motion_valid != coverage_full:
            raise ValueError(
                "Human-motion validity must match full 20 ms history coverage"
            )
        if sample.human_motion_valid and sample.human_motion_history_sample_count < 2:
            raise ValueError("valid Human-motion authority requires history samples")
        violation = bool(
            sample.human_motion_valid
            and np.any(
                np.abs(sample.human_motion_acceleration_rad_s2)
                > self.limit_rad_s2
            )
        )
        return HumanMotionAccelerationAuthorityDecision(
            sample_timestamp_s=sample.sample_timestamp_s,
            acceleration_rad_s2=(
                sample.human_motion_acceleration_rad_s2
                if sample.human_motion_valid
                else np.full(2, np.nan)
            ),
            limit_rad_s2=self.limit_rad_s2,
            history_valid=sample.human_motion_valid,
            history_coverage_s=sample.human_motion_history_coverage_s,
            history_sample_count=sample.human_motion_history_sample_count,
            authority_active=sample.human_motion_valid,
            violation=violation,
            abort_reason="TASK_ACCELERATION_LIMIT" if violation else None,
        )


@dataclass(frozen=True)
class _RawShadowSample:
    timestamp_s: float
    dq_hat_rad_s: np.ndarray
    cuff_wrench_world: np.ndarray
    command_wrench_world: np.ndarray
    robot_joint_torque_command_nm: np.ndarray
    robot_joint_torque_available: bool


class SplitAccelerationMonitorV1:
    """Shadow-only split monitor with independent 20 ms and 5 ms channels."""

    def __init__(
        self,
        *,
        human_motion_window_s: float = HUMAN_MOTION_WINDOW_S,
        fast_transient_window_s: float = FAST_TRANSIENT_WINDOW_S,
    ) -> None:
        if not np.isclose(human_motion_window_s, HUMAN_MOTION_WINDOW_S):
            raise ValueError("V1 Human-motion window is fixed at 20 ms")
        if not np.isclose(fast_transient_window_s, FAST_TRANSIENT_WINDOW_S):
            raise ValueError("V1 fast-transient window is fixed at 5 ms")
        self.human_motion_window_s = float(human_motion_window_s)
        self.fast_transient_window_s = float(fast_transient_window_s)
        self._history: list[_RawShadowSample] = []
        self._latest: SplitAccelerationShadowSample | None = None

    def reset(self) -> None:
        self._history.clear()
        self._latest = None

    @property
    def latest(self) -> SplitAccelerationShadowSample | None:
        """Return the latest immutable shadow sample for diagnostic cloning."""

        return self._latest

    def update(
        self,
        *,
        sample_timestamp_s: float,
        estimated_dq_rad_s: Any,
        cuff_force_world_n: Any,
        cuff_moment_world_nm: Any,
        interface_translation_human_m: Any,
        interface_velocity_human_m_s: Any,
        interface_rotation_human_rad: Any,
        interface_angular_velocity_human_rad_s: Any,
        command_wrench_world: Any,
        robot_joint_torque_command_nm: Any | None,
    ) -> SplitAccelerationShadowSample:
        timestamp = float(sample_timestamp_s)
        if not np.isfinite(timestamp) or timestamp < 0.0:
            raise ValueError("sample timestamp must be finite and nonnegative")
        if self._history:
            delta = timestamp - self._history[-1].timestamp_s
            if delta < -1.0e-12:
                raise ValueError("split monitor requires increasing timestamps")
            if abs(delta) <= 1.0e-12:
                assert self._latest is not None
                return self._latest

        dq_hat = _vector("estimated_dq_rad_s", estimated_dq_rad_s, 2)
        cuff_wrench = np.concatenate(
            [
                _vector("cuff_force_world_n", cuff_force_world_n, 3),
                _vector("cuff_moment_world_nm", cuff_moment_world_nm, 3),
            ]
        )
        command_wrench = _vector("command_wrench_world", command_wrench_world, 6)
        torque_available = robot_joint_torque_command_nm is not None
        torque = _optional_vector(
            "robot_joint_torque_command_nm", robot_joint_torque_command_nm, 6
        )
        raw = _RawShadowSample(
            timestamp_s=timestamp,
            dq_hat_rad_s=dq_hat,
            cuff_wrench_world=cuff_wrench,
            command_wrench_world=command_wrench,
            robot_joint_torque_command_nm=torque,
            robot_joint_torque_available=torque_available,
        )
        previous = None if not self._history else self._history[-1]
        self._history.append(raw)

        coverage = min(
            self.human_motion_window_s,
            timestamp - self._history[0].timestamp_s,
        )
        human_acceleration, human_valid = self._motion_acceleration(
            timestamp, dq_hat, self.human_motion_window_s
        )
        fast_acceleration, fast_valid = self._motion_acceleration(
            timestamp, dq_hat, self.fast_transient_window_s
        )
        fast_interval = (
            float("nan") if previous is None else timestamp - previous.timestamp_s
        )
        aligned_fast_sample = bool(
            previous is not None
            and np.isclose(
                fast_interval,
                self.fast_transient_window_s,
                atol=1.0e-10,
                rtol=0.0,
            )
        )
        if aligned_fast_sample:
            cuff_slew = (cuff_wrench - previous.cuff_wrench_world) / fast_interval
            command_slew = (
                command_wrench - previous.command_wrench_world
            ) / fast_interval
        else:
            cuff_slew = np.full(6, np.nan)
            command_slew = np.full(6, np.nan)
        torque_slew_valid = bool(
            aligned_fast_sample
            and torque_available
            and previous is not None
            and previous.robot_joint_torque_available
        )
        torque_slew = (
            (torque - previous.robot_joint_torque_command_nm) / fast_interval
            if torque_slew_valid and previous is not None
            else np.full(6, np.nan)
        )
        cutoff = timestamp - self.human_motion_window_s
        history_count = sum(
            sample.timestamp_s >= cutoff - 1.0e-12 for sample in self._history
        )
        result = SplitAccelerationShadowSample(
            sample_timestamp_s=timestamp,
            human_motion_acceleration_rad_s2=human_acceleration,
            human_motion_valid=human_valid,
            human_motion_history_coverage_s=coverage,
            human_motion_history_sample_count=history_count,
            fast_motion_acceleration_rad_s2=fast_acceleration,
            fast_motion_valid=fast_valid and aligned_fast_sample,
            fast_alignment_interval_s=fast_interval,
            cuff_wrench_world=cuff_wrench,
            cuff_wrench_slew_world_per_s=cuff_slew,
            interface_translation_human_m=_vector(
                "interface_translation_human_m",
                interface_translation_human_m,
                3,
            ),
            interface_velocity_human_m_s=_vector(
                "interface_velocity_human_m_s",
                interface_velocity_human_m_s,
                3,
            ),
            interface_rotation_human_rad=_vector(
                "interface_rotation_human_rad", interface_rotation_human_rad, 3
            ),
            interface_angular_velocity_human_rad_s=_vector(
                "interface_angular_velocity_human_rad_s",
                interface_angular_velocity_human_rad_s,
                3,
            ),
            command_wrench_world=command_wrench,
            command_wrench_slew_world_per_s=command_slew,
            robot_joint_torque_command_nm=torque,
            robot_joint_torque_slew_nm_s=torque_slew,
            robot_joint_torque_available=torque_available,
            robot_joint_torque_slew_valid=torque_slew_valid,
        )
        self._latest = result
        self._prune(timestamp)
        return result

    def _motion_acceleration(
        self, timestamp: float, current_dq: np.ndarray, window_s: float
    ) -> tuple[np.ndarray, bool]:
        cutoff = timestamp - window_s
        if self._history[0].timestamp_s > cutoff + 1.0e-12:
            return np.full(2, np.nan), False
        for index, sample in enumerate(self._history):
            if np.isclose(sample.timestamp_s, cutoff, atol=1.0e-10, rtol=0.0):
                return (current_dq - sample.dq_hat_rad_s) / window_s, True
            if sample.timestamp_s > cutoff:
                if index == 0:
                    break
                left = self._history[index - 1]
                alpha = (cutoff - left.timestamp_s) / (
                    sample.timestamp_s - left.timestamp_s
                )
                cutoff_dq = left.dq_hat_rad_s + alpha * (
                    sample.dq_hat_rad_s - left.dq_hat_rad_s
                )
                return (current_dq - cutoff_dq) / window_s, True
        return np.full(2, np.nan), False

    def _prune(self, timestamp: float) -> None:
        cutoff = timestamp - self.human_motion_window_s
        while len(self._history) > 2 and self._history[1].timestamp_s <= cutoff:
            self._history.pop(0)


__all__ = [
    "FAST_TRANSIENT_WINDOW_S",
    "HUMAN_MOTION_ACCELERATION_AUTHORITY_VERSION",
    "HUMAN_MOTION_WINDOW_S",
    "SPLIT_ACCELERATION_MONITOR_VERSION",
    "HumanMotionAccelerationAuthorityDecision",
    "HumanMotionAccelerationAuthorityV1",
    "SplitAccelerationMonitorV1",
    "SplitAccelerationShadowSample",
]
