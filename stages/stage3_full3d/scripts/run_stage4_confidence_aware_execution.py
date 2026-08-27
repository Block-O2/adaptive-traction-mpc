#!/usr/bin/env python3
"""Run the single registered fixed-speed versus confidence-aware comparison."""

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
    "confidence_aware_speed": {"confidence_aware": True, "duration_s": 32.0},
}


def _reference_completion_time(trace: dict[str, np.ndarray]) -> float | None:
    phase = np.asarray(trace["reference_phase_time_s"])
    time = np.asarray(trace["time_s"])
    reached = np.flatnonzero(phase >= COLD_START_TEACHING_DURATION_S - 1e-9)
    return None if not len(reached) else float(time[reached[0]])


def _comparison_row(
    mode: str, summary: dict[str, Any], trace: dict[str, np.ndarray]
) -> dict[str, Any]:
    execution = summary["reference_execution"]
    interaction = summary["interaction_metrics_engineering_not_clinical"]
    return {
        "mode": mode,
        "completed_requested_wall_duration": summary[
            "mechanically_completed_requested_duration"
        ],
        "completed_duration_s": summary["completed_duration_s"],
        "termination": summary["termination_reason"],
        "reference_completion_time_s": _reference_completion_time(trace),
        "final_reference_phase_time_s": execution["final_reference_phase_time_s"],
        "mean_speed_scale": execution["mean_speed_scale"],
        "minimum_speed_scale": execution["minimum_observed_speed_scale"],
        "maximum_speed_scale": execution["maximum_observed_speed_scale"],
        "final_combined_confidence": execution["final_status"][
            "combined_confidence"
        ],
        "tracking_combined_rmse_deg": summary["tracking"]["combined_rmse_deg"],
        "tracking_max_abs_error_deg": summary["tracking"]["max_abs_error_deg"],
        "peak_cuff_force_n": interaction["peak_total_translational_force_n"],
        "rms_cuff_force_n": interaction["rms_total_translational_force_n"],
        "peak_sagittal_cuff_moment_nm": interaction[
            "peak_abs_sagittal_cuff_moment_nm"
        ],
        "geometry_accepted_updates": summary["geometry_identifier"][
            "accepted_updates"
        ],
        "dynamic_accepted_updates": summary["dynamic_identifier"][
            "accepted_updates"
        ],
        "events": summary["events"],
        "force_gate_n": summary["force_gate_n"],
        "moment_limit_nm": summary["moment_limit_nm"],
    }


def _write_comparison(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    comparison = {
        "evidence_category": "stage4_confidence_aware_execution_engineering_comparison",
        "formal_experiment": False,
        "single_variable": "reference_time_speed_scale_from_existing_estimator_confidence",
        "registered_modes": REGISTERED_MODES,
        "shared": {
            "plant": "existing_stage4_rigid_cuff_plant",
            "measurement_case": "ideal_200hz",
            "estimator": "integral_minimal_unchanged",
            "mpc": "HumanSpaceMPC_unchanged",
            "trajectory": "stage4_population_prior_cold_start_high_flexion_23s",
            "safety_limits_changed": False,
            "tube_mpc": False,
        },
        "rows": rows,
    }
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 confidence-aware execution comparison",
        "",
        "Engineering comparison only. Estimator, MPC, plant, sensing, gains, and safety limits are shared.",
        "",
        "| mode | termination | reference complete (s) | mean/min/max speed | tracking RMSE (deg) | peak force (N) | peak sagittal moment (N m) | geom/dyn updates |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        completion = (
            "-"
            if row["reference_completion_time_s"] is None
            else f'{row["reference_completion_time_s"]:.3f}'
        )
        lines.append(
            f'| {row["mode"]} | {row["termination"]} | {completion} | '
            f'{row["mean_speed_scale"]:.3f}/{row["minimum_speed_scale"]:.3f}/'
            f'{row["maximum_speed_scale"]:.3f} | '
            f'{row["tracking_combined_rmse_deg"]:.3f} | '
            f'{row["peak_cuff_force_n"]:.2f} | '
            f'{row["peak_sagittal_cuff_moment_nm"]:.2f} | '
            f'{row["geometry_accepted_updates"]}/{row["dynamic_accepted_updates"]} |'
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
