#!/usr/bin/env python3
"""Run the Stage-5 Goal-MPC low/moderate engineering smoke."""

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
        default=STAGE5_ROOT / "results" / "goal_mpc_v13" / "attempt_01",
    )
    parser.add_argument("--maximum-duration-s", type=float, default=30.5)
    parser.add_argument(
        "--record-selected-horizon-diagnostics", action="store_true"
    )
    args = parser.parse_args()
    summary = run_goal_mpc_smoke(
        args.output_dir,
        maximum_duration_s=args.maximum_duration_s,
        record_selected_horizon_diagnostics=(
            args.record_selected_horizon_diagnostics
        ),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
