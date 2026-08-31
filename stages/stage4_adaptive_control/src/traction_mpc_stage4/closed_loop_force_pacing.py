"""Final-selected-action command-force predictor for High-ROM pacing audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference

from .high_rom_dynamic_pilot import PILOT_DURATION_S, HighROMPilotTrajectory


@dataclass(frozen=True)
class ClosedLoopForcePacingConfig:
    alpha_minimum: float = 0.50
    alpha_maximum: float = 1.00
    alpha_audit_samples: int = 101
    low_level_dt_s: float = 0.005
    slowdown_rate_per_s: float = 1.0
    recovery_rate_per_s: float = 0.25
    cartesian_kp_n_m: float = 3000.0
    cartesian_kd_ns_m: float = 140.0
    feedback_component_clip_n: float = 200.0

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha_minimum < self.alpha_maximum <= 1.0:
            raise ValueError("alpha bounds must satisfy 0 < min < max <= 1")
        if self.alpha_audit_samples < 11:
            raise ValueError("alpha audit requires at least 11 samples")
        if self.low_level_dt_s <= 0.0:
            raise ValueError("low-level time step must be positive")
        if self.slowdown_rate_per_s <= 0.0 or self.recovery_rate_per_s <= 0.0:
            raise ValueError("alpha rate limits must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _position_velocity(
    q_rad: np.ndarray, dq_rad_s: np.ndarray, model: Any
) -> tuple[np.ndarray, np.ndarray]:
    geometry = model.geometry
    q = np.asarray(q_rad, dtype=float)
    dq = np.asarray(dq_rad_s, dtype=float)
    q1 = q[..., 0]
    phi = q1 - q[..., 1]
    plane_x = np.asarray(geometry.plane_x_world, dtype=float)
    plane_z = np.asarray(geometry.plane_z_world, dtype=float)
    hip = np.asarray(geometry.hip_plane_m, dtype=float)
    px = (
        hip[0]
        + geometry.thigh_length_m * np.cos(q1)
        + geometry.cuff_distance_m * np.cos(phi)
    )
    pz = (
        hip[1]
        + geometry.thigh_length_m * np.sin(q1)
        + geometry.cuff_distance_m * np.sin(phi)
    )
    position = (
        np.asarray(geometry.origin_world_m, dtype=float)
        + px[..., None] * plane_x
        + pz[..., None] * plane_z
    )
    e1_perp = (
        -np.sin(q1)[..., None] * plane_x
        + np.cos(q1)[..., None] * plane_z
    )
    shank_perp = (
        -np.sin(phi)[..., None] * plane_x
        + np.cos(phi)[..., None] * plane_z
    )
    first = (
        geometry.thigh_length_m * e1_perp
        + geometry.cuff_distance_m * shank_perp
    )
    second = -geometry.cuff_distance_m * shank_perp
    velocity = first * dq[..., 0, None] + second * dq[..., 1, None]
    return position, velocity


class FinalSelectedCommandForcePredictor:
    """Evaluate final low-level force over one selected MPC sequence.

    Human states and allocated feedforward are rolled out once.  A continuous
    alpha vector changes only the future time-warped reference and the exact
    frozen Cartesian feedback path; no additional MPC/CEM solve is performed.
    """

    def __init__(
        self,
        trajectory: HighROMPilotTrajectory,
        *,
        config: ClosedLoopForcePacingConfig = ClosedLoopForcePacingConfig(),
    ) -> None:
        self.trajectory = trajectory
        self.config = config

    def _command_path(
        self,
        state: np.ndarray,
        selected_sequence: np.ndarray,
        model: Any,
        allocator: Any,
        prediction_dt_s: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sequence = np.asarray(selected_sequence, dtype=float)
        substeps = int(round(float(prediction_dt_s) / self.config.low_level_dt_s))
        if abs(substeps * self.config.low_level_dt_s - prediction_dt_s) > 1e-12:
            raise RuntimeError("MPC period must contain integer low-level substeps")
        actions = np.repeat(sequence, substeps, axis=0)
        states = np.empty((len(actions), 4), dtype=float)
        current = np.asarray(state, dtype=float).copy()
        feedforward = np.empty((len(actions), 3), dtype=float)
        for index, action in enumerate(actions):
            states[index] = current
            allocation = allocator.allocate(action, current[:2], model)
            feedforward[index] = np.asarray(
                allocation["wrench_world"], dtype=float
            )[:3]
            current = model.step_dynamics(
                current, action, self.config.low_level_dt_s
            )
        return actions, states, feedforward

    def _candidate_clock(
        self,
        phase_now_s: float,
        current_alpha: float,
        alpha_target: np.ndarray,
        offsets_s: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        target = np.asarray(alpha_target, dtype=float).reshape(-1, 1)
        offsets = np.asarray(offsets_s, dtype=float).reshape(1, -1)
        current = float(current_alpha)
        rates = np.where(
            target < current - 1e-15,
            -self.config.slowdown_rate_per_s,
            np.where(
                target > current + 1e-15,
                self.config.recovery_rate_per_s,
                0.0,
            ),
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            ramp_duration = np.where(
                np.abs(rates) > 1e-15, (target - current) / rates, 0.0
            )
        ramp_elapsed = np.minimum(offsets, np.maximum(ramp_duration, 0.0))
        phase = (
            float(phase_now_s)
            + current * ramp_elapsed
            + 0.5 * rates * ramp_elapsed**2
        )
        after = np.maximum(offsets - ramp_duration, 0.0)
        phase += np.where(offsets > ramp_duration, target * after, 0.0)
        speed = np.where(
            offsets < ramp_duration - 1e-12,
            current + rates * offsets,
            target,
        )
        phase = np.clip(phase, 0.0, PILOT_DURATION_S)
        return phase, speed, rates

    def evaluate(
        self,
        *,
        wall_time_s: float,
        phase_now_s: float,
        current_alpha: float,
        alpha_target: np.ndarray,
        state: np.ndarray,
        selected_sequence: np.ndarray,
        model: Any,
        allocator: Any,
        prediction_dt_s: float,
    ) -> dict[str, np.ndarray | float]:
        started = perf_counter()
        _, states, feedforward = self._command_path(
            state, selected_sequence, model, allocator, prediction_dt_s
        )
        offsets = self.config.low_level_dt_s * np.arange(len(states), dtype=float)
        phase, speed, _ = self._candidate_clock(
            phase_now_s, current_alpha, alpha_target, offsets
        )
        q_ref, dq_path, _ = self.trajectory.batched_path_kinematics(phase)
        dq_ref = speed[..., None] * dq_path
        target_position, target_velocity = _position_velocity(q_ref, dq_ref, model)
        predicted_position, predicted_velocity = _position_velocity(
            states[:, :2], states[:, 2:], model
        )
        feedback = self.config.cartesian_kp_n_m * (
            target_position - predicted_position[None, ...]
        )
        feedback += self.config.cartesian_kd_ns_m * (
            target_velocity - predicted_velocity[None, ...]
        )
        feedback = np.clip(
            feedback,
            -self.config.feedback_component_clip_n,
            self.config.feedback_component_clip_n,
        )
        total = feedback + feedforward[None, ...]
        force = np.linalg.norm(total, axis=-1)
        peaks = np.max(force, axis=1)
        peak_indices = np.argmax(force, axis=1)
        return {
            "alpha": np.asarray(alpha_target, dtype=float).reshape(-1),
            "peak_force_n": peaks,
            "peak_offset_s": offsets[peak_indices],
            "force_path_n": force,
            "feedforward_force_path_n": np.linalg.norm(feedforward, axis=1),
            "evaluation_latency_ms": 1000.0 * (perf_counter() - started),
            "wall_time_s": float(wall_time_s),
        }


class FixedClockForceCurveAuditor:
    """Read-only execution hook that records curves without changing reference."""

    def __init__(
        self,
        trajectory: HighROMPilotTrajectory,
        *,
        audit_start_s: float,
        audit_stop_s: float,
        audit_period_s: float = 0.10,
        config: ClosedLoopForcePacingConfig = ClosedLoopForcePacingConfig(),
    ) -> None:
        self.trajectory = trajectory
        self.audit_start_s = float(audit_start_s)
        self.audit_stop_s = float(audit_stop_s)
        self.audit_period_s = float(audit_period_s)
        self.config = config
        self.predictor = FinalSelectedCommandForcePredictor(
            trajectory, config=config
        )
        self.alpha_grid = np.linspace(
            config.alpha_minimum,
            config.alpha_maximum,
            config.alpha_audit_samples,
        )
        self.next_audit_s = self.audit_start_s
        self._context: tuple[Any, ...] | None = None
        self.records: list[dict[str, Any]] = []

    def update_from_prediction(
        self,
        wall_time_s: float,
        state: np.ndarray,
        current_model: Any,
        mpc: Any,
        cuff_allocator: Any,
    ) -> None:
        self._context = (
            float(wall_time_s),
            np.asarray(state, dtype=float).copy(),
            current_model,
            mpc,
            cuff_allocator,
        )

    def update_from_mpc_selection(
        self, wall_time_s: float, diagnostics: dict[str, Any]
    ) -> None:
        now = float(wall_time_s)
        if now + 1e-12 < self.next_audit_s or now > self.audit_stop_s + 1e-12:
            return
        if self._context is None or not diagnostics.get("accepted", False):
            self.next_audit_s += self.audit_period_s
            return
        context_time, state, model, mpc, allocator = self._context
        if abs(context_time - now) > 1e-9:
            raise RuntimeError("force audit context does not match selected MPC cycle")
        evaluation = self.predictor.evaluate(
            wall_time_s=now,
            phase_now_s=now,
            current_alpha=1.0,
            alpha_target=self.alpha_grid,
            state=state,
            selected_sequence=np.asarray(mpc.last_sequence, dtype=float),
            model=model,
            allocator=allocator,
            prediction_dt_s=float(mpc.config.prediction_dt_s),
        )
        reference = self.trajectory.reference(now)
        self.records.append(
            {
                "wall_time_s": now,
                "estimated_state": state.tolist(),
                "tracking_error_deg": np.degrees(
                    state[:2] - reference.q_rad
                ).tolist(),
                "selected_first_action_nm": np.asarray(
                    mpc.last_sequence[0], dtype=float
                ).tolist(),
                "alpha": np.asarray(evaluation["alpha"]).tolist(),
                "peak_force_n": np.asarray(evaluation["peak_force_n"]).tolist(),
                "peak_offset_s": np.asarray(evaluation["peak_offset_s"]).tolist(),
                "evaluation_latency_ms": float(
                    evaluation["evaluation_latency_ms"]
                ),
            }
        )
        while self.next_audit_s <= now + 1e-12:
            self.next_audit_s += self.audit_period_s

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        return self.trajectory.reference(wall_time_s)

    def status(self, wall_time_s: float) -> dict[str, float]:
        return {
            "reference_phase_time_s": float(wall_time_s),
            "speed_scale": 1.0,
            "speed_scale_rate_per_s": 0.0,
            "force_speed_scale": 1.0,
            "force_speed_target_scale": 1.0,
            "governor_predicted_peak_command_force_n": 0.0,
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
            "mode": "fixed_clock_final_selected_action_force_curve_audit",
            "config": self.config.as_dict(),
            "record_count": len(self.records),
            "audit_window_s": [self.audit_start_s, self.audit_stop_s],
            "audit_period_s": self.audit_period_s,
            "reference_modified": False,
            "mpc_solve_count_added": 0,
            "final_status": self.status(wall_time_s),
        }

