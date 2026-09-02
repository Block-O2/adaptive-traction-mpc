#!/usr/bin/env python3
"""Run the three authorized Phase-5 High-ROM system engineering pilots."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.reference import (
    CuffPoseReference,
    _world_from_cuff,
    quintic_progress,
)
from traction_mpc_stage4.confidence_execution import UnifiedReferenceManager
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.measurement import measurement_case_dict
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.reference import TeachingWaypoint
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
    write_strict_json,
)
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
)
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.track_brake import BRAKE, TrackBrakeSupervisor


STAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STAGE_ROOT.parents[1]
DEFAULT_MATRIX = (
    STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
)
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase5_high_rom_system_pilot_20260902"
)
NOMINAL_PATH_DURATION_S = 23.0
INITIAL_Q_DEG = np.array([5.0, 10.0])
HIGH_ROM_HUMAN = replace(
    HUMAN,
    q_min_rad=(0.0, 0.0),
    q_max_rad=(math.radians(125.0), math.radians(125.0)),
)


@dataclass(frozen=True)
class PilotTrajectory:
    name: str
    endpoint_deg: tuple[float, float]

    @property
    def waypoints(self) -> tuple[TeachingWaypoint, ...]:
        start = tuple(float(value) for value in INITIAL_Q_DEG)
        target = tuple(float(value) for value in self.endpoint_deg)
        return (
            TeachingWaypoint(0.0, start, "initial_hold_start"),
            TeachingWaypoint(1.0, start, "outbound_start"),
            TeachingWaypoint(13.0, target, "target_hold_start"),
            TeachingWaypoint(14.5, target, "return_start"),
            TeachingWaypoint(22.0, start, "final_hold_start"),
            TeachingWaypoint(23.0, start, "final_hold_end"),
        )

    def reference(self, phase_s: float) -> CuffPoseReference:
        time_s = float(np.clip(phase_s, 0.0, NOMINAL_PATH_DURATION_S))
        start = np.radians(INITIAL_Q_DEG)
        target = np.radians(np.asarray(self.endpoint_deg, dtype=float))
        delta = target - start
        if time_s <= 1.0:
            q, dq, ddq = start, np.zeros(2), np.zeros(2)
        elif time_s < 13.0:
            duration = 12.0
            progress, velocity, acceleration = quintic_progress(
                (time_s - 1.0) / duration
            )
            q = start + delta * progress
            dq = delta * velocity / duration
            ddq = delta * acceleration / duration**2
        elif time_s <= 14.5:
            q, dq, ddq = target, np.zeros(2), np.zeros(2)
        elif time_s < 22.0:
            duration = 7.5
            progress, velocity, acceleration = quintic_progress(
                (time_s - 14.5) / duration
            )
            q = target - delta * progress
            dq = -delta * velocity / duration
            ddq = -delta * acceleration / duration**2
        else:
            q, dq, ddq = start, np.zeros(2), np.zeros(2)
        return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))


TRAJECTORIES = (
    PilotTrajectory("knee_high_folding_90_120", (90.0, 120.0)),
    PilotTrajectory("hip_dominant_100_60", (100.0, 60.0)),
    PilotTrajectory("aggressive_both_120_120", (120.0, 120.0)),
)


def _norm(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return np.linalg.norm(array, axis=1) if len(array) else np.zeros(0)


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=float)
    if not len(array):
        return {"count": 0, "rms": None, "p95": None, "peak": None}
    return {
        "count": int(len(array)),
        "rms": float(np.sqrt(np.mean(array**2))),
        "p95": float(np.percentile(array, 95.0)),
        "peak": float(np.max(array)),
    }


def _smoothness(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time_s = np.asarray(trace["control_time_s"], dtype=float)
    dq_deg_s = np.degrees(
        np.asarray(trace["control_true_dq_rad_s_god_view"], dtype=float)
    )
    if len(time_s) >= 3:
        acceleration = np.gradient(dq_deg_s, time_s, axis=0, edge_order=2)
        jerk = np.gradient(acceleration, time_s, axis=0, edge_order=2)
    else:
        acceleration = np.zeros_like(dq_deg_s)
        jerk = np.zeros_like(dq_deg_s)
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


def _alpha_metrics(trace: dict[str, np.ndarray]) -> dict[str, Any]:
    time_s = np.asarray(trace["time_s"], dtype=float)
    alpha = np.asarray(trace["reference_speed_scale"], dtype=float)
    alpha_rate = np.asarray(
        trace["reference_speed_scale_rate_per_s"], dtype=float
    )
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    below = alpha < 1.0 - 1e-9
    below_duration = (
        float(np.sum(np.diff(time_s) * below[:-1])) if len(time_s) > 1 else 0.0
    )
    filter_time = np.asarray(trace["safety_filter_time_s"], dtype=float)
    filter_status = np.asarray(trace["safety_filter_status"])
    filtered_time = filter_time[filter_status == SAFE_FILTERED]
    decreased_during = False
    recovered_after = False
    first_filtered_time = None
    last_filtered_time = None
    if len(filtered_time):
        first_filtered_time = float(filtered_time[0])
        last_filtered_time = float(filtered_time[-1])
        during = (time_s >= first_filtered_time) & (time_s <= last_filtered_time)
        decreased_during = bool(
            np.any(alpha_rate[during] < -1e-12)
            or np.min(alpha[during]) < alpha[np.flatnonzero(during)[0]] - 1e-9
        )
        after = time_s > last_filtered_time
        if np.any(after):
            alpha_at_last = float(
                np.interp(last_filtered_time, time_s, alpha)
            )
            recovered_after = bool(np.max(alpha[after]) > alpha_at_last + 1e-9)
    return {
        "mean": float(np.mean(alpha)),
        "minimum": float(np.min(alpha)),
        "maximum": float(np.max(alpha)),
        "final": float(alpha[-1]),
        "time_below_one_s": below_duration,
        "final_phase_s": float(phase[-1]),
        "phase_delay_s": float(time_s[-1] - phase[-1]),
        "maximum_abs_rate_per_s": float(np.max(np.abs(alpha_rate))),
        "first_safe_filtered_time_s": first_filtered_time,
        "last_safe_filtered_time_s": last_filtered_time,
        "decreased_during_filter_intervention": decreased_during,
        "recovered_toward_one_after_intervention": recovered_after,
    }


def _filter_metrics(
    trace: dict[str, np.ndarray], supervisor: dict[str, Any]
) -> dict[str, Any]:
    status = np.asarray(trace["safety_filter_status"])
    filtered = status == SAFE_FILTERED

    def selected(key: str) -> np.ndarray:
        values = np.asarray(trace[key], dtype=float)
        return values[filtered]

    return {
        "status_counts": {
            name: int(np.count_nonzero(status == name))
            for name in (SAFE_UNCHANGED, SAFE_FILTERED, FILTER_INFEASIBLE)
        },
        "supervisor_status_counts_match": supervisor[
            "safety_filter_status_counts"
        ]
        == {
            name: int(np.count_nonzero(status == name))
            for name in (SAFE_UNCHANGED, SAFE_FILTERED, FILTER_INFEASIBLE)
        },
        "safe_filtered_intervention_coordinate_norm": _distribution(
            selected("safety_filter_intervention_coordinate_norm")
        ),
        "safe_filtered_force_intervention_norm_n": _distribution(
            selected("safety_filter_force_intervention_norm_n")
        ),
        "safe_filtered_moment_intervention_norm_nm": _distribution(
            selected("safety_filter_moment_intervention_norm_nm")
        ),
        "safe_filtered_abs_lambda": _distribution(
            np.abs(selected("safety_filter_lambda"))
        ),
        "maximum_human_torque_preservation_residual_nm": float(
            np.max(np.asarray(trace["safety_filter_torque_residual_nm"]))
        )
        if len(status)
        else None,
        "nominal_executable_force_norm_n": _distribution(
            np.asarray(
                trace["safety_filter_nominal_executable_force_norm_n"],
                dtype=float,
            )
        ),
        "filtered_executable_force_norm_n": _distribution(
            np.asarray(
                trace["safety_filter_filtered_executable_force_norm_n"],
                dtype=float,
            )
        ),
        "safe_filtered_nominal_executable_force_norm_n": _distribution(
            selected("safety_filter_nominal_executable_force_norm_n")
        ),
        "safe_filtered_output_executable_force_norm_n": _distribution(
            selected("safety_filter_filtered_executable_force_norm_n")
        ),
    }


def _compact_result(
    trajectory: PilotTrajectory,
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
) -> dict[str, Any]:
    q_deg = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    command_force = _norm(trace["executed_command_force_total_n"])
    actual_force = _norm(trace["cuff_force_local_n_god_view"])
    measured_force = _norm(trace["measured_cuff_force_world_n"])
    cuff_moment = _norm(trace["cuff_moment_local_nm_god_view"])
    events = summary["events"]
    supervisor = summary["track_brake_supervisor"]
    alpha = _alpha_metrics(trace)
    safety_filter = _filter_metrics(trace, supervisor)
    command_safe = bool(
        len(command_force) and np.max(command_force) <= 200.0 + 1e-9
    )
    invalid_event = bool(
        events["force_gate_events"]
        or events["rom_event_samples"]
        or events["mpc_solver_failures"]
        or events["mujoco_warning_counts"]
        or summary["robot"]["joint_position_limit_samples"]
    )
    completed = bool(summary["mechanically_completed_requested_duration"])
    if completed and command_safe and not invalid_event:
        classification = "PASS"
    elif command_safe and not invalid_event:
        classification = "PARTIAL"
    else:
        classification = "FAIL"
    return {
        "trajectory": trajectory.name,
        "endpoint_deg": list(trajectory.endpoint_deg),
        "classification": classification,
        "task": {
            "completed": completed,
            "termination_reason": summary["termination_reason"],
            "completion_time_s": (
                float(summary["completed_duration_s"]) if completed else None
            ),
            "elapsed_time_s": float(summary["completed_duration_s"]),
            "final_hip_knee_deg": q_deg[-1].tolist(),
            "peak_hip_knee_deg": np.max(q_deg, axis=0).tolist(),
            "tracking_rmse_hip_knee_deg": summary["tracking"]["rmse_deg"],
            "tracking_combined_rmse_deg": summary["tracking"][
                "combined_rmse_deg"
            ],
            "tracking_max_hip_knee_deg": summary["tracking"][
                "max_abs_error_deg"
            ],
        },
        "reference_manager": alpha,
        "safety_filter": safety_filter,
        "safety": {
            "executed_command_force_n": _distribution(command_force),
            "measured_cuff_force_n": _distribution(measured_force),
            "actual_cuff_force_n": _distribution(actual_force),
            "actual_cuff_moment_nm": _distribution(cuff_moment),
            "all_executed_commands_at_or_below_200_n": command_safe,
            "independent_200n_gate_events": events["force_gate_events"],
            "brake_count": supervisor["transition_count"],
            "brake_duration_s": 0.005 * supervisor["brake_cycle_count"],
            "brake_trigger": supervisor["trigger"],
            "brake_terminal_status": supervisor["terminal_status"],
            "rom_event_samples": events["rom_event_samples"],
            "mpc_solver_failures": events["mpc_solver_failures"],
            "mujoco_warning_counts": events["mujoco_warning_counts"],
            "robot_joint_limit_samples": summary["robot"][
                "joint_position_limit_samples"
            ],
            "unintended_contact_pairs": events["unintended_contact_pairs"],
        },
        "motion": _smoothness(trace),
        "runtime": summary["computational_cost"],
        "architecture": {
            "controller": "fixed_mpc_prior_only",
            "adaptive_model_applied": False,
            "cuff_adapter_translation_m": (
                ENGINEERING_ATTACHMENT_FROM_CUFF.translation.tolist()
            ),
            "reference_manager": "UnifiedReferenceManager",
            "supervisor_modes": ["TRACK", BRAKE],
            "new_recovery_mechanism": False,
        },
    }


def _git_provenance() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"phase4_commit": commit, "working_tree_dirty_during_pilot": bool(dirty)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite pilot: {output_dir}")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix, measurement_seed=44104)
    if case.seed != 44104:
        raise RuntimeError("Phase-5 measurement seed drifted")
    maximum_wall_time_s = float(matrix["shared_contract"]["wall_time_limit_s"])
    allocator = default_engineering_cuff_allocator()
    output_dir.mkdir(parents=True)
    runs: list[dict[str, Any]] = []
    for trajectory in TRAJECTORIES:
        manager = UnifiedReferenceManager(
            trajectory.reference,
            confidence_aware=True,
        )
        supervisor = TrackBrakeSupervisor()

        def estimator_factory(measurement: Any, q_prior: np.ndarray) -> Any:
            return OnlineSingleChallengerTrustEstimator(
                measurement,
                q_prior,
                measurement_case=case,
                apply_qualified_model=False,
                rom_human=HIGH_ROM_HUMAN,
            )

        summary, trace = run_sensor_realism_case(
            case,
            duration_s=maximum_wall_time_s,
            estimator_architecture="integral_minimal",
            result_case_name=f"{trajectory.name}__fixed_mpc_phase5_system",
            true_human_override=HIGH_ROM_HUMAN,
            true_metadata_override={
                "case": "nominal_high_rom_human_v2_engineering_0_125deg",
                "canonical_human_overwritten": False,
                "engineering_assumption": True,
            },
            reference_fn=trajectory.reference,
            trajectory_label=trajectory.name,
            trajectory_waypoints=trajectory.waypoints,
            plant_factory=lambda human: SensorBoundaryStage4Plant(
                human,
                attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            ),
            reference_execution=manager,
            reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
            capture_system_pilot_diagnostics=True,
            track_brake_supervisor=supervisor,
            mpc_factory=lambda: HumanSpaceMPC(cuff_allocator=allocator),
            cuff_allocator=allocator,
            estimator_factory=estimator_factory,
        )
        expected_beta = nominal_base_parameters(HUMAN)
        beta = np.asarray(trace["dynamic_base_estimate"], dtype=float)
        np.testing.assert_allclose(
            beta,
            np.broadcast_to(expected_beta, beta.shape),
            rtol=0.0,
            atol=1e-12,
        )
        run_dir = output_dir / trajectory.name
        run_dir.mkdir()
        write_strict_json(run_dir / "raw_summary.json", summary)
        np.savez_compressed(run_dir / "trace.npz", **trace)
        compact = _compact_result(trajectory, summary, trace)
        write_strict_json(run_dir / "metrics.json", compact)
        runs.append(compact)
        print(
            json.dumps(
                {
                    "trajectory": trajectory.name,
                    "classification": compact["classification"],
                    "termination": compact["task"]["termination_reason"],
                    "elapsed_s": compact["task"]["elapsed_time_s"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    payload = {
        "schema_version": "phase5_high_rom_system_pilot_v1",
        "evidence_category": "engineering_pilot_not_formal_or_authoritative",
        "run_count": len(runs),
        "run_order": [item.name for item in TRAJECTORIES],
        "controller": "fixed_mpc_prior_only",
        "measurement_case": measurement_case_dict(case),
        "high_rom_variant": {
            "q_min_deg": np.degrees(HIGH_ROM_HUMAN.q_min_rad).tolist(),
            "q_max_deg": np.degrees(HIGH_ROM_HUMAN.q_max_rad).tolist(),
            "only_change_from_nominal_human": "q_max_rad",
        },
        "maximum_wall_time_s": maximum_wall_time_s,
        "nominal_path_duration_s": NOMINAL_PATH_DURATION_S,
        "mpc_config": asdict(HumanMPCConfig()),
        "frozen_control_settings_changed": False,
        "adaptive_mpc_enabled": False,
        "patient_mismatch_added": False,
        "extra_seed_run": False,
        "new_recovery_added": False,
        "formal_scientific_run": False,
        "git": _git_provenance(),
        "runs": runs,
    }
    write_strict_json(output_dir / "phase5_summary.json", payload)
    print(json.dumps({"output": str(output_dir), "run_count": len(runs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
