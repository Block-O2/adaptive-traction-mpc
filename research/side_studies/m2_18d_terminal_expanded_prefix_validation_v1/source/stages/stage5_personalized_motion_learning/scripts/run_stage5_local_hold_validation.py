#!/usr/bin/env python3
"""Run the Stage-5 loaded-equilibrium local HOLD engineering validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.hold_validation import run_local_hold_validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "local_hold_v1" / "attempt_01",
    )
    args = parser.parse_args()
    summary = run_local_hold_validation(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
