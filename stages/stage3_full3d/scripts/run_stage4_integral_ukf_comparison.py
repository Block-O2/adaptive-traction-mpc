from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import COLD_START_TEACHING_DURATION_S
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


ARCHITECTURES = {
    "A": ("architecture_a_minimal", "integral_minimal"),
    "B": ("architecture_b_state_ukf", "integral_state_ukf"),
}


def _write_summary(output_dir: Path) -> None:
    rows = []
    for label, (directory, architecture) in ARCHITECTURES.items():
        for case in architecture_comparison_sensor_cases():
            path = output_dir / directory / f"{case.name}.json"
            if not path.exists():
                continue
            item = json.loads(path.read_text(encoding="utf-8"))
            dynamic = item["dynamic_identifier"]
            geometry = item["geometry_identifier"]
            rows.append(
                {
                    "architecture": label,
                    "architecture_name": architecture,
                    "case": case.name,
                    "completed": item["mechanically_completed_requested_duration"],
                    "completed_duration_s": item["completed_duration_s"],
                    "termination": item["termination_reason"],
                    "dynamic_trustworthy_time_s": dynamic["trustworthy_time_s"],
                    "dynamic_accepted_updates": dynamic["accepted_updates"],
                    "dynamic_rejected_updates": dynamic["rejected_updates"],
                    "dynamic_rank": dynamic["last_attempt"].get("rank", 0),
                    "dynamic_rrqr_rank": dynamic["last_attempt"].get("rrqr_rank", 0),
                    "dynamic_condition_number": dynamic["last_attempt"].get(
                        "condition_number"
                    ),
                    "dynamic_candidate_residual_rms_nms": dynamic["last_attempt"].get(
                        "candidate_residual_rms_nms"
                    ),
                    "dynamic_last_reason": dynamic["last_attempt"].get("reason"),
                    "base_relative_l2_error_percent": dynamic[
                        "relative_l2_error_percent"
                    ],
                    "base_prediction_combined_rmse_nm": dynamic[
                        "god_view_base_model_torque_prediction_combined_rmse_nm"
                    ],
                    "geometry_trustworthy_time_s": geometry["trustworthy_time_s"],
                    "geometry_hip_error_mm": geometry[
                        "hip_pivot_plane_error_mm_god_view"
                    ],
                    "geometry_thigh_error_percent": geometry[
                        "thigh_length_error_percent_god_view"
                    ],
                    "geometry_cuff_error_percent": geometry[
                        "cuff_distance_error_percent_god_view"
                    ],
                    "tracking_combined_rmse_deg": item["tracking"][
                        "combined_rmse_deg"
                    ],
                    "tracking_max_abs_error_deg": item["tracking"][
                        "max_abs_error_deg"
                    ],
                    "peak_cuff_force_n": item[
                        "interaction_metrics_engineering_not_clinical"
                    ]["peak_total_translational_force_n"],
                    "peak_torque_fraction": item["robot"][
                        "peak_unclipped_torque_limit_fraction"
                    ],
                    "max_joint_velocity_deg_s": max(
                        item["robot"]["peak_abs_joint_velocity_deg_s"]
                    ),
                    "events": item["events"],
                    "estimator_mean_ms": item["computational_cost"][
                        "estimator_mean_ms"
                    ],
                    "estimator_p95_ms": item["computational_cost"][
                        "estimator_p95_ms"
                    ],
                    "rollout_wall_time_s": item["computational_cost"][
                        "rollout_wall_time_s"
                    ],
                }
            )
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(
            {
                "evidence_category": "stage4_integral_state_ukf_engineering_comparison",
                "registered_architectures": ARCHITECTURES,
                "registered_cases": [
                    item.name for item in architecture_comparison_sensor_cases()
                ],
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Stage 4 integral identifier: minimal versus state UKF",
        "",
        "Engineering comparison only; no controller, trajectory, plant, gain, or safety setting differs between A and B.",
        "",
        "| arch | case | complete | dyn trust (s) | dyn A/R | base L2 (%) | prediction RMSE (N m) | tracking RMSE (deg) | peak F (N) | estimator mean (ms) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        trusted = (
            "-"
            if row["dynamic_trustworthy_time_s"] is None
            else f'{row["dynamic_trustworthy_time_s"]:.2f}'
        )
        lines.append(
            f'| {row["architecture"]} | {row["case"]} | {row["completed"]} | '
            f'{trusted} | {row["dynamic_accepted_updates"]}/{row["dynamic_rejected_updates"]} | '
            f'{row["base_relative_l2_error_percent"]:.2f} | '
            f'{row["base_prediction_combined_rmse_nm"]:.3f} | '
            f'{row["tracking_combined_rmse_deg"]:.3f} | '
            f'{row["peak_cuff_force_n"]:.2f} | {row["estimator_mean_ms"]:.3f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--architecture", choices=("A", "B", "all"), default="all")
    parser.add_argument("--case", default="all")
    parser.add_argument("--duration-s", type=float, default=COLD_START_TEACHING_DURATION_S)
    args = parser.parse_args()
    cases = {item.name: item for item in architecture_comparison_sensor_cases()}
    selected_cases = list(cases.values()) if args.case == "all" else [cases[args.case]]
    selected_architectures = (
        list(ARCHITECTURES.items())
        if args.architecture == "all"
        else [(args.architecture, ARCHITECTURES[args.architecture])]
    )
    for _, (directory, architecture) in selected_architectures:
        for case in selected_cases:
            summary, trace = run_sensor_realism_case(
                case,
                duration_s=args.duration_s,
                estimator_architecture=architecture,
            )
            save_sensor_case(args.output_dir / directory, summary, trace)
    _write_summary(args.output_dir)


if __name__ == "__main__":
    main()
