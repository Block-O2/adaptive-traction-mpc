#!/usr/bin/env python3
"""Run the Stage-3B robot-only validation without writing formal evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


STAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_ROOT / "src"))

from traction_mpc_stage3.validation import run_robot_core_validation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=301)
    parser.add_argument("--gravity-hold-s", type=float, default=0.25)
    args = parser.parse_args()
    result = run_robot_core_validation(
        sample_count=args.samples,
        gravity_hold_duration_s=args.gravity_hold_s,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
