#!/usr/bin/env python3
"""Run the registered MuJoCo sleeve/robot V2 engineering validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.validation import (  # noqa: E402
    run_validation,
    write_artifacts,
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
        REPOSITORY_ROOT / "linkage" / "results" / "local" / f"mujoco_sleeve_robot_v2_{timestamp}"
    )
    summary, traces = run_validation()
    write_artifacts(output_dir, summary, traces)
    equilibria = ", ".join(
        f"{row['q2_deg']:g}deg={'pass' if row['passed'] else 'fail'}"
        for row in summary["dynamic_equilibria"]
    )
    print(f"output_dir={output_dir}")
    print(f"fixture_gate_passed={summary['fixture_gate_passed']}")
    print(f"dynamic_equilibria={equilibria}")
    print(
        "dynamic_authority_gate_passed="
        f"{summary['dynamic_authority_gate_passed']}"
    )
    print(f"complete_protective_motion={summary['complete_protective_motion']}")


if __name__ == "__main__":
    main()
