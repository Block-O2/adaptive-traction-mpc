#!/usr/bin/env python3
"""Run the bounded Stage-3C gate sequence and preserve engineering artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage3.stage3c_validation import (
    run_coupled_scenario,
    write_scenario_artifacts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/engineering_stage3c"),
    )
    args = parser.parse_args()
    scenarios = (
        ("gate1_hold_5_10deg", dict(lower_q2_deg=10.0, duration_s=1.0, hold_only=True)),
        ("gate2_3deg_departure", dict(lower_q2_deg=3.0, duration_s=2.0, hold_only=False)),
        ("nominal_3deg_15s", dict(lower_q2_deg=3.0, duration_s=15.0, hold_only=False)),
    )
    summaries = {}
    for index, (name, parameters) in enumerate(scenarios):
        if index == 2 and not all(
            summaries[item]["mechanically_complete_for_next_gate"]
            for item in ("gate1_hold_5_10deg", "gate2_3deg_departure")
        ):
            summaries[name] = {"not_run": "prerequisite mechanical gate incomplete"}
            break
        summary, trace = run_coupled_scenario(**parameters)
        write_scenario_artifacts(args.output_dir, name, summary, trace)
        summaries[name] = summary
        print(json.dumps({name: summary}, indent=2, sort_keys=True))
    manifest = {
        "evidence_category": "engineering_validation_smoke",
        "command": (
            "PYTHONPATH=src python scripts/run_stage3c_nominal_smoke.py "
            f"--output-dir {args.output_dir}"
        ),
        "scientific_parameters_changed": False,
        "scenarios": summaries,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
