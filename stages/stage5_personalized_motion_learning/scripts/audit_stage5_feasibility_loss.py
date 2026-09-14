#!/usr/bin/env python3
"""Reproduce and audit the saved matched Goal-MPC feasibility loss."""

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
            / "feasibility_retention_v1"
            / "failure_reconstruction"
        ),
    )
    args = parser.parse_args()
    summary = run_goal_mpc_smoke(
        args.output_dir,
        maximum_duration_s=0.50,
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        stop_on_return_entry=False,
        use_bumpless_return_handoff=True,
        diagnose_feasibility_loss=True,
        feasibility_checkpoint_time_s=0.44,
    )
    print(json.dumps(summary["feasibility_loss_audit"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
