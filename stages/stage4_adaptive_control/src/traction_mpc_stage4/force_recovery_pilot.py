"""Two-run Stage-4 force-feasibility recovery engineering pilot."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from .force_feasibility_recovery import (
    MODE_CODE,
    NORMAL,
    ForceFeasibilityRecoveryConfig,
    ForceFeasibilityRecoverySupervisor,
)
from .high_rom_dynamic_pilot import (
    PILOT_DURATION_S,
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
RECOVERY_CONFIG = ForceFeasibilityRecoveryConfig()
MAXIMUM_WALL_TIME_S = (
    PILOT_DURATION_S
    + RECOVERY_CONFIG.maximum_recovery_attempts
    * (
        RECOVERY_CONFIG.maximum_hold_duration_s
        + 1.0 / RECOVERY_CONFIG.recovery_rate_per_s
    )
    + 1.0
)


def _smoothness(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time = np.asarray(trace["control_time_s"], dtype=float)
    q_deg = np.degrees(
        np.asarray(trace["control_true_q_rad_god_view"], dtype=float)
    )
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
        "jerk_rms_per_joint_deg_s3": np.sqrt(
            np.mean(jerk**2, axis=0)
        ).tolist(),
        "jerk_combined_rms_deg_s3": float(np.sqrt(np.mean(jerk**2))),
    }


def _interaction(trace: dict[str, np.ndarray]) -> dict[str, float]:
    force = np.linalg.norm(
        np.asarray(trace["cuff_force_local_n_god_view"], dtype=float), axis=1
    )
    moment = np.linalg.norm(
        np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float), axis=1
    )
    commanded = np.asarray(
        trace["commanded_translational_force_norm_n"], dtype=float
    )
    return {
        "executed_command_force_rms_n": float(np.sqrt(np.mean(commanded**2))),
        "executed_command_force_p95_n": float(np.percentile(commanded, 95.0)),
        "executed_command_force_peak_n": float(np.max(commanded)),
        "executed_command_force_margin_n": float(200.0 - np.max(commanded)),
        "physical_cuff_force_rms_n": float(np.sqrt(np.mean(force**2))),
        "physical_cuff_force_p95_n": float(np.percentile(force, 95.0)),
        "physical_cuff_force_peak_n": float(np.max(force)),
        "physical_cuff_moment_rms_nm": float(np.sqrt(np.mean(moment**2))),
        "physical_cuff_moment_peak_nm": float(np.max(moment)),
    }


def _speed_and_hold(
    trace: dict[str, np.ndarray], recovery: dict[str, Any], *, completed: bool
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    alpha = np.asarray(trace["reference_speed_scale"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    hold = np.asarray(trace["force_recovery_hold_active"], dtype=bool)
    dt = np.diff(time)
    below_duration = float(np.sum(dt * (alpha[:-1] < 1.0 - 1.0e-9)))
    hold_duration = float(np.sum(dt * hold[:-1]))
    alpha_rate = np.asarray(trace["reference_speed_scale_rate_per_s"], dtype=float)
    alpha_acceleration = (
        np.gradient(alpha_rate, time, edge_order=2)
        if len(time) >= 3
        else np.zeros_like(alpha_rate)
    )
    sample_indices = np.arange(0, len(time), 20, dtype=int)
    if len(time) and sample_indices[-1] != len(time) - 1:
        sample_indices = np.append(sample_indices, len(time) - 1)
    return {
        "completion_time_s": float(time[-1]),
        "completion_time_extension_from_nominal_23s_s": (
            float(max(0.0, time[-1] - PILOT_DURATION_S)) if completed else None
        ),
        "final_reference_phase_s": float(phase[-1]),
        "alpha_mean": float(np.mean(alpha)),
        "alpha_minimum": float(np.min(alpha)),
        "alpha_maximum": float(np.max(alpha)),
        "time_below_alpha_one_s": below_duration,
        "maximum_abs_alpha_rate_per_s": float(np.max(np.abs(alpha_rate))),
        "maximum_abs_alpha_acceleration_per_s2": float(
            np.max(np.abs(alpha_acceleration))
        ),
        "hold_event_count": len(recovery["hold_events"]),
        "hold_total_duration_s": hold_duration,
        "hold_events": recovery["hold_events"],
        "recovery_alpha_history_20ms": {
            "time_s": time[sample_indices].tolist(),
            "reference_phase_s": phase[sample_indices].tolist(),
            "alpha": alpha[sample_indices].tolist(),
            "mode_code": np.asarray(trace["force_recovery_mode_code"], dtype=float)[
                sample_indices
            ].tolist(),
        },
    }


def _mode_before_time(transitions: list[dict[str, Any]], time_s: float) -> str:
    mode = NORMAL
    for transition in transitions:
        if float(transition["wall_time_s"]) >= time_s - 1.0e-12:
            break
        mode = str(transition["to"])
    return mode


def _latency(
    summary: dict[str, Any], trace: dict[str, np.ndarray], recovery: dict[str, Any]
) -> dict[str, Any]:
    mpc_ms = np.asarray(trace["mpc_cycle_compute_ms"], dtype=float)
    mpc_time = np.asarray(trace["mpc_cycle_time_s"], dtype=float)
    full_ms = np.asarray(trace["high_level_cycle_compute_ms"], dtype=float)
    modes = np.array(
        [_mode_before_time(recovery["transitions"], time) for time in mpc_time]
    )
    normal = mpc_ms[modes == NORMAL]
    if not len(normal):
        normal = mpc_ms
    return {
        "normal_mpc": {
            "sample_count": int(len(normal)),
            "mean_ms": float(np.mean(normal)),
            "p95_ms": float(np.percentile(normal, 95.0)),
            "max_ms": float(np.max(normal)),
            "deadline_misses_over_20ms": int(np.sum(normal > 20.0)),
            "effective_hz_from_mean": float(1000.0 / np.mean(normal)),
        },
        "hold_recovery_scan": recovery["recovery_scan_latency"],
        "low_level_recovery_filter": recovery["filter_latency"],
        "full_high_level_cycle": {
            "sample_count": int(len(full_ms)),
            "mean_ms": float(np.mean(full_ms)),
            "p95_ms": float(np.percentile(full_ms, 95.0)),
            "max_ms": float(np.max(full_ms)),
            "deadline_misses_over_20ms": int(np.sum(full_ms > 20.0)),
            "effective_hz_from_mean": float(1000.0 / np.mean(full_ms)),
        },
        "sensor_summary_consistent": bool(
            summary["computational_cost"][
                "high_level_cycle_deadline_misses_over_20ms"
            ]
            == int(np.sum(full_ms > 20.0))
        ),
    }


def _run(
    measurement_case: MeasurementCase,
    trajectory: HighROMPilotTrajectory,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    supervisor = ForceFeasibilityRecoverySupervisor(
        trajectory, config=RECOVERY_CONFIG
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
        duration_s=MAXIMUM_WALL_TIME_S,
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__fixed_mpc_force_recovery",
        true_human_override=HIGH_ROM_HUMAN_V2,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_v2",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        reference_execution=supervisor,
        reference_completion_phase_s=PILOT_DURATION_S,
        mpc_factory=lambda: HumanSpaceMPC(),
        estimator_factory=estimator_factory,
    )
    recovery = summary["reference_execution"]
    metrics = compact_run_metrics(
        summary,
        trace,
        controller_id="fixed_mpc_force_feasibility_recovery",
        trajectory=trajectory,
    )
    metrics.update(
        {
            "completion_time_s": float(summary["completed_duration_s"]),
            "recovery_classification": recovery["recovery_classification"],
            "recovery": recovery,
            "speed_and_hold": _speed_and_hold(
                trace, recovery, completed=bool(summary["mechanically_completed_requested_duration"])
            ),
            "smoothness": _smoothness(trace),
            "interaction_extended": _interaction(trace),
            "latency": _latency(summary, trace, recovery),
            "fixed_population_prior_used_for_control": True,
            "adaptive_control_enabled": False,
            "full_endpoint_reached": bool(
                np.all(
                    np.max(
                        np.asarray(trace["human_q_deg_god_view"], dtype=float),
                        axis=0,
                    )
                    >= np.asarray(trajectory.endpoint_deg, dtype=float) - 5.0
                )
            ),
        }
    )
    return metrics, trace


def run_force_recovery_pilot(
    measurement_case: MeasurementCase,
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    trajectories = {
        trajectory.name: trajectory
        for trajectory in pilot_trajectories()
        if trajectory.name in PILOT_TRAJECTORY_NAMES
    }
    if set(trajectories) != set(PILOT_TRAJECTORY_NAMES):
        raise RuntimeError("required High-ROM pilot trajectories are unavailable")
    runs: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    for name in PILOT_TRAJECTORY_NAMES:
        run, trace = _run(measurement_case, trajectories[name])
        runs.append(run)
        traces[name] = trace
    return (
        {
            "schema_version": "high_rom_force_feasibility_recovery_pilot_v1",
            "evidence_category": "small_engineering_pilot_not_formal_benchmark",
            "design": "2 blocked trajectories x Fixed MPC force recovery x 1 seed",
            "run_count": len(runs),
            "measurement_case": asdict(measurement_case),
            "high_rom_variant": high_rom_config_payload(),
            "frozen_mpc_config": asdict(HumanMPCConfig()),
            "recovery_config": RECOVERY_CONFIG.as_dict(),
            "maximum_wall_time_s": MAXIMUM_WALL_TIME_S,
            "maximum_wall_time_basis": (
                "23 s reference plus three common 2 s HOLD timeouts and three "
                "0-to-1 recoveries at 0.25/s, plus 1 s numerical allowance"
            ),
            "adaptive_control_enabled": False,
            "patient_mismatch_added": False,
            "extra_seeds_run": False,
            "mpc_cem_trust_allocator_prior_retuned": False,
            "runtime_200n_gate_unchanged": True,
            "previous_pacing_evidence_preserved": True,
            "runs": runs,
        },
        traces,
    )
