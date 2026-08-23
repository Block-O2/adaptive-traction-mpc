#!/usr/bin/env python3
"""Run the rigid-cuff MuJoCo plant V2 posture validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.validation import (  # noqa: E402
    run_dynamic_rehab_baseline,
    run_rigid_cuff_posture_validation,
    write_dynamic_rehab_artifacts,
    write_rigid_cuff_posture_artifacts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to a timestamped local smoke directory.",
    )
    parser.add_argument(
        "--dynamic-baseline",
        action="store_true",
        help="Run the existing 15 s Human V2 rehab reference; no protective logic.",
    )
    parser.add_argument(
        "--lower-q2-deg",
        type=float,
        default=10.0,
        help="Lower reference endpoint; 10 is original, 3 is the engineering floor.",
    )
    parser.add_argument(
        "--hold-only",
        action="store_true",
        help="Run only the required one-second lower-endpoint hold.",
    )
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_name = (
        f"mujoco_rigid_cuff_dynamic_q2_{args.lower_q2_deg:g}_{timestamp}"
        if args.dynamic_baseline
        else f"mujoco_rigid_cuff_pose_v2_{timestamp}"
    )
    output_dir = args.output_dir or (
        REPOSITORY_ROOT / "linkage" / "results" / "local" / output_name
    )
    if args.dynamic_baseline:
        summary, trace = run_dynamic_rehab_baseline(
            args.lower_q2_deg,
            hold_only=args.hold_only,
        )
        write_dynamic_rehab_artifacts(output_dir, summary, trace)
        print(f"output_dir={output_dir}")
        print(f"termination_reason={summary['termination_reason']}")
        print(
            "mechanically_complete_for_follow_on="
            f"{summary['mechanically_complete_for_follow_on']}"
        )
        print(
            "peak_cuff_force_n="
            f"{summary['cuff']['peak_translational_force_n']:.6f}"
        )
        print(
            "peak_abs_cuff_my_nm="
            f"{summary['cuff']['peak_abs_sagittal_moment_my_nm']:.6f}"
        )
        return
    rows = run_rigid_cuff_posture_validation()
    write_rigid_cuff_posture_artifacts(output_dir, rows)
    print(f"output_dir={output_dir}")
    for row in rows:
        print(
            f"q2={row['q2_deg']:g}deg force={row['cuff_force_n']:.6f}N "
            f"My={row['cuff_my_nm']:.6f}Nm "
            f"torque_fraction={row['robot_peak_torque_limit_fraction']:.6f}"
        )
    print("protective_trajectory_run=False")


if __name__ == "__main__":
    main()
