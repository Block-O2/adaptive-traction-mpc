from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_DURATION_S,
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case, save_sensor_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--duration-s", type=float, default=CONTINUOUS_TEACHING_DURATION_S
    )
    args = parser.parse_args()
    case = architecture_comparison_sensor_cases()[1]
    summary, trace = run_sensor_realism_case(
        case,
        duration_s=args.duration_s,
        estimator_architecture="integral_minimal",
        result_case_name="continuous_perturbed_human_one_shot",
        reference_fn=continuous_teaching_reference,
        trajectory_label="stage4_continuous_c2_high_flexion_23s",
        trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
    )
    save_sensor_case(args.output_dir, summary, trace)
    compact = {
        "evidence_category": "stage4_continuous_trajectory_engineering",
        "architecture": "A_integral_minimal_no_ukf",
        "measurement_case": case.name,
        "trajectory_definition": summary["trajectory_waypoints"],
        "note": "Internal definition knots are non-stopping C2 spline pass-through points.",
        "completed": summary["mechanically_completed_requested_duration"],
        "duration_s": summary["completed_duration_s"],
        "termination": summary["termination_reason"],
        "geometry_identifier": summary["geometry_identifier"],
        "dynamic_identifier": summary["dynamic_identifier"],
        "tracking": summary["tracking"],
        "interaction": summary["interaction_metrics_engineering_not_clinical"],
        "robot": summary["robot"],
        "events": summary["events"],
    }
    (args.output_dir / "comparison_summary.json").write_text(
        json.dumps(compact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(
        "# Stage 4 continuous teaching trajectory\n\n"
        "One Architecture-A perturbed-Human engineering rollout using the C2 continuous 23 s reference. "
        "See `comparison_summary.json` for the complete registered metrics.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
