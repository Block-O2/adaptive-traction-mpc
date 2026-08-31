"""Minimal Stage-4 force-feasibility recovery supervisor.

The supervisor does not alter MPC/CEM, trust, allocation, or the independent
200 N runtime gate.  It previews the exact executable low-level first command,
rejects an unsafe proposal, freezes reference progress, and uses the existing
MPC against that frozen reference before attempting a smooth recovery.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference

from .high_rom_dynamic_pilot import PILOT_DURATION_S, HighROMPilotTrajectory


NORMAL = "NORMAL"
HOLD = "HOLD"
RECOVERY_SCAN = "RECOVERY_SCAN"
RECOVER = "RECOVER"
TERMINATE = "TERMINATE"

MODE_CODE = {
    NORMAL: 0.0,
    HOLD: 1.0,
    RECOVERY_SCAN: 2.0,
    RECOVER: 3.0,
    TERMINATE: 4.0,
}


@dataclass(frozen=True)
class ForceFeasibilityRecoveryConfig:
    force_gate_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N
    hold_force_reserve_n: float = 5.0
    settle_q_error_norm_deg: float = 2.0
    settle_dq_error_norm_deg_s: float = 5.0
    settle_dwell_s: float = 0.10
    recovery_rate_per_s: float = 0.25
    recovery_normal_dwell_s: float = 0.10
    alpha_search_coarse_intervals: int = 8
    alpha_search_tolerance: float = 1.0e-3
    maximum_hold_duration_s: float = 2.0
    maximum_recovery_attempts: int = 3

    def __post_init__(self) -> None:
        if self.force_gate_n != CUFF_TRANSLATIONAL_FORCE_GATE_N:
            raise ValueError("the recovery layer must retain the 200 N hard gate")
        if not 0.0 < self.hold_force_reserve_n < self.force_gate_n:
            raise ValueError("hold reserve must be positive and below the force gate")
        if self.settle_q_error_norm_deg <= 0.0:
            raise ValueError("settle q-error threshold must be positive")
        if self.settle_dq_error_norm_deg_s <= 0.0:
            raise ValueError("settle dq-error threshold must be positive")
        if self.settle_dwell_s <= 0.0 or self.recovery_normal_dwell_s <= 0.0:
            raise ValueError("dwell times must be positive")
        if self.recovery_rate_per_s <= 0.0:
            raise ValueError("recovery rate must be positive")
        if self.alpha_search_coarse_intervals < 4:
            raise ValueError("alpha search needs at least four coarse intervals")
        if not 0.0 < self.alpha_search_tolerance < 0.1:
            raise ValueError("alpha search tolerance must be in (0, 0.1)")
        if self.maximum_hold_duration_s <= self.settle_dwell_s:
            raise ValueError("hold timeout must exceed settle dwell")
        if self.maximum_recovery_attempts < 1:
            raise ValueError("at least one recovery attempt is required")

    @property
    def hold_force_limit_n(self) -> float:
        return self.force_gate_n - self.hold_force_reserve_n

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hold_force_limit_n"] = self.hold_force_limit_n
        return payload


class ForceFeasibilityRecoverySupervisor:
    """Reference clock plus exact first-command safety supervisor."""

    def __init__(
        self,
        trajectory: HighROMPilotTrajectory,
        *,
        config: ForceFeasibilityRecoveryConfig = ForceFeasibilityRecoveryConfig(),
    ) -> None:
        self.trajectory = trajectory
        self.config = config
        self.mode = NORMAL
        self._anchor_wall_s = 0.0
        self._anchor_phase_s = 0.0
        self._anchor_alpha = 1.0
        self._target_alpha = 1.0
        self._hold_phase_s: float | None = None
        self._hold_started_s: float | None = None
        self._settled_since_s: float | None = None
        self._normal_feasible_since_s: float | None = None
        self._last_safe_action = np.zeros(2, dtype=float)
        self._last_scan_peak_n = 0.0
        self._last_scan_maximum_safe_alpha: float | None = None
        self._termination_reason: str | None = None
        self._recovery_classification: str | None = None
        self._active_hold_event: dict[str, Any] | None = None
        self.hold_events: list[dict[str, Any]] = []
        self.transitions: list[dict[str, Any]] = []
        self.scan_records: list[dict[str, Any]] = []
        self.filter_latency_ms: list[float] = []
        self.scan_latency_ms: list[float] = []
        self.rejected_proposal_count = 0
        self.rejected_no_feasible_cem_count = 0
        self.maximum_rejected_force_n = 0.0
        self.recovery_attempt_count = 0
        self.fallback_action_count = 0

    def _clock_state(self, wall_time_s: float) -> tuple[float, float, float]:
        now = float(wall_time_s)
        elapsed = max(0.0, now - self._anchor_wall_s)
        delta = self._target_alpha - self._anchor_alpha
        if abs(delta) <= 1.0e-15:
            phase = self._anchor_phase_s + self._anchor_alpha * elapsed
            return float(np.clip(phase, 0.0, PILOT_DURATION_S)), self._anchor_alpha, 0.0
        rate = np.sign(delta) * self.config.recovery_rate_per_s
        duration = abs(delta) / self.config.recovery_rate_per_s
        ramp_time = min(elapsed, duration)
        phase = (
            self._anchor_phase_s
            + self._anchor_alpha * ramp_time
            + 0.5 * rate * ramp_time**2
        )
        if elapsed > duration:
            phase += self._target_alpha * (elapsed - duration)
            alpha = self._target_alpha
            alpha_rate = 0.0
        else:
            alpha = self._anchor_alpha + rate * ramp_time
            alpha_rate = rate
        return float(np.clip(phase, 0.0, PILOT_DURATION_S)), float(alpha), float(alpha_rate)

    def _reanchor(
        self,
        wall_time_s: float,
        *,
        phase_s: float,
        alpha: float,
        target_alpha: float,
    ) -> None:
        self._anchor_wall_s = float(wall_time_s)
        self._anchor_phase_s = float(np.clip(phase_s, 0.0, PILOT_DURATION_S))
        self._anchor_alpha = float(np.clip(alpha, 0.0, 1.0))
        self._target_alpha = float(np.clip(target_alpha, 0.0, 1.0))

    def _transition(self, mode: str, wall_time_s: float, reason: str) -> None:
        previous = self.mode
        if previous == mode:
            return
        self.mode = mode
        self.transitions.append(
            {
                "wall_time_s": float(wall_time_s),
                "from": previous,
                "to": mode,
                "reason": reason,
            }
        )

    def _reference_at(
        self, phase_s: float, alpha: float, alpha_rate: float
    ) -> CuffPoseReference:
        base = self.trajectory.reference(float(phase_s))
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=float(alpha) * base.dq_rad_s,
            ddq_rad_s2=(
                float(alpha) ** 2 * base.ddq_rad_s2
                + float(alpha_rate) * base.dq_rad_s
            ),
            world_from_cuff=base.world_from_cuff,
        )

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        phase, alpha, alpha_rate = self._clock_state(wall_time_s)
        return self._reference_at(phase, alpha, alpha_rate)

    @staticmethod
    def _total_force_n(command: dict[str, Any]) -> float:
        return float(command["preview"]["force_norm_n"])

    def _is_safe(self, command: dict[str, Any]) -> bool:
        allocated = float(command["allocation"]["force_norm_n"])
        total = self._total_force_n(command)
        return bool(
            np.isfinite(allocated)
            and np.isfinite(total)
            and allocated <= self.config.force_gate_n + 1.0e-9
            and total <= self.config.force_gate_n + 1.0e-9
        )

    def _hold_reference(self) -> CuffPoseReference:
        if self._hold_phase_s is None:
            raise RuntimeError("HOLD reference requested before phase was frozen")
        return self._reference_at(self._hold_phase_s, 0.0, 0.0)

    def _safest_hold_command(
        self,
        evaluate_command: Callable[[np.ndarray, CuffPoseReference], dict[str, Any]],
        *,
        include_proposed: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        reference = self._hold_reference()
        candidates = [
            evaluate_command(self._last_safe_action, reference),
            evaluate_command(np.zeros(2, dtype=float), reference),
        ]
        if include_proposed is not None:
            candidates.append(
                evaluate_command(
                    np.asarray(include_proposed["action"], dtype=float), reference
                )
            )
        safe = [candidate for candidate in candidates if self._is_safe(candidate)]
        if not safe:
            return None
        return min(safe, key=self._total_force_n)

    def _terminate(self, wall_time_s: float, reason: str) -> dict[str, Any]:
        self._termination_reason = reason
        self._recovery_classification = "UNRECOVERABLE"
        self._close_hold_event(wall_time_s, reason)
        self._transition(TERMINATE, wall_time_s, reason)
        return {"terminate_reason": reason}

    def _close_hold_event(self, wall_time_s: float, outcome: str) -> None:
        if self._active_hold_event is None:
            return
        event = dict(self._active_hold_event)
        event["end_time_s"] = float(wall_time_s)
        event["duration_s"] = float(wall_time_s - event["start_time_s"])
        event["outcome"] = outcome
        self.hold_events.append(event)
        self._active_hold_event = None

    def _enter_hold(
        self,
        wall_time_s: float,
        reason: str,
        proposed_command: dict[str, Any],
        evaluate_command: Callable[[np.ndarray, CuffPoseReference], dict[str, Any]],
    ) -> dict[str, Any]:
        phase, _, _ = self._clock_state(wall_time_s)
        self._hold_phase_s = phase
        self._hold_started_s = float(wall_time_s)
        self._settled_since_s = None
        self._normal_feasible_since_s = None
        self._reanchor(
            wall_time_s, phase_s=phase, alpha=0.0, target_alpha=0.0
        )
        self.recovery_attempt_count += 1
        self.rejected_proposal_count += 1
        proposed_force = self._total_force_n(proposed_command)
        if np.isfinite(proposed_force):
            self.maximum_rejected_force_n = max(
                self.maximum_rejected_force_n, proposed_force
            )
        if reason == "cem_no_force_feasible_action":
            self.rejected_no_feasible_cem_count += 1
        if self.recovery_attempt_count > self.config.maximum_recovery_attempts:
            return self._terminate(wall_time_s, "force_recovery_retry_limit")
        self._active_hold_event = {
            "start_time_s": float(wall_time_s),
            "frozen_phase_s": phase,
            "entry_reason": reason,
            "rejected_proposed_force_n": proposed_force,
        }
        self._transition(HOLD, wall_time_s, reason)
        safe = self._safest_hold_command(evaluate_command)
        if safe is None:
            return self._terminate(wall_time_s, "hold_command_force_infeasible")
        self.fallback_action_count += 1
        self._last_safe_action = np.asarray(safe["action"], dtype=float).copy()
        return safe

    def _settled(
        self,
        wall_time_s: float,
        estimated_state: np.ndarray,
        hold_command: dict[str, Any],
    ) -> bool:
        reference = self._hold_reference()
        q_error_deg = float(
            np.linalg.norm(np.degrees(estimated_state[:2] - reference.q_rad))
        )
        dq_error_deg_s = float(np.linalg.norm(np.degrees(estimated_state[2:])))
        force_n = self._total_force_n(hold_command)
        within = bool(
            q_error_deg <= self.config.settle_q_error_norm_deg
            and dq_error_deg_s <= self.config.settle_dq_error_norm_deg_s
            and force_n <= self.config.hold_force_limit_n + 1.0e-9
        )
        if not within:
            self._settled_since_s = None
            return False
        if self._settled_since_s is None:
            self._settled_since_s = float(wall_time_s)
            return False
        return bool(
            wall_time_s - self._settled_since_s
            >= self.config.settle_dwell_s - 1.0e-12
        )

    def _scan_maximum_safe_alpha(
        self,
        wall_time_s: float,
        phase_s: float,
        action: np.ndarray,
        evaluate_command: Callable[[np.ndarray, CuffPoseReference], dict[str, Any]],
    ) -> tuple[float | None, dict[str, Any]]:
        started = perf_counter()
        cache: dict[float, dict[str, Any]] = {}

        def evaluate(alpha: float) -> dict[str, Any]:
            key = float(alpha)
            if key not in cache:
                reference = self._reference_at(phase_s, key, 0.0)
                cache[key] = evaluate_command(action, reference)
            return cache[key]

        zero = evaluate(0.0)
        one = evaluate(1.0)
        if not self._is_safe(zero):
            maximum_safe = None
        elif self._is_safe(one):
            maximum_safe = 1.0
        else:
            grid = np.linspace(
                0.0, 1.0, self.config.alpha_search_coarse_intervals + 1
            )
            safe_flags = [self._is_safe(evaluate(float(alpha))) for alpha in grid]
            safe_indices = [index for index, safe in enumerate(safe_flags) if safe]
            if not safe_indices:
                maximum_safe = None
            else:
                safe_index = max(safe_indices)
                if safe_index == len(grid) - 1:
                    maximum_safe = 1.0
                else:
                    lower = float(grid[safe_index])
                    upper = float(grid[safe_index + 1])
                    if safe_flags[safe_index + 1]:
                        maximum_safe = upper
                    else:
                        while upper - lower > self.config.alpha_search_tolerance:
                            midpoint = 0.5 * (lower + upper)
                            if self._is_safe(evaluate(midpoint)):
                                lower = midpoint
                            else:
                                upper = midpoint
                        maximum_safe = lower
        latency_ms = 1000.0 * (perf_counter() - started)
        self.scan_latency_ms.append(latency_ms)
        forces = {
            f"{alpha:.6f}": self._total_force_n(command)
            for alpha, command in sorted(cache.items())
        }
        finite_forces = [force for force in forces.values() if np.isfinite(force)]
        self._last_scan_peak_n = max(finite_forces) if finite_forces else float("inf")
        self._last_scan_maximum_safe_alpha = maximum_safe
        record = {
            "wall_time_s": float(wall_time_s),
            "path_phase_s": float(phase_s),
            "maximum_safe_alpha": maximum_safe,
            "alpha_zero_force_n": self._total_force_n(zero),
            "alpha_one_force_n": self._total_force_n(one),
            "evaluated_force_n": forces,
            "latency_ms": latency_ms,
        }
        self.scan_records.append(record)
        return maximum_safe, record

    def _begin_recovery(
        self, wall_time_s: float, maximum_safe_alpha: float
    ) -> None:
        if self._hold_phase_s is None:
            raise RuntimeError("recovery requires a frozen phase")
        if self._recovery_classification is None:
            self._recovery_classification = (
                "TRANSIENT"
                if maximum_safe_alpha >= 1.0 - self.config.alpha_search_tolerance
                else "SPEED-RECOVERABLE"
            )
        self._reanchor(
            wall_time_s,
            phase_s=self._hold_phase_s,
            alpha=0.0,
            target_alpha=maximum_safe_alpha,
        )
        self._transition(
            RECOVER,
            wall_time_s,
            f"maximum_safe_alpha={maximum_safe_alpha:.6f}",
        )
        self._close_hold_event(wall_time_s, "recovery_started")
        self._normal_feasible_since_s = None

    def _synchronize_executed_action(self, command: dict[str, Any], mpc: Any) -> None:
        action = np.asarray(command["action"], dtype=float)
        self._last_safe_action = action.copy()
        if hasattr(mpc, "last_action"):
            mpc.last_action = action.copy()

    def filter_executable_command(
        self,
        *,
        wall_time_s: float,
        estimated_state: np.ndarray,
        proposed_command: dict[str, Any],
        mpc_diagnostics: dict[str, Any] | None,
        mpc: Any,
        evaluate_command: Callable[[np.ndarray, CuffPoseReference], dict[str, Any]],
    ) -> dict[str, Any]:
        started = perf_counter()
        now = float(wall_time_s)
        high_level_update = mpc_diagnostics is not None
        cem_accepted = bool(
            mpc_diagnostics is None or mpc_diagnostics.get("accepted", False)
        )

        if self.mode == TERMINATE:
            result = {"terminate_reason": self._termination_reason or "force_recovery_terminated"}
        elif self.mode == NORMAL:
            if not cem_accepted:
                result = self._enter_hold(
                    now,
                    "cem_no_force_feasible_action",
                    proposed_command,
                    evaluate_command,
                )
            elif not self._is_safe(proposed_command):
                result = self._enter_hold(
                    now,
                    "proposed_executable_force_over_200n",
                    proposed_command,
                    evaluate_command,
                )
            else:
                self._synchronize_executed_action(proposed_command, mpc)
                result = proposed_command
        elif self.mode in {HOLD, RECOVERY_SCAN}:
            if self._hold_started_s is None:
                raise RuntimeError("HOLD mode has no start time")
            hold_command = self._safest_hold_command(
                evaluate_command,
                include_proposed=proposed_command if cem_accepted else None,
            )
            if hold_command is None:
                result = self._terminate(now, "hold_command_force_infeasible")
            elif now - self._hold_started_s > self.config.maximum_hold_duration_s:
                result = self._terminate(now, "force_recovery_hold_timeout")
            else:
                self._synchronize_executed_action(hold_command, mpc)
                if self.mode == HOLD and self._settled(
                    now, estimated_state, hold_command
                ):
                    self._transition(
                        RECOVERY_SCAN, now, "common_settle_criterion_satisfied"
                    )
                if self.mode == RECOVERY_SCAN and high_level_update and cem_accepted:
                    maximum_safe, _ = self._scan_maximum_safe_alpha(
                        now,
                        float(self._hold_phase_s),
                        np.asarray(hold_command["action"], dtype=float),
                        evaluate_command,
                    )
                    if maximum_safe is None:
                        result = self._terminate(
                            now, "alpha_zero_executable_force_infeasible"
                        )
                    elif maximum_safe <= self.config.alpha_search_tolerance:
                        result = self._terminate(
                            now, "no_positive_recoverable_speed"
                        )
                    else:
                        self._begin_recovery(now, maximum_safe)
                        result = hold_command
                else:
                    result = hold_command
        elif self.mode == RECOVER:
            if not cem_accepted or not self._is_safe(proposed_command):
                reason = (
                    "cem_no_force_feasible_action"
                    if not cem_accepted
                    else "recovery_proposed_force_over_200n"
                )
                result = self._enter_hold(
                    now, reason, proposed_command, evaluate_command
                )
            else:
                phase, alpha, alpha_rate = self._clock_state(now)
                if high_level_update:
                    maximum_safe, _ = self._scan_maximum_safe_alpha(
                        now,
                        phase,
                        np.asarray(proposed_command["action"], dtype=float),
                        evaluate_command,
                    )
                    if maximum_safe is None or maximum_safe + 1.0e-9 < alpha:
                        result = self._enter_hold(
                            now,
                            "recovery_scan_below_current_speed",
                            proposed_command,
                            evaluate_command,
                        )
                    else:
                        self._reanchor(
                            now,
                            phase_s=phase,
                            alpha=alpha,
                            target_alpha=maximum_safe,
                        )
                        if (
                            maximum_safe
                            >= 1.0 - self.config.alpha_search_tolerance
                            and alpha >= 1.0 - self.config.alpha_search_tolerance
                        ):
                            if self._normal_feasible_since_s is None:
                                self._normal_feasible_since_s = now
                            elif (
                                now - self._normal_feasible_since_s
                                >= self.config.recovery_normal_dwell_s - 1.0e-12
                            ):
                                self._reanchor(
                                    now,
                                    phase_s=phase,
                                    alpha=1.0,
                                    target_alpha=1.0,
                                )
                                self._transition(
                                    NORMAL,
                                    now,
                                    "alpha_one_remained_executable",
                                )
                        else:
                            self._normal_feasible_since_s = None
                        self._synchronize_executed_action(proposed_command, mpc)
                        result = proposed_command
                else:
                    self._synchronize_executed_action(proposed_command, mpc)
                    result = proposed_command
        else:
            raise RuntimeError(f"unknown recovery mode {self.mode}")

        if "action" in result:
            self._synchronize_executed_action(result, mpc)
        self.filter_latency_ms.append(1000.0 * (perf_counter() - started))
        return result

    def status(self, wall_time_s: float) -> dict[str, float]:
        phase, alpha, alpha_rate = self._clock_state(wall_time_s)
        return {
            "reference_phase_time_s": phase,
            "speed_scale": alpha,
            "speed_scale_rate_per_s": alpha_rate,
            "force_speed_scale": alpha,
            "force_speed_target_scale": self._target_alpha,
            "governor_predicted_peak_command_force_n": self._last_scan_peak_n,
            "force_recovery_mode_code": MODE_CODE[self.mode],
            "force_recovery_hold_active": float(
                self.mode in {HOLD, RECOVERY_SCAN}
            ),
            "geometry_confidence": 0.0,
            "dynamic_confidence": 0.0,
            "combined_confidence": 0.0,
            "geometry_model_confidence": 0.0,
            "dynamic_model_confidence": 0.0,
            "combined_model_confidence_raw": 0.0,
            "filtered_model_confidence": 0.0,
            "execution_confidence_high": 0.0,
            "geometry_information_confidence": 0.0,
            "dynamic_information_confidence": 0.0,
            "combined_information_confidence": 0.0,
        }

    @staticmethod
    def _latency_summary(values: list[float]) -> dict[str, float | int]:
        array = np.asarray(values, dtype=float)
        if not len(array):
            return {"count": 0, "mean_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
        return {
            "count": int(len(array)),
            "mean_ms": float(np.mean(array)),
            "p95_ms": float(np.percentile(array, 95.0)),
            "max_ms": float(np.max(array)),
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": "stage4_force_feasibility_recovery",
            "state": self.mode,
            "config": self.config.as_dict(),
            "final_status": self.status(wall_time_s),
            "recovery_classification": self._recovery_classification,
            "termination_reason": self._termination_reason,
            "recovery_attempt_count": self.recovery_attempt_count,
            "rejected_proposal_count": self.rejected_proposal_count,
            "rejected_no_feasible_cem_count": self.rejected_no_feasible_cem_count,
            "maximum_rejected_force_n": self.maximum_rejected_force_n,
            "fallback_action_count": self.fallback_action_count,
            "hold_events": self.hold_events,
            "transitions": self.transitions,
            "recovery_scans": self.scan_records,
            "filter_latency": self._latency_summary(self.filter_latency_ms),
            "recovery_scan_latency": self._latency_summary(self.scan_latency_ms),
            "last_maximum_safe_alpha": self._last_scan_maximum_safe_alpha,
            "normal_mode_mpc_solves_per_cycle": 1,
            "additional_mpc_solves_per_alpha": 0,
            "runtime_force_gate_modified": False,
            "mpc_cem_trust_allocator_prior_modified": False,
        }
