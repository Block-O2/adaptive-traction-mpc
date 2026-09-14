#!/usr/bin/env python3
"""Run the focused Stage-5 Goal-MPC attempt-02 consistency audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from traction_mpc_stage5.goal_mpc_consistency_audit import (
    run_goal_mpc_consistency_audit,
)


STAGE5_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--primary-trace",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/goal_mpc_smoke_v1/attempt_02/trace.npz"
        ),
    )
    parser.add_argument(
        "--primary-summary",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/goal_mpc_smoke_v1/attempt_02/summary.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results/goal_mpc_consistency_audit_v1",
    )
    args = parser.parse_args()
    summary = run_goal_mpc_consistency_audit(
        args.primary_trace,
        args.primary_summary,
        args.output_dir,
    )
    print(args.output_dir / "audit_summary.json")
    print(summary["force_execution_discrepancy"]["abort_physical_force_norm_n"])


if __name__ == "__main__":
    main()
