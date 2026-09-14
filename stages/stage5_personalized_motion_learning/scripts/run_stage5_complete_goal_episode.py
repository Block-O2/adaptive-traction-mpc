#!/usr/bin/env python3
"""Run the matched-model Stage-5 non-learning complete-episode smoke."""

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
            / "goal_mpc_complete_v1"
            / "attempt_01_existing_return"
        ),
    )
    args = parser.parse_args()
    summary = run_goal_mpc_smoke(
        args.output_dir,
        use_loaded_local_hold=True,
        stop_on_return_entry=False,
        use_bumpless_return_handoff=True,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
