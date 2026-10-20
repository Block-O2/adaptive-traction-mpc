"""Replay immutable deployable planner snapshots; compare full decision records."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter_ns, process_time_ns

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in ("stages/stage5_personalized_motion_learning/src",
                 "stages/stage4_adaptive_control/src", "stages/stage3_full3d/src"):
    sys.path.insert(0, str(ROOT / relative))
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import execute_task_snapshot
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import _jsonable


def remove_timing(value):
    if isinstance(value, dict):
        return {k: remove_timing(v) for k, v in value.items() if k != "runtime_ms"}
    if isinstance(value, list):
        return [remove_timing(v) for v in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for phase in ("outbound", "hold", "return"):
        path = args.snapshot_dir / f"{phase}.pickle"
        payload = path.read_bytes()
        wall_start, cpu_start = perf_counter_ns(), process_time_ns()
        try:
            decision = execute_task_snapshot(payload)
            elapsed = (perf_counter_ns() - wall_start) / 1e6
            cpu = (process_time_ns() - cpu_start) / 1e6
            result = remove_timing(_jsonable(decision.record()))
            error = None
        except Exception as exc:
            elapsed = (perf_counter_ns() - wall_start) / 1e6
            cpu = (process_time_ns() - cpu_start) / 1e6
            result, error = None, f"{type(exc).__name__}:{exc}"
        rows.append({"phase": phase, "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
                     "wall_ms": elapsed, "cpu_ms": cpu, "error": error, "decision": result})
    output = {"schema": "high_rom_runtime_fixed_snapshot_replay_v1", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps([{"phase": x["phase"], "wall_ms": x["wall_ms"],
                       "error": x["error"]} for x in rows]))


if __name__ == "__main__":
    main()
