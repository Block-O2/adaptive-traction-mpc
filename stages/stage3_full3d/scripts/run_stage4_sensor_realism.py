from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.reference import COLD_START_TEACHING_DURATION_S
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


def _write_compact_summary(output_dir: Path) -> None:
    rows = []
    for case in sensor_realism_cases():
        path = output_dir / f"{case.name}.json"
        if not path.exists():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        geometry = item["geometry_identifier"]
        dynamics = item["dynamic_identifier"]
        tracking = item["tracking"]
        interaction = item["interaction_metrics_engineering_not_clinical"]
        robot = item["robot"]
        rows.append(
            {
                "case": case.name,
                "completed": item["mechanically_completed_requested_duration"],
                "termination": item["termination_reason"],
                "geometry_trusted_s": geometry["trustworthy_time_s"],
                "geometry_hip_error_mm": geometry["hip_pivot_plane_error_mm_god_view"],
                "geometry_thigh_error_percent": geometry["thigh_length_error_percent_god_view"],
                "geometry_cuff_error_percent": geometry["cuff_distance_error_percent_god_view"],
                "dynamic_trusted_s": dynamics["trustworthy_time_s"],
                "dynamic_relative_l2_error_percent": dynamics["relative_l2_error_percent"],
                "geometry_accepted_rejected": [geometry["accepted_updates"], geometry["rejected_updates"]],
                "dynamic_accepted_rejected": [dynamics["accepted_updates"], dynamics["rejected_updates"]],
                "tracking_combined_rmse_deg": tracking["combined_rmse_deg"],
                "tracking_max_abs_error_deg": tracking["max_abs_error_deg"],
                "peak_cuff_force_n": interaction["peak_total_translational_force_n"],
                "rms_parasitic_shear_force_n": interaction["rms_parasitic_shear_force_n"],
                "peak_cuff_moment_nm": interaction["peak_abs_sagittal_cuff_moment_nm"],
                "peak_torque_fraction": robot["peak_unclipped_torque_limit_fraction"],
                "max_joint_velocity_deg_s": max(robot["peak_abs_joint_velocity_deg_s"]),
                "events": item["events"],
            }
        )
    (output_dir / "suite_summary.json").write_text(
        json.dumps({"cases": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 sensor-realism engineering summary",
        "",
        "These deterministic perturbations are engineering assumptions, not measured CR12 specifications.",
        "All non-ideal cases use the same 8 Hz causal low-pass and 120 ms local-quadratic derivative window.",
        "No F/T bias is estimated or subtracted, and MuJoCo bed/contact truth is not fed to the estimator.",
        "",
        "| case | complete | geom trust (s) | dyn trust (s) | dyn L2 err (%) | track RMSE (deg) | peak F (N) | torque frac |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        geom = "-" if row["geometry_trusted_s"] is None else f'{row["geometry_trusted_s"]:.2f}'
        dyn = "-" if row["dynamic_trusted_s"] is None else f'{row["dynamic_trusted_s"]:.2f}'
        lines.append(
            f'| {row["case"]} | {row["completed"]} | {geom} | {dyn} | '
            f'{row["dynamic_relative_l2_error_percent"]:.2f} | '
            f'{row["tracking_combined_rmse_deg"]:.3f} | {row["peak_cuff_force_n"]:.2f} | '
            f'{row["peak_torque_fraction"]:.3f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--case",
        default="all",
        help="One registered case name or 'all'.",
    )
    parser.add_argument("--duration-s", type=float, default=COLD_START_TEACHING_DURATION_S)
    args = parser.parse_args()
    cases = {item.name: item for item in sensor_realism_cases()}
    selected = list(cases.values()) if args.case == "all" else [cases[args.case]]
    for case in selected:
        summary, trace = run_sensor_realism_case(case, duration_s=args.duration_s)
        save_sensor_case(args.output_dir, summary, trace)
    _write_compact_summary(args.output_dir)


if __name__ == "__main__":
    main()
