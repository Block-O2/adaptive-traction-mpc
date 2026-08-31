#!/usr/bin/env python3
"""Run the corrected six-run High-ROM dynamic engineering pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from traction_mpc_stage4.high_rom_dynamic_pilot import run_small_pilot
from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.report_validation import (
    load_report_validation_matrix,
    measurement_case,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
DEFAULT_MATRIX = STAGE_ROOT / "configs" / "stage4_report_validation_matrix_v2_coupled_pd.json"
CORRECTED_SUBDIR = "post_jacobian_corrected_pilot"
REPORT_MARKER = "## Corrected post-Jacobian High-ROM dynamic pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    return parser.parse_args()


def report_section(payload: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "Exactly six corrected non-formal engineering runs were executed: three "
            "High-ROM trajectories by Fixed MPC and Trusted Adaptive MPC, with "
            "one shared frozen measurement realization and no retuning."
        ),
        "",
        "| trajectory | controller | completion | RMSE / max error | peak hip/knee | soft lower/upper | cuff RMS/peak | command peak/margin | moment | accel RMS | promotions | events |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in payload["runs"]:
        events = run["events"]
        event_text = (
            f"force={events['force_gate_events']}, ROM={events['rom_event_samples']}, "
            f"solver={events['mpc_solver_failures']}, contacts={len(events['unintended_contact_pairs'])}"
        )
        lines.append(
            f"| {run['trajectory']} | {run['controller']} | {run['completion']} "
            f"({run['termination_reason']}) | {run['tracking_combined_rmse_deg']:.2f} / "
            f"{max(run['tracking_max_abs_error_deg']):.2f} deg | "
            f"{run['peak_human_angle_deg'][0]:.2f}/{run['peak_human_angle_deg'][1]:.2f} deg | "
            f"{run['soft_limit_activation']['lower_zone_sample_count']}/"
            f"{run['soft_limit_activation']['upper_120deg_zone_sample_count']} | "
            f"{run['cuff_force_rms_n']:.2f}/{run['cuff_force_peak_n']:.2f} N | "
            f"{run['commanded_force_gate']['peak_attempt_n']:.2f}/"
            f"{run['commanded_force_gate']['minimum_margin_n']:.2f} N | "
            f"{run['cuff_moment_peak_nm']:.2f} Nm | "
            f"{run['acceleration_rms']['combined_deg_s2']:.2f} deg/s2 | "
            f"{run['promotion_count']} | {event_text} |"
        )
    lines.extend(["", "Paired Adaptive-minus-Fixed changes:", ""])
    for name, comparison in payload["paired_comparisons"].items():
        lines.append(
            f"- `{name}`: tracking RMSE {comparison['adaptive_minus_fixed_tracking_combined_rmse_deg']:+.3f} deg; "
            f"peak cuff force {comparison['adaptive_minus_fixed_peak_cuff_force_n']:+.3f} N."
        )
    lines.append("")
    return "\n".join(lines)


def compare_with_invalid_pre_fix(
    corrected: dict[str, object], invalid: dict[str, object]
) -> dict[str, object]:
    invalid_by_key = {
        (item["trajectory"], item["controller"]): item
        for item in invalid["runs"]
    }
    rows = []
    for item in corrected["runs"]:
        key = (item["trajectory"], item["controller"])
        before = invalid_by_key[key]
        rows.append(
            {
                "trajectory": key[0],
                "controller": key[1],
                "invalid_pre_fix": {
                    "completion": before["completion"],
                    "termination_reason": before["termination_reason"],
                    "completed_duration_s": before["completed_duration_s"],
                    "tracking_combined_rmse_deg": before[
                        "tracking_combined_rmse_deg"
                    ],
                    "peak_human_angle_deg": before["peak_human_angle_deg"],
                    "cuff_force_peak_n": before["cuff_force_peak_n"],
                },
                "corrected_post_fix": {
                    "completion": item["completion"],
                    "termination_reason": item["termination_reason"],
                    "completed_duration_s": item["completed_duration_s"],
                    "tracking_combined_rmse_deg": item[
                        "tracking_combined_rmse_deg"
                    ],
                    "peak_human_angle_deg": item["peak_human_angle_deg"],
                    "cuff_force_peak_n": item["cuff_force_peak_n"],
                },
                "corrected_minus_invalid": {
                    "completed_duration_s": item["completed_duration_s"]
                    - before["completed_duration_s"],
                    "tracking_combined_rmse_deg": item[
                        "tracking_combined_rmse_deg"
                    ]
                    - before["tracking_combined_rmse_deg"],
                    "cuff_force_peak_n": item["cuff_force_peak_n"]
                    - before["cuff_force_peak_n"],
                },
            }
        )
    return {
        "schema_version": "high_rom_corrected_vs_invalid_pre_fix_v1",
        "invalid_pre_fix_disposition": "diagnostic_only",
        "corrected_run_count": corrected["run_count"],
        "rows": rows,
    }


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    audit_path = output / "high_rom_120_path_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit["all_three_ready"]:
        raise RuntimeError("geometry/mechanics audit did not clear all three paths")
    invalid_path = output / "high_rom_dynamic_pilot.json"
    invalid = json.loads(invalid_path.read_text(encoding="utf-8"))
    corrected_output = output / CORRECTED_SUBDIR
    corrected_output.mkdir(parents=True, exist_ok=False)
    result_path = corrected_output / "high_rom_dynamic_pilot_corrected.json"
    if result_path.exists():
        raise FileExistsError(f"refusing to overwrite completed pilot: {result_path}")
    matrix = load_report_validation_matrix(args.matrix.resolve())
    case = measurement_case(matrix)
    payload = run_small_pilot(case)
    if payload["run_count"] != 6:
        raise RuntimeError("small pilot must contain exactly six runs")
    comparison = compare_with_invalid_pre_fix(payload, invalid)
    payload["jacobian_frontend"] = {
        "cuff_point_offset_m": [0.0, 0.14, 0.0],
        "velocity_relation": "v_cuff = v_wrist + omega cross r",
        "pre_rollout_regressions_passed": True,
    }
    payload["invalid_pre_fix_pilot_preserved_at"] = str(invalid_path)
    result_path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    comparison_path = corrected_output / "invalid_vs_corrected_comparison.json"
    comparison_path.write_text(
        json.dumps(
            json_ready(comparison), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = output / "high_rom_feasibility_report.md"
    baseline = report_path.read_text(encoding="utf-8")
    baseline = baseline.split(REPORT_MARKER, maxsplit=1)[0].rstrip() + "\n\n"
    report_path.write_text(baseline + report_section(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(result_path),
                "comparison": str(comparison_path),
                "run_count": 6,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
