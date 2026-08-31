"""Two-run Fixed-MPC pilot for offline High-ROM path time parameterization."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from .constraint_aware_path_timing import (
    ConstraintAwarePathTiming,
    PathTimingConfig,
    nominal_high_rom_population_prior_model,
)
from .high_rom_dynamic_pilot import (
    HighROMPilotTrajectory,
    compact_run_metrics,
    pilot_trajectories,
)
from .high_rom_human_v2 import HIGH_ROM_HUMAN_V2, high_rom_config_payload
from .measurement import MeasurementCase
from .mpc import HumanMPCConfig, HumanSpaceMPC
from .online_trust import OnlineSingleChallengerTrustEstimator
from .sensor_realism import run_sensor_realism_case


PILOT_TRAJECTORY_NAMES = (
    "hip_dominant_100_60",
    "aggressive_both_120_120",
)


def _smoothness(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time = np.asarray(trace["control_time_s"], dtype=float)
    q_deg = np.degrees(
        np.asarray(trace["control_true_q_rad_god_view"], dtype=float)
    )
    velocity = np.gradient(q_deg, time, axis=0, edge_order=2)
    acceleration = np.gradient(velocity, time, axis=0, edge_order=2)
    jerk = np.gradient(acceleration, time, axis=0, edge_order=2)
    return {
        "acceleration_rms_per_joint_deg_s2": np.sqrt(
            np.mean(acceleration**2, axis=0)
        ).tolist(),
        "acceleration_combined_rms_deg_s2": float(
            np.sqrt(np.mean(acceleration**2))
        ),
        "jerk_rms_per_joint_deg_s3": np.sqrt(
            np.mean(jerk**2, axis=0)
        ).tolist(),
        "jerk_combined_rms_deg_s3": float(np.sqrt(np.mean(jerk**2))),
    }


def _speed(trace: dict[str, np.ndarray], planner: ConstraintAwarePathTiming) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    alpha = np.asarray(trace["reference_speed_scale"], dtype=float)
    below = alpha < 1.0 - 1e-9
    below_time = float(np.sum(np.diff(time) * below[:-1])) if len(time) > 1 else 0.0
    slow_indices = np.flatnonzero(below)
    recovery = None
    if len(slow_indices):
        after = np.flatnonzero(alpha[slow_indices[0] :] >= 1.0 - 1e-6)
        if len(after):
            index = int(slow_indices[0] + after[0])
            recovery = {
                "wall_time_s": float(time[index]),
                "reference_phase_time_s": float(trace["reference_phase_time_s"][index]),
            }
    return {
        "mean": float(np.trapz(alpha, time) / max(time[-1], 1e-12)),
        "minimum": float(np.min(alpha)),
        "maximum": float(np.max(alpha)),
        "time_below_nominal_s": below_time,
        "fraction_time_below_nominal": below_time / max(float(time[-1]), 1e-12),
        "first_slowing_wall_time_s": (
            float(time[slow_indices[0]]) if len(slow_indices) else None
        ),
        "first_slowing_reference_phase_s": (
            float(trace["reference_phase_time_s"][slow_indices[0]])
            if len(slow_indices)
            else None
        ),
        "recovered_to_nominal": recovery is not None,
        "recovery_location": recovery,
        "planned_duration_s": planner.duration_s,
    }


def _interaction(
    trace: dict[str, np.ndarray], planner: ConstraintAwarePathTiming
) -> dict[str, Any]:
    physical_force = np.linalg.norm(
        np.asarray(trace["cuff_force_local_n_god_view"], dtype=float), axis=1
    )
    physical_moment = np.linalg.norm(
        np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float), axis=1
    )
    commanded = np.asarray(
        trace["commanded_translational_force_norm_n"], dtype=float
    )
    command_time = np.asarray(trace["commanded_force_time_s"], dtype=float)
    phase = np.interp(
        command_time,
        np.asarray(trace["time_s"], dtype=float),
        np.asarray(trace["reference_phase_time_s"], dtype=float),
    )
    planned = np.interp(
        phase, planner.phase_grid_s, planner.predicted_force_n
    )
    error = commanded - planned
    return {
        "planned_inverse_dynamics_force_peak_n": float(
            np.max(planner.predicted_force_n)
        ),
        "executed_command_force_peak_n": float(np.max(commanded)),
        "executed_command_force_margin_n": float(200.0 - np.max(commanded)),
        "planner_to_executed_command_error": {
            "signed_mean_n": float(np.mean(error)),
            "absolute_mean_n": float(np.mean(np.abs(error))),
            "absolute_p95_n": float(np.percentile(np.abs(error), 95.0)),
            "absolute_max_n": float(np.max(np.abs(error))),
            "executed_minus_planned_peak_difference_n": float(
                np.max(commanded) - np.max(planner.predicted_force_n)
            ),
            "sample_count": int(len(error)),
        },
        "physical_cuff_force_rms_n": float(
            np.sqrt(np.mean(physical_force**2))
        ),
        "physical_cuff_force_p95_n": float(np.percentile(physical_force, 95.0)),
        "physical_cuff_force_peak_n": float(np.max(physical_force)),
        "physical_cuff_moment_rms_nm": float(
            np.sqrt(np.mean(physical_moment**2))
        ),
        "physical_cuff_moment_peak_nm": float(np.max(physical_moment)),
    }


def _latency(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    planner: ConstraintAwarePathTiming,
) -> dict[str, Any]:
    computational = summary["computational_cost"]
    sample_count = int(len(trace["mpc_cycle_compute_ms"]))
    return {
        "one_time_planning_ms": 1000.0 * planner.planning_latency_s,
        "existing_mpc_cycle_sample_count": sample_count,
        "existing_mpc_cycle_mean_ms": computational["mpc_mean_ms"],
        "existing_mpc_cycle_p95_ms": computational["mpc_p95_ms"],
        "existing_mpc_cycle_max_ms": computational["mpc_max_ms"],
        "existing_mpc_deadline_misses_over_20ms": computational[
            "mpc_deadline_misses_over_20ms"
        ],
        "existing_mpc_effective_hz_from_mean": computational[
            "mpc_effective_hz_from_mean"
        ],
        "full_high_level_cycle_mean_ms": computational[
            "high_level_cycle_including_estimator_and_mpc_mean_ms"
        ],
        "full_high_level_cycle_p95_ms": computational[
            "high_level_cycle_including_estimator_and_mpc_p95_ms"
        ],
        "full_high_level_cycle_max_ms": computational[
            "high_level_cycle_including_estimator_and_mpc_max_ms"
        ],
        "full_high_level_deadline_misses_over_20ms": computational[
            "high_level_cycle_deadline_misses_over_20ms"
        ],
        "full_high_level_effective_hz_from_mean": computational[
            "high_level_cycle_effective_hz_from_mean"
        ],
        "planner_inside_control_loop": False,
    }


def run_path_timing_pilot(
    measurement_case: MeasurementCase,
    *,
    config: PathTimingConfig = PathTimingConfig(),
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]], dict[str, ConstraintAwarePathTiming]]:
    trajectories = {
        item.name: item
        for item in pilot_trajectories()
        if item.name in PILOT_TRAJECTORY_NAMES
    }
    model = nominal_high_rom_population_prior_model()
    runs: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    planners: dict[str, ConstraintAwarePathTiming] = {}
    for name in PILOT_TRAJECTORY_NAMES:
        trajectory = trajectories[name]
        planner = ConstraintAwarePathTiming(trajectory, model, config=config)
        planners[name] = planner

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
            duration_s=planner.duration_s,
            estimator_architecture="integral_minimal",
            result_case_name=f"{name}__fixed_mpc_constraint_aware_path_timing",
            true_human_override=HIGH_ROM_HUMAN_V2,
            true_metadata_override={
                "case": "nominal_high_rom_human_v2_engineering_v2",
                "canonical_human_overwritten": False,
                "engineering_assumption": True,
            },
            reference_fn=trajectory.reference,
            trajectory_label=name,
            trajectory_waypoints=trajectory.waypoints,
            reference_execution=planner,
            reference_completion_phase_s=23.0,
            mpc_factory=lambda: HumanSpaceMPC(),
            estimator_factory=estimator_factory,
        )
        run = compact_run_metrics(
            summary,
            trace,
            controller_id="fixed_mpc_constraint_aware_path_timing",
            trajectory=trajectory,
        )
        run.update(
            {
                "completion_time_s": float(summary["completed_duration_s"]),
                "path_timing": planner.summary(float(summary["completed_duration_s"])),
                "speed": _speed(trace, planner),
                "interaction_extended": _interaction(trace, planner),
                "smoothness": _smoothness(trace),
                "latency": _latency(summary, trace, planner),
                "fixed_population_prior_used_for_control_and_planning": True,
                "adaptive_control_enabled": False,
            }
        )
        runs.append(run)
        traces[name] = trace

    return (
        {
            "schema_version": "high_rom_constraint_aware_path_timing_pilot_v1",
            "evidence_category": "small_engineering_pilot_not_formal_benchmark",
            "design": "2 trajectories x frozen Fixed MPC x one offline timing plan x 1 seed",
            "run_count": len(runs),
            "measurement_case": asdict(measurement_case),
            "high_rom_variant": high_rom_config_payload(),
            "frozen_mpc_config": asdict(HumanMPCConfig()),
            "path_timing_config": config.as_dict(),
            "frozen_components_changed": False,
            "adaptive_control_enabled": False,
            "patient_mismatch_added": False,
            "extra_seeds_run": False,
            "runs": runs,
        },
        traces,
        planners,
    )
