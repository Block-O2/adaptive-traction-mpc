#!/usr/bin/env python3
"""Re-audit the professor's 120-degree High-ROM target set.

This is a kinematic, collision, and quasi-static audit only.  The selected
bedside base pose and 140 mm engineering adapter come from the completed
high-ROM geometry work; the base search is deliberately not repeated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage4.base_placement_high_rom import BasePose, audit_path_at_base
from traction_mpc_stage4.continuous_high_rom import enumerate_initial_ik_branches
from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.high_rom_human_v2 import (
    HIGH_ROM_ENDPOINTS_DEG,
    HIGH_ROM_HUMAN_V2,
    PRIMARY_ENDPOINT_NAMES,
    audit_passive_model,
    audit_quasistatic_paths,
    high_rom_config_payload,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
SELECTED_BASE = BasePose(0.80, -0.77, 0.36, 20.0)
REPORT_MARKER = "## Professor 120-degree High-ROM re-audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-count", type=int, default=121)
    parser.add_argument("--random-seed-count", type=int, default=40)
    return parser.parse_args()


def run_audit(sample_count: int, random_seed_count: int) -> dict[str, object]:
    world_from_base = SELECTED_BASE.transform()
    branches = enumerate_initial_ik_branches(
        UR10eTorqueRobot(),
        random_seed_count=random_seed_count,
        world_from_base=world_from_base,
    )
    paths = {
        name: audit_path_at_base(
            name,
            HIGH_ROM_ENDPOINTS_DEG[name],
            branches,
            world_from_base=world_from_base,
            sample_count=sample_count,
            retain_trace=True,
            human=HIGH_ROM_HUMAN_V2,
            robot_bed_is_blocker=False,
            use_actual_passive_model=True,
        )
        for name in PRIMARY_ENDPOINT_NAMES
    }
    quasistatic = audit_quasistatic_paths(sample_count=sample_count)
    passive = audit_passive_model(samples_per_joint=501)
    for name, path in paths.items():
        path["actual_high_rom_passive_mechanics"] = quasistatic["paths"][name]
        path["classification"] = (
            "READY FOR DYNAMIC PILOT"
            if path["revised_policy_continuous_feasible"]
            and quasistatic["paths"][name]["classification"]
            == "READY FOR DYNAMIC PILOT"
            else "MODEL-BLOCKED"
        )
    return {
        "schema_version": "professor_high_rom_120_path_audit_v1",
        "controller_or_dynamic_rollout_run": False,
        "canonical_human_overwritten": False,
        "high_rom_variant": high_rom_config_payload(),
        "selected_common_base": SELECTED_BASE.as_dict(),
        "selected_base_source": "completed base_placement_audit.json; search not repeated",
        "adapter": {
            "axial_standoff_m": 0.14,
            "interpretation": "engineering surrogate, not actual CR12 hardware",
        },
        "collision_policy": {
            "robot_bed_recorded_not_blocking": True,
            "lying_bed_thigh_shank_cuff_contacts_ignored": True,
            "required": [
                "continuous IK and joint limits",
                "finite nonsingular robot Jacobian",
                "robot self-collision absence",
                "unintended robot/adapter-Human collision absence",
                "distal ankle endpoint support-plane clearance",
                "actual-model cuff force <= 200 N",
            ],
        },
        "initial_exact_ik_branch_count": len(branches),
        "sample_count_per_path": sample_count,
        "passive_model_global_checks": passive["global_checks"],
        "paths": paths,
        "all_three_ready": all(
            path["classification"] == "READY FOR DYNAMIC PILOT"
            for path in paths.values()
        ),
    }


def report_section(audit: dict[str, object]) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "The engineering High-ROM variant now uses a common [0,125] deg "
            "envelope with 5 deg soft zones for hip and knee; canonical Human "
            "V2 remains unchanged. The 120 deg references lie at, but not inside, "
            "the upper soft-zone boundary."
        ),
        (
            "The completed common base [0.80,-0.77,0.36] m, yaw 20 deg and "
            "140 mm engineering wrist-to-cuff adapter were reused without a new "
            "placement search. Robot-bed contact is recorded but is not a blocker "
            "for this seated/suspended-setup question."
        ),
        "",
        "| path | decision | worst cond(J) | min joint margin | min robot/adapter-Human clearance | min distal clearance | peak passive hip/knee | peak cuff force | peak moment |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in PRIMARY_ENDPOINT_NAMES:
        path = audit["paths"][name]
        clear = path["minimum_clearance_by_required_domain_m"]
        mechanics = path["actual_high_rom_passive_mechanics"]
        passive = mechanics["peak_passive_left_by_joint"]
        lines.append(
            f"| {name} | {path['classification']} | "
            f"{path['robot']['worst_jacobian_condition']:.2f} | "
            f"{path['robot']['minimum_joint_limit_margin_deg']:.2f} deg | "
            f"{1000.0 * min(clear['robot_human_m'], clear['adapter_human_m']):.1f} mm | "
            f"{1000.0 * clear['distal_ankle_support_plane_m']:.1f} mm | "
            f"{passive['hip']['absolute_nm']:.2f}/{passive['knee']['absolute_nm']:.2f} Nm | "
            f"{mechanics['peak_cuff_force']['n']:.2f} N | "
            f"{mechanics['peak_cuff_moment']['nm']:.2f} Nm |"
        )
    lines.extend(
        [
            "",
            f"All three ready under the revised non-bed policy: `{audit['all_three_ready']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    audit = run_audit(args.sample_count, args.random_seed_count)
    path = output / "high_rom_120_path_audit.json"
    path.write_text(
        json.dumps(json_ready(audit), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    report_path = output / "high_rom_feasibility_report.md"
    baseline = report_path.read_text(encoding="utf-8")
    baseline = baseline.split(REPORT_MARKER, maxsplit=1)[0].rstrip() + "\n\n"
    report_path.write_text(baseline + report_section(audit), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(path),
                "all_three_ready": audit["all_three_ready"],
                "classifications": {
                    name: audit["paths"][name]["classification"]
                    for name in PRIMARY_ENDPOINT_NAMES
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
