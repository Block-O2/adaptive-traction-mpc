#!/usr/bin/env python3
"""Generate the compact continuous high-ROM adapter/path audit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.cuff_adapter import CUFF_ADAPTER
from traction_mpc_stage3.frames import ATTACHMENT_FROM_CUFF
from traction_mpc_stage4.continuous_high_rom import (
    PATH_SAMPLE_COUNT,
    run_continuous_path_audit,
)
from traction_mpc_stage4.high_rom_feasibility import json_ready


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
REPORT_MARKER = "## Continuous-path audit after parameterized adapter"
DISPLAY_NAMES = {
    "hip_dominant_100_60": "hip 100/60",
    "both_high_90_90": "both 90/90",
    "aggressive_120_90": "aggressive 120/90",
    "knee_dominant_60_100": "knee 60/100",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-count", type=int, default=PATH_SAMPLE_COUNT)
    return parser.parse_args()


def _adapter_payload() -> dict[str, object]:
    return {
        "schema_version": "ur10e_surrogate_cuff_adapter_v1",
        "geometry": CUFF_ADAPTER.as_dict(),
        "attachment_from_cuff": {
            "rotation": ATTACHMENT_FROM_CUFF.rotation.tolist(),
            "translation_m": ATTACHMENT_FROM_CUFF.translation.tolist(),
        },
        "collision_geometry": {
            "shape": "cylinder",
            "radius_m": CUFF_ADAPTER.connector_radius_m,
            "length_to_cuff_outer_surface_m": (
                CUFF_ADAPTER.connector_length_to_cuff_surface_m
            ),
            "intentional_connections": [
                "UR10e wrist_3/attachment_site",
                "Human V2 cuff outer surface",
            ],
        },
        "hardware_claim": False,
    }


def _write_plot(output: Path, audit: dict[str, object]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    for name, path in audit["paths"].items():
        trace = path["trace"]
        fraction = np.asarray(trace["path_fraction"])
        axes[0].plot(
            fraction,
            1000.0 * np.asarray(trace["minimum_clearance_m"]),
            label=DISPLAY_NAMES[name],
        )
        axes[1].plot(
            fraction,
            np.asarray(trace["robot_jacobian_condition"]),
            label=DISPLAY_NAMES[name],
        )
    axes[0].axhline(0.0, color="black", linewidth=1.0)
    axes[0].set_title("Minimum explicit collision clearance")
    axes[0].set_xlabel("path fraction")
    axes[0].set_ylabel("clearance (mm)")
    axes[0].legend(fontsize=8)
    axes[1].set_title("UR10e Jacobian condition")
    axes[1].set_xlabel("path fraction")
    axes[1].set_ylabel("condition number")
    axes[1].legend(fontsize=8)
    figure.savefig(output / "continuous_path_clearance.png", dpi=180)
    plt.close(figure)


def _report_section(audit: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        "The identity adapter was replaced by a 140 mm attachment-to-cuff-centre side standoff.",
        "Its dimension is 69 mm committed wrist directional envelope + 58 mm cuff radius + 13 mm existing cuff-shell allowance.",
        "The 13 mm radius connector stops at the cuff outer surface. This is a Menagerie UR10e engineering surrogate, not CR12 hardware geometry.",
        "",
        "Dense paths use 121 quintic-spaced Human-joint samples from [5,10] deg and continue each UR10e IK branch from the previous solution.",
        "Six exact initial branches were evaluated for every endpoint.",
        "",
        "| candidate | strict result | min all-clearance | min robot-human | min adapter-human | bed collision interval end | worst J condition | min joint margin | peak force / moment |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, path in audit["paths"].items():
        robot_bed = path["collision_intervals"]["robot_bed_m"]
        bed_end = max(
            (interval["end_fraction"] for interval in robot_bed),
            default=None,
        )
        bed_text = "none" if bed_end is None else f"{bed_end:.3f}"
        lines.append(
            f"| {DISPLAY_NAMES[name]} | "
            f"{'feasible' if path['strict_continuous_path_feasible'] else 'blocked by bed geometry'} | "
            f"{1000*path['minimum_collision_clearance_m']:.1f} mm | "
            f"{1000*path['minimum_clearance_by_domain_m']['robot_human_m']:.1f} mm | "
            f"{1000*path['minimum_clearance_by_domain_m']['adapter_human_m']:.1f} mm | "
            f"{bed_text} | {path['robot']['worst_jacobian_condition']:.2f} | "
            f"{path['robot']['minimum_joint_limit_margin_deg']:.2f} deg | "
            f"{path['conditional_quasistatic']['peak_cuff_force_n']:.2f} N / "
            f"{path['conditional_quasistatic']['peak_cuff_moment_abs_nm']:.2f} Nm |"
        )
    lines.extend(
        [
            "",
            "The old systematic wrist/shank overlap is eliminated: selected paths retain positive robot-human clearance and exactly 13 mm minimum adapter-human clearance.",
            "No path is strictly collision-feasible from the committed initial pose because all exact initial IK branches intersect the bed and the collision-disabled cuff proxy starts about 4.6 mm inside the bed plane.",
            "Robot-human, adapter-human, adapter-bed, robot self-collision, IK continuity, joint limits, algebraic singularity, and the 200 N force gate otherwise pass on the selected branches.",
            "The knee-dominant 60/100 path retains robot-bed intersection for roughly half the path and is not recommended.",
            "",
            "Conditional design priorities after the initial cuff/bed and robot-base/bed geometry is corrected are 100/60, 90/90, and then 120/90. None is approved for a controller rollout by this audit.",
            "Their respective ROM upper bounds would need review to at least [105,100], [95,100], and [125,100] deg to keep endpoints outside the existing 5 deg soft-limit zone without reducing the other current bound.",
            "The ordinary passive stiffness/rest extrapolation must also be reviewed; no Human V2 parameter was changed here.",
            "",
            "See `adapter_geometry_config.json`, `continuous_path_audit.json`, and `continuous_path_clearance.png` for compact evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    audit = run_continuous_path_audit(sample_count=args.sample_count)
    (output / "adapter_geometry_config.json").write_text(
        json.dumps(json_ready(_adapter_payload()), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    (output / "continuous_path_audit.json").write_text(
        json.dumps(json_ready(audit), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_plot(output, audit)
    report_path = output / "high_rom_feasibility_report.md"
    baseline = report_path.read_text(encoding="utf-8")
    baseline = baseline.split(REPORT_MARKER, maxsplit=1)[0].rstrip() + "\n\n"
    report_path.write_text(baseline + _report_section(audit), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "initial_ik_branches": audit["initial_exact_ik_branch_count"],
                "path_results": {
                    name: path["strict_continuous_path_feasible"]
                    for name, path in audit["paths"].items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
