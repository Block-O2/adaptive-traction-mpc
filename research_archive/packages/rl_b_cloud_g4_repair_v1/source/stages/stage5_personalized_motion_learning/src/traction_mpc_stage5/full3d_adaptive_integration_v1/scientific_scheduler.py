"""Frozen-epoch execution adapter for scientific MuJoCo runs.

Wall timestamps remain honest profiling data. Only explicit native steps advance
the plant, and no worker is allowed to outlive the epoch that submitted it.
"""
from __future__ import annotations

from time import monotonic_ns
from typing import Any

from .wall_physics import WallPhysicsSession


class ScientificPhysicsSession(WallPhysicsSession):
    scientific = True

    def source_ns(self, time_s: float) -> int:
        # This is a host observation timestamp, never a simulated timestamp.
        for sample in reversed(self.samples):
            if abs(sample["sample_time_s"] - float(time_s)) <= 1e-12:
                return int(sample["source_capture_ns"])
        return self.clock()

    def catch_up(self, reason: str, *, finalizing: bool = False):
        if not self.active:
            return
        self.events.append({"reason": reason, "host_start_ns": self.clock(),
                            "host_end_ns": self.clock(), "start_physics_s": float(self.plant.data.time),
                            "end_physics_s": float(self.plant.data.time), "native_steps": 0,
                            "scientific_frozen_epoch": True})

    def boundary(self):
        self.catch_up("control_poll")
        return self.latest_truth, self.runtime["measurement_layer"].current

    def next_control_tick(self):
        if not self.active:
            raise RuntimeError("SCIENTIFIC_STEP_AFTER_TERMINAL_COMMIT")
        if self.steps % self.sensor_steps:
            raise RuntimeError("SCIENTIFIC_CONTROL_GRID_MISALIGNED")
        for _ in range(self.sensor_steps):
            if self.stop_check is not None:
                self.stop_check()
            self._step()

    def prepare_apply(self, command, *, source_sample_time_s):
        if not self.active:
            raise RuntimeError("SCIENTIFIC_WRITE_AFTER_TERMINAL_COMMIT")
        now = self.clock()
        source = self.source_ns(source_sample_time_s)
        receipt = {"command_ready_ns": now, "attempt_ns": now,
                   "receipt_index": len(self.applied_commands),
                   "source_sample_time_s": float(source_sample_time_s),
                   "source_capture_ns": source, "effective_activation_ns": now,
                   "start_physics_s": float(self.plant.data.time),
                   "end_physics_s": float(self.plant.data.time),
                   "native_steps": 0, "applied": False,
                   "command_torque_nm": command.joint_torque_command_nm.copy()}
        self.applied_commands.append(receipt)
        return receipt

    def apply(self, command, apply, *, source_sample_time_s, commit=None,
              catchup=True, prepared=None):
        # Do not invoke WallPhysicsSession.apply: its source expiration is wall
        # causal. A failed simulated write is rolled back before any step.
        receipt = prepared if prepared is not None else self.prepare_apply(
            command, source_sample_time_s=source_sample_time_s)
        if self.steps % self.sensor_steps:
            raise RuntimeError("SCIENTIFIC_WRITE_OFF_GRID")
        if float(self.plant.data.time) - source_sample_time_s >= .100 - 1e-12:
            receipt["cancelled_before_write_reason"] = "STALE_SIMULATED_SOURCE_MAXIMUM_AGE"
            raise RuntimeError("STALE_SIMULATED_SOURCE_MAXIMUM_AGE")
        old_ctrl = self.plant.data.ctrl.copy() if hasattr(self.plant.data, "ctrl") else None
        names = ("last_joint_torque", "last_unclipped_joint_torque", "last_force", "last_moment")
        old_fields = {name: getattr(self.plant, name).copy() for name in names
                      if hasattr(self.plant, name)}
        try:
            try:
                apply()
            except BaseException:
                if old_ctrl is not None:
                    self.plant.data.ctrl[:] = old_ctrl
                for name, value in old_fields.items():
                    setattr(self.plant, name, value)
                receipt["failed_write_rolled_back_before_physics"] = True
                raise
            receipt.update(applied=True, apply_ns=self.clock())
            self.active_receipt_index = next(i for i, row in enumerate(self.applied_commands)
                                             if row is receipt)
            receipt["conservative_activation_ns"] = receipt["apply_ns"]
            receipt["sensor_age_at_apply_ms"] = 1000.0 * (
                float(self.plant.data.time) - source_sample_time_s)
            receipt["host_sensor_age_at_apply_ms_profile"] = (
                receipt["apply_ns"] - receipt["source_capture_ns"]) / 1e6
            receipt["host_write_minus_effective_grid_ns"] = 0
            if commit is not None:
                commit(receipt)
        except BaseException as error:
            receipt["exception"] = f"{type(error).__name__}:{error}"
            error.applied_receipt = receipt
            raise
        finally:
            receipt["return_ns"] = self.clock()
        return receipt

    def record(self):
        row = super().record()
        row.update(schema="scientific_frozen_epoch_physics_v1",
                   policy="exactly 20 native steps after committed 5 ms command; host time is profiling only",
                   current_backlog_s=None, maximum_backlog_s=None,
                   control_cycle_misses=0)
        return row
