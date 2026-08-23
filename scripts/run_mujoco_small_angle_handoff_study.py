#!/usr/bin/env python3
"""Run the staged small-angle handoff engineering study."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.handoff_study import (  # noqa: E402
    run_staged_handoff_search,
    write_study_artifacts,
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
        / f"mujoco_small_angle_handoff_{stamp}"
    )
    summary, traces = run_staged_handoff_search()
    write_study_artifacts(output_dir, summary, traces)
    print(f"output_dir={output_dir}")
    for row in summary["candidate_rows"]:
        print(
            f"q_handoff={row['q_handoff_deg']:g} "
            f"status={row['status']} mechanism={row['direct_mechanism']}"
        )
    print(
        "minimum_tested_feasible_handoff_deg="
        f"{summary['minimum_tested_feasible_handoff_deg']}"
    )
    print(
        "architecture_small_angle_supported="
        f"{summary['architecture_small_angle_supported']}"
    )


if __name__ == "__main__":
    main()
