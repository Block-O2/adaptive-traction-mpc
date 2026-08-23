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
    run_rigid_cuff_posture_validation,
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
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (
        REPOSITORY_ROOT / "linkage" / "results" / "local" / f"mujoco_rigid_cuff_pose_v2_{timestamp}"
    )
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
