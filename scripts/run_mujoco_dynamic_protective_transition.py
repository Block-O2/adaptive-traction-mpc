#!/usr/bin/env python3
"""Run the fixed 3-degree-floor dynamic protective-transition diagnostic."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.dynamic_transition import (  # noqa: E402
    run_dynamic_transition_matrix,
    write_dynamic_transition_artifacts,
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
        / f"mujoco_dynamic_protective_transition_{stamp}"
    )
    summary, traces = run_dynamic_transition_matrix()
    write_dynamic_transition_artifacts(output_dir, summary, traces)
    print(f"output_dir={output_dir}")
    for row in summary["forward_rows"]:
        print(
            f"forward_3_to_{row['target_q2_deg']:g}={row['status']} "
            f"reason={row['failure_reason']} peak={row['peak_sleeve_force_n']:.3f}N "
            f"final_q2={row['final_q_deg'][1]:.3f}deg"
        )
    for row in summary["reverse_rows"]:
        print(
            f"reverse_{row['start_q2_deg']:g}_to_3={row['status']} "
            f"reason={row['failure_reason']} peak={row['peak_sleeve_force_n']:.3f}N "
            f"final_q2={row['final_q_deg'][1]:.3f}deg"
        )
    print(
        "continuous_safe_dynamic_bridge_exists="
        f"{summary['continuous_safe_dynamic_bridge_exists']}"
    )


if __name__ == "__main__":
    main()
