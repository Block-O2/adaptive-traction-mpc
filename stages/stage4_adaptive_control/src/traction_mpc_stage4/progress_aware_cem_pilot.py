"""Two-run joint-CEM pacing pilot for the blocked High-ROM trajectories."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from .high_rom_dynamic_pilot import (
    PILOT_DURATION_S,
    HighROMPilotTrajectory,
    compact_run_metrics,
    pilot_trajectories,
)
from .high_rom_human_v2 import HIGH_ROM_HUMAN_V2, high_rom_config_payload
from .measurement import MeasurementCase
from .mpc import HumanMPCConfig
from .online_trust import OnlineSingleChallengerTrustEstimator
from .progress_aware_cem import (
    ProgressAwareCEMConfig,
    ProgressAwareCEMMPC,
    ProgressAwareReferenceClock,
)
from .sensor_realism import run_sensor_realism_case


PILOT_TRAJECTORY_NAMES = (
    "hip_dominant_100_60",
    "aggressive_both_120_120",
)
MAX_WALL_TIME_S = PILOT_DURATION_S / ProgressAwareCEMConfig().minimum_alpha + 0.1


def _smoothness(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time = np.asarray(trace["control_time_s"], dtype=float)
    q_deg = np.degrees(np.asarray(trace["control_true_q_rad_god_view"], dtype=float))
    if len(time) >= 4:
        velocity = np.gradient(q_deg, time, axis=0, edge_order=2)
        acceleration = np.gradient(velocity, time, axis=0, edge_order=2)
        jerk = np.gradient(acceleration, time, axis=0, edge_order=2)
    else:
        acceleration = np.zeros_like(q_deg)
        jerk = np.zeros_like(q_deg)
    return {
        "acceleration_rms_per_joint_deg_s2": np.sqrt(
            np.mean(acceleration**2, axis=0)
        ).tolist(),
        "acceleration_combined_rms_deg_s2": float(
            np.sqrt(np.mean(acceleration**2))
        ),
        "jerk_rms_per_joint_deg_s3": np.sqrt(np.mean(jerk**2, axis=0)).tolist(),
        "jerk_combined_rms_deg_s3": float(np.sqrt(np.mean(jerk**2))),
    }


def _alpha_metrics(trace: dict[str, np.ndarray], end_time_s: float) -> dict[str, Any]:
    time = np.asarray(trace["mpc_selection_time_s"], dtype=float)
    alpha = np.asarray(trace["mpc_selected_alpha"], dtype=float)
    if not len(alpha):
        raise RuntimeError("joint CEM pilot produced no alpha selections")
    interval = np.diff(np.append(time, end_time_s))
    interval = np.maximum(interval, 0.0)
    total = max(float(np.sum(interval)), 1e-12)
    below = alpha < 1.0 - 1e-9
    weighted_mean = float(np.sum(alpha * interval) / total)
    first_slow = int(np.flatnonzero(below)[0]) if np.any(below) else None
    returned = bool(
        first_slow is not None
        and np.any(alpha[first_slow + 1 :] >= 1.0 - 1e-6)
    )
    return {
        "mean": weighted_mean,
        "minimum": float(np.min(alpha)),
        "maximum": float(np.max(alpha)),
        "time_below_one_s": float(np.sum(interval[below])),
        "fraction_time_below_one": float(np.sum(interval[below]) / total),
        "total_variation": float(np.sum(np.abs(np.diff(alpha)))),
        "maximum_step_change": float(np.max(np.abs(np.diff(alpha))))
        if len(alpha) > 1
        else 0.0,
        "first_slowing_time_s": float(time[first_slow])
        if first_slow is not None
        else None,
        "returned_to_one_after_slowing": returned,
    }


def _interaction(trace: dict[str, np.ndarray]) -> dict[str, float]:
    force = np.linalg.norm(
        np.asarray(trace["cuff_force_local_n_god_view"], dtype=float), axis=1
    )
    moment = np.linalg.norm(
        np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float), axis=1
    )
    commanded = np.asarray(trace["commanded_translational_force_norm_n"], dtype=float)
    predicted = np.asarray(
        trace["mpc_control_path_predicted_command_force_n"], dtype=float
    )
    return {
        "predicted_command_force_peak_n": float(np.max(predicted)),
        "executed_command_force_peak_n": float(np.max(commanded)),
        "executed_command_force_margin_n": float(200.0 - np.max(commanded)),
        "physical_cuff_force_rms_n": float(np.sqrt(np.mean(force**2))),
        "physical_cuff_force_p95_n": float(np.percentile(force, 95.0)),
        "physical_cuff_force_peak_n": float(np.max(force)),
        "physical_cuff_moment_rms_nm": float(np.sqrt(np.mean(moment**2))),
        "physical_cuff_moment_peak_nm": float(np.max(moment)),
    }


def _run(
    measurement_case: MeasurementCase,
    trajectory: HighROMPilotTrajectory,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    clock = ProgressAwareReferenceClock(
        trajectory.reference,
        trajectory.batched_path_kinematics,
        duration_s=PILOT_DURATION_S,
    )

    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=measurement_case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN_V2,
        )

    summary, trace = run_sensor_realism_case(
        measurement_case,
        duration_s=MAX_WALL_TIME_S,
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__fixed_mpc_joint_cem_progress",
        true_human_override=HIGH_ROM_HUMAN_V2,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_v2",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        reference_execution=clock,
        reference_completion_phase_s=PILOT_DURATION_S,
        mpc_factory=lambda: ProgressAwareCEMMPC(clock),
        estimator_factory=estimator_factory,
    )
    metrics = compact_run_metrics(
        summary,
        trace,
        controller_id="fixed_mpc_joint_cem_progress",
        trajectory=trajectory,
    )
    metrics.update(
        {
            "completion_time_s": float(summary["completed_duration_s"]),
            "completed_reference_phase_s": float(
                trace["reference_phase_time_s"][-1]
            ),
            "alpha": _alpha_metrics(trace, float(summary["completed_duration_s"])),
            "smoothness": _smoothness(trace),
            "interaction_extended": _interaction(trace),
            "force_prediction_accuracy": summary[
                "selected_control_path_command_force_prediction"
            ],
            "full_cycle_latency": summary["computational_cost"],
            "fixed_population_prior_used_for_control": True,
            "adaptive_control_enabled": False,
            "robot_limit_constraint_scope": (
                "pre-audited path-invariant continuous IK plus unchanged runtime "
                "robot joint-limit event check"
            ),
        }
    )
    return metrics, trace


def run_progress_aware_cem_pilot(
    measurement_case: MeasurementCase,
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    trajectories = {
        item.name: item
        for item in pilot_trajectories()
        if item.name in PILOT_TRAJECTORY_NAMES
    }
    runs: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    for name in PILOT_TRAJECTORY_NAMES:
        run, trace = _run(measurement_case, trajectories[name])
        runs.append(run)
        traces[name] = trace
    return (
        {
            "schema_version": "high_rom_joint_control_progress_cem_5ms_pilot_v2",
            "evidence_category": "small_engineering_pilot_not_formal_benchmark",
            "design": "2 trajectories x Fixed progress-aware CEM MPC x 1 seed",
            "run_count": len(runs),
            "measurement_case": asdict(measurement_case),
            "high_rom_variant": high_rom_config_payload(),
            "frozen_mpc_config": asdict(HumanMPCConfig()),
            "progress_aware_cem_config": ProgressAwareCEMConfig().as_dict(),
            "maximum_wall_time_s": MAX_WALL_TIME_S,
            "adaptive_control_enabled": False,
            "patient_mismatch_added": False,
            "extra_seeds_run": False,
            "previous_outer_governor_evidence_preserved": True,
            "candidate_force_discretization_s": 0.005,
            "runs": runs,
        },
        traces,
    )
