#!/usr/bin/env python3
"""Run the offline contact-consistent MuJoCo plant mechanics audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.contact_feasibility import (  # noqa: E402
    run_contact_feasibility_audit,
    write_contact_feasibility_artifacts,
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
        / f"mujoco_contact_feasibility_{stamp}"
    )
    summary = run_contact_feasibility_audit()
    write_contact_feasibility_artifacts(output_dir, summary)
    print(f"output_dir={output_dir}")
    print(f"classification={summary['global_classification']}")
    print(
        "robot_only_feasible_entry_deg="
        f"{summary['robot_only_feasible_entry_deg']}"
    )
    print(f"robot_only_persistent_entry_deg={summary['robot_only_persistent_entry_deg']}")
    print(
        "contact_assisted_continuous_from_rest="
        f"{summary['contact_assisted_continuous_from_rest']}"
    )


if __name__ == "__main__":
    main()
