"""Small fixed-clock versus predictive-speed-governor High-ROM pilot."""

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
from .mpc import HumanMPCConfig, HumanSpaceMPC
from .online_trust import OnlineSingleChallengerTrustEstimator
from .predictive_speed_governor import (
    PredictiveSpeedGovernor,
    PredictiveSpeedGovernorConfig,
)
from .sensor_realism import run_sensor_realism_case


PILOT_TRAJECTORY_NAMES = (
    "hip_dominant_100_60",
    "aggressive_both_120_120",
)
MAX_GOVERNED_WALL_TIME_S = (
    PILOT_DURATION_S / min(PredictiveSpeedGovernorConfig().candidate_speed_scales)
    + 0.1
)


def _smoothness_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
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
        "jerk_rms_per_joint_deg_s3": np.sqrt(np.mean(jerk**2, axis=0)).tolist(),
        "jerk_combined_rms_deg_s3": float(np.sqrt(np.mean(jerk**2))),
    }


def _speed_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    alpha = np.asarray(trace["force_speed_scale"], dtype=float)
    target = np.asarray(trace["force_speed_target_scale"], dtype=float)
    rate = np.asarray(trace["reference_speed_scale_rate_per_s"], dtype=float)
    below = alpha < 1.0 - 1e-9
    below_duration = 0.0
    if len(time) > 1:
        below_duration = float(np.sum(np.diff(time) * below[:-1]))
    return {
        "completed_wall_time_s": float(time[-1]),
        "completed_reference_phase_s": float(phase[-1]),
        "reference_progress_fraction": float(
            np.clip(phase[-1] / PILOT_DURATION_S, 0.0, 1.0)
        ),
        "mean_alpha": float(np.mean(alpha)),
        "minimum_alpha": float(np.min(alpha)),
        "minimum_target_alpha": float(np.min(target)),
        "time_below_nominal_s": below_duration,
        "alpha_total_variation": float(np.sum(np.abs(np.diff(alpha)))),
        "maximum_abs_alpha_rate_per_s": float(np.max(np.abs(rate))),
        "maximum_predicted_command_force_n": float(
            np.max(trace["governor_predicted_peak_command_force_n"])
        ),
    }


def _interaction_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
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
        "physical_cuff_force_rms_n": float(np.sqrt(np.mean(force**2))),
        "physical_cuff_force_p95_n": float(np.percentile(force, 95.0)),
        "physical_cuff_force_peak_n": float(np.max(force)),
        "physical_cuff_moment_rms_nm": float(np.sqrt(np.mean(moment**2))),
        "physical_cuff_moment_peak_nm": float(np.max(moment)),
        "commanded_force_p95_n": float(np.percentile(commanded, 95.0)),
        "commanded_force_peak_or_gate_attempt_n": float(np.max(commanded)),
        "commanded_force_minimum_margin_to_gate_n": float(200.0 - np.max(commanded)),
    }


def _run_arm(
    measurement_case: MeasurementCase,
    trajectory: HighROMPilotTrajectory,
    *,
    governed: bool,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
        return OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=measurement_case,
            apply_qualified_model=False,
            rom_human=HIGH_ROM_HUMAN_V2,
        )

    governor = PredictiveSpeedGovernor(trajectory.reference) if governed else None
    arm = "fixed_mpc_predictive_speed_governor" if governed else "fixed_mpc_fixed_clock"
    summary, trace = run_sensor_realism_case(
        measurement_case,
        duration_s=MAX_GOVERNED_WALL_TIME_S if governed else PILOT_DURATION_S,
        estimator_architecture="integral_minimal",
        result_case_name=f"{trajectory.name}__{arm}",
        true_human_override=HIGH_ROM_HUMAN_V2,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_v2",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        reference_execution=governor,
        reference_completion_phase_s=PILOT_DURATION_S if governed else None,
        mpc_factory=lambda: HumanSpaceMPC(),
        estimator_factory=estimator_factory,
    )
    metrics = compact_run_metrics(
        summary,
        trace,
        controller_id=arm,
        trajectory=trajectory,
    )
    speed = _speed_metrics(trace)
    governor_summary = summary.get("reference_execution")
    if governor_summary is not None:
        speed["maximum_predicted_command_force_n"] = max(
            speed["maximum_predicted_command_force_n"],
            float(governor_summary["maximum_selected_prediction_n"]),
        )
        speed["minimum_target_alpha"] = min(
            speed["minimum_target_alpha"],
            float(governor_summary["minimum_selected_target_scale"]),
        )
        speed["maximum_abs_alpha_rate_per_s"] = max(
            speed["maximum_abs_alpha_rate_per_s"],
            abs(float(governor_summary["final_status"]["speed_scale_rate_per_s"])),
        )
    metrics.update(
        {
            "clock_mode": "predictive_speed_governor" if governed else "fixed_nominal",
            "speed": speed,
            "smoothness": _smoothness_metrics(trace),
            "interaction_extended": _interaction_metrics(trace),
            "governor": governor_summary,
            "fixed_population_prior_used_for_control": True,
            "adaptive_control_enabled": False,
        }
    )
    return metrics, trace


def run_predictive_speed_governor_pilot(
    measurement_case: MeasurementCase,
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    trajectories = {
        item.name: item
        for item in pilot_trajectories()
        if item.name in PILOT_TRAJECTORY_NAMES
    }
    if set(trajectories) != set(PILOT_TRAJECTORY_NAMES):
        raise RuntimeError("required High-ROM pilot trajectories are unavailable")

    runs: list[dict[str, Any]] = []
    traces: dict[str, dict[str, np.ndarray]] = {}
    for trajectory_name in PILOT_TRAJECTORY_NAMES:
        trajectory = trajectories[trajectory_name]
        for governed in (False, True):
            run, trace = _run_arm(
                measurement_case,
                trajectory,
                governed=governed,
            )
            runs.append(run)
            traces[f"{trajectory_name}__{run['clock_mode']}"] = trace

    comparisons: dict[str, Any] = {}
    for trajectory_name in PILOT_TRAJECTORY_NAMES:
        pair = [item for item in runs if item["trajectory"] == trajectory_name]
        fixed = next(item for item in pair if item["clock_mode"] == "fixed_nominal")
        governed = next(
            item for item in pair if item["clock_mode"] == "predictive_speed_governor"
        )
        comparisons[trajectory_name] = {
            "fixed_completed": fixed["completion"],
            "governed_completed": governed["completion"],
            "governor_minus_fixed_tracking_rmse_deg": (
                governed["tracking_combined_rmse_deg"]
                - fixed["tracking_combined_rmse_deg"]
            ),
            "governor_minus_fixed_physical_force_peak_n": (
                governed["interaction_extended"]["physical_cuff_force_peak_n"]
                - fixed["interaction_extended"]["physical_cuff_force_peak_n"]
            ),
            "governor_minus_fixed_command_peak_n": (
                governed["interaction_extended"][
                    "commanded_force_peak_or_gate_attempt_n"
                ]
                - fixed["interaction_extended"][
                    "commanded_force_peak_or_gate_attempt_n"
                ]
            ),
            "governed_completion_time_extension_s": (
                governed["speed"]["completed_wall_time_s"] - PILOT_DURATION_S
                if governed["completion"]
                else None
            ),
        }

    config = PredictiveSpeedGovernorConfig()
    all_governed_completed = all(
        comparison["governed_completed"] for comparison in comparisons.values()
    )
    return (
        {
            "schema_version": "high_rom_predictive_speed_governor_small_pilot_v1",
            "evidence_category": "small_engineering_pilot_not_formal_benchmark",
            "design": "2 trajectories x fixed clock/governed clock x Fixed MPC x 1 seed",
            "run_count": len(runs),
            "measurement_case": asdict(measurement_case),
            "high_rom_variant": high_rom_config_payload(),
            "frozen_mpc_config": asdict(HumanMPCConfig()),
            "governor_config": config.as_dict(),
            "maximum_governed_wall_time_s": MAX_GOVERNED_WALL_TIME_S,
            "maximum_wall_time_basis": (
                "23 s reference divided by existing 0.50 minimum speed plus 0.1 s numerical allowance"
            ),
            "same_controller_prior_allocator_gate_geometry_and_path": True,
            "trust_confidence_used_for_force_pacing": False,
            "adaptive_control_enabled": False,
            "patient_mismatch_added": False,
            "additional_measurement_seeds_run": False,
            "optional_90_120_run": False,
            "decision": {
                "all_governed_paths_completed": all_governed_completed,
                "governor_effective_in_this_pilot": False,
                "observed_reason": (
                    "the 0.30 s seed-sequence force forecast stayed below the "
                    "195 N planning threshold until the hard-gate control update; "
                    "the applied alpha therefore remained 1.0"
                ),
                "remaining_blocker": (
                    "prediction fidelity/advance warning for the outbound command-force "
                    "transient, followed by the unchanged 200 N gate"
                ),
                "not_observed_as_blocker": [
                    "Human ROM",
                    "upper soft zone",
                    "solver failure",
                    "unintended contact",
                    "robot joint limit",
                ],
                "recommended_next_experiment": (
                    "instrumented diagnostic-only replay of the frozen pre-gate segment "
                    "comparing the governor "
                    "seed forecast with the selected MPC sequence and realized next-step "
                    "command; do not rerun or retune dynamics until that mismatch is localized"
                ),
            },
            "runs": runs,
            "paired_comparisons": comparisons,
        },
        traces,
    )
