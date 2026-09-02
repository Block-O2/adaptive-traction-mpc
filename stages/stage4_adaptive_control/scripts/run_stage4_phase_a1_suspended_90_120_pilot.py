#!/usr/bin/env python3
"""Run the one authorized suspended High-ROM 90/120 engineering pilot."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from run_stage4_phase5_high_rom_system_pilot import (
    DEFAULT_MATRIX,
    HIGH_ROM_HUMAN,
    NOMINAL_PATH_DURATION_S,
    REPO_ROOT,
    TRAJECTORIES,
    _alpha_metrics,
    _filter_metrics,
    _smoothness,
)
from traction_mpc_stage3.coupled import SUSPENDED_SEATED_LIKE_SCENARIO
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.confidence_execution import UnifiedReferenceManager
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.measurement import measurement_case_dict
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
    write_strict_json,
)
from traction_mpc_stage4.sensor_realism import (
    SensorBoundaryStage4Plant,
    run_sensor_realism_case,
)
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase_a1_suspended_90_120_20260902"
)
LYING_RUN = (
    STAGE_ROOT
    / "results"
    / "engineering_validation"
    / "phase5_high_rom_system_pilot_20260902"
    / "knee_high_folding_90_120"
)


def _norm(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return np.linalg.norm(values, axis=1) if len(values) else np.zeros(0)


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"count": 0, "rms": None, "p95": None, "peak": None}
    return {
        "count": int(len(values)),
        "rms": float(np.sqrt(np.mean(values**2))),
        "p95": float(np.percentile(values, 95.0)),
        "peak": float(np.max(values)),
    }


def _rate_distribution(time_s: np.ndarray, vectors: np.ndarray) -> dict[str, Any]:
    time_s = np.asarray(time_s, dtype=float)
    vectors = np.asarray(vectors, dtype=float)
    if len(time_s) < 2:
        return _distribution(np.zeros(0))
    dt = np.diff(time_s)
    if np.any(dt <= 0.0):
        raise RuntimeError("non-increasing diagnostic timestamps")
    return _distribution(np.linalg.norm(np.diff(vectors, axis=0), axis=1) / dt)


class SuspendedCapturePlant(SensorBoundaryStage4Plant):
    """Suspended plant with observation-only command and wrench capture."""

    def __init__(self, human: Any) -> None:
        super().__init__(
            human,
            attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO,
        )
        self.command_records: list[dict[str, Any]] = []
        self.physical_records: list[dict[str, Any]] = []

    def apply_executable_command(self, preview: Any) -> None:
        super().apply_executable_command(preview)
        self.command_records.append(
            {
                "time_s": float(self.data.time),
                "force_total_n": preview.force_total_n.copy(),
                "moment_total_nm": preview.moment_total_nm.copy(),
                "force_position_n": preview.force_position_n.copy(),
                "force_velocity_n": preview.force_velocity_n.copy(),
                "force_allocator_n": preview.force_allocator_n.copy(),
                "moment_orientation_nm": preview.moment_orientation_nm.copy(),
                "moment_angular_velocity_nm": (
                    preview.moment_angular_velocity_nm.copy()
                ),
                "moment_allocator_nm": preview.moment_allocator_nm.copy(),
            }
        )

    def step(self) -> Any:
        observation = super().step()
        self.physical_records.append(
            {
                "time_s": observation.time_s,
                "force_world_n": observation.cuff_force_vector_n.copy(),
                "moment_world_nm": observation.cuff_moment_vector_nm.copy(),
                "bed_force_n": observation.bed_force_n,
                "bed_contact_count": observation.bed_contact_count,
                "human_q_rad": observation.human_q_rad.copy(),
                "human_dq_rad_s": observation.human_dq_rad_s.copy(),
                "robot_q_rad": observation.robot_q_rad.copy(),
                "robot_dq_rad_s": observation.robot_dq_rad_s.copy(),
            }
        )
        return observation


def _records_array(records: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([item[key] for item in records])


def _aligned_force_residual(
    physical_time_s: np.ndarray,
    physical_force_world_n: np.ndarray,
    command_time_s: np.ndarray,
    command_force_world_n: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    indices = np.searchsorted(command_time_s, physical_time_s, side="right") - 1
    indices = np.clip(indices, 0, len(command_time_s) - 1)
    held = command_force_world_n[indices]
    return physical_force_world_n - held, _norm(physical_force_world_n) - _norm(held)


def _run_metrics(
    summary: dict[str, Any],
    trace: dict[str, np.ndarray],
    plant: SuspendedCapturePlant,
) -> dict[str, Any]:
    command_time = _records_array(plant.command_records, "time_s")
    command_force = _records_array(plant.command_records, "force_total_n")
    command_moment = _records_array(plant.command_records, "moment_total_nm")
    physical_time = _records_array(plant.physical_records, "time_s")
    physical_force = _records_array(plant.physical_records, "force_world_n")
    physical_moment = _records_array(plant.physical_records, "moment_world_nm")
    vector_residual, norm_residual = _aligned_force_residual(
        physical_time, physical_force, command_time, command_force
    )
    bed_force = _records_array(plant.physical_records, "bed_force_n")
    bed_count = _records_array(plant.physical_records, "bed_contact_count")
    return {
        "completion": {
            "mechanically_completed_requested_duration": bool(
                summary["mechanically_completed_requested_duration"]
            ),
            "termination_reason": summary["termination_reason"],
            "completed_duration_s": float(summary["completed_duration_s"]),
        },
        "command_force_norm_n": _distribution(_norm(command_force)),
        "physical_cuff_force_norm_n": _distribution(_norm(physical_force)),
        "physical_cuff_moment_norm_nm": _distribution(_norm(physical_moment)),
        "command_to_physical_force_vector_residual_norm_n": _distribution(
            _norm(vector_residual)
        ),
        "command_to_physical_force_norm_residual_n": {
            **_distribution(np.abs(norm_residual)),
            "minimum_signed_n": float(np.min(norm_residual)),
            "maximum_signed_n": float(np.max(norm_residual)),
        },
        "motion": _smoothness(trace),
        "safety_filter": _filter_metrics(
            trace, summary["track_brake_supervisor"]
        ),
        "reference_manager": _alpha_metrics(trace),
        "command_slew": {
            "force_n_per_s": _rate_distribution(command_time, command_force),
            "moment_nm_per_s": _rate_distribution(command_time, command_moment),
            "allocator_force_n_per_s": _rate_distribution(
                command_time,
                _records_array(plant.command_records, "force_allocator_n"),
            ),
            "allocator_moment_nm_per_s": _rate_distribution(
                command_time,
                _records_array(plant.command_records, "moment_allocator_nm"),
            ),
        },
        "physical_rate": {
            "force_n_per_s": _rate_distribution(physical_time, physical_force),
            "moment_nm_per_s": _rate_distribution(
                physical_time, physical_moment
            ),
        },
        "bed_contact_history": {
            "scenario": SUSPENDED_SEATED_LIKE_SCENARIO,
            "human_bed_collision_disabled_from_t0": True,
            "maximum_bed_force_n": float(np.max(bed_force)),
            "bed_force_nonzero_samples": int(np.count_nonzero(bed_force > 0.0)),
            "bed_contact_samples": int(np.count_nonzero(bed_count > 0)),
            "maximum_bed_contact_count": int(np.max(bed_count)),
        },
        "events": summary["events"],
        "runtime": summary["computational_cost"],
    }


def _lying_metrics() -> dict[str, Any]:
    summary = json.loads((LYING_RUN / "raw_summary.json").read_text())
    with np.load(LYING_RUN / "trace.npz", allow_pickle=False) as loaded:
        trace = {name: loaded[name] for name in loaded.files}
    command_force = _norm(trace["executed_command_force_total_n"])
    physical_force = _norm(trace["cuff_force_local_n_god_view"])
    physical_moment = _norm(trace["cuff_moment_local_nm_god_view"])
    command_time = np.asarray(trace["executed_command_time_s"], dtype=float)
    physical_time = np.asarray(trace["time_s"], dtype=float)
    indices = np.searchsorted(command_time, physical_time, side="right") - 1
    indices = np.clip(indices, 0, len(command_time) - 1)
    norm_residual = physical_force - command_force[indices]
    allocation = np.asarray(trace["allocated_wrench_world"], dtype=float)
    return {
        "completion": {
            "mechanically_completed_requested_duration": bool(
                summary["mechanically_completed_requested_duration"]
            ),
            "termination_reason": summary["termination_reason"],
            "completed_duration_s": float(summary["completed_duration_s"]),
        },
        "command_force_norm_n": _distribution(command_force),
        "physical_cuff_force_norm_n": _distribution(physical_force),
        "physical_cuff_moment_norm_nm": _distribution(physical_moment),
        "command_to_physical_force_norm_residual_n": {
            **_distribution(np.abs(norm_residual)),
            "minimum_signed_n": float(np.min(norm_residual)),
            "maximum_signed_n": float(np.max(norm_residual)),
        },
        "motion": _smoothness(trace),
        "safety_filter": _filter_metrics(
            trace, summary["track_brake_supervisor"]
        ),
        "reference_manager": _alpha_metrics(trace),
        "allocator_slew_at_simulation_samples": {
            "force_n_per_s": _rate_distribution(
                physical_time, allocation[:, :3]
            ),
            "moment_nm_per_s": _rate_distribution(
                physical_time, allocation[:, 3:]
            ),
        },
        "physical_rate": {
            "force_n_per_s": _rate_distribution(
                physical_time,
                np.asarray(trace["cuff_force_local_n_god_view"], dtype=float),
            ),
            "moment_nm_per_s": _rate_distribution(
                physical_time,
                np.asarray(trace["cuff_moment_local_nm_god_view"], dtype=float),
            ),
        },
        "bed_contact_history": {
            "scenario": "lying_bed",
            "human_bed_collision_disabled_from_t0": False,
            "maximum_bed_force_n": float(np.max(trace["bed_force_n_god_view"])),
            "bed_force_nonzero_samples": int(
                np.count_nonzero(trace["bed_force_n_god_view"] > 0.0)
            ),
        },
        "events": summary["events"],
        "runtime": summary["computational_cost"],
    }


def _git_provenance() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"phase_a_commit": commit, "expected_phase_a_commit": "542909c"}


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
    trajectory = TRAJECTORIES[0]
    if trajectory.name != "knee_high_folding_90_120":
        raise RuntimeError("authorized 90/120 trajectory ordering drifted")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix, measurement_seed=44104)
    if case.seed != 44104:
        raise RuntimeError("authorized measurement seed drifted")
    maximum_wall_time_s = float(matrix["shared_contract"]["wall_time_limit_s"])
    if maximum_wall_time_s != 32.0:
        raise RuntimeError("frozen wall-time limit drifted")
    allocator = default_engineering_cuff_allocator()
    manager = UnifiedReferenceManager(trajectory.reference, confidence_aware=True)
    supervisor = TrackBrakeSupervisor()
    plant_holder: list[SuspendedCapturePlant] = []

    def plant_factory(human: Any) -> SuspendedCapturePlant:
        plant = SuspendedCapturePlant(human)
        plant_holder.append(plant)
        return plant

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
        result_case_name=(
            "knee_high_folding_90_120__fixed_mpc_phase_a1_suspended"
        ),
        true_human_override=HIGH_ROM_HUMAN,
        true_metadata_override={
            "case": "nominal_high_rom_human_v2_engineering_0_125deg",
            "canonical_human_overwritten": False,
            "engineering_assumption": True,
        },
        reference_fn=trajectory.reference,
        trajectory_label=trajectory.name,
        trajectory_waypoints=trajectory.waypoints,
        plant_factory=plant_factory,
        reference_execution=manager,
        reference_completion_phase_s=NOMINAL_PATH_DURATION_S,
        capture_system_pilot_diagnostics=True,
        track_brake_supervisor=supervisor,
        mpc_factory=lambda: HumanSpaceMPC(cuff_allocator=allocator),
        cuff_allocator=allocator,
        estimator_factory=estimator_factory,
    )
    if len(plant_holder) != 1:
        raise RuntimeError("pilot did not retain exactly one plant")
    expected_beta = nominal_base_parameters(HUMAN)
    beta = np.asarray(trace["dynamic_base_estimate"], dtype=float)
    np.testing.assert_allclose(
        beta, np.broadcast_to(expected_beta, beta.shape), rtol=0.0, atol=1e-12
    )
    plant = plant_holder[0]
    suspended = _run_metrics(summary, trace, plant)
    lying = _lying_metrics()
    command_time = _records_array(plant.command_records, "time_s")
    command_force = _records_array(plant.command_records, "force_total_n")
    if float(np.max(_norm(command_force))) > 200.0 + 1.0e-9:
        raise RuntimeError("independent executable command force gate violated")
    if suspended["bed_contact_history"]["bed_contact_samples"] != 0:
        raise RuntimeError("suspended scenario unexpectedly recorded bed contact")

    output_dir.mkdir(parents=True)
    write_strict_json(output_dir / "raw_summary.json", summary)
    trace.update(
        {
            "diagnostic_command_time_s": command_time,
            "diagnostic_command_force_world_n": command_force,
            "diagnostic_command_moment_world_nm": _records_array(
                plant.command_records, "moment_total_nm"
            ),
            "diagnostic_allocator_force_world_n": _records_array(
                plant.command_records, "force_allocator_n"
            ),
            "diagnostic_allocator_moment_world_nm": _records_array(
                plant.command_records, "moment_allocator_nm"
            ),
            "diagnostic_physical_time_s": _records_array(
                plant.physical_records, "time_s"
            ),
            "diagnostic_physical_force_world_n": _records_array(
                plant.physical_records, "force_world_n"
            ),
            "diagnostic_physical_moment_world_nm": _records_array(
                plant.physical_records, "moment_world_nm"
            ),
            "diagnostic_bed_contact_count": _records_array(
                plant.physical_records, "bed_contact_count"
            ),
        }
    )
    np.savez_compressed(output_dir / "trace.npz", **trace)
    write_strict_json(output_dir / "metrics.json", suspended)
    comparison = {
        "schema_version": "phase_a1_suspended_90_120_comparison_v1",
        "evidence_category": "engineering_pilot_not_formal_or_authoritative",
        "authorized_run_count": 1,
        "controller": "fixed_mpc_prior_only",
        "trajectory": trajectory.name,
        "measurement_case": measurement_case_dict(case),
        "scenario_change_only": True,
        "scenario_change": (
            "Human-bed collisions disabled from initialization; controller, "
            "human, seed, reference, constraints, gains, and solver frozen"
        ),
        "maximum_wall_time_s": maximum_wall_time_s,
        "nominal_path_duration_s": NOMINAL_PATH_DURATION_S,
        "mpc_config": asdict(HumanMPCConfig()),
        "frozen_control_settings_changed": False,
        "scientific_variables_changed": ["engineering_scenario"],
        "adaptive_mpc_enabled": False,
        "extra_seed_run": False,
        "formal_scientific_run": False,
        "git": _git_provenance(),
        "lying_bed_existing": lying,
        "suspended_new": suspended,
    }
    write_strict_json(output_dir / "comparison.json", comparison)
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "termination": suspended["completion"]["termination_reason"],
                "elapsed_s": suspended["completion"]["completed_duration_s"],
                "command_force_peak_n": suspended["command_force_norm_n"]["peak"],
                "physical_force_peak_n": suspended[
                    "physical_cuff_force_norm_n"
                ]["peak"],
                "bed_contact_samples": suspended["bed_contact_history"][
                    "bed_contact_samples"
                ],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
