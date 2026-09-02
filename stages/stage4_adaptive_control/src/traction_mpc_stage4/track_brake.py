"""Minimal TRACK/BRAKE execution supervisor for Stage 4.

BRAKE is a small, deterministic reference-rate search evaluated exclusively
through the shared Stage-3 executable-command contract.  It does not run an
MPC and never substitutes a seed, previous action, or zero action.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference

from .executable_command import (
    Stage4ExecutableCommandPreview,
    preview_stage4_executable_command,
)
from .mpc import NO_SAFE_ACTION, SAFE_ACTION
from .safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
    ExecutableForceFilterResult,
    filter_executable_command,
    prepare_executable_force_filter_context,
)


TRACK = "TRACK"
BRAKE = "BRAKE"
SAFE_BRAKE = "SAFE_BRAKE"
BRAKE_INFEASIBLE = "BRAKE_INFEASIBLE"


@dataclass(frozen=True)
class TrackBrakeConfig:
    """Trajectory-independent engineering limits for the braking reference."""

    braking_rates_per_s: tuple[float, ...] = (8.0, 6.0, 4.0, 3.0, 2.0, 1.0)
    maximum_reference_deceleration_rad_s2: float = math.radians(180.0)
    maximum_reference_jerk_rad_s3: float = math.radians(2000.0)
    force_gate_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N
    control_dt_s: float = EXECUTION_CONTROL_DT_S

    def __post_init__(self) -> None:
        rates = np.asarray(self.braking_rates_per_s, dtype=float)
        if rates.ndim != 1 or not len(rates) or not np.all(np.isfinite(rates)):
            raise ValueError("braking rates must be a finite nonempty sequence")
        if np.any(rates <= 0.0):
            raise ValueError("braking rates must be positive")
        if self.maximum_reference_deceleration_rad_s2 <= 0.0:
            raise ValueError("reference deceleration limit must be positive")
        if self.maximum_reference_jerk_rad_s3 <= 0.0:
            raise ValueError("reference jerk limit must be positive")
        if self.force_gate_n != CUFF_TRANSLATIONAL_FORCE_GATE_N:
            raise ValueError("TRACK/BRAKE must retain the existing 200 N gate")
        if self.control_dt_s != EXECUTION_CONTROL_DT_S:
            raise ValueError("TRACK/BRAKE execution convention is fixed at 5 ms")


@dataclass(frozen=True)
class SupervisorDecision:
    mode: str
    status: str
    action_nm: np.ndarray | None
    reference: CuffPoseReference | None
    executable_preview: Stage4ExecutableCommandPreview | None
    trigger: str | None
    feasible_candidate_count: int
    selected_braking_rate_per_s: float | None
    reference_speed_norm_rad_s: float | None
    terminate_reason: str | None
    computation_ms: float
    safety_filter: dict[str, Any] | None = None

    @property
    def terminate(self) -> bool:
        return self.status == BRAKE_INFEASIBLE


@dataclass(frozen=True)
class _BrakeCandidate:
    rate_per_s: float
    action_nm: np.ndarray
    reference: CuffPoseReference
    preview: Stage4ExecutableCommandPreview
    projected_speed_norm_rad_s: float


class TrackBrakeSupervisor:
    """Two-mode supervisor with an explicit terminal result, not a third mode."""

    def __init__(
        self,
        config: TrackBrakeConfig = TrackBrakeConfig(),
    ) -> None:
        self.config = config
        self.mode = TRACK
        self.trigger: str | None = None
        self.termination_reason: str | None = None
        self.transition_count = 0
        self.track_mpc_solve_count = 0
        self.brake_cycle_count = 0
        self.rejected_track_command_count = 0
        self.computation_ms: list[float] = []
        self.safety_filter_status_counts = {
            SAFE_UNCHANGED: 0,
            SAFE_FILTERED: 0,
            FILTER_INFEASIBLE: 0,
        }
        self.last_safety_filter: dict[str, Any] | None = None
        self._reference_q_rad: np.ndarray | None = None
        self._reference_dq_rad_s: np.ndarray | None = None
        self._reference_ddq_rad_s2: np.ndarray | None = None
        self._entry_pending = False

    @staticmethod
    def _finite_vector(name: str, value: np.ndarray, length: int) -> np.ndarray:
        result = np.asarray(value, dtype=float)
        if result.shape != (length,) or not np.all(np.isfinite(result)):
            raise ValueError(f"{name} must be a finite {length}-vector")
        return result

    def note_track_mpc_solve(self) -> None:
        """Record the single ordinary 50 Hz solve performed by the caller."""

        if self.mode == TRACK:
            self.track_mpc_solve_count += 1

    def _preview(
        self,
        *,
        plant: Any,
        measurement: Any,
        estimated_state: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
        action_nm: np.ndarray,
        reference: CuffPoseReference,
    ) -> Stage4ExecutableCommandPreview:
        return preview_stage4_executable_command(
            plant=plant,
            measurement=measurement,
            action_nm=action_nm,
            estimated_state=estimated_state,
            human_model=human_model,
            cuff_allocator=cuff_allocator,
            reference=reference,
        )

    def _command_is_safe(self, preview: Stage4ExecutableCommandPreview) -> bool:
        # The exact total-force decision comes from Stage 3.  The existing
        # independent allocator gate remains unchanged in the runtime caller.
        allocated_force = float(preview.allocation["force_norm_n"])
        return bool(
            preview.command.feasible
            and np.isfinite(allocated_force)
            and allocated_force <= self.config.force_gate_n + 1.0e-9
        )

    def _enter_brake(
        self,
        track_reference: CuffPoseReference,
        trigger: str,
    ) -> None:
        self.mode = BRAKE
        self.trigger = trigger
        self.transition_count += 1
        self.rejected_track_command_count += 1
        self._reference_q_rad = self._finite_vector(
            "track reference q", track_reference.q_rad, 2
        ).copy()
        self._reference_dq_rad_s = self._finite_vector(
            "track reference dq", track_reference.dq_rad_s, 2
        ).copy()
        self._reference_ddq_rad_s2 = self._finite_vector(
            "track reference ddq", track_reference.ddq_rad_s2, 2
        ).copy()
        self._entry_pending = True

    def _braking_acceleration(
        self,
        rate_per_s: float,
    ) -> np.ndarray:
        assert self._reference_dq_rad_s is not None
        assert self._reference_ddq_rad_s2 is not None
        desired = -float(rate_per_s) * self._reference_dq_rad_s
        deceleration = self.config.maximum_reference_deceleration_rad_s2
        desired = np.clip(desired, -deceleration, deceleration)
        maximum_change = (
            self.config.maximum_reference_jerk_rad_s3 * self.config.control_dt_s
        )
        return np.clip(
            desired,
            self._reference_ddq_rad_s2 - maximum_change,
            self._reference_ddq_rad_s2 + maximum_change,
        )

    def _candidate_reference(
        self,
        acceleration_rad_s2: np.ndarray,
        human_model: Any,
    ) -> CuffPoseReference:
        assert self._reference_q_rad is not None
        assert self._reference_dq_rad_s is not None
        dt = 0.0 if self._entry_pending else self.config.control_dt_s
        q = (
            self._reference_q_rad
            + dt * self._reference_dq_rad_s
            + 0.5 * dt**2 * acceleration_rad_s2
        )
        dq = self._reference_dq_rad_s + dt * acceleration_rad_s2
        return CuffPoseReference(
            q_rad=q,
            dq_rad_s=dq,
            ddq_rad_s2=acceleration_rad_s2.copy(),
            world_from_cuff=human_model.geometry.cuff_pose(q),
        )

    def _brake(
        self,
        *,
        plant: Any,
        measurement: Any,
        estimated_state: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
    ) -> SupervisorDecision:
        self.brake_cycle_count += 1
        state = self._finite_vector("estimated_state", estimated_state, 4)
        candidates: list[_BrakeCandidate] = []
        for rate in self.config.braking_rates_per_s:
            acceleration = self._braking_acceleration(rate)
            reference = self._candidate_reference(acceleration, human_model)
            action = np.asarray(
                human_model.inverse_dynamics(
                    state[:2], state[2:], acceleration
                ),
                dtype=float,
            )
            preview = self._preview(
                plant=plant,
                measurement=measurement,
                estimated_state=state,
                human_model=human_model,
                cuff_allocator=cuff_allocator,
                action_nm=action,
                reference=reference,
            )
            if self._command_is_safe(preview):
                projected_dq = (
                    reference.dq_rad_s
                    if not self._entry_pending
                    else self._reference_dq_rad_s
                    + self.config.control_dt_s * acceleration
                )
                candidates.append(
                    _BrakeCandidate(
                        rate_per_s=float(rate),
                        action_nm=action,
                        reference=reference,
                        preview=preview,
                        projected_speed_norm_rad_s=float(
                            np.linalg.norm(projected_dq)
                        ),
                    )
                )
        if not candidates:
            self.termination_reason = BRAKE_INFEASIBLE
            return SupervisorDecision(
                mode=BRAKE,
                status=BRAKE_INFEASIBLE,
                action_nm=None,
                reference=None,
                executable_preview=None,
                trigger=self.trigger,
                feasible_candidate_count=0,
                selected_braking_rate_per_s=None,
                reference_speed_norm_rad_s=(
                    float(np.linalg.norm(self._reference_dq_rad_s))
                    if self._reference_dq_rad_s is not None
                    else None
                ),
                terminate_reason=BRAKE_INFEASIBLE,
                computation_ms=0.0,
            )
        selected = min(
            candidates,
            key=lambda candidate: (
                candidate.projected_speed_norm_rad_s,
                candidate.preview.command.translational_force_norm_n,
                -candidate.rate_per_s,
            ),
        )
        self._reference_q_rad = selected.reference.q_rad.copy()
        self._reference_dq_rad_s = selected.reference.dq_rad_s.copy()
        self._reference_ddq_rad_s2 = selected.reference.ddq_rad_s2.copy()
        self._entry_pending = False
        return SupervisorDecision(
            mode=BRAKE,
            status=SAFE_BRAKE,
            action_nm=selected.action_nm.copy(),
            reference=selected.reference,
            executable_preview=selected.preview,
            trigger=self.trigger,
            feasible_candidate_count=len(candidates),
            selected_braking_rate_per_s=selected.rate_per_s,
            reference_speed_norm_rad_s=float(
                np.linalg.norm(selected.reference.dq_rad_s)
            ),
            terminate_reason=None,
            computation_ms=0.0,
        )

    def command(
        self,
        *,
        plant: Any,
        measurement: Any,
        estimated_state: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
        track_reference: CuffPoseReference,
        proposed_action_nm: np.ndarray | None,
        mpc_status: str | None,
        proposed_filter_result: ExecutableForceFilterResult | None = None,
    ) -> SupervisorDecision:
        """Return the only command eligible for this exact 5 ms cycle."""

        started = perf_counter()
        if mpc_status not in {None, SAFE_ACTION, NO_SAFE_ACTION}:
            raise ValueError("unexpected MPC executable-action status")
        filter_result: ExecutableForceFilterResult | None = None
        if self.mode == TRACK:
            track_preview: Stage4ExecutableCommandPreview | None = None
            if proposed_action_nm is not None and mpc_status != NO_SAFE_ACTION:
                proposed = np.asarray(proposed_action_nm, dtype=float)
                if proposed_filter_result is not None:
                    if not np.array_equal(proposed_filter_result.action_nm, proposed):
                        raise ValueError(
                            "carried safety-filter result does not match action"
                        )
                    filter_result = proposed_filter_result
                else:
                    filter_context = prepare_executable_force_filter_context(
                        plant=plant,
                        measurement=measurement,
                        estimated_state=estimated_state,
                        human_model=human_model,
                        cuff_allocator=cuff_allocator,
                        reference=track_reference,
                    )
                    filter_result = filter_executable_command(
                        filter_context,
                        proposed,
                    )
                self.safety_filter_status_counts[filter_result.status] += 1
                self.last_safety_filter = filter_result.metadata()
                if filter_result.feasible:
                    track_preview = filter_result.filtered_preview
            if track_preview is not None and self._command_is_safe(track_preview):
                decision = SupervisorDecision(
                    mode=TRACK,
                    status=SAFE_ACTION,
                    action_nm=np.asarray(proposed_action_nm, dtype=float).copy(),
                    reference=track_reference,
                    executable_preview=track_preview,
                    trigger=None,
                    feasible_candidate_count=1,
                    selected_braking_rate_per_s=None,
                    reference_speed_norm_rad_s=float(
                        np.linalg.norm(track_reference.dq_rad_s)
                    ),
                    terminate_reason=None,
                    computation_ms=0.0,
                    safety_filter=(
                        filter_result.metadata()
                        if filter_result is not None
                        else None
                    ),
                )
            else:
                if proposed_action_nm is None or mpc_status == NO_SAFE_ACTION:
                    trigger = NO_SAFE_ACTION
                elif (
                    filter_result is not None
                    and filter_result.status == FILTER_INFEASIBLE
                ):
                    trigger = FILTER_INFEASIBLE
                else:
                    trigger = "EXECUTABLE_PREVIEW_UNSAFE"
                self._enter_brake(track_reference, trigger)
                decision = self._brake(
                    plant=plant,
                    measurement=measurement,
                    estimated_state=estimated_state,
                    human_model=human_model,
                    cuff_allocator=cuff_allocator,
                )
        else:
            decision = self._brake(
                plant=plant,
                measurement=measurement,
                estimated_state=estimated_state,
                human_model=human_model,
                cuff_allocator=cuff_allocator,
            )
        elapsed_ms = 1000.0 * (perf_counter() - started)
        safety_filter = decision.safety_filter
        if safety_filter is None and filter_result is not None:
            safety_filter = filter_result.metadata()
        self.computation_ms.append(elapsed_ms)
        return SupervisorDecision(
            **{
                **decision.__dict__,
                "computation_ms": elapsed_ms,
                "safety_filter": safety_filter,
            }
        )

    def latency_summary(self) -> dict[str, float | int]:
        values = np.asarray(self.computation_ms, dtype=float)
        if not len(values):
            return {"count": 0, "mean_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        return {
            "count": int(len(values)),
            "mean_ms": float(np.mean(values)),
            "p95_ms": float(np.percentile(values, 95.0)),
            "max_ms": float(np.max(values)),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "active_mode": self.mode,
            "terminal_status": self.termination_reason,
            "trigger": self.trigger,
            "transition_count": self.transition_count,
            "track_mpc_solve_count": self.track_mpc_solve_count,
            "brake_cycle_count": self.brake_cycle_count,
            "rejected_track_command_count": self.rejected_track_command_count,
            "safety_filter_status_counts": dict(
                self.safety_filter_status_counts
            ),
            "last_safety_filter": self.last_safety_filter,
            "latency": self.latency_summary(),
            "normal_track_mpc_solves_per_50hz_cycle": 1,
            "brake_mpc_solves_per_cycle": 0,
            "runtime_force_gate_modified": False,
        }
