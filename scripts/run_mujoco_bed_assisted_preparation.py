#!/usr/bin/env python3
"""Run the MuJoCo bed-assisted small-angle preparation smoke study."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.bed_assisted_preparation import (  # noqa: E402
    run_staged_preparation,
    write_preparation_artifacts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (
        REPOSITORY_ROOT
        / "linkage"
        / "results"
        / "local"
        / f"mujoco_bed_assisted_preparation_{stamp}"
    )
    summary, traces = run_staged_preparation()
    write_preparation_artifacts(output_dir, summary, traces)
    print(f"output_dir={output_dir}")
    for row in summary["candidate_rows"]:
        print(
            f"target={row['target_q2_deg']:g} status={row['status']} "
            f"mechanism={row['direct_mechanism']} final_q={row['measured_final_q_deg']} "
            f"peak_force_n={row['peak_interaction_force_n']:.3f}"
        )
    print(f"small_angle_preparation_supported={summary['small_angle_preparation_supported']}")


if __name__ == "__main__":
    main()
