"""Reproduce the rejected explicit-penalty cuff diagnostic only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.distributed_cuff import (
    DistributedCuffConfig,
    DistributedCuffStage4Plant,
    cuff_length_is_geometrically_supported,
)
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


LENGTHS_M = (0.060, 0.080, 0.100, 0.120)


def _case_name(length_m: float) -> str:
    return f"distributed_cuff_{round(1000.0 * length_m):03d}mm"


def _comparison_row(item: dict[str, object]) -> dict[str, object]:
    cuff = item["cuff_plant"]
    distribution = cuff["station_force_distribution_engineering"]
    relative = cuff["relative_motion"]
    interaction = item["interaction_metrics_engineering_not_clinical"]
    geometry = item["geometry_identifier"]
    dynamics = item["dynamic_identifier"]
    return {
        "case": item["case"],
        "cuff_length_mm": 1000.0 * cuff["config"]["cuff_length_m"],
        "completed": item["mechanically_completed_requested_duration"],
        "duration_s": item["completed_duration_s"],
        "termination": item["termination_reason"],
        "tracking_combined_rmse_deg": item["tracking"]["combined_rmse_deg"],
        "tracking_max_abs_error_deg": item["tracking"]["max_abs_error_deg"],
        "peak_resultant_force_n": interaction["peak_total_translational_force_n"],
        "peak_sagittal_moment_nm": interaction["peak_abs_sagittal_cuff_moment_nm"],
        "peak_off_axis_moment_nm": interaction["peak_off_axis_cuff_moment_nm"],
        "station_offsets_m": distribution["station_offsets_m"],
        "peak_station_force_norm_n": distribution["peak_force_norm_n"],
        "rms_station_force_norm_n": distribution["rms_force_norm_n"],
        "proximal_peak_force_n": distribution["proximal_station_peak_force_n"],
        "distal_peak_force_n": distribution["distal_station_peak_force_n"],
        "peak_center_translation_mm": relative["peak_center_translation_mm"],
        "peak_station_translation_mm": relative["peak_station_translation_mm"],
        "peak_relative_rotation_deg": relative["peak_cuff_shank_rotation_deg"],
        "peak_robot_torque_fraction": item["robot"]["peak_unclipped_torque_limit_fraction"],
        "peak_robot_velocity_deg_s": max(item["robot"]["peak_abs_joint_velocity_deg_s"]),
        "geometry_trusted_s": geometry["trustworthy_time_s"],
        "geometry_accepted_rejected": [geometry["accepted_updates"], geometry["rejected_updates"]],
        "geometry_rank": geometry["last_attempt"].get("rank"),
        "geometry_condition_number": geometry["last_attempt"].get("condition_number"),
        "dynamics_trusted_s": dynamics["trustworthy_time_s"],
        "dynamics_accepted_rejected": [dynamics["accepted_updates"], dynamics["rejected_updates"]],
        "dynamics_rank": dynamics["last_attempt"].get("rank"),
        "dynamics_condition_number": dynamics["last_attempt"].get("condition_number"),
        "dynamics_prediction_rmse_nm_god_view": dynamics[
            "god_view_base_model_torque_prediction_combined_rmse_nm"
        ],
        "events": item["events"],
    }


def _nominal_comparison(
    baseline: dict[str, object], finite: dict[str, object]
) -> dict[str, object]:
    base_interaction = baseline["interaction_metrics_engineering_not_clinical"]
    finite_interaction = finite["interaction_metrics_engineering_not_clinical"]
    base_velocity = max(baseline["robot"]["peak_abs_joint_velocity_deg_s"])
    finite_velocity = max(finite["robot"]["peak_abs_joint_velocity_deg_s"])
    metrics = {
        "tracking_combined_rmse_deg": (
            baseline["tracking"]["combined_rmse_deg"],
            finite["tracking"]["combined_rmse_deg"],
        ),
        "peak_resultant_force_n": (
            base_interaction["peak_total_translational_force_n"],
            finite_interaction["peak_total_translational_force_n"],
        ),
        "peak_sagittal_moment_nm": (
            base_interaction["peak_abs_sagittal_cuff_moment_nm"],
            finite_interaction["peak_abs_sagittal_cuff_moment_nm"],
        ),
        "peak_off_axis_moment_nm": (
            base_interaction["peak_off_axis_cuff_moment_nm"],
            finite_interaction["peak_off_axis_cuff_moment_nm"],
        ),
        "peak_robot_torque_fraction": (
            baseline["robot"]["peak_unclipped_torque_limit_fraction"],
            finite["robot"]["peak_unclipped_torque_limit_fraction"],
        ),
        "peak_robot_velocity_deg_s": (base_velocity, finite_velocity),
    }
    return {
        "single_weld_case": baseline["case"],
        "finite_cuff_case": finite["case"],
        "single_weld_completed": baseline["mechanically_completed_requested_duration"],
        "finite_cuff_completed": finite["mechanically_completed_requested_duration"],
        "single_weld_events": baseline["events"],
        "finite_cuff_events": finite["events"],
        "metrics": {
            name: {
                "single_weld": values[0],
                "finite_cuff": values[1],
                "absolute_delta": values[1] - values[0],
                "relative_delta_percent": 100.0 * (values[1] - values[0]) / max(abs(values[0]), 1e-12),
            }
            for name, values in metrics.items()
        },
    }


def _write_summary(output_dir: Path, baseline_path: Path) -> None:
    rows = []
    cases = {}
    for length in LENGTHS_M:
        name = _case_name(length)
        path = output_dir / f"{name}.json"
        if path.exists():
            item = json.loads(path.read_text(encoding="utf-8"))
            cases[name] = item
            rows.append(_comparison_row(item))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    nominal_name = _case_name(0.080)
    nominal = (
        _nominal_comparison(baseline, cases[nominal_name])
        if nominal_name in cases
        else None
    )
    payload = {
        "evidence_category": "stage4_finite_distributed_cuff_engineering",
        "architecture": "A_integral_minimal_no_ukf",
        "plant_single_variable": "cuff_to_shank_mechanics_and_registered_cuff_length",
        "robot_to_cuff_connection": "rigid",
        "station_count": 4,
        "station_direct_moments": False,
        "measurement_to_estimator_controller": "resultant_actual_cuff_wrench_only",
        "measurement_case": "noise_200hz_no_delay",
        "human_case": "cold_start_perturbed",
        "trajectory": "stage4_continuous_c2_high_flexion_23s",
        "lengths_mm": [1000.0 * item for item in LENGTHS_M],
        "length_160mm_excluded_reason": (
            "with fixed sc it extends beyond the modeled distal shank; 100 mm is inserted so 60/80/100/120 mm remain fully supported"
        ),
        "nominal_single_weld_comparison": nominal,
        "rows": rows,
        "hardware_claim": False,
    }
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 finite distributed rigid-cuff engineering sweep",
        "",
        "Four soft translational connect stations, no direct station moments, Architecture A unchanged.",
        "",
        "| Lc (mm) | complete | RMSE (deg) | peak F (N) | sagittal/off-axis M (N m) | prox/distal peak (N) | center/station slip (mm) | rotation (deg) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f'| {row["cuff_length_mm"]:.0f} | {row["completed"]} | '
            f'{row["tracking_combined_rmse_deg"]:.3f} | {row["peak_resultant_force_n"]:.2f} | '
            f'{row["peak_sagittal_moment_nm"]:.2f}/{row["peak_off_axis_moment_nm"]:.2f} | '
            f'{row["proximal_peak_force_n"]:.1f}/{row["distal_peak_force_n"]:.1f} | '
            f'{row["peak_center_translation_mm"]:.3f}/{row["peak_station_translation_mm"]:.3f} | '
            f'{row["peak_relative_rotation_deg"]:.3f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", choices=("all",) + tuple(_case_name(item) for item in LENGTHS_M), default="all")
    parser.add_argument("--duration-s", type=float, default=CONTINUOUS_TEACHING_DURATION_S)
    parser.add_argument(
        "--single-weld-baseline",
        type=Path,
        default=Path("results/stage4_continuous_trajectory_engineering/continuous_perturbed_human_one_shot.json"),
    )
    args = parser.parse_args()
    true_human, _ = registered_cold_start_perturbed_human()
    selected = LENGTHS_M if args.case == "all" else (
        next(item for item in LENGTHS_M if _case_name(item) == args.case),
    )
    noise_case = architecture_comparison_sensor_cases()[1]
    for length in selected:
        if not cuff_length_is_geometrically_supported(true_human, length):
            raise ValueError(f"cuff length {length} m extends beyond the modeled shank")
        config = DistributedCuffConfig(cuff_length_m=length)
        summary, trace = run_sensor_realism_case(
            noise_case,
            duration_s=args.duration_s,
            estimator_architecture="integral_minimal",
            result_case_name=_case_name(length),
            reference_fn=continuous_teaching_reference,
            trajectory_label="stage4_continuous_c2_high_flexion_23s",
            trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
            plant_factory=lambda human, config=config: DistributedCuffStage4Plant(
                human, config
            ),
        )
        save_sensor_case(args.output_dir, summary, trace)
    _write_summary(args.output_dir, args.single_weld_baseline)


if __name__ == "__main__":
    main()
