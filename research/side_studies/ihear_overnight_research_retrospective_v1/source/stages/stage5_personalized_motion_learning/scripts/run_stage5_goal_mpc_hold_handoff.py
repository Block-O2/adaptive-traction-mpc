#!/usr/bin/env python3
"""Run Goal-MPC OUTBOUND to loaded-equilibrium local HOLD handoff smoke."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "local_hold_v1"
            / "goal_mpc_handoff_01"
        ),
    )
    parser.add_argument("--maximum-duration-s", type=float, default=30.5)
    args = parser.parse_args()
    summary = run_goal_mpc_smoke(
        args.output_dir,
        maximum_duration_s=args.maximum_duration_s,
        use_loaded_local_hold=True,
        stop_on_return_entry=True,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
