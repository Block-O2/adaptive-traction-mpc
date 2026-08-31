"""Predictive outer-loop reference pacing for the frozen Stage-4 controller.

This engineering governor changes only the reference clock.  It does not alter
the MPC objective, estimator/trust lifecycle, cuff allocator, or the retained
200 N low-level translational-force gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference


@dataclass(frozen=True)
class PredictiveSpeedGovernorConfig:
    """Trajectory-independent engineering settings for reference pacing."""

    candidate_speed_scales: tuple[float, ...] = (
        1.0,
        0.9,
        0.8,
        0.7,
        0.6,
        0.5,
    )
    planning_force_limit_n: float = 195.0
    slowdown_rate_per_s: float = 1.0
    recovery_rate_per_s: float = 0.25
    cartesian_kp_n_m: float = 3000.0
    cartesian_kd_ns_m: float = 140.0
    feedback_component_clip_n: float = 200.0

    def __post_init__(self) -> None:
        candidates = np.asarray(self.candidate_speed_scales, dtype=float)
        if len(candidates) == 0 or not np.all(np.isfinite(candidates)):
            raise ValueError("candidate speed scales must be finite and nonempty")
        if np.any(candidates <= 0.0) or np.any(candidates > 1.0):
            raise ValueError("candidate speed scales must lie in (0, 1]")
        if np.any(np.diff(candidates) >= 0.0):
            raise ValueError("candidate speed scales must be strictly descending")
        if not 0.0 < self.planning_force_limit_n < CUFF_TRANSLATIONAL_FORCE_GATE_N:
            raise ValueError("planning force limit must lie strictly inside hard gate")
        if self.slowdown_rate_per_s <= 0.0 or self.recovery_rate_per_s <= 0.0:
            raise ValueError("speed-scale rates must be positive")

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "hard_force_gate_n_unchanged": CUFF_TRANSLATIONAL_FORCE_GATE_N,
                "planning_margin_n": (
                    CUFF_TRANSLATIONAL_FORCE_GATE_N - self.planning_force_limit_n
                ),
                "minimum_scale_source": (
                    "existing Stage-4 confidence-execution minimum of 0.50"
                ),
                "planning_margin_rationale": (
                    "small engineering allowance for model and measured cuff-state "
                    "error before the unchanged hard gate; not a new safety limit"
                ),
            }
        )
        return payload


class PredictiveSpeedGovernor:
    """Choose the fastest predicted-safe time-warp rate at each MPC update."""

    def __init__(
        self,
        base_reference: Callable[[float], CuffPoseReference],
        *,
        config: PredictiveSpeedGovernorConfig = PredictiveSpeedGovernorConfig(),
        initial_wall_time_s: float = 0.0,
    ) -> None:
        self.base_reference = base_reference
        self.config = config
        self.wall_anchor_s = float(initial_wall_time_s)
        self.phase_anchor_s = 0.0
        self.speed_anchor_scale = 1.0
        self.speed_target_scale = 1.0
        self.speed_scale_rate_per_s = 0.0
        self.predicted_peak_command_force_n = 0.0
        self.prediction_update_count = 0
        self.slowdown_selection_count = 0
        self.no_safe_candidate_count = 0
        self.minimum_selected_target_scale = 1.0
        self.maximum_predicted_peak_command_force_n = 0.0
        self.last_candidate_predictions_n: dict[str, float] = {}

    @property
    def mode(self) -> str:
        return "predictive_force_speed_governor"

    def _clock_state(self, wall_time_s: float) -> tuple[float, float, float]:
        wall_time = float(wall_time_s)
        if wall_time < self.wall_anchor_s - 1e-12:
            raise ValueError("reference execution time must be monotonic")
        elapsed = max(0.0, wall_time - self.wall_anchor_s)
        speed_0 = self.speed_anchor_scale
        target = self.speed_target_scale
        rate = self.speed_scale_rate_per_s
        if abs(rate) <= 1e-15:
            return self.phase_anchor_s + speed_0 * elapsed, speed_0, 0.0
        ramp_duration = (target - speed_0) / rate
        if ramp_duration <= 1e-15:
            return self.phase_anchor_s + target * elapsed, target, 0.0
        ramp_elapsed = min(elapsed, ramp_duration)
        phase = self.phase_anchor_s + speed_0 * ramp_elapsed + 0.5 * rate * ramp_elapsed**2
        if elapsed < ramp_duration - 1e-12:
            return phase, float(speed_0 + rate * elapsed), float(rate)
        phase += target * (elapsed - ramp_duration)
        return phase, float(target), 0.0

    def phase_time_s(self, wall_time_s: float) -> float:
        return self._clock_state(wall_time_s)[0]

    def _set_speed_target(self, wall_time_s: float, target: float) -> None:
        phase_now, speed_now, _ = self._clock_state(wall_time_s)
        clipped = float(np.clip(target, 0.0, 1.0))
        if clipped > speed_now + 1e-15:
            rate = self.config.recovery_rate_per_s
        elif clipped < speed_now - 1e-15:
            rate = -self.config.slowdown_rate_per_s
        else:
            rate = 0.0
        self.phase_anchor_s = phase_now
        self.wall_anchor_s = float(wall_time_s)
        self.speed_anchor_scale = float(speed_now)
        self.speed_target_scale = clipped
        self.speed_scale_rate_per_s = float(rate)

    def _candidate_reference(
        self, wall_time_s: float, target: float
    ) -> Callable[[float], CuffPoseReference]:
        phase_now, speed_now, _ = self._clock_state(wall_time_s)
        rate = (
            self.config.recovery_rate_per_s
            if target > speed_now + 1e-15
            else -self.config.slowdown_rate_per_s
            if target < speed_now - 1e-15
            else 0.0
        )

        def candidate_reference(future_wall_time_s: float) -> CuffPoseReference:
            elapsed = max(0.0, float(future_wall_time_s) - float(wall_time_s))
            if abs(rate) <= 1e-15:
                phase = phase_now + speed_now * elapsed
                speed = speed_now
                speed_rate = 0.0
            else:
                ramp_duration = (target - speed_now) / rate
                ramp_elapsed = min(elapsed, max(0.0, ramp_duration))
                phase = phase_now + speed_now * ramp_elapsed + 0.5 * rate * ramp_elapsed**2
                if elapsed < ramp_duration - 1e-12:
                    speed = speed_now + rate * elapsed
                    speed_rate = rate
                else:
                    phase += target * (elapsed - ramp_duration)
                    speed = target
                    speed_rate = 0.0
            base = self.base_reference(phase)
            return CuffPoseReference(
                q_rad=base.q_rad.copy(),
                dq_rad_s=speed * base.dq_rad_s,
                ddq_rad_s2=speed**2 * base.ddq_rad_s2 + speed_rate * base.dq_rad_s,
                world_from_cuff=base.world_from_cuff,
            )

        return candidate_reference

    def _predict_peak_command_force(
        self,
        wall_time_s: float,
        target: float,
        state: np.ndarray,
        human: Any,
        mpc: Any,
        cuff_allocator: Any,
    ) -> float:
        reference_fn = self._candidate_reference(wall_time_s, target)
        q_ref, dq_ref, ddq_ref = mpc._reference_arrays(wall_time_s, reference_fn)
        sequence = mpc._seed_sequence(state, q_ref, dq_ref, ddq_ref, human)
        predicted = mpc._rollout(state, sequence, human)[1:]
        peaks: list[float] = []
        for action, predicted_state, reference in zip(
            sequence,
            predicted,
            [
                reference_fn(
                    wall_time_s + (index + 1) * mpc.config.prediction_dt_s
                )
                for index in range(mpc.config.horizon_steps)
            ],
            strict=True,
        ):
            predicted_pose = human.geometry.cuff_pose(predicted_state[:2])
            predicted_velocity, _ = human.geometry.cuff_velocity(
                predicted_state[:2], predicted_state[2:]
            )
            target_pose = human.geometry.cuff_pose(reference.q_rad)
            target_velocity, _ = human.geometry.cuff_velocity(
                reference.q_rad, reference.dq_rad_s
            )
            feedback = self.config.cartesian_kp_n_m * (
                target_pose.translation - predicted_pose.translation
            )
            feedback += self.config.cartesian_kd_ns_m * (
                target_velocity - predicted_velocity
            )
            feedback = np.clip(
                feedback,
                -self.config.feedback_component_clip_n,
                self.config.feedback_component_clip_n,
            )
            allocation = cuff_allocator.allocate(action, predicted_state[:2], human)
            total = feedback + np.asarray(allocation["wrench_world"], dtype=float)[:3]
            peaks.append(float(np.linalg.norm(total)))
        return max(peaks) if peaks else 0.0

    def update_from_prediction(
        self,
        wall_time_s: float,
        state: np.ndarray,
        current_model: Any,
        mpc: Any,
        cuff_allocator: Any,
    ) -> None:
        predictions: dict[str, float] = {}
        selected: float | None = None
        selected_peak = float("inf")
        for candidate in self.config.candidate_speed_scales:
            try:
                peak = self._predict_peak_command_force(
                    wall_time_s,
                    candidate,
                    np.asarray(state, dtype=float),
                    current_model,
                    mpc,
                    cuff_allocator,
                )
            except (FloatingPointError, RuntimeError, ValueError, np.linalg.LinAlgError):
                peak = float("inf")
            predictions[f"{candidate:.1f}"] = peak
            if selected is None and np.isfinite(peak) and peak <= self.config.planning_force_limit_n:
                selected = float(candidate)
                selected_peak = float(peak)
        if selected is None:
            selected = float(self.config.candidate_speed_scales[-1])
            selected_peak = predictions[f"{selected:.1f}"]
            self.no_safe_candidate_count += 1
        self._set_speed_target(wall_time_s, selected)
        self.predicted_peak_command_force_n = selected_peak
        self.prediction_update_count += 1
        self.slowdown_selection_count += int(selected < 1.0 - 1e-12)
        self.minimum_selected_target_scale = min(
            self.minimum_selected_target_scale, selected
        )
        if np.isfinite(selected_peak):
            self.maximum_predicted_peak_command_force_n = max(
                self.maximum_predicted_peak_command_force_n, selected_peak
            )
        self.last_candidate_predictions_n = predictions

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        phase, speed, speed_rate = self._clock_state(wall_time_s)
        base = self.base_reference(phase)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=speed * base.dq_rad_s,
            ddq_rad_s2=speed**2 * base.ddq_rad_s2 + speed_rate * base.dq_rad_s,
            world_from_cuff=base.world_from_cuff,
        )

    def status(self, wall_time_s: float) -> dict[str, float]:
        phase, speed, speed_rate = self._clock_state(wall_time_s)
        return {
            "reference_phase_time_s": phase,
            "speed_scale": speed,
            "speed_scale_rate_per_s": speed_rate,
            "force_speed_scale": speed,
            "force_speed_target_scale": self.speed_target_scale,
            "governor_predicted_peak_command_force_n": (
                self.predicted_peak_command_force_n
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

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": self.config.as_dict(),
            "final_status": self.status(wall_time_s),
            "prediction_update_count": self.prediction_update_count,
            "slowdown_selection_count": self.slowdown_selection_count,
            "no_safe_candidate_count": self.no_safe_candidate_count,
            "minimum_selected_target_scale": self.minimum_selected_target_scale,
            "maximum_selected_prediction_n": (
                self.maximum_predicted_peak_command_force_n
            ),
            "last_candidate_predictions_n": self.last_candidate_predictions_n,
            "selection_rule": "largest candidate with predicted total force <= planning limit",
            "predicted_command": (
                "existing Cartesian feedback plus unchanged allocator feedforward"
            ),
            "time_warp_kinematics": (
                "qdot=q_prime*alpha; qddot=q_double_prime*alpha^2+q_prime*alpha_dot"
            ),
            "trust_confidence_used": False,
            "mpc_modified": False,
            "allocator_modified": False,
            "hard_force_gate_modified": False,
        }
