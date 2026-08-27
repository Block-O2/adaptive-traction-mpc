#!/usr/bin/env python3
"""Run one fixed-speed versus split-confidence adaptive-speed comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.reference import (
    COLD_START_TEACHING_DURATION_S,
    cold_start_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


REGISTERED_MODES = {
    "fixed_speed": {"confidence_aware": False, "duration_s": 23.0},
    "adaptive_speed": {"confidence_aware": True, "duration_s": 32.0},
}


def _first_time(time: np.ndarray, signal: np.ndarray) -> float | None:
    selected = np.flatnonzero(np.asarray(signal) >= 1.0 - 1e-12)
    return None if not len(selected) else float(np.asarray(time)[selected[0]])


def _phase_at_time(
    time: np.ndarray, phase: np.ndarray, event_time_s: float | None
) -> float | None:
    if event_time_s is None:
        return None
    return float(np.interp(float(event_time_s), time, phase))


def _phase_normalized_tracking_rmse_deg(
    phase: np.ndarray, tracking_error_deg: np.ndarray
) -> tuple[float, list[float]]:
    """Compare tracking on a common reference-phase grid, not wall time."""

    phase_end = min(float(phase[-1]), COLD_START_TEACHING_DURATION_S)
    grid = np.linspace(0.0, phase_end, 2301)
    interpolated = np.column_stack(
        [np.interp(grid, phase, tracking_error_deg[:, joint]) for joint in range(2)]
    )
    per_joint = np.sqrt(np.mean(interpolated**2, axis=0))
    return float(np.sqrt(np.mean(interpolated**2))), per_joint.tolist()


def _peak_with_phase(
    time: np.ndarray, phase: np.ndarray, signal: np.ndarray
) -> dict[str, float]:
    index = int(np.argmax(signal))
    return {
        "value": float(signal[index]),
        "wall_time_s": float(time[index]),
        "reference_phase_s": float(phase[index]),
    }


def _comparison_row(
    mode: str, summary: dict[str, Any], trace: dict[str, np.ndarray]
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"])
    phase = np.asarray(trace["reference_phase_time_s"])
    speed = np.asarray(trace["reference_speed_scale"])
    model_raw = np.asarray(trace["combined_model_confidence_raw"])
    information = np.asarray(trace["combined_information_confidence"])
    execution_high = np.asarray(trace["execution_confidence_high"])
    tracking_error_deg = np.asarray(trace["tracking_error_deg_god_view"])
    cuff_wrench = np.asarray(trace["cuff_wrench_local_god_view"])
    force_norm = np.linalg.norm(cuff_wrench[:, :3], axis=1)
    moment_norm = np.linalg.norm(cuff_wrench[:, 3:], axis=1)
    phase_tracking_rmse, phase_tracking_per_joint = (
        _phase_normalized_tracking_rmse_deg(phase, tracking_error_deg)
    )
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    geometry_trusted_time = summary["geometry_identifier"]["trustworthy_time_s"]
    dynamic_trusted_time = summary["dynamic_identifier"]["trustworthy_time_s"]
    return {
        "mode": mode,
        "completed_requested_wall_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "completed_duration_s": summary["completed_duration_s"],
        "termination": summary["termination_reason"],
        "reference_completion_time_s": _first_time(
            time, phase >= COLD_START_TEACHING_DURATION_S - 1e-9
        ),
        "final_reference_phase_time_s": float(phase[-1]),
        "mean_speed_scale": float(np.mean(speed)),
        "minimum_speed_scale": float(np.min(speed)),
        "maximum_speed_scale": float(np.max(speed)),
        "nominal_speed_fraction": float(np.mean(np.isclose(speed, 1.0))),
        "minimum_speed_fraction": float(np.mean(np.isclose(speed, 0.5))),
        "model_confidence_high_fraction": float(np.mean(model_raw >= 1.0)),
        "information_confidence_high_fraction": float(
            np.mean(information >= 1.0)
        ),
        "execution_confidence_high_fraction": float(
            np.mean(execution_high >= 1.0)
        ),
        "first_model_confidence_high_time_s": _first_time(time, model_raw),
        "first_execution_confidence_high_time_s": _first_time(
            time, execution_high
        ),
        "tracking_combined_rmse_deg": summary["tracking"]["combined_rmse_deg"],
        "phase_normalized_tracking_combined_rmse_deg": phase_tracking_rmse,
        "phase_normalized_tracking_per_joint_rmse_deg": phase_tracking_per_joint,
        "tracking_max_abs_error_deg": summary["tracking"]["max_abs_error_deg"],
        "peak_cuff_force_n": interaction["peak_total_translational_force_n"],
        "peak_cuff_force": _peak_with_phase(time, phase, force_norm),
        "rms_cuff_force_n": interaction["rms_total_translational_force_n"],
        "peak_sagittal_cuff_moment_nm": interaction[
            "peak_abs_sagittal_cuff_moment_nm"
        ],
        "peak_cuff_moment": _peak_with_phase(time, phase, moment_norm),
        "geometry_estimator_trusted_time_s": geometry_trusted_time,
        "geometry_estimator_trusted_reference_phase_s": _phase_at_time(
            time, phase, geometry_trusted_time
        ),
        "dynamic_estimator_trusted_time_s": dynamic_trusted_time,
        "dynamic_estimator_trusted_reference_phase_s": _phase_at_time(
            time, phase, dynamic_trusted_time
        ),
        "geometry_accepted_updates": summary["geometry_identifier"][
            "accepted_updates"
        ],
        "geometry_rejected_updates": summary["geometry_identifier"][
            "rejected_updates"
        ],
        "dynamic_accepted_updates": summary["dynamic_identifier"][
            "accepted_updates"
        ],
        "dynamic_rejected_updates": summary["dynamic_identifier"][
            "rejected_updates"
        ],
        "events": summary["events"],
        "force_gate_n": summary["force_gate_n"],
        "moment_limit_nm": summary["moment_limit_nm"],
    }


def _write_comparison(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    comparison = {
        "evidence_category": "stage4_split_confidence_execution_engineering_comparison",
        "formal_experiment": False,
        "single_variable": "reference_speed_from_filtered_hysteretic_current_model_confidence",
        "registered_modes": REGISTERED_MODES,
        "shared": {
            "plant": "existing_stage4_rigid_cuff_resultant_wrench_plant",
            "measurement_case": "ideal_200hz",
            "estimator": "integral_minimal_unchanged",
            "mpc": "HumanSpaceMPC_unchanged",
            "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
            "safety_limits_changed": False,
            "tube_mpc": False,
        },
        "confidence_contract": {
            "speed_input": "current_last_valid_model_confidence_only",
            "information_confidence_affects_speed": False,
            "rejected_candidate_invalidates_current_model": False,
            "filter_and_hysteresis": ReferenceExecutionLayer(
                cold_start_teaching_reference, confidence_aware=True
            ).config.as_dict(),
        },
        "rows": rows,
    }
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 split-confidence execution comparison",
        "",
        "Engineering comparison only; estimator, MPC, plant, sensing, gains, and safety limits are shared.",
        "",
        "| mode | termination | reference complete (s) | phase RMSE (deg) | peak force @ phase | peak moment @ phase | geometry trusted t/phase | dynamics trusted t/phase | safety events |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        completion = (
            "-"
            if row["reference_completion_time_s"] is None
            else f'{row["reference_completion_time_s"]:.3f}'
        )
        lines.append(
            f'| {row["mode"]} | {row["termination"]} | {completion} | '
            f'{row["phase_normalized_tracking_combined_rmse_deg"]:.3f} | '
            f'{row["peak_cuff_force"]["value"]:.2f} N @ '
            f'{row["peak_cuff_force"]["reference_phase_s"]:.3f} s | '
            f'{row["peak_cuff_moment"]["value"]:.2f} Nm @ '
            f'{row["peak_cuff_moment"]["reference_phase_s"]:.3f} s | '
            f'{row["geometry_estimator_trusted_time_s"]:.3f}/'
            f'{row["geometry_estimator_trusted_reference_phase_s"]:.3f} s | '
            f'{row["dynamic_estimator_trusted_time_s"]:.3f}/'
            f'{row["dynamic_estimator_trusted_reference_phase_s"]:.3f} s | '
            f'{row["events"]} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ideal_case = sensor_realism_cases()[0]
    rows = []
    for mode, settings in REGISTERED_MODES.items():
        execution = ReferenceExecutionLayer(
            cold_start_teaching_reference,
            confidence_aware=bool(settings["confidence_aware"]),
        )
        summary, trace = run_sensor_realism_case(
            ideal_case,
            duration_s=float(settings["duration_s"]),
            estimator_architecture="integral_minimal",
            result_case_name=mode,
            reference_execution=execution,
        )
        save_sensor_case(args.output_dir, summary, trace)
        rows.append(_comparison_row(mode, summary, trace))
    if rows[0]["force_gate_n"] != rows[1]["force_gate_n"]:
        raise RuntimeError("comparison changed the cuff force safety limit")
    if rows[0]["moment_limit_nm"] != rows[1]["moment_limit_nm"]:
        raise RuntimeError("comparison changed the cuff moment safety limit")
    _write_comparison(args.output_dir, rows)


if __name__ == "__main__":
    main()
