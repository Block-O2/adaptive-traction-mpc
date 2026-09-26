"""Run at most three frozen Stage-C cases per monitored dispatch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
PLAN = STAGE / "docs/high_rom_runtime_v1/CANDIDATE03_REGRESSION_PLAN.json"
OUTPUT = STAGE / "results/high_rom_runtime_v1/candidate03_regression"
STOP = STAGE / "docs/high_rom_v1/STOP"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    assert plan["denominator"] == len(plan["rows"]) == 49
    if args.start < 0 or args.start + args.count > 49:
        raise ValueError("batch outside frozen denominator")
    for relative, expected in plan["source_config_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"candidate source/config drift: {relative}")
    progress = []
    for index in range(args.start, args.start + args.count):
        if STOP.exists():
            raise RuntimeError("HIGH_ROM_USER_STOP")
        row = plan["rows"][index]
        case = ROOT / row["case"]
        if hashlib.sha256(case.read_bytes()).hexdigest() != row["case_sha256"]:
            raise RuntimeError(f"registered case drift: {row['id']}")
        dest = OUTPUT / row["id"]
        if dest.exists():
            raise FileExistsError(dest)
        command = [sys.executable, str(STAGE / "scripts/high_rom_v1/run_dev_case.py"),
                   "--case", str(case), "--output", str(dest),
                   "--plant-mode", row["plant"], "--host-monitor-limit-s", "300"]
        started = monotonic()
        result = subprocess.run(command, cwd=ROOT, check=False,
                                capture_output=True, text=True, timeout=330)
        saved = dest / "HIGH_ROM_CASE_RESULT.json"
        if not saved.is_file():
            raise RuntimeError(f"run did not save case evidence: {row['id']}: {result.stderr[-1000:]}")
        report = json.loads(saved.read_text())
        record = {"index": index, "id": row["id"], "status": report["status"],
                  "abort_reason": report.get("abort_reason"),
                  "elapsed_host_s": monotonic() - started, "exit_code": result.returncode,
                  "output": str(dest)}
        progress.append(record)
        print(json.dumps(record), flush=True)
    progress_file = STAGE / "docs/high_rom_runtime_v1/REGRESSION_PROGRESS.jsonl"
    with progress_file.open("a") as stream:
        for record in progress:
            stream.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
