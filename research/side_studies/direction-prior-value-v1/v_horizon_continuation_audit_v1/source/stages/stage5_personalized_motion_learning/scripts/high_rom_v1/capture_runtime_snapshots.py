"""Opt-in development capture of deployable planner inputs for offline profiling.

The extra serialization is deliberately outside the frozen timing benchmark.
No hidden plant or evaluation truth enters these snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import run_dev_case
import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--plant-mode", choices=("high_rom", "low_rom"), default="high_rom")
    parser.add_argument("--capture-all-task", action="store_true")
    args = parser.parse_args()
    if args.snapshot_dir.exists() or args.output.exists():
        raise FileExistsError("diagnostic output must be new")
    args.snapshot_dir.mkdir(parents=True)
    original = runtime.snapshot_task_call
    captured: set[str] = set()
    task_count = 0

    def capture(planner, arguments):
        nonlocal task_count
        payload = original(planner, arguments)
        phase = str(getattr(arguments.get("phase"), "value", arguments.get("phase")))
        if args.capture_all_task or (phase not in captured and phase in ("OUTBOUND", "HOLD", "RETURN")):
            stem = f"task_{task_count:02d}_{phase.lower()}" if args.capture_all_task else phase.lower()
            path = args.snapshot_dir / f"{stem}.pickle"
            path.write_bytes(payload)
            (args.snapshot_dir / f"{stem}.json").write_text(json.dumps({
                "schema": "development_deployable_planner_snapshot_v1",
                "phase": phase, "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload), "source": "snapshot_task_call unchanged payload",
                "truth_in_controller": False}, indent=2) + "\n")
            captured.add(phase)
            task_count += 1
        return payload

    runtime.snapshot_task_call = capture
    sys.argv = [str(Path(run_dev_case.__file__)), "--case", str(args.case),
                "--output", str(args.output), "--host-monitor-limit-s", "300",
                "--plant-mode", args.plant_mode]
    try:
        run_dev_case.main()
    finally:
        runtime.snapshot_task_call = original


if __name__ == "__main__":
    main()
