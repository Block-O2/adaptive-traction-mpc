from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path

from traction_mpc_stage3.coupled import SLEEVE_HALF_LENGTH_M
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import COLD_START_TEACHING_DURATION_S
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


PLACEMENTS_M = {
    "cuff_proximal_20mm": HUMAN.sleeve_center_m - 0.020,
    "cuff_nominal": HUMAN.sleeve_center_m,
    "cuff_distal_20mm": HUMAN.sleeve_center_m + 0.020,
}


def _human_at_cuff_distance(distance_m: float, name: str) -> tuple[object, dict[str, object]]:
    human, metadata = registered_cold_start_perturbed_human()
    unscaled_cuff = human.sleeve_center_m / human.sleeve_center_scale
    adjusted = replace(human, sleeve_center_scale=distance_m / unscaled_cuff)
    return adjusted, {
        **metadata,
        "case": name,
        "cuff_placement_sensitivity_single_variable": True,
        "true_knee_to_cuff_vector_in_cuff_frame_m_god_view": [distance_m, 0.0],
        "true_cuff_distance_m_god_view": distance_m,
        "true_fraction_of_shank_length_god_view": distance_m / adjusted.shank_length_m,
        "controller_population_prior_cuff_distance_m": HUMAN.sleeve_center_m,
    }


def _write_aggregate(output_dir: Path) -> None:
    rows = []
    for name, distance in PLACEMENTS_M.items():
        path = output_dir / f"{name}.json"
        if not path.exists():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        geometry = item["geometry_identifier"]
        estimate = geometry["final_estimate"]
        estimated_vector = estimate[3:5]
        interaction = item["interaction_metrics_engineering_not_clinical"]
        rows.append(
            {
                "case": name,
                "true_knee_to_cuff_vector_m_god_view": [distance, 0.0],
                "estimated_knee_to_cuff_vector_m": estimated_vector,
                "true_distance_m_god_view": distance,
                "estimated_distance_m": math.hypot(*estimated_vector),
                "geometry_trusted_s": geometry["trustworthy_time_s"],
                "geometry_last_attempt": geometry["last_attempt"],
                "completed": item["mechanically_completed_requested_duration"],
                "duration_s": item["completed_duration_s"],
                "termination": item["termination_reason"],
                "tracking_rmse_deg": item["tracking"]["combined_rmse_deg"],
                "peak_cuff_force_n": interaction["peak_total_translational_force_n"],
                "peak_sagittal_moment_nm": interaction["peak_abs_sagittal_cuff_moment_nm"],
                "peak_off_axis_moment_nm": interaction["peak_off_axis_cuff_moment_nm"],
                "peak_robot_torque_fraction": item["robot"]["peak_unclipped_torque_limit_fraction"],
                "events": item["events"],
            }
        )
    payload = {
        "evidence_category": "stage4_effective_cuff_location_sensitivity_engineering",
        "architecture": "A_integral_minimal_no_ukf",
        "trajectory": "frozen_stage4_cold_start_high_flexion_23s",
        "measurement_case": "noise_200hz_no_delay",
        "geometry_audit": {
            "visual_sleeve_full_length_m": 2.0 * SLEEVE_HALF_LENGTH_M,
            "visual_geom_collision_enabled": False,
            "physical_attachment_frame": "sleeve_attach_site at sc along the shank body x axis",
            "rigid_attachment": "six-constraint MuJoCo weld at the single attachment site",
            "nominal_knee_to_cuff_effective_distance_sc_m": HUMAN.sleeve_center_m,
            "nominal_shank_length_m": HUMAN.shank_length_m,
            "visual_length_changes_rigid_weld_mechanics": False,
        },
        "same_population_prior_for_all_cases": True,
        "rows": rows,
    }
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 effective cuff-location sensitivity",
        "",
        "The 80 mm collision-disabled cylinder is visual only. Mechanics use one rigid weld frame at `sc`; all three runs keep the same nominal controller prior.",
        "",
        "| case | true sc (m) | estimated sc (m) | trusted (s) | complete | RMSE (deg) | peak F (N) | peak cuff M (N m) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        trusted = "-" if row["geometry_trusted_s"] is None else f'{row["geometry_trusted_s"]:.2f}'
        peak_moment = max(row["peak_sagittal_moment_nm"], row["peak_off_axis_moment_nm"])
        lines.append(
            f'| {row["case"]} | {row["true_distance_m_god_view"]:.6f} | '
            f'{row["estimated_distance_m"]:.6f} | {trusted} | {row["completed"]} | '
            f'{row["tracking_rmse_deg"]:.3f} | {row["peak_cuff_force_n"]:.2f} | '
            f'{peak_moment:.2f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", choices=tuple(PLACEMENTS_M) + ("all",), default="all")
    parser.add_argument("--duration-s", type=float, default=COLD_START_TEACHING_DURATION_S)
    args = parser.parse_args()
    noise_case = architecture_comparison_sensor_cases()[1]
    names = list(PLACEMENTS_M) if args.case == "all" else [args.case]
    for name in names:
        human, metadata = _human_at_cuff_distance(PLACEMENTS_M[name], name)
        summary, trace = run_sensor_realism_case(
            noise_case,
            duration_s=args.duration_s,
            estimator_architecture="integral_minimal",
            result_case_name=name,
            true_human_override=human,
            true_metadata_override=metadata,
        )
        save_sensor_case(args.output_dir, summary, trace)
    _write_aggregate(args.output_dir)


if __name__ == "__main__":
    main()
