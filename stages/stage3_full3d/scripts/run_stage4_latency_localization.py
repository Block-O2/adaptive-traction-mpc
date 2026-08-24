from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import COLD_START_TEACHING_DURATION_S
from traction_mpc_stage4.sensor_realism import (
    MeasurementRouting,
    run_sensor_realism_case,
    save_sensor_case,
)


ROUTINGS = {
    "no_delay": MeasurementRouting(),
    "estimator_delay_only": MeasurementRouting(estimator_delay_s=0.010),
    "mpc_state_delay_only": MeasurementRouting(mpc_state_delay_s=0.010),
    "low_level_delay_only": MeasurementRouting(low_level_delay_s=0.010),
    "all_delay": MeasurementRouting(0.010, 0.010, 0.010),
    "all_delay_low_level_extrapolated": MeasurementRouting(
        0.010, 0.010, 0.010, extrapolate_low_level_to_arrival=True
    ),
}


def _registered_human_with_nominal_cuff() -> tuple[object, dict[str, object]]:
    human, metadata = registered_cold_start_perturbed_human()
    unscaled_cuff = human.sleeve_center_m / human.sleeve_center_scale
    adjusted = replace(
        human,
        sleeve_center_scale=HUMAN.sleeve_center_m / unscaled_cuff,
    )
    return adjusted, {
        **metadata,
        "case": "cold_start_perturbed_dynamics_nominal_cuff_placement",
        "latency_localization_single_variable": "measurement_channel_delay",
        "true_cuff_distance_m_god_view": adjusted.sleeve_center_m,
        "population_prior_cuff_distance_m": HUMAN.sleeve_center_m,
    }


def _row(item: dict[str, object]) -> dict[str, object]:
    interaction = item["interaction_metrics_engineering_not_clinical"]
    robot = item["robot"]
    return {
        "case": item["case"],
        "completed": item["mechanically_completed_requested_duration"],
        "duration_s": item["completed_duration_s"],
        "termination": item["termination_reason"],
        "tracking_rmse_deg": item["tracking"]["combined_rmse_deg"],
        "peak_cuff_force_n": interaction["peak_total_translational_force_n"],
        "peak_off_axis_moment_nm": interaction["peak_off_axis_cuff_moment_nm"],
        "rms_parasitic_shear_force_n": interaction["rms_parasitic_shear_force_n"],
        "peak_robot_velocity_deg_s": max(robot["peak_abs_joint_velocity_deg_s"]),
        "peak_robot_torque_fraction": robot["peak_unclipped_torque_limit_fraction"],
        "geometry_trusted_s": item["geometry_identifier"]["trustworthy_time_s"],
        "dynamics_trusted_s": item["dynamic_identifier"]["trustworthy_time_s"],
        "force_gate_events": item["events"]["force_gate_events"],
    }


def _write_aggregate(output_dir: Path) -> None:
    rows = []
    for name in ROUTINGS:
        path = output_dir / f"{name}.json"
        if path.exists():
            rows.append(_row(json.loads(path.read_text(encoding="utf-8"))))
    payload = {
        "evidence_category": "stage4_latency_localization_engineering",
        "architecture": "A_integral_minimal_no_ukf",
        "base_measurement_case": "noise_200hz",
        "trajectory": "frozen_stage4_cold_start_high_flexion_23s",
        "true_cuff_placement": "nominal_population_prior_value",
        "rows": rows,
    }
    (output_dir / "comparison_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Stage 4 10 ms latency localization",
        "",
        "Architecture A, realistic noise, frozen 23 s trajectory, and nominal cuff placement; only routed timestamp delay differs.",
        "",
        "| case | complete | duration (s) | termination | RMSE (deg) | peak F (N) | off-axis M (N m) | peak robot speed (deg/s) |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f'| {row["case"]} | {row["completed"]} | {row["duration_s"]:.3f} | '
            f'{row["termination"]} | {row["tracking_rmse_deg"]:.3f} | '
            f'{row["peak_cuff_force_n"]:.2f} | {row["peak_off_axis_moment_nm"]:.2f} | '
            f'{row["peak_robot_velocity_deg_s"]:.2f} |'
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", choices=tuple(ROUTINGS) + ("all_uncompensated",), default="all_uncompensated")
    parser.add_argument("--duration-s", type=float, default=COLD_START_TEACHING_DURATION_S)
    args = parser.parse_args()
    human, metadata = _registered_human_with_nominal_cuff()
    noise_case = architecture_comparison_sensor_cases()[1]
    names = list(ROUTINGS)[:5] if args.case == "all_uncompensated" else [args.case]
    for name in names:
        summary, trace = run_sensor_realism_case(
            noise_case,
            duration_s=args.duration_s,
            estimator_architecture="integral_minimal",
            measurement_routing=ROUTINGS[name],
            result_case_name=name,
            true_human_override=human,
            true_metadata_override=metadata,
        )
        save_sensor_case(args.output_dir, summary, trace)
    _write_aggregate(args.output_dir)


if __name__ == "__main__":
    main()
