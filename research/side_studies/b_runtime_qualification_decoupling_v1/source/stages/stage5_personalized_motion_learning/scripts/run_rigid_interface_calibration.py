#!/usr/bin/env python3
"""Generate the Stage-5 rigid-interface engineering calibration artifacts."""

from __future__ import annotations

import json

from traction_mpc_stage5.calibration import run_rigid_interface_calibration
from traction_mpc_stage5.config import STAGE5_ROOT


def main() -> None:
    output = STAGE5_ROOT / "results" / "rigid_interface_calibration"
    report = run_rigid_interface_calibration(output)
    compact = {
        "evidence_category": report["evidence_category"],
        "selection": report["selection"],
        "candidate_summary": [
            {
                key: row[key]
                for key in (
                    "candidate",
                    "probe_count",
                    "all_finite",
                    "warning_probe_count",
                    "unsettled_probe_count",
                    "maximum_ringing_zero_crossings",
                    "maximum_peak_force_n",
                )
            }
            for row in report["candidate_dynamic_sweep"]
        ],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
