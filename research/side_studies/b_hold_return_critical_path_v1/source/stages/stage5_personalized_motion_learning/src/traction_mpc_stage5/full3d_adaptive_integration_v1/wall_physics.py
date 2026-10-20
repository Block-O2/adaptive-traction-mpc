"""Single-owner native physics, immutable sensor grid and actual apply receipts.

Only old applied controls are integrated while host computations catch up.
Source times are fixed physical-grid acquisition epochs; materialization and
receipt on the host are separate events. No missed control output is replayed.
"""
from __future__ import annotations
from time import monotonic_ns, sleep
from typing import Callable, Any
import numpy as np
import gc


class WallPhysicsSession:
    def __init__(self, runtime: dict[str, Any], *, clock: Callable[[], int] = monotonic_ns,
                 sleeper: Callable[[float], None] = sleep, catchup_budget_s: float = 1.0,
                 stop_check: Callable[[], None] | None = None):
        self.runtime = runtime
        self.plant = runtime["plant"]
        self.clock, self.sleeper = clock, sleeper
        self.stop_check = stop_check
        self.dt = float(self.plant.model.opt.timestep)
        self.dt_ns = int(round(self.dt*1e9))
        self.sensor_steps = int(round(.005/self.dt))
        if self.dt_ns != 250_000 or self.sensor_steps != 20:
            raise ValueError("wall session requires unchanged 0.25 ms native / 200 Hz sensor grid")
        self.catchup_budget_ns = int(catchup_budget_s*1e9)
        self.gc_originally_enabled = gc.isenabled()
        self.gc_deferred = bool(runtime.get("autonomous_recovery_options", {}).get("defer_cyclic_gc", False))
        if self.gc_deferred:
            # Reference-counted reclamation continues. The finite <=47.420s
            # session retains a bounded graph for evidence anyway; cyclic
            # collections run before the epoch and after the physical session.
            gc.collect()
            gc.disable()
        self.origin_physics_s = float(self.plant.data.time)
        self.epoch_ns = self.clock()
        self.steps = 0
        self.events = []
        self.native_states = []
        self.end_ns = None
        self.samples = []
        self.sampled_estimates = []
        self.applied_commands = []
        if "last_command" in runtime:
            self.applied_commands.append({"origin":"offline validated support continuing into active epoch",
                "applied":True, "apply_ns":None, "active_hold_start_ns":self.epoch_ns,
                "start_physics_s":self.origin_physics_s, "end_physics_s":self.origin_physics_s,
                "native_steps":0, **runtime.get("offline_support_setup", {}),
                "command_torque_nm":runtime["last_command"].joint_torque_command_nm.copy()})
        self.active_receipt_index = len(self.applied_commands)-1 if self.applied_commands else None
        self.initial_native_boundary = self.native_boundary()
        self.phase_records = [{"phase":"COMMISSIONING", "start_physics_s":self.origin_physics_s,
                               "limit_s":7.420}]
        self.limit_violations = []
        self.active = True
        self.latest_truth = None
        self.maximum_backlog_ns = 0
        self.cycle_misses = 0
        self._last_poll_grid = -1
        self.gc_events = []
        def gc_event(phase, info):
            if self.active:
                self.gc_events.append({"phase":phase, "host_ns":self.clock(),
                    "physics_s":float(self.plant.data.time), **info})
        self._gc_callback = gc_event
        gc.callbacks.append(gc_event)

    def release_runtime_maintenance(self):
        if self._gc_callback in gc.callbacks:
            gc.callbacks.remove(self._gc_callback)
        if self.gc_deferred and self.gc_originally_enabled:
            gc.enable()

    def native_boundary(self):
        return {"time_s":float(self.plant.data.time), "host_read_ns":self.clock(),
                "qpos_evaluation_only":self.plant.data.qpos.copy(),
                "qvel_evaluation_only":self.plant.data.qvel.copy(),
                "command_torque_nm":self.plant.last_joint_torque.copy(),
                "contact_pairs_evaluation_only":self.plant.contact_pairs()}

    def set_phase(self, name, limit_s):
        self.phase_records[-1]["end_physics_s"] = float(self.plant.data.time)
        self.phase_records[-1]["duration_s"] = float(self.plant.data.time)-self.phase_records[-1]["start_physics_s"]
        self.phase_records.append({"phase":name, "start_physics_s":float(self.plant.data.time), "limit_s":float(limit_s)})

    def source_ns(self, time_s: float) -> int:
        return self.epoch_ns+round((time_s-self.origin_physics_s)*1e9)

    def capture(self, *, initial=False):
        # A genuinely new observation object is acquired at the active epoch.
        # Initial setup's measurement object is never registered/restamped.
        delay = self.source_ns(float(self.plant.data.time))-self.clock()
        if delay > 0:
            self.sleeper(delay/1e9)
        truth = self.plant.observe()
        layer = self.runtime["measurement_layer"]
        if initial:
            from traction_mpc_stage4.measurement import CausalMeasurementLayer
            layer = CausalMeasurementLayer(layer.case, truth, layer.preprocessing)
            self.runtime["measurement_layer"] = layer
            measurement = layer.current
        else:
            measurement = layer.update(truth)
        self.latest_truth = truth
        source = self.source_ns(measurement.sample_time_s)
        self.runtime["plan_lifecycle"].capture(measurement.sample_time_s, source)
        self.samples.append({"sample_time_s": float(measurement.sample_time_s),
                             "source_capture_ns": source, "host_materialized_ns": self.clock()})
        if "observer" in self.runtime:
            observation, interface = self.runtime["observer"].update(
                measurement, self.runtime["model"],
                human_model_version=str(self.runtime.get("model_sequence", "population_prior_v1")))
            command = self.runtime["last_command"]
            split = self.runtime["monitor"].update(
                sample_timestamp_s=observation.sample_timestamp_s,
                estimated_dq_rad_s=observation.as_array()[2:],
                cuff_force_world_n=interface.measured_force_world_n,
                cuff_moment_world_nm=interface.measured_moment_world_nm,
                interface_translation_human_m=interface.displacement_human_m,
                interface_velocity_human_m_s=interface.velocity_human_m_s,
                interface_rotation_human_rad=interface.rotation_error_human_rad,
                interface_angular_velocity_human_rad_s=interface.angular_velocity_human_rad_s,
                command_wrench_world=command.wrench_total_world,
                robot_joint_torque_command_nm=command.joint_torque_command_nm)
            self.sampled_estimates.append({"sample_time_s": float(observation.sample_timestamp_s),
                "estimated_state": observation.as_array().copy(),
                "model_version": observation.human_model_version,
                "human_motion_valid": split.human_motion_valid,
                "motion_source_sample_s": split.sample_timestamp_s,
                "fast_motion_valid": split.fast_motion_valid,
                "fast_motion_acceleration_rad_s2": split.fast_motion_acceleration_rad_s2.copy(),
                "human_motion_acceleration_rad_s2": split.human_motion_acceleration_rad_s2.copy()})
            terminal_hook = self.runtime.get("terminal_capture_hook")
            if terminal_hook is not None:
                terminal_hook(observation, measurement, interface, split)
        return truth, measurement

    def _step(self):
        before = float(self.plant.data.time)
        host_start = self.clock()
        try:
            if hasattr(self.plant, "step_native"):
                self.plant.step_native()
            else:
                self.plant.step()
        finally:
            # mj_step2 may have advanced even if a subsequent refresh failed.
            advanced = int(round((float(self.plant.data.time)-before)/self.dt))
            self.steps += advanced
            if advanced and self.active_receipt_index is not None:
                self.applied_commands[self.active_receipt_index]["native_steps"] += advanced
                self.applied_commands[self.active_receipt_index]["end_physics_s"] = float(self.plant.data.time)
            if advanced:
                self.native_states.append({"time_s": float(self.plant.data.time),
                    "host_step_start_ns": host_start, "host_step_finish_ns": self.clock(),
                    "qpos_evaluation_only": self.plant.data.qpos.copy(),
                    "qvel_evaluation_only": self.plant.data.qvel.copy(),
                    "command_torque_nm": self.plant.last_joint_torque.copy(),
                    "contact_pairs_evaluation_only": self.plant.contact_pairs()})
        phase = self.phase_records[-1]
        phase_elapsed = float(self.plant.data.time)-phase["start_physics_s"]
        for name, exceeded in (("PHYSICAL_PHASE_TIMEOUT_"+phase["phase"], phase_elapsed > phase["limit_s"]+1e-10),
                               ("PHYSICAL_SESSION_TIMEOUT", float(self.plant.data.time)-self.origin_physics_s > 47.420+1e-10)):
            if exceeded and not any(r["reason"] == name for r in self.limit_violations):
                self.limit_violations.append({"reason":name,"first_observed_physics_s":float(self.plant.data.time),
                    "host_observed_ns":self.clock(), "phase_elapsed_s":phase_elapsed})
        if "true_physics_monitor" in self.runtime:
            self.runtime["true_physics_monitor"].observe(self.plant)
        if self.steps % self.sensor_steps == 0:
            self.capture()

    def catch_up(self, reason: str, *, finalizing=False):
        if not self.active:
            return
        begin = self.clock()
        record = {"reason": reason, "host_start_ns": begin,
                  "start_physics_s": float(self.plant.data.time), "native_steps": 0}
        self.events.append(record)
        first = self.steps
        try:
            while True:
                now = self.clock()
                lag = now-(self.epoch_ns+self.steps*self.dt_ns)
                self.maximum_backlog_ns = max(self.maximum_backlog_ns, lag)
                if lag < self.dt_ns:
                    break
                if now-begin > self.catchup_budget_ns:
                    raise RuntimeError("WALL_PHYSICS_BACKLOG_UNRESOLVED")
                if self.stop_check is not None and self.steps % self.sensor_steps == 0 and not finalizing:
                    self.stop_check()
                # Fixed old command; no retroactive controller reconstruction.
                self._step()
            if self.limit_violations and not finalizing:
                # Already elapsed host time must still be represented. Record
                # overshoot; never pretend a late timeout stopped in the past.
                raise RuntimeError(self.limit_violations[0]["reason"])
        except BaseException as error:
            record["exception"] = f"{type(error).__name__}:{error}"
            raise
        finally:
            record.update(host_end_ns=self.clock(), end_physics_s=float(self.plant.data.time),
                          native_steps=self.steps-first,
                          quantization_or_backlog_ns=self.clock()-(self.epoch_ns+self.steps*self.dt_ns))

    def boundary(self):
        self.catch_up("control_poll")
        grid = self.steps//self.sensor_steps
        missed = max(0, grid-self._last_poll_grid-1)
        self.cycle_misses += missed
        self._last_poll_grid = grid
        sample = self.runtime["measurement_layer"].current
        return self.latest_truth, sample

    def next_control_tick(self):
        target = self.epoch_ns+(self.steps//self.sensor_steps+1)*self.sensor_steps*self.dt_ns
        delay = target-self.clock()
        if delay > 0:
            self.sleeper(delay/1e9)
        self.catch_up("next_control_tick")

    def prepare_apply(self, command, *, source_sample_time_s):
        ready = self.clock()
        target_step = max(self.steps, (ready-self.epoch_ns+self.dt_ns-1)//self.dt_ns)
        receipt = {"command_ready_ns":ready, "attempt_ns":ready,
                   "receipt_index":len(self.applied_commands),
                   "source_sample_time_s":float(source_sample_time_s),
                   "source_capture_ns":self.source_ns(source_sample_time_s),
                   "native_steps":0, "applied":False,
                   "command_torque_nm":command.joint_torque_command_nm.copy()}
        self.applied_commands.append(receipt)
        try:
            while self.steps < target_step:
                self._step()  # Still the active prior receipt / old control.
            receipt.update(effective_activation_ns=self.epoch_ns+self.steps*self.dt_ns,
                           start_physics_s=float(self.plant.data.time), end_physics_s=float(self.plant.data.time))
            if self.limit_violations:
                raise RuntimeError(self.limit_violations[0]["reason"])
        except BaseException as error:
            receipt["exception"] = f"{type(error).__name__}:{error}"
            raise
        return receipt

    def apply(self, command, apply, *, source_sample_time_s, commit=None, catchup=True, prepared=None):
        if catchup:
            self.catch_up("before_actual_command_apply")
        receipt = prepared if prepared is not None else self.prepare_apply(command, source_sample_time_s=source_sample_time_s)
        if max(self.clock(), receipt["effective_activation_ns"])-receipt["source_capture_ns"] > 100_000_000:
            receipt["cancelled_before_write_reason"] = "STALE_COMMAND_SOURCE_MAXIMUM_AGE"
            raise RuntimeError("STALE_COMMAND_SOURCE_MAXIMUM_AGE")
        # A failed simulated write is rolled back before any physics step.
        # A successful write followed by a commit exception remains active.
        old_ctrl = self.plant.data.ctrl.copy() if hasattr(self.plant.data, "ctrl") else None
        names = ("last_joint_torque", "last_unclipped_joint_torque", "last_force", "last_moment")
        old_fields = {name:getattr(self.plant,name).copy() for name in names if hasattr(self.plant,name)}
        try:
            try:
                apply()
            except BaseException:
                if old_ctrl is not None:
                    self.plant.data.ctrl[:] = old_ctrl
                for name, value in old_fields.items():
                    setattr(self.plant,name,value)
                receipt["failed_write_rolled_back_before_physics"] = True
                raise
            receipt.update(applied=True, apply_ns=self.clock())
            self.active_receipt_index = next(i for i,row in enumerate(self.applied_commands) if row is receipt)
            receipt["conservative_activation_ns"] = max(receipt["apply_ns"],receipt["effective_activation_ns"])
            receipt["sensor_age_at_apply_ms"] = (receipt["conservative_activation_ns"]-receipt["source_capture_ns"])/1e6
            receipt["host_write_minus_effective_grid_ns"] = receipt["apply_ns"]-receipt["effective_activation_ns"]
            if commit is not None:
                commit(receipt)
            if receipt["sensor_age_at_apply_ms"] > 100.:
                receipt["command_deadline_miss"] = True
                raise RuntimeError("COMMAND_WRITE_CROSSED_SOURCE_EXPIRATION")
        except BaseException as error:
            receipt["exception"] = f"{type(error).__name__}:{error}"
            error.applied_receipt = receipt
            raise
        finally:
            receipt["return_ns"] = self.clock()
        return receipt

    def record(self):
        now = self.clock() if self.end_ns is None else self.end_ns
        phases = [dict(row) for row in self.phase_records]
        phases[-1].update(end_physics_s=float(self.plant.data.time),
                          duration_s=float(self.plant.data.time)-phases[-1]["start_physics_s"])
        return {"schema": "whole_session_wall_physics_v2", "epoch_ns": self.epoch_ns,
                "origin_physics_s": self.origin_physics_s, "native_dt_s": self.dt,
                "sensor_period_s": .005, "catchup_budget_s": self.catchup_budget_ns/1e9,
                "policy": "catch up under last actual command; stop if a catch-up call exceeds host budget",
                "phase_boundaries":phases, "gc_events":self.gc_events,
                "gc_deferred_during_finite_active_session":self.gc_deferred,
                "phase_limit_violations":self.limit_violations,
                "initial_native_boundary_evaluation_only":self.initial_native_boundary,
                "final_native_boundary_evaluation_only":self.native_boundary(),
                "physics_elapsed_s": self.steps*self.dt, "wall_elapsed_s": (now-self.epoch_ns)/1e9,
                "current_backlog_s": (now-self.epoch_ns-self.steps*self.dt_ns)/1e9,
                "maximum_backlog_s": self.maximum_backlog_ns/1e9,
                "control_cycle_misses": self.cycle_misses,
                "sensor_samples": self.samples, "causal_sensor_estimates": self.sampled_estimates,
                "command_receipts": self.applied_commands,
                "catchup_intervals": self.events, "native_states_evaluation_only": self.native_states}
