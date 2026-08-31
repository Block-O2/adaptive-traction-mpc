"""Small frozen Fixed-vs-Trusted-Adaptive High-ROM engineering pilot.

Only the explicit Human V2 ROM envelope is changed.  Controller, MPC,
allocator, trust, sensor, and low-level execution settings remain frozen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff, quintic_progress

from .high_rom_human_v2 import (
    HIGH_ROM_ENDPOINTS_DEG,
    HIGH_ROM_HUMAN_V2,
    PRIMARY_ENDPOINT_NAMES,
    high_rom_config_payload,
)
from .measurement import MeasurementCase
from .mpc import HumanMPCConfig, HumanSpaceMPC
from .online_trust import OnlineSingleChallengerTrustEstimator
from .reference import TeachingWaypoint
from .sensor_realism import run_sensor_realism_case


PILOT_DURATION_S = 23.0
OUTBOUND_START_S = 1.0
TARGET_REACHED_S = 13.0
RETURN_START_S = 14.5
RETURN_REACHED_S = 22.0
INITIAL_Q_DEG = np.array([5.0, 10.0])


@dataclass(frozen=True)
class HighROMPilotTrajectory:
    name: str
    endpoint_deg: tuple[float, float]

    @property
    def waypoints(self) -> tuple[TeachingWaypoint, ...]:
        start = tuple(float(value) for value in INITIAL_Q_DEG)
        target = tuple(float(value) for value in self.endpoint_deg)
        return (
            TeachingWaypoint(0.0, start, "initial_hold_start"),
            TeachingWaypoint(OUTBOUND_START_S, start, "outbound_start"),
            TeachingWaypoint(TARGET_REACHED_S, target, "target_hold_start"),
            TeachingWaypoint(RETURN_START_S, target, "return_start"),
            TeachingWaypoint(RETURN_REACHED_S, start, "final_hold_start"),
            TeachingWaypoint(PILOT_DURATION_S, start, "final_hold_end"),
        )

    def reference(self, time_s: float) -> CuffPoseReference:
        time = float(np.clip(time_s, 0.0, PILOT_DURATION_S))
        q0 = np.radians(INITIAL_Q_DEG)
        target = np.radians(np.asarray(self.endpoint_deg, dtype=float))
        delta = target - q0
        if time <= OUTBOUND_START_S:
            q, dq, ddq = q0, np.zeros(2), np.zeros(2)
        elif time < TARGET_REACHED_S:
            duration = TARGET_REACHED_S - OUTBOUND_START_S
            progress, velocity, acceleration = quintic_progress(
                (time - OUTBOUND_START_S) / duration
            )
            q = q0 + delta * progress
            dq = delta * velocity / duration
            ddq = delta * acceleration / duration**2
        elif time <= RETURN_START_S:
            q, dq, ddq = target, np.zeros(2), np.zeros(2)
        elif time < RETURN_REACHED_S:
            duration = RETURN_REACHED_S - RETURN_START_S
            progress, velocity, acceleration = quintic_progress(
                (time - RETURN_START_S) / duration
            )
            q = target - delta * progress
            dq = -delta * velocity / duration
            ddq = -delta * acceleration / duration**2
        else:
            q, dq, ddq = q0, np.zeros(2), np.zeros(2)
        return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))

    def batched_path_kinematics(
        self, time_s: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorized equivalent of ``reference`` for joint CEM evaluation."""

        time = np.clip(np.asarray(time_s, dtype=float), 0.0, PILOT_DURATION_S)
        q0 = np.radians(INITIAL_Q_DEG)
        target = np.radians(np.asarray(self.endpoint_deg, dtype=float))
        delta = target - q0
        q = np.broadcast_to(q0, time.shape + (2,)).copy()
        dq = np.zeros_like(q)
        ddq = np.zeros_like(q)

        outbound = (time > OUTBOUND_START_S) & (time < TARGET_REACHED_S)
        outbound_duration = TARGET_REACHED_S - OUTBOUND_START_S
        x = np.clip((time - OUTBOUND_START_S) / outbound_duration, 0.0, 1.0)
        progress = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
        velocity = 30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4
        acceleration = 60.0 * x - 180.0 * x**2 + 120.0 * x**3
        q[outbound] = q0 + progress[outbound, None] * delta
        dq[outbound] = velocity[outbound, None] * delta / outbound_duration
        ddq[outbound] = (
            acceleration[outbound, None] * delta / outbound_duration**2
        )

        target_hold = (time >= TARGET_REACHED_S) & (time <= RETURN_START_S)
        q[target_hold] = target
        returning = (time > RETURN_START_S) & (time < RETURN_REACHED_S)
        return_duration = RETURN_REACHED_S - RETURN_START_S
        x = np.clip((time - RETURN_START_S) / return_duration, 0.0, 1.0)
        progress = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
        velocity = 30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4
        acceleration = 60.0 * x - 180.0 * x**2 + 120.0 * x**3
        q[returning] = target - progress[returning, None] * delta
        dq[returning] = -velocity[returning, None] * delta / return_duration
        ddq[returning] = (
            -acceleration[returning, None] * delta / return_duration**2
        )
        return q, dq, ddq


def pilot_trajectories() -> tuple[HighROMPilotTrajectory, ...]:
    return tuple(
        HighROMPilotTrajectory(
            name,
            tuple(float(value) for value in HIGH_ROM_ENDPOINTS_DEG[name]),
        )
        for name in PRIMARY_ENDPOINT_NAMES
    )


def _acceleration_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    q_deg = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    if len(time) < 3:
        acceleration = np.zeros_like(q_deg)
    else:
        velocity = np.gradient(q_deg, time, axis=0, edge_order=2)
        acceleration = np.gradient(velocity, time, axis=0, edge_order=2)
    return {
        "per_joint_deg_s2": np.sqrt(np.mean(acceleration**2, axis=0)).tolist(),
        "combined_deg_s2": float(np.sqrt(np.mean(acceleration**2))),
    }


def compact_run_metrics(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    *,
    controller_id: str,
    trajectory: HighROMPilotTrajectory,
) -> dict[str, Any]:
    q_deg = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    time = np.asarray(trace["time_s"], dtype=float)
    control_q = np.asarray(trace["control_true_q_rad_god_view"], dtype=float)
    control_dq = np.asarray(trace["control_true_dq_rad_s_god_view"], dtype=float)
    soft_active = np.array(
        [
            np.linalg.norm(soft_limit_torque(q, dq, HIGH_ROM_HUMAN_V2)) > 1e-8
            for q, dq in zip(control_q, control_dq, strict=True)
        ],
        dtype=bool,
    )
    lower_start = (
        np.asarray(HIGH_ROM_HUMAN_V2.q_min_rad)
        + HIGH_ROM_HUMAN_V2.soft_limit_margin_rad
        - HIGH_ROM_HUMAN_V2.soft_limit_numerical_tolerance_rad
    )
    upper_start = (
        np.asarray(HIGH_ROM_HUMAN_V2.q_max_rad)
        - HIGH_ROM_HUMAN_V2.soft_limit_margin_rad
        + HIGH_ROM_HUMAN_V2.soft_limit_numerical_tolerance_rad
    )
    lower_active = np.any(control_q < lower_start, axis=1)
    upper_active = np.any(control_q > upper_start, axis=1)
    trust = summary.get("hierarchical_trust", {})
    promotions = trust.get("control_promotions", [])
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    return {
        "trajectory": trajectory.name,
        "endpoint_deg": list(trajectory.endpoint_deg),
        "controller": controller_id,
        "completion": bool(summary["mechanically_completed_requested_duration"]),
        "termination_reason": summary["termination_reason"],
        "completed_duration_s": float(summary["completed_duration_s"]),
        "tracking_rmse_deg": summary["tracking"]["rmse_deg"],
        "tracking_combined_rmse_deg": float(
            summary["tracking"]["combined_rmse_deg"]
        ),
        "tracking_max_abs_error_deg": summary["tracking"]["max_abs_error_deg"],
        "peak_human_angle_deg": np.max(q_deg, axis=0).tolist(),
        "minimum_human_angle_deg": np.min(q_deg, axis=0).tolist(),
        "soft_limit_activation": {
            "sample_count": int(np.sum(soft_active)),
            "entered": bool(np.any(soft_active)),
            "lower_zone_sample_count": int(np.sum(lower_active)),
            "upper_120deg_zone_sample_count": int(np.sum(upper_active)),
            "upper_120deg_zone_entered": bool(np.any(upper_active)),
            "first_time_s": (
                float(trace["control_time_s"][np.flatnonzero(soft_active)[0]])
                if np.any(soft_active)
                else None
            ),
        },
        "cuff_force_rms_n": float(
            interaction["rms_total_translational_force_n"]
        ),
        "cuff_force_peak_n": float(
            interaction["peak_total_translational_force_n"]
        ),
        "cuff_force_margin_to_200_n": float(
            200.0 - interaction["peak_total_translational_force_n"]
        ),
        "commanded_force_gate": {
            "peak_attempt_n": float(
                summary["events"]["peak_commanded_translational_force_n"]
            ),
            "minimum_margin_n": float(
                summary["events"]["minimum_commanded_force_gate_margin_n"]
            ),
            "triggered": summary["termination_reason"]
            in {
                "allocated_cuff_force_gate",
                "total_commanded_cuff_force_gate",
                "physical_cuff_force_gate",
            },
        },
        "cuff_moment_peak_nm": float(
            interaction["peak_total_cuff_moment_nm"]
        ),
        "acceleration_rms": _acceleration_metrics(trace),
        "promotion_count": len(promotions),
        "promotion_times_s": [
            float(item["promotion_time_s"]) for item in promotions
        ],
        "events": summary["events"],
        "robot": {
            "peak_unclipped_torque_limit_fraction": summary["robot"][
                "peak_unclipped_torque_limit_fraction"
            ],
            "torque_saturation_control_samples": summary["robot"][
                "torque_saturation_control_samples"
            ],
            "joint_position_limit_samples": summary["robot"][
                "joint_position_limit_samples"
            ],
        },
        "bed_contact": {
            "peak_bed_force_n_god_view": float(
                np.max(np.asarray(trace["bed_force_n_god_view"], dtype=float))
            ),
            "recorded_not_a_pilot_rejection_criterion": True,
        },
        "rollout_wall_time_s": summary["computational_cost"][
            "rollout_wall_time_s"
        ],
        "mpc_mean_ms": summary["computational_cost"]["mpc_mean_ms"],
        "trace_sample_count": len(time),
    }


def run_small_pilot(
    measurement_case: MeasurementCase,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    controllers = (
        ("fixed_mpc_prior_only", False),
        ("trusted_adaptive_mpc", True),
    )
    for trajectory in pilot_trajectories():
        for controller_id, apply_model in controllers:
            def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
                return OnlineSingleChallengerTrustEstimator(
                    measurement,
                    q_prior,
                    measurement_case=measurement_case,
                    apply_qualified_model=apply_model,
                    rom_human=HIGH_ROM_HUMAN_V2,
                )

            summary, trace = run_sensor_realism_case(
                measurement_case,
                duration_s=PILOT_DURATION_S,
                estimator_architecture="integral_minimal",
                result_case_name=f"{trajectory.name}__{controller_id}",
                true_human_override=HIGH_ROM_HUMAN_V2,
                true_metadata_override={
                    "case": "nominal_high_rom_human_v2_engineering_v2",
                    "canonical_human_overwritten": False,
                    "engineering_assumption": True,
                },
                reference_fn=trajectory.reference,
                trajectory_label=trajectory.name,
                trajectory_waypoints=trajectory.waypoints,
                mpc_factory=lambda: HumanSpaceMPC(),
                estimator_factory=estimator_factory,
            )
            runs.append(
                compact_run_metrics(
                    summary,
                    trace,
                    controller_id=controller_id,
                    trajectory=trajectory,
                )
            )

    comparisons = {}
    for trajectory in pilot_trajectories():
        by_controller = {
            item["controller"]: item
            for item in runs
            if item["trajectory"] == trajectory.name
        }
        fixed = by_controller["fixed_mpc_prior_only"]
        adaptive = by_controller["trusted_adaptive_mpc"]
        comparisons[trajectory.name] = {
            "adaptive_minus_fixed_tracking_combined_rmse_deg": (
                adaptive["tracking_combined_rmse_deg"]
                - fixed["tracking_combined_rmse_deg"]
            ),
            "adaptive_minus_fixed_peak_cuff_force_n": (
                adaptive["cuff_force_peak_n"] - fixed["cuff_force_peak_n"]
            ),
            "adaptive_improved_tracking_rmse": (
                adaptive["tracking_combined_rmse_deg"]
                < fixed["tracking_combined_rmse_deg"]
            ),
        }
    return {
        "schema_version": "high_rom_fixed_vs_trusted_adaptive_small_pilot_v1",
        "evidence_category": "small_engineering_pilot_not_formal_benchmark",
        "run_count": len(runs),
        "design": "3 trajectories x 2 frozen MPC controllers x 1 measurement seed",
        "high_rom_variant": high_rom_config_payload(),
        "measurement_case": asdict(measurement_case),
        "frozen_mpc_config": asdict(HumanMPCConfig()),
        "frozen_settings_changed": False,
        "patient_mismatch_added": False,
        "multiple_seeds_run": False,
        "soft_limit_question": (
            "upper 120 deg soft-zone entry is reported separately from the "
            "lower-zone startup transient"
        ),
        "dynamic_bed_contact_is_setup_specific_diagnostic": True,
        "trajectory_profile": {
            "family": "quintic outbound, target hold, quintic return, final hold",
            "duration_s": PILOT_DURATION_S,
            "outbound_start_s": OUTBOUND_START_S,
            "target_reached_s": TARGET_REACHED_S,
            "return_start_s": RETURN_START_S,
            "return_reached_s": RETURN_REACHED_S,
        },
        "runs": runs,
        "paired_comparisons": comparisons,
    }
