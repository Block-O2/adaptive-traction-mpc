#!/usr/bin/env python3
"""Run the explicitly limited Stage-5 prescribed-trajectory sanity replay."""

from __future__ import annotations

import json

from traction_mpc_stage5.baseline_replay import run_limited_baseline_replay
from traction_mpc_stage5.config import STAGE5_ROOT


def main() -> None:
    output = STAGE5_ROOT / "results" / "rigid_interface_calibration" / "baseline_replay"
    report = run_limited_baseline_replay(output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
